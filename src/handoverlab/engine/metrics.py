# SPDX-License-Identifier: MIT
"""Counters of a run and the metric catalogue.

Rates are given per UE-minute of the measured part of the run (after the
warm-up), with the suffix ``_pm``.  Counts start with ``n_``.
"""
from __future__ import annotations

from typing import Dict

OUTCOMES = ("useful", "unnecessary", "too_early", "wrong_cell", "too_late", "censored")
CAUSES = ("command_lost", "rlf_in_preparation", "rlf_without_handover", "coverage_rlf", "execution_failure",
          "rlf_after_handover")

# internal counter -> public count name
_COUNTS = {
    "att": "n_attempts", "exec": "n_executions", "ho": "n_handovers", "fail": "n_failures", "pp": "n_pingpong",
    "reports": "n_reports", "prep_req": "n_preparations", "cfg_ok": "n_configurations",
    "cfg_lost": "n_lost_configurations", "prep_cancel": "n_cancelled_preparations",
    "prep_used": "n_used_preparations", "prep_wasted": "n_unused_preparations", "rel": "n_releases",
    "rec": "n_recoveries",
}

#: name -> (unit, definition) of every metric returned by a run
METRICS: Dict[str, tuple] = {
    "ue_minutes": ("UE-min", "measured UE-minutes (users x (duration - warm-up))"),
    "attempts_pm": ("1/UE-min", "handover attempts (a report for baseline handover, an execution for CHO)"),
    "handovers_pm": ("1/UE-min", "completed handovers"),
    "executions_pm": ("1/UE-min", "handover executions started"),
    "unnecessary_pm": ("1/UE-min", "unnecessary handovers: stay < T_min or mean SINR gain < theta_Q"),
    "unnecessary_short_and_low_pm": ("1/UE-min", "unnecessary with both a short stay and a low gain"),
    "unnecessary_low_gain_pm": ("1/UE-min", "completed handovers with a low gain (source would not fail)"),
    "pingpong_pm": ("1/UE-min", "handovers back to the previous cell within pingpong_s"),
    "failures_pm": ("1/UE-min", "all mobility failures (sum of the causes)"),
    "too_late_pm": ("1/UE-min", "failures caused by a late or missing handover"),
    "too_early_pm": ("1/UE-min", "attempts ending in an early failure (re-established in source or target)"),
    "wrong_cell_pm": ("1/UE-min", "attempts ending in a failure and re-establishment in a third cell"),
    "prepared_cells_mean": ("cells", "mean number of prepared cells per UE (CHO)"),
    "preparations_pm": ("1/UE-min", "cell preparations requested (CHO)"),
    "unused_preparations_pm": ("1/UE-min", "prepared cells released or dropped without being used (CHO)"),
    "lost_configurations_pm": ("1/UE-min", "conditional configurations lost while T310 ran (CHO)"),
    "reports_pm": ("1/UE-min", "measurement reports"),
    "releases_pm": ("1/UE-min", "prepared cells released by the network (CHO)"),
    "recoveries_pm": ("1/UE-min", "failures recovered into a prepared cell (CHO)"),
    "rlf_with_prepared_cell_pm": ("1/UE-min", "link failures without handover while a cell was prepared"),
    "interruption_s_pm": ("s/UE-min", "interruption by executions and re-establishments"),
    "interruption_exec_s_pm": ("s/UE-min", "interruption by handover executions"),
    "interruption_fail_s_pm": ("s/UE-min", "interruption by re-establishments after failures"),
    "outage_pct": ("%", "share of UE time interrupted or below Qout"),
    "rate_mbps": ("Mbit/s", "mean delivered rate per user"),
    "delivered_share": ("1", "delivered share of the demanded rate"),
    "sinr_db": ("dB", "mean serving SINR of connected users"),
    "spectral_eff": ("bit/s/Hz", "mean spectral efficiency of connected users"),
    "mean_load": ("1", "mean cell load"),
    "open_preparations": ("cells", "preparations still open at the end of the run"),
}
for _c in CAUSES:
    METRICS["fail_%s_pm" % _c] = ("1/UE-min", "failures with cause %s" % _c)


class Counters(dict):
    """Integer counters of a run; every name starts at zero."""

    def __init__(self):
        super().__init__({k: 0 for k in list(_COUNTS) + ["un_and", "un_gain", "rlf_prepared", "att_all"]})
        self.update({"n_" + o: 0 for o in OUTCOMES})
        self.update({"f_" + c: 0 for c in CAUSES})


def summarize(C: Counters, acc: dict, ue_min: float, ue_s: float, n_users: int, step_s: float,
              open_preparations: int) -> Dict[str, float]:
    """Metric dictionary of a finished run (see :data:`METRICS`)."""
    late = C["f_command_lost"] + C["f_rlf_in_preparation"] + C["f_rlf_without_handover"]
    out = dict(
        ue_minutes=ue_min,
        attempts_pm=C["att"] / ue_min, handovers_pm=C["ho"] / ue_min, executions_pm=C["exec"] / ue_min,
        unnecessary_pm=C["n_unnecessary"] / ue_min, unnecessary_short_and_low_pm=C["un_and"] / ue_min,
        unnecessary_low_gain_pm=C["un_gain"] / ue_min,
        pingpong_pm=C["pp"] / ue_min, failures_pm=C["fail"] / ue_min, too_late_pm=late / ue_min,
        too_early_pm=C["n_too_early"] / ue_min, wrong_cell_pm=C["n_wrong_cell"] / ue_min,
        prepared_cells_mean=acc["prep_time"] / ue_s, preparations_pm=C["prep_req"] / ue_min,
        unused_preparations_pm=C["prep_wasted"] / ue_min, lost_configurations_pm=C["cfg_lost"] / ue_min,
        reports_pm=C["reports"] / ue_min, releases_pm=C["rel"] / ue_min, recoveries_pm=C["rec"] / ue_min,
        rlf_with_prepared_cell_pm=C["rlf_prepared"] / ue_min,
        interruption_s_pm=(acc["int_exec"] + acc["int_fail"]) / ue_min,
        interruption_exec_s_pm=acc["int_exec"] / ue_min, interruption_fail_s_pm=acc["int_fail"] / ue_min,
        outage_pct=100.0 * (acc["int_exec"] + acc["int_fail"] + acc["out_steps"] * step_s) / ue_s,
        rate_mbps=acc["thr"] / max(acc["nmeas"], 1) / n_users / 1e6,
        delivered_share=acc["thr"] / max(acc["dem"], 1e-9),
        sinr_db=acc["sinr"] / max(acc["ncon"], 1), spectral_eff=acc["se"] / max(acc["ncon"], 1),
        mean_load=acc["load"] / max(acc["nmeas"], 1),
        open_preparations=open_preparations,
    )
    for c in CAUSES:
        out["fail_%s_pm" % c] = C["f_" + c] / ue_min
    for k, name in _COUNTS.items():
        out[name] = C[k]
    for o in OUTCOMES:
        out["n_" + o] = C["n_" + o]
    for c in CAUSES:
        out["n_fail_" + c] = C["f_" + c]
    return out
