# SPDX-License-Identifier: MIT
"""Fast fading with the tapped delay line (TDL) models of TR 38.901 (optional, since 2.2.0).

``radio.fast_fading`` selects one of TDL-A .. TDL-E (TR 38.901 V19.5.0 clause 7.7.2, Tables 7.7.2-1 to
7.7.2-5).  Each user-cell link fades independently:

* the normalised delays are scaled to the RMS delay spread ``radio.delay_spread_ns`` (Eq. 7.7-1,
  tau_scaled = tau_model x DS; Table 7.7.3-1 gives 10, 30, 100, 300 and 1000 ns as examples);
* for TDL-D and TDL-E the K-factor can be changed (``radio.fading_k_db``; Eq. 7.7.6-1 and 7.7.6-2, after
  which the delays are re-normalised to DS = 1);
* every Rayleigh tap is a sum of sinusoids with random arrival angles and phases, so that its Doppler
  spectrum tends to the classical (Jakes) shape with the maximum Doppler shift f_D = |v| / lambda_0 (|v| the
  user's speed, lambda_0 the carrier wavelength); the phases advance by one step at a time;
* the LOS tap of TDL-D / TDL-E is a specular component with the Doppler shift f_S = 0.7 f_D;
* the tap powers are normalised to a unit sum, so the mean power gain of a link is 1 and the large-scale model
  is unchanged on average.

The channel is evaluated at a few frequencies: points spread over the 24-PRB band of the hypothetical PDCCH of
radio-link monitoring (TS 38.133 Tables 8.1.2.1-1/-2) and points spread over the carrier bandwidth (the
transmission bandwidth configuration of TS 38.101-1/-2 Table 5.3.2-1).
"""
from __future__ import annotations

import math
from typing import Dict, Optional, Tuple

import numpy as np

C0 = 3.0e8                      # TR 38.901 Table 7.4.1-1 note: c = 3.0 x 10^8 m/s

#: TR 38.901 V19.5.0 Tables 7.7.2-1 to 7.7.2-5: (normalised delay, power [dB], kind) per tap; kind "L" is the LOS
#: path of TDL-D / TDL-E (the Rayleigh part of their first tap follows it at the same delay)
TDL: Dict[str, Tuple[Tuple[float, float, str], ...]] = {
    "tdl-a": ((0.0000, -13.4, "R"), (0.3819, 0.0, "R"), (0.4025, -2.2, "R"), (0.5868, -4.0, "R"),
              (0.4610, -6.0, "R"), (0.5375, -8.2, "R"), (0.6708, -9.9, "R"), (0.5750, -10.5, "R"),
              (0.7618, -7.5, "R"), (1.5375, -15.9, "R"), (1.8978, -6.6, "R"), (2.2242, -16.7, "R"),
              (2.1718, -12.4, "R"), (2.4942, -15.2, "R"), (2.5119, -10.8, "R"), (3.0582, -11.3, "R"),
              (4.0810, -12.7, "R"), (4.4579, -16.2, "R"), (4.5695, -18.3, "R"), (4.7966, -18.9, "R"),
              (5.0066, -16.6, "R"), (5.3043, -19.9, "R"), (9.6586, -29.7, "R")),
    "tdl-b": ((0.0000, 0.0, "R"), (0.1072, -2.2, "R"), (0.2155, -4.0, "R"), (0.2095, -3.2, "R"),
              (0.2870, -9.8, "R"), (0.2986, -1.2, "R"), (0.3752, -3.4, "R"), (0.5055, -5.2, "R"),
              (0.3681, -7.6, "R"), (0.3697, -3.0, "R"), (0.5700, -8.9, "R"), (0.5283, -9.0, "R"),
              (1.1021, -4.8, "R"), (1.2756, -5.7, "R"), (1.5474, -7.5, "R"), (1.7842, -1.9, "R"),
              (2.0169, -7.6, "R"), (2.8294, -12.2, "R"), (3.0219, -9.8, "R"), (3.6187, -11.4, "R"),
              (4.1067, -14.9, "R"), (4.2790, -9.2, "R"), (4.7834, -11.3, "R")),
    "tdl-c": ((0.0, -4.4, "R"), (0.2099, -1.2, "R"), (0.2219, -3.5, "R"), (0.2329, -5.2, "R"),
              (0.2176, -2.5, "R"), (0.6366, 0.0, "R"), (0.6448, -2.2, "R"), (0.6560, -3.9, "R"),
              (0.6584, -7.4, "R"), (0.7935, -7.1, "R"), (0.8213, -10.7, "R"), (0.9336, -11.1, "R"),
              (1.2285, -5.1, "R"), (1.3083, -6.8, "R"), (2.1704, -8.7, "R"), (2.7105, -13.2, "R"),
              (4.2589, -13.9, "R"), (4.6003, -13.9, "R"), (5.4902, -15.8, "R"), (5.6077, -17.1, "R"),
              (6.3065, -16.0, "R"), (6.6374, -15.7, "R"), (7.0427, -21.6, "R"), (8.6523, -22.8, "R")),
    "tdl-d": ((0.0, -0.2, "L"), (0.0, -13.5, "R"), (0.035, -18.8, "R"), (0.612, -21.0, "R"), (1.363, -22.8, "R"),
              (1.405, -17.9, "R"), (1.804, -20.1, "R"), (2.596, -21.9, "R"), (1.775, -22.9, "R"),
              (4.042, -27.8, "R"), (7.937, -23.6, "R"), (9.424, -24.8, "R"), (9.708, -30.0, "R"),
              (12.525, -27.7, "R")),
    "tdl-e": ((0.0, -0.03, "L"), (0.0, -22.03, "R"), (0.5133, -15.8, "R"), (0.5440, -18.1, "R"),
              (0.5630, -19.8, "R"), (0.5440, -22.9, "R"), (0.7112, -22.4, "R"), (1.9092, -18.6, "R"),
              (1.9293, -20.8, "R"), (1.9589, -22.6, "R"), (2.6426, -22.3, "R"), (3.7136, -25.6, "R"),
              (5.4524, -20.2, "R"), (12.0034, -29.8, "R"), (20.6519, -29.2, "R")),
}
MODELS = tuple(TDL)
#: K-factor of the first tap given in the notes of Tables 7.7.2-4 / 7.7.2-5 [dB]
K_MODEL_DB = {"tdl-d": 13.3, "tdl-e": 22.0}
N_SINUSOIDS = 32                # sinusoids per Rayleigh tap (16 left a measurable deviation from Rayleigh)
PDCCH_PRB = 24                  # bandwidth of the hypothetical PDCCH (TS 38.133 Tables 8.1.2.1-1/-2)


def rms_delay_spread(delays: np.ndarray, powers: np.ndarray) -> float:
    """RMS delay spread of a power delay profile (linear powers)."""
    p = powers / powers.sum()
    m = float((p * delays).sum())
    return math.sqrt(max(float((p * delays ** 2).sum()) - m * m, 0.0))


def tdl_profile(model: str, ds_s: float, k_db: Optional[float] = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Delays [s], linear powers (unit sum) and LOS flags of the taps of ``model`` at RMS delay spread ``ds_s``.

    With ``k_db`` (TDL-D / TDL-E only) the Rayleigh tap powers follow Eq. 7.7.6-1, P_scaled = P_model - K_desired
    + K_model, with K_model of Eq. 7.7.6-2: the LOS power over the sum of the powers of the taps that are rescaled
    (the Rayleigh taps); the delays are then divided by the RMS delay spread that results, so that DS = 1 before
    the scaling of Eq. 7.7-1.
    """
    taps = TDL[model]
    tau = np.array([t[0] for t in taps])
    p_db = np.array([t[1] for t in taps])
    los = np.array([t[2] == "L" for t in taps])
    if k_db is not None:
        if not los.any():
            raise ValueError("a K-factor applies to the LOS models tdl-d and tdl-e only")
        k_model = p_db[los][0] - 10.0 * np.log10(np.sum(10.0 ** (p_db[~los] / 10.0)))    # Eq. 7.7.6-2
        p_db = np.where(los, p_db, p_db - k_db + k_model)                                  # Eq. 7.7.6-1
        p_lin = 10.0 ** (p_db / 10.0)
        tau = tau / rms_delay_spread(tau, p_lin)
    p = 10.0 ** (p_db / 10.0)
    return tau * ds_s, p / p.sum(), los


def k_factor_db(model: str, k_db: Optional[float] = None) -> float:
    """K-factor of Eq. 7.7.6-2: LOS power over the sum of the Rayleigh tap powers [dB]."""
    _, p, los = tdl_profile(model, 1.0, k_db)
    return float(10.0 * np.log10(p[los].sum() / p[~los].sum()))


def first_tap_k_db(model: str) -> float:
    """K-factor of the first tap alone, as the notes of Tables 7.7.2-4 / 7.7.2-5 give it [dB]."""
    _, p, los = tdl_profile(model, 1.0)
    first = np.nonzero(los)[0][0]
    return float(10.0 * np.log10(p[first] / p[first + 1]))


def frequencies(bandwidth_mhz: float, scs_khz: float, n_rb: Optional[int], n_rlm: int = 4,
                n_data: int = 8) -> Tuple[np.ndarray, np.ndarray]:
    """Offsets [Hz] from the carrier centre of the PDCCH points (24 PRBs around the centre) and the data points."""
    rb_hz = 12.0 * scs_khz * 1e3
    n = n_rb if n_rb is not None else int(bandwidth_mhz * 1e3 / (12.0 * scs_khz))
    w_rlm = min(PDCCH_PRB, n) * rb_hz
    w_data = n * rb_hz
    centre = lambda w, k: (np.arange(k) + 0.5) / k * w - w / 2.0          # noqa: E731
    return centre(w_rlm, n_rlm), centre(w_data, n_data)


class TdlFading:
    """Independent TDL fading of ``U`` x ``M`` links evaluated at the frequencies ``f_hz``.

    ``fd`` (U,) are the users' maximum Doppler shifts [Hz]; each call of :meth:`gains` advances every link by one
    step of ``dt`` seconds and returns |H|^2 (U, M, F).  The draws come from ``rng`` once, at construction; every
    sinusoid then turns by a fixed phase per step (one complex multiplication), as the speed of a user is constant.
    """

    def __init__(self, rng: np.random.Generator, U: int, M: int, model: str, ds_s: float, f_hz: np.ndarray,
                 dt: float, fd: np.ndarray, k_db: Optional[float] = None, n_sin: int = N_SINUSOIDS):
        tau, p, los = tdl_profile(model, ds_s, k_db)
        ray = ~los
        L = int(ray.sum())
        w = 2.0 * np.pi * dt * np.asarray(fd, dtype=float)                       # phase per step at f_D (U,)
        # Rayleigh taps: sum of n_sin sinusoids with uniform arrival angles and phases (Clarke / Jakes spectrum)
        cos_a = np.cos(rng.uniform(0.0, 2.0 * np.pi, (U, M, L, n_sin)))
        self.z = np.exp(1j * rng.uniform(0.0, 2.0 * np.pi, (U, M, L, n_sin))).reshape(U, M, L * n_sin)
        self.rot = np.exp(1j * w[:, None, None, None] * cos_a).reshape(U, M, L * n_sin)
        f = np.asarray(f_hz, dtype=float)
        e_ray = np.sqrt(p[ray])[:, None] * np.exp(-2j * np.pi * tau[ray][:, None] * f[None, :])        # (L, F)
        self.e = np.repeat(e_ray, n_sin, axis=0) / math.sqrt(n_sin)                                    # (L n, F)
        self.los = bool(los.any())
        if self.los:                    # specular LOS component at f_S = 0.7 f_D with a random start phase
            self.e_los = np.sqrt(p[los][0]) * np.exp(-2j * np.pi * tau[los][0] * f)                    # (F,)
            self.z_los = np.exp(1j * rng.uniform(0.0, 2.0 * np.pi, (U, M)))
            self.rot_los = np.exp(1j * 0.7 * w)[:, None]
        self.n_f = len(f)

    def gains(self) -> np.ndarray:
        """|H|^2 of every link at every frequency after one more step (U, M, F)."""
        self.z *= self.rot
        h = self.z @ self.e                                                        # (U, M, F)
        if self.los:
            self.z_los *= self.rot_los
            h += self.z_los[..., None] * self.e_los
        return h.real ** 2 + h.imag ** 2
