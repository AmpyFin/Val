# strategies/value_driver_roic.py
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


class ValueDriverROICStrategy(Strategy):
    """
    Value-Driver (ROIC) Two-Stage DCF (McKinsey-style)

    Purpose
    -------
    Balance "potential" (growth) with "today" (returns on invested capital).
    Uses the value-driver identity:
        FCFF_t = NOPAT_t * (1 - g_t / ROIC_t)
    with explicit near-term fade of both growth (g) and ROIC toward stable levels.

    Mechanics
    ---------
    Inputs (metrics, canonical keys):
      - revenue_ttm              (total revenue, same currency as others)
      - ebit_ttm                 (trailing EBIT)
      - shares_outstanding
      - net_debt                 (debt - cash; negative means net cash)
      - book_value_per_share     (optional; helps infer invested capital)

    Hyperparameters (defaults; clamp in sensible ranges):
      - vdr_wacc                 (WACC, default 0.10)            [0.06..0.18]
      - vdr_tax_rate             (statutory/effective, 0.21)     [0.00..0.35]
      - vdr_stage_years          (explicit horizon N, default 8) [3..12]
      - vdr_g_start              (near-term growth gS, optional → fall back to eps_cagr_5y or 0.12) [0..0.30]
      - vdr_g_terminal           (stable growth gT, default 0.02) [-0.01..0.03], must be < WACC
      - vdr_roic_start           (current ROIC override; else inferred)
      - vdr_roic_terminal        (stable ROIC, default 0.12)     [0.06..0.25]
      - vdr_ic_override          (invested capital override; else inferred)
      - vdr_eps_cagr_fallback    (if set, used when g_start is None)

    Inference
    ---------
      - NOPAT0 = EBIT_TTM * (1 - tax)
      - Invested Capital (IC0) ≈ Equity_BV + max(0, Net Debt)
            where Equity_BV ≈ book_value_per_share * shares_outstanding
        (If not available or tiny, uses vdr_ic_override or infers from NOPAT0/assumed ROIC)
      - ROIC0 = NOPAT0 / IC0 (if not overridden)
      - Growth path g_t: linear fade from gS → gT over N years
      - ROIC path: linear fade from ROIC0 → ROIC_T over N years
      - Each year t:
            NOPAT_t = NOPAT_{t-1} * (1 + g_t)
            FCFF_t  = NOPAT_t * (1 - g_t / ROIC_t)   # value-driver identity
      - Terminal value (enterprise):
            TV = [ NOPAT_N * (1 + gT) * (1 - gT / ROIC_T) ] / (WACC - gT)

      EV = Σ FCFF_t / (1+WACC)^t + TV / (1+WACC)^N
      Equity = EV - NetDebt
      Fair Value per Share = Equity / shares_outstanding

    Notes
    -----
    - Requires currency/share-class normalization upstream.
    - If inputs produce nonsensical ROIC (e.g., negative IC), we guard & raise StrategyInputError.

    """

    def __init__(self) -> None:
        self._name = "value_driver_roic"

    def get_name(self) -> str:
        return self._name

    def run(self, params: Dict[str, Any]) -> float:
        rev0 = _f(params.get("revenue_ttm"))
        ebit0 = _f(params.get("ebit_ttm"))
        shares = _f(params.get("shares_outstanding"))
        net_debt = _f(params.get("net_debt"))
        bvps = _f(params.get("book_value_per_share"))

        if shares is None or shares <= 0:
            raise StrategyInputError(f"{self._name}: shares_outstanding must be > 0")
        if ebit0 is None:
            raise StrategyInputError(f"{self._name}: ebit_ttm missing")
        if ebit0 <= 0:
            raise StrategyInputError(f"{self._name}: EBIT must be positive for value-driver model (EBIT={ebit0:.0f})")
        if rev0 is None or rev0 <= 0:
            raise StrategyInputError(f"{self._name}: revenue_ttm must be > 0")
        if net_debt is None:
            net_debt = 0.0

        # --- Hyperparameters
        WACC = _f(params.get("vdr_wacc", 0.10)) or 0.10
        WACC = max(0.06, min(0.18, WACC))

        tax = _f(params.get("vdr_tax_rate", 0.21)) or 0.21
        tax = max(0.00, min(0.35, tax))

        N = int(params.get("vdr_stage_years", 8) or 8)
        N = max(3, min(12, N))

        gS = _f(params.get("vdr_g_start"))
        if gS is None:
            gS = _f(params.get("vdr_eps_cagr_fallback")) or _f(params.get("eps_cagr_5y"))
        if gS is None:
            gS = 0.12
        gS = max(0.00, min(0.30, gS))

        gT = _f(params.get("vdr_g_terminal", 0.02)) or 0.02
        gT = max(-0.01, min(0.03, gT))
        if WACC <= gT:
            raise StrategyInputError(f"{self._name}: WACC must exceed terminal growth (WACC={WACC:.3f}, gT={gT:.3f})")

        roic_start = _f(params.get("vdr_roic_start"))
        roic_term = _f(params.get("vdr_roic_terminal", 0.12)) or 0.12
        roic_term = max(0.06, min(0.25, roic_term))

        # --- Derive NOPAT0 and Invested Capital
        nopat0 = float(ebit0) * (1.0 - tax)

        ic_override = _f(params.get("vdr_ic_override"))
        if ic_override is not None and ic_override > 0:
            ic0 = ic_override
        else:
            equity_bv = None
            if bvps is not None and bvps > 0:
                equity_bv = bvps * float(shares)
            # IC ≈ Equity_BV + max(0, NetDebt)
            if equity_bv is not None:
                ic0 = equity_bv + max(0.0, float(net_debt))
            else:
                # Fallback: if ROIC override provided, infer IC0 = NOPAT0 / ROIC
                if roic_start is not None and roic_start > 0:
                    ic0 = max(1.0, nopat0 / roic_start)
                else:
                    # Conservative default: assume 12% ROIC to infer IC
                    ic0 = max(1.0, nopat0 / 0.12)

        if ic0 is None or ic0 <= 0:
            raise StrategyInputError(f"{self._name}: could not infer invested capital (IC0)")

        if roic_start is None or roic_start <= 0:
            roic_start = max(0.02, min(0.60, nopat0 / ic0))

        # --- Build paths over N years
        # Linear fade g: gS -> gT, ROIC: roic_start -> roic_term
        g_path = [gS + (gT - gS) * (t / float(N)) for t in range(1, N + 1)]
        roic_path = [roic_start + (roic_term - roic_start) * (t / float(N)) for t in range(1, N + 1)]

        # Project NOPAT by compounding with g_t
        nopat = nopat0
        fcffs = []
        for t in range(N):
            g_t = g_path[t]
            roic_t = max(0.02, roic_path[t])
            nopat = nopat * (1.0 + g_t)
            # Value-driver identity
            fcff_t = nopat * (1.0 - (g_t / roic_t))
            fcffs.append(fcff_t)

        # Discount FCFFs
        ev_pv = 0.0
        for t, fcff in enumerate(fcffs, start=1):
            ev_pv += fcff / ((1.0 + WACC) ** t)

        # Terminal year values (apply stable gT and ROIC_T to NOPAT_N)
        nopat_N = nopat  # last computed
        roic_N = max(0.02, roic_path[-1])
        fcff_N1 = (nopat_N * (1.0 + gT)) * (1.0 - (gT / roic_N))
        TV = fcff_N1 / (WACC - gT)
        pv_TV = TV / ((1.0 + WACC) ** N)

        EV = ev_pv + pv_TV

        equity_value = EV - float(net_debt)
        fv_per_share = equity_value / float(shares)

        if not (fv_per_share == fv_per_share):  # NaN
            raise StrategyInputError(f"{self._name}: computation failed")

        return float(fv_per_share)
