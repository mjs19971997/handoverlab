# SPDX-License-Identifier: MIT
"""Running handover rules on simulated worlds.

:func:`run_world` runs any number of rules on one world and on the same radio
samples (common random numbers): each radio chunk goes to the engines of all
rules before the next chunk is made.  :func:`simulate` does this for a list
of seeds.
"""
from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Union

from .channel.source import RadioSource
from .config import Experiment, Scenario
from .engine.batch import EngineBatch
from .engine.core import Engine
from .rules import Rule, make_rule, rule_key
from .world import World, build_world

RuleSpec = Union[Dict[str, Any], Rule]


@dataclass
class RunResult:
    """Metrics of one rule on one seed.

    ``fingerprint`` is the SHA-256 of the canonical event log (see
    :mod:`handoverlab.eventlog`) and is always set; ``events`` holds the log
    itself only if it was requested.  ``key`` is the registry key of the rule
    (``"a3"``, ``"cho"``, ...), so that the run can be repeated.
    """
    seed: int
    rule: str
    family: str
    params: Dict[str, Any]
    metrics: Dict[str, float]
    events: Optional[List[dict]] = None
    timing: Dict[str, float] = field(default_factory=dict)
    fingerprint: str = ""
    n_events: int = 0
    key: Optional[str] = None

    def spec(self) -> Dict[str, Any]:
        """Rule specification that recreates this rule (``{"rule": key, "name": ..., **params}``)."""
        if self.key is None:
            raise ValueError("rule %r is not registered; it cannot be recreated from its name" % self.rule)
        return dict(rule=self.key, name=self.rule, **self.params)

    def row(self) -> Dict[str, Any]:
        """Flat dictionary for a CSV row: seed, rule, parameters (prefixed ``param.``) and metrics."""
        r = {"seed": self.seed, "rule": self.rule, "family": self.family, "fingerprint": self.fingerprint,
             "n_events": self.n_events}
        r.update({"param." + k: v for k, v in self.params.items()})
        r.update(self.metrics)
        return r


def _instantiate(spec: RuleSpec) -> Rule:
    if isinstance(spec, Rule):
        return copy.deepcopy(spec)                  # each engine gets its own rule state
    return make_rule(spec)


def _key(spec: RuleSpec, obj: Rule) -> Optional[str]:
    return spec.get("rule") if isinstance(spec, dict) else rule_key(obj)


def run_world(world: World, rules: Sequence[RuleSpec], log_events: bool = False,
              chunk_steps: int = 1000, debug: Optional[bool] = None, batch: bool = True) -> List[RunResult]:
    """Run every rule of ``rules`` on ``world`` with identical radio samples.

    ``debug`` turns on the invariant checks of the engine (see
    :mod:`handoverlab.engine.invariants`); results are the same either way.
    With ``batch`` (the default) the engines of all rules share one step loop
    (:class:`~handoverlab.engine.batch.EngineBatch`); results are
    bit-identical to running them one by one (``batch=False``), only faster.
    Engines in debug mode always run one by one.
    """
    t0 = time.perf_counter()
    objs = [_instantiate(s) for s in rules]
    engines = [Engine(world, r, log_events, debug) for r in objs]
    runners = [EngineBatch(engines)] if batch and EngineBatch.supported(engines) else engines
    t_radio = 0.0
    it = RadioSource(world, chunk_steps).chunks()
    while True:
        ta = time.perf_counter()
        ch = next(it, None)
        t_radio += time.perf_counter() - ta
        if ch is None:
            break
        for e in runners:
            e.advance(ch)
    out = []
    for spec, r, e in zip(rules, objs, engines):
        m = e.finish()
        out.append(RunResult(world.seed, r.name, r.family, r.params(), m, e.events,
                             dict(engine_s=e.wall, radio_s=t_radio, total_s=time.perf_counter() - t0),
                             e.fingerprint, e.n_events, _key(spec, r)))
    return out


def simulate(scenario: Scenario, rules: Sequence[RuleSpec], seeds: Iterable[int] = (1,), log_events: bool = False,
             progress: Optional[Callable[[str], None]] = None, debug: Optional[bool] = None) -> List[RunResult]:
    """Build one world per seed and run all ``rules`` on it.

    ``rules`` are rule objects or specifications such as
    ``{"rule": "a3", "off_db": 3.0, "ttt_s": 0.16}``.
    """
    results: List[RunResult] = []
    for seed in seeds:
        t0 = time.perf_counter()
        world = build_world(scenario, int(seed))
        t_world = time.perf_counter() - t0
        res = run_world(world, rules, log_events, debug=debug)
        for r in res:
            r.timing["world_s"] = t_world
        results.extend(res)
        if progress:
            progress("seed %d: %d rules in %.1f s" % (seed, len(res), time.perf_counter() - t0))
    return results


def run_experiment(exp: Experiment, log_events: bool = False,
                   progress: Optional[Callable[[str], None]] = None, debug: Optional[bool] = None) -> List[RunResult]:
    """Run an :class:`~handoverlab.config.Experiment` (scenario, seeds and rules)."""
    return simulate(exp.scenario, exp.rules, exp.seeds, log_events, progress, debug)
