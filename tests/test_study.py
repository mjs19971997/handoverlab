# SPDX-License-Identifier: MIT
"""Studies: plans, tuning gates, resumption, reuse, workers, tables and reports."""
import copy
import json
import os

import pytest

from handoverlab.cli import main
from handoverlab.config import ConfigError
from handoverlab.studies import (GateError, StudyStore, dry_run, load_study, read_table, run_study, study_status,
                                 write_report, write_table)
from handoverlab.studies.runner import default_workers

TINY = {
    "name": "tiny",
    "scenario": {"base": "smoke", "layout": {"kind": "open_area", "blocks": [1, 1]}, "radio": {"isolation": 1.0},
                 "mobility": {"users": 6, "profile": "veh30"}, "run": {"duration_s": 8.0, "warmup_s": 1.0}},
    "seeds": {"tuning": [901], "test": [1, 2, 3]},
    "tuning": {"settings": 4, "random": 3, "reference": {"rule": "a3", "name": "ref", "off_db": 3.0, "ttt_s": 0.16},
               "budgets": {"standard": 1.0, "strict": 0.5}, "min_reference_failures": 0,
               "gates": {"grid_edge": "warn"}},
    "methods": {
        "A3": {"rule": "a3", "grid": {"off_db": [1.0, 2.0, 3.0, 4.0], "ttt_s": [0.04, 0.16]},
               "natural_bounds": {"ttt_s": "lower"}},
        "CHO": {"rule": "cho", "fixed": {"n_max": 2},
                "grid": {"o_exec_db": [1.0, 2.0, 3.0], "ttt_exec_s": [0.0, 0.08]}},
    },
    "compare": {"baseline": "ref", "metrics": ["unnecessary_pm", "failures_pm"], "bootstrap": 200},
}


def tiny(**changes):
    d = copy.deepcopy(TINY)
    for k, v in changes.items():
        node = d
        parts = k.split(".")
        for p in parts[:-1]:
            node = node[p]
        node[parts[-1]] = v
    return load_study(d)


@pytest.fixture(scope="module")
def done(tmp_path_factory):
    """The tiny study run once (one worker), shared by several tests."""
    root = str(tmp_path_factory.mktemp("study"))
    res = run_study(tiny(), root, workers=1)
    return root, res


def test_study_runs_all_stages(done):
    root, res = done
    assert res.completed
    assert res.jobs == {"tune1": 1, "tune2": 1, "test": 3}
    store = StudyStore(root)
    tune = store.records("tune1") + store.records("tune2")
    names = [r["name"] for rec in tune for r in rec["rules"]]
    assert names.count("ref") == 1
    assert sum(n.startswith("A3#") for n in names) == 4 and sum(n.startswith("CHO#") for n in names) == 4
    rows = read_table(res.tables["runs"])
    assert {r["rule"] for r in rows if r["stage"] == "test"} == {"ref", "A3@standard", "A3@strict", "CHO@standard",
                                                                 "CHO@strict"}
    assert len([r for r in rows if r["stage"] == "test"]) == 15
    trows = read_table(res.tables["tuning"])
    assert len(trows) == 8 and sum(r["selected.standard"] for r in trows) == 2
    gates = json.load(open(os.path.join(root, "tuned", "gates.json"), encoding="utf-8"))
    assert gates["ok"] and {g["gate"] for g in gates["gates"]} >= {"seed_overlap", "equal_budget", "grid_edge"}
    lock = json.load(open(os.path.join(root, "study.lock.json"), encoding="utf-8"))
    assert lock["sha256"] == tiny().lock_hash()


def test_test_stage_uses_the_selected_settings(done):
    root, res = done
    store = StudyStore(root)
    sel = json.load(open(os.path.join(root, "tuned", "all.json"), encoding="utf-8"))["methods"]["A3"]["selected"]
    for rec in store.records("test"):
        r = {x["name"]: x for x in rec["rules"]}
        assert r["A3@standard"]["setting"] == sel["standard"]["setting"]
        assert r["A3@standard"]["params"]["off_db"] == sel["standard"]["setting"]["off_db"]
        assert rec["seed"] in (1, 2, 3)


def test_rerun_skips_finished_jobs_and_reuses_runs(done, tmp_path):
    root, _ = done
    again = run_study(tiny(), root, workers=1)
    assert again.ran == {"tune1": 0, "tune2": 0, "test": 0}
    # one more test seed: only its job runs; the tuning stage is untouched
    more = run_study(tiny(**{"seeds.test": [1, 2, 3, 4]}), root, workers=1)
    assert more.ran == {"tune1": 0, "tune2": 0, "test": 1}
    man = json.load(open(os.path.join(root, "manifest.json"), encoding="utf-8"))
    assert len(man["sessions"]) == 3 and man["changes"]


def test_identical_rules_run_once_and_stored_runs_are_reused(done, tmp_path):
    root, _ = done
    store = StudyStore(root)
    for rec in store.records("test"):
        simulated = [r for r in rec["rules"] if not r["reused"]]
        assert len(simulated) == rec["simulated"] <= 5
        assert len({r["run_key"] for r in rec["rules"]}) == len(simulated)
    # a study in a new directory that shares the reference runs: copy one job record and rerun
    other = str(tmp_path / "copy")
    os.makedirs(os.path.join(other, "jobs", "test"))
    rec = store.records("test")[0]
    with open(os.path.join(other, "jobs", "test", "x.json"), "w", encoding="utf-8") as f:
        json.dump(rec, f)
    res = run_study(tiny(**{"seeds.test": [rec["seed"]]}), other, workers=1)
    new = StudyStore(other).load_job("test", rec["job"])               # same content, same job ID
    assert res.completed and new["simulated"] == 0 and all(r["reused"] for r in new["rules"])
    assert [r["fingerprint"] for r in new["rules"]] == [r["fingerprint"] for r in rec["rules"]]


def test_two_workers_give_identical_results(done, tmp_path):
    root, _ = done
    run_study(tiny(), str(tmp_path / "w2"), workers=2)

    def prints(r):
        return {(rec["stage"], rec["seed"], x["name"]): x["fingerprint"] for rec in StudyStore(r).records()
                for x in rec["rules"] if rec["seed"] != 4}
    assert prints(root) == prints(str(tmp_path / "w2"))


def test_blocking_gate_stops_before_the_test_stage(tmp_path):
    st = tiny(**{"tuning.gates": {"grid_edge": "block"},
                 "methods.A3.grid": {"off_db": [3.0, 4.0], "ttt_s": [0.04, 0.16]}})
    with pytest.raises(GateError) as e:
        run_study(st, str(tmp_path), workers=1)
    assert "grid_edge" in str(e.value) and "A3" in str(e.value)
    assert not StudyStore(str(tmp_path)).records("test")
    assert os.path.exists(tmp_path / "tuned" / "gates.json")
    assert any("BLOCKED" in line for line in study_status(st, str(tmp_path)))


def test_seed_overlap_blocks_before_anything_runs(tmp_path):
    st = tiny(**{"seeds.tuning": [1]})
    with pytest.raises(GateError, match="seed_overlap"):
        run_study(st, str(tmp_path), workers=1)
    assert not os.path.exists(tmp_path / "jobs")


def test_study_without_tuning(tmp_path):
    st = load_study({"scenario": TINY["scenario"], "seeds": {"test": [1, 2]},
                     "methods": {"A3": {"rule": "a3"}, "CHO": {"rule": "cho", "fixed": {"o_exec_db": 2.0}}}})
    res = run_study(st, str(tmp_path), workers=1)
    assert res.jobs == {"test": 2} and res.completed
    assert st.baseline() == "A3"


def test_study_file_errors():
    with pytest.raises(ConfigError, match="unknown key 'tunning'"):
        load_study(dict(TINY, tunning={}))
    with pytest.raises(ConfigError, match="methods.A3.grid.offset"):
        tiny(**{"methods.A3.grid": {"offset": [1, 2]}})
    with pytest.raises(ConfigError, match="tuning seeds"):
        tiny(**{"seeds": {"test": [1]}})
    with pytest.raises(ConfigError, match="compare.baseline"):
        tiny(**{"compare.baseline": "nobody"})
    with pytest.raises(ConfigError, match="tuning.gates.grid"):
        tiny(**{"tuning.gates": {"grid": "warn"}})
    with pytest.raises(ConfigError, match="natural_bounds"):
        tiny(**{"methods.A3.natural_bounds": {"ttt_s": "bottom"}})
    with pytest.raises(ConfigError, match="scenario.layout.site_spacing"):
        load_study(dict(TINY, conditions={"layout.site_spacing": [1]}))


def test_dry_run_and_workers():
    lines = dry_run(tiny())
    assert any("stage tune1: 1 jobs, 7 rule runs" in x for x in lines)
    assert any("stage test: 3 jobs x 5 rules" in x for x in lines)
    assert default_workers(32) == 28 and default_workers(8) == 4 and default_workers(4) == 2
    assert default_workers(1) == 1


def test_report(done, tmp_path):
    root, _ = done
    files = write_report(root, str(tmp_path / "rep"))
    names = {os.path.basename(p) for p in files}
    assert {"report.md", "report.html", "summary.json"} <= names
    md = open(tmp_path / "rep" / "report.md", encoding="utf-8").read()
    assert "Paired comparisons with ref" in md and "Gates" in md and "A3@standard" in md
    summary = json.load(open(tmp_path / "rep" / "summary.json", encoding="utf-8"))
    rows = summary["test"]["pooled"]["unnecessary_pm"]
    assert {r["rule"] for r in rows} == {"A3@standard", "A3@strict", "CHO@standard", "CHO@strict"}
    assert all(0.0 <= r["p"] <= 1.0 and r["p"] <= r["p_holm"] <= 1.0 for r in rows)
    pytest.importorskip("matplotlib")
    assert "comparison.png" in names and "<img" in open(tmp_path / "rep" / "report.html", encoding="utf-8").read()


def test_cli_study_and_report(tmp_path, capsys):
    import yaml
    path = tmp_path / "s.yaml"
    d = copy.deepcopy(TINY)
    d["seeds"]["test"] = [1]
    d["output"] = str(tmp_path / "out")
    path.write_text(yaml.safe_dump(d), encoding="utf-8")
    assert main(["study", str(path), "--dry-run"]) == 0
    assert "stage test" in capsys.readouterr().out
    assert main(["study", str(path), "--workers", "1", "-q", "--report"]) == 0
    assert os.path.exists(tmp_path / "out" / "report" / "report.html")
    assert main(["study", str(path), "--status"]) == 0
    assert "test" in capsys.readouterr().out
    assert main(["report", str(tmp_path / "out"), "-o", str(tmp_path / "r2"), "--format", "md",
                 "--no-figures"]) == 0
    assert os.path.exists(tmp_path / "r2" / "report.md") and not os.path.exists(tmp_path / "r2" / "report.html")
    assert main(["report", str(tmp_path)]) == 2
    d["tuning"]["gates"] = {"grid_edge": "block"}
    d["methods"]["A3"]["grid"] = {"off_db": [3.0, 4.0], "ttt_s": [0.04, 0.16]}
    d["output"] = str(tmp_path / "blocked")
    path.write_text(yaml.safe_dump(d), encoding="utf-8")
    assert main(["study", str(path), "--workers", "1", "-q"]) == 3


def test_tables_parquet_or_csv(tmp_path):
    rows = [{"a": 1, "b": 0.5, "c": "x", "d": True, "e": None}, {"a": 2, "b": 1, "c": "y", "d": False, "e": 3.0}]
    p = write_table(rows, str(tmp_path / "t.parquet"))
    back = read_table(str(tmp_path / "t.parquet"))
    assert back[0]["a"] == 1 and back[1]["b"] == 1.0 and back[0]["c"] == "x" and back[0]["d"] is True
    assert back[0]["e"] is None and back[1]["e"] == 3.0
    try:
        import pyarrow  # noqa: F401
        assert p.endswith(".parquet")
    except ImportError:
        assert p.endswith(".csv")
