# SPDX-License-Identifier: MIT
"""Handover command and execution as TS 38.331 specifies them (options of 1.9.0)."""
import numpy as np
import pytest

import handoverlab as hl
from handoverlab.config import ConfigError, Scenario
from handoverlab.engine.procedures import receive_during_t310

PROFILE = {"protocol.cmd_during_t310": "receive", "protocol.t304_s": 1.0, "protocol.rlm_holdoff_s": 0.2}
STRESS = {"radio.isolation": 1.0, "mobility.profile": "veh30", "run.duration_s": 40.0}
RULES = [{"rule": "a3", "name": "A3-late", "off_db": 6.0, "ttt_s": 0.32}, {"rule": "ltm"}, {"rule": "daps"}]


class _P:
    cmd_during_t310 = "receive"


class _Eng:
    def __init__(self, sl, run=True):
        self.P, self.qout, self.t0c = _P(), 1.0, 0.0
        self.run = np.array([run])
        self.sl_now = np.array([sl])
        self.C = {"cmd": 0}


def test_receive_waits_below_qout_and_stops_t310_at_qout():
    wait = np.zeros(1, dtype=bool)
    eng = _Eng(sl=0.5)
    assert receive_during_t310(eng, 0, wait, 1.0) is True          # below Qout: the command waits
    assert wait[0] and eng.C["cmd"] == 1 and eng.run[0]
    assert receive_during_t310(eng, 0, wait, 1.01) is True
    assert eng.C["cmd"] == 1                                         # counted once
    eng.sl_now[0] = 1.2
    assert receive_during_t310(eng, 0, wait, 1.02) is False          # received: T310 stops (TS 38.331 5.3.5.5.2)
    assert not eng.run[0]


def test_receive_does_nothing_without_t310_or_with_the_default():
    wait = np.zeros(1, dtype=bool)
    assert receive_during_t310(_Eng(sl=0.1, run=False), 0, wait, 1.0) is False
    eng = _Eng(sl=0.1)
    eng.P.cmd_during_t310 = "lost"
    assert receive_during_t310(eng, 0, wait, 1.0) is False and not wait[0]
    _P.cmd_during_t310 = "receive"


def test_defaults_unchanged_and_keys_checked():
    p = Scenario().protocol
    assert p.cmd_during_t310 == "lost" and p.t304_s is None
    d = Scenario().to_dict()["protocol"]
    assert "cmd_during_t310" not in d and "t304_s" not in d
    with pytest.raises(ConfigError, match="protocol.cmd_during_t310"):
        Scenario().with_overrides({"protocol.cmd_during_t310": "maybe"})
    with pytest.raises(ConfigError, match="protocol.t304_s"):
        Scenario().with_overrides({"protocol.t304_s": 0.0})


def test_t304_shorter_than_the_execution_is_the_default_model():
    sc = hl.builtin_scenario("smoke").with_overrides(STRESS)
    a = hl.simulate(sc, RULES, seeds=[3])
    b = hl.simulate(sc.with_overrides({"protocol.t304_s": 0.001}), RULES, seeds=[3])
    assert [r.fingerprint for r in a] == [r.fingerprint for r in b]


def test_profile_runs_with_invariants_and_has_no_lost_commands():
    sc = hl.builtin_scenario("smoke").with_overrides(dict(STRESS, **PROFILE))
    res = hl.simulate(sc, RULES + [{"rule": "cho"}, {"rule": "cltm"}], seeds=[3], debug=True)
    again = hl.simulate(sc, RULES + [{"rule": "cho"}, {"rule": "cltm"}], seeds=[3])
    assert [r.fingerprint for r in res] == [r.fingerprint for r in again]
    for r in res:
        assert r.metrics["fail_command_lost_pm"] == 0.0
    base = hl.simulate(hl.builtin_scenario("smoke").with_overrides(STRESS), RULES[:1], seeds=[3])[0]
    assert res[0].metrics["failures_pm"] <= base.metrics["failures_pm"]
