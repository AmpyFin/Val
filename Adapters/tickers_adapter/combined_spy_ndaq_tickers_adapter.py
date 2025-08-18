# adapters/tickers_adapter/combined_spy_ndaq_tickers_adapter.py
from __future__ import annotations

from typing import List

from adapters.adapter import TickersAdapter, DataNotAvailable
from adapters.tickers_adapter.wiki_spy_500_tickers_adapter import WikiSPY500TickersAdapter
from adapters.tickers_adapter.wiki_ndaq_100_tickers_adapter import WikiNDAQ100TickersAdapter
from adapters.tickers_adapter.list_static_tickers_adapter import ListStaticTickersAdapter

class CombinedSPYNDAQTickersAdapter(TickersAdapter):
    """
    Combines S&P 500 and NASDAQ 100 tickers, removing duplicates.
    
    This adapter fetches tickers from both sources and returns a unified list
    where each ticker appears only once, even if it exists in both indices.
    """

    def __init__(self) -> None:
        self._name = "combined_spy_ndaq_tickers"
        self._spy_adapter = WikiSPY500TickersAdapter()
        self._ndaq_adapter = WikiNDAQ100TickersAdapter()
        self._list_adapter = ListStaticTickersAdapter()

    def get_name(self) -> str:
        return self._name

    def fetch(self) -> List[str]:
        try:
            # Fetch tickers from both sources
            spy_tickers = self._spy_adapter.fetch()
            ndaq_tickers = self._ndaq_adapter.fetch()
            list_tickers = self._list_adapter.fetch()
            # Combine and remove duplicates while preserving order
            combined_tickers = []
            seen_tickers = set()
            
            # Add all tickers, keeping only the first occurrence
            for ticker in spy_tickers + ndaq_tickers + list_tickers:
                if ticker not in seen_tickers:
                    combined_tickers.append(ticker)
                    seen_tickers.add(ticker)
            
            if not combined_tickers:
                raise DataNotAvailable(f"{self._name}: empty combined tickers list")
            
            return combined_tickers
            
        except DataNotAvailable:
            raise
        except Exception as exc:
            raise DataNotAvailable(f"{self._name}: failed to combine tickers from S&P 500 and NASDAQ 100") from exc 