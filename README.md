# MarketPulse

### Prediction Market Intelligence Platform

> We find that Polymarket and Kalshi price identical macro events 20–80% apart — and these gaps persist. MarketPulse
> detects these inefficiencies in real time and evaluates which platform is more reliable.

[![Live API](https://img.shields.io/badge/API-Live-brightgreen)](https://your-zerve-deployment-url)
[![Built with Zerve](https://img.shields.io/badge/Built%20with-Zerve-blue)](https://zerve.ai)
[![ZerveHack 2026](https://img.shields.io/badge/ZerveHack-2026-purple)](https://zervehack.devpost.com)
[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://python.org)

---

## The Finding

Prediction markets are supposed to be the most accurate forecasting tools ever built. When two platforms price the same
event, their prices should converge — that's what efficient market theory predicts.

They don't.

**71.4% of matched pairs show gaps exceeding 20%.** The average gap is 35.3%. The largest observed gap is 80.4% — on the
same GDP event, priced simultaneously on both platforms. These gaps are not random noise. They are consistent across
event types, persistent in real time, and traceable to structural differences between the platforms.

---

## Four Findings

### Finding 1 — Cross-platform gaps are massive and persistent

| Metric                 | Value           |
|------------------------|-----------------|
| Matched pairs analyzed | 14              |
| Average gap            | 35.3%           |
| Max gap                | 80.4%           |
| Pairs with gap > 20%   | 10 / 14 (71.4%) |
| Pairs with gap > 40%   | 6 / 14 (42.9%)  |
| Fed rate avg gap       | 35.3%           |
| GDP avg gap            | 35.3%           |

The identical average gap across Fed rate (8 pairs) and GDP (6 pairs) markets confirms this is structural, not
event-specific. In traditional financial markets, a 5% gap between two exchanges would be arbitraged away in seconds.
Here, 80% gaps persist.

Why? Four structural reasons:

- **Regulatory barriers** — Kalshi requires US identity verification; Polymarket is crypto-based and globally accessible
- **Different user bases** — Kalshi attracts institutional/US traders; Polymarket attracts crypto-native global traders
- **Liquidity fragmentation** — arbitrageurs cannot easily move capital between platforms
- **Information asymmetry** — each platform's user base may hold genuinely different beliefs about the same event

### Finding 2 — Synthetic arbitrage: up to 23% spread via bucket aggregation

Polymarket lists individual outcome markets ("Will rate be 3.25%?", "Will rate be 3.5%?", etc.). Kalshi lists a single
binary market ("Will rate be above 3.25%?"). These aren't directly comparable — but by aggregating the Polymarket
buckets, we can reconstruct the equivalent probability.

When we do this, systematic gaps emerge:

| Kalshi threshold  | Polymarket synthetic | Kalshi | Spread |
|-------------------|----------------------|--------|--------|
| Above 2.75% (Dec) | 93.3%                | 69.5%  | 23.8%  |
| Above 3.0% (Dec)  | 88.3%                | 65.5%  | 22.8%  |
| Above 3.25% (Dec) | 84.8%                | 60.0%  | 24.8%  |

Polymarket consistently prices the Fed rate staying higher than Kalshi does — by ~23% on the same threshold. This is not
noise. It's a systematic belief difference between the two platforms' user bases.

### Finding 3 — Kalshi has mathematically impossible pricing (monotonicity violations)

For a set of threshold markets to be logically consistent, a market asking "above X%" must always be priced higher
than "above X+1%". Kalshi violates this.

We detect these intra-platform violations automatically. When they occur, a risk-free arbitrage exists within Kalshi
alone — buy YES on the lower threshold and NO on the higher threshold simultaneously.

### Finding 4 — Polymarket is more accurately calibrated

Using Brier scores on resolved economics markets, with prices taken **7 days before settlement** (not final prices,
which are biased):

| Platform   | Brier Score | Interpretation        | Resolved markets |
|------------|-------------|-----------------------|------------------|
| Polymarket | 0.033       | Excellent calibration | 5                |
| Kalshi     | 0.067       | Good calibration      | 56               |

Lower = better. Polymarket is more accurate on the markets where we have data. Kalshi has more resolved markets — it
runs structured, recurring economics series (KXFED, KXCPI, KXGDP) that generate consistent historical data.

The calibration finding partially explains the pricing gaps: if Polymarket's users are better calibrated, their prices
may simply be more correct — and the gap reflects Kalshi lagging behind.

---

## API Endpoints

Base URL: `https://your-zerve-deployment-url`

### `GET /insights`

Core analytical findings. Start here.

```json
{
  "thesis": "Polymarket and Kalshi price identical macro events 20-80% apart...",
  "summary": {
    "total_matched_pairs": 14,
    "avg_gap_pct": 35.33,
    "max_gap_pct": 80.4,
    "pairs_above_20pct": 10,
    "pct_pairs_above_20": 71.4
  },
  "why_gaps_persist": [
    "..."
  ],
  "implication": "A trader operating on both platforms could capture an average 35.33% edge..."
}
```

### `GET /arbitrage`

Live cross-platform pricing discrepancies across three categories:

- `intra_platform` — Kalshi monotonicity violations (mathematically impossible pricing within a single platform)
- `synthetic` — Polymarket bucket aggregates vs Kalshi binary markets (up to 23% spread)
- `cross_platform` — direct matched-pair divergences on identical events

Query params: `min_spread`, `include_intra`, `include_synthetic`, `include_cross`

### `GET /odds`

All 14 matched pairs with live prices from both platforms, sorted by gap size.

Query params: `topic` (fed_rate, gdp, all)

### `GET /calibration`

Historical accuracy analysis using resolved markets and candlestick price data. Returns Brier scores, calibration
buckets, and platform comparison.

### `GET /health`

Status check.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    DATA LAYER                        │
│  Polymarket Gamma API  ·  Kalshi API  ·  Struct API  │
└──────────────┬──────────────┬───────────────────────┘
               │              │
┌──────────────▼──────────────▼───────────────────────┐
│                    LOGIC LAYER                       │
│  Matcher (Stage 1: structured parser + Stage 2:     │
│  Groq/Llama validation)  ·  Arbitrage Detector  ·   │
│  Bucket Aggregator  ·  Calibration Engine           │
└──────────────┬──────────────┬───────────────────────┘
               │              │
┌──────────────▼──────────────▼───────────────────────┐
│                     API LAYER                        │
│   /insights  /arbitrage  /odds  /calibration         │
└─────────────────────────────────────────────────────┘
```

---

## How the Matching Works

The hardest problem: Polymarket asks "Will fed funds rate be 3.25% at end of 2026?" and Kalshi asks "Will federal funds
rate be above 3.25% following the Dec 9 meeting?" These are the same event, phrased differently, with different question
structures.

We solve this in two stages:

**Stage 1 — Structured parser** extracts 8 fields from each market question:

- `metric` (fed_rate, cpi, gdp)
- `threshold` (numeric value)
- `direction` (above/below)
- `year`, `month`, `quarter`
- `question_type` (binary vs categorical)
- `is_us_market` (rejects non-US Polymarket markets)

Two markets match if they share the same metric + threshold + date combination.

**Stage 2 — Groq/Llama validation** takes Stage 1 candidates and confirms semantic equivalence using
llama-3.1-8b-instant with strict rules to prevent false positives (e.g. rejecting matches where one market is about
nominations and another about policy).

Result: 31 test cases, 100% accuracy. 14 live matched pairs currently active.

---

## How the Bucket Aggregation Works

Polymarket's multi-outcome markets ("rate will be exactly X%") can be aggregated into a synthetic "above X%"
probability — directly comparable to Kalshi's binary threshold markets.

For a threshold T, the synthetic probability = sum of all Polymarket bucket probabilities for outcomes > T.

This is how we find the 23% synthetic arbitrage — we reconstruct what Polymarket is collectively saying about a
threshold and compare it to what Kalshi prices for the same threshold.

---

## How Calibration Works

Standard last-price approaches are biased — market prices converge to 0 or 1 near resolution, making all markets look
well-calibrated. We use **candlestick data from 7 days before settlement** to get a true predicted probability:

- **Polymarket**: Struct API candlestick endpoint (`/v1/polymarket/market/candlestick`) — the only working source for
  Polymarket historical price data after exhaustively testing TheGraph, Dune Analytics, and the CLOB prices-history
  endpoint (all returned empty or required paid access)
- **Kalshi**: Series candlestick endpoint (`/series/{ticker}/markets/{market}/candlesticks`) with daily resolution

Brier score: `(predicted_probability - actual_outcome)²`. Lower = better. Perfect = 0.0. Random = 0.25.

---

## Run Locally

```bash
git clone https://github.com/PABPAT/marketpulse.git
cd marketpulse
pip install -r requirements.txt

# Add API keys to .env
cp .env.example .env

uvicorn main:app --reload --port 8000
```

Required API keys: `GROQ_API_KEY`, `STRUCT_API_KEY`

---

## Project Structure

```
marketpulse/
├── main.py                  # FastAPI — 5 endpoints
├── fetchers/
│   ├── polymarket.py        # Polymarket Gamma API client
│   ├── kalshi.py            # Kalshi API client
│   └── resolved.py          # Historical resolved markets (Struct + Kalshi candlesticks)
├── core/
│   ├── matcher.py           # Two-stage semantic market matching
│   ├── arbitrage.py         # Cross-platform discrepancy detection
│   ├── aggregator.py        # Bucket aggregation + synthetic markets
│   └── calibration.py       # Brier score + calibration bucketing
└── tests/
    └── test_matcher.py      # 31 test cases, 100% accuracy
```

---

## Tech Stack

| Layer             | Technology                                        |
|-------------------|---------------------------------------------------|
| Data ingestion    | Python, Polymarket Gamma API, Kalshi Trade API v2 |
| Historical prices | Struct API (Polymarket), Kalshi candlestick API   |
| Market matching   | Structured parser + Groq llama-3.1-8b-instant     |
| API serving       | FastAPI, deployed on Zerve                        |
| Calibration       | Brier score, probability bucketing                |

---

## Hackathon

Built for **ZerveHack 2026** — a $10,000 data science hackathon.

- **Live Zerve Project:** [View on Zerve](https://your-zerve-project-url)
- **Devpost Submission:** [View on Devpost](https://devpost.com/your-submission)

---

## Contact

**Poorna Abhijith Patel**

- GitHub: [@PABPAT](https://github.com/PABPAT)
- LinkedIn: [linkedin.com/in/poornaabhijithpatel](https://www.linkedin.com/in/poornaabhijithpatel/)

---

*Built with [Zerve AI](https://zerve.ai) · ZerveHack 2026*