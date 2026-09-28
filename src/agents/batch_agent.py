import json
import os
import time
from datetime import datetime, timezone
from dotenv import load_dotenv
from google import genai
from google.genai import types

from src.data.extractor import extraer_datos_consolidados

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Lista de modelos a probar en orden si el servidor principal está saturado (503)
MODELOS_A_PROBAR = ["gemini-3.5-flash", "gemini-3.5-flash-lite"]


def analizar_mercado_en_lote(lista_monedas: list):
    """Envía la lista completa de activos en una sola petición.

    Si un modelo responde 503 (saturado), intenta automáticamente con el
    modelo de respaldo.
    """
    prompt = f"""
    Eres un asesor financiero amigable y experto en criptomonedas que explica las cosas de forma clara, directa y fácil de entender para cualquier persona (evita tecnicismos muy complejos o lenguaje de Wall Street). 
    A continuación se te proporciona la información de mercado, predicciones y noticias recientes para {len(lista_monedas)} activos:

    {json.dumps(lista_monedas, ensure_ascii=False, indent=2)}

    Instrucciones clave para tu análisis:
    1. Analiza CADA UNA de las monedas de la lista anterior utilizando de forma estricta los campos "current_price" y "predicted_close_24h" provistos en los datos.
    2. REGLA OBLIGATORIA SOBRE PRECIOS Y MÉTRICAS: En el "resumen_ejecutivo", DEBES mencionar obligatoriamente:
       - El **precio actual de cierre** de la moneda (usando la clave "current_price").
       - El **precio estimado o proyectado** para las próximas 24 horas (usando la clave "predicted_close_24h").
       - El porcentaje de variación proyectado.
       Siempre que menciones valores monetarios, incluye el símbolo correspondiente (por ejemplo: $2,629.07 USD). Nunca dejes números sueltos de dinero sin su símbolo.
    3. PROFUNDIDAD EN LA JUSTIFICACIÓN: En la "justificacion", ofrece un análisis educativo pero completo y orientado a la toma de decisiones de inversión. Explica en un aproximado de 3 a 5 líneas con claridad si las condiciones actuales del mercado (tendencia, sentimiento y proyección) respaldan o desaconsejan invertir, mantener o vender en este momento, detallando el porqué de forma transparente para el usuario.
    4. Tono y Claridad: Redacta de forma descriptiva y natural, orientada a que un usuario común entienda con precisión qué está pasando con su inversión.

    Devuelve OBLIGATORIAMENTE un arreglo JSON bajo la clave "dictamenes", donde cada objeto contenga la siguiente estructura exacta:
    [
      {{
        "coin_id": "nombre-de-la-moneda",
        "symbol": "SÍMBOLO",
        "recomendacion": "COMPRAR" | "MANTENER" | "VENDER",
        "nivel_riesgo": "Bajo" | "Medio" | "Alto",
        "tendencia": "ALCISTA" | "BAJISTA" | "ESTABLE",
        "resumen_ejecutivo": "Explicación detallada que incluya obligatoriamente el precio actual (ej. $... USD), el precio estimado a 24 horas (ej. $... USD) y la variación porcentual.",
        "justificacion": "Análisis financiero detallado y fundamentado que explique al usuario si es prudente o no invertir y por qué basándose en el comportamiento del activo."
      }}
    ]
    """

    for modelo in MODELOS_A_PROBAR:
        try:
            print(f"📡 Enviando lote a Google Gemini usando modelo: '{modelo}'...")
            chat = client.chats.create(
                model=modelo,
                config=types.GenerateContentConfig(
                    temperature=0.2, response_mime_type="application/json"
                ),
            )
            response = chat.send_message(prompt)
            return json.loads(response.text)

        except Exception as e:
            if "503" in str(e):
                print(
                    f"⚠️ El modelo '{modelo}' está saturado (503). Probando con"
                    " el modelo de respaldo..."
                )
                time.sleep(5)
            else:
                raise e

    raise RuntimeError(
        "Todos los modelos de Gemini están experimentando alta demanda en este"
        " momento. Intenta de nuevo en un par de minutos."
    )


def ejecutar_proceso_diario():
    print("📥 [Paso 1] Extrayendo datos consolidados desde MongoDB Atlas...")
    lista_monedas = extraer_datos_consolidados()

    if not lista_monedas:
        print("⚠️ No se encontraron datos para procesar hoy.")
        return

    print(
        f"📊 [Paso 2] Consolidados {len(lista_monedas)} activos. Procesando"
        " análisis en LOTE..."
    )

    for intento in range(1, 4):
        try:
            resultado_agente = analizar_mercado_en_lote(lista_monedas)

            reporte_final = {
                "fecha_actualizacion": datetime.now(timezone.utc).isoformat(),
                "total_activos": len(lista_monedas),
                "cuota_consumida": "1 petición",
                "analisis_diario": resultado_agente.get("dictamenes", []),
            }

            os.makedirs("data", exist_ok=True)
            ruta_salida = os.path.join("data", "daily_recommendations.json")

            with open(ruta_salida, "w", encoding="utf-8") as f:
                json.dump(reporte_final, f, ensure_ascii=False, indent=2)

            print(
                "\n🎉 ¡Proceso completado con éxito!"
                f"\n📁 Resultados guardados en: '{ruta_salida}'"
            )
            break

        except Exception as e:
            print(
                f"⚠️ Error al procesar en lote (Intento {intento}/3): {e}."
                " Esperando 30 segundos..."
            )
            time.sleep(30)


if __name__ == "__main__":
    ejecutar_proceso_diario()