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
    "radio.shadow_decorr_m": "TR 38.901 Table 7.5-6 Part-1 (UMi: 10 m LOS, 13 m NLOS; the LOS value is used for "
                             "both, see the limitations)",
    "radio.shadow_site_corr": "unset: uncorrelated between sites, TR 38.901 clause 7.5 step 4 (radio.channel_detail "
                              "simple: 0.5)",
    "radio.place_share": "assumption (blockage tied to place)",
    "radio.clutter_los": "TR 38.901 clause 7.6.3.3 (spatially consistent LOS state), applied on top of the "
                         "building geometry",
    "radio.channel_detail": "3gpp: the large-scale channel of TR 38.901 V19.5.0 (since 2.1.0; simple: that of 2.0.0)",
    "ntn.hpbw_deg": "unset: the tabled 3 dB beamwidth of TR 38.821 Tables 6.1.1.1-1/-2 (Table 6.1.1.1-4: only the "
                    "3 dB beamwidth is used)",
    "ntn.los_model": "probability: the LOS probability of TR 38.811 Table 6.6.1-1",
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
    "protocol.reest_s": "assumption (1 s outage); TS 38.133 6.2.1.2.1 bounds the delay by 50 ms + cell "
                        "identification (FR1: 200 ms known, 800 ms unknown cell, Table 6.2.1.2.1-1) + system "
                        "information + PRACH; TR 36.842 Table E.1-2 uses 250 ms",
    "protocol.cho_recovery_s": "TS 38.300 clauses 9.2.3.1 and 9.2.7 (recovery into a CHO candidate; assumption 0.4 s)",
    "protocol.pingpong_s": "TR 36.839 (minimum time of stay, 1 s)",
    "protocol.cfg_loss_as_failure": "check mode only",
    "protocol.lm_load": "off by default: link monitoring sees the load of the data channel (calibration option)",
    "protocol.lm_load_per_ue": "off by default (calibration option)",
    "protocol.rlm_holdoff_s": "0.2 s since 2.0.0: an interpretation of TS 38.133 8.1.2.2 (evaluation over the last "
                              "T_Evaluate_out, 200 ms in FR1) on a newly joined cell",
    "protocol.exec_can_fail": "TR 36.839: the execution fails when the target is below Qout",
    "protocol.ns3_oos_rx": "off by default (3GPP model); imitates ns-3 / 5G-LENA v5.1 (NrUePhy NumQoutEvalSf: 200 "
                           "control receptions), not 3GPP",
    "protocol.ns3_ins_rx": "ns-3 / 5G-LENA v5.1 (NrUePhy NumQinEvalSf: 100 control receptions); with ns3_oos_rx only",
    "protocol.ns3_ctrl_hz": "measured in ns-3 / 5G-LENA runs at light traffic (control receptions per second of a "
                            "user, base); with ns3_oos_rx only",
    "protocol.ns3_ctrl_per_ue_hz": "measured in ns-3 / 5G-LENA runs at light traffic (control receptions per second "
                                   "per user served by the cell); with ns3_oos_rx only",
    "radio.penetration_db": "off by default; TR 38.901 clause 7.4.3.2: 9 dB in a standard car",
    "radio.penetration_sd_db": "off by default; TR 38.901 clause 7.4.3.2: 5 dB in a standard car",
    "radio.o2i_model": "low: TR 38.901 Table 7.4.3-2 (applies to the users of an indoor speed group only)",
    "radio.o2i_d_in_max_m": "unset: TR 38.901 clause 7.4.3.1 (25 m UMa/UMi, 10 m RMa, SMa 10 m / 25 m)",
    "radio.building_los": "true: buildings block the links of street-level sites",
    "radio.env_height_m": "unset: TR 38.901 Table 7.4.1-1 note 1",
    "radio.vegetation": "SMa only: TR 38.901 Table 7.4.2-1 (0 % vegetation)",
    "traffic.model": "fixed: constant service rates (the model of 1.0)",
    "traffic.period_s": "periodic model: 20 ms, as VoIP",
    "traffic.packet_bytes": "periodic model: assumption",
    "traffic.ftp_file_bytes": "FTP model 3 (TR 36.872 Annex A.1) with 0.5 Mbyte files (TR 38.802 Table A.2.1-1; "
                              "TR 38.821 Table 6.1.1.1-7)",
    "traffic.ftp_rate_hz": "ftp3 model: assumption (file arrival rate per user)",
    "radio.energy_p0_w": "EARTH model, micro base station (Auer et al. 2011, Table 2): 56 W",
    "radio.energy_slope": "EARTH model, micro base station (Auer et al. 2011, Table 2): 2.6",
    "radio.energy_ntrx": "EARTH model, micro base station (Auer et al. 2011, Eq. 1 and Table 2): 2 transceivers",
    "radio.fast_fading": "off by default; TR 38.901 clause 7.7.2 (TDL-A .. TDL-E)",
    "protocol.scheduler": "off by default (rate model); rr / pf slot scheduler with TS 38.214 MCS and TBS",
    "protocol.harq_max_tx": "assumption (transmissions per TB; the network's choice)",
    "protocol.harq_rtt_slots": "assumption (HARQ round trip in slots)",
    "protocol.l2s_loss_db": "assumption (implementation loss of the block-error model)",
    "protocol.buffers": "off by default; am / um: PDCP / RLC buffers and data forwarding at handover (TS 38.300 "
                        "9.2.3.2.2, 9.2.3.2.3)",
    "protocol.forwarding": "TS 38.300 9.2.3.2.3 (the network may forward; with buffers)",
    "protocol.early_forwarding": "TS 38.300 9.2.3.4.4 / 9.2.3.5.2 (CHO and LTM: late forwarding unless set)",
    "protocol.xn_delay_s": "assumption (Xn forwarding delay; with buffers)",
    "protocol.discard_timer_s": "TS 38.331 PDCP-Config discardTimer (unset: infinity; with buffers)",
    "protocol.sdu_bytes": "assumption (SDU size for the SDU counts; unset: packet_bytes or 1500 bytes)",
    "radio.delay_spread_ns": "TR 38.901 Table 7.7.3-1 (nominal delay spread; used with fast_fading)",
    "radio.fading_k_db": "TR 38.901 clause 7.7.6 (unset: the K-factor of the table)",
    "traffic.services": "TS 23.501 Table 5.7.4-1 (5QI); thresholds are assumptions",
    "traffic.se_max": "assumption (spectral-efficiency cap)",
    "traffic.hotspot_share": "assumption",
    "traffic.hotspot_load": "assumption",
    "traffic.normal_load": "assumption",
    "traffic.load_tau_s": "assumption",
    "traffic.rate_scale": "assumption",
    "traffic.label_load": "assumption (all cells transmit for the label)",
    "mobility.users": "assumption",
    "mobility.profile": "TR 37.885 clause 6.1.2 (urban option A: 60 km/h in all lanes) and Table A-1 (2 lanes of "
                        "3.5 m per direction): profile v60 (since 2.0.0)",
    "mobility.groups": "profile",
    "run.duration_s": "numerical setting",
    "run.warmup_s": "numerical setting",
    "radio.scs_khz": "unset: 30 kHz up to 7.125 GHz, 120 kHz above (assumption)",
    "radio.beams": "off by default (antenna abstraction); TR 38.901 clause 7.3 when set",
    "radio.layers": "off by default (one carrier)",
    "radio.map_file": "off by default (statistical map); TR 38.901 clause 8 (map-based model) when set",
    "radio.map_sha256": "filled from the map file when the scenario is loaded",
    "radio.breakpoint_c_mps": "TR 38.901 Table 7.4.1-1 notes 1 and 5 (c = 3.0e8 m/s in the breakpoint distances)",
    "radio.pl_min_distance_m": "TR 38.901 Table 7.4.1-1 (applicability range of RMa, UMa, UMi: 10 m <= d2D)",
    "protocol.meas_periods": "sample: one L1 sample per L1 period (the model of 1.x)",
    "protocol.ssb_period_s": "assumption (20 ms SSB and SMTC periodicity)",
    "protocol.gap_pattern": "TS 38.133 Table 9.1.2-1 (gap pattern 0: MGL 6 ms, MGRP 40 ms)",
    "protocol.fr2_power_class": "assumption (FR2 power class 3, handheld UE)",
    "protocol.rlm_eval": "fixed: qout_window_s and qin_window_s (the model of 1.x)",
}


#: deprecated built-in scenarios: name -> (deprecated since, removed in, replacement, reason)
DEPRECATED: Dict[str, tuple] = {}


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
             "radio.map_sha256", "radio.channel_detail", "radio.o2i_model", "radio.o2i_d_in_max_m",
             "radio.building_los", "radio.env_height_m", "radio.vegetation", "protocol.dc")

_GRID_GEOMETRY = ("layout.blocks", "layout.pitch_m", "layout.street_width_m")
_HIGHWAY_KEYS = ("layout.lanes", "layout.lane_width_m", "layout.road_length_m", "layout.wrap", "layout.highway_sites")
_NTN_UNUSED_RADIO = ("radio.bs_gain_db", "radio.bs_height_m", "radio.ue_height_m", "radio.pathloss",
                     "radio.shadow_los_db", "radio.shadow_nlos_db", "radio.shadow_los_far_db", "radio.shadow_decorr_m",
                     "radio.shadow_site_corr", "radio.place_share", "radio.clutter_los", "radio.los_corr_m",
                     "radio.soft_los", "radio.soft_los_d_m", "radio.los_model", "radio.breakpoint_c_mps",
                     "radio.pl_min_distance_m", "radio.map_res_m", "radio.penetration_db", "radio.penetration_sd_db")


def unused_keys(sc: Scenario) -> set:
    """Scenario keys that the layout kind and the radio model of ``sc`` do not read (since 2.1.0); the card pages
    leave them out of the parameter table."""
    L, R = sc.layout, sc.radio
    out = set()
    if L.kind != "highway":
        out.update(_HIGHWAY_KEYS)
    if L.kind in ("highway", "indoor", "ntn") or (L.kind == "open_area" and L.area_m is not None):
        out.update(_GRID_GEOMETRY)
    if L.kind not in ("street_grid", "highway") or L.highway_sites == "hex19":
        out.add("layout.site_offset_m")
    if L.kind not in ("open_area", "indoor"):
        out.add("layout.min_site_distance_m")
    if L.kind not in ("street_grid",):
        out.add("radio.clutter_los")
    if L.kind == "ntn":
        out.update(("layout.site_spacing_m", "layout.sites", "layout.sites_file"))
        out.update(_NTN_UNUSED_RADIO)
        return out
    if R.los_model == "los" and L.kind != "street_grid":
        out.update(("radio.shadow_nlos_db", "radio.los_corr_m", "radio.soft_los", "radio.soft_los_d_m"))
    if R.beams is not None:                         # the beams replace the antenna abstraction of the first layer
        out.update(("radio.bs_gain_db", "radio.isolation"))
    if R.place_share <= 0.0:
        out.add("radio.shadow_site_corr")
    return out


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
    from ..config import BEAM_LATE_KEYS
    for key in [k for k in flat if k.rsplit(".", 1)[-1] in BEAM_LATE_KEYS and ".beams." in k]:
        if flat[key] == BEAM_LATE_KEYS[key.rsplit(".", 1)[-1]]:     # beam keys of 2.3.0 and later, while default
            del flat[key]
    skipped = sorted(k for k in unused_keys(sc) if k in flat)   # keys this layout and radio model do not read
    for key in skipped:
        del flat[key]
    own = card.get("sources") or {}
    import dataclasses

    from ..config import BeamConfig
    bdef = _flat({"radio": {"beams": dataclasses.asdict(BeamConfig())}})   # defaults of the beam keys (1.10.0)
    for key, value in flat.items():
        if key == "name":
            continue
        v = _fmt(value)
        if key in bdef and key not in default:
            if _fmt(value) == _fmt(bdef[key]):
                L.append("| `%s` | %s | %s |" % (key, v, own.get(key, "default of the beam model (user guide)")))
                continue
            default[key] = bdef[key]
        if value != default.get(key):
            v = "**%s**" % v
        src, k = sources.get(key), key
        while src is None and "." in k:                 # nested keys (beams, layers): the source of the parent
            k = k.rsplit(".", 1)[0]
            src = sources.get(k)
        L.append("| `%s` | %s | %s |" % (key, v, src or ""))
    if skipped:
        L += ["", "Not read by this layout and radio model, so not listed: %s."
              % ", ".join("`%s`" % k for k in skipped)]
    L += ["", "## Known limitations", ""]
    L += ["- %s" % x.strip() for x in card.get("limitations", [])]
    L += ["", "## Reference results", ""]
    L += ["- %s" % x.strip() for x in card.get("references", [])]
    L.append("")
    return "\n".join(L)


def layout_svg(scenario: Scenario, width_px: int = 640) -> str:
    """A plain SVG drawing of the layout of ``scenario``: buildings, streets and sites."""
    from ..layout import make_layout
    shown = None
    if scenario.layout.kind == "ntn":               # the beams' ground centres at mid-run (since 2.0.0)
        import numpy as np
        from ..channel.ntn import NtnGeometry, ntn_layout
        geom = NtnGeometry(scenario)
        lay = ntn_layout(scenario, geom)
        c = lay.sites
        elev = geom.link(c[:, 0], c[:, 1], np.full(len(c), geom.t_mid))[0]
        shown = elev >= 10.0                        # minimum elevation of TR 38.821 Table 4.2-2
    else:
        lay = make_layout(scenario.layout)
    pts = lay.sites if shown is None else lay.sites[shown]
    fx0, fx1, fy0, fy1 = lay.xmin, lay.xmax, lay.ymin, lay.ymax
    if lay.images is not None or shown is not None:     # sites far from the users' area (hexagonal highway, beams)
        pad = 60.0 if shown is None else 40e3
        fx0, fx1 = min(fx0, pts[:, 0].min() - pad), max(fx1, pts[:, 0].max() + pad)
        fy0, fy1 = min(fy0, pts[:, 1].min() - pad), max(fy1, pts[:, 1].max() + pad)
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
    if lay.kind == "ntn":                           # the users' area
        out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#b9b9b0"/>'
                   % (X(lay.xmin), Y(lay.ymax), (lay.xmax - lay.xmin) * s, (lay.ymax - lay.ymin) * s))
    for x, y in pts:
        out.append('<circle cx="%.1f" cy="%.1f" r="3" fill="#c0392b"/>' % (X(x), Y(y)))
    if shown is None:
        out.append('<text x="4" y="%d" font-family="sans-serif" font-size="12" fill="#333">%s: %d sites, %.0f m x '
                   '%.0f m (grey: %s, red: sites)</text>' % (round(H) + 17, scenario.name, lay.n_sites, w, h,
                                                       "road" if lay.kind == "highway" else "buildings"))
    else:
        out.append('<text x="4" y="%d" font-family="sans-serif" font-size="12" fill="#333">%s: %d beam centres above'
                   " 10 degrees elevation, %.0f km x %.0f km (grey: users' area)</text>"
                   % (round(H) + 17, scenario.name, len(pts), w / 1e3, h / 1e3))
    out.append("</svg>")
    return "\n".join(out) + "\n"


__all__ = ["DEFAULT_SOURCES", "scenario_names", "scenario_card", "builtin_scenario", "resolve", "merge",
           "card_markdown", "layout_svg", "unused_keys"]
