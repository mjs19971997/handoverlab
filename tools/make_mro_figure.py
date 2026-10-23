# SPDX-License-Identifier: MIT
"""Draw docs/images/mro.png: mobility robustness optimisation with the rule a3_mro (since 1.7.0).

The experiment of section 2 of docs/guides/mro.md: the card urban-grid-10ghz with 30 users of the profile veh30,
radio.isolation 1.0, 300 s (60 s warm-up).  Left: on seed 1, the cell individual offset (CIO) of every pair of
serving and neighbour cell that a3_mro (A3 offset 6 dB, time-to-trigger 160 ms, windows of 10 s, steps of 1 dB,
CIO within -4 and 4 dB) ever moved, read at the end of every window, and their mean.  Right: fixed A3 and
a3_mro from 6 dB and from 3 dB on the same worlds, seeds 1 to 3: all failures, the too-late and too-early
classes of TS 38.300 15.5.2 and ping-pong handovers per UE-minute (mean over the seeds, after the warm-up).

Run from the repository root:  python tools/make_mro_figure.py   (about three minutes)
"""
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from handoverlab.channel.source import RadioSource  # noqa: E402
from handoverlab.config import Scenario  # noqa: E402
from handoverlab.engine.core import Engine  # noqa: E402
from handoverlab.rules import make_rule  # noqa: E402
from handoverlab.scenarios import merge, resolve  # noqa: E402
from handoverlab.simulate import simulate  # noqa: E402
from handoverlab.world import build_world  # noqa: E402

OUT = os.path.join("docs", "images", "mro.png")
CARD, SEEDS = "urban-grid-10ghz", (1, 2, 3)
RULES = [("A3 6 dB", {"rule": "a3", "name": "A3-6dB", "off_db": 6.0}),
         ("MRO from 6 dB", {"rule": "a3_mro", "name": "MRO-6dB", "off_db": 6.0}),
         ("A3 3 dB", {"rule": "a3", "name": "A3-3dB"}),
         ("MRO from 3 dB", {"rule": "a3_mro", "name": "MRO-3dB"})]
BARS = [("failures_pm", "all failures", "#d23c3c"), ("too_late_pm", "too late", "#eb6834"),
        ("too_early_pm", "too early", "#f2b134"), ("pingpong_pm", "ping-pong", "#2a78d6")]
BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def scenario() -> Scenario:
    return Scenario.from_dict(merge(resolve(CARD), {"mobility": {"users": 30, "profile": "veh30"},
                                                    "radio": {"isolation": 1.0},
                                                    "run": {"duration_s": 300.0, "warmup_s": 60.0}}))


def cio_history(sc):
    world = build_world(sc, SEEDS[0])
    rule = make_rule({"rule": "a3_mro", "off_db": 6.0})
    eng = Engine(world, rule)
    rule = eng.rule
    hist = []
    update = rule.update

    def record():
        update()
        hist.append((rule.next_update, rule.cio.copy()))

    rule.update = record
    for ch in RadioSource(world).chunks():
        eng.advance(ch)
    eng.finish()
    return np.array([t for t, _ in hist]), np.array([c for _, c in hist])


def main() -> None:
    sc = scenario()
    t, cio = cio_history(sc)
    moved = np.any(cio != 0.0, axis=0)
    traj = cio[:, moved]                                       # (windows, moved pairs)
    t = np.concatenate([[0.0], t])
    traj = np.vstack([np.zeros((1, traj.shape[1])), traj])
    res = simulate(sc, [r for _, r in RULES], SEEDS)
    m = {}
    for name, spec in RULES:
        rows = [r.metrics for r in res if r.rule == spec["name"]]
        m[name] = {k: float(np.mean([x[k] for x in rows])) for k in rows[0]}

    fig, (ax, bx) = plt.subplots(1, 2, figsize=(10.0, 4.2), gridspec_kw={"width_ratios": [1.15, 1.0]})
    rng = np.random.default_rng(0)
    for j in range(traj.shape[1]):                             # a small vertical jitter so that equal paths show
        ax.step(t, 6.0 + traj[:, j] + rng.uniform(-0.08, 0.08), where="post", color=BLUE, lw=0.6, alpha=0.35)
    ax.step(t, 6.0 + traj.mean(axis=1), where="post", color=INK, lw=2.0, label="mean of these pairs")
    ax.plot([], [], color=BLUE, lw=0.8, alpha=0.6, label="each pair whose CIO moved (%d)" % traj.shape[1])
    ax.axvspan(0.0, sc.run.warmup_s, color=GRID, alpha=0.6, lw=0)
    ax.text(sc.run.warmup_s / 2, 10.1, "warm-up", ha="center", fontsize=8, color=MUTED)
    ax.set_xlim(0.0, sc.run.duration_s)
    ax.set_ylim(3.5, 10.5)
    ax.set_xlabel("time [s]", color=INK)
    ax.set_ylabel("A3 offset + CIO of the pair [dB]", color=INK)
    ax.legend(frameon=False, fontsize=8, loc="lower left")
    ax.set_title("a3_mro from 6 dB, seed %d: offsets at each window end" % SEEDS[0], fontsize=10, color=INK,
                 loc="left")

    names = [n for n, _ in RULES]
    x = np.arange(len(names))
    w = 0.2
    top = 0.0
    for j, (key, lab, col) in enumerate(BARS):
        v = np.array([m[n][key] for n in names])
        bx.bar(x + (j - 1.5) * w, v, w, color=col, label=lab)
        if key == "failures_pm":
            for i, y in enumerate(v):
                bx.text(i + (j - 1.5) * w, y, "%.2f" % y, ha="center", va="bottom", fontsize=7, color=INK)
        top = max(top, v.max())
    bx.set_xticks(x)
    bx.set_xticklabels(names, fontsize=8)
    bx.set_ylim(0.0, 1.3 * top)
    bx.set_ylabel("per UE-minute", color=INK)
    bx.legend(frameon=False, fontsize=8, loc="upper right", ncol=2)
    bx.set_title("Fixed A3 and a3_mro on the same worlds, seeds 1-3", fontsize=10, color=INK, loc="left")
    for a in (ax, bx):
        a.grid(color=GRID, lw=0.8, axis="y" if a is bx else "both")
        a.set_axisbelow(True)
        for s in ("top", "right"):
            a.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            a.spines[s].set_color(MUTED)
        a.tick_params(colors=MUTED, labelsize=9)
    fig.suptitle("Mobility robustness optimisation, card %s (isolation 1.0, 30 users at veh30, 300 s, 60 s warm-up)"
                 % CARD, fontsize=11, color=INK, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(OUT, dpi=150)
    print("wrote", OUT)
    print("windows", len(t) - 1, "moved pairs", int(moved.sum()), "of", moved.size, "final mean CIO of moved %.2f"
          % traj[-1].mean(), "final CIO values", np.unique(traj[-1], return_counts=True))
    for n in names:
        print(n, {k: round(m[n][k], 4) for k in ("failures_pm", "too_late_pm", "too_early_pm", "pingpong_pm",
                                                 "interruption_s_pm", "handovers_pm")})


if __name__ == "__main__":
    main()
