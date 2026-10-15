# HandoverLab

A system-level simulator for studying handover in dense 5G and beyond-5G networks, written in Python.

HandoverLab simulates 3GPP Release-16 mobility procedures (baseline handover with Event A3, and
conditional handover) for many users moving through a street grid or an open area, with a
received-power-level radio model from TR 38.901, an L3-filtered measurement chain, a radio-link
failure model, and an outcome label for every handover attempt.

> **Status: alpha, stage 2 (0.2.0a1).** The core simulator, configuration files, the rule plug-in
> interface and the command line (stage 1) are now checked in depth: invariant checks, golden
> event-log fingerprints, radio statistics against TR 38.901, a contract test kit for rule plug-ins,
> a `verify` command, scenario cards and a reference comparison with ns-3 / 5G-LENA. Interfaces may
> still change until 1.0.

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
  unnecessary-handover rates within the limits (median ratios 0.95 and 1.04, rank correlation 0.99).
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

HandoverLab needs Python 3.9 or later. NumPy, SciPy and PyYAML are installed with it.

```bash
git clone https://github.com/mjs19971997/handoverlab.git
cd handoverlab
python -m pip install -e ".[test]"
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
  API, rule plug-ins and their contract checks, event logs, verification, metrics, limitations.
- [Scenario cards](docs/scenarios): the built-in scenarios with the source of every parameter.
- [Verification](docs/verification.md) and [performance](docs/performance.md).
- [Changelog](CHANGELOG.md) and [contribution guide](CONTRIBUTING.md).

## Roadmap

1. Stage 1 (0.1.0a1): core simulator, configuration, rule interface, command line, tests.
2. **Stage 2 (this release)**: verification in depth (invariant checks, golden event-log
   fingerprints, radio statistics, rule contract test kit, wider bh6 regression, ns-3 reference
   case), event logs as tables, the `verify` command, scenario cards, a faster world build.
3. Stage 3: studies: equal-budget tuning of rules with automatic gates (grid edge, binding failure
   budget, equal budgets, seed separation), a paired statistics module, job records and Parquet
   result tables with resumable and reusable runs, reports, and the engine speed-ups of the
   performance plan (per-step work moved to measurement instants, batched engines, optional
   compiled kernels).
4. Then: tutorials and reference documentation, release 1.0 with a DOI; later L1/L2-triggered
   mobility, further scenarios, and a browser dashboard next to the command line.

## Citation

If you use HandoverLab, please cite it as described in [CITATION.cff](CITATION.cff).

## Licence

MIT. See [LICENSE](LICENSE).

## Authors

Mostafa Jalili Sanjarani and Yasser Elmi Sola
