# SPDX-License-Identifier: MIT
"""User-plane buffers at handover: simplified PDCP / RLC queues and data forwarding (``protocol.buffers``, since
2.3.0).

One downlink DRB per user with RLC mode ``am`` or ``um``.  The data of the traffic model reach the gNB that holds
the user's PDCP entity (the *anchor*) and wait there in one FIFO per user.  The engine calls the hooks of
:class:`Buffers` at the events of the procedures:

* ``leave`` -- the UE leaves the source for an execution.  Baseline handover (TS 38.300 V19.4.0 9.2.3.2.1 NOTE
  2: forwarding may start with the handover command): the source forwards its FIFO and the data that arrive
  until the completion to the target (``protocol.forwarding``; without it they are lost); the target can send
  them ``xn_delay_s`` after they were forwarded.  CHO and LTM / CLTM (every cell of HandoverLab is its own gNB,
  so LTM is inter-gNB): late forwarding after HANDOVER SUCCESS (9.2.3.4.2 NOTE 2, 9.2.3.4.4, 9.2.3.5.2 NOTE 5),
  so the data reach the target 2 x ``xn_delay_s`` after the completion, or early forwarding
  (``early_forwarding``; 9.2.3.4.4, 9.2.3.5.2 step 9a): the data are at the target when the UE arrives.  DAPS
  (9.2.3.2.2, 9.2.3.2.3): the forwarding tunnel always exists, the source keeps sending and forwards every
  SN-assigned SDU (SNs are assigned on arrival: an assumption), so every byte queued or arriving during the
  execution is counted as forwarded and the target goes on with the rest without loss or wait.
* HARQ data at the start of an execution other than DAPS (slot scheduler only): with UM they are lost (MAC reset
  and RLC re-establishment, 9.2.3.1 and TS 38.322 5.1.2; no PDCP SDU is re-transmitted in the target, 9.2.3.2.2),
  with AM they stay queued (not acknowledged: forwarded and re-transmitted by the target, 9.2.3.2.2, 9.2.3.2.3).
  A TB lost after ``harq_max_tx`` transmissions is lost with UM and re-sent with AM (ARQ only for AM, TS 38.322
  4.4).
* ``fail`` / ``rejoin`` -- a failure and the end of the re-establishment: with forwarding the data of the last
  anchor move to the new cell and can be sent ``xn_delay_s`` after the re-establishment (9.2.3.3 steps 6/7); a
  recovery into a prepared cell (CHO, LTM) is forwarded as an execution of that procedure; without forwarding
  the data are lost if the UE re-establishes in another cell.
* ``discard_timer_s`` -- data older than the timer leave the FIFO as lost (TS 38.323 V19.1.0 5.3; the gNB uses
  the values of the discardTimer of TS 38.331 PDCP-Config for its downlink data: an assumption).

The data plane stays on the measurement grid of the rate model or the slot scheduler.  Within an interval the
data of a user leave the FIFO as a fluid at the larger of its round-robin share of the free carrier at its
spectral efficiency and the rate needed to send what the interval delivers; the PDCP delay of a byte is its
delivery time minus its arrival at the anchor (data arrive at the start of their interval).
"""
from __future__ import annotations

import numpy as np

#: values of the discardTimer of TS 38.331 PDCP-Config [s] (None: infinity)
DISCARD_TIMERS = (0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.075, 0.1, 0.15, 0.2, 0.25, 0.3, 0.5, 0.75, 1.5)
#: metrics of the option (0 when it is off), see :data:`handoverlab.engine.metrics.METRICS`
PDCP_METRICS = ("pdcp_delivered_kbyte_pm", "pdcp_lost_kbyte_pm", "pdcp_lost_share", "pdcp_lost_handover_kbyte_pm",
                "pdcp_lost_failure_kbyte_pm", "pdcp_lost_discard_kbyte_pm", "pdcp_lost_harq_kbyte_pm",
                "pdcp_lost_sdus_pm", "pdcp_forwarded_kbyte_pm", "pdcp_forwarded_sdus_pm", "pdcp_delay_ms",
                "pdcp_delay_p95_ms", "pdcp_delay_forwarded_ms")
LOSS_CAUSES = ("handover", "failure", "discard", "harq")
BIT_EPS = 1e-6
HIST_MS = 20000                     # delay histogram: 1 ms bins up to 20 s, the last bin collects the rest

NORMAL, RELAY, DROP, DAPS = 0, 1, 2, 3     # what happens to arrivals: queued, queued as forwarded, lost, DAPS


class Buffers:
    """PDCP FIFOs of all users with the hooks of the procedures (all amounts in bits, times in s)."""

    def __init__(self, n_users: int, interval_s: float, mode: str = "am", forwarding: bool = True,
                 early_forwarding: bool = False, xn_delay_s: float = 0.005, discard_timer_s=None,
                 sdu_bits: float = 12000.0, t_count: float = 0.0, capacity: int = 16):
        U = n_users
        self.U, self.mdt = U, float(interval_s)
        self.um = mode == "um"
        self.forwarding, self.early = bool(forwarding), bool(early_forwarding)
        self.xn = float(xn_delay_s)
        self.discard = None if discard_timer_s is None else float(discard_timer_s)
        self.sdu_bits = float(sdu_bits)
        self.t0c = float(t_count)
        self.K = int(capacity)
        self.rem = np.zeros((self.K, U))                    # FIFO slots: remaining bits, arrival time, forwarded
        self.ta = np.zeros((self.K, U))
        self.fw = np.zeros((self.K, U), dtype=bool)
        self.head = np.zeros(U, dtype=np.int64)
        self.n = np.zeros(U, dtype=np.int64)
        self.q = np.zeros(U)                                # queued bits
        self.hold = np.full(U, -np.inf)                     # forwarded data not at the anchor before this time
        self.anchor = np.zeros(U, dtype=np.int64)
        self.arr_mode = np.zeros(U, dtype=np.int8)
        self.drop_cause = np.zeros(U, dtype=np.int8)        # index into LOSS_CAUSES while arrivals are lost
        self.late = np.zeros(U, dtype=bool)                 # late forwarding at the completion
        self.rec = np.zeros(U, dtype=bool)                  # the re-establishment is a recovery into a prepared cell
        self.ar = np.arange(U)
        self.total = dict(arrived=0.0, delivered=0.0, lost=0.0)   # whole run (conservation)
        self.acc = dict(arrived=0.0, delivered=0.0, forwarded=0.0, delay=0.0, fwd_bits=0.0, fwd_delay=0.0,
                        **{"lost_" + c: 0.0 for c in LOSS_CAUSES})
        self.hist = np.zeros(HIST_MS + 1)

    # ------------------------------------------------------------------ FIFO
    def _grow(self):
        K = self.K
        order = (self.head[None, :] + np.arange(K)[:, None]) % K
        for name in ("rem", "ta", "fw"):
            a = np.take_along_axis(getattr(self, name), order, axis=0)
            pad = np.zeros((K, self.U), dtype=a.dtype)
            setattr(self, name, np.concatenate([a, pad]))
        self.head[:] = 0
        self.K = 2 * K

    def _push(self, bits, t, fwd):
        """Append ``bits`` (U,) arriving at ``t`` (``fwd``: (U,) bool, the data are forwarded ones)."""
        u = np.nonzero(bits > BIT_EPS)[0]
        if not len(u):
            return
        if (self.n[u] >= self.K).any():
            self._grow()
        pos = (self.head[u] + self.n[u]) % self.K
        self.rem[pos, u] = bits[u]
        self.ta[pos, u] = t
        self.fw[pos, u] = fwd[u]
        self.n[u] += 1
        self.q[u] += bits[u]

    def _take(self, u, amount, t_s=None, rate=None, counted=False):
        """Remove ``amount`` bits from the head of the FIFOs of the (distinct) users ``u``; with ``t_s`` / ``rate``
        the removed data are delivered: data leave at ``rate`` from ``t_s`` on, their delays are recorded."""
        left = np.array(amount, dtype=float)
        sent = np.zeros(len(u))
        taken = np.zeros(len(u))
        act = (left > BIT_EPS) & (self.n[u] > 0)
        while act.any():
            i = np.nonzero(act)[0]
            ua = u[i]
            h = self.head[ua]
            b = np.minimum(self.rem[h, ua], left[i])
            if t_s is not None and counted:
                d = t_s[i] + (sent[i] + 0.5 * b) / rate[i] - self.ta[h, ua]
                self.acc["delay"] += float(b @ d)
                f = self.fw[h, ua]
                if f.any():
                    self.acc["fwd_bits"] += float(b[f].sum())
                    self.acc["fwd_delay"] += float(b[f] @ d[f])
                np.add.at(self.hist, np.minimum((np.maximum(d, 0.0) * 1e3).astype(np.int64), HIST_MS), b)
            self.rem[h, ua] -= b
            left[i] -= b
            sent[i] += b
            taken[i] += b
            done = self.rem[h, ua] <= BIT_EPS
            self.rem[h[done], ua[done]] = 0.0
            self.head[ua[done]] = (h[done] + 1) % self.K
            self.n[ua[done]] -= 1
            act = (left > BIT_EPS) & (self.n[u] > 0)
        self.q[u] = np.where(self.n[u] > 0, np.maximum(self.q[u] - taken, 0.0), 0.0)
        return taken

    def _lose(self, bits, cause, t):
        self.total["lost"] += float(np.sum(bits))
        if t >= self.t0c:
            self.acc["lost_" + cause] += float(np.sum(bits))

    def _clear(self, u, cause, t):
        """All queued data of user ``u`` are lost."""
        b = float(self.q[u])
        self.rem[:, u] = 0.0
        self.n[u] = 0
        self.q[u] = 0.0
        self._lose(b, cause, t)

    def _drop_head(self, u, bits, cause, t):
        u = np.atleast_1d(np.asarray(u, dtype=np.int64))
        got = self._take(u, np.minimum(np.atleast_1d(bits), self.q[u]))
        self._lose(got, cause, t)

    def _forward(self, u, t, ready):
        """The queued data of user ``u`` are forwarded to another gNB, where they can be sent from ``ready``."""
        if self.q[u] > BIT_EPS:
            self.fw[:, u] = True
            if t >= self.t0c:
                self.acc["forwarded"] += float(self.q[u])
            self.hold[u] = max(self.hold[u], ready)

    # ------------------------------------------------------------------ data plane (every measurement instant)
    def arrive(self, t, bits):
        """Data of the traffic model reach the anchors at ``t`` ((U,) bits)."""
        bits = np.asarray(bits, dtype=float)
        tot = float(bits.sum())
        self.total["arrived"] += tot
        counted = t >= self.t0c
        if counted:
            self.acc["arrived"] += tot
        m = self.arr_mode
        drop = m == DROP
        if drop.any():
            for c in np.unique(self.drop_cause[drop]):
                self._lose(bits[drop & (self.drop_cause == c)], LOSS_CAUSES[c], t)
        fwd = (m == RELAY) | (m == DAPS)
        if counted and fwd.any():
            self.acc["forwarded"] += float(bits[fwd].sum())
        self._push(np.where(drop, 0.0, bits), t, m == RELAY)

    def discard_old(self, t):
        """TS 38.323 5.3: data older than the discard timer are discarded."""
        if self.discard is None:
            return
        lim = t - self.discard - 1e-9
        while True:
            u = np.nonzero((self.n > 0) & (self.ta[self.head, self.ar] < lim))[0]
            if not len(u):
                return
            self._drop_head(u, self.rem[self.head[u], u], "discard", t)

    def start_fraction(self, t) -> np.ndarray:
        """Share of the interval from ``t`` in which the anchor can send (forwarded data still on their way)."""
        return np.clip((t + self.mdt - np.maximum(t, self.hold)) / self.mdt, 0.0, 1.0)

    def deliver(self, t, bits, rate_share) -> np.ndarray:
        """``bits`` (U,) are delivered in the interval from ``t``; ``rate_share`` (U,) is the user's round-robin
        rate [bit/s].  Returns the bits taken from the FIFOs (at most what was queued)."""
        u = np.nonzero(bits > BIT_EPS)[0]
        out = np.zeros(self.U)
        if not len(u):
            return out
        t_s = np.maximum(t, self.hold[u])
        span = np.maximum(t + self.mdt - t_s, 1e-9)
        rate = np.maximum(np.maximum(rate_share[u], bits[u] / span), 1e-9)
        got = self._take(u, bits[u], t_s, rate, t >= self.t0c)
        out[u] = got
        self.total["delivered"] += float(got.sum())
        if t >= self.t0c:
            self.acc["delivered"] += float(got.sum())
        return out

    def harq_lost(self, t, bits) -> None:
        """TBs lost after the last HARQ transmission: lost with UM, re-sent by RLC ARQ with AM."""
        if self.um:
            u = np.nonzero(bits > BIT_EPS)[0]
            if len(u):
                self._drop_head(u, bits[u], "harq", t)

    # ------------------------------------------------------------------ events of the procedures
    def leave(self, u, t, tgt, kind, harq_bits=0.0) -> None:
        """The UE leaves its anchor for an execution towards ``tgt``: ``kind`` "ho" (baseline), "cond" (CHO, LTM)
        or "daps"."""
        if kind == "daps":                          # copies to the target; the source keeps sending
            if t >= self.t0c:
                self.acc["forwarded"] += float(self.q[u])
            self.arr_mode[u] = DAPS
            return
        if self.um and harq_bits > BIT_EPS:
            self._drop_head(u, harq_bits, "handover", t)
        if not self.forwarding:
            self._clear(u, "handover", t)
            self.arr_mode[u] = DROP
            self.drop_cause[u] = 0
            self.anchor[u] = tgt
        elif kind == "cond" and not self.early:
            self.late[u] = True                     # forwarded once the source knows the target
        else:
            self._forward(u, t, t if kind == "cond" else t + self.xn)
            self.arr_mode[u] = RELAY
            self.anchor[u] = tgt

    def join(self, u, t, cell) -> None:
        """The execution of user ``u`` completed in ``cell``."""
        if self.late[u]:
            self._forward(u, t, t + 2.0 * self.xn)  # HANDOVER SUCCESS, then the data over Xn
            self.late[u] = False
        elif self.arr_mode[u] == DAPS:              # the target sends the rest from the forwarded copies
            self.fw[:, u] = True
        self.arr_mode[u] = NORMAL
        self.anchor[u] = cell

    def fallback(self, u) -> None:
        """DAPS: back to the source, which keeps the data."""
        self.arr_mode[u] = NORMAL

    def fail(self, u, t, recovery: bool, harq_bits=0.0) -> None:
        """User ``u`` had a failure and starts re-establishment (``recovery``: into a prepared cell)."""
        if self.um and harq_bits > BIT_EPS:
            self._drop_head(u, harq_bits, "failure", t)
        self.late[u] = False
        self.arr_mode[u] = NORMAL
        self.rec[u] = bool(recovery)

    def rejoin(self, u, t, cell) -> None:
        """The re-establishment (or recovery) of user ``u`` completed in ``cell``."""
        if cell != self.anchor[u]:
            if not self.forwarding:
                self._clear(u, "failure", t)
            elif self.rec[u]:                       # a prepared cell: as an execution of the procedure
                self._forward(u, t, t if self.early else t + 2.0 * self.xn)
            else:                                   # TS 38.300 9.2.3.3 steps 6/7
                self._forward(u, t, t + self.xn)
            self.anchor[u] = cell
        self.rec[u] = False

    # ------------------------------------------------------------------ results
    def metrics(self, ue_min: float) -> dict:
        """The metrics of :data:`PDCP_METRICS` (per UE-minute of the measured part)."""
        a = self.acc
        lost = sum(a["lost_" + c] for c in LOSS_CAUSES)
        kb = 1.0 / 8000.0 / ue_min
        n = a["delivered"]
        cum = np.cumsum(self.hist)
        p95 = float(np.searchsorted(cum, 0.95 * cum[-1]) + 0.5) if cum[-1] > 0 else float("nan")
        out = dict(pdcp_delivered_kbyte_pm=n * kb, pdcp_lost_kbyte_pm=lost * kb,
                   pdcp_lost_share=lost / a["arrived"] if a["arrived"] > 0 else 0.0,
                   pdcp_lost_sdus_pm=lost / self.sdu_bits / ue_min,
                   pdcp_forwarded_kbyte_pm=a["forwarded"] * kb,
                   pdcp_forwarded_sdus_pm=a["forwarded"] / self.sdu_bits / ue_min,
                   pdcp_delay_ms=1e3 * a["delay"] / n if n > 0 else float("nan"),
                   pdcp_delay_p95_ms=p95,
                   pdcp_delay_forwarded_ms=1e3 * a["fwd_delay"] / a["fwd_bits"] if a["fwd_bits"] > 0 else 0.0)
        for c in LOSS_CAUSES:
            out["pdcp_lost_%s_kbyte_pm" % c] = a["lost_" + c] * kb
        return out

    def check(self) -> None:
        """Conservation: arrived = delivered + lost + queued (whole run)."""
        T = self.total
        queued = float(self.q.sum())
        err = T["arrived"] - T["delivered"] - T["lost"] - queued
        if abs(err) > 1e-6 * max(T["arrived"], 1.0) + 1.0:
            raise AssertionError("user-plane buffers: arrived %.6g != delivered %.6g + lost %.6g + queued %.6g"
                                 % (T["arrived"], T["delivered"], T["lost"], queued))
