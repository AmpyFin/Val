# pipeline/stages/result_stage.py
"""
AmpyFin — Val Model
Result Stage (GUI override-capable)

Adds consensus dispersion bands:
- P25 (25th percentile), P75 (75th percentile) of per-strategy fair values

Outputs per run:
  * Console summary (with P25/P75)
  * Optional UDP broadcast (if Broadcast_mode=True)
  * Optional JSON dump (if Json_dump_enable=True in control.py)
  * Optional MongoDB storage (if MONGODB_ENABLE=True in control.py)
  * Optional minimal GUI (single-shot) and full live GUI (ui.viewer)
"""

from __future__ import annotations

import math
import os
import socket
import statistics
import time
from datetime import datetime
from typing import List, Optional, Tuple

import control
from pipeline.context import PipelineContext
from pipeline.stages.mongodb_storage import store_results_in_mongodb


def _median_ignoring_none(values: List[Optional[float]]) -> Optional[float]:
    vals = [v for v in values if isinstance(v, (int, float)) and not math.isnan(float(v))]
    if not vals:
        return None
    try:
        return float(statistics.median(vals))
    except Exception:
        return None


def _percentile(values: List[Optional[float]], p: float) -> Optional[float]:
    """
    Linear interpolation percentile: p in [0,1].
    Ignores None/NaN. Returns None if no data.
    """
    xs = [float(v) for v in values if isinstance(v, (int, float)) and not math.isnan(float(v))]
    n = len(xs)
    if n == 0:
        return None
    xs.sort()
    if n == 1:
        return xs[0]
    p = max(0.0, min(1.0, float(p)))
    idx = (n - 1) * p
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return xs[lo]
    frac = idx - lo
    return xs[lo] + (xs[hi] - xs[lo]) * frac


def _pct_diff(fair: Optional[float], price: Optional[float]) -> Optional[float]:
    if fair is None or price is None:
        return None
    if price == 0:
        return None
    try:
        return (fair / price) - 1.0
    except Exception:
        return None


def _console_print_summary(ctx: PipelineContext) -> None:
    """Console table: adds P25/P75 columns."""
    rows: List[Tuple[str, Optional[float], Optional[float], Optional[float], Optional[float], Optional[float]]] = []
    for tk in ctx.tickers:
        bt = ctx.results_by_ticker.get(tk, {})
        rows.append(
            (
                tk,
                bt.get("current_price"),
                bt.get("consensus_fair_value"),
                bt.get("consensus_discount"),
                bt.get("consensus_p25"),
                bt.get("consensus_p75"),
            )
        )

    print("\n==== AmpyFin Val Model — Results ====")
    print(f"Run at: {ctx.generated_at_iso or ''}")
    print(f"Strategies: {', '.join(ctx.strategy_names)}")
    print("-" * 84)
    print(f"{'Ticker':<8} {'Price':>12} {'Consensus FV':>16} {'Discount%':>12} {'P25 FV':>12} {'P75 FV':>12}")
    print("-" * 84)

    def fmtf(v: Optional[float], places: int = 2) -> str:
        return f"{v:.{places}f}" if isinstance(v, (int, float)) else "-"

    for tk, cur, cons, disc, p25, p75 in rows:
        disc_pct = f"{disc*100:,.1f}%" if isinstance(disc, (int, float)) else "-"
        print(
            f"{tk:<8} {fmtf(cur,2):>12} {fmtf(cons,2):>16} {disc_pct:>12} {fmtf(p25,2):>12} {fmtf(p75,2):>12}"
        )

    print("-" * 84)

    # Top 5 most undervalued by consensus
    scored = [(tk, ctx.results_by_ticker.get(tk, {}).get("consensus_discount")) for tk in ctx.tickers]
    scored = [x for x in scored if isinstance(x[1], (int, float))]
    scored.sort(key=lambda x: x[1], reverse=True)
    if scored:
        print("Top (potentially) undervalued by consensus:")
        for tk, s in scored[:5]:
            print(f"  {tk}: {s*100:.1f}%")
    print()


def _broadcast_udp(ctx: PipelineContext) -> Optional[str]:
    """Broadcast results over UDP as a compact JSON-like string (without file writing)."""
    try:
        import json
        payload_obj = {
            "generated_at": ctx.generated_at,
            "generated_at_iso": ctx.generated_at_iso,
            "tickers": ctx.tickers,
            "strategy_names": ctx.strategy_names,
            "by_ticker": ctx.results_by_ticker,  # includes consensus_p25 / consensus_p75 and per-strategy FVs
            "fetch_errors": ctx.fetch_errors,
            "strategy_errors": ctx.strategy_errors,
        }
        payload = json.dumps(payload_obj, separators=(",", ":")).encode("utf-8")
        addr = (
            getattr(control, "BROADCAST_NETWORK", "127.0.0.1"),
            int(getattr(control, "BROADCAST_PORT", 5002)),
        )
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2.0)
        sent = sock.sendto(payload, addr)
        sock.close()
        return f"sent {sent} bytes to {addr[0]}:{addr[1]}"
    except Exception as e:
        return f"broadcast failed: {e}"


def _dump_json(ctx: PipelineContext) -> Optional[str]:
    """Persist the full run as JSON (including per-strategy fair values)."""
    if not getattr(control, "JSON_DUMP_ENABLE", False):
        return None
    try:
        import json

        out_dir = getattr(control, "JSON_DUMP_DIR", "out") or "out"
        os.makedirs(out_dir, exist_ok=True)

        ts = int(ctx.generated_at or time.time())
        fname = f"val_results_{ts}.json"
        fpath = os.path.join(out_dir, fname)

        payload_obj = {
            "generated_at": ctx.generated_at,
            "generated_at_iso": ctx.generated_at_iso,
            "tickers": ctx.tickers,
            "strategy_names": ctx.strategy_names,
            "by_ticker": ctx.results_by_ticker,  # includes current_price, consensus, P25/P75, strategy_fair_values
            "fetch_errors": ctx.fetch_errors,
            "strategy_errors": ctx.strategy_errors,
        }

        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(payload_obj, f, indent=2, ensure_ascii=False)

        print(f"[result_stage] JSON written to {fpath}")
        return fpath
    except Exception as e:
        return f"json dump failed: {e}"


def _store_mongodb(ctx: PipelineContext) -> Optional[str]:
    """Store the full run in MongoDB."""
    if not getattr(control, "MONGODB_ENABLE", False):
        return None
    try:
        return store_results_in_mongodb(ctx, clear_existing=True)
    except Exception as e:
        return f"mongodb storage failed: {e}"


def _show_gui(ctx: PipelineContext) -> Optional[str]:
    """Minimal one-shot GUI (blocking). Now shows P25/P75 columns."""
    try:
        from PyQt5 import QtCore, QtWidgets  # type: ignore
    except Exception as e:
        return f"GUI unavailable: {e}"

    app = QtWidgets.QApplication([])
    w = QtWidgets.QWidget()
    w.setWindowTitle("AmpyFin — Val Results")
    layout = QtWidgets.QVBoxLayout(w)

    title = QtWidgets.QLabel(f"Generated at: {ctx.generated_at_iso or ''}")
    layout.addWidget(title)

    headers = ["Ticker", "Price", "Consensus FV", "Discount %", "P25 FV", "P75 FV"] + ctx.strategy_names
    table = QtWidgets.QTableWidget()
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setRowCount(len(ctx.tickers))

    def fmt(v: Optional[float], p: int = 2) -> str:
        return f"{v:.{p}f}" if isinstance(v, (int, float)) else "-"

    for r, tk in enumerate(ctx.tickers):
        bt = ctx.results_by_ticker.get(tk, {})
        cells = [
            tk,
            fmt(bt.get("current_price")),
            fmt(bt.get("consensus_fair_value")),
            (f"{bt.get('consensus_discount')*100:.1f}%" if isinstance(bt.get("consensus_discount"), (int, float)) else "-"),
            fmt(bt.get("consensus_p25")),
            fmt(bt.get("consensus_p75")),
        ]
        for sname in ctx.strategy_names:
            fv = (bt.get("strategy_fair_values") or {}).get(sname)
            cells.append(fmt(fv))

        for c, text in enumerate(cells):
            item = QtWidgets.QTableWidgetItem(str(text))
            if c == 0:
                item.setFlags(item.flags() ^ QtCore.Qt.ItemIsEditable)
            table.setItem(r, c, item)

    table.resizeColumnsToContents()
    layout.addWidget(table)

    w.resize(1000, 520)
    w.show()
    app.exec_()
    return "GUI shown."


def run_result_stage(ctx: PipelineContext, show_gui: Optional[bool] = None) -> PipelineContext:
    """
    Build per-ticker results with consensus P25/P50/P75 and execute outputs.
    """
    ctx.reset_results()

    now = time.time()
    now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    ctx.generated_at = now
    ctx.generated_at_iso = now_iso

    # Build per-ticker results
    for tk in ctx.tickers:
        current_price = ctx.metrics_by_ticker.get(tk, {}).get("current_price")
        fair_map = ctx.fair_values.get(tk, {}) or {}

        values = [fair_map.get(s) for s in ctx.strategy_names]
        cons = _median_ignoring_none(values)
        p25 = _percentile(values, 0.25)
        p75 = _percentile(values, 0.75)
        disc = _pct_diff(cons, current_price)

        ctx.results_by_ticker[tk] = {
            "current_price": current_price,
            "strategy_fair_values": fair_map,
            "consensus_fair_value": cons,
            "consensus_discount": disc,
            "consensus_p25": p25,
            "consensus_p75": p75,
        }

    # --- Outputs ---
    _console_print_summary(ctx)

    if getattr(control, "BROADCAST_MODE", False):
        ctx.side_effects["broadcast"] = _broadcast_udp(ctx)

    if getattr(control, "JSON_DUMP_ENABLE", False):
        ctx.side_effects["json_dump"] = _dump_json(ctx)

    if getattr(control, "MONGODB_ENABLE", False):
        ctx.side_effects["mongodb"] = _store_mongodb(ctx)

    do_gui = getattr(control, "GUI_MODE", False) if show_gui is None else bool(show_gui)
    ctx.side_effects["gui"] = _show_gui(ctx) if do_gui else None

    return ctx
