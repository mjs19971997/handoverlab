# SPDX-License-Identifier: MIT
"""Optional compiled kernel of the step loop (``run.backend: numba``; since 1.11.0).

One pass over the engines and users of a step does what the NumPy path of
:meth:`Engine.advance` and :meth:`EngineBatch.advance` does in about fifteen
array operations: the serving SINR, the Qout / Qin filters, the start of T310,
its stop and its expiry, for the radio-link monitoring with N310 = N311 = 1 and
without the monitoring load option.  Every value is computed with the same
operations in the same order as in NumPy (no fast-math, element by element),
so the results are bit-identical; the golden fingerprints are checked with both
backends.  The interference sums (matrix products) and the logarithms stay in
NumPy: their summation order and vectorised functions are not reproduced
bit for bit by a loop.

Numba is optional (``pip install handoverlab[fast]``); without it the kernel is
not available and ``run.backend: numba`` is refused when the scenario is checked.
"""
from __future__ import annotations

try:                                                          # optional dependency
    import numba
except ImportError:                                           # pragma: no cover - depends on the installation
    numba = None


def available() -> bool:
    """True if Numba can be imported."""
    return numba is not None


def _rlm_step(ln, tot, rcs, serv, state, qo, qi, run, t310, k310, rlm_t0, sinr, exp,
              t, k, noise, ao, ai, qout, qin, t310_lim, holdoff, eps, connected, std, ind):
    """Serving SINR, Qout / Qin filters and T310 of every engine (rows) and user (columns) for one step.

    Writes ``sinr``, ``qo``, ``qi``, ``run``, ``t310``, ``k310`` and ``exp`` (T310 expired) in place and
    returns the number of expiries.  ``std`` (since 2.1.0): out-of-sync / in-sync indications only at the
    indication instants (``ind``) and not both on one instant, as ``core.rlm_indications`` with N310 = N311 = 1.
    """
    K, U = tot.shape
    n_exp = 0
    for j in range(K):
        for u in range(U):
            ls = ln[u, serv[j, u]]
            s = ls / (tot[j, u] - rcs[j, u] * ls + noise)
            sinr[j, u] = s
            o = qo[j, u] + ao * (s - qo[j, u])
            qo[j, u] = o
            i = qi[j, u] + ai * (s - qi[j, u])
            qi[j, u] = i
            con = state[j, u] == connected
            r = run[j, u]
            if std:
                if ind and con:
                    oos = o < qout and t >= rlm_t0[j, u] - eps
                    ins = i > qin
                    if oos and not ins and not r:              # N310 = 1 reached
                        r = True
                        t310[j, u] = t
                        k310[j, u] = k
                    elif r and ins and not oos:                # N311 = 1 reached
                        r = False
            else:
                if o < qout and con and not r:
                    if holdoff <= 0.0 or t >= rlm_t0[j, u] - eps:
                        r = True
                        t310[j, u] = t
                        k310[j, u] = k
                if r and i > qin:
                    r = False
            run[j, u] = r
            e = r and con and (t - t310[j, u] >= t310_lim)
            exp[j, u] = e
            if e:
                n_exp += 1
    return n_exp


rlm_step = numba.njit(cache=True, fastmath=False, nogil=True)(_rlm_step) if numba is not None else None
