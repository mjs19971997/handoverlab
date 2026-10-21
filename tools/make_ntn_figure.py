# SPDX-License-Identifier: MIT
"""Draw docs/images/ntn-beams.png: the 19 beams of the LEO satellite of the card ntn-leo600-2ghz (since 2.0.0).

Left: the best normalised beam gain on the ground (TR 38.811 Bessel pattern, the 2 m aperture of TR 38.821
Table 6.1.1.1-1) with the beam centres, at the start and at the end of the run, so the sweep of the
earth-moving beams over the users' area shows. Right: the received power of the beams at one user standing
still, against time (path loss, antenna gain and EIRP only; no shadowing, clutter or scintillation).

Run from the repository root:  python tools/make_ntn_figure.py
"""
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import handoverlab as hl  # noqa: E402
from handoverlab.channel.ntn import NtnGeometry, fspl_db  # noqa: E402

OUT = os.path.join("docs", "images", "ntn-beams.png")
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE = "#2a78d6", "#eb6834"


def main() -> None:
    sc = hl.builtin_scenario("ntn-leo600-2ghz")
    geom = NtnGeometry(sc)
    T = sc.run.duration_s
    w, h = sc.layout.area_m
    half = 300e3                                       # the window shown; the outer beams of case 2 reach further east
    xs = np.linspace(-half, half, 241)
    X, Y = np.meshgrid(xs, xs)
    x, y = X.ravel(), Y.ravel()
    _, _, g = geom.link(x, y, np.zeros_like(x))
    best = g.max(axis=1).reshape(X.shape)

    fig, (ax, bx) = plt.subplots(1, 2, figsize=(10.0, 4.2), gridspec_kw={"width_ratios": [1.0, 1.25]})
    im = ax.pcolormesh(X / 1e3, Y / 1e3, best, cmap="Blues", vmin=-12.0, vmax=0.0, shading="auto")
    for t, col, lab in ((0.0, BLUE, "beam centres at t = 0"), (T, ORANGE, "at t = %.0f s" % T)):
        c = geom.beam_centres(t) / 1e3
        ax.plot(c[:, 0], c[:, 1], "o", ms=3.5, color=col, label=lab)
    ax.add_patch(plt.Rectangle((-w / 2e3, -h / 2e3), w / 1e3, h / 1e3, fill=False, ec=INK, lw=1.0, ls="--"))
    ax.set_xlim(-half / 1e3, half / 1e3)
    ax.set_ylim(-half / 1e3, half / 1e3)
    ax.set_aspect("equal")
    ax.set_xlabel("east [km]", color=INK)
    ax.set_ylabel("north [km]", color=INK)
    ax.legend(frameon=False, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=2)
    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
    cb.set_label("best beam gain [dB]", color=INK)
    ax.set_title("Beams on the ground, users' area dashed", fontsize=10, color=INK, loc="left")

    t = np.linspace(0.0, T, 601)
    z = np.zeros_like(t)
    _, rng, gb = geom.link(z, z, t)
    p = geom.eirp_dbm + gb - fspl_db(rng, sc.radio.carrier_ghz)[:, None]
    for b in range(p.shape[1]):
        bx.plot(t, p[:, b], color=BLUE, lw=1.0, alpha=0.8, label="each beam" if b == 0 else None)
    bx.plot(t, p.max(axis=1), color=ORANGE, lw=2.0, label="best beam")
    bx.set_xlim(0.0, T)
    bx.set_ylim(p.max() - 30.0, p.max() + 3.0)
    bx.set_xlabel("time [s]", color=INK)
    bx.set_ylabel("received power [dBm]", color=INK)
    bx.grid(color=GRID, lw=0.8)
    for s in ("top", "right"):
        bx.spines[s].set_visible(False)
    bx.legend(frameon=False, fontsize=8, loc="lower right")
    bx.set_title("A user standing at the area centre", fontsize=10, color=INK, loc="left")
    fig.suptitle("LEO at 600 km, S band, 2 m aperture (TR 38.811, TR 38.821)", fontsize=11, color=INK, x=0.01,
                 ha="left")
    fig.tight_layout()
    fig.savefig(OUT, dpi=150)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
