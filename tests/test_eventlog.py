# SPDX-License-Identifier: MIT
"""Event-log fingerprints and event tables (CSV, Parquet)."""
import hashlib
import json

import pytest

import handoverlab as hl
from handoverlab import eventlog
from handoverlab.cli import main
from handoverlab.eventlog import EVENT_FIELDS, canonical_csv, fingerprint, read_events, write_events

ROW = (1.2345, -1.0, 2.5, 3, "ho", 4, 7, "useful", "", 1.2655, -0.0, 0, 3.0, 10.5, -20.0)


def test_canonical_csv_by_hand():
    text = canonical_csv([ROW])
    assert text == (",".join(EVENT_FIELDS) + "\n"
                    "1.2345,-1.0,2.5,3,ho,4,7,useful,,1.2655,0.0,0,3.0,10.5,-20.0\n")
    assert fingerprint([ROW]) == hashlib.sha256(text.encode()).hexdigest()


def test_fingerprint_same_for_dicts_tuples_and_numpy_values():
    import numpy as np
    d = dict(zip(EVENT_FIELDS, ROW))
    d2 = dict(d, t_attempt=np.float64(1.2345), ue=np.int64(3))
    assert fingerprint([ROW]) == fingerprint([d]) == fingerprint([d2])
    assert fingerprint([ROW]) != fingerprint([ROW[:3] + (4,) + ROW[4:]])
    assert fingerprint([]) == hashlib.sha256((",".join(EVENT_FIELDS) + "\n").encode()).hexdigest()


@pytest.fixture(scope="module")
def results():
    sc = hl.Scenario.from_dict({"layout": {"kind": "open_area", "blocks": [1, 1], "site_spacing_m": 150.0},
                                "mobility": {"users": 6}, "run": {"duration_s": 20.0, "warmup_s": 2.0}})
    return hl.simulate(sc, [{"rule": "a3"}, {"rule": "cho"}], seeds=[1, 2], log_events=True)


def test_result_fingerprint_matches_log(results):
    for r in results:
        assert r.fingerprint == fingerprint(r.events) and r.n_events == len(r.events) > 0
        assert all(type(e["t_attempt"]) is float for e in r.events)


def test_fingerprint_without_logging(results):
    sc_res = hl.simulate(hl.Scenario.from_dict({"layout": {"kind": "open_area", "blocks": [1, 1],
                                                           "site_spacing_m": 150.0},
                                                "mobility": {"users": 6}, "run": {"duration_s": 20.0,
                                                                                  "warmup_s": 2.0}}),
                         [{"rule": "a3"}], seeds=[1])
    assert sc_res[0].events is None and sc_res[0].fingerprint == results[0].fingerprint


def test_csv_table_round_trip(tmp_path, results):
    path = write_events(results, str(tmp_path / "ev.csv"))
    rows = read_events(path)
    assert len(rows) == sum(r.n_events for r in results)
    logs = eventlog.group_logs(rows)
    for r in results:
        assert fingerprint(logs[(r.seed, r.rule)]) == r.fingerprint


def test_parquet_falls_back_to_csv(tmp_path, results, monkeypatch):
    monkeypatch.setattr(eventlog, "parquet_available", lambda: False)
    with pytest.warns(RuntimeWarning, match="pyarrow"):
        path = write_events(results, str(tmp_path / "ev.parquet"))
    assert path.endswith("ev.csv")
    assert len(read_events(path)) == sum(r.n_events for r in results)


@pytest.mark.skipif(not eventlog.parquet_available(), reason="pyarrow not installed")
def test_parquet_round_trip(tmp_path, results):
    path = write_events(results, str(tmp_path / "ev.parquet"))
    assert path.endswith(".parquet")
    logs = eventlog.group_logs(read_events(path))
    for r in results:
        assert fingerprint(logs[(r.seed, r.rule)]) == r.fingerprint


def test_cli_events_and_fingerprints_in_results(tmp_path):
    cfg = {"scenario": {"layout": {"kind": "open_area", "blocks": [1, 1], "site_spacing_m": 150.0},
                        "mobility": {"users": 4}, "run": {"duration_s": 10.0, "warmup_s": 2.0}},
           "rules": [{"rule": "a3"}]}
    p = tmp_path / "c.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    ev = tmp_path / "ev.csv"
    out = tmp_path / "r.json"
    assert main(["run", str(p), "-o", str(out), "--events", str(ev), "-q"]) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    rec = doc["results"][0]
    logs = eventlog.group_logs(read_events(str(ev)))
    assert rec["key"] == "a3" and rec["fingerprint"] == fingerprint(logs[(1, "A3")])
