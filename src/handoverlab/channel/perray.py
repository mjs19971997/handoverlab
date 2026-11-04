# SPDX-License-Identifier: MIT
"""Beam gains over the rays of an explicit TR 38.901 clause 7.5 realisation (``radio.beams.angular_spread``
"per_ray"; optional, off by default).

TR 38.901 V19.5.0 clause 7.5 sends the power of a link over N clusters of M = 20 rays, and Step 11 weights every
ray with the transmit field pattern in its own departure direction.  This module generates, for every user-site
link, the clusters and rays of Steps 4-8 and gives each SSB beam the power-weighted (incoherent) sum over the rays
of its gain: the power of Eq. 7.5-22 averaged over the uniform random phases of Step 10 (no polarisation, so
Step 11 allows the scalar exp(j Phi), and the XPR of Step 9 is not needed).  With the LOS ray of Eq. 7.5-29 /
7.5-30 the gain is K_R / (K_R + 1) G(LOS direction) + 1 / (K_R + 1) sum_n sum_m (P_n / M) G(ray n, m).

Per user-site link (shared by the co-sited sectors, Steps 4 and 9)

* LSPs (Step 4): K (LOS), ASD and ZSD, with ASA and ZSA only for blockage model A; log-normal (normal in dB for K)
  with the means and standard deviations of Table 7.5-6 Part-1 and Tables 7.5-7 / 7.5-8 (ZSD), the
  cross-correlations of Table 7.5-6 among these parameters through a Cholesky factor (the order [K, ASD, ZSD, ASA,
  ZSA] gives the same joint distribution as the order of Step 4 and keeps K, ASD and ZSD unchanged when ASA and
  ZSA are added), the caps ASD, ASA <= 104 deg and ZSD, ZSA <= 52 deg.  UMa below 6 GHz uses fc = 6 (note 6),
  UMi below 2 GHz fc = 2 (note 7), the ZSD offset of UMa below 6 GHz fc = 6 (note 4 under Tables 7.5-7 to 7.5-12).
  The cross-correlations with SF, DS (and of any parameter with HandoverLab's own shadowing) are not modelled.
* Powers (Steps 5-6): with tau'_n = -r_tau DS ln X_n (Eq. 7.5-1) and the shift of Eq. 7.5-2, Eq. 7.5-5 gives
  P'_n proportional to X_n^(r_tau - 1) 10^(-Z_n / 10), Z_n ~ N(0, zeta^2); DS cancels in the normalisation of
  Eq. 7.5-6, so no delay is formed.  The cluster with the smallest delay (the largest X_n) is the first cluster
  of the LOS case.  Clusters more than 25 dB below the strongest are removed, without renormalisation.
* Angles (Step 7): AOD by Eq. 7.5-9 to 7.5-13 with ASD and the cluster ASD, ZOD by Eq. 7.5-14, 7.5-15, 7.5-19
  (NLOS, O2I) or 7.5-17 (LOS) with the ray offsets of Eq. 7.5-20 and the wrap of Eq. 7.5-18; C_phi and C_theta
  of Tables 7.5-2 / 7.5-4 with the K-dependent LOS factors of Eq. 7.5-10 / 7.5-15 (K enters Eq. 7.5-15 at no less
  than -9.5 dB, where its cubic is still positive).  The angle powers are those of Eq. 7.5-8 in LOS.
* Coupling (Step 8): one random permutation per cluster couples the AOD offsets to the ZOD offsets, within the
  sub-clusters of Table 7.5-5 for the two strongest clusters.
* With blockage model A, the cluster arrival angles (AOA by Eq. 7.5-11 / 7.5-12, ZOA by Eq. 7.5-16 / 7.5-17 with
  theta_ZOA = 90 deg for O2I) give the attenuation of each cluster (clause 7.6.4.1 Step c); the LOS ray is
  attenuated at the LOS arrival direction.
* O2I links (indoor users) use the O2I column of Table 7.5-6 (no K, no LOS ray) and, by note 5 under Tables 7.5-7
  / 7.5-8, the ZSD and ZOD offset of the LOS state of the outdoor part.

Time evolution along each track (clause 7.6.3; "LSPs and SSPs may be interpolated within the coherence length",
note under Procedure B of clause 7.6.3.2): every random number above is driven by standard normals, the uniform
X_n as exp(-(z1^2 + z2^2) / 2).  The normals are drawn at knots spaced D along the user's travelled distance s and
mixed as z(s) = cos(pi u / 2) z_k + sin(pi u / 2) z_{k+1}, u = s / D - k, so every instant is an exact clause 7.5
draw.  D is the correlation distance of the LSP (Table 7.5-6) or, for the cluster variables, that of the
"cluster and ray specific random variables" (Table 7.6.3.1-2).  The cluster signs and the ray coupling are fixed
per link for the whole run (clause 7.6.3.1).  The normals of a knot come from a counter-based hash of (seed,
user, site, set, variable group, knot), so they never depend on chunk or block sizes.  Two sets per link (LOS and
NLOS parameter columns) are kept; with a LOS power weight w in (0, 1) the gain is w G(LOS set) + (1 - w) G(NLOS
set) (power form of Eq. 7.6-19).

Far pairs: a user-cell pair whose upper-bound power (site gain + peak panel gain) is more than ``per_ray_prune_db``
below the user's strongest cell (geometric gains) keeps the geometric gain.

Evaluation: the clusters (:meth:`PerRay.clusters`) are expanded to rays and combined into the beam gains by the
loops of :mod:`._perray_kernels` (``run.backend: numba``) or their NumPy path (:func:`rays_numpy`,
:func:`weights_numpy`, :func:`pairs_numpy`; the same values bit for bit); exp, cos and sin of the element gain,
the vertical phase and the horizontal phases are taken by NumPy in single precision.

Limits: power form only (no small-scale fading on the beam path, no polarisation, no delays); 1-D consistency along
each track (no 2-D field between users, neither Procedure A nor B of clause 7.6.3.2); LOS-set and NLOS-set
realisations independent; UMa and UMi only; no UE receive beams.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.special import ndtri

from ..seeds import streams
from ._perray_kernels import kernels
from .antenna import G_E_MAX_DB, wrap_deg
from .spread import _lg_zsd, zod_offset_deg

PERRAY_PATHLOSS = ("uma", "umi_street_canyon")
M_RAYS = 20
#: Table 7.5-3: ray offset angles for rms 1, rays 1, 2, ..., 20 (+, - per pair)
ALPHA = np.array([s * a for a in (0.0447, 0.1413, 0.2492, 0.3715, 0.5129, 0.6797, 0.8844, 1.1481, 1.5195, 2.1551)
                  for s in (1.0, -1.0)])
#: Table 7.5-5: rays of the three sub-clusters (0-based ray indices)
SUB_CLUSTERS = (np.array([0, 1, 2, 3, 4, 5, 6, 7, 18, 19]), np.array([8, 9, 10, 11, 16, 17]),
                np.array([12, 13, 14, 15]))
#: Table 7.5-2 (C_phi^NLOS) and Table 7.5-4 (C_theta^NLOS) for the cluster numbers of UMa / UMi
C_PHI = {12: 1.146, 19: 1.273, 20: 1.289}
C_THETA = {12: 1.104, 19: 1.184, 20: 1.178}
ASD_MAX_DEG, ZSD_MAX_DEG = 104.0, 52.0
#: K [dB] entering the LOS factor of C_theta (Eq. 7.5-15) at no less than this value (the cubic is 0 near -10 dB)
K_MIN_CTHETA_DB = -9.5
#: LSP order (Cholesky) and the hash groups of the variables
LSP_ORDER = ("K", "ASD", "ZSD", "ASA", "ZSA")
_G_LSP = {"K": 1, "ASD": 2, "ZSD": 3, "ASA": 4, "ZSA": 5}
_G_CLUSTER, _G_SIGN, _G_PERM = 8, 9, 10
#: cluster variables per slot: Z, X (two normals), Y_AOD, Y_ZOD, Y_AOA, Y_ZOA
N_CVAR, N_CVAR_DEP = 7, 5
#: entries (link, instant, set) per block and pairs per kernel call: the largest arrays are (pairs, rays) float64
ENTRY_BLOCK = 384
LN10_10 = math.log(10.0) / 10.0


def link_params(pathloss: str, fc: float, state: str) -> dict:
    """Parameters of TR 38.901 V19.5.0 Table 7.5-6 Part-1 for ``state`` "los", "nlos" or "o2i".

    Returns the cluster number N, r_tau, zeta [dB], cluster ASD / ASA / ZSA [deg], (mu, sigma) of lgASD, lgASA,
    lgZSA and K [dB] (None without K), the correlation distances [m] of the LSPs and of the cluster variables
    (Table 7.6.3.1-2) and the cross-correlation matrix in the order of ``LSP_ORDER`` (K left out without K)."""
    if pathloss == "uma":
        lf = math.log10(max(fc, 6.0))                     # note 6: UMa below 6 GHz uses fc = 6
        tab = {
            "los": dict(N=12, r_tau=2.5, zeta=3.0, c_asd=3.58, c_asa=11.0, c_zsa=7.0, asd=(0.92, 0.31),
                        asa=(1.76, 0.19), zsa=(0.96, 0.15), k=(9.0, 3.5),
                        D=dict(K=12.0, ASD=18.0, ZSD=15.0, ASA=15.0, ZSA=15.0, C=40.0),
                        rho=dict(K_ASD=0.0, K_ZSD=0.0, K_ASA=-0.2, K_ZSA=0.0, ASD_ZSD=0.5, ASD_ASA=0.0,
                                 ASD_ZSA=0.0, ZSD_ASA=-0.3, ZSD_ZSA=0.0, ASA_ZSA=0.4)),
            "nlos": dict(N=20, r_tau=2.3, zeta=3.0, c_asd=1.8, c_asa=15.0, c_zsa=7.0, asd=(1.09, 0.44),
                         asa=(2.04 - 0.25 * lf, 0.17 - 0.03 * lf), zsa=(-0.2856 * lf + 1.445, 0.17), k=None,
                         D=dict(ASD=50.0, ZSD=50.0, ASA=50.0, ZSA=50.0, C=50.0),
                         rho=dict(ASD_ZSD=0.5, ASD_ASA=0.4, ASD_ZSA=-0.1, ZSD_ASA=0.0, ZSD_ZSA=0.0, ASA_ZSA=0.0)),
            "o2i": dict(N=12, r_tau=2.2, zeta=4.0, c_asd=1.8, c_asa=8.0, c_zsa=3.0, asd=(0.58, 0.7),
                        asa=(1.76, 0.16), zsa=(1.01, 0.43), k=None,
                        D=dict(ASD=11.0, ZSD=25.0, ASA=17.0, ZSA=25.0, C=15.0),
                        rho=dict(ASD_ZSD=-0.2, ASD_ASA=0.0, ASD_ZSA=0.0, ZSD_ASA=0.0, ZSD_ZSA=0.5, ASA_ZSA=0.5)),
        }
    elif pathloss == "umi_street_canyon":
        f = math.log10(1.0 + max(fc, 2.0))                # note 7: UMi below 2 GHz uses fc = 2
        tab = {
            "los": dict(N=12, r_tau=3.0, zeta=3.0, c_asd=3.0, c_asa=17.0, c_zsa=7.0,
                        asd=(-0.05 * f + 1.21, 0.08 * f + 0.29), asa=(-0.07 * f + 1.66, 0.021 * f + 0.26),
                        zsa=(-0.11 * f + 0.81, -0.03 * f + 0.29), k=(9.0, 5.0),
                        D=dict(K=15.0, ASD=8.0, ZSD=12.0, ASA=8.0, ZSA=12.0, C=12.0),
                        rho=dict(K_ASD=-0.2, K_ZSD=0.0, K_ASA=-0.3, K_ZSA=0.0, ASD_ZSD=0.5, ASD_ASA=0.4,
                                 ASD_ZSA=0.3, ZSD_ASA=0.0, ZSD_ZSA=0.0, ASA_ZSA=0.0)),
            "nlos": dict(N=19, r_tau=2.1, zeta=3.0, c_asd=10.0, c_asa=22.0, c_zsa=7.0,
                         asd=(-0.24 * f + 1.54, 0.10 * f + 0.33), asa=(-0.07 * f + 1.76, 0.05 * f + 0.27),
                         zsa=(-0.03 * f + 0.92, -0.05 * f + 0.35), k=None,
                         D=dict(ASD=10.0, ZSD=10.0, ASA=9.0, ZSA=10.0, C=15.0),
                         rho=dict(ASD_ZSD=0.5, ASD_ASA=0.0, ASD_ZSA=0.5, ZSD_ASA=0.0, ZSD_ZSA=0.0, ASA_ZSA=0.2)),
            "o2i": dict(N=12, r_tau=2.2, zeta=4.0, c_asd=5.0, c_asa=8.0, c_zsa=3.0, asd=(1.25, 0.42),
                        asa=(1.76, 0.16), zsa=(1.01, 0.43), k=None,
                        D=dict(ASD=11.0, ZSD=25.0, ASA=17.0, ZSA=25.0, C=15.0),
                        rho=dict(ASD_ZSD=-0.2, ASD_ASA=0.0, ASD_ZSA=0.0, ZSD_ASA=0.0, ZSD_ZSA=0.5, ASA_ZSA=0.5)),
        }
    else:
        raise ValueError("per-ray beam gains need pathloss uma or umi_street_canyon, not %r" % pathloss)
    p = dict(tab[state])
    names = [n for n in LSP_ORDER if p["k"] is not None or n != "K"]
    rho = np.eye(len(names))
    for i, a in enumerate(names):
        for j, b in enumerate(names):
            if i != j:
                rho[i, j] = p["rho"].get(a + "_" + b, p["rho"].get(b + "_" + a, 0.0))
    p["names"] = names
    p["chol"] = np.linalg.cholesky(rho)
    p["c_phi"], p["c_theta"] = C_PHI[p["N"]], C_THETA[p["N"]]
    return p


# ---------------------------------------------------------------- counter-based normals
_U = np.uint64
_GOLD = _U(0x9E3779B97F4A7C15)
_M1, _M2 = _U(0xBF58476D1CE4E5B9), _U(0x94D049BB133111EB)
_S30, _S27, _S31, _S11 = _U(30), _U(27), _U(31), _U(11)


def _mix(z):
    """SplitMix64 finaliser of uint64 arrays (wrapping arithmetic)."""
    z = (z ^ (z >> _S30)) * _M1
    z = (z ^ (z >> _S27)) * _M2
    return z ^ (z >> _S31)


def _comb(h, v):
    """Hash of the pair (h, v), uint64 arrays (broadcast)."""
    with np.errstate(over="ignore"):
        return _mix(np.asarray(h, dtype=_U) ^ _mix(np.asarray(v, dtype=_U) + _GOLD))


def _uniform(key, idx):
    """Uniforms in (0, 1), shape key.shape + idx.shape, from the keys and the element indices."""
    h = _comb(np.asarray(key, dtype=_U)[..., None], np.asarray(idx, dtype=_U))
    return ((h >> _S11).astype(np.float64) + 0.5) * (1.0 / 9007199254740992.0)


def _normals(key, idx):
    return ndtri(_uniform(key, idx))


def mixed_normals(link, group: int, d_m: float, s, idx):
    """Standard normals (E, len(idx)) at the travelled distances ``s`` (E,) of the links ``link`` (E,) uint64:
    knot normals of ``group`` spaced ``d_m`` mixed as cos(pi u / 2) z_k + sin(pi u / 2) z_{k+1}."""
    t = np.asarray(s, dtype=float) / d_m
    k = np.floor(t)
    u = t - k
    base = _comb(link, group)
    key0 = _comb(base, k.astype(_U))
    uq, first, inv = np.unique(key0, return_index=True, return_inverse=True)
    inv = inv.reshape(-1)
    z0 = _normals(uq, idx)[inv]
    z1 = _normals(_comb(base[first], (k[first] + 1.0).astype(_U)), idx)[inv]
    a = 0.5 * math.pi * u
    return np.cos(a)[:, None] * z0 + np.sin(a)[:, None] * z1


def _fixed_uniforms(link, group: int, n: int):
    """Uniforms (E, n) fixed per link for the whole run (signs, ray coupling)."""
    base = _comb(link, group)
    uq, inv = np.unique(base, return_inverse=True)
    return _uniform(uq, np.arange(n, dtype=_U))[inv.reshape(-1)]


def coupling_pair(keys):
    """The free and the sub-cluster ray couplings (E, N, 20) from the uniforms ``keys`` (E, N, 20): ZOD offset
    index of every AOD ray, a random permutation per cluster, or within the sub-clusters of Table 7.5-5."""
    free = np.argsort(keys, axis=-1, kind="stable")
    sub = np.empty_like(free)
    for r in SUB_CLUSTERS:
        sub[..., r] = r[np.argsort(keys[..., r], axis=-1, kind="stable")]
    return free, sub


def coupling(keys, strongest):
    """Ray coupling (E, N, 20) of :func:`coupling_pair`, within the sub-clusters for the clusters marked
    ``strongest`` (the two strongest of each link, Step 8 and Table 7.5-5)."""
    free, sub = coupling_pair(keys)
    return np.where(strongest[..., None], sub, free)


def _sum_last(a):
    """Sum over the last axis from index 0 in order (independent of the other axes' sizes)."""
    acc = np.zeros(a.shape[:-1])
    for i in range(a.shape[-1]):
        acc = acc + a[..., i]
    return acc


def _wrap_zenith(t):
    """Eq. 7.5-18: theta wrapped within [0, 360) and reflected to 360 - theta in [180, 360); for -180 <= theta < 360
    that is |theta| up to 180 and 360 - theta above (the general rule for other values)."""
    t = np.asarray(t, dtype=float)
    out = np.where(t > 180.0, 360.0 - t, np.abs(t))
    far = (t < -180.0) | (t >= 360.0)
    if far.any():
        m = np.mod(t[far], 360.0)
        out[far] = np.where(m > 180.0, 360.0 - m, m)
    return out


def generate_clusters(p: dict, z_lsp, zc, signs, keys, phi_los, theta_zod_los, mu_lgzsd, sig_lgzsd, offset,
                      los_ray: bool, arrival=False, theta_zoa=None, lsp=None):
    """Clusters of E links of one parameter set ``p`` (:func:`link_params`) from standard normals (Steps 4-8).

    ``z_lsp`` (E, k) independent LSP normals in the order of ``p["names"]`` (the first k), ``zc`` (E, N, 5 or 7)
    cluster normals, ``signs`` (E, N, 4) uniforms of the cluster signs, ``keys`` (E, N, 20) uniforms of the
    coupling or the pair (free, sub) of :func:`coupling_pair`; ``phi_los`` LOS AOD (GCS), ``theta_zod_los`` LOS ZOD
    [deg]; ``mu_lgzsd``, ``sig_lgzsd`` of Tables 7.5-7 / 7.5-8 and the ZOD ``offset`` (E,); ``los_ray``: the LOS
    case.  Returns a dict with the cluster centres ``theta`` / ``phi`` (E, N) [deg] (ZOD unwrapped), the power of
    each of their rays ``ray_power`` (E, N) (P_n / M, times 1 / (K_R + 1) in LOS, 0 for removed clusters), the
    coupling ``perm`` (E, N, 20), the ZOD ray offsets ``dtheta`` (E, 20) and AOD ray offsets ``dphi`` (20,) [deg],
    in LOS the LOS ray ``los_power`` (E,), and with ``arrival`` the cluster arrival angles ``aoa`` / ``zoa`` (E, N)
    and the LOS arrival direction (``theta_zoa`` (E,): the ZOA centre of the NLOS formula, 90 deg for O2I).
    ``lsp`` (a test hook, model checks) fixes LSPs: {"ASD", "ZSD", "ASA", "ZSA" [deg], "K" [dB]: value or (E,)}."""
    E, N = zc.shape[0], p["N"]
    names = p["names"]
    L = p["chol"]
    x = {}
    for i, nm in enumerate(names[:z_lsp.shape[1]]):    # correlated LSP normals (Cholesky, fixed order)
        v = np.zeros(E)
        for j in range(i + 1):
            v = v + L[i, j] * z_lsp[:, j]
        x[nm] = v
    asd = np.minimum(10.0 ** (p["asd"][0] + p["asd"][1] * x["ASD"]), ASD_MAX_DEG)
    zsd = np.minimum(10.0 ** (mu_lgzsd + sig_lgzsd * x["ZSD"]), ZSD_MAX_DEG)
    lsp = lsp or {}
    asd = np.broadcast_to(np.asarray(lsp.get("ASD", asd), dtype=float), (E,))
    zsd = np.broadcast_to(np.asarray(lsp.get("ZSD", zsd), dtype=float), (E,))
    # Steps 5-6: powers (DS cancels), the first (smallest delay) cluster
    q = zc[..., 1] ** 2 + zc[..., 2] ** 2                                   # X_n = exp(-q / 2)
    lp = -0.5 * (p["r_tau"] - 1.0) * q - p["zeta"] * zc[..., 0] * LN10_10
    pp = np.exp(lp - lp.max(-1, keepdims=True))
    pn = pp / _sum_last(pp)[:, None]                                         # Eq. 7.5-6
    first = np.argmin(q, axis=-1)
    rows = np.arange(E)
    if los_ray:
        kdb = np.broadcast_to(np.asarray(lsp.get("K", p["k"][0] + p["k"][1] * x["K"]), dtype=float), (E,))
        kr = 10.0 ** (kdb / 10.0)
        pa = pn / (kr + 1.0)[:, None]
        pa[rows, first] += kr / (kr + 1.0)                                  # Eq. 7.5-8 (angles only)
        kc = np.maximum(kdb, K_MIN_CTHETA_DB)
        c_phi = p["c_phi"] * (1.1035 - 0.028 * kdb - 0.002 * kdb ** 2 + 0.0001 * kdb ** 3)      # Eq. 7.5-10
        c_th = p["c_theta"] * (1.3086 + 0.0339 * kc - 0.0077 * kc ** 2 + 0.0002 * kc ** 3)      # Eq. 7.5-15
        c_phi, c_th = c_phi[:, None], c_th[:, None]
    else:
        pa, c_phi, c_th = pn, p["c_phi"], p["c_theta"]
    lr = np.maximum(-np.log(pa / pa.max(-1, keepdims=True)), 0.0)
    sg = np.where(signs < 0.5, -1.0, 1.0)

    def centre(sign, spread_prime, y, anchor, extra):
        v = sign * spread_prime + y
        if los_ray:                                                          # Eq. 7.5-12 / 7.5-17
            return v - (v[rows, first] - anchor)[:, None]
        return v + (anchor + extra)[:, None]                                 # Eq. 7.5-11 / 7.5-16 / 7.5-19

    # Step 7: departure angles
    phi_n = centre(sg[..., 0], 2.0 * (asd / 1.4)[:, None] * np.sqrt(lr) / c_phi, (asd / 7.0)[:, None] * zc[..., 3],
                   phi_los, 0.0)                                             # Eq. 7.5-9, 7.5-11 / 7.5-12
    th_n = centre(sg[..., 1], zsd[:, None] * lr / c_th, (zsd / 7.0)[:, None] * zc[..., 4], theta_zod_los,
                  offset)                                                    # Eq. 7.5-14, 7.5-19 / 7.5-17
    keep = pn >= pn.max(-1, keepdims=True) * 10.0 ** -2.5                  # remove clusters below -25 dB
    order = np.argsort(-pn, axis=-1, kind="stable")
    strongest = np.zeros((E, N), dtype=bool)
    strongest[rows[:, None], order[:, :2]] = True
    if isinstance(keys, tuple):                                              # (free, sub) per link, precomputed
        perm = np.where(strongest[..., None], keys[1], keys[0])
    else:
        perm = coupling(keys, strongest)                                     # Step 8
    pw = np.where(keep, pn, 0.0) / M_RAYS
    if los_ray:
        pw = pw / (kr + 1.0)[:, None]
    out = dict(theta=th_n, phi=phi_n, ray_power=pw, perm=perm, keep=keep, los=los_ray,
               dtheta=(0.375 * 10.0 ** np.asarray(mu_lgzsd, dtype=float))[:, None] * ALPHA,   # Eq. 7.5-20
               dphi=p["c_asd"] * ALPHA,                                                         # Eq. 7.5-13
               theta_los=np.asarray(theta_zod_los, dtype=float), phi_los=np.asarray(phi_los, dtype=float))
    if los_ray:
        out["los_power"] = kr / (kr + 1.0)
    if arrival:
        asa = lsp.get("ASA", np.minimum(10.0 ** (p["asa"][0] + p["asa"][1] * x["ASA"]), ASD_MAX_DEG))
        zsa = lsp.get("ZSA", np.minimum(10.0 ** (p["zsa"][0] + p["zsa"][1] * x["ZSA"]), ZSD_MAX_DEG))
        asa = np.broadcast_to(np.asarray(asa, dtype=float), (E,))
        zsa = np.broadcast_to(np.asarray(zsa, dtype=float), (E,))
        aoa_los = wrap_deg(phi_los + 180.0)
        out["aoa"] = centre(sg[..., 2], 2.0 * (asa / 1.4)[:, None] * np.sqrt(lr) / c_phi,
                            (asa / 7.0)[:, None] * zc[..., 5], aoa_los, 0.0)
        out["zoa"] = _wrap_zenith(centre(sg[..., 3], zsa[:, None] * lr / c_th, (zsa / 7.0)[:, None] * zc[..., 6],
                                         theta_zoa, 0.0))
        out["aoa_los"], out["zoa_los"] = aoa_los, 180.0 - theta_zod_los
    return out


def ray_directions(cl):
    """Ray zenith (wrapped, Eq. 7.5-18) and azimuth [deg] and power (E, R) of the clusters ``cl`` of
    :func:`generate_clusters` (the LOS ray first in the LOS case)."""
    E, N = cl["theta"].shape
    th = _wrap_zenith(cl["theta"][..., None] + cl["dtheta"][np.arange(E)[:, None, None], cl["perm"]])
    ph = cl["phi"][..., None] + cl["dphi"]
    pw = np.repeat(cl["ray_power"], M_RAYS, axis=1)
    th, ph = th.reshape(E, -1), ph.reshape(E, -1)
    if cl["los"]:
        th = np.concatenate([cl["theta_los"][:, None], th], axis=1)
        ph = np.concatenate([cl["phi_los"][:, None], ph], axis=1)
        pw = np.concatenate([cl["los_power"][:, None], pw], axis=1)
    return th, ph, pw


def _trig_inputs(cl):
    """sin / cos of the cluster centres (E, N), of the ZOD ray offsets (E, 20) and AOD ray offsets (20,), and of
    the LOS direction (E,) (NumPy, few values per link)."""
    t, f = np.radians(cl["theta"]), np.radians(cl["phi"])
    dt, df = np.radians(cl["dtheta"]), np.radians(cl["dphi"])
    tl, fl = np.radians(cl["theta_los"]), np.radians(cl["phi_los"])
    return (np.sin(t), np.cos(t), np.sin(f), np.cos(f), np.sin(dt), np.cos(dt), np.sin(df), np.cos(df),
            np.sin(tl), np.cos(tl), np.sin(fl), np.cos(fl))


#: phase modes of the sectors: three sectors (products of P and Q), one sector (P^2), any other number (direct)
MODE_GENERIC, MODE_ONE, MODE_THREE = 0, 1, 3


def rays_numpy(cl, trig, ray_power, los_power, beta, cb, sb, mode, am, cos_tilt, ln10_10):
    """NumPy path of :func:`handoverlab.channel._perray_kernels._rays` (same operations, same order).

    Per ray (E, R; the LOS ray first in the LOS case): the element-gain exponents ``ea`` (E, sectors, R) float32,
    the half vertical phase ``hv`` (E, R) float32, the phase arguments ``pa`` (E, nt, R) float32 and the ray powers
    ``pw`` (E, R) float64 (``ray_power`` (E, N) per cluster ray, ``los_power`` (E,))."""
    sth, cth, sph, cph, sdt, cdt, sdf, cdf, stl, ctl, sfl, cfl = trig
    E, N = cl["theta"].shape
    rows = np.arange(E)[:, None, None]
    perm = cl["perm"]
    t = cl["theta"][..., None] + cl["dtheta"][rows, perm]
    tw = _wrap_zenith(t)
    st = np.abs(sth[..., None] * cdt[rows, perm] + cth[..., None] * sdt[rows, perm])
    ct = cth[..., None] * cdt[rows, perm] - sth[..., None] * sdt[rows, perm]
    ph = cl["phi"][..., None] + cl["dphi"]
    sp = sph[..., None] * cdf + cph[..., None] * sdf
    cp = cph[..., None] * cdf - sph[..., None] * sdf
    pw = np.broadcast_to(ray_power[..., None], (E, N, M_RAYS))
    tw, st, ct, ph, sp, cp, pw = (v.reshape(E, -1) for v in (tw, st, ct, ph, sp, cp, pw))
    if cl["los"]:
        tw = np.concatenate([cl["theta_los"][:, None], tw], axis=1)
        st = np.concatenate([np.abs(stl)[:, None], st], axis=1)
        ct = np.concatenate([ctl[:, None], ct], axis=1)
        ph = np.concatenate([cl["phi_los"][:, None], ph], axis=1)
        sp = np.concatenate([sfl[:, None], sp], axis=1)
        cp = np.concatenate([cfl[:, None], cp], axis=1)
        pw = np.concatenate([los_power[:, None], pw], axis=1)
    x = (tw - 90.0) / 65.0
    av = -np.minimum(12.0 * (x * x), 30.0)
    ns = len(beta)
    ea = np.empty((E, ns, tw.shape[1]), dtype=np.float32)
    for k in range(ns):
        m = ((ph - beta[k]) + 180.0) % 360.0
        xk = (m - 180.0) / 65.0
        ah = -np.minimum(12.0 * (xk * xk), am)
        ea[:, k] = (8.0 - np.minimum(-(av + ah), am)) * ln10_10
    hv = (0.5 * (math.pi * (ct - cos_tilt))).astype(np.float32)
    if mode == MODE_GENERIC:
        pa = np.empty((E, ns, tw.shape[1]), dtype=np.float32)
        for k in range(ns):
            pa[:, k] = math.pi * st * (sp * cb[k] - cp * sb[k])
    else:
        pa = np.empty((E, 2 if mode == MODE_THREE else 1, tw.shape[1]), dtype=np.float32)
        pa[:, 0] = 0.5 * (math.pi * st * (sp * cb[0] - cp * sb[0]))
        if mode == MODE_THREE:
            pa[:, 1] = SQRT3_2 * (math.pi * st * (cp * cb[0] + sp * sb[0]))
    return ea, hv, pa, np.ascontiguousarray(pw, dtype=np.float64)


SQRT3_2 = 0.5 * math.sqrt(3.0)


def weights_numpy(pw, vc, m):
    """NumPy path of :func:`handoverlab.channel._perray_kernels._weights`: ray power times the vertical array
    factor U_{m-1}(cos h)^2 / m (E, R)."""
    c = vc.astype(np.float64)
    u0, u1 = np.ones(c.shape), 2.0 * c
    u = u0 if m == 1 else u1
    for _ in range(2, m):
        u2 = 2.0 * c * u1 - u0
        u0, u1 = u1, u2
        u = u2
    return np.where(pw == 0.0, 0.0, pw * ((u * u) / m))


def pairs_numpy(ei, ki, we, el, pc, ps, mode, n, A, B):
    """NumPy path of :func:`handoverlab.channel._perray_kernels._pairs` (same operations, same order): the beam
    gains (pairs, B) of the pairs (entry ``ei``, sector ``ki``)."""
    L, R = len(ei), we.shape[1]
    F = np.zeros((L, 2 * n - 1))
    for r in range(R):
        wr = we[ei, r] * el[ei, ki, r].astype(np.float64)
        F[:, 0] += wr
        if n < 2:
            continue
        if mode == MODE_GENERIC:
            cs, sn = pc[ei, ki, r].astype(np.float64), ps[ei, ki, r].astype(np.float64)
        else:
            p_c, p_s = pc[ei, 0, r].astype(np.float64), ps[ei, 0, r].astype(np.float64)
            cs, sn = p_c * p_c - p_s * p_s, 2.0 * p_c * p_s
            if mode == MODE_THREE:
                q_c, q_s = pc[ei, 1, r].astype(np.float64), ps[ei, 1, r].astype(np.float64)
                cs = np.where(ki == 1, p_c * q_c - p_s * q_s, np.where(ki == 2, p_c * q_c + p_s * q_s, cs))
                sn = np.where(ki == 1, -(p_s * q_c + p_c * q_s), np.where(ki == 2, p_c * q_s - p_s * q_c, sn))
        cd, sd = cs, sn
        F[:, 1] += wr * cd
        F[:, n] += wr * sd
        for d in range(2, n):
            c2 = cd * cs - sd * sn
            s2 = sd * cs + cd * sn
            cd, sd = c2, s2
            F[:, d] += wr * cd
            F[:, n - 1 + d] += wr * sd
    G = np.empty((L, A.shape[0]))
    for b in range(A.shape[0]):
        v = n * F[:, 0]
        for d in range(1, n):
            v = v + (A[b, d - 1] * F[:, d] + B[b, d - 1] * F[:, n - 1 + d])
        G[:, b] = v / n
    return G


class PerRay:
    """Per-ray beam gains of the cells of one layer (one object per layer with ``angular_spread`` "per_ray")."""

    def __init__(self, seed: int, layer, hu: float, indoor=None, backend: str = "numpy", blockage=None,
                 site_offset: int = 0):
        b = layer.beams
        R = layer.radio
        self.pathloss, self.fc, self.hu, self.hb = R.pathloss, R.carrier_ghz, hu, R.bs_height_m
        self.sectors = layer.sectors
        self.boresight = np.asarray(layer.boresight, dtype=float)
        self.beam_az = np.asarray(layer.beam_az, dtype=float)
        self.tilt, self.m, self.n, self.am = b.tilt_deg, b.panel[0], b.panel[1], float(b.am_db)
        self.prune_db = b.per_ray_prune_db
        self.peak_db = G_E_MAX_DB + 10.0 * math.log10(self.m * self.n)
        self.indoor = None if indoor is None else np.asarray(indoor, dtype=bool)
        self.blockage = blockage
        self.site_offset = site_offset
        self.base = _U(int(streams(seed, "perray", 1)[0].integers(0, 2 ** 62)))
        self.kern = kernels() if backend == "numba" else None
        self.par = {s: link_params(self.pathloss, self.fc, s) for s in ("los", "nlos", "o2i")}
        # horizontal array factor: G_b = (n F_0 + sum_d A_bd F_C,d + B_bd F_S,d) / n with the DFT steering
        # c_b = pi sin(theta_tilt) sin(phi_b) of antenna.beam_gain_db
        c_b = math.pi * math.sin(math.radians(self.tilt)) * np.sin(np.radians(self.beam_az))
        d = np.arange(1, self.n)
        self.A = np.ascontiguousarray(2.0 * (self.n - d)[None, :] * np.cos(d[None, :] * c_b[:, None]))
        self.B = np.ascontiguousarray(2.0 * (self.n - d)[None, :] * np.sin(d[None, :] * c_b[:, None]))
        self.cos_tilt = math.cos(math.radians(self.tilt))
        self.cos_b, self.sin_b = np.cos(np.radians(self.boresight)), np.sin(np.radians(self.boresight))
        self.mode = MODE_THREE if self.sectors == 3 else MODE_ONE if self.sectors == 1 else MODE_GENERIC

    # ---------------------------------------------------------------- one call
    def gains_db(self, dx, dy, g_geo, gs, w, users, s, heading=None, blk=None):
        """Beam gains (P, S * sectors, B) float32 [dB] of the layer's cells at P points.

        ``dx``, ``dy`` (P, S) site -> user [m] (nearest image), ``g_geo`` (P, Lc, B) geometric gains [dB],
        ``gs`` (P, Lc) received power without the antenna gain [dB] (pruning), ``w`` (P, S) LOS power weight,
        ``users`` (P,), ``s`` (P,) travelled distance [m], ``heading`` (P,) [rad] and ``blk`` (phi_k, x_k) (P, K)
        of blockage model A (or None)."""
        P, S = dx.shape
        ns, nb = self.sectors, len(self.beam_az)
        out = np.array(g_geo, dtype=np.float32, copy=True)
        if self.prune_db is None:
            keep = np.ones(gs.shape, dtype=bool)
        else:
            ref = (gs + g_geo.max(-1)).max(-1)
            keep = gs + self.peak_db >= (ref - self.prune_db)[:, None]
        keep3 = keep.reshape(P, S, ns)
        anyk = keep3.any(-1)
        lin = np.zeros((P, S, ns, nb))
        d2 = np.maximum(np.hypot(dx, dy), 1.0)
        ind = np.zeros(P, dtype=bool) if self.indoor is None else self.indoor[users]
        for flag in (False, True):
            for st in (0, 1):
                ws = w if st == 0 else 1.0 - w
                pi, si = np.nonzero((ws > 0.0) & anyk & (ind == flag)[:, None])
                o = np.lexsort((pi, users[pi], si))           # links together: their draws are shared
                pi, si = pi[o], si[o]
                for e0 in range(0, len(pi), ENTRY_BLOCK):
                    pe, se = pi[e0:e0 + ENTRY_BLOCK], si[e0:e0 + ENTRY_BLOCK]
                    G = self._entry_gains(pe, se, st, flag, dx, dy, d2, users, s, keep3, heading, blk)
                    lin[pe, se] += ws[pe, se][:, None, None] * G
        res = (10.0 * np.log10(np.maximum(lin, 1e-30))).reshape(P, S * ns, nb).astype(np.float32)
        out[keep] = res[keep]
        return out

    def clusters(self, pe, se, st, o2i, dx, dy, d2, users, s, heading=None, blk=None):
        """Clusters (:func:`generate_clusters`) of the entries (points ``pe``, sites ``se``, set ``st``) with the
        blockage factors applied to the ray powers."""
        E = len(pe)
        u = users[pe]
        los_out = st == 0
        p = self.par["o2i" if o2i else ("los" if los_out else "nlos")]
        los_ray = los_out and not o2i
        arrival = self.blockage is not None
        dd = d2[pe, se]
        phi_los = np.degrees(np.arctan2(dy[pe, se], dx[pe, se]))
        th_zod = 90.0 + np.degrees(np.arctan2(self.hb - self.hu, dd))
        link = _comb(_comb(_comb(self.base, u.astype(_U)), (se + self.site_offset).astype(_U)), _U(st))
        sp = s[pe]
        names = [nm for nm in p["names"] if arrival or nm not in ("ASA", "ZSA")]
        z_lsp = np.empty((E, len(names)))
        for i, nm in enumerate(names):
            z_lsp[:, i] = mixed_normals(link, _G_LSP[nm], p["D"][nm], sp, np.zeros(1, dtype=_U))[:, 0]
        N = p["N"]
        nv = N_CVAR if arrival else N_CVAR_DEP
        idx = (np.arange(N)[:, None] * N_CVAR + np.arange(nv)[None, :]).astype(_U).ravel()
        zc = mixed_normals(link, _G_CLUSTER, p["D"]["C"], sp, idx).reshape(E, N, nv)
        signs = _fixed_uniforms(link, _G_SIGN, N * 4).reshape(E, N, 4)
        uq, inv = np.unique(link, return_inverse=True)
        inv = inv.reshape(-1)
        free, sub = coupling_pair(_uniform(_comb(uq, _G_PERM), np.arange(N * M_RAYS, dtype=_U)).reshape(-1, N, M_RAYS))
        mz, sz = _lg_zsd(self.pathloss, los_out, dd, self.hu, self.hb)
        mz = np.broadcast_to(np.asarray(mz, dtype=float), (E,))
        off = np.zeros(E) if los_out else np.asarray(zod_offset_deg(self.pathloss, dd, self.hu, self.fc), float)
        theta_zoa = np.full(E, 90.0) if o2i else 180.0 - th_zod
        cl = generate_clusters(p, z_lsp, zc, signs, (free[inv], sub[inv]), phi_los, th_zod, mz, sz, off, los_ray,
                               arrival, theta_zoa)
        if arrival:                                    # blockage model A per cluster (clause 7.6.4.1 Step c)
            hd = np.degrees(heading[pe])
            phk, xk = blk[0][pe], blk[1][pe]
            cl["ray_power"] = cl["ray_power"] * self.blockage.direction_factor(cl["aoa"], cl["zoa"], hd, phk, xk)
            if los_ray:
                cl["los_power"] = cl["los_power"] * self.blockage.direction_factor(
                    cl["aoa_los"][:, None], cl["zoa_los"][:, None], hd, phk, xk)[:, 0]
        return cl

    def _entry_gains(self, pe, se, st, o2i, dx, dy, d2, users, s, keep3, heading, blk):
        """Gains (E, sectors, B) of the entries (points ``pe``, sites ``se``, set ``st``); zero for pruned sectors."""
        cl = self.clusters(pe, se, st, o2i, dx, dy, d2, users, s, heading, blk)
        return self.cluster_gains(cl, keep3[pe, se])

    def cluster_gains(self, cl, keep):
        """Beam gains (E, sectors, B) of the clusters ``cl`` for the sectors ``keep`` (E, sectors) (0 elsewhere).

        The compiled loops (``run.backend: numba``) or their NumPy path give the arguments of every ray, NumPy
        takes the transcendental functions (single precision), and the loops (or NumPy) form the gains."""
        E, N = cl["theta"].shape
        ns, nb, n, m = self.sectors, len(self.beam_az), self.n, self.m
        trig = _trig_inputs(cl)
        los_power = cl["los_power"] if cl["los"] else np.zeros(E)
        args = (self.boresight, self.cos_b, self.sin_b, self.mode, self.am, self.cos_tilt, LN10_10)
        if self.kern is not None:
            krays, kweights, kpairs = self.kern
            R = N * M_RAYS + (1 if cl["los"] else 0)
            nt = ns if self.mode == MODE_GENERIC else (2 if self.mode == MODE_THREE else 1)
            ea, hv = np.empty((E, ns, R), np.float32), np.empty((E, R), np.float32)
            pa, pw = np.empty((E, nt, R), np.float32), np.empty((E, R))
            krays(cl["theta"], cl["phi"], cl["perm"], cl["dtheta"], cl["dphi"], cl["theta_los"], cl["phi_los"],
                  *trig, np.ascontiguousarray(cl["ray_power"]), los_power, bool(cl["los"]), math.pi, SQRT3_2,
                  *args, ea, hv, pa, pw)
        else:
            ea, hv, pa, pw = rays_numpy(cl, trig, cl["ray_power"], los_power, *args)
        el, vc, pc, ps = np.exp(ea), np.cos(hv), np.cos(pa), np.sin(pa)       # single precision
        ei, ki = np.nonzero(keep)
        if self.kern is not None:
            we = np.empty(pw.shape)
            kweights(pw, vc, m, we)
            G = np.empty((len(ei), nb))
            kpairs(ei, ki, we, el, pc, ps, self.mode, n, self.A, self.B, np.empty((len(ei), 2 * n - 1)), G)
        else:
            G = pairs_numpy(ei, ki, weights_numpy(pw, vc, m), el, pc, ps, self.mode, n, self.A, self.B)
        out = np.zeros((E, ns, nb))
        out[ei, ki] = G
        return out
