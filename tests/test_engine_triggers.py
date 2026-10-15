# SPDX-License-Identifier: MIT
"""A3, CHO and the failure model in the engine, on prescribed received powers.

One user, two cells, no measurement noise: cell 0 stays at -70 dBm while
cell 1 rises by 2 dB/s.  The expected trigger instants follow from the L3
filter applied to the same samples.
"""
import numpy as np
import pytest

from handoverlab.rules import A3, CHO
from helpers import run_synthetic

MDT = 0.04        # measurement period
PREP = 0.05       # preparation delay


def first_filtered_crossing(rsrp, threshold):
    """First measurement instant at which the L3-filtered gap (cell 1 - cell 0) exceeds ``threshold``."""
    a = 1.0 - 0.5 ** (MDT / 0.2)               # k = 4, rescaled from 200 ms to 40 ms
    f = None
    for k in range(0, rsrp.shape[0], 4):
        m = rsrp[k, 0]
        f = m.copy() if f is None else f + a * (m - f)
        if f[1] - f[0] > threshold:
            return k
    raise AssertionError("no crossing")


def test_a3_reports_after_ttt_and_executes_after_preparation(ramp):
    metrics, events = run_synthetic(A3(off_db=3.0, ttt_s=0.16), ramp)
    k = first_filtered_crossing(ramp, 3.0)
    assert metrics["n_handovers"] == 1 and metrics["n_failures"] == 0
    (ev,) = events
    assert ev["tgt"] == 1 and ev["src"] == 0 and ev["outcome"] == "useful"
    assert ev["t_attempt"] == pytest.approx(k * 0.01 + 0.16, abs=1e-6)
    assert ev["t_exec"] == pytest.approx(k * 0.01 + 0.16 + PREP, abs=1e-6)


def test_a3_larger_offset_triggers_later(ramp):
    _, ev3 = run_synthetic(A3(off_db=3.0, ttt_s=0.16), ramp)
    _, ev6 = run_synthetic(A3(off_db=6.0, ttt_s=0.16), ramp)
    assert ev6[0]["t_exec"] - ev3[0]["t_exec"] == pytest.approx(1.5, abs=0.05)   # 3 dB at 2 dB/s


def test_a3_no_trigger_below_offset(ramp):
    metrics, events = run_synthetic(A3(off_db=30.0, ttt_s=0.16), ramp)
    assert metrics["n_attempts"] == 0 and events == []


def test_cho_prepares_early_and_executes_on_condition(ramp):
    metrics, events = run_synthetic(CHO(o_prep_db=-2.0, o_exec_db=3.0, ttt_exec_s=0.08, n_max=4), ramp)
    k_exec = first_filtered_crossing(ramp, 3.0)
    assert metrics["n_preparations"] == 1
    assert metrics["n_used_preparations"] == 1 and metrics["n_unused_preparations"] == 0
    assert metrics["n_handovers"] == 1 and metrics["n_failures"] == 0
    (ev,) = events
    assert ev["tgt"] == 1 and ev["n_prepared"] == 1 and ev["o_exec"] == pytest.approx(3.0)
    # the UE executes on its own when the condition has held for ttt_exec: no report, no preparation delay
    assert ev["t_exec"] == pytest.approx(k_exec * 0.01 + 0.08, abs=1e-6)


def test_cho_executes_before_a3_with_equal_offset(ramp):
    _, ev_a3 = run_synthetic(A3(off_db=3.0, ttt_s=0.08), ramp)
    _, ev_cho = run_synthetic(CHO(o_prep_db=-2.0, o_exec_db=3.0, ttt_exec_s=0.08), ramp)
    assert ev_a3[0]["t_exec"] - ev_cho[0]["t_exec"] == pytest.approx(PREP, abs=1e-6)


def test_cho_no_execution_without_condition(ramp):
    metrics, _ = run_synthetic(CHO(o_prep_db=-2.0, o_exec_db=40.0, ttt_exec_s=0.08), ramp)
    assert metrics["n_preparations"] == 1 and metrics["n_handovers"] == 0
    assert metrics["open_preparations"] == 1


def test_cho_n_max_bounds():
    with pytest.raises(ValueError):
        CHO(n_max=9)                    # maxNrofCondCells-r16 = 8
    with pytest.raises(ValueError):
        CHO(n_max=0)


def test_radio_link_failure_without_handover():
    """Serving cell drops at 5 s; with no handover T310 (1 s) expires and the UE re-establishes in cell 1."""
    S = 1000
    r = np.empty((S, 1, 2))
    r[:, 0, 0] = np.where(np.arange(S) < 500, -70.0, -110.0)
    r[:, 0, 1] = -75.0
    metrics, events = run_synthetic(A3(off_db=60.0, ttt_s=0.16), r, bg_load=0.5)
    assert metrics["n_failures"] == 1 and metrics["n_fail_rlf_without_handover"] == 1
    assert metrics["n_attempts"] == 0
    (ev,) = events
    assert ev["kind"] == "rlf" and ev["tgt"] == 1
    assert 6.5 < ev["t_end"] < 7.2                  # smoothed SINR falls below Qout (~0.9 s), then T310 = 1 s
    assert metrics["interruption_fail_s_pm"] * metrics["ue_minutes"] == pytest.approx(1.0)


def test_command_lost_while_t310_runs():
    """A3 report sent just before the serving link degrades: the command arrives while T310 runs."""
    S = 1000
    k = np.arange(S)
    r = np.empty((S, 1, 2))
    r[:, 0, 0] = np.where(k < 300, -70.0, -110.0)
    r[:, 0, 1] = np.where(k < 300, -95.0, -75.0)
    metrics, events = run_synthetic(A3(off_db=3.0, ttt_s=0.0), r, bg_load=0.5,
                                    overrides={"protocol.prep_s": 1.5})
    assert metrics["n_fail_command_lost"] == 1
    assert metrics["n_too_late"] == 1
    assert events[0]["outcome"] == "too_late" and events[0]["cause"] == "command_lost"
