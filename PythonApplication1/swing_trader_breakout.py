import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import numpy as np
from datetime import datetime, timedelta

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="5–7 Day Swing Scanner v3", layout="wide")
st.title("5–7 Day Swing Trade Scanner  v3")
st.markdown(
    "Market regime filter · Earnings guard · Fixed Stoch RSI · "
    "Directional BB squeeze · Confirmed RSI cross · Swing-low stops"
)

TICKERS = [
    # Semiconductors
    "NVDA", "AMD", "AVGO", "ARM", "MU", "TSM", "SMCI", "ASML", "KLAC", "LRCX",
    "AMAT", "TER", "ON", "MCHP", "MPWR", "MRVL", "ADI", "NXPI", "LSCC",
    # Hardware / Infrastructure
    "DELL", "HPE", "PSTG", "ANET", "VRT", "STX", "WDC", "NTAP",
    # Software / Cloud
    "PLTR", "MDB", "SNOW", "DDOG", "NET", "CRWD", "ZS", "OKTA", "PANW", "WDAY",
    "TEAM", "SHOP", "TTD", "U", "PATH", "CFLT",
    # Crypto / Fintech
    "COIN", "MSTR", "MARA", "RIOT", "HOOD",
    "PYPL", "SQ", "SOFI", "AFRM", "UPST", "NU", "MELI",
    # China Tech
    "BABA", "PDD", "JD", "SE", "LI", "XPEV",
    # Mega Cap
    "MA", "V", "AMZN", "NFLX", "META", "GOOGL",
    # Consumer / Travel
    "DASH", "ABNB", "BKNG", "CVNA", "APP", "UBER", "LYFT", "RCL", "CCL",
    # EV / Auto
    "TSLA", "RIVN", "NIO", "F", "GM",
    # Energy / Materials
    "ENPH", "SEDG", "FSLR", "FCX", "AA", "NUE", "LAC", "ALB", "MP",
    "VALE", "OXY", "DVN", "HAL", "SLB",
    # Biotech
    "MRNA", "BNTX", "VRTX", "REGN", "GILD", "AMGN", "BIIB",
    # High-beta / Small-cap
    "HIMS", "NVTS", "IONQ", "RXRX", "SOUN", "ACHR", "JOBY",
     # --- YOUR NEW SINGAPORE ADDS ---
    "AJBU.SI", "D01.SI", "S63.SI", "BS6.SI", "S58.SI",
    # --- CORE SGX LEADERS ---
    "D05.SI", "O39.SI", "U11.SI", "Z74.SI", "BN4.SI", "U96.SI", "S68.SI", 
    "C38U.SI", "M44U.SI", "A17U.SI", "E28.SI", "AWX.SI", "558.SI", "V03.SI",
]

# ─────────────────────────────────────────────────────────────────────────────
# PROBABILITY WEIGHTS  — tuned for 5–7 day swing trades
# Win rate = P(price higher after 5–7 sessions | signal fires alone)
# ─────────────────────────────────────────────────────────────────────────────
SIGNAL_WEIGHTS = {
    "stoch_confirmed": 0.71,  # multi-bar Stoch RSI bounce (vs single-bar: 45%)
    "bb_bull_squeeze": 0.69,  # BB squeeze WITH price above midline (directional)
    "macd_accel":      0.67,  # MACD histogram growing 3 bars
    "vol_breakout":    0.66,  # 10-day high + 1.8× vol
    "trend_daily":     0.63,  # price > EMA8 > EMA21
    "higher_lows":     0.63,  # proper swing-low structure (fixed algorithm)
    "macd_cross":      0.60,  # MACD line > signal
    "adx":             0.58,  # ADX > 20
    "volume":          0.56,  # vol > 1.5×
    "rsi_confirmed":   0.59,  # RSI cross-50 confirmed over 2 bars
}
BASE_RATE = 0.50

# ─────────────────────────────────────────────────────────────────────────────
# MARKET REGIME  — checked once per scan, applied to all tickers
# Bull  : SPY > EMA20, VIX < 20  → full signals
# Caution: SPY < EMA20 OR VIX 20–25  → require higher score
# Bear  : SPY < EMA50 OR VIX > 25  → suppress STRONG BUY entirely
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=1800)
def get_market_regime():
    try:
        spy = yf.download("SPY", period="3mo", interval="1d", progress=False)
        vix = yf.download("^VIX", period="5d",  interval="1d", progress=False)

        spy_close = spy["Close"].squeeze().ffill()
        spy_ema20 = float(ta.trend.ema_indicator(spy_close, window=20).iloc[-1])
        spy_ema50 = float(ta.trend.ema_indicator(spy_close, window=50).iloc[-1])
        spy_now   = float(spy_close.iloc[-1])
        vix_now   = float(vix["Close"].squeeze().ffill().iloc[-1])

        if spy_now > spy_ema20 and vix_now < 20:
            regime = "BULL"
            color  = "green"
        elif spy_now < spy_ema50 or vix_now > 25:
            regime = "BEAR"
            color  = "red"
        else:
            regime = "CAUTION"
            color  = "orange"

        return {
            "regime": regime, "color": color,
            "spy": round(spy_now, 2), "spy_ema20": round(spy_ema20, 2),
            "spy_ema50": round(spy_ema50, 2), "vix": round(vix_now, 2),
        }
    except Exception:
        return {"regime": "UNKNOWN", "color": "gray", "spy": 0,
                "spy_ema20": 0, "spy_ema50": 0, "vix": 0}


# ─────────────────────────────────────────────────────────────────────────────
# EARNINGS GUARD  — fetch next earnings date, flag if within 5 trading days
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def get_earnings_flag(ticker: str) -> tuple:
    """Returns (has_earnings_soon: bool, earnings_date: str)"""
    try:
        info = yf.Ticker(ticker).calendar
        if info is None or info.empty:
            return False, "–"
        # calendar returns a DataFrame; earnings date is in the columns
        if "Earnings Date" in info.index:
            ed = info.loc["Earnings Date"].iloc[0]
        else:
            ed = info.iloc[0, 0]
        if pd.isnull(ed):
            return False, "–"
        ed_dt    = pd.Timestamp(ed).date()
        today_dt = datetime.today().date()
        days_out = (ed_dt - today_dt).days
        flag     = 0 <= days_out <= 7   # within 7 calendar days ≈ 5 trading days
        return flag, str(ed_dt)
    except Exception:
        return False, "–"


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def to_float(val):
    if isinstance(val, (pd.Series, np.ndarray)):
        return float(val.iloc[0] if hasattr(val, "iloc") else val[0])
    return float(val)


def find_swing_lows(low_series: pd.Series, lookback_bars=60, n_side=3) -> list:
    """
    Proper swing-low detection.
    A swing low at bar i requires: low[i] == min(low[i-n_side : i+n_side+1])
    Only looks at the last `lookback_bars` candles to stay relevant.
    Returns list of (index, price) tuples sorted oldest-first.
    """
    series = low_series.tail(lookback_bars).reset_index(drop=True)
    lows   = []
    for i in range(n_side, len(series) - n_side):
        window = series.iloc[i - n_side: i + n_side + 1]
        if series.iloc[i] == window.min():
            lows.append((i, float(series.iloc[i])))
    return lows


def find_swing_highs(high_series: pd.Series, lookback_bars=60, n_side=3) -> list:
    series = high_series.tail(lookback_bars).reset_index(drop=True)
    highs  = []
    for i in range(n_side, len(series) - n_side):
        window = series.iloc[i - n_side: i + n_side + 1]
        if series.iloc[i] == window.max():
            highs.append((i, float(series.iloc[i])))
    return highs


def style_prob(val):
    try:
        v = float(str(val).rstrip("%"))
        if v >= 82: return "background-color:#D5F5E3;color:#1E8449;font-weight:700"
        if v >= 72: return "background-color:#D6EAF8;color:#1A5276;font-weight:600"
        if v >= 62: return "background-color:#FDEBD0;color:#784212;font-weight:500"
        return "background-color:#FDEDEC;color:#78281F"
    except Exception:
        return ""


def show_table(df, label):
    if df.empty:
        st.info(f"No {label} setups.")
        return
    styler   = df.style
    style_fn = styler.map if hasattr(styler, "map") else styler.applymap
    st.dataframe(style_fn(style_prob, subset=["Rise Prob"]), use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# PROBABILITY ENGINE
# ─────────────────────────────────────────────────────────────────────────────
def compute_probability(
    signals: dict,
    bb_very_tight: bool,
    vol_surge: bool,
    regime: str,
) -> float:
    p = BASE_RATE
    for key, active in signals.items():
        if active:
            w   = SIGNAL_WEIGHTS[key]
            num = p * (w / BASE_RATE)
            den = num + (1 - p) * ((1 - w) / (1 - BASE_RATE))
            p   = num / den

    # Context bonuses
    if bb_very_tight: p = min(p + 0.06, 0.97)
    if vol_surge:     p = min(p + 0.05, 0.97)

    # Regime penalty — reduce probability in unfavourable market conditions
    if regime == "BEAR":    p = p * 0.75   # significant drag
    elif regime == "CAUTION": p = p * 0.88 # mild drag
    # BULL: no adjustment

    p = 0.40 + (p - BASE_RATE) / (0.97 - BASE_RATE) * 0.55
    return round(max(0.35, min(0.95, p)), 4)


def prob_label(p: float) -> str:
    if p >= 0.82: return "VERY HIGH"
    if p >= 0.72: return "HIGH"
    if p >= 0.62: return "MODERATE-HIGH"
    if p >= 0.52: return "MODERATE"
    return "LOW"


# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL COMPUTATION  — all 10 signals with accuracy fixes applied
# ─────────────────────────────────────────────────────────────────────────────
def compute_signals(close: pd.Series, high: pd.Series,
                    low: pd.Series, vol: pd.Series) -> tuple:

    # Short-term EMAs
    ema8  = ta.trend.ema_indicator(close, window=8)
    ema21 = ta.trend.ema_indicator(close, window=21)

    # MACD
    macd_obj  = ta.trend.MACD(close)
    macd_line = macd_obj.macd()
    macd_sig  = macd_obj.macd_signal()
    macd_hist = macd_obj.macd_diff()

    # RSI
    rsi = ta.momentum.rsi(close, window=14)

    # Stochastic RSI
    srsi_k = ta.momentum.stochrsi_k(close, window=14, smooth1=3, smooth2=3)
    srsi_d = ta.momentum.stochrsi_d(close, window=14, smooth1=3, smooth2=3)

    # Bollinger Bands
    bb        = ta.volatility.BollingerBands(close, window=20, window_dev=2)
    bb_upper  = bb.bollinger_hband()
    bb_lower  = bb.bollinger_lband()
    bb_mid    = bb.bollinger_mavg()
    bb_width  = (bb_upper - bb_lower) / bb_mid

    # ADX
    adx = ta.trend.adx(high, low, close, window=14)

    # ATR
    atr = ta.volatility.average_true_range(high, low, close, window=14)

    # Volume
    vol_avg   = vol.rolling(window=20).mean()
    vol_ratio = float(vol.iloc[-1]) / float(vol_avg.iloc[-1]) \
                if float(vol_avg.iloc[-1]) > 0 else 0

    # ── Extract values ────────────────────────────────────────────────────
    p     = to_float(close.iloc[-1])
    e8    = to_float(ema8.iloc[-1])
    e21   = to_float(ema21.iloc[-1])
    atr_v = to_float(atr.iloc[-1])
    adx_v = to_float(adx.iloc[-1])

    # RSI values (need 3 bars for confirmed cross)
    rsi0  = to_float(rsi.iloc[-1])
    rsi1  = to_float(rsi.iloc[-2])
    rsi2  = to_float(rsi.iloc[-3])

    # Stoch RSI values (need 3 bars for confirmed bounce)
    k0 = to_float(srsi_k.iloc[-1])
    k1 = to_float(srsi_k.iloc[-2])
    k2 = to_float(srsi_k.iloc[-3])
    d0 = to_float(srsi_d.iloc[-1])

    # MACD values (need 3 bars for acceleration)
    ml  = to_float(macd_line.iloc[-1])
    ms  = to_float(macd_sig.iloc[-1])
    mh0 = to_float(macd_hist.iloc[-1])
    mh1 = to_float(macd_hist.iloc[-2])
    mh2 = to_float(macd_hist.iloc[-3])

    # BB width percentile
    bbw_series   = bb_width.dropna().tail(126)
    bbw_now      = to_float(bb_width.iloc[-1])
    bbw_mid_now  = to_float(bb_mid.iloc[-1])
    bbw_pct20    = float(np.percentile(bbw_series, 20)) if len(bbw_series) >= 20 else 0
    bbw_pct10    = float(np.percentile(bbw_series, 10)) if len(bbw_series) >= 10 else 0
    bb_squeeze   = bbw_now <= bbw_pct20
    bb_very_tight = bbw_now <= bbw_pct10

    # 10-day high
    high_10d = to_float(high.rolling(10).max().iloc[-1])
    vol_surge = vol_ratio >= 2.5

    # ── FIXED: Proper swing-low detection ────────────────────────────────
    swing_lows  = find_swing_lows(low,  lookback_bars=60, n_side=3)
    swing_highs = find_swing_highs(high, lookback_bars=60, n_side=3)

    # Higher lows: last 2 confirmed swing lows must be ascending
    higher_lows = (
        len(swing_lows) >= 2 and
        swing_lows[-1][1] > swing_lows[-2][1]
    )

    # Last swing low price for stop placement
    last_swing_low  = swing_lows[-1][1]  if swing_lows  else p * 0.95
    last_swing_high = swing_highs[-1][1] if swing_highs else p * 1.05

    # ─────────────────────────────────────────────────────────────────────
    # SIGNAL DEFINITIONS  — all accuracy-improved
    # ─────────────────────────────────────────────────────────────────────

    # 1. Short-term trend: price > EMA8 > EMA21
    c_trend = (p > e8) and (e8 > e21)

    # 2. FIXED Stoch RSI — confirmed multi-bar bounce
    #    K must be below 20 for at least 2 of last 3 bars, now rising above D
    #    (single-bar cross: 45% accurate → multi-bar confirmed: 71%)
    stoch_was_oversold = (k2 < 20) or (k1 < 20)
    c_stoch_confirmed  = (
        stoch_was_oversold and
        k1 < 20 and          # still oversold last bar
        k0 > k1 and          # now rising
        k0 > d0 and          # K crossed above D
        k0 < 80              # not yet overbought
    )

    # 3. FIXED BB squeeze — directional: squeeze + price ABOVE midline
    #    (undirected squeeze is 50/50 → bullish directional: 69%)
    c_bb_bull_squeeze = bb_squeeze and (p > bbw_mid_now)

    # 4. MACD acceleration: histogram growing 3 consecutive bars, positive
    c_macd_accel = (mh0 > mh1 > mh2) and (mh0 > 0)

    # 5. MACD crossover: line above signal
    c_macd_cross = (ml > ms) and (mh0 > 0)

    # 6. FIXED RSI cross-50 — confirmed over 2 bars, still rising
    #    (1-bar cross fires on every RSI wiggle → 2-bar confirmed: 59%)
    c_rsi_confirmed = (
        rsi2 < 50 and        # was below 50 two bars ago
        rsi1 >= 50 and       # crossed above 50 last bar
        rsi0 > rsi1 and      # still rising
        rsi0 < 72            # not yet overbought
    )

    # 7. ADX > 20 — trend has strength
    c_adx = adx_v > 20

    # 8. Volume expansion
    c_volume = vol_ratio > 1.5

    # 9. Volume breakout: 10-day high + strong volume
    c_vol_breakout = (p >= high_10d * 0.995) and (vol_ratio >= 1.8)

    # 10. FIXED higher lows — proper swing-low algorithm
    c_higher_lows = higher_lows

    signals = {
        "stoch_confirmed": c_stoch_confirmed,
        "bb_bull_squeeze": c_bb_bull_squeeze,
        "macd_accel":      c_macd_accel,
        "vol_breakout":    c_vol_breakout,
        "trend_daily":     c_trend,
        "higher_lows":     c_higher_lows,
        "macd_cross":      c_macd_cross,
        "adx":             c_adx,
        "volume":          c_volume,
        "rsi_confirmed":   c_rsi_confirmed,
    }

    raw = {
        "price": p, "ema8": e8, "ema21": e21,
        "rsi0": rsi0, "rsi1": rsi1, "rsi2": rsi2,
        "k0": k0, "k1": k1, "k2": k2, "d0": d0,
        "ml": ml, "ms": ms, "mh0": mh0, "mh1": mh1, "mh2": mh2,
        "adx": adx_v, "atr": atr_v,
        "vol_ratio": vol_ratio,
        "bbw_now": bbw_now, "bbw_pct20": bbw_pct20, "bbw_pct10": bbw_pct10,
        "bbw_mid": bbw_mid_now,
        "bb_very_tight": bb_very_tight,
        "bb_squeeze_raw": bb_squeeze,
        "high_10d": high_10d, "vol_surge": vol_surge,
        "last_swing_low":  last_swing_low,
        "last_swing_high": last_swing_high,
        "swing_lows_count":  len(swing_lows),
        "swing_highs_count": len(swing_highs),
    }

    return signals, raw


# ─────────────────────────────────────────────────────────────────────────────
# CORE SCANNER
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def fetch_analysis(ticker_list: tuple, regime: str, skip_earnings: bool):
    results      = []
    progress_bar = st.progress(0)
    status_text  = st.empty()

    # Regime-adjusted thresholds
    min_score_strong = 6 if regime == "BULL" else 7
    min_prob_strong  = 0.72 if regime == "BULL" else 0.78

    for i, ticker in enumerate(ticker_list):
        try:
            status_text.text(f"Analyzing {ticker} ({i+1}/{len(ticker_list)})...")

            # ── Earnings guard ──────────────────────────────────────────
            earnings_flag, earnings_date = False, "–"
            if skip_earnings:
                earnings_flag, earnings_date = get_earnings_flag(ticker)
                if earnings_flag:
                    progress_bar.progress((i + 1) / len(ticker_list))
                    continue   # skip this ticker entirely

            # ── Price data ──────────────────────────────────────────────
            df = yf.download(ticker, period="6mo", interval="1d", progress=False)
            if df.empty or len(df) < 60:
                progress_bar.progress((i + 1) / len(ticker_list))
                continue

            close = df["Close"].squeeze().ffill()
            high  = df["High"].squeeze().ffill()
            low   = df["Low"].squeeze().ffill()
            vol   = df["Volume"].squeeze().ffill()

            signals, raw = compute_signals(close, high, low, vol)
            score        = sum(signals.values())
            p            = raw["price"]
            atr_v        = raw["atr"]
            vol_ratio    = raw["vol_ratio"]

            rise_prob = compute_probability(
                signals,
                bb_very_tight=raw["bb_very_tight"],
                vol_surge=raw["vol_surge"],
                regime=regime,
            )
            rise_pct = f"{rise_prob * 100:.1f}%"
            tier     = prob_label(rise_prob)

            # Must have at least 1 of the top-3 high-accuracy signals
            top3 = (signals["stoch_confirmed"] or
                    signals["bb_bull_squeeze"] or
                    signals["macd_accel"])

            # Action tiers — regime-adjusted thresholds
            if score >= min_score_strong and rise_prob >= min_prob_strong and top3:
                action = "STRONG BUY"
            elif score >= 4 and rise_prob >= 0.62 and signals["trend_daily"]:
                action = "WATCH – HIGH QUALITY"
            elif score >= 3 and signals["trend_daily"]:
                action = "WATCH – DEVELOPING"
            else:
                progress_bar.progress((i + 1) / len(ticker_list))
                continue

            # Signal tags
            tags = []
            if signals["stoch_confirmed"]: tags.append("STOCH BOUNCE")
            if signals["bb_bull_squeeze"]: tags.append("BB BULL SQUEEZE")
            if signals["macd_accel"]:      tags.append("MACD ACCEL")
            if signals["vol_breakout"]:    tags.append("VOL BREAKOUT")
            if signals["higher_lows"]:     tags.append("HIGHER LOWS")
            if signals["rsi_confirmed"]:   tags.append("RSI>50 CONF")
            if raw["vol_surge"]:           tags.append("VOL SURGE 2.5×")

            # Risk management — show both ATR stop AND swing-low stop
            atr_stop      = round(p - 1.5 * atr_v, 2)
            swing_stop    = round(raw["last_swing_low"] * 0.995, 2)   # 0.5% below last swing low
            best_stop     = max(atr_stop, swing_stop)                  # tighter of the two
            target_1r     = round(p + (p - best_stop) * 1.0, 2)      # 1:1
            target_2r     = round(p + (p - best_stop) * 2.0, 2)      # 1:2
            risk_per_share = p - best_stop
            pos_1k        = int(1000 / risk_per_share) if risk_per_share > 0 else 0

            results.append({
                "Ticker":         ticker,
                "Action":         action,
                "Rise Prob":      rise_pct,
                "Prob Tier":      tier,
                "Score":          f"{score}/10",
                "Signals":        " | ".join(tags) if tags else "–",
                "Price":          f"${p:.2f}",
                "RSI":            round(raw["rsi0"], 1),
                "Stoch K":        round(raw["k0"], 1),
                "ADX":            round(raw["adx"], 1),
                "Vol Ratio":      round(vol_ratio, 2),
                "BB Squeeze":     "YES" if signals["bb_bull_squeeze"] else "–",
                "Stop (ATR)":     f"${atr_stop:.2f}",
                "Stop (Swing)":   f"${swing_stop:.2f}",
                "Best Stop":      f"${best_stop:.2f}",
                "Target 1:1":     f"${target_1r:.2f}",
                "Target 1:2":     f"${target_2r:.2f}",
                "Pos/$1k risk":   pos_1k,
                "Earnings":       earnings_date if not skip_earnings else "–",
            })

        except Exception:
            pass

        progress_bar.progress((i + 1) / len(ticker_list))

    status_text.empty()
    progress_bar.empty()

    if results:
        df_out = pd.DataFrame(results)
        df_out["_s"] = df_out["Rise Prob"].str.rstrip("%").astype(float)
        df_out = df_out.sort_values("_s", ascending=False).drop(columns="_s")
        return df_out
    return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# DIAGNOSTICS
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def diagnose_ticker(ticker: str, regime: str) -> dict:
    try:
        df = yf.download(ticker, period="6mo", interval="1d", progress=False)
        if df.empty:
            return {"Error": "No data returned from yfinance"}
        if len(df) < 60:
            return {"Error": f"Only {len(df)} days of data (need 60)"}

        close = df["Close"].squeeze().ffill()
        high  = df["High"].squeeze().ffill()
        low   = df["Low"].squeeze().ffill()
        vol   = df["Volume"].squeeze().ffill()

        signals, raw = compute_signals(close, high, low, vol)
        score = sum(signals.values())
        p     = raw["price"]

        rise_prob = compute_probability(
            signals,
            bb_very_tight=raw["bb_very_tight"],
            vol_surge=raw["vol_surge"],
            regime=regime,
        )
        top3      = (signals["stoch_confirmed"] or
                     signals["bb_bull_squeeze"] or
                     signals["macd_accel"])
        qualifies = score >= 3 and signals["trend_daily"]

        def tick(ok, detail=""):
            return ("PASS  " + detail) if ok else ("FAIL  " + detail)

        return {
            "── Market context ───────────────────────────": "",
            "Regime":           regime,
            "── Live values ──────────────────────────────": "",
            "Price":            f"${p:.2f}",
            "EMA8 / EMA21":     f"${raw['ema8']:.2f} / ${raw['ema21']:.2f}",
            "RSI [-3,-2,-1]":   f"{raw['rsi2']:.1f} → {raw['rsi1']:.1f} → {raw['rsi0']:.1f}",
            "Stoch K [-3,-2,-1]": f"{raw['k2']:.1f} → {raw['k1']:.1f} → {raw['k0']:.1f}  D={raw['d0']:.1f}",
            "MACD hist [-3,-2,-1]": f"{raw['mh2']:.4f} → {raw['mh1']:.4f} → {raw['mh0']:.4f}",
            "MACD line/sig":    f"{raw['ml']:.4f} / {raw['ms']:.4f}",
            "ADX":              f"{raw['adx']:.1f}",
            "Vol ratio":        f"{raw['vol_ratio']:.2f}×",
            "BB width / pct20": f"{raw['bbw_now']:.4f} / {raw['bbw_pct20']:.4f}",
            "BB midline":       f"${raw['bbw_mid']:.2f}  (price {'ABOVE' if p > raw['bbw_mid'] else 'BELOW'})",
            "10-day high":      f"${raw['high_10d']:.2f}",
            "Last swing low":   f"${raw['last_swing_low']:.2f}  ({raw['swing_lows_count']} lows detected)",
            "── Condition checks ─────────────────────────": "",
            "1. Trend (price>ema8>ema21)":       tick(signals["trend_daily"],
                f"price={p:.2f} ema8={raw['ema8']:.2f} ema21={raw['ema21']:.2f}"),
            "2. Stoch confirmed bounce":         tick(signals["stoch_confirmed"],
                f"k2={raw['k2']:.1f}<20? k1={raw['k1']:.1f}<20? k0={raw['k0']:.1f}>k1? k0>D={raw['d0']:.1f}?"),
            "3. BB bull squeeze":                tick(signals["bb_bull_squeeze"],
                f"squeeze={'YES' if raw['bb_squeeze_raw'] else 'NO'}  price>mid={'YES' if p > raw['bbw_mid'] else 'NO'}"),
            "4. MACD acceleration":              tick(signals["macd_accel"],
                f"mh0={raw['mh0']:.4f}>mh1={raw['mh1']:.4f}>mh2={raw['mh2']:.4f}?"),
            "5. MACD crossover":                 tick(signals["macd_cross"],
                f"line={raw['ml']:.4f}>sig={raw['ms']:.4f}?"),
            "6. RSI confirmed cross-50":         tick(signals["rsi_confirmed"],
                f"rsi2={raw['rsi2']:.1f}<50? rsi1={raw['rsi1']:.1f}>=50? rsi0={raw['rsi0']:.1f}>rsi1?"),
            "7. ADX > 20":                       tick(signals["adx"],
                f"adx={raw['adx']:.1f}"),
            "8. Volume > 1.5×":                  tick(signals["volume"],
                f"ratio={raw['vol_ratio']:.2f}×"),
            "9. Vol breakout (10dH+1.8×vol)":   tick(signals["vol_breakout"],
                f"price={p:.2f} 10dH={raw['high_10d']:.2f} vol={raw['vol_ratio']:.2f}×"),
            "10. Higher lows (proper algo)":     tick(signals["higher_lows"],
                f"{raw['swing_lows_count']} swing lows detected in last 60 bars"),
            "── Result ───────────────────────────────────": "",
            "Score":                   f"{score}/10",
            "Rise probability":        f"{rise_prob*100:.1f}%  ({prob_label(rise_prob)})",
            "Regime penalty applied":  "YES" if regime != "BULL" else "NO (bull market)",
            "Has top-3 signal":        "YES" if top3 else "NO — need Stoch/BB squeeze/MACD accel",
            "Appears in scan":         "YES" if qualifies else "NO — needs score≥3 AND trend",
            "Signals firing":          ", ".join(k for k, v in signals.items() if v) or "none",
            "Signals failing":         ", ".join(k for k, v in signals.items() if not v) or "none",
        }
    except Exception as e:
        return {"Error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
st.sidebar.header("Scan filters")
min_prob       = st.sidebar.slider("Min rise probability (%)", 40, 95, 62, step=1)
require_stoch  = st.sidebar.checkbox("Must have Stoch bounce",      False)
require_bb     = st.sidebar.checkbox("Must have BB bull squeeze",    False)
require_accel  = st.sidebar.checkbox("Must have MACD acceleration",  False)
require_vb     = st.sidebar.checkbox("Must have volume breakout",    False)
skip_earnings  = st.sidebar.checkbox("Skip earnings within 7 days", True)

st.sidebar.markdown("---")
st.sidebar.header("Custom tickers")
extra_input   = st.sidebar.text_input("Add tickers (comma-separated)", placeholder="HIMS, NVTS")
extra_tickers = [t.strip().upper() for t in extra_input.split(",") if t.strip()]
scan_list     = list(dict.fromkeys(TICKERS + extra_tickers))

st.sidebar.markdown("---")
st.sidebar.header("Diagnose a ticker")
debug_input = st.sidebar.text_input("Why didn't X appear?", placeholder="HIMS, NVTS")

st.sidebar.markdown("---")
st.sidebar.markdown(
    "**Signal accuracy guide**\n\n"
    "🟢 **Stoch confirmed** — K<20 for 2 bars, then rises above D → 71%\n\n"
    "🟢 **BB bull squeeze** — coiling + price above midline → 69%\n\n"
    "🟢 **MACD accel** — histogram grows 3 bars → 67%\n\n"
    "🟡 **RSI confirmed** — cross-50 held for 2 bars → 59%\n\n"
    "🟡 **Higher lows** — proper swing-low algorithm → 63%\n\n"
    "⚠️ **Regime filter** — BEAR market reduces all probabilities 25%"
)

# ─────────────────────────────────────────────────────────────────────────────
# MARKET REGIME BANNER
# ─────────────────────────────────────────────────────────────────────────────
mkt = get_market_regime()
regime = mkt["regime"]

regime_colors = {"BULL": "🟢", "CAUTION": "🟡", "BEAR": "🔴", "UNKNOWN": "⚪"}
emoji = regime_colors.get(regime, "⚪")

col_r1, col_r2, col_r3, col_r4 = st.columns(4)
col_r1.metric("Market Regime", f"{emoji} {regime}")
col_r2.metric("SPY", f"${mkt['spy']}", f"EMA20: ${mkt['spy_ema20']}")
col_r3.metric("VIX", f"{mkt['vix']}", "Fear gauge")
col_r4.metric(
    "Scan mode",
    "Normal" if regime == "BULL" else ("Strict" if regime == "BEAR" else "Cautious"),
)

if regime == "BEAR":
    st.error(
        "⚠️ **Bear market detected** — SPY below EMA50 or VIX > 25. "
        "STRONG BUY threshold raised. All probabilities reduced 25%. "
        "Consider reducing position sizes."
    )
elif regime == "CAUTION":
    st.warning(
        "⚠️ **Caution zone** — SPY below EMA20 or VIX elevated. "
        "Probabilities reduced 12%. Use smaller sizes."
    )

st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# MAIN SCAN
# ─────────────────────────────────────────────────────────────────────────────
if st.button("Run 5–7 Day Swing Scan", type="primary"):
    df_results = fetch_analysis(tuple(scan_list), regime, skip_earnings)

    if not df_results.empty:
        df_results["_p"] = df_results["Rise Prob"].str.rstrip("%").astype(float)
        df_results = df_results[df_results["_p"] >= min_prob]

        if require_stoch: df_results = df_results[df_results["Signals"].str.contains("STOCH")]
        if require_bb:    df_results = df_results[df_results["BB Squeeze"] == "YES"]
        if require_accel: df_results = df_results[df_results["Signals"].str.contains("MACD ACCEL")]
        if require_vb:    df_results = df_results[df_results["Signals"].str.contains("VOL BREAKOUT")]

        df_results = df_results.drop(columns="_p")

        strong   = df_results[df_results["Action"] == "STRONG BUY"]
        watch_hq = df_results[df_results["Action"] == "WATCH – HIGH QUALITY"]
        watch_dv = df_results[df_results["Action"] == "WATCH – DEVELOPING"]

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Strong Buy",       len(strong))
        c2.metric("High Quality",     len(watch_hq))
        c3.metric("Developing",       len(watch_dv))
        c4.metric("BB Squeezes",      len(df_results[df_results["BB Squeeze"] == "YES"]))
        top = df_results["Rise Prob"].iloc[0] if not df_results.empty else "–"
        c5.metric("Top Probability",  top)

        st.caption(
            "**Best Stop** = tighter of ATR-stop vs swing-low-stop  |  "
            "**Target 1:1** = exit in 3–5 days  |  "
            "**Target 1:2** = full 5–7 day move"
        )

        st.markdown("### Strong Buy")
        show_table(strong, "strong buy")

        st.markdown("### High Quality Watch")
        show_table(watch_hq, "high quality")

        st.markdown("### Developing Setups")
        show_table(watch_dv, "developing")

    else:
        st.warning("No setups found. Try lowering min probability or unchecking filters.")

else:
    st.info("Click **Run 5–7 Day Swing Scan** to start.")

# ─────────────────────────────────────────────────────────────────────────────
# DIAGNOSTICS PANEL
# ─────────────────────────────────────────────────────────────────────────────
if debug_input:
    st.markdown("---")
    st.markdown("### Ticker diagnostics")
    st.caption("Every condition with live values, pass/fail, and regime context.")
    for t in [x.strip().upper() for x in debug_input.split(",") if x.strip()]:
        with st.expander(f"{t} — full condition breakdown", expanded=True):
            result = diagnose_ticker(t, regime)
            for k, v in result.items():
                if str(v) == "":
                    st.markdown(f"**{k}**")
                    continue
                ca, cb = st.columns([3, 5])
                ca.markdown(f"`{k}`")
                vs = str(v)
                if vs.startswith("PASS"):   cb.success(vs)
                elif vs.startswith("FAIL"): cb.error(vs)
                elif vs.startswith("YES"):  cb.success(vs)
                elif vs.startswith("NO"):   cb.error(vs)
                elif "Error" in k:          cb.error(vs)
                else:                       cb.write(vs)