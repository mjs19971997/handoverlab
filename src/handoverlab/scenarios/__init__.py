# SPDX-License-Identifier: MIT
"""Built-in scenarios and their scenario cards.

A built-in scenario is a named, documented starting point.  Its *card* (one
YAML file per scenario in this package) holds the scenario values that differ
from the defaults, the purpose, the source of every parameter, the known
limitations and the reference results the scenario was checked against.
:func:`card_markdown` turns a card into a page of the documentation and
:func:`layout_svg` draws its layout.

Use a built-in scenario by name::

    sc = hl.builtin_scenario("smoke")

or in a configuration file, alone or as the base of your own values::

    scenario: smoke
    scenario: {base: urban-grid-10ghz, mobility: {users: 60}}
"""
from __future__ import annotations

import copy
import os
from typing import Any, Dict, List

from ..config import ConfigError, Scenario

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cards")

#: source of every scenario value that is not overridden by a card
DEFAULT_SOURCES: Dict[str, str] = {
    "layout.kind": "TR 37.885 Annex A (urban grid)",
    "layout.blocks": "TR 37.885 Table A-1 (minimum 3 x 3 blocks)",
    "layout.pitch_m": "TR 37.885 Annex A (433 m x 250 m)",
    "layout.street_width_m": "TR 37.885 Annex A (20 m)",
    "layout.site_spacing_m": "assumption (dense small cells along the streets)",
    "layout.site_offset_m": "assumption (sites on the pavement)",
    "layout.sites": "regular placement along the streets",
    "layout.lanes": "TR 37.885 Table A-1 (highway: 3 lanes per direction)",
    "layout.lane_width_m": "TR 37.885 Table A-1 (highway: 4 m lanes)",
    "layout.road_length_m": "TR 37.885 Table A-1 (highway: at least 2000 m)",
    "layout.sites_file": "none (sites from the layout)",
    "radio.carrier_ghz": "assumption (upper mid-band, 7-24 GHz)",
    "radio.bandwidth_mhz": "assumption",
    "radio.tx_power_dbm": "assumption (small cell)",
    "radio.bs_gain_db": "assumption (beam gain, no beam management)",
    "radio.ue_gain_db": "assumption",
    "radio.noise_figure_db": "assumption (typical UE noise figure)",
    "radio.isolation": "assumption (mean-to-peak gain of an interfering data beam)",
    "radio.bs_height_m": "TR 38.901 Table 7.4.1-1 (UMi: 10 m)",
    "radio.ue_height_m": "TR 38.901 Table 7.4.1-1 (1.5 m)",
    "radio.pathloss": "TR 38.901 Table 7.4.1-1",
    "radio.shadow_los_db": "TR 38.901 Table 7.4.1-1 (UMi and UMa LOS: 4 dB)",
    "radio.shadow_nlos_db": "TR 38.901 Table 7.4.1-1 (UMi NLOS: 7.82 dB)",
    "radio.shadow_decorr_m": "TR 38.901 Table 7.5-6 (UMi: 10 m LOS, 13 m NLOS)",
    "radio.shadow_site_corr": "assumption (correlation between sites)",
    "radio.place_share": "assumption (blockage tied to place)",
    "radio.clutter_los": "TR 38.901 clause 7.6.3.3 (spatially consistent LOS state)",
    "radio.los_corr_m": "TR 38.901 Table 7.6.3.1-2 (LOS/NLOS state, UMi and UMa: 50 m)",
    "radio.time_var_db": "assumption (moving blockers)",
    "radio.time_var_tau_s": "assumption",
    "radio.l1_error_db": "assumption (error of one L1 RSRP sample)",
    "radio.map_res_m": "numerical setting",
    "protocol.step_s": "numerical setting",
    "protocol.l1_period_s": "assumption (L1 sample period)",
    "protocol.l3_k": "TS 38.331 clause 5.5.3.2",
    "protocol.label_period_s": "numerical setting",
    "protocol.report_interval_s": "TS 38.331 reportInterval (ms120)",
    "protocol.qout_db": "TR 36.839 (Qout -8 dB)",
    "protocol.qin_db": "TR 36.839 (Qin -6 dB)",
    "protocol.qout_window_s": "TS 38.133 (evaluation period, 200 ms)",
    "protocol.qin_window_s": "TS 38.133 (evaluation period, 100 ms)",
    "protocol.n310": "TR 36.839",
    "protocol.n311": "TR 36.839",
    "protocol.t310_s": "TR 36.839 (1 s)",
    "protocol.prep_s": "TR 36.839 (50 ms)",
    "protocol.exec_s": "TR 36.839 (40 ms)",
    "protocol.reest_s": "TR 36.842 (assumption: 1 s outage)",
    "protocol.cho_recovery_s": "TS 38.300 clause 9.2.3.4 (recovery into a prepared cell; assumption 0.4 s)",
    "protocol.pingpong_s": "TR 36.839 (minimum time of stay, 1 s)",
    "protocol.cfg_loss_as_failure": "check mode only",
    "protocol.lm_load": "off by default: link monitoring sees the load of the data channel (calibration option)",
    "protocol.lm_load_per_ue": "off by default (calibration option)",
    "protocol.exec_can_fail": "TR 36.839: the execution fails when the target is below Qout",
    "traffic.services": "TS 23.501 Table 5.7.4-1 (5QI); thresholds are assumptions",
    "traffic.se_max": "assumption (spectral-efficiency cap)",
    "traffic.hotspot_share": "assumption",
    "traffic.hotspot_load": "assumption",
    "traffic.normal_load": "assumption",
    "traffic.load_tau_s": "assumption",
    "traffic.rate_scale": "assumption",
    "traffic.label_load": "assumption (all cells transmit for the label)",
    "mobility.users": "assumption",
    "mobility.profile": "TR 37.885 clause 6.1.2 (urban: 60 km/h); see the user guide",
    "mobility.groups": "profile",
    "run.duration_s": "numerical setting",
    "run.warmup_s": "numerical setting",
}


def _read(name: str) -> Dict[str, Any]:
    import yaml
    path = os.path.join(_DIR, name + ".yaml")
    if not os.path.exists(path):
        raise ConfigError("unknown built-in scenario %r; known: %s" % (name, ", ".join(scenario_names())))
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def scenario_names() -> List[str]:
    """Names of the built-in scenarios."""
    return sorted(f[:-5] for f in os.listdir(_DIR) if f.endswith(".yaml"))


def scenario_card(name: str) -> Dict[str, Any]:
    """The scenario card of ``name`` as a dictionary (``scenario`` holds the values that differ from the defaults)."""
    return _read(name)


def builtin_scenario(name: str) -> Scenario:
    """The built-in scenario ``name``."""
    d = copy.deepcopy(_read(name)["scenario"])
    d.setdefault("name", name)
    return Scenario.from_dict(d)


def merge(base: Dict[str, Any], over: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge of two scenario dictionaries (``over`` wins)."""
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def resolve(data: Any) -> Dict[str, Any]:
    """A ``scenario`` entry of a configuration -> plain dictionary.

    ``"smoke"`` (a name) or ``{"base": "smoke", ...}`` start from a built-in
    scenario; any other mapping is returned unchanged.
    """
    if isinstance(data, str):
        d = copy.deepcopy(_read(data)["scenario"])
        d.setdefault("name", data)
        return d
    if isinstance(data, dict) and "base" in data:
        rest = {k: v for k, v in data.items() if k != "base"}
        if not isinstance(data["base"], str):
            raise ConfigError("scenario.base: expected the name of a built-in scenario")
        return merge(resolve(data["base"]), rest)
    return data


def _flat(d: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(_flat(v, prefix + k + "."))
        else:
            out[prefix + k] = v
    return out


def _fmt(v: Any) -> str:
    if v is None:
        return "none"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return ("%.6g" % v)
    if isinstance(v, (list, tuple)):
        if v and isinstance(v[0], dict):
            return "%d entries" % len(v)
        if len(v) > 4:
            return "%d entries" % len(v)
        return "[" + ", ".join(_fmt(x) for x in v) + "]"
    return str(v)


def card_markdown(name: str, figure: str = None) -> str:
    """The scenario card ``name`` as a Markdown page (``figure``: file name of the layout figure)."""
    card = _read(name)
    sc = builtin_scenario(name)
    default = _flat(Scenario().to_dict(full=True))
    sources = dict(DEFAULT_SOURCES)
    sources.update(card.get("sources") or {})
    L = ["# Scenario card: `%s`" % name, "", "*%s*  " % card["title"],
         "Available since version %s. Use it as `scenario: %s` in a configuration file or "
         "`hl.builtin_scenario(\"%s\")` in Python." % (card["since"], name, name), ""]
    L += ["## Purpose", "", card["purpose"].strip(), ""]
    if figure:
        L += ["## Layout", "", "![Layout of %s](%s)" % (name, figure), "", card.get("layout_note", "").strip(), ""]
    L += ["## Parameters", "",
          "Values in **bold** differ from the HandoverLab defaults.", "",
          "| Key | Value | Source |", "|---|---|---|"]
    flat = _flat(sc.to_dict(full=sc.layout.kind == "highway"))
    for key, value in flat.items():
        if key == "name":
            continue
        v = _fmt(value)
        if value != default.get(key):
            v = "**%s**" % v
        L.append("| `%s` | %s | %s |" % (key, v, sources.get(key, "")))
    L += ["", "## Known limitations", ""]
    L += ["- %s" % x.strip() for x in card.get("limitations", [])]
    L += ["", "## Reference results", ""]
    L += ["- %s" % x.strip() for x in card.get("references", [])]
    L.append("")
    return "\n".join(L)


def layout_svg(scenario: Scenario, width_px: int = 640) -> str:
    """A plain SVG drawing of the layout of ``scenario``: buildings, streets and sites."""
    from ..layout import make_layout
    lay = make_layout(scenario.layout)
    w, h = lay.xmax - lay.xmin, lay.ymax - lay.ymin
    s = width_px / w
    H = h * s

    def X(x):
        return (x - lay.xmin) * s

    def Y(y):
        return H - (y - lay.ymin) * s

    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
           % (width_px, round(H) + 24, width_px, round(H) + 24),
           '<rect x="0" y="0" width="%d" height="%d" fill="#f4f4f0" stroke="#999"/>' % (width_px, round(H))]
    for x0, y0, x1, y1 in lay.buildings:
        out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#b9b9b0"/>'
                   % (X(x0), Y(y1), (x1 - x0) * s, (y1 - y0) * s))
    if lay.kind == "highway":
        half = len(lay.ys) / 2.0 * lay.street_width
        out.append('<rect x="0" y="%.1f" width="%d" height="%.1f" fill="#b9b9b0"/>'
                   % (Y(half), width_px, 2.0 * half * s))
        out.append('<line x1="0" y1="%.1f" x2="%d" y2="%.1f" stroke="#f4f4f0" stroke-width="1"/>'
                   % (Y(0.0), width_px, Y(0.0)))
    for x, y in lay.sites:
        out.append('<circle cx="%.1f" cy="%.1f" r="3" fill="#c0392b"/>' % (X(x), Y(y)))
    out.append('<text x="4" y="%d" font-family="sans-serif" font-size="12" fill="#333">%s: %d sites, %.0f m x %.0f m'
               ' (grey: %s, red: sites)</text>' % (round(H) + 17, scenario.name, lay.n_sites, w, h,
                                                   "road" if lay.kind == "highway" else "buildings"))
    out.append("</svg>")
    return "\n".join(out) + "\n"


__all__ = ["DEFAULT_SOURCES", "scenario_names", "scenario_card", "builtin_scenario", "resolve", "merge",
           "card_markdown", "layout_svg"]
