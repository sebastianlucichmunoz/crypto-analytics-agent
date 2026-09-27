# Crypto Analytics PMV — Top 20

PMV académico para Business Analytics:

**CoinStats + Mobula + RSS -> Python -> MongoDB Atlas -> XGBoost/NLTK -> Streamlit**

La fase final puede reutilizar MongoDB y el pipeline para Power BI.

> Proyecto académico. Las predicciones son experimentales y no constituyen asesoría financiera.

## Arquitectura

```text
CoinStats ─┐
           ├── Python ETL ── MongoDB Atlas ── Streamlit
Mobula ────┤       │               │
           │       ├── XGBoost     └── Power BI (fase final)
RSS ───────┘       └── NLTK / VADER
```

## Colecciones

Se crean automáticamente:

- assets
- market_snapshots
- mobula_snapshots
- price_history
- ohlcv
- news
- models
- model_metrics
- predictions
- pipeline_runs

## Top 20

El Top 20 es dinámico: cada refresco consulta CoinStats ordenando por `rank`.
MongoDB conserva el histórico aunque una moneda salga temporalmente del Top 20.

## Frecuencia

El workflow incluido actualiza a las 00:00, 06:00, 12:00 y 18:00 hora de Lima.
El dashboard nunca consume las APIs directamente; lee MongoDB.

En la ejecución de medianoche también:
- actualiza histórico reciente;
- actualiza OHLCV cuando está disponible;
- reentrena XGBoost;
- genera nuevas predicciones.

## Instalación local en Windows

```powershell
cd crypto_analytics_pmv
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
```

Edita `.env` y coloca tus credenciales.

### 1. Probar MongoDB

```powershell
python scripts/test_connection.py
```

### 2. Primera carga completa

```powershell
python scripts/bootstrap.py
```

La primera carga:
1. obtiene Top 20 de CoinStats;
2. guarda snapshots;
3. resuelve IDs de Mobula;
4. descarga ~2 años de histórico diario;
5. intenta obtener OHLCV de Mobula;
6. descarga noticias RSS;
7. aplica NLTK/VADER;
8. entrena XGBoost;
9. genera predicciones.

### 3. Levantar el PMV

```powershell
streamlit run app.py
```

## Modelo ML

Target: cierre/precio del siguiente día (~24h).

Features:
- close/precio;
- volumen cuando existe;
- retornos 1d, 3d, 7d, 14d;
- MA 7/14/30;
- EMA 7/21;
- volatilidad 7/14/30;
- momentum 7/14;
- RSI 14;
- lags 1/2/3/7;
- sentimiento diario agregado.

Evaluación cronológica 80/20:
- MAE
- RMSE
- MAPE
- R²
- baseline MAE (mañana = hoy)

La tendencia:
- ALCISTA: > +0.50%
- ESTABLE: entre -0.50% y +0.50%
- BAJISTA: < -0.50%

Las stablecoins se monitorean, pero no se entrenan por defecto.

## OHLCV

Mobula expone OHLCV token-level por contrato. No todos los activos nativos tienen una serie token-level perfectamente comparable.

Por eso el pipeline:
1. intenta guardar OHLCV cuando hay un token compatible;
2. siempre mantiene `price_history` a nivel de activo;
3. XGBoost prefiere OHLCV si hay cobertura suficiente y, si no, usa el histórico de precios.

## Sentimiento

Se almacena el título, resumen RSS, enlace, fecha, fuente y score VADER.
`PÁNICO / NEUTRAL / CODICIA` es un **proxy académico de sentimiento**, no el Fear & Greed Index oficial.

## GitHub Actions

Crea estos Repository Secrets:

- `MONGODB_URI`
- `MONGODB_DB_NAME`
- `COINSTATS_API_KEY`
- `MOBULA_API_KEY`

El archivo `.github/workflows/refresh.yml` ya contiene los 4 horarios diarios.

## Streamlit Cloud

El dashboard solo necesita:

```toml
MONGODB_URI="mongodb+srv://..."
MONGODB_DB_NAME="crypto_analytics"
```

No necesitas poner las API keys en Streamlit porque la extracción la realiza GitHub Actions.

## Comandos útiles

Refresco normal:

```powershell
python scripts/refresh.py
```

Refresco diario con reentrenamiento:

```powershell
python scripts/refresh.py --daily
```

Solo modelos:

```powershell
python scripts/train_models.py
```


## Actualización visual del dashboard

Esta versión agrega visualizaciones para evidenciar directamente el trabajo analítico:

- variación 24h de las 20 criptomonedas;
- treemap por market cap;
- market cap vs volumen;
- histórico de precio + pronóstico XGBoost;
- backtest real vs XGBoost vs baseline;
- importancia de variables de XGBoost;
- distribución de sentimientos;
- evolución temporal de sentimiento;
- sentimiento promedio por fuente;
- etiquetas de tendencia y señales recientes.

Después de reemplazar esta versión, ejecuta **una vez**:

```powershell
python scripts\train_models.py
```

Eso vuelve a guardar los modelos con `feature_importance` y `backtest`.
Luego:

```powershell
streamlit run app.py
```
