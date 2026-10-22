# How to use your own radio map (ray tracing or measurements)

Since 1.12.0 a scenario can take its radio map from a file instead of building it from the statistical
model of TR 38.901 clause 7: `radio.map_file`. For a ray-traced map this follows the deterministic part of
the map-based hybrid channel model of TR 38.901 (V19.5.0, clause 8), which creates the channel "using the
deterministic ray-tracing upon a digitized map" (clause 8.4, step 1: import of the digitized map) and then
adds random clusters (from step 4 on), which HandoverLab does not add; the TR leaves the format of the map
to the implementation and states that the model "is not calibrated and can be used per company basis".
A map from measurements (drive tests) can be read in the same format, but it is outside TR 38.901: clause 8
starts from a digitized map and ray tracing, not from measurements.

HandoverLab takes the deterministic large-scale part from the map: the **path gain** of every site at every
pixel, in dB, without transmit power and antenna gains (HandoverLab adds `radio.tx_power_dbm`,
`radio.bs_gain_db`, `radio.ue_gain_db`, or the beams of `radio.beams`). The small-scale part of clause 8 is
not modelled, as nowhere in HandoverLab. Everything else (mobility, measurements, rules, failures) works as
with the built-in maps.

## 1. Where the map comes from

| Source | Function | Notes |
|---|---|---|
| A HandoverLab street-grid world | `handoverlab.mapfile.export_map(world.radio_map, path)` | importing it again gives the same event log bit for bit (checked for every golden case on the street grid) |
| A ray tracer (path-gain or coverage map per site) | `map_from_raster(path, x0, y0, res, gain_db, sites)` | `gain_db` of shape (ny, nx, sites); pixels without a value are NaN or marked in `valid` |
| Drive-test or other measurements | `map_from_points(path, x, y, gain_db, sites, area, res)` | linear interpolation per site; returns the error on held-out points |

The sites in the file must be the sites of the scenario's layout: give them as `layout.sites` or
`layout.sites_file` (a ray-traced city usually comes with its own site list). The map must cover the layout
area: the streets on the street grid, the whole area in the open area and the indoor hall.

```python
import handoverlab as hl
from handoverlab.mapfile import export_map
from handoverlab.world import build_world

sc = hl.builtin_scenario("smoke")
export_map(build_world(sc, 1).radio_map, "smoke_seed1.npz")
res = hl.simulate(sc.with_overrides({"radio.map_file": "smoke_seed1.npz"}), [{"rule": "a3"}], seeds=[1])
```

Measurements are path gains, so subtract the transmit power and the antenna gains from measured RSRP
first. `map_from_points` leaves a share of the points out (`holdout`, 10 % by default), interpolates from
the rest and returns the error on the left-out points, then builds the map from all points:

```python
from handoverlab.mapfile import map_from_points
path, err = map_from_points("drive.npz", x, y, gain_db, sites, area=(xmin, xmax, ymin, ymax), res=2.0)
print(err)          # {'rmse_db': ..., 'mae_db': ..., 'n_holdout': ...}
```

In the check of 1.12.0 (3000 points of the `smoke` map with 1 dB measurement error) the held-out error was
3.4 dB RMSE, against 7.8 dB of NLOS shadowing that the map would otherwise have to leave unknown.

## 2. The file format

An `.npz` file with the keys listed in [the API reference](../reference/api/mapfile.md): `format`
(`"handoverlab-radiomap"`), `version` (1), the pixel grid (`x0`, `y0`, `res`), a raster `idx` that points
every pixel to a row of `gain_db` (or -1 where there is no value), `gain_db` (rows x sites, float32), the
optional `los` (rows x sites) and `sites`. A newer version is refused with a message.

When a scenario is loaded, HandoverLab stores the SHA-256 of the file in `radio.map_sha256`; it is part of
the job IDs of a study, and a run refuses a file that has changed since. Use a new file name for a new map.

## 3. What changes and what does not

- The map is static: path loss, LOS state and place-tied shadowing come from the file; the LOS process along
  the users' paths of the open area is not drawn. `radio.place_share < 1` still adds shadowing that moves
  with the user (its standard deviation from `los` if the file has it, else the NLOS value), and
  `radio.time_var_db` still adds the moving blockers.
- Not combined with `radio.layers` or `layout.wrap` in 1.12.0 (the base layer only); `radio.beams` works.
- A map from a ray tracer is only as good as the ray tracer and its digitized map; TR 38.901 publishes no
  calibration for clause 8. Report where your map comes from (`source` in the file).
