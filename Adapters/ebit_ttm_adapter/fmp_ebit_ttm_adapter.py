# adapters/ebit_ttm_adapter/fmp_ebit_ttm_adapter.py
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


class FMPEBITTTMAdapter(MetricAdapter):
    """
    Computes EBIT TTM by summing the last 4 quarterly EBIT values via FMP.

    Requires:
      FINANCIAL_PREP_API_KEY in environment (.env)

    Endpoint:
      https://financialmodelingprep.com/api/v3/income-statement/{ticker}?period=quarter&limit=4&apikey=...
    Field:
      'ebit' (preferred) with fallbacks if schema varies.
    """

    def __init__(self) -> None:
        self._name = "fmp_ebit_ttm"

    def get_name(self) -> str:
        return self._name

    def fetch(self, ticker: str) -> float:
        api_key = os.getenv("FINANCIAL_PREP_API_KEY")
        if not api_key:
            raise DataNotAvailable(f"{self._name}: missing FINANCIAL_PREP_API_KEY")

        url = f"https://financialmodelingprep.com/api/v3/income-statement/{ticker.upper()}"
        try:
            resp = requests.get(
                url,
                params={"period": "quarter", "limit": 4, "apikey": api_key},
                timeout=HTTP_TIMEOUT,
                headers=HEADERS,
            )
            if resp.status_code != 200:
                raise DataNotAvailable(f"{self._name}: HTTP {resp.status_code} for {ticker}")

            data = resp.json()
            if not isinstance(data, list) or not data:
                raise DataNotAvailable(f"{self._name}: unexpected payload shape")

            total = 0.0
            count = 0
            for row in data:
                # EBIT should be operating income before interest & taxes; FMP often exposes 'ebit'
                val = _f(row.get("ebit")) or _f(row.get("EBIT")) or _f(row.get("operatingIncome"))
                if val is not None:
                    total += val
                    count += 1

            if count == 0:
                raise DataNotAvailable(f"{self._name}: no quarterly EBIT values for {ticker}")

            return float(total)

        except DataNotAvailable:
            raise
        except Exception as exc:
            raise DataNotAvailable(f"{self._name}: failed to compute EBIT TTM for {ticker}") from exc
