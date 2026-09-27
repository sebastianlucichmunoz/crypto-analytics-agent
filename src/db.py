from __future__ import annotations
from datetime import datetime, timezone
from pymongo import ASCENDING, DESCENDING, MongoClient
from src.config import settings, require

_client = None

def get_client():
    global _client
    require("mongodb_uri")
    if _client is None:
        _client = MongoClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=15000,
            connectTimeoutMS=15000,
        )
    return _client

def get_db():
    return get_client()[settings.mongodb_db_name]

def ping():
    get_client().admin.command("ping")
    return True

def ensure_indexes():
    db = get_db()
    db.assets.create_index("coin_id", unique=True)
    db.assets.create_index([("rank", ASCENDING)])
    db.market_snapshots.create_index([("coin_id", ASCENDING), ("observed_at", DESCENDING)])
    db.mobula_snapshots.create_index([("coin_id", ASCENDING), ("observed_at", DESCENDING)])
    db.price_history.create_index(
        [("coin_id", ASCENDING), ("date", ASCENDING), ("source", ASCENDING)], unique=True
    )
    db.ohlcv.create_index(
        [("coin_id", ASCENDING), ("timestamp", ASCENDING), ("period", ASCENDING), ("source", ASCENDING)],
        unique=True,
    )
    db.news.create_index("news_id", unique=True)
    db.news.create_index([("published_at", DESCENDING)])
    db.models.create_index("coin_id", unique=True)
    db.model_metrics.create_index([("coin_id", ASCENDING), ("trained_at", DESCENDING)])
    db.predictions.create_index([("coin_id", ASCENDING), ("predicted_at", DESCENDING)])
    db.pipeline_runs.create_index([("started_at", DESCENDING)])

def log_run(name: str, status: str, started_at, details=None, error=None):
    get_db().pipeline_runs.insert_one({
        "name": name,
        "status": status,
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc),
        "details": details or {},
        "error": error,
    })
