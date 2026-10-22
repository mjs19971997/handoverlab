# SPDX-License-Identifier: MIT
"""Scenario items of 2.3.0: the TR 37.885 urban macro card, SMa, O2I building penetration of indoor users."""
import math

import numpy as np
import pytest

import handoverlab as hl
from handoverlab.channel import pathloss as pl
from handoverlab.channel.source import RadioSource
from handoverlab.config import ConfigError, Scenario
from handoverlab.layout import make_layout
from handoverlab.mobility import trajectories
from handoverlab.world import build_world

SHORT = {"run.duration_s": 4.0, "run.warmup_s": 0.0}
GROUPS = [{"share": 0.5, "v_min": 1.0, "v_max": 1.0, "indoor": True}, {"share": 0.5, "v_min": 10.0, "v_max": 10.0}]


# ---------------------------------------------------------------------------
# indoor users: speed-group flag, job ids, trajectories
# ---------------------------------------------------------------------------
def test_indoor_flag_left_out_of_the_job_dictionary_while_false():
    sc = Scenario.from_dict({"mobility": {"groups": [{"share": 1.0, "v_min": 5.0, "v_max": 5.0}]}})
    assert "indoor" not in sc.to_dict()["mobility"]["groups"][0]
    assert sc.to_dict(full=True)["mobility"]["groups"][0]["indoor"] is False
    sc = Scenario.from_dict({"mobility": {"groups": GROUPS}})
    assert sc.to_dict()["mobility"]["groups"][0]["indoor"] is True
    for key in ("o2i_model", "o2i_d_in_max_m", "building_los", "env_height_m"):
        assert key not in Scenario().to_dict()["radio"]


def test_trajectories_mark_indoor_users_without_changing_the_draws():
    sc = Scenario.from_dict({"layout": {"kind": "open_area"}, "mobility": {"users": 20, "groups": GROUPS},
                             "run": {"duration_s": 3.0, "warmup_s": 0.0}})
    lay = make_layout(sc.layout)
    a = trajectories(lay, sc.mobility, 3.0, 0.01, np.random.default_rng(3))
    b = trajectories(lay, sc.mobility, 3.0, 0.01, np.random.default_rng(3), with_indoor=True)
    assert len(a) == 4 and len(b) == 5
    for x, y in zip(a, b[:4]):
        assert np.array_equal(x, y)
    assert np.array_equal(b[4], b[2] == 1.0) and 0 < b[4].sum() < 20      # indoor group: 1 m/s
    assert build_world(sc.with_overrides({"mobility.groups": None}), 1).indoor is None


# ---------------------------------------------------------------------------
# configuration checks
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("over,match", [
    ({"radio.o2i_model": "glass"}, "o2i_model"),
    ({"radio.o2i_d_in_max_m": -1.0}, "o2i_d_in_max_m"),
    ({"radio.env_height_m": 0.25, "radio.pathloss": "rma", "radio.bs_height_m": 35.0}, "env_height_m"),
    ({"radio.env_height_m": 2.0}, "env_height_m"),
    ({"radio.building_los": False, "radio.clutter_los": False}, "building_los"),
    ({"radio.building_los": False, "layout.kind": "open_area"}, "building_los"),
    ({"mobility.groups": GROUPS, "radio.pathloss": "inh_office", "layout.kind": "indoor"}, "indoor users"),
    ({"mobility.groups": GROUPS, "radio.pathloss": "rma", "radio.bs_height_m": 35.0, "radio.o2i_model": "high"},
     "only the low-loss"),
    ({"mobility.groups": GROUPS, "radio.o2i_model": "low_a"}, "SMa only"),
    ({"radio.pathloss": "sma", "radio.bs_height_m": 35.0, "radio.carrier_ghz": 40.0}, "0.5-37 GHz"),
])
def test_new_keys_are_checked(over, match):
    with pytest.raises(ConfigError, match=match):
        Scenario().with_overrides(over)


# ---------------------------------------------------------------------------
# effective environment height (TR 37.885 clause 6.2.1)
# ---------------------------------------------------------------------------
def test_fixed_effective_environment_height_moves_the_breakpoint():
    d = np.array([100.0, 900.0, 1500.0, 2500.0])
    base = pl.path_loss(d, True, "uma", 4.0, 25.0, 1.6)
    assert np.array_equal(base, pl.path_loss(d, True, "uma", 4.0, 25.0, 1.6, h_e0=None))
    got = pl.path_loss(d, True, "uma", 4.0, 25.0, 1.6, h_e0=0.25)
    dbp = 4.0 * (25.0 - 0.25) * (1.6 - 0.25) * 4.0e9 / 3.0e8                  # 1782 m (h_E = 1 m: 768 m)
    d3 = np.sqrt(d ** 2 + (25.0 - 1.6) ** 2)
    want = np.where(d <= dbp, 28.0 + 22.0 * np.log10(d3) + 20.0 * math.log10(4.0),
                    28.0 + 40.0 * np.log10(d3) + 20.0 * math.log10(4.0) - 9.0 * np.log10(dbp ** 2 + 23.4 ** 2))
    assert np.allclose(got, want, rtol=0, atol=1e-9)
    assert got[1] < base[1]                                                  # 900 m: before / after the breakpoint
    r = Scenario().with_overrides({"radio.pathloss": "uma", "radio.bs_height_m": 25.0, "radio.ue_height_m": 1.6,
                                   "radio.env_height_m": 0.25}).radio
    assert pl.radio_kwargs(r)["h_e0"] == 0.25 and pl.radio_kwargs(Scenario().radio)["h_e0"] is None


# ---------------------------------------------------------------------------
# street grid with the sites above the rooftops
# ---------------------------------------------------------------------------
def test_rooftop_sites_take_the_los_state_from_the_probability_only():
    over = dict(SHORT, **{"layout.site_spacing_m": 300.0, "radio.map_res_m": 4.0, "radio.pathloss": "uma",
                          "radio.bs_height_m": 25.0, "radio.los_corr_m": 5.0})
    street = build_world(Scenario().with_overrides(over), 1).radio_map
    roof = build_world(Scenario().with_overrides(dict(over, **{"radio.building_los": False})), 1).radio_map
    assert roof.los_share > street.los_share
    lay = roof.layout
    P = roof.n_pix
    gy, gx = np.nonzero(roof.idx < P)
    px, py = roof.x0 + gx * roof.res, roof.y0 + gy * roof.res
    dd = lay.distances(px, py)
    want = float(pl.p_los(dd, "uma", 1.5).mean())
    assert abs(roof.los[roof.idx[gy, gx]].mean() - want) < 0.03


def test_existing_grid_unchanged_with_the_default():
    over = dict(SHORT, **{"layout.blocks": [1, 1], "radio.map_res_m": 4.0})
    a = build_world(Scenario().with_overrides(over), 2).radio_map
    b = build_world(Scenario().with_overrides(dict(over, **{"radio.building_los": True})), 2).radio_map
    assert np.array_equal(a.gain, b.gain) and np.array_equal(a.los, b.los)


# ---------------------------------------------------------------------------
# SMa (TR 38.901 V19.5.0 Tables 7.4.1-1 and 7.4.2-1)
# ---------------------------------------------------------------------------
def test_sma_path_loss_by_hand():
    fc, hbs, hut = 7.0, 35.0, 1.5
    dbp = 2.0 * math.pi * 35.0 * 1.5 * 7e9 / 3.0e8                          # 7697 m: beyond 5 km at 7 GHz
    assert np.isclose(pl.rma_breakpoint(fc, hbs, hut), dbp)
    d3 = math.hypot(500.0, 33.5)
    pl1 = (20 * math.log10(40 * math.pi * d3 * fc / 3) + min(0.03 * 10 ** 1.72, 10) * math.log10(d3)
           - min(0.044 * 10 ** 1.72, 14.77) + 0.002 * math.log10(10) * d3)
    assert np.isclose(float(pl.path_loss(np.array(500.0), True, "sma", fc, hbs, hut)), pl1, rtol=0, atol=1e-9)
    nlos = (161.04 - 7.1 * math.log10(10) + 7.5 * math.log10(10) - (24.37 - 3.7 * (10 / 35) ** 2) * math.log10(35)
            + (43.42 - 3.1 * math.log10(35)) * (math.log10(d3) - 3) + 20 * math.log10(fc)
            - (3.2 * math.log10(11.75 * 1.5) ** 2 - 4.97))
    assert np.isclose(float(pl.path_loss(np.array(500.0), False, "sma", fc, hbs, hut)), nlos, rtol=0, atol=1e-9)
    # no max() with the LOS loss in the SMa NLOS row: for a UT on an upper floor close to the site NLOS is below LOS
    d = np.array([10.0, 20.0])
    assert np.all(pl.path_loss(d, False, "sma", 7.0, 25.0, 13.5) < pl.path_loss(d, True, "sma", 7.0, 25.0, 13.5))
    lo, hi = pl.sma_los(np.array(dbp * 0.1 - 1e-7), 0.7, 35, 1.5), pl.sma_los(np.array(dbp * 0.1 + 1e-7), 0.7, 35, 1.5)
    assert abs(float(lo) - float(hi)) < 1e-4                                 # 0.7 GHz: d_BP = 770 m


def test_sma_los_probability_by_hand():
    d = np.array([5.0, 10.0, 100.0, 1000.0])
    rate = (-(math.log(0.98) / 30) * (20 - 1.5) / 33.5 - (math.log(0.82) / 30) * (8 - 1.5) / 33.5
            - (math.log(0.9) / 30) * (15 - 1.5) / 33.5)
    want = np.where(d <= 10, 1.0, np.exp(-d * rate))
    assert np.allclose(pl.p_los(d, "sma", sma=(35.0, 1.5, 0.1)), want, rtol=0, atol=1e-15)
    # the residential term is clipped at h_UT above 8 m; vegetation 0 drops out
    r = (-(math.log(0.98) / 30) * (20 - 10.5) / 24.5)
    assert np.isclose(float(pl.p_los(np.array(200.0), "sma", sma=(35.0, 10.5, 0.0))), math.exp(-200 * r))
    sc = hl.builtin_scenario("suburban-sma-7ghz")
    assert pl.los_args(sc.radio)["sma"] == (35.0, 1.5, 0.0)


# ---------------------------------------------------------------------------
# O2I building penetration (clause 7.4.3.1)
# ---------------------------------------------------------------------------
def test_o2i_wall_losses_by_hand():
    f = 7.0
    low = 5 - 10 * math.log10(0.3 * 10 ** (-(2 + 0.2 * f) / 10) + 0.7 * 10 ** (-(5 + 4 * f) / 10))
    high = 5 - 10 * math.log10(0.7 * 10 ** (-(25.4 + 0.11 * f) / 10) + 0.3 * 10 ** (-(5 + 4 * f) / 10))
    low_a = 5 - 10 * math.log10(0.3 * 10 ** (-(2 + 0.2 * f) / 10) + 0.7 * 10 ** (-(1.03 + 0.17 * f) / 10))
    for model, want in (("low", low), ("high", high), ("low_a", low_a)):
        assert math.isclose(pl.o2i_wall_loss_db(model, f), want, abs_tol=1e-12)
    assert low_a < low < high


def test_o2i_loss_per_user():
    from types import SimpleNamespace
    r = SimpleNamespace(o2i_model="low", carrier_ghz=4.0, pathloss="uma", o2i_d_in_max_m=None)
    indoor = np.arange(10) % 2 == 0
    a = pl.o2i_building_loss(np.random.default_rng(1), indoor, r)
    b = pl.o2i_building_loss(np.random.default_rng(1), np.ones(10, bool), r)
    assert np.all(a[~indoor] == 0.0) and np.array_equal(a[indoor], b[indoor])   # independent of the others
    r.o2i_d_in_max_m = 0.0
    r.o2i_model = "high"
    c = pl.o2i_building_loss(np.random.default_rng(2), np.ones(20000, bool), r)
    assert abs(c.mean() - pl.o2i_wall_loss_db("high", 4.0)) < 0.2 and abs(c.std() - 6.5) < 0.2
    assert pl.o2i_d_in_max(SimpleNamespace(o2i_d_in_max_m=None, pathloss="rma")) == 10.0
    assert pl.o2i_d_in_max(SimpleNamespace(o2i_d_in_max_m=None, pathloss="sma")) is None


def test_o2i_replaces_the_car_loss_of_indoor_users():
    sc = hl.builtin_scenario("suburban-sma-7ghz").with_overrides(
        {"run.duration_s": 1.0, "run.warmup_s": 0.0, "mobility.users": 30})
    flat = sc.with_overrides({"mobility.groups": [{"share": g.share, "v_min": g.v_min, "v_max": g.v_max}
                                                  for g in sc.mobility.groups]})
    w1, w0 = build_world(sc, 3), build_world(flat, 3)
    assert w1.indoor is not None and w1.indoor.any() and w0.indoor is None
    r1, r0 = next(RadioSource(w1).chunks()).rsrp, next(RadioSource(w0).chunks()).rsrp
    diff = (r1 - r0)[0, :, 0]
    assert np.allclose(diff[~w1.indoor], 0.0, atol=1e-9) and np.all(np.abs(diff[w1.indoor]) > 0)


# ---------------------------------------------------------------------------
# the two cards
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name", ["urban-macro-tr37885-4ghz", "suburban-sma-7ghz"])
def test_new_cards_run(name):
    sc = hl.builtin_scenario(name).with_overrides({"run.duration_s": 4.0, "run.warmup_s": 1.0, "mobility.users": 6,
                                                   "radio.map_res_m": 10.0})
    res = hl.simulate(sc, [{"rule": "a3"}, {"rule": "cho"}], seeds=[1], debug=True)
    again = hl.simulate(sc, [{"rule": "a3"}, {"rule": "cho"}], seeds=[1])
    assert [r.metrics for r in res] == [r.metrics for r in again]
