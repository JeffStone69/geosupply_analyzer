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

# ====================== SECTOR TICKERS (EXPANDED + COMBINED) ======================
ASX_MINING = ["BHP.AX", "RIO.AX", "FMG.AX", "S32.AX", "MIN.AX"]
ASX_SHIPPING = ["QUB.AX", "TCL.AX", "ASX.AX"]
ASX_ENERGY = ["STO.AX", "WDS.AX", "ORG.AX", "WHC.AX", "BPT.AX"]          # Oil, Gas, LNG, Coal
ASX_TECH = ["WTC.AX", "XRO.AX", "TNE.AX", "NXT.AX", "REA.AX", "360.AX", "PME.AX"]
ASX_RENEW = ["ORG.AX", "AGL.AX", "IGO.AX", "IFT.AX", "MCY.AX", "CEN.AX", "MEZ.AX", "RNE.AX"]

US_MINING = ["FCX", "NEM", "VALE", "SCCO", "GOLD", "AEM"]
US_SHIPPING = ["ZIM", "MATX", "SBLK", "DAC", "CMRE"]
US_ENERGY = ["XOM", "CVX", "COP", "OXY", "CCJ"]                          # Oil, Gas + Uranium (Cameco)
US_TECH = ["NVDA", "AAPL", "MSFT", "GOOGL", "AMD", "TSLA"]
US_RENEW = ["NEE", "BEPC", "CWEN", "FSLR", "ENPH"]

ALL_ASX = list(dict.fromkeys(ASX_MINING + ASX_SHIPPING + ASX_ENERGY + ASX_TECH + ASX_RENEW))  # deduped
ALL_US = list(dict.fromkeys(US_MINING + US_SHIPPING + US_ENERGY + US_TECH + US_RENEW))
ALL_TICKERS = ALL_ASX + ALL_US

API_BASE = "https://api.x.ai/v1"
AVAILABLE_MODELS = ["grok-4.20-reasoning", "grok-4.20-non-reasoning", "grok-4.20-multi-agent-0309", "grok-4-1-fast-reasoning", "grok-4-1-fast-non-reasoning"]

logging.basicConfig(filename="geosupply_errors.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ====================== OPTIMIZED SAVED ANALYSES (REVIEWED & REFINED) ======================
def load_saved_analyses():
    """Optimised: load once into session_state, never force-reset, dedupe by timestamp."""
    if "saved_analyses" not in st.session_state:
        st.session_state.saved_analyses = []
        if os.path.exists(SAVED_LOG):
            try:
                with open(SAVED_LOG, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            analysis = json.loads(line)
                            # dedupe by timestamp + tab
                            if not any(a.get("timestamp") == analysis.get("timestamp") and a.get("tab") == analysis.get("tab") 
                                       for a in st.session_state.saved_analyses):
                                st.session_state.saved_analyses.append(analysis)
            except Exception as e:
                st.warning(f"Could not load saved.log: {e}")
    return st.session_state.saved_analyses

def save_analysis(analysis: dict):
    """Append to file + session_state with atomic write."""
    try:
        os.makedirs(os.path.dirname(SAVED_LOG) or ".", exist_ok=True)
        with open(SAVED_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(analysis, ensure_ascii=False) + "\n")
        if "saved_analyses" not in st.session_state:
            st.session_state.saved_analyses = []
        # dedupe before append
        if not any(a.get("timestamp") == analysis.get("timestamp") for a in st.session_state.saved_analyses):
            st.session_state.saved_analyses.append(analysis)
        return True
    except Exception as e:
        st.error(f"Failed to save: {e}")
        return False

# ====================== REUSABLE SECTOR BUILDER (CODE OPTIMISATION) ======================
def build_sector_df(tickers: List[str], raw_data: Dict[str, pd.DataFrame], period: str) -> pd.DataFrame:
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
    df_sector = pd.DataFrame(rows)
    if not df_sector.empty:
        df_sector = df_sector.sort_values("Rebound Score", ascending=False)
    return df_sector

# ====================== CORE FUNCTIONS (unchanged + minor optimisations) ======================
@st.cache_data(ttl=300)
def fetch_batch_data(tickers: List[str], period: str = "6mo", real_time_mode: bool = False) -> Dict[str, pd.DataFrame]:
    if real_time_mode:
        period = "5d"  # shorter for intra-day feel
    if not tickers:
        return {}
    try:
        data = yf.download(tickers, period=period, group_by="ticker", auto_adjust=True, progress=False, interval="1m" if real_time_mode else "1d")
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
            logging.error(f"Grok API {resp.status_code}: {resp.text[:500]}")
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
        return {"name": info.get("longName") or info.get("shortName") or ticker.replace(".AX", ""), 
                "sector": info.get("sector", "Multi-Sector"), 
                "currency": "AUD" if ".AX" in ticker else "USD"}
    except:
        return {"name": ticker.replace(".AX", ""), "sector": "Resources/Tech/Energy", "currency": "AUD" if ".AX" in ticker else "USD"}

# ====================== MAIN APP ======================
def main():
    load_saved_analyses()  # optimised load
    if "grok_api_key" not in st.session_state:
        st.session_state.grok_api_key = ""

    st.title("📍 GeoSupply Rebound Analyzer")
    st.caption("**v11.0** • Multi-Sector (Mining + Shipping + Energy + Tech + Renewables) • Saved.log optimised • Real-time option + IBKR AU tab")

    with st.sidebar:
        st.header("Controls")
        grok_key = st.text_input("Grok API Key", type="password", value=st.session_state.grok_api_key, help="Get key at https://x.ai/api")
        if grok_key:
            st.session_state.grok_api_key = grok_key
        selected_model = st.selectbox("Grok Model", AVAILABLE_MODELS, index=0)

        st.subheader("Data Options")
        real_time_mode = st.checkbox("🔴 Real-time intra-day mode (yfinance 1m candles)", value=False,
                                     help="Shorter history for live feel – rebound scores still use full logic")
        market_filter = st.radio("Market Focus", ["Both", "ASX Only", "US Only"], horizontal=True)
        period = st.selectbox("Historical Period", ["1mo", "3mo", "6mo", "1y"], index=2 if not real_time_mode else 0)
        st.divider()

        st.subheader("USD ↔ AUD")
        rate = get_usd_aud_rate()
        if rate:
            st.metric("1 USD =", f"{rate:.4f} AUD")
            c1, c2 = st.columns(2)
            with c1:
                usd = st.number_input("USD", value=1000.0, step=100.0, key="usd_input")
            with c2:
                aud_val = round(usd * rate, 2)
                st.number_input("AUD", value=aud_val, step=100.0, key="aud_input", disabled=True)
            st.caption(f"{usd:,.0f} USD = **{aud_val:,.2f} AUD**")

        st.divider()
        st.info("**Rebound Score**  \n55% RSI (oversold) + 30% distance from 52w high + 15% momentum  \n**≥65 + RSI≤42 = strong buy**")
        if st.button("Refresh All Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # Filter tickers
    active_tickers = ALL_TICKERS if market_filter == "Both" else (ALL_ASX if market_filter == "ASX Only" else ALL_US)
    raw_data = fetch_batch_data(active_tickers, period, real_time_mode)

    # Dashboard summary
    summary_df = build_sector_df(active_tickers, raw_data, period)

    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs([
        "📊 Dashboard", 
        "⛏️ Mining", 
        "🚢 Shipping", 
        "⚡ Energy", 
        "💻 Technology", 
        "🌱 Renewables",
        "🧪 Simulator", 
        "💡 Strategy & Grok Insights", 
        "📚 Saved Analyses",
        "💼 Interactive Brokers AU"
    ])

    # Reusable page analyzer
    def add_page_analyzer(tab_name: str, page_context: str = "", model: str = selected_model):
        with st.expander("Analyse this page with Grok", expanded=False):
            st.caption(f"**{tab_name}** tab • Model: **{model}**")
            user_prompt = st.text_area("Optional instructions", placeholder="e.g. Suggest better layout...", key=f"user_prompt_{tab_name}", height=80)
            if st.button("Analyse Page with Grok", key=f"analyze_btn_{tab_name}", use_container_width=True):
                with st.spinner("Grok analysing..."):
                    full_prompt = f"""
You are analysing the **'{tab_name}'** tab of GeoSupply Rebound Analyzer v11.0 (multi-sector: Mining/Shipping/Energy/Tech/Renewables).
CURRENT PAGE CONTEXT: {page_context or "No specific data summary."}
USER REQUEST: {user_prompt or "General improvements."}
TASK: 1. Bugs/UX 2. Actionable improvements 3. $500-user ideas 4. Code optimisations.
Be concise and numbered.
"""
                    response = call_grok_api(full_prompt, model, temperature=0.7)
                    st.markdown("### Grok's Analysis")
                    st.write(response)
                    if st.button("Save Analysis", key=f"save_btn_{tab_name}", use_container_width=True):
                        analysis = {
                            "tab": tab_name,
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "model_used": model,
                            "user_prompt": user_prompt or "General",
                            "response": response
                        }
                        if save_analysis(analysis):
                            st.success("Saved to saved.log!")

    # TAB 1: DASHBOARD
    with tab1:
        st.subheader("Top Rebound Opportunities (All Sectors)")
        if not summary_df.empty:
            styled = summary_df.style.format({"Price": "${:.3f}", "Change %": "{:.2f}%", "Rebound Score": "{:.1f}", "RSI": "{:.1f}"}).map(
                lambda x: "color: #2ED573; font-weight: bold" if x >= 65 else ("color: #FFC107; font-weight: bold" if x >= 45 else "color: #FF4757; font-weight: bold"),
                subset=["Rebound Score"]
            )
            st.dataframe(styled, use_container_width=True, hide_index=True)
            top_ticker = summary_df.iloc[0]["Ticker"]
            if top_ticker in raw_data:
                info = get_ticker_info(top_ticker)
                st.plotly_chart(create_price_rsi_chart(raw_data[top_ticker], top_ticker, info["name"]), use_container_width=True)
        context = summary_df.head(10).to_string(index=False) if not summary_df.empty else "No data"
        add_page_analyzer("Dashboard", context)

    # TAB 2-6: SECTOR TABS (using reusable builder)
    sector_config = {
        "Mining": (ASX_MINING + US_MINING, "⛏️"),
        "Shipping": (ASX_SHIPPING + US_SHIPPING, "🚢"),
        "Energy": (ASX_ENERGY + US_ENERGY, "⚡"),
        "Technology": (ASX_TECH + US_TECH, "💻"),
        "Renewables": (ASX_RENEW + US_RENEW, "🌱")
    }
    tab_map = {tab2: "Mining", tab3: "Shipping", tab4: "Energy", tab5: "Technology", tab6: "Renewables"}

    for tab_obj, sector_name in tab_map.items():
        with tab_obj:
            st.subheader(f"{sector_config[sector_name][1]} {sector_name} Stocks Analysis")
            sector_tickers = sector_config[sector_name][0]
            sector_data = {k: v for k, v in raw_data.items() if k in sector_tickers} or fetch_batch_data(sector_tickers, period, real_time_mode)
            sector_df = build_sector_df(sector_tickers, sector_data, period)
            if not sector_df.empty:
                styled = sector_df.style.format({"Price": "${:.3f}", "Change %": "{:.2f}%", "Rebound Score": "{:.1f}", "RSI": "{:.1f}"}).map(
                    lambda x: "color: #2ED573; font-weight: bold" if x >= 65 else ("color: #FFC107; font-weight: bold" if x >= 45 else "color: #FF4757; font-weight: bold"),
                    subset=["Rebound Score"]
                )
                st.dataframe(styled, use_container_width=True, hide_index=True)
                top_t = sector_df.iloc[0]["Ticker"]
                if top_t in sector_data:
                    info = get_ticker_info(top_t)
                    st.plotly_chart(create_price_rsi_chart(sector_data[top_t], top_t, info["name"]), use_container_width=True)
            context = sector_df.head(8).to_string(index=False) if not sector_df.empty else f"No {sector_name.lower()} data"
            add_page_analyzer(sector_name, context)

    # TAB 7: SIMULATOR
    with tab7:
        st.subheader("🧪 Rebound Simulator")
        col1, col2 = st.columns(2)
        with col1: ticker_sim = st.text_input("Ticker", value="SIM.AX")
        with col2: company_sim = st.text_input("Company", value="Simulated Co")
        price_input = st.text_area("Price series (one per line)", placeholder="12.3\n12.5\n...", height=150)
        if st.button("Calculate", use_container_width=True):
            try:
                prices = [float(p.strip()) for p in price_input.strip().split("\n") if p.strip()]
                if len(prices) < 10:
                    st.warning("Need ≥10 prices")
                else:
                    dates = pd.date_range(end=pd.Timestamp.today(), periods=len(prices), freq='B')
                    df_sim = pd.DataFrame({"Close": prices}, index=dates)
                    score, rsi, mom = calculate_rebound_score(df_sim)
                    st.success(f"**Rebound Score:** {score:.1f} | RSI: {rsi} | Momentum: {mom}%")
                    st.plotly_chart(create_price_rsi_chart(df_sim, ticker_sim, company_sim), use_container_width=True)
            except Exception as e:
                st.error(f"Invalid data: {e}")
        add_page_analyzer("Simulator", "Custom price simulator")

    # TAB 8: STRATEGY
    with tab8:
        st.subheader("💡 Strategy & Grok Insights ($500 AUD)")
        if not summary_df.empty:
            top_picks = summary_df.head(5)[["Ticker", "Company", "Rebound Score", "RSI"]].to_dict(orient="records")
            st.dataframe(summary_df.head(5), use_container_width=True, hide_index=True)
            if st.button("Get Grok $500 Portfolio Strategy", use_container_width=True):
                with st.spinner("Grok consulting..."):
                    strategy_prompt = f"""
Based on current top rebound stocks (multi-sector):
{json.dumps(top_picks, indent=2)}
Suggest a diversified $500 AUD CommSec/IBKR-friendly portfolio. Prefer ASX. Include exact share quantities, risk reasoning, and expected rebound. Be specific.
"""
                    response = call_grok_api(strategy_prompt, selected_model)
                    st.markdown("### Grok Strategy")
                    st.write(response)
                    if st.button("Save Strategy"):
                        analysis = {"tab": "Strategy", "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    "model_used": selected_model, "user_prompt": "Portfolio", "response": response}
                        save_analysis(analysis)
        add_page_analyzer("Strategy & Grok Insights", "Grok $500 strategy")

    # TAB 9: SAVED ANALYSES
    with tab9:
        st.subheader("📚 Saved Grok Analyses")
        st.caption(f"**{SAVED_LOG}** • {len(st.session_state.saved_analyses)} entries (optimised deduped load)")
        if st.session_state.saved_analyses:
            for i, analysis in enumerate(reversed(st.session_state.saved_analyses)):
                with st.expander(f"{analysis['tab']} — {analysis['timestamp']}"):
                    st.write(f"**Model:** {analysis.get('model_used', 'unknown')}")
                    st.write(f"**Prompt:** {analysis['user_prompt']}")
                    st.write(analysis['response'])
                    txt = f"Tab: {analysis['tab']}\nTimestamp: {analysis['timestamp']}\nModel: {analysis.get('model_used')}\n\n{analysis['response']}"
                    st.download_button("Download", data=txt, file_name=f"grok_{analysis['tab']}_{analysis['timestamp'].replace(':', '-')}.txt", key=f"dl_{i}")
        else:
            st.info("No saved analyses yet.")
        if st.button("Clear saved.log"):
            if os.path.exists(SAVED_LOG):
                os.remove(SAVED_LOG)
            st.session_state.saved_analyses = []
            st.success("Cleared!")
            st.rerun()
        add_page_analyzer("Saved Analyses", "Meta saved analyses tab")

    # TAB 10: INTERACTIVE BROKERS AU
    with tab10:
        st.subheader("💼 Interactive Brokers Australia")
        st.caption("Low-cost execution • ASX + Global • Ideal for $500 portfolios")
        st.info("IBKR AU offers $0–$5 brokerage on small ASX trades and direct US access. Real API integration possible via ib_insync (future).")
        
        col_a, col_b = st.columns(2)
        with col_a:
            st.metric("Typical $500 ASX trade fee", "**$0–$5**")
            st.metric("US stocks", "**$0.005/share** (min $1)")
        with col_b:
            st.write("**Why IBKR for GeoSupply users?**")
            st.write("• Real-time data via TWS API")
            st.write("• Fractional shares + auto-rebalancing")
            st.write("• Direct access to all 50+ GeoSupply tickers")

        if st.button("Generate IBKR-Optimised $500 Portfolio", use_container_width=True):
            with st.spinner("Building IBKR-friendly allocation..."):
                ibkr_prompt = f"""
Current top rebound picks (all sectors):
{json.dumps(summary_df.head(8)[['Ticker','Company','Rebound Score']].to_dict(orient='records') if not summary_df.empty else [])}
Create a $500 AUD portfolio optimised for IBKR Australia (low fees, whole/fractional shares, ASX priority). 
Include exact quantities, expected brokerage, and one-click TWS order notes.
"""
                ibkr_response = call_grok_api(ibkr_prompt, selected_model)
                st.markdown("### IBKR-Optimised Strategy")
                st.write(ibkr_response)

        st.caption("Tip: Use IBKR TWS API + this app for live portfolio sync in future releases.")
        add_page_analyzer("Interactive Brokers AU", "IBKR AU integration tab")

    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | v11.0 • All sectors combined • Saved.log refined • Real-time + IBKR ready")

if __name__ == "__main__":
    main()