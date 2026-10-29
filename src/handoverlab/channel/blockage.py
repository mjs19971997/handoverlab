# SPDX-License-Identifier: MIT
"""Blockage model A of TR 38.901 V19.5.0 clause 7.6.4.1 (since 2.10.0, ``radio.blockage`` "a").

* One self-blocking region in the UT local coordinate system (Eq. 7.6-20, Table 7.6.4.1-1, portrait or landscape
  mode): 30 dB for the power arriving inside it.
* K_block = 4 non-self-blocking regions in the global coordinate system around the UT (Eq. 7.6-21, Table
  7.6.4.1-2 for UMi / UMa: centre phi_k uniform in [0, 360) deg, width x_k uniform in [5, 15] deg, theta_k = 90 deg,
  y_k = 5 deg, distance r = 10 m), attenuating by the knife-edge terms of Eq. 7.6-22 to 7.6-27 with the signs of
  Table 7.6.4.1-3 inside |phi - phi_k| < x_k and |theta - theta_k| < y_k.
* The blocker centres (and widths) are uniform variables that are spatially and temporally consistent with
  R(dx, dt) = exp(-(|dx| / d_corr + |dt| / t_corr)) (Eq. 7.6-28; d_corr of Table 7.6.4.1-4, t_corr = d_corr / v
  with v the blockers' speed): a Gaussian AR(1) process along the user's path mapped to a uniform variable.

The clause attenuates every cluster.  HandoverLab has no clusters, so the attenuation acts on the expected
arrival power angular spectrum of each user-site link: the LOS ray (K_R / (K_R + 1) of the power, median K) at
the LOS arrival direction, and the diffuse part over a wrapped Gaussian of rms ASA in azimuth and a Laplacian of
rms ZSA in zenith (Table 7.5-6 medians).  The power factor of a direction is the product of the self-blocking
factor and of the non-self-blocking factors (1 - F_A F_Z)^2, the latter combined as if the small regions did not
overlap; the expectation over the separable spectrum is then exact for each term.  The UT local system is the
global one turned by the user's heading (phi' = 0 along the direction of travel, no tilt).
"""
from __future__ import annotations

import math

import numpy as np
from scipy.special import ndtr

from .spread import U_AZ, U_ZE, los_ray_share

C0 = 299792458.0
#: Table 7.6.4.1-1: (phi'_sb, x_sb, theta'_sb, y_sb) [deg]
SELF_REGION = {"portrait": (260.0, 120.0, 100.0, 80.0), "landscape": (40.0, 160.0, 110.0, 75.0)}
SELF_LOSS_DB = 30.0
K_BLOCK = 4
#: Table 7.6.4.1-2, UMi / UMa / SMa / RMa: x_k range, theta_k, y_k [deg], r [m]
X_RANGE, THETA_K, Y_K, R_M = (5.0, 15.0), 90.0, 5.0, 10.0
#: Table 7.6.4.1-4: d_corr [m] (UMi / UMa LOS and NLOS; O2I 5 m)
D_CORR_M, D_CORR_O2I_M = 10.0, 5.0
BLOCKAGE_PATHLOSS = ("uma", "umi_street_canyon")


def _lg_arrival(pathloss: str, los: bool, fc: float):
    """Median ASA and ZSA [deg] of TR 38.901 V19.5.0 Table 7.5-6 Part-1 (UMa below 6 GHz: fc = 6, note 6)."""
    if pathloss == "uma":
        f = max(fc, 6.0)
        asa = 1.76 if los else 2.04 - 0.25 * math.log10(f)
        zsa = 0.96 if los else -0.2856 * math.log10(f) + 1.445
    else:
        f = math.log10(1.0 + max(fc, 2.0))              # note 7: UMi below 2 GHz uses fc = 2
        asa = -0.07 * f + (1.66 if los else 1.76)
        zsa = -0.11 * f + 0.81 if los else -0.03 * f + 0.92
    return min(10.0 ** asa, 104.0), min(10.0 ** zsa, 52.0)


def _wrap(a):
    return (a + 180.0) % 360.0 - 180.0


def _edge_terms(d, half, full, kr):
    """F_1 + F_2 of Eq. 7.6-23 for angle offsets ``d`` from a region's centre (degrees, any shape), the region
    of width 2 ``half`` and the attenuation zone |d| < ``full``; zero outside the zone.  ``kr`` = pi r / lambda.
    Signs of Table 7.6.4.1-3: (+, +) inside, (-, +) above the region, (+, -) below it."""
    a1 = np.radians(d - half)
    a2 = np.radians(d + half)
    s1 = np.where(d > half, -1.0, 1.0)
    s2 = np.where(d < -half, -1.0, 1.0)

    def f(a, s):
        v = np.sqrt(np.maximum(kr * (1.0 / np.cos(a) - 1.0), 0.0))
        return np.arctan(s * 0.5 * math.pi * v) / math.pi
    return np.where(np.abs(d) < full, f(a1, s1) + f(a2, s2), 0.0)


class BlockageA:
    """Blockers of every user and their attenuation of every user-site link."""

    def __init__(self, rng: np.random.Generator, n_users: int, radio, speeds, dt_s: float, indoor=None):
        self.mode = radio.blockage_mode
        self.pathloss, self.fc = radio.pathloss, radio.carrier_ghz
        self.kr = math.pi * R_M / (C0 / (radio.carrier_ghz * 1e9))
        self.h_bs, self.h_ut = radio.bs_height_m, radio.ue_height_m
        self.rng = rng
        self.U = n_users
        d_corr = np.full(n_users, D_CORR_M)
        if indoor is not None:
            d_corr = np.where(indoor, D_CORR_O2I_M, d_corr)
        v_b = radio.blocker_speed_kmh / 3.6
        # per step: |dx| / d_corr + |dt| / t_corr with t_corr = d_corr / v_b
        self.r = np.exp(-(np.asarray(speeds, dtype=float) + v_b) * dt_s / d_corr)            # (U,)
        self.g = rng.standard_normal((2, n_users, K_BLOCK))                                   # centre, width
        self.p_los = los_ray_share()
        self.spreads = {s: _lg_arrival(self.pathloss, s, self.fc) for s in (True, False)}

    def _advance(self, n, mult):
        """Blocker variables (n, 2, U, K) at the next ``n`` instants ``mult`` steps apart (AR(1), per user)."""
        out = np.empty((n, 2, self.U, K_BLOCK))
        r = (self.r ** mult)[None, :, None]
        g = self.g
        q = np.sqrt(1.0 - r * r)
        for i in range(n):
            g = r * g + q * self.rng.standard_normal(g.shape)
            out[i] = g
        self.g = g
        return out

    def factor_db(self, x, y, heading, sites, los_w, n: int, mult: int = 1, layout=None):
        """Blockage gain [dB] (n, U, M) <= 0 of every link at ``n`` instants ``mult`` steps apart; ``x``, ``y``,
        ``heading`` (n, U) [m, rad], ``sites`` (M, 2), ``los_w`` (n, U, M) LOS power weight or None (all NLOS)."""
        g = self._advance(n, mult)
        u = ndtr(g)
        phi_k = 360.0 * u[:, 0]                                         # (n, U, K)
        x_k = X_RANGE[0] + (X_RANGE[1] - X_RANGE[0]) * u[:, 1]
        dx = x[..., None] - sites[None, None, :, 0]
        dy = y[..., None] - sites[None, None, :, 1]
        if layout is not None and layout.period_x:     # nearest image of the site (wrap-around)
            dx, dy = layout.nearest_image(dx, dy)
        dx, dy = -dx, -dy                                               # UE -> site
        d2 = np.maximum(np.hypot(dx, dy), 1.0)
        az = np.degrees(np.arctan2(dy, dx))                             # arrival azimuth (towards the site), GCS
        ze = 90.0 - np.degrees(np.arctan2(self.h_bs - self.h_ut, d2))  # arrival zenith of the LOS direction
        hd = np.degrees(heading)[..., None]
        p_sb, x_sb, t_sb, y_sb = SELF_REGION[self.mode]
        keep = 1.0 - 10.0 ** (-SELF_LOSS_DB / 10.0)

        def terms(a_az, a_ze):
            """Self-blocking indicators and non-self (F_A, F_Z) terms at directions (n, U, M, ...)."""
            i_a = np.abs(_wrap(a_az - hd[..., None] - p_sb)) < 0.5 * x_sb
            i_z = np.abs(a_ze - t_sb) < 0.5 * y_sb
            da = _wrap(a_az[..., None] - phi_k[:, :, None, None, :])                       # (..., K)
            fa = _edge_terms(da, 0.5 * x_k[:, :, None, None, :], x_k[:, :, None, None, :], self.kr)
            fz = _edge_terms(a_ze - THETA_K, 0.5 * Y_K, Y_K, self.kr)
            return i_a, i_z, fa, fz

        # LOS ray: the exact product over the regions at the LOS direction
        i_a, i_z, fa, fz = terms(az[..., None], ze[..., None])
        f_los = (1.0 - keep * (i_a & i_z)[..., 0]) * np.prod((1.0 - fa[..., 0, :] * fz[..., 0, None]) ** 2, -1)
        out = np.zeros(az.shape)
        for state in (True, False):
            asa, zsa = self.spreads[state]
            a_n = az[..., None] + asa * U_AZ                            # (n, U, M, N_AZ)
            z_n = np.clip(ze[..., None] + zsa * U_ZE, 0.0, 180.0)       # (n, U, M, N_ZE)
            ia, _, fa_n, _ = terms(a_n, ze[..., None])
            _, iz, _, fz_n = terms(az[..., None], z_n)
            pa, pz = ia.mean(-1), iz.mean(-1)                           # P(azimuth in), P(zenith in)
            ea, ea2 = fa_n.mean(-2), (fa_n ** 2).mean(-2)               # (n, U, M, K)
            eza, eza2 = (ia[..., None] * fa_n).mean(-2), (ia[..., None] * fa_n ** 2).mean(-2)
            ez, ez2 = fz_n.mean(-1), (fz_n ** 2).mean(-1)              # (n, U, M): one theta_k for all k
            ezz, ezz2 = (iz * fz_n).mean(-1), (iz * fz_n ** 2).mean(-1)
            # E[s] - sum_k E[s (1 - f_k)], s = 1 - keep I_a I_z, 1 - f_k = 2 F_A F_Z - F_A^2 F_Z^2
            e_s = 1.0 - keep * pa * pz
            e_nk = 2.0 * ea * ez[..., None] - ea2 * ez2[..., None]
            e_snk = e_nk - keep * (2.0 * eza * ezz[..., None] - eza2 * ezz2[..., None])
            f_dif = np.maximum(e_s - e_snk.sum(-1), 10.0 ** (-SELF_LOSS_DB / 10.0) * 1e-3)
            if state:
                f = self.p_los * f_los + (1.0 - self.p_los) * f_dif
                wl = np.zeros(az.shape) if los_w is None else los_w
                out += wl * f
            else:
                wl = np.ones(az.shape) if los_w is None else 1.0 - los_w
                out += wl * f_dif
        return 10.0 * np.log10(np.maximum(out, 1e-12))
