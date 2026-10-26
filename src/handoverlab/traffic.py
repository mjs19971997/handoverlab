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
    ``ftp_file_bytes`` arriving as a Poisson process of ``ftp_rate_hz`` per user (FTP model 3: TR 36.872 Annex A.1,
    FTP model 2 with Poisson arrivals; 0.5 Mbyte files as TR 38.802 Table A.2.1-1 and TR 38.821 Table 6.1.1.1-7).
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


class CellBursts:
    """Background traffic of every cell as bursts of files, for the optional dynamic interference on link
    monitoring (``protocol.rlm_interference: dynamic``).

    Files of ``file_bits`` arrive at cell m as a Poisson process (FTP model 1 of TR 36.814 Table A.2.1.3.1-1;
    FTP model 3 of TR 36.872 Annex A.1.1 has Poisson arrivals too) and the cell sends them one after the other
    over the whole carrier at ``rate_bps``, each in ``d = file_bits / rate_bps`` seconds (an M/D/1 queue).  The
    arrival rate ``load_m / d`` makes the long-run share of busy time, the resource utilisation of TR 36.814
    A.2.1.3.2, equal to ``load_m``; a cell with ``load_m >= 1`` is always busy (full buffer).  :meth:`step`
    returns the busy share of every cell in the next step of ``step_s``: an on/off process whose time
    correlation comes from the queue alone (mean busy period ``d / (1 - load_m)``).  Files that arrive within a
    step join the queue at its start.  The queue starts empty.
    """

    def __init__(self, load, file_bits: float, rate_bps: float, step_s: float, rng):
        load = np.asarray(load, dtype=float)
        self.full = load >= 1.0
        self.d = float(file_bits) / float(rate_bps)
        self.p = np.where(self.full, 0.0, np.maximum(load, 0.0)) / self.d * step_s   # mean arrivals per step
        self.dt = float(step_s)
        self.work = np.zeros(len(load))                 # unfinished work of every cell [s]
        self.rng = rng
        self.block = np.zeros((0, len(load)))            # arrivals of the next steps, drawn BLOCK steps at a time
        self.i = 0

    BLOCK = 1000

    def step(self) -> np.ndarray:
        """Busy share (0 to 1) of every cell in the next step."""
        if self.i >= len(self.block):
            self.block = self.rng.poisson(self.p, size=(self.BLOCK, len(self.p))) * self.d
            self.i = 0
        self.work += self.block[self.i]
        self.i += 1
        busy = np.minimum(self.work, self.dt)
        self.work -= busy
        busy /= self.dt
        busy[self.full] = 1.0
        return busy


class ServiceTable:
    """Per-user columns of the service table (arrays of length U)."""

    def __init__(self, services, svc_index: np.ndarray, rate_scale: float = 1.0):
        self.index = svc_index
        self.keys = [s.key for s in services]
        self.t_min = np.array([s.t_min_s for s in services])[svc_index]
        self.theta_q = np.array([s.theta_q_db for s in services])[svc_index]
        self.gbr = np.array([s.gbr for s in services])[svc_index]
        self.rate = (np.array([s.rate_mbps for s in services]) * 1e6)[svc_index] * rate_scale
