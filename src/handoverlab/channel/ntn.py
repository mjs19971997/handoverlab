# SPDX-License-Identifier: MIT
"""Non-terrestrial network: one LEO satellite with earth-moving beams (``layout.kind: ntn``; since 2.0.0).

Sources (texts in ``code/std3gpp``; equations read from the PDF pages):

* TR 38.811 V15.4.0: Earth as a sphere of radius 6371 km (clause 6.3); the satellite antenna
  ``G / Gmax = 4 |J1(ka sin t) / (ka sin t)|^2`` with ``a`` the aperture radius (clause 6.4.1); the LOS
  probability of Table 6.6.1-1 at the nearest reference elevation; the basic path loss
  ``PLb = FSPL + SF + CL`` (Eq. 6.6-4), ``FSPL = 32.45 + 20 log10(fc) + 20 log10(d)`` (Eq. 6.6-2, d in m,
  fc in GHz), the slant range ``d = sqrt(R^2 sin^2(a) + h^2 + 2 h R) - R sin(a)`` (Eq. 6.6-3), shadowing and
  clutter loss of Tables 6.6.2-1..3 (clutter only in NLOS), the atmospheric loss ``Azenith / sin(a)``
  (Eq. 6.6-8), shadowing correlation 37 m (LOS) and 120 m (NLOS) in the rural S band (Tables 6.7.2-7a, -8a).
* TR 38.821 V16.2.0: the satellite sets of Tables 6.1.1.1-1 and -2, the handheld UE of Table 6.1.1.1-3, the
  19-beam layout on the UV plane with the adjacent beam spacing ``sqrt(3) sin(HPBW / 2)`` (Table 6.1.1.1-4),
  frequency reuse 1 (Table 6.1.1.1-5, option 1), the link budget of clause 6.1.3 (Table 6.1.3.3-1), the LEO
  speed of 7.56 km/s and the round-trip delays of Table 7.1-1.

All beams belong to one satellite, so a user sees them over one propagation path: slant range, LOS state,
shadowing, clutter, atmospheric and scintillation loss are common to the beams; only the antenna gain differs.
The beams are fixed in the satellite frame and sweep over the ground with the satellite (scenarios C2 and D2,
which RAN2 prioritised for mobility, TR 38.821 clause 7.3.2.4).
"""
from __future__ import annotations

import math
from typing import Iterator

import numpy as np
from scipy.special import j1, ndtri

from ..seeds import streams
from .source import LN10_10, Chunk, _ar1

R_EARTH = 6371.0e3                     # m, TR 38.811 clause 6.3
MU_EARTH = 3.986004418e14              # m^3/s^2, standard gravitational parameter of the Earth
C_LIGHT = 299792458.0

#: LOS probability [%] of TR 38.811 Table 6.6.1-1 at the reference elevations 10, 20, ..., 90 degrees
LOS_PROB = {
    "dense_urban": (28.2, 33.1, 39.8, 46.8, 53.7, 61.2, 73.8, 82.0, 98.1),
    "urban": (24.6, 38.6, 49.3, 61.3, 72.6, 80.5, 91.9, 96.8, 99.2),
    "rural": (78.2, 86.9, 91.9, 92.9, 93.5, 94.0, 94.9, 95.2, 99.8),      # "Suburban and Rural scenarios"
}
#: S band shadowing and clutter of TR 38.811 Tables 6.6.2-1..3: (sigma LOS, sigma NLOS, CL NLOS) [dB] per reference
SF_CL_S = {
    "dense_urban": ((3.5, 15.5, 34.3), (3.4, 13.9, 30.9), (2.9, 12.4, 29.0), (3.0, 11.7, 27.7), (3.1, 10.6, 26.8),
                    (2.7, 10.5, 26.2), (2.5, 10.1, 25.8), (2.3, 9.2, 25.5), (1.2, 9.2, 25.5)),
    "urban": tuple((4.0, 6.0, cl) for cl in (34.3, 30.9, 29.0, 27.7, 26.8, 26.2, 25.8, 25.5, 25.5)),
    "rural": ((1.79, 8.93, 19.52), (1.14, 9.08, 18.17), (1.14, 8.78, 18.42), (0.92, 10.25, 18.28),
              (1.42, 10.56, 18.63), (1.56, 10.74, 17.68), (0.85, 10.17, 16.50), (0.72, 11.52, 16.30),
              (0.72, 11.52, 16.30)),
}


def slant_range(alpha_deg, h_m):
    """Eq. 6.6-3 of TR 38.811: distance [m] from a ground terminal to a satellite at altitude ``h_m``."""
    s = np.sin(np.radians(alpha_deg))
    return np.sqrt(R_EARTH ** 2 * s ** 2 + h_m ** 2 + 2.0 * h_m * R_EARTH) - R_EARTH * s


def fspl_db(d_m, fc_ghz):
    """Eq. 6.6-2 of TR 38.811: free-space path loss [dB], ``d_m`` in metres, ``fc_ghz`` in GHz."""
    return 32.45 + 20.0 * np.log10(fc_ghz) + 20.0 * np.log10(d_m)


def antenna_gain(theta_rad, ka):
    """Normalised satellite antenna gain of TR 38.811 clause 6.4.1 (linear, 1 at boresight)."""
    x = ka * np.sin(np.abs(np.asarray(theta_rad, dtype=float)))
    out = np.ones_like(x)
    nz = x > 1e-12
    out[nz] = 4.0 * (j1(x[nz]) / x[nz]) ** 2
    return out


def ka_from_aperture(aperture_m, fc_ghz):
    """``ka`` of the antenna pattern: the aperture radius ``a = aperture / 2`` times the wave number."""
    return 2.0 * math.pi * (aperture_m / 2.0) * fc_ghz * 1e9 / C_LIGHT


def hpbw_deg(ka):
    """3 dB beamwidth [deg] of the pattern: twice the angle where the normalised gain is 1/2."""
    from scipy.optimize import brentq
    x3 = brentq(lambda x: 4.0 * (j1(x) / x) ** 2 - 0.5, 0.5, 3.0)
    return 2.0 * math.degrees(math.asin(x3 / ka))


def orbital_speed(h_m):
    """Speed [m/s] of a circular orbit at altitude ``h_m``."""
    return math.sqrt(MU_EARTH / (R_EARTH + h_m))


def nearest_reference(alpha_deg):
    """Index 0..8 of the nearest reference elevation 10..90 degrees (TR 38.811 Tables 6.6.1-1, 6.6.2-x)."""
    return np.clip(np.rint(np.asarray(alpha_deg) / 10.0).astype(int) - 1, 0, 8)


def hex_uv(n_beams: int, spacing: float) -> np.ndarray:
    """UV offsets of a hexagonal beam layout: the centre beam and rings around it (19 = two rings)."""
    pts = [(0.0, 0.0)]
    ring = 1
    while len(pts) < n_beams:
        for i in range(-ring, ring + 1):
            for j in range(-ring, ring + 1):
                if max(abs(i), abs(j), abs(i + j)) == ring:
                    pts.append((i + j / 2.0, j * math.sqrt(3.0) / 2.0))
        ring += 1
    return spacing * np.array(pts[:n_beams])


def to_ecef(x, y):
    """Local coordinates [m] (x east, y north of the area centre at latitude 0, longitude 0) on the sphere."""
    lon, lat = np.asarray(x) / R_EARTH, np.asarray(y) / R_EARTH
    return np.stack([R_EARTH * np.cos(lat) * np.cos(lon), R_EARTH * np.cos(lat) * np.sin(lon),
                     R_EARTH * np.sin(lat)], axis=-1)


def to_local(p):
    """Inverse of :func:`to_ecef` for points on (or projected to) the sphere."""
    p = np.asarray(p, dtype=float)
    r = np.linalg.norm(p, axis=-1)
    lat = np.arcsin(p[..., 2] / r)
    lon = np.arctan2(p[..., 1], p[..., 0])
    return np.stack([lon * R_EARTH, lat * R_EARTH], axis=-1)


class NtnGeometry:
    """The satellite, its orbit and its beams for one scenario (see the module text)."""

    def __init__(self, scenario):
        n = scenario.ntn
        self.cfg, self.radio = n, scenario.radio
        self.h = n.altitude_km * 1e3
        self.v = orbital_speed(self.h)
        self.omega = self.v / (R_EARTH + self.h)
        self.ka = ka_from_aperture(n.aperture_m, scenario.radio.carrier_ghz)
        self.hpbw = hpbw_deg(self.ka)
        self.t_mid = 0.5 * scenario.run.duration_s
        # orbit: polar (in the x-z plane after a rotation by the cross-track angle), moving north, the satellite
        # at its closest point to the area centre at t_mid; the central beam points at the area centre with the
        # elevation centre_elevation_deg there (TR 38.821 Table 6.1.1.1-4, case 2; 90 degrees = case 1, nadir)
        a = math.radians(n.centre_elevation_deg)
        self.gamma = math.acos(R_EARTH * math.cos(a) / (R_EARTH + self.h)) - a    # Earth central angle
        sp = self.sat_pos(np.array([self.t_mid]))[0]
        c = to_ecef(0.0, 0.0)
        u, v, w = self.frame(np.array([self.t_mid]))
        d = (c - sp) / np.linalg.norm(c - sp)
        self.uv0 = np.array([d @ u[0], d @ v[0]])                  # central beam on the UV plane
        spacing = math.sqrt(3.0) * math.sin(math.radians(self.hpbw) / 2.0)
        self.uv = self.uv0 + hex_uv(n.n_beams, spacing)
        if np.any(np.hypot(self.uv[:, 0], self.uv[:, 1]) >= 1.0):
            raise ValueError("the beam layout does not fit on the UV plane")
        self.n_beams = n.n_beams
        self.eirp_dbm = n.eirp_dbw_per_mhz + 30.0 + 10.0 * math.log10(scenario.radio.bandwidth_mhz)

    # ------------------------------------------------------------------ orbit and frames
    def sat_pos(self, t):
        """ECEF positions (T, 3) of the satellite at times t [s]."""
        phi = self.omega * (np.asarray(t, dtype=float) - self.t_mid)
        r = R_EARTH + self.h
        p = np.stack([r * np.cos(phi), np.zeros_like(phi), r * np.sin(phi)], axis=-1)
        g = -self.gamma                                           # rotate the orbit plane west of the centre
        rot = np.array([[math.cos(g), -math.sin(g), 0.0], [math.sin(g), math.cos(g), 0.0], [0.0, 0.0, 1.0]])
        return p @ rot.T

    def frame(self, t):
        """Satellite frame (u along track, v across, w towards the Earth centre), each (T, 3)."""
        p = self.sat_pos(t)
        w = -p / np.linalg.norm(p, axis=-1, keepdims=True)
        p2 = self.sat_pos(np.asarray(t, dtype=float) + 1e-3)
        vel = p2 - p
        u = vel - np.sum(vel * w, axis=-1, keepdims=True) * w
        u /= np.linalg.norm(u, axis=-1, keepdims=True)
        v = np.cross(w, u)
        return u, v, w

    def boresights(self, t):
        """ECEF unit vectors (T, B, 3) of the beam boresights at times t."""
        u, v, w = self.frame(t)
        bu, bv = self.uv[:, 0], self.uv[:, 1]
        bw = np.sqrt(1.0 - bu ** 2 - bv ** 2)
        return u[:, None] * bu[None, :, None] + v[:, None] * bv[None, :, None] + w[:, None] * bw[None, :, None]

    def beam_centres(self, t) -> np.ndarray:
        """Ground points (B, 2) [m, local] where the beam boresights meet the Earth at time t (moving references)."""
        tt = np.atleast_1d(np.asarray(t, dtype=float))
        sp = self.sat_pos(tt)[0]
        b = self.boresights(tt)[0]                                 # (B, 3)
        # ray sp + s b hits the sphere |x| = R: s^2 + 2 s (sp.b) + |sp|^2 - R^2 = 0, nearest root
        pb = b @ sp
        s = -pb - np.sqrt(pb ** 2 - (sp @ sp - R_EARTH ** 2))
        return to_local(sp[None, :] + s[:, None] * b)

    # ------------------------------------------------------------------ link quantities
    def link(self, x, y, t):
        """Elevation [deg] (P,), slant range [m] (P,) and normalised antenna gain [dB] (P, B) at points and times."""
        p = to_ecef(x, y)
        sp = self.sat_pos(t)
        d = sp - p
        rng = np.linalg.norm(d, axis=-1)
        up = p / np.linalg.norm(p, axis=-1, keepdims=True)
        elev = np.degrees(np.arcsin(np.clip(np.sum(d * up, axis=-1) / rng, -1.0, 1.0)))
        b = self.boresights(t)                                     # (P, B, 3)
        cosang = np.einsum("pbk,pk->pb", b, -d / rng[:, None])
        theta = np.arccos(np.clip(cosang, -1.0, 1.0))
        g = antenna_gain(theta, self.ka)
        return elev, rng, 10.0 * np.log10(np.maximum(g, 1e-30))


def ntn_layout(scenario, geom: NtnGeometry):
    """The users' area (``layout.area_m``, centred on the origin) with the beams' ground centres at mid-run."""
    from ..layout import Layout
    w, h = scenario.layout.area_m or (100e3, 100e3)
    return Layout("ntn", geom.beam_centres(geom.t_mid), np.zeros((0, 4)), np.array([]), np.array([]), 0.0,
                  -w / 2.0, w / 2.0, -h / 2.0, h / 2.0)


class NtnMap:
    """The part of a radio map that the engine and the rules use: the nominal best beam (no buildings, no field)."""
    is_grid = False
    has_field = False
    imported = False

    def __init__(self, layout, geom: NtnGeometry):
        self.layout, self.geom = layout, geom

    def nominal_cell(self, x, y) -> np.ndarray:
        """Beam whose ground centre at the middle of the run is nearest (the operator's plan)."""
        c = self.geom.beam_centres(self.geom.t_mid)
        x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
        d = np.hypot(x[..., None] - c[:, 0], y[..., None] - c[:, 1])
        return np.argmin(d, axis=-1).astype(np.int16)


class NtnSource:
    """Received powers of every beam at every user and step, chunk by chunk (the contract of RadioSource)."""

    def __init__(self, world, chunk_steps: int = 1000):
        sc = world.scenario
        self.world, self.geom, self.R, self.n = world, world.ntn, sc.radio, sc.ntn
        self.X, self.Y, self.V = world.x, world.y, world.speed
        self.S, self.U = self.X.shape
        self.M = self.geom.n_beams
        dt = sc.protocol.step_s
        self.dt = dt
        self.mp = max(1, int(round(sc.protocol.l1_period_s / dt)))
        self.chunk = max(self.mp, (chunk_steps // self.mp) * self.mp)
        self.rng_t, self.rng_s, self.rng_m, self.rng_l = streams(world.seed, "ntn", 4)
        self.zs = self.rng_s.standard_normal(self.U)            # shadowing (one per user: one satellite)
        self.zl = self.rng_l.standard_normal(self.U)            # LOS state process
        self.r_s = np.exp(-self.V * dt / self.n.sf_corr_m)
        self.r_l = np.exp(-self.V * dt / self.n.los_corr_m)
        self.p0 = self.geom.eirp_dbm + self.R.ue_gain_db - self.n.scintillation_db
        self.r_t = float(np.exp(-self.mp * dt / self.R.time_var_tau_s))
        self.zt = self.rng_t.standard_normal((self.U, self.M))   # stationary start of the time-varying part
        self.los_ref = np.array(LOS_PROB[self.n.environment]) / 100.0
        self.sfcl = np.array(SF_CL_S[self.n.environment])

    def _ar1(self, rng, r_u, z, n):
        out = np.empty((n, self.U))
        for u in range(self.U):
            out[:, u] = _ar1(rng.standard_normal((n, 1)), r_u[u], z[u:u + 1])[:, 0]
        return out

    def chunks(self) -> Iterator[Chunk]:
        R = self.R
        for k0 in range(0, self.S, self.chunk):
            k1 = min(self.S, k0 + self.chunk)
            n = k1 - k0
            t = np.repeat(np.arange(k0, k1) * self.dt, self.U)
            x, y = self.X[k0:k1].ravel(), self.Y[k0:k1].ravel()
            elev, rng, g_db = self.geom.link(x, y, t)
            ref = nearest_reference(elev)
            gl = self._ar1(self.rng_l, self.r_l, self.zl, n)
            self.zl = gl[-1].copy()
            los = gl.ravel() < ndtri(np.clip(self.los_ref[ref], 1e-9, 1 - 1e-9))
            gs = self._ar1(self.rng_s, self.r_s, self.zs, n)
            self.zs = gs[-1].copy()
            sf = np.where(los, self.sfcl[ref, 0], self.sfcl[ref, 1]) * gs.ravel()
            cl = np.where(los, 0.0, self.sfcl[ref, 2])
            atm = self.n.atm_zenith_db / np.sin(np.radians(np.maximum(elev, 1.0)))
            common = self.p0 - fspl_db(rng, R.carrier_ghz) - atm - cl + sf      # positive SF: more power (note 2)
            rs = (common[:, None] + g_db).reshape(n, self.U, self.M)
            nm = -(-n // self.mp)
            if R.time_var_db > 0:
                zt = _ar1(self.rng_t.standard_normal((nm, self.U, self.M)), self.r_t, self.zt)
                self.zt = zt[-1].copy()
                rs += R.time_var_db * np.repeat(zt, self.mp, axis=0)[:n]
            l1 = rs[::self.mp] + R.l1_error_db * self.rng_m.standard_normal((nm, self.U, self.M))
            yield Chunk(k0, n, rs, np.exp(rs * LN10_10), l1, self.mp)
