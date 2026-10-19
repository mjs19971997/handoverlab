# SPDX-License-Identifier: MIT
"""TR 38.901 path loss and LOS probability against hand-computed values."""
import math

import numpy as np
import pytest

from handoverlab.channel import pathloss as pl


def test_breakpoint_distance_10ghz():
    # d'_BP = 4 (10 - 1)(1.5 - 1) 10e9 / c
    assert pl.breakpoint_distance(10.0, 10.0, 1.5) == pytest.approx(600.4, abs=0.05)


def test_umi_los_hand_value():
    # 32.4 + 21 log10(d3) + 20 log10(10), d3 = sqrt(50^2 + 8.5^2)
    assert pl.umi_los(np.array(50.0), 10.0) == pytest.approx(88.208, abs=5e-4)


def test_umi_nlos_hand_value():
    # 35.3 log10(d3) + 22.4 + 21.3 log10(10)
    assert pl.umi_nlos(np.array(50.0), 10.0) == pytest.approx(103.892, abs=5e-4)


def test_umi_los_beyond_breakpoint_uses_pl2():
    d = 800.0
    d3 = math.hypot(d, 8.5)
    dbp = pl.breakpoint_distance(10.0, 10.0, 1.5)
    expect = 32.4 + 40 * math.log10(d3) + 20.0 - 9.5 * math.log10(dbp ** 2 + 8.5 ** 2)
    assert pl.umi_los(np.array(d), 10.0) == pytest.approx(expect, abs=1e-9)


def test_nlos_never_below_los():
    d = np.linspace(10.0, 1000.0, 200)
    for los, nlos in ((pl.umi_los, pl.umi_nlos), (pl.uma_los, pl.uma_nlos)):
        assert np.all(nlos(d, 3.5) >= los(d, 3.5))


def test_path_loss_selects_state():
    d = np.array([50.0, 50.0])
    out = pl.path_loss(d, np.array([True, False]), "umi_street_canyon", 10.0, 10.0, 1.5)
    assert out == pytest.approx([88.208, 103.892], abs=5e-4)


def test_path_loss_unknown_model():
    with pytest.raises(ValueError):
        pl.path_loss(np.array([10.0]), np.array([True]), "sma", 3.5, 10.0, 1.5)


def test_los_probability_umi():
    assert pl.p_los_umi(100.0) == pytest.approx(0.2310, abs=5e-5)
    assert pl.p_los_umi(10.0) == 1.0
    p = pl.p_los_umi(np.linspace(20.0, 500.0, 50))
    assert np.all(np.diff(p) < 0)


# --- RMa and InH-Office (since 1.7.0) ---------------------------------------
def test_rma_breakpoint_and_pl1_hand_value():
    # d_BP = 2 pi 35 1.5 0.7e9 / c; PL1 = 20 log10(40 pi d3 fc / 3) + 0.03 h^1.72 log10(d3) - 0.044 h^1.72
    # + 0.002 log10(h) d3 with h = 5 m
    assert pl.rma_breakpoint(0.7, 35.0, 1.5) == pytest.approx(770.223, abs=1e-3)
    d3 = math.hypot(500.0, 33.5)
    h = 5.0
    expect = (20 * math.log10(40 * math.pi * d3 * 0.7 / 3) + 0.03 * h ** 1.72 * math.log10(d3) - 0.044 * h ** 1.72
              + 0.002 * math.log10(h) * d3)
    assert float(pl.rma_los(np.array(500.0), 0.7)) == pytest.approx(expect, abs=1e-9)
    assert expect == pytest.approx(84.633, abs=5e-4)


def test_rma_pl2_and_continuity():
    dbp = pl.rma_breakpoint(0.7, 35.0, 1.5)
    a, b = pl.rma_los(np.array(dbp - 1e-6), 0.7), pl.rma_los(np.array(dbp + 1e-6), 0.7)
    assert float(a) == pytest.approx(float(b), abs=1e-4)
    d3b, d3 = math.hypot(dbp, 33.5), math.hypot(2000.0, 33.5)
    assert float(pl.rma_los(np.array(2000.0), 0.7)) == pytest.approx(
        float(pl.rma_los(np.array(dbp), 0.7)) + 40 * math.log10(d3 / d3b), abs=1e-9)


def test_rma_nlos_hand_value():
    assert float(pl.rma_nlos(np.array(500.0), 0.7)) == pytest.approx(104.843, abs=5e-4)
    assert float(pl.rma_nlos(np.array(1000.0), 3.5)) == pytest.approx(130.424, abs=5e-4)


def test_inh_hand_values():
    # LOS 32.4 + 17.3 log10(d3) + 20 log10(4); NLOS' 38.3 log10(d3) + 17.30 + 24.9 log10(4); d3 = sqrt(d^2 + 2^2)
    assert float(pl.inh_los(np.array(10.0), 4.0)) == pytest.approx(61.889, abs=5e-4)
    assert float(pl.inh_nlos(np.array(10.0), 4.0)) == pytest.approx(70.9175, abs=5e-4)
    assert float(pl.inh_nlos(np.array(40.0), 4.0)) == pytest.approx(93.671, abs=5e-4)


@pytest.mark.parametrize("model,fc,hb,hu,d", [("rma", 0.7, 35.0, 1.5, np.linspace(10.0, 5000.0, 300)),
                                              ("inh_office", 4.0, 3.0, 1.0, np.linspace(1.0, 150.0, 300))])
def test_new_models_select_state_and_nlos_not_below_los(model, fc, hb, hu, d):
    los = pl.path_loss(d, True, model, fc, hb, hu)
    nlos = pl.path_loss(d, False, model, fc, hb, hu)
    assert np.all(nlos >= los)
    pick = np.arange(len(d)) % 2 == 0
    assert np.array_equal(pl.path_loss(d, pick, model, fc, hb, hu), np.where(pick, los, nlos))


def test_los_probability_rma_and_inh():
    assert float(pl.p_los(5.0, "rma")) == 1.0
    assert float(pl.p_los(1010.0, "rma")) == pytest.approx(math.exp(-1.0))
    assert float(pl.p_los(1.0, "inh_office")) == 1.0
    assert float(pl.p_los(4.0, "inh_office")) == pytest.approx(math.exp(-2.8 / 4.7))
    assert float(pl.p_los(39.1, "inh_office")) == pytest.approx(0.32 * math.exp(-1.0))
    assert set(pl.MODELS) == {"umi_street_canyon", "uma", "rma", "inh_office"}


# --- soft LOS state (since 1.7.0) ---------------------------------------------
def test_soft_los_power_weight_hand_values():
    # LOS_soft = 1/2 + arctan(sqrt(20 / lambda) z) / pi; the power weight is LOS_soft^2 (Eq. 7.6-19)
    assert float(pl.soft_los_power_weight(0.1, 10.0)) == pytest.approx(0.7786628, abs=1e-6)
    assert float(pl.soft_los_power_weight(-0.2, 0.7)) == pytest.approx(0.0404275, abs=1e-6)
    assert float(pl.soft_los_power_weight(0.0, 3.5)) == pytest.approx(0.25)
    w = pl.soft_los_power_weight(np.linspace(-3, 3, 61), 3.5)
    assert np.all(np.diff(w) > 0) and w[0] < 1e-3 and w[-1] > 0.98     # arctan tails fall off as 1 / z


def test_mix_db():
    assert float(pl.mix_db(1.0, -80.0, -100.0)) == pytest.approx(-80.0)
    assert float(pl.mix_db(0.0, -80.0, -100.0)) == pytest.approx(-100.0)
    assert float(pl.mix_db(0.5, -80.0, -100.0)) == pytest.approx(10 * math.log10(0.5e-8 + 0.5e-10))


def test_los_shadow_sd_beyond_the_breakpoint():
    from handoverlab.config import Scenario
    r = Scenario().with_overrides({"radio.pathloss": "rma", "radio.carrier_ghz": 0.7, "radio.bs_height_m": 35.0,
                                   "radio.shadow_los_far_db": 6.0}).radio
    assert np.array_equal(pl.los_shadow_sd(np.array([500.0, 770.0, 771.0, 3000.0]), r), [4.0, 4.0, 6.0, 6.0])
    assert pl.los_shadow_sd(np.array([5000.0]), Scenario().radio) == 4.0      # unset: one value
