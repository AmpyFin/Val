import types
from Strategies.peter_lynch import PeterLynchSimple
from Strategies.psales_reversion import PSalesReversion

def cfg(**kw):
    # Minimal config-like object with .caps attr
    c = types.SimpleNamespace()
    c.caps = {"max_growth_pe": 50, "min_growth_pe": 5}
    c.caps.update(kw.get("caps", {}))
    return c

def test_peter_lynch_basic():
    s = PeterLynchSimple(config=cfg())
    fv = s.compute("ACME", {"eps_ttm": 2.0, "growth_pct": 20.0})
    assert fv == 40.0  # 2 * 20

def test_peter_lynch_clamps_low():
    s = PeterLynchSimple(config=cfg())
    fv = s.compute("ACME", {"eps_ttm": 3.0, "growth_pct": 2.0})  # below min 5
    assert fv == 15.0

def test_peter_lynch_negative_eps_returns_none():
    s = PeterLynchSimple(config=cfg())
    assert s.compute("ACME", {"eps_ttm": -1.0, "growth_pct": 20.0}) is None

def test_psales_reversion_median_times_sps():
    s = PSalesReversion(config=cfg())
    data = {"sales_per_share": 10.0, "ps_history": [1, 2, 10, 4, 5]}
    fv = s.compute("ACME", data)
    # median([1,2,10,4,5]) = 4 -> 4 * 10 = 40
    assert fv == 40.0

def test_psales_reversion_missing_history_returns_none():
    s = PSalesReversion(config=cfg())
    assert s.compute("ACME", {"sales_per_share": 10.0, "ps_history": []}) is None
