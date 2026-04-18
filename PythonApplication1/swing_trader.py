#import os
#os.environ['REQUESTS_CA_BUNDLE'] = r"C:\FirewallCert\cert_Firewall_Root-CA_2026.crt"

import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import numpy as np
import time

# --- SETUP ---
st.set_page_config(page_title="High-Beta Swing Analyzer", layout="wide")
st.title("🚀 High-Beta Swing Trade Analyzer")
st.markdown("Scanning 100 high-volatility tickers for Trend, Momentum, and Volume confluence.")

# Copy and paste this block into your script
TICKERS = [
    "NVDA", "AMD", "AVGO", "ARM", "MU", "TSM", "SMCI", "ASML", "KLAC", "LRCX", "AMAT", "TER", "ON", "MCHP", "MPWR", "MRVL", "ADI", "NXPI", "LSCC", "ALTR",
    "DELL", "HPE", "PSTG", "ANET", "VRT", "STX", "WDC", "NTAP", "SMTC", "POWI", "PLTR", "MDB", "SNOW", "DDOG", "NET", "CRWD", "ZS", "OKTA", "PANW", "WDAY",
    "TEAM", "SHOP", "TTD", "U", "PATH", "CFLT", "GFS", "ESTC", "SPLK", "DT", "COIN", "MSTR", "MARA", "RIOT", "CLSK", "HOOD", "BITF", "HUT", "CAN", "WULF",
    "PYPL", "SQ", "SOFI", "AFRM", "UPST", "NU", "MELI", "TOST", "FLYW", "REMT", "BABA", "PDD", "JD", "SE", "CPNG", "KWEB", "TME", "VIPS", "LI", "XPEV",
    "MA", "V", "GPN", "FIS", "FISV", "AMZN", "NFLX", "META", "GOOGL", "DASH", "ABNB", "BKNG", "EXPE", "EBAY", "ETSY", "CVNA", "APP", "LULU", "SFIX", "CHWY",
    "RVLV", "BOOT", "CROX", "DECK", "BIRK", "DKNG", "PENN", "TKO", "GENI", "WYNN", "LVS", "MGM", "CZR", "BALY", "UBER", "LYFT", "RCL", "CCL", "NCLH", "MAR",
    "HLT", "WH", "TRIP", "DESP", "TSLA", "RIVN", "LCID", "NIO", "BYDDY", "F", "GM", "STLA", "RACE", "MRLN", "ENPH", "SEDG", "RUN", "FSLR", "BE", "PLUG",
    "BLNK", "CHPT", "TPIC", "STEM", "FCX", "AA", "NUE", "X", "LAC", "ALB", "MP", "SQM", "VALE", "CLF", "APA", "OXY", "DVN", "HAL", "SLB", "MRO", "FANG",
    "CHK", "EQNR", "REPX", "ILMN", "PACB", "EXAS", "BEAM", "CRSP", "NTLA", "EDIT", "TWST", "DNA", "SDGR", "MRNA", "BNTX", "VRTX", "REGN", "GILD", "AMGN",
    "SGEN", "BIIB", "ALNY", "BMRN", "TDOC", "HQY", "OSH", "CANO", "DOCS", "EVH", "PGNY", "ACCD", "RCM", "SEM"
]

def to_float(val):
    """Deep extraction of a float from a Series or scalar."""
    if isinstance(val, (pd.Series, np.ndarray)):
        return float(val.iloc[0] if hasattr(val, 'iloc') else val[0])
    return float(val)

@st.cache_data(ttl=3600)
def fetch_analysis(ticker_list):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, ticker in enumerate(ticker_list):
        try:
            status_text.text(f"Analyzing {ticker} ({i+1}/{len(ticker_list)})...")
            # We use auto_adjust=True to get a clean price column
            df = yf.download(ticker, period="1y", interval="1d", progress=False, auto_adjust=True)
            
            if df.empty or len(df) < 50:
                continue

            # CRITICAL FIX: Extract columns by position to avoid name errors
            # Close is usually index 0 or 3 depending on the yf version.
            # We ensure we have a 1D Series using .iloc and .squeeze()
            close_1d = df.iloc[:, 0].squeeze().ffill() # Takes the first column (Price)
            vol_1d = df.iloc[:, -1].squeeze().ffill()  # Takes the last column (Volume)

            # Indicators
            ema50_series = ta.trend.ema_indicator(close_1d, window=50)
            rsi_series = ta.momentum.rsi(close_1d, window=14)
            vol_avg_series = vol_1d.rolling(window=20).mean()

            # Latest Values
            curr_price = to_float(close_1d.iloc[-1])
            curr_rsi = to_float(rsi_series.iloc[-1])
            curr_ema = to_float(ema50_series.iloc[-1])
            curr_vol = to_float(vol_1d.iloc[-1])
            curr_vol_avg = to_float(vol_avg_series.iloc[-1])
            prev_rsi = to_float(rsi_series.iloc[-2])

            vol_ratio = curr_vol / curr_vol_avg

            # Logic
            is_bullish = curr_price > curr_ema
            is_momentum = 45 < curr_rsi < 65 and curr_rsi > prev_rsi
            is_vol_spike = vol_ratio > 1.15 # Slightly lower threshold to be more inclusive

            score = sum([is_bullish, is_momentum, is_vol_spike])
            
            if score == 3:
                action = "🔥 STRONG BUY"
            elif score == 2:
                action = "👀 WATCHLIST"
            else:
                action = "HOLD/WAIT"

            results.append({
                "Ticker": ticker,
                "Price": round(curr_price, 2),
                "RSI": round(curr_rsi, 1),
                "Vol Ratio": round(vol_ratio, 2),
                "Action": action
            })
        except Exception as e:
            # st.write(f"Error on {ticker}: {e}") # Uncomment for deep debugging
            continue
        
        progress_bar.progress((i + 1) / len(ticker_list))
    
    status_text.empty()
    progress_bar.empty()
    return pd.DataFrame(results)

# --- UI LOGIC ---
if st.button("🔄 Run Full Market Scan"):
    df_results = fetch_analysis(TICKERS)
    
    if not df_results.empty:
        # Summary Metrics
        strong_buys = df_results[df_results["Action"] == "🔥 STRONG BUY"]
        watchlists = df_results[df_results["Action"] == "👀 WATCHLIST"]
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Strong Buys", len(strong_buys))
        col2.metric("Watchlist", len(watchlists))
        col3.metric("Total Scanned", len(df_results))

        tab1, tab2 = st.tabs(["🎯 Top Recommendations", "📋 All Tickers"])

        with tab1:
            if not strong_buys.empty:
                st.success(f"Found {len(strong_buys)} setups with Trend, Momentum, and Volume confluence.")
                st.dataframe(strong_buys.sort_values(by="Vol Ratio", ascending=False), use_container_width=True)
            else:
                st.info("No 'Strong Buy' setups found. Showing Watchlist (2/3 criteria) instead:")
                st.dataframe(watchlists, use_container_width=True)

        with tab2:
            st.dataframe(df_results, use_container_width=True)
    else:
        st.error("No data fetched. Please check your internet connection or ticker list.")
else:
    st.info("Click the button above to start the scan.")
