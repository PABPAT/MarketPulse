from fastapi import FastAPI

app = FastAPI(
    title="MarketPulse",
    description="Real-time prediction market arbitrage detection and calibration analysis",
    version="1.0.0"
)

@app.get("/health")
def health_check():
    return {"status": "ok", "project": "MarketPulse"}