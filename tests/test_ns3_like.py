# SPDX-License-Identifier: MIT
"""The ns-3-like setting (handoverlab.verify.ns3.NS3_LIKE_SETTING, protocol.ns3_*) without ns-3: detection timing,
defaults untouched, validation, and the bridge / command line rows."""
import copy
import json
import os

import numpy as np
import pytest

import handoverlab as hl
from handoverlab import ns3bridge as nb
from handoverlab.cli import main
from handoverlab.config import ConfigError, ProtocolConfig
from handoverlab.engine import core
from handoverlab.verify import ns3

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "ns3bridge")
NS3 = {"protocol.ns3_oos_rx": 200.0, "protocol.cmd_during_t310": "lost", "protocol.rlm_holdoff_s": 0.0,
       "protocol.exec_can_fail": False}
SHORT = {"mobility.users": 12, "run.duration_s": 20.0, "run.warmup_s": 2.0, "radio.isolation": 1.0,
         "mobility.profile": "veh30", "protocol.lm_load": 1.0}
RULES = [{"rule": "a3", "name": "A3", "off_db": 3.0, "ttt_s": 0.32},
         {"rule": "a3", "name": "A3b", "off_db": 1.0, "ttt_s": 0.08}]
V1 = {"schema": 1, "name": "V1", "ns3": {
    "scenario": "ns3-urban-3.5ghz", "rule": "a3", "users": 20, "duration_s": 180, "discard_s": 60,
    "conditions": {"isd_m": [200, 300], "speed_mps": [10, 28], "ttt_ms": [80, 320], "offset_db": [3],
                   "traffic": ["light"], "fading": [False]},
    "seeds": {"first": 401, "last": 405}, "outputs": {"events": True, "ctrl_csv": True}}}


def _state(n):
    return dict(run=np.zeros(n, bool), c_o=np.zeros(n), c_i=np.zeros(n), n_o=np.zeros(n, int),
                n_i=np.zeros(n, int))


def _step(P, s, sl, rx, mon=None, live=None):
    n = len(sl)
    mon = np.ones(n, bool) if mon is None else mon
    live = np.ones(n, bool) if live is None else live
    return core.rlm_count(P, np.asarray(sl, float), 10 ** -0.8, 10 ** -0.6, s["run"], s["c_o"], s["c_i"], s["n_o"],
                          s["n_i"], mon, live, np.full(n, rx))


def test_out_of_sync_after_the_counted_receptions():
    """200 receptions below Qout give out-of-sync (N310 = 1 starts T310); one reception at or above Qout restarts
    the count; in-sync needs 100 receptions above Qin while T310 runs (NrUePhy::RlfDetection of 5G-LENA v5.1)."""
    P = ProtocolConfig(ns3_oos_rx=200.0)
    s = _state(1)
    bad, good = [0.01], [1.0]
    steps = 0
    while True:
        steps += 1
        if _step(P, s, bad, 2.6)[0]:
            break
    assert steps == int(np.ceil(200 / 2.6))                    # 77 steps of 10 ms: 0.77 s at 260 receptions/s
    assert s["run"][0] and s["c_o"][0] == 0
    # while T310 runs, in-sync after 100 receptions above Qin; a reception between Qout and Qin restarts it
    for _ in range(20):
        _step(P, s, good, 2.6)
    _step(P, s, [10 ** -0.7], 2.6)                              # -7 dB: not above Qin
    assert s["c_i"][0] == 0 and s["run"][0]
    k = 0
    while s["run"][0]:
        k += 1
        _step(P, s, good, 2.6)
    assert k == int(np.ceil(100 / 2.6))
    # a single good reception restarts the out-of-sync count
    s = _state(1)
    for _ in range(70):
        _step(P, s, bad, 2.6)
    _step(P, s, good, 2.6)
    assert s["c_o"][0] == 0 and not s["run"][0]
    # N310 = 2: two consecutive indications, the second after another 200 receptions
    P2 = ProtocolConfig(ns3_oos_rx=200.0, n310=2)
    s = _state(1)
    first = next(i for i in range(1, 1000) if _step(P2, s, bad, 2.6)[0] or s["n_o"][0] == 1)
    second = next(i for i in range(1, 1000) if _step(P2, s, bad, 2.6)[0])
    assert first == second == int(np.ceil(200 / 2.6))
    # users that are not monitored or not yet live (protocol.rlm_holdoff_s) do not count
    s = _state(2)
    for _ in range(200):
        _step(P, s, [0.01, 0.01], 2.6, mon=np.array([False, True]), live=np.array([True, False]))
    assert not s["run"].any() and (s["c_o"] == 0).all()


def test_reception_rate_follows_the_users_of_the_cell():
    P = ProtocolConfig(ns3_oos_rx=200.0)
    serv = np.array([0, 0, 0, 1, 2, 2])
    con = np.array([True, True, True, True, True, False])
    r = core.ctrl_rate(P, serv, con, 3)
    assert r.tolist() == [206.0 + 3 * 16.5] * 3 + [206.0 + 16.5] + [206.0 + 16.5] * 2


def _bad_runs(monkeypatch):
    """Record, at every T310 start of the ns-3-like model, how long the link was below Qout without a break."""
    rec = []
    orig = core.rlm_count
    state = {}

    def wrapped(P, sl, qout, qin, run, c_o, c_i, n_o, n_i, mon, live, rx):
        key = sl.shape
        if key not in state:
            state[key] = np.zeros(sl.shape)
        state[key] = np.where(mon & live & ~run & (sl < qout), state[key] + 1, 0.0)
        start = orig(P, sl, qout, qin, run, c_o, c_i, n_o, n_i, mon, live, rx)
        rec.extend(state[key][start].tolist())
        return start
    monkeypatch.setattr(core, "rlm_count", wrapped)
    return rec


def test_detection_takes_the_counted_time_in_a_simulation(monkeypatch):
    rec = _bad_runs(monkeypatch)
    # a Qout of 0 dB makes long bad runs frequent in a short run; the timing does not depend on the threshold
    sc = hl.builtin_scenario("smoke").with_overrides(dict(SHORT, **NS3, **{"protocol.qout_db": 0.0,
                                                                             "protocol.qin_db": 2.0}))
    hl.run_world(hl.build_world(sc, 3), RULES[:1])
    assert rec, "no T310 started"
    dt = sc.protocol.step_s
    lo = 200.0 / (206.0 + 16.5 * 12)                           # every user of the run on one cell
    hi = 200.0 / (206.0 + 16.5)                                 # alone on its cell
    assert min(rec) * dt >= lo - 1e-9 and max(rec) * dt <= hi + dt + 1e-9
    assert np.mean(rec) * dt > 0.6                              # against 0.2 s of the 3GPP filter


def test_slower_detection_gives_fewer_failures():
    sc = hl.builtin_scenario("smoke").with_overrides(SHORT)
    base = hl.simulate(sc, RULES[:1], seeds=[3])[0].metrics
    slow = hl.simulate(sc.with_overrides({"protocol.ns3_oos_rx": 200.0}), RULES[:1], seeds=[3])[0].metrics
    assert slow["failures_pm"] < base["failures_pm"]           # T310 starts later: fewer failures


def test_batch_and_single_engines_agree():
    sc = hl.builtin_scenario("smoke").with_overrides(dict(SHORT, **NS3))
    a = hl.run_world(hl.build_world(sc, 3), RULES)
    b = hl.run_world(hl.build_world(sc, 3), RULES, batch=False)
    assert [r.metrics for r in a] == [r.metrics for r in b]
    assert [r.fingerprint for r in a] == [r.fingerprint for r in b]


def test_defaults_untouched():
    P = ProtocolConfig()
    assert P.ns3_oos_rx is None
    assert (P.ns3_ins_rx, P.ns3_ctrl_hz, P.ns3_ctrl_per_ue_hz) == (100.0, 206.0, 16.5)
    sc = hl.builtin_scenario("smoke").with_overrides(SHORT)
    d = sc.to_dict()
    assert not [k for k in d["protocol"] if k.startswith("ns3_")]   # job IDs of existing scenarios unchanged
    assert "ns3_oos_rx" in sc.to_dict(full=True)["protocol"]
    # the other ns3_* values do nothing while ns3_oos_rx is null
    idle = sc.with_overrides({"protocol.ns3_ins_rx": 7.0, "protocol.ns3_ctrl_hz": 999.0,
                              "protocol.ns3_ctrl_per_ue_hz": 0.0})
    a = hl.simulate(sc, RULES, seeds=[3])
    b = hl.simulate(idle, RULES, seeds=[3])
    assert [r.metrics for r in a] == [r.metrics for r in b]


@pytest.mark.parametrize("over, key", [
    ({"protocol.ns3_oos_rx": 0.0}, "ns3_oos_rx"),
    ({"protocol.ns3_oos_rx": 200.0, "protocol.ns3_ins_rx": -1.0}, "ns3_ins_rx"),
    ({"protocol.ns3_oos_rx": 200.0, "protocol.ns3_ctrl_hz": 0.0}, "ns3_ctrl_hz"),
    ({"protocol.ns3_oos_rx": 200.0, "protocol.rlm_eval": "ts38133"}, "ns3_oos_rx"),
])
def test_validation(over, key):
    with pytest.raises(ConfigError, match=key):
        hl.builtin_scenario("smoke").with_overrides(over).validate()


def test_setting_applies_its_keys_only():
    assert ns3.NS3_LIKE_SETTING == {
        "protocol.ns3_oos_rx": 200.0, "protocol.ns3_ins_rx": 100.0, "protocol.ns3_ctrl_hz": 206.0,
        "protocol.ns3_ctrl_per_ue_hz": 16.5, "protocol.rlm_holdoff_s": 0.0, "protocol.cmd_during_t310": "lost",
        "protocol.exec_can_fail": False, "protocol.lm_load": 0.38}
    assert ns3.SETTINGS == {"comparison": ns3.COMPARISON_SETTING, "ns3-like": ns3.NS3_LIKE_SETTING}
    base = ns3.scenario_for(200, 22, car=True)
    sc = ns3.scenario_for(200, 22, car=True, ns3_like=True)
    a, b = base.to_dict(full=True), sc.to_dict(full=True)
    for k, v in ns3.NS3_LIKE_SETTING.items():
        a["protocol"][k.split(".", 1)[1]] = v
    assert a == b and sc.radio.penetration_db == 9.0
    assert base.protocol.ns3_oos_rx is None and base.protocol.cmd_during_t310 == "receive"
    with pytest.raises(ValueError, match="choose one"):
        ns3.scenario_for(200, 22, comparison=True, ns3_like=True)
    sc.validate()


def test_verify_flag_reaches_the_simulated_scenarios(monkeypatch):
    from handoverlab.verify.report import Report
    seen = []

    def fake(sc, rules, seeds):
        from types import SimpleNamespace
        seen.append((sc.protocol.ns3_oos_rx, sc.protocol.cmd_during_t310, sc.radio.penetration_db))
        return [SimpleNamespace(rule=r["name"], metrics=dict(attempts_pm=10.0 - 5 * r["ttt_s"], unnecessary_pm=3.0,
                                                             failures_pm=r["ttt_s"], sinr_db=10.0))
                for _ in seeds for r in rules]
    monkeypatch.setattr(ns3, "simulate", fake)
    out = ns3.ns3_checks(Report(), seeds=[1], ns3_like=True)
    assert {x[:2] for x in seen} == {(200.0, "lost")} and out["summary"]["ns3_like"] is True
    assert out["summary"]["car"] is True and any(x[2] > 0 for x in seen)
    calls = []
    monkeypatch.setattr(ns3, "ns3_checks", lambda rep, **kw: calls.append(kw))
    assert main(["verify", "--ns3", "--ns3-like", "-q"]) == 0
    assert calls[-1]["ns3_like"] is True and calls[-1]["comparison"] is False
    assert main(["verify", "--ns3", "--ns3-like", "--ns3-comparison", "-q"]) == 2


@pytest.fixture
def run_dir(tmp_path):
    d = tmp_path / "runs"
    d.mkdir()
    with open(os.path.join(DATA, "v1_runs.json"), encoding="utf-8") as f:
        for r in json.load(f):
            (d / (r["tag"] + ".json")).write_text(json.dumps(r), encoding="utf-8")
    return str(d)


def test_bridge_row_n(tmp_path, run_dir):
    st = nb.load_ns3_study(V1)
    sc = nb.handoverlab_scenario(st, 300, 28, "light", False, setting="ns3-like")
    ref = ns3.scenario_for(300, 28, car=True).with_overrides(dict(
        ns3.NS3_LIKE_SETTING, **{"mobility.users": 20, "run.duration_s": 180.0, "run.warmup_s": 60.0}))
    assert sc.to_dict(full=True) == ref.to_dict(full=True)
    assert nb.SETTINGS == ("reference", "comparison", "ns3-like")
    with pytest.raises(nb.Ns3BridgeError, match="unknown setting"):
        nb.handoverlab_scenario(st, 300, 28, "light", False, setting="ns-3")
    with pytest.raises(nb.Ns3BridgeError, match="choose one"):
        nb.handoverlab_scenario(st, 300, 28, "light", False, comparison=True, setting="ns3-like")
    assert nb.handoverlab_scenario(st, 300, 28, "light", False, comparison=True).to_dict(full=True) == \
        nb.handoverlab_scenario(st, 300, 28, "light", False, setting="comparison").to_dict(full=True)
    ref = nb.import_results(run_dir)
    d = copy.deepcopy(V1)
    d["ns3"]["conditions"].update(isd_m=[200], speed_mps=[10])
    d["ns3"]["seeds"] = [401, 402]
    short = {"run.duration_s": 3.0, "run.warmup_s": 1.0, "mobility.users": 3}
    res = nb.compare(d, ref, overrides=short, setting="ns3-like")
    assert res["setting"] == "ns3-like" and res["comparison"] is False and len(res["cells"]) == 2
    assert nb.compare(d, ref, overrides=short)["setting"] == "reference"


def test_cli_ns3_compare_ns3_like(tmp_path, monkeypatch, capsys):
    study = tmp_path / "v1.json"
    study.write_text(json.dumps(V1), encoding="utf-8")
    seen = []

    def fake(study, reference, **kw):
        seen.append(kw)
        cells = [dict(key="light_h3_d200_v10_t80", n=5, failures_hl=1, failures_ns3=2, ho_pm_hl=1.0,
                      ho_pm_ns3=1.0)]
        full = [dict(c, isd_m=200, speed_mps=10.0, ttt_ms=80, offset_db=3.0, traffic="light", fading=False)
                for c in cells]
        return dict(study="V1", comparison=kw["comparison"], setting=kw["setting"] or "reference",
                    run_length="study", cells=cells, notes=[], checks=nb.checks(full))
    monkeypatch.setattr(nb, "compare", fake)
    ref = tmp_path / "ref.json"
    ref.write_text("{}", encoding="utf-8")
    main(["ns3", "compare", str(study), str(ref), "--ns3-like"])
    assert seen[-1]["setting"] == "ns3-like" and seen[-1]["comparison"] is False
    assert "ns-3-like setting" in capsys.readouterr().out
    main(["ns3", "compare", str(study), str(ref)])
    assert seen[-1]["setting"] is None
    assert main(["ns3", "compare", str(study), str(ref), "--ns3-like", "--comparison"]) == 2
    assert "choose one" in capsys.readouterr().err
