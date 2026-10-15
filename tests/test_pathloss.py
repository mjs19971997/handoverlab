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
        pl.path_loss(np.array([10.0]), np.array([True]), "rma", 3.5, 10.0, 1.5)


def test_los_probability_umi():
    assert pl.p_los_umi(100.0) == pytest.approx(0.2310, abs=5e-5)
    assert pl.p_los_umi(10.0) == 1.0
    p = pl.p_los_umi(np.linspace(20.0, 500.0, 50))
    assert np.all(np.diff(p) < 0)
