# strategies/peter_lynch.py
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


class PeterLynchStrategy(Strategy):
    """
    Peter Lynch valuation:
      - Fair P/E ≈ growth% (capped)
      - fair_value = EPS_TTM * growth_pe

    Required inputs in `params`:
      - eps_ttm: float (must be > 0)
      - eps_cagr_5y: float as DECIMAL (e.g., 0.15 for 15%)

    Optional hyperparams in `params` (with defaults):
      - min_growth_pe: float = 5.0
      - max_growth_pe: float = 35.0
      - negative_growth_pe: float = 5.0   # used if eps_cagr_5y <= 0
    """

    def get_name(self) -> str:
        return "peter_lynch"

    def run(self, params: Dict[str, Any]) -> float:
        eps_ttm = _as_float(params, "eps_ttm")
        eps_cagr_5y = _as_float(params, "eps_cagr_5y")

        if eps_ttm <= 0:
            # A negative or zero EPS makes a Lynch fair value meaningless.
            raise StrategyInputError("eps_ttm must be positive for Peter Lynch strategy")

        min_growth_pe = float(params.get("min_growth_pe", 5.0))
        max_growth_pe = float(params.get("max_growth_pe", 35.0))
        negative_growth_pe = float(params.get("negative_growth_pe", 5.0))

        if eps_cagr_5y <= 0:
            growth_pe = negative_growth_pe
        else:
            growth_pct = eps_cagr_5y * 100.0  # convert decimal -> percent
            growth_pe = _clamp(growth_pct, min_growth_pe, max_growth_pe)

        fair_value = eps_ttm * growth_pe
        return float(fair_value)
