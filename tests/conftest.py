# SPDX-License-Identifier: MIT
"""Shared fixtures."""
import numpy as np
import pytest


@pytest.fixture
def ramp():
    """Cell 0 constant at -70 dBm; cell 1 rises linearly from -90 to -50 dBm over 20 s (1 user)."""
    S = 2000
    t = np.arange(S) * 0.01
    r = np.empty((S, 1, 2))
    r[:, 0, 0] = -70.0
    r[:, 0, 1] = -90.0 + 2.0 * t
    return r
