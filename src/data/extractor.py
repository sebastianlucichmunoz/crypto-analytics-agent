import json
import os
from datetime import datetime, timedelta, timezone
from src.db import get_db

def extraer_datos_consolidados():
    """
    Extrae las últimas predicciones y el sentimiento de noticias de MongoDB Atlas
    en solo 2 consultas optimizadas.
    """
    db = get_db()
    
    pipeline_preds = [
        {"$sort": {"predicted_at": -1}},
        {
            "$group": {
                "_id": "$coin_id",
                "symbol": {"$first": "$symbol"},
                "current_price": {"$first": "$current_price"},
                "predicted_close_24h": {"$first": "$predicted_close_24h"},
                "predicted_change_pct": {"$first": "$predicted_change_pct"},
                "trend": {"$first": "$trend"},
                "predicted_at": {"$first": "$predicted_at"}
            }
        }
    ]
    preds_raw = list(db.predictions.aggregate(pipeline_preds))
    
    mercado_consolidado = {}
    for p in preds_raw:
        coin_id = p["_id"]
        mercado_consolidado[coin_id] = {
            "coin_id": coin_id,
            "symbol": p.get("symbol", ""),
            "current_price": float(p.get("current_price", 0)),
            "predicted_close_24h": float(p.get("predicted_close_24h", 0)),
            "predicted_change_pct": float(p.get("predicted_change_pct", 0)),
            "trend": p.get("trend", "ESTABLE"),
            "predicted_at": str(p.get("predicted_at", "")),
            # Valores por defecto para sentimiento
            "sentiment_compound": 0.0,
            "sentiment_label": "NEUTRAL",
            "news_count": 0
        }

    hace_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    pipeline_news = [
        {"$match": {"published_at": {"$gte": hace_24h}}},
        {
            "$group": {
                "_id": "$coin_id",
                "avg_compound": {"$avg": "$sentiment_compound"},
                "news_count": {"$sum": 1}
            }
        }
    ]
    news_raw = list(db.news.aggregate(pipeline_news))
    
    for n in news_raw:
        coin_id = n["_id"]
        if coin_id in mercado_consolidado:
            compound = float(n.get("avg_compound", 0.0))
            mercado_consolidado[coin_id]["sentiment_compound"] = round(compound, 4)
            mercado_consolidado[coin_id]["news_count"] = n.get("news_count", 0)
            
            if compound >= 0.05:
                label = "POSITIVO"
            elif compound <= -0.05:
                label = "NEGATIVO"
            else:
                label = "NEUTRAL"
            mercado_consolidado[coin_id]["sentiment_label"] = label

    datos_finales = list(mercado_consolidado.values())

    os.makedirs("data", exist_ok=True)
    with open("data/latest_market_data.json", "w", encoding="utf-8") as f:
        json.dump(datos_finales, f, ensure_ascii=False, indent=2)

    return datos_finales

if __name__ == "__main__":
    datos = extraer_datos_consolidados()
    print(f"✅ Extracción completada. {len(datos)} monedas extraídas en lote.")