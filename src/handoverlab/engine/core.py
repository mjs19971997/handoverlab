# SPDX-License-Identifier: MIT
"""Protocol engine: time loop, radio-link monitoring, attempts and outcome labels.

One :class:`Engine` simulates one handover rule on given radio samples.  All
users advance together on the step grid (10 ms by default); cell load and
interference are coupled through the users' serving cells.  The engine draws
no random numbers, so two rules run on the same samples differ only through
their decisions.

Per step
    1. end of an execution (join the target if its SINR is at least Qout,
       otherwise an execution failure) or of a re-establishment;
    2. radio-link monitoring: serving SINR smoothed over the Qout / Qin
       windows; N310 out-of-sync indications start T310, N311 in-sync
       indications stop it; expiry is a radio-link failure followed by
       re-establishment in the strongest cell;
    3. procedure events (a handover command or a conditional configuration
       reaches the UE);
    4. at measurement instants: L3 filter, outcome-label sampling, the
       handover procedure (see :mod:`handoverlab.engine.procedures`), load and
       delivered rate.

Outcome of a handover attempt (exactly one per attempt)
    too_late     command or configuration lost, or link failure while the
                 handover was in preparation
    too_early    execution failed, or link failure in the target before the
                 evaluation window closed, and the UE re-established in the
                 source or the target
    wrong_cell   the same, but the UE re-established in a third cell
    unnecessary  completed; the source would not have failed during the window,
                 and the stay was shorter than T_min of the service or the mean
                 SINR gain over the window was below theta_Q
    useful       completed and not unnecessary
    censored     the run ended before the outcome was known

A link failure with no handover in flight is not an attempt; it counts as a
failure ("rlf_without_handover" if the UE re-establishes in another cell,
"coverage_rlf" if in the same cell).  The SINR of the label uses the true
received powers with all cells transmitting (``label_load``), so the label
does not depend on what a rule does to the load.
"""
from __future__ import annotations

import time
from typing import Dict, List, Optional

import numpy as np

from ..channel.l2s import capacity_esm, miesm_qpsk
from ..eventlog import EVENT_FIELDS, TRACE_FIELDS, event_level, fingerprint
from ..measurement import EPS, INF, L3Filter
from ..rules.base import EARLY, LATE, UNNECESSARY, USEFUL, FailureRecord, Observation, OutcomeRecord, RuleContext
from ..seeds import rule_stream
from . import invariants as inv
from .metrics import Counters, summarize
from .procedures import CONNECTED, EXECUTING, REESTABLISHING, make_procedure

LN10_10 = np.log(10.0) / 10.0


def rlm_indications(P, qo, qi, qout, qin, run, n_o, n_i, mon, t, rlm_t0):
    """Out-of-sync / in-sync indications of one indication instant as TS 38.331 and TS 38.133 specify (since 2.1.0).

    An out-of-sync indication is sent when the filtered quality is below Qout, an in-sync indication when it is
    above Qin (TS 38.133 8.1.6), at most every max(10 ms, T_SSB).  TS 38.331 clause 7.2: N310 counts the
    out-of-sync indications while T310 is stopped and is reset by an in-sync indication; N311 counts the in-sync
    indications while T310 runs and is reset by an out-of-sync indication; an instant with neither changes no
    counter (5.3.10.2, NOTE 2).  T310 starts when N310 is reached (5.3.10.1) and stops when N311 is reached
    (5.3.10.2).  ``mon`` are the users whose link is monitored, ``rlm_t0`` the end of the monitoring restart on a
    new cell.  Updates ``run``, ``n_o``, ``n_i`` in place (1-D or 2-D arrays) and returns the users whose T310
    starts.
    """
    live = t >= rlm_t0 - EPS
    oos = (qo < qout) & mon & live
    ins = (qi > qin) & mon
    n_o[...] = np.where(ins, 0, n_o + (oos & ~run))
    start = mon & ~run & (n_o >= P.n310)
    run |= start
    n_i[...] = np.where(oos, 0, n_i + (ins & run & ~start))
    stop = run & (n_i >= P.n311)
    run &= ~stop
    n_i[stop] = 0
    return start


def ctrl_rate(P, serv, con, M):
    """Control receptions per second of every user for the ns-3-like link monitoring (``protocol.ns3_oos_rx``):
    ``ns3_ctrl_hz + ns3_ctrl_per_ue_hz * n``, with ``n`` the connected users served by the user's cell."""
    n = np.bincount(serv[con], minlength=M)
    return P.ns3_ctrl_hz + P.ns3_ctrl_per_ue_hz * n[serv]


def rlm_count(P, sl, qout, qin, run, c_o, c_i, n_o, n_i, mon, live, rx):
    """One step of the ns-3-like link monitoring (``protocol.ns3_oos_rx``; imitates ns-3 / 5G-LENA v5.1, NOT 3GPP).

    As ``NrUePhy::RlfDetection`` and ``NrUeRrc`` of 5G-LENA v5.1 implement it: while T310 is stopped, ``c_o``
    counts the control receptions (``rx`` in this step, from :func:`ctrl_rate`) with the link-monitoring SINR
    ``sl`` below Qout; a reception at or above Qout restarts the count and resets the indication counter
    ``n_o``; ``ns3_oos_rx`` receptions give an out-of-sync indication, ``n310`` consecutive indications start
    T310.  While T310 runs, ``c_i`` counts receptions above Qin in the same way (``ns3_ins_rx``, ``n311``), and
    in-sync stops T310.  The counts restart on a new cell (``Engine._attach``) and, with
    ``protocol.rlm_holdoff_s``, count only from ``rlm_t0`` on (``live``).  Works on 1-D and 2-D arrays, in
    place; returns the users whose T310 starts.
    """
    cnt = mon & ~run
    bad = cnt & live & (sl < qout)
    c_o[...] = np.where(bad, c_o + rx, np.where(cnt, 0.0, c_o))
    n_o[...] = np.where(cnt & ~bad, 0, n_o)
    ind = bad & (c_o >= P.ns3_oos_rx - EPS)
    n_o[...] = n_o + ind
    c_o[ind] = 0.0
    start = ind & (n_o >= P.n310)
    n_o[start] = 0
    c_i[start] = 0.0
    n_i[start] = 0
    rmon = run & mon
    good = rmon & (sl > qin)
    c_i[...] = np.where(good, c_i + rx, np.where(rmon, 0.0, c_i))
    n_i[...] = np.where(rmon & ~good, 0, n_i)
    ind_i = good & (c_i >= P.ns3_ins_rx - EPS)
    n_i[...] = n_i + ind_i
    c_i[ind_i] = 0.0
    stop = ind_i & (n_i >= P.n311)
    n_i[stop] = 0
    run[...] = (run & ~stop) | start
    return start


def rlm_kernel(engine):
    """The compiled step kernel if ``run.backend`` is ``"numba"`` and it covers the engine's monitoring, else None.

    It covers N310 = N311 = 1 without the monitoring load option (``protocol.lm_load``); other settings and
    debug mode use the NumPy path.
    """
    sc = engine.world.scenario
    P = sc.protocol
    if (getattr(sc.run, "backend", "numpy") != "numba" or engine.lm or P.n310 != 1 or P.n311 != 1
            or engine.cnt):
        return None
    if engine.std and engine.daps_mon:
        return None                     # the source link of DAPS during T304: the NumPy path
    from ._kernels import rlm_step
    return rlm_step


class Engine:
    """Simulation of one rule.  Feed the radio chunks in order, then call :meth:`finish`.

    ``log_events`` is the event-log level (see :mod:`handoverlab.eventlog`):
    ``"off"`` (or False), ``"summary"`` (or True) keeps the event log for
    :attr:`events`, ``"full"`` also keeps the procedure trace for
    :attr:`trace`; the fingerprint is always available.  ``debug`` turns on
    the invariant checks of :mod:`handoverlab.engine.invariants` (default:
    the environment variable ``HANDOVERLAB_DEBUG``).  Neither changes a
    result.
    """

    def __init__(self, world, rule, log_events=False, debug: Optional[bool] = None):
        sc = world.scenario
        P, R, T = sc.protocol, sc.radio, sc.traffic
        self.world, self.rule, self.P = world, rule, P
        self.X, self.Y, self.V, self.TH = world.x, world.y, world.speed, world.heading
        self.S, self.U = self.X.shape
        self.M = world.n_cells
        self.dt = P.step_s
        self.mp = max(1, int(round(P.l1_period_s / P.step_s)))      # steps per measurement
        self.mdt = self.mp * P.step_s
        self.rep = max(1, int(round(P.report_interval_s / self.mdt)))
        self.lab_every = max(1, int(round(P.label_period_s / self.mdt)))
        self.learns = bool(rule.learns)
        # X of TS 38.331 5.5.3.2 depends on the frequency range (TS 38.133 9.2.5.2: 200 ms in FR1 at an SMTC of
        # 20 ms, 480 ms in FR2-1); 200 ms on every carrier up to 2.0.0
        from ..requirements import l3_reference_period
        self.std = P.rrc_detail == "3gpp"
        x_ref = l3_reference_period(R.carrier_ghz, P.ssb_period_s, P.fr2_power_class) if self.std else 0.2
        self.l3 = L3Filter(P.l3_k, self.mdt, x_ref)
        # out-of-sync / in-sync indications every max(10 ms, T_SSB) (TS 38.133 8.1.6) and the source link of DAPS
        # monitored while T304 runs (TS 38.331 5.3.10.1); both since 2.1.0
        self.ind_steps = max(1, int(round(max(0.01, P.ssb_period_s) / P.step_s))) if self.std else 1
        self.daps_mon = False
        self.ao = 1.0 - np.exp(-P.step_s / P.qout_window_s)
        self.ai = 1.0 - np.exp(-P.step_s / P.qin_window_s)
        self.qout = 10 ** (P.qout_db / 10.0)
        self.qin = 10 ** (P.qin_db / 10.0)
        self.noise = 10 ** (R.noise_dbm / 10.0)
        self.chi = R.isolation
        self.lab_chi = R.isolation * T.label_load
        self.W = R.bandwidth_mhz * 1e6
        self.se_max = T.se_max
        self.bg = np.asarray(world.bg_load, dtype=float)
        self.rho = self.bg.copy()
        self.rc = self.chi * self.rho                                 # interference weight of every cell
        # own interferer load at link monitoring (protocol.lm_load*); otherwise it sees rc
        self.lm = P.lm_load is not None or P.lm_load_per_ue > 0.0
        self.lm0 = 0.0 if P.lm_load is None else float(P.lm_load)
        self.rc_lm = self.rc.copy()
        self.lm_ln = None                                             # radio sample of the current step
        self.fad_now, self.n_rlm = None, 0                            # fast fading of the step (2.2.0)
        self.sched = None                                             # slot scheduler (2.2.0)
        if P.scheduler is not None:
            from .scheduler import SlotScheduler
            self.sched = SlotScheduler(world, self.M, self.U, P.scheduler, self.mdt, P.harq_max_tx,
                                       P.harq_rtt_slots, P.l2s_loss_db)
        self.buf = None                                               # user-plane buffers (2.3.0)
        if P.buffers is not None:
            from .buffers import Buffers
            sdu = P.sdu_bytes or (T.packet_bytes if T.model == "periodic" else 1500)
            self.buf = Buffers(self.U, self.mdt, P.buffers, P.forwarding, P.early_forwarding, P.xn_delay_s,
                               P.discard_timer_s, 8.0 * sdu, sc.run.warmup_s)
        self.t_load = 0.0                                             # time of the current measurement instant
        self.a_rho = 1.0 - np.exp(-self.mdt / T.load_tau_s)
        svc = world.services
        self.tmin, self.thq, self.rate, self.gbr = svc.t_min, svc.theta_q, svc.rate, svc.gbr
        # traffic model: buffered users ask for at most the peak rate of the carrier
        self.r_peak = self.W * self.se_max
        if T.model == "full_buffer":
            self.rate = np.full(self.U, self.r_peak)
        self.offered = world.offered
        self.backlog = np.zeros(self.U) if world.offered is not None and self.buf is None else None
        self.t0c = sc.run.warmup_s
        self.level = event_level(log_events)
        self.keep_events = self.level != "off"
        self.log: List[tuple] = []
        self.trace_log: Optional[List[tuple]] = [] if self.level == "full" else None
        self.debug = inv.debug_from_env() if debug is None else bool(debug)
        if self.sched is not None and not self.debug and getattr(sc.run, "backend", "numpy") == "numba":
            from ._kernels import sched_slots                             # compiled slot loop (2.4.0), same values
            self.sched.use_kernel(sched_slots)
        self.last_t_end = -INF
        U = self.U
        self.ar = np.arange(U)
        # connection state
        self.state = np.zeros(U, dtype=np.int8)
        self.t_done = np.zeros(U)
        self.re_cell = np.zeros(U, dtype=int)
        self.serv = np.zeros(U, dtype=np.intp)
        self.started = False
        self.prev = np.full(U, -1)
        self.last_ho = np.full(U, -1e9)
        # radio-link monitoring
        self.qo = np.zeros(U); self.qi = np.zeros(U)
        self.n_o = np.zeros(U, dtype=int); self.n_i = np.zeros(U, dtype=int)
        self.run = np.zeros(U, dtype=bool); self.t310 = np.zeros(U); self.k310 = np.zeros(U, dtype=int)
        self.rlm_t0 = np.full(U, -INF)                  # no out-of-sync before (protocol.rlm_holdoff_s)
        # ns-3-like link monitoring (protocol.ns3_oos_rx): receptions counted below Qout / above Qin
        self.cnt = P.ns3_oos_rx is not None
        self.c_o = np.zeros(U); self.c_i = np.zeros(U)
        # attempt in flight (reported / prepared / executing)
        self.f_on = np.zeros(U, dtype=bool); self.f_t = np.zeros(U); self.f_tx = np.full(U, np.nan)
        self.f_src = np.zeros(U, dtype=int); self.f_tgt = np.zeros(U, dtype=int); self.f_key = np.full(U, -1)
        self.f_np = np.zeros(U, dtype=int); self.f_oe = np.full(U, np.nan); self.f_cnt = np.zeros(U, dtype=bool)
        # evaluation window of the last completed handover
        self.w_on = np.zeros(U, dtype=bool); self.w_t0 = np.zeros(U); self.w_ta = np.zeros(U)
        self.w_tx = np.zeros(U)
        self.w_src = np.zeros(U, dtype=int); self.w_tgt = np.zeros(U, dtype=int); self.w_key = np.full(U, -1)
        self.w_np = np.zeros(U, dtype=int); self.w_oe = np.full(U, np.nan); self.w_cnt = np.zeros(U, dtype=bool)
        self.w_n = np.zeros(U); self.w_g = np.zeros(U); self.w_m = np.zeros(U)
        self.w_cf = np.zeros(U); self.w_cff = np.zeros(U, dtype=bool)
        self.w_mcf = np.zeros(U); self.w_mcff = np.zeros(U, dtype=bool); self.w_pp = np.zeros(U, dtype=bool)
        self.C = Counters()
        self.acc = dict(thr=0.0, dem=0.0, sinr=0.0, se=0.0, ncon=0, int_exec=0.0, int_fail=0.0, out_steps=0,
                        prep_time=0.0, load=0.0, nmeas=0, steps=0)
        self.wall = 0.0
        self.nmeas = 0
        self.proc = make_procedure(self, rule)
        self.daps_mon = self.std and bool(self.proc.dual) and P.t304_s is not None
        self.src_rlf = np.zeros(U, dtype=bool)                # DAPS: radio link failure of the source (5.3.10.3)
        self.rec_t0 = np.full(U, INF)                         # start of a recovery into a prepared cell (2.1.0)
        self.C["rrc_on"] = int(self.std)                      # RRC messages counted one by one (2.1.0)
        # DAPS per execution: TS 38.300 V18.11.0 9.2.3.1 does not support DAPS from FR2 to FR2 (such a handover
        # is a baseline one, since 2.1.0) and 16.14.3.2.1 not for NTN
        from ..requirements import is_fr2
        self.cell_fr2 = np.full(self.M, is_fr2(R.carrier_ghz))
        self.daps_u = np.full(U, bool(self.proc.dual))
        if self.std and self.proc.dual and world.ntn is not None:
            raise ValueError("DAPS handover is not supported for NTN (TS 38.300 V18.11.0 clause 16.14.3.2.1)")
        self.kind = self.proc.kind
        rule.reset(RuleContext(U, self.M, world.cell_sites, world.nominal_cell, P.step_s,
                               self.mdt, world.seed, rule_stream(world.seed), sc,
                               None if world.ext is None else world.ext.cell_carrier, world.cell_center))

    @property
    def meas(self) -> np.ndarray:
        """L3-filtered RSRP (U, M) [dBm]."""
        return self.l3.value

    # ------------------------------------------------------------------ attempts and outcomes
    def _event(self, t_att, t_x, t_end, u, kind, src, tgt, outcome, cause, dwell, gain, npr, oe, counted):
        self.C["closed_all"] += 1
        if not counted:
            return
        self.C["n_" + outcome] += 1
        k = min(int(round(t_end / self.dt)), self.S - 1)
        self._log((round(t_att, 4), round(t_x, 4) if t_x == t_x else -1.0, round(t_end, 4), int(u),
                   kind, int(src), int(tgt), outcome, cause, round(float(dwell), 4),
                   round(float(gain), 3), int(npr),
                   round(float(oe), 3) if oe == oe and abs(oe) != INF else -99.0,
                   round(float(self.X[k, u]), 1), round(float(self.Y[k, u]), 1)))

    def _log(self, row):
        if self.debug:
            inv.check_event(self, row)
        self.log.append(row)

    def trace_event(self, t, u, event, src, cell, value=np.nan, note=""):
        """Add a row to the procedure trace (only at event-log level ``full``)."""
        self.trace_log.append((round(float(t), 4), int(u), event, int(src), int(cell),
                               round(float(value), 3) if value == value else float("nan"), note))

    def _feedback(self, u, src, tgt, key, label, t):
        if self.learns:
            self.rule.on_outcome(OutcomeRecord(int(u), int(src), int(tgt), int(key), label, float(t)))

    def new_flight(self, u, tgt, t, key=-1, npr=0, oe=np.nan):
        """A handover attempt of user ``u`` towards ``tgt`` starts at ``t``."""
        if self.debug:
            inv.check_new_attempt(self, u, tgt, t)
        self.f_on[u] = True
        self.f_t[u] = t
        self.f_tx[u] = np.nan
        self.f_src[u] = self.serv[u]
        self.f_tgt[u] = tgt
        self.f_key[u] = key
        self.f_np[u] = npr
        self.f_oe[u] = oe
        self.f_cnt[u] = t >= self.t0c
        self.C["att"] += int(self.f_cnt[u])
        self.C["att_all"] += 1

    def _close_flight(self, u, t, outcome, cause):
        self._event(self.f_t[u], self.f_tx[u], t, u, self.kind, self.f_src[u], self.f_tgt[u], outcome, cause,
                    0.0, 0.0, self.f_np[u], self.f_oe[u], self.f_cnt[u])
        self.f_on[u] = False
        self.proc.cancel_command(u)

    def _close_window(self, u, t, outcome, cause, dwell, gain):
        self._event(self.w_ta[u], self.w_tx[u], t, u, self.kind, self.w_src[u], self.w_tgt[u], outcome, cause,
                    dwell, gain, self.w_np[u], self.w_oe[u], self.w_cnt[u])
        self.w_on[u] = False

    def _finalize(self, u, t, reason):
        """Close the evaluation window of user ``u`` ("win": complete, "ho": left by a new handover, "end")."""
        dwell = t - self.w_t0[u]
        n = max(self.w_n[u], 1.0)
        gain = self.w_g[u] / n
        short = dwell < self.tmin[u] - EPS
        if reason == "end" and short:
            self._close_window(u, t, "censored", "", dwell, gain)
            return
        low = gain < self.thq[u]
        un = (not self.w_cff[u]) and (short or low)
        if self.w_cnt[u]:
            self.C["un_and"] += int((not self.w_cff[u]) and short and low)
            self.C["un_gain"] += int((not self.w_cff[u]) and low)
        if self.learns:
            un_obs = (not self.w_mcff[u]) and (short or self.w_m[u] / n < self.thq[u])
            self._feedback(u, self.w_src[u], self.w_tgt[u], self.w_key[u], UNNECESSARY if un_obs else USEFUL, t)
        self._close_window(u, t, "unnecessary" if un else "useful", "", dwell, gain)

    # ------------------------------------------------------------------ execution and failures
    def start_exec(self, u, tgt, t):
        """The UE leaves the source cell and synchronises to ``tgt``."""
        if self.w_on[u]:
            self._finalize(u, t, "ho")
        if not self.f_on[u]:
            self.new_flight(u, tgt, t, *self.proc.flight_info(u, tgt))
        self.f_tx[u] = t
        if self.trace_log is not None:
            self.trace_event(t, u, "exec", self.serv[u], tgt)
        if self.proc.dual:
            self.daps_u[u] = not (self.std and self.cell_fr2[self.serv[u]] and self.cell_fr2[tgt])
        d = self.proc.exec_time(u)
        self.state[u] = EXECUTING
        self.t_done[u] = t + d
        if self.std:                     # TS 38.331 7.2: N310 / N311 reset upon a reconfiguration with sync
            self.n_o[u] = self.n_i[u] = 0
        if not (self.daps_mon and self.daps_u[u]):      # 5.3.5.5.2: T310 stops unless DAPS is configured
            self.run[u] = False
        self.src_rlf[u] = False
        self.proc.cancel_command(u)
        if self.buf is not None:
            dual = bool(self.proc.dual and self.daps_u[u])
            kind = "daps" if dual else "cond" if self.kind in ("cho", "ltm", "cltm") else "ho"
            self.buf.leave(u, t, tgt, kind, 0.0 if dual else self._flush(u))
        if t >= self.t0c:
            self.C["exec"] += 1
            self.acc["int_exec"] += min(self.proc.exec_interruption(u, d), self.S * self.dt - t)

    def _attach(self, u, cell, s, t=None):
        if self.trace_log is not None:
            self.trace_event(t, u, "attach" if self.state[u] == EXECUTING else "reestablish", self.serv[u], cell,
                             10.0 * np.log10(max(float(s), 1e-30)))
        self.serv[u] = cell
        self.state[u] = CONNECTED
        self.src_rlf[u] = False
        if self.lm and self.lm_ln is not None:
            s = self._sinr_lm(u, cell, self.lm_ln)
        self.qo[u] = self.qi[u] = s
        self.n_o[u] = self.n_i[u] = 0
        self.c_o[u] = self.c_i[u] = 0.0
        if self.P.rlm_holdoff_s > 0 and t is not None:
            self.rlm_t0[u] = t + self.P.rlm_holdoff_s
        self.run[u] = False
        self.proc.on_attach(u)

    def _end_exec(self, u, t, ln, tot):
        tgt = int(self.f_tgt[u])
        lt = ln[u, tgt]
        s = lt / (tot[u] - self.rc[tgt] * lt + self.noise)
        if s < self.qout and self.P.exec_can_fail:
            t304 = self.P.t304_s
            if t304 is not None and t - self.f_tx[u] < t304 - EPS:
                # random access goes on while T304 runs (TS 38.331 5.3.5.3, 5.3.10.3): try again next step
                self.t_done[u] = t + self.dt
                if t >= self.t0c and (not self.daps_u[u] or self.src_rlf[u]):   # DAPS: the source carries data
                    self.acc["int_exec"] += self.dt
                return
            if not (self.proc.fallback and self.daps_u[u] and self._fallback(u, t, ln, tot)):
                self.fail(u, t, "exec")
            return
        src = int(self.serv[u])
        pp = (self.prev[u] == tgt) and (t - self.last_ho[u] < self.P.pingpong_s)
        cnt = bool(self.f_cnt[u])
        if cnt:
            self.C["ho"] += 1
            self.msg(t)                                        # RRCReconfigurationComplete to the target
            self.C["pp"] += int(pp)
        self.proc.after_execution(u, tgt, t)
        self.prev[u] = src
        self.last_ho[u] = t
        if self.buf is not None:
            if self.proc.dual and self.daps_u[u]:
                self._flush(u)               # source released: the target has the forwarded copies
            self.buf.join(u, t, tgt)
        self._attach(u, tgt, s, t)
        # open the evaluation window
        self.w_on[u] = True; self.w_t0[u] = t; self.w_ta[u] = self.f_t[u]; self.w_tx[u] = self.f_tx[u]
        self.w_src[u] = src; self.w_tgt[u] = tgt; self.w_key[u] = self.f_key[u]
        self.w_np[u] = self.f_np[u]; self.w_oe[u] = self.f_oe[u]; self.w_cnt[u] = cnt
        self.w_n[u] = 0; self.w_g[u] = 0; self.w_m[u] = 0; self.w_cf[u] = 0; self.w_cff[u] = False
        self.w_mcf[u] = 0; self.w_mcff[u] = False; self.w_pp[u] = pp
        self.f_on[u] = False

    def _eff_sinr(self, ln, g, rc, pts, esm) -> np.ndarray:
        """Effective SINR of every user's serving link with fast fading (since 2.2.0): the SINR at the frequencies
        ``pts`` of the relative gains ``g`` (U, M, F), every link with its own fading, mapped to one value by
        ``esm`` (:func:`~handoverlab.channel.l2s.miesm_qpsk` or :func:`~handoverlab.channel.l2s.capacity_esm`)."""
        ar, serv = self.ar, self.serv
        gp = g[:, :, pts]
        ls = ln[ar, serv][:, None] * gp[ar, serv]
        tot = np.einsum("um,umf,m->uf", ln, gp, rc)
        return esm(ls / (tot - rc[serv][:, None] * ls + self.noise))

    def _sinr_lm(self, u, cell, ln) -> float:
        """SINR of user ``u`` on ``cell`` as link monitoring sees it (interferer weights ``rc_lm``)."""
        lc = ln[u, cell]
        return lc / (ln[u] @ self.rc_lm - self.rc_lm[cell] * lc + self.noise)

    def _update_lm(self, con) -> None:
        """Interferer load at link monitoring: lm_load plus lm_load_per_ue per served user, at most 1."""
        n = np.bincount(self.serv[con], minlength=self.M)
        np.multiply(self.chi, np.minimum(1.0, self.lm0 + self.P.lm_load_per_ue * n), out=self.rc_lm)

    def _recovery_joins(self, u, s, t) -> bool:
        """End of a re-establishment or of a recovery into a prepared cell.  TS 38.331 5.3.7.3 (since 2.1.0): the
        recovery (attemptCondReconfig, attemptLTM-Switch) is a reconfiguration with sync: the UE joins once the
        target SINR reaches Qout while T304 runs; when T304 expires (5.3.5.8.3) it re-establishes in the best cell
        (``protocol.reest_s``).  A re-establishment (and every recovery up to 2.0.0) always joins."""
        if not np.isfinite(self.rec_t0[u]) or s >= self.qout or not self.P.exec_can_fail:
            self.rec_t0[u] = INF
            return True
        t304 = self.P.t304_s
        if t304 is not None and t - self.rec_t0[u] < t304 - EPS:
            self.t_done[u] = t + self.dt                      # random access goes on while T304 runs
            if t >= self.t0c:
                self.acc["int_fail"] += self.dt
            return False
        self.rec_t0[u] = INF                                  # T304 expired: re-establishment
        self.re_cell[u] = int(np.argmax(self.meas[u]))
        if self.buf is not None:
            self.buf.rec[u] = False
        self.t_done[u] = t + self.P.reest_s
        if t >= self.t0c:
            self.acc["int_fail"] += min(self.P.reest_s, self.S * self.dt - t)
        if self.trace_log is not None:
            self.trace_event(t, u, "recovery_failed", self.serv[u], self.re_cell[u])
        return False

    def _flush(self, u) -> float:
        """MAC reset of user ``u`` with the slot scheduler: its HARQ data [bit] (0 without the scheduler)."""
        return self.sched.flush(u) if self.sched is not None else 0.0

    def msg(self, t, n=1) -> None:
        """Count ``n`` RRC messages sent at ``t`` (since 2.1.0): MeasurementReport, RRCReconfiguration (one per
        user and instant, whatever the number of conditional candidates it carries) and its
        RRCReconfigurationComplete; an LTM cell switch command is a MAC CE (TS 38.300 9.2.3.5.2), not counted."""
        if t >= self.t0c:
            self.C["rrc"] += int(n)

    def _source_rlf(self, u, t) -> None:
        """DAPS: T310 of the source expired while T304 runs: source RLF, the source connection is released and
        carries no more data (TS 38.331 5.3.10.3; since 2.1.0)."""
        self.src_rlf[u] = True
        self.run[u] = False
        if self.trace_log is not None:
            self.trace_event(t, u, "source_rlf", self.serv[u], self.f_tgt[u])
        if t >= self.t0c:
            self.acc["int_exec"] += max(0.0, min(float(self.t_done[u]), self.S * self.dt) - t)

    def _fallback(self, u, t, ln, tot) -> bool:
        """DAPS: the target could not be joined.  TS 38.331 5.3.5.8.3 (since 2.1.0): back to the source unless a
        radio link failure of the source was detected while T304 ran; 2.0.0: if the source SINR is at least Qout."""
        src = int(self.serv[u])
        ls = ln[u, src]
        s = ls / (tot[u] - self.rc[src] * ls + self.noise)
        if (self.src_rlf[u] if self.daps_mon else s < self.qout):
            return False
        self._feedback(u, src, self.f_tgt[u], self.f_key[u], EARLY, t)
        if self.trace_log is not None:
            self.trace_event(t, u, "fallback", src, self.f_tgt[u], 10.0 * np.log10(max(float(s), 1e-30)))
        self._close_flight(u, t, "too_early", "daps_fallback")
        if self.buf is not None:
            self.buf.fallback(u)
        self.state[u] = CONNECTED
        self.proc.on_attach(u)
        return True

    def fail(self, u, t, kind):
        """Mobility failure of user ``u``: "rlf" (T310 expired), "cmd" (command lost) or "exec"."""
        c = int(np.argmax(self.meas[u]))                  # cell selected for re-establishment
        s = int(self.serv[u])
        if kind == "rlf" and not self.f_on[u]:
            self.proc.before_link_failure(u, t)
        # MRO classes of TS 38.300 V18.11.0 15.5.2.2.2 (since 2.1.0): too early = re-establishment in the source,
        # wrong cell = in a cell other than source and target, too late = in a different cell; a re-establishment
        # in the serving cell (the target after a handover) is in none of the three classes: "coverage".  One
        # failure gets one class: an RLF shortly after a handover is classified by that handover.  2.0.0:
        # re-establishment in the target was too early, a lost command too late in any cell, and both labels when
        # two attempts met.
        std = self.std
        if kind == "exec":
            src, tgt = int(self.f_src[u]), int(self.f_tgt[u])
            cause = "execution_failure"
            if std:
                out = "too_early" if c == src else "coverage" if c == tgt else "wrong_cell"
            else:
                out = "too_early" if c in (src, tgt) else "wrong_cell"
            if out != "coverage":
                self._feedback(u, src, tgt, self.f_key[u], EARLY, t)
            self._close_flight(u, t, out, cause)
        elif kind == "cmd":
            cause = "command_lost"
            out = "too_late" if (c != s or not std) else "coverage"
            if out == "too_late":
                self._feedback(u, self.f_src[u], self.f_tgt[u], self.f_key[u], LATE, t)
                self.C["late_f"] += int(t >= self.t0c)
            self._close_flight(u, t, out, cause)
        elif self.w_on[u]:
            cause = "rlf_after_handover"
            if std:
                out = "too_early" if c == int(self.w_src[u]) else "coverage" if c == s else "wrong_cell"
            else:
                out = "too_early" if c in (int(self.w_src[u]), s) else "wrong_cell"
            if out != "coverage":
                self._feedback(u, self.w_src[u], self.w_tgt[u], self.w_key[u], EARLY, t)
            dwell = t - self.w_t0[u]
            self._close_window(u, t, out, cause, dwell, self.w_g[u] / max(self.w_n[u], 1.0))
            if self.f_on[u]:
                if std:                                 # the failure belongs to the handover just made
                    self._close_flight(u, t, "censored", "rlf_after_handover")
                else:                                   # 2.0.0 (its too_late_pm counted only the window)
                    self._feedback(u, self.f_src[u], self.f_tgt[u], self.f_key[u], LATE, t)
                    self._close_flight(u, t, "too_late", "rlf_in_preparation")
        elif self.f_on[u]:
            cause = "rlf_in_preparation"
            out = "too_late" if (c != s or not std) else "coverage"
            if out == "too_late":
                self._feedback(u, self.f_src[u], self.f_tgt[u], self.f_key[u], LATE, t)
                self.C["late_f"] += int(t >= self.t0c)
            self._close_flight(u, t, out, cause)
        else:
            cause = "rlf_without_handover" if c != s else "coverage_rlf"
            npr = self.proc.prepared_count(u)
            if c != s:
                self.C["late_f"] += int(t >= self.t0c)
                if self.learns:
                    k = int(self.k310[u])
                    self.rule.on_link_failure(FailureRecord(int(u), s, c, float(t), float(self.t310[u]),
                                                            float(self.X[k, u]), float(self.Y[k, u]),
                                                            float(self.TH[k, u])))
                if npr and t >= self.t0c:
                    self.C["rlf_prepared"] += 1
            if t >= self.t0c:
                k = min(int(round(t / self.dt)), self.S - 1)
                self._log((round(t, 4), -1.0, round(t, 4), int(u), "rlf", s, c,
                           "too_late" if c != s else "coverage", cause, 0.0, 0.0, npr, -99.0,
                           round(float(self.X[k, u]), 1), round(float(self.Y[k, u]), 1)))
        if self.trace_log is not None:
            self.trace_event(t, u, "failure", s, c, note=cause)
        if t >= self.t0c:
            self.C["fail"] += 1
            self.C["f_" + cause] += 1
        rec = self.proc.recovers_into(u, c)
        if rec and t >= self.t0c:
            self.C["rec"] += 1
        self.proc.clear(u, c if rec else -1, t)
        self.state[u] = REESTABLISHING
        t_out = self.P.cho_recovery_s if rec else self.P.reest_s
        self.rec_t0[u] = t if (rec and self.std) else INF
        self.t_done[u] = t + t_out
        if t >= self.t0c:
            self.acc["int_fail"] += min(t_out, self.S * self.dt - t)
        self.re_cell[u] = c
        self.run[u] = False
        if self.std:                     # a re-establishment is no handover: no ping-pong across it (2.1.0)
            self.prev[u] = -1
        if self.buf is not None:
            self.buf.fail(u, t, rec, self._flush(u))
        self.proc.on_failure(u)

    # ------------------------------------------------------------------ main loop
    def _init(self, ch):
        self.l3.reset(ch.l1[0])
        self.serv[:] = np.argmax(self.meas, axis=1)
        if self.buf is not None:
            self.buf.anchor[:] = self.serv
        self.started = True
        if self.lm:
            self._update_lm(self.state == CONNECTED)
        if self.trace_log is not None:
            t0 = ch.k0 * self.dt
            for u in range(self.U):
                self.trace_event(t0, u, "serve", -1, self.serv[u])
        ln = ch.lin[0]
        ls = ln[self.ar, self.serv]
        s = ls / (ln @ self.rc - self.rc[self.serv] * ls + self.noise)
        if self.lm:
            s = ls / (ln @ self.rc_lm - self.rc_lm[self.serv] * ls + self.noise)
        self.qo[:] = s
        self.qi[:] = s

    def advance(self, ch) -> None:
        """Simulate the steps of one radio chunk."""
        w0 = time.perf_counter()
        if not self.started:
            self._init(ch)
        P, dt, ar = self.P, self.dt, self.ar
        state, run = self.state, self.run
        noise, qout, qin, ao, ai = self.noise, self.qout, self.qin, self.ao, self.ai
        qo, qi = self.qo, self.qi
        simple = P.n310 == 1 and P.n311 == 1
        cnz = np.count_nonzero
        fad = getattr(ch, "fad", None)                     # fast fading (since 2.2.0): effective SINRs
        kern = None if (self.debug or fad is not None) else rlm_kernel(self)
        if kern is not None:                               # 2-D views for the kernel (one engine = one row)
            v = (state[None], qo[None], qi[None], run[None], self.t310[None], self.k310[None], self.rlm_t0[None])
            t310_lim = P.t310_s - EPS
        for i in range(ch.n):
            k = ch.k0 + i
            t = k * dt
            ln = ch.lin[i]
            tot = ln @ self.rc
            if self.lm:
                self.lm_ln = ln
            if fad is not None:
                self.fad_now, self.n_rlm = fad[i], ch.n_rlm
            # --- end of an execution or of a re-establishment
            if cnz(state):
                for u in np.nonzero((state != CONNECTED) & (t >= self.t_done - EPS))[0]:
                    if state[u] == EXECUTING:
                        self._end_exec(u, t, ln, tot)
                    else:
                        c = int(self.re_cell[u])
                        lc = ln[u, c]
                        s = lc / (tot[u] - self.rc[c] * lc + noise)
                        if self._recovery_joins(u, s, t):
                            if self.buf is not None:
                                self.buf.rejoin(u, t, c)
                            self._attach(u, c, s, t)
            serv = self.serv
            if kern is not None:                           # compiled kernel (run.backend: numba), same values
                sl = np.empty((1, self.U))
                ex = np.empty((1, self.U), dtype=bool)
                if kern(ln, tot[None], self.rc[serv][None], serv[None], v[0], v[1], v[2], v[3], v[4], v[5], v[6], sl,
                        ex, t, k, noise, ao, ai, qout, qin, t310_lim, P.rlm_holdoff_s, EPS, CONNECTED, self.std,
                        k % self.ind_steps == 0):
                    for u in np.nonzero(ex[0])[0]:
                        self.fail(u, t, "rlf")
                self.sl_now = sl[0]
                self.proc.step(t)
                if i % self.mp == 0:
                    self._measure(ch, i // self.mp, k, t, ln, tot)
                continue
            ls = ln[ar, serv]
            sinr = ls / (tot - self.rc[serv] * ls + noise)
            con = state == CONNECTED
            # --- radio-link monitoring
            if fad is not None:                            # hypothetical PDCCH band, MIESM (QPSK)
                sl = self._eff_sinr(ln, fad[i], self.rc_lm if self.lm else self.rc, slice(0, ch.n_rlm), miesm_qpsk)
            elif self.lm:
                rl = self.rc_lm
                sl = ls / (ln @ rl - rl[serv] * ls + noise)
            else:
                sl = sinr
            qo += ao * (sl - qo)
            qi += ai * (sl - qi)
            if self.cnt:                                   # ns-3-like link monitoring (not 3GPP)
                rx = ctrl_rate(P, serv, con, self.M) * dt
                start = rlm_count(P, sl, qout, qin, run, self.c_o, self.c_i, self.n_o, self.n_i, con,
                                  t >= self.rlm_t0 - EPS, rx)
                self.t310[start] = t
                self.k310[start] = k
                if cnz(run):
                    for u in np.nonzero(run & con & (t - self.t310 >= P.t310_s - EPS))[0]:
                        self.fail(u, t, "rlf")
            elif self.std:
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
            # --- handover command / conditional configuration reaches the UE
            self.sl_now = sl
            self.proc.step(t)
            if self.debug:
                inv.check_step(self, t, sinr)
            # --- measurement instant
            if i % self.mp == 0:
                self._measure(ch, i // self.mp, k, t, ln, tot)
        self.wall += time.perf_counter() - w0

    def _sample_windows(self, t, ln, meas):
        """Accumulate the outcome-label quantities of the open evaluation windows."""
        P, state, serv = self.P, self.state, self.serv
        ia = np.nonzero(self.w_on & (state == CONNECTED))[0]
        if not len(ia):
            return
        ldt = self.lab_every * self.mdt
        r = np.arange(len(ia))
        lr = ln[ia]
        lt = lr[r, serv[ia]]
        lsrc = lr[r, self.w_src[ia]]
        tsum = lr.sum(1)
        s_t = lt / (self.lab_chi * (tsum - lt) + self.noise)
        s_s = lsrc / (self.lab_chi * (tsum - lsrc) + self.noise)
        self.w_g[ia] += 10.0 * np.log10(s_t / s_s)
        self.w_n[ia] += 1
        self.w_cf[ia] = np.where(s_s < self.qout, self.w_cf[ia] + ldt, 0.0)
        self.w_cff[ia] |= self.w_cf[ia] >= P.t310_s - EPS
        if self.learns:                                  # what the network can observe of the same quantities
            mm = meas[ia]
            ml = np.exp(mm * LN10_10)
            msrc = ml[r, self.w_src[ia]]
            est = msrc / (self.lab_chi * (ml.sum(1) - msrc) + self.noise)
            self.w_mcf[ia] = np.where(est < self.qout, self.w_mcf[ia] + ldt, 0.0)
            self.w_mcff[ia] |= self.w_mcf[ia] >= P.t310_s - EPS
            self.w_m[ia] += mm[r, serv[ia]] - mm[r, self.w_src[ia]]
        for u in ia[t - self.w_t0[ia] >= self.tmin[ia] - EPS]:
            self._finalize(u, t, "win")

    def _measure(self, ch, j, k, t, ln, tot):
        counted = self._measure_rule(ch, j, k, t, ln)
        self.t_load = t
        self._load(ln, tot, counted)
        self.nmeas += 1

    def _measure_rule(self, ch, j, k, t, ln) -> bool:
        """Measurement instant, first part: L3 filter, outcome labels and the handover procedure."""
        ar, state = self.ar, self.state
        meas = self.l3.update(ch.l1[j])
        counted = t >= self.t0c
        if self.nmeas % self.lab_every == 0:
            self._sample_windows(t, ln, meas)
        # --- handover procedure
        serv = self.serv
        con = state == CONNECTED
        gap = meas - meas[ar, serv][:, None]
        if self.debug:                                   # a rule must not write into what it observes
            ro = inv.readonly_copy
            obs = Observation(t, k, ro(meas), ro(gap), ro(serv), ro(con), ro(self.X[k]), ro(self.Y[k]), ro(self.V),
                              ro(self.TH[k]), ro(ch.l1[j]))
        else:
            obs = Observation(t, k, meas, gap, serv, con, self.X[k], self.Y[k], self.V, self.TH[k], ch.l1[j])
        self.proc.measure(obs, counted)
        return counted

    def _load(self, ln, tot, counted) -> None:
        """Measurement instant, second part: load, scheduling and delivered rate (see also EngineBatch)."""
        ar, acc, state = self.ar, self.acc, self.state
        serv = self.serv
        con = state == CONNECTED
        buf = self.buf
        if self.proc.dual:                                       # DAPS: the source serves during the execution
            con = con | ((state == EXECUTING) & self.daps_u & (~self.src_rlf if buf is not None else True))
        ls = ln[ar, serv]
        sinr = ls / (tot - self.rc[serv] * ls + self.noise)      # tot = ln @ rc of this step (rc unchanged)
        if self.fad_now is not None:                             # fast fading: capacity over the carrier
            sinr = self._eff_sinr(ln, self.fad_now, self.rc, slice(self.n_rlm, None), capacity_esm)
        ok = con & (sinr >= self.qout)
        se = np.minimum(np.log2(1.0 + sinr), self.se_max)
        rate = self.rate
        if buf is not None:                                      # user-plane buffers (2.3.0): arrivals, discard
            t = self.t_load
            buf.arrive(t, rate * self.mdt if self.offered is None
                       else self.offered[min(self.nmeas, len(self.offered) - 1)])
            buf.discard_old(t)
            frac = buf.start_fraction(t)
            avail = buf.q if self.sched is None else np.maximum(buf.q - self.sched.inflight(), 0.0)
            rate = np.minimum(self.r_peak * frac, avail / self.mdt)
        elif self.backlog is not None:                           # buffered traffic: arrivals, then demand
            self.backlog += self.offered[min(self.nmeas, len(self.offered) - 1)]
            rate = np.minimum(self.r_peak, self.backlog / self.mdt)
        free = np.maximum(1.0 - self.bg, 0.0)
        if self.sched is not None:                               # slot scheduler, MCS and HARQ (2.2.0)
            if buf is not None:
                first = np.ceil((1.0 - frac) * self.sched.n_slots - 1e-9).astype(np.int64)
                got, used = self.sched.serve(sinr, avail, con, serv, free, first)
                buf.harq_lost(t, self.sched.lost_bits)
            else:
                got, used = self.sched.serve(sinr, rate * self.mdt, con, serv, free)
            thr = got / self.mdt
            rho_new = np.minimum(1.0, self.bg + used)
        else:
            need = np.where(ok, rate / (self.W * np.maximum(se, 1e-3)), 0.0)
            G = np.bincount(serv, weights=need * self.gbr, minlength=self.M)
            B = np.bincount(serv, weights=need * ~self.gbr, minlength=self.M)
            gs = np.minimum(1.0, free / np.maximum(G, 1e-12))
            rem = np.maximum(free - G * gs, 0.0)
            bs = np.minimum(1.0, rem / np.maximum(B, 1e-12))
            thr = np.where(ok, rate * np.where(self.gbr, gs[serv], bs[serv]), 0.0)
            rho_new = np.minimum(1.0, self.bg + G * gs + B * bs)
        if buf is not None:                                      # FIFO order, delays (round-robin share rate)
            n_act = np.bincount(serv, weights=thr > 0, minlength=self.M)
            thr = buf.deliver(t, thr * self.mdt, self.W * se * free[serv] / np.maximum(n_act[serv], 1.0)) / self.mdt
        elif self.backlog is not None:
            self.backlog = np.maximum(self.backlog - thr * self.mdt, 0.0)
        self.rho += self.a_rho * (rho_new - self.rho)
        np.multiply(self.chi, self.rho, out=self.rc)
        if self.lm:
            self._update_lm(con)
        if counted:
            acc["steps"] += self.mp
            acc["out_steps"] += self.mp * int(np.count_nonzero(con & (sinr < self.qout)))
            acc["thr"] += float(thr.sum()); acc["dem"] += float(rate.sum())
            acc["sinr"] += float(10.0 * np.log10(sinr[con]).sum()); acc["se"] += float(se[con].sum())
            acc["ncon"] += int(con.sum()); acc["load"] += float(rho_new.mean()); acc["nmeas"] += 1
            acc["prep_time"] += self.proc.prepared_total() * self.mdt

    # ------------------------------------------------------------------ results
    def finish(self) -> Dict[str, float]:
        """Close what is still open, check the invariants and return the metrics of the run."""
        T = self.S * self.dt
        for u in np.nonzero(self.w_on)[0]:
            self._finalize(u, T, "end")
        for u in np.nonzero(self.f_on)[0]:
            self._close_flight(u, T, "censored", "")
        C = self.C
        inv.check_final(self)
        run = self.world.scenario.run
        ue_min = self.U * (run.duration_s - run.warmup_s) / 60.0
        ue_s = max(self.acc["steps"], 1) * self.U * self.dt
        R = self.world.scenario.radio
        p_tx = 10.0 ** (R.tx_power_dbm / 10.0) / 1000.0              # transmit power per cell [W]
        if self.acc.get("load", 0.0) > 0 and "load_ptx" in self.acc:  # layers with their own power (2.1.0)
            p_tx = self.acc["load_ptx"] / self.acc["load"]           # load-weighted mean over the cells
        if self.buf is not None:                                     # user-plane buffers (2.3.0)
            self.buf.check()
            self.acc.update(self.buf.metrics(ue_min))
        return summarize(C, self.acc, ue_min, ue_s, self.U, self.dt, self.proc.open_preparations(),
                         n_sites=self.M, power=(R.energy_ntrx * R.energy_p0_w, R.energy_slope * p_tx))

    @property
    def events(self) -> Optional[List[dict]]:
        """Event log as a list of dictionaries (if the engine was created with ``log_events``)."""
        if not self.keep_events:
            return None
        return [{k: float(v) if isinstance(v, np.floating) else v for k, v in zip(EVENT_FIELDS, row)}
                for row in self.log]

    @property
    def trace(self) -> Optional[List[dict]]:
        """Procedure trace as a list of dictionaries (event-log level ``full`` only)."""
        if self.trace_log is None:
            return None
        return [dict(zip(TRACE_FIELDS, row)) for row in self.trace_log]

    @property
    def fingerprint(self) -> str:
        """SHA-256 of the canonical CSV of the event log (see :mod:`handoverlab.eventlog`)."""
        return fingerprint(self.log)

    @property
    def n_events(self) -> int:
        return len(self.log)
