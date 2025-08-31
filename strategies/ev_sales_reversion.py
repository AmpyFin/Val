# strategies/ev_sales_reversion.py
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


class EVSalesReversionStrategy(Strategy):
    """
    EV/Sales Multiple Reversion (enterprise-based comparable).

    Fair Enterprise Value:
        EV_fair = Revenue_TTM * target_EV_Sales_multiple   [optionally scaled by gross margin]

    Equity fair value per share:
        Equity = (EV_fair - net_debt) / shares_outstanding

    Required metrics (canonical keys):
      - revenue_ttm
      - net_debt                  (debt - cash; negative means net cash)
      - shares_outstanding

    Optional metrics:
      - gross_profit_ttm          (to compute gross margin for an optional GM adjustment)

    Tunable hyperparameters (sane defaults):
      - evs_target_multiple       (default 3.0, clamp 0.5..15.0)
      - evs_gm_adjust_enabled     (default False)  # if True, scale multiple by (GM / evs_ref_gm)
      - evs_ref_gm                (default 0.70)   # reference gross margin for scaling (70%)
      - evs_min_multiple          (default 0.5)    # hard clamp
      - evs_max_multiple          (default 15.0)   # hard clamp

    Notes:
      - Ensure currency/share-class normalization upstream (ADR vs ordinary).
      - If revenue <= 0 or shares <= 0, raises StrategyInputError.
      - If optional GM adjustment is enabled and gross_profit_ttm is missing, falls back to unadjusted multiple.
    """

    def __init__(self) -> None:
        self._name = "ev_sales_reversion"

    def get_name(self) -> str:
        return self._name

    def run(self, params: Dict[str, Any]) -> float:
        rev = _f(params.get("revenue_ttm"))
        net_debt = _f(params.get("net_debt"))
        sh = _f(params.get("shares_outstanding"))

        if rev is None or rev <= 0:
            raise StrategyInputError(f"{self._name}: revenue_ttm must be > 0")
        if sh is None or sh <= 0:
            raise StrategyInputError(f"{self._name}: shares_outstanding must be > 0")
        if net_debt is None:
            net_debt = 0.0

        # Target EV/Sales multiple
        mult = _f(params.get("evs_target_multiple", 3.0)) or 3.0
        mult = max(_f(params.get("evs_min_multiple", 0.5)) or 0.5,
                   min(_f(params.get("evs_max_multiple", 15.0)) or 15.0, mult))

        # Optional gross margin adjustment
        if bool(params.get("evs_gm_adjust_enabled", False)):
            gp = _f(params.get("gross_profit_ttm"))
            if gp is not None and rev > 0:
                gm = max(0.0, min(1.0, gp / rev))
                ref_gm = max(0.10, min(0.95, _f(params.get("evs_ref_gm", 0.70)) or 0.70))
                if ref_gm > 0:
                    mult = mult * (gm / ref_gm)

        ev_fair = float(rev) * float(mult)
        equity = ev_fair - float(net_debt)
        fv_per_share = equity / float(sh)

        if not (fv_per_share == fv_per_share):  # NaN guard
            raise StrategyInputError(f"{self._name}: computation failed")

        return float(fv_per_share)
