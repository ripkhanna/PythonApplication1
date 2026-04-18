import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import numpy as np

# --- SETUP ---
st.set_page_config(page_title="High-Beta Swing Analyzer", layout="wide")
st.title("🚀 Advanced Swing Trade Confluence Scanner")
st.markdown("Scanning high-beta tickers for MA Alignment, MACD Momentum, and Volume spikes.")

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
            # YF changed how multi-level indexing works, explicit column names are safer if squeezed
            df = yf.download(ticker, period="6mo", interval="1d", progress=False)
            
            if df.empty or len(df) < 60:
                continue

            # Handle robust column extraction for YF's latest updates
            close_1d = df['Close'].squeeze().ffill()
            high_1d = df['High'].squeeze().ffill()
            low_1d = df['Low'].squeeze().ffill()
            vol_1d = df['Volume'].squeeze().ffill()

            # --- INDICATORS ---
            ema20 = ta.trend.ema_indicator(close_1d, window=20)
            ema50 = ta.trend.ema_indicator(close_1d, window=50)
            rsi = ta.momentum.rsi(close_1d, window=14)
            macd = ta.trend.MACD(close_1d)
            atr = ta.volatility.average_true_range(high_1d, low_1d, close_1d, window=14)
            vol_avg = vol_1d.rolling(window=20).mean()

            # --- CURRENT VALUES ---
            curr_price = to_float(close_1d.iloc[-1])
            curr_ema20 = to_float(ema20.iloc[-1])
            curr_ema50 = to_float(ema50.iloc[-1])
            curr_rsi = to_float(rsi.iloc[-1])
            curr_macd_diff = to_float(macd.macd_diff().iloc[-1]) # MACD Histogram
            curr_atr = to_float(atr.iloc[-1])
            
            curr_vol = to_float(vol_1d.iloc[-1])
            curr_vol_avg = to_float(vol_avg.iloc[-1])
            vol_ratio = curr_vol / curr_vol_avg if curr_vol_avg > 0 else 0

            # --- SWING LOGIC ---
            # 1. Trend Alignment: Price > 20 EMA, and 20 EMA > 50 EMA
            is_trend_aligned = (curr_price > curr_ema20) and (curr_ema20 > curr_ema50)
            
            # 2. Momentum: MACD histogram is positive (bullish momentum) and RSI is healthy (not overbought)
            is_momentum = (curr_macd_diff > 0) and (50 < curr_rsi < 70)
            
            # 3. Volume: Above average volume on the recent move
            is_vol_spike = vol_ratio > 1.2

            score = sum([is_trend_aligned, is_momentum, is_vol_spike])
            
            if score == 3:
                action = "🔥 STRONG BUY"
            elif score == 2 and is_trend_aligned:
                action = "👀 PULLBACK WATCH"
            else:
                action = "HOLD/WAIT"

            # Skip junk to keep the dashboard clean
            if action == "HOLD/WAIT": continue 

            # --- RISK MANAGEMENT ---
            stop_loss = curr_price - (1.5 * curr_atr)
            target = curr_price + (3.0 * curr_atr) # 1:2 Risk Reward Ratio

            results.append({
                "Ticker": ticker,
                "Price": f"${curr_price:.2f}",
                "Action": action,
                "RSI": round(curr_rsi, 1),
                "Vol Ratio": round(vol_ratio, 2),
                "Stop Loss": f"${stop_loss:.2f}",
                "Target (1:2)": f"${target:.2f}",
                "ATR": round(curr_atr, 2)
            })
            
        except Exception as e:
            continue
        
        progress_bar.progress((i + 1) / len(ticker_list))
    
    status_text.empty()
    progress_bar.empty()
    return pd.DataFrame(results)

# --- UI LOGIC ---
if st.button("🔄 Run Full Market Scan"):
    df_results = fetch_analysis(TICKERS)
    
    if not df_results.empty:
        strong_buys = df_results[df_results["Action"] == "🔥 STRONG BUY"]
        watchlists = df_results[df_results["Action"] == "👀 PULLBACK WATCH"]
        
        col1, col2 = st.columns(2)
        col1.metric("Strong Confluence Setups", len(strong_buys))
        col2.metric("Watchlist (Waiting for Trigger)", len(watchlists))

        st.markdown("### 🎯 Top Trade Setups")
        if not strong_buys.empty:
            st.dataframe(strong_buys.sort_values(by="Vol Ratio", ascending=False), use_container_width=True)
        else:
            st.info("No 'Strong Buy' setups found today.")

        st.markdown("### 📋 Watchlist (Trend aligned, waiting on Volume/Momentum)")
        if not watchlists.empty:
            st.dataframe(watchlists, use_container_width=True)

    else:
        st.error("No actionable setups found today, or there was an error fetching data.")
else:
    st.info("Click 'Run Full Market Scan' to begin analyzing the market.")