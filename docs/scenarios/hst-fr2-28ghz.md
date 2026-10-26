# Scenario card: `hst-fr2-28ghz`

*High-speed train in FR2 (TR 38.854 Scenario-A, unidirectional RRHs, 28 GHz, 350 km/h)*  
Available since version 2.3.0. Use it as `scenario: hst-fr2-28ghz` in a configuration file or `hl.builtin_scenario("hst-fr2-28ghz")` in Python.

## Purpose

The FR2 high-speed train deployment of TR 38.854 as its system-level mobility study uses it (Table 6.3.8.1-1): one train with one roof-mounted CPE at 350 km/h on a straight track, remote radio heads (RRHs) every 700 m on one side of the track, 10 m from it (Scenario-A), each RRH with one panel and one SSB beam pointing along the track towards the next RRH, every RRH its own cell (L3 handover, no DPS / SFN), TR 38.901 RMa with line of sight only at 28 GHz, and no inter-cell interference.  The card's RRHs point west (towards -x); a train going east then travels towards the serving beams ("opposite direction" of the TR), a train going west away from them ("same direction").  Point the RRHs east with `radio.beams.sector_az0_deg: 359.18` to swap the two.  The TR's handover settings are event A3 with 3 dB offset and 80 ms time-to-trigger (`{rule: a3, off_db: 3.0, ttt_s: 0.08}`).

## Layout

![Layout of hst-fr2-28ghz](hst-fr2-28ghz.svg)

A track of 8400 m along the x axis with wrap-around, twelve RRH sites 700 m apart on its northern side, 10 m from it; the two directions of travel share the track.

## Parameters

Values in **bold** differ from the HandoverLab defaults.

| Key | Value | Source |
|---|---|---|
| `layout.kind` | **highway** | TR 38.854 clause 5.1 (one train on one straight railway track, no curvature; RRHs on one side of the track) |
| `layout.site_spacing_m` | **700** | TR 38.854 Table 5.1-1 and Table 5.2-1, Scenario 2 / Scenario-A (Ds 700 m); Table 6.3.8.1-1 (ISD 700 m) |
| `layout.site_offset_m` | **9.98** | TR 38.854 Table 5.2-1 and Table 6.3.8.1-1 (Dmin 10 m, Scenario-A): 9.98 m beyond the 0.02 m track edge |
| `layout.sites` | none | regular placement along the streets |
| `layout.lanes` | **1** | TR 38.854 clause 5.1 (one track); the highway layout has one lane per direction, both on the track |
| `layout.lane_width_m` | **0.02** | numerical setting: the two directions of travel lie within 1 cm of the track |
| `layout.road_length_m` | **8400** | TR 38.854 Table 6.3.8.1-1 (12 sites, Ds 700 m) with wrap-around |
| `layout.sites_file` | none | none (sites from the layout) |
| `layout.wrap` | **true** | assumption (a long line without end effects; the TR simulates 12 sites) |
| `layout.highway_sites` | **one_side** | TR 38.854 clause 5.1 (RRHs located on one side of the track) |
| `radio.carrier_ghz` | **28** | TR 38.854 Table 6.3.8.1-1 (28 GHz) |
| `radio.bandwidth_mhz` | **50** | TR 38.854 Table 6.3.8.1-1 (50 MHz) |
| `radio.tx_power_dbm` | **31** | TR 38.854 Table 6.3.8.1-1 (RRH TX output power 31 dBm) |
| `radio.ue_gain_db` | **17.04** | TR 38.854 clauses 6.1.3 and 6.1.4: CPE panel 4 x 4 elements of 5 dBi, one polarisation: 5 + 10 log10(16) dB, the peak of its one beam (Table 6.3.8.1-1: the CPE panel points to the RRHs) |
| `radio.noise_figure_db` | **10** | TR 38.854 Table 6.3.3.2.1-1 (UE noise figure 10 dB) |
| `radio.bs_height_m` | **15** | TR 38.854 clause 5.1 and Table 6.3.8.1-1 (RRH height 15 m) |
| `radio.ue_height_m` | **5** | TR 38.854 clause 5.1 and Table 6.3.8.1-1 (CPE height 5 m) |
| `radio.pathloss` | **rma** | TR 38.854 clause 6.2.1 and Table 6.3.8.1-1 (TR 38.901 RMa LOS) |
| `radio.shadow_los_db` | 4 | TR 38.901 Table 7.4.1-1 (RMa LOS: 4 dB below the breakpoint); TR 38.854 says nothing about shadowing |
| `radio.shadow_los_far_db` | **6** | TR 38.901 Table 7.4.1-1 (RMa LOS beyond the breakpoint: 6 dB; not reached here, the breakpoint is about 44 km) |
| `radio.shadow_decorr_m` | **37** | TR 38.901 Table 7.5-6 Part-2 (RMa LOS: 37 m) |
| `radio.shadow_site_corr` | none | unset: uncorrelated between sites, TR 38.901 clause 7.5 step 4 (radio.channel_detail simple: 0.5) |
| `radio.place_share` | 1 | assumption (blockage tied to place) |
| `radio.los_model` | **los** | TR 38.854 Table 6.3.8.1-1 (RMa with LOS only) |
| `radio.breakpoint_c_mps` | 3e+08 | TR 38.901 Table 7.4.1-1 notes 1 and 5 (c = 3.0e8 m/s in the breakpoint distances) |
| `radio.pl_min_distance_m` | 10 | TR 38.901 Table 7.4.1-1 (applicability range of RMa, UMa, UMi: 10 m <= d2D) |
| `radio.time_var_db` | **0** | set to 0: line of sight only, no blockers |
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
| `radio.map_res_m` | **4** | numerical setting (coarser map for the long track) |
| `radio.scs_khz` | **120** | TR 38.854 clause 6.3 and Table 6.3.8.1-1 (120 kHz) |
| `radio.beams.sectors` | **1** | TR 38.854 Table 5.2-1 (one RRH panel per RRH site, unidirectional) |
| `radio.beams.sector_az0_deg` | **180.82** | TR 38.854 Table 5.2-1 option 1 and Table 6.3.8.1-1 (panel pointing at the track where the next site is): 180 + atan(10 / 700) deg, west |
| `radio.beams.n_ssb` | **1** | TR 38.854 Table 5.2-1 (Scenario 2: 1 beam per RRH panel) and Table 6.3.8.1-1 (1 SSB beam into the boresight) |
| `radio.beams.panel` | **[8, 8]** | TR 38.854 clause 6.1.1 and Table 6.3.8.1-1 ([Mg, Ng, M, N, P] = [1, 1, 8, 8, 2]); one polarisation |
| `radio.beams.tilt_deg` | **90.82** | TR 38.854 Table 6.3.8.1-1 (pointing at the track at the next site): 90 + atan((15 - 5) / 700) deg |
| `radio.beams.beam_span_deg` | none | default of the beam model (user guide) |
| `radio.beams.ssb_avg` | none | default of the beam model (user guide) |
| `radio.beams.ssb_thresh_dbm` | none | default of the beam model (user guide) |
| `radio.beams.report_s` | 0.04 | default of the beam model (user guide) |
| `radio.beams.switch_db` | 2 | default of the beam model (user guide) |
| `radio.beams.tci_delay_s` | 0.01 | default of the beam model (user guide) |
| `radio.beams.rx_sweep_n` | **8** | TR 38.854 Table 6.3.8.1-1 (scaling factor N = 8, legacy requirements) |
| `radio.beams.bfd` | true | default of the beam model (user guide) |
| `radio.beams.bfi_max` | 3 | default of the beam model (user guide) |
| `radio.beams.bfd_timer` | 4 | default of the beam model (user guide) |
| `radio.beams.bfr_timer_s` | 0.1 | default of the beam model (user guide) |
| `radio.beams.rsrp_thresh_ssb_dbm` | -115 | default of the beam model (user guide) |
| `radio.beams.ra_attempt_s` | 0.01 | default of the beam model (user guide) |
| `radio.beams.preamble_max` | 10 | default of the beam model (user guide) |
| `radio.beams.rlm_rs` | tci | default of the beam model (user guide) |
| `protocol.step_s` | 0.01 | numerical setting |
| `protocol.l1_period_s` | 0.04 | assumption (L1 sample period) |
| `protocol.l3_k` | 4 | TS 38.331 clause 5.5.3.2 |
| `protocol.label_period_s` | 0.2 | numerical setting |
| `protocol.report_interval_s` | 0.12 | TS 38.331 reportInterval (ms120) |
| `protocol.qout_db` | -8 | TR 36.839 (Qout -8 dB) |
| `protocol.qin_db` | -6 | TR 36.839 (Qin -6 dB) |
| `protocol.qout_window_s` | **0.6** | TR 38.854 Table 6.3.8.1-1 (T_Evaluate_out_CSI-RS 600 ms without DRX) |
| `protocol.qin_window_s` | **0.3** | TR 38.854 Table 6.3.8.1-1 (T_Evaluate_in_CSI-RS 300 ms without DRX) |
| `protocol.n310` | **2** | TR 38.854 Table 6.3.8.1-1 (N310: 2 samples) |
| `protocol.n311` | **2** | TR 38.854 Table 6.3.8.1-1 (N311: 2 samples) |
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
| `protocol.meas_periods` | **ts38133** | TS 38.133 measurement periods: 480 ms intra-frequency in FR2 with N = 8 at power class 3, the value of TR 38.854 Table 6.3.8.1-1 (DRX disabled) |
| `protocol.rrc_detail` | 3gpp |  |
| `protocol.ns3_oos_rx` | none | off by default (3GPP model); imitates ns-3 / 5G-LENA v5.1 (NrUePhy NumQoutEvalSf: 200 control receptions), not 3GPP |
| `protocol.ns3_ins_rx` | 100 | ns-3 / 5G-LENA v5.1 (NrUePhy NumQinEvalSf: 100 control receptions); with ns3_oos_rx only |
| `protocol.ns3_ctrl_hz` | 206 | measured in ns-3 / 5G-LENA runs at light traffic (control receptions per second of a user, base); with ns3_oos_rx only |
| `protocol.ns3_ctrl_per_ue_hz` | 16.5 | measured in ns-3 / 5G-LENA runs at light traffic (control receptions per second per user served by the cell); with ns3_oos_rx only |
| `protocol.rlm_interference` | static | static by default (the load of the data channel, or lm_load); 'dynamic': every neighbour's activity of the step on the RLM-RS (bursty FTP traffic gives time-varying interference, TR 36.814 A.2.1.3; RLM quality over the RLM-RS REs, TS 38.133 A.6.5.1.1 NOTE 3) |
| `protocol.rlm_rs_type` | ssb | SSB (TS 38.133 8.1.1: SSB or CSI-RS); with rlm_interference dynamic only |
| `protocol.rlm_ssb_overlap` | 1 | assumption: 1, a synchronous network with the same SSB positions in every cell (3GPP does not say whether neighbour SSBs meet); with rlm_interference dynamic only |
| `protocol.rlm_bg_se` | 2 | assumption: 2 bit/s/Hz while a cell sends a background file (sets the burst length); with rlm_interference dynamic only |
| `traffic.services` | 5 entries | TS 23.501 Table 5.7.4-1 (5QI); thresholds are assumptions |
| `traffic.se_max` | 7.4 | assumption (spectral-efficiency cap) |
| `traffic.hotspot_share` | 0.25 | assumption |
| `traffic.hotspot_load` | **[0, 0]** | TR 38.854 Table 6.3.8.1-1 (only one train with one CPE: no inter-cell interference) |
| `traffic.normal_load` | **[0, 0]** | TR 38.854 Table 6.3.8.1-1 (only one train with one CPE: no inter-cell interference) |
| `traffic.load_tau_s` | 0.2 | assumption |
| `traffic.rate_scale` | 1 | assumption |
| `traffic.label_load` | 1 | assumption (all cells transmit for the label) |
| `traffic.model` | **full_buffer** | TR 38.854 Table 6.3.8.1-1 (DL full buffer) |
| `traffic.period_s` | 0.02 | periodic model: 20 ms, as VoIP |
| `traffic.packet_bytes` | 100 | periodic model: assumption |
| `traffic.ftp_file_bytes` | 500000 | FTP model 3 (TR 36.872 Annex A.1) with 0.5 Mbyte files (TR 38.802 Table A.2.1-1; TR 38.821 Table 6.1.1.1-7) |
| `traffic.ftp_rate_hz` | 0.1 | ftp3 model: assumption (file arrival rate per user) |
| `mobility.users` | **1** | TR 38.854 clause 5.3.3 and Table 6.3.8.1-1 (one CPE per train, one train) |
| `mobility.profile` | v60 | TR 37.885 clause 6.1.2 (urban option A: 60 km/h in all lanes) and Table A-1 (2 lanes of 3.5 m per direction): profile v60 (since 2.0.0) |
| `mobility.groups` | **1 entries** | TR 38.854 clause 6.3.4.1 and Table 6.3.8.1-1 (350 km/h); the direction is drawn per seed |
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

Not read by this layout and radio model, so not listed: `layout.blocks`, `layout.pitch_m`, `layout.street_width_m`, `radio.bs_gain_db`, `radio.clutter_los`, `radio.isolation`, `radio.los_corr_m`, `radio.shadow_nlos_db`.

## Known limitations

- One CPE per run: run many seeds (the TR uses 20 drops of 100 s).  The direction of travel is drawn per seed; mirror the RRHs (`radio.beams.sector_az0_deg: 359.18`) on the same seeds to get both directions on the same trajectories.
- The CPE gain is one number for every RRH (no CPE pattern, no second panel, no receive beams): the RRHs behind the CPE get the same gain as those in front.  Near an RRH this overstates the received power.
- The RRH element has the back lobe of TR 38.901 Table 7.3-1 (A_m 30 dB, as TR 38.854 Table 6.1.1.1); the system-level study of TR 38.854 clause 6.3.4.1 used an antenna model without back lobe.  `radio.beams.am_db` raises A_m.
- No DRX (TR 38.854 also studies DRX 40-160 ms); no DPS, SFN or multi-TRP transmission; no Doppler, no fast fading (TR 38.854 clause 6.2.2: one tap per link); no uplink and no timing advance.
- Radio-link monitoring uses the SSB-based link quality with the CSI-RS evaluation periods of Table 6.3.8.1-1 as filter time constants; cell detection delay (600 ms) is not modelled.
- Scenario-B (Dmin 150 m, 2 beams per RRH) is not a card of its own; set `layout.site_offset_m: 149.98` and the beams accordingly.
- The absolute failure level is not calibrated. It was checked against ns-3 only on `ns3-urban-3.5ghz`: with equal run lengths the ns-3 comparison setting gives 0.5-1.3 times ns-3's failure level, depending on the set, and passes the pre-registered checks on 1 of 4 fresh sets (V4; corrected in 2.6.0, docs/calibration.md); read failure rates relative to each other.

## Reference results

- Values checked against the text of TR 38.854 V18.0.0 (Table 5.1-1, Table 5.2-1, clauses 6.1, 6.2.1, Table 6.3.3.2.1-1, Table 6.3.8.1-1) and TR 38.901 V19.5.0.  Behaviour compared with the system-level results of TR 38.854 clause 6.3.4.1 in docs/guides/high-speed-train.md.
