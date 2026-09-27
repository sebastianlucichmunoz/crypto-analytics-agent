from __future__ import annotations
import os
import math
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

for key in ("MONGODB_URI","MONGODB_DB_NAME"):
    try:
        if key in st.secrets and not os.getenv(key):
            os.environ[key] = str(st.secrets[key])
    except Exception:
        pass

from src.db import ping
from src.dashboard import (
    latest_market, history, ohlcv, news, news_for_coin,
    latest_prediction, latest_metrics, market_mood
)

st.set_page_config(
    page_title="Crypto Analytics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 2rem;}
[data-testid="stMetric"] {
    background: rgba(127,127,127,.06);
    border: 1px solid rgba(127,127,127,.18);
    border-radius: 14px;
    padding: 14px 16px;
}
.dashboard-title {font-size: 2.15rem; font-weight: 750; margin-bottom: .1rem;}
.dashboard-subtitle {opacity: .70; margin-bottom: 1rem;}
.badge {
    display:inline-block; padding:5px 11px; border-radius:999px;
    font-size:.82rem; font-weight:700; border:1px solid rgba(127,127,127,.25);
    background:rgba(127,127,127,.08); margin-right:6px;
}
.section-note {opacity:.68; font-size:.88rem;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="dashboard-title">Crypto Analytics Dashboard</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="dashboard-subtitle">Top 20 del mercado · CoinStats + Mobula · XGBoost · Noticias + NLTK/VADER</div>',
    unsafe_allow_html=True
)

try:
    ping()
except Exception as exc:
    st.error("No se pudo conectar a MongoDB Atlas.")
    st.code(str(exc))
    st.stop()

@st.cache_data(ttl=60)
def market_cached():
    return latest_market()

@st.cache_data(ttl=120)
def news_cached():
    return news(250)

market = market_cached()
if market.empty:
    st.warning("No hay datos en MongoDB. Ejecuta: python scripts/bootstrap.py")
    st.stop()

market = market.sort_values("rank").copy()
for c in ["price","market_cap","volume_24h","price_change_1h","price_change_1d","price_change_1w","price_change_1m"]:
    if c in market.columns:
        market[c] = pd.to_numeric(market[c], errors="coerce")

labels = {
    f"#{int(r['rank'])} · {r['name']} ({r['symbol']})": r["coin_id"]
    for _, r in market.iterrows()
}

st.sidebar.header("Panel de control")
selected_label = st.sidebar.selectbox("Activo", list(labels.keys()))
coin_id = labels[selected_label]
selected = market[market["coin_id"] == coin_id].iloc[0]
symbol = selected["symbol"]
name = selected["name"]

range_days = st.sidebar.selectbox(
    "Histórico",
    [30, 90, 180, 365, 730],
    index=3,
    format_func=lambda x: f"{x} días" if x < 365 else ("1 año" if x == 365 else "2 años"),
)
st.sidebar.caption("Los datos del dashboard se leen desde MongoDB Atlas.")

mood, mood_score, news_count = market_mood(24)
total_cap = market["market_cap"].sum(skipna=True)
total_volume = market["volume_24h"].sum(skipna=True)
avg_change = market["price_change_1d"].mean(skipna=True)
btc_row = market[market["symbol"].str.upper() == "BTC"]
btc_dom_proxy = (
    float(btc_row.iloc[0]["market_cap"]) / total_cap * 100
    if not btc_row.empty and total_cap else 0
)

k1,k2,k3,k4,k5 = st.columns(5)
k1.metric("Market cap Top 20", f"${total_cap/1e12:,.2f} T")
k2.metric("Volumen 24h", f"${total_volume/1e9:,.1f} B")
k3.metric("Cambio medio 24h", f"{avg_change:,.2f}%")
k4.metric("Peso BTC en Top 20", f"{btc_dom_proxy:,.1f}%")
k5.metric("Sentimiento 24h", mood, f"{news_count} noticias")

st.markdown("---")

# =======================
# MARKET OVERVIEW
# =======================
st.subheader("1. Panorama del mercado")
c1,c2 = st.columns([1.15, 1])

with c1:
    bar_df = market.sort_values("price_change_1d", ascending=True).copy()
    fig = px.bar(
        bar_df,
        x="price_change_1d",
        y="symbol",
        orientation="h",
        title="Variación de precio en 24 horas — Top 20",
        labels={"price_change_1d":"Variación 24h (%)","symbol":""},
        hover_data=["name","price","rank"],
    )
    fig.add_vline(x=0, line_width=1, opacity=.45)
    fig.update_layout(height=520, margin=dict(l=20,r=20,t=55,b=25))
    st.plotly_chart(fig, use_container_width=True)

with c2:
    tree = market.dropna(subset=["market_cap"]).copy()
    tree["market_cap"] = tree["market_cap"].clip(lower=0)
    fig = px.treemap(
        tree,
        path=["symbol"],
        values="market_cap",
        color="price_change_1d",
        hover_data={"name":True,"price":":.6f","market_cap":":.3s","price_change_1d":":.2f"},
        title="Composición del Top 20 por market cap",
    )
    fig.update_layout(height=520, margin=dict(l=10,r=10,t=55,b=10))
    st.plotly_chart(fig, use_container_width=True)

c3,c4 = st.columns(2)
with c3:
    scatter = market.dropna(subset=["market_cap","volume_24h"]).copy()
    fig = px.scatter(
        scatter,
        x="market_cap",
        y="volume_24h",
        size="market_cap",
        color="price_change_1d",
        hover_name="name",
        hover_data=["symbol","rank","price"],
        log_x=True,
        log_y=True,
        title="Market cap vs volumen 24h",
        labels={"market_cap":"Market cap (USD)","volume_24h":"Volumen 24h (USD)"},
    )
    fig.update_layout(height=430)
    st.plotly_chart(fig, use_container_width=True)

with c4:
    rank_df = market.sort_values("rank").head(10).copy()
    fig = px.bar(
        rank_df,
        x="symbol",
        y="market_cap",
        color="price_change_1d",
        title="Market cap — Top 10",
        labels={"market_cap":"Market cap (USD)","symbol":""},
        hover_data=["name","rank","price_change_1d"],
    )
    fig.update_layout(height=430)
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# =======================
# ASSET + FORECAST
# =======================
st.subheader(f"2. {name} ({symbol}) — comportamiento y XGBoost")

a1,a2,a3,a4 = st.columns(4)
a1.metric("Precio actual", f"${float(selected.get('price') or 0):,.6f}")
a2.metric("24h", f"{float(selected.get('price_change_1d') or 0):,.2f}%")
a3.metric("7d", f"{float(selected.get('price_change_1w') or 0):,.2f}%")
a4.metric("Ranking", f"#{int(selected['rank'])}")

hist = history(coin_id)
if not hist.empty:
    hist["date"] = pd.to_datetime(hist["date"], utc=True)
    hist = hist.sort_values("date").tail(range_days)

pred = latest_prediction(coin_id)
metrics = latest_metrics(coin_id)

left,right = st.columns([1.55,1])

with left:
    if not hist.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=hist["date"], y=hist["price"],
            mode="lines", name="Precio real"
        ))
        if pred:
            last_date = hist["date"].max()
            fig.add_trace(go.Scatter(
                x=[last_date, pd.to_datetime(pred["target_time"], utc=True)],
                y=[float(pred["current_price"]), float(pred["predicted_close_24h"])],
                mode="lines+markers",
                name="Pronóstico XGBoost",
                line=dict(dash="dash"),
            ))
        fig.update_layout(
            title=f"Precio histórico y pronóstico ~24h — {symbol}",
            yaxis_title="USD",
            xaxis_title="",
            height=500,
            hovermode="x unified",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No existe histórico de precio para este activo.")

with right:
    if pred:
        change = float(pred.get("predicted_change_pct") or 0)
        trend = pred.get("trend","—")
        st.markdown(
            f'<span class="badge">XGBoost: {trend}</span>'
            f'<span class="badge">Δ esperado: {change:+.2f}%</span>',
            unsafe_allow_html=True,
        )
        g = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=float(pred["predicted_close_24h"]),
            delta={"reference": float(pred["current_price"]), "relative": True, "valueformat": ".2%"},
            title={"text":"Cierre estimado ~24h"},
            gauge={"axis":{"visible":False}}
        ))
        g.update_layout(height=300, margin=dict(l=25,r=25,t=65,b=20))
        st.plotly_chart(g, use_container_width=True)

        st.caption(
            f"Modelo entrenado: {pd.to_datetime(pred.get('model_trained_at'), utc=True).strftime('%Y-%m-%d %H:%M UTC') if pred.get('model_trained_at') else '—'}"
        )
    else:
        st.info("Este activo aún no tiene predicción XGBoost.")

if metrics:
    st.markdown("#### Evidencia del desempeño de XGBoost")
    m1,m2,m3,m4,m5 = st.columns(5)
    m1.metric("MAE", f"{float(metrics.get('mae') or 0):,.4f}")
    m2.metric("RMSE", f"{float(metrics.get('rmse') or 0):,.4f}")
    m3.metric("MAPE", f"{float(metrics.get('mape_pct') or 0):,.2f}%")
    m4.metric("R²", f"{float(metrics.get('r2') or 0):,.3f}")
    m5.metric("Vs baseline", "Mejor" if metrics.get("beats_naive") else "No mejora")

    bx1,bx2 = st.columns([1.35,1])

    with bx1:
        backtest = metrics.get("backtest") or []
        if backtest:
            bt = pd.DataFrame(backtest)
            bt["date"] = pd.to_datetime(bt["date"], utc=True)
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=bt["date"], y=bt["actual"], mode="lines", name="Real"))
            fig.add_trace(go.Scatter(x=bt["date"], y=bt["predicted"], mode="lines", name="XGBoost"))
            fig.add_trace(go.Scatter(
                x=bt["date"], y=bt["baseline"], mode="lines",
                name="Baseline", line=dict(dash="dot")
            ))
            fig.update_layout(
                title="Backtest: precio real vs predicción",
                yaxis_title="USD", height=430, hovermode="x unified"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Reentrena el modelo una vez para generar el gráfico de backtest.")

    with bx2:
        imp = metrics.get("feature_importance") or {}
        if imp:
            imp_df = pd.DataFrame(
                [{"feature":k,"importance":v} for k,v in imp.items()]
            ).sort_values("importance", ascending=False).head(10).sort_values("importance")
            fig = px.bar(
                imp_df, x="importance", y="feature", orientation="h",
                title="Top 10 variables más influyentes en XGBoost",
                labels={"importance":"Importancia","feature":""}
            )
            fig.update_layout(height=430)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Reentrena el modelo una vez para guardar importancia de variables.")
else:
    st.info("Este activo no tiene métricas de XGBoost; puede ser stablecoin o no contar con historial suficiente.")

st.markdown("---")

# =======================
# SENTIMENT
# =======================
st.subheader("3. Análisis de sentimientos de noticias")

all_news = news_cached()
coin_news = news_for_coin(coin_id, 250)

sentiment_scope = st.radio(
    "Ámbito del sentimiento",
    ["Mercado completo", f"Solo {symbol}"],
    horizontal=True,
)
sent_df = all_news if sentiment_scope == "Mercado completo" else coin_news

if sent_df.empty:
    st.info("No hay noticias suficientes para este filtro.")
else:
    sent_df = sent_df.copy()
    sent_df["published_at"] = pd.to_datetime(sent_df["published_at"], utc=True)
    sent_df["day"] = sent_df["published_at"].dt.floor("D")
    sent_df["sentiment_compound"] = pd.to_numeric(sent_df["sentiment_compound"], errors="coerce")

    s1,s2,s3 = st.columns(3)
    avg_sent = sent_df["sentiment_compound"].mean()
    pos_pct = (sent_df["sentiment_label"] == "POSITIVO").mean() * 100
    neg_pct = (sent_df["sentiment_label"] == "NEGATIVO").mean() * 100
    s1.metric("Sentimiento promedio", f"{avg_sent:+.3f}")
    s2.metric("Noticias positivas", f"{pos_pct:.1f}%")
    s3.metric("Noticias negativas", f"{neg_pct:.1f}%")

    sc1,sc2 = st.columns(2)

    with sc1:
        counts = (
            sent_df["sentiment_label"]
            .value_counts()
            .rename_axis("sentiment")
            .reset_index(name="count")
        )
        fig = px.pie(
            counts, names="sentiment", values="count", hole=.58,
            title="Distribución del sentimiento"
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

    with sc2:
        daily = sent_df.groupby("day", as_index=False)["sentiment_compound"].mean()
        fig = px.line(
            daily, x="day", y="sentiment_compound", markers=True,
            title="Evolución diaria del sentimiento",
            labels={"day":"","sentiment_compound":"Score VADER"}
        )
        fig.add_hline(y=0, line_width=1, opacity=.4)
        fig.update_yaxes(range=[-1,1])
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

    sc3,sc4 = st.columns(2)

    with sc3:
        by_source = (
            sent_df.groupby("source", as_index=False)
            .agg(
                sentiment=("sentiment_compound","mean"),
                news=("title","count")
            )
            .sort_values("sentiment")
        )
        fig = px.bar(
            by_source, x="sentiment", y="source", orientation="h",
            text="news", title="Sentimiento promedio por fuente",
            labels={"sentiment":"Score promedio","source":""}
        )
        fig.update_xaxes(range=[-1,1])
        fig.update_layout(height=380)
        st.plotly_chart(fig, use_container_width=True)

    with sc4:
        latest = sent_df.sort_values("published_at", ascending=False).head(8)
        st.markdown("##### Últimas señales")
        for _,r in latest.iterrows():
            score = float(r["sentiment_compound"])
            st.markdown(
                f'<span class="badge">{r["sentiment_label"]} {score:+.2f}</span> '
                f'**[{r["title"]}]({r["url"]})**',
                unsafe_allow_html=True,
            )
            st.caption(f'{r["source"]} · {r["published_at"].strftime("%Y-%m-%d %H:%M UTC")}')

st.markdown("---")
st.caption(
    "Metodología del PMV: datos estructurados de CoinStats/Mobula + RSS de CoinDesk, Cointelegraph y Decrypt. "
    "XGBoost se evalúa contra un baseline; el sentimiento se calcula con NLTK/VADER. "
    "PÁNICO/NEUTRAL/CODICIA es un proxy académico, no el Fear & Greed Index oficial."
)
