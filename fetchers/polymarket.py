import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

POLYMARKET_BASE_URL = os.getenv(
    "POLYMARKET_BASE_URL",
    "https://gamma-api.polymarket.com"
)


def fetch_markets(limit: int = 100, min_volume: float = 1000) -> list[dict]:
    """
    Fetch active markets from Polymarket Gamma API.

    Args:
        limit: Number of markets to fetch
        min_volume: Minimum trading volume in USD

    Returns:
        List of raw market dictionaries
    """
    url = f"{POLYMARKET_BASE_URL}/markets"
    params = {
        "active": "true",
        "closed": "false",
        "limit": limit,
        "order": "volume",
        "ascending": "false"
    }

    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    markets = response.json()

    return [
        m for m in markets
        if float(m.get("volume", 0) or 0) >= min_volume
    ]


def parse_market(market: dict) -> dict:
    """
    Parse a raw Polymarket market into clean normalized format.

    Args:
        market: Raw market dictionary from Gamma API

    Returns:
        Clean dictionary with standardized fields
    """
    prices_raw = market.get("outcomePrices", "[]")
    outcomes_raw = market.get("outcomes", "[]")

    prices = json.loads(prices_raw) if isinstance(prices_raw, str) else prices_raw
    outcomes = json.loads(outcomes_raw) if isinstance(outcomes_raw, str) else outcomes_raw

    label_map = {
        str(lbl).strip().lower(): float(p)
        for lbl, p in zip(outcomes, prices)
    }

    yes_prob = label_map.get("yes")
    no_prob = label_map.get("no")

    return {
        "id": market.get("id"),
        "question": market.get("question"),
        "yes_prob": yes_prob,
        "no_prob": no_prob,
        "volume": float(market.get("volume", 0) or 0),
        "volume_24hr": float(market.get("volume24hr", 0) or 0),
        "liquidity": float(market.get("liquidity", 0) or 0),
        "end_date": market.get("endDateIso"),
        "source": "polymarket"
    }


def search_markets(query: str, limit: int = 10) -> list[dict]:
    """
    Search Polymarket markets by keyword using public search.

    Args:
        query: Search term e.g. "fed rate", "inflation", "GDP"
        limit: Max results to return

    Returns:
        List of parsed market dictionaries
    """
    url = f"{POLYMARKET_BASE_URL}/public-search"
    params = {"q": query, "limit": limit}

    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()

    data = response.json()
    events = data.get("events", [])

    markets = []
    for event in events:
        for market in event.get("markets", []):
            parsed = parse_market(market)
            parsed["event_title"] = event.get("title")
            parsed["event_volume"] = float(
                event.get("volume", 0) or 0
            )
            markets.append(parsed)

    return markets


def fetch_and_parse(
    limit: int = 100,
    min_volume: float = 1000
) -> list[dict]:
    """
    Fetch and parse markets in one call.

    Returns:
        List of clean parsed market dictionaries
    """
    raw = fetch_markets(limit=limit, min_volume=min_volume)
    return [parse_market(m) for m in raw]