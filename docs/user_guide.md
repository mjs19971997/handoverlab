# HandoverLab user guide

This guide covers version 0.2.0a1 (stage 2). It explains the ideas behind a run, the built-in
scenarios, the configuration keys, the command line, the Python API, how to write and check your own
handover rule, event logs and their fingerprints, the verification checks, and what the metrics
mean.

## 1. Concepts

**World.** A scenario plus a seed fixes a *world*: the site layout, the radio map (line of sight,
path loss, shadowing), the trajectories of all users, their service classes and the background
load of every cell. Everything random comes from independent NumPy streams derived from the seed
(`handoverlab.seeds`).

**Rules run on the same world.** `simulate()` builds one world per seed and runs every handover
rule on it with *identical* radio samples. The protocol engine draws no random numbers, so two rules
on the same seed differ only through their decisions. Compare rules seed by seed (paired), not by
their overall averages alone.

**Ground truth and observations.** Outcome labels use the true received powers. A rule sees only
what a network can observe: filtered measurements, the serving cell, reported position, speed and
heading, and the nominal site plan.

**Time base.** The engine advances all users together in steps of `protocol.step_s` (10 ms). L1
samples are taken every `protocol.l1_period_s` (40 ms) and pass through the L3 filter; handover
decisions are made at these measurement instants.

## 2. Scenarios

### Street grid (`layout.kind = "street_grid"`)

The urban grid of 3GPP TR 37.885 Annex A: street centre lines every 433 m (x) and 250 m (y), streets
20 m wide, building blocks in between. `layout.blocks` sets the number of blocks; the default
`[3, 3]` is the minimum area of TR 37.885 Table A-1. Sites stand on the pavement every
`layout.site_spacing_m` metres along every street, `layout.site_offset_m` from the centre line,
alternately on the two sides. A link is in line of sight if the segment between site and user
crosses no building and, with `radio.clutter_los`, if the spatially consistent LOS state of TR 38.901
(clause 7.6.3.3; a random field with `radio.los_corr_m` correlation) says so. Both are properties of
the place: every user passing a spot sees the same blockage.

Users follow the street centre lines (with a lateral offset per user) and choose straight, left or
right at each intersection with probabilities 0.5 / 0.25 / 0.25.

### Open area (`layout.kind = "open_area"`)

The rectangle of the same grid size without buildings and with a hexagonal site grid. The LOS state
is drawn as a process along each user's path (nothing repeats by place), and users move between
random waypoints. With `radio.place_share = 0` all shadowing also moves with the user.

### Built-in scenarios

Four named scenarios are ready to use. Each has a *scenario card*: purpose, layout drawing, every
parameter with its source, known limitations and the reference results it was checked against
([docs/scenarios](scenarios)).

| Name | Content |
|---|---|
| [`smoke`](scenarios/smoke.md) | 2 x 2-block grid, 150 m sites, 20 users, 30 s: runs in seconds; checks and first steps |
| [`urban-grid-10ghz`](scenarios/urban-grid-10ghz.md) | the defaults: 3 x 3-block grid, 100 m sites, 10 GHz, 40 users, 120 s |
| [`open-area-10ghz`](scenarios/open-area-10ghz.md) | same rectangle without buildings, hexagonal sites, nothing tied to place |
| [`ns3-urban-3.5ghz`](scenarios/ns3-urban-3.5ghz.md) | the set-up of the comparison with ns-3 / 5G-LENA: seven sites, 3.5 GHz, light load |

Use one by name (`scenario: smoke`) or as the base of your own values
(`scenario: {base: smoke, mobility: {users: 40}}`); in Python `hl.builtin_scenario("smoke")`.
`handoverlab scenarios` lists them and `handoverlab scenarios smoke` prints a card.

## 3. Configuration

An experiment file has four top-level keys: `scenario`, `seeds`, `rules` and `output`. Every key is
checked; an unknown key or a value of the wrong type stops the run with a message that names the
key (for example `unknown key 'scenario.layout.blokcs'`). YAML (`.yaml`, `.yml`), TOML (`.toml`) and
JSON (`.json`) files are accepted, and `hl.load_config()` also takes a dictionary.

```yaml
scenario:
  layout: {kind: street_grid, blocks: [3, 3], site_spacing_m: 100.0}
  radio: {carrier_ghz: 10.0, pathloss: umi_street_canyon}
  mobility: {users: 40, profile: veh16}
  run: {duration_s: 120.0, warmup_s: 20.0}
seeds: [1, 2, 3]            # or {first: 1, last: 10}
rules:
  - {rule: a3, name: A3-3dB, off_db: 3.0, ttt_s: 0.16}
  - {rule: cho, name: CHO, o_prep_db: -2.0, o_exec_db: 3.0, ttt_exec_s: 0.08, n_max: 4}
output: results/metrics.csv
```

### Scenario keys and defaults

| Section | Key | Default | Meaning |
|---|---|---|---|
| `layout` | `kind` | `street_grid` | `street_grid` or `open_area` |
| | `blocks` | `[3, 3]` | number of blocks in x and y |
| | `pitch_m` | `[433, 250]` | distance between street centre lines [m] |
| | `street_width_m` | `20` | street width [m] |
| | `site_spacing_m` | `100` | site spacing along the streets / hexagonal spacing [m] |
| | `site_offset_m` | `9` | site distance from the street centre line [m] |
| | `sites` | none | explicit site list `[[x, y], ...]` [m] |
| `radio` | `carrier_ghz` | `10` | carrier frequency (0.5-100 GHz) |
| | `bandwidth_mhz` | `200` | carrier bandwidth |
| | `tx_power_dbm` | `35` | transmit power per site |
| | `bs_gain_db`, `ue_gain_db` | `20`, `0` | beam gain towards a served or measuring user; UE gain |
| | `noise_figure_db` | `7` | UE noise figure |
| | `isolation` | `0.3` | mean-to-peak gain of an interfering data beam (1 = no beam isolation) |
| | `bs_height_m`, `ue_height_m` | `10`, `1.5` | antenna heights |
| | `pathloss` | `umi_street_canyon` | or `uma` (TR 38.901 Table 7.4.1-1) |
| | `shadow_los_db`, `shadow_nlos_db` | `4`, `7.82` | shadowing standard deviation |
| | `shadow_decorr_m` | `10` | shadowing decorrelation distance |
| | `shadow_site_corr` | `0.5` | correlation of the shadowing between sites |
| | `place_share` | `1` | share of shadowing variance tied to place (rest moves with the user) |
| | `clutter_los` | `true` | spatially consistent LOS state on top of the buildings |
| | `los_corr_m` | `50` | correlation distance of the LOS state |
| | `time_var_db`, `time_var_tau_s` | `1.5`, `1` | time-varying component (moving blockers) |
| | `l1_error_db` | `1` | error of one L1 RSRP sample |
| | `map_res_m` | `1` | radio-map resolution (street grid) |
| `protocol` | `step_s` | `0.01` | simulation step |
| | `l1_period_s` | `0.04` | L1 sample period (multiple of `step_s`) |
| | `l3_k` | `4` | L3 filter coefficient k (TS 38.331) |
| | `label_period_s` | `0.2` | sampling of the outcome-label quantities |
| | `report_interval_s` | `0.12` | periodic reporting interval (CHO) |
| | `qout_db`, `qin_db` | `-8`, `-6` | out-of-sync / in-sync SINR thresholds |
| | `qout_window_s`, `qin_window_s` | `0.2`, `0.1` | their evaluation windows |
| | `n310`, `n311`, `t310_s` | `1`, `1`, `1` | radio-link failure counters and timer |
| | `prep_s`, `exec_s` | `0.05`, `0.04` | preparation delay; execution interruption |
| | `reest_s`, `cho_recovery_s` | `1`, `0.4` | outage of a re-establishment; of a recovery into a prepared cell |
| | `pingpong_s` | `1` | ping-pong window |
| | `cfg_loss_as_failure` | `false` | check mode: a lost conditional configuration fails like a lost handover command |
| `traffic` | `services` | 5 classes | list of `{key, fiveqi, gbr, t_min_s, theta_q_db, share, rate_mbps}` |
| | `se_max` | `7.4` | spectral-efficiency cap [bit/s/Hz] |
| | `hotspot_share`, `hotspot_load`, `normal_load` | `0.25`, `[0.55, 0.85]`, `[0.05, 0.25]` | background load |
| | `load_tau_s`, `rate_scale`, `label_load` | `0.2`, `1`, `1` | load smoothing; rate multiplier; load assumed by the label |
| `mobility` | `users` | `40` | number of users |
| | `profile` | `veh16` | `ped`, `veh8`, `veh16`, `veh30`, `mix`, `c8`, `c16`, `c30` |
| | `groups` | none | own speed groups `[{share, v_min, v_max, lateral_m: [lo, hi]}, ...]` |
| `run` | `duration_s`, `warmup_s` | `120`, `20` | run length; initial part not counted |

In Python, `Scenario.with_overrides({"layout.site_spacing_m": 50})` returns a changed copy.

### Built-in rules

| Key | Family | Parameters |
|---|---|---|
| `a3` | baseline | `off_db` (3.0), `ttt_s` (0.16), `name` |
| `cho` | conditional | `o_prep_db` (-2.0), `o_exec_db` (3.0), `ttt_exec_s` (0.08), `ttt_prep_s` (0.0), `n_max` (4, at most 8), `rel_hys_db` (3.0), `immediate` (false), `name` |

## 4. Command line

```text
handoverlab run CONFIG [-o OUT] [--seeds S ...] [--events FILE] [--debug] [-q]
handoverlab verify [--only GROUP ...] [--full] [--ns3] [--results FILE [--sample N]] [--json OUT] [-q]
handoverlab scenarios [NAME] [--markdown] [--svg FILE] [--docs DIR]
handoverlab rules
handoverlab init [PATH]
handoverlab --version
```

`run` writes one row per seed and rule. A `.csv` output has the columns `seed`, `rule`, `family`,
`fingerprint` (of the event log), `n_events`, the rule parameters (`param.*`) and all metrics; a
`.json` output also stores the resolved scenario, the rule key, the timing of every run and the
versions of Python, NumPy and SciPy. `--events` writes the event logs as one table (see section 8):
Parquet for a `.parquet` name if `pyarrow` is installed (`pip install handoverlab[parquet]`), CSV
otherwise. `--debug` checks the engine invariants while running (section 9).

`verify` runs the verification checks and prints PASS, FAIL or NOTE for each (section 9).
`scenarios` lists the built-in scenarios or prints one card. `python -m handoverlab` works as well.

## 5. Python API

```python
import handoverlab as hl

sc = hl.Scenario()                                     # all defaults
exp = hl.load_config("examples/street_grid.yaml")       # or a dict
results = hl.run_experiment(exp)                        # list of RunResult
world = hl.build_world(sc, seed=1)                      # one world ...
results = hl.run_world(world, [{"rule": "a3"}, {"rule": "cho"}], log_events=True)   # ... many rules
results[0].metrics["unnecessary_pm"], results[0].events[:3]
results[0].fingerprint                                  # SHA-256 of the event log, always set
hl.simulate(sc, [{"rule": "a3"}], seeds=[1], debug=True)   # with invariant checks
hl.write_events(results, "events.parquet")              # event table (CSV without pyarrow)
```

## 6. Writing a handover rule

A rule subclasses `BaselineRule` (A3-based handover) or `ConditionalRule` (CHO) and implements a few
hooks. The engine calls the hooks; the rule never calls the engine. Each hook receives an
`Observation` with arrays over users (U) and cells (M): `meas_dbm`, `gap_db` (neighbour minus
serving), `serving`, `connected`, `x`, `y`, `speed`, `heading`, `t`.

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

    def a3_offsets(self, obs):                 # scalar or (U, M)
        return self.off_db

    def time_to_trigger(self, obs):            # scalar or (U,)
        return self.ttt_s * np.minimum(1.0, self.v_ref / np.maximum(obs.speed, 1e-6))

results = hl.simulate(hl.Scenario(), [{"rule": "a3"}, {"rule": "a3_speed", "v_ref": 10.0}], seeds=[1])
```

A `ConditionalRule` sets `report_offset_db`, `ttt_prep_s`, `ttt_exec_s`, `n_max`,
`release_hys_db` and `immediate` in its constructor and implements `prep_offsets(obs)` and
`exec_offsets(obs)` (scalar or (U, M)). A rule that learns from outcomes sets `learns = True` and
receives `on_outcome(OutcomeRecord)` and `on_link_failure(FailureRecord)`; `memory_key(obs)` lets it
attach its own key to each preparation. Randomness must come from `ctx.rng` (given to `reset(ctx)`),
never from NumPy's global state.

Rules in an installed package are found through the entry-point group `handoverlab.rules`:

```toml
[project.entry-points."handoverlab.rules"]
a3_speed = "my_rules:SpeedScaledA3"
```

### Checking a rule: the contract test kit

`handoverlab.testing.check_rule` runs a rule on the `smoke` scenario and checks the contract of the
rule interface. Put it in the tests of your plug-in package:

```python
from handoverlab.testing import check_rule
from my_rules import SpeedScaledA3

def test_contract():
    check_rule(SpeedScaledA3, params={"off_db": 3.0, "ttt_s": 0.32, "v_ref": 8.0},
               reduces_to=("a3", {"off_db": 3.0, "ttt_s": 0.32}, {"v_ref": 1e9}))
```

| Check | Meaning |
|---|---|
| `construct` | the rule is built from `params`; `params()` is JSON-serialisable and reports them; the family is valid |
| `recreate` | `cls(**rule.params())` reports the same parameters, so stored results can be repeated |
| `debug run` | a run in debug mode raises nothing: hook values have valid shapes and no NaN, the observation is not written to, all invariants hold |
| `deterministic` | two runs give identical event logs and metrics |
| `global random state` | NumPy's and Python's global random state are untouched (use `ctx.rng`) |
| `independent` | next to another rule on the same world the rule gives the same event log as alone |
| `reduces_to` | optional: with the given parameter changes the rule gives the event log of a built-in rule |

`check_rule` raises `AssertionError` that lists every failed check; with
`raise_on_failure=False` it returns the report instead.

## 7. Metrics

Rates are per UE-minute of the measured part of the run (suffix `_pm`); counts start with `n_`. The
full catalogue with units is `handoverlab.engine.METRICS`.

**Outcome of an attempt** (exactly one per attempt; `n_attempts` equals their sum):

- `too_late`: the command or configuration was lost, or the link failed while the handover was in
  preparation;
- `too_early`: the execution failed, or the link failed in the target before the evaluation window
  closed, and the UE re-established in the source or the target;
- `wrong_cell`: the same, but the UE re-established in a third cell;
- `unnecessary`: completed, the source link would not have failed during the window, and the stay
  was shorter than `t_min_s` of the user's service or the mean SINR gain over the window was below
  `theta_q_db`;
- `useful`: completed and not unnecessary;
- `censored`: the run ended before the outcome was known.

**Failures by cause** (`failures_pm` is their sum): `command_lost`, `rlf_in_preparation`,
`rlf_without_handover` (re-established in another cell), `coverage_rlf` (in the same cell),
`execution_failure`, `rlf_after_handover`.

**Other metrics**: `handovers_pm`, `pingpong_pm`, `prepared_cells_mean`, `preparations_pm`,
`unused_preparations_pm`, `lost_configurations_pm`, `recoveries_pm`, `interruption_s_pm`,
`outage_pct`, `rate_mbps`, `delivered_share`, `sinr_db`, `spectral_eff`, `mean_load`.

## 8. Event logs and fingerprints

With `log_events=True` (Python) or `--events FILE` (command line) every run keeps its event log: one
row per handover attempt and per link failure without a handover. The columns and units are in
`handoverlab.eventlog.EVENT_COLUMNS`:

| Column | Meaning |
|---|---|
| `seed`, `rule` | the run (in tables) |
| `t_attempt`, `t_exec`, `t_end` | start of the attempt, start of the execution (-1 if none), time of the outcome [s] |
| `ue`, `kind` | user; `ho` baseline handover, `cho` conditional handover, `rlf` failure without handover |
| `src`, `tgt` | source cell; target cell (for `rlf`: cell of the re-establishment) |
| `outcome`, `cause` | outcome label (section 7) and failure cause |
| `dwell`, `gain_db` | time of stay in the target [s]; mean SINR gain over the evaluation window [dB] |
| `n_prepared`, `o_exec` | prepared cells at the attempt; execution or A3 offset (-99 if none) [dB] |
| `x`, `y` | position at `t_end` [m] |

`hl.write_events(results, path)` writes the logs of many runs as one table (Parquet with typed
columns if `pyarrow` is installed and the name ends in `.parquet`, else CSV) and
`hl.read_events(path)` reads it back.

The **fingerprint** of a log is the SHA-256 of its canonical CSV form (`hl.fingerprint(events)`).
Every run computes it, also when the log is not kept, and it is written into every result row. Two
runs with the same fingerprint have identical event logs. Use it to check that a study gives the
same events on another machine: `handoverlab verify --results results.json --sample 5` repeats
five stored runs and compares fingerprints and metrics.

## 9. Verification and debug mode

`handoverlab verify` runs these check groups (about two minutes) and prints a report:

| Group | Checks |
|---|---|
| `pathloss` | TR 38.901 path loss, breakpoint and LOS probability against values computed by hand |
| `radio` | shadowing standard deviation and correlation, LOS share against the LOS probability, time-varying part, L1 error, L3 filter |
| `invariants` | built-in rules in debug mode on a stressed scenario, conservation of all counts, determinism, independence of rules, global random state |
| `equivalences` | CHO with immediate execution = A3; a plug-in that reduces to A3 = A3 |
| `fingerprints` | golden event-log fingerprints of eight short reference runs |

`--only GROUP ...` selects groups, `--full` uses more seeds and longer runs, `--ns3` adds the
comparison with stored ns-3 / 5G-LENA results (a few minutes), `--results FILE` recomputes a stored
study, `--json OUT` writes the report. The exit status is 0 if no check failed. On another NumPy or
SciPy build than the reference, golden fingerprints may differ in single events; the report says so
and then requires only the counts to agree. Details and the results of this version:
[verification.md](verification.md).

**Debug mode** (`debug=True` in `simulate`, `run_world` and `Engine`; `handoverlab run --debug`;
or the environment variable `HANDOVERLAB_DEBUG=1`) checks the invariants of the engine at every
step: valid connection states and serving cells, T310 only while connected, no attempt towards the
serving cell, an execution always belongs to an attempt, finite SINR, one outcome per attempt,
event-log times in order, valid shapes and no NaN in the values a rule returns, and a read-only
observation for the rule. A violation raises `hl.InvariantError` naming the time, the users and the
rule. Debug mode changes no result and roughly doubles the run time. The conservation checks at the
end of a run (attempts = sum of outcomes, failures = sum of causes, every attempt has one outcome,
preparations = lost + cancelled + used + unused + open) always run.

## 10. Limitations

- Received-power level only: no link-level physical layer, no fast fading, no HARQ, no beam
  management (one beam gain and one isolation factor), no packet-level protocol stack.
- The failure model follows the TR 36.839 approach and is not calibrated in absolute terms; failure
  rates are best read relative to each other.
- The radio map of a large grid takes some time and memory to build (for the default 3 x 3 grid at
  100 m spacing, 76 sites and 0.2 million street pixels: about 17 s on a modest machine, see
  [performance.md](performance.md)). Use a larger `site_spacing_m`, a coarser `map_res_m` or fewer
  blocks for quick experiments.
- Results are bit-identical for the same seed, version and machine. Across NumPy/SciPy builds or
  platforms, averaged quantities can differ in the last bits and, rarely, a single threshold event can
  move; event-log fingerprints show whether this happened.
- Compared with ns-3 / 5G-LENA, handover and unnecessary-handover rates agree (median ratios 0.95 and
  1.04 over 24 A3 settings), failure rates do not (see [verification.md](verification.md)).
