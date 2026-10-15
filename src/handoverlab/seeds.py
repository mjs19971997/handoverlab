# SPDX-License-Identifier: MIT
"""Random streams derived from one seed.

Everything random in a run (radio map, trajectories, services, background
load, time variation, measurement error) is drawn from independent NumPy
generators that are derived from the run seed and a named *purpose*.  The
protocol engine and the built-in handover rules draw no random numbers, so
every rule compared on one seed sees exactly the same radio samples.

Purposes and the generators each one provides (in this order):

=========  ================================================================
``world``  trajectories, service classes, background load
``map``    place-tied shadowing field, spatially consistent LOS field
``radio``  time-varying component, own-path shadowing, L1 error, open-area LOS
``rule``   one generator for a rule that needs randomness of its own
=========  ================================================================
"""
from __future__ import annotations

from typing import List

import numpy as np

_PURPOSE = {"world": 3, "map": 11, "radio": 29, "rule": 71}
_STRIDE = 1000003


def streams(seed: int, purpose: str, n: int) -> List[np.random.Generator]:
    """``n`` independent generators for ``purpose`` derived from ``seed``."""
    try:
        base = int(seed) * _STRIDE + _PURPOSE[purpose]
    except KeyError:
        raise ValueError("unknown random-stream purpose %r; known: %s" % (purpose, ", ".join(_PURPOSE)))
    return [np.random.default_rng(s) for s in np.random.SeedSequence(base).spawn(n)]


def rule_stream(seed: int) -> np.random.Generator:
    """Private generator for a handover rule."""
    return np.random.default_rng(int(seed) * _STRIDE + _PURPOSE["rule"])
