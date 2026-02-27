"""
anomaly.py — Isolation Forest anomaly detection for FinPort-AI.

Reads transactions from the Transaction table, runs Isolation Forest on
(total_amount, fees, quantity), flags anomalies, and writes them to Alert.
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from utils.db import managed_conn


def detect_anomalies(contamination: float = 0.1) -> dict:
    """
    Detect anomalous transactions using Isolation Forest.

    Args:
        contamination: Expected proportion of outliers in the dataset (default 0.1).

    Returns:
        dict with keys:
            total_transactions  — number of rows analysed
            anomalies_detected  — number of flagged transactions
            alerts_written      — number of rows inserted into Alert
            flagged_ids         — list of transaction_ids that were flagged
    """
    # ------------------------------------------------------------------ #
    # 1. Load transaction data
    # ------------------------------------------------------------------ #
    query = """
        SELECT transaction_id, account_id, total_amount, fees, quantity
        FROM `Transaction`
    """
    with managed_conn() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query)
        rows = cursor.fetchall()
    df = pd.DataFrame(rows)

    if df.empty:
        return {
            "total_transactions": 0,
            "anomalies_detected": 0,
            "alerts_written": 0,
            "flagged_ids": [],
        }

    # ------------------------------------------------------------------ #
    # 2. Prepare feature matrix
    #    quantity can be NULL (e.g. Deposit/Withdrawal rows) — fill with 0
    # ------------------------------------------------------------------ #
    features = df[["total_amount", "fees", "quantity"]].fillna(0).astype(float)

    # ------------------------------------------------------------------ #
    # 3. Run Isolation Forest
    # ------------------------------------------------------------------ #
    model = IsolationForest(contamination=contamination, random_state=42)
    df["score"] = model.fit_predict(features)   # -1 = anomaly, 1 = normal

    anomalies = df[df["score"] == -1].copy()

    if anomalies.empty:
        return {
            "total_transactions": len(df),
            "anomalies_detected": 0,
            "alerts_written": 0,
            "flagged_ids": [],
        }

    # ------------------------------------------------------------------ #
    # 4. Write alerts to the Alert table
    # ------------------------------------------------------------------ #
    insert_sql = """
        INSERT INTO Alert (account_id, alert_type, severity, message)
        VALUES (%s, %s, %s, %s)
    """

    alerts_written = 0
    with managed_conn() as conn:
        cursor = conn.cursor()
        for _, row in anomalies.iterrows():
            message = (
                f"Anomalous transaction detected: transaction_id={int(row['transaction_id'])} "
                f"(total_amount={float(row['total_amount']):.2f}, "
                f"fees={float(row['fees']):.2f}, "
                f"quantity={float(row['quantity'] or 0):.4f})."
            )
            cursor.execute(insert_sql, (
                int(row["account_id"]),
                "Anomaly",
                "High",
                message,
            ))
            alerts_written += 1
        conn.commit()

    return {
        "total_transactions": len(df),
        "anomalies_detected": len(anomalies),
        "alerts_written": alerts_written,
        "flagged_ids": [int(i) for i in anomalies["transaction_id"].tolist()],
    }
