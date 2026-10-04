import os
import json
from datetime import datetime, timedelta
from google import genai
from src.db import get_db

MODELOS_A_PROBAR = ["gemini-3.5-flash", "gemini-3.5-flash-lite"]

def ejecutar_agente_notificaciones():
    print("-> El script del agente se ha iniciado correctamente...")
    db = get_db()
    
    # 1. Obtener clientes activos
    clientes = list(db.clients.find({"active": True}))
    if not clientes:
        print("No hay clientes activos para evaluar.")
        return

    # 2. Obtener las monedas únicas de las watchlists
    monedas_requeridas = set()
    for cliente in clientes:
        for moneda in cliente.get("watchlist", []):
            monedas_requeridas.add(moneda)

# ... dentro de tu función ejecutar_agente_notificaciones():
    resumen_mercado = {}
    for coin in monedas_requeridas:
        pred = db.predictions.find_one({"coin_id": coin}, sort=[("predicted_at", -1)])
        if pred and "predictions_15d" in pred:
            forecast_data = pred["predictions_15d"]
            
            # Generar los textos asociando el día calendario real
            dias_con_fecha = []
            hoy = datetime.now()
            for i, p in enumerate(forecast_data):
                # Calculamos la fecha sumando 'i' días a la fecha de hoy
                fecha_futura = hoy + timedelta(days=i)
                fecha_str = fecha_futura.strftime("%d de %B") # Ejemplo: "19 de October" (o en español si configuras locale)
                precio = p.get('price', 0)
                dias_con_fecha.append(f"{fecha_str}: ${precio:.2f}")
            
            dias_resumen = ", ".join(dias_con_fecha)
            resumen_mercado[coin] = f"Tendencia general: {pred.get('trend', 'N/A')} | Variación estimada: {pred.get('predicted_change_pct', 0)}% | Proyección diaria: {dias_resumen}"
        else:
            resumen_mercado[coin] = "Sin datos de predicción disponibles actualmente."


    # # 3. Recopilar predicciones a 15 días desde MongoDB
    # resumen_mercado = {}
    # for coin in monedas_requeridas:
    #     pred = db.predictions.find_one({"coin_id": coin}, sort=[("predicted_at", -1)])
    #     if pred and "predictions_15d" in pred:
    #         forecast_data = pred["predictions_15d"]
    #         total_dias = len(forecast_data)
    #         dias_resumen = ", ".join([f"Día {i+1}: ${p.get('price', 0):.2f}" for i, p in enumerate(forecast_data)])
    #         resumen_mercado[coin] = f"Tendencia general: {pred.get('trend', 'N/A')} | Variación estimada: {pred.get('predicted_change_pct', 0)}% | Detalle a {total_dias} días: {dias_resumen}"
    #     else:
    #         resumen_mercado[coin] = "Sin datos de predicción disponibles actualmente."

    # 4. Preparar el payload de clientes
    payload_clientes = []
    for cliente in clientes:
        payload_clientes.append({
            "cliente_id": str(cliente["_id"]),
            "nombre": cliente["name"],
            "email": cliente["email"],
            "watchlist": cliente["watchlist"],
            "preferencia": cliente["preferencia"]
        })

    prompt_sistema = f"""
    Eres un asesor financiero humano, experto, cercano y amigable especializado en criptomonedas. Tu objetivo es redactar un análisis claro, profesional pero de muy fácil comprensión para inversionistas principiantes, usando un tono conversacional (como si le escribieras directamente un mensaje personalizado a tu cliente).

    Analiza el siguiente resumen de mercado a 15 días para las monedas de los clientes y evalúa estrictamente sus preferencias individuales.
    
    Resumen de Mercado por Moneda:
    {json.dumps(resumen_mercado, ensure_ascii=False)}

    Lista de Clientes y Preferencias:
    {json.dumps(payload_clientes, ensure_ascii=False)}

    INSTRUCCIONES ESTRICTAS DE RESPUESTA:
    Para cada cliente, determina si se debe enviar una alerta comparando los movimientos de sus monedas con su campo "preferencia".
    Retorna ÚNICAMENTE un objeto JSON válido con una lista llamada "resultados" que contenga exactamente estos campos:
    - cliente_id (string)
    - enviar_correo (booleano: true o false)
    - resumen_personalizado (Un texto resumido, redactado en un tono muy humano y accesible para un principiante. Debe explicar de forma sencilla el panorama de aquí a 15 días, mencionando obligatoriamente los porcentajes estimados de subida o bajada, los precios esperados y señalando qué días específicos del calendario se proyectan como el pico de mayor ganancia o de riesgo/caída para las monedas de su interés, enfocándose solo en lo verdaderamente relevante para su perfil).
    - orden_inversion (Una instrucción consisa y específica que incluya obligatoriamente el nombre de la moneda, por ejemplo: "Invertir en Bitcoin", "Vender Ethereum" o "Mantener posición en Cardano", nunca dejes la orden suelta para evitar confusiones).
    """

    client_ai = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    response = None
    modelo_usado = None

    # 5. Iterar sobre los modelos de respaldo (Fallback Strategy)
    for modelo in MODELOS_A_PROBAR:
        try:
            print(f"Intentando conectar con el modelo: {modelo}...")
            response = client_ai.models.generate_content(
                model=modelo,
                contents=prompt_sistema
            )
            modelo_usado = modelo
            print(f"¡Éxito al conectar con {modelo}!")
            break
        except Exception as e:
            print(f"Fallo con el modelo {modelo}: {e}. Intentando con el siguiente...")

    if not response:
        print("Error crítico: Ninguno de los modelos en la lista pudo responder.")
        return

    print(f"Respuesta obtenida usando el modelo: {modelo_usado}")
    
    try:
        # Limpiar la respuesta de la IA por si trae bloques de código markdown ```json ... ```
        raw_text = response.text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
        
        data_resultado = json.loads(raw_text.strip())
        
        # 6. Cruzar los resultados de la IA con los datos del cliente (Email, Watchlist, ID) y guardar en MongoDB
        resultados_finales = []
        # Creamos un diccionario rápido para buscar al cliente por su ID de texto
        clientes_dict = {str(c["_id"]): c for c in clientes}

        for res in data_resultado.get("resultados", []):
            c_id = res.get("cliente_id")
            cliente_info = clientes_dict.get(c_id, {})
            
            registro_procesado = {
                "cliente_id": c_id,
                "nombre": cliente_info.get("name", "Desconocido"),
                "email": cliente_info.get("email", ""),
                "watchlist": cliente_info.get("watchlist", []),
                "enviar_correo": res.get("enviar_correo", False),
                "resumen_personalizado": res.get("resumen_personalizado", ""),
                "orden_inversion": res.get("orden_inversion", ""),
                "modelo_usado": modelo_usado,
                "fecha_generacion": datetime.utcnow()
            }
            resultados_finales.append(registro_procesado)

        # Guardar el bloque completo en una colección de logs en MongoDB
        log_documento = {
            "fecha_ejecucion": datetime.utcnow(),
            "modelo": modelo_usado,
            "resultados": resultados_finales
        }
        db.notification_logs.insert_one(log_documento)
        print("¡Resultados guardados exitosamente en la base de datos (colección: notification_logs)!")

        # 7. Simulación o preparación práctica para el envío de correos
        print("\n--- RESUMEN DE ENVÍO DE CORREOS ---")
        for reg in resultados_finales:
            if reg["enviar_correo"]:
                print(f"[ENVIAR] Correo a: {reg['email']} | Cliente: {reg['nombre']} | Monedas: {reg['watchlist']} | Orden: {reg['orden_inversion']}")
            else:
                print(f"[OMITIR] No se requiere correo para: {reg['email']} (Bandera en False)")

    except Exception as parse_error:
        print(f"Error procesando o guardando el JSON de la IA: {parse_error}")
        print("Texto recibido:", response.text)

if __name__ == "__main__":
    ejecutar_agente_notificaciones()

#python -m src.agents.notification_agent



# import os
# import json
# from google import genai
# from google.genai.errors import APIError # O capturar excepciones generales
# from src.db import get_db

# print("-> El script del agente se ha iniciado correctamente...")

# MODELOS_A_PROBAR = ["gemini-3.5-flash", "gemini-3.5-flash-lite"]

# def ejecutar_agente_notificaciones():
#     db = get_db()
    
#     # 1. Obtener clientes activos
#     clientes = list(db.clients.find({"active": True}))
#     if not clientes:
#         print("No hay clientes activos para evaluar.")
#         return

#     # 2. Obtener las monedas únicas de las watchlists
#     monedas_requeridas = set()
#     for cliente in clientes:
#         for moneda in cliente.get("watchlist", []):
#             monedas_requeridas.add(moneda)

# # 3. Recopilar predicciones a 15 días desde la estructura real de MongoDB
#     resumen_mercado = {}
#     for coin in monedas_requeridas:
#         # Buscamos la predicción más reciente que coincida con el coin_id (ej. "bitcoin", "ethereum")
#         pred = db.predictions.find_one({"coin_id": coin}, sort=[("predicted_at", -1)])
        
#         if pred and "predictions_15d" in pred:
#             forecast_data = pred["predictions_15d"]
#             total_dias = len(forecast_data)
            
#             # Construimos el resumen legible para la IA usando los datos reales de predictions_15d
#             dias_resumen = ", ".join([f"Día {i+1}: ${p.get('price', 0):.2f}" for i, p in enumerate(forecast_data)])
#             resumen_mercado[coin] = f"Tendencia general: {pred.get('trend', 'N/A')} | Variación estimada: {pred.get('predicted_change_pct', 0)}% | Detalle a {total_dias} días: {dias_resumen}"
#         else:
#             resumen_mercado[coin] = "Sin datos de predicción disponibles actualmente."


#     # 4. Preparar el payload de clientes
#     payload_clientes = []
#     for cliente in clientes:
#         payload_clientes.append({
#             "cliente_id": str(cliente["_id"]),
#             "nombre": cliente["name"],
#             "email": cliente["email"],
#             "watchlist": cliente["watchlist"],
#             "preferencia": cliente["preferencia"]
#         })

#     prompt_sistema = f"""
#     Eres un asesor financiero algorítmico experto en criptomonedas.
#     Analiza el siguiente resumen de mercado a 15 días para las monedas de los clientes y evalúa sus preferencias individuales.
    
#     Resumen de Mercado por Moneda:
#     {json.dumps(resumen_mercado, ensure_ascii=False)}

#     Lista de Clientes y Preferencias:
#     {json.dumps(payload_clientes, ensure_ascii=False)}

#     INSTRUCCIONES ESTRICTAS:
#     Para cada cliente, determina si se debe enviar una alerta comparando los movimientos de sus monedas con su campo "preferencia".
#     Retorna ÚNICAMENTE un objeto JSON válido con una lista llamada "resultados" que contenga:
#     - cliente_id
#     - enviar_correo (booleano: true o false)
#     - resumen_personalizado (texto breve explicando el comportamiento de su moneda según su perfil)
#     - orden_inversion (texto corto: "Invertir", "Vender", o "Mantener posición")
#     """

#     client_ai = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
#     response = None
#     modelo_usado = None

#     # 5. Iterar sobre los modelos de respaldo (Fallback Strategy)
#     for modelo in MODELOS_A_PROBAR:
#         try:
#             print(f"Intentando conectar con el modelo: {modelo}...")
#             response = client_ai.models.generate_content(
#                 model=modelo,
#                 contents=prompt_sistema
#             )
#             modelo_usado = modelo
#             print(f"¡Éxito al conectar con {modelo}!")
#             break  # Si responde bien, rompemos el ciclo y no probamos los demás
#         except Exception as e:
#             print(f"Fallo con el modelo {modelo}: {e}. Intentando con el siguiente...")

#     if not response:
#         print("Error crítico: Ninguno de los modelos en la lista pudo responder.")
#         return

#     print(f"Respuesta obtenida usando el modelo: {modelo_usado}")
#     print(response.text)




# if __name__ == "__main__":
#     ejecutar_agente_notificaciones()