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

Two further families (since 1.0.0rc2) reuse these hooks:

``DAPSRule``
    Dual active protocol stack handover (Rel-16): triggered like a baseline
    handover, but the source link keeps carrying data during the execution
    and the UE falls back to the source if the target cannot be joined.
    Hooks of :class:`BaselineRule`.

``LTMRule``
    L1/L2-triggered mobility (Rel-18): candidate cells are configured in
    advance from L3 reports; the network switches the UE to a candidate on
    L1 measurement reports with a MAC command.  Hooks
    :meth:`LTMRule.prep_offsets` and :meth:`LTMRule.switch_offsets`.

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
    cell_carrier: Optional[np.ndarray] = None  # (M,) carrier index of every cell, multi-carrier model (since 1.10.0)
    cell_center: Optional[Callable[[float], np.ndarray]] = None  # (M, 2) reference locations at time t (2.0.0)


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
    l1_dbm: Optional[np.ndarray] = None  # (U, M) unfiltered L1 RSRP of this instant (since 1.0.0rc2)


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
        """Time-to-trigger [s]: a scalar, an array (U,) or (since 1.10.0) an array (U, M)."""
        raise NotImplementedError

    def entering(self, obs: Observation, offsets) -> Optional[tuple]:
        """Own entering condition (since 1.10.0): ``(condition, score)``, both (U, M), or None for Event A3.

        ``condition`` says where the event's entering condition holds (the serving cell and users that are
        not connected are excluded by the engine); among the cells whose time-to-trigger expires, the one with
        the highest ``score`` becomes the target.  The default (None) is Event A3 with ``offsets``.
        """
        return None


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

    #: True if :meth:`exec_condition` returns a condition (then a UE never executes on delivery of a configuration)
    exec_condition_used = False

    def exec_condition(self, obs: Observation) -> Optional[np.ndarray]:
        """A further execution condition (U, M) that must hold together with the execution offset (since 2.0.0),
        e.g. condEventD1 / D2 / T1 of TS 38.331 5.5.4.15-16; None (the default): the offset alone."""
        return None


class DAPSRule(BaselineRule):
    """Dual active protocol stack (DAPS) handover (Rel-16, TS 38.300 clause 9.2.3.2).

    Triggered like a baseline handover (hooks :meth:`BaselineRule.a3_offsets`
    and :meth:`BaselineRule.time_to_trigger`).  Attributes read by the engine:

    ``interruption_s``  user-plane interruption of an execution while the
                        source link carries data (Rel-16 aims at 0 ms)
    ``fallback``        an execution that cannot join the target falls back to
                        the source if the source SINR is at least Qout (TS 38.331
                        clause 5.3.5.8.3) instead of a re-establishment
    ``source_data``     the source keeps serving data during the execution
    """
    family = "daps"
    interruption_s = 0.0
    fallback = True
    source_data = True


class LTMRule(Rule):
    """L1/L2-triggered mobility (Rel-18, TS 38.300 clause 9.2.3.5).

    Attributes read by the engine (set them in ``__init__``):

    ``report_offset_db``  L3 report of a neighbour this much better than serving
                          for ``ttt_prep_s`` (candidate configuration)
    ``ttt_prep_s``        time-to-trigger of the L3 reporting condition
    ``n_max``             largest set of candidate cells (at most 8)
    ``release_hys_db``    a candidate is released when it falls this far below its
                          preparation offset
    ``stick_db``          ranking bonus of an already configured candidate
    ``ttt_switch_s``      the L1 switch condition must hold this long
    ``cmd_delay_s``       delay of the cell switch command (MAC CE)
    ``exec_s``            execution time of the cell switch (RACH-less, early TA)
    ``recovery``          a failed UE that selects a candidate recovers into it in
                          ``cho_recovery_s`` (otherwise a full re-establishment)
    """
    family = "ltm"
    report_offset_db = 0.0
    ttt_prep_s = 0.0
    n_max = 4
    release_hys_db = 3.0
    stick_db = 1.0
    ttt_switch_s = 0.0
    cmd_delay_s = 0.01
    exec_s = 0.02
    recovery = True

    def prep_offsets(self, obs: Observation) -> Union[float, np.ndarray]:
        """Candidate preparation offset [dB] on L3 measurements: a scalar or an array (U, M)."""
        raise NotImplementedError

    def switch_offsets(self, obs: Observation) -> Union[float, np.ndarray]:
        """Cell switch offset [dB] on L1 measurements (``obs.l1_dbm``): a scalar or an array (U, M)."""
        raise NotImplementedError


class CLTMRule(LTMRule):
    """Conditional L1/L2-triggered mobility (Rel-19 work on LTM; available since version 1.6.0).

    As :class:`LTMRule` (candidates configured on L3 reports, cell switch on L1 measurements,
    RACH-less execution), but the UE evaluates the switch condition itself and executes as soon as
    it holds, without a cell switch command (as conditional handover does on L3 measurements).
    ``cmd_delay_s`` is not used.  The same hooks as :class:`LTMRule`.
    """
    family = "cltm"
