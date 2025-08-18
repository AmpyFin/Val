# tests/conftest.py
import os
import pytest

# Static tickers from our ListStaticTickersAdapter
STATIC_TICKERS = ["AAPL", "MSFT", "NVDA", "NVAX", "FSLR"]

def pytest_collection_modifyitems(config, items):
    # If AMPYFIN_TEST_OFFLINE is set, skip integration tests.
    if os.getenv("AMPYFIN_TEST_OFFLINE"):
        skip_integ = pytest.mark.skip(reason="AMPYFIN_TEST_OFFLINE set")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integ)

@pytest.fixture(scope="session")
def one_ticker():
    return "AAPL"

@pytest.fixture(scope="session")
def static_tickers():
    return list(STATIC_TICKERS)
