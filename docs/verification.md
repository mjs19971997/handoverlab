# Verification of HandoverLab

This page describes how HandoverLab is checked, how to run the checks yourself and what they
showed for version 0.2.0a1. Run everything with

```bash
handoverlab verify                 # about two minutes; prints PASS / FAIL / NOTE per check
handoverlab verify --full          # three seeds for the radio statistics, 60 s engine runs
handoverlab verify --ns3           # only the comparison with ns-3 / 5G-LENA (a few minutes)
handoverlab verify --results results.json --sample 5     # repeat stored runs and compare
```

The command exits with status 0 if no check failed and 1 otherwise; `--json report.json` also
writes the report with the versions of Python, NumPy and SciPy and the platform.

## Levels of checking

| Level | What is checked | Where |
|---|---|---|
| Unit tests | path loss, LOS probability, L3 filter, A3 and CHO triggers, failure model on synthetic radio samples | `tests/` |
| Invariants, end of run | attempts = sum of outcomes; failures = sum of causes; every attempt started got exactly one outcome; preparations = lost + cancelled + used + unused + open | every run |
| Invariants, debug mode | per step: valid states and serving cells, T310 only while connected, no attempt to the serving cell, an execution always belongs to an attempt, finite SINR; event-log times in order; rule outputs of valid shape without NaN; the observation given to a rule is read-only | `debug=True`, `--debug`, `HANDOVERLAB_DEBUG=1` |
| Path loss by hand | TR 38.901 UMi and UMa, LOS and NLOS, both breakpoint branches, LOS probabilities, noise | `verify` group `pathloss` |
| Radio statistics | shadowing standard deviation (LOS, NLOS), spatial correlation, correlation between sites, LOS share against the LOS probability, time-varying part, L1 error, L3 filter | `verify` group `radio` |
| Determinism | same world twice gives identical event logs; rule order changes nothing; another seed differs; global random state untouched | `verify` group `invariants` |
| Equivalences | CHO with immediate execution = A3 (three settings); a plug-in rule that reduces to A3 = A3 | `verify` group `equivalences` |
| Golden fingerprints | SHA-256 of the event logs of eight short reference runs (three scenarios, up to three rules) | `verify` group `fingerprints`, `tests/test_verify.py` |
| Regression against bh6 | ten cases, 36 runs: every metric and (for the wide sample) every event log identical to the prototype from which HandoverLab was ported | `tests/test_regression_bh6*.py` |
| Reference case | ns-3 / 5G-LENA, 24 A3 settings on four conditions | `verify --ns3` |
| Rule contract | any rule plug-in: construction, parameters, debug run, determinism, global random state, independence, optional equivalence | `handoverlab.testing.check_rule` |

## Event-log fingerprints

The fingerprint of a run is the SHA-256 of its event log written in a canonical CSV form (see
`handoverlab.eventlog`): times rounded to 0.1 ms, gains to 0.001 dB and positions to 0.1 m when the
row is written, numbers in Python's shortest round-trip form. Every run computes it, whether or not
the log is kept; it is stored in every CSV and JSON result row. It does not depend on how a log is
stored, so a log read back from CSV or Parquet has the same fingerprint as the one in memory.

NumPy promises identical random streams only for the same build on the same machine, and
floating-point sums can differ in the last bit between CPUs and BLAS builds; a handover is a
threshold decision, so such a difference can move a single event. HandoverLab therefore measures
agreement instead of assuming it: on the reference build the golden fingerprints must be identical;
on another build the check reports whether they are and requires the counts to agree within 10 % or
three events. `verify --results` reports the share of identical event logs of a stored study and the
largest relative metric difference (metrics count as equal within 1e-12).

A change that alters the golden fingerprints on purpose regenerates them with
`python -m handoverlab.verify.golden --write` and records the reason in `CHANGELOG.md`.

## Radio statistics (version 0.2.0a1, seed 3)

| Quantity | Simulated | Model |
|---|---|---|
| Shadowing standard deviation, LOS / NLOS links | 4.01 / 7.86 dB | 4 / 7.82 dB |
| Shadowing correlation at 10 m / 20 m along a street | 0.32 / -0.05 | 1/e = 0.37 at the decorrelation distance |
| Shadowing correlation between sites | 0.51 | 0.5 |
| LOS share of links clear of buildings, 20-40 / 40-80 / 80-160 / 160-320 m | 0.74 / 0.45 / 0.24 / 0.10 | 0.79 / 0.45 / 0.19 / 0.08 (TR 38.901 UMi) |
| Time-varying part: standard deviation, correlation after 1 s | 1.50 dB, 0.37 | 1.5 dB, 1/e |
| L1 sample error: standard deviation, mean | 1.000 dB, -0.0007 dB | 1 dB, 0 |

The Gaussian random fields have the correlation exp(-(d/d_corr)^2), which equals the 1/e of
TR 38.901's exponential model at the decorrelation distance but falls faster beyond it.

## Regression against the bh6 prototype

HandoverLab was ported from the research prototype bh6 and keeps its random-stream layout, the
order of all random draws and the order of the floating-point operations. Two samples are stored:

- `tests/data/bh6_reference.json`: two cases (default and stressed) with A3 and CHO;
- `tests/data/bh6_wide.json`: eight cases (site distances 50-150 m, pedestrian to 30 m/s, mixed
  speeds, open area, half the shadowing moving with the user, UMa at 3.5 GHz, no clutter, N310 =
  N311 = 2 with T310 = 0.5 s, label load 0.5 with 100 ms preparation and 20 ms L1 period) with four
  rules each (two A3 settings, CHO, CHO with immediate execution), about 2,500 events in all.

On the reference build every metric of all 36 runs is equal to the last bit and every event log of
the wide sample is identical (its fingerprint is stored). On other builds the tests require close
agreement only.

## Reference comparison with ns-3 / 5G-LENA

The scenario card [`ns3-urban-3.5ghz`](scenarios/ns3-urban-3.5ghz.md) describes the set-up, which was
also simulated with the packet-level simulator ns-3 and its 5G-LENA module. The stored ns-3 results
(`handoverlab/verify/data/ns3_urban_a3.json`) cover 24 Event-A3 settings (offset 1-6 dB,
time-to-trigger 100-1000 ms) on four conditions (site distance 200 / 400 m, 16 / 30 m/s). Seeds are
different realisations, so the comparison uses the mean over the four conditions per setting.

Result of 0.2.0a1 with one seed per condition:

| Quantity | Limit | Result |
|---|---|---|
| Handover rate, median ratio HandoverLab / ns-3 | 0.8-1.25 | 0.95 |
| Unnecessary-handover rate, median ratio | 0.8-1.25 | 1.04 |
| Handover rate, rank correlation over the settings | >= 0.9 | 0.99 |
| Unnecessary-handover rate, rank correlation | >= 0.9 | 0.99 |
| Failure rate, mean (no limit) | | 0.13 against 0.43 per UE-minute, rank correlation 0.54 |
| Mean serving SINR (no limit) | | 26.2 against 11.5 dB |

Handover and unnecessary-handover rates agree; failure rates do not, as expected: the two
simulators define the load of interfering cells differently (the SINR difference shows it) and the
failure model of HandoverLab is not calibrated in absolute terms. Report failure rates relative to
each other. Only baseline handover is compared, because 5G-LENA has no conditional handover; for
CHO the evidence is the equivalence "CHO with immediate execution = A3".
