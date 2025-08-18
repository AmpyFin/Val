# adapters/current_price_adapter/polygon_current_price_adapter.py
from __future__ import annotations

import os
import math
from typing import Any, Optional

import requests

# Load .env early if python-dotenv is available (non-fatal if missing)
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

from adapters.adapter import MetricAdapter, DataNotAvailable

HTTP_TIMEOUT = 12
HEADERS = {"User-Agent": "ampyfin-val-model/1.0 (+https://example.org)"}


class PolygonCurrentPriceAdapter(MetricAdapter):
    """
    Gets the most recent trade price from Polygon's snapshot endpoint.

    Requires:
      - POLYGON_API_KEY in environment (.env) loaded by python-dotenv.

    Endpoint (stocks snapshot):
      https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}

    Parsing:
      - We attempt multiple common fields (schema can drift):
        data["ticker"]["lastTrade"]["p"] or ["price"]
        data["ticker"]["lastQuote"]["p"] or ["price"]
        data["ticker"]["day"]["c"] (current day close so far)
    """

    def __init__(self) -> None:
        self._name = "polygon_current_price"

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

    def fetch(self, ticker: str) -> float:
        api_key = os.getenv("POLYGON_API_KEY")
        if not api_key:
            raise DataNotAvailable(f"{self._name}: missing POLYGON_API_KEY")

        url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers/{ticker.upper()}"
        try:
            resp = requests.get(url, params={"apiKey": api_key}, timeout=HTTP_TIMEOUT, headers=HEADERS)
            if resp.status_code != 200:
                raise DataNotAvailable(f"{self._name}: HTTP {resp.status_code} for {ticker}")

            data = resp.json()

            # Try several known locations for a recent price
            price_candidates = []

            try:
                price_candidates.append(data["ticker"]["lastTrade"].get("p"))
                price_candidates.append(data["ticker"]["lastTrade"].get("price"))
            except Exception:
                pass

            try:
                price_candidates.append(data["ticker"]["lastQuote"].get("p"))
                price_candidates.append(data["ticker"]["lastQuote"].get("price"))
            except Exception:
                pass

            try:
                price_candidates.append(data["ticker"]["day"].get("c"))  # today's running close
            except Exception:
                pass

            for cand in price_candidates:
                price = self._coerce_price(cand)
                if price is not None:
                    return price

            raise DataNotAvailable(f"{self._name}: no usable price fields for {ticker}")

        except DataNotAvailable:
            raise
        except Exception as exc:
            raise DataNotAvailable(f"{self._name}: failed to fetch price for {ticker}") from exc
