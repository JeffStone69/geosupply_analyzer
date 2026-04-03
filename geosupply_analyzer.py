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

st.set_page_config(page_title="GeoSupply Rebound Analyzer", page_icon="📈", layout="wide", initial_sidebar_state="expanded")

SAVED_LOG = "saved.log"

ASX_MINING = ["BHP.AX", "RIO.AX", "FMG.AX", "S32.AX", "MIN.AX"]
ASX_SHIPPING = ["QUB.AX", "TCL.AX", "ASX.AX"]
US_MINING = ["FCX", "NEM", "VALE", "SCCO", "GOLD", "AEM"]
US_SHIPPING = ["ZIM", "MATX", "SBLK", "DAC", "CMRE"]

ALL_ASX = ASX_MINING + ASX_SHIPPING
ALL_US = US_MINING + US_SHIPPING
ALL_TICKERS = ALL_ASX + ALL_US

API_BASE = "https://api.x.ai/v1"
AVAILABLE_MODELS = ["grok-4.20-reasoning", "grok-4.20-non-reasoning", "grok-4.20-multi-agent-0309", "grok-4-1-fast-reasoning", "grok-4-1-fast-non-reasoning"]

logging.basicConfig(filename="geosupply_errors.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def load_saved_analyses():
    if "saved_analyses" not in st.session_state:
        st.session_state.saved_analyses = []
    st.session_state.saved_analyses = []
    if os.path.exists(SAVED_LOG):
        try:
            with open(SAVED_LOG, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        st.session_state.saved_analyses.append(json.loads(line))
        except Exception as e:
            st.warning(f"Could not load saved.log: {e}")

def save_analysis(analysis: dict):
    try:
        with open(SAVED_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(analysis) + "\n")
        if "saved_analyses" not in st.session_state:
            st.session_state.saved_analyses = []
        st.session_state.saved_analyses.append(analysis)
    except Exception as e:
        st.error(f"Failed to save to saved.log: {e}")

def add_page_analyzer(tab_name: str, page_context: str = "", model: str = "grok-4.20-reasoning"):
    with st.expander("Analyse this page with Grok", expanded=False):
        st.caption(f"**{tab_name}** tab • Using model: **{model}**")
        user_prompt = st.text_area("Optional instructions to guide Grok", placeholder="e.g. Suggest better layout, fix bugs, make more beginner-friendly...", key=f"user_prompt_{tab_name}", height=80)
        if st.button("Analyse Page with Grok", key=f"analyze_btn_{tab_name}", use_container_width=True):
            with st.spinner("Grok is analysing this page..."):
                full_prompt = f"""
You are analysing the **'{tab_name}'** tab of the GeoSupply Rebound Analyzer (v10.8).
CURRENT PAGE CONTEXT: {page_context or "No specific data summary."}
USER REQUEST: {user_prompt or "General troubleshooting and improvement suggestions."}
TASK: 1. Bugs/UX issues 2. Actionable improvements 3. Ideas for $500 users 4. Code optimisations.
Be concise and number your suggestions.
"""
                response = call_grok_api(full_prompt, model, temperature=0.7)
                st.markdown("### Grok's Page Analysis")
                st.write(response)
                if st.button("Save this Grok Analysis", key=f"save_btn_{tab_name}", use_container_width=True):
                    analysis = {"tab": tab_name, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "model_used": model, "user_prompt": user_prompt or "General analysis", "response": response}
                    save_analysis(analysis)
                    st.success("Analysis saved permanently to saved.log!")

@st.cache_data(ttl=300)
def fetch_batch_data(tickers: List[str], period: str = "6mo") -> Dict[str, pd.DataFrame]:
    if not tickers: return {}
    try:
        data = yf.download(tickers, period=period, group_by="ticker", auto_adjust=True, progress=False)
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

def call_grok_api(prompt: str, model: str, temperature: float = 0.7) -> str:
    api_key = os.getenv("GROK_API_KEY") or st.session_state.get("grok_api_key", "")
    if not api_key:
        return "Please enter your Grok API key in the sidebar."
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": temperature, "max_tokens": 1200}
    try:
        resp = requests.post(f"{API_BASE}/chat/completions", headers=headers, json=payload, timeout=45)
        if resp.status_code != 200:
            logging.error(f"Grok API {resp.status_code} (model {model}): {resp.text[:500]}")
            return f"Grok API error {resp.status_code}"
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logging.error(f"Grok error: {str(e)}")
        return f"Connection error: {str(e)}"

def create_price_rsi_chart(df: pd.DataFrame, ticker: str, company_name: str) -> go.Figure:
    rsi_series = calculate_rsi(df["Close"])
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, row_heights=[0.70, 0.30], subplot_titles=(f"{ticker} — {company_name}", "RSI (14)"))
    fig.add_trace(go.Candlestick(x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"], name="Price"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=rsi_series, name="RSI", line=dict(color="#FF6B6B", width=2.5)), row=2, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="#FF4757", row=2, col=1, annotation_text="Overbought")
    fig.add_hline(y=30, line_dash="dash", line_color="#2ED573", row=2, col=1, annotation_text="Oversold")
    fig.update_layout(height=680, template="plotly_dark", margin=dict(l=30,r=30,t=60,b=30), legend=dict(orientation="h", y=1.05))
    fig.update_xaxes(rangeslider_visible=False)
    return fig

@st.cache_data(ttl=3600)
def get_ticker_info(ticker: str) -> Dict:
    try:
        info = yf.Ticker(ticker).info
        return {"name": info.get("longName") or info.get("shortName") or ticker.replace(".AX", ""), "sector": info.get("sector", "Mining/Shipping"), "currency": "AUD" if ".AX" in ticker else "USD"}
    except:
        return {"name": ticker.replace(".AX", ""), "sector": "Resources/Transport", "currency": "AUD" if ".AX" in ticker else "USD"}

def main():
    load_saved_analyses()
    if "grok_api_key" not in st.session_state:
        st.session_state.grok_api_key = ""
    st.title("GeoSupply Rebound Analyzer")
    st.caption("**v10.8** • Grok analyses now saved permanently to saved.log")
    with st.sidebar:
        st.header("Controls")
        grok_key = st.text_input("Grok API Key", type="password", value=st.session_state.grok_api_key, help="Get key at https://x.ai/api")
        if grok_key: st.session_state.grok_api_key = grok_key
        selected_model = st.selectbox("Grok Model", AVAILABLE_MODELS, index=0)
        market_filter = st.radio("Market Focus", ["Both", "ASX Only", "US Only"], horizontal=True)
        period = st.selectbox("Historical Period", ["1mo", "3mo", "6mo", "1y"], index=2)
        st.divider()
        st.subheader("USD ↔ AUD")
        rate = get_usd_aud_rate()
        if rate:
            st.metric("1 USD =", f"{rate:.4f} AUD")
            c1, c2 = st.columns(2)
            with c1: usd = st.number_input("USD", value=1000.0, step=100.0)
            with c2: st.number_input("AUD", value=round(usd * rate, 2), step=100.0, key="aud")
            st.caption(f"{usd:,.0f} USD = **{usd*rate:,.2f} AUD**")
        st.divider()
        st.info("**Rebound Score explained**  \n55% RSI (oversold) + 30% distance from 52w high + 15% momentum  \n**≥65 + RSI≤42 = strong buy signal**")
        if st.button("Refresh All Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    active_tickers = ALL_TICKERS if market_filter == "Both" else (ALL_ASX if market_filter == "ASX Only" else ALL_US)
    raw_data = fetch_batch_data(active_tickers, period)
    summary_rows = []
    detailed_data: Dict[str, pd.DataFrame] = {}
    for ticker, df in raw_data.items():
        if df.empty or len(df) < 15: continue
        score, rsi_val, mom = calculate_rebound_score(df)
        info = get_ticker_info(ticker)
        latest = df.iloc[-1]
        prev_close = df.iloc[-2]["Close"] if len(df) > 1 else latest["Close"]
        change_pct = ((latest["Close"] / prev_close) - 1) * 100
        summary_rows.append({"Ticker": ticker, "Company": info["name"], "Market": "ASX" if ".AX" in ticker else "US", "Currency": info["currency"], "Price": round(latest["Close"], 3), "Change %": round(change_pct, 2), "RSI": rsi_val, "Rebound Score": round(score, 1), "Momentum": mom, "Volume": int(latest.get("Volume", 0))})
        detailed_data[ticker] = df
    summary_df = pd.DataFrame(summary_rows)
    if not summary_df.empty:
        summary_df = summary_df.sort_values("Rebound Score", ascending=False)
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Dashboard", "Mining", "Shipping", "Simulator", "Strategy & Grok Insights", "Saved Analyses"])
    with tab1:
        st.subheader("Top Rebound Opportunities")
        if not summary_df.empty:
            styled = summary_df.style.format({"Price": "${:.3f}", "Change %": "{:.2f}%", "Rebound Score": "{:.1f}", "RSI": "{:.1f}"}).map(lambda x: "color: #2ED573; font-weight: bold" if x >= 65 else ("color: #FFC107; font-weight: bold" if x >= 45 else "color: #FF4757; font-weight: bold"), subset=["Rebound Score"])
            st.dataframe(styled, use_container_width=True, hide_index=True)
            top_ticker = summary_df.iloc[0]["Ticker"]
            if top_ticker in detailed_data:
                info = get_ticker_info(top_ticker)
                st.plotly_chart(create_price_rsi_chart(detailed_data[top_ticker], top_ticker, info["name"]), use_container_width=True)
        context = summary_df.head(8).to_string(index=False) if not summary_df.empty else "No data"
        add_page_analyzer("Dashboard", context, selected_model)
    with tab2:
        st.subheader("⛏️ Mining Stocks Analysis")
        st.caption("ASX & US mining stocks with rebound scoring")
        mining_tickers = ASX_MINING + US_MINING
        mining_data = fetch_batch_data(mining_tickers, period)
        mining_rows = []
        mining_detailed: Dict[str, pd.DataFrame] = {}
        for ticker, df in mining_data.items():
            if df.empty or len(df) < 15: continue
            score, rsi_val, mom = calculate_rebound_score(df)
            info = get_ticker_info(ticker)
            latest = df.iloc[-1]
            prev_close = df.iloc[-2]["Close"] if len(df) > 1 else latest["Close"]
            change_pct = ((latest["Close"] / prev_close) - 1) * 100
            mining_rows.append({"Ticker": ticker, "Company": info["name"], "Market": "ASX" if ".AX" in ticker else "US", "Currency": info["currency"], "Price": round(latest["Close"], 3), "Change %": round(change_pct, 2), "RSI": rsi_val, "Rebound Score": round(score, 1), "Momentum": mom, "Volume": int(latest.get("Volume", 0))})
            mining_detailed[ticker] = df
        mining_df = pd.DataFrame(mining_rows)
        if not mining_df.empty:
            mining_df = mining_df.sort_values("Rebound Score", ascending=False)
        st.dataframe(mining_df.style.format({"Price": "${:.3f}", "Change %": "{:.2f}%", "Rebound Score": "{:.1f}", "RSI": "{:.1f}"}).map(lambda x: "color: #2ED573; font-weight: bold" if x >= 65 else ("color: #FFC107; font-weight: bold" if x >= 45 else "color: #FF4757; font-weight: bold"), subset=["Rebound Score"]), use_container_width=True, hide_index=True)
        if not mining_df.empty:
            top_mining = mining_df.iloc[0]["Ticker"]
            if top_mining in mining_detailed:
                info = get_ticker_info(top_mining)
                st.plotly_chart(create_price_rsi_chart(mining_detailed[top_mining], top_mining, info["name"]), use_container_width=True)
        context = mining_df.head(8).to_string(index=False) if not mining_df.empty else "No mining data"
        add_page_analyzer("Mining", context, selected_model)
    with tab3:
        st.subheader("Shipping Stocks Analysis")
        st.caption("ASX & US shipping companies: QUB.AX, TCL.AX, ASX.AX, ZIM, MATX, SBLK, DAC, CMRE")
        shipping_tickers = ASX_SHIPPING + US_SHIPPING
        shipping_data = fetch_batch_data(shipping_tickers, period)
        shipping_rows = []
        shipping_detailed: Dict[str, pd.DataFrame] = {}
        for ticker, df in shipping_data.items():
            if df.empty or len(df) < 15: continue
            score, rsi_val, mom = calculate_rebound_score(df)
            info = get_ticker_info(ticker)
            latest = df.iloc[-1]
            prev_close = df.iloc[-2]["Close"] if len(df) > 1 else latest["Close"]
            change_pct = ((latest["Close"] / prev_close) - 1) * 100
            shipping_rows.append({"Ticker": ticker, "Company": info["name"], "Market": "ASX" if ".AX" in ticker else "US", "Currency": info["currency"], "Price": round(latest["Close"], 3), "Change %": round(change_pct, 2), "RSI": rsi_val, "Rebound Score": round(score, 1), "Momentum": mom, "Volume": int(latest.get("Volume", 0))})
            shipping_detailed[ticker] = df
        shipping_df = pd.DataFrame(shipping_rows)
        if not shipping_df.empty:
            shipping_df = shipping_df.sort_values("Rebound Score", ascending=False)
        if not shipping_df.empty:
            styled_shipping = shipping_df.style.format({"Price": "${:.3f}", "Change %": "{:.2f}%", "Rebound Score": "{:.1f}", "RSI": "{:.1f}"}).map(lambda x: "color: #2ED573; font-weight: bold" if x >= 65 else ("color: #FFC107; font-weight: bold" if x >= 45 else "color: #FF4757; font-weight: bold"), subset=["Rebound Score"])
            st.dataframe(styled_shipping, use_container_width=True, hide_index=True)
            top_shipping_ticker = shipping_df.iloc[0]["Ticker"]
            if top_shipping_ticker in shipping_detailed:
                info = get_ticker_info(top_shipping_ticker)
                st.plotly_chart(create_price_rsi_chart(shipping_detailed[top_shipping_ticker], top_shipping_ticker, info["name"]), use_container_width=True)
        context_shipping = shipping_df.head(8).to_string(index=False) if not shipping_df.empty else "No shipping data"
        add_page_analyzer("Shipping", context_shipping, selected_model)
    with tab4:
        st.subheader("🧪 Rebound Simulator")
        st.caption("Test rebound score calculations with custom price data")
        col1, col2 = st.columns(2)
        with col1:
            ticker_sim = st.text_input("Ticker (for display)", value="SIM.AX")
        with col2:
            company_sim = st.text_input("Company name", value="Simulated Co")
        st.markdown("### Enter historical prices (Close only)")
        price_input = st.text_area("Price series (one per line, e.g. 10.5, 10.8, ...)", placeholder="12.3\n12.5\n12.1\n11.9\n...", height=150)
        if st.button("Calculate Rebound Score", use_container_width=True):
            try:
                prices = [float(p.strip()) for p in price_input.strip().split("\n") if p.strip()]
                if len(prices) < 10:
                    st.warning("Need at least 10 price points for reliable RSI.")
                else:
                    dates = pd.date_range(end=pd.Timestamp.today(), periods=len(prices), freq='B')
                    df_sim = pd.DataFrame({"Close": prices}, index=dates)
                    score, rsi, mom = calculate_rebound_score(df_sim)
                    st.success(f"**Rebound Score:** {score:.1f} | RSI: {rsi} | Momentum (10d %): {mom}%")
                    st.plotly_chart(create_price_rsi_chart(df_sim, ticker_sim, company_sim), use_container_width=True)
            except Exception as e:
                st.error(f"Invalid price data: {e}")
        add_page_analyzer("Simulator", "Custom price input for rebound score testing", selected_model)
    with tab5:
        st.subheader("Strategy & Grok Insights")
        st.caption("Exact $500 AUD CommSec recommendations • Powered by Grok")
        if not summary_df.empty:
            top_picks = summary_df.head(5)[["Ticker", "Company", "Rebound Score", "RSI"]].to_dict(orient="records")
            st.write("**Current Top Rebound Picks:**")
            st.dataframe(summary_df.head(5), use_container_width=True, hide_index=True)
            if st.button("Get Grok $500 Portfolio Strategy", use_container_width=True):
                with st.spinner("Consulting Grok for strategy..."):
                    strategy_prompt = f"""
Based on the following top rebound stocks from GeoSupply Analyzer:
{json.dumps(top_picks, indent=2)}
Suggest a diversified $500 AUD portfolio allocation for CommSec (ASX focus preferred).
Include exact share quantities assuming current prices, risk reasoning, and expected rebound.
Be specific and actionable.
"""
                    strategy_response = call_grok_api(strategy_prompt, selected_model, temperature=0.7)
                    st.markdown("### Grok's $500 Strategy Recommendation")
                    st.write(strategy_response)
                    if st.button("Save Strategy Analysis"):
                        analysis = {"tab": "Strategy", "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "model_used": selected_model, "user_prompt": "Portfolio strategy", "response": strategy_response}
                        save_analysis(analysis)
                        st.success("Saved!")
        else:
            st.info("No data yet.")
        add_page_analyzer("Strategy & Grok Insights", "Strategy tab with Grok-powered $500 portfolio suggestions", selected_model)
    with tab6:
        st.subheader("Saved Grok Analyses")
        st.caption(f"Loaded from **{SAVED_LOG}** ({len(st.session_state.saved_analyses)} entries)")
        if st.session_state.saved_analyses:
            for i, analysis in enumerate(reversed(st.session_state.saved_analyses)):
                with st.expander(f"{analysis['tab']} — {analysis['timestamp']}"):
                    st.write(f"**Model:** {analysis.get('model_used', 'unknown')}")
                    st.write(f"**User prompt:** {analysis['user_prompt']}")
                    st.write(analysis['response'])
                    txt = f"Tab: {analysis['tab']}\nTimestamp: {analysis['timestamp']}\nModel: {analysis.get('model_used','unknown')}\nUser prompt: {analysis['user_prompt']}\n\n{analysis['response']}"
                    st.download_button("Download", data=txt, file_name=f"grok_analysis_{analysis['tab']}_{analysis['timestamp'].replace(':', '-')}.txt", key=f"dl_{i}")
        else:
            st.info("No analyses saved yet. Use any 'Analyse Page with Grok' button.")
        if st.button("Clear saved.log (delete all)"):
            if os.path.exists(SAVED_LOG):
                os.remove(SAVED_LOG)
            st.session_state.saved_analyses = []
            st.success("saved.log cleared!")
            st.rerun()
        add_page_analyzer("Saved Analyses", "Meta-tab showing all saved Grok feedback", selected_model)
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | v10.8 • Analyses saved to saved.log")

if __name__ == "__main__":
    main()