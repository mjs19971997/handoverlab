# SPDX-License-Identifier: MIT
"""Large-scale calibration of TR 38.901 clause 7.8.1 against 3GPP R1-165974 (since 1.8.0)."""
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
    assert rep.ok and len(rep.checks) == 18
