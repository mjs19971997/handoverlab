# SPDX-License-Identifier: MIT
"""Draw docs/images/radio-map.png: the radio map of a street-grid world, as written by export_map (1.12.0).

The best path gain over the sites in every street pixel of the card smoke (seed 1): path loss, LOS state from
the buildings and place-tied shadowing, without transmit power and antenna gains, the content of a
radio.map_file. A ray tracer's map has the same form.

Run from the repository root:  python tools/make_radiomap_figure.py
"""
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import handoverlab as hl  # noqa: E402
from handoverlab.world import build_world  # noqa: E402

OUT = os.path.join("docs", "images", "radio-map.png")
INK = "#0b0b0b"


def main() -> None:
    world = build_world(hl.builtin_scenario("smoke"), 1)
    rm, lay = world.radio_map, world.layout
    best = np.max(rm.gain[:rm.n_pix], axis=1)
    img = np.full(rm.idx.shape, np.nan, dtype=float)
    on = rm.idx < rm.n_pix
    img[on] = best[rm.idx[on]]
    ext = (rm.x0, rm.x0 + rm.nx * rm.res, rm.y0, rm.y0 + rm.ny * rm.res)
    fig, ax = plt.subplots(figsize=(8.0, 4.4))
    ax.set_facecolor("#d9d8d4")                               # buildings
    im = ax.imshow(img, origin="lower", extent=ext, cmap="viridis", vmin=np.nanpercentile(img, 2),
                   vmax=np.nanpercentile(img, 99.5), interpolation="nearest")
    ax.plot(lay.sites[:, 0], lay.sites[:, 1], "^", ms=6, color="#eb6834", mec=INK, mew=0.6)
    ax.set_xlim(lay.xmin, lay.xmax)
    ax.set_ylim(lay.ymin, lay.ymax)
    ax.set_aspect("equal")
    ax.set_xlabel("x [m]", color=INK)
    ax.set_ylabel("y [m]", color=INK)
    cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cb.set_label("best path gain [dB]", color=INK)
    ax.set_title("Radio map of the card smoke (seed 1): street pixels, sites as triangles, buildings grey",
                 fontsize=10, color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(OUT, dpi=150)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
