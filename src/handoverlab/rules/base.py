# SPDX-License-Identifier: MIT
"""The handover-rule interface.

A rule decides; the engine simulates.  The engine calls the hooks of a rule at
every measurement instant and after outcomes; the rule never calls the
engine.  Hooks receive an :class:`Observation` with what a network can
observe: filtered measurements, the serving cell, the reported position,
speed and heading, and the nominal site plan from :class:`RuleContext`.  A
rule never sees the true SINR, the buildings or the cell load.

Two families exist:

``BaselineRule``
    Baseline handover: Event A3 held for the time-to-trigger, report,
    preparation, handover command.  Hooks :meth:`BaselineRule.a3_offsets` and
    :meth:`BaselineRule.time_to_trigger`.

``ConditionalRule``
    Conditional handover (3GPP Rel-16): the network prepares up to ``n_max``
    candidate cells; each conditional configuration carries an execution
    offset; the UE executes on its own when the condition holds for
    ``ttt_exec_s``.  Hooks :meth:`ConditionalRule.prep_offsets` and
    :meth:`ConditionalRule.exec_offsets`.

Rules that learn from outcomes set ``learns = True`` and implement
:meth:`Rule.on_outcome` and :meth:`Rule.on_link_failure`.  A rule that needs
randomness must use ``ctx.rng``, never NumPy's global state.

Stability: this interface has the version
:data:`handoverlab.stability.RULE_API_VERSION` (1).  Within a major release,
the hooks keep their names and arguments, and the fields of
:class:`RuleContext`, :class:`Observation`, :class:`OutcomeRecord` and
:class:`FailureRecord` are only added to, never removed or renamed; a rule
written for 1.0 runs unchanged on every 1.x release (see
``docs/stability.md``).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Union

import numpy as np

# labels fed back to a learning rule (observable counterparts of the outcomes)
USEFUL, UNNECESSARY, EARLY, LATE = 0, 1, 2, 3

MAX_CONDITIONAL_CELLS = 8        # maxNrofCondCells-r16 of TS 38.331


@dataclass
class RuleContext:
    """Given to :meth:`Rule.reset` once per run."""
    n_users: int
    n_sites: int
    sites: np.ndarray                       # (M, 2) nominal site positions [m]
    nominal_cell: Callable[..., np.ndarray]  # nominal best server at points (x, y)
    step_s: float
    measurement_period_s: float
    seed: int
    rng: np.random.Generator                # private random stream of the rule
    scenario: Any


@dataclass
class Observation:
    """What the network observes at one measurement instant (arrays over users U and cells M)."""
    t: float
    step: int
    meas_dbm: np.ndarray      # (U, M) L3-filtered RSRP
    gap_db: np.ndarray        # (U, M) neighbour minus serving, filtered
    serving: np.ndarray       # (U,) serving cell
    connected: np.ndarray     # (U,) bool
    x: np.ndarray             # (U,) reported position [m]
    y: np.ndarray
    speed: np.ndarray         # (U,) [m/s]
    heading: np.ndarray       # (U,) [rad]


@dataclass
class OutcomeRecord:
    """Observable outcome of one handover attempt."""
    user: int
    source: int
    target: int
    key: int                  # memory key returned by :meth:`Rule.memory_key` at the attempt, or -1
    label: int                # USEFUL, UNNECESSARY, EARLY or LATE
    t: float


@dataclass
class FailureRecord:
    """Radio-link failure without a handover in flight; the UE re-established in ``cell``."""
    user: int
    source: int
    cell: int
    t: float
    t310_start: float
    x: float                  # position when T310 started [m]
    y: float
    heading: float


class Rule:
    """Common part of all rules."""
    family = "baseline"
    learns = False            # True: receives on_outcome / on_link_failure
    immediate = False

    def __init__(self, name: Optional[str] = None):
        self.name = name or type(self).__name__

    def params(self) -> Dict[str, Any]:
        """Parameters of the rule (written into the results)."""
        return {}

    def reset(self, ctx: RuleContext) -> None:
        """Called once before a run."""
        self.ctx = ctx

    def memory_key(self, obs: Observation) -> Optional[np.ndarray]:
        """Key (U,) under which an attempt prepared now is remembered, or None."""
        return None

    def on_outcome(self, rec: OutcomeRecord) -> None:
        """Outcome of a handover attempt (only called if ``learns``)."""

    def on_link_failure(self, rec: FailureRecord) -> None:
        """Radio-link failure without a handover (only called if ``learns``)."""

    def describe(self) -> Dict[str, Any]:
        return dict(name=self.name, family=self.family, **self.params())


class BaselineRule(Rule):
    """Baseline handover triggered by Event A3."""
    family = "baseline"

    def a3_offsets(self, obs: Observation) -> Union[float, np.ndarray]:
        """A3 offset [dB]: a scalar or an array (U, M)."""
        raise NotImplementedError

    def time_to_trigger(self, obs: Observation) -> Union[float, np.ndarray]:
        """Time-to-trigger [s]: a scalar or an array (U,)."""
        raise NotImplementedError


class ConditionalRule(Rule):
    """Conditional handover (Rel-16).

    Attributes read by the engine (set them in ``__init__``):

    ``report_offset_db``  the UE reports a neighbour that is this much better
                          than the serving cell for ``ttt_prep_s``
    ``ttt_prep_s``        time-to-trigger of the reporting condition
    ``ttt_exec_s``        time-to-trigger of the execution condition
    ``n_max``             largest prepared set (at most 8)
    ``release_hys_db``    a prepared cell is released when it falls this far
                          below its preparation offset
    ``stick_db``          ranking bonus of an already prepared cell
    ``immediate``         execute as soon as the configuration arrives (the
                          conditional handover then acts as a baseline one)
    """
    family = "conditional"
    report_offset_db = 0.0
    ttt_prep_s = 0.0
    ttt_exec_s = 0.0
    n_max = 4
    release_hys_db = 3.0
    stick_db = 1.0

    def prep_offsets(self, obs: Observation) -> Union[float, np.ndarray]:
        """Preparation offset [dB]: a scalar or an array (U, M)."""
        raise NotImplementedError

    def exec_offsets(self, obs: Observation) -> Union[float, np.ndarray]:
        """Execution offset [dB] written into a new conditional configuration: scalar or (U, M)."""
        raise NotImplementedError
