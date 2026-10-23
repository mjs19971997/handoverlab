# How to study handover indoors and in rural cells

Since 1.7.0 HandoverLab has two scenario families next to the urban grid, the open area and the
highway. Both follow TR 38.901 (V19.5.0, unchanged from V17.0.0 for these parts) for geometry and propagation and the IMT-2020 evaluation
configurations of ITU-R M.2412-0 for the link budget: the indoor office with the InH-Office path
loss, and rural macro cells with the RMa path loss. They stretch a rule in opposite directions:
indoors the cells are 20 m apart and the neighbours are almost as strong as the serving cell; in
rural cells the sites are 1.7 km apart and the users drive at 120 km/h.

| Scenario | Layout | Radio | Users |
|---|---|---|---|
| [`indoor-office-4ghz`](../scenarios/indoor-office-4ghz.md) | `indoor`: hall of 120 m x 50 m, 12 ceiling sites on a 20 m grid (TR 38.901 Table 7.2-2) | `inh_office_open` at 4 GHz (open-office LOS probability of ITU-R M.2412-0 Table A1-9, since 2.1.0), 24 dBm for 20 MHz (M.2412-0 Table 5a), sites 3 m and users 1 m high, soft LOS | 20 pedestrians at 3 km/h (`p3`, since 2.1.0; `ped3` with +-10 % until 2.0.0) |
| [`rural-700mhz`](../scenarios/rural-700mhz.md) | `open_area` of 6000 m x 3500 m (`layout.area_m`), 11 sites on a 1732 m hexagonal grid, users at least 35 m from a site (Table 7.2-3) | `rma` at 700 MHz, 49 dBm for 20 MHz (M.2412-0 Table 5c), sites 35 m high, car penetration loss, soft LOS | 30 users in cars at 120 km/h (`v120`, since 2.1.0; `veh120` with +-10 % until 2.0.0) |

## 1. Run them

```yaml
# indoor.yaml
schema: 1
scenario: indoor-office-4ghz
seeds: [1, 2, 3]
rules:
  - {rule: a3, off_db: 3.0, ttt_s: 0.16}
  - {rule: cho, o_prep_db: -2.0, o_exec_db: 3.0, ttt_exec_s: 0.08}
  - {rule: a3_mro}
output: results/indoor.csv
```

```bash
handoverlab run indoor.yaml
handoverlab scenarios rural-700mhz      # the scenario card with every parameter and its source
```

`rural-700mhz` is larger: 300 s of 30 users take one to two minutes per seed on one core. For a
first look shorten it, `scenario: {base: rural-700mhz, run: {duration_s: 60.0}}`.

## 2. The models

- **InH-Office** (`radio.pathloss: inh_office`): LOS `32.4 + 17.3 log10(d3D) + 20 log10(fc)`,
  NLOS `max(LOS, 38.3 log10(d3D) + 17.30 + 24.9 log10(fc))`, for 3D distances of 1 m to 150 m,
  with the LOS probability of the mixed office (TR 38.901 Tables 7.4.1-1 and 7.4.2-1); `inh_office_open`
  (since 2.1.0) has the same path loss with the LOS probability of the open office (1 up to 5 m,
  exp(-(d2D - 5) / 70.8) up to 49 m, 0.54 exp(-(d2D - 49) / 211.7) beyond), which ITU-R M.2412-0
  Table A1-9 uses for the Indoor Hotspot.
- **RMa** (`radio.pathloss: rma`): the LOS model with its breakpoint
  `d_BP = 2 pi h_BS h_UT fc / c` and the NLOS model, both with the default street width
  W = 20 m and building height h = 5 m; LOS probability `exp(-(d2D - 10) / 1000)` beyond 10 m.
  Shadowing 4 dB on LOS links below the breakpoint, 6 dB beyond it (`radio.shadow_los_far_db`) and
  8 dB on NLOS links. The model covers 0.5-30 GHz, and HandoverLab refuses a higher carrier with
  `rma`. Table 7.4.1-1 writes PL2 = PL1(d_BP) + 40 log10(d3D / d_BP); HandoverLab evaluates PL1 at
  the 3D distance of the breakpoint, so the loss is continuous (the difference is below 0.01 dB).
- **Soft LOS state** (`radio.soft_los`): both cards use the optional soft LOS state of TR 38.901
  clause 7.6.3.3, which the standard introduces to avoid hard LOS/NLOS transitions in mobility
  simulations; see the [user guide](../user_guide.md#soft-los-state-radiosoft_los-since-170).
- **Indoor layout** (`layout.kind: indoor`): no walls are drawn; the InH LOS probability and the
  place-tied shadowing stand for walls and furniture. Users walk between random waypoints at least
  2 m from the walls.
- **Users in cars** (rural): the TR 38.901 car penetration loss of clause 7.4.3.2, 9 dB mean and
  5 dB standard deviation, drawn once per user (`radio.penetration_db`, `radio.penetration_sd_db`).
  `layout.min_site_distance_m` keeps the start and the waypoints of a user 35 m from every site.

`handoverlab verify` checks both models, both LOS probabilities and the soft LOS weight against
values computed by hand (group `pathloss`), and the golden fingerprints include short runs of
both scenarios.

## 3. What the results look like

Means over three seeds per user-minute, with the cards as they are and with the hard LOS state:

| Scenario | Rule | LOS state | Handovers | Failures | Unnecessary | Ping-pong | Interruption [s] |
|---|---|---|---|---|---|---|---|
| indoor | A3 3 dB 160 ms | soft | 3.81 | 0.00 | 0.86 | 0.02 | 0.15 |
| indoor | A3 3 dB 160 ms | hard | 3.95 | 0.00 | 0.96 | 0.05 | 0.16 |
| indoor | A3 5 dB 320 ms | soft | 2.91 | 0.02 | 0.23 | 0.00 | 0.14 |
| indoor | `a3_mro` | soft | 3.77 | 0.00 | 0.84 | 0.02 | 0.15 |
| rural | A3 3 dB 160 ms | soft | 13.07 | 0.07 | 7.58 | 1.82 | 0.67 |
| rural | A3 3 dB 160 ms | hard | 15.62 | 0.18 | 9.24 | 2.57 | 1.06 |
| rural | A3 5 dB 320 ms | soft | 8.86 | 0.21 | 4.09 | 0.45 | 0.63 |
| rural | `a3_mro` | soft | 10.56 | 0.08 | 5.51 | 0.97 | 0.56 |

- **Indoors**, about a quarter of the handovers are unnecessary even at walking speed (0.86 of 3.81
  per user-minute), because every neighbour is close; ping-pong is rare. This is the point of the
  scenario: a rule has to avoid switching between nearly equal cells. A larger offset and
  time-to-trigger cut the unnecessary handovers by about three quarters at the price of a few late
  ones (0.02 failures per user-minute, all too late, against none).
- **In rural cells**, the handover rate is far above what the cell size alone would give, and most
  handovers are unnecessary: the 8 dB shadowing with 120 m decorrelation, uncorrelated between
  sites (TR 38.901 clause 7.5 step 4; half correlated until 2.0.0), moves the best cell often at
  120 km/h. Compare rules with each other here, and do
  not read the absolute handover rate as that of a real rural network.
- **Hard against soft LOS**: with the hard switch, a link jumps by about 20 dB (RMa at 1-2 km) or
  about 15 dB (InH at 20 m) when its state changes. In rural cells these jumps raise the failures from
  0.07 to 0.18 per user-minute and the handovers by about a fifth (13.07 to 15.62); indoors there are
  no failures with either state, and the hard switch adds only a few handovers (3.81 to 3.95).
- The failure model is not calibrated in absolute terms in any scenario; read failure rates
  relative to each other.

## 4. Change them

The usual keys apply, for example a denser office or a rural carrier in the upper mid-band:

```yaml
scenario:
  base: indoor-office-4ghz
  layout: {area_m: [60.0, 40.0], site_spacing_m: 10.0}
  radio: {carrier_ghz: 28.0, bandwidth_mhz: 400.0}
```

```yaml
scenario:
  base: rural-700mhz
  layout: {site_spacing_m: 5000.0, area_m: [16000.0, 9000.0]}
  radio: {carrier_ghz: 3.5, bandwidth_mhz: 100.0, map_res_m: 20.0}
```

A larger area needs a coarser radio map (`radio.map_res_m`) to keep memory and run time in bounds.
