# SPDX-License-Identifier: MIT
"""Draw docs/images/ai-mobility.png: prediction error of the rule a3_pred against the horizon (since 2.4.0).

TR 38.744 case A (intra-frequency temporal prediction) on the card urban-macro-tr37885-4ghz, reduced so that
the figure is quick to rebuild: 40 vehicles, 60 s per seed (10 s warm-up), every vehicle at 30, 60 or 90 km/h.
For every speed a ridge predictor (observation window 8 samples, lambda 1) is trained on seeds 101 and 102 and
tested, together with sample and hold, on seeds 201 and 202 (training and test seeds differ, TR 38.744 clause
5.1).  The error is the mean absolute difference between the predicted and the ground-truth L3 RSRP of the
4 strongest cells, per horizon (clause 5.2.1.1), pooled over the test seeds.  A3 offset 2 dB, time-to-trigger
320 ms; the rules only record (``act=False``), so both predictors see the same runs.  The full evaluation is
in docs/guides/ai-mobility.md.

Run from the repository root:  python tools/make_ai_mobility_figure.py   (about ten minutes)
"""
import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from handoverlab.config import Scenario  # noqa: E402
from handoverlab.rules.predict import PredA3, Recorder, collect  # noqa: E402
from handoverlab.scenarios import merge, resolve  # noqa: E402
from handoverlab.simulate import run_world  # noqa: E402
from handoverlab.world import build_world  # noqa: E402

OUT = os.path.join("docs", "images", "ai-mobility.png")
CARD = "urban-macro-tr37885-4ghz"
SPEEDS_KMH = (30.0, 60.0, 90.0)
TRAIN, TEST = (101, 102), (201, 202)
USERS, DURATION_S, WARMUP_S = 40, 60.0, 10.0
PW_S, N_OW, LAM = 0.4, 8, 1.0
OFF, TTT = 2.0, 0.32
COL = {30.0: "#2a78d6", 60.0: "#eb6834", 90.0: "#1baf7a"}
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def scenario(v_kmh: float) -> Scenario:
    d = merge(resolve(CARD), {"mobility": {"users": USERS, "groups": [
        {"share": 1.0, "v_min": v_kmh / 3.6, "v_max": v_kmh / 3.6, "lateral_m": [0.0, 0.0],
         "lanes_m": [1.75, 5.25]}]}, "run": {"duration_s": DURATION_S, "warmup_s": WARMUP_S}})
    return Scenario.from_dict(d)


def evaluate(v_kmh: float):
    """Mean absolute error per horizon [dB] of sample and hold and ridge, pooled over the test seeds."""
    sc = scenario(v_kmh)
    dt = sc.protocol.l1_period_s
    H = int(round(PW_S / dt))
    data, = collect(sc, TRAIN, [(N_OW, 1, H)])
    ridge = data.solve(LAM)
    tot = {"hold": [np.zeros(H), np.zeros(H)], "ridge": [np.zeros(H), np.zeros(H)]}
    for seed in TEST:
        rec = Recorder()
        run_world(build_world(sc, seed), [PredA3(OFF, TTT, "A", "hold", pw_s=PW_S, act=False, record=rec),
                                          PredA3(OFF, TTT, "A", "ridge", ridge, pw_s=PW_S, act=False, record=rec)])
        for name, r in zip(("hold", "ridge"), rec.rules):
            s = r.stats()
            tot[name][0] += np.asarray(s["err_sum"])
            tot[name][1] += np.asarray(s["err_n"])
        print("  %.0f km/h, test seed %d done" % (v_kmh, seed), flush=True)
    h_ms = 1e3 * dt * np.arange(1, H + 1)
    return h_ms, {k: s / np.maximum(n, 1) for k, (s, n) in tot.items()}, int(ridge.n_samples)


def main() -> None:
    res = {}
    for v in SPEEDS_KMH:
        print("speed %.0f km/h" % v, flush=True)
        res[v] = evaluate(v)
    fig, ax = plt.subplots(figsize=(8.0, 4.2))
    for v in SPEEDS_KMH:
        h_ms, err, _ = res[v]
        ax.plot(h_ms, err["hold"], color=COL[v], lw=1.4, ls=(0, (4, 3)), marker="o", ms=3.0)
        ax.plot(h_ms, err["ridge"], color=COL[v], lw=2.0, marker="o", ms=3.5)
    ax.set_xlim(0.0, res[SPEEDS_KMH[0]][0][-1] + 20.0)
    ax.set_ylim(0.0, None)
    ax.grid(color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.set_xlabel("prediction horizon [ms]", color=INK)
    ax.set_ylabel("mean absolute error of L3 RSRP [dB]", color=INK)
    handles = [plt.Line2D([], [], color=COL[v], lw=6) for v in SPEEDS_KMH] + \
              [plt.Line2D([], [], color=INK, lw=2.0), plt.Line2D([], [], color=INK, lw=1.4, ls=(0, (4, 3)))]
    labels = ["%.0f km/h" % v for v in SPEEDS_KMH] + ["ridge predictor", "sample and hold"]
    ax.legend(handles, labels, frameon=False, fontsize=8, loc="upper left", ncol=1)
    ax.set_title("Prediction error of a3_pred, TR 38.744 case A, card %s\n"
                 "%d vehicles, %.0f s per seed; ridge trained on seeds %s, tested on seeds %s"
                 % (CARD, USERS, DURATION_S, ", ".join(map(str, TRAIN)), ", ".join(map(str, TEST))),
                 fontsize=10, color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(OUT, dpi=150, bbox_inches="tight")
    print("wrote", OUT)
    summary = {"%.0f km/h" % v: {k: [round(float(x), 3) for x in e] for k, e in res[v][1].items()}
               for v in SPEEDS_KMH}
    for v in SPEEDS_KMH:
        summary["%.0f km/h" % v]["ridge_training_samples"] = res[v][2]
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
