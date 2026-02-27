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

### 2. Create a Python environment and install dependencies

> Requires Python 3.11. Choose whichever option suits your setup.

**Option A — Conda (recommended)**

```bash
conda create -n genai python=3.11
conda activate genai
pip install -r requirements.txt
```

**Option B — Virtual environment (Mac/Linux/Windows)**

```bash
python -m venv venv
```

```bash
# Mac / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

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

Open a **new terminal** (separate from the Node.js and React terminals) and run:

```bash
uvicorn ai_server:app --port 8000 --reload
```

The service will be available at `http://localhost:8000`.

> **Port summary — each service runs in its own terminal:**
>
> | Service | Port | Terminal |
> |---|---|---|
> | Node.js API (existing) | 5000 | Terminal 1 |
> | React frontend (existing) | 5173 | Terminal 2 |
> | FinPort-AI (this service) | 8000 | Terminal 3 |
>
> FinPort-AI runs completely independently. Starting or stopping it has no effect on the Node.js server or the React frontend.

---

## Available AI Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Health check — confirms the service is running |
| `/ai/anomalies` | POST | Runs Isolation Forest on `Transaction` data to flag unusual activity; writes results to the `Alert` table |
| `/ai/forecast` | POST | Computes next-day price forecasts for all securities from `Price_History`; writes `Price Forecast` alerts for downward-trending securities |
| `/ai/sentiment` | POST | Scores news sentiment per security using a bullish/bearish keyword dictionary; writes `Sentiment` alerts to the `Alert` table |
| `/ai/rebalance` | POST | Compares current allocation (from `vw_asset_allocation`) against target weights; writes `Pending` recommendations to the `Rebalance_Log` table |

---

## How Results Appear in the Dashboard

FinPort-AI writes directly to two tables in the shared `finport` MySQL database:

- **`Alert`** — anomaly detections and sentiment warnings surface here; the existing dashboard already queries this table to display alerts to advisors
- **`Rebalance_Log`** — rebalancing suggestions land here; the dashboard's rebalancing panel reads from this table automatically

No changes are required to the existing Node.js API or React frontend. Once FinPort-AI is running, trigger any endpoint and results will appear in the dashboard on the next data refresh.
