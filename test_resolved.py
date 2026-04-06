# test_resolved.py
import requests

# --- TEST 1: Polymarket resolved markets ---
print("=== POLYMARKET RESOLVED MARKETS ===")
response = requests.get(
    "https://gamma-api.polymarket.com/markets",
    params={
        "closed": "true",
        "limit": 5,
        "order": "volume",
        "ascending": "false",
    }
)
markets = response.json()
for m in markets[:3]:
    print(f"  Question: {m.get('question')}")
    print(f"  Closed: {m.get('closed')}")
    print(f"  Resolved: {m.get('resolved')}")
    print(f"  Resolution: {m.get('resolutionSource')}")
    print(f"  Winner: {m.get('winner')}")
    print(f"  End date: {m.get('endDate')}")
    print(f"  Keys: {list(m.keys())}")
    print()

# --- TEST 2: Kalshi resolved markets ---
print("=== KALSHI RESOLVED MARKETS ===")
response = requests.get(
    "https://api.elections.kalshi.com/trade-api/v2/events",
    params={
        "series_ticker": "KXFED",
        "status": "finalized",
        "limit": 5,
    }
)
data = response.json()
events = data.get("events", [])
for e in events[:3]:
    print(f"  Event: {e.get('title')}")
    print(f"  Status: {e.get('status')}")
    print(f"  Keys: {list(e.keys())}")
    # Check markets within event
    markets = e.get("markets", [])
    for km in markets[:2]:
        print(f"    Market: {km.get('title')}")
        print(f"    Result: {km.get('result')}")
        print(f"    Yes bid: {km.get('yes_bid')}")
        print(f"    Keys: {list(km.keys())}")
    print()