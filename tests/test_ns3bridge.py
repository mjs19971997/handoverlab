# SPDX-License-Identifier: MIT
"""The ns-3 bridge (handoverlab.ns3bridge, ``handoverlab ns3``) without ns-3: export, import, refusals, checks."""
import copy
import json
import os
import zipfile

import numpy as np
import pytest

from handoverlab import ns3bridge as nb
from handoverlab.cli import main
from handoverlab.verify.ns3 import scenario_for

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "ns3bridge")
EXAMPLE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples", "ns3_study_v1.yaml")

V1 = {"schema": 1, "name": "V1", "ns3": {
    "scenario": "ns3-urban-3.5ghz", "rule": "a3", "users": 20, "duration_s": 180, "discard_s": 60,
    "conditions": {"isd_m": [200, 300], "speed_mps": [10, 28], "ttt_ms": [80, 320], "offset_db": [3],
                   "traffic": ["light"], "fading": [False]},
    "seeds": {"first": 401, "last": 405}, "outputs": {"events": True, "ctrl_csv": True}}}


def _v1_reference_args():
    """The command lines of the hand-made ns-3 package of study V1 (2.5.0), copied from its run script
    (``LIGHT`` and ``job``) without the program path and ``--outDir``."""
    light = [("light", isd, v, ttt, s) for isd in (200, 300) for v in (10, 28) for ttt in (80, 320)
             for s in range(401, 406)]
    out = []
    for traffic, isd, v, ttt, seed in light:
        tag = "V1_%s_d%d_v%d_t%d_s%d" % (traffic, isd, v, ttt, seed)
        out.append(["--scen=urban", "--rule=a3", "--hyst=3", "--ttt=%d" % ttt, "--isd=%d" % isd, "--speed=%d" % v,
                    "--rngRun=%d" % seed, "--simTime=180", "--discard=60", "--nUe=20", "--udpInterval=100",
                    "--fading=0", "--traffic=" + traffic, "--events=1", "--ctrlCsv=1", "--tag=" + tag])
    return out


@pytest.fixture
def program(tmp_path):
    p = tmp_path / "handoverlab-ns3-a3.cc"
    p.write_text("// stand-in for the ns-3 program\n", encoding="utf-8")
    return str(p)


@pytest.fixture
def run_dir(tmp_path):
    d = tmp_path / "runs"
    d.mkdir()
    with open(os.path.join(DATA, "v1_runs.json"), encoding="utf-8") as f:
        for r in json.load(f):
            (d / (r["tag"] + ".json")).write_text(json.dumps(r), encoding="utf-8")
    return str(d)


# ------------------------------------------------------------------ B1: export
def test_b1_v1_command_lines(tmp_path, program):
    man = nb.export(V1, str(tmp_path / "pkg"), program=program)
    assert [r["args"] for r in man["runs"]] == _v1_reference_args()
    assert [r["tag"] for r in man["runs"]][0] == "V1_light_d200_v10_t80_s401"
    files = sorted(os.listdir(tmp_path / "pkg"))
    assert files == ["README.md", "build.sh", "handoverlab-ns3-a3.cc", "manifest.json", "run.ps1", "run.py"]
    with open(tmp_path / "pkg" / "manifest.json", encoding="utf-8") as f:
        stored = json.load(f)
    assert stored["study_sha256"] == nb.load_ns3_study(V1).sha256() and stored["runs"] == man["runs"]


def test_example_study_is_v1():
    ex, v1 = nb.load_ns3_study(EXAMPLE), nb.load_ns3_study(V1)
    assert ex.sha256() == v1.sha256() and ex.run_length == v1.run_length == "study"


def test_exported_run_script_lists_and_zips(tmp_path, program):
    import subprocess
    import sys
    pkg = tmp_path / "pkg"
    nb.export(V1, str(pkg), program=program)
    out = subprocess.run([sys.executable, str(pkg / "run.py"), "--dry-run"], capture_output=True, text=True)
    assert out.returncode == 0 and out.stdout.strip().endswith("40 runs")
    assert "--tag=V1_light_d300_v28_t320_s405 --outDir=runs" in out.stdout
    out = subprocess.run([sys.executable, str(pkg / "run.py"), "--zip-only"], capture_output=True, text=True)
    assert out.returncode == 1 and "0 of 40 runs finished" in out.stdout
    assert zipfile.ZipFile(pkg / "V1_results.zip").namelist() == ["manifest.json"]
    # the control-channel CSVs go into the zip when outputs.ctrl_csv is on, and only then
    off = copy.deepcopy(V1)
    off["ns3"]["outputs"] = {"events": True, "ctrl_csv": False}
    for study, name in ((V1, "on"), (off, "off")):
        p = tmp_path / name
        nb.export(study, str(p), program=program)
        (p / "runs").mkdir()
        for f in ("V1_x.json", "V1_x_att.csv", "V1_x_ctrl.csv", "V1_x.log", "V1_x.tmp"):
            (p / "runs" / f).write_text("x", encoding="utf-8")
        subprocess.run([sys.executable, str(p / "run.py"), "--zip-only"], capture_output=True, text=True)
        names = zipfile.ZipFile(p / "V1_results.zip").namelist()
        ctrl = ["runs/V1_x_ctrl.csv"] if name == "on" else []
        assert names == ["manifest.json", "runs/V1_x.json", "runs/V1_x_att.csv"] + ctrl


def test_tags_and_options_of_varying_offset_and_fading():
    d = copy.deepcopy(V1)
    d["ns3"]["conditions"].update(offset_db=[1, 4.5], fading=[False, True], speed_mps=[16])
    d["ns3"]["outputs"] = {"events": False}
    st = nb.load_ns3_study(d)
    rs = nb.runs(st)
    assert len(rs) == 2 * 2 * 2 * 1 * 2 * 5
    assert rs[-1]["tag"] == "V1_light_h4.5_d300_v16_t320_f1_s405"
    assert "--hyst=4.5" in rs[-1]["args"] and "--fading=1" in rs[-1]["args"]
    assert "--events=1" not in rs[-1]["args"] and "--ctrlCsv=1" not in rs[-1]["args"]


# ------------------------------------------------------------------ B2: import and compare
def test_b2_import_folder_and_zip(tmp_path, run_dir):
    ref = nb.import_results(run_dir, str(tmp_path / "ref.json"))
    with open(os.path.join(DATA, "v1_runs.json"), encoding="utf-8") as f:
        runs = json.load(f)
    assert ref["n_runs"] == 4 and len(ref["rows"]) == 2
    for r in ref["rows"]:
        mine = [x for x in runs if x["ttt_ms"] == r["ttt_ms"]]
        assert (r["isd_m"], r["speed_mps"], r["a3_offset_db"], r["traffic"], r["fading"]) == (200, 10.0, 3.0,
                                                                                            "light", False)
        assert r["seeds"] == [401, 402] and r["runs"] == 2 and r["part"] == "S"
        assert r["failures"] == sum(x["failures"] for x in mine)
        assert r["handovers_pm"] == float(np.mean([x["ho_pm"] for x in mine]))
        assert r["ue_min"] == 80.0 and (r["users"], r["duration_s"], r["discard_s"]) == (20, 180.0, 60.0)
    from handoverlab.verify.ns3 import load_reference
    assert load_reference(str(tmp_path / "ref.json"))["rows"] == ref["rows"]
    zp = tmp_path / "res.zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("manifest.json", json.dumps({"format": "handoverlab-ns3-export", "name": "V1",
                                                "study_sha256": "abc"}))
        for f in sorted(os.listdir(run_dir)):
            z.write(os.path.join(run_dir, f), "runs/" + f)
            z.writestr("runs/" + f[:-5] + "_att.csv", "t_cmd\n")
    rz = nb.import_results(str(zp))
    assert rz["rows"] == ref["rows"] and rz["study"] == "V1" and rz["study_sha256"] == "abc"


def test_b2_import_refusals(tmp_path, run_dir):
    (tmp_path / "empty").mkdir()
    with pytest.raises(nb.Ns3BridgeError, match="no run JSON"):
        nb.import_results(str(tmp_path / "empty"))
    r = json.load(open(os.path.join(run_dir, "V1_light_d200_v10_t80_s401.json")))
    with open(os.path.join(run_dir, "copy.json"), "w") as f:
        json.dump(r, f)
    with pytest.raises(nb.Ns3BridgeError, match="seed 401 appears twice"):
        nb.import_results(run_dir)
    del r["failures"]
    with open(os.path.join(run_dir, "copy.json"), "w") as f:
        json.dump(r, f)
    with pytest.raises(nb.Ns3BridgeError, match="without failures"):
        nb.import_results(run_dir)


def test_b2_checks_reproduce_v1_counts():
    """F1, F2 and F4 from the cell failure counts of study V1 (row C) as registered, with the wrong run length
    (90 s against 120 s); the checks themselves do not depend on it."""
    hl = [8, 46, 7, 33, 5, 16, 3, 11]
    ns = [16, 29, 7, 47, 3, 15, 4, 12]
    cells = [dict(isd_m=i, speed_mps=v, ttt_ms=t, offset_db=3.0, traffic="light", fading=False, failures_hl=h,
                  failures_ns3=n, ho_pm_hl=1.0, ho_pm_ns3=1.0)
             for (i, v, t), h, n in zip([(i, v, t) for i in (200, 300) for v in (10, 28) for t in (80, 320)], hl, ns)]
    c = nb.checks(cells)
    assert c["F1_level"] == pytest.approx(0.9699248120300752, abs=1e-15)
    assert c["F2_rank"] == pytest.approx(0.880952380952381, abs=1e-12)
    assert (c["F3_ho_ratio"], c["F4_ttt_sign"], c["F4_pairs"]) == (1.0, 4, 4)
    assert c["pass"] == {"F1": True, "F2": True, "F3": True, "F4": True}
    few = [dict(x, failures_ns3=1) for x in cells]
    c = nb.checks(few)
    assert c["F1_level"] is None and c["pass"]["F1"] is False and c["pass"]["F2"] is False
    c = nb.checks(cells, {"level": (1.0, 1.5), "ttt_share": 1.0})
    assert c["pass"]["F1"] is False and c["pass"]["F4"] is True


def test_b2_handoverlab_side_is_that_of_v1():
    st = nb.load_ns3_study(V1)
    # 'card' reproduces the registered V1 analysis, which used the wrong run length on the HandoverLab side
    # (the card's 150 s with 60 s warm-up, 90 s measured against 120 s in ns-3); new comparisons use 'study'
    st.run_length = "card"
    for comp in (False, True):
        sc = nb.handoverlab_scenario(st, 300, 28, "light", False, comparison=comp)
        ref = scenario_for(300, 28, car=True).with_overrides(
            {"protocol.exec_can_fail": False, **({"protocol.lm_load": 0.15} if comp else {})})
        assert sc.to_dict(full=True) == ref.to_dict(full=True)
    st.run_length = "study"
    sc = nb.handoverlab_scenario(st, 200, 10, "full", True)
    assert (sc.run.duration_s, sc.run.warmup_s, sc.traffic.model, sc.radio.fast_fading) == (180.0, 60.0,
                                                                                           "full_buffer", "tdl-c")


def test_b2_compare_runs_the_reference_cells(tmp_path, run_dir):
    ref = nb.import_results(run_dir)
    d = copy.deepcopy(V1)
    d["ns3"]["conditions"].update(isd_m=[200], speed_mps=[10])
    d["ns3"]["seeds"] = [401, 402]
    short = {"run.duration_s": 3.0, "run.warmup_s": 1.0, "mobility.users": 3}
    res = nb.compare(d, ref, overrides=short, out=str(tmp_path / "cmp.json"))
    assert [c["key"] for c in res["cells"]] == ["light_h3_d200_v10_t80", "light_h3_d200_v10_t320"]
    assert [c["failures_ns3"] for c in res["cells"]] == [r["failures"] for r in ref["rows"]]
    assert res["checks"]["F1_level"] is None and res["checks"]["F4_pairs"] == 1
    assert json.load(open(tmp_path / "cmp.json"))["cells"] == res["cells"]
    d["ns3"]["conditions"]["ttt_ms"] = [80, 160]
    with pytest.raises(nb.Ns3BridgeError, match="no runs for V1_light_d200_v10_t160"):
        nb.compare(d, ref, overrides=short)


# ------------------------------------------------------------------ B3: refusals before any file is written
@pytest.mark.parametrize("change, match", [
    ({"rule": "cho"}, "'ns3.rule: cho'"),
    ({"rule": {"rule": "a3", "ttt_s": 0.1}}, "'ns3.rule.ttt_s'"),
    ({"scenario": {"base": "ns3-urban-3.5ghz", "radio": {"beams": {"n_beams": 8}}}},
     "'ns3.scenario.radio.beams.n_beams'"),
    ({"scenario": {"base": "ns3-urban-3.5ghz", "layout": {"kind": "ntn"}}}, "'ns3.scenario.layout.kind'"),
    ({"scenario": "ntn-leo600-2ghz"}, "'ns3.scenario: ntn-leo600-2ghz'"),
    ({"scenario": "highway-tr37885-4ghz"}, "'ns3.scenario: highway-tr37885-4ghz'"),
    ({"beams": 8}, "'ns3.beams'"),
    ({"conditions": {"isd_m": [500]}}, "'ns3.conditions.isd_m: 500'"),
    ({"conditions": {"traffic": ["ftp3"]}}, "'ns3.conditions.traffic: ftp3'"),
    ({"conditions": {"t310_ms": [500]}}, "'ns3.conditions.t310_ms'"),
    ({"handoverlab": {"overrides": {"protocol.lm_load": 0.2}}}, "'ns3.handoverlab.overrides'"),
])
def test_b3_refused_before_writing(tmp_path, program, change, match):
    d = copy.deepcopy(V1)
    d["ns3"].update(change)
    out = tmp_path / "pkg"
    with pytest.raises(nb.Ns3BridgeError, match=match.replace(".", r"\.")):
        nb.export(d, str(out), program=program)
    assert not out.exists()


def test_b3_other_refusals(tmp_path, program, run_dir):
    with pytest.raises(nb.Ns3BridgeError, match="'ntn'"):
        nb.load_ns3_study({"schema": 1, "name": "x", "ns3": {}, "ntn": {}})
    with pytest.raises(nb.Ns3BridgeError, match="missing section 'ns3'"):
        nb.load_ns3_study({"name": "x"})
    with pytest.raises(nb.Ns3BridgeError, match="not part of the Python package|no such file"):
        nb.export(V1, str(tmp_path / "pkg"), program=str(tmp_path / "missing.cc"))
    assert not (tmp_path / "pkg").exists()
    (tmp_path / "full").mkdir()
    (tmp_path / "full" / "x").write_text("x")
    with pytest.raises(nb.Ns3BridgeError, match="not empty"):
        nb.export(V1, str(tmp_path / "full"), program=program)
    d = copy.deepcopy(V1)
    d["ns3"]["conditions"]["traffic"] = ["mixed"]
    nb.export(d, str(tmp_path / "mixed"), program=program)        # the ns-3 side can run it
    with pytest.raises(nb.Ns3BridgeError, match="'ns3.conditions.traffic: mixed' for compare"):
        nb.compare(d, nb.import_results(run_dir))


def test_cli_ns3(tmp_path, program, run_dir, capsys):
    study = tmp_path / "v1.json"
    study.write_text(json.dumps(V1), encoding="utf-8")
    assert main(["ns3", "export", str(study), "--out", str(tmp_path / "pkg"), "--program", program]) == 0
    assert "40 ns-3 runs of study V1" in capsys.readouterr().out
    bad = copy.deepcopy(V1)
    bad["ns3"]["rule"] = "daps"
    study.write_text(json.dumps(bad), encoding="utf-8")
    assert main(["ns3", "export", str(study), "--out", str(tmp_path / "pkg2"), "--program", program]) == 2
    assert "'ns3.rule: daps'" in capsys.readouterr().err and not (tmp_path / "pkg2").exists()
    assert main(["ns3", "import", run_dir, "--out", str(tmp_path / "ref.json")]) == 0
    assert "4 runs in 2 conditions" in capsys.readouterr().out
    assert main(["ns3", "compare", str(study), str(tmp_path / "ref.json")]) == 2
    assert "'ns3.rule: daps'" in capsys.readouterr().err
