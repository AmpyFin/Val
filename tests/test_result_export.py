import json
import tempfile
import types
from Pipeline import result as result_stage

class DummyLogger:
    def info(self, *a, **k): pass

def test_result_stage_writes_json(tmp_path):
    # Build a minimal ctx
    cfg = types.SimpleNamespace()
    cfg.thresholds = {"min_mos": 0.2}
    cfg.outputs = {"json_path": str(tmp_path / "results.json"), "include_per_strategy": True}

    ctx = types.SimpleNamespace()
    ctx.config = cfg
    ctx.logger = DummyLogger()
    ctx.results = {
        "summary": {
            "AAPL": {"price": 100.0, "best_strategy": "psales_rev", "best_fv": 120.0, "best_mos": 0.1667, "undervalued": False},
            "NVAX": {"price": 10.0, "best_strategy": "peter_lynch", "best_fv": 20.0, "best_mos": 0.5, "undervalued": True},
        },
        "per_strategy": {
            "psales_rev": {"AAPL": {"fv": 120.0, "mos": 0.1667}},
            "peter_lynch": {"NVAX": {"fv": 20.0, "mos": 0.5}},
        }
    }

    # Run and verify
    result_stage.run(ctx, limit=10)
    out = tmp_path / "results.json"
    assert out.exists(), "results.json should be created"

    data = json.loads(out.read_text())
    assert "generated_at" in data
    assert len(data["tickers"]) == 2
    aapl = next(t for t in data["tickers"] if t["ticker"] == "AAPL")
    assert aapl["best_strategy"] == "psales_rev"
