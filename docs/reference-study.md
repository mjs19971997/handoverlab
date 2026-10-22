# Reference study: conditional handover against A3 at an equal failure budget

A small study with one question, fixed with its decision rule before the runs (2.1.0). It shows what the study
machinery of HandoverLab answers, and where the answer is "this protocol cannot decide". The files:
[`examples/study_reference.yaml`](https://github.com/mjs19971997/handoverlab/blob/main/examples/study_reference.yaml)
(the confirmatory study) and
[`examples/study_reference_explore.yaml`](https://github.com/mjs19971997/handoverlab/blob/main/examples/study_reference_explore.yaml)
(the exploratory test stage).

## Question and decision rule

On the card `urban-grid-10ghz` (2.0.0 defaults, 40 users, 60 s, 10 s warm-up), does conditional handover (`cho`,
preparation offset -2 dB, up to 4 candidates), tuned on the same failure budget as Event A3, give fewer unnecessary
handovers per UE-minute than A3? Both rules are tuned on 8 settings each on the tuning seeds 901-908 (A3: offset
0-8 dB, time-to-trigger 0-320 ms; CHO: execution offset 0-6 dB, time-to-trigger 0-320 ms; grids extended at most
twice); budgets are the failure rate of A3 at 3 dB / 160 ms (standard) and half of it (strict). Primary endpoint:
paired difference CHO@standard - A3@standard of `unnecessary_pm` over the test seeds 1-20, Wilcoxon signed-rank
test, Holm-adjusted; claimed only if p < 0.05 and both rules meet the budget.

## What happened

1. **With the 2.0.0 defaults the budget does not bind.** The reference A3 had 12 failures in 8 tuning runs (0.045 per
   UE-minute), unrelated to the setting; every setting of both rules met the budget, and the CHO execution offset
   ran to the upper grid edge after two extensions. The gate `grid_edge` stopped the study before the test stage.
2. **Amendment, made before any test seed was run:** full interference (`radio.isolation: 1.0`) and vehicles at
   30 m/s (`mobility.profile: veh30`), the stress conditions of `examples/study_smoke.yaml`. Now the reference A3 has
   0.27 failures per UE-minute and A3's budget binds (selected 7 dB / 80 ms, inside the grid). **CHO meets the budget
   at every evaluated setting up to an execution offset of 8 dB and a time-to-trigger of 960 ms** and is selected at
   both upper edges; the gate stopped the study again.

**Result of the confirmatory study: the question is not answered.** Under an equal failure budget conditional
handover has no optimum inside the range of its parameters on this card: delaying the execution costs it no
failures, because the prepared target remains available.

## Exploratory test stage (no claim)

The test stage was then run on the same tuning with the gate set to `warn`, and with the user throughput and SINR
added to the compared metrics. Paired against A3@standard (20 seeds, Holm-adjusted p):

| Rule (selected setting) | Unnecessary / UE-min | Failures / UE-min | Mean SINR [dB] | Rate per user [Mbit/s] |
|---|---|---|---|---|
| A3@standard (7 dB, 80 ms) | 0.651 | 0.191 | 16.4 | 13.04 |
| A3@strict (6 dB, 40 ms) | 0.812 (+25 %) | 0.126 (-34 %) | 17.3 (+0.9) | 13.32 (+2 %) |
| CHO@standard (8 dB, 960 ms) | **0.063 (-90 %)**, p < 0.0001 | 0.176 (-8 %, p = 0.39) | **4.3 (-12.1)**, p < 0.0001 | **9.77 (-25 %)**, p < 0.0001 |
| CHO@strict (8 dB, 480 ms) | 0.370 (-43 %) | 0.128 (-33 %) | 11.7 (-4.7) | 11.70 (-10 %) |

The edge setting of CHO removes nine in ten unnecessary handovers at an unchanged failure rate, and pays for it with
users that stay on a cell 12 dB worse on average and a quarter less throughput.

## Reading

- **A failure budget alone does not make a fair comparison of conditional handover.** Tuned only against failures,
  CHO trades user quality for fewer handovers without limit. A comparison needs a second constraint, on the SINR or
  the throughput, or a cost that weighs them; the study files of HandoverLab do not have that yet.
- The gates of `handoverlab study` caught the problem twice before any test seed was used; without them the study
  would have reported "-90 % unnecessary handovers" as a result.
- The numbers above are exploratory: they were produced after the confirmatory study had stopped, and they hold
  for this card and these grids only.
