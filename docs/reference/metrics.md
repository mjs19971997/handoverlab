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
| `too_late_pm` | 1/UE-min | failures caused by a late or missing handover (since 2.1.0 with re-establishment in another cell, TS 38.300 15.5.2.2.2) |
| `too_early_pm` | 1/UE-min | attempts ending in an early failure (re-established in the source; up to 2.0.0 also in the target) |
| `wrong_cell_pm` | 1/UE-min | attempts ending in a failure and re-establishment in a third cell |
| `coverage_failures_pm` | 1/UE-min | attempts ending in a failure with re-establishment in the serving cell (the target after a handover): not one of the MRO classes of TS 38.300 15.5.2.2.2 (since 2.1.0) |
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
| `site_power_w` | W | mean input power per cell (a sector counts as a cell), EARTH model: `radio.energy_p0_w` + `radio.energy_slope` x transmit power of the cell's layer x load |
| `energy_uj_per_bit` | uJ/bit | network energy per delivered bit: the input power of all cells / the delivered rate of all users |
| `beam_switches_pm` | 1/UE-min | serving-beam (TCI state) changes after beam reports (since 1.10.0; 0 without `radio.beams`) |
| `beam_failures_pm` | 1/UE-min | beam failures detected: BFI_COUNTER reached beamFailureInstanceMaxCount (TS 38.321 5.17) |
| `beam_recoveries_pm` | 1/UE-min | beam failure recoveries completed by random access |
| `beam_recovery_failures_pm` | 1/UE-min | beam failure recoveries that ended in a random-access problem, i.e. a radio-link failure (TS 38.331 5.3.10.3) |
| `beam_recovery_s_pm` | s/UE-min | time spent in beam failure recovery |
| `inter_frequency_handovers_pm` | 1/UE-min | completed handovers between cells of different carriers (since 1.10.0; 0 on one carrier) |
| `gap_share` | 1 | share of the UE time in measurement gaps while connected; no data is received in a gap (TS 38.133 9.1.2) |
| `pdcp_delivered_kbyte_pm` | kbyte/UE-min | downlink PDCP data delivered (since 2.3.0; 0 without `protocol.buffers`, as all `pdcp_` metrics; see the [buffers guide](../guides/buffers.md)) |
| `pdcp_lost_kbyte_pm` | kbyte/UE-min | PDCP data lost (sum of the four causes below) |
| `pdcp_lost_share` | 1 | lost share of the PDCP data that arrived at the gNB |
| `pdcp_lost_handover_kbyte_pm` | kbyte/UE-min | data lost at handover executions: no forwarding, or HARQ data with RLC UM |
| `pdcp_lost_failure_kbyte_pm` | kbyte/UE-min | data lost at failures and re-establishments: no forwarding to another cell, or HARQ data with RLC UM |
| `pdcp_lost_discard_kbyte_pm` | kbyte/UE-min | data discarded by the PDCP discard timer (TS 38.323 5.3) |
| `pdcp_lost_harq_kbyte_pm` | kbyte/UE-min | transport blocks lost after the last HARQ transmission with RLC UM (slot scheduler) |
| `pdcp_lost_sdus_pm` | 1/UE-min | lost data in SDUs of `protocol.sdu_bytes` |
| `pdcp_forwarded_kbyte_pm` | kbyte/UE-min | data forwarded over Xn (DAPS: every SN-assigned byte of the execution, duplicates included) |
| `pdcp_forwarded_sdus_pm` | 1/UE-min | forwarded data in SDUs of `protocol.sdu_bytes` |
| `pdcp_delay_ms` | ms | mean PDCP delay: arrival at the gNB to delivery, byte-weighted |
| `pdcp_delay_p95_ms` | ms | 95th percentile of the PDCP delay (1 ms bins) |
| `pdcp_delay_forwarded_ms` | ms | mean PDCP delay of the delivered data that a target sent after forwarding |
| `fail_command_lost_pm` | 1/UE-min | failures with cause command_lost |
| `fail_rlf_in_preparation_pm` | 1/UE-min | failures with cause rlf_in_preparation |
| `fail_rlf_without_handover_pm` | 1/UE-min | failures with cause rlf_without_handover |
| `fail_coverage_rlf_pm` | 1/UE-min | failures with cause coverage_rlf |
| `fail_execution_failure_pm` | 1/UE-min | failures with cause execution_failure |
| `fail_rlf_after_handover_pm` | 1/UE-min | failures with cause rlf_after_handover |

## Counts

Next to the rates, a run returns the event counts of the measured part of the run (integers):

`n_attempts`, `n_executions`, `n_handovers`, `n_failures`, `n_pingpong`, `n_reports`, `n_preparations`, `n_configurations`, `n_lost_configurations`, `n_cancelled_preparations`, `n_used_preparations`, `n_unused_preparations`, `n_releases`, `n_recoveries`, `n_commands`, `n_useful`, `n_unnecessary`, `n_too_early`, `n_wrong_cell`, `n_too_late`, `n_coverage`, `n_censored`, `n_fail_command_lost`, `n_fail_rlf_in_preparation`, `n_fail_rlf_without_handover`, `n_fail_coverage_rlf`, `n_fail_execution_failure`, `n_fail_rlf_after_handover`.

**Signalling and energy (1.5.0).** `rrc_messages_pm` counts the messages of TS 38.331 that a
handover procedure sends over the air. Since 2.1.0 (`protocol.rrc_detail: 3gpp`) every message
counts once: a `MeasurementReport` per report, an `RRCReconfiguration` per handover command, one
`RRCReconfiguration` per user and instant for the conditional configurations it carries (however many
candidates) and for releases, and an `RRCReconfigurationComplete` for each of them and for each
completed handover; an LTM cell switch command is a MAC CE (TS 38.300 9.2.3.5.2) and is not counted.
With `simple` (2.0.0) every candidate counted as one message. Messages between base stations (Xn) and
re-establishment messages are not counted. The energy model is the linear EARTH model of a micro
base station (Auer et al., "How much energy is needed to run a wireless network?", IEEE Wireless
Communications 18(5), 2011, Eq. 1 and Table 2): input power
`P_in = N_TRX x P0 + Delta_p x P_tx x load` per cell (a sector of a site counts as one cell), which is
Eq. 1, `N_TRX (P0 + Delta_p P_out)`, with the transmit power shared by the transceivers
(`P_out = P_tx x load / N_TRX`). The defaults are the micro base station of Table 2: `N_TRX` = 2,
`P0` = 56 W, `Delta_p` = 2.6 (`radio.energy_ntrx`, `radio.energy_p0_w`, `radio.energy_slope`; 1.x and
2.0.0 left out `N_TRX`); `P_tx` is the transmit power of the cell's layer (since 2.1.0; before, the base
layer's power for every cell). Table 2 gives P_max = 6.3 W per transceiver (38 dBm) for this type; the
cards send more (35 to 49 dBm), and for macro cells Table 2 has N_TRX = 6, P0 = 130 W, Delta_p = 4.7. The same micro-base-station
coefficients are used on every card, also on the macro cards; set the three keys for another
base-station type. Sleep modes are not modelled. Add the new metrics to
`compare.metrics` of a study to see them in its report.

For DAPS handover, `too_early_pm` and `n_too_early` also count executions that fell back to the
source (event-log cause `daps_fallback`); these are not failures. For L1/L2-triggered mobility the
preparation counts refer to candidate cells.

The outcome counts `n_useful` ... `n_censored` add up to the attempts; the failure counts
`n_fail_<cause>` add up to `n_failures`. The definitions of the outcomes and causes are in the
[user guide](../user_guide.md#7-metrics).
