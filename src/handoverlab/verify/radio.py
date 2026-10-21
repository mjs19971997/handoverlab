# SPDX-License-Identifier: MIT
"""Checks of the radio model against the formulas of 3GPP TR 38.901.

``pathloss_checks``
    Path loss (UMi, UMa, RMa, InH), breakpoint distance and LOS probability against values
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

C0 = 3.0e8              # TR 38.901 Table 7.4.1-1 notes 1 and 5 (since 2.0.0)


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


def _hand_rma_los(d, fc, hb=35.0, hu=1.5, h=5.0):
    def pl1(d3):
        return (20 * math.log10(40 * math.pi * d3 * fc / 3) + min(0.03 * h ** 1.72, 10) * math.log10(d3)
                - min(0.044 * h ** 1.72, 14.77) + 0.002 * math.log10(h) * d3)
    d3 = math.hypot(d, hb - hu)
    dbp = 2 * math.pi * hb * hu * fc * 1e9 / C0
    d3bp = math.hypot(dbp, hb - hu)
    return pl1(d3) if d <= dbp else pl1(d3bp) + 40 * math.log10(d3 / d3bp)


def _hand_rma_nlos(d, fc, hb=35.0, hu=1.5, w=20.0, h=5.0):
    d3 = math.hypot(d, hb - hu)
    p = (161.04 - 7.1 * math.log10(w) + 7.5 * math.log10(h) - (24.37 - 3.7 * (h / hb) ** 2) * math.log10(hb)
         + (43.42 - 3.1 * math.log10(hb)) * (math.log10(d3) - 3) + 20 * math.log10(fc)
         - (3.2 * math.log10(11.75 * hu) ** 2 - 4.97))
    return max(_hand_rma_los(d, fc, hb, hu), p)


def _hand_inh_los(d, fc, hb=3.0, hu=1.0):
    return 32.4 + 17.3 * math.log10(math.hypot(d, hb - hu)) + 20 * math.log10(fc)


def _hand_inh_nlos(d, fc, hb=3.0, hu=1.0):
    d3 = math.hypot(d, hb - hu)
    return max(_hand_inh_los(d, fc, hb, hu), 38.3 * math.log10(d3) + 17.30 + 24.9 * math.log10(fc))


def pathloss_checks(rep) -> None:
    rep.section("pathloss", "path loss and LOS probability (TR 38.901 Tables 7.4.1-1, 7.4.2-1), by hand")
    cases = [  # name, model, los, d2d, fc, h_bs, published hand value or None
        ("UMi LOS  10 GHz, d2D 50 m, hBS 10 m, hUT 1.5 m (PL1)", "umi_street_canyon", True, 50.0, 10.0, 10.0, 88.208),
        ("UMi NLOS 10 GHz, d2D 50 m", "umi_street_canyon", False, 50.0, 10.0, 10.0, 103.892),
        ("UMi LOS  3.5 GHz, d2D 200 m (PL1, below d'BP 210.0 m)", "umi_street_canyon", True, 200.0, 3.5, 10.0, 91.611),
        # 1.x: 103.233
        ("UMi LOS  3.5 GHz, d2D 400 m (PL2, above d'BP)", "umi_street_canyon", True, 400.0, 3.5, 10.0, 103.239),
        ("UMi NLOS 28 GHz, d2D 120 m", "umi_street_canyon", False, 120.0, 28.0, 10.0, None),
        ("UMa LOS  3.5 GHz, d2D 100 m, hBS 25 m", "uma", True, 100.0, 3.5, 25.0, 83.138),
        ("UMa NLOS 3.5 GHz, d2D 100 m, hBS 25 m", "uma", False, 100.0, 3.5, 25.0, 103.038),
        ("UMa LOS  7 GHz, d2D 1500 m (PL2)", "uma", True, 1500.0, 7.0, 25.0, None),
        # since 1.7.0; reference values of this release, computed by hand from Table 7.4.1-1 (with c = 3.0e8 m/s
        # in the breakpoints since 2.0.0; the two values above and below that change carry their 1.x value)
        ("RMa LOS  0.7 GHz, d2D 500 m, hBS 35 m (PL1, below dBP 769.7 m)", "rma", True, 500.0, 0.7, 35.0, 84.633),
        ("RMa LOS  0.7 GHz, d2D 2000 m (PL2)", "rma", True, 2000.0, 0.7, 35.0, 105.4085),  # 1.x: 105.403
        ("RMa NLOS 0.7 GHz, d2D 500 m", "rma", False, 500.0, 0.7, 35.0, 104.843),
        ("RMa NLOS 3.5 GHz, d2D 1000 m", "rma", False, 1000.0, 3.5, 35.0, 130.424),
        ("InH LOS  4 GHz, d2D 10 m, hBS 3 m, hUT 1 m", "inh_office", True, 10.0, 4.0, 3.0, 61.889),
        ("InH NLOS 4 GHz, d2D 40 m", "inh_office", False, 40.0, 4.0, 3.0, 93.671),
    ]
    hand = {("umi_street_canyon", True): _hand_umi_los, ("umi_street_canyon", False): _hand_umi_nlos,
            ("uma", True): _hand_uma_los, ("uma", False): _hand_uma_nlos,
            ("rma", True): _hand_rma_los, ("rma", False): _hand_rma_nlos,
            ("inh_office", True): _hand_inh_los, ("inh_office", False): _hand_inh_nlos}
    for name, model, los, d, fc, hb, pub in cases:
        hu = 1.0 if model == "inh_office" else 1.5
        code = float(pl.path_loss(np.array([d]), np.array([los]), model, fc, hb, hu)[0])
        ref = hand[(model, los)](d, fc, hb, hu)
        ok = abs(code - ref) < 1e-9 and (pub is None or abs(code - pub) < 5e-4)
        table = "" if pub is None else ", table %.3f" % pub
        rep.check(name, ok, "code %.4f dB, by hand %.4f dB%s" % (code, ref, table))
    dbp = pl.breakpoint_distance(10.0, 10.0, 1.5)
    rep.check("breakpoint distance d'BP, 10 GHz, hBS 10 m, hUT 1.5 m", abs(dbp - 600.0) < 1e-3, "%.4f m" % dbp)
    dbp35 = pl.breakpoint_distance(3.5, 10.0, 1.5)
    rep.check("breakpoint distance d'BP, 3.5 GHz", abs(dbp35 - 210.0) < 1e-3, "%.4f m" % dbp35)
    a, b = pl.umi_los(np.array(dbp - 1e-7), 10.0), pl.umi_los(np.array(dbp + 1e-7), 10.0)
    rep.check("UMi LOS continuous at the breakpoint", abs(float(a) - float(b)) < 1e-4, "%.4f / %.4f dB" % (a, b))
    for model, dc, name in (("umi_street_canyon", 36.0, "UMi"), ("uma", 63.0, "UMa")):
        for d in (10.0, 50.0, 100.0, 300.0):
            ref = 1.0 if d <= 18.0 else 18.0 / d + math.exp(-d / dc) * (1.0 - 18.0 / d)
            code = float(pl.p_los(np.array(d), model))
            rep.check("%s LOS probability at %g m" % (name, d), abs(code - ref) < 1e-12, "%.4f" % code)
    dbp_r = pl.rma_breakpoint(0.7, 35.0, 1.5)
    rep.check("RMa breakpoint distance dBP = 2 pi hBS hUT fc / c, 0.7 GHz, 35 m / 1.5 m",
              abs(dbp_r - 769.690) < 1e-3, "%.4f m" % dbp_r)
    a, b = pl.rma_los(np.array(dbp_r - 1e-7), 0.7), pl.rma_los(np.array(dbp_r + 1e-7), 0.7)
    rep.check("RMa LOS continuous at the breakpoint", abs(float(a) - float(b)) < 1e-4, "%.4f / %.4f dB" % (a, b))
    for model, name, f in (("rma", "RMa", lambda d: 1.0 if d <= 10.0 else math.exp(-(d - 10.0) / 1000.0)),
                           ("inh_office", "InH mixed office",
                            lambda d: 1.0 if d <= 1.2 else (math.exp(-(d - 1.2) / 4.7) if d < 6.5
                                                            else 0.32 * math.exp(-(d - 6.5) / 32.6)))):
        for d in ((5.0, 500.0, 2000.0) if model == "rma" else (1.0, 4.0, 20.0)):
            code = float(pl.p_los(np.array(d), model))
            rep.check("%s LOS probability at %g m" % (name, d), abs(code - f(d)) < 1e-12, "%.4f" % code)
    # soft LOS state (TR 38.901 Eq. 7.6-18 and 7.6-19, since 1.7.0): power weight LOS_soft^2
    for z, fc, ref in ((0.1, 10.0, 0.7786628), (-0.2, 0.7, 0.0404275)):
        code = float(pl.soft_los_power_weight(z, fc))
        lam = 299792458.0 / (fc * 1e9)          # the wavelength (notes 1 and 5 set c = 3.0e8 only in the breakpoints)
        hand = (0.5 + math.atan(math.sqrt(20.0 / lam) * z) / math.pi) ** 2
        rep.check("soft LOS power weight, z = G + F(d) = %g, %g GHz" % (z, fc),
                  abs(code - hand) < 1e-12 and abs(code - ref) < 1e-6, "%.6f" % code)
    w = pl.soft_los_power_weight(np.array([-1e6, 0.0, 1e6]), 3.5)
    mixed = pl.mix_db(np.array([0.0, 0.5, 1.0]), -80.0, -100.0)
    rep.check("soft LOS: hard limits and the power mixture",
              abs(w[0]) < 1e-9 and abs(w[1] - 0.25) < 1e-12 and abs(w[2] - 1.0) < 1e-6
              and abs(mixed[0] + 100.0) < 1e-9 and abs(mixed[2] + 80.0) < 1e-9
              and abs(mixed[1] - 10 * math.log10(0.5e-8 + 0.5e-10)) < 1e-9,
              "%.4f / %.4f / %.4f dB" % tuple(mixed))
    d = np.linspace(10.0, 2000.0, 400)
    ok = True
    for fc in (3.5, 7.0, 10.0, 15.0, 28.0):
        for model, hb in (("umi_street_canyon", 10.0), ("uma", 25.0)):
            ok &= bool(np.all(pl.path_loss(d, False, model, fc, hb, 1.5) >= pl.path_loss(d, True, model, fc, hb, 1.5)))
    rep.check("NLOS loss >= LOS loss everywhere (UMi and UMa, 3.5-28 GHz, 10-2000 m)", ok)
    ok = all(bool(np.all(pl.path_loss(d, False, "rma", fc, 35.0, 1.5) >= pl.path_loss(d, True, "rma", fc, 35.0, 1.5)))
             for fc in (0.7, 3.5, 7.0, 28.0))
    di = np.linspace(1.0, 150.0, 300)
    ok &= all(bool(np.all(pl.path_loss(di, False, "inh_office", fc, 3.0, 1.0)
                          >= pl.path_loss(di, True, "inh_office", fc, 3.0, 1.0))) for fc in (2.0, 4.0, 28.0, 60.0))
    rep.check("NLOS loss >= LOS loss everywhere (RMa 0.7-28 GHz, 10-2000 m; InH 2-60 GHz, 1-150 m)", ok)
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
