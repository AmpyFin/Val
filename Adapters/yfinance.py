# adapters/yfinance.py
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Iterable, List

import yfinance as yf

try:
    import pandas as pd  # yfinance returns pandas objects
except Exception:  # pragma: no cover
    pd = None  # type: ignore

# Optional, helps rotate user agents & robustness under load
try:
    from curl_cffi import requests as curl_requests  # type: ignore
    from curl_cffi import Session as CurlSession  # type: ignore
except Exception:  # pragma: no cover
    import requests as curl_requests  # type: ignore
    from requests import Session as CurlSession  # type: ignore

# Optional, reduces repeated calls within a single run (safe default if missing)
try:
    from requests_cache import CachedSession  # type: ignore
except Exception:  # pragma: no cover
    CachedSession = None  # type: ignore

from .base import BaseAdapter

# ----------------------------
# Tunables
# ----------------------------
_MAX_PARALLEL = 6             # cap concurrent calls inside adapter (protects against 429/999)
_MAX_RETRIES = 4              # backoff attempts per call
_BASE_BACKOFF = 0.75          # seconds
_CACHE_EXPIRE_SEC = 15 * 60   # if requests_cache available

# A small pool of common desktop UA strings (rotated per session)
_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]

# One adapter-wide semaphore to avoid spamming Yahoo
_SEM = None  # initialized in __init__


def _make_session(idx: int) -> CurlSession:
    """Create a session with rotated UA and optional caching."""
    ua = _UAS[idx % len(_UAS)]
    if CachedSession is not None:
        s: CurlSession = CachedSession(
            cache_name="yf-cache",
            backend="sqlite",
            expire_after=_CACHE_EXPIRE_SEC,
        )
    else:
        s = CurlSession()
    try:
        s.headers.update({"User-Agent": ua, "Accept": "application/json,text/plain,*/*"})
    except Exception:
        pass
    return s


def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        # unwrap pandas scalars/Series
        if hasattr(x, "iloc"):
            x = x.iloc[0]  # type: ignore[attr-defined]
        val = float(x)
        if not math.isfinite(val):
            return None
        return val
    except Exception:
        return None


def _first_key(d: Dict[str, Any], keys: Iterable[str]) -> Any:
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def _normalize_df(df) -> Optional["pd.DataFrame"]:  # type: ignore[name-defined]
    if df is None:
        return None
    if pd is None:
        return None
    if isinstance(df, pd.DataFrame):
        return df
    # yfinance sometimes returns dict-like
    try:
        return pd.DataFrame(df)
    except Exception:
        return None


def _match_row_index(df: "pd.DataFrame", candidates: Iterable[str]) -> Optional[str]:  # type: ignore[name-defined]
    """Find a row label in df.index that matches any candidate (case/space-insensitive)."""
    if pd is None or df is None or df.empty:
        return None
    idx_map = {str(i).strip().lower().replace(" ", ""): i for i in df.index}
    for c in candidates:
        key = str(c).strip().lower().replace(" ", "")
        if key in idx_map:
            return idx_map[key]
    # loose contains match
    for c in candidates:
        key = str(c).strip().lower().replace(" ", "")
        for k_norm, orig in idx_map.items():
            if key in k_norm:
                return orig
    return None


def _sum_last_n(df: "pd.DataFrame", row_label: str, n: int = 4) -> Optional[float]:  # type: ignore[name-defined]
    if pd is None or df is None or df.empty or row_label not in df.index:
        return None
    try:
        row = df.loc[row_label]
        # Row may be Series (columns are periods)
        vals = pd.to_numeric(row, errors="coerce").dropna().values
        if vals.size == 0:
            return None
        return float(pd.Series(vals).tail(n).sum())
    except Exception:
        return None


@dataclass
class _FieldPack:
    price: Optional[float] = None
    eps_ttm: Optional[float] = None
    sales_per_share: Optional[float] = None
    pe_ttm: Optional[float] = None
    ps_ttm: Optional[float] = None
    growth_pct: Optional[float] = None
    ps_history: Optional[List[float]] = None
    net_income_ttm: Optional[float] = None
    revenue_ttm: Optional[float] = None

    def as_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        if self.price is not None:
            out["price"] = float(self.price)
        if self.eps_ttm is not None:
            out["eps_ttm"] = float(self.eps_ttm)
        if self.sales_per_share is not None:
            out["sales_per_share"] = float(self.sales_per_share)
        if self.pe_ttm is not None:
            out["pe_ttm"] = float(self.pe_ttm)
        if self.ps_ttm is not None:
            out["ps_ttm"] = float(self.ps_ttm)
        if self.growth_pct is not None:
            out["growth_pct"] = float(self.growth_pct)
        if self.ps_history is not None:
            out["ps_history"] = self.ps_history
        if self.net_income_ttm is not None:
            out["net_income_ttm"] = float(self.net_income_ttm)
        if self.revenue_ttm is not None:
            out["revenue_ttm"] = float(self.revenue_ttm)
        return out


class YFinanceAdapter(BaseAdapter):
    """
    Resilient yfinance adapter with session pool, UA rotation, caching & backoff.

    Fields provided (when available/derivable):
      - price
      - eps_ttm               (derived from Net Income TTM / Shares Outstanding, or EPS rows)
      - sales_per_share       (Total Revenue TTM / Shares Outstanding)
      - pe_ttm                (price / eps_ttm)
      - ps_ttm                (price / sales_per_share)
      - growth_pct            (revenue growth percentage)
      - ps_history            (historical P/S ratios)
    """

    name = "yfinance"
    fields_provided = ["price", "eps_ttm", "sales_per_share", "pe_ttm", "ps_ttm", "growth_pct", "ps_history", "net_income_ttm", "revenue_ttm"]

    def __init__(self, logger=None, **kwargs):
        super().__init__(logger=logger, **kwargs)
        global _SEM
        if _SEM is None:
            _SEM = __import__("threading").Semaphore(_MAX_PARALLEL)

        # Create a small pool of sessions and use round-robin
        self._sessions = [_make_session(i) for i in range(_MAX_PARALLEL)]
        self._rr = 0

    def _next_session(self) -> CurlSession:
        self._rr = (self._rr + 1) % len(self._sessions)
        return self._sessions[self._rr]

    # ----------------------------
    # Backoff wrapper
    # ----------------------------
    def _call_with_backoff(self, fn, *args, **kwargs):
        for attempt in range(_MAX_RETRIES):
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                msg = str(e).lower()
                is_rl = any(k in msg for k in ["rate limit", "429", "too many requests", "999"])
                is_tmp = any(k in msg for k in ["timed out", "temporarily unavailable", "connection reset"])
                if not is_rl and not is_tmp:
                    raise
                sleep = _BASE_BACKOFF * (2 ** attempt) + random.uniform(0.05, 0.35)
                if self.logger:
                    self.logger.debug(f"[yfinance] backoff {attempt+1}/{_MAX_RETRIES} ({sleep:.2f}s): {e}")
                time.sleep(sleep)
        # Final attempt: swallow error, return None
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            if self.logger:
                self.logger.debug(f"[yfinance] giving up after retries: {e}")
            return None

    # ----------------------------
    # Price (light paths first)
    # ----------------------------
    def _fetch_price(self, tk: yf.Ticker) -> Optional[float]:
        # 1) fast_info
        try:
            fi = self._call_with_backoff(lambda: getattr(tk, "fast_info", None))
            if isinstance(fi, dict) and fi:
                p = _first_key(fi, ["last_price", "lastPrice", "regularMarketPrice"])
                p = _safe_float(p)
                if p is None:  # sometimes fast_info fields are Series/arrays
                    p = _safe_float(_first_key(fi, ["last_price", "regularMarketPrice"]))
                if p is not None:
                    return p
        except Exception:
            pass

        # 2) history (very light)
        hist = self._call_with_backoff(lambda: tk.history(period="1d", interval="1d", auto_adjust=False))
        try:
            if hist is not None and not hist.empty and "Close" in hist.columns:
                return _safe_float(hist["Close"].iloc[-1])
        except Exception:
            pass

        # 3) download fallback (heavier)
        try:
            df = self._call_with_backoff(
                lambda: yf.download(
                    [tk.ticker],
                    period="1d",
                    interval="1d",
                    auto_adjust=False,
                    progress=False,
                    group_by="column",
                    threads=False,  # we control concurrency ourselves
                    session=getattr(tk, "_session", None),
                    timeout=8,
                )
            )
            if df is not None and hasattr(df, "empty") and not df.empty:
                if "Close" in getattr(df, "columns", []):
                    return _safe_float(df["Close"].iloc[-1])
                if (tk.ticker, "Close") in getattr(df, "columns", []):  # multi-index fallback
                    return _safe_float(df[(tk.ticker, "Close")].iloc[-1])
        except Exception:
            pass

        return None

    # ----------------------------
    # Shares outstanding
    # ----------------------------
    def _fetch_shares_outstanding(self, tk: yf.Ticker) -> Optional[float]:
        # Try fast_info first
        try:
            fi = getattr(tk, "fast_info", None)
            if isinstance(fi, dict) and fi:
                sh = _first_key(fi, ["sharesOutstanding", "shares_outstanding"])
                sh = _safe_float(sh)
                if sh and sh > 0:
                    return sh
        except Exception:
            pass

        # Fallback: get_shares_full (heavier, but sometimes necessary)
        try:
            df = self._call_with_backoff(lambda: tk.get_shares_full())  # type: ignore[attr-defined]
            df = _normalize_df(df)
            if df is not None and not df.empty:
                # Take the last known shares (diluted if present)
                last_row = df.sort_index().iloc[-1]
                # Common column names seen: 'Shares', 'BasicShares', 'DilutedShares'
                for c in ["DilutedShares", "BasicShares", "Shares", "Share Issued"]:
                    if c in last_row.index:
                        sh = _safe_float(last_row[c])
                        if sh and sh > 0:
                            return sh
                # Or if it's a Series of one value
                sh = _safe_float(last_row)
                if sh and sh > 0:
                    return sh
        except Exception:
            pass

        # As a very last resort, info (heavy, often rate-limited) — try once
        try:
            info = self._call_with_backoff(lambda: tk.get_info())
            if isinstance(info, dict):
                sh = _safe_float(_first_key(info, ["sharesOutstanding"]))
                if sh and sh > 0:
                    return sh
        except Exception:
            pass

        return None

    # ----------------------------
    # Growth percentage (for Peter Lynch)
    # ----------------------------
    def _fetch_growth_pct(self, tk: yf.Ticker) -> Optional[float]:
        # Try to get revenue growth from quarterly statements
        try:
            q_is = self._call_with_backoff(lambda: getattr(tk, "quarterly_income_stmt", None))
            q_is = _normalize_df(q_is)
            
            if q_is is not None and not q_is.empty:
                rev_label = _match_row_index(q_is, ["Total Revenue", "TotalRevenue", "Revenue"])
                if rev_label:
                    # Get last 8 quarters (2 years) of revenue data
                    row = q_is.loc[rev_label]
                    vals = pd.to_numeric(row, errors="coerce").dropna().values
                    if len(vals) >= 4:
                        # Calculate year-over-year growth
                        recent_4q = vals[:4].sum()  # Last 4 quarters
                        older_4q = vals[4:8].sum() if len(vals) >= 8 else vals[4:].sum()  # Previous 4 quarters
                        
                        if older_4q > 0:
                            growth = (recent_4q / older_4q - 1.0) * 100
                            return round(growth, 2)
        except Exception:
            pass

        # Fallback: try annual statements
        try:
            a_is = self._call_with_backoff(lambda: getattr(tk, "income_stmt", None))
            a_is = _normalize_df(a_is)
            
            if a_is is not None and not a_is.empty:
                rev_label = _match_row_index(a_is, ["Total Revenue", "TotalRevenue", "Revenue"])
                if rev_label:
                    row = a_is.loc[rev_label]
                    vals = pd.to_numeric(row, errors="coerce").dropna().values
                    if len(vals) >= 2:
                        # Calculate year-over-year growth
                        recent = vals[0]  # Most recent year
                        previous = vals[1]  # Previous year
                        
                        if previous > 0:
                            growth = (recent / previous - 1.0) * 100
                            return round(growth, 2)
        except Exception:
            pass

        return None

    # ----------------------------
    # P/S History (for PSales Reversion)
    # ----------------------------
    def _fetch_ps_history(self, tk: yf.Ticker, price: Optional[float], sales_per_share: Optional[float]) -> Optional[List[float]]:
        if price is None or sales_per_share is None or sales_per_share <= 0:
            return None
            
        # Calculate current P/S ratio
        current_ps = price / sales_per_share
        
        # Try to get historical P/S ratios from quarterly data
        try:
            q_is = self._call_with_backoff(lambda: getattr(tk, "quarterly_income_stmt", None))
            q_is = _normalize_df(q_is)
            
            if q_is is not None and not q_is.empty:
                rev_label = _match_row_index(q_is, ["Total Revenue", "TotalRevenue", "Revenue"])
                if rev_label:
                    # Get historical revenue data
                    row = q_is.loc[rev_label]
                    rev_vals = pd.to_numeric(row, errors="coerce").dropna().values
                    
                    # Get shares outstanding for historical periods
                    shares_out = self._fetch_shares_outstanding(tk)
                    if shares_out and shares_out > 0:
                        # Calculate historical P/S ratios (last 12 quarters)
                        ps_history = []
                        for i in range(min(12, len(rev_vals))):
                            if rev_vals[i] > 0:
                                # Estimate historical price (simplified - could be improved)
                                # For now, use current price as approximation
                                hist_sps = rev_vals[i] / shares_out
                                if hist_sps > 0:
                                    hist_ps = price / hist_sps  # Using current price as approximation
                                    ps_history.append(round(hist_ps, 2))
                        
                        if ps_history:
                            return ps_history
        except Exception:
            pass

        # Fallback: return current P/S as single value
        return [round(current_ps, 2)]

    # ----------------------------
    # Fundamentals (TTM from quarterlies)
    # ----------------------------
    def _fetch_ttm_net_income_and_revenue(self, tk: yf.Ticker) -> (Optional[float], Optional[float]):
        q_is = self._call_with_backoff(lambda: getattr(tk, "quarterly_income_stmt", None))
        q_is = _normalize_df(q_is)

        # yfinance sometimes returns transposed: rows are items, columns are periods (what we want).
        # Find matching rows for Net Income and Total Revenue and sum last 4 columns.
        net_income = revenue = None
        if q_is is not None and not q_is.empty:
            ni_label = _match_row_index(q_is, ["Net Income", "NetIncome", "Net Income Common Stockholders"])
            rev_label = _match_row_index(q_is, ["Total Revenue", "TotalRevenue", "Revenue"])
            if ni_label:
                net_income = _sum_last_n(q_is, ni_label, n=4)
            if rev_label:
                revenue = _sum_last_n(q_is, rev_label, n=4)

        # Fallback to annual (single year) if quarterly not present
        if (net_income is None or revenue is None):
            a_is = self._call_with_backoff(lambda: getattr(tk, "income_stmt", None))
            a_is = _normalize_df(a_is)
            if a_is is not None and not a_is.empty:
                if net_income is None:
                    ni_label = _match_row_index(a_is, ["Net Income", "NetIncome", "Net Income Common Stockholders"])
                    if ni_label:
                        try:
                            net_income = _safe_float(a_is.loc[ni_label].dropna().iloc[-1])
                        except Exception:
                            pass
                if revenue is None:
                    rev_label = _match_row_index(a_is, ["Total Revenue", "TotalRevenue", "Revenue"])
                    if rev_label:
                        try:
                            revenue = _safe_float(a_is.loc[rev_label].dropna().iloc[-1])
                        except Exception:
                            pass

        return net_income, revenue

    # ----------------------------
    # Derive EPS_TTM & Sales/Share TTM
    # ----------------------------
    def _derive_eps_and_sps(self, tk: yf.Ticker, price: Optional[float]) -> _FieldPack:
        fp = _FieldPack(price=price)

        # Try info first for quick wins (best effort, may be empty)
        try:
            info = self._call_with_backoff(lambda: tk.get_info())
        except Exception:
            info = None

        if isinstance(info, dict) and info:
            eps = _safe_float(_first_key(info, ["trailingEps"]))
            if eps is not None:
                fp.eps_ttm = eps
            sps = _safe_float(_first_key(info, ["revenuePerShare"]))
            if sps is not None:
                fp.sales_per_share = sps
            pe = _safe_float(_first_key(info, ["trailingPE"]))
            if pe is not None:
                fp.pe_ttm = pe
            ps = _safe_float(_first_key(info, ["priceToSalesTrailing12Months"]))
            if ps is not None:
                fp.ps_ttm = ps

        # If we still need EPS/SPS, derive them from statements + shares
        if fp.eps_ttm is None or fp.sales_per_share is None or fp.pe_ttm is None or fp.ps_ttm is None:
            net_income_ttm, revenue_ttm = self._fetch_ttm_net_income_and_revenue(tk)
            shares_out = self._fetch_shares_outstanding(tk)

            # Store raw net income and revenue for margin calculations
            if net_income_ttm is not None:
                fp.net_income_ttm = net_income_ttm
            if revenue_ttm is not None:
                fp.revenue_ttm = revenue_ttm

            # EPS_TTM = NetIncome_TTM / SharesOutstanding
            if fp.eps_ttm is None and net_income_ttm is not None and shares_out and shares_out > 0:
                fp.eps_ttm = net_income_ttm / shares_out

            # Sales/Share_TTM = Revenue_TTM / SharesOutstanding
            if fp.sales_per_share is None and revenue_ttm is not None and shares_out and shares_out > 0:
                fp.sales_per_share = revenue_ttm / shares_out

            # PE/PS from derived values if still missing
            if fp.pe_ttm is None and fp.eps_ttm and fp.eps_ttm != 0 and price is not None:
                fp.pe_ttm = price / fp.eps_ttm

            if fp.ps_ttm is None and fp.sales_per_share and fp.sales_per_share != 0 and price is not None:
                fp.ps_ttm = price / fp.sales_per_share

        # Fetch additional fields
        fp.growth_pct = self._fetch_growth_pct(tk)
        fp.ps_history = self._fetch_ps_history(tk, price, fp.sales_per_share)

        return fp

    # ----------------------------
    # Adapter interface
    # ----------------------------
    def fetch_one(self, ticker: str) -> Dict[str, Any]:
        """Fetch minimal fields needed by our strategies with retries and rate limiting."""
        sess = self._next_session()

        with _SEM:  # protect Yahoo endpoints from being spammed
            tk = yf.Ticker(ticker, session=sess)

            price = self._fetch_price(tk)
            if price is None and self.logger:
                self.logger.debug(f"[yfinance] {ticker}: price not found via light paths")

            fp = self._derive_eps_and_sps(tk, price)

        out = fp.as_dict()
        if self.logger:
            got = ", ".join(sorted(out.keys())) or "none"
            self.logger.debug(f"[yfinance] {ticker}: fields={got}")
        return out
