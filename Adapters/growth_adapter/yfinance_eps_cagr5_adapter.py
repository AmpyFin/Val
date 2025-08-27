# adapters/growth_adapter/yfinance_eps_cagr5_adapter.py
from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

from adapters.adapter import MetricAdapter, DataNotAvailable, retry_on_failure
from adapters.yf_session import get_simple_session


# ---------------------------- helpers ----------------------------

def _f(x) -> Optional[float]:
    try:
        if x is None:
            return None
        v = float(x)
        if np.isnan(v):  # NaN
            return None
        return v
    except Exception:
        return None


def _norm(s: str) -> str:
    return "".join(ch for ch in str(s).lower() if ch.isalnum())


def _series_to_float_by_date(ser: pd.Series) -> Optional[pd.Series]:
    """
    Convert a yfinance row Series (columns as index) to:
      - datetime index (ascending)
      - float values with NaNs dropped
    """
    if ser is None or ser.empty:
        return None

    raw_idx = ser.index
    dates = pd.to_datetime(raw_idx, errors="coerce")
    mask = ~dates.isna()
    if not mask.any():
        return None

    ser = ser[mask]
    dates = dates[mask]

    # sort by date ascending and carry dates along explicitly
    order = np.argsort(dates.values)
    ser = ser.iloc[order]
    dates_sorted = pd.DatetimeIndex(dates.values[order], name="date")

    # coerce to float & drop NaN/inf
    ser = ser.apply(_f)
    ser = pd.to_numeric(ser, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if ser.empty:
        return None

    # align length (if any entries were dropped)
    if len(ser) != len(dates_sorted):
        # keep only the dates that still exist after dropna by aligning on position
        # safer approach: rebuild Index by recomputing from ser's current index positions
        # Here, reconstruct by re-parsing ser.index as dates (they're still the original labels)
        ds = pd.to_datetime(ser.index, errors="coerce")
        ser.index = pd.DatetimeIndex(ds, name="date")
    else:
        ser.index = dates_sorted

    # ensure strictly ascending unique dates (drop accidental dup columns if any)
    ser = ser[~ser.index.duplicated(keep="last")].sort_index()
    return ser if not ser.empty else None


def _extract_eps_series(df: pd.DataFrame) -> Optional[pd.Series]:
    """
    Try direct EPS rows (prioritizing diluted EPS); else compute EPS = Net Income / Weighted Avg Diluted Shares.
    Returns Series indexed by period-end (datetime64[ns]) with float EPS.
    """
    if df is None or df.empty:
        return None

    idx_map = {_norm(ix): ix for ix in df.index}
    # Common EPS label variants
    eps_keys = [
        "dilutedeps", "epsdiluted", "basiceps", "epsbasic", "eps",
        "earningspersharediluted", "earningspersharebasic"
    ]
    for key in eps_keys:
        if key in idx_map:
            ser = df.loc[idx_map[key]]
            return _series_to_float_by_date(ser)

    # Compute EPS = Net Income (to common) / Weighted Avg Shares (prioritizing diluted)
    ni_keys = [
        "netincomecommonstockholders",
        "netincomeapplicabletocommon",
        "netincome",
        "netincomefromcontinuingoperations",
    ]
    sh_keys = [
        "weightedaveragesharesdiluted",
        "dilutedaverageshares",
        "averagesharesdiluted",
        "weightedaveragesharesbasic",
        "basicaverageshares",
        "averagesharesbasic",
    ]

    ni = None
    for k in ni_keys:
        if k in idx_map:
            ni = df.loc[idx_map[k]]
            break
    if ni is None:
        return None

    sh = None
    for k in sh_keys:
        if k in idx_map:
            sh = df.loc[idx_map[k]]
            break
    if sh is None:
        return None

    ni_s = _series_to_float_by_date(ni)
    sh_s = _series_to_float_by_date(sh)
    if ni_s is None or sh_s is None:
        return None

    common = ni_s.index.intersection(sh_s.index)
    if common.empty:
        return None

    eps = (ni_s[common] / sh_s[common]).replace([np.inf, -np.inf], np.nan).dropna()
    if eps.empty:
        return None

    # annual only (yfinance already gives yearly here, but guard anyway)
    # keep as ascending by date
    eps = eps.sort_index()
    return eps


def _choose_5y_window(eps: pd.Series,
                      min_years: float = 4.5,
                      max_years: float = 6.5) -> Tuple[pd.Timestamp, pd.Timestamp]:
    """
    Choose a ~5y window anchored at the last available year:
      - Prefer span between [min_years, max_years]
      - If insufficient data, use maximum available span (minimum 2 years)
      - earliest is the oldest point still meeting min_years span, or oldest available
    Raises DataNotAvailable if not enough history.
    """
    if eps is None or eps.empty:
        raise DataNotAvailable("EPS series empty")

    last_date = eps.index[-1]
    # Find the earliest index that yields span >= min_years
    candidates = eps.index[eps.index <= last_date]
    if len(candidates) < 2:
        raise DataNotAvailable("Insufficient EPS history")

    # Walk from oldest to newest, keep those that meet min span
    eligible = [d for d in candidates if (last_date - d).days / 365.2425 >= min_years]
    
    if eligible:
        # We have enough data for preferred ~5y window
        # Prefer the one closest to 5y without exceeding max_years
        # Among eligible, pick the most recent (max d) to keep span near min_years
        earliest = max(eligible)
        span_years = (last_date - earliest).days / 365.2425
        if span_years > max_years:
            # If somehow too long (odd calendars), shift forward until within bounds
            newer = [d for d in candidates if min_years <= (last_date - d).days / 365.2425 <= max_years]
            if newer:
                earliest = max(newer)  # closest to min_years
                span_years = (last_date - earliest).days / 365.2425
    else:
        # Not enough data for preferred ~5y window, use maximum available span
        # But require at least 2 years of data for meaningful CAGR
        min_span_years = 2.0
        fallback_eligible = [d for d in candidates if (last_date - d).days / 365.2425 >= min_span_years]
        if not fallback_eligible:
            raise DataNotAvailable("Not enough span for meaningful CAGR (minimum 2 years required)")
        
        # Use the maximum available span
        earliest = min(fallback_eligible)  # oldest date that meets minimum span

    return earliest, last_date


def _cagr_pos(earliest: float, latest: float, years: float) -> Optional[float]:
    if years is None or years <= 0:
        return None
    if earliest is None or latest is None:
        return None
    if earliest <= 0.0 or latest <= 0.0:
        return None
    try:
        return (latest / earliest) ** (1.0 / years) - 1.0
    except Exception:
        return None


# ---------------------------- adapter ----------------------------

class YFinanceEPSCAGR5Adapter(MetricAdapter):
    """
    ~5Y EPS CAGR (annual GAAP) from yfinance income statements.

    - Pulls annual income statement (prefers get_income_stmt(freq='yearly', pretty=True))
    - Extracts EPS (prioritizing diluted EPS) or computes from Net Income / Weighted Avg Diluted Shares
    - Selects a window with span in [4.5y, 6.5y] anchored at the latest period
    - Requires positive endpoints; if earliest EPS <= 0, advances to first positive and recomputes span
    - Returns CAGR as a float (e.g., 0.12 for 12%)
    """

    def __init__(self) -> None:
        self._name = "yfinance_eps_cagr_5y"

    def get_name(self) -> str:
        return self._name

    def _get_current_ttm_eps(self, t: yf.Ticker) -> Optional[float]:
        """Get the most recent TTM EPS from yfinance info."""
        try:
            info = t.info  # type: ignore[attr-defined]
            
            if not isinstance(info, dict):
                return None

            # Try to get trailing EPS directly
            trailing_eps = info.get('trailingEps')
            if trailing_eps is not None:
                val = _f(trailing_eps)
                if val is not None:
                    return float(val)
            
            # Try alternative field names
            eps_trailing = info.get('epsTrailingTwelveMonths')
            if eps_trailing is not None:
                val = _f(eps_trailing)
                if val is not None:
                    return float(val)
            
            return None
        except Exception:
            return None

    @retry_on_failure(max_retries=3, delay=0.6)
    def fetch(self, ticker: str) -> float:
        tk = ticker.upper()
        t = yf.Ticker(tk, session=get_simple_session())

        # Get historical annual EPS data
        df: Optional[pd.DataFrame] = None
        # Preferred API
        try:
            df = t.get_income_stmt(freq="yearly", pretty=True)  # type: ignore[attr-defined]
        except Exception:
            df = None
        # Fallbacks
        if df is None or df.empty:
            try:
                df = t.income_stmt  # type: ignore[attr-defined]
            except Exception:
                df = None
        if df is None or df.empty:
            try:
                df = t.financials  # type: ignore[attr-defined]
            except Exception:
                df = None

        if df is None or df.empty:
            raise DataNotAvailable(f"{self._name}: income statement unavailable for {tk}")

        eps = _extract_eps_series(df)
        if eps is None or eps.size < 1:
            raise DataNotAvailable(f"{self._name}: EPS series not usable for {tk}")

        # Try to get the current TTM EPS and replace the most recent annual value
        current_ttm_eps = self._get_current_ttm_eps(t)
        if current_ttm_eps is not None and current_ttm_eps > 0:
            # Replace the most recent annual EPS with TTM EPS
            import pandas as pd
            from datetime import datetime
            current_date = pd.Timestamp(datetime.now().replace(month=12, day=31))
            
            # Create a new series with TTM EPS as the most recent value
            eps_list = [(date, value) for date, value in eps.items()]
            eps_list.append((current_date, current_ttm_eps))
            
            # Sort by date and remove duplicates, keeping the most recent
            eps_list.sort(key=lambda x: x[0])
            eps_dict = dict(eps_list)
            eps = pd.Series(eps_dict, name=eps.name)
            eps.index.name = "date"

        if eps.size < 2:
            raise DataNotAvailable(f"{self._name}: insufficient EPS history for {tk}")

        # Choose a ~5y window by span, not by count
        earliest_date, latest_date = _choose_5y_window(eps, min_years=4.5, max_years=6.5)
        window = eps.loc[(eps.index >= earliest_date) & (eps.index <= latest_date)].copy()

        # Ensure positive endpoints; if earliest <= 0, slide forward to first positive
        if window.iloc[0] <= 0.0:
            pos_idx = window[window > 0.0].index
            if len(pos_idx) < 2:
                raise DataNotAvailable(f"{self._name}: positive EPS endpoints not available for {tk}")
            window = eps.loc[pos_idx[0]: latest_date]
            # Check span still meaningful
            span_years = (window.index[-1] - window.index[0]).days / 365.2425
            if span_years < 2.5:
                raise DataNotAvailable(f"{self._name}: insufficient positive EPS span for {tk}")

        earliest_eps = float(window.iloc[0])
        latest_eps = float(window.iloc[-1])

        years = (window.index[-1] - window.index[0]).days / 365.2425
        g = _cagr_pos(earliest_eps, latest_eps, years)
        if g is None:
            raise DataNotAvailable(f"{self._name}: could not compute CAGR for {tk}")

        return float(g)
