# Adapters/alpaca.py
from __future__ import annotations
from .base import BaseAdapter
from typing import Dict, Any, Optional
import os
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

ALP_BASE = "https://data.alpaca.markets"

@retry(
    reraise=True,
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
    retry=retry_if_exception_type(httpx.HTTPError),
)
def _get_json(url: str, headers: dict) -> Any:
    with httpx.Client(timeout=6.0) as c:
        r = c.get(url, headers=headers)
        r.raise_for_status()
        return r.json()

class AlpacaAdapter(BaseAdapter):
    name = "alpaca"
    fields_provided = ["price"]

    def fetch_one(self, ticker: str) -> Dict[str, Any]:
        key = os.getenv("ALPACA_API_KEY")
        secret = os.getenv("ALPACA_API_SECRET")
        if not key or not secret:
            if self.logger:
                self.logger.debug("[alpaca] ALPACA_API_KEY/SECRET missing; skipping")
            return {}

        headers = {
            "APCA-API-KEY-ID": key,
            "APCA-API-SECRET-KEY": secret,
        }

        price = None
        try:
            data = _get_json(f"{ALP_BASE}/v2/stocks/{ticker}/trades/latest", headers=headers)
            price = data.get("trade", {}).get("p")
            if price is not None:
                price = float(price)
        except Exception as e:
            if self.logger:
                self.logger.debug(f"[alpaca] latest trade failed for {ticker}: {e}")

        return {"price": price} if price is not None else {}
