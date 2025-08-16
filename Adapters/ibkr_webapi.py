# Adapters/ibkr_webapi.py
from __future__ import annotations
from .base import BaseAdapter
from typing import Dict, Any, Optional
import os
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

def _base_url() -> str:
    # Use HTTPS (IBeam’s gateway runs on https://localhost:5000 by default)
    # Example: https://localhost:5000
    return (os.getenv("IBEAM_GATEWAY_URL") or "https://localhost:5000").rstrip("/")

def _verify_tls() -> bool:
    """
    Self-signed cert on localhost will fail verification.
    Set IBEAM_INSECURE_TLS=true to disable verification (dev-only).
    Otherwise, try to be smart: disable verify for https://localhost/* automatically.
    """
    env_flag = os.getenv("IBEAM_INSECURE_TLS")
    if env_flag is not None:
        return not (env_flag.lower() in ("1", "true", "yes", "y"))
    base = _base_url()
    if base.startswith("https://localhost") or base.startswith("https://127.0.0.1"):
        return False
    return True

def _api_url(path: str) -> str:
    # Prefix all routes with /v1/api
    if not path.startswith("/"):
        path = "/" + path
    return f"{_base_url()}/v1/api{path}"

class IBKRAdapter(BaseAdapter):
    name = "ibkr"
    fields_provided = ["price"]
    _FIELDS_LAST_PRICE = "31"  # snapshot field for last price

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=10.0, verify=_verify_tls())

    # ---- low-level requests ---------------------------------------------------
    @retry(
        reraise=True,
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
        retry=retry_if_exception_type(httpx.HTTPError),
    )
    def _get(self, path: str, params: Optional[dict] = None) -> Any:
        with self._client() as c:
            r = c.get(_api_url(path), params=params)
            r.raise_for_status()
            return r.json()

    @retry(
        reraise=True,
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
        retry=retry_if_exception_type(httpx.HTTPError),
    )
    def _post(self, path: str, json_body: Optional[dict] = None) -> Any:
        with self._client() as c:
            r = c.post(_api_url(path), json=json_body or {})
            r.raise_for_status()
            return r.json()

    # ---- helpers --------------------------------------------------------------
    def _ensure_session(self) -> bool:
        """
        Tickle + check auth status. If not authenticated, try reauthenticate once.
        Returns True only if authenticated.
        """
        try:
            # keep-alive; OK if it fails, status check will tell us
            try:
                self._post("/tickle")
            except Exception:
                pass

            st = self._get("/iserver/auth/status")
            if st and st.get("authenticated"):
                return True

            # attempt reauth if available
            try:
                self._post("/iserver/reauthenticate")
            except Exception:
                pass

            st = self._get("/iserver/auth/status")
            return bool(st and st.get("authenticated"))
        except Exception as e:
            if self.logger:
                self.logger.debug(f"[ibkr] auth check failed: {e}")
            return False

    def _resolve_conid(self, symbol: str) -> Optional[int]:
        try:
            data = self._get("/trsrv/stocks", params={"symbols": symbol})
            # IBeam returns either a dict keyed by symbol → list[contracts], or a flat list
            items = []
            if isinstance(data, dict):
                items = data.get(symbol) or data.get(symbol.upper()) or []
            elif isinstance(data, list):
                items = data
            if items:
                first = items[0]
                conid = first.get("conid") or first.get("conidex")
                return int(conid) if conid is not None else None
        except Exception as e:
            if self.logger:
                self.logger.debug(f"[ibkr] conid lookup failed for {symbol}: {e}")
        return None

    def _snapshot_last(self, conid: int) -> Optional[float]:
        try:
            snap = self._get(
                "/iserver/marketdata/snapshot",
                params={"conids": str(conid), "fields": self._FIELDS_LAST_PRICE},
            )
            # Shape: list of rows, e.g. [{"conid":..., "31":"<price>", ...}]
            if isinstance(snap, list) and snap:
                v = snap[0].get(self._FIELDS_LAST_PRICE)
                return float(v) if v is not None else None
        except Exception as e:
            if self.logger:
                self.logger.debug(f"[ibkr] snapshot failed for conid={conid}: {e}")
        return None

    # ---- adapter API ----------------------------------------------------------
    def fetch_one(self, ticker: str) -> Dict[str, Any]:
        if not self._ensure_session():
            if self.logger:
                self.logger.debug("[ibkr] gateway not authenticated; skipping")
            return {}

        conid = self._resolve_conid(ticker)
        if not conid:
            return {}

        price = self._snapshot_last(conid)
        return {"price": price} if price is not None else {}
