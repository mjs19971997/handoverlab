# SPDX-License-Identifier: MIT
"""The contract test kit for rule plug-ins."""
import numpy as np
import pytest

import handoverlab as hl
from handoverlab.testing import ScaledA3, check_rule

SMALL = hl.builtin_scenario("smoke").with_overrides({"mobility.users": 8, "run.duration_s": 15.0,
                                                     "run.warmup_s": 2.0})


def test_builtin_rules_keep_the_contract():
    rep = check_rule("a3", {"off_db": 2.0, "ttt_s": 0.08}, scenario=SMALL)
    assert rep.ok and [n for n, _, _ in rep.results] == ["construct", "recreate", "debug run", "deterministic",
                                                         "global random state", "independent"]
    assert check_rule(hl.CHO, {"o_prep_db": -3.0, "n_max": 2}, scenario=SMALL).ok


def test_plugin_reduces_to_builtin():
    rep = check_rule(ScaledA3, {"off_db": 3.0, "ttt_s": 0.32, "v_ref": 8.0},
                     reduces_to=("a3", {"off_db": 3.0, "ttt_s": 0.32}, {"v_ref": 1e9}), scenario=SMALL)
    assert rep.ok and rep.results[-1][0] == "reduces_to a3"


def test_cho_immediate_reduces_to_a3_only_in_check_mode():
    sc = SMALL.with_overrides({"protocol.report_interval_s": 0.04, "protocol.cfg_loss_as_failure": True,
                               "run.warmup_s": 0.0})
    rep = check_rule(hl.CHO, {"o_prep_db": 3.0, "ttt_prep_s": 0.16, "immediate": True, "n_max": 1,
                              "rel_hys_db": 1e9}, reduces_to=("a3", {"off_db": 3.0, "ttt_s": 0.16}, {}), scenario=sc)
    assert rep.ok


class UsesGlobalRandom(hl.BaselineRule):
    def a3_offsets(self, obs):
        return 3.0 + np.random.random()

    def time_to_trigger(self, obs):
        return 0.16


class SharedState(hl.BaselineRule):
    calls = [0]                                       # class-level state shared between engines

    def a3_offsets(self, obs):
        self.calls[0] += 1
        return 3.0 + (self.calls[0] % 7)

    def time_to_trigger(self, obs):
        return 0.16


class ForgetsParams(hl.BaselineRule):
    def __init__(self, off_db=3.0, name="F"):
        super().__init__(name)
        self.off = off_db

    def a3_offsets(self, obs):
        return self.off

    def time_to_trigger(self, obs):
        return 0.16


def _failed(rep):
    return {n for n, ok, _ in rep.results if not ok}


def test_contract_names_the_broken_rules():
    assert "global random state" in _failed(check_rule(UsesGlobalRandom, scenario=SMALL, raise_on_failure=False))
    assert {"deterministic", "independent"} <= _failed(check_rule(SharedState, scenario=SMALL,
                                                                  raise_on_failure=False))
    assert _failed(check_rule(ForgetsParams, {"off_db": 2.0}, scenario=SMALL, raise_on_failure=False)) == {"construct"}
    with pytest.raises(AssertionError, match="FAIL  global random state"):
        check_rule(UsesGlobalRandom, scenario=SMALL)
