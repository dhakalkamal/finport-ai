"""
rebalance.py — Smart portfolio rebalancing engine for FinPort-AI.

Reads current asset allocation from vw_asset_allocation, compares against
target weights, flags portfolios where any asset class drifts more than
DRIFT_THRESHOLD percentage points from its target, and writes recommendations
to the Rebalance_Log table.
"""

import datetime
import pandas as pd
from utils.db import managed_conn

# Target allocation (must sum to 100)
TARGET_ALLOCATIONS = {
    "Equity":       40.0,
    "ETF":          25.0,
    "Fixed Income": 15.0,
    "Crypto":        5.0,
    "Real Estate":   5.0,
    "Commodity":     5.0,
    "Other":         5.0,
}

DRIFT_THRESHOLD = 10.0  # percentage points


def _get_allocations() -> pd.DataFrame:
    """Return vw_asset_allocation as a DataFrame."""
    query = "SELECT portfolio_id, portfolio_name, asset_class, class_value FROM vw_asset_allocation"
    with managed_conn() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(query)
        rows = cur.fetchall()
    return pd.DataFrame(rows)


def _get_advisor_map() -> dict:
    """Return {portfolio_id: advisor_id} using the primary advisor per portfolio.

    Falls back to any active advisor when no primary is flagged.
    """
    query = """
        SELECT p.portfolio_id, ca.advisor_id, ca.is_primary
        FROM Portfolio p
        JOIN Account a  ON p.account_id  = a.account_id
        JOIN Client_Advisor ca ON a.client_id = ca.client_id
        WHERE ca.end_date IS NULL OR ca.end_date >= CURDATE()
        ORDER BY p.portfolio_id, ca.is_primary DESC
    """
    with managed_conn() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(query)
        rows = cur.fetchall()

    # First row per portfolio wins (ORDER BY is_primary DESC puts primary first)
    advisor_map = {}
    for row in rows:
        pid = row["portfolio_id"]
        if pid not in advisor_map:
            advisor_map[pid] = row["advisor_id"]
    return advisor_map


def recommend_rebalance(drift_threshold: float = DRIFT_THRESHOLD) -> dict:
    """
    Analyse portfolio allocations and recommend rebalancing where needed.

    Args:
        drift_threshold: Minimum percentage-point drift to trigger a recommendation.

    Returns:
        dict with keys:
            portfolios_analysed    — total number of portfolios checked
            portfolios_flagged     — number needing rebalancing
            logs_written           — rows inserted into Rebalance_Log
            recommendations        — list of per-portfolio drift summaries
    """
    df = _get_allocations()
    if df.empty:
        return {
            "portfolios_analysed": 0,
            "portfolios_flagged": 0,
            "logs_written": 0,
            "recommendations": [],
        }

    df["class_value"] = df["class_value"].astype(float)
    advisor_map = _get_advisor_map()
    today = datetime.date.today()

    recommendations = []
    log_rows = []

    for portfolio_id, group in df.groupby("portfolio_id"):
        portfolio_name = group["portfolio_name"].iloc[0]
        total_value = group["class_value"].sum()
        if total_value == 0:
            continue

        # Build current allocation dict (asset classes not present default to 0%)
        current = {row["asset_class"]: (row["class_value"] / total_value) * 100
                   for _, row in group.iterrows()}

        # Compute drift for every target asset class
        drifts = {}
        for asset_class, target_pct in TARGET_ALLOCATIONS.items():
            actual_pct = float(current.get(asset_class, 0.0))
            drift = actual_pct - target_pct
            drifts[asset_class] = {
                "target_pct": round(target_pct, 2),
                "actual_pct": round(actual_pct, 2),
                "drift_pct":  round(drift, 2),
            }

        # Flag classes that exceed the threshold
        flagged = {k: v for k, v in drifts.items()
                   if abs(v["drift_pct"]) > drift_threshold}

        if not flagged:
            continue

        # Build human-readable reason
        parts = []
        for ac, info in flagged.items():
            direction = "overweight" if info["drift_pct"] > 0 else "underweight"
            parts.append(
                f"{ac} is {direction} at {info['actual_pct']:.1f}% "
                f"(target {info['target_pct']:.1f}%, drift {info['drift_pct']:+.1f}%)"
            )
        reason = "Rebalancing required — " + "; ".join(parts) + "."

        advisor_id = advisor_map.get(portfolio_id, 1)   # fallback to advisor 1

        log_rows.append({
            "portfolio_id": int(portfolio_id),
            "advisor_id":   int(advisor_id),
            "rebalance_date": today,
            "reason":       reason,
            "status":       "Pending",
        })

        recommendations.append({
            "portfolio_id":   int(portfolio_id),
            "portfolio_name": portfolio_name,
            "total_value":    round(float(total_value), 2),
            "flagged_classes": flagged,
            "reason":         reason,
        })

    # Write to Rebalance_Log
    insert_sql = """
        INSERT INTO Rebalance_Log (portfolio_id, advisor_id, rebalance_date, reason, status)
        VALUES (%s, %s, %s, %s, %s)
    """
    logs_written = 0
    with managed_conn() as conn:
        cur = conn.cursor()
        for row in log_rows:
            cur.execute(insert_sql, (
                row["portfolio_id"],
                row["advisor_id"],
                row["rebalance_date"],
                row["reason"],
                row["status"],
            ))
            logs_written += 1
        conn.commit()

    return {
        "portfolios_analysed": df["portfolio_id"].nunique(),
        "portfolios_flagged":  len(recommendations),
        "logs_written":        logs_written,
        "recommendations":     recommendations,
    }
