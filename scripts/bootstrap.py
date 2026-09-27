from pathlib import Path
import sys

# Permite ejecutar este archivo directamente con: python scripts/<archivo>.py
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from datetime import datetime, timezone
from src.db import ensure_indexes, log_run
from src.etl.market import refresh_market
from src.etl.history import load_price_history, load_ohlcv
from src.etl.news import refresh_news
from src.ml.model import train_all, predict_all

if __name__ == "__main__":
    started = datetime.now(timezone.utc)
    details = {}
    try:
        ensure_indexes()
        print("1/6 Mercado")
        details["market"] = refresh_market()
        print(details["market"])

        print("2/6 Histórico")
        details["history"] = load_price_history()
        print(details["history"])

        print("3/6 OHLCV")
        try:
            details["ohlcv"] = load_ohlcv()
        except Exception as exc:
            details["ohlcv"] = {"warning":str(exc)}
        print(details["ohlcv"])

        print("4/6 Noticias")
        details["news"] = refresh_news()
        print(details["news"])

        print("5/6 XGBoost")
        trained = train_all()
        details["models_trained"] = sum(x.get("status")=="trained" for x in trained)
        print("Modelos:",details["models_trained"])

        print("6/6 Predicciones")
        preds = predict_all()
        details["predictions"] = sum(x.get("status")=="predicted" for x in preds)
        print("Predicciones:",details["predictions"])

        log_run("bootstrap","success",started,details)
        print("✅ Bootstrap finalizado.")
    except Exception as exc:
        log_run("bootstrap","error",started,details,str(exc))
        raise
