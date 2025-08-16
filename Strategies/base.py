from abc import ABC, abstractmethod
from typing import Any, Optional
import logging

class BaseStrategy(ABC):
    name: str = "base"

    def __init__(self, config: Any, logger: Optional[logging.Logger] = None):
        self.config = config
        self.logger = logger

    @abstractmethod
    def compute(self, ticker: str, data: dict) -> Optional[float]:
        """Return fair value (float) or None if not applicable/insufficient data."""
        ...
