# adapters/shares_outstanding_adapter/fmp_shares_outstanding_adapter.py
from __future__ import annotations

import os
from typing import Any, Optional

import requests

# Load .env early if python-dotenv is available (non-fatal if missing)
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

from adapters.adapter import MetricAdapter, DataNotAvailable

HTTP_TIMEOUT = 15
HEADERS = {"User-Agent": "ampyfin-val-model/1.0 (+https://example.org)"}


class FMPSharesOutstandingAdapter(MetricAdapter):
    """
    Fetches total shares outstanding using Financial Modeling Prep.

    Requires:
      FINANCIAL_PREP_API_KEY in environment (.env)

    Primary endpoint (simple & stable):
      https://financialmodelingprep.com/api/v3/profile/{ticker}?apikey=...

    Parsing:
      - FMP 'profile' returns a list[ { "symbol":..., "sharesOutstanding": ... } ]
      - We return sharesOutstanding as a float.
    """

    def __init__(self) -> None:
        self._name = "fmp_shares_outstanding"

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

    def fetch(self, ticker: str) -> float:
        api_key = os.getenv("FINANCIAL_PREP_API_KEY")
        if not api_key:
            raise DataNotAvailable(f"{self._name}: missing FINANCIAL_PREP_API_KEY")

        url = f"https://financialmodelingprep.com/api/v3/profile/{ticker.upper()}"
        try:
            resp = requests.get(url, params={"apikey": api_key}, timeout=HTTP_TIMEOUT, headers=HEADERS)
            if resp.status_code != 200:
                raise DataNotAvailable(f"{self._name}: HTTP {resp.status_code} for {ticker}")

            data = resp.json()
            if not isinstance(data, list) or not data:
                raise DataNotAvailable(f"{self._name}: unexpected payload shape")

            row = data[0]
            candidates = [
                row.get("sharesOutstanding"),
                row.get("SharesOutstanding"),
            ]
            for c in candidates:
                val = self._coerce(c)
                if val is not None:
                    return val

            raise DataNotAvailable(f"{self._name}: sharesOutstanding not found for {ticker}")

        except DataNotAvailable:
            raise
        except Exception as exc:
            raise DataNotAvailable(f"{self._name}: failed to fetch sharesOutstanding for {ticker}") from exc
