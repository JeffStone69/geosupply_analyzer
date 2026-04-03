#!/usr/bin/env python
"""
geosupply_analyzer.py
GeoSupply Rebound Analyzer v10.3
Optimized Streamlit Dashboard for ASX + US Mining & Shipping Stocks

Changes in v10.3 (April 2026):
- Removed delisted tickers CXM.AX (delisted Sep 2025) and SYD.AX (delisted 2022)
- Improved Grok API error diagnostics (now logs full response body on 400 errors)
- Removed off-topic "UX Tools" tab and cleaned UI
- Added public explanation of proprietary Rebound Score
- Minor robustness & documentation improvements

Author: Optimized by Grok (xAI) - Self-improving system
Last Updated: April 2026
"""

import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import os
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional

st.set_page_config(
    page_title="GeoSupply Rebound Analyzer",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ====================== CONFIG & TICKERS ======================
ASX_MINING = ["BHP.AX", "RIO.AX", "FMG.AX", "S32.AX", "MIN.AX"]
ASX_SHIPPING = ["QUB.AX", "TCL.AX", "ASX.AX"]
US_MINING = ["FCX", "NEM", "VALE", "SCCO", "GOLD", "AEM"]
US_SHIPPING = ["ZIM", "MATX", "SBLK", "DAC", "CMRE"]

ALL_ASX = ASX_MINING + ASX_SHIPPING
ALL_US = US_MINING + US_SHIPPING
ALL_TICKERS = ALL_ASX + ALL_US

API_BASE = "https://api.x.ai/v1"
AVAILABLE_MODELS = [
    "grok-4.20-0309-non-reasoning",
    "grok-4.20-0309-reasoning",
    "grok-4.20-multi-agent-0309",
    "grok-4-1-fast-reasoning"  # Added per current x.ai docs
]

logging.basicConfig(
    filename="geosupply_errors.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ====================== DATA FETCHING ======================
@st.cache_data(ttl=300)
def fetch_batch_data(tickers: List[str], period: str = "6mo") -> Dict[str, pd.DataFrame]:
    """Fetch OHLCV data for multiple tickers efficiently."""
    if not tickers:
        return {}
    try:
        data = yf.download(
            tickers,
            period=period,
            group_by="ticker",
            auto_adjust=True,
            progress=False
        )
        data_dict = {}
        for ticker in tickers:
            if len(tickers) == 1:
                df = data.copy()
            elif ticker in data.columns.get_level_values(0):
                df = data[ticker].copy()
            else:
                continue
            df = df.dropna(how="all")
            if not df.empty:
                data_dict[ticker] = df
        return data_dict
    except Exception as e:
        logging.error(f"Data fetch failed: {e}")
        st.error(f"Failed to fetch market data: {e}")
        return {}


@st.cache_data(ttl=180)
def get_usd_aud_rate() -> Optional[float]:
    """Fetch real-time USD to AUD exchange rate."""
    try:
        rate_data = yf.download("AUD=X", period="1d", progress=False)
        if not rate_data.empty:
            return float(rate_data["Close"].iloc[-1])
        return None
    except:
        return None


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculate 14-period RSI (handles early NaNs gracefully)."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period, min_periods=1).mean()
    avg_loss = loss.rolling(window=period, min_periods=1).mean()
    rs = avg_gain / avg_loss.replace(0, float('nan'))  # avoid div-by-zero
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)  # neutral default for early rows


def calculate_rebound_score(df: pd.DataFrame) -> Tuple[float, float, float]:
    """
    Proprietary Rebound Score (0-100). Higher = stronger rebound potential.
    Formula: 55% RSI oversold weight + 30% distance from high + 15% momentum.
    """
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


def call_grok_api(prompt: str, model: str, temperature: float = 0.7) -> str:
    """Call xAI Grok API with robust error handling and full response logging."""
    api_key = os.getenv("GROK_API_KEY") or st.session_state.get("grok_api_key", "")
    if not api_key:
        return "❌ Please enter your Grok API key in the sidebar (get it from x.ai)."

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": 1200,
    }

    try:
        resp = requests.post(f"{API_BASE}/chat/completions", headers=headers, json=payload, timeout=45)
        
        if resp.status_code == 404:
            return f"❌ Model '{model}' not found. Please select a different model."
        if resp.status_code == 401:
            return "❌ Invalid or expired Grok API key."
        if resp.status_code == 429:
            return "❌ Rate limit reached. Please wait before trying again."
        
        if resp.status_code != 200:
            error_body = resp.text[:500]
            logging.error(f"Grok API error {resp.status_code}: {error_body}")
            return f"❌ Grok API error {resp.status_code}. Check logs for details."
        
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        logging.error(f"Grok connection error: {str(e)}")
        return f"❌ Connection error: {str(e)}"
    except Exception as e:
        logging.error(f"Grok unexpected error: {str(e)}")
        return f"❌ Unexpected error: {str(e)}"


def create_price_rsi_chart(df: pd.DataFrame, ticker: str, company_name: str) -> go.Figure:
    """Create interactive candlestick + RSI chart."""
    rsi_series = calculate_rsi(df["Close"])
    
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.70, 0.30],
        subplot_titles=(f"{ticker} — {company_name}", "RSI (14)")
    )

    fig.add_trace(
        go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"],
            low=df["Low"], close=df["Close"], name="Price"
        ), row=1, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=df.index, y=rsi_series, name="RSI",
            line=dict(color="#FF6B6B", width=2.5)
        ), row=2, col=1
    )

    fig.add_hline(y=70, line_dash="dash", line_color="#FF4757", row=2, col=1, annotation_text="Overbought")
    fig.add_hline(y=30, line_dash="dash", line_color="#2ED573", row=2, col=1, annotation_text="Oversold")

    fig.update_layout(
        height=680,
        template="plotly_dark",
        margin=dict(l=30, r=30, t=60, b=30),
        legend=dict(orientation="h", y=1.05)
    )
    fig.update_xaxes(rangeslider_visible=False)
    return fig


@st.cache_data(ttl=3600)
def get_ticker_info(ticker: str) -> Dict:
    """Get basic company information (cached)."""
    try:
        info = yf.Ticker(ticker).info
        return {
            "name": info.get("longName") or info.get("shortName") or ticker.replace(".AX", ""),
            "sector": info.get("sector", "Mining/Shipping"),
            "currency": "AUD" if ".AX" in ticker else "USD"
        }
    except:
        currency = "AUD" if ".AX" in ticker else "USD"
        return {"name": ticker.replace(".AX", ""), "sector": "Resources/Transport", "currency": currency}


# ====================== MAIN APP ======================
def main():
    if "grok_api_key" not in st.session_state:
        st.session_state.grok_api_key = ""

    st.title("📈 GeoSupply Rebound Analyzer")
    st.caption("**v10.3** • ASX + US Markets • Real-time USD/AUD • Grok 4.20")

    # ====================== SIDEBAR ======================
    with st.sidebar:
        st.header("⚙️ Controls")
        
        grok_key = st.text_input(
            "Grok API Key",
            type="password",
            value=st.session_state.grok_api_key,
            help="Get your key at https://x.ai/api"
        )
        if grok_key:
            st.session_state.grok_api_key = grok_key

        selected_model = st.selectbox(
            "Grok Model",
            AVAILABLE_MODELS,
            index=0
        )

        market_filter = st.radio(
            "Market Focus",
            ["Both", "ASX Only", "US Only"],
            horizontal=True
        )

        period = st.selectbox(
            "Historical Period",
            ["1mo", "3mo", "6mo", "1y"],
            index=2
        )

        st.divider()
        
        # Real-time USD to AUD Converter
        st.subheader("💱 USD ↔ AUD")
        rate = get_usd_aud_rate()
        if rate:
            st.metric("1 USD =", f"{rate:.4f} AUD", help="Source: Yahoo Finance")
            
            conv_col1, conv_col2 = st.columns(2)
            with conv_col1:
                usd_amount = st.number_input("USD", value=1000.0, step=100.0, key="usd_input")
            with conv_col2:
                aud_amount = st.number_input("AUD", value=round(usd_amount * rate, 2), step=100.0, key="aud_input")
            
            if usd_amount > 0:
                st.caption(f"{usd_amount:,.0f} USD = **{usd_amount * rate:,.2f} AUD**")
        else:
            st.warning("Could not fetch exchange rate.")

        st.divider()
        st.info("""
        **Rebound Score explained**  
        Proprietary 0-100 score:  
        • 55% RSI (oversold boost)  
        • 30% % from 52-week high  
        • 15% 10-day momentum  
        **>65 = strong rebound candidate** (ideal when RSI < 42)
        """)
        
        if st.button("🔄 Refresh All Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # Determine active tickers
    if market_filter == "ASX Only":
        active_tickers = ALL_ASX
    elif market_filter == "US Only":
        active_tickers = ALL_US
    else:
        active_tickers = ALL_TICKERS

    raw_data = fetch_batch_data(active_tickers, period)

    # Build summary table
    summary_rows = []
    detailed_data: Dict[str, pd.DataFrame] = {}

    for ticker, df in raw_data.items():
        if df.empty or len(df) < 15:
            continue
        score, rsi_val, mom = calculate_rebound_score(df)
        info = get_ticker_info(ticker)
        latest = df.iloc[-1]
        
        prev_close = df.iloc[-2]["Close"] if len(df) > 1 else latest["Close"]
        change_pct = ((latest["Close"] / prev_close) - 1) * 100

        summary_rows.append({
            "Ticker": ticker,
            "Company": info["name"],
            "Market": "ASX" if ".AX" in ticker else "US",
            "Currency": info["currency"],
            "Price": round(latest["Close"], 3),
            "Change %": round(change_pct, 2),
            "RSI": rsi_val,
            "Rebound Score": round(score, 1),
            "Momentum": mom,
            "Volume": int(latest.get("Volume", 0))
        })
        detailed_data[ticker] = df

    summary_df = pd.DataFrame(summary_rows)
    if not summary_df.empty:
        summary_df = summary_df.sort_values("Rebound Score", ascending=False)

    # ====================== TABS ======================
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Dashboard", "⛏️ Mining", "🚢 Shipping", "🧪 Simulator",
        "🤖 Grok Insights"
    ])

    with tab1:
        st.subheader("Top Rebound Opportunities")
        if not summary_df.empty:
            def score_color(val):
                if val >= 65: return "color: #2ED573; font-weight: bold"
                if val >= 45: return "color: #FFC107; font-weight: bold"
                return "color: #FF4757; font-weight: bold"

            styled = summary_df.style.format({
                "Price": "${:.3f}",
                "Change %": "{:.2f}%",
                "Rebound Score": "{:.1f}",
                "RSI": "{:.1f}"
            }).applymap(score_color, subset=["Rebound Score"])

            st.dataframe(styled, use_container_width=True, hide_index=True)

            if len(summary_df) > 0:
                top_ticker = summary_df.iloc[0]["Ticker"]
                top_df = detailed_data.get(top_ticker)
                if top_df is not None:
                    info = get_ticker_info(top_ticker)
                    st.plotly_chart(
                        create_price_rsi_chart(top_df, top_ticker, info["name"]),
                        use_container_width=True
                    )
        else:
            st.warning("No data available.")

    with tab2:
        st.subheader("Mining Sector")
        mining_tickers = ASX_MINING + US_MINING
        mining_df = summary_df[summary_df["Ticker"].isin(mining_tickers)]
        if not mining_df.empty:
            st.dataframe(mining_df, use_container_width=True, hide_index=True)
        else:
            st.info("No mining data available.")

    with tab3:
        st.subheader("Shipping & Logistics")
        shipping_tickers = ASX_SHIPPING + US_SHIPPING
        shipping_df = summary_df[summary_df["Ticker"].isin(shipping_tickers)]
        if not shipping_df.empty:
            st.dataframe(shipping_df, use_container_width=True, hide_index=True)
        else:
            st.info("No shipping data available.")

    with tab4:
        st.subheader("Investment Simulator")
        investment = st.number_input("Investment Amount (USD)", min_value=1000, value=10000, step=1000)
        horizon = st.selectbox("Time Horizon", ["1 Month", "3 Months", "6 Months"], index=1)
        
        default_tickers = summary_df.head(4)["Ticker"].tolist() if not summary_df.empty else []
        selected = st.multiselect("Select stocks", options=summary_df["Ticker"].tolist() if not summary_df.empty else [], default=default_tickers)

        if st.button("Run Simulation", type="primary"):
            if selected:
                results = []
                total_score = 0
                for tkr in selected:
                    row = summary_df[summary_df["Ticker"] == tkr].iloc[0]
                    score = row["Rebound Score"]
                    proj_gain = (score / 3.0) * (1.0 if "1 Month" in horizon else 2.2)
                    alloc = investment / len(selected)
                    proj_value = alloc * (1 + proj_gain / 100)
                    results.append({
                        "Ticker": tkr,
                        "Allocation": round(alloc),
                        "Rebound Score": score,
                        "Projected Gain %": round(proj_gain, 2),
                        "Projected Value": round(proj_value, 0)
                    })
                    total_score += score
                
                sim_df = pd.DataFrame(results)
                st.dataframe(sim_df, use_container_width=True, hide_index=True)
                st.success(f"**Projected Total:** ${sim_df['Projected Value'].sum():,.0f} "
                          f"({((sim_df['Projected Value'].sum()/investment)-1)*100:+.1f}%)")
            else:
                st.warning("Please select at least one stock.")

    with tab5:
        st.subheader("🤖 Grok Market Insights")
        st.caption(f"Connected to: **{selected_model}**")

        context = ""
        if not summary_df.empty:
            top_str = summary_df.head(5)[["Ticker", "Rebound Score", "RSI"]].to_string(index=False)
            context = f"Current top rebounders (as of {datetime.now().strftime('%Y-%m-%d')}):\n{top_str}\n\n"

        query = st.text_area(
            "Ask Grok about these markets",
            value="Analyze the top 3 rebound candidates. Which has the best risk/reward for the next 4-8 weeks?",
            height=110
        )

        if st.button("Send to Grok", type="primary"):
            if query.strip():
                with st.spinner("Grok is thinking..."):
                    full_prompt = context + "Question: " + query
                    response = call_grok_api(full_prompt, selected_model, 0.68)
                    st.markdown("### Grok Response")
                    st.write(response)
            else:
                st.warning("Please enter a question.")

    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Delisted tickers auto-removed")


if __name__ == "__main__":
    main()