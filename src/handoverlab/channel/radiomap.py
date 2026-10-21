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
from .pathloss import los_shadow_sd, mix_db, p_los, path_loss, soft_los_power_weight

FLOOR_DB = -300.0


class GaussianField:
    """Unit-variance Gaussian random fields, one per site, on a raster.

    Correlation exp(-(d / d_corr)^2); the fields of different sites share a
    common component so that their mutual correlation is ``site_corr``.

    With a wrap-around period of the layout (since 1.11.0) the raster spans
    exactly one period in x and the field is periodic in x: the filter wraps
    around and the interpolation takes the neighbours across the seam.
    """

    def __init__(self, rng, layout: Layout, n_sites: int, d_corr: float, res: float, site_corr: float):
        self.period = layout.period_x
        if self.period:
            self.nx = max(2, int(round(self.period / res)))
            res = self.period / self.nx                        # a whole number of pixels per period
            self.res = res
            self.x0, self.y0 = layout.xmin, layout.ymin - 2 * res
        else:
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

    def _periodic(self, x, y):
        """Values (P, M) at points with the field periodic in x."""
        gx = np.mod((np.asarray(x, dtype=float) - self.x0) / self.res, self.nx)
        gy = np.clip((np.asarray(y, dtype=float) - self.y0) / self.res, 0.0, self.ny - 1.001)
        ix, iy = np.minimum(gx.astype(int), self.nx - 1), gy.astype(int)
        jx = (ix + 1) % self.nx
        tx, ty = (gx - ix).astype(np.float32)[:, None], (gy - iy).astype(np.float32)[:, None]
        f = self.f
        return (f[iy, ix] * (1 - tx) * (1 - ty) + f[iy, jx] * tx * (1 - ty) + f[iy + 1, ix] * (1 - tx) * ty
                + f[iy + 1, jx] * tx * ty)

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
        if self.period:
            return self._periodic(x, y)
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
        if self.period:
            return self._periodic(np.asarray(x)[p], np.asarray(y)[p])[np.arange(len(p)), m]
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

    def __init__(self, layout: Layout, radio, seed: int, sub: int = 0):
        self.layout, self.radio = layout, radio
        self.imported = False
        self.is_grid = layout.is_grid
        res = float(radio.map_res_m) if self.is_grid else max(float(radio.map_res_m), 2.0)
        pad = 3.0 * res
        self.res = res
        self.x0, self.y0 = layout.xmin - pad, layout.ymin - pad
        self.nx = int(np.ceil((layout.xmax - layout.xmin + 2 * pad) / res)) + 1
        self.ny = int(np.ceil((layout.ymax - layout.ymin + 2 * pad) / res)) + 1
        M = layout.n_sites
        XX, YY = np.meshgrid(self.x0 + np.arange(self.nx) * res, self.y0 + np.arange(self.ny) * res)
        rng_shadow, rng_los = streams(seed, "map", 2, sub)    # sub: a further layer (since 1.10.0)

        self._nominal_plan(layout, pad)

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
                thr = ndtri(np.clip(p_los(dd, radio.pathloss), 1e-9, 1.0 - 1e-9))
                los[ip, im] = lat < thr
                if radio.soft_los:                        # soft LOS on the links the buildings leave clear
                    w = soft_los_power_weight(thr - lat, radio.carrier_ghz, radio.soft_los_d_m)
                    sh = shadow[ip, im].astype(np.float64) if shadow is not None else 0.0
                    del lat, thr
            gain[...] = path_loss(d2, los, radio.pathloss, radio.carrier_ghz, radio.bs_height_m,
                                  radio.ue_height_m)
            np.negative(gain, out=gain)
            if shadow is not None:
                if radio.shadow_los_far_db is None:
                    shadow *= np.where(los, np.float32(radio.shadow_los_db), np.float32(radio.shadow_nlos_db))
                else:
                    shadow *= np.where(los, los_shadow_sd(d2, radio), radio.shadow_nlos_db).astype(np.float32)
                gain += shadow
            if radio.clutter_los and radio.soft_los:
                args = (radio.pathloss, radio.carrier_ghz, radio.bs_height_m, radio.ue_height_m)
                g_l = -path_loss(dd, True, *args) + los_shadow_sd(dd, radio) * sh
                g_n = -path_loss(dd, False, *args) + radio.shadow_nlos_db * sh
                gain[ip, im] = mix_db(w, g_l, g_n)
                del g_l, g_n, w, sh
            self.los = np.zeros((P + 1, M), dtype=bool)
            self.los[:P] = los
            self.los_share = float(los.mean())
        elif shadow is not None:
            gain[...] = shadow
        else:
            gain[...] = 0.0
        self.gain[P] = FLOOR_DB if self.is_grid else 0.0

    def _nominal_plan(self, layout: Layout, pad: float) -> None:
        """Nominal plan on a 2 m raster: nearest site (equal power and height, no buildings)."""
        self.nres = 2.0
        nnx = int((layout.xmax - layout.xmin + 2 * pad) / self.nres) + 2
        nny = int((layout.ymax - layout.ymin + 2 * pad) / self.nres) + 2
        NX, NY = np.meshgrid(self.x0 + np.arange(nnx) * self.nres, self.y0 + np.arange(nny) * self.nres)
        if layout.period_x:                                    # nearest image of every site (wrap-around)
            nearest = np.argmin(layout.distances(NX.ravel(), NY.ravel()), axis=1)
        else:
            nearest = cKDTree(layout.sites).query(np.c_[NX.ravel(), NY.ravel()])[1]
        self.best_nominal = nearest.reshape(nny, nnx).astype(np.int16)

    @classmethod
    def from_file(cls, layout: Layout, radio, path: str) -> "RadioMap":
        """Radio map read from ``radio.map_file`` (since 1.12.0; see :mod:`handoverlab.mapfile`).

        The path gains of the file take the place of path loss, LOS state and place-tied shadowing; the map
        is static, like the street grid's, so the LOS process along the users' paths is not drawn.
        """
        from ..mapfile import MapFileError, load_map
        d = load_map(path)
        sites = np.asarray(d["sites"], dtype=float)
        if sites.shape != layout.sites.shape or not np.allclose(sites, layout.sites, atol=1e-6):
            raise MapFileError("%s: its %d sites differ from the %d sites of the layout" % (path, len(sites),
                                                                                       layout.n_sites))
        self = cls.__new__(cls)
        self.layout, self.radio, self.imported = layout, radio, True
        self.is_grid = True                                    # static lookup, as on the street grid
        self.res, self.x0, self.y0 = d["res"], d["x0"], d["y0"]
        idx = np.asarray(d["idx"], dtype=np.int64)
        self.ny, self.nx = idx.shape
        gain = np.asarray(d["gain_db"], dtype=np.float32)
        P = len(gain)
        self.n_pix = P
        self.idx = np.where(idx < 0, P, idx)
        self.gain = np.empty((P + 1, layout.n_sites), dtype=np.float32)
        self.gain[:P] = gain
        self.gain[P] = FLOOR_DB
        self.has_field = False
        if "los" in d:
            self.los = np.zeros((P + 1, layout.n_sites), dtype=bool)
            self.los[:P] = d["los"]
            self.los_share = float(self.los[:P].mean())
        else:
            self.los = np.zeros((P + 1, layout.n_sites), dtype=bool)
            self.los_share = float("nan")
        # the area where users go must have values: the streets on the grid, the whole area otherwise
        xmax = self.x0 + (self.nx - 1) * self.res
        ymax = self.y0 + (self.ny - 1) * self.res
        short = (self.x0 > layout.xmin + 1e-6 or self.y0 > layout.ymin + 1e-6 or xmax < layout.xmax - 1e-6
                 or ymax < layout.ymax - 1e-6)
        if short:
            raise MapFileError("%s covers x %.1f..%.1f, y %.1f..%.1f m, not the layout's %.1f..%.1f, %.1f..%.1f m"
                               % (path, self.x0, xmax, self.y0, ymax, layout.xmin, layout.xmax, layout.ymin,
                                  layout.ymax))
        XX, YY = np.meshgrid(self.x0 + np.arange(self.nx) * self.res, self.y0 + np.arange(self.ny) * self.res)
        inside = (XX >= layout.xmin) & (XX <= layout.xmax) & (YY >= layout.ymin) & (YY <= layout.ymax)
        need = inside & layout.street_mask(XX, YY, margin=self.res)    # incl. the neighbours read by interpolation
        if np.any(self.idx[need] == P):
            raise MapFileError("%s has no values at %d pixels where users can be" % (path,
                                                                                 int(np.sum(self.idx[need] == P))))
        self._nominal_plan(layout, max(0.0, layout.xmin - self.x0))
        return self

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
