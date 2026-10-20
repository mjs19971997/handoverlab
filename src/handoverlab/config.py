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

    ``wrap`` (since 1.11.0, highway only) applies the wrap-around of TR 37.885
    Table A-1: a vehicle keeps its lane and direction and re-enters the road
    at the other end, and every distance and angle between a user and a site
    is taken to the nearest image of the site along the road (period
    ``road_length_m``); the place-tied shadowing field is periodic along the
    road.  Without it (the default) a vehicle turns at the end of the road.

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
    wrap: bool = False
    highway_sites: str = "roadside"

    @property
    def size_m(self) -> Tuple[float, float]:
        """Width and height of the simulated rectangle [m]."""
        return (self.blocks[0] * self.pitch_m[0] + self.street_width_m,
                self.blocks[1] * self.pitch_m[1] + self.street_width_m)


@dataclass
class BeamConfig:
    """SSB beams, beam management and beam failure recovery of one layer (optional, since 1.10.0).

    Every site carries ``sectors`` panels (cells); boresight of sector ``s`` at
    ``sector_az0_deg + s * 360 / sectors`` degrees.  A panel is a uniform
    rectangular array of ``panel = (M, N)`` single-polarised elements at half a
    wavelength (TR 38.901 clause 7.3) with the element pattern of Table 7.3-1;
    each of the ``n_ssb`` SSB beams has DFT weights that steer it to the zenith
    angle ``tilt_deg`` (Eq. 7.3-1) and to one of ``n_ssb`` azimuths spread
    evenly over ``beam_span_deg`` (default: the sector width).  The cell
    quality follows TS 38.331 clause 5.5.3.3 (``ssb_avg`` =
    nrofSS-BlocksToAverage, ``ssb_thresh_dbm`` = absThreshSS-BlocksConsolidation;
    unset: the highest beam).

    Beam management: the gNB moves the serving beam (TCI state) to the best
    reported SSB beam when it is ``switch_db`` better than the serving beam in
    a periodic L1-RSRP report (every ``report_s``), ``tci_delay_s`` later.

    Beam failure detection and recovery (``bfd``; TS 38.213 clause 6,
    TS 38.321 clause 5.17, TS 38.133 clause 8.5): the BFD reference signal is
    the SSB of the serving beam; a beam failure instance is indicated when its
    quality, averaged over the evaluation period of TS 38.133 Table 8.5.2.2-1/-2,
    is below Qout_LR (= protocol.qout_db, 10 % BLER); ``bfi_max`` =
    beamFailureInstanceMaxCount, ``bfd_timer`` = beamFailureDetectionTimer in
    indication periods (pbfdN); then random access on the SpCell: contention-free
    on the best candidate SSB with L1-RSRP above ``rsrp_thresh_ssb_dbm``
    (rsrp-ThresholdSSB) while ``bfr_timer_s`` (beamFailureRecoveryTimer) runs,
    otherwise contention-based; one preamble attempt takes ``ra_attempt_s``
    (two for contention-based access) and succeeds if the chosen beam's SINR is
    at least Qout; after ``preamble_max`` (preambleTransMax) failed attempts a
    random-access problem is a radio-link failure (TS 38.331 clause 5.3.10.3).
    ``rlm_rs`` sets the RLM reference signals: ``"tci"`` the serving beam
    (TS 38.331 RadioLinkMonitoringConfig: no RS configured), ``"beams"`` the
    N_RLM best beams of the last report (TS 38.133 Table 8.1.1-2).
    ``rx_sweep_n`` is the scaling factor N of TS 38.133 (unset: 1 in FR1 and
    FR3, 8 in FR2-1, 12 in FR2-2).
    """
    sectors: int = 3
    sector_az0_deg: float = 30.0
    n_ssb: int = 8
    panel: Tuple[int, int] = (4, 8)
    tilt_deg: float = 100.0
    beam_span_deg: Optional[float] = None
    ssb_avg: Optional[int] = None
    ssb_thresh_dbm: Optional[float] = None
    report_s: float = 0.04
    switch_db: float = 2.0
    tci_delay_s: float = 0.01
    rx_sweep_n: Optional[int] = None
    bfd: bool = True
    bfi_max: int = 3
    bfd_timer: int = 4
    bfr_timer_s: Optional[float] = 0.1
    rsrp_thresh_ssb_dbm: float = -115.0
    ra_attempt_s: float = 0.01
    preamble_max: int = 10
    rlm_rs: str = "tci"


@dataclass
class LayerConfig:
    """A further carrier and its cells (optional, since 1.10.0; see ``RadioConfig.layers``).

    Unset values are taken from the scenario's ``radio`` (carrier, link budget,
    propagation) and ``layout`` (site placement).  ``cosited`` puts the layer on
    the sites of the first layer with the same LOS states, shadowing and
    blockers (TR 38.901 clause 7.6.5); otherwise the layer has its own sites
    (``sites``, ``sites_file`` or ``site_spacing_m`` / ``site_offset_m``) and
    independent random fields.
    """
    name: str = "layer2"
    carrier_ghz: Optional[float] = None
    bandwidth_mhz: Optional[float] = None
    scs_khz: Optional[float] = None
    tx_power_dbm: Optional[float] = None
    bs_gain_db: Optional[float] = None
    ue_gain_db: Optional[float] = None
    noise_figure_db: Optional[float] = None
    bs_height_m: Optional[float] = None
    pathloss: Optional[str] = None
    # shadowing and LOS-state correlation of the layer (since 1.11.0; unset: those of ``radio``), so that a
    # macro layer on UMa and a micro layer on UMi each get the values of TR 38.901 Tables 7.4.1-1, 7.5-6, 7.6.3.1-2
    shadow_los_db: Optional[float] = None
    shadow_nlos_db: Optional[float] = None
    shadow_decorr_m: Optional[float] = None
    los_corr_m: Optional[float] = None
    cosited: bool = False
    sites: Optional[Tuple[Tuple[float, float], ...]] = None
    sites_file: Optional[str] = None
    site_spacing_m: Optional[float] = None
    site_offset_m: Optional[float] = None
    beams: Optional[BeamConfig] = None


BFI_MAX_COUNTS = (1, 2, 3, 4, 5, 6, 8, 10)          # beamFailureInstanceMaxCount n1..n10 (TS 38.331)
BFD_TIMERS = (1, 2, 3, 4, 5, 6, 8, 10)              # beamFailureDetectionTimer pbfd1..pbfd10 (TS 38.331)
BFR_TIMERS_S = (0.01, 0.02, 0.04, 0.06, 0.08, 0.1, 0.15, 0.2)   # beamFailureRecoveryTimer ms10..ms200
PREAMBLE_TRANS_MAX = (3, 4, 5, 6, 7, 8, 10, 20, 50, 100, 200)  # preambleTransMax n3..n200 (RACH-ConfigGeneric)
SCS_KHZ = (15.0, 30.0, 60.0, 120.0, 240.0, 480.0, 960.0)


@dataclass
class RadioConfig:
    """Carrier, link budget, propagation and the antenna abstraction (TR 38.901).

    ``beams`` (since 1.10.0) replaces the antenna abstraction by sectors with
    SSB beams (:class:`BeamConfig`); ``layers`` (since 1.10.0) adds carriers
    with their own cells (:class:`LayerConfig`).  With either of them the
    measurements are SS-RSRP per resource element (the power over the
    bandwidth minus 10 log10(bandwidth / ``scs_khz``)); ``scs_khz`` unset is
    30 kHz below 7.125 GHz and 120 kHz above.
    """
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
    # LOS state (since 1.11.0): "probability" draws it from the LOS probability of the path loss model
    # (TR 38.901 Table 7.4.2-1; on the street grid on top of the buildings), "los" makes every link LOS
    # (TR 37.885 Table 6.2.1-2: the base-station-to-vehicle links of the highway are LOS only)
    los_model: str = "probability"
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
    # optional SSB beams and further carriers (since 1.10.0)
    scs_khz: Optional[float] = None
    beams: Optional[BeamConfig] = None
    layers: Optional[Tuple[LayerConfig, ...]] = None

    @property
    def extended(self) -> bool:
        """True if beams or further layers are configured (the extended radio model of 1.10.0)."""
        return self.beams is not None or bool(self.layers)

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
    # measurement periods and evaluation periods of TS 38.133 (since 1.10.0; the defaults keep the model of 1.x):
    # meas_periods "ts38133": every cell's L1 result is the average over its measurement period -- intra-frequency
    # without gaps (Tables 9.2.5.2-1/-2), inter-frequency within the gaps of pattern gap_pattern (Tables 9.1.2-1,
    # 9.3.5-1/-2) -- and the L3 filter is adapted to that input rate (TS 38.331 5.5.3.2); "sample": every L1 period
    meas_periods: str = "sample"
    ssb_period_s: float = 0.02          # SSB and SMTC periodicity (T_SSB)
    gap_pattern: int = 0                # gap pattern id of TS 38.133 Table 9.1.2-1 (0: MGL 6 ms, MGRP 40 ms)
    fr2_power_class: int = 3            # FR2 UE power class (sets M_meas of TS 38.133 9.2.5.2 and 9.3.4)
    # rlm_eval "ts38133": Qout / Qin windows from TS 38.133 Tables 8.1.2.2-1/-2 instead of qout_window_s / qin_window_s
    rlm_eval: str = "fixed"


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
    """Length of a run and (since 1.11.0) the ``backend`` of the step loop.

    ``backend`` ``"numpy"`` (the default and the reference) or ``"numba"``: a compiled kernel for the
    radio-link monitoring of every step (:mod:`handoverlab.engine._kernels`; needs ``pip install
    handoverlab[fast]``).  Both give bit-identical results, so the backend is not part of the job IDs.
    """
    duration_s: float = 120.0
    warmup_s: float = 20.0              # initial part not counted in the metrics
    backend: str = "numpy"


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
            d["run"].pop("backend", None)                 # results do not depend on it (since 1.11.0)
            for ly in d["radio"].get("layers") or ():     # layer keys of 1.11.0 and later, while unset
                for k in LAYER_LATE_KEYS:
                    if ly.get(k) is None:
                        ly.pop(k, None)
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
        _check(not L.wrap or L.kind == "highway", "layout.wrap", "is only defined for the highway layout")
        _check(not L.wrap or L.sites is not None or L.highway_sites == "hex19" or abs(L.road_length_m / L.site_spacing_m
                                                         - round(L.road_length_m / L.site_spacing_m)) < 1e-9,
               "layout.wrap", "needs a road length that is a whole number of site spacings")
        _check(R.los_model in ("probability", "los"), "radio.los_model", "must be 'probability' or 'los'")
        _check(R.los_model == "probability" or L.kind != "street_grid", "radio.los_model",
               "'los' is not available on the street grid, where the buildings decide the LOS state")
        _check(not (L.wrap and R.layers), "layout.wrap", "cannot be combined with radio.layers")
        _check(L.highway_sites in ("roadside", "one_side", "hex19"), "layout.highway_sites",
               "must be 'roadside', 'one_side' or 'hex19'")
        if L.highway_sites == "hex19":
            _check(L.kind == "highway" and L.wrap and L.sites is None, "layout.highway_sites",
                   "'hex19' needs layout.kind 'highway', layout.wrap true and no layout.sites")
            _check(abs(L.road_length_m - math.sqrt(19.0) * L.site_spacing_m) < 0.5, "layout.road_length_m",
                   "must be sqrt(19) x site_spacing_m = %.2f m with 'hex19'" % (math.sqrt(19.0) * L.site_spacing_m))
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
        _check(P.meas_periods in ("sample", "ts38133"), "protocol.meas_periods", "must be 'sample' or 'ts38133'")
        _check(P.rlm_eval in ("fixed", "ts38133"), "protocol.rlm_eval", "must be 'fixed' or 'ts38133'")
        _check(P.ssb_period_s > 0, "protocol.ssb_period_s", "must be positive")
        _check(0 <= P.gap_pattern <= 25, "protocol.gap_pattern", "TS 38.133 Table 9.1.2-1 defines the ids 0-25")
        _check(1 <= P.fr2_power_class <= 5, "protocol.fr2_power_class", "must be 1-5")
        self._validate_extended()
        _check(M.users >= 1, "mobility.users", "must be >= 1")
        if M.groups is None:
            from .mobility import PROFILES
            _check(M.profile in PROFILES, "mobility.profile", "unknown profile; known: %s" % ", ".join(PROFILES))
        _check(T.duration_s > T.warmup_s >= 0, "run.duration_s", "must exceed run.warmup_s (>= 0)")
        _check(T.backend in ("numpy", "numba"), "run.backend", "must be 'numpy' or 'numba'")
        if T.backend == "numba":
            from .engine._kernels import available
            _check(available(), "run.backend", "'numba' needs Numba: pip install handoverlab[fast]")
        shares = sum(s.share for s in self.traffic.services)
        _check(len(self.traffic.services) > 0 and shares > 0, "traffic.services", "needs a positive total share")
        from .traffic import MODELS
        Tr = self.traffic
        _check(Tr.model in MODELS, "traffic.model", "unknown model; known: %s" % ", ".join(MODELS))
        _check(Tr.period_s > 0 and Tr.packet_bytes > 0, "traffic.period_s", "period and packet size must be positive")
        _check(Tr.ftp_file_bytes > 0 and Tr.ftp_rate_hz >= 0, "traffic.ftp_file_bytes",
               "file size must be positive and the arrival rate >= 0")

    def _validate_extended(self) -> None:
        """Checks of the optional beams and layers (since 1.10.0)."""
        R = self.radio
        _check(R.scs_khz is None or R.scs_khz in SCS_KHZ, "radio.scs_khz", "must be one of %s" % (SCS_KHZ,))
        if R.beams is not None:
            _check_beams(R.beams, R.carrier_ghz, "radio.beams")
        names = set()
        for i, ly in enumerate(R.layers or ()):
            key = "radio.layers[%d]" % i
            _check(ly.name not in names and ly.name != "base", key + ".name", "must be unique and not 'base'")
            names.add(ly.name)
            f = R.carrier_ghz if ly.carrier_ghz is None else ly.carrier_ghz
            _check(0.5 <= f <= 100.0, key + ".carrier_ghz", "TR 38.901 covers 0.5-100 GHz")
            pl = ly.pathloss or R.pathloss
            _check(pl in ("umi_street_canyon", "uma", "rma", "inh_office"), key + ".pathloss",
                   "must be 'umi_street_canyon', 'uma', 'rma' or 'inh_office'")
            _check(pl != "rma" or f <= 30.0, key + ".carrier_ghz", "the TR 38.901 RMa model covers 0.5-30 GHz")
            _check(ly.bandwidth_mhz is None or ly.bandwidth_mhz > 0, key + ".bandwidth_mhz", "must be positive")
            _check(ly.scs_khz is None or ly.scs_khz in SCS_KHZ, key + ".scs_khz", "must be one of %s" % (SCS_KHZ,))
            _check(not (ly.cosited and (ly.sites is not None or ly.sites_file or ly.site_spacing_m is not None
                                        or ly.site_offset_m is not None)),
                   key + ".cosited", "a co-sited layer takes the sites of the first layer; give no own sites")
            _check(ly.site_spacing_m is None or ly.site_spacing_m > 0, key + ".site_spacing_m", "must be positive")
            if ly.beams is not None:
                _check_beams(ly.beams, f, key + ".beams")
            if ly.sites_file and ly.sites is None:
                ly.sites = read_sites(ly.sites_file)


#: keys added after 1.0.0rc2, by section; see :meth:`Scenario.to_dict`
LATE_KEYS: Dict[str, Tuple[str, ...]] = {"layout": ("lanes", "lane_width_m", "road_length_m", "sites_file",
                                                    "area_m", "min_site_distance_m", "wrap", "highway_sites"),
                                         "radio": ("soft_los", "soft_los_d_m", "shadow_los_far_db", "scs_khz",
                                                   "beams", "layers", "los_model"),
                                         "protocol": ("cmd_during_t310", "t304_s", "meas_periods", "ssb_period_s",
                                                      "gap_pattern", "fr2_power_class", "rlm_eval")}
_SECTIONS = {"layout": LayoutConfig, "radio": RadioConfig, "protocol": ProtocolConfig}
#: keys of :class:`LayerConfig` added after 1.10.0, left out of :meth:`Scenario.to_dict` while unset
LAYER_LATE_KEYS: Tuple[str, ...] = ("shadow_los_db", "shadow_nlos_db", "shadow_decorr_m", "los_corr_m")


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


def _check_beams(b: "BeamConfig", carrier_ghz: float, key: str) -> None:
    """Range checks of a :class:`BeamConfig` on a carrier of ``carrier_ghz``."""
    from .requirements import ssb_max
    _check(1 <= b.sectors <= 12, key + ".sectors", "must be 1-12")
    lmax = ssb_max(carrier_ghz)
    _check(1 <= b.n_ssb <= lmax, key + ".n_ssb",
           "must be 1-%d on %.3g GHz (L_max of TS 38.133 Table 8.1.1-2)" % (lmax, carrier_ghz))
    _check(b.panel[0] >= 1 and b.panel[1] >= 1, key + ".panel", "needs at least 1 x 1 elements")
    _check(0.0 < b.tilt_deg < 180.0, key + ".tilt_deg", "must be between 0 and 180 degrees")
    _check(b.beam_span_deg is None or 0.0 < b.beam_span_deg <= 360.0, key + ".beam_span_deg", "must be in (0, 360]")
    _check(b.ssb_avg is None or 2 <= b.ssb_avg <= b.n_ssb, key + ".ssb_avg", "nrofSS-BlocksToAverage must be 2-n_ssb")
    _check(b.report_s > 0 and b.tci_delay_s >= 0 and b.switch_db >= 0, key + ".report_s",
           "report_s must be positive, tci_delay_s and switch_db >= 0")
    _check(b.rx_sweep_n is None or b.rx_sweep_n >= 1, key + ".rx_sweep_n", "must be >= 1")
    _check(b.bfi_max in BFI_MAX_COUNTS, key + ".bfi_max", "beamFailureInstanceMaxCount: one of %s" % (BFI_MAX_COUNTS,))
    _check(b.bfd_timer in BFD_TIMERS, key + ".bfd_timer", "beamFailureDetectionTimer: one of %s" % (BFD_TIMERS,))
    _check(b.bfr_timer_s is None or any(abs(b.bfr_timer_s - v) < 1e-9 for v in BFR_TIMERS_S), key + ".bfr_timer_s",
           "beamFailureRecoveryTimer: null or one of %s s" % (BFR_TIMERS_S,))
    _check(b.preamble_max in PREAMBLE_TRANS_MAX, key + ".preamble_max",
           "preambleTransMax: one of %s" % (PREAMBLE_TRANS_MAX,))
    _check(b.ra_attempt_s > 0, key + ".ra_attempt_s", "must be positive")
    _check(b.rlm_rs in ("tci", "beams"), key + ".rlm_rs", "must be 'tci' or 'beams'")


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
