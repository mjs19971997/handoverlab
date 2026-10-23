# SPDX-License-Identifier: MIT
"""Draw docs/images/new-scenarios.png: the layouts of the cards added in 2.3.0 (since 2.4.0).

urban-macro-tr37885-4ghz (TR 37.885 urban grid with the 500 m macro lattice), suburban-sma-7ghz (TR 38.901 SMa
at 7 GHz) and hst-fr2-28ghz (TR 38.854 FR2 high-speed train).  Sites, buildings, the users' area and the track
come from the layout the engine builds (handoverlab.layout.make_layout), the labels from the cards.  The track
of the train is drawn with the y axis stretched; the dashed lines show where the one SSB beam of every RRH
points (radio.beams.sector_az0_deg and tilt_deg of the card).

Run from the repository root:  python tools/make_scenarios_figure.py
"""
import math
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import handoverlab as hl  # noqa: E402
from handoverlab.layout import make_layout  # noqa: E402

OUT = os.path.join("docs", "images", "new-scenarios.png")
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE = "#2a78d6", "#eb6834"
BUILDING, AREA = "#d9d8d4", "#f1f0ec"


def _style(ax, equal: bool = True) -> None:
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=8)
    if equal:
        ax.set_aspect("equal")


def _sites(ax, sites) -> None:
    ax.plot(sites[:, 0], sites[:, 1], "^", ms=6.5, color=ORANGE, mec=INK, mew=0.6, zorder=4)


def _nearest(sites) -> float:
    d = np.hypot(sites[:, None, 0] - sites[None, :, 0], sites[:, None, 1] - sites[None, :, 1])
    d[np.diag_indices(len(sites))] = np.inf
    return float(d.min())


def urban_macro(ax) -> None:
    sc = hl.builtin_scenario("urban-macro-tr37885-4ghz")
    lay = make_layout(sc.layout)
    ax.add_patch(Rectangle((lay.xmin, lay.ymin), lay.xmax - lay.xmin, lay.ymax - lay.ymin, fc=AREA, ec=INK,
                           lw=0.8, ls="--", zorder=1))
    for x0, y0, x1, y1 in lay.buildings:
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc=BUILDING, ec="none", zorder=2))
    _sites(ax, lay.sites)
    pad = 120.0
    ax.set_xlim(lay.sites[:, 0].min() - pad, lay.sites[:, 0].max() + pad)
    ax.set_ylim(lay.sites[:, 1].min() - pad, lay.sites[:, 1].max() + pad)
    _style(ax)
    ax.set_xlabel("x [m]", color=INK, fontsize=9)
    ax.set_ylabel("y [m]", color=INK, fontsize=9)
    ax.set_title("urban-macro-tr37885-4ghz (TR 37.885 urban grid)\n%d x %d blocks, road grid %.0f m x %.0f m;\n"
                 "%d macro sites %.0f m apart, %.0f GHz"
                 % (len(lay.xs) - 1, len(lay.ys) - 1, np.diff(lay.xs).mean(), np.diff(lay.ys).mean(),
                    lay.n_sites, _nearest(lay.sites), sc.radio.carrier_ghz), fontsize=9.5, color=INK, loc="left")


def suburban(ax) -> None:
    sc = hl.builtin_scenario("suburban-sma-7ghz")
    lay = make_layout(sc.layout)
    ax.add_patch(Rectangle((lay.xmin, lay.ymin), lay.xmax - lay.xmin, lay.ymax - lay.ymin, fc=AREA, ec=INK,
                           lw=0.8, ls="--", zorder=1))
    _sites(ax, lay.sites)
    pad = 150.0
    ax.set_xlim(lay.xmin - pad, lay.xmax + pad)
    ax.set_ylim(lay.ymin - pad, lay.ymax + pad)
    _style(ax)
    ax.set_xlabel("x [m]", color=INK, fontsize=9)
    ind = sum(g.share for g in sc.mobility.groups if g.indoor)
    car = [g for g in sc.mobility.groups if not g.indoor][0]
    ax.set_title("suburban-sma-7ghz (TR 38.901 SMa)\n%d sites %.0f m apart, %.0f GHz;\n"
                 "%.0f %% of the users indoors, %.0f %% in cars at %.0f km/h"
                 % (lay.n_sites, _nearest(lay.sites), sc.radio.carrier_ghz, 100 * ind, 100 * (1 - ind),
                    3.6 * car.v_min), fontsize=9.5, color=INK, loc="left")


def train(ax) -> None:
    sc = hl.builtin_scenario("hst-fr2-28ghz")
    lay = make_layout(sc.layout)
    b = sc.radio.beams
    ax.axhspan(lay.ys.min() - 0.6, lay.ys.max() + 0.6, color=MUTED, lw=0, zorder=1)
    az = math.radians(b.sector_az0_deg)
    span = sc.layout.site_spacing_m
    for x, y in lay.sites:
        ex, ey = x + span * math.cos(az), y + span * math.sin(az)
        ax.plot((x, ex), (y, ey), color=BLUE, lw=1.0, ls=(0, (4, 3)), zorder=3)
        if ex >= lay.xmin:
            ax.plot(ex, ey, "o", ms=3.5, color=BLUE, zorder=3)
    _sites(ax, lay.sites)
    ax.set_xlim(lay.xmin, lay.xmax)
    ax.set_ylim(-6.0, lay.sites[:, 1].max() + 6.0)
    _style(ax, equal=False)
    ax.set_xlabel("x along the track [m]", color=INK, fontsize=9)
    ax.set_ylabel("y [m]", color=INK, fontsize=9)
    ax.set_title("hst-fr2-28ghz (TR 38.854 FR2 high-speed train): %d RRHs %.0f m apart, %.0f m from the track, "
                 "%.0f GHz, train at %.0f km/h,\ntrack of %.0f m with wrap-around (y axis stretched); dashed: the "
                 "SSB beam of each RRH, aimed at the track below the next RRH"
                 % (lay.n_sites, span, lay.sites[0, 1], sc.radio.carrier_ghz,
                    3.6 * sc.mobility.groups[0].v_min, lay.xmax - lay.xmin),
                 fontsize=9.5, color=INK, loc="left")


def main() -> None:
    fig = plt.figure(figsize=(11.0, 7.0))
    gs = fig.add_gridspec(2, 2, height_ratios=[4.2, 1.0], width_ratios=[1.0, 1.55])
    urban_macro(fig.add_subplot(gs[0, 0]))
    suburban(fig.add_subplot(gs[0, 1]))
    train(fig.add_subplot(gs[1, :]))
    handles = [plt.Line2D([], [], ls="", marker="^", ms=7, color=ORANGE, mec=INK, mew=0.6),
               Rectangle((0, 0), 1, 1, fc=BUILDING, ec="none"),
               Rectangle((0, 0), 1, 1, fc=AREA, ec=INK, lw=0.8, ls="--"),
               Rectangle((0, 0), 1, 1, fc=MUTED, ec="none")]
    fig.legend(handles, ["site", "building", "users' area", "track"], loc="lower center", ncol=4,
               frameon=False, fontsize=9)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(OUT, dpi=150, facecolor="#fcfcfb")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
