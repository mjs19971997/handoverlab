# SPDX-License-Identifier: MIT
"""Status of a study: finished, failed and remaining jobs per stage, and the time still needed.

``handoverlab status STUDY`` (a study file or a study directory) prints, for
every stage that can be planned now, the planned, finished, failed and
remaining jobs and the rule runs that still have to be simulated.  Stages
that depend on earlier results (``tune2`` after ``tune1``, ``test`` after the
gates) are counted from the study file until they can be planned.

Time estimate
    From the finished jobs of the study: the mean time to build a world and
    the time per simulated rule run, scaled by users x simulated seconds of
    each job.  The remaining CPU time is spread over the workers (default:
    the worker count of the last session) and is never shorter than the
    longest remaining job.  It is a rough guide: jobs of other conditions or
    rules can take longer or shorter, and a machine that is busy with other
    work is slower.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Sequence, Union

from ..stability import check_schema
from .config import Study, load_study, study_from_dict
from .runner import Job, default_workers
from .store import StudyStore, read_json
from .study import (_budget_of, apply_amendments, load_amendments, output_dir, plan_round1, plan_round2,
                    plan_test)


def load_study_dir(root: str) -> Study:
    """The study stored in a study directory (from ``study.lock.json``)."""
    p = os.path.join(root, "study.lock.json")
    if not os.path.exists(p):
        raise FileNotFoundError("%s is not a study directory (no study.lock.json)" % root)
    lock = read_json(p)
    check_schema(lock.get("schema"), p)
    st = study_from_dict(lock["study"])
    st.output = root
    return st


def resolve(target: Union[str, Study], out: Optional[str] = None):
    """(study, study directory) for a study file, a study directory or a :class:`Study`."""
    if isinstance(target, Study):
        return target, output_dir(target, out)
    if os.path.isdir(target):
        return load_study_dir(target), out or target
    st = load_study(target)
    return st, output_dir(st, out)


# ---------------------------------------------------------------------------- measured rates
def _job_units(scenario: Dict[str, Any]) -> float:
    """Users x simulated seconds of one rule run (the unit of engine time)."""
    return float(scenario["mobility"]["users"]) * float(scenario["run"]["duration_s"])


def measured_rates(records: Sequence[Dict[str, Any]]) -> Optional[Dict[str, float]]:
    """Mean world-build time and engine time per rule run and user-second from finished job records."""
    world, n_world, eng, units = 0.0, 0, 0.0, 0.0
    for rec in records:
        n = int(rec.get("simulated", 0))
        tm = rec.get("timing", {})
        if n <= 0 or "total_s" not in tm:
            continue
        world += float(tm.get("world_s", 0.0))
        n_world += 1
        eng += max(0.0, float(tm["total_s"]) - float(tm.get("world_s", 0.0)))
        units += n * _job_units(rec["scenario"])
    if not n_world or units <= 0:
        return None
    return dict(world_s=world / n_world, rule_s_per_unit=eng / units, jobs=n_world)


def job_estimate(job: Job, todo_rules: int, rates: Dict[str, float]) -> float:
    if todo_rules <= 0:
        return 0.0
    return rates["world_s"] + rates["rule_s_per_unit"] * todo_rules * _job_units(job.scenario)


def _fmt_time(s: float) -> str:
    if s < 90:
        return "%.0f s" % s
    if s < 5400:
        return "%.0f min" % (s / 60.0)
    return "%.1f h" % (s / 3600.0)


# ---------------------------------------------------------------------------- status
def status_data(study: Study, out: Optional[str] = None, workers: Optional[int] = None) -> Dict[str, Any]:
    """Structured status (see the module text): stages, gates, sessions and the time estimate."""
    root = output_dir(study, out)
    store = StudyStore(root)
    study = apply_amendments(study, load_amendments(store))
    records = store.records()
    rates = measured_rates(records)
    index = store.run_index()
    failed = set()
    if os.path.isdir(store.path("failed")):
        failed = {os.path.splitext(f)[0] for f in os.listdir(store.path("failed"))}
    man = read_json(store.path("manifest.json")) if os.path.exists(store.path("manifest.json")) else {}
    sessions = man.get("sessions", [])
    if workers is None:
        workers = (sessions[-1].get("workers") if sessions else None) or study.workers or default_workers()
    stages: List[Dict[str, Any]] = []
    est_jobs: List[float] = []

    def planned(stage: str, jobs: Sequence[Job]) -> bool:
        done = [j for j in jobs if store.has_job(j.stage, j.id)]
        todo = [j for j in jobs if not store.has_job(j.stage, j.id)]
        sim = 0
        for j in todo:
            n = len({r["run_key"] for r in j.rules if r["run_key"] not in index})
            sim += n
            if rates:
                est_jobs.append(job_estimate(j, n, rates))
        stages.append(dict(stage=stage, planned=True, jobs=len(jobs), done=len(done),
                           failed=sum(j.id in failed for j in jobs), todo=len(todo), rule_runs=sim))
        return not todo

    def unplanned(stage: str, n_jobs: int, rules_per_job: int, scenario_units: float, note: str):
        stages.append(dict(stage=stage, planned=False, jobs=n_jobs, done=0, failed=0, todo=n_jobs,
                           rule_runs=n_jobs * rules_per_job, note=note))
        if rates and rules_per_job:
            per = rates["world_s"] + rates["rule_s_per_unit"] * rules_per_job * scenario_units
            est_jobs.extend([per] * n_jobs)

    units = sum(_job_units(study.scenario_for(c).to_dict()) for c in study.condition_list()) / max(
        1, len(study.condition_list()))
    n_test_jobs = len(study.condition_list()) * len(study.test_seeds)
    n_test_rules = len(study.test_rule_names()) - (1 if study.has_tuning else 0)
    gates = None
    tuned = None
    test_ready = True
    if study.has_tuning:
        j1 = plan_round1(study)
        n2 = sum(max(0, _budget_of(study, m) - min(study.tuning.n_random, _budget_of(study, m)))
                 for m in study.tuned_methods)
        if not planned("tune1", j1):
            unplanned("tune2", len(j1) if n2 else 0, n2, units, "planned after tune1; up to this many rule runs")
            test_ready = False
        else:
            j2 = plan_round2(study, store, j1)
            if not planned("tune2", j2):
                test_ready = False
            else:
                gp = store.path("tuned", "gates.json")
                if not os.path.exists(gp):
                    test_ready = False
                else:
                    gates = read_json(gp)
                    if gates["ok"]:
                        tuned = dict(groups={})
                        for f in os.listdir(store.path("tuned")):
                            if f != "gates.json" and f.endswith(".json"):
                                d = read_json(store.path("tuned", f))
                                tuned["groups"][d["group"]] = d
                    else:
                        test_ready = False
    if test_ready:
        planned("test", plan_test(study, tuned))
    else:
        unplanned("test", n_test_jobs, n_test_rules + (1 if study.has_tuning else 0), units,
                  "planned after the gates")
    est = None
    if rates and est_jobs:
        cpu = sum(est_jobs)
        w = max(1, int(workers))
        est = dict(cpu_s=cpu, wall_s=max(cpu / w, max(est_jobs)), workers=w, **rates)
    elif rates:
        est = dict(cpu_s=0.0, wall_s=0.0, workers=int(workers), **rates)
    running = bool(sessions) and "end" not in sessions[-1]
    return dict(study=study.name, root=store.root, stages=stages, gates=gates, estimate=est, sessions=len(sessions),
                running=running, last_session=sessions[-1] if sessions else None,
                amendments=len(load_amendments(store)))


def study_status(study: Union[str, Study], out: Optional[str] = None, workers: Optional[int] = None) -> List[str]:
    """Lines with the planned, finished, failed and remaining jobs of every stage and the time estimate."""
    st, root = resolve(study, out)
    d = status_data(st, root, workers)
    lines = ["study %s in %s" % (d["study"], d["root"])]
    ls = d["last_session"]
    if ls:
        if d["running"]:
            lines.append("  session %d started %s with %s workers and has not ended (running, or stopped without "
                         "a clean exit)" % (d["sessions"], ls.get("start", "?"), ls.get("workers", "?")))
        else:
            lines.append("  last session (%d) %s: %s" % (d["sessions"], ls.get("end", "?"), ls.get("status", "?")))
    else:
        lines.append("  not started yet")
    if d["amendments"]:
        lines.append("  grids extended %d time(s) by the grid_edge policy 'extend' (see AMENDMENTS.md)"
                     % d["amendments"])
    lines.append("  %-6s %6s %6s %7s %7s %10s" % ("stage", "jobs", "done", "failed", "to run", "rule runs"))
    for s in d["stages"]:
        if s["planned"]:
            lines.append("  %-6s %6d %6d %7d %7d %10d" % (s["stage"], s["jobs"], s["done"], s["failed"], s["todo"],
                                                      s["rule_runs"]))
        else:
            lines.append("  %-6s %6s %6s %7s %7s %10s   (%s)" % (s["stage"], "~%d" % s["jobs"], "-", "-",
                                                             "~%d" % s["todo"], "~%d" % s["rule_runs"], s["note"]))
    g = d["gates"]
    if g is not None:
        lines.append("  gates: %s (%d blocking, %d warnings)" % ("pass" if g["ok"] else "BLOCKED", len(g["blocking"]),
                                                                len(g["warnings"])))
    e = d["estimate"]
    left = sum(s["todo"] for s in d["stages"])
    if not left:
        lines.append("  complete: nothing left to run")
    elif e is None:
        lines.append("  time left: no estimate yet (no finished job to measure from)")
    else:
        lines.append("  time left: about %s with %d worker%s (%s CPU; measured on %d job%s: world %.1f s, "
                     "%.2f s per rule run of 1000 user-seconds)"
                     % (_fmt_time(e["wall_s"]), e["workers"], "s" if e["workers"] != 1 else "", _fmt_time(e["cpu_s"]),
                        e["jobs"], "s" if e["jobs"] != 1 else "", e["world_s"], 1000 * e["rule_s_per_unit"]))
    return lines


__all__ = ["study_status", "status_data", "load_study_dir", "resolve", "measured_rates"]
