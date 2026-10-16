# SPDX-License-Identifier: MIT
"""Event logs: fingerprints and tables.

An event log has one row per handover attempt and per link failure without a
handover (see :data:`EVENT_FIELDS`).  Times are rounded to 0.1 ms, gains and
offsets to 0.001 dB and positions to 0.1 m when the engine writes a row.

Fingerprint
    The SHA-256 of the *canonical CSV* of a log: a header with the field
    names, then one line per row in log order, fields separated by commas,
    numbers written with Python's shortest round-trip representation
    (``repr(float)``; ``-0.0`` is written as ``0.0``), lines ending in ``\\n``.
    It does not depend on how the log was stored (CSV, Parquet, memory), so
    a stored log can be checked against a recomputed one on any machine.

Levels
    How much a run keeps (:data:`LEVELS`, :func:`event_level`):

    ``off``      metrics and the fingerprint only (the default; tuning stages);
    ``summary``  the event log above (``RunResult.events``);
    ``full``     the event log plus a *trace* of the procedure
                 (``RunResult.trace``, :data:`TRACE_FIELDS`): the initial
                 serving cell of every user, measurement reports,
                 preparations, releases, configurations reaching the UE or
                 lost, executions, attachments after a handover or a
                 re-establishment, and failures.  The trace gives the serving
                 cell of every user at any time (:func:`serving_cells`).

    The level never changes a result or the fingerprint: the fingerprint is
    always that of the summary log.

Tables
    :func:`write_events` writes the logs of several runs as one table with the
    columns ``seed``, ``rule`` and :data:`EVENT_FIELDS`: Parquet (typed
    columns, needs ``pyarrow``) for a ``.parquet`` file name, CSV otherwise.
    :func:`read_events` reads either back; :func:`write_trace` and
    :func:`read_trace` do the same for traces.
"""
from __future__ import annotations

import csv
import hashlib
import os
import warnings
from typing import Any, Dict, Iterable, List, Sequence, Tuple

EVENT_FIELDS: Tuple[str, ...] = ("t_attempt", "t_exec", "t_end", "ue", "kind", "src", "tgt", "outcome", "cause",
                                 "dwell", "gain_db", "n_prepared", "o_exec", "x", "y")

#: column -> (type, unit, meaning)
EVENT_COLUMNS: Dict[str, Tuple[type, str, str]] = {
    "seed": (int, "", "seed of the world"),
    "rule": (str, "", "name of the rule"),
    "t_attempt": (float, "s", "start of the attempt (report for baseline handover, execution for CHO); "
                              "failure time for kind 'rlf'"),
    "t_exec": (float, "s", "start of the execution, -1 if there was none"),
    "t_end": (float, "s", "time at which the outcome was decided"),
    "ue": (int, "", "user index"),
    "kind": (str, "", "'ho' baseline handover, 'cho' conditional handover, 'rlf' link failure without handover"),
    "src": (int, "", "source (serving) cell"),
    "tgt": (int, "", "target cell; for 'rlf' the cell of the re-establishment"),
    "outcome": (str, "", "useful, unnecessary, too_early, wrong_cell, too_late, censored; 'rlf' rows: too_late "
                         "or coverage"),
    "cause": (str, "", "failure cause, empty if there was no failure"),
    "dwell": (float, "s", "time of stay in the target"),
    "gain_db": (float, "dB", "mean SINR gain of the target over the source during the evaluation window"),
    "n_prepared": (int, "", "prepared cells when the attempt started (CHO)"),
    "o_exec": (float, "dB", "execution offset (CHO) or A3 offset; -99 if not applicable"),
    "x": (float, "m", "position of the user at t_end"),
    "y": (float, "m", "position of the user at t_end"),
}
TABLE_FIELDS: Tuple[str, ...] = ("seed", "rule") + EVENT_FIELDS

#: Event-log levels, from least to most detail.
LEVELS: Tuple[str, ...] = ("off", "summary", "full")

TRACE_FIELDS: Tuple[str, ...] = ("t", "ue", "event", "src", "cell", "value", "note")

#: trace event -> meaning of ``src``, ``cell``, ``value`` and ``note``
TRACE_EVENTS: Dict[str, str] = {
    "serve": "initial serving cell at the first step (cell)",
    "report": "baseline handover: measurement report towards cell (value: A3 offset [dB])",
    "prepare": "conditional handover: preparation of cell requested (value: execution offset [dB])",
    "release": "conditional handover: preparation of cell released or cancelled",
    "config": "conditional configuration of cell reached the UE",
    "config_lost": "conditional configuration of cell lost (T310 running or not connected)",
    "exec": "execution starts: the UE leaves src for cell",
    "attach": "handover complete: the UE is connected to cell (value: SINR [dB])",
    "reestablish": "re-establishment complete in cell (value: SINR [dB])",
    "failure": "mobility failure; cell is the cell selected for re-establishment (note: cause)",
}

TRACE_COLUMNS: Dict[str, Tuple[type, str, str]] = {
    "seed": (int, "", "seed of the world"),
    "rule": (str, "", "name of the rule"),
    "t": (float, "s", "time of the event"),
    "ue": (int, "", "user index"),
    "event": (str, "", "event type (see TRACE_EVENTS)"),
    "src": (int, "", "serving cell before the event, -1 if not applicable"),
    "cell": (int, "", "cell the event refers to"),
    "value": (float, "", "offset [dB] or SINR [dB], see TRACE_EVENTS; NaN if not applicable"),
    "note": (str, "", "failure cause or empty"),
}
TRACE_TABLE_FIELDS: Tuple[str, ...] = ("seed", "rule") + TRACE_FIELDS


def event_level(value: Any) -> str:
    """Normalise an event-log level.

    ``False``/``None`` -> ``"off"``, ``True`` -> ``"summary"``, or a name of :data:`LEVELS`.
    """
    if value is None or value is False:
        return "off"
    if value is True:
        return "summary"
    if isinstance(value, str) and value.lower() in LEVELS:
        return value.lower()
    raise ValueError("event-log level must be one of %s (or true/false), got %r" % (", ".join(LEVELS), value))


def _canon(v: Any) -> str:
    if isinstance(v, str):
        return v
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, int) or (hasattr(v, "dtype") and v.dtype.kind in "iu"):
        return str(int(v))
    return repr(float(v) + 0.0)


def _rows(events: Iterable) -> Iterable[Sequence]:
    for ev in events:
        if isinstance(ev, dict):
            yield [ev[k] for k in EVENT_FIELDS]
        else:
            yield ev


def canonical_csv(events: Iterable) -> str:
    """Canonical CSV text of an event log (rows as dictionaries or tuples in :data:`EVENT_FIELDS` order)."""
    lines = [",".join(EVENT_FIELDS)]
    for row in _rows(events):
        if len(row) != len(EVENT_FIELDS):
            raise ValueError("an event row needs %d fields, got %d" % (len(EVENT_FIELDS), len(row)))
        lines.append(",".join(_canon(v) for v in row))
    return "\n".join(lines) + "\n"


def fingerprint(events: Iterable) -> str:
    """SHA-256 (hex) of the canonical CSV of an event log."""
    return hashlib.sha256(canonical_csv(events).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# tables
# ---------------------------------------------------------------------------
def parquet_available() -> bool:
    """True if ``pyarrow`` can be imported (needed for Parquet files)."""
    try:
        import pyarrow.parquet as pq
        del pq
    except ImportError:
        return False
    return True


def to_columns(results: Sequence) -> Dict[str, list]:
    """Event logs of ``results`` (:class:`~handoverlab.simulate.RunResult` with events) as columns."""
    cols: Dict[str, list] = {k: [] for k in TABLE_FIELDS}
    for r in results:
        if r.events is None:
            raise ValueError("run %s / seed %d has no event log (run with log_events=True)" % (r.rule, r.seed))
        for ev in r.events:
            cols["seed"].append(int(r.seed))
            cols["rule"].append(r.rule)
            for k in EVENT_FIELDS:
                cols[k].append(ev[k])
    return cols


def write_events(results: Sequence, path: str) -> str:
    """Write the event logs of ``results`` to ``path`` and return the path written.

    ``.parquet`` writes Parquet if ``pyarrow`` is installed; without it the
    table is written as CSV next to it (``.csv`` instead of ``.parquet``) and a
    warning is issued.  Any other name writes CSV.
    """
    cols = to_columns(results)
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    path, pq = _table_path(path)
    if pq:
        _write_parquet(cols, path)
    else:
        _write_csv(cols, path)
    return path


def _write_csv(cols: Dict[str, list], path: str, fields: Sequence[str] = TABLE_FIELDS) -> None:
    n = len(cols["seed"])
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(fields)
        for i in range(n):
            w.writerow([_canon(cols[k][i]) for k in fields])
    os.replace(tmp, path)


def _write_parquet(cols: Dict[str, list], path: str, fields_: Sequence[str] = TABLE_FIELDS,
                   catalogue: Dict[str, Tuple[type, str, str]] = EVENT_COLUMNS) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq
    types = {int: pa.int64(), float: pa.float64(), str: pa.string()}
    fields, arrays = [], []
    for k in fields_:
        tp = catalogue[k][0]
        vals = [tp(v) for v in cols[k]]
        fields.append(pa.field(k, types[tp]))
        arrays.append(pa.array(vals, type=types[tp]))
    table = pa.Table.from_arrays(arrays, schema=pa.schema(fields))
    tmp = path + ".tmp"
    pq.write_table(table, tmp)
    os.replace(tmp, path)


def read_events(path: str) -> List[dict]:
    """Rows of an event table written by :func:`write_events` (typed values, in file order)."""
    if path.lower().endswith(".parquet"):
        import pyarrow.parquet as pq
        data = pq.read_table(path).to_pydict()
        n = len(data["seed"])
        return [{k: data[k][i] for k in TABLE_FIELDS} for i in range(n)]
    out = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out.append({k: EVENT_COLUMNS[k][0](row[k]) if EVENT_COLUMNS[k][0] is not int else int(row[k])
                        for k in TABLE_FIELDS})
    return out


def _table_path(path: str) -> Tuple[str, bool]:
    """(path to write, parquet?) for a requested table name."""
    if path.lower().endswith(".parquet"):
        if parquet_available():
            return path, True
        new = path[:-len(".parquet")] + ".csv"
        warnings.warn("pyarrow is not installed; writing %s instead of %s" % (new, path), RuntimeWarning,
                      stacklevel=3)
        return new, False
    return path, False


def write_trace(results: Sequence, path: str) -> str:
    """Write the traces of ``results`` (runs at level ``full``) as one table; returns the path written.

    Columns: ``seed``, ``rule`` and :data:`TRACE_FIELDS`; Parquet or CSV as
    in :func:`write_events`.
    """
    cols: Dict[str, list] = {k: [] for k in TRACE_TABLE_FIELDS}
    for r in results:
        if getattr(r, "trace", None) is None:
            raise ValueError("run %s / seed %d has no trace (run with log_events='full')" % (r.rule, r.seed))
        for ev in r.trace:
            cols["seed"].append(int(r.seed))
            cols["rule"].append(r.rule)
            for k in TRACE_FIELDS:
                cols[k].append(ev[k])
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    path, pq = _table_path(path)
    if pq:
        _write_parquet(cols, path, TRACE_TABLE_FIELDS, TRACE_COLUMNS)
    else:
        _write_csv(cols, path, TRACE_TABLE_FIELDS)
    return path


def read_trace(path: str) -> List[dict]:
    """Rows of a trace table written by :func:`write_trace` (typed values, in file order)."""
    if path.lower().endswith(".parquet"):
        import pyarrow.parquet as pq
        data = pq.read_table(path).to_pydict()
        n = len(data["seed"])
        return [{k: data[k][i] for k in TRACE_TABLE_FIELDS} for i in range(n)]
    out = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out.append({k: (int(float(row[k])) if TRACE_COLUMNS[k][0] is int else TRACE_COLUMNS[k][0](row[k]))
                        for k in TRACE_TABLE_FIELDS})
    return out


def trace_path(events_path: str) -> str:
    """Name of the trace table that goes with an event table: ``events.parquet`` -> ``events-trace.parquet``."""
    root, ext = os.path.splitext(events_path)
    return root + "-trace" + (ext or ".csv")


def serving_cells(trace: Iterable[dict], n_users: int, times: Sequence[float]):
    """Serving cell of every user at ``times`` from a trace: an array (len(times), n_users).

    -1 while a user is executing a handover or re-establishing (not connected).
    """
    import numpy as np
    times = np.asarray(times, dtype=float)
    out = np.full((len(times), n_users), -1, dtype=int)
    changes: Dict[int, List[Tuple[float, int]]] = {}
    for ev in trace:
        e = ev["event"]
        if e in ("serve", "attach", "reestablish"):
            changes.setdefault(int(ev["ue"]), []).append((float(ev["t"]), int(ev["cell"])))
        elif e in ("exec", "failure"):
            changes.setdefault(int(ev["ue"]), []).append((float(ev["t"]), -1))
    for u, ch in changes.items():
        if u >= n_users:
            continue
        ch.sort(key=lambda x: x[0])
        ts = np.array([c[0] for c in ch])
        cells = np.array([c[1] for c in ch])
        idx = np.searchsorted(ts, times + 1e-9, side="right") - 1
        out[:, u] = np.where(idx >= 0, cells[np.maximum(idx, 0)], -1)
    return out


def group_logs(rows: Iterable[dict]) -> Dict[Tuple[int, str], List[dict]]:
    """Rows of an event table -> {(seed, rule): event log}."""
    out: Dict[Tuple[int, str], List[dict]] = {}
    for r in rows:
        out.setdefault((int(r["seed"]), r["rule"]), []).append({k: r[k] for k in EVENT_FIELDS})
    return out
