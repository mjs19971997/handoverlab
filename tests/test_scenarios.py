# SPDX-License-Identifier: MIT
"""Built-in scenarios, scenario cards and their documentation pages."""
import os

import pytest

import handoverlab as hl
from handoverlab.cli import main
from handoverlab.config import ConfigError
from handoverlab.scenarios import DEFAULT_SOURCES, card_markdown, layout_svg

DOCS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "scenarios")
NAMES = ["dense-urban-2layer", "fr3-urban-15ghz", "highway-tr37885-30ghz", "highway-tr37885-4ghz",
         "indoor-office-4ghz", "ns3-urban-3.5ghz", "ntn-leo600-2ghz", "open-area-10ghz", "rural-700mhz", "smoke",
         "urban-grid-10ghz", "urban-grid-28ghz-beams"]


def test_builtin_names_and_cards():
    assert hl.scenario_names() == NAMES
    for name in NAMES:
        card = hl.scenario_card(name)
        sc = hl.builtin_scenario(name)
        assert card["name"] == name == sc.name
        assert card["purpose"] and card["limitations"] and card["references"] and card["since"]


def test_every_parameter_has_a_source():
    flat = []

    def walk(d, p=""):
        for k, v in d.items():
            if isinstance(v, dict):
                walk(v, p + k + ".")
            else:
                flat.append(p + k)
    walk(hl.Scenario().to_dict())
    assert set(flat) - {"name"} <= set(DEFAULT_SOURCES)


def test_urban_grid_card_equals_defaults():
    sc = hl.builtin_scenario("urban-grid-10ghz")
    # since 2.1.0 the card has the 1.6 m antenna of TR 37.885 vehicle type 2 (the default UE height is 1.5 m)
    assert sc.with_overrides({"name": "street-grid", "radio.ue_height_m": 1.5}) == hl.Scenario()


def test_base_and_name_in_configuration():
    exp = hl.load_config({"scenario": "smoke", "rules": [{"rule": "a3"}]})
    assert exp.scenario == hl.builtin_scenario("smoke")
    exp = hl.load_config({"scenario": {"base": "smoke", "mobility": {"users": 5}, "radio": {"carrier_ghz": 7.0}}})
    assert exp.scenario.mobility.users == 5 and exp.scenario.radio.carrier_ghz == 7.0
    assert exp.scenario.layout.blocks == (2, 2) and exp.scenario.mobility.profile == "v60"
    with pytest.raises(ConfigError, match="unknown built-in scenario"):
        hl.load_config({"scenario": "nope"})


@pytest.mark.parametrize("name", NAMES)
def test_documentation_pages_are_current(name):
    """docs/scenarios is generated with ``handoverlab scenarios --docs docs/scenarios``."""
    with open(os.path.join(DOCS, name + ".md"), encoding="utf-8") as f:
        assert f.read() == card_markdown(name, name + ".svg")
    with open(os.path.join(DOCS, name + ".svg"), encoding="utf-8") as f:
        assert f.read() == layout_svg(hl.builtin_scenario(name))


def test_cli_scenarios(capsys, tmp_path):
    assert main(["scenarios"]) == 0
    assert "smoke" in capsys.readouterr().out
    assert main(["scenarios", "smoke", "--markdown"]) == 0
    assert "## Known limitations" in capsys.readouterr().out
    assert main(["scenarios", "smoke"]) == 0
    assert "purpose:" in capsys.readouterr().out
    assert main(["scenarios", "nope"]) == 2
    assert main(["scenarios", "--docs", str(tmp_path)]) == 0
    assert sorted(os.listdir(tmp_path)) == sorted([n + ".md" for n in NAMES] + [n + ".svg" for n in NAMES])
