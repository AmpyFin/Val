# strategies/dcf_gordon.py
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


class DCFGordonStrategy(Strategy):
    """
    Discounted Cash Flow (DCF) with Gordon Growth terminal value.

    EV = sum_{t=1..N} [ FCF_t / (1+r)^t ] + [ FCF_{N+1} / (r - g_T) ] / (1+r)^N
      where: FCF_{t} = FCF_{t-1} * (1+g)
            FCF_{N+1} = FCF_{N} * (1+g_T)

    Equity = EV - NetDebt
    Fair Value per share = Equity / SharesOutstanding

    Required metrics (canonical keys):
      - fcf_ttm              (USD)
      - shares_outstanding   (count)
      - net_debt             (USD; can be negative = net cash)
      - eps_cagr_5y          (decimal, optional fallback to set growth)

    Tunable hyperparameters (read from params; sensible defaults here):
      - dcf_years              (int, default 5, clamp 1..10)
      - dcf_discount_rate      (decimal, default 0.10, clamp 0.05..0.20)
      - dcf_terminal_growth    (decimal, default 0.03, clamp -0.02..0.05; must be < discount rate)
      - dcf_growth_rate        (decimal, optional; if None we use eps_cagr_5y; clamp -0.10..0.35)
      - dcf_negative_equity_handling  (str: 'exclude' | 'zero' | 'allow'; default 'exclude')
         * 'exclude': raise StrategyInputError so pipeline records None for this strategy/ticker
         * 'zero'   : return 0.0 fair value per share
         * 'allow'  : return the negative fair value per share as computed
    """

    def __init__(self) -> None:
        self._name = "dcf_gordon"

    def get_name(self) -> str:
        return self._name

    def run(self, params: Dict[str, Any]) -> float:
        # --- Required core inputs
        fcf0 = _to_float(params.get("fcf_ttm"))
        sh = _to_float(params.get("shares_outstanding"))
        net_debt = _to_float(params.get("net_debt", 0.0))

        if fcf0 is None:
            raise StrategyInputError(f"{self._name}: missing fcf_ttm")
        if sh is None or sh <= 0:
            raise StrategyInputError(f"{self._name}: missing/invalid shares_outstanding")
        if net_debt is None:
            net_debt = 0.0

        # --- Growth inputs
        g_explicit = params.get("dcf_growth_rate", None)
        g = _to_float(g_explicit)
        if g is None:
            g = _to_float(params.get("eps_cagr_5y"))
        if g is None:
            g = 0.08  # fallback if no growth hint
        g = max(-0.10, min(0.35, g))  # clamp

        # --- Horizon / discount / terminal growth
        years = int(params.get("dcf_years", 5) or 5)
        years = max(1, min(10, years))

        r = _to_float(params.get("dcf_discount_rate", 0.10)) or 0.10
        r = max(0.05, min(0.20, r))

        gT = _to_float(params.get("dcf_terminal_growth", 0.03)) or 0.03
        gT = max(-0.02, min(0.05, gT))

        if r <= gT:
            raise StrategyInputError(f"{self._name}: discount_rate must be > terminal_growth")

        # --- Project & discount FCFs
        ev_pv = 0.0
        fcf_t = float(fcf0)
        for t in range(1, years + 1):
            fcf_t = fcf_t * (1.0 + g)
            ev_pv += fcf_t / ((1.0 + r) ** t)

        # Terminal value at year N (as of N), then PV to today
        fcf_N_plus_1 = fcf_t * (1.0 + gT)
        tv_N = fcf_N_plus_1 / (r - gT)
        tv_pv = tv_N / ((1.0 + r) ** years)

        ev = ev_pv + tv_pv

        # Equity bridge
        equity = ev - float(net_debt)

        # Negative handling policy
        neg_policy = str(params.get("dcf_negative_equity_handling", "exclude")).lower()
        if equity <= 0:
            if neg_policy == "exclude":
                raise StrategyInputError(f"{self._name}: negative equity under assumptions (ev={ev:.2f}, net_debt={net_debt:.2f})")
            elif neg_policy == "zero":
                return 0.0
            # else 'allow': fall through and compute negative per-share

        # Per-share fair value
        fv_per_share = equity / float(sh)
        return float(fv_per_share)
