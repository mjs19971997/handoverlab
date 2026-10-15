# SPDX-License-Identifier: MIT
"""Mobility profiles and trajectories.

Street grid: users follow the street centre lines and choose a direction at
every intersection (straight 0.5, left 0.25, right 0.25, as in the urban case
of TR 37.885); each user keeps a constant lateral displacement from the centre
line and a constant speed.  Open area: straight legs between random waypoints.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np

from .config import SpeedGroup

# name -> speed groups (share, v_min, v_max [m/s], lateral displacement range [m])
PROFILES: Dict[str, List[SpeedGroup]] = {
    "ped": [SpeedGroup(1.0, 1.2, 1.8, (6.5, 8.5))],        # pedestrians on the pavement
    "veh8": [SpeedGroup(1.0, 7.2, 8.8, (0.0, 3.0))],       # about 30 km/h
    "veh16": [SpeedGroup(1.0, 14.4, 17.6, (0.0, 3.0))],    # about 60 km/h
    "veh30": [SpeedGroup(1.0, 27.0, 33.0, (0.0, 3.0))],    # about 110 km/h
    "mix": [SpeedGroup(0.4, 1.2, 1.8, (6.5, 8.5)), SpeedGroup(0.3, 7.2, 8.8, (0.0, 3.0)),
            SpeedGroup(0.3, 14.4, 17.6, (0.0, 3.0))],
    "c8": [SpeedGroup(1.0, 8.0, 8.0, (0.0, 0.0))],         # constant speeds on the centre line
    "c16": [SpeedGroup(1.0, 16.0, 16.0, (0.0, 0.0))],
    "c30": [SpeedGroup(1.0, 30.0, 30.0, (0.0, 0.0))],
}

_DX = np.array([1.0, 0.0, -1.0, 0.0])      # heading index 0: east, 1: north, 2: west, 3: south
_DY = np.array([0.0, 1.0, 0.0, -1.0])


def draw_users(groups, n_users: int, rng) -> Tuple[np.ndarray, np.ndarray]:
    """Speed (U,) and lateral displacement (U, 2) of every user."""
    shares = np.array([g.share for g in groups])
    cls = rng.choice(len(groups), size=n_users, p=shares / shares.sum())
    v = np.empty(n_users)
    off = np.empty((n_users, 2))
    for u in range(n_users):
        g = groups[cls[u]]
        v[u] = rng.uniform(g.v_min, g.v_max)
        off[u] = rng.uniform(g.lateral_m[0], g.lateral_m[1], 2) * rng.choice([-1.0, 1.0], 2)
    return v, off


def grid_waypoints(layout, v: float, t_end: float, rng):
    """Break points (t, x, y, heading index) of one user on the street grid."""
    xs, ys = layout.xs, layout.ys
    len_ew = (xs[-1] - xs[0]) * len(ys)
    len_ns = (ys[-1] - ys[0]) * len(xs)
    if rng.random() < len_ew / (len_ew + len_ns):
        y = ys[rng.integers(len(ys))]
        x = rng.uniform(xs[0], xs[-1])
        h = int(rng.choice([0, 2]))
    else:
        x = xs[rng.integers(len(xs))]
        y = rng.uniform(ys[0], ys[-1])
        h = int(rng.choice([1, 3]))
    T, Xb, Yb, Hb = [0.0], [x], [y], [h]
    t = 0.0
    while t < t_end:
        if h == 0:                                            # next intersection ahead
            nx_, ny_ = xs[xs > x + 1e-6].min(), y
        elif h == 2:
            nx_, ny_ = xs[xs < x - 1e-6].max(), y
        elif h == 1:
            nx_, ny_ = x, ys[ys > y + 1e-6].min()
        else:
            nx_, ny_ = x, ys[ys < y - 1e-6].max()
        t += (abs(nx_ - x) + abs(ny_ - y)) / v
        x, y = nx_, ny_
        ok = []                                               # directions that stay inside the area
        for turn, w in ((0, 0.5), (1, 0.25), (3, 0.25)):
            hh = (h + turn) % 4
            ex, ey = x + _DX[hh], y + _DY[hh]
            if xs[0] - 1e-6 <= ex <= xs[-1] + 1e-6 and ys[0] - 1e-6 <= ey <= ys[-1] + 1e-6:
                ok.append((hh, w))
        if ok:
            ws = np.array([w for _, w in ok])
            h = ok[int(rng.choice(len(ok), p=ws / ws.sum()))][0]
        else:
            h = (h + 2) % 4
        T.append(t); Xb.append(x); Yb.append(y); Hb.append(h)
    return np.array(T), np.array(Xb), np.array(Yb), np.array(Hb)


def open_waypoints(layout, v: float, t_end: float, rng, margin: float = 10.0):
    """Break points of one user in the open area (random waypoints, straight legs)."""
    x0, x1, y0, y1 = layout.xmin + margin, layout.xmax - margin, layout.ymin + margin, layout.ymax - margin
    x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
    T, Xb, Yb = [0.0], [x], [y]
    t = 0.0
    while t < t_end:
        nx_, ny_ = rng.uniform(x0, x1), rng.uniform(y0, y1)
        t += max(np.hypot(nx_ - x, ny_ - y), 1.0) / v
        x, y = nx_, ny_
        T.append(t); Xb.append(x); Yb.append(y)
    return np.array(T), np.array(Xb), np.array(Yb), None


def trajectories(layout, mobility, duration_s: float, step_s: float, rng):
    """Trajectories of all users.

    Returns ``x, y`` (S, U) positions [m], ``speed`` (U,) [m/s] and
    ``heading`` (S, U) [rad], one row per simulation step.
    """
    S = int(round(duration_s / step_s))
    U = mobility.users
    groups = mobility.groups if mobility.groups is not None else PROFILES[mobility.profile]
    v, off = draw_users(groups, U, rng)
    if not layout.is_grid:
        off[:] = 0.0
    t = np.arange(S) * step_s
    X = np.empty((S, U)); Y = np.empty((S, U)); TH = np.empty((S, U), dtype=np.float32)
    for u in range(U):
        if layout.is_grid:
            T, Xb, Yb, Hb = grid_waypoints(layout, v[u], duration_s + step_s, rng)
        else:
            T, Xb, Yb, Hb = open_waypoints(layout, v[u], duration_s + step_s, rng)
        X[:, u] = np.interp(t, T, Xb) + off[u, 0]
        Y[:, u] = np.interp(t, T, Yb) + off[u, 1]
        leg = np.clip(np.searchsorted(T, t, side="right") - 1, 0, len(T) - 2)
        if Hb is not None:
            TH[:, u] = np.arctan2(_DY[Hb[leg]], _DX[Hb[leg]])
        else:
            TH[:, u] = np.arctan2(Yb[leg + 1] - Yb[leg], Xb[leg + 1] - Xb[leg])
    return X, Y, v, TH
