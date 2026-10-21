# SPDX-License-Identifier: MIT
"""Conditional LTM (Rel-19 work, rule "cltm"): the UE executes the L1 cell switch without a command."""
import numpy as np
import pytest

import handoverlab as hl
from handoverlab.rules import CLTM, LTM
from handoverlab.testing import check_rule
from helpers import PROTOCOL_1X, run_synthetic
from test_rules_rc2 import SMALL, first_l1_crossing


def test_cltm_executes_at_the_switch_decision(ramp):
    m, events = run_synthetic(CLTM(o_prep_db=-2.0, o_switch_db=3.0, ttt_switch_s=0.08, exec_s=0.02), ramp)
    (ev,) = events
    k = first_l1_crossing(ramp, 3.0)
    assert ev["kind"] == "cltm" and ev["src"] == 0 and ev["tgt"] == 1 and ev["outcome"] == "useful"
    assert ev["t_attempt"] == pytest.approx(k * 0.01 + 0.08, abs=1e-6)       # decided on L1 samples
    assert ev["t_exec"] == ev["t_attempt"]                                    # no command, no delay
    assert m["n_commands"] == 0 and m["n_preparations"] == 1 and m["n_used_preparations"] == 1
    assert m["interruption_exec_s_pm"] * m["ue_minutes"] == pytest.approx(0.02)


def test_cltm_is_faster_than_ltm(ramp):
    _, ev_ltm = run_synthetic(LTM(o_prep_db=-2.0, o_switch_db=3.0, ttt_switch_s=0.08, cmd_delay_s=0.01), ramp)
    _, ev_c = run_synthetic(CLTM(o_prep_db=-2.0, o_switch_db=3.0, ttt_switch_s=0.08), ramp)
    assert ev_c[0]["t_exec"] == pytest.approx(ev_ltm[0]["t_exec"] - 0.01, abs=1e-6)


def test_cltm_has_no_late_command():
    """The serving link breaks just after the switch condition holds: LTM's command arrives while T310 runs and
    fails; conditional LTM has already executed."""
    S = 1000
    k = np.arange(S)
    r = np.empty((S, 1, 2))
    r[:, 0, 0] = np.where(k < 300, -70.0, -110.0)
    r[:, 0, 1] = np.where(k < 300, -71.0, -75.0)
    m_ltm, _ = run_synthetic(LTM(o_prep_db=-3.0, o_switch_db=3.0, ttt_switch_s=0.0, cmd_delay_s=1.5,
                                 recovery=False), r, bg_load=0.5, overrides=PROTOCOL_1X)     # command lost in T310
    m_c, ev = run_synthetic(CLTM(o_prep_db=-3.0, o_switch_db=3.0, ttt_switch_s=0.0, recovery=False), r,
                            bg_load=0.5)
    assert m_ltm["n_fail_command_lost"] == 1
    assert m_c["n_failures"] == 0 and ev[0]["kind"] == "cltm" and ev[0]["outcome"] == "useful"


def test_cltm_contract_and_registry():
    assert check_rule("cltm", {"o_prep_db": -3.0, "o_switch_db": 1.0, "n_max": 2}, scenario=SMALL).ok
    assert "cltm" in hl.available_rules() and hl.make_rule({"rule": "cltm"}).family == "cltm"
    assert CLTM().params()["o_switch_db"] == 2.0 and "cmd_delay_s" not in CLTM().params()
    with pytest.raises(ValueError):
        CLTM(n_max=9)
    with pytest.raises(ValueError):
        CLTM(exec_s=0.0)
