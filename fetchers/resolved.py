# fetchers/resolved.py
# Fetch resolved/settled markets from Polymarket (via Struct API) and Kalshi
# Used for calibration analysis

import requests
import time
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

POLYMARKET_BASE = os.getenv("POLYMARKET_BASE_URL", "https://gamma-api.polymarket.com")
KALSHI_BASE = os.getenv("KALSHI_PUBLIC_URL", "https://api.elections.kalshi.com/trade-api/v2")
STRUCT_BASE = "https://api.struct.to/v1/polymarket"


def fetch_resolved_polymarket_struct(limit_events: int = 200) -> list[dict]:
    """
    Fetch resolved Polymarket economics markets via Struct API.
    Uses candlestick data to get predicted probability before resolution.
    """
    STRUCT_API_KEY = os.getenv("STRUCT_API_KEY")
    headers = {"Authorization": f"Bearer {STRUCT_API_KEY}"}
    econ_tags = "fed-rates,economic-policy,fomc,inflation,economy"

    # Step 1 — Get economics events with pagination
    all_events = []
    pagination_key = None

    while True:
        params = {
            "tags": econ_tags,
            "limit": 100,
            "include_markets": "true",
        }
        if pagination_key:
            params["pagination_key"] = pagination_key

        response = requests.get(
            f"{STRUCT_BASE}/events",
            headers=headers,
            params=params,
            timeout=15
        )
        data = response.json()
        events = data.get("data", []) or []
        all_events.extend(events)

        pagination = data.get("pagination", {})
        if not pagination.get("has_more"):
            break
        pagination_key = pagination.get("pagination_key")
        time.sleep(0.3)

        if len(all_events) >= limit_events:
            break

    print(f"  Economics events fetched: {len(all_events)}")

    # Step 2 — Find resolved markets
    resolved = []

    for event in all_events:
        markets = event.get("markets", [])

        for m in markets:
            # Only resolved markets
            if m.get("status") != "Resolved":
                continue

            condition_id = m.get("condition_id")
            if not condition_id:
                continue

            # Determine outcome from final prices
            outcomes = m.get("outcomes", [])
            if len(outcomes) < 2:
                continue

            yes_price = outcomes[0].get("price", 0)
            no_price = outcomes[1].get("price", 0)

            if float(yes_price) == 1.0:
                outcome = 1
            elif float(no_price) == 1.0:
                outcome = 0
            else:
                continue

            # Step 3 — Get candlestick data for predicted probability
            time.sleep(0.2)
            candle_response = requests.get(
                f"{STRUCT_BASE}/market/candlestick",
                headers=headers,
                params={
                    "condition_id": condition_id,
                    "resolution": "D",
                    "count_back": 30,
                },
                timeout=15
            )
            candle_data = candle_response.json()
            candles = candle_data.get("data", []) or []

            if not candles:
                continue

            # Use second to last candle — last may already be at resolution price
            if len(candles) >= 2:
                predicted_prob = candles[-2].get("c")
            else:
                predicted_prob = candles[-1].get("c")

            if predicted_prob is None:
                continue

            # Skip if already snapped to 0 or 1
            if float(predicted_prob) in [0.0, 1.0]:
                continue

            resolved.append({
                "question": m.get("question"),
                "source": "polymarket",
                "predicted_prob": float(predicted_prob),
                "outcome": outcome,
                "volume": float(m.get("volume_24hr", 0) or 0),
                "end_date": event.get("closed_time"),
                "condition_id": condition_id,
                "event_title": event.get("title"),
            })

    return resolved


def fetch_resolved_kalshi(series_tickers: list[str] = None) -> list[dict]:
    """
    Fetch settled Kalshi markets with price 7 days before settlement.
    Uses candlestick endpoint for accurate predicted probability.
    """
    import datetime

    if series_tickers is None:
        series_tickers = ["KXFED", "KXCPI", "KXGDP"]

    resolved = []

    for ticker in series_tickers:
        try:
            # Step 1 — get settled events
            response = requests.get(
                f"{KALSHI_BASE}/events",
                params={
                    "series_ticker": ticker,
                    "status": "settled",
                    "limit": 100,
                },
                timeout=10
            )
            data = response.json()
            events = data.get("events", [])
            print(f"  {ticker}: {len(events)} settled events")

            for event in events:
                event_ticker = event.get("event_ticker")
                if not event_ticker:
                    continue

                # Step 2 — fetch markets for this event
                time.sleep(0.2)
                markets_response = requests.get(
                    f"{KALSHI_BASE}/markets",
                    params={
                        "event_ticker": event_ticker,
                        "limit": 100,
                    },
                    timeout=10
                )
                markets_data = markets_response.json()
                markets = markets_data.get("markets", [])

                for m in markets:
                    result = m.get("result", "")
                    status = m.get("status", "")

                    if status not in ["finalized", "settled"]:
                        continue
                    if result not in ["yes", "no"]:
                        continue

                    outcome = 1 if result == "yes" else 0
                    market_ticker = m.get("ticker")
                    settlement_ts = m.get("settlement_ts")

                    if not market_ticker or not settlement_ts:
                        continue

                    # Parse settlement timestamp
                    try:
                        settlement_dt = datetime.datetime.fromisoformat(
                            settlement_ts.replace("Z", "+00:00")
                        )
                        # Get price 7 days before settlement
                        end_dt = settlement_dt - datetime.timedelta(days=1)
                        start_dt = settlement_dt - datetime.timedelta(days=14)
                        start_ts = int(start_dt.timestamp())
                        end_ts = int(end_dt.timestamp())
                    except Exception:
                        continue

                    # Step 3 — get candlestick data
                    time.sleep(0.2)
                    candle_response = requests.get(
                        f"{KALSHI_BASE}/series/{ticker}/markets/{market_ticker}/candlesticks",
                        params={
                            "period_interval": 1440,
                            "start_ts": start_ts,
                            "end_ts": end_ts,
                        },
                        timeout=10
                    )
                    candle_data = candle_response.json()
                    candles = candle_data.get("candlesticks", [])

                    if not candles:
                        # Fall back to last_price_dollars
                        last_price = m.get("last_price_dollars")
                        if last_price is None:
                            continue
                        try:
                            predicted_prob = float(last_price)
                        except (ValueError, TypeError):
                            continue
                    else:
                        # Use price 7 days before settlement
                        # Take the candle closest to 7 days before
                        target_dt = settlement_dt - datetime.timedelta(days=7)
                        target_ts = int(target_dt.timestamp())

                        closest = min(
                            candles,
                            key=lambda c: abs(c.get("end_period_ts", 0) - target_ts)
                        )
                        price = closest.get("price", {})
                        close = price.get("close_dollars")

                        if close is None:
                            # Use midpoint from bid/ask
                            yes_bid = closest.get("yes_bid", {})
                            yes_ask = closest.get("yes_ask", {})
                            bid = yes_bid.get("close_dollars")
                            ask = yes_ask.get("close_dollars")
                            if bid and ask:
                                predicted_prob = (float(bid) + float(ask)) / 2
                            else:
                                continue
                        else:
                            predicted_prob = float(close)

                    # Skip if already snapped to 0 or 1
                    if predicted_prob in [0.0, 1.0]:
                        continue

                    resolved.append({
                        "question": m.get("title"),
                        "source": "kalshi",
                        "predicted_prob": round(predicted_prob, 4),
                        "outcome": outcome,
                        "volume": float(m.get("volume_fp", 0) or 0),
                        "end_date": settlement_ts,
                        "series": ticker,
                        "ticker": market_ticker,
                        "settlement_ts": settlement_ts,
                    })

            time.sleep(0.3)

        except Exception as e:
            print(f"  Kalshi resolved fetch error for {ticker}: {e}")

    return resolved


if __name__ == "__main__":
    print("=== PRICE DIVERGENCE INSIGHT ===")
    import datetime

    STRUCT_API_KEY = os.getenv("STRUCT_API_KEY")
    struct_headers = {"Authorization": f"Bearer {STRUCT_API_KEY}"}

    # Date range — 30 days before January 28 settlement
    start = int(datetime.datetime(2025, 12, 28).timestamp())
    end = int(datetime.datetime(2026, 1, 29).timestamp())

    # Polymarket — Fed rate cut by January 2026 meeting (NO = rate held)
    print("--- Polymarket: Fed rate cut by January 2026 ---")
    response = requests.get(
        f"{STRUCT_BASE}/market/candlestick",
        headers=struct_headers,
        params={
            "condition_id": "0xc8929e80e74ae959b3ed9b9e1c5e0903ad38e02e1339462e3acf8b49bbca35a9",
            "resolution": "D",
            "count_back": 30,
        },
        timeout=15
    )
    poly_candles = response.json().get("data", []) or []
    print(f"  Candles: {len(poly_candles)}")
    for c in poly_candles[-10:]:
        ts = datetime.datetime.fromtimestamp(c.get("t", 0) / 1000)
        print(f"  {ts.date()} | yes_prob={c.get('c')}")

    print()

    # Kalshi — KXFED-26JAN-T3.50 (above 3.50% = rate held at 4.25-4.50% = YES)
    print("--- Kalshi: Fed rate above 3.50% after Jan 2026 ---")
    response = requests.get(
        f"{KALSHI_BASE}/series/KXFED/markets/KXFED-26JAN-T3.50/candlesticks",
        params={
            "period_interval": 1440,
            "start_ts": start,
            "end_ts": end,
        },
        timeout=10
    )
    kalshi_candles = response.json().get("candlesticks", []) or []
    print(f"  Candles: {len(kalshi_candles)}")
    for c in kalshi_candles[-10:]:
        ts = datetime.datetime.fromtimestamp(c.get("end_period_ts", 0))
        price = c.get("price", {}).get("close_dollars")
        print(f"  {ts.date()} | yes_prob={price}")