# SPDX-License-Identifier: MIT
"""Built-in rules.

``A3``        Event A3 baseline handover
``CHO``       Rel-16 conditional handover with fixed offsets
``DAPS``      Rel-16 DAPS handover triggered by Event A3 (since 1.0.0rc2)
``LTM``       Rel-18 L1/L2-triggered mobility with fixed offsets (since 1.0.0rc2)
``BanditA3``  Event A3 whose offset is learned per cell by an epsilon-greedy bandit (since 1.0.0rc2)
"""
from __future__ import annotations

import numpy as np

from .base import (EARLY, LATE, MAX_CONDITIONAL_CELLS, UNNECESSARY, USEFUL, BaselineRule, ConditionalRule, DAPSRule,
                   LTMRule)


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
        self._sum[cell] += r
        self._n[cell] += 1
        if self._n[cell] < self.epoch:
            return
        a = self.arm[cell]
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
        self._credit(rec.source, self.reward(rec.label))

    def on_link_failure(self, rec):
        self._credit(rec.source, -self.w_failure)
