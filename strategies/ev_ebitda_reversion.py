# strategies/ev_ebitda_reversion.py
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


class EVEbitdaReversionStrategy(Strategy):
    """
    EV/EBITDA Multiple Reversion — classic market-comparable valuation.

    Fair Enterprise Value:
        EV_fair = EBITDA_TTM * target_EV_EBITDA_multiple

    Equity fair value per share:
        Equity = (EV_fair - net_debt) / shares_outstanding

    Required/optional inputs (canonical keys):
      - ebitda_ttm               (preferred)
      - OR: ebit_ttm + da_ttm    (fallback if ebitda_ttm is missing)
      - net_debt                 (debt - cash; negative means net cash)
      - shares_outstanding

    Tunable hyperparameters:
      - ev_ebitda_target_multiple   (default 10.0, clamp 3..25)
      - ev_ebitda_da_pct_of_revenue (optional fallback, default None; if both ebitda_ttm and da_ttm
                                     are missing but revenue_ttm is present, estimate D&A = pct * revenue)
        * Only used as a last resort; if still insufficient data, the strategy raises.

    Notes:
      - Ensure currency/share-class consistency (ADR vs ordinary) upstream.
      - If EBITDA <= 0, raises StrategyInputError (not meaningful for this method).
    """

    def __init__(self) -> None:
        self._name = "ev_ebitda_reversion"

    def get_name(self) -> str:
        return self._name

    def run(self, params: Dict[str, Any]) -> float:
        # --- Pull primary inputs
        ebitda = _f(params.get("ebitda_ttm"))
        net_debt = _f(params.get("net_debt"))
        shares = _f(params.get("shares_outstanding"))
        if net_debt is None:
            net_debt = 0.0
        if shares is None or shares <= 0:
            raise StrategyInputError(f"{self._name}: shares_outstanding must be > 0")

        # --- Fallback construction for EBITDA
        if ebitda is None:
            ebit = _f(params.get("ebit_ttm"))
            da = _f(params.get("da_ttm"))
            if ebit is not None and da is not None:
                ebitda = ebit + da
            else:
                # optional last-resort estimate of D&A from revenue
                rev = _f(params.get("revenue_ttm"))
                da_pct = _f(params.get("ev_ebitda_da_pct_of_revenue"))
                if ebit is not None and rev is not None and da_pct is not None:
                    ebitda = ebit + rev * da_pct

        if ebitda is None or ebitda <= 0:
            raise StrategyInputError(f"{self._name}: EBITDA TTM unavailable or non-positive")

        # --- Target multiple
        mult = _f(params.get("ev_ebitda_target_multiple", 10.0)) or 10.0
        mult = max(3.0, min(25.0, mult))

        # --- Fair enterprise value and equity per share
        ev_fair = float(ebitda) * float(mult)
        equity_fair = ev_fair - float(net_debt)
        fv_per_share = equity_fair / float(shares)

        if not (fv_per_share == fv_per_share):  # NaN guard
            raise StrategyInputError(f"{self._name}: computation failed")

        return float(fv_per_share)
