# SPDX-License-Identifier: MIT
"""Radio maps from a file: ray tracing or measurements (``radio.map_file``; since 1.12.0).

TR 38.901 V19.5.0 clause 8 (map-based hybrid channel model) creates the channel from deterministic ray
tracing on a digitized map plus stochastic components; it is "not calibrated and can be used per company
basis", and the format of the map is left to the implementation.  HandoverLab takes the deterministic
large-scale part from such a map: the **path gain** of every site at every pixel [dB], without transmit power
and antenna gains (HandoverLab adds those, or the beams).  The small-scale part is not modelled, as everywhere
in HandoverLab.

File format (``.npz``, format ``"handoverlab-radiomap"``, version 1):

=========  =================  ===========================================================================
key        shape / type       meaning
=========  =================  ===========================================================================
format     str                ``"handoverlab-radiomap"``
version    int                ``1``
x0, y0     float              coordinates of the centre of pixel ``[0, 0]`` [m]
res        float              pixel size [m]
idx        (ny, nx) int32     row of ``gain_db`` for every pixel, ``-1`` where there is no value
gain_db    (P, M) float32     path gain of every site [dB] (negative), one row per pixel with a value
los        (P, M) bool        optional: line of sight (sets the shadowing standard deviation of the part
                              of the shadowing that moves with the user, ``radio.place_share < 1``)
sites      (M, 2) float64     site positions [m]; must equal those of the scenario's layout
source     str                free text: where the map comes from
=========  =================  ===========================================================================

Pixel ``(iy, ix)`` has its centre at ``(x0 + ix * res, y0 + iy * res)``; values between pixel centres are
interpolated bilinearly.  Users must stay where there are values: on the street grid in the streets, in the
open area and the indoor hall everywhere in the area.
"""
from __future__ import annotations

import hashlib
import os
from typing import Dict, Optional

import numpy as np

FORMAT = "handoverlab-radiomap"
VERSION = 1


class MapFileError(ValueError):
    """A radio-map file that cannot be used."""


def file_sha256(path: str) -> str:
    """SHA-256 of a file (stored with the scenario so that a changed map is noticed)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def save_map(path: str, x0: float, y0: float, res: float, idx: np.ndarray, gain_db: np.ndarray,
             sites: np.ndarray, los: Optional[np.ndarray] = None, source: str = "") -> str:
    """Write a radio-map file (see the module text) and return its path."""
    idx = np.asarray(idx, dtype=np.int32)
    gain_db = np.asarray(gain_db, dtype=np.float32)
    sites = np.asarray(sites, dtype=np.float64).reshape(-1, 2)
    if gain_db.ndim != 2 or gain_db.shape[1] != len(sites):
        raise MapFileError("gain_db must have one column per site")
    if idx.ndim != 2 or idx.max() >= len(gain_db) or idx.min() < -1:
        raise MapFileError("idx must be a 2-D raster of rows of gain_db or -1")
    extra = {} if los is None else {"los": np.asarray(los, dtype=bool)}
    if los is not None and extra["los"].shape != gain_db.shape:
        raise MapFileError("los must have the shape of gain_db")
    with open(path, "wb") as f:
        np.savez_compressed(f, format=np.array(FORMAT), version=np.array(VERSION), x0=np.array(float(x0)),
                            y0=np.array(float(y0)), res=np.array(float(res)), idx=idx, gain_db=gain_db,
                            sites=sites, source=np.array(str(source)), **extra)
    return path


def load_map(path: str) -> Dict[str, object]:
    """Read and check a radio-map file; returns its arrays as a dictionary."""
    if not os.path.exists(path):
        raise MapFileError("radio map %r not found" % path)
    with np.load(path, allow_pickle=False) as z:
        keys = set(z.files)
        if "format" not in keys or str(z["format"]) != FORMAT:
            raise MapFileError("%s is not a HandoverLab radio map (format %r)" % (path, FORMAT))
        version = int(z["version"])
        if version > VERSION:
            raise MapFileError("%s has format version %d; this HandoverLab reads up to %d" % (path, version, VERSION))
        missing = {"x0", "y0", "res", "idx", "gain_db", "sites"} - keys
        if missing:
            raise MapFileError("%s lacks %s" % (path, ", ".join(sorted(missing))))
        out = {k: z[k] for k in z.files}
    out["x0"], out["y0"], out["res"] = float(out["x0"]), float(out["y0"]), float(out["res"])
    out["source"] = str(out.get("source", ""))
    if out["res"] <= 0 or out["gain_db"].shape[1] != len(out["sites"]):
        raise MapFileError("%s: res must be positive and gain_db must have one column per site" % path)
    return out


def export_map(rmap, path: str, source: str = "") -> str:
    """Write the radio map of a street-grid world (``world.radio_map``) as a file.

    Importing it again (``radio.map_file``) gives the same received powers bit for bit, so a run gives the
    same event log; the open area draws its LOS state along each user's path and has no static map.
    """
    if not rmap.is_grid:
        raise MapFileError("only the street grid (or an imported map) has a static radio map to export")
    P = rmap.n_pix
    idx = np.where(rmap.idx == P, -1, rmap.idx).astype(np.int32)
    los = rmap.los[:P] if rmap.los is not None else None
    return save_map(path, rmap.x0, rmap.y0, rmap.res, idx, rmap.gain[:P], rmap.layout.sites, los,
                    source or "exported from a HandoverLab street-grid world")


def map_from_raster(path: str, x0: float, y0: float, res: float, gain_db: np.ndarray, sites: np.ndarray,
                    valid: Optional[np.ndarray] = None, los: Optional[np.ndarray] = None, source: str = "") -> str:
    """Write a map from a full raster ``gain_db`` (ny, nx, M), e.g. the path-gain map of a ray tracer.

    ``valid`` (ny, nx) marks the pixels with a value (default: all finite values).
    """
    g = np.asarray(gain_db, dtype=np.float64)
    if g.ndim != 3:
        raise MapFileError("gain_db must have the shape (ny, nx, sites)")
    ok = np.all(np.isfinite(g), axis=2) if valid is None else np.asarray(valid, dtype=bool)
    idx = np.full(ok.shape, -1, dtype=np.int32)
    idx[ok] = np.arange(int(ok.sum()))
    rows = g[ok]
    lrows = None if los is None else np.asarray(los, dtype=bool)[ok]
    return save_map(path, x0, y0, res, idx, rows, sites, lrows, source or "raster")


def map_from_points(path: str, x: np.ndarray, y: np.ndarray, gain_db: np.ndarray, sites: np.ndarray,
                    area, res: float = 2.0, holdout: float = 0.1, seed: int = 1, source: str = ""):
    """Interpolate measured path gains (points x, y with ``gain_db`` (N, M)) onto a raster and write the map.

    ``area`` is ``(xmin, xmax, ymin, ymax)``.  Linear interpolation per site (SciPy ``griddata``), nearest
    value outside the convex hull of the points.  A share ``holdout`` of the points is left out first and the
    interpolation error on them is returned: ``(path, {"rmse_db", "mae_db", "n_holdout"})``; the map itself
    is then built from all points.
    """
    from scipy.interpolate import griddata
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    g = np.asarray(gain_db, dtype=float).reshape(len(x), -1)
    rng = np.random.default_rng(seed)
    test = rng.random(len(x)) < holdout
    err = None
    if test.any() and (~test).sum() >= 3:
        pts, q = np.c_[x[~test], y[~test]], np.c_[x[test], y[test]]
        pred = np.empty((int(test.sum()), g.shape[1]))
        for m in range(g.shape[1]):
            lin = griddata(pts, g[~test, m], q, method="linear")
            near = griddata(pts, g[~test, m], q, method="nearest")
            pred[:, m] = np.where(np.isfinite(lin), lin, near)
        d = pred - g[test]
        err = {"rmse_db": float(np.sqrt(np.mean(d ** 2))), "mae_db": float(np.mean(np.abs(d))),
               "n_holdout": int(test.sum())}
    xmin, xmax, ymin, ymax = area
    nx, ny = int(np.ceil((xmax - xmin) / res)) + 1, int(np.ceil((ymax - ymin) / res)) + 1
    XX, YY = np.meshgrid(xmin + np.arange(nx) * res, ymin + np.arange(ny) * res)
    q = np.c_[XX.ravel(), YY.ravel()]
    out = np.empty((len(q), g.shape[1]))
    pts = np.c_[x, y]
    for m in range(g.shape[1]):
        lin = griddata(pts, g[:, m], q, method="linear")
        near = griddata(pts, g[:, m], q, method="nearest")
        out[:, m] = np.where(np.isfinite(lin), lin, near)
    map_from_raster(path, xmin, ymin, res, out.reshape(ny, nx, -1), sites,
                    source=source or "interpolated from %d measured points" % len(x))
    return path, err


__all__ = ["FORMAT", "VERSION", "MapFileError", "file_sha256", "save_map", "load_map", "export_map",
           "map_from_raster", "map_from_points"]
