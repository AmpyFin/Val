# adapters/net_debt_adapter/yfinance_net_debt_adapter.py
from __future__ import annotations

from typing import Optional, Any

import pandas as pd
import yfinance as yf

from adapters.adapter import MetricAdapter, DataNotAvailable, retry_on_failure, retry_on_rate_limit
from adapters.yf_session import get_simple_session


def _f(v: Optional[Any]) -> Optional[float]:
    try:
        if v is None:
            return None
        x = float(v)
        if x != x:  # NaN
            return None
        return x
    except Exception:
        return None


class YFinanceNetDebtAdapter(MetricAdapter):
    """
    Estimates Net Debt from yfinance quarterly balance sheet with fallback to info fields.

    Strategy:
      - Primary: Use t.quarterly_balance_sheet (DataFrame with account rows).
      - Fallback: Use t.info fields for debt and cash data.
      - total_debt ≈ 'Total Debt' or sum of 'Long Term Debt' + 'Short Long Term Debt'/'Short Term Debt'
      - cash_and_sti ≈ 'Cash And Cash Equivalents And Short Term Investments'
                       or 'Cash And Cash Equivalents'
      - net_debt = total_debt - cash_and_sti  (can be negative if net cash)
    """

    def __init__(self) -> None:
        self._name = "yfinance_net_debt"

    def get_name(self) -> str:
        return self._name

    def _get_net_debt_from_info(self, t: yf.Ticker) -> Optional[float]:
        """Try to get net debt from info fields as fallback."""
        try:
            info = t.info  # type: ignore[attr-defined]
            
            if not isinstance(info, dict):
                return None

            # Try to get total debt
            total_debt = None
            for debt_field in ['totalDebt', 'totalDebtToEquity', 'debtToEquity']:
                if debt_field in info:
                    debt_val = _f(info[debt_field])
                    if debt_val is not None:
                        if debt_field == 'totalDebt':
                            total_debt = debt_val
                            break
                        elif debt_field in ['totalDebtToEquity', 'debtToEquity']:
                            # These are ratios, we'd need market cap to convert
                            # Skip for now as it's complex
                            continue

            # Try to get cash
            cash = None
            for cash_field in ['totalCash', 'cash', 'cashAndCashEquivalents']:
                if cash_field in info:
                    cash_val = _f(info[cash_field])
                    if cash_val is not None:
                        cash = cash_val
                        break

            # If we have either debt or cash, we can calculate net debt
            # Even if one is missing, we can assume it's 0
            if total_debt is not None or cash is not None:
                total_debt = total_debt or 0.0
                cash = cash or 0.0
                net_debt = total_debt - cash
                return float(net_debt)

            # Try alternative approach: look for debt-related fields
            # Some companies report debt in different fields
            debt_indicators = ['longTermDebt', 'shortTermDebt', 'totalDebt']
            total_debt_alt = 0.0
            
            for debt_field in debt_indicators:
                if debt_field in info:
                    debt_val = _f(info[debt_field])
                    if debt_val is not None:
                        total_debt_alt += debt_val

            # Try cash indicators
            cash_indicators = ['totalCash', 'cash', 'cashAndCashEquivalents', 'totalCashPerShare']
            cash_alt = 0.0
            
            for cash_field in cash_indicators:
                if cash_field in info:
                    cash_val = _f(info[cash_field])
                    if cash_val is not None:
                        cash_alt = cash_val
                        break

            if total_debt_alt > 0 or cash_alt > 0:
                net_debt = total_debt_alt - cash_alt
                return float(net_debt)

            return None
        except Exception:
            return None

    def _get_net_debt_from_balance_sheet(self, t: yf.Ticker) -> float:
        """Get net debt from quarterly balance sheet."""
        try:
            df: Optional[pd.DataFrame] = None
            try:
                df = t.quarterly_balance_sheet  # type: ignore[attr-defined]
            except Exception:
                df = None

            if df is None or not isinstance(df, pd.DataFrame) or df.empty:
                raise DataNotAvailable(f"{self._name}: quarterly balance sheet unavailable")

            # Get most recent column
            col = None
            try:
                # Columns are dates; take the last non-null column after sorting
                ordered_cols = list(df.columns)
                if not ordered_cols:
                    raise KeyError
                col = ordered_cols[0] if len(ordered_cols) == 1 else ordered_cols[-1]
            except Exception:
                # Fallback: take any column that exists
                if df.columns.size == 0:
                    raise DataNotAvailable(f"{self._name}: no columns in balance sheet")
                col = df.columns[-1]

            def row_val(*labels: str) -> Optional[float]:
                for lbl in labels:
                    if lbl in df.index and col in df.columns:
                        v = _f(df.at[lbl, col])
                        if v is not None:
                            return v
                return None

            # Compute total debt
            total_debt = row_val("Total Debt")
            if total_debt is None:
                ltd = row_val("Long Term Debt", "LongTermDebt")
                std = row_val("Short Long Term Debt", "ShortTermDebt", "Short Term Debt")
                total_debt = (ltd or 0.0) + (std or 0.0)

            # Compute cash & short-term investments
            cash_sti = row_val(
                "Cash And Cash Equivalents And Short Term Investments",
                "Cash And Short Term Investments",
            )
            if cash_sti is None:
                cash_sti = row_val("Cash And Cash Equivalents", "Cash")

            if total_debt is None and cash_sti is None:
                raise DataNotAvailable(f"{self._name}: could not derive net debt")

            total_debt = float(total_debt or 0.0)
            cash_sti = float(cash_sti or 0.0)
            net_debt = total_debt - cash_sti
            
            # If both values are 0, we probably couldn't find the data
            # But if we have at least one non-zero value, we can calculate net debt
            if total_debt == 0.0 and cash_sti == 0.0:
                raise DataNotAvailable(f"{self._name}: no debt or cash data found in balance sheet")
                
            return float(net_debt)

        except DataNotAvailable:
            raise
        except Exception as exc:
            raise DataNotAvailable(f"{self._name}: failed to compute net debt from balance sheet") from exc

    @retry_on_rate_limit(max_retries=3, base_delay=5.0)
    def fetch(self, ticker: str) -> float:
        try:
            session = get_simple_session()
            t = yf.Ticker(ticker, session=session)
            
            # First try: Get from balance sheet
            try:
                return self._get_net_debt_from_balance_sheet(t)
            except DataNotAvailable as e:
                # If balance sheet fails, try info fields as fallback
                net_debt_from_info = self._get_net_debt_from_info(t)
                if net_debt_from_info is not None:
                    return net_debt_from_info
                else:
                    # Re-raise the original error if fallback also fails
                    raise e

        except DataNotAvailable:
            raise
        except Exception as exc:
            raise DataNotAvailable(f"{self._name}: failed to compute net debt for {ticker}") from exc
