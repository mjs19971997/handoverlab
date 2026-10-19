# How to study DAPS handover and L1/L2-triggered mobility

Since 1.0.0rc2 HandoverLab has two procedures next to baseline and conditional handover:

| Rule | Procedure | Specification | What changes compared with `a3` |
|---|---|---|---|
| `daps` | DAPS handover (Rel-16) | TS 38.300 clause 9.2.3.2, TS 38.331 clause 5.3.5.8.3 | the source keeps serving during the execution; a failed execution falls back to the source |
| `ltm` | L1/L2-triggered mobility (Rel-18) | TS 38.300 clause 9.2.3.5 | candidates configured in advance; the switch is decided on unfiltered L1 reports and sent as a MAC CE; short RACH-less execution |
| `cltm` | conditional LTM (Rel-19 work on LTM, since 1.6.0) | as `ltm` for the candidates and the execution | the UE decides the switch on its L1 measurements and executes at once: no cell switch command that could arrive late |

Both run on the same worlds and seeds as every other rule, so they can be compared pairwise with
`a3` and `cho` in an experiment or a study. The [user guide](../user_guide.md#procedures) describes the
model in detail; this page shows how to use it.

## 1. Compare the four procedures

```yaml
# procedures.yaml
schema: 1
scenario: {base: smoke, radio: {isolation: 1.0}, mobility: {users: 20, profile: veh30}}
seeds: [1, 2, 3]
rules:
  - {rule: a3, off_db: 3.0, ttt_s: 0.16}
  - {rule: daps, off_db: 3.0, ttt_s: 0.16}
  - {rule: cho, o_prep_db: -2.0, o_exec_db: 3.0, ttt_exec_s: 0.08}
  - {rule: ltm, o_prep_db: -3.0, o_switch_db: 2.0, ttt_switch_s: 0.08}
  - {rule: cltm, o_prep_db: -3.0, o_switch_db: 2.0, ttt_switch_s: 0.08}
output: results/procedures.csv
```

```bash
handoverlab run procedures.yaml --events results/procedures-events.csv
```

`radio.isolation: 1.0` and fast users make failures likely, so that the differences between the
procedures show. Read the columns:

- `interruption_exec_s_pm`: DAPS removes the execution gap (0 with the default `interruption_s`);
  LTM shortens it to its `exec_s` (20 ms instead of `exec_s` = 40 ms of the scenario).
- `outage_pct`, `rate_mbps`: with DAPS the user keeps its rate through the execution.
- `too_early_pm` against `failures_pm`: for DAPS an execution that cannot join the target and falls
  back to the source is `too_early` but not a failure. Count the fallbacks in the event log:

```python
import handoverlab as hl

rows = hl.read_events("results/procedures-events.csv")
fallbacks = sum(1 for e in rows if e["cause"] == "daps_fallback")
```

- `n_preparations`, `n_unused_preparations`, `prepared_cells_mean`: for LTM these count candidate
  configurations, the signalling an early configuration costs.

## 2. Change one thing at a time

The DAPS parameters switch its two mechanisms on and off, so their contributions can be separated
on the same seeds:

```yaml
rules:
  - {rule: daps, name: DAPS, off_db: 3.0, ttt_s: 0.16}
  - {rule: daps, name: DAPS-no-fallback, off_db: 3.0, ttt_s: 0.16, fallback: false}
  - {rule: daps, name: DAPS-no-source-data, off_db: 3.0, ttt_s: 0.16, source_data: false}
  - {rule: daps, name: as-A3, off_db: 3.0, ttt_s: 0.16, fallback: false, source_data: false}
```

The last one gives exactly the results of `{rule: a3, off_db: 3.0, ttt_s: 0.16}`; the test suite
checks this equivalence.

For LTM the main parameters are the candidate offset `o_prep_db` (how early, and how many cells, are
configured), the switch offset `o_switch_db` with `ttt_switch_s` (L1 samples are noisier than L3
measurements: a short `ttt_switch_s` reacts fast but switches back and forth), and the timing
`cmd_delay_s` and `exec_s`. `recovery: false` turns off the recovery into a candidate after a
failure.

## 3. Tune them fairly

In a study, give each procedure the same tuning budget (see the
[tuning tutorial](../tutorials/tuning-study.md)):

```yaml
methods:
  A3:
    rule: a3
    grid: {off_db: [0.0, 1.0, 2.0, 3.0, 4.0, 5.0], ttt_s: [0.0, 0.04, 0.08, 0.16, 0.32]}
    natural_bounds: {ttt_s: lower}
  DAPS:
    rule: daps
    grid: {off_db: [0.0, 1.0, 2.0, 3.0, 4.0, 5.0], ttt_s: [0.0, 0.04, 0.08, 0.16, 0.32]}
    natural_bounds: {ttt_s: lower}
  LTM:
    rule: ltm
    fixed: {o_prep_db: -3.0, n_max: 4}
    grid: {o_switch_db: [0.0, 1.0, 2.0, 3.0, 4.0, 5.0], ttt_switch_s: [0.0, 0.04, 0.08, 0.16, 0.32]}
    natural_bounds: {ttt_switch_s: lower}
```

Add `interruption_exec_s_pm` and `outage_pct` to `compare.metrics` to see what the procedures buy.

## 4. Follow single users

With `--event-level full` the trace contains two new events: `switch` (an LTM cell switch command
is sent; value: the switch offset) and `fallback` (a DAPS execution returned to the source; value:
the source SINR). `handoverlab.eventlog.serving_cells`, which the dashboard map uses, puts a user
back into its source cell after a fallback.

## 5. Write your own DAPS or LTM rule

Subclass `hl.DAPSRule` (hooks `a3_offsets` and `time_to_trigger`, like a baseline rule) or
`hl.LTMRule` (hooks `prep_offsets` on L3 measurements and `switch_offsets`, which may use the
unfiltered L1 samples `obs.l1_dbm`), and check it with the contract kit:

```python
import numpy as np
import handoverlab as hl
from handoverlab.testing import check_rule

class SpeedLTM(hl.LTMRule):
    """LTM whose switch offset grows for slow users (fewer switches back and forth)."""

    def __init__(self, o_switch_db=2.0, name="LTM-speed"):
        super().__init__(name)
        self.o_switch_db = o_switch_db
        self.report_offset_db = -3.0

    def params(self):
        return dict(o_switch_db=self.o_switch_db)

    def prep_offsets(self, obs):
        return -3.0

    def switch_offsets(self, obs):
        off = self.o_switch_db + 2.0 * (obs.speed < 5.0)   # (U,)
        return np.repeat(off[:, None], obs.l1_dbm.shape[1], axis=1)   # a scalar or (U, M)

check_rule(SpeedLTM, {"o_switch_db": 2.0})
```

## Limits of the model

- DAPS: radio-link monitoring of the source is paused during the execution, as for the other
  procedures (the execution is short against T310); uplink and the PDCP details of dual protocol
  stacks are not modelled; the source carries the user's full rate until the target is joined.
- LTM: L1 reports arrive at every L1 sample with the scenario's L1 error, without beam-level
  reports or reporting delay; candidate configurations use the preparation delay and the loss
  model of conditional configurations; early timing-advance acquisition always succeeds.
- Conditional LTM (`cltm`): the switch condition is modelled like the LTM switch condition
  (one offset and a time-to-trigger on L1 samples), since the Rel-19 condition was not frozen
  when the rule was written; the UE-side evaluation has no reporting delay.
