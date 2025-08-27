# adapters/eps_adapter/fmp_eps_ttm_adapter.py
from __future__ import annotations

import os
from typing import Any, Optional

import requests

from adapters.adapter import MetricAdapter, DataNotAvailable

HTTP_TIMEOUT = 15
HEADERS = {"User-Agent": "ampyfin-val-model/1.0 (+https://example.org)"}


class FMPEPSTTMAdapter(MetricAdapter):
    """
    Fetches EPS TTM using Financial Modeling Prep's key-metrics-ttm endpoint.

    Requires:
      FINANCIAL_PREP_API_KEY in environment (.env).
    Endpoint example:
      https://financialmodelingprep.com/api/v3/key-metrics-ttm/AAPL?apikey=...
    We search for fields like: epsTTM, eps_ttm, epsTtm (schema variations).
    """

    def __init__(self) -> None:
        self._name = "fmp_eps_ttm"

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

    def fetch(self, ticker: str) -> float:
        api_key = os.getenv("FINANCIAL_PREP_API_KEY")
        if not api_key:
            raise DataNotAvailable(f"{self._name}: missing FINANCIAL_PREP_API_KEY")

        url = f"https://financialmodelingprep.com/api/v3/key-metrics-ttm/{ticker.upper()}"
        try:
            resp = requests.get(url, params={"apikey": api_key}, timeout=HTTP_TIMEOUT, headers=HEADERS)
            if resp.status_code != 200:
                raise DataNotAvailable(f"{self._name}: HTTP {resp.status_code} for {ticker}")

            data = resp.json()
            # FMP returns a list; usually the first element has fields we need
            if not isinstance(data, list) or not data:
                raise DataNotAvailable(f"{self._name}: unexpected payload shape")

            row = data[0]
            candidates = [
                row.get("epsTTM"),
                row.get("eps_ttm"),
                row.get("epsTtm"),
                row.get("epsTrailingTwelveMonths"),
            ]
            for c in candidates:
                val = self._coerce(c)
                if val is not None:
                    return val

            raise DataNotAvailable(f"{self._name}: eps TTM not found for {ticker}")

        except DataNotAvailable:
            raise
        except Exception as exc:
            raise DataNotAvailable(f"{self._name}: failed to fetch EPS TTM for {ticker}") from exc
