# Scenario card: `highway-10ghz`

*The TR 37.885 highway with roadside sites at 10 GHz*  
Available since version 1.0.0rc3. Use it as `scenario: highway-10ghz` in a configuration file or `hl.builtin_scenario("highway-10ghz")` in Python.

## Purpose

A vehicular counterpart of the urban grid: a straight road of 2000 m with three lanes of 4 m per direction (the highway case of TR 37.885), roadside sites every 500 m (the inter-site distance of the TR 37.885 highway set-up above 6 GHz), 35 m beyond the road edge and alternately on the two sides, and lane-keeping vehicles at 70 to 140 km/h.  The sites follow a line, so every handover is between two neighbours along the road and happens at high speed: short times of stay, few candidate cells and a large share of late handovers.  Use it to see how a rule copes with speed rather than with dense, irregular coverage.

## Layout

![Layout of highway-10ghz](highway-10ghz.svg)

A 2000 m road along the x axis (24 m wide: 3 + 3 lanes of 4 m), four sites at 500 m spacing, 35 m from the road edge and alternately on the two sides.  The drawing is to scale, so the road is a thin band.

## Parameters

Values in **bold** differ from the HandoverLab defaults.

| Key | Value | Source |
|---|---|---|
| `layout.kind` | **highway** | TR 37.885 Annex A, Table A-1 (highway) |
| `layout.blocks` | [3, 3] | TR 37.885 Table A-1 (minimum 3 x 3 blocks) |
| `layout.pitch_m` | [433, 250] | TR 37.885 Annex A (433 m x 250 m) |
| `layout.street_width_m` | 20 | TR 37.885 Annex A (20 m) |
| `layout.site_spacing_m` | **500** | TR 37.885 clause 6.1.3 (highway above 6 GHz: inter-site distance 500 m) |
| `layout.site_offset_m` | **35** | assumption (35 m from the road edge, after the 35 m freeway offset of TR 36.885 clause A.1.3) |
| `layout.sites` | none | regular placement along the streets |
| `layout.lanes` | 3 | TR 37.885 Table A-1 (highway: 3 lanes per direction) |
| `layout.lane_width_m` | 4 | TR 37.885 Table A-1 (highway: 4 m lanes) |
| `layout.road_length_m` | 2000 | TR 37.885 Table A-1 (highway: at least 2000 m) |
| `layout.sites_file` | none | none (sites from the layout) |
| `radio.carrier_ghz` | 10 | assumption (upper mid-band, 7-24 GHz) |
| `radio.bandwidth_mhz` | 200 | assumption |
| `radio.tx_power_dbm` | 35 | assumption (small cell) |
| `radio.bs_gain_db` | 20 | assumption (beam gain, no beam management) |
| `radio.ue_gain_db` | 0 | assumption |
| `radio.noise_figure_db` | 7 | assumption (typical UE noise figure) |
| `radio.isolation` | 0.3 | assumption (mean-to-peak gain of an interfering data beam) |
| `radio.bs_height_m` | **25** | TR 38.901 Table 7.4.1-1 (UMa: 25 m) |
| `radio.ue_height_m` | 1.5 | TR 38.901 Table 7.4.1-1 (1.5 m) |
| `radio.pathloss` | **uma** | TR 38.901 Table 7.4.1-1 (UMa) |
| `radio.shadow_los_db` | 4 | TR 38.901 Table 7.4.1-1 (UMi and UMa LOS: 4 dB) |
| `radio.shadow_nlos_db` | **6** | TR 38.901 Table 7.4.1-1 (UMa NLOS: 6 dB) |
| `radio.shadow_decorr_m` | **37** | TR 38.901 Table 7.5-6 (UMa LOS: 37 m) |
| `radio.shadow_site_corr` | 0.5 | assumption (correlation between sites) |
| `radio.place_share` | 1 | assumption (blockage tied to place) |
| `radio.clutter_los` | true | TR 38.901 clause 7.6.3.3 (spatially consistent LOS state) |
| `radio.los_corr_m` | 50 | TR 38.901 Table 7.6.3.1-2 (LOS/NLOS state, UMi and UMa: 50 m) |
| `radio.time_var_db` | 1.5 | assumption (moving blockers) |
| `radio.time_var_tau_s` | 1 | assumption |
| `radio.l1_error_db` | 1 | assumption (error of one L1 RSRP sample) |
| `radio.penetration_db` | 0 | off by default; TR 38.901 clause 7.4.3.2: 9 dB in a standard car |
| `radio.penetration_sd_db` | 0 | off by default; TR 38.901 clause 7.4.3.2: 5 dB in a standard car |
| `radio.map_res_m` | 1 | numerical setting |
| `protocol.step_s` | 0.01 | numerical setting |
| `protocol.l1_period_s` | 0.04 | assumption (L1 sample period) |
| `protocol.l3_k` | 4 | TS 38.331 clause 5.5.3.2 |
| `protocol.label_period_s` | 0.2 | numerical setting |
| `protocol.report_interval_s` | 0.12 | TS 38.331 reportInterval (ms120) |
| `protocol.qout_db` | -8 | TR 36.839 (Qout -8 dB) |
| `protocol.qin_db` | -6 | TR 36.839 (Qin -6 dB) |
| `protocol.qout_window_s` | 0.2 | TS 38.133 (evaluation period, 200 ms) |
| `protocol.qin_window_s` | 0.1 | TS 38.133 (evaluation period, 100 ms) |
| `protocol.n310` | 1 | TR 36.839 |
| `protocol.n311` | 1 | TR 36.839 |
| `protocol.t310_s` | 1 | TR 36.839 (1 s) |
| `protocol.prep_s` | 0.05 | TR 36.839 (50 ms) |
| `protocol.exec_s` | 0.04 | TR 36.839 (40 ms) |
| `protocol.reest_s` | 1 | TR 36.842 (assumption: 1 s outage) |
| `protocol.cho_recovery_s` | 0.4 | TS 38.300 clause 9.2.3.4 (recovery into a prepared cell; assumption 0.4 s) |
| `protocol.pingpong_s` | 1 | TR 36.839 (minimum time of stay, 1 s) |
| `protocol.cfg_loss_as_failure` | false | check mode only |
| `protocol.lm_load` | none | off by default: link monitoring sees the load of the data channel (calibration option) |
| `protocol.lm_load_per_ue` | 0 | off by default (calibration option) |
| `protocol.exec_can_fail` | true | TR 36.839: the execution fails when the target is below Qout |
| `protocol.rlm_holdoff_s` | 0 | off by default; TS 38.133 clause 8.1: out-of-sync evaluation of 0.2 s on a new cell |
| `traffic.services` | 5 entries | TS 23.501 Table 5.7.4-1 (5QI); thresholds are assumptions |
| `traffic.se_max` | 7.4 | assumption (spectral-efficiency cap) |
| `traffic.hotspot_share` | 0.25 | assumption |
| `traffic.hotspot_load` | [0.55, 0.85] | assumption |
| `traffic.normal_load` | [0.05, 0.25] | assumption |
| `traffic.load_tau_s` | 0.2 | assumption |
| `traffic.rate_scale` | 1 | assumption |
| `traffic.label_load` | 1 | assumption (all cells transmit for the label) |
| `traffic.model` | fixed | fixed: constant service rates (the model of 1.0) |
| `traffic.period_s` | 0.02 | periodic model: 20 ms, as VoIP |
| `traffic.packet_bytes` | 100 | periodic model: assumption |
| `traffic.ftp_file_bytes` | 500000 | TR 36.814 A.2.1.3 (FTP model 3: 0.5 Mbyte) |
| `traffic.ftp_rate_hz` | 0.1 | ftp3 model: assumption (file arrival rate per user) |
| `mobility.users` | 40 | assumption |
| `mobility.profile` | **hwy** | TR 37.885 clause 6.1.2 (highway: 140 km/h, optionally 70 km/h); uniform between them is an assumption |
| `mobility.groups` | none | profile |
| `run.duration_s` | 120 | numerical setting |
| `run.warmup_s` | 20 | numerical setting |

## Known limitations

- The road has no wrap-around: at its end a vehicle turns into the same lane of the other direction, so the ends of the road are crossed twice as often as the middle is passed, and the outermost sites see turning vehicles.
- The LOS state follows the TR 38.901 UMa LOS probability as a process along each vehicle's path; on an open road it stands for blocking by other vehicles and roadside obstacles and is more pessimistic than a free highway.
- No Doppler, no fast fading and no vehicle-to-vehicle links; received-power level only, as in the other scenarios.
- The failure model is not calibrated in absolute terms; read failure rates relative to each other.

## Reference results

- Layout geometry, lane keeping, speeds and the turn at the road end are checked in the unit tests; determinism and invariant checks as for every scenario.
