# SPDX-License-Identifier: MIT
"""Large-scale calibration of TR 38.901 clause 7.8.1 against 3GPP R1-165974 (since 1.8.0) and, at 7 GHz,
R1-2506406 (since 2.4.0)."""
import math

import numpy as np
import pytest

from handoverlab.channel import pathloss as pl
from handoverlab.verify import calibration as cal


def test_antenna_element_and_array():
    # Table 7.3-1: 8 dBi at boresight, 3 dB down at 32.5 deg off boresight, at most 30 dB down
    assert float(cal.element_gain_db(90.0, 0.0)) == pytest.approx(8.0)
    assert float(cal.element_gain_db(90.0, 32.5)) == pytest.approx(5.0)
    assert float(cal.element_gain_db(10.0, 170.0)) == pytest.approx(-22.0)
    # ten elements steered to the tilt: 10 log10(10) = 10 dB at the tilt angle
    assert float(cal.array_gain_db(102.0, 102.0)) == pytest.approx(10.0)
    assert float(cal.array_gain_db(90.0, 102.0)) < 10.0


def test_layout_and_wrap_around():
    s = cal.hex_sites(500.0)
    assert len(s) == 19 and np.allclose(s[0] * 0 + s.mean(axis=0), 0.0, atol=1e-9)
    d = np.hypot(*(s[:, None, :] - s[None, :, :]).transpose(2, 0, 1))
    assert np.min(d[d > 0]) == pytest.approx(500.0)
    off = cal.wrap_offsets(500.0)
    assert len(off) == 7 and np.allclose(np.hypot(off[1:, 0], off[1:, 1]), 500.0 * math.sqrt(19.0))
    assert len(cal.indoor_sites()) == 12


@pytest.mark.parametrize("name,model,hbs", [("UMa", "uma", 25.0), ("UMi", "umi_street_canyon", 10.0),
                                            ("Indoor", "inh_office", 3.0)])
def test_calibration_pathloss_is_the_engine_pathloss(name, model, hbs):
    hut = 1.0 if name == "Indoor" else 1.5
    d2 = np.linspace(10.0, 140.0 if name == "Indoor" else 3000.0, 200)
    d3 = np.sqrt(d2 ** 2 + (hbs - hut) ** 2)
    for los in (True, False):
        mine = cal.pathloss_db(name, los, d2, d3, 6.0, hbs, hut)
        assert np.allclose(mine, pl.path_loss(d2, los, model, 6.0, hbs, hut), atol=1e-9)
    if name != "Indoor":
        assert np.allclose(cal.p_los(name, d2, 1.5), pl.p_los(d2, model))


def test_uma_los_probability_and_effective_height_for_high_users():
    d = np.array([50.0, 100.0, 200.0])
    assert np.all(cal.p_los("UMa", d, 22.5) > cal.p_los("UMa", d, 1.5))      # C'(h_UT) > 0 above 13 m
    he = cal.uma_effective_height(np.random.default_rng(1), np.full(4000, 100.0), np.full(4000, 22.5))
    assert set(np.unique(he)) <= {1.0, 12.0, 15.0, 18.0, 21.0} and (he == 1.0).mean() > 0.3
    assert np.all(cal.uma_effective_height(np.random.default_rng(2), np.full(10, 100.0), np.full(10, 1.5)) == 1.0)


def test_o2i_penetration_loss():
    loss, d_in = cal.o2i_loss_db(np.random.default_rng(3), 20000, 6.0)
    assert np.all((d_in >= 0.0) & (d_in <= 25.0)) and d_in.mean() == pytest.approx(25.0 / 3.0, abs=0.2)
    # low loss at 6 GHz: 5 - 10 log10(0.3 10^(-3.2/10) + 0.7 10^(-29/10)) = 13.4 dB plus 0.5 d_in
    low = 5.0 - 10.0 * math.log10(0.3 * 10 ** (-0.32) + 0.7 * 10 ** (-2.9))
    assert low == pytest.approx(13.40, abs=0.01)
    assert np.median(loss) > low


def test_reference_data_is_r1_165974():
    ref = cal.load_reference()
    assert set(ref) >= {c.key for c in cal.CASES}
    uma = ref["UMa-6GHz"]
    i = list(uma["cdf_percent"]).index(50.0)
    assert uma["coupling_gain_db_mean"][i] == pytest.approx(-120.35, abs=0.01)
    assert uma["coupling_gain_db_n"][i] == 21


@pytest.mark.parametrize("case", cal.CASES, ids=lambda c: c.key)
def test_drops_fall_in_the_company_range(case):
    res = cal.simulate_drops(case, 4000, 5)
    for c in cal.compare(case, res, percentiles=(10, 50, 90)):
        assert np.all(c.ours >= c.lo - 1.0) and np.all(c.ours <= c.hi + 1.0), (c.key, c.metric, c.ours, c.lo, c.hi)


def test_verify_group(capsys):
    from handoverlab.verify import run_verify
    rep = run_verify(["calibration"])
    checks = [c for c in rep.checks if c.status != "NOTE"]
    notes = [c for c in rep.checks if c.status == "NOTE"]
    # 18 checks of R1-165974, 18 checks (C1) and 6 notes (C2) of R1-2506406 (since 2.4.0)
    assert rep.ok and len(checks) == 36 and len(notes) == 6
    assert sum(c.name.startswith("R1-2506406") for c in checks) == 18


# ---------------------------------------------------------------------------
# 7 GHz: TR 38.901 Table 7.8-1A against R1-2506406 (since 2.4.0)
# ---------------------------------------------------------------------------
def _rot_lcs(theta, phi, alpha, beta):
    """Independent write-out: direction in the GCS rotated by R^T = (Rz(alpha) Ry(beta))^T (Eqs. 7.1-2, 7.1-3)."""
    t, p, a, b = (math.radians(x) for x in (theta, phi, alpha, beta))
    rho = np.array([math.sin(t) * math.cos(p), math.sin(t) * math.sin(p), math.cos(t)])
    rz = np.array([[math.cos(a), -math.sin(a), 0.0], [math.sin(a), math.cos(a), 0.0], [0.0, 0.0, 1.0]])
    ry = np.array([[math.cos(b), 0.0, math.sin(b)], [0.0, 1.0, 0.0], [-math.sin(b), 0.0, math.cos(b)]])
    x, y, z = (rz @ ry).T @ rho
    return math.degrees(math.acos(z)), math.degrees(math.atan2(y, x))


def test_lcs_rotation_of_a_tilted_antenna():
    # no tilt: theta unchanged, phi relative to the bearing
    t, p = cal.gcs_to_lcs_deg(100.0, 170.0, 150.0, 0.0)
    assert float(t) == pytest.approx(100.0) and float(p) == pytest.approx(20.0)
    # a positive downtilt points the boresight below the horizon: theta = 90 + beta maps to theta' = 90
    t, p = cal.gcs_to_lcs_deg(95.0, 30.0, 30.0, 5.0)
    assert float(t) == pytest.approx(90.0) and float(p) == pytest.approx(0.0, abs=1e-9)
    rng = np.random.default_rng(4)
    for _ in range(50):
        th, ph, al, be = rng.uniform(1, 179), rng.uniform(-180, 180), rng.uniform(0, 360), rng.uniform(-10, 10)
        t, p = cal.gcs_to_lcs_deg(th, ph, al, be)
        t2, p2 = _rot_lcs(th, ph, al, be)
        assert float(t) == pytest.approx(t2, abs=1e-9) and float(p) == pytest.approx(p2, abs=1e-9)


def test_sma_sector_gain_peaks_at_the_mechanical_tilt():
    # element 8 dBi + array 10 log10(10) = 18 dBi on the rotated boresight
    assert float(cal.sma_gain_db(95.0, 150.0, 150.0, 95.0)) == pytest.approx(18.0)
    assert float(cal.sma_gain_db(92.0, 30.0, 30.0, 92.0)) == pytest.approx(18.0)
    assert float(cal.sma_gain_db(90.0, 150.0, 150.0, 95.0)) < 18.0


def test_sma_users_and_penetration_loss():
    rng = np.random.default_rng(6)
    indoor, resid, hut = cal.sma_users(rng, 40000)
    assert indoor.mean() == pytest.approx(0.8, abs=0.01) and resid.mean() == pytest.approx(0.9, abs=0.01)
    assert set(np.unique(hut[~indoor])) == {1.5}
    assert set(np.unique(hut[indoor & resid])) == {1.5, 4.5}
    assert set(np.unique(hut[indoor & ~resid])) == {1.5, 4.5, 7.5, 10.5, 13.5}
    assert (hut[indoor & resid] == 4.5).mean() == pytest.approx(0.5, abs=0.02)
    loss, d_in = cal.sma_penetration_db(rng, indoor, resid, 7.0)
    car = loss[~indoor]
    assert car.mean() == pytest.approx(9.0, abs=0.15) and car.std() == pytest.approx(5.0, abs=0.15)
    assert np.all(d_in[~indoor] == 0.0) and d_in[indoor & resid].max() <= 10.0 and d_in[indoor].max() <= 25.0
    # low-loss A wall at 7 GHz: 5 - 10 log10(0.3 10^(-(2 + 0.2 f)/10) + 0.7 10^(-(1.03 + 0.17 f)/10))
    wall = 5.0 - 10.0 * math.log10(0.3 * 10 ** (-(2.0 + 1.4) / 10) + 0.7 * 10 ** (-(1.03 + 1.19) / 10))
    b = loss[indoor & resid] - 0.5 * d_in[indoor & resid]
    assert b.mean() == pytest.approx(wall, abs=0.1) and b.std() == pytest.approx(4.4, abs=0.1)


def test_reference_data_is_r1_2506406():
    ref = cal.load_reference(cal.DATA_R1_2506406)
    assert set(ref) == {c.key for c in cal.CASES_R1_2506406}
    uma = ref["UMa-7GHz"]
    i = list(uma["cdf_percent"]).index(50.0)
    assert uma["coupling_gain_db_mean"][i] == pytest.approx(-122.39, abs=0.01)
    assert uma["coupling_gain_db_n"][i] == 17 and uma["sinr_db_n"][i] == 16
    assert ref["SMa-7GHz-1732m"]["coupling_gain_db_n"][i] == 13


def test_old_cases_keep_their_glass_and_draws():
    for sc in cal.CASES:
        assert sc.irr_glass == cal.IRR_GLASS_R1_165974
        a = cal.simulate_drops(sc, 300, 2)
        b = cal.simulate_drops(sc, 300, 2, irr_glass=cal.IRR_GLASS_R1_165974)
        assert all(np.array_equal(a[k], b[k]) for k in a)
    assert all(sc.irr_glass == cal.IRR_GLASS_V19 for sc in cal.CASES_R1_2506406)
    assert [c.key for c in cal.CASES_R1_2506406] == ["UMa-6GHz", "UMi-6GHz", "UMa-7GHz", "UMi-7GHz",
                                                      "SMa-7GHz-1299m", "SMa-7GHz-1732m"]


@pytest.mark.parametrize("case", cal.CASES_R1_2506406, ids=lambda c: c.key)
def test_7ghz_drops_fall_in_the_company_range(case):
    res = cal.simulate_drops(case, 4000, 5)
    for c in cal.compare(case, res, percentiles=(10, 50, 90)):
        assert np.all(c.ours >= c.lo - 1.0) and np.all(c.ours <= c.hi + 1.0), (c.key, c.metric, c.ours, c.lo, c.hi)
