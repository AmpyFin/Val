# adapters/da_ttm_adapter/yfinance_da_ttm_adapter.py
from __future__ import annotations

from typing import Any, Optional

import pandas as pd
import yfinance as yf

from adapters.adapter import MetricAdapter, DataNotAvailable, retry_on_failure
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


class YFinanceDATTMAdapter(MetricAdapter):
    """
    Computes Depreciation & Amortization TTM by summing the last 4 quarterly values via yfinance.
    
    Strategy:
      - Use t.quarterly_financials or t.quarterly_cashflow DataFrame
      - Look for various D&A related labels
      - Sum up to 4 most recent non-null values
      - Fallback to estimated 4% of revenue if no D&A data found
    """

    def __init__(self) -> None:
        self._name = "yfinance_da_ttm"

    def get_name(self) -> str:
        return self._name

    @retry_on_failure(max_retries=3, delay=0.5)
    def fetch(self, ticker: str) -> float:
        try:
            session = get_simple_session()
            t = yf.Ticker(ticker, session=session)
            
            # Try quarterly financials first
            df: Optional[pd.DataFrame] = None
            try:
                df = t.quarterly_financials  # type: ignore[attr-defined]
            except Exception:
                pass

            # Try quarterly cashflow as backup
            if df is None or df.empty:
                try:
                    df = t.quarterly_cashflow  # type: ignore[attr-defined]
                except Exception:
                    pass

            if df is None or not isinstance(df, pd.DataFrame) or df.empty:
                raise DataNotAvailable(f"{self._name}: quarterly financials/cashflow unavailable for {ticker}")

            # Look for D&A in various forms
            da_candidates = [
                "Depreciation", "DepreciationAndAmortization", "Depreciation And Amortization",
                "Depreciation & Amortization", "D&A", "DA", "Amortization", "Depreciation Amortization"
            ]
            
            da_row = None
            for lbl in da_candidates:
                if lbl in df.index:
                    da_row = df.loc[lbl]
                    break

            if da_row is not None and not da_row.empty:
                s = da_row.dropna()
                if not s.empty:
                    try:
                        s = s.sort_index(ascending=False)
                    except Exception:
                        pass
                    
                    vals = []
                    for v in s.tolist():
                        cv = _f(v)
                        if cv is not None:
                            vals.append(abs(cv))  # D&A is often negative in cash flow, make positive
                        if len(vals) == 4:
                            break
                    
                    if vals:
                        return float(sum(vals))

            # Fallback: estimate D&A as 4% of revenue
            revenue_candidates = ["Revenue", "Total Revenue", "Net Sales"]
            revenue_row = None
            for lbl in revenue_candidates:
                if lbl in df.index:
                    revenue_row = df.loc[lbl]
                    break
            
            if revenue_row is not None and not revenue_row.empty:
                s = revenue_row.dropna()
                if not s.empty:
                    try:
                        s = s.sort_index(ascending=False)
                    except Exception:
                        pass
                    
                    vals = []
                    for v in s.tolist():
                        cv = _f(v)
                        if cv is not None:
                            # Estimate D&A as 4% of revenue
                            vals.append(cv * 0.04)
                        if len(vals) == 4:
                            break
                    
                    if vals:
                        return float(sum(vals))

            raise DataNotAvailable(f"{self._name}: could not compute D&A TTM for {ticker}")

        except DataNotAvailable:
            raise
        except Exception as exc:
            raise DataNotAvailable(f"{self._name}: failed to fetch D&A TTM for {ticker}") from exc
