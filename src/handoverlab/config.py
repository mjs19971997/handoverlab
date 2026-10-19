# SPDX-License-Identifier: MIT
"""Scenario and experiment configuration.

A scenario (the simulated world and the protocol constants) is a tree of
dataclasses.  It can be built in Python, or read from a YAML, TOML or JSON
file, or from a plain dictionary.  Every key is checked: an unknown key or a
value of the wrong type raises :class:`ConfigError` with the full key name.

An *experiment* adds the seeds, the handover rules to compare and the output
file to a scenario; it is what the command line runs::

    schema: 1                  # file format version (optional; see docs/stability.md)
    scenario:
      layout: {kind: street_grid, blocks: [3, 3], site_spacing_m: 100}
      mobility: {users: 40, profile: veh16}
      run: {duration_s: 120, warmup_s: 20}
    seeds: [1, 2]
    rules:
      - {rule: a3, off_db: 3.0, ttt_s: 0.16}
      - {rule: cho, o_prep_db: -2.0, o_exec_db: 3.0}
    output: results/metrics.csv
"""
from __future__ import annotations

import dataclasses
import json
import math
import os
import sys
import typing
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple, Union


class ConfigError(ValueError):
    """Invalid configuration; the message names the offending key."""


# ---------------------------------------------------------------------------
# sections of a scenario
# ---------------------------------------------------------------------------
@dataclass
class LayoutConfig:
    """Deployment geometry.

    ``street_grid`` is the urban grid of 3GPP TR 37.885 Annex A: blocks of
    ``pitch_m`` (433 m x 250 m between street centre lines), streets
    ``street_width_m`` wide.  The default of 3 x 3 blocks is the minimum area
    of TR 37.885 Table A-1.  Sites stand on the pavement every
    ``site_spacing_m`` metres, ``site_offset_m`` from the street centre line.

    ``open_area`` is the same rectangle without buildings, with sites on a
    hexagonal grid of spacing ``site_spacing_m``.

    ``highway`` (since 1.0.0rc3) is the straight multi-lane road of the
    TR 37.885 highway case: ``lanes`` lanes of ``lane_width_m`` per direction
    over ``road_length_m``, without buildings; roadside sites every
    ``site_spacing_m`` metres, ``site_offset_m`` beyond the road edge,
    alternately on the two sides.

    ``indoor`` (since 1.7.0) is the indoor office of TR 38.901 Table 7.2-2:
    a hall of 120 m x 50 m without walls and ceiling sites on a rectangular
    grid of spacing ``site_spacing_m`` (20 m in the standard).

    ``area_m`` (since 1.7.0) sets the width and height of the rectangle of
    ``open_area`` and ``indoor`` [m]; unset, ``open_area`` takes the size of
    the street grid and ``indoor`` 120 m x 50 m.  ``min_site_distance_m``
    (since 1.7.0) is the minimum 2D distance of a user's start and waypoints
    from every site in ``open_area`` and ``indoor`` (TR 38.901 Table 7.2-3,
    RMa: 35 m); the straight legs between them may pass closer.

    ``sites_file`` (since 1.0.0rc3) names a CSV file with the columns ``x`` and
    ``y`` [m]; it is read when the scenario is loaded and fills ``sites``.
    """
    kind: str = "street_grid"
    blocks: Tuple[int, int] = (3, 3)
    pitch_m: Tuple[float, float] = (433.0, 250.0)
    street_width_m: float = 20.0
    site_spacing_m: float = 100.0
    site_offset_m: float = 9.0
    sites: Optional[Tuple[Tuple[float, float], ...]] = None
    lanes: int = 3
    lane_width_m: float = 4.0
    road_length_m: float = 2000.0
    sites_file: Optional[str] = None
    area_m: Optional[Tuple[float, float]] = None
    min_site_distance_m: float = 0.0

    @property
    def size_m(self) -> Tuple[float, float]:
        """Width and height of the simulated rectangle [m]."""
        return (self.blocks[0] * self.pitch_m[0] + self.street_width_m,
                self.blocks[1] * self.pitch_m[1] + self.street_width_m)


@dataclass
class RadioConfig:
    """Carrier, link budget, propagation and the antenna abstraction (TR 38.901)."""
    carrier_ghz: float = 10.0
    bandwidth_mhz: float = 200.0
    tx_power_dbm: float = 35.0          # per site
    bs_gain_db: float = 20.0            # beam gain towards a served or measuring user
    ue_gain_db: float = 0.0
    noise_figure_db: float = 7.0
    isolation: float = 0.30             # mean-to-peak gain of an interfering data beam
    bs_height_m: float = 10.0
    ue_height_m: float = 1.5
    pathloss: str = "umi_street_canyon"  # or "uma", "rma" (since 1.7.0), "inh_office" (since 1.7.0)
    shadow_los_db: float = 4.0
    shadow_nlos_db: float = 7.82
    shadow_los_far_db: Optional[float] = None  # LOS beyond the breakpoint (since 1.7.0; RMa: 6 dB); None: shadow_los_db
    shadow_decorr_m: float = 10.0
    shadow_site_corr: float = 0.5       # correlation of the shadowing between sites
    place_share: float = 1.0            # share of shadowing variance tied to place (1 = fully place-tied)
    clutter_los: bool = True            # spatially consistent LOS state on top of the buildings
    los_corr_m: float = 50.0
    # optional soft LOS state (since 1.7.0; TR 38.901 clause 7.6.3.3, Eq. 7.6-18 and 7.6-19): the received
    # power mixes the LOS and NLOS powers with the weights LOS_soft^2 and 1 - LOS_soft^2, where
    # LOS_soft = 1/2 + arctan(sqrt(soft_los_d_m / lambda) (G + F(d))) / pi, instead of a hard switch
    soft_los: bool = False
    soft_los_d_m: float = 20.0
    time_var_db: float = 1.5            # time-varying component (moving blockers)
    time_var_tau_s: float = 1.0
    l1_error_db: float = 1.0            # error of one L1 RSRP sample
    # optional per-user penetration loss on all links, drawn once per user (since 1.2.0; TR 38.901
    # clause 7.4.3.2: a user in a standard car has 9 dB mean and 5 dB standard deviation)
    penetration_db: float = 0.0
    penetration_sd_db: float = 0.0
    # site power for the energy metrics (since 1.5.0): EARTH model of a micro base station
    # (Auer et al., IEEE Wireless Communications 2011): P_in = energy_p0_w + energy_slope x P_tx x load
    energy_p0_w: float = 56.0
    energy_slope: float = 2.6
    map_res_m: float = 1.0

    @property
    def noise_dbm(self) -> float:
        """Thermal noise over the carrier plus the noise figure [dBm]."""
        return -174.0 + 10.0 * math.log10(self.bandwidth_mhz * 1e6) + self.noise_figure_db


@dataclass
class ProtocolConfig:
    """Measurement chain, handover timing and the failure model.

    Defaults follow 3GPP TR 36.839 / TR 36.842 (Qout -8 dB, Qin -6 dB,
    T310 1 s, N310 = N311 = 1, preparation 50 ms, execution 40 ms) and the L3
    filter of TS 38.331 clause 5.5.3.2.
    """
    step_s: float = 0.01
    l1_period_s: float = 0.04
    l3_k: int = 4
    label_period_s: float = 0.2
    report_interval_s: float = 0.12
    qout_db: float = -8.0
    qin_db: float = -6.0
    qout_window_s: float = 0.2
    qin_window_s: float = 0.1
    n310: int = 1
    n311: int = 1
    t310_s: float = 1.0
    prep_s: float = 0.05
    exec_s: float = 0.04
    reest_s: float = 1.0
    cho_recovery_s: float = 0.4
    pingpong_s: float = 1.0
    cfg_loss_as_failure: bool = False   # check mode: a lost conditional configuration fails like a lost command
    # optional link-monitoring model (since 1.1.0; the defaults keep the model of 1.0):
    lm_load: Optional[float] = None     # interferer load at link monitoring; None: the load of the data channel
    lm_load_per_ue: float = 0.0         # added to lm_load per user served by the interfering cell
    exec_can_fail: bool = True          # False: the execution always joins the target (ideal random access)
    rlm_holdoff_s: float = 0.0          # no out-of-sync on a newly joined cell for this time (TS 38.133: 0.2 s)
    # handover command and execution as TS 38.331 specifies them (since 1.9.0; the defaults keep the model of 1.x):
    # "receive": a command that reaches a UE while T310 runs is received at the first step with link-monitoring
    # SINR >= Qout and stops T310 (TS 38.331 5.3.5.5.2); "lost": it is lost at once
    cmd_during_t310: str = "lost"
    t304_s: Optional[float] = None      # T304: the execution fails only when T304 expires (TS 38.331 5.3.5.8.3)


@dataclass
class Service:
    """A service class (5QI of TS 23.501 Table 5.7.4-1) and its label thresholds."""
    key: str
    fiveqi: int
    gbr: bool
    t_min_s: float       # minimum useful time of stay in the target
    theta_q_db: float    # minimum mean SINR gain
    share: float         # share of users
    rate_mbps: float     # demanded rate


DEFAULT_SERVICES = (
    Service("voice", 1, True, 4.0, 0.7, 0.20, 0.1),
    Service("video_call", 2, True, 6.0, 1.0, 0.20, 4.0),
    Service("gaming", 3, True, 7.0, 1.2, 0.15, 30.0),
    Service("streaming", 6, False, 3.0, 1.5, 0.30, 25.0),
    Service("web", 9, False, 2.0, 0.4, 0.15, 10.0),
)


@dataclass
class TrafficConfig:
    """Services, background load and the scheduler abstraction."""
    services: Tuple[Service, ...] = DEFAULT_SERVICES
    se_max: float = 7.4                 # spectral-efficiency cap [bit/s/Hz]
    hotspot_share: float = 0.25
    hotspot_load: Tuple[float, float] = (0.55, 0.85)
    normal_load: Tuple[float, float] = (0.05, 0.25)
    load_tau_s: float = 0.2
    rate_scale: float = 1.0
    label_load: float = 1.0             # load assumed for the SINR of the outcome label
    # traffic model of the users (since 1.4.0): "fixed" keeps the constant service rates of 1.0;
    # "full_buffer" (always as much as the link carries), "periodic" (a packet every period_s, as
    # VoIP) and "ftp3" (files of ftp_file_bytes with Poisson arrivals, TR 36.814 FTP model 3) give
    # each user a buffer that the scheduler empties
    model: str = "fixed"
    period_s: float = 0.02
    packet_bytes: int = 100
    ftp_file_bytes: int = 500000
    ftp_rate_hz: float = 0.1


@dataclass
class SpeedGroup:
    """A share of users with a uniform speed range and lateral displacement range."""
    share: float
    v_min: float
    v_max: float
    lateral_m: Tuple[float, float] = (0.0, 3.0)


@dataclass
class MobilityConfig:
    """Number of users and their speeds; ``groups`` overrides the named ``profile``."""
    users: int = 40
    profile: str = "veh16"
    groups: Optional[Tuple[SpeedGroup, ...]] = None


@dataclass
class RunConfig:
    duration_s: float = 120.0
    warmup_s: float = 20.0              # initial part not counted in the metrics


@dataclass
class Scenario:
    """One simulated condition.  Together with a seed it fixes a *world*."""
    name: str = "street-grid"
    layout: LayoutConfig = field(default_factory=LayoutConfig)
    radio: RadioConfig = field(default_factory=RadioConfig)
    protocol: ProtocolConfig = field(default_factory=ProtocolConfig)
    traffic: TrafficConfig = field(default_factory=TrafficConfig)
    mobility: MobilityConfig = field(default_factory=MobilityConfig)
    run: RunConfig = field(default_factory=RunConfig)

    def to_dict(self, full: bool = False) -> Dict[str, Any]:
        """The scenario as a plain dictionary.

        Keys added after 1.0.0rc2 (:data:`LATE_KEYS`) are left out while they
        have their default value, so that the job IDs and study locks of
        scenarios that do not use them stay as they were; ``full=True`` keeps
        every key.
        """
        d = _plain(dataclasses.asdict(self))
        if not full:
            for section, keys in LATE_KEYS.items():
                default = _plain(dataclasses.asdict(_SECTIONS[section]()))
                for k in keys:
                    if d[section].get(k) == default[k]:
                        del d[section][k]
        return d

    @classmethod
    def from_dict(cls, data: Union[Dict[str, Any], str]) -> "Scenario":
        """Scenario from a dictionary.

        ``data`` may also be the name of a built-in scenario, or contain the key
        ``base`` with such a name; the other values then change the built-in
        scenario (see :mod:`handoverlab.scenarios`).
        """
        if isinstance(data, str) or (isinstance(data, dict) and "base" in data):
            from .scenarios import resolve
            data = resolve(data)
        sc = _build(cls, data or {}, "scenario.")
        if sc.layout.sites_file and sc.layout.sites is None:
            sc.layout.sites = read_sites(sc.layout.sites_file)
        sc.validate()
        return sc

    def with_overrides(self, overrides: Dict[str, Any]) -> "Scenario":
        """Copy with changed values; keys are dotted paths such as ``"layout.site_spacing_m"``."""
        d = self.to_dict(full=True)
        for key, value in overrides.items():
            node = d
            parts = key.split(".")
            for p in parts[:-1]:
                if not isinstance(node.get(p), dict):
                    raise ConfigError("unknown key 'scenario.%s'" % key)
                node = node[p]
            if parts[-1] not in node:
                raise ConfigError("unknown key 'scenario.%s'" % key)
            node[parts[-1]] = value
        return Scenario.from_dict(d)

    def validate(self) -> None:
        """Range checks that name the offending key."""
        L, R, P, M, T = self.layout, self.radio, self.protocol, self.mobility, self.run
        _check(L.kind in ("street_grid", "open_area", "highway", "indoor"), "layout.kind",
               "must be 'street_grid', 'open_area', 'highway' or 'indoor'")
        _check(L.min_site_distance_m >= 0, "layout.min_site_distance_m", "must be >= 0")
        _check(L.area_m is None or (L.area_m[0] > 0 and L.area_m[1] > 0), "layout.area_m",
               "width and height must be positive")
        _check(L.lanes >= 1, "layout.lanes", "must be >= 1")
        _check(L.lane_width_m > 0, "layout.lane_width_m", "must be positive")
        _check(L.road_length_m > 0, "layout.road_length_m", "must be positive")
        _check(L.sites is None or len(L.sites) >= 1, "layout.sites", "needs at least one site")
        _check(L.blocks[0] >= 1 and L.blocks[1] >= 1, "layout.blocks", "needs at least 1 x 1 blocks")
        _check(L.site_spacing_m > 0, "layout.site_spacing_m", "must be positive")
        _check(L.street_width_m > 0, "layout.street_width_m", "must be positive")
        _check(R.pathloss in ("umi_street_canyon", "uma", "rma", "inh_office"), "radio.pathloss",
               "must be 'umi_street_canyon', 'uma', 'rma' or 'inh_office'")
        _check(0.5 <= R.carrier_ghz <= 100.0, "radio.carrier_ghz", "TR 38.901 covers 0.5-100 GHz")
        _check(R.pathloss != "rma" or R.carrier_ghz <= 30.0, "radio.carrier_ghz",
               "the TR 38.901 RMa model covers 0.5-30 GHz")
        _check(0.0 <= R.place_share <= 1.0, "radio.place_share", "must be in [0, 1]")
        _check(0.0 <= R.shadow_site_corr <= 1.0, "radio.shadow_site_corr", "must be in [0, 1]")
        _check(R.map_res_m > 0, "radio.map_res_m", "must be positive")
        _check(R.soft_los_d_m > 0, "radio.soft_los_d_m", "must be positive")
        _check(R.shadow_los_far_db is None or R.shadow_los_far_db >= 0, "radio.shadow_los_far_db", "must be >= 0")
        _check(R.penetration_sd_db >= 0, "radio.penetration_sd_db", "must be >= 0")
        _check(R.energy_p0_w >= 0 and R.energy_slope >= 0, "radio.energy_p0_w", "energy parameters must be >= 0")
        _check(P.step_s > 0, "protocol.step_s", "must be positive")
        mp = P.l1_period_s / P.step_s
        _check(abs(mp - round(mp)) < 1e-9 and mp >= 1, "protocol.l1_period_s",
               "must be a whole multiple of protocol.step_s")
        _check(P.l3_k >= 0, "protocol.l3_k", "must be >= 0")
        _check(P.n310 >= 1 and P.n311 >= 1, "protocol.n310", "N310 and N311 must be >= 1")
        _check(P.lm_load is None or P.lm_load >= 0, "protocol.lm_load", "must be >= 0 or null")
        _check(P.lm_load_per_ue >= 0, "protocol.lm_load_per_ue", "must be >= 0")
        _check(P.rlm_holdoff_s >= 0, "protocol.rlm_holdoff_s", "must be >= 0")
        _check(P.cmd_during_t310 in ("lost", "receive"), "protocol.cmd_during_t310", "must be 'lost' or 'receive'")
        _check(P.t304_s is None or P.t304_s > 0, "protocol.t304_s", "must be positive or null")
        _check(M.users >= 1, "mobility.users", "must be >= 1")
        if M.groups is None:
            from .mobility import PROFILES
            _check(M.profile in PROFILES, "mobility.profile", "unknown profile; known: %s" % ", ".join(PROFILES))
        _check(T.duration_s > T.warmup_s >= 0, "run.duration_s", "must exceed run.warmup_s (>= 0)")
        shares = sum(s.share for s in self.traffic.services)
        _check(len(self.traffic.services) > 0 and shares > 0, "traffic.services", "needs a positive total share")
        from .traffic import MODELS
        Tr = self.traffic
        _check(Tr.model in MODELS, "traffic.model", "unknown model; known: %s" % ", ".join(MODELS))
        _check(Tr.period_s > 0 and Tr.packet_bytes > 0, "traffic.period_s", "period and packet size must be positive")
        _check(Tr.ftp_file_bytes > 0 and Tr.ftp_rate_hz >= 0, "traffic.ftp_file_bytes",
               "file size must be positive and the arrival rate >= 0")


#: keys added after 1.0.0rc2, by section; see :meth:`Scenario.to_dict`
LATE_KEYS: Dict[str, Tuple[str, ...]] = {"layout": ("lanes", "lane_width_m", "road_length_m", "sites_file",
                                                    "area_m", "min_site_distance_m"),
                                         "radio": ("soft_los", "soft_los_d_m", "shadow_los_far_db"),
                                         "protocol": ("cmd_during_t310", "t304_s")}
_SECTIONS = {"layout": LayoutConfig, "radio": RadioConfig, "protocol": ProtocolConfig}


def read_sites(path: Union[str, os.PathLike]) -> Tuple[Tuple[float, float], ...]:
    """Site positions from a CSV file with a header row and the columns ``x`` and ``y`` [m].

    Other columns are ignored.  A relative path is taken from the current directory.
    """
    import csv
    try:
        with open(os.fspath(path), "r", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
    except OSError as e:
        raise ConfigError("scenario.layout.sites_file: cannot read %r (%s)" % (os.fspath(path), e.strerror))
    try:
        sites = tuple((float(r["x"]), float(r["y"])) for r in rows)
    except (KeyError, TypeError, ValueError):
        raise ConfigError("scenario.layout.sites_file: %r needs the columns x and y with numbers"
                          % os.fspath(path))
    if not sites:
        raise ConfigError("scenario.layout.sites_file: %r holds no sites" % os.fspath(path))
    return sites


def _check(ok: bool, key: str, msg: str) -> None:
    if not ok:
        raise ConfigError("scenario.%s: %s" % (key, msg))


# ---------------------------------------------------------------------------
# experiment = scenario + seeds + rules + output
# ---------------------------------------------------------------------------
@dataclass
class Experiment:
    scenario: Scenario = field(default_factory=Scenario)
    seeds: Tuple[int, ...] = (1,)
    rules: Tuple[Dict[str, Any], ...] = ({"rule": "a3"},)
    output: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Experiment":
        from .stability import check_schema
        data = dict(data or {})
        unknown = set(data) - {"schema", "scenario", "seeds", "rules", "output"}
        if unknown:
            raise ConfigError("unknown key '%s'; allowed: schema, scenario, seeds, rules, output"
                              % sorted(unknown)[0])
        check_schema(data.get("schema"), "experiment")
        sc = Scenario.from_dict(data.get("scenario") or {})
        seeds = data.get("seeds", [1])
        if isinstance(seeds, int):
            seeds = [seeds]
        if isinstance(seeds, dict):                    # {first: 1, last: 10}
            seeds = list(range(int(seeds["first"]), int(seeds["last"]) + 1))
        if not seeds or not all(isinstance(s, int) and not isinstance(s, bool) and s >= 0 for s in seeds):
            raise ConfigError("seeds: expected a list of non-negative integers")
        rules = data.get("rules") or [{"rule": "a3"}]
        for i, r in enumerate(rules):
            if not isinstance(r, dict) or "rule" not in r:
                raise ConfigError("rules[%d]: expected a mapping with a 'rule' key" % i)
        return cls(sc, tuple(seeds), tuple(dict(r) for r in rules), data.get("output"))


def read_file(path: Union[str, os.PathLike]) -> Dict[str, Any]:
    """Read a YAML (.yaml/.yml), TOML (.toml) or JSON (.json) file into a dictionary."""
    path = os.fspath(path)
    ext = os.path.splitext(path)[1].lower()
    if ext in (".yaml", ".yml"):
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    if ext == ".toml":
        if sys.version_info >= (3, 11):
            import tomllib
        else:                                          # pragma: no cover
            import tomli as tomllib
        with open(path, "rb") as f:
            return tomllib.load(f)
    if ext == ".json":
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    raise ConfigError("%s: unknown file type (use .yaml, .yml, .toml or .json)" % path)


def load_config(source: Union[str, os.PathLike, Dict[str, Any]]) -> Experiment:
    """Experiment from a file path or a dictionary."""
    data = source if isinstance(source, dict) else read_file(source)
    return Experiment.from_dict(data)


# ---------------------------------------------------------------------------
# dictionary -> dataclass with type checks
# ---------------------------------------------------------------------------
def _build(cls, data, where):
    if dataclasses.is_dataclass(data) and isinstance(data, cls):
        return data
    if not isinstance(data, dict):
        raise ConfigError("%s: expected a mapping, got %r" % (where.rstrip("."), data))
    hints = typing.get_type_hints(cls)
    names = [f.name for f in dataclasses.fields(cls)]
    kw = {}
    for key, value in data.items():
        if key not in names:
            raise ConfigError("unknown key '%s%s'; allowed: %s" % (where, key, ", ".join(names)))
        kw[key] = _coerce(value, hints[key], where + key)
    try:
        return cls(**kw)
    except TypeError as e:
        raise ConfigError("%s: %s" % (where.rstrip("."), e))


def _coerce(v, tp, key):
    origin = typing.get_origin(tp)
    args = typing.get_args(tp)
    if origin is Union:                                 # Optional[X]
        if v is None and type(None) in args:
            return None
        inner = [a for a in args if a is not type(None)]
        return _coerce(v, inner[0], key)
    if dataclasses.is_dataclass(tp):
        return _build(tp, v, key + ".")
    if origin in (tuple, Tuple):
        if not isinstance(v, (list, tuple)):
            raise ConfigError("%s: expected a list, got %r" % (key, v))
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(_coerce(x, args[0], "%s[%d]" % (key, i)) for i, x in enumerate(v))
        if len(v) != len(args):
            raise ConfigError("%s: expected %d values, got %d" % (key, len(args), len(v)))
        return tuple(_coerce(x, a, "%s[%d]" % (key, i)) for i, (x, a) in enumerate(zip(v, args)))
    if tp is float:
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ConfigError("%s: expected a number, got %r" % (key, v))
        return float(v)
    if tp is int:
        if isinstance(v, bool) or not isinstance(v, (int, float)) or float(v) != int(v):
            raise ConfigError("%s: expected an integer, got %r" % (key, v))
        return int(v)
    if tp is bool:
        if not isinstance(v, bool):
            raise ConfigError("%s: expected true or false, got %r" % (key, v))
        return v
    if tp is str:
        if not isinstance(v, str):
            raise ConfigError("%s: expected a string, got %r" % (key, v))
        return v
    return v


def _plain(x):
    """Tuples -> lists, recursively (for JSON/YAML output)."""
    if isinstance(x, dict):
        return {k: _plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_plain(v) for v in x]
    return x
