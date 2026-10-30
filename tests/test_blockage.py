# SPDX-License-Identifier: MIT
"""Blockage model A of TR 38.901 clause 7.6.4.1 (radio.blockage "a", since 2.10.0): defaults untouched, the
knife-edge terms, the self-blocking region, and validation; since 2.10.1 the same values as the 2.10.0 function."""
import copy
import json
import math

import numpy as np
import pytest
from scipy.special import ndtr

import handoverlab as hl
from handoverlab.channel import blockage
from handoverlab.channel.blockage import (SELF_LOSS_DB, SELF_REGION, THETA_K, X_RANGE, Y_K, BlockageA, _edge_terms,
                                          _wrap)
from handoverlab.channel.spread import U_AZ, U_ZE
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


# ---- since 2.10.1: blocks of links and per-state evaluation give the same values as the 2.10.0 function ----

def _factor_db_210(self, x, y, heading, sites, los_w, n, mult=1, layout=None):
    """BlockageA.factor_db of 2.10.0 (whole chunk, both LOS states for every link), kept as the reference."""
    g = self._advance(n, mult)
    u = ndtr(g)
    phi_k = 360.0 * u[:, 0]
    x_k = X_RANGE[0] + (X_RANGE[1] - X_RANGE[0]) * u[:, 1]
    dx = x[..., None] - sites[None, None, :, 0]
    dy = y[..., None] - sites[None, None, :, 1]
    if layout is not None and layout.period_x:
        dx, dy = layout.nearest_image(dx, dy)
    dx, dy = -dx, -dy
    d2 = np.maximum(np.hypot(dx, dy), 1.0)
    az = np.degrees(np.arctan2(dy, dx))
    ze = 90.0 - np.degrees(np.arctan2(self.h_bs - self.h_ut, d2))
    hd = np.degrees(heading)[..., None]
    p_sb, x_sb, t_sb, y_sb = SELF_REGION[self.mode]
    keep = 1.0 - 10.0 ** (-SELF_LOSS_DB / 10.0)

    def terms(a_az, a_ze):
        i_a = np.abs(_wrap(a_az - hd[..., None] - p_sb)) < 0.5 * x_sb
        i_z = np.abs(a_ze - t_sb) < 0.5 * y_sb
        da = _wrap(a_az[..., None] - phi_k[:, :, None, None, :])
        fa = _edge_terms(da, 0.5 * x_k[:, :, None, None, :], x_k[:, :, None, None, :], self.kr)
        fz = _edge_terms(a_ze - THETA_K, 0.5 * Y_K, Y_K, self.kr)
        return i_a, i_z, fa, fz

    i_a, i_z, fa, fz = terms(az[..., None], ze[..., None])
    f_los = (1.0 - keep * (i_a & i_z)[..., 0]) * np.prod((1.0 - fa[..., 0, :] * fz[..., 0, None]) ** 2, -1)
    out = np.zeros(az.shape)
    for state in (True, False):
        asa, zsa = self.spreads[state]
        a_n = az[..., None] + asa * U_AZ
        z_n = np.clip(ze[..., None] + zsa * U_ZE, 0.0, 180.0)
        ia, _, fa_n, _ = terms(a_n, ze[..., None])
        _, iz, _, fz_n = terms(az[..., None], z_n)
        pa, pz = ia.mean(-1), iz.mean(-1)
        ea, ea2 = fa_n.mean(-2), (fa_n ** 2).mean(-2)
        eza, eza2 = (ia[..., None] * fa_n).mean(-2), (ia[..., None] * fa_n ** 2).mean(-2)
        ez, ez2 = fz_n.mean(-1), (fz_n ** 2).mean(-1)
        ezz, ezz2 = (iz * fz_n).mean(-1), (iz * fz_n ** 2).mean(-1)
        e_s = 1.0 - keep * pa * pz
        e_nk = 2.0 * ea * ez[..., None] - ea2 * ez2[..., None]
        e_snk = e_nk - keep * (2.0 * eza * ezz[..., None] - eza2 * ezz2[..., None])
        f_dif = np.maximum(e_s - e_snk.sum(-1), 10.0 ** (-SELF_LOSS_DB / 10.0) * 1e-3)
        if state:
            f = self.p_los * f_los + (1.0 - self.p_los) * f_dif
            wl = np.zeros(az.shape) if los_w is None else los_w
            out += wl * f
        else:
            wl = np.ones(az.shape) if los_w is None else 1.0 - los_w
            out += wl * f_dif
    return 10.0 * np.log10(np.maximum(out, 1e-12))


def _weights(kind, rng, shape):
    if kind == "none":
        return None
    if kind == "binary":
        return (rng.random(shape) < 0.3).astype(float)
    if kind == "per_site":                           # broadcast over instants and users
        return (rng.random(shape[-1]) < 0.5).astype(float)
    if kind == "fraction":                           # exact 0 and 1 mixed with values in between
        return np.choose(rng.integers(0, 3, shape), [np.zeros(shape), np.ones(shape), rng.random(shape)])
    return np.full(shape, 1.0 if kind == "ones" else 0.0)


@pytest.mark.parametrize("block", [None, 1, 7])
@pytest.mark.parametrize("kind", ["none", "binary", "fraction", "ones", "zeros", "per_site"])
@pytest.mark.parametrize("mode,pathloss,fc", [("portrait", "umi_street_canyon", 28.0), ("landscape", "uma", 3.5)])
def test_factor_db_equals_the_210_function(monkeypatch, block, kind, mode, pathloss, fc):
    if block is not None:
        monkeypatch.setattr(blockage, "BLOCK_LINKS", block)
    rng = np.random.default_rng(11)
    r = RadioConfig(pathloss=pathloss, carrier_ghz=fc, bs_height_m=10.0, ue_height_m=1.5, blockage="a",
                    blockage_mode=mode)
    for n, U, M, mult in ((1, 1, 1, 1), (3, 5, 7, 4), (6, 4, 9, 2)):
        b = BlockageA(np.random.default_rng(3), U, r, rng.uniform(0.5, 15.0, U), 0.01,
                      indoor=rng.random(U) < 0.3)
        x, y = rng.uniform(-300.0, 300.0, (n, U)), rng.uniform(-300.0, 300.0, (n, U))
        h = rng.uniform(-math.pi, math.pi, (n, U))
        sites = rng.uniform(-400.0, 400.0, (M, 2))
        w = _weights(kind, rng, (n, U, M))
        ref_b, new_b = copy.deepcopy(b), copy.deepcopy(b)
        ref = _factor_db_210(ref_b, x, y, h, sites, w, n, mult)
        new = new_b.factor_db(x, y, h, sites, w, n, mult)
        assert np.array_equal(new, ref)
        assert np.array_equal(new_b.g, ref_b.g)          # the blocker processes advance alike
        assert new_b.rng.bit_generator.state == ref_b.rng.bit_generator.state


@pytest.mark.parametrize("card,radio", [
    ("urban-grid-28ghz-beams", {"blockage": "a"}),
    ("urban-grid-28ghz-beams", {"blockage": "a", "blockage_mode": "landscape"}),
    ("urban-grid-28ghz-beams", {"blockage": "a", "beams": {"sectors": 3, "sector_az0_deg": 30.0, "n_ssb": 8,
                                                          "panel": [4, 8], "tilt_deg": 100.0,
                                                          "angular_spread": "tr38901"}}),
    ("urban-macro-tr37885-4ghz", {"blockage": "a"}),
    ("highway-tr37885-30ghz", {"blockage": "a"}),          # wrap-around, every link LOS
])
def test_runs_equal_the_210_function(monkeypatch, card, radio):
    sc = _sc(card, **radio)

    def runs():                                      # metrics as JSON: NaN compares equal to NaN
        return [(r.fingerprint, json.dumps(r.metrics, sort_keys=True))
                for r in hl.run_world(hl.build_world(sc, 7), RULES)]
    new = runs()
    monkeypatch.setattr(BlockageA, "factor_db", _factor_db_210)
    assert new == runs()
