# SPDX-License-Identifier: MIT
"""Check that the release metadata agree before a release.

    python tools/release_check.py            # versions, changelog and citation metadata
    python tools/release_check.py --tag v1.0.0

Checks that the version in ``pyproject.toml``, ``src/handoverlab/__init__.py``
and ``CITATION.cff`` is the same, that ``CHANGELOG.md`` has a section for it,
that every changelog section has a link definition and every link points to
the repository, that ``.zenodo.json`` is valid and that, with ``--tag``, the
tag is ``v`` followed by the version.  The publish workflow runs it on the tag
of the release.  It needs only the standard library.
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = "https://github.com/mjs19971997/handoverlab"


def _read(name: str) -> str:
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read()


def _one(pattern: str, text: str, what: str, problems: List[str]) -> Optional[str]:
    m = re.search(pattern, text, re.M)
    if not m:
        problems.append("%s: version not found" % what)
        return None
    return m.group(1)


def check(tag: Optional[str] = None) -> List[str]:
    """List of problems (empty if the release metadata agree)."""
    problems: List[str] = []
    version = _one(r'^version = "([^"]+)"', _read("pyproject.toml"), "pyproject.toml", problems)
    init = _one(r'^__version__ = "([^"]+)"', _read(os.path.join("src", "handoverlab", "__init__.py")),
                "src/handoverlab/__init__.py", problems)
    cff = _read("CITATION.cff")
    cit = _one(r'^version: "?([^"\s]+)"?\s*$', cff, "CITATION.cff", problems)
    for what, v in (("src/handoverlab/__init__.py", init), ("CITATION.cff", cit)):
        if version and v and v != version:
            problems.append("%s has version %s, pyproject.toml %s" % (what, v, version))
    if not re.search(r"^date-released: \d{4}-\d{2}-\d{2}\s*$", cff, re.M):
        problems.append("CITATION.cff: date-released missing or not YYYY-MM-DD")

    log = _read("CHANGELOG.md")
    heads = re.findall(r"^## \[([^\]]+)\]", log, re.M)
    links = dict(re.findall(r"^\[([^\]]+)\]: (\S+)\s*$", log, re.M))
    if version and version not in heads:
        problems.append("CHANGELOG.md: no section '## [%s]'" % version)
    for h in heads:
        if h not in links:
            problems.append("CHANGELOG.md: no link definition for [%s]" % h)
    for name, url in links.items():
        if not url.startswith(REPO + "/"):
            problems.append("CHANGELOG.md: link [%s] does not point to %s" % (name, REPO))
    if heads and heads[0] == "Unreleased" and version and links.get("Unreleased", "").find("v%s...HEAD" % version) < 0:
        problems.append("CHANGELOG.md: [Unreleased] should compare v%s...HEAD" % version)

    try:
        zen = json.loads(_read(".zenodo.json"))
    except (OSError, ValueError) as e:
        problems.append(".zenodo.json: %s" % e)
    else:
        if not zen.get("creators") or not zen.get("title") or not zen.get("license"):
            problems.append(".zenodo.json: needs title, creators and license")

    if tag is not None and version and tag != "v" + version:
        problems.append("tag %s does not match the package version %s (expected v%s)" % (tag, version, version))
    return problems


def main(argv: Optional[List[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    tag = None
    if argv[:1] == ["--tag"] and len(argv) == 2:
        tag = argv[1]
        if tag.startswith("refs/tags/"):
            tag = tag[len("refs/tags/"):]
    elif argv:
        print(__doc__)
        return 2
    problems = check(tag)
    for p in problems:
        print("problem: %s" % p)
    print("release metadata: %s" % ("OK" if not problems else "%d problem(s)" % len(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
