import re
from typing import Optional


def extract_year(question: str) -> int | None:
    """Extract the year from a market question."""
    match = re.search(r'\b(202[0-9])\b', question)
    return int(match.group(1)) if match else None


def extract_threshold(question: str) -> float:
    """
    Extract numeric threshold from a market question.
    Example: "Will rate be above 3.25%?" -> 3.25
    """
    matches = re.findall(r'(\d+\.?\d*)\s*%', question)
    if matches:
        return float(matches[0])
    return 0.0


def detect_arbitrage(
        market_a: dict,
        market_b: dict,
        threshold: float = 0.05
) -> dict | None:
    prob_a = market_a.get("yes_prob", 0)
    prob_b = market_b.get("yes_prob", 0)

    if prob_a is None or prob_b is None:
        return None

    q_a = market_a.get("question", "").lower()
    q_b = market_b.get("question", "").lower()

    # --- DIRECTION DETECTION ---
    a_above = any(x in q_a for x in ["more than", "above", "exceed", "greater than"])
    a_below = any(x in q_a for x in ["less than", "below", "under"])
    b_above = any(x in q_b for x in ["more than", "above", "exceed", "greater than"])
    b_below = any(x in q_b for x in ["less than", "below", "under"])

    # Classify opportunity type based on direction
    if (a_above and b_above) or (a_below and b_below):
        # Same direction on same threshold = true arbitrage candidate
        opportunity_type = "true_arbitrage"
    elif (a_above and b_below) or (a_below and b_above):
        # Opposite directions = consistency violation
        opportunity_type = "consistency_violation"
    else:
        # One or both are exact = price divergence
        opportunity_type = "price_divergence"

    # --- SPREAD ---
    spread = abs(prob_a - prob_b)
    if spread < threshold:
        return None

    # --- COST CALCULATION (only meaningful for true arbitrage) ---
    no_prob_a = 1.0 - prob_a
    no_prob_b = 1.0 - prob_b
    cost_yes_a_no_b = prob_a + no_prob_b
    cost_yes_b_no_a = prob_b + no_prob_a
    best_cost = min(cost_yes_a_no_b, cost_yes_b_no_a)
    profit_pct = round((1.0 - best_cost) * 100, 2) if opportunity_type == "true_arbitrage" else None

    # For true arbitrage, must be profitable (best_cost < 1.0)
    if opportunity_type == "true_arbitrage" and best_cost >= 1.0:
        # Same direction but not profitable — just price divergence
        opportunity_type = "price_divergence"
        profit_pct = None

    if opportunity_type == "true_arbitrage":
        strategy = (
            f"Buy YES on {market_a.get('source')} + NO on {market_b.get('source')}"
            if cost_yes_a_no_b < cost_yes_b_no_a
            else f"Buy YES on {market_b.get('source')} + NO on {market_a.get('source')}"
        )
        severity = "high" if profit_pct >= 5 else "medium" if profit_pct >= 2 else "low"
    else:
        strategy = None
        severity = "high" if spread >= 0.20 else "medium" if spread >= 0.10 else "low"

    return {
        "market_a_question": market_a.get("question"),
        "market_b_question": market_b.get("question"),
        "market_a_prob": round(prob_a * 100, 2),
        "market_b_prob": round(prob_b * 100, 2),
        "market_a_source": market_a.get("source"),
        "market_b_source": market_b.get("source"),
        "spread_pct": round(spread * 100, 2),
        "severity": severity,
        "opportunity_type": opportunity_type,
        "profit_pct": profit_pct,
        "strategy": strategy,
    }


def check_monotonicity(markets: list[dict]) -> list[dict]:
    """
    Check monotonicity violations within the same event group.
    Only compares markets with same metric, same meeting/month, same year.
    """
    from collections import defaultdict
    import re

    violations = []

    # Group markets by event key
    groups = defaultdict(list)

    for m in markets:
        q = m.get("question", "").lower()

        # Fed rate — group by meeting date
        if "federal funds" in q and "above" in q:
            meeting_match = re.search(
                r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d+,\s+\d{4}',
                q
            )
            if meeting_match:
                key = f"fed_rate_{meeting_match.group(0)}"
                groups[key].append(m)

        # CPI — group by month and year
        elif "cpi" in q or "inflation" in q:
            month_year = re.search(
                r'(january|february|march|april|may|june|july|august|'
                r'september|october|november|december)\s+\d{4}',
                q
            )
            if month_year:
                key = f"cpi_{month_year.group(0)}"
                groups[key].append(m)

        # GDP — group by quarter and year
        elif "gdp" in q or "real gdp" in q:
            quarter_year = re.search(r'q([1-4])\s+\d{4}', q)
            if quarter_year:
                key = f"gdp_{quarter_year.group(0)}"
                groups[key].append(m)

    # Check monotonicity within each group
    for group_key, group_markets in groups.items():
        sorted_markets = sorted(
            group_markets,
            key=lambda m: extract_threshold(m.get("question", ""))
        )

        for i in range(len(sorted_markets) - 1):
            lower = sorted_markets[i]
            higher = sorted_markets[i + 1]

            prob_lower = lower.get("yes_prob")
            prob_higher = higher.get("yes_prob")

            if prob_lower is None or prob_higher is None:
                continue

            if prob_higher > prob_lower:
                spread = round((prob_higher - prob_lower) * 100, 2)
                violations.append({
                    "type": "monotonicity_violation",
                    "group": group_key,
                    "market_lower": lower.get("question"),
                    "market_higher": higher.get("question"),
                    "prob_lower_threshold": round(prob_lower * 100, 2),
                    "prob_higher_threshold": round(prob_higher * 100, 2),
                    "violation_spread_pct": spread,
                    "source": lower.get("source"),
                    "severity": "high" if spread > 10 else "medium"
                })

    return violations


def is_valid_market(market: dict) -> bool:
    """
    Filter out resolved, stale, or unusable markets.
    """
    prob = market.get("yes_prob")

    if prob is None:
        return False

    if prob == 0.0 or prob == 1.0:
        return False

    if float(market.get("volume", 0) or 0) < 100:
        return False

    end_date = market.get("end_date") or ""
    if end_date and end_date < "2026-04-01":
        return False

    return True
