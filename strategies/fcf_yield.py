# strategies/fcf_yield.py
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


class FCFYieldStrategy(Strategy):
    """
    Free Cash Flow Yield valuation.

    Fair value is the price that implies a target FCF yield:
        fcf_per_share = fcf_ttm / shares_outstanding
        fair_value    = fcf_per_share / target_fcf_yield

    Required inputs in `params`:
      - fcf_ttm: float (USD; must be > 0 for meaningful valuation)
      - shares_outstanding: float (must be > 0)

    Optional hyperparams in `params` (with defaults):
      - target_fcf_yield: float = 0.065   # 6.5% implied yield
      - min_fcf_yield: float   = 0.02     # 2%
      - max_fcf_yield: float   = 0.12     # 12%
    """

    def get_name(self) -> str:
        return "fcf_yield"

    def run(self, params: Dict[str, Any]) -> float:
        fcf_ttm = _as_float(params, "fcf_ttm")
        shares_out = _as_float(params, "shares_outstanding")

        if shares_out <= 0:
            raise StrategyInputError("shares_outstanding must be positive")
        if fcf_ttm <= 0:
            # If FCF is <= 0, a yield-based fair value is not meaningful.
            raise StrategyInputError("fcf_ttm must be positive for FCF Yield strategy")

        target_yield = float(params.get("target_fcf_yield", 0.065))
        min_yield = float(params.get("min_fcf_yield", 0.02))
        max_yield = float(params.get("max_fcf_yield", 0.12))
        if min_yield <= 0 or max_yield <= 0 or min_yield > max_yield:
            raise StrategyInputError("Invalid FCF yield clamps: ensure 0 < min_fcf_yield <= max_fcf_yield")

        target_yield = _clamp(target_yield, min_yield, max_yield)

        fcf_per_share = fcf_ttm / shares_out
        fair_value = fcf_per_share / target_yield
        return float(fair_value)
