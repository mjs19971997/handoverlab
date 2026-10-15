# SPDX-License-Identifier: MIT
"""Non-visual logic of the dashboard: settings -> configuration, runs, map frames, figures, downloads.

Everything here works without Streamlit (it needs NumPy and, for figures,
matplotlib), so it can be tested and reused in scripts and notebooks::

    from handoverlab.gui import logic
    s = logic.Settings(layout="street_grid", users=20, profile="veh16")
    out = logic.run(s, [logic.RuleSettings("a3"), logic.RuleSettings("cho")])
    fig = logic.map_figure(out, rule=0, frame=10)
    open("metrics.csv", "wb").write(logic.metrics_csv(out))
"""
from __future__ import annotations

import csv
import io
import json
import platform
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

import numpy as np

from .. import __version__
from ..config import Scenario
from ..eventlog import serving_cells, write_events, write_trace
from ..simulate import RunResult, run_world
from ..world import build_world

#: speed profiles offered in the dashboard (key -> label)
PROFILES = {
    "ped": "pedestrians, 1.2-1.8 m/s",
    "veh8": "vehicles, 7.2-8.8 m/s (about 30 km/h)",
    "veh16": "vehicles, 14.4-17.6 m/s (about 60 km/h)",
    "veh30": "vehicles, 27-33 m/s (about 110 km/h)",
    "mix": "40 % pedestrians, 30 % at 8 m/s, 30 % at 16 m/s",
    "c8": "constant 8 m/s on the centre lines",
    "c16": "constant 16 m/s on the centre lines",
    "c30": "constant 30 m/s on the centre lines",
}
LAYOUTS = {"street_grid": "street grid (TR 37.885)", "open_area": "open area (hexagonal sites)"}
PATHLOSS = {"umi_street_canyon": "UMi street canyon", "uma": "UMa"}
FREQUENCIES = (3.5, 7.0, 10.0, 15.0, 28.0)
RULES = {"a3": "Event A3 (baseline handover)", "cho": "conditional handover"}
#: metrics shown in the charts and the table (key -> label)
CHART_METRICS = {
    "handovers_pm": "handovers per UE-minute",
    "unnecessary_pm": "unnecessary handovers per UE-minute",
    "failures_pm": "failures per UE-minute",
    "rate_mbps": "delivered rate [Mbit/s]",
}
TABLE_METRICS = ("handovers_pm", "unnecessary_pm", "pingpong_pm", "too_late_pm", "too_early_pm", "failures_pm",
                 "prepared_cells_mean", "interruption_s_pm", "outage_pct", "sinr_db", "rate_mbps")
FAILURE_CAUSES = ("command_lost", "rlf_in_preparation", "rlf_without_handover", "coverage_rlf", "execution_failure",
                  "rlf_after_handover")


@dataclass
class Settings:
    """Scenario settings as chosen in the dashboard (defaults: a quick street-grid run)."""
    layout: str = "street_grid"
    blocks: int = 2                       # blocks per side of the grid
    site_spacing_m: float = 150.0
    carrier_ghz: float = 10.0
    pathloss: str = "umi_street_canyon"
    users: int = 20
    profile: str = "veh16"
    duration_s: float = 40.0
    warmup_s: float = 10.0
    seeds: int = 1
    first_seed: int = 1

    def check(self) -> List[str]:
        """Problems with these settings (empty if none)."""
        p = []
        if self.layout not in LAYOUTS:
            p.append("unknown layout %r" % self.layout)
        if self.profile not in PROFILES:
            p.append("unknown speed profile %r" % self.profile)
        if self.pathloss not in PATHLOSS:
            p.append("unknown path-loss model %r" % self.pathloss)
        if not 1 <= self.blocks <= 4:
            p.append("blocks must be 1 to 4")
        if self.warmup_s >= self.duration_s:
            p.append("the warm-up must be shorter than the run")
        if self.users < 1 or self.seeds < 1:
            p.append("at least one user and one seed")
        return p


@dataclass
class RuleSettings:
    """One handover rule as chosen in the dashboard; ``params`` override the rule's defaults."""
    rule: str = "a3"
    name: str = ""
    params: Dict[str, Any] = field(default_factory=dict)

    def spec(self) -> Dict[str, Any]:
        d = {"rule": self.rule, "name": self.name or self.rule.upper()}
        d.update(self.params)
        return d


#: parameters offered per rule: name -> (label, min, max, step, default)
RULE_PARAMS = {
    "a3": {"off_db": ("A3 offset [dB]", 0.0, 10.0, 0.5, 3.0),
           "ttt_s": ("time-to-trigger [s]", 0.0, 1.28, 0.04, 0.16)},
    "cho": {"o_prep_db": ("preparation offset [dB]", -6.0, 6.0, 0.5, -2.0),
            "o_exec_db": ("execution offset [dB]", 0.0, 10.0, 0.5, 3.0),
            "ttt_exec_s": ("execution time-to-trigger [s]", 0.0, 0.64, 0.04, 0.08),
            "n_max": ("prepared cells at most", 1, 8, 1, 4)},
}


def scenario_dict(s: Settings) -> Dict[str, Any]:
    """Scenario dictionary (as in a configuration file) for dashboard settings."""
    return {
        "name": "dashboard-%s" % s.layout.replace("_", "-"),
        "layout": {"kind": s.layout, "blocks": [int(s.blocks), int(s.blocks)],
                   "site_spacing_m": float(s.site_spacing_m)},
        "radio": {"carrier_ghz": float(s.carrier_ghz), "pathloss": s.pathloss,
                  "map_res_m": 2.0 if s.blocks >= 3 else 1.0},
        "mobility": {"users": int(s.users), "profile": s.profile},
        "run": {"duration_s": float(s.duration_s), "warmup_s": float(s.warmup_s)},
    }


def make_scenario(s: Settings) -> Scenario:
    probs = s.check()
    if probs:
        raise ValueError("; ".join(probs))
    return Scenario.from_dict(scenario_dict(s))


def rule_specs(rules: Sequence[RuleSettings]) -> List[Dict[str, Any]]:
    """Rule specifications with unique names (a number is appended to repeated names)."""
    out, seen = [], {}
    for r in rules:
        d = r.spec()
        n = d["name"]
        seen[n] = seen.get(n, 0) + 1
        if seen[n] > 1:
            d["name"] = "%s-%d" % (n, seen[n])
        out.append(d)
    if not out:
        raise ValueError("choose at least one rule")
    return out


def seeds_of(s: Settings) -> List[int]:
    return list(range(int(s.first_seed), int(s.first_seed) + int(s.seeds)))


def experiment_dict(s: Settings, rules: Sequence[RuleSettings]) -> Dict[str, Any]:
    """An experiment configuration that ``handoverlab run`` repeats exactly."""
    return {"scenario": scenario_dict(s), "seeds": seeds_of(s), "rules": rule_specs(rules),
            "output": "results/dashboard.csv"}


def experiment_yaml(s: Settings, rules: Sequence[RuleSettings]) -> str:
    import yaml
    return ("# HandoverLab experiment written by the dashboard; repeat it with: handoverlab run dashboard.yaml\n"
            + yaml.safe_dump(experiment_dict(s, rules), sort_keys=False, width=100))


# ---------------------------------------------------------------------------- runs
@dataclass
class Outcome:
    """Results of a dashboard run: every rule on every seed, and the map data of the first seed."""
    settings: Settings
    rules: List[Dict[str, Any]]
    results: List[RunResult]
    times: np.ndarray                      # frame times [s]
    x: np.ndarray                          # (F, U) positions at the frame times
    y: np.ndarray
    serving: np.ndarray                    # (K, F, U) serving cell per rule, -1 = not connected
    sites: np.ndarray                      # (M, 2)
    buildings: np.ndarray                  # (B, 4) x0, y0, x1, y1
    extent: tuple                          # (xmin, xmax, ymin, ymax)
    seconds: float = 0.0

    @property
    def rule_names(self) -> List[str]:
        return [r["name"] for r in self.rules]


def run(s: Settings, rules: Sequence[RuleSettings], frame_s: float = 0.5,
        progress: Optional[Callable[[float, str], None]] = None) -> Outcome:
    """Run every rule on every seed (the first seed with the full event-log level for the map).

    ``progress(share, text)`` is called while the run proceeds (share from 0 to 1).
    """
    import time
    t0 = time.perf_counter()
    sc = make_scenario(s)
    specs = rule_specs(rules)
    seeds = seeds_of(s)
    say = progress or (lambda share, text: None)
    results: List[RunResult] = []
    first = None
    for i, seed in enumerate(seeds):
        say(i / len(seeds), "seed %d: building the world" % seed)
        world = build_world(sc, seed)
        say((i + 0.1) / len(seeds), "seed %d: running %d rule(s)" % (seed, len(specs)))
        res = run_world(world, specs, log_events="full" if i == 0 else "summary",
                        progress=lambda f, i=i, seed=seed: say((i + 0.1 + 0.9 * f) / len(seeds),
                                                               "seed %d: %.0f %% simulated" % (seed, 100 * f)))
        if i == 0:
            first = (world, res)
        results.extend(res)
    say(1.0, "done")
    world, res0 = first
    dt = world.scenario.protocol.step_s
    times = np.arange(0.0, world.n_steps * dt, frame_s)
    k = np.minimum(np.round(times / dt).astype(int), world.n_steps - 1)
    serving = np.stack([serving_cells(r.trace, world.n_users, times) for r in res0])
    lay = world.layout
    return Outcome(s, specs, results, times, world.x[k], world.y[k], serving, np.asarray(lay.sites, dtype=float),
                   np.asarray(lay.buildings, dtype=float).reshape(-1, 4), (lay.xmin, lay.xmax, lay.ymin, lay.ymax),
                   time.perf_counter() - t0)


def counts_until(out: Outcome, rule: int, t: float) -> Dict[str, int]:
    """What happened to the users of the first seed up to time ``t`` under one rule (warm-up included)."""
    name = out.rule_names[rule]
    r = next(x for x in out.results if x.rule == name and x.seed == int(out.settings.first_seed))
    f = int(np.clip(np.searchsorted(out.times, t + 1e-9) - 1, 0, len(out.times) - 1))
    trace = [e for e in r.trace if e["t"] <= t + 1e-9]
    return {"handovers": sum(e["event"] == "attach" for e in trace),
            "failures": sum(e["event"] == "failure" for e in trace),
            "re-establishments": sum(e["event"] == "reestablish" for e in trace),
            "users connected now": int((out.serving[rule, f] >= 0).sum()),
            "cells serving now": int(len(set(out.serving[rule, f][out.serving[rule, f] >= 0].tolist())))}


def summary_rows(out: Outcome) -> List[Dict[str, Any]]:
    """Mean of every table metric per rule over the seeds (with the number of seeds)."""
    rows = []
    for name in out.rule_names:
        rs = [r for r in out.results if r.rule == name]
        row: Dict[str, Any] = {"rule": name, "seeds": len(rs)}
        for m in TABLE_METRICS:
            row[m] = float(np.mean([r.metrics[m] for r in rs]))
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------- figures
def _mpl():
    from ..studies.report import GRID, MUTED, SERIES, SURFACE, TEXT, TEXT2, _figure, _style
    return dict(GRID=GRID, MUTED=MUTED, SERIES=SERIES, SURFACE=SURFACE, TEXT=TEXT, TEXT2=TEXT2, figure=_figure,
                style=_style)


def cell_colours(sites: np.ndarray, n_colours: int = 8) -> List[int]:
    """Colour slot of every cell such that near cells get different slots (greedy, nearest first).

    With more cells than colours a slot repeats only between cells that are
    far apart; the map also draws a line from every user to its serving site
    and labels the sites, so identity never rests on colour alone.
    """
    m = len(sites)
    d = np.hypot(sites[:, None, 0] - sites[None, :, 0], sites[:, None, 1] - sites[None, :, 1])
    slot = [-1] * m
    for i in range(m):
        order = np.argsort(d[i])
        taken = [slot[j] for j in order if slot[j] >= 0][:n_colours - 1]
        free = [c for c in range(n_colours) if c not in taken]
        slot[i] = free[0] if free else int(np.argmax([taken[::-1].index(c) if c in taken else 99
                                                     for c in range(n_colours)]))
    return slot


def map_figure(out: Outcome, rule: int = 0, frame: int = 0, tail: int = 6):
    """Users on the layout at one frame, coloured by serving cell (grey: executing or re-establishing)."""
    st = _mpl()
    S = st["SERIES"]
    fig = st["figure"](7.2, 7.2 * (out.extent[3] - out.extent[2]) / max(out.extent[1] - out.extent[0], 1) + 0.6)
    ax = fig.add_subplot(1, 1, 1)
    st["style"](ax)
    ax.grid(False)
    from matplotlib.patches import Rectangle
    for x0, y0, x1, y1 in out.buildings:
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor="#e9e8e4", edgecolor="none", zorder=0))
    slots = cell_colours(out.sites, len(S))
    f = int(np.clip(frame, 0, len(out.times) - 1))
    serv = out.serving[rule, f]
    x, y = out.x[f], out.y[f]
    f0 = max(0, f - tail)
    for u in range(x.shape[0]):
        ax.plot(out.x[f0:f + 1, u], out.y[f0:f + 1, u], color=st["MUTED"], linewidth=0.8, zorder=1)
        c = serv[u]
        if c >= 0:
            ax.plot([x[u], out.sites[c, 0]], [y[u], out.sites[c, 1]], color=S[slots[c]], linewidth=0.9, alpha=0.7,
                    zorder=2)
    for j, (sx, sy) in enumerate(out.sites):
        ax.scatter([sx], [sy], marker="^", s=46, color=S[slots[j]], edgecolors=st["SURFACE"], linewidths=1.0,
                   zorder=3)
        if len(out.sites) <= 40:
            ax.annotate(str(j), (sx, sy), xytext=(3, 3), textcoords="offset points", fontsize=6, color=st["TEXT2"])
    con = serv >= 0
    cols = [S[slots[c]] for c in serv[con]]
    ax.scatter(x[con], y[con], s=42, c=cols, edgecolors=st["SURFACE"], linewidths=1.6, zorder=4)
    ax.scatter(x[~con], y[~con], s=42, color=st["MUTED"], edgecolors=st["TEXT2"], linewidths=1.0, zorder=4,
               label="not connected")
    pad = 0.03 * max(out.extent[1] - out.extent[0], out.extent[3] - out.extent[2])
    ax.set_xlim(out.extent[0] - pad, out.extent[1] + pad)
    ax.set_ylim(out.extent[2] - pad, out.extent[3] + pad)
    ax.set_aspect("equal")
    ax.set_xlabel("x [m]", fontsize=8)
    ax.set_ylabel("y [m]", fontsize=8)
    ax.set_title("%s, t = %.1f s" % (out.rule_names[rule], out.times[f]), fontsize=9, loc="left", color=st["TEXT"],
                 pad=8)
    return fig


def metrics_figure(out: Outcome, metrics: Sequence[str] = tuple(CHART_METRICS)):
    """One small panel per metric: mean per rule over the seeds, with the range of the seeds."""
    st = _mpl()
    S = st["SERIES"]
    names = out.rule_names
    n = len(metrics)
    fig = st["figure"](2.6 * n + 0.4, 2.9)
    for i, m in enumerate(metrics):
        ax = fig.add_subplot(1, n, i + 1)
        st["style"](ax)
        ax.grid(False, axis="x")
        for k, name in enumerate(names):
            v = np.array([r.metrics[m] for r in out.results if r.rule == name])
            ax.bar([k], [v.mean()], width=0.6, color=S[k % len(S)], edgecolor=st["SURFACE"], linewidth=2)
            if len(v) > 1:
                ax.plot([k, k], [v.min(), v.max()], color=st["TEXT2"], linewidth=1.2)
            ax.annotate("%.3g" % v.mean(), (k, v.mean()), xytext=(0, 2), textcoords="offset points", ha="center",
                        va="bottom", fontsize=7, color=st["TEXT2"])
        ax.set_ylim(bottom=0, top=max(ax.get_ylim()[1], 1e-3))
        ax.set_xticks(range(len(names)))
        ax.set_xticklabels(names, fontsize=7, color=st["TEXT"], rotation=20 if len(names) > 2 else 0)
        ax.set_title(CHART_METRICS.get(m, m), fontsize=8, loc="left", color=st["TEXT"])
    fig.text(0.01, 1.0, "Mean over %d seed(s)%s" % (out.settings.seeds, "; lines: range over the seeds"
                                                     if out.settings.seeds > 1 else ""),
             fontsize=8, color=st["TEXT2"], va="bottom")
    fig.tight_layout()
    return fig


def causes_figure(out: Outcome):
    """Failures per UE-minute by cause, one row per rule (mean over the seeds)."""
    st = _mpl()
    S = st["SERIES"]
    names = out.rule_names
    fig = st["figure"](7.2, 0.5 * len(names) + 1.6)
    ax = fig.add_subplot(1, 1, 1)
    st["style"](ax)
    ax.grid(False, axis="y")
    ys = np.arange(len(names))[::-1]
    shown = set()
    for y, name in zip(ys, names):
        left = 0.0
        rs = [r for r in out.results if r.rule == name]
        for j, c in enumerate(FAILURE_CAUSES):
            v = float(np.mean([r.metrics.get("fail_%s_pm" % c, 0.0) for r in rs]))
            if v > 0:
                ax.barh([y], [v], left=left, height=0.55, color=S[j], edgecolor=st["SURFACE"], linewidth=2,
                        label=None if c in shown else c.replace("_", " "))
                shown.add(c)
            left += v
    ax.set_yticks(ys)
    ax.set_yticklabels(names, fontsize=8, color=st["TEXT"])
    ax.set_xlabel("failures per UE-minute", fontsize=8)
    h, lab = ax.get_legend_handles_labels()
    uniq = dict(zip(lab, h))
    if uniq:
        ax.legend(uniq.values(), uniq.keys(), fontsize=7, frameon=False, loc="lower right", labelcolor=st["TEXT2"])
    else:
        ax.text(0.5, 0.5, "no failures", transform=ax.transAxes, ha="center", color=st["TEXT2"], fontsize=9)
    ax.set_title("Failures by cause", fontsize=8, loc="left", color=st["TEXT"])
    fig.tight_layout()
    return fig


def timeline_figure(out: Outcome):
    """Cumulative handovers and failures over time on the first seed, one line per rule (two panels)."""
    st = _mpl()
    S = st["SERIES"]
    seed = int(out.settings.first_seed)
    fig = st["figure"](7.2, 2.8)
    axes = [fig.add_subplot(1, 2, i + 1) for i in range(2)]
    for k, name in enumerate(out.rule_names):
        r = next(r for r in out.results if r.rule == name and r.seed == seed)
        ho = [e["t"] for e in r.trace if e["event"] == "attach"]
        fl = [e["t"] for e in r.trace if e["event"] == "failure"]
        for ax, ts in zip(axes, (ho, fl)):
            ax.step([0.0] + ts + [out.times[-1]], list(range(len(ts) + 1)) + [len(ts)], where="post",
                    color=S[k % len(S)], linewidth=2, label=name)
    for ax, t in zip(axes, ("handovers (cumulative)", "failures (cumulative)")):
        st["style"](ax)
        ax.set_title("%s, seed %d" % (t, seed), fontsize=8, loc="left", color=st["TEXT"])
        ax.set_xlabel("time [s]", fontsize=8)
        ax.axvline(out.settings.warmup_s, color=st["TEXT2"], linewidth=0.8, linestyle=(0, (4, 3)))
        ax.set_ylim(bottom=0, top=max(1.0, ax.get_ylim()[1]))
    axes[0].legend(fontsize=7, frameon=False, labelcolor=st["TEXT2"])
    fig.text(0.01, 1.0, "Every event of the run; dashed: end of the warm-up (earlier events are not counted in the "
             "metrics)", fontsize=7,
             color=st["TEXT2"], va="bottom")
    fig.tight_layout()
    return fig


def png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=fig.get_facecolor(), bbox_inches="tight", dpi=130)
    return buf.getvalue()


# ---------------------------------------------------------------------------- downloads
def metrics_csv(out: Outcome) -> bytes:
    """One row per seed and rule: parameters and every metric (as ``handoverlab run`` writes it)."""
    rows = [r.row() for r in out.results]
    cols: List[str] = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(cols)
    for r in rows:
        w.writerow([repr(v) if isinstance(v, float) else ("" if v is None else v) for v in (r.get(c) for c in cols)])
    return buf.getvalue().encode("utf-8")


def results_json(out: Outcome) -> bytes:
    """Settings, the resolved scenario, the rules, every run's metrics and fingerprint, and versions."""
    doc = dict(handoverlab=__version__, python=platform.python_version(), numpy=np.__version__,
               settings=asdict(out.settings), scenario=make_scenario(out.settings).to_dict(), rules=out.rules,
               runs=[dict(seed=r.seed, rule=r.rule, key=r.key, params=r.params, fingerprint=r.fingerprint,
                          n_events=r.n_events, metrics=r.metrics) for r in out.results],
               summary=summary_rows(out))
    return json.dumps(doc, indent=1, default=float).encode("utf-8")


def _table_bytes(writer, results, name) -> bytes:
    import os
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        p = writer(results, os.path.join(d, name))
        with open(p, "rb") as f:
            return f.read()


def events_csv(out: Outcome) -> bytes:
    """Event logs of every run (one row per attempt and per failure without a handover)."""
    return _table_bytes(write_events, out.results, "events.csv")


def trace_csv(out: Outcome) -> bytes:
    """Procedure traces of the first seed (event-log level ``full``)."""
    return _table_bytes(write_trace, [r for r in out.results if r.trace is not None], "trace.csv")


__all__ = ["PROFILES", "LAYOUTS", "PATHLOSS", "FREQUENCIES", "RULES", "RULE_PARAMS", "CHART_METRICS",
           "TABLE_METRICS", "Settings", "RuleSettings", "Outcome", "scenario_dict", "make_scenario", "rule_specs",
           "experiment_dict", "experiment_yaml", "run", "summary_rows", "cell_colours", "map_figure",
           "metrics_figure", "causes_figure", "timeline_figure", "png", "metrics_csv", "results_json", "events_csv",
           "trace_csv"]
