# registries/adapter_registry.py
"""
AmpyFin — Val Model
Adapter Registry (selection-based, separate from pipeline)

Purpose:
- Import ALL concrete adapters but SELECT exactly ONE active provider per metric.
- Pipeline code should always call:
      get_active_metric_adapter("<metric>")
  and:
      get_active_tickers_adapter()
  so the chosen adapters are used consistently everywhere.

You can switch providers at runtime with:
    set_active_metric_provider("current_price", "polygon_current_price")
    set_active_tickers_source("wiki_spy_500_tickers")
"""

from __future__ import annotations

from typing import Callable, Dict, List

from adapters.adapter import MetricAdapter, TickersAdapter

# ---- Import concrete adapters (metrics) ----
# Current price
from adapters.current_price_adapter.yfinance_current_price_adapter import (
    YFinanceCurrentPriceAdapter,
)
from adapters.current_price_adapter.polygon_current_price_adapter import (
    PolygonCurrentPriceAdapter,
)

# EPS TTM
from adapters.eps_adapter.fmp_eps_ttm_adapter import FMPEPSTTMAdapter
from adapters.eps_adapter.yfinance_eps_ttm_adapter import YFinanceEPSTTMAdapter
from adapters.eps_adapter.finviz_eps_ttm_adapter import FinvizEPSTTMAdapter

# Revenue (last quarter)
from adapters.revenue_last_quarter_adapter.fmp_revenue_lq_adapter import (
    FMPRevenueLastQuarterAdapter,
)
from adapters.revenue_last_quarter_adapter.yfinance_revenue_lq_adapter import (
    YFinanceRevenueLastQuarterAdapter,
)

# EPS CAGR 5Y
from adapters.growth_adapter.fmp_eps_cagr5_adapter import FMPEPSCAGR5Adapter
from adapters.growth_adapter.yfinance_eps_cagr5_adapter import (
    YFinanceEPSCAGR5Adapter,
)

# Shares outstanding
from adapters.shares_outstanding_adapter.fmp_shares_outstanding_adapter import (
    FMPSharesOutstandingAdapter,
)
from adapters.shares_outstanding_adapter.yfinance_shares_outstanding_adapter import (
    YFinanceSharesOutstandingAdapter,
)

# Revenue TTM
from adapters.revenue_ttm_adapter.fmp_revenue_ttm_adapter import (
    FMPRevenueTTMAdapter,
)
from adapters.revenue_ttm_adapter.yfinance_revenue_ttm_adapter import (
    YFinanceRevenueTTMAdapter,
)

# EBIT TTM
from adapters.ebit_ttm_adapter.fmp_ebit_ttm_adapter import FMPEBITTTMAdapter
from adapters.ebit_ttm_adapter.yfinance_ebit_ttm_adapter import (
    YFinanceEBITTTMAdapter,
)

# Gross Profit TTM
from adapters.gross_profit_ttm_adapter.fmp_gross_profit_ttm_adapter import (
    FMPGrossProfitTTMAdapter,
)
from adapters.gross_profit_ttm_adapter.yfinance_gross_profit_ttm_adapter import (
    YFinanceGrossProfitTTMAdapter,
)

# FCF TTM
from adapters.fcf_ttm_adapter.fmp_fcf_ttm_adapter import FMPFCFTTMAdapter
from adapters.fcf_ttm_adapter.yfinance_fcf_ttm_adapter import (
    YFinanceFCFTTMAdapter,
)

# Net Debt
from adapters.net_debt_adapter.fmp_net_debt_adapter import FMPNetDebtAdapter
from adapters.net_debt_adapter.yfinance_net_debt_adapter import (
    YFinanceNetDebtAdapter,
)

# ---- Import concrete tickers sources ----
from adapters.tickers_adapter.list_static_tickers_adapter import (
    ListStaticTickersAdapter,
)
from adapters.tickers_adapter.wiki_spy_500_tickers_adapter import (
    WikiSPY500TickersAdapter,
)
from adapters.tickers_adapter.wiki_ndaq_100_tickers_adapter import (
    WikiNDAQ100TickersAdapter,
)
from adapters.tickers_adapter.combined_spy_ndaq_tickers_adapter import (
    CombinedSPYNDAQTickersAdapter,
)
from adapters.book_value_per_share_adapter.yfinance_bvps_adapter import YFinanceBVPSAdapter
from adapters.book_value_per_share_adapter.fmp_bvps_adapter import FMPBVPSAdapter

from adapters.dividend_ttm_adapter.yfinance_dividend_ttm_adapter import YFinanceDividendTTMAdapter
from adapters.dividend_ttm_adapter.fmp_dividend_ttm_adapter import FMPDividendTTMAdapter


# ---------------------------------------------------------------------------
# Registry maps:
#   _METRIC_PROVIDER_FACTORIES["metric"]["provider_name"] -> factory()
#   _ACTIVE_METRIC_PROVIDER["metric"] -> "provider_name"
# Same idea for tickers source.

_METRIC_PROVIDER_FACTORIES: Dict[str, Dict[str, Callable[[], MetricAdapter]]] = {
    "current_price": {
        "yfinance_current_price": lambda: YFinanceCurrentPriceAdapter(),
        "polygon_current_price": lambda: PolygonCurrentPriceAdapter(),
    },
    "eps_ttm": {
        "fmp_eps_ttm": lambda: FMPEPSTTMAdapter(),
        "yfinance_eps_ttm": lambda: YFinanceEPSTTMAdapter(),
        "finviz_eps_ttm": lambda: FinvizEPSTTMAdapter(),
    },
    "revenue_last_quarter": {
        "fmp_revenue_last_quarter": lambda: FMPRevenueLastQuarterAdapter(),
        "yfinance_revenue_last_quarter": lambda: YFinanceRevenueLastQuarterAdapter(),
    },
    "eps_cagr_5y": {
        "fmp_eps_cagr_5y": lambda: FMPEPSCAGR5Adapter(),
        "yfinance_eps_cagr_5y": lambda: YFinanceEPSCAGR5Adapter(),
    },
    "shares_outstanding": {
        "fmp_shares_outstanding": lambda: FMPSharesOutstandingAdapter(),
        "yfinance_shares_outstanding": lambda: YFinanceSharesOutstandingAdapter(),
    },
    "revenue_ttm": {
        "fmp_revenue_ttm": lambda: FMPRevenueTTMAdapter(),
        "yfinance_revenue_ttm": lambda: YFinanceRevenueTTMAdapter(),
    },
    "ebit_ttm": {
        "fmp_ebit_ttm": lambda: FMPEBITTTMAdapter(),
        "yfinance_ebit_ttm": lambda: YFinanceEBITTTMAdapter(),
    },
    "gross_profit_ttm": {
        "fmp_gross_profit_ttm": lambda: FMPGrossProfitTTMAdapter(),
        "yfinance_gross_profit_ttm": lambda: YFinanceGrossProfitTTMAdapter(),
    },
    "fcf_ttm": {
        "fmp_fcf_ttm": lambda: FMPFCFTTMAdapter(),
        "yfinance_fcf_ttm": lambda: YFinanceFCFTTMAdapter(),
    },
    "net_debt": {
        "fmp_net_debt": lambda: FMPNetDebtAdapter(),
        "yfinance_net_debt": lambda: YFinanceNetDebtAdapter(),
    },
    # "rule40_score": {}  # typically computed, not fetched directly
    "book_value_per_share": {
        "yfinance_book_value_per_share": lambda: YFinanceBVPSAdapter(),
        "fmp_book_value_per_share": lambda: FMPBVPSAdapter(),
    },
    "dividend_ttm": {
        "yfinance_dividend_ttm": lambda: YFinanceDividendTTMAdapter(),
        "fmp_dividend_ttm": lambda: FMPDividendTTMAdapter(),
    },

}

# ---- Active selections (defaults) ----
# As requested: use all yfinance metric providers and the custom list tickers source.
_ACTIVE_METRIC_PROVIDER: Dict[str, str] = {
    "current_price": "yfinance_current_price",
    "eps_ttm": "finviz_eps_ttm",
    "revenue_last_quarter": "yfinance_revenue_last_quarter",
    "eps_cagr_5y": "yfinance_eps_cagr_5y",
    "shares_outstanding": "yfinance_shares_outstanding",
    "revenue_ttm": "yfinance_revenue_ttm",
    "ebit_ttm": "yfinance_ebit_ttm",
    "gross_profit_ttm": "yfinance_gross_profit_ttm",
    "fcf_ttm": "yfinance_fcf_ttm",
    "net_debt": "yfinance_net_debt",
    "book_value_per_share": "yfinance_book_value_per_share",
    "dividend_ttm": "yfinance_dividend_ttm",


}

_TICKERS_PROVIDER_FACTORIES: Dict[str, Callable[[], TickersAdapter]] = {
    "list_static_tickers": lambda: ListStaticTickersAdapter(),
    "wiki_spy_500_tickers": lambda: WikiSPY500TickersAdapter(),
    "wiki_ndaq_100_tickers": lambda: WikiNDAQ100TickersAdapter(),
    "combined_spy_ndaq_tickers": lambda: CombinedSPYNDAQTickersAdapter(),
}

_ACTIVE_TICKERS_SOURCE: str = "wiki_ndaq_100_tickers"

# ---------------------------------------------------------------------------
# Helpers for metrics

def list_available_metrics() -> List[str]:
    return list(_METRIC_PROVIDER_FACTORIES.keys())


def get_metric_provider_names(metric: str) -> List[str]:
    return list(_METRIC_PROVIDER_FACTORIES.get(metric, {}).keys())


def get_active_metric_provider_name(metric: str) -> str:
    return _ACTIVE_METRIC_PROVIDER[metric]


def set_active_metric_provider(metric: str, provider_name: str) -> None:
    if metric not in _METRIC_PROVIDER_FACTORIES:
        raise KeyError(f"Unknown metric: {metric}")
    if provider_name not in _METRIC_PROVIDER_FACTORIES[metric]:
        raise KeyError(f"Unknown provider '{provider_name}' for metric '{metric}'")
    _ACTIVE_METRIC_PROVIDER[metric] = provider_name


def get_active_metric_adapter(metric: str) -> MetricAdapter:
    """Return an instance of the ACTIVE adapter for a metric."""
    provider_name = get_active_metric_provider_name(metric)
    factory = _METRIC_PROVIDER_FACTORIES[metric][provider_name]
    return factory()

# ---------------------------------------------------------------------------
# Helpers for tickers source

def list_tickers_sources() -> List[str]:
    return list(_TICKERS_PROVIDER_FACTORIES.keys())


def get_active_tickers_source_name() -> str:
    return _ACTIVE_TICKERS_SOURCE


def set_active_tickers_source(name: str) -> None:
    if name not in _TICKERS_PROVIDER_FACTORIES:
        raise KeyError(f"Unknown tickers source: {name}")
    global _ACTIVE_TICKERS_SOURCE
    _ACTIVE_TICKERS_SOURCE = name


def get_active_tickers_adapter() -> TickersAdapter:
    """Return an instance of the ACTIVE tickers adapter."""
    factory = _TICKERS_PROVIDER_FACTORIES[_ACTIVE_TICKERS_SOURCE]
    return factory()

