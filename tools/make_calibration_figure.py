# SPDX-License-Identifier: MIT
"""Draw docs/images/calibration_38901.png: HandoverLab against the 21 companies of 3GPP R1-165974.

Run from the repository root:  python tools/make_calibration_figure.py [n_users]
"""
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from handoverlab.verify import calibration as cal  # noqa: E402

OUT = os.path.join("docs", "images", "calibration_38901.png")
COL = {6.0: "#2a78d6", 30.0: "#eb6834"}          # categorical slots 1 and 2
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def main(n_users: int = 30000) -> None:
    ref = cal.load_reference()
    fig, axes = plt.subplots(2, 3, figsize=(12.0, 6.6), sharey=True)
    for j, name in enumerate(("UMa", "UMi", "Indoor")):
        for f in (6.0, 30.0):
            sc = cal.CalScenario(name, f)
            res = cal.simulate_drops(sc, n_users, 1)
            r = ref[sc.key]
            p = r["cdf_percent"] / 100.0
            for i, (m, sign) in enumerate((("coupling_gain_db", -1.0), ("sinr_db", 1.0))):
                ax = axes[i, j]
                # R1-165974 stores the coupling gain (-CL): the CDF of the loss at -x is 1 - p
                q = 1.0 - p if sign < 0 else p
                lo, hi = sign * r[m + "_min"], sign * r[m + "_max"]
                ax.fill_betweenx(q, np.minimum(lo, hi), np.maximum(lo, hi), color=COL[f], alpha=0.16, lw=0)
                ax.plot(sign * r[m + "_mean"], q, color=COL[f], lw=1.2, ls=(0, (4, 3)))
                x = np.sort(sign * res[m])
                ax.plot(x, np.arange(1, len(x) + 1) / len(x), color=COL[f], lw=2.0)
        axes[0, j].set_title({"UMa": "UMa (ISD 500 m)", "UMi": "UMi street canyon (ISD 200 m)",
                              "Indoor": "Indoor office (open)"}[name], color=INK, fontsize=11)
    for ax in axes.ravel():
        ax.grid(color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color(MUTED)
        ax.tick_params(colors=MUTED, labelsize=9)
        ax.set_ylim(0, 1)
    for j in range(3):
        axes[0, j].set_xlabel("coupling loss to the serving sector [dB]", color=MUTED, fontsize=9)
        axes[1, j].set_xlabel("geometry (wideband SINR) [dB]", color=MUTED, fontsize=9)
    for i in range(2):
        axes[i, 0].set_ylabel("CDF", color=MUTED, fontsize=9)
    handles = [plt.Line2D([], [], color=COL[6.0], lw=6), plt.Line2D([], [], color=COL[30.0], lw=6),
               plt.Line2D([], [], color=INK, lw=2.0), plt.Line2D([], [], color=INK, lw=1.2, ls=(0, (4, 3))),
               plt.Rectangle((0, 0), 1, 1, color=MUTED, alpha=0.25, lw=0)]
    fig.legend(handles, ["6 GHz", "30 GHz", "HandoverLab", "3GPP R1-165974: mean of 21 companies",
                         "range of the companies"],
               loc="upper center", ncol=5, frameon=False, fontsize=10, bbox_to_anchor=(0.5, 0.955))
    fig.suptitle("Large-scale calibration of TR 38.901 (clause 7.8.1)", y=0.995, color=INK, fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.91))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    fig.savefig(OUT, dpi=150, bbox_inches="tight", facecolor="#fcfcfb")
    print("wrote", OUT)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 30000)
