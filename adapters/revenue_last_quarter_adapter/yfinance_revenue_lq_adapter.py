# adapters/revenue_last_quarter_adapter/yfinance_revenue_lq_adapter.py
from __future__ import annotations

from typing import Optional, Any

import pandas as pd
import yfinance as yf

from adapters.adapter import MetricAdapter, DataNotAvailable, retry_on_failure
from adapters.yf_session import get_simple_session


class YFinanceRevenueLastQuarterAdapter(MetricAdapter):
    """
    Attempts to read last quarter revenue via yfinance quarterly financials.

    Strategy:
      - Try t.quarterly_financials (DataFrame: rows like 'Total Revenue', columns are quarter end dates)
      - Pick the most recent non-null value among common row labels.

    Returns revenue as float (USD).
    """

    def __init__(self) -> None:
        self._name = "yfinance_revenue_last_quarter"

    def get_name(self) -> str:
        return self._name

    def _coerce(self, v: Optional[Any]) -> Optional[float]:
        try:
            if v is None:
                return None
            f = float(v)
            if f != f:  # NaN
                return None
            return f
        except Exception:
            return None

    @retry_on_failure(max_retries=3, delay=0.5)
    def fetch(self, ticker: str) -> float:
        try:
            session = get_simple_session()
            t = yf.Ticker(ticker, session=session)

            df = None
            # Primary: quarterly_financials (older yfinance)
            try:
                df = t.quarterly_financials  # type: ignore[attr-defined]
            except Exception:
                df = None

            # Validate DataFrame
            if df is None or not isinstance(df, pd.DataFrame) or df.empty:
                raise DataNotAvailable(f"{self._name}: quarterly financials unavailable for {ticker}")

            # Common labels observed across yfinance versions
            row_candidates = ["Total Revenue", "TotalRevenue", "Revenue", "totalRevenue"]
            row = None
            for lbl in row_candidates:
                if lbl in df.index:
                    row = df.loc[lbl]
                    break
            if row is None or row.empty:
                raise DataNotAvailable(f"{self._name}: revenue row not found for {ticker}")

            # Columns are quarter end dates; select most recent non-null
            s = row.dropna()
            if s.empty:
                raise DataNotAvailable(f"{self._name}: revenue series empty for {ticker}")

            # Some yfinance versions keep columns unsorted; sort by column label where possible
            try:
                s = s.sort_index(ascending=False)
            except Exception:
                pass

            val = self._coerce(s.iloc[0])
            if val is None:
                raise DataNotAvailable(f"{self._name}: no usable revenue value for {ticker}")
            return val

        except DataNotAvailable:
            raise
        except Exception as exc:
            raise DataNotAvailable(f"{self._name}: failed to fetch last quarter revenue for {ticker}") from exc
