# SPDX-License-Identifier: MIT
"""Optional compiled loops of blockage model A (``run.backend: numba``, since 2.11.1; see
:meth:`handoverlab.channel.blockage.BlockageA.factor_db`).

The diffuse part of a block of links is computed in two loops with the NumPy edge terms in between:

* :func:`zones`: the quadrature nodes of every link, the self-blocking indicators, the wrapped offsets from the
  non-self blockers and the zone test |d| < x_k; the offsets inside a zone are written in the order of the NumPy
  path (link, node, blocker), so the compact arrays are the ones the NumPy path builds.
* the knife-edge terms of those offsets (cos, arctan) by the NumPy function of the reference
  (:func:`handoverlab.channel.blockage._edge_in`), on the compact arrays;
* :func:`means`: the means over the nodes and the products of the diffuse factor.

The loops use only additions, multiplications, divisions and comparisons, in the order of the NumPy path:

* the wrap ``(v + 180) % 360 - 180`` follows NumPy's ``remainder`` (``fmod``, plus 360 if negative, +0.0 if
  zero).  ``fmod(v, 360)`` is exact; for |v| < 720 it is v, v - 360 or v + 360, and those differences are exact
  (Sterbenz lemma), so the loop subtracts instead of calling ``fmod``; other values use ``%`` (the same rule);
* the means over the azimuth nodes (axis -2 of an (L, N, K) array) are sums from 0 node by node, the means over
  the zenith nodes (last axis) are NumPy's pairwise sums from 0, the sum over the blockers is a sum from 0.

The results are bit-identical to the NumPy path; the tests compare both in the same process.

Numba is optional (``pip install handoverlab[fast]``); without it :func:`kernels` returns None and the NumPy
path is used.
"""
from __future__ import annotations

try:                                                          # optional dependency
    import numba
except ImportError:                                           # pragma: no cover - depends on the installation
    numba = None

#: longest node axis that :func:`means` sums like NumPy (one block of NumPy's pairwise summation)
MAX_NODES = 128


def _zones(azl, zel, hdl, phl, xkl, au, zu, p_sb, hx_sb, t_sb, hy_sb, theta_k, y_k,
           ia, iz, za, zz, da, ha, dz):
    """Zone test of a block of L links (see the module text).

    ``azl``, ``zel``, ``hdl`` (L,) arrival azimuth, zenith and heading [deg]; ``phl``, ``xkl`` (L, K) blocker
    centres and widths; ``au``, ``zu`` the node offsets ``asa * U_AZ`` (N,) and ``zsa * U_ZE`` (NZ,); ``hx_sb``,
    ``hy_sb`` half the self-blocking widths.  Writes the indicators ``ia`` (L, N), ``iz`` (L, NZ), the in-zone
    flags ``za`` (L, N, K), ``zz`` (L, NZ), the in-zone azimuth offsets ``da`` with their half widths ``ha`` and
    the in-zone zenith offsets ``dz``; returns their numbers (na, nz)."""
    L = azl.shape[0]
    N = au.shape[0]
    NZ = zu.shape[0]
    K = phl.shape[1]
    na = 0
    nz = 0
    for i in range(L):
        for j in range(N):
            a = azl[i] + au[j]
            v = (a - hdl[i]) - p_sb + 180.0                   # _wrap: (v % 360) - 180, see the module text
            if v >= 0.0:
                m = v if v < 360.0 else (v - 360.0 if v < 720.0 else v % 360.0)
            elif v > -360.0:
                m = v + 360.0
            elif v > -720.0:
                m = v + 360.0
                if m < 0.0:
                    m += 360.0
            else:
                m = v % 360.0
            ia[i, j] = abs(m - 180.0) < hx_sb
            for k in range(K):
                v = (a - phl[i, k]) + 180.0
                if v >= 0.0:
                    m = v if v < 360.0 else (v - 360.0 if v < 720.0 else v % 360.0)
                elif v > -360.0:
                    m = v + 360.0
                elif v > -720.0:
                    m = v + 360.0
                    if m < 0.0:
                        m += 360.0
                else:
                    m = v % 360.0
                d = m - 180.0
                x = xkl[i, k]
                if abs(d) < x:
                    za[i, j, k] = True
                    da[na] = d
                    ha[na] = 0.5 * x
                    na += 1
                else:
                    za[i, j, k] = False
        for j in range(NZ):
            z = zel[i] + zu[j]
            z = z if z > 0.0 else 0.0                         # np.clip(z, 0, 180)
            z = z if z < 180.0 else 180.0
            iz[i, j] = abs(z - t_sb) < hy_sb
            d = z - theta_k
            if abs(d) < y_k:
                zz[i, j] = True
                dz[nz] = d
                nz += 1
            else:
                zz[i, j] = False
    return na, nz


def _means(ia, iz, za, zz, va, vz, keep, floor, f_dif, wa, wz, acc):
    """Diffuse factor ``f_dif`` (L,) of a block of links from the indicators and in-zone flags of :func:`zones`
    and the edge terms ``va``, ``vz`` of the in-zone offsets (in the order of ``da``, ``dz``).  ``wa`` (4, N, K),
    ``wz`` (4, NZ) and ``acc`` (8,) are work arrays."""
    L, N, K = za.shape
    NZ = zz.shape[1]
    pa_n = 0
    pz_n = 0
    lim = NZ - NZ % 8
    for i in range(L):
        c = 0.0
        for j in range(N):
            if ia[i, j]:
                c += 1.0
        pa = c / N                                            # ia.mean(-1): exact
        c = 0.0
        for j in range(NZ):
            if iz[i, j]:
                c += 1.0
        pz = c / NZ
        for j in range(NZ):                                   # fz, fz ** 2, iz * fz, iz * fz ** 2
            f = 0.0
            if zz[i, j]:
                f = vz[pz_n]
                pz_n += 1
            s = 1.0 if iz[i, j] else 0.0
            f2 = f * f
            wz[0, j] = f
            wz[1, j] = f2
            wz[2, j] = s * f
            wz[3, j] = s * f2
        ez = 0.0
        ez2 = 0.0
        ezz = 0.0
        ezz2 = 0.0
        for r in range(4):                                    # mean(-1): 0 + NumPy's pairwise sum
            if NZ < 8:
                t = 0.0
                for j in range(NZ):
                    t += wz[r, j]
            else:
                for q in range(8):
                    acc[q] = wz[r, q]
                j = 8
                while j < lim:
                    for q in range(8):
                        acc[q] += wz[r, j + q]
                    j += 8
                t = ((acc[0] + acc[1]) + (acc[2] + acc[3])) + ((acc[4] + acc[5]) + (acc[6] + acc[7]))
                while j < NZ:
                    t += wz[r, j]
                    j += 1
            t = (0.0 + t) / NZ
            if r == 0:
                ez = t
            elif r == 1:
                ez2 = t
            elif r == 2:
                ezz = t
            else:
                ezz2 = t
        for j in range(N):                                    # fa, fa ** 2, ia * fa, ia * fa ** 2
            s = 1.0 if ia[i, j] else 0.0
            for k in range(K):
                f = 0.0
                if za[i, j, k]:
                    f = va[pa_n]
                    pa_n += 1
                f2 = f * f
                wa[0, j, k] = f
                wa[1, j, k] = f2
                wa[2, j, k] = s * f
                wa[3, j, k] = s * f2
        tot = 0.0                                             # e_snk.sum(-1)
        for k in range(K):
            ea = 0.0                                          # mean(-2): 0 + node by node
            ea2 = 0.0
            eza = 0.0
            eza2 = 0.0
            for j in range(N):
                ea += wa[0, j, k]
                ea2 += wa[1, j, k]
                eza += wa[2, j, k]
                eza2 += wa[3, j, k]
            ea = ea / N
            ea2 = ea2 / N
            eza = eza / N
            eza2 = eza2 / N
            e_nk = 2.0 * ea * ez - ea2 * ez2
            tot += e_nk - keep * (2.0 * eza * ezz - eza2 * ezz2)
        v =(1.0 - keep * pa * pz) - (0.0 + tot)
        f_dif[i] = v if v >= floor else floor                 # np.maximum(v, floor)


def kernels():
    """The compiled (zones, means) loops, or None without Numba."""
    if numba is None:
        return None
    return _compiled()


_CACHE = []


def _compiled():
    if not _CACHE:
        jit = numba.njit(cache=True, fastmath=False, nogil=True)
        _CACHE.append((jit(_zones), jit(_means)))
    return _CACHE[0]


def python_kernels():
    """The same loops as plain Python (tests without Numba)."""
    return _zones, _means
