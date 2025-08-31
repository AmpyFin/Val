# strategies/dcf_fcff_three_stage.py
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


class DCF_FCFF_ThreeStage(Strategy):
    """
    Three-Stage FCFF DCF (Damodaran-style, enterprise first, then to equity per share).

    Forecasts:
      - Stage 1 (N1 years): revenue grows at gS; EBIT margin = current or fades toward target.
      - Stage 2 (N2 years): growth linearly fades from gS to gT; margin continues toward target.
      - Terminal: stable growth gT; FCFF_T+1 / (WACC - gT).

    FCFF construction each year t:
      Revenue_t  = Revenue_{t-1} * (1 + g_t)
      EBIT_t     = Revenue_t * Margin_t
      NOPAT_t    = EBIT_t * (1 - tax_rate)
      Reinvest_t = bounded reinvestment based on ΔRevenue_t / sales_to_capital
      FCFF_t     = NOPAT_t - Reinvest_t

    Enterprise Value:
      EV = Σ FCFF_t / (1+WACC)^t + TV / (1+WACC)^(N1+N2),
      where TV = FCFF_T+1 / (WACC - gT)

    Equity fair value per share:
      Equity = (EV - net_debt) / shares_outstanding

    Required metrics (canonical keys):
      - revenue_ttm
      - ebit_ttm (must be positive)
      - shares_outstanding
      - net_debt

    Helpful optional metric:
      - eps_cagr_5y (proxy for near-term growth gS if not provided)

    Tunable hyperparameters (sane defaults; override in strategy registry if desired):
      - dcf_wacc                (default 0.10, clamp 0.06..0.18)
      - dcf_tax_rate            (default 0.21, clamp 0.00..0.35)
      - dcf_sales_to_capital    (default 3.0, clamp 0.5..10.0)   # $ sales per $ capital
      - dcf_stage1_years (N1)   (default 5, clamp 1..7)
      - dcf_stage2_years (N2)   (default 5, clamp 1..10)
      - dcf_g_short (gS)        (optional; else uses eps_cagr_5y or 0.08), clamp 0.00..0.25
      - dcf_g_terminal (gT)     (default 0.025, clamp -0.01..0.03; must be < WACC)
      - dcf_target_ebit_margin  (optional; if None, hold current; else linearly fade to this by terminal, bounded 1-40%)
      - dcf_allow_negative_reinvestment (default True; allows controlled divestment to boost FCFF)

    Validation and safeguards:
      - EBIT must be positive (no loss-making companies)
      - EBIT margin must be reasonable (-50% to 100%)
      - Reinvestment capped at 80% of NOPAT to prevent extreme values
      - Terminal FCFF must be positive
      - Enterprise value must be positive
      - Equity value must be positive (accounts for high net debt scenarios)

    Notes:
      - Requires consistent currency/share class across inputs (normalize in fetch stage if ADR/local mix).
      - Designed for profitable companies with reasonable operating metrics.
      - Raises StrategyInputError for companies with negative EBIT or extreme debt levels.
    """

    def __init__(self) -> None:
        self._name = "dcf_fcff_three_stage"

    def get_name(self) -> str:
        return self._name

    def run(self, params: Dict[str, Any]) -> float:
        rev0 = _f(params.get("revenue_ttm"))
        ebit0 = _f(params.get("ebit_ttm"))
        shares = _f(params.get("shares_outstanding"))
        net_debt = _f(params.get("net_debt"))

        if rev0 is None or rev0 <= 0:
            raise StrategyInputError(f"{self._name}: revenue_ttm must be > 0")
        if ebit0 is None:
            raise StrategyInputError(f"{self._name}: ebit_ttm missing")
        if shares is None or shares <= 0:
            raise StrategyInputError(f"{self._name}: shares_outstanding must be > 0")
        if net_debt is None:
            net_debt = 0.0

        # Additional validation for negative EBIT
        margin0 = ebit0 / rev0 if rev0 != 0 else 0.0
        if ebit0 <= 0:
            raise StrategyInputError(f"{self._name}: EBIT must be positive for DCF (EBIT={ebit0:.0f}, margin={margin0:.1%})")
        
        # Validate reasonable margin bounds
        if margin0 < -0.5 or margin0 > 1.0:
            raise StrategyInputError(f"{self._name}: EBIT margin out of reasonable bounds (margin={margin0:.1%})")

        # Defaults & clamps
        WACC = _f(params.get("dcf_wacc", 0.10)) or 0.10
        WACC = max(0.06, min(0.18, WACC))

        tax = _f(params.get("dcf_tax_rate", 0.21)) or 0.21
        tax = max(0.00, min(0.35, tax))

        S2C = _f(params.get("dcf_sales_to_capital", 2.5)) or 2.5
        S2C = max(0.5, min(10.0, S2C))

        N1 = int(params.get("dcf_stage1_years", 5) or 5)
        N1 = max(1, min(7, N1))

        N2 = int(params.get("dcf_stage2_years", 5) or 5)
        N2 = max(1, min(10, N2))

        gS = _f(params.get("dcf_g_short"))
        if gS is None:
            gS = _f(params.get("eps_cagr_5y"))
        if gS is None:
            gS = 0.08  # More conservative default (was 0.10)
        gS = max(0.00, min(0.25, gS))

        gT = _f(params.get("dcf_g_terminal", 0.02)) or 0.02
        gT = max(-0.01, min(0.03, gT))

        allow_neg_reinv = bool(params.get("dcf_allow_negative_reinvestment", False))

        if WACC <= gT:
            raise StrategyInputError(f"{self._name}: WACC must exceed terminal growth (WACC={WACC:.3f}, gT={gT:.3f})")

        # Current and (optional) target EBIT margin
        # margin0 already calculated above for validation
        target_margin = _f(params.get("dcf_target_ebit_margin"))
        if target_margin is None:
            target_margin = margin0  # hold flat if no target provided
        
        # Bound target margin to reasonable range
        target_margin = max(0.01, min(0.40, target_margin))

        # Build growth & margin paths over N = N1 + N2 years
        N = N1 + N2
        revenues = []
        margins = []
        rev = rev0
        for t in range(1, N + 1):
            # growth path: Stage 1 constant gS, Stage 2 linearly fades to gT
            if t <= N1:
                g_t = gS
            else:
                # linear fade from gS -> gT over N2 steps
                frac = (t - N1) / float(N2)
                g_t = gS + (gT - gS) * max(0.0, min(1.0, frac))

            rev_next = rev * (1.0 + g_t)
            revenues.append(rev_next)
            rev = rev_next

            # margin path: linear fade from margin0 -> target_margin over entire horizon
            m_t = margin0 + (target_margin - margin0) * (t / float(N))
            margins.append(m_t)

        # Year-by-year FCFF
        fcffs = []
        prev_rev = rev0
        for t in range(N):
            rev_t = revenues[t]
            m_t = margins[t]

            ebit_t = rev_t * m_t
            nopat_t = ebit_t * (1.0 - tax)

            delta_rev = rev_t - prev_rev
            reinvest_t = delta_rev / S2C
            
            # Improved reinvestment logic: cap reinvestment relative to NOPAT to prevent extreme values
            max_reinvest = max(0.0, nopat_t * 0.8)  # Cap at 80% of NOPAT
            min_reinvest = min(0.0, nopat_t * -0.5)  # Allow some divestment but not extreme
            
            if not allow_neg_reinv:
                reinvest_t = max(0.0, min(reinvest_t, max_reinvest))
            else:
                reinvest_t = max(min_reinvest, min(reinvest_t, max_reinvest))

            fcff_t = nopat_t - reinvest_t
            fcffs.append(fcff_t)
            prev_rev = rev_t

        # Discount FCFFs
        ev_pv = 0.0
        for t, fcff in enumerate(fcffs, start=1):
            ev_pv += fcff / ((1.0 + WACC) ** t)

        # Terminal year inputs (year N)
        rev_N = revenues[-1]
        m_N = margins[-1]
        ebit_N1 = (rev_N * (1.0 + gT)) * m_N
        nopat_N1 = ebit_N1 * (1.0 - tax)
        reinvest_N1 = (rev_N * gT) / S2C
        
        # Apply same reinvestment caps for terminal value
        max_reinvest_N1 = max(0.0, nopat_N1 * 0.8)
        min_reinvest_N1 = min(0.0, nopat_N1 * -0.5)
        
        if not allow_neg_reinv:
            reinvest_N1 = max(0.0, min(reinvest_N1, max_reinvest_N1))
        else:
            reinvest_N1 = max(min_reinvest_N1, min(reinvest_N1, max_reinvest_N1))
            
        fcff_N1 = nopat_N1 - reinvest_N1

        # Validate terminal FCFF is reasonable
        if fcff_N1 <= 0:
            raise StrategyInputError(f"{self._name}: terminal FCFF must be positive (FCFF_N+1={fcff_N1:.0f})")

        TV = fcff_N1 / (WACC - gT)
        pv_TV = TV / ((1.0 + WACC) ** N)

        EV = ev_pv + pv_TV
        
        # Additional validation for extreme results
        if EV <= 0:
            raise StrategyInputError(f"{self._name}: enterprise value must be positive (EV={EV:.0f})")

        equity_value = EV - float(net_debt)
        
        # Check if high net debt creates negative equity value
        if equity_value <= 0:
            raise StrategyInputError(f"{self._name}: equity value negative due to high net debt (EV={EV:.0f}, net_debt={net_debt:.0f})")
            
        fv_per_share = equity_value / float(shares)

        if not (fv_per_share == fv_per_share):  # NaN
            raise StrategyInputError(f"{self._name}: computation failed")

        return float(fv_per_share)
