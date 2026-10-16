# How to export event logs

Metrics say how often something happened; the event log says when, where and to whom. A run keeps
as much history as its event-log level asks for: `off` (the default; only the fingerprint),
`summary` (one row per handover attempt and per failure without a handover) or `full` (also the
procedure trace). The level never changes a result. Columns and units are listed in the
[user guide](../user_guide.md#8-event-logs-and-fingerprints).

## From the command line

```bash
handoverlab run examples/smoke.yaml --events results/smoke-events.parquet
handoverlab run examples/smoke.yaml --events results/smoke-events.csv --event-level full
```

The first writes the event logs of all seeds and rules as one table; the second also writes the
trace next to it (`results/smoke-events-trace.csv`). A `.parquet` name needs `pyarrow`
(`pip install "handoverlab[parquet]"`); without it HandoverLab writes CSV with the same columns and
says so.

## From Python

```python
import handoverlab as hl
from handoverlab.eventlog import serving_cells, trace_path, write_trace

sc = hl.builtin_scenario("smoke")
res = hl.simulate(sc, [{"rule": "a3"}, {"rule": "cho"}], seeds=[1, 2], log_events="full")
path = hl.write_events(res, "results/events.parquet")     # returns the path written (.csv without pyarrow)
write_trace(res, trace_path(path))

rows = hl.read_events(path)                                # list of dictionaries with typed values
late = [r for r in rows if r["outcome"] == "too_late"]

times = [10.0, 20.0, 30.0]                                 # serving cell of every user at these times
cells = serving_cells(res[0].trace, sc.mobility.users, times)
```

pandas reads the tables directly (`pandas.read_parquet`, `pandas.read_csv`).

## From a study

Set `events: summary` or `events: full` in the study file. The test stage then stores one table
per run in `events/<run>.parquet` (and `events/<run>-trace.parquet` at level `full`) inside the
study directory (CSV without `pyarrow`); tuning stages keep only fingerprints, to save space. The
columns `events` and `trace` of `tables/runs.parquet` name the files of each run.

## From the dashboard

After a run, the *Downloads* tab offers the event logs of all runs and the trace of the first seed
as CSV, together with the experiment file that repeats the run.

## Checking an exported log

Every result row holds the SHA-256 fingerprint of its event log. `hl.fingerprint(rows)` of the
rows of one run (one seed and rule, as read back by `hl.read_events`) gives the same value, so an
exported log can be matched to its result row and checked for completeness:

```python
r = res[0]
mine = [e for e in rows if e["seed"] == r.seed and e["rule"] == r.rule]
assert hl.fingerprint(mine) == r.fingerprint
```
