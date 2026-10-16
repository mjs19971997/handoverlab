# Changelog

All notable changes to this project are documented in this file. The format follows
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/) for the public surface described in
[docs/stability.md](docs/stability.md); before 1.0.0 any interface could change.

## [Unreleased]

## [1.0.0rc2] - 2026-10-15

Second release candidate (stage 6: additive features). Everything is added next to what was there:
the defaults, the results of `a3` and `cho`, the golden fingerprints and the bh6 regression are
unchanged, and the model version stays 1. The public surface only grew; the snapshot
`tests/data/public_api.json` was extended deliberately (see below).

### Added

- DAPS handover (Rel-16): rule base class `DAPSRule` (family `daps`, hooks of `BaselineRule`;
  attributes `interruption_s`, `fallback`, `source_data`) and the built-in rule `daps` (`DAPS`).
  The source keeps serving during the execution (interruption `interruption_s`, default 0); an
  execution that cannot join the target falls back to the source if its SINR is at least Qout
  (outcome `too_early`, new event-log cause `daps_fallback`, not a failure). With
  `fallback: false, source_data: false` it equals `a3`.
- L1/L2-triggered mobility (Rel-18): rule base class `LTMRule` (family `ltm`, hooks `prep_offsets`
  and `switch_offsets`; attributes `report_offset_db`, `ttt_prep_s`, `n_max`, `release_hys_db`,
  `stick_db`, `ttt_switch_s`, `cmd_delay_s`, `exec_s`, `recovery`) and the built-in rule `ltm`
  (`LTM`): candidates configured on L3 reports, cell switch decided by the network on unfiltered L1
  measurements, cell switch command with its own delay and loss, short execution, optional recovery
  into a candidate.
- A learning-based example rule `a3_bandit` (`BanditA3`): Event A3 whose offset every cell learns
  with an epsilon-greedy bandit from the outcome labels; NumPy only.
- `Observation.l1_dbm`: the unfiltered L1 samples of the measurement instant (appended field with a
  default, so existing rules and code that builds observations keep working).
- Built-in scenario `fr3-urban-15ghz`: the default grid in the upper mid-band at 15 GHz with a
  400 MHz carrier and 3.5 dB more beam gain, with its scenario card.
- Event-log kinds `daps` and `ltm`; trace events `switch` (LTM cell switch command) and `fallback`
  (DAPS); `serving_cells` returns the source after a fallback.
- `handoverlab.rules.RULE_BASES` and `handoverlab.testing.FAMILIES`; the contract kit and
  `register_rule` accept `DAPSRule` and `LTMRule` rules.
- Documentation: the procedures in the user guide; how-to guides for DAPS and LTM, for using and
  writing a learning-based rule, and for the upper mid-band.
- Tests of the DAPS, LTM and bandit trigger and update logic on prescribed received powers, and
  their contract checks.

### Changed

- Version 1.0.0rc2.
- The public-surface snapshot now also lists the hooks and attributes of `DAPSRule` and `LTMRule`,
  the new exports (`DAPS`, `LTM`, `DAPSRule`, `LTMRule`, `BanditA3`, `RULE_BASES`), the
  observation field `l1_dbm` and the trace events `switch` and `fallback`. Nothing was removed or
  renamed.
- Engine internals (not public): a procedure may set its execution time, its user-plane
  interruption, a fallback to the source and data on the source during the execution; the
  conditional procedure is split into execution and reporting steps that the LTM procedure reuses.
  Results of the existing procedures are bit-identical.

## [1.0.0rc1] - 2026-10-15

Release candidate for 1.0.0 (stage 5: release readiness). Results are unchanged: the golden
fingerprints and the bh6 regression pass, and the model version stays 1.

### Added

- Schema version of the file formats (`handoverlab.stability.SCHEMA_VERSION`, 1): experiment and
  study files accept a top-level `schema` key, and result JSON files and `study.lock.json` carry
  it. A file without the key is read as schema 1; a file with a newer schema is refused with a
  message that names it. `handoverlab init`, the examples and the dashboard's experiment file
  write `schema: 1`.
- Stability policy (`docs/stability.md`): what the public surface is (configuration keys, result
  columns, metric names, the rule interface, the documented Python names and commands), what a
  major, minor or patch release may change, and how deprecations work.
- `handoverlab.stability`: `RULE_API_VERSION` (1), `METRIC_ALIASES` with `metric_name` (an old
  metric name keeps working with a warning; study files resolve metric names through it),
  `deprecated` and `deprecated_alias` raising `HandoverLabDeprecationWarning` (a `FutureWarning`),
  `check_schema`, and `public_surface`, a snapshot of the public names, rule hooks and record
  fields, metrics, event and trace fields, and configuration keys. A test compares it with
  `tests/data/public_api.json`, so that no part of the surface changes unnoticed.
- How-to guides: add a scenario, run a study on many cores, export event logs and traces, and
  check results against the stored fingerprints.
- CI: a lint job (ruff, plus the release-metadata check) and a minimum total test coverage of
  85 % (90 % at this release) in the Linux / Python 3.12 test job; a scheduled nightly
  workflow that runs the long verification on Linux and Windows and compares the golden
  fingerprints of both systems with each other and with the reference.
- Release plumbing (no release is made by it): a workflow that builds the sdist and the wheel,
  checks them and publishes them to PyPI with trusted publishing when a GitHub release is
  published; `.zenodo.json` for the archived DOI; `tools/release_check.py` (versions, changelog
  and citation metadata agree, tag matches the version); `docs/RELEASING.md` with the steps.

### Changed

- Version 1.0.0rc1; development status Beta.
- `CITATION.cff` gives the release version and date, and the preferred way to cite.
- The changelog links of the alpha releases point to their commits, so they resolve without
  tags; later releases compare tags.
- A few long lines were wrapped for the lint job (no change of behaviour).

## [0.4.0a1] - 2026-10-15

Fourth alpha release (stage 4: dashboard, documentation, study tooling).

### Added

- Browser dashboard (extra `gui`: Streamlit and matplotlib; `handoverlab gui [--port] [--address]
  [--headless]`): scenario and setting pickers (street grid or open area, blocks, site spacing,
  carrier frequency, path loss, users, speed profile, run length, warm-up, seeds), up to four A3 or
  CHO rules with their parameters, a run button with progress, a map of the users on the layout
  coloured by serving cell (time slider and play, with counts up to the chosen time), charts of
  handovers, unnecessary handovers, failures, failure causes, delivered rate and cumulative events,
  a metrics table, and downloads of metrics (CSV), results (JSON), event logs and traces (CSV),
  figures (PNG) and an experiment file that `handoverlab run` repeats exactly. It runs locally
  only. The logic (`handoverlab.gui.logic`) needs no Streamlit and is tested on its own; the page
  is tested headless with Streamlit's test runner.
- Event-log levels `off`, `summary` and `full` (`log_events` in `simulate`, `run_world` and
  `Engine`; `run --events FILE --event-level full`; `events: off | summary | full` in study files).
  Level `full` adds a procedure trace (`RunResult.trace`): initial serving cell, measurement
  reports, preparations, releases, configurations reaching the UE or lost, executions,
  attachments after a handover or a re-establishment, and failures; `TRACE_FIELDS`,
  `TRACE_EVENTS`, `write_trace`, `read_trace`, `trace_path` and `serving_cells` (serving cell of
  every user at given times). Study test stages at level `full` store a trace table per run.
- `run_world(progress=...)`: a callback with the share of the run simulated so far.
- `handoverlab status STUDY|DIR [--workers N]` and `handoverlab.studies.status_data`: planned,
  finished, failed and remaining jobs per stage, rule runs still to simulate, gate state, sessions
  and the time left, estimated from the study's finished jobs (world-build time and engine time per
  rule run and user-second); stages not yet plannable are counted from the study file. A study
  directory alone is enough (`load_study_dir` reads `study.lock.json`). `study --status` shows the
  same.
- Gate policy `extend` for `grid_edge` with `tuning.extend_steps` (default 2) and
  `tuning.max_extensions` (default 2): a grid whose selected value lies on its edge is widened by
  values with the spacing of the last two (never below zero for a non-negative grid, and only with
  values the rule accepts), every method is tuned again with the same budget (stored rule runs are
  reused), and this repeats up to the cap, after which a remaining edge blocks. Extensions are
  recorded with their date in `amendments.json` and `AMENDMENTS.md`, applied again on resumption,
  and listed in the report.
- Documentation: tutorials (first run, writing your own rule, a fair tuning study, reading the
  report), a dashboard guide, a command-line reference, an API reference generated from the
  docstrings (MkDocs with mkdocstrings, `mkdocs.yml`, extra `docs`), a page on the failure-model
  calibration, and a workflow that builds the site on every push and publishes it on GitHub Pages
  when the repository enables it.
- Failure-model calibration against stored ns-3 / 5G-LENA results (`docs/calibration.md`): the ns-3
  failures are characterised (96 % late handover commands, no effect of T310, dependence on the
  time-to-trigger, the preparation delay and the traffic); a Qout filter window of about 0.12 s
  fits the mean failure rate and the ranking of the 24 reference settings but fails every
  held-back set, so no calibrated preset is added and the default is unchanged.
  `handoverlab.verify.ns3.compare` and `scenario_for` take `overrides` for such experiments.
- Example `examples/speed_rule.py` (a rule plug-in with its contract check).
- CI: the dashboard tests and a headless start of the dashboard in one job.

### Changed

- `RunResult` has a new field `trace`; `Engine` accepts a level name for `log_events`.
- Study files accept `events` as a level name; `true` still means `summary` and keeps the job IDs
  of earlier versions.
- `GateResult` has a field `edges` (parameter and end of every grid edge) and the status `EXTEND`.
- `study_status` moved to `handoverlab.studies.status` (still importable from
  `handoverlab.studies`) and now applies grid extensions and shows the time left.
- Results are unchanged: the golden fingerprints and the bh6 regression pass, and the model
  version stays 1.

## [0.3.0a1] - 2026-10-15

Third alpha release (stage 3: studies).

### Added

- Studies (`handoverlab.studies`): a study file (YAML, TOML or JSON) with a scenario, a full
  factorial of conditions, tuning and test seeds, methods with tuning grids, fixed parameters and
  natural bounds, tuning settings and comparisons; every key is checked.
- Equal-budget tuning: every tuned method evaluates the same number of settings per tuning group
  (a seeded random round, then refinement one and two grid steps around the best, then random
  settings if the neighbourhood is used up), on tuning seeds only.
- Selection rule: lowest unnecessary-handover rate among the settings within a failure budget (a
  share of the failure rate of a reference rule); settings within 5 % count as equal and are
  ordered by preparation overhead, failure rate, unnecessary-handover rate and evaluation order;
  if no setting meets the budget, the lowest failure rate. Objective, constraint and tie-breaks are
  configurable.
- Automatic tuning gates with the policies `warn`, `block` and `off`: `grid_edge` (selected value
  at the edge of its grid, natural bounds excepted), `budget_binding` (the budget constrains no
  method, or the reference has too few failures), `budget_met`, `equal_budget`, `seed_overlap`
  (checked before anything runs) and `flat_optimum`. A blocking gate stops the study before the
  test stage (`GateError`, exit status 3) and names every failed gate.
- Paired statistics (`handoverlab.stats`): paired differences, t intervals, percentile bootstrap
  intervals of the mean difference and of the ratio of means, the Wilcoxon signed-rank test (exact
  null distribution with ties and zeros, or the normal approximation with tie and continuity
  corrections), Holm correction, a non-inferiority check, a planning aid and decimal rounding.
- Result storage: one atomic JSON record per job (metrics, fingerprints, parameters, timing, peak
  memory), `manifest.json` with versions and sessions, `study.lock.json` with the resolved study and
  its hash, `plan.json`, failed-job tracebacks, tuning files with every evaluated setting and the
  gate report, and the tables `runs` and `tuning` as Parquet (with pyarrow) or CSV;
  `read_table` / `write_table`.
- Resumable studies with content-hashed job IDs: re-running skips finished jobs, a changed study
  re-runs only the affected jobs, and stored rule runs (same scenario, seed, rule and parameters)
  are reused instead of simulated again.
- Parallel jobs in worker processes (`--workers`; default: the logical CPUs minus four, half of
  them below eight), one BLAS thread per process, longest jobs first, a restart of a broken pool;
  results do not depend on the worker count.
- `handoverlab study STUDY` (`--workers`, `--tuning-only`, `--dry-run`, `--status`, `--report`) and
  `handoverlab report DIR` (Markdown and self-contained HTML with tables and matplotlib figures, and
  `summary.json`); extra `report` (matplotlib).
- `EngineBatch`: the engines of all rules of a world share one step loop; `run_world(batch=True)`
  is the default and `batch=False` runs them one by one.
- Example study `examples/study_smoke.yaml`; verification check "batched engines = engines run one
  by one"; tests of the statistics, the tuning, the studies and the batched engines.
- Documentation: user-guide sections on studies and paired statistics; a validation section on the
  difference in failure rates to ns-3 / 5G-LENA; the performance page with the stage-3 changes.

### Changed

- Engine speed: with many rules per world the engines need about half the time (24 rules on the
  smoke scenario: 50.7 s down to 25.0 s; 8 rules: 16.9 s to 9.7 s; with 2 rules within the noise). Per-step work that
  changes only at measurement instants or at events (interference weight of the serving cells,
  pending handover commands) is no longer repeated every step, and the radio-link monitoring and the
  load model run on arrays over all rules. Results are bit-identical: golden fingerprints and the
  bh6 regression are unchanged.
- `python -m handoverlab` guards its entry point, so worker processes can be started from it.

## [0.2.0a1] - 2026-10-15

Second alpha release (stage 2: verification in depth).

### Added

- `handoverlab verify` command and `handoverlab.verify.run_verify()`: check groups `pathloss`
  (TR 38.901 against hand values), `radio` (radio statistics against the model parameters),
  `invariants`, `equivalences` and `fingerprints`; `--full`, `--only`, `--json`; `--ns3` for the
  reference comparison with stored ns-3 / 5G-LENA results; `--results FILE [--sample N]` to
  recompute stored runs and compare event-log fingerprints and metrics.
- Debug mode of the engine (`debug=True`, `handoverlab run --debug`, `HANDOVERLAB_DEBUG=1`) with
  invariant checks at every step, validation of the values returned by rules and a read-only
  observation; `InvariantError`.
- More conservation checks at the end of every run: every attempt gets exactly one outcome, and
  every preparation ends as lost, cancelled, used, unused or open (also across the warm-up).
- Event-log fingerprints (`handoverlab.eventlog`): SHA-256 of a canonical CSV form, computed for
  every run (`RunResult.fingerprint`, `n_events`) and stored in CSV and JSON results together with
  the rule key.
- Event logs as tables: `write_events` (Parquet with `pyarrow`, else CSV; extra `parquet`),
  `read_events`, typed column catalogue `EVENT_COLUMNS`; `run --events` accepts `.parquet`.
- Golden event-log fingerprints of eight short reference runs (`handoverlab/verify/data/golden.json`,
  regenerated with `python -m handoverlab.verify.golden --write`).
- Contract test kit for rule plug-ins: `handoverlab.testing.check_rule` and the example plug-in
  `ScaledA3`.
- Built-in scenarios with scenario cards (`smoke`, `urban-grid-10ghz`, `open-area-10ghz`,
  `ns3-urban-3.5ghz`): YAML cards in the package, Markdown pages and layout drawings in
  `docs/scenarios`, `handoverlab scenarios`, `builtin_scenario()`, `scenario: NAME` and
  `scenario: {base: NAME, ...}` in configuration files.
- Protocol switch `cfg_loss_as_failure` (check mode) for the equivalence "CHO with immediate
  execution = A3".
- Reference data of an ns-3 / 5G-LENA study (24 A3 settings, four conditions) with acceptance
  limits; result of this version: median ratios 0.95 (handovers) and 1.04 (unnecessary handovers),
  rank correlation 0.99 for both.
- Wider regression sample against the bh6 prototype (eight more cases with four rules each,
  metrics and event logs).
- Documentation: verification and performance pages, user-guide sections on scenarios, event logs,
  verification, debug mode and the contract kit.

### Changed

- The world build is about a third faster (path loss, LOS state, random fields, line of sight);
  results are bit-identical.
- The engine always keeps its event log internally to compute the fingerprint; `RunResult.events`
  is still set only when requested. Event-log values are plain Python numbers.
- Result CSV files have the new columns `fingerprint` and `n_events`; JSON records also hold `key`.

## [0.1.0a1] - 2026-10-15

First alpha release (stage 1: the core simulator).

### Added

- `handoverlab` package (src layout, Python 3.9 or later; NumPy, SciPy, PyYAML).
- Scenarios: TR 37.885 urban street grid with a configurable number of blocks (default 3 x 3),
  open area with a hexagonal site grid, explicit site lists.
- Channel: TR 38.901 UMi street canyon and UMa path loss and LOS probability; building line of
  sight plus the spatially consistent LOS state; place-tied correlated shadowing with an optional
  share that moves with the user; time-varying component; L1 measurement error; beam gain and
  load-coupled interference.
- Mobility: street-following users with turn probabilities, random waypoints, speed profiles and
  user-defined speed groups.
- Measurement chain: L1 samples, TS 38.331 L3 filter, Event A3 with time-to-trigger, periodic
  reporting.
- Handover procedures: baseline handover and Rel-16 conditional handover (up to 8 prepared cells),
  with a radio-link failure model (Qout/Qin, N310/N311/T310, re-establishment, CHO recovery).
- Rule interface (`BaselineRule`, `ConditionalRule`) with a registry, a decorator and the
  `handoverlab.rules` entry-point group; built-in rules `a3` and `cho`.
- Outcome label for every attempt, failures by cause, preparation, interruption and service
  metrics; conservation checks at the end of every run.
- Configuration as YAML, TOML, JSON or dictionary, with key-level validation messages.
- Command line `handoverlab run | rules | init`, CSV and JSON result files, event-log export.
- Tests: path loss, L3 filter, A3 and CHO triggers, failure model, configuration, command line,
  determinism, and a regression test against the bh6 prototype on a 2 x 2-block grid.
- Documentation: README, user guide, contribution guide, citation file; CI on Linux, Windows and
  macOS with Python 3.9-3.12.

[Unreleased]: https://github.com/mjs19971997/handoverlab/compare/v1.0.0rc2...HEAD
[1.0.0rc2]: https://github.com/mjs19971997/handoverlab/compare/v1.0.0rc1...v1.0.0rc2
[1.0.0rc1]: https://github.com/mjs19971997/handoverlab/compare/e93b9c59e5a42665a47be91922ddd5aede998367...v1.0.0rc1
[0.4.0a1]: https://github.com/mjs19971997/handoverlab/compare/b0802c5c18634506e47a19454ca9b51293e712d7...e93b9c59e5a42665a47be91922ddd5aede998367
[0.3.0a1]: https://github.com/mjs19971997/handoverlab/compare/a5ce5dd706c225c89c13a49fea239a89a1f56cb7...b0802c5c18634506e47a19454ca9b51293e712d7
[0.2.0a1]: https://github.com/mjs19971997/handoverlab/compare/803b849719342e96dabcf430e819d3dfcb96caf0...a5ce5dd706c225c89c13a49fea239a89a1f56cb7
[0.1.0a1]: https://github.com/mjs19971997/handoverlab/tree/803b849719342e96dabcf430e819d3dfcb96caf0
