# SPDX-License-Identifier: MIT
"""Expected beam gains over the power angular spectrum of TR 38.901 (since 2.10.0, ``radio.beams.angular_spread``).

In the channel of TR 38.901 V19.5.0 clause 7.5 the power leaves the base station over clusters and rays (steps
5-8), and every ray is weighted by the transmit field pattern in its own departure direction (step 11).  The
mean received power through a beam is then the power-weighted mean of the beam's gain over the ray directions.
The composite power angular spectrum (PAS) "in azimuth of all clusters is modelled as wrapped Gaussian" and in
zenith as Laplacian (step 7; Table 7.5-6 note 5), with the rms spreads ASD and ZSD of the link (Table 7.5-6,
Tables 7.5-7 / 7.5-8); NLOS links have the ZOD offset mu_offset,ZOD of Eq. 7.5-19; in LOS a single LOS ray
carries K_R / (K_R + 1) of the power (Eq. 7.5-7 and 7.5-8).

This module gives that expectation without clusters: the LOS ray in the geometric direction plus the diffuse
part averaged over quadrature nodes of the two distributions.  The diffuse spreads of a LOS link are
ASD / sqrt(1 - P_LOS) and ZSD / sqrt(1 - P_LOS), so that the rms of the whole PAS, LOS ray included, is the
table's value.  The evaluation is separable: the zenith offsets act on the vertical array factor, the azimuth
offsets on the element times the horizontal array factor.  The large-scale parameters of every user-site link
are drawn once per link and LOS state (log-normal of the tables; step 4 limits ASD to 104 deg and ZSD to
52 deg); their cross-correlations and spatial consistency are not modelled.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.special import ndtri

from .antenna import element_gain_db, ula_gain, wrap_deg

#: quadrature nodes per dimension (equal-probability midpoints)
N_AZ = 16
N_ZE = 16
_P_AZ = (np.arange(N_AZ) + 0.5) / N_AZ
_P_ZE = (np.arange(N_ZE) + 0.5) / N_ZE
#: nodes of a Gaussian (azimuth) and a Laplacian (zenith, scale b = rms / sqrt 2), scaled to an rms of exactly 1
#: (the 16 midpoints alone cut the tails: rms 0.96 and 0.90)
U_AZ = ndtri(_P_AZ)
U_AZ = U_AZ / np.sqrt(np.mean(U_AZ ** 2))
U_ZE = np.where(_P_ZE < 0.5, np.log(2.0 * _P_ZE), -np.log(2.0 * (1.0 - _P_ZE))) / math.sqrt(2.0)
U_ZE = U_ZE / np.sqrt(np.mean(U_ZE ** 2))

ASD_MAX_DEG = 104.0       # TR 38.901 clause 7.5 step 4
ZSD_MAX_DEG = 52.0
SPREAD_PATHLOSS = ("uma", "umi_street_canyon")


def _lg_asd(pathloss: str, los: bool, fc: float):
    """(mu, sigma) of lgASD = log10(ASD / 1 deg), TR 38.901 V19.5.0 Table 7.5-6 Part-1."""
    if pathloss == "uma":
        return (0.92, 0.31) if los else (1.09, 0.44)
    f = math.log10(1.0 + max(fc, 2.0))                    # note 7: UMi below 2 GHz uses fc = 2
    return (-0.05 * f + 1.21, 0.08 * f + 0.29) if los else (-0.24 * f + 1.54, 0.10 * f + 0.33)


def _lg_zsd(pathloss: str, los: bool, d2d, h_ut: float, h_bs: float):
    """(mu, sigma) of lgZSD, Table 7.5-7 (UMa) and Table 7.5-8 (UMi - Street Canyon)."""
    d = np.asarray(d2d, dtype=float) / 1000.0
    if pathloss == "uma":
        if los:
            return np.maximum(-0.5, -2.1 * d - 0.01 * (h_ut - 1.5) + 0.75), 0.40
        return np.maximum(-0.5, -2.1 * d - 0.01 * (h_ut - 1.5) + 0.9), 0.49
    if los:
        return np.maximum(-0.21, -14.8 * d + 0.01 * abs(h_ut - h_bs) + 0.83), 0.35
    return np.maximum(-0.5, -3.1 * d + 0.01 * max(h_ut - h_bs, 0.0) + 0.2), 0.35


def zod_offset_deg(pathloss: str, d2d, h_ut: float, fc: float):
    """mu_offset,ZOD of a NLOS link [deg] (Table 7.5-7 with fc = 6 below 6 GHz, note 4; Table 7.5-8)."""
    d = np.asarray(d2d, dtype=float)
    if pathloss == "uma":
        lf = math.log10(max(fc, 6.0))
        a, b, c, e = 0.208 * lf - 0.782, 25.0, -0.13 * lf + 2.03, 7.66 * lf - 5.96
        return e - 10.0 ** (a * np.log10(np.maximum(b, d)) + c - 0.07 * (h_ut - 1.5))
    return -10.0 ** (-1.5 * np.log10(np.maximum(10.0, d)) + 3.3)


#: median Ricean K-factor [dB] of LOS links (Table 7.5-6 Part-1: 9 dB for UMa and UMi)
K_DB = 9.0


def los_ray_share() -> float:
    """P_LOS = K_R / (K_R + 1) at the median K-factor."""
    kr = 10.0 ** (K_DB / 10.0)
    return kr / (kr + 1.0)


class LinkSpreads:
    """Rms spreads and ZOD offsets of the user-site links of one layer (one standard normal per link and state)."""

    def __init__(self, rng: np.random.Generator, n_users: int, n_sites: int, pathloss: str, fc: float,
                 h_ut: float, h_bs: float):
        self.pathloss, self.fc, self.h_ut, self.h_bs = pathloss, fc, h_ut, h_bs
        self.z = rng.standard_normal((4, n_users, n_sites))    # ASD LOS, ASD NLOS, ZSD LOS, ZSD NLOS
        self.p_los = los_ray_share()
        self.f_los = 1.0 / math.sqrt(1.0 - self.p_los)         # diffuse spread of a LOS link

    def spreads(self, users, sites, d2d, los: bool):
        """(asd, zsd, offset) [deg] of the diffuse part for links (users, sites) at distances ``d2d``."""
        m, s = _lg_asd(self.pathloss, los, self.fc)
        asd = np.minimum(10.0 ** (m + s * self.z[0 if los else 1][users, sites]), ASD_MAX_DEG)
        mz, sz = _lg_zsd(self.pathloss, los, d2d, self.h_ut, self.h_bs)
        zsd = np.minimum(10.0 ** (mz + sz * self.z[2 if los else 3][users, sites]), ZSD_MAX_DEG)
        if los:
            return asd * self.f_los, zsd * self.f_los, np.zeros_like(zsd)
        return asd, zsd, zod_offset_deg(self.pathloss, d2d, self.h_ut, self.fc)


def diffuse_gain_lin(theta_deg, phi_deg, beam_phi_deg, tilt_deg: float, m: int, n: int, am_db: float,
                     asd, zsd, offset):
    """Expected linear gain (S + (B,)) of the beams over the diffuse PAS: wrapped Gaussian of rms ``asd`` in
    azimuth, Laplacian of rms ``zsd`` around ``theta + offset`` in zenith (all of shape S, degrees)."""
    th = np.asarray(theta_deg, dtype=np.float32)
    ph = np.asarray(phi_deg, dtype=np.float32)
    asd = np.asarray(asd, dtype=np.float32)
    zsd = np.asarray(zsd, dtype=np.float32)
    tc = np.float32(math.cos(math.radians(tilt_deg)))
    t0 = th + np.asarray(offset, dtype=np.float32)
    gv = np.zeros(th.shape, dtype=np.float32)
    for u in U_ZE:                                         # vertical array factor over the zenith nodes
        t = np.clip(t0 + np.float32(u) * zsd, 0.0, 180.0)
        gv += ula_gain(np.float32(math.pi) * (np.cos(np.radians(t)) - tc), m)
    gv /= np.float32(N_ZE)
    st = np.sin(np.radians(th))[..., None]
    sb = np.float32(math.pi * math.sin(math.radians(tilt_deg))) * np.sin(np.radians(np.asarray(beam_phi_deg,
                                                                                               dtype=np.float32)))
    eh = np.zeros(th.shape + (len(sb),), dtype=np.float32)
    for u in U_AZ:                                         # element x horizontal array factor over the azimuth nodes
        p = wrap_deg(ph + np.float32(u) * asd).astype(np.float32)
        ge = np.power(np.float32(10.0), element_gain_db(th, p, am_db) / np.float32(10.0))
        eh += ge[..., None] * ula_gain(np.float32(math.pi) * st * np.sin(np.radians(p))[..., None] - sb, n)
    eh /= np.float32(N_AZ)
    return gv[..., None] * eh
