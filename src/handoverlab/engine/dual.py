# SPDX-License-Identifier: MIT
"""Dual connectivity (NR-DC of TS 37.340 V19.3.0), optional since 2.3.0 (``protocol.dc``).

:class:`DcEngine` is :class:`~handoverlab.engine.extended.ExtEngine` with a
secondary cell group.  The master cell group (MCG) is the engine's own
connection: the handover rule, radio-link monitoring, failures and
re-establishment run as without dual connectivity, on every cell that is not on
the SCG carrier (the MCG side sees the SCG cells as absent).  The SCG has one
serving cell, the PSCell, on the carrier of ``protocol.dc.scg_layer``; it never
changes what happens on the MCG.

SCG procedures (one at a time per user)
    SN addition (clause 10.2, MN initiated): event A4 on the SCG carrier (the
    best SCG cell's L3 RSRP above ``add_thresh_dbm``) held for ``add_ttt_s``
    while the MCG is connected -> ``prep_s`` (SN Addition Request /
    Acknowledge) -> RRC reconfiguration over the MCG -> random access on the
    new PSCell after ``exec_s``; the SCG joins when the PSCell SINR reaches Qout
    while T304 runs, otherwise an SCG failure (reconfiguration with sync
    failure of the SCG, TS 38.331 5.7.3.2).
    PSCell change (clauses 10.5, 10.6; SN change and intra-SN change alike):
    event A3 among SCG cells (``change_off_db``, ``change_ttt_s``) -> the same
    steps; no SCG data from the command until the target is joined.
    SN release (clause 10.4, MN initiated): the PSCell's L3 RSRP below
    ``release_thresh_dbm`` for ``release_ttt_s`` -> released after ``prep_s``.
    Every reconfiguration goes over the MCG (SRB1); one that falls due while the
    MCG is not connected or its T310 runs is dropped.

SCG failures (clause 7.7)
    Radio-link failure of the SCG (TS 38.331 5.3.10.3: T310 expiry in the
    PSCell, with the indications and constants of the MCG) and a failed SN
    addition or PSCell change: the UE reports SCGFailureInformation to the MN
    instead of re-establishing, and the MN releases the SCG (of its options
    keep / change / release, this model always releases).  An MCG failure
    starts re-establishment, which releases the SCG (TS 38.331 5.3.7.2: MR-DC
    release); at an MCG handover the target MN keeps the SN or releases it
    (``on_mcg_ho``, clause 10.7).

Measurements and data
    The SCG cells' L1 samples (cell quality as for the MCG) enter an L3 filter
    of their own (TS 38.331 5.5.3.2 with the reference period of the SCG
    carrier's frequency range).  The PSCell transmits on its strongest SSB beam
    of the current L1 instant (ideal SCG beam management).  Interference comes
    from the other cells of the SCG carrier with their load.  An SCG user
    receives W x min(log2(1 + SINR), se_max) x (1 - background load) / (SCG
    users of its PSCell): a full-buffer share reported as ``scg_rate_mbps``,
    apart from the MCG rate.
"""
from __future__ import annotations

import math

import numpy as np

from .. import requirements as req
from ..channel.extended import NO_BEAM_DB, ExtChunk
from ..measurement import EPS, INF, L3Filter
from .core import LN10_10, rlm_indications
from .extended import ExtEngine
from .procedures import CONNECTED

# SCG state of a user
IDLE, ADD_PREP, ADD_RA, ACTIVE, CHG_PREP, CHG_RA, REL_PREP = range(7)
SERVING = (ACTIVE, CHG_PREP, REL_PREP)                   # a PSCell carries data and is monitored

#: counters of the SCG (all start at zero; ``_all`` ones include the warm-up)
DC_COUNTERS = ("dc_add", "dc_add_ok", "dc_add_fail", "dc_add_drop", "dc_chg", "dc_chg_ok", "dc_chg_fail",
               "dc_chg_drop", "dc_rel", "dc_rlf", "dc_rel_mcg", "dc_rrc")


class DualConnectivity:
    """SCG state and procedures of all users of one engine."""

    def __init__(self, eng):
        self.eng = eng
        sc = eng.world.scenario
        P, D = sc.protocol, sc.protocol.dc
        self.P, self.D = P, D
        ext = eng.ext
        names = [L.name for L in ext.layers]
        li = names.index(D.scg_layer if D.scg_layer is not None else names[1])
        self.layer = ext.layers[li]
        self.cells = np.nonzero(ext.cell_layer == li)[0]
        self.n = len(self.cells)
        self.prep = P.prep_s if D.prep_s is None else D.prep_s
        self.exec = P.exec_s if D.exec_s is None else D.exec_s
        f = self.layer.radio.carrier_ghz
        x_ref = req.l3_reference_period(f, P.ssb_period_s, P.fr2_power_class) if eng.std else 0.2
        self.l3 = L3Filter(P.l3_k, eng.mdt, x_ref)
        # RLM of the PSCell: the windows of the protocol, or the TS 38.133 evaluation periods of the SCG carrier
        if P.rlm_eval == "ts38133":
            b = self.layer.beams
            n = b.rx_sweep_n if (b is not None and b.rx_sweep_n) else req.rx_sweep_factor(f)
            to, ti = req.rlm_evaluation_periods(P.ssb_period_s, n)
        else:
            to, ti = P.qout_window_s, P.qin_window_s
        self.ao = 1.0 - math.exp(-P.step_s / to)
        self.ai = 1.0 - math.exp(-P.step_s / ti)
        U = eng.U
        self.st = np.zeros(U, dtype=np.int8)
        self.ps = np.full(U, -1)                              # PSCell (index into self.cells), -1: none
        self.tgt = np.full(U, -1)
        self.t_due = np.full(U, INF)                          # end of the preparation / of the random access
        self.t304 = np.full(U, INF)                           # start of the SCG reconfiguration with sync
        self.te_add = np.full(U, INF)
        self.te_rel = np.full(U, INF)
        self.te_chg = np.full((U, self.n), INF)
        self.qo = np.zeros(U); self.qi = np.zeros(U)
        self.n_o = np.zeros(U, dtype=int); self.n_i = np.zeros(U, dtype=int)
        self.run = np.zeros(U, dtype=bool); self.t310 = np.zeros(U)
        self.rlm_t0 = np.full(U, -INF)
        self.raw = None
        for k in DC_COUNTERS:
            eng.C[k] = 0
        for k in ("dc_time", "dc_thr", "dc_int"):
            eng.acc[k] = 0.0

    # ------------------------------------------------------------------ radio
    def masked(self, ch):
        """The chunk as the MCG sees it: no L1 sample of an SCG cell."""
        self.raw = ch
        l1 = ch.l1.copy()
        l1[:, :, self.cells] = NO_BEAM_DB
        bl1 = ch.bl1.copy()
        bl1[:, :, self.cells, :] = NO_BEAM_DB
        return ExtChunk(ch.k0, ch.n, ch.lin, l1, ch.mp, bl1, ch.site_db, ch.x, ch.y, ch.bg)

    def sinr(self, i, users, idx):
        """SINR (linear) of SCG cells ``self.cells[idx]`` at ``users`` in step ``i`` of the current chunk."""
        eng, ch = self.eng, self.raw
        cells = self.cells[idx]
        ln = ch.lin[i]
        rc = eng.rc[self.cells]
        tot = ln[users][:, self.cells] @ rc
        lc = ln[users, cells]
        p = lc.copy()
        hb = eng.has_b[cells]
        if hb.any():                                          # the strongest beam of this L1 instant
            uu, cc = users[hb], cells[hb]
            g = ch.bg[i // ch.mp, uu, cc].max(-1)
            p[hb] = np.exp((ch.site_db[i, uu, eng.ext.cell_site[cc]] + eng.ext.p0[cc] + g) * LN10_10)
        return p / (tot - eng.rc[cells] * lc + eng.noise_c[cells])

    # ------------------------------------------------------------------ bookkeeping
    def _count(self, key, t, n=1):
        if t >= self.eng.t0c:
            self.eng.C[key] += n

    def _trace(self, t, u, event, src, cell, value=np.nan):
        if self.eng.trace_log is not None:
            g = lambda j: int(self.cells[j]) if j >= 0 else -1          # noqa: E731
            self.eng.trace_event(t, u, event, g(src), g(cell), value)

    def _to_idle(self, u):
        self.st[u] = IDLE
        self.ps[u] = self.tgt[u] = -1
        self.t_due[u] = self.t304[u] = INF
        self.te_add[u] = self.te_rel[u] = INF
        self.te_chg[u] = INF
        self.run[u] = False

    def _drop(self, u, t):
        """A pending addition or change ends without a result (lost command, MCG release)."""
        s = self.st[u]
        if s in (ADD_PREP, ADD_RA):
            self._count("dc_add_drop", t)
        elif s in (CHG_PREP, CHG_RA):
            self._count("dc_chg_drop", t)

    def _scg_failure(self, u, t, key, event):
        """SCG failure: SCGFailureInformation to the MN, which releases the SCG (TS 37.340 clause 7.7)."""
        self._count(key, t)
        self._count("dc_rrc", t)                              # SCGFailureInformation
        self._trace(t, u, event, self.ps[u], self.tgt[u] if self.tgt[u] >= 0 else self.ps[u])
        self._to_idle(u)

    def release_by_mcg(self, u, t, cause):
        """MCG failure (re-establishment: MR-DC release) or an MCG handover with ``on_mcg_ho: release``."""
        if self.st[u] == IDLE:
            return
        self._drop(u, t)
        self._count("dc_rel_mcg", t)
        self._trace(t, u, "scg_release_" + cause, self.ps[u], -1)
        self._to_idle(u)

    def _join(self, u, j, s, t):
        self.ps[u] = j
        self.tgt[u] = -1
        self.st[u] = ACTIVE
        self.t_due[u] = self.t304[u] = INF
        self.te_chg[u] = INF
        self.te_rel[u] = INF
        self.qo[u] = self.qi[u] = s
        self.n_o[u] = self.n_i[u] = 0
        self.run[u] = False
        self.rlm_t0[u] = t + self.P.rlm_holdoff_s

    # ------------------------------------------------------------------ per step
    def step(self, i, k, t):
        eng, P = self.eng, self.P
        st = self.st
        mcg_ok = (eng.state == CONNECTED) & ~eng.run
        # --- preparations end: the reconfiguration goes to the UE over the MCG
        for u in np.nonzero((st == ADD_PREP) | (st == CHG_PREP) | (st == REL_PREP))[0]:
            if t < self.t_due[u] - EPS:
                continue
            s = st[u]
            if not mcg_ok[u]:                                 # MCG not able to carry it: dropped
                if s == REL_PREP:
                    st[u] = ACTIVE
                    self.t_due[u] = INF
                else:
                    self._drop(u, t)
                    if s == ADD_PREP:
                        self._to_idle(u)
                    else:
                        st[u] = ACTIVE
                        self.tgt[u] = -1
                        self.t_due[u] = INF
                continue
            self._count("dc_rrc", t)                          # RRCReconfiguration
            if s == REL_PREP:
                self._count("dc_rel", t)
                self._trace(t, u, "sn_release", self.ps[u], -1)
                self._to_idle(u)
                continue
            st[u] = ADD_RA if s == ADD_PREP else CHG_RA
            self.t304[u] = t
            self.t_due[u] = t + self.exec
        # --- random access on the new PSCell
        ra = np.nonzero(((st == ADD_RA) | (st == CHG_RA)) & (t >= self.t_due - EPS))[0]
        if len(ra):
            s_ra = self.sinr(i, ra, self.tgt[ra])
            for u, s in zip(ra, s_ra):
                add = st[u] == ADD_RA
                if s >= eng.qout or not P.exec_can_fail:
                    self._count("dc_add_ok" if add else "dc_chg_ok", t)
                    self._count("dc_rrc", t)                  # RRCReconfigurationComplete
                    self._trace(t, u, "sn_add" if add else "pscell_change", self.ps[u], self.tgt[u],
                                10.0 * np.log10(max(float(s), 1e-30)))
                    self._join(u, int(self.tgt[u]), float(s), t)
                elif P.t304_s is not None and t - self.t304[u] < P.t304_s - EPS:
                    self.t_due[u] = t + eng.dt                # random access goes on while T304 runs
                else:
                    self._scg_failure(u, t, "dc_add_fail" if add else "dc_chg_fail",
                                      "sn_add_failure" if add else "pscell_change_failure")
        # --- radio-link monitoring of the PSCell
        mon = np.isin(st, SERVING)
        if mon.any():
            users = np.nonzero(mon)[0]
            s = np.zeros(eng.U)
            s[users] = self.sinr(i, users, self.ps[users])
            self.qo += np.where(mon, self.ao * (s - self.qo), 0.0)
            self.qi += np.where(mon, self.ai * (s - self.qi), 0.0)
            if k % eng.ind_steps == 0:
                start = rlm_indications(P, self.qo, self.qi, eng.qout, eng.qin, self.run, self.n_o, self.n_i, mon,
                                        t, self.rlm_t0)
                self.t310[start] = t
            for u in np.nonzero(self.run & mon & (t - self.t310 >= P.t310_s - EPS))[0]:
                self._scg_failure(u, t, "dc_rlf", "scg_rlf")
        # --- measurement instant
        if i % eng.mp == 0:
            self._measure(i, t, mcg_ok)

    def _measure(self, i, t, mcg_ok):
        eng, D, st = self.eng, self.D, self.st
        ch = self.raw
        m = self.l3.update(ch.l1[i // ch.mp][:, self.cells])
        # SN addition: event A4 on the best SCG cell, while the MCG is connected
        idle = (st == IDLE) & mcg_ok
        cond = idle & (m.max(1) > D.add_thresh_dbm)
        self.te_add = np.where(cond, np.minimum(self.te_add, t), INF)
        for u in np.nonzero(cond & (t - self.te_add >= D.add_ttt_s - EPS))[0]:
            self.st[u] = ADD_PREP
            self.tgt[u] = int(np.argmax(m[u]))
            self.t_due[u] = t + self.prep
            self._trace(t, u, "sn_add_request", -1, self.tgt[u], float(self.te_add[u]))   # value: A4 entry time
            self.te_add[u] = INF
            self._count("dc_add", t)
        # PSCell change (A3 among SCG cells) or SN release (PSCell below the release threshold)
        act = st == ACTIVE
        ps = np.where(act, self.ps, 0)
        ar = np.arange(eng.U)
        mps = m[ar, ps]
        cond = act[:, None] & (m - mps[:, None] > D.change_off_db)
        cond[ar, ps] = False
        self.te_chg = np.where(cond, np.minimum(self.te_chg, t), INF)
        ready = cond & (t - self.te_chg >= D.change_ttt_s - EPS)
        low = act & (mps < D.release_thresh_dbm)
        self.te_rel = np.where(low, np.minimum(self.te_rel, t), INF)
        for u in np.nonzero(act)[0]:
            if ready[u].any():
                self.st[u] = CHG_PREP
                self.tgt[u] = int(np.argmax(np.where(ready[u], m[u], -INF)))
                self.t_due[u] = t + self.prep
                self.te_chg[u] = INF
                self._count("dc_chg", t)
            elif low[u] and t - self.te_rel[u] >= D.release_ttt_s - EPS:
                self.st[u] = REL_PREP
                self.t_due[u] = t + self.prep
                self.te_rel[u] = INF
        # data on the SCG and the time with an SCG
        if t < eng.t0c:
            return
        serving = np.isin(st, SERVING)
        eng.acc["dc_int"] += eng.mdt * int(np.count_nonzero(st == CHG_RA))
        users = np.nonzero(serving)[0]
        if not len(users):
            return
        eng.acc["dc_time"] += eng.mdt * len(users)
        cells = self.cells[self.ps[users]]
        s = self.sinr(i, users, self.ps[users])
        n = np.bincount(self.ps[users], minlength=self.n)[self.ps[users]]
        se = np.minimum(np.log2(1.0 + s), eng.se_max)
        free = np.maximum(1.0 - eng.bg[cells], 0.0)
        eng.acc["dc_thr"] += float(np.sum(eng.W_c[cells] * se * free / n))


class DcEngine(ExtEngine):
    """:class:`ExtEngine` with a secondary cell group (``protocol.dc``, since 2.3.0)."""

    def __init__(self, world, rule, log_events=False, debug=None):
        super().__init__(world, rule, log_events, debug)
        self.dc = DualConnectivity(self)

    def advance(self, ch) -> None:
        super().advance(self.dc.masked(ch))

    def start_exec(self, u, tgt, t):
        super().start_exec(u, tgt, t)
        if self.dc.D.on_mcg_ho == "release":
            self.dc.release_by_mcg(u, t, "mcg_ho")

    def fail(self, u, t, kind):
        super().fail(u, t, kind)
        self.dc.release_by_mcg(u, t, "mcg_failure")
