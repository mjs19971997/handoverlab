# SPDX-License-Identifier: MIT
"""A radio map from a file (radio.map_file, since 1.12.0): export, import, and a map from measured points.

Run it:  python examples/radio_map.py
1. The radio map of a smoke world is written to a file and read back: the run gives the same event log.
2. "Measurements" are taken at 2000 street points of that map with 1 dB error; a map is interpolated from
   them, and the run on it is compared with the run on the original map.
A map from a ray tracer is written the same way with handoverlab.mapfile.map_from_raster.
"""
import os
import tempfile

import numpy as np

import handoverlab as hl
from handoverlab.mapfile import export_map, map_from_points
from handoverlab.world import build_world

sc = hl.builtin_scenario("smoke")
rules = [{"rule": "a3", "name": "A3", "off_db": 3.0, "ttt_s": 0.16}]
tmp = tempfile.mkdtemp(prefix="handoverlab_map_")
world = build_world(sc, 1)
path = export_map(world.radio_map, os.path.join(tmp, "smoke_seed1.npz"))
a = hl.simulate(sc, rules, seeds=[1])[0]
b = hl.simulate(sc.with_overrides({"radio.map_file": path}), rules, seeds=[1])[0]
print("exported map: %.1f MB, same event log: %s" % (os.path.getsize(path) / 1e6, a.fingerprint == b.fingerprint))

rm, lay = world.radio_map, world.layout
rng = np.random.default_rng(2)
x, y = rng.uniform(lay.xmin, lay.xmax, 20000), rng.uniform(lay.ymin, lay.ymax, 20000)
keep = lay.street_mask(x, y)
x, y = x[keep][:2000], y[keep][:2000]
gain = rm.lookup(x, y).astype(float) + rng.normal(0.0, 1.0, (len(x), lay.n_sites))
area = (rm.x0, rm.x0 + (rm.nx - 1) * rm.res, rm.y0, rm.y0 + (rm.ny - 1) * rm.res)
mpath, err = map_from_points(os.path.join(tmp, "measured.npz"), x, y, gain, lay.sites, area, res=2.0)
c = hl.simulate(sc.with_overrides({"radio.map_file": mpath}), rules, seeds=[1])[0]
print("interpolated map: hold-out RMSE %.2f dB on %d points" % (err["rmse_db"], err["n_holdout"]))
print("handovers per UE-minute: original %.2f, interpolated %.2f" % (a.metrics["handovers_pm"],
                                                                     c.metrics["handovers_pm"]))
