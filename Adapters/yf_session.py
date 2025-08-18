# adapters/yf_session.py
from __future__ import annotations

import itertools
import threading
import time
from typing import List
try:
    from curl_cffi import requests as curl_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False
    import requests
    from requests.adapters import HTTPAdapter

try:
    # Retry is useful for transient 429/5xx; available via urllib3 (dependency of requests)
    from urllib3.util.retry import Retry  # type: ignore
except Exception:  # pragma: no cover
    Retry = None  # graceful fallback if not present

# A small pool of common desktop UA strings (rotated per session)
_UAS: List[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]

# Pre-create a pool of Session objects sharing nothing (separate connection pools)
_SESSIONS: List = []

if CURL_CFFI_AVAILABLE:
    # Use curl_cffi sessions for newer yfinance compatibility
    for ua in _UAS:
        s = curl_requests.Session()
        s.headers.update({"User-Agent": ua})
        _SESSIONS.append(s)
else:
    # Fallback to requests sessions for older yfinance versions
    for ua in _UAS:
        s = requests.Session()
        s.headers.update({"User-Agent": ua})
        # Pooling + optional retries
        if Retry is not None:
            retry = Retry(
                total=2,
                backoff_factor=0.3,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["GET", "HEAD", "OPTIONS"],
                raise_on_status=False,
            )
            adapter = HTTPAdapter(pool_connections=50, pool_maxsize=50, max_retries=retry)
        else:  # pragma: no cover
            adapter = HTTPAdapter(pool_connections=50, pool_maxsize=50)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        _SESSIONS.append(s)

# Round-robin index for fair use of the pool
_lock = threading.Lock()
_rr = itertools.cycle(range(len(_SESSIONS)))

# Track rate limiting to implement backoff
_rate_limit_times: List[float] = []
_rate_limit_lock = threading.Lock()


def get_rotating_session():
    """Return a Session from the pool in round-robin order."""
    with _lock:
        idx = next(_rr)
    return _SESSIONS[idx]


def get_smart_session():
    """Return a session, preferring fresh sessions if rate limited recently."""
    current_time = time.time()
    
    with _rate_limit_lock:
        # If we've been rate limited recently, use a fresh session
        recent_rate_limits = [t for t in _rate_limit_times if current_time - t < 60]
        if len(recent_rate_limits) >= 1:
            return create_fresh_session()
    
    # Otherwise use the rotating session pool
    return get_rotating_session()


def create_fresh_session():
    """Create a completely fresh session to avoid rate limiting."""
    ua = _UAS[len(_SESSIONS) % len(_UAS)]  # Rotate through UAs
    
    if CURL_CFFI_AVAILABLE:
        s = curl_requests.Session()
        s.headers.update({"User-Agent": ua})
    else:
        s = requests.Session()
        s.headers.update({"User-Agent": ua})
        if Retry is not None:
            retry = Retry(
                total=2,
                backoff_factor=0.3,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["GET", "HEAD", "OPTIONS"],
                raise_on_status=False,
            )
            adapter = HTTPAdapter(pool_connections=50, pool_maxsize=50, max_retries=retry)
        else:
            adapter = HTTPAdapter(pool_connections=50, pool_maxsize=50)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
    
    return s


def handle_rate_limit():
    """Handle rate limiting by waiting and creating fresh sessions."""
    current_time = time.time()
    
    with _rate_limit_lock:
        # Clean old rate limit entries (older than 60 seconds)
        _rate_limit_times[:] = [t for t in _rate_limit_times if current_time - t < 60]
        
        # Add current rate limit
        _rate_limit_times.append(current_time)
        
        # If we've hit rate limit multiple times recently, wait longer
        if len(_rate_limit_times) >= 3:
            wait_time = 30  # Wait 30 seconds if heavily rate limited
        elif len(_rate_limit_times) >= 2:
            wait_time = 15  # Wait 15 seconds if moderately rate limited
        else:
            wait_time = 5   # Wait 5 seconds for first rate limit
        
        print(f"⚠️  Rate limit detected, waiting {wait_time}s...")
        time.sleep(wait_time)
    
    # Return a fresh session after waiting
    return create_fresh_session()


def get_simple_session():
    """Get a simple curl_cffi session with Chrome impersonation."""
    if CURL_CFFI_AVAILABLE:
        return curl_requests.Session(impersonate="chrome")
    else:
        # Fallback to regular requests session
        s = requests.Session()
        s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"})
        return s
