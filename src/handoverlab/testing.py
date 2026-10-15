# SPDX-License-Identifier: MIT
"""Contract test kit for handover-rule plug-ins.

:func:`check_rule` runs a rule on the ``smoke`` scenario and checks that it
keeps the contract of the rule interface:

``construct``    the rule can be built from the given parameters; ``params()`` is a dictionary that can be
                 written to JSON and reports the given values; the family is ``baseline`` or ``conditional``
``recreate``     a rule built from ``params()`` reports the same parameters (stored results can be repeated)
``debug run``    a run in debug mode raises nothing: every hook returns a number or an array of the right shape
                 without NaN, the rule does not write into the observation, all engine invariants hold
``deterministic`` two runs give identical event-log fingerprints and metrics, with and without debug mode
``global random state`` the run leaves NumPy's and Python's global random state untouched (use ``ctx.rng``)
``independent``  next to another rule on the same world the rule gives the same event log as alone
``reduces_to``   (optional) with given parameters the rule gives the same event log as a built-in rule

Use it in the tests of a plug-in package::

    from handoverlab.testing import check_rule
    from my_rules import SpeedScaledA3

    def test_contract():
        check_rule(SpeedScaledA3, params={"off_db": 3.0, "ttt_s": 0.32, "v_ref": 8.0},
                   reduces_to=("a3", {"off_db": 3.0, "ttt_s": 0.32}, {"v_ref": 1e9}))

``reduces_to`` is ``(key, built-in parameters, own parameter changes)``: the
rule with ``params`` updated by the changes must reproduce the built-in rule
``key``.  :func:`check_rule` raises ``AssertionError`` naming every failed
check, or returns a :class:`ContractReport` with ``raise_on_failure=False``.
"""
from __future__ import annotations

import inspect
import json
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from .config import Scenario
from .rules import BaselineRule, ConditionalRule, get_rule_class
from .simulate import run_world
from .world import build_world


@dataclass
class ContractReport:
    rule: str
    results: List[Tuple[str, bool, str]] = field(default_factory=list)

    def add(self, name: str, ok: bool, detail: str = "") -> bool:
        self.results.append((name, bool(ok), detail))
        return bool(ok)

    @property
    def ok(self) -> bool:
        return all(ok for _, ok, _ in self.results)

    def __str__(self) -> str:
        lines = ["contract of rule %s:" % self.rule]
        lines += ["  %s  %s%s" % ("PASS" if ok else "FAIL", n, ("  [%s]" % d) if d else "") for n, ok, d in self.results]
        return "\n".join(lines)


def _rows(res, reduced):
    if not reduced:
        return res.fingerprint
    return [(e["t_exec"], e["t_end"], e["ue"], e["src"], e["tgt"], e["outcome"], e["cause"]) for e in res.events
            if not (e["outcome"] == "censored" and e["t_exec"] == -1.0)]   # in preparation at the end


def check_rule(rule: Union[type, str], params: Optional[Dict[str, Any]] = None,
               reduces_to: Optional[Tuple[str, Dict[str, Any], Dict[str, Any]]] = None,
               scenario: Union[str, Scenario] = "smoke", seed: int = 1,
               raise_on_failure: bool = True) -> ContractReport:
    """Check the rule class ``rule`` (or registry key) with constructor arguments ``params``."""
    cls = get_rule_class(rule) if isinstance(rule, str) else rule
    params = dict(params or {})
    rep = ContractReport(getattr(cls, "__name__", str(rule)))
    # --- construction
    try:
        obj = cls(**params)
    except Exception as e:                                   # noqa: BLE001 - reported, not hidden
        rep.add("construct", False, "%s: %s" % (type(e).__name__, e))
        return _finish(rep, raise_on_failure)
    ok = inspect.isclass(cls) and issubclass(cls, (BaselineRule, ConditionalRule))
    ok &= obj.family in ("baseline", "conditional")
    detail = ""
    try:
        p = obj.params()
        json.dumps(p)
        missing = [k for k, v in params.items() if k != "name" and (k not in p or p[k] != v)]
        if missing:
            ok, detail = False, "params() does not report %s" % ", ".join(missing)
    except Exception as e:                                   # noqa: BLE001
        ok, detail = False, "params(): %s: %s" % (type(e).__name__, e)
    if not rep.add("construct", ok, detail or "family %s" % obj.family):
        return _finish(rep, raise_on_failure)
    try:
        again = cls(**obj.params())
        rep.add("recreate", again.params() == obj.params())
    except Exception as e:                                   # noqa: BLE001
        rep.add("recreate", False, "cls(**params()) failed: %s: %s" % (type(e).__name__, e))
    # --- runs
    sc = Scenario.from_dict(scenario) if isinstance(scenario, str) else scenario
    world = build_world(sc, seed)
    np_state = np.random.get_state()
    py_state = random.getstate()
    try:
        a = run_world(world, [cls(**params)], log_events=True, debug=True)[0]
    except Exception as e:                                   # noqa: BLE001
        rep.add("debug run", False, "%s: %s" % (type(e).__name__, e))
        return _finish(rep, raise_on_failure)
    rep.add("debug run", True, "%d events, %d handovers, %d failures"
            % (a.n_events, a.metrics["n_handovers"], a.metrics["n_failures"]))
    b = run_world(world, [cls(**params)])[0]
    rep.add("deterministic", a.fingerprint == b.fingerprint and a.metrics == b.metrics)
    same_np = np.array_equal(np_state[1], np.random.get_state()[1]) and np_state[2] == np.random.get_state()[2]
    rep.add("global random state", same_np and py_state == random.getstate(),
            "" if same_np else "NumPy's global random state changed; draw from ctx.rng instead")
    other = {"rule": "cho"} if obj.family == "baseline" else {"rule": "a3"}
    c = run_world(world, [other, cls(**params)])[1]
    rep.add("independent", c.fingerprint == a.fingerprint)
    # --- equivalence with a built-in rule
    if reduces_to is not None:
        key, bparams, changes = reduces_to
        mine = dict(params)
        mine.update(changes or {})
        x, y = run_world(world, [cls(**mine), dict(bparams, rule=key)], log_events=True)
        reduced = x.family != y.family
        rep.add("reduces_to %s" % key, _rows(x, reduced) == _rows(y, reduced),
                "%d / %d events%s" % (x.n_events, y.n_events,
                                       " (compared without kind, offsets and attempts open at the end)"
                                       if reduced else ""))
    return _finish(rep, raise_on_failure)


def _finish(rep: ContractReport, raise_on_failure: bool) -> ContractReport:
    if raise_on_failure and not rep.ok:
        raise AssertionError(str(rep))
    return rep


class ScaledA3(BaselineRule):
    """Example plug-in: Event A3 whose time-to-trigger shrinks with the reported speed.

    ttt = ttt_s * min(1, v_ref / speed).  With an infinite ``v_ref`` it is A3.
    """

    def __init__(self, off_db: float = 3.0, ttt_s: float = 0.32, v_ref: float = 8.0, name: str = "A3-speed"):
        super().__init__(name)
        self.off_db, self.ttt_s, self.v_ref = float(off_db), float(ttt_s), float(v_ref)

    def params(self):
        return dict(off_db=self.off_db, ttt_s=self.ttt_s, v_ref=self.v_ref)

    def a3_offsets(self, obs):
        return self.off_db

    def time_to_trigger(self, obs):
        return self.ttt_s * np.minimum(1.0, self.v_ref / np.maximum(obs.speed, 1e-6))


__all__ = ["check_rule", "ContractReport", "ScaledA3"]
