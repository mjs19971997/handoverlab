# SPDX-License-Identifier: MIT
"""The frozen public surface: schema versions, deprecations, the surface snapshot and release metadata."""
import json
import os
import warnings

import pytest

import handoverlab as hl
from handoverlab import stability
from handoverlab.cli import EXAMPLE_CONFIG, main
from handoverlab.config import ConfigError, read_file
from handoverlab.stability import (SCHEMA_VERSION, HandoverLabDeprecationWarning, check_schema, deprecated,
                                   deprecated_alias, metric_name, public_surface)
from handoverlab.studies import study_from_dict

from test_study import TINY

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOT = os.path.join(ROOT, "tests", "data", "public_api.json")


def test_public_surface_matches_the_snapshot():
    with open(SNAPSHOT, encoding="utf-8") as f:
        want = json.load(f)
    got = json.loads(json.dumps(public_surface()))
    changed = sorted(k for k in set(want) | set(got) if want.get(k) != got.get(k))
    assert not changed, ("the public surface changed in %s; if intended, follow docs/stability.md and run "
                         "python -m handoverlab.stability --write tests/data/public_api.json" % ", ".join(changed))


@pytest.mark.parametrize("value, ok", [(None, True), (1, True), (SCHEMA_VERSION + 1, False), (0, False),
                                       ("1", False), (True, False)])
def test_check_schema(value, ok):
    if ok:
        assert check_schema(value, "x") == (value or 1)
    else:
        with pytest.raises(ConfigError, match="x: "):
            check_schema(value, "x")


def test_experiment_schema_key():
    assert hl.Experiment.from_dict({"schema": 1}).seeds == (1,)
    assert hl.Experiment.from_dict({}).seeds == (1,)                      # files from before 1.0
    with pytest.raises(ConfigError, match="schema 2"):
        hl.Experiment.from_dict({"schema": 2})
    with pytest.raises(ConfigError, match="allowed: schema, scenario"):
        hl.Experiment.from_dict({"schemas": 1})


def test_written_files_carry_the_schema(tmp_path):
    p = tmp_path / "exp.yaml"
    p.write_text(EXAMPLE_CONFIG, encoding="utf-8")
    assert read_file(p)["schema"] == SCHEMA_VERSION
    for name in ("smoke.yaml", "street_grid.yaml", "open_area.toml", "study_smoke.yaml"):
        assert read_file(os.path.join(ROOT, "examples", name))["schema"] == SCHEMA_VERSION, name
    from handoverlab.gui.logic import RuleSettings, Settings, experiment_dict
    assert experiment_dict(Settings(), [RuleSettings()])["schema"] == SCHEMA_VERSION


def test_result_files_carry_and_check_the_schema(tmp_path, capsys):
    cfg = {"scenario": {"base": "smoke", "mobility": {"users": 4}, "run": {"duration_s": 4.0, "warmup_s": 1.0}},
           "seeds": [1], "rules": [{"rule": "a3"}]}
    p = tmp_path / "c.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    out = tmp_path / "r.json"
    assert main(["run", str(p), "-o", str(out), "-q"]) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["schema"] == SCHEMA_VERSION
    doc["schema"] = SCHEMA_VERSION + 1
    out.write_text(json.dumps(doc), encoding="utf-8")
    assert main(["verify", "--results", str(out), "-q"]) == 2
    assert "schema %d" % (SCHEMA_VERSION + 1) in capsys.readouterr().err


def test_study_schema_key():
    assert study_from_dict(dict(TINY, schema=1)).name == "tiny"
    with pytest.raises(ConfigError, match="study: written for schema 9"):
        study_from_dict(dict(TINY, schema=9))
    # the schema key does not enter the resolved study, so its lock hash is unchanged
    assert study_from_dict(dict(TINY, schema=1)).lock_hash() == study_from_dict(TINY).lock_hash()


def test_deprecation_helpers():
    with pytest.warns(HandoverLabDeprecationWarning, match="old_thing is deprecated since HandoverLab 1.1 and will "
                                                           "be removed in 2.0; use new_thing instead"):
        deprecated("old_thing", since="1.1", removed_in="2.0", instead="new_thing")
    assert issubclass(HandoverLabDeprecationWarning, FutureWarning)

    def new_func(x):
        return 2 * x
    old = deprecated_alias(new_func, "old_func", since="1.1", removed_in="2.0")
    with pytest.warns(HandoverLabDeprecationWarning, match="old_func .* use new_func instead"):
        assert old(3) == 6
    assert old.__name__ == "old_func"


def test_metric_aliases(monkeypatch):
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert metric_name("failures_pm") == "failures_pm"
    with pytest.raises(KeyError):
        metric_name("no_such_metric")
    monkeypatch.setitem(stability.METRIC_ALIASES, "rlf_pm", "failures_pm")
    with pytest.warns(HandoverLabDeprecationWarning, match="metric name 'rlf_pm'"):
        assert metric_name("rlf_pm") == "failures_pm"
    d = dict(TINY, compare=dict(TINY["compare"], metrics=["rlf_pm"]))
    with pytest.warns(HandoverLabDeprecationWarning):
        assert study_from_dict(d).compare.metrics == ("failures_pm",)
    with pytest.raises(ConfigError, match="compare.metrics: unknown metric 'nope'"):
        study_from_dict(dict(TINY, compare=dict(TINY["compare"], metrics=["nope"])))


def test_every_metric_and_count_is_documented():
    from handoverlab.engine import METRICS
    from handoverlab.stability import count_names
    with open(os.path.join(ROOT, "docs", "reference", "metrics.md"), encoding="utf-8") as f:
        page = f.read()
    missing = [m for m in list(METRICS) + count_names() if "`%s`" % m not in page]
    assert not missing, missing
    sc = hl.builtin_scenario("smoke").with_overrides({"mobility.users": 3, "run.duration_s": 3.0,
                                                        "run.warmup_s": 1.0})
    (res,) = hl.simulate(sc, [{"rule": "a3"}], seeds=[1])
    assert set(res.metrics) == set(METRICS) | set(count_names())
