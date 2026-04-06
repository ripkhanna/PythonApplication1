# import os
# from curl_cffi import requests as cffi_requests

# # Point to your exported Palo Alto / Firewall Root CA cert (PEM/CRT)
# cffi_requests.DEFAULT_VERIFY = r"P:\FirewallCert\cert_Firewall_Root-CA_2026.crt"

import os
os.environ['REQUESTS_CA_BUNDLE'] = r"C:\FirewallCert\cert_Firewall_Root-CA_2026.crt"


import streamlit as st

import yfinance as yf
import pandas as pd
import plotly.express as px
import numpy as np

# Configure Dashboard Layout
st.set_page_config(page_title="SG Investor ETF Dashboard", layout="wide")
st.title("📊 SG Investor ETF Dashboard: Target 10-12% Return")
st.markdown("Filtering for **Ireland-Domiciled UCITS ETFs** to cap US dividend withholding tax at 15%.")

# ETF Universe (LSE Tickers)
# Note: Using .DE for ANAU fetch reliability, but we will rename it in the UI.
etf_universe = {
    "CSPX.L": {"Name": "iShares Core S&P 500 (Acc)", "Sector/Focus": "US Large Cap", "ER": 0.07, "Post-Tax Yield (%)": 1.10, "Site": "ishares.com"},
    "VWRA.L": {"Name": "Vanguard FTSE All-World", "Sector/Focus": "Global (Dev + EM)", "ER": 0.22, "Post-Tax Yield (%)": 1.50, "Site": "vanguard.co.uk"},
    "SWRD.L": {"Name": "SPDR MSCI World", "Sector/Focus": "Developed Markets", "ER": 0.12, "Post-Tax Yield (%)": 1.41, "Site": "ssga.com"},
    "ISAC.L": {"Name": "iShares MSCI ACWI", "Sector/Focus": "Global (Dev + EM)", "ER": 0.20, "Post-Tax Yield (%)": 1.45, "Site": "ishares.com"},
    "VUAA.L": {"Name": "Vanguard S&P 500 (Acc)", "Sector/Focus": "US Large Cap", "ER": 0.07, "Post-Tax Yield (%)": 1.15, "Site": "vanguard.com.hk"},
    "ANAU.DE": {"Name": "AXA Nasdaq 100 (Acc)", "Sector/Focus": "US Tech Growth", "ER": 0.14, "Post-Tax Yield (%)": 0.70, "Site": "axa-im.com"}
}

@st.cache_data(ttl=3600) 
def fetch_etf_data():
    data = []
    for ticker, details in etf_universe.items():
        stock = yf.Ticker(ticker)
        
        # UI Ticker logic: Mask .DE with .L
        display_ticker = ticker.replace(".DE", ".L")
        
        hist = stock.history(period="5y")
        if not hist.empty:
            curr_price = hist['Close'].iloc[-1]
            price_1y = hist['Close'].iloc[-252] if len(hist) >= 252 else hist['Close'].iloc[0]
            price_3y = hist['Close'].iloc[0]
            
            ret_1y = ((curr_price - price_1y) / price_1y) * 100
            #ret_3y_ann = (((curr_price / price_3y) ** (1/3)) - 1) * 100
            
            days = (hist.index[-1] - hist.index[0]).days
            years = days / 365.25

            ret_3y_ann = ((curr_price / price_3y) ** (1 / years) - 1) * 100

            #--- 5Y CAGR ---
            if len(hist) >= 252 * 5:
                price_5y = hist["Close"].iloc[0]
                days_5y = (hist.index[-1] - hist.index[0]).days
                years_5y = days_5y / 365.25
                ret_5y_ann = ((curr_price / price_5y) ** (1 / years_5y) - 1) * 100
            else:
                ret_5y_ann = np.nan

            daily_returns = hist['Close'].pct_change().dropna()
            volatility_3y = daily_returns.std() * np.sqrt(252) * 100
        else:
            curr_price, ret_1y, ret_3y_ann, volatility_3y = np.nan, np.nan, np.nan, np.nan

        aum = stock.info.get('totalAssets', 'Data Unavailable')
        if isinstance(aum, (int, float)):
            aum = f"${aum / 1e9:.2f}B"

        data.append({
            "Ticker": display_ticker,
            "Fund Name": details["Name"],
            "Sector/Focus": details["Sector/Focus"],
            "Current Price (USD)": round(curr_price, 2),
            "1Y Return (%)": round(ret_1y, 2),
            "3Y Ann. Return (%)": round(ret_3y_ann, 2),
            "5Y Ann. Return (%)": round(ret_5y_ann, 2),
            "Risk: 3Y Vol (%)": round(volatility_3y, 2),
            "Yield Post-15% Tax (%)": details["Post-Tax Yield (%)"],
            "Expense Ratio (%)": details["ER"],
            "AUM": aum,
            "Fund Site": details["Site"]
        })
    return pd.DataFrame(data)

with st.spinner("Fetching live market data..."):
    df = fetch_etf_data()

# --- SIDEBAR FILTERS ---
st.sidebar.header("Sort & Filter Dashboard")
min_return = st.sidebar.slider("Min 1Y Return (%)", 0, 40, 5)
max_expense = st.sidebar.slider("Max Expense Ratio (%)", 0.05, 0.30, 0.25)
sector_filter = st.sidebar.multiselect("Focus", df["Sector/Focus"].unique(), default=df["Sector/Focus"].unique())

# Apply Filters
filtered_df = df[
    (df["1Y Return (%)"] >= min_return) & 
    (df["Expense Ratio (%)"] <= max_expense) & 
    (df["Sector/Focus"].isin(sector_filter))
]

# --- MAIN DASHBOARD AREA ---
st.subheader("Sortable ETF Comparison Table")
st.dataframe(filtered_df.set_index("Ticker"), use_container_width=True)

st.divider()
st.subheader("Visual Analytics")
col1, col2 = st.columns(2)

with col1:
    fig_returns = px.bar(
        filtered_df, x="Ticker", y=["1Y Return (%)", "3Y Ann. Return (%)","5Y Ann. Return (%)"], 
        barmode="group", title="Historical Returns Comparison"
    )
    st.plotly_chart(fig_returns, use_container_width=True)

with col2:
    fig_risk = px.scatter(
    filtered_df,
    x="Risk: 3Y Vol (%)",
    y="5Y Ann. Return (%)",
    size="Expense Ratio (%)",
    color="Sector/Focus",
    hover_name="Ticker",
    title="Risk vs. Return (Vol = 3Y)"
    )

    st.plotly_chart(fig_risk, use_container_width=True)
