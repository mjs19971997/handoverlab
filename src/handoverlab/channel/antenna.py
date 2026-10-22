# SPDX-License-Identifier: MIT
"""Base-station antenna of TR 38.901 clause 7.3 and the SSB beams of the beam model (since 1.10.0).

* Element pattern of Table 7.3-1: A(theta, phi) = -min(-(A_V + A_H), A_m) with
  A_V = -min(12 ((theta - 90) / 65)^2, SLA_V), A_H = -min(12 (phi / 65)^2, A_m),
  SLA_V = A_m = 30 dB, plus the maximum directional gain G_E,max = 8 dBi (theta
  zenith angle, phi azimuth from the boresight, degrees).  A larger A_m (since
  2.3.0, ``radio.beams.am_db``) lowers the back lobe of the element.
* Panel: a uniform rectangular array of M rows and N columns of
  single-polarised elements at d_V = d_H = lambda / 2 (Figure 7.3-1).
* Beams: separable DFT weights.  The vertical weights are those of Eq. 7.3-1,
  w_m = exp(-j pi (m - 1) cos(theta_etilt)) / sqrt(M); the horizontal weights
  steer the same way to the azimuth phi_b of SSB beam b,
  w_n = exp(-j pi (n - 1) sin(theta_etilt) sin(phi_b)) / sqrt(N).  The array
  gain in the direction (theta, phi) is then
  |sum_m e^{j pi m (cos theta - cos theta_t)}|^2 / M x
  |sum_n e^{j pi n (sin theta sin phi - sin theta_t sin phi_b)}|^2 / N
  (M N in the steered direction).  The beam codebook (azimuths spread evenly
  over the sector) is a deployment choice; TR 38.901 does not fix it.
* UE receive beams (since 2.4.0, optional): 1, 2 or 4 panels per UE with the
  element of TR 38.802 Table A.2.1-8 (model 1) and DFT receive beams formed
  the same way (:func:`ue_beam_gains_db`).  Polarisation is not modelled: a
  panel is an array of M x N elements of one polarisation.
"""
from __future__ import annotations

import math

import numpy as np

G_E_MAX_DB = 8.0          # TR 38.901 Table 7.3-1


def element_gain_db(theta_deg, phi_deg, am_db: float = 30.0):
    """Gain of one element: 8 dBi + A(theta, phi) of Table 7.3-1 (3 dB beam widths 65 deg, SLA_V 30 dB, front-to-back
    ratio A_m ``am_db``, 30 dB in the table)."""
    av = -np.minimum(12.0 * ((theta_deg - 90.0) / 65.0) ** 2, 30.0)
    ah = -np.minimum(12.0 * (phi_deg / 65.0) ** 2, am_db)
    return 8.0 - np.minimum(-(av + ah), am_db)


def ula_gain(psi, n: int):
    """|sum_{k<n} exp(j k psi)|^2 / n for phase steps ``psi`` [rad] (array factor, peak n)."""
    psi = np.asarray(psi)
    if psi.dtype != np.float32:
        psi = psi.astype(float)
    s = np.sin(0.5 * psi)
    small = np.abs(s) < 1e-12
    r = np.sin(0.5 * n * psi) / np.where(small, 1.0, s)
    return np.where(small, float(n), r * r / n)


def beam_azimuths_deg(n_ssb: int, span_deg: float) -> np.ndarray:
    """Azimuths of the SSB beams relative to the sector boresight, spread evenly over ``span_deg``."""
    return -0.5 * span_deg + (np.arange(n_ssb) + 0.5) * span_deg / n_ssb


def beam_gain_db(theta_deg, phi_deg, beam_phi_deg, tilt_deg: float, m: int, n: int, am_db: float = 30.0,
                 element=None):
    """Gain [dBi] of the SSB beams towards (theta, phi).

    ``theta_deg`` and ``phi_deg`` (any shape S) are the zenith angle and the azimuth
    from the sector boresight; ``beam_phi_deg`` (B,) the beam azimuths.  Returns
    shape S + (B,): element gain + vertical + horizontal array gain.  ``am_db`` is A_m of the element (Table 7.3-1:
    30 dB); ``element`` (since 2.4.0) replaces the element pattern by a function of (theta, phi) [dBi].
    """
    dt = np.float32 if np.asarray(theta_deg).dtype == np.float32 else float
    th = np.radians(np.asarray(theta_deg, dtype=dt))
    ph = np.radians(np.asarray(phi_deg, dtype=dt))
    tt = math.radians(tilt_deg)
    pb = np.radians(np.asarray(beam_phi_deg, dtype=dt))
    if element is None:
        ge = element_gain_db(np.asarray(theta_deg, dtype=dt), np.asarray(phi_deg, dtype=dt), am_db)
    else:
        ge = element(np.asarray(theta_deg, dtype=dt), np.asarray(phi_deg, dtype=dt))
    gv = ula_gain(dt(math.pi) * (np.cos(th) - dt(math.cos(tt))), m)
    gh = ula_gain(dt(math.pi) * (np.sin(th) * np.sin(ph))[..., None] - dt(math.pi * math.sin(tt)) * np.sin(pb), n)
    return (ge + 10.0 * np.log10(np.maximum(gv, 1e-30)))[..., None] + 10.0 * np.log10(np.maximum(gh, 1e-30))


def wrap_deg(a):
    """Angle wrapped to [-180, 180) degrees."""
    return (np.asarray(a) + 180.0) % 360.0 - 180.0


# ---------------------------------------------------------------- UE receive beams (since 2.4.0)
#: element of UE antenna radiation pattern model 1, TR 38.802 V14.2.0 Table A.2.1-8: 3 dB beam widths, SLA_V,
#: A_m [deg, dB] and G_E,max [dBi]
UE_THETA_3DB = 90.0
UE_PHI_3DB = 90.0
UE_SLA_V_DB = 25.0
UE_AM_DB = 25.0
UE_G_E_MAX_DB = 5.0


def ue_element_gain_db(theta_deg, phi_deg):
    """Gain of one UE element [dBi] in the panel's coordinate system: G_E,max + A(theta, phi) of TR 38.802
    Table A.2.1-8 (model 1), A = -min(-(A_V + A_H), A_m), A_V = -min(12 ((theta - 90) / theta_3dB)^2, SLA_V),
    A_H = -min(12 (phi / phi_3dB)^2, A_m)."""
    av = -np.minimum(12.0 * ((theta_deg - 90.0) / UE_THETA_3DB) ** 2, UE_SLA_V_DB)
    ah = -np.minimum(12.0 * (phi_deg / UE_PHI_3DB) ** 2, UE_AM_DB)
    return UE_G_E_MAX_DB - np.minimum(-(av + ah), UE_AM_DB)


def ue_beam_gains_db(theta_deg, az_deg, bearing_deg, panels: int, step_deg: float, m: int, n: int,
                     beam_az_deg, tilt_deg: float) -> np.ndarray:
    """Gains [dBi] of the receive beams of a UE towards arrival directions (zenith ``theta_deg``, azimuth
    ``az_deg`` in the global system; any shape S).

    The first panel faces the bearing ``bearing_deg`` (shape S, or broadcastable), panel p faces
    ``bearing_deg + p * step_deg``; every panel is broadside to the horizon (Theta = 90 deg, TR 38.802
    Table A.2.1-4), so the zenith angle in its system is the global one.  The receive beams of a panel are
    DFT beams (as in :func:`beam_gain_db`) steered to ``tilt_deg`` and the azimuths ``beam_az_deg`` (Q,)
    from the panel's broadside.  Returns shape S + (panels, Q): element gain + vertical + horizontal array
    gain, peak G_E,max + 10 log10(M N).
    """
    th = np.asarray(theta_deg, dtype=float)
    out = []
    for p in range(panels):
        phi = wrap_deg(np.asarray(az_deg, dtype=float) - np.asarray(bearing_deg, dtype=float) - p * step_deg)
        out.append(beam_gain_db(th, phi, beam_az_deg, tilt_deg, m, n, element=ue_element_gain_db))
    return np.stack(out, axis=-2)
