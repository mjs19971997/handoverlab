# SPDX-License-Identifier: MIT
"""Regenerate ``bh6_wide.json``: a wider regression sample against the bh6 prototype.

Eight small cases that cover what the two cases of ``bh6_reference.json`` do
not: other site distances and speed profiles, the open area, shadowing that
partly moves with the user, the UMa model at 3.5 GHz, no clutter, N310/N311 > 1
with a shorter T310, a different label load, preparation delay and L1 period,
and conditional handover with immediate execution.  Each case runs four rules
and stores bh6's metrics together with the fingerprint of its event log
(computed as in :mod:`handoverlab.eventlog`, after renaming bh6's outcome,
cause and kind names to HandoverLab's).

bh6 is not part of this repository; put the directory that contains the
``bh6`` package on ``PYTHONPATH`` or in ``BH6_PATH`` to rerun this script.
"""
import hashlib
import json
import os
import platform
import sys

if os.environ.get("BH6_PATH"):
    sys.path.insert(0, os.environ["BH6_PATH"])

import numpy
import scipy
from bh6.params import Scenario
from bh6.sim import run_rules

BASE = dict(env="grid", isd=100.0, profile="veh16", n_ue=16, t_sim=30.0, discard=5.0)
CASES = {
    "isd50-ped": dict(scenario=dict(isd=50.0, profile="ped", seed=2), radio={}, proto={}),
    "isd100-veh8": dict(scenario=dict(profile="veh8", seed=3), radio={}, proto={}),
    "mix-own-shadowing": dict(scenario=dict(profile="mix", seed=4), radio={"place_share": 0.5}, proto={}),
    "open-veh16": dict(scenario=dict(env="open", seed=5), radio={}, proto={}),
    "uma-3.5ghz": dict(scenario=dict(isd=150.0, seed=6), radio={"pl_model": "uma", "h_bs": 25.0, "fc_ghz": 3.5},
                       proto={}),
    "no-clutter-c30": dict(scenario=dict(profile="c30", clutter=False, seed=7), radio={"chi": 1.0}, proto={}),
    "n310-2-t310-0.5": dict(scenario=dict(profile="veh30", seed=8), radio={"chi": 1.0},
                            proto={"n310": 2, "n311": 2, "t310": 0.5}),
    "label-load-prep": dict(scenario=dict(seed=9, label_load=0.5), radio={},
                            proto={"t_prep": 0.1, "meas_period": 0.02}),
}
RULES = [
    {"rule": "a3", "name": "A3", "off": 3.0, "ttt": 0.16},
    {"rule": "a3", "name": "A3-late", "off": 6.0, "ttt": 0.32},
    {"rule": "cho", "name": "CHO", "o_prep": -2.0, "o_exec": 3.0, "ttt_exec": 0.08, "n_max": 4},
    {"rule": "cho", "name": "CHO-imm", "o_prep": 3.0, "ttt_prep": 0.16, "immediate": True, "n_max": 1,
     "rel_hys": 1e9},
]
OUTCOME = {"early": "too_early", "wrong": "wrong_cell", "late": "too_late"}
CAUSE = {"late_cmd": "command_lost", "late_prep": "rlf_in_preparation", "late_rlf": "rlf_without_handover",
         "cov_rlf": "coverage_rlf", "exec_fail": "execution_failure", "early_rlf": "rlf_after_handover"}
KIND = {"bho": "ho"}


def canon(v):
    if isinstance(v, str):
        return v
    if isinstance(v, (int, numpy.integer)) and not isinstance(v, bool):
        return str(int(v))
    return repr(float(v) + 0.0)


def fingerprint(log):
    lines = ["t_attempt,t_exec,t_end,ue,kind,src,tgt,outcome,cause,dwell,gain_db,n_prepared,o_exec,x,y"]
    for r in log:
        r = list(r)
        r[4] = KIND.get(r[4], r[4])
        r[7] = OUTCOME.get(r[7], r[7])
        r[8] = CAUSE.get(r[8], r[8])
        lines.append(",".join(canon(v) for v in r))
    return hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest(), len(log)


def main():
    out = {}
    for name, case in CASES.items():
        sc = Scenario(**dict(BASE, **case["scenario"]))
        kw = {"radio__" + k: v for k, v in case["radio"].items()}
        kw.update({"proto__" + k: v for k, v in case["proto"].items()})
        sc = sc.with_(**kw)
        res, engines = run_rules(sc, RULES, log_events=True)
        for r, e in zip(res, engines):
            r.pop("wall_s", None)
            r["fingerprint"], r["n_events"] = fingerprint(e.log)
        out[name] = dict(case=dict(case, scenario=dict(BASE, **case["scenario"])), results=res)
        print(name, [(r["rule"], r["n_events"], r["c_ho"], r["c_fail"]) for r in res], flush=True)
    doc = dict(note="Metrics and event-log fingerprints of the bh6 prototype (v1.0.0); metric names are bh6's own.",
               rules=RULES, cases=out,
               versions=dict(python=platform.python_version(), numpy=numpy.__version__, scipy=scipy.__version__,
                             platform=platform.platform()))
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bh6_wide.json")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1)
    print("wrote", path)


if __name__ == "__main__":
    main()
