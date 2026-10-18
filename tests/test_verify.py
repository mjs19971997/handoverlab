# SPDX-License-Identifier: MIT
"""The verification checks and the 'verify' command, including the golden event-log fingerprints."""
import json

import pytest

from handoverlab.cli import main
from handoverlab.verify import GROUPS, Report, run_verify
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
    assert sum(len(v) for v in ref["cases"].values()) == len([c for c in rep.checks if c.status != "NOTE"])


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
    assert GROUPS == ("pathloss", "radio", "invariants", "equivalences", "fingerprints")


def test_ns3_scenario_overrides():
    from handoverlab.verify.ns3 import scenario_for
    base = scenario_for(200, 16)
    sc = scenario_for(200, 16, overrides={"protocol.qout_window_s": 0.12})
    assert base.protocol.qout_window_s == 0.2 and sc.protocol.qout_window_s == 0.12
    assert sc.layout.sites == base.layout.sites and sc.mobility.profile == "c16"
