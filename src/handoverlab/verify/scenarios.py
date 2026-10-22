# SPDX-License-Identifier: MIT
"""The scenario items of 2.3.0: ``handoverlab verify --only scenarios``.

Checks of the TR 37.885 urban macro card ``urban-macro-tr37885-4ghz``, the SMa model and card
``suburban-sma-7ghz`` (TR 38.901 V19.5.0) and the O2I building penetration loss of indoor users
(TR 38.901 clause 7.4.3.1).  The criteria were written down before the first run (code of the
release: PLAN_scenarios.md):

U1  the urban card has the values of TR 37.885 V15.3.0 / TR 36.885 V14.0.0 / TR 38.901 (exact);
U2  its sites form the 500 m hexagonal lattice (nearest neighbours 500 m +- 0.05 m), every street
    point has a site within the hexagon radius 500 / sqrt(3) m + 1 m, and the sites reach at least
    500 m beyond the grid on every side;
U3  with the sites above the rooftops the LOS share of the radio map (street points, sites within
    1000 m) differs by at most 0.02 from the mean UMa LOS probability at the same distances;
U4  the coupling gain to the strongest site (percentiles 5 to 95) agrees within 0.5 dB with an
    independent computation at the simulated positions: UMa written out again with h_E = 0.25 m,
    the LOS state drawn per link from the probability, Gaussian shadowing independent between sites;
S1  the SMa path loss and LOS probability equal a separate write-out (1e-9 dB, 1e-12) over a grid of
    distances, carriers, heights and vegetation; the LOS path loss is continuous at d_BP and the LOS
    probability is 1 up to 10 m and does not increase;
S2  the SMa card has the values of TR 38.901 V19.5.0 (exact);
S3  coupling gain of the users outdoors, as U4, within 0.5 dB;
S4  coupling gain of all users against a TR-exact reference that also models what the simulator
    abstracts for indoor users (LOS probability at d2D-out, O2I shadowing 8 dB), within 1.0 dB: the
    size of that abstraction;
O1  the O2I loss of every model: sample mean and standard deviation of 20000 users within four
    standard errors of the analytic moments;
O2  in a run, every link of an indoor user is lower by exactly its O2I loss (and without the car
    loss), every link of an outdoor user unchanged.

Result of the registered run (2.3.0): U1-U3, S1, S2, O1, O2 pass; U4 fails (the simulation 0.3-1.2 dB below the
independent computation around the median in every block of seeds: a lower LOS share near the sites, cause
open), S3 fails on sampling noise (sign changes between blocks of seeds; 40 seeds pooled: +0.1 .. +0.5 dB) and
S4 fails by 2.0 dB at the 95 % point (the size of the indoor abstraction).  The checks are kept as registered
and the group is optional.

TR 38.901 V19.5.0 prints no 7 GHz calibration result (clause 7.8.1 refers to R1-2506406), so the SMa
model is checked against the text of the TR, not against company results.
"""
from __future__ import annotations

import math
from types import SimpleNamespace
from typing import Dict, Tuple

import numpy as np

from ..channel import pathloss as pl
from ..channel.source import RadioSource
from ..scenarios import builtin_scenario
from ..seeds import streams
from ..world import build_world

URBAN, SMA = "urban-macro-tr37885-4ghz", "suburban-sma-7ghz"

#: values fixed by the texts: key -> (value, source)
TR_VALUES: Dict[str, Dict[str, Tuple[object, str]]] = {
    URBAN: {
        "layout.kind": ("street_grid", "TR 37.885 Annex A"), "layout.blocks": ((3, 3), "TR 37.885 Table A-1"),
        "layout.pitch_m": ((433.0, 250.0), "TR 37.885 Table A-1"),
        "radio.carrier_ghz": (4.0, "TR 37.885 Table 6.1.1-1"), "radio.bandwidth_mhz": (20.0, "TR 37.885 Table 6.1.1-1"),
        "radio.tx_power_dbm": (49.0, "TR 37.885 Table 6.1.1-1"),
        "radio.noise_figure_db": (9.0, "TR 37.885 Table 6.1.1-1"),
        "radio.bs_height_m": (25.0, "TR 37.885 Table 6.1.4-1"), "radio.ue_height_m": (1.6, "TR 37.885 clause 6.1.2"),
        "radio.pathloss": ("uma", "TR 37.885 Table 6.2.1-2"), "radio.building_los": (False, "TR 37.885 clause 6.2.1"),
        "radio.clutter_los": (True, "TR 37.885 clause 6.2.1"), "radio.env_height_m": (0.25, "TR 37.885 clause 6.2.1"),
        "radio.shadow_los_db": (4.0, "TR 38.901 Table 7.4.1-1"),
        "radio.shadow_nlos_db": (6.0, "TR 38.901 Table 7.4.1-1"),
        "radio.shadow_decorr_m": (50.0, "TR 38.901 Table 7.5-6 Part-1"),
        "radio.los_corr_m": (50.0, "TR 38.901 Table 7.6.3.1-2"),
        "mobility.profile": ("v60", "TR 37.885 clause 6.1.2 urban option A"),
    },
    SMA: {
        "layout.site_spacing_m": (1299.0, "TR 38.901 Table 7.2-5"),
        "layout.min_site_distance_m": (35.0, "TR 38.901 Table 7.2-5"),
        "radio.carrier_ghz": (7.0, "TR 38.901 Table 7.8-1A"), "radio.bandwidth_mhz": (20.0, "TR 38.901 Table 7.8-1A"),
        "radio.tx_power_dbm": (49.0, "TR 38.901 Table 7.8-1A"), "radio.noise_figure_db": (9.0, "TR 38.901 Table 7.8-1"),
        "radio.bs_height_m": (35.0, "TR 38.901 Table 7.2-5"), "radio.ue_height_m": (1.5, "TR 38.901 Table 7.2-5"),
        "radio.pathloss": ("sma", "TR 38.901 Table 7.4.1-1"), "radio.shadow_los_db": (4.0, "TR 38.901 Table 7.4.1-1"),
        "radio.shadow_los_far_db": (6.0, "TR 38.901 Table 7.4.1-1"),
        "radio.shadow_nlos_db": (8.0, "TR 38.901 Table 7.4.1-1"),
        "radio.shadow_decorr_m": (50.0, "TR 38.901 Table 7.5-6 Part-4"),
        "radio.los_corr_m": (50.0, "TR 38.901 Table 7.6.3.1-2"), "radio.vegetation": (0.0, "TR 38.901 Table 7.8-1A"),
        "radio.o2i_model": ("low_a", "TR 38.901 Table 7.8-1A"), "radio.o2i_d_in_max_m": (None, "TR 38.901 7.4.3.1"),
        "radio.penetration_db": (9.0, "TR 38.901 clause 7.4.3.2"),
        "radio.penetration_sd_db": (5.0, "TR 38.901 clause 7.4.3.2"),
    },
}


def _get(sc, key):
    obj = sc
    for p in key.split("."):
        obj = getattr(obj, p)
    return tuple(obj) if isinstance(obj, list) else obj


# ---------------------------------------------------------------------------
# formulas written out again from the text (TR 38.901 V19.5.0)
# ---------------------------------------------------------------------------
def sma_ref(los: bool, d2, fc, hbs, hut):
    """SMa path loss of Table 7.4.1-1 (h = 10 m, W = 10 m; note 5 breakpoint), written out for the check."""
    h, w = 10.0, 10.0
    d2 = np.asarray(d2, dtype=float)
    d3 = np.sqrt(d2 ** 2 + (hbs - hut) ** 2)
    if not los:
        return (161.04 - 7.1 * math.log10(w) + 7.5 * math.log10(h) - (24.37 - 3.7 * (h / hbs) ** 2) * math.log10(hbs)
                + (43.42 - 3.1 * math.log10(hbs)) * (np.log10(d3) - 3.0) + 20.0 * math.log10(fc)
                - (3.2 * math.log10(11.75 * hut) ** 2 - 4.97))

    def pl1(x):
        return (20.0 * np.log10(40.0 * math.pi * x * fc / 3.0) + min(0.03 * h ** 1.72, 10.0) * np.log10(x)
                - min(0.044 * h ** 1.72, 14.77) + 0.002 * math.log10(h) * x)
    dbp = 2.0 * math.pi * hbs * hut * fc * 1e9 / 3.0e8
    d3bp = math.sqrt(dbp ** 2 + (hbs - hut) ** 2)
    return np.where(d2 < dbp, pl1(d3), pl1(d3bp) + 40.0 * np.log10(d3 / d3bp))


def sma_plos_ref(d2, hbs, hut, veg):
    """SMa LOS probability of Table 7.4.2-1, written out for the check."""
    def inv_k(r, hx, clip=False):
        dh = max(hx - hut, 0.0) if clip else hx - hut
        return -(math.log(1.0 - r) / 30.0) * dh / (hbs - hut)
    d = np.asarray(d2, dtype=float)
    p = np.exp(-d * inv_k(0.02, 20.0)) * np.exp(-d * inv_k(0.18, 8.0, True)) * np.exp(-d * inv_k(veg, 15.0))
    return np.where(d <= 10.0, 1.0, p)


def uma_ref(los, d2, fc, hbs, hut, he):
    """UMa of Table 7.4.1-1 with one effective environment height ``he`` (TR 37.885 clause 6.2.1: 0.25 m)."""
    d3 = np.sqrt(d2 ** 2 + (hbs - hut) ** 2)
    dbp = 4.0 * (hbs - he) * (hut - he) * fc * 1e9 / 3.0e8
    pl_l = np.where(d2 <= dbp, 28.0 + 22.0 * np.log10(d3) + 20.0 * math.log10(fc),
                    28.0 + 40.0 * np.log10(d3) + 20.0 * math.log10(fc) - 9.0 * np.log10(dbp ** 2 + (hbs - hut) ** 2))
    pl_n = np.maximum(pl_l, 13.54 + 39.08 * np.log10(d3) + 20.0 * math.log10(fc) - 0.6 * (hut - 1.5))
    return np.where(los, pl_l, pl_n)


def uma_plos_ref(d2):
    d = np.maximum(np.asarray(d2, dtype=float), 1e-9)
    return np.where(d <= 18.0, 1.0, 18.0 / d + np.exp(-d / 63.0) * (1.0 - 18.0 / d))


def wall_ref(model: str, fc: float) -> Tuple[float, float]:
    """PL_tw and sigma_P of Table 7.4.3-2 with the materials of Table 7.4.3-1, written out for the check."""
    glass, irr, concrete, plywood = 2.0 + 0.2 * fc, 25.4 + 0.11 * fc, 5.0 + 4.0 * fc, 1.03 + 0.17 * fc
    if model == "low":
        return 5.0 - 10.0 * math.log10(0.3 * 10 ** (-glass / 10) + 0.7 * 10 ** (-concrete / 10)), 4.4
    if model == "high":
        return 5.0 - 10.0 * math.log10(0.7 * 10 ** (-irr / 10) + 0.3 * 10 ** (-concrete / 10)), 6.5
    return 5.0 - 10.0 * math.log10(0.3 * 10 ** (-glass / 10) + 0.7 * 10 ** (-plywood / 10)), 4.4


def o2i_moments(model: str, fc: float, din: str) -> Tuple[float, float]:
    """Analytic mean and standard deviation of the O2I loss (O1); ``din`` "25" (UMa/UMi) or "sma" (90 % / 10 %)."""
    parts = [(0.5, "low"), (0.5, "high")] if model == "mixed" else [(1.0, model)]
    sizes = [(1.0, 25.0)] if din == "25" else [(0.9, 10.0), (0.1, 25.0)]
    e_d = sum(w * a / 3.0 for w, a in sizes)                     # E[min(U1, U2)] = a / 3
    e_d2 = sum(w * a * a / 6.0 for w, a in sizes)                # E[min^2] = a^2 / 6
    var_in = 0.25 * (e_d2 - e_d ** 2)
    ms = [(w, wall_ref(m, fc)[0] + 0.5 * e_d, var_in + wall_ref(m, fc)[1] ** 2) for w, m in parts]
    mean = sum(w * m for w, m, _ in ms)
    var = sum(w * (v + m * m) for w, m, v in ms) - mean ** 2
    return mean, math.sqrt(var)


# ---------------------------------------------------------------------------
# coupling gain at the simulated positions
# ---------------------------------------------------------------------------
def _samples(sc, seeds, every_s: float = 1.0):
    """Simulated coupling gain to the strongest site [dB], positions, user index and indoor flag of every sample."""
    g, xs, ys, us, ind = [], [], [], [], []
    for seed in seeds:
        w = build_world(sc, seed)
        k_every = int(round(every_s / sc.protocol.step_s))
        indoor = w.indoor if w.indoor is not None else np.zeros(w.n_users, dtype=bool)
        for ch in RadioSource(w).chunks():
            ks = np.arange(ch.k0, ch.k0 + ch.n)
            sel = np.flatnonzero(ks % k_every == 0)
            if not len(sel):
                continue
            g.append((ch.rsrp[sel].max(axis=-1) - sc.radio.tx_power_dbm).ravel())
            xs.append(w.x[ks[sel]].ravel())
            ys.append(w.y[ks[sel]].ravel())
            u = np.tile(np.arange(w.n_users), len(sel))
            us.append(u + 100000 * seed)
            ind.append(indoor[u])
        lay = w.layout
    cat = np.concatenate
    return cat(g), cat(xs), cat(ys), cat(us), cat(ind), lay


def _reference(sc, lay, x, y, users, indoor, rng, exact_o2i: bool = False):
    """Independent coupling gain to the strongest site at the given positions (U4, S3, S4)."""
    R = sc.radio
    d2 = np.maximum(lay.distances(x, y), 10.0)
    n, m = d2.shape
    uid, inv = np.unique(users, return_inverse=True)
    if R.pathloss == "sma":
        d_in = np.zeros(n)
        loss_u = np.zeros(len(uid))
        if exact_o2i or indoor.any():
            # O2I per user: low-loss A wall, d2D-in from the residential (10 m) or commercial (25 m) building
            tw, sp = wall_ref(R.o2i_model, R.carrier_ghz)
            a = np.where(rng.random(len(uid)) < 0.9, 10.0, 25.0)
            din_u = np.minimum(rng.random(len(uid)), rng.random(len(uid))) * a
            loss_u = tw + 0.5 * din_u + sp * rng.standard_normal(len(uid))
            d_in = np.where(indoor, din_u[inv], 0.0)
        car_u = R.penetration_db + R.penetration_sd_db * rng.standard_normal(len(uid))
        pen = np.where(indoor, loss_u[inv], car_u[inv])
        d_out = np.maximum(d2 - d_in[:, None], 0.0) if exact_o2i else d2
        los = rng.random((n, m)) < sma_plos_ref(d_out, R.bs_height_m, R.ue_height_m, R.vegetation)
        pl_l = sma_ref(True, d2, R.carrier_ghz, R.bs_height_m, R.ue_height_m)
        pl_n = sma_ref(False, d2, R.carrier_ghz, R.bs_height_m, R.ue_height_m)
        dbp = 2.0 * math.pi * R.bs_height_m * R.ue_height_m * R.carrier_ghz * 1e9 / 3.0e8
        sd = np.where(los, np.where(d2 < dbp, R.shadow_los_db, R.shadow_los_far_db), R.shadow_nlos_db)
        if exact_o2i:
            sd = np.where(indoor[:, None], 8.0, sd)             # Table 7.5-6 Part-4: O2I shadow fading 8 dB
        pl_ = np.where(los, pl_l, pl_n)
    else:
        pen = np.zeros(n)
        los = rng.random((n, m)) < uma_plos_ref(d2)
        pl_ = uma_ref(los, d2, R.carrier_ghz, R.bs_height_m, R.ue_height_m, R.env_height_m)
        sd = np.where(los, R.shadow_los_db, R.shadow_nlos_db)
    g = R.bs_gain_db + R.ue_gain_db - pl_ + sd * rng.standard_normal((n, m)) - pen[:, None]
    return g.max(axis=1)


def _compare(rep, label, sim, ref, tol):
    q = np.arange(5, 100, 5)
    diff = np.percentile(sim, q) - np.percentile(ref, q)
    worst = int(np.argmax(np.abs(diff)))
    rep.check(label, bool(np.all(np.abs(diff) <= tol)),
              "largest difference %+.2f dB at the %d %% point; median %.1f dB (reference %.1f dB); %d samples"
              % (diff[worst], q[worst], np.median(sim), np.median(ref), len(sim)))


def scenarios_checks(rep, seeds=tuple(range(1, 11)), n_o2i: int = 20000) -> None:
    rep.section("scenarios", "2.3.0 scenario items: TR 37.885 urban macro card, SMa of TR 38.901 V19.5.0, O2I "
                             "building penetration (criteria fixed before the first run)")
    for name in (URBAN, SMA):
        sc = builtin_scenario(name)
        bad = ["%s = %r (%s: %r)" % (k, _get(sc, k), src, v) for k, (v, src) in TR_VALUES[name].items()
               if _get(sc, k) != v]
        g = sc.mobility.groups
        if name == SMA and not (g and len(g) == 2 and g[0].indoor and g[0].share == 0.8
                                and abs(g[0].v_min * 3.6 - 3.0) < 1e-9 and abs(g[1].v_min * 3.6 - 40.0) < 1e-9):
            bad.append("mobility.groups (TR 38.901 Table 7.2-5: 80 % indoor at 3 km/h, in car at 40 km/h)")
        rep.check("%s: values as in the TRs" % name, not bad,
                  "; ".join(bad) if bad else "%d values" % len(TR_VALUES[name]))
    # U2
    sc = builtin_scenario(URBAN)
    w = build_world(sc.with_overrides({"run.duration_s": 2.0, "run.warmup_s": 0.0, "mobility.users": 2}), 1)
    lay, rmap = w.layout, w.radio_map
    s = lay.sites
    dd = np.hypot(s[:, None, 0] - s[None, :, 0], s[:, None, 1] - s[None, :, 1])
    dd[np.arange(len(s)), np.arange(len(s))] = np.inf
    nn = dd.min(axis=1)
    gy, gx = np.nonzero(rmap.idx < rmap.n_pix)
    px, py = rmap.x0 + gx * rmap.res, rmap.y0 + gy * rmap.res
    dp = lay.distances(px, py)
    far = float(dp.min(axis=1).max())
    margin = min(lay.xmin - s[:, 0].min(), s[:, 0].max() - lay.xmax, lay.ymin - s[:, 1].min(), s[:, 1].max() - lay.ymax)
    rep.check("%s: hexagonal 500 m lattice around the grid" % URBAN,
              bool(np.all(np.abs(nn - 500.0) <= 0.05) and far <= 500.0 / math.sqrt(3.0) + 1.0 and margin >= 500.0),
              "%d sites, nearest neighbours %.3f-%.3f m, farthest street point %.1f m from a site, sites %.0f m "
              "beyond the grid" % (len(s), nn.min(), nn.max(), far, margin))
    # U3
    near = dp <= 1000.0
    los = rmap.los[rmap.idx[gy, gx]]
    share, want = float(los[near].mean()), float(uma_plos_ref(dp[near]).mean())
    rep.check("%s: LOS share of the map equals the UMa LOS probability (sites above the rooftops)" % URBAN,
              abs(share - want) <= 0.02, "LOS share %.4f, mean probability %.4f over %d links"
              % (share, want, int(near.sum())))
    # U4
    ab = sc.with_overrides({"radio.place_share": 0.0, "run.duration_s": 30.0, "run.warmup_s": 0.0,
                            "mobility.users": 200})
    sim, x, y, u, ind, lay = _samples(ab, seeds)
    ref = _reference(ab, lay, x, y, u, ind, np.random.default_rng(11))
    _compare(rep, "%s: coupling gain to the strongest site, percentiles 5-95 within 0.5 dB" % URBAN, sim, ref, 0.5)
    # S1
    d = np.concatenate([np.linspace(10.0, 300.0, 59), np.geomspace(300.0, 5000.0, 60)])
    err_pl, err_p, cont = 0.0, 0.0, 0.0
    mono = True
    for fc in (0.5, 3.5, 7.0, 15.0, 30.0, 37.0):
        for hbs in (25.0, 35.0):
            for hut in (1.5, 4.5, 13.5):
                for los_ in (True, False):
                    code = pl.path_loss(d, los_, "sma", fc, hbs, hut)
                    err_pl = max(err_pl, float(np.abs(code - sma_ref(los_, d, fc, hbs, hut)).max()))
                dbp = pl.rma_breakpoint(fc, hbs, hut)
                a, b = pl.sma_los(np.array(dbp - 1e-7), fc, hbs, hut), pl.sma_los(np.array(dbp + 1e-7), fc, hbs, hut)
                cont = max(cont, abs(float(a) - float(b)))
                for veg in (0.0, 0.1, 0.2):
                    dl = np.concatenate([[1.0, 5.0, 10.0], d])
                    p = pl.p_los(dl, "sma", sma=(hbs, hut, veg))
                    err_p = max(err_p, float(np.abs(p - sma_plos_ref(dl, hbs, hut, veg)).max()))
                    mono &= bool(np.all(p[:3] == 1.0) and np.all(np.diff(p) <= 0.0))
    rep.check("SMa path loss and LOS probability equal the formulas of TR 38.901 V19.5.0 Tables 7.4.1-1 / 7.4.2-1",
              err_pl < 1e-9 and err_p < 1e-12 and cont < 1e-4 and mono,
              "largest difference %.1e dB / %.1e; step at d_BP %.1e dB; probability 1 up to 10 m and "
              "non-increasing: %s" % (err_pl, err_p, cont, mono))
    # S3, S4
    sc = builtin_scenario(SMA)
    ab = sc.with_overrides({"radio.place_share": 0.0, "radio.time_var_db": 0.0, "run.duration_s": 30.0,
                            "run.warmup_s": 0.0, "mobility.users": 200})
    sim, x, y, u, ind, lay = _samples(ab, seeds)
    out = ~ind
    ref = _reference(ab, lay, x[out], y[out], u[out], ind[out], np.random.default_rng(12))
    _compare(rep, "%s: coupling gain of the users outdoors, percentiles 5-95 within 0.5 dB" % SMA, sim[out], ref, 0.5)
    ref = _reference(ab, lay, x, y, u, ind, np.random.default_rng(13), exact_o2i=True)
    _compare(rep, "%s: all users against the TR-exact O2I reference (LOS at d2D-out, O2I shadowing 8 dB), "
                  "percentiles 5-95 within 1.0 dB" % SMA, sim, ref, 1.0)
    # O1
    worst = (0.0, "")
    ok = True
    for model, path, din in (("low", "uma", "25"), ("high", "uma", "25"), ("mixed", "umi_street_canyon", "25"),
                             ("low", "sma", "sma"), ("high", "sma", "sma"), ("low_a", "sma", "sma")):
        for fc in (4.0, 7.0, 28.0):
            r = SimpleNamespace(o2i_model=model, carrier_ghz=fc, pathloss=path, o2i_d_in_max_m=None)
            v = pl.o2i_building_loss(np.random.default_rng([7, int(fc), len(model)]), np.ones(n_o2i, bool), r)
            mean, sd = o2i_moments(model, fc, din)
            zm = abs(v.mean() - mean) / (sd / math.sqrt(n_o2i))
            zs = abs(v.std() - sd) / (sd / math.sqrt(2.0 * n_o2i))
            ok &= zm <= 4.0 and zs <= 4.0
            if max(zm, zs) > worst[0]:
                worst = (max(zm, zs), "%s %s %g GHz" % (model, path, fc))
    rep.check("O2I loss of every model (TR 38.901 Eq. 7.4-2/7.4-3, Tables 7.4.3-1/-2): mean and standard deviation "
              "within 4 standard errors", ok, "largest %.2f standard errors (%s), %d users each"
              % (worst[0], worst[1], n_o2i))
    # O2
    base = sc.with_overrides({"run.duration_s": 2.0, "run.warmup_s": 0.0, "mobility.users": 40})
    flat = base.with_overrides({"mobility.groups": [dict(share=g.share, v_min=g.v_min, v_max=g.v_max,
                                                         lateral_m=list(g.lateral_m)) for g in base.mobility.groups]})
    w1, w0 = build_world(base, 4), build_world(flat, 4)
    r1, r0 = next(RadioSource(w1).chunks()).rsrp, next(RadioSource(w0).chunks()).rsrp
    R = base.radio
    car = R.penetration_db + R.penetration_sd_db * streams(4, "penetration", 1)[0].standard_normal(w1.n_users)
    o2i = pl.o2i_building_loss(streams(4, "o2i", 1)[0], w1.indoor, R)
    want = np.where(w1.indoor, car - o2i, 0.0)[None, :, None]
    err = float(np.abs((r1 - r0) - want).max())
    rep.check("O2I loss on every link of an indoor user, outdoor users unchanged", err < 1e-9,
              "largest difference %.1e dB; %d of %d users indoors" % (err, int(w1.indoor.sum()), w1.n_users))
