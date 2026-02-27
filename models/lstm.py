"""
lstm.py — Price forecasting model for FinPort-AI.

Uses linear extrapolation over 3-day price history as a statistically honest
substitute for LSTM given the limited dataset (3 data points per security).
In production, replace _extrapolate_next_price() with a trained LSTM model
once sufficient historical data is available (minimum ~60 days recommended).

Per-security metrics computed:
  - 3-day moving average of close price
  - Momentum: percentage change from day 1 to day 3
  - Predicted next-day price via least-squares linear fit
  - Trend direction: UP (>+0.5%), DOWN (<-0.5%), or FLAT
"""

import numpy as np
from utils.db import managed_conn

FLAT_BAND = 0.5        # % — momentum within this range is classified FLAT
DOWN_ALERT_PCT = -1.0  # % — securities below this trigger a Price Forecast alert


def _extrapolate_next_price(prices: list[float]) -> float:
    """Fit a least-squares line to the price series and return the next value."""
    x = np.arange(len(prices), dtype=float)
    slope, intercept = np.polyfit(x, prices, deg=1)
    return float(intercept + slope * len(prices))


def forecast_prices(down_threshold: float = DOWN_ALERT_PCT) -> dict:
    """
    Compute price forecasts for all securities in Price_History.

    Args:
        down_threshold: Momentum % below which a Price Forecast alert is raised
                        (default -1.0).

    Returns:
        dict with keys:
            securities_analysed  — number of securities processed
            alerts_written       — number of DOWN alerts inserted into Alert
            forecasts            — list of per-security forecast dicts
    """
    # ------------------------------------------------------------------ #
    # 1. Load price history ordered by security and date
    # ------------------------------------------------------------------ #
    query = """
        SELECT ph.security_id, s.ticker, s.security_name,
               ph.price_date, ph.close_price
        FROM Price_History ph
        JOIN Security s ON ph.security_id = s.security_id
        ORDER BY ph.security_id, ph.price_date
    """
    with managed_conn() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(query)
        rows = cur.fetchall()

    if not rows:
        return {"securities_analysed": 0, "alerts_written": 0, "forecasts": []}

    # Group rows by security_id
    securities: dict[int, list] = {}
    for row in rows:
        sid = row["security_id"]
        securities.setdefault(sid, []).append(row)

    # ------------------------------------------------------------------ #
    # 2. Compute metrics per security
    # ------------------------------------------------------------------ #
    forecasts = []
    down_alerts = []

    for sid, price_rows in securities.items():
        # Sort by date (already ordered, but defensive)
        price_rows.sort(key=lambda r: r["price_date"])

        prices = [float(r["close_price"]) for r in price_rows]
        ticker = price_rows[0]["ticker"]
        security_name = price_rows[0]["security_name"]
        latest_date = price_rows[-1]["price_date"]

        n = len(prices)
        moving_avg = round(sum(prices) / n, 4)
        momentum_pct = round((prices[-1] - prices[0]) / prices[0] * 100, 4)
        predicted_price = round(_extrapolate_next_price(prices), 4)

        if momentum_pct > FLAT_BAND:
            trend = "UP"
        elif momentum_pct < -FLAT_BAND:
            trend = "DOWN"
        else:
            trend = "FLAT"

        forecast = {
            "security_id":     sid,
            "ticker":          ticker,
            "security_name":   security_name,
            "data_points":     n,
            "latest_date":     str(latest_date),
            "latest_price":    round(prices[-1], 4),
            "moving_avg_3d":   moving_avg,
            "momentum_pct":    momentum_pct,
            "predicted_price": predicted_price,
            "trend":           trend,
        }
        forecasts.append(forecast)

        # Flag securities trending down more than down_threshold
        if momentum_pct < down_threshold:
            down_alerts.append({
                "security_id": sid,
                "ticker":      ticker,
                "momentum_pct": momentum_pct,
                "predicted_price": predicted_price,
            })

    # ------------------------------------------------------------------ #
    # 3. Write DOWN alerts to Alert table
    #    account_id is required (NOT NULL) — use the first account that
    #    holds this security via its portfolio
    # ------------------------------------------------------------------ #
    alerts_written = 0
    if down_alerts:
        # Build security_id -> account_id lookup
        placeholders = ", ".join(["%s"] * len(down_alerts))
        sid_list = [a["security_id"] for a in down_alerts]
        account_query = f"""
            SELECT h.security_id, MIN(p.account_id) AS account_id
            FROM Holding h
            JOIN Portfolio p ON h.portfolio_id = p.portfolio_id
            WHERE h.security_id IN ({placeholders})
            GROUP BY h.security_id
        """
        with managed_conn() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(account_query, sid_list)
            account_map = {r["security_id"]: r["account_id"] for r in cur.fetchall()}

        insert_sql = """
            INSERT INTO Alert (account_id, alert_type, severity, message)
            VALUES (%s, %s, %s, %s)
        """
        with managed_conn() as conn:
            cur = conn.cursor()
            for alert in down_alerts:
                account_id = account_map.get(alert["security_id"], 1)
                message = (
                    f"Price forecast alert: {alert['ticker']} shows downward momentum "
                    f"of {alert['momentum_pct']:.2f}% over the last 3 days. "
                    f"Predicted next-day price: {alert['predicted_price']:.4f}."
                )
                cur.execute(insert_sql, (account_id, "Price Forecast", "Medium", message))
                alerts_written += 1
            conn.commit()

    return {
        "securities_analysed": len(forecasts),
        "alerts_written":      alerts_written,
        "forecasts":           forecasts,
    }
