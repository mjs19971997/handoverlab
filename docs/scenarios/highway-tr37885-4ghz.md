# Scenario card: `highway-tr37885-4ghz`

*The TR 37.885 highway below 6 GHz (baseline layout, 4 GHz)*  
Available since version 1.11.0. Use it as `scenario: highway-tr37885-4ghz` in a configuration file or `hl.builtin_scenario("highway-tr37885-4ghz")` in Python.

## Purpose

The highway case of the 3GPP NR V2X evaluation (TR 37.885) as specified below 6 GHz, for the base-station-to-vehicle link: a road of 3 + 3 lanes of 4 m, macro sites along the road 35 m away with an inter-site distance of 1732 m (the baseline of TR 36.885 clause A.1.3, which TR 37.885 uses), wrap-around, the RMa LOS path loss at 4 GHz, and every vehicle at 140 km/h.  Cells are long and the link is always LOS, so handovers are rare, regular and happen at high speed.  Use it for results that should follow the 3GPP highway assumptions as closely as this simulator can.

## Layout

![Layout of highway-tr37885-4ghz](highway-tr37885-4ghz.svg)

A road of 3464 m along the x axis (24 m wide), two sites 1732 m apart, both 35 m beyond the northern road edge; the road wraps around after two sites (TR 36.885 Figure A.1.3-2).

## Parameters

Values in **bold** differ from the HandoverLab defaults.

| Key | Value | Source |
|---|---|---|
| `layout.kind` | **highway** | TR 37.885 Annex A, Table A-1 (highway: 3 lanes in each direction, 4 m lane width) |
| `layout.site_spacing_m` | **1732** | TR 37.885 Table 6.1.3-1 (below 6 GHz, inter macro: 1732 m baseline) |
| `layout.site_offset_m` | **35** | TR 36.885 clause A.1.3, option 1 (baseline): eNBs located along the freeway 35 m away; read as 35 m from the road edge |
| `layout.sites` | none | regular placement along the streets |
| `layout.lanes` | 3 | TR 37.885 Table A-1 (highway: 3 lanes per direction) |
| `layout.lane_width_m` | 4 | TR 37.885 Table A-1 (highway: 4 m lanes) |
| `layout.road_length_m` | **3464** | TR 37.885 Table A-1 (highway length >= 2000 m with wrap-around); two sites per wrap-around period as drawn in TR 36.885 Figure A.1.3-2 |
| `layout.sites_file` | none | none (sites from the layout) |
| `layout.wrap` | **true** | TR 37.885 Table A-1 (wrap around should be applied) |
| `layout.highway_sites` | **one_side** | TR 36.885 Figure A.1.3-2 (all sites on one side of the road) |
| `radio.carrier_ghz` | **4** | TR 37.885 Table 6.1.1-1 (highway, macro to/from vehicle: 2 GHz or 4 GHz) |
| `radio.bandwidth_mhz` | **20** | TR 37.885 Table 6.1.1-1 (simulation bandwidth 20 or 40 MHz, DL+UL) |
| `radio.tx_power_dbm` | **49** | TR 37.885 Table 6.1.1-1 (macro BS: 49 dBm; the system bandwidth is taken equal to the simulation bandwidth, so the PA power is not scaled down) |
| `radio.bs_gain_db` | **26.1** | assumption: one polarisation of the 8 x 8 array of TR 37.885 Table 6.1.4-3 (4 GHz) with 8 dBi elements (Table 6.1.4-2): 8 + 10 log10(64) dB |
| `radio.ue_gain_db` | **6** | assumption: vehicle type 2, option 1, rooftop baseline (1, 2, 2, 1, 1) of TR 37.885 Table 6.1.4-9 with 3 dBi elements (Table 6.1.4-8): 3 + 10 log10(2) dB |
| `radio.noise_figure_db` | **9** | TR 37.885 Table 6.1.1-1 (UE receiver noise figure 9 dB) |
| `radio.isolation` | 0.3 | assumption (mean-to-peak gain of an interfering data beam) |
| `radio.bs_height_m` | **35** | TR 37.885 Table 6.1.4-1 (highway: 35 m for ISD 1732 m) |
| `radio.ue_height_m` | **1.6** | TR 37.885 clause 6.1.2 (vehicle type 2: antenna height 1.6 m) |
| `radio.pathloss` | **rma** | TR 37.885 Table 6.2.1-2 (highway, below 6 GHz, V2B/B2V: TR 38.901 RMa LOS) |
| `radio.shadow_los_db` | 4 | TR 37.885 clause 6.2.2 (shadowing of the TR 38.901 model used) and TR 38.901 Table 7.4.1-1 (RMa LOS: 4 dB below the breakpoint) |
| `radio.shadow_los_far_db` | **6** | TR 38.901 Table 7.4.1-1 (RMa LOS beyond the breakpoint: 6 dB) |
| `radio.shadow_decorr_m` | **37** | TR 38.901 Table 7.5-6 Part-2 (RMa LOS: 37 m) |
| `radio.shadow_site_corr` | none | unset: uncorrelated between sites, TR 38.901 clause 7.5 step 4 (radio.channel_detail simple: 0.5) |
| `radio.place_share` | 1 | assumption (blockage tied to place) |
| `radio.los_model` | **los** | TR 37.885 clause 6.2.1 (LOS propagation type is used for V2B and B2R links in the highway scenario) |
| `radio.breakpoint_c_mps` | 3e+08 | TR 38.901 Table 7.4.1-1 notes 1 and 5 (c = 3.0e8 m/s in the breakpoint distances) |
| `radio.pl_min_distance_m` | 10 | TR 38.901 Table 7.4.1-1 (applicability range of RMa, UMa, UMi: 10 m <= d2D) |
| `radio.time_var_db` | **0** | set to 0: TR 37.885 has no blockage of the B2V link in the highway (LOS only) |
| `radio.time_var_tau_s` | 1 | assumption |
| `radio.l1_error_db` | 1 | assumption (error of one L1 RSRP sample) |
| `radio.penetration_db` | 0 | off by default; TR 38.901 clause 7.4.3.2: 9 dB in a standard car |
| `radio.penetration_sd_db` | 0 | off by default; TR 38.901 clause 7.4.3.2: 5 dB in a standard car |
| `radio.energy_p0_w` | 56 | EARTH model, micro base station (Auer et al. 2011, Table 2): 56 W |
| `radio.energy_slope` | 2.6 | EARTH model, micro base station (Auer et al. 2011, Table 2): 2.6 |
| `radio.energy_ntrx` | 2 | EARTH model, micro base station (Auer et al. 2011, Eq. 1 and Table 2): 2 transceivers |
| `radio.fast_fading` | none | off by default; TR 38.901 clause 7.7.2 (TDL-A .. TDL-E) |
| `radio.delay_spread_ns` | 100 | TR 38.901 Table 7.7.3-1 (nominal delay spread; used with fast_fading) |
| `radio.fading_k_db` | none | TR 38.901 clause 7.7.6 (unset: the K-factor of the table) |
| `radio.map_res_m` | **4** | numerical setting (coarser map for the long road) |
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
| `protocol.scheduler` | none | off by default (rate model); rr / pf slot scheduler with TS 38.214 MCS and TBS |
| `protocol.harq_max_tx` | 4 | assumption (transmissions per TB; the network's choice) |
| `protocol.harq_rtt_slots` | 8 | assumption (HARQ round trip in slots) |
| `protocol.l2s_loss_db` | 1 | assumption (implementation loss of the block-error model) |
| `protocol.buffers` | none | off by default; am / um: PDCP / RLC buffers and data forwarding at handover (TS 38.300 9.2.3.2.2, 9.2.3.2.3) |
| `protocol.forwarding` | true | TS 38.300 9.2.3.2.3 (the network may forward; with buffers) |
| `protocol.early_forwarding` | false | TS 38.300 9.2.3.4.4 / 9.2.3.5.2 (CHO and LTM: late forwarding unless set) |
| `protocol.xn_delay_s` | 0.005 | assumption (Xn forwarding delay; with buffers) |
| `protocol.discard_timer_s` | none | TS 38.331 PDCP-Config discardTimer (unset: infinity; with buffers) |
| `protocol.sdu_bytes` | none | assumption (SDU size for the SDU counts; unset: packet_bytes or 1500 bytes) |
| `protocol.rrc_detail` | 3gpp |  |
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
| `mobility.users` | **251** | TR 37.885 clause 6.1.2: gap max(2 m, exponential with mean speed x 2 s) behind a 5 m vehicle, about 82.8 m per vehicle at 140 km/h, so 3464 m / 82.8 m x 6 lanes = 251 |
| `mobility.profile` | **v140c** | TR 37.885 clause 6.1.2, highway option A (all vehicles type 2, 140 km/h baseline), on the lane centre (since 2.1.0; until 2.0.0 profile v140 with a lateral offset of up to 0.5 m, which TR 37.885 does not specify) |
| `mobility.groups` | none | profile |
| `run.duration_s` | 120 | numerical setting |
| `run.warmup_s` | 20 | numerical setting |
| `run.backend` | numpy |  |
| `ntn.altitude_km` | 600 |  |
| `ntn.aperture_m` | 2 |  |
| `ntn.eirp_dbw_per_mhz` | 34 |  |
| `ntn.n_beams` | 19 |  |
| `ntn.centre_elevation_deg` | 30 |  |
| `ntn.environment` | rural |  |
| `ntn.atm_zenith_db` | 0.045 |  |
| `ntn.scintillation_db` | 2.2 |  |
| `ntn.sf_corr_m` | 37 |  |
| `ntn.los_corr_m` | 60 |  |
| `ntn.hpbw_deg` | none | unset: the tabled 3 dB beamwidth of TR 38.821 Tables 6.1.1.1-1/-2 (Table 6.1.1.1-4: only the 3 dB beamwidth is used) |
| `ntn.los_model` | probability | probability: the LOS probability of TR 38.811 Table 6.6.1-1 |

Not read by this layout and radio model, so not listed: `layout.blocks`, `layout.pitch_m`, `layout.street_width_m`, `radio.clutter_los`, `radio.los_corr_m`, `radio.shadow_nlos_db`.

## Known limitations

- Vehicles are placed independently and uniformly along their lane (a Poisson process), without the minimum gap of 2 m; their number is fixed at the mean, not drawn.
- One antenna gain per link (the antenna abstraction), no sectors and no beam pattern: TR 37.885 leaves the TXRU mapping to the proponents.
- The place-tied shadowing field is the same for all users at a place (TR 38.901 spatial consistency, exponential autocorrelation of Eq. 7.4-5) and uncorrelated between sites: TR 37.885 clause 6.2.2 takes the shadowing of the TR 38.901 path-loss model for B2V links, and TR 38.901 clause 7.5 step 4 has uncorrelated LSPs for different BS-UT links (since 2.1.0; until 2.0.0 half correlated, a value of the TR 36.885 model).
- Received-power level only: no fast fading, no Doppler, no sidelink.
- The failure model is not calibrated in absolute terms; read failure rates relative to each other.

## Reference results

- Values checked against the texts of TR 37.885 V15.3.0, TR 36.885 V14.0.0 and TR 38.901 V19.5.0 (unchanged from V17.0.0); geometry, wrap-around and the coupling loss of the link are checked by handoverlab verify (group highway).
