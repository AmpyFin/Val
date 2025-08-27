# AmpyFin — Val Model

A developer-friendly **valuation engine** that compares **current prices** with **strategy-derived fair values** using pluggable **adapters** and **strategies**, orchestrated by a simple, testable **pipeline**. The system is modular by design so you can swap data sources, add metrics, and plug in new valuation formulas with minimal friction.

---

## Why this exists (design goals)

- **Modularity first.** Every numeric input is fetched by a **single-purpose adapter** (one metric per adapter file). Strategies consume canonical metric names, not data vendors.
- **Swapability.** Choose exactly **one active provider per metric** at runtime (e.g., use Finviz for EPS, yfinance for everything else) without touching pipeline code.
- **Extensibility.** Add a new metric or strategy in minutes (documented below).
- **Deterministic stages.** The pipeline separates **Fetch → Process → Result** with a shared `PipelineContext`.
- **Real-time outputs.** No JSON files. Results go to **console**, optional **UDP broadcast**, and a **live PyQt5 GUI** that refreshes on a timer.
- **Robust consensus.** By default we use **median** across enabled strategies to reduce outlier impact. (Configurable in code if you later want mean/trimmed/weighted.)

---

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -U pip wheel
pip install -r requirements.txt
```

Optional `.env` (for alternative adapters and MongoDB you may enable later):
```
POLYGON_API_KEY=
FINANCIAL_PREP_API_KEY=
Alpaca_API_KEY=
Alpaca_API_SECRET=
MONGODB_CONNECTION_STRING=mongodb://localhost:27017/
```

Run once (console + optional broadcast/GUI based on `control.py`):
```bash
python main.py
```

Use the CLI (supports overrides, GUI, continuous mode, MongoDB):
```bash
python scripts/cli.py --run-once
python scripts/cli.py --loop --sleep 120
python scripts/cli.py --set eps_ttm=yfinance_eps_ttm --run-once
python scripts/cli.py --tickers-source wiki_spy_500_tickers --run-once
python scripts/cli.py --mongodb --run-once  # Store results in MongoDB
python scripts/cli.py --mongodb --mongodb-uri "mongodb://your-server:27017/" --run-once
# Or set MONGODB_CONNECTION_STRING environment variable
```

Listen for broadcasts (if enabled in `control.py`):
```bash
python scripts/udp_listen.py
```

Launch GUI continuously from CLI (if `Gui_mode=True`):
```bash
python scripts/cli.py --loop --sleep 120
```

Test MongoDB connection:
```bash
python scripts/test_mongodb.py
```

---

## Control flags (`control.py`)

```python
Run_continous = False     # False: run once, True: run forever
Gui_mode = False          # True: open live PyQt5 GUI (refresh timer & controls)
Broadcast_mode = False    # True: send UDP payload of results

broadcast_network = "127.0.0.1"
broadcast_port = 5002

# Loop timing
LOOP_SLEEP_SECONDS = 180

# JSON dump (optional)
Json_dump_enable = True   # True = write a JSON file each run
json_dump_dir = "out"     # directory for JSON output files

# MongoDB storage (optional)
MONGODB_ENABLE = False    # True = store results in MongoDB (clears existing valuations)

# Normalized mirrors (used internally)
RUN_CONTINUOUS = bool(Run_continous)
GUI_MODE = bool(Gui_mode)
BROADCAST_MODE = bool(Broadcast_mode)
BROADCAST_NETWORK = broadcast_network
BROADCAST_PORT = int(broadcast_port)
JSON_DUMP_ENABLE = bool(Json_dump_enable)
JSON_DUMP_DIR = json_dump_dir
```

---

## Architecture

```
adapters/
  adapter.py                        # interfaces + common exceptions
  yf_session.py                     # rotating Session/User-Agents for yfinance
  current_price_adapter/
  eps_adapter/
  revenue_last_quarter_adapter/
  growth_adapter/
  shares_outstanding_adapter/
  revenue_ttm_adapter/
  ebit_ttm_adapter/
  gross_profit_ttm_adapter/
  fcf_ttm_adapter/
  net_debt_adapter/
  book_value_per_share_adapter/     # (for Residual Income, BVPS)
  tickers_adapter/                  # static list + Wikipedia scrapers
strategies/
  strategy.py                       # Strategy interface
  peter_lynch.py
  psales_reversion.py
  ev_ebit_bridge.py
  fcf_yield.py
  gp_multiple_reversion.py
  dcf_gordon.py                     # DCF with terminal growth (negative-policy knob)
  epv_ebit.py                       # Earnings Power Value (no-growth perpetuity)
  residual_income.py                # RI per-share model
registries/
  adapter_registry.py               # **Single source of truth** for active providers
  strategy_registry.py              # enables strategies + declares required metrics + defaults
  pipeline_registry.py              # reads adapter/strategy selections; applies optional overrides
pipeline/
  context.py                        # PipelineContext container
  stages/
    fetch_stage.py                  # fetches metrics per ticker via active adapters
    process_stage.py                # executes each strategy with required inputs
    result_stage.py                 # median consensus; console + broadcast + GUI + MongoDB
  mongodb_storage.py              # MongoDB storage for valuation results
  runner.py                         # run_once / run_forever orchestrator
ui/
  viewer.py                         # live PyQt5 table: sorting, colors, pause/resume, interval
scripts/
  cli.py                            # runtime overrides + run once/loop + GUI routing + MongoDB
  udp_listen.py                     # debug helper for UDP broadcasts
  test_mongodb.py                   # MongoDB connection test script
tests/
  ...                               # smoke tests (can run offline by setting AMPYFIN_TEST_OFFLINE=1)
control.py
main.py
README.md
```

### Data flow
1. **Fetch Stage**: uses `registries.adapter_registry` to instantiate the active adapter **for each metric** and calls `fetch(ticker)` → populates `ctx.metrics_by_ticker[ticker][metric]`.
2. **Process Stage**: looks up enabled strategies in `strategy_registry`, ensures required metrics are present, then calls `strategy.run(params)`; results go to `ctx.fair_values[ticker][strategy_name]`.
3. **Result Stage**: computes **median** across per-ticker strategy fair values (`consensus_fair_value`). Prints a table, optionally broadcasts UDP, stores in MongoDB, and/or opens/refreshes the GUI.

---

## Adapters

### Interface
Every metric adapter implements:
```python
class MetricAdapter(Protocol):
    def get_name(self) -> str: ...
    def fetch(self, ticker: str) -> float: ...
```
Raise `DataNotAvailable` if a value cannot be fetched (the pipeline will record it and continue). We also use a small `retry_on_failure` decorator for resiliency.

### Naming & structure
- One folder per metric (e.g., `eps_adapter/`, `fcf_ttm_adapter/`).
- One file per **single-purpose** adapter: `yfinance_eps_ttm_adapter.py`, `finviz_eps_ttm_adapter.py`, etc.
- Tickers sources are adapters, too (`tickers_adapter/`), including a static list and Wikipedia scrapers.

### Provider selection (single source of truth)
`registries/adapter_registry.py` imports **all adapters** and exposes:
- `_METRIC_PROVIDER_FACTORIES` — vendor factories per metric
- `_ACTIVE_METRIC_PROVIDER` — **exactly one** chosen provider per metric
- `_ACTIVE_TICKERS_SOURCE` — chosen tickers source

Public helpers:
```python
set_active_metric_provider("eps_ttm", "finviz_eps_ttm")
get_active_metric_adapter("eps_ttm")

set_active_tickers_source("wiki_spy_500_tickers")
get_active_tickers_adapter()
```

**Runtime overrides** (no file edits): `scripts/cli.py` accepts `--set METRIC=PROVIDER`, `--tickers-source …`, and `--mongodb` which are applied by `pipeline_registry.apply_pipeline_registry()`.

### Rate-limit hardening (yfinance)
`adapters/yf_session.py` maintains a small pool of rotating `requests.Session` objects and common desktop user-agents, used by all yfinance adapters to reduce friction.

---

## MongoDB Storage

### Overview
The system can store valuation results in MongoDB for persistence and analysis. When enabled, it clears existing valuations and stores the complete results from each run.

### Configuration
- **Environment variable**: `MONGODB_CONNECTION_STRING` (defaults to `mongodb://localhost:27017/`)
- **Database**: `val_trades`
- **Collection**: `valuations`

### Usage
Enable via CLI:
```bash
python scripts/cli.py --mongodb --run-once
python scripts/cli.py --mongodb --mongodb-uri "mongodb://your-server:27017/" --run-once
# Or set MONGODB_CONNECTION_STRING environment variable
```

Enable via control.py:
```python
MONGODB_ENABLE = True
```

### Data Structure
Each valuation run creates a document with:
```json
{
  "run_id": "unique_run_identifier",
  "generated_at": timestamp,
  "generated_at_iso": "ISO8601_string",
  "tickers": ["list", "of", "tickers"],
  "strategy_names": ["list", "of", "strategies"],
  "by_ticker": {
    "TICKER": {
      "current_price": float,
      "strategy_fair_values": {"strategy_name": float},
      "consensus_fair_value": float,
      "consensus_discount": float,
      "consensus_p25": float,
      "consensus_p75": float
    }
  },
  "fetch_errors": {"ticker": "error_message"},
  "strategy_errors": {"ticker": {"strategy": "error_message"}},
  "created_at": datetime.utcnow()
}
```

### Testing
Test your MongoDB connection:
```bash
python scripts/test_mongodb.py
```

---

## Strategies

### Interface
```python
class Strategy(Protocol):
    def get_name(self) -> str: ...
    def run(self, params: Dict[str, Any]) -> float: ...
```
- Inputs are supplied via `params` using **canonical metric keys** (e.g., `eps_ttm`, `revenue_ttm`, `net_debt`).
- If inputs are missing/invalid and the strategy cannot proceed, raise `StrategyInputError`; the pipeline records the error and the strategy’s value becomes `None` for that ticker.

### Included strategies (enabled by default)
- **Peter Lynch** (`peter_lynch.py`)
- **P/S Reversion** (`psales_reversion.py`)
- **EV/EBIT Bridge** (`ev_ebit_bridge.py`)
- **FCF Yield** (`fcf_yield.py`)
- **Gross Profit multiple reversion** (`gp_multiple_reversion.py`)
- **DCF (Gordon)** (`dcf_gordon.py`) — has `dcf_negative_equity_handling: exclude|zero|allow` (default: `exclude` → robust)
- **EPV (EBIT)** (`epv_ebit.py`)
- **Residual Income** (`residual_income.py`) — requires **BVPS** via `book_value_per_share`

You enable/disable strategies and define their **required metrics** and **default hyperparameters** in `registries/strategy_registry.py`.

### Consensus method
The result stage uses **median** across available strategies for a ticker (ignores `None`s). Median is robust to outliers and noisy inputs. If you prefer mean/trimmed/weighted, you can refactor in `pipeline/consensus.py` later.

---

## How to add a **new ADAPTER** (step-by-step)

1. **Create a subfolder** under `adapters/<metric>_adapter/` if it doesn’t exist (e.g., `adapters/pe_ratio_adapter/`) and add `__init__.py`.
2. **Implement a single-purpose class**:
   ```python
   # adapters/pe_ratio_adapter/yfinance_pe_ratio_adapter.py
   from adapters.adapter import MetricAdapter, DataNotAvailable, retry_on_failure
   import yfinance as yf
   from adapters.yf_session import make_session

   class YFinancePERatioAdapter(MetricAdapter):
       def __init__(self): self._name = "yfinance_pe_ratio"
       def get_name(self): return self._name

       @retry_on_failure(max_retries=2, delay=0.5)
       def fetch(self, ticker: str) -> float:
           t = yf.Ticker(ticker.upper(), session=make_session())
           val = t.info.get("trailingPE")
           if val is None:
               raise DataNotAvailable(f"{self._name}: P/E not available")
           return float(val)
   ```
3. **Register it** in `registries/adapter_registry.py`:
   ```python
   from adapters.pe_ratio_adapter.yfinance_pe_ratio_adapter import YFinancePERatioAdapter

   _METRIC_PROVIDER_FACTORIES["pe_ratio"] = {
       "yfinance_pe_ratio": lambda: YFinancePERatioAdapter(),
   }
   _ACTIVE_METRIC_PROVIDER["pe_ratio"] = "yfinance_pe_ratio"
   ```
4. **Use it in a strategy** by adding `"pe_ratio"` to that strategy’s required metrics (if needed).

**Tip:** follow the naming convention `vendor_metric_adapter.py` and keep the class’ `get_name()` aligned with the provider string used in the registry.

---

## How to add a **new STRATEGY** (step-by-step)

1. **Create the file** in `strategies/` (e.g., `strategies/my_value_model.py`):
   ```python
   from strategies.strategy import Strategy, StrategyInputError

   class MyValueModel(Strategy):
       def __init__(self): self._name = "my_value_model"
       def get_name(self): return self._name

       def run(self, params):
           # read inputs e.g., price = params.get("current_price")
           # validate & compute fair value per share
           # raise StrategyInputError on missing/invalid input
           return float(42.0)
   ```
2. **Register it** in `registries/strategy_registry.py`:
   ```python
   from strategies.my_value_model import MyValueModel

   _STRATEGY_FACTORIES["my_value_model"] = lambda: MyValueModel()
   _REQUIRED_METRICS["my_value_model"] = ["current_price"]  # example
   _DEFAULT_HYPERPARAMS["my_value_model"] = {"alpha": 0.5}  # example
   _ENABLED_STRATEGIES.append("my_value_model")
   ```
3. **Run** the pipeline:
   ```bash
   python scripts/cli.py --run-once
   ```

**Contract:** return a **fair value per share (USD)**. If a strategy doesn’t apply (e.g., negative equity in DCF with strict policy), raise `StrategyInputError` so the consensus ignores it.

---

## GUI (PyQt5)

- **Live table** with sorting, color-coded Discount %, **Refresh now**, **Pause/Resume**, and **Interval** controls.
- To use, set `Gui_mode = True` in `control.py`, then:
  ```bash
  python scripts/cli.py --loop --sleep 120     # live, periodic refresh
  # or
  python scripts/cli.py --run-once             # one-off window
  ```
- Discount coloring:
  - ≥ **+20%** undervalued → strong green
  - **0–20%** undervalued → soft green
  - **< 0%** (overvalued) → soft red

---

## Broadcasting (UDP)

- Enable in `control.py`: `Broadcast_mode = True`.
- A compact JSON-like payload of the entire run is sent to `broadcast_network:broadcast_port` (default `127.0.0.1:5002`).
- View with:
  ```bash
  python scripts/udp_listen.py
  ```

---

## Tests

- Run all tests:
  ```bash
  pytest -q
  ```
- To **skip network** calls:
  ```bash
  AMPYFIN_TEST_OFFLINE=1 pytest -q
  ```
- What’s covered:
  - Registry selection (active providers & tickers source)
  - Adapter smoke tests (numeric checks)
  - Pipeline smoke (end-to-end structure)
- Add your own unit tests for new adapters/strategies (recommend minimum “smoke” tests plus a couple of edge cases).

---

## Conventions & tips

- **Error handling:** raise `DataNotAvailable` (adapters) or `StrategyInputError` (strategies) for missing/invalid inputs; the pipeline will record and keep running.
- **Single-purpose adapters:** one metric per file keeps composition simple and avoids vendor coupling.
- **Naming:** `yfinance_*`, `fmp_*`, `finviz_*`, `polygon_*` for clarity.
- **Median consensus:** robust default for combining strategies; avoids over-weighting any single noisy model.
- **No JSON files:** output goes to console, optional UDP broadcast, and GUI.
- **YFinance hardening:** all yfinance adapters use a rotating `Session` with common desktop UAs to reduce rate-limit friction.

---

## Roadmap ideas

- Historical backtests to produce **per-strategy weights** (enabling a data-driven weighted consensus).
- More adapters (Polygon/Alpaca/FMP) and sector-specific strategies (e.g., banks/insurers).
- CLI overrides for strategy hyperparameters (per strategy) on demand.
- Persistence layer (SQLite/Parquet) behind a feature flag, if desired later.

---

## License & credit

- Built for the AmpyFin open ecosystem; designed to be extended freely.
- **This module values**: correctness, clarity, composability.
- Pull requests welcome.
