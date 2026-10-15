# SPDX-License-Identifier: MIT
"""Studies: equal-budget tuning with gates, paired test stages, stored and resumable results, reports.

Quick start::

    from handoverlab.studies import load_study, run_study, write_report

    study = load_study("examples/study_smoke.yaml")
    run_study(study, workers=2, progress=print)      # resumable: re-running skips finished jobs
    write_report("results/study-smoke")              # report.md, report.html, figures

or on the command line ``handoverlab study examples/study_smoke.yaml`` and
``handoverlab report results/study-smoke``.  See :mod:`.config` for the study
file, :mod:`.tuning` for the selection rule and the gates, :mod:`.runner` for
jobs and workers, :mod:`.store` for the directory layout and
:mod:`handoverlab.stats` for the statistics.
"""
from .config import Compare, Method, Study, Tuning, load_study, study_from_dict
from .report import ReportError, build_report, write_report
from .runner import MODEL_VERSION, Job, default_workers, run_jobs, run_key
from .store import StudyStore, read_table, write_table
from .study import GateError, StudyError, StudyResult, dry_run, run_study, study_status
from .tuning import GATES, GateResult, first_round, refine, select

__all__ = ["Compare", "Method", "Study", "Tuning", "load_study", "study_from_dict", "ReportError", "build_report",
           "write_report", "MODEL_VERSION", "Job", "default_workers", "run_jobs", "run_key", "StudyStore",
           "read_table", "write_table", "GateError", "StudyError", "StudyResult", "dry_run", "run_study",
           "study_status", "GATES", "GateResult", "first_round", "refine", "select"]
