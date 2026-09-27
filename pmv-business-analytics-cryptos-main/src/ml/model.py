from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd
from bson.binary import Binary
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, mean_squared_error, r2_score
from xgboost import XGBRegressor, Booster, DMatrix
from src.config import settings
from src.db import get_db
from src.ml.features import FEATURES, build

STABLE = {"USDT","USDC","DAI","FDUSD","USDE","USDS","PYUSD","TUSD","FRAX"}

def is_stable(asset):
    return bool(asset.get("is_stablecoin")) or str(asset.get("symbol","")).upper() in STABLE

def sentiment_df(db, coin_id):
    pipeline = [
        {"$match": {"mentioned_coin_ids": coin_id}},
        {"$project": {
            "day": {"$dateTrunc": {"date": "$published_at", "unit": "day", "timezone": "UTC"}},
            "sentiment_compound": 1
        }},
        {"$group": {"_id": "$day", "sentiment_compound": {"$avg": "$sentiment_compound"}}},
        {"$sort": {"_id": 1}}
    ]
    rows = list(db.news.aggregate(pipeline))
    return pd.DataFrame([{"date": x["_id"], "sentiment_compound": x["sentiment_compound"]} for x in rows])

def price_df(db, coin_id):
    rows = list(db.ohlcv.find(
        {"coin_id": coin_id, "period": "1d"},
        {"_id": 0, "timestamp": 1, "close": 1, "volume": 1}
    ).sort("timestamp", 1))
    if len(rows) >= settings.model_min_rows:
        df = pd.DataFrame(rows).rename(columns={"timestamp": "date"})
        return df, "mobula_token_ohlcv"

    rows = list(db.price_history.find(
        {"coin_id": coin_id, "source": "mobula_asset_price_history"},
        {"_id": 0, "date": 1, "price": 1}
    ).sort("date", 1))
    if not rows:
        return pd.DataFrame(columns=["date","close","volume"]), "none"
    df = pd.DataFrame(rows).rename(columns={"price":"close"})
    df["volume"] = 0.0
    return df, "mobula_asset_price_history"

def train_one(coin_id):
    db = get_db()
    asset = db.assets.find_one({"coin_id": coin_id}) or {}
    if not asset:
        return {"coin_id": coin_id, "status":"asset_not_found"}
    if is_stable(asset):
        return {"coin_id": coin_id, "status":"skipped_stablecoin"}

    prices, source = price_df(db, coin_id)
    feat = build(prices, sentiment_df(db, coin_id), target=True)
    if len(feat) < settings.model_min_rows:
        return {"coin_id": coin_id, "status":"insufficient_history", "rows":len(feat)}

    split = int(len(feat)*0.8)
    train, test = feat.iloc[:split], feat.iloc[split:]
    if len(test) < 10:
        return {"coin_id": coin_id, "status":"insufficient_test"}

    model = XGBRegressor(
        objective="reg:squarederror", n_estimators=500, max_depth=4,
        learning_rate=0.03, subsample=0.85, colsample_bytree=0.85,
        reg_lambda=1.0, random_state=42, n_jobs=2
    )
    model.fit(train[FEATURES], train["target_close_next"])
    pred = model.predict(test[FEATURES])
    y = test["target_close_next"]
    naive = test["close"].to_numpy()

    mae = float(mean_absolute_error(y,pred))
    test_dates = pd.to_datetime(test["date"], utc=True)
    backtest = [
        {
            "date": dt.to_pydatetime(),
            "actual": float(actual),
            "predicted": float(predicted),
            "baseline": float(base),
        }
        for dt, actual, predicted, base in zip(test_dates, y, pred, naive)
    ]

    feature_importance = {
        feature: float(value)
        for feature, value in zip(FEATURES, model.feature_importances_)
    }

    metrics = {
        "coin_id": coin_id,
        "symbol": asset.get("symbol"),
        "trained_at": datetime.now(timezone.utc),
        "history_source": source,
        "training_rows": len(train),
        "test_rows": len(test),
        "mae": mae,
        "rmse": float(np.sqrt(mean_squared_error(y,pred))),
        "mape_pct": float(mean_absolute_percentage_error(y,pred)*100),
        "r2": float(r2_score(y,pred)),
        "naive_mae": float(mean_absolute_error(y,naive)),
        "feature_importance": feature_importance,
        "backtest": backtest,
    }
    metrics["beats_naive"] = metrics["mae"] < metrics["naive_mae"]

    raw = bytes(model.get_booster().save_raw(raw_format="json"))
    db.models.update_one({"coin_id":coin_id},{"$set":{
        "coin_id":coin_id, "symbol":asset.get("symbol"), "history_source":source,
        "feature_columns":FEATURES, "model_type":"XGBRegressor",
        "model_raw_json":Binary(raw), "trained_at":metrics["trained_at"],
    }},upsert=True)
    db.model_metrics.insert_one(metrics)
    return {"status":"trained", **metrics}

def train_all():
    db = get_db()
    ids = [x["coin_id"] for x in db.assets.find({"active_top_n":True},{"coin_id":1}).sort("rank",1)]
    return [train_one(x) for x in ids]

def predict_one(coin_id):
    db = get_db()
    model_doc = db.models.find_one({"coin_id":coin_id})
    if not model_doc:
        return {"coin_id":coin_id,"status":"no_model"}
    asset = db.assets.find_one({"coin_id":coin_id}) or {}
    prices, source = price_df(db, coin_id)
    snap = db.market_snapshots.find_one({"coin_id":coin_id}, sort=[("observed_at",-1)])
    if snap and snap.get("price") is not None:
        today = pd.Timestamp.now(tz="UTC").floor("D")
        prices["date"] = pd.to_datetime(prices["date"], utc=True)
        prices = prices[prices["date"].dt.floor("D") < today]
        prices = pd.concat([prices, pd.DataFrame([{
            "date":today, "close":float(snap["price"]),
            "volume":float(snap.get("volume_24h") or 0)
        }])], ignore_index=True)

    feat = build(prices, sentiment_df(db, coin_id), target=False)
    if feat.empty:
        return {"coin_id":coin_id,"status":"insufficient_features"}

    booster = Booster()
    booster.load_model(bytearray(model_doc["model_raw_json"]))
    last = feat.iloc[-1]
    X = pd.DataFrame([last[FEATURES].to_dict()])[FEATURES]
    dmatrix = DMatrix(X, feature_names=FEATURES)
    predicted = float(booster.predict(dmatrix)[0])
    current = float(last["close"])
    pct = (predicted/current - 1)*100 if current else 0
    t = settings.prediction_neutral_threshold_pct
    trend = "ALCISTA" if pct > t else ("BAJISTA" if pct < -t else "ESTABLE")
    now = datetime.now(timezone.utc)
    doc = {
        "coin_id":coin_id, "symbol":asset.get("symbol"),
        "predicted_at":now, "target_time":now+timedelta(hours=24),
        "current_price":current, "predicted_close_24h":predicted,
        "predicted_change_pct":float(pct), "trend":trend,
        "history_source":source, "model_trained_at":model_doc.get("trained_at"),
        "sentiment_compound":float(last.get("sentiment_compound",0)),
    }
    db.predictions.insert_one(doc)
    return {"status":"predicted", **doc}

def predict_all():
    db = get_db()
    return [predict_one(x["coin_id"]) for x in db.models.find({},{"coin_id":1})]
