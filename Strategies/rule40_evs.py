# strategies/rule40_evs.py
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


def _map_rule40_to_evs(score: float, evs_low: float, evs_mid: float, evs_high: float) -> float:
    """
    Piecewise mapping from Rule-of-40 score (0-100) to target EV/S multiple.
      - score < 30  -> evs_low
      - 30..50      -> evs_mid
      - > 50        -> evs_high
    """
    if score < 30:
        return evs_low
    if score <= 50:
        return evs_mid
    return evs_high


class Rule40EVSStrategy(Strategy):
    """
    Rule-of-40 EV/S valuation.

    Inputs:
      Required in `params`:
        - revenue_ttm: float (USD; >0)
        - net_debt: float (USD; can be negative if net cash)
        - shares_outstanding: float (>0)
        - rule40_score: float (0..100)  # growth% + operating margin% (approx)

      Optional hyperparams in `params` (with defaults):
        - evs_low: float = 2.0   # target EV/S if score < 30
        - evs_mid: float = 4.0   # target EV/S if 30 <= score <= 50
        - evs_high: float = 6.0  # target EV/S if score > 50
        - min_evs: float = 0.5   # lower clamp for resulting target multiple
        - max_evs: float = 20.0  # upper clamp for resulting target multiple

    Formula:
        target_evs       = map(rule40_score)
        enterprise_value = target_evs * revenue_ttm
        equity_value     = enterprise_value - net_debt
        fair_value       = equity_value / shares_outstanding
    """

    def get_name(self) -> str:
        return "rule40_evs"

    def run(self, params: Dict[str, Any]) -> float:
        revenue_ttm = _as_float(params, "revenue_ttm")
        net_debt = _as_float(params, "net_debt")
        shares_out = _as_float(params, "shares_outstanding")
        rule40_score = _as_float(params, "rule40_score")

        if revenue_ttm <= 0:
            raise StrategyInputError("revenue_ttm must be positive")
        if shares_out <= 0:
            raise StrategyInputError("shares_outstanding must be positive")

        evs_low = float(params.get("evs_low, ", params.get("evs_low", 2.0)))   # tolerate key with trailing comma typo
        evs_mid = float(params.get("evs_mid", 4.0))
        evs_high = float(params.get("evs_high", 6.0))
        min_evs = float(params.get("min_evs", 0.5))
        max_evs = float(params.get("max_evs", 20.0))
        if min_evs <= 0 or max_evs <= 0 or min_evs > max_evs:
            raise StrategyInputError("Invalid EV/S clamps: ensure 0 < min_evs <= max_evs")

        target_evs = _map_rule40_to_evs(rule40_score, evs_low, evs_mid, evs_high)
        target_evs = _clamp(target_evs, min_evs, max_evs)

        enterprise_value = target_evs * revenue_ttm
        equity_value = enterprise_value - net_debt
        fair_value = equity_value / shares_out
        return float(fair_value)
