import os, json, importlib, types, tempfile
from fastapi.testclient import TestClient

def test_results_and_filtering(tmp_path, monkeypatch):
    # Write a tiny results.json
    payload = {
        "generated_at": "2025-01-01T00:00:00Z",
        "min_mos": 0.2,
        "tickers": [
            {"ticker":"A","price":10,"best_fair_value":12,"best_mos":0.2,"best_strategy":"x","undervalued":True},
            {"ticker":"B","price":10,"best_fair_value":9,"best_mos":-0.111,"best_strategy":"x","undervalued":False},
        ]
    }
    p = tmp_path / "results.json"
    p.write_text(json.dumps(payload))

    # Ensure server.api reads THIS path on import
    monkeypatch.setenv("AMPYFIN_RESULTS_PATH", str(p))

    # Import fresh with env set
    import server.api as api
    importlib.reload(api)

    client = TestClient(api.app)

    # /results (all)
    r = client.get("/results")
    assert r.status_code == 200
    data = r.json()
    assert len(data["tickers"]) == 2

    # /results undervalued_only + min_mos override
    r = client.get("/results", params={"undervalued_only": "true", "min_mos": "0.25"})
    assert r.status_code == 200
    data = r.json()
    # A has 0.2 MoS, so with 0.25 filter it should be excluded
    assert len(data["tickers"]) == 0
