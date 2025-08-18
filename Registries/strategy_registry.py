# registries/strategy_registry.py
"""
AmpyFin — Val Model
Strategy Registry (separate from pipeline)

Purpose:
- Central place to register valuation strategies, their factories,
  required metric inputs, and default hyperparameters.
- Pipeline code asks this registry which strategies are enabled and what
  inputs each strategy needs so the Fetch stage knows which metrics to pull.

Usage (examples):
    from registries.strategy_registry import (
        get_enabled_strategy_names,
        get_strategy_factory,
        get_required_metrics,
        get_default_hyperparams,
        set_enabled_strategy_names,
    )

    names = get_enabled_strategy_names()
    strat = get_strategy_factory("peter_lynch")()
    req = get_required_metrics("peter_lynch")           # ['eps_ttm','eps_cagr_5y']
    hps = get_default_hyperparams("peter_lynch")        # dict of defaults

Notes:
- "required_metrics" lists canonical metric keys (see README).
- Hyperparams are optional; strategies will use their own internal defaults
  if a value isn't provided.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Sequence, Type

from strategies.strategy import Strategy
from strategies.peter_lynch import PeterLynchStrategy
from strategies.psales_reversion import PSalesReversionStrategy
from strategies.ev_ebit_bridge import EVEBITBridgeStrategy
from strategies.fcf_yield import FCFYieldStrategy
from strategies.rule40_evs import Rule40EVSStrategy
from strategies.gp_multiple_reversion import GPMultipleReversionStrategy
from strategies.dcf_gordon import DCFGordonStrategy
from strategies.epv_ebit import EPVEBITStrategy
from strategies.residual_income import ResidualIncomeStrategy


# ---------------------------------------------------------------------------
# Name -> factory
_STRATEGY_FACTORIES: Dict[str, Callable[[], Strategy]] = {
    "peter_lynch": lambda: PeterLynchStrategy(),
    "psales_reversion": lambda: PSalesReversionStrategy(),
    "ev_ebit_bridge": lambda: EVEBITBridgeStrategy(),
    "fcf_yield": lambda: FCFYieldStrategy(),
    "rule40_evs": lambda: Rule40EVSStrategy(),
    "gp_multiple_reversion": lambda: GPMultipleReversionStrategy(),
    "dcf_gordon": lambda: DCFGordonStrategy(),
    "epv_ebit": lambda: EPVEBITStrategy(),
    "residual_income": lambda: ResidualIncomeStrategy(),



}

# Name -> required canonical metrics
_REQUIRED_METRICS: Dict[str, List[str]] = {
    "peter_lynch": ["eps_ttm", "eps_cagr_5y"],
    "psales_reversion": ["revenue_ttm", "shares_outstanding"],
    "ev_ebit_bridge": ["ebit_ttm", "net_debt", "shares_outstanding"],
    "fcf_yield": ["fcf_ttm", "shares_outstanding"],
    "rule40_evs": ["revenue_ttm", "net_debt", "shares_outstanding", "rule40_score"],
    "gp_multiple_reversion": ["gross_profit_ttm", "net_debt", "shares_outstanding"],
    "dcf_gordon": ["fcf_ttm", "shares_outstanding", "net_debt", "eps_cagr_5y"],  # eps_cagr_5y optional but helpful
    "epv_ebit": ["ebit_ttm", "net_debt", "shares_outstanding"],
    "residual_income": ["eps_ttm", "book_value_per_share", "eps_cagr_5y"],



}

# Name -> default hyperparameters (optional; you can override at runtime)
_DEFAULT_HYPERPARAMS: Dict[str, Dict[str, float]] = {
    "peter_lynch": {
        "min_growth_pe": 5.0,
        "max_growth_pe": 35.0,
        "negative_growth_pe": 5.0,
    },
    "psales_reversion": {
        "target_ps": 3.0,
        "min_ps_fair": 0.3,
        "max_ps_fair": 8.0,
    },
    "ev_ebit_bridge": {
        "target_ev_ebit": 12.0,
        "min_ev_ebit": 6.0,
        "max_ev_ebit": 20.0,
    },
    "fcf_yield": {
        "target_fcf_yield": 0.065,
        "min_fcf_yield": 0.02,
        "max_fcf_yield": 0.12,
    },
    "rule40_evs": {
        "evs_low": 2.0,
        "evs_mid": 4.0,
        "evs_high": 6.0,
        "min_evs": 0.5,
        "max_evs": 20.0,
    },
    "gp_multiple_reversion": {
        "target_ev_gp": 12.0,
        "min_ev_gp": 6.0,
        "max_ev_gp": 20.0,
    },
        "dcf_gordon": {
        "dcf_years": 5,
        "dcf_discount_rate": 0.10,
        "dcf_terminal_growth": 0.03,
        # "dcf_growth_rate": None,  # optional explicit override; if absent uses eps_cagr_5y
    },
        "epv_ebit": {
        "epv_tax_rate": 0.21,
        "epv_cost_of_capital": 0.10,
        "epv_adjustment_factor": 1.0,
    },
        "residual_income": {
        "ri_years": 5,
        "ri_discount_rate": 0.10,
        "ri_terminal_growth": 0.03,
        "ri_payout_ratio": 0.30,
        # "ri_eps_growth_rate": None,  # optional explicit override
    },



}

# Enabled strategies (edit defaults as you like).
# You can also switch this at runtime via set_enabled_strategy_names([...]).
_ENABLED_STRATEGIES: List[str] = [
    "peter_lynch",
    "psales_reversion",
    "ev_ebit_bridge",
    "fcf_yield",
    # "rule40_evs",               # enable if you can supply rule40_score
    "gp_multiple_reversion",
    "dcf_gordon",
    "epv_ebit",
    "residual_income",
]

# ---------------------------------------------------------------------------
# Public API

def list_all_strategy_names() -> List[str]:
    """All strategies registered, regardless of enabled state."""
    return list(_STRATEGY_FACTORIES.keys())


def get_enabled_strategy_names() -> List[str]:
    """Return the list of currently enabled strategies (order preserved)."""
    return list(_ENABLED_STRATEGIES)


def set_enabled_strategy_names(names: Sequence[str]) -> None:
    """Set the enabled strategy list; validates names."""
    for n in names:
        if n not in _STRATEGY_FACTORIES:
            raise KeyError(f"Unknown strategy: {n}")
    # Preserve order given by caller
    global _ENABLED_STRATEGIES
    _ENABLED_STRATEGIES = list(names)


def get_strategy_factory(name: str) -> Callable[[], Strategy]:
    """Return a factory that constructs the given strategy."""
    if name not in _STRATEGY_FACTORIES:
        raise KeyError(f"Unknown strategy: {name}")
    return _STRATEGY_FACTORIES[name]


def get_required_metrics(name: str) -> List[str]:
    """Return the list of canonical metric keys required by the strategy."""
    if name not in _REQUIRED_METRICS:
        raise KeyError(f"Unknown strategy: {name}")
    return list(_REQUIRED_METRICS[name])


def get_default_hyperparams(name: str) -> Dict[str, float]:
    """Return default hyperparameters (may be empty dict)."""
    return dict(_DEFAULT_HYPERPARAMS.get(name, {}))
