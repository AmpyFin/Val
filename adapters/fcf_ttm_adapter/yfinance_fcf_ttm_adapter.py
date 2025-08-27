# adapters/fcf_ttm_adapter/yfinance_fcf_ttm_adapter.py
from __future__ import annotations

from typing import Any, Optional

import pandas as pd
import yfinance as yf

from adapters.adapter import MetricAdapter, DataNotAvailable, retry_on_failure, retry_on_rate_limit
from adapters.yf_session import get_simple_session


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


class YFinanceFCFTTMAdapter(MetricAdapter):
    """
    Computes Free Cash Flow (FCF) TTM by summing the last 4 quarterly values via yfinance.

    Strategy:
      - Use t.quarterly_cashflow DataFrame (rows as accounts, columns as period end dates).
      - Prefer a row labeled 'Free Cash Flow' / 'FreeCashFlow'.
      - Fallback to compute: Operating Cash Flow - Capital Expenditure.

    Returns: float (USD), can be negative.
    """

    def __init__(self) -> None:
        self._name = "yfinance_fcf_ttm"

    def get_name(self) -> str:
        return self._name

    @retry_on_rate_limit(max_retries=3, base_delay=5.0)
    def fetch(self, ticker: str) -> float:
        try:
            session = get_simple_session()
            t = yf.Ticker(ticker, session=session)
            df: Optional[pd.DataFrame] = None
            try:
                df = t.quarterly_cashflow  # type: ignore[attr-defined]
            except Exception:
                df = None

            if df is None or not isinstance(df, pd.DataFrame) or df.empty:
                # Check if this might be due to rate limiting
                raise DataNotAvailable(f"{self._name}: quarterly cashflow unavailable for {ticker} (possibly rate limited)")

            # Primary: Free Cash Flow row
            row = None
            for lbl in ("Free Cash Flow", "FreeCashFlow"):
                if lbl in df.index:
                    row = df.loc[lbl]
                    break

            vals = []
            if row is not None and not row.empty:
                s = row.dropna()
                try:
                    s = s.sort_index(ascending=False)
                except Exception:
                    pass
                for v in s.tolist():
                    cv = _f(v)
                    if cv is not None:
                        vals.append(cv)
                    if len(vals) == 4:
                        break
            else:
                # Fallback: Operating Cash Flow - Capital Expenditure
                ocf = None
                capex = None
                for lbl in ("Operating Cash Flow", "Total Cash From Operating Activities", "OperatingCashFlow"):
                    if lbl in df.index:
                        ocf = df.loc[lbl].dropna()
                        break
                for lbl in ("Capital Expenditure", "CapitalExpenditures", "Capital Expenditures"):
                    if lbl in df.index:
                        capex = df.loc[lbl].dropna()
                        break
                if ocf is None or ocf.empty or capex is None or capex.empty:
                    raise DataNotAvailable(f"{self._name}: cannot derive FCF from OCF and CapEx for {ticker}")

                # Align and take up to 4 most recent pairs
                try:
                    ocf = ocf.sort_index(ascending=False)
                    capex = capex.sort_index(ascending=False)
                except Exception:
                    pass

                for i in range(min(4, len(ocf), len(capex))):
                    fcf = _f(ocf.iloc[i])  # type: ignore[index]
                    cx = _f(capex.iloc[i])  # type: ignore[index]
                    if fcf is not None and cx is not None:
                        vals.append(fcf - cx)

            if not vals:
                raise DataNotAvailable(f"{self._name}: no usable FCF values for {ticker}")

            return float(sum(vals))

        except DataNotAvailable:
            raise
        except Exception as exc:
            raise DataNotAvailable(f"{self._name}: failed to compute FCF TTM for {ticker}") from exc
