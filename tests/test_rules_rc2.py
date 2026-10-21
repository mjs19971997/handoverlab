# SPDX-License-Identifier: MIT
"""DAPS handover, L1/L2-triggered mobility and the bandit A3 rule (added in 1.0.0rc2).

Trigger logic on prescribed received powers (one user, two cells, no
measurement noise; see ``test_engine_triggers.py``) and the rule contract.
"""
import numpy as np
import pytest

import handoverlab as hl
from handoverlab.rules import A3, CHO, DAPS, EARLY, LATE, LTM, UNNECESSARY, USEFUL, BanditA3, RuleContext
from handoverlab.testing import check_rule
from helpers import PROTOCOL_1X, run_synthetic
from test_engine_triggers import first_filtered_crossing

PREP, EXEC = 0.05, 0.04
SMALL = hl.builtin_scenario("smoke").with_overrides({"mobility.users": 8, "run.duration_s": 15.0,
                                                     "run.warmup_s": 2.0})


# ---------------------------------------------------------------------------- DAPS
def test_daps_triggers_like_a3_without_interruption(ramp):
    m_a3, ev_a3 = run_synthetic(A3(off_db=3.0, ttt_s=0.16), ramp)
    m_d, ev_d = run_synthetic(DAPS(off_db=3.0, ttt_s=0.16), ramp)
    (a,), (d,) = ev_a3, ev_d
    assert d["kind"] == "daps" and d["outcome"] == "useful"
    assert (d["t_attempt"], d["t_exec"], d["t_end"]) == (a["t_attempt"], a["t_exec"], a["t_end"])
    assert m_a3["interruption_exec_s_pm"] * m_a3["ue_minutes"] == pytest.approx(EXEC)
    assert m_d["interruption_exec_s_pm"] == 0.0
    assert m_d["outage_pct"] < m_a3["outage_pct"]


def test_daps_interruption_is_a_parameter(ramp):
    m, _ = run_synthetic(DAPS(off_db=3.0, ttt_s=0.16, interruption_s=0.01), ramp)
    assert m["interruption_exec_s_pm"] * m["ue_minutes"] == pytest.approx(0.01)


def _target_vanishes(ramp, off_db=3.0):
    """Ramp whose cell 1 collapses right after the execution of an A3 handover (ttt 0) has started."""
    k = first_filtered_crossing(ramp, off_db)
    k_exec = k + int(round(PREP / 0.01))
    r = ramp.copy()
    r[k_exec + 1:, 0, 1] = -130.0
    return r, k_exec


def test_daps_falls_back_to_the_source(ramp):
    r, k_exec = _target_vanishes(ramp)
    m_a3, ev_a3 = run_synthetic(A3(off_db=3.0, ttt_s=0.0), r, overrides=PROTOCOL_1X)
    m_d, ev_d = run_synthetic(DAPS(off_db=3.0, ttt_s=0.0), r, overrides=PROTOCOL_1X)   # without T304 (1.x)
    # baseline: execution failure, re-establishment in the source (too early)
    assert ev_a3[0]["outcome"] == "too_early" and ev_a3[0]["cause"] == "execution_failure"
    assert m_a3["n_failures"] == 1 and m_a3["interruption_fail_s_pm"] > 0
    # DAPS (TS 38.331 clause 5.3.5.8.3): back in the source, no failure and no re-establishment
    (d,) = ev_d
    assert d["outcome"] == "too_early" and d["cause"] == "daps_fallback" and d["src"] == 0 and d["tgt"] == 1
    assert d["t_exec"] == pytest.approx(k_exec * 0.01, abs=1e-6)
    assert d["t_end"] == pytest.approx(k_exec * 0.01 + EXEC, abs=1e-6)
    assert m_d["n_failures"] == 0 and m_d["n_too_early"] == 1 and m_d["n_handovers"] == 0
    assert m_d["interruption_s_pm"] == 0.0
    # with T304 (default since 2.0.0) the fallback comes when T304 expires (TS 38.331 5.3.5.8.3)
    m_t, (t,) = run_synthetic(DAPS(off_db=3.0, ttt_s=0.0), r)
    assert t["cause"] == "daps_fallback" and t["t_end"] == pytest.approx(k_exec * 0.01 + 1.0, abs=1e-6)
    assert m_t["n_failures"] == 0


def test_daps_without_fallback_fails_like_a3(ramp):
    r, _ = _target_vanishes(ramp)
    m_a3, ev_a3 = run_synthetic(A3(off_db=3.0, ttt_s=0.0), r)
    m_d, ev_d = run_synthetic(DAPS(off_db=3.0, ttt_s=0.0, fallback=False, source_data=False), r)
    assert [e["cause"] for e in ev_d] == [e["cause"] for e in ev_a3] == ["execution_failure"]
    assert {k: v for k, v in m_d.items()} == m_a3


def test_daps_fallback_needs_a_working_source(ramp):
    r, k_exec = _target_vanishes(ramp)
    r[k_exec + 1:, 0, 0] = -130.0                   # the source is lost as well
    m, ev = run_synthetic(DAPS(off_db=3.0, ttt_s=0.0), r, overrides={"protocol.reest_s": 0.5})
    assert ev[0]["cause"] == "execution_failure" and m["n_failures"] >= 1


def test_daps_validation():
    with pytest.raises(ValueError):
        DAPS(interruption_s=-0.01)


# ---------------------------------------------------------------------------- LTM
def first_l1_crossing(rsrp, threshold):
    """First measurement instant at which the unfiltered gap (cell 1 - cell 0) exceeds ``threshold``."""
    for k in range(0, rsrp.shape[0], 4):
        if rsrp[k, 0, 1] - rsrp[k, 0, 0] > threshold:
            return k
    raise AssertionError("no crossing")


def test_ltm_switches_on_l1_after_the_switch_ttt(ramp):
    rule = LTM(o_prep_db=-2.0, o_switch_db=3.0, ttt_switch_s=0.08, cmd_delay_s=0.01, exec_s=0.02)
    m, events = run_synthetic(rule, ramp)
    k = first_l1_crossing(ramp, 3.0)
    (ev,) = events
    assert ev["kind"] == "ltm" and ev["src"] == 0 and ev["tgt"] == 1 and ev["outcome"] == "useful"
    assert ev["n_prepared"] == 1 and ev["o_exec"] == pytest.approx(3.0)
    assert ev["t_attempt"] == pytest.approx(k * 0.01 + 0.08, abs=1e-6)        # decision on L1 reports
    assert ev["t_exec"] == pytest.approx(k * 0.01 + 0.08 + 0.01, abs=1e-6)    # + MAC CE delay
    assert m["n_preparations"] == 1 and m["n_used_preparations"] == 1
    assert m["interruption_exec_s_pm"] * m["ue_minutes"] == pytest.approx(0.02)


def test_ltm_switch_ttt_zero_acts_on_one_report(ramp):
    _, events = run_synthetic(LTM(o_prep_db=-2.0, o_switch_db=3.0, ttt_switch_s=0.0, cmd_delay_s=0.0), ramp)
    # decided at the crossing; a command without delay reaches the UE at the next step
    assert events[0]["t_attempt"] == pytest.approx(first_l1_crossing(ramp, 3.0) * 0.01, abs=1e-6)
    assert events[0]["t_exec"] == pytest.approx(first_l1_crossing(ramp, 3.0) * 0.01 + 0.01, abs=1e-6)


def test_ltm_switches_only_to_a_configured_candidate(ramp):
    m, events = run_synthetic(LTM(o_prep_db=40.0, o_switch_db=3.0), ramp)
    assert m["n_attempts"] == 0 and m["n_preparations"] == 0 and events == []


def test_ltm_is_faster_than_cho_with_the_same_offset(ramp):
    _, ev_cho = run_synthetic(CHO(o_prep_db=-2.0, o_exec_db=3.0, ttt_exec_s=0.08), ramp)
    _, ev_ltm = run_synthetic(LTM(o_prep_db=-2.0, o_switch_db=3.0, ttt_switch_s=0.08, cmd_delay_s=0.01), ramp)
    assert ev_ltm[0]["t_exec"] < ev_cho[0]["t_exec"]          # no L3 filter delay on the switch decision


def test_ltm_switch_command_lost_while_t310_runs():
    """The serving link breaks just after the switch decision; the command arrives while T310 runs."""
    S = 1000
    k = np.arange(S)
    r = np.empty((S, 1, 2))
    r[:, 0, 0] = np.where(k < 300, -70.0, -110.0)
    r[:, 0, 1] = np.where(k < 300, -71.0, -75.0)
    m, ev = run_synthetic(LTM(o_prep_db=-3.0, o_switch_db=3.0, ttt_switch_s=0.0, cmd_delay_s=1.5, recovery=False),
                          r, bg_load=0.5, overrides=PROTOCOL_1X)                       # the 1.x model
    assert ev[0]["kind"] == "ltm" and ev[0]["outcome"] == "too_late" and ev[0]["cause"] == "command_lost"
    assert m["n_fail_command_lost"] == 1 and m["n_recoveries"] == 0
    m2, _ = run_synthetic(LTM(o_prep_db=-3.0, o_switch_db=3.0, ttt_switch_s=0.0, cmd_delay_s=1.5, recovery=False),
                          r, bg_load=0.5)
    assert m2["n_fail_command_lost"] == 0                     # 2.0.0: received during T310 (TS 38.331 5.3.5.5.2)


def test_ltm_validation():
    with pytest.raises(ValueError):
        LTM(n_max=9)
    with pytest.raises(ValueError):
        LTM(exec_s=0.0)


# ---------------------------------------------------------------------------- bandit
def _bandit(**kw):
    rule = BanditA3(**kw)
    rule.reset(RuleContext(1, 2, np.zeros((2, 2)), None, 0.01, 0.04, 1, np.random.default_rng(0), None))
    return rule


class _Rec:
    def __init__(self, source, label):
        self.source, self.label = source, label


def test_bandit_plays_every_arm_then_the_best():
    rule = _bandit(arms_db=[1.0, 3.0, 5.0], epsilon=0.0, epoch=2)
    for label in (USEFUL, USEFUL, EARLY, LATE, UNNECESSARY, USEFUL):     # arms 0, 1, 2 of cell 0
        rule.on_outcome(_Rec(0, label))
    assert rule.value[0].tolist() == [1.0, -2.0, 0.0]
    assert rule.arm[0] == 0 and rule.arm[1] == 0                        # best arm; cell 1 untouched
    rule.on_link_failure(_Rec(0, None))
    rule.on_link_failure(_Rec(0, None))
    assert rule.value[0, 0] == pytest.approx((1.0 - 2.0) / 2) and rule.arm[0] == 2


def test_bandit_offsets_follow_the_serving_cell():
    rule = _bandit(arms_db=[1.0, 4.0], epsilon=0.0, epoch=1)
    rule.on_outcome(_Rec(1, USEFUL))                                     # cell 1 moves on to arm 1
    obs = type("O", (), {"serving": np.array([0, 1, 1])})()
    off = rule.a3_offsets(obs)
    assert off.shape == (3, 2) and off[:, 0].tolist() == [1.0, 4.0, 4.0]
    assert rule.reward(UNNECESSARY) == -1.0 and rule.reward(LATE) == -2.0


def test_bandit_validation():
    with pytest.raises(ValueError):
        BanditA3(arms_db=[])
    with pytest.raises(ValueError):
        BanditA3(epsilon=1.5)


# ---------------------------------------------------------------------------- contract
@pytest.mark.parametrize("key, params", [("daps", {"off_db": 2.0, "ttt_s": 0.08}),
                                         ("ltm", {"o_prep_db": -3.0, "o_switch_db": 1.0, "n_max": 2}),
                                         ("a3_bandit", {"arms_db": [1.0, 3.0], "epoch": 3, "epsilon": 0.2})])
def test_new_rules_keep_the_contract(key, params):
    assert check_rule(key, params, scenario=SMALL).ok


def test_reductions_to_a3():
    assert check_rule("daps", {"off_db": 3.0, "ttt_s": 0.16, "fallback": False, "source_data": False},
                      reduces_to=("a3", {"off_db": 3.0, "ttt_s": 0.16}, {}), scenario=SMALL).ok
    assert check_rule("a3_bandit", {"arms_db": [3.0], "ttt_s": 0.16},
                      reduces_to=("a3", {"off_db": 3.0, "ttt_s": 0.16}, {}), scenario=SMALL).ok


def test_registry_and_observation():
    assert {"daps", "ltm", "a3_bandit"} <= set(hl.available_rules())
    assert hl.make_rule({"rule": "ltm", "n_max": 2}).family == "ltm"
    assert hl.make_rule({"rule": "daps"}).family == "daps"
    rec = []

    class Probe(hl.LTMRule):
        def prep_offsets(self, obs):
            rec.append(obs.l1_dbm is not None and obs.l1_dbm.shape == obs.meas_dbm.shape)
            return 0.0

        def switch_offsets(self, obs):
            return 3.0

    hl.simulate(SMALL, [Probe()], seeds=[1])
    assert rec and all(rec)
