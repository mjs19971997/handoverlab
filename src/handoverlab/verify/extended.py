# SPDX-License-Identifier: MIT
"""Checks of the optional models of 1.10.0 (``handoverlab verify``, group ``extended``).

* Antenna and beams: element pattern of TR 38.901 Table 7.3-1, array factor and the gain of a
  steered SSB beam against hand values.
* Cell quality from beams (TS 38.331 clause 5.5.3.3) on hand-made beam values.
* TS 38.133 formulas (evaluation periods, measurement periods, gap patterns, L_max and N_RLM,
  frequency ranges) against values worked out by hand from the tables.
* The engine of the optional models without any option = the engine of 1.x (identical event logs);
  rule ``a3a5`` on one carrier = ``a3``.
* DAPS and LTM against TS 38.133 (clauses 6.1.3 and 6.3.1) and against published 3GPP evaluations
  (the plan and the sources are in ``docs/standard-compliance.md``): the requirement values, the
  interruption the engine actually applies, and the bands fixed before the comparison.
"""
from __future__ import annotations

import math
import sys

import numpy as np

from .. import requirements as req
from ..channel.antenna import beam_gain_db, element_gain_db, ula_gain
from ..scenarios import builtin_scenario
from ..world import build_world


def _close(a, b, tol=1e-6):
    return abs(float(a) - float(b)) <= tol


def antenna_checks(rep) -> None:
    rep.check("element gain on boresight = G_E,max = 8 dBi (TR 38.901 Table 7.3-1)",
              _close(element_gain_db(90.0, 0.0), 8.0))
    rep.check("element gain 65 deg off boresight in azimuth = 8 - 12 = -4 dBi (A_H = -12 dB)",
              _close(element_gain_db(90.0, 65.0), -4.0))
    rep.check("element gain behind the panel = 8 - 30 = -22 dBi (A_m = 30 dB)",
              _close(element_gain_db(90.0, 180.0), -22.0))
    rep.check("array factor of 8 elements: 8 in the steered direction, 0 at the first null (psi = 2 pi / 8)",
              _close(ula_gain(0.0, 8), 8.0) and float(ula_gain(2 * math.pi / 8, 8)) < 1e-20)
    g = float(beam_gain_db(100.0, 20.0, np.array([20.0]), 100.0, 4, 8)[0])
    hand = 8.0 - 12.0 * (10.0 / 65.0) ** 2 - 12.0 * (20.0 / 65.0) ** 2 + 10.0 * math.log10(32.0)
    rep.check("SSB beam of a 4 x 8 panel towards its own steering direction (100 deg, 20 deg): element gain "
              "+ 10 log10(32) = %.3f dBi" % hand, _close(g, hand, 1e-6), "%.4f dBi" % g)


def cell_quality_checks(rep) -> None:
    from types import SimpleNamespace

    from ..channel.extended import cell_quality
    from ..config import BeamConfig
    beams = np.array([[[-80.0, -83.0, -90.0, -100.0]]])            # (1, C=1, B=4)
    layer = SimpleNamespace(n_cells=1)
    ext = SimpleNamespace(layers=[layer])
    hand = 10.0 * math.log10((10 ** -8.0 + 10 ** -8.3) / 2.0)
    q = cell_quality(beams, ext, [BeamConfig(ssb_avg=3, ssb_thresh_dbm=-85.0)])[0, 0]
    rep.check("TS 38.331 5.5.3.3: linear average of the beams above absThreshSS-BlocksConsolidation "
              "(-80, -83 dBm above -85 dBm) = %.3f dBm" % hand, _close(q, hand, 1e-9), "%.4f dBm" % q)
    q = cell_quality(beams, ext, [BeamConfig(ssb_avg=None, ssb_thresh_dbm=-85.0)])[0, 0]
    rep.check("TS 38.331 5.5.3.3: nrofSS-BlocksToAverage not configured -> highest beam (-80 dBm)", _close(q, -80.0))
    q = cell_quality(beams, ext, [BeamConfig(ssb_avg=3, ssb_thresh_dbm=-79.0)])[0, 0]
    rep.check("TS 38.331 5.5.3.3: highest beam below the threshold -> highest beam (-80 dBm)", _close(q, -80.0))


def requirement_checks(rep) -> None:
    hand = [
        ("frequency ranges (TS 38.104 Table 5.1-1): 3.5 GHz FR1, 15 GHz FR3, 28 GHz FR2-1, 60 GHz FR2-2",
         [req.freq_range(f) for f in (3.5, 15.0, 28.0, 60.0)] == ["FR1", "FR3", "FR2-1", "FR2-2"]),
        ("L_max 4 / 8 / 64 and N_RLM 2 / 4 / 8 at 2, 3.5 and 28 GHz (TS 38.133 Table 8.1.1-2)",
         [req.ssb_max(f) for f in (2.0, 3.5, 28.0)] == [4, 8, 64]
         and [req.n_rlm(f) for f in (2.0, 3.5, 28.0)] == [2, 4, 8]),
        ("RLM T_SSB 20 ms: FR1 out/in = max(200, 10 x 20) / max(100, 5 x 20) = 200 / 100 ms; "
         "FR2-1 (N = 8) = 80 x 20 / 40 x 20 = 1600 / 800 ms (Tables 8.1.2.2-1/-2)",
         req.rlm_evaluation_periods(0.02) == (0.2, 0.1) and
         np.allclose(req.rlm_evaluation_periods(0.02, 8), (1.6, 0.8))),
        ("BFD T_SSB 20 ms: FR1 max(50, 5 x 20) = 100 ms; FR2-1 max(50, 40 x 20) = 800 ms (Tables 8.5.2.2-1/-2); "
         "indication interval max(2 ms, 20 ms) = 20 ms (8.5.4)",
         _close(req.bfd_evaluation_period(0.02), 0.1) and _close(req.bfd_evaluation_period(0.02, 8), 0.8)
         and _close(req.bfd_indication_interval(0.02), 0.02)),
        ("CBD T_SSB 20 ms: FR1 max(25, 3 x 20) = 60 ms; FR2-1 max(25, 24 x 20) = 480 ms (Tables 8.5.5.2-1/-2)",
         _close(req.cbd_evaluation_period(0.02), 0.06) and _close(req.cbd_evaluation_period(0.02, 8), 0.48)),
        ("L1-RSRP T_SSB 20 ms, M = 3: FR1 60 ms, FR2-1 480 ms (Tables 9.5.4.1-1/-2)",
         _close(req.l1_rsrp_period(0.02), 0.06) and _close(req.l1_rsrp_period(0.02, 8), 0.48)),
        ("intra-frequency, SMTC 20 ms: FR1 max(200, 5 x 20) = 200 ms; FR2-1 power class 3 max(400, 24 x 20) = "
         "480 ms (Tables 9.2.5.2-1/-2)",
         _close(req.intra_meas_period(3.5, 0.02), 0.2) and _close(req.intra_meas_period(28.0, 0.02), 0.48)),
        ("inter-frequency with gap pattern 0 (MGL 6 ms, MGRP 40 ms; Table 9.1.2-1), SMTC 20 ms: FR1 max(200, 8 x 40) "
         "= 320 ms; FR2-1 power class 3 max(400, 40 x 40) = 1600 ms (Tables 9.3.5-1/-2)",
         req.GAP_PATTERNS[0] == (0.006, 0.040) and _close(req.inter_meas_period(3.5, 0.04, 0.02), 0.32)
         and _close(req.inter_meas_period(28.0, 0.04, 0.02), 1.6)),
    ]
    for name, ok in hand:
        rep.check(name, bool(ok))


def engine_equivalence_checks(rep, duration_s: float = 20.0) -> None:
    from ..simulate import run_world
    sim = sys.modules["handoverlab.simulate"]
    sc = builtin_scenario("smoke").with_overrides({"name": "smoke-ext", "radio.isolation": 1.0,
                                                   "mobility.profile": "veh30", "run.duration_s": duration_s,
                                                   "run.warmup_s": 0.0})
    world = build_world(sc, 12)
    rules = [{"rule": "a3"}, {"rule": "cho"}, {"rule": "daps"}, {"rule": "ltm"}]
    ref = run_world(world, rules)
    orig = sim.uses_extended
    try:
        sim.uses_extended = lambda w: True
        ext = run_world(world, rules)
    finally:
        sim.uses_extended = orig
    rep.check("engine of the 1.10.0 options without any option = engine of 1.x (A3, CHO, DAPS, LTM: identical "
              "event logs)", all(a.fingerprint == b.fingerprint for a, b in zip(ref, ext)),
              "%d events" % sum(r.n_events for r in ref))
    a, b = run_world(world, [{"rule": "a3", "off_db": 3.0, "ttt_s": 0.16},
                             {"rule": "a3a5", "off_db": 3.0, "ttt_s": 0.16}])
    rep.check("rule a3a5 on one carrier = a3 (identical event logs)", a.fingerprint == b.fingerprint)


def daps_ltm_checks(rep, duration_s: float = 30.0) -> None:
    from ..rules import DAPS, LTM
    from ..simulate import simulate
    ltm, daps = LTM(), DAPS()
    exec_l3 = builtin_scenario("smoke").protocol.exec_s
    r = req.ltm_delay(t_harq=0.0)
    rep.check("V1a TS 38.133 6.3.1.3: LTM FR1-FR1, known cell and TCI, fast RRC, RACH-less, T_LTM-IU = 0 -> "
              "T_LTM-interrupt = 20 ms = LTM exec_s of HandoverLab (%.0f ms)" % (ltm.exec_s * 1e3),
              _close(r["interrupt"], 0.020) and _close(ltm.exec_s, r["interrupt"]))
    rb = req.ltm_delay(t_harq=0.0, rach_based=True, t_assoc=0.010)
    rep.note("V1b TS 38.133 6.3.1.3: RACH-based, SSB-to-PRACH association period 10 ms -> T_LTM-interrupt up to "
             "%.0f ms (report only)" % (rb["interrupt"] * 1e3))
    rep.check("V1c TS 38.133 6.3.1.2: T_cmd = T_HARQ + 3 ms; LTM cmd_delay_s (%.0f ms) in [3, 10] ms"
              % (ltm.cmd_delay_s * 1e3), 0.003 <= ltm.cmd_delay_s <= 0.010 + 1e-12)
    d = req.daps_interruption(30.0, True)
    da = req.daps_interruption(30.0, False)
    rep.check("V1d TS 38.133 6.1.3.2.2: DAPS FR1 intra-frequency at 30 kHz allows T_interrupt1 + T_interrupt2 = "
              "%.1f ms (sync) / %.1f ms (async); DAPS interruption_s of HandoverLab (%.1f ms) is within"
              % (d["total"] * 1e3, da["total"] * 1e3, daps.interruption_s * 1e3),
              0.0 <= daps.interruption_s <= da["total"] + 1e-12)
    sc = builtin_scenario("smoke").with_overrides({"run.duration_s": duration_s, "run.warmup_s": 0.0,
                                                   "mobility.profile": "veh30"})
    res = simulate(sc, [{"rule": "ltm", "exec_s": 0.020}, {"rule": "daps", "interruption_s": 0.002}], seeds=[1])
    for x, want in zip(res, (0.020, 0.002)):
        m = x.metrics
        per = m["interruption_exec_s_pm"] * m["ue_minutes"] / max(m["n_executions"], 1)
        rep.check("V1e the engine applies the configured interruption per execution (%s: %.1f ms)"
                  % (x.rule, want * 1e3), abs(per - want) <= 1e-9 * max(1, m["n_executions"]),
                  "%.6f ms over %d executions" % (per * 1e3, m["n_executions"]))
    # published evaluations: bands fixed before the comparison (std3gpp/EVAL_LTM_DAPS.md, measval/DAPS_LTM_PLAN.md)
    rep.check("V2a L3 handover interruption: protocol.exec_s = %.0f ms in [22.75, 240] ms (references 45.5-120 ms: "
              "TR 36.881, R1-2007151 80 ms, R2-2206982, R2-2208200)" % (exec_l3 * 1e3), 0.02275 <= exec_l3 <= 0.240)
    rep.check("V2b LTM interruption: exec_s = %.0f ms in [10, 140] ms (references 20-70 ms: R2-2207806 [44, 70] ms, "
              "R2-2209256 about 66 ms, Ericsson 20-30 ms)" % (ltm.exec_s * 1e3), 0.010 <= ltm.exec_s <= 0.140)
    ratio = ltm.exec_s / exec_l3
    rep.check("V2c ratio LTM / L3 interruption = %.2f in [0.11, 1.0] (Ericsson 20-30 ms vs 50-90 ms: 0.22-0.60)"
              % ratio, 0.11 <= ratio <= 1.0)
    rep.check("V2d DAPS interruption %.0f ms in [0, 4] ms (references about 0 ms: R2-1907308, R2-1901361, "
              "R2-2206982; 2 ms: TS 38.133 as cited by Nokia)" % (daps.interruption_s * 1e3),
              0.0 <= daps.interruption_s <= 0.004)


def extended_checks(rep, duration_s: float = 30.0) -> None:
    rep.section("extended", "beams, several carriers, TS 38.133 periods, DAPS and LTM against 3GPP (since 1.10.0)")
    antenna_checks(rep)
    cell_quality_checks(rep)
    requirement_checks(rep)
    engine_equivalence_checks(rep, duration_s=min(duration_s, 20.0))
    daps_ltm_checks(rep, duration_s=duration_s)
