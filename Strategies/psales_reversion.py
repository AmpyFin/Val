# strategies/psales_reversion.py
from __future__ import annotations

from typing import Any, Dict

from strategies.strategy import Strategy, StrategyInputError


def _as_float(d: Dict[str, Any], key: str) -> float:
    if key not in d:
        raise StrategyInputError(f"Missing required input: '{key}'")
    try:
        return float(d[key])
    except Exception as exc:
        raise StrategyInputError(f"Input '{key}' must be numeric") from exc


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


class PSalesReversionStrategy(Strategy):
    """
    Price-to-Sales reversion strategy.

    Fair value is computed by reverting to a target P/S multiple:
        sales_per_share = revenue_ttm / shares_outstanding
        fair_value      = sales_per_share * target_ps

    Required inputs in `params`:
      - revenue_ttm: float (USD, should be > 0)
      - shares_outstanding: float (must be > 0)

    Optional hyperparams in `params` (with defaults):
      - target_ps: float = 3.0         # baseline reversion multiple
      - min_ps_fair: float = 0.3       # clamp lower bound for target_ps
      - max_ps_fair: float = 8.0       # clamp upper bound for target_ps
    """

    def get_name(self) -> str:
        return "psales_reversion"

    def run(self, params: Dict[str, Any]) -> float:
        revenue_ttm = _as_float(params, "revenue_ttm")
        shares_out = _as_float(params, "shares_outstanding")

        if shares_out <= 0:
            raise StrategyInputError("shares_outstanding must be positive")
        if revenue_ttm <= 0:
            raise StrategyInputError("revenue_ttm must be positive")

        target_ps = float(params.get("target_ps", 3.0))
        min_ps_fair = float(params.get("min_ps_fair", 0.3))
        max_ps_fair = float(params.get("max_ps_fair", 8.0))
        if min_ps_fair <= 0 or max_ps_fair <= 0 or min_ps_fair > max_ps_fair:
            raise StrategyInputError("Invalid P/S clamps: ensure 0 < min_ps_fair <= max_ps_fair")

        target_ps = _clamp(target_ps, min_ps_fair, max_ps_fair)

        sales_per_share = revenue_ttm / shares_out
        fair_value = sales_per_share * target_ps
        return float(fair_value)
