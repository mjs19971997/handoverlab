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

from ..eventlog import EVENT_FIELDS, TRACE_FIELDS, event_level, fingerprint
from ..measurement import EPS, INF, L3Filter
from ..rules.base import EARLY, LATE, UNNECESSARY, USEFUL, FailureRecord, Observation, OutcomeRecord, RuleContext
from ..seeds import rule_stream
from . import invariants as inv
from .metrics import Counters, summarize
from .procedures import CONNECTED, EXECUTING, REESTABLISHING, make_procedure

LN10_10 = np.log(10.0) / 10.0


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
        self.M = world.layout.n_sites
        self.dt = P.step_s
        self.mp = max(1, int(round(P.l1_period_s / P.step_s)))      # steps per measurement
        self.mdt = self.mp * P.step_s
        self.rep = max(1, int(round(P.report_interval_s / self.mdt)))
        self.lab_every = max(1, int(round(P.label_period_s / self.mdt)))
        self.learns = bool(rule.learns)
        self.l3 = L3Filter(P.l3_k, self.mdt)
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
        self.a_rho = 1.0 - np.exp(-self.mdt / T.load_tau_s)
        svc = world.services
        self.tmin, self.thq, self.rate, self.gbr = svc.t_min, svc.theta_q, svc.rate, svc.gbr
        self.t0c = sc.run.warmup_s
        self.level = event_level(log_events)
        self.keep_events = self.level != "off"
        self.log: List[tuple] = []
        self.trace_log: Optional[List[tuple]] = [] if self.level == "full" else None
        self.debug = inv.debug_from_env() if debug is None else bool(debug)
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
        self.kind = self.proc.kind
        rule.reset(RuleContext(U, self.M, world.layout.sites, world.radio_map.nominal_cell, P.step_s,
                               self.mdt, world.seed, rule_stream(world.seed), sc))

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
        d = self.proc.exec_time(u)
        self.state[u] = EXECUTING
        self.t_done[u] = t + d
        self.run[u] = False
        self.proc.cancel_command(u)
        if t >= self.t0c:
            self.C["exec"] += 1
            self.acc["int_exec"] += min(self.proc.exec_interruption(u, d), self.S * self.dt - t)

    def _attach(self, u, cell, s, t=None):
        if self.trace_log is not None:
            self.trace_event(t, u, "attach" if self.state[u] == EXECUTING else "reestablish", self.serv[u], cell,
                             10.0 * np.log10(max(float(s), 1e-30)))
        self.serv[u] = cell
        self.state[u] = CONNECTED
        self.qo[u] = self.qi[u] = s
        self.n_o[u] = self.n_i[u] = 0
        self.run[u] = False
        self.proc.on_attach(u)

    def _end_exec(self, u, t, ln, tot):
        tgt = int(self.f_tgt[u])
        lt = ln[u, tgt]
        s = lt / (tot[u] - self.rc[tgt] * lt + self.noise)
        if s < self.qout:
            if not (self.proc.fallback and self._fallback(u, t, ln, tot)):
                self.fail(u, t, "exec")
            return
        src = int(self.serv[u])
        pp = (self.prev[u] == tgt) and (t - self.last_ho[u] < self.P.pingpong_s)
        cnt = bool(self.f_cnt[u])
        if cnt:
            self.C["ho"] += 1
            self.C["pp"] += int(pp)
        self.proc.clear(u, tgt, t)
        self.prev[u] = src
        self.last_ho[u] = t
        self._attach(u, tgt, s, t)
        # open the evaluation window
        self.w_on[u] = True; self.w_t0[u] = t; self.w_ta[u] = self.f_t[u]; self.w_tx[u] = self.f_tx[u]
        self.w_src[u] = src; self.w_tgt[u] = tgt; self.w_key[u] = self.f_key[u]
        self.w_np[u] = self.f_np[u]; self.w_oe[u] = self.f_oe[u]; self.w_cnt[u] = cnt
        self.w_n[u] = 0; self.w_g[u] = 0; self.w_m[u] = 0; self.w_cf[u] = 0; self.w_cff[u] = False
        self.w_mcf[u] = 0; self.w_mcff[u] = False; self.w_pp[u] = pp
        self.f_on[u] = False

    def _fallback(self, u, t, ln, tot) -> bool:
        """DAPS: the target could not be joined; return to the source if its SINR is at least Qout."""
        src = int(self.serv[u])
        ls = ln[u, src]
        s = ls / (tot[u] - self.rc[src] * ls + self.noise)
        if s < self.qout:
            return False
        self._feedback(u, src, self.f_tgt[u], self.f_key[u], EARLY, t)
        if self.trace_log is not None:
            self.trace_event(t, u, "fallback", src, self.f_tgt[u], 10.0 * np.log10(max(float(s), 1e-30)))
        self._close_flight(u, t, "too_early", "daps_fallback")
        self.state[u] = CONNECTED
        self.proc.on_attach(u)
        return True

    def fail(self, u, t, kind):
        """Mobility failure of user ``u``: "rlf" (T310 expired), "cmd" (command lost) or "exec"."""
        c = int(np.argmax(self.meas[u]))                  # cell selected for re-establishment
        s = int(self.serv[u])
        if kind == "rlf" and not self.f_on[u]:
            self.proc.before_link_failure(u, t)
        if kind == "exec":
            src, tgt = int(self.f_src[u]), int(self.f_tgt[u])
            cause = "execution_failure"
            self._feedback(u, src, tgt, self.f_key[u], EARLY, t)
            self._close_flight(u, t, "too_early" if c in (src, tgt) else "wrong_cell", cause)
        elif kind == "cmd":
            cause = "command_lost"
            self._feedback(u, self.f_src[u], self.f_tgt[u], self.f_key[u], LATE, t)
            self._close_flight(u, t, "too_late", cause)
        elif self.w_on[u]:
            cause = "rlf_after_handover"
            self._feedback(u, self.w_src[u], self.w_tgt[u], self.w_key[u], EARLY, t)
            dwell = t - self.w_t0[u]
            self._close_window(u, t, "too_early" if c in (int(self.w_src[u]), s) else "wrong_cell", cause,
                               dwell, self.w_g[u] / max(self.w_n[u], 1.0))
            if self.f_on[u]:
                self._feedback(u, self.f_src[u], self.f_tgt[u], self.f_key[u], LATE, t)
                self._close_flight(u, t, "too_late", "rlf_in_preparation")
        elif self.f_on[u]:
            cause = "rlf_in_preparation"
            self._feedback(u, self.f_src[u], self.f_tgt[u], self.f_key[u], LATE, t)
            self._close_flight(u, t, "too_late", cause)
        else:
            cause = "rlf_without_handover" if c != s else "coverage_rlf"
            npr = self.proc.prepared_count(u)
            if c != s:
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
        self.t_done[u] = t + t_out
        if t >= self.t0c:
            self.acc["int_fail"] += min(t_out, self.S * self.dt - t)
        self.re_cell[u] = c
        self.run[u] = False
        self.proc.on_failure(u)

    # ------------------------------------------------------------------ main loop
    def _init(self, ch):
        self.l3.reset(ch.l1[0])
        self.serv[:] = np.argmax(self.meas, axis=1)
        self.started = True
        if self.trace_log is not None:
            t0 = ch.k0 * self.dt
            for u in range(self.U):
                self.trace_event(t0, u, "serve", -1, self.serv[u])
        ln = ch.lin[0]
        ls = ln[self.ar, self.serv]
        s = ls / (ln @ self.rc - self.rc[self.serv] * ls + self.noise)
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
        for i in range(ch.n):
            k = ch.k0 + i
            t = k * dt
            ln = ch.lin[i]
            tot = ln @ self.rc
            # --- end of an execution or of a re-establishment
            if cnz(state):
                for u in np.nonzero((state != CONNECTED) & (t >= self.t_done - EPS))[0]:
                    if state[u] == EXECUTING:
                        self._end_exec(u, t, ln, tot)
                    else:
                        c = int(self.re_cell[u])
                        lc = ln[u, c]
                        self._attach(u, c, lc / (tot[u] - self.rc[c] * lc + noise), t)
            serv = self.serv
            ls = ln[ar, serv]
            sinr = ls / (tot - self.rc[serv] * ls + noise)
            con = state == CONNECTED
            # --- radio-link monitoring
            qo += ao * (sinr - qo)
            qi += ai * (sinr - qi)
            if simple:
                start = (qo < qout) & con & ~run
            else:
                self.n_o[:] = (self.n_o + 1) * (qo < qout)
                self.n_i[:] = (self.n_i + 1) * (qi > qin)
                start = con & ~run & (self.n_o >= P.n310)
            if cnz(start):
                run |= start
                self.t310[start] = t
                self.k310[start] = k
            if cnz(run):
                run &= ~((qi > qin) if simple else (self.n_i >= P.n311))
                for u in np.nonzero(run & con & (t - self.t310 >= P.t310_s - EPS))[0]:
                    self.fail(u, t, "rlf")
            # --- handover command / conditional configuration reaches the UE
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
        if self.proc.dual:                                       # DAPS: the source serves during the execution
            con = con | (state == EXECUTING)
        ls = ln[ar, serv]
        sinr = ls / (tot - self.rc[serv] * ls + self.noise)      # tot = ln @ rc of this step (rc unchanged)
        ok = con & (sinr >= self.qout)
        se = np.minimum(np.log2(1.0 + sinr), self.se_max)
        need = np.where(ok, self.rate / (self.W * np.maximum(se, 1e-3)), 0.0)
        G = np.bincount(serv, weights=need * self.gbr, minlength=self.M)
        B = np.bincount(serv, weights=need * ~self.gbr, minlength=self.M)
        free = np.maximum(1.0 - self.bg, 0.0)
        gs = np.minimum(1.0, free / np.maximum(G, 1e-12))
        rem = np.maximum(free - G * gs, 0.0)
        bs = np.minimum(1.0, rem / np.maximum(B, 1e-12))
        thr = np.where(ok, self.rate * np.where(self.gbr, gs[serv], bs[serv]), 0.0)
        rho_new = np.minimum(1.0, self.bg + G * gs + B * bs)
        self.rho += self.a_rho * (rho_new - self.rho)
        np.multiply(self.chi, self.rho, out=self.rc)
        if counted:
            acc["steps"] += self.mp
            acc["out_steps"] += self.mp * int(np.count_nonzero(con & (sinr < self.qout)))
            acc["thr"] += float(thr.sum()); acc["dem"] += float(self.rate.sum())
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
        return summarize(C, self.acc, ue_min, ue_s, self.U, self.dt, self.proc.open_preparations())

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
