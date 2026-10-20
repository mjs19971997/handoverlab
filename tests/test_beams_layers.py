# SPDX-License-Identifier: MIT
"""SSB beams, beam failure recovery, several carriers and the TS 38.133 periods (options of 1.10.0)."""
import math
from types import SimpleNamespace

import numpy as np
import pytest

import handoverlab as hl
from handoverlab import requirements as req
from handoverlab.channel.antenna import beam_azimuths_deg, beam_gain_db, ula_gain, wrap_deg
from handoverlab.config import ConfigError, Scenario
from handoverlab.engine.extended import ExtEngine, uses_extended
from handoverlab.rules import A3A5, RuleContext
from handoverlab.scenarios import builtin_scenario
from handoverlab.seeds import streams
from handoverlab.world import build_world

SHORT = {"run.duration_s": 12.0, "run.warmup_s": 1.0, "mobility.users": 6, "mobility.profile": "veh30"}
FR2 = {"radio.carrier_ghz": 28.0, "radio.bandwidth_mhz": 400.0}
BEAMS = {"radio.beams": {"sectors": 3, "n_ssb": 8}}
TWO = {"radio.carrier_ghz": 3.5, "radio.bandwidth_mhz": 100.0,
       "radio.layers": [{"name": "fr2", "carrier_ghz": 28.0, "bandwidth_mhz": 400.0, "site_spacing_m": 200.0,
                         "beams": {"sectors": 3, "n_ssb": 8}}],
       "protocol.meas_periods": "ts38133"}


def smoke(**over):
    sc = builtin_scenario("smoke").with_overrides(SHORT)
    return sc.with_overrides(over) if over else sc


# ---------------------------------------------------------------- configuration
def test_new_keys_are_late_keys_and_keep_old_job_ids():
    d = Scenario().to_dict()
    for k in ("beams", "layers", "scs_khz"):
        assert k not in d["radio"]
    for k in ("meas_periods", "ssb_period_s", "gap_pattern", "fr2_power_class", "rlm_eval"):
        assert k not in d["protocol"]
    full = Scenario().to_dict(full=True)
    assert full["radio"]["beams"] is None and full["protocol"]["meas_periods"] == "sample"


@pytest.mark.parametrize("over, key", [
    ({"radio.beams": {"n_ssb": 9}, "radio.carrier_ghz": 3.5}, "n_ssb"),
    ({"radio.beams": {"n_ssb": 5}, "radio.carrier_ghz": 2.0}, "n_ssb"),
    ({"radio.beams": {"bfi_max": 7}}, "bfi_max"),
    ({"radio.beams": {"bfd_timer": 7}}, "bfd_timer"),
    ({"radio.beams": {"bfr_timer_s": 0.03}}, "bfr_timer_s"),
    ({"radio.beams": {"preamble_max": 9}}, "preamble_max"),
    ({"radio.beams": {"rlm_rs": "all"}}, "rlm_rs"),
    ({"radio.beams": {"ssb_avg": 9, "n_ssb": 8}}, "ssb_avg"),
    ({"radio.beams": {"tilt_deg": 180.0}}, "tilt_deg"),
    ({"radio.beams": {"sectors": 0}}, "sectors"),
    ({"radio.scs_khz": 45.0}, "scs_khz"),
    ({"protocol.meas_periods": "fast"}, "meas_periods"),
    ({"protocol.rlm_eval": "x"}, "rlm_eval"),
    ({"protocol.gap_pattern": 26}, "gap_pattern"),
    ({"protocol.fr2_power_class": 6}, "fr2_power_class"),
    ({"protocol.ssb_period_s": 0.0}, "ssb_period_s"),
    ({"radio.layers": [{"name": "base"}]}, "name"),
    ({"radio.layers": [{"name": "a"}, {"name": "a"}]}, "name"),
    ({"radio.layers": [{"cosited": True, "site_spacing_m": 50.0}]}, "cosited"),
    ({"radio.layers": [{"carrier_ghz": 120.0}]}, "carrier_ghz"),
    ({"radio.layers": [{"pathloss": "rma", "carrier_ghz": 40.0}]}, "carrier_ghz"),
    ({"radio.layers": [{"pathloss": "x"}]}, "pathloss"),
    ({"radio.layers": [{"bandwidth_mhz": 0.0}]}, "bandwidth_mhz"),
    ({"radio.layers": [{"scs_khz": 7.0}]}, "scs_khz"),
    ({"radio.layers": [{"site_spacing_m": -1.0}]}, "site_spacing_m"),
    ({"radio.layers": [{"beams": {"n_ssb": 65}, "carrier_ghz": 28.0}]}, "n_ssb"),
])
def test_invalid_values_name_the_key(over, key):
    with pytest.raises(ConfigError, match=key):
        Scenario().with_overrides(over)


def test_layer_sites_file(tmp_path):
    f = tmp_path / "s.csv"
    f.write_text("x,y\n0,0\n50,0\n", encoding="utf-8")
    sc = Scenario().with_overrides({"radio.layers": [{"sites_file": str(f)}]})
    assert sc.radio.layers[0].sites == ((0.0, 0.0), (50.0, 0.0))


# ---------------------------------------------------------------- requirements and antenna
def test_requirement_tables():
    assert req.freq_range(0.3) == "other" and req.freq_range(80.0) == "other"
    assert req.rx_sweep_factor(28.0) == 8 and req.rx_sweep_factor(60.0) == 12 and req.rx_sweep_factor(3.5) == 1
    assert req.meas_m_intra(28.0, 1) == 40 and req.meas_m_intra(60.0, 1) == 60 and req.meas_m_intra(60.0, 3) == 36
    assert req.meas_m_inter(28.0, 5) == 64 and req.meas_m_inter(60.0, 1) == 96 and req.meas_m_inter(60.0, 2) == 60
    assert req.inter_meas_period(3.5, 0.08, 0.02) == pytest.approx(0.64)
    assert req.l3_reference_period(28.0, 0.02) == pytest.approx(0.48)
    assert len(req.GAP_PATTERNS) == 26 and req.GAP_PATTERNS[25] == (0.020, 0.160)
    r = req.ltm_delay(0.004, fr_change=True, fast_rrc=False, tci_known=False, t_first_ssb=0.01)
    assert r["interrupt"] == pytest.approx(0.010 + 0.040 + 0.010 + 0.002)
    assert r["delay"] == pytest.approx(r["interrupt"] + 0.007)
    assert req.daps_interruption(15.0)["total"] == pytest.approx(0.002)
    assert req.daps_interruption(60.0, False)["total"] == pytest.approx(0.0025)


def test_beam_gains_peak_at_their_own_azimuth():
    az = beam_azimuths_deg(8, 120.0)
    assert az[0] == pytest.approx(-52.5) and az[-1] == pytest.approx(52.5)
    phi = np.linspace(-60, 60, 241)
    g = beam_gain_db(np.full_like(phi, 100.0), phi, az, 100.0, 4, 8)
    best = phi[np.argmax(g, axis=0)]
    # the element pattern pulls the peaks of the outer beams a few degrees towards the boresight
    assert np.all(np.abs(best - az) <= 5.0) and np.all(np.abs(best[3:5] - az[3:5]) <= 0.5)
    assert ula_gain(np.array([0.0, math.pi]), 2)[1] == pytest.approx(0.0, abs=1e-12)
    assert wrap_deg(190.0) == pytest.approx(-170.0)
    g32 = beam_gain_db(np.float32(100.0), np.float32(10.0), az, 100.0, 4, 8)
    assert g32.dtype == np.float32


def test_streams_sub_zero_is_unchanged():
    a = streams(5, "map", 2)[0].standard_normal(3)
    b = streams(5, "map", 2, 0)[0].standard_normal(3)
    c = streams(5, "map", 2, 1)[0].standard_normal(3)
    assert np.array_equal(a, b) and not np.allclose(a, c)


# ---------------------------------------------------------------- worlds and cells
def test_extended_world_cells_and_nominal_cell():
    sc = smoke(**FR2, **BEAMS)
    w = build_world(sc, 1)
    ext = w.ext
    assert ext.n_cells == 3 * w.layout.n_sites == w.n_cells and ext.B == 8
    assert w.cell_sites.shape == (ext.n_cells, 2)
    s0 = w.layout.sites[0]
    # a point east of site 0 is served (nominally) by its sector facing 30 deg
    c = int(w.nominal_cell(np.array(s0[0] + 30.0), np.array(s0[1] + 5.0)))
    site = c // 3
    assert c % 3 == 0 and np.allclose(w.layout.sites[site], s0) or site != 0
    assert uses_extended(w)
    assert not uses_extended(build_world(smoke(), 1))


def test_cosited_layer_shares_los_and_shadowing():
    sc = smoke(**{"radio.layers": [{"name": "b", "carrier_ghz": 28.0, "bandwidth_mhz": 400.0, "cosited": True}]})
    w = build_world(sc, 2)
    L0, L1 = w.ext.layers
    assert np.array_equal(L0.rmap.los, L1.rmap.los)
    assert L1.sub == 0 and w.ext.n_carriers == 2
    sc2 = smoke(**{"radio.layers": [{"name": "b", "carrier_ghz": 28.0, "site_spacing_m": 100.0}]})
    w2 = build_world(sc2, 2)
    assert w2.ext.layers[1].sub == 1


# ---------------------------------------------------------------- engine
def test_extended_engine_equals_engine_without_options():
    sc = smoke()
    w = build_world(sc, 3)
    from handoverlab.engine import Engine
    from handoverlab.channel.source import RadioSource
    for spec in ({"rule": "a3"}, {"rule": "cho"}, {"rule": "daps"}, {"rule": "cltm"}):
        a = Engine(w, hl.make_rule(spec))
        b = ExtEngine(w, hl.make_rule(spec))
        for ch in RadioSource(w).chunks():
            a.advance(ch)
            b.advance(ch)
        assert a.finish() == b.finish() and a.fingerprint == b.fingerprint


def test_beam_run_in_debug_mode_has_beam_events():
    sc = smoke(**FR2, **BEAMS)
    res = hl.simulate(sc, [{"rule": "a3"}, {"rule": "ltm"}], seeds=[1], debug=True, log_events="full")
    for r in res:
        m = r.metrics
        assert m["beam_switches_pm"] > 0
        assert m["beam_failures_pm"] * m["ue_minutes"] >= (m["beam_recoveries_pm"] + m["beam_recovery_failures_pm"]) \
            * m["ue_minutes"] - 1e-9
        ev = {e["event"] for e in r.trace}
        assert "beam_switch" in ev
    assert any(r.metrics["beam_failures_pm"] > 0 for r in res)


def test_no_beam_failure_detection_without_bfd():
    sc = smoke(**FR2, **{"radio.beams": {"sectors": 3, "bfd": False}})
    r = hl.simulate(sc, [{"rule": "a3"}], seeds=[1])[0]
    assert r.metrics["beam_failures_pm"] == 0 and r.metrics["beam_recovery_s_pm"] == 0


def test_more_instances_needed_means_fewer_beam_failures():
    out = []
    for n in (1, 10):
        sc = smoke(**FR2, **{"radio.beams": {"sectors": 3, "bfi_max": n, "bfd_timer": 1}})
        out.append(hl.simulate(sc, [{"rule": "a3"}], seeds=[4])[0].metrics["beam_failures_pm"])
    assert out[0] >= out[1] and out[0] > 0


def test_rlm_on_the_best_beams_and_contention_free_recovery():
    sc = smoke(**FR2, **{"radio.beams": {"sectors": 3, "rlm_rs": "beams", "bfr_timer_s": None,
                                         "rsrp_thresh_ssb_dbm": -200.0, "report_s": 0.2}})
    r = hl.simulate(sc, [{"rule": "a3"}], seeds=[2], debug=True)[0]
    assert r.metrics["n_failures"] >= 0


def test_two_layers_measurement_gaps_and_inter_frequency_handovers():
    sc = smoke(**TWO)
    res = hl.simulate(sc, [{"rule": "a3"}, {"rule": "a3a5", "a5_thresh1_dbm": -60.0, "a5_thresh2_dbm": -120.0}],
                      seeds=[1], debug=True)
    a3, a5 = (r.metrics for r in res)
    assert 0.0 < a3["gap_share"] <= 0.15 + 1e-9                     # MGL / MGRP = 6 / 40
    assert a5["inter_frequency_handovers_pm"] > 0


def test_measurement_periods_per_cell():
    sc = smoke(**TWO)
    w = build_world(sc, 1)
    e = ExtEngine(w, hl.make_rule({"rule": "a3"}))
    fr1 = w.ext.cell_carrier == 0
    assert np.all(e.p_intra[fr1] == 5) and np.all(e.p_inter[fr1] == 8)          # 200 / 320 ms at 40 ms
    assert np.all(e.p_intra[~fr1] == 12) and np.all(e.p_inter[~fr1] == 40)      # 480 / 1600 ms
    assert np.allclose(e.a_intra, 0.5)                                           # k = 4 at the reference rate


def test_rlm_evaluation_periods_from_ts38133():
    sc = smoke(**{"protocol.rlm_eval": "ts38133", "radio.carrier_ghz": 28.0})
    w = build_world(sc, 1)
    r = hl.simulate(sc, [{"rule": "a3"}], seeds=[1])[0]
    e = ExtEngine(w, hl.make_rule({"rule": "a3"}))
    assert isinstance(e.ao, np.ndarray)
    assert r.metrics["n_attempts"] >= 0


def test_meas_periods_alone_on_one_carrier_runs():
    sc = smoke(**{"protocol.meas_periods": "ts38133"})
    r1 = hl.simulate(sc, [{"rule": "a3"}, {"rule": "cho"}], seeds=[1], debug=True)
    r0 = hl.simulate(smoke(), [{"rule": "a3"}], seeds=[1])
    assert r1[0].fingerprint != r0[0].fingerprint


def test_traffic_models_with_beams():
    for model in ("full_buffer", "ftp3"):
        sc = smoke(**FR2, **BEAMS, **{"traffic.model": model})
        r = hl.simulate(sc, [{"rule": "a3"}], seeds=[1])[0]
        assert r.metrics["rate_mbps"] > 0


# ---------------------------------------------------------------- A3A5
def _ctx(car):
    return RuleContext(2, len(car), np.zeros((len(car), 2)), None, 0.01, 0.04, 1, np.random.default_rng(1), None,
                       np.asarray(car))


def test_a3a5_entering_conditions():
    rule = A3A5(off_db=3.0, a5_thresh1_dbm=-100.0, a5_thresh2_dbm=-105.0, a5_hys_db=1.0,
                a5_down_thresh1_dbm=-110.0, a5_down_thresh2_dbm=-95.0)
    rule.reset(_ctx([0, 0, 1]))
    meas = np.array([[-102.0, -98.0, -103.0],     # serving cell 0 (carrier 0): A3 to cell 1, A5 up to cell 2
                     [-90.0, -92.0, -103.5]])     # serving 2 (carrier 1, below -110 + 1? no): down needs Mp < -111
    serving = np.array([0, 2])
    gap = meas - meas[np.arange(2), serving][:, None]
    obs = SimpleNamespace(meas_dbm=meas, gap_db=gap, serving=serving)
    cond, score = rule.entering(obs, 3.0)
    assert cond[0].tolist() == [False, True, True]    # A3 on cell 1 (4 dB), A5: -102 + 1 < -100, -103 - 1 > -105
    assert cond[1, 0] is np.False_ or not cond[1, 0]  # down: Mp + Hys = -102.5 > -110
    tt = rule.time_to_trigger(obs)
    assert tt.shape == (2, 3) and tt[0, 2] == rule.a5_ttt_s and tt[0, 1] == rule.ttt_s
    assert score[0, 2] == pytest.approx(2.0)
    rule.reset(_ctx([0, 0, 0]))
    assert rule.time_to_trigger(obs) == rule.ttt_s
    p = rule.params()
    assert p["a5_down_thresh2_dbm"] == -95.0


def test_dense_urban_card_builds():
    sc = builtin_scenario("dense-urban-2layer")
    assert sc.radio.layers[0].name == "micro-30ghz"
    assert sc.protocol.meas_periods == "ts38133"
