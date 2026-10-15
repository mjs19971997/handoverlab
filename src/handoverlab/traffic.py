# SPDX-License-Identifier: MIT
"""Service classes of the users and background load of the cells."""
from __future__ import annotations

import numpy as np


def assign_services(services, n_users: int, rng) -> np.ndarray:
    """Service index of every user, drawn according to the population shares."""
    share = np.array([s.share for s in services])
    return rng.choice(len(services), size=n_users, p=share / share.sum())


def background_load(traffic, n_sites: int, rng) -> np.ndarray:
    """Background load of every cell: a share of hotspot cells with a higher load."""
    hot = np.zeros(n_sites, dtype=bool)
    hot[rng.choice(n_sites, max(1, int(round(traffic.hotspot_share * n_sites))), replace=False)] = True
    return np.where(hot, rng.uniform(*traffic.hotspot_load, n_sites), rng.uniform(*traffic.normal_load, n_sites))


class ServiceTable:
    """Per-user columns of the service table (arrays of length U)."""

    def __init__(self, services, svc_index: np.ndarray, rate_scale: float = 1.0):
        self.index = svc_index
        self.keys = [s.key for s in services]
        self.t_min = np.array([s.t_min_s for s in services])[svc_index]
        self.theta_q = np.array([s.theta_q_db for s in services])[svc_index]
        self.gbr = np.array([s.gbr for s in services])[svc_index]
        self.rate = (np.array([s.rate_mbps for s in services]) * 1e6)[svc_index] * rate_scale
