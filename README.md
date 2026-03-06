# FinPort-AI

A standalone Python AI microservice for the **FinPort** financial portfolio management system. It connects to the same MySQL database as the dashboard, runs ML models on live portfolio data, and writes AI-generated insights back to the database — which the React dashboard picks up automatically.

---

## System Architecture

The full FinPort system is made up of two separate repositories that work together:

```
[ MySQL Database: finport ]  <--  shared by both services
         |                 \
         |                  \
  [ finport_ai ]        [ finport-ai ]
  Dashboard repo         This repo
  (React + Node.js)      (Python AI microservice)
  github.com/            github.com/
  Vyanaktesh/finport_ai  dhakalkamal/finport-ai

  port 5000 — Node API   port 8000 — FastAPI
  port 5173 — React UI
```

- **finport_ai** (dashboard) — the React frontend and Node.js/Express API. Handles user authentication, portfolio CRUD, and displays data from MySQL. Set this up first.
- **finport-ai** (this repo) — a FastAPI microservice that reads portfolio data from MySQL, runs anomaly detection, price forecasting, sentiment analysis, and rebalancing logic, then writes results back to the `Alert` and `Rebalance_Log` tables. The dashboard reads those tables automatically.

Both repos connect to the **same MySQL database**. FinPort-AI adds AI capabilities without requiring any changes to the dashboard code.

---

## Prerequisites

Install the following before you start:

- **Python 3.11** — [python.org/downloads](https://www.python.org/downloads/)
- **Node.js (v18+)** — [nodejs.org](https://nodejs.org/)
- **MySQL** and **MySQL Workbench** — [mysql.com/downloads/workbench](https://www.mysql.com/downloads/workbench/)
- **Conda** (optional, recommended for Python env) — [docs.conda.io](https://docs.conda.io/en/latest/miniconda.html)

---

## Step 1 — Set Up the Dashboard (finport_ai)

Clone and run the dashboard repo first. This sets up the MySQL database, Node.js API, and React frontend that FinPort-AI depends on.

### 1.1 Clone the dashboard repo

```bash
git clone https://github.com/Vyanaktesh/finport_ai
cd finport_ai
```

### 1.2 Install Node.js dependencies

```bash
npm install
```

### 1.3 Create the environment file

In the root of `finport_ai`, create a file named `.env`:

```
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_mysql_password_here
DB_NAME=finport
PORT=5000
```

Replace `your_mysql_password_here` with the password you set during MySQL installation.

### 1.4 Import the MySQL schema

1. Open **MySQL Workbench** and connect to your local MySQL server.
2. Create a new schema (database) named `finport`.
3. In the menu, go to **Server > Data Import**.
4. Select **Import from Self-Contained File** and choose the `.sql` schema file included in the `finport_ai` repo.
5. Set the target schema to `finport` and click **Start Import**.

### 1.5 Start the Node.js API server

Open a terminal in the `finport_ai` directory:

```bash
npm run server
```

This starts the backend API on **port 5000**. Leave this terminal running.

### 1.6 Start the React frontend

Open a **second terminal** in the `finport_ai` directory:

```bash
npm run dev
```

This starts the React app on **port 5173**. Leave this terminal running.

---

## Step 2 — Set Up the AI Microservice (finport-ai)

With the dashboard running, clone and start this repo in a separate terminal.

### 2.1 Clone this repo

```bash
git clone https://github.com/dhakalkamal/finport-ai
cd finport-ai
```

### 2.2 Create a Python environment and install dependencies

Requires **Python 3.11**. Choose either option:

**Option A — Conda (recommended)**

```bash
conda create -n genai python=3.11
conda activate genai
pip install -r requirements.txt
```

**Option B — Virtual environment (venv)**

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

### 2.3 Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in the **same MySQL credentials** you used in Step 1.3:

```
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_mysql_password_here
DB_NAME=finport
AI_PORT=8000
```

### 2.4 Start the AI server

Open a **third terminal** in the `finport-ai` directory (with your Python environment activated):

```bash
uvicorn ai_server:app --port 8000 --reload
```

The AI service will be available at `http://localhost:8000`.

---

## Step 3 — Verify Everything is Working

With all three servers running, open your browser and check:

1. **http://localhost:5173** — the FinPort dashboard should load and display the portfolio interface.
2. **http://localhost:8000/docs** — the FastAPI interactive docs page should appear, listing all AI endpoints.
3. In the dashboard, navigate to the **AI Insights** tab — it should show **AI Server Online**.
4. Click **Run All 4 Models** — all four AI analyses should complete and results should appear in the dashboard.

If the AI Insights tab shows the server as offline, double-check that `uvicorn` is still running and that your `.env` credentials match between the two repos.

---

## Port Summary

Each service runs in its own terminal and its own port:

| Service | Port | Command |
|---|---|---|
| MySQL | 3306 | Background service (started by MySQL installer) |
| Node.js API | 5000 | `npm run server` (in `finport_ai`) |
| React frontend | 5173 | `npm run dev` (in `finport_ai`) |
| FinPort-AI | 8000 | `uvicorn ai_server:app --port 8000 --reload` |

---

## Available AI Endpoints

Once the AI server is running, these endpoints are available at `http://localhost:8000`:

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Health check — confirms the AI service is running |
| `/ai/anomalies` | POST | Runs Isolation Forest on the `Transaction` table to flag unusual activity. Results written to `Alert` with `alert_type = 'Anomaly'`. |
| `/ai/forecast` | POST | Computes next-day price forecasts for all securities using `Price_History`. Securities with negative momentum receive a `'Price Forecast'` alert. |
| `/ai/sentiment` | POST | Scores news sentiment per security using a bullish/bearish keyword model. Results written to `Alert` with `alert_type = 'Sentiment'`. |
| `/ai/rebalance` | POST | Compares current portfolio allocation against target weights. Portfolios that have drifted beyond the threshold get a `Pending` entry in `Rebalance_Log`. |

You can test all endpoints interactively via the auto-generated docs at **http://localhost:8000/docs**.

---

## How Results Appear in the Dashboard

FinPort-AI writes directly to two tables in the shared `finport` MySQL database:

- **`Alert`** — anomaly detections, price forecasts, and sentiment warnings. The dashboard's Alerts panel queries this table and displays results to advisors automatically.
- **`Rebalance_Log`** — rebalancing recommendations. The dashboard's Rebalancing panel reads from this table automatically.

No changes are needed to the Node.js API or the React frontend. Once FinPort-AI is running, trigger any endpoint and results will appear in the dashboard on the next data refresh.

---

## Related

**Dashboard repo:** [github.com/Vyanaktesh/finport_ai](https://github.com/Vyanaktesh/finport_ai)

> Note on naming: the dashboard repo is named `finport_ai` (underscore) and this AI microservice repo is named `finport-ai` (hyphen). They are two separate repositories that form one system. Set up `finport_ai` first, then `finport-ai`.
