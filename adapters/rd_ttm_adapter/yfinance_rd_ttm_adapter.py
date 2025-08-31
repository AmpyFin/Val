# adapters/rd_ttm_adapter/yfinance_rd_ttm_adapter.py
from __future__ import annotations

from typing import Optional

import pandas as pd
import yfinance as yf

from adapters.adapter import MetricAdapter, DataNotAvailable, retry_on_failure
from adapters.yf_session import get_simple_session


def _sum_last_four(series: pd.Series) -> Optional[float]:
    try:
        ser = pd.to_numeric(series, errors="coerce").dropna()
        if ser.empty:
            return None
        return float(ser.tail(4).sum())
    except Exception:
        return None


class YFinanceRDTTMAdapter(MetricAdapter):
    """
    R&D expense TTM (total, NOT per share) via yfinance:
      - Try t.get_income_stmt(freq='trailing', pretty=True)['Research & Development']
      - Else sum last 4 quarters from 'quarterly' income statement
      - Else fall back to annual (approx TTM as last annual)
    Returns: float (currency units)
    """

    def __init__(self) -> None:
        self._name = "yfinance_rd_ttm"

    def get_name(self) -> str:
        return self._name

    @retry_on_failure(max_retries=3, delay=0.6)
    def fetch(self, ticker: str) -> float:
        t = yf.Ticker(ticker.upper(), session=get_simple_session())

        def extract(df: Optional[pd.DataFrame]) -> Optional[float]:
            if df is None or df.empty:
                return None
            idx = {str(i).strip().lower(): i for i in df.index}
            for key in ("research & development", "researchanddevelopment", "rnd", "research and development"):
                if key in idx:
                    ser = df.loc[idx[key]]
                    # If it's trailing, should be a 1-col series; coerce sum
                    val = pd.to_numeric(ser, errors="coerce").dropna()
                    if not val.empty:
                        # If quarterly, sum last 4
                        if df.columns.size > 1:
                            return _sum_last_four(ser)
                        # Single value
                        return float(val.iloc[-1])
            return None

        # Trailing
        try:
            df = t.get_income_stmt(freq="trailing", pretty=True)
            v = extract(df)
            if v is not None:
                return v
        except Exception:
            pass

        # Quarterly (sum last 4)
        try:
            dfq = t.get_income_stmt(freq="quarterly", pretty=True)
            v = extract(dfq)
            if v is not None:
                return v
        except Exception:
            pass

        # Annual (fallback)
        try:
            dfa = t.get_income_stmt(freq="yearly", pretty=True)
            if dfa is not None and not dfa.empty:
                idx = {str(i).strip().lower(): i for i in dfa.index}
                for key in ("research & development", "researchanddevelopment", "rnd", "research and development"):
                    if key in idx:
                        ser = dfa.loc[idx[key]]
                        val = pd.to_numeric(ser, errors="coerce").dropna()
                        if not val.empty:
                            return float(val.iloc[-1])
        except Exception:
            pass

        raise DataNotAvailable(f"{self._name}: R&D TTM unavailable for {ticker}")
