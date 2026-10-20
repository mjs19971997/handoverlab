# SPDX-License-Identifier: MIT
"""Measurement chain and event conditions.

* Layer-3 filter of TS 38.331 clause 5.5.3.2: ``F_n = (1 - a) F_{n-1} + a M_n``
  with ``a = 1 / 2^(k/4)``.  The coefficient is defined for a 200 ms sample
  period; for another L1 period the coefficient is rescaled so that the
  filter keeps the same time constant.
* Event A3 (neighbour becomes offset better than serving) with time-to-trigger.
* Conditional handover: entry timers of the execution condition and the
  choice of the prepared set.

All functions work on arrays of users x cells and are pure, so they can be
tested in isolation; the engine calls them at every measurement instant.
"""
from __future__ import annotations

import numpy as np

EPS = 1e-9
INF = np.inf


# ---------------------------------------------------------------------------
# layer-3 filter
# ---------------------------------------------------------------------------
def l3_coefficient(k: int, sample_period_s: float, ref_period_s: float = 0.2) -> float:
    """Filter coefficient ``a`` for samples every ``sample_period_s``.

    TS 38.331 gives ``a = 1/2^(k/4)`` for the reference period of 200 ms; the
    returned value gives the same decay per unit of time at another period.
    """
    a_ref = 0.5 ** (k / 4.0)
    return 1.0 - (1.0 - a_ref) ** (sample_period_s / ref_period_s)


class L3Filter:
    """Exponential layer-3 filter over arrays of samples (in dB).

    The first sample initialises the filter (TS 38.331: F_0 = M_1).
    """

    def __init__(self, k: int = 4, sample_period_s: float = 0.04):
        self.a = l3_coefficient(k, sample_period_s)
        self.value = None

    def reset(self, first_sample) -> np.ndarray:
        self.value = np.array(first_sample, dtype=float, copy=True)
        return self.value

    def update(self, sample) -> np.ndarray:
        if self.value is None:
            return self.reset(sample)
        self.value += self.a * (sample - self.value)
        return self.value


# ---------------------------------------------------------------------------
# entry conditions and timers
# ---------------------------------------------------------------------------
def a3_condition(gap_db: np.ndarray, offset_db, serving: np.ndarray, connected: np.ndarray) -> np.ndarray:
    """Event A3 entering condition per user and neighbour.

    ``gap_db`` (U, M): filtered neighbour minus serving measurement; ``offset_db``
    scalar or (U, M).  The serving cell and users that are not connected never
    fulfil the condition.
    """
    cond = gap_db > offset_db
    cond[np.arange(len(serving)), serving] = False
    cond &= connected[:, None]
    return cond


def update_entry_times(entry: np.ndarray, cond: np.ndarray, t: float) -> np.ndarray:
    """Time since which each condition has held without interruption (inf where it does not hold)."""
    return np.where(cond, np.minimum(entry, t), INF)


def ttt_expires_before(entry: np.ndarray, ttt_s, t: float, period_s: float) -> np.ndarray:
    """True where the time-to-trigger expires before the next measurement instant.

    A condition that held at every measurement since ``entry`` is reported at
    ``entry + ttt`` even if that falls between two measurement instants.
    ``ttt_s`` is a scalar, one value per user (U,) or (since 1.10.0) one per user and cell (U, M).
    """
    ttt = np.asarray(ttt_s, dtype=float)
    if ttt.ndim == 1:
        ttt = ttt[:, None]
    return (entry + ttt) < t + period_s - EPS


def held_for(entry: np.ndarray, t: float, ttt_s: float) -> np.ndarray:
    """True where a condition has held for at least ``ttt_s`` (checked at a measurement)."""
    return (t - entry) >= ttt_s - EPS


def select_prepared_set(score: np.ndarray, reported: np.ndarray, have: np.ndarray, active: np.ndarray,
                        serving: np.ndarray, n_max: int, release_hys_db: float, stick_db: float) -> np.ndarray:
    """Cells the network wants prepared for each user (conditional handover).

    ``score`` (U, M) is the measured advantage minus the preparation offset.
    A reported cell becomes eligible at ``score >= 0``; a cell that is already
    prepared or being prepared (``have``) stays eligible down to
    ``-release_hys_db``.  Among the eligible cells the ``n_max`` best by score
    are kept, with a bonus ``stick_db`` for cells already held.  Only users in
    ``active`` are evaluated.
    """
    elig = (reported & (score >= 0.0)) | (have & (score >= -release_hys_db))
    elig &= active[:, None]
    elig[np.arange(len(serving)), serving] = False
    rank = np.where(elig, score + np.where(have, stick_db, 0.0), -INF)
    M = score.shape[1]
    if n_max < M:
        kth = np.partition(rank, M - n_max, axis=1)[:, M - n_max]
        return elig & (rank >= kth[:, None])
    return elig
