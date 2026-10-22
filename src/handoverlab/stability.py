# SPDX-License-Identifier: MIT
"""Versions of the public surface, deprecations and the surface snapshot.

From 1.0 on, HandoverLab follows Semantic Versioning for its *public surface*
(see ``docs/stability.md``):

* configuration files (experiments and studies) and result files carry the
  schema version :data:`SCHEMA_VERSION` under the top-level key ``schema``;
  a file without the key is read as schema 1, a file with a newer schema is
  refused with a message that names it;
* the rule interface (:mod:`handoverlab.rules.base`) has the version
  :data:`RULE_API_VERSION`;
* metric names (:data:`handoverlab.engine.METRICS`) are stable; a renamed
  metric keeps its old name as an alias in :data:`METRIC_ALIASES` for at
  least one minor release, and the old name warns.

Anything to be removed is first deprecated with :func:`deprecated`, which
issues a :class:`HandoverLabDeprecationWarning` naming the version that
deprecated it, the version that removes it and the replacement.

:func:`public_surface` lists the names, hooks, fields, metrics and
configuration keys that make up the surface; a test compares it with the
snapshot in ``tests/data/public_api.json``.  After an intended change, write
a new snapshot with ``python -m handoverlab.stability --write
tests/data/public_api.json`` and record the change in ``CHANGELOG.md``.
"""
from __future__ import annotations

import functools
import inspect
import json
import sys
import warnings
from typing import Any, Callable, Dict, List, Optional

#: version of the configuration and result file formats (top-level key ``schema``)
SCHEMA_VERSION = 1

#: version of the handover-rule interface (hooks, observation and record fields)
RULE_API_VERSION = 1

#: old metric name -> current name (old names keep working, with a warning)
METRIC_ALIASES: Dict[str, str] = {}

#: scenario overrides that give the results of HandoverLab 1.x (since 2.0.0).  Apply them with
#: ``scenario.with_overrides(LEGACY_1X)``; a scenario on the urban grid also needs ``mobility.profile: veh16``
#: (the 1.x cards smoke, urban-grid-10ghz, fr3-urban-15ghz, urban-grid-28ghz-beams and open-area-10ghz).
#: ``radio.channel_detail: simple`` (since 2.1.0) restores the large-scale channel of 2.0.0 and 1.x.  The built-in
#: cards whose values 2.1.0 changed also need the old card values of :data:`LEGACY_CARDS`:
#:
#: * smoke, urban-grid-10ghz, fr3-urban-15ghz, urban-grid-28ghz-beams: ``radio.ue_height_m: 1.5`` (2.1.0: the
#:   1.6 m antenna of vehicle type 2, TR 37.885 clause 6.1.2);
#: * indoor-office-4ghz: ``mobility.profile: ped3`` and ``radio.pathloss: inh_office`` (2.1.0: ``p3``, the fixed
#:   3 km/h of ITU-R M.2412-0 Table 5a, and the open-office LOS probability of its Table A1-9);
#: * rural-700mhz: ``mobility.profile: veh120`` (2.1.0: ``v120``, the fixed 120 km/h of M.2412-0 Table 5c);
#: * dense-urban-2layer: ``mobility.groups: [{share: 1.0, v_min: 8.33, v_max: 8.33, lateral_m: [0, 0]}]``
#:   (2.1.0: ``v30``, 30/3.6 m/s, M.2412-0 Table 5b);
#: * highway-tr37885-4ghz, highway-tr37885-30ghz: ``mobility.profile: v140`` (2.1.0: ``v140c``, on the lane
#:   centre, TR 37.885 clause 6.1.2 gives no lateral spread);
#: * ntn-leo600-2ghz (a 2.0.0 card): ``ntn.los_model: probability`` (2.1.0: ``los``, TR 38.821 Table 6.1.1.1-5).
#:
#: ``handoverlab verify --only fingerprints`` checks that these settings reproduce every 1.x golden run.
LEGACY_1X: Dict[str, object] = {
    "radio.breakpoint_c_mps": 299792458.0,    # 1.x: the exact speed of light in the breakpoint distances
    "radio.pl_min_distance_m": 0.0,           # 1.x: path loss at any distance
    "protocol.cmd_during_t310": "lost",       # 1.x: a handover command is lost while T310 runs
    "protocol.t304_s": None,                  # 1.x: no T304
    "protocol.rlm_holdoff_s": 0.0,            # 1.x: link monitoring not restarted on a new cell
    "protocol.rrc_detail": "simple",          # 2.0.0 and before: the engine before the audit of 2.1.0
    "radio.channel_detail": "simple",         # 1.x and 2.0: the large-scale channel before 2.1.0
    "radio.energy_ntrx": 1,                   # 1.x and 2.0: the EARTH model without N_TRX
}

#: built-in card -> the card values of 2.0.0 (and 1.x) that 2.1.0 changed (see :data:`LEGACY_1X`); apply them
#: after :data:`LEGACY_1X` to a scenario built from that card
LEGACY_CARDS: Dict[str, Dict[str, object]] = {
    "smoke": {"radio.ue_height_m": 1.5},
    "urban-grid-10ghz": {"radio.ue_height_m": 1.5},
    "fr3-urban-15ghz": {"radio.ue_height_m": 1.5},
    "urban-grid-28ghz-beams": {"radio.ue_height_m": 1.5},
    "indoor-office-4ghz": {"mobility.profile": "ped3", "radio.pathloss": "inh_office"},
    "rural-700mhz": {"mobility.profile": "veh120"},
    "dense-urban-2layer": {"mobility.profile": "v60", "mobility.groups": [
        {"share": 1.0, "v_min": 8.33, "v_max": 8.33, "lateral_m": [0.0, 0.0]}]},
    "highway-tr37885-4ghz": {"mobility.profile": "v140"},
    "highway-tr37885-30ghz": {"mobility.profile": "v140"},
    "ntn-leo600-2ghz": {"ntn.los_model": "probability"},
}


class HandoverLabDeprecationWarning(FutureWarning):
    """A deprecated part of the public surface was used.

    It derives from :class:`FutureWarning`, so that it is shown by default
    to users of scripts and the command line, not only to test runners.
    """


def deprecated(what: str, *, since: str, removed_in: str, instead: Optional[str] = None,
               stacklevel: int = 2) -> None:
    """Warn that ``what`` is deprecated since version ``since`` and goes in ``removed_in``."""
    msg = "%s is deprecated since HandoverLab %s and will be removed in %s" % (what, since, removed_in)
    if instead:
        msg += "; use %s instead" % instead
    warnings.warn(msg, HandoverLabDeprecationWarning, stacklevel=stacklevel + 1)


def deprecated_alias(func: Callable, old_name: str, *, since: str, removed_in: str) -> Callable:
    """A function under the old name ``old_name`` that warns and calls ``func``."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        deprecated(old_name, since=since, removed_in=removed_in, instead=func.__name__, stacklevel=2)
        return func(*args, **kwargs)
    wrapper.__name__ = old_name
    return wrapper


def metric_name(name: str) -> str:
    """Current name of the metric ``name``; an old name warns, an unknown one raises ``KeyError``."""
    from .engine.metrics import METRICS
    if name in METRICS:
        return name
    if name in METRIC_ALIASES:
        new = METRIC_ALIASES[name]
        deprecated("metric name %r" % name, since="1.0", removed_in="2.0", instead=repr(new), stacklevel=2)
        return new
    raise KeyError(name)


def check_schema(value: Any, what: str) -> int:
    """Schema version of a file from its ``schema`` value (``None``: schema 1).

    Raises :class:`~handoverlab.config.ConfigError` for a value that is not a
    positive integer or that is newer than :data:`SCHEMA_VERSION`.
    """
    from .config import ConfigError
    if value is None:
        return 1
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ConfigError("%s: schema must be a positive integer, got %r" % (what, value))
    if value > SCHEMA_VERSION:
        raise ConfigError("%s: written for schema %d; this version of HandoverLab reads schema %d or older "
                          "(upgrade HandoverLab)" % (what, value, SCHEMA_VERSION))
    return value


# ---------------------------------------------------------------------------
# snapshot of the public surface
# ---------------------------------------------------------------------------
def _params(func) -> List[str]:
    return [p.name for p in inspect.signature(func).parameters.values()]


def _keys(d: Dict[str, Any], prefix: str = "") -> List[str]:
    out = []
    for k, v in d.items():
        if isinstance(v, dict) and v:
            out.extend(_keys(v, prefix + k + "."))
        else:
            out.append(prefix + k)
    return out


def count_names() -> List[str]:
    """Names of the event counts a run returns next to the metrics (``n_...``)."""
    from .engine.metrics import _COUNTS, CAUSES, OUTCOMES
    return list(_COUNTS.values()) + ["n_" + o for o in OUTCOMES] + ["n_fail_" + c for c in CAUSES]


def public_surface() -> Dict[str, Any]:
    """Names, rule hooks, record fields, metrics and configuration keys of the public surface."""
    import dataclasses

    import handoverlab
    from . import eventlog, rules, studies
    from .config import Scenario
    from .engine import EVENT_FIELDS
    from .engine.metrics import CAUSES, METRICS, OUTCOMES
    from .rules import base
    from .simulate import RunResult
    from .studies.config import _COMPARE, _METHOD, _TOP, _TUNING

    hooks = {}
    for cls in (base.Rule, base.BaselineRule, base.ConditionalRule, base.DAPSRule, base.LTMRule):
        hooks[cls.__name__] = {n: _params(f) for n, f in sorted(vars(cls).items())
                               if inspect.isfunction(f) and not n.startswith("_")}
    attrs = {cls.__name__: sorted(n for n, v in vars(cls).items() if not n.startswith("_") and not callable(v))
             for cls in (base.Rule, base.ConditionalRule, base.DAPSRule, base.LTMRule)}
    records = {cls.__name__: [f.name for f in dataclasses.fields(cls)]
               for cls in (base.RuleContext, base.Observation, base.OutcomeRecord, base.FailureRecord, RunResult)}
    return dict(
        schema=SCHEMA_VERSION,
        rule_api=RULE_API_VERSION,
        exports={"handoverlab": sorted(handoverlab.__all__), "handoverlab.rules": sorted(rules.__all__),
                 "handoverlab.studies": sorted(studies.__all__), "handoverlab.stability": sorted(__all__)},
        rule_hooks=hooks,
        rule_attributes=attrs,
        records=records,
        outcome_labels=dict(USEFUL=base.USEFUL, UNNECESSARY=base.UNNECESSARY, EARLY=base.EARLY, LATE=base.LATE),
        metrics=sorted(METRICS),
        counts=count_names(),
        outcomes=list(OUTCOMES),
        causes=list(CAUSES),
        event_fields=list(EVENT_FIELDS),
        trace_fields=list(eventlog.TRACE_FIELDS),
        trace_events=list(eventlog.TRACE_EVENTS),
        scenario_keys=sorted(_keys(Scenario().to_dict(full=True))),
        experiment_keys=["schema", "scenario", "seeds", "rules", "output"],
        study_keys=dict(top=sorted(_TOP), tuning=sorted(_TUNING), method=sorted(_METHOD), compare=sorted(_COMPARE)),
    )


__all__ = ["SCHEMA_VERSION", "RULE_API_VERSION", "METRIC_ALIASES", "LEGACY_1X", "LEGACY_CARDS",
           "HandoverLabDeprecationWarning",
           "deprecated",
           "deprecated_alias", "metric_name", "check_schema", "count_names", "public_surface"]


def main(argv: Optional[List[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    text = json.dumps(public_surface(), indent=1) + "\n"
    if argv[:1] == ["--write"] and len(argv) == 2:
        with open(argv[1], "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print("wrote", argv[1])
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":                                   # pragma: no cover
    sys.exit(main())

