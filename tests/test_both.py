from fetchers.polymarket import fetch_markets as poly_fetch, parse_market as poly_parse
from fetchers.kalshi import fetch_and_parse_series as fetch_kalshi

print("=" * 60)
print("ALL POLYMARKET QUESTIONS")
print("=" * 60)

raw_markets = poly_fetch(limit=100, min_volume=1000)
poly_markets = [poly_parse(m) for m in raw_markets]
print(f"Total: {len(poly_markets)}\n")

for m in poly_markets:
    print(f"  {m['question']}")