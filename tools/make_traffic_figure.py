# SPDX-License-Identifier: MIT
"""Draw docs/images/traffic.png: the per-user traffic models (traffic.model, since 1.4.0) and the energy metric.

The card smoke (20 users, 30 s, 5 s warm-up), seeds 1 to 3, rule A3 (offset 3 dB, time-to-trigger 160 ms), with
each of the four traffic models at its defaults: fixed (constant service rates), full_buffer, periodic (100 bytes
every 20 ms) and ftp3 (0.5 Mbyte files, 0.1 per user and second).  The mobility events are the same for all
four (the traffic does not change the radio or the decisions); what changes is the delivered rate per user,
the mean cell load and the network energy per delivered bit (EARTH model of the cells' input power).  Every bar
is the mean over the three seeds.

Run from the repository root:  python tools/make_traffic_figure.py   (about one minute)
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

OUT = os.path.join("docs", "images", "traffic.png")
CARD, SEEDS = "smoke", (1, 2, 3)
MODELS = [("fixed", "fixed"), ("full_buffer", "full\nbuffer"), ("periodic", "periodic\n100 B per\n20 ms"),
          ("ftp3", "ftp3\n0.5 MB files\n0.1 per s")]
COL = ["#52514e", "#2a78d6", "#1baf7a", "#eb6834"]
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def main() -> None:
    m = {}
    for key, _ in MODELS:
        sc = Scenario.from_dict(merge(resolve(CARD), {"traffic": {"model": key}}))
        res = simulate(sc, [{"rule": "a3", "off_db": 3.0, "ttt_s": 0.16}], SEEDS)
        m[key] = {k: float(np.mean([r.metrics[k] for r in res])) for k in res[0].metrics}
        print(key, {k: round(m[key][k], 4) for k in ("rate_mbps", "delivered_share", "mean_load", "site_power_w",
                                                      "energy_uj_per_bit", "handovers_pm", "rrc_messages_pm")},
              flush=True)
    keys = [k for k, _ in MODELS]
    x = np.arange(len(keys))
    fig, axs = plt.subplots(1, 3, figsize=(10.0, 3.9))
    panels = [("rate_mbps", "Delivered rate per user [Mbit/s]", True, "%.3g"),
              ("mean_load", "Mean cell load", False, "%.2f"),
              ("energy_uj_per_bit", "Energy per delivered bit [µJ/bit]", True, "%.3g")]
    for a, (k, title, log, fmt) in zip(axs, panels):
        v = np.array([m[c][k] for c in keys])
        bars = a.bar(x, v, 0.62, color=COL)
        for b, y in zip(bars, v):
            a.text(b.get_x() + b.get_width() / 2, y, "%.0f" % y if y >= 100 else fmt % y, ha="center",
                   va="bottom", fontsize=8, color=INK)
        if log:
            a.set_yscale("log")
            a.set_ylim(v.min() / 3.0, v.max() * 6.0)
        else:
            a.set_ylim(0.0, 1.2 * v.max())
        a.set_title(title, fontsize=10, color=INK, loc="left")
        a.set_xticks(x)
        a.set_xticklabels([lab for _, lab in MODELS], fontsize=8)
        a.grid(color=GRID, lw=0.8, axis="y")
        a.set_axisbelow(True)
        for s in ("top", "right"):
            a.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            a.spines[s].set_color(MUTED)
        a.tick_params(colors=MUTED, labelsize=8)
    p = [m[c]["site_power_w"] for c in keys]
    ho = [m[c]["handovers_pm"] for c in keys]
    same = "the same %.1f handovers per UE-minute" % ho[0] if max(ho) == min(ho) else \
        "%.1f to %.1f handovers per UE-minute" % (min(ho), max(ho))
    fig.suptitle("Traffic models, card %s (%d users, %.0f s), seeds 1-3, A3: %s;\nmean input power per cell %.0f to "
                 "%.0f W" % (CARD, sc.mobility.users, sc.run.duration_s, same, min(p), max(p)), fontsize=11,
                 color=INK, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(OUT, dpi=150)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
