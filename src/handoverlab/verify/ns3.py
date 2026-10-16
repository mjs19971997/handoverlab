# SPDX-License-Identifier: MIT
"""Reference comparison with stored ns-3 / 5G-LENA results.

``data/ns3_urban_a3.json`` holds results of the packet-level simulator ns-3
with its 5G-LENA module for stock Event-A3 handover in the scenario
``ns3-urban-3.5ghz`` (see its scenario card): 24 A3 settings (offset 1-6 dB
x time-to-trigger 100-1000 ms) on four conditions (site distance 200 / 400 m
x 16 / 30 m/s).  HandoverLab runs the same settings and conditions; seeds are
different realisations in the two simulators, so only averages over the
conditions are compared, setting by setting.

Acceptance limits (version 0.2):

* median over the settings of the ratio HandoverLab / ns-3 of the handover
  rate and of the unnecessary-handover rate between 0.8 and 1.25;
* rank correlation (Spearman) over the settings at least 0.9 for both.

Failure rates and the mean serving SINR are reported without a limit: the
two simulators define the load of interfering cells differently, and the
failure model of HandoverLab is not calibrated in absolute terms.

The comparison is not part of the quick checks: it simulates 4 x 24 runs of
150 s (a few minutes per seed on one core).
"""
from __future__ import annotations

import json
import os
from typing import Callable, Dict, Optional, Sequence

import numpy as np

from ..scenarios import builtin_scenario
from ..simulate import simulate

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "ns3_urban_a3.json")
LIMITS = dict(ratio_lo=0.8, ratio_hi=1.25, rank_min=0.9)


def load_reference() -> dict:
    with open(PATH, encoding="utf-8") as f:
        return json.load(f)


def scenario_for(isd_m: int, speed_mps: int, ref: Optional[dict] = None, overrides: Optional[Dict] = None):
    """``ns3-urban-3.5ghz`` with the sites of ``isd_m`` and constant speed ``speed_mps`` (8, 16 or 30).

    ``overrides`` (dotted keys, such as ``{"protocol.qout_window_s": 0.12}``) change the scenario
    further, for calibration experiments.
    """
    ref = ref or load_reference()
    sc = builtin_scenario("ns3-urban-3.5ghz").with_overrides({
        "name": "ns3-urban-3.5ghz-%dm-%dmps" % (isd_m, speed_mps),
        "layout.sites": ref["sites"][str(isd_m)], "mobility.profile": "c%d" % speed_mps})
    return sc.with_overrides(overrides) if overrides else sc


def spearman(a: Sequence[float], b: Sequence[float]) -> float:
    from scipy.stats import spearmanr
    return float(spearmanr(a, b)[0])


def compare(seeds: Sequence[int] = (500,), progress: Optional[Callable[[str], None]] = None,
            overrides: Optional[Dict] = None) -> Dict:
    """Run part A of the reference in HandoverLab and return the per-setting table and the summary.

    ``overrides`` change the scenario of every condition (see :func:`scenario_for`).
    """
    ref = load_reference()
    rows = [r for r in ref["rows"] if r["part"] == "A"]
    settings = sorted({(r["a3_offset_db"], r["ttt_ms"]) for r in rows})
    conds = sorted({(r["isd_m"], r["speed_mps"]) for r in rows})
    rules = [{"rule": "a3", "name": "A3_%g_%d" % (h, t), "off_db": h, "ttt_s": t / 1000.0} for h, t in settings]
    keys = ("attempts_pm", "unnecessary_pm", "failures_pm", "sinr_db")
    sim = {}
    for isd, v in conds:
        sc = scenario_for(isd, v, ref, overrides)
        for res in simulate(sc, rules, seeds=seeds):
            sim.setdefault((isd, v, res.rule), []).append([res.metrics[k] for k in keys])
        if progress:
            progress("ns-3 comparison: condition %d m, %d m/s done" % (isd, v))
    nref = {(r["isd_m"], r["speed_mps"], r["a3_offset_db"], r["ttt_ms"]):
            [r["handovers_pm"], r["unnecessary_pm"], r["failures_pm"], r["sinr_db"]] for r in rows}
    table = []
    for (h, t), rule in zip(settings, rules):
        r = np.mean([nref[(i, v, h, t)] for i, v in conds], axis=0)
        s = np.mean([np.mean(sim[(i, v, rule["name"])], axis=0) for i, v in conds], axis=0)
        table.append(dict(a3_offset_db=h, ttt_ms=t, ns3=r.tolist(), handoverlab=s.tolist()))
    R = np.array([x["ns3"] for x in table])
    S = np.array([x["handoverlab"] for x in table])
    summ = dict(
        ho_ratio_median=float(np.median(S[:, 0] / R[:, 0])),
        uho_ratio_median=float(np.median(S[:, 1] / np.maximum(R[:, 1], 1e-9))),
        ho_rank=spearman(R[:, 0], S[:, 0]), uho_rank=spearman(R[:, 1], S[:, 1]), fail_rank=spearman(R[:, 2], S[:, 2]),
        fail_mean_ns3=float(R[:, 2].mean()), fail_mean=float(S[:, 2].mean()),
        sinr_mean_ns3=float(R[:, 3].mean()), sinr_mean=float(S[:, 3].mean()),
        ho_mean_ns3=float(R[:, 0].mean()), ho_mean=float(S[:, 0].mean()),
        uho_mean_ns3=float(R[:, 1].mean()), uho_mean=float(S[:, 1].mean()),
        seeds=list(seeds), conditions=[list(c) for c in conds])
    return dict(table=table, summary=summ)


def ns3_checks(rep, seeds: Sequence[int] = (500,), progress=None) -> Dict:
    rep.section("ns3", "reference comparison with ns-3 / 5G-LENA (24 A3 settings x 4 conditions, %d seed%s)"
                % (len(seeds), "s" if len(seeds) > 1 else ""))
    out = compare(seeds, progress)
    s, L = out["summary"], LIMITS
    for x in out["table"]:
        rep.note("A3 %g dB / %4d ms" % (x["a3_offset_db"], x["ttt_ms"]),
                 "handovers %.2f / %.2f, unnecessary %.2f / %.2f, failures %.3f / %.3f per UE-min (HandoverLab / ns-3)"
                 % (x["handoverlab"][0], x["ns3"][0], x["handoverlab"][1], x["ns3"][1], x["handoverlab"][2],
                    x["ns3"][2]))
    rep.check("handover rate: median ratio HandoverLab / ns-3 in [%.2f, %.2f]" % (L["ratio_lo"], L["ratio_hi"]),
              L["ratio_lo"] <= s["ho_ratio_median"] <= L["ratio_hi"], "%.2f" % s["ho_ratio_median"])
    rep.check("unnecessary-handover rate: median ratio in [%.2f, %.2f]" % (L["ratio_lo"], L["ratio_hi"]),
              L["ratio_lo"] <= s["uho_ratio_median"] <= L["ratio_hi"], "%.2f" % s["uho_ratio_median"])
    rep.check("handover rate: rank correlation over the settings >= %.1f" % L["rank_min"],
              s["ho_rank"] >= L["rank_min"], "%.2f" % s["ho_rank"])
    rep.check("unnecessary-handover rate: rank correlation >= %.1f" % L["rank_min"],
              s["uho_rank"] >= L["rank_min"], "%.2f" % s["uho_rank"])
    rep.note("failure rate (no limit: interfering load defined differently)",
             "mean %.3f / %.3f per UE-min, rank correlation %.2f" % (s["fail_mean"], s["fail_mean_ns3"], s["fail_rank"]))
    rep.note("mean serving SINR (no limit)", "%.1f dB / %.1f dB" % (s["sinr_mean"], s["sinr_mean_ns3"]))
    return out
