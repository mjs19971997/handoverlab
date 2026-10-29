# Comparison with real network data

This page compares HandoverLab 2.8.0 with four public drive-test and walk-test datasets of commercial LTE and
5G networks. The aim is realism: the measurements are the reference. Every quantity, scenario, setting and
pass criterion was written down and frozen before any comparison number was computed, from the data or
from the simulator. One amendment (how the time-correlation series are cut into pieces) was made after the
real numbers were known and before any simulator number; it is listed below. Nothing was tuned.

**Summary.** With the default model, the distribution of the serving NR SS-SINR is within 3 dB of the
measurements on at least two of the three percentiles (10th, 50th, 90th) on every primary row (the upper tail
is up to 6 dB higher), the preparation delay of 50 ms is inside the measured range, and the time correlation of the
SINR matches two of three datasets. HandoverLab is wrong on the urban macro card in four points:
it makes **4-10 times more serving-cell changes per km**, its **margin at the handover command is larger**,
it has **more samples of very low SINR** than Vienna, and its RSRP spread is too narrow while its **received
power is 35-40 dB higher** than the phones report (the level is reported, not judged). The execution time of 40 ms is outside the measured ranges (LTE 30-39 ms, 5G SA 64-68 ms).
An exploratory diagnosis traces most of the excess handovers to hard LOS/NLOS transitions, which TR 38.901
clause 7.6.3.3 itself describes; see the end of the page. No default was changed.

## Data

| Dataset | Network and place | What was used | Sampling | Speeds |
|---|---|---|---|---|
| Vienna 4G/5G drive test v1.0.5 [1] | 3 operators, LTE B1/B3/B7/B8/B20, NR NSA n1/n78, Vienna (Austria) | handset serving RSRP and SINR (LTE, NR operator A), serving cell id / PCI, GNSS; estimated sites | 0.5 s | 15-25 km/h urban driving |
| SIGCOMM'22 artifact [2] | US, LTE + NR NSA (n5, n260, n261), walking loops in Boston and Chicago; per-handover durations of three operators | serving and one neighbour RSRP, NR SINR, explicit handover labels; figure 8 and 9 duration files | event driven (NR SINR about 80 ms) | walking |
| DoNext Dortmund, mobile set [3] | 2 operators, LTE + NR NSA, Dortmund (Germany) | LTE `sinr`/`rsrp`, NR `ss_sinr`/`ss_rsrp`, LTE neighbour RSRP, cell id, speed | 1-15 s (median 2 s) | 15-25 and 30-50 km/h |
| UCC 5G production dataset [4] | 1 operator, LTE + NR NSA (LTE anchor values), Cork (Ireland) | `SNR`, `RSRP`, cell id, speed (driving traces) | 1 s | 30-50 km/h |

Published numbers were also checked: the highway LTE SINR fit N(10.57, 9.96) dB of [5] and the share of time
with serving RSRP above -100 dBm (80 %) in a 5G SA n78 network [6]. No public dataset contains labelled
radio link failures, so the failure model could not be checked here.

## Method

- HandoverLab: card `urban-macro-tr37885-4ghz` (UMa, 500 m hexagon, 4 GHz, 20 MHz) with every user at a
  speed of the matching class (walking 3-6 km/h, 15-25 km/h, 30-50 km/h); `urban-grid-28ghz-beams` for the
  mmWave walking data; `highway-tr37885-4ghz` for the highway SINR. Rule A3 with 3 dB offset and 256 ms
  time-to-trigger (from [6], whose 2 dB hysteresis the single offset leaves out); three fresh seeds. Variants: the default static
  link-monitoring interference (V0), the dynamic option with SSB overlap 1.0, 0.5 and 0.0, and CSI-RS
  (V1-V4), and a 3-sector antenna (sensitivity).
- The SINR compared with the phones' SINR is the link-monitoring SINR. For NR the phones report SS-SINR, whose
  interference "is measured over the resource elements carrying secondary synchronisation signals"
  (TS 38.215 clause 5.1.5), the quantity the dynamic option models with `rlm_rs_type: ssb`.
- The same observation operator is applied to both sides: the simulator is sampled on each dataset's time
  grid, clipped to the dataset's reporting range and, for the Android datasets, rounded to whole dB; cell
  changes are counted on that grid with the same gap rule; samples are taken only in the matching speed
  class.
- Amendment (made after the real numbers, before any simulator number): the decorrelation distance depends
  on the segment length because each segment's mean is removed. The speed filter cuts the real routes into
  short pieces, so the simulator series are cut into pieces with lengths drawn from the real segment lengths.

## Results (registered criteria)

| Quantity | Real | HandoverLab (default, V0) | Verdict |
|---|---|---|---|
| NR SS-SINR p10/p50/p90, Vienna n78, 15-25 km/h | 1.2 / 11.1 / 24.4 dB | -0.6 / 12.5 / 30.2 dB | pass (2 of 3 within 3 dB) |
| NR SS-SINR, DoNext, 15-25 / 30-50 km/h | 0 / 9 / 20 dB; -1 / 9 / 20 dB | 0 / 13 / 22 dB; -5 / 12 / 22 dB | pass, pass |
| LTE SINR, Vienna operators A, B, C | p50 10.0-10.6 dB | p50 12.6 dB | pass (3 of 3 rows) |
| LTE anchor SINR, DoNext and UCC | p50 2-4 dB | p50 12-13 dB | fail (3 rows) |
| RSRP spread p90-p10 (9 rows) | 27-37 dB | 12-22 dB after clipping | fail (level 35-40 dB too high, see below) |
| Serving minus strongest neighbour, median | 4 dB (DoNext); 6.6-9.4 dB (walking) | 8 dB; 9.9 dB | 1 of 4 rows pass |
| SINR decorrelation distance | 11.7 m (Vienna LTE); 51.8 m (UCC); 2.4 m (mmWave walking) | 7.7 m; 12.7 m; 2.7 m | pass, fail, pass |
| Share of samples below -8 dB, Vienna | 0.1-0.7 % | 4.6-4.7 % | fail (UCC passes, mmWave fails) |
| Serving-cell changes per km, 15-25 km/h | 5.5-8.5 | 28-37 | fail (ratio 4.3-6.3) |
| Serving-cell changes per km, 30-50 km/h | 2.2-4.0 | 17-23 | fail (ratio 4.3-10.3) |
| Handovers per km, walking (SIGCOMM'22) | 25.7 | 45.8 | pass (ratio 1.8) |
| Neighbour minus serving RSRP before the handover (walking) | median 1.4 dB | 6.9 dB at the command | fail (weak evidence) |
| Preparation (report to command), LTE / 5G SA | IQR 43-71 / 32-104 ms | 50 ms | pass |
| Execution (command to random access done), LTE / 5G SA | IQR 30-39 / 64-68 ms | 40 ms | fail |
| Highway LTE SINR [5] | mean 10.6, sd 10.0 dB | mean 18.0, sd 10.3 dB | fail |
| RSRP above -100 dBm [6] | 80 % | 100 % | fail |

Dynamic link-monitoring interference: with SSB overlap 1.0 (aligned SSBs, the option's default) or 0.5 the
SS-SINR is 4-8 dB lower at the median than with the default (1-6 dB below the measured median) and fails
the variant rule; overlap 0.0 and CSI-RS (identical by
construction) pass like the default. The measurements therefore do not support fully aligned SSB
interference as a typical case; since the default passes too, no value of `rlm_ssb_overlap` is proposed.

## Measured handover durations as parameter values

The registered rule for a failed duration check was to take the medians of one operator as values and to
check them on the others. From the per-handover durations of [2] (figure 8: report to command; figure 9:
command to the end of the random access):

| Procedure | `protocol.prep_s` | `protocol.exec_s` | Check on other operators |
|---|---|---|---|
| LTE intra-RAT handover | 0.05 (median 52 ms) | **0.035** (T-Mobile median 35 ms) | inside the AT&T (29-35 ms, at its upper edge) and Verizon (31-40 ms) interquartile ranges: pass |
| 5G SA handover (one operator, low band) | 0.05 (median 45 ms) | **0.066** (median 66 ms, IQR 64-68 ms) | not possible: only one operator has 5G SA data |

These are documented values, not defaults: set them in a scenario to study measured timings, for example
`{"protocol.exec_s": 0.066}` for a 5G SA network like the one measured. The 5G SA value is not checked on a
second network. TS 38.133 clause 6.1.1.2.2 measures the interruption from the end of the TTI that carries
the RRC command to the start of the PRACH transmission, while both the measured execution time and
`exec_s` end after the random access, so the measured values can exceed the TS 38.133 bound without
contradicting it.

## Why the urban macro card changes cell too often (exploratory)

This diagnosis was made after the registered verdicts and is not part of them.

- The shadow fading is implemented as configured: its correlation follows exp(-d/50 m).
- The cause is the LOS/NLOS state. TR 38.901 clause 7.6.3.3 sets the state by comparing a spatially
  consistent random variable with the LOS probability (correlation distance 50 m for UMa, Table 7.6.3.1-2)
  and notes that a LOS-to-NLOS transition is "a hard transition". On this card each transition changes the
  link gain by about 25 dB, the median LOS run along a route is 12 m, and 82 % of the serving-cell changes
  follow a LOS change on the source or target link within 1.5 s.
- With every link NLOS (a diagnostic run only) the decorrelation distance becomes 52 m and the rate 9 cell
  changes per km, close to the measurements. The optional soft LOS state of TR 38.901 (Eq. 7.6-18/19,
  `radio.soft_los`) helps little at 4 GHz (16 m, 34 per km); a longer LOS correlation distance (500 m) gives
  35 m and 19 per km. L1 measurement error, the L3 filter and the TS 38.133 measurement periods have no
  visible effect.

So the excess is a property of the 3GPP evaluation model as configured on this card (spatially consistent
LOS without buildings, hard transitions, omni sites), not a coding error. Real streets change LOS state
less often than a thresholded random field.

## Re-test with the LOS-state process option

TR 38.901 gives the correlation distance "for LOS state" (clause 7.6.3.3, Table 7.6.3.1-2), but by default
HandoverLab gives it to the Gaussian variable that is compared with the LOS probability, so the binary state
decorrelates faster (0.24 instead of 0.37 at 50 m, at Pr_LOS = 1/2). The optional `radio.los_process: poisson_lines`
(see the [user guide](user_guide.md#los-state-process-radiolos_process-since-290)) gives the exponential
correlation of Eq. (7.4-5) with the table's distance to the state itself. Before any number with it existed,
an amendment fixed the variants, rows and verdict rule: the option "improves" if it passes more of the ten
judged rows (cell changes per km, margin at the command, low SINR) than the default, while the SINR
distribution does not get worse. The datasets had been used in the diagnosis, so this is a re-test of a
model change, not an independent hold-out; nothing was fitted.

| Row (real) | Default | `poisson_lines` | with soft LOS too |
|---|---|---|---|
| Cell changes per km, Vienna LTE (8.5) | x4.35 fail | x2.06 fail | x2.05 fail |
| Cell changes per km, Vienna NR (5.9) | x6.29 fail | x2.98 fail | x2.97 fail |
| Cell changes per km, UCC (2.2) | x10.3 fail | x6.53 fail | x6.45 fail |
| Cell changes per km, DoNext 15-25 / 30-50 km/h (5.5 / 4.0) | x5.08 / x4.31 fail | x2.90 / x3.19 fail | x2.92 / x3.16 fail |
| Handovers per km, walking (25.7) | x1.78 pass | x0.83 pass | x0.82 pass |
| Margin at the command (1.4 dB) | 6.9 dB fail | 5.4 dB fail | 4.9 dB fail |
| Low SINR: Vienna NR / Vienna LTE / UCC | fail / fail / pass | pass / fail / fail | pass / fail / fail |
| **Judged rows passed** | **2 of 10** | **2 of 10** | 2 of 10 |
| SINR distribution rows passed (guard: at least 6 of 9) | 6 | 4 (fails) | 6 |

Registered verdict: **no improvement**. Every failing quantity moves towards the measurements: the excess
of cell changes halves, HandoverLab's own share of unnecessary handovers falls from 0.40-0.49 to
0.23-0.31, ping-pongs fall 3-4 times and failures 4-7 times, and the SINR decorrelation distance doubles.
But the cell-change rate is still 2-6.5 times the measured one, the margin is still 4 dB too large, and with
fewer deep fades the SINR rises by 1-3 dB at the 10th percentile, which costs two LTE SINR rows and the UCC
low-SINR row. The LOS process explains part of the gap; the rest (sector
antennas and irregular sites, operator offsets and filters, multi-carrier networks) is open; the next
section tests the first two. The option
stays off by default.

## Re-test with sector antennas and published A3 settings

A second amendment, again fixed before any number existed, tested the two other named differences with
existing keys only (see [Settings closer to deployed networks](user_guide.md#settings-closer-to-deployed-networks-documented-values-not-defaults)):
**S**, the sector antennas of TR 38.901 Table 7.8-1 (3 sectors, (10, 1, 1) elements of Table 7.3-1, downtilt
102 degrees, one SSB beam per sector); **O**, the published LTE setting (a3-Offset 3 dB + hysteresis 1 dB,
Deng et al. IMC 2018 [7]); **N**, the published NR setting (Off + Hys 8 dB, time-to-trigger 640 ms,
Ghoshal et al. [8], a preprint); each alone and with the LOS-state process **L**. The L3 filter stays at k = 4,
the TS 38.331 default, and the cell individual offset at 0 dB: no measured value of either is published.
Rows, criteria and verdict rule are those of the previous section; nothing was fitted.

| Variant | Judged rows passed (of 10) | SINR rows (guard: 6 of 9) | Verdict | Cell changes / measured | Margin (1.4 dB) | Failures per UE-minute, 30-50 km/h |
|---|---|---|---|---|---|---|
| Default | 2 | 6 | | x1.8-10.3 | 6.9 dB | 1.13 |
| L | 2 | 4 | no improvement | x0.8-6.5 | 5.4 dB | 0.26 |
| O / OL | 2 / 3 | 6 / 4 | no improvement | x1.7-9.7 / x0.8-6.1 | 8.0 / 6.7 dB | 1.07 / 0.28 |
| N / NL | 1 / 4 | 2 / 4 | no improvement | x1.2-5.5 / x0.5-4.3 | 10.5 / 9.6 dB | 3.24 / 2.55 |
| S / SL | 3 / **6** | 6 / 6 | improves | x0.9-5.4 / x0.5-4.2 | 3.9 / 3.7 dB | 5.11 / 3.14 |
| SO / SOL | 3 / 5 | 6 / 6 | improves | x0.8-5.1 / x0.5-4.0 | 4.9 / 4.7 dB | 5.23 / 3.37 |
| SN / SNL | 5 / 4 | 5 / 6 | no improvement / improves | x0.6-4.2 / x0.4-3.4 | 9.4 / 9.2 dB | 6.06 / 4.72 |

The registered verdict is **improves** for the sector antennas (S, SL, SO, SOL, SNL); the best is S with the
LOS process (SL, 6 of 10: cell changes per km now pass on Vienna LTE, Vienna NR and DoNext at 15-25 km/h, low SINR on both
Vienna rows; the RSRP spread passes on every row). The published A3 settings alone do not help: the larger
threshold leaves the cell changes almost unchanged (O) or cuts them only at the price of more failures and
deeper low SINR (N), and it widens the margin at the command, which fails for every variant (best 3.7 dB
against 1.4 dB measured).

The verdict needs a caveat that the registered rows do not see. With sector antennas HandoverLab's failure
rate rises 3-7 times (for S, SO, SN and SNL more than one failure per handover at 15-50 km/h), and a part of the cell changes that
now match the measurements are re-establishments after a failure, not handovers. An exploratory run (one
seed, not judged) traces this to beam failure detection: with one wide SSB beam per sector the SSB of the
serving beam often falls below Qout_LR at the sector edges (13.6 beam failures per UE-minute), and failed
recoveries become radio link failures; with `radio.beams.bfd: false` the failures fall from 3.0 to 0.84 per
UE-minute and the handovers double. Public data label no failures, so this cannot be checked against the
measurements. The sector setting is therefore documented, not recommended: it brings the cell-change rate
and the RSRP spread close to the data, but the failure model with one beam per sector is not validated.
Nothing becomes a default. The next section removes the cause.

## Re-test with several SSB beams per sector, or without beam failure recovery

A third amendment, fixed before any number existed, tested two standard configurations that remove the
cause, and added a check the judged rows do not see: the failures per km at 15-25 km/h and at 30-50 km/h
must not exceed twice the default's (1.48 and 1.70 per km). **M**: three sectors with 8 SSB beams each on an
(8, 8) panel (TS 38.213 clause 4.1 allows 8 SS/PBCH blocks at 4 GHz; TR 38.802 Table A.2.5-2 takes (8, 8)
elements as the 4 GHz baseline), the serving beam following the best reported beam and beam failure detection
on the serving beam's SSB (TS 38.213 clause 6 takes, without configured resources, the periodic CSI-RS of the
PDCCH TCI state; HandoverLab uses the serving SSB beam in its place). **B**: no beam failure recovery configured, which TS 38.321
clause 5.17 allows ("may be configured"); a weak link then fails through radio link monitoring. Rows,
criteria and verdict rule as before, with the failure check added.

| Variant | Judged rows passed (of 10) | SINR rows (guard: 6 of 9) | Failures per km, 15-25 / 30-50 km/h (limit 2.96 / 3.40) | Verdict |
|---|---|---|---|---|
| Default | 2 | 6 | 1.48 / 1.70 | |
| M / with LOS process | 2 / 2 | 0 / 0 | 4.60 / 2.62 (fails); 1.54 / 1.11 | no improvement |
| S without recovery / with LOS process | 3 / **4** | 6 / 6 | 2.55 / 1.77; **1.38 / 1.26** | **improves** |
| M without recovery / with LOS process | 1 / 2 | 0 / 0 | 0.38 / 0.56; 0.04 / 0.13 | no improvement |
| For comparison: S / SL with recovery (previous section) | 3 / 6 | 6 / 6 | 9.64 / 7.68; 4.32 / 4.72 (fail) | |

Eight narrow beams per sector do not help: with the full array gain of 64 elements the SINR rises well above
the measurements (10th percentile about 6-8 dB instead of about 0 dB), so every SINR row fails, and at
15-25 km/h beam failure detection still triples the failures. The sector antennas of Table 7.8-1 without
beam failure recovery pass the check: with the LOS process (SLB) they pass 4 of 10 rows (cell changes per km
on Vienna LTE, Vienna NR and DoNext at 15-25 km/h, and the walking handover rate), keep the SINR rows, fail
less often than the default (1.38 and 1.26 per km), and pass the RSRP spread on all nine rows. Not improved:
UCC (still about 4 times too many cell changes), the low-SINR rows (without the LOS process the UCC row passes as with the
default, with it none), and the margin at the command (3.9 dB against 1.4 dB measured). Walking users, which the check leaves out because the default
has almost no failures there (0.03 per km), fail more often: 4.25 per km without the LOS process and 1.12 with
it. This is the most consistent
setting found, but it is a re-test on data used before, and the failure level is not calibrated by any public
data. It is documented in the [user guide](user_guide.md#settings-closer-to-deployed-networks-documented-values-not-defaults);
nothing becomes a default.

## Re-test with the SS-SINR of the SSB

With eight beams per sector the link-monitoring SINR lay about 6 dB above the measured SS-SINR. In the code,
link monitoring and beam failure detection of beam cells saw the serving beam over the data-channel
interference: each neighbour at its load and through the mean gain of its beams. TS 38.215 clause 5.1.5
measures the SS-SINR interference on the resource elements carrying the SSS, which in a synchronous network
(TS 38.213 clause 4.1 gives every cell of a band the same candidate SS/PBCH block positions; aligned frames and
the same transmitted SSBs are assumed) meet the neighbours' SSBs of the same
index, sent whatever the load. The new option `radio.beams.ssb_sinr: ssb` (off by default; see the
[user guide](user_guide.md#beams-and-several-carriers-since-1100)) models that. A fourth amendment, fixed
before any number, re-ran the A4 settings with it (Q), with the same rows, guard and failure check. An
independent code review before the release found that after a handover the option still restarted link
monitoring from the data-channel SINR; this was fixed and the amendment's runs were repeated with the fixed
code (the table shows the repeated runs; no verdict, pass count, guard or check changed).

| Variant | Judged rows passed (of 10) | SINR rows (guard) | Failures per km, 15-25 / 30-50 km/h (limit 2.96 / 3.40) | Verdict |
|---|---|---|---|---|
| Default | 2 | 6 | 1.48 / 1.70 | |
| 8 beams + Q / with LOS process | 2 / 2 | 0 / 0 | 3.17 / 2.12 (fails); 1.18 / 1.12 | no improvement |
| 8 beams + Q without recovery / with LOS process | 1 / 2 | 0 / 0 | 0.68 / 0.71; 0.22 / 0.19 | no improvement |
| Table 7.8-1 sectors + Q without recovery | 3 | 6 | 3.96 / 2.69 (fails) | no improvement |
| Table 7.8-1 sectors + Q without recovery, with LOS process | **5** | 6 | 2.12 / 1.99 | **improves** |

The diagnosed cause was only half right. With one beam per sector the SS-SINR model lowers the SINR by about
2 dB, as expected (the neighbours' SSBs are sent at full power). With eight narrow beams it does not lower it:
the neighbours' SSBs of the same index point in their own directions and rarely at the user, so the median
SS-SINR even rises by 1-2 dB, and the 10th percentile stays about 4-7 dB above the measurements. **The 8-beam
setting therefore remains about 6 dB optimistic, and the cause is open.** The most likely cause is the gain
of the SSB beams themselves (8 beams on an (8, 8) panel give each SSB the full array gain of 64 elements,
while the measured SS-SINR fits a wide sector beam), but no variant with wider SSB beams was run, so this is
not tested. Which SSB beam widths the operators use is not public, and no beam width was fitted to the data.
The next section tests the likely cause (2.10.0).

Among the settings that pass the failure check, the best is the Table 7.8-1 sectors with the SS-SINR model,
without beam failure recovery and with the LOS-state process (a sensitivity variant of the amendment; its
primary 8-beam variants gave no improvement): 5 of 10 judged rows (cell changes per km on Vienna LTE, Vienna NR and DoNext at
15-25 km/h, the walking handover rate, low SINR on UCC), the SINR rows kept, the RSRP spread on all nine rows,
and failures at 15-50 km/h 1.4 and 1.2 times the default's (2.12 and 1.99 per km; walking users 2.1 per km
against 0.03). Still
not matched: UCC (4.1 times the measured cell changes), DoNext at 30-50 km/h (2.1 times), the low-SINR rows of
Vienna, and the margin at the command (3.8 dB against 1.4 dB). This is a re-test on data used before; nothing
becomes a default.

## Re-test with the 2.10.0 options

HandoverLab 2.10.0 adds three options and documents one use of existing keys, all built from the 3GPP texts and
off by default: **a**, the angular spread of the departure power at the SSB beams
(`radio.beams.angular_spread: tr38901`, TR 38.901 clause 7.5; see the
[user guide](user_guide.md#angular-spread-at-the-beams-radiobeamsangular_spread-since-2100)); **b**, the
L1 measurement periods of TS 38.133 with the L3 filter of TS 38.331 (`protocol.meas_periods: ts38133`; the new
`protocol.meas_detail: 3gpp` fixes two deviations of that path found by an audit, see the
[user guide](user_guide.md#measurement-detail-of-the-ts-38133-periods-protocolmeas_detail-since-2100));
**c**, the in-vehicle penetration loss of TR 38.901 clause 7.4.3.2 (`radio.penetration_db: 9`,
`penetration_sd_db: 5`) for the driving classes; **d**, blockage model A of TR 38.901 clause 7.6.4.1
(`radio.blockage: a`, [user guide](user_guide.md#blockage-model-a-radioblockage-since-2100)) on the FR2 walking
card. Before any number with them existed, further registered amendments fixed the variants, the rows, the
verdict rule ("improves": more judged rows than the reference, the SINR guard holds -- all 3 primary NR rows
and at least 6 of the 9 SINR rows -- and the failure check passes) and the rule for a combined proposal.
References: the default (2 of 10) and, for "SLBQ + X", SLBQ, the best 2.9.0 setting (Table 7.8-1 sectors **S**,
LOS-state process **L**, no beam failure recovery **B**, SS-SINR **Q**; 5 of 10). Card `urban-macro-tr37885-4ghz`
with the 10 judged rows, except d: card `urban-grid-28ghz-beams`, walking, 3 rows (the SIGCOMM'22 FR2 SINR, its
decorrelation distance and its low-SINR share).

| Setting | Judged rows passed | SINR guard | Failures per km, 15-25 / 30-50 km/h | Ping-pong share, 15-25 / 30-50 km/h | Unnecessary-handover share, 15-25 / 30-50 km/h | Cell changes per km, 15-25 / 30-50 km/h | Verdict |
|---|---|---|---|---|---|---|---|
| Default (2.9.0) | 2 of 10 | holds | 1.48 / 1.70 (walking 0.03) | 0.077 / 0.108 | 0.40 / 0.49 | 36.2 / 25.0 | baseline |
| SLBQ (best 2.9.0 setting) | 5 of 10 | holds | 2.12 / 1.99 (walking 2.14) | 0.009 / 0.018 | 0.12 / 0.19 | 8.3 / 7.3 | reference |
| a. 8 SSB beams + Q + angular spread (MAQ) | 1 of 10 | fails | 11.14 / 7.39 | 0.056 / 0.089 | 0.29 / 0.37 | 21.8 / 16.5 | no improvement |
| a. MAQ + LOS-state process (MAQL) | 4 of 10 | fails | 3.67 / 3.47 (check fails) | 0.011 / 0.029 | 0.19 / 0.25 | 12.6 / 11.1 | no improvement |
| a. SLBQ + angular spread | 3 of 10 | fails | 3.12 / 2.86 (check fails) | 0.007 / 0.023 | 0.10 / 0.15 | 9.0 / 7.8 | no improvement |
| b. TS 38.133 periods and L3 filter (T) | 1 of 10 | fails | 2.84 / 2.66 | 0.050 / 0.072 | 0.38 / 0.46 | 33.7 / 23.4 | no improvement |
| b. SLBQ + T | 5 of 10 | holds | 3.09 / 2.77 (check fails) | 0.002 / 0.009 | 0.12 / 0.18 | 7.3 / 6.5 | no improvement |
| c. Car loss 9 dB, sd 5 dB (C) | 2 of 10 (same rows) | holds | 1.48 / 1.70 | 0.077 / 0.108 | 0.40 / 0.49 | 36.2 / 25.0 | no change |
| c. SLBQ + C | 5 of 10 (same rows) | holds | 2.13 / 2.01 | 0.009 / 0.018 | 0.12 / 0.19 | 8.3 / 7.3 | no change |
| d. FR2 body blockage, without / with angular spread (FK / FAK), walking | 1 of 3 (card alone: 1 of 3) | - | 0.00 / 0.00 | 0.004 / 0.000 (card alone 0.001) | 0.23 / 0.16 (card alone 0.22) | 50.5 / 43.8 (card alone 47.6) | no improvement |
| Combination: SLBQ + A3 offset 4 dB | 5 of 10 | holds | 2.69 / 2.34 | 0.005 / 0.018 | 0.10 / 0.17 | 7.0 / 6.3 | ties SLBQ, more failures |

(Row d: the four KPI columns hold the walking values of FK / FAK, not the two speed classes.)

Verdicts per option:

- **a. Angular spread.** No improvement. The explicit clause 7.5 procedure gives a median loss of the best beam
  of 5.85 dB for the (8, 8) panel in UMa NLOS (0.4 dB in LOS; the (10, 1) sector panel 3.8 dB in NLOS): the
  missing angular spread is about the size of the 8-beam optimism of 2.9.0, its likely cause. The option lowers the median of the
  primary NR SS-SINR rows by 5.2 dB (the registered "at least 3 dB" holds) and the DoNext SS-SINR rows pass,
  but the failures rise 4-8 times with 8 beams, the Vienna NR row stays about 3 dB optimistic, and with the
  SLBQ world it loses 2 rows and fails the failure check; the registered cause test is therefore "not
  confirmed". It also fails its own model check: against a Monte Carlo of the explicit procedure the median
  differences are -0.53 to +0.06 dB, but only 67-86 % of the points lie within 1.5 dB (90 % required).
- **b. L1/L3 filtering.** No improvement. The audit found the default chain matching TS 38.331 5.5.3.2; the
  two deviations of the `ts38133` path (F_0 = M_1, per-beam averaging before the consolidation) are fixed
  behind `meas_detail: 3gpp`, which changes no number of these settings (the first acts inside the warm-up,
  the second needs more than one SSB beam per cell), so the runs used the code before the fix. The ping-pong
  share falls by about a third, the failures per km rise 1.6-1.9 times (inside the limit; with SLBQ the limit
  is broken), and T loses the UCC low-SINR row and the guard.
- **c. In-vehicle penetration loss.** Faithful (exactly the text, one draw per user on all links) and harmless:
  C alone gives every KPI identical to the default, SLBQ + C differs from SLBQ by 0.02 failures per km or
  less, and no judged row changes, because the network is interference-limited
  and the loss is the same on every link of a user. The received power falls by about 8.7 dB (Vienna NR
  SS-RSRP median 44.4 dB above the measured one becomes 35.7 dB; reported, not judged). Mean 20 dB
  (metallized windows) at 30-50 km/h changes no row either.
- **d. Blockage model A.** No improvement. The LOS ray follows the text, the diffuse power uses the expected
  arrival spectrum, not per-cluster blocking. A per-link check works as intended: about 37 % of the LOS links lose more than 3 dB (median loss of those about 16 dB). The serving SINR moves only about 0.4 dB (-0.4 dB at the 10th and 50th percentiles),
  because the user is served by an unblocked cell and the interferers are blocked as often. Failures stay at 0;
  ping-pongs rise slightly. Landscape mode gives the same verdict.

The registered selection rule finds no option that improves, and the cause test is not confirmed, so the
combined candidates are SLBQ and SLBQ with the published LTE A3 offset (4 dB): both pass 5 of 10 rows, and
SLBQ wins on the lower failure sum at 15-50 km/h (4.11 against 5.03 per km). **The proposal keeps the 2.9.0
setting SLBQ; no 2.10.0 option joins it, and nothing becomes a default.** SLBQ has its own price: walking users
fail 2.14 times per km instead of 0.03 (not in the registered check).

Gaps that remain:

- **Multi-beam SINR about 6 dB optimistic.** Likely cause: no angular spread in the beam gain (the explicit
  TR 38.901 7.5 procedure gives a 5.85 dB median best-beam loss); the registered cause test was not confirmed
  (the option lowers the SINR by about 5 dB but raises the failures). A faithful fix would need the beams
  applied to the per-ray channel of clause 7.5, not to an expected gain.
- **FR2 about 6 dB optimistic** against the SIGCOMM'22 walking data (median serving SINR 21.2 dB against
  15.2 dB; 20.8 dB with blockage, 19.0 dB with blockage and angular spread).
- The margin at the handover command (SLBQ 3.8 dB against 1.4 dB measured) and the UCC cell-change rate.
- Open limits, not changed: the CHO / LTM report time-to-trigger and the condEventA3 leaving condition of
  `cho_d2` (evaluated at measurement instants; no separate hysteresis), and the indoor-user deviations of
  the O2I model (outdoor shadowing instead of the O2I values of Table 7.5-6, the LOS probability at the total
  instead of the outdoor distance, one shadowing field shared with outdoor users, no Table 7.4.3-3 model below
  6 GHz, no spatially consistent indoor distance).

**No hold-out.** Every dataset was used before (the earlier sections); the selection uses the same data as the
verdicts. These are re-tests of model changes, not independent validations, and nothing was fitted.

## Limits

- Real deployments differ from the card: sectorised irregular sites (nearest-site distance about 400-600 m),
  0.8-3.7 GHz on several carriers, unknown load, unknown operator settings (offsets, time-to-trigger,
  filters), phones inside cars. Cell-change counts in the data include inter-frequency changes.
- The card's link budget (omni 26.1 dBi, 6 dBi vehicle antenna, no car penetration loss) explains the high
  received power; the per-RE level should not be read as realistic. The car loss of TR 38.901 clause 7.4.3.2
  lowers it by about 8.7 dB (previous section).
- Phones report chipset-defined SINR (for LTE not standardised), integer and clipped, with an unknown
  averaging window. 5G in the data is NSA; HandoverLab models one NR layer.
- No radio link failures are labelled in public data; the failure level of HandoverLab remains not
  calibrated.

## References

1. Wiedner, Eller, Rupp et al., Vienna 4G/5G drive-test dataset, v1.0.5, Zenodo, doi:10.5281/zenodo.21372657
   (CC BY 4.0); Scientific Data (2026), doi:10.1038/s41597-026-08259-z.
2. Hassan, Narayanan et al., "Vivisecting Mobility Management in 5G Cellular Networks", ACM SIGCOMM 2022,
   doi:10.1145/3544216.3544217; artifact github.com/SIGCOMM22-5GMobility/artifact.
3. Schippers, Geis, Böcker, Wietfeld, DoNext - the Dortmund dataset, IEEE Transactions on Machine Learning in
   Communications and Networking (2025), doi:10.1109/TMLCN.2025.3564239.
4. Raca, Leahy, Sreenan, Quinlan, "Beyond Throughput, the Next Generation: a 5G Dataset with Channel and
   Context Metrics", ACM MMSys 2020, doi:10.1145/3339825.3394938; github.com/uccmisl/5Gdataset.
5. Farthofer, Herlich et al., IEEE Open Journal of the Communications Society (2022),
   doi:10.1109/OJCOMS.2022.3210289.
6. Narayana, Singh, Deepa, Ganti, real-world 5G mobility dataset (Chennai), arXiv:2605.12453 (2026).
7. Deng, Peng, Fida, Meng, Hu, "Mobility Support in Cellular Networks: A Measurement Study on Its
   Configurations and Implications", ACM IMC 2018 (authors' copy: www.cs.purdue.edu/homes/chunyi/pubs/imc18-deng.pdf).
8. Ghoshal, Khan, Dinh, Kong, Basit, Wang, Feng, Hu, Koutsonikolas, "Handover Configurations in Operational
   5G Networks: Diversity, Evolution, and Impact on Performance", arXiv:2511.03116 (2025, preprint).
