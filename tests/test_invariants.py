# SPDX-License-Identifier: MIT
"""Invariant checks of the engine (debug mode) and the end-of-run conservation checks."""
import numpy as np
import pytest

import handoverlab as hl
from handoverlab.engine import Engine, InvariantError
from handoverlab.engine.invariants import check_final
from handoverlab.rules import A3
from handoverlab.world import build_world

RULES = [{"rule": "a3"}, {"rule": "cho"}, {"rule": "cho", "immediate": True, "o_prep_db": 3.0, "ttt_prep_s": 0.16}]


@pytest.fixture(scope="module")
def world():
    sc = hl.builtin_scenario("smoke").with_overrides({"radio.isolation": 1.0, "mobility.profile": "veh30",
                                                      "mobility.users": 10, "run.duration_s": 15.0,
                                                      "run.warmup_s": 0.0})
    return build_world(sc, 4)


def test_debug_mode_changes_nothing(world):
    a = hl.run_world(world, RULES)
    b = hl.run_world(world, RULES, debug=True)
    for x, y in zip(a, b):
        assert x.fingerprint == y.fingerprint and x.metrics == y.metrics


def test_debug_from_environment(world, monkeypatch):
    monkeypatch.setenv("HANDOVERLAB_DEBUG", "1")
    assert Engine(world, A3()).debug
    monkeypatch.setenv("HANDOVERLAB_DEBUG", "0")
    assert not Engine(world, A3()).debug
    assert Engine(world, A3(), debug=True).debug


class WritesObservation(A3):
    def a3_offsets(self, obs):
        obs.gap_db[:] = 0.0                       # forbidden: the observation belongs to the engine
        return self.off_db


class BadShape(A3):
    def a3_offsets(self, obs):
        return np.zeros(3)


class NaNOffsets(hl.ConditionalRule):
    def prep_offsets(self, obs):
        return np.nan

    def exec_offsets(self, obs):
        return 3.0


def test_rule_cannot_write_into_observation(world):
    with pytest.raises(ValueError, match="read-only"):
        hl.run_world(world, [WritesObservation()], debug=True)


@pytest.mark.parametrize("rule, msg", [(BadShape(), "shape"), (NaNOffsets(), "NaN")])
def test_bad_rule_values_are_named(world, rule, msg):
    with pytest.raises(InvariantError, match=msg):
        hl.run_world(world, [rule], debug=True)


def test_final_checks_detect_broken_counts(world):
    eng = Engine(world, A3())
    eng.C["att"] += 1
    with pytest.raises(InvariantError, match="sum of outcomes"):
        check_final(eng)
    eng = Engine(world, A3())
    eng.C["att_all"] += 1
    with pytest.raises(InvariantError, match="attempts started"):
        check_final(eng)
    eng = Engine(world, hl.CHO())
    eng.C["prep_req_all"] += 1
    with pytest.raises(InvariantError, match="preparations requested"):
        check_final(eng)


def test_attempt_to_serving_cell_is_caught(world):
    eng = Engine(world, A3(), debug=True)
    eng.serv = np.zeros(eng.U, dtype=int)
    with pytest.raises(InvariantError, match="attempt towards cell 0"):
        eng.new_flight(0, 0, 1.0)
