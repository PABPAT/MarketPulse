# core/calibration.py
# Brier score and calibration analysis for Polymarket and Kalshi

import math
from collections import defaultdict


def brier_score(predicted_prob: float, outcome: int) -> float:
    """
    Calculate Brier score for a single prediction.
    Brier = (predicted_probability - actual_outcome)²
    Lower is better. Perfect = 0.0, Random = 0.25
    """
    return (predicted_prob - outcome) ** 2


def mean_brier_score(markets: list[dict]) -> float:
    """
    Calculate mean Brier score across a list of resolved markets.
    Each market must have predicted_prob and outcome fields.
    """
    if not markets:
        return None

    scores = [
        brier_score(m["predicted_prob"], m["outcome"])
        for m in markets
    ]
    return round(sum(scores) / len(scores), 4)


def calibration_buckets(
    markets: list[dict],
    n_buckets: int = 10
) -> list[dict]:
    """
    Group markets into probability buckets and compute
    actual resolution rate per bucket.

    A perfectly calibrated platform should show:
    - Markets priced at 10% → resolve YES ~10% of the time
    - Markets priced at 50% → resolve YES ~50% of the time
    - Markets priced at 90% → resolve YES ~90% of the time

    Returns list of buckets with:
    - bucket_low, bucket_high: probability range
    - predicted_avg: average predicted probability in bucket
    - actual_rate: actual YES resolution rate
    - count: number of markets in bucket
    - calibration_error: abs(predicted_avg - actual_rate)
    """
    bucket_size = 1.0 / n_buckets
    buckets = defaultdict(list)

    for m in markets:
        prob = m["predicted_prob"]
        outcome = m["outcome"]
        bucket_idx = min(int(prob / bucket_size), n_buckets - 1)
        buckets[bucket_idx].append((prob, outcome))

    result = []
    for i in range(n_buckets):
        low = round(i * bucket_size, 2)
        high = round((i + 1) * bucket_size, 2)
        items = buckets.get(i, [])

        if not items:
            result.append({
                "bucket_low": low,
                "bucket_high": high,
                "predicted_avg": None,
                "actual_rate": None,
                "count": 0,
                "calibration_error": None,
            })
            continue

        probs = [x[0] for x in items]
        outcomes = [x[1] for x in items]
        predicted_avg = round(sum(probs) / len(probs), 4)
        actual_rate = round(sum(outcomes) / len(outcomes), 4)
        calibration_error = round(abs(predicted_avg - actual_rate), 4)

        result.append({
            "bucket_low": low,
            "bucket_high": high,
            "predicted_avg": predicted_avg,
            "actual_rate": actual_rate,
            "count": len(items),
            "calibration_error": calibration_error,
        })

    return result


def mean_calibration_error(buckets: list[dict]) -> float:
    """
    Mean calibration error across all non-empty buckets.
    Lower is better.
    """
    errors = [
        b["calibration_error"]
        for b in buckets
        if b["calibration_error"] is not None
    ]
    if not errors:
        return None
    return round(sum(errors) / len(errors), 4)


def platform_calibration_report(
    markets: list[dict],
    platform: str
) -> dict:
    """
    Full calibration report for a platform.
    """
    if not markets:
        return {
            "platform": platform,
            "market_count": 0,
            "brier_score": None,
            "mean_calibration_error": None,
            "buckets": [],
        }

    brier = mean_brier_score(markets)
    buckets = calibration_buckets(markets)
    mce = mean_calibration_error(buckets)

    return {
        "platform": platform,
        "market_count": len(markets),
        "brier_score": brier,
        "mean_calibration_error": mce,
        "buckets": [b for b in buckets if b["count"] > 0],
        "interpretation": interpret_brier(brier),
    }


def interpret_brier(score: float) -> str:
    """Human readable interpretation of Brier score."""
    if score is None:
        return "insufficient data"
    if score < 0.05:
        return "excellent calibration"
    if score < 0.10:
        return "good calibration"
    if score < 0.15:
        return "moderate calibration"
    if score < 0.20:
        return "poor calibration"
    return "very poor calibration"


if __name__ == "__main__":
    # Test with sample data
    test_markets = [
        {"predicted_prob": 0.9, "outcome": 1},
        {"predicted_prob": 0.8, "outcome": 1},
        {"predicted_prob": 0.7, "outcome": 1},
        {"predicted_prob": 0.3, "outcome": 0},
        {"predicted_prob": 0.2, "outcome": 0},
        {"predicted_prob": 0.1, "outcome": 0},
    ]

    report = platform_calibration_report(test_markets, "test")
    print(f"Brier score: {report['brier_score']}")
    print(f"Interpretation: {report['interpretation']}")
    print(f"Buckets:")
    for b in report["buckets"]:
        print(f"  {b['bucket_low']}-{b['bucket_high']}: "
              f"predicted={b['predicted_avg']} "
              f"actual={b['actual_rate']} "
              f"n={b['count']} "
              f"error={b['calibration_error']}")