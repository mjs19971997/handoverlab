# Changelog

All notable changes to this project are documented in this file. The format follows
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/) for the public surface described in
[docs/stability.md](docs/stability.md); before 1.0.0 any interface could change.

## [Unreleased]

## [2.7.0] - 2026-10-25

No change of defaults or results: every golden fingerprint is unchanged. The new option is off by default and
imitates ns-3 / 5G-LENA, not 3GPP. Judged on a fresh, pre-registered ns-3 set (V4), it is **not validated**
(see "Validation"); the absolute failure level of HandoverLab stays not calibrated.

### Added

- An ns-3-like setting, `handoverlab.verify.ns3.NS3_LIKE_SETTING` (not a default), that imitates how ns-3 /
  5G-LENA v5.1 detects a radio-link failure, as read in its code (`NrUePhy::RlfDetection`, `NrUeRrc`) and
  measured in the control-channel diagnosis of ns-3 runs already used (N2 and an earlier diagnosis):
  - out-of-sync after 200 consecutive control-channel receptions below Qout (blocks of 10; a block at or above
    Qout restarts the count), in-sync after 100 receptions above Qin while T310 runs, both counted afresh on
    every new cell (new protocol keys `protocol.ns3_oos_rx`, `ns3_ins_rx`; off by default);
  - a user receives `ns3_ctrl_hz` + `ns3_ctrl_per_ue_hz` x (users of its cell) control channels per second,
    206 + 16.5 n measured at light traffic (new keys `protocol.ns3_ctrl_hz`, `ns3_ctrl_per_ue_hz`), so the
    detection takes 0.65-0.9 s, against the evaluation period of about 200 ms of TS 38.133 (Table 8.1.2.2-1);
  - a handover command that reaches the UE while T310 runs fails (the TR 36.839 criterion that ns-3 uses,
    `protocol.cmd_during_t310: lost`; TS 38.331 5.3.5.5.2 lets the command stop T310), ideal execution, no
    extra hold-off on a new cell, and an interferer load of 0.38 at link monitoring (`protocol.lm_load`; the
    load at which the HandoverLab link-monitoring SINR has the share below Qout and the quantiles of the ns-3
    control-channel SINR in N2).
  It is used with the in-car loss of ns-3: `scenario_for(isd, v, car=True, ns3_like=True)`,
  `verify.ns3.compare(..., ns3_like=True)`, `handoverlab verify --ns3 --ns3-like`, and in the bridge as row N:
  `ns3bridge.compare(..., setting="ns3-like")` (`ns3bridge.SETTINGS`), `handoverlab ns3 compare --ns3-like`.
- The values were chosen on seen ns-3 data only (N2, N3, V1, V3); the interferer load 0.38 was chosen in
  sample, after the in-sample rows were seen, between two candidates derived from the ns-3 control-channel
  SINR (stated in [calibration](docs/calibration.md#the-ns-3-like-setting-270)). In sample it is right only at
  long time-to-trigger: level 0.87 on N3 and 0.97 on V3, but 0.05 on V1 and 0.16 on N2 (TTT 80-320 ms, far
  too few failures); an interferer load of 1.0 gives the opposite pattern. The setting was committed before
  V4 was opened.

### Validation

- **V4, a fresh, pre-registered ns-3 set** (amendment N1 of the validation plan, fixed before the set was
  opened): 40 ns-3 / 5G-LENA runs, site distance 200 / 400 m, 14 / 22 m/s, time-to-trigger 128 / 1280 ms,
  seeds 701-705, equal run lengths on both sides (180 s, 60 s discarded); 897 ns-3 failures (29 in the
  128 ms cells, 868 in the 1280 ms cells). Rows run through the ns-3 bridge with the same seeds; criteria F1
  level in [0.67, 1.5], F2 rank correlation at least 0.8, F3 handover-rate ratio in [0.8, 1.25], F4 TTT sign
  in at least 3 of 4 pairs:

  | Row | F1 level | F2 order | F3 HO ratio | F4 TTT sign | Verdict | Level at TTT 128 ms | Level at TTT 1280 ms |
  |---|---|---|---|---|---|---|---|
  | R: defaults (default link monitoring, ideal execution) | 0.27, fails | 0.95 | 0.90 | 4 of 4 | fails F1 | 0.55 (16 / 29) | 0.26 (225 / 868) |
  | C: `COMPARISON_SETTING` | 0.73 | 0.98 | 0.815 | 4 of 4 | passes F1-F4 | 1.83 (53 / 29) | 0.70 (605 / 868) |
  | N: `NS3_LIKE_SETTING` | 1.03 | 0.93 | 0.759, fails | 4 of 4 | **not validated** (F3) | 0.03 (1 / 29) | 1.07 (924 / 868) |

  The levels per TTT are reported next to the verdict, as registered, not part of it.
- Row N, the ns-3-like setting: the overall level (1.03), the order and the TTT direction are right, but F3 is
  0.759, below 0.8, so by the registered rule it is **not validated**. Counted with HandoverLab's failed
  attempts (as ns-3's `ho_pm` counts them) F3 is 0.945; this was a side report announced in advance, not the
  criterion. The option imitates ns-3's failure detection and matches ns-3's failure level at long
  time-to-trigger (1.07 at 1280 ms), but gives far too few failures at short time-to-trigger (0.03 at 128 ms:
  1 failure against 29). It is offered as an option, not as a validated reproduction of ns-3, and it is not a
  default; the defaults stay those of 3GPP.
- Row C, the comparison setting: passes F1-F4 on V4 (level 0.73, just inside 0.67), the first fresh set with
  equal run lengths on which it passes; it passes 1 of the 4 fresh sets (N3, V1, V3, V4). Its level is too
  high at 128 ms (1.83) and too low at 1280 ms (0.70). It stays documented as a setting that brings the level
  closer (0.5-1.3 times ns-3's, depending on the set), not validated, not a default.
- Row R, the defaults: fail the level, as on every fresh set (0.27).
- The absolute failure level of HandoverLab stays **not calibrated**: compare failure rates between rules.
- Open question, left for future work: why HandoverLab has too few failures at short time-to-trigger under
  the ns-3-like detection. The likely cause, not checked, is fewer long periods below Qout before a neighbour
  becomes 3 dB stronger.

### Documentation

- The V4 result added to `docs/calibration.md` (summary and a new section "V4: the ns-3-like setting on a
  fresh set"), the [ns-3 bridge guide](docs/guides/ns3-bridge.md), `docs/verification.md`,
  `docs/comparison.md`, `docs/standard-compliance.md`, the user guide, the guides for indoor / rural and the
  upper mid-band, the README ("Checked against ns-3", the boundary table, What's new, roadmap), the 12
  scenario cards (scenario pages regenerated), the docstrings of `handoverlab.verify.ns3` and
  `handoverlab.ns3bridge`, and the help of `verify --ns3-like` and `ns3 compare --ns3-like` (command-line
  reference regenerated; it now lists `--ns3-like`). Every statement that the V4 validation is pending, and
  that the comparison setting passes on none of the fresh sets, is replaced by the result.
- Version 2.7.0 in the README, the user guide, the documentation home page, the comparison page and the
  citation metadata.

## [2.6.0] - 2026-10-25

No change of defaults or results: every golden fingerprint is unchanged. This release corrects a wrong
claim of 2.5.0 about the failure level (see "Corrected").

### Added

- A bridge to ns-3 / 5G-LENA (`handoverlab.ns3bridge`, `handoverlab ns3 export|import|compare`;
  [guide](docs/guides/ns3-bridge.md)). An ns-3 study file (`examples/ns3_study_v1.yaml`) defines conditions
  (site distance, speed, time-to-trigger, A3 offset, traffic, fading), users, run length and seeds once.
  `export` writes a ready-to-run package of the program `benchmarks/ns3/handoverlab-ns3-a3.cc`: the program,
  `build.sh`, `run.py` (standard library only, resumable, parallel, zips the results), `run.ps1` and
  `manifest.json` (study hash, HandoverLab version, every ns-3 command line). `import` reads the run JSONs
  into a reference file in the format of `handoverlab.verify.ns3.load_reference`. `compare` runs HandoverLab
  on the same cells and seeds (ideal execution, the in-car loss of ns-3; `--comparison` adds the comparison
  setting of 2.5.0) and applies the checks of the studies N3 and V1 (F1 level, F2 order, F3 handover rate,
  F4 time-to-trigger effect) with the limits as options. Options the program cannot simulate (other cards,
  beams, NTN, CHO, DAPS, LTM, other site distances, unknown keys) are refused, naming the option, before any
  file is written.
- `handoverlab.ns3bridge` is part of the public surface (`tests/data/public_api.json`).

### Validation

- Pre-registered acceptance of the bridge: exporting the V1 design gives the program options of the hand-made
  V1 package run by run (40 command lines); importing the 40 V1 results and running `compare` with and
  without the comparison setting gives the numbers of V1 (rows C and R) exactly, with
  `handoverlab.run_length: card`, the HandoverLab run length registered for V1 (150 s with 60 s warm-up, so
  90 s measured against 120 s in ns-3). With the same run length on both sides (`run_length: study`, the
  default; not registered) the comparison setting gives level 1.31, rank correlation 0.62 (below the limit
  0.8), handover-rate ratio 0.92 and the TTT sign in 4 of 4 pairs; the default link monitoring 0.32, 0.62,
  0.94 and 4 of 4. This difference revealed the error corrected below.

### Corrected

- **The failure-level analyses of 2.5.0 compared unequal run lengths.** For the fresh ns-3 sets N3, V1 and
  V3 the HandoverLab side ran the card's 150 s with 60 s warm-up (90 s measured), while ns-3 ran 180 s with
  60 s discarded (120 s measured); the level (F1) and order (F2) checks compare failure counts summed over
  the cells, so the HandoverLab counts covered three quarters of the ns-3 time. A corrected analysis was
  registered (amendment E1) before any corrected result was seen and applied to all three sets: equal run
  lengths (180 s, 60 s discarded on both sides), same ns-3 runs, seeds, rows and criteria.
- Corrected results (registered analysis with the wrong run length in brackets). The ns-3 comparison
  setting: N3 level 0.52 (0.47), fails; V1 level 1.31 (0.97) but rank correlation 0.62 (0.88), fails; V3
  level 0.64 (0.44), fails. So it passes F1-F3 on none of the three sets. The defaults (default link
  monitoring, ideal execution) fail level and rank on all three: level 0.18 / 0.32 / 0.17 (0.16 / 0.33 /
  0.095), rank 0.71 / 0.62 / 0.76. The handover-rate ratio (0.86-0.96) and the direction of the
  time-to-trigger effect pass in every set and row. A rate-based level (failures per UE-minute, not affected
  by the run length) equals the corrected count-based level in every set and row.
- Consequence: the 2.5.0 statement that the comparison setting passed the pre-registered checks on V1 is
  withdrawn. The absolute failure level is **not calibrated**: the comparison setting gives 0.5-1.3 times
  ns-3's failure level depending on the set, and its order of failures across cells is not
  reliable. `COMPARISON_SETTING`, `comparison=True` and `verify --ns3-comparison` are kept (the stability
  policy keeps them within 2.x) and documented as a setting that brings the level closer, not validated.
- Not affected: the comparisons of handover and unnecessary-handover rates (part A of the stored ns-3
  reference, `handoverlab verify --ns3`, `verify.ns3.compare`) and N2, which use rates per UE-minute.
- V3 (registered 2026-10-25 before its runs: 40 fresh ns-3 runs, site distance 200 / 300 m, 10 / 28 m/s,
  time-to-trigger 512 / 1024 ms, seeds 601-605, 1122 ns-3 failures): the comparison setting fails the level
  in both analyses (0.44 registered, 0.64 corrected) with rank 0.87 / 0.88; the defaults 0.095 / 0.17. At
  long time-to-trigger HandoverLab has fewer failures than ns-3, consistent with ns-3's slower out-of-sync
  detection (0.65-0.83 s), which HandoverLab does not model.
- Planned, not in this release: an "ns-3-like" option (not a default) that imitates ns-3's slower
  out-of-sync detection, built from the ns-3 data already seen and judged on a fresh set V4 (site distance
  200 / 400 m, 14 / 22 m/s, time-to-trigger 128 / 1280 ms, seeds 701-705), collected and kept unopened until
  the option and its settings are frozen.
- Corrected everywhere the 2.5.0 claim appeared: README ("Checked against ns-3", the boundary table, What's
  new), `docs/calibration.md` (the summary and the 2.5.0 study, with the registered numbers kept next to the
  corrected ones, and new sections on V3 and the correction), `docs/comparison.md`, `docs/verification.md`,
  `docs/standard-compliance.md`, the user guide, the guides, the 12 scenario cards (scenario pages
  regenerated), the docstrings of `handoverlab.verify.ns3`, the note of `verify --ns3 --ns3-comparison`, and
  the help of `verify --ns3-comparison` and `ns3 compare --comparison` (command-line reference regenerated).

### Documentation

- Version 2.6.0 in the README, the user guide, the documentation home page and the citation metadata.
  Dashboard screenshots retaken with this version.

## [2.5.0] - 2026-10-25

No change of defaults or results: every golden fingerprint is unchanged.

### Added

- The ns-3 comparison setting as code: `handoverlab.verify.ns3.COMPARISON_SETTING`
  (`{"protocol.lm_load": 0.15, "protocol.exec_can_fail": False}`: interferer load 0.15 at link monitoring,
  ideal execution), applied by `scenario_for(..., comparison=True)`, `compare(..., comparison=True)` and
  `holdout(..., comparison=True)` (after the in-car loss, before `overrides`), by
  `ns3_checks(..., comparison=True)` and `run_verify(..., ns3_comparison=True)` together with the in-car loss
  of ns-3, and on the command line by `handoverlab verify --ns3 --ns3-comparison`. The summary of `compare`
  records `car` and `comparison`. It is not a default.

### Validation

- An independent validation study, registered before any of its runs, with one amendment fixed before the runs
  of its second part; nothing tuned on its data (`docs/calibration.md`, "Independent validation study (2.5.0)").
- **V1, failure rate against 40 fresh ns-3 / 5G-LENA runs** (site distance 200 / 300 m, 10 / 28 m/s,
  time-to-trigger 80 / 320 ms, seeds 401-405). The N3 candidate, not re-tuned (`lm_load` 0.15, ideal
  execution, in-car loss): failure level 0.97 of ns-3 (limit 0.67-1.5), rank correlation 0.88 over the 8 cells,
  handover-rate ratio 0.965, TTT direction in 4 of 4: all pass, so it becomes the documented ns-3 comparison
  setting (corrected in 2.6.0: with equal run lengths it fails the rank on V1, 0.62, and is not validated).
  The 2.4.2 link monitoring with ideal execution: level 0.33 (fails), rank 0.84, ratio 0.973. V1 has
  time-to-trigger 80 and 320 ms only; on the earlier fresh set N3 the same setting failed the level (0.47): its
  TTT 100 ms cells matched, its TTT 640 ms cells had about half of ns-3's failures (matching at 100 ms was not a
  registered criterion).
- **V2, generalisation of the adaptive and learning rules** (tuned and trained on `urban-grid-10ghz`, seeds
  101-104; tested on `ns3-urban-3.5ghz`, `urban-macro-tr37885-4ghz`, `highway-tr37885-4ghz` and
  `fr3-urban-15ghz`, seeds 501-505, against tuned A3). `a3_mro` and `dqn` generalise (fewer unnecessary
  handovers on all four test cards, no cost flag). `a3_bandit` meets the registered criteria only formally: it
  has more unnecessary handovers than tuned A3 on every card (+1.644 per UE-minute on the training card) and
  1.65 to 4.15 times its ping-pong on three test cards. `a3_pred` does not generalise (the gain is lost on
  `urban-macro-tr37885-4ghz`, and it cannot run at the 0.2 s measurement period of `ns3-urban-3.5ghz`). Limits
  of the design: with 5 seeds the no-harm criterion cannot fail (smallest Wilcoxon p 0.0625), and
  `fr3-urban-15ghz` is the least independent test card.

### Documentation

- The failure level is now stated precisely everywhere it was called "not calibrated" (README, scenario cards,
  `docs/comparison.md`, `docs/verification.md`, the user guide and the guides): the ns-3
  comparison setting passed the pre-registered checks on one fresh set of ns-3 runs (V1, TTT 80 and 320 ms:
  level 0.97, rank 0.88) (withdrawn in 2.6.0: wrong run length; see Corrected)
  and failed the level on another (N3: 0.47, because of its TTT 640 ms cells); the
  default link-monitoring model gives a third to a sixth of ns-3's level (0.33 on V1, 0.16 on N3) (corrected
  in 2.6.0). Scenario pages regenerated.
- The learning-rule and AI/ML-mobility guides: the generalisation results of V2.
- README, `CITATION.cff` and `.zenodo.json` describe HandoverLab as a reproducible system-level simulator for
  studying and comparing handover algorithms and procedures in 5G-Advanced, beyond-5G and some NTN scenarios,
  with explicit models, optional features and a documented validation scope.
- Citation with the DOI of 2.4.2 (10.5281/zenodo.23589215).
- Command-line reference: `verify --ns3-comparison`. Dashboard screenshots retaken with this version.

## [2.4.2] - 2026-10-23

No change of results.

### Added

- A picture for every option, each drawn from a real run by its own script in `tools/`: the handover
  procedures side by side (`procedures.png`), mobility robustness optimisation (`mro.png`), fast fading
  (`fading.png`), the slot scheduler with the Numba timings (`scheduler.png`), buffers at handover
  (`buffers.png`), dual connectivity (`dual-connectivity.png`), UE receive beams (`ue-beams.png`) and the
  traffic models (`traffic.png`); shown in the README and in each guide.
- `tools/make_dashboard_screenshots.py`: the dashboard screenshots taken with Edge through the DevTools
  protocol; all four dashboard pictures redone with this version.

### Fixed

- The speed-ups stated for 2.4.0 ("8 to 60" times, "50-80" times the rate model) were not all supported by the
  measurements: `docs/performance.md` gives 23 to 59 times for the Numba scheduler and, measured again for 2.4.2
  on the configuration of the scheduler picture, 42 (round robin) and 93 times (proportional fair), with the
  NumPy scheduler about 91 times the rate model. The README, `docs/comparison.md`, the scheduler and fading guides
  and `docs/performance.md` now give these measured numbers.

### Documentation

- 7 GHz calibration: README, `docs/comparison.md`, `docs/calibration-3gpp.md` and
  `docs/standard-compliance.md` say which cases they count (at 7 GHz 228 percentiles, largest distance
  1.69-2.43 dB; with the two 6 GHz reruns 342 percentiles, 1.65-2.88 dB).
- README model boundaries: the slot scheduler (2.2.0) and the user-plane buffers (2.3.0) listed as options,
  with what is still not modelled.
- Scenario cards `suburban-sma-7ghz`, `rural-700mhz` and `indoor-office-4ghz`: the 7 GHz calibration of 2.4.0
  and the hard-LOS results of `docs/guides/indoor-rural.md`; scenario pages regenerated.
- Examples rerun with this version and their numbers, and where needed their conclusions, updated: the guides
  on buffers, MRO (the faster MRO setting is no better), beams and layers, indoor and rural scenarios, the
  learning rule and fast fading; tutorial 2; the README traffic table; the `status` example in the user guide.
- User guide: all 15 cards, the `a3_pred` rule, `ttt_d2_s`, the layout kinds `indoor` and `ntn`, `run.backend`
  under `run`, `ntn.hpbw_deg` (tabled widths at 2 GHz only), `ntn.los_model` and `radio.vegetation`; the study
  example with a main guard. `docs/index.md`: the current layouts and cards. `docs/stability.md`: the missing
  import. Tutorial 3: the cap of four extensions dates from 2.4.1.
- Citation with the DOI of 2.4.1.

## [2.4.1] - 2026-10-22

No change of results.

### Fixed

- `examples/study_smoke.yaml`: up to four grid extensions (`max_extensions: 4`); with two the example study
  stopped at the `grid_edge` gate under the 3GPP defaults of 2.x.

### Documentation

- README: pictures of the 7 GHz calibration, the new scenario cards and predicted measurements; what is new
  in 2.1.0-2.4.0, the roadmap, the lower-layer options; the citation with the DOI of 2.4.0 and a BibTeX entry.
- `CITATION.cff` and `.zenodo.json`: description and keywords of the current features.
- Tutorials 1, 3 and 4 and the report pictures rerun with 2.4.0; status lines name the current release.

## [2.4.0] - 2026-10-22

### Added

- 7 GHz large-scale calibration (TR 38.901 V19.5.0 clause 7.8.1, Table 7.8-1A) in the `verify` group
  `calibration`: UMa and UMi at 7 GHz, UMa and UMi at 6 GHz with the updated model, and SMa with ISD 1299 m and
  1732 m (35 m sites with a mechanical downtilt of 95 / 92 deg through Eqs. 7.1-7 and 7.1-8, 20 % of the users
  in cars with the car penetration loss, 80 % in residential and commercial buildings over their floors with the
  low-loss A model), compared with the companies of 3GPP R1-2506406 (RAN1 #122; mean and range in
  `verify/data/r1_2506406.csv`). Pre-registered result (30 000 users, seed 1): every percentile 5-95 % lies
  inside the company range (18 of 18 case-metric pairs pass, 342 of 342 percentiles); the largest distance from
  the company mean is 1.65-2.88 dB, so the second criterion (at most 1.5 dB) fails for all six cases. It is
  reported as a note. The checks against R1-165974 are unchanged. `simulate_drops` takes the IRR-glass loss of
  the case's reference when `irr_glass` is not given (unchanged for the old cases).
- Compiled slot scheduler: with `run.backend: numba` (`pip install handoverlab[fast]`) the slots of
  `protocol.scheduler` are played by a compiled loop (`handoverlab.engine._kernels.sched_slots`). The MCS
  look-ups, logarithms and block error probabilities still come from the NumPy functions of the reference loop
  (per-interval tables), and the loop uses only basic arithmetic in the reference order, so every result is
  bit-identical to the NumPy loop (`tests/test_sched_kernel.py`, which also runs the loop's logic as plain Python
  without Numba). On the ns-3 card the engine time with the scheduler drops by a factor of 8 to 60 (case and machine load) (about 3 times the rate model instead of 50-80 times; see `docs/performance.md`). The NumPy loop stays the reference and the default and runs in debug mode.
- UE receive beams as an option of the beam model (`radio.beams.ue_panels` 1, 2 or 4, off by default): UE panels
  of TR 38.802 V14.2.0 Table A.2.1-4 (Config 1: two panels 180 deg apart, Config 2: four at 90 deg; `ue_panel`
  [M, N] = [2, 4] at half a wavelength, one polarisation) with the element of Table A.2.1-8 (model 1, 5 dBi;
  = ITU-R M.2412-0 Table 11), `ue_beams` DFT receive beams per panel over `ue_beam_span_deg`, bearing uniform
  per UE (`ue_orientation: random`) or along the direction of travel (`heading`). Measurements use the best
  receive beam of the best panel (`ue_rx: best`; TS 38.215 5.1.1 receiver branches) or a sweep over the beams,
  one per L1 instant, with the highest of the last samples reported (`sweep`); data, RLM, beam failure
  detection and recovery and the interference use the serving receive beam. The FR2 time scaling of the sweep
  was already in `protocol.meas_periods: ts38133` (Mmeas_period_w/o_gaps = 24, TS 38.133 V19.6.0 9.2.5.1) and is
  not applied twice; `sweep` is refused with `ts38133`. New random stream `ue_beams`. Not combined with
  `protocol.dc`. With the option off every result is unchanged. Guide: `docs/guides/ue-beams.md`.
- AI/ML-based mobility after 3GPP TR 38.744 V19.0.1 (Release 19) as an optional rule, `a3_pred` (NumPy only, off
  unless a run names it): prediction of the L3 cell-level RSRP of a cell from its own past L3 results (RRM
  sub-use case 2), in case A (prediction window ahead; handover on the predicted Event A3, handover model
  option 2 with the preparation started at the report) and case B (measurement skipping with MRRT =
  skip / (skip + 1), L3 filtering options 1-3, Event A3 on the measured-and-predicted series, option 3).
  Predictors: sample and hold (the non-AI baseline of TR 38.744 clause 5.1) and a ridge-regression
  autoregressive model trained on runs of training seeds (`handoverlab.rules.predict.fit_predictor`,
  `collect`, JSON weights), or a user object. Statistics after a run (`PredA3.stats`, `Recorder`): prediction
  accuracy per horizon against the fully measured L3 result, MRRT, and the counters n1, n2, n3 and F1 score of
  the indirect A3 event prediction (clause 5.3.1). With `act: false` and in case B without skipping the rule
  gives the event log of `a3`. `handoverlab verify --only learning` gained four checks (P1-P4). Guide
  `docs/guides/ai-mobility.md` with the evaluation against TR 38.744 and what is not modelled (RLF
  prediction, frequency- and spatial-domain prediction, beam-level prediction, option 1, LCM); compliance rows
  in `docs/standard-compliance.md`. Pre-registered evaluation (FR1 case B, FR2 case A): ridge more accurate
  than sample and hold, errors rising with speed, PW and MRRT as TR 38.744 observes; MRRT 50 % costs
  +0.7-0.9 percentage points of HOF rate; option 2 cuts the HOF rate from 2.4 % to 0.3 % but with 55 % more
  attempts and three times the ping-pongs, and sample and hold does the same; generalization criterion G2
  failed. Every existing result is unchanged.

### Documentation

- `docs/comparison.md`: HandoverLab next to ns-3 with 5G-LENA and the mmWave module, Simu5G, the Vienna 5G System
  Level Simulator, the MATLAB 5G Toolbox, OpenAirInterface and Sionna on the points that matter for handover
  studies (A3, CHO, DAPS, LTM, radio-link failure, dual connectivity, NTN, beams, fast fading and link-to-system
  mapping, scheduler, speed and scale, licence, language, last release, validation against 3GPP). Every cell
  about another tool cites its official documentation, repository or paper (accessed 2026-10-22); facts not
  found are marked "not stated"; a section lists where the other tools are stronger.

## [2.3.0] - 2026-10-22

### Added

- User-plane buffers at handover as an option (`protocol.buffers`: `am` or `um`, off by default): one downlink
  bearer per user whose PDCP data wait in a FIFO at the gNB, data forwarding over Xn (`protocol.forwarding`,
  `protocol.xn_delay_s`) for baseline handover, CHO and LTM / CLTM (late forwarding after HANDOVER SUCCESS unless
  `protocol.early_forwarding`) and DAPS (the source keeps sending, copies to the target), re-establishment with
  and without forwarding, the PDCP discard timer of TS 38.331 (`protocol.discard_timer_s`), and with the slot
  scheduler the HARQ data at a MAC reset (lost with RLC UM, re-sent with AM) and TBs lost after the last HARQ
  transmission. Sources: TS 38.300 V19.4.0 9.2.3.1-9.2.3.7, TS 38.322 V19.2.0 4.4 / 5.1.2, TS 38.323 V19.1.0
  5.1.2 / 5.3 / 5.5. New metrics `pdcp_delivered_kbyte_pm`, `pdcp_lost_*`, `pdcp_forwarded_*`, `pdcp_delay_ms`,
  `pdcp_delay_p95_ms`, `pdcp_delay_forwarded_ms` (0 without the option). Base engine only. With the option off
  every result is unchanged. Guide: `docs/guides/buffers.md`.
- Suburban macro (SMa) of TR 38.901 V19.5.0 (`radio.pathloss: sma`, 0.5-37 GHz): the LOS and NLOS path loss of
  Table 7.4.1-1 (h = 10 m, W = 10 m; the NLOS row is used as printed, without a max() with the LOS loss, so for a
  UT high up close to a site NLOS can lie below LOS) and the LOS probability of Table 7.4.2-1 with the vegetation
  density `radio.vegetation` (0, 0.1, 0.2); heights checked against the applicability ranges (25-35 m, 1-14 m).
- O2I building penetration loss of indoor users (TR 38.901 clause 7.4.3.1): a speed group with `indoor: true`
  marks indoor users; each gets PL_tw + 0.5 d2D-in + N(0, sigma_P^2) on all its links, drawn once
  (`radio.o2i_model`: `low`, `high`, `low_a` for SMa, or `mixed`; `radio.o2i_d_in_max_m`; SMa residential /
  commercial buildings 90 % / 10 %), from its own random stream; an indoor user gets no car penetration loss.
  The LOS state and the shadowing of an indoor user stay those of its position (stated abstraction, measured by
  `verify`).
- `radio.building_los: false` on the street grid: sites above the rooftops, the LOS state from the LOS probability
  alone (TR 37.885 clause 6.2.1); `radio.env_height_m`: one effective environment height for the UMa / UMi
  breakpoint (TR 37.885: 0.25 m).
- Scenario cards `urban-macro-tr37885-4ghz` (the TR 37.885 urban grid below 6 GHz with 500 m macro sites on the
  hexagonal layout of TR 36.885 Figure A.1.3-1, UMa at 4 GHz, h_E 0.25 m, vehicles at 60 km/h; the wrap-around is
  replaced by the lattice sites within 1000 m of the grid) and `suburban-sma-7ghz` (11 SMa sites at 1299 m,
  7 GHz, 80 % indoor users with the low-loss A model, 20 % in cars). Guide: `docs/guides/suburban-o2i.md`.
- Optional `verify` group `scenarios` (`--only scenarios`; criteria fixed before the first run), reported as it
  came: 7 pass, 3 fail. The urban macro coupling gain lies 0.3-1.2 dB below an independent computation around
  the median in every block of seeds (cause open; the LOS share close to the sites is a little low); the check
  of the outdoor SMa users fails on sampling noise (40 seeds pooled: within 0.54 dB); a TR-exact treatment of
  indoor users (LOS at d2D-out, O2I shadowing 8 dB) gives a 2.0 dB wider upper tail (95 % point) than the
  simulator's abstraction, with the median within 0.1 dB.
- Scenario card `hst-fr2-28ghz`: the FR2 high-speed train of TR 38.854 V18.0.0 as its system-level mobility
  study sets it up (Table 6.3.8.1-1): one train with one roof-mounted CPE at 350 km/h on a straight track, an RRH
  every 700 m on one side, 10 m from the track (Scenario-A), one panel of 8 x 8 elements with one SSB beam per RRH
  pointing along the track at the next RRH, every RRH its own cell (L3 handover, no DPS), 28 GHz, 50 MHz,
  120 kHz, 31 dBm, TR 38.901 RMa LOS only, no inter-cell interference, N310 = N311 = 2 and the TS 38.133
  measurement periods of the legacy requirements (480 ms). Guide: `docs/guides/high-speed-train.md`, with the
  pre-registered comparison against the TR's results.
- `radio.beams.am_db`: A_m of the TR 38.901 Table 7.3-1 element pattern (default 30 dB, unchanged results); a
  larger value lowers the back lobe, as the antenna "without back lobe" of the TR 38.854 mobility study.
- Dual connectivity as an option (`protocol.dc`, off by default): NR-DC of TS 37.340 V19.3.0 with the master cell
  group on the scenario's other carriers and a secondary cell group (one PSCell) on the cells of one layer of
  `radio.layers`: SN addition on event A4 (clause 10.2), PSCell change on event A3 (clauses 10.5, 10.6) and SN
  release (clause 10.4), each prepared between the nodes and sent over the MCG, random access on the PSCell under
  T304; separate radio-link monitoring and SCG radio-link failure (TS 38.331 5.3.10.3); SCG failures reported to
  the MN, which releases the SCG (clause 7.7); an MCG failure releases the SCG (TS 38.331 5.3.7.2); at an MCG
  handover the SN is kept or released (`on_mcg_ho`, clause 10.7). The MCG behaves exactly as without the SCG.
  New metrics `sn_additions_pm`, `sn_addition_failures_pm`, `pscell_changes_pm`, `pscell_change_failures_pm`,
  `sn_releases_pm`, `scg_rlf_pm`, `scg_failures_pm`, `scg_released_by_mcg_pm`, `scg_time_share`,
  `scg_rate_mbps`, `pscell_change_interruption_s_pm`, `dc_rrc_messages_pm` (zero without the option). Guide:
  `docs/guides/dual-connectivity.md`, with what is left out.

### Documentation

- Fresh held-out check N3 of the failure model on 40 new ns-3 runs, limits fixed before the runs: a fixed
  link-monitoring interferer load (`protocol.lm_load` 0.15, chosen on the earlier runs) raises the failure level
  from 0.16 to 0.47 of ns-3's and the failure order from 0.78 to 0.95; the level check (0.67-1.5) fails, so the
  setting is reported, not adopted. The recovery time after a failure is set against the bounds of TS 38.133
  clause 6.2.1.2.1 (about 0.28-1.55 s), which the default 1.0 s meets. `docs/calibration.md`.

### Not done

- The 7 GHz large-scale calibration of TR 38.901 clause 7.8.1 (Table 7.8-1A): the TR gives the results only by
  reference to R1-2506406, which this release does not include.

## [2.2.0] - 2026-10-22

### Added

- Fast fading as an option (`radio.fast_fading`: `tdl-a` .. `tdl-e`, off by default): the tapped delay line
  models of TR 38.901 V19.5.0 clause 7.7.2 with the delay scaling of Eq. 7.7-1 (`radio.delay_spread_ns`, 100 ns
  by default) and the K-factor change of clause 7.7.6 (`radio.fading_k_db`); each user-cell link fades on its own
  with 32 sinusoids per Rayleigh tap (Jakes spectrum, f_D from the user's speed) and the LOS tap of TDL-D / -E at
  0.7 f_D. Link-to-system mapping (`handoverlab.channel.l2s`): radio-link monitoring compares the MIESM effective
  SINR of QPSK over the 24 PRBs of the hypothetical PDCCH (TS 38.133 Tables 8.1.2.1-1/-2) with Qout / Qin, and
  the rate uses the capacity-equivalent SINR over the carrier. Base engine only in this version. With the option
  off every result is unchanged. Guide: `docs/guides/fading.md`; `verify` group `fading` (criteria fixed before
  the model was written; 32 sinusoids instead of 16 after the Rayleigh test failed with 16).
- Slot scheduler as an option (`protocol.scheduler`: `rr` or `pf`, off by default): every slot of the interval is
  played (slot length of TS 38.211 Table 4.3.2-1), the free PRBs of a cell go to its users with data, the MCS is
  the highest of TS 38.214 Table 5.1.3.1-1 with a block-error probability of at most 10 % at the reported SINR,
  the TBS follows TS 38.214 clause 5.1.3.2, and HARQ runs with 8 processes per user, chase combining and at most
  `protocol.harq_max_tx` transmissions after `protocol.harq_rtt_slots`. The block-error probability is the normal
  approximation of the finite-blocklength error probability on the BICM bit channel of the modulation
  (`handoverlab.linklevel`), with an implementation loss `protocol.l2s_loss_db`. Base engine only; about 45
  times slower than the rate model. Guide: `docs/guides/scheduler.md`.
- `benchmarks/ns3/run_benchmark.py --fading`: the ns-3 runs with ns-3's TR 38.901 fast fading.

### Documentation

- Fast fading against ns-3 runs with fading (96 runs, criterion fixed before the runs): `tdl-c` passes
  (handover ratio 1.04, unnecessary-handover ratio 1.24, ranks 0.97 / 0.98); `docs/guides/fading.md`.
- Held-out check of the failure-model parts on 40 new ns-3 runs, limits fixed before the runs: execution time
  passes; the load effect on link monitoring and the time without connection after a failure fail; execution
  failures are not measurable (none in ns-3). Reported as is in `docs/calibration.md`.

## [2.1.0] - 2026-10-21

A clause-by-clause audit of the protocol engine against TS 38.331 V18.11.0, TS 38.133, TS 38.300 V18.11.0 and
TS 38.321, of the value domains against the ASN.1 of TS 38.331, and of the large-scale channel and the scenario
cards against TR 38.901 V19.5.0, TR 37.885 V15.3.0, TR 38.811 V15.4.0, TR 38.821 V16.2.0 and ITU-R M.2412-0.
Every change that alters results sits behind a switch: `protocol.rrc_detail: simple` and
`radio.channel_detail: simple` (both now in `handoverlab.stability.LEGACY_1X`) and the card values of
`handoverlab.stability.LEGACY_CARDS` give the 2.0.0 model back, and the 1.x golden fingerprints are still
reproduced. Results of an unchanged configuration differ from 2.0.0 (`MODEL_VERSION` 3; new golden
fingerprints in `verify/data/golden.json`).

### Added

- `protocol.rrc_detail` (`3gpp`, the default, or `simple`, the engine of 2.0.0). With `3gpp`:
  - out-of-sync and in-sync indications every max(10 ms, T_SSB) (TS 38.133 8.1.6); N310 counts consecutive
    out-of-sync indications while T310 is stopped, N311 consecutive in-sync indications while it runs, each reset
    by the other indication (TS 38.331 clause 7.2, 5.3.10.2), in all three engines and the compiled kernel;
  - DAPS: T310 of the source keeps running at the reconfiguration with sync (5.3.5.5.2), the source link is
    monitored during T304 and can fail (5.3.10.1, 5.3.10.3), and the UE falls back to the source only if no
    source RLF was detected (5.3.5.8.3); no DAPS from FR2 to FR2 (TS 38.300 9.2.3.1) and none for NTN (refused,
    16.14.3.2.1);
  - LTM keeps its ltm-Config across a cell switch (5.3.5.18.6) and adds 20 ms of T_LTM-processing on a change of
    frequency range (TS 38.133 6.3.1.3);
  - CHO executes when the time-to-trigger of its condition expires, also between measurement instants, like the
    report of 5.5.4.1 (5.3.5.13.4); CHO with condEventD2 and A3 keeps one state and time-to-trigger per event
    (`ttt_d2_s`), updated at every measurement and reset on release; a recovery into a prepared cell is a
    reconfiguration with sync and re-establishes if the cell cannot be joined before T304 expires (5.3.7.3);
  - L3 filter with the intra-frequency L1 period of the frequency range as reference period (5.5.3.2),
    Qout_LR = Qout + 4 dB for beam failure detection (TS 38.133 Tables 8.5.2.1-1 and 8.1.2.1-1), the RLM set
    N_RLM, the BFD timer reset only after it expired, and L1-RSRP with N = 8 in FR2 (9.5.4.1);
  - the RRC messages counted one by one: measurement reports, commands (an LTM cell switch is a MAC CE),
    configurations once per user, Complete messages and releases.
- Outcome `coverage` and metric `coverage_failures_pm`: a failure after which the UE re-establishes in its
  serving (or target) cell is neither too early nor too late. The outcome classes follow TS 38.300 15.5.2.2.2
  (too early: re-establishment in the source; wrong cell: in a cell other than source and target; too late: a
  failure before a handover, re-establishment elsewhere), one class per failure; `too_late_pm` counts the classes.
- `handoverlab.standard`: the value domains of TS 38.331 V18.11.0 (TimeToTrigger, Hysteresis,
  MeasTriggerQuantityOffset, Q-OffsetRange, FilterCoefficient, ReportInterval, RLF timers and constants, t304,
  SSB periodicity, RSRP-Range, maxNrofCondCells, the D2 distance steps) with the clause or page of each, and
  `check_rule` / `check_scenario`; the `verify` group `values` checks every built-in card and rule default;
  studies have a gate `standard_values` (blocking by default), and grid extensions stay on standard values.
- `radio.channel_detail` (`3gpp`, the default, or `simple`): with `3gpp` the place-tied shadowing and LOS
  fields have the exponential autocorrelation exp(-d / d_cor) of TR 38.901 Eq. (7.4-5) (circulant embedding,
  periodic with the highway wrap-around), the shadowing is uncorrelated between sites (clause 7.5 step 4),
  UMa has C'(h_UT) in the LOS probability and the random effective environment height of Table 7.4.1-1
  note 1 (h_UT >= 13 m), antenna heights outside the applicability ranges of Table 7.4.1-1 are refused,
  links beyond the upper distance bound give a warning, and a co-sited layer must keep the LOS-state and
  shadowing settings of the first layer (clause 7.6.5).
- `radio.pathloss: inh_office_open` (the open-office LOS probability); mobility profiles `p3`, `v30`, `v120`
  (the fixed speeds of ITU-R M.2412-0 Tables 5a-5c) and `v140c`, `v70c` (TR 37.885 highway speeds on the lane
  centre); `ntn.hpbw_deg` (unset: the tabled 3 dB beamwidth of TR 38.821 Tables 6.1.1.1-1/-2, from which the
  beam spacing of Table 6.1.1.1-4 is computed) and `ntn.los_model` (`los`: the baseline "Clear Sky, Line of
  sight" of TR 38.821 Table 6.1.1.1-5); `handoverlab.stability.LEGACY_CARDS`; the IRR-glass loss as a
  parameter of the calibration module.
- `benchmarks/ns3/`: the ns-3 / 5G-LENA side of the comparison as a package anyone can rerun: the A3-only ns-3
  program of the reference scenario (`handoverlab-ns3-a3.cc`, GPL-2.0-only like ns-3, outside the Python
  package), `run_benchmark.py` for parts A, B and C (resumable, parallel) and the library state of the
  reference runs; `handoverlab verify --ns3 --ns3-reference FILE` compares HandoverLab with such a file.
- "Model boundaries" and "Scope: 5G-Advanced and beyond 5G" in the README, with a test that keeps the table in
  step with the registered rules, cards and layouts.
- The page "The 10 ms step" (`docs/time-step.md`): 10, 5, 2 and 1 ms on two scenarios and four procedures, with
  criteria fixed before the runs; all 30 met, the metrics identical seed by seed.
- The reference study (`examples/study_reference.yaml`, `docs/reference-study.md`): CHO against A3 at an equal
  failure budget. The confirmatory question is not answered: the study gates stopped it, as CHO meets the budget
  at every setting up to 8 dB and 960 ms; an exploratory test stage shows the price (-90 % unnecessary
  handovers, but 12 dB lower SINR and 25 % lower throughput).

### Changed

- `radio.shadow_site_corr` is unset by default (0 with `channel_detail: 3gpp`, 0.5 with `simple`).
- Cards: UE antenna 1.6 m (TR 37.885 vehicle type 2) on `smoke`, `urban-grid-10ghz`, `fr3-urban-15ghz`,
  `urban-grid-28ghz-beams`; `indoor-office-4ghz` with `p3` and the open-office LOS probability;
  `rural-700mhz` with `v120`; `dense-urban-2layer` with `v30`; highway cards with `v140c`; `ntn-leo600-2ghz`
  with `ntn.los_model: los`. The card pages leave out keys that the layout and radio model do not read, keep
  the card's own source for beam keys, and the cards state the remaining abstractions (one shadowing
  decorrelation distance, LOS and NLOS on one shadowing realisation, LOS state on top of the buildings, user
  numbers, scintillation as a link-budget margin, no wrap-around beam tiers).
- `verify`: radio statistics expect the exponential correlation and no correlation between sites; highway
  check H3 uses the uncorrelated shadowing of TR 38.901 and simulates it along each vehicle's path (the
  place-tied exponential field leaves too few independent samples per road), H2 accepts a jump at the
  wrap-around up to the size of the ordinary steps (the radio map has a whole number of pixels per period);
  NTN check N2 checks the tabled beamwidth (it passes now for both S-band apertures).
- `a3_mro`: `step_db` 1 dB by default (0.5 dB before), so that every offset is a Q-OffsetRange value; a
  ping-pong must be strictly shorter than `pingpong_s`, and no ping-pong is counted across a re-establishment.
- Validation: `ssb_avg` at most min(`n_ssb`, 16) (maxNrofSS-BlocksToAverage); FR2-2 power classes 1 to 3;
  T310, delays and the report interval must not be negative; with `rrc_detail: 3gpp` and TS 38.133 measurement
  periods on several carriers, `protocol.gap_pattern` must be one of the per-UE gap ids that TS 38.133 Table
  9.1.2-3 allows for the frequency ranges (FR1 present: 0-11, 24, 25; FR2 only: 12-25).
- Energy: each cell counts with the transmit power of its own layer (2.0.0: the base layer's power for every
  cell), the metric is per cell, and the EARTH model has the number of transceivers of Auer et al. 2011 Eq. 1
  (`radio.energy_ntrx`, 2 for the micro base station of Table 2; 1.x and 2.0.0: 1, now in `LEGACY_1X`).
- SS-RSRP per resource element with beams or layers: the power is spread over the 12 N_RB subcarriers of
  TS 38.101-1 / TS 38.101-2 Table 5.3.2-1 (`radio.channel_detail: 3gpp`; 2.0.0: B / SCS, guard bands included).
- The title is "System-level handover simulator for 5G-Advanced and beyond-5G research" (README, PyPI, CITATION,
  Zenodo, documentation site).

### Fixed

- Citations checked against the text of each document: FTP model 3 is defined in TR 36.872 Annex A.1 with the
  0.5 Mbyte files of TR 38.802 Table A.2.1-1 and TR 38.821 Table 6.1.1.1-7 (TR 36.814 has models 1 and 2 only);
  `protocol.reest_s` (1 s) is an assumption: TS 38.133 6.2.1.2.1 bounds the re-establishment delay by 50 ms +
  cell identification (Table 6.2.1.2.1-1) + system information + PRACH, and TR 36.842 Table E.1-2 uses 250 ms;
  MRO cites TS 28.313 clause 7.1.2; hand-calculated radio checks use c = 3e8 m/s; rows of
  `docs/standard-compliance.md`, the user guide and the guides rewritten where the text said otherwise.
- Every citation of TS 38.133, TS 38.300, TS 38.321, TS 38.213 and TS 38.215 checked against the V19 texts (and
  the versions named): no DAPS from FR2 to FR2 is TS 38.300 9.2.3.1 (not 9.2.3.2); recovery into a CHO candidate
  9.2.3.1 and 9.2.7 (not 9.2.3.4); M_meas_period_w/o_gaps TS 38.133 9.2.5.1; the BFD threshold in the user
  guide is Qout_LR; the restart of link monitoring on a new cell is called what it is, an interpretation of
  TS 38.133 8.1.2.2; the SSB as BFD reference signal cites TS 38.133 8.5.1; conditional LTM cites TS 38.300
  V19.4.0 9.2.3.7.
- The verify check of the configured LTM / DAPS interruption (V1e) runs with ideal random access, so that an
  execution waiting for its target under T304 does not count against it; the README table of model boundaries is
  checked against the built-in rules only.

## [2.0.0] - 2026-10-20

2.0.0 makes the 3GPP values the defaults. Results of an unchanged configuration therefore differ from 1.x;
`handoverlab.stability.LEGACY_1X` (plus `mobility.profile: veh16` on the urban-grid cards) gives the 1.x
results back bit for bit. See [moving from 1.x to 2.0](docs/migration-2.0.md).

### Added

- Non-terrestrial networks (roadmap item 20): `layout.kind: ntn` with one LEO satellite on a circular orbit
  and earth-moving beams, after TR 38.811 V15.4.0 (Earth radius, Bessel antenna pattern, LOS probability per
  elevation, free-space loss on the slant range, shadowing and clutter loss, atmospheric loss over the
  elevation, scintillation) and TR 38.821 V16.2.0 (LEO-600 Set-1 S band: 2 m aperture, 34 dBW/MHz; handheld
  UE; 19 beams on the UV plane, reuse 1; 7.56 km/s; round-trip delay 25.77 ms of scenario C2). The new
  configuration section `ntn` and the card `ntn-leo600-2ghz`.
- The rule `cho_d2`: conditional handover with condEventD2 of TS 38.331 V18 5.5.4.15a (moving reference
  locations, the beam centres on the ground) together with A3; on fixed cells it is Event D1.
- `ConditionalRule.exec_condition` (a rule may add its own execution condition) and `RuleContext.cell_center`.
- The optional `verify` group `ntn` (N1-N3, below) and the section `fingerprints-1x` of the group
  `fingerprints`: every golden run of 1.12.0 repeated with `LEGACY_1X`.
- `radio.breakpoint_c_mps` and `radio.pl_min_distance_m`, the mobility profile `v60`.
- The guides "A LEO satellite (NTN)" and "Moving from 1.x to 2.0", the API page of `handoverlab.channel.ntn`,
  pictures of the highway, a radio map and the satellite beams in the README.

### Changed (breaking: results differ from 1.x)

- The speed of light in the breakpoint distances of TR 38.901 is 3.0e8 m/s (Table 7.4.1-1, notes 1 and 5);
  1.x: 299 792 458 m/s.
- The RMa, UMa and UMi path loss is evaluated at a 2D distance of at least 10 m, the lower end of its
  applicability range in Table 7.4.1-1 (InH not limited); 1.x: no limit.
- The default mobility profile is `v60`: every vehicle at 60 km/h in one of two lanes of 3.5 m (TR 37.885
  clause 6.1.2 option A, Table A-1); 1.x: `veh16`. The cards `smoke`, `urban-grid-10ghz`, `fr3-urban-15ghz`,
  `urban-grid-28ghz-beams` and `open-area-10ghz` use it.
- The 3GPP protocol profile of 1.9.0 is the default: `protocol.cmd_during_t310: receive`, `t304_s: 1.0`,
  `rlm_holdoff_s: 0.2` (TS 38.331 5.3.5.5.2 and 5.3.5.8.3, TS 38.133 clause 8.1); 1.x: `lost`, none, 0.
- With `cmd_during_t310: receive` a CHO (or LTM) candidate configuration that arrives while T310 runs is
  received like a handover command, at the first step with the link at or above Qout, and T310 goes on
  (TS 38.331 5.3.5.13 sets no condition on T310); up to 1.12.0 it was lost even with the 3GPP profile. The
  check "CHO with immediate execution = A3" now also holds with the 2.0.0 defaults. With `lost` nothing
  changes.
- The 3GPP calibration (`verify` group `calibration`) uses c = 3.0e8 m/s like the simulator; its result is
  unchanged (325 of 342 percentiles in the full run).
- `MODEL_VERSION` is 2: studies of 1.x run their jobs again. New golden fingerprints (17 cases, 35 runs,
  among them the highway and the satellite).

### Fixed

- With `protocol.t304_s`, every step that T304 kept an execution going counted as interruption also for DAPS
  handover, whose source link carries the data meanwhile (1.9.0-1.12.0, only with the 3GPP profile; the event
  logs are unchanged, only `interruption_*` metrics of DAPS are lower). `verify` check V1e now passes with the
  2.0.0 defaults.

### Removed

- The scenario card `highway-10ghz`, deprecated in 1.11.0; use `highway-tr37885-4ghz` or
  `highway-tr37885-30ghz`.

### Results (plan fixed before the runs)

- `LEGACY_1X` reproduces all 33 golden runs of 1.12.0 bit for bit.
- N1: slant range, free-space and atmospheric loss and CNR of the 8 S-band LEO cases of TR 38.821
  Table 6.1.3.3-1 within 0.1 dB: passed, largest difference 0.028 dB.
- N2: 3 dB beamwidth of the Bessel pattern within 0.01 degree of Tables 6.1.1.1-1/-2: **failed** for the
  1 m aperture (8.8462 against 8.8320 degrees; 2 m: 4.4198 against 4.4127); both are 0.16 % wider than the
  tables. Reported as is; the group `ntn` runs on request only.
- N3: 7562 m/s at 600 km (7.56 km/s), nadir footprint 46.3 km (50 km, informative): passed.
- The default distance thresholds of `cho_d2` (25 km, half the 50 km beam diameter of TR 38.821) replaced a
  first guess (20/15 km) after one run had been seen; no further tuning.

## [1.12.0] - 2026-10-20

### Added

- Radio maps from a file (roadmap item 17), after the map-based hybrid channel model of TR 38.901
  V19.5.0 clause 8: `radio.map_file` gives the path gain of every site and pixel (dB, without transmit
  power and antenna gains) in place of path loss, LOS state and place-tied shadowing; the map is static.
  `radio.map_sha256` is filled when the scenario is loaded, so the content of the file is part of the job
  IDs, and a run refuses a file that has changed. Not combined with `radio.layers` or `layout.wrap`.
- `handoverlab.mapfile`: the file format (`.npz`, `"handoverlab-radiomap"` version 1), `save_map`,
  `load_map`, `export_map` (the map of a street-grid world), `map_from_raster` (e.g. a ray tracer's
  path-gain map) and `map_from_points` (measurements, linear interpolation, error on held-out points);
  `RadioMap.from_file`.
- The guide "Your own radio map", `examples/radio_map.py`, the API page of `handoverlab.mapfile`.

### Results (plan fixed before the runs)

- Every golden case on the street grid (9 cases, 23 runs) gives the identical event log with its exported
  map.
- 3000 points of the `smoke` map with 1 dB measurement error: hold-out error 3.42 dB RMSE (criterion:
  below the 7.82 dB NLOS shadowing), 2.28 dB MAE.

Old golden fingerprints are unchanged.

## [1.11.0] - 2026-10-20

### Added

- The highway of TR 37.885 V15.3.0 as specified for the base-station-to-vehicle link (roadmap item
  11): `layout.wrap` (wrap-around of Table A-1: a vehicle keeps lane and direction and re-enters at
  the other end; distances and angles to the nearest image of every site; the place-tied shadowing is
  periodic along the road), `layout.highway_sites` (`one_side`: TR 36.885 A.1.3 option 1;
  `hex19`: 19 hexagonal sites with the road through the centre site along the cluster translation,
  option 2), `radio.los_model: los` (LOS on every link, Table 6.2.1-2), the speed profiles `v140`
  and `v70` (option A). All off by default.
- Scenario cards `highway-tr37885-4ghz` (below 6 GHz: 2 sites 35 m from the road, 1732 m apart,
  35 m masts, RMa LOS at 4 GHz, 20 MHz, 49 dBm, NF 9 dB) and `highway-tr37885-30ghz` (above 6 GHz:
  19 sites x 3 sectors, ISD 500 m, 25 m masts, UMa LOS at 30 GHz, 200 MHz, 43 dBm, NF 13 dB, SSB
  beams of the 4 x 8 panel tilted to 102 degrees); 140 km/h; every value with its clause.
- `verify` group `highway`: the geometry and link budget of both cards against the TRs, continuity
  of the received power at the wrap-around, the coupling gain to the strongest site against an
  independent computation (percentiles 5-95 within 0.5 dB) and LOS-only links.
- `verify --only learning` (optional, about 20 minutes): `a3_bandit` against an exhaustive search
  over its arms, with three criteria fixed before the run. `BanditA3` keeps a record of its credited
  outcomes and finished epochs (`outcomes`, `epochs`); its decisions are unchanged.
- The rule `dqn` (roadmap item 15): Event A3 whose offset a deep Q-network chooses per user, with
  replay buffer and target network, training and test modes, weights saved and loaded
  (`handoverlab.rules.dqn.train`); PyTorch is optional (`pip install handoverlab[torch]`),
  `import handoverlab` does not need it, and `handoverlab rules` names the missing package.
- `run.backend: numba` (roadmap item 16): a compiled kernel of the step loop (serving SINR,
  Qout / Qin filters, T310) with bit-identical results, optional (`pip install handoverlab[fast]`);
  the backend is not part of the job IDs. The NumPy path stays the reference.
- Per-layer shadowing keys of `radio.layers` (`shadow_los_db`, `shadow_nlos_db`,
  `shadow_decorr_m`, `los_corr_m`; unset: those of `radio`), left out of `to_dict` while unset.
- `scenario_names(deprecated=False)`; `Layout.offsets`, `Layout.distances`, `Layout.wrap_x`,
  `Layout.nearest_image`; `layout.highway_hex`.
- CI job with the optional extras (Numba, PyTorch CPU).

### Changed

- Scenario cards corrected against the texts (their results change; their job IDs change with them):
  `dense-urban-2layer` (UMa shadowing 4 / 6 dB and 50 m on the macro layer and UMi 4 / 7.82 dB and
  13 m on the micro layer, TR 38.901 Tables 7.4.1-1 and 7.5-6; car penetration loss 9 dB, 5 dB,
  M.2412-0 Annex 1 clause 3.3; minimum BS-UT distance 35 m, Table 7.2-1) and
  `urban-grid-28ghz-beams` (UE noise figure 10 dB, M.2412-0 Table 5b). Citations corrected on
  `indoor-office-4ghz`, `urban-grid-28ghz-beams`, `fr3-urban-15ghz` and in the default sources;
  the assumptions of the urban-grid cards (small cells on UMi, 52-63 km/h, no 10 m minimum
  distance) are stated on the cards.

### Fixed

- Baseline and DAPS handover attempts now carry the rule's `memory_key` into
  `OutcomeRecord.key`, as the rule interface describes; until 1.10.0 only conditional handover
  passed it on (baseline attempts came back with -1). No built-in rule uses the key, so no result
  changes.

### Deprecated

- The scenario card `highway-10ghz`: it combined the roadside offset of TR 36.885 option 1 with
  the spacing of option 2, used 10 GHz and had neither the LOS-only links nor the wrap-around of
  TR 37.885. It loads with a `HandoverLabDeprecationWarning`, is no longer listed, and is removed
  in 2.0.0.

### Results (plans fixed before the runs)

- Highway: all eight checks pass; the coupling gain agrees with the independent computation within
  +0.42 dB (4 GHz card) and -0.35 dB (30 GHz card); the largest jump at the wrap-around is
  0.05-0.09 dB.
- Bandit: the exhaustive search finds the largest arm (5 dB) best, with the reward still rising;
  criterion B1 (at least 0.6 of the second-half epochs on the best arm or a neighbour) **failed**
  with 0.57 (chance 0.4); B2 and B3 passed (0.503 against 0.471, 0.543 against 0.452). Reported as
  is; the rule was not changed.
- Numba: all 30 golden runs bit-identical; engine time 0.66 (reference job, batched), 0.85 (one
  engine) and 0.90 (8 rules on smoke) of the NumPy time, less than the factor of two to three hoped for.
- TR 38.901 V19.5.0 checked against V17.0.0: the path loss, LOS probabilities and shadowing used
  here are unchanged.

Old golden fingerprints are unchanged; new ones for the two highway cards.

## [1.10.0] - 2026-10-20

### Added

- SSB beams, beam management and beam failure recovery (roadmap item 18), as the option
  `radio.beams`: sectors per site, each a panel with the element of TR 38.901 Table 7.3-1 and DFT
  weights (Eq. 7.3-1) sending up to L_max SSB beams; beam-level L1-RSRP and the cell quality of
  TS 38.331 5.5.3.3; the serving beam (TCI state) from periodic beam reports; beam failure
  detection (all BFD-RS below Qout_LR over the evaluation period of TS 38.133 Tables 8.5.2.2-1/-2,
  indications every max(2 ms, T_SSB), BFI_COUNTER with beamFailureInstanceMaxCount and
  beamFailureDetectionTimer, TS 38.321 5.17) and recovery by random access (contention-free on a
  candidate above rsrp-ThresholdSSB while beamFailureRecoveryTimer runs, else contention-based;
  preambleTransMax failed attempts = radio-link failure, TS 38.331 5.3.10.3); radio-link monitoring
  on the serving beam or on the N_RLM best beams (up to 8 in FR2, TS 38.133 Table 8.1.1-2). Beam
  failure recovery and T310 run side by side (the coupling is not specified).
- Several carriers (roadmap item 19), as the option `radio.layers`: further layers with their own
  sites or co-sited with the first layer (same LOS states, shadowing and blockers, TR 38.901
  7.6.5), interference only within a carrier, SS-RSRP per resource element; the measurement
  periods of TS 38.133 as the option `protocol.meas_periods: ts38133` (intra-frequency Tables
  9.2.5.2-1/-2, inter-frequency within the gaps of `protocol.gap_pattern`, Tables 9.1.2-1 and
  9.3.5-1/-2, L3 filter adapted to the input rate, no data during a gap); the RLM evaluation
  periods of TS 38.133 Tables 8.1.2.2-1/-2 as `protocol.rlm_eval: ts38133`; the rule `a3a5`
  (Event A3 within a carrier, Event A5 towards another, thresholds per direction).
- External validation of DAPS and LTM (roadmap item 10): `handoverlab.requirements` (TS 38.133
  formulas, including D_LTM of 6.3.1 and the DAPS interruptions of 6.1.3) and checks of the
  interruption values against TS 38.133 and against published 3GPP evaluations (RAN1 R1-2007151,
  RAN2 R2-2207806, R2-2209256, R2-2206982, R2-2208200, R2-1907308, R2-1901361, TR 36.881).
- New metrics `beam_switches_pm`, `beam_failures_pm`, `beam_recoveries_pm`,
  `beam_recovery_failures_pm`, `beam_recovery_s_pm`, `inter_frequency_handovers_pm`, `gap_share`
  (zero without the options); `RuleContext.cell_carrier`; the rule hook `BaselineRule.entering`
  (an event of the rule's own) and time-to-trigger per user and cell.
- Scenario cards `urban-grid-28ghz-beams` (FR2 small cells with beams) and `dense-urban-2layer`
  (ITU-R M.2412 Dense Urban-eMBB, 4 GHz macro + 30 GHz micro); the guide "Beams and several
  carriers"; the figure `docs/images/ssb-beams.png` (`tools/make_beam_figure.py`).
- `verify` group `extended` (antenna, cell quality and TS 38.133 formulas against hand values; the
  new engine without options equals the engine of 1.x; DAPS and LTM against TS 38.133 and the
  published evaluations); golden fingerprints `smoke-beams`, `smoke-2layer`, `smoke-38133`.

### Results (plans fixed before the runs; every number in docs/standard-compliance.md)

- DAPS and LTM: the LTM interruption (20 ms) equals TS 38.133 6.3.1 for a known cell and TCI state
  with RACH-less execution, the DAPS interruption (0 ms) is within the 2-3 ms of TS 38.133 6.1.3,
  and all values lie in the bands around the published 3GPP evaluations; the L3 execution
  interruption of 40 ms is below every published value (45.5-120 ms), i.e. optimistic.
- Three sectors per site (instead of one cell per site) bring the mid-band handover counts of the
  1.9.0 comparison with commercial networks into the measured range (walking 2.44 handovers per
  UE-minute, measured 4.84, band from 2.42; driving 13.4 s between handovers, measured 9.2 s),
  while the ping-pong of the AT&T A3 setting (4.6 %, measured 15.5 %) and the failures per
  handover (0 %, measured 0.04-1.5 %) fall out of their bands.
- A two-layer ITU-R M.2412 deployment does not explain the counts: with the operators' A5
  settings the users alternate between the layers or hand over too often when driving (1.0 s and
  3.8 s between handovers); the macro layer with three sectors alone is inside the band (7.2 s
  driving, 18.7 s walking).

Without the new options every result and every fingerprint of 1.9.0 is unchanged.

## [1.9.0] - 2026-10-19

### Added

- Handover command and execution as TS 38.331 specifies them, as options (the defaults keep the
  model of 1.x and every fingerprint): `protocol.cmd_during_t310: receive` -- a handover or LTM cell
  switch command that reaches the UE while T310 runs is received at the first step with
  link-monitoring SINR >= Qout and stops T310 (TS 38.331 5.3.5.5.2; the default counts it as lost,
  which is stricter than the TR 36.839 evaluation rule); `protocol.t304_s` -- the execution fails
  only when T304 expires, random access goes on until then (TS 38.331 5.3.5.3, 5.3.5.8.3, 5.3.10.3).
  The 3GPP protocol profile is `{cmd_during_t310: receive, t304_s: 1.0, rlm_holdoff_s: 0.2}`.
- `docs/standard-compliance.md`: every rule of measurement, link monitoring, RLF, handover, CHO,
  DAPS, LTM and conditional LTM, clause by clause against the official texts of Releases 17 to 19
  (TS 38.331, 38.133, 38.300, 38.321, 38.322, 38.213, 38.215, 38.423, TR 36.839, TR 38.901,
  TR 38.913, TR 38.914, ITU-R M.2410/M.2412), with what is followed, abstracted or not modelled;
  the same rules in ns-3 / 5G-LENA; a fresh ns-3 hold-out (48 runs at speeds never used before:
  handover rates and the failure level agree with the 1.3.0 configuration, the order of the
  failure rates does not); and a comparison with handover statistics measured in commercial 5G
  networks (the 3GPP profile brings the handover failure rate from about six times above the
  measured range to just above it).
- Golden fingerprint `smoke-3gpp`.

## [1.8.0] - 2026-10-19

### Added

- Large-scale calibration of the radio model against 3GPP: `handoverlab.verify.calibration`
  reproduces the calibration drop of TR 38.901 clause 7.8.1 (Table 7.8-1: UMa, UMi-Street Canyon
  and the indoor office; three sectors per site with the element of Table 7.3-1 in a ten-element
  tilted array; 80 % indoor users with the O2I loss of clause 7.4.3.1; geographical wrap-around)
  with the propagation formulas of the simulator and compares the CDFs of coupling loss, SINR and
  SIR with the 21 companies of the 3GPP contribution R1-165974 (`verify/data/r1_165974.csv`). At
  6 and 30 GHz, 325 of 342 percentiles lie inside the company range and none is more than about
  1 dB from the industry mean. New `verify` group `calibration`, the page
  `docs/calibration-3gpp.md`, the figure `docs/images/calibration_38901.png`
  (`tools/make_calibration_figure.py`) and a README section.

Results and fingerprints are unchanged: the calibration is a check, not a change of the model.

## [1.7.0] - 2026-10-19

### Added

- Indoor and rural scenarios from TR 38.901. Path-loss models `radio.pathloss: rma` (RMa, LOS with
  its breakpoint and NLOS, default W = 20 m and h = 5 m, 0.5-30 GHz) and `inh_office` (InH-Office,
  LOS probability of the mixed office), each with its LOS probability of Table 7.4.2-1; the layout
  kind `indoor` (the indoor office of Table 7.2-2: a hall of 120 m x 50 m with ceiling sites on a
  rectangular grid); the keys `layout.area_m` (size of the open area or the indoor hall) and
  `layout.min_site_distance_m` (minimum distance of a user's start and waypoints from every site,
  TR 38.901 Table 7.2-3: 35 m for RMa); the
  mobility profiles `ped3` (about 3 km/h) and `veh120` (about 120 km/h). Two scenario cards,
  `indoor-office-4ghz` and `rural-700mhz`, with the link budgets of the IMT-2020 Indoor Hotspot-eMBB
  and Rural-eMBB evaluations (ITU-R M.2412-0 Table 5), and the how-to `docs/guides/indoor-rural.md`.
- The optional soft LOS state of TR 38.901 clause 7.6.3.3 (`radio.soft_los`, `radio.soft_los_d_m`):
  the received power mixes the LOS and NLOS powers with the weights LOS_soft^2 and 1 - LOS_soft^2
  (Eq. 7.6-18 and 7.6-19) instead of switching hard. It uses the random process of the hard state
  and reduces to it for a very steep transition. The two new scenario cards use it.
- `radio.shadow_los_far_db`: shadowing of LOS links beyond the breakpoint (RMa: 6 dB instead of
  4 dB, Table 7.4.1-1).
- Mobility robustness optimisation: the rule `a3_mro` (class `MROA3`). Event A3 with a cell
  individual offset per pair of serving and neighbour cell, moved by a deterministic counter rule
  once per window: earlier after too-late handovers and link failures, later after too-early,
  wrong-cell and ping-pong handovers (the failure classes of TS 38.300 clause 15.5.2; a ping-pong is
  a return to the previous cell within `protocol.pingpong_s`, seen in the serving cell). With
  `step_db: 0` it gives exactly the results of `a3`. How-to: `docs/guides/mro.md`.
- The `pathloss` group of `handoverlab verify` checks RMa, InH, both LOS probabilities and the soft
  LOS weight against values computed by hand. Golden fingerprints `indoor`, `rural`, `rural-hard`,
  `smoke-soft` and `smoke-mro`.

The fingerprints of 1.6.0 are unchanged: the new keys are left out of scenario dictionaries and
job IDs at their default, so the results of every existing scenario and rule stay as they were.

## [1.6.0] - 2026-10-19

### Added

- Conditional LTM, from the Release 19 work on L1/L2-triggered mobility: the rule `cltm` (class
  `CLTM`, base class `CLTMRule`, family `cltm`, event-log kind `cltm`). Candidates are configured
  as for `ltm`; the UE evaluates the L1 switch condition itself and executes at once, without a cell
  switch command, so no command can arrive while T310 runs. The rule keeps the rule contract
  (`handoverlab.testing.check_rule`), and a golden fingerprint `smoke-cltm` guards it. The results
  of every existing rule are unchanged.

## [1.5.0] - 2026-10-19

### Added

- Signalling and energy metrics, derived from counters (the event log and all fingerprints are
  unchanged): `commands_pm`, `rrc_messages_pm` (measurement reports, handover commands, conditional
  configurations, releases and completions of TS 38.331), `l1_measurements_pm` (a proxy for the
  measurement energy of the device), `site_power_w` and `energy_uj_per_bit` (linear EARTH model of
  a micro base station), and the count `n_commands`. The model parameters are
  `radio.energy_p0_w` (56 W) and `radio.energy_slope` (2.6). The definitions are in
  `docs/reference/metrics.md`.
- README: "Built for beyond-5G" and, under "Checked against ns-3", why failure rates differ:
  on the in-car loss and on the time to detect out-of-sync HandoverLab follows the 3GPP texts more
  closely, and on the restart of link monitoring ns-3 did. `docs/calibration.md` opens with the
  same summary.

## [1.4.0] - 2026-10-19

### Added

- Traffic models per user: `traffic.model` with `fixed` (the constant service rates of 1.x, the
  default), `full_buffer`, `periodic` (`traffic.period_s`, `traffic.packet_bytes`) and `ftp3`
  (TR 36.814 FTP model 3: `traffic.ftp_file_bytes`, `traffic.ftp_rate_hz`). Buffered users ask for
  what is in their buffer and the scheduler empties it, so cell load and interference follow the
  traffic. Arrivals come from a new random stream; with the default model, results and
  fingerprints are those of 1.3. Runs with a buffered model are not batched.
- `examples/traffic_models.py`: the same rule under the four traffic models.
- Dashboard: a traffic choice; the tab *Where* (the places of handovers, unnecessary handovers
  and failures); the tab *Compare* (means with 95 % confidence intervals over the seeds and paired
  differences to the first rule, as in the study report); the tab *Study* (the status of a study
  folder); downloads of the comparison (CSV) and of both new figures. Three seeds by default.
  New functions in `handoverlab.gui.logic`: `comparison_rows`, `comparison_figure`,
  `event_points`, `events_map_figure`, `study_status_lines`, `comparison_csv`.
- A golden fingerprint `smoke-ftp3` that runs the optional models of 1.1-1.4 together.
- README: a picture gallery (dashboard, where handovers happen, comparison, study report), a
  sample output, the result of the ns-3 comparison and a short list of what is new.
  `tools/make_readme_images.py` rebuilds the dashboard pictures.
- `docs/calibration.md`: ns-3 detects a radio problem only after 0.65-0.83 s at the control
  traffic of its reference runs, not after 200 ms. This explains its time-to-trigger trend and its
  dependence on the number of users. A setting that meets every part-A limit fails on the
  hold-out sets, so the calibration stops until fresh ns-3 results are available.

## [1.3.0] - 2026-10-18

### Added

- Optional restart of radio-link monitoring on a newly joined cell: `protocol.rlm_holdoff_s`, the
  time after a handover or re-establishment during which no out-of-sync can start T310
  (TS 38.133 clause 8.1: 0.2 s). Off by default; with the defaults, results and fingerprints are
  those of 1.2.
- `docs/calibration.md`: failure-by-failure comparison with ns-3 and the comparison with the
  restart. The speed dependence now agrees, and the ranking limits are met on part A and on both
  hold-out sets. The absolute level and the time-to-trigger trend are not, so failure rates remain
  relative quantities.

## [1.2.0] - 2026-10-18

### Added

- Optional per-user penetration loss on all links, drawn once per user from its own random stream:
  `radio.penetration_db` and `radio.penetration_sd_db` (TR 38.901 clause 7.4.3.2: 9 dB and 5 dB
  for a user in a standard car). Off by default; with the defaults, results and fingerprints are
  those of 1.1.
- `handoverlab.verify.ns3`: `car_loss` and the argument `car` of `scenario_for`, `compare` and
  `holdout`, which apply the in-car loss the way ns-3 does (only at 30-120 km/h).
- `docs/calibration.md`: the cause of the speed dependence of the ns-3 failure rate (ns-3 adds
  the in-car loss only between 30 and 120 km/h), and the comparison with the loss. Without any
  fitted parameter it brings the part-A failure rate to the level of ns-3 (0.38 against 0.43).
  The time-to-trigger trend and the hold-out level still differ, so failure rates remain relative
  quantities.

## [1.1.1] - 2026-10-18

No change to the package code or to any result.

### Added

- Optional extra `dev` (tests, coverage, ruff, pyarrow and the dashboard) for a complete
  development install: `python -m pip install -e ".[dev]"`.
- A test of the ns-3 comparison and hold-out logic that runs without simulating.

### Changed

- The minimum total test coverage checked in CI is 90 % (was 85 %).
- CI also runs the Parquet and dashboard tests on Windows (Python 3.12), so no test is skipped
  there.
- `docs/calibration.md`: the speed dependence of the failure rate, the main open difference to
  ns-3, and a test of the ns-3 out-of-sync counting in HandoverLab (it does not explain it).

### Repository

- Issue forms (bug report, feature request, new handover rule), a pull-request template with the
  checklist, `CODE_OF_CONDUCT.md`, `SECURITY.md` and Dependabot updates of the GitHub Actions.

## [1.1.0] - 2026-10-18

### Added

- Optional link-monitoring model: `protocol.lm_load` and `protocol.lm_load_per_ue` give the
  Qout / Qin filters their own interferer load (a part per user served by the interfering cell, so
  it follows the traffic), and `protocol.exec_can_fail: false` makes the execution always join the
  target. With the defaults, results and fingerprints are those of 1.0.
- The held-back ns-3 / 5G-LENA results are stored with the reference data: part C (the setting
  6 dB / 100 ms with one parameter changed per cell: users, preparation delay, T310, site
  distance, run length, speed), compared together with part B by the new
  `handoverlab.verify.ns3.holdout`. `compare` also reports the time-to-trigger trend of the failure
  rate, and the acceptance limits of a calibrated failure model are fixed in `FAIL_LIMITS`.
- `docs/calibration.md`: the calibration of the new model. It does not meet the limits on the
  hold-out sets, so no calibrated preset is offered and failure rates remain relative quantities.

## [1.0.2] - 2026-10-16

### Added

- The documentation site, <https://mjs19971997.github.io/handoverlab/>, is linked from the
  README, the package metadata (`Documentation`) and `CITATION.cff` (`url`).

### Fixed

- Every link in the README now uses an absolute URL, so the links also work on the PyPI project
  page (in 1.0.1 only the dashboard image did; relative links to the documentation, the examples,
  the changelog and the licence led nowhere there).
- The README installs the dashboard from PyPI (`pip install "handoverlab[gui]"`) in the quick
  start instead of from a source checkout.
- The README badge and `CITATION.cff` use the Zenodo concept DOI 10.5281/zenodo.23409131 (all
  versions, resolves to the latest); the DOIs of versions 1.0.0 and 1.0.1 are listed as well.
- `handoverlab verify --ns3` help: it runs only the ns-3 comparison unless `--only` names groups
  (it said "also").
- The gate message of a reference rule with a single failure says "1 failure", not "1 failures".
- Documentation: the warm-up of the first tutorial is 5 s (not 10 s); the user guide names the
  optional `schema` key, the event kinds `daps` and `ltm`, the trace events `switch` and
  `fallback`, and what `--ns3` runs; a link to the scenario cards that the site could not resolve;
  the Observation fields in the own-rule tutorial include `l1_dbm`; the release steps in
  `CONTRIBUTING.md` (a version tag publishes, a GitHub release archives on Zenodo) and the DOI step
  in `docs/RELEASING.md`; wording in the metric reference, the DAPS/LTM guide and the verification
  page.

### Changed

- The package metadata give the licence as an SPDX expression (`License-Expression: MIT`)
  instead of the licence table and classifier that setuptools deprecates; building from source
  needs setuptools 77 or later (pip fetches it automatically).

Results, fingerprints, job IDs and the public surface are as in 1.0.0.

## [1.0.1] - 2026-10-16

### Fixed

- The dashboard image in the README now uses an absolute URL, so it also shows on the PyPI
  project page.
- README and citation metadata carry the Zenodo DOI of version 1.0.0.

## [1.0.0] - 2026-10-16

First stable release (stages 5 to 8). This section merges the release candidates 1.0.0rc1 to
1.0.0rc4, which were not uploaded to PyPI. From this release on the public surface follows the
stability policy in [docs/stability.md](docs/stability.md). Everything since 0.4.0a1 was added next
to what was there: the defaults, the results of the existing rules and scenarios, the golden
fingerprints and the bh6 regression are unchanged, and the model version stays 1.

### Added

- Schema version of the file formats (`handoverlab.stability.SCHEMA_VERSION`, 1): experiment and
  study files accept a top-level `schema` key, and result JSON files and `study.lock.json` carry
  it. A file without the key is read as schema 1; a file with a newer schema is refused with a
  message that names it. `handoverlab init`, the examples and the dashboard's experiment file
  write `schema: 1`.
- Stability policy (`docs/stability.md`): what the public surface is (configuration keys, result
  columns, metric names, the rule interface, the documented Python names and commands), what a
  major, minor or patch release may change, and how deprecations work.
- `handoverlab.stability`: `RULE_API_VERSION` (1), `METRIC_ALIASES` with `metric_name` (an old
  metric name keeps working with a warning; study files resolve metric names through it),
  `deprecated` and `deprecated_alias` raising `HandoverLabDeprecationWarning` (a `FutureWarning`),
  `check_schema`, and `public_surface`, a snapshot of the public names, rule hooks and record
  fields, metrics, event and trace fields, and configuration keys. A test compares it with
  `tests/data/public_api.json`, so that no part of the surface changes unnoticed.
- How-to guides: add a scenario, run a study on many cores, export event logs and traces, and
  check results against the stored fingerprints.
- CI: a lint job (ruff, plus the release-metadata check) and a minimum total test coverage of
  85 % (90 % at this release) in the Linux / Python 3.12 test job; a scheduled nightly
  workflow that runs the long verification on Linux and Windows and compares the golden
  fingerprints of both systems with each other and with the reference.
- Release plumbing: a workflow that builds the sdist and the wheel, checks them and publishes
  them to PyPI with trusted publishing when a version tag is pushed (or a GitHub release is
  published); `.zenodo.json` for the archived DOI; `tools/release_check.py` (versions, changelog
  and citation metadata agree, tag matches the version); `docs/RELEASING.md` with the steps.
- DAPS handover (Rel-16): rule base class `DAPSRule` (family `daps`, hooks of `BaselineRule`;
  attributes `interruption_s`, `fallback`, `source_data`) and the built-in rule `daps` (`DAPS`).
  The source keeps serving during the execution (interruption `interruption_s`, default 0); an
  execution that cannot join the target falls back to the source if its SINR is at least Qout
  (outcome `too_early`, new event-log cause `daps_fallback`, not a failure). With
  `fallback: false, source_data: false` it equals `a3`.
- L1/L2-triggered mobility (Rel-18): rule base class `LTMRule` (family `ltm`, hooks `prep_offsets`
  and `switch_offsets`; attributes `report_offset_db`, `ttt_prep_s`, `n_max`, `release_hys_db`,
  `stick_db`, `ttt_switch_s`, `cmd_delay_s`, `exec_s`, `recovery`) and the built-in rule `ltm`
  (`LTM`): candidates configured on L3 reports, cell switch decided by the network on unfiltered L1
  measurements, cell switch command with its own delay and loss, short execution, optional recovery
  into a candidate.
- A learning-based example rule `a3_bandit` (`BanditA3`): Event A3 whose offset every cell learns
  with an epsilon-greedy bandit from the outcome labels; NumPy only.
- `Observation.l1_dbm`: the unfiltered L1 samples of the measurement instant (appended field with a
  default, so existing rules and code that builds observations keep working).
- Built-in scenario `fr3-urban-15ghz`: the default grid in the upper mid-band at 15 GHz with a
  400 MHz carrier and 3.5 dB more beam gain, with its scenario card.
- Event-log kinds `daps` and `ltm`; trace events `switch` (LTM cell switch command) and `fallback`
  (DAPS); `serving_cells` returns the source after a fallback.
- `handoverlab.rules.RULE_BASES` and `handoverlab.testing.FAMILIES`; the contract kit and
  `register_rule` accept `DAPSRule` and `LTMRule` rules.
- Documentation: the procedures in the user guide; how-to guides for DAPS and LTM, for using and
  writing a learning-based rule, and for the upper mid-band.
- Tests of the DAPS, LTM and bandit trigger and update logic on prescribed received powers, and
  their contract checks.
- Layout kind `highway`: the straight multi-lane road of the TR 37.885 highway case along the
  x axis, with the new keys `layout.lanes` (lanes per direction, default 3), `layout.lane_width_m`
  (4 m) and `layout.road_length_m` (2000 m); roadside sites every `layout.site_spacing_m` metres,
  `layout.site_offset_m` beyond the road edge, alternately on the two sides; no buildings, LOS
  state and shadowing as in the open area. `handoverlab.layout.highway` builds it.
- Lane-keeping highway mobility: every vehicle keeps its lane and speed and at the end of the road
  turns into the same lane of the other direction; the lateral range of a speed group is the
  displacement from the lane centre (at most half a lane). Mobility profiles `hwy` (70-140 km/h),
  `hwy70` (63-77 km/h) and `hwy140` (126-140 km/h).
- Built-in scenario `highway-10ghz` with its scenario card: 2000 m, 3 + 3 lanes of 4 m, four
  roadside sites every 500 m, 35 m from the road edge, TR 38.901 UMa with 25 m masts, 40 vehicles
  of the profile `hwy`.
- `layout.sites_file`: a CSV file with the columns `x` and `y` that fills `layout.sites` when the
  scenario is loaded (`handoverlab.config.read_sites`), for every layout kind.
- `Scenario.to_dict(full=False)`: keys added after 1.0.0rc2 (`handoverlab.config.LATE_KEYS`) are
  left out while they have their default value, so that result files and the job IDs and locks of
  existing studies stay the same; `full=True` lists every key.
- Documentation: the highway in the user guide, the how-to guide [a highway](docs/guides/highway.md)
  and the scenario card page.
- Tests of the highway geometry, lane keeping, speeds, the turn at the road end, a short run with
  invariant checks, the omitted keys and site files.

### Changed

- Version 1.0.0; development status Production/Stable.
- `CITATION.cff` gives the release version and date, and the preferred way to cite.
- The changelog links of the alpha releases point to their commits, so they resolve without
  tags; later releases compare tags.
- A few long lines were wrapped for the lint job (no change of behaviour).
- The public-surface snapshot `tests/data/public_api.json` was extended deliberately: the hooks
  and attributes of `DAPSRule` and `LTMRule`, the new exports (`DAPS`, `LTM`, `DAPSRule`,
  `LTMRule`, `BanditA3`, `RULE_BASES`), the observation field `l1_dbm`, the trace events
  `switch` and `fallback`, and the scenario keys `layout.lanes`, `layout.lane_width_m`,
  `layout.road_length_m` and `layout.sites_file`. Nothing was removed or renamed.
- Engine internals (not public): a procedure may set its execution time, its user-plane
  interruption, a fallback to the source and data on the source during the execution; the
  conditional procedure is split into execution and reporting steps that the LTM procedure reuses.
  Results of the existing procedures are bit-identical.
- `Scenario.with_overrides` accepts the new keys (it works on the full key set).
- Validation: `layout.kind` also accepts `highway`; `layout.lanes`, `layout.lane_width_m`,
  `layout.road_length_m` and a non-empty `layout.sites` are checked.
- Publishing: the publish workflow also runs when a tag `v*` is pushed, checks that the tag
  matches the version, and skips files that are already on PyPI, so that a GitHub release made
  later from the same tag (for the Zenodo archive) does not fail. `docs/RELEASING.md` describes
  the steps.
- README and documentation: installation from PyPI (`python -m pip install handoverlab`) next to
  the installation from source.

### Fixed

- Scenario cards: clause numbers checked against the specifications. The highway lanes, lane
  width and road length are cited from TR 37.885 Table A-1 (not clause 6.1.2); the highway
  inter-site distance of 500 m from TR 37.885 clause 6.1.3 (TR 38.913 gives it only as an
  option); the highway speeds from clause 6.1.2 (140 km/h, optionally 70 km/h; the uniform
  range between them is an assumption); the urban speed of 60 km/h from clause 6.1.2 (not
  Annex A); the 50 m correlation distance of TR 38.901 Table 7.6.3.1-2 as that of the LOS/NLOS
  state (UMi and UMa); the 4 dB LOS shadowing as that of UMi and UMa. The 35 m site offset of
  `highway-10ghz` is an assumption, after the freeway set-up of TR 36.885 clause A.1.3.
- Documentation: the list of built-in scenarios in the first tutorial, the highway in the home
  page and the README guide list, the versions named in the user guide and the verification
  page, the command synopsis (`verify --ns3-seeds`, `init --force`), a snippet of the user guide
  that used an undefined name, the per-carrier tuning of the upper mid-band guide (it needs
  `tuning.group_by`), and the release steps (all release-candidate sections are merged).
- Metadata: the descriptions in `CITATION.cff` and `.zenodo.json` name all procedures and
  layouts; links to the documentation site, which is not published, were removed or point to
  the `docs/` folder.

## [0.4.0a1] - 2026-10-15

Fourth alpha release (stage 4: dashboard, documentation, study tooling).

### Added

- Browser dashboard (extra `gui`: Streamlit and matplotlib; `handoverlab gui [--port] [--address]
  [--headless]`): scenario and setting pickers (street grid or open area, blocks, site spacing,
  carrier frequency, path loss, users, speed profile, run length, warm-up, seeds), up to four A3 or
  CHO rules with their parameters, a run button with progress, a map of the users on the layout
  coloured by serving cell (time slider and play, with counts up to the chosen time), charts of
  handovers, unnecessary handovers, failures, failure causes, delivered rate and cumulative events,
  a metrics table, and downloads of metrics (CSV), results (JSON), event logs and traces (CSV),
  figures (PNG) and an experiment file that `handoverlab run` repeats exactly. It runs locally
  only. The logic (`handoverlab.gui.logic`) needs no Streamlit and is tested on its own; the page
  is tested headless with Streamlit's test runner.
- Event-log levels `off`, `summary` and `full` (`log_events` in `simulate`, `run_world` and
  `Engine`; `run --events FILE --event-level full`; `events: off | summary | full` in study files).
  Level `full` adds a procedure trace (`RunResult.trace`): initial serving cell, measurement
  reports, preparations, releases, configurations reaching the UE or lost, executions,
  attachments after a handover or a re-establishment, and failures; `TRACE_FIELDS`,
  `TRACE_EVENTS`, `write_trace`, `read_trace`, `trace_path` and `serving_cells` (serving cell of
  every user at given times). Study test stages at level `full` store a trace table per run.
- `run_world(progress=...)`: a callback with the share of the run simulated so far.
- `handoverlab status STUDY|DIR [--workers N]` and `handoverlab.studies.status_data`: planned,
  finished, failed and remaining jobs per stage, rule runs still to simulate, gate state, sessions
  and the time left, estimated from the study's finished jobs (world-build time and engine time per
  rule run and user-second); stages not yet plannable are counted from the study file. A study
  directory alone is enough (`load_study_dir` reads `study.lock.json`). `study --status` shows the
  same.
- Gate policy `extend` for `grid_edge` with `tuning.extend_steps` (default 2) and
  `tuning.max_extensions` (default 2): a grid whose selected value lies on its edge is widened by
  values with the spacing of the last two (never below zero for a non-negative grid, and only with
  values the rule accepts), every method is tuned again with the same budget (stored rule runs are
  reused), and this repeats up to the cap, after which a remaining edge blocks. Extensions are
  recorded with their date in `amendments.json` and `AMENDMENTS.md`, applied again on resumption,
  and listed in the report.
- Documentation: tutorials (first run, writing your own rule, a fair tuning study, reading the
  report), a dashboard guide, a command-line reference, an API reference generated from the
  docstrings (MkDocs with mkdocstrings, `mkdocs.yml`, extra `docs`), a page on the failure-model
  calibration, and a workflow that builds the site on every push and publishes it on GitHub Pages
  when the repository enables it.
- Failure-model calibration against stored ns-3 / 5G-LENA results (`docs/calibration.md`): the ns-3
  failures are characterised (96 % late handover commands, no effect of T310, dependence on the
  time-to-trigger, the preparation delay and the traffic); a Qout filter window of about 0.12 s
  fits the mean failure rate and the ranking of the 24 reference settings but fails every
  held-back set, so no calibrated preset is added and the default is unchanged.
  `handoverlab.verify.ns3.compare` and `scenario_for` take `overrides` for such experiments.
- Example `examples/speed_rule.py` (a rule plug-in with its contract check).
- CI: the dashboard tests and a headless start of the dashboard in one job.

### Changed

- `RunResult` has a new field `trace`; `Engine` accepts a level name for `log_events`.
- Study files accept `events` as a level name; `true` still means `summary` and keeps the job IDs
  of earlier versions.
- `GateResult` has a field `edges` (parameter and end of every grid edge) and the status `EXTEND`.
- `study_status` moved to `handoverlab.studies.status` (still importable from
  `handoverlab.studies`) and now applies grid extensions and shows the time left.
- Results are unchanged: the golden fingerprints and the bh6 regression pass, and the model
  version stays 1.

## [0.3.0a1] - 2026-10-15

Third alpha release (stage 3: studies).

### Added

- Studies (`handoverlab.studies`): a study file (YAML, TOML or JSON) with a scenario, a full
  factorial of conditions, tuning and test seeds, methods with tuning grids, fixed parameters and
  natural bounds, tuning settings and comparisons; every key is checked.
- Equal-budget tuning: every tuned method evaluates the same number of settings per tuning group
  (a seeded random round, then refinement one and two grid steps around the best, then random
  settings if the neighbourhood is used up), on tuning seeds only.
- Selection rule: lowest unnecessary-handover rate among the settings within a failure budget (a
  share of the failure rate of a reference rule); settings within 5 % count as equal and are
  ordered by preparation overhead, failure rate, unnecessary-handover rate and evaluation order;
  if no setting meets the budget, the lowest failure rate. Objective, constraint and tie-breaks are
  configurable.
- Automatic tuning gates with the policies `warn`, `block` and `off`: `grid_edge` (selected value
  at the edge of its grid, natural bounds excepted), `budget_binding` (the budget constrains no
  method, or the reference has too few failures), `budget_met`, `equal_budget`, `seed_overlap`
  (checked before anything runs) and `flat_optimum`. A blocking gate stops the study before the
  test stage (`GateError`, exit status 3) and names every failed gate.
- Paired statistics (`handoverlab.stats`): paired differences, t intervals, percentile bootstrap
  intervals of the mean difference and of the ratio of means, the Wilcoxon signed-rank test (exact
  null distribution with ties and zeros, or the normal approximation with tie and continuity
  corrections), Holm correction, a non-inferiority check, a planning aid and decimal rounding.
- Result storage: one atomic JSON record per job (metrics, fingerprints, parameters, timing, peak
  memory), `manifest.json` with versions and sessions, `study.lock.json` with the resolved study and
  its hash, `plan.json`, failed-job tracebacks, tuning files with every evaluated setting and the
  gate report, and the tables `runs` and `tuning` as Parquet (with pyarrow) or CSV;
  `read_table` / `write_table`.
- Resumable studies with content-hashed job IDs: re-running skips finished jobs, a changed study
  re-runs only the affected jobs, and stored rule runs (same scenario, seed, rule and parameters)
  are reused instead of simulated again.
- Parallel jobs in worker processes (`--workers`; default: the logical CPUs minus four, half of
  them below eight), one BLAS thread per process, longest jobs first, a restart of a broken pool;
  results do not depend on the worker count.
- `handoverlab study STUDY` (`--workers`, `--tuning-only`, `--dry-run`, `--status`, `--report`) and
  `handoverlab report DIR` (Markdown and self-contained HTML with tables and matplotlib figures, and
  `summary.json`); extra `report` (matplotlib).
- `EngineBatch`: the engines of all rules of a world share one step loop; `run_world(batch=True)`
  is the default and `batch=False` runs them one by one.
- Example study `examples/study_smoke.yaml`; verification check "batched engines = engines run one
  by one"; tests of the statistics, the tuning, the studies and the batched engines.
- Documentation: user-guide sections on studies and paired statistics; a validation section on the
  difference in failure rates to ns-3 / 5G-LENA; the performance page with the stage-3 changes.

### Changed

- Engine speed: with many rules per world the engines need about half the time (24 rules on the
  smoke scenario: 50.7 s down to 25.0 s; 8 rules: 16.9 s to 9.7 s; with 2 rules within the noise). Per-step work that
  changes only at measurement instants or at events (interference weight of the serving cells,
  pending handover commands) is no longer repeated every step, and the radio-link monitoring and the
  load model run on arrays over all rules. Results are bit-identical: golden fingerprints and the
  bh6 regression are unchanged.
- `python -m handoverlab` guards its entry point, so worker processes can be started from it.

## [0.2.0a1] - 2026-10-15

Second alpha release (stage 2: verification in depth).

### Added

- `handoverlab verify` command and `handoverlab.verify.run_verify()`: check groups `pathloss`
  (TR 38.901 against hand values), `radio` (radio statistics against the model parameters),
  `invariants`, `equivalences` and `fingerprints`; `--full`, `--only`, `--json`; `--ns3` for the
  reference comparison with stored ns-3 / 5G-LENA results; `--results FILE [--sample N]` to
  recompute stored runs and compare event-log fingerprints and metrics.
- Debug mode of the engine (`debug=True`, `handoverlab run --debug`, `HANDOVERLAB_DEBUG=1`) with
  invariant checks at every step, validation of the values returned by rules and a read-only
  observation; `InvariantError`.
- More conservation checks at the end of every run: every attempt gets exactly one outcome, and
  every preparation ends as lost, cancelled, used, unused or open (also across the warm-up).
- Event-log fingerprints (`handoverlab.eventlog`): SHA-256 of a canonical CSV form, computed for
  every run (`RunResult.fingerprint`, `n_events`) and stored in CSV and JSON results together with
  the rule key.
- Event logs as tables: `write_events` (Parquet with `pyarrow`, else CSV; extra `parquet`),
  `read_events`, typed column catalogue `EVENT_COLUMNS`; `run --events` accepts `.parquet`.
- Golden event-log fingerprints of eight short reference runs (`handoverlab/verify/data/golden.json`,
  regenerated with `python -m handoverlab.verify.golden --write`).
- Contract test kit for rule plug-ins: `handoverlab.testing.check_rule` and the example plug-in
  `ScaledA3`.
- Built-in scenarios with scenario cards (`smoke`, `urban-grid-10ghz`, `open-area-10ghz`,
  `ns3-urban-3.5ghz`): YAML cards in the package, Markdown pages and layout drawings in
  `docs/scenarios`, `handoverlab scenarios`, `builtin_scenario()`, `scenario: NAME` and
  `scenario: {base: NAME, ...}` in configuration files.
- Protocol switch `cfg_loss_as_failure` (check mode) for the equivalence "CHO with immediate
  execution = A3".
- Reference data of an ns-3 / 5G-LENA study (24 A3 settings, four conditions) with acceptance
  limits; result of this version: median ratios 0.95 (handovers) and 1.04 (unnecessary handovers),
  rank correlation 0.99 for both.
- Wider regression sample against the bh6 prototype (eight more cases with four rules each,
  metrics and event logs).
- Documentation: verification and performance pages, user-guide sections on scenarios, event logs,
  verification, debug mode and the contract kit.

### Changed

- The world build is about a third faster (path loss, LOS state, random fields, line of sight);
  results are bit-identical.
- The engine always keeps its event log internally to compute the fingerprint; `RunResult.events`
  is still set only when requested. Event-log values are plain Python numbers.
- Result CSV files have the new columns `fingerprint` and `n_events`; JSON records also hold `key`.

## [0.1.0a1] - 2026-10-15

First alpha release (stage 1: the core simulator).

### Added

- `handoverlab` package (src layout, Python 3.9 or later; NumPy, SciPy, PyYAML).
- Scenarios: TR 37.885 urban street grid with a configurable number of blocks (default 3 x 3),
  open area with a hexagonal site grid, explicit site lists.
- Channel: TR 38.901 UMi street canyon and UMa path loss and LOS probability; building line of
  sight plus the spatially consistent LOS state; place-tied correlated shadowing with an optional
  share that moves with the user; time-varying component; L1 measurement error; beam gain and
  load-coupled interference.
- Mobility: street-following users with turn probabilities, random waypoints, speed profiles and
  user-defined speed groups.
- Measurement chain: L1 samples, TS 38.331 L3 filter, Event A3 with time-to-trigger, periodic
  reporting.
- Handover procedures: baseline handover and Rel-16 conditional handover (up to 8 prepared cells),
  with a radio-link failure model (Qout/Qin, N310/N311/T310, re-establishment, CHO recovery).
- Rule interface (`BaselineRule`, `ConditionalRule`) with a registry, a decorator and the
  `handoverlab.rules` entry-point group; built-in rules `a3` and `cho`.
- Outcome label for every attempt, failures by cause, preparation, interruption and service
  metrics; conservation checks at the end of every run.
- Configuration as YAML, TOML, JSON or dictionary, with key-level validation messages.
- Command line `handoverlab run | rules | init`, CSV and JSON result files, event-log export.
- Tests: path loss, L3 filter, A3 and CHO triggers, failure model, configuration, command line,
  determinism, and a regression test against the bh6 prototype on a 2 x 2-block grid.
- Documentation: README, user guide, contribution guide, citation file; CI on Linux, Windows and
  macOS with Python 3.9-3.12.

[Unreleased]: https://github.com/mjs19971997/handoverlab/compare/v2.7.0...HEAD
[2.7.0]: https://github.com/mjs19971997/handoverlab/compare/v2.6.0...v2.7.0
[2.6.0]: https://github.com/mjs19971997/handoverlab/compare/v2.5.0...v2.6.0
[2.5.0]: https://github.com/mjs19971997/handoverlab/compare/v2.4.2...v2.5.0
[2.4.2]: https://github.com/mjs19971997/handoverlab/compare/v2.4.1...v2.4.2
[2.4.1]: https://github.com/mjs19971997/handoverlab/compare/v2.4.0...v2.4.1
[2.4.0]: https://github.com/mjs19971997/handoverlab/compare/v2.3.0...v2.4.0
[2.3.0]: https://github.com/mjs19971997/handoverlab/compare/v2.2.0...v2.3.0
[2.2.0]: https://github.com/mjs19971997/handoverlab/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/mjs19971997/handoverlab/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/mjs19971997/handoverlab/compare/v1.12.0...v2.0.0
[1.12.0]: https://github.com/mjs19971997/handoverlab/compare/v1.11.0...v1.12.0
[1.11.0]: https://github.com/mjs19971997/handoverlab/compare/v1.10.0...v1.11.0
[1.10.0]: https://github.com/mjs19971997/handoverlab/compare/v1.9.0...v1.10.0
[1.9.0]: https://github.com/mjs19971997/handoverlab/compare/v1.8.0...v1.9.0
[1.8.0]: https://github.com/mjs19971997/handoverlab/compare/v1.7.0...v1.8.0
[1.7.0]: https://github.com/mjs19971997/handoverlab/compare/v1.6.0...v1.7.0
[1.6.0]: https://github.com/mjs19971997/handoverlab/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/mjs19971997/handoverlab/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/mjs19971997/handoverlab/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/mjs19971997/handoverlab/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/mjs19971997/handoverlab/compare/v1.1.1...v1.2.0
[1.1.1]: https://github.com/mjs19971997/handoverlab/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/mjs19971997/handoverlab/compare/v1.0.2...v1.1.0
[1.0.2]: https://github.com/mjs19971997/handoverlab/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/mjs19971997/handoverlab/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/mjs19971997/handoverlab/compare/e93b9c59e5a42665a47be91922ddd5aede998367...v1.0.0
[0.4.0a1]: https://github.com/mjs19971997/handoverlab/compare/b0802c5c18634506e47a19454ca9b51293e712d7...e93b9c59e5a42665a47be91922ddd5aede998367
[0.3.0a1]: https://github.com/mjs19971997/handoverlab/compare/a5ce5dd706c225c89c13a49fea239a89a1f56cb7...b0802c5c18634506e47a19454ca9b51293e712d7
[0.2.0a1]: https://github.com/mjs19971997/handoverlab/compare/803b849719342e96dabcf430e819d3dfcb96caf0...a5ce5dd706c225c89c13a49fea239a89a1f56cb7
[0.1.0a1]: https://github.com/mjs19971997/handoverlab/tree/803b849719342e96dabcf430e819d3dfcb96caf0
