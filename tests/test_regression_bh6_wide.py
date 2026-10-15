# SPDX-License-Identifier: MIT
"""Wider regression sample against the bh6 prototype: metrics and event logs.

``data/bh6_wide.json`` (made by ``data/make_bh6_wide.py``) holds eight small
cases on the 2 x 2-block grid and the open area, with four rules each: other
site distances and speed profiles, shadowing that partly moves with the user,
UMa at 3.5 GHz, no clutter, N310/N311 = 2 with T310 = 0.5 s, label load,
preparation delay and L1 period, and conditional handover with immediate
execution.  Besides the metrics it stores the fingerprint of every bh6 event
log.

With the NumPy and SciPy builds of the reference every metric must be equal
to the last bit and every event log identical.  Otherwise (another platform
or version) the test asserts close agreement of the metrics, as
``test_regression_bh6.py`` does, and does not compare event logs.
"""
import json
import os

import numpy as np
import pytest
import scipy

import handoverlab as hl
from test_regression_bh6 import NAMES

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "data", "bh6_wide.json"), encoding="utf-8") as _f:
    REF = json.load(_f)

SAME_BUILD = (np.__version__ == REF["versions"]["numpy"] and scipy.__version__ == REF["versions"]["scipy"])

_RULE_KEYS = {"off": "off_db", "ttt": "ttt_s", "o_prep": "o_prep_db", "o_exec": "o_exec_db", "ttt_exec": "ttt_exec_s",
              "ttt_prep": "ttt_prep_s", "n_max": "n_max", "rel_hys": "rel_hys_db", "immediate": "immediate",
              "rule": "rule", "name": "name"}
_RADIO = {"place_share": "place_share", "pl_model": "pathloss", "h_bs": "bs_height_m", "fc_ghz": "carrier_ghz",
          "chi": "isolation"}
_PROTO = {"n310": "n310", "n311": "n311", "t310": "t310_s", "t_prep": "prep_s", "meas_period": "l1_period_s"}


def rules():
    return [{_RULE_KEYS[k]: v for k, v in r.items()} for r in REF["rules"]]


def scenario_for(case):
    s = case["scenario"]
    radio = {_RADIO[k]: ({"uma": "uma", "umi": "umi_street_canyon"}.get(v, v) if k == "pl_model" else v)
             for k, v in case["radio"].items()}
    radio["clutter_los"] = s.get("clutter", True)
    return hl.Scenario.from_dict({
        "layout": {"kind": "street_grid" if s["env"] == "grid" else "open_area", "blocks": [2, 2],
                   "site_spacing_m": s["isd"]},
        "radio": radio,
        "protocol": {_PROTO[k]: v for k, v in case["proto"].items()},
        "traffic": {"label_load": s.get("label_load", 1.0)},
        "mobility": {"users": s["n_ue"], "profile": s["profile"]},
        "run": {"duration_s": s["t_sim"], "warmup_s": s["discard"]},
    })


def test_sample_is_wide():
    assert len(REF["cases"]) == 8 and len(REF["rules"]) == 4
    events = sum(r["n_events"] for c in REF["cases"].values() for r in c["results"])
    assert events > 2000


@pytest.mark.parametrize("case_name", sorted(REF["cases"]))
def test_reproduces_bh6_wide(case_name):
    case = REF["cases"][case_name]
    debug = case_name in ("n310-2-t310-0.5", "open-veh16")          # some cases also in debug mode
    results = hl.simulate(scenario_for(case["case"]), rules(), seeds=[case["case"]["scenario"]["seed"]], debug=debug)
    assert [r.rule for r in results] == [r["rule"] for r in case["results"]]
    for res, ref in zip(results, case["results"]):
        if SAME_BUILD:
            assert res.fingerprint == ref["fingerprint"], (case_name, res.rule, "event log differs")
            assert res.n_events == ref["n_events"]
        for old, new in NAMES.items():
            want, got = ref[old], res.metrics[new]
            if SAME_BUILD:
                assert got == want, "%s/%s: %s = %r, bh6 %s = %r" % (case_name, res.rule, new, got, old, want)
            elif new.endswith("_pm") or new.startswith("n_"):
                scale = 1.0 if new.endswith("_pm") else res.metrics["ue_minutes"]
                assert abs(got - want) <= max(0.10 * abs(want), 0.5 * scale), (case_name, res.rule, new, got, want)
            else:
                assert got == pytest.approx(want, rel=0.02, abs=1e-6), (case_name, res.rule, new)
