# SPDX-License-Identifier: MIT
"""Writing results: one CSV row or JSON record per (seed, rule)."""
from __future__ import annotations

import csv
import json
import os
import platform
from typing import Any, Dict, List, Optional, Sequence

from . import __version__
from .stability import SCHEMA_VERSION


def _ensure_dir(path: str) -> None:
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)


def _atomic_write_text(path: str, text: str) -> None:
    _ensure_dir(path)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    os.replace(tmp, path)


def write_csv(results: Sequence, path: str) -> None:
    """CSV with one row per (seed, rule): seed, rule, family, all rule parameters, then the metrics."""
    rows = [r.row() for r in results]
    cols: List[str] = ["seed", "rule", "family"]
    for row in rows:
        cols.extend(k for k in row if k.startswith("param.") and k not in cols)
    for row in rows:
        cols.extend(k for k in row if k not in cols)
    _ensure_dir(path)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        for row in rows:
            w.writerow({k: _fmt(row.get(k, "")) for k in cols})
    os.replace(tmp, path)


def _fmt(v: Any) -> Any:
    if isinstance(v, float):
        return repr(v)
    return v


def provenance() -> Dict[str, str]:
    import numpy
    import scipy
    return dict(handoverlab=__version__, python=platform.python_version(), numpy=numpy.__version__,
                scipy=scipy.__version__, platform=platform.platform())


def write_json(results: Sequence, path: str, scenario: Optional[Dict[str, Any]] = None) -> None:
    """JSON with the schema version, the resolved scenario, versions and one record per (seed, rule).

    Every record holds the rule key and parameters, the metrics and the
    fingerprint of the event log, so that ``handoverlab verify --results``
    can repeat the run and compare.
    """
    doc = dict(schema=SCHEMA_VERSION, provenance=provenance(), scenario=scenario,
               results=[dict(seed=r.seed, rule=r.rule, key=r.key, family=r.family, params=r.params,
                             fingerprint=r.fingerprint, n_events=r.n_events, metrics=r.metrics, timing=r.timing)
                        for r in results])
    _atomic_write_text(path, json.dumps(doc, indent=1, default=float))


def write_results(results: Sequence, path: str, scenario: Optional[Dict[str, Any]] = None) -> str:
    """Write ``results`` as CSV or JSON, chosen by the file extension."""
    if path.lower().endswith(".json"):
        write_json(results, path, scenario)
    else:
        write_csv(results, path)
    return path
