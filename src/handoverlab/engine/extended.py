# SPDX-License-Identifier: MIT
"""Protocol engine of the optional models of 1.10.0.

:class:`ExtEngine` runs a rule when a scenario uses SSB beams or several
carriers (``radio.beams``, ``radio.layers``), the measurement periods of
TS 38.133 (``protocol.meas_periods = "ts38133"``) or the RLM evaluation
periods of TS 38.133 (``protocol.rlm_eval = "ts38133"``).  Otherwise
:class:`~handoverlab.engine.core.Engine` runs unchanged.  Without any of these
options :class:`ExtEngine` gives the same event log as :class:`Engine`
(``handoverlab verify`` checks this).

What changes against :class:`Engine`

* Several carriers: only cells of the same carrier interfere; noise and
  bandwidth are those of each cell's carrier.
* SSB beams: the serving cell transmits on the UE's serving beam (TCI state);
  radio-link monitoring uses the serving beam (``rlm_rs = "tci"``) or the best
  of the N_RLM beams of the last report (``"beams"``); beam management, beam
  failure detection and recovery as described in
  :class:`~handoverlab.config.BeamConfig`.  A handover or a re-establishment
  joins the target on its best reported beam.  Beam failure recovery does
  not touch T310 (TS 38.133 clause 8.1 runs on its own); a random-access
  problem of the recovery is a radio-link failure (TS 38.331 clause
  5.3.10.3, T304 not running).
* Measurement periods (``ts38133``): the L1 result of a cell is the linear
  average of its samples over the measurement period -- intra-frequency
  (TS 38.133 Tables 9.2.5.2-1/-2) or inter-frequency within the gaps of
  ``protocol.gap_pattern`` (Tables 9.3.5-1/-2) -- and enters the L3 filter
  once per period, with the coefficient adapted to that rate (TS 38.331
  clause 5.5.3.2, reference X = the intra-frequency period of the cell's
  frequency range).  With several carriers every user has the gap pattern
  and receives no data during the gaps (TS 38.133 clause 9.1.2).
* RLM evaluation (``ts38133``): the Qout / Qin windows of the serving cell's
  frequency range (TS 38.133 Tables 8.1.2.2-1/-2).
"""
from __future__ import annotations

import math

import numpy as np

from .. import requirements as req
from ..measurement import EPS, INF, L3Filter
from .core import LN10_10, Engine, rlm_indications
from .procedures import CONNECTED, EXECUTING


def uses_extended(world) -> bool:
    """True if ``world`` needs :class:`ExtEngine`."""
    P = world.scenario.protocol
    return world.ext is not None or P.meas_periods != "sample" or P.rlm_eval != "fixed"


class ExtEngine(Engine):
    """Engine for beams, several carriers and the TS 38.133 measurement and evaluation periods."""

    def __init__(self, world, rule, log_events=False, debug=None):
        super().__init__(world, rule, log_events, debug)
        sc = world.scenario
        P, R = sc.protocol, sc.radio
        ext = self.ext = world.ext
        M, U = self.M, self.U
        if ext is None:                                       # one carrier, no beams
            self.car = np.zeros(M, dtype=int)
            self.nc = 1
            self.chi_c = np.full(M, R.isolation)
            self.noise_c = np.full(M, self.noise)
            self.W_c = np.full(M, self.W)
            self.f_c = np.full(M, R.carrier_ghz)
            self.has_b = np.zeros(M, dtype=bool)
            self.re_off = np.zeros(M)
            self.layer_of = np.zeros(M, dtype=int)
            self.bcfg = [None]
        else:
            self.car, self.nc = ext.cell_carrier, ext.n_carriers
            self.chi_c, self.noise_c, self.W_c = ext.chi, ext.noise_mw, ext.bw_hz
            self.f_c = ext.carrier_ghz
            self.has_b = ext.has_beams
            self.re_off = ext.re_off
            self.layer_of = ext.cell_layer
            self.bcfg = [L.beams for L in ext.layers]
            if self.std:                                      # energy: each cell with the power of its layer
                p_l = np.array([10.0 ** (L.radio.tx_power_dbm / 10.0) / 1000.0 for L in ext.layers])
                self.ptx_c = p_l[ext.cell_layer]
                self.acc["load_ptx"] = 0.0
        # the formulas of Engine where they still hold exactly (one carrier, one isolation, no beams)
        self.uniform = self.nc == 1 and bool(np.all(self.chi_c == self.chi_c[0])) and not self.has_b.any()
        if not self.uniform:
            self.rc = self.chi_c * self.rho
            self.rc_lm = self.rc.copy()
        self.mask = (self.car[:, None] == np.arange(self.nc)[None, :]).astype(float)       # (M, carriers)
        self.lab_chi_c = self.chi_c * sc.traffic.label_load
        self.beams = bool(self.has_b.any())
        self.dt_ = P.step_s
        # RLM evaluation windows (per user: they depend on the serving cell's frequency range)
        self.rlm38 = P.rlm_eval == "ts38133"
        if self.rlm38:
            self.ao = np.full(U, self.ao)
            self.ai = np.full(U, self.ai)
        # measurement periods
        self.mp38 = P.meas_periods == "ts38133"
        self.gaps = self.nc > 1 and self.mp38
        mgl, mgrp = req.GAP_PATTERNS[P.gap_pattern]
        self.gap_share = mgl / mgrp if self.gaps else 0.0
        self.cell_fr2 = np.array([req.is_fr2(f) for f in self.f_c])
        if not self.mp38 and self.std:                        # X of TS 38.331 5.5.3.2 per cell (its carrier's FR)
            self.l3 = L3Filter(P.l3_k, self.mdt, np.array([req.l3_reference_period(f, P.ssb_period_s,
                                                                                    P.fr2_power_class)
                                                           for f in self.f_c]))
        if self.mp38:
            n_inter = self.nc - 1                              # inter-frequency layers sharing the gaps (CSSF)
            t_intra = np.array([req.intra_meas_period(f, P.ssb_period_s, P.fr2_power_class) for f in self.f_c])
            t_inter = np.array([req.inter_meas_period(f, mgrp, P.ssb_period_s, P.fr2_power_class,
                                                      cssf=max(n_inter, 1)) for f in self.f_c])
            x_ref = t_intra                                    # X of TS 38.331 5.5.3.2 (no CSSF in single carrier)
            self.p_intra = np.maximum(1, np.rint(t_intra / self.mdt)).astype(int)
            self.p_inter = np.maximum(1, np.rint(t_inter / self.mdt)).astype(int)
            a_ref = 0.5 ** (P.l3_k / 4.0)
            self.a_intra = 1.0 - (1.0 - a_ref) ** (self.p_intra * self.mdt / x_ref)
            self.a_inter = 1.0 - (1.0 - a_ref) ** (self.p_inter * self.mdt / x_ref)
            self.macc = np.zeros((U, M))
            self.mcnt = np.zeros((U, M), dtype=int)
            self.t_intra, self.t_inter = t_intra, t_inter
        # beams
        if self.beams:
            self.sb = np.zeros(U, dtype=int)                   # serving beam (TCI state)
            self.tci_on = np.zeros(U, dtype=bool)
            self.tci_b = np.zeros(U, dtype=int)
            self.tci_t = np.full(U, INF)
            self.bf = None                                     # (U, M, B) filtered beam L1-RSRP [dBm]
            self.a_bf = np.empty(M)
            self.n_rlm = np.ones(M, dtype=int)
            self.rlm_set = np.zeros((U, 8), dtype=int)         # RLM-RS beams (rlm_rs = "beams")
            self.rlm_have = np.zeros(U, dtype=bool)            # the set was chosen from a beam report
            # Qout_LR of beam failure detection on the SSB: TS 38.133 Table 8.5.2.1-1 has the hypothetical PDCCH at
            # 0 dB to the SSS, Table 8.1.2.1-1 (Qout of RLM) at +4 dB, both at the same BLER, so Qout_LR is 4 dB
            # above Qout in SSB SINR (since 2.1.0; 2.0.0: Qout_LR = Qout)
            self.qout_lr = self.qout * (10 ** 0.4 if self.std else 1.0)
            self.t_ind = np.empty(M)
            self.a_bfd = np.empty(M)
            for c in range(M):
                b = self.bcfg[self.layer_of[c]]
                f = self.f_c[c]
                n = (b.rx_sweep_n if b is not None and b.rx_sweep_n else req.rx_sweep_factor(f))
                if self.std and not (b is not None and b.rx_sweep_n) and req.is_fr2(f):
                    n = 8                       # TS 38.133 9.5.4.1: N = 8 in Table 9.5.4.1-2 (all of FR2)
                # T_L1-RSRP = max(T_Report, ceil(M P N) T_SSB), TS 38.133 Tables 9.5.4.1-1/-2 (T_Report since 2.1.0)
                t_l1 = req.l1_rsrp_period(P.ssb_period_s, n, t_report=b.report_s if (self.std and b is not None)
                                          else 0.0)
                self.a_bf[c] = 1.0 - math.exp(-self.mdt / t_l1)
                self.n_rlm[c] = req.n_rlm(f)
                self.t_ind[c] = req.bfd_indication_interval(P.ssb_period_s)
                self.a_bfd[c] = 1.0 - math.exp(-self.dt_ / req.bfd_evaluation_period(P.ssb_period_s, n))
            self.bfd_q = np.zeros(U)                           # BFD-RS quality, averaged (linear SINR)
            self.bfi = np.zeros(U, dtype=int)                  # BFI_COUNTER
            self.bfd_end = np.full(U, -INF)                    # beamFailureDetectionTimer expiry
            self.bfd_next = np.zeros(U)                        # next L1 indication instant
            self.bfr = np.zeros(U, dtype=bool)                 # random access for beam failure recovery ongoing
            self.bfr_end = np.full(U, -INF)                    # beamFailureRecoveryTimer expiry (-inf: not running)
            self.bfr_att_t = np.full(U, INF)                   # end of the current preamble attempt
            self.bfr_beam = np.zeros(U, dtype=int)
            self.bfr_n = np.zeros(U, dtype=int)                # PREAMBLE_TRANSMISSION_COUNTER - 1
            self.bfr_t0 = np.zeros(U)
            self.rep_next = 0.0
        for k in ("beam_switch", "bfr", "bfr_ok", "bfr_fail", "ho_inter"):
            self.C[k] = 0
        self.acc["bfr_time"] = 0.0
        self.acc["gap_time"] = 0.0

    # ------------------------------------------------------------------ powers and SINR
    def _tot(self, ln, rc):
        """Interference sums (U, carriers) with weights ``rc``."""
        if self.nc == 1:
            return (ln @ rc)[:, None]
        return ln @ (rc[:, None] * self.mask)

    def _beam_power(self, i, ch, users, cells, beams):
        """Received power [mW] of ``beams`` of ``cells`` at ``users`` in step ``i`` of chunk ``ch``."""
        ext = self.ext
        g = ch.bg[i // ch.mp, users, cells, beams]
        return np.exp((ch.site_db[i, users, ext.cell_site[cells]] + ext.p0[cells] + g) * LN10_10)

    def _desired(self, i, ch, ln, serv):
        """Power of the serving cell on the serving beam (U,)."""
        ar = self.ar
        ls = ln[ar, serv]
        if self.beams:
            hb = self.has_b[serv]
            if hb.any():
                u = ar[hb]
                ls = ls.copy()
                ls[u] = self._beam_power(i, ch, u, serv[u], self.sb[u])
        return ls

    def _sinr_one(self, u, cell, ln, totc, power=None):
        lc = ln[u, cell]
        p = lc if power is None else power
        return p / (totc[u, self.car[cell]] - self.rc[cell] * lc + self.noise_c[cell])

    def _best_beam(self, u, cell) -> int:
        if not self.beams or not self.has_b[cell] or self.bf is None:
            return 0
        return int(np.argmax(self.bf[u, cell]))

    # ------------------------------------------------------------------ overrides of Engine
    def _attach(self, u, cell, s, t=None):
        super()._attach(u, cell, s, t)
        if self.rlm38:
            T = req.rlm_evaluation_periods(self.P.ssb_period_s, self._sweep_n(cell))
            self.ao[u] = 1.0 - np.exp(-self.P.step_s / T[0])
            self.ai[u] = 1.0 - np.exp(-self.P.step_s / T[1])
        if self.beams:
            self.sb[u] = self._best_beam(u, cell)
            self.rlm_have[u] = False                          # the RLM-RS set of the new cell comes with a report
            self._beam_reset(u, t if t is not None else 0.0)
            if self.has_b[cell] and getattr(self, "_ch", None) is not None:
                # monitoring starts from the quality of the beam the UE joined on
                ch, i = self._ch, self._i
                ln = ch.lin[i]
                rcx = self.rc_lm if self.lm else self.rc
                tl = self._tot(ln, rcx)
                p = self._beam_power(i, ch, np.array([u]), np.array([cell]), np.array([self.sb[u]]))[0]
                q = p / (tl[u, self.car[cell]] - rcx[cell] * ln[u, cell] + self.noise_c[cell])
                self.qo[u] = self.qi[u] = q
                self.bfd_q[u] = q
            else:
                self.bfd_q[u] = self.qo[u]

    def _sweep_n(self, cell) -> int:
        b = self.bcfg[self.layer_of[cell]]
        return b.rx_sweep_n if (b is not None and b.rx_sweep_n) else req.rx_sweep_factor(self.f_c[cell])

    def _beam_reset(self, u, t):
        self.tci_on[u] = False
        self.bfi[u] = 0
        self.bfd_end[u] = -INF
        self.bfr[u] = False
        self.bfr_end[u] = -INF
        self.bfr_att_t[u] = INF
        self.bfd_next[u] = t

    def start_exec(self, u, tgt, t):
        if self.beams and self.bfr[u]:
            self._bfr_stop(u, t, ok=False, counted_fail=False)
        super().start_exec(u, tgt, t)
        if self.beams:
            self.tci_on[u] = False

    def fail(self, u, t, kind):
        if self.beams and self.bfr[u]:
            self._bfr_stop(u, t, ok=False, counted_fail=False)
        super().fail(u, t, kind)
        if self.beams:
            self.tci_on[u] = False

    def _end_exec(self, u, t, ln, tot):
        tgt = int(self.f_tgt[u])
        if self.uniform:
            return super()._end_exec(u, t, ln, tot[:, 0] if tot.ndim == 2 else tot)
        b = self._best_beam(u, tgt)
        p = None
        if self.beams and self.has_b[tgt]:
            p = self._beam_power(self._i, self._ch, np.array([u]), np.array([tgt]), np.array([b]))[0]
        s = self._sinr_one(u, tgt, ln, tot, p)
        if s < self.qout and self.P.exec_can_fail:
            t304 = self.P.t304_s
            if t304 is not None and t - self.f_tx[u] < t304 - EPS:
                self.t_done[u] = t + self.dt
                if t >= self.t0c and (not self.daps_u[u] or self.src_rlf[u]):   # DAPS: the source carries data
                    self.acc["int_exec"] += self.dt
                return
            if not (self.proc.fallback and self.daps_u[u] and self._fallback(u, t, ln, tot)):
                self.fail(u, t, "exec")
            return
        src = int(self.serv[u])
        if self.car[src] != self.car[tgt] and self.f_cnt[u]:
            self.C["ho_inter"] += 1
        # the rest of Engine._end_exec with the SINR computed here
        pp = (self.prev[u] == tgt) and (t - self.last_ho[u] < self.P.pingpong_s)
        cnt = bool(self.f_cnt[u])
        if cnt:
            self.C["ho"] += 1
            self.msg(t)                                        # RRCReconfigurationComplete to the target
            self.C["pp"] += int(pp)
        self.proc.after_execution(u, tgt, t)
        self.prev[u] = src
        self.last_ho[u] = t
        self._attach(u, tgt, s, t)
        self.w_on[u] = True; self.w_t0[u] = t; self.w_ta[u] = self.f_t[u]; self.w_tx[u] = self.f_tx[u]
        self.w_src[u] = src; self.w_tgt[u] = tgt; self.w_key[u] = self.f_key[u]
        self.w_np[u] = self.f_np[u]; self.w_oe[u] = self.f_oe[u]; self.w_cnt[u] = cnt
        self.w_n[u] = 0; self.w_g[u] = 0; self.w_m[u] = 0; self.w_cf[u] = 0; self.w_cff[u] = False
        self.w_mcf[u] = 0; self.w_mcff[u] = False; self.w_pp[u] = pp
        self.f_on[u] = False

    def _fallback(self, u, t, ln, tot):
        if self.uniform:
            return super()._fallback(u, t, ln, tot[:, 0] if tot.ndim == 2 else tot)
        src = int(self.serv[u])
        p = None
        if self.beams and self.has_b[src]:
            p = self._beam_power(self._i, self._ch, np.array([u]), np.array([src]), np.array([self.sb[u]]))[0]
        s = self._sinr_one(u, src, ln, tot, p)
        if (self.src_rlf[u] if self.daps_mon else s < self.qout):     # TS 38.331 5.3.5.8.3 (see Engine._fallback)
            return False
        from ..rules.base import EARLY
        self._feedback(u, src, self.f_tgt[u], self.f_key[u], EARLY, t)
        if self.trace_log is not None:
            self.trace_event(t, u, "fallback", src, self.f_tgt[u], 10.0 * np.log10(max(float(s), 1e-30)))
        self._close_flight(u, t, "too_early", "daps_fallback")
        self.state[u] = CONNECTED
        self.proc.on_attach(u)
        return True

    def _sinr_lm(self, u, cell, ln) -> float:
        if self.uniform:
            return super()._sinr_lm(u, cell, ln)
        tl = self._tot(ln, self.rc_lm)
        lc = ln[u, cell]
        return lc / (tl[u, self.car[cell]] - self.rc_lm[cell] * lc + self.noise_c[cell])

    def _update_lm(self, con) -> None:
        if self.uniform:
            return super()._update_lm(con)
        n = np.bincount(self.serv[con], minlength=self.M)
        np.multiply(self.chi_c, np.minimum(1.0, self.lm0 + self.P.lm_load_per_ue * n), out=self.rc_lm)

    # ------------------------------------------------------------------ main loop
    def _init(self, ch):
        if self.beams:
            self.bf = ch.bl1[0].copy()
        self.l3.reset(ch.l1[0])
        self.serv[:] = np.argmax(self.meas, axis=1)
        self.started = True
        if self.lm:
            self._update_lm(self.state == CONNECTED)
        if self.trace_log is not None:
            t0 = ch.k0 * self.dt
            for u in range(self.U):
                self.trace_event(t0, u, "serve", -1, self.serv[u])
        ln = ch.lin[0]
        if self.beams:
            for u in range(self.U):
                self.sb[u] = self._best_beam(u, int(self.serv[u]))
        self._i, self._ch = 0, ch
        totc = self._tot(ln, self.rc_lm if self.lm else self.rc)
        ls_ref = ln[self.ar, self.serv]
        ls = self._desired(0, ch, ln, self.serv)
        rcx = self.rc_lm if self.lm else self.rc
        s = ls / (totc[self.ar, self.car[self.serv]] - rcx[self.serv] * ls_ref + self.noise_c[self.serv])
        self.qo[:] = s
        self.qi[:] = s
        if self.rlm38:
            for u in range(self.U):
                T = req.rlm_evaluation_periods(self.P.ssb_period_s, self._sweep_n(int(self.serv[u])))
                self.ao[u] = 1.0 - np.exp(-self.P.step_s / T[0])
                self.ai[u] = 1.0 - np.exp(-self.P.step_s / T[1])
        if self.beams:
            self.bfd_q[:] = s

    def advance(self, ch) -> None:
        import time
        w0 = time.perf_counter()
        if not self.started:
            self._init(ch)
        P, dt, ar = self.P, self.dt, self.ar
        state, run = self.state, self.run
        qout, qin = self.qout, self.qin
        qo, qi = self.qo, self.qi
        simple = P.n310 == 1 and P.n311 == 1
        cnz = np.count_nonzero
        for i in range(ch.n):
            k = ch.k0 + i
            t = k * dt
            ln = ch.lin[i]
            self._i, self._ch = i, ch
            totc = self._tot(ln, self.rc)
            if self.lm:
                self.lm_ln = ln
            # --- end of an execution or of a re-establishment
            if cnz(state):
                for u in np.nonzero((state != CONNECTED) & (t >= self.t_done - EPS))[0]:
                    if state[u] == EXECUTING:
                        self._end_exec(u, t, ln, totc)
                    else:
                        c = int(self.re_cell[u])
                        if self.uniform:
                            lc = ln[u, c]
                            s = lc / (totc[u, 0] - self.rc[c] * lc + self.noise)
                        else:
                            b = self._best_beam(u, c)
                            p = None
                            if self.beams and self.has_b[c]:
                                p = self._beam_power(i, ch, np.array([u]), np.array([c]), np.array([b]))[0]
                            s = self._sinr_one(u, c, ln, totc, p)
                        if self._recovery_joins(u, s, t):
                            self._attach(u, c, s, t)
            serv = self.serv
            con = state == CONNECTED
            ls_ref = ln[ar, serv]
            if self.uniform:
                sinr = ls_ref / (totc[:, 0] - self.rc[serv] * ls_ref + self.noise)
                ls = ls_ref
            else:
                ls = self._desired(i, ch, ln, serv)
                sinr = ls / (totc[ar, self.car[serv]] - self.rc[serv] * ls_ref + self.noise_c[serv])
            # --- radio-link monitoring
            if self.lm:
                rl = self.rc_lm
                if self.uniform:
                    sl = ls / (ln @ rl - rl[serv] * ls + self.noise)
                else:
                    tl = self._tot(ln, rl)
                    ilm = tl[ar, self.car[serv]] - rl[serv] * ls_ref + self.noise_c[serv]
                    sl = ls / ilm
            else:
                ilm = totc[ar, self.car[serv]] - self.rc[serv] * ls_ref + self.noise_c[serv]
                sl = sinr
            ssb_q = sl                                          # quality of the serving beam's SSB (BFD-RS)
            if self.beams:
                sl = self._rlm_quality(i, ch, serv, sl, ilm, con)
            qo += self.ao * (sl - qo)
            qi += self.ai * (sl - qi)
            if self.std:                                       # TS 38.331 7.2 / TS 38.133 8.1.6 (since 2.1.0)
                mon = con | ((state == EXECUTING) & self.daps_u & ~self.src_rlf) if self.daps_mon else con
                if k % self.ind_steps == 0:
                    start = rlm_indications(P, qo, qi, qout, qin, run, self.n_o, self.n_i, mon, t, self.rlm_t0)
                    self.t310[start] = t
                    self.k310[start] = k
                if cnz(run):
                    for u in np.nonzero(run & mon & (t - self.t310 >= P.t310_s - EPS))[0]:
                        if state[u] == EXECUTING:
                            self._source_rlf(u, t)
                        else:
                            self.fail(u, t, "rlf")
            else:
                if simple:
                    start = (qo < qout) & con & ~run
                else:
                    self.n_o[:] = (self.n_o + 1) * (qo < qout)
                    self.n_i[:] = (self.n_i + 1) * (qi > qin)
                    start = con & ~run & (self.n_o >= P.n310)
                if P.rlm_holdoff_s > 0:
                    start &= t >= self.rlm_t0 - EPS
                if cnz(start):
                    run |= start
                    self.t310[start] = t
                    self.k310[start] = k
                if cnz(run):
                    run &= ~((qi > qin) if simple else (self.n_i >= P.n311))
                    for u in np.nonzero(run & con & (t - self.t310 >= P.t310_s - EPS))[0]:
                        self.fail(u, t, "rlf")
            # --- beam management, beam failure detection and recovery
            if self.beams:
                self._beam_step(i, ch, t, ssb_q, ilm, ln, totc)
            # --- handover command / conditional configuration reaches the UE
            self.sl_now = sl
            self.proc.step(t)
            # --- measurement instant
            if i % self.mp == 0:
                self._measure(ch, i // self.mp, k, t, ln, totc)
        self.wall += time.perf_counter() - w0

    def _rlm_quality(self, i, ch, serv, s_tci, ilm, con):
        """Link quality for radio-link monitoring: the serving beam, or the best of the RLM-RS set."""
        out = s_tci.copy()
        users = np.nonzero(con & self.has_b[serv])[0]
        if not len(users):
            return out
        for u in users:
            c = int(serv[u])
            if self.bcfg[self.layer_of[c]].rlm_rs != "beams":
                continue
            n = self.n_rlm[c]
            beams = self.rlm_set[u, :n]
            p = self._beam_power(i, ch, np.full(n, u), np.full(n, c), beams)
            if self.std:                     # 2.1.0: the N_RLM RLM-RS only (TS 38.133 Table 8.1.1-2)
                out[u] = float(p.max() / ilm[u]) if self.rlm_have[u] else float(s_tci[u])
            else:
                out[u] = max(float(s_tci[u]), float(p.max() / ilm[u]))
        return out

    # ------------------------------------------------------------------ beams
    def _beam_step(self, i, ch, t, ssb_q, ilm, ln, totc):
        """TCI switches, beam failure detection (TS 38.321 5.17) and recovery by random access, per step."""
        state, serv = self.state, self.serv
        con = state == CONNECTED
        hb = self.has_b[serv] & con
        if not hb.any():
            return
        counted = t >= self.t0c
        # serving-beam changes ordered by the gNB (MAC CE TCI state activation)
        for u in np.nonzero(hb & self.tci_on & (t >= self.tci_t - EPS))[0]:
            self.tci_on[u] = False
            if self.bfr[u] or self.tci_b[u] == self.sb[u]:
                continue
            self.sb[u] = self.tci_b[u]
            self.bfi[u] = 0                                   # the BFD reference signal changed
            c = int(serv[u])
            self.bfd_q[u] = self._beam_power(i, ch, np.array([u]), np.array([c]),
                                             np.array([self.sb[u]]))[0] / ilm[u]
            self.C["beam_switch"] += int(counted)
            if self.trace_log is not None:
                self.trace_event(t, u, "beam_switch", serv[u], serv[u], float(self.sb[u]))
        # beam failure detection: quality of the BFD-RS averaged over T_Evaluate_BFD
        a = self.a_bfd[serv]
        self.bfd_q += np.where(hb, a * (ssb_q - self.bfd_q), 0.0)
        cfg = self.bcfg
        for u in np.nonzero(hb & (t >= self.bfd_next - EPS))[0]:
            c = int(serv[u])
            b = cfg[self.layer_of[c]]
            self.bfd_next[u] = t + self.t_ind[c]
            if not b.bfd:
                continue
            if self.std:
                # TS 38.321 5.17: an indication restarts beamFailureDetectionTimer; the counter is reset only if
                # the timer expired before this instant (2.0.0 also reset it when both fell on one instant)
                if t > self.bfd_end[u] + EPS:
                    self.bfi[u] = 0
            elif t >= self.bfd_end[u] - EPS:                  # beamFailureDetectionTimer expired
                self.bfi[u] = 0
            if self.bfd_q[u] < self.qout_lr:                  # all BFD-RS worse than Qout_LR: one indication
                self.bfd_end[u] = t + b.bfd_timer * self.t_ind[c]
                self.bfi[u] += 1
                if self.bfi[u] >= b.bfi_max and not self.bfr[u]:
                    self._bfr_start(u, t, b)
        # random access for beam failure recovery: end of a preamble attempt
        for u in np.nonzero(hb & self.bfr & (t >= self.bfr_att_t - EPS))[0]:
            c = int(serv[u])
            b = cfg[self.layer_of[c]]
            beam = int(self.bfr_beam[u])
            p = self._beam_power(i, ch, np.array([u]), np.array([c]), np.array([beam]))[0]
            ilm = totc[u, self.car[c]] - self.rc[c] * ln[u, c] + self.noise_c[c]
            if p / ilm >= self.qout:                          # response received on the new beam
                self.sb[u] = beam
                self.bfd_q[u] = p / ilm
                self._bfr_stop(u, t, ok=True)
                continue
            self.bfr_n[u] += 1
            if self.bfr_n[u] >= b.preamble_max:               # random-access problem -> radio-link failure
                self._bfr_stop(u, t, ok=False)
                if self.trace_log is not None:
                    self.trace_event(t, u, "bfr_ra_problem", c, c)
                self.fail(u, t, "rlf")
                continue
            self._bfr_attempt(u, t, b, c)

    def _bfr_start(self, u, t, b):
        self.bfr[u] = True
        self.bfr_t0[u] = t
        self.bfr_n[u] = 0
        self.bfr_end[u] = t + b.bfr_timer_s if b.bfr_timer_s is not None else INF
        self.tci_on[u] = False
        self.C["bfr"] += int(t >= self.t0c)
        if self.trace_log is not None:
            self.trace_event(t, u, "beam_failure", self.serv[u], self.serv[u], float(self.sb[u]))
        self._bfr_attempt(u, t, b, int(self.serv[u]))

    def _bfr_attempt(self, u, t, b, c):
        """Random Access Resource selection (TS 38.321 5.1.2) and the next preamble attempt."""
        bf = self.bf[u, c, :self.ext.n_beams[c]]
        cand = bf >= b.rsrp_thresh_ssb_dbm
        cfra = cand.any() and (b.bfr_timer_s is None or t < self.bfr_end[u] - EPS)
        if cfra:
            self.bfr_beam[u] = int(np.argmax(np.where(cand, bf, -INF)))
            self.bfr_att_t[u] = t + b.ra_attempt_s
        else:                                                 # contention-based: two round trips
            self.bfr_beam[u] = int(np.argmax(bf))
            self.bfr_att_t[u] = t + 2.0 * b.ra_attempt_s

    def _bfr_stop(self, u, t, ok, counted_fail=True):
        counted = t >= self.t0c
        if ok:
            self.C["bfr_ok"] += int(counted)
            self.bfi[u] = 0
            if self.trace_log is not None:
                self.trace_event(t, u, "beam_recovered", self.serv[u], self.serv[u], float(self.sb[u]))
        elif counted_fail:
            self.C["bfr_fail"] += int(counted)
        if counted:
            self.acc["bfr_time"] += t - max(self.bfr_t0[u], self.t0c)
        self.bfr[u] = False
        self.bfr_end[u] = -INF
        self.bfr_att_t[u] = INF

    # ------------------------------------------------------------------ measurement instants
    def _measure(self, ch, j, k, t, ln, tot):
        if self.beams:
            self.bf += self.a_bf[None, :, None] * (ch.bl1[j] - self.bf)
            self._beam_report(t)
        counted = self._measure_rule(ch, j, k, t, ln)
        self._load_ext(ln, tot, counted)
        self.nmeas += 1

    def _beam_report(self, t):
        """Periodic L1-RSRP beam reports: TCI switch decision and the RLM-RS set."""
        if t < self.rep_next - EPS:
            return
        self.rep_next = t + min(b.report_s for b in self.bcfg if b is not None)
        serv = self.serv
        users = np.nonzero((self.state == CONNECTED) & self.has_b[serv] & ~self.bfr)[0]
        for u in users:
            c = int(serv[u])
            nb = self.ext.n_beams[c]
            v = self.bf[u, c, :nb]
            best = int(np.argmax(v))
            b = self.bcfg[self.layer_of[c]]
            if best != self.sb[u] and v[best] > v[self.sb[u]] + b.switch_db and not self.tci_on[u]:
                self.tci_on[u] = True
                self.tci_b[u] = best
                self.tci_t[u] = t + b.tci_delay_s
            if b.rlm_rs == "beams":
                n = min(self.n_rlm[c], nb)
                self.rlm_set[u, :n] = np.argsort(-v)[:n]
                self.rlm_have[u] = True

    def _measure_rule(self, ch, j, k, t, ln) -> bool:
        if not self.mp38:
            return super()._measure_rule(ch, j, k, t, ln)
        # TS 38.133 measurement periods: average over the period, deliver once per period
        from ..rules.base import Observation
        from . import invariants as inv
        sample = ch.l1[j]
        self.macc += np.exp(sample * LN10_10)
        self.mcnt += 1
        inter = self.car[None, :] != self.car[self.serv][:, None]
        period = np.where(inter, self.p_inter[None, :], self.p_intra[None, :])
        due = self.mcnt >= period
        meas = self.l3.value
        if due.any():
            m = 10.0 * np.log10(self.macc[due] / self.mcnt[due])
            a = np.where(inter, self.a_inter[None, :], self.a_intra[None, :])[due]
            meas[due] += a * (m - meas[due])
            self.macc[due] = 0.0
            self.mcnt[due] = 0
        counted = t >= self.t0c
        if self.nmeas % self.lab_every == 0:
            self._sample_windows(t, ln, meas)
        serv = self.serv
        con = self.state == CONNECTED
        gap = meas - meas[self.ar, serv][:, None]
        if self.debug:
            ro = inv.readonly_copy
            obs = Observation(t, k, ro(meas), ro(gap), ro(serv), ro(con), ro(self.X[k]), ro(self.Y[k]), ro(self.V),
                              ro(self.TH[k]), ro(sample))
        else:
            obs = Observation(t, k, meas, gap, serv, con, self.X[k], self.Y[k], self.V, self.TH[k], sample)
        self.proc.measure(obs, counted)
        return counted

    def _sample_windows(self, t, ln, meas):
        if self.uniform:
            return super()._sample_windows(t, ln, meas)
        P, state, serv = self.P, self.state, self.serv
        ia = np.nonzero(self.w_on & (state == CONNECTED))[0]
        if not len(ia):
            return
        ldt = self.lab_every * self.mdt
        r = np.arange(len(ia))
        lr = ln[ia]
        if self.beams:                                        # best beam of every cell, no L1 error
            ch, i = self._ch, self._i
            g = ch.bg[i // ch.mp, ia].max(-1)
            lb = np.exp((ch.site_db[i][ia][:, self.ext.cell_site] + self.ext.p0 + g) * LN10_10)
        else:
            lb = lr
        tg, sr = serv[ia], self.w_src[ia]
        intf = (lr * self.lab_chi_c) @ self.mask                    # (n, carriers)
        it = intf[r, self.car[tg]] - self.lab_chi_c[tg] * lr[r, tg] + self.noise_c[tg]
        is_ = intf[r, self.car[sr]] - self.lab_chi_c[sr] * lr[r, sr] + self.noise_c[sr]
        s_t = lb[r, tg] / it
        s_s = lb[r, sr] / is_
        self.w_g[ia] += 10.0 * np.log10(s_t / s_s)
        self.w_n[ia] += 1
        self.w_cf[ia] = np.where(s_s < self.qout, self.w_cf[ia] + ldt, 0.0)
        self.w_cff[ia] |= self.w_cf[ia] >= P.t310_s - EPS
        if self.learns:
            mm = meas[ia]
            ml = np.exp((mm + self.re_off) * LN10_10)          # back to power over the bandwidth
            mi = (ml * self.lab_chi_c) @ self.mask
            est = ml[r, sr] / (mi[r, self.car[sr]] - self.lab_chi_c[sr] * ml[r, sr] + self.noise_c[sr])
            self.w_mcf[ia] = np.where(est < self.qout, self.w_mcf[ia] + ldt, 0.0)
            self.w_mcff[ia] |= self.w_mcf[ia] >= P.t310_s - EPS
            self.w_m[ia] += mm[r, serv[ia]] - mm[r, self.w_src[ia]]
        for u in ia[t - self.w_t0[ia] >= self.tmin[ia] - EPS]:
            self._finalize(u, t, "win")

    def _load_ext(self, ln, totc, counted) -> None:
        if self.uniform and not self.gaps:
            return super()._load(ln, totc[:, 0], counted)
        ar, acc, state = self.ar, self.acc, self.state
        serv = self.serv
        con = state == CONNECTED
        if self.proc.dual:
            con = con | ((state == EXECUTING) & self.daps_u)
        ls_ref = ln[ar, serv]
        ls = self._desired(self._i, self._ch, ln, serv)
        sinr = ls / (totc[ar, self.car[serv]] - self.rc[serv] * ls_ref + self.noise_c[serv])
        ok = con & (sinr >= self.qout)
        se = np.minimum(np.log2(1.0 + sinr), self.se_max)
        W = self.W_c[serv]
        rate = self.rate
        if self.world.scenario.traffic.model == "full_buffer":
            rate = W * self.se_max
        if self.backlog is not None:
            self.backlog += self.offered[min(self.nmeas, len(self.offered) - 1)]
            rate = np.minimum(W * self.se_max, self.backlog / self.mdt)
        need = np.where(ok, rate / (W * np.maximum(se, 1e-3)), 0.0)
        G = np.bincount(serv, weights=need * self.gbr, minlength=self.M)
        Bn = np.bincount(serv, weights=need * ~self.gbr, minlength=self.M)
        free = np.maximum(1.0 - self.bg, 0.0)
        gs = np.minimum(1.0, free / np.maximum(G, 1e-12))
        rem = np.maximum(free - G * gs, 0.0)
        bs = np.minimum(1.0, rem / np.maximum(Bn, 1e-12))
        thr = np.where(ok, rate * np.where(self.gbr, gs[serv], bs[serv]), 0.0)
        thr = thr * (1.0 - self.gap_share)                    # no data during the measurement gaps
        if self.backlog is not None:
            self.backlog = np.maximum(self.backlog - thr * self.mdt, 0.0)
        rho_new = np.minimum(1.0, self.bg + G * gs + Bn * bs)
        self.rho += self.a_rho * (rho_new - self.rho)
        np.multiply(self.chi_c, self.rho, out=self.rc)
        if self.lm:
            self._update_lm(con)
        if counted:
            acc["steps"] += self.mp
            acc["out_steps"] += self.mp * int(np.count_nonzero(con & (sinr < self.qout)))
            acc["thr"] += float(thr.sum()); acc["dem"] += float(np.sum(rate))
            acc["sinr"] += float(10.0 * np.log10(sinr[con]).sum()); acc["se"] += float(se[con].sum())
            acc["ncon"] += int(con.sum()); acc["load"] += float(rho_new.mean()); acc["nmeas"] += 1
            if "load_ptx" in acc:
                acc["load_ptx"] += float((rho_new * self.ptx_c).mean())
            acc["prep_time"] += self.proc.prepared_total() * self.mdt
            acc["gap_time"] += self.gap_share * self.mdt * int(con.sum())

    # ------------------------------------------------------------------ results
    def finish(self):
        T = self.S * self.dt
        if self.beams:
            for u in np.nonzero(self.bfr)[0]:
                self._bfr_stop(u, T, ok=False, counted_fail=False)
        return super().finish()
