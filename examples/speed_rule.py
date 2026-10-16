# SPDX-License-Identifier: MIT
"""Your own handover rule in a few lines: Event A3 whose time-to-trigger shrinks with the speed.

Run it:  python examples/speed_rule.py
It registers the rule as "a3_speed", checks its contract with the test kit, and compares it with
plain A3 on the same worlds (see docs/tutorials/own-rule.md).
"""
import numpy as np

import handoverlab as hl
from handoverlab.testing import check_rule


@hl.register_rule("a3_speed")
class SpeedScaledA3(hl.BaselineRule):
    """Event A3 whose time-to-trigger shrinks with the reported speed."""

    def __init__(self, off_db=3.0, ttt_s=0.32, v_ref=8.0, name="A3-speed"):
        super().__init__(name)
        self.off_db, self.ttt_s, self.v_ref = off_db, ttt_s, v_ref

    def params(self):
        return dict(off_db=self.off_db, ttt_s=self.ttt_s, v_ref=self.v_ref)

    def a3_offsets(self, obs):                    # scalar, or an array (users x cells)
        return self.off_db

    def time_to_trigger(self, obs):               # scalar, or an array (users,)
        return self.ttt_s * np.minimum(1.0, self.v_ref / np.maximum(obs.speed, 1e-6))


if __name__ == "__main__":
    # 1. the contract: deterministic, independent of other rules, no global random state, and with
    #    v_ref = 1e9 the rule is plain A3 with the same offset and time-to-trigger
    report = check_rule(SpeedScaledA3, params={"off_db": 3.0, "ttt_s": 0.32, "v_ref": 8.0},
                        reduces_to=("a3", {"off_db": 3.0, "ttt_s": 0.32}, {"v_ref": 1e9}))
    print(report)

    # 2. a paired comparison: both rules on the same worlds and radio samples
    sc = hl.builtin_scenario("smoke").with_overrides({"mobility.profile": "veh30"})
    rules = [{"rule": "a3", "name": "A3", "off_db": 3.0, "ttt_s": 0.32},
             {"rule": "a3_speed", "name": "A3-speed", "off_db": 3.0, "ttt_s": 0.32, "v_ref": 8.0}]
    res = hl.simulate(sc, rules, seeds=[1, 2, 3])
    print("%-9s %4s %10s %12s %9s" % ("rule", "seed", "handovers", "unnecessary", "failures"))
    for r in res:
        print("%-9s %4d %10.2f %12.2f %9.2f" % (r.rule, r.seed, r.metrics["handovers_pm"],
                                               r.metrics["unnecessary_pm"], r.metrics["failures_pm"]))
