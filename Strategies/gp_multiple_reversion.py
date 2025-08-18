# strategies/gp_multiple_reversion.py
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


class GPMultipleReversionStrategy(Strategy):
    """
    EV/GP (Gross Profit) reversion strategy.

    Fair value is computed via a target EV/GP multiple:
        enterprise_value = target_ev_gp * gross_profit_ttm
        equity_value     = enterprise_value - net_debt
        fair_value       = equity_value / shares_outstanding

    Required inputs in `params`:
      - gross_profit_ttm: float (USD; must be > 0)
      - net_debt: float (USD; can be negative if net cash)
      - shares_outstanding: float (> 0)

    Optional hyperparams in `params` (with defaults):
      - target_ev_gp: float = 12.0
      - min_ev_gp: float    = 6.0
      - max_ev_gp: float    = 20.0
    """

    def get_name(self) -> str:
        return "gp_multiple_reversion"

    def run(self, params: Dict[str, Any]) -> float:
        gp_ttm = _as_float(params, "gross_profit_ttm")
        net_debt = _as_float(params, "net_debt")
        shares_out = _as_float(params, "shares_outstanding")

        if gp_ttm <= 0:
            raise StrategyInputError("gross_profit_ttm must be positive")
        if shares_out <= 0:
            raise StrategyInputError("shares_outstanding must be positive")

        target_ev_gp = float(params.get("target_ev_gp", 12.0))
        min_ev_gp = float(params.get("min_ev_gp", 6.0))
        max_ev_gp = float(params.get("max_ev_gp", 20.0))
        if min_ev_gp <= 0 or max_ev_gp <= 0 or min_ev_gp > max_ev_gp:
            raise StrategyInputError("Invalid EV/GP clamps: ensure 0 < min_ev_gp <= max_ev_gp")

        target_ev_gp = _clamp(target_ev_gp, min_ev_gp, max_ev_gp)

        enterprise_value = target_ev_gp * gp_ttm
        equity_value = enterprise_value - net_debt
        fair_value = equity_value / shares_out
        return float(fair_value)
