# SPDX-License-Identifier: MIT
"""Fast fading (TR 38.901 clause 7.7.2 TDL models) and the link-to-system mapping (since 2.2.0)."""
import numpy as np
import pytest
from scipy import special, stats

import handoverlab as hl
from handoverlab.channel.fading import MODELS, TdlFading, first_tap_k_db, k_factor_db, rms_delay_spread, tdl_profile
from handoverlab.channel.l2s import bpsk_mi, capacity_esm, miesm_qpsk
from handoverlab.config import ConfigError


def _fading(model, U=200, M=5, fd=100.0, dt=1e-3, f=(0.0,), seed=1, k_db=None):
    return TdlFading(np.random.default_rng(seed), U, M, model, 100e-9, np.array(f), dt, np.full(U, fd), k_db)


def _taps(fad, model):
    """Complex amplitude of every Rayleigh tap (U, M, L) of a TdlFading."""
    U, M, LN = fad.z.shape
    L = int((~tdl_profile(model, 1.0)[2]).sum())
    return fad.z.reshape(U, M, L, LN // L).sum(-1) / np.sqrt(LN // L)


@pytest.mark.parametrize("model", MODELS)
def test_scaled_profile_has_the_wanted_delay_spread(model):
    """TR 38.901 Eq. 7.7-1: tau_scaled = tau_model x DS (criterion F4)."""
    for ds in (10e-9, 100e-9, 1000e-9):
        tau, p, _ = tdl_profile(model, ds)
        assert p.sum() == pytest.approx(1.0) and rms_delay_spread(tau, p) == pytest.approx(ds, rel=0.01)
    if model in ("tdl-d", "tdl-e"):
        tau, p, _ = tdl_profile(model, 100e-9, k_db=6.0)             # Eq. 7.7.6-1/-2, delays re-normalised
        assert rms_delay_spread(tau, p) == pytest.approx(100e-9, rel=1e-9)
        assert k_factor_db(model, 6.0) == pytest.approx(6.0, abs=1e-9)


def test_k_factor_of_the_tables():
    """Notes of Tables 7.7.2-4/-5: K1 = 13.3 dB (TDL-D) and 22 dB (TDL-E) for the first tap; K_model of
    Eq. 7.7.6-2 compares the LOS power with all Rayleigh taps."""
    assert first_tap_k_db("tdl-d") == pytest.approx(13.3, abs=1e-9)
    assert first_tap_k_db("tdl-e") == pytest.approx(22.0, abs=1e-9)
    _, p, los = tdl_profile("tdl-d", 1.0)
    assert k_factor_db("tdl-d") == pytest.approx(10 * np.log10(p[los].sum() / p[~los].sum()))
    assert 8.0 < k_factor_db("tdl-d") < 10.0
    with pytest.raises(ValueError):
        tdl_profile("tdl-a", 1.0, k_db=3.0)


def test_rayleigh_tap_power_and_distribution():
    """Criterion F1: mean power 1 within 2 %, KS test against Rayleigh p > 0.01."""
    r = []
    for seed in range(5):
        fad = _fading("tdl-b", U=400, M=10, seed=seed)
        g = _taps(fad, "tdl-b")[..., 0].ravel()
        r.append(np.abs(g))
    a = np.concatenate(r)[:20000]
    assert np.mean(a ** 2) == pytest.approx(1.0, rel=0.02)
    assert stats.kstest(a, lambda x: 1.0 - np.exp(-x * x)).pvalue > 0.01


def test_time_correlation_follows_the_jakes_spectrum():
    """Criterion F2: correlation of a Rayleigh tap against J0(2 pi f_D tau) within 0.07 for f_D tau <= 1
    (32 sinusoids since amendment 1 of the plan)."""
    fd, dt = 100.0, 1e-3
    fad = _fading("tdl-b", U=400, M=10, fd=fd, dt=dt)
    g0 = _taps(fad, "tdl-b")[..., 0].copy()
    for k in range(1, 11):                                          # f_D tau = 0.1 .. 1.0
        fad.gains()
        g = _taps(fad, "tdl-b")[..., 0]
        rho = np.real(np.mean(g * np.conj(g0))) / np.mean(np.abs(g0) ** 2)
        assert rho == pytest.approx(special.j0(2 * np.pi * fd * k * dt), abs=0.07)


def test_los_tap_k_factor_estimated_from_samples():
    """Criterion F3: the moment estimate of the first TDL-D tap's K-factor within 1 dB of 13.3 dB."""
    fad = _fading("tdl-d", U=2000, M=5)
    first = fad.z_los * fad.e_los[0] + _taps(fad, "tdl-d")[..., 0] * np.sqrt(tdl_profile("tdl-d", 1.0)[1][1])
    pw = np.abs(first.ravel()) ** 2
    g = np.var(pw) / np.mean(pw) ** 2
    k = np.sqrt(1.0 - g) / (1.0 - np.sqrt(1.0 - g))
    assert 10 * np.log10(k) == pytest.approx(13.3, abs=1.0)


def test_mean_gain_is_one():
    for model in MODELS:
        fad = _fading(model, U=300, M=10, f=np.linspace(-5e6, 5e6, 4))
        assert fad.gains().mean() == pytest.approx(1.0, rel=0.05)


def test_mutual_information_mapping():
    """Criteria L1 and L2: a flat channel maps to itself; the effective SINR never exceeds the mean."""
    assert bpsk_mi(np.array([1.0]))[0] == pytest.approx(0.486, abs=0.002)    # binary-input AWGN capacity at 0 dB
    for s in (0.05, 0.5, 5.0, 50.0):
        assert 10 * np.log10(miesm_qpsk(np.full(6, s))) == pytest.approx(10 * np.log10(s), abs=0.01)
        assert capacity_esm(np.full(6, s)) == pytest.approx(s)
    rng = np.random.default_rng(3)
    x = rng.exponential(1.0, (500, 8))
    assert np.all(miesm_qpsk(x) <= x.mean(1) + 1e-12) and np.all(capacity_esm(x) <= x.mean(1) + 1e-12)


SC = {"run.duration_s": 12.0, "run.warmup_s": 2.0, "mobility.users": 6}


def test_option_off_changes_nothing_and_on_is_reproducible():
    """Criteria E1 and E2 (the golden fingerprints check E1 for every card)."""
    sc = hl.builtin_scenario("smoke").with_overrides(SC)
    rules = [{"rule": "a3"}, {"rule": "cho"}]
    a = hl.simulate(sc, rules, seeds=[1])
    b = hl.simulate(sc.with_overrides({"radio.fast_fading": None}), rules, seeds=[1])
    assert [r.fingerprint for r in a] == [r.fingerprint for r in b]
    f = sc.with_overrides({"radio.fast_fading": "tdl-c", "radio.delay_spread_ns": 300.0})
    c = hl.simulate(f, rules, seeds=[1], debug=True)
    d = hl.simulate(f, rules, seeds=[1])
    assert [r.fingerprint for r in c] == [r.fingerprint for r in d]
    assert [r.fingerprint for r in c] != [r.fingerprint for r in a]
    assert "fast_fading" not in sc.to_dict()["radio"]                  # job IDs of 2.1.0 unchanged


def test_options_are_checked():
    sc = hl.builtin_scenario("smoke")
    for over, key in (({"radio.fast_fading": "tdl-x"}, "radio.fast_fading"),
                      ({"radio.fast_fading": "tdl-a", "radio.delay_spread_ns": 0.0}, "radio.delay_spread_ns"),
                      ({"radio.fast_fading": "tdl-a", "radio.fading_k_db": 9.0}, "radio.fading_k_db"),
                      ({"radio.fast_fading": "tdl-a", "protocol.meas_periods": "ts38133"}, "radio.fast_fading")):
        with pytest.raises(ConfigError, match=key):
            sc.with_overrides(over)
    with pytest.raises(ConfigError, match="radio.fast_fading"):
        hl.builtin_scenario("urban-grid-28ghz-beams").with_overrides({"radio.fast_fading": "tdl-a"})
