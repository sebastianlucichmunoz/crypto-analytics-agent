from datetime import datetime, timezone
from pymongo import UpdateOne
from src.api_clients.coinstats import CoinStatsClient
from src.api_clients.mobula import MobulaClient
from src.config import settings
from src.db import get_db

def refresh_coinstats():
    db = get_db()
    now = datetime.now(timezone.utc)
    coins = CoinStatsClient().top_coins(settings.top_n)
    db.assets.update_many({}, {"$set": {"active_top_n": False}})
    ops, snapshots = [], []

    for coin in coins:
        coin_id = coin.get("id")
        if not coin_id:
            continue
        ops.append(UpdateOne(
            {"coin_id": coin_id},
            {
                "$set": {
                    "coin_id": coin_id,
                    "name": coin.get("name"),
                    "symbol": coin.get("symbol"),
                    "rank": coin.get("rank"),
                    "icon": coin.get("icon"),
                    "active_top_n": True,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        ))
        snapshots.append({
            "coin_id": coin_id,
            "name": coin.get("name"),
            "symbol": coin.get("symbol"),
            "rank": coin.get("rank"),
            "price": coin.get("price"),
            "market_cap": coin.get("marketCap"),
            "volume_24h": coin.get("volume"),
            "price_change_1h": coin.get("priceChange1h"),
            "price_change_1d": coin.get("priceChange1d"),
            "price_change_1w": coin.get("priceChange1w"),
            "price_change_1m": coin.get("priceChange1m"),
            "source": "coinstats",
            "observed_at": now,
        })
    if ops:
        db.assets.bulk_write(ops)
    if snapshots:
        db.market_snapshots.insert_many(snapshots)
    return len(snapshots)

def resolve_mobula():
    db = get_db()
    client = MobulaClient()
    rows = list(db.assets.find(
        {"active_top_n": True},
        {"_id": 0, "coin_id": 1, "symbol": 1, "name": 1, "mobula_id": 1}
    ).sort("rank", 1))
    resolved, failed = 0, []
    for a in rows:
        if a.get("mobula_id") is not None:
            continue
        try:
            match = client.search_asset(a["symbol"], a.get("name"))
            if not match or match.get("id") is None:
                failed.append(a["coin_id"])
                continue
            details = client.asset_details(match["id"])
            asset = details.get("asset", {}) or {}
            db.assets.update_one(
                {"coin_id": a["coin_id"]},
                {"$set": {
                    "mobula_id": int(match["id"]),
                    "mobula_asset": asset,
                    "mobula_tokens": details.get("tokens", []) or [],
                    "is_stablecoin": bool(asset.get("isStablecoin", False)),
                    "mobula_native_chain_id": asset.get("nativeChainId"),
                    "mobula_resolved_at": datetime.now(timezone.utc),
                }}
            )
            resolved += 1
        except Exception:
            failed.append(a["coin_id"])
    return {"resolved": resolved, "failed": failed}

def refresh_mobula():
    db = get_db()
    client = MobulaClient()
    assets = list(db.assets.find(
        {"active_top_n": True, "mobula_id": {"$ne": None}},
        {"_id": 0, "coin_id": 1, "mobula_id": 1}
    ))
    if not assets:
        return 0
    mapping = {int(x["mobula_id"]): x["coin_id"] for x in assets}
    details = client.asset_details_batch(list(mapping.keys()))
    now = datetime.now(timezone.utc)
    docs = []
    for item in details:
        asset = item.get("asset", {}) or {}
        mid = asset.get("id")
        if mid is None or int(mid) not in mapping:
            continue
        coin_id = mapping[int(mid)]
        db.assets.update_one({"coin_id": coin_id}, {"$set": {
            "mobula_asset": asset,
            "mobula_tokens": item.get("tokens", []) or [],
            "is_stablecoin": bool(asset.get("isStablecoin", False)),
            "mobula_updated_at": now,
        }})
        docs.append({
            "coin_id": coin_id,
            "mobula_id": int(mid),
            "name": asset.get("name"),
            "symbol": asset.get("symbol"),
            "rank": asset.get("rank"),
            "price": asset.get("priceUSD"),
            "market_cap": asset.get("marketCapUSD"),
            "is_stablecoin": bool(asset.get("isStablecoin", False)),
            "source": "mobula",
            "observed_at": now,
        })
    if docs:
        db.mobula_snapshots.insert_many(docs)
    return len(docs)

def refresh_market():
    count = refresh_coinstats()
    resolution = resolve_mobula()
    mobula = refresh_mobula()
    return {"coinstats": count, "mobula": mobula, "resolution": resolution}
