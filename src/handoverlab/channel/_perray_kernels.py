# SPDX-License-Identifier: MIT
"""Optional compiled loops of the per-ray beam gains (``run.backend: numba``; see
:mod:`handoverlab.channel.perray`).

* :func:`_rays` expands the clusters of every link to its rays (the zenith of Eq. 7.5-20 with the wrap of
  Eq. 7.5-18, the azimuth of Eq. 7.5-13, sin / cos of both by the angle-addition formulas) and writes, per ray,
  the arguments of the transcendental functions that NumPy then evaluates in single precision: the exponent of
  the element gain of Table 7.3-1 in every sector, the half vertical array phase h, and the horizontal phase
  arguments.
* :func:`_pairs` forms, per user-cell pair, the power-weighted sums over the rays and the beam gains.  The
  vertical array factor is |sum_m exp(j m psi)|^2 / M = U_{M-1}(cos(psi / 2))^2 / M (Chebyshev polynomial of the
  second kind, U_{k+1}(c) = 2 c U_k(c) - U_{k-1}(c)).  The horizontal factor of beam b is
  (N + sum_d A_bd cos(d a) + B_bd sin(d a)) / N with A_bd = 2 (N - d) cos(d c_b), B_bd = 2 (N - d) sin(d c_b),
  d = 1 .. N - 1, so the sum over the rays needs only F_0 = sum w, F_C,d = sum w cos(d a), F_S,d = sum w sin(d a),
  formed with cos((d + 1) a) = cos(d a) cos a - sin(d a) sin a, sin((d + 1) a) = sin(d a) cos a + cos(d a) sin a.
  With three sectors exp(j a_k) are products of P = exp(j X / 2) and Q = exp(j (sqrt 3 / 2) Y), with one sector
  exp(j a) = P^2 (:meth:`handoverlab.channel.perray.PerRay.cluster_gains`).

The loops use only additions, subtractions, multiplications, divisions, comparisons and abs, in the order of
the NumPy path (:func:`handoverlab.channel.perray.rays_numpy`, :func:`handoverlab.channel.perray.pairs_numpy`):
rays in order from 0, a ray of power 0 adds nothing (the NumPy path adds +-0.0, which leaves every sum unchanged).
The azimuth wrap (v + 180) % 360 - 180 follows NumPy's remainder rule (fmod, plus 360 if negative): for
0 <= v + 180 < 720 fmod is v + 180 or v + 180 - 360 (exact), for -360 < v + 180 < 0 it is v + 180 and the
adjustment adds 360; other values use ``%`` (the same rule).  The results are bit-identical to the NumPy path;
the tests compare both in the same process.

Numba is optional (``pip install handoverlab[fast]``); without it :func:`kernels` returns None and the NumPy
path is used.
"""
from __future__ import annotations

import numpy as np

try:                                                          # optional dependency
    import numba
except ImportError:                                           # pragma: no cover - depends on the installation
    numba = None

#: phase modes (as in handoverlab.channel.perray)
_GENERIC, _ONE, _THREE = 0, 1, 3


def _rays(theta, phi, perm, dtheta, dphi, theta_los, phi_los, sth, cth, sph, cph, sdt, cdt, sdf, cdf,
          stl, ctl, sfl, cfl, ray_power, los_power, los, pi, sqrt3_2, beta, cb, sb, mode, am, cos_tilt, ln10_10,
          ea, hv, pa, pw):
    """Per link e and ray r (the LOS ray first if ``los``): ``ea[e, k, r]`` exponent of the element gain in sector
    k, ``hv[e, r]`` half vertical phase, ``pa[e, :, r]`` phase arguments, ``pw[e, r]`` ray power."""
    E, N = theta.shape
    M = dphi.shape[0]
    ns = beta.shape[0]
    off = 1 if los else 0
    for e in range(E):
        n = 0                                                 # cluster and ray of q (counters, no division)
        m = -1
        for q in range(off + N * M):
            if q >= off:
                m += 1
                if m == M:
                    m = 0
                    n += 1
            if q < off:
                tw = theta_los[e]
                st = abs(stl[e])
                ct = ctl[e]
                ph = phi_los[e]
                sp = sfl[e]
                cp = cfl[e]
                p = los_power[e]
            else:
                j = perm[e, n, m]
                t = theta[e, n] + dtheta[e, j]
                if -180.0 <= t < 360.0:
                    tw = 360.0 - t if t > 180.0 else abs(t)
                else:
                    mm = t % 360.0
                    tw = 360.0 - mm if mm > 180.0 else mm
                st = abs(sth[e, n] * cdt[e, j] + cth[e, n] * sdt[e, j])
                ct = cth[e, n] * cdt[e, j] - sth[e, n] * sdt[e, j]
                ph = phi[e, n] + dphi[m]
                sp = sph[e, n] * cdf[m] + cph[e, n] * sdf[m]
                cp = cph[e, n] * cdf[m] - sph[e, n] * sdf[m]
                p = ray_power[e, n]
            x = (tw - 90.0) / 65.0
            av = -min(12.0 * (x * x), 30.0)
            for k in range(ns):
                t2 = (ph - beta[k]) + 180.0
                if 0.0 <= t2 < 360.0:
                    w2 = t2
                elif 360.0 <= t2 < 720.0:
                    w2 = t2 - 360.0
                elif -360.0 < t2 < 0.0:
                    w2 = t2 + 360.0
                else:
                    w2 = t2 % 360.0
                xk = (w2 - 180.0) / 65.0
                ah = -min(12.0 * (xk * xk), am)
                ea[e, k, q] = (8.0 - min(-(av + ah), am)) * ln10_10
            hv[e, q] = 0.5 * (pi * (ct - cos_tilt))
            if mode == _GENERIC:
                for k in range(ns):
                    pa[e, k, q] = pi * st * (sp * cb[k] - cp * sb[k])
            else:
                pa[e, 0, q] = 0.5 * (pi * st * (sp * cb[0] - cp * sb[0]))
                if mode == _THREE:
                    pa[e, 1, q] = sqrt3_2 * (pi * st * (cp * cb[0] + sp * sb[0]))
            pw[e, q] = p


def _weights(pw, vc, m, we):
    """Per link e and ray r: ``we[e, r]`` = ``pw[e, r]`` U_{m-1}(c)^2 / m with c = ``vc[e, r]`` = cos(h) (the ray
    power times the vertical array factor); 0 where the power is 0."""
    E, R = pw.shape
    for e in range(E):
        for r in range(R):
            p = pw[e, r]
            if p == 0.0:
                we[e, r] = 0.0
                continue
            c = np.float64(vc[e, r])
            u0 = 1.0
            u1 = 2.0 * c
            u = u0 if m == 1 else u1
            for _ in range(2, m):
                u2 = 2.0 * c * u1 - u0
                u0 = u1
                u1 = u2
                u = u2
            we[e, r] = p * ((u * u) / m)


def _pairs(ei, ki, we, el, pc, ps, mode, n, A, B, F, G):
    """Per pair i (link ``ei[i]``, sector ``ki[i]``) the sums ``F[i]`` over the rays with the weights
    w = ``we[e, r]`` ``el[e, k, r]``: F[i, 0] = sum w, F[i, d] = sum w cos(d a), F[i, n - 1 + d] = sum w sin(d a)
    (d = 1 .. n - 1), and the beam gains G[i, b] = (n F_0 + sum_d (A[b, d - 1] F_C,d + B[b, d - 1] F_S,d)) / n."""
    L = ei.shape[0]
    R = we.shape[1]
    nb = A.shape[0]
    for i in range(L):
        e = ei[i]
        k = ki[i]
        for jj in range(2 * n - 1):
            F[i, jj] = 0.0
        for r in range(R):
            w0 = we[e, r]
            if w0 == 0.0:
                continue
            wr = w0 * np.float64(el[e, k, r])
            F[i, 0] += wr
            if n < 2:
                continue
            if mode == _GENERIC:
                cs = np.float64(pc[e, k, r])
                sn = np.float64(ps[e, k, r])
            else:
                p_c = np.float64(pc[e, 0, r])
                p_s = np.float64(ps[e, 0, r])
                cs = p_c * p_c - p_s * p_s
                sn = 2.0 * p_c * p_s
                if mode == _THREE and k > 0:
                    q_c = np.float64(pc[e, 1, r])
                    q_s = np.float64(ps[e, 1, r])
                    if k == 1:
                        cs = p_c * q_c - p_s * q_s
                        sn = -(p_s * q_c + p_c * q_s)
                    else:
                        cs = p_c * q_c + p_s * q_s
                        sn = p_c * q_s - p_s * q_c
            cd = cs
            sd = sn
            F[i, 1] += wr * cd
            F[i, n] += wr * sd
            for d in range(2, n):
                c2 = cd * cs - sd * sn
                s2 = sd * cs + cd * sn
                cd = c2
                sd = s2
                F[i, d] += wr * cd
                F[i, n - 1 + d] += wr * sd
        for b in range(nb):
            v = n * F[i, 0]
            for d in range(1, n):
                v = v + (A[b, d - 1] * F[i, d] + B[b, d - 1] * F[i, n - 1 + d])
            G[i, b] = v / n


def kernels():
    """The compiled (rays, weights, pairs) loops, or None without Numba."""
    if numba is None:
        return None
    return _compiled()


_CACHE = []


def _compiled():
    if not _CACHE:
        jit = numba.njit(cache=True, fastmath=False, nogil=True)
        _CACHE.append((jit(_rays), jit(_weights), jit(_pairs)))
    return _CACHE[0]


def python_kernels():
    """The same loops as plain Python (tests without Numba)."""
    return _rays, _weights, _pairs
