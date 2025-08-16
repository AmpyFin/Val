from .base import BaseStrategy
from typing import Optional

def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))

class PeterLynchSimple(BaseStrategy):
    name = "peter_lynch"

    def compute(self, ticker: str, data: dict) -> Optional[float]:
        eps = data.get("eps_ttm")
        growth_pct = data.get("growth_pct")  # e.g., 20 means ~PE 20
        if eps is None or growth_pct is None:
            return None
        if eps <= 0:
            return None  # not applicable for negative EPS

        max_pe = float(self.config.caps.get("max_growth_pe", 50))
        min_pe = float(self.config.caps.get("min_growth_pe", 5))
        fair_pe = clamp(float(growth_pct), min_pe, max_pe)
        fv = eps * fair_pe
        return round(fv, 2)
