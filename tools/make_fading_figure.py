# SPDX-License-Identifier: MIT
"""Draw docs/images/fading.png: the option radio.fast_fading (TR 38.901 TDL models, since 2.2.0).

The card ns3-urban-3.5ghz, reduced to 10 vehicles and 20 s, seed 1, is run three times: without fast fading,
with tdl-a and with tdl-c (delay spread 100 ns), each time with Event A3 (offset 3 dB, time-to-trigger 160 ms).
Left: the received power of one vehicle from one cell over 4 s, as the engine sees it (the mean fading gain over
the band of the hypothetical PDCCH); the path loss and shadowing are the same in the three runs.  Right: the
distribution of the SINR of radio-link monitoring over all connected vehicles and steps: the flat SINR without
fading, with fading the MIESM (QPSK) effective SINR over the PDCCH band, against Qout and Qin.

Run from the repository root:  python tools/make_fading_figure.py   (about one minute)
"""
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from handoverlab.channel.source import RadioSource  # noqa: E402
from handoverlab.config import Scenario  # noqa: E402
from handoverlab.engine.core import Engine  # noqa: E402
from handoverlab.engine.procedures import CONNECTED  # noqa: E402
from handoverlab.rules import make_rule  # noqa: E402
from handoverlab.scenarios import merge, resolve  # noqa: E402
from handoverlab.world import build_world  # noqa: E402

OUT = os.path.join("docs", "images", "fading.png")
CARD, SEED, USERS, DURATION_S = "ns3-urban-3.5ghz", 1, 10, 20.0
MODELS = (None, "tdl-a", "tdl-c")
LABEL = {None: "no fast fading", "tdl-a": "tdl-a, 100 ns", "tdl-c": "tdl-c, 100 ns"}
COL = {None: "#0b0b0b", "tdl-a": "#2a78d6", "tdl-c": "#eb6834"}
UE, T0, T1 = 0, 8.0, 12.0
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def scenario(model):
    d = merge(resolve(CARD), {"mobility": {"users": USERS}, "radio": {"fast_fading": model, "delay_spread_ns": 100.0},
                              "run": {"duration_s": DURATION_S, "warmup_s": 0.0}})
    return Scenario.from_dict(d)


def run(model):
    """Received power of user UE from every cell [dBm] per step, and the link-monitoring SINR of connected users."""
    sc = scenario(model)
    world = build_world(sc, SEED)
    eng = Engine(world, make_rule({"rule": "a3", "off_db": 3.0, "ttt_s": 0.16}))
    sl = []
    step = eng.proc.step

    def record(t):
        con = eng.state == CONNECTED
        sl.append(10.0 * np.log10(np.maximum(np.asarray(eng.sl_now)[con], 1e-30)))
        step(t)

    eng.proc.step = record
    rsrp = []
    for ch in RadioSource(world).chunks():
        rsrp.append(ch.rsrp[:, UE, :].copy())
        eng.advance(ch)
    eng.finish()
    return sc, np.concatenate(rsrp), np.concatenate(sl), float(world.speed[UE])


def main() -> None:
    res = {m: run(m) for m in MODELS}
    sc = res[None][0]
    dt = sc.run.duration_s / res[None][1].shape[0]
    k0, k1 = int(round(T0 / dt)), int(round(T1 / dt))
    cell = int(np.argmax(res[None][1][k0:k1].mean(axis=0)))
    t = np.arange(k0, k1) * dt

    fig, (ax, bx) = plt.subplots(1, 2, figsize=(10.0, 4.2), gridspec_kw={"width_ratios": [1.25, 1.0]})
    for m in MODELS[::-1]:
        ax.plot(t, res[m][1][k0:k1, cell], color=COL[m], lw=2.0 if m is None else 1.0, label=LABEL[m])
    ax.set_xlim(T0, T1)
    ax.set_xlabel("time [s]", color=INK)
    ax.set_ylabel("received power [dBm]", color=INK)
    ax.set_title("One vehicle at %.0f m/s, its strongest cell" % res[None][3], fontsize=10, color=INK, loc="left")
    h, lab = ax.get_legend_handles_labels()
    ax.legend(h[::-1], lab[::-1], frameon=False, fontsize=8, loc="lower left", ncol=3)

    qout, qin = sc.protocol.qout_db, sc.protocol.qin_db
    lo = -15.0
    for m in MODELS:
        x = np.sort(res[m][2])
        y = np.arange(1, x.size + 1) / x.size
        name = "no fading, flat" if m is None else m + ", MIESM"
        bx.plot(x, y, color=COL[m], lw=2.0 if m is None else 1.5,
                label="%s: 5th pct. %.1f dB" % (name, np.percentile(x, 5)))
    cap = float(np.max(res[MODELS[-1]][2]))
    for q, nm, ha in ((qout, "Qout ", "right"), (qin, " Qin", "left")):
        bx.axvline(q, color=MUTED, lw=1.0, ls=(0, (4, 3)))
        bx.text(q, 1.02, nm, color=MUTED, fontsize=8, ha=ha, va="bottom")
    bx.annotate("MIESM of QPSK\nsaturates at %.1f dB" % cap, xy=(cap, 0.84), xytext=(cap + 1.0, 0.75), color=MUTED,
                fontsize=8, ha="left", va="center", arrowprops=dict(arrowstyle="->", color=MUTED, lw=0.8))
    bx.set_xlim(lo, 35.0)
    bx.set_ylim(0.0, 1.0)
    bx.set_xlabel("SINR of radio-link monitoring [dB]", color=INK)
    bx.set_ylabel("share of connected UE steps", color=INK)
    bx.legend(fontsize=8, loc="upper left", bbox_to_anchor=(0.0, 0.93), facecolor="white", edgecolor="none",
              framealpha=1.0)
    bx.set_title("All vehicles, all steps", fontsize=10, color=INK, loc="left", pad=14)
    for a in (ax, bx):
        a.grid(color=GRID, lw=0.8)
        a.set_axisbelow(True)
        for s in ("top", "right"):
            a.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            a.spines[s].set_color(MUTED)
        a.tick_params(colors=MUTED, labelsize=9)
    fig.suptitle("Fast fading, card %s: %d vehicles, %.0f s, seed %d, steps of %.0f ms"
                 % (CARD, USERS, DURATION_S, SEED, 1e3 * dt), fontsize=11, color=INK, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(OUT, dpi=150)
    print("wrote", OUT)
    for m in MODELS:
        x = res[m][2]
        print(LABEL[m], "median %.2f dB, below Qout %.4f, p5 %.2f dB" % (np.median(x), np.mean(x < qout),
                                                                          np.percentile(x, 5)))


if __name__ == "__main__":
    main()
