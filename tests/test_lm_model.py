# SPDX-License-Identifier: MIT
"""The optional link-monitoring model of 1.1.0 (protocol.lm_load*, protocol.exec_can_fail)."""
import pytest

import handoverlab as hl
from handoverlab.config import ConfigError

RULES = [{"rule": "a3", "name": "A3", "off_db": 1.0, "ttt_s": 0.0}]
BASE = {"radio.isolation": 1.0, "mobility.profile": "veh30", "mobility.users": 20, "run.duration_s": 30.0,
        "run.warmup_s": 2.0}


def _run(**over):
    sc = hl.builtin_scenario("smoke").with_overrides(dict(BASE, **{"protocol." + k: v for k, v in over.items()}))
    return hl.run_world(hl.build_world(sc, 3), RULES)[0].metrics


def test_execution_that_cannot_fail():
    assert _run()["n_fail_execution_failure"] > 0
    m = _run(exec_can_fail=False)
    assert m["n_fail_execution_failure"] == 0


def test_link_monitoring_load_drives_failures():
    lo = _run(lm_load=0.0)
    hi = _run(lm_load=1.0)
    per_ue = _run(lm_load=0.0, lm_load_per_ue=1.0)          # every serving cell at full load
    assert hi["failures_pm"] > lo["failures_pm"]
    assert per_ue["failures_pm"] == pytest.approx(hi["failures_pm"], rel=0.5)
    assert hi["sinr_db"] == pytest.approx(lo["sinr_db"], abs=0.2)   # the data channel is not touched


def test_defaults_unchanged():
    assert _run(lm_load=None, lm_load_per_ue=0.0, exec_can_fail=True) == _run()


@pytest.mark.parametrize("key,val", [("lm_load", -0.1), ("lm_load_per_ue", -1.0)])
def test_validation(key, val):
    with pytest.raises(ConfigError, match=key):
        hl.builtin_scenario("smoke").with_overrides({"protocol." + key: val}).validate()


def test_penetration_loss_per_user():
    from handoverlab.channel.source import RadioSource
    from handoverlab.verify.ns3 import car_loss
    sc = hl.builtin_scenario("smoke").with_overrides({"mobility.users": 6, "run.duration_s": 2.0, "run.warmup_s": 0.0})
    base = next(RadioSource(hl.build_world(sc, 4)).chunks()).rsrp
    pen = sc.with_overrides({"radio.penetration_db": 9.0, "radio.penetration_sd_db": 5.0})
    loss = base - next(RadioSource(hl.build_world(pen, 4)).chunks()).rsrp
    per_user = loss[0, :, 0]
    assert abs(loss - per_user[None, :, None]).max() < 1e-9     # one loss per user, on every link and step
    assert per_user.std() > 0.5 and 0.0 < per_user.mean() < 20.0
    flat = sc.with_overrides({"radio.penetration_db": 9.0})
    assert base - next(RadioSource(hl.build_world(flat, 4)).chunks()).rsrp == pytest.approx(9.0)
    assert car_loss(16) and car_loss(30) and not car_loss(8) and not car_loss(36)      # 30-120 km/h, as in ns-3
    with pytest.raises(ConfigError, match="penetration_sd_db"):
        sc.with_overrides({"radio.penetration_sd_db": -1.0}).validate()
