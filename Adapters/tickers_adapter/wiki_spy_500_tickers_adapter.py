# adapters/tickers_adapter/wiki_spy_500_tickers_adapter.py
from __future__ import annotations

import io
from typing import List

import requests
import pandas as pd

from adapters.adapter import TickersAdapter, DataNotAvailable

WIKI_SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
HTTP_TIMEOUT = 15
HEADERS = {"User-Agent": "ampyfin-val-model/1.0 (+https://example.org)"}


class WikiSPY500TickersAdapter(TickersAdapter):
    """
    Scrapes S&P 500 constituents from Wikipedia and returns a list of ticker symbols.

    Notes:
    - Symbols like BRK.B appear with a dot on Wikipedia. Some data providers (e.g., Yahoo)
      expect a dash (BRK-B). We return the symbol verbatim from Wikipedia; downstream
      adapters can normalize if needed.
    """

    def __init__(self) -> None:
        self._name = "wiki_spy_500_tickers"

    def get_name(self) -> str:
        return self._name

    def fetch(self) -> List[str]:
        try:
            resp = requests.get(WIKI_SP500_URL, timeout=HTTP_TIMEOUT, headers=HEADERS)
            if resp.status_code != 200:
                raise DataNotAvailable(f"{self._name}: HTTP {resp.status_code}")

            # Use pandas to parse the first table containing a 'Symbol' column
            tables = pd.read_html(io.StringIO(resp.text), flavor="lxml")
            candidates = [t for t in tables if any(str(col).lower() in ("symbol", "ticker") for col in t.columns)]
            if not candidates:
                raise DataNotAvailable(f"{self._name}: could not locate table with Symbol/Ticker")

            df = candidates[0]
            # Prefer 'Symbol' column; fallback to 'Ticker'
            col = "Symbol" if "Symbol" in df.columns else ("Ticker" if "Ticker" in df.columns else None)
            if col is None:
                raise DataNotAvailable(f"{self._name}: missing Symbol/Ticker column")

            symbols = (
                df[col]
                .astype(str)
                .str.strip()
                .str.upper()
                .tolist()
            )

            # Basic sanitation: drop blanks, de-duplicate
            symbols = [s for s in symbols if s and s != "NAN"]
            symbols = list(dict.fromkeys(symbols))  # preserve order, unique
            if not symbols:
                raise DataNotAvailable(f"{self._name}: empty symbols list after parsing")

            return symbols

        except DataNotAvailable:
            raise
        except Exception as exc:
            raise DataNotAvailable(f"{self._name}: failed to fetch/parse S&P 500 tickers") from exc
