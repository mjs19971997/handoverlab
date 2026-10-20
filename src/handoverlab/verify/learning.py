# SPDX-License-Identifier: MIT
"""The learning rule ``a3_bandit`` against an exhaustive search (since 1.11.0): ``handoverlab verify --only learning``.

The bandit learns, per cell, which of its A3 offsets (arms) earns the highest
reward per outcome (useful +1, unnecessary -w_unnecessary, early, late or a
link failure -w_failure).  Its own objective can also be measured for every
arm used as a fixed A3 offset: a bandit with that single arm is A3 with that
offset (checked: identical event log), and its record gives the reward per
outcome.  The arm with the highest pooled reward, ``b*``, is what an
exhaustive search (grid search) over the arms finds.

Set-up and criteria, fixed in a plan before the first run: the ``smoke`` card
with 900 s per run (5 s warm-up), seeds 1, 2 and 3 (the same worlds for every
rule), the rule's default arms (1 to 5 dB), TTT 160 ms, epsilon 0.1, epoch 10
and weights 1 and 2.

B1  in the second half of the epochs the share of epochs played on arms within
    one arm of ``b*`` is at least 0.6 (if the best two arms differ by less than
    the standard error over the seeds, on the arms within one standard error of
    the best);
B2  the bandit's reward per outcome over the whole run is at least the median of
    the fixed arms;
B3  its reward per outcome in the second half of the run is at least
    best - 0.5 x (best - worst) of the fixed arms.
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np

from ..channel.source import RadioSource
from ..engine.batch import EngineBatch
from ..engine.core import Engine
from ..rules import make_rule
from ..scenarios import builtin_scenario
from ..world import build_world

SEEDS = (1, 2, 3)
DURATION_S = 900.0


def _run(world, rules):
    """Run rule objects on one world and return (rules, engines) so that the rules' records can be read."""
    engines = [Engine(world, r, False, None) for r in rules]
    runner = EngineBatch(engines) if EngineBatch.supported(engines) else None
    for ch in RadioSource(world).chunks():
        if runner is not None:
            runner.advance(ch)
        else:
            for e in engines:
                e.advance(ch)
    for e in engines:
        e.finish()
    return engines


def bandit_vs_grid(duration_s: float = DURATION_S, seeds=SEEDS) -> Dict[str, object]:
    sc = builtin_scenario("smoke").with_overrides({"run.duration_s": duration_s, "run.warmup_s": 5.0})
    arms = list(make_rule({"rule": "a3_bandit"}).arms_db)
    fixed: List[List[float]] = [[] for _ in arms]       # rewards of every outcome, per arm
    per_seed = np.zeros((len(seeds), len(arms)))
    band_all, band_late, epochs_late, same_log = [], [], [], True
    for i, seed in enumerate(seeds):
        world = build_world(sc, seed)
        rules = [make_rule({"rule": "a3_bandit", "arms_db": [a], "name": "A3-%g" % a}) for a in arms]
        rules += [make_rule({"rule": "a3", "off_db": arms[0], "ttt_s": 0.16, "name": "A3"}),
                  make_rule({"rule": "a3_bandit"})]
        eng = _run(world, rules)
        same_log &= eng[0].fingerprint == eng[len(arms)].fingerprint
        for k in range(len(arms)):
            r = [o[3] for o in rules[k].outcomes]
            fixed[k].extend(r)
            per_seed[i, k] = np.mean(r) if r else np.nan
        b = rules[-1]
        half = duration_s / 2.0
        band_all.extend(o[3] for o in b.outcomes)
        band_late.extend(o[3] for o in b.outcomes if o[0] >= half)
        ep = b.epochs
        epochs_late.extend(a for _, _, a in ep[len(ep) // 2:])
    obj = np.array([np.mean(f) for f in fixed])
    se = per_seed.std(axis=0, ddof=1) / np.sqrt(len(seeds)) if len(seeds) > 1 else np.zeros(len(arms))
    best = int(np.argmax(obj))
    order = np.argsort(obj)[::-1]
    close = obj[order[0]] - obj[order[1]] < se[order[0]]
    near = {a for a in range(len(arms)) if abs(a - best) <= 1}
    if close:
        near = {a for a in range(len(arms)) if obj[best] - obj[a] <= se[best]}
    share = float(np.mean([a in near for a in epochs_late])) if epochs_late else float("nan")
    return dict(arms=arms, objective=obj, se=se, best=best, close=bool(close), near=sorted(near), share=share,
                bandit_all=float(np.mean(band_all)), bandit_late=float(np.mean(band_late)),
                n_epochs_late=len(epochs_late), same_log=bool(same_log))


def learning_checks(rep, duration_s: float = DURATION_S) -> None:
    rep.section("learning", "the learning rule a3_bandit against an exhaustive search over its arms (smoke card, "
                            "%.0f s, seeds %s)" % (duration_s, ", ".join(map(str, SEEDS))))
    r = bandit_vs_grid(duration_s)
    obj, arms, best = r["objective"], r["arms"], r["best"]
    rep.check("a one-arm bandit is A3 with that offset (identical event log)", r["same_log"], "3 seeds")
    grid = ", ".join("%g dB %.3f" % (a, o) for a, o in zip(arms, obj))
    rep.note("exhaustive search: reward per outcome of every arm as a fixed A3 offset", grid +
             "; best %g dB%s" % (arms[best], " (within one standard error of the second best)" if r["close"] else ""))
    rep.check("B1: second half of the epochs on the best arm or a neighbour (>= 0.6)", r["share"] >= 0.6,
              "%.2f of %d epochs on %s dB" % (r["share"], r["n_epochs_late"],
                                              ", ".join("%g" % arms[a] for a in r["near"])))
    med = float(np.median(obj))
    rep.check("B2: reward per outcome over the whole run >= median of the fixed arms", r["bandit_all"] >= med,
              "%.3f against %.3f" % (r["bandit_all"], med))
    lim = obj.max() - 0.5 * (obj.max() - obj.min())
    rep.check("B3: reward per outcome in the second half >= best - 0.5 x (best - worst)", r["bandit_late"] >= lim,
              "%.3f against %.3f (best %.3f, worst %.3f)" % (r["bandit_late"], lim, obj.max(), obj.min()))
