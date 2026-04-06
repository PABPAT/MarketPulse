import requests
import os
from dotenv import load_dotenv
import time

load_dotenv()

BASE_URL = os.getenv(
    "KALSHI_PUBLIC_URL",
    "https://api.elections.kalshi.com/trade-api/v2"
)

# Known economic series and their event formats
ECONOMIC_SERIES = {
    "KXFED": {
        "title": "Federal Reserve Rate Decision",
        "event_tickers": [
            "KXFEDDECISION-26JUN",
            "KXFEDDECISION-26JUL",
            "KXFEDDECISION-26SEP",
        ]
    },
    "KXCPI": {
        "title": "CPI Inflation",
        "event_tickers": [
            "KXCPI-26MAR",
            "KXCPI-26APR",
            "KXCPI-26MAY",
        ]
    }
}


def fetch_events(series_ticker: str, limit: int = 10) -> list[dict]:
    """
    Fetch events for a given economic series.

    Args:
        series_ticker: e.g. 'KXFED', 'KXCPI', 'KXGDP'
        limit: Number of events to fetch

    Returns:
        List of event dictionaries
    """
    url = f"{BASE_URL}/events"
    params = {
        "series_ticker": series_ticker,
        "limit": limit
    }
    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    return response.json().get("events", [])


def fetch_markets(event_ticker: str, limit: int = 20) -> list[dict]:
    """
    Fetch markets for a given event ticker.

    Args:
        event_ticker: e.g. 'KXFEDDECISION-26JUN'
        limit: Number of markets to fetch

    Returns:
        List of raw market dictionaries
    """
    url = f"{BASE_URL}/markets"
    params = {
        "event_ticker": event_ticker,
        "limit": limit
    }
    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    return response.json().get("markets", [])


def parse_market(market: dict) -> dict:
    """
    Parse a raw Kalshi market into clean normalized format.

    Kalshi prices are in dollars (0.0 to 1.0).
    Midpoint = (yes_bid + yes_ask) / 2

    Args:
        market: Raw market dictionary from Kalshi API

    Returns:
        Clean dictionary with standardized fields
    """
    def safe_float(val):
        try:
            return float(val) if val is not None else None
        except (ValueError, TypeError):
            return None

    yes_bid = safe_float(market.get("yes_bid_dollars"))
    yes_ask = safe_float(market.get("yes_ask_dollars"))

    # Use midpoint as probability
    yes_prob = None
    if yes_bid is not None and yes_ask is not None:
        yes_prob = round((yes_bid + yes_ask) / 2, 4)
    elif yes_bid is not None:
        yes_prob = yes_bid
    elif yes_ask is not None:
        yes_prob = yes_ask

    no_prob = round(1 - yes_prob, 4) if yes_prob is not None else None

    return {
        "id": market.get("ticker"),
        "question": market.get("title"),
        "yes_prob": yes_prob,
        "no_prob": no_prob,
        "yes_bid": yes_bid,
        "yes_ask": yes_ask,
        "volume": float(market.get("volume_fp", 0) or 0),
        "volume_24hr": float(market.get("volume_24h_fp", 0) or 0),
        "open_interest": float(market.get("open_interest_fp", 0) or 0),
        "end_date": market.get("close_time", "")[:10],
        "event_ticker": market.get("event_ticker"),
        "source": "kalshi"
    }


def fetch_and_parse_series(series_tickers: list[str] = None) -> list[dict]:
    """
    Fetch and parse all markets for given economic series.

    Args:
        series_tickers: List of series e.g. ['KXFED', 'KXCPI']
                       Defaults to all known economic series

    Returns:
        List of clean parsed market dictionaries
    """
    if series_tickers is None:
        series_tickers = list(ECONOMIC_SERIES.keys())

    all_markets = []

    for series_ticker in series_tickers:
        # Get events for this series
        events = fetch_events(series_ticker, limit=5)
        time.sleep(0.5)  # wait 0.5s between series calls

        for event in events:
            event_ticker = event.get("event_ticker")
            if not event_ticker:
                continue

            # Get markets for this event
            raw_markets = fetch_markets(event_ticker)
            time.sleep(0.3)  # wait 0.3s between event calls

            for market in raw_markets:
                parsed = parse_market(market)
                if parsed["yes_prob"] is not None:
                    all_markets.append(parsed)

    return all_markets

if __name__ == "__main__":
    print("Testing Kalshi fetcher...")
    markets = fetch_and_parse_series(["KXFED"])
    print(f"Found {len(markets)} Fed markets")
    for m in markets[:3]:
        print(f"  {m['question']}")
        print(f"  Yes: {m['yes_prob']} | Vol: {m['volume']}")