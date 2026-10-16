# SPDX-License-Identifier: MIT
"""Study files: conditions, seeds, methods with tuning grids, tuning, comparisons.

A study file (YAML, TOML or JSON) describes a whole comparison::

    name: a3-vs-cho
    scenario: {base: smoke}              # built-in name, {base: ..., ...} or a full scenario
    conditions:                          # full factorial over dotted scenario keys (optional)
      layout.site_spacing_m: [100.0, 150.0]
    seeds:
      tuning: [901, 902]                 # never used in a test
      test: {first: 1, last: 10}
    tuning:
      settings: 12                       # evaluated settings per method: the same for every method
      random: 8                          # of which drawn at random; the rest refine around the best
      reference: {rule: a3, name: A3-ref, off_db: 3.0, ttt_s: 0.16}
      budgets: {standard: 1.0, strict: 0.5}   # shares of the reference failure rate
      group_by: [layout.site_spacing_m]  # tune per value of these condition keys (default: all keys)
      gates: {grid_edge: block}          # warn | block | off per gate (grid_edge also: extend)
    methods:
      A3:
        rule: a3
        grid: {off_db: [0, 1, 2, 3, 4, 6, 8], ttt_s: [0.0, 0.04, 0.08, 0.16, 0.32]}
        natural_bounds: {ttt_s: lower}   # 0 s is a floor, not an edge of the search
      CHO:
        rule: cho
        fixed: {n_max: 4}
        grid: {o_exec_db: [0, 1, 2, 3, 4, 6], ttt_exec_s: [0.0, 0.04, 0.08, 0.16]}
    compare:
      baseline: A3-ref                   # a method, a tuned method as METHOD@BUDGET, or the reference
      metrics: [unnecessary_pm, failures_pm, handovers_pm]
    output: results/a3-vs-cho

A method without a ``grid`` is not tuned and runs as given.  Every key is
checked; an unknown key raises :class:`~handoverlab.config.ConfigError`.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from ..config import ConfigError, Scenario, read_file
from ..rules import get_rule_class
from .tuning import BOUNDS, DEFAULT_POLICY, GATES, POLICIES

_TOP = ("schema", "name", "description", "scenario", "conditions", "seeds", "tuning", "methods", "compare", "events",
        "output", "workers")
_TUNING = ("settings", "random", "reference", "budgets", "tolerance", "group_by", "gates", "binding_share",
           "min_reference_failures", "flat_share", "objective", "constraint", "tie_breaks", "extend_steps",
           "max_extensions")
_METHOD = ("rule", "grid", "fixed", "natural_bounds", "settings")
_COMPARE = ("baseline", "metrics", "level", "bootstrap", "budget")


@dataclass
class Method:
    name: str
    rule: str
    grid: Dict[str, List[Any]] = field(default_factory=dict)
    fixed: Dict[str, Any] = field(default_factory=dict)
    natural_bounds: Dict[str, str] = field(default_factory=dict)
    settings: Optional[int] = None                  # own budget (the equal-budget gate checks it)

    @property
    def tuned(self) -> bool:
        return bool(self.grid)

    def spec(self, setting: Optional[Dict[str, Any]] = None, name: Optional[str] = None) -> Dict[str, Any]:
        d = {"rule": self.rule, "name": name or self.name}
        d.update(self.fixed)
        if setting:
            d.update(setting)
        return d


@dataclass
class Tuning:
    settings: int = 12
    random: Optional[int] = None                    # default: two thirds of ``settings``
    reference: Dict[str, Any] = field(default_factory=lambda: {"rule": "a3", "name": "reference",
                                                               "off_db": 3.0, "ttt_s": 0.16})
    budgets: Dict[str, float] = field(default_factory=lambda: {"standard": 1.0})
    tolerance: float = 0.05
    group_by: Optional[List[str]] = None
    gates: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_POLICY))
    binding_share: float = 0.9
    min_reference_failures: int = 5
    flat_share: float = 0.5
    objective: str = "unnecessary_pm"
    constraint: str = "failures_pm"
    tie_breaks: Tuple[str, ...] = ("prepared_cells_mean", "failures_pm")
    extend_steps: int = 2                           # grid_edge: extend: values added per extension
    max_extensions: int = 2                         # grid_edge: extend: at most this many extension rounds

    @property
    def n_random(self) -> int:
        return self.random if self.random is not None else max(1, (2 * self.settings + 2) // 3)

    @property
    def reference_name(self) -> str:
        return str(self.reference.get("name", "reference"))


@dataclass
class Compare:
    baseline: Optional[str] = None
    metrics: Tuple[str, ...] = ("unnecessary_pm", "failures_pm", "handovers_pm", "prepared_cells_mean")
    level: float = 0.95
    bootstrap: int = 2000
    budget: Optional[str] = None                    # restrict the comparison to one budget


@dataclass
class Study:
    name: str
    scenario: Scenario
    conditions: Dict[str, List[Any]]
    tuning_seeds: Tuple[int, ...]
    test_seeds: Tuple[int, ...]
    methods: List[Method]
    tuning: Tuning
    compare: Compare
    events: str = "off"                             # event-log level of the test stage
    output: Optional[str] = None
    workers: Optional[int] = None
    description: str = ""
    source: Dict[str, Any] = field(default_factory=dict)

    # ---------------------------------------------------------------- derived
    @property
    def tuned_methods(self) -> List[Method]:
        return [m for m in self.methods if m.tuned]

    @property
    def has_tuning(self) -> bool:
        return bool(self.tuned_methods)

    def condition_list(self) -> List[Dict[str, Any]]:
        """All conditions of the full factorial (one empty condition without ``conditions``)."""
        keys = list(self.conditions)
        return [dict(zip(keys, vals)) for vals in itertools.product(*(self.conditions[k] for k in keys))]

    def group_keys(self) -> List[str]:
        gb = self.tuning.group_by
        return list(self.conditions) if gb is None else list(gb)

    def group_of(self, cond: Dict[str, Any]) -> str:
        return label({k: cond[k] for k in self.group_keys()})

    def scenario_for(self, cond: Dict[str, Any]) -> Scenario:
        return self.scenario.with_overrides(cond) if cond else self.scenario

    def budget_names(self) -> List[str]:
        return list(self.tuning.budgets)

    def test_rule_names(self) -> List[str]:
        names = []
        if self.has_tuning:
            names.append(self.tuning.reference_name)
        for m in self.methods:
            if m.tuned:
                names.extend("%s@%s" % (m.name, b) for b in self.budget_names())
            else:
                names.append(m.name)
        return names

    def baseline(self) -> str:
        if self.compare.baseline:
            return self.compare.baseline
        return self.test_rule_names()[0]

    def resolved(self) -> Dict[str, Any]:
        """The study with every value explicit (written to ``study.lock.json``)."""
        t = self.tuning
        return dict(
            name=self.name, description=self.description, scenario=self.scenario.to_dict(),
            conditions=self.conditions, seeds=dict(tuning=list(self.tuning_seeds), test=list(self.test_seeds)),
            tuning=dict(settings=t.settings, random=t.n_random, reference=t.reference, budgets=t.budgets,
                        tolerance=t.tolerance, group_by=self.group_keys(), gates=t.gates,
                        binding_share=t.binding_share, min_reference_failures=t.min_reference_failures,
                        flat_share=t.flat_share, objective=t.objective, constraint=t.constraint,
                        tie_breaks=list(t.tie_breaks), extend_steps=t.extend_steps,
                        max_extensions=t.max_extensions),
            methods={m.name: dict(rule=m.rule, grid=m.grid, fixed=m.fixed, natural_bounds=m.natural_bounds,
                                  settings=m.settings if m.settings is not None else t.settings)
                     for m in self.methods},
            compare=dict(baseline=self.baseline(), metrics=list(self.compare.metrics), level=self.compare.level,
                         bootstrap=self.compare.bootstrap, budget=self.compare.budget),
            events=self.events)

    def lock_hash(self) -> str:
        return hashlib.sha256(canonical(self.resolved()).encode()).hexdigest()


def canonical(obj: Any) -> str:
    """Canonical JSON text (sorted keys, no spaces) used for content hashes."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=float)


def label(cond: Dict[str, Any]) -> str:
    """Short text of a condition, such as ``layout.site_spacing_m=100``; ``all`` for none."""
    if not cond:
        return "all"
    return ",".join("%s=%s" % (k, _short(v)) for k, v in cond.items())


def _short(v: Any) -> str:
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    return str(v)


# ---------------------------------------------------------------------------- parsing
def _check_keys(d: Dict[str, Any], allowed: Sequence[str], where: str) -> None:
    for k in d:
        if k not in allowed:
            raise ConfigError("unknown key '%s%s'; allowed: %s" % (where, k, ", ".join(allowed)))


def _seed_list(v: Any, where: str) -> Tuple[int, ...]:
    if isinstance(v, int) and not isinstance(v, bool):
        v = [v]
    if isinstance(v, dict):
        _check_keys(v, ("first", "last"), where + ".")
        try:
            v = list(range(int(v["first"]), int(v["last"]) + 1))
        except KeyError as e:
            raise ConfigError("%s: needs 'first' and 'last' (missing %s)" % (where, e))
    if not isinstance(v, (list, tuple)) or not v or not all(
            isinstance(s, int) and not isinstance(s, bool) and s >= 0 for s in v):
        raise ConfigError("%s: expected a list of non-negative integers or {first, last}" % where)
    if len(set(v)) != len(v):
        raise ConfigError("%s: seeds must not repeat" % where)
    return tuple(int(s) for s in v)


def _number(v: Any, where: str, lo: Optional[float] = None, hi: Optional[float] = None) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ConfigError("%s: expected a number, got %r" % (where, v))
    if (lo is not None and v < lo) or (hi is not None and v > hi):
        raise ConfigError("%s: must be in [%s, %s]" % (where, lo, hi))
    return float(v)


def _int(v: Any, where: str, lo: int = 0) -> int:
    if isinstance(v, bool) or not isinstance(v, int) or v < lo:
        raise ConfigError("%s: expected an integer >= %d, got %r" % (where, lo, v))
    return int(v)


def _rule_params(rule: str, where: str) -> List[str]:
    import inspect
    try:
        cls = get_rule_class(rule)
    except KeyError as e:
        raise ConfigError("%s: %s" % (where, e.args[0]))
    return [p for p in inspect.signature(cls.__init__).parameters if p not in ("self", "name")]


def _method(name: str, d: Any, where: str) -> Method:
    if not isinstance(d, dict) or "rule" not in d:
        raise ConfigError("%s: expected a mapping with a 'rule' key" % where)
    _check_keys(d, _METHOD, where + ".")
    allowed = _rule_params(d["rule"], where + ".rule")
    grid = d.get("grid") or {}
    fixed = d.get("fixed") or {}
    for part, values in (("grid", grid), ("fixed", fixed)):
        if not isinstance(values, dict):
            raise ConfigError("%s.%s: expected a mapping" % (where, part))
        for p in values:
            if p not in allowed:
                raise ConfigError("unknown key '%s.%s.%s'; parameters of rule %r: %s"
                                  % (where, part, p, d["rule"], ", ".join(allowed)))
    both = set(grid) & set(fixed)
    if both:
        raise ConfigError("%s: parameter %s is both in 'grid' and in 'fixed'" % (where, sorted(both)[0]))
    clean = {}
    for p, vals in grid.items():
        if not isinstance(vals, (list, tuple)) or not vals:
            raise ConfigError("%s.grid.%s: expected a non-empty list of values" % (where, p))
        vals = list(vals)
        if len(set(map(repr, vals))) != len(vals):
            raise ConfigError("%s.grid.%s: values must not repeat" % (where, p))
        if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals):
            vals = sorted(vals)
        clean[p] = vals
    nb = d.get("natural_bounds") or {}
    if not isinstance(nb, dict):
        raise ConfigError("%s.natural_bounds: expected a mapping" % where)
    for p, b in nb.items():
        if p not in clean:
            raise ConfigError("%s.natural_bounds.%s: not a grid parameter" % (where, p))
        if b not in BOUNDS:
            raise ConfigError("%s.natural_bounds.%s: must be one of %s" % (where, p, ", ".join(BOUNDS)))
    settings = d.get("settings")
    if settings is not None:
        settings = _int(settings, where + ".settings", 1)
    return Method(name, str(d["rule"]), clean, dict(fixed), dict(nb), settings)


def _metric(name: Any, where: str) -> str:
    """Current name of a metric (an old name warns); an unknown name raises ConfigError."""
    from ..stability import metric_name
    try:
        return metric_name(name)
    except (KeyError, TypeError):
        raise ConfigError("%s: unknown metric %r" % (where, name)) from None


def study_from_dict(data: Dict[str, Any], base_dir: str = ".") -> Study:
    """Study from a dictionary (see the module text)."""
    if not isinstance(data, dict):
        raise ConfigError("a study file must be a mapping")
    _check_keys(data, _TOP, "")
    from ..stability import check_schema
    check_schema(data.get("schema"), "study")
    name = str(data.get("name") or "study")
    sc = Scenario.from_dict(data.get("scenario") or {})
    conds = data.get("conditions") or {}
    if not isinstance(conds, dict):
        raise ConfigError("conditions: expected a mapping of dotted scenario keys to lists of values")
    conditions: Dict[str, List[Any]] = {}
    for k, vals in conds.items():
        if not isinstance(vals, (list, tuple)) or not vals:
            raise ConfigError("conditions.%s: expected a non-empty list of values" % k)
        for v in vals:
            sc.with_overrides({k: v})            # checks the key and the value
        conditions[str(k)] = list(vals)
    seeds = data.get("seeds")
    if not isinstance(seeds, dict) or "test" not in seeds:
        raise ConfigError("seeds: expected {tuning: [...], test: [...]} (tuning seeds are needed only for tuning)")
    _check_keys(seeds, ("tuning", "test"), "seeds.")
    test = _seed_list(seeds["test"], "seeds.test")
    tun_seeds = _seed_list(seeds["tuning"], "seeds.tuning") if seeds.get("tuning") is not None else ()
    methods_d = data.get("methods")
    if not isinstance(methods_d, dict) or not methods_d:
        raise ConfigError("methods: expected a mapping of method names to {rule, grid, fixed, ...}")
    methods = []
    for mname, md in methods_d.items():
        if "@" in str(mname):
            raise ConfigError("methods.%s: a method name must not contain '@'" % mname)
        methods.append(_method(str(mname), md, "methods.%s" % mname))
    td = data.get("tuning") or {}
    if not isinstance(td, dict):
        raise ConfigError("tuning: expected a mapping")
    _check_keys(td, _TUNING, "tuning.")
    t = Tuning()
    if "settings" in td:
        t.settings = _int(td["settings"], "tuning.settings", 1)
    if td.get("random") is not None:
        t.random = _int(td["random"], "tuning.random", 1)
        if t.random > t.settings:
            raise ConfigError("tuning.random: must not exceed tuning.settings")
    if "reference" in td:
        ref = td["reference"]
        if not isinstance(ref, dict) or "rule" not in ref:
            raise ConfigError("tuning.reference: expected a rule mapping with a 'rule' key")
        allowed = _rule_params(ref["rule"], "tuning.reference.rule")
        for p in ref:
            if p not in allowed + ["rule", "name"]:
                raise ConfigError("unknown key 'tuning.reference.%s'; parameters: %s" % (p, ", ".join(allowed)))
        t.reference = dict(ref)
        t.reference.setdefault("name", "reference")
    if "budgets" in td:
        b = td["budgets"]
        if not isinstance(b, dict) or not b:
            raise ConfigError("tuning.budgets: expected a mapping such as {standard: 1.0, strict: 0.5}")
        t.budgets = {str(k): _number(v, "tuning.budgets.%s" % k, 0.0) for k, v in b.items()}
    if "tolerance" in td:
        t.tolerance = _number(td["tolerance"], "tuning.tolerance", 0.0, 1.0)
    if "group_by" in td:
        gb = td["group_by"]
        if not isinstance(gb, (list, tuple)) or any(k not in conditions for k in gb):
            raise ConfigError("tuning.group_by: expected a list of keys of 'conditions' (%s)"
                              % ", ".join(conditions) if conditions else "tuning.group_by: there are no conditions")
        t.group_by = list(gb)
    if "gates" in td:
        g = td["gates"]
        if not isinstance(g, dict):
            raise ConfigError("tuning.gates: expected a mapping of gate names to warn, block or off")
        for k, v in g.items():
            if k not in GATES:
                raise ConfigError("unknown key 'tuning.gates.%s'; gates: %s" % (k, ", ".join(GATES)))
            if v == "extend" and k != "grid_edge":
                raise ConfigError("tuning.gates.%s: 'extend' is a policy of grid_edge only" % k)
            if v not in POLICIES:
                raise ConfigError("tuning.gates.%s: must be warn, block or off%s"
                                  % (k, " (or extend)" if k == "grid_edge" else ""))
            t.gates[k] = v
    if "extend_steps" in td:
        t.extend_steps = _int(td["extend_steps"], "tuning.extend_steps", 1)
    if "max_extensions" in td:
        t.max_extensions = _int(td["max_extensions"], "tuning.max_extensions", 0)
    if "binding_share" in td:
        t.binding_share = _number(td["binding_share"], "tuning.binding_share", 0.0, 1.0)
    if "min_reference_failures" in td:
        t.min_reference_failures = _int(td["min_reference_failures"], "tuning.min_reference_failures")
    if "flat_share" in td:
        t.flat_share = _number(td["flat_share"], "tuning.flat_share", 0.0, 1.0)
    for key in ("objective", "constraint"):
        if key in td:
            setattr(t, key, _metric(td[key], "tuning." + key))
    if "tie_breaks" in td:
        tb = td["tie_breaks"]
        if not isinstance(tb, (list, tuple)):
            raise ConfigError("tuning.tie_breaks: expected a list of metric names")
        t.tie_breaks = tuple(_metric(m, "tuning.tie_breaks") for m in tb)
    tuned = [m for m in methods if m.tuned]
    if tuned and not tun_seeds:
        raise ConfigError("seeds.tuning: methods with a grid need tuning seeds")
    cd = data.get("compare") or {}
    if not isinstance(cd, dict):
        raise ConfigError("compare: expected a mapping")
    _check_keys(cd, _COMPARE, "compare.")
    c = Compare()
    if cd.get("metrics") is not None:
        ms = cd["metrics"]
        if not isinstance(ms, (list, tuple)) or not ms:
            raise ConfigError("compare.metrics: expected a non-empty list of metric names, got %r" % (ms,))
        c.metrics = tuple(_metric(m, "compare.metrics") for m in ms)
    if "level" in cd:
        c.level = _number(cd["level"], "compare.level", 0.5, 0.999)
    if "bootstrap" in cd:
        c.bootstrap = _int(cd["bootstrap"], "compare.bootstrap")
    if cd.get("budget") is not None:
        if cd["budget"] not in t.budgets:
            raise ConfigError("compare.budget: not one of the tuning budgets (%s)" % ", ".join(t.budgets))
        c.budget = str(cd["budget"])
    from ..eventlog import event_level
    try:
        events = event_level(data.get("events", False))
    except ValueError as e:
        raise ConfigError("events: %s" % e)
    st = Study(name, sc, conditions, tun_seeds, test, methods, t, c, events,
               data.get("output"), None, str(data.get("description") or ""), dict(data))
    if data.get("workers") is not None:
        st.workers = _int(data["workers"], "workers", 1)
    names = st.test_rule_names()
    if len(set(names)) != len(names):
        raise ConfigError("rule names in the test stage repeat (%s); rename a method or the reference"
                          % ", ".join(names))
    if cd.get("baseline") is not None:
        if cd["baseline"] not in names:
            raise ConfigError("compare.baseline: %r is not a rule of the test stage (%s)"
                              % (cd["baseline"], ", ".join(names)))
        c.baseline = str(cd["baseline"])
    if st.output and not os.path.isabs(st.output):
        st.output = st.output                    # relative to the working directory, like 'run'
    return st


def load_study(source: Union[str, os.PathLike, Dict[str, Any]]) -> Study:
    """Study from a YAML, TOML or JSON file, or from a dictionary."""
    if isinstance(source, dict):
        return study_from_dict(source)
    data = read_file(source)
    st = study_from_dict(data, os.path.dirname(os.path.abspath(os.fspath(source))))
    if not data.get("name"):
        st.name = os.path.splitext(os.path.basename(os.fspath(source)))[0]
    return st
