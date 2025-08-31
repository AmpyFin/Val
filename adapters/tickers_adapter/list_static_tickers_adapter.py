# adapters/tickers_adapter/list_static_tickers_adapter.py
from __future__ import annotations

from typing import List

from adapters.adapter import TickersAdapter, DataNotAvailable


class ListStaticTickersAdapter(TickersAdapter):
    """
    Returns a predefined static list of tickers.
    """

    def __init__(self) -> None:
        self._name = "list_static_tickers"

    def get_name(self) -> str:
        return self._name

    def fetch(self) -> List[str]:
        try:
            return [
                    "MRVL",
                    "GOOGL",
                    "AAPL",
                    "META",
                    "VZ",
                    "CMCSA",
                    ]

        except Exception as exc:  # pragma: no cover
            raise DataNotAvailable(f"{self._name}: unable to produce static tickers") from exc
