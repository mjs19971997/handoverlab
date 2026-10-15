# SPDX-License-Identifier: MIT
"""Jobs, content hashes and their execution in a pool of worker processes.

A *job* is one world (a condition and a seed) with a list of rules.  Its ID
is a content hash: the SHA-256 of the canonical JSON of the resolved
scenario, the seed, the rule names and the *run keys* of its rules.  A run
key identifies one rule run: the hash of the scenario, the seed, the rule's
registry key and its full parameter set (as reported by ``params()``), and
:data:`MODEL_VERSION`.  Names do not enter a run key, because they do not
change a result.

Resumption and reuse
    A job whose record exists is skipped.  Before a job runs, every rule
    whose run key is already stored in the study (in any stage) is taken from
    the stored record instead of being simulated (rules on one world do not
    influence each other, which the rule contract checks), and identical
    rules within a job run once.  If nothing is left to simulate, the world
    is not even built.

Workers
    One job per process (processes are started with "spawn" on every
    platform); BLAS and OpenMP threads are limited to one per process.  The default number of workers leaves cores free
    (:func:`default_workers`).  Jobs are started longest first.  Worker
    count and order never change a result: every job is deterministic.
"""
from __future__ import annotations

import hashlib
import multiprocessing
import os
import platform
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .. import __version__
from .config import canonical

#: Version of the simulation model.  It changes whenever identical inputs give
#: different results (the golden fingerprints are regenerated at the same
#: time), and it is part of every run key and job ID, so stored results of an
#: older model are never reused.
MODEL_VERSION = "1"

_THREAD_VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
                "VECLIB_MAXIMUM_THREADS")


def default_workers(n_cpu: Optional[int] = None) -> int:
    """Default worker count: all logical CPUs but four (half of them on machines with fewer than eight)."""
    n = n_cpu or os.cpu_count() or 1
    return max(1, n - 4) if n >= 8 else max(1, n // 2)


def _sha(obj: Any) -> str:
    return hashlib.sha256(canonical(obj).encode()).hexdigest()


def scenario_hash_dict(scenario_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Scenario as it enters a hash: everything but its name."""
    return {k: v for k, v in scenario_dict.items() if k != "name"}


def run_key(scenario_dict: Dict[str, Any], seed: int, rule_key: str, params: Dict[str, Any]) -> str:
    """Content hash of one rule run (see the module text)."""
    return _sha(dict(model=MODEL_VERSION, scenario=scenario_hash_dict(scenario_dict), seed=int(seed),
                     rule=rule_key, params=params))


@dataclass
class Job:
    """One world (condition and seed) with its rules.

    ``rules`` are dictionaries with ``name``, ``spec`` (a rule specification
    for :func:`~handoverlab.rules.make_rule`) and optional labels ``method``,
    ``budget`` and ``setting``.  ``events`` is the event-log level kept for
    every rule run: ``False`` (off), ``True`` (summary) or ``"full"`` (summary
    and trace).
    """
    stage: str
    condition: Dict[str, Any]
    group: str
    seed: int
    scenario: Dict[str, Any]
    rules: List[Dict[str, Any]]
    events: Any = False
    _id: Optional[str] = field(default=None, repr=False)

    def __post_init__(self):
        from ..rules import make_rule
        for r in self.rules:
            if "run_key" not in r:
                obj = make_rule(r["spec"])
                r["params"] = obj.params()
                r["family"] = obj.family
                r["run_key"] = run_key(self.scenario, self.seed, r["spec"]["rule"], r["params"])

    @property
    def id(self) -> str:
        if self._id is None:
            self._id = _sha(dict(model=MODEL_VERSION, scenario=scenario_hash_dict(self.scenario), seed=self.seed,
                                 rules=[[r["name"], r["run_key"]] for r in self.rules], events=self.events))[:20]
        return self._id

    def reusable(self, cached: Dict[str, Any]) -> Dict[str, Any]:
        """Stored rule runs this job may reuse (with an event log, if the job keeps event logs)."""
        out = {}
        for r in self.rules:
            c = cached.get(r["run_key"])
            if c is not None and (not self.events or c.get("events")) and (self.events != "full" or c.get("trace")):
                out[r["run_key"]] = c
        return out

    def cost(self, cached: Dict[str, Any]) -> float:
        """Rough cost for ordering: rule runs still to simulate x users x duration."""
        use = self.reusable(cached)
        todo = len({r["run_key"] for r in self.rules if r["run_key"] not in use})
        sc = self.scenario
        return (todo + 0.5 * bool(todo)) * sc["mobility"]["users"] * sc["run"]["duration_s"]

    def payload(self, cached: Dict[str, Any]) -> Dict[str, Any]:
        """Picklable description for a worker, with the stored results it may reuse."""
        return dict(id=self.id, stage=self.stage, condition=self.condition, group=self.group, seed=self.seed,
                    scenario=self.scenario, rules=self.rules, events=self.events, cached=self.reusable(cached))


def peak_memory_mb() -> Optional[float]:
    """Peak resident memory of this process so far [MB], or None where it cannot be read."""
    try:
        import resource
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return peak / 1024.0 / (1024.0 if platform.system() == "Darwin" else 1.0)
    except ImportError:
        pass
    try:                                                      # Windows
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
        c = PMC()
        c.cb = ctypes.sizeof(PMC)
        k32 = ctypes.windll.kernel32
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        get = ctypes.windll.psapi.GetProcessMemoryInfo
        get.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
        get.restype = wintypes.BOOL
        if get(k32.GetCurrentProcess(), ctypes.byref(c), c.cb):
            return c.PeakWorkingSetSize / 2.0 ** 20
    except Exception:                                         # pragma: no cover
        pass
    return None


def execute(payload: Dict[str, Any], root: str) -> Dict[str, Any]:
    """Run one job and write its record atomically (the function a worker process calls).

    Returns the record, or ``{"job": id, "error": traceback}`` if the job failed
    (the traceback is also written to ``failed/<job>.txt``).
    """
    from .store import StudyStore
    store = StudyStore(root)
    try:
        rec = _execute(payload, store)
        store.write_job(rec)
        return rec
    except Exception:                                         # noqa: BLE001 - reported per job
        text = traceback.format_exc()
        store.write_failed(payload["id"], text)
        return dict(job=payload["id"], stage=payload["stage"], error=text)


def _execute(payload: Dict[str, Any], store) -> Dict[str, Any]:
    from ..config import Scenario
    from ..simulate import run_world
    from ..world import build_world
    t0 = time.perf_counter()
    cached = payload["cached"]
    entries = payload["rules"]
    todo: List[Dict[str, Any]] = []
    seen = set()
    for e in entries:
        k = e["run_key"]
        if k not in cached and k not in seen:
            seen.add(k)
            todo.append(e)
    fresh: Dict[str, Dict[str, Any]] = {}
    t_world = radio = 0.0
    if todo:
        sc = Scenario.from_dict(payload["scenario"])
        tw = time.perf_counter()
        world = build_world(sc, payload["seed"])
        t_world = time.perf_counter() - tw
        res = run_world(world, [e["spec"] for e in todo], log_events=payload["events"])
        for e, r in zip(todo, res):
            ev = tr = None
            if payload["events"]:
                from ..eventlog import trace_path, write_events, write_trace
                ev_path = store.events_path(e["run_key"])
                os.makedirs(os.path.dirname(ev_path), exist_ok=True)
                ev = os.path.relpath(write_events([r], ev_path), store.root).replace(os.sep, "/")
                if r.trace is not None:
                    tr = os.path.relpath(write_trace([r], trace_path(ev_path)), store.root).replace(os.sep, "/")
            fresh[e["run_key"]] = dict(metrics=r.metrics, fingerprint=r.fingerprint, n_events=r.n_events,
                                       family=r.family, params=r.params, engine_s=r.timing["engine_s"], events=ev,
                                       trace=tr)
            radio = r.timing["radio_s"]
    rows = []
    first = set()
    for e in entries:
        k = e["run_key"]
        src = fresh.get(k) or cached[k]
        own = k in fresh and k not in first          # simulated for this row (not stored, not a duplicate)
        first.add(k)
        rows.append(dict(name=e["name"], key=e["spec"]["rule"], method=e.get("method"), budget=e.get("budget"),
                         setting=e.get("setting"), family=src["family"], params=src["params"], run_key=k,
                         fingerprint=src["fingerprint"], n_events=src["n_events"], metrics=src["metrics"],
                         engine_s=src.get("engine_s") if own else None, events=src.get("events"),
                         trace=src.get("trace"),
                         reused=not own))
    return dict(job=payload["id"], stage=payload["stage"], condition=payload["condition"], group=payload["group"],
                seed=payload["seed"], model=MODEL_VERSION, handoverlab=__version__, scenario=payload["scenario"],
                rules=rows, timing=dict(world_s=t_world, radio_s=radio, total_s=time.perf_counter() - t0),
                simulated=len(todo), peak_memory_mb=peak_memory_mb(), host=platform.node(), pid=os.getpid(),
                finished=datetime.now(timezone.utc).isoformat(timespec="seconds"))


class _Threads:
    """Limit BLAS/OpenMP threads of worker processes to one (restored afterwards)."""

    def __enter__(self):
        self.old = {k: os.environ.get(k) for k in _THREAD_VARS}
        for k in _THREAD_VARS:
            os.environ[k] = "1"
        return self

    def __exit__(self, *exc):
        for k, v in self.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return False


def run_jobs(jobs: Sequence[Job], root: str, workers: int = 1, cached: Optional[Dict[str, Any]] = None,
             progress: Optional[Callable[[str], None]] = None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Run the jobs that have no record yet; returns (new records, failures).

    With ``workers`` > 1 the jobs run in a process pool; a broken pool is
    restarted once and its unfinished jobs are tried again.
    """
    from .store import StudyStore
    store = StudyStore(root)
    cached = cached if cached is not None else store.run_index()
    todo = [j for j in jobs if not store.has_job(j.stage, j.id)]
    todo.sort(key=lambda j: -j.cost(cached))
    say = progress or (lambda msg: None)
    done: List[Dict[str, Any]] = []
    failed: List[Dict[str, Any]] = []
    if not todo:
        return done, failed
    t_start = time.perf_counter()
    n_total = len(todo)

    def report(rec):
        (failed if "error" in rec else done).append(rec)
        k = len(done) + len(failed)
        el = time.perf_counter() - t_start
        left = el / k * (n_total - k)
        if "error" in rec:
            say("  job %s FAILED (%d/%d): %s" % (rec["job"], k, n_total, rec["error"].strip().splitlines()[-1]))
        else:
            say("  job %s done (%d/%d, %.1f s, %d rules simulated; about %.0f s left)"
                % (rec["job"], k, n_total, rec["timing"]["total_s"], rec["simulated"], left))

    if workers <= 1 or len(todo) == 1:
        for j in todo:
            report(execute(j.payload(cached), store.root))
        return done, failed
    pending = list(todo)
    for attempt in (1, 2):
        with _Threads():
            try:
                with ProcessPoolExecutor(max_workers=min(workers, len(pending)),
                                         mp_context=multiprocessing.get_context("spawn")) as pool:
                    futs = {pool.submit(execute, j.payload(cached), store.root): j for j in pending}
                    for f in as_completed(futs):
                        report(f.result())
                        pending.remove(futs[f])
                break
            except BrokenProcessPool:
                if attempt == 2:
                    for j in pending:
                        report(dict(job=j.id, stage=j.stage, error="worker process died (BrokenProcessPool)"))
                    break
                say("  a worker process died; restarting the pool for %d unfinished jobs" % len(pending))
                pending = [j for j in pending if not store.has_job(j.stage, j.id)]
    return done, failed
