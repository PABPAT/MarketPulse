# MarketPulse 📊

### Prediction Market Intelligence Platform

> Real-time arbitrage detection and calibration analysis across Polymarket & Kalshi — served as a live REST API with an
> interactive dashboard.

[![Live API](https://img.shields.io/badge/API-Live-brightgreen)](https://your-zerve-deployment-url)
[![Built with Zerve](https://img.shields.io/badge/Built%20with-Zerve-blue)](https://zerve.ai)
[![ZerveHack 2026](https://img.shields.io/badge/ZerveHack-2026-purple)](https://zervehack.devpost.com)
[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://python.org)

---

## 🔍 What Is This?

Prediction markets like Polymarket and Kalshi let people bet real money on future events — elections, Fed decisions,
sports outcomes, and more. In theory, these markets should be well-calibrated: a market priced at 70% should resolve
correctly ~70% of the time.

**But are they?**

MarketPulse answers three questions:

1. **Where do Polymarket and Kalshi disagree on the same event?** (arbitrage opportunities)
2. **How accurate are these markets over time?** (calibration analysis)
3. **What are the live aggregated odds for any event?** (unified data layer)

Everything is served through a **live REST API** and an **interactive dashboard** — not just a notebook.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                    DATA LAYER                        │
│   Polymarket API  ·  Kalshi API  ·  Metaculus        │
└──────────────┬──────────────┬───────────────────────┘
               │              │
┌──────────────▼──────────────▼───────────────────────┐
│                    LOGIC LAYER                       │
│  Normalizer  ·  Arbitrage Detector  ·  Calibration  │
└──────────────┬──────────────┬───────────────────────┘
               │              │
┌──────────────▼──────────────▼───────────────────────┐
│                     API LAYER                        │
│    /arbitrage    /calibration    /odds/{event}       │
└──────────────┬──────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────┐
│                   DASHBOARD UI                       │
│    Arbitrage Table  ·  Calibration Charts  ·  Feed  │
└─────────────────────────────────────────────────────┘
```

---

## 🚀 Live API Endpoints

Base URL: `https://your-zerve-deployment-url/api`

### `GET /arbitrage`

Returns current cross-platform pricing discrepancies.

**Response:**

```json
{
  "timestamp": "2026-04-01T14:22:00Z",
  "opportunities": [
    {
      "event": "Fed rate cut before June 2026",
      "polymarket_probability": 0.62,
      "kalshi_probability": 0.71,
      "spread": 0.09,
      "direction": "buy_polymarket_sell_kalshi"
    }
  ]
}
```

---

### `GET /calibration/{category}`

Returns accuracy statistics for a given market category.

**Parameters:**

- `category` — one of: `politics`, `economics`, `sports`, `science`, `crypto`

**Response:**

```json
{
  "category": "economics",
  "total_resolved": 312,
  "calibration_score": 0.84,
  "buckets": [
    {
      "probability_range": "60-70%",
      "actual_rate": 0.66,
      "sample_size": 48
    },
    {
      "probability_range": "70-80%",
      "actual_rate": 0.73,
      "sample_size": 61
    }
  ]
}
```

---

### `GET /odds/{event_id}`

Returns aggregated live odds for a specific event across all tracked platforms.

**Response:**

```json
{
  "event_id": "fed-rate-cut-june-2026",
  "event_title": "Fed rate cut before June 2026",
  "platforms": {
    "polymarket": {
      "probability": 0.62,
      "volume_usd": 1420000
    },
    "kalshi": {
      "probability": 0.71,
      "volume_usd": 890000
    }
  },
  "consensus_probability": 0.66,
  "last_updated": "2026-04-01T14:22:00Z"
}
```

---

## 📊 Key Findings

> *(Update these once your analysis is complete)*

- **X% of markets** on Polymarket and Kalshi disagree by more than 5 percentage points on the same event
- Markets in the **`economics`** category show the strongest calibration (score: X.XX)
- Markets in the **`crypto`** category show the weakest calibration — systematically overconfident
- The largest arbitrage spread observed: **XX%** on event `[event name]`
- Markets become significantly more accurate in the **final 72 hours** before resolution

---

## 🛠️ Tech Stack

| Layer             | Technology                                        |
|-------------------|---------------------------------------------------|
| Data ingestion    | Python, Polymarket API, Kalshi API                |
| Core logic        | Python (arbitrage detection, calibration scoring) |
| API serving       | FastAPI, deployed via Zerve                       |
| Dashboard         | Interactive UI via Zerve                          |
| Analysis platform | [Zerve AI](https://zerve.ai)                      |

---

## ⚙️ Run Locally

**Prerequisites:** Python 3.11+, pip

```bash
# Clone the repo
git clone https://github.com/yourusername/marketpulse.git
cd marketpulse

# Install dependencies
pip install -r requirements.txt

# Add your API keys
cp .env.example .env
# Edit .env with your Polymarket and Kalshi API keys

# Run the API server
uvicorn main:app --reload

# API is now live at http://localhost:8000
```

---

## 📁 Project Structure

```
marketpulse/
├── main.py                  # FastAPI app + route definitions
├── fetchers/
│   ├── polymarket.py        # Polymarket API client
│   ├── kalshi.py            # Kalshi API client
│   └── metaculus.py         # Metaculus historical data
├── core/
│   ├── normalizer.py        # Unified event format across platforms
│   ├── arbitrage.py         # Cross-platform discrepancy detection
│   └── calibration.py       # Brier score + calibration bucketing
├── models/
│   └── schemas.py           # Pydantic response models
├── tests/
│   └── test_arbitrage.py    # Unit tests for core logic
├── requirements.txt
└── .env.example
```

---

## 🧠 How the Arbitrage Detection Works

The core algorithm normalizes events across platforms into a unified format, then computes the spread:

```python
def detect_arbitrage(polymarket_event, kalshi_event, threshold=0.05):
    """
    Identify cross-platform pricing discrepancies above a threshold.
    Returns an ArbitrageOpportunity if spread exceeds threshold, else None.
    """
    spread = abs(polymarket_event.probability - kalshi_event.probability)

    if spread < threshold:
        return None

    return ArbitrageOpportunity(
        event=polymarket_event.title,
        polymarket_probability=polymarket_event.probability,
        kalshi_probability=kalshi_event.probability,
        spread=spread,
        direction=get_direction(polymarket_event, kalshi_event)
    )
```

Full implementation in [`core/arbitrage.py`](./core/arbitrage.py).

---

## 📐 How Calibration Is Measured

Calibration is measured using **Brier Score** and **probability bucketing**:

- Group all resolved markets by their predicted probability at time T (e.g. 60–70% bucket)
- Compare the predicted rate to the actual resolution rate for that bucket
- A perfectly calibrated market lies on the diagonal (predicted = actual)

```python
def calibration_score(predictions, outcomes):
    """
    Compute Brier score for a set of predictions.
    Lower is better. Perfect score = 0.0, worst = 1.0.
    """
    return sum((p - o) ** 2 for p, o in zip(predictions, outcomes)) / len(predictions)
```

Full implementation in [`core/calibration.py`](./core/calibration.py).

---

## Hackathon

Built for **ZerveHack 2026** — a $10,000 data science hackathon challenging participants to build end-to-end analytical
systems using the Zerve AI platform.

- **Live Zerve Project:** [View on Zerve](https://your-zerve-project-url)
- **Devpost Submission:** [View on Devpost](https://devpost.com/your-submission)

---

## 📬 Contact

**[Your Name]**

- GitHub: [@PABPAT](https://github.com/PABPAT)
- LinkedIn: [linkedin.com/in/poornaabhijithpatel](https://www.linkedin.com/in/poornaabhijithpatel/)
- Email: poornaabhijith@email.com

---

*Built with [Zerve AI](https://zerve.ai) · ZerveHack 2026*