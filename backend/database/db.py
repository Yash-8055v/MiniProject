"""
MongoDB Atlas connection and helper functions for misinformation_claims collection.
"""

import os
import hashlib
from datetime import datetime, timezone
from typing import Optional

from pymongo import MongoClient, DESCENDING
from pymongo.collection import Collection
from dotenv import load_dotenv

load_dotenv()

_client: Optional[MongoClient] = None
_collection: Optional[Collection] = None
_heatmap_collection: Optional[Collection] = None
_analysis_cache_collection: Optional[Collection] = None
_pipeline_state_collection: Optional[Collection] = None


def get_collection() -> Collection:
    """Return the misinformation_claims collection, connecting if needed."""
    global _client, _collection

    if _collection is not None:
        return _collection

    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise EnvironmentError("MONGO_URI is not set in .env")

    _client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    db = _client["truthcrew"]
    _collection = db["misinformation_claims"]

    # Unique index on claim_hash to prevent duplicates
    _collection.create_index("claim_hash", unique=True)

    # TTL index: auto-delete documents older than 7 days
    _collection.create_index("created_at", expireAfterSeconds=7 * 24 * 3600)

    return _collection


def get_heatmap_collection() -> Collection:
    """Return the heatmap_cache collection, connecting if needed."""
    global _client, _heatmap_collection

    if _heatmap_collection is not None:
        return _heatmap_collection

    if _client is None:
        get_collection()  # ensure connection

    db = _client["truthcrew"]
    _heatmap_collection = db["heatmap_cache"]

    # TTL index: auto-delete cached heatmaps after 12 hours
    _heatmap_collection.create_index("created_at", expireAfterSeconds=12 * 3600)

    return _heatmap_collection


def make_claim_hash(claim_text: str) -> str:
    """Generate an MD5 hash from normalized claim text for deduplication."""
    normalized = claim_text.strip().lower()
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()


def upsert_claim(doc: dict) -> None:
    """
    Insert a new claim or increment trending_score if already exists.
    Duplicate detection is based on claim_hash (MD5 of normalized claim text).
    """
    col = get_collection()
    claim_hash = make_claim_hash(doc["claim"])

    col.update_one(
        {"claim_hash": claim_hash},
        {
            "$setOnInsert": {
                "claim_hash": claim_hash,
                "claim": doc["claim"],
                "explanation": doc.get("explanation", ""),
                "category": doc.get("category", "General"),
                "misleading_score": doc.get("misleading_score", 70),
                "source_name": doc.get("source_name", "Unknown"),
                "source_url": doc.get("source_url", ""),
                "region": doc.get("region", "global"),
                "published_at": doc.get("published_at", datetime.now(timezone.utc)),
                "created_at": datetime.now(timezone.utc),
            },
            "$inc": {"trending_score": 1},
        },
        upsert=True,
    )


def get_trending_claims(region: Optional[str] = None, limit: int = 10) -> list[dict]:
    """
    Return top `limit` trending claims sorted by misleading_score descending.
    Optionally filter by region.
    """
    col = get_collection()
    query = {}
    if region and region.lower() != "all":
        query["region"] = region.lower()

    cursor = col.find(query).sort("misleading_score", DESCENDING).limit(limit)

    results = []
    for doc in cursor:
        doc["_id"] = str(doc["_id"])  # make JSON serialisable
        # Format dates as ISO strings
        for date_field in ("created_at", "published_at"):
            if date_field in doc and isinstance(doc[date_field], datetime):
                doc[date_field] = doc[date_field].isoformat()
        results.append(doc)

    return results


def get_analysis_cache_collection() -> Collection:
    """Return the analysis_cache collection, connecting if needed."""
    global _client, _analysis_cache_collection

    if _analysis_cache_collection is not None:
        return _analysis_cache_collection

    if _client is None:
        get_collection()  # ensure connection

    db = _client["truthcrew"]
    _analysis_cache_collection = db["analysis_cache"]

    # TTL index: auto-delete cached analyses after 24 hours
    _analysis_cache_collection.create_index("created_at", expireAfterSeconds=24 * 3600)

    return _analysis_cache_collection


def get_cached_analysis(claim_hash: str) -> Optional[dict]:
    """Retrieve cached claim analysis if it exists."""
    try:
        col = get_analysis_cache_collection()
        doc = col.find_one({"claim_hash": claim_hash})
        if doc:
            return doc.get("data")
    except Exception:
        pass
    return None


def set_cached_analysis(claim_hash: str, data: dict) -> None:
    """Store claim analysis with current timestamp for TTL expiration."""
    try:
        col = get_analysis_cache_collection()
        col.update_one(
            {"claim_hash": claim_hash},
            {
                "$set": {
                    "claim_hash": claim_hash,
                    "data": data,
                    "created_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )
    except Exception:
        pass  # Cache write failure is non-fatal


def get_pipeline_state_collection() -> Collection:
    """Return the pipeline_state collection (tracks last refresh time)."""
    global _client, _pipeline_state_collection

    if _pipeline_state_collection is not None:
        return _pipeline_state_collection

    if _client is None:
        get_collection()  # ensure connection

    db = _client["truthcrew"]
    _pipeline_state_collection = db["pipeline_state"]
    return _pipeline_state_collection


def get_last_refresh_time() -> Optional[datetime]:
    """Return the UTC datetime of the last successful trending refresh, or None."""
    try:
        col = get_pipeline_state_collection()
        doc = col.find_one({"_id": "trending_refresh"})
        if doc and "last_refreshed_at" in doc:
            return doc["last_refreshed_at"]
    except Exception:
        pass
    return None


def set_last_refresh_time() -> None:
    """Persist the current UTC time as the last successful trending refresh."""
    try:
        col = get_pipeline_state_collection()
        col.update_one(
            {"_id": "trending_refresh"},
            {"$set": {"last_refreshed_at": datetime.now(timezone.utc)}},
            upsert=True,
        )
    except Exception:
        pass  # Non-fatal


def close_connection() -> None:
    """Close the MongoDB client connection gracefully."""
    global _client, _collection
    if _client:
        _client.close()
        _client = None
        _collection = None
        _heatmap_collection = None


def get_cached_heatmap(query_hash: str) -> Optional[dict]:
    """Retrieve cached heatmap data if it exists."""
    col = get_heatmap_collection()
    doc = col.find_one({"query_hash": query_hash})
    if doc:
        return doc.get("data")
    return None


def set_cached_heatmap(query_hash: str, data: dict) -> None:
    """Store heatmap data with current timestamp for TTL expiration."""
    col = get_heatmap_collection()
    col.update_one(
        {"query_hash": query_hash},
        {
            "$set": {
                "query_hash": query_hash,
                "data": data,
                "created_at": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )
