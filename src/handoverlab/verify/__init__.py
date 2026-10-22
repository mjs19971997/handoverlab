# SPDX-License-Identifier: MIT
"""Verification of the simulator: ``handoverlab verify``.

Check groups (all run by default, in this order):

``pathloss``      TR 38.901 path loss, breakpoint and LOS probability against hand values
``radio``         statistics of the radio model against its parameters (shadowing, LOS share, time variation,
                  L1 error, L3 filter)
``calibration``   large-scale calibration of TR 38.901 clause 7.8.1 against the 21 companies of 3GPP
                  R1-165974 (coupling loss, SINR and SIR CDFs of UMa, UMi and the indoor office at 6 and 30 GHz)
``invariants``    built-in rules in debug mode, conservation of counts, determinism, independence of rules
``equivalences``  CHO with immediate execution = A3; a plug-in rule that reduces to A3 = A3
``fingerprints``  golden event-log fingerprints of short reference runs
``extended``      beams, several carriers, TS 38.133 periods, DAPS and LTM against TS 38.133 and published
                  3GPP evaluations (since 1.10.0)
``highway``       the TR 37.885 highway cards: geometry, wrap-around, coupling gain against an independent
                  computation, LOS-only links (since 1.11.0)

Optional:

``values``        RRC parameter values of the built-in cards and rules against TS 38.331 V18.11.0 (since 2.1.0)
``learning``      the learning rule a3_bandit against an exhaustive search over its arms (``--only learning``;
                  about 20 minutes; since 1.11.0)
``ntn``           NTN link budget, antenna and orbit against TR 38.821 / TR 38.811 (``--only ntn``; since 2.0.0)
``ns3``           reference comparison with stored ns-3 / 5G-LENA results (``--ns3``; minutes)
``stored``        recompute (a sample of) a stored result file and compare fingerprints (``--results FILE``)

:func:`run_verify` returns a :class:`~handoverlab.verify.report.Report`;
``report.ok`` is True if no check failed.
"""
from __future__ import annotations

from typing import Callable, Optional, Sequence

from .report import FAIL, NOTE, PASS, Check, Report, header

GROUPS = ("pathloss", "radio", "calibration", "invariants", "equivalences", "fingerprints", "extended", "highway",
          "values")
OPTIONAL_GROUPS = ("learning", "ntn")


def run_verify(groups: Optional[Sequence[str]] = None, full: bool = False, ns3: bool = False,
               ns3_seeds: int = 1, results: Optional[str] = None, sample: Optional[int] = None,
               printer: Optional[Callable[[str], None]] = print, ns3_reference: Optional[str] = None) -> Report:
    """Run the check groups ``groups`` (default: all of :data:`GROUPS`) and return the report.

    ``full`` uses three seeds for the radio statistics and 60 s runs for the
    engine checks instead of one seed and 30 s.
    """
    groups = list(GROUPS if groups is None else groups)
    unknown = [g for g in groups if g not in GROUPS + OPTIONAL_GROUPS]
    if unknown:
        raise ValueError("unknown check group %r; known: %s" % (unknown[0], ", ".join(GROUPS + OPTIONAL_GROUPS)))
    rep = Report(printer=printer)
    if printer:
        printer(header())
    dur = 60.0 if full else 30.0
    if "pathloss" in groups:
        from .radio import pathloss_checks
        pathloss_checks(rep)
    if "radio" in groups:
        from .radio import radio_statistics
        radio_statistics(rep, seeds=(3, 4, 5) if full else (3,))
    if "calibration" in groups:
        from .calibration import calibration_checks
        calibration_checks(rep, n_users=30000 if full else 10000)
    if "invariants" in groups:
        from .engine_checks import invariant_checks
        invariant_checks(rep, duration_s=dur)
    if "equivalences" in groups:
        from .engine_checks import equivalence_checks
        equivalence_checks(rep, duration_s=dur)
    if "fingerprints" in groups:
        from .golden import fingerprint_checks
        fingerprint_checks(rep)
    if "extended" in groups:
        from .extended import extended_checks
        extended_checks(rep, duration_s=dur)
    if "highway" in groups:
        from .highway import highway_checks
        highway_checks(rep)
    if "values" in groups:
        from .values import values_checks
        values_checks(rep)
    if "ntn" in groups:
        from .ntn import ntn_checks
        ntn_checks(rep)
    if "learning" in groups:
        from .learning import learning_checks
        learning_checks(rep)
    if ns3:
        from .ns3 import ns3_checks
        ns3_checks(rep, seeds=tuple(500 + i for i in range(ns3_seeds)), progress=printer, reference=ns3_reference)
    if results:
        from .stored import stored_checks
        stored_checks(rep, results, sample)
    if printer:
        printer("\n== summary ==\n%s: %s" % ("OK" if rep.ok else "FAILED", rep.summary()))
        for c in rep.failed:
            printer("  failed: [%s] %s" % (c.group, c.name))
    return rep


__all__ = ["GROUPS", "OPTIONAL_GROUPS", "run_verify", "Report", "Check", "PASS", "FAIL", "NOTE"]
