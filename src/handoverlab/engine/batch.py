# SPDX-License-Identifier: MIT
"""Several engines on one world, advanced by one step loop.

All rules of a job run on the same radio samples.  :class:`EngineBatch`
stacks the per-user state of the radio-link monitoring of K engines into
arrays of shape (K, U); each engine keeps views of its own row, so all of
its event handling (executions, failures, procedures, measurement instants,
outcome labels) runs unchanged.  Per step, one set of array operations then
serves all K engines:

* serving SINR of every user of every engine;
* the Qout / Qin filters, the N310 / T310 logic and the expiry of T310;
* the check for ends of executions and re-establishments.

Only the interference sum of each engine (``ln @ rc``, a matrix-vector
product per engine, as in :class:`~handoverlab.engine.core.Engine`) and the
work at events stay per engine.  The interference weight of the serving
cells changes only at measurement instants and when a user changes cell, so
it is gathered only then.

Every operation is element by element on the same values and in the same
order as in a single engine, so results are bit-identical; the golden
event-log fingerprints and the regression tests check this.  Engines in
debug mode are not batched.
"""
from __future__ import annotations

import time
from typing import List, Sequence

import numpy as np

from ..measurement import EPS
from .core import Engine
from .procedures import CONNECTED, EXECUTING


class EngineBatch:
    """Advance the engines of all rules of one world together (see the module text)."""

    _STACKED = (("state", np.int8), ("t_done", float), ("re_cell", int), ("serv", np.intp), ("qo", float),
                ("qi", float), ("n_o", int), ("n_i", int), ("run", bool), ("t310", float), ("k310", int),
                ("rc", float), ("rho", float))

    def __init__(self, engines: Sequence[Engine]):
        self.engines: List[Engine] = list(engines)
        if not self.engines:
            raise ValueError("an engine batch needs at least one engine")
        e0 = self.engines[0]
        for e in self.engines:
            if e.world is not e0.world:
                raise ValueError("all engines of a batch must run on the same world")
            if e.debug:
                raise ValueError("engines in debug mode are not batched")
            if e.started:
                raise ValueError("engines must be batched before the first step")
        K = len(self.engines)
        self.K, self.U, self.M = K, e0.U, e0.M
        for name, dt in self._STACKED:
            rows = [getattr(e, name) for e in self.engines]
            arr = np.empty((K,) + rows[0].shape, dtype=rows[0].dtype)
            for k, (e, r) in enumerate(zip(self.engines, rows)):
                arr[k] = r
                setattr(e, name, arr[k])                       # the engine now works on its row
            setattr(self, name, arr)
        self.tot = np.empty((K, self.U))
        self.rcs = None                                        # rc[serv] of every engine (K, U)
        self.offs = (np.arange(K) * self.M)[:, None]           # bin offsets of the engines for bincount
        self.free = np.maximum(1.0 - e0.bg, 0.0)
        self.dem = [float(e.rate.sum()) for e in self.engines]
        self.wall = 0.0

    @staticmethod
    def supported(engines: Sequence[Engine]) -> bool:
        return len(engines) > 1 and not any(e.debug for e in engines)

    def advance(self, ch) -> None:
        """Simulate the steps of one radio chunk for every engine."""
        w0 = time.perf_counter()
        E = self.engines
        for e in E:
            if not e.started:
                e._init(ch)
        e0 = E[0]
        P, dt = e0.P, e0.dt
        noise, qout, qin, ao, ai = e0.noise, e0.qout, e0.qin, e0.ao, e0.ai
        mp = e0.mp
        simple = P.n310 == 1 and P.n311 == 1
        t310_s = P.t310_s
        state, t_done, serv, run = self.state, self.t_done, self.serv, self.run
        qo, qi, rc, tot = self.qo, self.qi, self.rc, self.tot
        t310, k310 = self.t310, self.k310
        ar = e0.ar
        cnz = np.count_nonzero
        rcs = self.rcs
        for i in range(ch.n):
            k = ch.k0 + i
            t = k * dt
            ln = ch.lin[i]
            for j in range(self.K):
                np.matmul(ln, rc[j], out=tot[j])
            # --- end of an execution or of a re-establishment
            if cnz(state):
                due = np.nonzero((state != CONNECTED) & (t >= t_done - EPS))
                if len(due[0]):
                    for j, u in zip(*due):
                        e = E[j]
                        if state[j, u] == EXECUTING:
                            e._end_exec(u, t, ln, tot[j])
                        else:
                            c = int(e.re_cell[u])
                            lc = ln[u, c]
                            e._attach(u, c, lc / (tot[j, u] - e.rc[c] * lc + noise))
                    rcs = None
            if rcs is None:
                rcs = np.take_along_axis(rc, serv, axis=1)
            ls = ln[ar, serv]
            sinr = ls / (tot - rcs * ls + noise)
            con = state == CONNECTED
            # --- radio-link monitoring
            qo += ao * (sinr - qo)
            qi += ai * (sinr - qi)
            if simple:
                start = (qo < qout) & con & ~run
            else:
                self.n_o[:] = (self.n_o + 1) * (qo < qout)
                self.n_i[:] = (self.n_i + 1) * (qi > qin)
                start = con & ~run & (self.n_o >= P.n310)
            if cnz(start):
                run |= start
                t310[start] = t
                k310[start] = k
            if cnz(run):
                run &= ~((qi > qin) if simple else (self.n_i >= P.n311))
                exp = np.nonzero(run & con & (t - t310 >= t310_s - EPS))
                for j, u in zip(*exp):
                    E[j].fail(u, t, "rlf")
            # --- handover command / conditional configuration reaches the UE
            for e in E:
                e.proc.step(t)
            # --- measurement instant (rc changes here)
            if i % mp == 0:
                jm = i // mp
                counted = False
                for e in E:
                    counted = e._measure_rule(ch, jm, k, t, ln)
                self._load(ln, counted)
                for e in E:
                    e.nmeas += 1
                rcs = None
        self.rcs = rcs
        el = time.perf_counter() - w0
        self.wall += el
        for e in E:
            e.wall += el / self.K

    def _load(self, ln, counted: bool) -> None:
        """Load, scheduling and delivered rate of every engine (as ``Engine._load``, element by element)."""
        E, e0 = self.engines, self.engines[0]
        serv, state, rc, rho, tot = self.serv, self.state, self.rc, self.rho, self.tot
        rate, gbr, bg, K, M = e0.rate, e0.gbr, e0.bg, self.K, self.M
        con = state == CONNECTED
        ls = ln[e0.ar, serv]
        sinr = ls / (tot - np.take_along_axis(rc, serv, axis=1) * ls + e0.noise)
        ok = con & (sinr >= e0.qout)
        se = np.empty_like(sinr)
        for j in range(K):          # transcendental functions per engine, on arrays laid out as in Engine._load
            se[j] = np.minimum(np.log2(1.0 + sinr[j]), e0.se_max)
        need = np.where(ok, rate / (e0.W * np.maximum(se, 1e-3)), 0.0)
        idx = (serv + self.offs).ravel()
        G = np.bincount(idx, weights=(need * gbr).ravel(), minlength=K * M).reshape(K, M)
        B = np.bincount(idx, weights=(need * ~gbr).ravel(), minlength=K * M).reshape(K, M)
        free = self.free
        gs = np.minimum(1.0, free / np.maximum(G, 1e-12))
        rem = np.maximum(free - G * gs, 0.0)
        bs = np.minimum(1.0, rem / np.maximum(B, 1e-12))
        thr = np.where(ok, rate * np.where(gbr, np.take_along_axis(gs, serv, axis=1),
                                           np.take_along_axis(bs, serv, axis=1)), 0.0)
        rho_new = np.minimum(1.0, bg + G * gs + B * bs)
        rho += e0.a_rho * (rho_new - rho)
        np.multiply(e0.chi, rho, out=rc)
        if counted:
            mp = e0.mp
            n_out = np.count_nonzero(con & (sinr < e0.qout), axis=1)
            n_con = np.count_nonzero(con, axis=1)
            for j, e in enumerate(E):
                acc, c = e.acc, con[j]
                acc["steps"] += mp
                acc["out_steps"] += mp * int(n_out[j])
                acc["thr"] += float(thr[j].sum()); acc["dem"] += self.dem[j]
                acc["sinr"] += float(10.0 * np.log10(sinr[j][c]).sum()); acc["se"] += float(se[j][c].sum())
                acc["ncon"] += int(n_con[j]); acc["load"] += float(rho_new[j].mean()); acc["nmeas"] += 1
                acc["prep_time"] += e.proc.prepared_total() * e.mdt

    def finish(self):
        return [e.finish() for e in self.engines]
