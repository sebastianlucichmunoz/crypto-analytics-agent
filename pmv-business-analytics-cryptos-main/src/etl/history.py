from datetime import datetime, timedelta, timezone
from pymongo import UpdateOne
from src.api_clients.mobula import MobulaClient
from src.config import settings
from src.db import get_db

def load_price_history(days=None):
    db = get_db()
    days = days or settings.history_days
    assets = list(db.assets.find(
        {"active_top_n": True, "mobula_id": {"$ne": None}},
        {"_id": 0, "coin_id": 1, "mobula_id": 1}
    ).sort("rank", 1))
    if not assets:
        return {"assets": 0, "rows": 0}

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    mapping = {int(a["mobula_id"]): a["coin_id"] for a in assets}
    payload = [{
        "id": int(a["mobula_id"]),
        "period": "1d",
        "from": int(start.timestamp() * 1000),
        "to": int(now.timestamp() * 1000),
    } for a in assets]

    responses = MobulaClient().price_history_batch(payload)
    ops, covered = [], set()
    for item in responses:
        if item.get("error") or item.get("id") is None:
            continue
        coin_id = mapping.get(int(item["id"]))
        if not coin_id:
            continue
        covered.add(coin_id)
        for point in item.get("priceHistory", []) or []:
            if not isinstance(point, (list, tuple)) or len(point) < 2 or point[1] is None:
                continue
            dt = datetime.fromtimestamp(float(point[0]) / 1000, tz=timezone.utc)
            date = datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
            doc = {
                "coin_id": coin_id,
                "mobula_id": int(item["id"]),
                "date": date,
                "price": float(point[1]),
                "source": "mobula_asset_price_history",
                "updated_at": now,
            }
            ops.append(UpdateOne(
                {"coin_id": coin_id, "date": date, "source": doc["source"]},
                {"$set": doc}, upsert=True
            ))
    if ops:
        db.price_history.bulk_write(ops, ordered=False)
    return {"assets": len(covered), "rows": len(ops)}

def best_token(asset):
    tokens = asset.get("mobula_tokens", []) or []
    candidates = [t for t in tokens if t.get("address") and (t.get("chainId") or t.get("blockchain"))]
    if not candidates:
        return None
    def val(t):
        try:
            return float(t.get("liquidityUSD") or 0), float(t.get("volume24hUSD") or 0)
        except Exception:
            return (0.0, 0.0)
    return sorted(candidates, key=val, reverse=True)[0]

def load_ohlcv(days=None):
    # Best effort: el endpoint OHLCV de Mobula es contract-based.
    db = get_db()
    days = days or settings.history_days
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    assets = list(db.assets.find(
        {"active_top_n": True},
        {"_id": 0, "coin_id": 1, "mobula_tokens": 1}
    ).sort("rank", 1))

    payload, mapping, skipped = [], {}, []
    for a in assets:
        token = best_token(a)
        if not token:
            skipped.append(a["coin_id"])
            continue
        address = token["address"]
        chain = token.get("chainId") or token.get("blockchain")
        mapping[str(address).lower()] = {"coin_id": a["coin_id"], "token": token}
        payload.append({
            "address": address,
            "chainId": chain,
            "period": "1d",
            "from": int(start.timestamp() * 1000),
            "to": int(now.timestamp() * 1000),
            "amount": min(days + 10, 2000),
            "usd": True,
            "fill": True,
            "enableAssetHistory": True,
        })

    if not payload:
        return {"assets": 0, "rows": 0, "skipped": skipped}

    responses = MobulaClient().token_ohlcv_batch(payload)
    ops, covered = [], set()
    for item in responses:
        if item.get("error"):
            continue
        meta = mapping.get(str(item.get("address", "")).lower())
        if not meta:
            continue
        coin_id = meta["coin_id"]
        covered.add(coin_id)
        for c in item.get("ohlcv", []) or []:
            if c.get("t") is None:
                continue
            ts = datetime.fromtimestamp(float(c["t"]) / 1000, tz=timezone.utc)
            doc = {
                "coin_id": coin_id,
                "timestamp": ts,
                "period": "1d",
                "open": c.get("o"), "high": c.get("h"), "low": c.get("l"),
                "close": c.get("c"), "volume": c.get("v"),
                "source": "mobula_token_ohlcv",
                "source_token_address": meta["token"].get("address"),
                "source_chain_id": meta["token"].get("chainId") or meta["token"].get("blockchain"),
                "updated_at": now,
            }
            ops.append(UpdateOne(
                {"coin_id": coin_id, "timestamp": ts, "period": "1d", "source": doc["source"]},
                {"$set": doc}, upsert=True
            ))
    if ops:
        db.ohlcv.bulk_write(ops, ordered=False)
    return {"assets": len(covered), "rows": len(ops), "skipped": skipped}
