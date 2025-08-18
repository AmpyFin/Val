# tests/test_yf_adapters_smoke.py
import math
import pytest

from adapters.current_price_adapter.yfinance_current_price_adapter import YFinanceCurrentPriceAdapter
from adapters.eps_adapter.yfinance_eps_ttm_adapter import YFinanceEPSTTMAdapter
from adapters.revenue_last_quarter_adapter.yfinance_revenue_lq_adapter import YFinanceRevenueLastQuarterAdapter
from adapters.growth_adapter.yfinance_eps_cagr5_adapter import YFinanceEPSCAGR5Adapter
from adapters.shares_outstanding_adapter.yfinance_shares_outstanding_adapter import YFinanceSharesOutstandingAdapter
from adapters.revenue_ttm_adapter.yfinance_revenue_ttm_adapter import YFinanceRevenueTTMAdapter
from adapters.ebit_ttm_adapter.yfinance_ebit_ttm_adapter import YFinanceEBITTTMAdapter
from adapters.gross_profit_ttm_adapter.yfinance_gross_profit_ttm_adapter import YFinanceGrossProfitTTMAdapter
from adapters.fcf_ttm_adapter.yfinance_fcf_ttm_adapter import YFinanceFCFTTMAdapter
from adapters.net_debt_adapter.yfinance_net_debt_adapter import YFinanceNetDebtAdapter

def _is_num(x):
    return isinstance(x, (int, float)) and not math.isnan(float(x))

@pytest.mark.integration
def test_current_price(one_ticker):
    val = YFinanceCurrentPriceAdapter().fetch(one_ticker)
    assert _is_num(val) and val > 0

@pytest.mark.integration
def test_eps_ttm(one_ticker):
    val = YFinanceEPSTTMAdapter().fetch(one_ticker)
    assert _is_num(val)  # may be negative for some tickers; just numeric

@pytest.mark.integration
def test_revenue_last_quarter(one_ticker):
    val = YFinanceRevenueLastQuarterAdapter().fetch(one_ticker)
    assert _is_num(val) and val > 0

@pytest.mark.integration
def test_eps_cagr5(one_ticker):
    val = YFinanceEPSCAGR5Adapter().fetch(one_ticker)
    assert _is_num(val)  # CAGR can be small or large; numeric check only

@pytest.mark.integration
def test_shares_outstanding(one_ticker):
    val = YFinanceSharesOutstandingAdapter().fetch(one_ticker)
    assert _is_num(val) and val > 0

@pytest.mark.integration
def test_revenue_ttm(one_ticker):
    val = YFinanceRevenueTTMAdapter().fetch(one_ticker)
    assert _is_num(val) and val > 0

@pytest.mark.integration
def test_ebit_ttm(one_ticker):
    val = YFinanceEBITTTMAdapter().fetch(one_ticker)
    assert _is_num(val)  # typically >0 but avoid brittle assertion

@pytest.mark.integration
def test_gross_profit_ttm(one_ticker):
    val = YFinanceGrossProfitTTMAdapter().fetch(one_ticker)
    assert _is_num(val) and val > 0

@pytest.mark.integration
def test_fcf_ttm(one_ticker):
    val = YFinanceFCFTTMAdapter().fetch(one_ticker)
    assert _is_num(val)  # may be negative, so just numeric

@pytest.mark.integration
def test_net_debt(one_ticker):
    val = YFinanceNetDebtAdapter().fetch(one_ticker)
    assert _is_num(val)  # can be negative (net cash)
