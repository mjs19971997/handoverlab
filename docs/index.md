# HandoverLab

HandoverLab is a system-level simulator for studying handover in dense 5G and beyond-5G
networks, written in Python. It simulates the 3GPP Release-16 mobility procedures (baseline
handover with Event A3, and conditional handover) for many users moving through a street grid or
an open area, with a TR 38.901 received-power radio model, an L3-filtered measurement chain, a
radio-link failure model and an outcome label for every handover attempt. Every rule compared on
a seed runs on the same world and radio samples, so comparisons are paired.

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
| know how far to trust the results | [verification](verification.md), [failure-model calibration](calibration.md) |

## What is in the box

- **Scenarios**: the TR 37.885 urban grid with buildings and an open area with hexagonal sites;
  four built-in [scenario cards](scenarios/smoke.md) with the source of every parameter.
- **Rules**: Event A3 and conditional handover, and a small interface for your own rules with a
  contract test kit.
- **Studies**: equal-budget tuning with automatic gates (including widening a grid whose winner
  sits on its edge), paired statistics, stored and resumable results in worker processes, a status
  view with the time still needed, and Markdown/HTML reports.
- **Event logs** at three levels (off, summary, full) with a fingerprint of every run.
- **Verification**: hand-computed path loss, radio statistics, invariants, golden fingerprints, a
  regression against the prototype the package was ported from, and a comparison with ns-3 /
  5G-LENA.

HandoverLab is alpha software (version 0.4.0a1): interfaces may change until 1.0. It is MIT
licensed; the source is on [GitHub](https://github.com/mjs19971997/handoverlab).
