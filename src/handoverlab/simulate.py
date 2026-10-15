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
from .engine.core import Engine
from .rules import Rule, make_rule
from .world import World, build_world

RuleSpec = Union[Dict[str, Any], Rule]


@dataclass
class RunResult:
    """Metrics of one rule on one seed."""
    seed: int
    rule: str
    family: str
    params: Dict[str, Any]
    metrics: Dict[str, float]
    events: Optional[List[dict]] = None
    timing: Dict[str, float] = field(default_factory=dict)

    def row(self) -> Dict[str, Any]:
        """Flat dictionary for a CSV row: seed, rule, parameters (prefixed ``param.``) and metrics."""
        r = {"seed": self.seed, "rule": self.rule, "family": self.family}
        r.update({"param." + k: v for k, v in self.params.items()})
        r.update(self.metrics)
        return r


def _instantiate(spec: RuleSpec) -> Rule:
    if isinstance(spec, Rule):
        return copy.deepcopy(spec)                  # each engine gets its own rule state
    return make_rule(spec)


def run_world(world: World, rules: Sequence[RuleSpec], log_events: bool = False,
              chunk_steps: int = 1000) -> List[RunResult]:
    """Run every rule of ``rules`` on ``world`` with identical radio samples."""
    t0 = time.perf_counter()
    objs = [_instantiate(s) for s in rules]
    engines = [Engine(world, r, log_events) for r in objs]
    t_radio = 0.0
    it = RadioSource(world, chunk_steps).chunks()
    while True:
        ta = time.perf_counter()
        ch = next(it, None)
        t_radio += time.perf_counter() - ta
        if ch is None:
            break
        for e in engines:
            e.advance(ch)
    out = []
    for r, e in zip(objs, engines):
        m = e.finish()
        out.append(RunResult(world.seed, r.name, r.family, r.params(), m, e.events,
                             dict(engine_s=e.wall, radio_s=t_radio, total_s=time.perf_counter() - t0)))
    return out


def simulate(scenario: Scenario, rules: Sequence[RuleSpec], seeds: Iterable[int] = (1,), log_events: bool = False,
             progress: Optional[Callable[[str], None]] = None) -> List[RunResult]:
    """Build one world per seed and run all ``rules`` on it.

    ``rules`` are rule objects or specifications such as
    ``{"rule": "a3", "off_db": 3.0, "ttt_s": 0.16}``.
    """
    results: List[RunResult] = []
    for seed in seeds:
        t0 = time.perf_counter()
        world = build_world(scenario, int(seed))
        t_world = time.perf_counter() - t0
        res = run_world(world, rules, log_events)
        for r in res:
            r.timing["world_s"] = t_world
        results.extend(res)
        if progress:
            progress("seed %d: %d rules in %.1f s" % (seed, len(res), time.perf_counter() - t0))
    return results


def run_experiment(exp: Experiment, log_events: bool = False,
                   progress: Optional[Callable[[str], None]] = None) -> List[RunResult]:
    """Run an :class:`~handoverlab.config.Experiment` (scenario, seeds and rules)."""
    return simulate(exp.scenario, exp.rules, exp.seeds, log_events, progress)
