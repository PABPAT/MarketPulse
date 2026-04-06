import re
import os
import json
import time
from typing import cast
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

QUARTER_MONTH_MAP = {
    1: (1, 3),  # Q1 = Jan-Mar
    2: (4, 6),  # Q2 = Apr-Jun
    3: (7, 9),  # Q3 = Jul-Sep
    4: (10, 12),  # Q4 = Oct-Dec
}

NON_US = [
    "china", "chinese", "uk ", " uk", "united kingdom", "britain",
    "mexico", "mexican", "argentina", "argentinian", "india",
    "indian", "japan", "japanese", "europe", "eurozone",
    "germany", "france", "canada", "canadian", "brazil",
    "australian", "australia", "russia", "russian",
    "turkey", "turkish", "south korea", "korean"
]


def is_us_market(question: str) -> bool:
    """Check if a market question is about the US."""
    q = question.lower()
    return not any(x in q for x in NON_US)


def parse_market(question: str) -> dict:
    """
    Extract structured fields from a market question.
    All markets assumed US (Kalshi is US-only).
    """
    q = question.lower()

    # --- METRIC ---
    if any(x in q for x in ["federal funds", "fed funds", "funds rate",
                            "rate cut", "rate hike", "fomc", "fed cut",
                            "fed hike", "rate decision"]):
        metric = "fed_rate"
    elif any(x in q for x in ["cpi", "inflation", "consumer price"]):
        metric = "inflation"
    elif any(x in q for x in ["gdp", "economic growth", "real gdp"]):
        metric = "gdp"
    elif "recession" in q:
        metric = "recession"
    else:
        metric = "other"

    # --- YEAR ---
    year_match = re.search(r'\b(202\d)\b', q)
    year = int(year_match.group(1)) if year_match else None

    # --- QUARTER ---
    quarter_match = re.search(r'q([1-4])', q)
    quarter = int(quarter_match.group(1)) if quarter_match else None

    # --- MONTH ---
    # Check for end of year first = December
    # --- MONTH ---
    # "end of year" means different things per metric
    if any(x in q for x in ["end of year", "end of 2026", "end of 2027",
                            "end of 2028", "year end", "end of the year",
                            "by end of"]):
        if metric == "fed_rate":
            month = 12
        elif metric == "gdp":
            quarter = 4
            month = None
        else:
            month = None
    else:
        month_map = {
            "january": 1, "jan": 1,
            "february": 2, "feb": 2,
            "march": 3, "mar": 3,
            "april": 4, "apr": 4,
            "may": 5,
            "june": 6, "jun": 6,
            "july": 7, "jul": 7,
            "august": 8, "aug": 8,
            "september": 9, "sep": 9,
            "october": 10, "oct": 10,
            "november": 11, "nov": 11,
            "december": 12, "dec": 12,
        }
        month = None
        for name, num in month_map.items():
            if name in q:
                month = num
                break

    # --- THRESHOLD ---
    thresh_matches = re.findall(r'(\d+\.?\d*)\s*%', question)
    threshold = float(thresh_matches[0]) if thresh_matches else None

    # --- DIRECTION ---
    if any(x in q for x in ["more than", "above", "exceed", "over",
                            "greater than", "at least"]):
        direction = "above"
    elif any(x in q for x in ["less than", "below", "under"]):
        direction = "below"
    elif "between" in q:
        direction = "between"
    else:
        direction = "unknown"

    # --- QUESTION TYPE (for fed rate) ---
    if metric == "fed_rate":
        if any(x in q for x in ["cut", "cuts", "hike", "hikes"]):
            qtype = "rate_change"
        elif any(x in q for x in ["upper bound", "funds rate be",
                                  "rate be", "rate at", "level"]):
            qtype = "rate_level"
        else:
            qtype = "rate_decision"
    else:
        qtype = metric

    # --- QUARTER MONTH RANGE ---
    month_range = QUARTER_MONTH_MAP.get(quarter) if quarter else None

    return {
        "metric": metric,
        "year": year,
        "quarter": quarter,
        "month": month,
        "month_range": month_range,
        "threshold": threshold,
        "direction": direction,
        "qtype": qtype,
        "original": question,
    }


def are_markets_comparable(
        parsed_kalshi: dict,
        parsed_poly: dict
) -> tuple[bool, str]:
    """
    Stage 1: Structured filter.
    parsed_kalshi = Kalshi market (always US)
    parsed_poly = Polymarket market (check if US)
    """

    # Kalshi is US-only — reject any non-US Polymarket market
    if not is_us_market(parsed_poly["original"]):
        return False, "polymarket market is not US"

    # Must be same metric
    if parsed_kalshi["metric"] != parsed_poly["metric"]:
        return False, (f"different metrics: "
                       f"{parsed_kalshi['metric']} vs {parsed_poly['metric']}")

    # Must be same year if both have one
    if parsed_kalshi["year"] and parsed_poly["year"]:
        if parsed_kalshi["year"] != parsed_poly["year"]:
            return False, (f"different years: "
                           f"{parsed_kalshi['year']} vs {parsed_poly['year']}")

    # Must be same quarter if both have one
    if parsed_kalshi["quarter"] and parsed_poly["quarter"]:
        if parsed_kalshi["quarter"] != parsed_poly["quarter"]:
            return False, "different quarters"

    # If one has quarter and other has specific month
    # check if month falls within quarter range
    if parsed_kalshi["quarter"] and parsed_poly["month"]:
        q_range = QUARTER_MONTH_MAP.get(parsed_kalshi["quarter"])
        if q_range and not (q_range[0] <= parsed_poly["month"] <= q_range[1]):
            return False, (f"month {parsed_poly['month']} not in "
                           f"Q{parsed_kalshi['quarter']} range {q_range}")

    if parsed_poly["quarter"] and parsed_kalshi["month"]:
        q_range = QUARTER_MONTH_MAP.get(parsed_poly["quarter"])
        if q_range and not (q_range[0] <= parsed_kalshi["month"] <= q_range[1]):
            return False, (f"month {parsed_kalshi['month']} not in "
                           f"Q{parsed_poly['quarter']} range {q_range}")

    # Must be same month if both have one
    if parsed_kalshi["month"] and parsed_poly["month"]:
        if parsed_kalshi["month"] != parsed_poly["month"]:
            return False, (f"different months: "
                           f"{parsed_kalshi['month']} vs {parsed_poly['month']}")

    # For fed rate: must be same question type
    if parsed_kalshi["metric"] == "fed_rate":
        if parsed_kalshi["qtype"] != parsed_poly["qtype"]:
            return False, (f"different rate question types: "
                           f"{parsed_kalshi['qtype']} vs {parsed_poly['qtype']}")

    # Threshold check — tighter when thresholds are small
    if parsed_kalshi["threshold"] is not None and parsed_poly["threshold"] is not None:
        diff = abs(parsed_kalshi["threshold"] - parsed_poly["threshold"])
        tolerance = 0.0 if parsed_kalshi["metric"] == "fed_rate" else 0.5
        if diff > tolerance:
            return False, (f"thresholds too different: "
                           f"{parsed_kalshi['threshold']} vs {parsed_poly['threshold']}")

    kalshi_has_time = parsed_kalshi["month"] or parsed_kalshi["quarter"]
    poly_has_time = parsed_poly["month"] or parsed_poly["quarter"]

    if kalshi_has_time and not poly_has_time:
        return False, "kalshi is monthly/quarterly but polymarket is annual"
    if poly_has_time and not kalshi_has_time:
        return False, "polymarket is monthly/quarterly but kalshi is annual"

    return True, "passed structured filter"


def validate_with_groq(question_a: str, question_b: str) -> dict:
    """
    Stage 2: Groq/Llama validation.
    Only called after structured filter passes.
    """
    prompt = f"""You are a prediction market arbitrage analyst.

Your job is to determine if two markets are pricing the SAME 
real-world outcome and could be used for arbitrage.

Market A: {question_a}
Market B: {question_b}

IMPORTANT RULES:
- "rate cut" and "cut 25bps" are the SAME event (both = Fed cutting)
- "increase by X%" and "rise more than X%" are the SAME direction
- "exact rate of 3.75%" and "above 3.75%" are COMPARABLE (one implies the other)
- "end of year" and "December" are the SAME time period
- "CPI" and "inflation" are the SAME metric
- "FOMC" and "Fed meeting" are the SAME event
- "monthly inflation" and "CPI" are the SAME metric
- Small wording differences do NOT make markets incomparable
- A market asking "will X increase by 0.3%" and "will X rise more than 0.2%"
  are comparable because they are close thresholds same direction

Only return false if:
1. Different countries
2. Different years
3. Different months or quarters
4. Thresholds are far apart (more than 1%)
5. Completely different economic events

Respond in JSON only, no other text:
{{"comparable": true or false, "confidence": "high" or "medium" or "low", "reason": "one sentence"}}"""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],  # type: ignore
            max_tokens=150,
            temperature=0.1,
        )
        text = response.choices[0].message.content.strip()
        text = re.sub(r'```json|```', '', text).strip()
        return json.loads(text)
    except Exception as e:
        print(f"  Groq error: {e}")
        return {
            "comparable": True,
            "confidence": "low",
            "reason": f"validation failed: {e}"
        }


def find_matching_pairs(
        polymarket_markets: list[dict],
        kalshi_markets: list[dict],
        confidence_threshold: str = "medium",
        max_groq_calls: int = 50
) -> list[tuple]:
    """
    Two-stage matching pipeline:
    Stage 1 — Structured parser (free, instant)
    Stage 2 — Groq/Llama validation (free API, smart)

    Each market is only matched once (deduplication).
    Kalshi is always first argument (always US).
    Polymarket is second argument (US check applied).
    """

    # --- STAGE 1: Structured filter with deduplication ---
    stage1_candidates = []
    matched_poly_ids = set()
    matched_kalshi_ids = set()

    for km in kalshi_markets:
        parsed_km = parse_market(km.get("question", ""))
        km_id = km.get("id", km.get("question", ""))

        if km_id in matched_kalshi_ids:
            continue

        for pm in polymarket_markets:
            pm_id = pm.get("id", pm.get("question", ""))

            if pm_id in matched_poly_ids:
                continue

            parsed_pm = parse_market(pm.get("question", ""))
            is_comparable, filter_reason = are_markets_comparable(
                parsed_km, parsed_pm
            )

            if is_comparable:
                stage1_candidates.append((pm, km, parsed_pm, parsed_km))
                matched_poly_ids.add(pm_id)
                matched_kalshi_ids.add(km_id)
                break  # one match per kalshi market

    print(f"  Stage 1 (structured filter): {len(stage1_candidates)} candidates")

    if len(stage1_candidates) == 0:
        print("  No candidates passed Stage 1 — check your market data")
        return []

    # Cap Groq calls
    if len(stage1_candidates) > max_groq_calls:
        print(f"  Capping Groq calls at {max_groq_calls} "
              f"(from {len(stage1_candidates)})")
        stage1_candidates = stage1_candidates[:max_groq_calls]

    # --- STAGE 2: Groq validation ---
    matched_pairs = []
    confidence_levels = {"high": 3, "medium": 2, "low": 1}
    min_confidence = confidence_levels.get(confidence_threshold, 2)
    total = len(stage1_candidates)

    for i, (pm, km, parsed_pm, parsed_km) in enumerate(stage1_candidates):
        print(f"  Groq validating {i + 1}/{total}...", end="\r")
        groq_result = validate_with_groq(
            pm.get("question", ""),
            km.get("question", "")
        )
        time.sleep(0.1)

        if groq_result.get("comparable"):
            pair_confidence = confidence_levels.get(
                groq_result.get("confidence", "low"), 1
            )
            if pair_confidence >= min_confidence:
                matched_pairs.append((pm, km, {
                    "topic": parsed_pm["metric"],
                    "confidence": groq_result.get("confidence"),
                    "reason": groq_result.get("reason"),
                }))
                print(f"  ✅ MATCH ({groq_result['confidence']}): "
                      f"{pm['question'][:45]}... "
                      f"↔ {km['question'][:45]}...")
        else:
            print(f"  ❌ REJECTED: {pm['question'][:50]}...")

    print(f"\n  Stage 2 (Groq validated): {len(matched_pairs)} pairs")
    return matched_pairs


if __name__ == "__main__":
    test_pairs = [
        ("Fed rate cut by June 2026?",
         "Will Fed cut 25bps at June 2026 meeting?"),
        ("Will China GDP growth in Q1 2026 be between 3.5 and 4.0%?",
         "Will real GDP increase by more than 1.0% in Q1 2026?"),
        ("Will the upper bound of the target federal funds rate be 1.75% at end of 2026?",
         "Will the upper bound of the federal funds rate be above 0.50% following Mar 17, 2027?"),
        ("Will US inflation exceed 3% in 2026?",
         "Will CPI rise more than 3% in 2026?"),
        ("Will federal funds rate be 3.75% at end of 2026?",
         "Will upper bound be above 3.75% in November 2026?"),
        ("Will federal funds rate be 3.75% at end of 2026?",
         "Will upper bound be above 3.75% in December 2026?"),
    ]

    print("Testing matcher:\n")
    for q_a, q_b in test_pairs:
        pa = parse_market(q_a)
        pb = parse_market(q_b)
        comparable, reason = are_markets_comparable(pb, pa)
        print(f"A: {q_a}")
        print(f"B: {q_b}")
        print(f"  Stage 1: {comparable} — {reason}")
        print()
