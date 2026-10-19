# SPDX-License-Identifier: MIT
"""Signalling and energy metrics of 1.5.0: counted by hand from the other counters."""
import math

import pytest

import handoverlab as hl

SC = {"mobility.users": 8, "radio.isolation": 1.0, "mobility.profile": "veh30", "run.duration_s": 25.0,
      "run.warmup_s": 3.0}
RULES = [{"rule": "a3", "name": "A3", "off_db": 1.0, "ttt_s": 0.0}, {"rule": "cho", "name": "CHO"},
         {"rule": "ltm", "name": "LTM"}]


@pytest.fixture(scope="module")
def runs():
    sc = hl.builtin_scenario("smoke").with_overrides(SC)
    return {r.rule: r.metrics for r in hl.simulate(sc, RULES, seeds=[2])}, sc


def test_commands_and_rrc_messages(runs):
    m, _ = runs
    a3, cho, ltm = m["A3"], m["CHO"], m["LTM"]
    # every baseline command either starts an execution or arrives while T310 runs
    assert a3["n_commands"] == a3["n_executions"] + a3["n_fail_command_lost"] > 0
    assert cho["n_commands"] == 0 and ltm["n_commands"] > 0
    for x in (a3, cho, ltm):
        n = x["n_reports"] + x["n_commands"] + x["n_configurations"] + x["n_lost_configurations"] + x["n_releases"] \
            + x["n_handovers"]
        assert x["rrc_messages_pm"] == pytest.approx(n / x["ue_minutes"])
        assert x["commands_pm"] == pytest.approx(x["n_commands"] / x["ue_minutes"])
    assert cho["rrc_messages_pm"] > a3["rrc_messages_pm"]          # conditional handover costs signalling


def test_l1_measurements_and_energy(runs):
    m, sc = runs
    x = m["A3"]
    world = hl.build_world(sc, 2)
    per_min = 60.0 / sc.protocol.l1_period_s * world.layout.n_sites      # every cell in every L1 period
    assert 0.8 * per_min < x["l1_measurements_pm"] <= per_min * 1.0001  # connected most of the time
    p_tx = 10 ** (sc.radio.tx_power_dbm / 10) / 1000
    assert x["site_power_w"] == pytest.approx(56.0 + 2.6 * p_tx * x["mean_load"])
    bits = x["rate_mbps"] * 1e6 * sc.mobility.users
    assert x["energy_uj_per_bit"] == pytest.approx(1e6 * world.layout.n_sites * x["site_power_w"] / bits, rel=1e-9)
    sc0 = sc.with_overrides({"radio.energy_p0_w": 0.0, "radio.energy_slope": 0.0})
    (r0,) = hl.simulate(sc0, RULES[:1], seeds=[2])
    assert r0.metrics["site_power_w"] == 0.0 and r0.metrics["energy_uj_per_bit"] == 0.0
    assert not math.isnan(x["energy_uj_per_bit"])
