# SPDX-License-Identifier: MIT
"""Random streams derived from one seed.

Everything random in a run (radio map, trajectories, services, background
load, time variation, measurement error) is drawn from independent NumPy
generators that are derived from the run seed and a named *purpose*.  The
protocol engine and the built-in handover rules draw no random numbers, so
every rule compared on one seed sees exactly the same radio samples.

Purposes and the generators each one provides (in this order):

============  ================================================================
``world``     trajectories, service classes, background load
``map``       place-tied shadowing field, spatially consistent LOS field
``radio``     time-varying component, own-path shadowing, L1 error, open-area LOS
``rule``      one generator for a rule that needs randomness of its own
``beams``     L1 error of the SSB beams of the optional beam model (since 1.10.0)
``fading``    arrival angles and phases of the optional fast fading (since 2.2.0)
``harq``      decoding draws of the optional slot scheduler (since 2.2.0)
``o2i``       O2I building penetration loss of the indoor users (since 2.3.0)
``ue_beams``  bearing of the UE panels of the optional UE receive beams (since 2.4.0)
============  ================================================================

A further layer of the optional multi-carrier model (since 1.10.0) draws its
``map`` and ``radio`` streams with ``sub`` = its layer number, so that its
fields are independent of those of the first layer; ``sub = 0`` gives the
streams of 1.x unchanged.
"""
from __future__ import annotations

from typing import List

import numpy as np

_PURPOSE = {"world": 3, "map": 11, "radio": 29, "rule": 71, "penetration": 97, "traffic": 101, "beams": 113,
            "ntn": 127, "fading": 131, "harq": 137, "o2i": 139,
            "ue_beams": 149}
_STRIDE = 1000003


def streams(seed: int, purpose: str, n: int, sub: int = 0) -> List[np.random.Generator]:
    """``n`` independent generators for ``purpose`` derived from ``seed`` (and ``sub``, if not 0)."""
    try:
        base = int(seed) * _STRIDE + _PURPOSE[purpose]
    except KeyError:
        raise ValueError("unknown random-stream purpose %r; known: %s" % (purpose, ", ".join(_PURPOSE)))
    ss = np.random.SeedSequence(base) if not sub else np.random.SeedSequence([base, int(sub)])
    return [np.random.default_rng(s) for s in ss.spawn(n)]


def rule_stream(seed: int) -> np.random.Generator:
    """Private generator for a handover rule."""
    return np.random.default_rng(int(seed) * _STRIDE + _PURPOSE["rule"])
