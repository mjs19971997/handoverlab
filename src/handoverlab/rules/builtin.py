# SPDX-License-Identifier: MIT
"""Built-in rules.

``A3``        Event A3 baseline handover
``CHO``       Rel-16 conditional handover with fixed offsets
``DAPS``      Rel-16 DAPS handover triggered by Event A3 (since 1.0.0rc2)
``LTM``       Rel-18 L1/L2-triggered mobility with fixed offsets (since 1.0.0rc2)
``BanditA3``  Event A3 whose offset is learned per cell by an epsilon-greedy bandit (since 1.0.0rc2)
``A3A5``      Event A3 within a carrier, Event A5 between carriers (since 1.10.0)
"""
from __future__ import annotations

import numpy as np

from .base import (EARLY, LATE, MAX_CONDITIONAL_CELLS, UNNECESSARY, USEFUL, BaselineRule, ConditionalRule, DAPSRule,
                   CLTMRule, LTMRule)


class A3(BaselineRule):
    """Event A3 with one offset and one time-to-trigger for all users.

    off_db  A3 offset [dB] (neighbour better than serving by more than this)
    ttt_s   time-to-trigger [s]
    """

    def __init__(self, off_db: float = 3.0, ttt_s: float = 0.16, name: str = "A3"):
        super().__init__(name)
        if ttt_s < 0:
            raise ValueError("ttt_s must be >= 0")
        self.off_db, self.ttt_s = float(off_db), float(ttt_s)

    def params(self):
        return dict(off_db=self.off_db, ttt_s=self.ttt_s)

    def a3_offsets(self, obs):
        return self.off_db

    def time_to_trigger(self, obs):
        return self.ttt_s


class CHO(ConditionalRule):
    """Conditional handover with fixed offsets.

    o_prep_db    preparation offset [dB]: a neighbour is reported and prepared
                 when it is better than the serving cell by this much for
                 ``ttt_prep_s`` (negative: prepared before it is stronger)
    o_exec_db    execution offset [dB] carried in the conditional configuration
    ttt_exec_s   time-to-trigger of the execution condition [s]
    ttt_prep_s   time-to-trigger of the reporting condition [s]
    n_max        largest prepared set (1-8, maxNrofCondCells-r16)
    rel_hys_db   release hysteresis [dB]
    immediate    execute as soon as the configuration arrives
    """

    def __init__(self, o_prep_db: float = -2.0, o_exec_db: float = 3.0, ttt_exec_s: float = 0.08,
                 ttt_prep_s: float = 0.0, n_max: int = 4, rel_hys_db: float = 3.0, immediate: bool = False,
                 name: str = "CHO"):
        super().__init__(name)
        if not 1 <= int(n_max) <= MAX_CONDITIONAL_CELLS:
            raise ValueError("n_max must be between 1 and %d (maxNrofCondCells-r16)" % MAX_CONDITIONAL_CELLS)
        if ttt_exec_s < 0 or ttt_prep_s < 0:
            raise ValueError("time-to-trigger values must be >= 0")
        self.o_prep_db, self.o_exec_db = float(o_prep_db), float(o_exec_db)
        self.ttt_exec_s, self.ttt_prep_s = float(ttt_exec_s), float(ttt_prep_s)
        self.n_max, self.release_hys_db, self.immediate = int(n_max), float(rel_hys_db), bool(immediate)
        self.report_offset_db = self.o_prep_db
        if self.immediate:
            self.stick_db = np.inf          # the cell chosen at the report is never replaced

    def params(self):
        return dict(o_prep_db=self.o_prep_db, o_exec_db=self.o_exec_db, ttt_exec_s=self.ttt_exec_s,
                    ttt_prep_s=self.ttt_prep_s, n_max=self.n_max, rel_hys_db=self.release_hys_db,
                    immediate=self.immediate)

    def prep_offsets(self, obs):
        return self.o_prep_db

    def exec_offsets(self, obs):
        return -np.inf if self.immediate else self.o_exec_db


class DAPS(DAPSRule):
    """Dual active protocol stack (DAPS) handover triggered by Event A3 (3GPP Rel-16).

    Specification: TS 38.300 clause 9.2.3.2 (handover; DAPS keeps the source
    link during the handover), clause 9.2.7 (radio-link failure detection on
    the source continues until the target is joined), TS 38.331 clause
    5.3.5.8.3 (failure of the reconfiguration with sync: fallback to the
    source when its link has not failed).

    Trigger: Event A3 (TS 38.331 clause 5.5.4.4), neighbour better than the
    serving cell by ``off_db`` for ``ttt_s``; report, preparation and command
    as a baseline handover.

    off_db          A3 offset [dB]
    ttt_s           time-to-trigger [s]
    interruption_s  user-plane interruption of an execution [s] (Rel-16 aims at 0)
    fallback        fall back to the source if the target cannot be joined and the
                    source SINR is at least Qout
    source_data     the source keeps serving data during the execution

    With ``fallback=False`` and ``source_data=False`` the rule gives the same
    event log as :class:`A3` with the same offset and time-to-trigger.
    """

    def __init__(self, off_db: float = 3.0, ttt_s: float = 0.16, interruption_s: float = 0.0,
                 fallback: bool = True, source_data: bool = True, name: str = "DAPS"):
        super().__init__(name)
        if ttt_s < 0 or interruption_s < 0:
            raise ValueError("ttt_s and interruption_s must be >= 0")
        self.off_db, self.ttt_s = float(off_db), float(ttt_s)
        self.interruption_s = float(interruption_s)
        self.fallback, self.source_data = bool(fallback), bool(source_data)

    def params(self):
        return dict(off_db=self.off_db, ttt_s=self.ttt_s, interruption_s=self.interruption_s,
                    fallback=self.fallback, source_data=self.source_data)

    def a3_offsets(self, obs):
        return self.off_db

    def time_to_trigger(self, obs):
        return self.ttt_s


class LTM(LTMRule):
    """L1/L2-triggered mobility (LTM) with fixed offsets (3GPP Rel-18).

    Specification: TS 38.300 clause 9.2.3.5 (LTM: candidate cell
    configuration, L1 measurement reporting, cell switch command, early
    timing advance acquisition and RACH-less execution); TS 38.321 (LTM cell
    switch command MAC CE); TS 38.331 clause 5.5.3.2 (L3 filtering of the
    measurements that select the candidates).

    Candidates: a neighbour whose L3-filtered measurement is better than the
    serving cell by ``o_prep_db`` for ``ttt_prep_s`` is reported and
    configured as a candidate (at most ``n_max``, best first; released
    ``rel_hys_db`` below the offset).  Cell switch: the network switches to
    a configured candidate whose unfiltered L1 measurement is better than the
    serving cell by ``o_switch_db`` at every L1 report for ``ttt_switch_s``;
    the command reaches the UE after ``cmd_delay_s``, the execution takes
    ``exec_s``.

    o_prep_db     candidate preparation offset [dB] (L3)
    o_switch_db   cell switch offset [dB] (L1)
    ttt_switch_s  time the switch condition must hold [s] (0: one L1 report)
    ttt_prep_s    time-to-trigger of the candidate report [s]
    n_max         largest candidate set (1-8)
    rel_hys_db    release hysteresis [dB]
    cmd_delay_s   delay of the cell switch command [s]
    exec_s        execution time of the cell switch [s]
    recovery      a failed UE that selects a candidate recovers into it in ``cho_recovery_s``
    """

    def __init__(self, o_prep_db: float = -3.0, o_switch_db: float = 2.0, ttt_switch_s: float = 0.08,
                 ttt_prep_s: float = 0.0, n_max: int = 4, rel_hys_db: float = 3.0, cmd_delay_s: float = 0.01,
                 exec_s: float = 0.02, recovery: bool = True, name: str = "LTM"):
        super().__init__(name)
        if not 1 <= int(n_max) <= MAX_CONDITIONAL_CELLS:
            raise ValueError("n_max must be between 1 and %d" % MAX_CONDITIONAL_CELLS)
        if min(ttt_switch_s, ttt_prep_s, cmd_delay_s) < 0 or exec_s <= 0:
            raise ValueError("times must be >= 0 and exec_s > 0")
        self.o_prep_db, self.o_switch_db = float(o_prep_db), float(o_switch_db)
        self.ttt_switch_s, self.ttt_prep_s = float(ttt_switch_s), float(ttt_prep_s)
        self.n_max, self.release_hys_db = int(n_max), float(rel_hys_db)
        self.cmd_delay_s, self.exec_s, self.recovery = float(cmd_delay_s), float(exec_s), bool(recovery)
        self.report_offset_db = self.o_prep_db

    def params(self):
        return dict(o_prep_db=self.o_prep_db, o_switch_db=self.o_switch_db, ttt_switch_s=self.ttt_switch_s,
                    ttt_prep_s=self.ttt_prep_s, n_max=self.n_max, rel_hys_db=self.release_hys_db,
                    cmd_delay_s=self.cmd_delay_s, exec_s=self.exec_s, recovery=self.recovery)

    def prep_offsets(self, obs):
        return self.o_prep_db

    def switch_offsets(self, obs):
        return self.o_switch_db


class CLTM(CLTMRule):
    """Conditional L1/L2-triggered mobility with fixed offsets (3GPP Rel-19 work on LTM).

    Specification: TS 38.300 clause 9.2.3.5 (LTM, Rel-18) for the candidate configuration, L1
    measurements and RACH-less execution; the Rel-19 work item on further NR mobility
    enhancements adds conditional LTM, in which the UE executes a configured LTM cell switch when
    a condition holds, without the cell switch command.  As the Rel-19 text was not frozen when
    this rule was written, the condition is modelled like the LTM switch condition: a configured
    candidate whose unfiltered L1 measurement is better than the serving cell by ``o_switch_db``
    at every L1 sample for ``ttt_switch_s``; the UE then executes at once (``exec_s``).

    o_prep_db     candidate preparation offset [dB] (L3)
    o_switch_db   cell switch offset [dB] (L1), evaluated by the UE
    ttt_switch_s  time the switch condition must hold [s] (0: one L1 sample)
    ttt_prep_s    time-to-trigger of the candidate report [s]
    n_max         largest candidate set (1-8)
    rel_hys_db    release hysteresis [dB]
    exec_s        execution time of the cell switch [s]
    recovery      a failed UE that selects a candidate recovers into it in ``cho_recovery_s``
    """

    def __init__(self, o_prep_db: float = -3.0, o_switch_db: float = 2.0, ttt_switch_s: float = 0.08,
                 ttt_prep_s: float = 0.0, n_max: int = 4, rel_hys_db: float = 3.0, exec_s: float = 0.02,
                 recovery: bool = True, name: str = "CLTM"):
        super().__init__(name)
        if not 1 <= int(n_max) <= MAX_CONDITIONAL_CELLS:
            raise ValueError("n_max must be between 1 and %d" % MAX_CONDITIONAL_CELLS)
        if min(ttt_switch_s, ttt_prep_s) < 0 or exec_s <= 0:
            raise ValueError("times must be >= 0 and exec_s > 0")
        self.o_prep_db, self.o_switch_db = float(o_prep_db), float(o_switch_db)
        self.ttt_switch_s, self.ttt_prep_s = float(ttt_switch_s), float(ttt_prep_s)
        self.n_max, self.release_hys_db = int(n_max), float(rel_hys_db)
        self.exec_s, self.recovery = float(exec_s), bool(recovery)
        self.cmd_delay_s = 0.0
        self.report_offset_db = self.o_prep_db

    def params(self):
        return dict(o_prep_db=self.o_prep_db, o_switch_db=self.o_switch_db, ttt_switch_s=self.ttt_switch_s,
                    ttt_prep_s=self.ttt_prep_s, n_max=self.n_max, rel_hys_db=self.release_hys_db,
                    exec_s=self.exec_s, recovery=self.recovery)

    def prep_offsets(self, obs):
        return self.o_prep_db

    def switch_offsets(self, obs):
        return self.o_switch_db


class CHOD2(CHO):
    """Conditional handover with condEventD2 together with A3 (NTN with moving cells; since 2.0.0).

    TS 38.331 V18 5.5.4.15a, Event D2: entering when ``Ml1 - Hys > Thresh1`` (distance of the UE from the
    serving cell's moving reference location) and ``Ml2 + Hys < Thresh2`` (distance from the candidate's moving
    reference location); leaving when ``Ml1 + Hys < Thresh1`` or ``Ml2 - Hys > Thresh2``.  The reference
    locations are ``ctx.cell_center(t)``: the beam centres on the ground, which move with the satellite; on cells
    that do not move (terrestrial sites) the event is Event D1 (5.5.4.15).  TS 38.331 (CondReconfigToAddMod)
    has the network configure a second event (A3, A4 or A5) together with D1 or D2; here the execution needs both
    the D2 state and the A3 condition of :class:`CHO` (``o_exec_db``), held together for ``ttt_exec_s`` (one
    time-to-trigger for both events, a simplification).  Distances use the UE's reported position.

    d_thresh1_m  distanceThreshFromReference1 [m] (serving cell); default: half the 50 km nadir beam diameter of
                 the LEO-600 S-band beams of TR 38.821 Table 6.1.1.1-1 (TS 38.331 gives no default)
    d_thresh2_m  distanceThreshFromReference2 [m] (candidate); the same default
    hys_m        hysteresisLocation [m]
    Other parameters as :class:`CHO`.
    """
    exec_condition_used = True

    def __init__(self, d_thresh1_m: float = 25000.0, d_thresh2_m: float = 25000.0, hys_m: float = 1000.0,
                 o_prep_db: float = -2.0, o_exec_db: float = 0.0, ttt_exec_s: float = 0.08, ttt_prep_s: float = 0.0,
                 n_max: int = 4, rel_hys_db: float = 3.0, name: str = "CHO-D2"):
        super().__init__(o_prep_db, o_exec_db, ttt_exec_s, ttt_prep_s, n_max, rel_hys_db, False, name)
        if d_thresh1_m < 0 or d_thresh2_m < 0 or hys_m < 0:
            raise ValueError("distance thresholds and hysteresis must be >= 0")
        self.d_thresh1_m, self.d_thresh2_m, self.hys_m = float(d_thresh1_m), float(d_thresh2_m), float(hys_m)

    def params(self):
        p = super().params()
        p.pop("immediate")
        p.update(d_thresh1_m=self.d_thresh1_m, d_thresh2_m=self.d_thresh2_m, hys_m=self.hys_m)
        return p

    def reset(self, ctx):
        super().reset(ctx)
        self.d_on = np.zeros((ctx.n_users, ctx.n_sites), dtype=bool)

    def exec_condition(self, obs):
        ref = self.ctx.cell_center(obs.t) if self.ctx.cell_center is not None else self.ctx.sites
        d = np.hypot(obs.x[:, None] - ref[None, :, 0], obs.y[:, None] - ref[None, :, 1])      # (U, M)
        ml1 = d[np.arange(len(obs.serving)), obs.serving][:, None]
        enter = (ml1 - self.hys_m > self.d_thresh1_m) & (d + self.hys_m < self.d_thresh2_m)
        leave = (ml1 + self.hys_m < self.d_thresh1_m) | (d - self.hys_m > self.d_thresh2_m)
        self.d_on = (self.d_on | enter) & ~leave
        return self.d_on


class BanditA3(BaselineRule):
    """Event A3 whose offset each cell learns with an epsilon-greedy bandit (a learning-based example).

    Trigger: Event A3 (TS 38.331 clause 5.5.4.4) with the offset of the arm
    that the serving cell plays and a fixed time-to-trigger.  The rewards
    follow the outcome classes of mobility robustness optimisation (TS 38.300
    clause 15.5.2: too-late, too-early and wrong-cell handovers) plus
    unnecessary handovers: useful ``+1``, unnecessary ``-w_unnecessary``,
    early or late ``-w_failure``; a link failure without a handover counts as
    late for the source cell.

    Every cell plays one arm (an A3 offset of ``arms_db``) for ``epoch``
    outcomes of handovers from it, then updates the mean reward of that arm
    and picks the next arm: with probability ``epsilon`` at random (from
    ``ctx.rng``), otherwise an arm not yet played or the best one.  An
    outcome reaches the arm that its source cell plays when the outcome is
    known, so an arm change can credit a few outcomes to the next arm.  No
    dependency beyond NumPy; the learned values are kept per run.

    arms_db        candidate A3 offsets [dB]
    ttt_s          time-to-trigger [s]
    epsilon        exploration probability
    epoch          outcomes per evaluation of an arm
    w_unnecessary  penalty of an unnecessary handover
    w_failure      penalty of an early or late handover or a link failure

    With a single arm the rule is :class:`A3` with that offset.

    Since 1.11.0 the rule keeps a record of what it learned (it does not change
    any decision): ``outcomes`` lists ``(t, cell, arm, reward)`` of every credited
    outcome and ``epochs`` lists ``(t, cell, arm)`` of every finished epoch.
    """
    learns = True

    def __init__(self, arms_db=(1.0, 2.0, 3.0, 4.0, 5.0), ttt_s: float = 0.16, epsilon: float = 0.1,
                 epoch: int = 10, w_unnecessary: float = 1.0, w_failure: float = 2.0, name: str = "A3-bandit"):
        super().__init__(name)
        arms = [float(a) for a in arms_db]
        if not arms:
            raise ValueError("arms_db needs at least one offset")
        if not 0.0 <= epsilon <= 1.0 or int(epoch) < 1 or ttt_s < 0:
            raise ValueError("epsilon must be in [0, 1], epoch >= 1 and ttt_s >= 0")
        self.arms_db, self.ttt_s, self.epsilon, self.epoch = arms, float(ttt_s), float(epsilon), int(epoch)
        self.w_unnecessary, self.w_failure = float(w_unnecessary), float(w_failure)

    def params(self):
        return dict(arms_db=list(self.arms_db), ttt_s=self.ttt_s, epsilon=self.epsilon, epoch=self.epoch,
                    w_unnecessary=self.w_unnecessary, w_failure=self.w_failure)

    def reset(self, ctx):
        super().reset(ctx)
        M, K = ctx.n_sites, len(self.arms_db)
        self._arms = np.asarray(self.arms_db)
        self.value = np.zeros((M, K))              # mean reward of every arm of every cell
        self.plays = np.zeros((M, K), dtype=int)   # evaluated epochs
        self.arm = np.zeros(M, dtype=int)          # arm played now (first arm first)
        self._sum = np.zeros(M)
        self._n = np.zeros(M, dtype=int)
        self.outcomes, self.epochs = [], []
        self._t = 0.0

    def reward(self, label: int) -> float:
        """Reward of an outcome label."""
        if label == USEFUL:
            return 1.0
        if label == UNNECESSARY:
            return -self.w_unnecessary
        if label in (EARLY, LATE):
            return -self.w_failure
        return 0.0

    def _credit(self, cell: int, r: float) -> None:
        self.outcomes.append((self._t, int(cell), int(self.arm[cell]), float(r)))
        self._sum[cell] += r
        self._n[cell] += 1
        if self._n[cell] < self.epoch:
            return
        a = self.arm[cell]
        self.epochs.append((self._t, int(cell), int(a)))
        self.plays[cell, a] += 1
        self.value[cell, a] += (self._sum[cell] / self._n[cell] - self.value[cell, a]) / self.plays[cell, a]
        self._sum[cell], self._n[cell] = 0.0, 0
        self.arm[cell] = self.choose(cell)

    def choose(self, cell: int) -> int:
        """Next arm of ``cell``: random with probability epsilon, else an unplayed or the best arm."""
        K = len(self._arms)
        if K > 1 and self.ctx.rng.random() < self.epsilon:
            return int(self.ctx.rng.integers(K))
        unplayed = np.flatnonzero(self.plays[cell] == 0)
        if len(unplayed):
            return int(unplayed[0])
        return int(np.argmax(self.value[cell]))

    def a3_offsets(self, obs):
        off = self._arms[self.arm[obs.serving]]
        return np.repeat(off[:, None], self.ctx.n_sites, axis=1)

    def time_to_trigger(self, obs):
        return self.ttt_s

    def on_outcome(self, rec):
        self._t = getattr(rec, "t", self._t)            # records built by hand may have no time
        self._credit(rec.source, self.reward(rec.label))

    def on_link_failure(self, rec):
        self._t = getattr(rec, "t", self._t)            # records built by hand may have no time
        self._credit(rec.source, -self.w_failure)


class A3A5(BaselineRule):
    """Event A3 within a carrier and Event A5 towards other carriers (multi-carrier model; since 1.10.0).

    Trigger towards a cell on the serving carrier: Event A3 (TS 38.331 clause 5.5.4.4), neighbour
    better than the serving cell by ``off_db`` for ``ttt_s``.  Trigger towards a cell on another
    carrier: Event A5 (clause 5.5.4.6), entering conditions A5-1 ``Mp + Hys < Thresh1`` and A5-2
    ``Mn + Ofn + Ocn - Hys > Thresh2`` (Ofn = Ocn = 0) held for ``a5_ttt_s``; Mp and Mn are the
    L3-filtered SS-RSRP per resource element [dBm] of the multi-carrier model.  The thresholds
    apply towards a carrier of higher frequency; ``a5_down_thresh1_dbm`` / ``a5_down_thresh2_dbm``
    (unset: the same) towards a lower one, as a network configures A5 per measurement object.
    ``a3_inter`` also applies A3 towards the other carriers.  Report, preparation and command as
    :class:`A3`.  On one carrier the rule is :class:`A3`.

    off_db          A3 offset [dB]
    ttt_s           A3 time-to-trigger [s]
    a5_thresh1_dbm  a5-Threshold1 (serving) [dBm]
    a5_thresh2_dbm  a5-Threshold2 (neighbour) [dBm]
    a5_hys_db       hysteresis of the A5 event [dB]
    a5_ttt_s        A5 time-to-trigger [s]
    a3_inter        A3 also towards cells of other carriers
    a5_down_thresh1_dbm, a5_down_thresh2_dbm  A5 thresholds towards a lower carrier (unset: as above)
    """

    def __init__(self, off_db: float = 3.0, ttt_s: float = 0.16, a5_thresh1_dbm: float = -110.0,
                 a5_thresh2_dbm: float = -105.0, a5_hys_db: float = 1.0, a5_ttt_s: float = 0.32,
                 a3_inter: bool = False, a5_down_thresh1_dbm=None, a5_down_thresh2_dbm=None, name: str = "A3A5"):
        super().__init__(name)
        if ttt_s < 0 or a5_ttt_s < 0 or a5_hys_db < 0:
            raise ValueError("ttt_s, a5_ttt_s and a5_hys_db must be >= 0")
        self.off_db, self.ttt_s = float(off_db), float(ttt_s)
        self.a5_thresh1_dbm, self.a5_thresh2_dbm = float(a5_thresh1_dbm), float(a5_thresh2_dbm)
        self.a5_hys_db, self.a5_ttt_s, self.a3_inter = float(a5_hys_db), float(a5_ttt_s), bool(a3_inter)
        self.a5_down_thresh1_dbm = self.a5_thresh1_dbm if a5_down_thresh1_dbm is None else float(a5_down_thresh1_dbm)
        self.a5_down_thresh2_dbm = self.a5_thresh2_dbm if a5_down_thresh2_dbm is None else float(a5_down_thresh2_dbm)

    def params(self):
        return dict(off_db=self.off_db, ttt_s=self.ttt_s, a5_thresh1_dbm=self.a5_thresh1_dbm,
                    a5_thresh2_dbm=self.a5_thresh2_dbm, a5_hys_db=self.a5_hys_db, a5_ttt_s=self.a5_ttt_s,
                    a3_inter=self.a3_inter, a5_down_thresh1_dbm=self.a5_down_thresh1_dbm,
                    a5_down_thresh2_dbm=self.a5_down_thresh2_dbm)

    def _inter(self, obs):
        car = self.ctx.cell_carrier
        if car is None:
            return None
        return car[None, :] != car[obs.serving][:, None]

    def a3_offsets(self, obs):
        return self.off_db

    def time_to_trigger(self, obs):
        inter = self._inter(obs)
        if inter is None or not inter.any():
            return self.ttt_s
        return np.where(inter, self.a5_ttt_s, self.ttt_s)

    def entering(self, obs, offsets):
        inter = self._inter(obs)
        if inter is None:
            return None
        car = self.ctx.cell_carrier
        down = car[None, :] < car[obs.serving][:, None]          # carriers are numbered by frequency
        th1 = np.where(down, self.a5_down_thresh1_dbm, self.a5_thresh1_dbm)
        th2 = np.where(down, self.a5_down_thresh2_dbm, self.a5_thresh2_dbm)
        mp = obs.meas_dbm[np.arange(len(obs.serving)), obs.serving]
        a3 = obs.gap_db > self.off_db
        a5 = (mp[:, None] + self.a5_hys_db < th1) & (obs.meas_dbm - self.a5_hys_db > th2)
        cond = np.where(inter, a5 | (a3 & self.a3_inter), a3)
        score = np.where(inter, obs.meas_dbm - th2, obs.gap_db - self.off_db)
        return cond, score
