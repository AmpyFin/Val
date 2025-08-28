#!/usr/bin/env python3
"""
Script to check MongoDB date fields in stored valuation results.
"""

import os
import sys
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.stages.mongodb_storage import MongoDBStorage


def check_mongodb_dates():
    """Check the date fields in MongoDB documents."""
    try:
        storage = MongoDBStorage()
        collection = storage._get_collection()
        
        # Get the most recent document
        latest_doc = collection.find_one(sort=[("created_at", -1)])
        
        if not latest_doc:
            print("No documents found in MongoDB")
            return
        
        print("=== MongoDB Date Fields Check ===")
        print(f"Document ID: {latest_doc['_id']}")
        print(f"Run ID: {latest_doc.get('run_id', 'N/A')}")
        print()
        
        # Check all date fields
        date_fields = [
            'run_date',
            'run_datetime', 
            'generated_at',
            'generated_at_iso',
            'created_at',
            'created_at_iso'
        ]
        
        for field in date_fields:
            value = latest_doc.get(field, 'NOT_FOUND')
            print(f"{field}: {value}")
        
        print()
        print("=== Sample Ticker Data ===")
        by_ticker = latest_doc.get('by_ticker', {})
        if by_ticker:
            ticker = list(by_ticker.keys())[0]
            ticker_data = by_ticker[ticker]
            print(f"Sample ticker ({ticker}):")
            print(f"  Current price: {ticker_data.get('current_price', 'N/A')}")
            print(f"  Consensus FV: {ticker_data.get('consensus_fair_value', 'N/A')}")
            print(f"  Discount %: {ticker_data.get('consensus_discount', 'N/A')}")
        
        storage.close()
        
    except Exception as e:
        print(f"Error checking MongoDB dates: {e}")


if __name__ == "__main__":
    check_mongodb_dates() 