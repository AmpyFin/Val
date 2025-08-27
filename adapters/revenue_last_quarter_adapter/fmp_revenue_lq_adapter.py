# adapters/revenue_last_quarter_adapter/fmp_revenue_lq_adapter.py
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


class FMPRevenueLastQuarterAdapter(MetricAdapter):
    """
    Fetches LAST QUARTER revenue using Financial Modeling Prep.

    Requires:
      FINANCIAL_PREP_API_KEY in environment (.env)

    Endpoint:
      https://financialmodelingprep.com/api/v3/income-statement/{ticker}?period=quarter&limit=1&apikey=...
    We read the 'revenue' field from the most recent quarterly income statement.
    Returns revenue as a float (USD).
    """

    def __init__(self) -> None:
        self._name = "fmp_revenue_last_quarter"

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

        url = f"https://financialmodelingprep.com/api/v3/income-statement/{ticker.upper()}"
        try:
            resp = requests.get(
                url,
                params={"period": "quarter", "limit": 1, "apikey": api_key},
                timeout=HTTP_TIMEOUT,
                headers=HEADERS,
            )
            if resp.status_code != 200:
                raise DataNotAvailable(f"{self._name}: HTTP {resp.status_code} for {ticker}")

            data = resp.json()
            if not isinstance(data, list) or not data:
                raise DataNotAvailable(f"{self._name}: unexpected payload shape")

            row = data[0]
            candidates = [row.get("revenue"), row.get("Revenue")]
            for c in candidates:
                val = self._coerce(c)
                if val is not None:
                    return val

            raise DataNotAvailable(f"{self._name}: revenue not found in last quarter for {ticker}")

        except DataNotAvailable:
            raise
        except Exception as exc:
            raise DataNotAvailable(f"{self._name}: failed to fetch last quarter revenue for {ticker}") from exc
