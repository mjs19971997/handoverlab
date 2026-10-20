# SPDX-License-Identifier: MIT
"""3GPP requirement formulas used by the optional models of 1.10.0, and by ``handoverlab verify``.

Every function quotes the table it implements.  Times are in seconds.  Only
the no-DRX rows are implemented (HandoverLab models no DRX).

* frequency ranges: TS 38.104 Table 5.1-1 (FR1 410-7125 MHz, FR2-1
  24250-52600 MHz, FR2-2 52600-71000 MHz).  Carriers between FR1 and FR2
  ("FR3", 7.125-24.25 GHz, studied for 6G) have no RRM requirements yet;
  HandoverLab then applies the FR1 formulas without receive-beam sweeping
  (N = 1) and the FR2 limit of 64 SSB beams -- an assumption, stated in
  ``docs/standard-compliance.md``;
* L_max and N_RLM: TS 38.133 Table 8.1.1-2;
* RLM evaluation periods: TS 38.133 Tables 8.1.2.2-1 (FR1) and 8.1.2.2-2 (FR2);
* beam failure detection: TS 38.133 Tables 8.5.2.2-1/-2 (evaluation period)
  and clause 8.5.4 (indication interval); candidate beam detection:
  Tables 8.5.5.2-1/-2;
* SSB-based L1-RSRP for reporting: TS 38.133 Tables 9.5.4.1-1/-2;
* intra-frequency measurement period without gaps: TS 38.133 Tables
  9.2.5.2-1/-2; inter-frequency measurement period with gaps: Tables
  9.3.5-1/-2; gap patterns: Table 9.1.2-1;
* LTM cell switch delay and interruption: TS 38.133 clause 6.3.1 (Rel-18);
* DAPS handover interruption: TS 38.133 Tables 6.1.3.2.2-1 and -5 (FR1, intra-frequency).

The scaling factors P (measurement gaps overlapping the reference signal),
Kp, Kgap, K_layer1 and CSSF are 1 unless given: HandoverLab assumes that the
gaps do not overlap the serving SSBs and that only the configured layers are
measured (see ``docs/standard-compliance.md``).
"""
from __future__ import annotations

import math
from typing import Dict, Tuple

#: TS 38.133 Table 9.1.2-1: gap pattern id -> (MGL, MGRP) [s]
GAP_PATTERNS: Dict[int, Tuple[float, float]] = {
    0: (0.006, 0.040), 1: (0.006, 0.080), 2: (0.003, 0.040), 3: (0.003, 0.080), 4: (0.006, 0.020),
    5: (0.006, 0.160), 6: (0.004, 0.020), 7: (0.004, 0.040), 8: (0.004, 0.080), 9: (0.004, 0.160),
    10: (0.003, 0.020), 11: (0.003, 0.160), 12: (0.0055, 0.020), 13: (0.0055, 0.040), 14: (0.0055, 0.080),
    15: (0.0055, 0.160), 16: (0.0035, 0.020), 17: (0.0035, 0.040), 18: (0.0035, 0.080), 19: (0.0035, 0.160),
    20: (0.0015, 0.020), 21: (0.0015, 0.040), 22: (0.0015, 0.080), 23: (0.0015, 0.160), 24: (0.010, 0.080),
    25: (0.020, 0.160)}


def _ceil(x: float) -> int:
    return int(math.ceil(x - 1e-9))


def freq_range(carrier_ghz: float) -> str:
    """"FR1", "FR2-1" or "FR2-2" (TS 38.104 Table 5.1-1), "FR3" between FR1 and FR2, "other" outside."""
    f = carrier_ghz * 1000.0
    if 410.0 <= f <= 7125.0:
        return "FR1"
    if 7125.0 < f < 24250.0:
        return "FR3"
    if 24250.0 <= f <= 52600.0:
        return "FR2-1"
    if 52600.0 < f <= 71000.0:
        return "FR2-2"
    return "other"


def is_fr2(carrier_ghz: float) -> bool:
    return freq_range(carrier_ghz).startswith("FR2")


def ssb_max(carrier_ghz: float) -> int:
    """L_max, the most SSBs per half frame (TS 38.133 Table 8.1.1-2): 4 up to 3 GHz, 8 in FR1 above, 64 in FR2.

    Above FR1 outside FR2 (FR3) the FR2 value is assumed.
    """
    if carrier_ghz <= 3.0:
        return 4
    if freq_range(carrier_ghz) == "FR1":
        return 8
    return 64


def n_rlm(carrier_ghz: float) -> int:
    """N_RLM, the most RLM-RS resources (TS 38.133 Table 8.1.1-2): 2, 4 or 8 for L_max 4, 8 or 64."""
    return {4: 2, 8: 4, 64: 8}[ssb_max(carrier_ghz)]


def rx_sweep_factor(carrier_ghz: float) -> int:
    """Scaling factor N of TS 38.133 clauses 8.1 and 8.5: 8 in FR2-1, 12 in FR2-2, otherwise 1."""
    fr = freq_range(carrier_ghz)
    return 8 if fr == "FR2-1" else 12 if fr == "FR2-2" else 1


def rlm_evaluation_periods(t_ssb: float, n: int = 1, p: float = 1.0) -> Tuple[float, float]:
    """(T_Evaluate_out_SSB, T_Evaluate_in_SSB), no DRX: TS 38.133 Tables 8.1.2.2-1 (N = 1) and 8.1.2.2-2.

    out = Max(200 ms, Ceil(10 P N) T_SSB); in = Max(100 ms, Ceil(5 P N) T_SSB).
    """
    return max(0.2, _ceil(10 * p * n) * t_ssb), max(0.1, _ceil(5 * p * n) * t_ssb)


def bfd_evaluation_period(t_ssb: float, n: int = 1, p: float = 1.0) -> float:
    """T_Evaluate_BFD_SSB, no DRX: Max(50 ms, Ceil(5 P N) T_SSB) (TS 38.133 Tables 8.5.2.2-1, 8.5.2.2-2)."""
    return max(0.05, _ceil(5 * p * n) * t_ssb)


def bfd_indication_interval(t_rs: float) -> float:
    """T_Indication_interval_BFD, no DRX: max(2 ms, T_SSB-RS,M) (TS 38.133 clause 8.5.4)."""
    return max(0.002, t_rs)


def cbd_evaluation_period(t_ssb: float, n: int = 1, p: float = 1.0, p_cbd: int = 1) -> float:
    """T_Evaluate_CBD_SSB, no DRX: Max(25 ms, Ceil(3 P N P_CBD) T_SSB) (TS 38.133 Tables 8.5.5.2-1, 8.5.5.2-2)."""
    return max(0.025, _ceil(3 * p * n * p_cbd) * t_ssb)


def l1_rsrp_period(t_ssb: float, n: int = 1, m: int = 3, p: float = 1.0, t_report: float = 0.0) -> float:
    """T_L1-RSRP_Measurement_Period_SSB, no DRX: max(T_Report, ceil(M P N) T_SSB) (TS 38.133 Tables 9.5.4.1-1/-2).

    FR1 is the case N = 1; M = 3 unless timeRestrictionForChannelMeasurement is configured (M = 1).
    """
    return max(t_report, _ceil(m * p * n) * t_ssb)


def meas_m_intra(carrier_ghz: float, power_class: int = 3) -> int:
    """M_meas_period_w/o_gaps of TS 38.133 clause 9.2.5.2 (FR2): 24 or 40 in FR2-1, 36 or 60 in FR2-2."""
    if freq_range(carrier_ghz) == "FR2-2":
        return 60 if power_class == 1 else 36
    return 40 if power_class in (1, 5) else 24


def meas_m_inter(carrier_ghz: float, power_class: int = 3) -> int:
    """M_meas_period_inter of TS 38.133 clause 9.3.4 (FR2): 40 or 64 in FR2-1, 60 or 96 in FR2-2."""
    if freq_range(carrier_ghz) == "FR2-2":
        return 96 if power_class == 1 else 60
    return 64 if power_class in (1, 5) else 40


def intra_meas_period(carrier_ghz: float, t_smtc: float, power_class: int = 3, kp: float = 1.0,
                      cssf: float = 1.0, k_layer1: float = 1.0) -> float:
    """T_SSB_measurement_period_intra without gaps, no DRX (TS 38.133 Tables 9.2.5.2-1 and 9.2.5.2-2).

    FR1 (and FR3): max(200 ms, ceil(5 Kp) T_SMTC) CSSF; FR2: max(400 ms, ceil(M_meas Kp K_layer1) T_SMTC) CSSF.
    """
    if is_fr2(carrier_ghz):
        return max(0.4, _ceil(meas_m_intra(carrier_ghz, power_class) * kp * k_layer1) * t_smtc) * cssf
    return max(0.2, _ceil(5 * kp) * t_smtc) * cssf


def inter_meas_period(carrier_ghz: float, mgrp: float, t_smtc: float, power_class: int = 3,
                      kgap: float = 1.0, cssf: float = 1.0) -> float:
    """T_SSB_measurement_period_inter with gaps, no DRX (TS 38.133 Tables 9.3.5-1 and 9.3.5-2).

    FR1 target (and FR3): Max(200 ms, Ceil(8 Kgap) Max(MGRP, T_SMTC)) CSSF_inter;
    FR2 target: Max(400 ms, Ceil(Kgap M_meas_period_inter) Max(MGRP, T_SMTC)) CSSF_inter.
    """
    if is_fr2(carrier_ghz):
        return max(0.4, _ceil(kgap * meas_m_inter(carrier_ghz, power_class)) * max(mgrp, t_smtc)) * cssf
    return max(0.2, _ceil(8 * kgap) * max(mgrp, t_smtc)) * cssf


def l3_reference_period(carrier_ghz: float, t_smtc: float, power_class: int = 3) -> float:
    """X of TS 38.331 clause 5.5.3.2: one intra-frequency L1 measurement period without DRX, for the FR."""
    return intra_meas_period(carrier_ghz, t_smtc, power_class)


def ltm_delay(t_harq: float, fr_change: bool = False, fast_rrc: bool = True, tci_known: bool = True,
              t_first_ssb: float = 0.0, rach_based: bool = False, t_assoc: float = 0.0,
              t_iu_rach_less: float = 0.0) -> Dict[str, float]:
    """LTM PCell cell switch delay D_LTM = T_cmd + T_LTM-interrupt (TS 38.133 clauses 6.3.1.2 and 6.3.1.3).

    T_cmd = T_HARQ + 3 ms; T_LTM-interrupt = T_LTM-RRC-processing (0 with fast processing, else 10 ms)
    + T_LTM-processing (20 ms FR1-FR1 / FR2-FR2, 40 ms between FR1 and FR2, UE without the fast-processing
    capability) + T_first-RS + T_RS-proc (0 and 0 with a known, active target TCI state; else the time to
    the first SSB and 2 ms) + T_LTM-IU (RACH-based: up to the SSB-to-PRACH association period + 10 ms;
    RACH-less: the uncertainty of the first UL transmission, ``t_iu_rach_less``, not specified).
    Returns the parts and the totals (upper values where the clause gives a bound).
    """
    t_cmd = t_harq + 0.003
    rrc = 0.0 if fast_rrc else 0.010
    proc = 0.040 if fr_change else 0.020
    first, rs = (0.0, 0.0) if tci_known else (t_first_ssb, 0.002)
    iu = (t_assoc + 0.010) if rach_based else t_iu_rach_less
    inter = rrc + proc + first + rs + iu
    return dict(t_cmd=t_cmd, rrc=rrc, processing=proc, first_rs=first, rs_proc=rs, iu=iu, interrupt=inter,
                delay=t_cmd + inter)


#: TS 38.133 Table 6.1.3.2.2-1 (T_interrupt1) and Table 6.1.3.2.2-5 (T_interrupt2, same BWP), FR1-to-FR1
#: intra-frequency DAPS handover: mu -> (sync, async) in slots
DAPS_INTERRUPT1_SLOTS = {0: (1, 2), 1: (2, 3), 2: (4, 5)}
DAPS_INTERRUPT2_SLOTS = {0: (1, 2), 1: (2, 3), 2: (4, 5)}


def daps_interruption(scs_khz: float, synchronous: bool = True) -> Dict[str, float]:
    """Allowed interruptions of an FR1 intra-frequency DAPS handover [s] (TS 38.133 clause 6.1.3.2.2).

    T_interrupt1 on the source cell during D_handover1 (Table 6.1.3.2.2-1) and T_interrupt2 at the release
    of the source when the target uses the same BWP (Table 6.1.3.2.2-5); slot length 1 ms / 2^mu.
    """
    mu = {15.0: 0, 30.0: 1, 60.0: 2}[float(scs_khz)]
    slot = 0.001 / 2 ** mu
    k = 0 if synchronous else 1
    t1 = DAPS_INTERRUPT1_SLOTS[mu][k] * slot
    t2 = DAPS_INTERRUPT2_SLOTS[mu][k] * slot
    return dict(slot=slot, interrupt1=t1, interrupt2=t2, total=t1 + t2)
