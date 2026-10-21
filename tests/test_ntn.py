# SPDX-License-Identifier: MIT
"""The NTN model of 2.0.0: TR 38.811 / TR 38.821 geometry and channel, the card, the rule cho_d2."""
import math
from types import SimpleNamespace

import numpy as np
import pytest

import handoverlab as hl
from handoverlab.channel import ntn
from handoverlab.config import ConfigError, Scenario
from handoverlab.rules.builtin import CHOD2
from handoverlab.scenarios import layout_svg
from handoverlab.testing import check_rule
from handoverlab.verify import Report, run_verify
from handoverlab.verify.ntn import CASES, link_budget
from handoverlab.world import build_world

CARD = "ntn-leo600-2ghz"
SHORT = {"mobility.users": 8, "run.duration_s": 6.0, "run.warmup_s": 1.0}


def test_slant_range_and_free_space_loss():
    assert ntn.slant_range(90.0, 600e3) == pytest.approx(600e3)                     # nadir: the altitude
    d = float(ntn.slant_range(30.0, 600e3))
    assert d == pytest.approx(1075.1e3, abs=0.5e3)
    assert float(ntn.fspl_db(d, 2.0)) == pytest.approx(159.1, abs=0.05)             # TR 38.821 Table 6.1.3.3-1
    assert float(ntn.fspl_db(1000.0, 1.0)) == pytest.approx(32.45 + 60.0)            # Eq. 6.6-2
    assert float(ntn.slant_range(10.0, 600e3)) > d > float(ntn.slant_range(60.0, 600e3))


def test_antenna_pattern_and_beamwidth():
    ka = ntn.ka_from_aperture(2.0, 2.0)
    assert ka == pytest.approx(math.pi * 2.0 * 2e9 / 299792458.0)
    hp = ntn.hpbw_deg(ka)
    assert hp == pytest.approx(4.4127, rel=0.002)                                   # TR 38.821 Table 6.1.1.1-1
    g = ntn.antenna_gain(np.radians([0.0, hp / 2.0, -hp / 2.0]), ka)
    assert g == pytest.approx([1.0, 0.5, 0.5], abs=1e-9)
    first_null = math.asin(3.8317 / ka)                                             # first zero of J1
    assert float(ntn.antenna_gain(np.array([first_null]), ka)[0]) < 1e-6


def test_orbit_reference_elevations_and_beam_grid():
    assert ntn.orbital_speed(600e3) == pytest.approx(7560.0, rel=0.005)             # TR 38.821 Table 7.1-1
    assert list(ntn.nearest_reference(np.array([0.0, 10.0, 14.9, 15.1, 47.0, 90.0]))) == [0, 0, 0, 1, 4, 8]
    uv = ntn.hex_uv(19, 0.1)
    assert uv.shape == (19, 2) and np.allclose(uv[0], 0.0)
    d = np.hypot(uv[:, None, 0] - uv[None, :, 0], uv[:, None, 1] - uv[None, :, 1])
    d[np.arange(19), np.arange(19)] = np.inf
    assert np.allclose(d.min(axis=1), 0.1)                          # every beam has a neighbour at the spacing
    assert np.isclose(np.hypot(uv[:, 0], uv[:, 1]).max(), 0.2)                      # two rings
    pts = np.array([[0.0, 0.0], [30e3, -20e3], [-250e3, 120e3]])
    assert np.allclose(ntn.to_local(ntn.to_ecef(pts[:, 0], pts[:, 1])), pts, atol=1e-6)


def test_geometry_of_the_card():
    sc = hl.builtin_scenario(CARD)
    geom = ntn.NtnGeometry(sc)
    assert geom.n_beams == 19 and geom.v == pytest.approx(7562.0, abs=1.0)
    c = geom.beam_centres(geom.t_mid)
    assert np.hypot(*c[0]) < 1.0                                    # the central beam points at the area centre
    elev, rng, g = geom.link(np.zeros(1), np.zeros(1), np.array([geom.t_mid]))
    assert elev[0] == pytest.approx(30.0, abs=1e-6)                                 # TR 38.821 target elevation
    assert rng[0] == pytest.approx(float(ntn.slant_range(30.0, 600e3)), rel=1e-6)
    assert g[0, 0] == pytest.approx(0.0, abs=1e-6) and np.all(g[0, 1:] < -3.0)
    shift = geom.beam_centres(geom.t_mid + 1.0) - c
    assert np.all(shift[:, 1] > 5e3) and np.all(np.abs(shift[:, 0]) < shift[:, 1])  # beams sweep north at km/s
    assert geom.eirp_dbm == pytest.approx(34.0 + 30.0 + 10.0 * math.log10(30.0))
    lay = ntn.ntn_layout(sc, geom)
    assert (lay.xmin, lay.xmax, lay.ymin, lay.ymax) == (-30e3, 30e3, -30e3, 30e3)
    nm = ntn.NtnMap(lay, geom)
    assert int(nm.nominal_cell(np.array(0.0), np.array(0.0))) == 0
    assert nm.nominal_cell(c[:, 0], c[:, 1]).tolist() == list(range(19))


def test_link_budget_cases_of_tr38821():
    for h, eirp, bw, fspl_t, atm_t, cnr_t in CASES.values():
        fspl, atm, cnr = link_budget(h, eirp, bw)
        assert round(fspl, 1) == fspl_t and round(atm, 1) == atm_t and cnr == pytest.approx(cnr_t, abs=0.1)


def test_verify_group_ntn_reports_n2_as_failed():
    rep = run_verify(groups=["ntn"])
    status = {c.name.split(":")[0]: c.status for c in rep.checks}
    assert status == {"N1": "PASS", "N2": "FAIL", "N3": "PASS"}                    # N2 is pre-registered and failed
    assert isinstance(rep, Report)


def test_world_source_and_cell_centres():
    sc = hl.builtin_scenario(CARD).with_overrides(SHORT)
    w = build_world(sc, 1)
    assert w.ntn is not None and w.layout.kind == "ntn" and w.layout.n_sites == 19
    assert np.allclose(w.cell_center(0.0), w.ntn.beam_centres(0.0))
    src = ntn.NtnSource(w, chunk_steps=200)
    chunks = list(src.chunks())
    assert sum(ch.n for ch in chunks) == w.x.shape[0]
    rs = np.concatenate([ch.rsrp for ch in chunks])
    assert rs.shape == (w.x.shape[0], 8, 19) and np.all(np.isfinite(rs))
    best = rs.max(axis=2)
    assert np.all(best < -60.0) and np.median(best) > -110.0       # received powers of an S-band LEO link
    again = np.concatenate([ch.rsrp for ch in ntn.NtnSource(build_world(sc, 1), chunk_steps=200).chunks()])
    assert np.array_equal(rs, again)                                                # the same world: the same powers


def test_card_and_validation():
    sc = hl.builtin_scenario(CARD)
    assert sc.layout.kind == "ntn" and sc.ntn.n_beams == 19 and sc.radio.carrier_ghz == 2.0
    assert "ntn" in sc.to_dict() and "ntn" not in hl.builtin_scenario("smoke").to_dict()
    for over, key in (({"ntn.environment": "forest"}, "ntn.environment"),
                      ({"ntn.centre_elevation_deg": 5.0}, "ntn.centre_elevation_deg"),
                      ({"radio.carrier_ghz": 20.0}, "radio.carrier_ghz"),
                      ({"ntn.n_beams": 0}, "ntn.altitude_km"),
                      ({"layout.wrap": True}, "layout.kind")):
        with pytest.raises(ConfigError, match=key.replace(".", r"\.")):
            sc.with_overrides(over)
    svg = layout_svg(sc)
    assert svg.startswith("<svg") and "16 beam centres above 10 degrees elevation" in svg
    assert Scenario.from_dict(sc.to_dict()) == sc


def test_cho_d2_entering_and_leaving():
    rule = CHOD2(d_thresh1_m=10e3, d_thresh2_m=10e3, hys_m=1e3)
    ref = np.array([[0.0, 0.0], [30e3, 0.0]])
    rule.ctx = SimpleNamespace(cell_center=lambda t: ref, sites=ref)
    rule.d_on = np.zeros((4, 2), dtype=bool)

    def obs(x):
        return SimpleNamespace(t=0.0, x=np.asarray(x, dtype=float), y=np.zeros(4), serving=np.zeros(4, dtype=int))

    on = rule.exec_condition(obs([5e3, 11.5e3, 21.5e3, 25e3]))
    assert on[:, 1].tolist() == [False, False, True, True]          # Ml1 - Hys > 10 km and Ml2 + Hys < 10 km
    on = rule.exec_condition(obs([5e3, 11.5e3, 19.5e3, 8.5e3]))
    assert on[:, 1].tolist() == [False, False, True, False]         # inside both hystereses: stays; else leaves
    with pytest.raises(ValueError):
        CHOD2(hys_m=-1.0)
    p = rule.params()
    assert "immediate" not in p and p["d_thresh1_m"] == 10e3 and p["hys_m"] == 1e3


def test_cho_d2_contract_and_reduction_to_cho():
    print(check_rule(CHOD2, params={"o_exec_db": 3.0},
                     reduces_to=("cho", {"o_exec_db": 3.0}, {"d_thresh1_m": 0.0, "d_thresh2_m": 1e12, "hys_m": 0.0})))


def test_ntn_runs_are_reproducible():
    sc = hl.builtin_scenario(CARD).with_overrides(SHORT)
    rules = [{"rule": "a3", "off_db": 3.0, "ttt_s": 0.16}, {"rule": "cho_d2"}]
    a = hl.simulate(sc, rules, seeds=[1])
    b = hl.simulate(sc, rules[::-1], seeds=[1])
    assert {r.rule: r.fingerprint for r in a} == {r.rule: r.fingerprint for r in b}
    assert a[0].metrics["handovers_pm"] > 0.0                                       # the beams sweep over still users
