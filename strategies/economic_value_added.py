# strategies/economic_value_added.py
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


class EconomicValueAddedStrategy(Strategy):
    """
    Economic Value Added (EVA) — enterprise value via PV of EVA + invested capital,
    then to equity per share.

    Core identity:
        EVA_t = (ROIC_t - WACC) * IC_{t-1}

    Enterprise Value:
        EV_ops = IC_0
                 + Σ_{t=1..N} [ EVA_t / (1+WACC)^t ]
                 + [ EVA_{N+1} / (WACC - g_T) ] / (1+WACC)^N
      with EVA_{N+1} = (ROIC_T - WACC) * IC_N * (1 + g_T)

    Equity value per share:
        Equity = EV_ops - NetDebt
        FV     = Equity / Shares

    Paths (simple, robust):
      • Capital growth path (IC growth): linear fade from g_start → g_T over N years.
      • ROIC path: linear fade from ROIC_0 → ROIC_T over N years.

    Inputs (canonical keys):
      - ebit_ttm
      - shares_outstanding
      - book_value_per_share
      - net_debt

    Hyperparameters (defaults):
      - eva_wacc             (default 0.10)    clamp 0.06..0.18
      - eva_tax_rate         (default 0.21)    clamp 0.00..0.35
      - eva_horizon_years N  (default 8)       clamp 3..15
      - eva_g_capital_start  (optional → fallback eps_cagr_5y or 0.10) clamp 0.00..0.25
      - eva_g_terminal g_T   (default 0.02)    clamp -0.01..0.03, must be < WACC
      - eva_roic_start       (optional; else inferred from NOPAT_0 / IC_0)
      - eva_roic_terminal    (default 0.12)    clamp 0.04..0.30

    Notes:
      - IC_0 ≈ BVPS * Shares + max(0, NetDebt). Requires upstream currency/share-class normalization.
      - If ROIC path dips too low or IC becomes non-positive, we guard with small floors & raise if needed.
    """

    def __init__(self) -> None:
        self._name = "economic_value_added"

    def get_name(self) -> str:
        return self._name

    def run(self, params: Dict[str, Any]) -> float:
        ebit = _f(params.get("ebit_ttm"))
        shares = _f(params.get("shares_outstanding"))
        bvps = _f(params.get("book_value_per_share"))
        net_debt = _f(params.get("net_debt"))
        eps_cagr = _f(params.get("eps_cagr_5y"))

        if shares is None or shares <= 0:
            raise StrategyInputError(f"{self._name}: shares_outstanding must be > 0")
        if ebit is None:
            raise StrategyInputError(f"{self._name}: ebit_ttm missing")
        if bvps is None or bvps <= 0:
            raise StrategyInputError(f"{self._name}: book_value_per_share must be > 0")
        if net_debt is None:
            net_debt = 0.0

        # Hyperparameters & clamps
        WACC = _f(params.get("eva_wacc", 0.10)) or 0.10
        WACC = max(0.06, min(0.18, WACC))

        tax = _f(params.get("eva_tax_rate", 0.21)) or 0.21
        tax = max(0.00, min(0.35, tax))

        N = int(params.get("eva_horizon_years", 8) or 8)
        N = max(3, min(15, N))

        g_start = _f(params.get("eva_g_capital_start"))
        if g_start is None:
            g_start = eps_cagr if eps_cagr is not None else 0.10
        g_start = max(0.00, min(0.25, g_start))

        g_T = _f(params.get("eva_g_terminal", 0.02)) or 0.02
        g_T = max(-0.01, min(0.03, g_T))
        if WACC <= g_T:
            raise StrategyInputError(f"{self._name}: WACC must exceed terminal growth (WACC={WACC:.3f}, g_T={g_T:.3f})")

        roic_start = _f(params.get("eva_roic_start"))
        roic_T = _f(params.get("eva_roic_terminal", 0.12)) or 0.12
        roic_T = max(0.04, min(0.30, roic_T))

        # Derive NOPAT_0, Invested Capital IC_0, ROIC_0
        nopat0 = float(ebit) * (1.0 - tax)

        equity_bv = float(bvps) * float(shares)
        IC0 = equity_bv + max(0.0, float(net_debt))
        if IC0 <= 0:
            raise StrategyInputError(f"{self._name}: inferred invested capital (IC0) non-positive")

        if roic_start is None or roic_start <= 0:
            roic_start = max(0.02, min(0.60, nopat0 / IC0))

        # Build paths (length N, for t=1..N)
        g_cap = [g_start + (g_T - g_start) * (t / float(N)) for t in range(1, N + 1)]
        roic_path = [roic_start + (roic_T - roic_start) * (t / float(N)) for t in range(1, N + 1)]

        # Iterate EVA and capital
        IC_prev = IC0
        pv_eva = 0.0
        for t in range(N):
            roic_t = max(0.02, roic_path[t])
            eva_t = (roic_t - WACC) * IC_prev
            pv_eva += eva_t / ((1.0 + WACC) ** (t + 1))
            # grow invested capital
            g_it = g_cap[t]
            IC_prev = IC_prev * (1.0 + g_it)
            if IC_prev <= 0:
                raise StrategyInputError(f"{self._name}: invested capital became non-positive during projection")

        # Terminal EVA (year N+1) on IC_N grown by g_T, with ROIC_T
        IC_N = IC_prev
        eva_N1 = (max(0.02, roic_T) - WACC) * (IC_N * (1.0 + g_T))
        pv_tv = (eva_N1 / (WACC - g_T)) / ((1.0 + WACC) ** N)

        EV_ops = IC0 + pv_eva + pv_tv
        equity_value = EV_ops - float(net_debt)
        fv_per_share = equity_value / float(shares)

        if not (fv_per_share == fv_per_share):  # NaN guard
            raise StrategyInputError(f"{self._name}: computation failed")

        return float(fv_per_share)
