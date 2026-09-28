# crypto-analytics-agent

PMV académico:

**CoinStats + Mobula + RSS + Gemini AI ── Python ── MongoDB Atlas ── Streamlit**

> Proyecto académico. Las predicciones son experimentales y no constituyen asesoría financiera directa.

## Arquitectura

```text
CoinStats ─┐
           ├── Python ETL ── MongoDB Atlas ── Streamlit (Dashboard)
Mobula ────┤       │               │
           │       ├── XGBoost     └── GitHub Actions (Automatización)
RSS ───────┘       └── NLTK / VADER
                           │
                           └── Google Gemini AI (Agente Batch) ── daily_recommendations.json

## Colecciones en MongoDB

Las siguientes colecciones se crean automáticamente:

- `assets`
- `market_snapshots`
- `mobula_snapshots`
- `price_history`
- `ohlcv`
- `news`
- `models`
- `model_metrics`
- `predictions`
- `pipeline_runs`

---

## Top 20 y Agente de IA

El **Top 20** es dinámico: cada refresco consulta CoinStats ordenando por `rank`. MongoDB conserva el histórico aunque una moneda salga temporalmente del Top 20.

Además, el sistema integra un **Agente Batch de Gemini AI** (`src/agents/batch_agent.py`) que procesa:

- Datos del mercado.
- Predicciones de Machine Learning.
- Noticias recientes.

El agente genera dictámenes profesionales de inversión detallados en:

```text
data/daily_recommendations.json
```

Estos resultados quedan listos para ser consumidos por el dashboard en Streamlit.

---

##  Frecuencia y Automatización (GitHub Actions)

El workflow automatizado de GitHub Actions:

```text
.github/workflows/refresh.yml
```

se ejecuta de forma calendarizada mediante `cron`, ajustada a la hora local de Lima (PET):

| Hora Lima (PET) | Hora UTC |
|---|---|
| 07:00 AM | 12:00 UTC |
| 04:00 PM | 21:00 UTC |
| 06:30 PM | 23:30 UTC |

También se admiten ejecuciones manuales mediante `workflow_dispatch`, con opción de histórico y reentrenamiento.

---

##  Instalación local en Windows

### 1. Crear y activar el entorno virtual

```powershell
cd crypto_analytics_pmv
python -m venv .venv
.venv\Scripts\activate
```

### 2. Instalar dependencias

```powershell
python -m pip install -r requirements.txt
```

### 3. Configurar variables de entorno

Copia el archivo de ejemplo:

```powershell
copy .env.example .env
```

Luego edita `.env` y coloca tus credenciales.

---

## Probar MongoDB

Ejecuta:

```powershell
python scripts/test_connection.py
```

---

## Primera carga completa

Ejecuta:

```powershell
python scripts/bootstrap.py
```

La primera carga realiza las siguientes tareas:

1. Obtiene el Top 20 de CoinStats.
2. Guarda snapshots.
3. Resuelve IDs de Mobula.
4. Descarga aproximadamente 2 años de histórico diario.
5. Intenta obtener OHLCV de Mobula.
6. Descarga noticias RSS.
7. Aplica NLTK/VADER para el análisis de sentimiento.
8. Entrena XGBoost.
9. Genera predicciones.

---

##  Ejecutar el Agente de IA localmente

```powershell
python -m src.agents.batch_agent
```

---

## Levantar el Dashboard con Streamlit

```powershell
streamlit run app.py
```

---

## Modelo ML y Predicciones

### Target

El modelo tiene como objetivo predecir el **cierre/precio del siguiente día (~24 horas)**.

### Features principales

- Precio de cierre / volumen.
- Retornos de `1d`, `3d`, `7d` y `14d`.
- Medias móviles `MA 7/14/30`.
- Medias móviles exponenciales `EMA 7/21`.
- Volatilidad y momentum.
- `RSI 14`.
- Lags temporales.
- Sentimiento diario agregado.

### Umbrales de tendencia

| Tendencia | Condición |
|---|---|
| **ALCISTA** | > +0.50% |
| **ESTABLE** | Entre -0.50% y +0.50% |
| **BAJISTA** | < -0.50% |

---

##  GitHub Actions — Secrets obligatorios

Configura los siguientes **Repository Secrets** en tu repositorio de GitHub:

```text
MONGODB_URI
MONGODB_DB_NAME
COINSTATS_API_KEY
MOBULA_API_KEY
GEMINI_API_KEY
```

El flujo ejecuta automáticamente:

- Actualización de datos.
- Predicciones.
- Generación de recomendaciones mediante IA.

De esta manera, no requiere intervención manual.

---

## Streamlit Cloud

El dashboard solo necesita las variables de conexión a la base de datos:

```toml
MONGODB_URI="mongodb+srv://..."
MONGODB_DB_NAME="crypto_analytics"
```

No necesitas incluir las API keys en Streamlit, ya que todo el procesamiento pesado y la ingesta se realizan de forma centralizada mediante GitHub Actions.

---

## Comandos útiles

### Refresco manual del pipeline

```powershell
python scripts/refresh.py
```

### Refresco diario completo con reentrenamiento

```powershell
python scripts/refresh.py --daily
```

### Ejecución exclusiva de modelos

```powershell
python scripts/train_models.py
```
