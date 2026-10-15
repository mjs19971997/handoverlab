# SPDX-License-Identifier: MIT
"""Path loss and LOS probability of 3GPP TR 38.901 (Tables 7.4.1-1 and 7.4.2-1).

Implemented: UMi street canyon and UMa, LOS and NLOS, outdoor users.
Distances in metres, carrier frequency in GHz, results in dB.  The formulas
are specified for 0.5-100 GHz.
"""
from __future__ import annotations

import math

import numpy as np

C0 = 299792458.0


def breakpoint_distance(fc_ghz: float, h_bs: float, h_ut: float, h_e: float = 1.0) -> float:
    """d'_BP = 4 h'_BS h'_UT f_c / c with effective heights h' = h - h_E [m]."""
    return 4.0 * (h_bs - h_e) * (h_ut - h_e) * fc_ghz * 1e9 / C0


def umi_los(d2d, fc_ghz: float, h_bs: float = 10.0, h_ut: float = 1.5):
    """UMi street canyon, LOS (PL1 below the breakpoint distance, PL2 above)."""
    dh2 = (h_bs - h_ut) ** 2
    d3 = np.sqrt(d2d * d2d + dh2)
    dbp = breakpoint_distance(fc_ghz, h_bs, h_ut)
    lf = 20.0 * math.log10(fc_ghz)
    pl1 = 32.4 + 21.0 * np.log10(d3) + lf
    pl2 = 32.4 + 40.0 * np.log10(d3) + lf - 9.5 * math.log10(dbp * dbp + dh2)
    return np.where(d2d <= dbp, pl1, pl2)


def _umi_nlos_prime(d2d, fc_ghz, h_bs, h_ut):
    d3 = np.sqrt(d2d * d2d + (h_bs - h_ut) ** 2)
    return 35.3 * np.log10(d3) + 22.4 + 21.3 * math.log10(fc_ghz) - 0.3 * (h_ut - 1.5)


def umi_nlos(d2d, fc_ghz: float, h_bs: float = 10.0, h_ut: float = 1.5):
    """UMi street canyon, NLOS: max(PL_LOS, PL'_NLOS)."""
    return np.maximum(umi_los(d2d, fc_ghz, h_bs, h_ut), _umi_nlos_prime(d2d, fc_ghz, h_bs, h_ut))


def uma_los(d2d, fc_ghz: float, h_bs: float = 25.0, h_ut: float = 1.5):
    """UMa, LOS (effective environment height 1 m)."""
    dh2 = (h_bs - h_ut) ** 2
    d3 = np.sqrt(d2d * d2d + dh2)
    dbp = breakpoint_distance(fc_ghz, h_bs, h_ut)
    lf = 20.0 * math.log10(fc_ghz)
    pl1 = 28.0 + 22.0 * np.log10(d3) + lf
    pl2 = 28.0 + 40.0 * np.log10(d3) + lf - 9.0 * math.log10(dbp * dbp + dh2)
    return np.where(d2d <= dbp, pl1, pl2)


def _uma_nlos_prime(d2d, fc_ghz, h_bs, h_ut):
    d3 = np.sqrt(d2d * d2d + (h_bs - h_ut) ** 2)
    return 13.54 + 39.08 * np.log10(d3) + 20.0 * math.log10(fc_ghz) - 0.6 * (h_ut - 1.5)


def uma_nlos(d2d, fc_ghz: float, h_bs: float = 25.0, h_ut: float = 1.5):
    """UMa, NLOS: max(PL_LOS, PL'_NLOS)."""
    return np.maximum(uma_los(d2d, fc_ghz, h_bs, h_ut), _uma_nlos_prime(d2d, fc_ghz, h_bs, h_ut))


_MODELS = {"umi_street_canyon": (umi_los, _umi_nlos_prime), "uma": (uma_los, _uma_nlos_prime)}

# coefficients of the formulas above: LOS (A + B log10 d3 + 20 log10 fc; A + 40 log10 d3 + 20 log10 fc - C
# log10(d'BP^2 + dh^2)) and NLOS' (D log10 d3 + E + F log10 fc - G (h_UT - 1.5))
_COEF = {"umi_street_canyon": (32.4, 21.0, 9.5, 35.3, 22.4, 21.3, 0.3),
         "uma": (28.0, 22.0, 9.0, 39.08, 13.54, 20.0, 0.6)}


def path_loss(d2d, los, model: str, fc_ghz: float, h_bs: float, h_ut: float):
    """Path loss of ``model`` ("umi_street_canyon" or "uma") for a boolean LOS state.

    Gives exactly the values of ``np.where(los, X_los(...), X_nlos(...))``,
    but computes the logarithm of the distance once, the second breakpoint
    branch only where it applies and the rest in place (the radio map of a
    large grid evaluates tens of millions of links).
    """
    if model not in _COEF:
        raise ValueError("unknown path-loss model %r; known: %s" % (model, ", ".join(_MODELS)))
    a, b, c, d, e, f, g = _COEF[model]
    d2d = np.asarray(d2d, dtype=float)
    scalar = d2d.ndim == 0
    if scalar:
        d2d = d2d.reshape(1)
    dh2 = (h_bs - h_ut) ** 2
    lg = np.log10(np.sqrt(d2d * d2d + dh2))
    lf = 20.0 * math.log10(fc_ghz)
    dbp = breakpoint_distance(fc_ghz, h_bs, h_ut)
    pl = b * lg
    pl += a                                             # same rounding as a + b * lg
    pl += lf
    far = d2d > dbp
    if far.any():
        pl[far] = a + 40.0 * lg[far] + lf - c * math.log10(dbp * dbp + dh2)
    los = np.broadcast_to(np.asarray(los, dtype=bool), pl.shape)
    if not los.all():
        nl = d * lg                                     # NLOS' over the whole array, in place
        nl += e
        nl += f * math.log10(fc_ghz)
        nl -= g * (h_ut - 1.5)
        np.maximum(pl, nl, out=nl)
        np.copyto(pl, nl, where=~los)
    return pl.reshape(()) if scalar else pl


def p_los_umi(d2d):
    """LOS probability, UMi street canyon."""
    d = np.maximum(np.asarray(d2d, dtype=float), 1e-9)
    return np.where(d <= 18.0, 1.0, 18.0 / d + np.exp(-d / 36.0) * (1.0 - 18.0 / d))


def p_los_uma(d2d):
    """LOS probability, UMa, for h_UT <= 13 m."""
    d = np.maximum(np.asarray(d2d, dtype=float), 1e-9)
    return np.where(d <= 18.0, 1.0, 18.0 / d + np.exp(-d / 63.0) * (1.0 - 18.0 / d))


def p_los(d2d, model: str):
    """LOS probability for the named path-loss model."""
    return p_los_umi(d2d) if model == "umi_street_canyon" else p_los_uma(d2d)
