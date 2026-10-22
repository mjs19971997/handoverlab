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
        self.C = {"cmd": 0, "rrc": 0}
        self.proc = type("_Proc", (), {"kind": "a3"})()

    def msg(self, t, n=1):
        self.C["rrc"] += n


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


def test_defaults_and_keys_checked():
    p = Scenario().protocol
    assert p.cmd_during_t310 == "receive" and p.t304_s == 1.0 and p.rlm_holdoff_s == 0.2     # defaults since 2.0.0
    d = Scenario().to_dict()["protocol"]
    assert "cmd_during_t310" not in d and "t304_s" not in d
    with pytest.raises(ConfigError, match="protocol.cmd_during_t310"):
        Scenario().with_overrides({"protocol.cmd_during_t310": "maybe"})
    with pytest.raises(ConfigError, match="protocol.t304_s"):
        Scenario().with_overrides({"protocol.t304_s": 0.0})


def test_t304_shorter_than_the_execution_is_the_default_model():
    sc = hl.builtin_scenario("smoke").with_overrides(STRESS)
    for detail, rules in (("simple", RULES), ("3gpp", RULES[:2])):
        # since 2.1.0 (3gpp) T304 also bounds the source-link monitoring of DAPS (TS 38.331 5.3.10.1), so a T304
        # shorter than the execution is no longer the model without T304 for DAPS
        s = sc.with_overrides({"protocol.rrc_detail": detail})
        a = hl.simulate(s.with_overrides({"protocol.t304_s": None}), rules, seeds=[3])       # no T304 (1.x default)
        b = hl.simulate(s.with_overrides({"protocol.t304_s": 0.001}), rules, seeds=[3])
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


def test_cho_configuration_during_t310_is_received_like_a_command():
    """2.0.0: a CHO configuration that reaches the UE while T310 runs waits for the link like a handover command
    (TS 38.331 5.3.5.13 sets no condition on T310); with the 1.x model both are lost."""
    from helpers import PROTOCOL_1X, run_synthetic

    from handoverlab.rules.builtin import A3, CHO
    k = np.arange(1000)
    r = np.empty((1000, 1, 2))
    r[:, 0, 0] = np.where(k < 300, -70.0, np.where(k < 450, -110.0, -78.0))   # T310 runs, then the link recovers
    r[:, 0, 1] = np.where(k < 300, -95.0, -75.0)

    def rows(over):
        o = dict(over, **{"protocol.prep_s": 1.0})
        _, ea = run_synthetic(A3(off_db=3.0, ttt_s=0.0), r, bg_load=0.5, overrides=o)
        mc, ec = run_synthetic(CHO(o_prep_db=3.0, ttt_prep_s=0.0, immediate=True, n_max=1, rel_hys_db=1e9), r,
                               bg_load=0.5, overrides=o)
        f = [[(e["t_exec"], e["outcome"]) for e in ev] for ev in (ea, ec)]
        return f, mc
    (a3, cho), m = rows({})
    assert a3 == cho == [(4.5, "useful")] and m["n_failures"] == 0       # received when the link is back above Qout
    (a3, cho), m = rows(dict(PROTOCOL_1X, **{"protocol.cfg_loss_as_failure": True}))
    assert a3 == cho == [(-1.0, "too_late")] and m["n_fail_command_lost"] == 1


def test_daps_interruption_is_not_stretched_by_t304():
    """2.0.0: while T304 keeps a DAPS execution going, the source link carries the data: the interruption stays
    the configured one (verify V1e)."""
    from handoverlab.verify import Report
    from handoverlab.verify.extended import daps_ltm_checks
    rep = Report()
    daps_ltm_checks(rep, duration_s=15.0)
    v1e = [c for c in rep.checks if c.name.startswith("V1e")]
    assert v1e and all(c.status == "PASS" for c in v1e)
