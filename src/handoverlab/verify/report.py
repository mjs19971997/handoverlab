# SPDX-License-Identifier: MIT
"""Results of verification checks and their text and JSON report."""
from __future__ import annotations

import json
import platform
from dataclasses import asdict, dataclass, field
from typing import Callable, List, Optional

PASS, FAIL, NOTE = "PASS", "FAIL", "NOTE"


@dataclass
class Check:
    """Outcome of one check: PASS, FAIL or NOTE (information that cannot fail)."""
    group: str
    name: str
    status: str
    detail: str = ""


@dataclass
class Report:
    checks: List[Check] = field(default_factory=list)
    printer: Optional[Callable[[str], None]] = None
    group: str = ""

    def section(self, group: str, title: str) -> None:
        self.group = group
        self._say("\n== %s ==" % title)

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        return self._add(Check(self.group, name, PASS if ok else FAIL, detail))

    def note(self, name: str, detail: str = "") -> None:
        self._add(Check(self.group, name, NOTE, detail))

    def _add(self, c: Check) -> bool:
        self.checks.append(c)
        self._say("%s  %s%s" % (c.status, c.name, ("  [%s]" % c.detail) if c.detail else ""))
        return c.status != FAIL

    def _say(self, text: str) -> None:
        if self.printer:
            self.printer(text)

    @property
    def failed(self) -> List[Check]:
        return [c for c in self.checks if c.status == FAIL]

    @property
    def ok(self) -> bool:
        return not self.failed

    def summary(self) -> str:
        n = {s: sum(c.status == s for c in self.checks) for s in (PASS, FAIL, NOTE)}
        return "%d passed, %d failed, %d notes" % (n[PASS], n[FAIL], n[NOTE])

    def to_dict(self) -> dict:
        from ..io import provenance
        return dict(provenance=provenance(), ok=self.ok, summary=self.summary(),
                    checks=[asdict(c) for c in self.checks])

    def write_json(self, path: str) -> None:
        from ..io import _atomic_write_text
        _atomic_write_text(path, json.dumps(self.to_dict(), indent=1))


def header() -> str:
    from .. import __version__
    import numpy
    import scipy
    return ("HandoverLab %s verify  (Python %s, NumPy %s, SciPy %s, %s)"
            % (__version__, platform.python_version(), numpy.__version__, scipy.__version__, platform.platform()))
