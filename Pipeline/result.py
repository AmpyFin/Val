# Pipeline/result.py
from __future__ import annotations
from typing import List, Tuple, Dict, Any
from rich.console import Console
from rich.table import Table
from rich import box
import json, os
from datetime import datetime, timezone

def _fmt_money(x):
    return f"{float(x):,.2f}" if x is not None else "-"

def _fmt_pct(x):
    return f"{100.0*float(x):.1f}%" if x is not None else "-"

def _build_sorted_rows(ctx) -> List[Tuple[str, float, float, float, str, bool]]:
    summary = ctx.results.get("summary", {})
    rows: List[Tuple[str, float, float, float, str, bool]] = []
    for t, d in summary.items():
        price = d.get("price")
        fv = d.get("best_fv")
        mos = d.get("best_mos")
        strat = d.get("best_strategy")
        undervalued = bool(d.get("undervalued"))
        if price is None or fv is None or mos is None or strat is None:
            continue
        rows.append((t, price, fv, mos, strat, undervalued))
    rows.sort(key=lambda r: (r[3] if r[3] is not None else -1.0), reverse=True)
    return rows

def _export_json(ctx, rows: List[Tuple[str, float, float, float, str, bool]]):
    cfg = getattr(ctx, "config", None)
    if not cfg:
        return
    outputs: Dict[str, Any] = cfg.__dict__.get("outputs") if hasattr(cfg, "__dict__") else getattr(cfg, "outputs", None)
    if not outputs:
        return
    path = outputs.get("json_path")
    if not path:
        return

    os.makedirs(os.path.dirname(path), exist_ok=True)
    include_per_strategy = bool(outputs.get("include_per_strategy", True))

    # Build payload
    payload: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "min_mos": float(cfg.thresholds.get("min_mos", 0.20)),
        "tickers": [],
    }
    
    # Build ticker data with weights
    for (t, price, fv, mos, strat, uv) in rows:
        ticker_data = {
            "ticker": t,
            "price": float(price),
            "best_fair_value": float(fv),
            "best_mos": float(mos),
            "best_strategy": strat,
            "undervalued": bool(uv),
        }
        
        # Add weights if available
        summary = ctx.results.get("summary", {}).get(t, {})
        if "weights" in summary:
            ticker_data["weights"] = summary["weights"]
        
        payload["tickers"].append(ticker_data)
    if include_per_strategy:
        payload["per_strategy"] = ctx.results.get("per_strategy", {})

    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

def run(ctx, limit: int = 50):
    console = Console()
    rows = _build_sorted_rows(ctx)

    min_mos = float(ctx.config.thresholds.get("min_mos", 0.20))
    undervalued_rows = [r for r in rows if r[5]]
    total = len(rows)
    uv_count = len(undervalued_rows)

    console.print(
        f"[bold]AmpyFin Val Model[/bold] — "
        f"{uv_count} undervalued out of {total} (threshold: {int(min_mos*100)}%)"
    )

    def _render(title: str, data: List[Tuple], lim: int):
        table = Table(title=title, box=box.SIMPLE_HEAVY, show_lines=False)
        table.add_column("Ticker", style="bold")
        table.add_column("Price", justify="right")
        table.add_column("Fair Value", justify="right")
        table.add_column("MoS", justify="right")
        table.add_column("Strategy", justify="left")
        table.add_column("Weights", justify="left")

        for t, price, fv, mos, strat, _ in data[:lim]:
            mos_str = _fmt_pct(mos)
            if mos is not None and mos >= min_mos:
                mos_str = f"[green]{mos_str}[/green]"
            elif mos is not None and mos < 0:
                mos_str = f"[red]{mos_str}[/red]"

            # Get weights for display
            summary = ctx.results.get("summary", {}).get(t, {})
            weights = summary.get("weights", {})
            weights_str = ""
            if weights:
                pl_w = weights.get("peter_lynch", 0)
                ps_w = weights.get("psales_rev", 0)
                weights_str = f"PL:{pl_w:.1f} PS:{ps_w:.1f}"

            table.add_row(
                t, _fmt_money(price), _fmt_money(fv), mos_str, strat, weights_str
            )
        console.print(table)

    if undervalued_rows:
        _render(
            f"Undervalued (MoS ≥ {int(min_mos*100)}%) — Top {min(limit, len(undervalued_rows))}",
            undervalued_rows,
            limit,
        )
    else:
        console.print("[yellow]No tickers meet the undervaluation threshold.[/yellow] Showing top by MoS.")
        _render("Top by MoS", rows, limit)

    # NEW: export JSON snapshot
    _export_json(ctx, rows)
    return ctx

