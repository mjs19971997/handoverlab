# SPDX-License-Identifier: MIT
"""Paired statistics for comparing handover rules.

Rules compared on the same seed run on the same world and the same radio
samples, so the unit of analysis is one run (condition and seed) and two
rules are compared through their *paired differences*.  Per-run rates are
ratios of small counts with many ties and zeros, which is why a rank test
with an exact null distribution is the default.

* :func:`paired_differences` and :func:`t_interval`;
* :func:`bootstrap_ci`: percentile bootstrap of the mean paired difference,
  or of the ratio of the two means (pairs are resampled together);
* :func:`wilcoxon_signed_rank`: two-sided Wilcoxon signed-rank test, zero
  differences dropped, ties with mid-ranks; ``method="exact"`` builds the null
  distribution exactly for the ranks present, ``"approx"`` uses the normal
  approximation with tie and continuity corrections, ``"auto"`` is exact up
  to :data:`EXACT_MAX` non-zero differences;
* :func:`holm`: Holm's step-down adjustment of a family of p-values;
* :func:`paired_summary`: all of the above for one comparison;
* :func:`noninferior`, :func:`seeds_needed`: a one-sided margin check and a
  simple planning aid;
* :func:`rnd`: decimal rounding half away from zero for printing, so that a
  value such as 0.0975 always prints the same way.

Only NumPy and SciPy (for the t and normal quantiles) are used.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, Optional, Sequence, Tuple

import numpy as np
from scipy import stats as _st

#: differences closer than this to each other (or to zero) count as equal
TIE_TOL = 1e-9
#: ``method="auto"`` uses the exact null distribution up to this many non-zero differences
EXACT_MAX = 500


def paired_differences(a: Sequence[float], b: Sequence[float]) -> np.ndarray:
    """``a - b`` element by element; ``a`` and ``b`` must be paired (same order of runs)."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if a.shape != b.shape or a.ndim != 1:
        raise ValueError("paired samples need two 1-D arrays of the same length (got %s and %s)"
                         % (a.shape, b.shape))
    return a - b


def t_interval(d: Sequence[float], level: float = 0.95) -> Tuple[float, float]:
    """Two-sided t interval of the mean of ``d`` (``(nan, nan)`` for fewer than two values)."""
    d = np.asarray(d, dtype=float)
    n = len(d)
    if n < 2:
        return float("nan"), float("nan")
    m = float(d.mean())
    h = float(_st.t.ppf(0.5 + level / 2.0, n - 1) * d.std(ddof=1) / math.sqrt(n))
    return m - h, m + h


def bootstrap_ci(a: Sequence[float], b: Optional[Sequence[float]] = None, stat: str = "mean_diff",
                 n_boot: int = 2000, level: float = 0.95, seed: int = 0) -> Tuple[float, float]:
    """Percentile bootstrap interval for paired data.

    ``stat="mean_diff"``: mean of ``a - b`` (or of ``a`` alone if ``b`` is
    None).  ``stat="ratio"``: ratio of the means ``mean(a) / mean(b)``.  Runs
    are resampled with replacement as pairs, with a seeded generator, so the
    interval is reproducible.  For the ratio, resamples whose baseline mean is
    zero are dropped: the interval is conditional on a non-zero baseline mean
    (NaN if no resample is left).
    """
    a = np.asarray(a, dtype=float)
    n = len(a)
    if b is not None:
        b = np.asarray(b, dtype=float)
        if b.shape != a.shape:
            raise ValueError("paired samples need the same length")
    if n < 2:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(int(n_boot), n))
    if stat == "mean_diff":
        d = a - b if b is not None else a
        boot = d[idx].mean(axis=1)
    elif stat == "ratio":
        if b is None:
            raise ValueError("stat='ratio' needs two samples")
        num = a[idx].mean(axis=1)
        den = b[idx].mean(axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            boot = num / den
        boot = boot[np.isfinite(boot)]
        if not len(boot):
            return float("nan"), float("nan")
    else:
        raise ValueError("stat must be 'mean_diff' or 'ratio'")
    lo, hi = np.quantile(boot, [0.5 - level / 2.0, 0.5 + level / 2.0])
    return float(lo), float(hi)


@dataclass
class WilcoxonResult:
    """Result of :func:`wilcoxon_signed_rank`."""
    p: float               # two-sided p-value
    w_plus: float          # sum of the (mid-)ranks of the positive differences
    n: int                 # number of non-zero differences used
    method: str            # "exact", "approx" or "none" (all differences zero)


def _mid_ranks2(a: np.ndarray) -> np.ndarray:
    """Twice the mid-ranks of ``a`` (an integer array); values within TIE_TOL are tied."""
    n = len(a)
    order = np.argsort(a, kind="mergesort")
    ranks2 = np.empty(n, dtype=np.int64)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and a[order[j + 1]] - a[order[i]] <= TIE_TOL:
            j += 1
        ranks2[order[i:j + 1]] = (i + 1) + (j + 1)        # 2 x mean of the ranks i+1 .. j+1
        i = j + 1
    return ranks2


def wilcoxon_signed_rank(d: Sequence[float], method: str = "auto") -> WilcoxonResult:
    """Two-sided Wilcoxon signed-rank test of the paired differences ``d``.

    Differences within :data:`TIE_TOL` of zero are dropped; tied absolute
    differences get mid-ranks.  ``method="exact"`` computes the null
    distribution of the signed-rank sum exactly for the ranks present (each
    rank joins the positive sum with probability 1/2), which is valid with
    ties.  ``method="approx"`` uses the normal approximation with the tie
    correction of the variance and a continuity correction of 1/2.
    ``method="auto"`` is exact up to :data:`EXACT_MAX` non-zero differences.
    """
    if method not in ("auto", "exact", "approx"):
        raise ValueError("method must be 'auto', 'exact' or 'approx'")
    d = np.asarray(d, dtype=float)
    d = d[np.abs(d) > TIE_TOL]
    n = len(d)
    if n == 0:
        return WilcoxonResult(1.0, 0.0, 0, "none")
    ranks2 = _mid_ranks2(np.abs(d))
    w2 = int(ranks2[d > 0].sum())
    if method == "approx" or (method == "auto" and n > EXACT_MAX):
        total2 = int(ranks2.sum())
        mean2 = total2 / 2.0
        var2 = float((ranks2.astype(float) ** 2).sum()) / 4.0      # variance of the doubled statistic
        if var2 <= 0:
            return WilcoxonResult(1.0, w2 / 2.0, n, "approx")
        dev = abs(w2 - mean2) - 1.0                                 # continuity: 1/2 on the original scale
        z = max(dev, 0.0) / math.sqrt(var2)
        p = float(min(1.0, 2.0 * _st.norm.sf(z)))
        return WilcoxonResult(p, w2 / 2.0, n, "approx")
    total2 = int(ranks2.sum())
    dist = np.zeros(total2 + 1)
    dist[0] = 1.0
    for r in ranks2:
        r = int(r)
        nxt = 0.5 * dist
        nxt[r:] += 0.5 * dist[:-r]
        dist = nxt
    lo = float(dist[:w2 + 1].sum())
    hi = float(dist[w2:].sum())
    return WilcoxonResult(float(min(1.0, 2.0 * min(lo, hi))), w2 / 2.0, n, "exact")


def holm(pvals: Sequence[float]) -> list:
    """Holm-adjusted p-values, in the order given (NaN values are kept and not counted)."""
    p = np.asarray(pvals, dtype=float)
    adj = np.full(len(p), np.nan)
    ok = np.nonzero(~np.isnan(p))[0]
    m = len(ok)
    order = ok[np.argsort(p[ok], kind="mergesort")]
    run = 0.0
    for k, i in enumerate(order):
        run = max(run, (m - k) * p[i])
        adj[i] = min(1.0, run)
    return adj.tolist()


def paired_summary(a: Sequence[float], b: Sequence[float], level: float = 0.95, n_boot: int = 2000,
                   seed: int = 0, method: str = "auto") -> Dict[str, Any]:
    """Comparison of ``a`` (a rule) with ``b`` (the baseline) over paired runs.

    Returns the number of pairs, both means, the mean difference ``a - b``
    with its t interval and bootstrap interval, the relative change of the
    means in per cent, the bootstrap interval of the ratio of the means, the
    Wilcoxon p-value, the number of non-zero differences and the test method.
    """
    d = paired_differences(a, b)
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    n = len(d)
    nan = float("nan")
    m = float(d.mean()) if n else nan
    mb = float(b.mean()) if n else nan
    t_lo, t_hi = t_interval(d, level)
    b_lo, b_hi = bootstrap_ci(d, None, "mean_diff", n_boot, level, seed) if n_boot else (nan, nan)
    r_lo, r_hi = bootstrap_ci(a, b, "ratio", n_boot, level, seed) if n_boot and n else (nan, nan)
    w = wilcoxon_signed_rank(d, method)
    return dict(n=n, mean=float(a.mean()) if n else nan, mean_base=mb, diff=m, t_lo=t_lo, t_hi=t_hi,
                boot_lo=b_lo, boot_hi=b_hi, rel_pct=100.0 * m / mb if n and abs(mb) > 1e-12 else nan,
                ratio_lo=r_lo, ratio_hi=r_hi, p=w.p, n_nonzero=w.n, test=w.method)


def noninferior(d: Sequence[float], margin: float, level: float = 0.95) -> bool:
    """True if the upper end of the one-sided ``level`` t interval of mean(d) lies below ``margin``.

    Use it for statements such as "failures not higher than the baseline by
    more than ``margin``" with ``d`` = rule minus baseline.
    """
    d = np.asarray(d, dtype=float)
    n = len(d)
    if n < 2:
        return False
    hi = float(d.mean() + _st.t.ppf(level, n - 1) * d.std(ddof=1) / math.sqrt(n))
    return hi < margin


def seeds_needed(sd: float, half_width: float, level: float = 0.95) -> int:
    """Number of paired runs for a t interval of the given half-width when the differences have spread ``sd``."""
    if half_width <= 0:
        raise ValueError("half_width must be positive")
    n = 2
    while n < 100000:
        if _st.t.ppf(0.5 + level / 2.0, n - 1) * sd / math.sqrt(n) <= half_width:
            return n
        n += 1
    return n


def rnd(x: Any, nd: int = 3) -> str:
    """``x`` rounded to ``nd`` decimals, half away from zero, as a string ("n/a" for None, NaN and inf)."""
    if x is None:
        return "n/a"
    x = float(x)
    if math.isnan(x) or math.isinf(x):
        return "n/a"
    q = Decimal(1).scaleb(-nd)
    s = str(Decimal(repr(x)).quantize(q, rounding=ROUND_HALF_UP))
    if s.startswith("-") and Decimal(s) == 0:
        s = s[1:]
    return s


__all__ = ["TIE_TOL", "EXACT_MAX", "paired_differences", "t_interval", "bootstrap_ci", "WilcoxonResult",
           "wilcoxon_signed_rank", "holm", "paired_summary", "noninferior", "seeds_needed", "rnd"]
