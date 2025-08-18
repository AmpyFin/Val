# adapters/fcf_ttm_adapter/fmp_fcf_ttm_adapter.py
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


class FMPFCFTTMAdapter(MetricAdapter):
    """
    Computes Free Cash Flow (FCF) TTM by summing the last 4 quarterly FCF values via FMP.

    Requires:
      FINANCIAL_PREP_API_KEY in environment (.env)

    Endpoint:
      https://financialmodelingprep.com/api/v3/cash-flow-statement/{ticker}?period=quarter&limit=4&apikey=...

    Parsing:
      - Prefer 'freeCashFlow'
      - Fallback to 'operatingCashFlow - capitalExpenditure' if needed
    Returns: float (USD), can be negative.
    """

    def __init__(self) -> None:
        self._name = "fmp_fcf_ttm"

    def get_name(self) -> str:
        return self._name

    def fetch(self, ticker: str) -> float:
        api_key = os.getenv("FINANCIAL_PREP_API_KEY")
        if not api_key:
            raise DataNotAvailable(f"{self._name}: missing FINANCIAL_PREP_API_KEY")

        url = f"https://financialmodelingprep.com/api/v3/cash-flow-statement/{ticker.upper()}"
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
                fcf = _f(row.get("freeCashFlow"))
                if fcf is None:
                    ocf = _f(row.get("operatingCashFlow"))
                    capex = _f(row.get("capitalExpenditure"))
                    if ocf is not None and capex is not None:
                        fcf = ocf - capex
                if fcf is not None:
                    total += fcf
                    count += 1

            if count == 0:
                raise DataNotAvailable(f"{self._name}: no quarterly FCF values for {ticker}")

            return float(total)

        except DataNotAvailable:
            raise
        except Exception as exc:
            raise DataNotAvailable(f"{self._name}: failed to compute FCF TTM for {ticker}") from exc
