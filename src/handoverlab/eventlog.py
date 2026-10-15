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

Tables
    :func:`write_events` writes the logs of several runs as one table with the
    columns ``seed``, ``rule`` and :data:`EVENT_FIELDS`: Parquet (typed
    columns, needs ``pyarrow``) for a ``.parquet`` file name, CSV otherwise.
    :func:`read_events` reads either back.
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
    if path.lower().endswith(".parquet"):
        if parquet_available():
            _write_parquet(cols, path)
            return path
        new = path[:-len(".parquet")] + ".csv"
        warnings.warn("pyarrow is not installed; writing %s instead of %s" % (new, path), RuntimeWarning,
                      stacklevel=2)
        path = new
    _write_csv(cols, path)
    return path


def _write_csv(cols: Dict[str, list], path: str) -> None:
    n = len(cols["seed"])
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(TABLE_FIELDS)
        for i in range(n):
            w.writerow([_canon(cols[k][i]) for k in TABLE_FIELDS])
    os.replace(tmp, path)


def _write_parquet(cols: Dict[str, list], path: str) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq
    types = {int: pa.int64(), float: pa.float64(), str: pa.string()}
    fields, arrays = [], []
    for k in TABLE_FIELDS:
        tp = EVENT_COLUMNS[k][0]
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


def group_logs(rows: Iterable[dict]) -> Dict[Tuple[int, str], List[dict]]:
    """Rows of an event table -> {(seed, rule): event log}."""
    out: Dict[Tuple[int, str], List[dict]] = {}
    for r in rows:
        out.setdefault((int(r["seed"]), r["rule"]), []).append({k: r[k] for k in EVENT_FIELDS})
    return out
