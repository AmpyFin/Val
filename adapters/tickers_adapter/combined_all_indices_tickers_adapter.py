# adapters/tickers_adapter/combined_all_indices_tickers_adapter.py
from __future__ import annotations

from typing import List

from adapters.adapter import TickersAdapter, DataNotAvailable
from adapters.tickers_adapter.wiki_spy_500_tickers_adapter import WikiSPY500TickersAdapter
from adapters.tickers_adapter.wiki_sp400_tickers_adapter import WikiSP400TickersAdapter
from adapters.tickers_adapter.wiki_sp600_tickers_adapter import WikiSP600TickersAdapter
from adapters.tickers_adapter.wiki_ndaq_100_tickers_adapter import WikiNDAQ100TickersAdapter
# PHLX Semiconductor adapter removed per user request


class CombinedAllIndicesTickersAdapter(TickersAdapter):
    """
    Combines tickers from S&P 500, S&P 400, S&P 600, and NASDAQ 100 indices,
    removing duplicates.
    
    This adapter fetches tickers from all major indices and returns a unified list
    where each ticker appears only once, even if it exists in multiple indices.
    
    Indices included:
    - S&P 500 (Large Cap)
    - S&P 400 (Mid Cap) 
    - S&P 600 (Small Cap)
    - NASDAQ 100
    """

    def __init__(self) -> None:
        self._name = "combined_all_indices_tickers"
        self._spy500_adapter = WikiSPY500TickersAdapter()
        self._sp400_adapter = WikiSP400TickersAdapter()
        self._sp600_adapter = WikiSP600TickersAdapter()
        self._ndaq100_adapter = WikiNDAQ100TickersAdapter()

    def get_name(self) -> str:
        return self._name

    def fetch(self) -> List[str]:
        try:
            # Fetch tickers from all sources
            all_tickers = []
            
            # Collect tickers from each adapter, handling potential failures gracefully
            adapters = [
                ("S&P 500", self._spy500_adapter),
                ("S&P 400", self._sp400_adapter),
                ("S&P 600", self._sp600_adapter),
                ("NASDAQ 100", self._ndaq100_adapter)
            ]
            
            successful_fetches = 0
            for adapter_name, adapter in adapters:
                try:
                    tickers = adapter.fetch()
                    all_tickers.extend(tickers)
                    successful_fetches += 1
                except DataNotAvailable as e:
                    # Log the failure but continue with other adapters
                    print(f"Warning: Failed to fetch {adapter_name} tickers: {e}")
                    continue
            
            if successful_fetches == 0:
                raise DataNotAvailable(f"{self._name}: all underlying adapters failed")
            
            # Remove duplicates while preserving order
            combined_tickers = []
            seen_tickers = set()
            
            for ticker in all_tickers:
                if ticker not in seen_tickers:
                    combined_tickers.append(ticker)
                    seen_tickers.add(ticker)
            
            if not combined_tickers:
                raise DataNotAvailable(f"{self._name}: empty combined tickers list")
            
            return combined_tickers
            
        except DataNotAvailable:
            raise
        except Exception as exc:
            raise DataNotAvailable(f"{self._name}: failed to combine tickers from all indices") from exc
