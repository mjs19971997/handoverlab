# Standard compliance

**Summary (1.11.0).** This page lists, clause by clause, the 3GPP and ITU-R rules that govern
handover in 5G and beyond-5G systems, and how HandoverLab models each of them: as the standard
specifies it (**follows**), with a stated abstraction (**abstraction**), or not yet (**not modelled**,
with the roadmap item). The clauses were read from the official texts (TS 38.331 V17.18.0 and
V18.11.0, TS 38.133 V17.23.0, V18.15.0 and V19.6.0, TS 38.300 V17.17.0, V18.11.0 and V19.4.0, TS 38.321
V17.15.0, V18.10.0 and V19.4.0, TS 38.322 V17.4.0, TS 38.213 V18.9.0 and V19.5.0, TS 38.215 V18.5.0 and V19.4.0, TS 38.101-1 V19.7.0, TS 38.101-2 V19.5.0,
TS 38.423 V18.9.0, TS 37.340 V18.7.0, TS 38.104 V18.15.0, TR 38.901 V17.0.0 and V19.5.0,
TR 37.885 V15.3.0, TR 36.885 V14.0.0, TR 38.811 V15.4.0, TR 38.821 V16.2.0, TR 36.839 V11.1.0, TR 38.913 V19.0.0,
TR 36.814 V9.2.0, TR 36.872 V12.1.0, TR 38.802 V14.2.0,
TR 38.914 V20.1.0,
ITU-R M.2410-0 and M.2412-0). The page ends with the
comparison against ns-3 / 5G-LENA, against handover statistics measured in commercial 5G networks
and, since 1.10.0, against the DAPS and LTM requirements of TS 38.133 and published 3GPP
evaluations.

The options added in 1.9.0 make the handover command and the execution follow TS 38.331; in 1.x they were
switched off by default, and since 2.0.0 they are the defaults (`handoverlab.stability.LEGACY_1X` switches
them off again). The **3GPP protocol profile** is:

```yaml
scenario:
  protocol: {cmd_during_t310: receive, t304_s: 1.0, rlm_holdoff_s: 0.2}
```

The options added in 1.10.0 bring SSB beams with beam management and beam failure recovery
(`radio.beams`), several carriers with measurement gaps (`radio.layers`), the measurement periods
of TS 38.133 (`protocol.meas_periods: ts38133`) and its RLM evaluation periods
(`protocol.rlm_eval: ts38133`); they are also off by default, and without them every result and
fingerprint of 1.9.0 is unchanged (`handoverlab verify` checks that the engine of the new options
gives the same event log as the engine of 1.x when no option is set).

Since 1.11.0 the highway follows TR 37.885 (wrap-around, LOS-only links, the two site layouts of
TR 36.885; options `layout.wrap`, `layout.highway_sites`, `radio.los_model`), and every scenario card
was checked against the texts (next section).

## Scenario cards against the texts (1.11.0)

Every value of every built-in card that names a source, and every default it relies on, was looked
up in the text of the source (TR 38.901 V17.0.0, TR 37.885 V15.3.0, TR 36.885 V14.0.0, ITU-R
M.2412-0). Outcome:

| Card | Finding | Action |
|---|---|---|
| `highway-10ghz` | 35 m roadside offset of TR 36.885 A.1.3 option 1 combined with the 500 m spacing of option 2; 10 GHz (TR 37.885: 2 or 4 GHz below 6 GHz, 30 GHz above); LOS from a probability (Table 6.2.1-2: LOS only); no wrap-around (Table A-1) | deprecated in 1.11.0, removed in 2.0.0; replaced by `highway-tr37885-4ghz` (option 1) and `highway-tr37885-30ghz` (option 2) |
| `dense-urban-2layer` | the UMa macro layer had the UMi shadowing (7.82 dB NLOS, 10 m); the in-car users had no car penetration loss (M.2412-0 Annex 1 clause 3.3: 9 dB, 5 dB); no minimum BS-UT distance | corrected: UMa 4 / 6 dB and 50 m, UMi 4 / 7.82 dB and 13 m per layer (TR 38.901 Tables 7.4.1-1, 7.5-6), 9 / 5 dB car loss, 35 m (Table 7.2-1) |
| `urban-grid-28ghz-beams` | UE noise figure 7 dB (M.2412-0 Table 5b at 30 GHz: 10 dB) | corrected to 10 dB |
| `indoor-office-4ghz` | citations of the bandwidth and of the 12 sites (M.2412-0 Table 5a, clause 8.3.1); UE height 1 m of TR 38.901 with the link budget of M.2412 (1.5 m) | citations corrected; the mixed source stated |
| urban-grid cards (`urban-grid-10ghz`, `fr3-urban-15ghz`, `smoke`, `urban-grid-28ghz-beams`) | TR 37.885 has 500 m macro sites with UMa in the urban grid (ours: small cells on UMi); speeds 52-63 km/h around the 60 km/h of option A; users closer than the 10 m minimum distance of UMi | stated on the cards as assumptions in 1.11.0; since 2.0.0 every vehicle drives at exactly 60 km/h in a lane of 3.5 m (profile `v60`) and the path loss is evaluated at 10 m or more (`radio.pl_min_distance_m`); the small cells on UMi remain an assumption |
| `fr3-urban-15ghz` | "FR3 (7.125-24.25 GHz)" is not a range of TR 38.901, which studies "7-24 GHz" in Release 19 | wording corrected |

TR 38.901 V19.5.0 (Release 19, with the 7-24 GHz study) was compared with V17.0.0: the path loss of
RMa, UMa, UMi and InH (Table 7.4.1-1), the LOS probabilities (Table 7.4.2-1) and the shadowing rows
and correlation distances of Table 7.5-6 are unchanged; Release 19 changed small-scale spreads, which
HandoverLab does not model, the IRR-glass loss of Table 7.4.3-1 (note 2: 25.4 + 0.11 f dB; the
calibration against R1-165974 keeps the earlier 23 + 0.3 f dB, see [radio calibration](calibration-3gpp.md)),
and added the SMa scenario. Notes 1 and 5 of Table 7.4.1-1 take
c = 3.0e8 m/s in the breakpoint distances; up to 1.12.0 HandoverLab took the exact speed of light (0.07 %
longer breakpoints), since 2.0.0 it takes 3.0e8 m/s (`radio.breakpoint_c_mps`).

Since 2.1.0 the cards were checked again against TR 38.901 V19.5.0, TR 37.885 V15.3.0, TR 38.811 V15.4.0,
TR 38.821 V16.2.0 and ITU-R M.2412-0:

| Card | Finding | Action (2.1.0) |
|---|---|---|
| urban-grid cards (`smoke`, `urban-grid-10ghz`, `fr3-urban-15ghz`, `urban-grid-28ghz-beams`) | UE antenna 1.5 m with the TR 37.885 urban option A (100 % vehicle type 2: antenna height 1.6 m, clause 6.1.2) | `radio.ue_height_m: 1.6` |
| `indoor-office-4ghz` | speeds spread +-10 % (M.2412-0 Table 5a: "Fixed and identical speed", 3 km/h); LOS probability of the mixed office with the 12-site layout of M.2412-0 clause 8.3.1, which takes Table A1-9 (InH_x: the open office) | profile `p3` (exactly 3 km/h); `radio.pathloss: inh_office_open` |
| `rural-700mhz` | speeds spread +-10 % (M.2412-0 Table 5c: fixed, 120 km/h in car) | profile `v120` |
| `dense-urban-2layer` | 8.33 m/s for 30 km/h | profile `v30` (30/3.6 m/s) |
| highway cards | lateral offset of up to 0.5 m in the lane, which TR 37.885 does not specify; shadowing half correlated between sites (a value of the TR 36.885 model; TR 37.885 clause 6.2.2 takes the shadowing of TR 38.901 for B2V links) | profile `v140c` (lane centre); uncorrelated shadowing (below) |
| `ntn-leo600-2ghz` | LOS probability of TR 38.811 with clutter loss in NLOS, while the baseline of TR 38.821 Table 6.1.1.1-5 is "Clear Sky, Line of sight" | `ntn.los_model: los` |

`handoverlab.stability.LEGACY_CARDS` lists the old card values.

## Scenario cards of 2.3.0

| Card | Follows | Abstraction (stated on the card) |
|---|---|---|
| `urban-macro-tr37885-4ghz` | TR 37.885 Tables 6.1.1-1, 6.1.3-1, 6.1.4-1, 6.2.1-2, clause 6.2.1 (UMa LOS/NLOS from the probability, spatially consistent, h_E 0.25 m), Table A-1; TR 36.885 A.1.3 (ISD 500 m) | no wrap-around (the lattice sites within 1000 m of the 3 x 3 blocks instead); lattice position read from TR 36.885 Figure A.1.3-1 (no numbers); antenna abstraction; one SF correlation distance |
| `suburban-sma-7ghz` | TR 38.901 V19.5.0 Tables 7.2-5, 7.4.1-1, 7.4.2-1, 7.4.3-2, 7.5-6 Part-4, 7.6.3.1-2, 7.8-1A | 11 sites without sectors or wrap-around; indoor users keep the LOS state and shadowing of their position and one UT height |
| 7 GHz large-scale calibration (TR 38.901 7.8.1, Table 7.8-1A) | since 2.4.0: UMa, UMi (6 and 7 GHz) and SMa (ISD 1299 m, 1732 m) at 7 GHz against the companies of R1-2506406; every percentile 5-95 % inside the company range (228 at 7 GHz, 342 with the 6 GHz reruns), the largest distance from the company mean 1.69-2.43 dB at 7 GHz and 1.65 / 2.88 dB for UMa / UMi at 6 GHz (the pre-registered 1.5 dB is not met) | `verify` group `calibration`; [radio calibration](calibration-3gpp.md) |

## Large-scale channel (TR 38.901 V19.5.0 clause 7; 2.1.0, `radio.channel_detail`)

`radio.channel_detail: 3gpp` (the default since 2.1.0) gives the rows below; `simple` gives the model of 2.0.0
and 1.x (Gaussian-shaped field correlation, shadowing 0.5-correlated between sites, no C'(h_UT), no height
checks) and is part of `handoverlab.stability.LEGACY_1X`.

| Rule | Clause | HandoverLab | Status |
|---|---|---|---|
| Path loss of RMa, UMa, UMi street canyon, InH-Office, LOS and NLOS; breakpoints with c = 3.0e8 m/s | Table 7.4.1-1, notes 1 and 5 | `radio.pathloss`; every coefficient checked by `verify --only pathloss` | follows |
| Applicability ranges: d2D >= 10 m; UMa/UMi 1.5 m <= h_UT <= 22.5 m; RMa 10 m <= h_BS <= 150 m, 1 m <= h_UT <= 10 m; d2D <= 5 km (RMa LOS 10 km); InH 1 m <= d3D <= 150 m | Table 7.4.1-1 | the formulas are evaluated at d2D >= 10 m (`radio.pl_min_distance_m`); heights outside the ranges are refused; links longer than the upper bound give a warning, and the formulas are used there (rural card: up to about 6.4 km) | follows (heights, lower bound); abstraction above the upper bound |
| UMa effective environment height h_E: 1 m with probability 1 / (1 + C(d2D, h_UT)), otherwise uniform(12, 15, ..., h_UT - 1.5); LOS probability with C'(h_UT) | Table 7.4.1-1 note 1; Table 7.4.2-1 | both, per link (place-tied on the street grid, per user and site elsewhere); they differ from h_E = 1 m only for h_UT >= 13 m | follows |
| LOS probability: RMa, UMi, UMa, InH mixed office and open office | Table 7.4.2-1 | `radio.pathloss` `inh_office` (mixed) or `inh_office_open` (open office) | follows |
| Shadow fading: log-normal, autocorrelation R(dx) = exp(-\|dx\| / d_cor) | 7.4.4, Eq. (7.4-5); Table 7.5-6 | place-tied field generated exactly with this covariance on the raster (circulant embedding), unit variance between raster points; along a user's own path an AR(1) process, which has the same exponential autocorrelation. On the street grid the radio map (path loss and shadowing, `radio.map_res_m`, 1 m) is interpolated linearly between its pixels, which smooths the field below the pixel size | follows (map raster: numerical setting) |
| LSPs of different BS-UT links uncorrelated, co-sited sectors equal | 7.5 step 4 | shadowing uncorrelated between sites (`radio.shadow_site_corr` unset); sectors of a site share the site's value | follows |
| Separate LOS and NLOS shadowing parameters (sigma and d_cor) | Tables 7.4.1-1, 7.5-6; 7.6.3.4 | separate sigma; one d_cor per card (UMi street grid: the LOS 10 m also for NLOS, NLOS 13 m), and LOS and NLOS links share one unit realisation, so the shadowing keeps its sign when a link changes state | abstraction (stated on the cards) |
| Spatially consistent LOS state: a realisation of a correlated random variable compared with the LOS probability; correlation distance of Table 7.6.3.1-2; site-specific (uncorrelated between sites) | 7.6.3.1, 7.6.3.3, Table 7.6.3.4-1 | street grid: a place-tied field with exp(-d / d_cor), applied to the links that the buildings leave clear, so the LOS share is P(clear) x Pr_LOS, below Table 7.4.2-1; open area and indoor: an AR(1) process along each user's path, not shared between users | follows (state); abstraction (combination with the buildings, open-area process) |
| Soft LOS state, Eqs. (7.6-18), (7.6-19) | 7.6.3.3 | `radio.soft_los`: power weights LOS_soft^2 and 1 - LOS_soft^2 (no fast fading, so no cross term) | follows (power level) |
| Multi-frequency: the same LOS state (Step 2) and LSPs (Step 4) on all frequencies of one link | 7.6.5 | layers with `cosited: true` reuse the random fields of the first layer; their `pathloss`, `los_corr_m` and `shadow_decorr_m` must equal those of the first layer (checked since 2.1.0); soft LOS may differ with the frequency, as 7.6.5 allows | follows |
| O2I car penetration loss N(9, 5^2) per UT | 7.4.3.2 | `radio.penetration_db`, `penetration_sd_db` (since 2.3.0 not for indoor users) | follows (option) |
| SMa path loss (LOS PL1/PL2 with d_BP of note 5, NLOS without max(), h = 10 m, W = 10 m, fc <= 37 GHz) and LOS probability (commercial, residential, vegetation terms) | V19.5.0 Table 7.4.1-1 notes 2 and 5; Table 7.4.2-1 | `radio.pathloss: sma`, `radio.vegetation` (2.3.0); checked by `verify --only scenarios` | follows |
| O2I building penetration: PL_tw (Eq. 7.4-3, materials of Table 7.4.3-1 with the Release 19 IRR glass), PL_in = 0.5 d2D-in, d2D-in = min of two uniform variables (25 m UMa/UMi/SMa commercial, 10 m RMa/SMa residential), sigma_P; low, high, low-loss A; UT-specific | 7.4.3.1, Eq. (7.4-2), Tables 7.4.3-1, 7.4.3-2 | users of an `indoor: true` speed group, `radio.o2i_model`, `o2i_d_in_max_m` (2.3.0); the loss on all links of the user | follows (loss) |
| Indoor UT: LOS probability at d2D-out, PL_b at d3D-out + d3D-in, O2I shadowing (UMa/UMi 7 dB, SMa 8 dB), floors | Table 7.4.2-1; 7.4.3.1; Table 7.5-6 | the indoor user keeps the LOS state, breakpoint and shadowing of its position and the one UT height; the effect on the coupling gain is measured by `verify` (S4) | abstraction |
| Fast fading: TDL-A .. TDL-E taps, Jakes Doppler per tap with f_D = \|v\| / lambda_0, LOS tap of TDL-D / -E at f_S = 0.7 f_D with K1 13.3 / 22 dB, delay scaling Eq. 7.7-1, K-factor change Eq. 7.7.6-1/-2 | 7.7.2 (Tables 7.7.2-1 to -5), 7.7.3, 7.7.6 | `radio.fast_fading` (2.2.0, off by default), `delay_spread_ns`, `fading_k_db`: one TDL per scenario, independent per user-cell link, 32 sinusoids per Rayleigh tap, channel at 4 points of the PDCCH band and 8 of the carrier ([guide](guides/fading.md)); MIMO extension 7.7.5 and CDL not used | follows (option; single-link TDL) |

## Map-based channel model (1.12.0, `radio.map_file`)

TR 38.901 V19.5.0 clause 8 defines a map-based hybrid model: deterministic ray tracing on a digitized map
plus stochastic components of clause 7, "not calibrated and can be used per company basis", with the map
format left to the implementation. For ray-traced maps HandoverLab **follows** the deterministic
large-scale part of clause 8 (a path gain per site and pixel from a ray tracer, `handoverlab.mapfile`;
clause 8.4 step 1: "Import digitized map") and **does not model** the random clusters added from step 4
on, nor the small-scale part (ray-level phases, Doppler), as nowhere else in HandoverLab. Maps from
measurements can be read in the same format, but they are outside TR 38.901 (**abstraction**).

## Non-terrestrial networks (2.0.0, `layout.kind: ntn`)

| Rule | Clause | HandoverLab | Status |
|---|---|---|---|
| Earth a sphere of radius 6371 km; satellite antenna 4 \|J1(ka sin t) / (ka sin t)\|^2 | TR 38.811 V15.4.0 6.3, 6.4.1 | so; since 2.1.0 ka is set so that the pattern has the tabled 3 dB beamwidth (next rows; until 2.0.0 ka came from the aperture, 0.16 % wider for 2 m) | follows |
| LOS probability per elevation (reference elevations 10-90 degrees) | TR 38.811 Table 6.6.1-1, 6.6.1 | `ntn.los_model: probability`: the value of the nearest reference elevation, as 6.6.1 prescribes ("taken from the nearest reference elevation angle"; 6.6.2 likewise for shadowing and clutter), a spatially correlated state along each user's path | follows (nearest reference elevation, as 6.6.1 and 6.6.2 prescribe); the process along the path is an abstraction (next row) |
| Propagation conditions of the system-level simulations: "Base-line: Clear Sky, Line of sight" | TR 38.821 Tables 6.1.1.1-5, 6.1.1.1-7 | `ntn.los_model: los` (since 2.1.0; the card `ntn-leo600-2ghz` uses it): every link LOS, no clutter loss, LOS shadowing | follows (option) |
| Time variation of LOS state and shadowing | TR 38.811 6.5.1: "Only drop-based simulations are considered" | AR(1) processes in the user's own displacement only; the change of the line of sight with the moving satellite does not decorrelate them | abstraction (not specified) |
| Basic path loss PLb = FSPL(d, fc) + SF + CL, FSPL = 32.45 + 20 log10 fc + 20 log10 d, slant range d | TR 38.811 Eqs. 6.6-2..6.6-4, Tables 6.6.2-1..3 | so, with the shadowing and clutter loss of the S band for suburban and rural areas | follows |
| Atmospheric loss Azenith / sin(alpha) | TR 38.811 Eq. 6.6-8 | `ntn.atm_zenith_db` (0.045 dB, derived from the link budgets of TR 38.821 Table 6.1.3.3-1) | follows |
| Ionospheric scintillation | TR 38.821 Table 6.1.3.2-1 note 1 (link-budget margin, P3 curve for 1 % of the time); Table 6.1.1.1-5 note 2 (zero for the calibration) | `ntn.scintillation_db` (2.2 dB, a fixed loss on every link) | abstraction (link-budget margin; set 0 for the calibration of Table 6.1.1.1-5) |
| LEO-600 Set-1 S band, handheld UE, 19 beams on the UV plane, spacing sqrt(3) sin(HPBW / 2) from the 3 dB beamwidth ("Only the 3dB beam width parameters should be used"), reuse 1 | TR 38.821 V16.2.0 Tables 6.1.1.1-1, -3, -4, -5 | the card `ntn-leo600-2ghz`; since 2.1.0 the tabled 4.4127 degrees (`ntn.hpbw_deg` unset), spacing 0.06668 (Table 6.1.1.1-6, informative: 0.0668); reuse 3 and 2 not modelled | follows (option 1) |
| Wrap-around for FRF = 1: two additional tiers of beams around the 19 beams | TR 38.821 6.1.1.1, after Table 6.1.1.1-5 | not modelled: only the 19 beams interfere | abstraction |
| Central beam: baseline for C2/D2 at nadir (90 degrees, (0, 0) on the UV plane); case 2 from a target elevation allowed | TR 38.821 Tables 6.1.1.1-4, 6.1.1.1-6 | `ntn.centre_elevation_deg` (card: 30 degrees, the LEO target elevation of Table 6.1.3.2-1; not the baseline) | follows (case 2, non-baseline) |
| Link budget of the S-band LEO cases | TR 38.821 Table 6.1.3.3-1 | `verify --only ntn`, N1: within 0.028 dB | follows |
| Satellite speed 7.56 km/s, maximum round-trip delay 25.77 ms (C2) | TR 38.821 Table 7.1-1 | circular orbit from the altitude; the worst-case delay added to preparation and execution | follows (one delay for every user) |
| condEventD1 / D2: entering Ml1 - Hys > Thresh1 and Ml2 + Hys < Thresh2, leaving Ml1 + Hys < Thresh1 or Ml2 - Hys > Thresh2; with D2 the reference locations move | TS 38.331 V18 5.5.4.15, 5.5.4.15a | rule `cho_d2`: reference locations = beam centres on the ground at time t | follows |
| D1 / D2 configured together with A3, A4 or A5 | TS 38.331 CondReconfigToAddMod | `cho_d2` requires D2 and A3; one time-to-trigger for both | follows (one TTT, a simplification) |
| condEventT1, RACH-less NTN handover, earth-fixed beams, several satellites, feeder link, Doppler | TS 38.331 5.5.4.16; TS 38.300 16.14 | not modelled | not modelled |

## Measurements and triggering

| Rule | Clause | HandoverLab | Status |
|---|---|---|---|
| L3 filter F_n = (1 - a) F_(n-1) + a M_n, a = 1/2^(k/4), default k = 4, in dB; the filter adapted to other input rates so that its time characteristics are kept, with k defined for a sample rate X = one intra-frequency L1 measurement period of the frequency range | TS 38.331 V18.11.0 5.5.3.2 (second bullet) | `protocol.l3_k`; the coefficient is converted to the L1 sample period with X of the carrier's frequency range: 200 ms in FR1 (and FR3), 480 ms in FR2-1 at an SMTC of 20 ms (TS 38.133 9.2.5.2), per cell with several carriers (since 2.1.0; 2.0.0: 200 ms everywhere) | follows |
| L1 measurement period without gaps: FR1 max(200 ms, ceil(5 Kp) T_SMTC), FR2 max(400 ms, ceil(M_meas Kp K_layer1) T_SMTC) (M_meas 24 or 40 in FR2-1) | TS 38.133 9.2.5.2 (Tables 9.2.5.2-1/-2), 9.2.5.1 (M_meas) | default: L1 samples every `protocol.l1_period_s` (40 ms) into the time-equivalent filter. With `protocol.meas_periods: ts38133` (1.10.0): the linear average of the samples over the period of the cell's frequency range (200 ms FR1, 480 ms FR2-1 at T_SMTC 20 ms, power class `protocol.fr2_power_class`), delivered once per period; Kp = K_layer1 = CSSF = 1 | follows with the option |
| Inter-frequency measurements within gaps: gap patterns (MGL, MGRP); period FR1 Max(200 ms, Ceil(8 Kgap) Max(MGRP, T_SMTC)) CSSF, FR2 Max(400 ms, Ceil(Kgap M_meas_inter) Max(MGRP, T_SMTC)) CSSF; no reception from the serving cell during a gap | TS 38.133 9.1.2 (Table 9.1.2-1), 9.3.4, 9.3.5 (Tables 9.3.5-1/-2), 9.1.5.2 | `radio.layers` with `meas_periods: ts38133`: gap pattern `protocol.gap_pattern` (default 0: 6 ms every 40 ms), 320 ms (FR1) and 1.6 s (FR2-1) at T_SMTC 20 ms; Kgap = 1, CSSF = number of other carriers (equal sharing); every user has the gap pattern and gets no data for MGL / MGRP of the time | follows with the option |
| L3 filter input rate: X = one intra-frequency L1 period of the frequency range | TS 38.331 5.5.3.2 | X of each cell's frequency range (since 2.1.0 also by default, see the first row); with `meas_periods: ts38133` the coefficient is adapted to each cell's delivery period (a = 1/2^(k/4) exactly at the intra-frequency rate) | follows |
| SS-RSRP accuracy: FR1 absolute +-4.5 dB (normal) / +-9 dB (extreme), relative +-2 / +-3 dB; FR2 absolute and relative +-6 / +-9 dB | TS 38.133 10.1.2 and 10.1.3 (Tables 10.1.2.1.1-1, 10.1.2.1.2-1, 10.1.3.1.1-1, 10.1.3.1.2-1) | Gaussian error `radio.l1_error_db` (1 dB) per L1 sample; the standard gives bounds, not a distribution | abstraction (inside the bounds) |
| SS-RSRP, RSRQ, SINR definitions | TS 38.215 5.1 | received power per site (wideband), SINR with load-weighted interference; no RSRQ. With beams or layers (1.10.0): SS-RSRP per resource element as the power over the bandwidth spread evenly over the 12 N_RB subcarriers of the transmission bandwidth configuration (TS 38.101-1 V19.7.0 / TS 38.101-2 V19.5.0 Table 5.3.2-1; since 2.1.0 with `channel_detail: 3gpp`; a bandwidth without a table entry, FR3 and `simple`: B / SCS subcarriers, guard bands included), per SSB beam; the SSS power is not boosted relative to the data REs | abstraction (flat spectrum) |
| Event A3: Mn + Ofn + Ocn - Hys > Mp + Ofp + Ocp + Off, cell individual offsets | TS 38.331 5.5.4.4 | `gap_db > off_db` with `off_db = Off + Hys` and per-cell-pair offsets (CIO) from the rule hooks; Ofn = Ofp = 0 (no offsetMO per measurement object) | follows (entering condition); the leaving hysteresis is not separate; offsetMO not modelled |
| Time-to-trigger: the condition holds for all L3-filtered samples during TTT; TimeToTrigger ms0, 40, 64, 80, 100, 128, 160, 256, 320, 480, 512, 640, 1024, 1280, 2560, 5120 | TS 38.331 5.5.4.1; TimeToTrigger (V18.11.0 p.1159) | entry time per user and neighbour; the report at the expiry of the TTT, also between two measurement instants; since 2.1.0 the same for the CHO execution condition (5.3.5.13.4 uses the same wording; 2.0.0: at the next instant). Other values are accepted; `handoverlab.standard`, the `verify` group `values` and the study gate `standard_values` flag them | follows |
| Report interval ReportInterval ms120 ... min30 | TS 38.331 ReportConfigNR (V18.11.0 p.1053) | `protocol.report_interval_s` (0.12 s); one reporting grid shared by all users, reportAmount infinite, no reportOnLeave (5.5.5, 5.5.4.1 use a timer per measId and UE) | follows (value); abstraction (one grid) |
| Cell quality from the beams: the highest beam, or the linear average of up to nrofSS-BlocksToAverage beams above absThreshSS-BlocksConsolidation | TS 38.331 5.5.3.3 | default: one value per cell. With `radio.beams` (1.10.0): exactly this rule (`ssb_avg`, `ssb_thresh_dbm`) on the beam L1 values, then the L3 filter | follows with the option |
| Event A5: Mp + Hys < Thresh1 and Mn + Ofn + Ocn - Hys > Thresh2 | TS 38.331 5.5.4.6 | rule `a3a5` (1.10.0): A5 towards other carriers (thresholds per direction), A3 within a carrier; Ofn = Ocn = 0; with `a3_inter` the A3 towards other carriers shares the A5 time-to-trigger and entry time (one timer per cell, where 3GPP has two events) | follows (entering condition); `a3_inter`: abstraction |

## Radio link monitoring and radio link failure

| Rule | Clause | HandoverLab | Status |
|---|---|---|---|
| Qout = 10 % and Qin = 2 % BLER of a hypothetical PDCCH (Tables 8.1.2.1-1/-2: AL8 at +4 dB, AL4 at 0 dB to the SSS) | TS 38.133 8.1.1, 8.1.2.1 | SINR thresholds `protocol.qout_db` (-8 dB), `qin_db` (-6 dB) of TR 36.839 Table 5.2.1.3.1, with no BLER mapping (TS 38.133 clause 8.1 gives none, also with `rlm_interference: dynamic`); the 2 dB gap is the TR 36.839 value, not derived from the two hypothetical PDCCH | abstraction (TR 36.839 thresholds) |
| Evaluation of out of sync Max(200, Ceil(10 P) T_SSB) and in sync Max(100, Ceil(5 P) T_SSB) ms in FR1 without DRX (200 / 100 ms for T_SSB <= 20 ms); FR2 with the factor N (8 in FR2-1, 12 in FR2-2) | TS 38.133 8.1.2.2 (Tables 8.1.2.2-1/-2) | filtered SINR with `protocol.qout_window_s` 0.2 s and `qin_window_s` 0.1 s (exponential averaging; fixed, whatever T_SSB); with `protocol.rlm_eval: ts38133` (1.10.0) the windows of the serving cell's frequency range and T_SSB (FR2-1 at T_SSB 20 ms: 1.6 s and 0.8 s), P = 1 | abstraction (window shape; `ts38133` for the lengths) |
| RLM reference signals: up to N_RLM (2, 4 or 8 for L_max 4, 8, 64); out of sync when all RLM-RS are below Qout; without configured RLM-RS the RS of the active TCI state of the PDCCH | TS 38.133 8.1.1 (Table 8.1.1-2); TS 38.213 5; TS 38.331 RadioLinkMonitoringConfig | with `radio.beams` (1.10.0): `rlm_rs: tci` (default) the serving beam, `rlm_rs: beams` the N_RLM best beams of the last beam report (the best of them counts; since 2.1.0 only these N_RLM, 2.0.0 also the serving beam); the set changes with every report, as an implicit RRC reconfiguration; L_max for paired spectrum (the 1.88 GHz limit of unpaired Case C is not modelled) | follows with the option |
| Out-of-sync / in-sync indications at least max(10 ms, T_RLM-RS) apart; N310 counts out-of-sync while T310 is stopped and is reset by in-sync, N311 counts in-sync while T310 runs and is reset by out-of-sync, both reset by a reconfiguration with sync; T310 starts at N310, stops at N311; defaults 1000 ms, n1, n1 | TS 38.133 8.1.6; TS 38.331 7.2, 5.3.10.1-2 (NOTE 2), 9.2.3 | `t310_s`, `n310`, `n311` with these defaults and value sets; indications every max(10 ms, `ssb_period_s`) (since 2.1.0; 2.0.0: every step, and for N > 1 the counters were reset by an instant without indication) | follows |
| Interference in the link-monitoring quality: SS-SINR / CSI-SINR take noise and interference over the REs of the SSS / CSI-RS; the RLM test SNR is over the SSS REs; what neighbours send on those REs is not specified | TS 38.215 5.1.5, 5.1.6; TS 38.133 A.6.5.1.1 NOTE 3 | default: the data-channel load of every neighbour, smoothed over `traffic.load_tau_s`; with `protocol.rlm_interference: dynamic` (2.8.0, not a default) the SINR over the RLM-RS REs with every neighbour's activity of the step: on CSI-RS that activity, on SSB the neighbours' SSBs on a share `rlm_ssb_overlap` and the activity on the rest | abstraction (what meets the RLM-RS is a deployment assumption) |
| RLM-RS: all SSBs, all CSI-RSs or a mix; TS 38.133 states frame and SFN alignment (under `deriveSSB-IndexFromCell`, or at 960 kHz SCS), not SSB overlap; whether neighbour SSBs overlap is not specified | TS 38.133 8.1.1, 7.7.1; TS 38.213 5; TS 38.331 RadioLinkMonitoringConfig | with `rlm_interference: dynamic`: `protocol.rlm_rs_type` `ssb` (default) or `csi-rs` (one type, no mix); `protocol.rlm_ssb_overlap` the share of the SSB REs that meet neighbour SSBs, sent whatever the load (1, default: a synchronous network with the same SSB positions, an assumption) | abstraction (choices left open by 3GPP, offered as sensitivity keys) |
| Neighbour activity in system-level evaluation: full buffer gives non-varying, bursty FTP traffic time-varying interference; FTP model 1 with Poisson arrivals and 2 Mbyte files (0.5 Mbyte optional), FTP model 3 with Poisson packet arrivals per UE; resource utilisation = used RBs / available RBs; cell loading = share of RBs used, full-buffer background users = full power in all RBs | TR 36.814 A.2.1.3, Table A.2.1.3.1-1, A.2.1.3.2, A.2.1.3.4; TR 36.872 A.1.1; TR 38.802 Table A.2.1-1; TR 36.839 Table 5.2.4.1 NOTE 1 | with `rlm_interference: dynamic`: per cell, Poisson arrivals of `traffic.ftp_file_bytes` files (0.5 Mbyte, TR 38.802 Table A.2.1-1) at the rate that makes the resource utilisation equal to the cell's background load (offered traffic = lambda S), each sent over the whole carrier at `protocol.rlm_bg_se` (2 bit/s/Hz, an assumption); load 1 = full buffer; an idle RE sends nothing; plus the share used by the simulated users | follows the evaluation method (send rate and time variation of a real neighbour's load are assumptions) |
| T310 cannot start while T304 runs; with DAPS the source T310 starts on N310 out-of-sync while T304 runs, and its expiry is a source RLF that releases the source | TS 38.331 5.3.10.1, 5.3.10.3 | no link monitoring during an execution; for DAPS (with T304) the source link is monitored during the execution and a source RLF releases it (since 2.1.0) | follows |
| RLF on T310 expiry, then re-establishment: T311 runs during cell selection (TS 38.304), the UE goes to RRC_IDLE if T311 expires | TS 38.331 5.3.10.3, 5.3.7.2, Table 7.1-1 | failure, then re-establishment that always succeeds, in the cell with the best L3 measurement, after `protocol.reest_s` (1 s); no cell suitability check, no T311 / T301 expiry, no RRC_IDLE | abstraction (delay: TS 38.133 6.2.1.2.1 bounds it by 50 ms + cell identification, in FR1 200 ms for a known and 800 ms for an unknown cell (Table 6.2.1.2.1-1), + system information + PRACH; TR 36.842 Table E.1-2 assumes 250 ms) |
| RLF on an RA problem or on RLC max retransmissions | TS 38.331 5.3.10.3; TS 38.321 5.1; TS 38.322 5.3.2 | with `radio.beams` (1.10.0): a beam failure recovery whose random access reaches preambleTransMax is a radio-link failure; otherwise failures come from link monitoring and execution (no RLC model) | follows for beam failure recovery; abstraction otherwise |
| T312 (optional, useT312) | TS 38.331 5.3.10, 5.5.4.1 | not modelled | not modelled (optional feature) |
| Link monitoring restarts on a newly joined cell: the quality is evaluated over the last T_Evaluate_out | TS 38.133 8.1.2.2 (interpretation; no clause defines a hold-off) | `protocol.rlm_holdoff_s` (0.2 s, default since 2.0.0): no out-of-sync for this time after joining a cell, whatever the frequency range | abstraction (interpretation of 8.1.2.2) |
| In-car penetration loss per user, 9 dB +- 5 dB | TR 38.901 7.4.3.2 | `radio.penetration_db`, `penetration_sd_db`, any speed | follows (option) |
| Qout / Qin as the BLER of a hypothetical PDCCH on the faded channel | TS 38.133 8.1, Tables 8.1.2.1-1/-2 (QPSK, 24 PRBs) | with `radio.fast_fading` (2.2.0): the MIESM effective SINR of QPSK over the 24-PRB band against `qout_db` / `qin_db` (flat-channel SINRs); without it the wideband SINR | abstraction (no link-level BLER curve) |

## Handover procedure

| Rule | Clause | HandoverLab | Status |
|---|---|---|---|
| Baseline handover steps: report, preparation, command, execution, completion | TS 38.300 9.2.3.2.1 | report after TTT, preparation `prep_s` (50 ms, TR 36.839 Table 5.2.4.1), command, execution `exec_s` (40 ms) | follows (timing abstraction) |
| A command received while T310 runs is executed: "stop timer T310" (if no DAPS bearer is configured) and "start timer T304" | TS 38.331 5.3.5.5.2 | `protocol.cmd_during_t310: receive` (1.9.0, default since 2.0.0): the command is received at the first step with link-monitoring SINR >= Qout and stops T310 (with DAPS since 2.1.0 the source T310 goes on); T310 expiry first ends in RLF (too late). 1.x default `lost`: lost at once, stricter than TR 36.839 5.2.1 and 5.4.1 | follows |
| A CHO configuration (RRCReconfiguration with conditionalReconfiguration) is stored whenever it is received; no condition on T310 | TS 38.331 5.3.5.13.1, 5.3.5.13.3 | since 2.0.0, with `cmd_during_t310: receive`: received like a command at the first step with SINR >= Qout, T310 goes on; with `lost` (1.x) lost while T310 runs | follows |
| Lost command: no UE rule; the outcome follows from RLF detection | TS 38.331 (none); TR 36.839 5.2.1 (evaluation rule: T310 running at reception = handover failure) | see the row above | follows with the option |
| T304: started at execution, stopped by a successful random access; expiry = handover failure, re-establishment; RA problems during T304 are not RLF; MAC retries | TS 38.331 5.3.5.3, 5.3.5.8.3, 5.3.10.3; TS 38.321 5.1 | `protocol.t304_s: 1.0` (1.9.0, default since 2.0.0): the UE joins at the first step with target SINR >= Qout and fails only when T304 expires. 1.x default (none): the target must reach Qout at the end of the execution time (TR 36.839 5.2.1 state 3) | follows |
| Interruption: T_interrupt = T_search + T_IU + T_processing (<= 20 ms) + T_delta (= Trs for a 20-PRB SSB) + T_margin (<= 2 ms); T_RRC 10 ms | TS 38.133 6.1.1.2.2; TS 38.331 12 | `exec_s` 40 ms (inside the bound); metric `interruption_s_pm` | follows (abstraction) |
| Mobility interruption target 0 ms | TR 38.913 7.7; ITU-R M.2410 4.12 | measured per rule (DAPS and LTM reach it closely) | measured |
| Xn handover preparation (TXnRELOCprep, no value in the spec) | TS 38.423 8.2.1 | preparation delay `prep_s` | abstraction |
| Measurement-based admission control, multi-connectivity | TS 38.300 9.2.3.2.1 (admission control), 4.5 (MR-DC) | not modelled (admission always succeeds) | abstraction |

## Conditional handover, DAPS, LTM and conditional LTM

| Rule | Clause | HandoverLab | Status |
|---|---|---|---|
| CHO: up to 8 candidates (maxNrofCondCells); execution condition with its time-to-trigger; execution starts T304, stops T310; choice among several triggered cells left to the UE; conditional configurations removed after a successful execution | TS 38.331 5.3.5.13, 5.3.5.3; TS 38.300 9.2.3.4 | rule `cho`: condEventA3 only (A4 / A5 not modelled), `n_max` (<= 8), execution offset and TTT, executed at the expiry of the TTT (since 2.1.0), the best triggered cell | follows (condEventA3) |
| CHO / LTM recovery: after RLF, the stored configuration of the selected candidate is applied with a reconfiguration with sync (attemptCondReconfig, attemptLTM-Switch); T304 expiry then leads to re-establishment | TS 38.331 5.3.7.3, 5.3.5.8.3 | `protocol.cho_recovery_s` (0.4 s); since 2.1.0 the UE joins only when the candidate's SINR reaches Qout while T304 runs, otherwise it re-establishes (2.0.0: always joined) | follows (delay abstraction) |
| DAPS: source link kept during execution; T310 not stopped; source RLF during T304 releases the source; at T304 expiry back to the source unless a source RLF was detected; not FR2 to FR2, not for NTN | TS 38.300 V18.11.0 9.2.3.1 (FR2 to FR2), 9.2.3.2, 16.14.3.2.1 (NTN); TS 38.331 5.3.5.5.2, 5.3.10.1, 5.3.10.3, 5.3.5.8.3 | rule `daps` with `fallback` and `source_data`; since 2.1.0 every item of this row (an FR2-to-FR2 handover of a DAPS rule is a baseline one; a DAPS rule on the NTN layout is refused); 2.0.0: T310 stopped, no source monitoring, fallback if the source SINR was at least Qout | follows |
| LTM (Rel-18): candidates configured in advance, MAC CE cell switch on L1 reports, early TA / RACH-less, T304, T310 stops, the ltm-Config kept across a cell switch, recovery into a candidate | TS 38.300 9.2.3.5 (Rel-18); TS 38.331 5.3.5.18 (5.3.5.18.6); TS 38.321 6.1.3.75 | rule `ltm`: L3-based candidates, L1 switch condition, `cmd_delay_s` 10 ms (as a delay before the UE receives the command, during which it can wait or be lost; TS 38.133 counts T_cmd after reception), `exec_s` 20 ms (RACH-less), recovery; the other candidates stay configured after a switch (since 2.1.0; 2.0.0: released); after a switch T310 / N310 / N311 keep their configured values (5.3.5.18.6 applies the 9.2.3 defaults; equal unless changed) | follows (timing abstraction; one gNB-CU is not modelled) |
| LTM delay D_LTM = T_HARQ + 3 ms + T_LTM-interrupt; T_LTM-processing 20 ms within FR1 or FR2, 40 ms between them (no ltm-FastUE-Processing) | TS 38.133 V18.15.0 6.3, 6.3.1.3 | 10 ms + 20 ms; since 2.1.0 20 ms more for a switch between FR1 and FR2 | follows (abstraction) |
| Conditional LTM (Rel-19): UE executes on L1 events LTM3/LTM5, up to 8 candidates, intra-gNB, RACH-less with a valid TA | TS 38.300 V19.4.0 9.2.3.7; TS 38.331 Rel-19 (not in V18.11.0) | rule `cltm`: a generic L1 switch offset evaluated by the UE, no command; not the LTM3 / LTM5 events with their hysteresis, offsets and TTT | abstraction |
| RACH-less execution: LTM with early TA (Rel-18), conditional LTM (Rel-19); RACH-less L3 handover with a configured or dynamic grant | TS 38.300 V18.11.0 9.2.3.5.1, V19.4.0 9.2.3.7.1; 9.2.3.6 (L3 handover) | LTM and CLTM executions are RACH-less | follows for LTM / CLTM; RACH-less L3 handover not separate |

## Beams and beam failure recovery (1.10.0, `radio.beams`)

| Rule | Clause | HandoverLab | Status |
|---|---|---|---|
| Antenna: uniform rectangular panel, element pattern (3 dB widths 65 deg, 30 dB limits, 8 dBi), DFT weights for the electrical tilt | TR 38.901 7.3, Table 7.3-1, Eq. 7.3-1 | `sectors` panels per site, `panel = [M, N]` at lambda/2, tilt `tilt_deg`; horizontal DFT weights of the same form steer `n_ssb` SSB beams spread over the sector (the codebook is a deployment choice) | follows (codebook: assumption) |
| At most L_max SSBs per cell (4 up to 3 GHz, 8 in FR1, 64 in FR2) | TS 38.133 Table 8.1.1-2 | checked on `n_ssb` | follows |
| Multi-frequency: the same LOS state, large-scale parameters and blockers on all frequencies of one link | TR 38.901 7.6.5 | layers with `cosited: true` reuse the random fields of the first layer; other layers have their own sites and fields | follows |
| Serving beam (TCI state) from L1-RSRP beam reports; L1-RSRP over max(T_Report, ceil(M P N) T_SSB), N = 8 in FR2 (Table 9.5.4.1-2); MAC-CE TCI switch delay T_HARQ + 3 ms + TO_k (T_first-SSB + 2 ms) | TS 38.133 9.5.4.1, 8.10.3 | beam L1 values averaged with the time constant of that period (M = 3, with T_Report = `report_s` and N = 8 in FR2 since 2.1.0), reports every `report_s`, switch to the best beam when it is `switch_db` better, `tci_delay_s` (10 ms: TO_k = 0, a TCI state in the active list) later | abstraction (switch decision) |
| BFD-RS: without failureDetectionResources the periodic CSI-RS of the active TCI states of the PDCCH (at most 2); an SSB may be in the set q0 | TS 38.213 6; TS 38.133 8.5.1; TS 38.331 RadioLinkMonitoringConfig | the SSB of the serving beam (one BFD-RS, as TS 38.133 8.5.1 allows) | follows (abstraction: SSB instead of CSI-RS) |
| Beam failure instance when the quality of all BFD-RS over T_Evaluate_BFD = Max(50, Ceil(5 P N) T_SSB) is worse than Qout_LR (10 % BLER of a hypothetical PDCCH at 0 dB to the SSS, Table 8.5.2.1-1, where Qout of RLM has +4 dB, Table 8.1.2.1-1); indications at least max(2 ms, T_SSB) apart | TS 38.133 8.5.1, 8.5.2.1, 8.5.2.2, 8.5.4; TS 38.213 6 | SINR of the serving beam averaged with the time constant T_Evaluate_BFD (FR1 100 ms, FR2-1 800 ms at T_SSB 20 ms) against Qout_LR = `protocol.qout_db` + 4 dB in SSB SINR (since 2.1.0; 2.0.0: `qout_db`), an indication every max(2 ms, T_SSB) | follows (window shape: abstraction) |
| BFI_COUNTER, beamFailureDetectionTimer (pbfd1-10, in indication periods), beamFailureInstanceMaxCount (n1-n10); an indication starts or restarts the timer; counter reset on timer expiry, on a new BFD-RS and on successful recovery | TS 38.321 5.17; TS 38.331 RadioLinkMonitoringConfig | `bfd_timer`, `bfi_max` with these value sets; since 2.1.0 an indication that falls on the timer's expiry restarts it (2.0.0 reset the counter first, so with pbfd1 it never passed 1) | follows |
| Recovery by random access on the SpCell: contention-free on a candidate SSB of candidateBeamRSList with SS-RSRP above rsrp-ThresholdSSB while beamFailureRecoveryTimer (ms10-ms200) runs, otherwise contention-based; success ends the recovery; preambleTransMax failed attempts = random-access problem | TS 38.321 5.1.1-5.1.4, 5.17; TS 38.331 BeamFailureRecoveryConfig | candidateBeamRSList = all SSBs of the cell, with contention-free resources for each; candidate beams from the filtered beam values (the candidate beam detection period of Tables 8.5.5.2-1/-2 equals the L1 period with M = 3 in FR1 and FR2-1 when T_Report <= ceil(3 N) T_SSB); one attempt takes `ra_attempt_s` (contention-based: twice), succeeds if the chosen beam's SINR >= Qout; `preamble_max` from the preambleTransMax values | follows (RA timing and success: abstraction) |
| Random-access problem of the SpCell while T300, T301, T304, T311, T319 are not running = RLF | TS 38.331 5.3.10.3 | the recovery's RA problem is an RLF (beam failure recovery does not run during an execution) | follows |
| Relation of beam failure recovery to T310 | TS 38.133 8.1 (RLM) and 8.5 (BFD) are separate; TS 38.321 5.17 does not touch T310 | the two run side by side: recovery does not stop T310, T310 expiry is an RLF during a recovery; a recovered beam ends out-of-sync through RLM. The coupling is not specified (implementation) | follows; coupling stated |
| Interference of a cell | (not specified) | a cell with beams interferes with the mean gain of its beams towards the user (a cell serving on all its beams), scaled by its load; without beams the abstraction of 1.x | abstraction |

What the beam model leaves out: CSI-RS beams and their refinement (data beams equal SSB beams),
UE receive beamforming unless `ue_panels` is set (next section), two BFD-RS sets (multi-TRP), SCell beam
failure recovery, DRX, measurement gaps that overlap the serving SSBs (P = 1), and fast fading.
FR3 (7.125-24.25 GHz) has no RRM requirements yet; there HandoverLab uses the FR1 formulas (N = 1)
and the FR2 limit of 64 SSBs. The evaluation periods of TS 38.133 are minimum requirements (the
longest time a UE may take); HandoverLab uses them as the averaging time constants, a conservative
reading.

## Data plane (2.2.0, `protocol.scheduler`)

| What the texts specify | Clause | HandoverLab | Status |
|---|---|---|---|
| Slots: 2^mu slots per 1 ms subframe | TS 38.211 Table 4.3.2-1 | slot length 1 ms / 2^mu of the carrier's subcarrier spacing | follows |
| MCS index table 1 for PDSCH (Q_m, target code rate) | TS 38.214 Table 5.1.3.1-1 | the 29 rows; the highest MCS with a block-error probability of at most 10 % at the reported SINR | follows (table); link adaptation: implementation |
| Transport block size | TS 38.214 5.1.3.2, Table 5.1.3.2-1 | steps 1 to 4; 12 PDSCH symbols, 12 DMRS REs per PRB, xOverhead 0, one layer | follows |
| HARQ entity per serving cell, parallel processes, retransmission decoded with the earlier data | TS 38.321 5.3.2.1, 5.3.2.2 | 8 processes per user (TS 38.331: absent nrofHARQ-ProcessesForPDSCH), chase combining, at most `harq_max_tx` transmissions after `harq_rtt_slots` | follows (combining and the number of transmissions: implementation choices) |
| Block errors of a transport block | not specified (receiver property) | normal approximation of the finite-blocklength error probability on the BICM bit channel, with an implementation loss | abstraction |
| Scheduling | not specified (gNB) | round robin in frequency or proportional fair in time | abstraction |

## User-plane buffers at handover (2.3.0, `protocol.buffers`)

| What the texts specify | Clause | HandoverLab | Status |
|---|---|---|---|
| Data forwarding may start with HANDOVER REQUEST ACKNOWLEDGE or the handover command | TS 38.300 V19.4.0 9.2.3.2.1 NOTE 2 | baseline handover: the source forwards its FIFO when the UE leaves and the data arriving until the completion | follows (forwarding is optional in the text: `forwarding`) |
| Forwarding in order; the target sends forwarded data before new data | 9.2.3.2.2, 9.2.3.2.3 | one FIFO per user, forwarded data stay at its head | follows |
| RLC-AM: the target re-transmits forwarded data not acknowledged; RLC-UM: no PDCP SDU re-transmitted in the target | 9.2.3.2.2 | HARQ data at the execution start kept with AM, lost with UM | follows (no PDCP status report, no duplicates) |
| RRC handover: MAC reset and RLC re-establishment (DAPS excepted); RLC re-establishment discards the RLC PDUs | 9.2.3.1; TS 38.322 V19.2.0 5.1.2 | as in the row above | follows |
| ARQ only for AM | TS 38.322 4.4 | a TB lost after the last HARQ transmission: re-sent with AM, lost with UM | follows (RLC ARQ timing not modelled) |
| DAPS: forwarding tunnel always; the source keeps sending and forwards SN-assigned SDUs; the UE receives from both until the source is released | 9.2.3.2.1 NOTE 4, 9.2.3.2.2, 9.2.3.2.3 | the source serves during the execution, its data are counted as forwarded copies, the target sends the rest at the completion | follows (SN assignment on arrival: assumption) |
| CHO: late forwarding after HANDOVER SUCCESS or early forwarding to candidates | 9.2.3.4.2 NOTE 2, 9.2.3.4.3, 9.2.3.4.4 | late: the data reach the target 2 x `xn_delay_s` after the completion; `early_forwarding`: at the target when the UE arrives | follows (copies to unused candidates not counted) |
| Inter-gNB LTM: early forwarding (step 9a), at the cell switch (NOTE 4) or late (NOTE 5); MAC reset, RLC / PDCP handling configured | 9.2.3.5.2, 9.2.3.5.3, 9.2.3.7.1 | as CHO (every HandoverLab cell is its own gNB) | follows (intra-CU LTM not modelled) |
| Re-establishment: the new gNB may fetch the data of the last serving gNB | 9.2.3.3 steps 6/7 | with `forwarding` the data move to the new cell, `xn_delay_s` after the re-establishment; without it they are lost in another cell | follows |
| PDCP discard timer; its values | TS 38.323 V19.1.0 5.3; TS 38.331 PDCP-Config discardTimer | data older than `discard_timer_s` (a value of the list or infinity) are discarded | follows (the gNB uses the UE timer values: assumption) |
| Xn delay, path switch | not specified | `xn_delay_s` (assumption); the path switches at the completion | abstraction |
## High-speed train in FR2 (2.3.0, card `hst-fr2-28ghz`)

Checked against TR 38.854 V18.0.0 (local text); behaviour compared with its system-level results in the
[high-speed train guide](guides/high-speed-train.md).

| What the text specifies | Clause | HandoverLab | Status |
|---|---|---|---|
| One train on one straight track, RRHs on one side; Ds 700 m, Dmin 10 m (Scenario 2 / Scenario-A), RRH 15 m, CPE 5 m | 5.1, Table 5.1-1, Table 5.2-1 | highway layout with one lane per direction 2 cm apart (one track), 12 one-side sites 700 m apart at 10 m, wrap-around | follows (wrap-around: assumption) |
| One RRH panel per site pointing along the track at the next RRH; 1 beam (Scenario 2); panel [1, 1, 8, 8, 2]; element A_m 30 dB, G_E,max 8 dBi | Table 5.2-1, Table 6.1.1.1, Table 6.1.2.1, Table 6.3.8.1-1 | one sector with one SSB beam of an 8 x 8 panel (one polarisation), azimuth and tilt aimed at the track 700 m away (180.82 deg, 90.82 deg) | follows |
| 28 GHz, 50 MHz, 120 kHz, 31 dBm, RMa LOS only, one CPE, no inter-cell interference, DL full buffer | 6.2.1, Table 6.3.8.1-1 | as specified; no background load; TR 38.901 RMa LOS shadowing (TR 38.854 is silent on it) | follows (shadowing: assumption) |
| CPE: 2 panels of 4 x 4 elements of 5 dBi, one active, 1 beam per panel | 5.3, 6.1.3, 6.1.4, Table 6.3.8.1-1 | one scalar gain of 17.04 dB towards every RRH | abstraction |
| A3 3 dB, TTT 80 ms; SMTC 20 ms; measurement period 480 ms (N = 8, no DRX); N310 = N311 = 2; Qout -8 dB, Qin -6 dB; T_Evaluate_out / in 600 / 300 ms | Table 6.3.8.1-1 | rule `{a3, 3, 0.08}`; TS 38.133 periods (480 ms at power class 3); RLM windows 0.6 / 0.3 s on the SSB link quality | follows (CSI-RS RLM: SSB instead) |
| DRX 40-320 ms, DPS / SFN, multi-TRP, tunnels, Doppler, uplink timing, cell detection delay | 5.1, 6.2.2, 6.3.4, 7.2 | not modelled (DRX only emulated through longer periods in the guide) | not modelled |
| Element back lobe in the mobility study ("antenna model without back lobe") | 6.3.4.1.3 | `radio.beams.am_db` raises A_m (default 30 dB, Table 6.1.1.1) | option |

## Dual connectivity (2.3.0, `protocol.dc`)

Checked against TS 37.340 V19.3.0 and TS 38.331 V18.11.0 (local texts). See the
[dual connectivity guide](guides/dual-connectivity.md).

| What the texts specify | Clause | HandoverLab | Status |
|---|---|---|---|
| NR-DC: one gNB as MN, another (or the same) as SN; MCG and SCG | TS 37.340 4.1.3.3 | the MCG on every carrier but one, the SCG (one PSCell) on the cells of `scg_layer` | follows (no SCells) |
| SN addition initiated by the MN on its measurements: SN Addition Request / Acknowledge, RRC reconfiguration via the MN, random access to the PSCell | TS 37.340 7.2, 10.2.2 | event A4 above `add_thresh_dbm` for `add_ttt_s` -> `prep_s` -> reconfiguration over the MCG -> random access after `exec_s`, joined at SINR >= Qout while T304 runs | follows (A4 trigger: implementation choice) |
| SN change (MN or SN initiated) and PSCell change within the SN, with random access; SN change signalling over the MCG SRB | TS 37.340 10.5.2, 10.6 | event A3 among SCG cells -> the same steps; every SCG reconfiguration over the MCG | follows (SRB3 not modelled) |
| SN release (MN or SN initiated) | TS 37.340 10.4.2 | PSCell below `release_thresh_dbm` for `release_ttt_s` -> released after `prep_s` | follows |
| RLF declared separately for MCG and SCG; SCG RLF on T310 expiry in the PSCell | TS 37.340 7.7; TS 38.331 5.3.10.3 | own RLM, N310/N311 indications and T310 on the PSCell with the protocol's constants | follows |
| SCG failure (RLF, SN addition/change failure) reported with SCGFailureInformation instead of re-establishment; the MN may keep, change or release the SN | TS 37.340 7.7; TS 38.331 5.7.3 | reported; the MN always releases the SCG | follows (MN decision: one of the options) |
| MCG RLF -> fast MCG link recovery if configured, otherwise re-establishment; re-establishment performs MR-DC release | TS 37.340 7.7; TS 38.331 5.3.7.2 | re-establishment (no T316), the SCG is released | follows (fast MCG recovery not modelled) |
| Inter-MN handover: the target MN keeps, changes or releases the SN | TS 37.340 10.7 | `on_mcg_ho`: `keep` (SCG unchanged) or `release` | follows (change: not modelled) |
| EN-DC / NGEN-DC / NE-DC, CPA / CPC, SCG deactivation, SCG LTM, CHO with candidate SCGs, split SRB / SRB3, bearer types and data forwarding, SCG measurement gaps | TS 37.340 4.1, 7.5, 7.6, 7.13, 10.2.3, 10.19, 10.20 | not modelled | not modelled |

## UE receive beams (2.4.0, `radio.beams.ue_panels`)

| Rule | Clause | HandoverLab | Status |
|---|---|---|---|
| UE antenna element: A_V = -min(12 ((theta - 90) / 90)^2, 25), A_H = -min(12 (phi / 90)^2, 25), A = -min(-(A_V + A_H), 25), G_E,max = 5 dBi | TR 38.802 V14.2.0 Table A.2.1-8 (model 1); ITU-R M.2412-0 Table 11 (the same pattern for 30 and 70 GHz) | exactly this element on every UE panel | follows |
| UE panels: panel model 1 (Mg = Ng = 1); Config 1 (Mg, Ng) = (1, 2), Omega_0,1 = Omega_0,0 + 180 deg; Config 2 (1, 4) at 90 deg steps; Theta = 90 deg; Config a (M, N, P) = (2, 4, 2), d = lambda / 2; up to 32 elements at 30 and 70 GHz | TR 38.802 Table A.2.1-4 | `ue_panels` 1, 2 or 4 with these bearings, `ue_panel` [M, N] (default [2, 4]) at lambda / 2, at most 32 elements over the panels; one polarisation per panel (P = 2 not modelled) | follows (polarisation: abstraction) |
| UE orientation of a mobile device: (Omega_0,0, Theta_0,0) = (U(0 deg, 360 deg), 90 deg) | TR 38.802 Table A.2.1-4 | `ue_orientation: random` (default): once per UE, fixed; `heading`: the first panel faces the direction of travel (an assumption, e.g. a vehicle-mounted UE) | follows (`random`) |
| Handheld UT model: antennas at the corners and edge centres of a 15 x 7 cm device, element of Table 7.3-2 (125 deg, 22.5 dB, 5.3 dBi), UT rotations for calibration | TR 38.901 V19.5.0 clause 7.3, Table 7.3-2 | not modelled (panel model of TR 38.802 instead) | not modelled |
| Receive beams of a panel | TR 38.802 6.1.6.1 (beam management P-1 / P-3: UE Rx beam sweep from a set of beams; codebook not specified) | `ue_beams` DFT beams per panel (default 4), weights of the form of Eq. 7.3-1, steered to `ue_tilt_deg` (90 deg) and azimuths spread over `ue_beam_span_deg` (120 deg) | follows (codebook: assumption) |
| FR2 SS-RSRP from the combined signal of the antenna elements of a receiver branch; with receiver diversity not lower than any branch | TS 38.215 V18.5.0 5.1.1 | every panel is a receiver branch: `ue_rx: best` measures every SSB with the best beam of the best panel; `sweep` with beam j mod `ue_beams` of every panel at L1 instant j, reporting the highest of the last `ue_beams` samples | follows (ideal selection in `best`) |
| Time cost of the receive-beam sweep in FR2: Mmeas_period_w/o_gaps = 24 (PC 3) in max(400 ms, ceil(M Kp K_layer1) T_SMTC); for a UE with FastRx-BSF-MeasDelayReduction-r19 M = 3 x N_reduced_Rx_BSF; N = 8 / 12 in RLM, BFD and L1-RSRP | TS 38.133 V19.6.0 9.2.5.1, Table 9.2.5.2-2, 8.1, 8.5, 9.5.4.1 | already in `protocol.meas_periods` / `rlm_eval: ts38133` and the beam model (our reading: 24 = 3 samples x 8 receive beams); the option adds the gain, not a second time scaling, so `ue_rx: sweep` (which spends the sweep time itself) is refused with `meas_periods: ts38133` | follows |
| Serving receive beam (P-3 on the serving beam) | TR 38.802 6.1.6.1 | the best receive beam towards the serving site, re-chosen at every L1 instant, turned to the new cell when a handover or a re-establishment completes; desired power, RLM, BFD, BFR and the interference of every co-channel cell use it | abstraction (no receive-beam failure, no delay) |
| Direction of arrival | TR 38.901 7.5 (cluster angles, fast fading) | the geometric direction of the site, LOS or NLOS (HandoverLab has no multipath angles) | abstraction |

The option is off by default (`ue_panels: 0`, the isotropic UE of 2.3.0); it is not combined with
`protocol.dc` in this version, and layers on one carrier must share the UE settings. Radio-map and
dashboard plots do not show the UE gains.
## AI/ML-based mobility (2.4.0, rule `a3_pred`)

Checked against TR 38.744 V19.0.1 and TR 38.843 V19.0.0 (local texts). Results against the TR in the
[AI/ML mobility guide](guides/ai-mobility.md).

| What the text specifies | Clause | HandoverLab | Status |
|---|---|---|---|
| RRC_CONNECTED; goal 1 measurement reduction, goal 2 handover performance | TR 38.744 4.1 | case B (skipping) and case A (prediction ahead) | follows |
| RRM sub-use case 2: L3 cell-level result predicted from actual L3 cell-level results | TR 38.744 4.2 | one cell at a time from its own L3 series (single-cell approach) | follows (sub-use cases 1, 3-6 and the cluster approach: not modelled) |
| Case B filtering options 1, 2, 3 for the result after skipped instants | TR 38.744 4.2 | `filter_option` 1, 2, 3 | follows |
| Indirect event prediction: predicted results, then the event without further AI/ML; events A1-A6 | TR 38.744 4.3 | Event A3 from actual results up to the origin and predicted ones after it | follows (A3 only; direct prediction: not modelled) |
| RLF prediction | TR 38.744 4.4 | - | not modelled |
| Different random seeds for training and test; no traffic model | TR 38.744 5.1 | `fit_predictor` on training seeds; the evaluation uses disjoint seeds | follows (traffic model of the card kept) |
| Non-AI baseline: sample and hold (temporal), pathloss offset (frequency); ARIMA allowed | TR 38.744 5.1 | `predictor: hold`; ridge autoregression | follows (frequency domain: not modelled) |
| Sliding L1/L3 filtering: a filtered result every sample period; L3 filter of TS 38.331 5.5.3.2 | TR 38.744 5.1 | the engine's L3 filter every L1 period; the rule reproduces it bit for bit with `skip: 0` | follows |
| FR1: UMa 4 GHz, 20 MHz, ISD 500 m, 7 sites x 3 sectors with wrap-around, sampling 40 ms; FR2: UMi 30 GHz, 80 MHz, ISD 200 m, sampling 80 ms | TR 38.744 Table 5.1-1 | FR1: card `urban-macro-tr37885-4ghz` (UMa 4 GHz, 20 MHz, 500 m lattice, omni sites, no wrap-around), 40 ms; FR2: card `urban-grid-28ghz-beams` (UMi 28 GHz, 3 sectors x 8 SSB beams, 100 m site spacing), 80 ms | approximation |
| UE trajectory: TR 38.843 6.3.1 options 1-3 (straight segments, direction change in [-45, 45] deg) | TR 38.744 Table 5.1-1; TR 38.843 6.3.1 | street-grid trajectories of the cards (turns of 90 deg at crossings) | approximation |
| Accuracy: average L3 RSRP difference between predicted and ground-truth L3 result of the same cell; MRRT = skipped / total instants | TR 38.744 5.2.1.1 | mean absolute difference per horizon on the 4 strongest cells; MRRT counted after the warm-up | follows (cell set: assumption) |
| FilterCoefficient 4 (FR1 and FR2) | TR 38.744 Table 5.2.1.1-2 | `protocol.l3_k: 4` (the default) | follows |
| Generalization over UE speed: baseline, GC#1, GC#2 | TR 38.744 5.2.1.2, Table 5.2.1.2-1 | models per speed and on mixed speeds (`collect` data sets added) | follows |
| F1 = 2PR/(P+R) with counters n1, n2, n3 and maximum ETD | TR 38.744 5.3.1 | `stats()` of case A | follows (instants around a serving-cell change left out) |
| A3 offset 2 dB, TTT 320 ms, PW 320 ms (case A) or MRRT 50 % (case B), max ETD 80 ms | TR 38.744 Tables 5.3.1-1, 5.3.1-2 | the evaluation set-up of the guide | follows |
| HOF model of TR 36.839 5.2.1.3; HOF rate, HO attempts and HOF per UE per second; 40 ms preparation, 40 ms execution | TR 38.744 5.5.1 | HOF = failures `command_lost` + `rlf_in_preparation` + `execution_failure`; `protocol.prep_s` / `exec_s` 0.04 in the evaluation | follows |
| Handover model option 2 (command once the entry condition of the predicted event holds on the actual result, preparation from the prediction) | TR 38.744 5.5.1, Figure 5.5.1-2 | report when the entry condition holds now and is predicted for the TTT; preparation from the report | approximation |
| Handover model option 3 (predicted event reported, command after preparation) | TR 38.744 5.5.1, Figure 5.5.1-3 | A3 with TTT on the measured-and-predicted series | follows |
| Handover model option 1 (preparation on the predicted event, command on the legacy event) | TR 38.744 5.5.1, Figure 5.5.1-1 | - | not modelled |
| LCM, applicability, UE- or network-sided model, data collection and reporting | TR 38.744 6 | - | not modelled |

## Beyond 5G: what is not modelled yet

| Rule | Clause | Status |
|---|---|---|
| NTN mobility: CHO with condEventT1 (time), RACH-less NTN handover, earth-fixed beams, several satellites | TS 38.331 5.5.4.16; TS 38.300 16.14 | not modelled (D1 and D2 follow since 2.0.0, see above) |
| 6G | TR 38.914 V20.1.0 sets requirements only (mobility interruption 0 ms between TRxPs of one base station; speeds up to 1000-1200 km/h) | no 6G procedure is specified yet |

## Definitions used in the metrics

| Rule | Clause | HandoverLab |
|---|---|---|
| Too-late, too-early and wrong-cell handover: too late = RLF after a long stay, re-establishment in a different cell; too early = RLF shortly after a handover or a handover failure, re-establishment in the source; wrong cell = the same in a cell other than source and target | TS 38.300 V18.11.0 15.5.2.2.2 | outcome labels `too_late`, `too_early`, `wrong_cell` with exactly these cells (since 2.1.0); a re-establishment in the serving cell (the target after a handover, or the same cell) is labelled `coverage` (`coverage_failures_pm`), as the clause defines no class for it; one class per failure (an RLF shortly after a handover belongs to that handover). "Shortly after" is the time of stay of the service (`t_min_s`, 2-7 s) from the completion, where 15.5.2.2.2 uses an OAM timer (e.g. Tstore_UE_cntxt) from the handover initialisation | follows (classes); abstraction (the time) |
| Ping-pong: handover back within the minimum time of stay (MTS = 1 s) | TR 36.839 5.2.2 (TS 38.300 defines ping-pong only between systems) | `protocol.pingpong_s` = 1 s |
| Unnecessary handover: a completed handover after which the user stays shorter than the minimum time of its service or gains too little SINR, while the source would not have failed | HandoverLab definition (TS 38.300 15.5.2.3 defines an unnecessary handover only between systems; TR 36.839 5.2.2 uses the time of stay against MTS = 1 s) | `unnecessary_pm` with `t_min_s` and `theta_q_db` per service (assumptions, `traffic.services`) | HandoverLab definition |
| RRC messages: MeasurementReport, RRCReconfiguration and RRCReconfigurationComplete; one RRCReconfiguration carries all conditional candidates (condReconfigToAddModList); the LTM cell switch command is a MAC CE | TS 38.331 5.3.5.3, 5.3.5.13; TS 38.300 9.2.3.4.2, 9.2.3.5.2 | `rrc_messages_pm`: counted message by message (since 2.1.0; 2.0.0 counted per candidate and the LTM command, without the Complete of configurations and releases); re-establishment messages are not counted | follows |
| Handover failure rate = failures / attempts; failures in state 2 (from the A3 entering condition, i.e. also during the TTT, to the reception of the command) and state 3 (target below Qout at the end of execution) | TR 36.839 5.2.1 | failure causes `rlf_in_preparation` (from the report on: an RLF during the TTT counts as `rlf_without_handover`), `command_lost`, `execution_failure` | follows (state 2 from the report, not from the entering condition) |

## Comparison with ns-3 / 5G-LENA on the same rules

The ns-3 / 5G-LENA build of the comparison study was read at the source (contrib/nr, src/lte):

| Rule | ns-3 / 5G-LENA | HandoverLab (3GPP profile) |
|---|---|---|
| Command received while T310 runs (TS 38.331 5.3.5.5.2) | executed and T310 stopped in the stock code; the study build switched on a TR 36.839 rule (`Tr36839HandoverFailure`) that counts it as a failure | executed when the link reaches Qout (the ns-3-like option of 2.7.0, not a default: a failure, as in ns-3) |
| Out-of-sync detection in about 200 ms (TS 38.133 8.1.2.2) | 20 frames of 10 control receptions, 0.65-0.83 s at light traffic | 0.2 s (the ns-3-like option of 2.7.0, not a default: 200 control receptions, as in ns-3) |
| In-car loss per user (TR 38.901 7.4.3.2) | only at 30-120 km/h | any speed, per user |
| T304 at the UE (TS 38.331 5.3.5.8.3) | handover joining timeout of 200 ms at the target gNB | UE timer, 1 s |
| Link monitoring restart on the new cell | yes | yes (`rlm_holdoff_s`) |
| Re-establishment (TS 38.331 5.3.7) | yes (`UseRrcReestablishment`) | yes (fixed outage) |
| CHO, DAPS, LTM, conditional LTM (Rel-16 to 19) | none | all four |
| Beam failure recovery | none | none |
| Large-scale channel calibration (TR 38.901 7.8.1) | calibrated by its authors | calibrated (see [radio calibration](calibration-3gpp.md)) |
| Fast fading, packet-level PHY/MAC/RLC | yes | options since 2.2.0: TDL fast fading, a slot scheduler with MCS, TBS and HARQ; since 2.3.0 simplified PDCP / RLC buffers with data forwarding (downlink, one bearer) |

**Reading.** On the rules of the handover procedure and on the procedures of Releases 16 to 19,
HandoverLab with the 3GPP profile follows the normative texts more closely; on the physical layer
(fast fading, packets, scheduling) ns-3 models more. Neither models beam failure recovery.

## Fresh ns-3 hold-out (1.9.0)

48 new ns-3 runs (`ns3-urban-3.5ghz`, ISD 200 and 400 m, 12 and 20 m/s -- speeds never used before --,
A3 2/4/6 dB x 160/480 ms, two seeds) were compared with HandoverLab on 24 conditions. The
configuration and the limits were fixed in writing before the runs; nothing was tuned.

| Metric (24 conditions) | Limit | 1.3.0 configuration | 3GPP profile |
|---|---|---|---|
| Handovers: median ratio, rank | [0.8, 1.25], >= 0.9 | 0.93, 0.97 (pass) | 0.93, 0.97 (pass) |
| Unnecessary handovers: median ratio, rank | [0.8, 1.25], >= 0.9 | 0.95, 0.97 (pass) | 0.98, 0.97 (pass) |
| Failures: ratio of the means | [0.67, 1.5] | **0.84 (pass)** | 0.18 (fail) |
| Failures: rank | >= 0.8 | 0.68 (fail) | 0.64 (fail) |

The 1.3.0 configuration (in-car loss, ideal execution, restart of link monitoring) meets the
failure level of ns-3 on data it had never seen (later checks, N3, V1, V3 and V4 of the [calibration page](calibration.md), found the level of the defaults at 0.18, 0.32, 0.17 and 0.27 of ns-3's, and a separate comparison setting at 0.5-1.3 of
ns-3's, passing on 1 of the 4 sets (V4), not validated; corrected in 2.6.0; the ns-3-like setting of 2.7.0 is
not validated on V4 either). The 3GPP profile has far fewer failures than ns-3
because the ns-3 build counts every command that arrives during T310 as a failure (the TR 36.839
evaluation rule), while the profile follows TS 38.331. The order of the failure rates over the
conditions agrees in neither configuration: ns-3 failures grow much more with the time-to-trigger.

## Comparison with commercial 5G networks (1.9.0)

Handover statistics measured in commercial networks were taken from Xu et al. (SIGCOMM 2020),
Hassan et al. (SIGCOMM 2022), Ghoshal et al. (IMC 2023; arXiv 2511.03116), Kalntis et al.
(IMC 2024) and Liu et al. (MobiCom 2024). Six cases with acceptance bands (mostly a factor of 2)
were fixed in writing before the first run; nothing was tuned.

| Case | Measured | Default | 3GPP profile |
|---|---|---|---|
| C1 handovers per minute, walking, 3.5 GHz, A3 3 dB / 320 ms | 4.84 | 1.58 (fail) | 1.58 (fail) |
| C2 ping-pong within 15 s, A3 6 dB / 256 ms (Verizon setting) | 25 % | 26.9 % (pass) | 27.0 % (pass) |
| C2 ping-pong within 15 s, A3 8 dB / 640 ms (AT&T setting) | 15.5 % | 3.2 % (fail) | 4.0 % (fail) |
| C3 time between handovers, driving 11 m/s | 9.2 s | 24.6 s (fail) | 22.7 s (fail) |
| C4 handover failures per handover (TR 36.839 states 2 and 3) | 0.04-1.5 % | 8.8 % (fail) | 1.9 % (fail, 1.25x above) |
| C6 km per handover, low band at 120 km/h | 0.4-0.9 km | 0.75 km (pass) | 0.51 km (pass) |
| C5 interruption 27-76 ms; report to command 70-179 ms | -- | 40 ms; 50 ms | same |

The 3GPP profile brings the handover failure rate from about six times above the measured range to
just above it. In the mid band HandoverLab gives fewer handovers than the measured networks, whose
irregular, multi-layer deployments (LTE, 5G low/mid band, mmWave) the simulated grids do not have.

## DAPS and LTM against TS 38.133 and published 3GPP evaluations (1.10.0)

The checks and their bands were fixed in writing before the comparison (no value was changed after
it); `handoverlab verify` (group `extended`) repeats V1 and V2. The 3GPP contributions were read in
the documents downloaded from the 3GPP server (RAN1 and RAN2 TDocs of 2019-2022, TR 36.881).

| Check | Reference | HandoverLab | Result |
|---|---|---|---|
| V1a LTM interruption, FR1-FR1, known cell and TCI state, fast RRC processing, RACH-less, T_LTM-IU = 0 | TS 38.133 6.3.1.3: 0 + 20 + 0 + 0 + 0 = 20 ms | LTM `exec_s` 20 ms | pass (equal) |
| V1b the same, RACH-based, SSB-to-PRACH association period 10 ms | up to 20 + 10 + 10 = 40 ms | (no default for this case) | report only |
| V1c LTM command delay T_cmd = T_HARQ + 3 ms | TS 38.133 6.3.1.2; band [3, 10] ms | `cmd_delay_s` 10 ms | pass (at the upper end) |
| V1d DAPS, FR1 intra-frequency, 30 kHz: T_interrupt1 + T_interrupt2 | TS 38.133 6.1.3.2.2: 2 ms (sync), 3 ms (async) | `interruption_s` 0 ms | pass |
| V1e interruption the engine applies per execution | the configured value | LTM 20.000 ms (189 executions), DAPS 2.000 ms (156) | pass |
| V2a L3 handover interruption | 45.5-49.5 ms (TR 36.881, LTE), 80 ms (R1-2007151, agreed RAN1 model, FR2), about 75 ms (R2-2206982), about 120 ms (R2-2208200), 50-90 ms (Ericsson); band [22.75, 240] ms | `protocol.exec_s` 40 ms | pass, but below every reference: the default is optimistic |
| V2b LTM interruption | [44, 70] ms without enhancements (R2-2207806), about 66 ms from the RAN2 time chart (R2-2209256, RACH-based), 20-30 ms with early synchronisation (Ericsson); band [10, 140] ms | 20 ms | pass (the enhanced, RACH-less case) |
| V2c ratio LTM / L3 interruption | 0.22-0.60 (Ericsson); band [0.11, 1.0] | 0.50 | pass |
| V2d DAPS interruption | about 0 ms (R2-1907308, R2-1901361, R2-2206982), 2 ms (TS 38.133, as cited by Nokia); band [0, 4] ms | 0 ms | pass |
| V2e interruption per UE-minute against A3 (urban grid, 30 users at 30 m/s, seeds 720-722) | field trials (Ericsson with KDDI and AT&T, 2026): "up to 25 %" less interruption with LTM, conditions not published | DAPS 65 % less, LTM 63 % less (1.39 s, 0.48 s, 0.51 s per UE-minute) | report only: the simulated gain is larger than the field claims, as its L3 baseline includes re-establishments and its LTM case is the best one |

The LTM and DAPS parameters therefore sit at the fast end of what 3GPP specifies and evaluates;
for a pessimistic study set `exec_s` of `ltm` to 40-70 ms and `protocol.exec_s` to 50-90 ms.

## Sectors and two-layer deployments against measured handover counts (1.10.0)

1.9.0 gave fewer mid-band handovers than measured. Two explanations were tested with a plan fixed
before the runs (fresh seeds 710-712, the 3GPP protocol profile, the bands of the 1.9.0
comparison, every number reported):

**H1, three sectors per site** (Xu 2020: "Each gNB consists of 2 or 3 sectors"). The deployment of
the 1.9.0 cases with one change, `radio.beams: {sectors: 3, n_ssb: 8, panel: [4, 8], tilt_deg: 100}`:

| Case | Measured | Band | Without sectors | Three sectors with SSB beams |
|---|---|---|---|---|
| C1 handovers per UE-minute, walking, A3 3 dB / 320 ms | 4.84 | [2.42, 9.68] | 1.78 (fail) | 2.44 (pass, at the lower edge) |
| C2 ping-pong within 15 s, A3 6 dB / 256 ms | 25 % | [12.5, 50] % | 25.3 % (pass) | 14.8 % (pass) |
| C2 ping-pong within 15 s, A3 8 dB / 640 ms | 15.5 % | [7.75, 32] % | 9.4 % (pass) | 4.6 % (fail) |
| C3 time between handovers, driving 11 m/s | 9.2 s | [4.6, 18.4] s | 21.9 s (fail) | 13.4 s (pass) |
| C4 failures per handover | 0.04-1.5 % | [0.04, 1.5] % | 0.12 % (pass) | 0 % (fail: below the range) |

Sectors explain a large part of the missing handovers (C1 +37 %, C3 from 21.9 to 13.4 s), but the
case C2 with the AT&T setting and C4 now fail: with sectors the 8 dB / 640 ms setting returns to
the previous cell less often than measured, and no execution failure or lost command occurred.

**H2, two layers** (the ITU-R M.2412 dense urban deployment, card `dense-urban-2layer`, rule
`a3a5` with the dominant AT&T and Verizon settings of Ghoshal 2025). H2a uses the A5 thresholds in
both directions as written in the plan; H2b (fixed in an addendum before its runs, after a 20 s
software smoke run showed the layer alternation) uses the study's other dominant A5 setting
(-115 / -108 dBm) from the micro to the macro layer:

| Run | Time between handovers | Band | Failures per handover | Inter-frequency share |
|---|---|---|---|---|
| driving, H2a, two layers | 1.0 s (fail) | [4.6, 18.4] s | 6.9 % (fail) | 97 % (alternation between the layers) |
| driving, H2b, two layers | 3.8 s (fail: too many) | [4.6, 18.4] s | 3.5 % (fail) | 19 % |
| driving, macro layer alone | 7.2 s (pass) | [4.6, 18.4] s | 1.6 % (fail, just above) | -- |
| walking, H2a, two layers | 0.8 s (fail) | [11.05, 44.2] s | 0.39 % (pass) | 99 % |
| walking, H2b, two layers | 16.3 s (pass) | [11.05, 44.2] s | 0.14 % (pass) | 1 % |
| walking, macro layer alone | 18.7 s (pass) | [11.05, 44.2] s | 0.64 % (pass) | -- |

Measured dwell (M2HO): 15.5 s in sub-6 GHz cells, 7.2 s in mmWave cells. Simulated, driving H2b:
3.7 s in micro cells (most users stay on the micro layer, mean SINR 0.9 dB); walking H2b: 14.4 s.
The hypothesis "multi-layer deployments explain the missing handovers" is **not supported** in
this form: the two-layer deployment gives too many handovers when driving, and the macro layer
with three sectors at 200 m alone already reaches the measured range. What matters most is the
sectorisation and the site density, which the 1.9.0 scenarios lacked. A symmetric A5 configuration
makes users alternate between layers; the result depends strongly on the A5 thresholds per
direction, which the measurement studies report only as distributions.
