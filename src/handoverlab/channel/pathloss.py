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


def path_loss(d2d, los, model: str, fc_ghz: float, h_bs: float, h_ut: float):
    """Path loss of ``model`` ("umi_street_canyon" or "uma") for a boolean LOS state."""
    try:
        f_los, f_nlos_prime = _MODELS[model]
    except KeyError:
        raise ValueError("unknown path-loss model %r; known: %s" % (model, ", ".join(_MODELS)))
    pl_los = f_los(d2d, fc_ghz, h_bs, h_ut)
    return np.where(los, pl_los, np.maximum(pl_los, f_nlos_prime(d2d, fc_ghz, h_bs, h_ut)))


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
