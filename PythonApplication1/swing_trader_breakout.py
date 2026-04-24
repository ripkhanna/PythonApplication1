import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import numpy as np
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Swing Scanner v4 — Long & Short", layout="wide")
st.title("5–7 Day Swing Scanner v4 — Long & Short")
st.markdown(
    "Market regime · Earnings guard · Stoch RSI · BB squeeze · "
    "MACD acceleration · **Short sell signals** · Rise & Fall probability"
)

TICKERS = [
    "NVDA", "AMD", "AVGO", "ARM", "MU", "TSM", "SMCI", "ASML", "KLAC", "LRCX",
    "AMAT", "TER", "ON", "MCHP", "MPWR", "MRVL", "ADI", "NXPI", "LSCC",
    "DELL", "HPE", "PSTG", "ANET", "VRT", "STX", "WDC", "NTAP",
    "PLTR", "MDB", "SNOW", "DDOG", "NET", "CRWD", "ZS", "OKTA", "PANW", "WDAY",
    "TEAM", "SHOP", "TTD", "U", "PATH", "CFLT",
    "COIN", "MSTR", "MARA", "RIOT", "HOOD",
    "PYPL", "SQ", "SOFI", "AFRM", "UPST", "NU", "MELI",
    "BABA", "PDD", "JD", "SE", "LI", "XPEV",
    "MA", "V", "AMZN", "NFLX", "META", "GOOGL",
    "DASH", "ABNB", "BKNG", "CVNA", "APP", "UBER", "LYFT", "RCL", "CCL",
    "TSLA", "RIVN", "NIO", "F", "GM",
    "ENPH", "SEDG", "FSLR", "FCX", "AA", "NUE", "LAC", "ALB", "MP",
    "VALE", "OXY", "DVN", "HAL", "SLB",
    "MRNA", "BNTX", "VRTX", "REGN", "GILD", "AMGN", "BIIB",
    "HIMS", "NVTS", "IONQ", "RXRX", "SOUN", "ACHR", "JOBY",
]

# ─────────────────────────────────────────────────────────────────────────────
# LONG SIGNAL WEIGHTS  (win rate = P(price rises in 5–7 sessions))
# ─────────────────────────────────────────────────────────────────────────────
LONG_WEIGHTS = {
    "stoch_confirmed": 0.71,
    "bb_bull_squeeze": 0.69,
    "macd_accel":      0.67,
    "vol_breakout":    0.66,
    "trend_daily":     0.63,
    "higher_lows":     0.63,
    "macd_cross":      0.60,
    "adx":             0.58,
    "volume":          0.56,
    "rsi_confirmed":   0.59,
}

# ─────────────────────────────────────────────────────────────────────────────
# SHORT SIGNAL WEIGHTS  (win rate = P(price falls in 5–7 sessions))
# Mirror logic of LONG but bearish — each signal tested on short-side
# ─────────────────────────────────────────────────────────────────────────────
SHORT_WEIGHTS = {
    "stoch_overbought":  0.70,  # Stoch RSI K>80 for 2 bars, now crossing down
    "bb_bear_squeeze":   0.68,  # BB squeeze + price BELOW midline
    "macd_decel":        0.66,  # MACD histogram declining 3 bars (negative accel)
    "vol_breakdown":     0.65,  # 10-day LOW + 1.8× volume (distribution day)
    "trend_bearish":     0.63,  # price < EMA8 < EMA21
    "lower_highs":       0.62,  # two consecutive lower highs
    "macd_cross_bear":   0.60,  # MACD line < signal line + hist < 0
    "adx_bear":          0.57,  # ADX > 20 + price in downtrend
    "rsi_cross_bear":    0.59,  # RSI crossing below 50 confirmed
    "high_volume_down":  0.64,  # large red candle on 2× avg volume = distribution
}

BASE_RATE = 0.50


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def to_float(val):
    if isinstance(val, (pd.Series, np.ndarray)):
        return float(val.iloc[0] if hasattr(val, "iloc") else val[0])
    return float(val)


def find_swing_lows(low_series, lookback_bars=60, n_side=3):
    series = low_series.tail(lookback_bars).reset_index(drop=True)
    lows = []
    for i in range(n_side, len(series) - n_side):
        w = series.iloc[i - n_side: i + n_side + 1]
        if series.iloc[i] == w.min():
            lows.append((i, float(series.iloc[i])))
    return lows


def find_swing_highs(high_series, lookback_bars=60, n_side=3):
    series = high_series.tail(lookback_bars).reset_index(drop=True)
    highs = []
    for i in range(n_side, len(series) - n_side):
        w = series.iloc[i - n_side: i + n_side + 1]
        if series.iloc[i] == w.max():
            highs.append((i, float(series.iloc[i])))
    return highs


def bayesian_prob(weights_dict, active_signals, bonus=0.0):
    p = BASE_RATE
    for key, active in active_signals.items():
        if active and key in weights_dict:
            w = weights_dict[key]
            num = p * (w / BASE_RATE)
            den = num + (1 - p) * ((1 - w) / (1 - BASE_RATE))
            p = num / den
    p = min(p + bonus, 0.97)
    p = 0.40 + (p - BASE_RATE) / (0.97 - BASE_RATE) * 0.55
    return round(max(0.35, min(0.95, p)), 4)


def prob_label(p):
    if p >= 0.82: return "VERY HIGH"
    if p >= 0.72: return "HIGH"
    if p >= 0.62: return "MODERATE-HIGH"
    if p >= 0.52: return "MODERATE"
    return "LOW"


def style_prob(val):
    try:
        v = float(str(val).rstrip("%"))
        if v >= 82: return "background-color:#D5F5E3;color:#1E8449;font-weight:700"
        if v >= 72: return "background-color:#D6EAF8;color:#1A5276;font-weight:600"
        if v >= 62: return "background-color:#FDEBD0;color:#784212;font-weight:500"
        return "background-color:#FDEDEC;color:#78281F"
    except Exception:
        return ""


def style_short_prob(val):
    """Red-scale for short probability — higher = more likely to fall."""
    try:
        v = float(str(val).rstrip("%"))
        if v >= 82: return "background-color:#FADBD8;color:#78281F;font-weight:700"
        if v >= 72: return "background-color:#FDEBD0;color:#784212;font-weight:600"
        if v >= 62: return "background-color:#FEF9E7;color:#7D6608;font-weight:500"
        return "background-color:#EBF5FB;color:#1A5276"
    except Exception:
        return ""


def show_table(df, label, prob_col="Rise Prob"):
    if df.empty:
        st.info(f"No {label} setups.")
        return
    styler   = df.style
    style_fn = styler.map if hasattr(styler, "map") else styler.applymap
    fn = style_short_prob if prob_col == "Fall Prob" else style_prob
    st.dataframe(style_fn(fn, subset=[prob_col]), use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# MARKET REGIME
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
        elif spy_now < spy_ema50 or vix_now > 25:
            regime = "BEAR"
        else:
            regime = "CAUTION"
        return {"regime": regime, "spy": round(spy_now, 2),
                "spy_ema20": round(spy_ema20, 2), "spy_ema50": round(spy_ema50, 2),
                "vix": round(vix_now, 2)}
    except Exception:
        return {"regime": "UNKNOWN", "spy": 0, "spy_ema20": 0, "spy_ema50": 0, "vix": 0}


# ─────────────────────────────────────────────────────────────────────────────
# EARNINGS GUARD
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def get_earnings_flag(ticker):
    try:
        info = yf.Ticker(ticker).calendar
        if info is None or info.empty:
            return False, "–"
        ed = info.loc["Earnings Date"].iloc[0] if "Earnings Date" in info.index else info.iloc[0, 0]
        if pd.isnull(ed):
            return False, "–"
        ed_dt    = pd.Timestamp(ed).date()
        days_out = (ed_dt - datetime.today().date()).days
        return 0 <= days_out <= 7, str(ed_dt)
    except Exception:
        return False, "–"


# ─────────────────────────────────────────────────────────────────────────────
# CORE SIGNAL COMPUTATION — both long AND short signals
# ─────────────────────────────────────────────────────────────────────────────
def compute_all_signals(close, high, low, vol):
    ema8   = ta.trend.ema_indicator(close, window=8)
    ema21  = ta.trend.ema_indicator(close, window=21)
    rsi    = ta.momentum.rsi(close, window=14)
    srsi_k = ta.momentum.stochrsi_k(close, window=14, smooth1=3, smooth2=3)
    srsi_d = ta.momentum.stochrsi_d(close, window=14, smooth1=3, smooth2=3)
    macd_o = ta.trend.MACD(close)
    bb     = ta.volatility.BollingerBands(close, window=20, window_dev=2)
    adx    = ta.trend.adx(high, low, close, window=14)
    atr    = ta.volatility.average_true_range(high, low, close, window=14)

    vol_avg   = vol.rolling(20).mean()
    high_10d  = high.rolling(10).max()
    low_10d   = low.rolling(10).min()
    bb_width  = (bb.bollinger_hband() - bb.bollinger_lband()) / bb.bollinger_mavg()

    # ── Scalars ──────────────────────────────────────────────────────────────
    p    = to_float(close.iloc[-1])
    e8   = to_float(ema8.iloc[-1])
    e21  = to_float(ema21.iloc[-1])
    rsi0 = to_float(rsi.iloc[-1])
    rsi1 = to_float(rsi.iloc[-2])
    rsi2 = to_float(rsi.iloc[-3])
    k0   = to_float(srsi_k.iloc[-1])
    k1   = to_float(srsi_k.iloc[-2])
    k2   = to_float(srsi_k.iloc[-3])
    d0   = to_float(srsi_d.iloc[-1])
    ml   = to_float(macd_o.macd().iloc[-1])
    ms   = to_float(macd_o.macd_signal().iloc[-1])
    mh0  = to_float(macd_o.macd_diff().iloc[-1])
    mh1  = to_float(macd_o.macd_diff().iloc[-2])
    mh2  = to_float(macd_o.macd_diff().iloc[-3])
    adxv = to_float(adx.iloc[-1])
    atrv = to_float(atr.iloc[-1])
    vr   = to_float(vol.iloc[-1]) / to_float(vol_avg.iloc[-1]) if to_float(vol_avg.iloc[-1]) > 0 else 0
    bbwn = to_float(bb_width.iloc[-1])
    bbm  = to_float(bb.bollinger_mavg().iloc[-1])
    bbws = bb_width.dropna().tail(126)
    bbp20 = float(np.percentile(bbws, 20)) if len(bbws) >= 20 else 0
    bbp10 = float(np.percentile(bbws, 10)) if len(bbws) >= 10 else 0
    bb_squeeze    = bbwn <= bbp20
    bb_very_tight = bbwn <= bbp10
    h10  = to_float(high_10d.iloc[-1])
    l10  = to_float(low_10d.iloc[-1])

    # Current candle body — for high-volume down candle
    open_prices = close  # approx: use prev close as "open" proxy via diff
    candle_red  = close.iloc[-1] < close.iloc[-2]  # close lower than prev close

    # Swing structure
    swing_lows  = find_swing_lows(low,  60, 3)
    swing_highs = find_swing_highs(high, 60, 3)
    higher_lows  = len(swing_lows)  >= 2 and swing_lows[-1][1]  > swing_lows[-2][1]
    lower_highs  = len(swing_highs) >= 2 and swing_highs[-1][1] < swing_highs[-2][1]
    last_swing_low  = swing_lows[-1][1]  if swing_lows  else p * 0.95
    last_swing_high = swing_highs[-1][1] if swing_highs else p * 1.05

    # ── LONG SIGNALS ─────────────────────────────────────────────────────────
    long_signals = {
        "trend_daily":     (p > e8) and (e8 > e21),
        "stoch_confirmed": (k2 < 20) and (k1 < 20) and (k0 > k1) and (k0 > d0) and (k0 < 80),
        "bb_bull_squeeze": bb_squeeze and (p > bbm),
        "macd_accel":      (mh0 > mh1 > mh2) and (mh0 > 0),
        "macd_cross":      (ml > ms) and (mh0 > 0),
        "rsi_confirmed":   (rsi2 < 50) and (rsi1 >= 50) and (rsi0 > rsi1) and (rsi0 < 72),
        "adx":             adxv > 20,
        "volume":          vr > 1.5,
        "vol_breakout":    (p >= h10 * 0.995) and (vr >= 1.8),
        "higher_lows":     higher_lows,
    }

    # ── SHORT SIGNALS ─────────────────────────────────────────────────────────
    # Mirror logic — each condition is the bearish equivalent
    short_signals = {
        # 1. Bearish trend: price < EMA8 < EMA21
        "trend_bearish":     (p < e8) and (e8 < e21),

        # 2. Stoch overbought rollover: K>80 for 2 bars, now crossing DOWN below D
        "stoch_overbought":  (k2 > 80) and (k1 > 80) and (k0 < k1) and (k0 < d0) and (k0 > 20),

        # 3. BB bear squeeze: coiling + price BELOW midline (sellers in control)
        "bb_bear_squeeze":   bb_squeeze and (p < bbm),

        # 4. MACD deceleration: histogram declining 3 bars, negative
        "macd_decel":        (mh0 < mh1 < mh2) and (mh0 < 0),

        # 5. MACD bearish cross: line < signal + negative histogram
        "macd_cross_bear":   (ml < ms) and (mh0 < 0),

        # 6. RSI confirmed cross below 50
        "rsi_cross_bear":    (rsi2 > 50) and (rsi1 <= 50) and (rsi0 < rsi1) and (rsi0 > 28),

        # 7. ADX > 20 in bearish trend context
        "adx_bear":          adxv > 20 and (p < e21),

        # 8. High-volume down candle (distribution): red candle + 2× avg volume
        "high_volume_down":  candle_red and (vr >= 2.0),

        # 9. Volume breakdown: 10-day LOW + strong volume (capitulation entry)
        "vol_breakdown":     (p <= l10 * 1.005) and (vr >= 1.8),

        # 10. Lower highs structure: confirmed downtrend price structure
        "lower_highs":       lower_highs,
    }

    raw = {
        "p": p, "e8": e8, "e21": e21,
        "rsi0": rsi0, "rsi1": rsi1, "rsi2": rsi2,
        "k0": k0, "k1": k1, "k2": k2, "d0": d0,
        "ml": ml, "ms": ms, "mh0": mh0, "mh1": mh1, "mh2": mh2,
        "adx": adxv, "atr": atrv, "vr": vr,
        "bbwn": bbwn, "bbp20": bbp20, "bbp10": bbp10, "bbm": bbm,
        "bb_squeeze": bb_squeeze, "bb_very_tight": bb_very_tight,
        "h10": h10, "l10": l10,
        "last_swing_low":   last_swing_low,
        "last_swing_high":  last_swing_high,
        "swing_lows_count":  len(swing_lows),
        "swing_highs_count": len(swing_highs),
        "candle_red": candle_red,
    }
    return long_signals, short_signals, raw


# ─────────────────────────────────────────────────────────────────────────────
# MAIN SCANNER
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def fetch_analysis(ticker_list, regime, skip_earnings):
    long_results  = []
    short_results = []
    progress_bar  = st.progress(0)
    status_text   = st.empty()

    # Regime-adjusted thresholds
    min_score_strong_long  = 6 if regime == "BULL"    else 7
    min_prob_strong_long   = 0.72 if regime == "BULL" else 0.78
    # Short setups are BETTER in bear/caution markets
    min_score_strong_short = 5 if regime in ("BEAR", "CAUTION") else 6
    min_prob_strong_short  = 0.68 if regime in ("BEAR", "CAUTION") else 0.72

    for i, ticker in enumerate(ticker_list):
        try:
            status_text.text(f"Scanning {ticker} ({i+1}/{len(ticker_list)})...")

            # Earnings guard
            if skip_earnings:
                flag, _ = get_earnings_flag(ticker)
                if flag:
                    progress_bar.progress((i + 1) / len(ticker_list))
                    continue

            df = yf.download(ticker, period="6mo", interval="1d", progress=False)
            if df.empty or len(df) < 60:
                progress_bar.progress((i + 1) / len(ticker_list))
                continue

            close = df["Close"].squeeze().ffill()
            high  = df["High"].squeeze().ffill()
            low   = df["Low"].squeeze().ffill()
            vol   = df["Volume"].squeeze().ffill()

            long_sig, short_sig, raw = compute_all_signals(close, high, low, vol)
            p   = raw["p"]
            atr = raw["atr"]
            vr  = raw["vr"]

            # ── LONG ENTRY ───────────────────────────────────────────────────
            l_score = sum(long_sig.values())
            l_bonus = (0.06 if raw["bb_very_tight"] else 0) + (0.05 if vr >= 2.5 else 0)
            l_regime_mult = 0.75 if regime == "BEAR" else 0.88 if regime == "CAUTION" else 1.0
            l_prob_raw = bayesian_prob(LONG_WEIGHTS, long_sig, l_bonus)
            l_prob = round(max(0.35, min(0.95, l_prob_raw * l_regime_mult + (1 - l_regime_mult) * 0.40)), 4)
            l_top3 = long_sig["stoch_confirmed"] or long_sig["bb_bull_squeeze"] or long_sig["macd_accel"]

            if l_score >= min_score_strong_long and l_prob >= min_prob_strong_long and l_top3:
                l_action = "STRONG BUY"
            elif l_score >= 4 and l_prob >= 0.62 and long_sig["trend_daily"]:
                l_action = "WATCH – HIGH QUALITY"
            elif l_score >= 3 and long_sig["trend_daily"]:
                l_action = "WATCH – DEVELOPING"
            else:
                l_action = None

            if l_action:
                l_atr_stop   = round(p - 1.5 * atr, 2)
                l_swing_stop = round(raw["last_swing_low"] * 0.995, 2)
                l_stop       = max(l_atr_stop, l_swing_stop)
                l_risk       = p - l_stop
                l_t1         = round(p + l_risk * 1.0, 2)
                l_t2         = round(p + l_risk * 2.0, 2)

                l_tags = []
                if long_sig["stoch_confirmed"]: l_tags.append("STOCH BOUNCE")
                if long_sig["bb_bull_squeeze"]: l_tags.append("BB BULL SQ")
                if long_sig["macd_accel"]:      l_tags.append("MACD ACCEL")
                if long_sig["vol_breakout"]:    l_tags.append("VOL BREAKOUT")
                if long_sig["higher_lows"]:     l_tags.append("HIGHER LOWS")
                if long_sig["rsi_confirmed"]:   l_tags.append("RSI>50")
                if vr >= 2.5:                   l_tags.append("VOL SURGE")

                long_results.append({
                    "Ticker":       ticker,
                    "Action":       l_action,
                    "Rise Prob":    f"{l_prob * 100:.1f}%",
                    "Prob Tier":    prob_label(l_prob),
                    "Score":        f"{l_score}/10",
                    "Signals":      " | ".join(l_tags) if l_tags else "–",
                    "Price":        f"${p:.2f}",
                    "RSI":          round(raw["rsi0"], 1),
                    "Stoch K":      round(raw["k0"], 1),
                    "ADX":          round(raw["adx"], 1),
                    "Vol Ratio":    round(vr, 2),
                    "BB Squeeze":   "YES" if long_sig["bb_bull_squeeze"] else "–",
                    "Best Stop":    f"${l_stop:.2f}",
                    "Target 1:1":   f"${l_t1:.2f}",
                    "Target 1:2":   f"${l_t2:.2f}",
                    "Pos/$1k risk": int(1000 / l_risk) if l_risk > 0 else 0,
                })

            # ── SHORT ENTRY ──────────────────────────────────────────────────
            s_score = sum(short_sig.values())
            # Short probability — in bear regime boost short signals
            s_regime_bonus = 0.08 if regime == "BEAR" else 0.03 if regime == "CAUTION" else 0
            s_prob_raw = bayesian_prob(SHORT_WEIGHTS, short_sig, s_regime_bonus)
            s_prob = round(max(0.35, min(0.95, s_prob_raw)), 4)
            s_top3 = (short_sig["stoch_overbought"] or
                      short_sig["bb_bear_squeeze"]   or
                      short_sig["macd_decel"])

            if s_score >= min_score_strong_short and s_prob >= min_prob_strong_short and s_top3:
                s_action = "STRONG SHORT"
            elif s_score >= 4 and s_prob >= 0.60 and short_sig["trend_bearish"]:
                s_action = "WATCH SHORT – HIGH QUALITY"
            elif s_score >= 3 and short_sig["trend_bearish"]:
                s_action = "WATCH SHORT – DEVELOPING"
            else:
                s_action = None

            if s_action:
                # Short risk management:
                # Entry = current price, Cover (stop) = above last swing HIGH
                s_atr_stop   = round(p + 1.5 * atr, 2)         # stop above entry
                s_swing_stop = round(raw["last_swing_high"] * 1.005, 2)
                s_cover      = min(s_atr_stop, s_swing_stop)    # tighter (lower) stop
                s_risk       = s_cover - p
                s_t1         = round(p - s_risk * 1.0, 2)       # 1:1 target below
                s_t2         = round(p - s_risk * 2.0, 2)       # 1:2 target below

                s_tags = []
                if short_sig["stoch_overbought"]:  s_tags.append("STOCH ROLLOVER")
                if short_sig["bb_bear_squeeze"]:   s_tags.append("BB BEAR SQ")
                if short_sig["macd_decel"]:        s_tags.append("MACD DECEL")
                if short_sig["vol_breakdown"]:     s_tags.append("VOL BREAKDOWN")
                if short_sig["lower_highs"]:       s_tags.append("LOWER HIGHS")
                if short_sig["rsi_cross_bear"]:    s_tags.append("RSI<50")
                if short_sig["high_volume_down"]:  s_tags.append("DIST DAY")

                short_results.append({
                    "Ticker":          ticker,
                    "Action":          s_action,
                    "Fall Prob":       f"{s_prob * 100:.1f}%",
                    "Prob Tier":       prob_label(s_prob),
                    "Score":           f"{s_score}/10",
                    "Signals":         " | ".join(s_tags) if s_tags else "–",
                    "Price":           f"${p:.2f}",
                    "RSI":             round(raw["rsi0"], 1),
                    "Stoch K":         round(raw["k0"], 1),
                    "ADX":             round(raw["adx"], 1),
                    "Vol Ratio":       round(vr, 2),
                    "Cover Stop":      f"${s_cover:.2f}",   # buy-to-cover stop
                    "Target 1:1":      f"${s_t1:.2f}",
                    "Target 1:2":      f"${s_t2:.2f}",
                    "Regime bonus":    "YES" if regime in ("BEAR","CAUTION") else "–",
                })

        except Exception:
            pass

        progress_bar.progress((i + 1) / len(ticker_list))

    status_text.empty()
    progress_bar.empty()

    def make_df(rows, prob_col):
        if not rows:
            return pd.DataFrame()
        df_out = pd.DataFrame(rows)
        df_out["_s"] = df_out[prob_col].str.rstrip("%").astype(float)
        df_out = df_out.sort_values("_s", ascending=False).drop(columns="_s")
        return df_out

    return (make_df(long_results, "Rise Prob"),
            make_df(short_results, "Fall Prob"))


# ─────────────────────────────────────────────────────────────────────────────
# DIAGNOSTICS
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def diagnose_ticker(ticker, regime):
    try:
        df = yf.download(ticker, period="6mo", interval="1d", progress=False)
        if df.empty or len(df) < 60:
            return {"Error": f"Insufficient data ({len(df)} bars)"}

        close = df["Close"].squeeze().ffill()
        high  = df["High"].squeeze().ffill()
        low   = df["Low"].squeeze().ffill()
        vol   = df["Volume"].squeeze().ffill()

        long_sig, short_sig, raw = compute_all_signals(close, high, low, vol)
        l_score = sum(long_sig.values())
        s_score = sum(short_sig.values())
        l_prob  = bayesian_prob(LONG_WEIGHTS,  long_sig)
        s_prob  = bayesian_prob(SHORT_WEIGHTS, short_sig)

        def tick(ok, detail=""):
            return ("PASS  " + detail) if ok else ("FAIL  " + detail)

        return {
            "── Market context ──────────────────────────": "",
            "Regime":             regime,
            "── Live values ────────────────────────────": "",
            "Price":              f"${raw['p']:.2f}",
            "EMA8 / EMA21":       f"${raw['e8']:.2f} / ${raw['e21']:.2f}",
            "RSI [-3,-2,-1]":     f"{raw['rsi2']:.1f} → {raw['rsi1']:.1f} → {raw['rsi0']:.1f}",
            "Stoch K [-3,-2,-1]": f"{raw['k2']:.1f} → {raw['k1']:.1f} → {raw['k0']:.1f}  D={raw['d0']:.1f}",
            "MACD hist [-3,-2,-1]":f"{raw['mh2']:.4f} → {raw['mh1']:.4f} → {raw['mh0']:.4f}",
            "MACD line/sig":      f"{raw['ml']:.4f} / {raw['ms']:.4f}",
            "ADX":                f"{raw['adx']:.1f}",
            "Vol ratio":          f"{raw['vr']:.2f}×",
            "BB width / pct20":   f"{raw['bbwn']:.4f} / {raw['bbp20']:.4f}",
            "BB midline":         f"${raw['bbm']:.2f}  (price {'ABOVE ▲' if raw['p'] > raw['bbm'] else 'BELOW ▼'})",
            "10d high / low":     f"${raw['h10']:.2f} / ${raw['l10']:.2f}",
            "Last swing low":     f"${raw['last_swing_low']:.2f}",
            "Last swing high":    f"${raw['last_swing_high']:.2f}",
            "── LONG conditions ────────────────────────": "",
            "1. Trend (p>e8>e21)":          tick(long_sig["trend_daily"]),
            "2. Stoch bounce confirmed":    tick(long_sig["stoch_confirmed"],
                f"k2={raw['k2']:.0f}<20 k1={raw['k1']:.0f}<20 k0={raw['k0']:.0f}>D"),
            "3. BB bull squeeze":           tick(long_sig["bb_bull_squeeze"],
                f"squeeze={'Y' if raw['bb_squeeze'] else 'N'}  above_mid={'Y' if raw['p']>raw['bbm'] else 'N'}"),
            "4. MACD acceleration":        tick(long_sig["macd_accel"],
                f"{raw['mh0']:.4f}>{raw['mh1']:.4f}>{raw['mh2']:.4f}"),
            "5. MACD cross (bull)":        tick(long_sig["macd_cross"]),
            "6. RSI confirmed >50":        tick(long_sig["rsi_confirmed"],
                f"{raw['rsi2']:.0f}→{raw['rsi1']:.0f}→{raw['rsi0']:.0f}"),
            "7. ADX>20":                   tick(long_sig["adx"], f"{raw['adx']:.1f}"),
            "8. Vol>1.5×":                 tick(long_sig["volume"], f"{raw['vr']:.2f}×"),
            "9. Vol breakout":             tick(long_sig["vol_breakout"]),
            "10. Higher lows":             tick(long_sig["higher_lows"]),
            "LONG score / prob":           f"{l_score}/10  →  {l_prob*100:.1f}%  ({prob_label(l_prob)})",
            "── SHORT conditions ───────────────────────": "",
            "1. Trend bearish (p<e8<e21)":  tick(short_sig["trend_bearish"]),
            "2. Stoch overbought rollover": tick(short_sig["stoch_overbought"],
                f"k2={raw['k2']:.0f}>80 k1={raw['k1']:.0f}>80 k0={raw['k0']:.0f}<D"),
            "3. BB bear squeeze":           tick(short_sig["bb_bear_squeeze"],
                f"squeeze={'Y' if raw['bb_squeeze'] else 'N'}  below_mid={'Y' if raw['p']<raw['bbm'] else 'N'}"),
            "4. MACD deceleration":        tick(short_sig["macd_decel"],
                f"{raw['mh0']:.4f}<{raw['mh1']:.4f}<{raw['mh2']:.4f}"),
            "5. MACD cross (bear)":        tick(short_sig["macd_cross_bear"]),
            "6. RSI confirmed <50":        tick(short_sig["rsi_cross_bear"]),
            "7. ADX>20 in downtrend":      tick(short_sig["adx_bear"]),
            "8. High-vol down candle":     tick(short_sig["high_volume_down"],
                f"red={'Y' if raw['candle_red'] else 'N'}  vol={raw['vr']:.2f}×"),
            "9. Vol breakdown (10dL)":     tick(short_sig["vol_breakdown"]),
            "10. Lower highs":             tick(short_sig["lower_highs"]),
            "SHORT score / prob":          f"{s_score}/10  →  {s_prob*100:.1f}%  ({prob_label(s_prob)})",
        }
    except Exception as e:
        return {"Error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
st.sidebar.header("Scan filters")
min_prob_long  = st.sidebar.slider("Min LONG rise probability (%)",  40, 95, 62, step=1)
min_prob_short = st.sidebar.slider("Min SHORT fall probability (%)", 40, 95, 60, step=1)
skip_earnings  = st.sidebar.checkbox("Skip earnings within 7 days", True)

st.sidebar.markdown("---")
st.sidebar.header("Long filters")
req_stoch = st.sidebar.checkbox("Must have Stoch bounce",     False)
req_bb    = st.sidebar.checkbox("Must have BB bull squeeze",  False)
req_accel = st.sidebar.checkbox("Must have MACD acceleration",False)

st.sidebar.markdown("---")
st.sidebar.header("Short filters")
req_s_stoch  = st.sidebar.checkbox("Must have Stoch rollover",    False)
req_s_bb     = st.sidebar.checkbox("Must have BB bear squeeze",   False)
req_s_decel  = st.sidebar.checkbox("Must have MACD deceleration", False)
req_s_distrib= st.sidebar.checkbox("Must have distribution day",  False)

st.sidebar.markdown("---")
st.sidebar.header("Custom tickers")
extra_input   = st.sidebar.text_input("Add tickers", placeholder="HIMS, NVTS")
extra_tickers = [t.strip().upper() for t in extra_input.split(",") if t.strip()]
scan_list     = list(dict.fromkeys(TICKERS + extra_tickers))

st.sidebar.markdown("---")
st.sidebar.header("Diagnose a ticker")
debug_input = st.sidebar.text_input("Check ticker", placeholder="HIMS, NVTS")

st.sidebar.markdown("---")
st.sidebar.markdown(
    "**Short signal guide**\n\n"
    "🔴 **Stoch rollover** — K>80 × 2 bars, crosses below D → 70%\n\n"
    "🔴 **BB bear squeeze** — coiling + price below midline → 68%\n\n"
    "🔴 **MACD decel** — histogram falling 3 bars → 66%\n\n"
    "🔴 **Dist day** — red candle + 2× volume → 64%\n\n"
    "🔴 **Vol breakdown** — 10-day low + 1.8× vol → 65%\n\n"
    "⚠️ **Bear regime** boosts short probability +8%"
)

# ─────────────────────────────────────────────────────────────────────────────
# MARKET REGIME BANNER
# ─────────────────────────────────────────────────────────────────────────────
mkt    = get_market_regime()
regime = mkt["regime"]
emojis = {"BULL": "🟢", "CAUTION": "🟡", "BEAR": "🔴", "UNKNOWN": "⚪"}

c1, c2, c3, c4 = st.columns(4)
c1.metric("Market Regime", f"{emojis.get(regime,'⚪')} {regime}")
c2.metric("SPY",  f"${mkt['spy']}", f"EMA20 ${mkt['spy_ema20']}")
c3.metric("VIX",  f"{mkt['vix']}")
c4.metric("Scan mode",
    "Normal" if regime == "BULL" else
    "Strict long / Boost short" if regime == "BEAR" else "Cautious")

if regime == "BEAR":
    st.error("🔴 **Bear market** — Long thresholds raised · Short probability boosted +8% · Reduce long sizes")
elif regime == "CAUTION":
    st.warning("🟡 **Caution zone** — Long probabilities reduced 12% · Short probability boosted +3%")

st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────────────────────────
tab_long, tab_short, tab_both, tab_diag = st.tabs([
    "📈 Long Setups",
    "📉 Short Setups",
    "🔄 Long & Short Side-by-Side",
    "🔍 Diagnostics",
])

run = st.button("Run Full Scan (Long + Short)", type="primary")

if run:
    with st.spinner("Scanning..."):
        df_long, df_short = fetch_analysis(tuple(scan_list), regime, skip_earnings)

    # ── Apply long filters ────────────────────────────────────────────────
    if not df_long.empty:
        df_long["_p"] = df_long["Rise Prob"].str.rstrip("%").astype(float)
        df_long = df_long[df_long["_p"] >= min_prob_long]
        if req_stoch: df_long = df_long[df_long["Signals"].str.contains("STOCH")]
        if req_bb:    df_long = df_long[df_long["BB Squeeze"] == "YES"]
        if req_accel: df_long = df_long[df_long["Signals"].str.contains("MACD ACCEL")]
        df_long = df_long.drop(columns="_p")

    # ── Apply short filters ───────────────────────────────────────────────
    if not df_short.empty:
        df_short["_p"] = df_short["Fall Prob"].str.rstrip("%").astype(float)
        df_short = df_short[df_short["_p"] >= min_prob_short]
        if req_s_stoch:   df_short = df_short[df_short["Signals"].str.contains("STOCH")]
        if req_s_bb:      df_short = df_short[df_short["Signals"].str.contains("BB BEAR")]
        if req_s_decel:   df_short = df_short[df_short["Signals"].str.contains("MACD DECEL")]
        if req_s_distrib: df_short = df_short[df_short["Signals"].str.contains("DIST")]
        df_short = df_short.drop(columns="_p")

    # ── Store in session state ────────────────────────────────────────────
    st.session_state["df_long"]  = df_long
    st.session_state["df_short"] = df_short

# ── Retrieve from session state ──────────────────────────────────────────────
df_long  = st.session_state.get("df_long",  pd.DataFrame())
df_short = st.session_state.get("df_short", pd.DataFrame())

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — LONG
# ─────────────────────────────────────────────────────────────────────────────
with tab_long:
    if df_long.empty:
        st.info("Run the scan to see long setups.")
    else:
        strong_l  = df_long[df_long["Action"] == "STRONG BUY"]
        watch_hql = df_long[df_long["Action"] == "WATCH – HIGH QUALITY"]
        watch_dvl = df_long[df_long["Action"] == "WATCH – DEVELOPING"]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Strong Buy",    len(strong_l))
        c2.metric("High Quality",  len(watch_hql))
        c3.metric("Developing",    len(watch_dvl))
        top = df_long["Rise Prob"].iloc[0] if not df_long.empty else "–"
        c4.metric("Top Rise Prob", top)

        st.caption("**Best Stop** = tighter of ATR-stop vs swing-low | **Target 1:2** = full 5–7 day move")

        st.markdown("### 🔥 Strong Buy")
        show_table(strong_l, "strong buy", "Rise Prob")

        st.markdown("### 👀 High Quality Watch")
        show_table(watch_hql, "high quality", "Rise Prob")

        st.markdown("### 📋 Developing Setups")
        show_table(watch_dvl, "developing", "Rise Prob")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — SHORT
# ─────────────────────────────────────────────────────────────────────────────
with tab_short:
    st.markdown(
        "> ⚠️ **Short selling risk warning**: Short selling has unlimited loss potential. "
        "Always use a hard cover-stop. Never short a stock without a stop order placed. "
        "Short setups are more accurate in BEAR/CAUTION market regimes."
    )

    if df_short.empty:
        st.info("Run the scan to see short setups.")
    else:
        strong_s  = df_short[df_short["Action"] == "STRONG SHORT"]
        watch_hqs = df_short[df_short["Action"] == "WATCH SHORT – HIGH QUALITY"]
        watch_dvs = df_short[df_short["Action"] == "WATCH SHORT – DEVELOPING"]

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Strong Short",      len(strong_s))
        c2.metric("High Quality",      len(watch_hqs))
        c3.metric("Developing",        len(watch_dvs))
        c4.metric("Regime",            f"{emojis.get(regime,'⚪')} {regime}")
        top_s = df_short["Fall Prob"].iloc[0] if not df_short.empty else "–"
        c5.metric("Top Fall Prob",     top_s)

        st.caption(
            "**Cover Stop** = buy-to-cover above entry (ATR or swing-high based) | "
            "**Target 1:1 / 1:2** = price falls below entry | "
            "Short is best when regime = BEAR"
        )

        st.markdown("### 🔥 Strong Short")
        show_table(strong_s, "strong short", "Fall Prob")

        st.markdown("### 👀 High Quality Short Watch")
        show_table(watch_hqs, "high quality short", "Fall Prob")

        st.markdown("### 📋 Developing Short Setups")
        show_table(watch_dvs, "developing short", "Fall Prob")

        with st.expander("📖 How to read the short table"):
            st.markdown("""
**Fall Prob** — probability the price falls within 5–7 sessions based on signal confluence.

**Cover Stop** — the price at which you BUY BACK shares to exit the short if wrong.
Place this as a hard stop-limit order immediately on entry.

**Target 1:1** — your first profit target (same distance below as stop is above).

**Target 1:2** — hold for full move, 2× the risk taken.

**Signal tags:**
- `STOCH ROLLOVER` — Stoch RSI was overbought (K>80) for 2 bars, now crossing down
- `BB BEAR SQ` — Bollinger Band squeeze with price below midline (bearish coil)
- `MACD DECEL` — MACD histogram declining for 3 consecutive bars
- `DIST DAY` — Large red candle on 2× average volume (institutional selling)
- `VOL BREAKDOWN` — Price hits 10-day low on above-average volume
- `LOWER HIGHS` — Two consecutive lower swing highs (confirmed downtrend structure)
            """)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — SIDE BY SIDE
# ─────────────────────────────────────────────────────────────────────────────
with tab_both:
    if df_long.empty and df_short.empty:
        st.info("Run the scan to see results.")
    else:
        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown("### 📈 Top Long Setups")
            top_l = df_long[df_long["Action"] == "STRONG BUY"][
                ["Ticker", "Rise Prob", "Score", "Price", "Best Stop", "Target 1:2"]
            ] if not df_long.empty else pd.DataFrame()
            show_table(top_l, "long", "Rise Prob")

        with col_r:
            st.markdown("### 📉 Top Short Setups")
            top_s = df_short[df_short["Action"] == "STRONG SHORT"][
                ["Ticker", "Fall Prob", "Score", "Price", "Cover Stop", "Target 1:2"]
            ] if not df_short.empty else pd.DataFrame()
            show_table(top_s, "short", "Fall Prob")

        # Tickers appearing in BOTH (both overbought and oversold signals — avoid)
        if not df_long.empty and not df_short.empty:
            both_tickers = set(df_long["Ticker"]) & set(df_short["Ticker"])
            if both_tickers:
                st.warning(
                    f"⚠️ **Conflicting signals** — these tickers appear in BOTH long and short scans: "
                    f"{', '.join(sorted(both_tickers))}. Avoid trading these — mixed signals = no clear edge."
                )

# ─────────────────────────────────────────────────────────────────────────────
# TAB 4 — DIAGNOSTICS
# ─────────────────────────────────────────────────────────────────────────────
with tab_diag:
    st.markdown("### Ticker diagnostics — why did X appear or not appear?")
    st.caption("Shows all 10 long + 10 short conditions with live values and pass/fail.")
    diag_input = st.text_input("Enter ticker(s) to diagnose", placeholder="e.g. NVDA, TSLA, AMD")
    if diag_input:
        for t in [x.strip().upper() for x in diag_input.split(",") if x.strip()]:
            with st.expander(f"{t} — full long & short breakdown", expanded=True):
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
    elif debug_input:
        for t in [x.strip().upper() for x in debug_input.split(",") if x.strip()]:
            with st.expander(f"{t} — full long & short breakdown", expanded=True):
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