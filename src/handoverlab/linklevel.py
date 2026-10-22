# SPDX-License-Identifier: MIT
"""Link-level quantities of the PDSCH for the optional slot scheduler (since 2.2.0).

* :data:`MCS_TABLE1`: MCS index table 1 for PDSCH (TS 38.214 V19.2.0 Table 5.1.3.1-1): modulation order Q_m and
  target code rate R x 1024 for I_MCS 0 to 28.
* :data:`CQI_TABLE1`: the 4-bit CQI table (Table 5.2.2.1-2).
* :func:`tbs`: transport block size by TS 38.214 clause 5.1.3.2 (steps 1 to 4, Table 5.1.3.2-1).
* :func:`bler`: block error probability of a transport block on a channel with a given (effective) SINR. 3GPP
  gives no such curve (it is a property of the receiver); HandoverLab uses the normal approximation of the
  finite-blocklength error probability (Polyanskiy, Poor and Verdu, IEEE Trans. Inf. Theory 56(5), 2010) on the
  bit channel of the modulation: the mutual information C and the dispersion V per coded bit of BICM with Gray
  mapping, P_e = Q((n C - k + log2(n) / 2) / sqrt(n V)) for n coded and k information bits, evaluated at the SINR
  reduced by an implementation loss (``loss_db``, an assumption standing for the gap of a practical LDPC decoder).
"""
from __future__ import annotations

import math
from functools import lru_cache
from typing import Tuple

import numpy as np

#: TS 38.214 V19.2.0 Table 5.1.3.1-1, I_MCS -> (Q_m, R x 1024)
MCS_TABLE1: Tuple[Tuple[int, float], ...] = (
    (2, 120), (2, 157), (2, 193), (2, 251), (2, 308), (2, 379), (2, 449), (2, 526), (2, 602), (2, 679),
    (4, 340), (4, 378), (4, 434), (4, 490), (4, 553), (4, 616), (4, 658),
    (6, 438), (6, 466), (6, 517), (6, 567), (6, 616), (6, 666), (6, 719), (6, 772), (6, 822), (6, 873), (6, 910),
    (6, 948))
#: TS 38.214 V19.2.0 Table 5.2.2.1-2, CQI 1..15 -> (Q_m, R x 1024); CQI 0 is "out of range"
CQI_TABLE1: Tuple[Tuple[int, float], ...] = (
    (2, 78), (2, 120), (2, 193), (2, 308), (2, 449), (2, 602), (4, 378), (4, 490), (4, 616), (6, 466), (6, 567),
    (6, 666), (6, 772), (6, 873), (6, 948))
#: TS 38.214 V19.2.0 Table 5.1.3.2-1 (TBS for N_info <= 3824)
TBS_TABLE = (24, 32, 40, 48, 56, 64, 72, 80, 88, 96, 104, 112, 120, 128, 136, 144, 152, 160, 168, 176, 184, 192,
             208, 224, 240, 256, 272, 288, 304, 320, 336, 352, 368, 384, 408, 432, 456, 480, 504, 528, 552, 576, 608,
             640, 672, 704, 736, 768, 808, 848, 888, 928, 984, 1032, 1064, 1128, 1160, 1192, 1224, 1256, 1288, 1320,
             1352, 1416, 1480, 1544, 1608, 1672, 1736, 1800, 1864, 1928, 2024, 2088, 2152, 2216, 2280, 2408, 2472,
             2536, 2600, 2664, 2728, 2792, 2856, 2976, 3104, 3240, 3368, 3496, 3624, 3752, 3824)


def spectral_efficiency(mcs: int) -> float:
    q, r = MCS_TABLE1[mcs]
    return q * r / 1024.0


def n_re(n_prb: int, n_symb: int = 12, n_dmrs: int = 12, n_oh: int = 0) -> int:
    """Step 1: N_RE = min(156, N'_RE) n_PRB with N'_RE = 12 N_symb - N_DMRS - N_oh."""
    return min(156, 12 * n_symb - n_dmrs - n_oh) * n_prb


def tbs(n_re_total: int, mcs: int, layers: int = 1) -> int:
    """Transport block size [bit] of TS 38.214 clause 5.1.3.2 for ``n_re_total`` REs and MCS table 1."""
    q, r1024 = MCS_TABLE1[mcs]
    r = r1024 / 1024.0
    n_info = n_re_total * r * q * layers                                     # step 2
    if n_info <= 0:
        return 0
    if n_info <= 3824:                                                       # step 3
        n = max(3, math.floor(math.log2(n_info)) - 6)
        nq = max(24, (2 ** n) * math.floor(n_info / 2 ** n))
        return next(t for t in TBS_TABLE if t >= nq)
    n = math.floor(math.log2(n_info - 24)) - 5                               # step 4
    x = (n_info - 24) / 2 ** n
    nq = max(3840, (2 ** n) * math.floor(x + 0.5))                           # ties towards the next largest integer
    if r <= 0.25:
        c = math.ceil((nq + 24) / 3816)
        return 8 * c * math.ceil((nq + 24) / (8 * c)) - 24
    if nq > 8424:
        c = math.ceil((nq + 24) / 8424)
        return 8 * c * math.ceil((nq + 24) / (8 * c)) - 24
    return 8 * math.ceil((nq + 24) / 8) - 24


_GH_X, _GH_W = np.polynomial.hermite.hermgauss(48)


@lru_cache(maxsize=None)
def _bit_channel(q: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(SINR grid [dB], C, V) of the BICM bit channel of square 2^q-QAM with Gray mapping (two PAM dimensions)."""
    m = 2 ** (q // 2)                                                        # PAM levels per dimension
    a = math.sqrt(3.0 / (2.0 * (m * m - 1)))                                 # unit mean energy of the complex symbol
    lv = (2 * np.arange(m) - (m - 1)) * a
    gray = np.arange(m) ^ (np.arange(m) >> 1)
    bits = [(gray >> i) & 1 for i in range(q // 2)]
    db = np.linspace(-15.0, 35.0, 501)
    z = math.sqrt(2.0) * _GH_X
    w = _GH_W / math.sqrt(math.pi)
    sigma = np.sqrt(1.0 / (2.0 * 10.0 ** (db / 10.0)))[:, None, None, None]   # noise per real dimension
    # y for every SINR, transmitted level and quadrature node; distance terms to every candidate level
    y = lv[None, :, None, None] + sigma * z[None, None, :, None]               # (grid, m, nodes, 1)
    d = -((y - lv[None, None, None, :]) ** 2) / (2.0 * sigma * sigma)          # (grid, m, nodes, m)
    den = np.logaddexp.reduce(d, axis=-1)
    i_sum = np.zeros(len(db))
    i_sq = np.zeros(len(db))
    for b in bits:
        same = b[:, None] == b[None, :]                                        # (m sent, m candidate)
        num = np.logaddexp.reduce(np.where(same[None, :, None, :], d, -np.inf), axis=-1)
        info = 1.0 + (num - den) / math.log(2.0)                               # information density [bit]
        i_sum += (info * w[None, None, :]).sum(axis=(1, 2))
        i_sq += (info * info * w[None, None, :]).sum(axis=(1, 2))
    n = len(bits) * m
    cap = i_sum / n
    disp = np.maximum(i_sq / n - cap * cap, 1e-12)
    return db, cap, disp


def bit_capacity(q: int, sinr_db: np.ndarray) -> np.ndarray:
    """Mutual information per coded bit of 2^q-QAM (BICM, Gray) at ``sinr_db``."""
    db, cap, _ = _bit_channel(q)
    return np.interp(sinr_db, db, cap)


_QM = np.array([q for q, _ in MCS_TABLE1])


def bler_vec(sinr_db: np.ndarray, mcs: np.ndarray, tbs_bits: np.ndarray, n_coded: np.ndarray,
             loss_db: float = 1.0) -> np.ndarray:
    """:func:`bler` element by element for arrays of SINR, MCS, TBS and coded bits."""
    from scipy.special import ndtr
    s = np.asarray(sinr_db, dtype=float) - loss_db
    q = _QM[np.asarray(mcs, dtype=int)]
    c = np.empty_like(s)
    v = np.empty_like(s)
    for qm in (2, 4, 6):
        sel = q == qm
        if sel.any():
            db, cap, disp = _bit_channel(qm)
            c[sel] = np.interp(s[sel], db, cap)
            v[sel] = np.interp(s[sel], db, disp)
    n = np.maximum(np.asarray(n_coded, dtype=float), 1.0)
    k = np.asarray(tbs_bits, dtype=float) + 24.0
    return ndtr(-(n * c - k + 0.5 * np.log2(n)) / np.sqrt(n * v))


def bler(sinr_db: np.ndarray, mcs: int, tbs_bits: int, n_coded: int, loss_db: float = 1.0) -> np.ndarray:
    """Block error probability of a transport block of ``tbs_bits`` (+ 24 CRC bits) on ``n_coded`` coded bits."""
    from scipy.special import ndtr
    q = MCS_TABLE1[mcs][0]
    db, cap, disp = _bit_channel(q)
    s = np.asarray(sinr_db, dtype=float) - loss_db
    c = np.interp(s, db, cap)
    v = np.interp(s, db, disp)
    k = tbs_bits + 24
    n = max(int(n_coded), 1)
    return ndtr(-(n * c - k + 0.5 * math.log2(n)) / np.sqrt(n * v))
