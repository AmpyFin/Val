#!/usr/bin/env python3
"""
Test script for MongoDB integration.
Run this to verify MongoDB connection and storage works.
"""

import os
import sys
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.stages.mongodb_storage import MongoDBStorage


def test_mongodb_connection():
    """Test MongoDB connection and basic operations."""
    print("Testing MongoDB connection...")
    
    try:
        # Test connection
        storage = MongoDBStorage()
        client = storage._get_client()
        print("✓ MongoDB connection successful")
        
        # Test collection access
        collection = storage._get_collection()
        print(f"✓ Collection access successful: {storage.database_name}.{storage.collection_name}")
        
        # Test clear operation
        result = storage.clear_existing_valuations()
        if result:
            print("✓ Clear existing valuations successful")
        else:
            print("✗ Clear existing valuations failed")
        
        # Test insert operation with dummy data
        dummy_document = {
            "run_id": "test_run_123",
            "generated_at": datetime.now().timestamp(),
            "generated_at_iso": datetime.utcnow().isoformat() + "Z",
            "tickers": ["AAPL", "MSFT", "GOOGL"],
            "strategy_names": ["peter_lynch", "fcf_yield"],
            "by_ticker": {
                "AAPL": {
                    "current_price": 150.0,
                    "consensus_fair_value": 160.0,
                    "consensus_discount": 0.067,
                    "consensus_p25": 155.0,
                    "consensus_p75": 165.0,
                    "strategy_fair_values": {
                        "peter_lynch": 158.0,
                        "fcf_yield": 162.0
                    }
                }
            },
            "fetch_errors": {},
            "strategy_errors": {},
            "created_at": datetime.utcnow()
        }
        
        result = collection.insert_one(dummy_document)
        print(f"✓ Test document inserted with ID: {result.inserted_id}")
        
        # Test query
        doc = collection.find_one({"run_id": "test_run_123"})
        if doc:
            print("✓ Test document retrieved successfully")
            print(f"  - Tickers: {doc['tickers']}")
            print(f"  - Strategies: {doc['strategy_names']}")
        else:
            print("✗ Test document retrieval failed")
        
        # Clean up test data
        collection.delete_one({"run_id": "test_run_123"})
        print("✓ Test data cleaned up")
        
        storage.close()
        print("✓ MongoDB connection closed")
        
        return True
        
    except Exception as e:
        print(f"✗ MongoDB test failed: {e}")
        return False


if __name__ == "__main__":
    print("MongoDB Integration Test")
    print("=" * 30)
    
    # Check if MongoDB connection string is set
    mongodb_uri = os.getenv("MONGODB_CONNECTION_STRING", "mongodb://localhost:27017/")
    print(f"MongoDB Connection String: {mongodb_uri}")
    
    success = test_mongodb_connection()
    
    if success:
        print("\n✓ All tests passed! MongoDB integration is working.")
        print("\nTo use MongoDB with the CLI:")
        print("  python scripts/cli.py --mongodb --run-once")
        print("  python scripts/cli.py --mongodb --mongodb-uri 'your_connection_string' --run-once")
        print("  # Or set MONGODB_CONNECTION_STRING environment variable")
    else:
        print("\n✗ Tests failed. Please check your MongoDB connection.")
        print("\nTroubleshooting:")
        print("1. Ensure MongoDB is running")
        print("2. Check your MONGODB_URI environment variable")
        print("3. Verify network connectivity to MongoDB")
    
    sys.exit(0 if success else 1) 