# SPDX-License-Identifier: MIT
"""Draw docs/images/ue-beams.png: UE receive beams, radio.beams.ue_panels (since 2.4.0).

Left: the gains of the receive beams of a UE with two panels 180 degrees apart (TR 38.802 Config 1), 2 x 4
elements each and 4 DFT beams per panel over 120 degrees, at the horizon, from the model of the run
(handoverlab.channel.antenna.ue_beam_gains_db with the layer's own settings).  Right: the card
urban-grid-28ghz-beams, reduced to 10 users and 30 s (5 s warm-up), seed 1, rule A3 (offset 3 dB,
time-to-trigger 160 ms), with an isotropic UE and with two UE panels (ue_rx best or sweep, random bearing; best
with the panels along the heading): the mean serving SINR and the mobility failures per UE-minute.

Run from the repository root:  python tools/make_ue_beams_figure.py   (about three minutes)
"""
import copy
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from handoverlab.channel.antenna import ue_beam_gains_db  # noqa: E402
from handoverlab.config import Scenario  # noqa: E402
from handoverlab.scenarios import merge, resolve  # noqa: E402
from handoverlab.simulate import run_world  # noqa: E402
from handoverlab.world import build_world  # noqa: E402

OUT = os.path.join("docs", "images", "ue-beams.png")
CARD, SEED, USERS, DURATION_S, WARMUP_S = "urban-grid-28ghz-beams", 1, 10, 30.0, 5.0
CASES = [("isotropic\nUE", None), ("2 panels,\nbest", {"ue_panels": 2, "ue_rx": "best"}),
         ("2 panels,\nsweep", {"ue_panels": 2, "ue_rx": "sweep"}),
         ("2 panels, best,\nalong heading", {"ue_panels": 2, "ue_rx": "best", "ue_orientation": "heading"})]
BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def scenario(ue) -> Scenario:
    d = merge(resolve(CARD), {"mobility": {"users": USERS}, "run": {"duration_s": DURATION_S, "warmup_s": WARMUP_S}})
    if ue is not None:
        d = copy.deepcopy(d)
        d["radio"]["beams"] = dict(d["radio"]["beams"], **ue)
    return Scenario.from_dict(d)


def style(a):
    a.grid(color=GRID, lw=0.8, axis="y")
    a.set_axisbelow(True)
    for s in ("top", "right"):
        a.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        a.spines[s].set_color(MUTED)
    a.tick_params(colors=MUTED, labelsize=9)


def main() -> None:
    res = []
    layer = None
    for name, ue in CASES:
        world = build_world(scenario(ue), SEED)
        if ue is not None and layer is None:
            layer = world.ext.layers[0]
        r, = run_world(world, [{"rule": "a3", "off_db": 3.0, "ttt_s": 0.16}])
        res.append(r.metrics)
        print(name.replace("\n", " "), {k: round(r.metrics[k], 3) for k in ("sinr_db", "failures_pm", "handovers_pm",
                                                                           "beam_failures_pm")}, flush=True)

    b = layer.beams
    az = np.linspace(-180.0, 180.0, 721)
    g = ue_beam_gains_db(np.full_like(az, 90.0), az, 0.0, layer.ue_panels, layer.ue_step, b.ue_panel[0],
                         b.ue_panel[1], layer.ue_beam_az, b.ue_tilt_deg)            # (A, panels, Q)
    fig = plt.figure(figsize=(10.0, 4.4))
    ax = fig.add_subplot(1, 2, 1, projection="polar")
    lo = -15.0
    for p, col in zip(range(layer.ue_panels), (BLUE, ORANGE)):
        for q in range(layer.ue_q):
            ax.plot(np.radians(az), np.maximum(g[:, p, q], lo), color=col, lw=1.2,
                    label=("panel %d (broadside %.0f deg)" % (p + 1, p * layer.ue_step)) if q == 0 else None)
    ax.set_ylim(lo, np.ceil(g.max()) + 1.0)
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.set_rlabel_position(90)
    ax.set_rticks([-10.0, 0.0, 10.0])
    ax.grid(color=GRID, lw=0.8)
    ax.legend(frameon=False, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.06), ncol=2)
    ax.set_title("Receive beams at the horizon [dBi], peak %.1f dBi\n%d x %d elements, %d beams per panel"
                 % (g.max(), b.ue_panel[0], b.ue_panel[1], layer.ue_q), fontsize=10, color=INK, loc="left", pad=16)

    bx = fig.add_subplot(1, 2, 2)
    x = np.arange(len(CASES))
    w = 0.38
    s = [m["sinr_db"] for m in res]
    f = [m["failures_pm"] for m in res]
    b1 = bx.bar(x - w / 2, s, w, color=BLUE, label="mean serving SINR [dB]")
    tx = bx.twinx()
    b2 = tx.bar(x + w / 2, f, w, color=ORANGE, label="failures per UE-minute")
    for bars, a, fmt in ((b1, bx, "%.1f"), (b2, tx, "%.2f")):
        for bb in bars:
            a.text(bb.get_x() + bb.get_width() / 2, bb.get_height(), fmt % bb.get_height(), ha="center",
                   va="bottom", fontsize=8, color=INK)
    bx.set_ylim(0.0, 1.25 * max(s))
    tx.set_ylim(0.0, 1.25 * max(f))
    bx.set_ylabel("mean serving SINR [dB]", color=BLUE)
    tx.set_ylabel("failures per UE-minute", color=ORANGE)
    bx.set_xticks(x)
    bx.set_xticklabels([n for n, _ in CASES], fontsize=8)
    style(bx)
    tx.spines["top"].set_visible(False)
    tx.spines["right"].set_color(MUTED)
    tx.tick_params(colors=MUTED, labelsize=9)
    bx.set_title("A3 on %s, %d users, %.0f s, seed %d" % (CARD, USERS, DURATION_S, SEED), fontsize=10, color=INK,
                 loc="left")
    fig.suptitle("UE receive beams (radio.beams.ue_panels, TR 38.802 UE model 1)", fontsize=11, color=INK, x=0.01,
                 ha="left")
    fig.tight_layout()
    fig.savefig(OUT, dpi=150)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
