# strategies/hmodel_dividend.py
from __future__ import annotations

from typing import Any, Dict, Optional

from strategies.strategy import Strategy, StrategyInputError


def _f(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        v = float(x)
        if v != v:  # NaN
            return None
        return v
    except Exception:
        return None


class HModelDividendStrategy(Strategy):
    """
    H-Model valuation using dividends per share (classic, CFA-curriculum model).

    Formula (price per share):
        P0 = [ D0*(1 + gL) + D0*H*(gS - gL) ] / (r - gL)

    where:
      D0 = current dividend per share (we use dividend_ttm as a proxy)
      r  = cost of equity (discount rate)
      gS = near-term (supernormal) growth rate
      gL = long-run (stable) growth rate   (must be < r)
      H  = N / 2, with N the years over which growth linearly fades from gS to gL

    Required metrics (canonical keys):
      - dividend_ttm

    Helpful optional metric:
      - eps_cagr_5y  (fallback proxy for gS if not provided)

    Tunable hyperparameters:
      - h_discount_rate     (r)   default 0.10, clamp 0.06..0.20
      - h_long_run_growth   (gL)  default 0.02, clamp -0.01..0.04
      - h_short_run_growth  (gS)  optional; if None uses eps_cagr_5y; else 0.10 default
                                   clamp 0.00..0.25
      - h_fade_years        (N)   default 8, clamp 2..20
    """

    def __init__(self) -> None:
        self._name = "hmodel_dividend"

    def get_name(self) -> str:
        return self._name

    def run(self, params: Dict[str, Any]) -> float:
        D0 = _f(params.get("dividend_ttm"))
        if D0 is None or D0 <= 0:
            raise StrategyInputError(f"{self._name}: dividend_ttm must be > 0")

        r = _f(params.get("h_discount_rate", 0.10)) or 0.10
        r = max(0.06, min(0.20, r))

        gL = _f(params.get("h_long_run_growth", 0.02)) or 0.02
        gL = max(-0.01, min(0.04, gL))

        gS = _f(params.get("h_short_run_growth"))
        if gS is None:
            gS = _f(params.get("eps_cagr_5y"))
        if gS is None:
            gS = 0.10
        gS = max(0.00, min(0.25, gS))

        N = int(params.get("h_fade_years", 8) or 8)
        N = max(2, min(20, N))
        H = 0.5 * N

        if r <= gL:
            raise StrategyInputError(f"{self._name}: discount_rate must exceed long-run growth (r={r:.3f}, gL={gL:.3f})")

        # H-Model price
        numerator = D0 * (1.0 + gL) + D0 * H * (gS - gL)
        P0 = numerator / (r - gL)

        if not (P0 == P0):  # NaN guard
            raise StrategyInputError(f"{self._name}: computation failed")

        return float(P0)
