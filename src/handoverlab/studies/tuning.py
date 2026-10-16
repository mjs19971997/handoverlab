# SPDX-License-Identifier: MIT
"""Tuning of handover rules on an equal budget, the selection rule and the gates.

Every tuned method evaluates the same number of settings from its declared
grid (its *budget*): first ``random`` settings drawn without repetition with
a generator seeded by the method name, then settings one grid step around the
best of the first round, then two steps, and, if the neighbourhood is
exhausted, further random settings, until the budget is spent.  All settings
run on the tuning seeds, which never appear among the test seeds.

Selection rule (fixed before any result is seen)
    The failure budget is a share of the failure rate of a reference rule on
    the tuning runs.  Among the settings whose failure rate does not exceed
    the budget, those within ``tolerance`` (5 %) of the lowest
    unnecessary-handover rate count as equal; among them the lowest
    preparation overhead wins, then the lowest failure rate, then the lowest
    unnecessary-handover rate, then the order of evaluation.  If no setting
    meets the budget, the setting with the lowest failure rate is used and
    flagged.

Gates (checked after tuning, before any test run)
    ``grid_edge``       the selected value of a numeric parameter is the
                        smallest or largest of its grid, and that end is not
                        declared a natural bound;
    ``budget_binding``  more than ``binding_share`` of the settings of every
                        method meet the failure budget, or the reference rule
                        has fewer than ``min_reference_failures`` failures:
                        the budget does not constrain the trade-off;
    ``budget_met``      no setting of a method meets the budget;
    ``equal_budget``    methods evaluated different numbers of settings
                        (except where a grid is smaller than the budget);
    ``seed_overlap``    a tuning seed is also a test seed (checked before
                        anything runs);
    ``flat_optimum``    more than ``flat_share`` of the settings within the
                        budget lie within the tolerance of the best: the
                        choice is made by the tie-breaks.

Each gate has a policy: ``block`` (the study stops before the test stage
with a message that names the cause), ``warn`` (reported in the gate report
and in every table) or ``off``.  ``grid_edge`` also accepts ``extend``: the
grid of the parameter is widened at the offending end by ``extend_steps``
values with the spacing of the last two values (:func:`extension_values`),
the methods are tuned again with the same budget, and this repeats up to
``max_extensions`` times; each extension is recorded as a dated amendment.
If the cap is reached, or the grid cannot be widened (for example below
zero), the gate blocks.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence

GATES = ("grid_edge", "budget_binding", "budget_met", "equal_budget", "seed_overlap", "flat_optimum")
DEFAULT_POLICY = {"grid_edge": "block", "budget_binding": "warn", "budget_met": "warn", "equal_budget": "block",
                  "seed_overlap": "block", "flat_optimum": "warn"}
BOUNDS = ("lower", "upper", "both")
POLICIES = ("warn", "block", "off", "extend")       # "extend" only for grid_edge


def setting_key(cfg: Dict[str, Any]) -> str:
    """Canonical text of a setting (for duplicates and names)."""
    return json.dumps(cfg, sort_keys=True, separators=(",", ":"))


def grid_size(grid: Dict[str, Sequence]) -> int:
    n = 1
    for v in grid.values():
        n *= len(v)
    return n


def _moves(grid: Dict[str, Sequence], cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Settings one grid step away from ``cfg`` along one parameter."""
    out = []
    for k in sorted(grid):
        vals = list(grid[k])
        i = vals.index(cfg[k])
        for j in (i - 1, i + 1):
            if 0 <= j < len(vals):
                out.append(dict(cfg, **{k: vals[j]}))
    return out


def first_round(method: str, grid: Dict[str, Sequence], n: int) -> List[Dict[str, Any]]:
    """``n`` settings drawn at random from ``grid`` without repetition (seeded by the method name)."""
    rng = random.Random("round1-" + method)
    n = min(n, grid_size(grid))
    out, seen = [], set()
    names = sorted(grid)
    while len(out) < n:
        cfg = {k: rng.choice(list(grid[k])) for k in names}
        key = setting_key(cfg)
        if key not in seen:
            seen.add(key)
            out.append(cfg)
    return out


def refine(method: str, grid: Dict[str, Sequence], best: Dict[str, Any], taken: Sequence[Dict[str, Any]],
           n: int, tag: str = "") -> List[Dict[str, Any]]:
    """``n`` new settings: one grid step around ``best``, then two steps, then random ones.

    The random fill keeps the budget equal for every method when the
    neighbourhood of the best setting is smaller than ``n``.
    """
    rng = random.Random("round2-%s-%s" % (method, tag))
    seen = {setting_key(c) for c in taken}
    one = _moves(grid, best)
    rng.shuffle(one)
    two = [c2 for c in one for c2 in _moves(grid, c)]
    rng.shuffle(two)
    out: List[Dict[str, Any]] = []
    for c in one + two:
        if len(out) >= n:
            return out
        k = setting_key(c)
        if k not in seen:
            seen.add(k)
            out.append(c)
    n = min(n, grid_size(grid) - len(seen) + len(out))
    names = sorted(grid)
    while len(out) < n:
        cfg = {k: rng.choice(list(grid[k])) for k in names}
        k = setting_key(cfg)
        if k not in seen:
            seen.add(k)
            out.append(cfg)
    return out


@dataclass
class Selection:
    """Result of the selection rule for one method and budget."""
    index: int                    # index of the selected candidate
    met_budget: bool
    n_meeting: int                # candidates within the budget
    n_near: int                   # candidates within the tolerance of the best (among those meeting)


def select(cands: Sequence[Dict[str, float]], budget: float, tolerance: float = 0.05,
           objective: str = "unnecessary_pm", constraint: str = "failures_pm",
           tie_breaks: Sequence[str] = ("prepared_cells_mean", "failures_pm")) -> Selection:
    """Apply the selection rule to candidates with mean metrics (see the module text)."""
    if not cands:
        raise ValueError("no candidates to select from")
    ok = [i for i, c in enumerate(cands) if c[constraint] <= budget + 1e-12]
    if not ok:
        i = min(range(len(cands)), key=lambda i: (cands[i][constraint], cands[i][objective], i))
        return Selection(i, False, 0, 0)
    best = min(cands[i][objective] for i in ok)
    near = [i for i in ok if cands[i][objective] <= best * (1.0 + tolerance) + 1e-12]
    i = min(near, key=lambda i: tuple(round(cands[i][m], 9) for m in tie_breaks) + (cands[i][objective], i))
    return Selection(i, True, len(ok), len(near))


@dataclass
class GateResult:
    gate: str
    ok: bool
    policy: str
    message: str
    group: str = ""
    method: str = ""
    budget: str = ""
    edges: List[List[str]] = field(default_factory=list)     # grid_edge: [parameter, "lower" | "upper"]

    @property
    def blocking(self) -> bool:
        return (not self.ok) and self.policy in ("block", "extend")

    @property
    def status(self) -> str:
        if self.ok:
            return "pass"
        return {"block": "BLOCK", "extend": "EXTEND"}.get(self.policy, "warn")

    def as_dict(self) -> Dict[str, Any]:
        d = dict(gate=self.gate, status=self.status, policy=self.policy, group=self.group, method=self.method,
                 budget=self.budget, message=self.message)
        if self.edges:
            d["edges"] = [list(e) for e in self.edges]
        return d


@dataclass
class MethodTuning:
    """Everything that tuning found for one method in one group."""
    name: str
    grid: Dict[str, List[Any]]
    natural_bounds: Dict[str, str]
    budget_n: int                                   # declared number of settings
    candidates: List[Dict[str, Any]] = field(default_factory=list)   # setting + mean metrics
    selected: Dict[str, Selection] = field(default_factory=dict)     # per failure budget


def seed_overlap_gate(tuning_seeds: Sequence[int], test_seeds: Sequence[int], policy: str) -> GateResult:
    common = sorted(set(tuning_seeds) & set(test_seeds))
    if common:
        return GateResult("seed_overlap", False, policy, "tuning seeds also used as test seeds: %s"
                          % ", ".join(map(str, common[:10])) + (" ..." if len(common) > 10 else ""))
    return GateResult("seed_overlap", True, policy, "tuning and test seeds are disjoint (%d and %d seeds)"
                      % (len(set(tuning_seeds)), len(set(test_seeds))))


def evaluate_gates(group: str, methods: Sequence[MethodTuning], budgets: Dict[str, float], ref_failures: float,
                   policy: Dict[str, str], binding_share: float = 0.9, min_reference_failures: int = 5,
                   flat_share: float = 0.5, tolerance: float = 0.05, objective: str = "unnecessary_pm",
                   constraint: str = "failures_pm") -> List[GateResult]:
    """Gates ``grid_edge``, ``budget_binding``, ``budget_met``, ``equal_budget`` and ``flat_optimum`` of one group.

    ``ref_failures`` is the number of failures of the reference rule over all
    tuning runs of the group.
    """
    out: List[GateResult] = []

    def add(gate, ok, msg, method="", budget="", edges=None):
        if policy.get(gate, "warn") != "off":
            out.append(GateResult(gate, ok, policy.get(gate, "warn"), msg, group, method, budget, list(edges or [])))

    # equal budget
    declared = {m.name: m.budget_n for m in methods}
    counts = {m.name: len(m.candidates) for m in methods}
    want = {m.name: min(m.budget_n, grid_size(m.grid)) for m in methods}
    if len(set(declared.values())) > 1:
        add("equal_budget", False, "declared budgets differ: %s"
            % ", ".join("%s %d" % kv for kv in sorted(declared.items())))
    else:
        short = [n for n in counts if counts[n] != want[n]]
        add("equal_budget", not short,
            "evaluated settings: %s" % ", ".join("%s %d of %d" % (n, counts[n], want[n]) for n in sorted(counts))
            if short else "every method evaluated %s settings" % (
                "/".join(sorted({str(v) for v in counts.values()})) or "0"))
    for bname, bval in budgets.items():
        # budget binding: is the trade-off constrained at all?
        shares = {}
        for m in methods:
            if m.candidates:
                shares[m.name] = sum(c[constraint] <= bval + 1e-12 for c in m.candidates) / len(m.candidates)
        loose = shares and all(s > binding_share for s in shares.values())
        few = ref_failures < min_reference_failures
        msg = "reference failures %d (minimum %d); share of settings within the budget: %s" % (
            ref_failures, min_reference_failures, ", ".join("%s %.0f %%" % (n, 100 * s) for n, s in shares.items()))
        if few:
            msg = "the reference rule has only %d failures on the tuning runs (minimum %d); " % (
                ref_failures, min_reference_failures) + msg.split("; ", 1)[1]
        elif loose:
            msg = "more than %.0f %% of the settings of every method meet the budget: " % (100 * binding_share) + \
                  msg.split("; ", 1)[1]
        add("budget_binding", not (loose or few), msg, budget=bname)
        for m in methods:
            sel = m.selected.get(bname)
            if sel is None:
                continue
            c = m.candidates[sel.index]
            setting = c["setting"]
            # budget met
            add("budget_met", sel.met_budget,
                "%d of %d settings meet the budget %.4g" % (sel.n_meeting, len(m.candidates), bval) if sel.met_budget
                else "no setting meets the budget %.4g; the lowest failure rate (%.4g) is used"
                % (bval, c[constraint]), m.name, bname)
            # grid edge
            edges, where = [], []
            for p, vals in m.grid.items():
                if len(vals) < 2 or not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals):
                    continue
                nb = m.natural_bounds.get(p, "")
                v = setting[p]
                if v == min(vals) and nb not in ("lower", "both"):
                    edges.append("%s = %s is the smallest grid value" % (p, _fmt(v)))
                    where.append([p, "lower"])
                if v == max(vals) and nb not in ("upper", "both"):
                    edges.append("%s = %s is the largest grid value" % (p, _fmt(v)))
                    where.append([p, "upper"])
            add("grid_edge", not edges, "; ".join(edges) if edges else "selected setting inside the grid",
                m.name, bname, where)
            # flat optimum
            if sel.met_budget and sel.n_meeting:
                share = sel.n_near / sel.n_meeting
                add("flat_optimum", share <= flat_share,
                    "%d of %d settings within the budget lie within %.0f %% of the lowest %s" % (
                        sel.n_near, sel.n_meeting, 100 * tolerance, objective), m.name, bname)
    return out


def extension_values(values: Sequence[Any], side: str, steps: int) -> List[Any]:
    """``steps`` new grid values beyond the ``side`` end ("lower" or "upper") with the spacing of the last two.

    Integer grids stay integer; float values are rounded to 10 decimals.  A
    grid whose values are all non-negative is not extended below zero.
    """
    vals = sorted(values)
    if len(vals) < 2 or steps < 1:
        return []
    ints = all(isinstance(v, int) and not isinstance(v, bool) for v in vals)
    if side == "upper":
        step, start = vals[-1] - vals[-2], vals[-1]
    elif side == "lower":
        step, start = vals[0] - vals[1], vals[0]
    else:
        raise ValueError("side must be 'lower' or 'upper', got %r" % side)
    out = []
    for i in range(1, steps + 1):
        v = start + step * i
        v = int(v) if ints else round(float(v), 10)
        if side == "lower" and vals[0] >= 0 and v < 0:
            break
        out.append(v)
    return out


def _fmt(v: Any) -> str:
    if isinstance(v, float) and v == int(v):
        return "%g" % v
    return str(v)


def describe_setting(setting: Dict[str, Any]) -> str:
    return ", ".join("%s=%s" % (k, _fmt(v)) for k, v in sorted(setting.items()))


def summary_lines(gates: Sequence[GateResult]) -> List[str]:
    """Human-readable lines for the gates that did not pass."""
    lines = []
    for g in gates:
        if g.ok:
            continue
        where = ", ".join(x for x in (g.group, g.method, g.budget and "budget " + g.budget) if x)
        lines.append("%s %s%s: %s" % (g.status, g.gate, " (%s)" % where if where else "", g.message))
    return lines


__all__ = ["GATES", "DEFAULT_POLICY", "BOUNDS", "POLICIES", "extension_values", "setting_key", "grid_size",
           "first_round", "refine", "Selection",
           "select", "GateResult", "MethodTuning", "seed_overlap_gate", "evaluate_gates", "describe_setting",
           "summary_lines"]
