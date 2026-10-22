# SPDX-License-Identifier: MIT
"""Mobility robustness optimisation: the rule a3_mro (since 1.7.0)."""
import numpy as np
import pytest

import handoverlab as hl
from handoverlab.rules import EARLY, LATE, UNNECESSARY, USEFUL, FailureRecord, MROA3, OutcomeRecord, make_rule
from handoverlab.testing import check_rule

SMALL = hl.builtin_scenario("smoke")


class _Ctx:
    n_sites = 3


class _Obs:
    def __init__(self, t, serving=(0, 1)):
        self.t, self.serving = t, np.asarray(serving)


def _rule(**kw):
    r = MROA3(**kw)
    r.reset(_Ctx())
    return r


def _out(label, src=0, tgt=1, t=1.0):
    return OutcomeRecord(0, src, tgt, -1, label, t)


def test_three_late_handovers_lower_the_offset_by_one_step():
    r = _rule()
    for _ in range(3):
        r.on_outcome(_out(LATE))
    off = r.a3_offsets(_Obs(9.99))
    assert np.all(off == 3.0)                         # window not closed yet
    off = r.a3_offsets(_Obs(10.0))
    assert r.cio[0, 1] == -1.0 and off[0, 1] == 2.0 and off[0, 2] == 3.0 and off[1, 0] == 3.0   # step 1 dB
    assert r.late.sum() == 0 and r.next_update == 20.0


def test_early_pingpong_and_failures_move_the_right_pairs():
    r = _rule(step_db=1.0, min_events=1)
    r.on_outcome(_out(EARLY, 1, 2))
    r.on_outcome(_out(UNNECESSARY, 1, 2))
    r.on_outcome(_out(USEFUL, 2, 0))                  # useful outcomes are not counted
    r.on_link_failure(FailureRecord(0, 2, 0, 3.0, 2.0, 0.0, 0.0, 0.0))
    r.a3_offsets(_Obs(10.5))
    assert r.cio[1, 2] == 1.0 and r.cio[2, 0] == -1.0 and r.cio[0, 1] == 0.0


def test_ties_min_events_bounds_and_unnecessary_switch():
    r = _rule(min_events=2, max_db=1.0)
    r.on_outcome(_out(LATE))
    r.on_outcome(_out(EARLY))                         # tie: no move
    r.on_outcome(_out(EARLY, 1, 0))                   # below min_events: no move
    r.a3_offsets(_Obs(10.0))
    assert not r.cio.any()
    for k in range(5):                                # clipped at max_db
        r.on_outcome(_out(EARLY))
        r.on_outcome(_out(EARLY))
        r.a3_offsets(_Obs(20.0 + 10.0 * k))
    assert r.cio[0, 1] == 1.0
    r2 = _rule(count_unnecessary=False, min_events=1)
    r2.on_outcome(_out(UNNECESSARY))
    r2.a3_offsets(_Obs(10.0))
    assert not r2.cio.any()


def test_pingpong_is_seen_in_the_serving_cell_and_counts_as_too_early():
    r = _rule(pingpong_s=1.0)
    r.a3_offsets(_Obs(0.00, (0, 1)))
    r.a3_offsets(_Obs(0.04, (1, 1)))                  # user 0: 0 -> 1
    r.a3_offsets(_Obs(0.80, (0, 1)))                  # back to 0 within 1 s: ping-pong of the pair (0, 1)
    r.a3_offsets(_Obs(1.00, (2, 1)))                  # 0 -> 2: no return
    r.a3_offsets(_Obs(2.50, (0, 1)))                  # back to 0 after 1.5 s: not a ping-pong
    assert r.n_pingpong == 1 and r.early[0, 1] == 1 and r.early.sum() == 1
    r.a3_offsets(_Obs(10.0, (0, 1)))
    assert r.cio[0, 1] == 1.0
    off = _rule(count_pingpong=False)
    for t, s in ((0.0, (0, 1)), (0.04, (1, 1)), (0.8, (0, 1))):
        off.a3_offsets(_Obs(t, s))
    assert off.n_pingpong == 0


def test_construction_and_registry():
    assert isinstance(make_rule({"rule": "a3_mro", "step_db": 1.0}), MROA3)
    with pytest.raises(ValueError):
        MROA3(window_s=0.0)
    with pytest.raises(ValueError):
        MROA3(min_db=1.0)
    with pytest.raises(ValueError):
        MROA3(pingpong_s=0.0)


def test_contract_and_reduction_to_a3():
    assert check_rule("a3_mro", {"window_s": 5.0}, scenario=SMALL).ok
    assert check_rule("a3_mro", {"step_db": 0.0}, reduces_to=("a3", {"off_db": 3.0, "ttt_s": 0.16}, {}),
                      scenario=SMALL).ok


def test_failures_not_above_fixed_a3_on_smoke():
    sc = SMALL.with_overrides({"radio.isolation": 1.0, "mobility.profile": "veh30", "run.duration_s": 60.0})
    a3, mro = hl.simulate(sc, [{"rule": "a3"}, {"rule": "a3_mro", "window_s": 5.0, "step_db": 1.0}], seeds=[2])
    assert mro.metrics["failures_pm"] <= a3.metrics["failures_pm"] * 1.25 + 0.1
    assert mro.metrics["unnecessary_pm"] <= a3.metrics["unnecessary_pm"] + 0.1
