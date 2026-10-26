# Comparison with other simulators

This page sets HandoverLab 2.8.0 next to other open or widely used 5G simulators and emulators, on the points
that matter for handover and mobility studies. It is meant to help you pick the right tool for a question, not
to rank tools: most of them were built for other questions, and several are far more detailed than HandoverLab
in layers that HandoverLab abstracts.

**How the table was made.** Every cell about another tool comes from that project's own documentation,
repository (README, docs, source tree, release notes) or its peer-reviewed paper; the source labels in brackets
point to the [list of sources](#sources), all accessed on 2026-10-22. **"not stated"** means the fact was not found
in those sources; it does not prove that the feature is absent, and a later release may add it. Corrections are
welcome as issues. The HandoverLab column follows the code and the pages of this site for version 2.8.0.

Tools compared (latest release found on 2026-10-22):

| Tool | Kind | Latest release | Licence | Language |
|---|---|---|---|---|
| HandoverLab | system-level, procedure-centred, time-stepped | 2.8.0 (2026-10-26) | MIT | Python (optional Numba kernel) |
| ns-3 with 5G-LENA (`nr` module) | packet-level, end-to-end, discrete-event | v5.1 (2026-08-06, ns-3.48) [L5] | GPLv2 [L6] | C++ [L6] |
| ns-3 mmWave module (NYU / UniPD) | packet-level, end-to-end, discrete-event | v8.0 (2024-06-26, ns-3.42) [M2] | GPL-2.0 [M1] | C++ [M1] |
| Simu5G (OMNeT++ / INET) | packet-level, end-to-end, discrete-event; real-time emulation | 1.8.0 (2026-10-07) [S2] | LGPL-3.0 [S7] | C++ and NED [S1] |
| Vienna 5G System Level Simulator | system-level, link abstraction from link-level curves | 1.4 (October 2023) [V3, V4] | academic use only, non-commercial [V5] | MATLAB [V2, V3] |
| MATLAB 5G Toolbox, system-level part | system-level with abstract or full PHY | R2026b (2026-09-24) [W12] | proprietary; nrGNB / nrUE also need the Wireless Network Toolbox since R2026a [W3, W13] | MATLAB |
| OpenAirInterface 5G RAN | real-time protocol stack (emulator with RF simulator, or real radios) | v3.0.0 (October 2026) [O4] | CSSL v1.0 (code) [O1] | C [O1] |
| NVIDIA Sionna (PHY, SYS, RT) | link-level library with a system-level part (SYS), GPU | v2.2.0 (2026-09-29) [N2] | Apache-2.0 [N1] | Python (PyTorch since 2.0.0) [N2] |

## Handover and mobility procedures

| Tool | Event A3 / RRC handover | CHO | DAPS | LTM | Radio-link failure | Dual connectivity |
|---|---|---|---|---|---|---|
| HandoverLab 2.8.0 | yes: report, preparation, command, execution; A5 between carriers; a rule on predicted measurements after TR 38.744 ([AI/ML mobility](guides/ai-mobility.md)) | yes (Rel-16, up to 8 candidates; D1/D2 for NTN) | yes | yes, and conditional LTM | Qout/Qin as SINR thresholds with windows (or the MIESM effective SINR of the hypothetical PDCCH with fading), N310/N311/T310, T304, command during T310, re-establishment after a fixed outage; absolute failure rates are not calibrated | NR-DC as an option: SN addition, PSCell change, SN release, SCG failure; no EN-DC |
| ns-3 5G-LENA v5.1 | yes: X2-based, intra- and inter-frequency, A3 and A2-A4 algorithms, CIO; TTT scaling and ping-pong guards in v5.1 [L2, L3, L5] | not stated | not stated | not stated | Qout/Qin from the hypothetical-PDCCH BLER, N310/N311/T310, re-establishment; optional TR 36.839 handover-failure model (v5.1) [L2, L4, L5] | no: "out of scope and is future work" [L3] |
| ns-3 mmWave v8.0 | mmWave secondary-cell switch coordinated by the LTE eNB (SINR difference with fixed or dynamic TTT), not an A3 configuration as such [M1, M4, M5] | not stated | not stated | not stated | mmWave outage by an SINR threshold; T310/N310: not stated [M4] | LTE-mmWave DC (LTE master, mmWave secondary) [M1, M5]; NR-DC: not stated |
| Simu5G 1.8.0 | yes: Xn-prepared handover on a measurement report with the best cell, hysteresis on RSSI; A3 with TTT: not stated [S3, S4] | not stated | not stated | not stated | RLF when an RLC AM PDU exceeds its retransmission limit, RRC re-establishment (T311 = 0 disables it by default); T310/N310: not stated [S2] | EN-DC and NE-DC with split bearers [S1, S6]; NR-DC: not stated |
| Vienna 5G SLS 1.4 | no handover procedure described; cell association by received power or SINR, fixed per segment [V1] | not stated | not stated | not stated | not stated; "we omit the implementation of the complete protocol stack" [V1] | not stated |
| MATLAB 5G Toolbox R2026b | not stated; UE mobility models exist, the mobility example uses one gNB [W4, W6, W7] | not stated | not stated | not stated | not stated; the node stack is traffic, RLC, MAC and PHY [W5] | not stated; carrier aggregation since R2026b [W10] |
| OpenAirInterface v3.0.0 | yes: A3 or manual triggers, intra-/inter-frequency, F1 inter-DU and N2 inter-gNB [O2, O3, O4] | not stated | not stated | not stated | RLF declared by the MAC after a number of PUSCH DTX, RRC re-establishment; T310/N310: not stated [O4, O6] | EN-DC (NSA "unstable (only one UE connection)") and NR-DC [O2, O4] |
| Sionna v2.2.0 | no: the SYS tutorial excludes handover, users attach to the nearest base station [N6] | not stated | not stated | not stated | not stated | not stated |

## Radio, beams and PHY abstraction

| Tool | NTN | Beams | Fast fading and link-to-system mapping | Scheduler |
|---|---|---|---|---|
| HandoverLab 2.8.0 | one LEO satellite with earth-moving beams (TR 38.811, TR 38.821), CHO with D2; no several satellites, Doppler or earth-fixed beams ([NTN guide](guides/ntn.md)) | SSB beams per sector from the TR 38.901 element and DFT beams, cell quality from beams, beam failure detection and recovery; UE receive beams optional (1, 2 or 4 panels, [UE beams](guides/ue-beams.md)), isotropic UE by default; no MIMO ([beams](guides/beams-layers.md)) | off by default (large-scale channel with a slow time-varying part); option: TDL-A to TDL-E with MIESM for link monitoring and a capacity-equivalent SINR for the rate; no CDL ([fading](guides/fading.md)) | by default a rate model without a scheduler; option: slot scheduler RR or PF with MCS, TBS and HARQ (base engine only; with `run.backend: numba` bit-identical and, on the ns-3 card, 42 (`rr`) and 93 (`pf`) times faster than its NumPy loop) ([scheduler](guides/scheduler.md)) |
| ns-3 5G-LENA v5.1 | NTN channel (TR 38.811, from ns-3 mainline [L9]) and a LEO mobility example [L1, L2] | ideal and SRS-based realistic beamforming; beam management "Simplified model; no SSB blocks" [L1]; quasi-omni beams in the RRC / handover context [L3] | TR 38.901 with fast fading; EESM-based PHY abstraction with SINR-BLER tables [L1, L8] | PF, RR, MR, QoS-aware, RL-based; OFDMA and TDMA [L1] |
| ns-3 mmWave v8.0 | TR 38.811 channel inherited from ns-3.42; no NTN protocol features stated [M2] | SVD- and DFT-based beamforming; NR beam tracking listed as future work [M1, M3] | TR 38.901 channel, ray-tracing and measured traces; EESM error model from 5G-LENA [M1, M3] | flexible-TTI RR, PF, max-rate, max-weight [M1] |
| Simu5G 1.8.0 | not in the official release; separate third-party work exists [S10] | not stated; antenna-gain link budget only [S1] | path loss, LOS and shadowing of TR 36.814 / 36.873 / 38.901 with Jakes or Rayleigh fading; reception from SINR and BLER curves [S5, S6] | MAX C/I, PF, DRR, QoS-aware PF [S1] |
| Vienna 5G SLS 1.4 | not stated | precoding and MIMO (CLSM / OLSM, MU-MIMO); no beam-management procedure described [V1, V2] | small-scale fading per slot (TR 38.901 CDL, PDP models, QuaDRiGa interface); post-equalisation SINR mapped to BLER with tables from the Vienna link-level simulator [V1, V2] | RR, best CQI, weighted RR, QoS-aware, ZF MU-MIMO [V2] |
| MATLAB 5G Toolbox R2026b | system-level LEO transparent-payload example with static satellite and UEs, no handover (R2026b) [W8] | system-level example with P-2 beam measurement and reporting, without SSB sweeping [W9] | CDL, TR 38.901 system-level channel or custom; abstract PHY (RBIR mapping and lookup tables) or full PHY [W2, W4, W5] | RR, PF, best CQI and custom schedulers [W2] |
| OpenAirInterface v3.0.0 | GEO and LEO transparent satellites; RF simulator with LEO delay and Doppler [O5, O10] | basic FR2 beam management; analog beamforming; beam gains in the RF simulator [O4, O7, O8] | full PHY on time-domain samples; channel simulator with TR 36.873 / 38.901 models; no abstraction needed [O8, O9] | proportional fair [O2, O6] |
| Sionna v2.2.0 | not stated; the official 3GPP channel page lists TDL, CDL, UMi, UMa, RMa, InH and InF [N7] | TR 38.901 panel arrays; beam management: not stated [N6] | TR 38.901 TDL, CDL, UMi, UMa, RMa, InH, InF; PHY abstraction with EESM and BLER tables [N4, N7] | PF for single-user MIMO; link adaptation and power control [N3, N5] |

## Speed, scale and validation

| Tool | Speed and scale | Validation against 3GPP |
|---|---|---|
| HandoverLab 2.8.0 | one process: 2 rules, 40 users, 76 cells, 60 s simulated in 10-15 s on a modest virtual machine (1.11.0 timings, [performance](performance.md)); many rules share one world; no published figures for thousands of nodes | large-scale calibration of TR 38.901 clause 7.8.1 against the 21 companies of R1-165974 (325 of 342 percentiles inside the range) and against R1-2506406 (at 7 GHz all 228 percentiles of UMa, UMi and SMa inside the company range, largest distance from the company mean 1.69-2.43 dB; with the two 6 GHz reruns 342 percentiles, 1.65-2.88 dB, [details](calibration-3gpp.md)); handover counts against ns-3 / 5G-LENA; failure level not calibrated: over equal run lengths the defaults give 0.17-0.32 of ns-3's and the comparison setting 0.5-1.3, passing the pre-registered checks on 1 of 4 fresh sets (V4; corrected in 2.6.0, [calibration](calibration.md)); the ns-3-like option of 2.7.0 is not validated, and the dynamic link-monitoring interference of 2.8.0 is a sensitivity option, not validated; clause-by-clause [standard compliance](standard-compliance.md) |
| ns-3 5G-LENA v5.1 | runtime numbers: not stated for the module; a MIMO channel speed-up of up to 16 times is reported in a WNS3 paper [L11]; the calibration scenario has 12 gNBs and 120 UEs [L10] | calibrated in 3GPP outdoor reference scenarios (SIMPAT 2022) [L7]; calibration examples for RP-180524 [L2]; mobility checked against TR 36.839 (v5.1) [L5] |
| ns-3 mmWave v8.0 | not stated | not stated (examples "verify its correct functioning" [M6]) |
| Simu5G 1.8.0 | background cells and UEs for large scenarios; real-time emulation of "hundreds of simulated users and tens of cells" on one desktop [S1, S9] | PHY abstraction validated in 3GPP-based scenarios [S8]; fingerprint regression tests [S1] |
| Vienna 5G SLS 1.4 | "more than 7000 users" in less than 16 GB RAM for 100 slots; runs split over cores or a cluster [V1] | not stated (TR 38.901 channels implemented; no calibration reported) [V1] |
| MATLAB 5G Toolbox R2026b | no measured runtimes published; a full-PHY example with 19 sites of 3 sectors and 20 UEs per cell can need "several hundred gigabytes" of memory [W2, W14] | InH SINR CDF against RP-180524 and dense urban against R1-1715251 [W11] |
| OpenAirInterface v3.0.0 | real time; "up to 100 UEs" (v3.0.0) [O4]; 55 UEs in the stress test of the paper [O10] | not stated (CI over 4G, 5G NSA and SA) [O10] |
| Sionna v2.2.0 | GPU acceleration; runtime numbers: not stated [N1] | TR 38.901 channel models "Updated and calibrated" (v2.1.0) and calibration metrics in SYS [N2] |

## Where the other tools are stronger

- **Full protocol stacks and packets.** ns-3 with 5G-LENA or the mmWave module and Simu5G simulate every packet
  through RLC, PDCP, RRC, the core network, transport and applications [L10, M6, S6]. End-to-end latency,
  TCP behaviour during a handover, or application quality can be studied there and not in HandoverLab, which
  has no transport layer or applications (it has an optional PDCP buffer model at handover).
- **Real systems.** OpenAirInterface runs the real protocol stack in real time, with commercial UEs and core
  networks [O1, O3, O10]; results from it include implementation effects that no simulator has.
- **PHY detail.** MATLAB can switch the same network to a waveform-level full PHY [W4]; the Vienna simulator
  takes its BLER curves from a link-level simulator with several waveforms and codes [V1]; Sionna offers a
  differentiable link-level chain on GPUs and a ray tracer [N1]. HandoverLab has no MIMO and no CDL channel.
- **Scale.** The Vienna simulator reports thousands of nodes [V1]; Simu5G emulates tens of cells in real time
  [S9]. HandoverLab runs in one Python process per world and is sized for tens of cells and users per run.
- **Packet-level handover against the 3GPP mobility study.** 5G-LENA v5.1 can be checked against the TR 36.839
  handover-failure curves [L5], which matters because HandoverLab's absolute failure level is checked against ns-3 / 5G-LENA only: it is not calibrated. Over equal run lengths the ns-3 comparison setting (`handoverlab.verify.ns3.COMPARISON_SETTING`, with the in-car loss of ns-3) gives 0.52, 1.31, 0.64 and 0.73 of ns-3's level on the fresh sets N3, V1, V3 and V4 (on V1 the order of failures across cells fails, rank 0.62), so it passes the pre-registered checks on 1 of them (V4); the default link-monitoring model gives 0.18, 0.32, 0.17 and 0.27. The ns-3-like setting of 2.7.0 imitates ns-3's failure detection but is not validated on V4 (right at long time-to-trigger, far too few failures at short; [V4](calibration.md#v4-the-ns-3-like-setting-on-a-fresh-set)). 2.5.0 had reported a pass on V1 (0.97, rank 0.88) from an analysis with unequal run lengths
  ([calibration](calibration.md#correction-in-260-equal-run-lengths)).

## Where HandoverLab differs

- The Rel-16 to Rel-19 mobility procedures (CHO, DAPS, LTM, conditional LTM, CHO with D1/D2) sit side by side
  behind one rule interface; none of them is stated in the sources of the other tools above.
- Every compared rule runs on the same world per seed (paired comparison), and the cost of each procedure
  (signalling, prepared cells, interruption, energy) is measured next to its benefit.
- The price is abstraction: received power per step with a slow time-varying part by default, SINR thresholds
  for link monitoring, fixed procedure delays and a fixed re-establishment outage. The
  [model boundaries](https://github.com/mjs19971997/handoverlab#model-boundaries) and
  [standard compliance](standard-compliance.md) say what this supports.

## Sources

All accessed on 2026-10-22.

**HandoverLab:** the pages linked above and `CHANGELOG.md` of 2.5.0.

**ns-3 5G-LENA**

- [L1] 5G-LENA features: <https://5g-lena.cttc.es/features/>
- [L2] `nr` release notes: <https://gitlab.com/cttc-lena/nr/-/raw/master/RELEASE_NOTES.md>
- [L3] `nr` RRC layer documentation: <https://gitlab.com/cttc-lena/nr/-/raw/master/doc/source/rrc-layer.rst>
- [L4] `nr` source, UE RRC and PHY (master branch): <https://gitlab.com/cttc-lena/nr/-/raw/master/model/nr-ue-rrc.cc>,
  <https://gitlab.com/cttc-lena/nr/-/raw/master/model/nr-ue-phy.cc>
- [L5] 5G-LENA v5.1 announcement: <https://5g-lena.cttc.es/blog/36/>
- [L6] `nr` documentation: <https://cttc-lena.gitlab.io/nr/html/>
- [L7] K. Koutlia, B. Bojovic, Z. Ali, S. Lagén, "Calibration of the 5G-LENA system level simulator in 3GPP
  reference scenarios", Simulation Modelling Practice and Theory 119 (2022) 102580,
  <https://doi.org/10.1016/j.simpat.2022.102580>
- [L8] S. Lagén et al., "New radio physical layer abstraction for system-level simulations of 5G networks",
  IEEE ICC 2020, <https://doi.org/10.1109/ICC40277.2020.9149444>
- [L9] M. Sandri et al., "Implementation of a channel model for non-terrestrial networks in ns-3", WNS3 2023,
  <https://doi.org/10.1145/3592149.3592158>
- [L10] N. Patriciello et al., "An E2E simulator for 5G NR networks", Simulation Modelling Practice and Theory 96
  (2019) 101933, <https://doi.org/10.1016/j.simpat.2019.101933>
- [L11] M. Pagin et al., "Improving the efficiency of MIMO simulations in ns-3", WNS3 2023,
  <https://doi.org/10.1145/3592149.3592167>

**ns-3 mmWave module**

- [M1] Repository and README: <https://github.com/nyuwireless-unipd/ns3-mmwave>
- [M2] Releases: <https://github.com/nyuwireless-unipd/ns3-mmwave/releases>
- [M3] Module documentation: <https://github.com/nyuwireless-unipd/ns3-mmwave/blob/new-handover/src/mmwave/doc/mmwave-doc.md>
- [M4] eNB and UE RRC source: <https://github.com/nyuwireless-unipd/ns3-mmwave/blob/new-handover/src/lte/model/lte-enb-rrc.cc>,
  <https://github.com/nyuwireless-unipd/ns3-mmwave/blob/new-handover/src/lte/model/lte-ue-rrc.cc>
- [M5] M. Polese et al., "Improved handover through dual connectivity in 5G mmWave mobile networks", IEEE JSAC
  35(9), 2017, <https://doi.org/10.1109/JSAC.2017.2720338>
- [M6] M. Mezzavilla et al., "End-to-end simulation of 5G mmWave networks", IEEE Communications Surveys &
  Tutorials 20(3), 2018, <https://doi.org/10.1109/COMST.2018.2828880>

**Simu5G**

- [S1] Repository and README: <https://github.com/Unipisa/Simu5G>
- [S2] Releases (1.6.0, 1.7.0, 1.8.0): <https://github.com/Unipisa/Simu5G/releases>
- [S3] What's new: <https://github.com/Unipisa/Simu5G/blob/master/WHATSNEW.md>
- [S4] UE connection control: <https://github.com/Unipisa/Simu5G/blob/master/src/simu5g/stack/rrc/ConnectionControlUe.ned>
- [S5] Stochastic channel model: <https://github.com/Unipisa/Simu5G/blob/master/src/simu5g/stack/phy/channelmodel/StochasticChannelModel.ned>
- [S6] Simu5G site and overview: <https://simu5g.org/>, <https://simu5g.org/users-guide/overview>
- [S7] Licence: <https://github.com/Unipisa/Simu5G/blob/master/LICENSE.md>
- [S8] G. Nardini et al., "Simu5G: an OMNeT++ library for end-to-end performance evaluation of 5G networks",
  IEEE Access 8, 2020, <https://doi.org/10.1109/ACCESS.2020.3028550>
- [S9] G. Nardini, G. Stea, A. Virdis, "Scalable real-time emulation of 5G networks with Simu5G", IEEE Access 9,
  2021, <https://doi.org/10.1109/ACCESS.2021.3123873>
- [S10] LEON, a LEO handover simulator built on OMNeT++, INET and Simu5G, DroNet 2024,
  <https://doi.org/10.1145/3661810.3663470>

**Vienna 5G System Level Simulator**

- [V1] M. K. Müller et al., "Flexible multi-node simulation of cellular mobile communications: the Vienna 5G
  System Level Simulator", EURASIP J. Wireless Commun. Netw. 2018:227, <https://doi.org/10.1186/s13638-018-1238-7>
- [V2] List of features, v1.4: <https://www.tuwien.at/etit/tc/wp-content/uploads/2023/11/listoffeatures-v1-4.pdf>
- [V3] Simulator page: <https://www.tuwien.at/etit/tc/vienna-simulators/vienna-5g-simulators/>
- [V4] Release 1.4 announcement: <https://vccsforum.nt.tuwien.ac.at/t/new-release-v1-4-vienna-5g-sl-simulator/297>
- [V5] Licence agreement: <https://www.tuwien.at/etit/tc/wp-content/uploads/2022/06/license-agreement-5g-sl.pdf>

**MATLAB 5G Toolbox**

- [W1] System-level simulation: <https://www.mathworks.com/help/5g/system-level-simulation.html>
- [W2] Overview of system-level simulation: <https://www.mathworks.com/help/5g/ug/overview-system-level-simulation-in-5g-network-analysis.html>
- [W3] `nrGNB`: <https://www.mathworks.com/help/5g/ref/nrgnb.html>
- [W4] `nrUE`: <https://www.mathworks.com/help/5g/ref/nrue.html>
- [W5] Composition of NR nodes: <https://www.mathworks.com/help/5g/ug/composition-of-nr-nodes.html>
- [W6] `addMobility`: <https://www.mathworks.com/help/5g/ref/nrue.addmobility.html>
- [W7] Simulate mobility of a UE node: <https://www.mathworks.com/help/5g/ug/simulate-ue-mobility-in-5g-network.html>
- [W8] NR NTN system performance with a transparent-payload LEO satellite:
  <https://www.mathworks.com/help/5g/ug/nr-ntn-system-performance-evaluation-with-transparent-payload-leo-satellite.html>
- [W9] NR cell performance with beam management:
  <https://www.mathworks.com/help/5g/ug/nr-cell-performance-evaluation-with-beam-management.html>
- [W10] Carrier aggregation in system-level simulation:
  <https://www.mathworks.com/help/5g/ug/carrier-aggregation-in-5g-system-level-simulation.html>
- [W11] Evaluate 3GPP indoor reference scenario: <https://www.mathworks.com/help/5g/ug/evaluate-3gpp-indoor-reference-scenario.html>
- [W12] Release 2026b announcement: <https://www.mathworks.com/company/newsroom/mathworks-introduces-release-2026b-of-matlab-and-simulink.html>
- [W13] R2026a product transition: <https://www.mathworks.com/products/new_products/r2026a-transition.html>
- [W14] Run 5G system-level simulations on AWS: <https://www.mathworks.com/help/5g/ug/run-5g-system-level-simulations-on-aws-cloud.html>

**OpenAirInterface**

- [O1] README: <https://github.com/OPENAIRINTERFACE/openairinterface5g/blob/develop/README.md>
- [O2] Feature set: <https://github.com/OPENAIRINTERFACE/openairinterface5g/blob/develop/doc/FEATURE_SET.md>
- [O3] Handover tutorial: <https://github.com/OPENAIRINTERFACE/openairinterface5g/blob/develop/doc/handover-tutorial.md>
- [O4] Changelog: <https://github.com/OPENAIRINTERFACE/openairinterface5g/blob/develop/CHANGELOG.md>
- [O5] NTN configuration: <https://github.com/OPENAIRINTERFACE/openairinterface5g/blob/develop/doc/ntn-configuration.md>
- [O6] MAC usage: <https://github.com/OPENAIRINTERFACE/openairinterface5g/blob/develop/doc/MAC/mac-usage.md>
- [O7] Analog beamforming: <https://github.com/OPENAIRINTERFACE/openairinterface5g/blob/develop/doc/analog_beamforming.md>
- [O8] RF simulator: <https://github.com/OPENAIRINTERFACE/openairinterface5g/blob/develop/radio/rfsimulator/README.md>
- [O9] Channel simulation: <https://github.com/OPENAIRINTERFACE/openairinterface5g/blob/develop/openair1/SIMULATION/TOOLS/DOC/channel_simulation.md>
- [O10] F. Kaltenberger et al., Computer Networks (2025) 111410, <https://doi.org/10.1016/j.comnet.2025.111410>

**NVIDIA Sionna**

- [N1] Repository and documentation: <https://github.com/NVlabs/sionna>, <https://nvlabs.github.io/sionna/>
- [N2] Releases (v2.0.0, v2.1.0, v2.2.0): <https://github.com/NVlabs/sionna/releases>
- [N3] Sionna SYS: <https://nvlabs.github.io/sionna/sys/index.html>
- [N4] `PHYAbstraction`: <https://nvlabs.github.io/sionna/sys/api/sionna.sys.PHYAbstraction.html>
- [N5] `PFSchedulerSUMIMO`: <https://nvlabs.github.io/sionna/sys/api/sionna.sys.PFSchedulerSUMIMO.html>
- [N6] SYS end-to-end tutorial: <https://nvlabs.github.io/sionna/sys/tutorials/notebooks/End-to-End_Example.html>
- [N7] 3GPP channel models: <https://nvlabs.github.io/sionna/phy/api/channel/wireless/3gpp.html>
