import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import numpy as np

# Configure Dashboard Layout
st.set_page_config(page_title="SG Investor ETF Dashboard", layout="wide")
st.title("📊 SG Investor ETF Dashboard: Ripin's 5-Year Alpha Strategy")
st.markdown("Optimized for **Singapore Residents**: 15% WHT & No US Estate Tax Risk.")

# ETF Universe with metadata
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
    try:
        jpy_usd = 1 / yf.Ticker("JPY=X").fast_info['last_price']
    except:
        jpy_usd = 0.0064 

    for ticker, details in etf_universe.items():
        stock = yf.Ticker(ticker)
        hist = stock.history(period="max")
        
        if not hist.empty:
            curr_p = hist['Close'].iloc[-1]
            price_usd = curr_p * jpy_usd if ".T" in ticker else curr_p
            
            def get_ann_return(years):
                days = int(years * 252) # Trading days approx
                if len(hist) >= days:
                    start_p = hist['Close'].iloc[-days]
                    return (((curr_p / start_p) ** (1/years)) - 1) * 100
                else:
                    # Fallback: Calculate Ann. Return since inception if 3y/5y not available
                    total_years = len(hist) / 252
                    start_p = hist['Close'].iloc[0]
                    return (((curr_p / start_p) ** (1/total_years)) - 1) * 100 if total_years > 0.5 else np.nan

            ret_1y = get_ann_return(1)
            ret_3y = get_ann_return(3)
            ret_5y = get_ann_return(5)
            vol = hist['Close'].pct_change().std() * np.sqrt(252) * 100
        else:
            price_usd, ret_1y, ret_3y, ret_5y, vol = [np.nan]*5

        data.append({
            "Ticker": ticker.replace(".DE", ".L"),
            "Fund Name": details["Name"],
            "Focus": details["Focus"],
            "Price (USD)": round(price_usd, 2),
            "Exp Ratio (%)": details["ER"],
            "1Y Ret (%)": round(ret_1y, 2),
            "3Y Ann (%)": round(ret_3y, 2),
            "5Y Ann (%)": round(ret_5y, 2),
            "Vol (%)": round(vol, 2),
            "Net Yield (%)": details["Yield"]
        })
    return pd.DataFrame(data)

try:
    with st.spinner("Fetching Live Market Tapes..."):
        df = fetch_etf_data()
    
    if df.empty:
        st.warning("No data fetched. Please refresh the page.")
        st.stop()
except Exception as e:
    st.error(f"Error fetching data: {str(e)}")
    st.info("The app will display sample data. Please refresh to try again.")
    # Create sample dataframe to prevent crashes
    df = pd.DataFrame({
        "Ticker": ["CSPX.L", "VWRA.L", "SWRD.L"],
        "Fund Name": ["iShares Core S&P 500", "Vanguard FTSE All-World", "SPDR MSCI World"],
        "Focus": ["US Large Cap", "Global", "Developed Markets"],
        "Price (USD)": [150.23, 120.45, 145.67],
        "Exp Ratio (%)": [0.07, 0.22, 0.12],
        "1Y Ret (%)": [25.5, 18.3, 22.1],
        "3Y Ann (%)": [15.2, 12.1, 14.5],
        "5Y Ann (%)": [12.8, 10.5, 11.9],
        "Vol (%)": [18.5, 15.2, 16.8],
        "Net Yield (%)": [1.10, 1.50, 1.41]
    })

# Sidebar for interactive filtering
st.sidebar.header("Filter Dash")
selected_focus = st.sidebar.multiselect("Select Sector", df["Focus"].unique(), default=df["Focus"].unique())
filtered_df = df[df["Focus"].isin(selected_focus)]

# 1. Performance Table
st.subheader("Performance & Fee Comparison Matrix")
st.dataframe(filtered_df.set_index("Ticker").sort_values("Exp Ratio (%)"), use_container_width=True)

st.divider()

# 2. Visual Analytics
st.subheader("Visual Analytics")
col1, col2 = st.columns(2)

with col1:
    fig_returns = px.bar(
        filtered_df, x="Ticker", y=["1Y Ret (%)", "3Y Ann (%)", "5Y Ann (%)"], 
        barmode="group", title="Return Horizons (Annualized)"
    )
    st.plotly_chart(fig_returns, use_container_width=True)

with col2:
    fig_risk = px.scatter(
        filtered_df, x="Vol (%)", y="5Y Ann (%)",
        size="Exp Ratio (%)", color="Focus", hover_name="Ticker",
        title="Risk vs. 5Y Return (Size = Expense Ratio)"
    )
    st.plotly_chart(fig_risk, use_container_width=True)