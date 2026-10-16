# Tutorial 2: writing your own handover rule

A *rule* decides when and where a user hands over; the engine does everything else (measurements,
the protocol, failures, outcome labels). This tutorial writes a rule, checks it with the contract
test kit and compares it with plain A3. The complete script is
[`examples/speed_rule.py`](https://github.com/mjs19971997/handoverlab/blob/main/examples/speed_rule.py).

## The idea

Event A3 triggers a handover when a neighbour is better than the serving cell by an offset for a
time-to-trigger (TTT). A long TTT avoids needless handovers but is too slow for fast users. Our
rule shortens the TTT with the reported speed: `ttt = ttt_s * min(1, v_ref / speed)`.

## The code

```python
import numpy as np
import handoverlab as hl


@hl.register_rule("a3_speed")
class SpeedScaledA3(hl.BaselineRule):
    """Event A3 whose time-to-trigger shrinks with the reported speed."""

    def __init__(self, off_db=3.0, ttt_s=0.32, v_ref=8.0, name="A3-speed"):
        super().__init__(name)
        self.off_db, self.ttt_s, self.v_ref = off_db, ttt_s, v_ref

    def params(self):
        return dict(off_db=self.off_db, ttt_s=self.ttt_s, v_ref=self.v_ref)

    def a3_offsets(self, obs):                    # scalar, or an array (users x cells)
        return self.off_db

    def time_to_trigger(self, obs):               # scalar, or an array (users,)
        return self.ttt_s * np.minimum(1.0, self.v_ref / np.maximum(obs.speed, 1e-6))
```

Four things matter:

1. **The family.** `BaselineRule` is A3-based handover (report, preparation, command). For
   conditional handover subclass `ConditionalRule` and implement `prep_offsets(obs)` and
   `exec_offsets(obs)`; its constructor sets `report_offset_db`, `ttt_prep_s`, `ttt_exec_s`,
   `n_max`, `release_hys_db` and `immediate`.
2. **The observation.** Every hook gets an `Observation` with what a network can see: filtered
   measurements `meas_dbm` and `gap_db` (neighbour minus serving) per user and cell, `serving`,
   `connected`, reported position `x`, `y`, `speed`, `heading` and the time `t`. Outcome labels use
   the true powers, which a rule never sees. Do not write into the observation.
3. **`params()`** returns every parameter, so that `cls(**rule.params())` recreates the rule. Stored
   results and studies rely on it.
4. **Randomness** only from `ctx.rng` (given to `reset(ctx)`), never from NumPy's global state.

`@hl.register_rule("a3_speed")` makes the rule usable by name in configuration files and studies
of the same Python process. For the command line, publish it as a package with an entry point:

```toml
[project.entry-points."handoverlab.rules"]
a3_speed = "my_rules:SpeedScaledA3"
```

`handoverlab rules` then lists it.

## Check the contract

```python
from handoverlab.testing import check_rule

print(check_rule(SpeedScaledA3, params={"off_db": 3.0, "ttt_s": 0.32, "v_ref": 8.0},
                 reduces_to=("a3", {"off_db": 3.0, "ttt_s": 0.32}, {"v_ref": 1e9})))
```

```text
contract of rule SpeedScaledA3:
  PASS  construct  [family baseline]
  PASS  recreate
  PASS  debug run  [87 events, 85 handovers, 0 failures]
  PASS  deterministic
  PASS  global random state
  PASS  independent
  PASS  reduces_to a3  [80 / 80 events]
```

The `debug run` runs the engine with its invariant checks and validates every value the rule
returns (shapes, no NaN). `independent` runs the rule next to another rule on the same world and
requires the same event log as alone. `reduces_to` is the strongest check: with `v_ref = 1e9` the
TTT is never shortened, so the rule must give exactly the event log of built-in A3 with the same
offset and TTT. Put `check_rule` into the tests of your package; it raises `AssertionError` listing
every failed check.

## Compare with A3

```python
sc = hl.builtin_scenario("smoke").with_overrides({"mobility.profile": "veh30"})
rules = [{"rule": "a3", "name": "A3", "off_db": 3.0, "ttt_s": 0.32},
         {"rule": "a3_speed", "name": "A3-speed", "off_db": 3.0, "ttt_s": 0.32, "v_ref": 8.0}]
for r in hl.simulate(sc, rules, seeds=[1, 2, 3]):
    print(r.rule, r.seed, r.metrics["handovers_pm"], r.metrics["unnecessary_pm"], r.metrics["failures_pm"])
```

```text
rule      seed  handovers  unnecessary  failures
A3           1      14.76         2.76      0.60
A3-speed     1      17.04         4.56      0.12
A3           2      14.16         1.44      0.00
A3-speed     2      14.28         1.92      0.00
A3           3      13.32         0.84      0.12
A3-speed     3      13.92         1.20      0.24
```

Three seeds of a 30-second scenario prove nothing, and both rules use one hand-picked setting.
A fair comparison tunes *each* rule on its own seeds with the same effort and then tests on fresh
seeds with paired statistics: [Tutorial 3](tuning-study.md).
