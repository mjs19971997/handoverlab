# SPDX-License-Identifier: MIT
"""Event-log levels, the study status with time estimates, and the grid-edge policy ``extend``."""
import json
import math
import os

import numpy as np
import pytest

import handoverlab as hl
from handoverlab.cli import main
from handoverlab.config import ConfigError
from handoverlab.eventlog import (TRACE_EVENTS, event_level, read_trace, serving_cells, trace_path, write_trace)
from handoverlab.studies import GateError, StudyStore, load_study_dir, run_study, status_data, study_status
from handoverlab.studies.tuning import extension_values

from test_study import tiny


# ---------------------------------------------------------------------------- event-log levels
def test_event_level_names():
    assert event_level(False) == event_level(None) == "off"
    assert event_level(True) == "summary"
    assert event_level("FULL") == "full"
    with pytest.raises(ValueError):
        event_level("everything")


@pytest.fixture(scope="module")
def smoke_runs():
    world = hl.build_world(hl.builtin_scenario("smoke"), 2)
    rules = [{"rule": "a3"}, {"rule": "cho"}]
    shares = []
    return (world, hl.run_world(world, rules), hl.run_world(world, rules, log_events="summary"),
            hl.run_world(world, rules, log_events="full", progress=shares.append),
            hl.run_world(world, rules, log_events="full", batch=False), shares)


def test_levels_do_not_change_results(smoke_runs):
    world, off, summ, full, single, shares = smoke_runs
    for a, b, c, d in zip(off, summ, full, single):
        assert a.fingerprint == b.fingerprint == c.fingerprint == d.fingerprint
        assert a.metrics == b.metrics == c.metrics
        assert a.events is None and a.trace is None
        assert b.events is not None and b.trace is None
        assert c.events == b.events and c.trace is not None
        assert repr(c.trace) == repr(d.trace)                       # batched and single engines agree
    assert shares and shares[-1] == 1.0 and shares == sorted(shares)


def test_trace_content(smoke_runs):
    world, _, _, full, _, _ = smoke_runs
    a3, cho = full
    for r in full:
        kinds = {e["event"] for e in r.trace}
        assert kinds <= set(TRACE_EVENTS)
        assert sum(e["event"] == "serve" for e in r.trace) == world.n_users
        times = [e["t"] for e in r.trace]
        assert times == sorted(times) or all(e["event"] != "serve" for e in r.trace[world.n_users:])
        n_exec = sum(e["event"] == "exec" for e in r.trace)
        n_att = sum(e["event"] == "attach" for e in r.trace)
        assert n_att <= n_exec
        fails = [e for e in r.trace if e["event"] == "failure"]
        assert all(e["note"] for e in fails)
    assert "report" in {e["event"] for e in a3.trace}
    assert {"prepare", "config"} <= {e["event"] for e in cho.trace}


def test_serving_cells_follow_the_trace(smoke_runs):
    world, _, _, full, _, _ = smoke_runs
    r = full[0]
    S = serving_cells(r.trace, world.n_users, [0.0, world.scenario.run.duration_s])
    first = {e["ue"]: e["cell"] for e in r.trace if e["event"] == "serve"}
    assert [S[0, u] for u in range(world.n_users)] == [first[u] for u in range(world.n_users)]
    # at the end every user is either connected (the cell of its last attach) or not connected (-1)
    last = {}
    for e in r.trace:
        if e["event"] in ("serve", "attach", "reestablish"):
            last[e["ue"]] = e["cell"]
        elif e["event"] in ("exec", "failure"):
            last[e["ue"]] = -1
    assert [S[1, u] for u in range(world.n_users)] == [last[u] for u in range(world.n_users)]
    assert S.min() >= -1 and S.max() < world.layout.n_sites


def test_trace_table_round_trip(smoke_runs, tmp_path):
    full = smoke_runs[3]
    p = write_trace(full, str(tmp_path / "ev-trace.csv"))
    rows = read_trace(p)
    assert len(rows) == sum(len(r.trace) for r in full)
    a = rows[0]
    b = full[0].trace[0]
    assert a["event"] == b["event"] and a["cell"] == b["cell"] and a["seed"] == 2
    assert math.isnan(a["value"]) == math.isnan(b["value"])
    assert trace_path("x/events.parquet") == "x/events-trace.parquet"


def test_cli_run_full_level(tmp_path):
    cfg = tmp_path / "c.yaml"
    cfg.write_text("scenario: {base: smoke, run: {duration_s: 6.0, warmup_s: 1.0}}\nseeds: [1]\n"
                   "rules: [{rule: a3}]\n", encoding="utf-8")
    ev = str(tmp_path / "ev.csv")
    assert main(["run", str(cfg), "-o", str(tmp_path / "m.csv"), "--events", ev, "--event-level", "full", "-q"]) == 0
    assert os.path.exists(ev) and os.path.exists(str(tmp_path / "ev-trace.csv"))


def test_study_events_level(tmp_path):
    st = tiny(**{"events": "full", "seeds.test": [1]})
    assert st.events == "full"
    res = run_study(st, str(tmp_path), workers=1)
    rec = StudyStore(str(tmp_path)).records("test")[0]
    for r in rec["rules"]:
        assert r["events"] and r["trace"]
        assert os.path.exists(os.path.join(str(tmp_path), r["trace"]))
    assert res.completed
    with pytest.raises(ConfigError):
        tiny(**{"events": "lots"})
    assert tiny(**{"events": True}).events == "summary"


# ---------------------------------------------------------------------------- status
def test_status_before_and_after(tmp_path):
    st = tiny(**{"seeds.test": [1, 2]})
    lines = study_status(st, str(tmp_path))
    assert any("not started" in x for x in lines) and any("no estimate" in x for x in lines)
    d = status_data(st, str(tmp_path))
    assert [s["stage"] for s in d["stages"]] == ["tune1", "tune2", "test"]
    assert not d["stages"][1]["planned"] and d["stages"][0]["todo"] == 1
    run_study(st, str(tmp_path), workers=1, stop_after="tuning")
    d = status_data(st, str(tmp_path))
    test = d["stages"][-1]
    assert test["planned"] and test["todo"] == 2 and test["rule_runs"] > 0
    assert d["estimate"]["wall_s"] > 0 and d["estimate"]["jobs"] >= 1
    # the study directory alone is enough
    st2 = load_study_dir(str(tmp_path))
    assert st2.lock_hash() == st.lock_hash()
    assert main(["status", str(tmp_path), "--workers", "3"]) == 0
    run_study(st, str(tmp_path), workers=1)
    assert any("complete" in x for x in study_status(str(tmp_path)))


# ---------------------------------------------------------------------------- grid-edge policy extend
def test_extension_values():
    assert extension_values([3.0, 4.0], "upper", 2) == [5.0, 6.0]
    assert extension_values([0.04, 0.08, 0.16], "upper", 1) == [0.24]
    assert extension_values([1, 2, 4], "lower", 2) == [0]                 # never below zero for a >= 0 grid
    assert extension_values([-2.0, -1.0], "lower", 2) == [-3.0, -4.0]
    assert all(isinstance(v, int) for v in extension_values([1, 2], "upper", 3))


def test_extend_widens_the_grid_and_tunes_again(tmp_path):
    st = tiny(**{"tuning.gates": {"grid_edge": "extend"}, "tuning.extend_steps": 2, "tuning.max_extensions": 3,
                 "methods.A3.grid": {"off_db": [3.0, 4.0], "ttt_s": [0.04, 0.16]}, "seeds.test": [1]})
    msgs = []
    try:
        res = run_study(st, str(tmp_path), workers=1, progress=msgs.append)
        completed = res.completed
    except GateError:
        completed = False
    am = json.load(open(os.path.join(str(tmp_path), "amendments.json"), encoding="utf-8"))["rounds"]
    assert 1 <= len(am) <= 3
    first = am[0]["changes"][0]
    assert first["method"] == "A3" and first["param"] == "off_db" and first["grid_before"] == [3.0, 4.0]
    assert any(m.startswith("  extend A3.off_db") for m in msgs)
    assert os.path.exists(os.path.join(str(tmp_path), "AMENDMENTS.md"))
    tuned = json.load(open(os.path.join(str(tmp_path), "tuned", "all.json"), encoding="utf-8"))
    grid = tuned["methods"]["A3"]["grid"]["off_db"]
    assert len(grid) == 2 + sum(len(c["added"]) for rd in am for c in rd["changes"] if c["param"] == "off_db")
    from handoverlab.studies import build_report
    doc, summ = build_report(str(tmp_path), figures=False)
    assert summ["amendments"] == am and "Grid extensions" in doc.markdown()
    # every method still evaluated the same number of settings
    assert {len(m["candidates"]) for m in tuned["methods"].values()} == {4}
    if completed:
        gates = json.load(open(os.path.join(str(tmp_path), "tuned", "gates.json"), encoding="utf-8"))
        assert all(g["status"] == "pass" for g in gates["gates"] if g["gate"] == "grid_edge")
    # a second run reuses everything, including the extensions
    again = run_study(st, str(tmp_path), workers=1) if completed else None
    if again is not None:
        assert again.ran == {"tune1": 0, "tune2": 0, "test": 0}


def test_extend_cap_blocks(tmp_path):
    st = tiny(**{"tuning.gates": {"grid_edge": "extend"}, "tuning.max_extensions": 0,
                 "methods.A3.grid": {"off_db": [3.0, 4.0], "ttt_s": [0.04, 0.16]}, "seeds.test": [1]})
    with pytest.raises(GateError) as e:
        run_study(st, str(tmp_path), workers=1)
    assert "not resolved by extension" in str(e.value) and "max_extensions = 0" in str(e.value)
    assert not os.path.exists(os.path.join(str(tmp_path), "amendments.json"))


def test_extend_is_a_grid_edge_policy_only():
    with pytest.raises(ConfigError, match="grid_edge only"):
        tiny(**{"tuning.gates": {"flat_optimum": "extend"}})
    assert tiny(**{"tuning.gates": {"grid_edge": "extend"}}).tuning.gates["grid_edge"] == "extend"
    assert np.isfinite(tiny().tuning.extend_steps)
