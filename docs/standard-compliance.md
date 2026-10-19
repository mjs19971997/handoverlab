# Standard compliance

**Summary (1.9.0).** This page lists, clause by clause, the 3GPP and ITU-R rules that govern
handover in 5G and beyond-5G systems, and how HandoverLab models each of them: as the standard
specifies it (**follows**), with a stated abstraction (**abstraction**), or not yet (**not modelled**,
with the roadmap item). The clauses were read from the official texts (TS 38.331 V17.18.0 and
V18.11.0, TS 38.133 V17.23.0 and V18.15.0, TS 38.300 V17.17.0, V18.11.0 and V19.4.0, TS 38.321
V17.15.0, V18.10.0 and V19.4.0, TS 38.322 V17.4.0, TS 38.213 V18.9.0, TS 38.215 V18.5.0,
TS 38.423 V18.9.0, TS 37.340 V18.7.0, TR 38.901 V17.0.0, TR 36.839 V11.1.0, TR 38.913 V19.0.0,
TR 38.914 V20.1.0, ITU-R M.2410-0 and M.2412-0). The page ends with the comparison against ns-3 /
5G-LENA and against handover statistics measured in commercial 5G networks.

The options added in 1.9.0 make the handover command and the execution follow TS 38.331; they are
switched off by default, so the results of 1.x are unchanged. The **3GPP protocol profile** is:

```yaml
scenario:
  protocol: {cmd_during_t310: receive, t304_s: 1.0, rlm_holdoff_s: 0.2}
```

## Measurements and triggering

| Rule | Clause | HandoverLab | Status |
|---|---|---|---|
| L3 filter F_n = (1 - a) F_(n-1) + a M_n, a = 1/2^(k/4), default k = 4, in dB | TS 38.331 5.5.3.2 | `protocol.l3_k`; the coefficient is converted to the L1 sample period so that the time characteristic of the 200 ms reference is kept, as note 3 of the clause requires | follows |
| L1 measurement period about 200 ms in FR1 (max(200 ms, ceil(5 Kp) SMTC)), 480 ms in FR2 | TS 38.133 9.2.5 | L1 samples every `protocol.l1_period_s` (40 ms) into the time-equivalent filter; one period for all carriers | abstraction (FR2 period not distinguished) |
| SS-RSRP accuracy: relative +-2 to 3 dB (FR1), +-6 dB (FR2) | TS 38.133 10.1 | Gaussian error `radio.l1_error_db` (1 dB) per L1 sample; the standard gives bounds, not a distribution | abstraction (inside the bounds) |
| SS-RSRP, RSRQ, SINR definitions | TS 38.215 5.1 | received power per site (wideband), SINR with load-weighted interference; no RSRQ | abstraction |
| Event A3: Mn + Ofn + Ocn - Hys > Mp + Ofp + Ocp + Off, cell individual offsets | TS 38.331 5.5.4.4 | `gap_db > off_db` with `off_db = Off + Hys` and per-cell-pair offsets (CIO) from the rule hooks | follows (entering condition); the leaving hysteresis is not separate |
| Time-to-trigger: the condition holds for all L3-filtered samples during TTT; values 0-5120 ms | TS 38.331 5.5.4.1, TimeToTrigger | entry time kept per user and neighbour; any value | follows |
| Report interval (ms120 ...) | TS 38.331 ReportConfigNR | `protocol.report_interval_s` (0.12 s) | follows |
| Cell quality from the best beam(s) | TS 38.331 5.5.3.3 | one value per cell (no beams) | abstraction |

## Radio link monitoring and radio link failure

| Rule | Clause | HandoverLab | Status |
|---|---|---|---|
| Qout = 10 % and Qin = 2 % hypothetical PDCCH BLER | TS 38.133 8.1.1 | SINR thresholds `protocol.qout_db` (-8 dB), `qin_db` (-6 dB) of TR 36.839 Table 5.2.1.3.1; the SINR-to-BLER mapping is left to implementation | follows (implementation choice) |
| Evaluation over 200 ms (out of sync) and 100 ms (in sync), FR1 without DRX | TS 38.133 8.1.2.2 | filtered SINR with `protocol.qout_window_s` 0.2 s and `qin_window_s` 0.1 s (exponential averaging instead of a sliding window) | follows (abstraction of the window shape) |
| T310 starts on N310 consecutive out-of-sync, stops on N311 in-sync; defaults 1000 ms, n1, n1 | TS 38.331 5.3.10.1-2, 9.2.3 | `t310_s`, `n310`, `n311` with these defaults | follows |
| T310 cannot start while T304 runs | TS 38.331 5.3.10.1 | link monitoring only on connected users, not during execution | follows |
| RLF on T310 expiry, then re-establishment (T311) | TS 38.331 5.3.10.3, 5.3.7 | failure, cell selection by the best measurement, outage `protocol.reest_s` (1 s) | follows; delay is an abstraction (TS 38.133 6.2.1: 50 ms + 200-800 ms identification + SI + PRACH) |
| RLF on an RA problem or on RLC max retransmissions | TS 38.331 5.3.10.3; TS 38.321 5.1; TS 38.322 5.3.2 | not modelled separately (failures come from link monitoring and execution) | abstraction |
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

## Beyond 5G: what is not modelled yet

| Rule | Clause | Status |
|---|---|---|
| Beam failure detection and recovery (beamFailureInstanceMaxCount, beamFailureDetectionTimer, BFR by random access; evaluation max(50 ms, ...)) | TS 38.321 5.17; TS 38.133 8.5; TS 38.213 6 | not modelled: roadmap item 18 (beam management) |
| Several RLM reference signals per cell (up to 8 in FR2) | TS 38.133 8.1.1 | not modelled (one link per cell): roadmap item 18 |
| Measurement gaps, inter-frequency and multi-carrier measurements, FR2 measurement periods | TS 38.133 9.3; 9.2.5 | not modelled: roadmap item 19 |
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
