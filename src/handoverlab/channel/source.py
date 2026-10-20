# SPDX-License-Identifier: MIT
"""Received powers and L1 samples of a run, produced chunk by chunk.

:class:`RadioSource` turns trajectories into received powers:

* street grid: lookup of the place-tied radio map;
* open area: path loss with a LOS state that is an AR(1) process along each
  user's own path (nothing repeatable by place), plus the place-tied
  shadowing field if any;
* plus, if ``place_share < 1``, a shadowing process along each user's path;
* plus a time-varying component (moving blockers), an AR(1) process updated
  once per L1 period.

It also draws the noisy L1 samples that feed the measurement filter.  Every
random number of the radio part comes from here, so all rules run on the same
world see identical samples.

Antenna abstraction: each site forms a beam of gain ``bs_gain_db`` towards the
user it serves and towards a user that measures it.  A site that serves other
users interferes with the mean gain of its data beams (``isolation`` times the
peak gain) scaled by its load.  No beam management and no fast fading.
"""
from __future__ import annotations

from typing import Iterator

import numpy as np
from scipy.signal import lfilter
from scipy.special import ndtri

from ..seeds import streams
from .pathloss import los_shadow_sd, mix_db, p_los, path_loss, soft_los_power_weight

LN10_10 = np.log(10.0) / 10.0


class Chunk:
    """Radio samples of the consecutive steps ``k0 .. k0 + n - 1``.

    ``rsrp`` (n, U, M) received power [dBm]; ``lin`` the same in mW; ``l1`` the
    noisy L1 samples at the measurement instants (steps with ``k % mp == 0``).
    """
    __slots__ = ("k0", "n", "rsrp", "lin", "l1", "mp")

    def __init__(self, k0, n, rsrp, lin, l1, mp):
        self.k0, self.n, self.rsrp, self.lin, self.l1, self.mp = k0, n, rsrp, lin, l1, mp

    @classmethod
    def from_rsrp(cls, k0: int, rsrp: np.ndarray, mp: int, l1: np.ndarray = None) -> "Chunk":
        """Chunk from given received powers (used by tests and custom radio sources)."""
        rsrp = np.asarray(rsrp, dtype=float)
        if l1 is None:
            l1 = rsrp[::mp].copy()
        return cls(k0, rsrp.shape[0], rsrp, np.exp(rsrp * LN10_10), l1, mp)


def _ar1(w, r, z):
    """Unit-variance AR(1) along axis 0 with coefficient ``r`` and previous value ``z``."""
    y, _ = lfilter([np.sqrt(1.0 - r * r)], [1.0, -r], w, axis=0, zi=(r * z)[None])
    return y


class RadioSource:
    """Received power of every site at every user and step."""

    def __init__(self, world, chunk_steps: int = 1000, layer=None):
        sc = world.scenario
        self.rmap = world.radio_map if layer is None else layer.rmap
        self.X, self.Y, self.V = world.x, world.y, world.speed
        self.S, self.U = self.X.shape
        self.M = self.rmap.layout.n_sites
        self.R = R = sc.radio if layer is None else layer.radio
        sub = 0 if layer is None else layer.sub
        dt = sc.protocol.step_s
        self.mp = max(1, int(round(sc.protocol.l1_period_s / dt)))
        self.chunk = max(self.mp, (chunk_steps // self.mp) * self.mp)   # whole L1 periods per chunk
        self.rng_t, self.rng_o, self.rng_m, self.rng_l = streams(world.seed, "radio", 4, sub)
        self.r_t = float(np.exp(-self.mp * dt / R.time_var_tau_s))     # per L1 period
        self.zt = self.rng_t.standard_normal((self.U, self.M))         # stationary start
        self.own = R.place_share < 1.0
        self.r_o = np.exp(-self.V * dt / R.shadow_decorr_m)            # per user and step
        self.zo = self.rng_o.standard_normal((self.U, self.M)) if self.own else None
        self.open = not self.rmap.is_grid
        if self.open:
            self.r_l = np.exp(-self.V * dt / R.los_corr_m)
            self.zl = self.rng_l.standard_normal((self.U, self.M))
        self.p0 = R.tx_power_dbm + R.bs_gain_db + R.ue_gain_db
        self.pen = 0.0                                  # per-user penetration gain [dB] (for raw_chunks)
        if R.penetration_db or R.penetration_sd_db:     # per-user loss on all links (own stream)
            rng = streams(world.seed, "penetration", 1)[0]
            pen = (R.penetration_db + R.penetration_sd_db * rng.standard_normal(self.U))[:, None]
            self.p0 = self.p0 - pen
            self.pen = -pen

    def _ar1_users(self, rng, r_u, z, n):
        """AR(1) along time with one coefficient per user -> (n, U, M)."""
        out = np.empty((n, self.U, self.M))
        for u in range(self.U):
            out[:, u, :] = _ar1(rng.standard_normal((n, self.M)), r_u[u], z[u])
        return out

    def _soft_open(self, x, y, sites, n, shape):
        """Static part of the received power with the soft LOS state (open area, indoor; since 1.7.0).

        The LOS process along each user's path gives ``G + F(d)``; the LOS and NLOS powers, each with
        its own path loss and shadowing standard deviation on the same unit shadowing, are mixed with
        the weights LOS_soft^2 and 1 - LOS_soft^2 (TR 38.901 Eq. 7.6-18 and 7.6-19).
        """
        R, rmap = self.R, self.rmap
        d2 = rmap.layout.distances(x, y, sites)
        g = self._ar1_users(self.rng_l, self.r_l, self.zl, n)
        self.zl = g[-1].copy()
        z = ndtri(np.clip(p_los(d2, R.pathloss), 1e-9, 1.0 - 1e-9)) - g.reshape(d2.shape)
        u = rmap.lookup(x, y).astype(np.float64) if rmap.has_field else np.zeros_like(d2)
        if self.own:
            o = self._ar1_users(self.rng_o, self.r_o, self.zo, n)
            self.zo = o[-1].copy()
            u += np.sqrt(1.0 - R.place_share) * o.reshape(d2.shape)
        args = (R.pathloss, R.carrier_ghz, R.bs_height_m, R.ue_height_m)
        g_l = -path_loss(d2, True, *args) + los_shadow_sd(d2, R) * u
        g_n = -path_loss(d2, False, *args) + R.shadow_nlos_db * u
        return mix_db(soft_los_power_weight(z, R.carrier_ghz, R.soft_los_d_m), g_l, g_n).reshape(shape)

    def chunks(self) -> Iterator[Chunk]:
        """Yield :class:`Chunk` objects covering the whole run in order."""
        for k0, n, rs in self._large_scale():
            nm = -(-n // self.mp)
            rs += self.p0
            l1 = rs[::self.mp] + self.R.l1_error_db * self.rng_m.standard_normal((nm, self.U, self.M))
            yield Chunk(k0, n, rs, np.exp(rs * LN10_10), l1, self.mp)

    def raw_chunks(self) -> Iterator[tuple]:
        """``(k0, n, gain)`` per chunk: the site gain [dB] of every step, user and site without the transmit
        power and the antenna gains, with the per-user penetration loss (used by the beam and multi-carrier
        model of :mod:`handoverlab.channel.extended`; no L1 error is drawn)."""
        for k0, n, rs in self._large_scale():
            rs += self.pen
            yield k0, n, rs

    def _large_scale(self) -> Iterator[tuple]:
        """Path loss, LOS state, shadowing and time variation of every step, user and site [dB]."""
        R, rmap = self.R, self.rmap
        sites = rmap.layout.sites
        for k0 in range(0, self.S, self.chunk):
            k1 = min(self.S, k0 + self.chunk)
            n = k1 - k0
            x = self.X[k0:k1].ravel()
            y = self.Y[k0:k1].ravel()
            shape = (n, self.U, self.M)
            sig = None
            if not rmap.is_grid and R.soft_los and R.los_model != "los":
                rs = self._soft_open(x, y, sites, n, shape)
            elif rmap.is_grid:
                rs = rmap.lookup(x, y).astype(np.float64).reshape(shape)
                if self.own:
                    s_los = R.shadow_los_db if R.shadow_los_far_db is None else los_shadow_sd(
                        rmap.layout.distances(x, y, sites), R)
                    sig = np.where(rmap.los_at(x, y), s_los, R.shadow_nlos_db).reshape(shape)
            else:
                d2 = rmap.layout.distances(x, y, sites)
                if R.los_model == "los":                  # every link LOS (TR 37.885 Table 6.2.1-2; since 1.11.0)
                    los = np.ones(d2.shape, dtype=bool)
                else:
                    g = self._ar1_users(self.rng_l, self.r_l, self.zl, n)
                    self.zl = g[-1].copy()
                    los = g.reshape(d2.shape) < ndtri(np.clip(p_los(d2, R.pathloss), 1e-9, 1.0 - 1e-9))
                rs = -path_loss(d2, los, R.pathloss, R.carrier_ghz, R.bs_height_m, R.ue_height_m).reshape(shape)
                sig = np.where(los, los_shadow_sd(d2, R), R.shadow_nlos_db).reshape(shape)
                if rmap.has_field:
                    rs += rmap.lookup(x, y).astype(np.float64).reshape(shape) * sig
            if self.own and sig is not None:
                o = self._ar1_users(self.rng_o, self.r_o, self.zo, n)
                self.zo = o[-1].copy()
                rs += np.sqrt(1.0 - R.place_share) * sig * o
            nm = -(-n // self.mp)
            if R.time_var_db > 0:
                zt = _ar1(self.rng_t.standard_normal((nm, self.U, self.M)), self.r_t, self.zt)
                self.zt = zt[-1].copy()
                rs += R.time_var_db * np.repeat(zt, self.mp, axis=0)[:n]
            yield k0, n, rs
