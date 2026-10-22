# SPDX-License-Identifier: MIT
"""UE receive beams: panels, receive-beam selection and sweeping (option of 2.4.0, radio.beams.ue_panels)."""
import math

import numpy as np
import pytest

import handoverlab as hl
from handoverlab import requirements as req
from handoverlab.channel.antenna import beam_azimuths_deg, ue_beam_gains_db, ue_element_gain_db
from handoverlab.channel.extended import NO_BEAM_DB, ExtendedSource
from handoverlab.config import ConfigError, Scenario
from handoverlab.scenarios import builtin_scenario
from handoverlab.world import build_world

SHORT = {"run.duration_s": 12.0, "run.warmup_s": 1.0, "mobility.users": 6, "mobility.profile": "veh30",
         "radio.carrier_ghz": 28.0, "radio.bandwidth_mhz": 400.0}
BS = {"sectors": 3, "n_ssb": 8}


def smoke(ue=None, **over):
    beams = dict(BS, **(ue or {}))
    sc = builtin_scenario("smoke").with_overrides(SHORT).with_overrides({"radio.beams": beams})
    return sc.with_overrides(over) if over else sc


# ---------------------------------------------------------------- configuration
def test_ue_keys_are_late_keys():
    d = smoke().to_dict()
    for k in ("ue_panels", "ue_panel", "ue_beams", "ue_beam_span_deg", "ue_tilt_deg", "ue_orientation", "ue_rx"):
        assert k not in d["radio"]["beams"]
    assert smoke({"ue_panels": 2}).to_dict()["radio"]["beams"]["ue_panels"] == 2


@pytest.mark.parametrize("ue, over, key", [
    ({"ue_panels": 3}, {}, "ue_panels"),
    ({"ue_panels": 4, "ue_panel": [4, 4]}, {}, "ue_panel"),
    ({"ue_panels": 2, "ue_panel": [0, 4]}, {}, "ue_panel"),
    ({"ue_panels": 2, "ue_beams": 0}, {}, "ue_beams"),
    ({"ue_panels": 2, "ue_beam_span_deg": 0.0}, {}, "ue_beam_span_deg"),
    ({"ue_panels": 2, "ue_tilt_deg": 180.0}, {}, "ue_tilt_deg"),
    ({"ue_panels": 2, "ue_orientation": "fixed"}, {}, "ue_orientation"),
    ({"ue_panels": 2, "ue_rx": "all"}, {}, "ue_rx"),
    ({"ue_panels": 2, "ue_rx": "sweep"}, {"protocol.meas_periods": "ts38133"}, "meas_periods"),
    ({"ue_panels": 2}, {"radio.layers": [{"name": "same", "cosited": True, "beams": BS}]}, "layers"),
])
def test_invalid_ue_values_name_the_key(ue, over, key):
    with pytest.raises(ConfigError, match=key):
        smoke(ue, **over)


def test_ue_beams_not_with_dual_connectivity():
    with pytest.raises(ConfigError, match="protocol.dc"):
        Scenario.from_dict({"base": "smoke", "radio": {"carrier_ghz": 3.5, "beams": dict(BS, ue_panels=2),
                                                       "layers": [{"name": "fr2", "carrier_ghz": 28.0}]},
                            "protocol": {"dc": {}}})


# ---------------------------------------------------------------- antenna (criteria B1-B3)
def test_ue_element_pattern_of_tr38802_table_a218():
    assert ue_element_gain_db(90.0, 0.0) == pytest.approx(5.0)            # G_E,max
    for th, ph in ((90.0, 45.0), (90.0, -45.0), (45.0, 0.0), (135.0, 0.0)):
        assert ue_element_gain_db(th, ph) == pytest.approx(2.0)          # 3 dB down at half the 90 deg width
    assert ue_element_gain_db(90.0, 180.0) == pytest.approx(-20.0)       # A_m = 25 dB
    assert ue_element_gain_db(0.0, 0.0) == pytest.approx(-7.0)           # 12 dB below at the zenith
    assert ue_element_gain_db(0.0, 120.0) == pytest.approx(-20.0)        # A_V + A_H floored at A_m


def test_ue_beam_peak_and_array_gain():
    q = beam_azimuths_deg(4, 120.0)
    for b, a in enumerate(q):                                             # array gain M N in the steered direction
        g = ue_beam_gains_db(np.array(90.0), np.array(a), 0.0, 1, 0.0, 2, 4, q, 90.0)[0, b]
        assert g - ue_element_gain_db(90.0, a) == pytest.approx(10 * math.log10(8), abs=1e-9)
    g0 = ue_beam_gains_db(np.array(90.0), np.array(0.0), 0.0, 1, 0.0, 2, 4, np.zeros(1), 90.0)
    assert float(g0[0, 0]) == pytest.approx(5.0 + 10 * math.log10(8), abs=0.01)


def test_two_opposite_panels_are_symmetric_and_four_cover_all_round():
    q = beam_azimuths_deg(4, 120.0)
    az = np.arange(0.0, 360.0, 1.0)
    best = {}
    for P, step in ((1, 0.0), (2, 180.0), (4, 90.0)):
        best[P] = ue_beam_gains_db(np.full_like(az, 85.0), az, 30.0, P, step, 2, 4, q, 90.0).reshape(360, -1).max(-1)
    assert np.abs(best[2] - np.roll(best[2], 180)).max() < 0.01
    assert best[1].min() < best[2].min() < best[4].min()
    assert best[4].max() <= 5.0 + 10 * math.log10(8) + 1e-9


# ---------------------------------------------------------------- measurements (criteria C1-C3)
def _static_world(sc, seed=1):
    w = build_world(sc, seed)
    w.x[:] = w.x[0]
    w.y[:] = w.y[0]
    return w


def test_best_receive_beam_adds_its_gain_to_every_ssb():
    off = smoke(**{"radio.l1_error_db": 0.0})
    on = smoke({"ue_panels": 2}, **{"radio.l1_error_db": 0.0})
    c0 = next(ExtendedSource(build_world(off, 1)).chunks())
    w1 = build_world(on, 1)
    c1 = next(ExtendedSource(w1).chunks())
    assert c0.rg is None and c1.rg.shape[-1] == 8
    have = c0.bl1 > NO_BEAM_DB
    gain = np.broadcast_to(c1.rgb[:, :, w1.ext.cell_site][..., None], c1.bl1.shape)
    assert np.abs((c1.bl1 - c0.bl1)[have] - gain[have]).max() < 0.01
    assert np.array_equal(c1.bl1 <= NO_BEAM_DB, ~have)


def test_sweep_reaches_the_best_beam_after_one_cycle():
    over = {"radio.l1_error_db": 0.0, "radio.time_var_db": 0.0}
    best = next(ExtendedSource(_static_world(smoke({"ue_panels": 2}, **over))).chunks())
    sw = next(ExtendedSource(_static_world(smoke({"ue_panels": 2, "ue_rx": "sweep"}, **over))).chunks())
    have = best.bl1 > NO_BEAM_DB
    assert np.all(sw.bl1[have] <= best.bl1[have] + 1e-9)
    assert np.abs(sw.bl1[3:][have[3:]] - best.bl1[3:][have[3:]]).max() < 1e-9     # Q = 4 beams per panel
    assert np.any(sw.bl1[:3][have[:3]] < best.bl1[:3][have[:3]] - 0.1)


def test_fr2_measurement_period_contains_the_sweep():
    # TS 38.133 Table 9.2.5.2-2: max(400 ms, ceil(Mmeas_period_w/o_gaps) x T_SMTC), Mmeas_period_w/o_gaps = 24
    assert req.intra_meas_period(28.0, 0.02) == pytest.approx(0.48)
    assert req.intra_meas_period(3.5, 0.02) == pytest.approx(0.2)


# ---------------------------------------------------------------- engine
def test_isotropic_ue_given_explicitly_changes_nothing():
    a = hl.simulate(smoke(), [{"rule": "a3"}, {"rule": "cho"}], seeds=[2])
    b = hl.simulate(smoke({"ue_panels": 0, "ue_rx": "sweep"}), [{"rule": "a3"}, {"rule": "cho"}], seeds=[2])
    for x, y in zip(a, b):
        assert x.fingerprint == y.fingerprint and x.metrics == y.metrics


@pytest.mark.parametrize("ue, over", [
    ({"ue_panels": 2}, {}),
    ({"ue_panels": 2, "ue_rx": "sweep"}, {}),
    ({"ue_panels": 4, "ue_panel": [2, 2], "ue_orientation": "heading"}, {}),
    ({"ue_panels": 1, "ue_beams": 2}, {"protocol.meas_periods": "ts38133", "protocol.rlm_eval": "ts38133"}),
])
def test_receive_beams_run_in_debug_mode(ue, over):
    res = hl.simulate(smoke(ue, **over), [{"rule": "a3"}, {"rule": "ltm"}], seeds=[1], debug=True,
                      log_events="full")
    assert all(r.metrics["handovers_pm"] > 0 for r in res)


def test_receive_beams_raise_the_serving_sinr():
    off = hl.simulate(smoke(), [{"rule": "a3"}], seeds=[1, 2])
    on = hl.simulate(smoke({"ue_panels": 2}), [{"rule": "a3"}], seeds=[1, 2])
    assert np.mean([r.metrics["sinr_db"] for r in on]) > np.mean([r.metrics["sinr_db"] for r in off]) + 3.0


def test_receive_beams_on_a_second_layer_only():
    sc = builtin_scenario("smoke").with_overrides(dict(SHORT, **{
        "radio.carrier_ghz": 3.5, "radio.bandwidth_mhz": 100.0,
        "radio.layers": [{"name": "fr2", "carrier_ghz": 28.0, "bandwidth_mhz": 400.0, "site_spacing_m": 200.0,
                          "beams": dict(BS, ue_panels=2)}]}))
    w = build_world(sc, 1)
    ch = next(ExtendedSource(w).chunks())
    base = w.ext.site_layer == 0
    assert np.all(ch.rg[:, :, base] == 0.0) and np.any(ch.rg[:, :, ~base] > 5.0)
    r = hl.simulate(sc, [{"rule": "a3"}], seeds=[1], debug=True)[0]
    assert r.metrics["handovers_pm"] >= 0
