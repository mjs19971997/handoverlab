# SPDX-License-Identifier: MIT
"""The release and CI helpers in tools/: release metadata and the fingerprint comparison across systems."""
import importlib.util
import json
import os

import handoverlab as hl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _tool(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_release_metadata_agree():
    mod = _tool("release_check")
    assert mod.check() == []
    assert mod.check(tag="v" + hl.__version__) == []
    assert mod.check(tag="v0.0.1") != []


def test_fingerprint_comparison_across_systems(tmp_path):
    mod = _tool("compare_fingerprints")
    from handoverlab.verify import golden
    ref = golden.load()
    same = dict(ref["versions"])
    other = dict(same, system="Linux" if same["system"] != "Linux" else "Windows")
    a = json.loads(json.dumps(ref["cases"]))
    b = json.loads(json.dumps(ref["cases"]))
    b["smoke"][0]["fingerprint"] = "f" * 64                  # another build: a moved event is no failure
    rows, failures, _ = mod.compare(ref, {"A": a, "B": b}, {"A": same, "B": other})
    assert not failures and rows[0]["A = B"] == "no" and rows[1]["A = B"] == "yes"
    _, failures, _ = mod.compare(ref, {"A": b}, {"A": same})  # the reference build must be identical
    assert len(failures) == 1 and "reference build" in failures[0]
    b["smoke"][0]["n_handovers"] += 50
    _, failures, _ = mod.compare(ref, {"A": a, "B": b}, {"A": same, "B": other})
    assert any("n_handovers" in f for f in failures)
    for name, doc in (("a.json", a), ("v.json", same)):
        (tmp_path / name).write_text(json.dumps(doc), encoding="utf-8")
    summary = tmp_path / "summary.md"
    assert mod.main(["--reference", golden.PATH, "X=%s" % (tmp_path / "a.json"), "--versions",
                     "X=%s" % (tmp_path / "v.json"), "--summary", str(summary)]) == 0
    assert "OK: counts agree everywhere" in summary.read_text(encoding="utf-8")
