"""
sentiment.py — News sentiment analysis model for FinPort-AI.

Current implementation: keyword-dictionary scoring on trend-driven synthetic
headlines. This demonstrates the full pipeline and output structure cleanly.

Production upgrade path:
  1. Replace _generate_headline() with a NewsAPI call:
       newsapi = NewsApiClient(api_key=os.getenv('NEWS_API_KEY'))
       articles = newsapi.get_everything(q=ticker, language='en', page_size=5)
  2. Replace _score_headline() with FinBERT inference:
       from transformers import pipeline
       nlp = pipeline('text-classification', model='ProsusAI/finbert')
       label = nlp(headline)[0]['label']   # 'positive' | 'negative' | 'neutral'

The Alert rows written, severity mapping, and return schema are identical
regardless of which scoring backend is used.
"""

from utils.db import managed_conn

# ------------------------------------------------------------------ #
# Keyword dictionaries
# ------------------------------------------------------------------ #
BULLISH_WORDS = {
    "surges", "rallies", "climbs", "gains", "soars", "rises", "jumps",
    "outperforms", "beats", "upgrades", "upgraded", "record", "strong",
    "growth", "momentum", "bullish", "positive", "confidence", "buying",
    "breakout", "upside", "recovery", "expansion", "robust", "optimism",
}

BEARISH_WORDS = {
    "falls", "drops", "slips", "tumbles", "plunges", "declines", "sinks",
    "underperforms", "misses", "downgrades", "downgraded", "weak", "loss",
    "bearish", "negative", "concern", "selling", "breakdown", "downside",
    "risk", "uncertainty", "contraction", "caution", "pressure", "warning",
}

# ------------------------------------------------------------------ #
# Headline templates keyed by trend direction
# Each list gives variety — security_id % len(list) picks the template
# ------------------------------------------------------------------ #
_TEMPLATES = {
    "UP": [
        "{ticker} surges on strong quarterly momentum, analysts upgraded outlook",
        "{ticker} climbs as investor confidence grows; institutional buying accelerates",
        "{ticker} rallies to multi-week highs with robust volume and upside momentum",
        "{ticker} gains amid positive market sentiment and sector rotation into growth",
        "{ticker} beats expectations: record trading volume signals bullish breakout",
    ],
    "DOWN": [
        "{ticker} falls as growth concerns weigh on investor sentiment",
        "{ticker} drops on weak momentum; analysts flag near-term downside risk",
        "{ticker} tumbles amid market uncertainty, downgrade risk elevated",
        "{ticker} declines under selling pressure as bearish signals mount",
        "{ticker} slips on negative outlook; caution advised ahead of key data",
    ],
    "FLAT": [
        "{ticker} holds steady as market awaits key economic data",
        "{ticker} consolidates near support with mixed signals from analysts",
        "{ticker} trades flat amid cautious sentiment and low volume",
        "{ticker} neutral session: neither strong buying nor selling pressure detected",
        "{ticker} stable after recent moves; investors remain on the sidelines",
    ],
}

# Alert severity by sentiment label
_SEVERITY = {"positive": "Low", "neutral": "Medium", "negative": "High"}


def _get_price_trends() -> dict[int, dict]:
    """Return {security_id: {ticker, security_name, momentum_pct, trend, account_id}}."""
    query = """
        SELECT ph.security_id, s.ticker, s.security_name, ph.price_date, ph.close_price
        FROM Price_History ph
        JOIN Security s ON ph.security_id = s.security_id
        ORDER BY ph.security_id, ph.price_date
    """
    account_query = """
        SELECT h.security_id, MIN(p.account_id) AS account_id
        FROM Holding h
        JOIN Portfolio p ON h.portfolio_id = p.portfolio_id
        GROUP BY h.security_id
    """
    with managed_conn() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(query)
        price_rows = cur.fetchall()
        cur.execute(account_query)
        account_rows = cur.fetchall()

    account_map = {r["security_id"]: r["account_id"] for r in account_rows}

    # Group prices by security and compute trend
    groups: dict[int, list] = {}
    for row in price_rows:
        groups.setdefault(row["security_id"], []).append(row)

    FLAT_BAND = 0.5
    trends = {}
    for sid, rows in groups.items():
        rows.sort(key=lambda r: r["price_date"])
        prices = [float(r["close_price"]) for r in rows]
        momentum = (prices[-1] - prices[0]) / prices[0] * 100

        if momentum > FLAT_BAND:
            trend = "UP"
        elif momentum < -FLAT_BAND:
            trend = "DOWN"
        else:
            trend = "FLAT"

        trends[sid] = {
            "ticker":        rows[0]["ticker"],
            "security_name": rows[0]["security_name"],
            "momentum_pct":  round(momentum, 4),
            "trend":         trend,
            "account_id":    account_map.get(sid, 1),
        }
    return trends


def _generate_headline(ticker: str, trend: str, security_id: int) -> str:
    """Pick a trend-appropriate headline template for the given security."""
    templates = _TEMPLATES[trend]
    template = templates[security_id % len(templates)]
    return template.format(ticker=ticker)


def _score_headline(headline: str) -> tuple[str, int, int, int]:
    """
    Score a headline using the bullish/bearish keyword dictionaries.

    Returns:
        (sentiment_label, net_score, bullish_hits, bearish_hits)
        sentiment_label: 'positive' | 'negative' | 'neutral'
    """
    words = set(headline.lower().replace(",", "").replace(";", "").replace(":", "").split())
    bullish_hits = len(words & BULLISH_WORDS)
    bearish_hits = len(words & BEARISH_WORDS)
    net = bullish_hits - bearish_hits

    if net > 0:
        label = "positive"
    elif net < 0:
        label = "negative"
    else:
        label = "neutral"

    return label, net, bullish_hits, bearish_hits


def analyze_sentiment() -> dict:
    """
    Run sentiment analysis for all securities and write alerts to the Alert table.

    Returns:
        dict with keys:
            securities_analysed  — total securities processed
            alerts_written       — rows inserted into Alert
            breakdown            — count of positive / neutral / negative results
            results              — list of per-security sentiment dicts
    """
    trends = _get_price_trends()
    if not trends:
        return {
            "securities_analysed": 0,
            "alerts_written": 0,
            "breakdown": {"positive": 0, "neutral": 0, "negative": 0},
            "results": [],
        }

    results = []
    breakdown = {"positive": 0, "neutral": 0, "negative": 0}

    insert_sql = """
        INSERT INTO Alert (account_id, alert_type, severity, message)
        VALUES (%s, %s, %s, %s)
    """

    alerts_written = 0
    with managed_conn() as conn:
        cur = conn.cursor()

        for sid, info in sorted(trends.items()):
            headline = _generate_headline(info["ticker"], info["trend"], sid)
            label, net_score, bull_hits, bear_hits = _score_headline(headline)
            severity = _SEVERITY[label]
            breakdown[label] += 1

            message = (
                f"Sentiment analysis for {info['ticker']} ({info['security_name']}): "
                f"{label.upper()} (score {net_score:+d}, "
                f"{bull_hits} bullish / {bear_hits} bearish keywords). "
                f"Headline: \"{headline}\". "
                f"3-day momentum: {info['momentum_pct']:+.2f}%."
            )

            cur.execute(insert_sql, (info["account_id"], "Sentiment", severity, message))
            alerts_written += 1

            results.append({
                "security_id":   sid,
                "ticker":        info["ticker"],
                "security_name": info["security_name"],
                "trend":         info["trend"],
                "momentum_pct":  info["momentum_pct"],
                "headline":      headline,
                "sentiment":     label,
                "net_score":     net_score,
                "bullish_hits":  bull_hits,
                "bearish_hits":  bear_hits,
                "severity":      severity,
            })

        conn.commit()

    return {
        "securities_analysed": len(results),
        "alerts_written":      alerts_written,
        "breakdown":           breakdown,
        "results":             results,
    }
