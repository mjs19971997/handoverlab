# Standard compliance

**Summary (1.11.0).** This page lists, clause by clause, the 3GPP and ITU-R rules that govern
handover in 5G and beyond-5G systems, and how HandoverLab models each of them: as the standard
specifies it (**follows**), with a stated abstraction (**abstraction**), or not yet (**not modelled**,
with the roadmap item). The clauses were read from the official texts (TS 38.331 V17.18.0 and
V18.11.0, TS 38.133 V17.23.0 and V18.15.0, TS 38.300 V17.17.0, V18.11.0 and V19.4.0, TS 38.321
V17.15.0, V18.10.0 and V19.4.0, TS 38.322 V17.4.0, TS 38.213 V18.9.0, TS 38.215 V18.5.0,
TS 38.423 V18.9.0, TS 37.340 V18.7.0, TS 38.104 V18.15.0, TR 38.901 V17.0.0 and V19.5.0,
TR 37.885 V15.3.0, TR 36.885 V14.0.0, TR 36.839 V11.1.0, TR 38.913 V19.0.0, TR 38.914 V20.1.0,
ITU-R M.2410-0 and M.2412-0). The page ends with the
comparison against ns-3 / 5G-LENA, against handover statistics measured in commercial 5G networks
and, since 1.10.0, against the DAPS and LTM requirements of TS 38.133 and published 3GPP
evaluations.

The options added in 1.9.0 make the handover command and the execution follow TS 38.331; they are
switched off by default, so the results of 1.x are unchanged. The **3GPP protocol profile** is:

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
| `highway-10ghz` | 35 m roadside offset of TR 36.885 A.1.3 option 1 combined with the 500 m spacing of option 2; 10 GHz (TR 37.885: 2 or 4 GHz below 6 GHz, 30 GHz above); LOS from a probability (Table 6.2.1-2: LOS only); no wrap-around (Table A-1) | deprecated (removed in 2.0.0); replaced by `highway-tr37885-4ghz` (option 1) and `highway-tr37885-30ghz` (option 2) |
| `dense-urban-2layer` | the UMa macro layer had the UMi shadowing (7.82 dB NLOS, 10 m); the in-car users had no car penetration loss (M.2412-0 Annex 1 clause 3.3: 9 dB, 5 dB); no minimum BS-UT distance | corrected: UMa 4 / 6 dB and 50 m, UMi 4 / 7.82 dB and 13 m per layer (TR 38.901 Tables 7.4.1-1, 7.5-6), 9 / 5 dB car loss, 35 m (Table 7.2-1) |
| `urban-grid-28ghz-beams` | UE noise figure 7 dB (M.2412-0 Table 5b at 30 GHz: 10 dB) | corrected to 10 dB |
| `indoor-office-4ghz` | citations of the bandwidth and of the 12 sites (M.2412-0 Table 5a, clause 8.3.1); UE height 1 m of TR 38.901 with the link budget of M.2412 (1.5 m) | citations corrected; the mixed source stated |
| urban-grid cards (`urban-grid-10ghz`, `fr3-urban-15ghz`, `smoke`, `urban-grid-28ghz-beams`) | TR 37.885 has 500 m macro sites with UMa in the urban grid (ours: small cells on UMi); speeds 52-63 km/h around the 60 km/h of option A; users closer than the 10 m minimum distance of UMi | stated on the cards as assumptions (the golden runs use these cards; exact 60 km/h and the minimum distance are planned for 2.0.0) |
| `fr3-urban-15ghz` | "FR3 (7.125-24.25 GHz)" is not a range of TR 38.901, which studies "7-24 GHz" in Release 19 | wording corrected |

TR 38.901 V19.5.0 (Release 19, with the 7-24 GHz study) was compared with V17.0.0: the path loss of
RMa, UMa, UMi and InH (Table 7.4.1-1), the LOS probabilities (Table 7.4.2-1) and the shadowing rows
and correlation distances of Table 7.5-6 are unchanged; Release 19 changed small-scale spreads, which
HandoverLab does not model, and added the SMa scenario. One small deviation remains: notes 1 and 5
of Table 7.4.1-1 take c = 3.0e8 m/s in the breakpoint distances, HandoverLab the exact speed of light
(0.07 % longer breakpoints); the correction changes results and is planned for 2.0.0.

## Measurements and triggering

| Rule | Clause | HandoverLab | Status |
|---|---|---|---|
| L3 filter F_n = (1 - a) F_(n-1) + a M_n, a = 1/2^(k/4), default k = 4, in dB | TS 38.331 5.5.3.2 | `protocol.l3_k`; the coefficient is converted to the L1 sample period so that the time characteristic of the 200 ms reference is kept, as note 3 of the clause requires | follows |
| L1 measurement period without gaps: FR1 max(200 ms, ceil(5 Kp) T_SMTC), FR2 max(400 ms, ceil(M_meas Kp K_layer1) T_SMTC) (M_meas 24 or 40 in FR2-1) | TS 38.133 9.2.5.2 (Tables 9.2.5.2-1/-2) | default: L1 samples every `protocol.l1_period_s` (40 ms) into the time-equivalent filter. With `protocol.meas_periods: ts38133` (1.10.0): the linear average of the samples over the period of the cell's frequency range (200 ms FR1, 480 ms FR2-1 at T_SMTC 20 ms, power class `protocol.fr2_power_class`), delivered once per period; Kp = K_layer1 = CSSF = 1 | follows with the option |
| Inter-frequency measurements within gaps: gap patterns (MGL, MGRP); period FR1 Max(200 ms, Ceil(8 Kgap) Max(MGRP, T_SMTC)) CSSF, FR2 Max(400 ms, Ceil(Kgap M_meas_inter) Max(MGRP, T_SMTC)) CSSF; no reception from the serving cell during a gap | TS 38.133 9.1.2 (Table 9.1.2-1), 9.3.4, 9.3.5 (Tables 9.3.5-1/-2), 9.1.5.2 | `radio.layers` with `meas_periods: ts38133`: gap pattern `protocol.gap_pattern` (default 0: 6 ms every 40 ms), 320 ms (FR1) and 1.6 s (FR2-1) at T_SMTC 20 ms; Kgap = 1, CSSF = number of other carriers (equal sharing); every user has the gap pattern and gets no data for MGL / MGRP of the time | follows with the option |
| L3 filter input rate: X = one intra-frequency L1 period of the frequency range | TS 38.331 5.5.3.2 | with `meas_periods: ts38133` the coefficient is adapted to each cell's delivery period with X of its frequency range (a = 1/2^(k/4) exactly at the intra-frequency rate) | follows with the option |
| SS-RSRP accuracy: relative +-2 to 3 dB (FR1), +-6 dB (FR2) | TS 38.133 10.1 | Gaussian error `radio.l1_error_db` (1 dB) per L1 sample; the standard gives bounds, not a distribution | abstraction (inside the bounds) |
| SS-RSRP, RSRQ, SINR definitions | TS 38.215 5.1 | received power per site (wideband), SINR with load-weighted interference; no RSRQ. With beams or layers (1.10.0): SS-RSRP per resource element (power over the bandwidth minus 10 log10(B / SCS)), per SSB beam | abstraction (follows per RE with the options) |
| Event A3: Mn + Ofn + Ocn - Hys > Mp + Ofp + Ocp + Off, cell individual offsets | TS 38.331 5.5.4.4 | `gap_db > off_db` with `off_db = Off + Hys` and per-cell-pair offsets (CIO) from the rule hooks | follows (entering condition); the leaving hysteresis is not separate |
| Time-to-trigger: the condition holds for all L3-filtered samples during TTT; values 0-5120 ms | TS 38.331 5.5.4.1, TimeToTrigger | entry time kept per user and neighbour; any value | follows |
| Report interval (ms120 ...) | TS 38.331 ReportConfigNR | `protocol.report_interval_s` (0.12 s) | follows |
| Cell quality from the beams: the highest beam, or the linear average of up to nrofSS-BlocksToAverage beams above absThreshSS-BlocksConsolidation | TS 38.331 5.5.3.3 | default: one value per cell. With `radio.beams` (1.10.0): exactly this rule (`ssb_avg`, `ssb_thresh_dbm`) on the beam L1 values, then the L3 filter | follows with the option |
| Event A5: Mp + Hys < Thresh1 and Mn + Ofn + Ocn - Hys > Thresh2 | TS 38.331 5.5.4.6 | rule `a3a5` (1.10.0): A5 towards other carriers (thresholds per direction), A3 within a carrier; Ofn = Ocn = 0 | follows (entering condition) |

## Radio link monitoring and radio link failure

| Rule | Clause | HandoverLab | Status |
|---|---|---|---|
| Qout = 10 % and Qin = 2 % hypothetical PDCCH BLER | TS 38.133 8.1.1 | SINR thresholds `protocol.qout_db` (-8 dB), `qin_db` (-6 dB) of TR 36.839 Table 5.2.1.3.1; the SINR-to-BLER mapping is left to implementation | follows (implementation choice) |
| Evaluation over 200 ms (out of sync) and 100 ms (in sync), FR1 without DRX; FR2 with the factor N (8 in FR2-1, 12 in FR2-2): Max(200, Ceil(10 P N) T_SSB) and Max(100, Ceil(5 P N) T_SSB) | TS 38.133 8.1.2.2 (Tables 8.1.2.2-1/-2) | filtered SINR with `protocol.qout_window_s` 0.2 s and `qin_window_s` 0.1 s (exponential averaging instead of a sliding window); with `protocol.rlm_eval: ts38133` (1.10.0) the windows of the serving cell's frequency range (FR2-1 at T_SSB 20 ms: 1.6 s and 0.8 s), P = 1 | follows (abstraction of the window shape) |
| RLM reference signals: up to N_RLM (2, 4 or 8 for L_max 4, 8, 64); out of sync when all RLM-RS are below Qout; without configured RLM-RS the RS of the active TCI state of the PDCCH | TS 38.133 8.1.1 (Table 8.1.1-2); TS 38.213 5; TS 38.331 RadioLinkMonitoringConfig | with `radio.beams` (1.10.0): `rlm_rs: tci` (default) the serving beam, `rlm_rs: beams` the N_RLM best beams of the last beam report (the best of them counts) | follows with the option |
| T310 starts on N310 consecutive out-of-sync, stops on N311 in-sync; defaults 1000 ms, n1, n1 | TS 38.331 5.3.10.1-2, 9.2.3 | `t310_s`, `n310`, `n311` with these defaults | follows |
| T310 cannot start while T304 runs | TS 38.331 5.3.10.1 | link monitoring only on connected users, not during execution | follows |
| RLF on T310 expiry, then re-establishment (T311) | TS 38.331 5.3.10.3, 5.3.7 | failure, cell selection by the best measurement, outage `protocol.reest_s` (1 s) | follows; delay is an abstraction (TS 38.133 6.2.1: 50 ms + 200-800 ms identification + SI + PRACH) |
| RLF on an RA problem or on RLC max retransmissions | TS 38.331 5.3.10.3; TS 38.321 5.1; TS 38.322 5.3.2 | with `radio.beams` (1.10.0): a beam failure recovery whose random access reaches preambleTransMax is a radio-link failure; otherwise failures come from link monitoring and execution (no RLC model) | follows for beam failure recovery; abstraction otherwise |
| T312 (optional, useT312) | TS 38.331 5.3.10, 5.5.4.1 | not modelled | not modelled (optional feature) |
| Link monitoring restarts on a newly joined cell (a full evaluation period) | TS 38.133 8.1.2.2, 8.1.4 | `protocol.rlm_holdoff_s` (0.2 s in the 3GPP profile) | follows (option) |
| In-car penetration loss per user, 9 dB +- 5 dB | TR 38.901 7.4.3.2 | `radio.penetration_db`, `penetration_sd_db`, any speed | follows (option) |

## Handover procedure

| Rule | Clause | HandoverLab | Status |
|---|---|---|---|
| Baseline handover steps: report, preparation, command, execution, completion | TS 38.300 9.2.3.2.1 | report after TTT, preparation `prep_s` (50 ms, TR 36.839 Table 5.2.4.1), command, execution `exec_s` (40 ms) | follows (timing abstraction) |
| A command received while T310 runs is executed: "stop timer T310 ... start timer T304" | TS 38.331 5.3.5.5.2 | default (1.x): lost at once, stricter than TR 36.839 5.2.1 and 5.4.1; with `protocol.cmd_during_t310: receive` (1.9.0) the command is received at the first step with link-monitoring SINR >= Qout and stops T310; T310 expiry first ends in RLF (too late) | follows with the option |
| Lost command: no UE rule; the outcome follows from RLF detection | TS 38.331 (none); TR 36.839 5.2.1 (evaluation rule: T310 running at reception = handover failure) | see the row above | follows with the option |
| T304: started at execution, stopped by a successful random access; expiry = handover failure, re-establishment; RA problems during T304 are not RLF; MAC retries | TS 38.331 5.3.5.3, 5.3.5.8.3, 5.3.10.3; TS 38.321 5.1 | default: the target must reach Qout at the end of the execution time (TR 36.839 5.2.1 state 3); with `protocol.t304_s` (1.9.0) the UE joins at the first step with target SINR >= Qout and fails only when T304 expires | follows with the option |
| Interruption: T_interrupt = T_search + T_IU + T_processing (<= 20 ms) + Trs + T_margin; T_RRC 10 ms | TS 38.133 6.1.1.2.2; TS 38.331 12 | `exec_s` 40 ms (inside the bound); metric `interruption_s_pm` | follows (abstraction) |
| Mobility interruption target 0 ms | TR 38.913 7.7; ITU-R M.2410 4.12 | measured per rule (DAPS and LTM reach it closely) | measured |
| Xn handover preparation (TXnRELOCprep, no value in the spec) | TS 38.423 8.2.1 | preparation delay `prep_s` | abstraction |
| Measurement-based admission control, multi-connectivity | TS 38.300 9.2.3.2 | not modelled (admission always succeeds) | abstraction |

## Conditional handover, DAPS, LTM and conditional LTM

| Rule | Clause | HandoverLab | Status |
|---|---|---|---|
| CHO: up to 8 candidates; CondEvent A3/A5 over TTT; execution starts T304, stops T310; choice among several triggered cells left to the UE | TS 38.331 5.3.5.13; TS 38.300 9.2.3.4 | rule `cho`: `n_max` (<= 8), execution offset and TTT, the best triggered cell | follows |
| CHO recovery: after RLF, CHO once into a candidate cell (attemptCondReconfig) | TS 38.331 5.3.7.3 | `protocol.cho_recovery_s` (0.4 s) | follows (delay abstraction) |
| DAPS: source link kept during execution; fallback to the source on failure without source RLF | TS 38.300 9.2.3.2; TS 38.331 5.3.5.8.3 | rule `daps` with `fallback` and `source_data` | follows |
| LTM (Rel-18): candidates configured in advance, MAC CE cell switch on L1 reports, early TA / RACH-less, T304, T310 stops, recovery into a candidate | TS 38.300 9.2.3.5 (Rel-18); TS 38.331 5.3.5.18; TS 38.321 6.1.3.75 | rule `ltm`: L3-based candidates, L1 switch condition, `cmd_delay_s` 10 ms, `exec_s` 20 ms (RACH-less), recovery | follows (timing abstraction; one gNB-CU is not modelled) |
| LTM delay D_LTM = T_HARQ + 3 ms + T_LTM-interrupt (UE processing 20 ms, first RS) | TS 38.133 6.3 (Rel-18) | 10 ms + 20 ms | follows (abstraction) |
| Conditional LTM (Rel-19): UE executes on L1 events LTM3/LTM5, up to 8 candidates, intra-gNB, RACH-less with a valid TA | TS 38.300 9.2.3.7 (Rel-19); TS 38.331 5.3.5.18 (Rel-19) | rule `cltm`: L1 switch condition evaluated by the UE, no command | follows |
| RACH-less handover (Rel-18): configured or dynamic grant, fallback to RA | TS 38.300 9.2.3.6 | LTM and CLTM executions are RACH-less | follows for LTM; not separate for baseline handover |

## Beams and beam failure recovery (1.10.0, `radio.beams`)

| Rule | Clause | HandoverLab | Status |
|---|---|---|---|
| Antenna: uniform rectangular panel, element pattern (3 dB widths 65 deg, 30 dB limits, 8 dBi), DFT weights for the electrical tilt | TR 38.901 7.3, Table 7.3-1, Eq. 7.3-1 | `sectors` panels per site, `panel = [M, N]` at lambda/2, tilt `tilt_deg`; horizontal DFT weights of the same form steer `n_ssb` SSB beams spread over the sector (the codebook is a deployment choice) | follows (codebook: assumption) |
| At most L_max SSBs per cell (4 up to 3 GHz, 8 in FR1, 64 in FR2) | TS 38.133 Table 8.1.1-2 | checked on `n_ssb` | follows |
| Multi-frequency: the same LOS state, large-scale parameters and blockers on all frequencies of one link | TR 38.901 7.6.5 | layers with `cosited: true` reuse the random fields of the first layer; other layers have their own sites and fields | follows |
| Serving beam (TCI state) from L1-RSRP beam reports; L1-RSRP over max(T_Report, ceil(M P N) T_SSB) | TS 38.133 9.5.4.1 (Tables 9.5.4.1-1/-2) | beam L1 values averaged with the time constant of that period (M = 3), reports every `report_s`, switch to the best beam when it is `switch_db` better, `tci_delay_s` later | abstraction (switch decision and delay are network implementation) |
| BFD-RS: the RS of the active TCI state of the PDCCH when none are configured (at most 2) | TS 38.213 6; TS 38.331 RadioLinkMonitoringConfig | the SSB of the serving beam (one BFD-RS) | follows |
| Beam failure instance when the quality of all BFD-RS over T_Evaluate_BFD = Max(50, Ceil(5 P N) T_SSB) is worse than Qout_LR (10 % BLER, the Qout threshold); indications at least max(2 ms, T_SSB) apart | TS 38.133 8.5.1, 8.5.2.2 (Tables 8.5.2.2-1/-2), 8.5.4; TS 38.213 6 | SINR of the serving beam averaged with the time constant T_Evaluate_BFD (FR1 100 ms, FR2-1 800 ms at T_SSB 20 ms) against `protocol.qout_db`, an indication every max(2 ms, T_SSB) | follows (window shape: abstraction) |
| BFI_COUNTER, beamFailureDetectionTimer (pbfd1-10, in indication periods), beamFailureInstanceMaxCount (n1-n10); counter reset on timer expiry, on a new BFD-RS and on successful recovery | TS 38.321 5.17; TS 38.331 RadioLinkMonitoringConfig | `bfd_timer`, `bfi_max` with these value sets; the counter is reset as listed | follows |
| Recovery by random access on the SpCell: contention-free on a candidate SSB with SS-RSRP above rsrp-ThresholdSSB while beamFailureRecoveryTimer (ms10-ms200) runs, otherwise contention-based; success ends the recovery; preambleTransMax failed attempts = random-access problem | TS 38.321 5.1.1-5.1.4, 5.17; TS 38.331 BeamFailureRecoveryConfig | candidate beams from the filtered beam values (the candidate beam detection period of Tables 8.5.5.2-1/-2 equals the L1 period with M = 3 at these settings); one attempt takes `ra_attempt_s` (contention-based: twice), succeeds if the chosen beam's SINR >= Qout; `preamble_max` from the preambleTransMax values | follows (RA timing and success: abstraction) |
| Random-access problem of the SpCell while T300, T301, T304, T311, T319 are not running = RLF | TS 38.331 5.3.10.3 | the recovery's RA problem is an RLF (beam failure recovery does not run during an execution) | follows |
| Relation of beam failure recovery to T310 | TS 38.133 8.1 (RLM) and 8.5 (BFD) are separate; TS 38.321 5.17 does not touch T310 | the two run side by side: recovery does not stop T310, T310 expiry is an RLF during a recovery; a recovered beam ends out-of-sync through RLM. The coupling is not specified (implementation) | follows; coupling stated |
| Interference of a cell | (not specified) | a cell with beams interferes with the mean gain of its beams towards the user (a cell serving on all its beams), scaled by its load; without beams the abstraction of 1.x | abstraction |

What the beam model leaves out: CSI-RS beams and their refinement (data beams equal SSB beams),
UE receive beamforming (only the factor N of TS 38.133), two BFD-RS sets (multi-TRP), SCell beam
failure recovery, DRX, measurement gaps that overlap the serving SSBs (P = 1), and fast fading.
FR3 (7.125-24.25 GHz) has no RRM requirements yet; there HandoverLab uses the FR1 formulas (N = 1)
and the FR2 limit of 64 SSBs. The evaluation periods of TS 38.133 are minimum requirements (the
longest time a UE may take); HandoverLab uses them as the averaging time constants, a conservative
reading.

## Beyond 5G: what is not modelled yet

| Rule | Clause | Status |
|---|---|---|
| NTN mobility: CHO triggers D1/T1 (distance, time), RACH-less NTN handover | TS 38.331 5.5.4.15-16; TS 38.300 16.14 | not modelled: roadmap item 20 |
| 6G | TR 38.914 V20.1.0 sets requirements only (mobility interruption 0 ms between TRxPs of one base station; speeds up to 1000-1200 km/h) | no 6G procedure is specified yet |

## Definitions used in the metrics

| Rule | Clause | HandoverLab |
|---|---|---|
| Too-late, too-early and wrong-cell handover | TS 38.300 15.5.2 | outcome labels `too_late`, `too_early`, `wrong_cell` |
| Ping-pong: handover back within the minimum time of stay (MTS = 1 s) | TR 36.839 5.2.2 (TS 38.300 defines ping-pong only between systems) | `protocol.pingpong_s` = 1 s |
| Handover failure rate = failures / attempts; failures in state 2 (RLF or PDCCH failure before the command is received) and state 3 (target below Qout at the end of execution) | TR 36.839 5.2.1 | failure causes `rlf_in_preparation`, `command_lost`, `execution_failure` |

## Comparison with ns-3 / 5G-LENA on the same rules

The ns-3 / 5G-LENA build of the comparison study was read at the source (contrib/nr, src/lte):

| Rule | ns-3 / 5G-LENA | HandoverLab (3GPP profile) |
|---|---|---|
| Command received while T310 runs (TS 38.331 5.3.5.5.2) | executed and T310 stopped in the stock code; the study build switched on a TR 36.839 rule (`Tr36839HandoverFailure`) that counts it as a failure | executed when the link reaches Qout |
| Out-of-sync detection in about 200 ms (TS 38.133 8.1.2.2) | 20 frames of 10 control receptions, 0.65-0.83 s at light traffic | 0.2 s |
| In-car loss per user (TR 38.901 7.4.3.2) | only at 30-120 km/h | any speed, per user |
| T304 at the UE (TS 38.331 5.3.5.8.3) | handover joining timeout of 200 ms at the target gNB | UE timer, 1 s |
| Link monitoring restart on the new cell | yes | yes (`rlm_holdoff_s`) |
| Re-establishment (TS 38.331 5.3.7) | yes (`UseRrcReestablishment`) | yes (fixed outage) |
| CHO, DAPS, LTM, conditional LTM (Rel-16 to 19) | none | all four |
| Beam failure recovery | none | none |
| Large-scale channel calibration (TR 38.901 7.8.1) | calibrated by its authors | calibrated (see [radio calibration](calibration-3gpp.md)) |
| Fast fading, packet-level PHY/MAC/RLC | yes | no (received-power level) |

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
failure level of ns-3 on data it had never seen. The 3GPP profile has far fewer failures than ns-3
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
