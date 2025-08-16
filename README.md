# AmpyFin — Val Model

_A lightweight, open-source valuation pipeline that compares **current price** to **strategy-defined fair value** and surfaces opportunities with a configurable **Margin of Safety (MoS)**._

> ⚠️ **Disclaimer:** This is developer tooling for research/education. It is **not** investment advice. Always do your own due diligence.

---

## Table of Contents

- [What is the Val Model?](#what-is-the-val-model)
- [Core Features](#core-features)
- [Repository Structure](#repository-structure)
- [Quick Start (Local)](#quick-start-local)
- [Configuration](#configuration)
  - [settings.yaml](#settingsyaml)
  - [.env & Secrets](#env--secrets)
- [Running Modes](#running-modes)
  - [Console Mode](#console-mode)
  - [Continuous Writer](#continuous-writer)
  - [HTTP API](#http-api)
  - [Web Dashboard](#web-dashboard)
- [Choosing Adapters & Strategies](#choosing-adapters--strategies)
- [Results JSON Schema](#results-json-schema)
- [Docker & Compose](#docker--compose)
- [Optional: IBKR via IBeam](#optional-ibkr-via-ibeam)
- [Testing](#testing)
- [Extending the System](#extending-the-system)
  - [Add a New Strategy](#add-a-new-strategy)
  - [Add a New Adapter](#add-a-new-adapter)
- [Troubleshooting](#troubleshooting)
- [Roadmap Ideas](#roadmap-ideas)
- [License](#license)

---

## What is the Val Model?

The Val Model fetches market & fundamental data, computes **fair values** using one or more **valuation strategies** (e.g., Peter Lynch PEG, Price/Sales reversion), and compares them to current price to calculate **Margin of Safety (MoS)**. It can:

- print a **Rich** console table,
- write a machine-readable **JSON** snapshot,
- expose the snapshot over a **FastAPI** endpoint and a **WebSocket** stream,
- serve a simple **web dashboard** for browsing/filtering results.

The whole pipeline is designed to be **adapter-driven** and **strategy-driven**, so developers can swap data sources and valuation models at runtime.

---

## Core Features

- **Pipeline stages:** `Fetch` (multithreaded) → `Process` (multithreaded) → `Result` (console + JSON export)
- **Adapters:** `yfinance` (no vendor keys), `alpaca`, `polygon`, `fmp` (Financial Modeling Prep), `ibkr` (IBeam gateway), `mock_local`
- **Strategies:** `peter_lynch`, `psales_rev`
- **Config-first, CLI override:** set defaults in `config/settings.yaml`, override with CLI flags
- **Live outputs:** `out/results.json` + `/results` API + `/stream` WebSocket
- **Dashboard:** built-in HTML/JS UI at `/` (served by FastAPI)
- **Continuous mode:** run the pipeline on an interval to refresh results automatically
- **Tests:** fast, network-free unit tests with `pytest`
- **Dockerized:** run writer + API/dashboard together with `docker compose`

---

## Repository Structure

```
.
├── Adapters/
│   ├── base.py
│   ├── yfinance.py
│   ├── alpaca.py
│   ├── polygon.py
│   ├── fmp.py
│   ├── ibkr_webapi.py
│   └── mock_local.py
├── Strategies/
│   ├── base.py
│   ├── peter_lynch.py
│   └── psales_reversion.py
├── Pipeline/
│   ├── context.py
│   ├── fetch.py
│   ├── process.py
│   └── result.py
├── Registries/
│   ├── adapters.py
│   └── strategies.py
├── server/
│   ├── __init__.py
│   ├── api.py               # FastAPI app: /, /health, /results, /stream
│   └── web/
│       └── index.html       # Lightweight dashboard
├── config/
│   ├── settings.yaml
│   └── settings.example.yaml
├── core/
│   ├── config.py
│   └── logging.py
├── out/
│   └── .gitkeep
├── tests/
│   ├── test_api.py
│   ├── test_result_export.py
│   └── test_strategies.py
├── main.py                  # Typer CLI entrypoint
├── requirements.txt
├── docker-compose.yml
├── Dockerfile
├── .env.example
└── .gitignore
```

---

## Quick Start (Local)

Prereqs: Python **3.11+**, `pip`.

```bash
# 1) Install deps
python -m pip install -r requirements.txt

# 2) (Optional) copy env template if you plan to use paid APIs
cp .env.example .env

# 3) Run once in console mode (no vendor keys needed thanks to yfinance)
python main.py --adapters yfinance                --strategies peter_lynch,psales_rev                --tickers NVAX,CTMX,AAPL,MSFT,TSLA

# 4) Start the API (in a second terminal)
uvicorn server.api:app --host 127.0.0.1 --port 8000

# 5) Open the dashboard
# http://127.0.0.1:8000/
```

---

## Configuration

### `settings.yaml`

Defaults live in `config/settings.yaml`. You can override any of them via CLI at runtime.

```yaml
mode: console                 # console|gui|broadcast (informational; CLI selects behavior)
run: once                     # once|continuous

adapters:                     # order = priority per field (first non-None wins)
  - yfinance
  - alpaca
  - polygon
  - fmp
  - mock_local

strategies:
  - peter_lynch
  - psales_rev

tickers: ["AAPL","MSFT","NVDA"]   # default list (override with --tickers or --tickers-file)

thresholds:
  min_mos: 0.20               # 20% Margin of Safety threshold used in summaries/filters

caps:                         # used by some strategies (e.g., Peter Lynch growth PE clamps)
  max_growth_pe: 50
  min_growth_pe: 5

schedule:
  interval_sec: 60            # used by continuous mode if --interval not provided

logging:
  level: INFO

outputs:
  json_path: "out/results.json"
  include_per_strategy: true
```

> **Important:** The **order** of `adapters` matters. For each field (e.g., price, eps), the first adapter that returns a non-`None` value is used.

### `.env` & Secrets

Use `.env` for provider credentials (already in `.gitignore`). See `.env.example`:

```
POLYGON_API_KEY=
FINANCIAL_PREP_API_KEY=
ALPACA_API_KEY=
ALPACA_API_SECRET=

# IBKR/IBeam (optional)
IBKR_USERNAME=
IBKR_PASSWORD=
IBEAM_GATEWAY_URL=https://localhost:5000
IBEAM_INSECURE_TLS=true   # dev only; self-signed cert

# Where API/dashboard look for results
AMPYFIN_RESULTS_PATH=out/results.json
```

---

## Running Modes

### Console Mode

One-shot run that prints a Rich table and writes `out/results.json`:

```bash
python main.py --adapters yfinance                --strategies peter_lynch,psales_rev                --tickers NVAX,CTMX,AAPL,MSFT,TSLA
```

Flags you can use:

- `--adapters yfinance,alpaca` — only hit the adapters listed (no accidental API calls)
- `--strategies peter_lynch` — compute only chosen strategies
- `--min-mos 0.25` — use a 25% MoS threshold for the summary table
- `--tickers-file path/to/tickers.txt` — newline or comma-separated tickers

### Continuous Writer

Loop forever, refreshing `out/results.json` every _N_ seconds:

```bash
python main.py --adapters yfinance                --strategies peter_lynch,psales_rev                --tickers NVAX,CTMX,AAPL,MSFT,TSLA                --continuous                --interval 60
```

### HTTP API

Start the API:

```bash
uvicorn server.api:app --host 127.0.0.1 --port 8000
```

Endpoints:

- `GET /health` → `{ status, time, results_path }`
- `GET /results`  
  Query params:
  - `undervalued_only=true|false`
  - `min_mos=0.25` (override MoS threshold)
  
  Examples:
  ```bash
  curl http://127.0.0.1:8000/results
  curl "http://127.0.0.1:8000/results?undervalued_only=true&min_mos=0.25"
  ```

- `WS /stream` (WebSocket) → pushes full JSON payload whenever `out/results.json` changes

### Web Dashboard

A zero-dependency dashboard is served at the API root:

```
http://127.0.0.1:8000/
```

- Filters: MoS threshold, undervalued-only, sort/limit
- Live updates via `/stream`
- Download current view as CSV

---

## Choosing Adapters & Strategies

You can choose **exactly** which adapters & strategies to run — either in `config/settings.yaml` or via CLI.

- **Adapter selection** controls **which data sources** are queried and in what **priority order**.
- **Strategy selection** controls **which valuation models** run.

Examples:

```bash
# Only yfinance (no vendor keys), both strategies
python main.py --adapters yfinance --strategies peter_lynch,psales_rev --tickers NVAX,CTMX,AAPL

# Use IBKR for price first (via IBeam), then yfinance as fallback
python main.py --adapters ibkr,yfinance --strategies peter_lynch --tickers AAPL,MSFT

# Peter Lynch only, stricter MoS
python main.py --adapters yfinance --strategies peter_lynch --min-mos 0.3 --tickers NVAX,CTMX
```

---

## Results JSON Schema

`out/results.json` (path configurable) is the contract for the API and dashboard.

```jsonc
{
  "generated_at": "2025-08-15T23:48:36.776177+00:00",
  "min_mos": 0.2,
  "tickers": [
    {
      "ticker": "NVAX",
      "price": 9.58,
      "best_fair_value": 111.0,
      "best_mos": 0.9137,
      "best_strategy": "peter_lynch",
      "undervalued": true
    }
    // ...
  ],
  "per_strategy": {
    "peter_lynch": { "NVAX": { "fv": 111.0, "mos": 0.9137 } },
    "psales_rev": { "AAPL": { "fv": 228.23, "mos": -0.015 } }
  }
}
```

Notes:
- `best_*` is the best (most conservative MoS) across the selected strategies.
- `per_strategy` is optional (enabled via `outputs.include_per_strategy`).

---

## Docker & Compose

Single image runs the API by default; the writer runs as a second service.

```bash
docker compose up --build
# API: http://127.0.0.1:8000/
```

`docker-compose.yml` ships with:
- `api` (FastAPI server + dashboard)
- `writer` (continuous pipeline)  
Both share the `./out` volume for `results.json`.

Customize writer command in `docker-compose.yml`:
```yaml
command: >
  python main.py
  --adapters yfinance
  --strategies peter_lynch,psales_rev
  --tickers NVAX,CTMX,AAPL,MSFT,TSLA
  --continuous
  --interval 120
```

---

## Optional: IBKR via IBeam

If you want **Interactive Brokers** prices:

1. Create `.env.ibeam` (do **not** commit):
   ```
   IBKR_USERNAME=your_username
   IBKR_PASSWORD=your_password
   IBEAM_ACCOUNT=U1234567          # or DU1234567 for paper
   IBEAM_GATEWAY_PORT=5000
   ```

2. Run IBeam:
   ```bash
   docker run --rm -p 127.0.0.1:5000:5000 --env-file .env.ibeam voyz/ibeam:latest
   # complete login at https://localhost:5000 if required (self-signed cert)
   ```

3. Set env for the Val app (e.g., in `.env`):
   ```
   IBEAM_GATEWAY_URL=https://localhost:5000
   IBEAM_INSECURE_TLS=true  # dev only
   ```

4. Run with IBKR first in adapter order:
   ```bash
   python main.py --adapters ibkr,yfinance --strategies peter_lynch --tickers AAPL,MSFT
   ```

> If the gateway is not authenticated, the adapter skips gracefully and falls back to later adapters.

---

## Testing

Fast, network-free tests:

```bash
python -m pytest -q
```

- `tests/test_strategies.py` — math checks for strategies
- `tests/test_result_export.py` — JSON export contract
- `tests/test_api.py` — API filtering behavior using a temp results file

---

## Extending the System

### Add a New Strategy

1. Create `Strategies/my_strategy.py`:
   ```python
   from .base import BaseStrategy
   from typing import Optional

   class MyStrategy(BaseStrategy):
     name = "my_strategy"

     def compute(self, ticker: str, data: dict) -> Optional[float]:
         # data contains merged fields (price, eps_ttm, sales_per_share, etc.)
         # return a fair value (float) or None to skip
         eps = data.get("eps_ttm")
         if not eps:
             return None
         fv = eps * 12.34
         return round(float(fv), 2)
   ```

2. Register it in `Registries/strategies.py`:
   ```python
   from Strategies.my_strategy import MyStrategy
   STRATEGIES["my_strategy"] = MyStrategy
   ```

3. Run it:
   ```bash
   python main.py --adapters yfinance --strategies my_strategy --tickers AAPL,MSFT
   ```

### Add a New Adapter

1. Create `Adapters/my_source.py`:
   ```python
   from .base import BaseAdapter
   from typing import Dict, Any

   class MySourceAdapter(BaseAdapter):
     name = "my_source"
     fields_provided = ["price","eps_ttm"]  # declare what you can fill

     def fetch_one(self, ticker: str) -> Dict[str, Any]:
         # return a dict of available fields, missing fields omitted
         return {"price": 123.45}
   ```

2. Register in `Registries/adapters.py`:
   ```python
   from Adapters.my_source import MySourceAdapter
   ADAPTERS["my_source"] = MySourceAdapter
   ```

3. Use it (order matters):
   ```bash
   python main.py --adapters my_source,yfinance --strategies peter_lynch --tickers NVAX
   ```

The merge policy is **first non-None wins** per field according to adapter order you pass on the CLI (or list in `settings.yaml`).

---

## Troubleshooting

- **Big MoS numbers?**  
  Likely fundamentals missing → only one strategy returns a fair value. Ensure your selected adapter(s) can provide `eps_ttm` (for Peter Lynch) or `sales_per_share` + `ps_history` (for P/S Reversion). `yfinance` supplies many fields without paid keys.

- **Vendor rate-limits (429) or forbidden (403):**  
  Prefer `--adapters yfinance` or place `yfinance` first. Paid providers may throttle free tiers.

- **No `out/results.json`:**  
  Make sure `outputs` exists on `Settings` and `outputs.json_path` points to `out/results.json`. Create the folder: `mkdir -p out`.

- **Dashboard shows “missing results”:**  
  Run the writer once (or in continuous mode) so the JSON exists. The API & dashboard read `AMPYFIN_RESULTS_PATH` or default `out/results.json`.

- **IBKR/IBeam TLS errors:**  
  For dev on localhost, set `IBEAM_INSECURE_TLS=true`. Avoid this in production; use a trusted cert/endpoint.

- **Compose tried to pull an image:**  
  Our `docker-compose.yml` builds locally for both services and uses the same image (`ampyfin/val:dev`).

---

## Roadmap Ideas

- More strategies: DCF, EV/EBIT, CAPE, sector-based caps
- Caching & backoff for paid providers
- Alerts (email/webhook) on MoS crossovers
- Historical snapshots in SQLite/Parquet for trend analysis
- CI/CD (lint, type-check, tests, image build)

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

### Development Setup

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Install development dependencies: `pip install -r requirements.txt`
4. Run tests: `python -m pytest`
5. Commit your changes: `git commit -m 'Add amazing feature'`
6. Push to the branch: `git push origin feature/amazing-feature`
7. Open a Pull Request

---

## Support

- **Issues:** Use the [GitHub Issues](https://github.com/yourusername/val/issues) page
- **Discussions:** Join the [GitHub Discussions](https://github.com/yourusername/val/discussions) for questions and ideas
- **Documentation:** Check the inline code comments and this README

---

**Happy building!** 🚀

If you have tweaks you want (new strategies, a different data source, or a custom table in the dashboard), the registry pattern makes it easy—drop in a file, register it, and select it on the CLI.

---

*Built with ❤️ for the open-source financial analysis community.*
