# SPDX-License-Identifier: MIT
"""Indoor office and rural scenarios (since 1.7.0): layout, mobility, configuration and short runs."""
import numpy as np
import pytest

import handoverlab as hl
from handoverlab.config import ConfigError, Scenario
from handoverlab.layout import make_layout
from handoverlab.mobility import trajectories


def test_indoor_layout_is_the_tr38901_office():
    lay = make_layout(hl.builtin_scenario("indoor-office-4ghz").layout)
    assert lay.kind == "indoor" and lay.n_sites == 12 and not lay.is_grid
    assert (lay.xmin, lay.xmax, lay.ymin, lay.ymax) == (-60.0, 60.0, -25.0, 25.0)
    assert sorted(set(lay.sites[:, 0])) == [-50.0, -30.0, -10.0, 10.0, 30.0, 50.0]
    assert sorted(set(lay.sites[:, 1])) == [-10.0, 10.0]
    # without area_m the indoor hall has the standard size
    lay2 = make_layout(Scenario().with_overrides({"layout.kind": "indoor", "layout.site_spacing_m": 20.0}).layout)
    assert (lay2.xmax - lay2.xmin, lay2.ymax - lay2.ymin) == (120.0, 50.0)


def test_rural_layout_is_a_hexagonal_grid_of_1732_m():
    lay = make_layout(hl.builtin_scenario("rural-700mhz").layout)
    assert lay.kind == "open_area" and lay.n_sites == 11
    assert (lay.xmax - lay.xmin, lay.ymax - lay.ymin) == (6000.0, 3500.0)
    d = np.hypot(*(lay.sites[:, None, :] - lay.sites[None, :, :]).transpose(2, 0, 1))
    assert np.min(d[d > 0]) == pytest.approx(1732.0, abs=0.5)


def test_area_m_leaves_the_open_area_default_unchanged():
    base = make_layout(Scenario().with_overrides({"layout.kind": "open_area"}).layout)
    same = make_layout(Scenario().with_overrides({"layout.kind": "open_area",
                                                  "layout.area_m": [1319.0, 770.0]}).layout)
    assert np.array_equal(base.sites, same.sites)
    assert "area_m" not in Scenario().to_dict()["layout"]
    with pytest.raises(ConfigError, match="layout.area_m"):
        Scenario().with_overrides({"layout.area_m": [0.0, 10.0]})


def test_indoor_users_stay_inside_the_hall_at_walking_speed():
    sc = hl.builtin_scenario("indoor-office-4ghz")
    lay = make_layout(sc.layout)
    x, y, v, _ = trajectories(lay, sc.mobility, 60.0, sc.protocol.step_s, np.random.default_rng(2))
    assert np.all((x >= lay.xmin + 2.0 - 1e-9) & (x <= lay.xmax - 2.0 + 1e-9))
    assert np.all((y >= lay.ymin + 2.0 - 1e-9) & (y <= lay.ymax - 2.0 + 1e-9))
    assert np.all((v >= 2.7 / 3.6) & (v <= 3.3 / 3.6))


def test_rma_frequency_limit_and_model_names():
    with pytest.raises(ConfigError, match="radio.carrier_ghz"):
        hl.builtin_scenario("rural-700mhz").with_overrides({"radio.carrier_ghz": 40.0})
    with pytest.raises(ConfigError, match="radio.pathloss"):
        Scenario().with_overrides({"radio.pathloss": "suburban"})


@pytest.mark.parametrize("name,over", [
    ("indoor-office-4ghz", {"run.duration_s": 30.0, "run.warmup_s": 5.0, "mobility.users": 10}),
    ("rural-700mhz", {"run.duration_s": 30.0, "run.warmup_s": 5.0, "mobility.users": 8,
                      "layout.area_m": [4000.0, 2000.0]}),
])
def test_new_scenarios_run_with_invariants(name, over):
    sc = hl.builtin_scenario(name).with_overrides(over)
    res = hl.simulate(sc, [{"rule": "a3"}, {"rule": "cho"}], seeds=[1], debug=True)
    again = hl.simulate(sc, [{"rule": "a3"}, {"rule": "cho"}], seeds=[1])
    assert [r.metrics for r in res] == [r.metrics for r in again]
    assert res[0].metrics["attempts_pm"] > 0


@pytest.mark.parametrize("base,over", [
    ("smoke", {}),
    ("smoke", {"layout.kind": "open_area", "radio.place_share": 0.5}),
    ("indoor-office-4ghz", {"mobility.users": 6}),
])
def test_soft_los_reduces_to_the_hard_state_and_smooths(base, over):
    from handoverlab.channel.source import RadioSource
    from handoverlab.world import build_world
    sc = hl.builtin_scenario(base).with_overrides(dict(over, **{"run.duration_s": 8.0, "run.warmup_s": 1.0,
                                                                "radio.soft_los": False}))

    def first(s):
        return next(RadioSource(build_world(s, 1)).chunks()).rsrp

    hard = first(sc)
    steep = first(sc.with_overrides({"radio.soft_los": True, "radio.soft_los_d_m": 1e14}))
    soft = first(sc.with_overrides({"radio.soft_los": True}))
    # an infinitely steep transition is the hard state; a link exactly at the LOS boundary (|z| below about 1e-7,
    # where even this transition is not yet complete) may differ: at most a few of the ~10^5 values
    assert np.count_nonzero(np.abs(steep - hard) > 0.01) <= 2
    assert np.max(np.abs(np.diff(soft, axis=0))) <= np.max(np.abs(np.diff(hard, axis=0))) + 1e-9
    assert "soft_los" not in Scenario().to_dict()["radio"]
    with pytest.raises(ConfigError, match="radio.soft_los_d_m"):
        Scenario().with_overrides({"radio.soft_los_d_m": 0.0})


def test_min_site_distance_holds_for_waypoints_and_is_off_by_default():
    from handoverlab.mobility import open_waypoints
    lay = make_layout(Scenario().with_overrides({"layout.kind": "indoor", "layout.site_spacing_m": 20.0}).layout)
    _, x, y, _ = open_waypoints(lay, 1.0, 600.0, np.random.default_rng(3), margin=2.0, min_dist=8.0)
    d = np.min(np.hypot(x[:, None] - lay.sites[None, :, 0], y[:, None] - lay.sites[None, :, 1]), axis=1)
    assert d.min() >= 8.0
    a = open_waypoints(lay, 1.0, 60.0, np.random.default_rng(4), margin=2.0)
    b = open_waypoints(lay, 1.0, 60.0, np.random.default_rng(4), margin=2.0, min_dist=0.0)
    assert all(np.array_equal(p, q) for p, q in zip(a[:3], b[:3]))
    assert hl.builtin_scenario("rural-700mhz").layout.min_site_distance_m == 35.0
    with pytest.raises(ConfigError, match="layout.min_site_distance_m"):
        Scenario().with_overrides({"layout.min_site_distance_m": -1.0})
