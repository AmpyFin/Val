# strategies/residual_income.py
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


class ResidualIncomeStrategy(Strategy):
    """
    Residual Income (per-share) valuation.

    Core idea:
      Intrinsic Value per share = BVPS_0 + Σ_{t=1..N} [ RI_t / (1+r)^t ] + TV_RI / (1+r)^N
        where residual income per share is:
          RI_t = EPS_t - r * BVPS_{t-1}
        and clean-surplus updates book value per share:
          BVPS_t = BVPS_{t-1} + (EPS_t - DPS_t)
                 = BVPS_{t-1} + EPS_t * (1 - payout_ratio)

      Terminal value uses Gordon on residual income:
          TV_RI = RI_{N+1} / (r - g_T),
          where RI_{N+1} = EPS_{N+1} - r * BVPS_N and EPS_{N+1} grows at g_T.

    Required metrics (canonical keys):
      - eps_ttm                 (EPS per share, trailing 12m)
      - book_value_per_share    (BVPS; equity per share)
      - eps_cagr_5y             (optional; used if explicit growth not provided)

    Tunable hyperparameters (defaults chosen conservatively):
      - ri_years               (int, default 5, clamp 1..10)
      - ri_discount_rate       (decimal, default 0.10, clamp 0.05..0.20)  # r
      - ri_terminal_growth     (decimal, default 0.03, clamp -0.02..0.05) # g_T, must be < r
      - ri_eps_growth_rate     (decimal, optional; if None uses eps_cagr_5y; clamp -0.10..0.25) # g
      - ri_payout_ratio        (decimal 0..1, default 0.30)

    Returns:
      float fair value per share (USD)

    Notes:
      * This is a per-share model—no need to bridge EV/net debt here.
      * If EPS or BVPS is missing/invalid, raises StrategyInputError.
    """

    def __init__(self) -> None:
        self._name = "residual_income"

    def get_name(self) -> str:
        return self._name

    def run(self, params: Dict[str, Any]) -> float:
        # --- Required metrics
        eps0 = _to_float(params.get("eps_ttm"))
        bvps0 = _to_float(params.get("book_value_per_share"))
        if eps0 is None:
            raise StrategyInputError(f"{self._name}: missing eps_ttm")
        if bvps0 is None or bvps0 <= 0:
            raise StrategyInputError(f"{self._name}: missing/invalid book_value_per_share")

        # --- Growth inputs
        g = _to_float(params.get("ri_eps_growth_rate"))
        if g is None:
            g = _to_float(params.get("eps_cagr_5y"))
        if g is None:
            g = 0.06  # conservative fallback if no growth hint
        g = max(-0.10, min(0.25, g))

        # --- Horizon / discount / terminal growth
        years = int(params.get("ri_years", 5) or 5)
        years = max(1, min(10, years))

        r = _to_float(params.get("ri_discount_rate", 0.10)) or 0.10
        r = max(0.05, min(0.20, r))

        gT = _to_float(params.get("ri_terminal_growth", 0.03)) or 0.03
        gT = max(-0.02, min(0.05, gT))

        if r <= gT:
            raise StrategyInputError(f"{self._name}: discount_rate must be > terminal_growth")

        payout = _to_float(params.get("ri_payout_ratio", 0.30))
        if payout is None:
            payout = 0.30
        payout = max(0.0, min(1.0, payout))

        # --- Project EPS/BVPS, accumulate PV of residual income
        pv_ri = 0.0
        eps_t = float(eps0)
        bvps = float(bvps0)

        for t in range(1, years + 1):
            # grow EPS
            eps_t = eps_t * (1.0 + g)
            # residual income this year (using beginning BVPS)
            ri_t = eps_t - r * bvps
            pv_ri += ri_t / ((1.0 + r) ** t)
            # update book per share via clean surplus (retained earnings)
            bvps = bvps + eps_t * (1.0 - payout)

        # Terminal on RI
        eps_N_plus_1 = eps_t * (1.0 + gT)
        ri_N_plus_1 = eps_N_plus_1 - r * bvps
        tv_ri = ri_N_plus_1 / (r - gT)
        tv_pv = tv_ri / ((1.0 + r) ** years)

        intrinsic_per_share = float(bvps0) + pv_ri + tv_pv
        
        # Economic validity: intrinsic value should not be negative
        if intrinsic_per_share <= 0:
            raise StrategyInputError(f"{self._name}: intrinsic value <= 0 from residual income model")
        
        return float(intrinsic_per_share)
