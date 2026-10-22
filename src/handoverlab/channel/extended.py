# SPDX-License-Identifier: MIT
"""Extended radio model of 1.10.0: SSB beams per sector and several carriers (layers).

Used only when the scenario sets ``radio.beams`` or ``radio.layers``; without
them the model of 1.x (:mod:`handoverlab.channel.source`) runs unchanged.

Cells
    Layer 0 is the scenario's own carrier and sites; every entry of
    ``radio.layers`` adds a carrier with its own sites (or, ``cosited``, the
    sites of layer 0 with the same LOS states, shadowing and blockers, as
    TR 38.901 clause 7.6.5 asks for multi-frequency simulations).  A layer
    without beams has one cell per site with the antenna abstraction of 1.x
    (gain ``bs_gain_db`` towards the user, interfering with ``isolation``
    times its peak power, scaled by the load).  A layer with beams
    (:class:`~handoverlab.config.BeamConfig`) has ``sectors`` cells per site,
    each with ``n_ssb`` SSB beams (:mod:`handoverlab.channel.antenna`); such a
    cell interferes with the mean gain of its beams in the user's direction,
    scaled by the load (a cell that serves its users on all of its beams).

Received power of user u from beam b of cell c (site s, layer l)
    P = tx_power_l + ue_gain_l + G_c,b(theta, phi) + g_s(u)
    where g_s(u) is the site gain of :meth:`RadioSource.raw_chunks` (path
    loss, LOS state, shadowing, time variation, penetration loss) of layer l.

Measurements (SS-RSRP per resource element, TS 38.215 clause 5.1.1)
    The power over the bandwidth minus 10 log10(12 N_RB) (power per
    subcarrier of a flat spectrum over the transmission bandwidth configuration
    N_RB of TS 38.101-1 / TS 38.101-2 Table 5.3.2-1; since 2.1.0 with
    ``radio.channel_detail: 3gpp``, otherwise and for bandwidths without a table
    entry 10 log10(B / SCS)).  Every beam gets its own L1 error
    (``radio.l1_error_db``, stream ``beams``); the cell quality of a cell with
    beams follows TS 38.331 clause 5.5.3.3 (the highest beam, or the linear
    average of up to nrofSS-BlocksToAverage beams above
    absThreshSS-BlocksConsolidation).

Interference
    Only cells on the same carrier interfere; the noise is that of the
    carrier's bandwidth and the layer's noise figure.
"""
from __future__ import annotations

import copy
import dataclasses
import math
from typing import Iterator, List, Optional

import numpy as np

from ..config import BeamConfig, LayoutConfig, RadioConfig, Scenario
from ..layout import make_layout
from ..seeds import streams
from .antenna import beam_azimuths_deg, beam_gain_db, wrap_deg
from .radiomap import RadioMap

LN10_10 = np.log(10.0) / 10.0
NO_BEAM_DB = -400.0               # L1 value of a beam index that a cell does not have


def default_scs_khz(carrier_ghz: float) -> float:
    """Subcarrier spacing assumed when ``scs_khz`` is unset: 30 kHz up to 7.125 GHz, 120 kHz above."""
    return 30.0 if carrier_ghz <= 7.125 else 120.0


#: maximum transmission bandwidth configuration N_RB, (SCS kHz, bandwidth MHz) -> N_RB: FR1 from TS 38.101-1
#: V19.7.0 Table 5.3.2-1, FR2 from TS 38.101-2 V19.5.0 Table 5.3.2-1 (N/A entries left out)
N_RB_FR1 = {(15, 3): 15, (15, 5): 25, (15, 7): 35, (15, 10): 52, (15, 15): 79, (15, 20): 106, (15, 25): 133,
            (15, 30): 160, (15, 35): 188, (15, 40): 216, (15, 45): 242, (15, 50): 270,
            (30, 5): 11, (30, 10): 24, (30, 15): 38, (30, 20): 51, (30, 25): 65, (30, 30): 78, (30, 35): 92,
            (30, 40): 106, (30, 45): 119, (30, 50): 133, (30, 60): 162, (30, 70): 189, (30, 80): 217,
            (30, 90): 245, (30, 100): 273,
            (60, 10): 11, (60, 15): 18, (60, 20): 24, (60, 25): 31, (60, 30): 38, (60, 35): 44, (60, 40): 51,
            (60, 45): 58, (60, 50): 65, (60, 60): 79, (60, 70): 93, (60, 80): 107, (60, 90): 121, (60, 100): 135}
N_RB_FR2 = {(60, 50): 66, (60, 100): 132, (60, 200): 264, (120, 50): 32, (120, 100): 66, (120, 200): 132,
            (120, 400): 264, (480, 400): 66, (480, 800): 124, (480, 1600): 248, (960, 400): 33, (960, 800): 62,
            (960, 1600): 124, (960, 2000): 148}


def n_rb(bandwidth_mhz: float, scs_khz: float, carrier_ghz: float) -> Optional[int]:
    """N_RB of TS 38.101-1 / -2 Table 5.3.2-1 for the frequency range of the carrier, or None (no entry)."""
    from ..requirements import freq_range
    fr = freq_range(carrier_ghz)
    table = N_RB_FR1 if fr == "FR1" else N_RB_FR2 if fr.startswith("FR2") else {}
    key = (int(round(scs_khz)), int(round(bandwidth_mhz)))
    if abs(key[0] - scs_khz) > 1e-9 or abs(key[1] - bandwidth_mhz) > 1e-9:
        return None
    return table.get(key)


def re_offset_db(bandwidth_mhz: float, scs_khz: float, carrier_ghz: Optional[float] = None,
                 detail: str = "simple") -> float:
    """Total power over the bandwidth minus power per subcarrier [dB]: 10 log10(12 N_RB) with ``detail`` "3gpp"
    and a table entry for the carrier (TS 38.101-1 / -2 Table 5.3.2-1), else 10 log10(B / SCS) (2.0.0)."""
    if detail == "3gpp" and carrier_ghz is not None:
        n = n_rb(bandwidth_mhz, scs_khz, carrier_ghz)
        if n is not None:
            return 10.0 * math.log10(12.0 * n)
    return 10.0 * math.log10(bandwidth_mhz * 1e3 / scs_khz)


class Layer:
    """One carrier with its sites, radio map and cells."""

    def __init__(self, index: int, name: str, radio: RadioConfig, layout, rmap: RadioMap, sub: int,
                 beams: Optional[BeamConfig], scs_khz: float):
        self.index, self.name, self.radio, self.layout, self.rmap, self.sub = index, name, radio, layout, rmap, sub
        self.beams, self.scs_khz = beams, scs_khz
        self.n_sites = layout.n_sites
        self.sectors = beams.sectors if beams else 1
        self.n_beams = beams.n_ssb if beams else 1
        self.n_cells = self.n_sites * self.sectors
        if beams:
            span = beams.beam_span_deg if beams.beam_span_deg is not None else 360.0 / beams.sectors
            self.beam_az = beam_azimuths_deg(beams.n_ssb, span)
            self.boresight = (beams.sector_az0_deg + np.arange(beams.sectors) * 360.0 / beams.sectors) % 360.0
        else:
            self.beam_az = np.zeros(1)
            self.boresight = np.zeros(1)
        self.re_off = re_offset_db(radio.bandwidth_mhz, scs_khz, radio.carrier_ghz, radio.channel_detail)
        self.p0 = radio.tx_power_dbm + radio.ue_gain_db          # + antenna gain of the beam or the abstraction


def _layer_radio(base: RadioConfig, ly) -> RadioConfig:
    over = {k: getattr(ly, k) for k in ("carrier_ghz", "bandwidth_mhz", "tx_power_dbm", "bs_gain_db", "ue_gain_db",
                                        "noise_figure_db", "bs_height_m", "pathloss", "shadow_los_db", "shadow_nlos_db",
                                        "shadow_decorr_m", "los_corr_m") if getattr(ly, k, None) is not None}
    return dataclasses.replace(base, beams=ly.beams, layers=None, scs_khz=ly.scs_khz, **over)


def _layer_layout(base: LayoutConfig, ly) -> LayoutConfig:
    over = {}
    if ly.sites is not None:
        over["sites"] = tuple(tuple(map(float, s)) for s in ly.sites)
    else:
        over["sites"] = None
        over["sites_file"] = None
        if ly.site_spacing_m is not None:
            over["site_spacing_m"] = ly.site_spacing_m
        if ly.site_offset_m is not None:
            over["site_offset_m"] = ly.site_offset_m
    return dataclasses.replace(base, **over)


class ExtendedRadio:
    """Layers and the cell table of one world (built once per seed)."""

    def __init__(self, scenario: Scenario, layout, rmap: RadioMap, seed: int):
        R = scenario.radio
        self.seed = seed
        self.layers: List[Layer] = []
        base_radio = dataclasses.replace(R, layers=None)
        self.layers.append(Layer(0, "base", base_radio, layout, rmap, 0, R.beams,
                                 R.scs_khz or default_scs_khz(R.carrier_ghz)))
        for i, ly in enumerate(R.layers or (), start=1):
            lr = _layer_radio(base_radio, ly)
            if ly.cosited:
                lay, sub = layout, 0
            else:
                lay, sub = make_layout(_layer_layout(scenario.layout, ly)), i
            lm = RadioMap(lay, lr, seed, sub)
            self.layers.append(Layer(i, ly.name, lr, lay, lm, sub, ly.beams,
                                     ly.scs_khz or default_scs_khz(lr.carrier_ghz)))
        # cell table: layer, global site, sector of every cell
        cl, cs, csec, gs0 = [], [], [], 0
        self.site0 = []
        for L in self.layers:
            self.site0.append(gs0)
            for s in range(L.n_sites):
                for k in range(L.sectors):
                    cl.append(L.index)
                    cs.append(gs0 + s)
                    csec.append(k)
            gs0 += L.n_sites
        self.n_sites = gs0
        self.cell_layer = np.asarray(cl, dtype=int)
        self.cell_site = np.asarray(cs, dtype=int)
        self.cell_sector = np.asarray(csec, dtype=int)
        self.n_cells = len(cl)
        self.site_pos = np.concatenate([L.layout.sites for L in self.layers])
        self.cell_pos = self.site_pos[self.cell_site]
        lay = self.layers
        self.n_beams = np.array([lay[i].n_beams for i in cl])
        self.B = int(self.n_beams.max())
        self.has_beams = np.array([lay[i].beams is not None for i in cl])
        self.cell_az = np.array([lay[i].boresight[k] for i, k in zip(cl, csec)])
        self.p0 = np.array([lay[i].p0 for i in cl])
        self.re_off = np.array([lay[i].re_off for i in cl])
        self.hb = np.array([lay[i].radio.bs_height_m for i in cl])
        self.hu = R.ue_height_m
        self.carrier_ghz = np.array([lay[i].radio.carrier_ghz for i in cl])
        # carriers: cells of one carrier frequency interfere with each other
        freqs = sorted({round(L.radio.carrier_ghz, 9) for L in lay})
        self.n_carriers = len(freqs)
        self.cell_carrier = np.array([freqs.index(round(lay[i].radio.carrier_ghz, 9)) for i in cl])
        self.noise_mw = np.array([10 ** (lay[i].radio.noise_dbm / 10.0) for i in cl])
        self.bw_hz = np.array([lay[i].radio.bandwidth_mhz * 1e6 for i in cl])
        self.chi = np.array([1.0 if lay[i].beams is not None else lay[i].radio.isolation for i in cl])
        self.carrier_mask = (self.cell_carrier[:, None] == np.arange(self.n_carriers)[None, :]).astype(float)
        # beam azimuths per cell (absolute), padded
        self.beam_az = np.full((self.n_cells, self.B), np.nan)
        for c in range(self.n_cells):
            L = lay[cl[c]]
            self.beam_az[c, :L.n_beams] = L.beam_az
        self.base_layout, self.base_rmap = layout, rmap

    # ---------------------------------------------------------------- geometry and gains
    def _angles(self, x, y, cells):
        """Zenith angle and azimuth from the boresight [deg] of points (x, y) seen from ``cells`` (same shape)."""
        sp = self.cell_pos[cells]
        dx, dy = x - sp[..., 0], y - sp[..., 1]
        if self.base_layout.period_x:                        # nearest image of the site (wrap-around, since 1.11.0)
            dx, dy = self.base_layout.nearest_image(dx, dy)
        d2 = np.maximum(np.hypot(dx, dy), 1.0)
        theta = 90.0 + np.degrees(np.arctan2(self.hb[cells] - self.hu, d2))
        phi = wrap_deg(np.degrees(np.arctan2(dy, dx)) - self.cell_az[cells])
        return theta, phi

    def gain_db(self, x, y, cells, beams) -> np.ndarray:
        """Antenna gain [dBi] of ``beams`` of ``cells`` towards points (x, y); arrays of one shape.

        Cells without beams give ``bs_gain_db`` of their layer.
        """
        x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
        cells = np.asarray(cells, dtype=int)
        beams = np.asarray(beams, dtype=int)
        out = np.empty(np.broadcast(x, cells).shape)
        lay = self.cell_layer[cells]
        for L in self.layers:
            sel = lay == L.index
            if not sel.any():
                continue
            if L.beams is None:
                out[sel] = L.radio.bs_gain_db
                continue
            th, ph = self._angles(x[sel], y[sel], cells[sel])
            b = L.beams
            g = beam_gain_db(th, ph, L.beam_az, b.tilt_deg, b.panel[0], b.panel[1])
            out[sel] = np.take_along_axis(g, beams[sel][:, None], axis=-1)[:, 0]
        return out

    def all_beam_gains_db(self, x, y) -> np.ndarray:
        """Gains (P, C, B) of every beam of every cell towards the points (P,); NO_BEAM_DB where a cell has fewer."""
        x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
        P = len(x)
        out = np.full((P, self.n_cells, self.B), NO_BEAM_DB)
        c0 = 0
        for L in self.layers:
            cells = np.arange(c0, c0 + L.n_cells)
            c0 += L.n_cells
            if L.beams is None:
                out[:, cells, 0] = L.radio.bs_gain_db
                continue
            cc = np.broadcast_to(cells, (P, L.n_cells))
            th, ph = self._angles(x[:, None], y[:, None], cc)
            b = L.beams
            # single precision: the gains are needed to a small fraction of a dB
            out[:, cells, :L.n_beams] = beam_gain_db(th.astype(np.float32), ph.astype(np.float32), L.beam_az,
                                                     b.tilt_deg, b.panel[0], b.panel[1])
        return out

    def mean_gain_db(self, g_all: np.ndarray) -> np.ndarray:
        """Interference gain (P, C) from (P, C, B): mean linear gain over the cell's beams, or the abstraction."""
        lin = np.exp(g_all * LN10_10)
        m = lin.sum(-1) / self.n_beams
        return 10.0 * np.log10(m)

    # ---------------------------------------------------------------- nominal plan and positions
    def nominal_cell(self, x, y) -> np.ndarray:
        """Nominal best cell of layer 0 at points: the nearest site, the sector whose boresight is closest."""
        site = self.base_rmap.nominal_cell(x, y).astype(int)
        L = self.layers[0]
        if L.sectors == 1:
            return site
        sp = L.layout.sites[site]
        dx, dy = np.asarray(x) - sp[..., 0], np.asarray(y) - sp[..., 1]
        if self.base_layout.period_x:
            dx, dy = self.base_layout.nearest_image(dx, dy)
        az = np.degrees(np.arctan2(dy, dx))
        d = np.abs(wrap_deg(az[..., None] - L.boresight))
        return site * L.sectors + np.argmin(d, axis=-1)


class ExtChunk:
    """Radio samples of steps ``k0 .. k0 + n - 1`` of the extended model.

    ``lin`` (n, U, C) interference reference power [mW] (the desired power of a cell without beams);
    ``l1`` (nm, U, C) cell quality, SS-RSRP per RE with L1 error [dBm]; ``bl1`` (nm, U, C, B) beam L1
    values per RE [dBm]; ``site_db`` (n, U, S) site gains; ``x``, ``y`` (n, U) user positions; ``bg``
    (nm, U, C, B) antenna gains of every beam at the L1 instants [dBi], held over the L1 period.
    """
    __slots__ = ("k0", "n", "rsrp", "lin", "l1", "mp", "bl1", "site_db", "x", "y", "bg")

    def __init__(self, k0, n, lin, l1, mp, bl1, site_db, x, y, bg):
        self.k0, self.n, self.lin, self.l1, self.mp = k0, n, lin, l1, mp
        self.bl1, self.site_db, self.x, self.y, self.bg = bl1, site_db, x, y, bg
        self.rsrp = None


class ExtendedSource:
    """Chunks of the extended model for one world (all rules see the same samples)."""

    def __init__(self, world, chunk_steps: int = 1000):
        from .source import RadioSource
        self.world = world
        self.ext = ext = world.ext
        sc = world.scenario
        dt = sc.protocol.step_s
        self.mp = max(1, int(round(sc.protocol.l1_period_s / dt)))
        # chunks of at most 400 steps: the beam L1 array (nm, U, C, B) stays small
        self.chunk = max(self.mp, (min(chunk_steps, 400) // self.mp) * self.mp)
        self.sources = [RadioSource(world, self.chunk, layer=L) for L in ext.layers]
        self.X, self.Y = world.x, world.y
        self.S, self.U = self.X.shape
        self.rng = streams(world.seed, "beams", 1)[0]
        self.err = sc.radio.l1_error_db
        self.beam_cfg = [L.beams for L in ext.layers]

    def chunks(self) -> Iterator[ExtChunk]:
        ext, mp, U = self.ext, self.mp, self.U
        C, B = ext.n_cells, ext.B
        gens = [s.raw_chunks() for s in self.sources]
        while True:
            parts = [next(g, None) for g in gens]
            if parts[0] is None:
                return
            k0, n = parts[0][0], parts[0][1]
            site_db = np.concatenate([p[2] for p in parts], axis=2)              # (n, U, S)
            x, y = self.X[k0:k0 + n], self.Y[k0:k0 + n]
            # antenna gains at the L1 instants, held over the L1 period (the user moves < 2 m in 40 ms at
            # 160 km/h); the site gains change every step
            gsite = site_db[:, :, ext.cell_site] + ext.p0                         # (n, U, C)
            nm = -(-n // mp)
            xm, ym = x[::mp], y[::mp]
            bg = np.empty((nm, U, C, B), dtype=np.float32)
            blk = 25
            for a in range(0, nm, blk):
                b = min(nm, a + blk)
                bg[a:b] = ext.all_beam_gains_db(xm[a:b].ravel(), ym[a:b].ravel()).reshape(b - a, U, C, B)
            gm = ext.mean_gain_db(bg.astype(float))                                # (nm, U, C)
            lin = np.exp((gsite + np.repeat(gm, mp, axis=0)[:n]) * LN10_10)        # interference reference
            bl1 = bg + gsite[::mp][:, :, :, None]
            # beam L1 values per RE with an L1 error per beam, and the cell quality (TS 38.331 5.5.3.3)
            bl1 -= ext.re_off[None, None, :, None]
            bl1 += self.err * self.rng.standard_normal(bl1.shape)
            bl1[:, :, ext.n_beams[:, None] <= np.arange(B)[None, :]] = NO_BEAM_DB
            l1 = cell_quality(bl1, ext, self.beam_cfg)
            yield ExtChunk(k0, n, lin, l1, mp, bl1, site_db, x, y, bg)


def cell_quality(bl1: np.ndarray, ext: ExtendedRadio, cfgs) -> np.ndarray:
    """Cell measurement (..., C) from beam values (..., C, B) [dBm] (TS 38.331 clause 5.5.3.3).

    The highest beam, unless nrofSS-BlocksToAverage and absThreshSS-BlocksConsolidation are both
    configured and the highest beam is above the threshold: then the linear average of the highest
    beams above the threshold, at most nrofSS-BlocksToAverage of them.
    """
    best = bl1.max(-1)
    out = best.copy()
    c0 = 0
    for L, b in zip(ext.layers, cfgs):
        cells = slice(c0, c0 + L.n_cells)
        c0 += L.n_cells
        if b is None or b.ssb_avg is None or b.ssb_thresh_dbm is None:
            continue
        v = np.sort(bl1[..., cells, :], axis=-1)[..., ::-1][..., :b.ssb_avg]       # highest first
        above = v > b.ssb_thresh_dbm
        lin = np.where(above, np.exp(v * LN10_10), 0.0)
        k = above.sum(-1)
        avg = 10.0 * np.log10(np.maximum(lin.sum(-1), 1e-300) / np.maximum(k, 1))
        out[..., cells] = np.where(best[..., cells] > b.ssb_thresh_dbm, avg, best[..., cells])
    return out


def build_extended(scenario: Scenario, layout, rmap, seed: int) -> Optional[ExtendedRadio]:
    """The extended radio model of a world, or None if the scenario uses neither beams nor layers."""
    if not scenario.radio.extended:
        return None
    return ExtendedRadio(copy.deepcopy(scenario), layout, rmap, seed)
