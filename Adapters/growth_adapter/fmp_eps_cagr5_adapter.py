# adapters/growth_adapter/fmp_eps_cagr5_adapter.py
from __future__ import annotations

import os
from typing import Any, List, Optional, Tuple

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


def _coerce_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        f = float(v)
        if f != f:  # NaN
            return None
        return f
    except Exception:
        return None


def _compute_cagr(earliest: float, latest: float, years: float) -> Optional[float]:
    """
    CAGR as a decimal (e.g., 0.15 for 15%).
    If inputs are invalid (<=0 or sign flip), return None.
    """
    try:
        if years <= 0:
            return None
        if earliest is None or latest is None:
            return None
        # If EPS <= 0 at start or signs flip, CAGR is not meaningful for Lynch-style growth.
        if earliest <= 0 or (earliest < 0) != (latest < 0):
            return None
        return (latest / earliest) ** (1.0 / years) - 1.0
    except Exception:
        return None


class FMPEPSCAGR5Adapter(MetricAdapter):
    """
    Computes 5Y EPS CAGR using FMP annual income statements.

    Strategy:
      - Pull annual income statements (limit ~10).
      - Prefer 'epsdiluted' then 'eps'.
      - Use the most recent and the oldest value ~5 years apart.
      - Compute CAGR = (Latest / Earliest)^(1/years) - 1
      - Returns a decimal (e.g., 0.15 for 15%).

    Requires:
      FINANCIAL_PREP_API_KEY in environment (.env)

    Endpoint:
      https://financialmodelingprep.com/api/v3/income-statement/{ticker}?period=annual&limit=10&apikey=...
    """

    def __init__(self) -> None:
        self._name = "fmp_eps_cagr_5y"

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
                params={"period": "annual", "limit": 10, "apikey": api_key},
                timeout=HTTP_TIMEOUT,
                headers=HEADERS,
            )
            if resp.status_code != 200:
                raise DataNotAvailable(f"{self._name}: HTTP {resp.status_code} for {ticker}")

            data = resp.json()
            if not isinstance(data, list) or not data:
                raise DataNotAvailable(f"{self._name}: unexpected payload shape")

            # FMP returns most-recent first. Build list of (year_str, eps_value)
            points: List[Tuple[str, float]] = []
            for row in data:
                # Try several field names for EPS
                eps_candidates = [
                    row.get("epsdiluted"),
                    row.get("epsDiluted"),
                    row.get("eps"),
                    row.get("EPS"),
                ]
                eps = None
                for c in eps_candidates:
                    eps = _coerce_float(c)
                    if eps is not None:
                        break
                if eps is None:
                    continue

                year = row.get("calendarYear") or row.get("date") or ""
                year = str(year)
                points.append((year, eps))

            if len(points) < 2:
                raise DataNotAvailable(f"{self._name}: insufficient EPS history for {ticker}")

            # Points are most-recent first; reverse to chronological
            points = list(reversed(points))

            # Choose earliest and latest ~5 years apart (fallback to max span if fewer)
            earliest_idx = max(0, len(points) - 6)  # ~5 intervals back
            latest_idx = len(points) - 1

            earliest_eps = points[earliest_idx][1]
            latest_eps = points[latest_idx][1]
            years_span = max(1.0, latest_idx - earliest_idx)  # assume 1 year per step

            cagr = _compute_cagr(earliest_eps, latest_eps, years_span)
            if cagr is None:
                raise DataNotAvailable(f"{self._name}: could not compute CAGR for {ticker}")

            return float(cagr)

        except DataNotAvailable:
            raise
        except Exception as exc:
            raise DataNotAvailable(f"{self._name}: failed to compute 5Y EPS CAGR for {ticker}") from exc
