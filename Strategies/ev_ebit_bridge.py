# strategies/ev_ebit_bridge.py
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


class EVEBITBridgeStrategy(Strategy):
    """
    EV/EBIT bridge valuation.

    Fair value is computed via a target EV/EBIT multiple:
        enterprise_value = target_ev_ebit * ebit_ttm
        equity_value     = enterprise_value - net_debt
        fair_value       = equity_value / shares_outstanding

    Required inputs in `params`:
      - ebit_ttm: float (USD, must be > 0 for meaningful multiple)
      - net_debt: float (USD; can be negative if net cash)
      - shares_outstanding: float (must be > 0)

    Optional hyperparams in `params` (with defaults):
      - target_ev_ebit: float = 12.0     # baseline reversion multiple
      - min_ev_ebit: float    = 6.0
      - max_ev_ebit: float    = 20.0
    """

    def get_name(self) -> str:
        return "ev_ebit_bridge"

    def run(self, params: Dict[str, Any]) -> float:
        ebit_ttm = _as_float(params, "ebit_ttm")
        net_debt = _as_float(params, "net_debt")
        shares_out = _as_float(params, "shares_outstanding")

        if shares_out <= 0:
            raise StrategyInputError("shares_outstanding must be positive")
        if ebit_ttm <= 0:
            # Negative/zero EBIT makes an EV/EBIT-based fair value meaningless.
            raise StrategyInputError("ebit_ttm must be positive for EV/EBIT strategy")

        target_ev_ebit = float(params.get("target_ev_ebit", 12.0))
        min_ev_ebit = float(params.get("min_ev_ebit", 6.0))
        max_ev_ebit = float(params.get("max_ev_ebit", 20.0))
        if min_ev_ebit <= 0 or max_ev_ebit <= 0 or min_ev_ebit > max_ev_ebit:
            raise StrategyInputError("Invalid EV/EBIT clamps: ensure 0 < min_ev_ebit <= max_ev_ebit")

        target_ev_ebit = _clamp(target_ev_ebit, min_ev_ebit, max_ev_ebit)

        enterprise_value = target_ev_ebit * ebit_ttm
        equity_value = enterprise_value - net_debt  # if net_debt < 0, adds cash to equity_value
        fair_value = equity_value / shares_out
        return float(fair_value)
