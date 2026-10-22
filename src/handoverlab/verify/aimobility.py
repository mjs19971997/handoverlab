# SPDX-License-Identifier: MIT
"""RRM measurement prediction of the rule ``a3_pred`` (TR 38.744; since 2.4.0): part of ``verify --only learning``.

A short check of the mechanics on the ``smoke`` card; the evaluation against TR 38.744 itself (FR1 and FR2
set-ups, generalization, event prediction, handover failures) is in ``docs/guides/ai-mobility.md``.

Set-up and criteria, fixed in a plan before the first run of this check: ridge predictors trained on seeds
11 and 12 (observation window 8, lambda 1), tested on seed 21 (training and test seeds differ, TR 38.744
clause 5.1); A3 offset 2 dB, time-to-trigger 320 ms.

P1  ``a3_pred`` with ``act=False`` (case A and case B) and case B without skipping give the event log of A3;
P2  case A, prediction window 320 ms: the mean prediction error of ridge is below that of sample and hold;
P3  case B, MRRT 50 %: the same;
P4  the measurement reduction rate achieved after the warm-up is within 0.01 of 0.5.
"""
from __future__ import annotations

from ..rules.predict import PredA3, Recorder, collect
from ..scenarios import builtin_scenario
from ..simulate import run_world
from ..world import build_world

TRAIN, TEST = (11, 12), 21
OFF, TTT, PW = 2.0, 0.32, 0.32


def ai_mobility_checks(rep) -> None:
    rep.section("learning", "RRM measurement prediction, rule a3_pred (TR 38.744; smoke card, training seeds "
                            "%s, test seed %d)" % (", ".join(map(str, TRAIN)), TEST))
    sc = builtin_scenario("smoke")
    H = int(round(PW / sc.protocol.l1_period_s))
    da, db = collect(sc, TRAIN, [(8, 1, H), (8, 2, 1)])
    pa, pb = da.solve(1.0), db.solve(1.0)
    rec = Recorder()
    rules = [{"rule": "a3", "off_db": OFF, "ttt_s": TTT},
             PredA3(OFF, TTT, "A", "hold", pw_s=PW, act=False, record=rec),
             PredA3(OFF, TTT, "A", "ridge", pa, pw_s=PW, act=False, record=rec),
             PredA3(OFF, TTT, "B", "hold", skip=1, record=rec),
             PredA3(OFF, TTT, "B", "ridge", pb, skip=1, record=rec),
             PredA3(OFF, TTT, "B", "ridge", pb, skip=1, act=False, record=rec),
             PredA3(OFF, TTT, "B", "hold", skip=0, record=rec)]
    res = run_world(build_world(sc, TEST), rules)
    fp = [r.fingerprint for r in res]
    rep.check("P1: a3_pred with act=False (cases A and B) and case B without skipping = A3 (identical event log)",
              fp[0] == fp[1] == fp[2] == fp[5] == fp[6], "seed %d" % TEST)
    s = [r.stats() for r in rec.rules]
    rep.check("P2: case A, PW 320 ms: ridge error < sample and hold", s[1]["err_avg_db"] < s[0]["err_avg_db"],
              "%.3f dB against %.3f dB (mean over %d horizons; %d training samples)"
              % (s[1]["err_avg_db"], s[0]["err_avg_db"], H, pa.n_samples))
    rep.check("P3: case B, MRRT 50 %: ridge error < sample and hold", s[3]["err_avg_db"] < s[2]["err_avg_db"],
              "%.3f dB against %.3f dB" % (s[3]["err_avg_db"], s[2]["err_avg_db"]))
    m = [s[i]["mrrt"] for i in (2, 3, 4)]
    rep.check("P4: MRRT achieved within 0.01 of 0.5", all(abs(x - 0.5) <= 0.01 for x in m),
              ", ".join("%.3f" % x for x in m))
    rep.note("indirect A3 event prediction (PW 320 ms, max ETD 80 ms): F1 score",
             "sample and hold %.2f, ridge %.2f" % (s[0]["f1"], s[1]["f1"]))
