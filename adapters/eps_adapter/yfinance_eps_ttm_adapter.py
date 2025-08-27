# adapters/eps_adapter/yfinance_eps_ttm_adapter.py
from __future__ import annotations

from typing import Any, Optional

import pandas as pd
import yfinance as yf

from adapters.adapter import MetricAdapter, DataNotAvailable, retry_on_failure, retry_on_rate_limit
from adapters.yf_session import get_simple_session


def _coerce(v: Optional[Any]) -> Optional[float]:
    try:
        if v is None:
            return None
        f = float(v)
        if f != f:  # NaN
            return None
        return f
    except Exception:
        return None


class YFinanceEPSTTMAdapter(MetricAdapter):
    """
    Gets EPS TTM directly from yfinance info fields, with fallback to quarterly calculation.

    Strategy:
      - First try: Use t.info to get trailingEps or epsTrailingTwelveMonths.
      - Fallback: Calculate from quarterly earnings data (last 4 quarters).
      - Uses smart session management to handle rate limiting.

    Returns a float (USD per share).
    """

    def __init__(self) -> None:
        self._name = "yfinance_eps_ttm"

    def get_name(self) -> str:
        return self._name

    def _get_eps_from_info(self, t: yf.Ticker) -> Optional[float]:
        """Try to get EPS TTM from info fields."""
        try:
            info = t.info  # type: ignore[attr-defined]
            
            if not isinstance(info, dict):
                return None

            # Try to get trailing EPS directly
            trailing_eps = info.get('trailingEps')
            if trailing_eps is not None:
                val = _coerce(trailing_eps)
                if val is not None:
                    return float(val)
            
            # Try alternative field names
            eps_trailing = info.get('epsTrailingTwelveMonths')
            if eps_trailing is not None:
                val = _coerce(eps_trailing)
                if val is not None:
                    return float(val)
            
            return None
        except Exception:
            return None

    def _normalize_key(self, s: str) -> str:
        return "".join(ch for ch in str(s).lower() if ch.isalnum())

    def _sort_cols_desc_by_date(self, df: pd.DataFrame) -> pd.DataFrame:
        cols_dt = pd.to_datetime(df.columns, errors="coerce")
        order = pd.Series(cols_dt, index=df.columns).sort_values(ascending=False).index
        return df.loc[:, order]

    def _sum_last4_quarters(self, ser: pd.Series) -> float:
        # ser is indexed by columns (periods), already sorted most-recent-first
        s = pd.to_numeric(ser, errors="coerce").replace([float("inf"), float("-inf")], pd.NA).dropna()
        if s.empty or len(s) < 4:
            raise DataNotAvailable(f"{self._name}: insufficient quarterly EPS values for TTM")
        return float(s.iloc[:4].sum())

    def _calculate_eps_from_quarterly(self, t: yf.Ticker) -> float:
        """Calculate EPS TTM from quarterly data, prioritizing quarterly diluted EPS."""
        # Prefer the newer API if present; fallback to quarterly_income_stmt
        df: Optional[pd.DataFrame] = None
        try:
            df = t.get_income_stmt(freq="quarterly", pretty=True)  # type: ignore[attr-defined]
        except Exception:
            pass
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            try:
                df = t.quarterly_income_stmt  # type: ignore[attr-defined]
            except Exception:
                df = None
        if df is None or df.empty:
            raise DataNotAvailable(f"{self._name}: quarterly income statement unavailable for calculation")

        df = self._sort_cols_desc_by_date(df)

        idx_map = {self._normalize_key(ix): ix for ix in df.index}

        # 1) If a quarterly Diluted EPS row exists, just sum the last 4 quarters
        for key in ["dilutedeps", "epsdiluted", "earningspersharediluted"]:
            if key in idx_map:
                return self._sum_last4_quarters(df.loc[idx_map[key]])

        # 2) Else compute quarterly EPS = Net income to common / Weighted avg diluted shares
        ni_keys = [
            "netincomecommonstockholders", "netincomeapplicabletocommon",
            "netincome", "netincomefromcontinuingoperations",
        ]
        sh_keys = [
            "weightedaveragesharesdiluted", "dilutedaverageshares", "averagesharesdiluted",
        ]

        ni_row = next((idx_map[k] for k in ni_keys if k in idx_map), None)
        sh_row = next((idx_map[k] for k in sh_keys if k in idx_map), None)
        if ni_row is None or sh_row is None:
            raise DataNotAvailable(f"{self._name}: needed rows not found to compute quarterly EPS")

        ni = pd.to_numeric(df.loc[ni_row], errors="coerce")
        sh = pd.to_numeric(df.loc[sh_row], errors="coerce")
        q_eps = (ni / sh).replace([float("inf"), float("-inf")], pd.NA).dropna()

        if q_eps.empty or len(q_eps) < 4:
            raise DataNotAvailable(f"{self._name}: insufficient computed quarterly EPS for TTM")

        return float(q_eps.iloc[:4].sum())

    @retry_on_rate_limit(max_retries=3, base_delay=5.0)
    def fetch(self, ticker: str) -> float:
        try:
            session = get_simple_session()
            t = yf.Ticker(ticker, session=session)
            
            # First try: Get EPS from info fields
            eps_from_info = self._get_eps_from_info(t)
            if eps_from_info is not None:
                return eps_from_info
            
            # Fallback: Calculate from quarterly data
            # Create a fresh session for quarterly data to avoid rate limiting
            fresh_session = get_simple_session()
            fresh_t = yf.Ticker(ticker, session=fresh_session)
            return self._calculate_eps_from_quarterly(fresh_t)

        except DataNotAvailable:
            raise
        except Exception as exc:
            raise DataNotAvailable(f"{self._name}: failed to compute EPS TTM for {ticker}") from exc
