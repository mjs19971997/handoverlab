# SPDX-License-Identifier: MIT
"""radio.channel_detail of 2.1.0: the large-scale channel as TR 38.901 V19.5.0 specifies it, the corrected cards,
and the switch back to the model of 2.0.0 (LEGACY_1X, LEGACY_CARDS)."""
import math
import warnings

import numpy as np
import pytest

from handoverlab.channel import ntn
from handoverlab.channel import pathloss as pl
from handoverlab.channel.radiomap import GaussianField, applicability_warning
from handoverlab.config import ConfigError, Scenario
from handoverlab.layout import highway, make_layout, open_area
from handoverlab.mobility import PROFILES
from handoverlab.scenarios import builtin_scenario, card_markdown, unused_keys
from handoverlab.stability import LEGACY_1X, LEGACY_CARDS


def _lag_corr(f, k):
    """Mean correlation of a 2D field at a lag of k pixels along x and along y."""
    cx = np.corrcoef(f[:, :-k].ravel(), f[:, k:].ravel())[0, 1]
    cy = np.corrcoef(f[:-k].ravel(), f[k:].ravel())[0, 1]
    return 0.5 * (cx + cy)


# ---------------------------------------------------------------- CH-1: exponential autocorrelation
def test_exponential_field_has_the_autocorrelation_of_eq_7_4_5():
    lay = open_area((1600.0, 1600.0), 400.0)
    d = 20.0
    g = GaussianField(np.random.default_rng(1), lay, 2, d, 2.0, 0.0, "exp")
    for m in range(2):
        f = g.f[:, :, m].astype(float)
        assert f.std() == pytest.approx(1.0, abs=0.05)
        for lag in (2.0, 10.0, 20.0, 40.0):                      # TR 38.901 Eq. (7.4-5): exp(-|dx| / d_cor)
            assert _lag_corr(f, int(lag / g.res)) == pytest.approx(math.exp(-lag / d), abs=0.04)
    # the Gaussian-shaped field of channel_detail "simple" falls much faster beyond d_cor
    gg = GaussianField(np.random.default_rng(1), lay, 1, d, 2.0, 0.0, "gauss").f[:, :, 0].astype(float)
    assert _lag_corr(gg, 20) < 0.03 < math.exp(-2.0) - 0.05


def test_exponential_field_has_unit_variance_between_raster_points():
    lay = open_area((1200.0, 1200.0), 300.0)
    g = GaussianField(np.random.default_rng(2), lay, 1, 10.0, 2.0, 0.0, "exp")
    rng = np.random.default_rng(3)
    x, y = rng.uniform(-550.0, 550.0, 200000), rng.uniform(-550.0, 550.0, 200000)
    assert float(g.at(x, y)[:, 0].std()) == pytest.approx(1.0, abs=0.03)
    mid = g.x0 + (np.arange(20, 500) + 0.5) * g.res              # half way between raster points
    v = g.at(mid, np.full(len(mid), g.y0 + 300.5 * g.res))[:, 0]
    assert float(v.std()) == pytest.approx(1.0, abs=0.12)
    assert np.allclose(g.at_pairs(x[:50], y[:50], np.arange(50), np.zeros(50, dtype=int)), g.at(x[:50], y[:50])[:, 0],
                       atol=1e-5)


def test_open_area_map_gives_the_field_with_unit_variance():
    from handoverlab.channel.radiomap import RadioMap
    sc = Scenario.from_dict({"layout": {"kind": "open_area", "area_m": [1500.0, 1500.0], "site_spacing_m": 500.0},
                             "radio": {"map_res_m": 4.0, "shadow_decorr_m": 20.0}})
    lay = make_layout(sc.layout)
    rm = RadioMap(lay, sc.radio, 6)
    rng = np.random.default_rng(7)
    x, y = rng.uniform(-700.0, 700.0, 100000), rng.uniform(-700.0, 700.0, 100000)
    v = rm.lookup_field(x, y)
    assert float(v.std()) == pytest.approx(1.0, abs=0.05)
    assert float(rm.lookup(x, y).std()) < float(v.std())         # plain interpolation loses variance
    old = RadioMap(lay, sc.with_overrides({"radio.channel_detail": "simple"}).radio, 6)
    assert np.array_equal(old.lookup_field(x[:100], y[:100]), old.lookup(x[:100], y[:100]))


def test_exponential_field_is_periodic_with_the_wrap_around():
    lay = highway(1000.0, 3, 4.0, 500.0, 35.0, None, wrap=True, one_side=True)
    g = GaussianField(np.random.default_rng(4), lay, lay.n_sites, 37.0, 2.0, 0.0, "exp")
    x = np.linspace(lay.xmin, lay.xmax, 50)
    y = np.full(50, 2.0)
    assert np.allclose(g.at(x, y), g.at(x + lay.period_x, y), atol=1e-5)
    f = g.f.astype(float)                                        # correlated across the seam as inside
    seam = np.corrcoef(f[:, -1].ravel(), f[:, 0].ravel())[0, 1]
    inside = np.corrcoef(f[:, 10].ravel(), f[:, 11].ravel())[0, 1]
    assert seam == pytest.approx(math.exp(-g.res / 37.0), abs=0.08)
    assert abs(seam - inside) < 0.08
    # the radio map has a whole number of pixels per period, so both sides of the seam are interpolated alike
    from handoverlab.channel.radiomap import RadioMap
    radio = Scenario().with_overrides({"radio.map_res_m": 3.0, "radio.shadow_decorr_m": 37.0}).radio
    rm = RadioMap(lay, radio, 8)
    assert abs(lay.period_x / rm.res - round(lay.period_x / rm.res)) < 1e-9
    xs = np.linspace(lay.xmin - 2.0 * rm.res, lay.xmin + 2.0 * rm.res, 40)     # the pads on both sides of the seam
    assert np.allclose(rm.lookup_field(xs, np.full(40, 2.0)), rm.lookup_field(xs + lay.period_x, np.full(40, 2.0)),
                       atol=1e-4)


def test_site_correlation_follows_clause_7_5_step_4():
    assert Scenario().radio.shadow_site_corr is None
    assert pl.site_corr(Scenario().radio) == 0.0                                    # 3gpp: uncorrelated
    simple = Scenario().with_overrides({"radio.channel_detail": "simple"}).radio
    assert pl.site_corr(simple) == 0.5                                              # the value of 2.0.0
    assert pl.site_corr(Scenario().with_overrides({"radio.shadow_site_corr": 0.3}).radio) == 0.3
    with pytest.raises(ConfigError, match="channel_detail"):
        Scenario().with_overrides({"radio.channel_detail": "exact"})


# ---------------------------------------------------------------- CH-6, CH-7: UMa above 13 m, ranges
def test_uma_los_probability_with_c_prime():
    d = np.array([10.0, 18.0, 50.0, 100.0, 200.0, 400.0])
    base = pl.p_los_uma(d)
    assert np.array_equal(pl.p_los_uma(d, 1.5), base) and np.array_equal(pl.p_los_uma(d, 13.0), base)
    h = 22.5
    cp = ((h - 13.0) / 10.0) ** 1.5
    want = np.where(d <= 18.0, 1.0, base * (1.0 + cp * 1.25 * (d / 100.0) ** 3 * np.exp(-d / 150.0)))
    assert np.allclose(pl.p_los_uma(d, h), want)
    assert np.all(pl.p_los(d[2:], "uma", h) > base[2:])
    assert np.array_equal(pl.p_los(d, "uma", None), base)


def test_uma_effective_environment_height_of_note_1():
    rng = np.random.default_rng(5)
    n = 200000
    d2 = np.full(n, 150.0)
    h = 22.5
    he = pl.uma_effective_height(rng.random(n), rng.random(n), d2, h)
    c = float(pl.uma_c(150.0, h))
    assert np.mean(he == 1.0) == pytest.approx(1.0 / (1.0 + c), abs=0.005)
    vals = set(np.unique(he[he != 1.0]))
    assert vals == {12.0, 15.0, 18.0, 21.0}                       # 12, 15, ..., h_UT - 1.5 = 21
    assert np.all(pl.uma_effective_height(rng.random(10), rng.random(10), np.full(10, 150.0), 1.5) == 1.0)
    assert np.all(pl.uma_effective_height(np.ones(5), np.zeros(5), np.full(5, 10.0), h) == 1.0)   # g = 0 at 18 m
    # path loss with h_E: the breakpoint d'BP = 4 (h_BS - h_E)(h_UT - h_E) fc / c of note 1
    d = np.array([100.0, 300.0, 1000.0])
    hee = np.array([1.0, 12.0, 12.0])
    got = pl.path_loss(d, True, "uma", 3.5, 25.0, h, h_e=hee)
    for di, hi, g in zip(d, hee, got):
        dbp = 4.0 * (25.0 - hi) * (h - hi) * 3.5e9 / 3.0e8
        d3 = math.hypot(di, 25.0 - h)
        want = (28.0 + 22.0 * math.log10(d3) + 20.0 * math.log10(3.5) if di <= dbp else
                28.0 + 40.0 * math.log10(d3) + 20.0 * math.log10(3.5) - 9.0 * math.log10(dbp ** 2 + (25.0 - h) ** 2))
        assert g == pytest.approx(want, abs=1e-9)
    assert np.array_equal(pl.path_loss(d, True, "uma", 3.5, 25.0, h, h_e=np.ones(3)),
                          pl.path_loss(d, True, "uma", 3.5, 25.0, h))


def test_heights_must_lie_in_the_applicability_range():
    with pytest.raises(ConfigError, match="ue_height_m"):
        Scenario().with_overrides({"radio.pathloss": "uma", "radio.ue_height_m": 25.0, "radio.bs_height_m": 25.0})
    with pytest.raises(ConfigError, match="ue_height_m"):
        Scenario().with_overrides({"radio.ue_height_m": 1.0})                      # UMi: 1.5-22.5 m
    with pytest.raises(ConfigError, match="bs_height_m"):
        Scenario().with_overrides({"radio.pathloss": "rma", "radio.carrier_ghz": 4.0, "radio.bs_height_m": 5.0})
    Scenario().with_overrides({"radio.ue_height_m": 1.0, "radio.channel_detail": "simple"})   # no check
    Scenario().with_overrides({"radio.pathloss": "uma", "radio.ue_height_m": 20.0, "radio.bs_height_m": 25.0})


def test_warning_beyond_the_upper_distance_bound():
    sc = builtin_scenario("rural-700mhz")
    with pytest.warns(UserWarning, match="applicability range"):
        applicability_warning(make_layout(sc.layout), sc.radio)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        sm = builtin_scenario("smoke")
        applicability_warning(make_layout(sm.layout), sm.radio)
        simple = sc.with_overrides({"radio.channel_detail": "simple"})
        applicability_warning(make_layout(simple.layout), simple.radio)


def test_uma_open_area_with_a_high_ue_runs():
    sc = Scenario.from_dict({"layout": {"kind": "open_area", "area_m": [600.0, 600.0], "site_spacing_m": 300.0},
                             "radio": {"pathloss": "uma", "bs_height_m": 25.0, "ue_height_m": 19.5,
                                       "carrier_ghz": 3.5, "place_share": 0.5},
                             "mobility": {"users": 3, "profile": "p3"}, "run": {"duration_s": 1.0, "warmup_s": 0.0}})
    from handoverlab.channel.source import RadioSource
    from handoverlab.world import build_world
    w = build_world(sc, 1)
    src = RadioSource(w)
    assert src.he_u is not None
    rs = np.concatenate([c.rsrp for c in src.chunks()])
    assert np.all(np.isfinite(rs))


# ---------------------------------------------------------------- CH-8: co-sited layers
def test_cosited_layer_keeps_the_los_and_shadowing_settings():
    base = {"radio.layers": [{"name": "b", "carrier_ghz": 28.0, "bandwidth_mhz": 400.0, "cosited": True}]}
    builtin_scenario("smoke").with_overrides(base)
    for k, v in (("pathloss", "uma"), ("los_corr_m", 20.0), ("shadow_decorr_m", 13.0)):
        over = {"radio.layers": [{"name": "b", "carrier_ghz": 28.0, "bandwidth_mhz": 400.0, "cosited": True, k: v}]}
        with pytest.raises(ConfigError, match="7.6.5"):
            builtin_scenario("smoke").with_overrides(over)
        builtin_scenario("smoke").with_overrides(dict(over, **{"radio.channel_detail": "simple"}))
    # the same value as the first layer is allowed
    builtin_scenario("smoke").with_overrides({"radio.layers": [{"name": "b", "carrier_ghz": 28.0, "cosited": True,
                                                                "pathloss": "umi_street_canyon"}]})


# ---------------------------------------------------------------- SC-1, SC-2, SC-5: profiles and cards
def test_fixed_speed_profiles():
    for name, kmh in (("p3", 3.0), ("v30", 30.0), ("v120", 120.0), ("v140c", 140.0), ("v70c", 70.0)):
        (g,) = PROFILES[name]
        assert g.v_min == g.v_max == pytest.approx(kmh / 3.6) and tuple(g.lateral_m) == (0.0, 0.0)
    assert PROFILES["ped3"][0].v_min < PROFILES["ped3"][0].v_max          # the old profiles keep their meaning
    assert PROFILES["v140"][0].lateral_m == (0.0, 0.5)


def test_open_office_los_probability():
    d = np.array([3.0, 5.0, 20.0, 49.0, 100.0])
    want = [1.0, 1.0, math.exp(-15.0 / 70.8), math.exp(-44.0 / 70.8), 0.54 * math.exp(-51.0 / 211.7)]
    assert np.allclose(pl.p_los(d, "inh_office_open"), want)
    assert np.allclose(pl.path_loss(d, False, "inh_office_open", 4.0, 3.0, 1.0),
                       pl.path_loss(d, False, "inh_office", 4.0, 3.0, 1.0))


def test_cards_follow_the_texts_and_the_legacy_values_restore_them():
    want = {"smoke": ("radio.ue_height_m", 1.6), "urban-grid-10ghz": ("radio.ue_height_m", 1.6),
            "indoor-office-4ghz": ("mobility.profile", "p3"), "rural-700mhz": ("mobility.profile", "v120"),
            "dense-urban-2layer": ("mobility.profile", "v30"), "highway-tr37885-4ghz": ("mobility.profile", "v140c"),
            "ntn-leo600-2ghz": ("ntn.los_model", "los")}
    for name, (key, value) in want.items():
        sc = builtin_scenario(name)
        sec, k = key.split(".")
        assert getattr(getattr(sc, sec), k) == value
        old = sc.with_overrides(LEGACY_1X).with_overrides(LEGACY_CARDS[name])
        assert old.radio.channel_detail == "simple"
    assert builtin_scenario("indoor-office-4ghz").radio.pathloss == "inh_office_open"
    old = builtin_scenario("dense-urban-2layer").with_overrides(LEGACY_CARDS["dense-urban-2layer"])
    assert old.mobility.groups[0].v_min == 8.33


def test_card_pages_leave_out_unused_keys_and_keep_card_sources():
    sc = builtin_scenario("ntn-leo600-2ghz")
    assert {"radio.pathloss", "radio.los_corr_m", "layout.site_spacing_m"} <= unused_keys(sc)
    page = card_markdown("ntn-leo600-2ghz")
    assert "| `radio.pathloss` |" not in page and "Not read by this layout" in page
    page = card_markdown("highway-tr37885-30ghz")
    assert "| `radio.shadow_nlos_db` |" not in page and "| `radio.bs_gain_db` |" not in page
    assert "TR 37.885 Table 6.1.4-3" in [r for r in page.splitlines() if r.startswith("| `radio.beams.panel`")][0]


# ---------------------------------------------------------------- NT-1, NT-2: NTN beams and propagation
def test_ntn_beam_spacing_from_the_tabled_beamwidth():
    sc = builtin_scenario("ntn-leo600-2ghz")
    g = ntn.NtnGeometry(sc)
    assert g.hpbw == 4.4127                                           # TR 38.821 Table 6.1.1.1-1
    assert ntn.hpbw_deg(g.ka) == pytest.approx(4.4127, abs=1e-9)
    assert math.sqrt(3.0) * math.sin(math.radians(g.hpbw) / 2.0) == pytest.approx(0.0668, abs=2e-4)   # Table -6
    g1 = ntn.NtnGeometry(sc.with_overrides({"ntn.aperture_m": 1.0, "ntn.centre_elevation_deg": 90.0}))
    assert g1.hpbw == 8.8320                                          # Table 6.1.1.1-2
    gs = ntn.NtnGeometry(sc.with_overrides({"radio.channel_detail": "simple"}))
    assert gs.ka == ntn.ka_from_aperture(2.0, 2.0) and gs.hpbw == pytest.approx(4.4198, abs=1e-3)
    assert ntn.NtnGeometry(sc.with_overrides({"ntn.hpbw_deg": 5.0})).hpbw == 5.0
    with pytest.raises(ConfigError, match="los_model"):
        sc.with_overrides({"ntn.los_model": "nlos"})


def test_ntn_los_baseline_has_no_clutter_loss():
    from handoverlab.world import build_world
    short = {"mobility.users": 40, "run.duration_s": 1.0, "run.warmup_s": 0.0}
    sc = builtin_scenario("ntn-leo600-2ghz").with_overrides(short)
    a = np.concatenate([c.rsrp for c in ntn.NtnSource(build_world(sc, 3)).chunks()])
    pb = sc.with_overrides({"ntn.los_model": "probability"})
    b = np.concatenate([c.rsrp for c in ntn.NtnSource(build_world(pb, 3)).chunks()])
    same = np.isclose(a, b, atol=1e-9)
    assert 0.5 < same.mean() < 1.0                 # LOS links of the probability model are the same
    assert float(np.mean(a[~same] - b[~same])) > 10.0   # NLOS links had the clutter loss (16-20 dB, rural S band)


def test_rsrp_per_resource_element_uses_the_transmission_bandwidth_configuration():
    """TS 38.101-1 / -2 Table 5.3.2-1: 20 MHz at 30 kHz has 51 RB in FR1, 100 MHz at 120 kHz 66 RB in FR2."""
    import math
    from handoverlab.channel.extended import n_rb, re_offset_db
    assert n_rb(20.0, 30.0, 3.5) == 51 and n_rb(100.0, 120.0, 28.0) == 66 and n_rb(50.0, 60.0, 28.0) == 66
    assert n_rb(50.0, 60.0, 3.5) == 65 and n_rb(400.0, 120.0, 3.5) is None and n_rb(100.0, 30.0, 15.0) is None
    assert re_offset_db(20.0, 30.0, 3.5, "3gpp") == pytest.approx(10 * math.log10(612))
    assert re_offset_db(20.0, 30.0, 3.5, "simple") == pytest.approx(10 * math.log10(20e3 / 30))
    assert re_offset_db(100.0, 30.0, 15.0, "3gpp") == pytest.approx(10 * math.log10(100e3 / 30))   # FR3: no table
