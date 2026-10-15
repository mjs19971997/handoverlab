# SPDX-License-Identifier: MIT
"""Same seed -> identical metrics and event logs; another seed -> different ones."""
import numpy as np
import pytest

import handoverlab as hl
from handoverlab.world import build_world

RULES = [{"rule": "a3", "off_db": 2.0, "ttt_s": 0.08}, {"rule": "cho", "o_prep_db": -3.0, "o_exec_db": 2.0}]


@pytest.fixture(scope="module")
def scenario():
    return hl.Scenario.from_dict({
        "layout": {"blocks": [2, 2], "site_spacing_m": 200.0},
        "radio": {"map_res_m": 2.0},
        "mobility": {"users": 10, "profile": "veh16"},
        "run": {"duration_s": 20.0, "warmup_s": 2.0},
    })


def _run(sc, seed):
    return hl.simulate(sc, RULES, seeds=[seed], log_events=True)


def test_same_seed_identical(scenario):
    a, b = _run(scenario, 7), _run(scenario, 7)
    for ra, rb in zip(a, b):
        assert ra.metrics == rb.metrics
        assert ra.events == rb.events
    assert a[0].metrics["n_handovers"] > 0                # the case is not trivial


def test_other_seed_differs(scenario):
    a, c = _run(scenario, 7), _run(scenario, 8)
    assert any(ra.metrics != rc.metrics for ra, rc in zip(a, c))


def test_rules_share_one_world(scenario):
    """All rules of a run see the same world; the engine draws no random numbers."""
    world = build_world(scenario, 3)
    state = np.random.get_state()
    r1 = hl.run_world(world, RULES)
    r2 = hl.run_world(world, list(reversed(RULES)))
    assert r1[0].metrics == r2[1].metrics and r1[1].metrics == r2[0].metrics   # order does not matter
    assert np.array_equal(np.random.get_state()[1], state[1])                    # global state untouched
