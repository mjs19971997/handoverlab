# AI/ML-based mobility: RRM measurement prediction (TR 38.744)

3GPP studied machine learning for NR mobility in TR 38.744 (Release 19, V19.0.1). Its two study goals
(clause 4.1) are to reduce the measurement effort of the device by predicting measurement results, and to
improve handover performance (for example handover failures). The rule `a3_pred` (since 2.4.0) follows the
two representative use cases the study recommends for normative work (clause 7):

- **case A**, intra-frequency temporal prediction: from the L3 results of a cell in an observation window
  (OW), the results in the next prediction window (PW) are predicted; the handover can act on the predicted
  event (second goal);
- **case B**, measurement skipping: after each measured instant, `skip` instants are not measured but
  predicted (measurement reduction rate MRRT = skip / (skip + 1)); Event A3 runs on the mixed series (first
  goal).

The rule is optional: nothing changes unless a run names it, and it needs nothing beyond NumPy.

## 1. The rule

```yaml
rules:
  - {rule: a3, off_db: 2.0, ttt_s: 0.32}                                   # legacy
  - {rule: a3_pred, case: B, skip: 1, predictor: ridge, weights: b1.json}  # MRRT 50 %, option 3
  - {rule: a3_pred, case: A, pw_s: 0.32, predictor: ridge, weights: a.json} # option 2
```

| Parameter | Meaning |
|---|---|
| `off_db`, `ttt_s` | Event A3 offset and time-to-trigger (TR 38.744 Tables 5.3.1-1/-2: 2 dB, 320 ms) |
| `case` | `A` (prediction ahead, no skipping) or `B` (measurement skipping) |
| `predictor` | `hold` (sample and hold, the non-AI baseline of clause 5.1), `ridge` (needs `weights`), or your object with `predict()` |
| `weights` | a JSON file written by `fit_predictor`, or its dictionary |
| `pw_s` | case A: prediction window [s] |
| `skip` | case B: skipped instants after every measured one |
| `filter_option` | case B: L3 filtering after skipped instants, options 1, 2 or 3 of clause 4.2 (1: on the last, predicted, value; 2: none; 3: on the last actual result) |
| `act` | `true`: hand over on the predictions; `false`: hand over exactly as `a3` and only record the predictions |
| `top_k`, `etd_s`, `event_pw_s` | statistics: cells per user in the accuracy (strongest at the prediction origin), maximum ETD and how far ahead the event is predicted (case A) |

**Case A and handover model option 2** (clause 5.5.1, Figure 5.5.1-2). The network sends the command when
the entering condition of the predicted event holds on the actual result. `a3_pred` reports when the A3
entering condition holds now *and* is predicted to hold at every predicted instant within `ttt_s`; the
engine's time-to-trigger is then 0. With `predictor: hold` this is A3 without time-to-trigger (the test
suite checks that the event logs are identical). The preparation starts at the report, not at the earlier
instant of the prediction, so the command comes one preparation time later than in the TR's option 2.

**Case B and handover model option 3** (Figure 5.5.1-3). The rule keeps its own L3 series: measured
instants filter the L1 result (`obs.l1_dbm`) with the coefficient of the engine's filter (TS 38.331 clause
5.5.3.2), skipped instants take the prediction. Event A3 with the usual time-to-trigger runs on this series
and the handover follows as for `a3`. With `skip: 0` the series is the engine's L3 result, bit for bit.

## 2. Predictors and training

`hold` keeps the last result of the observation window. `ridge` is a linear autoregressive model per
horizon h, one cell at a time (RRM sub-use case 2 of clause 4.2, single-cell approach):

    F(t0 + h) = F(t0) + w_h . [F(t0) - F(t0 - s), ..., F(t0) - F(t0 - 7 s), 1]

with the observation window of 8 samples spaced `s` measurement instants (1 in case A, `skip + 1` in
case B). The weights come from ridge regression on runs with full measurement, over the 4 strongest cells of
each connected user. 3GPP asks for different random seeds for training and test (clause 5.1): train on seeds
you never test on.

```python
import handoverlab as hl
from handoverlab.rules.predict import fit_predictor

sc = hl.builtin_scenario("urban-macro-tr37885-4ghz")
fit_predictor(sc, seeds=[101, 102, 103, 104], path="b1.json", case="B", skip=1)
fit_predictor(sc, seeds=[101, 102, 103, 104], path="a.json", case="A", pw_s=0.32)
res = hl.simulate(sc, [{"rule": "a3", "off_db": 2.0, "ttt_s": 0.32},
                       {"rule": "a3_pred", "case": "B", "skip": 1, "predictor": "ridge",
                        "weights": "b1.json"}], seeds=[201, 202])
```

The model has 8 x H weights (for example 40 for H = 5), far below the 4.5 k to 1.5 M parameters of the
models in TR 38.744 Table 5.2.2-1: it is a transparent baseline that any learned model should beat, not a
competitive method. Several speeds or set-ups can be mixed (generalization case GC#2 of clause 5.2.1.2) by
adding the data sets of `handoverlab.rules.predict.collect` before solving.

## 3. Statistics

`simulate` gives every run a copy of a rule object; pass a `Recorder` to read the statistics of the copies:

```python
from handoverlab.rules.predict import PredA3, Recorder
from handoverlab.simulate import run_world
from handoverlab.world import build_world

rec = Recorder()
run_world(build_world(sc, 201), [PredA3(case="A", predictor="ridge", weights="a.json", act=False, record=rec)])
print(rec.rules[0].stats())
```

- `err_db`: prediction accuracy of clause 5.2.1.1, the mean absolute difference between the predicted and the
  ground-truth L3 RSRP of the same cell, per horizon (`err_avg_db` over the PW). The ground truth is the
  engine's L3 result with full measurement and sliding filtering (clause 5.1).
- `mrrt`, `n_measured`, `n_skipped`: measurement reduction rate MRRT of clause 5.2.1.1 after the warm-up.
- case A: `n1`, `n2`, `n3`, `precision`, `recall`, `f1` of the indirect prediction of Event A3 (clauses 4.3
  and 5.3.1): a true event is the onset of the A3 condition held for the time-to-trigger; a predicted event
  comes from actual results up to the origin and predicted ones after it; a predicted event within the
  maximum ETD of a true event of the same user, neighbour and serving cell counts as true (n3). Instants
  around a change of the serving cell are left out.

Handover failure in the TR's sense (the model of TR 36.839 clause 5.2.1.3, failures in handover states 2 and
3) is the sum of the failure causes `command_lost`, `rlf_in_preparation` and `execution_failure`; the HOF
rate is HOF / (HOF + completed handovers).

## 4. Evaluation against TR 38.744

Criteria were fixed in a plan before the first run and are reported as they came. Training seeds 101-104
(FR1) and 101-102 (FR2), test seeds 201-203; A3 offset 2 dB, time-to-trigger 320 ms, preparation and execution
40 ms each (TR 38.744 clause 5.5.1), FilterCoefficient 4; ridge with an observation window of 8 samples.

- **FR1** (TR scenario 2, case B): card `urban-macro-tr37885-4ghz` (UMa 4 GHz, 20 MHz, 500 m lattice), L1
  period 40 ms, 30 / 60 / 90 km/h, 100 users, 120 s per seed; one ridge model per speed and MRRT.
- **FR2** (TR scenario 4, case A): card `urban-grid-28ghz-beams` (UMi 28 GHz, 3 sectors x 8 SSB beams), L1
  period 80 ms, 60 / 90 / 120 km/h, 40 users; one ridge model trained on all three speeds.

**Prediction accuracy** (mean absolute L3 RSRP difference over the PW, dB, pooled over the test seeds):

| Set-up | Speed | Sample and hold | Ridge |
|---|---|---|---|
| FR2 case A, PW 400 ms (5 instants) | 60 km/h | 2.00 | 1.14 |
| | 90 km/h | 2.42 | 1.41 |
| | 120 km/h | 2.74 | 1.61 |
| FR1 case B, MRRT 50 % | 30 / 60 / 90 km/h | 1.33 / 1.76 / 1.97 | 0.35 / 0.49 / 0.65 |
| FR1 case B, MRRT 66.7 % | 30 / 60 / 90 km/h | 2.18 / 2.82 / 3.11 | 0.72 / 1.33 / 1.77 |
| FR1 case B, MRRT 80 % | 30 / 60 / 90 km/h | 3.38 / 4.21 / 4.54 | 2.10 / 3.52 / 4.27 |

As TR 38.744 clause 5.2.2.1.4 observes, the error grows with the speed, the PW and the MRRT, and the learned
model beats sample and hold (criteria A1, A2, B1, B2 passed). Two differences: here sample and hold is far
worse in case B than in the TR's tables, because with filtering option 1 the held values enter the L3 filter
and slow it down; and the ridge gain shrinks at MRRT 80 %, where the TR sees it grow.

**Generalization over speed** (FR1 case B, MRRT 50 %, loss against the model trained at the test speed):
GC#2 (trained on all three speeds, three times the data) +0.08 / +0.03 / -0.08 dB at 30 / 60 / 90 km/h,
within 0.1 dB everywhere (G1 passed). GC#2 was not better than GC#1 on average (G2 **failed**: +0.008 against
-0.009 dB): at 90 km/h the models trained at 30 and 60 km/h were more accurate than the 90 km/h model.

**Event prediction** (FR2, 90 km/h, indirect A3, PW 320 ms, maximum ETD 80 ms): F1 0.978 for both
predictors (precision 0.957, recall 1.0), inside the 0.59-0.99 of TR 38.744 Table 5.3.2.1-1 (E2 passed; E1
passed only as a tie). With PW equal to the time-to-trigger, sample and hold predicts every onset that
persists, so this score does not separate the predictors here.

**Handover performance** (pooled over the test seeds; HOF of TR 36.839):

| Set-up | Rule | HOF rate | HO attempts /UE/s | Ping-pong /UE-min |
|---|---|---|---|---|
| FR1 case B, MRRT 50 %, 30 km/h | legacy A3 | 3.94 % | 0.247 | 1.25 |
| | ridge, option 3 | 4.68 % | 0.242 | 1.18 |
| FR1 case B, MRRT 50 %, 60 km/h | legacy A3 | 7.35 % | 0.306 | 1.90 |
| | ridge, option 3 | 8.18 % | 0.291 | 1.80 |
| FR1 case B, MRRT 50 %, 90 km/h | legacy A3 | 7.12 % | 0.328 | 2.45 |
| | ridge, option 3 | 8.02 % | 0.301 | 2.04 |
| FR2 case A, 90 km/h | legacy A3 | 2.40 % | 0.372 | 0.35 |
| | sample and hold, option 2 | 0.32 % | 0.576 | 1.07 |
| | ridge, option 2 | 0.30 % | 0.576 | 1.06 |

Case B halves the measurements at a cost of +0.7 to +0.9 percentage points of HOF rate and with 2-8 % fewer
attempts (H1 passed; TR 38.744 Table 5.5.2.2-1 reports -1.00, 0.29 and 5.90 percentage points). In case A
option 2 removes most handover failures (H2 passed, as in most results of TR 38.744 Table 5.5.2.1-1), but
almost all of the gain comes from not waiting for the time-to-trigger: sample and hold does the same (H3
passed only by 0.0002 attempts per UE per second), and both make 55 % more attempts and three times the
ping-pongs. The TR tables report no ping-pong rate; read the gain together with that cost.

**Generalisation (2.5.0).** Tuned and trained on `urban-grid-10ghz` (ridge, case A) and tested on four other
cards with unseen seeds in a pre-registered study ([V2](../calibration.md#v2-do-the-adaptive-and-learning-rules-generalise)), `a3_pred` did not generalise: on
`urban-macro-tr37885-4ghz` it had more unnecessary handovers than tuned A3 (+0.95 per UE-minute) while its
failures fell (0.38 against 1.76), and it cannot run on `ns3-urban-3.5ghz`, whose 0.2 s measurement period
differs from the 0.04 s the predictor was trained at (the rule refuses such a predictor). Limits of the design:
with 5 seeds the smallest two-sided Wilcoxon p is 0.0625, so the no-harm check could not fail, and
`fr3-urban-15ghz` is the training grid at another frequency, so it is the least independent test card
([V2](../calibration.md#v2-do-the-adaptive-and-learning-rules-generalise)).

The runner and the full numbers are kept outside the package; `handoverlab verify --only learning` repeats a
short check of the mechanics (P1-P4) on the `smoke` card.

## 5. What TR 38.744 studies and HandoverLab does not model

- RLF prediction (clause 4.4; the TR itself evaluated it without simulations).
- Frequency-domain (inter-frequency) prediction, TR scenario 3: HandoverLab's co-sited carriers share their
  large-scale fields (TR 38.901 clause 7.6.5 with full correlation), so the pathloss-offset baseline would be
  nearly exact and the comparison not meaningful.
- Spatial-domain prediction (scenario 6), beam-level prediction (sub-use cases 4-6), L1 inputs (sub-use cases
  1 and 3), the cluster approach, direct event prediction, other events than A3.
- Handover model option 1 (preparation started by the predicted event) and the early preparation of option 2.
- The engine's measurement-energy counter (`l1_measurements_pm`) does not drop with case B; the rule reports
  MRRT instead.
- Model life cycle, UE-sided and network-sided models, reporting and data collection (clause 6), RF and
  baseband measurement errors of the prediction (clause 6.2.1.2), model complexity in FLOPs.
- The 7-site, 3-sector layout with wrap-around and the trajectory models of TR 38.843 clause 6.3.1 (straight
  segments with random direction changes): the evaluation uses the street-grid trajectories of the cards.
