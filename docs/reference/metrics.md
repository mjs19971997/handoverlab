# Metric names

Every run returns the metrics below in `RunResult.metrics` and in the result files (CSV columns,
JSON `metrics`). The names are part of the stable public surface (see [stability](../stability.md)):
within a major release a metric is never removed or renamed, and a name to be changed in a major
release is deprecated at least one minor release before it; the old name then keeps working as an
alias, with a warning.
Rates are per UE-minute of the measured part of the run (after the warm-up) and end in `_pm`.

| Metric | Unit | Definition |
|---|---|---|
| `ue_minutes` | UE-min | measured UE-minutes (users x (duration - warm-up)) |
| `attempts_pm` | 1/UE-min | handover attempts (a report for baseline handover, an execution for CHO) |
| `handovers_pm` | 1/UE-min | completed handovers |
| `executions_pm` | 1/UE-min | handover executions started |
| `unnecessary_pm` | 1/UE-min | unnecessary handovers: stay < T_min or mean SINR gain < theta_Q |
| `unnecessary_short_and_low_pm` | 1/UE-min | unnecessary with both a short stay and a low gain |
| `unnecessary_low_gain_pm` | 1/UE-min | completed handovers with a low gain (source would not fail) |
| `pingpong_pm` | 1/UE-min | handovers back to the previous cell within pingpong_s |
| `failures_pm` | 1/UE-min | all mobility failures (sum of the causes) |
| `too_late_pm` | 1/UE-min | failures caused by a late or missing handover |
| `too_early_pm` | 1/UE-min | attempts ending in an early failure (re-established in source or target) |
| `wrong_cell_pm` | 1/UE-min | attempts ending in a failure and re-establishment in a third cell |
| `prepared_cells_mean` | cells | mean number of prepared cells per UE (CHO) |
| `preparations_pm` | 1/UE-min | cell preparations requested (CHO) |
| `unused_preparations_pm` | 1/UE-min | prepared cells released or dropped without being used (CHO) |
| `lost_configurations_pm` | 1/UE-min | conditional configurations lost while T310 ran (CHO) |
| `reports_pm` | 1/UE-min | measurement reports |
| `releases_pm` | 1/UE-min | prepared cells released by the network (CHO) |
| `recoveries_pm` | 1/UE-min | failures recovered into a prepared cell (CHO) |
| `rlf_with_prepared_cell_pm` | 1/UE-min | link failures without handover while a cell was prepared |
| `interruption_s_pm` | s/UE-min | interruption by executions and re-establishments |
| `interruption_exec_s_pm` | s/UE-min | interruption by handover executions |
| `interruption_fail_s_pm` | s/UE-min | interruption by re-establishments after failures |
| `outage_pct` | % | share of UE time interrupted or below Qout |
| `rate_mbps` | Mbit/s | mean delivered rate per user |
| `delivered_share` | 1 | delivered share of the demanded rate |
| `sinr_db` | dB | mean serving SINR of connected users |
| `spectral_eff` | bit/s/Hz | mean spectral efficiency of connected users |
| `mean_load` | 1 | mean cell load |
| `open_preparations` | cells | preparations still open at the end of the run |
| `commands_pm` | 1/UE-min | handover commands sent (baseline and DAPS handover, LTM cell switch), also those that arrive while T310 runs |
| `rrc_messages_pm` | 1/UE-min | RRC messages over the air: measurement reports + handover commands + conditional configurations (delivered or lost) + releases + handover completions |
| `l1_measurements_pm` | 1/UE-min | L1 measurement samples taken by a connected user (one per cell and L1 period); a proxy for the measurement energy of the device |
| `site_power_w` | W | mean input power per site, EARTH model: `radio.energy_p0_w` + `radio.energy_slope` x transmit power x load |
| `energy_uj_per_bit` | uJ/bit | network energy per delivered bit: the input power of all sites / the delivered rate of all users |
| `fail_command_lost_pm` | 1/UE-min | failures with cause command_lost |
| `fail_rlf_in_preparation_pm` | 1/UE-min | failures with cause rlf_in_preparation |
| `fail_rlf_without_handover_pm` | 1/UE-min | failures with cause rlf_without_handover |
| `fail_coverage_rlf_pm` | 1/UE-min | failures with cause coverage_rlf |
| `fail_execution_failure_pm` | 1/UE-min | failures with cause execution_failure |
| `fail_rlf_after_handover_pm` | 1/UE-min | failures with cause rlf_after_handover |

## Counts

Next to the rates, a run returns the event counts of the measured part of the run (integers):

`n_attempts`, `n_executions`, `n_handovers`, `n_failures`, `n_pingpong`, `n_reports`, `n_preparations`, `n_configurations`, `n_lost_configurations`, `n_cancelled_preparations`, `n_used_preparations`, `n_unused_preparations`, `n_releases`, `n_recoveries`, `n_commands`, `n_useful`, `n_unnecessary`, `n_too_early`, `n_wrong_cell`, `n_too_late`, `n_censored`, `n_fail_command_lost`, `n_fail_rlf_in_preparation`, `n_fail_rlf_without_handover`, `n_fail_coverage_rlf`, `n_fail_execution_failure`, `n_fail_rlf_after_handover`.

**Signalling and energy (1.5.0).** `rrc_messages_pm` counts the messages of TS 38.331 that a
handover procedure sends over the air: a `MeasurementReport` per report, an `RRCReconfiguration`
per handover command, per conditional configuration (delivered, or lost while T310 runs) and per
release of a prepared cell, and an `RRCReconfigurationComplete` per completed handover. Messages
between base stations (Xn) and re-establishment messages are not counted. The energy model is the
linear EARTH model of a micro base station (Auer et al., "How much energy is needed to run a
wireless network?", IEEE Wireless Communications 18(5), 2011): input power
`P_in = P0 + Delta_p x P_tx x load` with `P0` = 56 W and `Delta_p` = 2.6 by default, and `P_tx`
the transmit power of the scenario. Sleep modes are not modelled. Add the new metrics to
`compare.metrics` of a study to see them in its report.

For DAPS handover, `too_early_pm` and `n_too_early` also count executions that fell back to the
source (event-log cause `daps_fallback`); these are not failures. For L1/L2-triggered mobility the
preparation counts refer to candidate cells.

The outcome counts `n_useful` ... `n_censored` add up to the attempts; the failure counts
`n_fail_<cause>` add up to `n_failures`. The definitions of the outcomes and causes are in the
[user guide](../user_guide.md#7-metrics).
