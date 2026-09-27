from pathlib import Path
import sys

# Permite ejecutar este archivo directamente con: python scripts/<archivo>.py
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import argparse
from datetime import datetime, timezone
from src.db import ensure_indexes, log_run
from src.etl.market import refresh_market
from src.etl.news import refresh_news
from src.etl.history import load_price_history, load_ohlcv
from src.ml.model import train_all, predict_all

def main(daily=False):
    started = datetime.now(timezone.utc)
    details = {"daily":daily}
    try:
        ensure_indexes()
        details["market"] = refresh_market()
        details["news"] = refresh_news()
        if daily:
            details["history"] = load_price_history(days=45)
            try:
                details["ohlcv"] = load_ohlcv(days=45)
            except Exception as exc:
                details["ohlcv"] = {"warning":str(exc)}
            trained = train_all()
            details["models_trained"] = sum(x.get("status")=="trained" for x in trained)
        preds = predict_all()
        details["predictions"] = sum(x.get("status")=="predicted" for x in preds)
        log_run("refresh_daily" if daily else "refresh","success",started,details)
        print("✅",details)
    except Exception as exc:
        log_run("refresh_daily" if daily else "refresh","error",started,details,str(exc))
        raise

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--daily",action="store_true")
    args = p.parse_args()
    main(args.daily)
