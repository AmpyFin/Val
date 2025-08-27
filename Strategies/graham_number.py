# strategies/graham_number.py
from __future__ import annotations

import math
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


class GrahamNumberStrategy(Strategy):
    """
    Graham Number (Benjamin Graham) — conservative fair value per share.

    Formula (default caps P/E=15, P/B=1.5):
        FV = sqrt( (PE_cap * PB_cap) * EPS * BVPS )  = sqrt(22.5 * EPS * BVPS)

    Required metrics (canonical keys):
      - eps_ttm                 (EPS per share, TTM)
      - book_value_per_share    (BVPS)

    Tunable hyperparameters:
      - graham_pe_cap     (default 15.0, clamp 1..40)
      - graham_pb_cap     (default 1.5, clamp 0.2..10)
      - graham_multiplier (optional) if provided, overrides pe_cap*pb_cap

    Notes:
    - If EPS<=0 or BVPS<=0, the classic Graham number is undefined; we raise
      StrategyInputError so the pipeline treats it as N/A for that ticker.
    """

    def __init__(self) -> None:
        self._name = "graham_number"

    def get_name(self) -> str:
        return self._name

    def run(self, params: Dict[str, Any]) -> float:
        eps = _to_float(params.get("eps_ttm"))
        bvps = _to_float(params.get("book_value_per_share"))
        if eps is None or eps <= 0:
            raise StrategyInputError(f"{self._name}: EPS must be > 0")
        if bvps is None or bvps <= 0:
            raise StrategyInputError(f"{self._name}: BVPS must be > 0")

        mult = _to_float(params.get("graham_multiplier"))
        if mult is None:
            pe_cap = _to_float(params.get("graham_pe_cap", 15.0)) or 15.0
            pb_cap = _to_float(params.get("graham_pb_cap", 1.5)) or 1.5
            # clamp to sane ranges
            pe_cap = max(1.0, min(40.0, pe_cap))
            pb_cap = max(0.2, min(10.0, pb_cap))
            mult = pe_cap * pb_cap

        if mult <= 0:
            raise StrategyInputError(f"{self._name}: invalid multiplier")

        try:
            fv = math.sqrt(float(mult) * float(eps) * float(bvps))
            return float(fv)
        except Exception as e:
            raise StrategyInputError(f"{self._name}: failed to compute") from e
