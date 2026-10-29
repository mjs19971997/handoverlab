# SPDX-License-Identifier: MIT
"""Expected beam gains over the TR 38.901 power angular spectrum (radio.beams.angular_spread, since 2.10.0):
defaults untouched, the quadrature against simple limits, the table values, and validation."""
import math

import numpy as np
import pytest

import handoverlab as hl
from handoverlab.channel.antenna import beam_azimuths_deg, beam_gain_db
from handoverlab.channel.spread import (U_AZ, U_ZE, LinkSpreads, _lg_asd, _lg_zsd, diffuse_gain_lin, los_ray_share,
                                        zod_offset_deg)
from handoverlab.config import BeamConfig, ConfigError

BEAMS = {"sectors": 3, "sector_az0_deg": 30.0, "n_ssb": 8, "panel": [8, 8], "tilt_deg": 102.0}
SHORT = {"mobility.users": 8, "run.duration_s": 6.0, "run.warmup_s": 1.0}
RULES = [{"rule": "a3", "name": "A3", "off_db": 3.0, "ttt_s": 0.256}]
AZ = beam_azimuths_deg(8, 120.0)


def _sc(**beam_keys):
    return hl.builtin_scenario("urban-macro-tr37885-4ghz").with_overrides(
        dict(SHORT, **{"radio.beams": dict(BEAMS, **beam_keys)}))


def _fp(sc, seed=4):
    return [(r.fingerprint, r.metrics["failures_pm"]) for r in hl.run_world(hl.build_world(sc, seed), RULES)]


def test_default_unchanged():
    assert BeamConfig().angular_spread == "none"
    assert "angular_spread" not in _sc().to_dict()["radio"]["beams"]
    assert _fp(_sc()) == _fp(_sc(angular_spread="none"))


def test_option_changes_the_run():
    sc = _sc(angular_spread="tr38901")
    assert "angular_spread" in sc.to_dict()["radio"]["beams"]
    assert _fp(sc) != _fp(_sc())
    assert _fp(sc) == _fp(sc)                                  # reproducible


def test_nodes_have_unit_rms_and_zero_mean():
    for u in (U_AZ, U_ZE):
        assert abs(float(np.mean(u))) < 1e-12
        assert float(np.sqrt(np.mean(u ** 2))) == pytest.approx(1.0)


def test_tiny_spread_is_the_geometric_gain():
    th, ph = np.array([96.0, 100.0]), np.array([5.0, -40.0])
    g0 = beam_gain_db(th, ph, AZ, 102.0, 8, 8)
    d = diffuse_gain_lin(th, ph, AZ, 102.0, 8, 8, 30.0, np.full(2, 1e-4), np.full(2, 1e-4), np.zeros(2))
    assert np.allclose(10 * np.log10(d), g0, atol=0.01)


def test_wide_spread_takes_peak_gain_and_fills_nulls():
    th, ph = np.array([97.0]), np.array([AZ[4]])                # in the peak of beam 4
    g0 = 10 ** (beam_gain_db(th, ph, AZ, 102.0, 8, 8)[0] / 10)
    d = diffuse_gain_lin(th, ph, AZ, 102.0, 8, 8, 30.0, np.array([20.0]), np.array([3.0]), np.zeros(1))[0]
    assert d[4] < 0.5 * g0[4]                                   # the narrow beam loses more than 3 dB
    assert d.min() > g0.min()                                   # the deepest null fills
    assert 0.6 < d.sum() / g0.sum() <= 1.05                     # the sum over the beams is nearly kept
    # the wide sector beam (10 x 1) loses far less
    s0 = 10 ** (beam_gain_db(th, ph, [0.0], 102.0, 10, 1)[0, 0] / 10)
    s = diffuse_gain_lin(th, ph, [0.0], 102.0, 10, 1, 30.0, np.array([20.0]), np.array([3.0]), np.zeros(1))[0, 0]
    assert s / s0 > 0.6 > d[4] / g0[4]


def test_table_values():
    # TR 38.901 V19.5.0 Table 7.5-6 Part-1 (UMa) and Tables 7.5-7 / 7.5-8
    assert _lg_asd("uma", False, 4.0) == (1.09, 0.44) and _lg_asd("uma", True, 4.0) == (0.92, 0.31)
    f = math.log10(1 + 28.0)
    assert _lg_asd("umi_street_canyon", False, 28.0) == pytest.approx((-0.24 * f + 1.54, 0.10 * f + 0.33))
    mu, sd = _lg_zsd("uma", False, 250.0, 1.5, 25.0)
    assert float(mu) == pytest.approx(-2.1 * 0.25 + 0.9) and sd == 0.49
    assert float(_lg_zsd("uma", True, 2000.0, 1.5, 25.0)[0]) == -0.5
    # NLOS ZOD offset of UMa at fc = 6 GHz (note 4): e(6) - 10^(a log10(max(25, d)) + c)
    lf = math.log10(6.0)
    want = 7.66 * lf - 5.96 - 10 ** ((0.208 * lf - 0.782) * math.log10(250.0) + (-0.13 * lf + 2.03))
    assert float(zod_offset_deg("uma", 250.0, 1.5, 4.0)) == pytest.approx(want)
    assert float(zod_offset_deg("umi_street_canyon", 5.0, 1.5, 28.0)) == pytest.approx(-10 ** (-1.5 + 3.3))
    assert los_ray_share() == pytest.approx(10 ** 0.9 / (10 ** 0.9 + 1))


def test_link_spreads_limits_and_los_scaling():
    ls = LinkSpreads(np.random.default_rng(1), 50, 7, "uma", 4.0, 1.5, 25.0)
    u, s = np.meshgrid(np.arange(50), np.arange(7), indexing="ij")
    a_n, z_n, o_n = ls.spreads(u, s, np.full(u.shape, 200.0), False)
    a_l, z_l, o_l = ls.spreads(u, s, np.full(u.shape, 200.0), True)
    assert a_n.max() <= 104.0 and z_n.max() <= 52.0 and np.all(o_l == 0) and np.all(o_n < 0)
    assert np.median(a_l) / (10 ** 0.92) == pytest.approx(1 / math.sqrt(1 - los_ray_share()), rel=0.3)


def test_validation():
    with pytest.raises(ConfigError):
        _sc(angular_spread="cluster")
    with pytest.raises(ConfigError):
        hl.builtin_scenario("rural-700mhz").with_overrides({"radio.beams": dict(BEAMS, angular_spread="tr38901")})
