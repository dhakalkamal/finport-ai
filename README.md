# FinPort-AI

A standalone Python AI microservice that plugs into the existing **FinPort** financial portfolio management system. It connects to the same MySQL database, runs ML models on live portfolio data, and writes AI-generated insights back to the `Alert` and `Rebalance_Log` tables — which the existing React dashboard picks up automatically.

---

## Prerequisites

Before running FinPort-AI, your friend's core system must already be up and running:

- MySQL server with the `finport` database populated
- Node.js API running on **port 5000**
- React dashboard running on **port 5173**

FinPort-AI does **not** replace any of those — it runs alongside them on **port 8000**.

---

## Setup

### 1. Clone this repository

```bash
git clone <repo-url>
cd finport-ai
```

### 2. Install dependencies

> Requires Python 3.9+. Use the `genai` conda environment or any Python environment.

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy the example file and fill in your MySQL credentials:

```bash
cp .env.example .env
```

Edit `.env`:

```
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_password_here
DB_NAME=finport
AI_PORT=8000
```

### 4. Run the AI server

```bash
uvicorn ai_server:app --port 8000 --reload
```

The service will be available at `http://localhost:8000`.

---

## Available AI Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Health check — confirms the service is running and DB is reachable |
| `/anomaly/detect` | POST | Runs Isolation Forest on transaction history to flag unusual activity; writes results to the `Alert` table |
| `/forecast/prices` | POST | Runs an LSTM model on `Price_History` to generate short-term price forecasts for held securities |
| `/sentiment/news` | POST | Fetches recent news via NewsAPI and runs BERT sentiment analysis on headlines for securities in client portfolios; writes sentiment alerts to the `Alert` table |
| `/rebalance/suggest` | POST | Analyses current `Holding` weights against target allocations and generates rebalancing suggestions; writes results to the `Rebalance_Log` table |

---

## How Results Appear in the Dashboard

FinPort-AI writes directly to two tables in the shared `finport` MySQL database:

- **`Alert`** — anomaly detections and sentiment warnings surface here; the existing dashboard already queries this table to display alerts to advisors
- **`Rebalance_Log`** — rebalancing suggestions land here; the dashboard's rebalancing panel reads from this table automatically

No changes are required to the existing Node.js API or React frontend. Once FinPort-AI is running, trigger any endpoint and results will appear in the dashboard on the next data refresh.
