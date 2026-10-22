# SPDX-License-Identifier: MIT
"""The details of TS 38.331 / TS 38.133 corrected in 2.1.0 (protocol.rrc_detail: "3gpp"; "simple" = 2.0.0)."""
import numpy as np
import pytest

import handoverlab as hl
from handoverlab.engine.core import rlm_indications
from handoverlab.rules import DAPS, LTM
from helpers import run_synthetic
from test_rules_rc2 import _target_vanishes

P = hl.Scenario().protocol


def _counters(n310=1, n311=1):
    p = hl.Scenario().with_overrides({"protocol.n310": n310, "protocol.n311": n311}).protocol
    return p, np.zeros(1, dtype=bool), np.zeros(1, dtype=int), np.zeros(1, dtype=int)


def _ind(p, run, n_o, n_i, q, t=1.0):
    """One indication instant with filtered quality q (Qout 1.0, Qin 2.0 in linear units)."""
    qa = np.array([q])
    return bool(rlm_indications(p, qa, qa, 1.0, 2.0, run, n_o, n_i, np.ones(1, dtype=bool), t, np.zeros(1))[0])


def test_n310_counts_consecutive_out_of_sync_while_t310_is_stopped():
    p, run, n_o, n_i = _counters(n310=3, n311=2)
    assert [_ind(p, run, n_o, n_i, q) for q in (0.5, 0.5, 1.5, 0.5)] == [False, False, False, True]
    # 1.5 lies between Qout and Qin: no indication, the count goes on (TS 38.331 5.3.10.2 NOTE 2)
    assert run[0] and n_o[0] == 3
    p, run, n_o, n_i = _counters(n310=3, n311=2)
    [_ind(p, run, n_o, n_i, q) for q in (0.5, 0.5, 3.0, 0.5)]
    assert not run[0] and n_o[0] == 1                   # an in-sync indication resets N310 (clause 7.2)


def test_n311_counts_in_sync_only_while_t310_runs():
    p, run, n_o, n_i = _counters(n310=1, n311=2)
    _ind(p, run, n_o, n_i, 3.0)
    assert n_i[0] == 0                                  # T310 stopped: in-sync is not counted
    assert _ind(p, run, n_o, n_i, 0.5) and run[0]       # T310 starts
    _ind(p, run, n_o, n_i, 3.0)
    assert run[0] and n_i[0] == 1
    _ind(p, run, n_o, n_i, 0.5)
    assert run[0] and n_i[0] == 0                       # out-of-sync resets N311
    _ind(p, run, n_o, n_i, 3.0)
    _ind(p, run, n_o, n_i, 3.0)
    assert not run[0]                                   # N311 = 2 consecutive in-sync stop T310


def test_indication_interval_follows_the_ssb_period():
    from handoverlab.engine import Engine
    from helpers import synthetic_world
    from handoverlab.rules import A3
    for period, steps in ((0.02, 2), (0.005, 1), (0.04, 4)):
        e = Engine(synthetic_world(10, overrides={"protocol.ssb_period_s": period}), A3())
        assert e.ind_steps == steps                     # max(10 ms, T_SSB) / step (TS 38.133 8.1.6)
    e = Engine(synthetic_world(10, overrides={"protocol.rrc_detail": "simple"}), A3())
    assert e.ind_steps == 1 and not e.std


def test_daps_falls_back_unless_the_source_failed(ramp):
    """TS 38.331 5.3.5.8.3: at T304 expiry the UE returns to the source unless the source RLF was detected."""
    r, k_exec = _target_vanishes(ramp)
    over = {"protocol.t304_s": 2.0, "protocol.t310_s": 0.2}
    m, ev = run_synthetic(DAPS(off_db=3.0, ttt_s=0.0), r, overrides=over)
    assert ev[0]["cause"] == "daps_fallback" and m["n_failures"] == 0
    r2 = r.copy()
    r2[k_exec + 1:k_exec + 200, 0, 0] = -125.0          # the source breaks too: its T310 runs out while T304 runs
    m2, ev2 = run_synthetic(DAPS(off_db=3.0, ttt_s=0.0), r2, overrides=over)
    assert ev2[0]["cause"] == "execution_failure" and m2["n_failures"] >= 1
    m3, ev3 = run_synthetic(DAPS(off_db=3.0, ttt_s=0.0), r2, overrides=dict(over, **{"protocol.rrc_detail": "simple"}))
    assert ev3[0]["cause"] == "daps_fallback"           # 2.0.0: the source SINR at T304 expiry decided (recovered)


def test_ltm_keeps_its_candidates_across_a_cell_switch():
    """TS 38.331 5.3.5.18.6: the ltm-Config survives an LTM cell switch."""
    from handoverlab.engine import Engine
    from handoverlab.channel.source import Chunk
    from helpers import synthetic_world
    S = 600
    k = np.arange(S)
    r = np.empty((S, 1, 3))
    r[:, 0, 0] = np.where(k < 200, -70.0, -90.0)
    r[:, 0, 1] = np.where(k < 200, -72.0, -70.0)
    r[:, 0, 2] = -73.0
    sites = ((0.0, 0.0), (100.0, 0.0), (0.0, 100.0))
    req = {}
    for detail in ("3gpp", "simple"):
        eng = Engine(synthetic_world(S, sites=sites, overrides={"protocol.rrc_detail": detail}),
                     LTM(o_prep_db=-5.0, o_switch_db=3.0, ttt_switch_s=0.0), log_events="full")
        eng.advance(Chunk.from_rsrp(0, r, eng.mp))
        assert eng.serv[0] == 1
        t_sw = [x["t"] for x in eng.trace if x["event"] == "exec"][0]
        req[detail] = (eng.C["prep_req_all"], [x for x in eng.trace if x["event"] == "release"
                                                 and t_sw <= x["t"] <= t_sw + 0.05])
    assert req["3gpp"][1] == [] and req["simple"][1]        # 2.0.0 released the candidates at the switch
    assert req["3gpp"][0] < req["simple"][0]                 # ... and had to prepare the third cell again


def test_cho_executes_when_its_time_to_trigger_expires(ramp):
    """TS 38.331 5.3.5.13.4 words the CHO execution condition like the reporting condition of 5.5.4.1: since 2.1.0
    both act when the time-to-trigger expires, also between two measurement instants (2.0.0: CHO waited)."""
    from handoverlab.rules import CHO
    t = {}
    for detail in ("3gpp", "simple"):
        _, ev = run_synthetic(CHO(o_prep_db=-6.0, o_exec_db=3.0, ttt_exec_s=0.064), ramp,
                              overrides={"protocol.rrc_detail": detail})
        t[detail] = ev[0]["t_exec"]
    assert t["simple"] - t["3gpp"] == pytest.approx(0.01, abs=1e-6)   # 64 ms: step 70 ms instead of instant 80 ms


def test_daps_is_not_used_from_fr2_to_fr2_nor_for_ntn():
    """TS 38.300 V18.11.0: DAPS handover from FR2 to FR2 (9.2.3.2) and for NTN (16.14.3.2.1) is not supported."""
    sc = hl.builtin_scenario("urban-grid-28ghz-beams").with_overrides(
        {"mobility.users": 8, "run.duration_s": 10.0, "run.warmup_s": 1.0})
    rules = [{"rule": "a3", "name": "A3"}, {"rule": "daps", "name": "DAPS"}]
    a3, daps = hl.simulate(sc, rules, seeds=[1])
    assert daps.metrics["interruption_exec_s_pm"] == pytest.approx(a3.metrics["interruption_exec_s_pm"])
    old = hl.simulate(sc.with_overrides({"protocol.rrc_detail": "simple"}), rules, seeds=[1])[1]
    assert old.metrics["interruption_exec_s_pm"] < daps.metrics["interruption_exec_s_pm"]
    ntn = hl.builtin_scenario("ntn-leo600-2ghz").with_overrides({"mobility.users": 4, "run.duration_s": 3.0,
                                                                 "run.warmup_s": 0.5})
    with pytest.raises(ValueError, match="not supported for NTN"):
        hl.simulate(ntn, [{"rule": "daps"}], seeds=[1])


def test_cho_recovery_is_a_reconfiguration_with_sync():
    """TS 38.331 5.3.7.3: a recovery into a prepared cell after RLF applies the stored configuration with a
    reconfiguration with sync; if the cell cannot be joined before T304 expires the UE re-establishes (2.1.0)."""
    from handoverlab.engine import Engine
    from handoverlab.rules import CHO
    from helpers import synthetic_world
    for detail, joins in (("3gpp", False), ("simple", True)):
        eng = Engine(synthetic_world(10, overrides={"protocol.rrc_detail": detail}), CHO())
        eng.rec_t0[0] = 0.0 if detail == "3gpp" else np.inf
        eng.l3.value = np.array([[-70.0, -80.0]])
        ok = eng._recovery_joins(0, eng.qout * 0.1, 1.5)       # below Qout after T304 (1 s) has expired
        assert ok == joins
        if not joins:
            assert eng.re_cell[0] == 0 and eng.t_done[0] == pytest.approx(1.5 + eng.P.reest_s)


def test_energy_takes_the_transmit_power_of_each_layer():
    """Each cell's input power uses the transmit power of its own layer (2.1.0; 2.0.0: the base layer's)."""
    sc = hl.builtin_scenario("dense-urban-2layer").with_overrides({"mobility.users": 6, "run.duration_s": 4.0,
                                                                   "run.warmup_s": 1.0})
    m = hl.simulate(sc, [{"rule": "a3"}], seeds=[1])[0].metrics
    R = sc.radio
    p0 = R.energy_ntrx * R.energy_p0_w
    p_in = [p0 + R.energy_slope * 10.0 ** (dbm / 10.0) / 1000.0 * m["mean_load"] for dbm in (33.0, 44.0)]
    assert m["mean_load"] > 0 and p_in[0] < m["site_power_w"] < p_in[1]   # between micro (33 dBm) and macro (44)
    old = hl.simulate(sc.with_overrides({"protocol.rrc_detail": "simple"}), [{"rule": "a3"}], seeds=[1])[0].metrics
    assert old["site_power_w"] == pytest.approx(p0 + R.energy_slope * 10 ** 4.4 / 1000 * old["mean_load"])


def test_gap_pattern_must_suit_the_frequency_ranges():
    """TS 38.133 Table 9.1.2-3: with an FR1 frequency the per-UE gap ids are 0-11, 24, 25; FR2 only: 12-25."""
    from handoverlab.config import ConfigError
    sc = hl.builtin_scenario("dense-urban-2layer")                   # 4 GHz + 30 GHz, meas_periods ts38133
    for gp, ok in ((0, True), (11, True), (12, False), (23, False), (24, True)):
        over = {"protocol.gap_pattern": gp}
        if ok:
            sc.with_overrides(over)
        else:
            with pytest.raises(ConfigError, match="Table 9.1.2-3"):
                sc.with_overrides(over)
        sc.with_overrides(dict(over, **{"protocol.rrc_detail": "simple"}))      # 2.0.0 accepted every id
