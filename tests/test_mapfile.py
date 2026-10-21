# SPDX-License-Identifier: MIT
"""Radio maps from a file (radio.map_file, since 1.12.0): round trip, measurements, errors."""
import numpy as np
import pytest

import handoverlab as hl
from handoverlab.config import ConfigError
from handoverlab.mapfile import (MapFileError, export_map, file_sha256, load_map, map_from_points,
                                 map_from_raster, save_map)
from handoverlab.verify.golden import cases, load
from handoverlab.world import build_world


def test_export_and_import_give_the_same_event_log(tmp_path):
    ref = load()["cases"]
    c = cases()["smoke-3gpp"]
    w = build_world(c["scenario"], c["seed"])
    path = export_map(w.radio_map, str(tmp_path / "m.npz"))
    d = load_map(path)
    assert d["gain_db"].shape == (w.radio_map.n_pix, w.layout.n_sites) and d["los"].shape == d["gain_db"].shape
    sc = c["scenario"].with_overrides({"radio.map_file": path})
    assert sc.radio.map_sha256 == file_sha256(path) and "map_sha256" in sc.to_dict()["radio"]
    res = hl.simulate(sc, c["rules"], seeds=[c["seed"]])
    assert [r.fingerprint for r in res] == [x["fingerprint"] for x in ref["smoke-3gpp"]]
    w2 = build_world(sc, c["seed"])
    assert w2.radio_map.imported and np.array_equal(w2.radio_map.gain, w.radio_map.gain)


def test_open_area_map_from_a_raster_and_from_points(tmp_path):
    sc = hl.Scenario().with_overrides({"layout.kind": "open_area", "layout.area_m": [400.0, 300.0],
                                       "layout.site_spacing_m": 150.0, "mobility.users": 6,
                                       "run.duration_s": 20.0, "run.warmup_s": 2.0})
    lay = build_world(sc, 1).layout
    x0, y0, res = lay.xmin - 4.0, lay.ymin - 4.0, 4.0
    nx, ny = int((lay.xmax - lay.xmin + 8) / res) + 1, int((lay.ymax - lay.ymin + 8) / res) + 1
    XX, YY = np.meshgrid(x0 + np.arange(nx) * res, y0 + np.arange(ny) * res)
    d = np.hypot(XX[..., None] - lay.sites[:, 0], YY[..., None] - lay.sites[:, 1])
    g = -(32.4 + 21.0 * np.log10(np.maximum(d, 1.0)) + 20.0 * np.log10(10.0))     # a free-space-like map
    p = map_from_raster(str(tmp_path / "r.npz"), x0, y0, res, g, lay.sites, source="test")
    r = hl.simulate(sc.with_overrides({"radio.map_file": p}), [{"rule": "a3"}], seeds=[1])[0]
    assert r.metrics["ue_minutes"] > 0
    rng = np.random.default_rng(3)
    px, py = rng.uniform(lay.xmin, lay.xmax, 400), rng.uniform(lay.ymin, lay.ymax, 400)
    dd = np.hypot(px[:, None] - lay.sites[:, 0], py[:, None] - lay.sites[:, 1])
    gm = -(32.4 + 21.0 * np.log10(np.maximum(dd, 1.0)) + 20.0)
    p2, err = map_from_points(str(tmp_path / "p.npz"), px, py, gm, lay.sites, (x0, x0 + (nx - 1) * res, y0,
                                                                           y0 + (ny - 1) * res), res=res)
    assert err["n_holdout"] > 10 and err["rmse_db"] < 3.0
    assert hl.simulate(sc.with_overrides({"radio.map_file": p2}), [{"rule": "a3"}], seeds=[1])[0].n_events >= 0


def test_map_errors(tmp_path):
    sc = hl.builtin_scenario("smoke").with_overrides({"run.duration_s": 10.0, "run.warmup_s": 2.0})
    lay = build_world(sc, 1).layout
    with pytest.raises(ConfigError, match="not found"):
        sc.with_overrides({"radio.map_file": str(tmp_path / "none.npz")})
    np.savez(str(tmp_path / "x.npz"), a=np.zeros(2))
    with pytest.raises(MapFileError, match="not a HandoverLab radio map"):
        build_world(sc.with_overrides({"radio.map_file": str(tmp_path / "x.npz")}), 1)
    p = save_map(str(tmp_path / "s.npz"), 0, 0, 1, np.zeros((3, 3), dtype=np.int32), np.zeros((1, 2)), np.zeros((2, 2)))
    with pytest.raises(MapFileError, match="sites differ"):
        build_world(sc.with_overrides({"radio.map_file": p}), 1)
    p = save_map(str(tmp_path / "c.npz"), lay.xmin, lay.ymin, 1.0, np.zeros((5, 5), dtype=np.int32),
                 np.zeros((1, lay.n_sites)), lay.sites)
    with pytest.raises(MapFileError, match="covers"):
        build_world(sc.with_overrides({"radio.map_file": p}), 1)
    with pytest.raises(MapFileError, match="one column per site"):
        save_map(str(tmp_path / "e.npz"), 0, 0, 1, np.zeros((2, 2), dtype=np.int32), np.zeros((1, 3)), np.zeros((2, 2)))
    with pytest.raises(ConfigError, match="radio.map_file"):
        sc.with_overrides({"radio.map_file": p, "radio.layers": [{"name": "x", "carrier_ghz": 28.0}]})
    w = build_world(hl.Scenario().with_overrides({"layout.kind": "open_area", "run.duration_s": 5.0,
                                                  "run.warmup_s": 1.0, "mobility.users": 2}), 1)
    with pytest.raises(MapFileError, match="only the street grid"):
        export_map(w.radio_map, str(tmp_path / "o.npz"))
    good = export_map(build_world(sc, 1).radio_map, str(tmp_path / "g.npz"))
    s2 = sc.with_overrides({"radio.map_file": good})
    with open(good, "ab") as f:
        f.write(b"!")
    with pytest.raises(MapFileError, match="changed"):
        build_world(s2, 1)
    assert "map_file" not in hl.Scenario().to_dict()["radio"]
