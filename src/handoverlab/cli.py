# SPDX-License-Identifier: MIT
"""Command line: ``handoverlab run config.yaml``.

Commands
    run CONFIG [-o OUT] [--seeds S ...] [--events FILE] [--event-level LEVEL] [--debug]
        Run the experiment in CONFIG (YAML, TOML or JSON) and write one row per
        seed and rule to OUT (.csv or .json; default: the ``output`` key of
        the configuration, else ``results/<config name>.csv``).  ``--events``
        writes the event logs as a table (.parquet with pyarrow, else .csv);
        with ``--event-level full`` also the procedure trace (FILE-trace).
    verify [--only GROUP ...] [--full] [--ns3 [--ns3-reference FILE] [--ns3-comparison]]
           [--results FILE --sample N] [--json OUT]
        Run the verification checks and print a pass/fail report.
    scenarios [NAME] [--markdown] [--svg FILE] [--docs DIR]
        List the built-in scenarios, or show the card of one.
    study STUDY [-o DIR] [--workers N] [--tuning-only] [--dry-run] [--status] [--report]
        Run or resume a study: tuning with gates, test stage, result tables.
    report DIR [-o OUT] [--format md html] [--no-figures]
        Write the Markdown/HTML report of a study directory.
    status STUDY|DIR [-o DIR] [--workers N]
        Finished, failed and remaining jobs per stage and the time still needed.
    gui [--port N] [--address A] [--headless]
        Start the browser dashboard (needs ``pip install handoverlab[gui]``).
    rules
        List the available handover rules.
    init [PATH]
        Write a commented example configuration.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional

from . import __version__
from .config import ConfigError, load_config

EXAMPLE_CONFIG = """\
# HandoverLab experiment: A3 versus conditional handover in the TR 37.885 street grid.
schema: 1                    # file format version (see docs/stability.md)
scenario:
  name: street-grid-10GHz
  layout:
    kind: street_grid        # or open_area
    blocks: [3, 3]           # TR 37.885 minimum area
    site_spacing_m: 100.0
  radio:
    carrier_ghz: 10.0
    pathloss: umi_street_canyon
  mobility:
    users: 20
    profile: veh16           # ped, veh8, veh16, veh30, mix, c8, c16, c30
  run:
    duration_s: 60.0
    warmup_s: 10.0
seeds: [1]
rules:
  - {rule: a3, name: A3, off_db: 3.0, ttt_s: 0.16}
  - {rule: cho, name: CHO, o_prep_db: -2.0, o_exec_db: 3.0, ttt_exec_s: 0.08, n_max: 4}
output: results/metrics.csv
"""

SUMMARY = ("handovers_pm", "unnecessary_pm", "pingpong_pm", "failures_pm", "prepared_cells_mean")


def _cmd_run(args) -> int:
    from .io import write_results
    from .simulate import run_experiment
    try:
        exp = load_config(args.config)
    except (ConfigError, OSError, ValueError) as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    if args.seeds:
        exp.seeds = tuple(args.seeds)
    out = args.output or exp.output or os.path.join(
        "results", os.path.splitext(os.path.basename(args.config))[0] + ".csv")
    log = (lambda msg: print(msg, file=sys.stderr)) if not args.quiet else None
    try:
        level = args.event_level if args.events else "off"
        results = run_experiment(exp, log_events=level, progress=log, debug=args.debug or None)
    except (KeyError, ValueError) as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    write_results(results, out, exp.scenario.to_dict())
    ev_path = tr_path = None
    if args.events:
        import warnings
        from .eventlog import trace_path, write_events, write_trace
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            ev_path = write_events(results, args.events)
            if level == "full":
                tr_path = write_trace(results, trace_path(args.events))
        for w in caught:
            print("note: %s" % w.message, file=sys.stderr)
    if not args.quiet:
        print("%-12s %5s " % ("rule", "seed") + " ".join("%12s" % k[:12] for k in SUMMARY))
        for r in results:
            print("%-12s %5d " % (r.rule[:12], r.seed) + " ".join("%12.4f" % r.metrics[k] for k in SUMMARY))
        print("wrote %s" % out)
        for p in (ev_path, tr_path):
            if p:
                print("wrote %s" % p)
    return 0


def _cmd_verify(args) -> int:
    from .verify import GROUPS, run_verify
    groups = args.only
    if groups is None:
        groups = [] if (args.ns3 or args.results) else list(GROUPS)
    printer = None if args.quiet else (lambda msg: print(msg, flush=True))
    try:
        rep = run_verify(groups, full=args.full, ns3=args.ns3, ns3_seeds=args.ns3_seeds, results=args.results,
                         sample=args.sample, printer=printer, ns3_reference=args.ns3_reference,
                         ns3_comparison=args.ns3_comparison)
    except (ValueError, OSError) as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    if args.json:
        rep.write_json(args.json)
    if args.quiet:
        print("%s: %s" % ("OK" if rep.ok else "FAILED", rep.summary()))
    return 0 if rep.ok else 1


def _cmd_study(args) -> int:
    from .studies import GateError, StudyError, dry_run, load_study, run_study, study_status, write_report
    try:
        study = load_study(args.study)
    except (ConfigError, OSError, ValueError, KeyError) as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    if args.dry_run:
        print("\n".join(dry_run(study)))
        return 0
    if args.status:
        print("\n".join(study_status(study, args.output, args.workers)))
        return 0
    if args.workers is not None and args.workers < 1:
        print("error: --workers must be at least 1", file=sys.stderr)
        return 2
    say = None if args.quiet else (lambda msg: print(msg, flush=True))
    try:
        res = run_study(study, args.output, args.workers, progress=say,
                        stop_after="tuning" if args.tuning_only else None)
    except GateError as e:
        print("error: %s" % e, file=sys.stderr)
        print("The gate report is in %s; change the grids or the gate policy and run the study again."
              % os.path.join(_study_root(study, args.output), "tuned", "gates.json"), file=sys.stderr)
        return 3
    except StudyError as e:
        print("error: %s" % e, file=sys.stderr)
        return 4
    if args.report and res.completed:
        for p in write_report(res.root):
            if not args.quiet and not p.endswith(".png"):
                print("wrote %s" % p)
    if not args.quiet:
        print("study %s: %s" % (study.name, "complete" if res.completed else "stopped after tuning"))
    return 0


def _cmd_status(args) -> int:
    from .studies import study_status
    try:
        lines = study_status(args.target, args.output, args.workers)
    except (ConfigError, OSError, ValueError, KeyError) as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    print("\n".join(lines))
    return 0


def _cmd_gui(args) -> int:
    from .gui import launch
    return launch(port=args.port, headless=args.headless, address=args.address)


def _study_root(study, out):
    from .studies.study import output_dir
    return os.path.abspath(output_dir(study, out))


def _cmd_report(args) -> int:
    from .studies import ReportError, write_report
    try:
        files = write_report(args.dir, args.output, args.format, figures=not args.no_figures)
    except (ReportError, OSError, ValueError) as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    for p in files:
        if not p.endswith(".png"):
            print("wrote %s" % p)
    return 0


def _cmd_scenarios(args) -> int:
    from .config import ConfigError
    from .scenarios import builtin_scenario, card_markdown, layout_svg, scenario_card, scenario_names
    try:
        if args.docs:
            os.makedirs(args.docs, exist_ok=True)
            for name in scenario_names():
                _write_text(os.path.join(args.docs, name + ".svg"), layout_svg(builtin_scenario(name)))
                _write_text(os.path.join(args.docs, name + ".md"), card_markdown(name, name + ".svg"))
            print("wrote %d scenario cards to %s" % (len(scenario_names()), args.docs))
            return 0
        if not args.name:
            for name in scenario_names():
                print("%-18s %s" % (name, scenario_card(name)["title"]))
            return 0
        if args.svg:
            _write_text(args.svg, layout_svg(builtin_scenario(args.name)))
            print("wrote %s" % args.svg)
            return 0
        if args.markdown:
            print(card_markdown(args.name))
            return 0
        import yaml
        card = scenario_card(args.name)
        print(yaml.safe_dump(card, sort_keys=False, width=100).rstrip())
        return 0
    except ConfigError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2


def _write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _cmd_rules(args) -> int:
    from .rules import available_rules, get_rule_class
    for key in available_rules():
        cls = get_rule_class(key)
        doc = (cls.__doc__ or "").strip().splitlines()
        extra = ""
        installed = getattr(cls, "installed", None)
        if installed is not None and not installed():          # an optional dependency is missing
            extra = "  [needs %s]" % getattr(cls, "requires", "an optional package")
        print("%-10s %-12s %s%s" % (key, cls.family, doc[0] if doc else "", extra))
    return 0


def _cmd_init(args) -> int:
    path = args.path
    if os.path.exists(path) and not args.force:
        print("error: %s exists (use --force to overwrite)" % path, file=sys.stderr)
        return 1
    with open(path, "w", encoding="utf-8") as f:
        f.write(EXAMPLE_CONFIG)
    print("wrote %s" % path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="handoverlab", description="System-level handover simulator.")
    p.add_argument("--version", action="version", version="handoverlab " + __version__)
    sub = p.add_subparsers(dest="command")
    r = sub.add_parser("run", help="run an experiment configuration")
    r.add_argument("config", help="configuration file (.yaml, .yml, .toml or .json)")
    r.add_argument("-o", "--output", help="result file (.csv or .json)")
    r.add_argument("--seeds", type=int, nargs="+", help="override the seeds of the configuration")
    r.add_argument("--events", metavar="FILE",
                   help="also write the event logs to FILE (.parquet if pyarrow is installed, else .csv)")
    r.add_argument("--event-level", choices=("summary", "full"), default="summary",
                   help="with --events: 'summary' (one row per attempt and failure, default) or 'full' "
                        "(also the procedure trace, written next to FILE as FILE-trace)")
    r.add_argument("--debug", action="store_true", help="check the engine invariants while running (slower)")
    r.add_argument("-q", "--quiet", action="store_true", help="print nothing but errors")
    r.set_defaults(func=_cmd_run)
    from .verify import GROUPS, OPTIONAL_GROUPS
    v = sub.add_parser("verify", help="run the verification checks and print a pass/fail report")
    v.add_argument("--only", nargs="+", metavar="GROUP",
                   help="check groups: %s (default: all of them); on request only: %s"
                   % (" ".join(GROUPS), " ".join(OPTIONAL_GROUPS)))
    v.add_argument("--full", action="store_true", help="longer checks (three seeds for the radio statistics)")
    v.add_argument("--ns3", action="store_true",
                   help="compare with the stored ns-3 / 5G-LENA results (several minutes); "
                        "only this check unless --only names groups")
    v.add_argument("--ns3-seeds", type=int, default=1, help="seeds per condition for --ns3 (default 1)")
    v.add_argument("--ns3-reference", metavar="FILE",
                   help="with --ns3: compare with this reference file instead of the stored one "
                        "(written by benchmarks/ns3/run_benchmark.py)")
    v.add_argument("--ns3-comparison", action="store_true",
                   help="with --ns3: run HandoverLab with the ns-3 comparison setting of 2.5.0 (interferer load "
                        "0.15 at link monitoring, ideal execution, the in-car loss of ns-3; passed on "
                        "one fresh ns-3 set with TTT 80/320 ms, failed the level on one with TTT 640 ms; "
                        "not a default)")
    v.add_argument("--results", metavar="FILE", help="recompute a JSON result file of 'run' and compare fingerprints")
    v.add_argument("--sample", type=int, help="with --results: recompute only this many runs, chosen at random")
    v.add_argument("--json", metavar="OUT", help="also write the report as JSON")
    v.add_argument("-q", "--quiet", action="store_true", help="print only the summary line")
    v.set_defaults(func=_cmd_verify)
    s = sub.add_parser("scenarios", help="list the built-in scenarios or show a scenario card")
    s.add_argument("name", nargs="?", help="scenario to show")
    s.add_argument("--markdown", action="store_true", help="print the card as Markdown")
    s.add_argument("--svg", metavar="FILE", help="write a drawing of the layout")
    s.add_argument("--docs", metavar="DIR", help="write Markdown cards and layout drawings of all scenarios")
    s.set_defaults(func=_cmd_scenarios)
    st = sub.add_parser("study", help="run or resume a study (tuning with gates, test stage, tables)")
    st.add_argument("study", help="study file (.yaml, .yml, .toml or .json)")
    st.add_argument("-o", "--output", metavar="DIR", help="study directory (default: 'output' of the study file)")
    st.add_argument("--workers", type=int,
                    help="worker processes (default: the study file's 'workers', else the CPUs minus four)")
    st.add_argument("--tuning-only", action="store_true", help="stop after the tuning gates")
    st.add_argument("--dry-run", action="store_true", help="show what would run, run nothing")
    st.add_argument("--status", action="store_true", help="show finished, failed and remaining jobs")
    st.add_argument("--report", action="store_true", help="write the report when the study is complete")
    st.add_argument("-q", "--quiet", action="store_true", help="print nothing but errors")
    st.set_defaults(func=_cmd_study)
    rp = sub.add_parser("report", help="write the Markdown/HTML report of a study directory")
    rp.add_argument("dir", help="study directory")
    rp.add_argument("-o", "--output", metavar="OUT", help="report directory (default: DIR/report)")
    rp.add_argument("--format", nargs="+", choices=("md", "html"), default=["md", "html"])
    rp.add_argument("--no-figures", action="store_true", help="tables only")
    rp.set_defaults(func=_cmd_report)
    ss = sub.add_parser("status", help="finished, failed and remaining jobs of a study and the time still needed")
    ss.add_argument("target", help="study file or study directory")
    ss.add_argument("-o", "--output", metavar="DIR", help="study directory (for a study file; default: its 'output')")
    ss.add_argument("--workers", type=int, help="workers assumed for the estimate (default: those of the last session)")
    ss.set_defaults(func=_cmd_status)
    g = sub.add_parser("gui", help="start the browser dashboard (pip install handoverlab[gui])")
    g.add_argument("--port", type=int, default=8501, help="port of the local server (default 8501)")
    g.add_argument("--address", default="localhost", help="address to listen on (default localhost)")
    g.add_argument("--headless", action="store_true", help="do not open a browser window")
    g.set_defaults(func=_cmd_gui)
    ru = sub.add_parser("rules", help="list the available handover rules")
    ru.set_defaults(func=_cmd_rules)
    i = sub.add_parser("init", help="write an example configuration")
    i.add_argument("path", nargs="?", default="config.yaml")
    i.add_argument("--force", action="store_true")
    i.set_defaults(func=_cmd_init)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":                                   # pragma: no cover
    sys.exit(main())
