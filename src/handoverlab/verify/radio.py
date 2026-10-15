# SPDX-License-Identifier: MIT
"""Checks of the radio model against the formulas of 3GPP TR 38.901.

``pathloss_checks``
    Path loss, breakpoint distance and LOS probability against values
    computed by hand from TR 38.901 Tables 7.4.1-1 and 7.4.2-1 (independently
    of the implementation), continuity at the breakpoint, NLOS >= LOS, noise.

``radio_statistics``
    Statistics of a simulated world against the model's parameters: standard
    deviation of the shadowing on LOS and NLOS links, its spatial correlation
    along a street and its correlation between sites, the share of LOS links
    against the LOS probability (spatially consistent LOS state of clause
    7.6.3.3), the time-varying component (standard deviation and correlation
    after one time constant), the L1 measurement error and the L3 filter.
"""
from __future__ import annotations

import dataclasses
import math
from typing import Sequence

import numpy as np

from ..channel import pathloss as pl
from ..channel.radiomap import RadioMap
from ..channel.source import RadioSource
from ..config import Scenario
from ..layout import make_layout
from ..measurement import l3_coefficient
from ..world import build_world

C0 = 299792458.0


def _hand_umi_los(d, fc, hb=10.0, hu=1.5):
    d3 = math.hypot(d, hb - hu)
    dbp = 4 * (hb - 1) * (hu - 1) * fc * 1e9 / C0
    if d <= dbp:
        return 32.4 + 21 * math.log10(d3) + 20 * math.log10(fc)
    return 32.4 + 40 * math.log10(d3) + 20 * math.log10(fc) - 9.5 * math.log10(dbp ** 2 + (hb - hu) ** 2)


def _hand_umi_nlos(d, fc, hb=10.0, hu=1.5):
    d3 = math.hypot(d, hb - hu)
    return max(_hand_umi_los(d, fc, hb, hu), 35.3 * math.log10(d3) + 22.4 + 21.3 * math.log10(fc) - 0.3 * (hu - 1.5))


def _hand_uma_los(d, fc, hb=25.0, hu=1.5):
    d3 = math.hypot(d, hb - hu)
    dbp = 4 * (hb - 1) * (hu - 1) * fc * 1e9 / C0
    if d <= dbp:
        return 28.0 + 22 * math.log10(d3) + 20 * math.log10(fc)
    return 28.0 + 40 * math.log10(d3) + 20 * math.log10(fc) - 9 * math.log10(dbp ** 2 + (hb - hu) ** 2)


def _hand_uma_nlos(d, fc, hb=25.0, hu=1.5):
    d3 = math.hypot(d, hb - hu)
    return max(_hand_uma_los(d, fc, hb, hu), 13.54 + 39.08 * math.log10(d3) + 20 * math.log10(fc) - 0.6 * (hu - 1.5))


def pathloss_checks(rep) -> None:
    rep.section("pathloss", "path loss and LOS probability (TR 38.901 Tables 7.4.1-1, 7.4.2-1), by hand")
    cases = [  # name, model, los, d2d, fc, h_bs, published hand value or None
        ("UMi LOS  10 GHz, d2D 50 m, hBS 10 m, hUT 1.5 m (PL1)", "umi_street_canyon", True, 50.0, 10.0, 10.0, 88.208),
        ("UMi NLOS 10 GHz, d2D 50 m", "umi_street_canyon", False, 50.0, 10.0, 10.0, 103.892),
        ("UMi LOS  3.5 GHz, d2D 200 m (PL1, below d'BP 210.1 m)", "umi_street_canyon", True, 200.0, 3.5, 10.0, 91.611),
        ("UMi LOS  3.5 GHz, d2D 400 m (PL2, above d'BP)", "umi_street_canyon", True, 400.0, 3.5, 10.0, 103.233),
        ("UMi NLOS 28 GHz, d2D 120 m", "umi_street_canyon", False, 120.0, 28.0, 10.0, None),
        ("UMa LOS  3.5 GHz, d2D 100 m, hBS 25 m", "uma", True, 100.0, 3.5, 25.0, 83.138),
        ("UMa NLOS 3.5 GHz, d2D 100 m, hBS 25 m", "uma", False, 100.0, 3.5, 25.0, 103.038),
        ("UMa LOS  7 GHz, d2D 1500 m (PL2)", "uma", True, 1500.0, 7.0, 25.0, None),
    ]
    hand = {("umi_street_canyon", True): _hand_umi_los, ("umi_street_canyon", False): _hand_umi_nlos,
            ("uma", True): _hand_uma_los, ("uma", False): _hand_uma_nlos}
    for name, model, los, d, fc, hb, pub in cases:
        code = float(pl.path_loss(np.array([d]), np.array([los]), model, fc, hb, 1.5)[0])
        ref = hand[(model, los)](d, fc, hb)
        ok = abs(code - ref) < 1e-9 and (pub is None or abs(code - pub) < 5e-4)
        rep.check(name, ok, "code %.4f dB, by hand %.4f dB%s" % (code, ref, "" if pub is None else ", table %.3f" % pub))
    dbp = pl.breakpoint_distance(10.0, 10.0, 1.5)
    rep.check("breakpoint distance d'BP, 10 GHz, hBS 10 m, hUT 1.5 m", abs(dbp - 600.415) < 1e-3, "%.4f m" % dbp)
    dbp35 = pl.breakpoint_distance(3.5, 10.0, 1.5)
    rep.check("breakpoint distance d'BP, 3.5 GHz", abs(dbp35 - 210.145) < 1e-3, "%.4f m" % dbp35)
    a, b = pl.umi_los(np.array(dbp - 1e-7), 10.0), pl.umi_los(np.array(dbp + 1e-7), 10.0)
    rep.check("UMi LOS continuous at the breakpoint", abs(float(a) - float(b)) < 1e-4, "%.4f / %.4f dB" % (a, b))
    for model, dc, name in (("umi_street_canyon", 36.0, "UMi"), ("uma", 63.0, "UMa")):
        for d in (10.0, 50.0, 100.0, 300.0):
            ref = 1.0 if d <= 18.0 else 18.0 / d + math.exp(-d / dc) * (1.0 - 18.0 / d)
            code = float(pl.p_los(np.array(d), model))
            rep.check("%s LOS probability at %g m" % (name, d), abs(code - ref) < 1e-12, "%.4f" % code)
    d = np.linspace(10.0, 2000.0, 400)
    ok = True
    for fc in (3.5, 7.0, 10.0, 15.0, 28.0):
        for model, hb in (("umi_street_canyon", 10.0), ("uma", 25.0)):
            ok &= bool(np.all(pl.path_loss(d, False, model, fc, hb, 1.5) >= pl.path_loss(d, True, model, fc, hb, 1.5)))
    rep.check("NLOS loss >= LOS loss everywhere (UMi and UMa, 3.5-28 GHz, 10-2000 m)", ok)
    n = Scenario().radio.noise_dbm
    rep.check("thermal noise -174 dBm/Hz over 200 MHz plus a noise figure of 7 dB",
              abs(n - (-174.0 + 10.0 * math.log10(200e6) + 7.0)) < 1e-9 and abs(n + 83.990) < 1e-3, "%.3f dBm" % n)


# ---------------------------------------------------------------------------
def _stat_scenario(seed_users: int = 30) -> Scenario:
    return Scenario.from_dict({"name": "radio-statistics", "layout": {"blocks": [2, 2], "site_spacing_m": 100.0},
                               "mobility": {"users": seed_users, "profile": "veh16"},
                               "run": {"duration_s": 60.0, "warmup_s": 0.0}})


def _pixels(rm):
    iy, ix = np.nonzero(rm.idx < rm.n_pix)
    order = rm.idx[iy, ix]
    px = np.empty(rm.n_pix)
    py = np.empty(rm.n_pix)
    px[order] = rm.x0 + ix * rm.res
    py[order] = rm.y0 + iy * rm.res
    return px, py


def radio_statistics(rep, seeds: Sequence[int] = (3,)) -> None:
    rep.section("radio", "radio statistics against the model parameters (%d seed%s)"
                % (len(seeds), "s" if len(seeds) > 1 else ""))
    sc = _stat_scenario()
    R = sc.radio
    lay = make_layout(sc.layout)
    f_los, f_nlos, c10, c20, cs, bins = [], [], [], [], [], {}
    edges = ((20, 40), (40, 80), (80, 160), (160, 320))
    for seed in seeds:
        r0 = dataclasses.replace(R, place_share=0.0, clutter_los=False)
        r1 = dataclasses.replace(R, clutter_los=False)
        rm0, rm1, rmc = RadioMap(lay, r0, seed), RadioMap(lay, r1, seed), RadioMap(lay, R, seed)
        f = (rm1.gain[:-1].astype(float) - rm0.gain[:-1])        # place-tied shadowing x its standard deviation
        geo = rm1.los[:-1]
        f_los.append(f[geo])
        f_nlos.append(f[~geo])
        xs = np.arange(-400.0, 400.0, 1.0)                      # along the middle east-west street
        ys = np.zeros_like(xs)
        z = (rm1.lookup(xs, ys).astype(float) - rm0.lookup(xs, ys)) / np.where(rm1.los_at(xs, ys), R.shadow_los_db,
                                                                               R.shadow_nlos_db)
        for lag, acc in ((10, c10), (20, c20)):
            acc.append(np.mean([np.corrcoef(z[:-lag, m], z[lag:, m])[0, 1] for m in range(z.shape[1])]))
        cc = np.corrcoef((f / np.where(geo, R.shadow_los_db, R.shadow_nlos_db)).T)
        cs.append(cc[~np.eye(len(cc), dtype=bool)].mean())
        px, py = _pixels(rmc)
        d2 = np.hypot(px[:, None] - lay.sites[None, :, 0], py[:, None] - lay.sites[None, :, 1])
        for lo, hi in edges:
            sel = geo & (d2 >= lo) & (d2 < hi)
            g, e = bins.get((lo, hi), (0.0, 0.0))
            bins[(lo, hi)] = (g + rmc.los[:-1][sel].sum(), e + pl.p_los(d2[sel], R.pathloss).sum())
            bins[(lo, hi, "n")] = bins.get((lo, hi, "n"), 0) + int(sel.sum())
    sl, sn = np.concatenate(f_los).std(), np.concatenate(f_nlos).std()
    rep.check("place-tied shadowing: standard deviation on LOS / NLOS links",
              abs(sl - R.shadow_los_db) < 0.4 and abs(sn - R.shadow_nlos_db) < 0.8,
              "%.2f dB (%.2f) / %.2f dB (%.2f)" % (sl, R.shadow_los_db, sn, R.shadow_nlos_db))
    a, b = float(np.mean(c10)), float(np.mean(c20))
    rep.check("place-tied shadowing: spatial correlation at 10 m and 20 m (decorrelation distance %g m)"
              % R.shadow_decorr_m, abs(a - math.exp(-1.0)) < 0.12 and b < 0.15,
              "%.2f (1/e = 0.37), %.2f" % (a, b))
    c = float(np.mean(cs))
    rep.check("place-tied shadowing: correlation between sites", abs(c - R.shadow_site_corr) < 0.15,
              "%.2f (%.2f)" % (c, R.shadow_site_corr))
    txt, ok = [], True
    for lo, hi in edges:
        g, e = bins[(lo, hi)]
        n = max(bins[(lo, hi, "n")], 1)
        txt.append("%d-%d m: %.2f (%.2f)" % (lo, hi, g / n, e / n))
        ok &= abs(g / n - e / n) < 0.08
    rep.check("spatially consistent LOS state: LOS share of links clear of buildings vs. TR 38.901 LOS probability",
              ok, "; ".join(txt))
    # time-varying component and L1 error, from the radio samples of a world
    d_all, n_all = [], []
    for seed in seeds:
        w = build_world(sc, seed)
        wq = dataclasses.replace(w, scenario=sc.with_overrides({"radio.time_var_db": 0.0, "radio.l1_error_db": 0.0}))
        for ch, cq in zip(RadioSource(w).chunks(), RadioSource(wq).chunks()):
            d_all.append((ch.rsrp - cq.rsrp)[::ch.mp])
            n_all.append(ch.l1 - ch.rsrp[::ch.mp])
    d = np.concatenate(d_all)
    n1 = np.concatenate(n_all)
    lag = int(round(R.time_var_tau_s / sc.protocol.l1_period_s))
    r = float(np.mean(d[:-lag] * d[lag:]) / d.var())
    rep.check("time-varying component: standard deviation and correlation after %g s" % R.time_var_tau_s,
              abs(d.std() - R.time_var_db) < 0.1 and abs(r - math.exp(-1.0)) < 0.06,
              "%.2f dB (%.2f), %.2f (1/e = 0.37)" % (d.std(), R.time_var_db, r))
    rep.check("L1 sample error: standard deviation and mean", abs(n1.std() - R.l1_error_db) < 0.02 and
              abs(n1.mean()) < 0.01, "%.3f dB (%.2f), %.4f dB" % (n1.std(), R.l1_error_db, n1.mean()))
    a200, a40 = l3_coefficient(4, 0.2), l3_coefficient(4, 0.04)
    rep.check("L3 filter (TS 38.331 5.5.3.2): a = 1/2^(k/4) = 0.5 at 200 ms for k = 4; five 40 ms samples equal one",
              abs(a200 - 0.5) < 1e-12 and abs((1 - a40) ** 5 - 0.5) < 1e-12, "a(40 ms) = %.4f" % a40)
