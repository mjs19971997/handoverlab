# SPDX-License-Identifier: MIT
"""Draw docs/images/buffers.png: user-plane data at handover with protocol.buffers (since 2.3.0).

The card smoke with 15 users, 30 s (5 s warm-up), seeds 1 and 2, RLC AM and periodic traffic (100-byte packets
every 20 ms), as in section 6 of docs/guides/buffers.md.  A3, CHO (late forwarding), DAPS and LTM with their
default parameters run on the same worlds, once with forwarding over Xn (5 ms one way) and once without.
Left: the share of the arrived PDCP data that is lost.  Right: with forwarding, the mean PDCP delay of all
delivered data and of the data that were forwarded.  Every bar is the mean over the two seeds.

Run from the repository root:  python tools/make_buffers_figure.py   (about two minutes)
"""
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from handoverlab.config import Scenario  # noqa: E402
from handoverlab.scenarios import merge, resolve  # noqa: E402
from handoverlab.simulate import simulate  # noqa: E402

OUT = os.path.join("docs", "images", "buffers.png")
CARD, SEEDS, USERS, DURATION_S, WARMUP_S = "smoke", (1, 2), 15, 30.0, 5.0
RULES = [("A3", {"rule": "a3"}), ("CHO", {"rule": "cho"}), ("DAPS", {"rule": "daps"}), ("LTM", {"rule": "ltm"})]
BLUE, ORANGE, GREEN = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def scenario(fwd: bool) -> Scenario:
    d = merge(resolve(CARD), {"mobility": {"users": USERS}, "traffic": {"model": "periodic", "period_s": 0.02,
                                                                         "packet_bytes": 100},
                              "protocol": {"buffers": "am", "forwarding": fwd, "xn_delay_s": 0.005},
                              "run": {"duration_s": DURATION_S, "warmup_s": WARMUP_S}})
    return Scenario.from_dict(d)


def metrics(fwd: bool):
    """Mean of every metric over the seeds, per rule name."""
    res = simulate(scenario(fwd), [r for _, r in RULES], SEEDS)
    out = {}
    for name, spec in RULES:
        rows = [r.metrics for r in res if r.key == spec["rule"]]
        out[name] = {k: float(np.mean([m[k] for m in rows])) for k in rows[0]}
    return out


def style(a):
    a.grid(color=GRID, lw=0.8, axis="y")
    a.set_axisbelow(True)
    for s in ("top", "right"):
        a.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        a.spines[s].set_color(MUTED)
    a.tick_params(colors=MUTED, labelsize=9)


def label(a, bars, fmt):
    for b in bars:
        v = b.get_height()
        a.text(b.get_x() + b.get_width() / 2, v, fmt % v, ha="center", va="bottom", fontsize=8, color=INK)


def main() -> None:
    on, off = metrics(True), metrics(False)
    names = [n for n, _ in RULES]
    x = np.arange(len(names))
    w = 0.38
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(10.0, 4.2))
    label(ax, ax.bar(x - w / 2, [100.0 * off[n]["pdcp_lost_share"] for n in names], w, color=ORANGE,
                     label="no forwarding"), "%.2f %%")
    label(ax, ax.bar(x + w / 2, [100.0 * on[n]["pdcp_lost_share"] for n in names], w, color=BLUE,
                     label="forwarding over Xn"), "%.2f %%")
    ax.set_ylabel("lost share of the arrived data [%]", color=INK)
    ax.set_title("Data lost", fontsize=10, color=INK, loc="left")
    ax.legend(frameon=False, fontsize=8, loc="upper right")

    label(bx, bx.bar(x - w / 2, [on[n]["pdcp_delay_ms"] for n in names], w, color=BLUE, label="all delivered data"),
          "%.1f")
    label(bx, bx.bar(x + w / 2, [on[n]["pdcp_delay_forwarded_ms"] for n in names], w, color=GREEN,
                     label="forwarded data"), "%.0f")
    bx.set_yscale("log")
    bx.set_ylim(0.1, 1000.0)
    bx.set_ylabel("mean PDCP delay [ms]", color=INK)
    bx.set_title("Delay, with forwarding", fontsize=10, color=INK, loc="left")
    bx.legend(frameon=False, fontsize=8, loc="upper left", ncol=2)
    for a in (ax, bx):
        a.set_xticks(x)
        a.set_xticklabels(names, fontsize=9)
        style(a)
    fig.suptitle("User-plane buffers at handover, card %s: %d users, %.0f s, seeds %s, RLC AM, 100 B every 20 ms"
                 % (CARD, USERS, DURATION_S, " and ".join(map(str, SEEDS))), fontsize=11, color=INK, x=0.01,
                 ha="left")
    fig.tight_layout()
    fig.savefig(OUT, dpi=150)
    print("wrote", OUT)
    keys = ("pdcp_lost_share", "pdcp_forwarded_kbyte_pm", "pdcp_delay_ms", "pdcp_delay_forwarded_ms",
            "handovers_pm", "failures_pm")
    for n in names:
        print(n, "fwd", {k: round(on[n][k], 4) for k in keys}, "no fwd", {k: round(off[n][k], 4) for k in keys})


if __name__ == "__main__":
    main()
