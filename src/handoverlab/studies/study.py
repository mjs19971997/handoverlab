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
from ..stability import SCHEMA_VERSION
from .config import Study, label
from .runner import MODEL_VERSION, Job, default_workers, run_jobs
from .store import StudyStore, atomic_write_json, read_json, write_table
from .tuning import (GateResult, MethodTuning, describe_setting, evaluate_gates, extension_values, first_round,
                     refine, seed_overlap_gate, select, setting_key, summary_lines)


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
    write_gate_report(study, store, gates)
    return dict(groups=groups, gates=gates)


def write_gate_report(study: Study, store: StudyStore, gates: Sequence[GateResult]) -> None:
    """Write ``tuned/gates.json`` (every gate, the blocking ones, the warnings, the selection rule)."""
    doc = dict(ok=not any(x.blocking for x in gates), blocking=[x.as_dict() for x in gates if x.blocking],
               warnings=[x.as_dict() for x in gates if not x.ok and not x.blocking],
               gates=[x.as_dict() for x in gates], selection=_selection_text(study))
    atomic_write_json(store.path("tuned", "gates.json"), doc)


# ---------------------------------------------------------------------------- grid extensions (amendments)
AMENDMENTS = "amendments.json"


def load_amendments(store: StudyStore) -> List[Dict[str, Any]]:
    """Recorded grid extensions of a study directory (one entry per extension round, oldest first)."""
    p = store.path(AMENDMENTS)
    return list(read_json(p).get("rounds", [])) if os.path.exists(p) else []


def apply_amendments(study: Study, rounds: Sequence[Dict[str, Any]]) -> Study:
    """A copy of ``study`` whose grids include every recorded extension."""
    if not rounds:
        return study
    import copy
    sx = copy.deepcopy(study)
    by_name = {m.name: m for m in sx.methods}
    for rd in rounds:
        for c in rd["changes"]:
            m = by_name.get(c["method"])
            if m is None or c["param"] not in m.grid:
                continue
            vals = list(m.grid[c["param"]])
            for v in c["added"]:
                if v not in vals:
                    vals.append(v)
            m.grid[c["param"]] = sorted(vals)
    return sx


def plan_extension(study: Study, gates: Sequence[GateResult], steps: int):
    """Grid extensions for failed ``grid_edge`` gates; returns (changes, problems).

    One change per method, parameter and side, with the values to add (checked
    by constructing the rule with each of them).  ``problems`` names the edges
    that cannot be extended.
    """
    from ..rules import make_rule
    by_name = {m.name: m for m in study.methods}
    changes: Dict[tuple, Dict[str, Any]] = {}
    problems: List[str] = []
    for g in gates:
        m = by_name[g.method]
        for p, side in g.edges:
            key = (m.name, p, side)
            where = "%s, budget %s" % (g.group, g.budget)
            if key in changes:
                changes[key]["where"].append(where)
                continue
            vals = m.grid[p]
            ok = []
            for v in extension_values(vals, side, steps):
                cfg = {k: vv[0] for k, vv in m.grid.items()}
                cfg[p] = v
                try:
                    make_rule(m.spec(cfg))
                except (ValueError, TypeError) as e:          # value outside what the rule accepts
                    problems.append("%s.%s = %s is not accepted by rule %s (%s)" % (m.name, p, v, m.rule, e))
                    break
                ok.append(v)
            if ok:
                changes[key] = dict(method=m.name, param=p, side=side, added=ok, grid_before=list(vals),
                                    where=[where])
            elif not any(x.startswith("%s.%s " % (m.name, p)) for x in problems):
                problems.append("%s.%s cannot be extended below %s (declare natural_bounds: {%s: %s} if this end "
                                "is a physical limit)" % (m.name, p, vals[0] if side == "lower" else vals[-1], p,
                                                          side))
    return list(changes.values()), problems


def _write_amendments(store: StudyStore, rounds: Sequence[Dict[str, Any]]) -> None:
    atomic_write_json(store.path(AMENDMENTS), dict(rounds=list(rounds)))
    lines = ["# Amendments", "", "Grid extensions made by the gate policy `grid_edge: extend` (newest last).", ""]
    for rd in rounds:
        lines.append("## Extension %d (%s)" % (rd["round"], rd["time"]))
        lines.append("")
        for c in rd["changes"]:
            lines.append("- `%s.%s`: added %s at the %s end (grid before: %s); selected at the edge in %s."
                         % (c["method"], c["param"], ", ".join(map(str, c["added"])), c["side"],
                            ", ".join(map(str, c["grid_before"])), "; ".join(c["where"])))
        lines.append("")
    with open(store.path("AMENDMENTS.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))


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
    return _jobs(study, "test", study.test_seeds, rules, events=job_events(study.events))


def job_events(level: str):
    """Event-log level as stored in a job (``False``, ``True`` or ``"full"``; keeps older job IDs valid)."""
    return {"off": False, "summary": True, "full": "full"}[level]


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
                       run_key=r["run_key"], events=r.get("events"), trace=r.get("trace"))
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
    atomic_write_json(lock_p, dict(schema=SCHEMA_VERSION, sha256=h, study=study.resolved()))
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
            rounds = load_amendments(store)
            while True:
                sx = apply_amendments(study, rounds)
                j1 = plan_round1(sx)
                _stage(sx, store, "tune1", j1, w, say, res)
                j2 = plan_round2(sx, store, j1)
                _stage(sx, store, "tune2", j2, w, say, res)
                tuned = analyse_tuning(sx, store, j1 + j2)
                ext = [g for g in tuned["gates"] if g.gate == "grid_edge" and not g.ok and g.policy == "extend"]
                if not ext:
                    break
                changes, problems = plan_extension(sx, ext, study.tuning.extend_steps)
                if changes and len(rounds) < study.tuning.max_extensions:
                    rounds.append(dict(round=len(rounds) + 1, time=_now(), changes=changes))
                    _write_amendments(store, rounds)
                    for c in changes:
                        say("  extend %s.%s at the %s end by %s (extension %d of at most %d); tuning again"
                            % (c["method"], c["param"], c["side"], ", ".join(map(str, c["added"])), len(rounds),
                               study.tuning.max_extensions))
                    continue
                why = ("the grid was extended %d time(s), the cap max_extensions = %d"
                       % (len(rounds), study.tuning.max_extensions)) if changes else "; ".join(problems)
                for g in ext:
                    g.policy = "block"
                    g.message += " (policy extend; not resolved by extension: %s)" % why
                write_gate_report(sx, store, tuned["gates"])
                break
            study = sx
            all_jobs += j1 + j2
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


__all__ = ["StudyError", "GateError", "StudyResult", "run_study", "dry_run", "plan_round1",
           "plan_round2", "plan_test", "analyse_tuning", "run_rows", "tuning_rows", "output_dir", "load_amendments",
           "apply_amendments", "plan_extension", "write_gate_report", "job_events"]
