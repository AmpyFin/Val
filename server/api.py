# server/api.py
from __future__ import annotations
from fastapi.responses import HTMLResponse
from pathlib import Path

import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query

# ---- Config helpers ---------------------------------------------------------

def _load_settings_path() -> str:
    # default location set in our README/steps
    return os.environ.get("AMPYFIN_RESULTS_PATH", "out/results.json")

RESULTS_PATH = _load_settings_path()

def _read_results(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Results file not found at: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _filter_undervalued(payload: Dict[str, Any], min_mos_override: Optional[float]) -> Dict[str, Any]:
    min_mos = float(min_mos_override) if min_mos_override is not None else float(payload.get("min_mos", 0.2))
    tickers = payload.get("tickers", [])
    uv = [t for t in tickers if t.get("undervalued") and (t.get("best_mos") or 0) >= min_mos]
    out = dict(payload)
    out["tickers"] = uv
    out["min_mos"] = min_mos
    return out

# ---- FastAPI app ------------------------------------------------------------

app = FastAPI(title="AmpyFin Val Model API", version="0.1.0")

WEB_DIR = Path(__file__).parent / "web"

@app.get("/", response_class=HTMLResponse)
def index():
    path = WEB_DIR / "index.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Missing {path}")
    return HTMLResponse(path.read_text(encoding="utf-8"))

@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat(), "results_path": RESULTS_PATH}

@app.get("/results")
def get_results(
    undervalued_only: bool = Query(False, description="Return only tickers at/above min_mos"),
    min_mos: Optional[float] = Query(None, description="Override Margin of Safety threshold (e.g., 0.2 = 20%)"),
):
    """
    Returns the latest snapshot written by the pipeline (out/results.json by default).
    - Set `undervalued_only=true` to filter by MoS.
    - Optionally override min_mos via querystring (?min_mos=0.25).
    """
    try:
        payload = _read_results(RESULTS_PATH)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Results file is not valid JSON yet")

    if undervalued_only:
        payload = _filter_undervalued(payload, min_mos)

    return payload

@app.websocket("/stream")
async def stream(ws: WebSocket):
    """
    Pushes the entire results payload whenever the file changes.
    Simple local dev stream: polls mtime every 2s.
    """
    await ws.accept()
    last_mtime = None
    try:
        while True:
            try:
                mtime = os.path.getmtime(RESULTS_PATH)
                if last_mtime is None or mtime != last_mtime:
                    last_mtime = mtime
                    payload = _read_results(RESULTS_PATH)
                    await ws.send_json(payload)
            except FileNotFoundError:
                await ws.send_json({"error": f"Results not found at {RESULTS_PATH}"})
            await ws.receive_text()  # keep the socket alive, client can send pings
    except WebSocketDisconnect:
        return
    except Exception as e:
        try:
            await ws.send_json({"error": str(e)})
        except Exception:
            pass
