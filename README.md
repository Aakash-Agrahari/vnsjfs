# Wind Desk

Web app for a GB power buyer who must purchase day-ahead electricity and needs to know
(1) what the latest wind forecast says at decision time and (2) how accurate that forecast has been.

Data: Elexon BMRS only, national wind. `FUELHH` (actuals, fuelType WIND) and `WINDFOR` (forecasts).
Scope: purchase decisions made in **January 2026** (delivery days 2 Jan - 1 Feb 2026).

**Live app:** `<paste your Vercel URL here>`

> **AI disclosure:** this project was built with the help of an AI assistant (Anthropic Claude) for
> scaffolding, code and documentation. I reviewed, ran and tested the result.

## Stack
- Backend: Python 3.12, FastAPI (pure-Python analysis, no pandas, so it fits a Vercel function)
- Frontend: React 18 (ES modules) with Vite and Recharts
- Docker (backend + nginx-served frontend) and Vercel deployment

## Files and directories
```
.
├── api/index.py              Vercel serverless entrypoint (re-exports the FastAPI app)
├── backend/
│   ├── app/
│   │   ├── config.py         Business assumptions: date scope, default cutoff, max horizon
│   │   ├── data.py           Snapshot loader + DataStore (latest forecast at/before a time)
│   │   ├── analysis.py       Forecast selection rules and error metrics (pure functions)
│   │   ├── elexon.py         Elexon BMRS client (FUELHH, WINDFOR)
│   │   └── main.py           FastAPI routes under /api
│   ├── scripts/
│   │   ├── fetch_data.py         Download real data -> backend/data/snapshot.json.gz
│   │   └── make_demo_snapshot.py Synthetic data for offline demos (UI shows a warning banner)
│   ├── data/                 snapshot.json.gz lives here (commit it for deployment)
│   ├── tests/                pytest unit + API tests
│   └── Dockerfile
├── frontend/
│   ├── src/                  App.jsx, api.js, format.js, components/, styles.css
│   ├── Dockerfile, nginx.conf
│   └── vite.config.js        Dev proxy: /api -> localhost:8000
├── docker-compose.yml
├── vercel.json
├── requirements.txt / requirements-dev.txt
└── README.md
```

## Start the application (local, without Docker)
Prerequisites: Python 3.11+, Node 18+.

```bash
# 1. backend (from repo root)
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python -m backend.scripts.fetch_data      # real Elexon data (needs internet, ~1-3 min)
uvicorn backend.app.main:app --reload --port 8000

# 2. frontend (new terminal)
cd frontend
npm install
npm run dev                         # http://localhost:5173
```
No internet? Run `python -m backend.scripts.make_demo_snapshot` instead (synthetic data).

Tests: `pytest -q backend/tests`

## Start with Docker
```bash
python -m backend.scripts.fetch_data    # create the snapshot first (or use the demo one)
docker compose up --build
# app: http://localhost:8080   API docs: http://localhost:8000/docs
```

## Deploy on Vercel
1. Run `fetch_data`, then commit `backend/data/snapshot.json.gz` (remove it from .gitignore if you add it there).
2. Push to GitHub, import the repo in Vercel (framework preset "Other"; settings come from `vercel.json`).
3. Deploy, open the URL, and paste it at the top of this README.

## How it works
- **Day-ahead rule:** for delivery day D and decision time T (UK local, default 09:00 on D-1), each
  half-hour uses the latest WINDFOR forecast with `publishTime <= T`. Nothing published later is used.
- **Fixed lead time rule:** each half-hour uses the latest forecast published at least H hours before it.
- **Error** = forecast - actual. Positive = forecast overstated wind (buyer short).
- **Metrics:** MAE, RMSE, bias, MAE as % of mean output, P50/P90/P95 absolute error, P90 over- and under-forecast.
  P90 over-forecast is the suggested shortfall buffer.
- **Snapshot:** Elexon is queried once offline; the app serves a compressed snapshot, so it is fast and
  does not depend on Elexon being up. Only forecasts published 0-48 h before target are kept.

## Assumptions
- A "decision in January" means forecasts published in January 2026; delivery days are 2 Jan - 1 Feb.
  Targets with no January-published forecast at the chosen rule are skipped.
- Default decision time 09:00 UK is an assumption; change it in the UI to match your venue's gate closure.
- Times from Elexon are UTC; January is GMT so UK local = UTC, but conversion is done properly via `zoneinfo`.
- National wind only; no demand, prices or other fuels.
