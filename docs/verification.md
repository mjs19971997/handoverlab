# Verification of HandoverLab

This page describes how HandoverLab is checked, how to run the checks yourself and what they
showed for version 0.2.0a1. All versions since 0.3.0a1 give bit-identical results (the golden
fingerprints and the bh6 regression are unchanged), so every number below still holds. Run everything with

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
| Determinism | same world twice gives identical event logs; rule order changes nothing; engines batched in one step loop = engines run one by one; another seed differs; global random state untouched; a study gives the same fingerprints with one or two worker processes | `verify` group `invariants`, `tests/test_batch.py`, `tests/test_study.py` |
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

Handover and unnecessary-handover rates agree; failure rates do not (next section). Only baseline
handover is compared, because 5G-LENA has no conditional handover; for CHO the evidence is the
equivalence "CHO with immediate execution = A3".

## Validation: the known difference in failure rates

HandoverLab gives about a third of the failure rate of ns-3 / 5G-LENA in the reference case:
**0.13 against 0.43 failures per UE-minute** (mean over the 24 A3 settings and four conditions),
with a rank correlation over the settings of only 0.54. This is a real difference between the two
models, not a sampling effect, and it is not resolved in this version. What is known about it
(version 0.3.0a1, one seed per condition; the same numbers as in 0.2.0a1):

| Condition | Failures, HandoverLab / ns-3 [1/UE-min] | Mean serving SINR, HandoverLab / ns-3 [dB] |
|---|---|---|
| 200 m, 16 m/s | 0.16 / 0.70 | 22.5 / 8.0 |
| 200 m, 30 m/s | 0.20 / 0.52 | 22.3 / 7.5 |
| 400 m, 16 m/s | 0.09 / 0.20 | 30.3 / 15.4 |
| 400 m, 30 m/s | 0.06 / 0.32 | 29.6 / 15.1 |

| A3 time-to-trigger | 100 ms | 300 ms | 500 ms | 1000 ms |
|---|---|---|---|---|
| Failures, HandoverLab / ns-3 [1/UE-min] | 0.065 / 0.031 | 0.078 / 0.140 | 0.090 / 0.436 | 0.271 / 1.119 |

- **Both simulators agree on the direction** (more failures at the smaller site distance and with a
  longer time-to-trigger), but in ns-3 the failure rate grows about 36-fold from 100 ms to 1000 ms
  and in HandoverLab only about 4-fold. At the shortest time-to-trigger HandoverLab has *more*
  failures than ns-3. The difference is therefore mainly in late handovers: ns-3 declares a link
  failure much sooner once the serving cell fades while the time-to-trigger runs.
- **The interference is defined differently.** In this scenario the interfering cells of
  HandoverLab carry about 3 % load (light traffic), so the mean serving SINR is 14-15 dB higher than
  the SINR reported by the ns-3 study, which is computed from the RSRP of all cells with every
  other cell interfering (a definition, not what the ns-3 failure detection sees). With fully loaded interfering cells (`traffic.normal_load` and `traffic.hotspot_load` set
  to 1) the mean SINR of HandoverLab matches ns-3 within 0.5 dB in every condition (8.4, 8.0, 15.7,
  15.0 dB against 8.0, 7.5, 15.4, 15.1 dB).
- **Matching the SINR does not match the failures.** With fully loaded interferers HandoverLab gives
  3.55 failures per UE-minute, eight times the ns-3 value, almost independent of the
  time-to-trigger (rank correlation -0.30), and its handover rates fall below ns-3 (median ratio
  0.85, unnecessary handovers 0.28). No single load setting reproduces both the SINR and the
  failure rate of ns-3.
- **The failure models differ.** HandoverLab declares a radio-link failure from the wideband SINR
  of the serving cell, filtered over the Qout / Qin windows, with Qout = -8 dB, N310 = 1 and
  T310 = 1 s (the TR 36.839 abstraction). The failure detection of the ns-3 study works on the
  physical-layer quantities of ns-3 rather than on this abstraction, so the same SINR trace need not
  give the same failure times. HandoverLab's failure model is therefore *not calibrated in
  absolute terms*.

**What this means for results.** Compare failure rates between rules within HandoverLab (the
tuning budgets of a study are shares of a reference rule's failure rate for this reason), and
report them as relative quantities. Do not compare an absolute failure rate from HandoverLab with
another simulator or with field data. Handover and unnecessary-handover rates, the main outputs,
agree with ns-3 within the limits above.

**Calibration attempt (version 0.4.0a1).** 96 % of the ns-3 failures are handover commands that
arrive while T310 runs, and T310 itself has no effect on their rate. One existing parameter, a Qout
filter window `protocol.qout_window_s` of about 0.12 s instead of 0.2 s, reproduces the mean
failure rate of part A (0.35-0.41 against 0.43 per UE-minute) and its ranking over the settings
(0.97), but fails every held-back set: part B is three times too high, and the response to the
preparation delay and to the number of users differs from ns-3. No calibrated preset is therefore
offered and the default is unchanged. The evidence, and what a calibration would need, are on the
[calibration page](calibration.md).

Reproduce the comparison with `handoverlab verify --ns3`; the fully loaded variant is the same
scenario with `traffic.normal_load: [1.0, 1.0]` and `traffic.hotspot_load: [1.0, 1.0]`.
