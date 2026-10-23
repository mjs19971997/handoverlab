# SPDX-License-Identifier: MIT
"""Draw docs/images/scheduler.png: the slot scheduler protocol.scheduler (since 2.2.0) and its compiled loop.

The card ns3-urban-3.5ghz with full-buffer traffic, reduced to 10 vehicles and 20 s, seed 1, Event A3 (offset
3 dB, time-to-trigger 160 ms), is run with round robin (rr) and with proportional fair (pf); HARQ with at most
4 transmissions, round trip 8 slots, implementation loss 1 dB.  Left: the delivered rate of every vehicle against
its mean SINR over the run (the SINR the scheduler is given, while connected).  Right: the wall time of the same
runs with the NumPy slot loop and with run.backend: numba (after one short run per scheduler that compiles
the kernel); the event-log fingerprints of the two backends are compared and printed.

Run from the repository root:  python tools/make_scheduler_figure.py   (about five minutes; needs numba)
"""
import os
import sys
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from handoverlab.channel.source import RadioSource  # noqa: E402
from handoverlab.config import Scenario  # noqa: E402
from handoverlab.engine.core import Engine  # noqa: E402
from handoverlab.rules import make_rule  # noqa: E402
from handoverlab.scenarios import merge, resolve  # noqa: E402
from handoverlab.world import build_world  # noqa: E402

OUT = os.path.join("docs", "images", "scheduler.png")
CARD, SEED, USERS, DURATION_S = "ns3-urban-3.5ghz", 1, 10, 20.0
KINDS = ("rr", "pf")
LABEL = {"rr": "round robin (rr)", "pf": "proportional fair (pf)"}
COL = {"rr": "#2a78d6", "pf": "#eb6834"}
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def scenario(kind, backend, duration_s=DURATION_S):
    d = merge(resolve(CARD), {"mobility": {"users": USERS}, "traffic": {"model": "full_buffer"},
                              "protocol": {"scheduler": kind, "harq_max_tx": 4, "harq_rtt_slots": 8,
                                           "l2s_loss_db": 1.0},
                              "run": {"duration_s": duration_s, "warmup_s": 0.0, "backend": backend}})
    return Scenario.from_dict(d)


def run(kind, backend, duration_s=DURATION_S):
    """Delivered bits and mean SINR [dB] per user, wall time [s], event-log fingerprint, TB statistics."""
    world = build_world(scenario(kind, backend, duration_s), SEED)
    eng = Engine(world, make_rule({"rule": "a3", "off_db": 3.0, "ttt_s": 0.16}))
    U = world.n_users
    bits, s_sum, s_n = np.zeros(U), np.zeros(U), np.zeros(U)
    serve = eng.sched.serve

    def record(sinr, demand, con, serv, free, first_slot=None):
        got, used = serve(sinr, demand, con, serv, free, first_slot)
        bits[:] += got
        s_sum[con] += 10.0 * np.log10(np.maximum(sinr[con], 1e-30))
        s_n[con] += 1
        return got, used

    eng.sched.serve = record
    t0 = time.perf_counter()
    for ch in RadioSource(world).chunks():
        eng.advance(ch)
    m = eng.finish()
    wall = time.perf_counter() - t0
    st = dict(eng.sched.stats)
    return dict(bits=bits, sinr=s_sum / np.maximum(s_n, 1), wall=wall, fp=eng.fingerprint, m=m, st=st,
                slots=eng.sched.n_slots, prb=eng.sched.n_prb, slot_ms=1e3 * eng.sched.slot_s)


def main() -> None:
    for kind in KINDS:
        run(kind, "numba", 1.0)                                # compiles the kernel before the timed runs
    res = {}
    for kind in KINDS:
        for be in ("numpy", "numba"):
            res[kind, be] = run(kind, be)
            print("%s %s: %.1f s, fingerprint %s" % (kind, be, res[kind, be]["wall"], res[kind, be]["fp"][:16]),
                  flush=True)
    same = all(res[k, "numpy"]["fp"] == res[k, "numba"]["fp"] for k in KINDS)

    fig, (ax, bx) = plt.subplots(1, 2, figsize=(10.0, 4.2), gridspec_kw={"width_ratios": [1.35, 1.0]})
    for kind in KINDS:
        r = res[kind, "numpy"]
        rate = r["bits"] / DURATION_S / 1e6
        st = r["st"]
        ax.scatter(r["sinr"], rate, s=28, color=COL[kind], alpha=0.9, zorder=3,
                   label="%s: total %.1f Mbit/s, %.0f retransmissions per 100 new TBs"
                   % (LABEL[kind], rate.sum(), 100.0 * st["retx"] / max(st["tb"], 1)))
    ax.set_xlabel("mean SINR of the vehicle while connected [dB]", color=INK)
    ax.set_ylabel("delivered rate [Mbit/s]", color=INK)
    ax.set_ylim(0.0, 1.3 * max(res[k, "numpy"]["bits"].max() for k in KINDS) / DURATION_S / 1e6)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    r0 = res["rr", "numpy"]
    ax.set_title("Every vehicle, %d PRBs, slots of %.1f ms" % (r0["prb"], r0["slot_ms"]), fontsize=10, color=INK,
                 loc="left")

    x = np.arange(len(KINDS))
    w = 0.36
    for j, (be, col) in enumerate((("numpy", MUTED), ("numba", INK))):
        v = [res[k, be]["wall"] for k in KINDS]
        bars = bx.bar(x + (j - 0.5) * w, v, w, color=col, label="run.backend: " + be)
        for b, val in zip(bars, v):
            bx.text(b.get_x() + b.get_width() / 2, val, "%.1f s" % val, ha="center", va="bottom", fontsize=8,
                    color=INK)
    bx.set_xticks(x)
    bx.set_xticklabels([LABEL[k] for k in KINDS], fontsize=9)
    bx.set_ylabel("wall time of the run [s]", color=INK)
    bx.legend(frameon=False, fontsize=8, loc="upper right")
    bx.set_title("Same runs, %s results" % ("bit-identical" if same else "DIFFERENT"), fontsize=10, color=INK,
                 loc="left")
    bx.set_ylim(0.0, 1.4 * max(r["wall"] for r in res.values()))
    for a in (ax, bx):
        a.grid(color=GRID, lw=0.8, axis="y" if a is bx else "both")
        a.set_axisbelow(True)
        for s in ("top", "right"):
            a.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            a.spines[s].set_color(MUTED)
        a.tick_params(colors=MUTED, labelsize=9)
    fig.suptitle("Slot scheduler with MCS and HARQ, card %s, full buffer: %d vehicles, %.0f s, seed %d"
                 % (CARD, USERS, DURATION_S, SEED), fontsize=11, color=INK, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(OUT, dpi=150)
    print("wrote", OUT)
    print("identical fingerprints:", same)
    for kind in KINDS:
        r = res[kind, "numpy"]
        rate = r["bits"] / DURATION_S / 1e6
        jain = rate.sum() ** 2 / (len(rate) * (rate ** 2).sum())
        print(kind, "rates", np.round(rate, 2).tolist(), "jain %.3f" % jain, "stats", r["st"], "rate_mbps",
              round(r["m"]["rate_mbps"], 3))


if __name__ == "__main__":
    main()
