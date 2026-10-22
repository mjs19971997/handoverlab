# SPDX-License-Identifier: MIT
"""Large-scale calibration of the radio model against 3GPP (TR 38.901 clause 7.8.1), since 1.8.0.

TR 38.901 clause 7.8.1 defines a drop-based calibration (Table 7.8-1): UMa, UMi-Street Canyon and
the indoor office (open office), three sectors per site with the antenna element of Table 7.3-1 in
a vertical array of ten elements tilted by DFT weights (Eq. 7.3-1), no fast fading, users attached
to the sector with the highest received power, and two metrics, the coupling loss to the serving
sector and the geometry (wideband SINR with and without noise).  21 companies reported their CDFs
in the 3GPP contribution R1-165974 (RAN1 #85, "E-mail discussion summary of the large scale
calibration"); ``data/r1_165974.csv`` holds their mean and their range at every percentile.

This module reproduces the drop with the propagation models of HandoverLab (the formulas of
TR 38.901 Tables 7.4.1-1 and 7.4.2-1, written here for per-link user heights and, for UMa, the
random effective environment height of note 1), the deployment of Tables 7.2-1 and 7.2-2, the O2I
building penetration loss of clause 7.4.3.1 (50 % low loss, 50 % high loss) and geographical
wrap-around of the 19-site layouts, and compares the CDFs with the 3GPP results.

Versions: the formulas are those of TR 38.901 V19.5.0, except the IRR-glass loss of Table 7.4.3-1.  The
companies of R1-165974 (May 2016) worked with TR 38.900 V14.0.0, before the Release 19 change of that value;
the calibration keeps the pre-Release-19 IRR-glass loss 23 + 0.3 f dB (the value of TR 38.901 V17.0.0,
:data:`IRR_GLASS_R1_165974`), while V19.5.0 has 25.4 + 0.11 f dB (Table 7.4.3-1 note 2: updated in the
Release 19 study on 7-24 GHz; :data:`IRR_GLASS_V19`, which :func:`o2i_loss_db` takes on request).  With the
V19.5.0 value the 30 GHz cases leave the company range, the 6 GHz cases do not.  It checks the
radio model of HandoverLab -- path loss, LOS probability, shadowing, penetration loss -- with the
deployment and antenna that 3GPP fixed for calibration; the handover engine itself uses its own
antenna abstraction (``radio.bs_gain_db``) and is not part of this check.

7 GHz (since 2.4.0): TR 38.901 V19.5.0 Table 7.8-1A adds UMa, UMi-Street Canyon and SMa (ISD 1299 m and
1732 m) at 7 GHz, and clause 7.8.1 asks for UMa and UMi at 6 GHz again with the updated channel model.  The
companies reported these CDFs in R1-2506406 (RAN1 #122, "Calibration Results for 7 - 24 GHz SI", workbook
``Calibration_LS_v35``, based on TR 38.901 V19.0.0); ``data/r1_2506406.csv`` holds their mean and range.  These
cases use the IRR-glass loss of Release 19 (:data:`IRR_GLASS_V19`).  SMa follows Tables 7.2-5 and 7.8-1A: 35 m
sites with a mechanical downtilt (95 deg for ISD 1299 m, 92 deg for 1732 m; the element and the array are
rotated, Eqs. 7.1-7 and 7.1-8, without electrical tilt), 20 % of the users outdoors in cars (car penetration
loss of clause 7.4.3.2, non-metallic windows), 80 % indoors (90 % in residential buildings with two floors,
10 % in commercial buildings with five floors, uniform over the floors) with the low-loss A model, the SMa path
loss, LOS probability (no vegetation) and shadowing of HandoverLab, and an O2I shadowing of 8 dB (Table 7.5-6
Part-4).
"""
from __future__ import annotations

import csv
import math
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..channel import pathloss as _pl
from ..channel.antenna import element_gain_db  # Table 7.3-1, shared with the beam model

C0 = 3.0e8                # TR 38.901 Table 7.4.1-1 notes 1 and 5 (since 2.0.0; 1.x: 299792458)
_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DATA = os.path.join(_DATA_DIR, "r1_165974.csv")
DATA_R1_2506406 = os.path.join(_DATA_DIR, "r1_2506406.csv")     # since 2.4.0
PERCENTILES = tuple(range(5, 100, 5))


@dataclass(frozen=True)
class CalScenario:
    """One calibration case of TR 38.901 Table 7.8-1 (or, since 2.4.0, Table 7.8-1A)."""
    name: str          # "UMa", "UMi", "Indoor" or (since 2.4.0) "SMa"
    fc_ghz: float
    isd_m: float = 0.0             # SMa only: 1299 or 1732 m (Table 7.8-1A)
    reference: str = "R1-165974"   # or "R1-2506406" (since 2.4.0)

    @property
    def key(self) -> str:
        """Sheet name of the reference, e.g. ``UMa-6GHz`` or ``SMa-7GHz-1299m``."""
        k = "%s-%dGHz" % (self.name, round(self.fc_ghz))
        return k + "-%dm" % round(self.isd_m) if self.name == "SMa" else k

    @property
    def tx_power_dbm(self) -> float:
        """Table 7.8-1: 44 dBm UMi, 49 dBm UMa at 6 GHz (also used at 7 GHz); 35 dBm at 30 and 70 GHz; 24 dBm
        indoor.  Table 7.8-1A: 49 dBm SMa."""
        if self.name == "Indoor":
            return 24.0
        if self.fc_ghz < 10.0:
            return 49.0 if self.name in ("UMa", "SMa") else 44.0
        return 35.0

    @property
    def irr_glass(self) -> Tuple[float, float]:
        """IRR-glass loss of the reference: before Release 19 for R1-165974, Release 19 for R1-2506406."""
        return IRR_GLASS_V19 if self.reference == "R1-2506406" else IRR_GLASS_R1_165974

    @property
    def bandwidth_hz(self) -> float:
        """Table 7.8-1: 20 MHz at 6 GHz, 100 MHz at 30 and 70 GHz."""
        return 20e6 if self.fc_ghz < 10.0 else 100e6


UT_NOISE_FIGURE_DB = 9.0          # Table 7.8-1
TILT_DEG = {"UMa": 102.0, "UMi": 102.0, "Indoor": 110.0}
SECTORS_DEG = (30.0, 150.0, 270.0)
N_ELEMENTS = 10                   # (M, N, P) = (10, 1, 1), d_V = 0.5 lambda
#: SMa (Table 7.8-1A): mechanical downtilt [deg, zenith convention] per ISD [m]
SMA_MECH_TILT_DEG = {1299.0: 95.0, 1732.0: 92.0}


# ---------------------------------------------------------------------------
# antenna (Table 7.3-1 and Eq. 7.3-1)
# ---------------------------------------------------------------------------
def array_gain_db(theta_deg, tilt_deg: float, m: int = N_ELEMENTS):
    """Gain of the vertical array with the weights of Eq. 7.3-1 (d_V = lambda / 2), relative to one element."""
    psi = math.pi * (np.cos(np.radians(theta_deg)) - math.cos(math.radians(tilt_deg)))
    k = np.arange(m)
    af = np.abs(np.exp(1j * np.multiply.outer(psi, k)).sum(-1)) ** 2 / m
    return 10.0 * np.log10(np.maximum(af, 1e-30))


def gcs_to_lcs_deg(theta_deg, phi_deg, bearing_deg: float, downtilt_deg: float):
    """Zenith and azimuth angles in the LCS of an antenna with bearing alpha and downtilt beta (slant 0) [deg].

    Eqs. 7.1-7 and 7.1-8 of TR 38.901 with gamma = 0:
    theta' = arccos(cos beta cos theta + sin beta cos(phi - alpha) sin theta),
    phi' = arg(cos beta sin theta cos(phi - alpha) - sin beta cos theta + j sin(phi - alpha) sin theta).
    """
    t, b = np.radians(theta_deg), math.radians(downtilt_deg)
    p = np.radians(np.asarray(phi_deg) - bearing_deg)
    ct = np.clip(math.cos(b) * np.cos(t) + math.sin(b) * np.cos(p) * np.sin(t), -1.0, 1.0)
    re = math.cos(b) * np.sin(t) * np.cos(p) - math.sin(b) * np.cos(t)
    return np.degrees(np.arccos(ct)), np.degrees(np.arctan2(np.sin(p) * np.sin(t), re))


# ---------------------------------------------------------------------------
# propagation (Tables 7.4.1-1 and 7.4.2-1, per-link heights)
# ---------------------------------------------------------------------------
def _uma_los(d2, d3, fc, hbs, hut, he):
    dbp = 4.0 * (hbs - he) * (hut - he) * fc * 1e9 / C0
    pl1 = 28.0 + 22.0 * np.log10(d3) + 20.0 * math.log10(fc)
    pl2 = 28.0 + 40.0 * np.log10(d3) + 20.0 * math.log10(fc) - 9.0 * np.log10(dbp ** 2 + (hbs - hut) ** 2)
    return np.where(d2 <= dbp, pl1, pl2)


def _umi_los(d2, d3, fc, hbs, hut):
    dbp = 4.0 * (hbs - 1.0) * (hut - 1.0) * fc * 1e9 / C0
    pl1 = 32.4 + 21.0 * np.log10(d3) + 20.0 * math.log10(fc)
    pl2 = 32.4 + 40.0 * np.log10(d3) + 20.0 * math.log10(fc) - 9.5 * np.log10(dbp ** 2 + (hbs - hut) ** 2)
    return np.where(d2 <= dbp, pl1, pl2)


def pathloss_db(name: str, los, d2, d3, fc, hbs, hut, he=1.0):
    """Path loss of Table 7.4.1-1 for UMa (with effective height ``he``), UMi and InH-Office."""
    if name == "UMa":
        pl_l = _uma_los(d2, d3, fc, hbs, hut, he)
        pl_n = np.maximum(pl_l, 13.54 + 39.08 * np.log10(d3) + 20.0 * math.log10(fc) - 0.6 * (hut - 1.5))
    elif name == "UMi":
        pl_l = _umi_los(d2, d3, fc, hbs, hut)
        pl_n = np.maximum(pl_l, 35.3 * np.log10(d3) + 22.4 + 21.3 * math.log10(fc) - 0.3 * (hut - 1.5))
    else:
        pl_l = 32.4 + 17.3 * np.log10(d3) + 20.0 * math.log10(fc)
        pl_n = np.maximum(pl_l, 38.3 * np.log10(d3) + 17.30 + 24.9 * math.log10(fc))
    return np.where(los, pl_l, pl_n)


def p_los(name: str, d2out, hut):
    """LOS probability of Table 7.4.2-1: UMa (with C'(h_UT)), UMi, indoor open office."""
    d = np.maximum(np.asarray(d2out, dtype=float), 1e-9)
    if name == "Indoor":
        return np.where(d <= 5.0, 1.0, np.where(d <= 49.0, np.exp(-(d - 5.0) / 70.8),
                                                 0.54 * np.exp(-(d - 49.0) / 211.7)))
    dc = 63.0 if name == "UMa" else 36.0
    base = np.where(d <= 18.0, 1.0, 18.0 / d + np.exp(-d / dc) * (1.0 - 18.0 / d))
    if name != "UMa":
        return base
    c = np.where(hut <= 13.0, 0.0, (np.clip(hut, 13.0, 23.0) - 13.0) / 10.0) ** 1.5
    return np.where(d <= 18.0, 1.0, base * (1.0 + c * 1.25 * (d / 100.0) ** 3 * np.exp(-d / 150.0)))


def uma_effective_height(rng, d2, hut):
    """h_E of note 1 of Table 7.4.1-1.

    1 m with probability 1 / (1 + C(d2D, h_UT)), otherwise uniform over 12, 15, ..., h_UT - 1.5 m.
    """
    g = np.where(d2 <= 18.0, 0.0, 1.25 * (d2 / 100.0) ** 3 * np.exp(-d2 / 150.0))
    c = np.where(hut < 13.0, 0.0, ((np.clip(hut, 13.0, 23.0) - 13.0) / 10.0) ** 1.5 * g)
    he = np.ones(np.shape(d2))
    pick = rng.random(np.shape(d2)) >= 1.0 / (1.0 + c)
    n = np.floor((hut - 1.5 - 12.0) / 3.0).astype(int) + 1         # number of values 12, 15, ..., h_UT - 1.5
    choice = 12.0 + 3.0 * np.floor(rng.random(np.shape(d2)) * np.maximum(n, 1))
    return np.where(pick & (n >= 1), choice, he)


#: IRR-glass loss a + b f [dB] of TR 38.901 V17.0.0, before the Release 19 change (the calibration of R1-165974)
IRR_GLASS_R1_165974 = (23.0, 0.3)
#: IRR-glass loss of TR 38.901 V19.5.0 Table 7.4.3-1 (note 2: updated in Release 19)
IRR_GLASS_V19 = (25.4, 0.11)


def o2i_loss_db(rng, n: int, fc: float, irr_glass: Tuple[float, float] = IRR_GLASS_R1_165974
                ) -> Tuple[np.ndarray, np.ndarray]:
    """Building penetration loss of clause 7.4.3.1 for ``n`` indoor users (half low loss, half high loss).

    Returns the loss PL_tw + PL_in + N(0, sigma_P) [dB] and d2D-in [m] (minimum of two uniform(0, 25 m)).
    ``irr_glass`` = (a, b) of the IRR-glass loss a + b f (default: the value of R1-165974, see the module text).
    """
    lg, lc, lirr = 2.0 + 0.2 * fc, 5.0 + 4.0 * fc, irr_glass[0] + irr_glass[1] * fc
    low = rng.random(n) < 0.5
    tw_low = 5.0 - 10.0 * math.log10(0.3 * 10 ** (-lg / 10.0) + 0.7 * 10 ** (-lc / 10.0))
    tw_high = 5.0 - 10.0 * math.log10(0.7 * 10 ** (-lirr / 10.0) + 0.3 * 10 ** (-lc / 10.0))
    d_in = np.minimum(rng.uniform(0.0, 25.0, n), rng.uniform(0.0, 25.0, n))
    sd = np.where(low, 4.4, 6.5)
    return np.where(low, tw_low, tw_high) + 0.5 * d_in + sd * rng.standard_normal(n), d_in


# ---------------------------------------------------------------------------
# deployment
# ---------------------------------------------------------------------------
def hex_sites(isd: float) -> np.ndarray:
    """The 19 sites of a two-ring hexagonal layout (Table 7.2-1), centre site at the origin."""
    pts = [(i + j / 2.0, j * math.sqrt(3.0) / 2.0) for i in range(-2, 3) for j in range(-2, 3)
           if max(abs(i), abs(j), abs(i + j)) <= 2]
    return isd * np.array(pts)


def wrap_offsets(isd: float) -> np.ndarray:
    """Translations of the 19-site cluster for geographical wrap-around (the cluster and its six images)."""
    v = isd * np.array([4.0, math.sqrt(3.0)])
    rot = [np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
           for a in np.radians(np.arange(0, 360, 60))]
    return np.vstack([[0.0, 0.0]] + [r @ v for r in rot])


def _drop_hex(rng, sites, isd, min_dist):
    """Users uniform over the hexagonal cells of the sites; user ``u`` at least ``min_dist[u]`` from every
    (wrapped) site.  Points outside the cells or too close are drawn again."""
    r = isd / 2.0
    n = len(min_dist)
    out = np.empty((n, 2))
    todo = np.arange(n)
    off = wrap_offsets(isd)
    allsites = (sites[None, :, :] + off[:, None, :]).reshape(-1, 2)
    while len(todo):
        k = rng.integers(len(sites), size=len(todo))
        p = rng.uniform(-isd / math.sqrt(3.0), isd / math.sqrt(3.0), (len(todo), 2))
        ok = np.ones(len(todo), dtype=bool)
        for a in np.radians((0.0, 60.0, 120.0)):
            ok &= np.abs(p[:, 0] * math.cos(a) + p[:, 1] * math.sin(a)) <= r
        p = p + sites[k]
        dmin = np.min(np.hypot(p[:, None, 0] - allsites[None, :, 0], p[:, None, 1] - allsites[None, :, 1]), axis=1)
        ok &= dmin >= min_dist[todo]
        out[todo[ok]] = p[ok]
        todo = todo[~ok]
    return out


def indoor_sites() -> np.ndarray:
    """The 12 ceiling sites of TR 38.901 Figure 7.2-1 in a 120 m x 50 m hall centred on the origin."""
    gx, gy = np.meshgrid(np.arange(-50.0, 51.0, 20.0), (-10.0, 10.0))
    return np.c_[gx.ravel(), gy.ravel()]


# ---------------------------------------------------------------------------
# one calibration run
# ---------------------------------------------------------------------------
def simulate_drops(sc: CalScenario, n_users: int = 6000, seed: int = 1,
                   irr_glass: Optional[Tuple[float, float]] = None) -> Dict[str, np.ndarray]:
    """Coupling gain (= -coupling loss) to the serving sector, SINR and SIR [dB] of ``n_users`` dropped users
    (``irr_glass``: see :func:`o2i_loss_db`; unset: the value of the case's reference, ``sc.irr_glass``)."""
    if sc.name == "SMa":
        return _simulate_sma(sc, n_users, seed)
    irr_glass = sc.irr_glass if irr_glass is None else irr_glass
    rng = np.random.default_rng([seed, round(sc.fc_ghz * 10), {"UMa": 1, "UMi": 2, "Indoor": 3}[sc.name]])
    fc = sc.fc_ghz
    if sc.name == "Indoor":
        sites, hbs = indoor_sites(), 3.0
        ux = np.c_[rng.uniform(-60.0, 60.0, n_users), rng.uniform(-25.0, 25.0, n_users)]
        hut = np.full(n_users, 1.0)
        indoor = np.zeros(n_users, dtype=bool)
        offsets = np.zeros((1, 2))
    else:
        isd, hbs, dmin = (500.0, 25.0, 35.0) if sc.name == "UMa" else (200.0, 10.0, 10.0)
        sites = hex_sites(isd)
        indoor = rng.random(n_users) < 0.8                       # Table 7.2-1: 80 % indoor
        nfl = rng.integers(4, 9, n_users)                         # Table 7.2-1 (as 3D-UMa of TR 36.873); ITU-R M.2412-0
        # Table 5b: h_UT = 3 (n_fl - 1) + 1.5 m, N_fl ~ uniform(4, 8),
        hut = np.where(indoor, 3.0 * (np.floor(rng.random(n_users) * nfl)) + 1.5, 1.5)  # n_fl ~ uniform(1, N_fl)
        offsets = wrap_offsets(isd)
    S = len(sites)
    pen = np.zeros(n_users)
    d_in = np.zeros(n_users)
    if indoor.any():
        pen[indoor], d_in[indoor] = o2i_loss_db(rng, int(indoor.sum()), fc, irr_glass)
    if sc.name != "Indoor":                                       # the minimum distance holds for d2D-out
        ux = _drop_hex(rng, sites, isd, dmin + d_in)
    # nearest image of every site (geographical wrap-around)
    dx = ux[:, None, None, 0] - (sites[None, None, :, 0] + offsets[None, :, None, 0])
    dy = ux[:, None, None, 1] - (sites[None, None, :, 1] + offsets[None, :, None, 1])
    dd = np.hypot(dx, dy)
    k = np.argmin(dd, axis=1)
    iu, js = np.meshgrid(np.arange(n_users), np.arange(S), indexing="ij")
    d2 = np.maximum(dd[iu, k, js], 1e-3)
    ex, ey = dx[iu, k, js], dy[iu, k, js]
    h = hut[:, None]
    d3 = np.sqrt(d2 ** 2 + (hbs - h) ** 2)
    d2out = np.maximum(d2 - d_in[:, None], 0.0)
    los = rng.random((n_users, S)) < p_los(sc.name, d2out, h)
    he = uma_effective_height(rng, d2, np.broadcast_to(h, d2.shape)) if sc.name == "UMa" else 1.0
    pl = pathloss_db(sc.name, los, d2, d3, fc, hbs, h, he)
    if sc.name == "Indoor":
        sf_sd = np.where(los, 3.0, 8.03)
    else:
        sf_sd = np.where(indoor[:, None], 7.0, np.where(los, 4.0, 6.0 if sc.name == "UMa" else 7.82))
    loss = pl + sf_sd * rng.standard_normal((n_users, S)) + pen[:, None]
    # antenna gain of the three sectors of every site towards the user (LOS angles)
    theta = 90.0 + np.degrees(np.arctan2(hbs - h, d2))
    phi = np.degrees(np.arctan2(ey, ex))
    gains = []
    for b in SECTORS_DEG:
        rel = (phi - b + 180.0) % 360.0 - 180.0
        gains.append(element_gain_db(theta, rel) + array_gain_db(theta, TILT_DEG[sc.name]))
    return _serving_metrics(sc, np.concatenate([g - loss for g in gains], axis=1), n_users)


def _serving_metrics(sc: CalScenario, cg, n_users: int) -> Dict[str, np.ndarray]:
    """Metrics of Table 7.8-1 from the coupling gain ``cg`` (users x sectors) [dB]."""
    p = 10.0 ** ((sc.tx_power_dbm + cg) / 10.0)                   # received power [mW]
    srv = np.argmax(cg, axis=1)                                   # handover margin 0 dB
    ps = p[np.arange(n_users), srv]
    interf = p.sum(axis=1) - ps
    noise = 10.0 ** ((-174.0 + 10.0 * math.log10(sc.bandwidth_hz) + UT_NOISE_FIGURE_DB) / 10.0)
    return dict(coupling_gain_db=cg[np.arange(n_users), srv], sinr_db=10.0 * np.log10(ps / (interf + noise)),
                sir_db=10.0 * np.log10(ps / interf))


# ---------------------------------------------------------------------------
# SMa at 7 GHz (Tables 7.2-5 and 7.8-1A; since 2.4.0)
# ---------------------------------------------------------------------------
SMA_BS_HEIGHT_M = 35.0            # Table 7.2-5
SMA_MIN_DISTANCE_M = 35.0         # Table 7.2-5 (2D)
SMA_OUTDOOR_SHARE = 0.2           # Table 7.8-1A: 20 % of the UTs outdoors (in cars, Table 7.2-5)
SMA_FLOORS = (2, 5)               # Table 7.2-5: up to two floors (residential), five (commercial)
SMA_O2I_SHADOW_DB = 8.0           # Table 7.5-6 Part-4, O2I column
CAR_LOSS_DB = (9.0, 5.0)          # clause 7.4.3.2: mu = 9 dB (non-metallic windows), sigma_P = 5 dB


def sma_users(rng, n: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Indoor flag, residential flag and height [m] of ``n`` SMa users (Tables 7.8-1A and 7.2-5).

    80 % indoors; 90 % of them in residential buildings (1.5 or 4.5 m), 10 % in commercial buildings
    (1.5, 4.5, ..., 13.5 m), uniform over the floors of the building type; outdoor users at 1.5 m.
    """
    indoor = rng.random(n) >= SMA_OUTDOOR_SHARE
    resid = rng.random(n) < _pl.SMA_RESIDENTIAL_SHARE
    floor = np.floor(rng.random(n) * np.where(resid, SMA_FLOORS[0], SMA_FLOORS[1]))
    return indoor, resid, np.where(indoor, 3.0 * floor + 1.5, 1.5)


def sma_penetration_db(rng, indoor, resid, fc: float) -> Tuple[np.ndarray, np.ndarray]:
    """Penetration loss [dB] and d2D-in [m] of SMa users: the low-loss A model of Table 7.4.3-2 indoors
    (d2D-in = minimum of two uniform variables up to 10 m residential, 25 m commercial), the car penetration
    loss N(9 dB, 5 dB) of clause 7.4.3.2 outdoors."""
    n = len(indoor)
    a = np.where(resid, 10.0, 25.0)
    d_in = np.where(indoor, np.minimum(rng.random(n), rng.random(n)) * a, 0.0)
    z_bldg, z_car = rng.standard_normal(n), rng.standard_normal(n)
    bldg = _pl.o2i_wall_loss_db("low_a", fc) + 0.5 * d_in + _pl.O2I_WALLS["low_a"][1] * z_bldg
    return np.where(indoor, bldg, CAR_LOSS_DB[0] + CAR_LOSS_DB[1] * z_car), d_in


def sma_gain_db(theta_deg, phi_deg, bearing_deg: float, mech_tilt_deg: float):
    """Gain of one SMa sector: element and ten-element array (no electrical tilt) rotated by the mechanical
    downtilt (zenith convention, e.g. 95 deg = 5 deg below the horizon) and the bearing."""
    tp, pp = gcs_to_lcs_deg(theta_deg, phi_deg, bearing_deg, mech_tilt_deg - 90.0)
    return element_gain_db(tp, pp) + array_gain_db(tp, 90.0)


def _simulate_sma(sc: CalScenario, n_users: int, seed: int) -> Dict[str, np.ndarray]:
    fc, isd, hbs = sc.fc_ghz, sc.isd_m, SMA_BS_HEIGHT_M
    rng = np.random.default_rng([seed, round(fc * 10), 4, round(isd)])
    sites, offsets = hex_sites(isd), wrap_offsets(isd)
    S = len(sites)
    indoor, resid, hut = sma_users(rng, n_users)
    pen, d_in = sma_penetration_db(rng, indoor, resid, fc)
    ux = _drop_hex(rng, sites, isd, SMA_MIN_DISTANCE_M + d_in)    # the minimum distance holds for d2D-out
    dx = ux[:, None, None, 0] - (sites[None, None, :, 0] + offsets[None, :, None, 0])
    dy = ux[:, None, None, 1] - (sites[None, None, :, 1] + offsets[None, :, None, 1])
    dd = np.hypot(dx, dy)
    k = np.argmin(dd, axis=1)
    iu, js = np.meshgrid(np.arange(n_users), np.arange(S), indexing="ij")
    d2 = np.maximum(dd[iu, k, js], 1e-3)
    ex, ey = dx[iu, k, js], dy[iu, k, js]
    d2out = np.maximum(d2 - d_in[:, None], 0.0)
    plos = np.empty_like(d2)
    for h in np.unique(hut):                                      # the SMa formulas take one UT height
        rows = hut == h
        plos[rows] = _pl.p_los_sma(d2out[rows], hbs, float(h), 0.0)   # Table 7.8-1A: no vegetation
    los = rng.random((n_users, S)) < plos
    pl = np.empty_like(d2)
    for h in np.unique(hut):
        rows = hut == h
        pl[rows] = np.where(los[rows], _pl.sma_los(d2[rows], fc, hbs, float(h)),
                            _pl.sma_nlos(d2[rows], fc, hbs, float(h)))
    dbp = (2.0 * math.pi * hbs * hut * fc * 1e9 / C0)[:, None]   # Table 7.4.1-1 note 5
    sf_sd = np.where(indoor[:, None], SMA_O2I_SHADOW_DB, np.where(los, np.where(d2 < dbp, 4.0, 6.0), 8.0))
    loss = pl + sf_sd * rng.standard_normal((n_users, S)) + pen[:, None]
    h = hut[:, None]
    theta = 90.0 + np.degrees(np.arctan2(hbs - h, d2))
    phi = np.degrees(np.arctan2(ey, ex))
    tilt = SMA_MECH_TILT_DEG[float(isd)]
    gains = [sma_gain_db(theta, phi, b, tilt) for b in SECTORS_DEG]
    return _serving_metrics(sc, np.concatenate([g - loss for g in gains], axis=1), n_users)


# ---------------------------------------------------------------------------
# reference and comparison
# ---------------------------------------------------------------------------
REFERENCE_FILES = {"R1-165974": DATA, "R1-2506406": DATA_R1_2506406}


def load_reference(path: str = DATA) -> Dict[str, Dict[str, np.ndarray]]:
    """Mean, minimum and maximum over the companies of R1-165974 (or of the reference file ``path``), per sheet
    and metric, at 0..100 %."""
    ref: Dict[str, Dict[str, List[float]]] = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            d = ref.setdefault(row["scenario"], {})
            for k, v in row.items():
                if k != "scenario":
                    d.setdefault(k, []).append(float(v))
    return {s: {k: np.asarray(v) for k, v in d.items()} for s, d in ref.items()}


@dataclass
class Comparison:
    key: str
    metric: str
    percentiles: Tuple[int, ...]
    ours: np.ndarray
    mean: np.ndarray
    lo: np.ndarray
    hi: np.ndarray

    @property
    def inside(self) -> np.ndarray:
        return (self.ours >= self.lo) & (self.ours <= self.hi)

    @property
    def max_dev_db(self) -> float:
        """Largest distance from the industry mean over the compared percentiles [dB]."""
        return float(np.max(np.abs(self.ours - self.mean)))


def compare(sc: CalScenario, result: Dict[str, np.ndarray], ref=None,
            percentiles: Sequence[int] = PERCENTILES) -> List[Comparison]:
    """Our percentiles against the industry mean and range of the case's reference for the three metrics."""
    ref = load_reference(REFERENCE_FILES[sc.reference]) if ref is None else ref
    r = ref[sc.key]
    idx = np.searchsorted(r["cdf_percent"], percentiles)
    out = []
    for m in ("coupling_gain_db", "sinr_db", "sir_db"):
        ours = np.percentile(result[m], percentiles)
        out.append(Comparison(sc.key, m, tuple(percentiles), ours, r[m + "_mean"][idx], r[m + "_min"][idx],
                              r[m + "_max"][idx]))
    return out


CASES = tuple(CalScenario(n, f) for n in ("UMa", "UMi", "Indoor") for f in (6.0, 30.0))
#: the cases of R1-2506406 (since 2.4.0): UMa and UMi at 6 GHz with the updated model, UMa, UMi and SMa at 7 GHz
CASES_R1_2506406 = tuple(CalScenario(n, f, reference="R1-2506406") for f in (6.0, 7.0) for n in ("UMa", "UMi")) + \
    tuple(CalScenario("SMa", 7.0, isd, "R1-2506406") for isd in (1299.0, 1732.0))
#: largest distance from the company mean [dB] of the 7 GHz criterion C2 (code/hl240 plan; reported as a note)
MEAN_TOL_DB = 1.5


def calibration_checks(rep, n_users: int = 10000, seed: int = 1, tol_db: float = 0.5) -> None:
    """Section ``calibration`` of ``handoverlab verify``: within the company range of R1-165974 (+- ``tol_db``)."""
    rep.section("calibration", "large-scale calibration, TR 38.901 V19.5.0 clause 7.8.1 (IRR glass of V17.0.0, "
                               "see the module text), against the 21 companies of 3GPP R1-165974 "
                               "(5-95 %%, %d users)" % n_users)
    ref = load_reference()
    for sc in CASES:
        res = simulate_drops(sc, n_users, seed)
        for c in compare(sc, res, ref):
            ok = bool(np.all((c.ours >= c.lo - tol_db) & (c.ours <= c.hi + tol_db)))
            rep.check("%s %s within the company range" % (c.key, c.metric.replace("_db", "")), ok,
                      "%d/%d percentiles inside, largest distance from the mean %.2f dB"
                      % (int(c.inside.sum()), len(c.percentiles), c.max_dev_db))
    calibration_7ghz_checks(rep, n_users, seed, tol_db)


def calibration_7ghz_checks(rep, n_users: int = 10000, seed: int = 1, tol_db: float = 0.5) -> None:
    """7 GHz part of the section ``calibration`` (since 2.4.0): the cases of Table 7.8-1A and the 6 GHz rerun
    against the companies of R1-2506406.  C1 (a check): every percentile 5-95 % within the company range
    (+- ``tol_db``); C2 (a note): largest distance from the company mean at most :data:`MEAN_TOL_DB`."""
    rep.section("calibration", "large-scale calibration at 7 GHz, TR 38.901 V19.5.0 clause 7.8.1 and Table 7.8-1A "
                               "(IRR glass of V19.5.0), against the companies of 3GPP R1-2506406 (5-95 %%, %d users)"
                % n_users)
    ref = load_reference(DATA_R1_2506406)
    for sc in CASES_R1_2506406:
        comps = compare(sc, simulate_drops(sc, n_users, seed), ref)
        for c in comps:
            ok = bool(np.all((c.ours >= c.lo - tol_db) & (c.ours <= c.hi + tol_db)))
            rep.check("R1-2506406 %s %s within the company range" % (c.key, c.metric.replace("_db", "")), ok,
                      "%d/%d percentiles inside, largest distance from the mean %.2f dB"
                      % (int(c.inside.sum()), len(c.percentiles), c.max_dev_db))
        dev = max(c.max_dev_db for c in comps)
        rep.note("R1-2506406 %s near the company mean" % sc.key,
                 "largest distance %.2f dB over the three metrics (C2: at most %.1f dB, %s)"
                 % (dev, MEAN_TOL_DB, "met" if dev <= MEAN_TOL_DB else "NOT met"))
