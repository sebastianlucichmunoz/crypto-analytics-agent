from datetime import datetime, timedelta, timezone
import pandas as pd
from src.db import get_db
from src.nlp.sentiment import mood

def latest_market():
    db = get_db()
    pipe = [
        {"$sort":{"observed_at":-1}},
        {"$group":{"_id":"$coin_id","doc":{"$first":"$$ROOT"}}},
        {"$replaceRoot":{"newRoot":"$doc"}},
        {"$sort":{"rank":1}},
    ]
    rows = list(db.market_snapshots.aggregate(pipe))
    for x in rows:
        x.pop("_id",None)
    return pd.DataFrame(rows)

def market_snapshot_history(hours=72):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = list(get_db().market_snapshots.find(
        {"observed_at":{"$gte":since}},
        {"_id":0,"coin_id":1,"symbol":1,"name":1,"rank":1,"price":1,
         "market_cap":1,"volume_24h":1,"price_change_1d":1,"observed_at":1}
    ).sort("observed_at",1))
    return pd.DataFrame(rows)

def history(coin_id):
    rows = list(get_db().price_history.find(
        {"coin_id":coin_id,"source":"mobula_asset_price_history"},
        {"_id":0,"date":1,"price":1}
    ).sort("date",1))
    return pd.DataFrame(rows)

def ohlcv(coin_id):
    rows = list(get_db().ohlcv.find(
        {"coin_id":coin_id,"period":"1d"},
        {"_id":0,"timestamp":1,"open":1,"high":1,"low":1,"close":1,"volume":1}
    ).sort("timestamp",1))
    return pd.DataFrame(rows)

def news(limit=250):
    rows = list(get_db().news.find({},{
        "_id":0,"source":1,"title":1,"url":1,"published_at":1,
        "sentiment_compound":1,"sentiment_label":1,"mentioned_coin_ids":1
    }).sort("published_at",-1).limit(limit))
    return pd.DataFrame(rows)

def news_for_coin(coin_id, limit=250):
    rows = list(get_db().news.find(
        {"mentioned_coin_ids":coin_id},
        {"_id":0,"source":1,"title":1,"url":1,"published_at":1,
         "sentiment_compound":1,"sentiment_label":1,"mentioned_coin_ids":1}
    ).sort("published_at",-1).limit(limit))
    return pd.DataFrame(rows)

def latest_prediction(coin_id):
    return get_db().predictions.find_one({"coin_id":coin_id},sort=[("predicted_at",-1)])

def latest_metrics(coin_id):
    return get_db().model_metrics.find_one({"coin_id":coin_id},sort=[("trained_at",-1)])

def market_mood(hours=24):
    since = datetime.now(timezone.utc)-timedelta(hours=hours)
    rows = list(get_db().news.aggregate([
        {"$match":{"published_at":{"$gte":since}}},
        {"$group":{"_id":None,"avg":{"$avg":"$sentiment_compound"},"count":{"$sum":1}}}
    ]))
    if not rows:
        return "SIN DATOS",None,0
    return mood(rows[0]["avg"]),rows[0]["avg"],rows[0]["count"]
