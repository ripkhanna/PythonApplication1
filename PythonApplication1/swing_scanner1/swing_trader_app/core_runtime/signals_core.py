"""Extracted runtime section from app_runtime.py lines 1229-1608.
Loaded by app_runtime with exec(..., globals()) to preserve the original single-file behavior.
"""

# ─────────────────────────────────────────────────────────────────────────────
def compute_all_signals(close, high, low, vol, spy_close=None, sector_close=None):
    """
    Computes all long and short signals.
    spy_close:    optional SPY Close series for relative strength calculation
    sector_close: optional sector ETF Close series for sector leader calculation
    """
    ema8   = ta.trend.ema_indicator(close, window=8)
    ema21  = ta.trend.ema_indicator(close, window=21)
    ema50  = ta.trend.ema_indicator(close, window=50)
    ema200 = ta.trend.ema_indicator(close, window=200)
    rsi    = ta.momentum.rsi(close, window=14)
    srsi_k = ta.momentum.stochrsi_k(close, window=14, smooth1=3, smooth2=3)
    srsi_d = ta.momentum.stochrsi_d(close, window=14, smooth1=3, smooth2=3)
    macd_o = ta.trend.MACD(close)
    bb     = ta.volatility.BollingerBands(close, window=20, window_dev=2)
    adx    = ta.trend.adx(high, low, close, window=14)
    atr    = ta.volatility.average_true_range(high, low, close, window=14)
    obv    = ta.volume.on_balance_volume(close, vol)
    vol_avg  = vol.rolling(20).mean()
    high_10d = high.rolling(10).max()
    low_10d  = low.rolling(10).min()
    bb_width = (bb.bollinger_hband() - bb.bollinger_lband()) / bb.bollinger_mavg()

    # ── Scalars ───────────────────────────────────────────────────────────────
    p    = to_float(close.iloc[-1])
    e8   = to_float(ema8.iloc[-1])
    e21  = to_float(ema21.iloc[-1])
    e50  = to_float(ema50.iloc[-1])
    e200 = to_float(ema200.iloc[-1]) if len(close) >= 200 else 0
    rsi0 = to_float(rsi.iloc[-1]);   rsi1 = to_float(rsi.iloc[-2]); rsi2 = to_float(rsi.iloc[-3])
    k0   = to_float(srsi_k.iloc[-1]); k1  = to_float(srsi_k.iloc[-2]); k2 = to_float(srsi_k.iloc[-3])
    d0   = to_float(srsi_d.iloc[-1])
    ml   = to_float(macd_o.macd().iloc[-1]);      ms  = to_float(macd_o.macd_signal().iloc[-1])
    mh0  = to_float(macd_o.macd_diff().iloc[-1]); mh1 = to_float(macd_o.macd_diff().iloc[-2])
    mh2  = to_float(macd_o.macd_diff().iloc[-3])
    adxv = to_float(adx.iloc[-1]); atrv = to_float(atr.iloc[-1])
    vr   = to_float(vol.iloc[-1]) / to_float(vol_avg.iloc[-1]) \
           if to_float(vol_avg.iloc[-1]) > 0 else 0
    bbwn = to_float(bb_width.iloc[-1]); bbm = to_float(bb.bollinger_mavg().iloc[-1])
    bbws = bb_width.dropna().tail(126)
    bbp20 = float(np.percentile(bbws, 20)) if len(bbws) >= 20 else 0
    bbp10 = float(np.percentile(bbws, 10)) if len(bbws) >= 10 else 0
    bb_squeeze    = bbwn <= bbp20
    bb_very_tight = bbwn <= bbp10
    h10  = to_float(high_10d.iloc[-1]); l10 = to_float(low_10d.iloc[-1])
    candle_red = float(close.iloc[-1]) < float(close.iloc[-2])

    # ── 52-week high ──────────────────────────────────────────────────────────
    high_252 = float(high.rolling(252).max().iloc[-1]) if len(high) >= 50 else float(high.max())

    # ── Weekly trend ──────────────────────────────────────────────────────────
    weekly_ema20 = to_float(ta.trend.ema_indicator(close, window=20).iloc[-1])
    weekly_ema50 = to_float(ta.trend.ema_indicator(close, window=50).iloc[-1])
    # Standard: price > MA20 > MA60 (healthy uptrend)
    weekly_trend_ok = (p > weekly_ema20) and (weekly_ema20 > weekly_ema50)
    # Relaxed: price just broke above MA20 on high volume (early breakout — MA60 can lag)
    weekly_trend_breakout = (p > weekly_ema20) and (vr >= 1.8)

    # ── Golden cross ──────────────────────────────────────────────────────────
    gc_now     = (e50 > e200) if e200 > 0 else False
    # Fresh golden cross = EMA50 crossed EMA200 within last 10 bars
    gc_fresh   = False
    if e200 > 0 and len(close) >= 210:
        e50_10 = to_float(ema50.iloc[-10])
        e200_10 = to_float(ema200.iloc[-10])
        gc_fresh = gc_now and (e50_10 <= e200_10)  # was below, now above

    # ── OBV trend (rising for 5 consecutive days) ─────────────────────────────
    obv_vals = obv.dropna().tail(6)
    obv_rising = len(obv_vals) >= 5 and all(
        obv_vals.iloc[i] < obv_vals.iloc[i+1] for i in range(len(obv_vals)-1)
    )

    # ── Bullish candlestick patterns ──────────────────────────────────────────
    o_last  = float(close.iloc[-2])   # use prev close as proxy for open
    c_last  = float(close.iloc[-1])
    h_last  = float(high.iloc[-1])
    l_last  = float(low.iloc[-1])
    body    = abs(c_last - o_last)
    candle_range = h_last - l_last
    lower_wick   = min(c_last, o_last) - l_last
    upper_wick   = h_last - max(c_last, o_last)
    # Hammer: small body, long lower wick, at or near support
    hammer = (lower_wick >= 2 * body) and (c_last >= o_last) and (body > 0)
    # Bullish engulfing: today's body fully engulfs yesterday's
    o_prev = float(close.iloc[-3])
    c_prev = float(close.iloc[-2])
    bull_engulf = (c_last > o_last) and (c_prev < o_prev) and \
                  (c_last > o_prev) and (o_last < c_prev)
    bull_candle = hammer or bull_engulf

    # ── ATR expansion (today's range > 1.2× ATR = breakout energy) ───────────
    today_range  = float(high.iloc[-1]) - float(low.iloc[-1])
    atr_expansion = today_range > 1.2 * atrv

    # ── Consolidation (3–8 tight days before today) ───────────────────────────
    if len(close) >= 10:
        recent_ranges = [float(high.iloc[i]) - float(low.iloc[i])
                         for i in range(-9, -1)]
        avg_recent_range = np.mean(recent_ranges) if recent_ranges else atrv
        tight_days = sum(1 for r in recent_ranges if r < 0.7 * atrv)
        consolidation = 3 <= tight_days <= 8
    else:
        consolidation = False

    # ── RSI bullish divergence (price lower low but RSI higher low) ───────────
    rsi_div = False
    if len(close) >= 20:
        # Compare last 2 swing lows in price vs RSI
        price_lows = find_swing_lows(close, 30, 2)
        rsi_series = rsi.dropna()
        if len(price_lows) >= 2 and len(rsi_series) >= 20:
            # Price made lower low
            p_lower = price_lows[-1][1] < price_lows[-2][1]
            # RSI at those same approximate positions
            try:
                idx1 = -int(len(close) - price_lows[-1][0])
                idx2 = -int(len(close) - price_lows[-2][0])
                r1 = float(rsi_series.iloc[idx1]) if abs(idx1) < len(rsi_series) else rsi0
                r2 = float(rsi_series.iloc[idx2]) if abs(idx2) < len(rsi_series) else rsi1
                rsi_div = p_lower and (r1 > r2)   # price down, RSI up = divergence
            except Exception:
                pass

    # ── Relative strength vs SPY ──────────────────────────────────────────────
    rel_strength = False
    if spy_close is not None and len(spy_close) >= 6 and len(close) >= 6:
        stock_5d = (float(close.iloc[-1]) - float(close.iloc[-6])) / float(close.iloc[-6])
        spy_5d   = (float(spy_close.iloc[-1]) - float(spy_close.iloc[-6])) / float(spy_close.iloc[-6])
        rel_strength = stock_5d > spy_5d

    # ── Sector leader ─────────────────────────────────────────────────────────
    sector_leader = False
    if sector_close is not None and len(sector_close) >= 6 and len(close) >= 6:
        stock_5d   = (float(close.iloc[-1]) - float(close.iloc[-6])) / float(close.iloc[-6])
        sector_5d  = (float(sector_close.iloc[-1]) - float(sector_close.iloc[-6])) / float(sector_close.iloc[-6])
        sector_leader = stock_5d > sector_5d

    # ── Swing structure ───────────────────────────────────────────────────────
    swing_lows  = find_swing_lows(low,  60, 3)
    swing_highs = find_swing_highs(high, 60, 3)
    higher_lows  = len(swing_lows)  >= 2 and swing_lows[-1][1]  > swing_lows[-2][1]
    lower_highs  = len(swing_highs) >= 2 and swing_highs[-1][1] < swing_highs[-2][1]
    last_swing_low  = swing_lows[-1][1]  if swing_lows  else p * 0.95
    last_swing_high = swing_highs[-1][1] if swing_highs else p * 1.05

    # ── [NEW] VCP TIGHTNESS (Volatility Contraction) ──────────────────────────
    # High-probability setups often happen when volatility "shrinks" before a move
    atr5 = ta.volatility.average_true_range(high, low, close, window=5).iloc[-1]
    atr20 = ta.volatility.average_true_range(high, low, close, window=20).iloc[-1]
    vcp_tightness = (atr5 / atr20) < 0.85 if atr20 > 0 else False

    # ── [NEW] STRONG CLOSE (Institutional Support) ────────────────────────────
    # A strong finish implies buyers held control into the close
    day_range = float(high.iloc[-1]) - float(low.iloc[-1])
    closing_pos = (float(close.iloc[-1]) - float(low.iloc[-1])) / day_range if day_range > 0 else 0
    strong_close = closing_pos >= 0.75

    # ── [NEW] RS MOMENTUM (Relative Strength Line) ────────────────────────────
    # Does the stock continue to gain ground vs SPY?
    rs_momentum = False
    if spy_close is not None and len(close) >= 20:
        rs_line = close / spy_close.reindex(close.index).ffill()
        rs_ema = rs_line.rolling(20).mean()
        rs_momentum = rs_line.iloc[-1] > rs_ema.iloc[-1]

    # ── STRATEGY SIGNALS (MA20/MA60 dip rules) ───────────────────────────────
    # MA20 and MA60 (proxy: EMA20=daily 20, EMA60=daily 60)
    ma20 = ta.trend.sma_indicator(close, window=20)
    ma60 = ta.trend.sma_indicator(close, window=60)
    ma20_val = to_float(ma20.iloc[-1])
    ma60_val = to_float(ma60.iloc[-1])

    # Volume trend — is volume decreasing over last 3 bars? (dip with declining vol = healthy pullback)
    vol_3d_avg = float(vol.iloc[-4:-1].mean()) if len(vol) >= 4 else float(vol_avg.iloc[-1])
    vol_declining = float(vol.iloc[-1]) < vol_3d_avg

    # Dip to MA20: price within 1% below/above MA20 AND declining volume
    dip_to_ma20 = (p >= ma20_val * 0.99) and (p <= ma20_val * 1.015) and vol_declining

    # Dip to MA60: price within 1.5% below/above MA60 AND declining volume
    dip_to_ma60 = (p >= ma60_val * 0.985) and (p <= ma60_val * 1.015) and vol_declining

    # No-chase filter: price NOT running away from MA20 (not >5% above MA20 = avoid chasing highs)
    #not_chasing = p <= ma20_val * 1.05
    not_chasing  = p <= ma20_val * 1.10

    # Limit-up filter: today's move not >8% (avoid limit-up/gap-up chasing)
    today_chg_pct = float((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100) if len(close) >= 2 else 0
    #not_limit_up = today_chg_pct < 8.0
    not_limit_up = today_chg_pct < 12.0


    # Stop-loss trigger: price broke below MA60 with significant volume (>1.5× avg)
    ma60_stop_triggered = (p < ma60_val * 0.995) and (vr >= 1.5)

    # Support hold: price holding ABOVE MA60 (not stopped out)
    above_ma60 = p >= ma60_val

    # ── Full MA stack: price > EMA8 > EMA21 > MA20 (3-stack — doesn't require MA60 alignment)
    # Relaxed: MA60 alignment excluded — misses early breakouts and recovering stocks like UUUU
    full_ma_stack = (p > e8) and (e8 > e21) and (e21 > ma20_val)

    # ── Momentum continuation: up 3 of last 5 days ───────────────────────────
    if len(close) >= 6:
        daily_returns = [float(close.iloc[i]) - float(close.iloc[i-1])
                         for i in range(-5, 0)]
        momentum_3d = sum(1 for r in daily_returns if r > 0) >= 3
    else:
        momentum_3d = False

    # ── [NEW] VWAP + OPERATOR / SMART-MONEY ACTIVITY LAYER ───────────────────
    # These are confirmation filters, not standalone reasons to buy. They look
    # for footprints of accumulation/distribution: volume expansion, close
    # location, OBV, VWAP control, and failed breakouts.
    try:
        typical_price = (high + low + close) / 3
        cum_vol = vol.replace(0, np.nan).cumsum()
        vwap_series = ((typical_price * vol).cumsum() / cum_vol).replace([np.inf, -np.inf], np.nan).ffill()
        vwap_now = float(vwap_series.iloc[-1]) if len(vwap_series.dropna()) else p
    except Exception:
        vwap_now = p

    above_vwap = p >= vwap_now
    below_vwap = p < vwap_now
    vwap_support = p >= vwap_now * 0.995

    false_breakout = (p >= h10 * 0.995) and (vr >= 1.8) and (not strong_close)
    gap_chase_risk = (today_chg_pct > 7.0) and (vr > 2.5)
    operator_distribution = (vr >= 1.8) and (today_chg_pct <= 0.5) and (not strong_close)

    operator_score = 0
    if (not candle_red) and (vr >= 2.0):
        operator_score += 2
    if (vr >= 1.5) and strong_close:
        operator_score += 2
    if obv_rising:
        operator_score += 1
    if (p >= h10 * 0.995) and (vr >= 1.8):
        operator_score += 2
    if above_vwap:
        operator_score += 1
    if (p > ma20_val) and above_ma60:
        operator_score += 1
    if 0 < today_chg_pct < 8:
        operator_score += 1
    # Accumulation/absorption: red/high-volume day but price closes off lows.
    if candle_red and (vr >= 1.8) and (closing_pos >= 0.45) and (p >= ma20_val * 0.98):
        operator_score += 2

    if false_breakout or gap_chase_risk or operator_distribution:
        operator_score = max(0, operator_score - 2)

    if operator_score >= 6:
        operator_label = "🔥 STRONG OPERATOR"
    elif operator_score >= 4:
        operator_label = "🟢 ACCUMULATION"
    elif operator_score >= 2:
        operator_label = "🟡 WEAK SIGNS"
    else:
        operator_label = "⚪ NONE"

    trap_risk_label = "FALSE BO" if false_breakout else "GAP CHASE" if gap_chase_risk else "DISTRIB" if operator_distribution else "–"

    # ── LONG signals (scored) ─────────────────────────────────────────────────
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
        "weekly_trend":    weekly_trend_ok or weekly_trend_breakout,
        "golden_cross":    gc_now,
        "rel_strength":    rel_strength,
        "near_52w_high":   (p >= high_252 * 0.90),
        "obv_rising":      obv_rising,
        "bull_candle":     bull_candle,
        "atr_expansion":   atr_expansion,
        "sector_leader":   sector_leader,
        "vcp_tightness":   vcp_tightness,
        "strong_close":    strong_close,
        "operator_accumulation": operator_score >= 4,
        "vwap_support":    vwap_support,
        "rs_momentum":     rs_momentum,
        "full_ma_stack":   full_ma_stack,
        "momentum_3d":     momentum_3d,
        "vol_surge_up":    (not candle_red) and (vr >= 2.0) and (today_chg_pct >= 1.5),
        "pocket_pivot":    (not candle_red) and (vr >= 1.5) and (p > ma20_val),
    }
    # Strategy entry signals — entry quality label only, NOT scored
    _strat = {
        "dip_to_ma20": dip_to_ma20,
        "dip_to_ma60": dip_to_ma60,
        "not_chasing": not_chasing and not_limit_up,
        "above_ma60":  above_ma60,
    }

    # ── SHORT signals ─────────────────────────────────────────────────────────
    short_signals = {
        "trend_bearish":    (p < e8) and (e8 < e21),
        "stoch_overbought": (k2 > 80) and (k1 > 80) and (k0 < k1) and (k0 < d0) and (k0 > 20),
        "bb_bear_squeeze":  bb_squeeze and (p < bbm),
        "macd_decel":       (mh0 < mh1 < mh2) and (mh0 < 0),
        "macd_cross_bear":  (ml < ms) and (mh0 < 0),
        "rsi_cross_bear":   (rsi2 > 50) and (rsi1 <= 50) and (rsi0 < rsi1) and (rsi0 > 28),
        "adx_bear":         adxv > 20 and (p < e21),
        "high_volume_down": candle_red and (vr >= 2.0),
        "operator_distribution": operator_distribution,
        "below_vwap":       below_vwap,
        "vol_breakdown":    (p <= l10 * 1.005) and (vr >= 1.8),
        "lower_highs":      lower_highs,
        # Strategy: MA60 stop-loss broken
        "ma60_stop":        ma60_stop_triggered,
    }

    raw = {
        "p": p, "e8": e8, "e21": e21, "e50": e50, "e200": e200,
        "rsi0": rsi0, "rsi1": rsi1, "rsi2": rsi2,
        "k0": k0, "k1": k1, "k2": k2, "d0": d0,
        "ml": ml, "ms": ms, "mh0": mh0, "mh1": mh1, "mh2": mh2,
        "adx": adxv, "atr": atrv, "vr": vr,
        "bbwn": bbwn, "bbp20": bbp20, "bbp10": bbp10, "bbm": bbm,
        "bb_squeeze": bb_squeeze, "bb_very_tight": bb_very_tight,
        "h10": h10, "l10": l10, "high_252": high_252,
        "last_swing_low":    last_swing_low,
        "last_swing_high":   last_swing_high,
        "swing_lows_count":  len(swing_lows),
        "swing_highs_count": len(swing_highs),
        "candle_red":        candle_red,
        "gc_fresh":          gc_fresh,
        "obv_rising":        obv_rising,
        "bull_candle":       bull_candle,
        "weekly_trend":      weekly_trend_ok,
        "full_ma_stack":     full_ma_stack,
        "momentum_3d":       momentum_3d,
        # Strategy fields (entry quality only — not scored)
        "ma20":              ma20_val,
        "ma60":              ma60_val,
        "dip_to_ma20":       _strat["dip_to_ma20"],
        "dip_to_ma60":       _strat["dip_to_ma60"],
        "not_chasing":       not_chasing,
        "not_limit_up":      not_limit_up,
        "vol_declining":     vol_declining,
        "above_ma60":        _strat["above_ma60"],
        "ma60_stop_triggered": ma60_stop_triggered,
        "today_chg_pct":     today_chg_pct,
        "vwap":              vwap_now,
        "above_vwap":        above_vwap,
        "below_vwap":        below_vwap,
        "vwap_support":      vwap_support,
        "operator_score":    operator_score,
        "operator_label":    operator_label,
        "false_breakout":    false_breakout,
        "gap_chase_risk":    gap_chase_risk,
        "operator_distribution": operator_distribution,
        "trap_risk_label":   trap_risk_label,
    }
    return long_signals, short_signals, raw


# ─────────────────────────────────────────────────────────────────────────────
# OPTIONS SIGNALS (v12)  — forward-looking flow / IV / positioning
#
# Why this exists: price/volume signals are reactive. Options markets aggregate
# the views of leveraged, often better-informed participants and price expected
# moves, fear, and positioning *before* spot moves. Folding a small set of
# option-derived flags into the existing Bayesian engine is purely additive:
# if the data is missing (no options market, illiquid chain, fetch failure),
# the keys aren't present and probabilities are unchanged.
#
# Backends supported:
#   • US (.US-listed)  → yfinance Ticker.options / option_chain
#   • India (.NS)      → nsepython (only the ~200 F&O-listed stocks have chains)
#   • SGX, HK, others  → no options market or no public chain → skipped
