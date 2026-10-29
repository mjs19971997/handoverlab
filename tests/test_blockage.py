# SPDX-License-Identifier: MIT
"""Blockage model A of TR 38.901 clause 7.6.4.1 (radio.blockage "a", since 2.10.0): defaults untouched, the
knife-edge terms, the self-blocking region, and validation."""
import math

import numpy as np
import pytest

import handoverlab as hl
from handoverlab.channel.blockage import SELF_REGION, BlockageA, _edge_terms
from handoverlab.config import ConfigError, RadioConfig

SHORT = {"mobility.users": 6, "run.duration_s": 5.0, "run.warmup_s": 1.0}
RULES = [{"rule": "a3", "name": "A3", "off_db": 3.0, "ttt_s": 0.256}]


def _sc(card="urban-grid-28ghz-beams", **radio):
    ov = dict(SHORT, **{"radio." + k: v for k, v in radio.items()})
    return hl.builtin_scenario(card).with_overrides(ov)


def _fp(sc, seed=5):
    return [r.fingerprint for r in hl.run_world(hl.build_world(sc, seed), RULES)]


def test_default_unchanged():
    assert RadioConfig().blockage is None
    assert "blockage" not in _sc().to_dict()["radio"]
    assert _fp(_sc()) == _fp(_sc(blockage=None))


def test_option_changes_the_run():
    sc = _sc(blockage="a")
    assert _fp(sc) != _fp(_sc()) and _fp(sc) == _fp(sc)


def test_edge_terms_inside_and_outside():
    kr = math.pi * 10.0 / (299792458.0 / 28e9)
    # centre of a 10 deg wide blocker: both terms positive, sum below 1
    c = float(_edge_terms(np.array(0.0), 5.0, 10.0, kr))
    assert 0.5 < c < 1.0
    # Eq. 7.6-23 at the centre by hand
    f = math.atan(0.5 * math.pi * math.sqrt(kr * (1 / math.cos(math.radians(5.0)) - 1))) / math.pi
    assert c == pytest.approx(2 * f)
    # outside the attenuation zone |d| >= x_k: no term; just outside the region: small (diffraction)
    assert float(_edge_terms(np.array(10.5), 5.0, 10.0, kr)) == 0.0
    edge = float(_edge_terms(np.array(7.0), 5.0, 10.0, kr))
    assert 0.0 < edge < 0.2 * c


def _one(mode="portrait", los=1.0, heading_deg=0.0, site=(100.0, 0.0)):
    r = RadioConfig(pathloss="umi_street_canyon", carrier_ghz=28.0, bs_height_m=10.0, ue_height_m=1.5,
                    blockage="a", blockage_mode=mode)
    b = BlockageA(np.random.default_rng(0), 1, r, np.array([1.0]), 0.01)
    b.g[:] = -8.0                       # park the non-self blockers at phi ~ 0 deg with the narrowest width
    x, y = np.zeros((1, 1)), np.zeros((1, 1))
    h = np.full((1, 1), math.radians(heading_deg))
    return float(b.factor_db(x, y, h, np.array([site]), np.full((1, 1, 1), los), 1)[0, 0, 0])


def test_self_blocking_region():
    p_sb = SELF_REGION["portrait"][0]
    # LOS site straight ahead (phi' = 0, outside the portrait region 200-320 deg): little loss
    ahead = _one(site=(0.0, 100.0), heading_deg=90.0)
    # LOS site in the centre of the region (phi' = 260 deg): the LOS ray loses 30 dB
    behind = _one(site=(100.0 * math.cos(math.radians(p_sb + 90.0)), 100.0 * math.sin(math.radians(p_sb + 90.0))),
                  heading_deg=90.0)
    assert -3.0 < ahead <= 0.0
    assert behind < -6.0
    assert behind < ahead


def test_validation():
    with pytest.raises(ConfigError):
        _sc(blockage="b")
    with pytest.raises(ConfigError):
        _sc(blockage="a", blockage_mode="sideways")
    with pytest.raises(ConfigError):
        _sc("rural-700mhz", blockage="a")
