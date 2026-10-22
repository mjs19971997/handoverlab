# SPDX-License-Identifier: MIT
"""Optional compiled kernels (``run.backend: numba``): the step loop (since 1.11.0) and the slot scheduler
(since 2.4.0, :func:`sched_slots`; see :mod:`handoverlab.engine.scheduler`).

Step loop: one pass over the engines and users of a step does what the NumPy path of
:meth:`Engine.advance` and :meth:`EngineBatch.advance` does in about fifteen
array operations: the serving SINR, the Qout / Qin filters, the start of T310,
its stop and its expiry, for the radio-link monitoring with N310 = N311 = 1 and
without the monitoring load option.  Every value is computed with the same
operations in the same order as in NumPy (no fast-math, element by element),
so the results are bit-identical; the golden fingerprints are checked with both
backends.  The interference sums (matrix products) and the logarithms stay in
NumPy: their summation order and vectorised functions are not reproduced
bit for bit by a loop.

Slot scheduler: the slots of a measurement interval in one loop; the logarithms
and block error probabilities are computed by the NumPy functions of the
reference into tables that the loop reads, so the results are bit-identical too.

Numba is optional (``pip install handoverlab[fast]``); without it the kernels are
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


def _sched_slots(s0, k0, pf, a_pf, max_tx, rtt, con, serv, prb_cell, first_slot, sinr, draws, left, got, used,
                 lost_bits, avg, h_bits, h_data, h_sinr, h_tx, h_due, h_mcs, h_ncb, h_p, sel, p_tab, req, stats,
                 want, has_re, nprb, rate_slot, metric, best, cnt, rank):
    """Slots ``s0`` .. of one interval of :meth:`SlotScheduler.serve` (since 2.4.0).

    Plays the slots as the NumPy body of ``serve`` does, with only additions, multiplications, divisions,
    minima and comparisons in the same order; every block error probability comes from the tables that
    the caller fills with the NumPy functions: ``sel[u, n]`` = (MCS, TBS, coded bits) for ``n`` PRBs
    (MCS -2: not yet looked up), ``p_tab[u, n, k]`` = BLER of transmission ``k`` of a new TB, ``h_p[u, h, k]``
    = BLER of transmission ``k`` of the TB in process ``h``.  If a slot needs an entry that is not there
    yet, the slot is left untouched, ``req[u]`` gets the PRBs to look up and the slot index is returned;
    -1 when the interval is done.  Updates the state arrays in place; ``stats`` = (tb, tb_ok, tb_lost, retx).
    """
    U = con.shape[0]
    M = prb_cell.shape[0]
    H = h_bits.shape[1]
    for s in range(s0, draws.shape[0]):
        k = k0 + s
        any_want = False
        for u in range(U):
            re = False
            free = False
            for h in range(H):
                if h_bits[u, h] > 0:
                    if h_due[u, h] <= k:
                        re = True
                else:
                    free = True
            has_re[u] = re
            w = con[u] and (re or (left[u] > 0 and free)) and prb_cell[serv[u]] > 0 and first_slot[u] <= s
            want[u] = w
            nprb[u] = 0
            rate_slot[u] = 0.0
            if w:
                any_want = True
        if not any_want:
            continue
        need = False
        if pf:                           # per cell: a due retransmission (lowest user), else the best metric
            for c in range(M):
                best[c] = -1
            for u in range(U):
                if not want[u]:
                    continue
                if not has_re[u]:
                    n = prb_cell[serv[u]]
                    if sel[u, n, 0] == -2:
                        req[u] = n
                        need = True
                        continue
                    metric[u] = sel[u, n, 1] / max(avg[u], 1e-9)
                c = serv[u]
                b = best[c]
                if b < 0 or (has_re[u] and not has_re[b]) or (not has_re[u] and not has_re[b]
                                                              and metric[u] > metric[b]):
                    best[c] = u
            if need:
                return s
            for c in range(M):
                if best[c] >= 0:
                    nprb[best[c]] = prb_cell[c]
        else:                            # equal shares; per cell the retransmissions first, then by user
            for c in range(M):
                cnt[c] = 0
                rank[c] = 0
            for u in range(U):
                if want[u]:
                    cnt[serv[u]] += 1
            for second in range(2):
                for u in range(U):
                    if want[u] and has_re[u] == (second == 0):
                        c = serv[u]
                        q = max(cnt[c], 1)
                        nprb[u] = prb_cell[c] // q + (1 if rank[c] < prb_cell[c] % q else 0)
                        rank[c] += 1
        any_srv = False
        for u in range(U):                                      # tables complete before any state changes
            if nprb[u] > 0:
                any_srv = True
                if not has_re[u]:
                    n = nprb[u]
                    if sel[u, n, 0] == -2 or (sel[u, n, 0] >= 0 and p_tab[u, n, 1] != p_tab[u, n, 1]):
                        req[u] = n
                        need = True
        if need:
            return s
        if not any_srv:
            continue
        for u in range(U):                                      # retransmissions (oldest due process)
            if nprb[u] == 0 or not has_re[u]:
                continue
            h = -1
            for j in range(H):
                if h_bits[u, j] > 0 and h_due[u, j] <= k and (h < 0 or h_due[u, j] < h_due[u, h]):
                    h = j
            h_sinr[u, h] += sinr[u]
            h_tx[u, h] += 1
            stats[3] += 1
            ok = draws[s, u] >= h_p[u, h, h_tx[u, h]]
            lost = not ok and h_tx[u, h] >= max_tx
            if ok:
                got[u] += h_data[u, h]
                rate_slot[u] = h_data[u, h]
                stats[1] += 1
            if lost:
                lost_bits[u] += h_data[u, h]
                stats[2] += 1
            if ok or lost:
                h_bits[u, h] = 0
            else:
                h_due[u, h] = k + rtt
            used[serv[u]] += nprb[u]
        for u in range(U):                                      # new transport blocks
            if nprb[u] == 0 or has_re[u]:
                continue
            n = nprb[u]
            m = sel[u, n, 0]
            if m < 0:
                continue
            h = 0
            while h < H - 1 and h_bits[u, h] != 0:         # first free process (always one: see ``want``)
                h += 1
            t = sel[u, n, 1]
            data = min(float(t), left[u])
            left[u] -= data
            stats[0] += 1
            h_bits[u, h] = t
            h_data[u, h] = data
            h_sinr[u, h] = sinr[u]
            h_tx[u, h] = 1
            h_mcs[u, h] = m
            h_ncb[u, h] = sel[u, n, 2]
            for j in range(p_tab.shape[2]):
                h_p[u, h, j] = p_tab[u, n, j]
            ok = draws[s, u] >= p_tab[u, n, 1]
            lost = not ok and max_tx <= 1
            if ok:
                got[u] += data
                rate_slot[u] = data
                stats[1] += 1
            if lost:
                lost_bits[u] += data
                stats[2] += 1
            if ok or lost:
                h_bits[u, h] = 0
            else:
                h_due[u, h] = k + rtt
            used[serv[u]] += nprb[u]
        for u in range(U):
            if want[u]:
                avg[u] += a_pf * (rate_slot[u] - avg[u])
    return -1


rlm_step = numba.njit(cache=True, fastmath=False, nogil=True)(_rlm_step) if numba is not None else None
sched_slots = numba.njit(cache=True, fastmath=False, nogil=True)(_sched_slots) if numba is not None else None
