# Adapters/yfinance.py
from __future__ import annotations
from .base import BaseAdapter
from typing import Dict, Any, Optional, List
import logging
import math

import pandas as pd
import yfinance as yf

def _try_keys(d: dict, keys: List[str]) -> Optional[float]:
    for k in keys:
        if k in d and d[k] is not None:
            try:
                v = float(d[k])
                if math.isfinite(v):
                    return v
            except Exception:
                continue
    return None

def _last_price_fast(tk: yf.Ticker) -> Optional[float]:
    # Try fast_info first; fall back to a quick history call
    try:
        fi = getattr(tk, "fast_info", {}) or {}
        for k in ("lastPrice", "last_price", "regularMarketPrice", "last_trade_price"):
            v = fi.get(k)
            if v is not None and math.isfinite(float(v)):
                return float(v)
    except Exception:
        pass
    try:
        hist = tk.history(period="1d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass
    return None

def _revenue_ttm(tk: yf.Ticker) -> Optional[float]:
    # Sum last 4 quarters of Total Revenue
    try:
        inc_q = tk.quarterly_income_stmt
        if isinstance(inc_q, pd.DataFrame) and not inc_q.empty:
            # yfinance uses line items as rows, periods as columns
            for label in ("Total Revenue", "TotalRevenue", "Revenue", "TotalRevenueTTM"):
                if label in inc_q.index:
                    vals = pd.to_numeric(inc_q.loc[label].dropna(), errors="coerce")
                    vals = vals[~vals.isna()]
                    if len(vals) >= 4:
                        return float(vals.iloc[:4].sum())
                    elif len(vals) > 0:
                        return float(vals.sum())  # fallback if <4 quarters available
    except Exception:
        pass
    # Fallback to yearly if quarterly missing
    try:
        inc_y = tk.income_stmt
        if isinstance(inc_y, pd.DataFrame) and not inc_y.empty:
            for label in ("Total Revenue", "TotalRevenue", "Revenue"):
                if label in inc_y.index:
                    vals = pd.to_numeric(inc_y.loc[label].dropna(), errors="coerce")
                    vals = vals[~vals.isna()]
                    if len(vals) >= 1:
                        return float(vals.iloc[0])
    except Exception:
        pass
    return None

def _shares_outstanding(tk: yf.Ticker) -> Optional[float]:
    # Prefer info dict, fallback to shares history (latest)
    try:
        info = tk.get_info()
        so = _try_keys(info or {}, ["sharesOutstanding"])
        if so is not None:
            return so
    except Exception:
        pass
    try:
        sh = tk.get_shares_full(start=None, end=None)
        if isinstance(sh, pd.DataFrame) and not sh.empty:
            # Use the latest row's OutstandingShares or SharesOutstanding
            for col in ("SharesOutstanding", "shares", "OutstandingShares"):
                if col in sh.columns:
                    series = pd.to_numeric(sh[col], errors="coerce").dropna()
                    if not series.empty:
                        return float(series.iloc[-1])
    except Exception:
        pass
    return None

def _eps_ttm(tk: yf.Ticker) -> Optional[float]:
    # Most reliable from info['trailingEps'] when present
    try:
        info = tk.get_info()
        eps = _try_keys(info or {}, ["trailingEps"])
        if eps is not None:
            return eps
    except Exception:
        pass
    # Fallback: derive from net income TTM per share if available (rare via yfinance)
    return None

def _ps_history_from_price_and_sps(tk: yf.Ticker, sps: Optional[float]) -> Optional[List[float]]:
    if sps is None or sps <= 0:
        return None
    try:
        prices = tk.history(period="3y", interval="1mo")["Close"].dropna()
        if prices.empty:
            return None
        ps = (prices / float(sps)).astype(float)
        # Last ~12 monthly points
        return [round(x, 4) for x in ps.tail(12).tolist()]
    except Exception:
        return None

def _revenue_cagr_pct(tk: yf.Ticker) -> Optional[float]:
    # Compute simple CAGR from yearly Total Revenue if >=3 points
    try:
        inc_y = tk.income_stmt
        if isinstance(inc_y, pd.DataFrame) and not inc_y.empty:
            for label in ("Total Revenue", "TotalRevenue", "Revenue"):
                if label in inc_y.index:
                    vals = pd.to_numeric(inc_y.loc[label].dropna(), errors="coerce")
                    vals = vals[~vals.isna()]
                    if len(vals) >= 3:
                        # Columns are timestamps descending; use last (oldest) and first (newest)
                        newest = float(vals.iloc[0])
                        oldest = float(vals.iloc[-1])
                        years = max(1, len(vals) - 1)
                        if newest > 0 and oldest > 0:
                            cagr = (newest / oldest) ** (1.0 / years) - 1.0
                            return round(100.0 * cagr, 2)
    except Exception:
        pass
    return None

class YFinanceAdapter(BaseAdapter):
    name = "yfinance"
    # We can provide most of what we need for MVP fundamentals
    fields_provided = [
        "price",
        "eps_ttm",
        "sales_per_share",
        "ps_history",
        "growth_pct",
        "sector",
        "shares_outstanding",
    ]

    def fetch_one(self, ticker: str) -> Dict[str, Any]:
        tk = yf.Ticker(ticker)
        out: Dict[str, Any] = {}

        # Price
        price = _last_price_fast(tk)
        if price is not None:
            out["price"] = round(float(price), 4)

        # Shares & revenue TTM → sales per share
        shares = _shares_outstanding(tk)
        rev_ttm = _revenue_ttm(tk)
        if shares and shares > 0 and rev_ttm and rev_ttm > 0:
            sps = float(rev_ttm) / float(shares)
            out["sales_per_share"] = round(sps, 6)

        # EPS TTM (best-effort)
        eps = _eps_ttm(tk)
        if eps is not None:
            out["eps_ttm"] = round(float(eps), 6)

        # Sector (best-effort from info)
        try:
            info = tk.get_info()
            sector = (info or {}).get("sector")
            if isinstance(sector, str) and sector:
                out["sector"] = sector
        except Exception:
            pass

        # PS history (price history / current SPS)
        ps_hist = _ps_history_from_price_and_sps(tk, out.get("sales_per_share"))
        if ps_hist:
            out["ps_history"] = ps_hist

        # Growth proxy (revenue CAGR %)
        growth = _revenue_cagr_pct(tk)
        if growth is not None:
            out["growth_pct"] = float(growth)

        # Shares outstanding
        if shares is not None:
            out["shares_outstanding"] = int(shares)

        return out
