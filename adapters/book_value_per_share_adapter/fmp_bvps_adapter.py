from __future__ import annotations

import os
from typing import Any, Optional

import requests

from adapters.adapter import MetricAdapter, DataNotAvailable, retry_on_failure

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


class FMPBVPSAdapter(MetricAdapter):
    """
    Book Value Per Share (BVPS) from FinancialModelingPrep key-metrics TTM.

    Endpoint shape (examples):
      /api/v3/key-metrics-ttm/{symbol}?apikey=KEY
        -> [{ "bookValuePerShareTTM": ... }, ...]
    Fallback:
      /api/v3/key-metrics/{symbol}?limit=1&apikey=KEY
        -> [{ "bookValuePerShare": ... }, ...]
    """

    def __init__(self) -> None:
        self._name = "fmp_book_value_per_share"

    def get_name(self) -> str:
        return self._name

    @retry_on_failure(max_retries=2, delay=0.5)
    def fetch(self, ticker: str) -> float:
        tk = ticker.upper()
        api_key = os.getenv("FINANCIAL_PREP_API_KEY") or os.getenv("FINANCIAL_PREP_API_KEY".upper())
        if not api_key:
            raise DataNotAvailable(f"{self._name}: FINANCIAL_PREP_API_KEY missing")

        sess = requests.Session()
        sess.headers.update({"User-Agent": "ampyfin/1.0"})

        # Try TTM first
        url1 = f"https://financialmodelingprep.com/api/v3/key-metrics-ttm/{tk}?apikey={api_key}"
        r = sess.get(url1, timeout=10)
        if r.ok:
            arr = r.json()
            if isinstance(arr, list) and arr:
                v = _to_float(arr[0].get("bookValuePerShareTTM"))
                if v is not None and v > 0:
                    return float(v)

        # Fallback latest key-metrics
        url2 = f"https://financialmodelingprep.com/api/v3/key-metrics/{tk}?limit=1&apikey={api_key}"
        r = sess.get(url2, timeout=10)
        if r.ok:
            arr = r.json()
            if isinstance(arr, list) and arr:
                v = _to_float(arr[0].get("bookValuePerShare"))
                if v is not None and v > 0:
                    return float(v)

        raise DataNotAvailable(f"{self._name}: BVPS not available for {tk}")
