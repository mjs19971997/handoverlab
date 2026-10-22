# SPDX-License-Identifier: MIT
"""Counters of a run and the metric catalogue.

Rates are given per UE-minute of the measured part of the run (after the
warm-up), with the suffix ``_pm``.  Counts start with ``n_``.
"""
from __future__ import annotations

from typing import Dict

OUTCOMES = ("useful", "unnecessary", "too_early", "wrong_cell", "too_late", "censored", "coverage")
CAUSES = ("command_lost", "rlf_in_preparation", "rlf_without_handover", "coverage_rlf", "execution_failure",
          "rlf_after_handover")

# internal counter -> public count name
_COUNTS = {
    "att": "n_attempts", "exec": "n_executions", "ho": "n_handovers", "fail": "n_failures", "pp": "n_pingpong",
    "reports": "n_reports", "prep_req": "n_preparations", "cfg_ok": "n_configurations",
    "cfg_lost": "n_lost_configurations", "prep_cancel": "n_cancelled_preparations",
    "prep_used": "n_used_preparations", "prep_wasted": "n_unused_preparations", "rel": "n_releases",
    "rec": "n_recoveries", "cmd": "n_commands",
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
    "too_late_pm": ("1/UE-min", "failures caused by a late or missing handover (since 2.1.0 with re-establishment "
                                "in another cell, TS 38.300 15.5.2.2.2)"),
    "too_early_pm": ("1/UE-min", "attempts ending in an early failure (re-established in the source; up to 2.0.0 "
                                 "also in the target)"),
    "wrong_cell_pm": ("1/UE-min", "attempts ending in a failure and re-establishment in a third cell"),
    "coverage_failures_pm": ("1/UE-min", "attempts ending in a failure with re-establishment in the serving cell (the "
                                         "target after a handover): not one of the MRO classes of TS 38.300 15.5.2.2.2 "
                                         "(since 2.1.0)"),
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
    # signalling and energy (since 1.5.0; derived from counters, the event log is unchanged)
    "commands_pm": ("1/UE-min", "handover commands sent (baseline and DAPS handover, LTM cell switch), also those "
                                "that arrive while T310 runs"),
    "rrc_messages_pm": ("1/UE-min", "RRC messages over the air: measurement reports + handover commands + "
                                    "conditional configurations (delivered or lost) + releases + handover completions"),
    "l1_measurements_pm": ("1/UE-min", "L1 measurement samples taken by a connected user (one per cell and L1 "
                                       "period); a proxy for the measurement energy of the device"),
    "site_power_w": ("W", "mean input power per cell (a sector counts as a cell), EARTH model: energy_ntrx x "
                          "energy_p0_w + energy_slope x transmit power of the cell's layer x load"),
    "energy_uj_per_bit": ("uJ/bit", "network energy per delivered bit: all cells' input power / delivered rate"),
    # beams and several carriers (since 1.10.0; zero without these options)
    "beam_switches_pm": ("1/UE-min", "serving-beam (TCI state) changes after beam reports"),
    "beam_failures_pm": ("1/UE-min", "beam failures detected (BFI_COUNTER reached beamFailureInstanceMaxCount)"),
    "beam_recoveries_pm": ("1/UE-min", "beam failure recoveries completed by random access"),
    "beam_recovery_failures_pm": ("1/UE-min", "beam failure recoveries that ended in a random-access problem "
                                              "(a radio-link failure)"),
    "beam_recovery_s_pm": ("s/UE-min", "time spent in beam failure recovery"),
    "inter_frequency_handovers_pm": ("1/UE-min", "completed handovers between cells of different carriers"),
    "gap_share": ("1", "share of the UE time in measurement gaps while connected (no data in a gap)"),
}
for _c in CAUSES:
    METRICS["fail_%s_pm" % _c] = ("1/UE-min", "failures with cause %s" % _c)


# counters over the whole run including the warm-up (for the conservation checks)
_ALL_TIME = ("prep_req_all", "prep_lost_all", "prep_cancel_all", "prep_used_all", "prep_wasted_all")


class Counters(dict):
    """Integer counters of a run; every name starts at zero."""

    def __init__(self):
        super().__init__({k: 0 for k in list(_COUNTS) + ["un_and", "un_gain", "rlf_prepared", "att_all",
                                                        "closed_all", "late_f", "rrc", "rrc_on"] + list(_ALL_TIME)})
        self.update({"n_" + o: 0 for o in OUTCOMES})
        self.update({"f_" + c: 0 for c in CAUSES})


def summarize(C: Counters, acc: dict, ue_min: float, ue_s: float, n_users: int, step_s: float,
              open_preparations: int, n_sites: int = 1, l1_per_meas: int = 1, power=(0.0, 0.0)) -> Dict[str, float]:
    """Metric dictionary of a finished run (see :data:`METRICS`)."""
    late = C["late_f"]                                   # failures classified too late (see Engine.fail)
    out = dict(
        ue_minutes=ue_min,
        attempts_pm=C["att"] / ue_min, handovers_pm=C["ho"] / ue_min, executions_pm=C["exec"] / ue_min,
        unnecessary_pm=C["n_unnecessary"] / ue_min, unnecessary_short_and_low_pm=C["un_and"] / ue_min,
        unnecessary_low_gain_pm=C["un_gain"] / ue_min,
        pingpong_pm=C["pp"] / ue_min, failures_pm=C["fail"] / ue_min, too_late_pm=late / ue_min,
        too_early_pm=C["n_too_early"] / ue_min, wrong_cell_pm=C["n_wrong_cell"] / ue_min,
        coverage_failures_pm=C["n_coverage"] / ue_min,
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
        commands_pm=C["cmd"] / ue_min,
        rrc_messages_pm=(C["rrc"] if C["rrc_on"] else
                         C["reports"] + C["cmd"] + C["cfg_ok"] + C["cfg_lost"] + C["rel"] + C["ho"]) / ue_min,
        l1_measurements_pm=acc["ncon"] * l1_per_meas * n_sites / ue_min,
    )
    p0, p_load = power                                   # site power = p0 + p_load x mean load
    out["site_power_w"] = p0 + p_load * out["mean_load"]
    bits = acc["thr"] / max(acc["nmeas"], 1)             # delivered bit/s of all users
    out["energy_uj_per_bit"] = 1e6 * n_sites * out["site_power_w"] / bits if bits > 0 else float("nan")
    for c in CAUSES:
        out["fail_%s_pm" % c] = C["f_" + c] / ue_min
    out["beam_switches_pm"] = C.get("beam_switch", 0) / ue_min
    out["beam_failures_pm"] = C.get("bfr", 0) / ue_min
    out["beam_recoveries_pm"] = C.get("bfr_ok", 0) / ue_min
    out["beam_recovery_failures_pm"] = C.get("bfr_fail", 0) / ue_min
    out["beam_recovery_s_pm"] = acc.get("bfr_time", 0.0) / ue_min
    out["inter_frequency_handovers_pm"] = C.get("ho_inter", 0) / ue_min
    out["gap_share"] = acc.get("gap_time", 0.0) / ue_s
    for k, name in _COUNTS.items():
        out[name] = C[k]
    for o in OUTCOMES:
        out["n_" + o] = C["n_" + o]
    for c in CAUSES:
        out["n_fail_" + c] = C["f_" + c]
    return out
