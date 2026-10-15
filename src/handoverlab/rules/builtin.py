# SPDX-License-Identifier: MIT
"""Built-in rules: Event A3 baseline handover and Rel-16 conditional handover."""
from __future__ import annotations

import numpy as np

from .base import MAX_CONDITIONAL_CELLS, BaselineRule, ConditionalRule


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
