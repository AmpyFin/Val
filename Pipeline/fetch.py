# Pipeline/fetch.py
from __future__ import annotations
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from Registries.adapters import build_adapters

# Fields we try to populate for each ticker (first non-None wins, in adapter order).
FIELDS = [
    "price",
    "eps_ttm",
    "sales_per_share",
    "ps_history",
    "growth_pct",
    "sector",
    "shares_outstanding",
]

def _merge_derived(tickers: List[str], adapters, raw: Dict[str, Dict[str, Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
    derived: Dict[str, Dict[str, Any]] = {t: {} for t in tickers}
    for t in tickers:
        for f in FIELDS:
            val = None
            for ad in adapters:
                v = raw.get(ad.name, {}).get(t, {}).get(f)
                if v is not None:
                    val = v
                    break
            if val is not None:
                derived[t][f] = val
    return derived

def run(ctx):
    logger = ctx.logger
    adapters = build_adapters(ctx.config.adapters, ctx.config, logger)
    if not adapters:
        raise RuntimeError("No adapters configured. Check config.settings.yaml → adapters.")

    # 1) Fetch concurrently per adapter
    ctx.raw.clear()
    max_workers = min(32, max(4, len(adapters) * 4))
    logger.info(f"[fetch] launching with {len(adapters)} adapter(s), max_workers={max_workers}")

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(ad.fetch_many, ctx.tickers): ad for ad in adapters}
        for fut in as_completed(futures):
            ad = futures[fut]
            try:
                data = fut.result()  # Dict[ticker] -> Dict[field] -> value
                ctx.raw[ad.name] = data or {}
                logger.info(f"[fetch] {ad.name}: fetched {len(ctx.raw[ad.name])} tickers")
            except Exception as e:
                logger.exception(f"[fetch] {ad.name} failed: {e}")
                ctx.raw[ad.name] = {}

    # 2) Merge normalized/derived dataset (first non-None by adapter order)
    ctx.derived = _merge_derived(ctx.tickers, adapters, ctx.raw)
    logger.info(f"[fetch] merged derived fields for {len(ctx.derived)} tickers")
    return ctx
