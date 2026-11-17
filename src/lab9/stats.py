"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import comb

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    if len(human) != len(judge):
        raise ValueError("human and judge must be the same length")
    results = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for h, j in zip(human, judge):
        if h not in ("FAIL", "PASS") or j not in ("FAIL", "PASS"):
            raise ValueError("human and judge must contain only 'FAIL' or 'PASS'")
        if h == "FAIL" and j == "FAIL":
            results["tp"] += 1
        elif h == "FAIL" and j == "PASS":
            results["fn"] += 1
        elif h == "PASS" and j == "FAIL":
            results["fp"] += 1
        else:
            results["tn"] += 1
    return results


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    cm = confusion(human, judge)
    precision = cm["tp"] / (cm["tp"] + cm["fp"]) if (cm["tp"] + cm["fp"]) > 0 else 0.0
    recall = cm["tp"] / (cm["tp"] + cm["fn"]) if (cm["tp"] + cm["fn"]) > 0 else 0.0
    return precision, recall


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    cm = confusion(human, judge)
    n = sum(cm.values())

    if n == 0:
        raise ValueError("Không có dữ liệu để tính kappa")

    observed_agreement = (cm["tp"] + cm["tn"]) / n

    human_fail = (cm["tp"] + cm["fn"]) / n
    judge_fail = (cm["tp"] + cm["fp"]) / n

    expected_agreement = (
        human_fail * judge_fail
        + (1 - human_fail) * (1 - judge_fail)
    )

    if expected_agreement == 1:
        raise ValueError("Kappa không xác định")

    return (
        (observed_agreement - expected_agreement)
        / (1 - expected_agreement)
    )

def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1]."""
    denominator = sensitivity + specificity - 1

    if denominator <= 0:
        raise ValueError("Judge không đủ khả năng để hiệu chỉnh tỷ lệ lỗi")

    corrected_rate = (
        observed_rate + specificity - 1
    ) / denominator

    return max(0.0, min(1.0, corrected_rate))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    import numpy as np
    from scipy.stats import bootstrap
    if len(a) != len(b):
        raise ValueError("Hai danh sách phải có cùng độ dài")

    if len(a) == 0:
        raise ValueError("Không có dữ liệu để so sánh")

    a_array = np.asarray(a, dtype=float)
    b_array = np.asarray(b, dtype=float)

    if a_array.ndim != 1 or b_array.ndim != 1:
        raise ValueError("Dữ liệu phải là danh sách một chiều")

    if not np.all(np.isfinite(a_array)) or not np.all(np.isfinite(b_array)):
        raise ValueError("Dữ liệu không được chứa NaN hoặc infinity")

    if np.array_equal(a_array, b_array):
        return 0.0, 0.0, 0.0

    if len(a_array) < 2:
        raise ValueError("Cần ít nhất hai item để bootstrap")

    def mean_difference(x, y):
        return np.mean(x) - np.mean(y)

    result = bootstrap(
        (a_array, b_array),
        statistic=mean_difference,
        paired=True,
        vectorized=False,
        n_resamples=n_resamples,
        confidence_level=confidence,
        method="percentile",
        rng=np.random.default_rng(rng),
    )

    delta = mean_difference(a_array, b_array)

    return (
        float(delta),
        float(result.confidence_interval.low),
        float(result.confidence_interval.high),
    )


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    _validate_pass_k(n, c, k)
    return 1.0 - (comb(n - c, k) / comb(n, k) if n - c >= k else 0.0)


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    _validate_pass_k(n, c, k)
    return comb(c, k) / comb(n, k) if c >= k else 0.0


def _validate_pass_k(n: int, c: int, k: int) -> None:
    if any(type(v) is not int for v in (n, c, k)) or not (n >= 1 and 0 <= c <= n and 1 <= k <= n):
        raise ValueError("Require integer n >= 1, 0 <= c <= n, and 1 <= k <= n")
