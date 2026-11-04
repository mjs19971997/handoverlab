# SPDX-License-Identifier: MIT
"""Blockage model A of TR 38.901 clause 7.6.4.1 (radio.blockage "a", since 2.10.0): defaults untouched, the
knife-edge terms, the self-blocking region, and validation; since 2.10.1 the same values as the 2.10.0 function,
since 2.11.0 also the same values as the 2.10.1 function, since 2.11.1 the compiled loops (run.backend: numba)
the same values as the NumPy path."""
import copy
import json
import math

import numpy as np
import pytest
from scipy.special import ndtr

import handoverlab as hl
from handoverlab.channel import _blockage_kernels as bk
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

def _edge_terms_210(d, half, full, kr):
    """_edge_terms of 2.10.0 and 2.10.1 (every offset evaluated, then masked), kept as the reference."""
    a1 = np.radians(d - half)
    a2 = np.radians(d + half)
    s1 = np.where(d > half, -1.0, 1.0)
    s2 = np.where(d < -half, -1.0, 1.0)

    def f(a, s):
        v = np.sqrt(np.maximum(kr * (1.0 / np.cos(a) - 1.0), 0.0))
        return np.arctan(s * 0.5 * math.pi * v) / math.pi
    return np.where(np.abs(d) < full, f(a1, s1) + f(a2, s2), 0.0)


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
        fa = _edge_terms_210(da, 0.5 * x_k[:, :, None, None, :], x_k[:, :, None, None, :], self.kr)
        fz = _edge_terms_210(a_ze - THETA_K, 0.5 * Y_K, Y_K, self.kr)
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


def _factor_db_2101(self, x, y, heading, sites, los_w, n, mult=1, layout=None):
    """BlockageA.factor_db of 2.10.1 (blocks of links, per LOS state, every edge term evaluated), kept as the
    reference."""
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
    hd = np.degrees(heading)
    p_sb, x_sb, t_sb, y_sb = SELF_REGION[self.mode]
    keep = 1.0 - 10.0 ** (-SELF_LOSS_DB / 10.0)

    def terms(a_az, a_ze, hdl, phl, xkl):
        i_a = np.abs(_wrap(a_az - hdl[:, None] - p_sb)) < 0.5 * x_sb
        i_z = np.abs(a_ze - t_sb) < 0.5 * y_sb
        da = _wrap(a_az[..., None] - phl[:, None, :])
        fa = _edge_terms_210(da, 0.5 * xkl[:, None, :], xkl[:, None, :], self.kr)
        fz = _edge_terms_210(a_ze - THETA_K, 0.5 * Y_K, Y_K, self.kr)
        return i_a, i_z, fa, fz

    out = np.zeros(az.shape)
    o, azf, zef = out.reshape(-1), az.reshape(-1), ze.reshape(-1)
    wf = None if los_w is None else np.broadcast_to(np.asarray(los_w), az.shape).reshape(-1)
    for state in (True, False):
        if wf is None:
            if state:
                continue
            k_all = np.arange(o.size)
        else:
            k_all = np.flatnonzero(wf > 0.0 if state else wf < 1.0)
        asa, zsa = self.spreads[state]
        for b0 in range(0, len(k_all), blockage.BLOCK_LINKS):
            k = k_all[b0:b0 + blockage.BLOCK_LINKS]
            i, uu, _ = np.unravel_index(k, az.shape)
            azl, zel = azf[k], zef[k]
            hdl, phl, xkl = hd[i, uu], phi_k[i, uu], x_k[i, uu]
            a_n = azl[:, None] + asa * U_AZ
            z_n = np.clip(zel[:, None] + zsa * U_ZE, 0.0, 180.0)
            ia, _, fa_n, _ = terms(a_n, zel[:, None], hdl, phl, xkl)
            _, iz, _, fz_n = terms(azl[:, None], z_n, hdl, phl, xkl)
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
                i_a, i_z, fa, fz = terms(azl[:, None], zel[:, None], hdl, phl, xkl)
                f_los = (1.0 - keep * (i_a & i_z)[..., 0]) * np.prod((1.0 - fa[..., 0, :] * fz[..., 0, None])
                                                                     ** 2, -1)
                o[k] += wf[k] * (self.p_los * f_los + (1.0 - self.p_los) * f_dif)
            else:
                o[k] += (1.0 if wf is None else 1.0 - wf[k]) * f_dif
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
        new_b = copy.deepcopy(b)
        new = new_b.factor_db(x, y, h, sites, w, n, mult)
        for fn in (_factor_db_210, _factor_db_2101):
            ref_b = copy.deepcopy(b)
            ref = fn(ref_b, x, y, h, sites, w, n, mult)
            assert np.array_equal(new, ref)
            assert np.array_equal(new_b.g, ref_b.g)      # the blocker processes advance alike
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
    for fn in (_factor_db_2101, _factor_db_210):
        monkeypatch.setattr(BlockageA, "factor_db", fn)
        assert new == runs()


# ---- since 2.11.0: the edge terms are evaluated only inside the attenuation zone, as in 2.10.1 ----

@pytest.mark.parametrize("fc", [3.5, 28.0, 60.0])
def test_edge_terms_equal_the_2101_function(fc):
    kr = math.pi * 10.0 / (299792458.0 / (fc * 1e9))
    rng = np.random.default_rng(int(fc * 10))
    # azimuth use: offsets (L, N, K) wrapped to [-180, 180), widths (L, 1, K) in [5, 15] deg
    for L, N, K in ((1, 1, 1), (7, 16, 4), (300, 16, 4)):
        xk = rng.uniform(5.0, 15.0, (L, 1, K))
        d = _wrap(rng.uniform(-400.0, 400.0, (L, N, K)))
        d[:, :, :1] = rng.uniform(-16.0, 16.0, (L, N, 1))          # many offsets in or near the zone
        new, ref = _edge_terms(d, 0.5 * xk, xk, kr), _edge_terms_210(d, 0.5 * xk, xk, kr)
        assert new.shape == ref.shape and new.dtype == ref.dtype
        assert np.array_equal(new, ref)
    # zenith use: scalar half and full, offsets of any shape
    for shape in ((), (1,), (5, 1), (40, 16)):
        d = rng.uniform(-12.0, 12.0, shape)
        new, ref = _edge_terms(d, 0.5 * Y_K, Y_K, kr), _edge_terms_210(d, 0.5 * Y_K, Y_K, kr)
        assert np.shape(new) == np.shape(ref) and np.array_equal(new, ref)
    # the region edges (+-half), the zone edges (+-full), the centre (both zero signs), and no offset in the zone
    d = np.array([-10.0, -5.0, -0.0, 0.0, 5.0, 10.0, -10.0 + 1e-12, 10.0 - 1e-12, 180.0, -180.0])
    new, ref = _edge_terms(d, 5.0, 10.0, kr), _edge_terms_210(d, 5.0, 10.0, kr)
    assert np.array_equal(new, ref) and np.array_equal(np.signbit(new), np.signbit(ref))
    d = np.full((3, 4), 50.0)
    assert np.array_equal(_edge_terms(d, 5.0, 10.0, kr), _edge_terms_210(d, 5.0, 10.0, kr))


# ---- since 2.11.1: compiled loops of the diffuse part (run.backend: numba), the same values as NumPy ----

def _kernel_sets():
    """The loops as plain Python always; compiled when Numba is installed."""
    out = [pytest.param("python", id="python")]
    if bk.numba is not None:
        out.append(pytest.param("numba", id="numba"))
    return out


def _kern(kind):
    return bk.kernels() if kind == "numba" else bk.python_kernels()


def _with_kernels(b, kind):
    b = copy.deepcopy(b)
    b.kern = _kern(kind)
    return b


@pytest.mark.parametrize("kern", _kernel_sets())
@pytest.mark.parametrize("block", [None, 1, 7])
@pytest.mark.parametrize("kind", ["none", "binary", "fraction", "ones", "zeros", "per_site"])
@pytest.mark.parametrize("mode,pathloss,fc", [("portrait", "umi_street_canyon", 28.0), ("landscape", "uma", 3.5)])
def test_kernels_equal_numpy_on_random_inputs(monkeypatch, kern, block, kind, mode, pathloss, fc):
    if block is not None:
        monkeypatch.setattr(blockage, "BLOCK_LINKS", block)
    rng = np.random.default_rng(13)
    r = RadioConfig(pathloss=pathloss, carrier_ghz=fc, bs_height_m=10.0, ue_height_m=1.5, blockage="a",
                    blockage_mode=mode)
    for n, U, M, mult in ((1, 1, 1, 1), (3, 5, 7, 4), (6, 4, 9, 2), (4, 12, 19, 1)):
        b = BlockageA(np.random.default_rng(3), U, r, rng.uniform(0.5, 15.0, U), 0.01,
                      indoor=rng.random(U) < 0.3)
        assert b.kern is None                                      # NumPy unless run.backend is numba
        x, y = rng.uniform(-300.0, 300.0, (n, U)), rng.uniform(-300.0, 300.0, (n, U))
        h = rng.uniform(-math.pi, math.pi, (n, U))
        sites = rng.uniform(-400.0, 400.0, (M, 2))
        w = _weights(kind, rng, (n, U, M))
        ref_b, new_b = copy.deepcopy(b), _with_kernels(b, kern)
        ref = ref_b.factor_db(x, y, h, sites, w, n, mult)
        new = new_b.factor_db(x, y, h, sites, w, n, mult)
        assert np.array_equal(new, ref)
        assert np.array_equal(new_b.g, ref_b.g)
        assert new_b.rng.bit_generator.state == ref_b.rng.bit_generator.state


def _f_dif_numpy(b, azl, zel, hdl, phl, xkl, asa, zsa):
    """The diffuse factor of a block of links by the NumPy lines of factor_db (2.11.0)."""
    p_sb, x_sb, t_sb, y_sb = SELF_REGION[b.mode]
    keep = 1.0 - 10.0 ** (-SELF_LOSS_DB / 10.0)
    a_n = azl[:, None] + asa * U_AZ
    z_n = np.clip(zel[:, None] + zsa * U_ZE, 0.0, 180.0)
    ia = np.abs(_wrap(a_n - hdl[:, None] - p_sb)) < 0.5 * x_sb
    fa_n = _edge_terms(_wrap(a_n[..., None] - phl[:, None, :]), 0.5 * xkl[:, None, :], xkl[:, None, :], b.kr)
    iz, fz_n = np.abs(z_n - t_sb) < 0.5 * y_sb, _edge_terms(z_n - THETA_K, 0.5 * Y_K, Y_K, b.kr)
    pa, pz = ia.mean(-1), iz.mean(-1)
    ea, ea2 = fa_n.mean(-2), (fa_n ** 2).mean(-2)
    eza, eza2 = (ia[..., None] * fa_n).mean(-2), (ia[..., None] * fa_n ** 2).mean(-2)
    ez, ez2 = fz_n.mean(-1), (fz_n ** 2).mean(-1)
    ezz, ezz2 = (iz * fz_n).mean(-1), (iz * fz_n ** 2).mean(-1)
    e_s = 1.0 - keep * pa * pz
    e_nk = 2.0 * ea * ez[..., None] - ea2 * ez2[..., None]
    e_snk = e_nk - keep * (2.0 * eza * ezz[..., None] - eza2 * ezz2[..., None])
    return np.maximum(e_s - e_snk.sum(-1), 10.0 ** (-SELF_LOSS_DB / 10.0) * 1e-3)


@pytest.mark.parametrize("kern", _kernel_sets())
@pytest.mark.parametrize("mode", ["portrait", "landscape"])
def test_kernels_on_zone_and_wrap_edges(kern, mode):
    r = RadioConfig(pathloss="umi_street_canyon", carrier_ghz=28.0, bs_height_m=10.0, ue_height_m=1.5,
                    blockage="a", blockage_mode=mode)
    b = _with_kernels(BlockageA(np.random.default_rng(0), 1, r, np.array([1.0]), 0.01), kern)
    p_sb, x_sb, t_sb, y_sb = SELF_REGION[mode]
    # offsets a - phi_k on the zone edges (+-x_k), the region edges (+-x_k / 2), the centre (both zero signs),
    # the wrap boundaries (v = a - phi_k + 180 at 0, +-360, +-720 and one ulp beside them) and far outside
    xk = 10.0
    off = [-xk, xk, -0.5 * xk, 0.5 * xk, -0.0, 0.0, np.nextafter(xk, 0.0), np.nextafter(-xk, 0.0), 180.0, -180.0,
           540.0, -540.0, -900.0, 900.0, 1e6]
    for v in (0.0, 360.0, -360.0, 720.0, -720.0):
        off += [v - 180.0, np.nextafter(v, 1e9) - 180.0, np.nextafter(v, -1e9) - 180.0]
    off = np.array(off)
    L = len(off)
    phl = np.tile([0.0, 30.0, 359.0, 180.0], (L, 1))
    xkl = np.tile([xk, 5.0, 15.0, xk], (L, 1))
    azl = off + phl[:, 0]
    # self-blocking edges through the heading: a - heading - p_sb = +-x_sb / 2
    hdl = np.where(np.arange(L) % 2 == 0, azl - p_sb - 0.5 * x_sb, azl - p_sb + 0.5 * x_sb)
    # zenith: clipped at 0 and 180, the zone edges theta_k +- y_k, the region edges, the self-blocking edges
    zs = [-40.0, 0.0, 180.0, 230.0, THETA_K - Y_K, THETA_K + Y_K, THETA_K - 0.5 * Y_K, THETA_K + 0.5 * Y_K,
          THETA_K, t_sb - 0.5 * y_sb, t_sb + 0.5 * y_sb, 91.0]
    zel = np.resize(np.array(zs), L)
    for asa, zsa in ((0.0, 0.0), (1.0, 1.0), (17.4, 9.1), (104.0, 52.0)):
        for perm in (slice(None), slice(None, None, -1)):
            args = (azl[perm], zel[perm], hdl[perm], np.ascontiguousarray(phl[perm]),
                    np.ascontiguousarray(xkl[perm]), asa, zsa)
            ref = _f_dif_numpy(b, *args)
            new = b._f_dif_compiled(*args, 1.0 - 10.0 ** (-SELF_LOSS_DB / 10.0))
            assert np.array_equal(new, ref) and np.array_equal(np.signbit(new), np.signbit(ref))


@pytest.mark.parametrize("kern", _kernel_sets())
def test_kernel_wrap_equals_numpy_remainder(kern):
    zones = _kern(kern)[0]
    rng = np.random.default_rng(5)
    grid = np.arange(-1080.0, 1081.0, 90.0)
    v = np.concatenate([rng.uniform(-2000.0, 2000.0, 20000), grid, np.nextafter(grid, 1e9),
                        np.nextafter(grid, -1e9), [-0.0, 1e-300, -1e-300, 1e17, -1e17]])
    L = len(v)
    one = np.zeros(1)
    ia, iz = np.empty((L, 1), np.bool_), np.empty((L, 1), np.bool_)
    za, zz = np.empty((L, 1, 1), np.bool_), np.empty((L, 1), np.bool_)
    da, ha, dz = np.empty(L), np.empty(L), np.empty(L)
    na, _ = zones(v, np.zeros(L), np.zeros(L), np.zeros((L, 1)), np.full((L, 1), 1e30), one, one, 0.0, 1.0,
                  100.0, 1.0, THETA_K, Y_K, ia, iz, za, zz, da, ha, dz)
    assert na == L and za.all()
    assert np.array_equal(da, _wrap(v)) and np.array_equal(np.signbit(da), np.signbit(_wrap(v)))
    assert np.array_equal(ia[:, 0], np.abs(_wrap(v)) < 1.0)


def test_numba_backend_without_numba_uses_numpy(monkeypatch):
    monkeypatch.setattr(bk, "numba", None)
    assert bk.kernels() is None
    r = RadioConfig(pathloss="uma", carrier_ghz=3.5, blockage="a")
    assert BlockageA(np.random.default_rng(0), 2, r, np.ones(2), 0.01, backend="numba").kern is None
    assert BlockageA(np.random.default_rng(0), 2, r, np.ones(2), 0.01).kern is None


def _runs(sc, seed=7):
    """Fingerprints and metrics as JSON (NaN compares equal to NaN)."""
    return [(r.fingerprint, json.dumps(r.metrics, sort_keys=True))
            for r in hl.run_world(hl.build_world(sc, seed), RULES)]


@pytest.mark.parametrize("card,radio", [
    ("urban-grid-28ghz-beams", {"blockage": "a"}),
    ("urban-grid-28ghz-beams", {"blockage": "a", "blockage_mode": "landscape"}),
    ("urban-grid-28ghz-beams", {"blockage": "a", "beams": {"sectors": 3, "sector_az0_deg": 30.0, "n_ssb": 8,
                                                          "panel": [4, 8], "tilt_deg": 100.0,
                                                          "angular_spread": "tr38901"}}),
    ("urban-macro-tr37885-4ghz", {"blockage": "a"}),
    ("highway-tr37885-30ghz", {"blockage": "a"}),          # wrap-around, every link LOS
])
def test_numba_backend_runs_equal_numpy(monkeypatch, card, radio):
    pytest.importorskip("numba")
    sc = _sc(card, **radio)
    ref = _runs(sc)
    calls = []
    compiled = BlockageA._f_dif_compiled

    def spy(self, *a):
        calls.append(1)
        return compiled(self, *a)
    monkeypatch.setattr(BlockageA, "_f_dif_compiled", spy)
    assert _runs(sc.with_overrides({"run.backend": "numba"})) == ref
    assert calls                                     # the compiled loops ran


def test_kernel_logic_in_a_run_without_numba(monkeypatch):
    """The loops as plain Python in a whole run: the same fingerprints and metrics as the NumPy path."""
    sc = _sc("urban-grid-28ghz-beams", blockage="a").with_overrides({"mobility.users": 3, "run.duration_s": 3.0})
    ref = _runs(sc)
    init = BlockageA.__init__
    used = []

    def numba_init(self, *a, **kw):
        init(self, *a, **kw)
        self.kern = bk.python_kernels()
        used.append(1)
    monkeypatch.setattr(BlockageA, "__init__", numba_init)
    assert _runs(sc) == ref and used
