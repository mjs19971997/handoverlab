# SPDX-License-Identifier: MIT
"""Engines batched in one step loop give the results of engines run one by one, bit for bit."""
import numpy as np
import pytest

import handoverlab as hl
from handoverlab.engine import Engine
from handoverlab.engine.batch import EngineBatch

RULES = [
    {"rule": "a3", "name": "A3", "off_db": 3.0, "ttt_s": 0.16},
    {"rule": "a3", "name": "A3-0", "off_db": 1.0, "ttt_s": 0.0},
    {"rule": "cho", "name": "CHO", "o_prep_db": -2.0, "o_exec_db": 3.0, "ttt_exec_s": 0.08, "n_max": 4},
    {"rule": "cho", "name": "CHO-imm", "immediate": True, "n_max": 1},
]
CASES = {
    "stress": {"radio.isolation": 1.0, "mobility.profile": "veh30"},
    "n310": {"radio.isolation": 1.0, "protocol.n310": 2, "protocol.n311": 2, "protocol.t310_s": 0.5},
    "open": {"layout.kind": "open_area", "radio.place_share": 0.5, "mobility.profile": "mix"},
}


@pytest.mark.parametrize("case", sorted(CASES))
def test_batched_equals_one_by_one(case):
    over = dict(CASES[case], **{"mobility.users": 10, "run.duration_s": 15.0, "run.warmup_s": 2.0})
    world = hl.build_world(hl.builtin_scenario("smoke").with_overrides(over), 4)
    a = hl.run_world(world, RULES, log_events=True, batch=False)
    b = hl.run_world(world, RULES, log_events=True, batch=True)
    assert sum(r.n_events for r in a) > 20
    for x, y in zip(a, b):
        assert x.fingerprint == y.fingerprint and x.events == y.events, (case, x.rule)
        assert x.metrics == y.metrics, (case, x.rule)        # every float to the last bit


def test_batch_rules():
    world = hl.build_world(hl.builtin_scenario("smoke").with_overrides({"mobility.users": 4, "run.duration_s": 2.0,
                                                                        "run.warmup_s": 0.0}), 1)
    engines = [Engine(world, hl.A3()), Engine(world, hl.CHO())]
    assert EngineBatch.supported(engines)
    assert not EngineBatch.supported(engines[:1])
    assert not EngineBatch.supported([Engine(world, hl.A3(), debug=True), Engine(world, hl.CHO())])
    with pytest.raises(ValueError, match="debug"):
        EngineBatch([Engine(world, hl.A3(), debug=True), Engine(world, hl.CHO())])
    batch = EngineBatch(engines)
    assert np.shares_memory(engines[1].qo, batch.qo) and engines[1].qo.shape == (4,)
