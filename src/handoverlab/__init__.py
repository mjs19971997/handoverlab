# SPDX-License-Identifier: MIT
"""HandoverLab: system-level simulation of handover and mobility procedures.

Quick start::

    import handoverlab as hl

    sc = hl.Scenario()                                  # 3 x 3-block street grid, 10 GHz
    res = hl.simulate(sc, [{"rule": "a3"}, {"rule": "cho"}], seeds=[1])
    for r in res:
        print(r.rule, r.metrics["handovers_pm"], r.metrics["failures_pm"])
"""
__version__ = "1.0.0rc2"

from .config import (ConfigError, Experiment, LayoutConfig, MobilityConfig, ProtocolConfig, RadioConfig, RunConfig,
                     Scenario, Service, SpeedGroup, TrafficConfig, load_config)
from .engine import InvariantError
from .eventlog import fingerprint, read_events, write_events
from .rules import (A3, CHO, DAPS, LTM, BaselineRule, ConditionalRule, DAPSRule, LTMRule, Rule, available_rules,
                    make_rule, register_rule)
from .scenarios import builtin_scenario, scenario_card, scenario_names
from .simulate import RunResult, run_experiment, run_world, simulate
from .world import World, build_world

__all__ = ["__version__", "ConfigError", "Experiment", "LayoutConfig", "MobilityConfig", "ProtocolConfig",
           "RadioConfig", "RunConfig", "Scenario", "Service", "SpeedGroup", "TrafficConfig", "load_config",
           "A3", "CHO", "DAPS", "LTM", "BaselineRule", "ConditionalRule", "DAPSRule", "LTMRule", "Rule",
           "available_rules", "make_rule", "register_rule",
           "RunResult", "run_experiment", "run_world", "simulate", "World", "build_world", "InvariantError",
           "fingerprint", "read_events", "write_events", "builtin_scenario", "scenario_card", "scenario_names"]
