from __future__ import annotations
import os
import math
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

for key in ("MONGODB_URI", "MONGODB_DB_NAME"):
    try:
        if key in st.secrets and not os.getenv(key):
            os.environ[key] = str(st.secrets[key])
    except Exception:
        pass

from src.db import ping
from src.dashboard import (
    latest_market, history, ohlcv, news, news_for_coin,
    latest_prediction, latest_metrics, market_mood, load_gemini_recommendations
)

# Configuración de página
st.set_page_config(
    page_title="Crypto Analytics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==========================================
# CSS 
# ==========================================
st.markdown("""
<style>
/* Fondo general claro del panel principal */
.stApp {
    background-color: #F8FAFC;
}

/* Espaciados limpios */
.block-container {
    padding-top: 2rem !important;
    padding-bottom: 3rem !important;
}

/* --- ESTILOS DE LA BARRA LATERAL (SIDEBAR) NEGRA Y MOSTAZA --- */
[data-testid="stSidebar"] {
    background-color: #0B0F19 !important; /* Negro elegante */
    border-right: 3px solid #EAB308 !important; /* Borde amarillo mostaza */
}
/* Textos de la barra lateral en Mostaza */
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, 
[data-testid="stSidebar"] p, [data-testid="stSidebar"] label, [data-testid="stSidebar"] .stMarkdown {
    color: #EAB308 !important;
    font-weight: 600;
}
/* Cajas de selección (Filtros) en Mostaza con texto Negro */
[data-testid="stSidebar"] div[data-baseweb="select"] > div {
    background-color: #EAB308 !important;
    border-color: #EAB308 !important;
    border-radius: 6px;
    color: #000000 !important;
}
[data-testid="stSidebar"] div[data-baseweb="select"] span {
    color: #000000 !important;
    font-weight: 700;
}
[data-testid="stSidebar"] svg {
    fill: #000000 !important;
}

/* --- TARJETAS DE MÉTRICAS (SUPERIORES Y CENTRADAS) --- */
[data-testid="stMetric"] {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-left: 4px solid #1E3A8A; /* Detalle Azul Corporativo */
    border-radius: 8px;
    padding: 12px 16px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.04);
}
[data-testid="stMetricLabel"] {
    color: #475569 !important;
    font-size: 0.9rem !important;
    font-weight: 600 !important;
}
[data-testid="stMetricValue"] {
    color: #0F172A !important;
    font-size: 1.6rem !important;
    font-weight: 800 !important;
}

/* Títulos de sección en Azul */
.section-title {
    color: #1E3A8A;
    font-size: 1.5rem;
    font-weight: 700;
    margin-top: 1.5rem;
    margin-bottom: 1rem;
    border-bottom: 2px solid #EAB308;
    padding-bottom: 5px;
    display: inline-block;
}

/* Badges de noticias y estados */
.badge {
    display: inline-block;
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 0.8rem;
    font-weight: 700;
    background-color: #EFF6FF;
    color: #1E3A8A;
    border: 1px solid #BFDBFE;
    margin-right: 6px;
    margin-bottom: 4px;
}
</style>
""", unsafe_allow_html=True)

# =======================
# CABECERA: LOGO + TÍTULO
# =======================
st.markdown("""
<div style="display: flex; align-items: center; gap: 20px; margin-bottom: 20px;">
    <img src="https://www.interactivebrokers.com.hk/images/web/crypto-tokens-hk-hero-nbg.png" style="width: 120px; filter: drop-shadow(0px 4px 6px rgba(0,0,0,0.1));">
    <div>
        <h1 style="margin: 0; color: #0F172A; font-size: 2.6rem; font-weight: 800; line-height: 1.1;">Crypto Analytics Dashboard</h1>
        <p style="margin: 0; color: #64748B; font-size: 1.1rem; font-weight: 500;">Top 20 del mercado · Modelos Predictivos · Gemini AI</p>
    </div>
</div>
""", unsafe_allow_html=True)

try:
    ping()
except Exception as exc:
    st.error("No se pudo conectar a MongoDB Atlas.")
    st.stop()

@st.cache_data(ttl=60)
def market_cached(): return latest_market()

@st.cache_data(ttl=120)
def news_cached(): return news(250)

market = market_cached()
if market.empty:
    st.warning("No hay datos en MongoDB Atlas.")
    st.stop()

market = market.sort_values("rank").copy()
for c in ["price", "market_cap", "volume_24h", "price_change_1h", "price_change_1d", "price_change_1w"]:
    if c in market.columns:
        market[c] = pd.to_numeric(market[c], errors="coerce")

labels = {f"#{int(r['rank'])} · {r['name']} ({r['symbol']})": r["coin_id"] for _, r in market.iterrows()}

# =======================
# BARRA LATERAL (SIDEBAR)
# =======================
st.sidebar.image("https://www.interactivebrokers.com.hk/images/web/crypto-tokens-hk-hero-nbg.png", width=100)
st.sidebar.header("Panel de control")
selected_label = st.sidebar.selectbox("Activo", list(labels.keys()))
coin_id = labels[selected_label]
selected = market[market["coin_id"] == coin_id].iloc[0]
symbol = selected["symbol"]
name = selected["name"]

range_days = st.sidebar.selectbox(
    "Histórico (Gráfico)",
    [30, 90, 180, 365, 730],
    index=3,
    format_func=lambda x: f"{x} días" if x < 365 else ("1 año" if x == 365 else "2 años"),
)
st.sidebar.caption("")

# =========================================================
# 1. DATOS  DE LA MONEDA
# =========================================================
st.markdown(f"<div align='center'><h2 style='color: #0F172A; font-weight: 800;'>Métricas en Tiempo Real: {name} ({symbol})</h2></div>", unsafe_allow_html=True)
s
coin_news_df = news_for_coin(coin_id, 250)
if not coin_news_df.empty:
    coin_news_df["sentiment_compound"] = pd.to_numeric(coin_news_df["sentiment_compound"], errors="coerce")
    coin_sent = coin_news_df["sentiment_compound"].mean()
    coin_sent_label = "Positivo" if coin_sent > 0.05 else ("Negativo" if coin_sent < -0.05 else "Neutral")
else:
    coin_sent_label = "Sin datos"

_, c_m1, c_m2, c_m3, c_m4, _ = st.columns([0.5, 1, 1, 1, 1, 0.5])
c_m1.metric("Precio Actual", f"${float(selected.get('price') or 0):,.4f}")
c_m2.metric("Volumen 24h", f"${float(selected.get('volume_24h') or 0)/1e6:,.1f} M")
c_m3.metric("Rendimiento Día", f"{float(selected.get('price_change_1d') or 0):+.2f}%")
c_m4.metric("Sentimiento Activo", coin_sent_label)

st.markdown("<hr style='border:1px solid #E2E8F0; margin-top:2rem; margin-bottom:2rem;'>", unsafe_allow_html=True)

# =========================================================
# 2. DICTAMEN DE IA (GEMINI)
# =========================================================
st.markdown(f"<div class='section-title'>🤖 Dictamen Principal de IA para {name}</div>", unsafe_allow_html=True)

rec_data = load_gemini_recommendations()

if rec_data and "analisis_diario" in rec_data:
    dictamen_activo = next((item for item in rec_data["analisis_diario"] if item.get("coin_id") == coin_id or item.get("symbol") == symbol), None)
    if dictamen_activo:
        rec = dictamen_activo.get("recomendacion", "N/A")
        riesgo = dictamen_activo.get("nivel_riesgo", "N/A")
        tendencia = dictamen_activo.get("tendencia", "N/A")
        color_hex = "#10B981" if rec == "COMPRAR" else ("#EF4444" if rec == "VENDER" else "#F59E0B")

        st.markdown(f"""
        <div style="background-color: #FFFFFF; border: 2px solid {color_hex}; border-radius: 12px; padding: 25px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
            <div style="display:flex; justify-content: space-between; margin-bottom: 15px;">
                <div style="text-align: center; width: 33%;">
                    <p style="margin:0; color: #64748B; font-size: 0.9rem; font-weight:bold;">Recomendación IA</p>
                    <h3 style="margin:0; color: {color_hex}; font-size: 1.8rem;">{rec}</h3>
                </div>
                <div style="text-align: center; width: 33%; border-left: 1px solid #E2E8F0; border-right: 1px solid #E2E8F0;">
                    <p style="margin:0; color: #64748B; font-size: 0.9rem; font-weight:bold;">Nivel de Riesgo</p>
                    <h3 style="margin:0; color: #0F172A; font-size: 1.5rem;">{riesgo}</h3>
                </div>
                <div style="text-align: center; width: 33%;">
                    <p style="margin:0; color: #64748B; font-size: 0.9rem; font-weight:bold;">Tendencia General</p>
                    <h3 style="margin:0; color: #0F172A; font-size: 1.5rem;">{tendencia}</h3>
                </div>
            </div>
            <div style="background-color: #F8FAFC; padding: 15px; border-radius: 8px; border-left: 4px solid {color_hex};">
                <p style="margin:0 0 10px 0; color: #334155;"><strong>Resumen Ejecutivo:</strong> {dictamen_activo.get('resumen_ejecutivo', '')}</p>
                <p style="margin:0; color: #334155;"><strong>Justificación:</strong> {dictamen_activo.get('justificacion', '')}</p>
            </div>
            <p style="margin:10px 0 0 0; text-align:right; font-size:0.75rem; color:#94A3B8;">Última actualización: {rec_data.get('fecha_actualizacion', 'Desconocida')}</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("No hay un dictamen generado para este activo en la base de datos.")
else:
    st.warning("No se encontraron recomendaciones recientes de Gemini.")

st.markdown("<br>", unsafe_allow_html=True)

# =========================================================
# 3. GRÁFICO
# =========================================================
c_chart, c_news = st.columns([1.8, 1], gap="large")

with c_chart:
    st.markdown(f"<div class='section-title'>Comportamiento Histórico de la moneda</div>", unsafe_allow_html=True)
    hist = history(coin_id)
    pred = latest_prediction(coin_id)

    if not hist.empty:
        hist["date"] = pd.to_datetime(hist["date"], utc=True)
        hist = hist.sort_values("date").tail(range_days)
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=hist["date"], y=hist["price"], 
            mode="lines", name="Precio Real", 
            line=dict(color="#1E3A8A", width=2.5)
        ))
        
        if pred:
            last_date = hist["date"].max()
            fig.add_trace(go.Scatter(
                x=[last_date, pd.to_datetime(pred["target_time"], utc=True)],
                y=[float(pred["current_price"]), float(pred["predicted_close_24h"])],
                mode="lines+markers", name="Pronóstico XGBoost",
                line=dict(dash="dash", color="#EAB308", width=3),
                marker=dict(size=8)
            ))
    
        fig.update_layout(
            template="plotly_white",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#0F172A"),
            height=450, 
            margin=dict(l=10, r=10, t=30, b=10),
            hovermode="x unified",
            showlegend=False, 
            xaxis=dict(
                showgrid=False,
                title="", 
                tickfont=dict(color="#64748B")
            ), 
            yaxis=dict(
                showgrid=True, 
                gridcolor="#E2E8F0",
                title="", 
                tickfont=dict(color="#64748B"),
                zeroline=False
            )
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sin datos históricos.")

with c_news:
    st.markdown(f"<div class='section-title'>Últimas Noticias de la Moneda Detectadas</div>", unsafe_allow_html=True)
    if not coin_news_df.empty:
        latest = coin_news_df.sort_values("published_at", ascending=False).head(8)
        for _, r in latest.iterrows():
            score = float(r.get("sentiment_compound", 0))
            color_badge = "🟢" if score > 0.05 else ("🔴" if score < -0.05 else "⚪")
            st.markdown(
                f'<div style="background-color:#FFFFFF; padding:10px; border-radius:8px; border:1px solid #E2E8F0; margin-bottom:10px; box-shadow: 0 1px 2px rgba(0,0,0,0.03);">'
                f'<span style="font-size:0.8rem; font-weight:bold; color:#64748B;">{color_badge} {r["sentiment_label"]} ({score:+.2f})</span><br>'
                f'<a href="{r["url"]}" target="_blank" style="color:#1E3A8A; font-weight:600; text-decoration:none; font-size:0.9rem;">{r["title"]}</a><br>'
                f'<span style="font-size:0.75rem; color:#94A3B8;">{r["source"]} · {pd.to_datetime(r["published_at"]).strftime("%d %b %H:%M")}</span>'
                f'</div>',
                unsafe_allow_html=True
            )
    else:
        st.info(f"No hay noticias recientes de {name}.")

# =========================================================
# 4. ANÁLISIS DE SENTIMIENTO
# =========================================================
st.markdown("<div class='section-title'>4. Análisis de Sentimiento en Noticias</div>", unsafe_allow_html=True)

all_news = news_cached()
coin_news_df = all_news[
    all_news['title'].str.contains(name, case=False, na=False) | 
    all_news['title'].str.contains(symbol, case=False, na=False)
].copy()

if not coin_news_df.empty:
    coin_news_df["published_at"] = pd.to_datetime(coin_news_df["published_at"], utc=True)
    coin_news_df["sentiment_compound"] = pd.to_numeric(coin_news_df["sentiment_compound"], errors="coerce")

    avg_sent = coin_news_df["sentiment_compound"].mean()
    pos_pct = (coin_news_df["sentiment_label"] == "POSITIVO").mean() * 100
    neg_pct = (coin_news_df["sentiment_label"] == "NEGATIVO").mean() * 100

    s1, s2, s3 = st.columns(3)
    s1.metric(f"Sentimiento Promedio ({symbol})", f"{avg_sent:+.3f}")
    s2.metric("Impacto Positivo", f"{pos_pct:.1f}%")
    s3.metric("Impacto Negativo", f"{neg_pct:.1f}%")


    counts = coin_news_df["sentiment_label"].value_counts().rename_axis("sentiment").reset_index(name="count")
    color_map = {"POSITIVO": "#10B981", "NEGATIVO": "#EF4444", "NEUTRAL": "#94A3B8"}
    

    fig = px.pie(
        counts, 
        names="sentiment", 
        values="count", 
        hole=0.6, 
        title=f"Distribución de Impacto para {name} ({symbol})", 
        color="sentiment", 
        color_discrete_map=color_map,
        template="plotly_white"
    )
    

    fig.update_traces(
        textinfo="percent+label", 
        textfont=dict(size=14, family="Arial", color="white")
    )
    
  
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#0F172A"),
        height=400, 
        margin=dict(t=40, b=10, l=10, r=10),
        legend=dict(
            font=dict(size=13, color="#0F172A"),
            title=dict(font=dict(size=14, color="#0F172A"))
        )
    )
    
    st.markdown("""
    <style>
    .g-gtitle text, .legendtext {
        font-weight: 700 !important;
    }
    </style>
    """, unsafe_allow_html=True)

    _, col_center, _ = st.columns([1, 2, 1])
    with col_center:
        st.plotly_chart(fig, use_container_width=True)

else:
    st.info(f"Volumen insuficiente de noticias específicas de {name} para generar el gráfico de dona.")