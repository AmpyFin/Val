# tests/test_registry_selection.py
import pytest

from registries.adapter_registry import (
    get_active_metric_provider_name,
    get_active_tickers_source_name,
    get_active_tickers_adapter,
)
from adapters.tickers_adapter.list_static_tickers_adapter import ListStaticTickersAdapter

def test_active_tickers_source_is_custom_list(static_tickers):
    assert get_active_tickers_source_name() == "list_static_tickers"
    adapter = get_active_tickers_adapter()
    assert isinstance(adapter, ListStaticTickersAdapter)
    lst = adapter.fetch()
    assert list(lst) == static_tickers  # exact match to spec

def test_active_metric_providers_are_yfinance():
    expected = {
        "current_price": "yfinance_current_price",
        "eps_ttm": "yfinance_eps_ttm",
        "revenue_last_quarter": "yfinance_revenue_last_quarter",
        "eps_cagr_5y": "yfinance_eps_cagr_5y",
        "shares_outstanding": "yfinance_shares_outstanding",
        "revenue_ttm": "yfinance_revenue_ttm",
        "ebit_ttm": "yfinance_ebit_ttm",
        "gross_profit_ttm": "yfinance_gross_profit_ttm",
        "fcf_ttm": "yfinance_fcf_ttm",
        "net_debt": "yfinance_net_debt",
    }
    for metric, provider in expected.items():
        assert get_active_metric_provider_name(metric) == provider
