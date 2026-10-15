# SPDX-License-Identifier: MIT
"""Paired statistics: Wilcoxon signed-rank (exact and approximate), Holm, intervals, rounding."""
import itertools
import math

import numpy as np
import pytest
from scipy import stats as st

from handoverlab import stats


def brute_force_p(d):
    """Exact two-sided p-value by enumerating every sign assignment (mid-ranks, zeros dropped)."""
    d = np.asarray([x for x in d if abs(x) > stats.TIE_TOL], dtype=float)
    if not len(d):
        return 1.0
    ranks = st.rankdata(np.abs(d))
    w = ranks[d > 0].sum()
    sums = [sum(r for r, s in zip(ranks, signs) if s) for signs in itertools.product((0, 1), repeat=len(d))]
    sums = np.array(sums)
    lo = np.mean(sums <= w + 1e-9)
    hi = np.mean(sums >= w - 1e-9)
    return min(1.0, 2 * min(lo, hi))


@pytest.mark.parametrize("d", [
    [1.5, -0.5, 2.0, 3.0, 0.7, 1.1, -0.2, 2.2],
    [1, 1, -1, 2, 2, 2, -3, 0, 0, 4],                     # ties and zeros
    [0.25, 0.25, 0.25, -0.25, 0.5, 0.5, 0.75, 1.0, 1.0, -1.0, 0.0, 1.25],
    [-2.0, -1.0, -1.0, -3.0, -0.5],
    [0.1],
])
def test_exact_wilcoxon_matches_enumeration(d):
    r = stats.wilcoxon_signed_rank(d, method="exact")
    assert r.method == "exact"
    assert r.p == pytest.approx(brute_force_p(d), abs=1e-12)
    assert r.n == sum(abs(x) > stats.TIE_TOL for x in d)


def test_exact_wilcoxon_without_ties_matches_tables():
    # n = 10 with ranks 1-5 negative: W+ = 6 + 7 + 8 + 9 + 10 = 40
    d = np.arange(1, 11, dtype=float)
    d[:5] *= -1
    r = stats.wilcoxon_signed_rank(d, "exact")
    assert r.w_plus == 40.0
    assert r.p == pytest.approx(brute_force_p(d))
    # all positive, n = 6: p = 2 / 2^6
    assert stats.wilcoxon_signed_rank([1, 2, 3, 4, 5, 6], "exact").p == pytest.approx(2 / 64)


def test_all_zero_differences():
    r = stats.wilcoxon_signed_rank([0.0, 0.0, 1e-12])
    assert (r.p, r.n, r.method) == (1.0, 0, "none")


def test_approximation_is_close_to_exact_for_many_pairs():
    rng = np.random.default_rng(5)
    d = np.round(rng.normal(0.3, 1.0, 60), 1)            # ties from rounding
    ex = stats.wilcoxon_signed_rank(d, "exact").p
    ap = stats.wilcoxon_signed_rank(d, "approx").p
    assert ap == pytest.approx(ex, rel=0.1, abs=0.002)


def test_approximation_against_the_textbook_formula():
    d = [3.0, -1.0, 4.0, 1.5, 5.0, 9.0, -2.5, 6.0, 7.5, 2.0, 8.0, 10.0]
    r = stats.wilcoxon_signed_rank(d, "approx")
    n = len(d)
    ranks = st.rankdata(np.abs(d))
    w = ranks[np.array(d) > 0].sum()
    mu, sd = n * (n + 1) / 4, math.sqrt(n * (n + 1) * (2 * n + 1) / 24)
    z = (abs(w - mu) - 0.5) / sd
    assert r.p == pytest.approx(2 * st.norm.sf(z), rel=1e-12)


def test_auto_switches_to_the_approximation(monkeypatch):
    monkeypatch.setattr(stats, "EXACT_MAX", 5)
    assert stats.wilcoxon_signed_rank([1, 2, 3, 4, 5, 6]).method == "approx"
    assert stats.wilcoxon_signed_rank([1, 2, 3]).method == "exact"


def test_holm():
    adj = stats.holm([0.01, 0.04, 0.03, 0.005])
    assert adj == pytest.approx([0.03, 0.06, 0.06, 0.02])
    assert math.isnan(stats.holm([0.5, float("nan"), 0.01])[1])            # NaN kept, not counted
    assert stats.holm([0.5, float("nan"), 0.01])[2] == pytest.approx(0.02)
    assert stats.holm([0.3, 0.4]) == pytest.approx([0.6, 0.6])          # monotone
    assert stats.holm([0.9, 0.8]) == [1.0, 1.0]                         # capped at 1


def test_t_interval_and_paired_summary():
    a = np.array([2.0, 3.0, 2.5, 4.0, 3.5])
    b = np.array([1.5, 2.5, 2.5, 3.0, 3.0])
    d = a - b
    lo, hi = stats.t_interval(d)
    h = st.t.ppf(0.975, 4) * d.std(ddof=1) / math.sqrt(5)
    assert (lo, hi) == pytest.approx((d.mean() - h, d.mean() + h))
    s = stats.paired_summary(a, b, n_boot=500)
    assert s["n"] == 5 and s["diff"] == pytest.approx(d.mean())
    assert s["boot_lo"] <= s["diff"] <= s["boot_hi"]
    assert s["ratio_lo"] <= a.mean() / b.mean() <= s["ratio_hi"]
    assert s["rel_pct"] == pytest.approx(100 * d.mean() / b.mean())
    assert s["test"] == "exact" and s["n_nonzero"] == 4
    with pytest.raises(ValueError):
        stats.paired_differences([1, 2], [1, 2, 3])


def test_bootstrap_is_reproducible_and_seeded():
    rng = np.random.default_rng(1)
    d = rng.normal(1.0, 1.0, 30)
    assert stats.bootstrap_ci(d, seed=3) == stats.bootstrap_ci(d, seed=3)
    assert stats.bootstrap_ci(d, seed=3) != stats.bootstrap_ci(d, seed=4)
    lo, hi = stats.bootstrap_ci(d, n_boot=4000)
    tlo, thi = stats.t_interval(d)
    assert lo == pytest.approx(tlo, abs=0.15) and hi == pytest.approx(thi, abs=0.15)
    assert all(math.isnan(x) for x in stats.bootstrap_ci([1.0]))


def test_noninferiority_and_planning():
    d = np.array([0.01, -0.02, 0.0, 0.015, -0.01, 0.005, 0.0, -0.005])
    assert stats.noninferior(d, margin=0.05)
    assert not stats.noninferior(d + 0.05, margin=0.05)
    n = stats.seeds_needed(sd=1.0, half_width=0.5)
    assert st.t.ppf(0.975, n - 1) / math.sqrt(n) <= 0.5 < st.t.ppf(0.975, n - 2) / math.sqrt(n - 1)


@pytest.mark.parametrize("x, nd, want", [(0.0975, 3, "0.098"), (0.0965, 3, "0.097"), (-0.0975, 3, "-0.098"),
                                         (2.5, 0, "3"), (-0.0004, 3, "0.000"), (1.23456, 2, "1.23"),
                                         (float("nan"), 3, "n/a"), (None, 3, "n/a")])
def test_decimal_rounding(x, nd, want):
    assert stats.rnd(x, nd) == want
