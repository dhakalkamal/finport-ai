"""
ai_server.py — Main FastAPI application for FinPort-AI.
"""

from fastapi import FastAPI, HTTPException
from models.anomaly import detect_anomalies
from models.rebalance import recommend_rebalance
from models.lstm import forecast_prices
from models.sentiment import analyze_sentiment

app = FastAPI(
    title="FinPort-AI",
    description="Standalone AI microservice for the FinPort portfolio management system.",
    version="0.1.0",
)


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "FinPort-AI"}


@app.post("/ai/anomalies")
def run_anomaly_detection(contamination: float = 0.1):
    """
    Run Isolation Forest anomaly detection on the Transaction table.

    Flagged transactions are written to the Alert table with:
      alert_type = 'Anomaly', severity = 'High'

    Optional query param:
      contamination (float, default 0.1) — expected fraction of outliers.
    """
    try:
        result = detect_anomalies(contamination=contamination)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ai/rebalance")
def run_rebalance(drift_threshold: float = 10.0):
    """
    Analyse portfolio asset allocations and recommend rebalancing.

    Compares current allocation (from vw_asset_allocation) against target weights:
      Equity 40%, ETF 25%, Fixed Income 15%, Crypto/Real Estate/Commodity/Other 5% each.

    Portfolios where any asset class drifts beyond drift_threshold percentage
    points receive a Pending entry in the Rebalance_Log table.

    Optional query param:
      drift_threshold (float, default 10.0) — minimum drift in percentage points.
    """
    try:
        result = recommend_rebalance(drift_threshold=drift_threshold)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ai/forecast")
def run_price_forecast(down_threshold: float = -1.0):
    """
    Forecast next-day prices for all securities using linear extrapolation
    over the 3-day price history in Price_History.

    Securities with momentum below down_threshold % receive a Medium-severity
    'Price Forecast' alert in the Alert table.

    Optional query param:
      down_threshold (float, default -1.0) — momentum % that triggers an alert.

    Note: Named /ai/forecast to match the lstm.py module. In production this
    endpoint will be backed by a trained LSTM model once sufficient data exists.
    """
    try:
        result = forecast_prices(down_threshold=down_threshold)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ai/sentiment")
def run_sentiment_analysis():
    """
    Run sentiment analysis on all securities in the database.

    Generates a trend-driven headline per security (based on Price_History
    momentum), scores it against a bullish/bearish keyword dictionary, and
    writes the result to the Alert table:
      alert_type = 'Sentiment'
      severity   = 'Low' (positive) | 'Medium' (neutral) | 'High' (negative)

    Production upgrade: replace keyword scoring with FinBERT inference and
    live NewsAPI headlines by setting NEWS_API_KEY in .env.
    """
    try:
        result = analyze_sentiment()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
