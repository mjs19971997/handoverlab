# Scenario card: `dense-urban-2layer`

*Two-layer dense urban deployment of ITU-R M.2412 (4 GHz macro + 30 GHz micro, SSB beams)*  
Available since version 1.10.0. Use it as `scenario: dense-urban-2layer` in a configuration file or `hl.builtin_scenario("dense-urban-2layer")` in Python.

## Purpose

The Dense Urban-eMBB test environment of ITU-R M.2412-0 in its two-layer form (Configuration C): a macro layer at 4 GHz on a hexagonal grid with 200 m between sites and three TRxPs (sectors) per site, and a micro layer at 30 GHz with three micro sites per macro TRxP, each with three TRxPs.  Every TRxP sends 8 SSB beams from a 4 x 8 panel with the element of TR 38.901 Table 7.3-1. Users are the outdoor in-car users of M.2412 (30 km/h).  Measurements follow the periods of TS 38.133 (inter-frequency measurements in gaps), and the rule `a3a5` hands over with Event A3 within a layer and Event A5 between layers.  Use it to study multi-layer mobility, beam failures and inter-frequency handovers.

## Layout

![Layout of dense-urban-2layer](dense-urban-2layer.svg)

Open area of 800 m x 700 m (no wrap-around), 23 macro sites (ISD 200 m) and 207 micro sites (drawn once: 3 per macro TRxP, uniform by area in the TRxP's 120-degree wedge between 25 m and 115.5 m from the macro site, at least 20 m apart; numpy default_rng(2412)).

## Parameters

Values in **bold** differ from the HandoverLab defaults.

| Key | Value | Source |
|---|---|---|
| `layout.kind` | **open_area** | ITU-R M.2412-0 clause 8.3 (no topographical details; regular hexagonal macro grid) |
| `layout.site_spacing_m` | **200** | ITU-R M.2412-0 Table 5b (macro layer ISD 200 m) |
| `layout.sites` | **23 entries** | hexagonal macro grid with ISD 200 m in the area (ITU-R M.2412-0 clause 8.3) |
| `layout.area_m` | **[800, 700]** | assumption (800 m x 700 m, about 23 macro sites) |
| `layout.min_site_distance_m` | **35** | TR 38.901 Table 7.2-1 (UMa: minimum BS-UT distance 35 m; applied to the start and waypoints, macro sites only) |
| `radio.carrier_ghz` | **4** | ITU-R M.2412-0 Table 5b, Configuration C (macro layer 4 GHz) |
| `radio.bandwidth_mhz` | **20** | ITU-R M.2412-0 Table 5b (20 MHz TDD at 4 GHz) |
| `radio.tx_power_dbm` | **44** | ITU-R M.2412-0 Table 5b (macro 4 GHz: 44 dBm for 20 MHz) |
| `radio.ue_gain_db` | 0 | ITU-R M.2412-0 Table 5b (UE antenna element gain 0 dBi at 4 GHz) |
| `radio.noise_figure_db` | 7 | ITU-R M.2412-0 Table 5b (UE noise figure 7 dB at 4 GHz) |
| `radio.bs_height_m` | **25** | ITU-R M.2412-0 Table 5b (25 m for macro sites) |
| `radio.ue_height_m` | 1.5 | ITU-R M.2412-0 Table 5 (outdoor UEs: 1.5 m), within 1.5-22.5 m of TR 38.901 Table 7.4.1-1 |
| `radio.pathloss` | **uma** | TR 38.901 UMa (macro) and UMi street canyon (micro), as ITU-R M.2412-0 Annex 1 Table A1-1 uses for Dense Urban |
| `radio.shadow_los_db` | 4 | TR 38.901 Table 7.4.1-1 (UMa LOS: 4 dB); micro layer UMi LOS: 4 dB |
| `radio.shadow_nlos_db` | **6** | TR 38.901 Table 7.4.1-1 (UMa NLOS: 6 dB); micro layer UMi NLOS: 7.82 dB |
| `radio.shadow_decorr_m` | **50** | TR 38.901 Table 7.5-6 Part-1 (UMa NLOS: 50 m; micro layer UMi NLOS: 13 m) |
| `radio.shadow_site_corr` | none | unset: uncorrelated between sites, TR 38.901 clause 7.5 step 4 (radio.channel_detail simple: 0.5) |
| `radio.place_share` | 1 | assumption (blockage tied to place) |
| `radio.los_corr_m` | 50 | TR 38.901 Table 7.6.3.1-2 (LOS/NLOS state: UMa and UMi 50 m) |
| `radio.time_var_db` | 1.5 | assumption (moving blockers) |
| `radio.time_var_tau_s` | 1 | assumption |
| `radio.l1_error_db` | 1 | assumption (error of one L1 RSRP sample) |
| `radio.penetration_db` | **9** | ITU-R M.2412-0 Annex 1 clause 3.3 and TR 38.901 clause 7.4.3.2 (in-car users: 9 dB) |
| `radio.penetration_sd_db` | **5** | ITU-R M.2412-0 Annex 1 clause 3.3 and TR 38.901 clause 7.4.3.2 (5 dB, per user) |
| `radio.energy_p0_w` | 56 | EARTH model, micro base station (Auer et al. 2011, Table 2): 56 W |
| `radio.energy_slope` | 2.6 | EARTH model, micro base station (Auer et al. 2011, Table 2): 2.6 |
| `radio.map_res_m` | 1 | numerical setting |
| `radio.scs_khz` | **30** | assumption (30 kHz at 4 GHz) |
| `radio.beams.sectors` | 3 | default of the beam model (user guide) |
| `radio.beams.sector_az0_deg` | 30 | default of the beam model (user guide) |
| `radio.beams.n_ssb` | 8 | default of the beam model (user guide) |
| `radio.beams.panel` | [4, 8] | default of the beam model (user guide) |
| `radio.beams.tilt_deg` | **102** | M.2412 clause 8.3.2 (three TRxPs per macro site); element of TR 38.901 Table 7.3-1 (8 dBi, M.2412 BS element gain 8 dBi); panel size, 8 SSB beams (L_max at 4 GHz) and tilt are assumptions |
| `radio.beams.beam_span_deg` | none | default of the beam model (user guide) |
| `radio.beams.ssb_avg` | none | default of the beam model (user guide) |
| `radio.beams.ssb_thresh_dbm` | none | default of the beam model (user guide) |
| `radio.beams.report_s` | 0.04 | default of the beam model (user guide) |
| `radio.beams.switch_db` | 2 | default of the beam model (user guide) |
| `radio.beams.tci_delay_s` | 0.01 | default of the beam model (user guide) |
| `radio.beams.rx_sweep_n` | none | default of the beam model (user guide) |
| `radio.beams.bfd` | true | default of the beam model (user guide) |
| `radio.beams.bfi_max` | 3 | default of the beam model (user guide) |
| `radio.beams.bfd_timer` | 4 | default of the beam model (user guide) |
| `radio.beams.bfr_timer_s` | 0.1 | default of the beam model (user guide) |
| `radio.beams.rsrp_thresh_ssb_dbm` | -115 | default of the beam model (user guide) |
| `radio.beams.ra_attempt_s` | 0.01 | default of the beam model (user guide) |
| `radio.beams.preamble_max` | 10 | default of the beam model (user guide) |
| `radio.beams.rlm_rs` | tci | default of the beam model (user guide) |
| `radio.layers` | **1 entries** | M.2412 clause 8.3.2 and Table 5b: micro layer at 30 GHz, 80 MHz, 33 dBm, 10 m, UE noise figure 10 dB, UE element gain 5 dBi; 3 micro sites per macro TRxP (placement method and three TRxPs per micro site: assumptions, as M.2412 leaves them to the proponent) |
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
| `protocol.meas_periods` | **ts38133** | TS 38.133 Tables 9.2.5.2-1/-2 and 9.3.5-1/-2 (gap pattern 0 of Table 9.1.2-1) |
| `protocol.rlm_eval` | **ts38133** | TS 38.133 Tables 8.1.2.2-1/-2 |
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
| `mobility.users` | **20** | assumption (20 users for run time; ITU-R M.2412-0 Table 5b: 10 UEs per TRxP) |
| `mobility.profile` | **v30** | ITU-R M.2412-0 Table 5b: fixed and identical speed of the outdoor (in-car) users, 30 km/h = 8.333 m/s (since 2.1.0; until 2.0.0 8.33 m/s); the 80 % indoor users are not simulated |
| `mobility.groups` | none | profile |
| `run.duration_s` | 120 | numerical setting |
| `run.warmup_s` | 20 | numerical setting |

Not read by this layout and radio model, so not listed: `layout.blocks`, `layout.pitch_m`, `layout.site_offset_m`, `layout.street_width_m`, `radio.bs_gain_db`, `radio.clutter_los`, `radio.isolation`.

## Known limitations

- No wrap-around: users near the edge of the area see fewer interferers than in M.2412.
- No fast fading and no UE beamforming; one hypothetical beam per SSB with fixed DFT weights.
- Only the outdoor in-car users of M.2412 are simulated (the 80 % indoor users and building penetration are not).
- The micro-site positions are one draw; other draws give other statistics.
- One shadowing decorrelation distance per layer, that of the NLOS links (TR 38.901 Table 7.5-6 Part-1: UMa LOS 37 m, UMi LOS 10 m).
- The minimum distance of 35 m holds for the macro sites; the 10 m of UMi (TR 38.901 Table 7.2-1) to the micro sites is not enforced.
- 20 users for 69 macro TRxPs instead of the 10 UEs per TRxP of ITU-R M.2412-0 Table 5b; the number is set for run time (the interference load of HandoverLab does not depend on it). Users move between random waypoints, which are denser in the middle of the area, while M.2412-0 drops them uniformly with a uniformly distributed direction.
- LOS and NLOS links share one unit shadowing realisation per layer, scaled by the LOS or NLOS standard deviation (TR 38.901 gives separate LOS and NLOS parameters, Table 7.5-6).
- Changed in 1.11.0: until 1.10.0 the macro layer had the UMi shadowing (7.82 dB NLOS, 10 m) and the in-car users no car penetration loss.

## Reference results

- ITU-R M.2412-0 (2017) clause 8.3.2 and Table 5b (local copy std3gpp/pdf/R-REP-M.2412-2017-PDF-E.pdf).
