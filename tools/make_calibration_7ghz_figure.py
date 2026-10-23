# SPDX-License-Identifier: MIT
"""Draw docs/images/calibration_7ghz.png: HandoverLab against the companies of 3GPP R1-2506406 (since 2.4.0).

The 7 GHz cases of TR 38.901 clause 7.8.1 and Table 7.8-1A (UMa, UMi-Street Canyon, SMa with ISD 1299 m and
1732 m), drawn as calibration_38901.png draws R1-165974.  The 6 GHz reruns of R1-2506406 are computed as well
and printed, not drawn.  The subtitle is computed from the same run.

Run from the repository root:  python tools/make_calibration_7ghz_figure.py [n_users]
"""
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from handoverlab.verify import calibration as cal  # noqa: E402

OUT = os.path.join("docs", "images", "calibration_7ghz.png")
COL = "#2a78d6"                                   # categorical slot 1
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
TITLES = {"UMa-7GHz": "UMa (ISD 500 m)", "UMi-7GHz": "UMi street canyon (ISD 200 m)",
          "SMa-7GHz-1299m": "SMa (ISD 1299 m)", "SMa-7GHz-1732m": "SMa (ISD 1732 m)"}


def main(n_users: int = 30000) -> None:
    ref = cal.load_reference(cal.DATA_R1_2506406)
    drawn = [sc for sc in cal.CASES_R1_2506406 if sc.fc_ghz == 7.0]
    worst = {}
    for sc in cal.CASES_R1_2506406:
        res = cal.simulate_drops(sc, n_users, 1)
        comps = cal.compare(sc, res, ref)
        worst[sc.key] = (all(bool(c.inside.all()) for c in comps), max(c.max_dev_db for c in comps), res)
        print("%-15s all 5-95 %% percentiles inside: %s; largest distance from the mean %.2f dB (%s)"
              % (sc.key, worst[sc.key][0], worst[sc.key][1],
                 ", ".join("%s %d/%d" % (c.metric, c.inside.sum(), len(c.percentiles)) for c in comps)))
    fig, axes = plt.subplots(2, len(drawn), figsize=(13.0, 6.6), sharey=True)
    for j, sc in enumerate(drawn):
        r, res = ref[sc.key], worst[sc.key][2]
        p = r["cdf_percent"] / 100.0
        for i, (m, sign) in enumerate((("coupling_gain_db", -1.0), ("sinr_db", 1.0))):
            ax = axes[i, j]
            # R1-2506406 stores the coupling gain (-CL): the CDF of the loss at -x is 1 - p
            q = 1.0 - p if sign < 0 else p
            lo, hi = sign * r[m + "_min"], sign * r[m + "_max"]
            ax.fill_betweenx(q, np.minimum(lo, hi), np.maximum(lo, hi), color=COL, alpha=0.18, lw=0)
            ax.plot(sign * r[m + "_mean"], q, color=INK, lw=1.2, ls=(0, (4, 3)))
            x = np.sort(sign * res[m])
            ax.plot(x, np.arange(1, len(x) + 1) / len(x), color=COL, lw=2.0)
            ax.text(0.97, 0.05, "%d companies" % int(r[m + "_n"][0]), transform=ax.transAxes, ha="right",
                    va="bottom", color=MUTED, fontsize=9)
        axes[0, j].set_title(TITLES[sc.key], color=INK, fontsize=11)
    for ax in axes.ravel():
        ax.grid(color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color(MUTED)
        ax.tick_params(colors=MUTED, labelsize=9)
        ax.set_ylim(0, 1)
    for j in range(len(drawn)):
        axes[0, j].set_xlabel("coupling loss to the serving sector [dB]", color=MUTED, fontsize=9)
        axes[1, j].set_xlabel("geometry (wideband SINR) [dB]", color=MUTED, fontsize=9)
    for i in range(2):
        axes[i, 0].set_ylabel("CDF", color=MUTED, fontsize=9)
    handles = [plt.Line2D([], [], color=COL, lw=2.0), plt.Line2D([], [], color=INK, lw=1.2, ls=(0, (4, 3))),
               plt.Rectangle((0, 0), 1, 1, color=COL, alpha=0.25, lw=0)]
    fig.legend(handles, ["HandoverLab (%d users)" % n_users, "3GPP R1-2506406: mean of the companies",
                         "range of the companies"],
               loc="upper center", ncol=3, frameon=False, fontsize=10, bbox_to_anchor=(0.5, 0.925))
    keys = [sc.key for sc in drawn]
    devs = [worst[k][1] for k in keys]
    inside = all(worst[k][0] for k in keys)
    fig.suptitle("Large-scale calibration at 7 GHz, TR 38.901 clause 7.8.1 and Table 7.8-1A\n"
                 "%s; largest distance from the company mean %.2f-%.2f dB per case"
                 % ("every 5-95 % percentile inside the company range" if inside
                    else "NOT every 5-95 % percentile inside the company range", min(devs), max(devs)),
                 y=0.995, color=INK, fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    fig.savefig(OUT, dpi=150, bbox_inches="tight", facecolor="#fcfcfb")
    print("wrote", OUT)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 30000)
