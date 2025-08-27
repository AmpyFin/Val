# adapters/tickers_adapter/wiki_ndaq_100_tickers_adapter.py
from __future__ import annotations

import io
from typing import List

import requests
import pandas as pd

from adapters.adapter import TickersAdapter, DataNotAvailable

WIKI_NDQ100_URL = "https://en.wikipedia.org/wiki/Nasdaq-100"
HTTP_TIMEOUT = 15
HEADERS = {"User-Agent": "ampyfin-val-model/1.0 (+https://example.org)"}


class WikiNDAQ100TickersAdapter(TickersAdapter):
    """
    Scrapes Nasdaq-100 constituents from Wikipedia and returns a list of ticker symbols.

    We search for the first table containing a 'Ticker' or 'Symbol' column.
    """

    def __init__(self) -> None:
        self._name = "wiki_ndaq_100_tickers"

    def get_name(self) -> str:
        return self._name

    def fetch(self) -> List[str]:
        try:
            resp = requests.get(WIKI_NDQ100_URL, timeout=HTTP_TIMEOUT, headers=HEADERS)
            if resp.status_code != 200:
                raise DataNotAvailable(f"{self._name}: HTTP {resp.status_code}")

            tables = pd.read_html(io.StringIO(resp.text), flavor="lxml")
            candidates = [t for t in tables if any(str(col).lower() in ("ticker", "symbol") for col in t.columns)]
            if not candidates:
                raise DataNotAvailable(f"{self._name}: could not locate table with Ticker/Symbol")

            df = candidates[0]
            col = "Ticker" if "Ticker" in df.columns else ("Symbol" if "Symbol" in df.columns else None)
            if col is None:
                raise DataNotAvailable(f"{self._name}: missing Ticker/Symbol column")

            symbols = (
                df[col]
                .astype(str)
                .str.strip()
                .str.upper()
                .tolist()
            )

            symbols = [s for s in symbols if s and s != "NAN"]
            symbols = list(dict.fromkeys(symbols))
            if not symbols:
                raise DataNotAvailable(f"{self._name}: empty symbols list after parsing")

            return symbols

        except DataNotAvailable:
            raise
        except Exception as exc:
            raise DataNotAvailable(f"{self._name}: failed to fetch/parse Nasdaq-100 tickers") from exc
