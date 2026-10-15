# SPDX-License-Identifier: MIT
"""Recompute stored results and compare their event-log fingerprints.

A JSON result file written by ``handoverlab run -o results.json`` holds the
resolved scenario and, for every seed and rule, the rule specification, the
metrics and the fingerprint of the event log.  :func:`stored_checks`
recomputes all runs, or a random sample of them, on the current machine and
reports the share of identical event logs and the largest relative
difference of a metric.  Metrics count as equal within a relative tolerance
of 1e-12 (averaged floating-point quantities may differ in the last bits
between machines).
"""
from __future__ import annotations

import json
import random
from typing import Optional

from ..config import Scenario
from ..simulate import run_world
from ..world import build_world

REL_TOL = 1e-12


def _rel(a, b) -> float:
    if a == b:
        return 0.0
    return abs(a - b) / max(abs(a), abs(b), 1e-300)


def stored_checks(rep, path: str, sample: Optional[int] = None, pick_seed: int = 0, progress=None) -> dict:
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    rep.section("stored", "stored results in %s" % path)
    recs = doc.get("results") or []
    if not recs or "fingerprint" not in recs[0] or "key" not in recs[0]:
        rep.check("the file holds fingerprints and rule keys (written by version 0.2 or later)", False)
        return {}
    sc = Scenario.from_dict(doc["scenario"])
    idx = list(range(len(recs)))
    if sample is not None and sample < len(idx):
        idx = sorted(random.Random(pick_seed).sample(idx, sample))
    by_seed = {}
    for i in idx:
        by_seed.setdefault(int(recs[i]["seed"]), []).append(i)
    same, worst, worst_key = 0, 0.0, ""
    for seed, ii in sorted(by_seed.items()):
        world = build_world(sc, seed)
        specs = [dict(rule=recs[i]["key"], name=recs[i]["rule"], **recs[i]["params"]) for i in ii]
        for i, res in zip(ii, run_world(world, specs)):
            want = recs[i]
            ok = res.fingerprint == want["fingerprint"]
            same += ok
            d = {k: _rel(res.metrics[k], v) for k, v in want["metrics"].items() if k in res.metrics}
            k = max(d, key=d.get) if d else ""
            if d and d[k] > worst:
                worst, worst_key = d[k], "%s (seed %d, %s)" % (k, seed, want["rule"])
            rep.check("seed %d / %s: event log identical" % (seed, want["rule"]), ok,
                      "%s..." % res.fingerprint[:12] if ok else "got %s..., stored %s..."
                      % (res.fingerprint[:12], want["fingerprint"][:12]))
        if progress:
            progress("seed %d recomputed" % seed)
    n = len(idx)
    rep.check("metrics equal within a relative %.0e" % REL_TOL, worst <= REL_TOL,
              "largest relative difference %.2e%s" % (worst, (" in " + worst_key) if worst_key else ""))
    rep.note("identical event logs", "%d of %d recomputed runs (%.0f %%)" % (same, n, 100.0 * same / max(n, 1)))
    return dict(identical=same, recomputed=n, max_rel_diff=worst)
