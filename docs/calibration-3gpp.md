# Radio calibration against 3GPP (TR 38.901 clause 7.8.1)

**Summary (1.8.0).** The radio model of HandoverLab -- path loss, LOS probability, shadowing and
building penetration loss of TR 38.901 -- passes the large-scale calibration that 3GPP defined for
TR 38.901. In the calibration drop of clause 7.8.1, the CDFs of the coupling loss and of the
geometry (wideband SINR, with and without noise) lie inside the range of the 21 companies that
reported their results to 3GPP in R1-165974, for UMa, UMi-Street Canyon and the indoor office at
6 GHz and 30 GHz: 325 of 342 compared percentiles (5 % to 95 % in steps of 5 %) are inside the
range, and none is more than about 1 dB from the industry mean. `handoverlab verify` repeats the
check (group `calibration`). With c = 3.0e8 m/s in the breakpoint distances (2.0.0) every number of this
page is unchanged.

**Version.** The drop uses the formulas of TR 38.901 V19.5.0 with one exception: the IRR-glass loss of the
high-loss O2I model. V19.5.0 Table 7.4.3-1 gives 25.4 + 0.11 f dB (note 2: updated in the Release 19 study
on 7-24 GHz); the calibration keeps the earlier 23 + 0.3 f dB of TR 38.901 V17.0.0, because the companies of
R1-165974 worked before that change (`IRR_GLASS_R1_165974` in `handoverlab.verify.calibration`; pass
`irr_glass=IRR_GLASS_V19` to `simulate_drops` for the V19.5.0 value). With the V19.5.0 value (30 000 users,
seed 1) the 6 GHz cases stay inside the company range, but at 30 GHz the coupling loss and the SINR of UMa
and UMi leave it (coupling loss: UMa 15 of 19 percentiles inside, largest distance from the mean 3.30 dB;
UMi 11 of 19, 3.25 dB): the higher glass loss at 30 GHz is a change of the model, not an error of the
reproduction.

![HandoverLab against the 21 companies of 3GPP R1-165974](images/calibration_38901.png)

## The reference

TR 38.901 clause 7.8.1 fixes the large-scale calibration (Table 7.8-1) and points to the 3GPP RAN1
contribution **R1-165974**, "E-mail discussion summary of the large scale calibration" (RAN1 #85,
Nanjing, May 2016; [3GPP server](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_85/Docs/R1-165974.zip)).
Its workbook holds the CDFs of 21 companies (Huawei, CATT, ITRI, LGE, InterDigital, CHTTL, Samsung,
Intel, Sharp, CATR, ZTE, Ericsson, NTT DOCOMO, Nokia, Qualcomm, Xinwei, CMCC, Lenovo, KDDI, ETRI,
NEC; 20 for the indoor office) at every percentile. `src/handoverlab/verify/data/r1_165974.csv`
keeps, per case, metric and percentile, the mean over the companies, the smallest and the largest
company value and the number of companies. The companies produced the results with TR 38.900 V14.0.0;
TR 38.901 still names R1-165974 as the calibration results of clause 7.8.1.

## The calibration drop

`handoverlab.verify.calibration` reproduces the drop of Table 7.8-1 with the propagation formulas
of the simulator (a test checks that they give exactly the values of `handoverlab.channel.pathloss`):

| Item | Setting | Source |
|---|---|---|
| Layout | UMa: 19 sites, ISD 500 m, BS 25 m; UMi: 19 sites, ISD 200 m, BS 10 m; geographical wrap-around | TR 38.901 Tables 7.2-1 and 7.8-1 |
| Indoor office | 12 ceiling sites, 20 m apart, in a 120 m x 50 m hall, BS 3 m, users 1 m | Table 7.2-2, Figure 7.2-1 |
| Sectors and antenna | 3 sectors per site (30, 150, 270 deg); element pattern of Table 7.3-1 (8 dBi); 10 vertical elements, d_V = lambda / 2, DFT tilt 102 deg (UMa, UMi), 110 deg (indoor) | Tables 7.3-1, 7.8-1; Eq. 7.3-1 |
| Users | uniform; UMa and UMi 80 % indoor at height 3 (n_fl - 1) + 1.5 m, n_fl ~ uniform(1, N_fl), N_fl ~ uniform(4, 8); minimum 2D distance 35 m (UMa), 10 m (UMi), applied to d2D-out | Table 7.2-1 ("Same as 3D-UMa in TR36.873"); the formula as in ITU-R M.2412-0 Table 5b (TR 36.873 itself is not in the local sources) |
| Path loss and LOS | Table 7.4.1-1 (UMa with the random effective environment height of note 1), Table 7.4.2-1 (UMa with C'(h_UT), indoor open office) | TR 38.901 |
| Shadowing | LOS / NLOS of Table 7.4.1-1; 7 dB for indoor users of UMa and UMi; independent between sites, shared by the sectors of a site | Tables 7.4.1-1 and 7.5-6 |
| O2I loss | 50 % low loss, 50 % high loss; d2D-in = min of two uniform(0, 25 m); IRR glass 23 + 0.3 f dB (see Version above) | clause 7.4.3.1, Tables 7.4.3-1 (V17.0.0 value), 7.4.3-2 |
| Link budget | 49 dBm (UMa), 44 dBm (UMi) at 6 GHz with 20 MHz; 35 dBm at 30 GHz with 100 MHz; 24 dBm indoor; UT noise figure 9 dB; isotropic UT | Table 7.8-1 |
| Association | sector with the highest received power (handover margin 0 dB), no fast fading | Table 7.8-1 |

## Results

30 000 users per case, seed 1 (`handoverlab verify --full`):

| Case | Metric | Median: HandoverLab / 3GPP mean [dB] | Percentiles 5-95 % inside the company range | Largest distance from the mean [dB] |
|---|---|---|---|---|
| UMa-6 GHz | coupling loss | 119.6 / 120.3 | 19 / 19 | 0.76 |
| UMa-6 GHz | SINR | 5.6 / 5.8 | 19 / 19 | 0.39 |
| UMa-6 GHz | SIR | 8.0 / 8.5 | 16 / 19 | 0.79 |
| UMa-30 GHz | coupling loss | 139.2 / 140.1 | 19 / 19 | 1.02 |
| UMa-30 GHz | SINR | -19.2 / -19.8 | 19 / 19 | 0.73 |
| UMa-30 GHz | SIR | 7.8 / 8.6 | 10 / 19 | 0.80 |
| UMi-6 GHz | coupling loss | 111.5 / 112.2 | 19 / 19 | 0.90 |
| UMi-6 GHz | SINR | 5.3 / 5.5 | 19 / 19 | 0.61 |
| UMi-6 GHz | SIR | 6.8 / 7.3 | 19 / 19 | 0.76 |
| UMi-30 GHz | coupling loss | 131.7 / 132.4 | 19 / 19 | 0.83 |
| UMi-30 GHz | SINR | -11.8 / -12.2 | 19 / 19 | 0.53 |
| UMi-30 GHz | SIR | 6.9 / 7.5 | 14 / 19 | 0.77 |
| Indoor-6 GHz | coupling loss | 59.4 / 59.3 | 19 / 19 | 0.20 |
| Indoor-6 GHz | SINR | 3.0 / 3.0 | 19 / 19 | 0.16 |
| Indoor-6 GHz | SIR | 3.0 / 3.0 | 19 / 19 | 0.16 |
| Indoor-30 GHz | coupling loss | 73.3 / 73.3 | 19 / 19 | 0.20 |
| Indoor-30 GHz | SINR | 3.0 / 3.1 | 19 / 19 | 0.13 |
| Indoor-30 GHz | SIR | 3.0 / 3.1 | 19 / 19 | 0.13 |

The 17 percentiles outside the range are all SIR values of UMa and UMi in the lower half of the
distribution, at most 0.12 dB below the smallest company value: the SIR of HandoverLab is about
0.5 dB below the industry mean there, which is on the conservative side. `handoverlab verify`
passes a case when every percentile lies inside the company range widened by 0.5 dB.

## 7 GHz: Table 7.8-1A against R1-2506406 (since 2.4.0)

**Summary.** TR 38.901 V19.5.0 adds Table 7.8-1A to clause 7.8.1: UMa, UMi-Street Canyon and suburban macro
(SMa, ISD 1299 m and 1732 m) at 7 GHz, plus UMa and UMi at 6 GHz again "with updated channel modeling". The
companies reported their CDFs in the 3GPP contribution **R1-2506406** (RAN1 #122, Bengaluru, August 2025,
InterDigital and ZTE, "Calibration Results for 7 - 24 GHz SI";
[3GPP server](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_122/Docs/R1-2506406.zip); large-scale workbook
`Calibration_LS_v35`, based on TR 38.901 V19.0.0). The criteria were fixed before the first run: every
percentile 5-95 % inside the company range widened by 0.5 dB (C1, the rule of the cases above), and the
largest distance from the company mean at most 1.5 dB per case (C2). Result, 30 000 users per case, seed 1:
**C1 passes for all 18 case-metric pairs of the six cases (342 of 342 percentiles strictly inside the range;
228 of 228 for the four 7 GHz cases); C2 fails for all six cases (largest distance 1.65-2.88 dB; 1.69-2.43 dB
for the four 7 GHz cases, 1.65 and 2.88 dB for the two 6 GHz reruns).** `handoverlab verify` runs C1 as checks and C2 as notes in the
group `calibration`.

**The reference.** `src/handoverlab/verify/data/r1_2506406.csv` keeps, in the format of `r1_165974.csv`, the
mean, the smallest and the largest company value and the number of companies per case, metric and percentile;
the mean equals the workbook's own mean column. Companies with complete columns: 16 (coupling loss) / 15
(SINR, SIR) at 6 GHz; 17 / 16 for UMa and UMi at 7 GHz (Huawei, InterDigital, Samsung, ZTE, CATT, Lenovo,
Apple, Nokia, Ericsson, OPPO, MediaTek, Intel, Sharp, Spreadtrum, LGE, ETRI, Xiaomi; Spreadtrum gave the
coupling loss only); 17 / 16 for SMa 1299 m (with vivo, without ETRI); 13 / 12 for SMa 1732 m.

**The drop.** UMa and UMi as above (Table 7.8-1), with the IRR-glass loss of V19.5.0 (25.4 + 0.11 f dB) because
the companies worked with Release 19; at 7 GHz 49 dBm (UMa) and 44 dBm (UMi) with 20 MHz, the 6 GHz values of
Table 7.8-1, which Table 7.8-1A leaves unchanged for these two scenarios. SMa:

| Item | Setting | Source |
|---|---|---|
| Layout | 19 sites, 3 sectors, ISD 1299 m or 1732 m, BS 35 m, geographical wrap-around, minimum 2D distance 35 m (to d2D-out) | Tables 7.2-5, 7.8-1A |
| Antenna | element of Table 7.3-1 and 10 vertical elements (one port) without electrical tilt, the panel tilted mechanically to 95 deg (ISD 1299 m) or 92 deg (ISD 1732 m): the angles are taken into the antenna's local coordinates with Eqs. 7.1-7 and 7.1-8 | Tables 7.3-1, 7.8-1A; clause 7.1.3 |
| Users | 20 % outdoors (in cars, 1.5 m) with the car penetration loss N(9 dB, 5 dB) of non-metallic windows; 80 % indoors, 90 % of them in residential buildings (1.5 or 4.5 m), 10 % in commercial buildings (1.5 ... 13.5 m), uniform over the floors | Tables 7.2-5, 7.8-1A; clause 7.4.3.2 |
| O2I loss | low-loss A model (30 % glass, 70 % plywood, sigma_P 4.4 dB); d2D-in = minimum of two uniform variables up to 10 m (residential) or 25 m (commercial) | clause 7.4.3.1, Tables 7.4.3-1, 7.4.3-2 |
| Path loss, LOS, shadowing | the SMa models of `handoverlab.channel.pathloss` (Table 7.4.1-1; LOS probability of Table 7.4.2-1 without vegetation); shadowing 4 dB (LOS below d_BP), 6 dB (LOS beyond), 8 dB (NLOS), 8 dB for indoor users | Tables 7.4.1-1, 7.4.2-1, 7.5-6 Part-4 |
| Link budget | 49 dBm, 20 MHz, UT noise figure 9 dB, isotropic UT, attachment to the highest coupling gain | Tables 7.8-1, 7.8-1A |

Results (median HandoverLab / company mean; percentiles 5-95 % strictly inside the range; largest distance
from the mean):

| Case | Coupling loss [dB] | SINR [dB] | SIR [dB] | C1 | C2 (largest distance) |
|---|---|---|---|---|---|
| UMa-6 GHz | 119.9 / 121.0; 19/19; 1.65 | 5.5 / 5.6; 19/19; 1.34 | 8.0 / 8.0; 19/19; 0.17 | pass | fail (1.65) |
| UMi-6 GHz | 111.9 / 112.1; 19/19; 2.88 | 5.1 / 5.2; 19/19; 1.35 | 6.8 / 6.6; 19/19; 0.53 | pass | fail (2.88) |
| UMa-7 GHz | 121.7 / 122.4; 19/19; 1.78 | 5.0 / 5.0; 19/19; 0.90 | 7.9 / 7.9; 19/19; 0.29 | pass | fail (1.78) |
| UMi-7 GHz | 113.8 / 113.3; 19/19; 2.43 | 4.7 / 4.8; 19/19; 1.63 | 6.7 / 6.6; 19/19; 0.30 | pass | fail (2.43) |
| SMa-7 GHz, ISD 1299 m | 103.5 / 104.3; 19/19; 1.31 | 5.9 / 5.7; 19/19; 1.69 | 5.9 / 5.9; 19/19; 1.57 | pass | fail (1.69) |
| SMa-7 GHz, ISD 1732 m | 109.2 / 111.3; 19/19; 2.24 | 6.3 / 5.9; 19/19; 1.07 | 6.4 / 6.6; 19/19; 0.32 | pass | fail (2.24) |

Where the distance comes from: for UMa and UMi the coupling loss of the best users (75-95 %, close to a site)
is 1.6-2.9 dB lower than the company mean, and at UMi 7 GHz also at 5-10 %; the medians are within 1.1 dB.
For SMa 1732 m the coupling loss is about 2.1 dB lower than the mean over most of the distribution. The
company spread is large here (at the median, from 106.5 dB to 129.4 dB for SMa 1732 m), so the mean is a soft
target, but C2 was fixed before the run and is reported as it came. No parameter was changed after the run.

## What this calibration covers, and what it does not

- It covers the **radio model**: the path-loss formulas, the LOS probabilities, the shadowing, the
  O2I loss and the frequency dependence, with the deployment and antenna that 3GPP fixed for
  calibration. These are the same formulas the handover engine uses.
- The **handover engine** uses its own antenna abstraction (one beam gain, `radio.bs_gain_db`, and
  an isolation factor for interfering beams) instead of the sectorised array of Table 7.8-1, and a
  spatially consistent, moving radio map instead of independent drops. Received powers in a
  handover scenario therefore differ from the calibration drop by the antenna model, not by the
  propagation model.
- The **failure model** (link monitoring, T310, the outcome of a handover) is not part of any 3GPP
  calibration; its comparison with ns-3 is on the page [failure-model calibration](calibration.md).
  Read failure rates relative to each other.

## Repeat it

```bash
handoverlab verify --only calibration          # 10 000 users per case, under a minute
handoverlab verify --only calibration --full   # 30 000 users per case, the tables above
python tools/make_calibration_figure.py        # docs/images/calibration_38901.png
```

```python
from handoverlab.verify import calibration as cal

case = cal.CalScenario("UMa", 6.0)
res = cal.simulate_drops(case, n_users=30000, seed=1)
for c in cal.compare(case, res):
    print(c.metric, c.inside.sum(), "of", len(c.percentiles), "inside, largest distance", c.max_dev_db)

case = cal.CalScenario("SMa", 7.0, isd_m=1299.0, reference="R1-2506406")   # compared with R1-2506406
```
