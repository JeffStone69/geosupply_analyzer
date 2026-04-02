import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="ASX Logistics Dashboard", layout="wide")
st.title("ASX Logistics Sector Analysis & Investment Tool")

# ==================== SECTOR SUMMARY ====================
st.header("Sector Risks & Opportunities")
col1, col2 = st.columns(2)

with col1:
    st.subheader("Key Risks")
    st.markdown("""
    - Fuel & energy price volatility
    - Higher interest rates reducing consumer freight demand
    - Labour shortages and wage inflation
    - Geopolitical disruptions and port congestion
    - Rising environmental compliance costs
    """)

with col2:
    st.subheader("Key Opportunities")
    st.markdown("""
    - Continued e-commerce and last-mile growth
    - Government infrastructure investment (Inland Rail, ports)
    - Automation and digital transformation
    - Decarbonisation of fleets and green contracts
    - Strong resource & agricultural export volumes
    """)

st.caption("Note: This is a general overview only. Risks and opportunities evolve rapidly.")

# ==================== STOCK DATA ====================
# Example target prices (UPDATE THESE with current analyst consensus)
example_targets = {
    'QUB.AX': 3.85,   # Qube Holdings
    'AZJ.AX': 4.10,   # Aurizon Holdings
    'KSC.AX': 2.95,   # K&S Corporation
    'LAU.AX': 6.20,   # Lindsay Australia
}

tickers = list(example_targets.keys())

# Fetch live data
@st.cache_data(ttl=300)  # refresh every 5 minutes
def get_stock_data(tickers):
    data = []
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            current_price = info.get('currentPrice') or info.get('regularMarketPrice')
            if not current_price:
                current_price = stock.history(period="1d")['Close'].iloc[-1]

            target = example_targets.get(ticker, current_price * 1.15)
            upside = ((target / current_price) - 1) * 100 if current_price else 0

            data.append({
                'Ticker': ticker,
                'Company': info.get('longName', ticker),
                'Current Price': round(current_price, 3),
                'Example Target': target,
                'Est. Upside %': round(upside, 1),
                'PE Ratio': round(info.get('trailingPE', float('nan')), 2),
                'Market Cap (B)': round(info.get('marketCap', 0) / 1e9, 2)
            })
        except Exception as e:
            data.append({'Ticker': ticker, 'Company': 'Error fetching data', 'Current Price': None})
    return pd.DataFrame(data)

df = get_stock_data(tickers)

# ==================== METRICS FOR $500 INVESTMENT ====================
investment_amount = st.sidebar.number_input("Investment Amount (AUD)", 
                                          min_value=100.0, value=500.0, step=50.0)

st.header(f"Metrics for ${investment_amount:,.0f} AUD Investment")
st.caption("Example target prices are for demonstration only. Update `example_targets` dict with current analyst targets.")

results = []
for _, row in df.iterrows():
    if pd.isna(row['Current Price']):
        continue
    price = row['Current Price']
    target = row['Example Target']

    shares = investment_amount / price
    current_value = investment_amount
    projected_value = shares * target
    dollar_gain = projected_value - current_value
    percent_gain = (dollar_gain / current_value) * 100

    results.append({
        'Ticker': row['Ticker'],
        'Shares (approx)': round(shares)})
