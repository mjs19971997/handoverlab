# Changelog

All notable changes to this project are documented in this file. The format follows
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/) for the public surface described in
[docs/stability.md](docs/stability.md); before 1.0.0 any interface could change.

## [Unreleased]

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

[Unreleased]: https://github.com/mjs19971997/handoverlab/compare/v1.11.0...HEAD
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
