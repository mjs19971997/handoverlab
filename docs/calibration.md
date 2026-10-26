# Failure-model calibration against ns-3 / 5G-LENA

The radio model itself is calibrated against 3GPP (TR 38.901 clause 7.8.1, the 21 companies of
R1-165974); see [radio calibration against 3GPP](calibration-3gpp.md). This page is about the
failure model, which no 3GPP calibration covers.

**Where the failure level stands (2.7.0).** The absolute failure level is **not calibrated**.
On four fresh, pre-registered sets of ns-3 / 5G-LENA runs (N3, V1, V3, V4), compared over equal run lengths
(120 s measured on both sides), the comparison setting passes the checks of level, order and handover rate on
one set (V4) and fails on the other three; the default link monitoring fails the level on all four:

| Set (time-to-trigger) | Comparison setting: level, rank | Default link monitoring: level, rank | Handover-rate ratio (C / R) |
|---|---|---|---|
| N3 (100, 640 ms) | 0.52 fails, 0.95 | 0.18 fails, 0.71 fails | 0.92 / 0.96 |
| V1 (80, 320 ms) | 1.31, 0.62 fails | 0.32 fails, 0.62 fails | 0.92 / 0.94 |
| V3 (512, 1024 ms) | 0.64 fails, 0.88 | 0.17 fails, 0.76 fails | 0.86 / 0.94 |
| V4 (128, 1280 ms) | 0.73, 0.98 | 0.27 fails, 0.95 | 0.815 / 0.90 |

The *ns-3 comparison setting* (`handoverlab.verify.ns3.COMPARISON_SETTING`: interferer load 0.15 at link
monitoring, ideal execution, with the in-car loss of ns-3) brings the level closer, to 0.5-1.3 times ns-3's
depending on the set (V4: 0.73), but it is not validated: it passes on 1 of the 4 fresh sets, and its order
of failures across cells is not reliable. The handover-rate ratio (0.815-0.96) and the direction of the
time-to-trigger effect agree in every set and row. The setting is not a default. *Corrected in 2.6.0:* 2.5.0 stated that the setting passed on V1
(level 0.97, rank 0.88; N3 0.47, defaults 0.33 and 0.16); those numbers are the registered analysis with the
wrong run length (90 s of HandoverLab against 120 s of ns-3). See the
[correction](#correction-in-260-equal-run-lengths) and the [independent validation study
(2.5.0)](#independent-validation-study-250) at the end of this page, which also tests whether the adaptive
and learning rules generalise.

The *ns-3-like setting* (2.7.0, `handoverlab.verify.ns3.NS3_LIKE_SETTING`, not a default) imitates how ns-3
detects a radio-link failure. Frozen in the code before V4 was opened, it gives on V4 a level of 1.03, order
0.93 and the TTT direction in 4 of 4 pairs, but a handover-rate ratio of 0.759 (limit 0.8), so it is **not
validated**. Its level is right at TTT 1280 ms (1.07) and far too low at 128 ms (0.03: 1 failure against 29).
See [the ns-3-like setting](#the-ns-3-like-setting-270) and [V4](#v4-the-ns-3-like-setting-on-a-fresh-set).

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
| Failure level, sum HandoverLab / sum ns-3 | 0.67-1.5 | 0.47, fails (corrected: 0.52, fails) | 0.16, fails (corrected: 0.18, fails) |
| Failure order over the 8 cells (Spearman) | at least 0.8 | 0.95, passes (corrected: 0.95, passes) | 0.78, fails (corrected: 0.71, fails) |
| Handover rate, median ratio | 0.8-1.25 | 0.93, passes (corrected: 0.92, passes) | 0.96, passes (corrected: 0.96, passes) |
| Direction of the TTT effect on failures | 3 of 4 | 4, passes (corrected: 4, passes) | 4, passes (corrected: 3, passes) |

The first numbers are the registered analysis with the wrong run length (HandoverLab 90 s measured
against 120 s in ns-3); the corrected ones use equal run lengths ([correction in
2.6.0](#correction-in-260-equal-run-lengths)). Corrected, at TTT 100 ms the fixed load gives ns-3's
failure counts (14 against 14, 10 against 10; registered 17 and 11); at TTT 640 ms it gives about half
of them (97 against 180, 71 against 193; registered 84 and 68), the known effect of ns-3's
slow out-of-sync detection (below). As fixed in advance, the setting is not adopted because the
level check fails; it is reported here, and no further tuning was done on these runs. It was
adopted as the comparison setting in 2.5.0 after V1, see
[below](#independent-validation-study-250); with equal run lengths it does not pass on V1 either
([correction in 2.6.0](#correction-in-260-equal-run-lengths)).

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

## Independent validation study (2.5.0)

A study in two parts was registered on 2026-10-24, before any of its runs, with its conditions, seeds,
criteria and decisions fixed; one amendment (2026-10-25, before any run of part V2) fixed the tuning
grids and the test procedure without changing a criterion, card, seed or selection rule. Nothing was
tuned on the study's data, and every result is reported as it came. Code: HandoverLab 2.4.2 (results
identical to 2.4.0). A third part (V3, longer time-to-trigger) was registered on 2026-10-25 before its runs, and
an amendment of the analysis (E1, equal run lengths) before any corrected result was seen; see the
[correction in 2.6.0](#correction-in-260-equal-run-lengths).

### V1: failure rate against fresh ns-3 runs

**Runs.** 40 new ns-3 / 5G-LENA runs (`benchmarks/ns3/handoverlab-ns3-a3.cc`, ns-3.48 with the
documented upstream commits, 5G-LENA v5.1 with the one documented local change, see
`benchmarks/ns3/README.md`) on conditions never used before: urban, 20 users, 180 s (60 s
discarded), light traffic, A3 3 dB, site distance 200 and 300 m, 10 and 28 m/s (both inside the
30-120 km/h range of the ns-3 in-car loss), time-to-trigger 80 and 320 ms, seeds 401-405: 8 cells of
5 runs. HandoverLab ran `verify.ns3.scenario_for(isd, v, car=True)` with seeds 401-405 in two rows
fixed in advance:

- **R** (reference): the 2.4.2 defaults with `protocol.exec_can_fail: false` (ns-3 has ideal execution);
- **C** (the N3 candidate above, not re-tuned): R with `protocol.lm_load: 0.15`.

| Row | Analysis | F1 level, sum HandoverLab / sum ns-3 (0.67-1.5) | F2 order, Spearman over the 8 cells (at least 0.8) | F3 handover rate, median ratio (0.8-1.25) | F4 TTT direction (3 of 4) |
|---|---|---|---|---|---|
| C: `lm_load` 0.15, ideal execution | registered analysis, wrong run length | 0.97, passes | 0.88, passes | 0.965, passes | 4, passes |
| C: `lm_load` 0.15, ideal execution | corrected (2.6.0), equal run lengths | 1.31, passes | **0.62, fails** | 0.92, passes | 4, passes |
| R: 2.4.2 link monitoring, ideal execution | registered analysis, wrong run length | 0.33, fails | 0.84, passes | 0.973, passes | 4, passes |
| R: 2.4.2 link monitoring, ideal execution | corrected (2.6.0), equal run lengths | 0.32, fails | 0.62, fails | 0.94, passes | 4, passes |

Failures summed over the 5 seeds per cell (site distance / speed / time-to-trigger):

| Cell | 200 m, 10 m/s, 80 ms | 200, 10, 320 | 200, 28, 80 | 200, 28, 320 | 300, 10, 80 | 300, 10, 320 | 300, 28, 80 | 300, 28, 320 | Total |
|---|---|---|---|---|---|---|---|---|---|
| ns-3 | 16 | 29 | 7 | 47 | 3 | 15 | 4 | 12 | 133 |
| HandoverLab, row C, registered (90 s measured) | 8 | 46 | 7 | 33 | 5 | 16 | 3 | 11 | 129 |
| HandoverLab, row C, corrected (120 s) | 2 | 51 | 6 | 67 | 4 | 22 | 3 | 19 | 174 |
| HandoverLab, row R, registered (90 s measured) | 6 | 12 | 2 | 13 | 3 | 6 | 0 | 2 | 44 |
| HandoverLab, row R, corrected (120 s) | 1 | 15 | 3 | 10 | 2 | 5 | 1 | 6 | 43 |

**Decision, as registered (withdrawn in 2.6.0).** In the registered analysis row C passed F1-F3 on V1, the
fresh set after N3 (on which it had failed F1), so 2.5.0 made it the documented **ns-3 comparison setting**: `handoverlab.verify.ns3.COMPARISON_SETTING`
(`{"protocol.lm_load": 0.15, "protocol.exec_can_fail": False}`), used with the in-car loss of ns-3
(`scenario_for(isd, v, car=True, comparison=True)`, `compare(..., car=True, comparison=True)`, or
`handoverlab verify --ns3 --ns3-comparison`, which adds the in-car loss itself). It is not a default:
every default, golden fingerprint and stored result is unchanged. With equal run lengths row C fails F2
on V1 (rank 0.62: cell 200 m, 10 m/s, 80 ms has 2 failures against ns-3's 16, cell 200, 28, 320 has 67
against 47), so the condition of this decision is not met: the setting and its command-line flag are kept
(the [stability policy](stability.md) keeps them within 2.x), documented as a setting that brings the
level closer (0.5-1.3 of ns-3's), **not validated**.

**Validity range (corrected in 2.6.0).** The setting passes the pre-registered checks on none of N3, V1
and V3 (in 2.7.0 it passes on the fourth fresh set, [V4](#v4-the-ns-3-like-setting-on-a-fresh-set), so on 1
of 4).
2.5.0 stated that it passed on V1 (time-to-trigger 80 and 320 ms) and failed the level on N3 (0.47); both
were the registered analysis with the wrong run length. With equal run lengths: V1 level 1.31 but rank
0.62 (fails); N3 level 0.52 (fails; TTT 640 ms cells 97 against 180, 71 against 193, 27 against 46, 48
against 80, the slow out-of-sync detection of ns-3 described in the version 1.4.0 section; TTT 100 ms
cells 14 against 14, 10 against 10, 2 against 3, 3 against 1); V3 level 0.64 (fails). The default
link-monitoring model (row R) gives 0.32 here, 0.18 on N3 and 0.17 on V3 of ns-3's failure level, and
fails the order on all three (0.62, 0.71, 0.76; registered 0.84, 0.78, 0.62).

A run of 5G-LENA without the local change is not part of V1: it aborts the run instead of producing
data, and how often it would do so cannot be measured in the optimised build (logging compiled out).

### V3: the comparison setting at long time-to-trigger

Registered on 2026-10-25 before its runs, to find up to which time-to-trigger the setting holds: 40 fresh
ns-3 runs as V1 (urban, 20 users, 180 s with 60 s discarded, light traffic, A3 3 dB), site distance 200
and 300 m, 10 and 28 m/s, time-to-trigger 512 and 1024 ms, seeds 601-605; ns-3 has 1122 failures. Rows,
seeds and criteria as V1.

| Row | Analysis | F1 level (0.67-1.5) | F2 order (at least 0.8) | F3 handover rate (0.8-1.25) | F4 TTT direction (3 of 4) |
|---|---|---|---|---|---|
| C | registered analysis, wrong run length | 0.44, fails | 0.87, passes | 0.805, passes | 4, passes |
| C | corrected (2.6.0), equal run lengths | 0.64, fails | 0.88, passes | 0.86, passes | 4, passes |
| R | registered analysis, wrong run length | 0.095, fails | 0.62, fails | 0.90, passes | 4, passes |
| R | corrected (2.6.0), equal run lengths | 0.17, fails | 0.76, fails | 0.94, passes | 4, passes |

Row C fails the level at long time-to-trigger, as on N3 at 640 ms, consistent with ns-3's slower
out-of-sync detection (0.65-0.83 s, version 1.4.0 section), which the default model does not reproduce
(the ns-3-like option of 2.7.0 imitates it); its order and the time-to-trigger direction hold. The verdict
is the same in both analyses.

### Correction in 2.6.0: equal run lengths

The ns-3 bridge of 2.6.0 ([guide](guides/ns3-bridge.md)) reproduced V1 exactly only with the HandoverLab
run length of the card. This showed an error in the analyses of N3, V1 and V3: HandoverLab ran the card's
150 s with 60 s warm-up (90 s measured), while ns-3 ran 180 s with 60 s discarded (120 s measured). F1 and
F2 compare failure counts summed over the cells, so the HandoverLab counts covered three quarters of the
ns-3 time. A corrected analysis was registered (amendment E1) before any corrected result was seen: the
HandoverLab side runs the ns-3 duration and discard (180 s, 60 s; `run_length: study` of the bridge), same
seeds, rows and criteria.

| Set | Row | F1 level, registered / corrected | F2 rank, registered / corrected | F3 handover-rate ratio, registered / corrected | F4 TTT sign, registered / corrected |
|---|---|---|---|---|---|
| N3 | C | 0.47 fails / 0.52 fails | 0.95 / 0.95 | 0.93 / 0.92 | 4 / 4 |
| N3 | R | 0.16 fails / 0.18 fails | 0.78 fails / 0.71 fails | 0.96 / 0.96 | 4 / 3 |
| V1 | C | 0.97 / 1.31 | 0.88 / **0.62 fails** | 0.965 / 0.92 | 4 / 4 |
| V1 | R | 0.33 fails / 0.32 fails | 0.84 / 0.62 fails | 0.97 / 0.94 | 4 / 4 |
| V3 | C | 0.44 fails / 0.64 fails | 0.87 / 0.88 | 0.805 / 0.86 | 4 / 4 |
| V3 | R | 0.095 fails / 0.17 fails | 0.62 fails / 0.76 fails | 0.90 / 0.94 | 4 / 4 |

The registered numbers are the registered analysis with the wrong run length; the corrected ones count.
A rate-based level (sum over the cells of the mean failures per UE-minute, HandoverLab over ns-3, not
affected by the run length) equals the corrected F1 in every set and row.

**Corrected verdict.** The comparison setting (row C) passes F1-F3 on none of N3, V1 and V3: level 0.52,
1.31 with rank 0.62, and 0.64, so it gives 0.5-1.3 times ns-3's failure level depending on the
set, and its order of failures across cells is not reliable. The defaults (row R) fail level
and order on all three (0.18 / 0.32 / 0.17). The handover-rate ratio (0.86-0.96) and the direction of the
time-to-trigger effect pass in every set and row. The absolute failure level of HandoverLab is therefore
**not calibrated**; compare failure rates between rules within HandoverLab. Not affected: the comparisons of
handover and unnecessary-handover rates (part A of the stored reference, `handoverlab verify --ns3`) and
N2, which use rates per UE-minute.

**Next (done in 2.7.0).** An "ns-3-like" option that imitates ns-3's slower out-of-sync detection (not a
default) was built from the ns-3 data already seen; see the next section. It was judged on a fresh set (V4:
site distance 200 and 400 m, 14 and 22 m/s, time-to-trigger 128 and 1280 ms, seeds 701-705), collected
before the option existed and kept unopened until the option and its settings were frozen; it is not
validated ([V4](#v4-the-ns-3-like-setting-on-a-fresh-set)).

### The ns-3-like setting (2.7.0)

`handoverlab.verify.ns3.NS3_LIKE_SETTING` imitates how ns-3 / 5G-LENA v5.1 declares a radio-link failure.
It imitates ns-3, **not 3GPP**, and it is **not a default**; every default and golden fingerprint is unchanged.
Use it with the in-car loss of ns-3: `scenario_for(isd, v, car=True, ns3_like=True)`,
`handoverlab verify --ns3 --ns3-like`, or row N of the [ns-3 bridge](guides/ns3-bridge.md)
(`handoverlab ns3 compare --ns3-like`, `ns3bridge.compare(..., setting="ns3-like")`).

**The mechanism.** Read in the code of 5G-LENA v5.1 and measured in the control-channel diagnosis of ns-3
runs already used (N2 and the 1.4.0 diagnosis):

| ns-3 / 5G-LENA v5.1 | Setting | 3GPP, as HandoverLab's default |
|---|---|---|
| out-of-sync after 200 consecutive control-channel receptions below Qout (blocks of 10; a good block restarts the count; `NrUePhy::RlfDetection`) | `protocol.ns3_oos_rx: 200` | quality over the evaluation period, at least 200 ms (TS 38.133 Table 8.1.2.2-1) |
| in-sync after 100 receptions above Qin while T310 runs | `protocol.ns3_ins_rx: 100` | at least 100 ms (same table) |
| a user receives the control channels of its cell: 206 + 16.5 n per second with n users on the cell (measured, light traffic), so 200 receptions take 0.65-0.9 s | `protocol.ns3_ctrl_hz: 206`, `protocol.ns3_ctrl_per_ue_hz: 16.5` | |
| the count restarts on every new cell | `protocol.rlm_holdoff_s: 0` (the count restarts by itself) | |
| a handover command that arrives while T310 runs fails (TR 36.839 clause 5.2.1.3, `Tr36839HandoverFailure`) | `protocol.cmd_during_t310: lost` | the command stops T310 (TS 38.331 clause 5.3.5.5.2) |
| ideal random access | `protocol.exec_can_fail: false` | |
| neighbours interfere on the control symbols only in slots in which they send control | `protocol.lm_load: 0.38` | |

In the ns-3 runs 97 % of the out-of-sync indications ended in a failure, and 96 % of the failures were a
handover command that arrived while T310 ran. The interferer load 0.38 is the one at which HandoverLab's
link-monitoring SINR has the share of time below Qout and the quantiles of the ns-3 control-channel SINR in
N2; at that load HandoverLab has fewer long periods below Qout than ns-3 (a load of 1.0 matches those).
Of these two candidates, both derived from the ns-3 control-channel SINR, 0.38 was chosen in sample, after the
in-sample rows below were seen: F1-F4 pass on 2 of the 4 seen sets against 1, pooled level 0.82 against 1.85.

**In sample, not a validation.** The values were chosen with the ns-3 sets already seen; with equal run
lengths (180 s, 60 s discarded) the setting (row N) gives:

| Set | Time-to-trigger | F1 level (0.67-1.5) | F2 order (at least 0.8) | F3 handover rate (0.8-1.25) | F4 TTT direction |
|---|---|---|---|---|---|
| N2 | 300 ms | 0.16, fails | 0.89 | 0.90 | n/a |
| N3 | 100 / 640 ms | 0.87 | 0.93 | 0.87 | 4 of 4 |
| V1 | 80 / 320 ms | 0.05, fails | 0.55, fails | 0.94 | 3 of 4 |
| V3 | 512 / 1024 ms | 0.97 | 0.90 | 0.81 | 4 of 4 |

It matches ns-3's failure level at long time-to-trigger (512-1024 ms) but gives far too few failures at
80-320 ms; with an interferer load of 1.0 the pattern turns over (the level matches at 300-320 ms and is twice
ns-3's at 512-1024 ms). So the slower detection explains the long-TTT gap, but the short-TTT failures of ns-3,
which need long periods below Qout before any neighbour is 3 dB stronger, are not reproduced.

**Not validated on V4** (next section): level 1.03 overall and 1.07 at TTT 1280 ms, but 0.03 at 128 ms,
and the handover-rate check fails (0.759). The failure level stays **not calibrated**.

### V4: the ns-3-like setting on a fresh set

Registered before the set was opened (amendment N1 of the validation plan), with the ns-3-like setting
committed to the code beforehand (commit abb8b92) and its values checked by the judging script: 40 fresh
ns-3 runs, collected before the option existed and kept unopened (urban, 20 users, light traffic, A3 3 dB,
no fading), site distance 200 and 400 m, 14 and 22 m/s, time-to-trigger 128 and 1280 ms, seeds 701-705.
Both sides run 180 s with 60 s discarded (equal run lengths). ns-3 has 897 failures: 29 in the 128 ms
cells and 868 in the 1280 ms cells. Rows R (default link monitoring, ideal execution), C
(`COMPARISON_SETTING`) and N (`NS3_LIKE_SETTING`) were run through the [ns-3 bridge](guides/ns3-bridge.md)
with the same seeds; criteria F1-F4 as V1 (TTT direction 1280 - 128 ms) and the rate-based level. Row N is
validated only if it passes all of them.

| Row | F1 level (0.67-1.5) | F2 order (at least 0.8) | F3 handover rate (0.8-1.25) | F4 TTT direction (3 of 4) | Verdict |
|---|---|---|---|---|---|
| R: default link monitoring, ideal execution | 0.27, fails | 0.95 | 0.90 | 4 of 4 | fails F1 |
| C: `COMPARISON_SETTING` | 0.73 | 0.98 | 0.815 | 4 of 4 | **passes F1-F4** |
| N: `NS3_LIKE_SETTING` | 1.03 | 0.93 | **0.759, fails** | 4 of 4 | **not validated** (F3) |

The rate-based level equals F1 in every row. Reported next to the verdict, as registered, not part of it:

| Row | Level at TTT 128 ms (failures HandoverLab / ns-3) | Level at TTT 1280 ms | F3 counting HandoverLab's failed attempts |
|---|---|---|---|
| R | 0.55 (16 / 29) | 0.26 (225 / 868) | 0.95 |
| C | 1.83 (53 / 29) | 0.70 (605 / 868) | 0.94 |
| N | 0.03 (1 / 29) | 1.07 (924 / 868) | 0.945 |

**Row N.** The overall level is close to ns-3's (1.03), and the order of the cells and the direction of the
time-to-trigger effect are right, but the registered F3 (completed HandoverLab handovers against ns-3's
handover attempts) is 0.759, below 0.8, so by the registered rule the setting is **not validated**. Counted
with HandoverLab's failed attempts, as ns-3's `ho_pm` counts them, F3 is 0.945; this was announced in
advance as a side report, not as the criterion, and does not change the verdict. The level splits as in
sample: right at 1280 ms (1.07), far too low at 128 ms (1 failure against 29). In sample it was also right
only at long time-to-trigger (N3 0.87, V3 0.97; V1 0.05, N2 0.16). So the setting imitates ns-3's failure
detection and matches ns-3's failure level at long time-to-trigger, but gives far too few failures at short
time-to-trigger. It is offered as an option, not as a validated reproduction of ns-3; it is not a default.

**Row C** passes F1-F4 on V4 (level 0.73, just inside 0.67), the first fresh set with equal run lengths on
which it passes; it passes 1 of the 4 fresh sets (N3, V1, V3, V4). Its level is too high at 128 ms (1.83)
and too low at 1280 ms (0.70). **Row R** fails the level, as on every set (0.27). F2 and F4 pass
for every row; F3 passes for rows R and C (row N: 0.759).

**Consequence.** The absolute failure level of HandoverLab stays **not calibrated**: the comparison setting
gives 0.5-1.3 times ns-3's level depending on the set (V4: 0.73). The defaults stay those of 3GPP.

**Open question (future work).** Why HandoverLab has too few failures at short time-to-trigger under the
ns-3-like detection. The likely cause, not checked, is that it has fewer long periods below Qout before a
neighbour becomes 3 dB stronger.

### V2: do the adaptive and learning rules generalise?

**Design.** Rules `a3_mro`, `a3_bandit`, `a3_pred` (ridge predictor, case A) and `dqn`, against
A3-ref (3 dB, 160 ms) and A3-tuned. Tuning and training on `urban-grid-10ghz`, seeds 101-104 only:
8 evaluated settings per rule from its grid (5 drawn at random, 3 around the best), the lowest
`unnecessary_pm` among settings with `failures_pm` at most that of A3-ref on the same runs (budget
0.0638 per UE-minute), ties within 5 % broken by fewer RRC messages. Settings and weights were frozen
before any test run. Test cards never used for tuning: `ns3-urban-3.5ghz`, `urban-macro-tr37885-4ghz`,
`highway-tr37885-4ghz`, `fr3-urban-15ghz`, with test seeds 501-505 and each card's default length and
users; also the training card with the test seeds. Criteria, paired by card and seed against
A3-tuned (two-sided Wilcoxon, Holm over the 4 test cards):

- **G-A (no harm):** failures not significantly higher than A3-tuned's on at least 3 of the 4 test cards;
- **G-B (gain kept):** the sign of the mean difference in `unnecessary_pm` on the training card's test
  seeds is the same on at least 3 of the 4 test cards;
- cost flags, no limit: attempts, ping-pong or RRC messages above 1.5 times A3-tuned's on a test card.

A rule generalises if it passes G-A and G-B.

**Selected settings.** A3-tuned 4 dB / 160 ms; `a3_mro` offset 6 dB, 160 ms, step 2 dB, window 5 s;
`a3_bandit` arms 1-5 dB, 40 ms, epoch 5, `w_failure` 2; `a3_pred` offset 6 dB, 80 ms, prediction window
0.4 s; `dqn` offsets 0-6 dB, 160 ms, `w_failure` 1.

Difference to A3-tuned in unnecessary handovers per UE-minute (rule minus A3-tuned, mean over seeds
501-505):

| Rule | `urban-grid-10ghz` (training card) | `ns3-urban-3.5ghz` | `urban-macro-tr37885-4ghz` | `highway-tr37885-4ghz` | `fr3-urban-15ghz` | G-A | G-B | Verdict |
|---|---|---|---|---|---|---|---|---|
| `a3_mro` | -0.780 | -1.120 | -4.793 | -0.637 | -0.798 | 4 of 4 | 4 of 4 | generalises |
| `dqn` | -0.357 | -0.520 | -1.408 | -0.382 | -0.363 | 4 of 4 | 4 of 4 | generalises |
| `a3_bandit` | +1.644 | +0.033 | +4.069 | +0.537 | +1.617 | 4 of 4 | 4 of 4 | meets the criteria, but worse (below) |
| `a3_pred` | -0.288 | not run | +0.946 | -0.507 | -0.312 | 3 of 4 | 2 of 4 | does not generalise |

- **`a3_mro` and `dqn` generalise.** Both keep fewer unnecessary handovers than A3-tuned on all four
  test cards (every seed in the same direction; Wilcoxon p 0.0625, Holm 0.25), with no cost flag. Their
  failure differences are small and of both signs (`a3_mro` -0.307 on `urban-macro-tr37885-4ghz`,
  +0.021 on `fr3-urban-15ghz`; `dqn` +0.020 and +0.015 per UE-minute), none significant.
- **`a3_bandit` is worse in unnecessary handovers and ping-pong, although it formally meets the
  registered criteria.** G-B checks only that the sign stays the same, and its sign is +: the setting
  chosen within the failure budget already had more unnecessary handovers than A3-tuned on the training
  card (+1.644 per UE-minute), and that loss stays on every test card. It has fewer failures (0.782
  against 1.759 per UE-minute on `urban-macro-tr37885-4ghz`) and pays with 1.65, 4.15 and 2.80 times
  A3-tuned's ping-pong on `urban-macro-tr37885-4ghz`, `highway-tr37885-4ghz` and `fr3-urban-15ghz`.
  Its G-B pass is a consistent loss, not a kept gain.
- **`a3_pred` does not generalise.** It loses the sign on `urban-macro-tr37885-4ghz` (+0.946
  unnecessary handovers per UE-minute, while failures fall from 1.759 to 0.384), and it cannot run on
  `ns3-urban-3.5ghz`: that card measures every 0.2 s, the predictor was trained at the 0.04 s of the
  training card, and the rule refuses a predictor trained with another measurement period (counted as
  not passed, as registered).

**Limits of the design.** With 5 paired seeds the smallest two-sided exact Wilcoxon p is 0.0625, so no
card can show significant harm and G-A cannot fail; read the failure differences themselves.
`fr3-urban-15ghz` has the same street grid and users as the training card on another carrier and gives
nearly the same numbers, so it is the least independent of the four test cards.
