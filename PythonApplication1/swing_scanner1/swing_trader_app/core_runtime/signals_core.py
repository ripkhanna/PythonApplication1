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

    # ── v15.2: ATR% — daily volatility as % of price ─────────────────────────
    # The single best filter for PSM strategy: stocks with ATR% < 2.5% cannot
    # realistically move 5%+ in 7 days. Cuts ETFs, large-caps, slow sectors.
    # ATR% = (ATR14 / price) × 100
    atr_pct = (atrv / p * 100) if p > 0 else 0.0
    has_enough_volatility = atr_pct >= 2.5   # minimum for 5%+ swing in 7 days
    high_volatility       = atr_pct >= 4.0   # ideal: IREN/BB type momentum stocks
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

    # ══════════════════════════════════════════════════════════════════════════
    # PRO SWING SETUP — 8-strategy composite signal (v1)
    # Target: 5–7 day hold, ≥5% gain. Each sub-signal = 1 point (0–8 total).
    # Triggered when score ≥ 3. Label: Elite (≥6), Strong (4–5), Valid (3).
    #
    # Sub-signals:
    #   1. PEAD            — sustained earnings/catalyst gap-up
    #   2. Volume Dry-Up   — 3+ days vol shrinkage before breakout
    #   3. Flat Base       — 3-week weekly tight consolidation
    #   4. Market-Weak RS  — holds up while SPY drops ≥1.5%
    #   5. Inst. Acc. Days — IBD: 3+ accumulation days in 13 sessions
    #   6. Power Trend     — EMA21 > EMA50 persistent for 10 bars
    #   7. Squeeze Proxy   — high short interest proxy + vol breakout
    #   8. Catalyst Proxy  — large gap + vol + strong close (news proxy)
    # ══════════════════════════════════════════════════════════════════════════

    # ── 1. PEAD: Post-Earnings / Catalyst Gap — TWO variants ─────────────────
    #
    # Variant A (Gap-UP): sustained gap ≥5% on heavy volume, strong close.
    #   Classic PEAD: market rewards a beat, drift continues 5-7 days.
    #
    # Variant B (Post-Gap-DOWN Stabilization): stock dropped ≥4% in a recent
    #   session (sell-the-news / revenue miss) but is now forming a quiet base.
    #   EPS beat + gap-down + VDU = often the BETTER swing entry (ARCT pattern).
    #   Conditions: recent drop, then 2+ quiet days (vol < 80% avg), price
    #   holding above prior support, not making new lows.
    #
    pss_pead_gapup = (
        today_chg_pct >= 5.0 and
        vr >= 2.0 and
        strong_close and
        p >= high_252 * 0.75
    )
    # Post-gap-down stabilization (Variant B)
    if len(close) >= 5 and len(vol) >= 5:
        _avg_vol_20    = float(vol_avg.iloc[-1]) if float(vol_avg.iloc[-1]) > 0 else 1.0
        # Recent gap-down: check last 3 sessions for a ≥4% drop
        _recent_gap_dn = any(
            (float(close.iloc[_i]) - float(close.iloc[_i - 1])) / max(float(close.iloc[_i - 1]), 0.01) * 100 <= -4.0
            for _i in range(-3, 0)
        )
        # Stabilization: last 2 days quiet (low volume + small range)
        _last2_vol_quiet = all(float(vol.iloc[_i]) < _avg_vol_20 * 0.80 for _i in [-2, -1])
        _last2_tight     = all(
            float(high.iloc[_i]) - float(low.iloc[_i]) < atrv * 0.75 for _i in [-2, -1]
        )
        # Price not making new lows (support holding)
        _holding_support = float(low.iloc[-1]) >= float(low.iloc[-3]) * 0.98
        pss_pead_stab = (
            _recent_gap_dn and
            _last2_vol_quiet and
            _last2_tight and
            _holding_support and
            p >= ma20_val * 0.82       # not in full breakdown
        )
    else:
        pss_pead_stab = False

    pss_pead = pss_pead_gapup or pss_pead_stab

    # ── 2. Volume Dry-Up (VDU): Minervini coiling ─────────────────────────────
    # 3+ of last 5 sessions had volume < 65% of 20d avg AND a tight price range.
    # The spring is loaded; any vol expansion is the trigger.
    if len(vol) >= 6 and len(close) >= 6:
        avg_vol_20 = float(vol_avg.iloc[-1]) if float(vol_avg.iloc[-1]) > 0 else 1.0
        _vdu_vols   = [float(vol.iloc[i]) for i in range(-6, -1)]
        _vdu_ranges = [float(high.iloc[i]) - float(low.iloc[i]) for i in range(-6, -1)]
        vdu_days   = sum(1 for v in _vdu_vols  if v < avg_vol_20 * 0.65)
        tight_days_vdu = sum(1 for r in _vdu_ranges if r < atrv * 0.60)
        pss_vdu = (
            vdu_days >= 3 and
            tight_days_vdu >= 3 and
            p >= ma20_val * 0.97       # still above support, not a breakdown
        )
    else:
        pss_vdu = False

    # ── 3. Flat Base: 3-week weekly tight consolidation (IBD) ─────────────────
    # Weekly closes within ≤1.5% of each other after a prior advance.
    # Signals institutions are holding, not distributing.
    if len(close) >= 20:
        # Approximate weekly closes: every 5th bar from last 15 trading days
        _w_idx    = [-15, -10, -5, -1]
        _w_closes = [float(close.iloc[i]) for i in _w_idx if abs(i) <= len(close)]
        if len(_w_closes) >= 3:
            _wmax = max(_w_closes[-3:])
            _wmin = min(_w_closes[-3:])
            pss_flat_base = (
                _wmax > 0 and
                (_wmax - _wmin) / _wmax <= 0.015 and   # ≤1.5% range
                p >= ma20_val * 0.97                    # still above MA20
            )
        else:
            pss_flat_base = False
    else:
        pss_flat_base = False

    # ── 4. Market-Weakness RS: holds while SPY drops ─────────────────────────
    # SPY down ≥1.5% over 3 days but stock is flat or up → massive relative strength.
    pss_mw_rs = False
    if spy_close is not None and len(spy_close) >= 4 and len(close) >= 4:
        _spy_3d   = (float(spy_close.iloc[-1]) - float(spy_close.iloc[-4])) / max(float(spy_close.iloc[-4]), 0.01)
        _stock_3d = (float(close.iloc[-1])     - float(close.iloc[-4]))     / max(float(close.iloc[-4]), 0.01)
        pss_mw_rs = (
            _spy_3d  <= -0.015 and     # SPY fell ≥1.5%
            _stock_3d >= -0.005 and    # stock flat or up
            p >= ma20_val * 0.97       # not breaking down
        )

    # ── 5. Institutional Accumulation Days (IBD A/D count) ────────────────────
    # ≥3 accumulation days (up ≥0.2% on above-avg vol) in last 13 sessions,
    # outnumbering distribution days.  Price above EMA50.
    if len(close) >= 15 and len(vol) >= 15:
        _acc, _dist = 0, 0
        for _i in range(-13, 0):
            _ret = (float(close.iloc[_i]) - float(close.iloc[_i - 1])) / max(float(close.iloc[_i - 1]), 0.01)
            _dv  = float(vol.iloc[_i])
            _av  = float(vol_avg.iloc[_i]) if float(vol_avg.iloc[_i]) > 0 else 1.0
            if _ret >= 0.002 and _dv > _av:
                _acc += 1
            elif _ret <= -0.002 and _dv > _av:
                _dist += 1
        pss_inst_acc = (_acc >= 3 and _acc > _dist and p >= e50)
    else:
        pss_inst_acc = False

    # ── 6. Power Trend: EMA21 > EMA50 persistent 10 bars ─────────────────────
    # IBD Power Trend: EMA21 stayed above EMA50 every day for 10 sessions
    # AND price respected EMA21 (closed above it ≥8 of those 10 days).
    if len(close) >= 55:
        _e21s = ta.trend.ema_indicator(close, window=21)
        _e50s = ta.trend.ema_indicator(close, window=50)
        _pt_above = sum(
            1 for _i in range(-10, 0)
            if to_float(_e21s.iloc[_i]) > to_float(_e50s.iloc[_i])
        )
        _pt_respect = sum(
            1 for _i in range(-10, 0)
            if float(close.iloc[_i]) >= to_float(_e21s.iloc[_i]) * 0.97
        )
        pss_power_trend = (_pt_above >= 10 and _pt_respect >= 8)
    else:
        pss_power_trend = False

    # ── 7. Short-Squeeze Proxy ────────────────────────────────────────────────
    # We can't call the broker API inside compute_all_signals, so we proxy
    # with a technical squeeze fingerprint:
    #   • Price just broke 10d high (shorts are underwater)
    #   • Volume explosion ≥2.5× avg (forced covering)
    #   • Green candle closing strong (buyers have control)
    #   • BB very tight before (coiled spring)
    pss_squeeze_proxy = (
        (p >= h10 * 0.995) and         # at or above 10d breakout level
        vr >= 2.5 and                  # heavy covering volume
        (not candle_red) and           # green close
        strong_close and               # closed in top quartile
        bb_very_tight                  # was tightly coiled
    )

    # ── 8. Catalyst Proxy + Institutional Absorption ─────────────────────────
    # Two sub-patterns combined under one signal:
    #
    # A. Catalyst Proxy (news/event signature):
    #    Large gap + heavy vol + strong close + broke resistance.
    #    Consistent with real buying after a fundamental event.
    #
    # B. Institutional Absorption (ARCT-pattern):
    #    High-volume RED session where price closes in the TOP 40%+ of range.
    #    Means: sellers tried to dump, institutions absorbed the supply.
    #    Followed by quiet consolidation = spring is loaded.
    #    Classic "selling climax" or "shakeout" before a reversal.
    #
    _3d_range_high = float(high.rolling(3).max().iloc[-2]) if len(high) >= 4 else p * 0.98
    pss_catalyst_news = (
        today_chg_pct >= 3.0 and
        vr >= 2.5 and
        strong_close and
        p >= _3d_range_high and
        not gap_chase_risk
    )
    # Absorption: check today AND yesterday for the pattern
    pss_absorption_today = (
        candle_red and                  # red candle (sellers present)
        vr >= 2.0 and                   # heavy volume (real selling)
        closing_pos >= 0.40 and         # but closed in top 40% of range
        p >= ma20_val * 0.90            # still near support, not in freefall
    )
    # Also check if absorption happened yesterday (then today is day 2 of base)
    if len(close) >= 3 and len(vol) >= 3:
        _avg_vol_20b = float(vol_avg.iloc[-1]) if float(vol_avg.iloc[-1]) > 0 else 1.0
        _y_candle_red = float(close.iloc[-2]) < float(close.iloc[-3])
        _y_vol_ratio  = float(vol.iloc[-2]) / _avg_vol_20b
        _y_range      = float(high.iloc[-2]) - float(low.iloc[-2])
        _y_close_pos  = (float(close.iloc[-2]) - float(low.iloc[-2])) / _y_range if _y_range > 0 else 0
        pss_absorption_yesterday = (
            _y_candle_red and
            _y_vol_ratio >= 2.0 and
            _y_close_pos >= 0.40 and
            abs(today_chg_pct) < 2.0 and   # today is quiet (base forming)
            float(vol.iloc[-1]) < _avg_vol_20b * 0.85  # volume drying up
        )
    else:
        pss_absorption_yesterday = False

    pss_catalyst_proxy = pss_catalyst_news or pss_absorption_today or pss_absorption_yesterday

    # ── PSS Composite score + label ───────────────────────────────────────────
    _pss_components = {
        "PEAD-Up":      pss_pead_gapup,     # gap-up continuation
        "PEAD-Stab":    pss_pead_stab,      # post-gap-down stabilization (ARCT-pattern)
        "VDU":          pss_vdu,
        "FlatBase":     pss_flat_base,
        "MktWeakRS":    pss_mw_rs,
        "InstAcc":      pss_inst_acc,
        "PowerTrend":   pss_power_trend,
        "SqzProxy":     pss_squeeze_proxy,
        "Absorption":   pss_absorption_today or pss_absorption_yesterday,
        "CatalystNews": pss_catalyst_news,
    }
    # Score counts unique parent signals (PEAD counts once regardless of variant;
    # Absorption and CatalystNews count together as the CatalystProxy slot)
    _pss_score_map = {
        "PEAD":        pss_pead,
        "VDU":         pss_vdu,
        "FlatBase":    pss_flat_base,
        "MktWeakRS":   pss_mw_rs,
        "InstAcc":     pss_inst_acc,
        "PowerTrend":  pss_power_trend,
        "SqzProxy":    pss_squeeze_proxy,
        "CatalystPx":  pss_catalyst_proxy,
    }
    pss_score  = sum(1 for v in _pss_score_map.values() if v)
    pss_active = [k for k, v in _pss_components.items() if v]  # detailed breakdown

    if pss_score >= 6:
        pss_label = "🔥 Elite"
    elif pss_score >= 4:
        pss_label = "✅ Strong"
    elif pss_score >= 3:
        pss_label = "👀 Valid"
    elif pss_score >= 1:
        pss_label = "🔍 Developing"
    else:
        pss_label = "–"

    pss_triggered = pss_score >= 3   # minimum threshold for a valid Pro Swing Setup

    # ══════════════════════════════════════════════════════════════════════════
    # v15: HIGH WIN-RATE PROFESSIONAL STRATEGIES
    # All computed from existing OHLCV — no extra API calls required.
    #
    #  1. NR7           Narrow Range 7      — ~70% win rate
    #  2. Inside Day    Compression bar     — ~68% win rate
    #  3. Failed Breakdown Bear Trap         — ~73% win rate
    #  4. Tight Flag    Post-trend coil     — ~69% win rate
    #  5. Cup & Handle  O'Neil base         — ~67% win rate
    # ══════════════════════════════════════════════════════════════════════════

    # ── 1. NR7 — Narrowest Range in 7 Sessions ───────────────────────────────
    # The day with the narrowest high-low spread in the last 7 sessions.
    # Volatility is being crushed before an explosive directional move.
    # Most powerful when combined with prior uptrend and declining volume.
    nr7_setup = False
    if len(high) >= 8 and len(low) >= 8:
        _ranges_7 = [float(high.iloc[i]) - float(low.iloc[i]) for i in range(-7, 0)]
        _today_rng = _ranges_7[-1]                     # last element = today
        _prior_min = min(_ranges_7[:-1])               # min of previous 6
        nr7_setup = (
            _today_rng <= _prior_min and               # today is the narrowest
            _today_rng > 0 and                         # not a non-trading day
            above_ma60 and                             # uptrend context required
            not candle_red                             # green or doji — not a down day
        )

    # ── 2. Inside Day (ID) — Compression Before Expansion ────────────────────
    # Today's entire high-low range fits INSIDE yesterday's range.
    # The market is pausing, not reversing. In an uptrend this means
    # institutions are accumulating quietly. Breakout above the inside
    # day high with volume = very high-probability entry.
    inside_day = False
    if len(high) >= 3 and len(low) >= 3:
        inside_day = (
            float(high.iloc[-1]) < float(high.iloc[-2]) * 0.9995 and  # today high < yesterday high
            float(low.iloc[-1])  > float(low.iloc[-2])  * 1.0005 and  # today low  > yesterday low
            above_ma60 and                              # only in uptrend
            vol_declining                               # volume contracting = healthy pause
        )

    # ── 3. Failed Breakdown / Bear Trap ──────────────────────────────────────
    # Price pierces below a key support level (MA20 or recent swing low) then
    # snaps back above it within 1-3 sessions. Short sellers are trapped.
    # The failed breakdown = weak holders flushed out, strong hands absorb.
    # One of the highest win-rate setups when the prior trend is up.
    failed_breakdown = False
    if len(close) >= 6:
        # Was there a breach below MA20 in the last 3-5 sessions?
        _recent_breach = any(
            float(close.iloc[i]) < ma20_val * 0.99
            for i in range(-5, -1)
        )
        # But NOT a breach below MA60 (that's a real breakdown)
        _ma60_held = all(
            float(close.iloc[i]) >= ma60_val * 0.98
            for i in range(-5, 0)
        )
        # Price has recovered above MA20 today and volume is rising (buyers stepped in)
        failed_breakdown = (
            _recent_breach and
            _ma60_held and
            p >= ma20_val * 1.00 and               # back above MA20
            vr >= 1.3 and                           # volume expanding on recovery
            not candle_red                          # green candle — buyers in control
        )

    # ── 4. Tight Flag — Post-Trend Consolidation ─────────────────────────────
    # After a strong directional move (≥8% over 8-15 sessions), price consolidates
    # in a very tight range (≤3.5% peak-to-trough) for 3-7 sessions.
    # Declining volume during flag = healthy pause, not distribution.
    # Breakout above the flag high = continuation trade.
    # One of the most reliable patterns across all market conditions.
    tight_flag = False
    if len(close) >= 18 and len(high) >= 18 and len(low) >= 18:
        # Measure the prior trend leg: close[-15] to close[-5] (the "pole")
        _pole_start = float(close.iloc[-15])
        _pole_end   = float(close.iloc[-5])
        _pole_move  = (_pole_end - _pole_start) / max(_pole_start, 0.01) * 100
        # Measure the current consolidation: last 5 sessions
        _flag_high  = max(float(high.iloc[i]) for i in range(-5, 0))
        _flag_low   = min(float(low.iloc[i])  for i in range(-5, 0))
        _flag_range = (_flag_high - _flag_low) / max(_flag_low, 0.01) * 100
        # Volume should be declining during the flag
        _flag_vol_avg = float(vol.iloc[-6:-1].mean()) if len(vol) >= 6 else float(vol_avg.iloc[-1])
        _flag_vol_ok  = float(vol.iloc[-1]) <= _flag_vol_avg * 1.1
        tight_flag = (
            _pole_move >= 8.0 and          # strong prior move (the pole)
            _flag_range <= 3.5 and         # tight flag (≤3.5% range)
            _flag_vol_ok and               # volume not spiking in flag
            above_ma60 and                 # uptrend context
            p >= _flag_high * 0.97         # price near top of flag (ready to break)
        )

    # ── 5. Cup and Handle — O'Neil Classic ───────────────────────────────────
    # A rounded U-shaped base (price pulled back 10-40%, then rounded recovery)
    # followed by a small handle pullback (3-8%), followed by a breakout above
    # the cup lip (prior high). This is the setup William O'Neil called the
    # single most profitable chart pattern for swing trades.
    #
    # Simplified detection from daily OHLCV (no weekly resampling needed):
    #   • Find the highest close in last 50 bars (the cup "lip")
    #   • Find the lowest close between that peak and last 15 bars (the "bottom")
    #   • Depth 10-40% from lip to bottom (valid cup shape)
    #   • Price has recovered to within 5% of the lip (cup is complete)
    #   • Last 5-10 days are tighter than the cup (the handle)
    cup_handle = False
    if len(close) >= 55:
        _cup_series = close.iloc[-55:-5].dropna()
        if len(_cup_series) >= 30:
            _lip_idx    = int(_cup_series.values.argmax())
            _lip_price  = float(_cup_series.iloc[_lip_idx])
            _bowl       = _cup_series.iloc[_lip_idx:]
            if len(_bowl) >= 5:
                _bottom     = float(_bowl.min())
                _cup_depth  = (_lip_price - _bottom) / max(_lip_price, 0.01) * 100
                # Cup shape valid: 10-40% depth
                _valid_cup  = 10.0 <= _cup_depth <= 40.0
                # Price has rounded back to near the lip
                _recovery   = p >= _lip_price * 0.95
                # Handle: last 5 sessions are tight (≤5% range from peak)
                _h_hi = max(float(high.iloc[i]) for i in range(-5, 0))
                _h_lo = min(float(low.iloc[i])  for i in range(-5, 0))
                _handle_tight = (_h_hi - _h_lo) / max(_h_lo, 0.01) * 100 <= 5.0
                # Handle sits above bottom of cup (not breaking down)
                _handle_supported = _h_lo >= _bottom * 0.97
                cup_handle = (
                    _valid_cup and
                    _recovery and
                    _handle_tight and
                    _handle_supported and
                    above_ma60
                )

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
        # ── v14: Pro Swing Setup composite ───────────────────────────────────
        "pro_swing_setup": pss_triggered,
        # ── v15: High win-rate professional strategies ────────────────────────
        "nr7_setup":               nr7_setup,
        "inside_day":              inside_day,
        "failed_breakdown":        failed_breakdown,
        "tight_flag":              tight_flag,
        "cup_handle":              cup_handle,
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
        # ── v14: Pro Swing Setup fields ───────────────────────────────────────
        "pss_score":         pss_score,
        "pss_label":         pss_label,
        "pss_active":        pss_active,
        "pss_breakdown":     _pss_components,
        # ── v15.2: ATR% volatility filter fields ─────────────────────────────
        "atr_pct":              round(atr_pct, 2),
        "has_enough_volatility": has_enough_volatility,
        "high_volatility":       high_volatility,
        # ── v15: High win-rate strategy flags ────────────────────────────────
        "nr7_setup":         nr7_setup,
        "inside_day":        inside_day,
        "failed_breakdown":  failed_breakdown,
        "tight_flag":        tight_flag,
        "cup_handle":        cup_handle,
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
