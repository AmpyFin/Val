# strategies/justified_pe_roe.py
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


class JustifiedPEROEStrategy(Strategy):
    """
    Justified P/E using ROE and payout (CFA / Gordon identity).

    Core identity (leading P/E):
        P0 / E1 = payout / (r - g)     where g = retention * ROE
      => Fair Value = E1 * payout / (r - g)

    Approximations:
      - ROE ≈ EPS / BVPS  (per-share approximation)
      - E1 defaults to EPS * (1 + g). You can set jpe_use_forward_eps=False to use EPS (TTM).

    Required metrics (canonical keys):
      - eps_ttm
      - book_value_per_share
      - (optional) dividend_ttm  # used to infer payout if retention not provided explicitly

    Tunable hyperparameters:
      - jpe_discount_rate     (r)   default 0.10, clamp 0.05..0.20
      - jpe_retention_ratio   (b)   optional; if not provided we infer payout from dividends or use default
      - jpe_default_payout          default 0.30 (used if no dividends info and no retention provided)
      - jpe_floor_payout            default 0.05 (avoid degenerate near-zero payout for growth firms)
      - jpe_use_forward_eps         default True (if True use E1 = EPS*(1+g); else E1=EPS)
      - jpe_max_long_run_g          default 0.12 (cap g), clamp to [-0.02..0.15]

    Behavior:
      - If EPS<=0 or BVPS<=0, raises StrategyInputError (N/A).
      - Ensures r > g; otherwise raises StrategyInputError.
    """

    def __init__(self) -> None:
        self._name = "justified_pe_roe"

    def get_name(self) -> str:
        return self._name

    def run(self, params: Dict[str, Any]) -> float:
        eps = _to_float(params.get("eps_ttm"))
        bvps = _to_float(params.get("book_value_per_share"))
        if eps is None or eps <= 0:
            raise StrategyInputError(f"{self._name}: EPS must be > 0")
        if bvps is None or bvps <= 0:
            raise StrategyInputError(f"{self._name}: BVPS must be > 0")

        # Discount rate
        r = _to_float(params.get("jpe_discount_rate", 0.10)) or 0.10
        r = max(0.05, min(0.20, r))

        # ROE per-share
        roe = float(eps) / float(bvps)

        # Retention / payout determination
        b = _to_float(params.get("jpe_retention_ratio"))  # may be None
        if b is None:
            # try to infer payout from dividends
            payout = None
            div = _to_float(params.get("dividend_ttm"))
            if div is not None and eps is not None and eps > 0:
                payout = float(div) / float(eps)
            if payout is None:
                payout = float(_to_float(params.get("jpe_default_payout", 0.30)) or 0.30)
            # floor & clamp payout [0..1]
            payout_floor = float(_to_float(params.get("jpe_floor_payout", 0.05)) or 0.05)
            payout = max(payout_floor, min(1.0, payout))
            b = 1.0 - payout
        else:
            # clamp retention [0..1] and derive payout
            b = max(0.0, min(1.0, float(b)))

        payout_from_b = 1.0 - b

        # Long-run growth g = b * ROE with conservative cap
        g_cap = float(_to_float(params.get("jpe_max_long_run_g", 0.12)) or 0.12)
        g_cap = max(-0.02, min(0.15, g_cap))
        g = max(-0.02, min(g_cap, b * roe))

        # Allow r >= g but ensure we don't get division by zero or negative values
        if r <= g:
            # For high-quality companies, growth can equal discount rate
            # Use a larger buffer to avoid extreme values when g approaches r
            g = r - 0.01

        # EPS one-year forward or trailing
        use_forward = bool(params.get("jpe_use_forward_eps", True))
        E1 = float(eps) * (1.0 + g) if use_forward else float(eps)

        fv = E1 * payout_from_b / (r - g)
        return float(fv)
