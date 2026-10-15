# SPDX-License-Identifier: MIT
"""Deployment geometry: a street grid with buildings, or an open area.

Street grid
    The urban grid of 3GPP TR 37.885 Annex A: street centre lines every
    ``pitch`` metres (433 m in x, 250 m in y), streets 20 m wide, the space
    between the streets filled by building blocks.  ``blocks = (nx, ny)``
    gives ``nx + 1`` north-south and ``ny + 1`` east-west streets.  Sites stand
    on the pavement every ``site_spacing`` metres along every street,
    alternately on the two sides.  A link has line of sight if the straight
    segment between site and user crosses no building block.

Open area
    The same rectangle without buildings, sites on a hexagonal grid.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

import numpy as np


@dataclass
class Layout:
    kind: str                # "street_grid" or "open_area"
    sites: np.ndarray        # (M, 2) site positions [m]
    buildings: np.ndarray    # (B, 4) rectangles x0, y0, x1, y1 [m]
    xs: np.ndarray           # x of the north-south street centre lines
    ys: np.ndarray           # y of the east-west street centre lines
    street_width: float
    xmin: float
    xmax: float
    ymin: float
    ymax: float

    @property
    def n_sites(self) -> int:
        return len(self.sites)

    @property
    def is_grid(self) -> bool:
        return self.kind == "street_grid"

    def street_mask(self, x, y, margin: float = 0.0) -> np.ndarray:
        """True where a point lies in a street (grid) or anywhere (open area)."""
        if not self.is_grid:
            return np.ones(np.broadcast(x, y).shape, dtype=bool)
        hw = self.street_width / 2.0 + margin
        in_x = (np.abs(np.asarray(x)[..., None] - self.xs) <= hw).any(-1)
        in_y = (np.abs(np.asarray(y)[..., None] - self.ys) <= hw).any(-1)
        return in_x | in_y


def _along(length: float, spacing: float) -> np.ndarray:
    """Positions along a street of the given length, ``spacing`` apart, centred."""
    n = max(1, int(round(length / spacing)))
    return (np.arange(n) - (n - 1) / 2.0) * spacing


def street_grid(blocks: Tuple[int, int] = (3, 3), pitch: Tuple[float, float] = (433.0, 250.0),
                street_width: float = 20.0, site_spacing: float = 100.0, site_offset: float = 9.0,
                sites: Optional[Sequence[Sequence[float]]] = None) -> Layout:
    """Street grid of ``blocks`` centred on the origin.

    Without an explicit ``sites`` list, sites are placed every ``site_spacing``
    metres along every street; a site on a north-south street closer than
    0.4 ``site_spacing`` to a site on an east-west street is left out, so that
    intersections are not covered twice.
    """
    nbx, nby = int(blocks[0]), int(blocks[1])
    px, py = pitch
    xs = (np.arange(nbx + 1) - nbx / 2.0) * px
    ys = (np.arange(nby + 1) - nby / 2.0) * py
    hw = street_width / 2.0
    bld = [(xs[i] + hw, ys[j] + hw, xs[i + 1] - hw, ys[j + 1] - hw) for i in range(nbx) for j in range(nby)]
    if sites is None:
        pts = []
        for j, y in enumerate(ys):                                  # east-west streets
            for i, s in enumerate(_along(xs[-1] - xs[0], site_spacing)):
                side = 1.0 if (i + j) % 2 == 0 else -1.0
                pts.append((s, y + side * site_offset))
        ew = np.array(pts)
        for i, x in enumerate(xs):                                  # north-south streets
            for j, s in enumerate(_along(ys[-1] - ys[0], site_spacing)):
                side = 1.0 if (i + j) % 2 == 0 else -1.0
                p = (x + side * site_offset, s)
                if np.min(np.hypot(ew[:, 0] - p[0], ew[:, 1] - p[1])) >= 0.4 * site_spacing:
                    pts.append(p)
        site_arr = np.array(pts)
    else:
        site_arr = np.asarray(sites, dtype=float).reshape(-1, 2)
    return Layout("street_grid", site_arr, np.array(bld), xs, ys, street_width,
                  xs[0] - hw, xs[-1] + hw, ys[0] - hw, ys[-1] + hw)


def open_area(size: Tuple[float, float] = (1319.0, 770.0), site_spacing: float = 100.0,
              sites: Optional[Sequence[Sequence[float]]] = None) -> Layout:
    """Open rectangle centred on the origin with a hexagonal site grid."""
    w, h = size
    if sites is None:
        dy = site_spacing * np.sqrt(3.0) / 2.0
        ny = int(h / dy) + 1
        nx = int(w / site_spacing) + 1
        pts = []
        for j in range(ny):
            y = (j - (ny - 1) / 2.0) * dy
            if j % 2 == 0:
                row = (np.arange(nx) - (nx - 1) / 2.0) * site_spacing
            else:                                                   # odd rows shifted by half a spacing
                row = (np.arange(nx - 1) - (nx - 2) / 2.0) * site_spacing
            pts.extend((x, y) for x in row)
        site_arr = np.array(pts)
    else:
        site_arr = np.asarray(sites, dtype=float).reshape(-1, 2)
    return Layout("open_area", site_arr, np.zeros((0, 4)), np.array([]), np.array([]), 0.0,
                  -w / 2.0, w / 2.0, -h / 2.0, h / 2.0)


def make_layout(cfg) -> Layout:
    """Layout from a :class:`handoverlab.config.LayoutConfig`."""
    if cfg.kind == "street_grid":
        return street_grid(cfg.blocks, cfg.pitch_m, cfg.street_width_m, cfg.site_spacing_m,
                           cfg.site_offset_m, cfg.sites)
    if cfg.kind == "open_area":
        return open_area(cfg.size_m, cfg.site_spacing_m, cfg.sites)
    raise ValueError("unknown layout kind %r" % cfg.kind)


def los_matrix(px, py, sites: np.ndarray, buildings: np.ndarray) -> np.ndarray:
    """Line of sight between points and sites (slab test against rectangles).

    Returns a boolean array (P, M): True if the segment site -> point crosses
    no rectangle of ``buildings``.  A segment that only touches an edge is not
    blocked.  Points on the same side of a rectangle as the site cannot be
    blocked by it and are skipped before the slab test.
    """
    px = np.asarray(px, dtype=float)
    py = np.asarray(py, dtype=float)
    P, M = len(px), len(sites)
    res = np.ones((P, M), dtype=bool)
    if len(buildings) == 0 or P == 0:
        return res
    tiny = 1e-9
    rects = np.asarray(buildings, dtype=float).tolist()
    for m in range(M):
        sx, sy = float(sites[m, 0]), float(sites[m, 1])
        dx = px - sx
        dy = py - sy
        dx = np.where(np.abs(dx) < tiny, tiny, dx)
        dy = np.where(np.abs(dy) < tiny, tiny, dy)
        blocked = np.zeros(P, dtype=bool)
        for x0, y0, x1, y1 in rects:
            skip = blocked.copy()
            if sx < x0:
                skip |= px < x0
            if sx > x1:
                skip |= px > x1
            if sy < y0:
                skip |= py < y0
            if sy > y1:
                skip |= py > y1
            i = np.flatnonzero(~skip)
            if not i.size:
                continue
            dxi, dyi = dx[i], dy[i]
            tx1 = (x0 - sx) / dxi
            tx2 = (x1 - sx) / dxi
            ty1 = (y0 - sy) / dyi
            ty2 = (y1 - sy) / dyi
            tn = np.maximum(np.maximum(np.minimum(tx1, tx2), np.minimum(ty1, ty2)), 0.0)
            tf = np.minimum(np.minimum(np.maximum(tx1, tx2), np.maximum(ty1, ty2)), 1.0)
            blocked[i[(tf - tn) > 1e-9]] = True
        res[:, m] = ~blocked
    return res
