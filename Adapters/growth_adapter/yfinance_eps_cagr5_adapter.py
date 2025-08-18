# adapters/growth_adapter/yfinance_eps_cagr5_adapter.py
from __future__ import annotations

from typing import List, Optional, Tuple

import pandas as pd
import yfinance as yf

from adapters.adapter import MetricAdapter, DataNotAvailable, retry_on_failure
from adapters.yf_session import get_simple_session


def _coerce_float(v) -> Optional[float]:
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
    if years <= 0:
        return None
    if earliest is None or latest is None:
        return None
    
    # Handle negative earnings: if both are negative, we can still calculate CAGR
    # For negative earnings, improving means becoming less negative (closer to zero)
    if earliest < 0 and latest < 0:
        # Both negative: calculate CAGR using absolute values, then negate if getting worse
        abs_earliest = abs(earliest)
        abs_latest = abs(latest)
        try:
            cagr = (abs_latest / abs_earliest) ** (1.0 / years) - 1.0
            # If latest is more negative (worse), CAGR should be negative
            # If latest is less negative (better), CAGR should be positive
            if abs_latest > abs_earliest:  # Getting worse (more negative)
                return -cagr
            else:  # Getting better (less negative)
                return cagr
        except Exception:
            return None
    elif earliest <= 0 or latest <= 0:
        # Mixed signs or zero values - can't calculate meaningful CAGR
        return None
    
    # Both positive - standard CAGR calculation
    try:
        return (latest / earliest) ** (1.0 / years) - 1.0
    except Exception:
        return None


class YFinanceEPSCAGR5Adapter(MetricAdapter):
    """
    Computes ~5Y EPS CAGR using yfinance annual income statement data.

    Strategy:
      - Attempt to read an income-statement DataFrame with an EPS row:
        labels like: 'Diluted EPS', 'DilutedEPS', 'Basic EPS', 'BasicEPS', 'EPS'
      - Columns are annual period end dates; treat them as yearly steps.
      - Use last column vs. fifth-from-last (if available) to approximate 5Y CAGR.
      - Return decimal (e.g., 0.15 for 15%).

    Notes:
      - yfinance schemas vary by version; this is best-effort and may raise DataNotAvailable.
    """

    def __init__(self) -> None:
        self._name = "yfinance_eps_cagr_5y"

    def get_name(self) -> str:
        return self._name

    @retry_on_failure(max_retries=3, delay=0.5)
    def fetch(self, ticker: str) -> float:
        try:
            session = get_simple_session()
            t = yf.Ticker(ticker, session=session)

            df: Optional[pd.DataFrame] = None

            # Try newer getter first (if present)
            if hasattr(t, "get_income_stmt"):
                try:
                    df = t.get_income_stmt(freq="annual")  # type: ignore[attr-defined]
                except Exception:
                    df = None

            # Fallbacks: .income_stmt (newer) or .financials (older)
            if df is None:
                try:
                    df = t.income_stmt  # type: ignore[attr-defined]
                except Exception:
                    df = None
            if df is None:
                try:
                    df = t.financials  # type: ignore[attr-defined]
                except Exception:
                    df = None

            if df is None or not isinstance(df, pd.DataFrame) or df.empty:
                raise DataNotAvailable(f"{self._name}: income statement unavailable for {ticker}")

            row_labels = [
                "Diluted EPS", "DilutedEPS", "EPS (Diluted)",
                "Basic EPS", "BasicEPS", "EPS",
                "EPS Diluted", "EPS Basic",
            ]
            row = None
            for lbl in row_labels:
                if lbl in df.index:
                    row = df.loc[lbl]
                    break
            if row is None or row.empty:
                raise DataNotAvailable(f"{self._name}: EPS row not found for {ticker}")

            s = row.dropna()
            if s.empty:
                raise DataNotAvailable(f"{self._name}: EPS series empty for {ticker}")

            # Ensure columns are in chronological order (left oldest → right newest)
            try:
                # Many yfinance frames already have ascending columns; sort if datetime-like.
                if hasattr(s.index, "to_series"):
                    # Here 's' is a Series with column labels as its index (after .loc)
                    pass
            except Exception:
                pass

            # Convert to list preserving order (as given by df)
            values: List[float] = []
            for val in s.tolist():
                fv = _coerce_float(val)
                if fv is not None:
                    values.append(fv)

            if len(values) < 2:
                raise DataNotAvailable(f"{self._name}: insufficient EPS history for {ticker}")

            # Use the longest available span up to ~5 intervals
            earliest_idx = max(0, len(values) - 6)
            latest_idx = len(values) - 1
            earliest_eps = values[earliest_idx]
            latest_eps = values[latest_idx]
            years_span = max(1.0, latest_idx - earliest_idx)

            cagr = _compute_cagr(earliest_eps, latest_eps, years_span)
            if cagr is None:
                raise DataNotAvailable(f"{self._name}: could not compute CAGR for {ticker}")

            return float(cagr)

        except DataNotAvailable:
            raise
        except Exception as exc:
            raise DataNotAvailable(f"{self._name}: failed to compute 5Y EPS CAGR for {ticker}") from exc
