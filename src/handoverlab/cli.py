# SPDX-License-Identifier: MIT
"""Command line: ``handoverlab run config.yaml``.

Commands
    run CONFIG [-o OUT] [--seeds S ...] [--events FILE]
        Run the experiment in CONFIG (YAML, TOML or JSON) and write one row per
        seed and rule to OUT (.csv or .json; default: the ``output`` key of
        the configuration, else ``results/<config name>.csv``).
    rules
        List the available handover rules.
    init [PATH]
        Write a commented example configuration.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from typing import List, Optional

from . import __version__
from .config import ConfigError, load_config

EXAMPLE_CONFIG = """\
# HandoverLab experiment: A3 versus conditional handover in the TR 37.885 street grid.
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
        results = run_experiment(exp, log_events=bool(args.events), progress=log)
    except (KeyError, ValueError) as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    write_results(results, out, exp.scenario.to_dict())
    if args.events:
        _write_events(results, args.events)
    if not args.quiet:
        print("%-12s %5s " % ("rule", "seed") + " ".join("%12s" % k[:12] for k in SUMMARY))
        for r in results:
            print("%-12s %5d " % (r.rule[:12], r.seed) + " ".join("%12.4f" % r.metrics[k] for k in SUMMARY))
        print("wrote %s" % out)
    return 0


def _write_events(results, path: str) -> None:
    from .engine import EVENT_FIELDS
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(("seed", "rule") + EVENT_FIELDS)
        for r in results:
            for ev in r.events or []:
                w.writerow([r.seed, r.rule] + [ev[k] for k in EVENT_FIELDS])


def _cmd_rules(args) -> int:
    from .rules import available_rules, get_rule_class
    for key in available_rules():
        cls = get_rule_class(key)
        doc = (cls.__doc__ or "").strip().splitlines()
        print("%-10s %-12s %s" % (key, cls.family, doc[0] if doc else ""))
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
    r.add_argument("--events", metavar="FILE", help="also write the event log of every run to FILE (.csv)")
    r.add_argument("-q", "--quiet", action="store_true", help="print nothing but errors")
    r.set_defaults(func=_cmd_run)
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
