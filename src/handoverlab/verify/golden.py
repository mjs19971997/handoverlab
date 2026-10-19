# SPDX-License-Identifier: MIT
"""Golden event-log fingerprints of short reference runs.

``data/golden.json`` stores, for a few short runs per scenario and rule, the
fingerprint of the event log (see :mod:`handoverlab.eventlog`), the number of
events and some counts, together with the Python, NumPy and SciPy versions
and the platform that produced them.

On the same NumPy and SciPy build the fingerprints must be identical: any
change of a result shows up here.  A change that alters them on purpose
needs a new reference (``python -m handoverlab.verify.golden --write``) and
an entry in the changelog.  On another build or platform the random streams
and floating-point sums may differ in the last bits and move single events,
so there the check reports whether the fingerprints are identical and only
requires the counts to agree within a tolerance.
"""
from __future__ import annotations

import json
import os
import platform
import sys
from typing import Any, Dict, List

import numpy as np
import scipy

from ..scenarios import builtin_scenario
from ..simulate import simulate

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "golden.json")

RULES = [
    {"rule": "a3", "name": "A3", "off_db": 3.0, "ttt_s": 0.16},
    {"rule": "a3", "name": "A3-late", "off_db": 6.0, "ttt_s": 0.32},
    {"rule": "cho", "name": "CHO", "o_prep_db": -2.0, "o_exec_db": 3.0, "ttt_exec_s": 0.08, "n_max": 4},
]
COUNTS = ("n_attempts", "n_handovers", "n_unnecessary", "n_pingpong", "n_failures", "n_preparations")


def cases() -> Dict[str, Dict[str, Any]]:
    """name -> scenario, seed and rules of every golden run."""
    smoke = builtin_scenario("smoke")
    return {
        "smoke": dict(scenario=smoke, seed=1, rules=RULES),
        "smoke-stress": dict(scenario=smoke.with_overrides({"name": "smoke-stress", "radio.isolation": 1.0,
                                                            "mobility.profile": "veh30"}), seed=2, rules=RULES),
        "smoke-open": dict(scenario=smoke.with_overrides({"name": "smoke-open", "layout.kind": "open_area",
                                                          "radio.place_share": 0.5, "mobility.profile": "mix"}),
                           seed=3, rules=RULES[::2]),
        # the optional models of 1.1-1.4: FTP traffic, in-car loss, link monitoring with its own load,
        # execution that cannot fail and the restart of link monitoring on a new cell
        "smoke-ftp3": dict(scenario=smoke.with_overrides({
            "name": "smoke-ftp3", "traffic.model": "ftp3", "traffic.ftp_rate_hz": 0.5, "radio.penetration_db": 9.0,
            "radio.penetration_sd_db": 5.0, "protocol.lm_load": 0.05, "protocol.lm_load_per_ue": 0.02,
            "protocol.exec_can_fail": False, "protocol.rlm_holdoff_s": 0.2}), seed=4, rules=RULES[:2]),
        "smoke-cltm": dict(scenario=smoke.with_overrides({"name": "smoke-cltm", "radio.isolation": 1.0,
                                                          "mobility.profile": "veh30"}), seed=5,
                           rules=[{"rule": "ltm", "name": "LTM"}, {"rule": "cltm", "name": "CLTM"}]),
        # since 1.7.0: the indoor and rural scenarios (shortened) and mobility robustness optimisation
        "indoor": dict(scenario=builtin_scenario("indoor-office-4ghz").with_overrides({
            "name": "indoor", "run.duration_s": 40.0, "run.warmup_s": 5.0, "mobility.users": 12}),
            seed=6, rules=RULES[::2]),
        "rural": dict(scenario=builtin_scenario("rural-700mhz").with_overrides({
            "name": "rural", "run.duration_s": 40.0, "run.warmup_s": 5.0, "mobility.users": 8,
            "layout.area_m": [4000.0, 2000.0]}), seed=7, rules=RULES[::2]),
        "smoke-soft": dict(scenario=smoke.with_overrides({"name": "smoke-soft", "radio.soft_los": True}),
                           seed=9, rules=RULES[:1]),
        "rural-hard": dict(scenario=builtin_scenario("rural-700mhz").with_overrides({
            "name": "rural-hard", "run.duration_s": 40.0, "run.warmup_s": 5.0, "mobility.users": 8,
            "layout.area_m": [4000.0, 2000.0], "radio.soft_los": False}), seed=7, rules=RULES[::2]),
        # since 1.9.0: the 3GPP protocol profile (command received during T310, T304, restart of monitoring)
        "smoke-3gpp": dict(scenario=smoke.with_overrides({
            "name": "smoke-3gpp", "radio.isolation": 1.0, "mobility.profile": "veh30",
            "protocol.cmd_during_t310": "receive", "protocol.t304_s": 1.0, "protocol.rlm_holdoff_s": 0.2}),
            seed=10, rules=RULES + [{"rule": "ltm", "name": "LTM"}]),
        "smoke-mro": dict(scenario=smoke.with_overrides({"name": "smoke-mro", "radio.isolation": 1.0,
                                                         "mobility.profile": "veh30", "run.duration_s": 60.0}),
                          seed=8, rules=[RULES[0], {"rule": "a3_mro", "name": "A3-MRO", "window_s": 5.0,
                                                    "step_db": 1.0}]),
    }


def compute() -> Dict[str, Any]:
    out = {}
    for name, c in cases().items():
        res = simulate(c["scenario"], c["rules"], seeds=[c["seed"]])
        out[name] = [dict(rule=r.rule, fingerprint=r.fingerprint, n_events=r.n_events,
                          sinr_db=r.metrics["sinr_db"], **{k: r.metrics[k] for k in COUNTS}) for r in res]
    return out


def versions() -> Dict[str, str]:
    return dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__,
                system=platform.system(), machine=platform.machine())


def load() -> Dict[str, Any]:
    with open(PATH, encoding="utf-8") as f:
        return json.load(f)


def same_build(ref_versions: Dict[str, str]) -> bool:
    """True if NumPy, SciPy and the operating system match those of the reference."""
    v = versions()
    return all(v[k] == ref_versions.get(k) for k in ("numpy", "scipy", "system", "machine"))


def fingerprint_checks(rep) -> None:
    ref = load()
    rv = ref["versions"]
    same = same_build(rv)
    rep.section("fingerprints", "golden event-log fingerprints (reference: NumPy %s, SciPy %s, %s)"
                % (rv["numpy"], rv["scipy"], rv["system"]))
    if not same:
        rep.note("different NumPy / SciPy build or platform than the reference",
                 "fingerprints may differ; counts must agree within 10 %% or 3 events")
    got = compute()
    for name, runs in ref["cases"].items():
        for want, have in zip(runs, got[name]):
            label = "%s / %s" % (name, want["rule"])
            if have["fingerprint"] == want["fingerprint"]:
                rep.check(label + ": identical event log", True, "%s..., %d events" % (have["fingerprint"][:12],
                                                                                    have["n_events"]))
                continue
            if same:
                rep.check(label + ": identical event log", False, "got %s..., reference %s..."
                          % (have["fingerprint"][:12], want["fingerprint"][:12]))
                continue
            bad = [k for k in COUNTS + ("n_events",) if abs(have[k] - want[k]) > max(3, 0.10 * abs(want[k]))]
            rep.check(label + ": event log differs, counts agree", not bad,
                      "different: %s" % ", ".join("%s %d/%d" % (k, have[k], want[k]) for k in bad) if bad else
                      "%d / %d events" % (have["n_events"], want["n_events"]))


def write(path: str = PATH) -> None:
    doc = dict(note="Golden event-log fingerprints; regenerate with python -m handoverlab.verify.golden --write "
                    "and record the reason in CHANGELOG.md.",
               versions=versions(), cases=compute())
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1)
        f.write("\n")


def main(argv: List[str] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--write" in argv:
        write()
        print("wrote", PATH)
        return 0
    print(json.dumps(compute(), indent=1))
    return 0


if __name__ == "__main__":                                   # pragma: no cover
    sys.exit(main())
