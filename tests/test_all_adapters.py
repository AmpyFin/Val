#!/usr/bin/env python3
"""
Test script to fetch and print all adapter values for static tickers.
This script tests all metric adapters (excluding ticker adapters) for each ticker in the static list.
"""

import sys
import time
from typing import Dict, List, Any

# Add the project root to the path
sys.path.insert(0, '.')

from registries.adapter_registry import (
    list_available_metrics,
    get_active_metric_adapter,
    get_active_tickers_adapter
)
from adapters.adapter import DataNotAvailable


def fetch_all_metrics_for_ticker(ticker: str) -> Dict[str, Any]:
    """
    Fetch all available metrics for a single ticker.
    
    Args:
        ticker: The stock ticker symbol
        
    Returns:
        Dictionary with metric names as keys and values/errors as values
    """
    results = {}
    metrics = list_available_metrics()
    
    print(f"\n{'='*60}")
    print(f"Fetching metrics for: {ticker}")
    print(f"{'='*60}")
    
    for metric in metrics:
        try:
            adapter = get_active_metric_adapter(metric)
            value = adapter.fetch(ticker)
            results[metric] = value
            print(f"✓ {metric:25} = {value}")
        except DataNotAvailable as e:
            results[metric] = f"DataNotAvailable: {str(e)}"
            print(f"✗ {metric:25} = DataNotAvailable: {str(e)}")
        except Exception as e:
            results[metric] = f"Error: {str(e)}"
            print(f"✗ {metric:25} = Error: {str(e)}")
        
        # Small delay to avoid rate limiting
        time.sleep(0.1)
    
    return results


def test_all_tickers():
    """
    Test all adapters for all tickers in the static list.
    """
    print("Starting adapter test for all static tickers...")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Get the tickers from the static list
    try:
        tickers_adapter = get_active_tickers_adapter()
        tickers = tickers_adapter.fetch()
        print(f"\nFound {len(tickers)} tickers in static list:")
        print(f"Tickers: {', '.join(tickers)}")
    except Exception as e:
        print(f"Error getting tickers: {e}")
        return
    
    # Test each ticker
    all_results = {}
    for i, ticker in enumerate(tickers, 1):
        print(f"\n[{i}/{len(tickers)}] Testing {ticker}...")
        try:
            results = fetch_all_metrics_for_ticker(ticker)
            all_results[ticker] = results
        except Exception as e:
            print(f"Error testing {ticker}: {e}")
            all_results[ticker] = {"error": str(e)}
        
        # Delay between tickers to avoid rate limiting
        if i < len(tickers):
            print("Waiting 2 seconds before next ticker...")
            time.sleep(2)
    
    # Print summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    
    metrics = list_available_metrics()
    print(f"Total tickers tested: {len(all_results)}")
    print(f"Total metrics available: {len(metrics)}")
    print(f"Metrics: {', '.join(metrics)}")
    
    # Count successes and failures per metric
    print(f"\n{'='*80}")
    print("METRIC SUCCESS RATES")
    print(f"{'='*80}")
    
    for metric in metrics:
        success_count = 0
        total_count = 0
        
        for ticker_results in all_results.values():
            if isinstance(ticker_results, dict) and metric in ticker_results:
                total_count += 1
                value = ticker_results[metric]
                if isinstance(value, (int, float)) and not isinstance(value, str):
                    success_count += 1
        
        if total_count > 0:
            success_rate = (success_count / total_count) * 100
            print(f"{metric:25} = {success_count}/{total_count} ({success_rate:.1f}%)")
        else:
            print(f"{metric:25} = 0/0 (0.0%)")
    
    print(f"\nTest completed at: {time.strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    test_all_tickers() 