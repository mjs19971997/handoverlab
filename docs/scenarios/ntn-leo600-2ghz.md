# Scenario card: `ntn-leo600-2ghz`

*A LEO satellite at 600 km with 19 earth-moving beams in the S band (NTN)*  
Available since version 2.0.0. Use it as `scenario: ntn-leo600-2ghz` in a configuration file or `hl.builtin_scenario("ntn-leo600-2ghz")` in Python.

## Purpose

The LEO scenario of the 3GPP NTN study (TR 38.821) that RAN2 prioritised for mobility: one satellite at 600 km altitude, transparent payload, 19 beams fixed in the satellite frame (they sweep over the ground with the satellite at 7.56 km/s), Set-1 satellite parameters in the S band (2 GHz, 30 MHz), frequency reuse 1, handheld users at 3 km/h in a rural area, and the large-scale channel of TR 38.811.  The handovers come from the satellite's motion, not the users': every user crosses a beam within seconds.  Use it for NTN mobility, e.g. conditional handover with the location condition D2 of Release 18 (rule `cho_d2`).

## Layout

![Layout of ntn-leo600-2ghz](ntn-leo600-2ghz.svg)

The users' area of 60 km x 60 km around the point at which the central beam points with 30 degrees elevation at the middle of the run, and the beam centres on the ground at that time (the drawing leaves out the three below 10 degrees elevation, far to the east).  The satellite passes west of the area, moving north.

## Parameters

Values in **bold** differ from the HandoverLab defaults.

| Key | Value | Source |
|---|---|---|
| `layout.kind` | **ntn** | TR 38.821 Table 4.2-2 and Table 7.1-1 (scenario C2: LEO 600 km, transparent payload, beams moving with the satellite); TR 38.821 clause 7.3.2.4 (RAN2 prioritises LEO with moving beams for mobility) |
| `layout.blocks` | [3, 3] | TR 37.885 Table A-1 (minimum 3 x 3 blocks) |
| `layout.pitch_m` | [433, 250] | TR 37.885 Annex A (433 m x 250 m) |
| `layout.street_width_m` | 20 | TR 37.885 Annex A (20 m) |
| `layout.site_spacing_m` | 100 | assumption (dense small cells along the streets; TR 37.885 Table 6.1.3-2 has 500 m macro sites in the urban grid) |
| `layout.site_offset_m` | 9 | assumption (sites on the pavement) |
| `layout.sites` | none | regular placement along the streets |
| `layout.area_m` | **[60000, 60000]** | assumption (the users stay under the 19 beams for the length of the run) |
| `radio.carrier_ghz` | **2** | TR 38.821 Table 6.1.1.1-5 (S band, 2 GHz) |
| `radio.bandwidth_mhz` | **30** | TR 38.821 Table 6.1.1.1-5 (S band: 30 MHz per beam, frequency reuse 1) |
| `radio.tx_power_dbm` | 35 | assumption (small cell; TR 37.885 Table 6.1.1-2 has 43 dBm for its macro sites) |
| `radio.bs_gain_db` | 20 | assumption (beam gain, no beam management) |
| `radio.ue_gain_db` | 0 | TR 38.821 Table 6.1.1.1-3 (handheld UE: 0 dBi per element) |
| `radio.noise_figure_db` | 7 | TR 38.821 Table 6.1.1.1-3 (handheld UE: noise figure 7 dB, antenna temperature 290 K) |
| `radio.isolation` | **1** | TR 38.821 Table 6.1.1.1-5 (frequency reuse factor 1: every beam interferes with its full power and load) |
| `radio.bs_height_m` | 10 | TR 38.901 Table 7.4.1-1 (UMi: 10 m) |
| `radio.ue_height_m` | 1.5 | ITU-R M.2412-0 Table 5 (outdoor UEs: 1.5 m), within 1.5-22.5 m of TR 38.901 Table 7.4.1-1 |
| `radio.pathloss` | umi_street_canyon | TR 38.901 Table 7.4.1-1 |
| `radio.shadow_los_db` | 4 | TR 38.901 Table 7.4.1-1 (UMi and UMa LOS: 4 dB) |
| `radio.shadow_nlos_db` | 7.82 | TR 38.901 Table 7.4.1-1 (UMi NLOS: 7.82 dB) |
| `radio.shadow_decorr_m` | 10 | TR 38.901 Table 7.5-6 (UMi: 10 m LOS, 13 m NLOS) |
| `radio.shadow_site_corr` | 0.5 | assumption (correlation between sites) |
| `radio.place_share` | 1 | assumption (blockage tied to place) |
| `radio.clutter_los` | true | TR 38.901 clause 7.6.3.3 (spatially consistent LOS state) |
| `radio.los_corr_m` | 50 | TR 38.901 Table 7.6.3.1-2 (LOS/NLOS state, UMi and UMa: 50 m) |
| `radio.time_var_db` | **0** | set to 0: the large-scale model of TR 38.811 has no further time-varying component |
| `radio.time_var_tau_s` | 1 | assumption |
| `radio.l1_error_db` | 1 | assumption (error of one L1 RSRP sample) |
| `radio.penetration_db` | 0 | off by default; TR 38.901 clause 7.4.3.2: 9 dB in a standard car |
| `radio.penetration_sd_db` | 0 | off by default; TR 38.901 clause 7.4.3.2: 5 dB in a standard car |
| `radio.energy_p0_w` | 56 | EARTH model, micro base station (Auer et al. 2011): 56 W |
| `radio.energy_slope` | 2.6 | EARTH model, micro base station (Auer et al. 2011): 2.6 |
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
| `protocol.prep_s` | **0.07577** | TR 36.839 (50 ms) plus the maximum round-trip delay of scenario C2 (TR 38.821 Table 7.1-1: 25.77 ms) |
| `protocol.exec_s` | **0.06577** | TR 36.839 (40 ms) plus the maximum round-trip delay of scenario C2 for the random access (assumption: one round trip) |
| `protocol.reest_s` | 1 | TR 36.842 (assumption: 1 s outage) |
| `protocol.cho_recovery_s` | 0.4 | TS 38.300 clause 9.2.3.4 (recovery into a prepared cell; assumption 0.4 s) |
| `protocol.pingpong_s` | 1 | TR 36.839 (minimum time of stay, 1 s) |
| `protocol.cfg_loss_as_failure` | false | check mode only |
| `protocol.lm_load` | none | off by default: link monitoring sees the load of the data channel (calibration option) |
| `protocol.lm_load_per_ue` | 0 | off by default (calibration option) |
| `protocol.exec_can_fail` | true | TR 36.839: the execution fails when the target is below Qout |
| `protocol.rlm_holdoff_s` | 0.2 | off by default; TS 38.133 clause 8.1: out-of-sync evaluation of 0.2 s on a new cell |
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
| `mobility.profile` | **ped3** | TR 38.821 Table 6.1.1.1-3 (handheld UE); 3 km/h is an assumption |
| `mobility.groups` | none | profile |
| `run.duration_s` | **30** | numerical setting (the satellite moves 227 km in 30 s; the users stay under the 19 beams) |
| `run.warmup_s` | **2** | numerical setting |
| `ntn.altitude_km` | 600 | TR 38.821 Table 6.1.1.1-1 (LEO-600) |
| `ntn.aperture_m` | 2 | TR 38.821 Table 6.1.1.1-1 (Set-1, S band: equivalent antenna aperture 2 m; 3 dB beamwidth 4.4127 degrees) |
| `ntn.eirp_dbw_per_mhz` | 34 | TR 38.821 Table 6.1.1.1-1 (Set-1, S band, LEO-600: 34 dBW/MHz) |
| `ntn.n_beams` | 19 | TR 38.821 Table 6.1.1.1-4 (19 beams, hexagonal on the UV plane, adjacent beam spacing sqrt(3) sin(HPBW/2)) |
| `ntn.centre_elevation_deg` | 30 | TR 38.821 Table 6.1.1.1-4 (case 2: central beam boresight from the target elevation) and Table 6.1.3.2-1 (target elevation 30 degrees for LEO) |
| `ntn.environment` | rural | TR 38.821 Table 6.1.1.1-5 (deployment scenario: rural); TR 38.811 Tables 6.6.1-1 and 6.6.2-3 (suburban and rural) |
| `ntn.atm_zenith_db` | 0.045 | TR 38.811 Eq. 6.6-8 with the atmospheric losses of the S-band LEO link budgets of TR 38.821 Table 6.1.3.3-1 (0.1 dB at 30 degrees; 0.2 dB at 12.5 degrees for GEO): 0.04-0.05 dB |
| `ntn.scintillation_db` | 2.2 | TR 38.821 Table 6.1.3.2-1 (ionospheric scintillation loss 2.2 dB, note 1) |
| `ntn.sf_corr_m` | 37 | TR 38.811 Table 6.7.2-7a (rural, S band, LOS: shadowing correlation 37 m; NLOS 120 m, Table 6.7.2-8a) |
| `ntn.los_corr_m` | 60 | assumption: TR 38.901 Table 7.6.3.1-2 (LOS/NLOS state, RMa: 60 m); TR 38.811 gives no value |

## Known limitations

- With the central beam at 30 degrees elevation (case 2 of TR 38.821 Table 6.1.1.1-4) the regular hexagon of the UV plane is stretched on the ground: neighbouring beam centres lie 72 km along the track and 163-283 km across it, and three beams of the outer ring point at 5.6-7 degrees elevation, below the 10 degrees of TR 38.821 Table 4.2-2; they serve no user of the area and only interfere.
- Frequency reuse 1 (TR 38.821 Table 6.1.1.1-5, option 1): at the beam edges the neighbouring beams interfere with full power, and most link failures are coverage failures (no beam is good enough); the options of reuse 3 and 2 are not modelled in this version.
- One satellite and its 19 beams, no wrap-around of beams and no next satellite: the run is short enough for the users to stay under the beams.
- Earth-moving beams only (scenarios C2, D2); earth-fixed beams (C1, D1), several satellites, the feeder link, Doppler and the Ka band are not modelled.
- The round-trip delay is the worst case of scenario C2 for every user, not the user's own slant range.
- One shadowing correlation distance (37 m, the LOS value; NLOS 120 m in TR 38.811); the LOS state correlation is the RMa value of TR 38.901.
- condEventT1 is not modelled; condEventD2 is combined with A3 with one time-to-trigger (rule cho_d2).
- The failure model is not calibrated for NTN; read failure rates relative to each other.

## Reference results

- Slant range, free-space path loss and the link budget are checked against TR 38.821 Table 6.1.3.3-1, the beamwidth of the antenna pattern against Tables 6.1.1.1-1 and -2 (handoverlab verify, group ntn).
