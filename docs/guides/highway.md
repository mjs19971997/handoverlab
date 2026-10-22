# How to study handover on a highway

HandoverLab has the straight multi-lane road of the TR 37.885 highway case next to the street grid,
the open area and the indoor hall. Since 1.11.0 two built-in scenarios follow the highway
assumptions of TR 37.885 V15.3.0 for the link between base station and vehicle:

| Card | TR 37.885 case | Sites | Carrier, link | Speed |
|---|---|---|---|---|
| [`highway-tr37885-4ghz`](../scenarios/highway-tr37885-4ghz.md) | below 6 GHz (baseline) | 2 sites on one side, 35 m away, 1732 m apart, 35 m masts (TR 36.885 A.1.3, option 1) | 4 GHz, 20 MHz, 49 dBm, RMa LOS | 140 km/h |
| [`highway-tr37885-30ghz`](../scenarios/highway-tr37885-30ghz.md) | above 6 GHz | 19 hexagonal sites x 3 sectors, ISD 500 m, 25 m masts (option 2), SSB beams of the 4 x 8 panel | 30 GHz, 200 MHz, 43 dBm, UMa LOS | 140 km/h |

Both have 3 + 3 lanes of 4 m, wrap-around (TR 37.885 Table A-1) and LOS on every base-station-to-
vehicle link (TR 37.885 clause 6.2.1 and Table 6.2.1-2). Every value and its source is on the card
pages; `handoverlab verify --only highway` checks them (section 4).

The card `highway-10ghz` of 1.0.0rc3 to 1.10.0 was deprecated in 1.11.0 and removed in 2.0.0: it combined the 35 m roadside offset of option 1 with the 500 m spacing of option 2, used
10 GHz, which TR 37.885 does not, and had neither the LOS-only links nor the wrap-around.

## 1. Run a built-in scenario

```yaml
# highway.yaml
schema: 1
scenario: highway-tr37885-4ghz
seeds: [1, 2, 3]
rules:
  - {rule: a3, off_db: 3.0, ttt_s: 0.16}
  - {rule: cho, o_prep_db: -2.0, o_exec_db: 3.0, ttt_exec_s: 0.08}
  - {rule: daps}
output: results/highway.csv
```

```bash
handoverlab run highway.yaml
handoverlab scenarios highway-tr37885-4ghz     # the scenario card with every parameter and its source
```

The 30 GHz card has 57 cells with 8 beams each and 158 vehicles; a run takes several minutes per
simulated minute. Shorten it with `mobility.users` and `run.duration_s` while you set up a study.

## 2. The keys behind the cards

| Key | Values | Meaning |
|---|---|---|
| `layout.wrap` | `false` (default), `true` | wrap-around of TR 37.885 Table A-1: a vehicle keeps its lane and direction and re-enters at the other end; distances and angles go to the nearest image of every site; the place-tied shadowing is periodic along the road |
| `layout.highway_sites` | `roadside` (default), `one_side`, `hex19` | sites alternately on both sides; all on one side (TR 36.885 Figure A.1.3-2); or the 19-site hexagonal layout with the road through the centre site along the cluster translation (Figure A.1.3-3; road length `sqrt(19) x site_spacing_m`) |
| `radio.los_model` | `probability` (default), `los` | LOS state from the LOS probability of the path-loss model, or LOS on every link (TR 37.885 Table 6.2.1-2); `los` is not available on the street grid |
| `mobility.profile` | `v140c`, `v70c` (since 2.1.0); `v140`, `v70` | every vehicle at 140 or 70 km/h (TR 37.885 clause 6.1.2, option A), on the lane centre; `v140` and `v70` add a lateral offset of up to 0.5 m in the lane, which TR 37.885 does not specify (the cards used `v140` until 2.0.0) |

With `wrap` the road length must be a whole number of site spacings (for `roadside` and
`one_side`), so that the sites repeat with the road. The older profiles `hwy` (70-140 km/h,
uniform), `hwy70` and `hwy140` remain.

The shadowing of the B2V links is that of the TR 38.901 path-loss model (TR 37.885 clause 6.2.2): log-normal
with the exponential autocorrelation of TR 38.901 Eq. (7.4-5) along the road, and uncorrelated between sites
(TR 38.901 clause 7.5 step 4; since 2.1.0, `radio.shadow_site_corr` unset). Until 2.0.0 it was half correlated
between sites, the value of TR 36.885 Table A.1.4-2, which belongs to the path-loss model of that table.

To compare speeds in one study, make them conditions:

```yaml
scenario: {base: highway-tr37885-4ghz}
conditions:
  mobility.profile: [v70c, v140c]
```

## 3. What to expect

- Below 6 GHz the sites are 1732 m apart: at 140 km/h a vehicle crosses a cell in about 45 s, so a
  run of 120 s gives about two handovers per vehicle after the warm-up (check run with the model of
  2.0.0: A3 with 3 dB and 160 ms, 1.8 handovers per user-minute, no failures).
- Above 6 GHz the road runs through the sectors of the hexagonal grid, past and under sites; with
  beams and 140 km/h there are many more handovers and beam switches (check run with the model of
  2.0.0: A3, 15 handovers and 0.85 failures per user-minute in 30 s).
- The links are LOS, so the received power changes only through distance, shadowing and the beams;
  `radio.time_var_db` (moving blockers) is 0 on both cards.
- As everywhere, compare failure rates between rules and conditions, not as absolute values.

## 4. What `verify --only highway` checks

1. The geometry and link budget of both cards equal the values of TR 37.885, TR 36.885 and
   TR 38.901 (lanes, lane width, wrap-around, spacing, offset, carrier, bandwidth, power, noise
   figure, heights, path-loss model, LOS-only links, shadowing, panel, tilt, speed).
2. With wrap-around the received power of every site is continuous where a vehicle re-enters the
   road: the largest jump there is below 0.5 dB or below the 99.9 % point of the ordinary steps (since
   2.1.0 the shadowing field has the exponential autocorrelation of TR 38.901 Eq. (7.4-5), which is not
   smooth, and the radio map has a whole number of pixels per wrap-around period).
3. The coupling gain to the strongest site (percentiles 5-95; since 2.1.0 with the shadowing drawn along each
   vehicle's path, which has the same distribution as the place-tied field but many more independent
   samples per run) agrees within 0.5 dB with an
   independent computation from the TR geometry (the hexagonal sites and their images built with
   the functions of the calibration module, in the frame of the grid), the TR 38.901 path loss and
   Gaussian shadowing, uncorrelated between sites as TR 38.901 clause 7.5 step 4 specifies.
4. Every link has the LOS path loss.

TR 37.885 publishes no calibration of the base-station-to-vehicle link (its calibration work is on
the sidelink), so check 3 confirms that the TR assumptions are implemented, not a company result.
(Until 2.0.0 check 3 took the inter-site correlation of 0.5 from the simulator, which is not a TR 38.901
assumption.)
The limitations of each card (Poisson placement of the vehicles, one panel per sector, effective
environment height) are on its page.
