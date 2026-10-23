# SPDX-License-Identifier: MIT
"""Draw docs/images/procedures.png: baseline, conditional, DAPS, LTM and conditional LTM handover compared.

The experiment of section 1 of docs/guides/daps-ltm.md: the card smoke with radio.isolation 1.0 and 20 users of
the profile veh30, 30 s (5 s warm-up), seeds 1 to 3; A3 and DAPS (offset 3 dB, time-to-trigger 160 ms), CHO
(preparation offset -2 dB, execution offset 3 dB, 80 ms), LTM and conditional LTM (preparation -3 dB, switch
2 dB, 80 ms), all on the same worlds.  Left: mobility failures and ping-pong handovers; middle: interruption
by executions and by re-establishments; right: RRC messages over the air.  Every bar is the mean over the
three seeds, per UE-minute.

Run from the repository root:  python tools/make_procedures_figure.py   (about one minute)
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

OUT = os.path.join("docs", "images", "procedures.png")
CARD, SEEDS = "smoke", (1, 2, 3)
RULES = [("A3", {"rule": "a3", "off_db": 3.0, "ttt_s": 0.16}),
         ("CHO", {"rule": "cho", "o_prep_db": -2.0, "o_exec_db": 3.0, "ttt_exec_s": 0.08}),
         ("DAPS", {"rule": "daps", "off_db": 3.0, "ttt_s": 0.16}),
         ("LTM", {"rule": "ltm", "o_prep_db": -3.0, "o_switch_db": 2.0, "ttt_switch_s": 0.08}),
         ("CLTM", {"rule": "cltm", "o_prep_db": -3.0, "o_switch_db": 2.0, "ttt_switch_s": 0.08})]
BLUE, GREEN = "#2a78d6", "#1baf7a"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def style(a):
    a.grid(color=GRID, lw=0.8, axis="y")
    a.set_axisbelow(True)
    for s in ("top", "right"):
        a.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        a.spines[s].set_color(MUTED)
    a.tick_params(colors=MUTED, labelsize=9)


def main() -> None:
    sc = Scenario.from_dict(merge(resolve(CARD), {"radio": {"isolation": 1.0},
                                                  "mobility": {"users": 20, "profile": "veh30"}}))
    res = simulate(sc, [r for _, r in RULES], SEEDS)
    m = {}
    for name, spec in RULES:
        rows = [r.metrics for r in res if r.key == spec["rule"]]
        m[name] = {k: float(np.mean([x[k] for x in rows])) for k in rows[0]}
    names = [n for n, _ in RULES]
    x = np.arange(len(names))
    fig, axs = plt.subplots(1, 3, figsize=(10.0, 4.0))

    a = axs[0]
    top = 0.0
    for key, lab, col, dx in (("failures_pm", "failures", "#d23c3c", -0.2), ("pingpong_pm", "ping-pong", MUTED, 0.2)):
        v = np.array([m[n][key] for n in names])
        a.bar(x + dx, v, 0.4, color=col, label=lab)
        for i, y in enumerate(v):
            a.text(i + dx, y, "%.1f" % y, ha="center", va="bottom", fontsize=7, color=INK)
        top = max(top, v.max())
    a.set_ylim(0.0, 1.3 * top)
    a.set_title("Failures and ping-pong", fontsize=10, color=INK, loc="left")
    a.legend(frameon=False, fontsize=8, loc="upper left")

    a = axs[1]
    ex = np.array([m[n]["interruption_exec_s_pm"] for n in names]) * 1e3
    fa = np.array([m[n]["interruption_fail_s_pm"] for n in names]) * 1e3
    a.bar(x, ex, 0.6, color=BLUE, label="executions")
    a.bar(x, fa, 0.6, bottom=ex, color="#d23c3c", label="re-establishments")
    for i, v in enumerate(ex + fa):
        a.text(i, v, "%.0f" % v, ha="center", va="bottom", fontsize=8, color=INK)
    a.set_ylim(0.0, 1.3 * (ex + fa).max())
    a.set_title("Interruption [ms]", fontsize=10, color=INK, loc="left")
    a.legend(frameon=False, fontsize=8, loc="upper right")

    a = axs[2]
    rrc = np.array([m[n]["rrc_messages_pm"] for n in names])
    a.bar(x, rrc, 0.6, color=GREEN)
    for i, v in enumerate(rrc):
        a.text(i, v, "%.0f" % v, ha="center", va="bottom", fontsize=8, color=INK)
    a.set_ylim(0.0, 1.2 * rrc.max())
    a.set_title("RRC messages", fontsize=10, color=INK, loc="left")
    for a in axs:
        a.set_xticks(x)
        a.set_xticklabels(names, fontsize=9)
        style(a)
    axs[0].set_ylabel("per UE-minute", color=INK)
    fig.suptitle("Handover procedures on one world, card %s (isolation 1.0, 20 users at veh30, %.0f s), "
                 "seeds 1-3, per UE-minute" % (CARD, sc.run.duration_s), fontsize=11, color=INK, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(OUT, dpi=150)
    print("wrote", OUT)
    keys = ["too_late_pm", "too_early_pm", "wrong_cell_pm", "failures_pm", "interruption_exec_s_pm",
            "interruption_fail_s_pm", "rrc_messages_pm", "handovers_pm", "pingpong_pm", "outage_pct"]
    for n in names:
        print(n, {k: round(m[n][k], 4) for k in keys})


if __name__ == "__main__":
    main()
