# SPDX-License-Identifier: MIT
"""Regression against the bh6 prototype from which HandoverLab was ported.

``data/bh6_reference.json`` holds the metrics that bh6 (v1.0.0) produced for
two small cases on a 2 x 2-block street grid (the only grid size bh6
supports): 150 m site spacing, 20 users, 40 s with 10 s warm-up, seed 1, one
A3 and one CHO setting; case ``stress`` removes the beam isolation and uses
30 m/s users so that failures occur.  ``data/make_bh6_reference.py`` shows how
the file was made.

HandoverLab keeps bh6's random-stream layout, the order of all random draws
and the order of the floating-point operations, so with the same NumPy and
SciPy builds the results are bit-identical: every count equal and every
averaged quantity equal to the last bit.  That is what the test asserts when
the installed NumPy and SciPy versions match the ones recorded in the
reference file.

Bit-identity cannot be promised across other versions or platforms: NumPy
guarantees identical random streams only for the same build, the Gaussian
smoothing of the shadowing field (SciPy, float32) and BLAS summations may
differ in the last bits, and a handover is a threshold decision, so a
last-bit difference can move a single event.  In that case the test asserts
close agreement instead: every per-UE-minute rate within 10 % or 0.5 events
per UE-minute (5 events in this 10 UE-minute case), and the averaged radio
quantities within 2 %.
"""
import json
import os

import numpy as np
import pytest
import scipy

import handoverlab as hl
from handoverlab.stability import LEGACY_1X

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "data", "bh6_reference.json"), encoding="utf-8") as _f:
    REF = json.load(_f)

RULES = [  # the bh6 settings of REF["rules"] in HandoverLab's parameter names
    {"rule": "a3", "name": "A3", "off_db": 3.0, "ttt_s": 0.16},
    {"rule": "cho", "name": "CHO", "o_prep_db": -2.0, "o_exec_db": 3.0, "ttt_exec_s": 0.08, "n_max": 4},
]

_CAUSES = {"late_cmd": "command_lost", "late_prep": "rlf_in_preparation", "late_rlf": "rlf_without_handover",
           "cov_rlf": "coverage_rlf", "exec_fail": "execution_failure", "early_rlf": "rlf_after_handover"}
_OUTCOMES = {"useful": "useful", "unnecessary": "unnecessary", "early": "too_early", "wrong": "wrong_cell",
             "late": "too_late", "censored": "censored"}
NAMES = {  # bh6 metric -> HandoverLab metric
    "ue_min": "ue_minutes", "att_pm": "attempts_pm", "ho_pm": "handovers_pm", "exec_pm": "executions_pm",
    "uho_pm": "unnecessary_pm", "uho_and_pm": "unnecessary_short_and_low_pm",
    "uho_gain_pm": "unnecessary_low_gain_pm", "pp_pm": "pingpong_pm", "fail_pm": "failures_pm",
    "late_pm": "too_late_pm", "early_pm": "too_early_pm", "wrong_pm": "wrong_cell_pm",
    "prep_mean": "prepared_cells_mean", "prep_req_pm": "preparations_pm", "prep_wasted_pm": "unused_preparations_pm",
    "cfg_lost_pm": "lost_configurations_pm", "reports_pm": "reports_pm", "rel_pm": "releases_pm",
    "rec_pm": "recoveries_pm", "int_s_pm": "interruption_s_pm", "int_exec_s_pm": "interruption_exec_s_pm",
    "int_fail_s_pm": "interruption_fail_s_pm", "outage_pct": "outage_pct", "rate_mbps": "rate_mbps",
    "delivered": "delivered_share", "sinr_db": "sinr_db", "se": "spectral_eff", "mean_load": "mean_load",
    "prep_left": "open_preparations", "late_rlf_prepared_pm": "rlf_with_prepared_cell_pm",
    "c_att": "n_attempts", "c_exec": "n_executions", "c_ho": "n_handovers", "c_fail": "n_failures",
    "c_pp": "n_pingpong", "c_prep_req": "n_preparations", "c_cfg_ok": "n_configurations",
    "c_cfg_lost": "n_lost_configurations", "c_prep_cancel": "n_cancelled_preparations",
    "c_prep_used": "n_used_preparations", "c_prep_wasted": "n_unused_preparations", "c_rel": "n_releases",
    "c_rec": "n_recoveries", "c_reports": "n_reports",
}
NAMES.update({"f_%s_pm" % k: "fail_%s_pm" % v for k, v in _CAUSES.items()})
NAMES.update({"c_f_%s" % k: "n_fail_%s" % v for k, v in _CAUSES.items()})
NAMES.update({"n_%s" % k: "n_%s" % v for k, v in _OUTCOMES.items()})

SAME_BUILD = (np.__version__ == REF["versions"]["numpy"] and scipy.__version__ == REF["versions"]["scipy"])


def scenario_for(case):
    s, radio = case["scenario"], case["radio"]
    return hl.Scenario.from_dict({  # the prototype of 1.x: legacy settings (2.0.0)
        "layout": {"kind": "street_grid", "blocks": [2, 2], "site_spacing_m": s["isd"]},
        "mobility": {"users": s["n_ue"], "profile": s["profile"]},
        "run": {"duration_s": s["t_sim"], "warmup_s": s["discard"]},
        "radio": {"isolation": radio.get("chi", 0.30)},
    }).with_overrides(LEGACY_1X)


@pytest.mark.parametrize("case_name", sorted(REF["cases"]))
def test_reproduces_bh6(case_name):
    case = REF["cases"][case_name]
    results = hl.simulate(scenario_for(case["case"]), RULES, seeds=[case["case"]["scenario"]["seed"]])
    assert len(results) == len(case["results"]) == 2
    for res, ref in zip(results, case["results"]):
        assert res.rule == ref["rule"]
        compared = 0
        for old, new in NAMES.items():
            want, got = ref[old], res.metrics[new]
            compared += 1
            if SAME_BUILD:
                assert got == want, "%s/%s: %s = %r, bh6 %s = %r" % (case_name, res.rule, new, got, old, want)
            elif new.endswith("_pm") or new.startswith("n_"):
                scale = 1.0 if new.endswith("_pm") else res.metrics["ue_minutes"]
                assert abs(got - want) <= max(0.10 * abs(want), 0.5 * scale), (case_name, res.rule, new, got, want)
            else:
                assert got == pytest.approx(want, rel=0.02, abs=1e-6), (case_name, res.rule, new)
        assert compared == len([k for k in ref if k not in ("rule", "kind")])
