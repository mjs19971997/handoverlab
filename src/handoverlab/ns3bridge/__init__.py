# SPDX-License-Identifier: MIT
"""A bridge to ns-3 / 5G-LENA: one study, run in both simulators and compared with the same checks.

Quick start::

    from handoverlab import ns3bridge

    study = ns3bridge.load_ns3_study("examples/ns3_study_v1.yaml")
    ns3bridge.export(study, "v1pkg")                           # ns-3 program, build.sh, run.py, run.ps1, manifest
    # ... build and run the package with ns-3, bring back v1pkg/V1_results.zip ...
    ref = ns3bridge.import_results("v1pkg/V1_results.zip", "v1_ref.json")
    res = ns3bridge.compare(study, ref, comparison=True, workers=4)   # same run length as ns-3 (180 s, 60 s)
    # setting="ns3-like": the ns-3-like setting (imitates ns-3 / 5G-LENA, not 3GPP; not validated)
    print(res["checks"])

or ``handoverlab ns3 export|import|compare`` on the command line.  Only what the program
``benchmarks/ns3/handoverlab-ns3-a3.cc`` can simulate is accepted (the card ``ns3-urban-3.5ghz``, Event A3,
site distance 200 / 300 / 400 m, speeds, users, run length, traffic, fading, seeds); everything else is
refused, naming the option, before any file is written.  See :mod:`.study` for the study file, :mod:`.export`,
:mod:`.results` and :mod:`.compare` for the three steps.
"""
from .compare import IDEAL_EXECUTION, LIMITS, SETTINGS, checks, compare, handoverlab_scenario
from .export import command_args, export, manifest, program_source, runs
from .results import import_results, read_runs, reference_from_runs
from .study import CARD, Cell, Ns3BridgeError, Ns3Study, load_ns3_study, study_from_dict

__all__ = ["CARD", "Cell", "IDEAL_EXECUTION", "LIMITS", "Ns3BridgeError", "Ns3Study", "SETTINGS", "checks",
           "command_args", "compare", "export", "handoverlab_scenario", "import_results", "load_ns3_study",
           "manifest", "program_source", "read_runs", "reference_from_runs", "runs", "study_from_dict"]
