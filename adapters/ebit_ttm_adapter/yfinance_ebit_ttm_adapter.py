# adapters/ebit_ttm_adapter/yfinance_ebit_ttm_adapter.py
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
        if x != x:
            return None
        return x
    except Exception:
        return None


class YFinanceEBITTTMAdapter(MetricAdapter):
    """
    Computes EBIT TTM by summing the last 4 quarterly EBIT values via yfinance.

    Strategy:
      - Use t.quarterly_financials DataFrame.
      - Prefer rows labeled 'EBIT' or 'Ebit'; fallback to 'Operating Income'.
      - Sum up to 4 most recent non-null values.
    """

    def __init__(self) -> None:
        self._name = "yfinance_ebit_ttm"

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

            row_candidates = ["EBIT", "Ebit", "Operating Income", "OperatingIncome"]
            row = None
            for lbl in row_candidates:
                if lbl in df.index:
                    row = df.loc[lbl]
                    break
            if row is None or row.empty:
                raise DataNotAvailable(f"{self._name}: EBIT/Operating Income row not found for {ticker}")

            s = row.dropna()
            if s.empty:
                raise DataNotAvailable(f"{self._name}: EBIT series empty for {ticker}")

            # Sort columns descending by label if possible (recent first)
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
                raise DataNotAvailable(f"{self._name}: no usable EBIT values for {ticker}")

            return float(sum(vals))

        except DataNotAvailable:
            raise
        except Exception as exc:
            raise DataNotAvailable(f"{self._name}: failed to compute EBIT TTM for {ticker}") from exc
