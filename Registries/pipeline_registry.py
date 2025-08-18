# registries/pipeline_registry.py
"""
AmpyFin — Val Model
Pipeline Registry (no duplication)

Goal:
- Avoid duplicating adapter choices across files.
- Treat registries.adapter_registry as the **single source of truth** for:
    * active tickers source
    * active provider per metric
- Treat registries.strategy_registry as the **single source of truth** for:
    * enabled strategies (and their defaults)

This module only:
  1) Returns a snapshot of current selections (for logging/diagnostics).
  2) Optionally applies *overrides* if explicitly provided (e.g., from a CLI).

Typical usage at startup:
    from registries.pipeline_registry import apply_pipeline_registry
    selections = apply_pipeline_registry()   # just reads current choices

If you want to override at runtime (without editing files):
    overrides = {
        "tickers_source": "wiki_spy_500_tickers",
        "metric_providers": {"eps_ttm": "yfinance_eps_ttm"},
        "enabled_strategies": ["peter_lynch", "fcf_yield"],
    }
    apply_pipeline_registry(overrides)
"""

from __future__ import annotations

from typing import Dict, List, Optional

from registries import adapter_registry as ar
from registries import strategy_registry as sr


def _snapshot() -> Dict[str, object]:
    """Return a dict with the current selections from the registries."""
    metrics = ar.list_available_metrics()
    return {
        "tickers_source": ar.get_active_tickers_source_name(),
        "metric_providers": {m: ar.get_active_metric_provider_name(m) for m in metrics},
        "enabled_strategies": sr.get_enabled_strategy_names(),
    }


def _validate_metric_overrides(mp: Dict[str, str]) -> None:
    for metric, provider in mp.items():
        names = ar.get_metric_provider_names(metric)
        if provider not in names:
            raise KeyError(
                f"[pipeline_registry] Unknown provider '{provider}' for metric '{metric}'. "
                f"Available: {names}"
            )


def apply_pipeline_registry(
    overrides: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    """
    Apply optional overrides; otherwise just return a snapshot of current selections.

    overrides schema (all optional):
      {
        "tickers_source": str,
        "metric_providers": { "<metric>": "<provider_name>", ... },
        "enabled_strategies": [ "<strategy_name>", ... ],
      }
    """
    if overrides:
        # Override tickers source
        if "tickers_source" in overrides and overrides["tickers_source"]:
            ar.set_active_tickers_source(str(overrides["tickers_source"]))

        # Override metric providers
        if "metric_providers" in overrides and overrides["metric_providers"]:
            mp = dict(overrides["metric_providers"])  # type: ignore[arg-type]
            _validate_metric_overrides(mp)
            for metric, provider in mp.items():
                ar.set_active_metric_provider(metric, provider)

        # Override enabled strategies
        if "enabled_strategies" in overrides and overrides["enabled_strategies"]:
            names = list(overrides["enabled_strategies"])  # type: ignore[list-item]
            sr.set_enabled_strategy_names(names)

    # Always return the post-override snapshot
    return _snapshot()
