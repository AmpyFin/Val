from .base import BaseStrategy
from statistics import median
from typing import Optional, List

class PSalesReversion(BaseStrategy):
    name = "psales_rev"

    def compute(self, ticker: str, data: dict) -> Optional[float]:
        sps = data.get("sales_per_share")
        ps_hist: List[float] = data.get("ps_history") or []
        if sps is None or sps <= 0:
            return None
        if ps_hist:
            ps_fair = median([float(x) for x in ps_hist if x is not None])
        else:
            # fallback (if we had sector medians, we would use them here)
            return None
        fv = ps_fair * float(sps)
        return round(fv, 2)
