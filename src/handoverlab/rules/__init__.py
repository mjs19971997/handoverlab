# SPDX-License-Identifier: MIT
"""Handover rules and their registry.

Built-in rules are registered under ``"a3"``, ``"cho"``, ``"daps"``, ``"ltm"``,
``"cltm"``, ``"a3_bandit"``, ``"a3_mro"`` (since 1.7.0), ``"a3a5"`` (since 1.10.0), ``"dqn"`` (since 1.11.0;
needs PyTorch: ``pip install handoverlab[torch]``) and ``"a3_pred"`` (since 2.4.0; RRM measurement prediction of
TR 38.744).  Your own rule can
be registered in code::

    from handoverlab.rules import BaselineRule, register_rule

    @register_rule("a3_speed")
    class SpeedA3(BaselineRule):
        ...

or, from an installed package, through the entry-point group
``handoverlab.rules`` in its ``pyproject.toml``::

    [project.entry-points."handoverlab.rules"]
    a3_speed = "my_rules:SpeedA3"
"""
from __future__ import annotations

import inspect
from typing import Any, Dict, List, Optional, Type

from .base import (EARLY, LATE, MAX_CONDITIONAL_CELLS, UNNECESSARY, USEFUL, BaselineRule, ConditionalRule, DAPSRule,
                   CLTMRule, FailureRecord, LTMRule, Observation, OutcomeRecord, Rule, RuleContext)
from .builtin import A3, A3A5, CHO, CHOD2, CLTM, DAPS, LTM, BanditA3
from .dqn import DQNA3
from .mro import MROA3
from .predict import PredA3

ENTRY_POINT_GROUP = "handoverlab.rules"
_REGISTRY: Dict[str, Type[Rule]] = {"a3": A3, "cho": CHO, "daps": DAPS, "ltm": LTM, "cltm": CLTM,
                                   "a3_bandit": BanditA3, "a3_mro": MROA3, "a3a5": A3A5, "dqn": DQNA3,
                                   "cho_d2": CHOD2, "a3_pred": PredA3}

#: base classes a rule must derive from (DAPSRule derives from BaselineRule)
RULE_BASES = (BaselineRule, ConditionalRule, LTMRule)


def register_rule(key: str):
    """Class decorator that makes a rule available under ``key``."""
    def deco(cls):
        if not (inspect.isclass(cls) and issubclass(cls, RULE_BASES)):
            raise TypeError("a rule must subclass BaselineRule, ConditionalRule, DAPSRule or LTMRule")
        _REGISTRY[key] = cls
        return cls
    return deco


def _entry_points():
    try:
        from importlib.metadata import entry_points
    except ImportError:                                       # pragma: no cover
        return []
    eps = entry_points()
    if hasattr(eps, "select"):
        return list(eps.select(group=ENTRY_POINT_GROUP))
    return list(eps.get(ENTRY_POINT_GROUP, []))               # Python 3.9


def get_rule_class(key: str) -> Type[Rule]:
    """Rule class registered under ``key`` (built-in, decorated or entry point)."""
    if key in _REGISTRY:
        return _REGISTRY[key]
    for ep in _entry_points():
        if ep.name == key:
            cls = ep.load()
            _REGISTRY[key] = cls
            return cls
    raise KeyError("unknown rule %r; available: %s" % (key, ", ".join(available_rules())))


def rule_key(rule) -> Optional[str]:
    """Registry key of a rule object or class, or None if it is not registered."""
    cls = rule if inspect.isclass(rule) else type(rule)
    for key, c in _REGISTRY.items():
        if c is cls:
            return key
    for ep in _entry_points():
        try:
            if ep.load() is cls:
                return ep.name
        except Exception:                                     # pragma: no cover - broken plug-in
            continue
    return None


def available_rules() -> List[str]:
    names = set(_REGISTRY)
    names.update(ep.name for ep in _entry_points())
    return sorted(names)


def make_rule(spec: Dict[str, Any]) -> Rule:
    """Rule from ``{"rule": <key>, <parameters>...}``."""
    d = dict(spec)
    if "rule" not in d:
        raise ValueError("a rule specification needs a 'rule' key")
    cls = get_rule_class(d.pop("rule"))
    try:
        return cls(**d)
    except TypeError as e:
        sig = inspect.signature(cls.__init__)
        allowed = [p for p in sig.parameters if p != "self"]
        raise ValueError("rule %r: %s (parameters: %s)" % (spec["rule"], e, ", ".join(allowed)))


__all__ = ["Rule", "BaselineRule", "ConditionalRule", "DAPSRule", "LTMRule", "CLTMRule", "RuleContext", "Observation",
           "OutcomeRecord", "FailureRecord", "USEFUL", "UNNECESSARY", "EARLY", "LATE", "MAX_CONDITIONAL_CELLS", "A3",
           "CHO", "CHOD2", "DAPS", "LTM", "CLTM", "BanditA3", "MROA3", "A3A5", "DQNA3", "PredA3", "RULE_BASES",
           "register_rule", "get_rule_class", "available_rules", "make_rule", "rule_key"]
