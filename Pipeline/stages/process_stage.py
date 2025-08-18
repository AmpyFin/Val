# pipeline/stages/process_stage.py
"""
AmpyFin — Val Model
Process Stage (context-based)

Responsibility:
- Instantiate enabled strategies (from strategy registry).
- For each ticker, gather inputs from ctx.metrics_by_ticker, merge with
  default + override hyperparameters, then run strategy.run(params) to compute fair value.
- Write results into ctx.fair_values and ctx.strategy_errors (no I/O here).
"""

from __future__ import annotations

from typing import Any, Dict, List

from pipeline.context import PipelineContext
from registries.strategy_registry import (
    get_enabled_strategy_names,
    get_strategy_factory,
    get_default_hyperparams,
)
from strategies.strategy import Strategy, StrategyInputError


def run_process_stage(
    ctx: PipelineContext,
    hyperparam_overrides: Dict[str, Dict[str, float]] | None = None,
) -> PipelineContext:
    """
    Execute the process stage and mutate ctx in-place.
    """
    # Reset prior process data (if any)
    ctx.reset_process()

    # Allow call-time overrides (merged with any existing ones on ctx)
    if hyperparam_overrides:
        # Shallow merge: call-time overrides take precedence
        merged: Dict[str, Dict[str, float]] = dict(ctx.hyperparam_overrides)
        for sname, hp in hyperparam_overrides.items():
            cur = dict(merged.get(sname, {}))
            cur.update(hp or {})
            merged[sname] = cur
        ctx.hyperparam_overrides = merged

    # Strategy lineup
    ctx.strategy_names = get_enabled_strategy_names()

    fair_values: Dict[str, Dict[str, float | None]] = {}
    errors: Dict[str, Dict[str, str]] = {}

    for tk in ctx.tickers:
        per_ticker: Dict[str, float | None] = {}
        per_ticker_errs: Dict[str, str] = {}
        metrics = ctx.metrics_by_ticker.get(tk, {})

        for sname in ctx.strategy_names:
            factory = get_strategy_factory(sname)
            strat: Strategy = factory()

            # Build params dict from metrics + defaults + overrides
            params: Dict[str, Any] = {}
            params.update(metrics)  # includes metric keys like 'eps_ttm', etc.
            params.update(get_default_hyperparams(sname))
            params.update(ctx.hyperparam_overrides.get(sname, {}))

            try:
                fv = float(strat.run(params))
                per_ticker[sname] = fv
            except StrategyInputError as e:
                per_ticker[sname] = None
                per_ticker_errs[sname] = str(e)
            except Exception as e:  # pragma: no cover
                per_ticker[sname] = None
                per_ticker_errs[sname] = f"unexpected error: {e}"

        fair_values[tk] = per_ticker
        if per_ticker_errs:
            errors[tk] = per_ticker_errs

    ctx.fair_values = fair_values
    ctx.strategy_errors = errors
    return ctx
