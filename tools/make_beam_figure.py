# SPDX-License-Identifier: MIT
"""Draw docs/images/ssb-beams.png: the 8 SSB beams of one sector of the beam model (since 1.10.0).

Gain of every beam of a 4 x 8 panel (TR 38.901 element of Table 7.3-1, DFT weights, tilt 100 deg)
against the azimuth from the sector boresight, at the zenith angle of the electrical tilt, next to
the gain of the 1.x antenna abstraction (20 dB towards the user, 0.3 x that for interference).

Run from the repository root:  python tools/make_beam_figure.py
"""
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from handoverlab.channel.antenna import beam_azimuths_deg, beam_gain_db  # noqa: E402

OUT = os.path.join("docs", "images", "ssb-beams.png")
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE = "#2a78d6", "#eb6834"


def main() -> None:
    phi = np.linspace(-180.0, 180.0, 1441)
    az = beam_azimuths_deg(8, 120.0)
    g = beam_gain_db(np.full_like(phi, 100.0), phi, az, 100.0, 4, 8)
    mean = 10.0 * np.log10(np.mean(10.0 ** (g / 10.0), axis=1))
    fig, ax = plt.subplots(figsize=(8.0, 3.6))
    for b in range(8):
        ax.plot(phi, g[:, b], color=BLUE, lw=1.1, alpha=0.85, label="SSB beams (8)" if b == 0 else None)
    ax.plot(phi, mean, color=ORANGE, lw=2.0, label="mean of the beams (interference of a loaded cell)")
    ax.axhline(20.0, color=MUTED, lw=1.0, ls=(0, (4, 3)), label="1.x abstraction: 20 dB")
    ax.axhline(20.0 + 10 * np.log10(0.3), color=MUTED, lw=1.0, ls=":", label="1.x interference: 0.3 x 20 dB")
    ax.set_xlim(-180, 180)
    ax.set_ylim(-48, 30)
    ax.set_xticks(range(-180, 181, 60))
    ax.set_xlabel("azimuth from the sector boresight [deg]", color=INK)
    ax.set_ylabel("gain [dBi]", color=INK)
    ax.grid(color=GRID, lw=0.8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(frameon=False, fontsize=8, loc="lower center", ncol=2)
    ax.set_title("One sector: 4 x 8 panel, TR 38.901 element, DFT beams tilted to 100 deg", fontsize=10,
                 color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(OUT, dpi=150)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
