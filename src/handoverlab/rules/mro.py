# SPDX-License-Identifier: MIT
"""Event A3 with mobility robustness optimisation (MRO), available since version 1.7.0.

MRO is the self-organising-network function that tunes handover parameters
from the observed outcomes of handovers (TS 38.300 clause 15.5.2; SON for 5G in TS 28.313
clause 7.1.2; the SON concepts of TS 32.500).  The rule ``a3_mro`` keeps one cell individual
offset (CIO) for every pair of serving and neighbour cell and moves it in fixed
steps once per time window, as counter-based MRO schemes do: towards an
earlier handover when too-late handovers dominate the window, towards a later
one when too-early, wrong-cell and ping-pong handovers dominate.

Assumptions, made explicit:

* The three failure classes are those of TS 38.300 clause 15.5.2, taken from
  the outcome labels that HandoverLab feeds to learning rules: a late handover
  and a link failure without a handover after which the UE re-establishes in a
  neighbour count as too late for (source, cell); a too-early and a
  wrong-cell handover count as too early for (source, target).
* A ping-pong is a return to the previous cell within ``pingpong_s`` (default:
  ``protocol.pingpong_s`` of the scenario); the rule sees it in the serving
  cell of the user, as a network sees it in the cell history of the UE, and
  counts it as too early for the pair of the first handover.  The wider
  HandoverLab label *unnecessary* (short stay or low gain) is not an MRO
  counter; ``count_unnecessary`` adds it as too early (a ping-pong then counts
  twice).
* The update is deterministic: at the first measurement instant at or after
  the end of a window, every pair with at least ``min_events`` counted
  outcomes moves by ``step_db`` in the direction of the larger count (no move
  on a tie), the offset stays in ``[min_db, max_db]``, and all counts restart.
* The offset is added to the A3 offset of the pair (positive: later handover),
  as a CIO enters the A3 condition of TS 38.331 clause 5.5.4.4.  Offsets are
  kept per run; the time-to-trigger is not tuned.

With ``step_db = 0`` the rule is :class:`~handoverlab.rules.builtin.A3` with
``off_db`` and ``ttt_s``.
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np

from .base import EARLY, LATE, UNNECESSARY, BaselineRule


class MROA3(BaselineRule):
    """Event A3 whose offset per cell pair is tuned by mobility robustness optimisation.

    off_db             A3 offset before any tuning [dB]
    ttt_s              time-to-trigger [s]
    step_db            change of a pair's offset per window [dB]; 1 dB by default (since 2.1.0; 0.5 before), so
                       that every offset is a value of Q-OffsetRange (TS 38.331 V18.11.0: whole dB from -5 to 5,
                       steps of 2 dB beyond 6 dB); :func:`handoverlab.standard.check_rule` checks a setting
    window_s           length of a counting window [s]
    min_db, max_db     bounds of a pair's offset [dB]; -4 and 4 by default, within Q-OffsetRange (TS 38.331:
                       -24 to 24 dB) and the handover-trigger deviation of MRO (TS 28.313 Table 7.1.2.2.3-1:
                       -20 to 20 in 0.5 dB, i.e. +-10 dB)
    min_events         counted outcomes a pair needs in a window before its offset moves
    count_pingpong     count a return to the previous cell within ``pingpong_s`` as too early
    pingpong_s         ping-pong time [s]; None: ``protocol.pingpong_s`` of the scenario
    count_unnecessary  also count every unnecessary handover as too early
    """
    learns = True

    def __init__(self, off_db: float = 3.0, ttt_s: float = 0.16, step_db: float = 1.0, window_s: float = 10.0,
                 min_db: float = -4.0, max_db: float = 4.0, min_events: int = 1, count_pingpong: bool = True,
                 pingpong_s: Optional[float] = None, count_unnecessary: bool = False, name: str = "A3-MRO"):
        super().__init__(name)
        if ttt_s < 0 or step_db < 0 or window_s <= 0 or int(min_events) < 1 or not min_db <= 0.0 <= max_db:
            raise ValueError("need ttt_s >= 0, step_db >= 0, window_s > 0, min_events >= 1 and min_db <= 0 <= max_db")
        if pingpong_s is not None and pingpong_s <= 0:
            raise ValueError("pingpong_s must be positive or None")
        self.off_db, self.ttt_s, self.step_db, self.window_s = float(off_db), float(ttt_s), float(step_db), \
            float(window_s)
        self.min_db, self.max_db, self.min_events = float(min_db), float(max_db), int(min_events)
        self.count_pingpong = bool(count_pingpong)
        self.pingpong_s = None if pingpong_s is None else float(pingpong_s)
        self.count_unnecessary = bool(count_unnecessary)

    def params(self):
        return dict(off_db=self.off_db, ttt_s=self.ttt_s, step_db=self.step_db, window_s=self.window_s,
                    min_db=self.min_db, max_db=self.max_db, min_events=self.min_events,
                    count_pingpong=self.count_pingpong, pingpong_s=self.pingpong_s,
                    count_unnecessary=self.count_unnecessary)

    def reset(self, ctx):
        super().reset(ctx)
        M = ctx.n_sites
        self.cio = np.zeros((M, M))                    # offset of every (serving, neighbour) pair [dB]
        self.late = np.zeros((M, M), dtype=int)        # counts of the current window
        self.early = np.zeros((M, M), dtype=int)
        self.next_update = self.window_s
        self.n_updates = 0
        self.n_pingpong = 0
        sc = getattr(ctx, "scenario", None)
        self._pp_s = self.pingpong_s if self.pingpong_s is not None else (
            sc.protocol.pingpong_s if sc is not None else 1.0)
        # a ping-pong is a return within the time (TR 36.839 Definition 5, as the engine: strictly shorter;
        # since 2.1.0, 2.0.0: up to and including it)
        self._pp_strict = sc is None or getattr(sc.protocol, "rrc_detail", "3gpp") == "3gpp"
        self._last = None                              # serving cell, previous cell and time of the last change

    def update(self) -> None:
        """Close a window: move the offsets of the pairs with enough outcomes, restart the counts."""
        n = self.late + self.early
        act = n >= self.min_events
        move = np.where(act & (self.late > self.early), -self.step_db,
                        np.where(act & (self.early > self.late), self.step_db, 0.0))
        np.clip(self.cio + move, self.min_db, self.max_db, out=self.cio)
        self.late[...] = 0
        self.early[...] = 0
        self.n_updates += 1

    def _watch_pingpong(self, obs) -> None:
        s = np.asarray(obs.serving)
        if self._last is None:
            self._last, self._prev = s.copy(), np.full(len(s), -1)
            self._t_change = np.full(len(s), -np.inf)
            return
        for u in np.flatnonzero(s != self._last):
            dt = obs.t - self._t_change[u]
            if s[u] == self._prev[u] and (dt < self._pp_s if self._pp_strict else dt <= self._pp_s):
                self.early[s[u], self._last[u]] += 1   # the first handover, back cell -> left cell, was too early
                self.n_pingpong += 1
            self._prev[u], self._last[u], self._t_change[u] = self._last[u], s[u], obs.t

    def a3_offsets(self, obs):
        if self.count_pingpong:
            self._watch_pingpong(obs)
        if obs.t >= self.next_update:
            self.update()
            self.next_update = (math.floor(obs.t / self.window_s) + 1) * self.window_s
        return self.off_db + self.cio[obs.serving]

    def time_to_trigger(self, obs):
        return self.ttt_s

    def on_outcome(self, rec):
        if rec.label == LATE:
            self.late[rec.source, rec.target] += 1
        elif rec.label == EARLY or (rec.label == UNNECESSARY and self.count_unnecessary):
            self.early[rec.source, rec.target] += 1

    def on_link_failure(self, rec):
        self.late[rec.source, rec.cell] += 1
