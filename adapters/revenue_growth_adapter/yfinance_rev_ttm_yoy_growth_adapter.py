# adapters/revenue_growth_adapter/yfinance_rev_ttm_yoy_growth_adapter.py
from __future__ import annotations

from typing import Optional

import pandas as pd
import yfinance as yf

from adapters.adapter import MetricAdapter, DataNotAvailable, retry_on_failure
from adapters.yf_session import get_simple_session


class YFinanceRevTTMYoYGrowthAdapter(MetricAdapter):
    """
    Revenue TTM YoY Growth (decimal) via yfinance quarterly income statements.

    Method:
      - Pull quarterly income stmt, locate 'Total Revenue' (pretty=True labels).
      - Build TTM_current = sum(last 4 quarters), TTM_prev = sum(prior 4).
      - growth = (TTM_current / TTM_prev) - 1.0

    Returns float (e.g., 0.25 for +25%). Raises if insufficient quarters.
    """

    def __init__(self) -> None:
        self._name = "yfinance_rev_ttm_yoy_growth"

    def get_name(self) -> str:
        return self._name

    @retry_on_failure(max_retries=3, delay=0.6)
    def fetch(self, ticker: str) -> float:
        t = yf.Ticker(ticker.upper(), session=get_simple_session())

        # Prefer modern getter
        qdf: Optional[pd.DataFrame] = None
        try:
            qdf = t.get_income_stmt(freq="quarterly", pretty=True)
        except Exception:
            qdf = None

        if qdf is None or qdf.empty:
            # Fallback to legacy property
            try:
                qdf = t.quarterly_income_stmt  # type: ignore[attr-defined]
            except Exception:
                qdf = None

        if qdf is None or qdf.empty:
            raise DataNotAvailable(f"{self._name}: quarterly income statement unavailable for {ticker}")

        idx = {str(i).strip().lower(): i for i in qdf.index}
        rev_key = None
        for key in ("total revenue", "revenue", "sales", "totalrevenue"):
            if key in idx:
                rev_key = idx[key]
                break
        if rev_key is None:
            raise DataNotAvailable(f"{self._name}: Total Revenue row not found for {ticker}")

        ser = qdf.loc[rev_key]
        vals = pd.to_numeric(ser, errors="coerce").dropna()
        if len(vals) < 8:
            raise DataNotAvailable(f"{self._name}: need >= 8 quarterly revenue points for {ticker}")

        # ensure chronological ascending by index if possible
        try:
            dates = pd.to_datetime(vals.index, errors="coerce")
            order = dates.argsort()
            vals = vals.iloc[order]
        except Exception:
            vals = vals[::-1]  # best guess fallback

        ttm_curr = float(vals.tail(4).sum())
        ttm_prev = float(vals.tail(8).head(4).sum())
        if ttm_prev <= 0:
            raise DataNotAvailable(f"{self._name}: prior TTM revenue <= 0 for {ticker}")

        growth = (ttm_curr / ttm_prev) - 1.0
        return float(growth)
