# SPDX-License-Identifier: MIT
"""Reports of a study: Markdown and HTML with tables and figures.

:func:`write_report` reads a study directory (the job records of the current
plan, the tuning files and the manifest) and writes ``report.md``,
``report.html`` (self-contained, figures embedded), ``summary.json`` (every
number of the report) and ``figures/*.png`` into ``<study>/report`` or
another directory.  Figures need matplotlib (``pip install
handoverlab[report]``); without it the report has tables only.

Content
    provenance (versions, sessions, jobs); tuning per group (budgets,
    selected settings, gates, a figure of every evaluated setting); test
    results (means with t intervals per rule, pooled and per condition);
    paired comparisons with the baseline per metric: mean difference with t
    and bootstrap intervals, relative change, bootstrap interval of the ratio
    of means, Wilcoxon signed-rank p-value and Holm-adjusted p-value.

Multiplicity: the pooled comparisons of one metric form one Holm family; the
per-condition comparisons of one metric (all rules and conditions) form
another.
"""
from __future__ import annotations

import base64
import html
import io
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .. import stats
from ..engine.metrics import METRICS
from .config import label
from .store import StudyStore, atomic_write_json, read_json

# reference palette (light surface): categorical slots in fixed order, text and grid tokens
SERIES = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948")
SURFACE, TEXT, TEXT2, GRID, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#b9b8b2"


class ReportError(RuntimeError):
    pass


# ---------------------------------------------------------------------------- data
def _load(root: str) -> Dict[str, Any]:
    store = StudyStore(root)
    lp = store.path("study.lock.json")
    if not os.path.exists(lp):
        raise ReportError("%s is not a study directory (no study.lock.json); run 'handoverlab study' first" % root)
    lock = read_json(lp)
    plan = read_json(store.path("plan.json")) if os.path.exists(store.path("plan.json")) else {"stages": {}}
    records: Dict[str, List[Dict[str, Any]]] = {}
    for stage, ids in plan["stages"].items():
        recs = [store.load_job(stage, i) for i in ids]
        records[stage] = [r for r in recs if r is not None]
    tuned = None
    gp = store.path("tuned", "gates.json")
    if os.path.exists(gp):
        tuned = dict(gates=read_json(gp), groups={})
        for f in sorted(os.listdir(store.path("tuned"))):
            if f.endswith(".json") and f != "gates.json":
                d = read_json(store.path("tuned", f))
                tuned["groups"][d["group"]] = d
    man = read_json(store.path("manifest.json")) if os.path.exists(store.path("manifest.json")) else {}
    return dict(store=store, study=lock["study"], sha=lock.get("sha256", ""), records=records, tuned=tuned,
                manifest=man)


def test_values(records: Sequence[Dict[str, Any]], metric: str) -> Dict[str, Dict[Tuple[str, int], float]]:
    """rule -> {(condition label, seed): value} of the test stage."""
    out: Dict[str, Dict[Tuple[str, int], float]] = {}
    for rec in records:
        cl = label(rec["condition"])
        for r in rec["rules"]:
            out.setdefault(r["name"], {})[(cl, rec["seed"])] = float(r["metrics"][metric])
    return out


def compared_rules(study: Dict[str, Any], names: Sequence[str]) -> List[str]:
    base = study["compare"]["baseline"]
    b = study["compare"].get("budget")
    out = []
    for n in names:
        if n == base:
            continue
        if b and "@" in n and not n.endswith("@" + b):
            continue
        out.append(n)
    return out


def analyse_test(data: Dict[str, Any]) -> Dict[str, Any]:
    """Means and paired comparisons of the test stage (every number of the report)."""
    study = data["study"]
    cmp_ = study["compare"]
    recs = data["records"].get("test", [])
    if not recs:
        return dict(rules=[], means={}, pooled={}, per_condition={}, conditions=[])
    names = [r["name"] for r in recs[0]["rules"]]
    conds = list(dict.fromkeys(label(r["condition"]) for r in recs))
    base = cmp_["baseline"]
    others = compared_rules(study, names)
    level, nb = cmp_["level"], cmp_["bootstrap"]
    means: Dict[str, Any] = {}
    pooled: Dict[str, List[Dict[str, Any]]] = {}
    per_cond: Dict[str, List[Dict[str, Any]]] = {}
    for m in cmp_["metrics"]:
        vals = test_values(recs, m)
        means[m] = {}
        for n in names:
            for scope in ["pooled"] + (conds if len(conds) > 1 else []):
                v = np.array([x for (c, s), x in sorted(vals[n].items()) if scope == "pooled" or c == scope])
                lo, hi = stats.t_interval(v, level)
                means[m].setdefault(n, {})[scope] = dict(n=len(v), mean=float(v.mean()) if len(v) else float("nan"),
                                                         t_lo=lo, t_hi=hi)
        rows = []
        for n in others:
            keys = sorted(set(vals[n]) & set(vals[base]))
            a = [vals[n][k] for k in keys]
            b = [vals[base][k] for k in keys]
            rows.append(dict(rule=n, **stats.paired_summary(a, b, level, nb, seed=0)))
        for r, p in zip(rows, stats.holm([r["p"] for r in rows])):
            r["p_holm"] = p
        pooled[m] = rows
        crow = []
        if len(conds) > 1:
            for c in conds:
                for n in others:
                    keys = sorted(k for k in set(vals[n]) & set(vals[base]) if k[0] == c)
                    a = [vals[n][k] for k in keys]
                    b = [vals[base][k] for k in keys]
                    crow.append(dict(condition=c, rule=n, **stats.paired_summary(a, b, level, nb, seed=0)))
            for r, p in zip(crow, stats.holm([r["p"] for r in crow])):
                r["p_holm"] = p
        per_cond[m] = crow
    return dict(rules=names, baseline=base, compared=others, conditions=conds, means=means, pooled=pooled,
                per_condition=per_cond, level=level, bootstrap=nb)


# ---------------------------------------------------------------------------- figures
def _have_mpl() -> bool:
    try:
        import matplotlib  # noqa: F401
    except ImportError:
        return False
    return True


def _figure(w: float, h: float):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    fig = Figure(figsize=(w, h), dpi=110, facecolor=SURFACE)
    FigureCanvasAgg(fig)
    return fig


def _style(ax) -> None:
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
        ax.spines[s].set_linewidth(0.8)
    ax.tick_params(colors=TEXT2, labelsize=8, length=3, width=0.6)
    ax.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.xaxis.label.set_color(TEXT2)
    ax.yaxis.label.set_color(TEXT2)
    ax.title.set_color(TEXT)


def _png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=SURFACE, bbox_inches="tight")
    return buf.getvalue()


def tuning_figure(gd: Dict[str, Any], objective: str, constraint: str) -> bytes:
    """One panel per method: every evaluated setting (constraint vs objective), budgets, selected settings."""
    methods = list(gd["methods"])
    n = len(methods)
    fig = _figure(3.6 * n + 0.4, 3.3)
    axes = [fig.add_subplot(1, n, i + 1) for i in range(n)]
    first = list(gd["budgets"])[0]
    for i, (ax, mname) in enumerate(zip(axes, methods)):
        md = gd["methods"][mname]
        col = SERIES[i % len(SERIES)]
        cands = md["candidates"]
        x = np.array([c[constraint] for c in cands])
        y = np.array([c[objective] for c in cands])
        inside = np.array([c["within"][first] for c in cands], dtype=bool)
        ax.scatter(x[~inside], y[~inside], s=22, facecolors="none", edgecolors=MUTED, linewidths=1.0,
                   label="outside budget '%s'" % first)
        ax.scatter(x[inside], y[inside], s=22, color=col, edgecolors=SURFACE, linewidths=0.8,
                   label="within budget '%s'" % first)
        for j, (b, val) in enumerate(gd["budgets"].items()):
            ax.axvline(val, color=TEXT2, linewidth=1.0, linestyle=(0, (4, 3)) if j == 0 else (0, (1, 2)),
                       label="budget '%s'" % b)
            sel = md["selected"].get(b)
            if sel:
                ax.scatter([sel[constraint]], [sel[objective]], s=90, facecolors="none", edgecolors=TEXT,
                           linewidths=1.4, zorder=5)
        ref = gd["reference"]
        ax.scatter([ref[constraint]], [ref[objective]], marker="D", s=30, color=TEXT2, zorder=4, label="reference")
        ax.set_title(mname, fontsize=9, loc="left")
        ax.set_xlabel(constraint, fontsize=8)
        if i == 0:
            ax.set_ylabel(objective, fontsize=8)
        _style(ax)
    h, lab = axes[0].get_legend_handles_labels()
    fig.legend(h, lab, loc="lower center", ncol=len(lab), frameon=False, fontsize=7, labelcolor=TEXT2,
               bbox_to_anchor=(0.5, -0.08))
    fig.text(0.01, 1.0, "Tuning, %s: every evaluated setting; circles = selected per budget" % gd["group"],
             fontsize=9, color=TEXT, va="bottom")
    return _png(fig)


def comparison_figure(res: Dict[str, Any], metrics: Sequence[str]) -> bytes:
    """Mean paired difference to the baseline with bootstrap intervals, one panel per metric."""
    rules = res["compared"]
    n = len(metrics)
    fig = _figure(3.2 * n + 0.6, 0.45 * len(rules) + 1.3)
    for i, m in enumerate(metrics):
        ax = fig.add_subplot(1, n, i + 1)
        rows = {r["rule"]: r for r in res["pooled"][m]}
        ys = np.arange(len(rules))[::-1]
        for y, rname in zip(ys, rules):
            r = rows[rname]
            lo, hi = r["boot_lo"], r["boot_hi"]
            if np.isfinite(lo):
                ax.plot([lo, hi], [y, y], color=SERIES[0], linewidth=2.0, solid_capstyle="round")
            ax.scatter([r["diff"]], [y], s=36, color=SERIES[0], edgecolors=SURFACE, linewidths=1.2, zorder=3)
        ax.axvline(0.0, color=TEXT2, linewidth=0.9)
        ax.set_yticks(ys)
        ax.set_yticklabels(rules if i == 0 else [""] * len(rules), fontsize=8, color=TEXT)
        ax.set_ylim(-0.7, len(rules) - 0.3)
        ax.set_title(m, fontsize=9, loc="left")
        ax.set_xlabel("difference to %s" % res["baseline"], fontsize=8)
        _style(ax)
        ax.grid(False, axis="y")
    fig.text(0.01, 1.0, "Paired differences to %s, pooled over conditions and seeds (%.0f %% bootstrap intervals)"
             % (res["baseline"], 100 * res["level"]), fontsize=9, color=TEXT, va="bottom")
    return _png(fig)


# ---------------------------------------------------------------------------- document model
class Doc:
    """A small document model rendered as Markdown and as HTML."""

    def __init__(self):
        self.blocks: List[Tuple[str, Any]] = []

    def h(self, level: int, text: str):
        self.blocks.append(("h", (level, text)))

    def p(self, text: str):
        self.blocks.append(("p", text))

    def table(self, header: Sequence[str], rows: Sequence[Sequence[Any]], note: str = ""):
        self.blocks.append(("table", (list(header), [list(map(str, r)) for r in rows], note)))

    def fig(self, name: str, png: bytes, caption: str):
        self.blocks.append(("fig", (name, png, caption)))

    def markdown(self) -> str:
        out = []
        for kind, v in self.blocks:
            if kind == "h":
                out.append("#" * v[0] + " " + v[1])
            elif kind == "p":
                out.append(v)
            elif kind == "table":
                head, rows, note = v
                out.append("| " + " | ".join(head) + " |")
                out.append("|" + "|".join("---" for _ in head) + "|")
                out.extend("| " + " | ".join(c.replace("|", "\\|") for c in r) + " |" for r in rows)
                if note:
                    out.append("\n" + note)
            elif kind == "fig":
                out.append("![%s](figures/%s)" % (v[2], v[0]))
            out.append("")
        return "\n".join(out)

    def html(self, title: str) -> str:
        e = html.escape
        body = []
        for kind, v in self.blocks:
            if kind == "h":
                body.append("<h%d>%s</h%d>" % (v[0], _inline(e(v[1])), v[0]))
            elif kind == "p":
                body.append("<p>%s</p>" % _inline(e(v)))
            elif kind == "table":
                head, rows, note = v
                t = ["<div class='tw'><table><thead><tr>" + "".join("<th>%s</th>" % _inline(e(c)) for c in head)
                     + "</tr></thead><tbody>"]
                for r in rows:
                    t.append("<tr>" + "".join("<td>%s</td>" % _inline(e(c)) for c in r) + "</tr>")
                t.append("</tbody></table></div>")
                if note:
                    t.append("<p class='note'>%s</p>" % _inline(e(note)))
                body.append("".join(t))
            elif kind == "fig":
                b64 = base64.b64encode(v[1]).decode()
                body.append("<figure><img alt='%s' src='data:image/png;base64,%s'><figcaption>%s</figcaption>"
                            "</figure>" % (e(v[2]), b64, e(v[2])))
        return _HTML % dict(title=e(title), body="\n".join(body))


def _inline(s: str) -> str:
    """`code` -> <code> in already escaped text."""
    parts = s.split("`")
    return "".join(("<code>%s</code>" % p) if i % 2 else p for i, p in enumerate(parts))


_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
<style>
:root { --bg: #fcfcfb; --fg: #0b0b0b; --fg2: #52514e; --line: #e4e3df; --head: #f2f1ee; }
@media (prefers-color-scheme: dark) { :root { --bg: #1a1a19; --fg: #ffffff; --fg2: #c3c2b7; --line: #3a3936;
  --head: #242423; } figure img { background: #fcfcfb; } }
body { background: var(--bg); color: var(--fg); font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif;
  margin: 0 auto; max-width: 1100px; padding: 24px 16px 48px; }
h1 { font-size: 1.6em; margin: 0.2em 0 0.4em; } h2 { font-size: 1.25em; margin-top: 1.8em;
  border-bottom: 1px solid var(--line); padding-bottom: 4px; } h3 { font-size: 1.05em; margin-top: 1.4em; }
p { margin: 0.5em 0; } .note { color: var(--fg2); font-size: 0.9em; }
code { font-family: ui-monospace, Consolas, monospace; font-size: 0.92em; }
.tw { overflow-x: auto; margin: 0.6em 0; }
table { border-collapse: collapse; font-size: 0.88em; font-variant-numeric: tabular-nums; }
th, td { border-bottom: 1px solid var(--line); padding: 4px 10px; text-align: right; white-space: nowrap; }
th:first-child, td:first-child { text-align: left; } th { background: var(--head); font-weight: 600; }
figure { margin: 1em 0; } figure img { max-width: 100%%; height: auto; border-radius: 4px; }
figcaption { color: var(--fg2); font-size: 0.88em; }
</style></head><body>
%(body)s
</body></html>
"""


# ---------------------------------------------------------------------------- report
def _f(x: Any, nd: int = 3) -> str:
    return stats.rnd(x, nd)


def _p(p: float) -> str:
    if p is None or not np.isfinite(p):
        return "n/a"
    return "< 0.0001" if p < 1e-4 else stats.rnd(p, 4)


def _ci(lo: float, hi: float, nd: int = 3) -> str:
    if not (np.isfinite(lo) and np.isfinite(hi)):
        return "n/a"
    return "[%s, %s]" % (_f(lo, nd), _f(hi, nd))


def build_report(root: str, figures: bool = True) -> Tuple[Doc, Dict[str, Any]]:
    data = _load(root)
    study = data["study"]
    doc = Doc()
    summary: Dict[str, Any] = dict(study=study["name"], lock_sha256=data["sha"])
    doc.h(1, "Study report: %s" % study["name"])
    if study.get("description"):
        doc.p(study["description"])
    man = data["manifest"]
    v = man.get("versions", {})
    n_jobs = {s: len(r) for s, r in data["records"].items()}
    sim = sum(1 for rs in data["records"].values() for r in rs for x in r["rules"] if not x["reused"])
    cpu = sum(r["timing"]["total_s"] for rs in data["records"].values() for r in rs)
    doc.p("HandoverLab %s (model %s), Python %s, NumPy %s, SciPy %s, %s. Study file hash `%s`."
          % (v.get("handoverlab", "?"), v.get("model", "?"), v.get("python", "?"), v.get("numpy", "?"),
             v.get("scipy", "?"), v.get("platform", "?"), data["sha"][:16]))
    doc.p("Jobs: %s; %d rule runs simulated, the rest reused; %.0f s of job time; %d session(s)."
          % (", ".join("%s %d" % kv for kv in n_jobs.items()) or "none", sim, cpu, len(man.get("sessions", []))))
    summary.update(jobs=n_jobs, simulated_rule_runs=sim, job_time_s=cpu, versions=v)
    seeds = study["seeds"]
    doc.p("Scenario `%s`; conditions: %s; tuning seeds %s; test seeds %s."
          % (study["scenario"].get("name", ""), ", ".join("`%s` = %s" % (k, vals) for k, vals in
                                                         study["conditions"].items()) or "one",
             _seed_text(seeds["tuning"]), _seed_text(seeds["test"])))
    mpl = figures and _have_mpl()
    if figures and not mpl:
        doc.p("Figures are missing: matplotlib is not installed (`pip install handoverlab[report]`).")
    # ------------------------------------------------------------ tuning
    tuned = data["tuned"]
    t = study["tuning"]
    if tuned is not None:
        doc.h(2, "Tuning")
        doc.p("Every tuned method evaluated %d settings per tuning group (%d drawn at random, the rest around "
              "the best of the first round) on the tuning seeds. Failure budgets are shares of the failure rate "
              "of the reference rule `%s` on the same runs: %s. Selection: %s."
              % (t["settings"], t["random"], t["reference"].get("name", "reference"),
                 ", ".join("%s %g" % kv for kv in t["budgets"].items()), tuned["gates"]["selection"]))
        g = tuned["gates"]
        doc.h(3, "Gates")
        bad = [x for x in g["gates"] if x["status"] != "pass"]
        passed: Dict[str, int] = {}
        for x in g["gates"]:
            if x["status"] == "pass":
                passed[x["gate"]] = passed.get(x["gate"], 0) + 1
        if bad:
            rows = [[x["gate"], x["status"], x["group"] or "all", x["method"] or "-", x["budget"] or "-",
                     x["message"]] for x in bad]
            doc.table(["gate", "status", "group", "method", "budget", "detail"], rows,
                      "Blocking gates: %d; warnings: %d. Passed: %s." % (
                          len(g["blocking"]), len(g["warnings"]),
                          ", ".join("%s %d" % kv for kv in passed.items()) or "none"))
        else:
            doc.p("Every gate passed (%s). The full gate report is in `tuned/gates.json`."
                  % ", ".join("%s %d" % kv for kv in passed.items()))
        summary["gates"] = g
        summary["tuning"] = {}
        for gname, gd in tuned["groups"].items():
            doc.h(3, "Group %s" % gname)
            ref = gd["reference"]
            doc.p("Reference `%s`: %s = %s, %s = %s per UE-minute over %d runs (%d failures). Budgets: %s."
                  % (ref["name"], t["objective"], _f(ref[t["objective"]]), t["constraint"], _f(ref[t["constraint"]]),
                     ref["n_runs"], ref["n_failures"],
                     ", ".join("%s %s" % (b, _f(val, 4)) for b, val in gd["budgets"].items())))
            rows = []
            for mname, md in gd["methods"].items():
                for b, s in md["selected"].items():
                    rows.append([mname, b, s["text"], _f(s[t["objective"]]), _f(s[t["constraint"]]),
                                 _f(s["prepared_cells_mean"]), "%d / %d" % (s["n_meeting"], len(md["candidates"])),
                                 "yes" if s["met_budget"] else "NO"])
            doc.table(["method", "budget", "selected setting", t["objective"], t["constraint"], "prepared cells",
                       "within budget", "budget met"], rows)
            summary["tuning"][gname] = {m: md["selected"] for m, md in gd["methods"].items()}
            if mpl and gd["methods"]:
                name = "tuning_%s.png" % _safe(gname)
                doc.fig(name, tuning_figure(gd, t["objective"], t["constraint"]),
                        "Tuning of group %s: every evaluated setting; filled = within the first budget, "
                        "circled = selected, diamond = reference." % gname)
    # ------------------------------------------------------------ test
    res = analyse_test(data)
    summary["test"] = res
    if res["rules"]:
        doc.h(2, "Test results")
        doc.p("%d test jobs, rules: %s. Means over runs with %.0f %% t intervals; rates per UE-minute."
              % (len(data["records"]["test"]), ", ".join("`%s`" % r for r in res["rules"]), 100 * res["level"]))
        metrics = study["compare"]["metrics"]
        for scope in ["pooled"] + (res["conditions"] if len(res["conditions"]) > 1 else []):
            doc.h(3, "Means, %s" % ("all conditions" if scope == "pooled" else scope))
            rows = []
            for n in res["rules"]:
                row = [n]
                for m in metrics:
                    d = res["means"][m][n][scope]
                    row.append("%s %s" % (_f(d["mean"]), _ci(d["t_lo"], d["t_hi"])))
                rows.append(row)
            doc.table(["rule"] + list(metrics), rows)
        doc.h(2, "Paired comparisons with %s" % res["baseline"])
        doc.p("Runs are paired by condition and seed (same world and radio samples). Difference = rule minus "
              "baseline. p: two-sided Wilcoxon signed-rank test (zero differences dropped, mid-ranks for ties, "
              "exact null distribution up to %d pairs); p (Holm): adjusted within the family of the metric. "
              "Bootstrap intervals use %d resamples of the pairs." % (stats.EXACT_MAX, res["bootstrap"]))
        for m in metrics:
            unit = METRICS.get(m, ("", ""))[0]
            doc.h(3, "%s (%s)" % (m, unit))
            rows = [[r["rule"], r["n"], _f(r["mean"]), _f(r["mean_base"]), _f(r["diff"], 4),
                     _ci(r["t_lo"], r["t_hi"], 4), _ci(r["boot_lo"], r["boot_hi"], 4), _f(r["rel_pct"], 1),
                     _ci(r["ratio_lo"], r["ratio_hi"]), _p(r["p"]), _p(r["p_holm"]), r["n_nonzero"]]
                    for r in res["pooled"][m]]
            doc.table(["rule", "pairs", "mean", "baseline", "difference", "t interval", "bootstrap interval",
                       "change %", "ratio interval", "p", "p (Holm)", "non-zero"], rows)
            if res["per_condition"][m]:
                rows = [[r["condition"], r["rule"], r["n"], _f(r["diff"], 4), _ci(r["boot_lo"], r["boot_hi"], 4),
                         _f(r["rel_pct"], 1), _p(r["p"]), _p(r["p_holm"])] for r in res["per_condition"][m]]
                doc.table(["condition", "rule", "pairs", "difference", "bootstrap interval", "change %", "p",
                           "p (Holm)"], rows, "Per condition; Holm family: all rows of this table.")
        if mpl and res["compared"]:
            doc.fig("comparison.png", comparison_figure(res, metrics),
                    "Mean paired difference to %s with bootstrap intervals, pooled." % res["baseline"])
    else:
        doc.h(2, "Test results")
        doc.p("The test stage has not run (yet).")
    return doc, summary


def _seed_text(s: Sequence[int]) -> str:
    if not s:
        return "none"
    s = list(s)
    if s == list(range(s[0], s[0] + len(s))) and len(s) > 3:
        return "%d-%d (%d)" % (s[0], s[-1], len(s))
    return ", ".join(map(str, s))


def _safe(s: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in s)


def write_report(root: str, out: Optional[str] = None, formats: Sequence[str] = ("md", "html"),
                 figures: bool = True) -> List[str]:
    """Write the report of the study in ``root``; returns the files written."""
    doc, summary = build_report(root, figures)
    out = out or os.path.join(root, "report")
    os.makedirs(out, exist_ok=True)
    written = []
    figs = [v for k, v in doc.blocks if k == "fig"]
    if figs:
        os.makedirs(os.path.join(out, "figures"), exist_ok=True)
        for name, png, _ in figs:
            p = os.path.join(out, "figures", name)
            with open(p, "wb") as f:
                f.write(png)
            written.append(p)
    if "md" in formats:
        p = os.path.join(out, "report.md")
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(doc.markdown())
        written.append(p)
    if "html" in formats:
        p = os.path.join(out, "report.html")
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(doc.html("Study report: %s" % summary["study"]))
        written.append(p)
    p = os.path.join(out, "summary.json")
    atomic_write_json(p, summary)
    written.append(p)
    return written


__all__ = ["write_report", "build_report", "analyse_test", "ReportError"]
