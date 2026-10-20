# SPDX-License-Identifier: MIT
"""Mobility profiles and trajectories.

Street grid: users follow the street centre lines and choose a direction at
every intersection (straight 0.5, left 0.25, right 0.25, as in the urban case
of TR 37.885); each user keeps a constant lateral displacement from the centre
line and a constant speed.  Open area: straight legs between random waypoints.
Highway (since 1.0.0rc3): lane-keeping vehicles at a constant speed in one
lane; at the end of the road a vehicle turns into the same lane of the other
direction, so that it stays on the road without jumping.  Indoor (since
1.7.0): random waypoints as in the open area, 2 m away from the walls.
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
    # highway (since 1.0.0rc3); lateral range: displacement from the lane centre
    "hwy": [SpeedGroup(1.0, 70.0 / 3.6, 140.0 / 3.6, (0.0, 0.5))],    # 70-140 km/h
    "hwy70": [SpeedGroup(1.0, 63.0 / 3.6, 77.0 / 3.6, (0.0, 0.5))],   # about 70 km/h
    "hwy140": [SpeedGroup(1.0, 126.0 / 3.6, 140.0 / 3.6, (0.0, 0.5))],  # up to 140 km/h
    # TR 37.885 clause 6.1.2, highway option A (since 1.11.0): every vehicle at 140 km/h (baseline) or 70 km/h
    "v140": [SpeedGroup(1.0, 140.0 / 3.6, 140.0 / 3.6, (0.0, 0.5))],
    "v70": [SpeedGroup(1.0, 70.0 / 3.6, 70.0 / 3.6, (0.0, 0.5))],
    # indoor and rural (since 1.7.0): TR 38.901 Table 7.2-2 (indoor office: 3 km/h); rural users in cars at
    # 120 km/h (TR 38.913 rural evaluation; TR 38.901 Table 7.2-3 gives the users as 50 % indoor, 50 % in car)
    "ped3": [SpeedGroup(1.0, 2.7 / 3.6, 3.3 / 3.6, (0.0, 0.0))],      # about 3 km/h
    "veh120": [SpeedGroup(1.0, 108.0 / 3.6, 132.0 / 3.6, (0.0, 0.0))],  # about 120 km/h
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


def open_waypoints(layout, v: float, t_end: float, rng, margin: float = 10.0, min_dist: float = 0.0):
    """Break points of one user in the open area (random waypoints, straight legs).

    With ``min_dist > 0`` (since 1.7.0) a start or waypoint closer than that to a site is drawn again.
    """
    x0, x1, y0, y1 = layout.xmin + margin, layout.xmax - margin, layout.ymin + margin, layout.ymax - margin
    sites = layout.sites

    def point():
        while True:
            px, py = rng.uniform(x0, x1), rng.uniform(y0, y1)
            if min_dist <= 0.0 or np.min(np.hypot(sites[:, 0] - px, sites[:, 1] - py)) >= min_dist:
                return px, py

    x, y = point()
    T, Xb, Yb = [0.0], [x], [y]
    t = 0.0
    while t < t_end:
        nx_, ny_ = point()
        t += max(np.hypot(nx_ - x, ny_ - y), 1.0) / v
        x, y = nx_, ny_
        T.append(t); Xb.append(x); Yb.append(y)
    return np.array(T), np.array(Xb), np.array(Yb), None


def highway_waypoints(layout, v: float, t_end: float, rng):
    """Break points (t, x, y, heading index) of one vehicle on the highway.

    The vehicle starts at a random point of a random lane and direction and
    keeps its lane; at the end of the road it crosses to the same lane of the
    other direction (a short leg at its own speed) and drives back.
    """
    ys = layout.ys                                            # lane centre lines, south to north
    n = len(ys) // 2
    lane = int(rng.integers(n))
    h = int(rng.choice([0, 2]))                               # 0: east (southern lanes), 2: west
    x = rng.uniform(layout.xmin, layout.xmax)
    y_e, y_w = ys[n - 1 - lane], ys[n + lane]
    y = y_e if h == 0 else y_w
    T, Xb, Yb, Hb = [0.0], [x], [y], [h]
    t = 0.0
    while t < t_end:
        end = layout.xmax if h == 0 else layout.xmin
        t += abs(end - x) / v
        x = end
        ny_ = y_w if h == 0 else y_e
        T.append(t); Xb.append(x); Yb.append(y); Hb.append(1 if h == 0 else 3)
        t += abs(ny_ - y) / v
        y = ny_
        h = 2 if h == 0 else 0
        T.append(t); Xb.append(x); Yb.append(y); Hb.append(h)
    return np.array(T), np.array(Xb), np.array(Yb), np.array(Hb)


def trajectories(layout, mobility, duration_s: float, step_s: float, rng, min_dist: float = 0.0):
    """Trajectories of all users.

    Returns ``x, y`` (S, U) positions [m], ``speed`` (U,) [m/s] and
    ``heading`` (S, U) [rad], one row per simulation step.  ``min_dist``: minimum distance of a
    start or waypoint from every site in the open area and indoors (since 1.7.0).
    """
    S = int(round(duration_s / step_s))
    U = mobility.users
    groups = mobility.groups if mobility.groups is not None else PROFILES[mobility.profile]
    v, off = draw_users(groups, U, rng)
    if layout.kind == "highway":                              # lane keeping: lateral offset within the lane
        off[:, 0] = 0.0
        off[:, 1] = np.clip(off[:, 1], -layout.street_width / 2.0, layout.street_width / 2.0)
    elif not layout.is_grid:
        off[:] = 0.0
    t = np.arange(S) * step_s
    X = np.empty((S, U)); Y = np.empty((S, U)); TH = np.empty((S, U), dtype=np.float32)
    for u in range(U):
        if layout.is_grid:
            T, Xb, Yb, Hb = grid_waypoints(layout, v[u], duration_s + step_s, rng)
        elif layout.kind == "highway" and layout.period_x:
            # wrap-around (since 1.11.0): the vehicle keeps its lane and direction and re-enters at the other end
            ys = layout.ys
            n = len(ys) // 2
            lane = int(rng.integers(n))
            h = int(rng.choice([0, 2]))
            x0 = rng.uniform(layout.xmin, layout.xmax)
            sgn = 1.0 if h == 0 else -1.0
            X[:, u] = layout.wrap_x(x0 + sgn * v[u] * t + off[u, 0])
            Y[:, u] = (ys[n - 1 - lane] if h == 0 else ys[n + lane]) + off[u, 1]
            TH[:, u] = 0.0 if h == 0 else np.pi
            continue
        elif layout.kind == "highway":
            T, Xb, Yb, Hb = highway_waypoints(layout, v[u], duration_s + step_s, rng)
        elif layout.kind == "indoor":
            T, Xb, Yb, Hb = open_waypoints(layout, v[u], duration_s + step_s, rng, margin=2.0, min_dist=min_dist)
        else:
            T, Xb, Yb, Hb = open_waypoints(layout, v[u], duration_s + step_s, rng, min_dist=min_dist)
        X[:, u] = np.interp(t, T, Xb) + off[u, 0]
        Y[:, u] = np.interp(t, T, Yb) + off[u, 1]
        leg = np.clip(np.searchsorted(T, t, side="right") - 1, 0, len(T) - 2)
        if Hb is not None:
            TH[:, u] = np.arctan2(_DY[Hb[leg]], _DX[Hb[leg]])
        else:
            TH[:, u] = np.arctan2(Yb[leg + 1] - Yb[leg], Xb[leg + 1] - Xb[leg])
    return X, Y, v, TH
