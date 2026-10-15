# Changelog

All notable changes to this project are documented in this file. The format follows
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/). Until 1.0.0 any interface may change.

## [Unreleased]

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

[Unreleased]: https://github.com/mjs19971997/handoverlab/compare/v0.1.0a1...HEAD
[0.1.0a1]: https://github.com/mjs19971997/handoverlab/releases/tag/v0.1.0a1
