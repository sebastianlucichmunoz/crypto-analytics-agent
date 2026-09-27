# src/agents/tools.py
from src.dashboard import latest_prediction, market_mood, latest_market

def consultar_prediccion_xgboost(coin_id: str) -> str:
    """
    Obtiene los datos del modelo cuantitativo XGBoost para una criptomoneda específica (ejemplo coin_id: 'bitcoin').
    Retorna el precio actual, precio estimado a 24h, porcentaje de cambio esperado y tendencia técnica.
    """
    pred = latest_prediction(coin_id)
    if not pred:
        return f"No se encontró predicción cuantitativa de XGBoost para {coin_id}."
    
    return (
        f"Activo: {coin_id}\n"
        f"- Precio actual: ${float(pred.get('current_price', 0)):,.2f}\n"
        f"- Precio proyectado (24h): ${float(pred.get('predicted_close_24h', 0)):,.2f}\n"
        f"- Cambio esperado: {float(pred.get('predicted_change_pct', 0)):+.2f}%\n"
        f"- Tendencia XGBoost: {pred.get('trend', 'Desconocida')}"
    )

def consultar_sentimiento_mercado(horas: int = 24) -> str:
    """
    Obtiene el resumen del análisis de noticias y la puntuación de sentimiento VADER acumulada de las últimas horas.
    """
    mood, score, count = market_mood(horas)
    return (
        f"Análisis de noticias en las últimas {horas} horas:\n"
        f"- Diagnóstico de Sentimiento: {mood}\n"
        f"- Score numérico VADER: {score:+.3f}\n"
        f"- Cantidad de noticias analizadas: {count}"
    )