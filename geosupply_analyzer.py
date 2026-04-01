#!/usr/bin/env python3
"""
GeoSupply Rebound Analyzer v6.2 - Final SSH-ready Version
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import yfinance as yf
import numpy as np
import random
import traceback
import logging
import subprocess
import os

logging.basicConfig(filename='geosupply_errors.log', level=logging.ERROR,
                    format='%(asctime)s - %(levelname)s - %(message)s')

st.set_page_config(page_title="GeoSupply v6.2", layout="wide", page_icon="🚢")

st.warning("⚠️ EDUCATIONAL TOOL ONLY — Not financial advice.")

if st.sidebar.checkbox("🌙 Dark Mode", value=True):
    st.markdown('<style>.stApp { background-color: #0E1117; color: #FAFAFA; }</style>', unsafe_allow_html=True)

st.title("🚢 GeoSupply Rebound Analyzer v6.2")
st.caption("Hormuz AIS + Shipping + Minerals Impact Analysis")

# ===================== SELF UPDATE (Your Repo) =====================
def self_update():
    try:
        if not os.path.exists('.git'):
            st.error("Not a git repository.")
            return
        with st.spinner("Pulling latest from GitHub..."):
            result = subprocess.run(["git", "pull", "--rebase"], capture_output=True, text=True)
            if result.returncode == 0:
                st.success("✅ Updated successfully! Rerunning app...")
                st.rerun()
            else:
                st.error(f"Update failed:\n{result.stderr}")
    except Exception as e:
        st.error(f"Self-update error: {e}")
        logging.error(traceback.format_exc())

st.sidebar.header("🔄 Self Update")
if st.sidebar.button("🔄 Self-Update from GitHub"):
    self_update()

use_demo_mode = st.sidebar.checkbox("🧪 Demo Mode", value=True)

# Simulated Vessels
@st.cache_data(ttl=60)
def get_simulated_vessels():
    vessels = [
        {"vessel_name": "TI Europe", "location": "Strait of Hormuz", "impact": 92, "destination_congestion": 78},
        {"vessel_name": "Seawise Giant", "location": "Strait of Hormuz", "impact": 88, "destination_congestion": 65},
        {"vessel_name": "Hormuz Voyager", "location": "Strait of Hormuz", "impact": 95, "destination_congestion": 82},
    ]
    for v in vessels:
        v["impact"] = max(20, min(98, v["impact"] + random.randint(-8,12)))
    return vessels

df_vessels = pd.DataFrame(get_simulated_vessels())

# Demo Data
shipping_demo = [
    {"ticker": "ZIM", "sector": "Shipping", "current_price": 18.45, "target_price": 28.50, "pct_down": -42.0, "peg": 0.35, "rebound_score": 78.5, "hormuz_exposure": "High"},
    {"ticker": "SBLK", "sector": "Shipping", "current_price": 19.80, "target_price": 32.00, "pct_down": -35.0, "peg": 0.55, "rebound_score": 82.3, "hormuz_exposure": "High"},
]

minerals_demo = [
    {"ticker": "FCX", "sector": "Mining", "pct_down": -22.0, "mineral_exposure": "High"},
    {"ticker": "MOS", "sector": "Fertilizers", "pct_down": -35.0, "mineral_exposure": "High"},
]

df_shipping = pd.DataFrame(shipping_demo)
df_minerals = pd.DataFrame(minerals_demo)

tabs = st.tabs(["Overview", "🚢 Live AIS", "📈 Shipping Rebound", "⛏️ Minerals", "🔗 Correlation"])

with tabs[0]:
    col1, col2 = st.columns(2)
    with col1: st.metric("Active Vessels", len(df_vessels))
    with col2: st.metric("Avg Vessel Impact", f"{df_vessels['impact'].mean():.1f}%")

with tabs[1]:
    st.dataframe(df_vessels)

with tabs[2]:
    st.dataframe(df_shipping.style.format({"pct_down": "{:.1f}%", "rebound_score": "{:.1f}"}))

with tabs[3]:
    st.subheader("⛏️ Minerals Impacted by Hormuz Conflict")
    st.dataframe(df_minerals)

with tabs[4]:
    st.info("Correlation heatmap (placeholder)")

st.caption(f"v6.2 • SSH enabled • {datetime.now().strftime('%Y-%m-%d %H:%M')}")
st.success("✅ App ready. Use Self-Update button after pushing changes.")

# Download
st.download_button("📥 Download Dataset", 
                   pd.concat([df_vessels.assign(type="Vessel"), df_shipping.assign(type="Stock")]).to_csv(index=False),
                   "geosupply_data.csv")