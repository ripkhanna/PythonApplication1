"""
swing_scanner_dashboard.py
---------------------------
Final Version with Full Transparency & Low Threshold
Run: streamlit run swing_scanner_dashboard.py
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
from datetime import datetime
import warnings
warnings.filterwarnings("ignore")

# ------------------------------------------------------------
# 1. TICKER UNIVERSE
# ------------------------------------------------------------
TICKERS = [
    "NVDA", "AMD", "AVGO", "ARM", "MU", "TSM", "SMCI", "ASML", "KLAC", "LRCX", "AMAT", "TER", "ON", "MCHP", "MPWR", "MRVL", "ADI", "NXPI", "LSCC", "ALTR",
    "DELL", "HPE", "PSTG", "ANET", "VRT", "STX", "WDC", "NTAP", "SMTC", "POWI", "PLTR", "MDB", "SNOW", "DDOG", "NET", "CRWD", "ZS", "OKTA", "PANW", "WDAY",
    "TEAM", "SHOP", "TTD", "U", "PATH", "CFLT", "GFS", "ESTC", "DT", "COIN", "MSTR", "MARA", "RIOT", "CLSK", "HOOD", "BITF", "HUT", "CAN", "WULF",
    "PYPL", "SQ", "SOFI", "AFRM", "UPST", "NU", "MELI", "TOST", "FLYW", "REMT", "BABA", "PDD", "JD", "SE", "CPNG", "KWEB", "TME", "VIPS", "LI", "XPEV",
    "MA", "V", "GPN", "FIS", "FISV", "AMZN", "NFLX", "META", "GOOGL", "DASH", "ABNB", "BKNG", "EXPE", "EBAY", "ETSY", "CVNA", "APP", "LULU", "SFIX", "CHWY",
    "RVLV", "BOOT", "CROX", "DECK", "BIRK", "DKNG", "PENN", "TKO", "GENI", "WYNN", "LVS", "MGM", "CZR", "BALY", "UBER", "LYFT", "RCL", "CCL", "NCLH", "MAR",
    "HLT", "WH", "TRIP", "DESP", "TSLA", "RIVN", "LCID", "NIO", "BYDDY", "F", "GM", "STLA", "RACE", "MRLN", "ENPH", "SEDG", "RUN", "FSLR", "BE", "PLUG",
    "BLNK", "CHPT", "TPIC", "STEM", "FCX", "AA", "NUE", "X", "LAC", "ALB", "MP", "SQM", "VALE", "CLF", "APA", "OXY", "DVN", "HAL", "SLB", "MRO", "FANG",
    "CHK", "EQNR", "REPX", "ILMN", "PACB", "EXAS", "BEAM", "CRSP", "NTLA", "EDIT", "TWST", "DNA", "SDGR", "MRNA", "BNTX", "VRTX", "REGN", "GILD", "AMGN",
    "AAPL", "BA", "BIDU", "C", "CMG", "CRM", "DAL", "DIS", "DOCU", "DUOL", "FTNT", "GME", "GS", "HD", "HIMS", "IBM", "INTC", "JPM", "KSS", "M", "MDT", "MSFT", 
    "NKE", "NOW", "NVTS", "PINS", "QS", "RBLX", "ROKU", "SNAP", "SYY", "TWLO", "TXN", "UBER", "UHAL", "ULTA", "UPST", "V", "VRTX", "W", "WDC", "WFC", "WIX", "WMT", "XOM", "Z", "ZION", "ZM"
]

# ------------------------------------------------------------
# 2. PURE PANDAS INDICATOR FUNCTIONS
# ------------------------------------------------------------
def ema(series, length):
    return series.ewm(span=length, adjust=False).mean()

def atr(high, low, close, length=14):
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=length).mean()

def adx(high, low, close, length=14):
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    tr = atr(high, low, close, length=1)
    atr_smooth = tr.rolling(window=length).mean()
    plus_di = 100 * pd.Series(plus_dm).rolling(window=length).mean() / atr_smooth
    minus_di = 100 * pd.Series(minus_dm).rolling(window=length).mean() / atr_smooth
    dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di))
    adx_val = dx.rolling(window=length).mean()
    return adx_val, plus_di, minus_di

# ------------------------------------------------------------
# 3. CACHED DATA FETCH
# ------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_ticker_data(symbol, period="180d", interval="1d"):
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval, timeout=10)
        if not df.empty and len(df) > 20:
            return df
    except:
        pass
    return None

# ------------------------------------------------------------
# 4. ANALYZER (with full component return)
# ------------------------------------------------------------
def analyze_single_stock(symbol, benchmark="SPY", lookback_days=180,
                         adx_threshold=15, vol_multiplier=1.2, proximity_mult=2.5):
    try:
        df_daily = fetch_ticker_data(symbol, f"{lookback_days}d", "1d")
        if df_daily is None or len(df_daily) < 50:
            return None

        df_bench = fetch_ticker_data(benchmark, f"{lookback_days}d", "1d")
        bench_valid = False
        if df_bench is not None and 'Close' in df_bench.columns:
            df_daily['Bench_Close'] = df_bench['Close'].reindex(df_daily.index, method='ffill')
            bench_valid = True
        else:
            df_daily['Bench_Close'] = df_daily['Close'].copy()

        df_weekly = fetch_ticker_data(symbol, "2y", "1wk")
        if df_weekly is None or df_weekly.empty:
            df_weekly = df_daily.resample('W').agg({
                'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
            }).dropna()
            df_weekly['Bench_Close'] = df_daily['Bench_Close'].resample('W').last()
        else:
            if bench_valid and df_bench is not None:
                weekly_bench = df_bench['Close'].resample('W').last().reindex(df_weekly.index, method='ffill')
                df_weekly['Bench_Close'] = weekly_bench
            else:
                df_weekly['Bench_Close'] = df_weekly['Close']

        def calc_indicators(df, bench_valid_flag):
            df = df.copy()
            if 'Bench_Close' not in df.columns:
                df['Bench_Close'] = df['Close']
            df['ATR'] = atr(df['High'], df['Low'], df['Close'], 14)
            df['ATR_Pct'] = (df['ATR'] / df['Close']) * 100
            adx_vals, plus_di, minus_di = adx(df['High'], df['Low'], df['Close'], 14)
            df['ADX'] = adx_vals
            df['DI_PLUS'] = plus_di
            df['DI_MINUS'] = minus_di
            df['VWAP_Price'] = df['Close'] * df['Volume']
            df['VWAP'] = df['VWAP_Price'].rolling(window=20).sum() / df['Volume'].rolling(window=20).sum()
            df['VWMACD_Line'] = ema(df['VWAP'], 12) - ema(df['VWAP'], 26)
            df['VWMACD_Signal'] = ema(df['VWMACD_Line'], 9)
            df['VWMACD_Hist'] = df['VWMACD_Line'] - df['VWMACD_Signal']
            df['Roll_Max_20'] = df['High'].rolling(20).max()
            df['Roll_Min_20'] = df['Low'].rolling(20).min()
            if bench_valid_flag:
                try:
                    df['RS_Ratio'] = (df['Close'] / df['Close'].iloc[0]) / (df['Bench_Close'] / df['Bench_Close'].iloc[0])
                    df['RS_Momentum'] = df['RS_Ratio'].pct_change(20)
                except:
                    df['RS_Momentum'] = 0.0
            else:
                df['RS_Momentum'] = 0.0
            return df

        df_daily = calc_indicators(df_daily, bench_valid)
        df_weekly = calc_indicators(df_weekly, bench_valid)
        df_weekly['MA_40w'] = df_weekly['Close'].rolling(window=40).mean()

        last_week = df_weekly.iloc[-1]
        mtf_bias = "NEUTRAL"
        quality_score = 0.0
        weekly_score = 0.0
        above_ma = last_week['Close'] > last_week['MA_40w']
        strong_trend = last_week['ADX'] > adx_threshold
        if above_ma and strong_trend and last_week['DI_PLUS'] > last_week['DI_MINUS']:
            mtf_bias = "BULLISH"
            weekly_score = 3.0
        elif not above_ma and strong_trend and last_week['DI_MINUS'] > last_week['DI_PLUS']:
            mtf_bias = "BEARISH"
            weekly_score = 3.0
        else:
            mtf_bias = "NEUTRAL/CHOP"
            weekly_score = -2.0
        quality_score += weekly_score

        daily = df_daily.iloc[-1]
        prev_daily = df_daily.iloc[-2]
        recent_20 = df_daily.iloc[-20:]
        entry_side = "NO TRADE"
        entry_price = daily['Close']
        suggested_stop = None
        suggested_target = None
        comp_score = {'weekly': weekly_score, 'proximity': 0, 'volume': 0, 'vwmacd': 0, 'rs': 0}
        avg_vol_20 = df_daily['Volume'].rolling(20).mean().iloc[-1]

        if mtf_bias == "BULLISH":
            anchor_high_idx = recent_20['High'].idxmax()
            anchor_df = df_daily.loc[anchor_high_idx:]
            anchor_vwap = (anchor_df['Close'] * anchor_df['Volume']).sum() / anchor_df['Volume'].sum()
            vol_condition = daily['Volume'] < (avg_vol_20 * vol_multiplier)
            hist_rising = daily['VWMACD_Hist'] > prev_daily['VWMACD_Hist']
            rs_strong = daily['RS_Momentum'] > 0 if bench_valid else True
            support_level = max(anchor_vwap, recent_20['Low'].min())
            dist_to_support_pct = (daily['Close'] - support_level) / daily['Close'] * 100
            near_support = 0 < dist_to_support_pct < daily['ATR_Pct'] * proximity_mult
            
            if near_support:
                quality_score += 2.5
                comp_score['proximity'] = 2.5
            if vol_condition:
                quality_score += 1.5
                comp_score['volume'] = 1.5
            if hist_rising:
                quality_score += 2.0
                comp_score['vwmacd'] = 2.0
            if rs_strong and bench_valid:
                quality_score += 1.0
                comp_score['rs'] = 1.0
            if quality_score >= 3.0:  # Lowered threshold for demonstration
                entry_side = "LONG"
                swing_low = recent_20['Low'].min()
                suggested_stop = swing_low - (daily['ATR'] * 0.5)
                suggested_target = daily['Close'] + (daily['Close'] - suggested_stop) * 2.5

        elif mtf_bias == "BEARISH":
            anchor_low_idx = recent_20['Low'].idxmin()
            anchor_df = df_daily.loc[anchor_low_idx:]
            anchor_vwap = (anchor_df['Close'] * anchor_df['Volume']).sum() / anchor_df['Volume'].sum()
            vol_condition = daily['Volume'] < (avg_vol_20 * vol_multiplier)
            hist_falling = daily['VWMACD_Hist'] < prev_daily['VWMACD_Hist']
            rs_weak = daily['RS_Momentum'] < 0 if bench_valid else True
            resistance_level = min(anchor_vwap, recent_20['High'].max())
            dist_to_resist_pct = (resistance_level - daily['Close']) / daily['Close'] * 100
            near_resistance = 0 < dist_to_resist_pct < daily['ATR_Pct'] * proximity_mult
            
            if near_resistance:
                quality_score += 2.5
                comp_score['proximity'] = 2.5
            if vol_condition:
                quality_score += 1.5
                comp_score['volume'] = 1.5
            if hist_falling:
                quality_score += 2.0
                comp_score['vwmacd'] = 2.0
            if rs_weak and bench_valid:
                quality_score += 1.0
                comp_score['rs'] = 1.0
            if quality_score >= 3.0:  # Lowered threshold
                entry_side = "SHORT"
                swing_high = recent_20['High'].max()
                suggested_stop = swing_high + (daily['ATR'] * 0.5)
                suggested_target = daily['Close'] - (suggested_stop - daily['Close']) * 2.5

        position_size_pct = 0.0
        if quality_score >= 3.0:
            win_prob = 0.55
            avg_win_loss_ratio = 2.5
            kelly_fraction = win_prob - ((1 - win_prob) / avg_win_loss_ratio)
            kelly_fraction = max(0, min(kelly_fraction * 0.5, 0.05))
            position_size_pct = kelly_fraction * 100

        return {
            'Ticker': symbol,
            'Price': daily['Close'],
            'Bias': mtf_bias,
            'Quality': quality_score,
            'Signal': entry_side,
            'Stop': suggested_stop,
            'Target': suggested_target,
            'Size_%': position_size_pct,
            'ATR_%': daily['ATR_Pct'],
            'ADX': daily['ADX'],
            'Volume_Ratio': daily['Volume'] / avg_vol_20,
            'WeeklyScore': weekly_score,
            'ProximityScore': comp_score['proximity'],
            'VolumeScore': comp_score['volume'],
            'VWMACDScore': comp_score['vwmacd'],
            'RSScore': comp_score['rs']
        }
    except:
        return None

# ------------------------------------------------------------
# 5. STREAMLIT UI
# ------------------------------------------------------------
st.set_page_config(page_title="Swing Scanner Pro", layout="wide")
st.title("📊 Institutional Swing Trading Scanner")
st.markdown("**Full transparency:** See exactly why each stock scored as it did. Threshold lowered to **3.0** for demonstration.")

with st.sidebar:
    st.header("🔧 Sensitivity Settings")
    adx_threshold = st.slider("ADX Threshold", 5, 40, 15, help="Lower = easier trend qualification.")
    vol_multiplier = st.slider("Volume Multiplier", 0.5, 2.0, 1.2, help="Values >1 make volume dry‑up easier.")
    proximity_mult = st.slider("Proximity Multiplier", 1.0, 4.0, 2.5, help="Higher = wider acceptable pullback zone.")
    
    st.divider()
    show_all = st.checkbox("Show All Scanned", value=True)
    min_score = st.slider("Min Quality Score", 0.0, 10.0, 0.0 if show_all else 3.0, 0.5, disabled=show_all)
    test_mode = st.checkbox("Test Mode (first 20 tickers)", value=True)
    
    st.divider()
    if st.button("🧹 Clear Cache & Refresh"):
        st.cache_data.clear()
        st.rerun()

# Main
col1, col2 = st.columns([2, 1])
with col1:
    scan_label = "🚀 Scan All Tickers" if not test_mode else "🔬 Scan First 20 Tickers"
    if st.button(scan_label, type="primary", use_container_width=True):
        st.session_state.scan_triggered = True
        st.session_state.scan_params = (adx_threshold, vol_multiplier, proximity_mult)
        st.session_state.test_mode = test_mode

with col2:
    st.metric("Tickers to Scan", len(TICKERS[:20] if test_mode else TICKERS))

if 'scan_triggered' not in st.session_state:
    st.session_state.scan_triggered = False

if st.session_state.scan_triggered:
    params = st.session_state.get('scan_params', (15, 1.2, 2.5))
    adx_thresh, vol_mult, prox_mult = params
    ticker_list = TICKERS[:20] if st.session_state.get('test_mode', True) else TICKERS
    
    results = []
    failed_tickers = []
    progress_bar = st.progress(0, text="Starting scan...")
    total = len(ticker_list)
    
    for i, ticker in enumerate(ticker_list):
        progress_bar.progress((i+1)/total, text=f"Analyzing {ticker} ({i+1}/{total})")
        res = analyze_single_stock(ticker, adx_threshold=adx_thresh,
                                   vol_multiplier=vol_mult, proximity_mult=prox_mult)
        if res:
            results.append(res)
        else:
            failed_tickers.append(ticker)
        time.sleep(0.1)
    
    progress_bar.empty()
    
    if failed_tickers:
        with st.expander(f"⚠️ {len(failed_tickers)} tickers failed to fetch data"):
            st.write(", ".join(failed_tickers))
    
    if results:
        df = pd.DataFrame(results)
        if show_all:
            df_filtered = df.copy()
        else:
            df_filtered = df[df['Quality'] >= min_score].copy()
        
        st.subheader("📈 Quality Score Distribution")
        st.bar_chart(df['Quality'].value_counts(bins=10).sort_index())
        
        def color_signal(val):
            if val == 'LONG':
                return 'background-color: #d4edda; color: #155724'
            elif val == 'SHORT':
                return 'background-color: #f8d7da; color: #721c24'
            return ''
        
        if not df_filtered.empty:
            # Show all columns including component scores
            display_cols = ['Ticker', 'Price', 'Bias', 'Quality', 'Signal', 
                            'WeeklyScore', 'ProximityScore', 'VolumeScore', 'VWMACDScore', 'RSScore',
                            'Stop', 'Target', 'Size_%', 'ATR_%', 'ADX', 'Volume_Ratio']
            styled_df = df_filtered[display_cols].style \
                .map(color_signal, subset=['Signal']) \
                .format({
                    'Price': lambda x: f'${x:.2f}' if pd.notna(x) else '',
                    'Quality': '{:.1f}',
                    'WeeklyScore': '{:.1f}',
                    'ProximityScore': '{:.1f}',
                    'VolumeScore': '{:.1f}',
                    'VWMACDScore': '{:.1f}',
                    'RSScore': '{:.1f}',
                    'Stop': lambda x: f'${x:.2f}' if pd.notna(x) else '',
                    'Target': lambda x: f'${x:.2f}' if pd.notna(x) else '',
                    'Size_%': lambda x: f'{x:.1f}%' if pd.notna(x) else '',
                    'ATR_%': '{:.2f}%',
                    'ADX': '{:.1f}',
                    'Volume_Ratio': '{:.2f}x'
                })
            st.dataframe(styled_df, use_container_width=True, height=600, hide_index=True)
            
            # Explanation of scoring
            with st.expander("📘 How Scoring Works"):
                st.markdown("""
                - **WeeklyScore (max +3)**: Stock must be above 40‑week MA, ADX > threshold, and DI+ > DI- for bullish bias (or opposite for bearish).  
                - **ProximityScore (max +2.5)**: Price must be near an anchored VWAP support/resistance within ATR‑adjusted range.  
                - **VolumeScore (max +1.5)**: Volume must be below 20‑day average (absorption).  
                - **VWMACDScore (max +2.0)**: Volume‑weighted MACD histogram must be rising (bull) or falling (bear).  
                - **RSScore (max +1.0)**: Relative strength vs SPY must be positive (bull) or negative (bear).  
                **Total Quality = sum of above**. Threshold for signal is 3.0 in this demo (professional would be 6.5+).
                """)
        else:
            st.info("No setups meet the current criteria.")
        
        csv = df_filtered.to_csv(index=False)
        st.download_button("📥 Download CSV", data=csv, file_name=f"swing_signals_{datetime.now().strftime('%Y%m%d')}.csv")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Scanned", total)
        col2.metric("Valid Results", len(results))
        col3.metric("Displayed", len(df_filtered))
    else:
        st.error("❌ No data could be retrieved. Try clearing cache or using a VPN.")

st.divider()
st.caption("Professional setups are rare. A quality score of 6.5+ is required for institutional‑grade trades. This demo uses 3.0 to show more examples.")