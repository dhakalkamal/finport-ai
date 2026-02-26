"""
ai_server.py — Main FastAPI application for FinPort-AI.

This is a placeholder. Actual route logic will be implemented
in subsequent development phases.
"""

from fastapi import FastAPI

app = FastAPI(
    title="FinPort-AI",
    description="Standalone AI microservice for the FinPort portfolio management system.",
    version="0.1.0",
)


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "FinPort-AI"}


# TODO: Register routers for /anomaly, /forecast, /sentiment, /rebalance
