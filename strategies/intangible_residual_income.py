# strategies/intangible_residual_income.py
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


class IntangibleResidualIncomeStrategy(Strategy):
    """
    Intangible-Adjusted Residual Income (IARI)

    Goal
    ----
    For tech/growth firms, capitalize R&D (and a % of SG&A as brand-building),
    adjust EPS and BVPS accordingly, then apply a finite-horizon + terminal
    Residual Income model. This balances "today" (current book/earnings) with
    "potential" (growth driven by intangibles).

    Adjustments (steady-state approximation)
    ---------------------------------------
      R&D asset per share      = (rd_ttm * rd_life_years) / shares
      Brand asset per share    = (sga_ttm * brand_pct * brand_life_years) / shares

      Adjusted BVPS            = BVPS + R&D_asset_ps + Brand_asset_ps

      Adjusted EPS             = EPS + R&D_addback_ps + Brand_addback_ps
        where:
          R&D_addback_ps       = (rd_ttm / shares) * (1 - 1/rd_life_years)
          Brand_addback_ps     = (sga_ttm * brand_pct / shares) * (1 - 1/brand_life_years)

      Notes: In strict steady-state, addback ≈ amortization and net effect is modest.
             When R&D/brand spend is ramping, this lifts adjusted earnings slightly.

    Residual Income Valuation
    -------------------------
      RI_t     = (Adj_EPS_t - r * Adj_BVPS_{t-1})
      Adj_BVPS_t evolves with retained earnings (payout inferred from dividend_ttm/EPS, floored).

      Price    = Adj_BVPS_0
                 + Σ_{t=1..N} RI_t / (1+r)^t
                 + [ RI_{N+1} / (r - g_T) ] / (1+r)^N    (terminal via continuing RI)

    Required metrics
    ----------------
      - eps_ttm
      - book_value_per_share
      - shares_outstanding
      - rd_ttm                  (R&D last 12m total)
      - sga_ttm                 (SG&A last 12m total; we use a % as brand-building)

    Optional
    --------
      - dividend_ttm            (for payout inference)

    Hyperparameters (conservative defaults; clamp sensibly)
    -------------------------------------------------------
      - iri_discount_rate   (r)              default 0.10  [0.06..0.18]
      - iri_horizon_years   (N)              default 8     [3..15]
      - iri_terminal_growth (g_T)            default 0.02  [-0.01..0.03], must be < r
      - iri_eps_growth      (g_eps)          optional → fallback eps_cagr_5y or 0.10  [0..0.25]
      - iri_div_payout_floor               default 0.10    [0.0..0.6]
      - rd_life_years                       default 5      [2..8]
      - brand_pct_of_sga                    default 0.30   [0.0..0.7]
      - brand_life_years                    default 5      [2..10]

    Returns: fair value per share (float)
    """

    def __init__(self) -> None:
        self._name = "intangible_residual_income"

    def get_name(self) -> str:
        return self._name

    def run(self, params: Dict[str, Any]) -> float:
        eps = _f(params.get("eps_ttm"))
        bvps = _f(params.get("book_value_per_share"))
        shares = _f(params.get("shares_outstanding"))
        rd_ttm = _f(params.get("rd_ttm"))
        sga_ttm = _f(params.get("sga_ttm"))
        div = _f(params.get("dividend_ttm"))
        eps_cagr_5y = _f(params.get("eps_cagr_5y"))

        if shares is None or shares <= 0:
            raise StrategyInputError(f"{self._name}: shares_outstanding must be > 0")
        if eps is None or eps <= 0:
            raise StrategyInputError(f"{self._name}: eps_ttm must be > 0")
        if bvps is None or bvps <= 0:
            raise StrategyInputError(f"{self._name}: book_value_per_share must be > 0")
        # Allow missing R&D/SG&A data with fallback to zero (strategy becomes regular RI)
        if rd_ttm is None or rd_ttm < 0:
            rd_ttm = 0.0
        if sga_ttm is None or sga_ttm < 0:
            sga_ttm = 0.0
            
        # If both R&D and SG&A are zero, warn but continue (becomes regular residual income)
        if rd_ttm == 0.0 and sga_ttm == 0.0:
            # Still can run as regular residual income model without intangible adjustments
            pass

        # Hyperparameters
        r = _f(params.get("iri_discount_rate", 0.10)) or 0.10
        r = max(0.06, min(0.18, r))

        N = int(params.get("iri_horizon_years", 8) or 8)
        N = max(3, min(15, N))

        gT = _f(params.get("iri_terminal_growth", 0.02)) or 0.02
        gT = max(-0.01, min(0.03, gT))
        if r <= gT:
            raise StrategyInputError(f"{self._name}: discount_rate must exceed terminal growth (r={r:.3f}, gT={gT:.3f})")

        g_eps = _f(params.get("iri_eps_growth"))
        if g_eps is None:
            g_eps = eps_cagr_5y if eps_cagr_5y is not None else 0.10
        g_eps = max(0.00, min(0.25, g_eps))

        payout_floor = _f(params.get("iri_div_payout_floor", 0.10)) or 0.10
        payout_floor = max(0.0, min(0.6, payout_floor))

        rd_life = int(params.get("rd_life_years", 5) or 5)
        rd_life = max(2, min(8, rd_life))

        brand_pct = _f(params.get("brand_pct_of_sga", 0.30)) or 0.30
        brand_pct = max(0.0, min(0.7, brand_pct))

        brand_life = int(params.get("brand_life_years", 5) or 5)
        brand_life = max(2, min(10, brand_life))

        # Capitalized intangibles per share (steady-state approximation)
        rd_asset_ps = (rd_ttm * rd_life) / shares if rd_ttm is not None else 0.0
        brand_asset_ps = (sga_ttm * brand_pct * brand_life) / shares if sga_ttm is not None else 0.0

        adj_bvps = float(bvps) + rd_asset_ps + brand_asset_ps

        # Addbacks to EPS per share (add expense, subtract amortization -> (1 - 1/L) * spend_ps)
        rd_addback_ps = (rd_ttm / shares) * (1.0 - 1.0 / rd_life) if rd_ttm is not None and rd_life > 0 else 0.0
        brand_addback_ps = (sga_ttm * brand_pct / shares) * (1.0 - 1.0 / brand_life) if sga_ttm is not None and brand_life > 0 else 0.0
        adj_eps0 = float(eps) + rd_addback_ps + brand_addback_ps

        # Infer payout ratio from dividend; otherwise floor
        if div is not None and div >= 0 and eps > 0:
            payout = max(payout_floor, min(1.0, float(div) / float(eps)))
        else:
            payout = payout_floor
        retention = 1.0 - payout

        # Residual Income path
        pv = 0.0
        bv = adj_bvps
        eps_t = adj_eps0
        for t in range(1, N + 1):
            # grow EPS with g_eps
            if t > 1:
                eps_t = eps_t * (1.0 + g_eps)
            # RI_t based on beginning BV
            ri_t = eps_t - r * bv
            pv += ri_t / ((1.0 + r) ** t)
            # update BV with retained earnings
            bv = bv + eps_t * retention

        # Terminal continuing RI (year N+1)
        eps_N1 = eps_t * (1.0 + gT)
        ri_N1 = eps_N1 - r * bv
        tv = ri_N1 / (r - gT)
        pv += tv / ((1.0 + r) ** N)

        price = adj_bvps + pv

        if not (price == price):
            raise StrategyInputError(f"{self._name}: computation failed")

        return float(price)
