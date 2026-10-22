# SPDX-License-Identifier: MIT
"""RRM measurement prediction in time and Event A3 on predicted results (3GPP TR 38.744; since 2.4.0).

The rule ``a3_pred`` follows the use cases of TR 38.744 V19.0.1 for an
intra-frequency, cell-level, single-cell prediction of the L3 RSRP from past
L3 results of the same cell (RRM sub-use case 2, clause 4.2):

* **case A** (clause 5.2.1.1, second study goal): every measurement instant
  the results of the next ``pw_s`` (the prediction window, PW) are predicted
  from the observation window (OW).  With ``act`` the handover follows
  handover model option 2 of clause 5.5.1: the network sends the command once
  the entering condition of the predicted event holds on the actual result.
  Here: the rule reports when the A3 entering condition holds now and is
  predicted to hold at every predicted instant within ``ttt_s``; the engine's
  time-to-trigger is then 0.  The preparation starts at the report (the
  instant t2 of TR 38.744 Figure 5.5.1-2), not at the prediction (t0).
* **case B** (first study goal, measurement reduction): after each measured
  instant the next ``skip`` instants are not measured but predicted; MRRT =
  skip / (skip + 1).  The rule keeps its own L3 series, filtered with option
  1, 2 or 3 of clause 4.2, and evaluates Event A3 with the usual
  time-to-trigger on it (handover model option 3).
* ``act=False``: the rule hands over exactly as :class:`~handoverlab.rules.A3`
  with the same offset and time-to-trigger and only records its predictions.

Predictors: ``"hold"`` -- sample and hold, the non-AI baseline of clause 5.1
("the actual measurement result of the last time instance in OW is held for
PW") -- and ``"ridge"`` -- a linear autoregressive model per horizon fitted by
ridge regression (:func:`fit_predictor`) on simulated runs whose seeds must not
be the test seeds (clause 5.1).  Any object with the methods of
:class:`HoldPredictor` can be passed instead.

Statistics read after a run (:meth:`PredA3.stats`): the prediction accuracy of
clause 5.2.1.1 (mean absolute difference between the predicted and the ground
truth L3 RSRP of the same cell, per horizon; the ground truth is the engine's
L3 result with full measurement) over the ``top_k`` strongest cells of each
connected user at the prediction origin, the measurement reduction rate MRRT
and, in case A, the counters n1, n2, n3, precision, recall and F1 score of
the indirect prediction of Event A3 (clause 5.3.1, maximum ETD ``etd_s``).

See ``docs/guides/ai-mobility.md`` for what TR 38.744 models and this rule does
not.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

from .base import BaselineRule

EPS = 1e-9


# ---------------------------------------------------------------------------
# predictors
# ---------------------------------------------------------------------------
class HoldPredictor:
    """Sample and hold: the last value of the observation window for every horizon."""
    kind = "hold"
    n_ow = 1                 # samples of the observation window needed
    stride = None            # any spacing of the samples
    horizons = None          # any number of horizons

    def predict(self, hist: np.ndarray, n: int) -> np.ndarray:
        """Predictions (..., n) for horizons 1..n from ``hist`` (..., n_ow), oldest sample first."""
        return np.repeat(hist[..., -1:], n, axis=-1)

    def describe(self) -> Dict[str, Any]:
        return dict(kind=self.kind)


def window_features(hist: np.ndarray) -> np.ndarray:
    """Inputs of the ridge model: F(t0) - F(t0 - j s) for j = 1..n_ow-1 and a constant 1 (shape (..., n_ow))."""
    last = hist[..., -1:]
    d = last - hist[..., -2::-1]
    return np.concatenate([d, np.ones(hist.shape[:-1] + (1,))], axis=-1)


class RidgePredictor:
    """Linear autoregressive predictor of the L3 RSRP of one cell, one weight vector per horizon.

    ``F(t0 + h) = F(t0) + w_h . [F(t0) - F(t0 - s), ..., F(t0) - F(t0 - (n_ow-1) s), 1]`` with the stride ``s``
    (measurement instants between the samples of the observation window) and horizons h = 1..H in measurement
    instants of ``dt_s``.
    """
    kind = "ridge"

    def __init__(self, weights, stride: int, dt_s: float, lam: float = 1.0, n_samples: int = 0,
                 info: Optional[Dict[str, Any]] = None):
        self.w = np.asarray(weights, dtype=float)          # (n_ow, H)
        if self.w.ndim != 2 or self.w.shape[0] < 2:
            raise ValueError("ridge weights must have the shape (n_ow, H) with n_ow >= 2")
        self.n_ow, self.horizons = self.w.shape
        self.stride, self.dt_s, self.lam = int(stride), float(dt_s), float(lam)
        self.n_samples = int(n_samples)
        self.info = dict(info or {})

    def predict(self, hist: np.ndarray, n: int) -> np.ndarray:
        if n > self.horizons:
            raise ValueError("the ridge model predicts %d horizons, %d asked" % (self.horizons, n))
        return hist[..., -1:] + window_features(hist) @ self.w[:, :n]

    def n_parameters(self) -> int:
        return int(self.w.size)

    def describe(self) -> Dict[str, Any]:
        return dict(kind=self.kind, n_ow=self.n_ow, horizons=self.horizons, stride=self.stride, dt_s=self.dt_s,
                    lam=self.lam, n_samples=self.n_samples)

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.describe(), weights=self.w.tolist(), info=self.info)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RidgePredictor":
        return cls(d["weights"], d["stride"], d["dt_s"], d.get("lam", 1.0), d.get("n_samples", 0), d.get("info"))

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(self.to_dict(), f, indent=1)

    @classmethod
    def load(cls, path: str) -> "RidgePredictor":
        with open(path, encoding="utf-8") as f:
            return cls.from_dict(json.load(f))


class RidgeData:
    """Sums X'X and X'Y of a ridge regression; data sets add up (``a + b``)."""

    def __init__(self, n_ow: int, stride: int, horizons: int, dt_s: float):
        self.n_ow, self.stride, self.horizons, self.dt_s = int(n_ow), int(stride), int(horizons), float(dt_s)
        self.xx = np.zeros((self.n_ow, self.n_ow))
        self.xy = np.zeros((self.n_ow, self.horizons))
        self.n = 0

    def add(self, hist: np.ndarray, future: np.ndarray) -> None:
        """Samples: ``hist`` (N, n_ow) observation windows, ``future`` (N, H) the values at horizons 1..H."""
        x = window_features(hist)
        y = future - hist[:, -1:]
        self.xx += x.T @ x
        self.xy += x.T @ y
        self.n += len(x)

    def __add__(self, other: "RidgeData") -> "RidgeData":
        if (self.n_ow, self.stride, self.horizons) != (other.n_ow, other.stride, other.horizons) \
                or abs(self.dt_s - other.dt_s) > EPS:
            raise ValueError("ridge data sets with different windows cannot be added")
        out = RidgeData(self.n_ow, self.stride, self.horizons, self.dt_s)
        out.xx, out.xy, out.n = self.xx + other.xx, self.xy + other.xy, self.n + other.n
        return out

    def solve(self, lam: float = 1.0, info: Optional[Dict[str, Any]] = None) -> RidgePredictor:
        if self.n == 0:
            raise ValueError("no training samples")
        reg = np.eye(self.n_ow) * lam
        reg[-1, -1] = 0.0                                  # the constant is not penalised
        w = np.linalg.solve(self.xx + reg, self.xy)
        return RidgePredictor(w, self.stride, self.dt_s, lam, self.n, info)


class Recorder:
    """Keeps the rule objects that ran.

    :func:`~handoverlab.simulate.run_world` gives every engine a copy of a rule object; a recorder passed as
    ``record`` is shared by the copies, so that their statistics can be read after the run::

        rec = Recorder()
        run_world(world, [PredA3(act=False, record=rec)])
        rec.rules[0].stats()
    """

    def __init__(self):
        self.rules: List[Any] = []

    def __deepcopy__(self, memo):
        return self


def _make_predictor(predictor, weights):
    if not isinstance(predictor, str):
        return predictor
    if predictor == "hold":
        return HoldPredictor()
    if predictor == "ridge":
        if weights is None:
            raise ValueError("predictor 'ridge' needs weights (a file written by fit_predictor or a dict)")
        if isinstance(weights, RidgePredictor):
            return weights
        return RidgePredictor.from_dict(weights) if isinstance(weights, dict) else RidgePredictor.load(weights)
    raise ValueError("unknown predictor %r (hold, ridge or an object with predict())" % predictor)


def _top_mask(meas: np.ndarray, k: int) -> np.ndarray:
    """(U, M) mask of the k strongest cells of every user."""
    k = min(int(k), meas.shape[1])
    idx = np.argpartition(-meas, k - 1, axis=1)[:, :k]
    mask = np.zeros(meas.shape, dtype=bool)
    np.put_along_axis(mask, idx, True, axis=1)
    return mask


# ---------------------------------------------------------------------------
# the rule
# ---------------------------------------------------------------------------
class PredA3(BaselineRule):
    """Event A3 on predicted L3 measurements, TR 38.744 case A (option 2) or case B (option 3).

    off_db         A3 offset [dB]
    ttt_s          time-to-trigger [s]; in case A with ``act`` the span that must be predicted to fulfil the
                   entering condition (the engine's time-to-trigger is then 0)
    case           "A" (prediction ahead, no skipping) or "B" (measurement skipping)
    predictor      "hold" (sample and hold), "ridge" (needs ``weights``) or an object with ``predict()``
    weights        ridge model: a JSON file written by :func:`fit_predictor`, its dict, or a RidgePredictor
    pw_s           case A: prediction window [s]
    skip           case B: skipped instants after every measured one (MRRT = skip / (skip + 1))
    filter_option  case B: L3 filtering at a measured instant after skipped ones (TR 38.744 clause 4.2):
                   1 on the last (predicted) value, 2 none (L1 result), 3 on the last actual result
    act            True: hand over on the predictions; False: hand over as A3 and only record predictions
    top_k          cells per user in the accuracy statistics (the strongest at the prediction origin)
    etd_s          maximum ETD of the event prediction score (TR 38.744 clause 5.3.1)
    event_pw_s     case A: how far ahead the event is predicted (default ``pw_s``; at most ``pw_s``)
    record         a :class:`Recorder` that keeps the rule object of every run (for :meth:`stats`)
    """

    def __init__(self, off_db: float = 2.0, ttt_s: float = 0.32, case: str = "A",
                 predictor: Union[str, Any] = "hold", weights: Union[None, str, dict, RidgePredictor] = None,
                 pw_s: float = 0.32, skip: int = 1, filter_option: int = 1, act: bool = True, top_k: int = 4,
                 etd_s: float = 0.08, event_pw_s: Optional[float] = None,
                 record: Optional[Recorder] = None, name: str = "A3-pred"):
        super().__init__(name)
        if ttt_s < 0 or pw_s <= 0 or etd_s < 0:
            raise ValueError("ttt_s and etd_s must be >= 0 and pw_s > 0")
        if case not in ("A", "B"):
            raise ValueError("case must be 'A' or 'B'")
        if int(skip) < 0 or int(filter_option) not in (1, 2, 3) or int(top_k) < 1:
            raise ValueError("skip must be >= 0, filter_option 1, 2 or 3 and top_k >= 1")
        self.off_db, self.ttt_s, self.case = float(off_db), float(ttt_s), case
        self.pw_s, self.skip, self.filter_option = float(pw_s), int(skip), int(filter_option)
        self.act, self.top_k, self.etd_s = bool(act), int(top_k), float(etd_s)
        self.event_pw_s = self.pw_s if event_pw_s is None else float(event_pw_s)
        if not 0 < self.event_pw_s <= self.pw_s + EPS:
            raise ValueError("event_pw_s must lie in (0, pw_s]")
        self.weights, self.record = weights, record
        self.pred = _make_predictor(predictor, weights)
        self.predictor = predictor if isinstance(predictor, str) else type(predictor).__name__

    def params(self):
        w = self.weights if isinstance(self.weights, (str, type(None))) else "inline"
        return dict(off_db=self.off_db, ttt_s=self.ttt_s, case=self.case, predictor=self.predictor, weights=w,
                    pw_s=self.pw_s, skip=self.skip, filter_option=self.filter_option, act=self.act,
                    top_k=self.top_k, etd_s=self.etd_s, event_pw_s=self.event_pw_s)

    # -- set-up ---------------------------------------------------------
    def _steps(self, s: float) -> int:
        return int(round(s / self.dt + EPS))

    def reset(self, ctx):
        super().reset(ctx)
        if self.record is not None:
            self.record.rules.append(self)
        self.dt = float(ctx.measurement_period_s)
        U, M = ctx.n_users, ctx.n_sites
        p = self.pred
        p_dt = getattr(p, "dt_s", None)
        if p_dt is not None and abs(p_dt - self.dt) > 1e-6:
            raise ValueError("the predictor was trained with a measurement period of %g s, the run has %g s"
                             % (p_dt, self.dt))
        self.n_ow = int(getattr(p, "n_ow", 1))
        self.n_ttt = self._steps(self.ttt_s)
        self.n_pw = self._steps(self.pw_s) if self.case == "A" else self.skip
        self.n_etd = self._steps(self.etd_s)
        self.n_ev = max(1, min(self._steps(self.event_pw_s), self.n_pw))
        stride = 1 if self.case == "A" else self.skip + 1
        if getattr(p, "stride", None) not in (None, stride):
            raise ValueError("the predictor uses a stride of %s instants, case %s with skip %d needs %d"
                             % (p.stride, self.case, self.skip, stride))
        if getattr(p, "horizons", None) is not None and p.horizons < self.n_pw:
            raise ValueError("the predictor has %d horizons, %d needed" % (p.horizons, self.n_pw))
        if self.case == "A" and self.act and self.n_pw < self.n_ttt:
            raise ValueError("case A with act needs pw_s >= ttt_s")
        sc = getattr(ctx, "scenario", None)
        self.warmup = float(sc.run.warmup_s) if sc is not None else 0.0
        self.k = -1
        self.err_sum = np.zeros(self.n_pw)
        self.err_n = np.zeros(self.n_pw, dtype=np.int64)
        self.n_meas = self.n_skip = 0
        self.hist = np.zeros((self.n_ow, U, M))              # observation window (oldest first), filled from the right
        self.n_hist = 0
        if self.case == "A":
            self.pring = np.zeros((self.n_pw + 1, U, M, self.n_pw))   # predictions made at the last instants
            self.pmask = np.zeros((self.n_pw + 1, U, M), dtype=bool)
            self.pvalid = np.zeros(self.n_pw + 1, dtype=bool)
            self.run = np.zeros((U, M), dtype=np.int64)           # instants the actual A3 condition has held
            self.ev_true: List[np.ndarray] = []
            self.ev_pred: List[np.ndarray] = []
            self.serv_hist: List[np.ndarray] = []
            self.con_hist: List[np.ndarray] = []
            self.t_hist: List[float] = []
            self.cur_cond = None
        else:
            if sc is not None and sc.protocol.meas_periods != "sample":
                raise ValueError("case B needs protocol.meas_periods 'sample'")
            if ctx.cell_carrier is not None:
                raise ValueError("case B supports one carrier")
            self.a = self._l3_coefficient(sc)
            self.own = None                                   # own L3 series (U, M)
            self.last_act = None
            self.cache = None                                 # predictions of the skipped instants (U, M, skip)
            self.cmask = None

    def _l3_coefficient(self, sc) -> float:
        """Coefficient of the engine's L3 filter (see Engine.__init__)."""
        from ..measurement import l3_coefficient
        from ..requirements import l3_reference_period
        if sc is None:
            return l3_coefficient(4, self.dt, 0.2)
        P, R = sc.protocol, sc.radio
        x_ref = l3_reference_period(R.carrier_ghz, P.ssb_period_s, P.fr2_power_class) \
            if P.rrc_detail == "3gpp" else 0.2
        return float(l3_coefficient(P.l3_k, self.dt, x_ref))

    def _push(self, values: np.ndarray) -> None:
        self.hist[:-1] = self.hist[1:]
        self.hist[-1] = values
        self.n_hist = min(self.n_hist + 1, self.n_ow)

    # -- per measurement instant ----------------------------------------
    def _update(self, obs) -> None:
        if obs.step == getattr(self, "_last_step", None):
            return
        self._last_step = obs.step
        self.k += 1
        counted = obs.t >= self.warmup - EPS
        if self.case == "A":
            self._update_a(obs, counted)
        else:
            self._update_b(obs, counted)

    def _update_a(self, obs, counted) -> None:
        k, H = self.k, self.n_pw
        meas = obs.meas_dbm
        if counted:                                           # accuracy of earlier predictions for this instant
            for h in range(1, H + 1):
                i = (k - h) % (H + 1)
                if k - h >= 0 and self.pvalid[i]:
                    m = self.pmask[i]
                    self.err_sum[h - 1] += np.abs(self.pring[i][..., h - 1][m] - meas[m]).sum()
                    self.err_n[h - 1] += int(m.sum())
        self._push(meas)
        i = k % (H + 1)
        if self.n_hist >= self.n_ow:
            pred = self.pred.predict(np.moveaxis(self.hist, 0, -1), H)
            self.pring[i] = pred
            self.pmask[i] = _top_mask(meas, self.top_k) & obs.connected[:, None]
            self.pvalid[i] = True
        else:
            self.pvalid[i] = False
            pred = None
        self.n_meas += int(counted)
        # Event A3 on actual results, and its prediction (indirect event prediction, TR 38.744 clause 4.3)
        ar = np.arange(len(obs.serving))
        cond = (obs.gap_db > self.off_db) & obs.connected[:, None]
        cond[ar, obs.serving] = False
        self.run = np.where(cond, self.run + 1, 0)
        self.cur_cond = cond
        self.serv_hist.append(np.array(obs.serving, dtype=np.int32))
        self.con_hist.append(np.array(obs.connected, dtype=bool))
        self.t_hist.append(float(obs.t))
        need = self.n_ttt + 1
        u, m = np.nonzero(self.run == need)
        self.ev_true.append(np.column_stack([np.full(len(u), k), u, m, obs.serving[u]]))
        self.pcond = None
        if pred is not None:
            pgap = pred - pred[ar, obs.serving][:, None, :]       # (U, M, H) predicted neighbour minus serving
            pc = (pgap > self.off_db) & obs.connected[:, None, None]
            pc[ar, obs.serving, :] = False
            self.pcond = pc
            # run length at k + E: trailing true predicted instants, plus the actual run if all of them are true
            E = self.n_ev
            tail = np.cumprod(pc[..., E - 1::-1], axis=-1).sum(-1)
            rune = np.where(tail == E, self.run + E, tail)
            u, m = np.nonzero(rune == need)
            self.ev_pred.append(np.column_stack([np.full(len(u), k + E), u, m, obs.serving[u]]))

    def _update_b(self, obs, counted) -> None:
        # instants k with k mod (skip + 1) = 0 are measured and enter the observation window (stride skip + 1);
        # the others are predicted from it once the window is full, and measured before that
        l1 = obs.l1_dbm if obs.l1_dbm is not None else obs.meas_dbm
        phase = self.k % (self.skip + 1)
        if self.own is None:                                  # the first sample initialises the filter (F_0 = M_1)
            self.own = np.array(l1, dtype=float, copy=True)
            self.last_act = self.own.copy()
        elif phase > 0 and self.cache is not None:            # skipped: the prediction takes the place of the result
            self.own = self.cache[..., phase - 1].copy()
            self.n_skip += int(counted)
            if counted:
                m = self.cmask
                self.err_sum[phase - 1] += np.abs(self.own[m] - obs.meas_dbm[m]).sum()
                self.err_n[phase - 1] += int(m.sum())
            return
        else:
            a, fo = self.a, self.filter_option
            if fo == 1:                                       # on the last value, predicted or not
                self.own += a * (l1 - self.own)
            elif fo == 2:                                     # no L3 filtering
                self.own = np.array(l1, dtype=float, copy=True)
            else:                                             # on the last actual result
                self.own = self.last_act + a * (l1 - self.last_act)
            self.last_act = self.own.copy()
        self.n_meas += int(counted)
        if phase == 0:
            self._push(self.own)
            if self.skip > 0 and self.n_hist >= self.n_ow:
                self.cache = self.pred.predict(np.moveaxis(self.hist, 0, -1), self.skip)
                self.cmask = _top_mask(obs.meas_dbm, self.top_k) & obs.connected[:, None]
            else:
                self.cache = None

    # -- hooks ------------------------------------------------------------
    def a3_offsets(self, obs):
        self._update(obs)
        return self.off_db

    def time_to_trigger(self, obs):
        return 0.0 if (self.act and self.case == "A") else self.ttt_s

    def entering(self, obs, offsets):
        self._update(obs)
        if not self.act:
            return None
        if self.case == "A":
            cond = self.cur_cond.copy()
            if self.pcond is not None and self.n_ttt > 0:
                cond &= self.pcond[..., :self.n_ttt].all(-1)
            elif self.n_ttt > 0:                              # no prediction yet: no early report
                cond[:] = False
            return cond, obs.gap_db - self.off_db
        ar = np.arange(len(obs.serving))
        gap = self.own - self.own[ar, obs.serving][:, None]
        return gap > self.off_db, gap - self.off_db

    # -- results ----------------------------------------------------------
    def stats(self) -> Dict[str, Any]:
        """Accuracy per horizon (sums and means), MRRT and, in case A, the event prediction counters."""
        n = np.maximum(self.err_n, 1)
        tot = self.n_meas + self.n_skip
        out = dict(err_sum=self.err_sum.tolist(), err_n=self.err_n.tolist(),
                   err_db=(self.err_sum / n).tolist(),
                   err_avg_db=float(self.err_sum.sum() / max(self.err_n.sum(), 1)),
                   n_measured=int(self.n_meas), n_skipped=int(self.n_skip),
                   mrrt=float(self.n_skip / tot) if tot else 0.0)
        if self.case == "A":
            out.update(self.event_counts())
        return out

    def event_counts(self) -> Dict[str, float]:
        """Counters n1 (false), n2 (missed), n3 (true) of the indirect A3 prediction and P, R, F1 (clause 5.3.1)."""
        serv = np.array(self.serv_hist)
        con = np.array(self.con_hist)
        t = np.array(self.t_hist)
        K = len(t)
        lo_off = self.n_ev + self.n_ttt + 1

        def valid(ev):
            if not len(ev):
                return ev
            keep = []
            for row in ev:
                k, u = int(row[0]), int(row[1])
                a, b = k - lo_off, k
                if a < 0 or b >= K or t[k] < self.warmup - EPS:
                    continue
                if np.all(serv[a:b + 1, u] == row[3]) and np.all(con[a:b + 1, u]):
                    keep.append(row)
            return np.array(keep, dtype=np.int64).reshape(-1, 4)

        tru = valid(np.concatenate(self.ev_true) if self.ev_true else np.zeros((0, 4), dtype=np.int64))
        prd = valid(np.concatenate(self.ev_pred) if self.ev_pred else np.zeros((0, 4), dtype=np.int64))
        groups: Dict[Tuple[int, int, int], Tuple[list, list]] = {}
        for row in tru:
            groups.setdefault((row[1], row[2], row[3]), ([], []))[0].append(int(row[0]))
        for row in prd:
            groups.setdefault((row[1], row[2], row[3]), ([], []))[1].append(int(row[0]))
        n3 = 0
        for tk, pk in groups.values():
            used = [False] * len(tk)
            for p in sorted(pk):                              # greedy: the nearest unused ground-truth event
                best, bd = -1, self.n_etd + 1
                for j, q in enumerate(tk):
                    if not used[j] and abs(p - q) < bd:
                        best, bd = j, abs(p - q)
                if best >= 0:
                    used[best] = True
                    n3 += 1
        n1, n2 = len(prd) - n3, len(tru) - n3
        prec = n3 / (n1 + n3) if n1 + n3 else float("nan")
        rec = n3 / (n2 + n3) if n2 + n3 else float("nan")
        f1 = 2 * prec * rec / (prec + rec) if (n3 and prec + rec > 0) else 0.0
        return dict(n1=n1, n2=n2, n3=n3, precision=prec, recall=rec, f1=f1)


# ---------------------------------------------------------------------------
# training
# ---------------------------------------------------------------------------
class _Collector(BaselineRule):
    """A3 that accumulates ridge training data from the engine's L3 results (full measurement)."""

    def __init__(self, data: Sequence[RidgeData], top_k: int, off_db: float = 2.0, ttt_s: float = 0.32):
        super().__init__("collector")
        self.top_k, self.off_db, self.ttt_s = int(top_k), float(off_db), float(ttt_s)
        self.shared = Recorder()                            # shared by the copy that runs: holds the data sets
        self.shared.rules = list(data)
        self.data = self.shared.rules
        self.span = max((d.n_ow - 1) * d.stride + d.horizons for d in self.data)

    def reset(self, ctx):
        super().reset(ctx)
        self.data = self.shared.rules
        L = self.span + 1
        self.ring = np.zeros((L, ctx.n_users, ctx.n_sites))
        self.cring = np.zeros((L, ctx.n_users), dtype=bool)
        self.k = -1
        self._last = None

    def a3_offsets(self, obs):
        if obs.step != self._last:
            self._last = obs.step
            self.k += 1
            L = len(self.ring)
            self.ring[self.k % L] = obs.meas_dbm
            self.cring[self.k % L] = obs.connected
            for d in self.data:
                k0 = self.k - d.horizons                    # origin whose future is now complete
                first = k0 - (d.n_ow - 1) * d.stride
                if first < 0:
                    continue
                org = self.ring[k0 % L]
                mask = _top_mask(org, self.top_k) & self.cring[k0 % L][:, None]
                hist = np.stack([self.ring[(first + j * d.stride) % L][mask] for j in range(d.n_ow)], axis=-1)
                fut = np.stack([self.ring[(k0 + h) % L][mask] for h in range(1, d.horizons + 1)], axis=-1)
                d.add(hist, fut)
        return self.off_db

    def time_to_trigger(self, obs):
        return self.ttt_s


def collect(scenario, seeds: Sequence[int], windows: Sequence[Tuple[int, int, int]], top_k: int = 4,
            progress=None) -> List[RidgeData]:
    """Ridge training data from runs of ``scenario`` on ``seeds`` (legacy A3, full measurement).

    ``windows``: (n_ow, stride, horizons) per data set.  The seeds must not be test seeds (TR 38.744 clause 5.1).
    """
    from ..simulate import run_world
    from ..world import build_world
    dt = scenario.protocol.l1_period_s
    data = [RidgeData(n, s, h, dt) for n, s, h in windows]
    for seed in seeds:
        world = build_world(scenario, int(seed))
        run_world(world, [_Collector(data, top_k)])
        if progress:
            progress(seed)
    return data


def fit_predictor(scenario, seeds: Sequence[int], path: Optional[str] = None, case: str = "A", pw_s: float = 0.32,
                  skip: int = 1, n_ow: int = 8, lam: float = 1.0, top_k: int = 4) -> RidgePredictor:
    """Train the ridge predictor of ``a3_pred`` for ``case`` on runs of ``scenario`` and save it to ``path``.

    Case A predicts ``pw_s`` ahead from consecutive instants, case B the ``skip`` instants after a measured one
    from measured instants.  Use seeds that never appear among the test seeds; test with
    ``{"rule": "a3_pred", "case": ..., "predictor": "ridge", "weights": path}``.
    """
    dt = scenario.protocol.l1_period_s
    if case == "A":
        stride, H = 1, int(round(pw_s / dt + EPS))
    else:
        stride, H = skip + 1, skip
    data = collect(scenario, seeds, [(n_ow, stride, H)], top_k)[0]
    p = data.solve(lam, info=dict(case=case, seeds=[int(s) for s in seeds], scenario=scenario.name))
    if path:
        p.save(path)
    return p


__all__ = ["PredA3", "Recorder", "HoldPredictor", "RidgePredictor", "RidgeData", "collect", "fit_predictor",
           "window_features"]
