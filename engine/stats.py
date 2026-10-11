"""Statistics for the Monte Carlo comparison.

Clopper-Pearson (exact binomial) confidence intervals on the blow-out
proportion, and a pooled two-proportion z-test between modes. Both use scipy
only (no statsmodels dependency).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats


@dataclass(frozen=True)
class ProportionCI:
    """A proportion with an exact (Clopper-Pearson) confidence interval."""

    successes: int
    trials: int
    proportion: float
    low: float
    high: float
    confidence: float


def clopper_pearson(successes: int, trials: int, confidence: float = 0.95) -> ProportionCI:
    """Exact binomial confidence interval via the Beta distribution."""
    if trials <= 0:
        return ProportionCI(0, 0, float("nan"), float("nan"), float("nan"), confidence)
    alpha = 1.0 - confidence
    k, n = int(successes), int(trials)
    low = 0.0 if k == 0 else stats.beta.ppf(alpha / 2.0, k, n - k + 1)
    high = 1.0 if k == n else stats.beta.ppf(1.0 - alpha / 2.0, k + 1, n - k)
    return ProportionCI(k, n, k / n, float(low), float(high), confidence)


@dataclass(frozen=True)
class TwoProportionTest:
    """Result of a pooled two-proportion z-test (two-sided)."""

    label_a: str
    label_b: str
    prop_a: float
    prop_b: float
    z: float
    p_value: float


def two_proportion_z_test(
    successes_a: int,
    trials_a: int,
    successes_b: int,
    trials_b: int,
    label_a: str = "A",
    label_b: str = "B",
) -> TwoProportionTest:
    """Pooled two-sided z-test for a difference in two proportions."""
    if trials_a <= 0 or trials_b <= 0:
        return TwoProportionTest(label_a, label_b, float("nan"), float("nan"), float("nan"), float("nan"))
    pa = successes_a / trials_a
    pb = successes_b / trials_b
    pooled = (successes_a + successes_b) / (trials_a + trials_b)
    se = np.sqrt(pooled * (1.0 - pooled) * (1.0 / trials_a + 1.0 / trials_b))
    if se == 0.0:
        # No variance (e.g. both 0% or both 100%): difference is zero if equal.
        z = 0.0 if pa == pb else float("inf")
        p = 1.0 if pa == pb else 0.0
        return TwoProportionTest(label_a, label_b, pa, pb, z, p)
    z = (pa - pb) / se
    p = 2.0 * stats.norm.sf(abs(z))
    return TwoProportionTest(label_a, label_b, pa, pb, float(z), float(p))
