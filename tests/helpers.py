# SPDX-License-Identifier: MIT
"""Test helpers: a synthetic world with prescribed received powers."""
from types import SimpleNamespace

import numpy as np

from handoverlab.channel.source import Chunk
from handoverlab.config import Scenario
from handoverlab.engine import Engine
from handoverlab.layout import Layout
from handoverlab.traffic import ServiceTable
from handoverlab.world import World


def synthetic_world(n_steps, n_users=1, sites=((0.0, 0.0), (100.0, 0.0)), bg_load=0.0, overrides=None):
    """World with fixed positions and no radio map; radio samples are supplied by the test."""
    sc = Scenario.from_dict({"run": {"duration_s": n_steps * 0.01, "warmup_s": 0.0},
                             "mobility": {"users": n_users}})
    if overrides:
        sc = sc.with_overrides(overrides)
    sites = np.asarray(sites, dtype=float)
    layout = Layout("open_area", sites, np.zeros((0, 4)), np.array([]), np.array([]), 0.0,
                    -500.0, 500.0, -500.0, 500.0)
    rmap = SimpleNamespace(nominal_cell=lambda x, y: np.zeros(np.shape(x), dtype=int))
    x = np.zeros((n_steps, n_users))
    svc = ServiceTable(sc.traffic.services, np.full(n_users, 4), 1.0)     # "web": T_min 2 s
    return World(sc, 1, layout, rmap, x, x.copy(), np.full(n_users, 10.0), np.zeros((n_steps, n_users)),
                 svc, np.full(len(sites), bg_load))


def run_synthetic(rule, rsrp, log=True, **kw):
    """Run ``rule`` on received powers ``rsrp`` (S, U, M) [dBm] without measurement noise."""
    rsrp = np.asarray(rsrp, dtype=float)
    world = synthetic_world(rsrp.shape[0], rsrp.shape[1], **kw)
    eng = Engine(world, rule, log_events=log)
    mp = eng.mp
    for k0 in range(0, rsrp.shape[0], 1000):
        eng.advance(Chunk.from_rsrp(k0, rsrp[k0:k0 + 1000], mp))
    return eng.finish(), eng.events
