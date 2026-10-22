# Failure-model calibration against ns-3 / 5G-LENA

The radio model itself is calibrated against 3GPP (TR 38.901 clause 7.8.1, the 21 companies of
R1-165974); see [radio calibration against 3GPP](calibration-3gpp.md). This page is about the
failure model, which no 3GPP calibration covers.

**Fresh hold-out D (1.9.0).** 48 new ns-3 runs on conditions never used before (12 and 20 m/s)
were compared with the 1.3.0 configuration fixed in advance: handover and unnecessary-handover
rates agree (median ratios 0.93 and 0.95, ranks 0.97), and the failure level agrees too (ratio
0.84, limit 0.67-1.5), but the order of the failure rates does not (rank 0.68, limit 0.8). See
[standard compliance](standard-compliance.md#fresh-ns-3-hold-out-190).

**Held-out check of the failure-model parts (2.2.0).** 40 new ns-3 runs (seeds 201-210, urban,
20 users, A3 3 dB / 300 ms, ISD 200 and 400 m at 16 m/s, light traffic and 12 Mbit/s full traffic)
tested each part of the failure model against limits fixed before the runs, with the 2.0.0 engine as
registered (2.1.0 defaults gave the same verdicts):

| Part | ns-3 | HandoverLab | Limit | Result |
|---|---|---|---|---|
| Load: link-monitoring SINR, light to full traffic | -2.1 / -1.8 dB | -13.3 / -13.4 dB | within 2 dB | fails |
| Execution: command to completion | median 4.1 ms | `exec_s` 10 ms | within 10 ms | passes |
| Recovery: time without connection per failure | 0.09 s | 1.0 s (`reest_s`) | ratio 0.67-1.5 | fails |
| Execution failures | none in any cell | 0-5 % | needs 10 in ns-3 | not measurable |

ns-3's full traffic is an overload too (more than a cell can carry), so both simulators fill the
cells; the difference is what link monitoring sees. In ns-3 its SINR hardly moves with the data
load; in HandoverLab it follows the data load by default (ns-3 has fewer failures at full traffic,
90 to 34 and 13 to 3; HandoverLab many more, 18 to 521 and 4 to 175). TS 38.133 V19.6.0 clause 8.1
evaluates the link on a hypothetical PDCCH, and the neighbours' control channels and reference
signals are sent whatever the data load; `protocol.lm_load` gives link monitoring such a fixed
interferer load.

On recovery, the standard does not fix one value: TS 38.133 V19.6.0 clause 6.2.1.2.1 bounds the
re-establishment delay by 50 ms + T_identify_intra_NR (known FR1 cell: max(200 ms, 5 T_SMTC), Table
6.2.1.2.1-1) + T_SI-NR + T_PRACH (at most the SSB-to-PRACH association period + 10 ms, TS 38.213
Table 8.1-1), followed by RRCReestablishment processing of 10 ms (TS 38.331 V19.4.0 Table 12.1-1).
That is about 0.28 s when the system information is already held and about 1.55 s with the T_SI of
1280 ms of the test case A.6.3.2.1.1.2. HandoverLab's `reest_s` of 1.0 s lies inside; ns-3 (ideal
RRC) takes 0.09 s, below both. The recovery time was therefore not changed towards ns-3.

**Fresh held-out check N3 (2.3.0).** One setting was chosen on the light-traffic N2 cells above
(`protocol.lm_load` 0.15, with `protocol.exec_can_fail` false, as ns-3 has ideal execution) and
tested on 40 new ns-3 runs (seeds 301-305, ISD 200 / 400 m, 12 / 24 m/s, TTT 100 / 640 ms, light
traffic), with limits fixed before the runs:

| Check | Limit | Fixed link-monitoring load 0.15 | Default link monitoring |
|---|---|---|---|
| Failure level, sum HandoverLab / sum ns-3 | 0.67-1.5 | 0.47, fails | 0.16, fails |
| Failure order over the 8 cells (Spearman) | at least 0.8 | 0.95, passes | 0.78, fails |
| Handover rate, median ratio | 0.8-1.25 | 0.93, passes | 0.96, passes |
| Direction of the TTT effect on failures | 3 of 4 | 4, passes | 4, passes |

At TTT 100 ms the fixed load gives ns-3's failure counts (17 against 14, 11 against 10); at
TTT 640 ms it gives about half of them (84 against 180, 68 against 193), the known effect of ns-3's
slow out-of-sync detection (below). As fixed in advance, the setting is not adopted because the
level check fails; it is reported here, and no further tuning was done on these runs.

**Summary (1.5.0).** Handover and unnecessary-handover rates of HandoverLab agree with ns-3 /
5G-LENA. For failure rates, the order of settings and conditions agrees on part A and on both
hold-out sets when the in-car loss of ns-3 and the restart of link monitoring are switched on
(version 1.3.0 below), but the absolute values do not. Three causes were found in the ns-3 code
and diagnosis runs:

| Cause | ns-3 | TS / TR text | HandoverLab |
|---|---|---|---|
| In-car penetration loss | added only at 30-120 km/h | TR 38.901 7.4.3.2: a property of a user in a car | per user when configured, any speed (`radio.penetration_db`) |
| Time to detect out-of-sync | 20 frames of 10 control receptions; 0.65-0.83 s at light traffic | TS 38.133 8.1: about 200 ms | evaluated over time (`protocol.qout_window_s` 0.2 s) |
| Link monitoring on a new cell | restarts | TS 38.331: T310 stops at a handover; out-of-sync evaluated anew (an interpretation of TS 38.133 8.1.2.2: quality over the last T_Evaluate_out) | option since 1.3.0 (`protocol.rlm_holdoff_s`) |

On the first two, HandoverLab is closer to the 3GPP texts; on the third, ns-3 was, and HandoverLab
now offers it. The sections below give the evidence in the order it was found.

**Result of version 0.4.0a1: no calibrated preset is offered, and the default failure model is
unchanged.** One existing parameter, the Qout filter window `protocol.qout_window_s`, can be set so
that HandoverLab reproduces the mean failure rate of the ns-3 reference and its ranking over the 24
A3 settings. The same setting fails on every independent set of ns-3 results that was held back, so
it is a fit to one data set and not a calibration. This page gives the evidence. Failure rates of
HandoverLab therefore remain relative quantities, as stated in the
[verification](verification.md#validation-the-known-difference-in-failure-rates) page: compare them
between rules within HandoverLab, not with absolute values from another simulator.

The work used only stored ns-3 / 5G-LENA output files (per-run attempt and link-failure tables and
summaries of the study behind the scenario [`ns3-urban-3.5ghz`](scenarios/ns3-urban-3.5ghz.md));
ns-3 was not run again. HandoverLab used seeds 500 and 501 per condition; seeds are different
realisations in the two simulators, so only averages are compared.

## What the ns-3 failures are

The ns-3 runs used N310 = N311 = 1, T310 = 1 s, Qout = -8 dB, 50 ms preparation, 1 ms slots, ideal
RRC and random access, the TR 36.839 handover-failure model, and 10 downlink packets per second per
user.

- **Almost all are late handovers.** Of 1268 failures in part A (0.432 per UE-minute), 96 % are
  handover commands that arrive while T310 runs; 2 % are T310 expiries and 2 % connection
  time-outs. The median time since the last successful handover is 12.4 s (under 1 s for 6 % of
  failures): these are not early handovers or ping-pongs.
- **Strong dependence on the time-to-trigger.** 0.031, 0.140, 0.436 and 1.119 failures per
  UE-minute at a TTT of 100, 300, 500 and 1000 ms (36-fold). When the late command arrived, T310 had
  been running for a median 299 ms (64 ms at TTT 100 ms, 419 ms at 1000 ms).
- **Part B** (two settings, six conditions, 20 seeds each): 0.035 (1 dB / 300 ms) and 0.031
  (6 dB / 100 ms) per UE-minute; 0.077-0.100 at 200 m with 16 or 30 m/s, at most 0.014 elsewhere.
- **Further A3 runs** (6 dB / 100 ms, 200 m, 16 m/s, 10 seeds): 0.075 per UE-minute; T310 of 0.5 or
  2 s gives 0.092 and 0.087 (no effect); a preparation delay of 20 or 100 ms gives 0.072 and 0.107;
  10 or 40 users give 0.045 and 0.159, so the failure rate depends on the traffic.

**The SINR gap is a matter of definition.** The mean serving SINR reported by the ns-3 study
(11.5 dB) is computed from the RSRP of all cells with every other cell interfering. HandoverLab's
SINR with fully loaded interferers matches it within 0.5 dB; its usual SINR (26 dB in this
scenario) counts the interferers at their actual, light load. Neither number is what the ns-3
failure detection sees: ns-3 checks Qout on the control symbols of the serving cell, where
neighbours interfere only in the slots in which they send control information, so the interference
seen by link monitoring depends on the traffic.

## Parameters tried

All on part A (24 A3 settings x 4 conditions); failures per UE-minute against ns-3's 0.432; rank:
Spearman correlation of the failure rate over the 24 settings.

| Change to the scenario card | Failures | Rank | Failures at TTT 100 / 300 / 500 / 1000 ms |
|---|---|---|---|
| none (interferer load 0.03, `qout_window_s` 0.2 s) | 0.126 | 0.54 | 0.065 / 0.078 / 0.090 / 0.271 |
| interferer load 0.1 / 0.3 / 1.0 | 0.48 / 1.40 / 3.55 | 0.78 / 0.90 / -0.30 | trend flattens; unnecessary-handover ratio 0.73 and 0.28 at 0.3 and 1.0 (outside the limits) |
| load 0.05-0.2 with `qout_window_s` 0.05-0.1 s | 0.71-2.43 | 0.93 to -0.38 | too many failures |
| `qout_window_s` 0.08 / 0.10 / 0.11 / 0.12 / 0.13 / 0.15 s | 0.58 / 0.49 / 0.43 / 0.37 / 0.31 / 0.23 | 0.88 / 0.94 / 0.95 / 0.96 / 0.94 / 0.85 | at 0.12 s: 0.067 / 0.146 / 0.504 / 0.749 |
| `qout_window_s` 0.1 s and Qout -9 dB (Qin -7 dB) | 0.40 | 0.96 | 0.040 / 0.219 / 0.632 / 0.713 |
| `qout_window_s` 0.1 s and `qin_window_s` 0.05 / 0.2 s | 0.48 / 0.18 | 0.90 / 0.78 | |
| prototype: count consecutive out-of-sync steps instead of filtering, window 0.2-0.6 s | 0.12-0.60 | 0.79-0.95 | no better than the filter window |

The failure rate is steep in the window (0.49 at 0.10 s, 0.23 at 0.15 s). Handover and
unnecessary-handover rates stayed within the acceptance limits for every window setting.

## The best candidate and the hold-out test

`protocol.qout_window_s: 0.12` (or 0.11) and nothing else changed, two seeds per condition:

| | Window 0.11 s | Window 0.12 s | Scenario card (0.2 s) | ns-3 |
|---|---|---|---|---|
| Part A failures per UE-minute | 0.405 | 0.352 | 0.131 | 0.432 |
| Part A rank over the 24 settings | 0.97 | 0.97 | 0.67 | |
| Part A failures at TTT 100 / 300 / 500 / 1000 ms | 0.074 / 0.228 / 0.579 / 0.738 | 0.072 / 0.163 / 0.464 / 0.711 | 0.066 / 0.078 / 0.097 / 0.281 | 0.031 / 0.140 / 0.436 / 1.119 |
| Part A handover ratio / rank | 0.91 / 0.99 | 0.92 / 0.99 | 0.92 / 0.99 | |
| Part A unnecessary-handover ratio / rank | 0.93 / 0.99 | 0.94 / 0.99 | 0.97 / 0.99 | |
| **Hold-out** part B failures (4 seeds) | 0.115 | 0.097 | 0.068 | 0.033 |
| **Hold-out** part B rank over 12 cells | 0.73 | 0.69 | 0.70 | |

On part A the window fits the level (also per condition: 0.32 / 0.57 / 0.20 / 0.33 against
0.70 / 0.52 / 0.20 / 0.32 at 200 m / 16 m/s, 200 / 30, 400 / 16, 400 / 30) and the ranking, but the
time-to-trigger trend is about 10-fold against ns-3's 36-fold. On the held-back results it fails:

- **Part B** is three times too high, and its ranking is no better than with the scenario card.
  In the worst cell (200 m, 30 m/s, 1 dB / 300 ms: 0.53 against 0.085) 64 % of HandoverLab's
  failures are execution failures (the target is below Qout at the end of the execution), which
  ns-3 with ideal random access practically does not produce. Leaving them out as a diagnostic
  still gives 0.052 against 0.033, rank 0.66.
- **The further A3 runs** (8 seeds): 0.022 against 0.075. A T310 of 0.5 or 2 s changes nothing in
  either simulator (this agrees). A preparation delay from 20 to 100 ms raises HandoverLab's failures
  5-fold (0.009 to 0.044) and ns-3's 1.5-fold (0.072 to 0.107). 10 or 40 users give 0.056 and 0.034
  in HandoverLab (no trend) against a 3.5-fold rise in ns-3: HandoverLab's fixed interferer load
  cannot respond to the traffic.

## Conclusion and what would be needed

A single parameter fits part A because it can shift the level of late failures, but it does not
capture what drives the ns-3 failures: interference at link monitoring that depends on the traffic
of the neighbours, and an execution step that practically never fails. A calibrated preset would
need, at least, a link-monitoring SINR with its own, traffic-dependent interferer load (the way
`traffic.label_load` sets the load for the outcome label), and an option for an execution that
cannot fail, each checked against the held-back results above. Both change results, so they will
come with a new model version, and only if the hold-out sets confirm them.

Reproduce the part-A numbers with the comparison of `handoverlab verify --ns3`:

```python
from handoverlab.verify.ns3 import compare

out = compare(seeds=[500, 501], overrides={"protocol.qout_window_s": 0.12})   # about 6 min on one core
print(out["summary"]["fail_mean"], out["summary"]["fail_rank"], out["summary"]["ho_ratio_median"])
```

Part B is stored with the reference data (`handoverlab/verify/data/ns3_urban_a3.json`, means over
20 runs per cell); the further A3 runs are not stored in the package, their means are given above.

## Version 1.1.0: a link-monitoring model

Version 1.1.0 adds the two pieces named above as options; with their defaults the model of 1.0 is
unchanged:

- `protocol.lm_load` and `protocol.lm_load_per_ue`: link monitoring (the Qout / Qin filters)
  counts each interfering cell with its own load, `lm_load + lm_load_per_ue x` (users served by
  that cell), at most 1, instead of the load of the data channel. This follows the traffic: a cell
  sends control information for each user it serves.
- `protocol.exec_can_fail: false`: the execution always joins the target, like the ideal random
  access of the ns-3 runs.

The held-back ns-3 results are now stored with the reference data and compared by
`handoverlab.verify.ns3.holdout`: part B (two settings on six conditions, 20 runs each) and part C
(the setting 6 dB / 100 ms with one parameter changed per cell: 10, 40 or 60 users, a preparation
delay of 20 or 100 ms, T310 of 0.5 or 2 s, a site distance of 300 m, 600 s runs, 3 or 42 m/s;
20 cells of 10 runs each).

**Acceptance limits, fixed before any tuning** (`FAIL_LIMITS` in `verify/ns3.py`):

| | Limit |
|---|---|
| Part A: mean failure rate, HandoverLab / ns-3 | 0.8 to 1.25 |
| Part A: rank correlation over the 24 settings | at least 0.9 |
| Part A: failure rate at TTT 1000 ms over TTT 100 ms | at least 20 (ns-3: 36) |
| Part B and part C, each: mean failure rate, HandoverLab / ns-3 | 0.67 to 1.5 |
| Part B and part C, each: rank correlation over the cells | at least 0.8 |
| Handover and unnecessary-handover rates of part A | the limits of `verify --ns3` still hold |

Tuning uses part A only; parts B and C are run once with the chosen values. A scenario card with
the calibrated values is published only if every limit holds.

### Result of version 1.1.0: no calibrated preset

Tuning on part A (two seeds per condition, `exec_can_fail: false`, `lm_load: 0`):

| `qout_window_s` | `lm_load_per_ue` | Failures (ns-3: 0.432) | Rank | TTT trend (ns-3: 36) |
|---|---|---|---|---|
| 0.2 | 0.01 / 0.02 / 0.03 / 0.05 / 0.08 | 0.09 / 0.19 / 0.30 / 0.51 / 0.81 | 0.68 / 0.85 / 0.93 / 0.90 / 0.94 | 8.5 / 8.0 / 6.9 / 4.9 / 3.7 |
| 0.12 | 0.005 / 0.009 / 0.011 / 0.015 / 0.025 | 0.16 / 0.26 / 0.31 / 0.40 / 0.62 | 0.96 / 0.96 / 0.96 / 0.96 / 0.96 | 30.9 / 18.9 / 19.2 / 12.6 / 7.8 |
| 0.1 | 0.005 / 0.007 / 0.009 / 0.015 / 0.025 | 0.22 / 0.29 / 0.35 / 0.53 / 0.80 | 0.97 / 0.96 / 0.96 / 0.94 / 0.90 | 31.0 / 21.1 / 17.1 / 9.4 / 4.8 |
| 0.08 | 0.004 / 0.006 | 0.23 / 0.32 | 0.96 / 0.97 | 25.7 / 17.4 |

With the model, almost all failures are handover commands that arrive while T310 runs, as in
ns-3 (with the default model a large share were execution failures). The ranking over the 24
settings is good (0.96), and the handover and unnecessary-handover rates stay within their limits
(median ratios 0.92 and 0.95). But no setting meets the level and the time-to-trigger trend
together: where the mean reaches 0.8 of ns-3, the trend is about 17-fold. The longest
time-to-trigger saturates near one failure per UE-minute, while the shortest one keeps a floor.

The closest point (`qout_window_s` 0.1 s, `lm_load_per_ue` 0.009) was run once on the hold-out
sets (four seeds per cell), next to the default model:

| | Calibration candidate | Default model | ns-3 |
|---|---|---|---|
| Part B failures per UE-minute (ratio) | 0.076 (2.29) | 0.068 (2.07) | 0.033 |
| Part B rank over 12 cells | 0.62 | 0.70 | |
| Part C failures per UE-minute (ratio) | 0.036 (0.98) | 0.027 (0.72) | 0.037 |
| Part C rank over 20 cells | 0.39 | 0.47 | |

It fails the limits on both sets. Some parts of it do work. The failure rate now rises with the
traffic, as in ns-3: 10 / 40 users at 200 m give 0.000 / 0.209 against ns-3's 0.045 / 0.159, where
the default model gives 0.013 / 0.034. A longer preparation delay raises it, and T310 has no effect
in either simulator. What fails: at 42 m/s HandoverLab gives 0.14 against 0.003, and part B stays
twice too high. So the per-user load explains the traffic dependence but not the speed dependence.
The ns-3 failures depend on more than this model has, probably the slot-level timing of control
information and of the handover command. The options stay in the package for experiments, the
defaults are unchanged, and failure rates remain relative quantities. A third attempt should start
from the speed dependence of parts B and C, not from part A.

**The speed dependence (checked after 1.1.0).** At 200 m and 6 dB / 100 ms, ns-3 gives 0.000 /
0.075 / 0.080 / 0.003 failures per UE-minute at 8 / 16 / 30 / 42 m/s: a peak at medium speed,
falling to almost none at 42 m/s. HandoverLab's failures rise with the speed (calibration candidate:
0.000 / 0.013 / 0.119 / 0.138), as expected when the signals change faster against a fixed
time-to-trigger and fixed delays. One explanation was tested: ns-3 starts T310 only after 200 ms
of control SINR continuously below Qout (20 blocks of 10 slots, any good block resets the count),
which a fast user may cross in less time. HandoverLab can count in the same way (`qout_window_s`
and `qin_window_s` 0.001 s, `n310` 20 and `n311` 10 steps of 10 ms). It does not help: the
failures rise even more steeply with the speed (0.075 / 0.20 / 0.40 / 0.50 with `lm_load_per_ue`
0.01), and on part A the time-to-trigger trend falls to about 3. The cause of the ns-3 drop at
42 m/s is therefore in what ns-3 models differently at high speed, which needs new ns-3 runs with
link-monitoring traces.

### Version 1.2.0: the cause of the speed dependence is an in-car loss in ns-3

ns-3 (`ThreeGppPropagationLossModel`, function `GetO2iVehicularLoss`) adds the in-car penetration
loss of TR 38.901 clause 7.4.3.2 to every link of a user that moves at 30 to 120 km/h: a normal
draw with 9 dB mean and 5 dB standard deviation, once per user, kept for the whole run. Below
30 km/h and above 120 km/h it adds nothing. So 16, 24 and 30 m/s (58-108 km/h) have the loss, while
8 m/s (28.8 km/h) and 36 and 42 m/s (130 and 151 km/h) do not.

Diagnosis runs of ns-3 wrote each reported RSRP next to the deterministic path loss of the same
3GPP model at the user's position. At the same position, cell and LOS state, the loss at 16-30 m/s
is 8.7 dB higher than at 8 m/s (7.5-8.8 dB, depending on which users are present), and at
36 and 42 m/s it is identical to 8 m/s. RSRP plus path loss is the same at every speed, so the
RSRP measurement itself is correct. The loss lowers every link of a user alike: it leaves the
signal-to-interference ratio unchanged but lowers the signal-to-noise ratio. At light load the
link monitoring of ns-3 is close to noise-limited, and its late-handover failures happen at serving
RSRP of -133 to -142 dBm. This explains the drop at 8 and 42 m/s. Part A (16 and 30 m/s) has the
loss throughout; part B at 8 m/s and part C at 3 and 42 m/s do not.

HandoverLab 1.2.0 adds the loss as an option (`radio.penetration_db`, `radio.penetration_sd_db`;
off by default). `compare(..., car=True)` and `holdout(..., car=True)` apply it the way ns-3 does
(`car_loss` in `verify/ns3.py`). No parameter was fitted for the following runs (part A two seeds,
hold-out four seeds per cell):

| HandoverLab with `car=True` | Part A failures (ns-3: 0.432) | Part A rank | TTT trend (ns-3: 36) | Part B ratio / rank | Part C ratio / rank |
|---|---|---|---|---|---|
| default failure model | 0.38 | 0.80 | 2.0 | 6.3 / 0.83 | 3.1 / 0.69 |
| `exec_can_fail: false` | 0.31 | 0.89 | 2.6 | 4.4 / 0.85 | 2.6 / 0.76 |
| `exec_can_fail: false`, `lm_load: 0` (link monitoring sees noise only) | 0.12 | -0.50 | 0.7 | 2.5 / 0.75 | 1.7 / 0.78 |
| as the row above, with the ns-3 out-of-sync counting | 0.26 | -0.45 | 0.5 | 5.2 / 0.78 | 4.0 / 0.79 |

Without any fitted parameter, the loss brings part A to the level of ns-3 (0.38 against 0.43;
0.13 without it). It reproduces the absence of failures at 8 and 42 m/s when link monitoring sees
noise only, and it improves the ranking on both hold-out sets. Handover and unnecessary-handover
rates stay within their limits. Two differences remain:

- The time-to-trigger trend: ns-3's failure rate grows 36-fold from 100 to 1000 ms, HandoverLab's
  by at most 2.6. HandoverLab has too many failures at short time-to-trigger.
- The level on the hold-out sets, 2.5 to 6 times that of ns-3.

Noise-only link monitoring gives the best hold-out results but reverses the time-to-trigger trend.
So the trend in ns-3 comes from the interference that link monitoring sees, which HandoverLab does
not reproduce. The limits are still not met: no calibrated preset is offered, and failure rates
remain relative quantities. Comparisons with ns-3 results should use `car=True`, because the ns-3
reference includes this loss.

### Version 1.3.0: link monitoring restarts on a new cell

The remaining failures were compared with those of ns-3, failure by failure (A3 6 dB / 100 ms at
200 m). At 42 m/s, every HandoverLab failure came about 0.2 s after a handover, at an
intersection: T310 had started on the newly joined cell at once, and the next handover command
arrived while it was running. In ns-3 radio-link monitoring restarts on a new cell and needs a full evaluation period (200 ms)
before an out-of-sync indication; HandoverLab reads TS 38.133 8.1.2.2 (quality estimated over the last
T_Evaluate_out) the same way, an interpretation, as no clause defines a restart. Overall,
half of HandoverLab's failures came less than 2 s after the previous handover, against a quarter to
a third in ns-3.

Version 1.3.0 adds the restart as an option, `protocol.rlm_holdoff_s` (off by default; 0.2 s from
TS 38.133, not fitted). With `car=True`, `exec_can_fail: false` and `rlm_holdoff_s: 0.2`:

| | HandoverLab | ns-3 | Limit | |
|---|---|---|---|---|
| Part A mean failures (two seeds) | 0.288 (ratio 0.67) | 0.432 | 0.8-1.25 | fails |
| Part A rank over the 24 settings | 0.91 | | at least 0.9 | passes |
| Part A TTT trend | 4.9 | 36 | at least 20 | fails |
| Part B failures (four seeds; ratio) | 0.133 (4.0) | 0.033 | 0.67-1.5 | fails |
| Part B rank over 12 cells | 0.86 | | at least 0.8 | passes |
| Part C failures (four seeds; ratio) | 0.084 (2.3) | 0.037 | 0.67-1.5 | fails |
| Part C rank over 20 cells | 0.82 | | at least 0.8 | passes |

The speed dependence now agrees: at 200 m, 0.000 / 0.200 / 0.256 / 0.013 failures per UE-minute at
8 / 16 / 30 / 42 m/s against ns-3's 0.005 / 0.100 / 0.077 / 0.003, and none at 3 m/s in either.
The ranking limits are met on all three sets: HandoverLab orders handover settings and conditions
by failure rate as ns-3 does, on data it was not tuned on. The absolute level and the
time-to-trigger trend are not met. HandoverLab has two to four times too many failures at short
time-to-trigger and too few at the longest one, and its failure rate does not rise with the number
of users as in ns-3 (10 / 40 users: 0.375 / 0.131 against 0.045 / 0.159). Six variants of the link
monitoring were tried on part A (noise-only, interference per served user, the ns-3 out-of-sync
counting, a shorter filter window). None improved the trend without breaking the ranking.

So the evidence now supports comparing failure rates between rules and conditions in HandoverLab
on all three sets, and still not reading them as absolute values. No calibrated preset is offered.

### Version 1.4.0: how long ns-3 takes to detect a radio problem

A further diagnosis run of ns-3 wrote the control-channel SINR that its link monitoring uses
(`NrUePhy::RlfDetection`) and its in-sync and out-of-sync indications, at 16 m/s with 10, 20 and
40 users and time-to-trigger 100 and 1000 ms. ns-3 declares out-of-sync after 20 consecutive bad
frames, each the mean SINR in dB of 10 control receptions. Its source code calls this 200 ms, which
holds for one reception per slot. In these runs a user received only 240 to 310 control channels
per second, more with more users (23 to 31 per 100 ms for 10 to 40 users). So T310 starts only
after 0.65 to 0.83 s below Qout. This explains the two remaining differences:

- **The time-to-trigger trend**: with a short time-to-trigger the handover is usually complete
  before the problem is detected; with a long one it is not.
- **The dependence on the number of users**: more users mean more control receptions and faster
  detection. At 100 ms, the failure rate was 0.000, 0.075 and 0.125 per UE-minute for 10, 20 and
  40 users.

The control SINR itself dips below Qout often (in 5 to 11 % of the 100 ms windows), but only a
long unbroken run of bad frames counts.

A test on part A used the counting mode of HandoverLab with this detection time (`n310` 77 and
`n311` 38 steps of 10 ms, `qout_window_s` and `qin_window_s` 0.001 s), together with the in-car
loss, `exec_can_fail: false` and `rlm_holdoff_s: 0.2`. Only the interferer load of link
monitoring was tuned (`lm_load_per_ue`). At 0.3 it meets every part-A limit: failures 0.455
against 0.432 (ratio 1.05), rank 0.97, a time-to-trigger trend above 20, and handover and
unnecessary-handover rates within their limits. On the hold-out sets it fails clearly: part B
0.003 against 0.033 (rank 0.57), part C 0.007 against 0.037 (rank 0.61). The hold-out cells mostly
have short time-to-trigger, where this setting gives too few failures (0.006 against 0.031 at
100 ms in part A).

The hold-out sets have now been used to judge several candidates. Tuning further against them
would fit them rather than test the model, so the calibration stops here. A new attempt needs
fresh, independent ns-3 results. The mechanism above is the starting point for one: the detection
time should follow the control traffic of each cell.

Reproduce with `compare(seeds=[500, 501], overrides=...)` and
`holdout(seeds=[500, 501, 502, 503], overrides=...)` from `handoverlab.verify.ns3`.
