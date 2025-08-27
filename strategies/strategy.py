# strategies/strategy.py
"""
AmpyFin — Val Model
Strategy contract (interface) for valuation models.

Each strategy:
- Implements get_name() -> str
- Implements run(params: dict) -> float   (returns a fair value PRICE per share)

Conventions:
- All inputs must be provided via 'params' with canonical keys (see README).
- Strategies should raise StrategyInputError if required inputs are missing/invalid.
- Strategies must return a float (can be float('nan') if not computable, but prefer raising).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class StrategyError(RuntimeError):
    """Base class for strategy-related errors."""


class StrategyInputError(StrategyError):
    """Raised when required inputs are missing or invalid."""


class Strategy(ABC):
    """Abstract base class for all valuation strategies."""

    @abstractmethod
    def get_name(self) -> str:
        """Human-readable strategy name (e.g., 'peter_lynch')."""
        raise NotImplementedError

    @abstractmethod
    def run(self, params: Dict[str, Any]) -> float:
        """
        Compute and return a FAIR VALUE price per share as a float.
        Implementations should validate required inputs from 'params' and
        raise StrategyInputError with a clear message if something is missing.
        """
        raise NotImplementedError
