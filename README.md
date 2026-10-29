# HandoverLab

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23409131.svg)](https://doi.org/10.5281/zenodo.23409131) [![PyPI](https://img.shields.io/pypi/v/handoverlab.svg)](https://pypi.org/project/handoverlab/)

HandoverLab is a reproducible system-level simulator for studying and comparing handover algorithms and procedures in 5G-Advanced, beyond-5G and some NTN scenarios, with explicit models, optional features and a documented validation scope. It is written in Python.

HandoverLab simulates 3GPP mobility procedures (baseline handover with Event A3, Release-16
conditional handover and DAPS handover, Release-18 L1/L2-triggered mobility, conditional handover with
the location event D2 for satellites) for many users moving through a street grid, an open area, along a
highway, in an indoor office, across rural cells or under the beams of a LEO satellite, with a
received-power-level radio model from TR 38.901 (TR 38.811 for the satellite) (optionally with SSB beams, beam failure recovery
and several carriers), an L3-filtered measurement chain, a radio-link failure model, and an
outcome label for every handover attempt.

> **Status: 2.10.0** (`python -m pip install handoverlab`). The public surface (configuration and
> result formats with a schema version, the rule interface, metric names, commands and the
> documented Python names) follows the [stability policy](https://github.com/mjs19971997/handoverlab/blob/main/docs/stability.md): within 2.x it only grows,
> and anything removed is deprecated first. 2.0.0 makes the 3GPP values the defaults (the protocol profile,
> the urban vehicles of TR 37.885, the path-loss constants of TR 38.901), so results differ from 1.x;
> one switch, `LEGACY_1X`, gives every 1.x result back bit for bit (for the cards changed since 2.1.0
> together with their old values in `LEGACY_CARDS`)
> ([moving from 1.x to 2.0](https://github.com/mjs19971997/handoverlab/blob/main/docs/migration-2.0.md)).

## See it

**Run and watch.** `handoverlab gui` opens a dashboard in the browser, on your computer only. Choose a
layout, users and rules, press Run, and follow the users. Each user is coloured by its serving cell:

![The dashboard map: users on the street grid, each joined to its serving site](https://raw.githubusercontent.com/mjs19971997/handoverlab/main/docs/images/dashboard.png)

**See where things happen.** The tab *Where* marks every handover, unnecessary handover and
failure at the place where it happened:

![Places of handovers and unnecessary handovers on the street grid](https://raw.githubusercontent.com/mjs19971997/handoverlab/main/docs/images/dashboard-where.png)

**Compare rules fairly.** All rules run on the same worlds, one world per seed. The tab *Compare*
shows each mean with its 95 % confidence interval over the seeds, and the paired difference to the
first rule:

![Handovers, unnecessary handovers, failures and rate of A3 and conditional handover, with confidence intervals](https://raw.githubusercontent.com/mjs19971997/handoverlab/main/docs/images/dashboard-compare.png)

**Run whole studies.** `handoverlab study` tunes every rule, checks gates, runs paired tests with
multiple-comparison correction and writes an HTML report:

![Study report: paired differences to a reference rule with bootstrap intervals](https://raw.githubusercontent.com/mjs19971997/handoverlab/main/docs/images/report-comparison.png)

**Indoors and in rural cells.** Since 1.7.0: the TR 38.901 indoor office (12 ceiling sites,
20 m apart) and rural macro cells (sites 1732 m apart, users in cars at 120 km/h), both with the
IMT-2020 link budgets and the soft LOS state of TR 38.901:

![Layout of the indoor office: a 120 m x 50 m hall with 12 ceiling sites](https://raw.githubusercontent.com/mjs19971997/handoverlab/main/docs/scenarios/indoor-office-4ghz.svg)

![Layout of the rural scenario: 11 macro sites on a 1732 m hexagonal grid](https://raw.githubusercontent.com/mjs19971997/handoverlab/main/docs/scenarios/rural-700mhz.svg)

**Beams and several carriers.** Since 1.10.0: sectors with SSB beams (the antenna of TR 38.901),
beam management and beam failure recovery as in TS 38.321 and TS 38.133, and further carriers with
inter-frequency measurements in gaps, for example the two-layer dense urban deployment of ITU-R
M.2412 (4 GHz macro cells, 30 GHz micro cells):

![The 8 SSB beams of one sector against the antenna abstraction of 1.x](https://raw.githubusercontent.com/mjs19971997/handoverlab/main/docs/images/ssb-beams.png)

![Layout of the two-layer dense urban scenario: 23 macro sites and 207 micro sites](https://raw.githubusercontent.com/mjs19971997/handoverlab/main/docs/scenarios/dense-urban-2layer.svg)

**Highway as in TR 37.885.** Since 1.11.0: wrap-around, LOS-only links and both site layouts of
TR 36.885; above 6 GHz the road crosses a cluster of 19 hexagonal sites with 3 sectors each:

![Layout of the highway above 6 GHz: 19 sites on a 500 m hexagonal grid, the road across the cluster](https://raw.githubusercontent.com/mjs19971997/handoverlab/main/docs/scenarios/highway-tr37885-30ghz.svg)

**Your own radio map.** Since 1.12.0: the path gain of every site and street pixel from a ray tracer or
from measurements replaces the statistical channel (TR 38.901 clause 8); an exported map gives the same
event log bit for bit:

![The radio map of the card smoke: best path gain in every street pixel](https://raw.githubusercontent.com/mjs19971997/handoverlab/main/docs/images/radio-map.png)

**Satellites.** Since 2.0.0: one LEO satellite at 600 km with 19 earth-moving beams in the S band
(TR 38.811 channel, TR 38.821 parameters). The beams sweep over the ground at about 7 km/s, so even a user
standing still hands over every few seconds; the rule `cho_d2` is conditional handover with the location
event D2 of Release 18:

![The 19 beams on the ground at the start and end of a run, and the received power of each beam at one user](https://raw.githubusercontent.com/mjs19971997/handoverlab/main/docs/images/ntn-beams.png)

**New cards.** Since 2.3.0: the TR 37.885 urban grid with 35 macro sites 500 m apart (4 GHz), suburban
macro (SMa) at 7 GHz with 11 sites 1299 m apart and 80 % of the users indoors, and a high-speed train in FR2
(TR 38.854: 12 remote radio heads 700 m apart, 10 m from the track, 350 km/h):

![Layouts of the cards urban-macro-tr37885-4ghz, suburban-sma-7ghz and hst-fr2-28ghz](https://raw.githubusercontent.com/mjs19971997/handoverlab/main/docs/images/new-scenarios.png)

**Predicted measurements.** Since 2.4.0 the rule `a3_pred` hands over on predicted L3 results, as studied
in TR 38.744. Trained on two seeds and tested on two others, the ridge predictor is about 0.5-0.6 dB more
accurate than sample and hold 400 ms ahead (1.84 / 2.66 / 3.14 dB against 2.38 / 3.26 / 3.74 dB at 30 / 60 /
90 km/h):

![Prediction error against horizon for the ridge predictor and sample and hold at 30, 60 and 90 km/h](https://raw.githubusercontent.com/mjs19971997/handoverlab/main/docs/images/ai-mobility.png)

**Handover procedures side by side.** On one card failures fall from 0.6 (A3) to 0.2 (LTM and CLTM) per
UE-minute; DAPS has no execution interruption; LTM pays with 192 RRC messages per UE-minute against 45 for A3:

![Failures and ping-pong, interruption and RRC messages for A3, CHO, DAPS, LTM and CLTM](https://raw.githubusercontent.com/mjs19971997/handoverlab/main/docs/images/procedures.png)

**Mobility robustness optimisation.** `a3_mro` moves the offset of every cell pair from its own failures;
here 17 pairs move and failures fall from 0.22 to 0.14 per UE-minute when starting from 3 dB:

![Cell-pair offsets over time under a3_mro, and failures against fixed A3](https://raw.githubusercontent.com/mjs19971997/handoverlab/main/docs/images/mro.png)

**Fast fading.** With TDL-A or TDL-C the 5th percentile of the link-monitoring SINR on the ns-3 card falls
from 8.3 dB to 3.8 and 3.4 dB:

![Received power of one vehicle with no fading, TDL-A and TDL-C, and the distribution of the link-monitoring SINR](https://raw.githubusercontent.com/mjs19971997/handoverlab/main/docs/images/fading.png)

**Slot scheduler.** Round robin and proportional fair with the MCS, TBS and HARQ of TS 38.214; with
`run.backend: numba` the same runs take 2.2 s and 1.0 s instead of 92.7 s and 93.3 s with NumPy, with identical
fingerprints (the default rate model takes about 1.0 s for the same run):

![Delivered rate of each vehicle against its SINR for round robin and proportional fair, and the wall time with NumPy and Numba](https://raw.githubusercontent.com/mjs19971997/handoverlab/main/docs/images/scheduler.png)

**Buffers at handover.** Without data forwarding A3 loses 2.17 % of the data and DAPS 0.34 %; with
forwarding nothing is lost, and the forwarded data wait 85-349 ms:

![Lost data with and without forwarding, and the PDCP delay, for A3, CHO, DAPS and LTM](https://raw.githubusercontent.com/mjs19971997/handoverlab/main/docs/images/buffers.png)

**Dual connectivity.** A 4 GHz master cell and a 30 GHz secondary cell: the secondary cell group carries data
96 % of the time and 183 Mbit/s per user, against 10.1 Mbit/s on the master cell group:

![One user's 4 GHz master cell and 30 GHz secondary cell over time with the dual-connectivity events, and the procedure rates](https://raw.githubusercontent.com/mjs19971997/handoverlab/main/docs/images/dual-connectivity.png)

**UE receive beams.** Two panels with DFT beams (peak gain 13.7 dBi) raise the mean SINR from 10.9 to 19.2 dB
and cut failures from 3.60 to 1.44 per UE-minute; a beam sweep keeps them at 3.36:

![Receive beam patterns of a two-panel UE, and SINR and failures for four UE receive-beam setups](https://raw.githubusercontent.com/mjs19971997/handoverlab/main/docs/images/ue-beams.png)

**Traffic models.** The same handovers (11.3 per UE-minute) under fixed rates, full buffer, periodic packets and FTP model 3,
with very different rate, cell load and energy per bit:

![Rate, cell load and energy per bit for the four traffic models](https://raw.githubusercontent.com/mjs19971997/handoverlab/main/docs/images/traffic.png)

## What it models

- **Scenarios**: the TR 37.885 urban street grid (configurable number of blocks; 433 m x 250 m
  pitch, 20 m streets) with sites on the pavement, an open area with a hexagonal site grid, the
  TR 37.885 highway (since 1.11.0 with wrap-around, LOS-only links and both site layouts of
  TR 36.885, below and above 6 GHz), the TR 37.885 urban grid with 500 m macro sites (since 2.3.0), the
  TR 38.901 indoor office, rural and suburban (SMa, since 2.3.0) macro cells, a LEO satellite with
  earth-moving beams (since 2.0.0, TR 38.811 and TR 38.821), explicit site lists, and built-in scenario
  cards (`handoverlab scenarios`).
- **Channel**: TR 38.901 UMi street canyon, UMa, RMa, SMa (since 2.3.0) and InH-Office path loss (LOS/NLOS); O2I
  building penetration loss of indoor users (since 2.3.0); line of sight from the
  building geometry plus the spatially consistent LOS state, hard or soft; spatially correlated shadowing; a
  time-varying component; L1 measurement error; beam gain and load-coupled interference;
  optionally a penetration loss per user (in-car loss of TR 38.901); or, since 1.12.0, your own radio
  map from a ray tracer or measurements (`radio.map_file`, the map-based model of TR 38.901 clause 8).
- **Beams and carriers** (options, 1.10.0): sectors with SSB beams from the TR 38.901 antenna
  model, cell quality from the beams (TS 38.331 5.5.3.3), the serving beam from beam reports, beam
  failure detection and recovery (TS 38.321 5.17, TS 38.133 8.5), several carriers with the
  measurement periods and gaps of TS 38.133, Event A5 between carriers; UE receive beams (since 2.4.0) and
  dual connectivity with a secondary cell group (since 2.3.0, TS 37.340).
- **Lower layers** (options, since 2.2.0): TDL fast fading of TR 38.901 with an effective SINR (MIESM) for
  link monitoring and the rate; a slot scheduler with the MCS, TBS and HARQ of TS 38.214; user-plane buffers
  at handover with data forwarding (since 2.3.0, TS 38.300, TS 38.322, TS 38.323).
- **Mobility**: street-following users with turn probabilities, random waypoints in the open area,
  pedestrian and vehicular speed profiles (by default the urban vehicles of TR 37.885: 60 km/h in one of
  two lanes) or your own speed groups.
- **Traffic**: constant service rates per 5QI class, or a traffic model per user: full buffer,
  periodic packets (as VoIP) or FTP model 3 (TR 38.802, the 0.5 Mbyte files of TR 38.821). The load of every cell, and so the
  interference, follows the traffic of its users.
- **Measurements**: L1 samples, the TS 38.331 L3 filter, Event A3 with time-to-trigger, periodic
  reporting for conditional handover.
- **Handover procedures**: baseline handover (report, preparation, command, execution), Rel-16
  conditional handover (up to 8 prepared candidates) and DAPS handover, Rel-18 L1/L2-triggered
  mobility and conditional LTM from the Rel-19 work, conditional handover with the Rel-18 location events
  D1/D2 (`cho_d2`), behind a small rule interface. Rules that learn from outcomes are supported, among them
  mobility robustness optimisation of a cell individual offset per cell pair (`a3_mro`), an
  epsilon-greedy bandit (`a3_bandit`, checked against an exhaustive search) and a deep Q-network
  (`dqn`, optional PyTorch).
- **Failure model**: Qout/Qin with windows, N310/N311/T310, T304, lost commands and configurations,
  execution failures, re-establishment after a fixed outage (1 s, inside the bounds of TS 38.133
  6.2.1.2.1), the handover command
  during T310 as TS 38.331 specifies and the restart of the link monitoring on a new cell as HandoverLab
  reads TS 38.133 8.1.2.2 (defaults since 2.0.0), with options for the link monitoring (own interferer load, ideal random access).
- **Metrics**: outcome of every attempt (useful, unnecessary, too early, wrong cell, too late,
  censored), failures by cause, ping-pong, preparation overhead, interruption, delivered rate,
  signalling (RRC messages, commands), L1 measurements of the device and network energy (EARTH
  model).
- **Reproducibility**: one world per seed shared by all compared rules (paired comparison); the
  engine draws no random numbers; golden event-log fingerprints guard every change. An optional
  compiled kernel (`run.backend: numba`) gives the same event logs bit for bit.

## Model boundaries

What HandoverLab is for, at a glance: questions about handover and mobility procedures and the rules that
drive them, compared on the same worlds. What it abstracts or leaves out decides which conclusions it supports;
the clause-by-clause detail is in [standard compliance](https://github.com/mjs19971997/handoverlab/blob/main/docs/standard-compliance.md).

| Part | Modelled | Abstracted | Not modelled |
|---|---|---|---|
| Layouts | `street_grid` (TR 37.885 urban grid), `open_area`, `highway` (TR 37.885 / TR 36.885, wrap-around), `indoor` (TR 38.901 office), `ntn` (one LEO satellite, TR 38.821); explicit site lists | sites on the pavement with small cells (urban cards); the TR 37.885 urban macro grid without wrap-around (`urban-macro-tr37885-4ghz`) | several satellites |
| Channel | TR 38.901 path loss and LOS (UMi, UMa, RMa, SMa, InH), LOS from buildings, spatially consistent LOS and shadowing, car and O2I building penetration loss, radio maps from a file (clause 8), TR 38.811 for the satellite | received power per site and step with a slow time-varying component; indoor users keep the LOS state and shadowing of their position; optional TDL fast fading with effective SINRs (clause 7.7.2, since 2.2.0); options (2.10.0): beam gains over the expected angular spectrum of clause 7.5 and blockage model A (clause 7.6.4.1) on the expected arrival spectrum, not per cluster | CDL and the full fast-fading model of clause 7.5, MIMO |
| Beams and carriers | SSB beams per sector, cell quality from beams, beam failure detection and recovery, several carriers with gaps and Event A5; dual connectivity (NR-DC: SN addition, PSCell change, SN release, SCG failure; option since 2.3.0) | the TR 38.901 antenna element and DFT beams; isotropic UE unless UE receive panels are set (option since 2.4.0); the SCG as one PSCell with a full-buffer share | UE transmit beams and polarisation, conditional PSCell change, fast MCG recovery |
| Mobility | street-following vehicles (60 km/h, two lanes), highway lanes at 70/140 km/h, a train at 350 km/h (TR 38.854), random waypoints, pedestrians | constant speed per user | handheld rotation; body blockage only as the option `radio.blockage: a` (TR 38.901 blockage model A, 2.10.0), model B not modelled |
| Traffic and load | constant rates per 5QI, full buffer, periodic, FTP model 3; cell load drives interference; options: a slot scheduler (`protocol.scheduler`: round robin or proportional fair) with the MCS, TBS and HARQ of TS 38.214 (since 2.2.0), and user-plane buffers at handover (`protocol.buffers`: simplified PDCP / RLC in AM or UM with Xn data forwarding, since 2.3.0) | by default the rate from the SINR (Shannon-type mapping) without a scheduler; with the scheduler the channel is held for the 10 ms step and the MCS is chosen from the SINR of one measurement interval earlier (no CSI reports); buffers: downlink only, one bearer per user, the interruption quantised to the measurement interval; both options need the base engine (no beams, layers, NTN or TS 38.133 periods) | uplink data, CSI-based link adaptation, PDCP reordering and status reports at the UE, TCP and applications |
| Measurements | L1 samples with error, TS 38.331 L3 filter, TS 38.133 measurement periods and gaps (option) | wideband RSRP; SS-RSRP per resource element with beams/carriers | RSRQ, CSI reporting |
| Procedures | baseline (A3), CHO, DAPS, LTM, conditional LTM, CHO with D1/D2 for satellites, A3/A5 between carriers; rules `a3`, `a3a5`, `a3_mro`, `a3_bandit`, `dqn`, `a3_pred`, `cho`, `cho_d2`, `daps`, `ltm`, `cltm` | fixed preparation, command and execution delays; re-establishment always succeeds after a fixed outage | condEventT1, RACH-less NTN handover, Xn signalling in detail |
| Failure model | Qout/Qin with windows, N310/N311/T310, T304, command received during T310, re-establishment, link-monitoring restart; option (2.8.0, `protocol.rlm_interference: dynamic`): time-varying, load-dependent interference on SSB- or CSI-RS-based link monitoring from FTP burst traffic (TR 36.814, TR 36.872) | Qout/Qin as SINR thresholds (TR 36.839 values) instead of the BLER of a hypothetical PDCCH; by default the interferers' smoothed data load at link monitoring; with the option, what meets the RLM-RS (RLM-RS type, SSB overlap) is an assumption, since 3GPP does not fix it | BLER-based link monitoring; the absolute failure level is not calibrated: with equal run lengths the default gives 0.17-0.32 of ns-3's and the ns-3 comparison setting 0.5-1.3 depending on the set, passing the pre-registered checks on 1 of 4 fresh ns-3 sets (V4); the ns-3-like option (2.7.0) imitates ns-3's failure detection but is not validated (right at long time-to-trigger, far too few failures at short); the dynamic link-monitoring interference (2.8.0) is a sensitivity option, not validated, that gives from far below ns-3's failure level (CSI-RS, light traffic) to 2.8-15 times it (aligned SSBs): compare rules with each other, for a stated RLM configuration |
| Time | 10 ms step by default (`protocol.step_s`); the effect of the step is measured in [time step](https://github.com/mjs19971997/handoverlab/blob/main/docs/time-step.md) | events rounded to the step | sub-slot timing |

Built-in cards: `smoke`, `urban-grid-10ghz`, `fr3-urban-15ghz`, `urban-grid-28ghz-beams`, `dense-urban-2layer`,
`open-area-10ghz`, `ns3-urban-3.5ghz`, `highway-tr37885-4ghz`, `highway-tr37885-30ghz`, `indoor-office-4ghz`,
`rural-700mhz`, `ntn-leo600-2ghz`, `urban-macro-tr37885-4ghz`, `suburban-sma-7ghz`, `hst-fr2-28ghz`; each
names the source of every value and its own limitations.

## Scope: 5G-Advanced and beyond 5G

HandoverLab is a system-level handover simulator for 5G-Advanced and beyond-5G research. It covers the
mobility procedures of Releases 16 to 19 (conditional handover, DAPS handover, L1/L2-triggered mobility,
conditional LTM, conditional handover with the location events of Release 18 for satellites) in dense
networks with small cells 50-300 m apart. Three paths lead beyond 5G:

- **The upper mid-band (FR3, 7-24 GHz)**, studied in TR 38.901 V19.5.0: the card `fr3-urban-15ghz` and every
  layout at any carrier the path-loss models cover.
- **Non-terrestrial networks**: a LEO satellite with earth-moving beams (TR 38.811, TR 38.821) and conditional
  handover with condEventD2 (TS 38.331 Release 18).
- **Learning-based mobility**: the rule interface gives a rule every measurement and the outcome of every
  attempt; `a3_bandit` and `dqn` are examples, `a3_mro` the fair tuned baseline, and `a3_pred` follows the
  RRM measurement prediction of TR 38.744 (Release 19).

6G itself is at the stage of requirements: TR 38.914 V20.1.0 (Release 20, last changed at RAN #113 in September
2026) sets scenarios and key performance requirements but specifies no handover procedure, timer or measurement
rule yet. HandoverLab therefore claims no 6G procedure; the paths above are where 6G mobility work is expected
to build on 5G-Advanced. The cost of every procedure (signalling, prepared cells, interruption, energy) is
measured next to its benefit.

## Calibrated against 3GPP

The radio model passes the large-scale calibration of TR 38.901 (clause 7.8.1): in the
calibration drop of 3GPP, the CDFs of the coupling loss and of the geometry (SINR) lie inside the
range of the 21 companies that reported their results in the 3GPP contribution R1-165974 (Huawei,
Ericsson, Nokia, Samsung, Qualcomm and others), for UMa, UMi and the indoor office at 6 and
30 GHz. 325 of 342 compared percentiles are inside the range, none is more than about 1 dB from
the industry mean, and `handoverlab verify` repeats the check
([details](https://github.com/mjs19971997/handoverlab/blob/main/docs/calibration-3gpp.md)). Since 2.4.0 the
same check runs for Table 7.8-1A against the companies of R1-2506406. At 7 GHz (UMa, UMi and SMa with ISD
1299 m and 1732 m) all 228 percentiles lie inside their range, but the largest distance from their mean is
1.69-2.43 dB, which misses the 1.5 dB criterion set before the run; the two 6 GHz reruns of UMa and UMi with
the updated model add 114 percentiles, also all inside, at 1.65 and 2.88 dB.

![CDFs of coupling loss and geometry for UMa, UMi and SMa at 7 GHz, with the HandoverLab curve inside the company range of R1-2506406](https://raw.githubusercontent.com/mjs19971997/handoverlab/main/docs/images/calibration_7ghz.png)

![HandoverLab against the 21 companies of 3GPP R1-165974](https://raw.githubusercontent.com/mjs19971997/handoverlab/main/docs/images/calibration_38901.png)

## Follows the 3GPP texts

Every rule of the handover procedure is listed clause by clause against the official 3GPP texts
(TS 38.331, 38.133, 38.300, 38.321 of Releases 17 to 19, TR 36.839, TR 38.901) in
[standard compliance](https://github.com/mjs19971997/handoverlab/blob/main/docs/standard-compliance.md),
with what is followed, what is abstracted and what is not modelled yet. The 3GPP protocol profile of
1.9.0 (`protocol: {cmd_during_t310: receive, t304_s: 1.0, rlm_holdoff_s: 0.2}`), the default since 2.0.0,
makes the handover command and its execution follow TS 38.331; the audit of 2.1.0 checked every procedure,
requirement and value against TS 38.331 V18.11.0, TS 38.133, TS 38.300 and the TRs, and what remains an
abstraction is listed on that page. Against handover statistics
measured in commercial 5G networks (SIGCOMM, IMC and MobiCom measurement studies) the profile
brings the handover failure rate from about six times above the measured range to just above it;
ping-pong with the Verizon A3 setting and the handover distance in low-band rural cells match.
Since 1.10.0 the page also covers beams, beam failure recovery, measurement gaps and Event A5, and
the DAPS and LTM interruptions are checked against TS 38.133 and published 3GPP evaluations.

## Checked against ns-3

The same 24 Event-A3 settings were simulated in HandoverLab and in the packet-level simulator
ns-3 with 5G-LENA. Handover and unnecessary-handover rates agree (median ratios 0.95 and 1.06,
rank correlation 0.99; `handoverlab verify --ns3`, version 2.1.0). For failure rates, with the in-car loss of ns-3 and the restart of the link
monitoring switched on, the order of settings and conditions agrees too, also on ns-3 results
that were held back from any tuning (rank correlation 0.82-0.91). **The absolute failure level is not
calibrated.** On four fresh, pre-registered sets of ns-3 runs (N3, V1, V3, V4), compared over equal run
lengths, the default link-monitoring model gives 0.18, 0.32, 0.17 and 0.27 of ns-3's failure level and fails
the level on all four. The ns-3 comparison setting of 2.5.0
(`handoverlab.verify.ns3.COMPARISON_SETTING`: interferer load 0.15 at link monitoring and ideal execution,
with the in-car loss of ns-3; `handoverlab verify --ns3 --ns3-comparison`) brings the level closer but is
not validated: 0.52 (N3), 1.31 (V1, where the order of failures across cells fails, rank 0.62), 0.64
(V3) and 0.73 (V4), so 0.5-1.3 times ns-3's level depending on the set, passing the checks on 1 of the 4
sets (V4). The handover-rate ratio (0.815-0.96) and the direction of the time-to-trigger effect agree in
every set. *Corrected in 2.6.0:* 2.5.0 reported that the setting passed on V1 (level 0.97, rank 0.88);
that analysis compared 90 s of HandoverLab with 120 s of ns-3. The ns-3-like option of 2.7.0
(`handoverlab.verify.ns3.NS3_LIKE_SETTING`) imitates ns-3's failure detection; frozen before V4 was opened,
it gives level 1.03 on V4, right at time-to-trigger 1280 ms (1.07) but far too low at 128 ms (0.03), and
fails the handover-rate check (0.759, limit 0.8), so it is **not validated**. Neither setting is a default,
so compare failure rates between rules within HandoverLab. The dynamic link-monitoring interference of 2.8.0
(`protocol.rlm_interference: dynamic`, not a default) follows the 3GPP texts where they are fixed and does not reproduce ns-3
either: depending on the RLM-RS and the SSB overlap, which 3GPP leaves open, it gives in sample from far below
ns-3's failure level to 2.8-15 times it. The study and the causes of the differences are
in [docs/calibration.md](https://github.com/mjs19971997/handoverlab/blob/main/docs/calibration.md). On two of the causes HandoverLab follows the 3GPP texts more closely
than ns-3:

- **In-car penetration loss.** TR 38.901 clause 7.4.3.2 gives it to a user inside a car. ns-3 adds
  it only while a user moves at 30-120 km/h and drops it above 120 km/h. HandoverLab applies it
  per user when configured (`radio.penetration_db`), at any speed.
- **Time to detect a radio problem.** TS 38.133 clause 8.1 evaluates out-of-sync over about
  200 ms. ns-3 counts control receptions instead of time, and at light traffic this takes 0.65-0.9 s
  (measured in 2.7.0). HandoverLab evaluates over time (`protocol.qout_window_s`, 0.2 s);
  the ns-3-like option (2.7.0) counts receptions as ns-3 does.

On a third point ns-3 was closer to the 3GPP texts: link monitoring restarts on a newly joined cell.
HandoverLab has had this as an option since 1.3.0 (`protocol.rlm_holdoff_s`), on by default since 2.0.0. The comparison
covers baseline handover at 3.5 GHz only: 5G-LENA has no conditional handover, DAPS or
L1/L2-triggered mobility.

To run your own study in both simulators, `handoverlab ns3 export|import|compare` writes the ns-3 package, reads its results back and applies the same checks ([guide](https://github.com/mjs19971997/handoverlab/blob/main/docs/guides/ns3-bridge.md)).

## What's new

- **2.10.0**: four realism options from the 3GPP texts, all off by default, re-tested against the real
  data ([real data](https://github.com/mjs19971997/handoverlab/blob/main/docs/real-data.md#re-test-with-the-2100-options)):
  `radio.beams.angular_spread: tr38901` takes the beam gains over the departure power angular spectrum of
  TR 38.901 clause 7.5 (wrapped-Gaussian ASD, Laplacian ZSD with the ZOD offset of Tables 7.5-6 to 7.5-8, a
  LOS ray with K = 9 dB); `protocol.meas_detail: 3gpp` gives the TS 38.133 measurement periods F_0 = M_1
  (TS 38.331 5.5.3.2) and per-beam averaging before the cell quality (TS 38.300 9.2.4); the in-vehicle
  penetration loss of TR 38.901 7.4.3.2 is documented with the existing `radio.penetration_db` 9 /
  `penetration_sd_db` 5; `radio.blockage: a` adds blockage model A of TR 38.901 7.6.4.1. None improves the
  judged rows: the angular spread lowers the 8-beam SINR by about 5 dB (the likely cause of its 6 dB optimism; the registered cause test was not confirmed) but
  raises the failures 4-8 times, and fails its own check against the explicit procedure; the TS 38.133 periods
  cut ping-pongs but raise failures 1.6-1.9 times; the car loss changes no row (received power 8.7 dB lower);
  blockage costs about 37 % of the LOS links more than 3 dB (median about 16 dB) but moves the FR2 SINR by about 0.4 dB. Remaining
  gaps: multi-beam SINR about 6 dB optimistic (a faithful fix needs beams on the per-ray channel) and FR2
  about 6 dB optimistic. Re-tests on data used before, no hold-out; no change of defaults or results.
- **2.9.0**: a comparison with real network data
  ([real data](https://github.com/mjs19971997/handoverlab/blob/main/docs/real-data.md)): HandoverLab 2.8.0
  against four public LTE/5G drive-test datasets with quantities and pass criteria registered before the
  first number, and four registered re-tests. The default passes the NR SS-SINR distribution, the
  preparation delay and the walking handover rate, but on the urban macro card it changes cell 4-10 times
  too often per km and has a larger margin at the handover command. Two new options, off by default:
  `radio.los_process: poisson_lines` gives the LOS state itself the correlation distance of TR 38.901
  Table 7.6.3.1-2, and `radio.beams.ssb_sinr: ssb` takes the SS-SINR of beam cells over the SSS resource
  elements with the neighbours' colliding SSBs (TS 38.215 5.1.5). Documented settings closer to deployed
  networks (sector antennas of TR 38.901 Table 7.8-1, published A3 offsets): the best of them passes 5 of 10
  judged rows instead of 2, within twice the default's failure rate; a sector setting with eight SSB beams
  stays about 6 dB optimistic in SINR, cause open. Re-tests on data used before, nothing fitted, no change of
  defaults or results.
- **2.8.0**: an option for time-varying, load-dependent interference on radio-link monitoring,
  `protocol.rlm_interference: dynamic` (default `static`; keys `rlm_rs_type`, `rlm_ssb_overlap`,
  `rlm_bg_se`), built from the 3GPP texts: every neighbour's activity comes from FTP-style burst traffic
  (TR 36.814 A.2.1.3, TR 36.872 A.1.1) at the cell's load, and the SINR is taken over the RLM-RS resource
  elements (TS 38.215 5.1.5, 5.1.6), with SSB or CSI-RS as the RLM-RS (TS 38.133 8.1.1) and the SSB overlap as
  a parameter. 3GPP does not fix the RLM-RS choice, whether neighbour SSBs overlap, or the SINR-to-BLER
  mapping; across the first two the failure level moves, in sample, from far below ns-3 (CSI-RS, light
  traffic) to 2.8-15 times ns-3 (aligned SSBs). It is a sensitivity option, **not validated** and not a
  default. On `urban-grid-10ghz`, A3 against CHO, the order of the rules is unchanged in every variant and on
  every seed (CHO has fewer failures, with one tie, and less outage), but the size of the failure gap changes
  by up to 12 times: report results for the RLM configuration you assume. The absolute failure level stays not calibrated; making the
  option the default would need field data, not ns-3
  ([calibration](https://github.com/mjs19971997/handoverlab/blob/main/docs/calibration.md#dynamic-interference-on-link-monitoring)).
  No change of results.
- **2.7.0**: an ns-3-like option (`handoverlab.verify.ns3.NS3_LIKE_SETTING`, `--ns3-like`; not a default)
  that imitates how ns-3 / 5G-LENA v5.1 declares a radio-link failure: out-of-sync after 200 control
  receptions below Qout (0.65-0.9 s, against about 200 ms in TS 38.133) and a handover command during T310
  counted as a failure. Frozen before the fresh, pre-registered ns-3 set V4 was opened, it is **not
  validated** on V4: level 1.03, right at time-to-trigger 1280 ms (1.07) but far too low at 128 ms (0.03),
  and the handover-rate check fails (0.759, limit 0.8). On V4 the ns-3 comparison setting passes the checks
  (level 0.73), its first pass, so 1 of 4 fresh sets; the absolute failure level stays not calibrated
  ([V4](https://github.com/mjs19971997/handoverlab/blob/main/docs/calibration.md#v4-the-ns-3-like-setting-on-a-fresh-set)). No change of results.
- **2.6.0**: a bridge to ns-3 / 5G-LENA (`handoverlab ns3 export|import|compare`) that writes a ready-to-run
  ns-3 package for a study, reads its results back and applies the checks of the ns-3 studies
  ([guide](https://github.com/mjs19971997/handoverlab/blob/main/docs/guides/ns3-bridge.md)). It found an error in 2.5.0: the failure counts of
  HandoverLab covered 90 s against 120 s of ns-3. Corrected, the ns-3 comparison setting passes the
  pre-registered checks on none of the three fresh ns-3 sets (level 0.52, 1.31 with rank 0.62, 0.64): the
  absolute failure level is not calibrated ([correction](https://github.com/mjs19971997/handoverlab/blob/main/docs/calibration.md#correction-in-260-equal-run-lengths)). Handover-rate comparisons were not
  affected. No change of results.
- **2.5.0** (corrected in 2.6.0): an independent, pre-registered [validation study](https://github.com/mjs19971997/handoverlab/blob/main/docs/calibration.md#independent-validation-study-250). On 40
  fresh ns-3 runs (V1, TTT 80 and 320 ms) the ns-3 comparison setting was reported to pass the
  pre-registered checks (level 0.97, order 0.88); this compared 90 s of HandoverLab with 120 s of ns-3, and
  with equal run lengths it fails the order on V1 (rank 0.62) and the level on N3 and V3 (0.52, 0.64), so it
  is not validated. It is documented as code (`handoverlab.verify.ns3.COMPARISON_SETTING`,
  `verify --ns3 --ns3-comparison`; not a default). Tuned on one card and tested on four unseen cards and
  seeds, `a3_mro` and `dqn` kept fewer unnecessary handovers than tuned A3; `a3_bandit` met the criteria
  only formally (more unnecessary handovers and ping-pong); `a3_pred` did not generalise. Limits of this
  design: with 5 seeds the smallest two-sided Wilcoxon p is 0.0625, so the no-harm check could not fail, and
  `fr3-urban-15ghz` is the training grid at another frequency, so it is the least independent test card
  ([V2](https://github.com/mjs19971997/handoverlab/blob/main/docs/calibration.md#v2-do-the-adaptive-and-learning-rules-generalise)). No change of results.
- **2.4.0**: UE receive beams (panels of TR 38.802, best beam or a sweep); a measurement-prediction rule after
  TR 38.744 (`a3_pred`: predicted Event A3 or measurement skipping, sample and hold or a trained ridge
  predictor); the slot scheduler as a compiled kernel (`run.backend: numba`, bit-identical; on the ns-3 card
  42 times (`rr`) and 93 times (`pf`) faster than the NumPy loop); the 7 GHz large-scale calibration against the companies of R1-2506406 (every percentile inside the
  range, the distance to the mean criterion missed); a [comparison with other simulators](https://github.com/mjs19971997/handoverlab/blob/main/docs/comparison.md).
- **2.3.0**: user-plane buffers at handover (PDCP / RLC, Xn data forwarding for baseline, conditional, DAPS and
  L1/L2-triggered handover); the TR 37.885 urban macro grid, suburban macro (SMa) and O2I penetration of indoor
  users; a high-speed train card from TR 38.854; dual connectivity (TS 37.340: SN addition, PSCell change, SN
  release, SCG failure); a fresh held-out check of the failure model against new ns-3 runs, reported as it
  came.
- **2.2.0**: TDL fast fading of TR 38.901 with an effective SINR for link monitoring and rate; a slot scheduler
  with the MCS, TBS and HARQ of TS 38.214; checked against ns-3 runs with fading.
- **2.1.0**: a clause-by-clause audit against the full 3GPP texts (`protocol.rrc_detail`,
  `radio.channel_detail`), value domains from the standards and a study gate that checks them.
- **2.0.0**: satellites (non-terrestrial networks): one LEO satellite at 600 km with 19 earth-moving beams
  (TR 38.811 channel, TR 38.821 Set-1 S band), conditional handover with the location event D2 of TS 38.331
  Release 18 (`cho_d2`), checked against the link budgets of TR 38.821 (within 0.03 dB). The 3GPP values
  become the defaults: the protocol profile of 1.9.0, the urban vehicles of TR 37.885 (`v60`), and
  c = 3.0e8 m/s and the 10 m applicability range in the path loss of TR 38.901; the deprecated highway card
  is removed. `LEGACY_1X` reproduces all 33 golden runs of 1.x bit for bit.
- **1.12.0**: radio maps from a file (`radio.map_file`): the path gain of every site and pixel from a ray
  tracer (TR 38.901 clause 8, map-based hybrid model) or interpolated from measurements, with the error on
  held-out points; an exported street-grid map gives the same event log bit for bit.
- **1.11.0**: the TR 37.885 highway as specified (wrap-around, LOS-only base-station-to-vehicle
  links, sites on one side 1732 m apart below 6 GHz, 19 hexagonal sites with 3 sectors above), checked
  against an independent computation; every scenario card audited against TR 38.901 (also against
  V19.5.0), TR 37.885, TR 36.885 and ITU-R M.2412, with two cards corrected and the old highway card
  deprecated; `a3_bandit` against an exhaustive search (two of three criteria met, reported as is);
  the rule `dqn` with optional PyTorch; an optional Numba kernel with identical results.
- **1.10.0**: SSB beams per sector with beam management and beam failure recovery (TS 38.321 5.17,
  TS 38.133 8.5), several carriers with inter-frequency measurements in gaps and Event A5, the
  measurement and RLM evaluation periods of TS 38.133, and DAPS and LTM checked against TS 38.133
  and published 3GPP evaluations. Three sectors per site bring the mid-band handover counts into the
  range measured in commercial networks; a two-layer deployment alone does not.
- **1.9.0**: the 3GPP protocol profile (handover command received during T310 and T304 as in
  TS 38.331), a clause-by-clause standard-compliance page, a fresh ns-3 hold-out and a comparison
  with commercial 5G measurements.
- **1.8.0**: the radio model calibrated against 3GPP: the large-scale calibration of TR 38.901
  clause 7.8.1 against the 21 companies of R1-165974, as the `verify` group `calibration`.
- **1.7.0**: indoor office (TR 38.901 InH) and rural (RMa) scenarios with the IMT-2020 link
  budgets, the optional soft LOS state of TR 38.901, and the rule `a3_mro` (mobility robustness
  optimisation of a cell individual offset per cell pair).
- **1.6.0**: conditional LTM (rule `cltm`), from the Release 19 work on L1/L2-triggered mobility.
- **1.5.0**: signalling and energy metrics (RRC messages, handover commands, L1 measurements,
  site power and energy per bit); why failure rates differ from ns-3, stated in the README.
- **1.4.0**: traffic models per user (`traffic.model`: full buffer, periodic, FTP model 3); a
  dashboard with confidence intervals, a map of where handovers and failures happen, and the status
  of a running study; the ns-3 link-monitoring finding in the calibration report.
- **1.3.0**: optional restart of the link monitoring on a newly joined cell (an interpretation of TS 38.133 8.1.2.2).
- **1.2.0**: optional penetration loss per user; the ns-3 comparison with the in-car loss of ns-3.
- **1.1.0 / 1.1.1**: optional link-monitoring model; held-back ns-3 results; issue forms, CI on
  Windows for every test.

Earlier versions and every detail: the [changelog](https://github.com/mjs19971997/handoverlab/blob/main/CHANGELOG.md).

## Install

HandoverLab needs Python 3.9 or later. NumPy, SciPy and PyYAML are installed with it; matplotlib
(reports, extra `report`), pyarrow (Parquet tables, extra `parquet`), Streamlit (the dashboard,
extra `gui`) and MkDocs (the documentation site, extra `docs`) are optional.

From PyPI:

```bash
python -m pip install handoverlab                  # the core package
python -m pip install "handoverlab[report,gui]"    # with reports and the dashboard
handoverlab verify --only pathloss fingerprints    # optional: a quick check of the installation
```

From source (for development, the tests and the examples):

```bash
git clone https://github.com/mjs19971997/handoverlab.git
cd handoverlab
python -m pip install -e ".[test,report]"    # add gui for the dashboard: ".[test,report,gui]"
python -m pytest            # optional: run the tests (a few minutes)
handoverlab verify          # optional: verification report (about two minutes)
```

## Quick start

Write an example configuration and run it:

```bash
handoverlab init config.yaml
handoverlab run config.yaml -o results/metrics.csv
```

`run` writes one row per seed and rule with all metrics and the fingerprint of the event log, to
CSV or (with a `.json` output name) to JSON together with the resolved scenario and the package
versions. `handoverlab rules` lists the available rules and `handoverlab scenarios` the built-in
scenarios (`scenario: smoke` in a configuration uses one). Configurations can be YAML, TOML or JSON;
see [examples/](https://github.com/mjs19971997/handoverlab/tree/main/examples).

A whole study, with tuning, gates, paired tests and a report (a few minutes):

```bash
handoverlab study examples/study_smoke.yaml --workers 2 --report
```

The report lands in `results/study-smoke/report/` (`report.html`, `report.md`, figures);
re-running the command skips everything that is already done, and `handoverlab status
results/study-smoke` shows what is left and how long it will take.

Or explore in the browser:

```bash
python -m pip install "handoverlab[gui]"
handoverlab gui                      # http://localhost:8501, on your computer only
```

## Example

```python
import handoverlab as hl

scenario = hl.Scenario.from_dict({
    "layout": {"kind": "street_grid", "blocks": [3, 3], "site_spacing_m": 150.0},
    "mobility": {"users": 20, "profile": "v60"},
    "run": {"duration_s": 60.0, "warmup_s": 10.0},
})
rules = [
    {"rule": "a3", "name": "A3", "off_db": 3.0, "ttt_s": 0.16},
    {"rule": "cho", "name": "CHO", "o_prep_db": -2.0, "o_exec_db": 3.0, "ttt_exec_s": 0.08},
]
for r in hl.simulate(scenario, rules, seeds=[1]):      # both rules run on the same world
    print(r.rule, r.metrics["handovers_pm"], r.metrics["unnecessary_pm"], r.metrics["failures_pm"])
```

Sample output of [examples/traffic_models.py](https://github.com/mjs19971997/handoverlab/blob/main/examples/traffic_models.py), the same rule under the four
traffic models (one seed, 30 users, 60 s on the urban grid at 10 GHz):

```text
model        cell load  rate [Mbit/s]  delivered  SINR [dB]  failures/UE-min
fixed             0.28          14.10       0.97       23.6             0.08
full_buffer       0.52         717.77       0.48       21.2             0.08
periodic          0.28           0.04       0.86       23.7             0.08
ftp3              0.28           3.93       0.87       23.7             0.08
```

Busier cells interfere more: under full buffer the SINR drops by about 2.4 dB. With one seed each
failure rate counts only a few failures; compare them over several seeds.

The full script is [examples/compare_a3_cho.py](https://github.com/mjs19971997/handoverlab/blob/main/examples/compare_a3_cho.py). Writing your own
handover rule takes a few lines; see the [user guide](https://github.com/mjs19971997/handoverlab/blob/main/docs/user_guide.md).

## Documentation

The documentation site is at **<https://mjs19971997.github.io/handoverlab/>**. It is a MkDocs site (`python -m pip install -e ".[docs]"`, then `mkdocs serve`);
the pages are plain Markdown in [docs/](https://github.com/mjs19971997/handoverlab/tree/main/docs) and readable on GitHub as well.

- Tutorials: [your first run](https://github.com/mjs19971997/handoverlab/blob/main/docs/tutorials/first-run.md),
  [writing your own rule](https://github.com/mjs19971997/handoverlab/blob/main/docs/tutorials/own-rule.md),
  [a fair tuning study](https://github.com/mjs19971997/handoverlab/blob/main/docs/tutorials/tuning-study.md),
  [reading the report](https://github.com/mjs19971997/handoverlab/blob/main/docs/tutorials/reading-the-report.md).
- [User guide](https://github.com/mjs19971997/handoverlab/blob/main/docs/user_guide.md): concepts, scenarios, configuration keys, command line, Python
  API, rule plug-ins and their contract checks, event logs and their levels, verification, metrics,
  studies (tuning, gates, storage, workers, status, reports), paired statistics, limitations.
- How-to guides: [dashboard](https://github.com/mjs19971997/handoverlab/blob/main/docs/guides/dashboard.md), [add a scenario](https://github.com/mjs19971997/handoverlab/blob/main/docs/guides/add-scenario.md),
  [run on many cores](https://github.com/mjs19971997/handoverlab/blob/main/docs/guides/many-cores.md), [export event logs](https://github.com/mjs19971997/handoverlab/blob/main/docs/guides/export-event-logs.md),
  [reproduce and check results](https://github.com/mjs19971997/handoverlab/blob/main/docs/guides/reproduce.md), [DAPS and LTM](https://github.com/mjs19971997/handoverlab/blob/main/docs/guides/daps-ltm.md),
  [a learning-based rule](https://github.com/mjs19971997/handoverlab/blob/main/docs/guides/learning-rule.md), [the upper mid-band](https://github.com/mjs19971997/handoverlab/blob/main/docs/guides/upper-mid-band.md),
  [a highway](https://github.com/mjs19971997/handoverlab/blob/main/docs/guides/highway.md), [your own radio map](https://github.com/mjs19971997/handoverlab/blob/main/docs/guides/radio-maps.md),
  [a LEO satellite](https://github.com/mjs19971997/handoverlab/blob/main/docs/guides/ntn.md), [moving from 1.x to 2.0](https://github.com/mjs19971997/handoverlab/blob/main/docs/migration-2.0.md).
- Reference: [command line](https://github.com/mjs19971997/handoverlab/blob/main/docs/reference/cli.md), [metric names](https://github.com/mjs19971997/handoverlab/blob/main/docs/reference/metrics.md) and the
  API (generated from the docstrings, in the site); [stability policy](https://github.com/mjs19971997/handoverlab/blob/main/docs/stability.md).
- [Scenario cards](https://github.com/mjs19971997/handoverlab/tree/main/docs/scenarios): the built-in scenarios with the source of every parameter.
- [Verification](https://github.com/mjs19971997/handoverlab/blob/main/docs/verification.md), [failure-model calibration](https://github.com/mjs19971997/handoverlab/blob/main/docs/calibration.md) and
  [performance](https://github.com/mjs19971997/handoverlab/blob/main/docs/performance.md).
- [Comparison with other simulators](https://github.com/mjs19971997/handoverlab/blob/main/docs/comparison.md): ns-3 with 5G-LENA
  and the mmWave module, Simu5G, the Vienna 5G System Level Simulator, the MATLAB 5G Toolbox, OpenAirInterface
  and Sionna on handover procedures, failure model, NTN, beams, PHY abstraction, scheduler, scale and validation,
  each cell with its source, including where the other tools are stronger.
- [Changelog](https://github.com/mjs19971997/handoverlab/blob/main/CHANGELOG.md), [contribution guide](https://github.com/mjs19971997/handoverlab/blob/main/CONTRIBUTING.md) and [releasing](https://github.com/mjs19971997/handoverlab/blob/main/docs/RELEASING.md).

## Roadmap

1. Stage 1 (0.1.0a1): core simulator, configuration, rule interface, command line, tests.
2. Stage 2 (0.2.0a1): verification in depth (invariant checks, golden event-log fingerprints, radio
   statistics, rule contract test kit, wider bh6 regression, ns-3 reference case), event logs as
   tables, the `verify` command, scenario cards, a faster world build.
3. Stage 3 (0.3.0a1): studies: equal-budget tuning with automatic gates, the selection rule, paired
   statistics, job records and Parquet tables, resumable studies with reused runs, worker
   processes, `study` and `report` commands, batched engines.
4. Stage 4 (0.4.0a1): browser dashboard (extra `gui`), tutorials, API and command-line
   reference with a documentation site, event-log levels, `status` with the time left, the
   grid-edge policy `extend`, failure-model calibration against ns-3 / 5G-LENA.
5. Stage 5 (1.0.0rc1): the public interfaces frozen and documented with a
   schema version (configuration, results, rule interface, metric names) and a stability policy;
   how-to guides; a lint job and a coverage threshold in CI; a nightly comparison of fingerprints
   between Linux and Windows; release plumbing for PyPI and Zenodo.
6. Stage 6 (1.0.0rc2): DAPS handover, L1/L2-triggered mobility, a learning-based
   example rule and an upper mid-band scenario, all additive.
7. Stage 7 (1.0.0rc3): a highway layout with lane-keeping vehicular mobility and its scenario
   card, site lists from CSV files, all additive.
8. Stage 8 (1.0.0rc4): the 3GPP citations and the documentation checked and
   corrected; no change of results.
9. 1.0.0: the first stable release, published on PyPI.
10. 1.0.1: the dashboard image shows on the PyPI project page; no change of results.
11. 1.0.2: README links work on PyPI, the documentation site is linked, text corrections; no change
    of results.
12. 1.1.0-1.3.0: optional link-monitoring and penetration-loss models traced against ns-3; issue
    forms and CI for every test on Windows.
13. 1.4.0: traffic models per user, a richer dashboard, pictures in the README.
14. 1.5.0: signalling and energy metrics.
15. 1.6.0: conditional LTM.
16. 1.7.0: indoor and rural scenarios; mobility robustness optimisation.
17. 1.8.0: the radio model calibrated against 3GPP (TR 38.901 clause 7.8.1).
18. 1.9.0: the 3GPP protocol profile and the standard-compliance page.
19. 1.10.0: SSB beams and beam failure recovery, several carriers with measurement gaps, DAPS
    and LTM against TS 38.133 and published 3GPP evaluations.
20. 1.11.0: the TR 37.885 highway, the card audit, the bandit against an exhaustive search, the
    `dqn` rule and the optional Numba kernel.
21. 1.12.0: radio maps from ray tracing or measurements.
22. 2.0.0: a LEO satellite with earth-moving beams and conditional handover with
    event D2; the 3GPP values as defaults, with a switch back to 1.x.
23. 2.1.0: the clause-by-clause standard audit; held-out validation of the failure model, the
    time-step study, the ns-3 benchmark package and the table of model boundaries.
24. 2.2.0: fast fading with link-to-system mapping; the slot scheduler with MCS, TBS and HARQ.
25. 2.3.0: buffers at handover, urban macro, SMa and O2I, the high-speed train, dual connectivity.
26. 2.4.0: UE receive beams, the TR 38.744 prediction rule, the compiled
    scheduler, the 7 GHz calibration and the comparison with other simulators.
27. 2.4.1: pictures, citation and tutorials brought up to date; the example study
    completes again; no change of results.
28. 2.4.2: every option has a picture; the dashboard pictures show the current version;
    guide and tutorial examples rerun; facts made consistent; no change of results.
29. 2.5.0: an independent, pre-registered validation study: the ns-3 comparison setting for the
    failure level (its pass on V1 was corrected in 2.6.0: not validated), and the generalisation of the
    adaptive and learning rules to unseen cards and seeds; no change of results.
30. 2.6.0: the bridge to ns-3 / 5G-LENA (export, import, compare); the correction of the
    2.5.0 failure-level comparison (equal run lengths: the absolute failure level is not calibrated); no
    change of results.
31. 2.7.0: the ns-3-like option (not a default), judged on the fresh ns-3 set V4 and not
    validated (right at long time-to-trigger, far too few failures at short); no change of results.
32. 2.8.0: dynamic, load-dependent interference on radio-link monitoring from the 3GPP
    texts, a sensitivity option (not a default, not validated); no change of results.
33. 2.9.0: the comparison with real network data, the LOS-state process and SS-SINR
    options (not defaults) and documented settings closer to deployed networks; no change of results.
34. **2.10.0 (this release)**: angular spread at the beams, TS 38.133 measurement detail, in-vehicle
    penetration loss and blockage model A from the 3GPP texts (not defaults), re-tested against the real
    data: none improves it; no change of results.
35. Later (planned, not done), staying a handover simulator: why HandoverLab has too few failures at short
    time-to-trigger under the ns-3-like detection; field data on radio-link failures, which a link-monitoring
    interference model would need before it could become a default; the effect of a handover on what the user
    sees (simple TCP and application models on top of the buffers), MIMO as an SINR gain and hundreds of
    users per run; condEventT1 and earth-fixed beams.

## Citation

If you use HandoverLab, please cite it as described in [CITATION.cff](https://github.com/mjs19971997/handoverlab/blob/main/CITATION.cff) (GitHub shows
it under *Cite this repository*). Every release is archived on Zenodo:
[doi:10.5281/zenodo.23409131](https://doi.org/10.5281/zenodo.23409131) cites all versions (it resolves to
the latest). To cite the exact version you used, take its DOI from the version list on that page, where
the DOI of the latest version is listed; for example, version 2.4.2 is
[doi:10.5281/zenodo.23589215](https://doi.org/10.5281/zenodo.23589215), version 2.4.1
[doi:10.5281/zenodo.23585308](https://doi.org/10.5281/zenodo.23585308) and version 2.4.0
[doi:10.5281/zenodo.23582521](https://doi.org/10.5281/zenodo.23582521). The BibTeX entry below cites 2.4.2;
replace version and DOI with those of the version you used.

```bibtex
@software{handoverlab,
  author    = {Jalili Sanjarani, Mostafa and Elmi Sola, Yasser},
  title     = {{HandoverLab}: system-level handover simulator for 5G-Advanced and beyond-5G research},
  year      = {2026},
  publisher = {Zenodo},
  version   = {2.4.2},
  doi       = {10.5281/zenodo.23589215},
  url       = {https://github.com/mjs19971997/handoverlab}
}
```

## Licence

MIT. See [LICENSE](https://github.com/mjs19971997/handoverlab/blob/main/LICENSE).

## Authors

Mostafa Jalili Sanjarani and Yasser Elmi Sola
