# SPDX-License-Identifier: MIT
"""Static radio map of one world: everything that is tied to place.

For every map pixel in a street and every site the map stores

* the line-of-sight state: blocked if the straight segment crosses a building
  block, and (``clutter_los``) additionally the spatially consistent LOS state
  of TR 38.901 clause 7.6.3.3 -- a Gaussian random field with ``los_corr_m``
  correlation compared with the LOS probability -- standing for obstacles in
  the street (vehicles, trees, street furniture).  The state is a property of
  the place, the same for every user who passes there ("place-tied blockage");
* the path loss for that state, and a static, spatially correlated shadowing
  field shared by all users (share ``place_share`` of the shadowing variance).

It also holds the operator's nominal best-server map (nearest site, no
buildings, no shadowing), which is the only map a handover rule may use.

In the open area there are no buildings; the map holds only the place-tied
shadowing field, and the LOS state is drawn along each user's path by
:class:`handoverlab.channel.source.RadioSource`.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter
from scipy.spatial import cKDTree
from scipy.special import ndtri

from ..layout import Layout, los_matrix
from ..seeds import streams
from .pathloss import p_los, path_loss

FLOOR_DB = -300.0


class GaussianField:
    """Unit-variance Gaussian random fields, one per site, on a raster.

    Correlation exp(-(d / d_corr)^2); the fields of different sites share a
    common component so that their mutual correlation is ``site_corr``.
    """

    def __init__(self, rng, layout: Layout, n_sites: int, d_corr: float, res: float, site_corr: float):
        self.res = res
        self.x0, self.y0 = layout.xmin - 2 * res, layout.ymin - 2 * res
        self.nx = int((layout.xmax - layout.xmin) / res) + 6
        self.ny = int((layout.ymax - layout.ymin) / res) + 6
        s_pix = (d_corr / 2.0) / res
        ca, cb = np.sqrt(site_corr), np.sqrt(1.0 - site_corr)

        def one():
            g = gaussian_filter(rng.standard_normal((self.ny, self.nx), dtype=np.float32), s_pix, mode="wrap")
            return g / g.std()

        common = one() if site_corr > 0 else 0.0
        f = np.empty((n_sites, self.ny, self.nx), dtype=np.float32)     # one contiguous plane per site
        for m in range(n_sites):
            f[m] = ca * common + cb * one()
        self.f = np.ascontiguousarray(f.transpose(1, 2, 0))              # (ny, nx, M) for fast lookups
        self._flat = self.f.reshape(-1, n_sites)

    def _weights(self, x, y):
        gx = np.clip((x - self.x0) / self.res, 0.0, self.nx - 1.001)
        gy = np.clip((y - self.y0) / self.res, 0.0, self.ny - 1.001)
        ix, iy = gx.astype(int), gy.astype(int)
        return iy * self.nx + ix, (gx - ix).astype(np.float32), (gy - iy).astype(np.float32)

    def at(self, x, y) -> np.ndarray:
        """Bilinear interpolation at points (P,) -> (P, M).

        Evaluated as ``f00 (1-tx)(1-ty) + f10 tx (1-ty) + f01 (1-tx) ty + f11 tx ty``
        from left to right, with the products in that order.
        """
        k, tx, ty = self._weights(x, y)
        tx, ty = tx[:, None], ty[:, None]
        ux, uy = 1 - tx, 1 - ty
        f, nx = self._flat, self.nx
        v = np.take(f, k, axis=0)
        v *= ux
        v *= uy
        for kk, a, b in ((k + 1, tx, uy), (k + nx, ux, ty), (k + nx + 1, tx, ty)):
            w = np.take(f, kk, axis=0)
            w *= a
            w *= b
            v += w
        return v

    def at_pairs(self, x, y, p, m) -> np.ndarray:
        """Same values as ``at(x, y)[p, m]`` for the point/site pairs ``(p, m)`` only."""
        k, tx, ty = self._weights(x, y)
        k, tx, ty = k[p], tx[p], ty[p]
        ux, uy = 1 - tx, 1 - ty
        f, nx = self._flat, self.nx
        v = f[k, m] * ux
        v *= uy
        for kk, a, b in ((k + 1, tx, uy), (k + nx, ux, ty), (k + nx + 1, tx, ty)):
            w = f[kk, m] * a
            w *= b
            v += w
        return v


class RadioMap:
    """Place-tied part of the radio environment of one world."""

    def __init__(self, layout: Layout, radio, seed: int):
        self.layout, self.radio = layout, radio
        self.is_grid = layout.is_grid
        res = float(radio.map_res_m) if self.is_grid else max(float(radio.map_res_m), 2.0)
        pad = 3.0 * res
        self.res = res
        self.x0, self.y0 = layout.xmin - pad, layout.ymin - pad
        self.nx = int(np.ceil((layout.xmax - layout.xmin + 2 * pad) / res)) + 1
        self.ny = int(np.ceil((layout.ymax - layout.ymin + 2 * pad) / res)) + 1
        M = layout.n_sites
        XX, YY = np.meshgrid(self.x0 + np.arange(self.nx) * res, self.y0 + np.arange(self.ny) * res)
        rng_shadow, rng_los = streams(seed, "map", 2)

        # nominal plan on a 2 m raster: nearest site (equal power and height, no buildings)
        self.nres = 2.0
        nnx = int((layout.xmax - layout.xmin + 2 * pad) / self.nres) + 2
        nny = int((layout.ymax - layout.ymin + 2 * pad) / self.nres) + 2
        NX, NY = np.meshgrid(self.x0 + np.arange(nnx) * self.nres, self.y0 + np.arange(nny) * self.nres)
        nearest = cKDTree(layout.sites).query(np.c_[NX.ravel(), NY.ravel()])[1]
        self.best_nominal = nearest.reshape(nny, nnx).astype(np.int16)

        mask = layout.street_mask(XX, YY, margin=2.0 * res)
        px, py = XX[mask], YY[mask]
        P = len(px)
        self.n_pix = P
        self.idx = np.full((self.ny, self.nx), P, dtype=np.int64)    # pixel -> row; off-street -> dummy row P
        self.idx[mask] = np.arange(P)
        self.has_field = radio.place_share > 0.0
        shadow = None
        if self.has_field:
            fres = min(2.0, radio.shadow_decorr_m / 4.0) if radio.shadow_decorr_m >= 4.0 else res
            shadow = GaussianField(rng_shadow, layout, M, radio.shadow_decorr_m, max(fres, res),
                                   radio.shadow_site_corr).at(px, py)
            shadow *= np.float32(np.sqrt(radio.place_share))
        self.los = None
        self.los_share = float("nan")
        self.gain = np.empty((P + 1, M), dtype=np.float32)            # last row: off-street dummy
        gain = self.gain[:P]
        if self.is_grid:
            los = los_matrix(px, py, layout.sites, layout.buildings)
            d2 = np.hypot(px[:, None] - layout.sites[None, :, 0], py[:, None] - layout.sites[None, :, 1])
            if radio.clutter_los:
                # spatially consistent LOS state; only links that the buildings leave clear need it
                ip, im = np.nonzero(los)
                lat = GaussianField(rng_los, layout, M, radio.los_corr_m, 5.0, 0.0).at_pairs(px, py, ip, im)
                dd = d2[ip, im]
                los[ip, im] = lat < ndtri(np.clip(p_los(dd, radio.pathloss), 1e-9, 1.0 - 1e-9))
            gain[...] = path_loss(d2, los, radio.pathloss, radio.carrier_ghz, radio.bs_height_m,
                                  radio.ue_height_m)
            np.negative(gain, out=gain)
            if shadow is not None:
                shadow *= np.where(los, np.float32(radio.shadow_los_db), np.float32(radio.shadow_nlos_db))
                gain += shadow
            self.los = np.zeros((P + 1, M), dtype=bool)
            self.los[:P] = los
            self.los_share = float(los.mean())
        elif shadow is not None:
            gain[...] = shadow
        else:
            gain[...] = 0.0
        self.gain[P] = FLOOR_DB if self.is_grid else 0.0

    # ------------------------------------------------------------------
    def _grid_coords(self, x, y):
        gx = np.clip((np.asarray(x, dtype=float) - self.x0) / self.res, 0.0, self.nx - 1.001)
        gy = np.clip((np.asarray(y, dtype=float) - self.y0) / self.res, 0.0, self.ny - 1.001)
        return gx, gy

    def lookup(self, x, y) -> np.ndarray:
        """Bilinear interpolation of the static gain (or shadowing) map at points (P,) -> (P, M)."""
        gx, gy = self._grid_coords(x, y)
        ix, iy = gx.astype(np.int64), gy.astype(np.int64)
        tx = (gx - ix).astype(np.float32)
        ty = (gy - iy).astype(np.float32)
        idx = self.idx
        w = np.stack([(1 - tx) * (1 - ty), tx * (1 - ty), (1 - tx) * ty, tx * ty]).astype(np.float32)
        p = np.stack([idx[iy, ix], idx[iy, ix + 1], idx[iy + 1, ix], idx[iy + 1, ix + 1]])
        v = np.take(self.gain, p[0], axis=0) * w[0][:, None]
        for q in (1, 2, 3):
            v += np.take(self.gain, p[q], axis=0) * w[q][:, None]
        return v

    def los_at(self, x, y) -> np.ndarray:
        """Line-of-sight state at points (nearest pixel) -> (P, M) bool (street grid only)."""
        gx, gy = self._grid_coords(x, y)
        return self.los[self.idx[np.rint(gy).astype(int), np.rint(gx).astype(int)]]

    def nominal_cell(self, x, y) -> np.ndarray:
        """Nominal best server (nearest site) at points of any shape."""
        ny, nx = self.best_nominal.shape
        ix = np.clip(np.rint((np.asarray(x) - self.x0) / self.nres).astype(int), 0, nx - 1)
        iy = np.clip(np.rint((np.asarray(y) - self.y0) / self.nres).astype(int), 0, ny - 1)
        return self.best_nominal[iy, ix]
