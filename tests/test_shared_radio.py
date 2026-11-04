# SPDX-License-Identifier: MIT
"""Shared radio samples for scenario variants that differ only in engine settings (since 2.11.0).

Pass criterion fixed before the code: every engine of a shared-radio run gives the same fingerprint, metrics, event
log and trace as its own separate run, compared with ``==`` in the same process.  The rule that decides which
variants may share is strict, and a static check makes sure that no code the world or the radio samples depend on
reads an engine-only setting.
"""
import ast
import copy
import dataclasses
import glob
import io
import json
import os
import tokenize

import pytest

import handoverlab as hl
from handoverlab.config import DcConfig, ProtocolConfig
from handoverlab.simulate import ENGINE_BEAM_KEYS, RADIO_PROTOCOL_KEYS, radio_key, run_shared, simulate_variants
from handoverlab.studies import StudyStore, load_study, run_study

SRC = os.path.dirname(os.path.abspath(hl.__file__))
BEAMS = {"sectors": 3, "sector_az0_deg": 30.0, "n_ssb": 8, "panel": [8, 8], "tilt_deg": 102.0}
UMA = {"mobility.users": 8, "run.duration_s": 8.0, "run.warmup_s": 1.0}
RULES = [{"rule": "a3", "name": "A3", "off_db": 3.0, "ttt_s": 0.256},
         {"rule": "cho", "name": "CHO", "o_exec_db": 2.0}]


def _beams(**keys):
    return {"radio.beams": dict(BEAMS, **keys)}


def _uma(*parts):
    over = dict(UMA)
    for p in parts:
        over.update(p)
    return hl.builtin_scenario("urban-macro-tr37885-4ghz").with_overrides(over)


def _smoke(over=None):
    sc = hl.builtin_scenario("smoke").with_overrides({"mobility.users": 6, "run.duration_s": 10.0,
                                                        "run.warmup_s": 1.0})
    return sc.with_overrides(over) if over else sc


def _exact(x):
    """Canonical JSON: floats by repr (exact; NaN equals NaN, -0.0 differs from 0.0)."""
    return json.dumps(x, sort_keys=True, default=repr)


def _view(r):
    return _exact([r.rule, r.fingerprint, r.n_events, r.metrics, r.events, r.trace])


def _check_shared(scenarios, seed=5, rules=RULES, log_events="full", **kw):
    """Shared run of all scenarios against a separate run of each, in this process."""
    worlds = [hl.build_world(sc, seed) for sc in scenarios]
    shared = run_shared(worlds, [rules] * len(worlds), log_events, **kw)
    for sc, got in zip(scenarios, shared):
        alone = hl.run_world(hl.build_world(sc, seed), rules, log_events, **kw)
        assert [_view(r) for r in got] == [_view(r) for r in alone]
        if len(scenarios) > 1:
            assert all(r.timing["radio_shared"] == len(scenarios) for r in got)
    return shared


# ---------------------------------------------------------------------------------------------- the sharing rule
def _engine_only_names():
    names = set(ENGINE_BEAM_KEYS) | {f.name for f in dataclasses.fields(DcConfig)}
    names |= {f.name for f in dataclasses.fields(ProtocolConfig)} - set(RADIO_PROTOCOL_KEYS)
    return names


def _radio_modules():
    """Every module that build_world and the radio sources run (their package imports included)."""
    files = glob.glob(os.path.join(SRC, "channel", "*.py"))
    files += [os.path.join(SRC, m + ".py") for m in ("world", "layout", "mobility", "traffic", "mapfile", "seeds",
                                                     "requirements")]
    return files


def test_radio_code_reads_no_engine_setting():
    names = _engine_only_names()
    found = []
    for path in _radio_modules():
        with open(path, encoding="utf-8") as f:
            toks = list(tokenize.generate_tokens(io.StringIO(f.read()).readline))
        for a, b in zip(toks, toks[1:]):
            if a.type == tokenize.OP and a.string == "." and b.type == tokenize.NAME and b.string in names:
                found.append("%s:%d .%s" % (os.path.basename(path), b.start[0], b.string))
        for t in toks:                                        # getattr(obj, "name") and dictionary keys
            if t.type == tokenize.STRING:
                try:
                    v = ast.literal_eval(t.string)
                except ValueError:
                    continue
                if isinstance(v, str) and v in names:
                    found.append("%s:%d %r" % (os.path.basename(path), t.start[0], v))
    assert not found, found


def test_radio_modules_import_nothing_else_of_the_package():
    # the static check above covers the whole package code that the world and the radio samples run
    allowed = {"config", "layout", "seeds", "requirements", "mobility", "traffic", "mapfile", "world"}
    for path in _radio_modules():
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        in_channel = os.path.basename(os.path.dirname(path)) == "channel"
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level:
                mod = (node.module or "").split(".")[0]
                if in_channel and node.level == 1:
                    continue                                  # another module of channel/
                if not in_channel and mod == "channel":
                    continue
                assert mod in allowed, (path, node.module)


def test_radio_key_ignores_only_engine_settings():
    base = _uma(_beams())
    k = radio_key(base)
    same = [_beams(ssb_sinr="ssb", ssb_overlap=0.5), _beams(bfd=False, bfi_max=5), _beams(rlm_rs="beams"),
            {"protocol.t310_s": 0.5}, {"protocol.meas_periods": "ts38133"}, {"protocol.l3_k": 0}]
    for over in same:
        assert radio_key(base.with_overrides(over)) == k, over
    assert radio_key(base.with_overrides({"name": "other"})) == k
    other = [_beams(n_ssb=4), _beams(angular_spread="tr38901"), _beams(ue_rx="best", ue_panels=2),
             {"protocol.step_s": 0.005}, {"protocol.l1_period_s": 0.08}, {"run.duration_s": 9.0},
             {"traffic.label_load": 0.5}, {"radio.los_process": "poisson_lines"}]
    for over in other:
        assert radio_key(base.with_overrides(over)) != k, over
    nb = copy.deepcopy(base)
    nb.run.backend = "numba"                                  # set directly: Numba need not be installed here
    assert radio_key(nb) != k


def test_run_shared_refuses_what_may_not_share():
    a = hl.build_world(_smoke(), 1)
    with pytest.raises(ValueError, match="more than engine settings"):
        run_shared([a, hl.build_world(_smoke({"radio.isolation": 0.5}), 1)], [RULES, RULES])
    with pytest.raises(ValueError, match="different seeds"):
        run_shared([a, hl.build_world(_smoke(), 2)], [RULES, RULES])
    with pytest.raises(ValueError, match="rule lists"):
        run_shared([a], [RULES, RULES])
    assert run_shared([], []) == []


# ---------------------------------------------------------------------------------------------- equality (criterion 5c)
def test_one_carrier_variants_batched_and_one_by_one():
    scs = [_smoke(), _smoke({"protocol.t310_s": 0.5}), _smoke({"protocol.l3_k": 8}),
           _smoke({"protocol.qout_db": -6.0, "protocol.n310": 2}), _smoke({"protocol.rlm_interference": "dynamic"})]
    _check_shared(scs, log_events="summary")
    _check_shared(scs, log_events="summary", batch=False)
    _check_shared(scs, log_events="full", chunk_steps=137)


def test_beam_variants_ssb_sinr_and_beam_failure():
    scs = [_uma(_beams()), _uma(_beams(ssb_sinr="ssb", ssb_overlap=1.0)), _uma(_beams(bfd=False)),
           _uma(_beams(rlm_rs="beams")), _uma(_beams(), {"protocol.meas_periods": "ts38133"})]
    shared = _check_shared(scs)
    assert len({r.fingerprint for rs in shared for r in rs if r.rule == "A3"}) > 1   # the variants do differ


def test_angular_spread_variants():
    sp = _beams(angular_spread="tr38901")
    q = _beams(angular_spread="tr38901", ssb_sinr="ssb")
    b = _beams(angular_spread="tr38901", ssb_sinr="ssb", bfd=False)
    over = {"run.duration_s": 4.0, "mobility.users": 5}
    _check_shared([_uma(sp, over), _uma(q, over), _uma(b, over)], rules=RULES[:1])


def test_layer_variants():
    two = {"radio.carrier_ghz": 3.5, "radio.bandwidth_mhz": 100.0, "protocol.meas_periods": "ts38133",
           "radio.layers": [{"name": "fr2", "carrier_ghz": 28.0, "bandwidth_mhz": 400.0, "site_spacing_m": 200.0,
                             "beams": {"sectors": 3, "n_ssb": 8}}]}
    off = dict(two, **{"radio.layers": [dict(two["radio.layers"][0], beams={"sectors": 3, "n_ssb": 8, "bfd": False})]})
    _check_shared([_smoke(two), _smoke(off), _smoke(dict(two, **{"protocol.gap_pattern": 1}))])


def test_dual_connectivity_variants():
    def dc(**d):
        d.setdefault("scg_layer", "fr2")
        return hl.Scenario.from_dict({
            "name": "dc-test",
            "layout": {"kind": "highway", "lanes": 1, "road_length_m": 1600.0, "sites": [[0.0, 80.0]]},
            "radio": {"carrier_ghz": 3.5, "bandwidth_mhz": 20.0, "tx_power_dbm": 46.0, "bs_height_m": 25.0,
                      "pathloss": "uma", "bs_gain_db": 15.0, "time_var_db": 0.0, "map_res_m": 4.0,
                      "layers": [{"name": "fr2", "carrier_ghz": 28.0, "bandwidth_mhz": 100.0, "scs_khz": 120.0,
                                  "tx_power_dbm": 30.0, "bs_height_m": 10.0, "pathloss": "umi_street_canyon",
                                  "bs_gain_db": 20.0, "noise_figure_db": 10.0,
                                  "sites": [[-600.0, 15.0], [-200.0, 15.0], [200.0, 15.0], [600.0, 15.0]]}]},
            "protocol": {"dc": d},
            "mobility": {"users": 2,
                         "groups": [{"share": 1.0, "v_min": 20.0, "v_max": 20.0, "lateral_m": [0.0, 0.0]}]},
            "run": {"duration_s": 20.0, "warmup_s": 0.0}})
    no_dc = dc().with_overrides({"protocol.dc": None})
    _check_shared([dc(), dc(add_thresh_dbm=-100.0), no_dc], rules=RULES[:1])


def test_simulate_variants_equals_simulate():
    scs = [_smoke(), _smoke({"radio.isolation": 0.5}), _smoke({"protocol.t310_s": 0.5}),
           _smoke({"radio.isolation": 0.5, "protocol.l3_k": 2})]
    groups = []
    got = simulate_variants(scs, RULES, seeds=[3, 4], log_events=True, progress=groups.append)
    assert len(groups) == 4                                   # 2 seeds x 2 radio streams
    for sc, res in zip(scs, got):
        alone = hl.simulate(sc, RULES, seeds=[3, 4], log_events=True)
        assert [(r.seed, _view(r)) for r in res] == [(r.seed, _view(r)) for r in alone]
        assert all(r.timing["radio_shared"] == 2 and r.timing["world_s"] > 0 for r in res)
    off = simulate_variants(scs, RULES, seeds=[3], share_radio=False)
    assert [[r.fingerprint for r in rs] for rs in off] == [[r.fingerprint for r in rs if r.seed == 3] for rs in got]
    assert all("radio_shared" not in r.timing for rs in off for r in rs)


# ---------------------------------------------------------------------------------------------- studies
STUDY = {"name": "shared",
         "scenario": {"base": "smoke", "layout": {"kind": "open_area", "blocks": [1, 1]},
                      "mobility": {"users": 6, "profile": "veh30"}, "run": {"duration_s": 8.0, "warmup_s": 1.0}},
         "conditions": {"protocol.t310_s": [0.5, 1.0], "radio.isolation": [0.5, 1.0]},
         "seeds": {"test": [1, 2]},
         "methods": {"A3": {"rule": "a3"}, "CHO": {"rule": "cho", "fixed": {"o_exec_db": 2.0}}},
         "events": "summary"}


def test_study_with_shared_radio_gives_the_same_records(tmp_path):
    st = load_study(STUDY)
    msgs = []
    run_study(st, str(tmp_path / "alone"), workers=1)
    run_study(st, str(tmp_path / "shared"), workers=1, share_radio=True, progress=msgs.append)
    assert any("8 jobs in 4 radio streams" in m for m in msgs)

    def view(root):
        out = {}
        for rec in StudyStore(root).records("test"):
            for x in rec["rules"]:
                out[(rec["job"], x["name"])] = _exact([x["fingerprint"], x["metrics"], x["n_events"], x["run_key"]])
        return out
    a, s = view(str(tmp_path / "alone")), view(str(tmp_path / "shared"))
    assert a == s and len(a) == 16
    recs = StudyStore(str(tmp_path / "shared")).records("test")
    assert all(rec["radio_shared"] == 2 for rec in recs)
    assert not any("radio_shared" in rec for rec in StudyStore(str(tmp_path / "alone")).records("test"))
    for rec in recs:                                          # event logs written per job as in a separate run
        for x in rec["rules"]:
            assert os.path.exists(os.path.join(str(tmp_path / "shared"), x["events"]))


def test_study_with_shared_radio_and_two_workers(tmp_path):
    st = load_study(STUDY)
    run_study(st, str(tmp_path / "one"), workers=1)
    run_study(st, str(tmp_path / "two"), workers=2, share_radio=True)

    def prints(root):
        return {(rec["job"], x["name"]): x["fingerprint"] for rec in StudyStore(root).records() for x in rec["rules"]}
    assert prints(str(tmp_path / "one")) == prints(str(tmp_path / "two"))
