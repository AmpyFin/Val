# Adapters/polygon.py
from __future__ import annotations
from .base import BaseAdapter
from typing import Dict, Any, Optional
import os
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

POLY_BASE = "https://api.polygon.io"

def _pick(*vals):
    for v in vals:
        if v is not None:
            try:
                fv = float(v)
                if fv == fv:  # not NaN
                    return fv
            except Exception:
                pass
    return None

@retry(
    reraise=True,
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
    retry=retry_if_exception_type(httpx.HTTPError),
)
def _get_json(url: str, params: Optional[dict] = None, headers: Optional[dict] = None) -> Any:
    with httpx.Client(timeout=6.0) as c:
        r = c.get(url, params=params, headers=headers)
        r.raise_for_status()
        return r.json()

class PolygonAdapter(BaseAdapter):
    name = "polygon"
    fields_provided = ["price"]

    def fetch_one(self, ticker: str) -> Dict[str, Any]:
        key = os.getenv("POLYGON_API_KEY")
        if not key:
            if self.logger:
                self.logger.debug("[polygon] POLYGON_API_KEY missing; skipping")
            return {}

        price = None

        # Try latest trade endpoint (v2)
        try:
            data = _get_json(f"{POLY_BASE}/v2/last/trade/{ticker}", params={"apiKey": key})
            # Response schemas have varied; try common shapes:
            price = _pick(
                (data.get("trade") or {}).get("p"),
                (data.get("results") or {}).get("p"),
                data.get("p"),
            )
        except Exception as e:
            if self.logger:
                self.logger.debug(f"[polygon] last trade failed for {ticker}: {e}")

        # Fallback: previous aggregate close
        if price is None:
            try:
                data = _get_json(f"{POLY_BASE}/v2/aggs/ticker/{ticker}/prev", params={"adjusted": "true", "apiKey": key})
                results = data.get("results") or []
                if results:
                    price = _pick(results[0].get("c"), results[0].get("vw"))
            except Exception as e:
                if self.logger:
                    self.logger.debug(f"[polygon] prev agg failed for {ticker}: {e}")

        return {"price": price} if price is not None else {}

