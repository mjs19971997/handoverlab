# SPDX-License-Identifier: MIT
"""High-speed train card (TR 38.854) and dual connectivity (TS 37.340), both since 2.3.0."""
import math

import numpy as np
import pytest

import handoverlab as hl
from handoverlab.channel.antenna import beam_gain_db, element_gain_db
from handoverlab.channel.extended import ExtendedSource
from handoverlab.config import ConfigError
from handoverlab.engine.dual import ACTIVE, IDLE, DcEngine
from handoverlab.engine.extended import ExtEngine
from handoverlab.rules import make_rule
from handoverlab.world import build_world

A3 = {"rule": "a3", "off_db": 3.0, "ttt_s": 0.08}


# ---------------------------------------------------------------------------------------------- antenna A_m
def test_am_default_gives_the_table_7_3_1_element_bit_for_bit():
    th = np.linspace(0.0, 180.0, 37)[:, None]
    ph = np.linspace(-180.0, 180.0, 73)[None, :]
    av = -np.minimum(12.0 * ((th - 90.0) / 65.0) ** 2, 30.0)        # the formula of 1.10.0 - 2.2.0
    ah = -np.minimum(12.0 * (ph / 65.0) ** 2, 30.0)
    old = 8.0 - np.minimum(-(av + ah), 30.0)
    assert np.array_equal(element_gain_db(th, ph), old)
    assert np.array_equal(element_gain_db(th, ph, 30.0), old)
    az = np.array([-20.0, 0.0, 20.0])
    assert np.array_equal(beam_gain_db(th, ph, az, 95.0, 4, 8), beam_gain_db(th, ph, az, 95.0, 4, 8, 30.0))


def test_am_lowers_the_back_lobe_only():
    assert float(element_gain_db(90.0, 180.0)) == pytest.approx(-22.0)
    assert float(element_gain_db(90.0, 180.0, 100.0)) == pytest.approx(8.0 - 12.0 * (180.0 / 65.0) ** 2)
    assert float(element_gain_db(90.0, 20.0, 100.0)) == float(element_gain_db(90.0, 20.0))


def test_new_keys_stay_out_of_the_scenario_dictionary_while_default():
    sc = hl.builtin_scenario("urban-grid-28ghz-beams")
    d = sc.to_dict()
    assert "am_db" not in d["radio"]["beams"] and "dc" not in d["protocol"]
    assert "am_db" in sc.with_overrides({"radio.beams.am_db": 40.0}).to_dict()["radio"]["beams"]
    with pytest.raises(ConfigError, match="am_db"):
        sc.with_overrides({"radio.beams.am_db": 0.0})


# ---------------------------------------------------------------------------------------------- HST card
def test_hst_card_geometry_and_boresight_gain():
    sc = hl.builtin_scenario("hst-fr2-28ghz")
    w = build_world(sc, 1)
    sites = w.layout.sites
    assert len(sites) == 12 and np.allclose(np.diff(sites[:, 0]), 700.0) and np.allclose(sites[:, 1], 10.0)
    assert w.layout.period_x == pytest.approx(8400.0)
    assert np.allclose(np.abs(w.layout.ys), 0.01)                 # both directions on one track, Dmin 10 m
    assert np.allclose(np.hypot(np.diff(w.x[:, 0]), 0)[:10] / sc.protocol.step_s, 350.0 / 3.6, rtol=1e-3)
    # the beam points at the track where the next RRH (to the west) stands: full array gain 8 dBi + 64 elements
    ext = w.ext
    s = 6
    g = ext.gain_db(np.array([sites[s, 0] - 700.0]), np.array([0.0]), np.array([s]), np.array([0]))
    assert float(g[0]) == pytest.approx(8.0 + 10.0 * math.log10(64.0), abs=0.05)
    # behind the RRH the element's front-to-back ratio of 30 dB applies
    gb = ext.gain_db(np.array([sites[s, 0] + 700.0]), np.array([0.0]), np.array([s]), np.array([0]))
    assert float(g[0] - gb[0]) == pytest.approx(30.0, abs=0.5)


def test_hst_card_short_run():
    sc = hl.builtin_scenario("hst-fr2-28ghz").with_overrides({"run.duration_s": 20.0, "run.warmup_s": 2.0})
    (r,) = hl.simulate(sc, [A3], seeds=[3])
    assert r.metrics["n_handovers"] >= 2                        # 18 s at 350 km/h: 2.5 RRH spacings
    assert r.metrics["sinr_db"] > 20.0                           # no inter-cell interference


# ---------------------------------------------------------------------------------------------- dual connectivity
def dc_scenario(**dc):
    """One FR1 macro site (MCG) and four 28 GHz small cells along a road (SCG), one car at 20 m/s."""
    d = dict(dc)
    d.setdefault("scg_layer", "fr2")
    return hl.Scenario.from_dict({
        "name": "dc-test",
        "layout": {"kind": "highway", "lanes": 1, "road_length_m": 1600.0, "sites": [[0.0, 80.0]]},
        "radio": {"carrier_ghz": 3.5, "bandwidth_mhz": 20.0, "tx_power_dbm": 46.0, "bs_height_m": 25.0,
                  "pathloss": "uma", "bs_gain_db": 15.0, "time_var_db": 0.0, "map_res_m": 4.0,
                  "layers": [{"name": "fr2", "carrier_ghz": 28.0, "bandwidth_mhz": 100.0, "scs_khz": 120.0,
                              "tx_power_dbm": 30.0, "bs_height_m": 10.0, "pathloss": "umi_street_canyon",
                              "bs_gain_db": 20.0, "noise_figure_db": 10.0,
                              "sites": [[-600.0, 15.0], [-200.0, 15.0], [200.0, 15.0], [600.0, 15.0]]}]},
        "protocol": {"dc": d},
        "mobility": {"users": 2, "groups": [{"share": 1.0, "v_min": 20.0, "v_max": 20.0, "lateral_m": [0.0, 0.0]}]},
        "run": {"duration_s": 40.0, "warmup_s": 0.0}})


def test_dc_configuration_checks():
    with pytest.raises(ConfigError, match="needs a second carrier"):
        hl.Scenario.from_dict({"protocol": {"dc": {}}})
    with pytest.raises(ConfigError, match="scg_layer: must name"):
        dc_scenario(scg_layer="nope")
    with pytest.raises(ConfigError, match="on_mcg_ho"):
        dc_scenario(on_mcg_ho="maybe")
    with pytest.raises(ConfigError, match="release_thresh_dbm"):
        dc_scenario(add_thresh_dbm=-120.0, release_thresh_dbm=-110.0)
    d = dc_scenario().to_dict(full=True)
    d["radio"]["layers"][0]["carrier_ghz"] = 3.5
    with pytest.raises(ConfigError, match="carrier of its own"):
        hl.Scenario.from_dict(d)
    assert dc_scenario().protocol.dc.prep_s is None


def _trace(sc, seed=1, rule=A3):
    (r,) = hl.simulate(sc, [rule], seeds=[seed], log_events="full")
    return r, r.trace


def test_dc_addition_change_and_timing():
    sc = dc_scenario()
    r, tr = _trace(sc)
    m = r.metrics
    assert m["sn_additions_pm"] > 0 and m["pscell_changes_pm"] > 0 and 0.0 < m["scg_time_share"] <= 1.0
    assert m["scg_rate_mbps"] > 0
    D, P = sc.protocol.dc, sc.protocol
    req = [e for e in tr if e["event"] == "sn_add_request"]
    add = [e for e in tr if e["event"] == "sn_add"]
    assert req and add
    for e in req:                                     # A4 held for the time-to-trigger (value: entry time)
        assert D.add_ttt_s - 1e-9 <= e["t"] - e["value"] <= D.add_ttt_s + P.l1_period_s + 1e-9
    for e in add:                                     # preparation and random access, joined at the first try
        q = max(x["t"] for x in req if x["ue"] == e["ue"] and x["t"] <= e["t"])
        assert P.prep_s + P.exec_s - 1e-9 <= e["t"] - q <= P.prep_s + P.exec_s + P.step_s + 1e-9
    # no MCG handover into an SCG cell, no inter-frequency handover
    scg = set(range(1, 5))
    assert not any(e["event"] in ("attach", "exec") and e["cell"] in scg for e in tr)
    assert m["inter_frequency_handovers_pm"] == 0


def test_dc_bookkeeping():
    sc = dc_scenario(release_thresh_dbm=-112.0, add_thresh_dbm=-105.0)
    world = build_world(sc, 2)
    eng = DcEngine(world, make_rule(A3))
    for ch in ExtendedSource(world).chunks():
        eng.advance(ch)
    C, dc = eng.C, eng.dc
    open_add = int(np.count_nonzero(np.isin(dc.st, (1, 2))))
    open_chg = int(np.count_nonzero(np.isin(dc.st, (4, 5))))
    assert C["dc_add"] == C["dc_add_ok"] + C["dc_add_fail"] + C["dc_add_drop"] + open_add
    assert C["dc_chg"] == C["dc_chg_ok"] + C["dc_chg_fail"] + C["dc_chg_drop"] + open_chg
    assert C["dc_add_ok"] >= 1
    m = eng.finish()
    assert m["scg_time_share"] <= 1.0
    assert m["scg_failures_pm"] == pytest.approx(m["scg_rlf_pm"] + m["sn_addition_failures_pm"]
                                                 + m["pscell_change_failures_pm"])


def test_dc_mcg_failure_releases_the_scg():
    sc = dc_scenario()
    world = build_world(sc, 1)
    eng = DcEngine(world, make_rule(A3))
    src = ExtendedSource(world).chunks()
    while True:
        ch = next(src)
        eng.advance(ch)
        if (eng.dc.st == ACTIVE).any():
            break
    u = int(np.nonzero(eng.dc.st == ACTIVE)[0][0])
    t = (ch.k0 + ch.n) * sc.protocol.step_s
    n = eng.C["dc_rel_mcg"]
    eng.fail(u, t, "rlf")
    assert eng.dc.st[u] == IDLE and eng.dc.ps[u] == -1 and eng.C["dc_rel_mcg"] == n + 1


def test_dc_never_changes_the_mcg():
    """The MCG event log is the same whether an SN is ever added or not, and with the SN released at handover."""
    base = dc_scenario()
    for seed in (1, 2):
        (a,) = hl.simulate(base, [A3], seeds=[seed])
        (b,) = hl.simulate(dc_scenario(add_thresh_dbm=1000.0), [A3], seeds=[seed])
        (c,) = hl.simulate(dc_scenario(on_mcg_ho="release"), [A3], seeds=[seed])
        assert a.metrics["sn_additions_pm"] > 0 and b.metrics["sn_additions_pm"] == 0
        assert a.fingerprint == b.fingerprint == c.fingerprint
        assert a.metrics["handovers_pm"] == b.metrics["handovers_pm"]


def test_without_dc_the_extended_engine_runs():
    sc = dc_scenario()
    d = sc.to_dict(full=True)
    d["protocol"]["dc"] = None
    plain = hl.Scenario.from_dict(d)
    world = build_world(plain, 1)
    from handoverlab.simulate import run_world
    (r,) = run_world(world, [A3])
    assert r.metrics["sn_additions_pm"] == 0 and r.metrics["scg_time_share"] == 0
    assert type(ExtEngine(world, make_rule(A3))).dc is None
