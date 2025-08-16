# AmpyFin — Val Model

_A lightweight, open-source valuation pipeline that compares **current price** to **strategy-defined fair value** and surfaces opportunities with a configurable **Margin of Safety (MoS)**. Now featuring **dynamic strategy weighting** based on company characteristics._

> ⚠️ **Disclaimer:** This is developer tooling for research/education. It is **not** investment advice. Always do your own due diligence.

---

## Table of Contents

- [What is the Val Model?](#what-is-the-val-model)
- [Core Features](#core-features)
- [Dynamic Strategy Weighting](#dynamic-strategy-weighting)
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

- print a **Rich** console table with **dynamic strategy weights**,
- write a machine-readable **JSON** snapshot,
- expose the snapshot over a **FastAPI** endpoint and a **WebSocket** stream,
- serve a simple **web dashboard** for browsing/filtering results.

The whole pipeline is designed to be **adapter-driven** and **strategy-driven**, so developers can swap data sources and valuation models at runtime.

**NEW: Dynamic Strategy Weighting** - The system now automatically balances Peter Lynch vs P/S Reversion strategies based on company characteristics like net margin, growth rate, and earnings quality.

---

## Core Features

- **Pipeline stages:** `Fetch` (multithreaded) → `Process` (multithreaded) → `Result` (console + JSON export)
- **Adapters:** `yfinance` (no vendor keys), `alpaca`, `polygon`, `fmp` (Financial Modeling Prep), `ibkr` (IBeam gateway), `mock_local`
- **Strategies:** `peter_lynch`, `psales_rev`
- **Dynamic Weighting:** Automatic strategy balancing based on company fundamentals
- **Config-first, CLI override:** set defaults in `config/settings.yaml`, override with CLI flags
- **Live outputs:** `out/results.json` + `/results` API + `/stream` WebSocket
- **Dashboard:** built-in HTML/JS UI at `/` (served by FastAPI)
- **Continuous mode:** run the pipeline on an interval to refresh results automatically
- **Tests:** fast, network-free unit tests with `pytest`
- **Dockerized:** run writer + API/dashboard together with `docker compose`

---

## Dynamic Strategy Weighting

The Val Model now uses **intelligent weighting** to balance Peter Lynch vs P/S Reversion strategies based on company characteristics:

### Weighting Logic

**Net Margin-Based Weighting:**
- **Low margin (< 5%):** 80% P/S Reversion, 20% Peter Lynch
- **High margin (> 10%):** 80% Peter Lynch, 20% P/S Reversion  
- **Medium margin (5-10%):** 60% Peter Lynch, 40% P/S Reversion

**Growth Rate Adjustments:**
- **Negative growth:** Reduce Peter Lynch weight by 30%
- **High growth (> 15%):** Increase Peter Lynch weight by 20%

**Earnings Quality:**
- **Negative EPS:** 90% P/S Reversion, 10% Peter Lynch

### Why This Matters

**Netflix Example:**
- **P/S Reversion:** $3000+ (overestimates due to historical bubble P/S ratios)
- **Peter Lynch:** ~$1000 (more conservative, based on earnings growth)
- **Dynamic Weight:** ~$1500 (balanced approach considering Netflix's mature growth phase)

**Early-Stage Companies:**
- **NVAX/CTMX:** Heavily weighted toward P/S Reversion (low margins, negative earnings)
- **Established Tech:** Balanced toward Peter Lynch (high margins, stable earnings)

### Configuration

Adjust weighting behavior in `config/settings.yaml`:

```yaml
weighting:
  low_margin_threshold: 0.05    # < 5% net margin: favor P/S reversion
  high_margin_threshold: 0.10   # > 10% net margin: favor Peter Lynch
  negative_growth_penalty: 0.3  # Reduce Peter Lynch weight by 30% for negative growth
  high_growth_boost: 0.2        # Increase Peter Lynch weight by 20% for >15% growth
  default_peter_lynch_weight: 0.5
  default_psales_weight: 0.5
```

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
│   ├── weighting.py          # NEW: Dynamic strategy weighting
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

# 3) Run once in console mode with dynamic weighting (no vendor keys needed)
python main.py --adapters yfinance                --strategies peter_lynch,psales_rev                --tickers NFLX,NVAX,AAPL,MSFT,TSLA

# 4) Start the API (in a second terminal)
python -m uvicorn server.api:app --host 127.0.0.1 --port 8000

# 5) Open the dashboard
# http://127.0.0.1:8000/
```

**Console Output Now Shows:**
```
┌─────────┬─────────┬──────────────┬─────────┬──────────┬──────────┐
│ Ticker  │ Price   │ Fair Value   │ MoS     │ Strategy │ Weights  │
├─────────┼─────────┼──────────────┼─────────┼──────────┼──────────┤
│ NFLX    │ $485.09 │ $1,247.50    │ 61.1%   │ peter_lynch │ PL:0.6 PS:0.4 │
│ NVAX    │ $9.58   │ $45.20       │ 78.8%   │ psales_rev  │ PL:0.2 PS:0.8 │
└─────────┴─────────┴──────────────┴─────────┴──────────┴──────────┘
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

# NEW: Dynamic weighting configuration
weighting:
  # Net margin thresholds for strategy weighting
  low_margin_threshold: 0.05    # < 5% net margin: favor P/S reversion
  high_margin_threshold: 0.10   # > 10% net margin: favor Peter Lynch
  
  # Growth rate thresholds
  negative_growth_penalty: 0.3  # Reduce Peter Lynch weight by 30% for negative growth
  high_growth_boost: 0.2        # Increase Peter Lynch weight by 20% for >15% growth
  
  # Default weights when insufficient data
  default_peter_lynch_weight: 0.5
  default_psales_weight: 0.5

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

One-shot run that prints a Rich table with **dynamic weights** and writes `out/results.json`:

```bash
python main.py --adapters yfinance                --strategies peter_lynch,psales_rev                --tickers NFLX,NVAX,AAPL,MSFT,TSLA
```

Flags you can use:

- `--adapters yfinance,alpaca` — only hit the adapters listed (no accidental API calls)
- `--strategies peter_lynch` — compute only chosen strategies
- `--min-mos 0.25` — use a 25% MoS threshold for the summary table
- `--tickers-file path/to/tickers.txt` — newline or comma-separated tickers

### Continuous Writer

Loop forever, refreshing `out/results.json` every _N_ seconds:

```bash
python main.py --adapters yfinance                --strategies peter_lynch,psales_rev                --tickers NFLX,NVAX,AAPL,MSFT,TSLA                --continuous                --interval 60
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
- **Dynamic weighting** automatically balances strategies based on company fundamentals.

Examples:

```bash
# Only yfinance (no vendor keys), both strategies with dynamic weighting
python main.py --adapters yfinance --strategies peter_lynch,psales_rev --tickers NFLX,NVAX,AAPL

# Use IBKR for price first (via IBeam), then yfinance as fallback
python main.py --adapters ibkr,yfinance --strategies peter_lynch --tickers AAPL,MSFT

# Peter Lynch only (no weighting since only one strategy)
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
      "ticker": "NFLX",
      "price": 485.09,
      "best_fair_value": 1247.50,
      "best_mos": 0.611,
      "best_strategy": "peter_lynch",
      "undervalued": true,
      "weights": {
        "peter_lynch": 0.6,
        "psales_rev": 0.4
      }
    }
    // ...
  ],
  "per_strategy": {
    "peter_lynch": { "NFLX": { "fv": 1247.50, "mos": 0.611 } },
    "psales_rev": { "NFLX": { "fv": 3120.25, "mos": 0.845 } }
  }
}
```

Notes:
- `best_*` is the **weighted average** across the selected strategies.
- `weights` shows the dynamic weighting applied (NEW).
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
  --tickers NFLX,NVAX,AAPL,MSFT,TSLA
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

### Extending Dynamic Weighting

To add a new strategy to the weighting system:

1. Update `Pipeline/weighting.py` to include your strategy in the weight calculation
2. Modify the `apply_weighted_valuation` function to handle your strategy
3. Update the configuration schema in `core/config.py` and `config/settings.yaml`

---

## Troubleshooting

- **Big MoS numbers?**  
  Likely fundamentals missing → only one strategy returns a fair value. Ensure your selected adapter(s) can provide `eps_ttm` (for Peter Lynch) or `sales_per_share` + `ps_history` (for P/S Reversion). `yfinance` supplies many fields without paid keys.

- **Vendor rate-limits (429) or forbidden (403):**  
  Prefer `--adapters yfinance` or place `yfinance` first. Paid providers may throttle free tiers.

- **No `out/results.json`:**  
  Make sure `outputs` exists on `Settings` and `outputs.json_path` points to `out/results.json`. Create the folder: `mkdir -p out`.

- **Dashboard shows "missing results":**  
  Run the writer once (or in continuous mode) so the JSON exists. The API & dashboard read `AMPYFIN_RESULTS_PATH` or default `out/results.json`.

- **IBKR/IBeam TLS errors:**  
  For dev on localhost, set `IBEAM_INSECURE_TLS=true`. Avoid this in production; use a trusted cert/endpoint.

- **Compose tried to pull an image:**  
  Our `docker-compose.yml` builds locally for both services and uses the same image (`ampyfin/val:dev`).

- **Weights showing as 0.5/0.5 for all stocks:**  
  Check that your adapters are providing `net_margin` data. The system falls back to default weights when margin data is unavailable.

---

## Roadmap Ideas

- More strategies: DCF, EV/EBIT, CAPE, sector-based caps
- Caching & backoff for paid providers
- Alerts (email/webhook) on MoS crossovers
- Historical snapshots in SQLite/Parquet for trend analysis
- CI/CD (lint, type-check, tests, image build)
- **Enhanced weighting:** Sector-specific weights, market cap considerations
- **Backtesting:** Historical performance of dynamic weighting vs static strategies

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

**Happy building!** 🚀

If you have tweaks you want (new strategies, a different data source, custom weighting logic, or a custom table in the dashboard), the registry pattern makes it easy—drop in a file, register it, and select it on the CLI.


