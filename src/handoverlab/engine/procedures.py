# SPDX-License-Identifier: MIT
"""Handover procedures: baseline, conditional, DAPS handover and L1/L2-triggered mobility.

A procedure holds the per-user state of one handover family and implements
the protocol around the decisions of a rule.  The engine calls it through a
small interface (:class:`Procedure`), so further procedures (for example
L1/L2-triggered mobility) can be added without touching the engine.

Baseline handover (TR 36.839 failure model)
    Event A3 (offset per user and neighbour) held for the time-to-trigger ->
    measurement report -> preparation (``prep_s``) -> handover command.  The
    command is lost if T310 is running when it arrives ("too late").
    Otherwise the UE leaves the source, is interrupted for ``exec_s`` and
    joins the target if the target SINR is at least Qout.

Conditional handover (TS 38.300 clause 9.2.3.4)
    The UE reports a neighbour once it passes the reporting offset (first
    report at once, then every ``report_interval_s``).  At a report the
    network prepares the neighbours whose advantage reaches the preparation
    offset, at most ``n_max`` (best first), and releases prepared cells that
    fell ``release_hys_db`` below it.  The conditional configuration reaches
    the UE after ``prep_s`` and is lost if T310 is running.  The UE evaluates
    the execution condition of every prepared cell at each measurement and
    executes on its own.  After an execution the other prepared cells are
    released; after a failure the UE recovers faster (``cho_recovery_s``) if
    it selects a prepared cell.

DAPS handover (TS 38.300 clause 9.2.3.2, TS 38.331 clause 5.3.5.8.3)
    Triggered and prepared as a baseline handover.  During the execution the
    source link keeps carrying data (the user-plane interruption is
    ``interruption_s`` of the rule instead of ``exec_s``).  If the target
    cannot be joined and the source SINR is still at least Qout, the UE falls
    back to the source: the attempt ends as ``too_early`` with the cause
    ``daps_fallback`` and no re-establishment follows.

L1/L2-triggered mobility (TS 38.300 clause 9.2.3.5)
    Candidate cells are configured as the prepared cells of a conditional
    handover (L3 reports, preparation offset, ``n_max``, release).  The
    network evaluates the unfiltered L1 measurements: when a configured
    candidate is better than the serving cell by the switch offset for
    ``ttt_switch_s``, it sends a cell switch command (MAC CE), which reaches
    the UE after ``cmd_delay_s`` and is lost if T310 is running.  The
    execution takes ``exec_s`` of the rule (RACH-less, with early timing
    advance acquisition).
"""
from __future__ import annotations

import numpy as np

from ..measurement import (EPS, INF, a3_condition, held_for, select_prepared_set, ttt_expires_before,
                           update_entry_times)
from .invariants import check_rule_value

CONNECTED, EXECUTING, REESTABLISHING = 0, 1, 2      # connection state of a user


class Procedure:
    """Interface between the engine and a handover family."""
    kind = ""
    dual = False             # the source link carries data during an execution (DAPS)
    fallback = False         # a failed execution falls back to the source if possible (DAPS)

    def __init__(self, eng, rule):
        self.eng, self.rule = eng, rule

    def exec_time(self, u) -> float:
        """Duration of an execution of user ``u`` [s]."""
        return self.eng.P.exec_s

    def exec_interruption(self, u, duration) -> float:
        """User-plane interruption of an execution of the given duration [s]."""
        return duration

    def step(self, t):
        """Called every step after radio-link monitoring (deliver commands or configurations)."""

    def measure(self, obs, counted):
        """Called at every measurement instant with the filtered measurements."""

    def flight_info(self, u, tgt):
        """(memory key, prepared-set size, execution offset) of an attempt that starts at execution."""
        return -1, 0, np.nan

    def cancel_command(self, u):
        """A pending handover command of user ``u`` is void."""

    def on_attach(self, u):
        """User ``u`` is connected to a new serving cell."""

    def on_failure(self, u):
        """User ``u`` had a failure and starts re-establishment."""

    def clear(self, u, used_cell, t):
        """Drop all preparations of user ``u`` (``used_cell`` is the cell it went to, or -1)."""

    def before_link_failure(self, u, t):
        """User ``u`` has a radio-link failure while no attempt is in flight (called first)."""

    def recovers_into(self, u, cell) -> bool:
        """True if a failed UE that selects ``cell`` recovers into a prepared cell."""
        return False

    def prepared_count(self, u) -> int:
        return 0

    def prepared_total(self) -> int:
        return 0

    def open_preparations(self) -> int:
        return 0


class BaselineProcedure(Procedure):
    kind = "ho"

    def __init__(self, eng, rule):
        super().__init__(eng, rule)
        U, M = eng.U, eng.M
        self.te = np.full((U, M), INF)              # time since which A3 holds
        self.pend = np.zeros(U, dtype=bool)         # handover command on its way
        self.pend_t = np.zeros(U)
        self.n_pend = 0                             # number of commands on their way

    def step(self, t):
        eng = self.eng
        if not self.n_pend:
            return
        for u in np.nonzero(self.pend & (t >= self.pend_t - EPS))[0]:
            if eng.run[u]:
                eng.fail(u, t, "cmd")                   # command lost while T310 runs
            else:
                eng.start_exec(u, int(eng.f_tgt[u]), t)

    def measure(self, obs, counted):
        eng, rule = self.eng, self.rule
        off = rule.a3_offsets(obs)
        ttt = rule.time_to_trigger(obs)
        if eng.debug:
            check_rule_value(eng, "a3_offsets", off, obs.t)
            check_rule_value(eng, "time_to_trigger", ttt, obs.t, per_cell=False)
        cond = a3_condition(obs.gap_db, off, obs.serving, obs.connected)
        te = self.te = update_entry_times(self.te, cond, obs.t)
        ready = ttt_expires_before(te, ttt, obs.t, eng.mdt)
        per_user_ttt = isinstance(ttt, np.ndarray) and np.ndim(ttt) == 1
        for u in np.nonzero(ready.any(1) & ~self.pend)[0]:
            o = off[u] if isinstance(off, np.ndarray) else off
            tgt = int(np.argmax(np.where(ready[u], obs.gap_db[u] - o, -INF)))
            t_rep = max(obs.t, te[u, tgt] + (ttt[u] if per_user_ttt else ttt))
            eng.new_flight(u, tgt, t_rep, -1, 0, o[tgt] if isinstance(o, np.ndarray) else o)
            if eng.trace_log is not None:
                eng.trace_event(t_rep, u, "report", eng.serv[u], tgt, o[tgt] if isinstance(o, np.ndarray) else o)
            self.pend[u] = True
            self.n_pend += 1
            self.pend_t[u] = t_rep + eng.P.prep_s
            eng.C["reports"] += int(counted)

    def cancel_command(self, u):
        if self.pend[u]:
            self.pend[u] = False
            self.n_pend -= 1

    def on_attach(self, u):
        self.te[u] = INF

    def on_failure(self, u):
        self.cancel_command(u)
        self.te[u] = INF


class ConditionalProcedure(Procedure):
    kind = "cho"

    def __init__(self, eng, rule):
        super().__init__(eng, rule)
        U, M = eng.U, eng.M
        self.prepared = np.zeros((U, M), dtype=bool)        # configuration held by the UE
        self.ppend = np.zeros((U, M), dtype=bool)           # configuration on its way
        self.ppend_t = np.full((U, M), INF)
        self.oexec = np.zeros((U, M))                       # execution offset of each configuration
        self.pkey = np.full((U, M), -1)
        self.tx = np.full((U, M), INF)                      # time since which the execution condition holds
        self.tr = np.full((U, M), INF)                      # time since which the reporting condition holds
        self.seen = np.zeros((U, M), dtype=bool)
        self.n_pp, self.pp_next = 0, INF

    # -- interface -----------------------------------------------------
    def flight_info(self, u, tgt):
        return self.pkey[u, tgt], int(self.prepared[u].sum()), self.oexec[u, tgt]

    def recovers_into(self, u, cell):
        return (not self.rule.immediate) and bool(self.prepared[u, cell])

    def prepared_count(self, u):
        return int(self.prepared[u].sum())

    def prepared_total(self):
        return int(np.count_nonzero(self.prepared))

    def open_preparations(self):
        return int(np.count_nonzero(self.prepared | self.ppend))

    def on_attach(self, u):
        pass

    def before_link_failure(self, u, t):
        if self.eng.P.cfg_loss_as_failure and self.ppend[u].any():
            # check mode: a configuration on its way counts as a handover command on its way
            self.eng.new_flight(u, int(np.argmax(self.ppend[u])), t)

    def clear(self, u, used_cell, t):
        C = self.eng.C
        npr = int(self.prepared[u].sum())
        used = 1 if (used_cell >= 0 and self.prepared[u, used_cell]) else 0
        npp = int(self.ppend[u].sum())
        C["prep_used_all"] += used
        C["prep_wasted_all"] += npr - used
        C["prep_cancel_all"] += npp
        if t >= self.eng.t0c:
            C["prep_used"] += used
            C["prep_wasted"] += npr - used
            C["prep_cancel"] += npp
        if self.eng.trace_log is not None:
            for n in np.nonzero(self.prepared[u] | self.ppend[u])[0]:
                if n != used_cell:
                    self.eng.trace_event(t, u, "release", self.eng.serv[u], n)
        self.prepared[u] = False
        self.ppend[u] = False
        self.ppend_t[u] = INF
        self.tx[u] = INF
        self.tr[u] = INF
        self.seen[u] = False

    # -- configurations reach the UE ----------------------------------
    def step(self, t):
        if self.n_pp and t >= self.pp_next - EPS:
            self._deliver(t)

    def _deliver(self, t):
        eng = self.eng
        due = self.ppend & (t >= self.ppend_t - EPS)
        for u, n in zip(*np.nonzero(due)):
            if not self.ppend[u, n]:
                continue                                    # dropped by an earlier event of this step
            self.ppend[u, n] = False
            self.ppend_t[u, n] = INF
            if eng.state[u] == CONNECTED and not eng.run[u]:
                self.prepared[u, n] = True
                if eng.trace_log is not None:
                    eng.trace_event(t, u, "config", eng.serv[u], n, self.oexec[u, n])
                eng.C["cfg_ok"] += int(t >= eng.t0c)
                if self._exec_on_delivery(u, n):
                    eng.start_exec(u, int(n), t)
            else:
                if eng.trace_log is not None:
                    eng.trace_event(t, u, "config_lost", eng.serv[u], n)
                eng.C["cfg_lost"] += int(t >= eng.t0c)
                eng.C["prep_lost_all"] += 1
                if eng.P.cfg_loss_as_failure and eng.state[u] == CONNECTED:
                    eng.new_flight(u, int(n), t)                    # check mode: like a lost handover command
                    eng.fail(u, t, "cmd")
        self.n_pp = int(np.count_nonzero(self.ppend))
        self.pp_next = float(self.ppend_t.min()) if self.n_pp else INF

    def _exec_on_delivery(self, u, n) -> bool:
        """True if the UE executes towards ``n`` as soon as its configuration arrives."""
        rule, meas = self.rule, self.eng.meas
        return rule.immediate or (rule.ttt_exec_s <= 0 and meas[u, n] - meas[u, self.eng.serv[u]] > self.oexec[u, n])

    def _config_offsets(self, obs):
        """Offsets written into new configurations (execution offsets of the rule)."""
        oe = self.rule.exec_offsets(obs)
        if self.eng.debug:
            check_rule_value(self.eng, "exec_offsets", oe, obs.t)
        return oe

    # -- measurement instant -------------------------------------------
    def measure(self, obs, counted):
        con = obs.connected
        if self.prepared.any():
            con = self._execute(obs, con)
        self._report(obs, counted, con)

    def _execute(self, obs, con):
        """UE side: execution condition of the prepared cells; returns the users still connected."""
        eng, gap, t = self.eng, obs.gap_db, obs.t
        cx = self.prepared & (gap > self.oexec) & con[:, None]
        self.tx = np.where(cx, np.minimum(self.tx, t), INF)
        rdy = held_for(self.tx, t, self.rule.ttt_exec_s)
        for u in np.nonzero(rdy.any(1))[0]:
            eng.start_exec(u, int(np.argmax(np.where(rdy[u], gap[u], -INF))), t)
        return eng.state == CONNECTED

    def _report(self, obs, counted, con):
        """UE side: reporting condition; network side: cells to prepare, keep or release."""
        eng, rule = self.eng, self.rule
        C, ar, serv, gap, t = eng.C, eng.ar, eng.serv, obs.gap_db, obs.t
        # UE side: reporting condition
        cr = gap > rule.report_offset_db
        cr[ar, serv] = False
        cr &= con[:, None]
        self.tr = update_entry_times(self.tr, cr, t)
        reported = held_for(self.tr, t, rule.ttt_prep_s)
        fresh = reported & ~self.seen
        self.seen = reported
        if eng.nmeas % eng.rep == 0:                       # periodic report: every connected UE is re-evaluated
            if not (reported.any() or self.prepared.any() or self.ppend.any()):
                return
            act = con.copy()
        else:                                              # in between: only UEs with a newly triggered cell
            act = fresh.any(1)
            if not act.any():
                return
        if counted:
            C["reports"] += int(np.count_nonzero(act & reported.any(1)))
        # network side: which cells to prepare, keep or release
        po = rule.prep_offsets(obs)
        if eng.debug:
            check_rule_value(eng, "prep_offsets", po, t)
        score = gap - po
        have = self.prepared | self.ppend
        desired = select_prepared_set(score, reported, have, act, serv, rule.n_max, rule.release_hys_db,
                                      rule.stick_db)
        to_prep = desired & ~have
        to_rel = have & ~desired & act[:, None]
        if to_rel.any():
            if eng.trace_log is not None:
                for u, n in zip(*np.nonzero(to_rel)):
                    eng.trace_event(t, u, "release", serv[u], n)
            C["prep_wasted_all"] += int(np.count_nonzero(to_rel & self.prepared))
            C["prep_cancel_all"] += int(np.count_nonzero(to_rel & self.ppend))
            if counted:
                C["prep_wasted"] += int(np.count_nonzero(to_rel & self.prepared))
                C["prep_cancel"] += int(np.count_nonzero(to_rel & self.ppend))
                C["rel"] += int(np.count_nonzero(to_rel))
            self.prepared[to_rel] = False
            self.ppend[to_rel] = False
            self.ppend_t[to_rel] = INF
            self.tx[to_rel] = INF
        if to_prep.any():
            oe = self._config_offsets(obs)
            keys = rule.memory_key(obs)
            if eng.debug:
                if keys is not None:
                    check_rule_value(eng, "memory_key", keys, t, per_cell=False)
            C["prep_req_all"] += len(np.nonzero(to_prep)[0])
            uu, nn = np.nonzero(to_prep)
            self.ppend[uu, nn] = True
            self.ppend_t[uu, nn] = t + eng.P.prep_s
            self.n_pp, self.pp_next = self.n_pp + len(uu), min(self.pp_next, t + eng.P.prep_s)
            self.oexec[uu, nn] = oe[uu, nn] if isinstance(oe, np.ndarray) else oe
            self.pkey[uu, nn] = keys[uu] if keys is not None else -1
            if counted:
                C["prep_req"] += len(uu)
            if eng.trace_log is not None:
                for u, n in zip(uu, nn):
                    eng.trace_event(t, u, "prepare", serv[u], n, self.oexec[u, n])


class DAPSProcedure(BaselineProcedure):
    """DAPS handover: a baseline handover whose source link stays up during the execution."""
    kind = "daps"

    def __init__(self, eng, rule):
        super().__init__(eng, rule)
        self.dual = bool(rule.source_data)
        self.fallback = bool(rule.fallback)

    def exec_interruption(self, u, duration):
        return min(float(self.rule.interruption_s), duration) if self.dual else duration


class LTMProcedure(ConditionalProcedure):
    """L1/L2-triggered mobility: candidates configured on L3 reports, cell switch on L1 reports."""
    kind = "ltm"

    def __init__(self, eng, rule):
        super().__init__(eng, rule)
        U = eng.U
        self.cmd = np.zeros(U, dtype=bool)          # cell switch command on its way
        self.cmd_t = np.zeros(U)
        self.cmd_tgt = np.zeros(U, dtype=int)
        self.n_cmd = 0

    def exec_time(self, u):
        return float(self.rule.exec_s)

    def recovers_into(self, u, cell):
        return bool(self.rule.recovery) and bool(self.prepared[u, cell])

    def _exec_on_delivery(self, u, n):
        return False                                # the network decides the switch

    def _config_offsets(self, obs):
        so = self.rule.switch_offsets(obs)
        if self.eng.debug:
            check_rule_value(self.eng, "switch_offsets", so, obs.t)
        return so

    def cancel_command(self, u):
        if self.cmd[u]:
            self.cmd[u] = False
            self.n_cmd -= 1

    def on_failure(self, u):
        self.cancel_command(u)

    def step(self, t):
        super().step(t)
        if not self.n_cmd:
            return
        eng = self.eng
        for u in np.nonzero(self.cmd & (t >= self.cmd_t - EPS))[0]:
            if eng.run[u]:
                eng.fail(u, t, "cmd")                   # command lost while T310 runs
            else:
                eng.start_exec(u, int(self.cmd_tgt[u]), t)

    def _execute(self, obs, con):
        """Network side: cell switch decision on the L1 reports of the configured candidates."""
        eng, rule, t = self.eng, self.rule, obs.t
        l1 = obs.l1_dbm if obs.l1_dbm is not None else obs.meas_dbm
        lgap = l1 - l1[eng.ar, obs.serving][:, None]
        so = rule.switch_offsets(obs)
        if eng.debug:
            check_rule_value(eng, "switch_offsets", so, t)
        cx = self.prepared & (lgap > so) & (con & ~self.cmd)[:, None]
        self.tx = np.where(cx, np.minimum(self.tx, t), INF)
        rdy = held_for(self.tx, t, rule.ttt_switch_s)
        for u in np.nonzero(rdy.any(1))[0]:
            n = int(np.argmax(np.where(rdy[u], lgap[u], -INF)))
            o = so[u, n] if isinstance(so, np.ndarray) else so
            eng.new_flight(u, n, t, self.pkey[u, n], int(self.prepared[u].sum()), o)
            if eng.trace_log is not None:
                eng.trace_event(t, u, "switch", eng.serv[u], n, o)
            self.cmd[u] = True
            self.cmd_t[u] = t + float(rule.cmd_delay_s)
            self.cmd_tgt[u] = n
            self.n_cmd += 1
            self.tx[u] = INF
        return con


def make_procedure(eng, rule) -> Procedure:
    if rule.family == "baseline":
        return BaselineProcedure(eng, rule)
    if rule.family == "conditional":
        return ConditionalProcedure(eng, rule)
    if rule.family == "daps":
        return DAPSProcedure(eng, rule)
    if rule.family == "ltm":
        return LTMProcedure(eng, rule)
    raise ValueError("rule %r has unknown family %r" % (getattr(rule, "name", rule), rule.family))
