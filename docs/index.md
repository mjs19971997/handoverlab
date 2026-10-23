# HandoverLab

HandoverLab is a system-level handover simulator for 5G-Advanced and beyond-5G research, written in
Python. It simulates 3GPP mobility procedures (baseline handover with Event A3, Release-16 conditional and DAPS
handover, Release-18 L1/L2-triggered mobility, conditional LTM, conditional handover with the location events of
Release 18) for many users moving through a street grid, an open area, along a highway, in an indoor office,
across rural cells or under the beams of a LEO satellite, with a TR 38.901 received-power radio model, an L3-filtered measurement chain, a
radio-link failure model and an outcome label for every handover attempt. Every rule compared on
a seed runs on the same world and radio samples, so comparisons are paired.

Install it from PyPI with `python -m pip install "handoverlab[report,gui]"`, or from source to
get the examples and the tests:

```bash
git clone https://github.com/mjs19971997/handoverlab.git && cd handoverlab
python -m pip install -e ".[report,gui]"
handoverlab run examples/smoke.yaml          # two rules, two seeds, a few seconds
handoverlab gui                              # the dashboard in your browser
```

## Where to start

| You want to | Read |
|---|---|
| run something now | [Tutorial 1: your first run](tutorials/first-run.md) |
| try scenarios and rules interactively | [the dashboard](guides/dashboard.md) |
| test your own handover rule | [Tutorial 2: writing your own rule](tutorials/own-rule.md) |
| compare rules fairly | [Tutorial 3: a fair tuning study](tutorials/tuning-study.md) |
| understand a study report | [Tutorial 4: reading the report](tutorials/reading-the-report.md) |
| look up a configuration key, metric or command | [user guide](user_guide.md), [command line](reference/cli.md), [API](reference/api/index.md) |
| add a scenario, use many cores, export event logs, reproduce a result | the how-to guides: [scenario](guides/add-scenario.md), [many cores](guides/many-cores.md), [event logs](guides/export-event-logs.md), [reproduce](guides/reproduce.md) |
| study DAPS handover, LTM, a learning rule, the upper mid-band or a highway | [DAPS and LTM](guides/daps-ltm.md), [learning rule](guides/learning-rule.md), [upper mid-band](guides/upper-mid-band.md), [highway](guides/highway.md) |
| know what stays stable between versions | [stability policy](stability.md), [metric names](reference/metrics.md) |
| know how far to trust the results | [verification](verification.md), [failure-model calibration](calibration.md) |

## What is in the box

- **Scenarios**: the TR 37.885 urban grid with buildings, an open area with hexagonal sites and the
  TR 37.885 highway with roadside sites;
  six built-in [scenario cards](scenarios/smoke.md) with the source of every parameter.
- **Rules**: Event A3, conditional handover, DAPS handover, L1/L2-triggered mobility and a
  learning-based example, and a small interface for your own rules with a contract test kit.
- **Studies**: equal-budget tuning with automatic gates (including widening a grid whose winner
  sits on its edge), paired statistics, stored and resumable results in worker processes, a status
  view with the time still needed, and Markdown/HTML reports.
- **Event logs** at three levels (off, summary, full) with a fingerprint of every run.
- **Verification**: hand-computed path loss, radio statistics, invariants, golden fingerprints, a
  regression against the prototype the package was ported from, and a comparison with ns-3 /
  5G-LENA.

This is release 2.4.1. The public surface follows the
[stability policy](stability.md). HandoverLab is MIT licensed; the source is on [GitHub](https://github.com/mjs19971997/handoverlab).
