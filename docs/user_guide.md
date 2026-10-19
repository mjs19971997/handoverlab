# HandoverLab user guide

This guide covers version 1.0.2. It explains the ideas behind a run, the built-in
scenarios, the configuration keys, the command line, the Python API, how to write and check your own
handover rule, event logs at their three levels and their fingerprints, the verification checks,
what the metrics mean, and how to run a whole study: equal-budget tuning with automatic gates
(including widening a grid), paired tests, stored and resumable results, the status view, and
reports. Step-by-step introductions are in the [tutorials](tutorials/first-run.md); the
[dashboard](guides/dashboard.md) has its own page.

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

### Highway (`layout.kind = "highway"`, since 1.0.0rc3)

The straight multi-lane road of the TR 37.885 highway case along the x axis: `layout.lanes` lanes
(default 3) of `layout.lane_width_m` (4 m) per direction over `layout.road_length_m` (2000 m),
eastbound south of the centre line and westbound north of it, no buildings. Roadside sites stand
every `layout.site_spacing_m` metres along the road, `layout.site_offset_m` beyond the road edge,
alternately on the two sides. As in the open area, the LOS state is a process along each user's
path. Vehicles keep their lane (the lateral range of their speed group is the displacement from the
lane centre, at most half a lane) and their speed; at the end of the road a vehicle turns into the
same lane of the other direction. The profiles `hwy` (70-140 km/h), `hwy70` (about 70 km/h) and
`hwy140` (126-140 km/h) are meant for it. See the how-to [highway and vehicular
scenarios](guides/highway.md).

### Sites from a file

`layout.sites_file` (since 1.0.0rc3) names a CSV file with a header row and the columns `x` and
`y` in metres (other columns are ignored; a relative path is taken from the current directory). It
is read when the scenario is loaded and fills `layout.sites`, so the coordinates are part of the
resolved scenario, of result files and of study job IDs. It works with every layout kind.

### Built-in scenarios

Six named scenarios are ready to use. Each has a *scenario card*: purpose, layout drawing, every
parameter with its source, known limitations and the reference results it was checked against
([scenario cards](scenarios/smoke.md)).

| Name | Content |
|---|---|
| [`smoke`](scenarios/smoke.md) | 2 x 2-block grid, 150 m sites, 20 users, 30 s: runs in seconds; checks and first steps |
| [`urban-grid-10ghz`](scenarios/urban-grid-10ghz.md) | the defaults: 3 x 3-block grid, 100 m sites, 10 GHz, 40 users, 120 s |
| [`open-area-10ghz`](scenarios/open-area-10ghz.md) | same rectangle without buildings, hexagonal sites, nothing tied to place |
| [`ns3-urban-3.5ghz`](scenarios/ns3-urban-3.5ghz.md) | the set-up of the comparison with ns-3 / 5G-LENA: seven sites, 3.5 GHz, light load |
| [`fr3-urban-15ghz`](scenarios/fr3-urban-15ghz.md) | the default grid in the upper mid-band (FR3): 15 GHz, 400 MHz, 3.5 dB more beam gain (since 1.0.0rc2) |
| [`highway-10ghz`](scenarios/highway-10ghz.md) | the TR 37.885 highway: 2000 m, 3 + 3 lanes, roadside sites every 500 m, vehicles at 70-140 km/h (since 1.0.0rc3) |

Use one by name (`scenario: smoke`) or as the base of your own values
(`scenario: {base: smoke, mobility: {users: 40}}`); in Python `hl.builtin_scenario("smoke")`.
`handoverlab scenarios` lists them and `handoverlab scenarios smoke` prints a card.

## 3. Configuration

An experiment file has four top-level keys, `scenario`, `seeds`, `rules` and `output`, plus the
optional `schema` (see [stability](stability.md)). Every key is
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
| `layout` | `kind` | `street_grid` | `street_grid`, `open_area` or `highway` |
| | `blocks` | `[3, 3]` | number of blocks in x and y |
| | `pitch_m` | `[433, 250]` | distance between street centre lines [m] |
| | `street_width_m` | `20` | street width [m] |
| | `site_spacing_m` | `100` | site spacing along the streets / hexagonal spacing [m] |
| | `site_offset_m` | `9` | site distance from the street centre line (highway: from the road edge) [m] |
| | `sites` | none | explicit site list `[[x, y], ...]` [m] |
| | `lanes`, `lane_width_m` | `3`, `4` | highway: lanes per direction and their width [m] (since 1.0.0rc3) |
| | `road_length_m` | `2000` | highway: length of the road [m] (since 1.0.0rc3) |
| | `sites_file` | none | CSV file with columns `x`, `y` that fills `sites` (since 1.0.0rc3) |
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
| | `penetration_db`, `penetration_sd_db` | `0`, `0` | optional (1.2.0): penetration loss of each user on all its links, drawn once per user (TR 38.901 clause 7.4.3.2: `9`, `5` for a user in a standard car) |
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
| | `lm_load`, `lm_load_per_ue` | `null`, `0` | optional (1.1.0): interferer load at link monitoring, plus a part per user served by the interfering cell; `null` and `0` keep the load of the data channel ([calibration](calibration.md)) |
| | `exec_can_fail` | `true` | `false`: the execution always joins the target (ideal random access) |
| | `rlm_holdoff_s` | `0` | optional (1.3.0): no out-of-sync on a newly joined cell for this time, as radio-link monitoring restarts there (TS 38.133 clause 8.1: `0.2`) |
| `traffic` | `services` | 5 classes | list of `{key, fiveqi, gbr, t_min_s, theta_q_db, share, rate_mbps}` |
| | `se_max` | `7.4` | spectral-efficiency cap [bit/s/Hz] |
| | `hotspot_share`, `hotspot_load`, `normal_load` | `0.25`, `[0.55, 0.85]`, `[0.05, 0.25]` | background load |
| | `load_tau_s`, `rate_scale`, `label_load` | `0.2`, `1`, `1` | load smoothing; rate multiplier; load assumed by the label |
| `mobility` | `users` | `40` | number of users |
| | `profile` | `veh16` | `ped`, `veh8`, `veh16`, `veh30`, `mix`, `c8`, `c16`, `c30`; highway: `hwy`, `hwy70`, `hwy140` |
| | `groups` | none | own speed groups `[{share, v_min, v_max, lateral_m: [lo, hi]}, ...]` |
| `run` | `duration_s`, `warmup_s` | `120`, `20` | run length; initial part not counted |

In Python, `Scenario.with_overrides({"layout.site_spacing_m": 50})` returns a changed copy.
`Scenario.to_dict()` leaves out the keys added after 1.0.0rc2 while they have their default value,
so that results and study job IDs of scenarios that do not use them are unchanged;
`to_dict(full=True)` lists every key.

### Built-in rules

| Key | Family | Parameters |
|---|---|---|
| `a3` | baseline | `off_db` (3.0), `ttt_s` (0.16), `name` |
| `cho` | conditional | `o_prep_db` (-2.0), `o_exec_db` (3.0), `ttt_exec_s` (0.08), `ttt_prep_s` (0.0), `n_max` (4, at most 8), `rel_hys_db` (3.0), `immediate` (false), `name` |
| `daps` | daps | `off_db` (3.0), `ttt_s` (0.16), `interruption_s` (0.0), `fallback` (true), `source_data` (true), `name` |
| `ltm` | ltm | `o_prep_db` (-3.0), `o_switch_db` (2.0), `ttt_switch_s` (0.08), `ttt_prep_s` (0.0), `n_max` (4, at most 8), `rel_hys_db` (3.0), `cmd_delay_s` (0.01), `exec_s` (0.02), `recovery` (true), `name` |
| `a3_bandit` | baseline | `arms_db` ([1, 2, 3, 4, 5]), `ttt_s` (0.16), `epsilon` (0.1), `epoch` (10), `w_unnecessary` (1.0), `w_failure` (2.0), `name` |

`daps`, `ltm` and `a3_bandit` were added in 1.0.0rc2; they leave the results of `a3` and `cho`
unchanged.

### Procedures

The family of a rule selects the procedure the engine runs around its decisions:

- **baseline** (`kind` `ho` in the event log): Event A3 held for the time-to-trigger, measurement
  report, preparation (`prep_s`), handover command, execution (`exec_s`, an interruption), join of
  the target if its SINR is at least Qout.
- **conditional** (`cho`, TS 38.300 clause 9.2.3.4): prepared cells with execution conditions that
  the UE evaluates itself; faster recovery into a prepared cell after a failure.
- **daps** (`daps`, Rel-16 DAPS handover, TS 38.300 clause 9.2.3.2): triggered like a baseline
  handover, but the source keeps carrying data during the execution, so the execution counts
  `interruption_s` (default 0) instead of `exec_s` in `interruption_exec_s_pm`, and the user keeps
  its rate. If the target cannot be joined while the source SINR is still at least Qout, the UE falls
  back to the source (TS 38.331 clause 5.3.5.8.3): the attempt ends as `too_early` with the cause
  `daps_fallback`, without a failure or a re-establishment. `too_early_pm` therefore includes
  fallbacks for DAPS, `failures_pm` does not. With `fallback: false, source_data: false` the rule
  gives exactly the results of `a3`.
- **ltm** (`ltm`, Rel-18 L1/L2-triggered mobility, TS 38.300 clause 9.2.3.5): candidate cells are
  configured like the prepared cells of a conditional handover (L3 reports with `o_prep_db`, at most
  `n_max`); the network then switches the UE to a candidate whose *unfiltered L1* measurement beats
  the serving cell by `o_switch_db` for `ttt_switch_s`. The cell switch command (MAC CE) reaches
  the UE after `cmd_delay_s` and is lost if T310 runs; the execution (RACH-less, with early timing
  advance) takes `exec_s`. Preparation counts (`preparations_pm`, `unused_preparations_pm`, ...)
  count candidate configurations; `recoveries_pm` counts failures recovered into a candidate.

See the how-to [DAPS handover and L1/L2-triggered mobility](guides/daps-ltm.md) and, for the
learning rule, [a learning-based rule](guides/learning-rule.md).

## 4. Command line

```text
handoverlab run CONFIG [-o OUT] [--seeds S ...] [--events FILE] [--event-level summary|full] [--debug] [-q]
handoverlab verify [--only GROUP ...] [--full] [--ns3 [--ns3-seeds N]] [--results FILE [--sample N]] [--json OUT] [-q]
handoverlab scenarios [NAME] [--markdown] [--svg FILE] [--docs DIR]
handoverlab study STUDY [-o DIR] [--workers N] [--tuning-only] [--dry-run] [--status] [--report] [-q]
handoverlab report DIR [-o OUT] [--format md html] [--no-figures]
handoverlab status STUDY|DIR [-o DIR] [--workers N]
handoverlab gui [--port N] [--address A] [--headless]
handoverlab rules
handoverlab init [PATH] [--force]
handoverlab --version
```

`run` writes one row per seed and rule. A `.csv` output has the columns `seed`, `rule`, `family`,
`fingerprint` (of the event log), `n_events`, the rule parameters (`param.*`) and all metrics; a
`.json` output also stores the resolved scenario, the rule key, the timing of every run and the
versions of Python, NumPy and SciPy. `--events` writes the event logs as one table (see section 8):
Parquet for a `.parquet` name if `pyarrow` is installed (`pip install handoverlab[parquet]`), CSV
otherwise; with `--event-level full` the procedure traces go to a second table next to it
(`events.csv` -> `events-trace.csv`). `--debug` checks the engine invariants while running
(section 9).

`verify` runs the verification checks and prints PASS, FAIL or NOTE for each (section 9).
`scenarios` lists the built-in scenarios or prints one card. `study` runs or resumes a study,
`status` shows what is left of it and how long that will take, and `report` writes its report
(section 10). `gui` starts the browser dashboard ([dashboard](guides/dashboard.md); needs
`pip install handoverlab[gui]`). `python -m handoverlab` works as well. The full option lists are
in the [command-line reference](reference/cli.md).

## 5. Python API

```python
import handoverlab as hl

sc = hl.Scenario()                                     # all defaults
exp = hl.load_config("examples/street_grid.yaml")       # or a dict
results = hl.run_experiment(exp)                        # list of RunResult
world = hl.build_world(sc, seed=1)                      # one world ...
results = hl.run_world(world, [{"rule": "a3"}, {"rule": "cho"}], log_events="summary")   # ... many rules
results[0].metrics["unnecessary_pm"], results[0].events[:3]
results[0].fingerprint                                  # SHA-256 of the event log, always set
hl.simulate(sc, [{"rule": "a3"}], seeds=[1], debug=True)   # with invariant checks
hl.write_events(results, "events.parquet")              # event table (CSV without pyarrow)
full = hl.run_world(world, [{"rule": "a3"}], log_events="full")[0]
full.trace[:3]                                          # procedure trace (section 8)
hl.run_world(world, [{"rule": "a3"}, {"rule": "cho"}], batch=False)   # engines one by one (same results, slower)
```

`run_world` advances the engines of all rules of a world in one step loop (`EngineBatch`); the
results are bit-identical to running them one by one, which `batch=False` does. Engines in debug
mode always run one by one.

## 6. Writing a handover rule

A rule subclasses `BaselineRule` (A3-based handover), `ConditionalRule` (CHO), `DAPSRule` (DAPS
handover) or `LTMRule` (L1/L2-triggered mobility) and implements a few hooks. The engine calls the
hooks; the rule never calls the engine. Each hook receives an `Observation` with arrays over users
(U) and cells (M): `meas_dbm`, `gap_db` (neighbour minus serving), `serving`, `connected`, `x`,
`y`, `speed`, `heading`, `t`, and (since 1.0.0rc2) `l1_dbm`, the unfiltered L1 samples of the
same instant.

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

A `DAPSRule` has the hooks of `BaselineRule` and sets `interruption_s`, `fallback` and
`source_data`. An `LTMRule` sets `report_offset_db`, `ttt_prep_s`, `n_max`, `release_hys_db`,
`ttt_switch_s`, `cmd_delay_s`, `exec_s` and `recovery` and implements `prep_offsets(obs)`
(candidate configuration, on L3 measurements) and `switch_offsets(obs)` (cell switch, on
`obs.l1_dbm`), each a scalar or (U, M).

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
full catalogue with units is `handoverlab.engine.METRICS`, listed in the
[metric reference](reference/metrics.md); the names are stable (see [stability](stability.md)).

**Outcome of an attempt** (exactly one per attempt; `n_attempts` equals their sum):

- `too_late`: the command or configuration was lost, or the link failed while the handover was in
  preparation;
- `too_early`: the execution failed, or the link failed in the target before the evaluation window
  closed, and the UE re-established in the source or the target; for DAPS handover also an
  execution that fell back to the source (cause `daps_fallback`, not counted as a failure);
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

A run keeps as much of its history as its *event-log level* asks for:

| Level | Kept | Typical use |
|---|---|---|
| `off` (default) | metrics and the fingerprint of the event log | tuning, large studies |
| `summary` | the event log: one row per handover attempt and per failure without a handover | test stages, causes of failures |
| `full` | the event log and the procedure trace | debugging a rule, following users, the dashboard map |

Set it with `log_events="off" | "summary" | "full"` in `simulate` and `run_world` (`True` means
`summary`), with `--events FILE --event-level summary|full` on the command line, or with
`events: off | summary | full` in a study file (`true` means `summary`). The level never changes a
result or a fingerprint. The event-log columns and units are in
`handoverlab.eventlog.EVENT_COLUMNS`:

| Column | Meaning |
|---|---|
| `seed`, `rule` | the run (in tables) |
| `t_attempt`, `t_exec`, `t_end` | start of the attempt, start of the execution (-1 if none), time of the outcome [s] |
| `ue`, `kind` | user; `ho` baseline handover, `cho` conditional handover, `daps` DAPS handover, `ltm` L1/L2-triggered mobility, `rlf` failure without handover |
| `src`, `tgt` | source cell; target cell (for `rlf`: cell of the re-establishment) |
| `outcome`, `cause` | outcome label (section 7) and failure cause |
| `dwell`, `gain_db` | time of stay in the target [s]; mean SINR gain over the evaluation window [dB] |
| `n_prepared`, `o_exec` | prepared cells at the attempt; execution or A3 offset (-99 if none) [dB] |
| `x`, `y` | position at `t_end` [m] |

`hl.write_events(results, path)` writes the logs of many runs as one table (Parquet with typed
columns if `pyarrow` is installed and the name ends in `.parquet`, else CSV) and
`hl.read_events(path)` reads it back.

The **trace** (level `full`, `RunResult.trace`) has one row per procedure event with the columns
`t`, `ue`, `event`, `src` (serving cell before the event), `cell`, `value` and `note`:

| Event | Meaning |
|---|---|
| `serve` | initial serving cell at the first step |
| `report` | baseline handover: measurement report towards `cell` (`value`: A3 offset) |
| `prepare`, `release` | conditional handover: preparation of `cell` requested (`value`: execution offset), or released |
| `config`, `config_lost` | the conditional configuration of `cell` reached the UE, or was lost |
| `exec` | execution starts: the UE leaves `src` for `cell` |
| `attach`, `reestablish` | the UE is connected to `cell` after a handover or a re-establishment (`value`: SINR in dB) |
| `switch` | LTM: cell switch command towards `cell` sent (`value`: switch offset) |
| `fallback` | DAPS: the target could not be joined; the UE stays in `src` (`value`: source SINR) |
| `failure` | mobility failure; `cell` is the cell chosen for re-establishment, `note` the cause |

`hl.eventlog.serving_cells(trace, n_users, times)` turns a trace into the serving cell of every
user at the given times (-1 while not connected); `write_trace` and `read_trace` store traces as
tables like the event logs.

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

`--only GROUP ...` selects groups, `--full` uses more seeds and longer runs, `--ns3` runs the
comparison with stored ns-3 / 5G-LENA results (a few minutes; alone, unless `--only` names groups), `--results FILE` recomputes a stored
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

## 10. Studies

A *study* compares handover rules in a controlled way: every rule with free parameters is tuned on
its own seeds with the same number of evaluated settings, a fixed rule selects one setting per
failure budget, automatic gates check that the tuning means something, and the tuned rules are
then compared on separate test seeds with paired statistics. One file describes the whole study,
one command runs it, and re-running it resumes where it stopped.

```bash
handoverlab study examples/study_smoke.yaml --dry-run     # what would run
handoverlab study examples/study_smoke.yaml --workers 2   # run or resume
handoverlab status results/study-smoke                    # finished, failed, remaining jobs, time left
handoverlab report results/study-smoke                    # report.md, report.html, figures
```

### The study file

```yaml
name: study-smoke
scenario: {base: smoke, mobility: {users: 12, profile: veh30}}
conditions:                         # full factorial over dotted scenario keys (optional)
  layout.site_spacing_m: [100.0, 150.0]
seeds:
  tuning: [901, 902]                # never used in a test
  test: {first: 1, last: 6}
tuning:
  settings: 8                       # evaluated settings per method: the same for every method
  random: 5                         # of which drawn at random; the rest refine around the best
  reference: {rule: a3, name: A3-ref, off_db: 3.0, ttt_s: 0.16}
  budgets: {standard: 1.0, strict: 0.5}   # shares of the reference failure rate
  group_by: [layout.site_spacing_m] # tune per site spacing (default: per condition)
  gates: {grid_edge: block}         # warn | block | off per gate
methods:
  A3:
    rule: a3
    grid: {off_db: [0, 1, 2, 3, 4, 5, 6], ttt_s: [0.0, 0.04, 0.08, 0.16, 0.32]}
    natural_bounds: {ttt_s: lower}  # 0 s is a floor, not an edge of the search
  CHO:
    rule: cho
    fixed: {o_prep_db: -2.0, n_max: 4}
    grid: {o_exec_db: [0, 1, 2, 3, 4, 5], ttt_exec_s: [0.0, 0.04, 0.08, 0.16, 0.32]}
compare:
  baseline: A3-ref                  # a method, METHOD@BUDGET or the reference
  metrics: [unnecessary_pm, failures_pm, handovers_pm, prepared_cells_mean]
output: results/study-smoke
```

A complete example, with four tuning seeds and the grid-edge policy `extend`, is [examples/study_smoke.yaml](https://github.com/mjs19971997/handoverlab/blob/main/examples/study_smoke.yaml). Every key is
checked; an unknown key or a parameter that the rule does not have stops the study with a message
that names it.

| Key | Meaning |
|---|---|
| `name`, `description` | name of the study (default: the file name) and a line for the report |
| `scenario` | as in an experiment file: a built-in name, `{base: NAME, ...}` or a full scenario |
| `conditions` | dotted scenario keys with lists of values; the study runs their full factorial |
| `seeds.tuning`, `seeds.test` | lists or `{first, last}`; tuning seeds are needed only for tuned methods |
| `tuning.settings` | evaluated settings per method and tuning group (default 12) |
| `tuning.random` | settings of the first, random round (default two thirds of `settings`) |
| `tuning.reference` | the rule whose failure rate sets the budgets (default A3 3 dB / 160 ms) |
| `tuning.budgets` | failure budgets as shares of the reference failure rate (default `{standard: 1.0}`) |
| `tuning.tolerance` | settings within this share of the lowest objective count as equal (0.05) |
| `tuning.group_by` | condition keys to tune per value of (default: all condition keys) |
| `tuning.gates` | policy per gate: `warn`, `block` or `off` (defaults below) |
| `tuning.binding_share`, `min_reference_failures`, `flat_share` | thresholds of the gates (0.9, 5, 0.5) |
| `tuning.objective`, `constraint`, `tie_breaks` | metrics of the selection rule (`unnecessary_pm`, `failures_pm`, `[prepared_cells_mean, failures_pm]`) |
| `tuning.extend_steps`, `max_extensions` | with `gates: {grid_edge: extend}`: values added at the edge per extension (2) and the most extension rounds (2) |
| `methods.NAME.rule` | registered rule key (built-in or plug-in) |
| `methods.NAME.grid` | parameter -> list of values; a method without a grid is not tuned |
| `methods.NAME.fixed` | parameters that stay fixed |
| `methods.NAME.natural_bounds` | grid ends that are physical limits, not search limits: `lower`, `upper` or `both` |
| `methods.NAME.settings` | an own budget (the `equal_budget` gate then blocks the study) |
| `compare.baseline` | the rule every other rule is compared with (default: the first test rule) |
| `compare.metrics`, `level`, `bootstrap`, `budget` | metrics of the report, interval level (0.95), bootstrap resamples (2000), restriction to one budget |
| `events` | event-log level of the test stage: `off` (default), `summary` (`events/<run>.parquet`) or `full` (also `events/<run>-trace.parquet`) |
| `output`, `workers` | study directory (default `results/<name>`) and worker processes |

### Stages

1. **`tune1`**: every condition and tuning seed with the reference rule and the first settings of
   every tuned method, drawn at random from its grid without repetition (seeded by the method name).
2. **`tune2`**: the rest of the budget, per tuning group: settings one grid step around the best
   setting of round 1 (under the first budget), then two steps, then, if the neighbourhood is used
   up, further random settings. Every method thus evaluates exactly `settings` settings, or its
   whole grid if that is smaller.
3. **Selection and gates** (below). A blocking gate stops the study here: `handoverlab study` exits
   with status 3 and names every failed gate; `tuned/gates.json` holds the full report.
4. **`test`**: every condition and test seed with the reference, every tuned method with its
   selected setting per budget (named `METHOD@BUDGET`) and every untuned method.

### Selection rule

The failure budget of a tuning group is a share of the mean failure rate of the reference rule on
the tuning runs of that group. Among the settings whose mean failure rate does not exceed the
budget, those within 5 % of the lowest unnecessary-handover rate count as equal; among them the
lowest preparation overhead (`prepared_cells_mean`) wins, then the lowest failure rate, then the
lowest unnecessary-handover rate, then the order of evaluation. If no setting meets the budget,
the setting with the lowest failure rate is used and flagged by the `budget_met` gate. The rule is
fixed before any result is seen; every evaluated setting and its means are stored
(`tuned/<group>.json`, `tables/tuning`), so the selection can be redone.

### Gates

| Gate | Fails when | Default |
|---|---|---|
| `grid_edge` | the selected value of a numeric parameter is the smallest or largest of its grid and that end is not a declared natural bound (per method, budget and group); policy `extend` widens the grid and tunes again (below) | block |
| `budget_binding` | more than 90 % of the settings of every method meet the budget, or the reference rule has fewer than 5 failures on the tuning runs: the budget does not constrain the trade-off | warn |
| `budget_met` | no setting of a method meets the budget | warn |
| `equal_budget` | methods evaluated different numbers of settings (except where a grid is smaller than the budget), or declared different budgets | block |
| `seed_overlap` | a tuning seed is also a test seed; checked before anything runs | block |
| `flat_optimum` | more than half of the settings within the budget lie within 5 % of the best: the tie-breaks decide | warn |

A setting on the edge of its grid means that the search may have stopped too early, and a baseline
tuned that way can make another rule look better than it is. With `block` the study stops before
any test run with a message such as `grid_edge (layout.site_spacing_m=100, A3, budget standard):
off_db = 6 is the largest grid value`. Extend the grid (or declare a natural bound) and run the
study again; finished jobs are reused.

**Policy `extend`.** With `gates: {grid_edge: extend}` the study widens the grid itself: at every
edge where a selected value sits, `extend_steps` new values are added with the spacing of the last
two grid values (`off_db: [.., 5, 6]` gains 7 and 8; a grid of non-negative values is never
extended below zero), and then *every* method is tuned again with the same budget on the widened
grids, so the budgets stay equal. Rule runs that were already simulated are reused. This repeats
until no selected value sits on an edge or `max_extensions` extension rounds were made; then a
remaining edge blocks like `block`, and so does an edge that cannot be widened (the message says
why). Every extension is recorded with its date in `amendments.json` and `AMENDMENTS.md` of the
study directory, applied again when the study is resumed, and listed in the report.

### Results, resumption and workers

```text
results/<study>/
  manifest.json            versions, platform, sessions (start, end, workers, jobs run), changes of the study file
  study.lock.json          the resolved study (every value explicit) and its SHA-256
  plan.json                job IDs of every stage of the current plan
  jobs/<stage>/<job>.json  one record per job: metrics, fingerprints, parameters, timing, peak memory
  failed/<job>.txt         traceback of a failed job (removed when it succeeds)
  events/<run>.parquet     event logs of the test stage (events: summary or full)
  events/<run>-trace.parquet  procedure traces of the test stage (events: full)
  tuned/<group>.json       every evaluated setting, the selection per budget, the gates of a group
  tuned/gates.json         the gate report of the whole study
  amendments.json          grid extensions made by the policy extend (and AMENDMENTS.md)
  tables/runs.parquet      one row per job and rule (CSV without pyarrow)
  tables/tuning.parquet    one row per evaluated setting
  report/                  report.md, report.html, summary.json, figures/
```

A *job* is one world (condition and seed) with its rules; its ID is a hash of its content (the
resolved scenario, the seed, the rules and the model version). A job record is written atomically:
it is complete or absent. Re-running a study skips every job whose record exists, so a study can be
stopped at any time and continued, also with another worker count. Changing the study file changes
only the IDs of the jobs it affects; the others are reused. A rule run (scenario, seed, rule and
parameters) that is already stored in the study, such as the reference rule or a setting that two
budgets select, is reused instead of simulated again, and if nothing is left to simulate the world
is not built at all. Tables are rebuilt from the job records after every run. A failed job leaves
its traceback in `failed/` and stops the study after its stage; the next run retries it.

`--workers N` runs N jobs in parallel, one per process, with BLAS and OpenMP threads limited to one
per process. The default leaves cores free: the logical CPUs minus four (half of them on machines
with fewer than eight). Jobs start longest first. Neither the worker count nor the order changes a
result: two runs of the same study give identical event-log fingerprints.

`handoverlab status STUDY` (a study file or directory) lists, per stage, the planned, finished,
failed and remaining jobs and the rule runs still to simulate; stages that depend on earlier
results are counted from the study file until they can be planned. It also estimates the time
left from the finished jobs of the study (world-build time and engine time per rule run, scaled by
users and simulated seconds), spread over the workers of the last session or `--workers N`:

```text
study study-smoke in results/study-smoke
  last session (1) 2026-10-15T23:59:30+00:00: stopped after tuning
  stage    jobs   done  failed  to run  rule runs
  tune1       8      8       0       0          0
  tune2       8      8       0       0          0
  test       12      0       0      12         48
  gates: pass (0 blocking, 5 warnings)
  time left: about 34 s with 2 workers (69 s CPU; measured on 16 jobs: world 2.5 s, 3.36 s per rule run of 1000 user-seconds)
```

The estimate is a guide: other conditions or rules can be slower or faster, and a busy machine is
slower.

Parquet tables need `pyarrow` (`pip install handoverlab[parquet]`); without it the tables are CSV
files with the same columns. `handoverlab.studies.read_table` reads either into a list of
dictionaries; pandas reads both directly.

### Report

`handoverlab report DIR` writes `report.md`, `report.html` (self-contained, figures embedded),
`summary.json` with every number, and the figures as PNG files (with matplotlib:
`pip install handoverlab[report]`). The report contains the provenance (versions, sessions, jobs,
simulated and reused rule runs), the tuning (budgets, selected settings, the gate table and a figure
of every evaluated setting per group), the means of every rule with t intervals (pooled and per
condition), and the paired comparisons with the baseline (section 11). `study --report` writes it
when the study is complete.

### Python

```python
from handoverlab.studies import GateError, load_study, run_study, write_report

study = load_study("examples/study_smoke.yaml")
try:
    res = run_study(study, workers=2, progress=print)
    write_report(res.root)
except GateError as e:
    print(e.lines)                       # every blocking gate
```

## 11. Paired statistics

`handoverlab.stats` holds the statistics of the report. Rules compared on the same condition and
seed share the world and the radio samples, so the unit is one run and two rules are compared
through their paired differences (rule minus baseline).

| Function | What it does |
|---|---|
| `paired_differences(a, b)` | `a - b` for paired runs |
| `t_interval(d, level)` | two-sided t interval of the mean difference |
| `bootstrap_ci(a, b, stat, n_boot, level, seed)` | percentile bootstrap of the mean difference (`"mean_diff"`) or of the ratio of the means (`"ratio"`); pairs are resampled together with a seeded generator |
| `wilcoxon_signed_rank(d, method)` | two-sided signed-rank test: zero differences dropped, mid-ranks for ties; `"exact"` builds the null distribution for the ranks present (valid with ties), `"approx"` is the normal approximation with tie and continuity corrections, `"auto"` is exact up to 500 non-zero differences |
| `holm(p)` | Holm's step-down adjustment of a family of p-values |
| `paired_summary(a, b)` | all of the above for one comparison |
| `noninferior(d, margin)` | the upper end of the one-sided interval lies below a margin |
| `seeds_needed(sd, half_width)` | paired runs for a t interval of the given half-width |
| `rnd(x, nd)` | decimal rounding half away from zero for printing (0.0975 -> 0.098) |

Per-run rates are ratios of small counts with many ties and zeros, which is why the exact rank test
is the default. In the report, the pooled comparisons of one metric form one Holm family and the
per-condition comparisons of one metric (all rules and conditions) another. With few seeds the
intervals are wide; the report shows them next to every estimate.

## 12. Limitations

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
  1.04 over 24 A3 settings), failure rates do not: 0.13 against 0.43 per UE-minute (see the
  validation section of [verification.md](verification.md)). Compare failure rates between rules
  within HandoverLab, not with absolute values from other simulators or from the field. An attempt
  to calibrate the failure model against ns-3 found no setting that holds on independent ns-3
  results ([calibration](calibration.md)).
- Tuning gates check the search, not the model: a study that passes every gate can still answer the
  wrong question if the scenario does not fit it.
