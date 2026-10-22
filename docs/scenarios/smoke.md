# Scenario card: `smoke`

*Small street grid that runs in seconds*  
Available since version 0.2.0. Use it as `scenario: smoke` in a configuration file or `hl.builtin_scenario("smoke")` in Python.

## Purpose

A quick, complete run of every part of the simulator: a 2 x 2-block street grid with buildings, the spatially consistent LOS state, place-tied shadowing, 20 vehicular users and 30 s of simulated time.  It is the scenario of the golden event-log fingerprints, of the rule contract checks (`handoverlab.testing.check_rule`) and of first experiments.  It is too small and too short for statistical conclusions.

## Layout

![Layout of smoke](smoke.svg)

Two by two blocks of the TR 37.885 urban grid (smaller than the minimum 3 x 3 area of TR 37.885 Table A-1), sites every 150 m along the streets.

## Parameters

Values in **bold** differ from the HandoverLab defaults.

| Key | Value | Source |
|---|---|---|
| `layout.kind` | street_grid | TR 37.885 Annex A (urban grid) |
| `layout.blocks` | **[2, 2]** | assumption (smaller than TR 37.885 Table A-1, for speed) |
| `layout.pitch_m` | [433, 250] | TR 37.885 Annex A (433 m x 250 m) |
| `layout.street_width_m` | 20 | TR 37.885 Annex A (20 m) |
| `layout.site_spacing_m` | **150** | assumption |
| `layout.site_offset_m` | 9 | assumption (sites on the pavement) |
| `layout.sites` | none | regular placement along the streets |
| `radio.carrier_ghz` | 10 | assumption (upper mid-band, 7-24 GHz) |
| `radio.bandwidth_mhz` | 200 | assumption |
| `radio.tx_power_dbm` | 35 | assumption (small cell; TR 37.885 Table 6.1.1-2 has 43 dBm for its macro sites) |
| `radio.bs_gain_db` | 20 | assumption (beam gain, no beam management) |
| `radio.ue_gain_db` | 0 | assumption |
| `radio.noise_figure_db` | 7 | assumption (typical UE noise figure) |
| `radio.isolation` | 0.3 | assumption (mean-to-peak gain of an interfering data beam) |
| `radio.bs_height_m` | 10 | TR 38.901 Table 7.4.1-1 (UMi: 10 m) |
| `radio.ue_height_m` | **1.6** | TR 37.885 clause 6.1.2 (urban option A: 100 % vehicle type 2, antenna height 1.6 m; since 2.1.0, until 2.0.0 1.5 m) |
| `radio.pathloss` | umi_street_canyon | TR 38.901 Table 7.4.1-1 |
| `radio.shadow_los_db` | 4 | TR 38.901 Table 7.4.1-1 (UMi and UMa LOS: 4 dB) |
| `radio.shadow_nlos_db` | 7.82 | TR 38.901 Table 7.4.1-1 (UMi NLOS: 7.82 dB) |
| `radio.shadow_decorr_m` | 10 | TR 38.901 Table 7.5-6 Part-1 (UMi: 10 m LOS, 13 m NLOS; the LOS value is used for both, see the limitations) |
| `radio.shadow_site_corr` | none | unset: uncorrelated between sites, TR 38.901 clause 7.5 step 4 (radio.channel_detail simple: 0.5) |
| `radio.place_share` | 1 | assumption (blockage tied to place) |
| `radio.clutter_los` | true | TR 38.901 clause 7.6.3.3 (spatially consistent LOS state), applied on top of the building geometry |
| `radio.los_corr_m` | 50 | TR 38.901 Table 7.6.3.1-2 (LOS/NLOS state, UMi and UMa: 50 m) |
| `radio.time_var_db` | 1.5 | assumption (moving blockers) |
| `radio.time_var_tau_s` | 1 | assumption |
| `radio.l1_error_db` | 1 | assumption (error of one L1 RSRP sample) |
| `radio.penetration_db` | 0 | off by default; TR 38.901 clause 7.4.3.2: 9 dB in a standard car |
| `radio.penetration_sd_db` | 0 | off by default; TR 38.901 clause 7.4.3.2: 5 dB in a standard car |
| `radio.energy_p0_w` | 56 | EARTH model, micro base station (Auer et al. 2011, Table 2): 56 W |
| `radio.energy_slope` | 2.6 | EARTH model, micro base station (Auer et al. 2011, Table 2): 2.6 |
| `radio.map_res_m` | **2** | numerical setting (coarser map for speed) |
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
| `protocol.reest_s` | 1 | assumption (1 s outage); TS 38.133 6.2.1.2.1 bounds the delay by 50 ms + cell identification (FR1: 200 ms known, 800 ms unknown cell, Table 6.2.1.2.1-1) + system information + PRACH; TR 36.842 Table E.1-2 uses 250 ms |
| `protocol.cho_recovery_s` | 0.4 | TS 38.300 clauses 9.2.3.1 and 9.2.7 (recovery into a CHO candidate; assumption 0.4 s) |
| `protocol.pingpong_s` | 1 | TR 36.839 (minimum time of stay, 1 s) |
| `protocol.cfg_loss_as_failure` | false | check mode only |
| `protocol.lm_load` | none | off by default: link monitoring sees the load of the data channel (calibration option) |
| `protocol.lm_load_per_ue` | 0 | off by default (calibration option) |
| `protocol.exec_can_fail` | true | TR 36.839: the execution fails when the target is below Qout |
| `protocol.rlm_holdoff_s` | 0.2 | 0.2 s since 2.0.0: an interpretation of TS 38.133 8.1.2.2 (evaluation over the last T_Evaluate_out, 200 ms in FR1) on a newly joined cell |
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
| `traffic.ftp_file_bytes` | 500000 | FTP model 3 (TR 36.872 Annex A.1) with 0.5 Mbyte files (TR 38.802 Table A.2.1-1; TR 38.821 Table 6.1.1.1-7) |
| `traffic.ftp_rate_hz` | 0.1 | ftp3 model: assumption (file arrival rate per user) |
| `mobility.users` | **20** | assumption |
| `mobility.profile` | v60 | TR 37.885 clause 6.1.2 (urban option A: 60 km/h in all lanes) and Table A-1 (2 lanes of 3.5 m per direction): profile v60 (since 2.0.0) |
| `mobility.groups` | none | profile |
| `run.duration_s` | **30** | numerical setting (short run) |
| `run.warmup_s` | **5** | numerical setting |

## Known limitations

- Small cells on UMi along the streets, as in urban-grid-10ghz (TR 37.885 itself has 500 m macro sites with UMa in the urban grid); the path loss is evaluated at no less than 10 m from a site.
- Below the minimum area of TR 37.885 Table A-1; users near the edge see fewer neighbours.
- About 10 UE-minutes per seed: rates have a large sampling error; use it for checks, not for results.
- The coarser 2 m radio map smooths the LOS edges a little compared with the 1 m default.
- The LOS state of a link is LOS only if the buildings leave it clear and the spatially consistent LOS variable of TR 38.901 clause 7.6.3.3 is below the LOS probability of Table 7.4.2-1; the share of LOS links is therefore lower than Table 7.4.2-1 gives (which `handoverlab verify` compares only for the links clear of buildings).
- One shadowing decorrelation distance, the UMi LOS value of 10 m, also for the NLOS links (TR 38.901 Table 7.5-6 Part-1: UMi LOS 10 m, NLOS 13 m); LOS and NLOS links share one unit shadowing realisation scaled by the LOS or NLOS standard deviation, so the shadowing keeps its sign when a link changes state (TR 38.901 gives separate LOS and NLOS parameters, Table 7.5-6).
- A vehicle keeps a lane offset drawn at the start, on either side of the street centre line, through turns: it may drive in a lane of the opposite direction (TR 37.885 Table A-1 has 2 lanes in each direction).
- The number of vehicles is set for run time: TR 37.885 clause 6.1.2 places vehicles with a gap of max(2 m, exponential with mean speed x 2 s), which gives hundreds of vehicles in the grid; the interference load of HandoverLab does not depend on the number of users.

## Reference results

- Golden event-log fingerprints of the built-in rules (`handoverlab verify`, check group `fingerprints`).
- Invariant checks in debug mode and the equivalence 'CHO with immediate execution = A3' (`handoverlab verify`).
