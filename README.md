# HandoverLab

A system-level simulator for studying handover in dense 5G and beyond-5G networks, written in Python.

HandoverLab simulates 3GPP Release-16 mobility procedures (baseline handover with Event A3, and
conditional handover) for many users moving through a street grid or an open area, with a
received-power-level radio model from TR 38.901, an L3-filtered measurement chain, a radio-link
failure model, and an outcome label for every handover attempt.

> **Status: alpha, stage 1 (0.1.0a1).** The core simulator, configuration files, the rule plug-in
> interface and the command line are in place. Interfaces may still change until 1.0.

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
python -m pytest            # optional: run the tests (about a minute)
```

## Quick start

Write an example configuration and run it:

```bash
handoverlab init config.yaml
handoverlab run config.yaml -o results/metrics.csv
```

`run` writes one row per seed and rule with all metrics, to CSV or (with a `.json` output name)
to JSON together with the resolved scenario and the package versions. `handoverlab rules` lists the
available rules. Configurations can be YAML, TOML or JSON; see [examples/](examples).

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

- [User guide](docs/user_guide.md): concepts, configuration keys, command line, Python API, rule
  plug-ins, metrics, limitations.
- [Changelog](CHANGELOG.md) and [contribution guide](CONTRIBUTING.md).

## Roadmap

1. **Stage 1 (this release)**: core simulator, configuration, rule interface, command line, tests.
2. Stage 2: verification and continuous integration in depth (invariant checks, golden event-log
   fingerprints, radio statistics checks, rule contract test kit), event logs as tables, a
   `verify` command, scenario cards.
3. Later: equal-budget tuning with automatic checks, paired statistics, resumable studies,
   L1/L2-triggered mobility, further scenarios, and a browser dashboard next to the command line.

## Citation

If you use HandoverLab, please cite it as described in [CITATION.cff](CITATION.cff).

## Licence

MIT. See [LICENSE](LICENSE).

## Authors

Mostafa Jalili Sanjarani and Yasser Elmi Sola
