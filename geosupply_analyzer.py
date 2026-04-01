#!/usr/bin/env python3
"""
ULTIMATE GEOPOLITICAL SUPPLY CHAIN + STOCK REBOUND ANALYZER v6.2
================================================================
Self-updating • Error logging • Minerals & Commodities exposure
Hormuz Strait AIS + Post-Conflict Rebound Intelligence
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import yfinance as yf
import numpy as np
import random
import traceback
import logging
import subprocess
import os

# =============================================================================
# SETUP LOGGING
# =============================================================================
logging.basicConfig(
    filename='geosupply_errors.log',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

st.set_page_config(
    page_title="GeoSupply Rebound Analyzer v6.2",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🚢"
)

# =============================================================================
# EDUCATIONAL DISCLAIMER
# =============================================================================
st.warning("⚠️ **EDUCATIONAL & ILLUSTRATIVE TOOL ONLY** — This is NOT financial advice. "
           "All data is simulated or hypothetical (2026 context). Always do your own research.")

# Dark mode
if st.sidebar.checkbox("🌙 Dark Mode", value=True):
    st.markdown("""
    <style>
        .stApp { background-color: #0E1117; color: #FAFAFA; }
        .stDataFrame, .stTable { background-color: #1E1E1E; }
    </style>
    """, unsafe_allow_html=True)

st.title("🚢 GeoSupply Rebound Analyzer v6.2")
st.markdown("**Live AIS Shipping Risk + Post-Conflict Stock Rebound + Minerals Impact**")

# =============================================================================
# SELF-UPDATE FUNCTION
# =============================================================================
def self_update():
    try:
        # CHANGE THIS TO YOUR ACTUAL REPO URL
        repo_url = "https://github.com/JeffStone69/A.git"
        
        if not os.path.exists('.git'):
            st.error("Not a git repository. Please run `git init` first.")
            return
        
        with st.spinner("Updating from GitHub..."):
            result = subprocess.run(["git", "pull", "--rebase"], 
                                  capture_output=True, text=True, cwd=os.getcwd())
            
            if result.returncode == 0:
                st.success("✅ Successfully updated! Rerunning app...")
                st.rerun()
            else:
                st.error(f"Update failed: {result.stderr}")
                logging.error(f"Git pull failed: {result.stderr}")
    except Exception as e:
        error_msg = f"Self-update error: {e}\n{traceback.format_exc()}"
        st.error(error_msg)
        logging.error(error_msg)

# Sidebar
st.sidebar.header("🔄 Self-Update & Logging")
if st.sidebar.button("🔄 Self-Update Now (Git Pull)"):
    self_update()

st.sidebar.info("Errors are automatically saved to `geosupply_errors.log`")

# =============================================================================
# SESSION STATE
# =============================================================================
if "core_shipping_tickers" not in st.session_state:
    st.session_state.core_shipping_tickers = ["ZIM", "MATX", "SBLK", "DAC", "GSL"]
if "core_tech_tickers" not in st.session_state:
    st.session_state.core_tech_tickers = ["SMCI", "NVDA", "MSFT", "MU"]

use_demo_mode = st.sidebar.checkbox("🧪 Demo Mode (2026 Hypothetical)", value=True)

# =============================================================================
# SIMULATED VESSELS (AIS)
# =============================================================================
@st.cache_data(ttl=60)
def get_simulated_vessels():
    vessels = [
        {"id": "HORMUZ-TANK-01", "vessel_name": "TI Europe", "vessel_type": "Oil Tanker",
         "location": "Strait of Hormuz", "destination": "Rotterdam", "value": 45200000,
         "impact": 92, "lat": 26.42, "lng": 56.12, "destination_congestion": 78, "weather_impact": 18},
        {"id": "HORMUZ-TANK-02", "vessel_name": "Seawise Giant", "vessel_type": "Oil Tanker",
         "location": "Strait of Hormuz", "destination": "Los Angeles", "value": 32800000,
         "impact": 88, "lat": 26.68, "lng": 56.48, "destination_congestion": 65, "weather_impact": 12},
        {"id": "HORMUZ-TANK-03", "vessel_name": "Hormuz Voyager", "vessel_type": "Oil Tanker",
         "location": "Strait of Hormuz", "destination": "Singapore", "value": 41200000,
         "impact": 95, "lat": 26.55, "lng": 56.35, "destination_congestion": 82, "weather_impact": 25},
        {"id": "HORMUZ-CONT-01", "vessel_name": "Hormuz Express", "vessel_type": "Container Ship",
         "location": "Strait of Hormuz", "destination": "Rotterdam", "value": 1850000,
         "impact": 78, "lat": 26.35, "lng": 56.05, "destination_congestion": 71, "weather_impact": 15},
    ]
    for v in vessels:
        v["impact"] = max(20, min(98, v["impact"] + random.randint(-8, 12)))
        v["destination_congestion"] = max(30, min(92, v["destination_congestion"] + random.randint(-10, 15)))
    return vessels

df_vessels = pd.DataFrame(get_simulated_vessels())

# =============================================================================
# ROBUST STOCK DATA
# =============================================================================
def fetch_stock_data(tickers):
    results = []
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            hist = stock.history(period="1mo")
            current_price = round(hist['Close'].iloc[-1], 2) if not hist.empty else None

            results.append({
                "ticker": ticker,
                "sector": info.get("sector", "Unknown"),
                "current_price": current_price or round(random.uniform(15, 150), 2),
                "target_price": info.get("targetMeanPrice") or round(random.uniform(30, 250), 2),
                "pct_down": round(random.uniform(-45, -5), 1),
                "peg": info.get("pegRatio") or round(random.uniform(0.3, 2.5), 2),
                "beta": info.get("beta") or round(random.uniform(0.8, 2.4), 2),
                "short_pct": round(random.uniform(1, 25), 1),
                "rating": info.get("recommendationKey", "Buy").title(),
                "hormuz_exposure": "High" if ticker in ["ZIM", "SBLK", "DAC"] else "Medium",
                "mineral_exposure": "High" if ticker in ["FCX", "MOS", "CF", "ALB"] else "Low"
            })
        except Exception as e:
            logging.error(f"Data fetch failed for {ticker}: {traceback.format_exc()}")
            results.append({
                "ticker": ticker, "sector": "Unknown", "current_price": 50.0, "target_price": 80.0,
                "pct_down": -25.0, "peg": 1.0, "beta": 1.5, "short_pct": 10.0, "rating": "Buy",
                "hormuz_exposure": "Medium", "mineral_exposure": "Medium"
            })
    return results

# Demo Data
shipping_demo = [
    {"ticker": "ZIM", "sector": "Shipping", "current_price": 18.45, "target_price": 28.50, "pct_down": -42.0,
     "peg": 0.35, "beta": 2.1, "short_pct": 18.4, "rating": "Buy", "hormuz_exposure": "High", "mineral_exposure": "Low"},
    {"ticker": "MATX", "sector": "Shipping", "current_price": 112.30, "target_price": 145.00, "pct_down": -18.0,
     "peg": 0.85, "beta": 1.4, "short_pct": 6.2, "rating": "Buy", "hormuz_exposure": "Medium", "mineral_exposure": "Low"},
    {"ticker": "SBLK", "sector": "Shipping", "current_price": 19.80, "target_price": 32.00, "pct_down": -35.0,
     "peg": 0.55, "beta": 1.9, "short_pct": 12.8, "rating": "Strong Buy", "hormuz_exposure": "High", "mineral_exposure": "Low"},
]

minerals_demo = [
    {"ticker": "FCX", "sector": "Mining", "current_price": 42.50, "target_price": 58.00, "pct_down": -22.0,
     "peg": 0.75, "beta": 1.6, "short_pct": 8.5, "rating": "Buy", "hormuz_exposure": "Medium", "mineral_exposure": "High"},
    {"ticker": "MOS", "sector": "Fertilizers", "current_price": 28.40, "target_price": 42.00, "pct_down": -35.0,
     "peg": 0.45, "beta": 1.9, "short_pct": 14.2, "rating": "Strong Buy", "hormuz_exposure": "High", "mineral_exposure": "High"},
    {"ticker": "CF", "sector": "Fertilizers", "current_price": 68.90, "target_price": 95.00, "pct_down": -28.0,
     "peg": 0.55, "beta": 1.4, "short_pct": 9.8, "rating": "Buy", "hormuz_exposure": "High", "mineral_exposure": "High"},
]

if use_demo_mode:
    df_shipping = pd.DataFrame(shipping_demo)
    df_minerals = pd.DataFrame(minerals_demo)
else:
    df_shipping = pd.DataFrame(fetch_stock_data(st.session_state.core_shipping_tickers))
    df_minerals = pd.DataFrame(fetch_stock_data(["FCX", "MOS", "CF"]))

# Safe Rebound Score Calculation
if not df_shipping.empty:
    df_shipping["implied_upside"] = round(
        (df_shipping["target_price"].fillna(50) / df_shipping["current_price"].fillna(50) - 1) * 100, 1
    )
    df_shipping["rebound_score"] = round(
        (-df_shipping["pct_down"].fillna(0) * 6) +
        (df_shipping["implied_upside"] * 2.5) +
        (15 / df_shipping["peg"].fillna(3)) +
        df_shipping["short_pct"].fillna(0) * 3 -
        (df_shipping["beta"].fillna(1.5) * 8), 1
    )

# =============================================================================
# TABS
# =============================================================================
tabs = st.tabs(["📊 Overview", "🚢 Live AIS", "📈 Shipping Rebound", "⛏️ Minerals", "💻 Tech", "🔗 Correlation"])

with tabs[0]:
    col1, col2, col3 = st.columns(3)
    with col1: st.metric("Active Vessels", len(df_vessels))
    with col2: st.metric("Avg Vessel Impact", f"{df_vessels['impact'].mean():.1f}%")
    with col3: 
        if not df_shipping.empty and "rebound_score" in df_shipping.columns:
            st.metric("Top Rebound Score", f"{df_shipping['rebound_score'].max():.1f}")
    
    st.subheader("Highest Rebound Candidates")
    if not df_shipping.empty:
        st.dataframe(df_shipping.nlargest(6, "rebound_score")[["ticker", "pct_down", "rebound_score", "implied_upside"]].style.format({
            "pct_down": "{:.1f}%", "rebound_score": "{:.1f}", "implied_upside": "{:.1f}%"
        }), use_container_width=True)

with tabs[1]:
    st.subheader("🚢 Live AIS Vessel Tracking (Hormuz Focus)")
    st.dataframe(df_vessels[["vessel_name", "location", "impact", "destination_congestion"]].style.format({
        "impact": "{:.0f}%", "destination_congestion": "{:.0f}%"
    }), use_container_width=True)

with tabs[2]:
    st.subheader("📈 Shipping Rebound Analysis")
    if not df_shipping.empty:
        st.dataframe(df_shipping[["ticker", "current_price", "pct_down", "implied_upside", "rebound_score", "hormuz_exposure"]].style.format({
            "current_price": "${:.2f}", "pct_down": "{:.1f}%", "implied_upside": "{:.1f}%", "rebound_score": "{:.1f}"
        }), use_container_width=True)

with tabs[3]:
    st.subheader("⛏️ Minerals & Commodities Impact")
    st.markdown("**Fertilizers, Sulphur, Aluminum, Copper** heavily affected by Hormuz disruptions.")
    if not df_minerals.empty:
        st.dataframe(df_minerals[["ticker", "sector", "pct_down", "mineral_exposure", "hormuz_exposure"]].style.format({
            "pct_down": "{:.1f}%"
        }), use_container_width=True)
    st.info("High mineral_exposure = potential price upside from supply bottlenecks.")

with tabs[4]:
    st.subheader("💻 Technology Rebound")
    st.info("Tech stocks shown for contrast (supply chain ripple effects).")

with tabs[5]:
    st.subheader("🔗 Correlation Heatmap")
    all_tickers = ["ZIM", "SBLK", "FCX", "MOS", "NVDA"]
    corr_matrix = pd.DataFrame(
        np.random.uniform(0.4, 0.95, size=(len(all_tickers), len(all_tickers))),
        index=all_tickers, columns=all_tickers
    )
    np.fill_diagonal(corr_matrix.values, 1.0)
    fig = px.imshow(corr_matrix, text_auto=True, color_continuous_scale="RdBu_r")
    st.plotly_chart(fig, use_container_width=True)

# =============================================================================
# FOOTER
# =============================================================================
st.caption(f"v6.2 • Self-updating + Error logging active • {datetime.now().strftime('%Y-%m-%d %H:%M')}")
st.success("✅ Dashboard ready. Use the Self-Update button in sidebar after pushing to GitHub.")

# Download button
csv_data = pd.concat([
    df_vessels.assign(type="Vessel"),
    df_shipping.assign(type="Stock") if not df_shipping.empty else pd.DataFrame()
]).to_csv(index=False)

st.download_button("📥 Download Full Dataset (CSV)", csv_data, "geosupply_full_data.csv", "text/csv")
