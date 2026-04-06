import re

from fetchers.polymarket import search_markets
from fetchers.kalshi import fetch_and_parse_series
from core.arbitrage import detect_arbitrage, is_valid_market, check_monotonicity
from core.matcher import find_matching_pairs
from core.aggregator import build_all_synthetics, match_synthetics_to_kalshi

print("=" * 60)
print("MARKETPULSE - ARBITRAGE SCAN")
print("=" * 60)

# --- FETCH POLYMARKET ---
print("\nFetching Polymarket markets...")
poly_markets = []
for query in [
    "fed funds rate above",
    "federal funds rate exceed",
    "fed rate above",
    "CPI above",
    "CPI exceed",
    "inflation above",
    "inflation exceed",
    "GDP above",
    "GDP exceed",
    "recession 2026",
]:
    results = search_markets(query, limit=20)
    poly_markets.extend(results)

# Deduplicate by question
seen = set()
unique_poly = []
for m in poly_markets:
    q = m.get("question", "")
    if q not in seen:
        seen.add(q)
        unique_poly.append(m)

valid_poly = [m for m in unique_poly if is_valid_market(m)]
print(f"Valid Polymarket markets: {len(valid_poly)}")

# --- FETCH KALSHI ---
print("\nFetching Kalshi markets...")
kalshi_markets = fetch_and_parse_series(["KXFED", "KXCPI", "KXGDP"])
valid_kalshi = [m for m in kalshi_markets if is_valid_market(m)]
print(f"Valid Kalshi markets: {len(valid_kalshi)}")

# --- INTRA-PLATFORM MONOTONICITY ---
print("\n--- KALSHI INTRA-PLATFORM OPPORTUNITIES ---")
kalshi_violations = check_monotonicity(valid_kalshi)
print(f"Monotonicity violations found: {len(kalshi_violations)}")
for v in kalshi_violations:
    print(f"\n  [MONOTONICITY VIOLATION] {v['severity'].upper()}")
    print(f"  Lower threshold: {v['market_lower']}")
    print(f"  Higher threshold: {v['market_higher']}")
    print(f"  Lower prob: {v['prob_lower_threshold']}%")
    print(f"  Higher prob: {v['prob_higher_threshold']}%")
    print(f"  Violation spread: {v['violation_spread_pct']}%")
    print(f"  Strategy: Buy YES on lower threshold + NO on higher threshold")

# --- BUILD SYNTHETICS ---
print("\nBuilding synthetic Polymarket markets...")
synthetic_poly = build_all_synthetics(valid_poly)
print(f"Synthetic markets built: {len(synthetic_poly)}")

# --- MATCH SYNTHETICS vs KALSHI ---
print("\nMatching synthetic markets against Kalshi...")
synthetic_opportunities = match_synthetics_to_kalshi(synthetic_poly, valid_kalshi)
synthetic_opportunities.sort(key=lambda x: x["spread_pct"], reverse=True)

print(f"\n--- SYNTHETIC ARBITRAGE OPPORTUNITIES ---")
print(f"Opportunities found: {len(synthetic_opportunities)}")

for opp in synthetic_opportunities:
    violation_flag = " ⚠️  KALSHI MISPRICED" if opp.get("kalshi_violation") else ""
    print(f"\n  [SYNTHETIC] Above {opp['threshold']}%{violation_flag}")
    print(f"  Kalshi:  {opp['kalshi_question']}")
    print(f"  Kalshi prob: {opp['kalshi_prob']}%")
    print(f"  Poly synthetic ({opp['bucket_count']} buckets): {opp['poly_synthetic_prob']}%")
    print(f"  Spread: {opp['spread_pct']}% | Strategy: {opp['strategy']}")
    for bq in opp['bucket_questions']:
        print(f"    Bucket: {bq}")

# --- MATCH MARKETS ---
print("\nMatching markets (Stage 1: structured + Stage 2: Groq)...")
matched_pairs = find_matching_pairs(valid_poly, valid_kalshi)
print(f"\nTotal matched pairs: {len(matched_pairs)}")

# --- DETECT ARBITRAGE ---
print("\n--- CROSS-PLATFORM OPPORTUNITIES ---")
opportunities = []
for pm, km, match_info in matched_pairs:
    result = detect_arbitrage(pm, km, threshold=0.03)
    if result:
        result["topic"] = match_info["topic"]
        result["match_reason"] = match_info["reason"]
        result["confidence"] = match_info["confidence"]
        opportunities.append(result)

opportunities.sort(key=lambda x: x["spread_pct"], reverse=True)
print(f"Opportunities found: {len(opportunities)}")

for opp in opportunities[:10]:
    print(f"\n  [{opp['topic'].upper()}] [{opp['opportunity_type'].upper()}]")
    print(f"  Polymarket: {opp['market_a_question']}")
    print(f"  Kalshi:     {opp['market_b_question']}")
    print(f"  Poly:  {opp['market_a_prob']}%")
    print(f"  Kalshi:{opp['market_b_prob']}%")
    print(f"  Spread:{opp['spread_pct']}% | {opp['severity'].upper()}")
    if opp.get("profit_pct") is not None:
        print(f"  Profit: {opp['profit_pct']}% | Strategy: {opp.get('strategy')}")