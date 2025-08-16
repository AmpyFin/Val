from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import logging

class BaseAdapter(ABC):
    name: str = "base"
    fields_provided: List[str] = []

    def __init__(self, config: Any, logger: Optional[logging.Logger] = None):
        self.config = config
        self.logger = logger

    @abstractmethod
    def fetch_one(self, ticker: str) -> Dict[str, Any]:
        """Return normalized fields for a single ticker."""
        ...

    def fetch_many(self, tickers: List[str]) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for t in tickers:
            try:
                out[t] = self.fetch_one(t)
            except Exception as e:
                if self.logger:
                    self.logger.exception(f"[{self.name}] fetch_one failed for {t}: {e}")
        return out
