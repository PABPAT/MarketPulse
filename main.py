# main.py
# MarketPulse FastAPI — three endpoints
# /arbitrage  → all opportunity types
# /odds       → raw matched market pairs
# /health     → status check

import re
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from fetchers.polymarket import search_markets
from fetchers.kalshi import fetch_and_parse_series
from core.arbitrage import detect_arbitrage, is_valid_market, check_monotonicity
from core.matcher import find_matching_pairs
from core.aggregator import build_all_synthetics, match_synthetics_to_kalshi
from fetchers.resolved import fetch_resolved_polymarket_struct, fetch_resolved_kalshi
from core.calibration import platform_calibration_report

app = FastAPI(
    title="MarketPulse",
    description="Cross-platform prediction market arbitrage intelligence",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def fetch_markets():
    """Fetch and filter markets from both platforms."""

    # Polymarket
    poly_markets = []
    for query in [
        "fed funds rate above", "federal funds rate exceed",
        "fed rate above", "CPI above", "CPI exceed",
        "inflation above", "inflation exceed",
        "GDP above", "GDP exceed", "recession 2026",
    ]:
        results = search_markets(query, limit=20)
        poly_markets.extend(results)

    # Deduplicate
    seen = set()
    unique_poly = []
    for m in poly_markets:
        q = m.get("question", "")
        if q not in seen:
            seen.add(q)
            unique_poly.append(m)

    valid_poly = [m for m in unique_poly if is_valid_market(m)]

    # Kalshi
    kalshi_markets = fetch_and_parse_series(["KXFED", "KXCPI", "KXGDP"])
    valid_kalshi = [m for m in kalshi_markets if is_valid_market(m)]

    return valid_poly, valid_kalshi


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "MarketPulse",
        "version": "1.0.0"
    }


@app.get("/arbitrage")
def get_arbitrage(
        min_spread: float = Query(default=0.03, description="Minimum spread to report"),
        include_intra: bool = Query(default=True, description="Include intra-platform violations"),
        include_synthetic: bool = Query(default=True, description="Include synthetic cross-platform"),
        include_cross: bool = Query(default=True, description="Include cross-platform divergence"),
):
    """
    Find all arbitrage opportunities across Polymarket and Kalshi.

    Returns three categories:
    - intra_platform: Kalshi markets violating monotonicity (mathematically impossible pricing)
    - synthetic: Polymarket bucket aggregates vs Kalshi binary markets
    - cross_platform: Direct cross-platform price divergences
    """
    valid_poly, valid_kalshi = fetch_markets()

    response = {
        "summary": {},
        "intra_platform": [],
        "synthetic": [],
        "cross_platform": [],
    }

    # --- INTRA-PLATFORM ---
    if include_intra:
        violations = check_monotonicity(valid_kalshi)
        response["intra_platform"] = [
            {
                "type": "monotonicity_violation",
                "severity": v["severity"],
                "market_lower": v["market_lower"],
                "market_higher": v["market_higher"],
                "prob_lower": v["prob_lower_threshold"],
                "prob_higher": v["prob_higher_threshold"],
                "spread_pct": v["violation_spread_pct"],
                "strategy": "Buy YES on lower threshold + NO on higher threshold",
                "source": "kalshi",
            }
            for v in violations
            if v["violation_spread_pct"] >= min_spread * 100
        ]

    # --- SYNTHETIC ---
    if include_synthetic:
        synthetic_poly = build_all_synthetics(valid_poly)
        synthetic_opps = match_synthetics_to_kalshi(
            synthetic_poly, valid_kalshi, min_spread=min_spread
        )
        response["synthetic"] = [
            {
                "type": "synthetic_arbitrage",
                "threshold": opp["threshold"],
                "poly_synthetic_prob": opp["poly_synthetic_prob"],
                "kalshi_prob": opp["kalshi_prob"],
                "kalshi_question": opp["kalshi_question"],
                "spread_pct": opp["spread_pct"],
                "strategy": opp["strategy"],
                "bucket_count": opp["bucket_count"],
                "bucket_questions": opp["bucket_questions"],
                "kalshi_mispriced": opp.get("kalshi_violation", False),
            }
            for opp in synthetic_opps
        ]

    # --- CROSS-PLATFORM ---
    if include_cross:
        matched_pairs = find_matching_pairs(valid_poly, valid_kalshi)
        cross_opps = []
        for pm, km, match_info in matched_pairs:
            result = detect_arbitrage(pm, km, threshold=min_spread)
            if result:
                cross_opps.append({
                    "type": result["opportunity_type"],
                    "topic": match_info["topic"],
                    "polymarket_question": result["market_a_question"],
                    "kalshi_question": result["market_b_question"],
                    "poly_prob": result["market_a_prob"],
                    "kalshi_prob": result["market_b_prob"],
                    "spread_pct": result["spread_pct"],
                    "severity": result["severity"],
                    "strategy": result.get("strategy"),
                    "profit_pct": result.get("profit_pct"),
                    "confidence": match_info["confidence"],
                })
        cross_opps.sort(key=lambda x: x["spread_pct"], reverse=True)
        response["cross_platform"] = cross_opps

    # --- SUMMARY ---
    response["summary"] = {
        "intra_platform_count": len(response["intra_platform"]),
        "synthetic_count": len(response["synthetic"]),
        "cross_platform_count": len(response["cross_platform"]),
        "total": (
                len(response["intra_platform"]) +
                len(response["synthetic"]) +
                len(response["cross_platform"])
        ),
        "polymarket_markets_scanned": len(valid_poly),
        "kalshi_markets_scanned": len(valid_kalshi),
    }

    return response


@app.get("/odds")
def get_odds(
        topic: str = Query(default="all", description="Filter by topic: fed_rate, inflation, gdp, recession, all"),
):
    """
    Return raw matched market pairs with prices from both platforms.
    Useful for comparing how each platform prices the same event.
    """
    valid_poly, valid_kalshi = fetch_markets()
    matched_pairs = find_matching_pairs(valid_poly, valid_kalshi)

    pairs = []
    for pm, km, match_info in matched_pairs:
        if topic != "all" and match_info["topic"] != topic:
            continue
        pairs.append({
            "topic": match_info["topic"],
            "confidence": match_info["confidence"],
            "polymarket": {
                "question": pm.get("question"),
                "yes_prob": round(pm.get("yes_prob", 0) * 100, 2),
                "volume": pm.get("volume"),
                "end_date": pm.get("end_date"),
            },
            "kalshi": {
                "question": km.get("question"),
                "yes_prob": round(km.get("yes_prob", 0) * 100, 2),
                "volume": km.get("volume"),
                "end_date": km.get("end_date"),
            },
            "spread_pct": round(
                abs(pm.get("yes_prob", 0) - km.get("yes_prob", 0)) * 100, 2
            ),
        })

    pairs.sort(key=lambda x: x["spread_pct"], reverse=True)

    return {
        "count": len(pairs),
        "topic_filter": topic,
        "pairs": pairs,
    }


@app.get("/calibration")
def get_calibration():
    """
    Calibration analysis for Polymarket and Kalshi.
    Shows Brier scores and calibration curves using resolved markets.
    Brier score: lower is better. Perfect = 0.0, Random = 0.25
    """

    print("Fetching resolved Polymarket markets...")
    poly_resolved = fetch_resolved_polymarket_struct(limit_events=200)

    print("Fetching resolved Kalshi markets...")
    kalshi_resolved = fetch_resolved_kalshi()

    poly_report = platform_calibration_report(poly_resolved, "polymarket")
    kalshi_report = platform_calibration_report(kalshi_resolved, "kalshi")

    return {
        "summary": {
            "polymarket": {
                "market_count": poly_report["market_count"],
                "brier_score": poly_report["brier_score"],
                "mean_calibration_error": poly_report["mean_calibration_error"],
                "interpretation": poly_report["interpretation"],
            },
            "kalshi": {
                "market_count": kalshi_report["market_count"],
                "brier_score": kalshi_report["brier_score"],
                "mean_calibration_error": kalshi_report["mean_calibration_error"],
                "interpretation": kalshi_report["interpretation"],
            },
            "winner": (
                "kalshi"
                if (kalshi_report["brier_score"] or 1) < (poly_report["brier_score"] or 1)
                else "polymarket"
            ),
            "note": (
                "Lower Brier score = better calibration. "
                "Polymarket data sourced via Struct API. "
                "Kalshi data sourced via official Kalshi API."
            )
        },
        "polymarket": poly_report,
        "kalshi": kalshi_report,
    }


@app.get("/insights")
def get_insights():
    """
    Core analytical findings from MarketPulse.

    Thesis: Polymarket and Kalshi price identical macro events 20-80% apart,
    and these gaps persist — revealing structural inefficiencies that
    traditional arbitrage theory cannot explain.
    """
    valid_poly, valid_kalshi = fetch_markets()
    matched_pairs = find_matching_pairs(valid_poly, valid_kalshi)

    # Compute all pair gaps
    pairs = []
    for pm, km, match_info in matched_pairs:
        gap = round(abs(pm.get("yes_prob", 0) - km.get("yes_prob", 0)) * 100, 2)
        pairs.append({
            "topic": match_info["topic"],
            "polymarket_question": pm.get("question"),
            "kalshi_question": km.get("question"),
            "poly_prob": round(pm.get("yes_prob", 0) * 100, 2),
            "kalshi_prob": round(km.get("yes_prob", 0) * 100, 2),
            "gap_pct": gap,
        })

    pairs.sort(key=lambda x: x["gap_pct"], reverse=True)

    total = len(pairs)
    gaps = [p["gap_pct"] for p in pairs]
    avg_gap = round(sum(gaps) / total, 2) if total else 0
    max_gap = max(gaps) if gaps else 0
    above_20 = [p for p in pairs if p["gap_pct"] > 20]
    above_40 = [p for p in pairs if p["gap_pct"] > 40]

    # Topic breakdown
    by_topic = {}
    for p in pairs:
        t = p["topic"]
        if t not in by_topic:
            by_topic[t] = []
        by_topic[t].append(p["gap_pct"])

    topic_summary = {
        topic: {
            "count": len(vals),
            "avg_gap_pct": round(sum(vals) / len(vals), 2),
            "max_gap_pct": round(max(vals), 2),
        }
        for topic, vals in by_topic.items()
    }

    return {
        "thesis": (
            "Polymarket and Kalshi price identical macro events 20-80% apart. "
            "These gaps persist in real time, revealing structural inefficiencies "
            "caused by different user bases, regulatory constraints, and "
            "information asymmetries between platforms."
        ),
        "summary": {
            "total_matched_pairs": total,
            "avg_gap_pct": avg_gap,
            "max_gap_pct": max_gap,
            "pairs_above_20pct": len(above_20),
            "pairs_above_40pct": len(above_40),
            "pct_pairs_above_20": round(len(above_20) / total * 100, 1) if total else 0,
        },
        "by_topic": topic_summary,
        "why_gaps_persist": [
            "Regulatory barriers: Kalshi requires US identity verification; Polymarket is crypto-based and globally accessible",
            "Different user bases: Kalshi attracts institutional/US traders; Polymarket attracts crypto-native global traders",
            "Liquidity fragmentation: arbitrageurs cannot easily move capital between platforms",
            "Information asymmetry: each platform's user base may have different information or beliefs",
        ],
        "implication": (
            "A trader who could operate on both platforms simultaneously could "
            f"capture an average {avg_gap}% edge, with peaks up to {max_gap}%. "
            "The persistence of these gaps is itself evidence of market inefficiency."
        ),
        "pairs": pairs,
    }
