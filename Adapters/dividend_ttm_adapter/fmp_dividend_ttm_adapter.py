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


class FMPDividendTTMAdapter(MetricAdapter):
    """
    Dividend per share TTM from FinancialModelingPrep.

    Endpoint shape:
      /api/v3/historical-price-full/stock_dividend/{symbol}?apikey=KEY
      Sum the last 4 'dividend' entries as TTM approximation.
    """

    def __init__(self) -> None:
        self._name = "fmp_dividend_ttm"

    def get_name(self) -> str:
        return self._name

    @retry_on_failure(max_retries=2, delay=0.5)
    def fetch(self, ticker: str) -> float:
        tk = ticker.upper()
        api_key = os.getenv("FINANCIAL_PREP_API_KEY") or os.getenv("FINANCIAL_PREP_API_KEY".upper())
        if not api_key:
            raise DataNotAvailable(f"{self._name}: FINANCIAL_PREP_API_KEY missing")

        url = f"https://financialmodelingprep.com/api/v3/historical-price-full/stock_dividend/{tk}?apikey={api_key}"
        r = requests.get(url, timeout=12)
        if not r.ok:
            raise DataNotAvailable(f"{self._name}: HTTP {r.status_code} for {tk}")

        js = r.json()
        hist = js.get("historical") if isinstance(js, dict) else None
        if not isinstance(hist, list) or not hist:
            raise DataNotAvailable(f"{self._name}: no dividend history for {tk}")

        # Sum last 4 payments
        vals = []
        for row in hist[:4]:
            v = _to_float(row.get("dividend"))
            if v is not None and v > 0:
                vals.append(v)
        if not vals:
            raise DataNotAvailable(f"{self._name}: zero TTM dividends for {tk}")

        return float(sum(vals))
