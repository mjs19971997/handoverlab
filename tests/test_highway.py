# SPDX-License-Identifier: MIT
"""The highway layout, lane-keeping mobility, keys added after 1.0.0rc2 and site lists from CSV files."""
import numpy as np
import pytest

import handoverlab as hl
from handoverlab.config import LATE_KEYS, ConfigError, Scenario
from handoverlab.layout import highway, make_layout
from handoverlab.mobility import PROFILES, trajectories
from handoverlab.seeds import streams

SHORT = {"run.duration_s": 30.0, "run.warmup_s": 5.0, "mobility.users": 8}


def _old():
    """The deprecated card of 1.0.0rc3-1.10.0 (roadside sites, no wrap-around); it warns since 1.11.0."""
    with pytest.warns(FutureWarning, match="deprecated"):
        return hl.builtin_scenario("highway-10ghz")


def test_highway_geometry():
    lay = highway(length=2000.0, lanes=3, lane_width=4.0, site_spacing=500.0, site_offset=35.0)
    assert lay.kind == "highway" and not lay.is_grid and len(lay.buildings) == 0
    assert np.allclose(lay.ys, [-10, -6, -2, 2, 6, 10])
    assert np.allclose(lay.sites[:, 0], [-750, -250, 250, 750])
    assert np.allclose(np.abs(lay.sites[:, 1]), 12 + 35) and np.all(np.diff(np.sign(lay.sites[:, 1])) != 0)
    assert lay.xmin == -1000 and lay.xmax == 1000 and lay.ymax >= 47
    assert lay.street_mask(np.array([0.0, 900.0]), np.array([0.0, 40.0])).all()
    two = highway(lanes=2, lane_width=3.5, sites=[(0.0, 20.0)])
    assert np.allclose(two.ys, [-5.25, -1.75, 1.75, 5.25]) and two.n_sites == 1


def _world(overrides=None, seed=3):
    sc = _old().with_overrides(dict(SHORT, **(overrides or {})))
    lay = make_layout(sc.layout)
    rng = streams(seed, "world", 3)[0]
    return sc, lay, trajectories(lay, sc.mobility, sc.run.duration_s, sc.protocol.step_s, rng)


def test_vehicles_keep_their_lane_and_speed():
    sc, lay, (x, y, v, th) = _world({"run.duration_s": 120.0})
    kmh = v * 3.6
    assert kmh.min() >= 70 - 1e-9 and kmh.max() <= 140 + 1e-9
    dt = sc.protocol.step_s
    step = np.hypot(np.diff(x, axis=0), np.diff(y, axis=0))
    assert np.all(step <= v[None, :] * dt * (1 + 1e-9))                # continuous, never faster than v
    assert x.min() >= lay.xmin - 1e-9 and x.max() <= lay.xmax + 1e-9
    half = lay.street_width / 2.0
    on_road = np.abs(x) < lay.xmax - 1e-6                              # away from the turn at the ends
    for u in range(x.shape[1]):
        yy = y[on_road[:, u], u]
        east = np.cos(th[on_road[:, u], u]) > 0.5
        assert np.all(yy[east] < 0) and np.all(yy[~east] > 0)          # eastbound south, westbound north
        lanes = {int(np.argmin(np.abs(lay.ys - val))) for val in yy}
        assert len(lanes) <= 2                                         # one lane per direction
        assert np.all(np.min(np.abs(yy[:, None] - lay.ys[None, :]), axis=1) <= half + 1e-9)
    # 120 s at >= 70 km/h cover more than the 2000 m road: some vehicle has turned at an end
    assert np.any(np.cos(th[1:]) * np.cos(th[:-1]) < -0.5) or np.any(np.abs(np.sin(th)) > 0.5)


def test_highway_profiles_and_groups():
    assert {"hwy", "hwy70", "hwy140"} <= set(PROFILES)
    _, _, (_, _, v, _) = _world({"mobility.profile": "hwy70"})
    assert np.all(np.abs(v * 3.6 - 70) <= 7 + 1e-9)
    sc = _old().with_overrides(
        dict(SHORT, **{"mobility.groups": [{"share": 1.0, "v_min": 25.0, "v_max": 25.0, "lateral_m": [0, 9]}]}))
    lay = make_layout(sc.layout)
    x, y, v, _ = trajectories(lay, sc.mobility, 30.0, sc.protocol.step_s, np.random.default_rng(1))
    assert np.all(v == 25.0)
    assert np.all(np.min(np.abs(y[..., None] - lay.ys), axis=-1) <= lay.street_width / 2 + 1e-9)


def test_highway_runs_with_invariants():
    sc = _old().with_overrides(SHORT)
    res = hl.simulate(sc, [{"rule": "a3"}, {"rule": "cho"}], seeds=[1], debug=True)
    again = hl.simulate(sc, [{"rule": "a3"}, {"rule": "cho"}], seeds=[1])
    assert [r.metrics for r in res] == [r.metrics for r in again]
    assert res[0].metrics["handovers_pm"] > 0


def test_late_keys_are_left_out_at_their_default():
    d = Scenario().to_dict()
    for section, keys in LATE_KEYS.items():
        assert not set(keys) & set(d[section])
        assert set(keys) <= set(Scenario().to_dict(full=True)[section])
    sc = Scenario().with_overrides({"layout.kind": "highway", "layout.lanes": 2})
    assert sc.to_dict()["layout"]["lanes"] == 2 and "lane_width_m" not in sc.to_dict()["layout"]
    assert Scenario.from_dict(sc.to_dict()) == sc
    with pytest.raises(ConfigError, match="layout.lanes"):
        Scenario().with_overrides({"layout.lanes": 0})
    with pytest.raises(ConfigError, match="layout.kind"):
        Scenario().with_overrides({"layout.kind": "motorway"})


def test_sites_from_a_csv_file(tmp_path):
    p = tmp_path / "sites.csv"
    p.write_text("name,x,y\na,-100,5\nb,100.5,-5\n", encoding="utf-8")
    sc = hl.load_config({"scenario": {"layout": {"kind": "open_area", "sites_file": str(p)}}}).scenario
    assert sc.layout.sites == ((-100.0, 5.0), (100.5, -5.0))
    assert make_layout(sc.layout).n_sites == 2
    assert Scenario.from_dict(sc.to_dict()) == sc                      # the coordinates travel with the scenario
    (tmp_path / "bad.csv").write_text("x,z\n1,2\n", encoding="utf-8")
    for name, msg in (("bad.csv", "columns x and y"), ("missing.csv", "cannot read")):
        with pytest.raises(ConfigError, match=msg):
            Scenario.from_dict({"layout": {"sites_file": str(tmp_path / name)}})
