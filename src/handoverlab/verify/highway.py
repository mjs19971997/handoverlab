# SPDX-License-Identifier: MIT
"""The highway of TR 37.885 (since 1.11.0): ``handoverlab verify --only highway``.

Checks of the two highway cards ``highway-tr37885-4ghz`` (below 6 GHz: sites
along the road, TR 36.885 clause A.1.3 option 1) and ``highway-tr37885-30ghz``
(above 6 GHz: 19 hexagonal sites, option 2):

H1  geometry and link budget equal the values of TR 37.885 V15.3.0, TR 36.885
    V14.0.0 and TR 38.901 V17.0.0 (exact);
H2  with wrap-around the static received power of every site is continuous where
    a vehicle re-enters the road (largest jump below 0.5 dB);
H3  the coupling gain to the strongest site (percentiles 5 to 95) agrees within
    0.5 dB with an independent computation: uniform drops on the lanes, the
    sites and their wrap-around images built from the TR geometry (for the
    hexagonal layout with the 19-site functions of the calibration module, in
    the frame of the grid, not turned), the TR 38.901 path loss written out
    again here (RMa LOS) or taken from the calibration module (UMa LOS), and
    Gaussian shadowing with the card's standard deviation and inter-site
    correlation;
H4  with ``radio.los_model: los`` every link has the LOS path loss.

TR 37.885 has no published calibration of the base-station-to-vehicle link of
the highway (its calibration work is for the sidelink), so H3 checks that the
TR assumptions are implemented, not a company result.  The plan with these
criteria was written before the first run.
"""
from __future__ import annotations

import math
from typing import Dict, Tuple

import numpy as np

from ..channel.pathloss import path_loss, radio_kwargs
from ..channel.source import RadioSource
from ..scenarios import builtin_scenario
from ..world import build_world
from .calibration import hex_sites, pathloss_db, wrap_offsets

CARDS = ("highway-tr37885-4ghz", "highway-tr37885-30ghz")

#: values fixed by the texts: key -> (value, source)
TR_VALUES: Dict[str, Dict[str, Tuple[object, str]]] = {
    "highway-tr37885-4ghz": {
        "layout.lanes": (3, "TR 37.885 Table A-1"), "layout.lane_width_m": (4.0, "TR 37.885 Table A-1"),
        "layout.wrap": (True, "TR 37.885 Table A-1"), "layout.site_spacing_m": (1732.0, "TR 37.885 Table 6.1.3-1"),
        "layout.site_offset_m": (35.0, "TR 36.885 clause A.1.3 option 1"),
        "layout.highway_sites": ("one_side", "TR 36.885 Figure A.1.3-2"),
        "radio.carrier_ghz": (4.0, "TR 37.885 Table 6.1.1-1"), "radio.bandwidth_mhz": (20.0, "TR 37.885 Table 6.1.1-1"),
        "radio.tx_power_dbm": (49.0, "TR 37.885 Table 6.1.1-1"),
        "radio.noise_figure_db": (9.0, "TR 37.885 Table 6.1.1-1"),
        "radio.bs_height_m": (35.0, "TR 37.885 Table 6.1.4-1"), "radio.ue_height_m": (1.6, "TR 37.885 clause 6.1.2"),
        "radio.pathloss": ("rma", "TR 37.885 Table 6.2.1-2"), "radio.los_model": ("los", "TR 37.885 clause 6.2.1"),
        "radio.shadow_los_db": (4.0, "TR 38.901 Table 7.4.1-1"),
        "radio.shadow_los_far_db": (6.0, "TR 38.901 Table 7.4.1-1"),
        "radio.shadow_decorr_m": (37.0, "TR 38.901 Table 7.5-6 Part-2"),
        "mobility.profile": ("v140", "TR 37.885 clause 6.1.2 option A"),
    },
    "highway-tr37885-30ghz": {
        "layout.lanes": (3, "TR 37.885 Table A-1"), "layout.lane_width_m": (4.0, "TR 37.885 Table A-1"),
        "layout.wrap": (True, "TR 37.885 Table A-1"), "layout.site_spacing_m": (500.0, "TR 37.885 Table 6.1.3-2"),
        "layout.highway_sites": ("hex19", "TR 36.885 clause A.1.3 option 2"),
        "radio.carrier_ghz": (30.0, "TR 37.885 Table 6.1.1-2"),
        "radio.bandwidth_mhz": (200.0, "TR 37.885 Table 6.1.1-2"),
        "radio.tx_power_dbm": (43.0, "TR 37.885 Table 6.1.1-2"),
        "radio.noise_figure_db": (13.0, "TR 37.885 Table 6.1.1-2"),
        "radio.bs_height_m": (25.0, "TR 37.885 Table 6.1.4-1"), "radio.ue_height_m": (1.6, "TR 37.885 clause 6.1.2"),
        "radio.pathloss": ("uma", "TR 37.885 Table 6.2.1-2"), "radio.los_model": ("los", "TR 37.885 clause 6.2.1"),
        "radio.shadow_los_db": (4.0, "TR 38.901 Table 7.4.1-1"),
        "radio.shadow_decorr_m": (37.0, "TR 38.901 Table 7.5-6 Part-1"),
        "radio.beams.sectors": (3, "TR 36.885 clause A.1.3 option 2"),
        "radio.beams.panel": ((4, 8),
        "TR 37.885 Table 6.1.4-3"),
        "radio.beams.tilt_deg": (102.0, "TR 37.885 Table 6.1.4-3"),
        "mobility.profile": ("v140", "TR 37.885 clause 6.1.2 option A"),
    },
}


def _get(sc, key):
    obj = sc
    for p in key.split("."):
        obj = getattr(obj, p)
    return tuple(obj) if isinstance(obj, list) else obj


def rma_los_db(d2, h_bs, h_ut, fc_ghz, h=5.0):
    """RMa LOS of TR 38.901 Table 7.4.1-1 with the breakpoint of note 5 (written out again for the check)."""
    d3 = np.sqrt(d2 ** 2 + (h_bs - h_ut) ** 2)
    dbp = 2.0 * math.pi * h_bs * h_ut * fc_ghz * 1e9 / 3.0e8

    def pl1(d):
        return (20.0 * np.log10(40.0 * math.pi * d * fc_ghz / 3.0) + min(0.03 * h ** 1.72, 10.0) * np.log10(d)
                - min(0.044 * h ** 1.72, 14.77) + 0.002 * math.log10(h) * d)
    d3bp = math.sqrt(dbp ** 2 + (h_bs - h_ut) ** 2)
    return np.where(d2 <= dbp, pl1(d3), pl1(d3bp) + 40.0 * np.log10(d3 / d3bp)), dbp


def _lane_points(rng, n, lanes, width, lateral=0.5):
    k = rng.integers(2 * lanes, size=n)
    y = np.abs(k - lanes + 0.5) * width * np.sign(k - lanes + 0.5)   # lane centres +-2, +-6, +-10 m
    return y + rng.uniform(-lateral, lateral, n)


def reference_gain(name: str, sc, n: int, rng) -> np.ndarray:
    """Coupling gain to the strongest site [dB] of ``n`` independent drops (see H3)."""
    R, L = sc.radio, sc.layout
    y = _lane_points(rng, n, L.lanes, L.lane_width_m)
    if L.highway_sites == "hex19":
        isd = L.site_spacing_m
        t = isd * np.array([4.0, math.sqrt(3.0)])
        v = np.array([-t[1], t[0]]) / np.linalg.norm(t)                  # unit normal of the road
        s = rng.uniform(-0.5, 0.5, n)[:, None] * t + y[:, None] * v           # points on the road, frame of the grid
        sites = hex_sites(isd)
        img = (sites[None, :, :] + wrap_offsets(isd)[:, None, :])          # (7, 19, 2)
        d = np.linalg.norm(s[:, None, None, :] - img[None], axis=-1).min(axis=1)  # (n, 19)
        d3 = np.sqrt(d ** 2 + (R.bs_height_m - R.ue_height_m) ** 2)
        pl = pathloss_db("UMa", True, d, d3, R.carrier_ghz, R.bs_height_m, R.ue_height_m)
        sd = np.full(d.shape, R.shadow_los_db)
    else:
        per = L.road_length_m
        m = int(round(per / L.site_spacing_m))
        sx = np.arange(m) * L.site_spacing_m
        sy = L.lanes * L.lane_width_m + L.site_offset_m
        x = rng.uniform(0.0, per, n)
        dx = x[:, None] - sx[None, :]
        dx -= per * np.round(dx / per)
        d = np.hypot(dx, y[:, None] - sy)
        pl, dbp = rma_los_db(d, R.bs_height_m, R.ue_height_m, R.carrier_ghz)
        far = R.shadow_los_far_db if R.shadow_los_far_db is not None else R.shadow_los_db
        sd = np.where(d <= dbp, R.shadow_los_db, far)
    c = R.shadow_site_corr
    z = math.sqrt(c) * rng.standard_normal((n, 1)) + math.sqrt(1.0 - c) * rng.standard_normal(d.shape)
    g = R.bs_gain_db + R.ue_gain_db - pl + sd * z
    return g.max(axis=1)


def _abstraction(sc):
    """The card with the antenna abstraction (no beams) and without time variation, for H2 to H4."""
    return sc.with_overrides({"radio.beams": None, "radio.time_var_db": 0.0, "run.duration_s": 10.0,
                              "run.warmup_s": 0.0})


def simulated_gain(sc, seeds, every_s: float = 1.0) -> np.ndarray:
    """Coupling gain to the strongest site [dB] seen by the vehicles of the card, every ``every_s`` seconds."""
    out = []
    for seed in seeds:
        w = build_world(sc, seed)
        src = RadioSource(w)
        k_every = int(round(every_s / sc.protocol.step_s))
        p0 = sc.radio.tx_power_dbm
        for ch in src.chunks():
            ks = np.arange(ch.k0, ch.k0 + ch.n)
            sel = ks % k_every == 0
            out.append(ch.rsrp[sel].max(axis=-1).ravel() - p0)
    return np.concatenate(out)


def highway_checks(rep, n_ref: int = 20000, seeds=tuple(range(1, 11)), tol_db: float = 0.5) -> None:
    rep.section("highway", "the TR 37.885 highway: geometry, wrap-around and coupling gain against an independent "
                           "computation (TR 37.885 V15.3.0, TR 36.885 V14.0.0, TR 38.901 V17.0.0)")
    for name in CARDS:
        sc = builtin_scenario(name)
        # H1
        bad = ["%s = %r (%s: %r)" % (k, _get(sc, k), src, v) for k, (v, src) in TR_VALUES[name].items()
               if _get(sc, k) != v]
        lay = build_world(_abstraction(sc), 1).layout
        if sc.layout.highway_sites == "hex19":
            d = lay.distances(lay.sites[:, 0], lay.sites[:, 1])
            d[np.arange(len(d)), np.arange(len(d))] = np.inf
            nn = d.min(axis=1)
            if lay.n_sites != 19 or np.abs(nn - sc.layout.site_spacing_m).max() > 1e-6:
                bad.append("hexagonal layout: %d sites, nearest wrapped neighbours %.3f-%.3f m"
                           % (lay.n_sites, nn.min(), nn.max()))
        if lay.period_x is None or lay.period_x < 2000.0:
            bad.append("wrap-around period %s m (TR 37.885 Table A-1: road >= 2000 m with wrap-around)" % lay.period_x)
        rep.check("%s: geometry and link budget as in the TRs" % name, not bad,
                  "; ".join(bad) if bad else "%d values, %d sites, road %.1f m with wrap-around"
                  % (len(TR_VALUES[name]), lay.n_sites, lay.period_x))
        # H2
        ab = _abstraction(sc)
        w = build_world(ab, 2)
        rs = np.concatenate([c.rsrp for c in RadioSource(w).chunks()])
        reent = np.abs(np.diff(w.x, axis=0)) > 0.5 * lay.period_x
        k, u = np.nonzero(reent)
        jump = np.abs(rs[k + 1, u] - rs[k, u]).max() if len(k) else float("nan")
        step = np.percentile(np.abs(np.diff(rs, axis=0))[~reent], 99.9)
        rep.check("%s: received power continuous at the wrap-around" % name, len(k) > 0 and jump < 0.5,
                  "%d re-entries, largest jump %.3f dB (99.9 %% of the other steps below %.3f dB)"
                  % (len(k), jump, step))
        # H3
        sim = simulated_gain(ab, seeds)
        ref = reference_gain(name, ab, n_ref, np.random.default_rng(7))
        q = np.arange(5, 100, 5)
        diff = np.percentile(sim, q) - np.percentile(ref, q)
        worst = int(np.argmax(np.abs(diff)))
        rep.check("%s: coupling gain to the strongest site, percentiles 5-95 within %.1f dB" % (name, tol_db),
                  bool(np.all(np.abs(diff) <= tol_db)),
                  "largest difference %+.2f dB at the %d %% point; median %.1f dB (reference %.1f dB); "
                  "%d and %d samples"
                  % (diff[worst], q[worst], np.median(sim), np.median(ref), len(sim), len(ref)))
        # H4
        flat = ab.with_overrides({"radio.shadow_los_db": 0.0, "radio.shadow_los_far_db": None,
                                  "radio.shadow_nlos_db": 0.0})
        w = build_world(flat, 3)
        R = flat.radio
        ch = next(RadioSource(w).chunks())
        x, y = w.x[:ch.n].ravel(), w.y[:ch.n].ravel()
        d2 = w.layout.distances(x, y)
        want = R.tx_power_dbm + R.bs_gain_db + R.ue_gain_db - path_loss(d2, True, R.pathloss, R.carrier_ghz,
                                                                          R.bs_height_m, R.ue_height_m,
                                                                          **radio_kwargs(R))
        err = float(np.abs(ch.rsrp.reshape(want.shape) - want).max())
        rep.check("%s: every link has the LOS path loss" % name, err < 1e-6,
                  "largest difference from the LOS path loss %.2e dB over %d links" % (err, want.size))
