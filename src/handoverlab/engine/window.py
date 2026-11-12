# SPDX-License-Identifier: MIT
"""Moving means over the last evaluation period (since 2.12.0).

TS 38.133 8.1.2.2 (radio link monitoring) and 8.5.2.2 (beam failure detection) ask whether the link quality
"estimated over the last" T_Evaluate period becomes worse than the threshold within that period.  The models up to
2.11 use an exponential filter with the time constant T_Evaluate, which never forgets: after a drop of 20-30 dB it
needs several time constants to cross the threshold.  :class:`WindowMean` keeps the samples of the last ``n`` steps
and gives their mean, so a quality that has stayed below the threshold for a whole period is below it.

Used by ``protocol.rlm_filter: window`` (the Qout and Qin qualities of radio link monitoring) and
``radio.beams.bfd_filter: window`` (the beam failure detection quality of every SSB beam of the serving cell).
"""
from __future__ import annotations

import numpy as np


class WindowMean:
    """Means of the last ``n[u]`` samples of every user ``u`` (and of every trailing index, e.g. a beam).

    ``n`` (U,) is the window of every user in samples, at most ``n_max``.  :meth:`push` adds one sample per user
    (shape ``(U,) + tail``; with ``mask`` only for those users) and returns the means over the samples since the
    user's last :meth:`reset`, at most the last ``n[u]``.  :attr:`count` (U,) is the number of samples in the
    window.  Running sums, recomputed exactly every 1024 samples of a user.
    """

    def __init__(self, n, n_max: int, tail=()):
        n = np.asarray(n, dtype=np.int64)
        self.U = n.shape[0]
        self.n = n.copy()
        self.n_max = int(max(n_max, int(n.max()) if n.size else 1, 1))
        self.tail = tuple(tail)
        self.buf = np.zeros((self.n_max, self.U) + self.tail)
        self.sum = np.zeros((self.U,) + self.tail)
        self.count = np.zeros(self.U, dtype=np.int64)
        self.pos = np.zeros(self.U, dtype=np.int64)
        self._ar = np.arange(self.U)
        self._ones = (1,) * len(self.tail)

    def set_n(self, u, n) -> None:
        """New window of user ``u`` (``n`` samples, at most :attr:`n_max`); the user's window is reset."""
        self.n[u] = min(max(int(n), 1), self.n_max)
        self.reset(u)

    def reset(self, u) -> None:
        """Forget the samples of user(s) ``u``: the next mean is the next sample alone."""
        self.sum[u] = 0.0
        self.count[u] = 0

    def full(self, u) -> bool:
        """True when user ``u`` has a whole window of samples."""
        return bool(self.count[u] >= self.n[u])

    def push(self, x, mask=None) -> np.ndarray:
        """Add the samples ``x`` (U,) + tail (of the users in ``mask``, default all) and return the means of every
        user's window (U,) + tail; a user outside ``mask`` keeps its window."""
        x = np.asarray(x, dtype=float)
        u = self._ar if mask is None else np.nonzero(mask)[0]
        if len(u):
            n, pos = self.n[u], self.pos[u]
            full = (self.count[u] >= n).reshape((len(u),) + self._ones)
            old = self.buf[(pos - n) % self.n_max, u]
            self.sum[u] += x[u] - np.where(full, old, 0.0)
            self.buf[pos % self.n_max, u] = x[u]
            self.count[u] = np.minimum(self.count[u] + 1, n)
            self.pos[u] = pos + 1
            r = u[self.pos[u] % 1024 == 0]
            if len(r):
                self._resum(r)
        return self.sum / np.maximum(self.count, 1).reshape((self.U,) + self._ones)

    def _resum(self, u) -> None:
        j = np.arange(self.n_max)
        idx = (self.pos[u][None, :] - 1 - j[:, None]) % self.n_max                  # (n_max, len(u)), newest first
        vals = self.buf[idx, u[None, :]]
        take = (j[:, None] < self.count[u][None, :]).reshape(idx.shape + self._ones)
        self.sum[u] = np.where(take, vals, 0.0).sum(0)
