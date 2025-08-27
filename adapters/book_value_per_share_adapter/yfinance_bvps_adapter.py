from __future__ import annotations

from typing import Any, Optional

import yfinance as yf

from adapters.adapter import MetricAdapter, DataNotAvailable, retry_on_failure
from adapters.yf_session import get_simple_session
from adapters.shares_outstanding_adapter.yfinance_shares_outstanding_adapter import (
    YFinanceSharesOutstandingAdapter,
)

def _to_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        f = float(x)
        if f != f:  # NaN
            return None
        return f
    except Exception:
        return None


class YFinanceBVPSAdapter(MetricAdapter):
    """
    Book Value Per Share (BVPS) via Yahoo Finance:
      BVPS = (Most-recent Total Stockholders' Equity) / Shares Outstanding

    We fetch equity from the most recent column of balance sheet and divide by
    shares outstanding (via the yfinance shares adapter to keep consistency).
    """

    def __init__(self) -> None:
        self._name = "yfinance_book_value_per_share"
        self._so = YFinanceSharesOutstandingAdapter()

    def get_name(self) -> str:
        return self._name

    @retry_on_failure(max_retries=2, delay=0.5)
    def fetch(self, ticker: str) -> float:
        tk = ticker.upper()
        try:
            session = get_simple_session()
            t = yf.Ticker(tk, session=session)

            # Try quarterly first (fresher), then annual
            for df in (getattr(t, "quarterly_balance_sheet", None), getattr(t, "balance_sheet", None)):
                if df is None or df.empty:
                    continue

                # Find most recent period column
                col = df.columns[0]  # yfinance puts most recent first
                # Try several equity row labels (Yahoo uses inconsistent labels)
                candidate_rows = {
                    "Total Stockholder Equity",
                    "Stockholders Equity",
                    "Total Equity Gross Minority Interest",
                    "Total Equity",
                    "Total shareholders equity",
                    "Total stockholders' equity",
                }
                # Case-insensitive lookup
                idx_lower = {str(i).lower(): i for i in df.index}

                equity_val = None
                for label in candidate_rows:
                    key = label.lower()
                    if key in idx_lower:
                        try:
                            v = df.loc[idx_lower[key], col]
                            equity_val = _to_float(v)
                            if equity_val is not None:
                                break
                        except Exception:
                            pass

                if equity_val is not None and equity_val != 0:
                    shares = _to_float(self._so.fetch(tk))
                    if shares is None or shares <= 0:
                        raise DataNotAvailable(f"{self._name}: shares outstanding missing for {tk}")
                    return float(equity_val / shares)

            raise DataNotAvailable(f"{self._name}: could not find equity on balance sheet for {tk}")

        except DataNotAvailable:
            raise
        except Exception as exc:
            raise DataNotAvailable(f"{self._name}: failure for {tk}") from exc
