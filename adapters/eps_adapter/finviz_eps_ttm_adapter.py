# adapters/eps_adapter/finviz_eps_ttm_adapter.py
from __future__ import annotations

import re
from typing import Any, Optional

import requests

from adapters.adapter import MetricAdapter, DataNotAvailable, retry_on_failure


def _coerce(v: Optional[Any]) -> Optional[float]:
    try:
        if v is None:
            return None
        f = float(v)
        if f != f:  # NaN
            return None
        return f
    except Exception:
        return None


class FinvizEPSTTMAdapter(MetricAdapter):
    """
    Gets EPS TTM by scraping Finviz website.

    Strategy:
      - Scrape the Finviz quote page for the ticker
      - Look for EPS TTM in the fundamental data table
      - Parse the value and return as float
      - Uses retry mechanism for reliability

    Returns a float (USD per share).
    """

    def __init__(self) -> None:
        self._name = "finviz_eps_ttm"

    def get_name(self) -> str:
        return self._name

    @retry_on_failure(max_retries=3, delay=1.0)
    def fetch(self, ticker: str) -> float:
        try:
            # Construct Finviz URL
            url = f"https://finviz.com/quote.ashx?t={ticker.upper()}"
            
            # Headers to mimic a browser request
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
            
            # Make request
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Get the HTML content
            html_content = response.text
            
            # Look for EPS TTM in the fundamental data
            # Finviz shows EPS TTM with <b> tags around the value
            eps_patterns = [
                r'<td[^>]*>EPS\s*\(ttm\)</td>\s*<td[^>]*><b>([^<]+)</b></td>',  # EPS (ttm) with <b> tag
                r'<td[^>]*>EPS\s*\(ttm\)</td>\s*<td[^>]*>([^<]+)</td>',  # EPS (ttm) without <b> tag
                r'P/E\s*</td>\s*<td[^>]*>([^<]+)</td>',  # P/E ratio (fallback)
            ]
            
            # First try to find EPS TTM directly
            for pattern in eps_patterns:
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                if matches:
                    # Clean up the matched value
                    eps_str = matches[0].strip()
                    
                    # Handle different formats
                    if eps_str == 'N/A' or eps_str == '-' or eps_str == '':
                        continue
                    
                    # Try to extract EPS from P/E ratio if needed
                    if 'P/E' in pattern and eps_str != 'N/A':
                        try:
                            pe_ratio = _coerce(eps_str)
                            if pe_ratio is not None and pe_ratio > 0:
                                # We need to get the current price to calculate EPS
                                price_pattern = r'<td[^>]*>Price</td>\s*<td[^>]*><b>([^<]+)</b></td>'
                                price_matches = re.findall(price_pattern, html_content, re.IGNORECASE)
                                if price_matches:
                                    price_str = price_matches[0].strip()
                                    price = _coerce(price_str)
                                    if price is not None and price > 0:
                                        eps_ttm = price / pe_ratio
                                        return float(eps_ttm)
                        except Exception:
                            continue
                    
                    # Direct EPS value
                    eps_ttm = _coerce(eps_str)
                    if eps_ttm is not None:
                        return float(eps_ttm)
            
            # If we can't find EPS TTM directly, try to find it in the fundamental table
            # Look for the fundamental data section
            fundamental_section = re.search(r'<table[^>]*class="snapshot-table2"[^>]*>(.*?)</table>', html_content, re.DOTALL | re.IGNORECASE)
            if fundamental_section:
                section_html = fundamental_section.group(1)
                
                # Look for EPS in the fundamental table
                eps_matches = re.findall(r'<td[^>]*>EPS\s*\(ttm\)</td>\s*<td[^>]*><b>([^<]+)</b></td>', section_html, re.IGNORECASE)
                if eps_matches:
                    eps_str = eps_matches[0].strip()
                    if eps_str != 'N/A' and eps_str != '-':
                        eps_ttm = _coerce(eps_str)
                        if eps_ttm is not None:
                            return float(eps_ttm)
            
            raise DataNotAvailable(f"{self._name}: EPS TTM not found for {ticker}")

        except DataNotAvailable:
            raise
        except Exception as exc:
            raise DataNotAvailable(f"{self._name}: failed to fetch EPS TTM for {ticker}") from exc
