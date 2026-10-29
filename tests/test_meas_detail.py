# SPDX-License-Identifier: MIT
"""Measurement detail of the TS 38.133 periods (protocol.meas_detail, since 2.10.0): defaults untouched, the option
changes a ts38133 run with beams, no effect without ts38133, and validation."""
import pytest

import handoverlab as hl
from handoverlab.config import ConfigError, ProtocolConfig

SHORT = {"mobility.users": 6, "run.duration_s": 5.0, "run.warmup_s": 1.0}
RULES = [{"rule": "a3", "name": "A3", "off_db": 3.0, "ttt_s": 0.256}]


def _sc(card="urban-grid-28ghz-beams", **protocol):
    ov = dict(SHORT, **{"protocol." + k: v for k, v in protocol.items()})
    return hl.builtin_scenario(card).with_overrides(ov)


def _fp(sc, seed=5):
    return [r.fingerprint for r in hl.run_world(hl.build_world(sc, seed), RULES)]


def test_default_unchanged():
    assert ProtocolConfig().meas_detail == "2x"
    assert "meas_detail" not in _sc().to_dict()["protocol"]
    sc = _sc(meas_periods="ts38133")
    assert _fp(sc) == _fp(_sc(meas_periods="ts38133", meas_detail="2x"))


def test_option_changes_a_ts38133_run_with_beams():
    sc = _sc(meas_periods="ts38133", meas_detail="3gpp")
    assert sc.to_dict()["protocol"]["meas_detail"] == "3gpp"
    assert _fp(sc) != _fp(_sc(meas_periods="ts38133"))
    assert _fp(sc) == _fp(sc)                                  # reproducible


def test_no_effect_without_ts38133():
    assert _fp(_sc(meas_detail="3gpp")) == _fp(_sc())


def test_validation():
    with pytest.raises(ConfigError):
        _sc(meas_detail="3GPP")
    with pytest.raises(ConfigError):
        _sc(meas_periods="ts38133", meas_detail="ts38133")
