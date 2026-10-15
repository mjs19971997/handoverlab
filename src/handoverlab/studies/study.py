# SPDX-License-Identifier: MIT
"""Running a study: tuning rounds, gates, the test stage and the result tables.

Stages
    ``tune1``  every condition x tuning seed: the reference rule and the first
               (random) settings of every tuned method;
    ``tune2``  the same worlds with the refinement settings around the best
               setting of round 1 of each tuning group (if the budget is not
               spent yet);
    (gates)    selection per method and failure budget, then the gates of
               :mod:`handoverlab.studies.tuning`; a blocking gate stops the
               study here with :class:`GateError`;
    ``test``   every condition x test seed: the reference, every tuned method
               with its selected setting per budget (``METHOD@BUDGET``) and
               every untuned method.

Every stage is resumable: re-running the study skips the jobs whose records
exist and reuses stored rule runs.  After the stages the tables
``tables/runs`` and ``tables/tuning`` are rebuilt from the job records.
"""
from __future__ import annotations

import os
import platform
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence

from .. import __version__
from .config import Study, label
from .runner import MODEL_VERSION, Job, default_workers, run_jobs
from .store import StudyStore, atomic_write_json, read_json, write_table
from .tuning import (GateResult, MethodTuning, describe_setting, evaluate_gates, first_round, refine,
                     seed_overlap_gate, select, setting_key, summary_lines)


class StudyError(RuntimeError):
    """A study cannot continue (failed jobs or an invalid state); the message says why."""


class GateError(StudyError):
    """A blocking tuning gate failed; ``lines`` name every failed gate."""

    def __init__(self, lines: Sequence[str]):
        self.lines = list(lines)
        super().__init__("blocking tuning gates failed; the test stage was not started:\n  " +
                         "\n  ".join(self.lines))


@dataclass
class StudyResult:
    root: str
    jobs: Dict[str, int] = field(default_factory=dict)        # stage -> planned jobs
    ran: Dict[str, int] = field(default_factory=dict)         # stage -> jobs run now
    gates: List[GateResult] = field(default_factory=list)
    tables: Dict[str, str] = field(default_factory=dict)
    completed: bool = False


# ---------------------------------------------------------------------------- plans
def _budget_of(study: Study, m) -> int:
    return m.settings if m.settings is not None else study.tuning.settings


def _ref_entry(study: Study) -> Dict[str, Any]:
    ref = dict(study.tuning.reference)
    return dict(name=study.tuning.reference_name, spec=ref, method=study.tuning.reference_name, budget=None)


def round1_settings(study: Study) -> Dict[str, List[Dict[str, Any]]]:
    return {m.name: first_round(m.name, m.grid, min(study.tuning.n_random, _budget_of(study, m)))
            for m in study.tuned_methods}


def _jobs(study: Study, stage: str, seeds: Sequence[int], rules_of: Callable[[Dict[str, Any], str], List[Dict]],
          events: bool = False) -> List[Job]:
    jobs = []
    for cond in study.condition_list():
        group = study.group_of(cond)
        rules = rules_of(cond, group)
        if not rules:
            continue
        scd = study.scenario_for(cond).to_dict()
        for s in seeds:
            jobs.append(Job(stage, cond, group, int(s), scd, [dict(r) for r in rules], events))
    return jobs


def plan_round1(study: Study) -> List[Job]:
    r1 = round1_settings(study)

    def rules(cond, group):
        out = [_ref_entry(study)]
        for m in study.tuned_methods:
            for k, cfg in enumerate(r1[m.name]):
                out.append(dict(name="%s#%d" % (m.name, k + 1), spec=m.spec(cfg, "%s#%d" % (m.name, k + 1)),
                                method=m.name, budget=None, setting=cfg, round=1))
        return out
    return _jobs(study, "tune1", study.tuning_seeds, rules)


def _records_by_job(store: StudyStore, jobs: Sequence[Job]) -> List[Dict[str, Any]]:
    out = []
    for j in jobs:
        rec = store.load_job(j.stage, j.id)
        if rec is None:
            raise StudyError("job %s of stage %s has no record" % (j.id, j.stage))
        out.append(rec)
    return out


_MEANS = ("unnecessary_pm", "failures_pm", "handovers_pm", "pingpong_pm", "prepared_cells_mean",
          "too_late_pm", "too_early_pm")


def _group_means(study: Study, records: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """group -> rule name -> {setting, method, round, n_runs, means..., n_failures}."""
    t = study.tuning
    keys = list(dict.fromkeys(list(_MEANS) + [t.objective, t.constraint] + list(t.tie_breaks)))
    acc: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for rec in records:
        g = acc.setdefault(rec["group"], {})
        for r in rec["rules"]:
            e = g.setdefault(r["name"], dict(method=r["method"], setting=r.get("setting"), n_runs=0, n_failures=0,
                                             sums={k: 0.0 for k in keys}, round=1 if rec["stage"] == "tune1" else 2))
            e["n_runs"] += 1
            e["n_failures"] += int(r["metrics"]["n_failures"])
            for k in keys:
                e["sums"][k] += r["metrics"][k]
    out: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for g, rules in acc.items():
        out[g] = {}
        for name, e in rules.items():
            d = dict(method=e["method"], setting=e["setting"], n_runs=e["n_runs"], n_failures=e["n_failures"],
                     round=e["round"])
            d.update({k: v / e["n_runs"] for k, v in e["sums"].items()})
            out[g][name] = d
    return out


def _candidates(study: Study, means: Dict[str, Dict[str, Any]], method: str) -> List[Dict[str, Any]]:
    c = [dict(name=n, **v) for n, v in means.items() if v["method"] == method and n != study.tuning.reference_name]
    c.sort(key=lambda d: (d["round"], int(d["name"].rsplit("#", 1)[1])))
    return c


def _select(study: Study, cands, budget):
    t = study.tuning
    return select(cands, budget, t.tolerance, t.objective, t.constraint, t.tie_breaks)


def plan_round2(study: Study, store: StudyStore, round1_jobs: Sequence[Job]) -> List[Job]:
    """Refinement settings around the best setting of round 1 (first budget), per tuning group."""
    t = study.tuning
    means = _group_means(study, _records_by_job(store, round1_jobs))
    first_budget = list(t.budgets.values())[0]
    extra: Dict[str, List[Dict[str, Any]]] = {}
    for g, gm in means.items():
        ref = gm[t.reference_name]
        rows = []
        for m in study.tuned_methods:
            cands = _candidates(study, gm, m.name)
            n2 = _budget_of(study, m) - len(cands)
            if n2 <= 0 or not cands:
                continue
            sel = _select(study, cands, first_budget * ref[t.constraint])
            new = refine(m.name, m.grid, cands[sel.index]["setting"], [c["setting"] for c in cands], n2, g)
            for k, cfg in enumerate(new):
                name = "%s#%d" % (m.name, len(cands) + k + 1)
                rows.append(dict(name=name, spec=m.spec(cfg, name), method=m.name, budget=None, setting=cfg, round=2))
        extra[g] = rows
    return _jobs(study, "tune2", study.tuning_seeds, lambda cond, group: extra.get(group, []))


def analyse_tuning(study: Study, store: StudyStore, jobs: Sequence[Job]) -> Dict[str, Any]:
    """Selection and gates of every tuning group; writes ``tuned/<group>.json`` and ``tuned/gates.json``."""
    t = study.tuning
    means = _group_means(study, _records_by_job(store, jobs))
    gates: List[GateResult] = [seed_overlap_gate(study.tuning_seeds, study.test_seeds, t.gates["seed_overlap"])]
    groups: Dict[str, Any] = {}
    for g in sorted(means):
        gm = means[g]
        ref = gm[t.reference_name]
        budgets = {b: share * ref[t.constraint] for b, share in t.budgets.items()}
        mts = []
        mdoc = {}
        for m in study.tuned_methods:
            cands = _candidates(study, gm, m.name)
            mt = MethodTuning(m.name, m.grid, m.natural_bounds, _budget_of(study, m), cands)
            sel_doc = {}
            for b, val in budgets.items():
                if cands:
                    s = _select(study, cands, val)
                    mt.selected[b] = s
                    c = cands[s.index]
                    sel_doc[b] = dict(name=c["name"], setting=c["setting"], text=describe_setting(c["setting"]),
                                      met_budget=s.met_budget, n_meeting=s.n_meeting, n_near=s.n_near,
                                      **{k: c[k] for k in _MEANS})
            mts.append(mt)
            for c in cands:
                c["within"] = {b: c[t.constraint] <= v + 1e-12 for b, v in budgets.items()}
            mdoc[m.name] = dict(rule=m.rule, fixed=m.fixed, grid=m.grid, natural_bounds=m.natural_bounds,
                                budget_n=mt.budget_n, candidates=cands, selected=sel_doc)
        gg = evaluate_gates(g, mts, budgets, ref["n_failures"], t.gates, t.binding_share, t.min_reference_failures,
                            t.flat_share, t.tolerance, t.objective, t.constraint)
        gates.extend(gg)
        groups[g] = dict(group=g, reference=dict(name=t.reference_name, spec=t.reference, **ref), budgets=budgets,
                         budget_shares=dict(t.budgets), methods=mdoc, gates=[x.as_dict() for x in gg])
        atomic_write_json(store.path("tuned", _file_label(g) + ".json"), groups[g])
    doc = dict(ok=not any(x.blocking for x in gates), blocking=[x.as_dict() for x in gates if x.blocking],
               warnings=[x.as_dict() for x in gates if not x.ok and not x.blocking],
               gates=[x.as_dict() for x in gates], selection=_selection_text(study))
    atomic_write_json(store.path("tuned", "gates.json"), doc)
    return dict(groups=groups, gates=gates)


def _selection_text(study: Study) -> str:
    t = study.tuning
    return ("lowest %s among the settings with %s within the budget; settings within %.0f %% of it count as "
            "equal and are ordered by %s; if no setting meets the budget, the lowest %s"
            % (t.objective, t.constraint, 100 * t.tolerance, ", then ".join(t.tie_breaks), t.constraint))


def _file_label(g: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_.=," else "_" for ch in g)


def plan_test(study: Study, tuned: Optional[Dict[str, Any]]) -> List[Job]:
    def rules(cond, group):
        out = []
        if study.has_tuning:
            out.append(_ref_entry(study))
        for m in study.methods:
            if m.tuned:
                sel = tuned["groups"][group]["methods"][m.name]["selected"]
                for b in study.budget_names():
                    name = "%s@%s" % (m.name, b)
                    out.append(dict(name=name, spec=m.spec(sel[b]["setting"], name), method=m.name, budget=b,
                                    setting=sel[b]["setting"]))
            else:
                out.append(dict(name=m.name, spec=m.spec(), method=m.name, budget=None, setting=None))
        return out
    return _jobs(study, "test", study.test_seeds, rules, events=study.events)


# ---------------------------------------------------------------------------- tables
def run_rows(study: Study, records: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One flat row per job and rule."""
    rows = []
    ckeys = list(study.conditions)
    for rec in records:
        for r in rec["rules"]:
            row = dict(stage=rec["stage"], job=rec["job"], group=rec["group"], condition=label(rec["condition"]))
            row.update({"cond." + k: rec["condition"].get(k) for k in ckeys})
            row.update(seed=rec["seed"], rule=r["name"], method=r["method"], budget=r["budget"],
                       setting=setting_key(r["setting"]) if r.get("setting") else None, key=r["key"],
                       family=r["family"], fingerprint=r["fingerprint"], n_events=r["n_events"], reused=r["reused"],
                       run_key=r["run_key"], events=r.get("events"))
            row.update({"param." + k: (v if not isinstance(v, bool) else int(v)) for k, v in r["params"].items()})
            row.update(r["metrics"])
            rows.append(row)
    return rows


def tuning_rows(tuned: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for g, gd in tuned["groups"].items():
        for mname, md in gd["methods"].items():
            sel_names = {b: s["name"] for b, s in md["selected"].items()}
            for c in md["candidates"]:
                row = dict(group=g, method=mname, name=c["name"], round=c["round"], setting=setting_key(c["setting"]),
                           n_runs=c["n_runs"], n_failures=c["n_failures"])
                row.update({"param." + k: v for k, v in c["setting"].items()})
                row.update({k: c[k] for k in _MEANS})
                for b in gd["budgets"]:
                    row["budget." + b] = gd["budgets"][b]
                    row["within." + b] = bool(c["within"][b])
                    row["selected." + b] = sel_names.get(b) == c["name"]
                rows.append(row)
    return rows


def write_tables(study: Study, store: StudyStore, jobs: Sequence[Job], tuned: Optional[Dict[str, Any]]):
    tables = {}
    recs = [store.load_job(j.stage, j.id) for j in jobs]
    recs = [r for r in recs if r is not None]
    tables["runs"] = write_table(run_rows(study, recs), store.path("tables", "runs.parquet"))
    if tuned is not None:
        tables["tuning"] = write_table(tuning_rows(tuned), store.path("tables", "tuning.parquet"))
    return tables


# ---------------------------------------------------------------------------- manifest
def _versions() -> Dict[str, str]:
    import numpy
    import scipy
    return dict(handoverlab=__version__, model=MODEL_VERSION, python=platform.python_version(),
                numpy=numpy.__version__, scipy=scipy.__version__, platform=platform.platform(),
                machine=platform.machine(), processor=platform.processor(), cpus=str(os.cpu_count()))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _start_manifest(study: Study, store: StudyStore, workers: int) -> Dict[str, Any]:
    p = store.path("manifest.json")
    man = read_json(p) if os.path.exists(p) else dict(study=study.name, created=_now(), sessions=[], changes=[])
    lock_p = store.path("study.lock.json")
    h = study.lock_hash()
    if os.path.exists(lock_p):
        old = read_json(lock_p).get("sha256")
        if old != h:
            man.setdefault("changes", []).append(dict(time=_now(), old=old, new=h,
                                                      note="study file changed; unchanged jobs are reused"))
    atomic_write_json(lock_p, dict(sha256=h, study=study.resolved()))
    man["versions"] = _versions()
    man["lock_sha256"] = h
    man.setdefault("sessions", []).append(dict(start=_now(), workers=workers, versions=_versions()))
    atomic_write_json(p, man)
    return man


def _end_manifest(store: StudyStore, man: Dict[str, Any], ran: Dict[str, int], status: str) -> None:
    man["sessions"][-1].update(end=_now(), jobs_run=ran, status=status)
    atomic_write_json(store.path("manifest.json"), man)


# ---------------------------------------------------------------------------- driver
def output_dir(study: Study, out: Optional[str] = None) -> str:
    return out or study.output or os.path.join("results", study.name)


def run_study(study: Study, out: Optional[str] = None, workers: Optional[int] = None,
              progress: Optional[Callable[[str], None]] = None, stop_after: Optional[str] = None) -> StudyResult:
    """Run (or resume) all stages of ``study`` in ``out``; returns a :class:`StudyResult`.

    ``stop_after="tuning"`` stops after the gates.  Raises :class:`GateError`
    if a blocking gate fails and :class:`StudyError` if jobs failed (their
    tracebacks are in ``failed/``; re-running retries them).
    """
    say = progress or (lambda msg: None)
    root = output_dir(study, out)
    store = StudyStore(root)
    w = workers or study.workers or default_workers()
    res = StudyResult(store.root)
    ov = seed_overlap_gate(study.tuning_seeds, study.test_seeds, study.tuning.gates["seed_overlap"])
    if study.has_tuning and ov.blocking:
        raise GateError(summary_lines([ov]))
    man = _start_manifest(study, store, w)
    say("study %s -> %s (%d workers)" % (study.name, store.root, w))
    all_jobs: List[Job] = []
    tuned = None
    status = "failed"
    try:
        if study.has_tuning:
            j1 = plan_round1(study)
            _stage(study, store, "tune1", j1, w, say, res)
            j2 = plan_round2(study, store, j1)
            _stage(study, store, "tune2", j2, w, say, res)
            all_jobs += j1 + j2
            tuned = analyse_tuning(study, store, j1 + j2)
            res.gates = tuned["gates"]
            for line in summary_lines(res.gates):
                say("  gate " + line)
            atomic_write_json(store.path("plan.json"), _plan_doc(all_jobs))
            if any(g.blocking for g in res.gates):
                res.tables = write_tables(study, store, all_jobs, tuned)
                status = "blocked by gates"
                raise GateError(summary_lines([g for g in res.gates if g.blocking]))
            if stop_after == "tuning":
                res.tables = write_tables(study, store, all_jobs, tuned)
                status = "stopped after tuning"
                return res
        jt = plan_test(study, tuned)
        _stage(study, store, "test", jt, w, say, res)
        all_jobs += jt
        atomic_write_json(store.path("plan.json"), _plan_doc(all_jobs))
        res.tables = write_tables(study, store, all_jobs, tuned)
        res.completed = True
        status = "complete"
        say("tables: %s" % ", ".join(os.path.relpath(p, store.root) for p in res.tables.values()))
        return res
    finally:
        _end_manifest(store, man, res.ran, status)


def _plan_doc(jobs: Sequence[Job]) -> Dict[str, Any]:
    doc: Dict[str, List[str]] = {}
    for j in jobs:
        doc.setdefault(j.stage, []).append(j.id)
    return dict(stages=doc)


def _stage(study: Study, store: StudyStore, stage: str, jobs: Sequence[Job], workers: int, say, res: StudyResult):
    res.jobs[stage] = len(jobs)
    if not jobs:
        res.ran[stage] = 0
        return
    have = sum(store.has_job(j.stage, j.id) for j in jobs)
    n_rules = sum(len(j.rules) for j in jobs)
    say("stage %s: %d jobs (%d rule runs), %d done earlier" % (stage, len(jobs), n_rules, have))
    done, failed = run_jobs(jobs, store.root, workers, progress=say)
    res.ran[stage] = len(done)
    if failed:
        raise StudyError("%d job(s) of stage %s failed; see %s (re-run the study to retry them)"
                         % (len(failed), stage, store.path("failed")))


def study_status(study: Study, out: Optional[str] = None) -> List[str]:
    """Lines with the planned, finished and failed jobs of every stage that can be planned now."""
    store = StudyStore(output_dir(study, out))
    lines = ["study %s in %s" % (study.name, store.root)]
    failed = set()
    if os.path.isdir(store.path("failed")):
        failed = {os.path.splitext(f)[0] for f in os.listdir(store.path("failed"))}

    def line(stage, jobs):
        done = sum(store.has_job(j.stage, j.id) for j in jobs)
        bad = sum(j.id in failed for j in jobs)
        lines.append("  %-6s %4d jobs: %4d done, %3d failed, %4d to run" % (stage, len(jobs), done, bad,
                                                                          len(jobs) - done))
        return done == len(jobs)

    tuned = None
    if study.has_tuning:
        j1 = plan_round1(study)
        if not line("tune1", j1):
            lines.append("  tune2, test: planned after round 1")
            return lines
        j2 = plan_round2(study, store, j1)
        if not line("tune2", j2):
            lines.append("  test: planned after tuning")
            return lines
        gp = store.path("tuned", "gates.json")
        if not os.path.exists(gp):
            lines.append("  gates: not evaluated yet; test: planned after tuning")
            return lines
        g = read_json(gp)
        lines.append("  gates: %s (%d blocking, %d warnings)" % ("pass" if g["ok"] else "BLOCKED",
                                                                 len(g["blocking"]), len(g["warnings"])))
        if not g["ok"]:
            return lines
        tuned = dict(groups={})
        for f in os.listdir(store.path("tuned")):
            if f != "gates.json" and f.endswith(".json"):
                d = read_json(store.path("tuned", f))
                tuned["groups"][d["group"]] = d
    line("test", plan_test(study, tuned))
    return lines


def dry_run(study: Study) -> List[str]:
    """What the study would run, without running anything."""
    lines = ["study %s: %d condition(s), %d tuning seed(s), %d test seed(s)"
             % (study.name, len(study.condition_list()), len(study.tuning_seeds), len(study.test_seeds))]
    if study.has_tuning:
        t = study.tuning
        groups = sorted({study.group_of(c) for c in study.condition_list()})
        lines.append("tuning: %d group(s) (%s), %d settings per method (%d random, then refinement), budgets %s"
                     % (len(groups), ", ".join(groups), t.settings, t.n_random,
                        ", ".join("%s = %g x reference" % kv for kv in t.budgets.items())))
        for m in study.tuned_methods:
            from .tuning import grid_size
            lines.append("  %-12s rule %-6s grid %s (%d settings)" % (m.name, m.rule, ", ".join(
                "%s: %d values" % (p, len(v)) for p, v in m.grid.items()), grid_size(m.grid)))
        j1 = plan_round1(study)
        lines.append("stage tune1: %d jobs, %d rule runs" % (len(j1), sum(len(j.rules) for j in j1)))
        n2 = sum(max(0, _budget_of(study, m) - min(study.tuning.n_random, _budget_of(study, m)))
                 for m in study.tuned_methods)
        lines.append("stage tune2: %d jobs, up to %d rule runs" % (len(j1) if n2 else 0, n2 * len(j1)))
        g = seed_overlap_gate(study.tuning_seeds, study.test_seeds, study.tuning.gates["seed_overlap"])
        lines.append("gate seed_overlap: %s (%s)" % (g.status, g.message))
    names = study.test_rule_names()
    n_test = len(study.condition_list()) * len(study.test_seeds)
    lines.append("stage test: %d jobs x %d rules (%s)" % (n_test, len(names), ", ".join(names)))
    lines.append("baseline of the paired comparisons: %s" % study.baseline())
    return lines


__all__ = ["StudyError", "GateError", "StudyResult", "run_study", "study_status", "dry_run", "plan_round1",
           "plan_round2", "plan_test", "analyse_tuning", "run_rows", "tuning_rows", "output_dir"]
