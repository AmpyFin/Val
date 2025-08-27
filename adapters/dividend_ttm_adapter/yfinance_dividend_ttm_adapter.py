from __future__ import annotations

from typing import Any, Optional

import yfinance as yf

from adapters.adapter import MetricAdapter, DataNotAvailable, retry_on_failure
from adapters.yf_session import get_simple_session

def _to_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        f = float(x)
        if f != f:
            return None
        return f
    except Exception:
        return None


class YFinanceDividendTTMAdapter(MetricAdapter):
    """
    Dividend per share, trailing 12 months, via yfinance.
    We use `Ticker.dividends` series and sum the last 4 quarters (or 12 months).
    """

    def __init__(self) -> None:
        self._name = "yfinance_dividend_ttm"

    def get_name(self) -> str:
        return self._name

    @retry_on_failure(max_retries=2, delay=0.5)
    def fetch(self, ticker: str) -> float:
        tk = ticker.upper()
        try:
            session = get_simple_session()
            t = yf.Ticker(tk, session=session)
            s = t.dividends
            if s is None or s.empty:
                raise DataNotAvailable(f"{self._name}: no dividends series for {tk}")
            # Sum last ~12 months
            s = s.sort_index()
            # If monthly data isn't uniform, take last 4 payments as an approximation to TTM
            ttm = float(s.tail(4).sum())
            if ttm <= 0:
                raise DataNotAvailable(f"{self._name}: zero TTM dividends for {tk}")
            return ttm
        except DataNotAvailable:
            raise
        except Exception as exc:
            raise DataNotAvailable(f"{self._name}: failure for {tk}") from exc
