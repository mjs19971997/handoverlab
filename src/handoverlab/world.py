# SPDX-License-Identifier: MIT
"""A simulated world: everything that a scenario and a seed fix.

The world (layout, radio map, trajectories, services, background load) is
built once per seed.  Every handover rule compared on that seed runs on the
same world and on the same radio samples, so differences between rules come
only from their decisions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from .channel.radiomap import RadioMap
from .config import Scenario
from .layout import Layout, make_layout
from .mobility import trajectories
from .seeds import streams
from .traffic import ServiceTable, assign_services, background_load, offered_bits


@dataclass
class World:
    scenario: Scenario
    seed: int
    layout: Layout
    radio_map: RadioMap
    x: np.ndarray            # (S, U) positions [m]
    y: np.ndarray
    speed: np.ndarray        # (U,) [m/s]
    heading: np.ndarray      # (S, U) [rad]
    services: ServiceTable
    bg_load: np.ndarray      # (M,) background load of every cell
    offered: Optional[np.ndarray] = None   # (n_meas, U) arriving bits per measurement interval (traffic.model)

    @property
    def n_steps(self) -> int:
        return self.x.shape[0]

    @property
    def n_users(self) -> int:
        return self.x.shape[1]


def build_world(scenario: Scenario, seed: int) -> World:
    """Layout, radio map, trajectories, services and background load of one seed."""
    layout = make_layout(scenario.layout)
    rng_traj, rng_svc, rng_bg = streams(seed, "world", 3)
    rmap = RadioMap(layout, scenario.radio, seed)
    x, y, v, th = trajectories(layout, scenario.mobility, scenario.run.duration_s, scenario.protocol.step_s,
                               rng_traj, scenario.layout.min_site_distance_m)
    tr = scenario.traffic
    svc = ServiceTable(tr.services, assign_services(tr.services, scenario.mobility.users, rng_svc), tr.rate_scale)
    bg = background_load(tr, layout.n_sites, rng_bg)
    offered = None
    if tr.model in ("periodic", "ftp3"):                       # own stream: the other draws stay as they were
        P = scenario.protocol
        mp = max(1, int(round(P.l1_period_s / P.step_s)))
        offered = offered_bits(tr, -(-x.shape[0] // mp), mp * P.step_s, x.shape[1], streams(seed, "traffic", 1)[0])
    return World(scenario, int(seed), layout, rmap, x, y, v, th, svc, bg, offered)
