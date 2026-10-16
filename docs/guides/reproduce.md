# How to reproduce and check results

Every run is fixed by its scenario, seed, rules and the HandoverLab version; every result carries
the SHA-256 fingerprint of its event log. That is enough to repeat a result on another machine and
to see whether it is the same down to the last event.

## Keep what a run needs

- Write results as JSON (`-o results.json`): the file holds the schema version, the resolved
  scenario (every value explicit), the versions of HandoverLab, Python, NumPy and SciPy, and for
  every run the rule key, its parameters, the metrics and the fingerprint.
- For studies, keep the study directory: `study.lock.json` (the resolved study and its hash),
  `manifest.json` (versions and sessions) and the job records are what `handoverlab report` and a
  later check need.
- Note the exact version: `handoverlab --version`. Within a major release the file formats stay
  readable (see [stability](../stability.md)); results are only guaranteed identical with the same
  version and the same NumPy and SciPy builds.

## Repeat stored runs

```bash
handoverlab verify --results results.json              # repeat every run and compare
handoverlab verify --results results.json --sample 5   # five runs chosen at random
```

Each repeated run is compared with its stored fingerprint and metrics. Identical fingerprints mean
identical event logs; the report also states the largest relative difference of a metric. The exit
status is 0 only if every check passed, so the command can guard a pipeline.

## Check the installation

```bash
handoverlab verify                     # all check groups, about two minutes
handoverlab verify --only fingerprints # the golden event-log fingerprints only
```

The golden fingerprints are short reference runs stored with the package. On the NumPy and SciPy
build and the system of the reference they must be identical. On another build or operating system
the random streams and floating-point sums may differ in the last bits and move single events: the
report then says so and requires only the event counts to agree within 10 % (or 3 events). The
project's nightly workflow runs these checks on Linux and Windows and compares the fingerprints of
both systems with each other and with the reference.

## When fingerprints differ

1. Compare the versions in the result file (`provenance`) with `handoverlab --version` and
   `python -c "import numpy, scipy; print(numpy.__version__, scipy.__version__)"`.
2. Run `handoverlab verify --only fingerprints`. If the golden runs agree only in their counts,
   the difference comes from the numerical libraries, not from your configuration; metrics then
   agree within their sampling error but single events differ.
3. If the golden runs are identical but your runs are not, the inputs differ: check the resolved
   scenario in both result files (a changed default, a different built-in scenario card, or a rule
   plug-in of another version).
4. For a rule of your own, check that it draws random numbers only from `ctx.rng` and keeps no
   state between runs (`handoverlab.testing.check_rule` tests both).
