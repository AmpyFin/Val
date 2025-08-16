from .base import BaseAdapter
from typing import Dict, Any, Optional
import random
import math
import logging

SECTORS = ["Technology", "Healthcare", "Financials", "Industrials", "Consumer", "Energy"]

class MockLocalAdapter(BaseAdapter):
    name = "mock_local"
    fields_provided = [
        "price",
        "eps_ttm",
        "sales_per_share",
        "ps_history",       # list[float]
        "growth_pct",       # % growth used by Peter Lynch
        "sector",
        "shares_outstanding",
        "net_income_ttm",
        "revenue_ttm"
    ]

    def __init__(self, config: Any, logger: Optional[logging.Logger] = None):
        super().__init__(config, logger)

    def fetch_one(self, ticker: str) -> Dict[str, Any]:
        # Deterministic pseudo-randoms per ticker
        seed = abs(hash(ticker)) & 0xFFFFFFFF
        rng = random.Random(seed)

        price = round(rng.uniform(5, 500), 2)
        eps = round(rng.uniform(-2.0, 12.0), 2)       # allow negative EPS
        sps = round(rng.uniform(1.0, 200.0), 2)       # sales per share
        ps_history = [round(rng.uniform(1.0, 15.0), 2) for _ in range(12)]  # ~3y monthly points
        growth_pct = round(rng.uniform(0.0, 40.0), 2) # %-growth proxy for fair PE
        sector = rng.choice(SECTORS)
        shares_out = int(rng.uniform(10_000_000, 5_000_000_000))

        # Calculate net income and revenue from EPS and sales per share
        net_income_ttm = eps * shares_out if eps is not None else None
        revenue_ttm = sps * shares_out if sps is not None else None
        
        return {
            "price": price,
            "eps_ttm": eps,
            "sales_per_share": sps,
            "ps_history": ps_history,
            "growth_pct": growth_pct,
            "sector": sector,
            "shares_outstanding": shares_out,
            "net_income_ttm": net_income_ttm,
            "revenue_ttm": revenue_ttm
        }
