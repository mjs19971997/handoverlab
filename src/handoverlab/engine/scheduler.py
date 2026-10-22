# SPDX-License-Identifier: MIT
"""Slot scheduler with MCS selection and HARQ for the optional data plane (``protocol.scheduler``, since 2.2.0).

At every measurement instant the engine hands the scheduler the effective SINR of every user's serving link, the
data each user has to receive and the free share of every cell; the scheduler then plays the slots of the interval
(slot length 1 ms / 2^mu for the subcarrier spacing):

* the PRBs of a cell left by the background load go to its connected users with data: ``rr`` gives every such
  user an equal share in every slot (round robin in frequency), ``pf`` gives the whole band in a slot to the user
  with the largest instantaneous over average rate (proportional fair in time); a user with a retransmission due
  is served first;
* the MCS is the highest of MCS table 1 (TS 38.214 Table 5.1.3.1-1) whose BLER at the SINR reported at the
  previous instant is at most 10 % (link adaptation; the reporting delay is one measurement interval);
* the TBS follows TS 38.214 clause 5.1.3.2 for 12 PDSCH symbols and 12 DMRS REs per PRB; a TB larger than the
  user's data is padded (only the data count as delivered);
* a TB is decoded with the BLER of :func:`handoverlab.linklevel.bler`; HARQ (TS 38.321 clause 5.3.2) with
  ``N_HARQ`` = 8 processes per user (TS 38.331 PDSCH-ServingCellConfig: the number when
  nrofHARQ-ProcessesForPDSCH is absent): a failed TB waits in its process and is sent again after
  ``harq_rtt_slots`` with chase combining (the SINRs of its transmissions add), at most ``harq_max_tx``
  transmissions in all (an assumption: the number is the network's choice); a new TB needs a free process.

The decoding draws come from the world's own stream ``harq``, one uniform number per user and slot whatever the
decisions, so every rule compared on one seed sees the same draws.

With the user-plane buffers (``protocol.buffers``, since 2.3.0) the engine also uses the first slot a user may be
served in (forwarded data still on their way), the data of TBs lost after the last transmission, the data in the
HARQ processes and their flush at a MAC reset.

With ``run.backend: numba`` (since 2.4.0) the slots are played by the compiled loop
:func:`handoverlab.engine._kernels.sched_slots`.  The MCS look-ups and block error probabilities still come from
the functions and memos of the NumPy loop (tables filled per interval; the BLER of the later transmissions of a TB
follows from its combined SINR, a fixed sequence of additions of the user's SINR, which is constant within the
interval), and the loop itself uses only basic arithmetic in the NumPy loop's order, so the results are
bit-identical.  The NumPy loop stays the reference and runs in debug mode.
"""
from __future__ import annotations

import math
from functools import lru_cache
from typing import Dict, Tuple

import numpy as np

from .. import linklevel as ll
from ..seeds import streams

N_HARQ = 8
BLER_TARGET = 0.1


@lru_cache(maxsize=None)
def _tbs_row(nre: int) -> np.ndarray:
    """TBS of every MCS of table 1 for ``nre`` REs."""
    return np.array([ll.tbs(nre, m) for m in range(len(ll.MCS_TABLE1))], dtype=np.int64)


class SlotScheduler:
    def __init__(self, world, n_cells: int, n_users: int, kind: str, interval_s: float, harq_max_tx: int = 4,
                 harq_rtt_slots: int = 8, loss_db: float = 1.0, pf_tc_slots: float = 100.0):
        from ..channel.extended import default_scs_khz, n_rb
        R = world.scenario.radio
        scs = R.scs_khz or default_scs_khz(R.carrier_ghz)
        self.slot_s = 1e-3 / (scs / 15.0)
        self.n_slots = max(1, int(round(interval_s / self.slot_s)))
        self.n_prb = n_rb(R.bandwidth_mhz, scs, R.carrier_ghz) or int(R.bandwidth_mhz * 1e3 // (12 * scs))
        self.kind, self.M, self.U = kind, n_cells, n_users
        self.max_tx, self.rtt, self.loss = harq_max_tx, harq_rtt_slots, loss_db
        self.rng = streams(world.seed, "harq", 1)[0]
        self.avg = np.full(n_users, 1e3)                     # PF average rate [bit/slot]
        self.a_pf = 1.0 / pf_tc_slots
        shape = (n_users, N_HARQ)                            # HARQ processes: TB size 0 = free
        self.h_bits = np.zeros(shape, dtype=np.int64)
        self.h_data = np.zeros(shape)                        # data carried by the TB [bit] (<= TB size)
        self.h_sinr = np.zeros(shape)                        # accumulated SINR (chase combining, linear)
        self.h_tx = np.zeros(shape, dtype=np.int64)
        self.h_due = np.zeros(shape, dtype=np.int64)
        self.h_mcs = np.zeros(shape, dtype=np.int64)
        self.h_ncb = np.zeros(shape, dtype=np.int64)
        self.sinr_rep = np.full(n_users, np.nan)             # reported SINR (previous instant) [dB]
        self.slot = 0
        self.stats = dict(tb=0, tb_ok=0, tb_lost=0, retx=0)
        self.lost_bits = np.zeros(n_users)                   # data of TBs lost in the last interval [bit]
        self._sel: Dict[Tuple[int, int], Tuple[int, int, int]] = {}
        self.kernel = None                                   # compiled slot loop (run.backend: numba, 2.4.0)

    def use_kernel(self, kernel) -> None:
        """Play the slots with ``kernel`` (:func:`handoverlab.engine._kernels.sched_slots`); same results."""
        self.kernel = kernel
        self.h_p = np.zeros((self.U, N_HARQ, self.max_tx + 1))   # BLER of each transmission of a process's TB
        self._scratch = (np.zeros(self.U, dtype=np.bool_), np.zeros(self.U, dtype=np.bool_),
                         np.zeros(self.U, dtype=np.int64), np.zeros(self.U), np.zeros(self.U),
                         np.zeros(self.M, dtype=np.int64), np.zeros(self.M, dtype=np.int64),
                         np.zeros(self.M, dtype=np.int64))

    def select(self, sinr_db: float, n_prb: int) -> Tuple[int, int, int]:
        """(MCS, TBS, coded bits) for ``n_prb`` PRBs at a reported SINR (0.1 dB steps); MCS -1 if none reaches the
        target BLER."""
        key = (int(round(sinr_db * 10.0)), int(n_prb))
        if key not in self._sel:
            nre = ll.n_re(n_prb)
            best = (-1, 0, 0)
            for m in range(len(ll.MCS_TABLE1)):
                t = ll.tbs(nre, m)
                ncb = nre * ll.MCS_TABLE1[m][0]
                if ll.bler(np.array([key[0] / 10.0]), m, t, ncb, self.loss)[0] > BLER_TARGET:
                    break
                best = (m, t, ncb)
            self._sel[key] = best
        return self._sel[key]

    def select_all(self, sinr_db: float, n_prb: int) -> Tuple[int, int, int]:
        """:meth:`select` with the BLER of all MCS in one array operation (for the compiled loop, since 2.4.0):
        the same operations element by element as :func:`handoverlab.linklevel.bler` (the log2 of the coded
        bits by ``math.log2``), so the same values; shares the memo of :meth:`select`."""
        key = (int(round(sinr_db * 10.0)), int(n_prb))
        if key not in self._sel:
            from scipy.special import ndtr
            nre = ll.n_re(n_prb)
            tb = _tbs_row(nre)
            q = ll._QM
            n = np.maximum(nre * q, 1)
            s = np.array([key[0] / 10.0]) - self.loss
            c = np.empty(len(q))
            v = np.empty(len(q))
            for qm in (2, 4, 6):
                db, cap, disp = ll._bit_channel(qm)
                j = q == qm
                c[j] = np.interp(s, db, cap)[0]
                v[j] = np.interp(s, db, disp)[0]
            nf = n.astype(float)
            p = ndtr(-(nf * c - (tb + 24) + 0.5 * np.array([math.log2(x) for x in n.tolist()])) / np.sqrt(nf * v))
            over = np.nonzero(p > BLER_TARGET)[0]
            m = (int(over[0]) if len(over) else len(q)) - 1
            self._sel[key] = (m, int(tb[m]), int(nre * q[m])) if m >= 0 else (-1, 0, 0)
        return self._sel[key]

    def _new_tb(self, users: np.ndarray, nprb: np.ndarray, rep: np.ndarray):
        """MCS, TBS and coded bits of a new TB for each of ``users`` (arrays; MCS -1: none fits); the reported SINR
        is constant within the interval, so each (user, PRBs) is looked up once per interval."""
        out = np.empty((len(users), 3), dtype=np.int64)
        memo = self._tbmemo
        for i, (u, n) in enumerate(zip(users.tolist(), nprb.tolist())):
            v = memo.get((u, n))
            if v is None:
                v = memo[(u, n)] = self.select(float(rep[u]), n)
            out[i] = v
        return out[:, 0], out[:, 1], out[:, 2]

    def _p_new(self, n, m, t, ncb, sinr_db):
        """BLER of new TBs; the SINR is constant within the interval, so each (user, MCS, TBS) is computed once."""
        p = np.empty(len(n))
        todo = []
        for i, key in enumerate(zip(n.tolist(), m.tolist(), t.tolist())):
            v = self._pmemo.get(key)
            if v is None:
                todo.append(i)
            else:
                p[i] = v
        if todo:
            j = np.array(todo)
            pv = ll.bler_vec(sinr_db[n[j]], m[j], t[j], ncb[j], self.loss)
            p[j] = pv
            for i, v in zip(todo, pv.tolist()):
                self._pmemo[(int(n[i]), int(m[i]), int(t[i]))] = v
        return p

    def inflight(self) -> np.ndarray:
        """Data in the HARQ processes of every user [bit]."""
        return np.where(self.h_bits > 0, self.h_data, 0.0).sum(axis=1)

    def flush(self, u) -> float:
        """MAC reset of user ``u``: the HARQ processes are emptied; returns the data they held [bit]."""
        bits = float(np.where(self.h_bits[u] > 0, self.h_data[u], 0.0).sum())
        self.h_bits[u] = 0
        return bits

    def serve(self, sinr: np.ndarray, demand_bits: np.ndarray, con: np.ndarray, serv: np.ndarray,
              free: np.ndarray, first_slot=None) -> Tuple[np.ndarray, np.ndarray]:
        """Play the slots of one interval: delivered data per user [bit] and used share of the PRBs per cell
        (``first_slot``: per user, the first slot it may be served in)."""
        U, M = self.U, self.M
        sinr_db = 10.0 * np.log10(np.maximum(sinr, 1e-30))
        rep = np.where(np.isnan(self.sinr_rep), sinr_db, self.sinr_rep)
        self.sinr_rep = sinr_db
        draws = self.rng.random((self.n_slots, U))
        left = np.where(con, demand_bits, 0.0).astype(float)
        got = np.zeros(U)
        used = np.zeros(M)
        prb_cell = np.floor(np.clip(free, 0.0, 1.0) * self.n_prb).astype(np.int64)
        idx = np.arange(U)
        big = np.iinfo(np.int64).max
        self.lost_bits = np.zeros(U)
        self._pmemo = {}                                     # BLER of a new TB per (user, MCS, TBS) this interval
        self._tbmemo = {}                                    # MCS / TBS per (user, PRBs) this interval
        if self.kernel is not None:
            self._serve_kernel(sinr, sinr_db, rep, draws, left, got, used, con, serv, prb_cell, first_slot)
            self.slot += self.n_slots
            return got, used / np.maximum(self.n_prb * self.n_slots, 1)
        share_memo = {}                                      # round-robin shares per set of active users
        for s in range(self.n_slots):
            k = self.slot + s
            due = (self.h_bits > 0) & (self.h_due <= k)                       # (U, N_HARQ)
            has_re = due.any(axis=1)
            has_free = (self.h_bits == 0).any(axis=1)
            want = con & (has_re | ((left > 0) & has_free)) & (prb_cell[serv] > 0)
            if first_slot is not None:
                want &= first_slot <= s
            if not want.any():
                continue
            nprb = np.zeros(U, dtype=np.int64)
            w = idx[want]
            if self.kind == "pf":
                prio = np.where(has_re[w], 1, 0)
                metric = np.zeros(len(w))
                nre = ~has_re[w]
                if nre.any():
                    t = self._new_tb(w[nre], prb_cell[serv[w[nre]]], rep)[1]
                    metric[nre] = t / np.maximum(self.avg[w[nre]], 1e-9)
                order = np.lexsort((-metric, -prio, serv[w]))                 # per cell: retransmission, best metric
                first = np.ones(len(order), dtype=bool)
                first[1:] = serv[w[order]][1:] != serv[w[order]][:-1]
                pick = w[order[first]]
                nprb[pick] = prb_cell[serv[pick]]
            else:
                key = want.tobytes() + has_re.tobytes()
                cached = share_memo.get(key)
                if cached is None:
                    order = np.lexsort((w, ~has_re[w], serv[w]))              # per cell: retransmissions first
                    ws = w[order]
                    cell = serv[ws]
                    start = np.r_[0, np.nonzero(cell[1:] != cell[:-1])[0] + 1]
                    rank = np.arange(len(ws)) - np.repeat(start, np.diff(np.r_[start, len(ws)]))
                    cnt = np.bincount(cell, minlength=M)
                    base, extra = np.divmod(prb_cell, np.maximum(cnt, 1))
                    cached = share_memo[key] = (ws, base[cell] + (rank < extra[cell]))
                nprb[cached[0]] = cached[1]
            srv = idx[nprb > 0]
            if not len(srv):
                continue
            rate_slot = np.zeros(U)
            r = srv[has_re[srv]]                                              # retransmissions (oldest due process)
            if len(r):
                h = np.argmin(np.where(due[r], self.h_due[r], big), axis=1)
                self.h_sinr[r, h] += sinr[r]
                self.h_tx[r, h] += 1
                self.stats["retx"] += len(r)
                p = ll.bler_vec(10.0 * np.log10(np.maximum(self.h_sinr[r, h], 1e-30)), self.h_mcs[r, h],
                                self.h_bits[r, h], self.h_ncb[r, h], self.loss)
                ok = draws[s, r] >= p
                got[r[ok]] += self.h_data[r[ok], h[ok]]
                rate_slot[r[ok]] = self.h_data[r[ok], h[ok]]
                lost = ~ok & (self.h_tx[r, h] >= self.max_tx)
                np.add.at(self.lost_bits, r[lost], self.h_data[r[lost], h[lost]])
                self.stats["tb_ok"] += int(ok.sum())
                self.stats["tb_lost"] += int(lost.sum())
                self.h_bits[r[ok | lost], h[ok | lost]] = 0
                again = ~ok & ~lost
                self.h_due[r[again], h[again]] = k + self.rtt
                np.add.at(used, serv[r], nprb[r])
            n = srv[~has_re[srv]]                                             # new transport blocks
            if len(n):
                m, t, ncb = self._new_tb(n, nprb[n], rep)
                fit = m >= 0
                n, m, t, ncb = n[fit], m[fit], t[fit], ncb[fit]
                if len(n):
                    h = np.argmax(self.h_bits[n] == 0, axis=1)
                    data = np.minimum(t.astype(float), left[n])
                    left[n] -= data
                    self.stats["tb"] += len(n)
                    self.h_bits[n, h], self.h_data[n, h], self.h_sinr[n, h] = t, data, sinr[n]
                    self.h_tx[n, h], self.h_mcs[n, h], self.h_ncb[n, h] = 1, m, ncb
                    p = self._p_new(n, m, t, ncb, sinr_db)
                    ok = draws[s, n] >= p
                    got[n[ok]] += data[ok]
                    rate_slot[n[ok]] = data[ok]
                    lost = ~ok & (self.max_tx <= 1)
                    np.add.at(self.lost_bits, n[lost], data[lost])
                    self.stats["tb_ok"] += int(ok.sum())
                    self.stats["tb_lost"] += int(lost.sum())
                    self.h_bits[n[ok | lost], h[ok | lost]] = 0
                    again = ~ok & ~lost
                    self.h_due[n[again], h[again]] = k + self.rtt
                    np.add.at(used, serv[n], nprb[n])
            self.avg[w] += self.a_pf * (rate_slot[w] - self.avg[w])
        self.slot += self.n_slots
        return got, used / np.maximum(self.n_prb * self.n_slots, 1)

    def _later_bler(self, u, acc, k0, m, t, ncb, out):
        """BLER of transmissions k0+1 .. ``harq_max_tx`` of TBs of users ``u`` whose combined SINR is ``acc``
        after transmission ``k0``; the SINR of the interval is added once per transmission, in the order of the
        NumPy loop, and ``out(rows, k, p)`` stores the values."""
        acc = acc.copy()
        for k in range(int(k0.min()) + 1, self.max_tx + 1):
            j = np.nonzero(k > k0)[0]
            acc[j] = acc[j] + self._sinr[u[j]]
            if len(j):
                out(j, k, ll.bler_vec(10.0 * np.log10(np.maximum(acc[j], 1e-30)), m[j], t[j], ncb[j], self.loss))

    def _fill(self, us, ns, rep, sinr_db, sel, p_tab):
        """Look up (MCS, TBS, coded bits) and the BLER of every transmission of a new TB for the pairs (user,
        PRBs) with the functions and memos of the NumPy loop."""
        for u, n in zip(us.tolist(), ns.tolist()):
            if sel[u, n, 0] == -2:
                v = self._tbmemo.get((u, n))
                if v is None:
                    v = self._tbmemo[(u, n)] = self.select_all(float(rep[u]), n)
                sel[u, n] = v
        fit = sel[us, ns, 0] >= 0
        fit &= np.isnan(p_tab[us, ns, 1])
        us, ns = us[fit], ns[fit]
        if not len(us):
            return
        m, t, ncb = sel[us, ns, 0], sel[us, ns, 1], sel[us, ns, 2]
        p_tab[us, ns, 1] = self._p_new(us, m, t, ncb, sinr_db)
        if self.max_tx > 1:
            def put(j, k, p):
                p_tab[us[j], ns[j], k] = p
            self._later_bler(us, self._sinr[us], np.ones(len(us), dtype=np.int64), m, t, ncb, put)

    def _serve_kernel(self, sinr, sinr_db, rep, draws, left, got, used, con, serv, prb_cell, first_slot):
        """The slots of :meth:`serve` in the compiled loop; the logarithms and BLERs come from the NumPy functions
        (tables filled here, on request of the loop), so every value equals the NumPy loop's."""
        U = self.U
        sinr = np.ascontiguousarray(sinr, dtype=float)
        self._sinr = sinr
        serv = np.ascontiguousarray(serv, dtype=np.int64)
        con = np.ascontiguousarray(con, dtype=np.bool_)
        first = (np.zeros(U, dtype=np.int64) if first_slot is None
                 else np.ascontiguousarray(first_slot, dtype=np.int64))
        sel = np.full((U, self.n_prb + 1, 3), -2, dtype=np.int64)
        p_tab = np.full((U, self.n_prb + 1, self.max_tx + 1), np.nan)
        uu, hh = np.nonzero(self.h_bits > 0)                  # TBs carried over: BLER of their later transmissions
        if len(uu):
            def put(j, k, p):
                self.h_p[uu[j], hh[j], k] = p
            self._later_bler(uu, self.h_sinr[uu, hh], self.h_tx[uu, hh], self.h_mcs[uu, hh], self.h_bits[uu, hh],
                             self.h_ncb[uu, hh], put)
        if self.kind == "pf":                                  # one PRB count per user in the interval
            us = np.nonzero(con & (prb_cell[serv] > 0))[0]
            self._fill(us, prb_cell[serv[us]], rep, sinr_db, sel, p_tab)
        req = np.full(U, -1, dtype=np.int64)
        stats = np.zeros(4, dtype=np.int64)
        s = 0
        while True:
            s_new = self.kernel(s, self.slot, self.kind == "pf", self.a_pf, self.max_tx, self.rtt, con, serv,
                                prb_cell, first, sinr, draws, left, got, used, self.lost_bits, self.avg,
                                self.h_bits, self.h_data, self.h_sinr, self.h_tx, self.h_due, self.h_mcs, self.h_ncb,
                                self.h_p, sel, p_tab, req, stats, *self._scratch)
            if s_new < 0:
                break
            us = np.nonzero(req >= 0)[0]
            self._fill(us, req[us], rep, sinr_db, sel, p_tab)
            req[us] = -1
            s = s_new
        for key, v in zip(("tb", "tb_ok", "tb_lost", "retx"), stats.tolist()):
            self.stats[key] += v
