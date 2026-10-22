# SPDX-License-Identifier: MIT
"""Checks of the optional fast fading and the link-to-system mapping (since 2.2.0).

The criteria were fixed before the model was written (TR 38.901 V19.5.0 clauses 7.7.2, 7.7.3 and 7.7.6):
Rayleigh taps with unit power and the Jakes time correlation, the K-factor of the TDL-D first tap, the delay
spread of the scaled profiles, and the effective-SINR mappings (exact on a flat channel, never above the mean).
"""
from __future__ import annotations

import numpy as np

from ..channel.fading import MODELS, TdlFading, first_tap_k_db, rms_delay_spread, tdl_profile
from ..channel.l2s import capacity_esm, miesm_qpsk


def _taps(fad, n_ray):
    U, M, LN = fad.z.shape
    return fad.z.reshape(U, M, n_ray, LN // n_ray).sum(-1) / np.sqrt(LN // n_ray)


def fading_checks(rep) -> None:
    from scipy import special, stats
    rep.section("fading", "fast fading (TR 38.901 clause 7.7.2 TDL models) and link-to-system mapping (since 2.2.0)")
    fd, dt, n_ray = 100.0, 1e-3, 23
    amp, rho = [], []
    for seed in range(5):
        fad = TdlFading(np.random.default_rng(seed), 400, 10, "tdl-b", 100e-9, np.zeros(1), dt, np.full(400, fd))
        g0 = _taps(fad, n_ray)[..., 0].copy()
        amp.append(np.abs(g0).ravel())
        if seed == 0:
            for k in range(1, 11):
                fad.gains()
                g = _taps(fad, n_ray)[..., 0]
                rho.append(np.real(np.mean(g * np.conj(g0))) / np.mean(np.abs(g0) ** 2))
    a = np.concatenate(amp)[:20000]
    p = stats.kstest(a, lambda x: 1.0 - np.exp(-x * x)).pvalue
    rep.check("F1 Rayleigh tap: mean power 1 within 2 %, KS test against Rayleigh p > 0.01 (20 000 samples)",
              abs(np.mean(a ** 2) - 1.0) <= 0.02 and p > 0.01, "mean power %.4f, p = %.3f" % (np.mean(a ** 2), p))
    j0 = special.j0(2 * np.pi * fd * dt * np.arange(1, 11))
    err = float(np.max(np.abs(np.array(rho) - j0)))
    rep.check("F2 time correlation of a Rayleigh tap against J0(2 pi f_D tau), f_D tau = 0.1 .. 1: within 0.07",
              err <= 0.07, "largest difference %.3f" % err)
    fad = TdlFading(np.random.default_rng(7), 2000, 5, "tdl-d", 100e-9, np.zeros(1), dt, np.full(2000, fd))
    p1 = tdl_profile("tdl-d", 1.0)[1]
    first = fad.z_los * fad.e_los[0] + _taps(fad, 13)[..., 0] * np.sqrt(p1[1])
    pw = np.abs(first.ravel()) ** 2
    gam = np.var(pw) / np.mean(pw) ** 2
    k_est = 10 * np.log10(np.sqrt(1.0 - gam) / (1.0 - np.sqrt(1.0 - gam)))
    rep.check("F3 TDL-D first tap: estimated K-factor within 1 dB of 13.3 dB (Table 7.7.2-4 note; table value %.1f dB)"
              % first_tap_k_db("tdl-d"), abs(k_est - 13.3) <= 1.0, "%.2f dB" % k_est)
    worst = max(abs(rms_delay_spread(*tdl_profile(m, 100e-9)[:2]) / 100e-9 - 1.0) for m in MODELS)
    worst_k = max(abs(rms_delay_spread(*tdl_profile(m, 100e-9, 6.0)[:2]) / 100e-9 - 1.0) for m in ("tdl-d", "tdl-e"))
    rep.check("F4 RMS delay spread of the scaled profiles (Eq. 7.7-1) within 1 % of DS, all five models and after a "
              "K change (Eq. 7.7.6-1/-2)", max(worst, worst_k) <= 0.01,
              "largest deviation %.2f %% (%.1e after a K change)" % (100 * worst, worst_k))
    flat = max(abs(10 * np.log10(miesm_qpsk(np.full(6, s)) / s)) for s in (0.05, 0.5, 5.0, 50.0))
    x = np.random.default_rng(3).exponential(1.0, (2000, 8))
    rep.check("L1 effective SINR of a flat channel equals its SINR within 0.01 dB (MIESM QPSK)", flat <= 0.01,
              "largest difference %.4f dB" % flat)
    rep.check("L2 effective SINR never above the mean SINR (MIESM QPSK and capacity, 2000 random channels)",
              bool(np.all(miesm_qpsk(x) <= x.mean(1) + 1e-12) and np.all(capacity_esm(x) <= x.mean(1) + 1e-12)))
