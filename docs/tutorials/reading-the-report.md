# Tutorial 4: reading the report

`handoverlab report results/study-smoke` (or `study --report`) writes `report/report.md`,
`report/report.html` (self-contained, figures embedded), `report/summary.json` with every number,
and the figures as PNG files. This tutorial reads the report of the study from
[Tutorial 3](tuning-study.md) section by section. Its numbers come from 6 test seeds of a 20-second
scenario: they illustrate how to read a report, not how A3 and CHO compare.

## Provenance

```text
HandoverLab 2.4.0 (model 3), Python 3.12.10, NumPy 2.4.6, SciPy 1.18.0, Windows-2022Server-10.0.20348-SP0.
Study file hash `7b3cf5b44bde5a6d`.
Jobs: tune1 8, tune2 8, test 12; 60 rule runs simulated, the rest reused; 213 s of job time; 1 session(s).
```

The study-file hash identifies the resolved study (`study.lock.json`); the model version changes
whenever identical inputs would give different results. Quote both when you report results, and
keep the study directory: `handoverlab verify --results` can repeat stored runs on another machine
and compare their event-log fingerprints.

## Tuning: gates first

The gate table lists every gate that did not pass, then counts the passed ones:

| gate | status | group | method | budget | detail |
|---|---|---|---|---|---|
| budget_binding | warn | layout.site_spacing_m=100 | - | standard | more than 90 % of the settings of every method meet the budget: share of settings within the budget: A3 100 %, CHO 100 % |

Read the gates before any result. A `BLOCK` means no test ran. A `warn` limits what a result can
mean: here, at 100 m, every evaluated setting of both methods met the standard budget, so "within the
failure budget" says little at that site spacing. The *Grid extensions* table lists every grid that
the policy `extend` widened (here six extensions in four rounds: A3's offset to 8 dB, CHO's execution
offset step by step to 13 dB and its time-to-trigger to 512 ms).

## Tuning: what was selected

For every tuning group the report gives the reference rule, the budgets and the selected setting
per method and budget, with how many of the 8 settings met the budget (group 100 m):

| method | budget | selected setting | unnecessary_pm | failures_pm | prepared cells | within budget | budget met |
|---|---|---|---|---|---|---|---|
| A3 | standard | off_db=6, ttt_s=0.16 | 1.016 | 0.313 | 0.000 | 8 / 8 | yes |
| A3 | strict | off_db=6, ttt_s=0.04 | 1.328 | 0.078 | 0.000 | 7 / 8 | yes |
| CHO | standard | o_exec_db=11, ttt_exec_s=0.48 | 0.156 | 0.078 | 0.442 | 8 / 8 | yes |
| CHO | strict | o_exec_db=11, ttt_exec_s=0.48 | 0.156 | 0.078 | 0.442 | 5 / 8 | yes |

![Tuning figure](../images/report-tuning.png)

The figure shows every evaluated setting: failure rate (the constraint) against unnecessary-handover
rate (the objective). Filled points are within the first budget (dashed line), the circles are the
selected settings, the diamond is the reference rule. Two things to look for:

- **Is the trade-off real?** If all points sit left of the budget lines, the budget does not
  constrain the choice (the `budget_binding` gate says so).
- **Is the winner isolated?** If many filled points have nearly the same objective, the tie-breaks
  decide (the `flat_optimum` gate). Here CHO met both budgets with the same setting, so
  `CHO@standard` and `CHO@strict` are identical in the test stage.

Every evaluated setting and its means are in `tables/tuning` and `tuned/<group>.json`, so the
selection can be redone or checked.

## Test results: means

| rule | unnecessary_pm | failures_pm | handovers_pm | prepared_cells_mean |
|---|---|---|---|---|
| A3-ref | 1.719 [0.805, 2.633] | 0.234 [0.085, 0.384] | 17.057 [15.334, 18.781] | 0.000 [0.000, 0.000] |
| A3@standard | 1.172 [0.538, 1.806] | 0.052 [-0.025, 0.129] | 16.510 [14.504, 18.517] | 0.000 [0.000, 0.000] |
| CHO@standard | 0.339 [0.052, 0.625] | 0.026 [-0.031, 0.083] | 15.703 [13.643, 17.763] | 0.406 [0.372, 0.441] |

Means over the 12 test runs (2 conditions x 6 seeds) with 95 % t intervals, then the same per
condition. These intervals describe the spread between worlds; they are wide because worlds differ
a lot. They are *not* the right basis for comparing rules, because every rule ran on the same worlds.

## Test results: paired comparisons

The comparisons use the differences run by run (rule minus baseline on the same condition and
seed), which removes the differences between worlds:

| rule | pairs | mean | baseline | difference | t interval | bootstrap interval | change % | p | p (Holm) |
|---|---|---|---|---|---|---|---|---|---|
| A3@standard | 12 | 1.172 | 1.719 | -0.5469 | [-1.0267, -0.0670] | [-0.9375, -0.1302] | -31.8 | 0.0430 | 0.0430 |
| CHO@standard | 12 | 0.339 | 1.719 | -1.3802 | [-2.2330, -0.5274] | [-2.0833, -0.7031] | -80.3 | 0.0049 | 0.0195 |

(unnecessary handovers per UE-minute; some columns left out.)

- **difference** with its **t interval** and **bootstrap interval**: the size of the effect and
  its uncertainty. Report these first.
- **change %** and the ratio interval: the same relative to the baseline mean.
- **p**: the Wilcoxon signed-rank test on the paired differences (zero differences dropped; exact up to
  500 non-zero differences, normal approximation above).
  **p (Holm)** is adjusted for all comparisons of the same metric: use it when you look at several
  rules at once.
- **non-zero**: how many of the pairs differ at all. With per-run rates built from a handful of
  events, many pairs are tied.

Reading the rows above: tuned A3 had 0.55 fewer unnecessary handovers per UE-minute than the
reference A3 on average; the t interval excludes zero and p (Holm) = 0.043. CHO@standard had 1.38 fewer
(80 %, p (Holm) = 0.02), but with a 10-11 dB execution offset and 480 ms time-to-trigger, and it holds
0.4 prepared cells per user. The per-condition rows (in the report) are weaker: with 6 pairs per site
spacing no difference survives the Holm adjustment, so the pooled result should be read with the
checklist below. For failures (not shown) both tuned rules had fewer failures than the reference, but
after the Holm adjustment none is significant (p (Holm) = 0.13-0.16).

![Paired differences](../images/report-comparison.png)

The figure shows the mean paired difference with its bootstrap interval for each metric. An
interval that crosses zero is not a demonstrated difference.

## A checklist

1. Gates: any `BLOCK`? Which warnings, and do they touch the comparison you care about?
2. Budgets: did every method meet them? Is the trade-off constrained?
3. Selected settings: interior points of the grids? Any grid extensions?
4. Paired differences with intervals, per condition as well as pooled. Is the sign the same in
   every condition? When the conditions differ in scale, the per-condition rows are the primary test:
   the pooled Wilcoxon test mixes differences that are not symmetric about one centre. With fewer than
   about 20 pairs the percentile bootstrap interval tends to be too narrow; rely on the t interval.
5. Holm-adjusted p-values when several rules are compared on one metric (each metric is its own family;
   there is no correction across metrics).
6. Enough pairs: `handoverlab.stats.seeds_needed(sd, half_width)` tells how many seeds a given
   interval width needs, from the spread of a pilot study like this one.
