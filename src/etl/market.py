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
    client = MobulaClient() # Nota: Mantiene el nombre de la clase por compatibilidad
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
            
            asset_id = str(match["id"]) # ID en texto (ej. "bitcoin")
            details = client.asset_details(asset_id)
            market_data = details.get("market_data", {}) or {}
            
            db.assets.update_one(
                {"coin_id": a["coin_id"]},
                {"$set": {
                    "mobula_id": asset_id, # Guardamos como string
                    "mobula_asset": details,
                    "mobula_tokens": [],
                    "is_stablecoin": False, # O lógica para stablecoins si se requiere
                    "mobula_native_chain_id": None,
                    "mobula_resolved_at": datetime.now(timezone.utc),
                }}
            )
            resolved += 1
        except Exception as e:
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
    
    mapping = {str(x["mobula_id"]): x["coin_id"] for x in assets}
    details_list = client.asset_details_batch(list(mapping.keys()))
    now = datetime.now(timezone.utc)
    docs = []
    
    for item in details_list:
        mid = item.get("id")
        if mid is None or str(mid) not in mapping:
            continue
        coin_id = mapping[str(mid)]
        market_data = item.get("market_data", {}) or {}
        price = market_data.get("current_price", {}).get("usd", 0)
        market_cap = market_data.get("market_cap", {}).get("usd", 0)
        
        db.assets.update_one({"coin_id": coin_id}, {"$set": {
            "mobula_asset": item,
            "mobula_tokens": [],
            "mobula_updated_at": now,
        }})
        docs.append({
            "coin_id": coin_id,
            "mobula_id": str(mid),
            "name": item.get("name"),
            "symbol": item.get("symbol"),
            "rank": item.get("market_cap_rank"),
            "price": price,
            "market_cap": market_cap,
            "is_stablecoin": False,
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
