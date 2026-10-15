# Changelog

All notable changes to this project are documented in this file. The format follows
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/). Until 1.0.0 any interface may change.

## [Unreleased]

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

[Unreleased]: https://github.com/mjs19971997/handoverlab/compare/v0.3.0a1...HEAD
[0.3.0a1]: https://github.com/mjs19971997/handoverlab/compare/v0.2.0a1...v0.3.0a1
[0.2.0a1]: https://github.com/mjs19971997/handoverlab/compare/v0.1.0a1...v0.2.0a1
[0.1.0a1]: https://github.com/mjs19971997/handoverlab/releases/tag/v0.1.0a1
