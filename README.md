# HandoverLab

A system-level simulator for studying handover in dense 5G and beyond-5G networks, written in Python.

HandoverLab simulates 3GPP Release-16 mobility procedures (baseline handover with Event A3, and
conditional handover) for many users moving through a street grid or an open area, with a
received-power-level radio model from TR 38.901, an L3-filtered measurement chain, a radio-link
failure model, and an outcome label for every handover attempt.

> **Status: alpha, stage 3 (0.3.0a1).** On top of the core simulator (stage 1) and its verification in
> depth (stage 2), HandoverLab now runs whole studies: equal-budget tuning of every rule with
> automatic gates, paired statistics, stored and resumable results in worker processes, and
> Markdown/HTML reports. Interfaces may still change until 1.0.

## What stage 3 adds

- **`handoverlab study study.yaml`**: one file describes conditions, tuning and test seeds, the
  rules with their tuning grids and the comparisons; one command runs everything.
- **Tuning on an equal budget**: every rule evaluates the same number of settings (a random round,
  then refinement around the best) on seeds that never appear in a test. Selection rule: lowest
  unnecessary-handover rate within a failure budget set by a reference rule, with fixed tie-breaks.
- **Gates that fail loudly or warn** before any test run: a selected setting on the edge of its
  grid, a failure budget that constrains nothing, unequal budgets, tuning seeds reused as test
  seeds, a flat optimum, a budget no setting meets.
- **Paired statistics** (`handoverlab.stats`): paired differences, t and bootstrap intervals,
  exact or approximate Wilcoxon signed-rank tests, Holm correction.
- **Storage and runs**: one atomic record per job, Parquet tables (CSV without pyarrow),
  content-hashed job IDs, resumption (finished jobs are skipped, stored rule runs reused), worker
  processes with `--workers` (default: leave four cores free).
- **`handoverlab report DIR`**: Markdown and HTML with tables and figures.
- **Faster engines**: the engines of all rules of a world share one step loop; with many rules per
  world (as in tuning) about half the engine time, with bit-identical results.

See the [user guide](docs/user_guide.md#10-studies), [docs/performance.md](docs/performance.md) and
the validation section of [docs/verification.md](docs/verification.md).

## What stage 2 adds

- **`handoverlab verify`**: path loss and LOS probability against hand-computed TR 38.901 values,
  radio statistics (shadowing standard deviation and correlation, LOS share, time variation, L1
  error), invariants and conservation of counts, determinism, equivalences (CHO with immediate
  execution = A3), golden event-log fingerprints; a pass/fail report and a JSON copy.
- **Debug mode** (`debug=True`, `run --debug`, `HANDOVERLAB_DEBUG=1`): invariant checks at every
  step and a read-only observation for rules; results unchanged.
- **Event-log fingerprints**: the SHA-256 of every run's event log is stored with its metrics;
  `verify --results` recomputes stored runs and compares them.
- **Event logs as tables**: Parquet (with `pyarrow`) or CSV, typed columns, read back with
  `read_events`.
- **Contract test kit** for rule plug-ins: `handoverlab.testing.check_rule`.
- **Scenario cards** for four built-in scenarios (`smoke`, `urban-grid-10ghz`, `open-area-10ghz`,
  `ns3-urban-3.5ghz`), usable by name in configuration files.
- **Wider regression** against the bh6 prototype: ten cases, 36 runs, identical metrics and event
  logs.
- **Reference comparison with ns-3 / 5G-LENA** over 24 A3 settings: handover and
  unnecessary-handover rates within the limits (median ratios 0.95 and 1.04, rank correlation 0.99);
  failure rates differ (0.13 against 0.43 per UE-minute), as documented in the validation section.
- **Faster world build**: about a third less time for the radio map, with bit-identical results.

See [docs/verification.md](docs/verification.md) and [docs/performance.md](docs/performance.md).

## What stage 1 contains

- **Scenarios**: the TR 37.885 urban street grid (configurable number of blocks, default 3 x 3, the
  minimum area of TR 37.885 Table A-1; 433 m x 250 m pitch, 20 m streets) with sites on the
  pavement, and an open area of the same size with a hexagonal site grid; explicit site lists.
- **Channel**: TR 38.901 UMi street canyon and UMa path loss (LOS/NLOS); line of sight from the
  building geometry plus the spatially consistent LOS state; spatially correlated shadowing shared by
  all users ("place-tied blockage"), optionally partly moved to a process along each user's path; a
  time-varying component; L1 measurement error; beam gain and load-coupled interference.
- **Mobility**: street-following users with turn probabilities, random waypoints in the open area,
  pedestrian and vehicular speed profiles or your own speed groups.
- **Measurements**: L1 samples, the TS 38.331 L3 filter, Event A3 with time-to-trigger, periodic
  reporting for conditional handover.
- **Handover procedures**: baseline handover (report, preparation, command, execution) and Rel-16
  conditional handover (preparation of up to 8 candidates, per-candidate execution offset and
  time-to-trigger, release, recovery into a prepared cell), behind a small rule interface.
- **Failure model**: Qout/Qin with windows, N310/N311/T310, lost commands and configurations,
  execution failures, re-establishment (TR 36.839 / TR 36.842 values by default).
- **Metrics**: outcome of every attempt (useful, unnecessary, too early, wrong cell, too late,
  censored), failures by cause, ping-pong, preparation overhead, interruption, delivered rate.
- **Reproducibility**: one world per seed shared by all compared rules (paired comparison); the
  engine draws no random numbers.

## Install from source

HandoverLab needs Python 3.9 or later. NumPy, SciPy and PyYAML are installed with it; matplotlib
(reports, extra `report`) and pyarrow (Parquet tables, extra `parquet`) are optional.

```bash
git clone https://github.com/mjs19971997/handoverlab.git
cd handoverlab
python -m pip install -e ".[test,report]"
python -m pytest            # optional: run the tests (a few minutes)
handoverlab verify          # optional: verification report (about two minutes)
```

## Quick start

Write an example configuration and run it:

```bash
handoverlab init config.yaml
handoverlab run config.yaml -o results/metrics.csv
```

`run` writes one row per seed and rule with all metrics and the fingerprint of the event log, to
CSV or (with a `.json` output name) to JSON together with the resolved scenario and the package
versions. `handoverlab rules` lists the available rules and `handoverlab scenarios` the built-in
scenarios (`scenario: smoke` in a configuration uses one). Configurations can be YAML, TOML or JSON;
see [examples/](examples).

A whole study, with tuning, gates, paired tests and a report (a few minutes):

```bash
handoverlab study examples/study_smoke.yaml --workers 2 --report
```

The report lands in `results/study-smoke/report/` (`report.html`, `report.md`, figures);
re-running the command skips everything that is already done.

## Example

```python
import handoverlab as hl

scenario = hl.Scenario.from_dict({
    "layout": {"kind": "street_grid", "blocks": [3, 3], "site_spacing_m": 150.0},
    "mobility": {"users": 20, "profile": "veh16"},
    "run": {"duration_s": 60.0, "warmup_s": 10.0},
})
rules = [
    {"rule": "a3", "name": "A3", "off_db": 3.0, "ttt_s": 0.16},
    {"rule": "cho", "name": "CHO", "o_prep_db": -2.0, "o_exec_db": 3.0, "ttt_exec_s": 0.08},
]
for r in hl.simulate(scenario, rules, seeds=[1]):      # both rules run on the same world
    print(r.rule, r.metrics["handovers_pm"], r.metrics["unnecessary_pm"], r.metrics["failures_pm"])
```

The full script is [examples/compare_a3_cho.py](examples/compare_a3_cho.py). Writing your own
handover rule takes a few lines; see the [user guide](docs/user_guide.md).

## Documentation

- [User guide](docs/user_guide.md): concepts, scenarios, configuration keys, command line, Python
  API, rule plug-ins and their contract checks, event logs, verification, metrics, studies (tuning,
  gates, storage, workers, reports), paired statistics, limitations.
- [Scenario cards](docs/scenarios): the built-in scenarios with the source of every parameter.
- [Verification](docs/verification.md) and [performance](docs/performance.md).
- [Changelog](CHANGELOG.md) and [contribution guide](CONTRIBUTING.md).

## Roadmap

1. Stage 1 (0.1.0a1): core simulator, configuration, rule interface, command line, tests.
2. Stage 2 (0.2.0a1): verification in depth (invariant checks, golden event-log fingerprints, radio
   statistics, rule contract test kit, wider bh6 regression, ns-3 reference case), event logs as
   tables, the `verify` command, scenario cards, a faster world build.
3. **Stage 3 (this release)**: studies: equal-budget tuning with automatic gates, the selection
   rule, paired statistics, job records and Parquet tables, resumable studies with reused runs,
   worker processes, `study` and `report` commands, batched engines.
4. Stage 4: tutorials and reference documentation (how-to guides for studies, plug-ins and
   calibration), event-log levels, a `status` view with remaining time per stage, the grid-edge
   policy `extend`, release 1.0 with a DOI.
5. Later: optional compiled kernels for the step loop, L1/L2-triggered mobility, further scenarios
   (highway, TR 38.901 calibration), and a browser dashboard next to the command line.

## Citation

If you use HandoverLab, please cite it as described in [CITATION.cff](CITATION.cff).

## Licence

MIT. See [LICENSE](LICENSE).

## Authors

Mostafa Jalili Sanjarani and Yasser Elmi Sola
