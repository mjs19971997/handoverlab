# SPDX-License-Identifier: MIT
"""Running handover rules on simulated worlds.

:func:`run_world` runs any number of rules on one world and on the same radio
samples (common random numbers): each radio chunk goes to the engines of all
rules before the next chunk is made.  :func:`simulate` does this for a list
of seeds.

Shared radio samples (since 2.11.0)
    Scenario variants that differ only in settings that the protocol engine
    alone reads (:func:`radio_key`) have the same world arrays and the same
    radio samples on a seed.  :func:`run_shared` runs them on one radio
    stream, and :func:`simulate_variants` groups a list of variants that way:
    every engine gives the result of its own separate run, bit for bit; only
    the radio samples are computed once instead of once per variant.
"""
from __future__ import annotations

import copy
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Union

from .channel.extended import ExtendedSource
from .channel.source import RadioSource
from .config import Experiment, Scenario
from .engine.batch import EngineBatch
from .engine.core import Engine
from .engine.dual import DcEngine
from .engine.extended import ExtEngine, uses_extended
from .rules import Rule, make_rule, rule_key
from .world import World, build_world

RuleSpec = Union[Dict[str, Any], Rule]


@dataclass
class RunResult:
    """Metrics of one rule on one seed.

    ``fingerprint`` is the SHA-256 of the canonical event log (see
    :mod:`handoverlab.eventlog`) and is always set; ``events`` holds the log
    itself only if it was requested.  ``key`` is the registry key of the rule
    (``"a3"``, ``"cho"``, ...), so that the run can be repeated.  ``trace``
    holds the procedure trace at event-log level ``"full"`` (see
    :mod:`handoverlab.eventlog`).
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
    trace: Optional[List[dict]] = None

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


def run_world(world: World, rules: Sequence[RuleSpec], log_events: Union[bool, str] = False,
              chunk_steps: int = 1000, debug: Optional[bool] = None, batch: bool = True,
              progress: Optional[Callable[[float], None]] = None) -> List[RunResult]:
    """Run every rule of ``rules`` on ``world`` with identical radio samples.

    ``log_events`` is the event-log level: ``"off"`` (or False), ``"summary"``
    (or True: :attr:`RunResult.events`) or ``"full"`` (also
    :attr:`RunResult.trace`).  ``progress`` is called after every radio chunk
    with the share of the run simulated so far (0 to 1).

    ``debug`` turns on the invariant checks of the engine (see
    :mod:`handoverlab.engine.invariants`); results are the same either way.
    With ``batch`` (the default) the engines of all rules share one step loop
    (:class:`~handoverlab.engine.batch.EngineBatch`); results are
    bit-identical to running them one by one (``batch=False``), only faster.
    Engines in debug mode always run one by one.
    """
    return run_shared([world], [rules], log_events, chunk_steps, debug, batch, progress)[0]


#: Keys of ``radio.beams`` (and of the ``beams`` of every ``radio.layers``
#: entry) that only the protocol engine reads: beam reports and switching,
#: beam failure detection and recovery, the RLM reference signals and the
#: SS-SINR definition.  The other beam keys shape the radio samples.
ENGINE_BEAM_KEYS = ("report_s", "switch_db", "tci_delay_s", "rx_sweep_n", "bfd", "bfi_max", "bfd_timer",
                    "bfr_timer_s", "rsrp_thresh_ssb_dbm", "ra_attempt_s", "preamble_max", "rlm_rs", "ssb_sinr",
                    "ssb_overlap", "bfd_filter")
#: Keys of ``protocol`` that the world and the radio samples depend on; every
#: other ``protocol`` key is read by the protocol engine alone.
RADIO_PROTOCOL_KEYS = ("step_s", "l1_period_s")


def radio_key(scenario: Scenario) -> str:
    """Content hash of everything that fixes the world and the radio samples of ``scenario`` (since 2.11.0).

    It is the SHA-256 of the full scenario without its name, without the
    ``protocol`` keys other than :data:`RADIO_PROTOCOL_KEYS` and without the
    beam keys of :data:`ENGINE_BEAM_KEYS`.  Two scenarios with the same radio
    key give the same world arrays and the same radio samples on every seed,
    so :func:`run_shared` may run them on one radio stream.  The rule is
    strict: any other difference, even one that would not change the radio
    samples (``run.backend``, ``traffic``, the duration), gives another key.
    """
    d = scenario.to_dict(full=True)
    d.pop("name", None)
    d["protocol"] = {k: d["protocol"][k] for k in RADIO_PROTOCOL_KEYS}
    R = d["radio"]
    for b in [R.get("beams")] + [ly.get("beams") for ly in R.get("layers") or ()]:
        if b:
            for k in ENGINE_BEAM_KEYS:
                b.pop(k, None)
    return hashlib.sha256(json.dumps(d, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def run_shared(worlds: Sequence[World], rules: Sequence[Sequence[RuleSpec]], log_events: Union[bool, str] = False,
               chunk_steps: int = 1000, debug: Optional[bool] = None, batch: bool = True,
               progress: Optional[Callable[[float], None]] = None) -> List[List[RunResult]]:
    """Run ``rules[i]`` on ``worlds[i]`` for every i, all on one radio stream (since 2.11.0).

    The worlds must have the same seed and scenarios with the same
    :func:`radio_key` (variants that differ only in engine settings), each
    built by :func:`~handoverlab.world.build_world` as for a separate run.
    The radio samples are made once, from the first world, and every chunk
    goes to the engines of all worlds before the next chunk is made.  Returns
    one list of results per world, each equal (fingerprint, metrics, event
    log) to ``run_world(worlds[i], rules[i], ...)``; ``timing["radio_s"]`` is
    the time of the shared samples and ``timing["radio_shared"]`` the number
    of worlds that used them.  The other arguments are those of
    :func:`run_world`.
    """
    if len(worlds) != len(rules):
        raise ValueError("run_shared: %d worlds but %d rule lists" % (len(worlds), len(rules)))
    if not worlds:
        return []
    w0 = worlds[0]
    if len(worlds) > 1:
        key = radio_key(w0.scenario)
        for w in worlds[1:]:
            if w.seed != w0.seed:
                raise ValueError("run_shared: the worlds have different seeds (%d, %d)" % (w0.seed, w.seed))
            if radio_key(w.scenario) != key:
                raise ValueError("run_shared: scenarios %r and %r differ in more than engine settings; they "
                                 "cannot share radio samples" % (w0.scenario.name, w.scenario.name))
            if w.x.shape != w0.x.shape or w.n_cells != w0.n_cells:
                raise ValueError("run_shared: the worlds differ in size")
    t0 = time.perf_counter()
    groups = []                                               # per world: (rule objects, engines, runners)
    for world, specs in zip(worlds, rules):
        objs = [_instantiate(s) for s in specs]
        ext = uses_extended(world)
        cls = DcEngine if world.scenario.protocol.dc is not None else ExtEngine if ext else Engine
        engines = [cls(world, r, log_events, debug) for r in objs]
        runners = [EngineBatch(engines)] if batch and EngineBatch.supported(engines) else engines
        groups.append((objs, engines, runners))
    t_radio = 0.0
    if w0.ntn is not None:                                    # one satellite with moving beams (since 2.0.0)
        from .channel.ntn import NtnSource
        src = NtnSource(w0, chunk_steps)
    else:
        src = ExtendedSource(w0, chunk_steps) if w0.ext is not None else RadioSource(w0, chunk_steps)
    it = src.chunks()
    while True:
        ta = time.perf_counter()
        ch = next(it, None)
        t_radio += time.perf_counter() - ta
        if ch is None:
            break
        for _, _, runners in groups:
            for e in runners:
                e.advance(ch)
        if progress:
            progress(min(1.0, (ch.k0 + ch.n) / float(w0.n_steps)))
    out = []
    for world, specs, (objs, engines, _) in zip(worlds, rules, groups):
        res = []
        for spec, r, e in zip(specs, objs, engines):
            m = e.finish()
            timing = dict(engine_s=e.wall, radio_s=t_radio, total_s=time.perf_counter() - t0)
            if len(worlds) > 1:
                timing["radio_shared"] = float(len(worlds))
            res.append(RunResult(world.seed, r.name, r.family, r.params(), m, e.events, timing,
                                 e.fingerprint, e.n_events, _key(spec, r), e.trace))
        out.append(res)
    return out


def simulate(scenario: Scenario, rules: Sequence[RuleSpec], seeds: Iterable[int] = (1,),
             log_events: Union[bool, str] = False,
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


def run_experiment(exp: Experiment, log_events: Union[bool, str] = False,
                   progress: Optional[Callable[[str], None]] = None, debug: Optional[bool] = None) -> List[RunResult]:
    """Run an :class:`~handoverlab.config.Experiment` (scenario, seeds and rules)."""
    return simulate(exp.scenario, exp.rules, exp.seeds, log_events, progress, debug)


def simulate_variants(scenarios: Sequence[Scenario], rules: Sequence[RuleSpec], seeds: Iterable[int] = (1,),
                      log_events: Union[bool, str] = False, progress: Optional[Callable[[str], None]] = None,
                      debug: Optional[bool] = None, share_radio: bool = True) -> List[List[RunResult]]:
    """Run ``rules`` on every scenario of ``scenarios`` for every seed (since 2.11.0).

    Returns one list per scenario, equal to ``simulate(scenario, rules,
    seeds, ...)``.  With ``share_radio`` (the default) the scenarios with the
    same :func:`radio_key` run on one radio stream per seed
    (:func:`run_shared`): each still gets its own world and engines, and its
    results are bit-identical to a separate run; the radio samples are made
    once per group instead of once per scenario.
    """
    seeds = [int(s) for s in seeds]
    groups: Dict[str, List[int]] = {}
    for i, sc in enumerate(scenarios):
        groups.setdefault(radio_key(sc) if share_radio else str(i), []).append(i)
    per: List[List[RunResult]] = [[] for _ in scenarios]
    for seed in seeds:
        for idx in groups.values():
            t0 = time.perf_counter()
            worlds, t_world = [], []
            for i in idx:
                tw = time.perf_counter()
                worlds.append(build_world(scenarios[i], seed))
                t_world.append(time.perf_counter() - tw)
            res = run_shared(worlds, [rules] * len(idx), log_events, debug=debug)
            for i, tw, rs in zip(idx, t_world, res):
                for r in rs:
                    r.timing["world_s"] = tw
                per[i].extend(rs)
            if progress:
                progress("seed %d: %d scenario(s) x %d rules on one radio stream in %.1f s"
                         % (seed, len(idx), len(rules), time.perf_counter() - t0))
            del worlds
    return per
