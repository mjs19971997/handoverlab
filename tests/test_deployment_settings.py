# SPDX-License-Identifier: MIT
"""The documented sector-antenna settings (user guide, "Settings closer to deployed networks"): TR 38.901
Table 7.8-1 with one SSB beam per sector, and 8 SSB beams on an (8, 8) panel (TS 38.213 clause 4.1,
TR 38.802 Table A.2.5-2). They validate on the urban macro card, give three cells per site and the expected
gains, and run repeatably, also without beam failure recovery."""
import numpy as np

import handoverlab as hl
from handoverlab.channel.antenna import beam_gain_db

SECTOR = {"radio.beams": {"sectors": 3, "sector_az0_deg": 30.0, "n_ssb": 1, "panel": [10, 1], "tilt_deg": 102.0}}
SHORT = {"mobility.users": 8, "run.duration_s": 10.0, "run.warmup_s": 1.0}
MULTI = {"radio.beams": {"sectors": 3, "sector_az0_deg": 30.0, "n_ssb": 8, "panel": [8, 8], "tilt_deg": 102.0}}
RULES = [{"rule": "a3", "name": "A3", "off_db": 4.0, "ttt_s": 0.256}]


def _sc(ov=SECTOR):
    return hl.builtin_scenario("urban-macro-tr37885-4ghz").with_overrides(dict(SHORT, **ov))


def test_sector_setting_validates():
    b = _sc().radio.beams
    assert (b.sectors, b.n_ssb, tuple(b.panel), b.tilt_deg) == (3, 1, (10, 1), 102.0)
    assert [b.sector_az0_deg + s * 360.0 / b.sectors for s in range(b.sectors)] == [30.0, 150.0, 270.0]


def test_sector_beam_gain():
    # towards the steered direction: element G_E,max 8 dBi with A_V at 12 deg below the horizon, plus the array
    # gain 10 log10(10)
    g = beam_gain_db(np.array([102.0]), np.array([0.0]), np.array([0.0]), 102.0, 10, 1)
    assert abs(float(g[0, 0]) - (8.0 - 12.0 * (12.0 / 65.0) ** 2 + 10.0)) < 1e-4
    # half the 65 deg beam width away in azimuth the element is 3 dB down (Table 7.3-1)
    g3 = beam_gain_db(np.array([102.0]), np.array([32.5]), np.array([0.0]), 102.0, 10, 1)
    assert abs(float(g[0, 0] - g3[0, 0]) - 3.0) < 1e-4


def test_sector_setting_runs_repeatably():
    sc = _sc()
    w = hl.build_world(sc, 5)
    sites = (hl.build_world(hl.builtin_scenario("urban-macro-tr37885-4ghz").with_overrides(SHORT), 5).n_cells)
    assert w.n_cells == 3 * sites
    a = [r.fingerprint for r in hl.run_world(w, RULES)]
    b = [r.fingerprint for r in hl.run_world(hl.build_world(sc, 5), RULES)]
    assert a == b


def test_multi_beam_gain():
    # 8 SSB beams spread over the 120 deg sector; each beam peaks with the full array gain 10 log10(64) towards
    # its own azimuth, and the outer beams are well below it at the sector boresight
    b = _sc(MULTI).radio.beams
    assert b.n_ssb == 8 and b.beam_span_deg is None
    az = np.linspace(-52.5, 52.5, 8)
    g = beam_gain_db(np.array([102.0]), np.array([az[0]]), az, 102.0, 8, 8)
    ge = 8.0 - 12.0 * (12.0 / 65.0) ** 2 - 12.0 * (az[0] / 65.0) ** 2
    assert int(np.argmax(g[0])) == 0
    assert abs(float(g[0, 0]) - (ge + 10.0 * np.log10(64.0))) < 0.05
    g0 = beam_gain_db(np.array([102.0]), np.array([0.0]), az, 102.0, 8, 8)
    assert float(g0[0, 0]) < float(g0[0].max()) - 10.0


def test_multi_beam_and_no_bfd_run_repeatably():
    for ov in (MULTI, {"radio.beams": dict(MULTI["radio.beams"], bfd=False)},
               {"radio.beams": dict(SECTOR["radio.beams"], bfd=False)}):
        sc = _sc(ov)
        a = [r.fingerprint for r in hl.run_world(hl.build_world(sc, 2), RULES)]
        b = [r.fingerprint for r in hl.run_world(hl.build_world(sc, 2), RULES)]
        assert a == b
    nb = hl.run_world(hl.build_world(_sc({"radio.beams": dict(MULTI["radio.beams"], bfd=False)}), 2), RULES)[0]
    assert nb.metrics["beam_failures_pm"] == 0.0
