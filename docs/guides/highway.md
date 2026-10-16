# How to study handover on a highway

Since 1.0.0rc3 HandoverLab has a third layout next to the street grid and the open area: the
straight multi-lane road of the TR 37.885 highway case, with roadside sites and lane-keeping
vehicles at 70 to 140 km/h. The built-in scenario [`highway-10ghz`](../scenarios/highway-10ghz.md)
is a ready set-up: 2000 m of road, 3 + 3 lanes of 4 m, four sites every 500 m, 35 m beyond the
road edge, the TR 38.901 UMa model with 25 m masts.

## 1. Run the built-in scenario

```yaml
# highway.yaml
schema: 1
scenario: highway-10ghz
seeds: [1, 2, 3]
rules:
  - {rule: a3, off_db: 3.0, ttt_s: 0.16}
  - {rule: cho, o_prep_db: -2.0, o_exec_db: 3.0, ttt_exec_s: 0.08}
  - {rule: daps}
output: results/highway.csv
```

```bash
handoverlab run highway.yaml
handoverlab scenarios highway-10ghz     # the scenario card with every parameter and its source
```

## 2. Change the road, the sites and the speeds

Every part of the layout is a key of `layout`; the speeds come from `mobility`:

```yaml
scenario:
  base: highway-10ghz
  layout: {lanes: 2, lane_width_m: 3.5, road_length_m: 3000.0, site_spacing_m: 300.0, site_offset_m: 10.0}
  mobility:
    users: 60
    groups:
      - {share: 0.7, v_min: 25.0, v_max: 33.0, lateral_m: [0.0, 0.5]}   # cars, 90-120 km/h
      - {share: 0.3, v_min: 19.4, v_max: 22.2, lateral_m: [0.0, 0.3]}   # lorries, 70-80 km/h
```

- `site_offset_m` is measured from the road edge (the outermost lane line), not from the centre
  line as on the street grid. For your own site plan give `layout.sites` or a CSV file in
  `layout.sites_file` (columns `x`, `y`; the road runs along the x axis, centred on the origin).
- The named profiles `hwy` (70-140 km/h, uniform), `hwy70` (63-77 km/h) and `hwy140`
  (126-140 km/h) cover the two highway speeds of TR 37.885 and the range between them.
- `lateral_m` is the displacement from the lane centre; it is clipped to half a lane, so a vehicle
  never leaves its lane.

To compare speeds or site spacings in one study, make them conditions:

```yaml
scenario: {base: highway-10ghz}
conditions:
  mobility.profile: [hwy70, hwy140]
  layout.site_spacing_m: [300.0, 500.0]
```

## 3. What to expect and what to check

- The sites follow a line, so a vehicle sees at most two strong cells at a time and every handover
  goes to the next site along the road. Fast vehicles stay only a few seconds in the overlap zone:
  expect more `too_late_pm` with long time-to-trigger values.
- The time of stay in a cell is about `site_spacing_m / speed`: at 140 km/h and 500 m about 13 s.
  Keep `run.duration_s` long enough for several handovers per vehicle (the default 120 s gives
  about eight after the warm-up at 140 km/h).
- At the end of the road a vehicle turns into the same lane of the other direction instead of a
  wrap-around; handovers at the outermost sites therefore include turning vehicles. For metrics
  that should exclude them, use a longer road than the area of interest.
- As everywhere, compare failure rates between rules and conditions, not as absolute values.
