# Pipeline/process.py
from __future__ import annotations
from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from Registries.strategies import build_strategies

def _compute_mos(price: Optional[float], fv: Optional[float]) -> Optional[float]:
    if price is None or fv is None:
        return None
    if fv <= 0:
        return None
    return round(1.0 - float(price) / float(fv), 4)

def run(ctx):
    """
    - Builds strategies from registry
    - Computes fair value per (strategy, ticker) concurrently
    - Fills:
        ctx.valuations[strategy_name][ticker] = fair_value (float|None)
        ctx.results['per_strategy'][strategy_name][ticker] = {'fv': float|None, 'mos': float|None}
        ctx.results['summary'][ticker] = {'price', 'best_strategy', 'best_fv', 'best_mos', 'undervalued'}
    """
    logger = ctx.logger
    strategies = build_strategies(ctx.config.strategies, ctx.config, logger)
    if not strategies:
        raise RuntimeError("No strategies configured. Check config.settings.yaml → strategies.")

    # Ensure dicts exist / reset
    ctx.valuations = {}
    ctx.results.setdefault("per_strategy", {})
    ctx.results.setdefault("summary", {})

    # Threading: per-strategy thread pool over tickers (CPU-light)
    for strat in strategies:
        sname = strat.name
        ctx.valuations[sname] = {}
        ctx.results["per_strategy"].setdefault(sname, {})

        # Choose a sensible worker count
        workers = min(32, max(4, len(ctx.tickers) // 8))
        logger.info(f"[process] {sname}: computing fair values with max_workers={workers}")

        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {
                ex.submit(strat.compute, t, ctx.derived.get(t, {})): t
                for t in ctx.tickers
            }
            for fut in as_completed(futures):
                ticker = futures[fut]
                try:
                    fv = fut.result()
                except Exception as e:
                    logger.exception(f"[process] {sname}: compute failed for {ticker}: {e}")
                    fv = None

                if isinstance(fv, (int, float)):
                    fv = round(float(fv), 2)
                else:
                    fv = None

                ctx.valuations[sname][ticker] = fv

                price = ctx.derived.get(ticker, {}).get("price")
                mos = _compute_mos(price, fv)
                ctx.results["per_strategy"][sname][ticker] = {"fv": fv, "mos": mos}

        logger.info(f"[process] {sname}: done for {len(ctx.valuations[sname])} tickers")

    # Build per-ticker summary (select best by highest MoS)
    min_mos = float(ctx.config.thresholds.get("min_mos", 0.20))
    for t in ctx.tickers:
        price = ctx.derived.get(t, {}).get("price")
        best = {"strategy": None, "fv": None, "mos": None}

        for sname, per_ticker in ctx.results["per_strategy"].items():
            entry = per_ticker.get(t)
            if not entry:
                continue
            mos = entry.get("mos")
            if mos is None:
                continue
            if best["mos"] is None or mos > best["mos"]:
                best = {"strategy": sname, "fv": entry.get("fv"), "mos": mos}

        ctx.results["summary"][t] = {
            "price": price,
            "best_strategy": best["strategy"],
            "best_fv": best["fv"],
            "best_mos": best["mos"],
            "undervalued": (best["mos"] is not None and best["mos"] >= min_mos)
        }

    logger.info(f"[process] summary completed for {len(ctx.results['summary'])} tickers")
    return ctx
