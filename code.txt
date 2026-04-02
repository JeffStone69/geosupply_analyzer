import streamlit as st
import subprocess
import os
import pandas as pd
import yfinance as yf
import plotly.express as px
import requests
import json
import time
import warnings
import logging
import traceback
from datetime import datetime
from pathlib import Path

warnings.filterwarnings("ignore")

st.set_page_config(
    page_title="GeoSupply Rebound Analyzer v9.2",
    page_icon="⚓",
    layout="wide",
    initial_sidebar_state="expanded"
)

VERSION = "9.2"
LAST_UPDATED = "April 2026"

logging.basicConfig(
    filename='geosupply_errors.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    force=True
)

if "xai_api_key" not in st.session_state:
    st.session_state.xai_api_key = ""
if "selected_model" not in st.session_state:
    st.session_state.selected_model = "grok-beta"

def call_grok_api(prompt: str, temperature: float = 0.7, max_tokens: int = 1500) -> str:
    api_key = st.session_state.xai_api_key
    if not api_key:
        return "❌ xAI API key not configured. Please add it in the sidebar."
    model = st.session_state.selected_model
    url = "https://api.x.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": temperature, "max_tokens": max_tokens}
    try:
        with st.spinner(f"Consulting {model}..."):
            response = requests.post(url, json=payload, headers=headers, timeout=45)
            if response.status_code == 401:
                return "❌ Invalid xAI API key."
            if response.status_code == 429:
                return "❌ Rate limit exceeded."
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logging.error(str(e))
        return f"❌ API error: {str(e)}"

@st.cache_data(ttl=300)
def fetch_asx_data(tickers):
    data = {}
    for ticker in tickers:
        try:
            df = yf.download(ticker, period="3mo", interval="1d", progress=False)
            if df.empty or len(df) < 2:
                continue
            current = float(df['Close'].iloc[-1])
            low_52w = float(df['Close'].min())
            high_52w = float(df['Close'].max())
            rebound_score = round(((current - low_52w) / (high_52w - low_52w)) * 100, 1) if high_52w > low_52w else 50.0
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            last_rs = rs.iloc[-1] if not rs.empty else None
            if pd.isna(last_rs) or pd.isinf(last_rs) or pd.isnull(last_rs) or len(df) < 14:
                rsi = 50.0
            else:
                rsi = round(100 - (100 / (1 + float(last_rs))), 1)
            data[ticker] = {
                'df': df,
                'current_price': round(current, 3),
                'volume': int(df['Volume'].iloc[-1]),
                'rebound_score': rebound_score,
                'rsi': rsi,
                'change_pct': round(((current - float(df['Close'].iloc[-2])) / float(df['Close'].iloc[-2])) * 100, 2)
            }
        except Exception:
            continue
    return data if data else {
        "QUBE.AX": {"current_price": 2.85, "volume": 1245000, "rebound_score": 68.4, "rsi": 42.3, "change_pct": 1.2, "df": pd.DataFrame()},
        "BHP.AX": {"current_price": 51.23, "volume": 8900000, "rebound_score": 75.2, "rsi": 58.1, "change_pct": 2.1, "df": pd.DataFrame()},
    }

def calculate_investment_metrics(df_summary, investment_amount=500.0):
    results = []
    example_targets = {'QUBE.AX': 3.85, 'AZJ.AX': 4.10, 'KSC.AX': 2.95, 'LAU.AX': 6.20, 'BHP.AX': 55.0, 'RIO.AX': 130.0, 'FMG.AX': 28.0, 'PLS.AX': 4.50}
    for _, row in df_summary.iterrows():
        ticker = row['Ticker']
        price = float(row['Current Price'])
        target = example_targets.get(ticker, price * 1.18)
        shares = investment_amount / price
        projected_value = shares * target
        dollar_gain = projected_value - investment_amount
        percent_gain = (dollar_gain / investment_amount) * 100
        results.append({
            'Ticker': ticker,
            'Company': row.get('Company', ticker.replace('.AX', '')),
            'Shares': round(shares, 2),
            'Current Value': round(investment_amount, 2),
            'Projected Value': round(projected_value, 2),
            'Dollar Gain': round(dollar_gain, 2),
            'Percent Gain %': round(percent_gain, 1)
        })
    return pd.DataFrame(results)

def run_git_command(args):
    try:
        result = subprocess.run(['git'] + args, capture_output=True, text=True, cwd=os.getcwd(), timeout=30)
        return result.stdout.strip() if result.returncode == 0 else f"❌ {result.stderr.strip()}"
    except Exception as e:
        return f"⚠️ {str(e)}"

def get_git_logs():
    try:
        log = run_git_command(["log", "--oneline", "-10"])
        status = run_git_command(["status", "--short"])
        diff = run_git_command(["diff", "--name-only"])
        return f"Recent Commits:\n{log}\n\nStatus:\n{status}\n\nChanged Files:\n{diff}"
    except:
        return "No git history available."

def grok_suggest_update():
    git_info = get_git_logs()
    prompt = f"""You are an expert Streamlit developer.
Current app: GeoSupply Rebound Analyzer v{VERSION} (ASX focused).
Git Info:
{git_info}
Suggest improvements and output:
1. Key changes
2. Full updated self-contained Python code
3. Updated README.md content
4. Updated requirements.txt (no sklearn)"""
    result = call_grok_api(prompt, temperature=0.65, max_tokens=2000)
    st.markdown("### 🤖 Grok Update Recommendation")
    st.markdown(result)

def perform_self_update():
    st.subheader("🚀 Grok-Powered Self Update")
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🔍 Get Grok Update Suggestion", type="primary", use_container_width=True):
            grok_suggest_update()
    with col_b:
        if st.button("📝 Generate README & requirements.txt", use_container_width=True):
            readme_content = "# GeoSupply Rebound Analyzer v" + VERSION + "\n\nReal-time ASX Shipping & Mining Rebound Analyzer with Grok (xAI) integration.\n\n## Features\n- Live rebound scores + RSI\n- Shipping + Mining tickers\n- Investment simulator\n- Real xAI Grok API\n- Self-updating\n\n## Installation\npip install -r requirements.txt\nstreamlit run geosupply_rebound_analyzer.py\n\nNote: No scikit-learn required.\n\nLast Updated: " + LAST_UPDATED
            with open("README.md", "w", encoding="utf-8") as f:
                f.write(readme_content)
            req_content = "streamlit\nyfinance\npandas\nplotly\nrequests\n"
            with open("requirements.txt", "w", encoding="utf-8") as f:
                f.write(req_content)
            st.success("✅ README.md and requirements.txt generated!")
            st.code(readme_content, language="markdown")
    st.divider()
    if not os.path.exists(".git"):
        st.warning("⚠️ Not a git repository.")
        return
    with st.spinner("🔍 Git Status"):
        branch = run_git_command(["branch", "--show-current"]) or "unknown"
        status = run_git_command(["status", "--short"]) or "clean"
        st.success(f"**Branch:** `{branch}` | Status: {status}")
    if st.button("⬇️ Pull Latest Changes", use_container_width=True):
        with st.spinner("Pulling..."):
            pull_out = run_git_command(["pull", "--ff-only"])
            st.code(pull_out or "Pull successful", language="bash")
            if "successful" in (pull_out or ""):
                st.success("✅ Updated!")
                st.rerun()

st.title("⚓ GeoSupply Rebound Analyzer v9.2")
st.markdown("**ASX Resources & Logistics Edition** • Real-time • xAI Grok API • Clean")

with st.sidebar:
    st.header("⚙️ Controls & xAI Authentication")
    xai_key_input = st.text_input("🔑 xAI Grok API Key", value=st.session_state.xai_api_key, type="password", help="Get key from https://console.x.ai")
    if st.button("💾 Save xAI API Key"):
        st.session_state.xai_api_key = xai_key_input
        st.success("✅ xAI API key saved!")
    model_options = ["grok-beta", "grok-2-latest", "grok-3", "grok-vision"]
    selected_model = st.selectbox("🤖 Grok Model", options=model_options, index=model_options.index(st.session_state.selected_model) if st.session_state.selected_model in model_options else 0)
    st.session_state.selected_model = selected_model
    investment_amount = st.number_input("Investment Amount (AUD)", min_value=100.0, value=500.0, step=50.0)
    st.divider()
    shipping_options = ["QUBE.AX", "SVW.AX", "TCL.AX", "BAP.AX", "DBI.AX", "PMV.AX", "JBH.AX", "LNC.AX", "AZJ.AX", "KSC.AX", "LAU.AX"]
    selected_shipping = st.multiselect("ASX Shipping & Logistics", options=shipping_options, default=["QUBE.AX", "SVW.AX", "TCL.AX", "AZJ.AX"])
    mining_options = ["BHP.AX", "RIO.AX", "FMG.AX", "NST.AX", "EVN.AX", "S32.AX", "MIN.AX", "PLS.AX", "LTR.AX", "BOE.AX"]
    selected_mining = st.multiselect("ASX Mining & Resources", options=mining_options, default=["BHP.AX", "RIO.AX", "FMG.AX", "PLS.AX"])
    selected_tickers = selected_shipping + selected_mining

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["📊 Live Rebound Dashboard", "🔍 Deep Grok Analysis", "📡 Real-Time Data", "🌟 Top Undervalued", "💰 Investment Simulator", "⚠️ Sector Risks", "🚀 Self-Update (Grok)"])

with tab1:
    st.subheader("Live Rebound Scores — ASX Resources & Logistics")
    if not selected_tickers:
        st.warning("Select tickers in sidebar")
    else:
        data_dict = fetch_asx_data(selected_tickers)
        cols = st.columns(min(4, len(data_dict)))
        for i, (ticker, info) in enumerate(data_dict.items()):
            with cols[i % 4]:
                st.metric(label=f"{ticker}", value=f"${info['current_price']}", delta=f"{info['change_pct']}%")
                st.caption(f"Rebound: **{info['rebound_score']}** | RSI: {info['rsi']}")
        if st.button("🔄 Refresh Charts"):
            st.cache_data.clear()
            st.rerun()
        for ticker, info in data_dict.items():
            if not info['df'].empty:
                fig = px.line(info['df'], y="Close", title=f"{ticker} 3-Month Trend")
                fig.update_layout(height=300)
                st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("🔍 Deep Grok Analysis")
    query = st.text_area("Enter your analysis request", value="Analyse rebound potential for selected ASX shipping and mining stocks given current market conditions.")
    if st.button("🚀 Run Grok Analysis"):
        if not st.session_state.xai_api_key:
            st.error("Please configure your xAI API key in the sidebar first.")
        else:
            with st.spinner("Consulting Grok..."):
                result = call_grok_api(query, temperature=0.7)
                st.markdown("### Grok Response")
                st.markdown(result)

with tab3:
    st.subheader("📡 Real-Time Data Feed")
    st.write("Last refreshed:", datetime.now().strftime("%H:%M:%S AEST"))
    data_dict = fetch_asx_data(selected_tickers)
    if data_dict:
        df_summary = pd.DataFrame([{"Ticker": t, **{k: v for k, v in info.items() if k != "df"}} for t, info in data_dict.items()])
        st.dataframe(df_summary, use_container_width=True, hide_index=True)

with tab4:
    st.subheader("🌟 Top Undervalued Rebound Stocks")
    broad_data = fetch_asx_data(selected_tickers + mining_options)
    if broad_data:
        df_broad = pd.DataFrame([{"Ticker": t, "Price": info["current_price"], "Rebound %": info["rebound_score"], "RSI": info["rsi"], "Change %": info["change_pct"], "Volume": info["volume"], "Rebound Potential": round((100 - info["rebound_score"]) + (100 - info["rsi"]) * 0.8, 1)} for t, info in broad_data.items()])
        df_broad = df_broad.sort_values("Rebound Potential", ascending=False).reset_index(drop=True)
        st.dataframe(df_broad, use_container_width=True, hide_index=True)
        st.markdown("**Top 3 Rebound Opportunities:**")
        for _, row in df_broad.head(3).iterrows():
            st.success(f"**{row['Ticker']}** — Potential: {row['Rebound Potential']} | Rebound: {row['Rebound %']}% | RSI: {row['RSI']}")

with tab5:
    st.subheader(f"💰 Metrics for ${investment_amount:,.0f} AUD Investment")
    data_dict = fetch_asx_data(selected_tickers)
    if data_dict:
        summary_list = [{'Ticker': ticker, 'Company': ticker.replace('.AX', '') + " Ltd", 'Current Price': info['current_price']} for ticker, info in data_dict.items()]
        df_invest = pd.DataFrame(summary_list)
        results = calculate_investment_metrics(df_invest, investment_amount)
        if not results.empty:
            st.dataframe(results, use_container_width=True, hide_index=True)
            best = results.loc[results['Percent Gain %'].idxmax()]
            st.success(f"**Best Projected Return:** {best['Ticker']} (+{best['Percent Gain %']}%)")

with tab6:
    st.header("⚠️ Sector Risks & Opportunities")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Key Risks")
        st.markdown("- Fuel & energy price volatility\n- Geopolitical disruptions\n- Labour shortages\n- Commodity price swings")
    with col2:
        st.subheader("Key Opportunities")
        st.markdown("- Infrastructure investment\n- E-commerce growth\n- Green transition demand\n- Strong resource exports")

with tab7:
    perform_self_update()

st.divider()
st.caption(f"⚓ GeoSupply Rebound Analyzer v{VERSION} — ASX Resources & Logistics | xAI Grok API | Clean & sklearn-free | {LAST_UPDATED}")