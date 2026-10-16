# SPDX-License-Identifier: MIT
"""Compare golden event-log fingerprints computed on several systems.

    python -m handoverlab.verify.golden > golden-Linux.json          # on each system
    python tools/compare_fingerprints.py --reference src/handoverlab/verify/data/golden.json \\
        Linux=golden-Linux.json Windows=golden-Windows.json \\
        [--versions Linux=versions-Linux.json Windows=versions-Windows.json] [--summary FILE]

For every golden run it reports whether the fingerprints of the systems are identical with each
other and with the reference.  Like ``handoverlab verify``, it fails (exit status 1) if

* a system with the NumPy / SciPy build and operating system of the reference does not reproduce
  the reference fingerprints exactly, or
* the event counts of two systems, or of a system and the reference, differ by more than 10 %
  (at least 3 events).

Different fingerprints on different builds are reported but are not a failure: the random
streams and floating-point sums may differ in the last bits there and move single events.
``--summary`` appends the table as Markdown (for ``$GITHUB_STEP_SUMMARY``).  Standard library only.
"""
from __future__ import annotations

import itertools
import json
import sys
from typing import Dict, List, Optional

COUNTS = ("n_events", "n_attempts", "n_handovers", "n_unnecessary", "n_pingpong", "n_failures", "n_preparations")
BUILD = ("numpy", "scipy", "system", "machine")


def _load(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _pairs(args: List[str]) -> Dict[str, str]:
    out = {}
    for a in args:
        name, sep, path = a.partition("=")
        if not sep:
            raise SystemExit("expected NAME=FILE, got %r" % a)
        out[name] = path
    return out


def _close(a: dict, b: dict) -> List[str]:
    return [k for k in COUNTS if k in a and k in b and abs(a[k] - b[k]) > max(3, 0.10 * abs(b[k]))]


def compare(ref: dict, runs: Dict[str, dict], versions: Optional[Dict[str, dict]] = None):
    """(rows, failures): one row per golden run, and the failure messages."""
    versions = versions or {}
    names = list(runs)
    same_build = {n: n in versions and all(versions[n].get(k) == ref["versions"].get(k) for k in BUILD)
                  for n in names}
    rows, failures = [], []
    for case, want_runs in ref["cases"].items():
        for i, want in enumerate(want_runs):
            label = "%s / %s" % (case, want["rule"])
            got = {n: runs[n][case][i] for n in names}
            row = dict(run=label, ref=want["fingerprint"][:12])
            for n in names:
                g = got[n]
                ident = g["fingerprint"] == want["fingerprint"]
                row[n] = "%s %s" % (g["fingerprint"][:12], "= ref" if ident else "differs")
                if not ident and same_build[n]:
                    failures.append("%s: %s has the reference build but a different fingerprint" % (label, n))
                bad = _close(g, want)
                if bad:
                    failures.append("%s: counts of %s differ from the reference: %s"
                                    % (label, n, ", ".join("%s %d/%d" % (k, g[k], want[k]) for k in bad)))
            for a, b in itertools.combinations(names, 2):
                key = "%s = %s" % (a, b)
                row[key] = "yes" if got[a]["fingerprint"] == got[b]["fingerprint"] else "no"
                bad = _close(got[a], got[b])
                if bad:
                    failures.append("%s: counts differ between %s and %s: %s" % (label, a, b, ", ".join(bad)))
            rows.append(row)
    return rows, failures, same_build


def markdown(rows: List[dict], failures: List[str], same_build: Dict[str, bool], ref: dict) -> str:
    cols = list(rows[0]) if rows else []
    rv = ref["versions"]
    lines = ["## Golden fingerprints across systems", "",
             "Reference: Python %s, NumPy %s, SciPy %s, %s %s." % (rv.get("python"), rv.get("numpy"),
                                                                rv.get("scipy"), rv.get("system"), rv.get("machine")),
             "Same build as the reference: %s." % ", ".join("%s %s" % (n, "yes" if s else "no")
                                                           for n, s in same_build.items()), "",
             "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(str(r[c]) for c in cols) + " |" for r in rows]
    n_id = sum(all(v == "yes" for k, v in r.items() if " = " in k) for r in rows)
    lines += ["", "Identical across systems: %d of %d runs." % (n_id, len(rows)), ""]
    lines += ["**%s**" % ("FAILED: " + "; ".join(failures) if failures else "OK: counts agree everywhere"), ""]
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    ref_path, summary, files, vers, mode = None, None, [], [], "files"
    it = iter(argv)
    for a in it:
        if a == "--reference":
            ref_path = next(it)
        elif a == "--summary":
            summary = next(it)
        elif a == "--versions":
            mode = "versions"
        elif a.startswith("--"):
            print(__doc__)
            return 2
        else:
            (vers if mode == "versions" else files).append(a)
    if not ref_path or not files:
        print(__doc__)
        return 2
    ref = _load(ref_path)
    runs = {n: _load(p) for n, p in _pairs(files).items()}
    versions = {n: _load(p) for n, p in _pairs(vers).items()}
    rows, failures, same = compare(ref, runs, versions)
    text = markdown(rows, failures, same, ref)
    print(text)
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
