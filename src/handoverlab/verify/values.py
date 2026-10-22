# SPDX-License-Identifier: MIT
"""Check group ``values`` (since 2.1.0): RRC parameter values of the built-in cards and rules against TS 38.331.

Every protocol value of every built-in scenario card and every default parameter of every registered rule is
checked against the value sets of TS 38.331 V18.11.0 (:mod:`handoverlab.standard`).  Deliberate exceptions are
listed in :data:`EXCEPTIONS` with their reason and reported as notes.
"""
from __future__ import annotations

from typing import Dict, Tuple

from .. import standard
from ..rules import available_rules
from ..scenarios import builtin_scenario, scenario_names

#: (card, key) -> reason of a value outside TS 38.331 that a card keeps on purpose
EXCEPTIONS: Dict[Tuple[str, str], str] = {
    ("ns3-urban-3.5ghz", "protocol.report_interval_s"):
        "replica of the ns-3 / 5G-LENA reference, whose UEs report every 200 ms",
}


def values_checks(rep) -> None:
    rep.section("values", "RRC parameter values of the built-in cards and rules against %s" % standard.SOURCE)
    for name in scenario_names():
        found = standard.check_scenario(builtin_scenario(name), name)
        kept = [f for f in found if (name, f.key) in EXCEPTIONS]
        bad = [f for f in found if (name, f.key) not in EXCEPTIONS]
        rep.check("card %s: protocol values" % name, not bad, "; ".join(str(f) for f in bad) or "all allowed")
        for f in kept:
            rep.note("card %s: %s = %r kept" % (name, f.key, f.value), EXCEPTIONS[(name, f.key)])
    for rule in available_rules():
        try:
            found = standard.check_rule({"rule": rule}, "rule " + rule)
        except ImportError as e:                        # optional dependency missing (dqn: PyTorch)
            rep.note("rule %s: defaults not checked" % rule, str(e))
            continue
        rep.check("rule %s: default parameters" % rule, not found, "; ".join(str(f) for f in found) or "all allowed")
