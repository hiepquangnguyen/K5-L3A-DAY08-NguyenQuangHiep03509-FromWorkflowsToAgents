"""Standard-library-only statistics for Bonus B4.

Provides:
- Cluster bootstrap 95% CI for pass rate (resampling by claim_id).
- Exact two-sided McNemar test on paired (claim_id, seed) pass/fail outcomes.
- Exact two-sided sign test on paired continuous metrics (e.g., cost_estimate).
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from typing import Any


def bootstrap_pass_rate_ci(
    trials: list[dict[str, Any]],
    *,
    n_boot: int = 2000,
    seed: int = 42,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Cluster bootstrap confidence interval for pass_rate, resampling claims."""
    graded = [row for row in trials if row.get("passed") is not None]
    if not graded:
        return {"point": None, "ci_low": None, "ci_high": None, "n_claims": 0, "n_trials": 0}

    by_claim: dict[str, list[int]] = defaultdict(list)
    for row in graded:
        by_claim[str(row["claim_id"])].append(1 if row["passed"] else 0)

    clusters = [by_claim[cid] for cid in sorted(by_claim)]
    n_claims = len(clusters)
    point = sum(v for c in clusters for v in c) / len(graded)

    rng = random.Random(seed)
    samples: list[float] = []
    for _ in range(n_boot):
        chosen = rng.choices(clusters, k=n_claims)
        total = sum(len(c) for c in chosen)
        passed = sum(v for c in chosen for v in c)
        samples.append(passed / total)

    samples.sort()
    low_idx = max(0, min(n_boot - 1, int(math.floor((alpha / 2.0) * (n_boot - 1)))))
    high_idx = max(0, min(n_boot - 1, int(math.ceil((1.0 - alpha / 2.0) * (n_boot - 1)))))
    return {
        "point": point,
        "ci_low": samples[low_idx],
        "ci_high": samples[high_idx],
        "n_claims": n_claims,
        "n_trials": len(graded),
        "n_boot": n_boot,
    }


def _exact_two_sided_binomial_p(k: int, n: int) -> float:
    """Exact two-sided p-value for Binomial(n, 0.5) at minor count k = min(k, n - k)."""
    if n <= 0:
        return 1.0
    minor = min(k, n - k)
    if minor * 2 == n:
        return 1.0
    log_half_n = -n * math.log(2.0)
    tail = 0.0
    for i in range(minor + 1):
        log_comb = math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
        tail += math.exp(log_comb + log_half_n)
    return min(1.0, 2.0 * tail)


def mcnemar_paired_test(
    trials_a: list[dict[str, Any]],
    trials_b: list[dict[str, Any]],
) -> dict[str, Any]:
    """Exact two-sided McNemar test on paired (claim_id, seed) trials."""
    map_a = {(row["claim_id"], row["seed"]): bool(row["passed"]) for row in trials_a if row.get("passed") is not None}
    map_b = {(row["claim_id"], row["seed"]): bool(row["passed"]) for row in trials_b if row.get("passed") is not None}
    keys = sorted(set(map_a) & set(map_b))

    n11 = n10 = n01 = n00 = 0
    for key in keys:
        a, b = map_a[key], map_b[key]
        if a and b:
            n11 += 1
        elif a and not b:
            n10 += 1
        elif not a and b:
            n01 += 1
        else:
            n00 += 1

    discordant = n10 + n01
    p_value = _exact_two_sided_binomial_p(min(n10, n01), discordant)
    return {
        "pairs": len(keys),
        "both_pass": n11,
        "a_only_pass": n10,
        "b_only_pass": n01,
        "both_fail": n00,
        "discordant": discordant,
        "p_value": p_value,
        "significant_0_05": p_value < 0.05,
    }


def sign_test_paired_metric(
    trials_a: list[dict[str, Any]],
    trials_b: list[dict[str, Any]],
    *,
    metric: str = "cost_estimate",
    tol: float = 1e-9,
) -> dict[str, Any]:
    """Exact two-sided sign test on paired (claim_id, seed) metric values."""
    map_a = {(row["claim_id"], row["seed"]): float(row[metric]) for row in trials_a}
    map_b = {(row["claim_id"], row["seed"]): float(row[metric]) for row in trials_b}
    keys = sorted(set(map_a) & set(map_b))

    a_lower = a_higher = ties = 0
    for key in keys:
        diff = map_a[key] - map_b[key]
        if abs(diff) <= tol:
            ties += 1
        elif diff < 0:
            a_lower += 1
        else:
            a_higher += 1

    non_tied = a_lower + a_higher
    p_value = _exact_two_sided_binomial_p(min(a_lower, a_higher), non_tied)
    return {
        "metric": metric,
        "pairs": len(keys),
        "a_lower": a_lower,
        "a_higher": a_higher,
        "ties": ties,
        "non_tied": non_tied,
        "p_value": p_value,
        "significant_0_05": p_value < 0.05,
    }
