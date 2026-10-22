# Urban macro, suburban macro and indoor users

Since 2.3.0 HandoverLab has three more pieces of the 3GPP evaluation scenarios:

| Scenario | Layout | Radio | Users |
|---|---|---|---|
| [`urban-macro-tr37885-4ghz`](../scenarios/urban-macro-tr37885-4ghz.md) | the TR 37.885 urban grid (3 x 3 blocks of 433 m x 250 m) with 35 macro sites of a 500 m hexagonal lattice (TR 36.885 Figure A.1.3-1) | UMa at 4 GHz, 49 dBm, 20 MHz, sites 25 m high above the rooftops: the LOS state comes from the UMa LOS probability, not from the buildings; effective environment height 0.25 m (TR 37.885 clause 6.2.1) | vehicles at 60 km/h in the lanes of TR 37.885 (`v60`) |
| [`suburban-sma-7ghz`](../scenarios/suburban-sma-7ghz.md) | `open_area` of 4500 m x 2625 m, 11 sites on a 1299 m grid, users at least 35 m from a site | SMa at 7 GHz, 49 dBm, 20 MHz (TR 38.901 V19.5.0 Tables 7.2-5 and 7.8-1A) | 80 % indoors at 3 km/h with the O2I loss of the low-loss A model, 20 % in cars at 40 km/h with the car loss |

## 1. Run them

```yaml
# suburban.yaml
schema: 1
scenario: suburban-sma-7ghz
seeds: [1, 2, 3]
rules:
  - {rule: a3, off_db: 3.0, ttt_s: 0.16}
  - {rule: cho, o_prep_db: -2.0, o_exec_db: 3.0, ttt_exec_s: 0.08}
output: results/suburban.csv
```

```bash
handoverlab run suburban.yaml
handoverlab scenarios urban-macro-tr37885-4ghz      # the card with every parameter and its source
```

## 2. The models

- **SMa** (`radio.pathloss: sma`, TR 38.901 V19.5.0 Table 7.4.1-1, 0.5-37 GHz): LOS
  `PL1 = 20 log10(40 pi d3D fc / 3) + min(0.03 h^1.72, 10) log10(d3D) - min(0.044 h^1.72, 14.77) + 0.002 log10(h) d3D`
  below the breakpoint `d_BP = 2 pi h_BS h_UT fc / c`, `PL2 = PL1(d_BP) + 40 log10(d3D / d_BP)` from it on;
  NLOS `161.04 - 7.1 log10(W) + 7.5 log10(h) - (24.37 - 3.7 (h / h_BS)^2) log10(h_BS) + (43.42 - 3.1 log10(h_BS))
  (log10(d3D) - 3) + 20 log10(fc) - (3.2 (log10(11.75 h_UT))^2 - 4.97)` with h = 10 m and W = 10 m. The SMa row of
  the table has no max() with the LOS loss, unlike RMa, UMa and UMi; HandoverLab uses it as printed, so for a
  UT high above the ground close to a site the NLOS loss can be below the LOS loss (up to 9 dB at 10 m for
  h_UT = 13.5 m). Shadowing 4 dB (LOS below d_BP), 6 dB (LOS beyond), 8 dB (NLOS). LOS probability (Table
  7.4.2-1): 1 up to 10 m, then the product of a commercial (20 m high, 2 %), a residential (8 m, 18 %) and a
  vegetation term (15 m, `radio.vegetation` 0, 0.1 or 0.2) with the clutter size 30 m.
- **O2I building penetration** (TR 38.901 clause 7.4.3.1): give a speed group `indoor: true`. Each user of that
  group gets, once, `PL_tw + 0.5 d2D-in + N(0, sigma_P^2)` on all its links: `PL_tw` from Eq. (7.4-3) with the
  wall of `radio.o2i_model` (Table 7.4.3-2: `low` 30 % glass and 70 % concrete, sigma_P 4.4 dB; `high` 70 % IRR
  glass and 30 % concrete, 6.5 dB; `low_a` 30 % glass and 70 % plywood, 4.4 dB, SMa only; `mixed` low or high
  with probability 1/2) and the material losses of Table 7.4.3-1 (the IRR glass of Release 19, 25.4 + 0.11 f);
  `d2D-in` the minimum of two uniform variables up to 25 m (UMa, UMi, SMa commercial) or 10 m (RMa, SMa
  residential; SMa buildings are 90 % residential), or up to `radio.o2i_d_in_max_m`. An indoor user gets no car
  loss (`radio.penetration_db` then applies to the other users only).

```yaml
scenario:
  base: urban-grid-10ghz
  radio: {pathloss: uma, bs_height_m: 25.0, o2i_model: mixed}
  mobility:
    groups:
      - {share: 0.8, v_min: 0.8333, v_max: 0.8333, indoor: true}     # TR 38.901 Table 7.2-1: 80 % indoor
      - {share: 0.2, v_min: 16.67, v_max: 16.67, lanes_m: [1.75, 5.25]}
```

- **Sites above the rooftops** (`radio.building_los: false`, street grid only): every link is first taken as clear
  and the spatially consistent LOS state of TR 38.901 clause 7.6.3.3 decides LOS or NLOS with the LOS probability
  of the path-loss model (TR 37.885 clause 6.2.1 for the urban base-station-to-vehicle links). With the default
  `true` a link through a building block is NLOS, as for small cells on the pavement.
- **Effective environment height** (`radio.env_height_m`, UMa and UMi): one h_E for the breakpoint distance
  `d'_BP = 4 (h_BS - h_E)(h_UT - h_E) fc / c` of every link; TR 37.885 clause 6.2.1 sets 0.25 m, which moves the
  UMa breakpoint at 4 GHz from 768 m to 1782 m for a 1.6 m vehicle antenna.

## 3. What is abstracted

- An indoor user keeps the LOS state, the breakpoint distance and the shadowing of its own position. TR 38.901
  takes the LOS probability at the outdoor distance d2D-out, the path loss at d3D-out + d3D-in and an O2I
  shadowing of 7 dB (UMa, UMi) or 8 dB (SMa). `handoverlab verify --only scenarios` (S4) measures what this
  changes in the coupling gain of the SMa card.
- All users share one UT height; the floors of Tables 7.2-1 and 7.2-5 are not modelled.
- The urban macro card has no wrap-around: the vehicles drive on 3 x 3 blocks and every lattice site within
  1000 m of them is simulated. The position of the lattice relative to the blocks is read from TR 36.885 Figure
  A.1.3-1, which has no numbers.
- The 7 GHz large-scale calibration of TR 38.901 clause 7.8.1 (Table 7.8-1A) was not part of 2.3.0; since 2.4.0
  it is checked against the companies of R1-2506406 with a sectorised, wrapped SMa drop
  ([radio calibration](../calibration-3gpp.md)).

## 4. Checks

`handoverlab verify --only scenarios` (optional group, about 30 minutes) runs the criteria that were fixed
before the first run; see [verification](../verification.md). The registered run of 2.3.0 gave 7 passes and
3 failures, reported as they came:

- pass: the card values against the TRs; the 500 m lattice (nearest neighbours 499.989 m, every street point
  within 288.5 m of a site); the LOS share of the map with the sites above the rooftops (0.034 against the mean
  probability 0.039); the SMa path loss and LOS probability against a separate write-out of the formulas (exact);
  the O2I loss moments of every model (at most 1.5 standard errors); the O2I loss on every link of an indoor user;
- fail: the coupling gain to the strongest site of the urban macro card lies 0.3-1.2 dB below an independent
  computation around the median in every block of seeds (limit 0.5 dB). The LOS share close to the sites is a
  little below the probability (100-150 m: 0.23 against 0.26 over 8 seeds); the cause is not found yet;
- fail: the coupling gain of the outdoor SMa users, +1.17 dB at the 20 % point (limit 0.5 dB); this is sampling
  noise of the check (the sign changes between blocks of seeds; over 40 seeds +0.1 to +0.5 dB);
- fail: all SMa users against a TR-exact treatment of indoor users, 2.0 dB at the 95 % point (limit 1.0 dB;
  median within 0.1 dB): the size of the indoor abstraction of section 3. Read results of the upper tail of
  indoor users with this in mind.
