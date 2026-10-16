# Metric names

Every run returns the metrics below in `RunResult.metrics` and in the result files (CSV columns,
JSON `metrics`). The names are part of the stable public surface (see [stability](../stability.md)):
within a major release a metric is never removed or renamed, and a name that changes in a major
release keeps working as an alias, with a warning, for at least one minor release before it.
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
| `fail_command_lost_pm` | 1/UE-min | failures with cause command_lost |
| `fail_rlf_in_preparation_pm` | 1/UE-min | failures with cause rlf_in_preparation |
| `fail_rlf_without_handover_pm` | 1/UE-min | failures with cause rlf_without_handover |
| `fail_coverage_rlf_pm` | 1/UE-min | failures with cause coverage_rlf |
| `fail_execution_failure_pm` | 1/UE-min | failures with cause execution_failure |
| `fail_rlf_after_handover_pm` | 1/UE-min | failures with cause rlf_after_handover |

## Counts

Next to the rates, a run returns the event counts of the measured part of the run (integers):

`n_attempts`, `n_executions`, `n_handovers`, `n_failures`, `n_pingpong`, `n_reports`, `n_preparations`, `n_configurations`, `n_lost_configurations`, `n_cancelled_preparations`, `n_used_preparations`, `n_unused_preparations`, `n_releases`, `n_recoveries`, `n_useful`, `n_unnecessary`, `n_too_early`, `n_wrong_cell`, `n_too_late`, `n_censored`, `n_fail_command_lost`, `n_fail_rlf_in_preparation`, `n_fail_rlf_without_handover`, `n_fail_coverage_rlf`, `n_fail_execution_failure`, `n_fail_rlf_after_handover`.

For DAPS handover, `too_early_pm` and `n_too_early` also count executions that fell back to the
source (event-log cause `daps_fallback`); these are not failures. For L1/L2-triggered mobility the
preparation counts refer to candidate cells.

The outcome counts `n_useful` ... `n_censored` add up to the attempts; the failure counts
`n_fail_<cause>` add up to `n_failures`. The definitions of the outcomes and causes are in the
[user guide](../user_guide.md#7-metrics).
