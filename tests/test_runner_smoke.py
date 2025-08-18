# tests/test_runner_smoke.py
import math
import pytest

from pipeline.runner import run_once

def _is_num(x):
    try:
        return isinstance(x, (int, float)) and not math.isnan(float(x))
    except Exception:
        return False

@pytest.mark.integration
def test_pipeline_run_once():
    ctx = run_once(write_json=False)

    # Tickers populated from custom list
    assert isinstance(ctx.tickers, list) and len(ctx.tickers) >= 1

    # We at least fetched a current price per ticker (may be None if transient errors)
    for tk in ctx.tickers:
        cur = ctx.metrics_by_ticker.get(tk, {}).get("current_price")
        if cur is not None:
            assert _is_num(cur) and cur > 0

    # Fair values mapping exists for each strategy (values may be None if inputs missing)
    assert isinstance(ctx.strategy_names, list) and len(ctx.strategy_names) >= 1
    for tk in ctx.tickers:
        fv_map = ctx.fair_values.get(tk, {})
        # Make sure all strategies are present as keys
        assert all(s in fv_map for s in ctx.strategy_names)

    # Results section is built
    for tk in ctx.tickers:
        rt = ctx.results_by_ticker.get(tk, {})
        assert "current_price" in rt
        assert "strategy_fair_values" in rt
        assert "consensus_fair_value" in rt
        assert "consensus_discount" in rt
