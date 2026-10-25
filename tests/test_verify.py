# SPDX-License-Identifier: MIT
"""The verification checks and the 'verify' command, including the golden event-log fingerprints."""
import json

import pytest

from handoverlab.cli import main
from handoverlab.verify import GROUPS, OPTIONAL_GROUPS, Report, run_verify
from handoverlab.verify import golden, ns3
from handoverlab.verify.engine_checks import equivalence_checks, invariant_checks
from handoverlab.verify.radio import radio_statistics


def _ok(rep):
    assert rep.ok, "\n".join("%s: %s" % (c.name, c.detail) for c in rep.failed)


def test_pathloss_checks_and_cli(tmp_path, capsys):
    rep = run_verify(["pathloss"], printer=None)
    _ok(rep)
    assert len(rep.checks) >= 20
    out = tmp_path / "v.json"
    assert main(["verify", "--only", "pathloss", "--json", str(out), "-q"]) == 0
    assert "OK:" in capsys.readouterr().out
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["ok"] and doc["provenance"]["handoverlab"]
    assert main(["verify", "--only", "nope"]) == 2


def test_golden_fingerprints():
    """Event logs of short reference runs: identical on the reference build, close elsewhere."""
    rep = Report()
    golden.fingerprint_checks(rep)
    _ok(rep)
    ref = golden.load()
    assert sum(len(v) for v in ref["cases"].values()) == len([c for c in rep.checks
                                                              if c.status != "NOTE" and c.group == "fingerprints"])
    with open(golden.PATH_1X, encoding="utf-8") as f:   # 2.0.0: every golden run of 1.12.0 with LEGACY_1X
        old = json.load(f)
    assert sum(len(v) for v in old["cases"].values()) == len([c for c in rep.checks if c.group == "fingerprints-1x"
                                                              and c.status != "NOTE"]) == 33


def test_radio_statistics():
    rep = Report()
    radio_statistics(rep, seeds=(3,))
    _ok(rep)


def test_engine_checks_short():
    rep = Report()
    invariant_checks(rep, duration_s=10.0)
    equivalence_checks(rep, duration_s=10.0)
    _ok(rep)
    assert any("immediate execution = A3" in c.name for c in rep.checks)


def test_stored_results_are_recomputed(tmp_path, capsys):
    cfg = {"scenario": {"base": "smoke", "mobility": {"users": 6}, "run": {"duration_s": 10.0, "warmup_s": 2.0}},
           "seeds": [1, 2], "rules": [{"rule": "a3"}, {"rule": "cho", "name": "C"}]}
    p = tmp_path / "c.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    out = tmp_path / "r.json"
    assert main(["run", str(p), "-o", str(out), "-q"]) == 0
    assert main(["verify", "--results", str(out), "--sample", "3", "-q"]) == 0
    assert "OK: 4 passed" in capsys.readouterr().out
    doc = json.loads(out.read_text(encoding="utf-8"))
    doc["results"][0]["fingerprint"] = "0" * 64
    doc["results"][1]["metrics"]["sinr_db"] *= 1.0 + 1e-9
    out.write_text(json.dumps(doc), encoding="utf-8")
    assert main(["verify", "--results", str(out), "-q"]) == 1
    assert "FAILED: 3 passed, 2 failed" in capsys.readouterr().out


def test_ns3_reference_data():
    ref = ns3.load_reference()
    a = [r for r in ref["rows"] if r["part"] == "A"]
    assert len(a) == 96 and len({(r["a3_offset_db"], r["ttt_ms"]) for r in a}) == 24
    sc = ns3.scenario_for(200, 30, ref)
    assert sc.layout.sites[1] == (200.0, 0.0) and sc.mobility.profile == "c30" and sc.radio.carrier_ghz == 3.5
    assert ns3.spearman([1, 2, 3, 4], [10, 20, 30, 25]) == pytest.approx(0.8)



def _fake_simulate(sc, rules, seeds):
    """Stand-in for ``simulate`` in the ns-3 comparison: rates follow the time-to-trigger, no simulation."""
    from types import SimpleNamespace
    users = sc.mobility.users
    return [SimpleNamespace(rule=r["name"], metrics=dict(
        attempts_pm=10.0 - 5.0 * r["ttt_s"] + 0.1 * r["off_db"], unnecessary_pm=3.0 - r["ttt_s"] + 0.05 * r["off_db"],
        failures_pm=r["ttt_s"] * users / 20.0, sinr_db=10.0)) for _ in seeds for r in rules]


def test_ns3_compare_and_holdout_logic(monkeypatch):
    from handoverlab.verify.report import Report
    monkeypatch.setattr(ns3, "simulate", _fake_simulate)
    msgs = []
    rep = Report()
    out = ns3.ns3_checks(rep, seeds=[1, 2], progress=msgs.append)
    s = out["summary"]
    assert len(out["table"]) == 24 and len(msgs) == 4 and s["seeds"] == [1, 2]
    assert s["ttt_trend"] == pytest.approx(10.0) and s["ttt_trend_ns3"] > 1
    assert any(c.name.startswith("handover rate: rank") for c in rep.checks)
    h = ns3.holdout(seeds=[1], progress=msgs.append, overrides={"protocol.lm_load_per_ue": 0.01})
    assert h["summary"]["B"]["cells"] == 12 and h["summary"]["C"]["cells"] == 20
    users = {x["variant"]: x["handoverlab"][2] for x in h["table"] if x["isd_m"] == 200 and x["part"] == "C"}
    assert users["users 40"] == pytest.approx(4 * users["users 10"])
    assert ns3.scenario_for(200, 42).mobility.groups[0].v_min == 42.0       # speeds without a profile
    assert ns3._trend([dict(ttt_ms=100, x=[0, 0, 0.0]), dict(ttt_ms=200, x=[0, 0, 1.0])], "x") == float("inf")


def test_groups_listed():
    assert GROUPS == ("pathloss", "radio", "calibration", "invariants", "equivalences", "fingerprints", "extended",
                      "highway", "values", "fading")
    assert OPTIONAL_GROUPS == ("learning", "ntn", "scenarios")


def test_ns3_scenario_overrides():
    from handoverlab.verify.ns3 import scenario_for
    base = scenario_for(200, 16)
    sc = scenario_for(200, 16, overrides={"protocol.qout_window_s": 0.12})
    assert base.protocol.qout_window_s == 0.2 and sc.protocol.qout_window_s == 0.12
    assert sc.layout.sites == base.layout.sites and sc.mobility.profile == "c16"


def test_ns3_comparison_setting_applies_its_keys_and_leaves_the_defaults():
    """2.5.0: the ns-3 comparison setting (study V1) is opt-in; the defaults stay as they were."""
    assert ns3.COMPARISON_SETTING == {"protocol.lm_load": 0.15, "protocol.exec_can_fail": False}
    base = ns3.scenario_for(200, 30, car=True)
    sc = ns3.scenario_for(200, 30, car=True, comparison=True)
    assert sc.protocol.lm_load == 0.15 and sc.protocol.exec_can_fail is False
    assert base.protocol.lm_load is None and base.protocol.exec_can_fail is True
    plain = ns3.scenario_for(200, 30).to_dict(full=True)
    assert plain == ns3.scenario_for(200, 30, comparison=False).to_dict(full=True)
    a, b = base.to_dict(full=True), sc.to_dict(full=True)
    a["protocol"].update(lm_load=0.15, exec_can_fail=False)
    assert a == b                                      # nothing else changes
    assert sc.radio.penetration_db == 9.0              # the in-car loss is kept
    ov = ns3.scenario_for(200, 16, comparison=True, overrides={"protocol.lm_load": 0.2})
    assert ov.protocol.lm_load == 0.2 and ov.protocol.exec_can_fail is False   # overrides come after


def test_ns3_comparison_flag_reaches_the_simulated_scenarios(monkeypatch):
    seen = []

    def fake(sc, rules, seeds):
        seen.append((sc.protocol.lm_load, sc.protocol.exec_can_fail, sc.radio.penetration_db))
        return _fake_simulate(sc, rules, seeds)
    monkeypatch.setattr(ns3, "simulate", fake)
    out = ns3.compare(seeds=[1])
    assert {x[:2] for x in seen} == {(None, True)} and out["summary"]["comparison"] is False
    seen.clear()
    rep = Report()
    out = ns3.ns3_checks(rep, seeds=[1], comparison=True)
    assert {x[:2] for x in seen} == {(0.15, False)} and out["summary"]["comparison"] is True
    assert out["summary"]["car"] is True and any(x[2] > 0 for x in seen)      # 30 m/s: the in-car loss
    seen.clear()
    ns3.holdout(seeds=[1], comparison=True)
    assert {x[:2] for x in seen} == {(0.15, False)}
    seen.clear()
    calls = []
    monkeypatch.setattr(ns3, "ns3_checks", lambda rep, **kw: calls.append(kw))
    assert main(["verify", "--ns3", "--ns3-comparison", "-q"]) == 0
    assert main(["verify", "--ns3", "-q"]) == 0
    assert [c["comparison"] for c in calls] == [True, False]


def test_ns3_reference_from_a_file(tmp_path):
    """2.1.0: verify --ns3 --ns3-reference reads a reference file written by benchmarks/ns3/run_benchmark.py."""
    from handoverlab.verify import ns3
    stored = ns3.load_reference()
    path = tmp_path / "reference.json"
    path.write_text(json.dumps(stored), encoding="utf-8")
    assert ns3.load_reference(str(path)) == stored
    bad = tmp_path / "bad.json"
    bad.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(ValueError, match="not an ns-3 reference"):
        ns3.load_reference(str(bad))
    assert main(["verify", "--ns3", "--ns3-reference", str(bad)]) == 2


def test_benchmark_script_lists_the_reference_runs():
    import importlib.util
    import os
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "benchmarks", "ns3",
                     "run_benchmark.py")
    spec = importlib.util.spec_from_file_location("run_benchmark", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    jobs = mod.jobs(["A", "B", "C"], 20, 10)
    assert sum(j["part"] == "A" for j in jobs) == 96 and sum(j["part"] == "B" for j in jobs) == 240
    assert sum(j["part"] == "C" for j in jobs) == 200 and len({j["tag"] for j in jobs}) == len(jobs)
    from handoverlab.verify import ns3
    stored = {(r["isd_m"], r["speed_mps"], r["a3_offset_db"], r["ttt_ms"]) for r in ns3.load_reference()["rows"]
              if r["part"] == "A"}
    assert {(j["isd"], j["speed"], float(j["h"]), j["t"]) for j in jobs if j["part"] == "A"} == stored
