# adapters/adapter.py
"""
AmpyFin — Val Model
Adapter contracts (interfaces).

Rules:
- Each adapter serves ONE purpose and returns ONE metric only.
- Metric adapters return a primitive number (float) for a single ticker.
- Tickers adapters return a list of ticker symbols (List[str]).
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import List


class AdapterError(RuntimeError):
    """Generic adapter error."""


class DataNotAvailable(AdapterError):
    """Raised when the provider cannot supply the requested data."""


def retry_on_failure(max_retries=3, delay=2.0):
    """Decorator to retry adapter fetch operations on failure."""
    def decorator(func):
        def wrapper(self, ticker: str) -> float:
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(self, ticker)
                except DataNotAvailable as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        time.sleep(delay)
                        continue
                    raise
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        time.sleep(delay)
                        continue
                    raise DataNotAvailable(f"{self._name}: failed after {max_retries} attempts") from e
            raise last_exception
        return wrapper
    return decorator


def retry_on_rate_limit(max_retries=3, base_delay=5.0):
    """Decorator to retry adapter fetch operations specifically on rate limiting."""
    def decorator(func):
        def wrapper(self, ticker: str) -> float:
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(self, ticker)
                except DataNotAvailable as e:
                    # Check if this is a rate limiting error
                    error_msg = str(e).lower()
                    if any(phrase in error_msg for phrase in ['rate limit', 'too many requests', 'rate limited', 'possibly rate limited']):
                        last_exception = e
                        if attempt < max_retries - 1:
                            # Use the session management rate limiting handler
                            from adapters.yf_session import handle_rate_limit
                            handle_rate_limit()
                            continue
                        else:
                            raise DataNotAvailable(f"{self._name}: rate limited after {max_retries} attempts") from e
                    else:
                        # Not a rate limiting error, re-raise immediately
                        raise
                except Exception as e:
                    # Check if this is a rate limiting error from yfinance
                    error_msg = str(e).lower()
                    if any(phrase in error_msg for phrase in ['rate limit', 'too many requests', 'rate limited', 'possibly rate limited']):
                        last_exception = e
                        if attempt < max_retries - 1:
                            # Use the session management rate limiting handler
                            from adapters.yf_session import handle_rate_limit
                            handle_rate_limit()
                            continue
                        else:
                            raise DataNotAvailable(f"{self._name}: rate limited after {max_retries} attempts") from e
                    else:
                        # Not a rate limiting error, re-raise immediately
                        raise DataNotAvailable(f"{self._name}: failed after {max_retries} attempts") from e
            raise last_exception
        return wrapper
    return decorator


class MetricAdapter(ABC):
    """
    Contract for single-metric adapters (e.g., current price, EPS TTM, FCF TTM).
    Implementations must return a numeric value (float).
    """

    @abstractmethod
    def get_name(self) -> str:
        """Human-readable adapter name (e.g., 'yfinance_current_price')."""
        raise NotImplementedError

    @abstractmethod
    def fetch(self, ticker: str) -> float:
        """
        Fetch the metric value for a given ticker.
        Must raise DataNotAvailable if the metric cannot be retrieved.
        """
        raise NotImplementedError


class TickersAdapter(ABC):
    """
    Contract for tickers source adapters (e.g., S&P 500 via Wikipedia).
    Implementations must return a list of ticker symbols.
    """

    @abstractmethod
    def get_name(self) -> str:
        """Human-readable adapter name (e.g., 'wiki_spy_500_tickers')."""
        raise NotImplementedError

    @abstractmethod
    def fetch(self) -> List[str]:
        """
        Return a list of ticker symbols (e.g., ['AAPL','MSFT',...]).
        Must raise DataNotAvailable if no list can be retrieved.
        """
        raise NotImplementedError
