# Adapters/fmp.py
from __future__ import annotations
from .base import BaseAdapter
from typing import Dict, Any, Optional, List
import os
import httpx
from statistics import median
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

FMP_BASE = "https://financialmodelingprep.com/api/v3"

def _pick(d: dict, keys: List[str]) -> Optional[float]:
    for k in keys:
        if k in d and d[k] is not None:
            try:
                v = float(d[k])
                if v == v:  # not NaN
                    return v
            except Exception:
                continue
    return None

@retry(
    reraise=True,
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
    retry=retry_if_exception_type(httpx.HTTPError),
)
def _get_json(url: str, params: Optional[dict] = None) -> Any:
    with httpx.Client(timeout=7.0) as c:
        r = c.get(url, params=params)
        r.raise_for_status()
        return r.json()

class FMPAdapter(BaseAdapter):
    name = "fmp"
    fields_provided = [
        "eps_ttm",
        "sales_per_share",
        "ps_history",
        "shares_outstanding",
        "growth_pct",  # best-effort (derived)
        "net_income_ttm",
        "revenue_ttm",
    ]

    def fetch_one(self, ticker: str) -> Dict[str, Any]:
        key = os.getenv("FINANCIAL_PREP_API_KEY") or os.getenv("FINANCIAL_MODELING_PREP_API_KEY")
        if not key:
            if self.logger:
                self.logger.debug("[fmp] FINANCIAL_PREP_API_KEY missing; skipping")
            return {}

        out: Dict[str, Any] = {}

        # 1) EPS TTM & Shares Outstanding (try key-metrics-ttm and profile)
        try:
            km = _get_json(f"{FMP_BASE}/key-metrics-ttm/{ticker}", params={"apikey": key})
            km0 = (km or [{}])[0] if isinstance(km, list) else {}
            eps_ttm = _pick(km0, ["epsTTM", "epsDilutedTTM", "epsNormalizedTTM"])
            sps_ttm = _pick(km0, ["salesPerShareTTM", "salesPerShare"])
            shares = _pick(km0, ["sharesOutstandingTTM", "sharesOutstanding"])
            if eps_ttm is not None:
                out["eps_ttm"] = round(eps_ttm, 4)
            if sps_ttm is not None:
                out["sales_per_share"] = round(sps_ttm, 4)
            if shares is not None:
                out["shares_outstanding"] = int(shares)
        except Exception as e:
            if self.logger:
                self.logger.debug(f"[fmp] key-metrics-ttm failed for {ticker}: {e}")

        if "shares_outstanding" not in out:
            try:
                prof = _get_json(f"{FMP_BASE}/profile/{ticker}", params={"apikey": key})
                p0 = (prof or [{}])[0] if isinstance(prof, list) else {}
                shares = _pick(p0, ["sharesOutstanding"])
                if shares is not None:
                    out["shares_outstanding"] = int(shares)
            except Exception as e:
                if self.logger:
                    self.logger.debug(f"[fmp] profile failed for {ticker}: {e}")

        # 2) Net Income and Revenue TTM
        try:
            inc = _get_json(f"{FMP_BASE}/income-statement/{ticker}", params={"limit": 1, "apikey": key})
            if isinstance(inc, list) and inc:
                row = inc[0]
                net_income = _pick(row, ["netIncome", "netIncomeTTM"])
                revenue = _pick(row, ["revenue", "revenueTTM", "totalRevenue"])
                if net_income is not None:
                    out["net_income_ttm"] = round(net_income, 2)
                if revenue is not None:
                    out["revenue_ttm"] = round(revenue, 2)
        except Exception as e:
            if self.logger:
                self.logger.debug(f"[fmp] income-statement failed for {ticker}: {e}")

        # 3) PS ratio history (for PSalesReversion)
        try:
            ratios = _get_json(f"{FMP_BASE}/ratios/{ticker}", params={"limit": 48, "apikey": key})
            ps_vals = []
            if isinstance(ratios, list):
                for row in ratios:
                    v = _pick(row, ["priceToSalesRatio"])
                    if v is not None:
                        ps_vals.append(float(v))
            if ps_vals:
                # use latest ~12 values as 'recent history'
                out["ps_history"] = ps_vals[:12] if len(ps_vals) >= 12 else ps_vals
        except Exception as e:
            if self.logger:
                self.logger.debug(f"[fmp] ratios failed for {ticker}: {e}")

        # 4) Derive growth_pct best-effort:
        #    Try revenue growth using income statements (annual).
        if "growth_pct" not in out:
            try:
                inc = _get_json(f"{FMP_BASE}/income-statement/{ticker}", params={"limit": 6, "apikey": key})
                revs = []
                if isinstance(inc, list):
                    for row in inc:
                        v = _pick(row, ["revenue", "revenueTTM", "totalRevenue"])
                        if v is not None:
                            revs.append(float(v))
                # Compute simple CAGR if we have >= 3 points
                if len(revs) >= 3:
                    first, last = revs[-1], revs[0]  # data often newest first
                    years = max(1, len(revs) - 1)
                    if first > 0 and last > 0:
                        cagr = (first / last) ** (1 / years) - 1.0
                        out["growth_pct"] = round(100.0 * cagr, 2)
            except Exception as e:
                if self.logger:
                    self.logger.debug(f"[fmp] income-statement growth derive failed for {ticker}: {e}")

        return out
