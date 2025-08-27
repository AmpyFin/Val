# adapters/shares_outstanding_adapter/yfinance_shares_outstanding_adapter.py
from __future__ import annotations

from typing import Any, Optional

import yfinance as yf

from adapters.adapter import MetricAdapter, DataNotAvailable, retry_on_failure
from adapters.yf_session import get_simple_session


class YFinanceSharesOutstandingAdapter(MetricAdapter):
    """
    Fetches total shares outstanding using yfinance.

    Strategy:
      - Prefer fast_info['shares_outstanding'] (newer yfinance).
      - Fallback to get_info()['sharesOutstanding'] or legacy .info['sharesOutstanding'].
      - Returns a positive float; raises DataNotAvailable on failure.
    """

    def __init__(self) -> None:
        self._name = "yfinance_shares_outstanding"

    def get_name(self) -> str:
        return self._name

    def _coerce(self, v: Optional[Any]) -> Optional[float]:
        try:
            if v is None:
                return None
            f = float(v)
            if f != f or f <= 0:  # NaN or non-positive
                return None
            return f
        except Exception:
            return None

    @retry_on_failure(max_retries=3, delay=0.5)
    def fetch(self, ticker: str) -> float:
        try:
            session = get_simple_session()
            t = yf.Ticker(ticker, session=session)

            # 1) fast_info (if present)
            fi = getattr(t, "fast_info", None)
            if fi is not None:
                for key in ("shares_outstanding", "sharesOutstanding", "float_shares_outstanding"):
                    try:
                        val = fi.get(key) if hasattr(fi, "get") else None
                    except Exception:
                        val = None
                    v = self._coerce(val)
                    if v is not None:
                        return v

            # 2) get_info() (preferred)
            info = None
            if hasattr(t, "get_info"):
                try:
                    info = t.get_info()
                except Exception:
                    info = None

            # 3) legacy .info
            if info is None:
                try:
                    info = t.info  # type: ignore[attr-defined]
                except Exception:
                    info = None

            if isinstance(info, dict):
                candidates = [
                    info.get("sharesOutstanding"),
                    info.get("SharesOutstanding"),
                ]
                for c in candidates:
                    v = self._coerce(c)
                    if v is not None:
                        return v

            raise DataNotAvailable(f"{self._name}: sharesOutstanding not available for {ticker}")

        except DataNotAvailable:
            raise
        except Exception as exc:
            raise DataNotAvailable(f"{self._name}: failed to fetch sharesOutstanding for {ticker}") from exc
