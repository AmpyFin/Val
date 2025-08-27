# strategies/justified_pb_roe.py
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


class JustifiedPBROEStrategy(Strategy):
    """
    Justified Price-to-Book using ROE (residual income steady-state identity):

        P0 / B0 = (ROE - g) / (r - g)      =>    Fair Value = BVPS * (ROE - g) / (r - g)

    where:
      - ROE = EPS / BVPS   (per-share approximation)
      - r   = required return (discount rate)
      - g   = long-run growth rate (must be < r; typically also < ROE)

    Required metrics (canonical keys):
      - eps_ttm
      - book_value_per_share
      - (optional) dividend_ttm     # used to infer retention if explicit growth not provided
      - (optional) eps_cagr_5y      # fallback long-run growth proxy

    Tunable hyperparameters (defaults chosen conservatively):
      - jpbr_discount_rate   (r)   default 0.10, clamp 0.05..0.20
      - jpbr_growth_rate     (g)   optional; if None uses:
                                   eps_cagr_5y, else retention*ROE, else 0.03
                                   clamp -0.02..0.08

    Behavior:
      - If EPS<=0 or BVPS<=0, raises StrategyInputError (N/A for that ticker).
      - If resulting g >= r or g >= ROE, raises StrategyInputError (avoids nonsensical P/B).
    """

    def __init__(self) -> None:
        self._name = "justified_pb_roe"

    def get_name(self) -> str:
        return self._name

    def run(self, params: Dict[str, Any]) -> float:
        eps = _to_float(params.get("eps_ttm"))
        bvps = _to_float(params.get("book_value_per_share"))
        if eps is None or eps <= 0:
            raise StrategyInputError(f"{self._name}: EPS must be > 0")
        if bvps is None or bvps <= 0:
            raise StrategyInputError(f"{self._name}: BVPS must be > 0")

        # ROE per-share approximation
        roe = float(eps) / float(bvps)

        # Required return
        r = _to_float(params.get("jpbr_discount_rate", 0.10)) or 0.10
        r = max(0.05, min(0.20, r))

        # Growth selection
        g = _to_float(params.get("jpbr_growth_rate"))
        if g is None:
            g = _to_float(params.get("eps_cagr_5y"))
        if g is None:
            # Infer from retention * ROE if we have dividends
            div = _to_float(params.get("dividend_ttm"))
            if div is not None and eps and eps > 0:
                payout = max(0.0, min(1.0, float(div) / float(eps)))
                retention = 1.0 - payout
                g = retention * roe
        if g is None:
            g = 0.03  # conservative fallback

        # Clamp long-run g to conservative band
        g = max(-0.02, min(0.08, float(g)))

        # Sanity conditions (avoid negative/undefined justified multiples)
        if r <= g:
            raise StrategyInputError(f"{self._name}: discount_rate must exceed growth (r={r:.3f}, g={g:.3f})")
        if roe <= g:
            raise StrategyInputError(f"{self._name}: ROE must exceed growth (roe={roe:.3f}, g={g:.3f})")

        # Justified P/B and fair value
        justified_pb = (roe - g) / (r - g)
        fv = float(bvps) * justified_pb
        return float(fv)
