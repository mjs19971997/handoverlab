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
"""
from __future__ import annotations

from typing import Dict, Tuple

import numpy as np

from .. import linklevel as ll
from ..seeds import streams

N_HARQ = 8
BLER_TARGET = 0.1


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
