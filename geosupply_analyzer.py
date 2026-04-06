#!/usr/bin/env python3
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import os
import logging
import json
from datetime import datetime
from typing import Dict, List, Tuple, Optional

st.set_page_config(
    page_title="GeoSupply Rebound Analyzer",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

SAVED_LOG = "saved.log"

# ====================== SECTOR TICKERS ======================
ASX_MINING = ["BHP.AX", "RIO.AX", "FMG.AX", "S32.AX", "MIN.AX"]
ASX_SHIPPING = ["QUB.AX", "TCL.AX", "ASX.AX"]
ASX_ENERGY = ["STO.AX", "WDS.AX", "ORG.AX", "WHC.AX", "BPT.AX"]
ASX_TECH = ["WTC.AX", "XRO.AX", "TNE.AX", "NXT.AX", "REA.AX", "360.AX", "PME.AX"]
ASX_RENEW = ["ORG.AX", "AGL.AX", "IGO.AX", "IFT.AX", "MCY.AX", "CEN.AX", "MEZ.AX", "RNE.AX"]

US_MINING = ["FCX", "NEM", "VALE", "SCCO", "GOLD", "AEM"]
US_SHIPPING = ["ZIM", "MATX", "SBLK", "DAC", "CMRE"]
US_ENERGY = ["XOM", "CVX", "COP", "OXY", "CCJ"]
US_TECH = ["NVDA", "AAPL", "MSFT", "GOOGL", "AMD", "TSLA"]
US_RENEW = ["NEE", "BEPC", "CWEN", "FSLR", "ENPH"]

ALL_ASX = list(dict.fromkeys(ASX_MINING + ASX_SHIPPING + ASX_ENERGY + ASX_TECH + ASX_RENEW))
ALL_US = list(dict.fromkeys(US_MINING + US_SHIPPING + US_ENERGY + US_TECH + US_RENEW))
ALL_TICKERS = ALL_ASX + ALL_US

API_BASE = "https://api.x.ai/v1"
AVAILABLE_MODELS = ["grok-4.20-reasoning", "grok-4.20-non-reasoning", "grok-4.20-multi-agent-0309", "grok-4-1-fast-reasoning", "grok-4-1-fast-non-reasoning"]

logging.basicConfig(filename="geosupply_errors.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ====================== GROK API CALL ======================
def call_grok_api(prompt: str, model: str, temperature: float = 0.7) -> str:
    if not st.session_state.get("grok_api_key"):
        return "❌ Please enter your Grok API key in the sidebar."
    headers = {
        "Authorization": f"Bearer {st.session_state.grok_api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }
    try:
        resp = requests.post(f"{API_BASE}/chat/completions", headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logging.error(f"Grok API error: {e}")
        return f"❌ Grok API error: {str(e)}"

# ====================== POLYMARKET INTEGRATION (NEW) ======================
@st.cache_data(ttl=180)
def fetch_polymarket_markets() -> pd.DataFrame:
    """
    Fetches live Polymarket data from the public Gamma API and filters for
    GeoSupply-relevant events (energy, commodities, mining, shipping, geopolitics,
    tariffs, EV/renewables — anything that can drive rebound in your sector tickers).
    """
    try:
        url = "https://gamma-api.polymarket.com/markets"
        params = {
            "active": "true",
            "closed": "false",
            "limit": 200,          # fetch plenty so we can filter
        }
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        markets = resp.json()

        GEO_KEYWORDS = ["oil", "energy", "copper", "gold", "lithium", "shipping", "mining",
                        "tariff", "china", "ev", "renewable", "commodity", "geopolitic", "opec"]

        relevant = []
        for m in markets:
            question = m.get("question", "").lower()
            if any(kw in question for kw in GEO_KEYWORDS):
                # Safe parsing (API sometimes returns JSON strings)
                outcomes_raw = m.get("outcomes")
                prices_raw = m.get("outcomePrices")
                outcomes = json.loads(outcomes_raw) if isinstance(outcomes_raw, str) else outcomes_raw or []
                prices = json.loads(prices_raw) if isinstance(prices_raw, str) else prices_raw or []

                if len(outcomes) >= 2 and len(prices) >= 2:
                    # Most Polymarket events are binary (Yes/No). We show the first outcome prob.
                    # (You can extend this for multi-outcome later)
                    try:
                        prob_yes = float(prices[0]) * 100
                    except:
                        prob_yes = 0.0

                    volume = float(m.get("volume") or m.get("clobVolume") or m.get("liquidity") or 0)

                    relevant.append({
                        "Question": m.get("question", "N/A"),
                        "Slug": m.get("slug", ""),
                        "Primary Outcome": outcomes[0] if outcomes else "Yes",
                        "Prob %": round(prob_yes, 1),
                        "Volume (USDC)": f"${volume:,.0f}",
                        "Link": f"https://polymarket.com/{m.get('slug')}" if m.get("slug") else ""
                    })

        df = pd.DataFrame(relevant)
        if not df.empty:
            df = df.sort_values("Volume (USDC)", ascending=False).head(15)  # top 15 most traded relevant markets
        return df

    except Exception as e:
        logging.error(f"Polymarket API error: {e}")
        st.error(f"Polymarket fetch failed: {e}")
        return pd.DataFrame()

# ====================== HELPER FUNCTIONS (unchanged from v11.6) ======================
def get_data_timeframe(raw_data: Dict[str, pd.DataFrame], real_time_mode: bool, period: str) -> str:
    if not raw_data:
        return "No data loaded"
    sample_df = next(iter(raw_data.values()), pd.DataFrame())
    if sample_df.empty:
        return f"📅 {period} data"
    latest_ts = sample_df.index[-1]
    if real_time_mode:
        return f"📈 LIVE INTRA-DAY (1-minute candles) • Last price: {latest_ts.strftime('%H:%M %d %b %Y')}"
    else:
        return f"📅 {period.upper()} HISTORICAL DATA • Last close: {latest_ts.strftime('%Y-%m-%d')}"

def load_saved_analyses():
    if "saved_analyses" not in st.session_state:
        st.session_state.saved_analyses = []
        if os.path.exists(SAVED_LOG):
            try:
                with open(SAVED_LOG, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            analysis = json.loads(line)
                            if not any(a.get("timestamp") == analysis.get("timestamp") and a.get("tab") == analysis.get("tab")
                                       for a in st.session_state.saved_analyses):
                                st.session_state.saved_analyses.append(analysis)
            except Exception as e:
                st.warning(f"Could not load saved.log: {e}")
    return st.session_state.saved_analyses

def save_analysis(analysis: dict):
    try:
        os.makedirs(os.path.dirname(SAVED_LOG) or ".", exist_ok=True)
        with open(SAVED_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(analysis, ensure_ascii=False) + "\n")
        st.session_state.setdefault("saved_analyses", []).append(analysis)
        return True
    except Exception as e:
        st.error(f"Failed to save to saved.log: {e}")
        return False

def clear_all_saved_analyses():
    try:
        if os.path.exists(SAVED_LOG):
            os.remove(SAVED_LOG)
        st.session_state.saved_analyses = []
        st.success("✅ All saved analyses permanently deleted from saved.log")
        st.rerun()
    except Exception as e:
        st.error(f"Failed to clear saved.log: {e}")

def build_sector_df(tickers: List[str], raw_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for ticker in tickers:
        if ticker not in raw_data or raw_data[ticker].empty or len(raw_data[ticker]) < 15:
            continue
        df = raw_data[ticker]
        score, rsi_val, mom = calculate_rebound_score(df)
        info = get_ticker_info(ticker)
        latest = df.iloc[-1]
        prev_close = df.iloc[-2]["Close"] if len(df) > 1 else latest["Close"]
        change_pct = ((latest["Close"] / prev_close) - 1) * 100
        rows.append({
            "Ticker": ticker, "Company": info["name"], "Market": "ASX" if ".AX" in ticker else "US",
            "Currency": info["currency"], "Price": round(latest["Close"], 3),
            "Change %": round(change_pct, 2), "RSI": rsi_val,
            "Rebound Score": round(score, 1), "Momentum": mom,
            "Volume": int(latest.get("Volume", 0))
        })
    df_sector = pd.DataFrame(rows)
    if not df_sector.empty:
        df_sector = df_sector.sort_values("Rebound Score", ascending=False)
    return df_sector

def evaluate_custom_ticker(ticker: str, period: str, real_time_mode: bool) -> Tuple[Optional[pd.DataFrame], Optional[float], Optional[float], Optional[float], str]:
    if not ticker:
        return None, None, None, None, "Enter a ticker"
    try:
        custom_data = fetch_batch_data([ticker.strip().upper()], period, real_time_mode)
        if ticker not in custom_data or custom_data[ticker].empty:
            return None, None, None, None, f"❌ No data returned for {ticker}"
        df = custom_data[ticker].copy()
        if "Close" not in df.columns:
            if "Adj Close" in df.columns:
                df["Close"] = df["Adj Close"]
            else:
                return None, None, None, None, f"❌ Missing price column for {ticker}"
        score, rsi_val, mom = calculate_rebound_score(df)
        return df, score, rsi_val, mom, ""
    except Exception as e:
        return None, None, None, None, f"Error fetching {ticker}: {str(e)}"

@st.cache_data(ttl=300)
def fetch_batch_data(tickers: List[str], period: str = "6mo", real_time_mode: bool = False) -> Dict[str, pd.DataFrame]:
    if real_time_mode:
        period = "5d"
    if not tickers:
        return {}
    try:
        data = yf.download(tickers, period=period, group_by="ticker", auto_adjust=True, progress=False,
                           interval="1m" if real_time_mode else "1d")
        data_dict = {}
        for ticker in tickers:
            if len(tickers) == 1:
                df = data.copy()
            elif isinstance(data.columns, pd.MultiIndex) and ticker in data.columns.get_level_values(0):
                df = data[ticker].copy()
            else:
                continue
            df = df.dropna(how="all")
            if not df.empty:
                if "Close" not in df.columns and "Adj Close" in df.columns:
                    df["Close"] = df["Adj Close"]
                data_dict[ticker] = df
        return data_dict
    except Exception as e:
        logging.error(f"Data fetch failed: {e}")
        st.error(f"Failed to fetch market data: {e}")
        return {}

@st.cache_data(ttl=180)
def get_usd_aud_rate() -> Optional[float]:
    try:
        rate_data = yf.download("AUD=X", period="1d", progress=False)
        return float(rate_data["Close"].iloc[-1]) if not rate_data.empty else None
    except:
        return None

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period, min_periods=1).mean()
    avg_loss = loss.rolling(window=period, min_periods=1).mean()
    rs = avg_gain / avg_loss.replace(0, float('nan'))
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

def calculate_rebound_score(df: pd.DataFrame) -> Tuple[float, float, float]:
    if df.empty or len(df) < 20 or "Close" not in df.columns:
        return 0.0, 50.0, 0.0
    close = df["Close"].iloc[-1]
    rsi = calculate_rsi(df["Close"]).iloc[-1]
    rsi = max(min(rsi, 100), 0)
    rolling_high = df["Close"].rolling(window=252, min_periods=20).max().iloc[-1]
    percent_from_high = ((close - rolling_high) / rolling_high * 100) if rolling_high > 0 else -30.0
    momentum = df["Close"].pct_change(periods=10).iloc[-1] * 100
    rsi_comp = max(0, (50 - rsi) * 2.2) if rsi < 50 else max(0, (30 - rsi) * 1.5)
    high_comp = max(0, -percent_from_high * 1.8)
    mom_comp = max(0, -momentum * 1.4)
    score = rsi_comp * 0.55 + high_comp * 0.30 + mom_comp * 0.15
    return max(0, min(100, score)), round(rsi, 1), round(momentum, 2)

def create_price_rsi_chart(df: pd.DataFrame, ticker: str, company_name: str) -> go.Figure:
    if "Close" not in df.columns and "Adj Close" in df.columns:
        df = df.copy()
        df["Close"] = df["Adj Close"]
    rsi_series = calculate_rsi(df["Close"])
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, row_heights=[0.70, 0.30],
                        subplot_titles=(f"{ticker} — {company_name}", "RSI (14)"))
    fig.add_trace(go.Candlestick(x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"], name="Price"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=rsi_series, name="RSI", line=dict(color="#FF6B6B", width=2.5)), row=2, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="#FF4757", row=2, col=1, annotation_text="Overbought")
    fig.add_hline(y=30, line_dash="dash", line_color="#2ED573", row=2, col=1, annotation_text="Oversold")
    fig.update_layout(height=680, template="plotly_dark", margin=dict(l=30, r=30, t=60, b=30), legend=dict(orientation="h", y=1.05))
    fig.update_xaxes(rangeslider_visible=False)
    return fig

@st.cache_data(ttl=3600)
def get_ticker_info(ticker: str) -> Dict:
    try:
        info = yf.Ticker(ticker).info
        return {"name": info.get("longName") or info.get("shortName") or ticker.replace(".AX", ""),
                "sector": info.get("sector", "Multi-Sector"),
                "currency": "AUD" if ".AX" in ticker else "USD"}
    except:
        return {"name": ticker.replace(".AX", ""), "sector": "Resources/Tech/Energy", "currency": "AUD" if ".AX" in ticker else "USD"}

# ====================== FIXED GROK PAGE ANALYZER ======================
def add_page_analyzer(tab_name: str, page_context: str = "", raw_data: Dict = None,
                      selected_model: str = None, real_time_mode: bool = False, period: str = "6mo"):
    key_prefix = f"grok_{tab_name.lower().replace(' ', '_')}"
    if f"{key_prefix}_response" not in st.session_state:
        st.session_state[f"{key_prefix}_response"] = None
        st.session_state[f"{key_prefix}_timestamp"] = None
        st.session_state[f"{key_prefix}_user_prompt"] = None

    with st.expander("🤖 Analyse this page with Grok", expanded=False):
        st.caption(f"**{tab_name}** tab • Model: **{selected_model}** • {get_data_timeframe(raw_data or {}, real_time_mode, period)}")
        
        user_prompt = st.text_area(
            "Optional instructions to guide Grok",
            placeholder="e.g. Suggest better layout, fix bugs, or give sector strategy ideas...",
            key=f"user_prompt_{tab_name}",
            height=80
        )

        if st.button("🚀 Analyse Page with Grok", key=f"analyze_btn_{tab_name}", use_container_width=True):
            with st.spinner("Grok is analysing..."):
                full_prompt = f"""You are analysing the **'{tab_name}'** tab of the GeoSupply Rebound Analyzer v11.7.
DATA TIMEFRAME: {get_data_timeframe(raw_data or {}, real_time_mode, period)}
CURRENT PAGE CONTEXT: {page_context or "No specific data summary."}
USER REQUEST: {user_prompt or "General troubleshooting and improvement suggestions."}
TASK: 1. Bugs/UX issues 2. Actionable improvements 3. Ideas for $500 users 4. Code optimisations.
Be concise and number your suggestions."""
                
                response = call_grok_api(full_prompt, selected_model, temperature=0.7)
                
                st.session_state[f"{key_prefix}_response"] = response
                st.session_state[f"{key_prefix}_timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.session_state[f"{key_prefix}_user_prompt"] = user_prompt or "General"
                
                st.success("✅ Grok analysis complete!")

        if st.session_state.get(f"{key_prefix}_response"):
            st.markdown("### 🤖 Grok's Page Analysis")
            st.write(st.session_state[f"{key_prefix}_response"])
            
            col_save, col_clear = st.columns([3, 1])
            with col_save:
                if st.button("💾 Save this Grok Analysis to saved.log", 
                            key=f"save_btn_{tab_name}", use_container_width=True):
                    analysis = {
                        "tab": tab_name,
                        "timestamp": st.session_state[f"{key_prefix}_timestamp"],
                        "model_used": selected_model,
                        "user_prompt": st.session_state[f"{key_prefix}_user_prompt"],
                        "response": st.session_state[f"{key_prefix}_response"],
                        "data_timeframe": get_data_timeframe(raw_data or {}, real_time_mode, period)
                    }
                    if save_analysis(analysis):
                        st.success(f"✅ Saved permanently at {analysis['timestamp']}")
            
            with col_clear:
                if st.button("🗑️ Clear this analysis", key=f"clear_btn_{tab_name}"):
                    st.session_state[f"{key_prefix}_response"] = None
                    st.rerun()

# ====================== MAIN APP ======================
def main():
    load_saved_analyses()

    if "grok_api_key" not in st.session_state:
        st.session_state.grok_api_key = ""
    if "selected_model" not in st.session_state:
        st.session_state.selected_model = AVAILABLE_MODELS[0]
    if "real_time_mode" not in st.session_state:
        st.session_state.real_time_mode = False
    if "market_filter" not in st.session_state:
        st.session_state.market_filter = "Both"
    if "period" not in st.session_state:
        st.session_state.period = "6mo"

    st.title("📈 GeoSupply Rebound Analyzer")
    st.caption("**v11.7** • Polymarket live odds added • Prediction markets for energy/mining/shipping/geopolitics • Grok + rebound correlation")

    with st.sidebar:
        st.header("Controls")
        st.text_input("Grok API Key", type="password", value=st.session_state.grok_api_key, key="grok_api_key")
        
        st.selectbox("Grok Model", AVAILABLE_MODELS, index=AVAILABLE_MODELS.index(st.session_state.selected_model), key="selected_model")
        
        st.subheader("Data Options")
        st.checkbox("📈 Real-time intra-day mode (1m candles)", value=st.session_state.real_time_mode, key="real_time_mode")
        st.radio("Market Focus", ["Both", "ASX Only", "US Only"], horizontal=True, key="market_filter")
        st.selectbox("Historical Period", ["1mo", "3mo", "6mo", "1y"], index=["1mo", "3mo", "6mo", "1y"].index(st.session_state.period), key="period")
        
        st.divider()
        st.subheader("USD ↔ AUD")
        rate = get_usd_aud_rate()
        if rate:
            st.metric("1 USD =", f"{rate:.4f} AUD")
            c1, c2 = st.columns(2)
            with c1:
                usd = st.number_input("USD", value=1000.0, step=100.0, key="usd_input")
            with c2:
                st.number_input("AUD", value=round(usd * rate, 2), step=100.0, key="aud_input", disabled=True)
            st.caption(f"{usd:,.0f} USD = **{usd*rate:,.2f} AUD**")

        st.divider()
        st.info("**Rebound Score explained**  \n55% RSI (oversold) + 30% distance from 52w high + 15% momentum")
        if st.button("Refresh All Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    active_tickers = ALL_TICKERS if st.session_state.market_filter == "Both" else (ALL_ASX if st.session_state.market_filter == "ASX Only" else ALL_US)
    raw_data = fetch_batch_data(active_tickers, st.session_state.period, st.session_state.real_time_mode)
    summary_df = build_sector_df(active_tickers, raw_data)

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🌍 Dashboard (All Sectors)",
        "🧪 Simulator",
        "🧠 Strategy & Grok Insights",
        "📋 Saved Analyses",
        "🔗 IBKR AU",
        "🔮 Polymarket Insights"
    ])

    # TAB 1–5 unchanged (same as v11.6)
    with tab1:
        st.subheader("🌍 Top Rebound Opportunities — All Sectors Combined")
        st.caption(f"**Data timeframe:** {get_data_timeframe(raw_data, st.session_state.real_time_mode, st.session_state.period)}")
        
        if not summary_df.empty:
            styled = summary_df.style.format({"Price": "${:.3f}", "Change %": "{:.2f}%", "Rebound Score": "{:.1f}", "RSI": "{:.1f}"}).map(
                lambda x: "color: #2ED573; font-weight: bold" if x >= 65 else ("color: #FFC107; font-weight: bold" if x >= 45 else "color: #FF4757; font-weight: bold"),
                subset=["Rebound Score"]
            )
            st.dataframe(styled, use_container_width=True, hide_index=True)
            
            top_ticker = summary_df.iloc[0]["Ticker"]
            if top_ticker in raw_data:
                info = get_ticker_info(top_ticker)
                st.plotly_chart(create_price_rsi_chart(raw_data[top_ticker], top_ticker, info["name"]), use_container_width=True, key="dashboard_top_chart")

        st.subheader("🔍 Custom Ticker Rebound Evaluator")
        st.caption("Enter any ticker (ASX/US) → instant rebound score + chart")
        col1, col2 = st.columns([3, 1])
        with col1:
            custom_ticker = st.text_input("Ticker symbol", placeholder="e.g. AAPL, BHP.AX, TSLA, STO.AX, CCJ", value="", key="custom_ticker_input")
        with col2:
            if st.button("Evaluate Rebound", use_container_width=True, type="primary"):
                df_custom, score, rsi_val, mom, error = evaluate_custom_ticker(custom_ticker, st.session_state.period, st.session_state.real_time_mode)
                if error:
                    st.error(error)
                else:
                    info = get_ticker_info(custom_ticker)
                    st.success(f"**{custom_ticker}** — Rebound Score: **{score:.1f}** | RSI: **{rsi_val}** | Momentum: **{mom}%**")
                    st.plotly_chart(create_price_rsi_chart(df_custom, custom_ticker, info["name"]), use_container_width=True, key="custom_ticker_chart")
                    
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Latest Price", f"${df_custom['Close'].iloc[-1]:.3f}")
                    c2.metric("Rebound Score", f"{score:.1f}")
                    c3.metric("RSI (14)", f"{rsi_val}")

        context = summary_df.head(10).to_string(index=False) if not summary_df.empty else "No data"
        add_page_analyzer("Dashboard", context, raw_data,
                          st.session_state.selected_model,
                          st.session_state.real_time_mode,
                          st.session_state.period)

    with tab2:
        st.subheader("🧪 Rebound Simulator")
        st.caption(f"**Data timeframe:** {get_data_timeframe(raw_data, st.session_state.real_time_mode, st.session_state.period)} (simulator uses your custom prices)")
        col1, col2 = st.columns(2)
        with col1:
            ticker_sim = st.text_input("Ticker (for display)", value="SIM.AX")
        with col2:
            company_sim = st.text_input("Company name", value="Simulated Co")
        
        price_input = st.text_area("Price series (one per line)",
                                   placeholder="12.3\n12.5\n13.1\n...",
                                   height=150)
        
        if st.button("Calculate Rebound Score", use_container_width=True):
            try:
                prices = [float(p.strip()) for p in price_input.strip().split("\n") if p.strip()]
                if len(prices) < 10:
                    st.warning("Need at least 10 price points")
                else:
                    dates = pd.date_range(end=pd.Timestamp.today(), periods=len(prices), freq='B')
                    df_sim = pd.DataFrame({"Close": prices}, index=dates)
                    score, rsi, mom = calculate_rebound_score(df_sim)
                    st.success(f"**Rebound Score:** {score:.1f} | RSI: {rsi} | Momentum (10d %): {mom}%")
                    st.plotly_chart(create_price_rsi_chart(df_sim, ticker_sim, company_sim),
                                    use_container_width=True, key="simulator_chart")
            except Exception as e:
                st.error(f"Invalid price data: {e}")
        
        add_page_analyzer("Simulator", "Custom price input for rebound score testing", None,
                          st.session_state.selected_model,
                          st.session_state.real_time_mode,
                          st.session_state.period)

    with tab3:
        st.subheader("🧠 Strategy & Grok Insights")
        st.caption("Deep strategic analysis across all sectors using current rebound data")
        strategy_context = summary_df.to_string(index=False) if not summary_df.empty else "No data loaded yet"
        add_page_analyzer("Strategy & Grok Insights", strategy_context, raw_data,
                          st.session_state.selected_model,
                          st.session_state.real_time_mode,
                          st.session_state.period)

    with tab4:
        st.subheader("📋 Saved Grok Analyses")
        st.caption(f"{len(st.session_state.get('saved_analyses', []))} analyses stored in saved.log")
        
        if st.button("🗑️ Clear ALL saved analyses", type="secondary", use_container_width=True):
            clear_all_saved_analyses()
        
        if st.session_state.get("saved_analyses"):
            for analysis in reversed(st.session_state.saved_analyses):
                with st.expander(f"📌 {analysis['tab']} • {analysis['timestamp']} • {analysis['model_used']}"):
                    st.caption(analysis['data_timeframe'])
                    st.write(analysis['response'])
        else:
            st.info("No analyses saved yet. Analyse any page with Grok and hit 'Save'.")

    with tab5:
        st.subheader("🔗 IBKR AU (Interactive Brokers Australia)")
        st.markdown("""**Coming soon:** Direct TWS API integration for one-click orders from rebound scores.

In the meantime, use this **risk-based position sizer** (manual copy to IBKR TWS):""")
        
        col_a, col_b = st.columns(2)
        with col_a:
            account_size = st.number_input("Account Size (AUD)", value=50000.0, step=1000.0, format="%.0f")
            risk_percent = st.slider("Risk per trade (%)", min_value=0.5, max_value=3.0, value=1.0, step=0.1)
        with col_b:
            entry_price = st.number_input("Entry Price", value=10.0, step=0.01)
            stop_loss_pct = st.number_input("Stop Loss (%)", value=5.0, step=0.5)
        
        if st.button("Calculate Position Size", use_container_width=True, type="primary"):
            risk_amount = account_size * (risk_percent / 100)
            if stop_loss_pct > 0:
                risk_per_share = entry_price * (stop_loss_pct / 100)
                shares = int(risk_amount / risk_per_share)
                st.success(f"**Position:** {shares:,} shares")
                st.metric("Total risk", f"${risk_amount:,.2f} AUD")
                st.caption("✅ Paste ticker + shares into IBKR TWS → place limit order")
            else:
                st.warning("Stop loss cannot be 0%")
        
        st.info("Copy any ticker from the Dashboard and trade directly in IBKR.")
        add_page_analyzer("IBKR AU", "IBKR trading workflow and integration ideas for rebound strategy", None,
                          st.session_state.selected_model,
                          st.session_state.real_time_mode,
                          st.session_state.period)

    # ====================== NEW TAB 6: POLYMARKET ======================
    with tab6:
        st.subheader("🔮 Polymarket GeoSupply Insights")
        st.caption("Live prediction-market odds on events that move mining, energy, shipping & supply-chain stocks")
        
        if st.button("🔄 Refresh Polymarket Odds", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        
        pm_df = fetch_polymarket_markets()
        
        if not pm_df.empty:
            st.dataframe(
                pm_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Link": st.column_config.LinkColumn("Open on Polymarket", display_text="Trade →")
                }
            )
            
            st.info("**How to use:** High-probability events (e.g. oil price spikes, tariff wins) often drive rebound scores in BHP/RIO/XOM/CVX etc.")
            
            # Optional Grok analysis of Polymarket data
            context_pm = pm_df.to_string(index=False)
            add_page_analyzer(
                "Polymarket Insights",
                context_pm,
                None,
                st.session_state.selected_model,
                st.session_state.real_time_mode,
                st.session_state.period
            )
        else:
            st.warning("No GeoSupply-relevant Polymarket markets found right now or temporary API issue. Try refreshing.")

if __name__ == "__main__":
    main()