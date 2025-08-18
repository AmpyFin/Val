# strategies/epv_ebit.py
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


class EPVEBITStrategy(Strategy):
    """
    Earnings Power Value (EPV) using EBIT (no-growth perpetuity).

    Idea (Bruce Greenwald): value the business on its sustainable, after-tax,
    *normalized* operating earnings capitalized at a required return.

      EV = (EBIT * (1 - tax_rate) * adj_factor) / cost_of_capital
      Equity = EV - NetDebt
      FV/share = Equity / SharesOutstanding

    Where:
      - tax_rate: effective tax rate (default 21%)
      - cost_of_capital: required return / WACC proxy (default 10%)
      - adj_factor: optional haircut to reflect maintenance capex & cyclicality
                    (default 1.0; e.g., 0.9 = 10% haircut)

    Required metrics (canonical keys):
      - ebit_ttm
      - net_debt
      - shares_outstanding

    Tunable hyperparameters:
      - epv_tax_rate           (default 0.21, clamp 0..0.5)
      - epv_cost_of_capital   (default 0.10, clamp 0.05..0.20)
      - epv_adjustment_factor (default 1.0, clamp 0.7..1.1)

    Returns float fair value per share (USD).
    """

    def __init__(self) -> None:
        self._name = "epv_ebit"

    def get_name(self) -> str:
        return self._name

    def run(self, params: Dict[str, Any]) -> float:
        ebit = _to_float(params.get("ebit_ttm"))
        net_debt = _to_float(params.get("net_debt", 0.0))
        sh = _to_float(params.get("shares_outstanding"))

        if ebit is None:
            raise StrategyInputError(f"{self._name}: missing ebit_ttm")
        if sh is None or sh <= 0:
            raise StrategyInputError(f"{self._name}: missing/invalid shares_outstanding")
        if net_debt is None:
            net_debt = 0.0

        tax = _to_float(params.get("epv_tax_rate", 0.21))
        if tax is None:
            tax = 0.21
        tax = max(0.0, min(0.5, tax))

        k = _to_float(params.get("epv_cost_of_capital", 0.10))
        if k is None:
            k = 0.10
        k = max(0.05, min(0.20, k))

        adj = _to_float(params.get("epv_adjustment_factor", 1.0))
        if adj is None:
            adj = 1.0
        adj = max(0.7, min(1.1, adj))

        # After-tax sustainable operating earnings
        ebit_after_tax = float(ebit) * (1.0 - tax) * adj

        if k <= 0:
            raise StrategyInputError(f"{self._name}: cost_of_capital must be > 0")

        ev = ebit_after_tax / k
        equity = ev - float(net_debt)
        fv_per_share = equity / float(sh)
        return float(fv_per_share)
