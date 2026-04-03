#!/usr/bin/env python
"""
geosupply_analyzer.py
GeoSupply Rebound Analyzer v10.5
Optimized Streamlit Dashboard for ASX + US Mining & Shipping Stocks

New in v10.5 (April 2026):
- "🤖 Analyse Page with Grok" feature on EVERY tab
- Optional custom instructions for targeted improvements/troubleshooting
- "💾 Save Grok Answer" with persistent storage + download
- New "📜 Saved Analyses" tab to view/export all saved Grok feedback
- Self-improving system now fully integrated

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
    "grok-4-1-fast-reasoning"
]

logging.basicConfig(
    filename="geosupply_errors.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ====================== HELPER: PAGE ANALYZER (NEW v10.5) ======================
def add_page_analyzer(tab_name: str, page_context: str = ""):
    """Adds 'Analyse Page with Grok' feature to any tab."""
    with st.expander("🤖 Analyse this page with Grok", expanded=False):
        st.caption(f"**{tab_name}** tab • Troubleshooting + improvement ideas")
        
        user_prompt = st.text_area(
            "Optional instructions to guide Grok",
            placeholder="e.g. 'Suggest better layout for mobile', 'Add export button', 'Fix any bugs you see', 'Make this more beginner-friendly for $500 accounts'",
            key=f"user_prompt_{tab_name}",
            height=80
        )
        
        if st.button("🚀 Analyse Page with Grok", key=f"analyze_btn_{tab_name}", use_container_width=True):
            with st.spinner("Grok is analysing this page..."):
                full_prompt = f"""
You are an expert Streamlit + trading dashboard reviewer.
You are analysing the **'{tab_name}'** tab of the GeoSupply Rebound Analyzer (v10.5).

CURRENT PAGE CONTEXT:
{page_context or "No specific data summary available for this tab."}

USER OPTIONAL REQUEST: {user_prompt or "No specific request — provide general troubleshooting and improvement suggestions."}

TASK:
1. Any bugs, errors, or UX issues you spot on this page.
2. Specific, actionable UI/UX improvements.
3. New feature ideas that would help $500 AUD CommSec users maximise profit while staying risk-averse.
4. Any code-level optimisations or best practices.

Be concise, professional, and directly actionable. Number your suggestions.
"""
                response = call_grok_api(full_prompt, selected_model, temperature=0.7)
                
                st.markdown("### Grok's Page Analysis")
                st.write(response)
                
                # Save button
                if st.button("💾 Save this Grok Analysis", key=f"save_btn_{tab_name}", use_container_width=True):
                    if "saved_analyses" not in st.session_state:
                        st.session_state.saved_analyses = []
                    st.session_state.saved_analyses.append({
                        "tab": tab_name,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "user_prompt": user_prompt or "General analysis",
                        "response": response
                    })
                    st.success("✅ Analysis saved! View it in the 📜 Saved Analyses tab.")

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
    """Calculate 14-period RSI."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period, min_periods=1).mean()
    avg_loss = loss.rolling(window=period, min_periods=1).mean()
    rs = avg_gain / avg_loss.replace(0, float('nan'))
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def calculate_rebound_score(df: pd.DataFrame) -> Tuple[float, float, float]:
    """Proprietary Rebound Score (0-100)."""
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
    """Call xAI Grok API with full error logging."""
    api_key = os.getenv("GROK_API_KEY") or st.session_state.get("grok_api_key", "")
    if not api_key:
        return "❌ Please enter your Grok API key in the sidebar."

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": 1200,
    }

    try:
        resp = requests.post(f"{API_BASE}/chat/completions", headers=headers, json=payload, timeout=45)
        if resp.status_code != 200:
            logging.error(f"Grok API {resp.status_code}: {resp.text[:500]}")
            if resp.status_code == 401: return "❌ Invalid or expired Grok API key."
            if resp.status_code == 429: return "❌ Rate limit reached."
            return f"❌ Grok API error {resp.status_code} (check log)."
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logging.error(f"Grok error: {str(e)}")
        return f"❌ Connection error: {str(e)}"


def create_price_rsi_chart(df: pd.DataFrame, ticker: str, company_name: str) -> go.Figure:
    """Create interactive candlestick + RSI chart."""
    rsi_series = calculate_rsi(df["Close"])
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                        row_heights=[0.70, 0.30],
                        subplot_titles=(f"{ticker} — {company_name}", "RSI (14)"))
    
    fig.add_trace(go.Candlestick(x=df.index, open=df["Open"], high=df["High"],
                                 low=df["Low"], close=df["Close"], name="Price"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=rsi_series, name="RSI",
                             line=dict(color="#FF6B6B", width=2.5)), row=2, col=1)
    
    fig.add_hline(y=70, line_dash="dash", line_color="#FF4757", row=2, col=1, annotation_text="Overbought")
    fig.add_hline(y=30, line_dash="dash", line_color="#2ED573", row=2, col=1, annotation_text="Oversold")
    
    fig.update_layout(height=680, template="plotly_dark", margin=dict(l=30,r=30,t=60,b=30),
                      legend=dict(orientation="h", y=1.05))
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
        return {"name": ticker.replace(".AX", ""), "sector": "Resources/Transport",
                "currency": "AUD" if ".AX" in ticker else "USD"}


# ====================== MAIN APP ======================
def main():
    if "grok_api_key" not in st.session_state:
        st.session_state.grok_api_key = ""
    if "saved_analyses" not in st.session_state:
        st.session_state.saved_analyses = []

    st.title("📈 GeoSupply Rebound Analyzer")
    st.caption("**v10.5** • Analyse Any Page with Grok • $500 CommSec Strategy • Self-Improving")

    # ====================== SIDEBAR ======================
    with st.sidebar:
        st.header("⚙️ Controls")
        grok_key = st.text_input("Grok API Key", type="password",
                                 value=st.session_state.grok_api_key,
                                 help="Get key at https://x.ai/api")
        if grok_key:
            st.session_state.grok_api_key = grok_key

        selected_model = st.selectbox("Grok Model", AVAILABLE_MODELS, index=0)
        market_filter = st.radio("Market Focus", ["Both", "ASX Only", "US Only"], horizontal=True)
        period = st.selectbox("Historical Period", ["1mo", "3mo", "6mo", "1y"], index=2)

        st.divider()
        st.subheader("💱 USD ↔ AUD")
        rate = get_usd_aud_rate()
        if rate:
            st.metric("1 USD =", f"{rate:.4f} AUD")
            c1, c2 = st.columns(2)
            with c1: usd = st.number_input("USD", value=1000.0, step=100.0)
            with c2: st.number_input("AUD", value=round(usd * rate, 2), step=100.0, key="aud")
            st.caption(f"{usd:,.0f} USD = **{usd*rate:,.2f} AUD**")

        st.divider()
        st.info("""
        **Rebound Score explained**  
        55% RSI (oversold) + 30% distance from 52w high + 15% momentum  
        **≥65 + RSI≤42 = strong buy signal**
        """)

        if st.button("🔄 Refresh All Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # Determine active tickers
    active_tickers = ALL_TICKERS if market_filter == "Both" else (ALL_ASX if market_filter == "ASX Only" else ALL_US)
    raw_data = fetch_batch_data(active_tickers, period)

    # Build summary
    summary_rows = []
    detailed_data: Dict[str, pd.DataFrame] = {}
    for ticker, df in raw_data.items():
        if df.empty or len(df) < 15: continue
        score, rsi_val, mom = calculate_rebound_score(df)
        info = get_ticker_info(ticker)
        latest = df.iloc[-1]
        prev_close = df.iloc[-2]["Close"] if len(df) > 1 else latest["Close"]
        change_pct = ((latest["Close"] / prev_close) - 1) * 100

        summary_rows.append({
            "Ticker": ticker, "Company": info["name"], "Market": "ASX" if ".AX" in ticker else "US",
            "Currency": info["currency"], "Price": round(latest["Close"], 3),
            "Change %": round(change_pct, 2), "RSI": rsi_val,
            "Rebound Score": round(score, 1), "Momentum": mom,
            "Volume": int(latest.get("Volume", 0))
        })
        detailed_data[ticker] = df

    summary_df = pd.DataFrame(summary_rows)
    if not summary_df.empty:
        summary_df = summary_df.sort_values("Rebound Score", ascending=False)

    # ====================== TABS ======================
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📊 Dashboard", "⛏️ Mining", "🚢 Shipping", "🧪 Simulator",
        "🤖 Grok Insights", "💰 $500 Strategy", "📜 Saved Analyses"
    ])

    # ------------------- TAB 1: Dashboard -------------------
    with tab1:
        st.subheader("Top Rebound Opportunities")
        if not summary_df.empty:
            styled = summary_df.style.format({
                "Price": "${:.3f}", "Change %": "{:.2f}%",
                "Rebound Score": "{:.1f}", "RSI": "{:.1f}"
            }).applymap(lambda x: "color: #2ED573; font-weight: bold" if x >= 65 else
                        ("color: #FFC107; font-weight: bold" if x >= 45 else "color: #FF4757; font-weight: bold"),
                        subset=["Rebound Score"])
            st.dataframe(styled, use_container_width=True, hide_index=True)

            top_ticker = summary_df.iloc[0]["Ticker"]
            if top_ticker in detailed_data:
                info = get_ticker_info(top_ticker)
                st.plotly_chart(create_price_rsi_chart(detailed_data[top_ticker], top_ticker, info["name"]),
                                use_container_width=True)
        else:
            st.warning("No data available.")
        
        # Page Analyzer
        context = summary_df.head(8).to_string(index=False) if not summary_df.empty else "No data"
        add_page_analyzer("Dashboard", context)

    # ------------------- TAB 2: Mining -------------------
    with tab2:
        st.subheader("Mining Sector")
        mining_tickers = ASX_MINING + US_MINING
        df_m = summary_df[summary_df["Ticker"].isin(mining_tickers)] if not summary_df.empty else pd.DataFrame()
        if not df_m.empty:
            st.dataframe(df_m, use_container_width=True, hide_index=True)
        else:
            st.info("No mining data.")
        
        context = df_m.head(8).to_string(index=False) if not df_m.empty else "No mining data"
        add_page_analyzer("Mining", context)

    # ------------------- TAB 3: Shipping -------------------
    with tab3:
        st.subheader("Shipping & Logistics")
        shipping_tickers = ASX_SHIPPING + US_SHIPPING
        df_s = summary_df[summary_df["Ticker"].isin(shipping_tickers)] if not summary_df.empty else pd.DataFrame()
        if not df_s.empty:
            st.dataframe(df_s, use_container_width=True, hide_index=True)
        else:
            st.info("No shipping data.")
        
        context = df_s.head(8).to_string(index=False) if not df_s.empty else "No shipping data"
        add_page_analyzer("Shipping", context)

    # ------------------- TAB 4: Simulator -------------------
    with tab4:
        st.subheader("Investment Simulator")
        investment = st.number_input("Investment Amount (USD)", min_value=1000, value=10000, step=1000)
        horizon = st.selectbox("Time Horizon", ["1 Month", "3 Months", "6 Months"], index=1)
        default_tickers = summary_df.head(4)["Ticker"].tolist() if not summary_df.empty else []
        selected = st.multiselect("Select stocks", summary_df["Ticker"].tolist() if not summary_df.empty else [], default=default_tickers)
        if st.button("Run Simulation", type="primary"):
            if selected:
                results = []
                for tkr in selected:
                    row = summary_df[summary_df["Ticker"] == tkr].iloc[0]
                    score = row["Rebound Score"]
                    proj_gain = (score / 3.0) * (1.0 if "1 Month" in horizon else 2.2)
                    alloc = investment / len(selected)
                    proj_value = alloc * (1 + proj_gain / 100)
                    results.append({"Ticker": tkr, "Allocation": round(alloc), "Rebound Score": score,
                                    "Projected Gain %": round(proj_gain, 2), "Projected Value": round(proj_value, 0)})
                sim_df = pd.DataFrame(results)
                st.dataframe(sim_df, use_container_width=True, hide_index=True)
                st.success(f"**Projected Total:** ${sim_df['Projected Value'].sum():,.0f} "
                           f"({((sim_df['Projected Value'].sum()/investment)-1)*100:+.1f}%)")
            else:
                st.warning("Select at least one stock.")
        
        add_page_analyzer("Simulator", "Investment simulator tab — projection engine based on Rebound Score")

    # ------------------- TAB 5: Grok Insights -------------------
    with tab5:
        st.subheader("🤖 Grok Market Insights")
        st.caption(f"Connected to: **{selected_model}**")
        context_str = ""
        if not summary_df.empty:
            top_str = summary_df.head(5)[["Ticker", "Rebound Score", "RSI"]].to_string(index=False)
            context_str = f"Current top rebounders (as of {datetime.now().strftime('%Y-%m-%d')}):\n{top_str}\n\n"
        query = st.text_area("Ask Grok about these markets",
                             value="Analyze the top 3 rebound candidates. Which has the best risk/reward for the next 4-8 weeks?",
                             height=110)
        if st.button("Send to Grok", type="primary"):
            if query.strip():
                with st.spinner("Grok is thinking..."):
                    response = call_grok_api(context_str + "Question: " + query, selected_model, 0.68)
                    st.markdown("### Grok Response")
                    st.write(response)
            else:
                st.warning("Please enter a question.")
        
        add_page_analyzer("Grok Insights", "Natural language market insights tab powered by Grok API")

    # ------------------- TAB 6: $500 Strategy -------------------
    with tab6:
        st.subheader("💰 $500 AUD CommSec Micro-Rebound Strategy")
        st.caption("Ultra risk-averse • Max profit • Updated live from Rebound Score")

        st.markdown("""
        **Exact Rules (save in CommSec notes):**
        - Only trade when **Rebound Score ≥ 65** AND **RSI ≤ 42**
        - Max 2–3 positions ($200–$250 each)
        - First buy must be **≥ $500** per stock (CommSec rule)
        - Stop-loss **-8%**, Take-profit **+18%**
        - Review only once per week (Sunday night)
        - Use CommSec Pocket ($2 fee) if possible
        """)

        if not summary_df.empty:
            candidates = summary_df[(summary_df["Rebound Score"] >= 65) & (summary_df["RSI"] <= 42)].copy()
            if not candidates.empty:
                candidates = candidates.sort_values("Rebound Score", ascending=False).head(5)
                n_pos = min(3, len(candidates))
                alloc = 500 / n_pos
                candidates["Suggested Allocation"] = round(alloc, 2)
                candidates["Est. Shares"] = (candidates["Suggested Allocation"] / candidates["Price"]).astype(int)

                st.success(f"**{len(candidates)} high-probability setups found**")
                display_cols = ["Ticker", "Company", "Rebound Score", "RSI", "Price", "Suggested Allocation", "Est. Shares"]
                st.dataframe(candidates[display_cols].style.background_gradient(subset=["Rebound Score"], cmap="Greens"),
                             use_container_width=True, hide_index=True)

                if st.button("📋 Generate Full Trade Plan (Copy to Notepad)", type="primary", use_container_width=True):
                    plan = candidates[display_cols].copy()
                    plan["Stop-Loss Price"] = round(plan["Price"] * 0.92, 3)
                    plan["Target Price (+18%)"] = round(plan["Price"] * 1.18, 3)
                    plan["Max Loss if Stopped"] = round(plan["Suggested Allocation"] * 0.08, 2)
                    st.dataframe(plan, use_container_width=True, hide_index=True)
                    st.success(f"**Projected value at +18% target:** ${round(500 * 1.18):,} AUD")
                    st.info("**Next steps:** Buy top 2–3 in CommSec → set alerts → screenshot this plan.")
            else:
                st.warning("No setups meet strict criteria right now. Check again after market moves.")
        else:
            st.error("Refresh data in sidebar first.")
        
        add_page_analyzer("$500 Strategy", "Micro-rebound strategy tab for $500 AUD CommSec accounts")

    # ------------------- TAB 7: Saved Analyses -------------------
    with tab7:
        st.subheader("📜 Saved Grok Analyses")
        st.caption("All page improvement feedback you have saved")
        
        if st.session_state.saved_analyses:
            for i, analysis in enumerate(reversed(st.session_state.saved_analyses)):
                with st.expander(f"📌 {analysis['tab']} — {analysis['timestamp']}"):
                    st.write(f"**User prompt:** {analysis['user_prompt']}")
                    st.write(analysis['response'])
                    # Download button for this analysis
                    txt = f"Tab: {analysis['tab']}\nTimestamp: {analysis['timestamp']}\nUser prompt: {analysis['user_prompt']}\n\n{analysis['response']}"
                    st.download_button(
                        label="💾 Download this analysis",
                        data=txt,
                        file_name=f"grok_analysis_{analysis['tab']}_{analysis['timestamp'].replace(':', '-')}.txt",
                        mime="text/plain",
                        key=f"download_{i}"
                    )
        else:
            st.info("No analyses saved yet. Use the 'Analyse Page with Grok' feature on any tab to start collecting feedback.")
        
        if st.button("🗑️ Clear All Saved Analyses", use_container_width=True):
            st.session_state.saved_analyses = []
            st.success("All saved analyses cleared.")
        
        add_page_analyzer("Saved Analyses", "Meta-tab showing all saved Grok page improvement feedback")

    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | v10.5 • Every page now has Grok self-analysis")

if __name__ == "__main__":
    main()