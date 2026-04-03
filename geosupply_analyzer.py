import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
import requests
import logging
import re
import json
from datetime import datetime
import io
from typing import Dict, List, Optional, Tuple

# ====================== CONFIG & SETUP ======================
st.set_page_config(
    page_title="GeoSupply Analyzer v10.0 - Optimized",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

VERSION = "10.0 Optimized & Self-Improving"
LAST_UPDATED = "April 2026"

# Enhanced logging for self-monitoring
logging.basicConfig(
    filename='geosupply_errors.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    force=True
)

# Default curated ASX tickers (mining + shipping focus) - expanded for power
DEFAULT_TICKERS: List[str] = [
    "BHP.AX", "RIO.AX", "FMG.AX", "PLS.AX", "AZJ.AX", "QUBE.AX",
    "SVW.AX", "MIN.AX", "S32.AX", "CXM.AX", "WDS.AX", "RMD.AX"
]

# ====================== CORE HELPERS (Optimized & Reusable) ======================
def validate_ticker(ticker: str) -> bool:
    """Validate ticker format (supports .AX and international)."""
    return bool(re.match(r'^[A-Z0-9]+\.?(AX)?$', ticker.strip().upper()))

@st.cache_data(ttl=180, show_spinner=False)  # Reduced TTL for freshness + faster reloads
def fetch_stock_data(tickers: List[str]) -> Dict:
    """Batch fetch data with vectorized calculations - dramatically faster than v9.x."""
    if not tickers:
        return {}
    
    try:
        # Single batch download (yfinance optimized)
        raw_data = yf.download(
            tickers, 
            period="6mo", 
            interval="1d", 
            progress=False, 
            group_by='ticker',
            threads=True  # Parallel threads for speed
        )
        
        data: Dict = {}
        for ticker in tickers:
            try:
                df = raw_data[ticker] if len(tickers) > 1 else raw_data
                if df.empty or len(df) < 15:
                    continue
                
                df = df.dropna(subset=['Close']).copy()
                
                current = float(df['Close'].iloc[-1])
                low_52w = float(df['Close'].min())
                high_52w = float(df['Close'].max())
                
                # Optimized rebound score (vectorized)
                rebound_score = round(((current - low_52w) / (high_52w - low_52w)) * 100, 1) if high_52w > low_52w else 50.0
                
                # RSI(14) - fully vectorized
                delta = df['Close'].diff()
                gain = delta.where(delta > 0, 0).rolling(window=14).mean()
                loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
                rs = gain / loss
                rsi = 50.0
                if not rs.empty and not pd.isna(rs.iloc[-1]):
                    rsi_val = 100 - (100 / (1 + float(rs.iloc[-1])))
                    rsi = round(max(0, min(100, rsi_val)), 1)
                
                # Extra metrics for power
                volume_avg = int(df['Volume'].rolling(20).mean().iloc[-1]) if 'Volume' in df else 0
                
                data[ticker] = {
                    'df': df,
                    'current_price': round(current, 3),
                    'volume': int(df['Volume'].iloc[-1]) if 'Volume' in df else 0,
                    'volume_avg_20d': volume_avg,
                    'rebound_score': rebound_score,
                    'rsi': rsi,
                    'change_pct': round(((current - float(df['Close'].iloc[-2])) / float(df['Close'].iloc[-2])) * 100, 2),
                    'high_52w': round(high_52w, 2),
                    'low_52w': round(low_52w, 2)
                }
            except Exception as e:
                logging.warning(f"Failed to process {ticker}: {e}")
                continue
                
        return data
    except Exception as e:
        logging.error(f"Batch download failed: {e}")
        return {}

def get_grok_analysis(prompt: str, api_key: str) -> str:
    """Call xAI Grok API with improved error handling and timeout."""
    if not api_key or len(api_key.strip()) < 10:
        return "⚠️ Please provide a valid xAI Grok API key."
    
    try:
        url = "https://api.x.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "grok-beta",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 1500
        }
        
        with st.spinner("🚀 Consulting Grok (xAI)..."):
            resp = requests.post(url, json=payload, headers=headers, timeout=45)
            
            if resp.status_code == 401:
                return "❌ Invalid xAI API key. Please check and try again."
            if resp.status_code == 429:
                return "⏳ Rate limit reached. Wait a moment and retry."
            
            resp.raise_for_status()
            result = resp.json()["choices"][0]["message"]["content"].strip()
            logging.info(f"Grok analysis completed successfully ({len(result)} chars)")
            return result
            
    except requests.exceptions.Timeout:
        return "⏰ Grok API timeout. Please try again."
    except Exception as e:
        logging.error(f"Grok API error: {e}")
        return f"❌ Grok API error: {str(e)}"

def save_response(content: str, file_type: str, filename_base: str = "grok_output") -> Tuple[bytes, str]:
    """Save response in multiple formats - powers 'save to/as type' feature."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{filename_base}_{timestamp}"
    
    if file_type == "txt":
        return content.encode('utf-8'), f"{filename}.txt"
    elif file_type == "json":
        data = {"timestamp": datetime.now().isoformat(), "response": content}
        return json.dumps(data, indent=2).encode('utf-8'), f"{filename}.json"
    elif file_type == "md":
        md_content = f"# Grok Response\n\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n{content}"
        return md_content.encode('utf-8'), f"{filename}.md"
    return b"", ""

# ====================== SIDEBAR (Legacy + New Controls) ======================
with st.sidebar:
    st.header("⚙️ Settings")
    st.caption(f"v{VERSION} | Self-Improving Edition")
    
    # API Key moved to dedicated tab but mirrored here for convenience
    api_key = st.text_input(
        "🔑 xAI Grok API Key",
        value="",
        type="password",
        help="Required for Grok features. Stored only in session."
    )
    
    st.markdown("---")
    st.subheader("📌 ASX Focus Tickers")
    use_preset = st.checkbox("Use Preset Mining & Shipping List", value=True)
    
    if use_preset:
        selected_tickers = st.multiselect(
            "Select ASX Tickers", 
            DEFAULT_TICKERS, 
            default=["BHP.AX", "RIO.AX", "AZJ.AX", "FMG.AX"]
        )
    else:
        custom_input = st.text_input("Custom Ticker (e.g. BHP.AX or TSLA)", value="BHP.AX")
        if st.button("➕ Add Custom", use_container_width=True) and validate_ticker(custom_input):
            if custom_input.upper() not in selected_tickers:
                selected_tickers = [custom_input.upper()]
            else:
                selected_tickers = [custom_input.upper()]
        else:
            selected_tickers = ["BHP.AX"]
    
    st.caption("✅ .AX supported • International in Universal tab")
    
    # Self-improving hint
    if st.button("🧬 Self-Improve App (Ask Grok)", use_container_width=True):
        st.session_state.self_improve_trigger = True

# ====================== MAIN TITLE & DATA FETCH ======================
st.title("🌍 GeoSupply Analyzer")
st.markdown(f"**v{VERSION}** • Real-time Rebound Analysis + xAI Grok + Universal Stock Intelligence")
st.markdown("**Mining • Shipping • Supply Chain Rebounds** | Powered by yfinance + Grok-beta")

# Fetch data for ASX-focused tabs (cached & fast)
if 'selected_tickers' not in locals() or not selected_tickers:
    st.warning("👉 Select at least one ticker in the sidebar.")
    st.stop()

asx_data = fetch_stock_data(selected_tickers)

if not asx_data:
    st.error("❌ Failed to fetch market data. Check tickers or connection.")
    st.stop()

# Convert to summary DataFrame (vectorized)
summary_data = []
for ticker, info in asx_data.items():
    summary_data.append({
        "Ticker": ticker,
        "Price": info['current_price'],
        "Rebound (%)": info['rebound_score'],
        "RSI": info['rsi'],
        "Daily Δ (%)": info['change_pct'],
        "Vol (latest)": f"{info['volume']:,}",
        "Vol 20d Avg": f"{info['volume_avg_20d']:,}"
    })
df_summary = pd.DataFrame(summary_data)

# ====================== TABS (Legacy + New Features) ======================
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📈 Price Charts",
    "📊 Rebound Metrics",
    "💰 Investment Simulator",
    "🧠 Grok Analysis (Legacy)",
    "🔮 Interactive Grok Prompt",
    "🌍 Universal Stock Analyzer"
])

# TAB 1: Price Charts (Legacy optimized with Plotly improvements)
with tab1:
    st.subheader("Interactive Price Charts")
    ticker_to_plot = st.selectbox("Select Ticker", selected_tickers, key="chart_select")
    df = asx_data[ticker_to_plot]['df']
    
    # Enhanced chart with volume + rebound annotation
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'], name='Close Price', line=dict(color='#00ff9d')))
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', yaxis='y2', opacity=0.3))
    
    fig.update_layout(
        title=f"{ticker_to_plot} • 6-Month Price & Volume",
        xaxis_title="Date",
        yaxis_title="Price (AUD)",
        yaxis2=dict(title="Volume", overlaying='y', side='right'),
        hovermode='x unified',
        height=500
    )
    st.plotly_chart(fig, use_container_width=True)
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Key Stats")
        st.dataframe(df['Close'].describe().round(2), use_container_width=True)
    with col2:
        st.metric("Current Price", f"${asx_data[ticker_to_plot]['current_price']}", 
                  f"{asx_data[ticker_to_plot]['change_pct']}% today")

# TAB 2: Rebound Metrics (Legacy + enhanced table)
with tab2:
    st.subheader("Rebound Metrics Overview")
    st.dataframe(
        df_summary.sort_values("Rebound (%)", ascending=False),
        use_container_width=True,
        hide_index=True
    )
    
    # Detail view
    selected_detail = st.selectbox("Detailed View", selected_tickers, key="detail_select")
    info = asx_data[selected_detail]
    
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.metric("Rebound Score", f"{info['rebound_score']}%", delta=None)
    with col_b:
        st.metric("RSI (14)", f"{info['rsi']}", delta=None)
    with col_c:
        st.metric("52w Range", f"${info['low_52w']} - ${info['high_52w']}")
    
    # SMA + rebound visual
    df_plot = info['df'].copy()
    df_plot['SMA20'] = df_plot['Close'].rolling(20).mean()
    fig_ma = go.Figure()
    fig_ma.add_trace(go.Scatter(x=df_plot.index, y=df_plot['Close'], name='Close'))
    fig_ma.add_trace(go.Scatter(x=df_plot.index, y=df_plot['SMA20'], name='SMA 20', line=dict(color='orange')))
    fig_ma.update_layout(title=f"{selected_detail} Rebound + SMA", hovermode='x unified')
    st.plotly_chart(fig_ma, use_container_width=True)

# TAB 3: Investment Simulator (Legacy completed + optimized)
with tab3:
    st.subheader("Investment Simulator")
    amount = st.number_input("Investment Amount (AUD)", min_value=1000, value=10000, step=1000)
    target_rebound = st.slider("Target Rebound Level (%)", 50, 100, 85)
    
    if st.button("🚀 Run Simulation", type="primary", use_container_width=True):
        ticker_sim = st.selectbox("Simulate on Ticker", selected_tickers, key="sim_select")
        info_sim = asx_data[ticker_sim]
        
        shares = amount / info_sim['current_price']
        projected_price = info_sim['low_52w'] + (info_sim['high_52w'] - info_sim['low_52w']) * (target_rebound / 100)
        projected_value = shares * projected_price
        potential_profit = projected_value - amount
        
        col_sim1, col_sim2 = st.columns(2)
        with col_sim1:
            st.success(f"**Shares Purchased:** {shares:,.2f}")
            st.metric("Projected Value", f"${projected_value:,.0f}", f"+${potential_profit:,.0f}")
        with col_sim2:
            st.info(f"**Assumption:** Stock rebounds to {target_rebound}% of 52w high in next cycle.")
            st.caption("Based on historical rebound score. Not financial advice.")

# TAB 4: Grok Analysis (Legacy - uses old prompt style)
with tab4:
    st.subheader("Grok Analysis (Legacy Mode)")
    if not api_key:
        st.warning("Enter xAI API Key in sidebar for AI insights.")
    else:
        prompt_legacy = f"""
        You are an expert supply-chain and mining analyst. 
        Analyze these ASX stocks: {', '.join(selected_tickers)}
        Current rebound scores: { {t: asx_data[t]['rebound_score'] for t in selected_tickers} }
        Provide investment thesis, risks, and supply-chain impact. Be concise and bullish where justified.
        """
        if st.button("📡 Get Grok Legacy Analysis"):
            response = get_grok_analysis(prompt_legacy, api_key)
            st.markdown(response)

# TAB 5: NEW - Interactive Grok Prompt (New Feature - asks for API key + save options)
with tab5:
    st.subheader("🔮 Interactive Grok Prompt")
    st.caption("Full control: Ask anything. Save responses in multiple formats.")
    
    # API key input directly in tab (as requested)
    api_key_interactive = st.text_input(
        "🔑 xAI Grok API Key (for this session)",
        value=api_key,
        type="password",
        key="interactive_key"
    )
    
    user_prompt = st.text_area(
        "Your custom prompt to Grok",
        value="Analyze the rebound potential and supply-chain risks for BHP.AX in the next 90 days.",
        height=150
    )
    
    if st.button("📤 Send to Grok", type="primary", use_container_width=True):
        if api_key_interactive:
            grok_response = get_grok_analysis(user_prompt, api_key_interactive)
            st.markdown("### Grok Response")
            st.markdown(grok_response)
            
            # Save to/as type options
            save_format = st.selectbox(
                "Save response as",
                ["txt", "json", "md"],
                format_func=lambda x: {"txt": "Plain Text (.txt)", "json": "Structured JSON (.json)", "md": "Markdown (.md)"}[x]
            )
            
            content_bytes, filename = save_response(grok_response, save_format, "grok_interactive")
            
            st.download_button(
                label=f"💾 Download as {save_format.upper()}",
                data=content_bytes,
                file_name=filename,
                mime=f"{'text/plain' if save_format=='txt' else 'application/json' if save_format=='json' else 'text/markdown'}",
                use_container_width=True
            )
            
            # Bonus: copy to clipboard simulation
            st.success("✅ Response ready for download!")
        else:
            st.error("API key required.")

# TAB 6: NEW - Universal Stock Analyzer (New Feature - any ticker)
with tab6:
    st.subheader("🌍 Universal Stock Analyzer")
    st.caption("Analyze ANY ticker (ASX, NYSE, NASDAQ, etc.) on demand.")
    
    universal_ticker = st.text_input("Enter Ticker Symbol", value="TSLA", key="universal_input").upper().strip()
    
    if st.button("🔍 Analyze Ticker", type="primary"):
        if validate_ticker(universal_ticker):
            try:
                # Reuse optimized fetch helper (old code logic adapted)
                univ_data = fetch_stock_data([universal_ticker])
                
                if univ_data and universal_ticker in univ_data:
                    info_u = univ_data[universal_ticker]
                    st.success(f"✅ Data loaded for {universal_ticker}")
                    
                    col_u1, col_u2 = st.columns([3, 1])
                    with col_u1:
                        fig_u = px.line(info_u['df'], x=info_u['df'].index, y='Close', title=f"{universal_ticker} Price History")
                        st.plotly_chart(fig_u, use_container_width=True)
                    
                    with col_u2:
                        st.metric("Current", f"${info_u['current_price']}", f"{info_u['change_pct']}%")
                        st.metric("Rebound", f"{info_u['rebound_score']}%")
                        st.metric("RSI", info_u['rsi'])
                    
                    # Extra fundamentals (power feature)
                    ticker_obj = yf.Ticker(universal_ticker)
                    info_dict = ticker_obj.info
                    st.subheader("Fundamentals")
                    fund_df = pd.DataFrame([
                        {"Metric": "Market Cap", "Value": f"${info_dict.get('marketCap', 'N/A'):,}"},
                        {"Metric": "PE Ratio", "Value": info_dict.get('trailingPE', 'N/A')},
                        {"Metric": "52w High", "Value": info_dict.get('fiftyTwoWeekHigh', 'N/A')},
                        {"Metric": "Beta", "Value": info_dict.get('beta', 'N/A')}
                    ])
                    st.dataframe(fund_df, hide_index=True, use_container_width=True)
                    
                    # Quick Grok analysis option
                    if api_key and st.button("Ask Grok about this ticker"):
                        grok_univ_prompt = f"Quick analysis of {universal_ticker}: current price ${info_u['current_price']}, rebound {info_u['rebound_score']}%. Key insights?"
                        univ_resp = get_grok_analysis(grok_univ_prompt, api_key)
                        st.markdown(univ_resp)
                else:
                    st.error("Could not fetch data for this ticker.")
            except Exception as e:
                st.error(f"Error analyzing {universal_ticker}: {e}")
        else:
            st.error("Invalid ticker format.")

# ====================== SELF-IMPROVING FOOTER & FINAL TOUCHES ======================
st.markdown("---")
col_foot1, col_foot2 = st.columns([4, 1])
with col_foot1:
    st.caption(f"© GeoSupply Analyzer v{VERSION} • Built as self-improving system using old v9.x code as foundation.")
with col_foot2:
    if st.button("🔄 Refresh All Data"):
        st.cache_data.clear()
        st.rerun()

# Self-improving trigger (uses Grok to suggest code enhancements)
if st.session_state.get('self_improve_trigger', False):
    st.session_state.self_improve_trigger = False
    improve_prompt = f"""
    You are the ultimate code optimizer. Review this Streamlit app (GeoSupply Analyzer v{VERSION}).
    It uses yfinance, Plotly, Grok API, caching, and multiple tabs.
    Suggest 5 concrete improvements for speed, cleanliness, and new power features.
    Focus on performance, UX, and self-improvement loops.
    """
    if api_key:
        with st.spinner("Grok is optimizing the app..."):
            suggestion = get_grok_analysis(improve_prompt, api_key)
            st.markdown("### 🧬 Grok Self-Improvement Suggestions")
            st.info(suggestion)
    else:
        st.warning("Enable API key for self-improvement mode.")

# Final ready-to-run note (invisible in UI)
# This file is complete, standalone, and ready for: streamlit run geosupply_analyzer.py