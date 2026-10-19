# SPDX-License-Identifier: MIT
"""Dashboard: the non-visual logic (settings, runs, map frames, figures, downloads) and, with Streamlit, the page."""
import csv
import io
import json
import os
import sys

import numpy as np
import pytest
import yaml

import handoverlab as hl
from handoverlab.gui import APP, logic, streamlit_args

pytest.importorskip("matplotlib")

QUICK = logic.Settings(layout="street_grid", blocks=1, site_spacing_m=150.0, users=6, profile="veh30",
                       duration_s=12.0, warmup_s=2.0, seeds=2, first_seed=3)
RULES = [logic.RuleSettings("a3", "A3", {"off_db": 2.0, "ttt_s": 0.08}),
         logic.RuleSettings("cho", "CHO", {"o_exec_db": 2.0, "n_max": 2})]


@pytest.fixture(scope="module")
def outcome():
    shares = []
    out = logic.run(QUICK, RULES, frame_s=1.0, progress=lambda s, t: shares.append(s))
    return out, shares


def test_core_package_does_not_import_the_gui():
    import subprocess
    code = ("import sys; sys.path[:0] = %r; import handoverlab, handoverlab.cli, handoverlab.studies; " % sys.path +
            "print(int(any(m.startswith(('streamlit', 'handoverlab.gui')) for m in sys.modules)))")
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path))
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env)
    if out.returncode != 0:
        pytest.skip("cannot start a fresh interpreter here: %s" % out.stderr[-200:])
    assert out.stdout.strip() == "0"


def test_settings_to_scenario_and_experiment():
    sc = logic.make_scenario(QUICK)
    assert sc.layout.kind == "street_grid" and tuple(sc.layout.blocks) == (1, 1)
    assert sc.mobility.users == 6 and sc.mobility.profile == "veh30" and sc.run.duration_s == 12.0
    exp = hl.load_config(logic.experiment_dict(QUICK, RULES))
    assert list(exp.seeds) == [3, 4] and [r["name"] for r in exp.rules] == ["A3", "CHO"]
    text = logic.experiment_yaml(QUICK, RULES)
    assert yaml.safe_load(text)["rules"][1]["o_exec_db"] == 2.0
    bad = logic.Settings(warmup_s=50.0, duration_s=40.0, profile="fast")
    assert len(bad.check()) == 2
    with pytest.raises(ValueError):
        logic.make_scenario(bad)
    names = [r["name"] for r in logic.rule_specs([logic.RuleSettings("a3", "X"), logic.RuleSettings("a3", "X")])]
    assert names == ["X", "X-2"]
    for key, params in logic.RULE_PARAMS.items():         # every offered parameter exists and the default is valid
        rule = hl.make_rule(dict({p: v[4] for p, v in params.items()}, rule=key))
        assert set(params) <= set(rule.params())
        assert all(v[1] <= v[4] <= v[2] for v in params.values())


def test_run_matches_the_simulator(outcome):
    out, shares = outcome
    assert shares[-1] == 1.0 and shares == sorted(shares)
    assert out.rule_names == ["A3", "CHO"] and len(out.results) == 4
    ref = hl.simulate(logic.make_scenario(QUICK), logic.rule_specs(RULES), seeds=[3, 4])
    assert [r.fingerprint for r in ref] == [r.fingerprint for r in out.results]
    F = len(out.times)
    assert out.x.shape == (F, 6) and out.serving.shape == (2, F, 6)
    assert out.serving.min() >= -1 and out.serving.max() < len(out.sites)
    assert (out.serving[:, 0] >= 0).all()                  # everybody is served at the start
    rows = logic.summary_rows(out)
    a3 = [r.metrics["handovers_pm"] for r in out.results if r.rule == "A3"]
    assert rows[0]["seeds"] == 2 and rows[0]["handovers_pm"] == pytest.approx(np.mean(a3))


def test_cell_colours_differ_for_near_cells():
    sites = np.array([[0, 0], [100, 0], [200, 0], [0, 100], [100, 100], [200, 100]], dtype=float)
    slots = logic.cell_colours(sites, 8)
    assert len(set(slots)) == 6
    many = np.array([[x, y] for x in range(0, 1000, 100) for y in range(0, 500, 100)], dtype=float)
    slots = logic.cell_colours(many, 8)
    d = np.hypot(*(many[:, None, :] - many[None, :, :]).transpose(2, 0, 1))
    for i in range(len(many)):
        for j in range(len(many)):
            if i != j and d[i, j] <= 100.0:
                assert slots[i] != slots[j]


def test_figures(outcome):
    out, _ = outcome
    for fig in (logic.map_figure(out, 1, 5), logic.metrics_figure(out), logic.causes_figure(out),
                logic.timeline_figure(out)):
        data = logic.png(fig)
        assert data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) > 5000
    fig = logic.map_figure(out, 0, 10**6)                   # frames are clipped
    assert "t = %.1f s" % out.times[-1] in fig.axes[0].get_title(loc="left")



def test_comparison_with_intervals(outcome):
    out, _ = outcome
    rows = logic.comparison_rows(out)
    assert len(rows) == 2 * len(logic.CHART_METRICS)
    a3 = next(r for r in rows if r["rule"] == "A3" and r["metric"] == "handovers_pm")
    cho = next(r for r in rows if r["rule"] == "CHO" and r["metric"] == "handovers_pm")
    v = [r.metrics["handovers_pm"] for r in out.results if r.rule == "A3"]
    assert a3["seeds"] == 2 and a3["mean"] == pytest.approx(np.mean(v)) and a3["ci_low"] <= a3["mean"] <= a3["ci_high"]
    assert "diff" not in a3 and cho["diff_vs"] == "A3" and cho["diff_low"] <= cho["diff"] <= cho["diff_high"]
    assert logic.comparison_csv(out).decode().splitlines()[0].startswith("metric,rule,seeds,mean")
    assert logic.png(logic.comparison_figure(out))[1:4] == b"PNG"


def test_where_map(outcome):
    out, _ = outcome
    pts = logic.event_points(out, 0)
    r = next(x for x in out.results if x.rule == "A3" and x.seed == 3)
    assert len(pts["handover"]) + len(pts["failure"]) == sum(1 for e in r.events if e["kind"] == "rlf"
                                                              or e.get("cause") or e["t_exec"] >= 0)
    assert len(pts["unnecessary"]) <= len(pts["handover"])
    assert logic.png(logic.events_map_figure(out, 1))[1:4] == b"PNG"


def test_traffic_setting_and_study_status(tmp_path):
    assert "traffic" not in logic.scenario_dict(logic.Settings())             # default: the configuration of 1.3
    assert logic.scenario_dict(logic.Settings(traffic="ftp3"))["traffic"] == {"model": "ftp3"}
    assert logic.Settings(traffic="voip").check() == ["unknown traffic model 'voip'"]
    assert logic.study_status_lines(str(tmp_path / "missing.yaml"))[0].startswith("cannot read a study")


def test_downloads(outcome):
    out, _ = outcome
    rows = list(csv.DictReader(io.StringIO(logic.metrics_csv(out).decode())))
    assert len(rows) == 4 and {"seed", "rule", "fingerprint", "handovers_pm"} <= set(rows[0])
    doc = json.loads(logic.results_json(out))
    assert doc["settings"]["users"] == 6 and len(doc["runs"]) == 4 and doc["scenario"]["mobility"]["users"] == 6
    ev = logic.events_csv(out).decode().splitlines()
    assert ev[0].startswith("seed,rule,t_attempt") and len(ev) == 1 + sum(r.n_events for r in out.results)
    tr = logic.trace_csv(out).decode().splitlines()
    assert tr[0].startswith("seed,rule,t,ue,event") and len(tr) > 13


def test_launch_arguments():
    args = streamlit_args(8600, headless=True)
    assert args[:2] == ["run", APP] and "8600" in args and os.path.exists(APP)
    assert args[args.index("--server.headless") + 1] == "true"


def test_page_runs_headless():
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest
    main = sys.modules["__main__"]                         # the page runs as __main__; keep ours for workers
    try:
        _page_run(AppTest)
    finally:
        sys.modules["__main__"] = main


def _page_run(AppTest):
    at = AppTest.from_file(APP, default_timeout=240)
    at.run()
    assert not at.exception
    at.sidebar.slider[0].set_value(1)                       # blocks per side
    at.sidebar.slider[2].set_value(6)                       # users
    at.sidebar.slider[3].set_value(10)                      # run length
    at.sidebar.slider[4].set_value(0)                       # warm-up
    at.sidebar.slider[5].set_value(1)                       # seeds (the page offers 3)
    at.button[0].click().run()
    assert not at.exception
    out = at.session_state["outcome"]
    assert out.settings.users == 6 and len(out.results) == 2
    assert len(at.tabs) == 7
