# adapters/ebitda_ttm_adapter/yfinance_ebitda_ttm_adapter.py
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


class YFinanceEBITDATTMAdapter(MetricAdapter):
    """
    Computes EBITDA TTM by trying multiple approaches via yfinance:
    
    1. Direct EBITDA from quarterly_financials if available
    2. EBIT + D&A if both are available  
    3. EBIT + estimated D&A (4% of revenue as fallback)
    
    Strategy:
      - Use t.quarterly_financials DataFrame
      - Look for 'EBITDA', 'Ebitda' rows first
      - Fallback to 'EBIT' + 'Depreciation' or estimated D&A
      - Sum up to 4 most recent non-null values
    """

    def __init__(self) -> None:
        self._name = "yfinance_ebitda_ttm"

    def get_name(self) -> str:
        return self._name

    @retry_on_failure(max_retries=3, delay=0.5)
    def fetch(self, ticker: str) -> float:
        try:
            session = get_simple_session()
            t = yf.Ticker(ticker, session=session)
            df: Optional[pd.DataFrame] = None

            try:
                df = t.quarterly_financials  # type: ignore[attr-defined]
            except Exception:
                df = None

            if df is None or not isinstance(df, pd.DataFrame) or df.empty:
                raise DataNotAvailable(f"{self._name}: quarterly financials unavailable for {ticker}")

            # Method 1: Try direct EBITDA
            ebitda_candidates = ["EBITDA", "Ebitda", "EBITDA TTM"]
            ebitda_row = None
            for lbl in ebitda_candidates:
                if lbl in df.index:
                    ebitda_row = df.loc[lbl]
                    break
            
            if ebitda_row is not None and not ebitda_row.empty:
                s = ebitda_row.dropna()
                if not s.empty:
                    try:
                        s = s.sort_index(ascending=False)
                    except Exception:
                        pass
                    
                    vals = []
                    for v in s.tolist():
                        cv = _f(v)
                        if cv is not None:
                            vals.append(cv)
                        if len(vals) == 4:
                            break
                    
                    if vals:
                        return float(sum(vals))

            # Method 2: Try EBIT + D&A
            ebit_candidates = ["EBIT", "Ebit", "Operating Income", "OperatingIncome"]
            ebit_row = None
            for lbl in ebit_candidates:
                if lbl in df.index:
                    ebit_row = df.loc[lbl]
                    break

            da_candidates = ["Depreciation", "DepreciationAndAmortization", "Depreciation And Amortization"]
            da_row = None  
            for lbl in da_candidates:
                if lbl in df.index:
                    da_row = df.loc[lbl]
                    break

            if ebit_row is not None and da_row is not None:
                ebit_s = ebit_row.dropna()
                da_s = da_row.dropna()
                
                if not ebit_s.empty and not da_s.empty:
                    # Align periods and sum
                    try:
                        ebit_s = ebit_s.sort_index(ascending=False)
                        da_s = da_s.sort_index(ascending=False)
                    except Exception:
                        pass
                    
                    vals = []
                    for i, (ebit_val, da_val) in enumerate(zip(ebit_s.tolist(), da_s.tolist())):
                        if i >= 4:
                            break
                        ebit_cv = _f(ebit_val)
                        da_cv = _f(da_val)
                        if ebit_cv is not None and da_cv is not None:
                            vals.append(ebit_cv + da_cv)
                        elif ebit_cv is not None:
                            vals.append(ebit_cv)  # Use EBIT even without D&A
                    
                    if vals:
                        return float(sum(vals))

            # Method 3: EBIT + estimated D&A (4% of revenue fallback)
            if ebit_row is not None:
                revenue_candidates = ["Revenue", "Total Revenue", "Net Sales"]
                revenue_row = None
                for lbl in revenue_candidates:
                    if lbl in df.index:
                        revenue_row = df.loc[lbl]
                        break
                
                if revenue_row is not None:
                    ebit_s = ebit_row.dropna()
                    revenue_s = revenue_row.dropna()
                    
                    if not ebit_s.empty and not revenue_s.empty:
                        try:
                            ebit_s = ebit_s.sort_index(ascending=False)
                            revenue_s = revenue_s.sort_index(ascending=False)
                        except Exception:
                            pass
                        
                        vals = []
                        for i, (ebit_val, rev_val) in enumerate(zip(ebit_s.tolist(), revenue_s.tolist())):
                            if i >= 4:
                                break
                            ebit_cv = _f(ebit_val)
                            rev_cv = _f(rev_val)
                            if ebit_cv is not None and rev_cv is not None:
                                # Estimate D&A as 4% of revenue
                                estimated_da = rev_cv * 0.04
                                vals.append(ebit_cv + estimated_da)
                        
                        if vals:
                            return float(sum(vals))

            raise DataNotAvailable(f"{self._name}: could not compute EBITDA TTM for {ticker}")

        except DataNotAvailable:
            raise
        except Exception as exc:
            raise DataNotAvailable(f"{self._name}: failed to fetch EBITDA TTM for {ticker}") from exc
