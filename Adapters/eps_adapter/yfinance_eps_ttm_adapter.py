# adapters/eps_adapter/yfinance_eps_ttm_adapter.py
from __future__ import annotations

from typing import Any, Optional

import pandas as pd
import yfinance as yf

from adapters.adapter import MetricAdapter, DataNotAvailable, retry_on_failure, retry_on_rate_limit
from adapters.yf_session import get_simple_session


def _coerce(v: Optional[Any]) -> Optional[float]:
    try:
        if v is None:
            return None
        f = float(v)
        if f != f:  # NaN
            return None
        return f
    except Exception:
        return None


class YFinanceEPSTTMAdapter(MetricAdapter):
    """
    Gets EPS TTM directly from yfinance info fields, with fallback to quarterly calculation.

    Strategy:
      - First try: Use t.info to get trailingEps or epsTrailingTwelveMonths.
      - Fallback: Calculate from quarterly earnings data (last 4 quarters).
      - Uses smart session management to handle rate limiting.

    Returns a float (USD per share).
    """

    def __init__(self) -> None:
        self._name = "yfinance_eps_ttm"

    def get_name(self) -> str:
        return self._name

    def _get_eps_from_info(self, t: yf.Ticker) -> Optional[float]:
        """Try to get EPS TTM from info fields."""
        try:
            info = t.info  # type: ignore[attr-defined]
            
            if not isinstance(info, dict):
                return None

            # Try to get trailing EPS directly
            trailing_eps = info.get('trailingEps')
            if trailing_eps is not None:
                val = _coerce(trailing_eps)
                if val is not None:
                    return float(val)
            
            # Try alternative field names
            eps_trailing = info.get('epsTrailingTwelveMonths')
            if eps_trailing is not None:
                val = _coerce(eps_trailing)
                if val is not None:
                    return float(val)
            
            return None
        except Exception:
            return None

    def _calculate_eps_from_quarterly(self, t: yf.Ticker) -> float:
        """Calculate EPS TTM from quarterly earnings data."""
        try:
            # Get quarterly income statement (replaces deprecated earnings)
            df: Optional[pd.DataFrame] = None
            try:
                df = t.quarterly_income_stmt  # type: ignore[attr-defined]
            except Exception:
                df = None

            if df is None or not isinstance(df, pd.DataFrame) or df.empty:
                raise DataNotAvailable(f"{self._name}: quarterly income statement unavailable for calculation")

            # Get the last 4 quarters (TTM)
            if len(df.columns) < 4:
                raise DataNotAvailable(f"{self._name}: insufficient quarterly data for TTM calculation")

            # Look for Net Income row
            net_income_row = None
            for row_name in ['Net Income', 'Net Income Common Stockholders']:
                if row_name in df.index:
                    net_income_row = row_name
                    break

            if net_income_row is None:
                raise DataNotAvailable(f"{self._name}: net income not found in income statement")

            # Sum the last 4 quarters of net income
            last_4_quarters = df.loc[net_income_row, df.columns[:4]]  # First 4 columns (most recent)
            total_earnings = last_4_quarters.sum()

            # Get shares outstanding for the most recent quarter
            shares_df: Optional[pd.DataFrame] = None
            try:
                shares_df = t.quarterly_balance_sheet  # type: ignore[attr-defined]
            except Exception:
                shares_df = None

            if shares_df is None or not isinstance(shares_df, pd.DataFrame) or shares_df.empty:
                # Fallback: try to get shares from info
                info = t.info  # type: ignore[attr-defined]
                if isinstance(info, dict):
                    shares = info.get('sharesOutstanding')
                    if shares is not None:
                        shares_outstanding = _coerce(shares)
                        if shares_outstanding is not None:
                            eps_ttm = total_earnings / shares_outstanding
                            return float(eps_ttm)
                
                raise DataNotAvailable(f"{self._name}: shares outstanding unavailable for EPS calculation")

            # Get shares outstanding from balance sheet
            shares_col = shares_df.columns[0]  # Most recent quarter
            shares_row = None
            
            # Try different possible row names for shares outstanding
            for row_name in ['Share Issued', 'Shares Outstanding', 'Common Stock Shares Outstanding']:
                if row_name in shares_df.index:
                    shares_row = _coerce(shares_df.at[row_name, shares_col])
                    if shares_row is not None:
                        break

            if shares_row is None:
                raise DataNotAvailable(f"{self._name}: shares outstanding not found in balance sheet")

            eps_ttm = total_earnings / shares_row
            return float(eps_ttm)

        except DataNotAvailable:
            raise
        except Exception as exc:
            raise DataNotAvailable(f"{self._name}: failed to calculate EPS from quarterly data") from exc

    @retry_on_rate_limit(max_retries=3, base_delay=5.0)
    def fetch(self, ticker: str) -> float:
        try:
            session = get_simple_session()
            t = yf.Ticker(ticker, session=session)
            
            # First try: Get EPS from info fields
            eps_from_info = self._get_eps_from_info(t)
            if eps_from_info is not None:
                return eps_from_info
            
            # Fallback: Calculate from quarterly data
            # Create a fresh session for quarterly data to avoid rate limiting
            fresh_session = get_simple_session()
            fresh_t = yf.Ticker(ticker, session=fresh_session)
            return self._calculate_eps_from_quarterly(fresh_t)

        except DataNotAvailable:
            raise
        except Exception as exc:
            raise DataNotAvailable(f"{self._name}: failed to compute EPS TTM for {ticker}") from exc
