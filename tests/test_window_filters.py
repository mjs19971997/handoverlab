# SPDX-License-Identifier: MIT
"""Moving-window qualities of radio link monitoring and beam failure detection (since 2.12.0):
``protocol.rlm_filter: window`` and ``radio.beams.bfd_filter: window`` (TS 38.133 8.1.2.2 and 8.5.2.2: the quality
"estimated over the last" evaluation period).  Defaults untouched, the window by hand, the step tests of the
requirements, the restart of beam failure detection on a new cell, and validation."""
import numpy as np
import pytest

import handoverlab as hl
from handoverlab import requirements as req
from handoverlab.channel.extended import ExtendedSource
from handoverlab.config import BeamConfig, ConfigError, ProtocolConfig
from handoverlab.engine.extended import ExtEngine
from handoverlab.engine.window import WindowMean

BEAMS = {"sectors": 3, "sector_az0_deg": 30.0, "n_ssb": 8, "panel": [8, 8], "tilt_deg": 102.0}
SHORT = {"mobility.users": 12, "run.duration_s": 10.0, "run.warmup_s": 1.0}
RULES = [{"rule": "a3", "name": "A3", "off_db": 3.0, "ttt_s": 0.256}]
DT = 0.01
QOUT = 10 ** (-8.0 / 10)          # protocol.qout_db
QOUT_LR = QOUT * 10 ** 0.4         # TS 38.133 Tables 8.1.2.1-1 / 8.5.2.1-1: 4 dB above Qout
DB = lambda x: 10 ** (x / 10.0)   # noqa: E731


def _sc(beam=None, **proto):
    b = dict(BEAMS, **(beam or {}))
    ov = dict(SHORT, **{"radio.beams": b})
    ov.update({"protocol." + k: v for k, v in proto.items()})
    return hl.builtin_scenario("urban-macro-tr37885-4ghz").with_overrides(ov)


def _fp(sc, seed=4):
    return [(r.fingerprint, r.metrics["failures_pm"]) for r in hl.run_world(hl.build_world(sc, seed), RULES)]


# ----------------------------------------------------------------------------- the window itself
def test_window_mean_by_hand():
    rng = np.random.default_rng(1)
    x = rng.random((3000, 4))
    w = WindowMean(np.array([1, 3, 10, 7]), 10)
    for k in range(3000):
        got = w.push(x[k])
        for u, n in enumerate((1, 3, 10, 7)):
            assert got[u] == pytest.approx(x[max(0, k - n + 1):k + 1, u].mean(), rel=1e-12)


def test_window_reset_mask_and_tail():
    w = WindowMean(np.array([4, 4]), 4, (3,))
    for k in range(6):
        w.push(np.full((2, 3), float(k)))
    w.reset(1)
    assert not w.full(1) and w.full(0)
    m = w.push(np.full((2, 3), 10.0), np.array([False, True]))     # user 0 keeps its window
    assert m[0].tolist() == [3.5] * 3 and m[1].tolist() == [10.0] * 3
    for _ in range(3):
        m = w.push(np.full((2, 3), 2.0), np.array([False, True]))
    assert w.full(1) and m[1].tolist() == [4.0] * 3                 # (10 + 2 + 2 + 2) / 4
    w.set_n(0, 2)
    assert w.n[0] == 2 and w.count[0] == 0


# ----------------------------------------------------------------------------- step tests (pre-registered F2-a..d)
def _first_indication(quality, period_steps, ind_steps, thr, window):
    """Step index of the first indication after a step from +10 dB to ``quality`` dB at step 0 (None: never)."""
    n = 300
    x = np.r_[np.full(n, DB(10.0)), np.full(400, DB(quality))]
    if window:
        w = WindowMean(np.array([period_steps]), period_steps)
        q = [w.push(np.array([v]))[0] for v in x]
    else:
        a = 1.0 - np.exp(-1.0 / period_steps)
        q, f = [], x[0]
        for v in x:
            f += a * (v - f)
            q.append(f)
    for k in range(n, len(x)):
        if k % ind_steps == 0 and q[k] < thr:
            return k - n
    return None


def test_bfd_step_detected_within_the_evaluation_period():
    # TS 38.133 Table 8.5.2.2-1 (FR1, T_SSB 20 ms): T_Evaluate_BFD_SSB = 100 ms; indications every 20 ms (8.5.4)
    n = int(round(req.bfd_evaluation_period(0.02) / DT))
    ind = int(round(req.bfd_indication_interval(0.02) / DT))
    assert (n, ind) == (10, 2)
    k = _first_indication(-20.0, n, ind, QOUT_LR, window=True)
    assert k is not None and k * DT <= 0.100 + 0.020 + 1e-9                         # F2-a
    assert _first_indication(-3.0, n, ind, QOUT_LR, window=True) is None            # F2-b
    k_exp = _first_indication(-20.0, n, ind, QOUT_LR, window=False)                 # F2-d: the old filter misses it
    assert k_exp is None or k_exp * DT > 0.120


def test_rlm_step_detected_within_the_evaluation_period():
    # TS 38.133 Table 8.1.2.2-1 (FR1, T_SSB 20 ms): T_Evaluate_out = 200 ms; indications every max(10 ms, T_SSB)
    T = req.rlm_evaluation_periods(0.02)
    n = int(round(T[0] / DT))
    k = _first_indication(-20.0, n, 2, QOUT, window=True)
    assert k is not None and k * DT <= 0.200 + 0.020 + 1e-9                         # F2-c
    k_exp = _first_indication(-20.0, n, 2, QOUT, window=False)
    assert k_exp is None or k_exp * DT > 0.220


# ----------------------------------------------------------------------------- engine: defaults and options
def test_defaults_unchanged():
    assert BeamConfig().bfd_filter == "exp" and ProtocolConfig().rlm_filter == "exp"
    d = _sc().to_dict()
    assert "bfd_filter" not in d["radio"]["beams"] and "rlm_filter" not in d["protocol"]
    base = _fp(_sc())
    assert _fp(_sc(beam={"bfd_filter": "exp"}, rlm_filter="exp")) == base


def test_options_change_the_run_and_repeat():
    base = _fp(_sc())
    for sc in (_sc(beam={"bfd_filter": "window"}), _sc(rlm_filter="window"),
               _sc(beam={"bfd_filter": "window", "ssb_sinr": "ssb"}, rlm_filter="window")):
        a = _fp(sc)
        assert a == _fp(sc) and a != base
    assert "bfd_filter" in _sc(beam={"bfd_filter": "window"}).to_dict()["radio"]["beams"]
    assert _sc(rlm_filter="window").to_dict()["protocol"]["rlm_filter"] == "window"


def test_rlm_window_without_beams_and_numba_falls_back():
    pytest.importorskip("numba")
    sc = hl.builtin_scenario("urban-macro-tr37885-4ghz").with_overrides(
        {"mobility.users": 10, "run.duration_s": 6.0, "run.warmup_s": 1.0, "protocol.rlm_filter": "window"})
    assert _fp(sc) == _fp(sc.with_overrides({"run.backend": "numba"}))
    assert _fp(sc) != _fp(sc.with_overrides({"protocol.rlm_filter": "exp"}))


def test_engine_bfd_quality_is_the_window_of_the_serving_beam():
    sc = _sc(beam={"bfd_filter": "window", "ssb_sinr": "ssb"})
    w = hl.build_world(sc, 5)
    e = ExtEngine(w, hl.make_rule(RULES[0]))
    seen = {"n": 0}
    o_bs = e._beam_step
    hist = {}

    def beam_step(i, ch, t, ssb_q, ilm, ln, totc):
        sb0 = e.sb.copy()
        out = o_bs(i, ch, t, ssb_q, ilm, ln, totc)
        hb = e.has_b[e.serv] & (e.state == 0) & (e.sb == sb0)   # a recovery in the step changes sb afterwards
        for u in np.nonzero(hb)[0]:
            n = int(e.bfd_win.count[u])
            if n == int(e.bfd_win.n[u]) and n == 10:
                # by hand: the last 10 per-beam SS-SINRs of this user on this cell, beam sb[u]
                h = hist.get(u)
                if h is not None and len(h) >= 10 and all(c == e.serv[u] for c, _ in h[-10:]):
                    want = np.mean([row[e.sb[u]] for _, row in h[-10:]])
                    assert e.bfd_q[u] == pytest.approx(want, rel=1e-9)
                    seen["n"] += 1
        return out

    o_push = e.bfd_win.push

    def push(x, mask=None):
        for u in np.nonzero(mask)[0]:
            hist.setdefault(u, []).append((int(e.serv[u]), np.array(x[u])))
        return o_push(x, mask)

    e._beam_step = beam_step
    e.bfd_win.push = push
    for ch in ExtendedSource(w, 200).chunks():
        e.advance(ch)
    assert seen["n"] > 100


def test_bfd_restarts_on_a_new_cell():
    # pre-registered F1-c: no beam failure (BFR start) before one T_Evaluate_BFD_SSB plus three indications
    # after a user joins a cell
    sc = _sc(beam={"bfd_filter": "window", "ssb_sinr": "ssb"}).with_overrides({"mobility.users": 30,
                                                                              "run.duration_s": 15.0})
    w = hl.build_world(sc, 7)
    e = ExtEngine(w, hl.make_rule(RULES[0]), "full")
    for ch in ExtendedSource(w, 400).chunks():
        e.advance(ch)
    e.finish()
    last_join = {}
    n_bf = 0
    # the window is full with its 10th sample, 90 ms after the join (10 samples of 10 ms cover 100 ms); the BFR
    # starts at the third indication, two indication intervals later
    t_min = req.bfd_evaluation_period(0.02) - DT + 2 * req.bfd_indication_interval(0.02) - 1e-6
    for t, u, ev, *_ in e.trace_log:
        if ev in ("attach", "reestablish"):
            last_join[u] = t
        elif ev == "beam_failure":
            n_bf += 1
            if u in last_join:
                assert t - last_join[u] >= t_min, (u, t, last_join[u])
    assert n_bf > 0


@pytest.mark.parametrize("over, word", [
    ({"radio.beams": dict(BEAMS, bfd_filter="mean")}, "bfd_filter"),
    ({"protocol.rlm_filter": "boxcar"}, "rlm_filter"),
])
def test_validation(over, word):
    with pytest.raises(ConfigError, match=word):
        hl.builtin_scenario("urban-macro-tr37885-4ghz").with_overrides(over)
