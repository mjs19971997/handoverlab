# How to study a high-speed train in FR2

Since 2.3.0 the built-in card [`hst-fr2-28ghz`](../scenarios/hst-fr2-28ghz.md) follows the FR2
high-speed train deployment of TR 38.854 V18.0.0 as its system-level mobility study sets it up
(Table 6.3.8.1-1, Scenario-A, unidirectional RRHs, without DPS):

| | TR 38.854 | Card |
|---|---|---|
| Track and RRHs | one train on one straight track, RRHs on one side, Ds 700 m, Dmin 10 m, 12 sites (Tables 5.1-1, 5.2-1, 6.3.8.1-1) | highway layout with one track, 12 sites 700 m apart at 10 m, wrap-around |
| RRH | 15 m, 31 dBm, panel [1, 1, 8, 8, 2], one SSB beam into the boresight, the panel pointing at the track where the next site is | one sector, one SSB beam, 8 x 8 panel, azimuth 180.82 deg, zenith 90.82 deg |
| CPE | 5 m, panel [1, 1, 4, 4, 2] of 5 dBi elements pointing to the RRHs, 350 km/h | one gain of 17.04 dB, 97.22 m/s |
| Carrier, channel | 28 GHz, 50 MHz, 120 kHz, TR 38.901 RMa LOS only, one CPE, no inter-cell interference, DL full buffer | the same, no background load |
| Handover, RLM | A3 3 dB, TTT 80 ms, SMTC 20 ms, measurement period 480 ms (N = 8), N310 = N311 = 2, Qout / Qin -8 / -6 dB, 600 / 300 ms | rule `{a3, off_db: 3, ttt_s: 0.08}`, TS 38.133 periods, the same RLM values |

Each RRH is its own cell ("each BBU has only one RRH", TR 38.854 clause 6.3.4.1), so the train hands
over at every RRH: about every Ds / v = 700 m / 97.2 m/s = 7.2 s.

## 1. Run it in both directions

All RRHs of the card point west. A train going east travels towards the serving beams (the
"opposite direction" of the TR: train east, RRHs west), a train going west away from them ("same
direction"). The card has one train per run and draws its direction from the seed; pointing the
RRHs east on the same seeds gives the other direction on the same trajectories:

```yaml
# hst.yaml
schema: 1
scenario: hst-fr2-28ghz
seeds: {first: 1, last: 20}
rules:
  - {rule: a3, off_db: 3.0, ttt_s: 0.08}
output: results/hst-west.csv
```

and a second file `hst-east.yaml` with the RRHs pointing east (`359.18 = -atan(10 / 700)` degrees):

```yaml
schema: 1
scenario: {base: hst-fr2-28ghz, radio: {beams: {sector_az0_deg: 359.18}}}
seeds: {first: 1, last: 20}
rules:
  - {rule: a3, off_db: 3.0, ttt_s: 0.08}
output: results/hst-east.csv
```

```bash
handoverlab run hst.yaml
handoverlab run hst-east.yaml
```

Scenario-B (Dmin 150 m) is an override: `layout.site_offset_m: 149.98` and the beams aimed again.

## 2. What the TR describes, and what HandoverLab gives

Criteria fixed before the runs (pre-registered); 40 seeds x 2 RRH orientations, 100 s measured per run
(4000 CPE-seconds per direction), rule A3 3 dB / 80 ms. The TR's values are read from its bar charts
(Figures 6.3.4.1.1.1-1 to -4, legacy requirements, uni-directional Scenario-A without DPS).

| | Same direction: TR / HandoverLab | Opposite direction: TR / HandoverLab |
|---|---|---|
| Handovers per CPE-second, no DRX | 0.152 / 0.139 | 0.150 / 0.145 |
| Time of stay in a cell [s] | 6.54 / 7.22 | 6.66 / 6.92 |
| Ping-pong handovers [%] | 3.95 / 0.0 | 3.36 / 0.35 |
| Mobility failures (RLF + HOF) [% of handovers and failures] | 0 / 0 | 2.1 / 0 |
| Time below Qout or interrupted [% of time] | about 0.7 / 0.55 | 1.8 / 2.4 |

| Check | Result |
|---|---|
| H1: received power from the serving RRH >= -50 dBm along its stretch (TR 6.3.3.1.1) | **fail as registered**: from 43 m to 700 m in front of the RRH it is -45.8 dBm or more, but within 10-42 m of the RRH it drops to -115 dBm, in the vertical null of the 8-element column (the CPE passes 10 m below the beam's tilt). The TR's statement does not cover the area under the RRH. |
| H2: handovers per CPE-second in [0.125, 0.181] in both directions | pass (0.139 same, 0.145 opposite) |
| H3: no failure in the same direction | pass (0 in 40 runs) |
| H4: with DRX-40 periods, failures only in the opposite direction | **fail**: no failure in either direction. The emulation registered for it (`rx_sweep_n: 24`) did not lengthen the L3 measurement period, which in TS 38.133 Table 9.2.5.2-2 is ceil(M_meas) T_SMTC with M_meas = 24 already containing N = 8; the runs were identical to those without DRX except for the RLM windows. |

Exploratory, after that finding (not pass/fail): the DRX-40 period of 1440 ms through
`protocol.ssb_period_s: 0.06` with the RLM windows of 3.6 / 1.8 s, 20 seeds per orientation:
still no failure in either direction. With the element back lobe removed as in the TR's mobility study
(`radio.beams.am_db: 100`), the opposite direction spends 28.8 % of the time below Qout (same
direction 0.6 %; TR at DRX 40: 40.3 % and about 0.7 %), but none of it ends in a radio-link failure:
radio-link monitoring averages the linear SINR over 3.6 s, and the strong signal before the RRH keeps
that average above Qout. With the 480 ms measurement period of no DRX, removing the back lobe raises the opposite direction's
time below Qout from 2.4 % to 8.6 %, again without failure.

What this means for a study with the card:

- The geometry, link budget and handover rhythm follow the TR: one handover per RRH, about 7 s apart,
  and the asymmetry of the two directions shows in the time below Qout.
- The failure side of the TR's result (2.1 % without DRX, about 70 % at DRX 40 in the opposite
  direction) is not reproduced. Two simplifications are the likely reason (not tested one by one): the CPE has one gain towards all RRHs
  (in the TR the CPE panel faces the serving RRHs, so the source RRH falls behind the panel once the
  CPE passes it), and radio-link monitoring is a smoothed SINR threshold, not the BLER of a hypothetical PDCCH.
  Use the card for handover timing, rates and outage; do not read absolute failure rates from it.

## 3. Limits

- One gain for the CPE towards every RRH: the RRHs behind the CPE get the same gain as those in front,
  which overstates the received power right after the CPE passes an RRH.
- The RRH element has the back lobe of TR 38.901 Table 7.3-1 (A_m 30 dB, as TR 38.854 Table 6.1.1.1);
  the TR's mobility study used "an antenna model without back lobe" (clause 6.3.4.1.3).
  `radio.beams.am_db` raises A_m.
- No DRX, DPS / SFN, multi-TRP, Doppler or fast fading, uplink timing, tunnels or cell-detection delay.
- Radio-link monitoring on the SSB link quality with the CSI-RS evaluation periods of the TR as time
  constants.
