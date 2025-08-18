# pipeline/stages/fetch_stage.py
"""
AmpyFin — Val Model
Fetch Stage (context-based)

Responsibility:
- Decide which tickers to evaluate (via registries.adapter_registry active tickers adapter)
- Decide which metrics to fetch (union of required metrics from enabled strategies
  + always include 'current_price' for downstream comparisons)
- Call the ACTIVE adapter for each metric and ticker
- Write results into PipelineContext (no valuation logic here).
"""

from __future__ import annotations

from typing import Dict, List, Any

from adapters.adapter import DataNotAvailable
from pipeline.context import PipelineContext
from registries.adapter_registry import (
    get_active_tickers_adapter,
    get_active_metric_adapter,
)
from registries.strategy_registry import (
    get_enabled_strategy_names,
    get_required_metrics,
)


def _collect_required_metrics() -> List[str]:
    """
    Build the set of canonical metric keys required by all enabled strategies.
    Always includes 'current_price' so the Result Stage can compare fair value vs price.
    """
    names = get_enabled_strategy_names()
    needed: List[str] = ["current_price"]
    for n in names:
        for m in get_required_metrics(n):
            if m not in needed:
                needed.append(m)
    return needed


def run_fetch_stage(ctx: PipelineContext) -> PipelineContext:
    """
    Execute the fetch stage and mutate ctx in-place.
    """
    # Reset prior fetch data (if any)
    ctx.reset_fetch()

    # 1) Tickers
    tickers_adapter = get_active_tickers_adapter()
    ctx.tickers = list(tickers_adapter.fetch())

    # 2) Metrics required by strategies (+ current_price)
    ctx.required_metrics = _collect_required_metrics()

    # 3) Fetch data
    metrics_by_ticker: Dict[str, Dict[str, float | None]] = {}
    errors: Dict[str, Dict[str, str]] = {}

    for tk in ctx.tickers:
        per_ticker: Dict[str, float | None] = {}
        per_ticker_errs: Dict[str, str] = {}

        for metric in ctx.required_metrics:
            adapter = get_active_metric_adapter(metric) if metric != "rule40_score" else None

            # 'rule40_score' is a computed/externally-supplied metric; skip adapter fetch (leave None)
            if metric == "rule40_score":
                per_ticker[metric] = None
                continue

            try:
                value = adapter.fetch(tk)  # type: ignore[union-attr]
                per_ticker[metric] = float(value)
            except DataNotAvailable as e:
                per_ticker[metric] = None
                per_ticker_errs[metric] = str(e)
            except Exception as e:  # pragma: no cover
                per_ticker[metric] = None
                per_ticker_errs[metric] = f"unexpected error: {e}"

        metrics_by_ticker[tk] = per_ticker
        if per_ticker_errs:
            errors[tk] = per_ticker_errs

    ctx.metrics_by_ticker = metrics_by_ticker
    ctx.fetch_errors = errors
    return ctx
