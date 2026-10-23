# SPDX-License-Identifier: MIT
"""Draw docs/images/dual-connectivity.png: NR-DC with protocol.dc (since 2.3.0).

The card dense-urban-2layer with protocol.dc: {scg_layer: micro-30ghz} (an FR1 master cell group on the 4 GHz
macro layer, an FR2 secondary cell group on the 30 GHz micro layer, default thresholds), reduced to 10 users
and 40 s (5 s warm-up), seed 1, Event A3 (offset 3 dB, time-to-trigger 160 ms) on the MCG.  The serving cell of
the MCG and the PSCell of the SCG are sampled every 50 ms.  Left: one user (the one with the most kinds of SCG
events in its procedure trace): its MCG cell, its PSCell and the SCG events of the trace.  Right: the rates of
the procedures over all users, per UE-minute, from the metrics of the same run.

Run from the repository root:  python tools/make_dc_figure.py   (about two minutes)
"""
import os
import sys
from collections import Counter

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from handoverlab.channel.extended import ExtendedSource  # noqa: E402
from handoverlab.config import Scenario  # noqa: E402
from handoverlab.engine.dual import DcEngine  # noqa: E402
from handoverlab.rules import make_rule  # noqa: E402
from handoverlab.scenarios import merge, resolve  # noqa: E402
from handoverlab.world import build_world  # noqa: E402

OUT = os.path.join("docs", "images", "dual-connectivity.png")
CARD, SEED, USERS, DURATION_S, WARMUP_S, SAMPLE = "dense-urban-2layer", 1, 10, 40.0, 5.0, 5
SCG_EVENTS = {"sn_add": ("SN addition", "#1baf7a", "^"), "pscell_change": ("PSCell change", "#2a78d6", "o"),
              "sn_release": ("SN release", "#52514e", "v"),
              "scg_release_mcg_failure": ("SCG released by MCG failure", "#d23c3c", "x"),
              "scg_release_mcg_ho": ("SCG released at MCG handover", "#d23c3c", "x"),
              "sn_add_failure": ("failed SN addition", "#d23c3c", "s"),
              "pscell_change_failure": ("failed PSCell change", "#d23c3c", "s"),
              "scg_rlf": ("SCG radio-link failure", "#d23c3c", "D")}
BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def main() -> None:
    d = merge(resolve(CARD), {"mobility": {"users": USERS}, "protocol": {"dc": {"scg_layer": "micro-30ghz"}},
                              "run": {"duration_s": DURATION_S, "warmup_s": WARMUP_S}})
    world = build_world(Scenario.from_dict(d), SEED)
    eng = DcEngine(world, make_rule({"rule": "a3", "off_db": 3.0, "ttt_s": 0.16}), log_events="full")
    dt = world.scenario.protocol.step_s
    ts, mcg, scg = [], [], []
    for ch in ExtendedSource(world, SAMPLE).chunks():
        eng.advance(ch)
        ts.append((ch.k0 + ch.n) * dt)
        mcg.append(np.where(eng.state == 0, eng.serv, -1).copy())
        ps = eng.dc.ps
        scg.append(np.where(ps >= 0, eng.dc.cells[np.maximum(ps, 0)], -1))
    m = eng.finish()
    ts, mcg, scg = np.array(ts), np.array(mcg, dtype=float), np.array(scg, dtype=float)
    trace = eng.trace
    kinds = {}
    for r in trace:
        if r["event"] in SCG_EVENTS:
            kinds.setdefault(r["ue"], Counter())[r["event"]] += 1
    u = max(kinds, key=lambda k: (len(kinds[k]), sum(kinds[k].values())))
    print("user", u, dict(kinds[u]))
    print("all trace events:", dict(Counter(r["event"] for r in trace)))

    fig = plt.figure(figsize=(10.0, 4.3))
    gs = fig.add_gridspec(2, 2, width_ratios=[1.6, 1.0], height_ratios=[1.0, 1.0], hspace=0.12)
    ax = fig.add_subplot(gs[0, 0])
    sx = fig.add_subplot(gs[1, 0], sharex=ax)
    bx = fig.add_subplot(gs[:, 1])
    a = mcg[:, u].copy()
    a[a < 0] = np.nan
    s = scg[:, u].copy()
    s[s < 0] = np.nan
    ax.step(ts, a, where="post", color=ORANGE, lw=1.8)
    sx.step(ts, s, where="post", color=BLUE, lw=1.8)
    ax.set_ylabel("MCG cell\n(4 GHz)", color=INK, fontsize=9)
    sx.set_ylabel("PSCell\n(30 GHz)", color=INK, fontsize=9)
    seen = set()
    for r in trace:
        if r["ue"] != u or r["event"] not in SCG_EVENTS:
            continue
        lab, col, mk = SCG_EVENTS[r["event"]]
        y = r["cell"] if r["cell"] >= 0 else r["src"]
        sx.plot(r["t"], y, mk, color=col, ms=6, mfc="none" if mk != "x" else col, mew=1.4,
                label=lab if lab not in seen else None, zorder=4)
        seen.add(lab)
    sx.legend(frameon=False, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.28), ncol=3)
    sx.set_xlabel("time [s]", color=INK)
    sx.set_xlim(0.0, DURATION_S)
    ax.set_title("User %d: serving cells (cell numbers) and SCG events" % u, fontsize=10, color=INK, loc="left")
    plt.setp(ax.get_xticklabels(), visible=False)

    rows = [("MCG handovers", m["handovers_pm"]), ("SN additions", m["sn_additions_pm"]),
            ("PSCell changes", m["pscell_changes_pm"]), ("SN releases", m["sn_releases_pm"]),
            ("SCG released by MCG", m["scg_released_by_mcg_pm"]), ("SCG failures", m["scg_failures_pm"])]
    y = np.arange(len(rows))[::-1]
    bars = bx.barh(y, [v for _, v in rows], color=[ORANGE, BLUE, BLUE, BLUE, BLUE, "#d23c3c"], height=0.6)
    for b, (_, v) in zip(bars, rows):
        bx.text(b.get_width(), b.get_y() + b.get_height() / 2, " %.2f" % v, va="center", fontsize=8, color=INK)
    bx.set_yticks(y)
    bx.set_yticklabels([n for n, _ in rows], fontsize=9)
    bx.set_xlabel("per UE-minute", color=INK)
    bx.set_xlim(0.0, 1.2 * max(v for _, v in rows))
    bx.set_title("All %d users: SCG time share %.2f\nper user SCG %.0f, MCG %.1f Mbit/s"
                 % (USERS, m["scg_time_share"], m["scg_rate_mbps"], m["rate_mbps"]), fontsize=10, color=INK,
                 loc="left")
    for a_ in (ax, sx, bx):
        a_.grid(color=GRID, lw=0.8, axis="x" if a_ is bx else "both")
        a_.set_axisbelow(True)
        for sp in ("top", "right"):
            a_.spines[sp].set_visible(False)
        for sp in ("left", "bottom"):
            a_.spines[sp].set_color(MUTED)
        a_.tick_params(colors=MUTED, labelsize=9)
    fig.suptitle("Dual connectivity (NR-DC), card %s: %d users, %.0f s (%.0f s warm-up), seed %d, A3 3 dB / 160 ms"
                 % (CARD, USERS, DURATION_S, WARMUP_S, SEED), fontsize=11, color=INK, x=0.01, ha="left")
    fig.subplots_adjust(left=0.08, right=0.97, top=0.83, bottom=0.2, wspace=0.55)
    fig.savefig(OUT, dpi=150)
    print("wrote", OUT)
    print({k: round(v, 3) for k, v in m.items() if k.startswith(("sn_", "pscell", "scg", "handovers", "rate"))})


if __name__ == "__main__":
    main()
