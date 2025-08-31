# strategies/pvgo.py
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


class PVGOStrategy(Strategy):
    """
    PVGO (Present Value of Growth Opportunities) — fair value per share.

    Decomposition identity:
        P0 = (E1 / r) + PVGO
    with Gordon / ROE–retention link:
        g = b * ROE,  payout = 1 - b

    Practical pricing formula used here:
        P0 = E1 * payout / (r - g)     (same as justified P/E with E1)
      where:
        E1 = EPS * (1 + g) if pvgo_use_forward_eps=True else EPS
        ROE ≈ EPS / BVPS   (per-share approximation)
        payout inferred from dividends if available, else default

    We return P0 (total fair value), not just PVGO, but this model is useful
    because it conceptually separates "no-growth value" (E1/r) from the PVGO
    component. (We keep safeguards to avoid g ~ r explosions.)

    Required metrics (canonical keys):
      - eps_ttm
      - book_value_per_share

    Optional metrics:
      - dividend_ttm   (to infer payout)

    Tunable hyperparameters (conservative defaults):
      - pvgo_discount_rate   (r)   default 0.10, clamp 0.05..0.20
      - pvgo_default_payout        default 0.30  (used if dividend_ttm unavailable)
      - pvgo_floor_payout          default 0.05  (avoid degenerate near-zero payout)
      - pvgo_use_forward_eps       default True  (E1 = EPS*(1+g))
      - pvgo_cap_roe               default 0.35  (cap ROE used in model)
      - pvgo_cap_g                 default 0.12  (cap long-run g), clamp -0.02..0.15

    Raises StrategyInputError on invalid inputs.
    """

    def __init__(self) -> None:
        self._name = "pvgo"

    def get_name(self) -> str:
        return self._name

    def run(self, params: Dict[str, Any]) -> float:
        eps = _f(params.get("eps_ttm"))
        bvps = _f(params.get("book_value_per_share"))
        if eps is None or eps <= 0:
            raise StrategyInputError(f"{self._name}: EPS must be > 0")
        if bvps is None or bvps <= 0:
            raise StrategyInputError(f"{self._name}: BVPS must be > 0")

        # Discount rate
        r = _f(params.get("pvgo_discount_rate", 0.10)) or 0.10
        r = max(0.05, min(0.20, r))

        # ROE (per-share approximation), capped
        roe_cap = _f(params.get("pvgo_cap_roe", 0.35)) or 0.35
        roe_cap = max(0.05, min(0.60, roe_cap))
        roe = min(eps / bvps, roe_cap)

        # Payout (from dividends if available; else default)
        div = _f(params.get("dividend_ttm"))
        if div is not None and eps > 0:
            payout = max(0.0, min(1.0, div / eps))
        else:
            payout = _f(params.get("pvgo_default_payout", 0.30)) or 0.30
            payout = max(_f(params.get("pvgo_floor_payout", 0.05)) or 0.05, min(1.0, payout))
        b = 1.0 - payout  # retention

        # Long-run growth g = b * ROE, capped conservatively
        g_cap = _f(params.get("pvgo_cap_g", 0.12)) or 0.12
        g_cap = max(-0.02, min(0.15, g_cap))
        g = max(-0.02, min(g_cap, b * roe))

        if r <= g:
            raise StrategyInputError(f"{self._name}: discount_rate must exceed growth (r={r:.3f}, g={g:.3f})")

        # E1: forward or trailing EPS
        use_fwd = bool(params.get("pvgo_use_forward_eps", True))
        E1 = float(eps) * (1.0 + g) if use_fwd else float(eps)

        # Price via payout/(r-g); algebraically P0 = (E1/r) + PVGO, we return P0
        P0 = E1 * payout / (r - g)

        if not (P0 == P0):  # NaN
            raise StrategyInputError(f"{self._name}: computation failed")

        return float(P0)
