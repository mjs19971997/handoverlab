# How to use and write a learning-based rule

HandoverLab gives a rule the outcome of every handover attempt it made, so a rule can learn while
it runs. The built-in `a3_bandit` (since 1.0.0rc2) is a small example: Event A3 whose offset every
cell learns with an epsilon-greedy multi-armed bandit. It needs nothing beyond NumPy and is meant
as a starting point for your own learning rules, not as a tuned method.

## 1. How `a3_bandit` decides and learns

- **Trigger.** Event A3 (TS 38.331 clause 5.5.4.4) with a fixed `ttt_s`; the offset of a user is
  the arm its serving cell currently plays, one of `arms_db`.
- **Reward.** Every outcome of a handover from a cell is a reward for that cell: useful `+1`,
  unnecessary `-w_unnecessary`, too early or too late `-w_failure`; a link failure without a
  handover counts as late (`-w_failure`). These are the classes of mobility robustness optimisation
  (TS 38.300 clause 15.5.2) plus unnecessary handovers. The labels are what the network can observe
  (`handoverlab.rules.USEFUL`, `UNNECESSARY`, `EARLY`, `LATE`), not the true outcomes.
- **Learning.** A cell plays one arm for `epoch` outcomes, then updates the mean reward of that arm
  and chooses the next one: with probability `epsilon` at random, otherwise the first arm it has
  not played yet, otherwise the best. Random draws come from `ctx.rng`, so runs are repeatable.

With a single arm it is `a3` with that offset; the test suite checks that both give the same event
log.

## 2. Run it next to fixed A3

```yaml
schema: 1
scenario: {base: smoke, mobility: {users: 30}, run: {duration_s: 120.0, warmup_s: 60.0}}
seeds: [1, 2, 3]
rules:
  - {rule: a3, off_db: 3.0, ttt_s: 0.16}
  - {rule: a3_bandit, arms_db: [1.0, 2.0, 3.0, 4.0, 5.0], ttt_s: 0.16, epsilon: 0.1, epoch: 5}
output: results/bandit.csv
```

```bash
handoverlab run bandit.yaml
```

A learning rule starts knowing nothing in every run. Give it a long warm-up
(`run.warmup_s`): the metrics count only what happens after it, so the comparison is between the
learned behaviour and the fixed rule. Short runs mostly measure exploration.

`simulate` gives every run its own copy of a rule object, so nothing learned leaks between runs or
seeds. The event log shows what the cells chose: for baseline-family rules the column `o_exec` is the
A3 offset an attempt used.

```python
import handoverlab as hl

sc = hl.load_config("bandit.yaml").scenario
(res,) = hl.simulate(sc, [{"rule": "a3_bandit", "epoch": 5}], seeds=[1], log_events=True)
for e in res.events[-10:]:
    print(e["t_attempt"], e["src"], e["o_exec"], e["outcome"])
```

## 3. Things to vary

- `w_unnecessary` against `w_failure` sets the trade-off the rule learns: a larger `w_failure`
  pushes cells towards smaller offsets (earlier handovers).
- `epoch` trades noise for speed: few outcomes per epoch give noisy estimates; many make learning
  slow in cells with little traffic.
- `epsilon` keeps some exploration going after all arms were played.

In a study, give its parameters a grid like any other rule; the equal-budget tuning and the paired
tests treat it the same way (see the [tuning tutorial](../tutorials/tuning-study.md)).

## 4. Write your own learning rule

A learning rule sets `learns = True` and implements `on_outcome` (and, if it wants, `on_link_failure`):

```python
import numpy as np
import handoverlab as hl
from handoverlab.rules import EARLY, LATE, UNNECESSARY

@hl.register_rule("a3_step")
class StepA3(hl.BaselineRule):
    """Every cell raises its offset after an unnecessary handover and lowers it after a failure."""
    learns = True

    def __init__(self, step_db=0.5, ttt_s=0.16, name="A3-step"):
        super().__init__(name)
        self.step_db, self.ttt_s = step_db, ttt_s

    def params(self):
        return dict(step_db=self.step_db, ttt_s=self.ttt_s)

    def reset(self, ctx):
        super().reset(ctx)
        self.off = np.full(ctx.n_sites, 3.0)        # learned state lives in the rule, per run

    def a3_offsets(self, obs):
        return np.repeat(self.off[obs.serving][:, None], self.ctx.n_sites, axis=1)

    def time_to_trigger(self, obs):
        return self.ttt_s

    def on_outcome(self, rec):
        delta = -self.step_db if rec.label in (EARLY, LATE) else (self.step_db if rec.label == UNNECESSARY else 0.0)
        self.off[rec.source] = np.clip(self.off[rec.source] + delta, 0.0, 8.0)

    def on_link_failure(self, rec):
        self.off[rec.source] = max(self.off[rec.source] - self.step_db, 0.0)
```

Rules for learning rules:

- Keep the learned state in the rule object and create it in `reset(ctx)`; one rule object serves
  one run, and runs on other worlds start from scratch.
- Draw random numbers from `ctx.rng` only; the contract kit fails a rule that touches NumPy's or
  Python's global random state.
- Use only the `Observation` and the records (`OutcomeRecord`, `FailureRecord`); a rule never sees
  the true SINR, the buildings or the cell load.
- `memory_key(obs)` lets a conditional rule tag each preparation; the key comes back in
  `OutcomeRecord.key`.

Check it with the contract kit before using it in a study:

```python
from handoverlab.testing import check_rule
check_rule(StepA3, {"step_db": 0.5, "ttt_s": 0.16}, reduces_to=("a3", {"off_db": 3.0, "ttt_s": 0.16}, {"step_db": 0.0}))
```

To train a model offline instead, export event logs with positions and outcomes
([export event logs](export-event-logs.md)) and load the trained model in `reset`.
