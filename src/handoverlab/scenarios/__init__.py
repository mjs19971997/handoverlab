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
    "layout.site_spacing_m": "assumption (dense small cells along the streets; TR 37.885 Table 6.1.3-2 has "
                              "500 m macro sites in the urban grid)",
    "layout.site_offset_m": "assumption (sites on the pavement)",
    "layout.sites": "regular placement along the streets",
    "layout.lanes": "TR 37.885 Table A-1 (highway: 3 lanes per direction)",
    "layout.lane_width_m": "TR 37.885 Table A-1 (highway: 4 m lanes)",
    "layout.road_length_m": "TR 37.885 Table A-1 (highway: at least 2000 m)",
    "layout.sites_file": "none (sites from the layout)",
    "radio.carrier_ghz": "assumption (upper mid-band, 7-24 GHz)",
    "radio.bandwidth_mhz": "assumption",
    "radio.tx_power_dbm": "assumption (small cell; TR 37.885 Table 6.1.1-2 has 43 dBm for its macro sites)",
    "radio.bs_gain_db": "assumption (beam gain, no beam management)",
    "radio.ue_gain_db": "assumption",
    "radio.noise_figure_db": "assumption (typical UE noise figure)",
    "radio.isolation": "assumption (mean-to-peak gain of an interfering data beam)",
    "radio.bs_height_m": "TR 38.901 Table 7.4.1-1 (UMi: 10 m)",
    "radio.ue_height_m": "ITU-R M.2412-0 Table 5 (outdoor UEs: 1.5 m), within 1.5-22.5 m of TR 38.901 Table 7.4.1-1",
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
    "protocol.rlm_holdoff_s": "off by default; TS 38.133 clause 8.1: out-of-sync evaluation of 0.2 s on a new cell",
    "protocol.exec_can_fail": "TR 36.839: the execution fails when the target is below Qout",
    "radio.penetration_db": "off by default; TR 38.901 clause 7.4.3.2: 9 dB in a standard car",
    "radio.penetration_sd_db": "off by default; TR 38.901 clause 7.4.3.2: 5 dB in a standard car",
    "traffic.model": "fixed: constant service rates (the model of 1.0)",
    "traffic.period_s": "periodic model: 20 ms, as VoIP",
    "traffic.packet_bytes": "periodic model: assumption",
    "traffic.ftp_file_bytes": "TR 36.814 A.2.1.3 (FTP model 3: 0.5 Mbyte)",
    "traffic.ftp_rate_hz": "ftp3 model: assumption (file arrival rate per user)",
    "radio.energy_p0_w": "EARTH model, micro base station (Auer et al. 2011): 56 W",
    "radio.energy_slope": "EARTH model, micro base station (Auer et al. 2011): 2.6",
    "traffic.services": "TS 23.501 Table 5.7.4-1 (5QI); thresholds are assumptions",
    "traffic.se_max": "assumption (spectral-efficiency cap)",
    "traffic.hotspot_share": "assumption",
    "traffic.hotspot_load": "assumption",
    "traffic.normal_load": "assumption",
    "traffic.load_tau_s": "assumption",
    "traffic.rate_scale": "assumption",
    "traffic.label_load": "assumption (all cells transmit for the label)",
    "mobility.users": "assumption",
    "mobility.profile": "TR 37.885 clause 6.1.2 (urban option A: 60 km/h); the profile veh16 spreads the speed "
                        "over 52-63 km/h (assumption); see the user guide",
    "mobility.groups": "profile",
    "run.duration_s": "numerical setting",
    "run.warmup_s": "numerical setting",
    "radio.scs_khz": "unset: 30 kHz up to 7.125 GHz, 120 kHz above (assumption)",
    "radio.beams": "off by default (antenna abstraction); TR 38.901 clause 7.3 when set",
    "radio.layers": "off by default (one carrier)",
    "radio.map_file": "off by default (statistical map); TR 38.901 clause 8 (map-based model) when set",
    "radio.map_sha256": "filled from the map file when the scenario is loaded",
    "protocol.meas_periods": "sample: one L1 sample per L1 period (the model of 1.x)",
    "protocol.ssb_period_s": "assumption (20 ms SSB and SMTC periodicity)",
    "protocol.gap_pattern": "TS 38.133 Table 9.1.2-1 (gap pattern 0: MGL 6 ms, MGRP 40 ms)",
    "protocol.fr2_power_class": "assumption (FR2 power class 3, handheld UE)",
    "protocol.rlm_eval": "fixed: qout_window_s and qin_window_s (the model of 1.x)",
}


#: deprecated built-in scenarios: name -> (deprecated since, removed in, replacement, reason)
DEPRECATED: Dict[str, tuple] = {
    "highway-10ghz": ("1.11", "2.0", "'highway-tr37885-30ghz' or 'highway-tr37885-4ghz'",
                      "it combines the 35 m roadside offset of TR 36.885 option 1 with the 500 m spacing of option 2, "
                      "uses 10 GHz, which TR 37.885 does not, and has neither the LOS-only links nor the wrap-around "
                      "of TR 37.885"),
}


def _read(name: str) -> Dict[str, Any]:
    import yaml
    path = os.path.join(_DIR, name + ".yaml")
    if not os.path.exists(path):
        raise ConfigError("unknown built-in scenario %r; known: %s" % (name, ", ".join(scenario_names())))
    if name in DEPRECATED:
        from ..stability import deprecated
        since, removed, instead, why = DEPRECATED[name]
        deprecated("the built-in scenario %r (%s)" % (name, why), since=since, removed_in=removed, instead=instead)
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def scenario_names(deprecated: bool = False) -> List[str]:
    """Names of the built-in scenarios; deprecated ones (:data:`DEPRECATED`) only with ``deprecated=True``."""
    names = sorted(f[:-5] for f in os.listdir(_DIR) if f.endswith(".yaml"))
    return names if deprecated else [n for n in names if n not in DEPRECATED]


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


_KEYS_1_7 = ("layout.area_m", "layout.min_site_distance_m", "radio.soft_los", "radio.soft_los_d_m",
             "radio.shadow_los_far_db", "protocol.cmd_during_t310", "protocol.t304_s",
             "radio.scs_khz", "radio.beams", "radio.layers", "protocol.meas_periods", "protocol.ssb_period_s",
             "protocol.gap_pattern", "protocol.fr2_power_class", "protocol.rlm_eval", "radio.map_file",
             "radio.map_sha256")


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
    for key in _KEYS_1_7:                           # keys of 1.7.0 and later: shown only where a card sets them
        if key in flat and flat[key] == default.get(key):
            del flat[key]
    import dataclasses

    from ..config import BeamConfig
    bdef = _flat({"radio": {"beams": dataclasses.asdict(BeamConfig())}})   # defaults of the beam keys (1.10.0)
    for key, value in flat.items():
        if key == "name":
            continue
        v = _fmt(value)
        if key in bdef and key not in default:
            if _fmt(value) == _fmt(bdef[key]):
                L.append("| `%s` | %s | default of the beam model (user guide) |" % (key, v))
                continue
            default[key] = bdef[key]
        if value != default.get(key):
            v = "**%s**" % v
        src, k = sources.get(key), key
        while src is None and "." in k:                 # nested keys (beams, layers): the source of the parent
            k = k.rsplit(".", 1)[0]
            src = sources.get(k)
        L.append("| `%s` | %s | %s |" % (key, v, src or ""))
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
    fx0, fx1, fy0, fy1 = lay.xmin, lay.xmax, lay.ymin, lay.ymax
    if lay.images is not None:                      # sites far from the road (hexagonal highway): show them all
        pad = 60.0
        fx0, fx1 = min(fx0, lay.sites[:, 0].min() - pad), max(fx1, lay.sites[:, 0].max() + pad)
        fy0, fy1 = min(fy0, lay.sites[:, 1].min() - pad), max(fy1, lay.sites[:, 1].max() + pad)
    w, h = fx1 - fx0, fy1 - fy0
    s = width_px / w
    H = h * s

    def X(x):
        return (x - fx0) * s

    def Y(y):
        return H - (y - fy0) * s

    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
           % (width_px, round(H) + 24, width_px, round(H) + 24),
           '<rect x="0" y="0" width="%d" height="%d" fill="#f4f4f0" stroke="#999"/>' % (width_px, round(H))]
    for x0, y0, x1, y1 in lay.buildings:
        out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#b9b9b0"/>'
                   % (X(x0), Y(y1), (x1 - x0) * s, (y1 - y0) * s))
    if lay.kind == "highway":
        half = len(lay.ys) / 2.0 * lay.street_width
        if lay.images is None:
            out.append('<rect x="0" y="%.1f" width="%d" height="%.1f" fill="#b9b9b0"/>'
                       % (Y(half), width_px, 2.0 * half * s))
            out.append('<line x1="0" y1="%.1f" x2="%d" y2="%.1f" stroke="#f4f4f0" stroke-width="1"/>'
                       % (Y(0.0), width_px, Y(0.0)))
        else:                                       # the simulated road with its wrap-around period
            out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#8a8a80"/>'
                       % (X(lay.xmin), Y(half), (lay.xmax - lay.xmin) * s, max(2.0 * half * s, 2.0)))
    for x, y in lay.sites:
        out.append('<circle cx="%.1f" cy="%.1f" r="3" fill="#c0392b"/>' % (X(x), Y(y)))
    out.append('<text x="4" y="%d" font-family="sans-serif" font-size="12" fill="#333">%s: %d sites, %.0f m x %.0f m'
               ' (grey: %s, red: sites)</text>' % (round(H) + 17, scenario.name, lay.n_sites, w, h,
                                                   "road" if lay.kind == "highway" else "buildings"))
    out.append("</svg>")
    return "\n".join(out) + "\n"


__all__ = ["DEFAULT_SOURCES", "scenario_names", "scenario_card", "builtin_scenario", "resolve", "merge",
           "card_markdown", "layout_svg"]
