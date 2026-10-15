# SPDX-License-Identifier: MIT
"""Configuration loading, validation, layouts and the command line."""
import csv
import json

import numpy as np
import pytest

import handoverlab as hl
from handoverlab.cli import EXAMPLE_CONFIG, main
from handoverlab.config import ConfigError, read_file
from handoverlab.layout import make_layout


def test_default_grid_is_three_by_three():
    sc = hl.Scenario()
    assert sc.layout.blocks == (3, 3)
    lay = make_layout(sc.layout)
    assert len(lay.xs) == 4 and len(lay.ys) == 4 and len(lay.buildings) == 9
    assert lay.xmax - lay.xmin == pytest.approx(3 * 433.0 + 20.0)


def test_grid_size_configurable():
    lay = make_layout(hl.Scenario.from_dict({"layout": {"blocks": [2, 1]}}).layout)
    assert len(lay.buildings) == 2 and len(lay.xs) == 3 and len(lay.ys) == 2


def test_open_area_matches_grid_rectangle():
    sc = hl.Scenario.from_dict({"layout": {"kind": "open_area", "blocks": [2, 2]}})
    lay = make_layout(sc.layout)
    assert (lay.xmax - lay.xmin, lay.ymax - lay.ymin) == (886.0, 520.0)
    assert len(lay.buildings) == 0


def test_unknown_key_named():
    with pytest.raises(ConfigError, match="scenario.radio.carrier"):
        hl.Scenario.from_dict({"radio": {"carrier": 3.5}})


def test_wrong_type_and_range_named():
    with pytest.raises(ConfigError, match="mobility.users"):
        hl.Scenario.from_dict({"mobility": {"users": "many"}})
    with pytest.raises(ConfigError, match="radio.place_share"):
        hl.Scenario.from_dict({"radio": {"place_share": 1.5}})
    with pytest.raises(ConfigError, match="l1_period_s"):
        hl.Scenario.from_dict({"protocol": {"l1_period_s": 0.045}})


def test_overrides_and_round_trip():
    sc = hl.Scenario().with_overrides({"layout.site_spacing_m": 50, "radio.carrier_ghz": 3.5})
    assert sc.layout.site_spacing_m == 50.0 and sc.radio.carrier_ghz == 3.5
    assert hl.Scenario.from_dict(json.loads(json.dumps(sc.to_dict()))) == sc


def test_yaml_toml_json_equivalent(tmp_path):
    (tmp_path / "c.yaml").write_text(EXAMPLE_CONFIG, encoding="utf-8")
    exp_yaml = hl.load_config(tmp_path / "c.yaml")
    data = read_file(tmp_path / "c.yaml")
    (tmp_path / "c.json").write_text(json.dumps(data), encoding="utf-8")
    toml = ('seeds = [1]\noutput = "results/metrics.csv"\n'
            '[scenario]\nname = "street-grid-10GHz"\n'
            '[scenario.layout]\nkind = "street_grid"\nblocks = [3, 3]\nsite_spacing_m = 100.0\n'
            '[scenario.radio]\ncarrier_ghz = 10.0\npathloss = "umi_street_canyon"\n'
            '[scenario.mobility]\nusers = 20\nprofile = "veh16"\n'
            '[scenario.run]\nduration_s = 60.0\nwarmup_s = 10.0\n'
            '[[rules]]\nrule = "a3"\nname = "A3"\noff_db = 3.0\nttt_s = 0.16\n'
            '[[rules]]\nrule = "cho"\nname = "CHO"\no_prep_db = -2.0\no_exec_db = 3.0\nttt_exec_s = 0.08\nn_max = 4\n')
    (tmp_path / "c.toml").write_text(toml, encoding="utf-8")
    assert hl.load_config(tmp_path / "c.json") == exp_yaml
    assert hl.load_config(tmp_path / "c.toml") == exp_yaml


def test_rule_registry():
    assert {"a3", "cho"} <= set(hl.available_rules())
    with pytest.raises(KeyError):
        hl.make_rule({"rule": "nope"})
    with pytest.raises(ValueError, match="off_db"):
        hl.make_rule({"rule": "a3", "offset": 3})

    @hl.register_rule("a3_test_fixed")
    class FixedA3(hl.BaselineRule):
        def a3_offsets(self, obs):
            return np.full(obs.gap_db.shape, 4.0)

        def time_to_trigger(self, obs):
            return np.full(len(obs.serving), 0.1)

    assert isinstance(hl.make_rule({"rule": "a3_test_fixed"}), FixedA3)


def test_cli_run_writes_csv_and_json(tmp_path, capsys):
    cfg = {
        "scenario": {"layout": {"kind": "open_area", "blocks": [1, 1], "site_spacing_m": 150.0},
                     "mobility": {"users": 4, "profile": "veh16"}, "run": {"duration_s": 10.0, "warmup_s": 2.0}},
        "seeds": [1],
        "rules": [{"rule": "a3"}, {"rule": "cho"}],
    }
    path = tmp_path / "small.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    out_csv = tmp_path / "out" / "m.csv"
    assert main(["run", str(path), "-o", str(out_csv), "--events", str(tmp_path / "ev.csv")]) == 0
    rows = list(csv.DictReader(out_csv.open(encoding="utf-8")))
    assert [r["rule"] for r in rows] == ["A3", "CHO"]
    assert {"seed", "handovers_pm", "failures_pm", "unnecessary_pm", "param.off_db"} <= set(rows[0])
    out_json = tmp_path / "m.json"
    assert main(["run", str(path), "-o", str(out_json), "-q"]) == 0
    doc = json.loads(out_json.read_text(encoding="utf-8"))
    assert doc["results"][0]["metrics"]["handovers_pm"] == float(rows[0]["handovers_pm"])
    assert doc["scenario"]["layout"]["kind"] == "open_area"


def test_cli_rejects_bad_config(tmp_path, capsys):
    path = tmp_path / "bad.yaml"
    path.write_text("scenario:\n  layout:\n    blokcs: [3, 3]\n", encoding="utf-8")
    assert main(["run", str(path)]) == 2
    assert "scenario.layout.blokcs" in capsys.readouterr().err
