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
from strategies.ddm_two_stage import DDMTwoStageStrategy
from strategies.graham_number import GrahamNumberStrategy
from strategies.justified_pb_roe import JustifiedPBROEStrategy
from strategies.justified_pe_roe import JustifiedPEROEStrategy
from strategies.dcf_fcff_three_stage import DCF_FCFF_ThreeStage
from strategies.ev_ebitda_reversion import EVEbitdaReversionStrategy
from strategies.ev_sales_reversion import EVSalesReversionStrategy
from strategies.hmodel_dividend import HModelDividendStrategy
from strategies.pvgo import PVGOStrategy
from strategies.value_driver_roic import ValueDriverROICStrategy
from strategies.intangible_residual_income import IntangibleResidualIncomeStrategy
from strategies.economic_value_added import EconomicValueAddedStrategy
from strategies.saas_growth_evs_regression import SAASGrowthEVSRegressionStrategy



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
    "ddm_two_stage": lambda: DDMTwoStageStrategy(),
    "graham_number": lambda: GrahamNumberStrategy(),
    "justified_pb_roe": lambda: JustifiedPBROEStrategy(),
    "justified_pe_roe": lambda: JustifiedPEROEStrategy(),
    "dcf_fcff_three_stage": lambda: DCF_FCFF_ThreeStage(),
    "ev_ebitda_reversion": lambda: EVEbitdaReversionStrategy(),
    "ev_sales_reversion":  lambda: EVSalesReversionStrategy(),
    "hmodel_dividend": lambda: HModelDividendStrategy(),
    "pvgo": lambda: PVGOStrategy(),
    "value_driver_roic": lambda: ValueDriverROICStrategy(),
    "intangible_residual_income": lambda: IntangibleResidualIncomeStrategy(),
    "economic_value_added": lambda: EconomicValueAddedStrategy(),
    "saas_growth_evs_regression": lambda: SAASGrowthEVSRegressionStrategy(),


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
    "ddm_two_stage": ["dividend_ttm", "eps_cagr_5y"],
    "graham_number": ["eps_ttm", "book_value_per_share"],
    "justified_pb_roe": ["eps_ttm", "book_value_per_share", "dividend_ttm", "eps_cagr_5y"],
    "justified_pe_roe": ["eps_ttm", "book_value_per_share", "dividend_ttm"],
    "dcf_fcff_three_stage": ["revenue_ttm", "ebit_ttm", "shares_outstanding", "net_debt", "eps_cagr_5y"],
        "ev_ebitda_reversion": [
        "shares_outstanding", "net_debt",
        "ebitda_ttm",          # preferred
        "ebit_ttm", "da_ttm",  # fallback path (EBIT + D&A)
        "revenue_ttm",         # last-resort D&A estimate if da_ttm missing
    ],
    "ev_sales_reversion": [
        "revenue_ttm", "net_debt", "shares_outstanding",
        "gross_profit_ttm",  # optional for GM adjustment
    ],
    "hmodel_dividend": ["dividend_ttm", "eps_cagr_5y"],
    "pvgo": ["eps_ttm", "book_value_per_share", "dividend_ttm"],
    "value_driver_roic": [
        "revenue_ttm", "ebit_ttm", "shares_outstanding", "net_debt",
        "book_value_per_share", "eps_cagr_5y",
    ],
    "intangible_residual_income": [
        "eps_ttm", "book_value_per_share", "shares_outstanding",
        "rd_ttm", "sga_ttm", "dividend_ttm", "eps_cagr_5y",
    ],
    "economic_value_added": [
        "ebit_ttm", "shares_outstanding", "book_value_per_share", "net_debt",
        "eps_cagr_5y",  # used for g_start fallback
    ],
    "saas_growth_evs_regression": [
        "revenue_ttm", "shares_outstanding", "net_debt",
        "gross_profit_ttm",
        "rev_ttm_yoy_growth",     # primary growth signal
        "eps_cagr_5y",            # optional fallback growth signal
    ],



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
        "ddm_two_stage": {
        "ddm_high_years": 5,
        "ddm_discount_rate": 0.09,
        "ddm_terminal_growth": 0.02,
        # "ddm_high_growth_rate": None,  # optional explicit override
    },
        "graham_number": {
        "graham_pe_cap": 15.0,
        "graham_pb_cap": 1.5,
        # "graham_multiplier": None,  # optional override of pe_cap*pb_cap
    },
        "justified_pb_roe": {
        "jpbr_discount_rate": 0.10,
        # "jpbr_growth_rate": None,  # optional explicit override
    },
        "justified_pe_roe": {
        "jpe_discount_rate": 0.10,
        "jpe_default_payout": 0.30,
        "jpe_floor_payout": 0.05,
        "jpe_use_forward_eps": True,
        "jpe_max_long_run_g": 0.12,
        # "jpe_retention_ratio": None,   # optional explicit override
    },
        "dcf_fcff_three_stage": {
        "dcf_wacc": 0.10,
        "dcf_tax_rate": 0.21,
        "dcf_sales_to_capital": 3.0,  # More conservative (was 2.5)
        "dcf_stage1_years": 5,
        "dcf_stage2_years": 5,
        # "dcf_g_short": None,         # optional; falls back to eps_cagr_5y or 0.08
        "dcf_g_terminal": 0.025,     # Slightly higher terminal growth (was 0.02)
        # "dcf_target_ebit_margin": None,  # optional; hold current margin if None
        "dcf_allow_negative_reinvestment": True,  # Allow some divestment (was False)
    },
        "ev_ebitda_reversion": {
        "ev_ebitda_target_multiple": 10.0,  # override per sector if desired
        # If ebitda_ttm & da_ttm are missing, you can estimate D&A as % of revenue:
        "ev_ebitda_da_pct_of_revenue": 0.04,  # 4% fallback; set None to disable
    },
    "ev_sales_reversion": {
        "evs_target_multiple": 3.0,          # override per sector if desired
        "evs_gm_adjust_enabled": False,      # True to scale multiple by GM/ref
        "evs_ref_gm": 0.70,
        "evs_min_multiple": 0.5,
        "evs_max_multiple": 15.0,
    },
        "hmodel_dividend": {
        "h_discount_rate": 0.10,
        "h_long_run_growth": 0.02,
        # "h_short_run_growth": None,  # optional override; else uses eps_cagr_5y or 0.10
        "h_fade_years": 8,
    },
        "pvgo": {
        "pvgo_discount_rate": 0.12,    # Increased from 0.10 to handle high-growth companies
        "pvgo_default_payout": 0.30,
        "pvgo_floor_payout": 0.05,
        "pvgo_use_forward_eps": True,
        "pvgo_cap_roe": 0.35,
        "pvgo_cap_g": 0.10,            # Reduced from 0.12 to be more conservative
    },
    "value_driver_roic": {
        "vdr_wacc": 0.10,
        "vdr_tax_rate": 0.21,
        "vdr_stage_years": 8,
        # "vdr_g_start": None,            # optional; falls back to eps_cagr_5y or 0.12
        "vdr_g_terminal": 0.02,
        # "vdr_roic_start": None,         # optional override
        "vdr_roic_terminal": 0.12,
        # "vdr_ic_override": None,        # optional override
        # "vdr_eps_cagr_fallback": None,  # optional
    },
    "intangible_residual_income": {
        "iri_discount_rate": 0.10,
        "iri_horizon_years": 8,
        "iri_terminal_growth": 0.02,
        # "iri_eps_growth": None,         # optional; falls back to eps_cagr_5y or 0.10
        "iri_div_payout_floor": 0.10,
        "rd_life_years": 5,
        "brand_pct_of_sga": 0.30,
        "brand_life_years": 5,
    },
    "economic_value_added": {
        "eva_wacc": 0.10,
        "eva_tax_rate": 0.21,
        "eva_horizon_years": 8,
        # "eva_g_capital_start": None,   # optional; falls back to eps_cagr_5y or 0.10
        "eva_g_terminal": 0.02,
        # "eva_roic_start": None,        # optional
        "eva_roic_terminal": 0.12,
    },
    "saas_growth_evs_regression": {
        "sg_base_multiple": 3.0,
        "sg_beta_growth": 8.0,
        "sg_beta_gm": 3.0,
        "sg_gm_ref": 0.70,
        "sg_beta_rule40": 2.0,
        "sg_min_multiple": 0.5,
        "sg_max_multiple": 25.0,
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
    # "ddm_two_stage", # Was not working well - valued NVDA below $1 because of low dividends
    "graham_number",
    "justified_pb_roe",
    "justified_pe_roe",
    "dcf_fcff_three_stage",
    "ev_ebitda_reversion",
    "ev_sales_reversion",
    "hmodel_dividend",
    "pvgo",
    "value_driver_roic",
    "intangible_residual_income",
    "economic_value_added",
    "saas_growth_evs_regression",


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
