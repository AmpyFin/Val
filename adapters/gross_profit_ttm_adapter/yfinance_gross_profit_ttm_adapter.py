# adapters/gross_profit_ttm_adapter/yfinance_gross_profit_ttm_adapter.py
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


class YFinanceGrossProfitTTMAdapter(MetricAdapter):
    """
    Computes Gross Profit TTM by summing the last 4 quarterly 'Gross Profit' values via yfinance.

    Strategy:
      - Use t.quarterly_financials DataFrame.
      - Find a row labeled like 'Gross Profit' / 'GrossProfit'.
      - Sum up to the 4 most recent non-null values.
    """

    def __init__(self) -> None:
        self._name = "yfinance_gross_profit_ttm"

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

            row_candidates = ["Gross Profit", "GrossProfit"]
            row = None
            for lbl in row_candidates:
                if lbl in df.index:
                    row = df.loc[lbl]
                    break
            if row is None or row.empty:
                raise DataNotAvailable(f"{self._name}: gross profit row not found for {ticker}")

            s = row.dropna()
            if s.empty:
                raise DataNotAvailable(f"{self._name}: gross profit series empty for {ticker}")

            # Sort columns desc if sortable (newest first)
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

            if not vals:
                raise DataNotAvailable(f"{self._name}: no usable gross profit values for {ticker}")

            return float(sum(vals))

        except DataNotAvailable:
            raise
        except Exception as exc:
            raise DataNotAvailable(f"{self._name}: failed to compute gross profit TTM for {ticker}") from exc
