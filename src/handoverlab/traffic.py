# SPDX-License-Identifier: MIT
"""Service classes of the users and background load of the cells."""
from __future__ import annotations

import numpy as np


def assign_services(services, n_users: int, rng) -> np.ndarray:
    """Service index of every user, drawn according to the population shares."""
    share = np.array([s.share for s in services])
    return rng.choice(len(services), size=n_users, p=share / share.sum())


MODELS = ("fixed", "full_buffer", "periodic", "ftp3")


def offered_bits(traffic, n_meas: int, mdt: float, n_users: int, rng):
    """Bits that reach each user's buffer in every measurement interval, shape (n_meas, U).

    ``None`` for the models without arrivals ("fixed", "full_buffer").  "periodic": one packet of
    ``packet_bytes`` every ``period_s`` with a random phase per user; "ftp3": files of
    ``ftp_file_bytes`` arriving as a Poisson process of ``ftp_rate_hz`` per user (TR 36.814 A.2.1.3).
    """
    if traffic.model == "periodic":
        phase = rng.uniform(0.0, traffic.period_s, n_users)
        t0 = np.arange(n_meas)[:, None] * mdt
        n = np.floor((t0 + mdt - phase) / traffic.period_s) - np.floor((t0 - phase) / traffic.period_s)
        return n * (8.0 * traffic.packet_bytes)
    if traffic.model == "ftp3":
        return rng.poisson(traffic.ftp_rate_hz * mdt, (n_meas, n_users)) * (8.0 * traffic.ftp_file_bytes)
    return None


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
