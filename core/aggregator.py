# core/aggregator.py
# Aggregates Polymarket bucket markets into synthetic "above X%" markets
# to match against Kalshi binary markets

import re


def extract_exact_threshold(question: str) -> float | None:
    """
    Extract exact threshold from Polymarket bucket question.
    Handles: "be 3.75%", "be ≥ 4.5%", "be ≤ 1.0%"
    """
    q = question.lower()

    # Handle "≥ X%" — this is the top bucket, means above this value
    if "≥" in question or ">=" in q:
        match = re.search(r'(\d+\.?\d*)\s*%', question)
        return float(match.group(1)) if match else None

    # Handle "≤ X%" — this is the bottom bucket, means below this value
    if "≤" in question or "<=" in q:
        return None  # skip bottom bucket for "above X%" aggregation

    # Handle "be X%" — exact bucket
    match = re.search(r'be\s+(\d+\.?\d*)\s*%', question.lower())
    if match:
        return float(match.group(1))

    return None


def is_top_bucket(question: str) -> bool:
    """Check if this is the top bucket (≥ X%)."""
    return "≥" in question or ">=" in question.lower()


def group_poly_buckets(poly_markets: list[dict]) -> dict:
    """
    Group Polymarket bucket markets by event.
    Returns dict keyed by event identifier.

    For fed rate end of 2026:
    key = "fed_rate_end_2026"
    value = list of bucket markets sorted by threshold
    """
    groups = {}

    for m in poly_markets:
        q = m.get("question", "")
        q_lower = q.lower()

        # Fed rate end of year buckets
        if ("upper bound" in q_lower and
                "federal funds" in q_lower and
                "end of" in q_lower):
            year_match = re.search(r'\b(202\d)\b', q_lower)
            year = year_match.group(1) if year_match else "unknown"
            key = f"fed_rate_end_{year}"

            if key not in groups:
                groups[key] = []
            groups[key].append(m)

    return groups


def build_synthetic_above(
        bucket_markets: list[dict],
        threshold: float
) -> dict | None:
    """
    Build a synthetic "above X%" market by summing all Polymarket
    buckets with value >= threshold, normalized to account for
    bucket sum != 100%.
    """
    buckets_above = []
    total_prob = 0.0
    total_all_buckets = sum(m.get("yes_prob", 0) for m in bucket_markets)

    for m in bucket_markets:
        q = m.get("question", "")
        bucket_threshold = extract_exact_threshold(q)

        if bucket_threshold is None:
            continue

        if bucket_threshold >= threshold:
            buckets_above.append(m)
            total_prob += m.get("yes_prob", 0)

    if not buckets_above:
        return None

    # Normalize: adjust for fact that buckets sum to ~104% not 100%
    normalized_prob = total_prob / total_all_buckets if total_all_buckets > 0 else total_prob

    bucket_questions = [m.get("question") for m in buckets_above]
    total_volume = sum(float(m.get("volume", 0) or 0) for m in buckets_above)

    return {
        "question": f"Synthetic: Will fed funds rate be above {threshold}% (aggregated from {len(buckets_above)} buckets)",
        "yes_prob": min(normalized_prob, 1.0),
        "volume": total_volume,
        "source": "polymarket_synthetic",
        "is_synthetic": True,
        "bucket_count": len(buckets_above),
        "bucket_questions": bucket_questions,
        "threshold": threshold,
        "end_date": buckets_above[0].get("end_date"),
        "raw_prob": total_prob,
        "normalization_factor": round(total_all_buckets, 4),
    }


def build_all_synthetics(poly_markets: list[dict]) -> list[dict]:
    """
    Build all possible synthetic "above X%" markets from Polymarket buckets.
    Returns list of synthetic markets ready to match against Kalshi.
    """
    groups = group_poly_buckets(poly_markets)
    synthetics = []

    for group_key, bucket_markets in groups.items():
        # Get all unique thresholds from buckets
        thresholds = set()
        for m in bucket_markets:
            t = extract_exact_threshold(m.get("question", ""))
            if t is not None:
                thresholds.add(t)

        # Build synthetic "above X%" for each threshold
        for threshold in sorted(thresholds):
            synthetic = build_synthetic_above(bucket_markets, threshold)
            if synthetic:
                synthetic["group_key"] = group_key
                synthetics.append(synthetic)

    return synthetics


def match_synthetics_to_kalshi(
        synthetic_poly: list[dict],
        kalshi_markets: list[dict],
        min_spread: float = 0.03
) -> list[dict]:
    # Build Kalshi threshold→prob lookup for monotonicity check
    kalshi_fed_dec = {}
    for km in kalshi_markets:
        q = km.get("question", "").lower()
        if "above" in q and "federal funds" in q and "dec" in q:
            thresh = re.findall(r'(\d+\.?\d*)\s*%', km.get("question", ""))
            if thresh:
                kalshi_fed_dec[float(thresh[0])] = km.get("yes_prob", 0)

    # Check monotonicity — flag violations
    sorted_thresholds = sorted(kalshi_fed_dec.keys())
    kalshi_violations = set()
    for i in range(len(sorted_thresholds) - 1):
        lower_t = sorted_thresholds[i]
        higher_t = sorted_thresholds[i + 1]
        if kalshi_fed_dec[higher_t] > kalshi_fed_dec[lower_t]:
            kalshi_violations.add(lower_t)
            kalshi_violations.add(higher_t)
            print(f"  ⚠️  Kalshi monotonicity violation: "
                  f"above {lower_t}% = {round(kalshi_fed_dec[lower_t] * 100, 1)}% "
                  f"but above {higher_t}% = {round(kalshi_fed_dec[higher_t] * 100, 1)}%")

    opportunities = []

    for synthetic in synthetic_poly:
        threshold = synthetic.get("threshold")
        synthetic_prob = synthetic.get("yes_prob", 0)

        for km in kalshi_markets:
            km_q = km.get("question", "").lower()

            if "above" not in km_q:
                continue

            thresh_matches = re.findall(r'(\d+\.?\d*)\s*%', km.get("question", ""))
            if not thresh_matches:
                continue
            kalshi_threshold = float(thresh_matches[0])

            if abs(kalshi_threshold - threshold) > 0.01:
                continue

            km_year_match = re.search(r'\b(202\d)\b', km_q)
            if not km_year_match or km_year_match.group(1) != "2026":
                continue

            kalshi_prob = km.get("yes_prob", 0)
            spread = abs(synthetic_prob - kalshi_prob)

            if spread < min_spread:
                continue

            if synthetic_prob > kalshi_prob:
                strategy = "Buy NO on Polymarket (synthetic) + YES on Kalshi"
            else:
                strategy = "Buy YES on Polymarket (synthetic) + NO on Kalshi"

            # Flag if Kalshi has monotonicity violation at this threshold
            has_violation = threshold in kalshi_violations

            opportunities.append({
                "type": "SYNTHETIC_ARBITRAGE",
                "threshold": threshold,
                "poly_synthetic_prob": round(synthetic_prob * 100, 2),
                "kalshi_prob": round(kalshi_prob * 100, 2),
                "kalshi_question": km.get("question"),
                "spread_pct": round(spread * 100, 2),
                "strategy": strategy,
                "profit_pct": round(spread * 100, 2),
                "bucket_count": synthetic.get("bucket_count"),
                "bucket_questions": synthetic.get("bucket_questions"),
                "kalshi_violation": has_violation,
            })
            break

    return opportunities


if __name__ == "__main__":
    # Test with our actual data
    test_markets = [
        {"question": "Will the upper bound of the target federal funds rate be 3.5% at the end of 2026?",
         "yes_prob": 0.26, "volume": 56941.0},
        {"question": "Will the upper bound of the target federal funds rate be 3.75% at the end of 2026?",
         "yes_prob": 0.2895, "volume": 491911.0},
        {"question": "Will the upper bound of the target federal funds rate be 4.0% at the end of 2026?",
         "yes_prob": 0.114, "volume": 1343476.0},
        {"question": "Will the upper bound of the target federal funds rate be 4.25% at the end of 2026?",
         "yes_prob": 0.0325, "volume": 403673.0},
        {"question": "Will the upper bound of the target federal funds rate be ≥ 4.5% at the end of 2026?",
         "yes_prob": 0.085, "volume": 2388430.0},
    ]

    print("Building synthetics:\n")
    synthetics = build_all_synthetics(test_markets)
    for s in synthetics:
        print(f"  Above {s['threshold']}%: {round(s['yes_prob'] * 100, 2)}% "
              f"(from {s['bucket_count']} buckets)")
        for bq in s['bucket_questions']:
            print(f"    + {bq}")
        print()
