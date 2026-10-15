# SPDX-License-Identifier: MIT
"""Result storage of a study: job records, tables and the directory layout.

::

    <output>/
      manifest.json            versions, platform, start and end times, worker count
      study.lock.json          the resolved study (every value explicit) and its SHA-256
      jobs/<stage>/<job>.json  one record per job (atomic write: complete or absent)
      failed/<job>.txt         traceback of a failed job (removed when it succeeds)
      events/<run>.parquet     event log of one rule run (test stage, with ``events: summary`` or ``full``)
      events/<run>-trace.parquet procedure trace of one rule run (``events: full``)
      tuned/<group>.json       all evaluated settings, the selection and the gates of a tuning group
      tuned/gates.json         the gate report of the whole study
      tables/runs.parquet      one row per job and rule (CSV without pyarrow)
      tables/tuning.parquet    one row per evaluated setting and tuning group
      report/                  written by ``handoverlab report``

A job record is the unit of resumption: a job whose record exists is not run
again.  Tables are derived from the records and can be rebuilt at any time.
Parquet needs the optional package ``pyarrow`` (``pip install
handoverlab[parquet]``); without it tables are written as CSV and read back
with their types.
"""
from __future__ import annotations

import csv
import glob
import json
import os
from typing import Any, Dict, Iterable, List, Optional, Sequence

STAGES = ("tune1", "tune2", "test")


def have_pyarrow() -> bool:
    try:
        import pyarrow  # noqa: F401
        import pyarrow.parquet  # noqa: F401
    except ImportError:
        return False
    return True


def atomic_write_json(path: str, obj: Any) -> None:
    """Write JSON to a temporary file and rename it, so a reader sees all or nothing."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=1, default=_json_default)
        f.write("\n")
    os.replace(tmp, path)


def _json_default(o):
    try:
        import numpy as np
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.bool_):
            return bool(o)
    except ImportError:                                       # pragma: no cover
        pass
    raise TypeError("not JSON serialisable: %r" % (o,))


def read_json(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------- tables
def write_table(rows: Sequence[Dict[str, Any]], path: str, columns: Optional[Sequence[str]] = None) -> str:
    """Write ``rows`` as Parquet (``.parquet`` name and pyarrow installed) or CSV; returns the path written.

    A ``.parquet`` name falls back to the same name with ``.csv`` when
    pyarrow is missing.
    """
    cols = list(columns) if columns else _columns(rows)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if path.lower().endswith(".parquet"):
        if have_pyarrow():
            import pyarrow as pa
            import pyarrow.parquet as pq
            data = {c: [r.get(c) for r in rows] for c in cols}
            arrays = {}
            for c, vals in data.items():
                arrays[c] = pa.array(_uniform(vals))
            table = pa.table(arrays) if cols else pa.table({})
            tmp = path + ".tmp"
            pq.write_table(table, tmp)
            os.replace(tmp, path)
            return path
        path = path[:-len(".parquet")] + ".csv"
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(cols)
        for r in rows:
            w.writerow([_cell(r.get(c)) for c in cols])
    os.replace(tmp, path)
    return path


def _uniform(vals: List[Any]) -> List[Any]:
    """Make a column acceptable to Arrow: ints mixed with floats become floats; mixed types become text."""
    kinds = {type(v) for v in vals if v is not None}
    if kinds <= {int, float} and float in kinds:
        return [None if v is None else float(v) for v in vals]
    if len(kinds) > 1:
        return [None if v is None else str(v) for v in vals]
    return vals


def _columns(rows: Iterable[Dict[str, Any]]) -> List[str]:
    cols: List[str] = []
    seen = set()
    for r in rows:
        for k in r:
            if k not in seen:
                seen.add(k)
                cols.append(k)
    return cols


def _cell(v: Any) -> Any:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return repr(v)
    return v


def _parse(s: str) -> Any:
    if s == "":
        return None
    if s == "true":
        return True
    if s == "false":
        return False
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        return s


def read_table(path: str) -> List[Dict[str, Any]]:
    """Rows of a table written by :func:`write_table` (Parquet or CSV) as dictionaries.

    For a ``.parquet`` name that does not exist, the CSV of the same name is
    read if present.
    """
    if path.lower().endswith(".parquet"):
        if os.path.exists(path):
            import pyarrow.parquet as pq
            return pq.read_table(path).to_pylist()
        alt = path[:-len(".parquet")] + ".csv"
        if os.path.exists(alt):
            path = alt
    with open(path, encoding="utf-8", newline="") as f:
        rd = csv.reader(f)
        header = next(rd, [])
        return [{c: _parse(v) for c, v in zip(header, row)} for row in rd]


def table_path(base: str) -> str:
    """Existing table file for ``base`` (without extension): Parquet first, then CSV."""
    for ext in (".parquet", ".csv"):
        if os.path.exists(base + ext):
            return base + ext
    raise FileNotFoundError("no table %s.parquet or %s.csv" % (base, base))


# ---------------------------------------------------------------------------- the study directory
class StudyStore:
    """Paths and records of one study directory."""

    def __init__(self, root: str):
        self.root = os.path.abspath(root)

    def path(self, *parts: str) -> str:
        return os.path.join(self.root, *parts)

    def job_path(self, stage: str, job_id: str) -> str:
        return self.path("jobs", stage, job_id + ".json")

    def failed_path(self, job_id: str) -> str:
        return self.path("failed", job_id + ".txt")

    def events_path(self, run_key: str) -> str:
        return self.path("events", run_key[:24] + (".parquet" if have_pyarrow() else ".csv"))

    def has_job(self, stage: str, job_id: str) -> bool:
        return os.path.exists(self.job_path(stage, job_id))

    def load_job(self, stage: str, job_id: str) -> Optional[Dict[str, Any]]:
        p = self.job_path(stage, job_id)
        if not os.path.exists(p):
            return None
        try:
            return read_json(p)
        except (OSError, ValueError):                         # damaged record: run the job again
            return None

    def write_job(self, record: Dict[str, Any]) -> None:
        atomic_write_json(self.job_path(record["stage"], record["job"]), record)
        fp = self.failed_path(record["job"])
        if os.path.exists(fp):
            os.remove(fp)

    def write_failed(self, job_id: str, text: str) -> None:
        p = self.failed_path(job_id)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def records(self, stage: Optional[str] = None) -> List[Dict[str, Any]]:
        """All job records (of one stage), in a stable order."""
        stages = [stage] if stage else list(STAGES)
        out = []
        for s in stages:
            for p in sorted(glob.glob(self.path("jobs", s, "*.json"))):
                try:
                    out.append(read_json(p))
                except (OSError, ValueError):
                    continue
        return out

    def run_index(self) -> Dict[str, Dict[str, Any]]:
        """run key -> stored result of that rule run, from every job record (for reuse)."""
        idx: Dict[str, Dict[str, Any]] = {}
        for rec in self.records():
            for r in rec.get("rules", []):
                k = r.get("run_key")
                if k and k not in idx and not r.get("reused"):
                    idx[k] = dict(metrics=r["metrics"], fingerprint=r["fingerprint"], n_events=r["n_events"],
                                  family=r["family"], params=r["params"], job=rec["job"],
                                  events=r.get("events"), trace=r.get("trace"))
        return idx


__all__ = ["STAGES", "have_pyarrow", "atomic_write_json", "read_json", "write_table", "read_table", "table_path",
           "StudyStore"]
