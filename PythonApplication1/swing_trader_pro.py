import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import numpy as np

st.set_page_config(page_title="High-Beta Swing Analyzer", layout="wide")
st.title("Advanced Swing Trade Confluence Scanner")
st.markdown("MA alignment · MACD momentum · ADX trend strength · Volume · Weekly confirmation")

TICKERS = [
    "NVDA", "AMD", "AVGO", "ARM", "MU", "TSM", "SMCI", "ASML", "KLAC", "LRCX", "AMAT", "TER", "ON", "MCHP", "MPWR", "MRVL", "ADI", "NXPI", "LSCC", "ALTR",
    "DELL", "HPE", "PSTG", "ANET", "VRT", "STX", "WDC", "NTAP", "SMTC", "POWI", "PLTR", "MDB", "SNOW", "DDOG", "NET", "CRWD", "ZS", "OKTA", "PANW", "WDAY",
    "TEAM", "SHOP", "TTD", "U", "PATH", "CFLT", "GFS", "ESTC", "SPLK", "DT", "COIN", "MSTR", "MARA", "RIOT", "CLSK", "HOOD", "BITF", "HUT", "CAN", "WULF",
    "PYPL", "SQ", "SOFI", "AFRM", "UPST", "NU", "MELI", "TOST", "FLYW", "BABA", "PDD", "JD", "SE", "CPNG", "KWEB", "TME", "VIPS", "LI", "XPEV",
    "MA", "V", "GPN", "FIS", "FISV", "AMZN", "NFLX", "META", "GOOGL", "DASH", "ABNB", "BKNG", "EXPE", "EBAY", "ETSY", "CVNA", "APP", "LULU", "CHWY",
    "RVLV", "BOOT", "CROX", "DECK", "DKNG", "PENN", "TKO", "UBER", "LYFT", "RCL", "CCL", "NCLH", "MAR", "HLT",
    "TSLA", "RIVN", "LCID", "NIO", "F", "GM", "ENPH", "SEDG", "FSLR", "PLUG", "FCX", "AA", "NUE", "LAC", "ALB", "MP",
    "VALE", "APA", "OXY", "DVN", "HAL", "SLB", "FANG", "MRNA", "BNTX", "VRTX", "REGN", "GILD", "AMGN", "BIIB", "ALNY",
]

def to_float(val):
    if isinstance(val, (pd.Series, np.ndarray)):
        return float(val.iloc[0] if hasattr(val, "iloc") else val[0])
    return float(val)

@st.cache_data(ttl=3600)
def fetch_analysis(ticker_list):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, ticker in enumerate(ticker_list):
        try:
            status_text.text(f"Analyzing {ticker} ({i+1}/{len(ticker_list)})...")

            # --- Daily data (6 months) ---
            df = yf.download(ticker, period="6mo", interval="1d", progress=False)
            if df.empty or len(df) < 60:
                continue

            close = df["Close"].squeeze().ffill()
            high  = df["High"].squeeze().ffill()
            low   = df["Low"].squeeze().ffill()
            vol   = df["Volume"].squeeze().ffill()

            # --- Weekly data (1 year for higher-timeframe trend) ---
            df_w = yf.download(ticker, period="1y", interval="1wk", progress=False)
            weekly_trend_ok = False
            if not df_w.empty and len(df_w) >= 20:
                wc = df_w["Close"].squeeze().ffill()
                wema20 = ta.trend.ema_indicator(wc, window=20)
                wema50 = ta.trend.ema_indicator(wc, window=50)
                if len(wema50.dropna()) > 0:
                    weekly_trend_ok = to_float(wema20.iloc[-1]) > to_float(wema50.iloc[-1])

            # --- Indicators ---
            ema20 = ta.trend.ema_indicator(close, window=20)
            ema50 = ta.trend.ema_indicator(close, window=50)
            rsi   = ta.momentum.rsi(close, window=14)
            macd  = ta.trend.MACD(close)
            atr   = ta.volatility.average_true_range(high, low, close, window=14)
            adx   = ta.trend.adx(high, low, close, window=14)
            vol_avg = vol.rolling(window=20).mean()

            # 52-week high from the daily data we already have
            high_52w = to_float(high.tail(252).max())

            # --- Current values ---
            curr_price    = to_float(close.iloc[-1])
            curr_ema20    = to_float(ema20.iloc[-1])
            curr_ema50    = to_float(ema50.iloc[-1])
            curr_rsi      = to_float(rsi.iloc[-1])
            curr_macd_line = to_float(macd.macd().iloc[-1])
            curr_macd_sig  = to_float(macd.macd_signal().iloc[-1])
            curr_macd_hist = to_float(macd.macd_diff().iloc[-1])
            curr_atr      = to_float(atr.iloc[-1])
            curr_adx      = to_float(adx.iloc[-1])
            curr_vol      = to_float(vol.iloc[-1])
            curr_vol_avg  = to_float(vol_avg.iloc[-1])
            vol_ratio     = curr_vol / curr_vol_avg if curr_vol_avg > 0 else 0

            # RSI slope — is RSI rising over the last 3 days?
            rsi_slope_up = to_float(rsi.iloc[-1]) > to_float(rsi.iloc[-4])

            # --- Conditions (each worth 1 point) ---
            # 1. Daily trend aligned
            c_trend_daily  = (curr_price > curr_ema20) and (curr_ema20 > curr_ema50)
            # 2. Weekly trend confirms
            c_trend_weekly = weekly_trend_ok
            # 3. MACD: histogram positive AND line above signal (true crossover)
            c_macd         = (curr_macd_hist > 0) and (curr_macd_line > curr_macd_sig)
            # 4. RSI: healthy zone AND rising
            c_rsi          = (50 < curr_rsi < 72) and rsi_slope_up
            # 5. Trend strength: ADX > 20 filters out choppy markets
            c_adx          = curr_adx > 20
            # 6. Volume: tightened to 1.5× for stronger conviction
            c_volume       = vol_ratio > 1.5
            # Bonus flag: near 52-week high (breakout continuation)
            near_52w_high  = curr_price >= high_52w * 0.95

            score = sum([c_trend_daily, c_trend_weekly, c_macd, c_rsi, c_adx, c_volume])

            # --- Action labels ---
            if score == 6:
                action = "STRONG BUY"
            elif score >= 4 and c_trend_daily and c_trend_weekly:
                action = "WATCH – HIGH QUALITY"
            elif score >= 3 and c_trend_daily:
                action = "WATCH – DEVELOPING"
            else:
                continue  # skip noise

            # --- Risk management ---
            stop_loss      = curr_price - (1.5 * curr_atr)
            target         = curr_price + (3.0 * curr_atr)
            risk_per_share = curr_price - stop_loss
            # Suggest position size for a $1,000 risk budget
            suggested_shares = int(1000 / risk_per_share) if risk_per_share > 0 else 0

            results.append({
                "Ticker":         ticker,
                "Action":         action,
                "Score":          f"{score}/6",
                "Price":          f"${curr_price:.2f}",
                "RSI":            round(curr_rsi, 1),
                "ADX":            round(curr_adx, 1),
                "Vol Ratio":      round(vol_ratio, 2),
                "Stop Loss":      f"${stop_loss:.2f}",
                "Target (1:2)":   f"${target:.2f}",
                "Near 52W High":  "YES" if near_52w_high else "–",
                "Shares/$1k risk": suggested_shares,
            })

        except Exception:
            continue

        progress_bar.progress((i + 1) / len(ticker_list))

    status_text.empty()
    progress_bar.empty()
    return pd.DataFrame(results)


# --- UI ---
if st.button("Run Full Market Scan"):
    df_results = fetch_analysis(TICKERS)

    if not df_results.empty:
        strong  = df_results[df_results["Action"] == "STRONG BUY"]
        watch_hq = df_results[df_results["Action"] == "WATCH – HIGH QUALITY"]
        watch_dev = df_results[df_results["Action"] == "WATCH – DEVELOPING"]

        c1, c2, c3 = st.columns(3)
        c1.metric("Strong Buy (6/6)", len(strong))
        c2.metric("High Quality Watch (4–5)", len(watch_hq))
        c3.metric("Developing Setups (3)", len(watch_dev))

        st.markdown("### Top setups — all 6 conditions met")
        if not strong.empty:
            st.dataframe(strong.sort_values("Vol Ratio", ascending=False), use_container_width=True)
        else:
            st.info("No 6/6 setups today.")

        st.markdown("### High quality watch (4–5 conditions, both trends aligned)")
        if not watch_hq.empty:
            st.dataframe(watch_hq.sort_values("Score", ascending=False), use_container_width=True)

        st.markdown("### Developing setups (3 conditions, daily trend aligned)")
        if not watch_dev.empty:
            st.dataframe(watch_dev, use_container_width=True)
    else:
        st.error("No actionable setups found, or a data error occurred.")
else:
    st.info("Click 'Run Full Market Scan' to begin.")