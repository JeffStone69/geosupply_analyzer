import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
import requests
import logging
import re
from datetime import datetime

# ====================== CONFIG ======================
st.set_page_config(
    page_title="GeoSupply Rebound Analyzer v9.3 Secure",
    page_icon="⚓",
    layout="wide"
)

VERSION = "9.3 Secure"
LAST_UPDATED = "April 2026"

# Logging
logging.basicConfig(
    filename='geosupply_errors.log',
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s',
    force=True
)

# Default curated ASX tickers (mining + shipping focus)
DEFAULT_TICKERS = ["BHP.AX", "RIO.AX", "FMG.AX", "PLS.AX", "AZJ.AX", "QUBE.AX", "SVW.AX", "MIN.AX", "S32.AX"]

# ====================== HELPERS ======================
def validate_asx_ticker(ticker: str) -> bool:
    return bool(re.match(r'^[A-Z0-9]+\.AX$', ticker.strip().upper()))

@st.cache_data(ttl=300)
def fetch_asx_data(tickers: list):
    data = {}
    try:
        raw = yf.download(tickers, period="6mo", interval="1d", progress=False, group_by='ticker')
        for ticker in tickers:
            try:
                df = raw[ticker] if len(tickers) > 1 else raw
                if df.empty or len(df) < 10:
                    continue
                df = df.dropna(subset=['Close'])
                current = float(df['Close'].iloc[-1])
                low_52w = float(df['Close'].min())
                high_52w = float(df['Close'].max())
                rebound_score = round(((current - low_52w) / (high_52w - low_52w)) * 100, 1) if high_52w > low_52w else 50.0

                # RSI(14)
                delta = df['Close'].diff()
                gain = delta.where(delta > 0, 0).rolling(window=14).mean()
                loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
                rs = gain / loss
                rsi = 50.0
                if not rs.empty and not pd.isna(rs.iloc[-1]):
                    rsi_val = 100 - (100 / (1 + float(rs.iloc[-1])))
                    rsi = round(max(0, min(100, rsi_val)), 1)

                data[ticker] = {
                    'df': df,
                    'current_price': round(current, 3),
                    'volume': int(df['Volume'].iloc[-1]) if 'Volume' in df else 0,
                    'rebound_score': rebound_score,
                    'rsi': rsi,
                    'change_pct': round(((current - float(df['Close'].iloc[-2])) / float(df['Close'].iloc[-2])) * 100, 2)
                }
            except Exception as e:
                logging.warning(f"Failed to process {ticker}: {e}")
                continue
    except Exception as e:
        logging.error(f"Batch download failed: {e}")
    
    return data or {}

def get_grok_analysis(prompt: str, api_key: str) -> str:
    if not api_key:
        return "⚠️ xAI API key not provided."
    try:
        url = "https://api.x.ai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": "grok-beta",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 1200
        }
        with st.spinner("Consulting Grok..."):
            resp = requests.post(url, json=payload, headers=headers, timeout=40)
            if resp.status_code == 401:
                return "❌ Invalid xAI API key."
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logging.error(f"Grok API error: {e}")
        return f"❌ Grok API error: {str(e)}"

# ====================== SIDEBAR ======================
with st.sidebar:
    st.header("⚙️ Settings")
    
    # API Key (secure handling)
    api_key = st.text_input(
        "xAI Grok API Key (optional)",
        value="",
        type="password",
        help="For AI narrative analysis. Use st.secrets in production deployments."
    )
    
    st.markdown("---")
    st.subheader("Tickers")
    use_preset = st.checkbox("Use Preset ASX List", value=True)
    if use_preset:
        selected_tickers = st.multiselect("Select Tickers", DEFAULT_TICKERS, default=["BHP.AX", "RIO.AX", "AZJ.AX"])
    else:
        custom = st.text_input("Custom Ticker (e.g. BHP.AX)", value="BHP.AX")
        if st.button("Add Custom") and validate_asx_ticker(custom):
            selected_tickers = [custom.upper()]
        else:
            selected_tickers = ["BHP.AX"]
    
    st.caption("Only .AX tickers supported")

# ====================== MAIN APP ======================
st.title("GeoSupply Rebound Analyzer v9.3 Secure")
st.markdown("**ASX Mining & Shipping Rebound Analysis** with RSI + 52-week recovery scoring.")

if 'selected_tickers' not in locals() or not selected_tickers:
    st.warning("Please select at least one ticker.")
    st.stop()

data_dict = fetch_asx_data(selected_tickers)

if not data_dict:
    st.error("Failed to fetch any data. Try different tickers.")
    st.stop()

# Convert to summary DataFrame
summary = []
for ticker, info in data_dict.items():
    summary.append({
        "Ticker": ticker,
        "Current Price": info['current_price'],
        "Rebound Score (%)": info['rebound_score'],
        "RSI (14)": info['rsi'],
        "Daily Change (%)": info['change_pct'],
        "Volume": f"{info['volume']:,}"
    })
df_summary = pd.DataFrame(summary)

tab1, tab2, tab3, tab4 = st.tabs(["📊 Price Charts", "📈 Rebound Metrics", "💰 Investment Simulator", "🤖 Grok Analysis"])

with tab1:
    ticker_to_plot = st.selectbox("Select Ticker for Detailed Chart", selected_tickers)
    df = data_dict[ticker_to_plot]['df']
    
    fig = px.line(df, x=df.index, y='Close', title=f"{ticker_to_plot} - Closing Price")
    fig.update_layout(hovermode='x unified')
    st.plotly_chart(fig, use_container_width=True)
    
    st.subheader("Statistics")
    st.dataframe(df['Close'].describe(), use_container_width=True)

with tab2:
    st.subheader("Rebound Metrics Overview")
    st.dataframe(df_summary.sort_values("Rebound Score (%)", ascending=False), use_container_width=True, hide_index=True)
    
    # Detailed view
    selected_detail = st.selectbox("Detailed View", selected_tickers, key="detail")
    info = data_dict[selected_detail]
    st.metric("Rebound Score", f"{info['rebound_score']}%", 
              f"RSI: {info['rsi']}")
    
    # Simple MA for visual rebound confirmation
    df_plot = info['df'].copy()
    df_plot['SMA20'] = df_plot['Close'].rolling(20).mean()
    fig_ma = go.Figure()
    fig_ma.add_trace(go.Scatter(x=df_plot.index, y=df_plot['Close'], name='Close'))
    fig_ma.add_trace(go.Scatter(x=df_plot.index, y=df_plot['SMA20'], name='20-day SMA', line=dict(color='orange')))
    fig_ma.update_layout(title=f"{selected_detail} with SMA", hovermode='x unified')
    st.plotly_chart(fig_ma, use_container_width=True)

with tab3:
    st.subheader("Investment Simulator")
    amount = st.number_input("Investment Amount (AUD)", min_value=1000, value=10000, step=1000)
    
    if st.button("Run Simulation"):
        st.info("Simulation logic coming in next update (portfolio projection based on rebound scores).")
        # Placeholder for future simulator expansion
        projected = amount * 1.15  # dummy 15% upside example
        st.success(f"Projected value in 6 months (optimistic): ${projected:,.0f} AUD")

with tab4:
    st.subheader("🤖 Grok Analysis")
    if api_key:
        prompt = f"Analyze these ASX mining/shipping stocks for rebound potential: {', '.join(selected_tickers)}. Current rebound scores: {[data_dict[t]['rebound_score'] for t in selected_tickers]}. Provide market insights, risks, and opportunities."
        analysis = get_grok_analysis(prompt, api_key)
        st.markdown(analysis)
    else:
        st.info("Enter your xAI Grok API key in the sidebar for AI-powered insights.")

st.caption(f"GeoSupply Rebound Analyzer v{VERSION} | Last updated: {LAST_UPDATED} | Data from yfinance • Powered by Grok (xAI)")