# SPDX-License-Identifier: MIT
"""Checks of the protocol engine: invariants, determinism and equivalences.

All runs use a stressed version of the ``smoke`` scenario (no beam
isolation, 30 m/s users, no warm-up) so that every failure cause and every
outcome occurs.
"""
from __future__ import annotations

import numpy as np

from ..scenarios import builtin_scenario
from ..simulate import run_world
from ..world import build_world

BUILTIN_RULES = [
    {"rule": "a3", "name": "A3", "off_db": 3.0, "ttt_s": 0.16},
    {"rule": "a3", "name": "A3-late", "off_db": 6.0, "ttt_s": 0.32},
    {"rule": "cho", "name": "CHO", "o_prep_db": -2.0, "o_exec_db": 3.0, "ttt_exec_s": 0.08, "n_max": 4},
    {"rule": "cho", "name": "CHO-late", "o_prep_db": 0.0, "o_exec_db": 8.0, "ttt_exec_s": 0.32, "n_max": 2},
]


def stress_scenario(duration_s: float = 30.0):
    """``smoke`` without beam isolation, with 30 m/s users and no warm-up."""
    return builtin_scenario("smoke").with_overrides({
        "name": "smoke-stress", "radio.isolation": 1.0, "mobility.profile": "veh30",
        "run.duration_s": duration_s, "run.warmup_s": 0.0})


def _rows(res):
    """Event rows for comparing a baseline and a conditional rule.

    Kind and offsets differ by definition, and so does an attempt still in
    preparation when the run ends (a report starts a baseline attempt, an
    execution a conditional one); such censored rows are left out.
    """
    return [(e["t_exec"], e["t_end"], e["ue"], e["src"], e["tgt"], e["outcome"]) for e in res.events
            if not (e["outcome"] == "censored" and e["t_exec"] == -1.0)]


def invariant_checks(rep, seed: int = 11, duration_s: float = 30.0) -> None:
    rep.section("invariants", "invariants in debug mode and conservation of counts (stressed smoke scenario)")
    sc = stress_scenario(duration_s)
    world = build_world(sc, seed)
    res = run_world(world, BUILTIN_RULES, debug=True)
    rep.check("all built-in rules run in debug mode without an invariant violation", True,
              "%d rules, %d events" % (len(res), sum(r.n_events for r in res)))
    causes = {}
    for r in res:
        m = r.metrics
        outs = [m["n_" + o] for o in ("useful", "unnecessary", "too_early", "wrong_cell", "too_late", "censored")]
        ok = m["n_attempts"] == sum(outs)
        txt = ("attempts %d = useful %d + unnecessary %d + too early %d + wrong cell %d + too late %d + censored %d;"
               " failures %d" % ((m["n_attempts"],) + tuple(outs) + (m["n_failures"],)))
        if r.family == "conditional":
            parts = (m["n_lost_configurations"], m["n_cancelled_preparations"], m["n_used_preparations"],
                     m["n_unused_preparations"], m["open_preparations"])
            ok &= m["n_preparations"] == sum(parts)
            txt += "; preparations %d = lost %d + cancelled %d + used %d + unused %d + open %d" % (
                (m["n_preparations"],) + parts)
        ok &= m["n_failures"] == sum(v for k, v in m.items() if k.startswith("n_fail_"))
        rep.check("%-8s counts add up" % r.rule, ok, txt)
        for k, v in m.items():
            if k.startswith("n_fail_"):
                causes[k[7:]] = causes.get(k[7:], 0) + v
    rep.note("failure causes seen (all rules)", ", ".join("%s %d" % kv for kv in causes.items()))
    # determinism
    again = run_world(world, BUILTIN_RULES)
    rep.check("same world twice: identical event logs and metrics (debug mode on and off)",
              all(a.fingerprint == b.fingerprint and a.metrics == b.metrics for a, b in zip(res, again)))
    rev = run_world(world, list(reversed(BUILTIN_RULES)))
    rep.check("rules are independent: the order of the rules in a run changes nothing",
              all(a.fingerprint == b.fingerprint for a, b in zip(res, reversed(rev))))
    other = run_world(build_world(sc, seed + 1), BUILTIN_RULES[:1])
    rep.check("another seed gives another event log", other[0].fingerprint != res[0].fingerprint)
    state = np.random.get_state()[1].copy()
    run_world(world, BUILTIN_RULES[:1])
    rep.check("the global NumPy random state is untouched", np.array_equal(state, np.random.get_state()[1]))


def equivalence_checks(rep, seed: int = 11, duration_s: float = 30.0) -> None:
    rep.section("equivalences", "equivalences between rules")
    sc = stress_scenario(duration_s).with_overrides({"protocol.report_interval_s": 0.04,
                                                     "protocol.cfg_loss_as_failure": True})
    world = build_world(sc, seed)
    keys = ("n_handovers", "n_failures", "n_useful", "n_unnecessary", "n_too_early", "n_wrong_cell", "n_too_late",
            "n_fail_command_lost", "n_fail_execution_failure")
    for off, ttt in ((3.0, 0.16), (1.0, 0.04), (6.0, 0.32)):
        a, b = run_world(world, [
            {"rule": "a3", "name": "A3", "off_db": off, "ttt_s": ttt},
            {"rule": "cho", "name": "CHO-imm", "o_prep_db": off, "ttt_prep_s": ttt, "immediate": True, "n_max": 1,
             "rel_hys_db": 1e9}], log_events=True)
        same = _rows(a) == _rows(b) and all(a.metrics[k] == b.metrics[k] for k in keys)
        rep.check("CHO with immediate execution = A3 (%g dB, %g ms; lost configuration = lost command)"
                  % (off, ttt * 1000), same, "%d / %d events, failures %d / %d"
                  % (a.n_events, b.n_events, a.metrics["n_failures"], b.metrics["n_failures"]))
    from ..testing import ScaledA3
    a, b = run_world(world, [{"rule": "a3", "off_db": 3.0, "ttt_s": 0.16},
                             ScaledA3(off_db=3.0, ttt_s=0.16, v_ref=1e9)], log_events=True)
    rep.check("speed-scaled A3 with an infinite reference speed = A3 (plug-in interface)",
              a.fingerprint == b.fingerprint, "%d events" % a.n_events)
