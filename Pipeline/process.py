# Pipeline/process.py
from __future__ import annotations
from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from Registries.strategies import build_strategies
from .weighting import calculate_strategy_weights, apply_weighted_valuation

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

    # Build per-ticker summary using dynamic weighting
    min_mos = float(ctx.config.thresholds.get("min_mos", 0.20))
    for t in ctx.tickers:
        price = ctx.derived.get(t, {}).get("price")
        ticker_data = ctx.derived.get(t, {})
        
        # Calculate dynamic weights based on company characteristics
        weights = calculate_strategy_weights(ticker_data, ctx.config)
        
        # Collect strategy valuations
        strategy_valuations = {}
        for sname, per_ticker in ctx.results["per_strategy"].items():
            entry = per_ticker.get(t)
            if entry and entry.get("fv") is not None:
                strategy_valuations[sname] = entry["fv"]
        
        # Apply weighted valuation
        weighted_fv = apply_weighted_valuation(strategy_valuations, weights, logger)
        
        # Calculate MoS for weighted fair value
        weighted_mos = _compute_mos(price, weighted_fv)
        
        # Determine which strategy contributed most to the weighted result
        best_strategy = None
        if strategy_valuations:
            if "peter_lynch" in strategy_valuations and "psales_rev" in strategy_valuations:
                # Both strategies available - use the one with higher weight
                pl_weight, ps_weight = weights
                best_strategy = "peter_lynch" if pl_weight > ps_weight else "psales_rev"
            else:
                # Only one strategy available
                best_strategy = list(strategy_valuations.keys())[0]
        
        # Store weights for debugging/transparency
        pl_weight, ps_weight = weights
        
        ctx.results["summary"][t] = {
            "price": price,
            "best_strategy": best_strategy,
            "best_fv": weighted_fv,
            "best_mos": weighted_mos,
            "undervalued": (weighted_mos is not None and weighted_mos >= min_mos),
            "weights": {
                "peter_lynch": round(pl_weight, 3),
                "psales_rev": round(ps_weight, 3)
            }
        }

    logger.info(f"[process] summary completed for {len(ctx.results['summary'])} tickers")
    return ctx
