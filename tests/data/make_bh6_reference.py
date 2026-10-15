# SPDX-License-Identifier: MIT
"""Regenerate ``bh6_reference.json`` from the bh6 prototype.

bh6 is the research prototype from which HandoverLab was ported.  It is not
part of this repository; to rerun this script put the directory that contains
the ``bh6`` package on ``PYTHONPATH`` (or in the ``BH6_PATH`` environment
variable).  The test suite only reads the stored JSON file.

The cases are small on purpose: a 2 x 2-block street grid (the only grid size
bh6 supports), 150 m site spacing, 20 users, 40 s with 10 s warm-up, seed 1,
one A3 and one CHO setting.  Case ``default`` uses the default radio
settings; case ``stress`` removes the beam isolation (isolation 1.0) and uses
30 m/s users so that the failure model is exercised too.
"""
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

CASES = {
    "default": dict(scenario=dict(env="grid", isd=150.0, profile="veh16", n_ue=20, t_sim=40.0, discard=10.0, seed=1),
                    radio={}),
    "stress": dict(scenario=dict(env="grid", isd=150.0, profile="veh30", n_ue=20, t_sim=40.0, discard=10.0, seed=1),
                   radio={"chi": 1.0}),
}
RULES = [
    {"rule": "a3", "name": "A3", "off": 3.0, "ttt": 0.16},
    {"rule": "cho", "name": "CHO", "o_prep": -2.0, "o_exec": 3.0, "ttt_exec": 0.08, "n_max": 4},
]


def main():
    out_cases = {}
    for name, case in CASES.items():
        sc = Scenario(**case["scenario"]).with_(**{"radio__" + k: v for k, v in case["radio"].items()})
        res, _ = run_rules(sc, RULES)
        for r in res:
            r.pop("wall_s", None)
        out_cases[name] = dict(case=case, results=res)
    doc = dict(
        note="Metrics of the bh6 prototype (v1.0.0); metric names are bh6's own.",
        rules=RULES, cases=out_cases,
        versions=dict(python=platform.python_version(), numpy=numpy.__version__, scipy=scipy.__version__,
                      platform=platform.platform()),
    )
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bh6_reference.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
    print("wrote", out)


if __name__ == "__main__":
    main()
