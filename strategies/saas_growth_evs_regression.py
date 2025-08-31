# strategies/saas_growth_evs_regression.py
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


class SAASGrowthEVSRegressionStrategy(Strategy):
    """
    SaaS Growth EV/S Regression (opportunistic, guardrailed)

    Idea:
      - Estimate a fair EV/S multiple from growth & margin signals:
            EV/S_fair = base
                        + beta_g * growth
                        + beta_gm * (gross_margin - gm_ref)
                        + beta_r40 * max(0, growth + gross_margin - 1)
        Then:
            EV_fair = Revenue_TTM * EV/S_fair
            Equity  = EV_fair - NetDebt
            FV_ps   = Equity / Shares

    Required metrics:
      - revenue_ttm
      - shares_outstanding
      - net_debt
      - gross_profit_ttm
      - rev_ttm_yoy_growth        # decimal (e.g., 0.30 for +30%)

    Optional:
      - eps_cagr_5y               # fallback for growth if rev_ttm_yoy_growth missing

    Hyperparameters (sane defaults; clamp hard):
      - sg_base_multiple   (default 3.0)                    [0.5..20.0]
      - sg_beta_growth     (default 8.0)   # per 1.0 growth [0.0..20.0]
      - sg_beta_gm         (default 3.0)   # per GM delta   [0.0..10.0]
      - sg_gm_ref          (default 0.70)                  [0.30..0.90]
      - sg_beta_rule40     (default 2.0)                   [0.0..10.0]
      - sg_min_multiple    (default 0.5)
      - sg_max_multiple    (default 25.0)

    Notes:
      - growth should be decimal (0.25 = 25%).
      - gross_margin = GP/Revenue; if rev <= 0, raises.
      - Heavily guardrailed; coefficients are overrides in strategy registry.
    """

    def __init__(self) -> None:
        self._name = "saas_growth_evs_regression"

    def get_name(self) -> str:
        return self._name

    def run(self, params: Dict[str, Any]) -> float:
        rev = _f(params.get("revenue_ttm"))
        sh  = _f(params.get("shares_outstanding"))
        nd  = _f(params.get("net_debt"))
        gp  = _f(params.get("gross_profit_ttm"))
        gr  = _f(params.get("rev_ttm_yoy_growth"))  # preferred
        if gr is None:
            gr = _f(params.get("eps_cagr_5y"))      # fallback proxy

        if rev is None or rev <= 0:
            raise StrategyInputError(f"{self._name}: revenue_ttm must be > 0")
        if sh is None or sh <= 0:
            raise StrategyInputError(f"{self._name}: shares_outstanding must be > 0")
        if nd is None:
            nd = 0.0
        if gp is None or gp < 0:
            raise StrategyInputError(f"{self._name}: gross_profit_ttm missing")
        if gr is None:
            raise StrategyInputError(f"{self._name}: growth metric missing (rev_ttm_yoy_growth or eps_cagr_5y)")

        gm = gp / rev  # gross margin (0..1+)
        gm = max(0.0, min(1.0, gm))

        base = _f(params.get("sg_base_multiple", 3.0)) or 3.0
        base = max(0.5, min(20.0, base))

        beta_g = _f(params.get("sg_beta_growth", 8.0)) or 8.0
        beta_g = max(0.0, min(20.0, beta_g))

        beta_gm = _f(params.get("sg_beta_gm", 3.0)) or 3.0
        beta_gm = max(0.0, min(10.0, beta_gm))

        gm_ref = _f(params.get("sg_gm_ref", 0.70)) or 0.70
        gm_ref = max(0.30, min(0.90, gm_ref))

        beta_r40 = _f(params.get("sg_beta_rule40", 2.0)) or 2.0
        beta_r40 = max(0.0, min(10.0, beta_r40))

        mult_min = _f(params.get("sg_min_multiple", 0.5)) or 0.5
        mult_max = _f(params.get("sg_max_multiple", 25.0)) or 25.0
        if mult_min >= mult_max:
            mult_min, mult_max = 0.5, 25.0

        # Rule of 40 term uses growth + margin over 100% threshold
        r40_excess = max(0.0, gr + gm - 1.0)

        evs = base + beta_g * gr + beta_gm * (gm - gm_ref) + beta_r40 * r40_excess
        evs = max(mult_min, min(mult_max, evs))

        ev_fair = float(rev) * float(evs)
        equity = ev_fair - float(nd)
        fv_ps = equity / float(sh)

        if not (fv_ps == fv_ps):  # NaN guard
            raise StrategyInputError(f"{self._name}: computation failed")

        return float(fv_ps)
