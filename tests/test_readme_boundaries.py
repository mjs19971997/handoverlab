# SPDX-License-Identifier: MIT
"""The model-boundary table of the README stays in step with the code (since 2.1.0)."""
import os
import re

import handoverlab as hl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _section(title):
    with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
        text = f.read()
    i = text.index("## " + title)
    j = text.index("\n## ", i + 3)
    return text[i:j]


def test_every_rule_card_and_layout_is_in_the_boundary_table():
    sec = _section("Model boundaries")
    named = set(re.findall(r"`([a-z0-9_.\-]+)`", sec))
    from handoverlab.rules import get_rule_class
    builtin = {k for k in hl.available_rules() if get_rule_class(k).__module__.startswith("handoverlab.")}
    assert builtin <= named                          # rules registered by other tests are left out
    assert set(hl.scenario_names()) <= named
    assert {"street_grid", "open_area", "highway", "indoor", "ntn"} <= named


def test_scope_names_the_three_paths_and_claims_no_6g_procedure():
    sec = _section("Scope: 5G-Advanced and beyond 5G")
    assert "TR 38.914" in sec and "no handover procedure" in sec
    for path in ("FR3", "Non-terrestrial", "Learning-based"):
        assert path in sec
