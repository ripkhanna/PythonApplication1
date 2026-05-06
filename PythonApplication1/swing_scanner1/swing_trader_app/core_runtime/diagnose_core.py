"""Extracted runtime section from app_runtime.py lines 3193-3283.
Loaded by app_runtime with exec(..., globals()) to preserve the original single-file behavior.
"""

@st.cache_data(ttl=3600)
def diagnose_ticker(ticker, regime):
    try:
        raw = yf.download(ticker, period="6mo", interval="1d",
                          progress=False, auto_adjust=True)
        if raw.empty or len(raw) < 60:
            return {"Error": f"Insufficient data ({len(raw)} bars)"}
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        close = raw["Close"].squeeze().ffill()
        high  = raw["High"].squeeze().ffill()
        low   = raw["Low"].squeeze().ffill()
        vol   = raw["Volume"].squeeze().ffill()
        long_sig, short_sig, rv = compute_all_signals(close, high, low, vol)
        l_score = sum(long_sig.values())
        s_score = sum(short_sig.values())
        l_prob  = bayesian_prob(LONG_WEIGHTS,  long_sig)
        s_prob  = bayesian_prob(SHORT_WEIGHTS, short_sig)

        def tick(ok, detail=""):
            return ("PASS  " + detail) if ok else ("FAIL  " + detail)

        return {
            "Regime":                   regime,
            "Price":                    f"${rv['p']:.2f}",
            "EMA8 / EMA21":             f"${rv['e8']:.2f} / ${rv['e21']:.2f}",
            "RSI [-3,-2,-1]":           f"{rv['rsi2']:.1f}→{rv['rsi1']:.1f}→{rv['rsi0']:.1f}",
            "Stoch K [-3,-2,-1]":       f"{rv['k2']:.1f}→{rv['k1']:.1f}→{rv['k0']:.1f}  D={rv['d0']:.1f}",
            "MACD hist [-3,-2,-1]":     f"{rv['mh2']:.4f}→{rv['mh1']:.4f}→{rv['mh0']:.4f}",
            "MACD line / signal":       f"{rv['ml']:.4f} / {rv['ms']:.4f}",
            "ADX / Vol ratio":          f"{rv['adx']:.1f} / {rv['vr']:.2f}×",
            "VWAP":                     f"${rv.get('vwap', rv['p']):.2f} · price {'ABOVE' if rv.get('above_vwap') else 'BELOW'} VWAP",
            "Operator activity":        f"{rv.get('operator_label','–')} · score {rv.get('operator_score',0)} · trap {rv.get('trap_risk_label','–')}",
            "BB squeeze":               f"{'YES' if rv['bb_squeeze'] else 'NO'}  price {'ABOVE' if rv['p']>rv['bbm'] else 'BELOW'} midline",
            "Last swing low":           f"${rv['last_swing_low']:.2f}  ({rv['swing_lows_count']} lows detected)",
            "Last swing high":          f"${rv['last_swing_high']:.2f}  ({rv['swing_highs_count']} highs detected)",
            "── LONG ──":              "",
            "1. Trend bullish":         tick(long_sig["trend_daily"],
                f"price={rv['p']:.2f} ema8={rv['e8']:.2f} ema21={rv['e21']:.2f}"),
            "2. Stoch bounce":          tick(long_sig["stoch_confirmed"],
                f"k2={rv['k2']:.0f}<20 k1={rv['k1']:.0f}<20 k0={rv['k0']:.0f}>D={rv['d0']:.0f}"),
            "3. BB bull squeeze":       tick(long_sig["bb_bull_squeeze"],
                f"squeeze={'YES' if rv['bb_squeeze'] else 'NO'}  above_mid={'YES' if rv['p']>rv['bbm'] else 'NO'}"),
            "4. MACD accel":            tick(long_sig["macd_accel"],
                f"mh0={rv['mh0']:.4f}>mh1={rv['mh1']:.4f}>mh2={rv['mh2']:.4f}"),
            "5. MACD cross bull":       tick(long_sig["macd_cross"],
                f"line={rv['ml']:.4f}>sig={rv['ms']:.4f}"),
            "6. RSI >50 confirmed":     tick(long_sig["rsi_confirmed"],
                f"rsi2={rv['rsi2']:.1f}<50 rsi1={rv['rsi1']:.1f}>=50 rsi0={rv['rsi0']:.1f}>rsi1"),
            "7. ADX >20":               tick(long_sig["adx"],   f"adx={rv['adx']:.1f}"),
            "8. Vol >1.5×":             tick(long_sig["volume"], f"ratio={rv['vr']:.2f}×"),
            "9. Vol breakout":          tick(long_sig["vol_breakout"],
                f"price={rv['p']:.2f} 10dH={rv['h10']:.2f} vol={rv['vr']:.2f}×"),
            "10. Higher lows":          tick(long_sig["higher_lows"],
                f"{rv['swing_lows_count']} swing lows in last 60 bars"),
            "11. Operator accumulation": tick(long_sig.get("operator_accumulation", False),
                f"score={rv.get('operator_score',0)} label={rv.get('operator_label','–')}"),
            "12. VWAP support":         tick(long_sig.get("vwap_support", False),
                f"price={rv['p']:.2f} vwap={rv.get('vwap', rv['p']):.2f}"),
            "LONG score / prob":        f"{l_score}/{len(long_sig)}  →  {l_prob*100:.1f}%  ({prob_label(l_prob)})",
            "── SHORT ──":             "",
            "1. Trend bearish":         tick(short_sig["trend_bearish"],
                f"price={rv['p']:.2f} ema8={rv['e8']:.2f} ema21={rv['e21']:.2f}"),
            "2. Stoch rollover":        tick(short_sig["stoch_overbought"],
                f"k2={rv['k2']:.0f}>80 k1={rv['k1']:.0f}>80 k0={rv['k0']:.0f}<D={rv['d0']:.0f}"),
            "3. BB bear squeeze":       tick(short_sig["bb_bear_squeeze"],
                f"squeeze={'YES' if rv['bb_squeeze'] else 'NO'}  below_mid={'YES' if rv['p']<rv['bbm'] else 'NO'}"),
            "4. MACD decel":            tick(short_sig["macd_decel"],
                f"mh0={rv['mh0']:.4f}<mh1={rv['mh1']:.4f}<mh2={rv['mh2']:.4f}"),
            "5. MACD cross bear":       tick(short_sig["macd_cross_bear"],
                f"line={rv['ml']:.4f}<sig={rv['ms']:.4f}"),
            "6. RSI <50 confirmed":     tick(short_sig["rsi_cross_bear"],
                f"rsi2={rv['rsi2']:.1f}>50 rsi1={rv['rsi1']:.1f}<=50 rsi0={rv['rsi0']:.1f}<rsi1"),
            "7. ADX >20 downtrend":     tick(short_sig["adx_bear"],
                f"adx={rv['adx']:.1f} price<ema21={rv['e21']:.2f}"),
            "8. Dist day (red+2×vol)":  tick(short_sig["high_volume_down"],
                f"red={'YES' if rv['candle_red'] else 'NO'}  vol={rv['vr']:.2f}×"),
            "9. Vol breakdown":         tick(short_sig["vol_breakdown"],
                f"price={rv['p']:.2f} 10dL={rv['l10']:.2f} vol={rv['vr']:.2f}×"),
            "10. Lower highs":          tick(short_sig["lower_highs"],
                f"{rv['swing_highs_count']} swing highs in last 60 bars"),
            "11. Operator distribution": tick(short_sig.get("operator_distribution", False),
                f"trap={rv.get('trap_risk_label','–')} vol={rv['vr']:.2f}×"),
            "12. Below VWAP":           tick(short_sig.get("below_vwap", False),
                f"price={rv['p']:.2f} vwap={rv.get('vwap', rv['p']):.2f}"),
            "SHORT score / prob":       f"{s_score}/{len(short_sig)}  →  {s_prob*100:.1f}%  ({prob_label(s_prob)})",
        }
    except Exception as e:
        return {"Error": str(e)}


