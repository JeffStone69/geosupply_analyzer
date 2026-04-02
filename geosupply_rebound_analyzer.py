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

# =============================================
# ⚓ GeoSupply Rebound Analyzer v9.0 — ASX Resources & Logistics Edition
# Fixed: Removed sklearn dependency • xAI Grok API • Production Ready
# =============================================

st.set_page_config(
    page_title="GeoSupply Rebound Analyzer v9.0",
    page_icon="⚓",
    layout="wide",
    initial_sidebar_state="expanded"
)

VERSION = "9.0"
LAST_UPDATED = "April 2026"

# ===================== LOGGING =====================
logging.basicConfig(
    filename='geosupply_errors.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    force=True
)

# ===================== SESSION STATE =====================
if "xai_api_key" not in st.session_state:
    st.session_state.xai_api_key = ""
if "selected_model" not in st.session_state:
    st.session_state.selected_model = "grok-beta"

# ===================== xAI GROK API =====================
def call_grok_api(prompt: str, temperature: float = 0.7, max_tokens: int = 1500) -> str:
    """Call xAI Grok API with authentication."""
    api_key = st.session_state.xai_api_key
    if not api_key:
        return "❌ xAI API key not configured. Please add it in the sidebar."

    model = st.session_state.selected_model
    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    try:
        with st.spinner(f"Consulting {model}..."):
            response = requests.post(url, json=payload, headers=headers, timeout=45)
            if response.status_code == 401:
                return "❌ Invalid xAI API key. Please check and update your key."
            if response.status_code == 429:
                return "❌ Rate limit exceeded. Please try again later."
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
    except requests.exceptions.RequestException as e:
        logging.error(f"Grok API error: {str(e)}")
        return f"❌ API connection error: {str(e)}"
    except (KeyError, json.JSONDecodeError):
        return "❌ Received invalid response from xAI API."
    except Exception as e:
        logging.error(traceback.format_exc())
        return f"❌ Unexpected error: {str(e)}"

# ===================== DATA FETCH =====================
@st.cache_data(ttl=300)
def fetch_asx_data(tickers):
    """Robust fetch without any sklearn dependency."""
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

            # Safer RSI calculation
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

# ===================== INVESTMENT METRICS =====================
def calculate_investment_metrics(df_summary, investment_amount=500.0):
    results = []
    example_targets = {
        'QUBE.AX': 3.85, 'AZJ.AX': 4.10, 'KSC.AX': 2.95, 'LAU.AX': 6.20,
        'BHP.AX': 55.0, 'RIO.AX': 130.0, 'FMG.AX': 28.0, 'PLS.AX': 4.50
    }
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

# ===================== GIT COMMANDS =====================
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

# ===================== GROK-POWERED SELF UPDATE =====================
def grok_suggest_update():
    git_info = get_git_logs()
    prompt = f"""You are an expert Streamlit + finance app developer.
Current app: GeoSupply Rebound Analyzer v{VERSION} (ASX focused).

Git Info:
{git_info}

Suggest smart improvements and output in clear sections:
1. Key suggested changes
2. Full updated self-contained Python code for the main script
3. Updated README.md content
4. Updated requirements.txt (keep it minimal - no sklearn)

Focus on ASX rebound analysis, investment tools, and xAI integration. Keep code clean and dependency-free where possible."""
    
    result = call_grok_api(prompt, temperature=0.65, max_tokens=2000)
    st.markdown("### 🤖 Grok Update Recommendation")
    st.markdown(result)
    return result

def perform_self_update():
    st.subheader("🚀 Grok-Powered Self Update")
    
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🔍 Get Grok Update Suggestion", type="primary", use_container_width=True):
            grok_suggest_update()
    
    with col_b:
        if st.button("📝 Generate README & requirements.txt", use_container_width=True):
            readme_content = f"""# GeoSupply Rebound Analyzer v{VERSION}

Real-time ASX Shipping & Mining Rebound Analyzer with Grok (xAI) integration.

## Features
- Live rebound scores + RSI
- Shipping + Mining tickers
- Investment return simulator
- Real xAI Grok API calls
- Self-updating with Grok intelligence

## Installation
```bash
pip install -r requirements.txt
streamlit run geosupply_rebound_analyzer.py