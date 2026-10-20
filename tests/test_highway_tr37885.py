# SPDX-License-Identifier: MIT
"""The TR 37.885 highway of 1.11.0: wrap-around, the hexagonal layout, LOS-only links and the new cards."""
import math
import warnings

import numpy as np
import pytest

import handoverlab as hl
from handoverlab.channel.pathloss import path_loss
from handoverlab.channel.source import RadioSource
from handoverlab.config import ConfigError, Scenario
from handoverlab.layout import HEX_ROAD_DEG, highway, highway_hex, make_layout
from handoverlab.mobility import PROFILES, trajectories
from handoverlab.stability import HandoverLabDeprecationWarning
from handoverlab.world import build_world

SHORT = {"run.duration_s": 10.0, "run.warmup_s": 2.0}


def test_wrap_offsets_take_the_nearest_image():
    lay = highway(length=2000.0, site_spacing=500.0, wrap=True)
    assert lay.period_x == 2000.0
    dx, _ = lay.offsets(np.array([990.0]), np.array([0.0]))
    assert np.isclose(dx[0, 0], 990.0 - (-750.0) - 2000.0)              # site at -750 seen across the seam
    assert np.all(np.abs(lay.offsets(np.linspace(-1000, 999, 50), np.zeros(50))[0]) <= 1000.0 + 1e-9)
    assert np.allclose(lay.wrap_x([1000.0, -1000.0, 2500.0]), [-1000.0, -1000.0, 500.0])
    plain = highway(length=2000.0, site_spacing=500.0)
    assert plain.period_x is None and np.allclose(plain.wrap_x([1500.0]), [1500.0])


def test_one_side_and_hexagonal_layouts():
    one = highway(length=3464.0, site_spacing=1732.0, site_offset=35.0, wrap=True, one_side=True)
    assert np.allclose(one.sites[:, 1], 12.0 + 35.0) and np.allclose(np.diff(one.sites[:, 0]), 1732.0)
    hexa = highway_hex(500.0)
    assert hexa.n_sites == 19 and np.isclose(hexa.period_x, math.sqrt(19.0) * 500.0)
    assert np.isclose(HEX_ROAD_DEG, math.degrees(math.atan2(math.sqrt(3.0), 4.0)))
    assert np.any(np.all(np.isclose(hexa.sites, 0.0), axis=1))         # the road passes the centre site
    d = hexa.distances(hexa.sites[:, 0], hexa.sites[:, 1])
    d[np.arange(19), np.arange(19)] = np.inf
    assert np.allclose(d.min(axis=1), 500.0)                           # every site has neighbours at the ISD
    assert np.isclose(np.sort(d, axis=1)[:, 5], 500.0).all()           # six of them, with the wrap-around


def test_wrapped_vehicles_keep_lane_direction_and_speed():
    assert PROFILES["v140"][0].v_min == PROFILES["v140"][0].v_max == 140.0 / 3.6
    sc = hl.builtin_scenario("highway-tr37885-4ghz").with_overrides({"run.duration_s": 120.0, "mobility.users": 12})
    lay = make_layout(sc.layout)
    x, y, v, th = trajectories(lay, sc.mobility, 120.0, sc.protocol.step_s, np.random.default_rng(4))
    assert np.allclose(v, 140.0 / 3.6)
    assert x.min() >= lay.xmin - 1e-9 and x.max() < lay.xmax
    assert np.all(np.ptp(y, axis=0) == 0.0) and np.all(np.ptp(th, axis=0) == 0.0)   # one lane, one heading
    step = np.abs(np.diff(x, axis=0))
    jump = step > lay.period_x / 2
    assert jump.any() and np.allclose(step[~jump], v[None, :].repeat(len(step), 0)[~jump] * sc.protocol.step_s)


def test_los_only_links_and_continuity_at_the_seam():
    sc = hl.builtin_scenario("highway-tr37885-4ghz").with_overrides(
        dict(SHORT, **{"mobility.users": 20, "radio.shadow_los_db": 0.0, "radio.shadow_los_far_db": None}))
    w = build_world(sc, 2)
    ch = next(RadioSource(w).chunks())
    R = sc.radio
    d2 = w.layout.distances(w.x[:ch.n].ravel(), w.y[:ch.n].ravel())
    want = R.tx_power_dbm + R.bs_gain_db + R.ue_gain_db - path_loss(d2, True, R.pathloss, R.carrier_ghz,
                                                                      R.bs_height_m, R.ue_height_m)
    assert np.abs(ch.rsrp.reshape(want.shape) - want).max() < 1e-9
    sc2 = hl.builtin_scenario("highway-tr37885-4ghz").with_overrides(
        {"run.duration_s": 60.0, "mobility.users": 8, "radio.time_var_db": 0.0})
    w = build_world(sc2, 5)
    rs = np.concatenate([c.rsrp for c in RadioSource(w).chunks()])
    k, u = np.nonzero(np.abs(np.diff(w.x, axis=0)) > w.layout.period_x / 2)
    assert len(k) and np.abs(rs[k + 1, u] - rs[k, u]).max() < 0.5


def test_new_cards_run_with_invariants():
    for name, extra in (("highway-tr37885-4ghz", {"mobility.users": 20}),
                        ("highway-tr37885-30ghz", {"mobility.users": 6, "run.duration_s": 4.0, "run.warmup_s": 1.0})):
        sc = hl.builtin_scenario(name).with_overrides(dict(SHORT, **extra))
        res = hl.simulate(sc, [{"rule": "a3"}], seeds=[1], debug=True)
        assert res[0].metrics["ue_minutes"] > 0


def test_configuration_checks():
    base = {"layout.kind": "highway", "layout.wrap": True}
    with pytest.raises(ConfigError, match="layout.wrap"):
        Scenario().with_overrides({"layout.wrap": True})                 # street grid
    with pytest.raises(ConfigError, match="whole number"):
        Scenario().with_overrides(dict(base, **{"layout.road_length_m": 2100.0, "layout.site_spacing_m": 500.0}))
    with pytest.raises(ConfigError, match="layout.road_length_m"):
        Scenario().with_overrides(dict(base, **{"layout.highway_sites": "hex19", "layout.site_spacing_m": 500.0}))
    with pytest.raises(ConfigError, match="layout.highway_sites"):
        Scenario().with_overrides({"layout.kind": "highway", "layout.highway_sites": "hex19"})
    with pytest.raises(ConfigError, match="radio.los_model"):
        Scenario().with_overrides({"radio.los_model": "los"})            # the buildings decide on the grid
    with pytest.raises(ConfigError, match="radio.los_model"):
        Scenario().with_overrides({"layout.kind": "open_area", "radio.los_model": "always"})
    d = Scenario().to_dict()
    assert "wrap" not in d["layout"] and "highway_sites" not in d["layout"] and "los_model" not in d["radio"]


def test_old_highway_card_is_deprecated():
    assert "highway-10ghz" not in hl.scenario_names()
    assert "highway-10ghz" in hl.scenario_names(deprecated=True)
    with pytest.warns(HandoverLabDeprecationWarning, match="highway-tr37885"):
        sc = hl.builtin_scenario("highway-10ghz")
    assert sc.layout.kind == "highway" and not sc.layout.wrap
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        hl.builtin_scenario("highway-tr37885-4ghz")                    # the new cards do not warn
