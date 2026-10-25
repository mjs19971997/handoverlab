# SPDX-License-Identifier: MIT
"""``handoverlab ns3 compare``: HandoverLab on the cells and seeds of an imported ns-3 reference, and the checks.

The HandoverLab side of a cell is :func:`handoverlab.verify.ns3.scenario_for` (the card ``ns3-urban-3.5ghz``
with the sites of the site distance and the in-car loss of ns-3) with ideal execution (ns-3 has an ideal
random access), the users, the run length (unless ``run_length: card``), the traffic and the fading of the
study, and, with ``comparison``, :data:`handoverlab.verify.ns3.COMPARISON_SETTING`.  Each seed of the
reference runs with the same seed in HandoverLab.

The checks are those of the studies N3 and V1 (limits as parameters, defaults those of V1):

* F1 level: sum of the HandoverLab failures over the cells / sum of the ns-3 failures in [0.67, 1.5];
* F2 order: Spearman rank correlation of the cell failure counts at least 0.8;
* F1 and F2 are "not measurable" (None, failed) when ns-3 has fewer than 20 failures in total;
* F3 handover rate: median over the cells of the handover-rate ratio HandoverLab / ns-3 in [0.8, 1.25];
* F4 time-to-trigger effect: the sign of (longest - shortest TTT) failures equal to ns-3's in at least
  0.75 of the cell pairs that differ only in the TTT (None when the study has one TTT).
"""
from __future__ import annotations

import json
import math
import os
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Callable, Dict, List, Optional, Union

import numpy as np

from .study import Ns3BridgeError, Ns3Study, load_ns3_study

LIMITS = dict(level=(0.67, 1.5), rank_min=0.8, ho_ratio=(0.8, 1.25), ttt_share=0.75, min_failures=20)
IDEAL_EXECUTION = {"protocol.exec_can_fail": False}
TRAFFIC = {"light": {}, "full": {"traffic.model": "full_buffer"}}     # mixed: no checked counterpart
FADING = {"radio.fast_fading": "tdl-c"}                                 # the criterion of the fading checks


def cell_key(isd: int, speed: float, ttt: int, offset: float, traffic: str, fading: bool) -> str:
    """Name of a cell in the result, such as ``light_h3_d200_v10_t80``."""
    return "%s_h%g_d%d_v%g_t%d%s" % (traffic, offset, isd, speed, ttt, "_fading" if fading else "")


def handoverlab_scenario(study: Ns3Study, isd: int, speed: float, traffic: str, fading: bool,
                         comparison: bool = False, overrides: Optional[Dict] = None):
    """The HandoverLab scenario of one cell (see the module text)."""
    from ..verify.ns3 import COMPARISON_SETTING, scenario_for
    if traffic not in TRAFFIC:
        raise Ns3BridgeError("unsupported option 'ns3.conditions.traffic: %s' for compare: HandoverLab has no "
                             "checked counterpart of this ns-3 traffic (export works; compare supports %s)"
                             % (traffic, ", ".join(TRAFFIC)))
    ov = dict(COMPARISON_SETTING if comparison else IDEAL_EXECUTION)
    ov["mobility.users"] = study.users
    if study.run_length == "study":
        ov.update({"run.duration_s": study.duration_s, "run.warmup_s": study.discard_s})
    ov.update(TRAFFIC[traffic])
    if fading:
        ov.update(FADING)
    sc = scenario_for(isd, speed, car=True).with_overrides(ov)
    return sc.with_overrides(overrides) if overrides else sc


def _job(job):
    from ..simulate import simulate
    sc, rule, seed = job
    m = simulate(sc, [rule], seeds=[seed])[0].metrics
    return int(m["n_failures"]), float(m["handovers_pm"])


def _sign(x: float) -> int:
    return int(np.sign(x))


def checks(cells: List[Dict[str, Any]], limits: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """F1-F4 from the cells (each with ``failures_hl``, ``failures_ns3``, ``ho_pm_hl``, ``ho_pm_ns3`` and the
    condition); see the module text."""
    from scipy.stats import spearmanr
    L = dict(LIMITS, **(limits or {}))
    hf = np.array([c["failures_hl"] for c in cells], float)
    nf = np.array([c["failures_ns3"] for c in cells], float)
    hh = np.array([c["ho_pm_hl"] for c in cells])
    nh = np.array([c["ho_pm_ns3"] for c in cells])
    measurable = bool(nf.sum() >= L["min_failures"])
    groups: Dict[tuple, Dict[int, int]] = {}
    for i, c in enumerate(cells):
        groups.setdefault((c["traffic"], c["fading"], c["offset_db"], c["isd_m"], c["speed_mps"]), {})[c["ttt_ms"]] = i
    pairs = [(g[min(g)], g[max(g)]) for g in groups.values() if len(g) > 1]
    sign_ok = sum(_sign(hf[j] - hf[i]) == _sign(nf[j] - nf[i]) for i, j in pairs)
    r = dict(F1_level=float(hf.sum() / nf.sum()) if measurable else None,
             F2_rank=float(spearmanr(nf, hf)[0]) if measurable else None,
             F3_ho_ratio=float(np.median(hh / nh)), F4_ttt_sign=int(sign_ok) if pairs else None,
             F4_pairs=len(pairs), failures_hl=hf.tolist(), failures_ns3=nf.tolist(), measurable=measurable)
    lo, hi = L["level"]
    hlo, hhi = L["ho_ratio"]
    r["pass"] = dict(F1=bool(measurable and lo <= r["F1_level"] <= hi),
                     F2=bool(measurable and not math.isnan(r["F2_rank"]) and r["F2_rank"] >= L["rank_min"]),
                     F3=bool(hlo <= r["F3_ho_ratio"] <= hhi),
                     F4=bool(sign_ok >= L["ttt_share"] * len(pairs) - 1e-9) if pairs else None)
    r["limits"] = dict(level=list(L["level"]), rank_min=L["rank_min"], ho_ratio=list(L["ho_ratio"]),
                       ttt_share=L["ttt_share"], min_failures=L["min_failures"])
    return r


def compare(study: Union[str, os.PathLike, Dict[str, Any], Ns3Study], reference: Union[str, Dict[str, Any]],
            comparison: bool = False, limits: Optional[Dict[str, Any]] = None, workers: int = 1,
            progress: Optional[Callable[[str], None]] = None, overrides: Optional[Dict] = None,
            out: Optional[str] = None) -> Dict[str, Any]:
    """Run HandoverLab on the cells and seeds of ``reference`` (a file of :func:`import_results` or its
    dictionary) and return the cells and the checks F1-F4; with ``out`` also write the result as JSON.

    ``comparison`` applies :data:`handoverlab.verify.ns3.COMPARISON_SETTING`; ``limits`` changes the limits
    of :data:`LIMITS`; ``overrides`` (dotted keys) change every HandoverLab scenario further, for
    calibration experiments; ``workers`` runs that many processes.
    """
    st = load_ns3_study(study)
    for tr in st.traffic:
        if tr not in TRAFFIC:
            handoverlab_scenario(st, st.isd_m[0], st.speed_mps[0], tr, False)      # raises, naming the option
    if not isinstance(reference, dict):
        with open(reference, encoding="utf-8") as f:
            reference = json.load(f)
    rows = {(r["isd_m"], float(r["speed_mps"]), float(r["a3_offset_db"]), r["ttt_ms"], r.get("traffic", "light"),
             bool(r.get("fading", False))): r for r in reference.get("rows", []) if r.get("part") == "S"}
    notes, cells, jobs = [], [], []
    for c in st.cells():
        r = rows.get((c.isd_m, c.speed_mps, c.offset_db, c.ttt_ms, c.traffic, c.fading))
        if r is None:
            raise Ns3BridgeError("the reference has no runs for %s (import the results of this study)"
                                 % st.tag(c))
        if (r.get("users"), r.get("duration_s"), r.get("discard_s")) != (st.users, st.duration_s, st.discard_s):
            raise Ns3BridgeError("%s: the ns-3 runs have %s users and %s s (%s s discarded), the study %d users "
                                 "and %g s (%g s discarded)" % (st.tag(c), r.get("users"), r.get("duration_s"),
                                                                 r.get("discard_s"), st.users, st.duration_s,
                                                                 st.discard_s))
        seeds = list(r["seeds"])
        if sorted(seeds) != sorted(st.seeds):
            notes.append("%s: ns-3 runs for seeds %s, the study has %s" % (st.tag(c), seeds, list(st.seeds)))
        sc = handoverlab_scenario(st, c.isd_m, c.speed_mps, c.traffic, c.fading, comparison, overrides)
        rule = {"rule": "a3", "off_db": c.offset_db, "ttt_s": c.ttt_ms / 1000.0}
        cells.append(dict(key=cell_key(c.isd_m, c.speed_mps, c.ttt_ms, c.offset_db, c.traffic, c.fading),
                          isd_m=c.isd_m, speed_mps=c.speed_mps, ttt_ms=c.ttt_ms, offset_db=c.offset_db,
                          traffic=c.traffic, fading=c.fading, seeds=seeds, n=len(seeds),
                          failures_ns3=int(r["failures"]),
                          ho_pm_ns3=float(np.mean([x["ho_pm"] for x in r["per_run"]]))))
        jobs += [(sc, rule, s) for s in seeds]
    if progress:
        progress("HandoverLab: %d runs (%d cells)%s" % (len(jobs), len(cells),
                                                         ", comparison setting" if comparison else ""))
    if workers > 1:
        with ProcessPoolExecutor(workers) as pool:
            res = list(pool.map(_job, jobs))
    else:
        res = []
        for j in jobs:
            res.append(_job(j))
            if progress and len(res) % 10 == 0:
                progress("HandoverLab: %d of %d runs" % (len(res), len(jobs)))
    k = 0
    for c in cells:
        part = res[k:k + c["n"]]
        k += c["n"]
        c["failures_hl"] = int(sum(f for f, _ in part))
        c["ho_pm_hl"] = float(np.mean([h for _, h in part]))
    out_d = dict(study=st.name, study_sha256=st.sha256(), reference_study_sha256=reference.get("study_sha256"),
                 comparison=bool(comparison), run_length=st.run_length, overrides=dict(overrides or {}),
                 cells=cells, checks=checks(cells, limits), notes=notes)
    if reference.get("study_sha256") and reference["study_sha256"] != out_d["study_sha256"]:
        notes.append("the ns-3 results were exported from another version of this study (hash %s, now %s)"
                     % (reference["study_sha256"][:12], out_d["study_sha256"][:12]))
    if out:
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(out_d, f, indent=1)
            f.write("\n")
    return out_d
