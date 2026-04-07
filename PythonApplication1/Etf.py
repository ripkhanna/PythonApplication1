import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import numpy as np

# Configure Dashboard Layout
st.set_page_config(page_title="SG Investor ETF Dashboard", layout="wide")
st.title("📊 SG Investor ETF Dashboard: Ripin's 5-Year Alpha Strategy")
st.markdown("Optimized for **Singapore Residents**: 15% WHT & No US Estate Tax Risk.")

# ETF Universe with metadata (Validated for April 2026)
etf_universe = {
    "CSPX.L": {"Name": "iShares Core S&P 500 (Acc)", "Focus": "US Large Cap", "ER": 0.07, "Yield": 1.10},
    "VWRA.L": {"Name": "Vanguard FTSE All-World", "Focus": "Global (Dev + EM)", "ER": 0.22, "Yield": 1.50},
    "SWRD.L": {"Name": "SPDR MSCI World", "Focus": "Developed Markets", "ER": 0.12, "Yield": 1.41},
    "ISAC.L": {"Name": "iShares MSCI ACWI", "Focus": "Global (Dev + EM)", "ER": 0.20, "Yield": 1.45},
    "VUAA.L": {"Name": "Vanguard S&P 500 (Acc)", "Focus": "US Large Cap", "ER": 0.07, "Yield": 1.15},
    "ANAU.DE": {"Name": "AXA Nasdaq 100 (Acc)", "Focus": "US Tech Growth", "ER": 0.14, "Yield": 0.70},
    "2854.T": {"Name": "Global X Japan Tech Top 20", "Focus": "Japan Tech Growth", "ER": 0.30, "Yield": 0.71},
    "1475.T": {"Name": "iShares Core TOPIX", "Focus": "Japan Broad Market", "ER": 0.05, "Yield": 1.70}
}

@st.cache_data(ttl=3600)
def fetch_etf_data():
    data = []
    # Currency conversion for Japanese Tickers
    try:
        jpy_usd = 1 / yf.Ticker("JPY=X").fast_info['last_price']
    except:
        jpy_usd = 0.0064 # Baseline rate for April 2026

    for ticker, details in etf_universe.items():
        stock = yf.Ticker(ticker)
        hist = stock.history(period="max")
        
        if not hist.empty:
            curr_p = hist['Close'].iloc[-1]
            price_usd = curr_p * jpy_usd if ".T" in ticker else curr_p
            
            # Growth Calculations
            def get_ann_return(years):
                days = int(years * 365)
                if len(hist) >= days:
                    start_p = hist['Close'].iloc[-days]
                    return (((curr_p / start_p) ** (1/years)) - 1) * 100
                return np.nan

            ret_1y = get_ann_return(1)
            ret_3y = get_ann_return(3)
            ret_5y = get_ann_return(5)
            
            # Risk Calc (Standard Deviation)
            vol = hist['Close'].pct_change().std() * np.sqrt(252) * 100
        else:
            price_usd, ret_1y, ret_3y, ret_5y, vol = [np.nan]*5

        data.append({
            "Ticker": ticker.replace(".DE", ".L"),
            "Fund Name": details["Name"],
            "Focus": details["Focus"],
            "Price (USD)": round(price_usd, 2),
            "Exp Ratio (%)": details["ER"], # Added Expense Ratio
            "1Y Ret (%)": round(ret_1y, 2),
            "3Y Ann (%)": round(ret_3y, 2),
            "5Y Ann (%)": round(ret_5y, 2),
            "Vol (%)": round(vol, 2),
            "Net Yield (%)": details["Yield"]
        })
    return pd.DataFrame(data)

with st.spinner("Fetching Live Market Tapes & Expense Data..."):
    df = fetch_etf_data()

# Dashboard UI Display
st.subheader("Performance & Fee Comparison Matrix")
# Sort by Expense Ratio by default to help you find the cheapest options
st.dataframe(df.set_index("Ticker").sort_values("Exp Ratio (%)"), use_container_width=True)

# Visual Comparison of Efficiency
st.divider()
st.subheader("Fee Efficiency vs. Performance")
fig = px.scatter(df, x="Exp Ratio (%)", y="5Y Ann (%)", size="Vol (%)", 
                 color="Focus", hover_name="Ticker", text="Ticker",
                 title="The Sweet Spot: Low Fee (Left) + High Return (Top)")
st.plotly_chart(fig, use_container_width=True)