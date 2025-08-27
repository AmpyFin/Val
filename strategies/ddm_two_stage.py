# strategies/ddm_two_stage.py
from __future__ import annotations

from typing import Any, Dict, Optional

from strategies.strategy import Strategy, StrategyInputError


def _to_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        f = float(x)
        if f != f:  # NaN
            return None
        return f
    except Exception:
        return None


class DDMTwoStageStrategy(Strategy):
    """
    Two-Stage Dividend Discount Model (per-share).

    Fair value per share:
      FV = sum_{t=1..N} [ D0*(1+g1)^t / (1+r)^t ]  +  [ D_N*(1+gT) / (r - gT) ] / (1+r)^N
        where D_N = D0*(1+g1)^N

    Required metrics (canonical keys):
      - dividend_ttm           (D0; per-share dividends over the last 12 months)
      - eps_cagr_5y            (optional; used if high-growth rate not provided)

    Tunable hyperparameters (defaults conservative):
      - ddm_high_years         (int, default 5, clamp 1..15)
      - ddm_discount_rate      (decimal, default 0.09, clamp 0.05..0.20)
      - ddm_high_growth_rate   (decimal, optional; if None uses eps_cagr_5y; clamp -0.05..0.20)
      - ddm_terminal_growth    (decimal, default 0.02, clamp -0.02..0.05; must be < discount rate)

    Returns:
      float fair value per share (USD). Raises StrategyInputError if inputs invalid.
    """

    def __init__(self) -> None:
        self._name = "ddm_two_stage"

    def get_name(self) -> str:
        return self._name

    def run(self, params: Dict[str, Any]) -> float:
        D0 = _to_float(params.get("dividend_ttm"))
        if D0 is None or D0 <= 0.0:
            raise StrategyInputError(f"{self._name}: missing/invalid dividend_ttm")

        # horizon
        N = int(params.get("ddm_high_years", 5) or 5)
        N = max(1, min(15, N))

        # discount
        r = _to_float(params.get("ddm_discount_rate", 0.09)) or 0.09
        r = max(0.05, min(0.20, r))

        # high-growth rate
        g1 = _to_float(params.get("ddm_high_growth_rate"))
        if g1 is None:
            g1 = _to_float(params.get("eps_cagr_5y"))  # fallback proxy
        if g1 is None:
            g1 = 0.05
        g1 = max(-0.05, min(0.20, g1))

        # terminal growth
        gT = _to_float(params.get("ddm_terminal_growth", 0.02)) or 0.02
        gT = max(-0.02, min(0.05, gT))

        if r <= gT:
            raise StrategyInputError(f"{self._name}: discount_rate must be > terminal_growth")

        # PV of high-growth dividends
        fv = 0.0
        D_t = float(D0)
        for t in range(1, N + 1):
            D_t = D_t * (1.0 + g1)
            fv += D_t / ((1.0 + r) ** t)

        # Terminal (as of year N), then PV
        D_N = D_t
        TV_N = (D_N * (1.0 + gT)) / (r - gT)
        TV_PV = TV_N / ((1.0 + r) ** N)

        return float(fv + TV_PV)
