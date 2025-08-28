# pipeline/stages/mongodb_storage.py
"""
MongoDB storage for valuation results.

Stores results in the val_trades.valuations collection with the following structure:
{
    "run_id": "unique_run_identifier",
    "run_date": "YYYY-MM-DD",  # Date when valuation was run
    "run_datetime": "ISO8601_string",  # Full datetime when valuation was run
    "generated_at": timestamp,  # Original pipeline timestamp
    "generated_at_iso": "ISO8601_string",  # Original pipeline ISO string
    "tickers": ["list", "of", "tickers"],
    "strategy_names": ["list", "of", "strategies"],
    "by_ticker": {
        "TICKER": {
            "current_price": float,
            "strategy_fair_values": {"strategy_name": float},
            "consensus_fair_value": float,
            "consensus_discount": float,
            "consensus_p25": float,
            "consensus_p75": float
        }
    },
    "fetch_errors": {"ticker": "error_message"},
    "strategy_errors": {"ticker": {"strategy": "error_message"}},
    "created_at": datetime.utcnow(),  # When document was stored in MongoDB
    "created_at_iso": "ISO8601_string"  # When document was stored in MongoDB (ISO format)
}
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from pipeline.context import PipelineContext


class MongoDBStorage:
    """Handles MongoDB operations for valuation results."""
    
    def __init__(self, connection_string: Optional[str] = None, database_name: str = "val_trades", collection_name: str = "valuations"):
        """
        Initialize MongoDB connection.
        
        Args:
            connection_string: MongoDB connection string (defaults to MONGODB_CONNECTION_STRING env var)
            database_name: Database name (default: val_trades)
            collection_name: Collection name (default: valuations)
        """
        self.connection_string = connection_string or os.getenv("MONGODB_CONNECTION_STRING", "mongodb://localhost:27017/")
        self.database_name = database_name
        self.collection_name = collection_name
        self._client = None
        self._db = None
        self._collection = None
    
    def _get_client(self):
        """Get MongoDB client, creating connection if needed."""
        if self._client is None:
            try:
                from pymongo import MongoClient
                self._client = MongoClient(self.connection_string)
                # Test connection
                self._client.admin.command('ping')
            except Exception as e:
                raise RuntimeError(f"Failed to connect to MongoDB: {e}")
        return self._client
    
    def _get_collection(self):
        """Get the valuations collection."""
        if self._collection is None:
            client = self._get_client()
            self._db = client[self.database_name]
            self._collection = self._db[self.collection_name]
        return self._collection
    
    def clear_existing_valuations(self) -> bool:
        """
        Clear all existing documents from the valuations collection.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            collection = self._get_collection()
            result = collection.delete_many({})
            print(f"[mongodb] Cleared {result.deleted_count} existing valuation documents")
            return True
        except Exception as e:
            print(f"[mongodb] Failed to clear existing valuations: {e}")
            return False
    
    def store_valuation_results(self, ctx: PipelineContext) -> bool:
        """
        Store valuation results in MongoDB.
        
        Args:
            ctx: PipelineContext containing the results
            
        Returns:
            True if successful, False otherwise
        """
        try:
            collection = self._get_collection()
            
            # Prepare document with comprehensive date tracking
            now = datetime.utcnow()
            document = {
                "run_id": ctx.run_id,
                "run_date": now.date().isoformat(),  # YYYY-MM-DD format
                "run_datetime": now.isoformat() + "Z",  # Full ISO datetime with Z
                "generated_at": ctx.generated_at,
                "generated_at_iso": ctx.generated_at_iso,
                "tickers": ctx.tickers,
                "strategy_names": ctx.strategy_names,
                "by_ticker": ctx.results_by_ticker,
                "fetch_errors": ctx.fetch_errors,
                "strategy_errors": ctx.strategy_errors,
                "created_at": now,
                "created_at_iso": now.isoformat() + "Z"
            }
            
            # Insert document
            result = collection.insert_one(document)
            print(f"[mongodb] Stored valuation results with ID: {result.inserted_id}")
            return True
            
        except Exception as e:
            print(f"[mongodb] Failed to store valuation results: {e}")
            return False
    
    def close(self):
        """Close MongoDB connection."""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
            self._collection = None


def store_results_in_mongodb(ctx: PipelineContext, clear_existing: bool = True) -> Optional[str]:
    """
    Store valuation results in MongoDB.
    
    Args:
        ctx: PipelineContext containing the results
        clear_existing: Whether to clear existing valuations before storing
        
    Returns:
        Success message or error message
    """
    try:
        storage = MongoDBStorage()
        
        if clear_existing:
            if not storage.clear_existing_valuations():
                return "Failed to clear existing valuations"
        
        if storage.store_valuation_results(ctx):
            return f"Results stored in MongoDB (database: {storage.database_name}, collection: {storage.collection_name})"
        else:
            return "Failed to store results in MongoDB"
            
    except Exception as e:
        return f"MongoDB storage failed: {e}"
    finally:
        if 'storage' in locals():
            storage.close() 