# adapters/current_price_adapter/yfinance_current_price_adapter.py
from __future__ import annotations

import math
from typing import Any, Optional

import yfinance as yf

from adapters.adapter import MetricAdapter, DataNotAvailable, retry_on_rate_limit
from adapters.yf_session import get_simple_session


class YFinanceCurrentPriceAdapter(MetricAdapter):
    """
    Gets the latest price using yfinance.

    Notes:
      - Tries fast_info first (very quick), then falls back to 1d history close.
      - Returns a float price; raises DataNotAvailable on failure.
    """

    def __init__(self) -> None:
        self._name = "yfinance_current_price"

    def get_name(self) -> str:
        return self._name

    def _coerce_price(self, val: Optional[Any]) -> Optional[float]:
        try:
            if val is None:
                return None
            f = float(val)
            if math.isnan(f) or f <= 0:
                return None
            return f
        except Exception:
            return None

    @retry_on_rate_limit(max_retries=3, base_delay=5.0)
    def fetch(self, ticker: str) -> float:
        try:
            session = get_simple_session()
            t = yf.Ticker(ticker, session=session)

            # 1) Try fast_info
            price = None
            fi = getattr(t, "fast_info", None)
            if fi:
                # different yfinance versions expose different keys
                for key in ("last_price", "lastPrice", "last_trade_price", "lastTradePrice"):
                    val = fi.get(key) if hasattr(fi, "get") else None
                    price = self._coerce_price(val)
                    if price is not None:
                        return price

            # 2) Fallback: last close from daily history
            hist = t.history(period="1d", auto_adjust=False)
            if hist is not None and not hist.empty and "Close" in hist.columns:
                price = self._coerce_price(hist["Close"].iloc[-1])
                if price is not None:
                    return price

            raise DataNotAvailable(f"{self._name}: no usable price for {ticker}")

        except DataNotAvailable:
            raise
        except Exception as exc:
            raise DataNotAvailable(f"{self._name}: failed to fetch price for {ticker}") from exc
