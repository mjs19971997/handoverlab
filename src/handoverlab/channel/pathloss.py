# SPDX-License-Identifier: MIT
"""Path loss and LOS probability of 3GPP TR 38.901 (Tables 7.4.1-1 and 7.4.2-1).

Implemented: UMi street canyon and UMa, LOS and NLOS, outdoor users; since
1.7.0 also RMa (rural macro) and InH-Office (indoor hotspot; LOS probability
of the mixed office).  Distances in metres, carrier frequency in GHz, results
in dB.  The formulas are specified for 0.5-100 GHz, RMa for 0.5-30 GHz
(Table 7.4.1-1 note 2).
"""
from __future__ import annotations

import math

import numpy as np

C0 = 299792458.0
#: speed of light in the breakpoint distances of TR 38.901 Table 7.4.1-1 (notes 1 and 5: c = 3.0e8 m/s); since
#: 2.0.0 the default (``radio.breakpoint_c_mps``), 1.x used the exact value C0
C_TR = 3.0e8


def breakpoint_distance(fc_ghz: float, h_bs: float, h_ut: float, h_e: float = 1.0, c: float = C_TR) -> float:
    """d'_BP = 4 h'_BS h'_UT f_c / c with effective heights h' = h - h_E [m] (note 1: c = 3.0e8 m/s)."""
    return 4.0 * (h_bs - h_e) * (h_ut - h_e) * fc_ghz * 1e9 / c


def umi_los(d2d, fc_ghz: float, h_bs: float = 10.0, h_ut: float = 1.5, c: float = C_TR):
    """UMi street canyon, LOS (PL1 below the breakpoint distance, PL2 above)."""
    dh2 = (h_bs - h_ut) ** 2
    d3 = np.sqrt(d2d * d2d + dh2)
    dbp = breakpoint_distance(fc_ghz, h_bs, h_ut, c=c)
    lf = 20.0 * math.log10(fc_ghz)
    pl1 = 32.4 + 21.0 * np.log10(d3) + lf
    pl2 = 32.4 + 40.0 * np.log10(d3) + lf - 9.5 * math.log10(dbp * dbp + dh2)
    return np.where(d2d <= dbp, pl1, pl2)


def _umi_nlos_prime(d2d, fc_ghz, h_bs, h_ut):
    d3 = np.sqrt(d2d * d2d + (h_bs - h_ut) ** 2)
    return 35.3 * np.log10(d3) + 22.4 + 21.3 * math.log10(fc_ghz) - 0.3 * (h_ut - 1.5)


def umi_nlos(d2d, fc_ghz: float, h_bs: float = 10.0, h_ut: float = 1.5, c: float = C_TR):
    """UMi street canyon, NLOS: max(PL_LOS, PL'_NLOS)."""
    return np.maximum(umi_los(d2d, fc_ghz, h_bs, h_ut, c), _umi_nlos_prime(d2d, fc_ghz, h_bs, h_ut))


def uma_los(d2d, fc_ghz: float, h_bs: float = 25.0, h_ut: float = 1.5, c: float = C_TR):
    """UMa, LOS (effective environment height 1 m)."""
    dh2 = (h_bs - h_ut) ** 2
    d3 = np.sqrt(d2d * d2d + dh2)
    dbp = breakpoint_distance(fc_ghz, h_bs, h_ut, c=c)
    lf = 20.0 * math.log10(fc_ghz)
    pl1 = 28.0 + 22.0 * np.log10(d3) + lf
    pl2 = 28.0 + 40.0 * np.log10(d3) + lf - 9.0 * math.log10(dbp * dbp + dh2)
    return np.where(d2d <= dbp, pl1, pl2)


def _uma_nlos_prime(d2d, fc_ghz, h_bs, h_ut):
    d3 = np.sqrt(d2d * d2d + (h_bs - h_ut) ** 2)
    return 13.54 + 39.08 * np.log10(d3) + 20.0 * math.log10(fc_ghz) - 0.6 * (h_ut - 1.5)


def uma_nlos(d2d, fc_ghz: float, h_bs: float = 25.0, h_ut: float = 1.5, c: float = C_TR):
    """UMa, NLOS: max(PL_LOS, PL'_NLOS)."""
    return np.maximum(uma_los(d2d, fc_ghz, h_bs, h_ut, c), _uma_nlos_prime(d2d, fc_ghz, h_bs, h_ut))


RMA_W_M = 20.0          # average street width W of the RMa model (default of Table 7.4.1-1)
RMA_H_M = 5.0           # average building height h of the RMa model (default)


def rma_breakpoint(fc_ghz: float, h_bs: float, h_ut: float, c: float = C_TR) -> float:
    """d_BP = 2 pi h_BS h_UT f_c / c with the actual antenna heights (Table 7.4.1-1 note 5: c = 3.0e8 m/s) [m]."""
    return 2.0 * math.pi * h_bs * h_ut * fc_ghz * 1e9 / c


def _rma_pl1(d3, fc_ghz, h=RMA_H_M):
    return (20.0 * np.log10(40.0 * math.pi * d3 * fc_ghz / 3.0) + min(0.03 * h ** 1.72, 10.0) * np.log10(d3)
            - min(0.044 * h ** 1.72, 14.77) + 0.002 * math.log10(h) * d3)


def rma_los(d2d, fc_ghz: float, h_bs: float = 35.0, h_ut: float = 1.5, c: float = C_TR):
    """RMa, LOS (since 1.7.0): PL1 up to the breakpoint d_BP, PL2 = PL1(d_BP) + 40 log10(d3D / d_BP) beyond.

    PL1 = 20 log10(40 pi d3D fc / 3) + min(0.03 h^1.72, 10) log10(d3D) - min(0.044 h^1.72, 14.77)
    + 0.002 log10(h) d3D with the default building height h = 5 m.  The breakpoint is a 2D
    distance; PL1(d_BP) is taken at the 3D distance of that point, so the loss is continuous.
    """
    d2d = np.asarray(d2d, dtype=float)
    dh2 = (h_bs - h_ut) ** 2
    d3 = np.sqrt(d2d * d2d + dh2)
    dbp = rma_breakpoint(fc_ghz, h_bs, h_ut, c)
    d3bp = math.sqrt(dbp * dbp + dh2)
    pl2 = _rma_pl1(d3bp, fc_ghz) + 40.0 * np.log10(d3 / d3bp)
    return np.where(d2d <= dbp, _rma_pl1(d3, fc_ghz), pl2)


def _rma_nlos_prime(d2d, fc_ghz, h_bs, h_ut, w=RMA_W_M, h=RMA_H_M):
    d3 = np.sqrt(np.asarray(d2d, dtype=float) ** 2 + (h_bs - h_ut) ** 2)
    return (161.04 - 7.1 * math.log10(w) + 7.5 * math.log10(h)
            - (24.37 - 3.7 * (h / h_bs) ** 2) * math.log10(h_bs)
            + (43.42 - 3.1 * math.log10(h_bs)) * (np.log10(d3) - 3.0) + 20.0 * math.log10(fc_ghz)
            - (3.2 * math.log10(11.75 * h_ut) ** 2 - 4.97))


def rma_nlos(d2d, fc_ghz: float, h_bs: float = 35.0, h_ut: float = 1.5, c: float = C_TR):
    """RMa, NLOS (since 1.7.0): max(PL_LOS, PL'_NLOS) with W = 20 m and h = 5 m."""
    return np.maximum(rma_los(d2d, fc_ghz, h_bs, h_ut, c), _rma_nlos_prime(d2d, fc_ghz, h_bs, h_ut))


def inh_los(d2d, fc_ghz: float, h_bs: float = 3.0, h_ut: float = 1.0, c: float = C_TR):
    """InH-Office, LOS (since 1.7.0): 32.4 + 17.3 log10(d3D) + 20 log10(fc), 1 m <= d3D <= 150 m."""
    d3 = np.sqrt(np.asarray(d2d, dtype=float) ** 2 + (h_bs - h_ut) ** 2)
    return 32.4 + 17.3 * np.log10(d3) + 20.0 * math.log10(fc_ghz)


def _inh_nlos_prime(d2d, fc_ghz, h_bs, h_ut):
    d3 = np.sqrt(np.asarray(d2d, dtype=float) ** 2 + (h_bs - h_ut) ** 2)
    return 38.3 * np.log10(d3) + 17.30 + 24.9 * math.log10(fc_ghz)


def inh_nlos(d2d, fc_ghz: float, h_bs: float = 3.0, h_ut: float = 1.0, c: float = C_TR):
    """InH-Office, NLOS (since 1.7.0): max(PL_LOS, 38.3 log10(d3D) + 17.30 + 24.9 log10(fc))."""
    return np.maximum(inh_los(d2d, fc_ghz, h_bs, h_ut), _inh_nlos_prime(d2d, fc_ghz, h_bs, h_ut))


_MODELS = {"umi_street_canyon": (umi_los, _umi_nlos_prime), "uma": (uma_los, _uma_nlos_prime)}
_OTHER = {"rma": (rma_los, rma_nlos), "inh_office": (inh_los, inh_nlos)}

#: names of all path-loss models
MODELS = ("umi_street_canyon", "uma", "rma", "inh_office")

# coefficients of the formulas above: LOS (A + B log10 d3 + 20 log10 fc; A + 40 log10 d3 + 20 log10 fc - C
# log10(d'BP^2 + dh^2)) and NLOS' (D log10 d3 + E + F log10 fc - G (h_UT - 1.5))
_COEF = {"umi_street_canyon": (32.4, 21.0, 9.5, 35.3, 22.4, 21.3, 0.3),
         "uma": (28.0, 22.0, 9.0, 39.08, 13.54, 20.0, 0.6)}


def path_loss(d2d, los, model: str, fc_ghz: float, h_bs: float, h_ut: float, c: float = C_TR,
              d_min: float = 0.0):
    """Path loss of ``model`` (one of :data:`MODELS`) for a boolean LOS state.

    ``c`` is the speed of light in the breakpoint distances (TR 38.901 notes 1 and 5: 3.0e8 m/s; 1.x used the
    exact value) and ``d_min`` the smallest 2D distance the formulas are evaluated at (since 2.0.0: 10 m, the
    lower end of the applicability range of RMa, UMa and UMi in Table 7.4.1-1; InH has d3D >= 1 m anyway and
    is not limited).  Both come from the scenario (:func:`radio_kwargs`).

    For UMi and UMa it gives exactly the values of ``np.where(los, X_los(...), X_nlos(...))``,
    but computes the logarithm of the distance once, the second breakpoint
    branch only where it applies and the rest in place (the radio map of a
    large grid evaluates tens of millions of links).  RMa and InH-Office use
    that expression directly.
    """
    if d_min > 0.0 and model != "inh_office":
        d2d = np.maximum(np.asarray(d2d, dtype=float), d_min)
    if model in _OTHER:
        f_los, f_nlos = _OTHER[model]
        d2d = np.asarray(d2d, dtype=float)
        los = np.broadcast_to(np.asarray(los, dtype=bool), d2d.shape)
        pl = f_los(d2d, fc_ghz, h_bs, h_ut, c)
        if not los.all():
            pl = np.where(los, pl, f_nlos(d2d, fc_ghz, h_bs, h_ut, c))
        return pl
    if model not in _COEF:
        raise ValueError("unknown path-loss model %r; known: %s" % (model, ", ".join(MODELS)))
    c_light = c                                          # the coefficients below reuse the letter c
    a, b, c, d, e, f, g = _COEF[model]
    d2d = np.asarray(d2d, dtype=float)
    scalar = d2d.ndim == 0
    if scalar:
        d2d = d2d.reshape(1)
    dh2 = (h_bs - h_ut) ** 2
    lg = np.log10(np.sqrt(d2d * d2d + dh2))
    lf = 20.0 * math.log10(fc_ghz)
    dbp = breakpoint_distance(fc_ghz, h_bs, h_ut, c=c_light)
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


def p_los_rma(d2d):
    """LOS probability, RMa (since 1.7.0): 1 up to 10 m, then exp(-(d2D - 10) / 1000)."""
    d = np.asarray(d2d, dtype=float)
    return np.where(d <= 10.0, 1.0, np.exp(-(d - 10.0) / 1000.0))


def p_los_inh_mixed(d2d):
    """LOS probability, InH mixed office (since 1.7.0).

    1 up to 1.2 m, exp(-(d2D - 1.2) / 4.7) up to 6.5 m, then 0.32 exp(-(d2D - 6.5) / 32.6).
    """
    d = np.asarray(d2d, dtype=float)
    return np.where(d <= 1.2, 1.0, np.where(d < 6.5, np.exp(-(d - 1.2) / 4.7), 0.32 * np.exp(-(d - 6.5) / 32.6)))


def radio_kwargs(radio) -> dict:
    """Keyword arguments of :func:`path_loss` taken from a ``RadioConfig`` (breakpoint constant, minimum distance)."""
    return {"c": getattr(radio, "breakpoint_c_mps", C_TR), "d_min": getattr(radio, "pl_min_distance_m", 0.0)}


def los_shadow_sd(d2d, radio):
    """Shadowing standard deviation of LOS links [dB]: a scalar, or an array of the shape of ``d2d``.

    ``radio.shadow_los_far_db`` (since 1.7.0) applies beyond the breakpoint distance of the model
    (RMa: 6 dB instead of 4 dB in TR 38.901 Table 7.4.1-1); unset, every LOS link has
    ``radio.shadow_los_db``.
    """
    far = radio.shadow_los_far_db
    if far is None:
        return radio.shadow_los_db
    if radio.pathloss == "rma":
        dbp = rma_breakpoint(radio.carrier_ghz, radio.bs_height_m, radio.ue_height_m,
                             getattr(radio, "breakpoint_c_mps", C_TR))
    else:
        dbp = breakpoint_distance(radio.carrier_ghz, radio.bs_height_m, radio.ue_height_m,
                                  c=getattr(radio, "breakpoint_c_mps", C_TR))
    return np.where(np.asarray(d2d) > dbp, far, radio.shadow_los_db)


def soft_los_power_weight(z, fc_ghz: float, d_m: float = 20.0):
    """Weight LOS_soft^2 of the LOS power under the soft LOS state (since 1.7.0).

    TR 38.901 clause 7.6.3.3 (V17.0.0), Eq. (7.6-18): LOS_soft = 1/2 + arctan(sqrt(d / lambda) z) / pi
    with ``z = G + F(d)``, ``F(d) = sqrt(2) erf^-1(2 Pr_LOS(d) - 1)`` and the wavelength lambda [m]
    (``d`` is the 20 of the equation).  Eq. (7.6-19), H = H_LOS LOS_soft + H_NLOS sqrt(1 - LOS_soft^2),
    gives the power weights LOS_soft^2 (LOS) and 1 - LOS_soft^2 (NLOS).  For z > 0 the hard state is LOS.
    """
    lam = C0 / (fc_ghz * 1e9)
    s = 0.5 + np.arctan(math.sqrt(d_m / lam) * np.asarray(z, dtype=float)) / math.pi
    return s * s


def mix_db(w, g_los_db, g_nlos_db):
    """10 log10(w 10^(g_los/10) + (1 - w) 10^(g_nlos/10)): power mixture of two gains [dB]."""
    k = math.log(10.0) / 10.0
    w = np.asarray(w, dtype=float)
    with np.errstate(divide="ignore"):
        return np.logaddexp(np.log(w) + k * np.asarray(g_los_db, dtype=float),
                            np.log1p(-w) + k * np.asarray(g_nlos_db, dtype=float)) / k


def p_los(d2d, model: str):
    """LOS probability for the named path-loss model."""
    if model == "rma":
        return p_los_rma(d2d)
    if model == "inh_office":
        return p_los_inh_mixed(d2d)
    return p_los_umi(d2d) if model == "umi_street_canyon" else p_los_uma(d2d)
