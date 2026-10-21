# Tutorial 1: your first run

This tutorial installs HandoverLab, runs two handover rules on a small built-in scenario, and
shows where the numbers come from. It takes about ten minutes.

## Install

HandoverLab needs Python 3.9 or later. `python -m pip install "handoverlab[report]"` installs it
from PyPI; this tutorial uses the example files of the repository, so install it from source:

```bash
git clone https://github.com/mjs19971997/handoverlab.git
cd handoverlab
python -m pip install -e ".[report]"        # add ",gui" for the dashboard, ",test" for the tests
handoverlab --version
```

## Look at the built-in scenarios

```bash
handoverlab scenarios
```

```text
dense-urban-2layer Two-layer dense urban deployment of ITU-R M.2412 (4 GHz macro + 30 GHz micro, SSB beams)
fr3-urban-15ghz    The TR 37.885 urban grid in the upper mid-band (FR3) at 15 GHz
highway-tr37885-30ghz The TR 37.885 highway above 6 GHz (hexagonal layout, 30 GHz, SSB beams)
highway-tr37885-4ghz The TR 37.885 highway below 6 GHz (baseline layout, 4 GHz)
indoor-office-4ghz The TR 38.901 indoor office with ceiling sites at 4 GHz
ns3-urban-3.5ghz   Reference scenario of the comparison with ns-3 / 5G-LENA
ntn-leo600-2ghz    A LEO satellite at 600 km with 19 earth-moving beams in the S band (NTN)
open-area-10ghz    Open area with hexagonal sites, nothing tied to place
rural-700mhz       Rural macro cells at 700 MHz
smoke              Small street grid that runs in seconds
urban-grid-10ghz   Dense small cells in the TR 37.885 urban grid at 10 GHz
urban-grid-28ghz-beams Small cells with SSB beams and beam failure recovery in the TR 37.885 urban grid at 28 GHz (FR2)
```

`smoke` is a 2 x 2-block street grid with sites every 150 m and 20 users for 30 s. It runs in
seconds and is the scenario of every tutorial. `handoverlab scenarios smoke` prints its card with
the source of every parameter ([scenario cards](../scenarios/smoke.md)).

## Run an experiment file

[`examples/smoke.yaml`](https://github.com/mjs19971997/handoverlab/blob/main/examples/smoke.yaml)
runs Event A3 and conditional handover (CHO) on two seeds:

```yaml
scenario:
  base: smoke                  # 2 x 2-block grid, 150 m sites, 20 users, 30 s
  mobility: {users: 10}        # values given here change the built-in scenario
seeds: [1, 2]
rules:
  - {rule: a3, name: A3, off_db: 3.0, ttt_s: 0.16}
  - {rule: cho, name: CHO, o_prep_db: -2.0, o_exec_db: 3.0, ttt_exec_s: 0.08, n_max: 4}
output: results/smoke.json
```

```bash
handoverlab run examples/smoke.yaml
```

```text
seed 1: 2 rules in 8.1 s
seed 2: 2 rules in 8.4 s
rule          seed handovers_pm unnecessary_  pingpong_pm  failures_pm prepared_cel
A3               1      11.7600       4.3200       1.2000       0.0000       0.0000
CHO              1      12.0000       4.5600       1.4400       0.0000       0.0979
A3               2       7.9200       0.9600       0.4800       0.2400       0.0000
CHO              2       8.8800       1.6800       0.7200       0.0000       0.0894
wrote results/smoke.json
```

Times depend on the machine; the numbers do not (same version, same platform). The numbers are those of
2.0.0; 1.x gave other values, as its defaults differed ([moving from 1.x to 2.0](../migration-2.0.md)).

**What happened.** For each seed HandoverLab built one *world*: the site layout, the radio map
(line of sight, path loss, shadowing), the trajectories of the users and their services. Both rules
then ran on that world with identical radio samples. A3 and CHO on seed 1 therefore saw exactly
the same channel; their difference comes only from the rule. Compare rules seed by seed.

**What the columns mean.** Rates are per UE-minute of the measured part of the run (after the
warm-up of 5 s):

- `handovers_pm`: completed handovers;
- `unnecessary_pm`: completed handovers after which the user stayed shorter than the minimum time
  of its service, or gained too little SINR, while the old cell would not have failed;
- `pingpong_pm`: handovers back to the previous cell within one second;
- `failures_pm`: mobility failures (radio-link failures, lost commands, failed executions);
- `prepared_cells_mean`: cells held in preparation per user (CHO only).

The JSON file also holds the resolved scenario, every metric, the timing and the SHA-256
*fingerprint* of each run's event log; two runs with the same fingerprint produced identical
events. The full metric catalogue is in the [user guide](../user_guide.md#7-metrics).

## Keep the event log

```bash
handoverlab run examples/smoke.yaml --events results/smoke_events.csv
handoverlab run examples/smoke.yaml --events results/smoke_events.csv --event-level full
```

The first command writes one row per handover attempt and per failure without a handover: its
time, user, source and target cell, outcome (useful, unnecessary, too early, too late, wrong
cell) and cause. With `--event-level full` a second table, `results/smoke_events-trace.csv`, adds
the procedure: measurement reports, preparations, configurations, executions, attachments and
failures, from which the serving cell of every user can be followed over time. The level never
changes a result or a fingerprint.

## The same in Python

```python
import handoverlab as hl

sc = hl.builtin_scenario("smoke").with_overrides({"mobility.users": 10})
rules = [{"rule": "a3", "name": "A3", "off_db": 3.0, "ttt_s": 0.16},
         {"rule": "cho", "name": "CHO", "o_prep_db": -2.0, "o_exec_db": 3.0, "ttt_exec_s": 0.08}]
for r in hl.simulate(sc, rules, seeds=[1, 2]):
    print(r.rule, r.seed, r.metrics["handovers_pm"], r.metrics["failures_pm"], r.fingerprint[:12])
```

## Or in the browser

```bash
python -m pip install -e ".[gui]"
handoverlab gui
```

The dashboard opens at http://localhost:8501 and runs on your computer only. See the
[dashboard guide](../guides/dashboard.md).

## Next

- [Tutorial 2](own-rule.md): write your own handover rule and check it.
- [Tutorial 3](tuning-study.md): compare rules fairly with a tuning study.
