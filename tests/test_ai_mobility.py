# SPDX-License-Identifier: MIT
"""RRM measurement prediction and the rule a3_pred (TR 38.744, since 2.4.0)."""
import numpy as np
import pytest

import handoverlab as hl
from handoverlab.channel.source import RadioSource
from handoverlab.engine.core import Engine
from handoverlab.rules.predict import (HoldPredictor, PredA3, Recorder, RidgeData, RidgePredictor, fit_predictor,
                                       window_features)
from handoverlab.simulate import run_world
from handoverlab.world import build_world

SHORT = {"run.duration_s": 12.0, "run.warmup_s": 2.0}


@pytest.fixture(scope="module")
def world():
    return build_world(hl.builtin_scenario("smoke").with_overrides(SHORT), 3)


def test_contract():
    from handoverlab.testing import check_rule
    check_rule("a3_pred")
    check_rule("a3_pred", {"case": "B", "skip": 2, "filter_option": 3})


def test_passive_rule_and_case_b_without_skipping_hand_over_as_a3(world):
    rules = [{"rule": "a3", "off_db": 2.0, "ttt_s": 0.32},
             {"rule": "a3_pred", "act": False},
             {"rule": "a3_pred", "case": "B", "skip": 2, "act": False},
             {"rule": "a3_pred", "case": "B", "skip": 0},
             {"rule": "a3_pred", "case": "B", "skip": 0, "filter_option": 3},
             {"rule": "a3", "off_db": 2.0, "ttt_s": 0.0},
             {"rule": "a3_pred", "case": "A", "predictor": "hold"}]
    fp = [r.fingerprint for r in run_world(world, rules)]
    assert fp[0] == fp[1] == fp[2] == fp[3] == fp[4]
    assert fp[5] == fp[6]                     # hold predictor, option 2: A3 without time-to-trigger
    assert fp[0] != fp[5]


def test_own_l3_series_equals_the_engine_filter_without_skipping(world):
    rule = PredA3(case="B", skip=0)
    eng = Engine(world, rule, False, None)
    for ch in RadioSource(world).chunks():
        eng.advance(ch)
    eng.finish()
    assert np.array_equal(rule.own, eng.meas)
    assert rule.stats()["mrrt"] == 0.0


def test_skipping_gives_the_measurement_reduction_rate(world):
    rec = Recorder()
    run_world(world, [PredA3(case="B", skip=s, record=rec) for s in (1, 2, 4)])
    for s, r in zip((1, 2, 4), rec.rules):
        st = r.stats()
        assert abs(st["mrrt"] - s / (s + 1.0)) < 0.01
        assert len(st["err_db"]) == s and all(n > 0 for n in st["err_n"])
        assert st["err_db"][-1] >= st["err_db"][0]


def test_hold_predicts_the_last_value():
    hist = np.array([[1.0, 2.0, 5.0], [0.0, 0.0, -3.0]])
    assert np.array_equal(HoldPredictor().predict(hist, 2), [[5.0, 5.0], [-3.0, -3.0]])


def test_ridge_learns_a_linear_trend_and_round_trips(tmp_path):
    d = RidgeData(4, 2, 3, 0.04)
    rng = np.random.default_rng(1)
    slope = rng.normal(0.0, 1.0, 500)
    off = rng.normal(-90.0, 5.0, 500)
    t = np.arange(4) * 2.0                            # samples of the window, stride 2 instants
    d.add(off[:, None] + slope[:, None] * t, off[:, None] + slope[:, None] * (t[-1] + np.arange(1, 4)))
    p = d.solve(1e-9)
    hist = np.array([[-80.0, -79.0, -78.0, -77.0]])    # +0.5 dB per instant
    assert np.allclose(p.predict(hist, 3), [[-76.5, -76.0, -75.5]], atol=1e-6)
    assert window_features(hist).shape == (1, 4) and p.n_parameters() == 12
    path = str(tmp_path / "m.json")
    p.save(path)
    q = RidgePredictor.load(path)
    assert np.array_equal(q.w, p.w) and q.stride == 2 and q.n_samples == 500
    with pytest.raises(ValueError):
        d + RidgeData(4, 1, 3, 0.04)
    with pytest.raises(ValueError):
        RidgeData(4, 2, 3, 0.04).solve()


def test_trained_model_from_a_file_and_its_checks(world, tmp_path):
    sc = hl.builtin_scenario("smoke").with_overrides(SHORT)
    path = str(tmp_path / "a.json")
    p = fit_predictor(sc, [101], path, case="A", pw_s=0.12, n_ow=4)
    assert p.horizons == 3 and p.stride == 1 and p.n_samples > 0
    res = hl.simulate(sc, [{"rule": "a3_pred", "predictor": "ridge", "weights": path, "pw_s": 0.12,
                            "ttt_s": 0.08}], seeds=[3])[0]
    assert res.params["weights"] == path and res.metrics["ue_minutes"] > 0
    with pytest.raises(ValueError, match="horizons"):
        run_world(world, [PredA3(predictor="ridge", weights=p, pw_s=0.32)])
    with pytest.raises(ValueError, match="stride"):
        run_world(world, [PredA3(case="B", predictor="ridge", weights=p, skip=1)])
    other = RidgePredictor(p.w, 1, 0.08)
    with pytest.raises(ValueError, match="measurement period"):
        run_world(world, [PredA3(predictor="ridge", weights=other, pw_s=0.12)])
    with pytest.raises(ValueError, match="weights"):
        hl.make_rule({"rule": "a3_pred", "predictor": "ridge"})
    with pytest.raises(ValueError):
        hl.make_rule({"rule": "a3_pred", "case": "C"})
    with pytest.raises(ValueError):
        hl.make_rule({"rule": "a3_pred", "pw_s": 0.32, "event_pw_s": 0.4})


def test_event_prediction_counters():
    r = PredA3(pw_s=0.08, ttt_s=0.08, etd_s=0.04)
    r.reset(type("C", (), {"measurement_period_s": 0.04, "n_users": 1, "n_sites": 3, "scenario": None,
                           "cell_carrier": None})())
    K = 30
    r.serv_hist = [np.array([0])] * K
    r.con_hist = [np.array([True])] * K
    r.t_hist = list(np.arange(K) * 0.04)
    r.ev_true = [np.array([[10, 0, 1, 0], [20, 0, 2, 0], [25, 0, 1, 0]])]
    r.ev_pred = [np.array([[11, 0, 1, 0], [20, 0, 1, 0], [27, 0, 1, 0], [3, 0, 1, 0]])]
    c = r.event_counts()                    # 11~10 true, 20 (cell 1) false, 27 vs 25 beyond the ETD, 3 too early
    assert (c["n3"], c["n1"], c["n2"]) == (1, 2, 2)
    assert c["f1"] == pytest.approx(2 * (1 / 3) * (1 / 3) / (2 / 3))
