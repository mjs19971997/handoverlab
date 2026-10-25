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
two simulators define the load of interfering cells differently.  The
absolute failure level is not calibrated.  With equal run lengths on both
sides (corrected in 2.6.0; the 2.5.0 analyses compared 90 s of HandoverLab
with 120 s of ns-3), the default link-monitoring model gives 0.18, 0.32 and
0.17 of the failure level of ns-3 on the fresh sets N3, V1 and V3.  The
*comparison setting* (:data:`COMPARISON_SETTING`, since 2.5.0;
``scenario_for(..., comparison=True)``, ``compare(..., comparison=True)``,
``handoverlab verify --ns3 --ns3-comparison``) brings the level closer
(0.52, 1.31 and 0.64 on N3, V1 and V3) but is not
validated: it passes the pre-registered checks on none of the three sets
(on V1 the rank correlation is 0.62) (docs/calibration.md).  It is not a
default: every default and every stored result is unchanged.

The *ns-3-like setting* (:data:`NS3_LIKE_SETTING`; ``scenario_for(..., ns3_like=True)``,
``compare(..., ns3_like=True)``, ``handoverlab verify --ns3 --ns3-like``) imitates the link
monitoring of ns-3 / 5G-LENA v5.1 as found in its code and measured in its runs (out-of-sync after
200 control receptions below Qout, 0.65-0.9 s, and a handover command that fails while T310 runs).
It imitates ns-3, not 3GPP, and is not a default; its validation on a fresh ns-3 set (V4) is
pending (docs/calibration.md).

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
# ns-3 (ThreeGppPropagationLossModel) adds the in-car penetration loss of TR 38.901 to every link of
# a user that moves at 30-120 km/h, and none outside that range (see docs/calibration.md)
CAR_LOSS = {"radio.penetration_db": 9.0, "radio.penetration_sd_db": 5.0}


# The ns-3 comparison setting (2.5.0): interferer load 0.15 at link monitoring and ideal execution (ns-3 has
# an ideal random access), used together with the in-car loss (``car=True``).  A setting that brings the
# failure level closer to ns-3's, NOT validated.  With equal run lengths on both sides (corrected in 2.6.0; the
# 2.5.0 analyses compared 90 s of HandoverLab with 120 s of ns-3) it gives 0.52 (N3, TTT 100 / 640 ms), 1.31
# (V1, TTT 80 / 320 ms; rank correlation 0.62) and 0.64 (V3, TTT 512 / 1024 ms) of ns-3's failure level, so it
# passes the pre-registered checks on none of the three fresh sets; the handover-rate ratio and the direction
# of the time-to-trigger effect agree.  Kept for compatibility within 2.x.  Not a default.
COMPARISON_SETTING = {"protocol.lm_load": 0.15, "protocol.exec_can_fail": False}

# The ns-3-like setting: imitates ns-3 / 5G-LENA v5.1, NOT 3GPP; not a default.  It reproduces the link-failure
# mechanism found in the code of 5G-LENA v5.1 and measured in ns-3 runs (docs/calibration.md): out-of-sync after
# 200 consecutive control receptions below Qout (0.65-0.9 s at light traffic, against about 200 ms in TS 38.133),
# in-sync after 100 receptions above Qin, both counted afresh on every new cell, a reception rate that grows with
# the users of the cell, a handover command that fails when it arrives while T310 runs (the TR 36.839 model that
# ns-3 uses; TS 38.331 lets the command stop T310), and ideal execution.  Used with the in-car loss
# (``car=True``).  Validation on a fresh ns-3 set (V4) is pending.
NS3_LIKE_SETTING = {"protocol.ns3_oos_rx": 200.0, "protocol.ns3_ins_rx": 100.0, "protocol.ns3_ctrl_hz": 206.0,
                    "protocol.ns3_ctrl_per_ue_hz": 16.5, "protocol.rlm_holdoff_s": 0.0,
                    "protocol.cmd_during_t310": "lost", "protocol.exec_can_fail": False, "protocol.lm_load": 0.38}
SETTINGS = {"comparison": COMPARISON_SETTING, "ns3-like": NS3_LIKE_SETTING}


def car_loss(speed_mps: float) -> Dict:
    """Overrides that reproduce the in-car loss ns-3 applies at ``speed_mps``."""
    return dict(CAR_LOSS) if 30.0 <= speed_mps * 3.6 <= 120.0 else {}
# acceptance limits of a calibrated failure model (docs/calibration.md), fixed before any tuning
FAIL_LIMITS = dict(a_ratio=(0.8, 1.25), a_rank=0.9, ttt_trend=20.0, holdout_ratio=(0.67, 1.5), holdout_rank=0.8)


def load_reference(path: Optional[str] = None) -> dict:
    """The stored reference, or the file ``path`` in the same format (benchmarks/ns3 writes one; since 2.1.0)."""
    with open(path or PATH, encoding="utf-8") as f:
        ref = json.load(f)
    if not isinstance(ref, dict) or "rows" not in ref or "sites" not in ref:
        raise ValueError("%s: not an ns-3 reference file (needs 'sites' and 'rows')" % (path or PATH))
    return ref


def scenario_for(isd_m: int, speed_mps: int, ref: Optional[dict] = None, overrides: Optional[Dict] = None,
                 car: bool = False, comparison: bool = False, ns3_like: bool = False):
    """``ns3-urban-3.5ghz`` with the sites of ``isd_m`` and constant speed ``speed_mps`` (8, 16 or 30).

    ``overrides`` (dotted keys, such as ``{"protocol.qout_window_s": 0.12}``) change the scenario
    further, for calibration experiments.  ``car`` adds the in-car loss that ns-3 applies at this
    speed (:func:`car_loss`).  ``comparison`` applies :data:`COMPARISON_SETTING` (2.5.0) before
    ``overrides``; the setting is meant for ``car=True`` (not validated).  ``ns3_like`` applies
    :data:`NS3_LIKE_SETTING` instead (imitates ns-3, not 3GPP; meant for ``car=True``; validation pending).
    """
    if comparison and ns3_like:
        raise ValueError("comparison and ns3_like are two different settings; choose one")
    ref = ref or load_reference()
    mob = ({"mobility.profile": "c%d" % speed_mps} if speed_mps in (8, 16, 30) else
           {"mobility.groups": [{"share": 1.0, "v_min": speed_mps, "v_max": speed_mps, "lateral_m": [0.0, 0.0]}]})
    sc = builtin_scenario("ns3-urban-3.5ghz").with_overrides(dict(mob, **{
        "name": "ns3-urban-3.5ghz-%dm-%dmps" % (isd_m, speed_mps),
        "layout.sites": ref["sites"][str(isd_m)]}))
    if car and car_loss(speed_mps):
        sc = sc.with_overrides(car_loss(speed_mps))
    if comparison:
        sc = sc.with_overrides(dict(COMPARISON_SETTING))
    if ns3_like:
        sc = sc.with_overrides(dict(NS3_LIKE_SETTING))
    return sc.with_overrides(overrides) if overrides else sc


def spearman(a: Sequence[float], b: Sequence[float]) -> float:
    from scipy.stats import spearmanr
    return float(spearmanr(a, b)[0])


def compare(seeds: Sequence[int] = (500,), progress: Optional[Callable[[str], None]] = None,
            overrides: Optional[Dict] = None, car: bool = False, reference: Optional[str] = None,
            comparison: bool = False, ns3_like: bool = False) -> Dict:
    """Run part A of the reference in HandoverLab and return the per-setting table and the summary.

    ``overrides`` change the scenario of every condition and ``car`` adds the in-car loss of ns-3
    (see :func:`scenario_for`); ``reference`` is another reference file (:func:`load_reference`);
    ``comparison`` applies :data:`COMPARISON_SETTING` (2.5.0) to every condition, ``ns3_like``
    :data:`NS3_LIKE_SETTING`.
    """
    ref = load_reference(reference)
    rows = [r for r in ref["rows"] if r["part"] == "A"]
    settings = sorted({(r["a3_offset_db"], r["ttt_ms"]) for r in rows})
    conds = sorted({(r["isd_m"], r["speed_mps"]) for r in rows})
    rules = [{"rule": "a3", "name": "A3_%g_%d" % (h, t), "off_db": h, "ttt_s": t / 1000.0} for h, t in settings]
    keys = ("attempts_pm", "unnecessary_pm", "failures_pm", "sinr_db")
    sim = {}
    for isd, v in conds:
        sc = scenario_for(isd, v, ref, overrides, car, comparison, ns3_like)
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
        ttt_trend_ns3=_trend(table, "ns3"), ttt_trend=_trend(table, "handoverlab"),
        uho_mean_ns3=float(R[:, 1].mean()), uho_mean=float(S[:, 1].mean()),
        seeds=list(seeds), conditions=[list(c) for c in conds], car=bool(car), comparison=bool(comparison),
        ns3_like=bool(ns3_like))
    return dict(table=table, summary=summ)


def _trend(table, who: str) -> float:
    """Failure rate at the longest over the shortest time-to-trigger (mean over the offsets)."""
    t = sorted({x["ttt_ms"] for x in table})
    lo = np.mean([x[who][2] for x in table if x["ttt_ms"] == t[0]])
    hi = np.mean([x[who][2] for x in table if x["ttt_ms"] == t[-1]])
    return float(hi / lo) if lo > 0 else float("inf")


def holdout(seeds: Sequence[int] = (500,), progress: Optional[Callable[[str], None]] = None,
            overrides: Optional[Dict] = None, car: bool = False, reference: Optional[str] = None,
            comparison: bool = False, ns3_like: bool = False) -> Dict:
    """Run the held-back parts B and C of the reference (see the module text) and compare them cell by cell.

    Part B: two A3 settings on six conditions; part C: one setting with one parameter changed per cell
    (users, preparation delay, T310, site distance, run length, speed).  ``overrides`` change every
    scenario and ``car`` adds the in-car loss of ns-3, as in :func:`compare`; tune only on part A.
    ``comparison`` applies :data:`COMPARISON_SETTING` (2.5.0), ``ns3_like`` :data:`NS3_LIKE_SETTING`.
    """
    ref = load_reference(reference)
    cells = [r for r in ref["rows"] if r["part"] in ("B", "C")]
    jobs: Dict[tuple, list] = {}
    for r in cells:
        ov = dict(r.get("overrides", {}))
        ov["run.duration_s"] = r.get("duration_s", 180.0)
        key = (r["isd_m"], r["speed_mps"], json.dumps(ov, sort_keys=True))
        jobs.setdefault(key, []).append(r)
    table = []
    for (isd, v, ovs), rows in jobs.items():
        sc = scenario_for(isd, v, ref, overrides, car, comparison, ns3_like).with_overrides(json.loads(ovs))
        rules = [{"rule": "a3", "name": "A3_%g_%d" % (r["a3_offset_db"], r["ttt_ms"]), "off_db": r["a3_offset_db"],
                  "ttt_s": r["ttt_ms"] / 1000.0} for r in rows]
        res = simulate(sc, rules, seeds=seeds)
        for r, rule in zip(rows, rules):
            m = np.mean([[x.metrics[k] for k in ("attempts_pm", "unnecessary_pm", "failures_pm", "sinr_db")]
                         for x in res if x.rule == rule["name"]], axis=0)
            table.append(dict(part=r["part"], variant=r.get("variant", ""), isd_m=isd, speed_mps=v,
                              a3_offset_db=r["a3_offset_db"], ttt_ms=r["ttt_ms"],
                              ns3=[r["handovers_pm"], r["unnecessary_pm"], r["failures_pm"], r["sinr_db"]],
                              handoverlab=m.tolist()))
        if progress:
            progress("ns-3 hold-out: %d m, %d m/s %s done" % (isd, v, rows[0].get("variant", "")))
    summ = dict(seeds=list(seeds))
    for part in ("B", "C"):
        R = np.array([x["ns3"] for x in table if x["part"] == part])
        S = np.array([x["handoverlab"] for x in table if x["part"] == part])
        summ[part] = dict(cells=len(R), fail_mean_ns3=float(R[:, 2].mean()), fail_mean=float(S[:, 2].mean()),
                          fail_ratio=float(S[:, 2].mean() / R[:, 2].mean()), fail_rank=spearman(R[:, 2], S[:, 2]),
                          ho_ratio_median=float(np.median(S[:, 0] / R[:, 0])))
    return dict(table=table, summary=summ)


def ns3_checks(rep, seeds: Sequence[int] = (500,), progress=None, reference: Optional[str] = None,
               comparison: bool = False, ns3_like: bool = False) -> Dict:
    """The check group ``ns3``.  ``comparison`` (2.5.0) runs HandoverLab with :data:`COMPARISON_SETTING`
    and the in-car loss of ns-3 (``car=True``); a setting that brings the failure level closer, not validated.
    ``ns3_like`` runs it with :data:`NS3_LIKE_SETTING` and the in-car loss (imitates ns-3; validation pending)."""
    rep.section("ns3", "reference comparison with ns-3 / 5G-LENA (24 A3 settings x 4 conditions, %d seed%s%s%s)"
                % (len(seeds), "s" if len(seeds) > 1 else "", "; reference %s" % reference if reference else "",
                   "; comparison setting with the in-car loss" if comparison else
                   "; ns-3-like setting with the in-car loss" if ns3_like else ""))
    out = compare(seeds, progress, reference=reference, car=comparison or ns3_like, comparison=comparison,
                  ns3_like=ns3_like)
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
    rep.note("failure rate (no limit; comparison setting, not validated: 0.5-1.3 of ns-3)" if comparison else
             "failure rate (no limit; ns-3-like setting, validation pending)" if ns3_like else
             "failure rate (no limit: interfering load defined differently)",
             "mean %.3f / %.3f per UE-min, rank correlation %.2f"
             % (s["fail_mean"], s["fail_mean_ns3"], s["fail_rank"]))
    rep.note("mean serving SINR (no limit)", "%.1f dB / %.1f dB" % (s["sinr_mean"], s["sinr_mean_ns3"]))
    return out
