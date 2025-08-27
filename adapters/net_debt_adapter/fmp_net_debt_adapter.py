# adapters/net_debt_adapter/fmp_net_debt_adapter.py
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


class FMPNetDebtAdapter(MetricAdapter):
    """
    Fetches Net Debt using Financial Modeling Prep (most recent quarterly balance sheet).

    Requires:
      FINANCIAL_PREP_API_KEY in environment (.env)

    Endpoint:
      https://financialmodelingprep.com/api/v3/balance-sheet-statement/{ticker}?period=quarter&limit=1&apikey=...

    Parsing:
      - Prefer 'netDebt' if present.
      - Otherwise compute: totalDebt - cashAndShortTermInvestments (fallbacks used).
      - Returns a float (USD), can be negative if net cash.
    """

    def __init__(self) -> None:
        self._name = "fmp_net_debt"

    def get_name(self) -> str:
        return self._name

    def fetch(self, ticker: str) -> float:
        api_key = os.getenv("FINANCIAL_PREP_API_KEY")
        if not api_key:
            raise DataNotAvailable(f"{self._name}: missing FINANCIAL_PREP_API_KEY")

        url = f"https://financialmodelingprep.com/api/v3/balance-sheet-statement/{ticker.upper()}"
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

            # 1) direct field
            nd = _f(row.get("netDebt"))
            if nd is not None:
                return nd

            # 2) compute from components
            total_debt = _f(row.get("totalDebt")) or _f(row.get("shortTermDebt")) or 0.0
            if total_debt and (row.get("longTermDebt") is not None):
                ltd = _f(row.get("longTermDebt"))
                if ltd is not None and total_debt < ltd:
                    # Some payloads don't set totalDebt, combine if needed
                    std = _f(row.get("shortTermDebt")) or 0.0
                    total_debt = ltd + std

            cash_sti = (
                _f(row.get("cashAndShortTermInvestments"))
                or _f(row.get("cashAndCashEquivalents"))
                or 0.0
            )

            nd2 = (total_debt or 0.0) - (cash_sti or 0.0)
            return float(nd2)

        except DataNotAvailable:
            raise
        except Exception as exc:
            raise DataNotAvailable(f"{self._name}: failed to fetch net debt for {ticker}") from exc
