"""Extracted runtime section from app_runtime.py lines 2375-3192.
Loaded by app_runtime with exec(..., globals()) to preserve the original single-file behavior.
"""

def detect_traps(open_, high_, low_, close_, vol_, atr, swing_high, swing_low):
    """
    Detect classic operator manipulation patterns.

    Returns a list of tuples:
        (severity, label, detail, long_dir, short_dir)
    where severity ∈ {"high","med","low"} and *_dir ∈ {-1, 0, +1}.
    long_dir = +1 means the pattern supports going long; -1 contradicts long.
    short_dir is the mirror for shorts. 0 means neutral / informational.
    """
    traps = []
    try:
        N = 20
        if len(close_) < N + 5:
            return traps

        body_size  = (close_ - open_).abs()
        day_range  = (high_ - low_).replace(0, np.nan)
        body_top   = close_.combine(open_, max)
        body_bot   = close_.combine(open_, min)
        upper_wick = high_ - body_top
        lower_wick = body_bot - low_
        close_pos  = (close_ - low_) / day_range
        vol_avg20  = vol_.rolling(20).mean()
        vol_rat    = vol_ / vol_avg20

        p_now   = float(close_.iloc[-1])
        atr_now = float(atr)
        sw_hi   = float(swing_high)
        sw_lo   = float(swing_low)

        # 1) BULL TRAP — find highest-vol breakout in last 7d, check if trapped
        best_k = None; best_vr = 0; best_hi = 0
        for k in range(-min(7, len(high_) - N - 1), 0):
            pre_window = high_.iloc[k - N : k]
            if len(pre_window) < N:
                continue
            pre_hi = float(pre_window.max())
            if float(high_.iloc[k]) > pre_hi * 1.001:
                vk = float(vol_rat.iloc[k]) if pd.notna(vol_rat.iloc[k]) else 1.0
                if vk > best_vr:
                    best_vr = vk
                    best_k  = k
                    best_hi = float(high_.iloc[k])
        if best_k is not None and best_vr >= 1.3 and p_now < best_hi * 0.99:
            traps.append(("high",
                "🚨 BULL TRAP — failed breakout",
                f"Broke above ${best_hi:.2f} on {best_vr:.1f}× volume {abs(best_k)} session(s) ago, "
                f"now back below at ${p_now:.2f}.",
                -1, +1))

        # 2) BEAR TRAP — strongest-vol breakdown in last 7d, check if trapped
        best_k = None; best_vr = 0; best_lo = 0
        for k in range(-min(7, len(low_) - N - 1), 0):
            pre_window = low_.iloc[k - N : k]
            if len(pre_window) < N:
                continue
            pre_lo = float(pre_window.min())
            if float(low_.iloc[k]) < pre_lo * 0.999:
                vk = float(vol_rat.iloc[k]) if pd.notna(vol_rat.iloc[k]) else 1.0
                if vk > best_vr:
                    best_vr = vk
                    best_k  = k
                    best_lo = float(low_.iloc[k])
        if best_k is not None and best_vr >= 1.3 and p_now > best_lo * 1.01:
            traps.append(("high",
                "🚨 BEAR TRAP — failed breakdown",
                f"Broke below ${best_lo:.2f} on {best_vr:.1f}× volume {abs(best_k)} session(s) ago, "
                f"now back above at ${p_now:.2f}.",
                +1, -1))

        # 3) STOP HUNT — wick beyond swing on volume
        for k in [-1, -2, -3]:
            if -k > len(close_):
                continue
            uw = float(upper_wick.iloc[k]) if pd.notna(upper_wick.iloc[k]) else 0
            lw = float(lower_wick.iloc[k]) if pd.notna(lower_wick.iloc[k]) else 0
            bd = float(body_size.iloc[k])  if pd.notna(body_size.iloc[k])  else 0
            vk = float(vol_rat.iloc[k])    if pd.notna(vol_rat.iloc[k])    else 1.0
            hi_k = float(high_.iloc[k]); lo_k = float(low_.iloc[k]); cl_k = float(close_.iloc[k])

            if uw > 2 * bd and uw > 0.6 * atr_now and vk >= 1.3 \
                    and hi_k > sw_hi * 0.998 and cl_k < sw_hi:
                traps.append(("med",
                    "🎯 UPSIDE stop hunt",
                    f"{abs(k)} session(s) ago: long upper wick (${uw:.2f}) on {vk:.1f}× volume "
                    f"probed swing high ${sw_hi:.2f} and rejected.",
                    -1, +1))
                break
            if lw > 2 * bd and lw > 0.6 * atr_now and vk >= 1.3 \
                    and lo_k < sw_lo * 1.002 and cl_k > sw_lo:
                traps.append(("med",
                    "🎯 DOWNSIDE stop hunt",
                    f"{abs(k)} session(s) ago: long lower wick (${lw:.2f}) on {vk:.1f}× volume "
                    f"probed swing low ${sw_lo:.2f} and rejected.",
                    +1, -1))
                break

        cp10 = float(close_pos.iloc[-10:].mean()) if pd.notna(close_pos.iloc[-10:].mean()) else 0.5
        vr10 = float(vol_rat.iloc[-10:].mean())   if pd.notna(vol_rat.iloc[-10:].mean())   else 1.0
        ret10 = float((close_.iloc[-1] - close_.iloc[-10]) / close_.iloc[-10])

        # 4) DISTRIBUTION at top
        high20 = float(high_.iloc[-20:].max())
        if p_now > high20 * 0.95 and cp10 < 0.45 and vr10 > 1.15 and abs(ret10) < 0.04:
            traps.append(("high",
                "📤 DISTRIBUTION at top",
                f"Within 5% of recent high but last 10d: avg close in lower {cp10*100:.0f}% "
                f"of daily range, volume {vr10:.1f}× avg, net move {ret10*100:+.1f}%.",
                -1, +1))

        # 5) ACCUMULATION at bottom
        low20 = float(low_.iloc[-20:].min())
        if p_now < low20 * 1.05 and cp10 > 0.55 and vr10 > 1.15 and abs(ret10) < 0.04:
            traps.append(("high",
                "📥 ACCUMULATION at bottom",
                f"Within 5% of recent low but last 10d: avg close in upper {cp10*100:.0f}% "
                f"of daily range, volume {vr10:.1f}× avg, net move {ret10*100:+.1f}%.",
                +1, -1))

        # 6) GAP & REVERSE
        for k in [-1, -2]:
            if -k > len(close_) - 1:
                continue
            op_k = float(open_.iloc[k]); cl_k = float(close_.iloc[k]); pc_k = float(close_.iloc[k-1])
            gap  = (op_k - pc_k) / pc_k if pc_k else 0
            vk   = float(vol_rat.iloc[k]) if pd.notna(vol_rat.iloc[k]) else 1.0
            if gap > 0.012 and cl_k < pc_k and vk >= 1.2:
                traps.append(("med",
                    "🪤 GAP-UP and reverse",
                    f"{abs(k)}d ago: gapped up {gap*100:+.1f}%, closed {(cl_k-pc_k)/pc_k*100:+.1f}% "
                    f"on {vk:.1f}× volume.",
                    -1, +1))
                break
            if gap < -0.012 and cl_k > pc_k and vk >= 1.2:
                traps.append(("med",
                    "🪤 GAP-DOWN and reverse",
                    f"{abs(k)}d ago: gapped down {gap*100:+.1f}%, closed {(cl_k-pc_k)/pc_k*100:+.1f}% "
                    f"on {vk:.1f}× volume.",
                    +1, -1))
                break

        # 7) CLIMAX / EXHAUSTION
        vr_today  = float(vol_rat.iloc[-1])  if pd.notna(vol_rat.iloc[-1])  else 1.0
        cp_today  = float(close_pos.iloc[-1]) if pd.notna(close_pos.iloc[-1]) else 0.5
        ret_today = float((close_.iloc[-1] - close_.iloc[-2]) / close_.iloc[-2])
        if vr_today >= 2.5 and ret_today > 0.02 and cp_today < 0.4:
            traps.append(("med",
                "🌋 BUY climax (exhaustion)",
                f"Today: +{ret_today*100:.1f}% on {vr_today:.1f}× volume, closed in lower "
                f"{cp_today*100:.0f}% of range.",
                -1, +1))
        elif vr_today >= 2.5 and ret_today < -0.02 and cp_today > 0.6:
            traps.append(("med",
                "🌋 SELL climax (capitulation)",
                f"Today: {ret_today*100:.1f}% on {vr_today:.1f}× volume, closed in upper "
                f"{cp_today*100:.0f}% of range.",
                +1, -1))

        # 8) CHURN
        range10_pct = float((close_.iloc[-10:].max() - close_.iloc[-10:].min()) / close_.iloc[-10])
        if range10_pct < 0.04 and vr10 > 1.30:
            traps.append(("low",
                "🔄 CHURN — sideways heavy volume",
                f"Last 10d: only {range10_pct*100:.1f}% range, volume {vr10:.1f}× avg.",
                0, 0))

    except Exception:
        pass
    return traps


def summarize_traps(traps):
    """Summarize a traps list into compact strings for display in tables."""
    if not traps:
        return {"count": 0, "high": 0, "med": 0, "low": 0,
                "patterns": "–", "bias": "–", "bias_score": 0}
    high = sum(1 for t in traps if t[0] == "high")
    med  = sum(1 for t in traps if t[0] == "med")
    low  = sum(1 for t in traps if t[0] == "low")
    # Direction bias: positive = bullish operator activity (accumulation/bear traps)
    # Negative = bearish operator activity (distribution/bull traps)
    sev_w = {"high": 3, "med": 2, "low": 1}
    bias_score = sum(sev_w[t[0]] * t[3] for t in traps)  # use long_dir
    if   bias_score >=  4: bias = "🟢 BULLISH"
    elif bias_score >=  1: bias = "🟢 mild bull"
    elif bias_score <= -4: bias = "🔴 BEARISH"
    elif bias_score <= -1: bias = "🔴 mild bear"
    else:                  bias = "⚪ NEUTRAL"
    # Compact pattern list — just labels, comma-joined
    patterns = " · ".join(t[1].split(" — ")[0].split(" (")[0] for t in traps)
    return {"count": len(traps), "high": high, "med": med, "low": low,
            "patterns": patterns, "bias": bias, "bias_score": bias_score}


# ─────────────────────────────────────────────────────────────────────────────
# MAIN SCANNER  — v5 signal logic + v7 batch OHLCV pre-fetch
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def fetch_analysis(green_sectors, red_sectors, regime,
                   skip_earnings, top_n_sectors, live_sectors=None,
                   market_tickers=None, enable_options=True):
    sectors_data = live_sectors or {}
    sector_membership = {}
    for sec_name, sec_data in sectors_data.items():
        for t in sec_data.get("stocks", []):
            if t not in sector_membership:
                sector_membership[t] = sec_name

    # Use market-specific tickers if provided, else fall back to full BASE_TICKERS
    all_tickers = list(market_tickers) if market_tickers else list(BASE_TICKERS)
    for sec_name, sec_data in sectors_data.items():
        for t in sec_data.get("stocks", []):
            if t not in all_tickers:
                all_tickers.append(t)

    total = len(all_tickers)
    scan_debug = {
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "total_tickers": int(total),
        "batch_loaded": 0,
        "individual_loaded": 0,
        "skipped_history": 0,
        "skipped_liquidity": 0,
        "skipped_earnings": 0,
        "ticker_errors": 0,
        "ticker_error_samples": [],
        "batch_error": "",
        "empty_reason": "",
    }
    if total == 0:
        scan_debug["empty_reason"] = "No tickers were passed to fetch_analysis"
        try:
            st.session_state["last_scan_debug"] = scan_debug
            _record_app_warning("fetch_analysis", "No tickers were passed to fetch_analysis")
        except Exception:
            pass
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    green_set = set(green_sectors[:top_n_sectors])
    red_set   = set(red_sectors[:top_n_sectors])

    def sector_label(ticker):
        sec = sector_membership.get(ticker, "")
        if sec in green_set:  return f"🟢 {sec}"
        if sec in red_set:    return f"🔴 {sec}"
        return f"⚪ {sec}" if sec else "⚪ Mixed"

    long_results  = []
    short_results = []
    operator_results = []
    progress_bar  = st.progress(0)
    status_text   = st.empty()

    # ── Monday filter ─────────────────────────────────────────────────────────
    is_monday = datetime.today().weekday() == 0

    # ── Pre-fetch SPY for relative strength ───────────────────────────────────
    spy_close_global = None
    try:
        spy_raw = yf.download("SPY", period="1mo", interval="1d",
                              progress=False, auto_adjust=True)
        if isinstance(spy_raw.columns, pd.MultiIndex):
            spy_raw.columns = spy_raw.columns.get_level_values(0)
        spy_close_global = spy_raw["Close"].squeeze().ffill()
    except Exception:
        pass

    # ── Pre-fetch sector ETF closes for sector leader signal ─────────────────
    sector_etf_closes = {}
    try:
        etf_list = list(SECTOR_ETFS.values())
        etf_raw  = yf.download(etf_list, period="1mo", interval="1d",
                               progress=False, auto_adjust=True, group_by="ticker")
        for etf in etf_list:
            try:
                c = _extract_closes(etf_raw, etf, len(etf_list))
                if len(c) >= 6:
                    sector_etf_closes[etf] = c
            except Exception:
                continue
    except Exception:
        pass

    # ── Batch OHLCV pre-fetch ─────────────────────────────────────────────────
    status_text.text(f"📥 Batch downloading {total} stocks...")
    batch_cache = {}
    try:
        raw_batch = yf.download(
            all_tickers, period="6mo", interval="1d",
            progress=False, group_by="ticker", threads=True, auto_adjust=True
        )
        for tkr in all_tickers:
            try:
                if isinstance(raw_batch.columns, pd.MultiIndex):
                    lvl1 = raw_batch.columns.get_level_values(1)
                    lvl0 = raw_batch.columns.get_level_values(0)
                    if tkr in lvl1:    df_t = raw_batch.xs(tkr, axis=1, level=1).copy()
                    elif tkr in lvl0:  df_t = raw_batch[tkr].copy()
                    else:              continue
                elif len(all_tickers) == 1:
                    df_t = raw_batch.copy()
                else:
                    continue
                df_t = _clean_scan_ohlcv(df_t)
                if len(df_t) >= 60:
                    batch_cache[tkr] = df_t
            except Exception:
                continue
        scan_debug["batch_loaded"] = int(len(batch_cache))
        status_text.text(f"✅ {len(batch_cache)}/{total} stocks loaded")
    except Exception as e:
        scan_debug["batch_error"] = f"{type(e).__name__}: {e}"
        try:
            _record_app_error("batch_yfinance_download", e, extra={"total_tickers": total})
        except Exception:
            pass
        status_text.text(f"Batch failed ({e}), fetching individually...")

    # ── Regime thresholds — lowered to catch more real swing candidates ──────
    min_score_strong_long  = 5 if regime == "BULL"               else 6
    min_prob_strong_long   = 0.68 if regime == "BULL"            else 0.74
    min_score_strong_short = 4 if regime in ("BEAR", "CAUTION")  else 5
    min_prob_strong_short  = 0.65 if regime in ("BEAR", "CAUTION") else 0.68

    for i, ticker in enumerate(all_tickers):
        try:
            status_text.text(f"Scanning {ticker} ({i+1}/{total})...")

            # ── Earnings guard (14 days) ──────────────────────────────────────
            if skip_earnings:
                try:
                    info_cal = yf.Ticker(ticker).calendar
                    if info_cal is not None and not info_cal.empty:
                        ed = info_cal.loc["Earnings Date"].iloc[0] \
                             if "Earnings Date" in info_cal.index else info_cal.iloc[0, 0]
                        if not pd.isnull(ed):
                            days_out = (pd.Timestamp(ed).date() - datetime.today().date()).days
                            if 0 <= days_out <= 7:   # 7-day guard (was 14)
                                scan_debug["skipped_earnings"] += 1
                                progress_bar.progress((i + 1) / total)
                                continue
                except Exception:
                    pass

            # Use pre-fetched batch or individual fallback
            if ticker in batch_cache:
                df = batch_cache[ticker]
            else:
                raw_ind = yf.download(ticker, period="6mo", interval="1d",
                                      progress=False, auto_adjust=True)
                if raw_ind.empty or len(raw_ind) < 60:
                    scan_debug["skipped_history"] += 1
                    progress_bar.progress((i + 1) / total)
                    continue
                if isinstance(raw_ind.columns, pd.MultiIndex):
                    raw_ind.columns = raw_ind.columns.get_level_values(0)
                df = _clean_scan_ohlcv(raw_ind)
                if len(df) >= 60:
                    scan_debug["individual_loaded"] += 1

            if len(df) < 60:
                scan_debug["skipped_history"] += 1
                progress_bar.progress((i + 1) / total)
                continue

            close = df["Close"].squeeze().ffill()
            high  = df["High"].squeeze().ffill()
            low   = df["Low"].squeeze().ffill()
            vol   = df["Volume"].squeeze().ffill()

            # ── Pre-filter: liquidity only ────────────────────────────────────
            _vol_avg_s = float(vol.rolling(20).mean().iloc[-1])
            _p_chk     = float(close.iloc[-1])
            _atr_pct   = float(ta.volatility.average_true_range(
                             high, low, close, window=14).iloc[-1]) / _p_chk * 100 \
                         if _p_chk > 0 else 0
            # Skip if dollar volume < $500k/day (illiquid) or ATR < 0.8% (can't swing 5-10%)
            if _p_chk * _vol_avg_s < 500_000 or _atr_pct < 0.8:
                scan_debug["skipped_liquidity"] += 1
                progress_bar.progress((i + 1) / total)
                continue

            # Get sector ETF close for this ticker
            sec_name   = sector_membership.get(ticker, "")
            sec_etf    = SECTOR_ETFS.get(sec_name, "")
            sec_close  = sector_etf_closes.get(sec_etf, None)

            long_sig, short_sig, raw = compute_all_signals(
                close, high, low, vol,
                spy_close=spy_close_global,
                sector_close=sec_close,
            )
            p    = raw["p"]
            atrv = raw["atr"]
            vr   = raw["vr"]
            today_chg = _safe_today_change_pct(close)

            # ── Operator + Trap detection (universe-wide) ─────────────────────
            # Runs for every scanned ticker so the Operator Activity tab can
            # surface stocks with manipulation patterns even when they don't
            # show a long/short setup.
            try:
                open_s = df["Open"].squeeze().ffill()
                _traps = detect_traps(
                    open_s, high, low, close, vol,
                    atrv, raw["last_swing_high"], raw["last_swing_low"]
                )
                _tsum = summarize_traps(_traps)
                _op_score = int(raw.get("operator_score", 0))
                # Include any ticker with meaningful operator/trap activity:
                # operator_score ≥ 2, OR any pattern detected, OR a trap-risk flag.
                if _op_score >= 2 or _tsum["count"] >= 1 or raw.get("false_breakout") \
                        or raw.get("gap_chase_risk") or raw.get("operator_distribution"):
                    operator_results.append({
                        "Ticker":       ticker,
                        "Sector":       sector_label(ticker),
                        "Price":        f"${p:.2f}",
                        "Today %":      f"{today_chg:+.2f}%",
                        "Op Score":     _op_score,
                        "Op Label":     raw.get("operator_label", "–"),
                        "Trap Bias":    _tsum["bias"],
                        "Patterns":     f"{_tsum['count']} ({_tsum['high']}H · {_tsum['med']}M · {_tsum['low']}L)" if _tsum["count"] else "–",
                        "Detected":     _tsum["patterns"],
                        "Trap Risk":    raw.get("trap_risk_label", "–"),
                        "Vol Ratio":    round(vr, 2),
                        "VWAP":         "ABOVE" if raw.get("above_vwap") else "BELOW",
                        "RSI":          round(raw["rsi0"], 1),
                        "_bias_score":  _tsum["bias_score"],
                        "_op_score":    _op_score,
                        "_trap_count":  _tsum["count"],
                        "_high_count":  _tsum["high"],
                    })
            except Exception:
                pass

            # ── v12: OPTIONS ENRICHMENT ───────────────────────────────────────
            # Run only on US tickers that already show technical interest, so
            # we don't pay the option-chain HTTP cost on the full universe.
            # Failures fall through silently — keys simply won't be present
            # in long_sig/short_sig and bayesian_prob is unaffected.
            opt_long, opt_short, opt_raw = ({}, {}, {})
            if enable_options and _is_us_ticker_for_options(ticker):
                pre_l = sum(1 for v in long_sig.values()  if v)
                pre_s = sum(1 for v in short_sig.values() if v)
                if pre_l >= 4 or pre_s >= 3:
                    try:
                        rets   = close.pct_change().dropna().tail(20)
                        rv_pct = float(rets.std() * (252 ** 0.5) * 100) \
                                 if len(rets) >= 10 else None
                        opt_long, opt_short, opt_raw = compute_options_signals(
                            ticker, p, rv_pct
                        )
                    except Exception:
                        opt_long, opt_short, opt_raw = ({}, {}, {})

            # Merge option signals into the existing signal dicts. The
            # Bayesian engine only consumes keys present in LONG_WEIGHTS /
            # SHORT_WEIGHTS, so this is purely additive.
            long_sig  = {**long_sig,  **opt_long}
            short_sig = {**short_sig, **opt_short}

            # ── Float and short interest from yfinance.info ───────────────────
            float_shares = short_pct = pe = None
            try:
                inf = yf.Ticker(ticker).info
                float_shares = inf.get("floatShares")
                short_pct    = inf.get("shortPercentOfFloat")
                pe           = inf.get("trailingPE")
            except Exception:
                pass

            float_str = f"{float_shares/1e6:.0f}M" if float_shares else "–"
            short_str = f"{short_pct*100:.1f}%" if short_pct else "–"
            # Short squeeze flag: high short interest + bullish signals
            squeeze_flag = (short_pct or 0) > 0.15

            # ── Signal combination quality multiplier ─────────────────────────
            # Specific combos proven to be more accurate than raw score alone
            combo_bonus = 0.0
            # Combo A: compression → explosion (BB squeeze + vol breakout + stoch)
            if long_sig["bb_bull_squeeze"] and long_sig["vol_breakout"] and long_sig["stoch_confirmed"]:
                combo_bonus += 0.07
            # Combo B: momentum alignment (MACD accel + RSI>50 + higher lows)
            if long_sig["macd_accel"] and long_sig["rsi_confirmed"] and long_sig["higher_lows"]:
                combo_bonus += 0.06
            # Combo C: trend + structure + market alignment
            if long_sig["trend_daily"] and long_sig["weekly_trend"] and long_sig["rel_strength"]:
                combo_bonus += 0.05
            # Combo D: fresh golden cross + breakout = highest quality setup
            if raw.get("gc_fresh") and long_sig["vol_breakout"]:
                combo_bonus += 0.08

            # Monday penalty — reduce probability on Mondays
            monday_penalty = 0.06 if is_monday else 0.0

            # ── LONG ──────────────────────────────────────────────────────────
            l_score       = sum(v for k, v in long_sig.items() if v)
            l_bonus       = (0.06 if raw["bb_very_tight"] else 0) + \
                            (0.05 if vr >= 2.5 else 0) + combo_bonus
            l_regime_mult = 0.75 if regime == "BEAR" else 0.88 if regime == "CAUTION" else 1.0
            l_prob_raw    = bayesian_prob(LONG_WEIGHTS, long_sig, l_bonus)
            l_prob        = round(max(0.35, min(0.95,
                            l_prob_raw * l_regime_mult
                            + (1 - l_regime_mult) * 0.40
                            - monday_penalty)), 4)
            l_top3 = (
                long_sig["stoch_confirmed"] or
                long_sig["bb_bull_squeeze"] or
                long_sig["macd_accel"]      or
                long_sig["vol_breakout"]    or   # breakout on 10d high + vol
                long_sig.get("vol_surge_up", False)  # green candle + 2x vol + 1.5% up
            )

            operator_score = int(raw.get("operator_score", 0))
            operator_confirmed = operator_score >= 4
            false_breakout = bool(raw.get("false_breakout", False))
            gap_chase_risk = bool(raw.get("gap_chase_risk", False))
            distribution_risk = bool(raw.get("operator_distribution", False))
            trap_risk = false_breakout or gap_chase_risk or distribution_risk

            # ── HIGH-ACCURACY GATE ─────────────────────────────────────────────
            # This prevents the Bayesian score from becoming over-confident when
            # many correlated trend signals fire together. Only these setups are
            # allowed to become STRONG BUY / ✅ BUY. Everything else is WATCH/WAIT.
            volume_confirmed = (
                long_sig.get("vol_breakout", False) or
                long_sig.get("pocket_pivot", False) or
                long_sig.get("vol_surge_up", False)
            )
            high_accuracy_long = (
                l_prob >= 0.82 and
                l_score >= 8 and
                raw.get("above_ma60", False) and
                raw.get("not_chasing", False) and
                raw.get("not_limit_up", False) and
                raw.get("today_chg_pct", 99) < 6 and
                operator_confirmed and
                raw.get("vwap_support", False) and
                not trap_risk and
                long_sig.get("trend_daily", False) and
                long_sig.get("weekly_trend", False) and
                long_sig.get("rel_strength", False) and
                volume_confirmed
            )

            if high_accuracy_long:
                l_action = "STRONG BUY"
            elif trap_risk:
                l_action = "WATCH – TRAP RISK"
            elif l_score >= min_score_strong_long and l_prob >= min_prob_strong_long and l_top3:
                l_action = "WATCH – HIGH QUALITY"
            elif l_score >= 4 and l_prob >= 0.62 and long_sig["trend_daily"]:
                l_action = "WATCH – DEVELOPING"
            elif l_score >= 3 and long_sig["trend_daily"]:
                l_action = "WATCH – EARLY"
            else:
                l_action = None

            if l_action:
                # ── Strategy stop: MA60 or swing low (whichever is higher = tighter) ──
                l_atr_stop   = round(p - 1.5 * atrv, 2)
                l_swing_stop = round(raw["last_swing_low"] * 0.995, 2)
                l_ma60_stop  = round(raw["ma60"] * 0.995, 2)   # MA60 hard stop
                l_stop       = max(l_atr_stop, l_swing_stop, l_ma60_stop)
                l_risk       = max(p - l_stop, p * 0.001)       # prevent zero division

                # ── Strategy profit targets: 10% (short-term), 15%, 20% (swing) ────
                l_pt_short   = round(p * 1.10, 2)   # +10%  short-term take-profit (batch 1)
                l_pt_swing1  = round(p * 1.15, 2)   # +15%  swing take-profit (batch 2)
                l_pt_swing2  = round(p * 1.20, 2)   # +20%  swing full target (batch 3)
                l_trail      = round(p + l_risk * 0.5, 2)
                l_time_stop  = "Day 4 if < +5%"

                # ── Strategy filter tags ──────────────────────────────────────────
                strat_tags = []
                if raw.get("dip_to_ma20"):   strat_tags.append("📍DIP-MA20")
                if raw.get("dip_to_ma60"):   strat_tags.append("📍DIP-MA60")
                if raw.get("vol_declining"): strat_tags.append("📉VOL-DIP")
                if not raw.get("not_chasing", True):  strat_tags.append("⚠️CHASING")
                if not raw.get("not_limit_up", True): strat_tags.append("🚫LIMIT-UP")
                if raw.get("ma60_stop_triggered"):     strat_tags.append("🛑MA60-BREAK")

                # Strategy entry quality
                is_ideal_dip = (raw.get("dip_to_ma20") or raw.get("dip_to_ma60")) and \
                               raw.get("vol_declining") and raw.get("not_chasing") and \
                               raw.get("not_limit_up")
                is_vol_surge = long_sig.get("vol_surge_up", False)   # vol burst entry
                is_chasing   = not raw.get("not_chasing", True) or not raw.get("not_limit_up", True)
                is_stopped   = raw.get("ma60_stop_triggered", False)

                if is_stopped:
                    entry_quality = "🚫 AVOID"
                elif high_accuracy_long and (is_ideal_dip or is_vol_surge or long_sig.get("pocket_pivot", False) or long_sig.get("vol_breakout", False)):
                    entry_quality = "✅ BUY"
                elif is_chasing:
                    entry_quality = "⏳ WAIT"
                else:
                    entry_quality = "👀 WATCH"

                l_tags = []
                if long_sig["stoch_confirmed"]: l_tags.append("STOCH BOUNCE")
                if long_sig["bb_bull_squeeze"]: l_tags.append("BB BULL SQ")
                if long_sig["macd_accel"]:      l_tags.append("MACD ACCEL")
                if long_sig["vol_breakout"]:    l_tags.append("VOL BREAKOUT")
                if long_sig["higher_lows"]:     l_tags.append("HIGHER LOWS")
                if long_sig["rsi_confirmed"]:   l_tags.append("RSI>50")
                if long_sig["weekly_trend"]:    l_tags.append("WKLY TREND")
                if long_sig["golden_cross"]:    l_tags.append("🟡GC" if not raw.get("gc_fresh") else "🔥FRESH GC")
                if long_sig["rel_strength"]:    l_tags.append("RS>SPY")
                if long_sig["near_52w_high"]:   l_tags.append("52W HIGH")
                if long_sig["obv_rising"]:      l_tags.append("OBV↑")
                if long_sig["bull_candle"]:     l_tags.append("BULL CANDLE")
                if long_sig["sector_leader"]:   l_tags.append("SEC LEAD")
                if long_sig.get("vol_surge_up"):   l_tags.append("🚀VOL SURGE UP")
                if long_sig.get("pocket_pivot"):   l_tags.append("📌POCKET PIVOT")
                if squeeze_flag:                   l_tags.append("⚡SQUEEZE")
                if vr >= 2.5:                   l_tags.append("VOL SURGE")
                if is_monday:                   l_tags.append("⚠️MON")
                if combo_bonus > 0:             l_tags.append(f"COMBO+{combo_bonus:.0%}")
                if high_accuracy_long:          l_tags.append("🎯HIGH-ACCURACY")
                elif l_prob >= 0.82:            l_tags.append("⚠️PROB-NO-GATE")
                l_tags.extend(strat_tags)       # append strategy tags

                # ── v12: Options tags + smart targets + entry-tier downgrades ─
                opt_tags = []
                if opt_long.get("opt_unusual_call_flow"): opt_tags.append("🔥CALL FLOW")
                if opt_long.get("opt_call_skew_bullish"): opt_tags.append("📈CALL SKEW")
                if opt_long.get("opt_pc_volume_low"):     opt_tags.append("P/C↓")
                if opt_long.get("opt_iv_cheap"):          opt_tags.append("IV CHEAP")
                if opt_raw.get("term_inversion"):         opt_tags.append("⚠️IV INVERTED")
                if opt_raw.get("iv_rich"):                opt_tags.append("⚠️IV RICH")

                # If front-month IV is inverted, near-term event/fear is
                # priced in — downgrade a fresh ✅ BUY to 👀 WATCH.
                if opt_raw.get("term_inversion") and entry_quality == "✅ BUY":
                    entry_quality = "👀 WATCH"

                l_tags.extend(opt_tags)

                # Implied move (scaled to ~10 trading days) and "smart" TP
                # derived from it. Falls back to "–" when options data
                # is unavailable so the column behaviour is uniform.
                im_2w = opt_raw.get("implied_move_2w")
                if im_2w is not None and 0.005 <= im_2w <= 0.30:
                    implied_move_str = f"±{im_2w*100:.1f}%"
                    smart_tp_val     = round(p * (1 + max(im_2w, 0.05)), 2)
                    smart_tp_str     = f"${smart_tp_val:.2f}"
                else:
                    implied_move_str = "–"
                    smart_tp_str     = "–"

                ivr = opt_raw.get("iv_rank_proxy")
                iv_rank_str = f"{ivr:.2f}× RV" if ivr is not None else "–"

                long_results.append({
                    "Ticker":         ticker,
                    "Sector":         sector_label(ticker),
                    "Action":         l_action,
                    "Entry Quality":  entry_quality,
                    "Rise Prob":      f"{l_prob * 100:.1f}%",
                    "Prob Tier":      prob_label(l_prob),
                    "Score":          f"{l_score}/{len(long_sig)}",
                    "Operator":       raw.get("operator_label", "–"),
                    "Op Score":       str(raw.get("operator_score", 0)),
                    "VWAP":           "ABOVE" if raw.get("above_vwap") else "BELOW",
                    "Trap Risk":      raw.get("trap_risk_label", "–"),
                    "Today %":        f"{today_chg:+.2f}%",
                    "Price":          f"${p:.2f}",
                    "MA20":           f"${raw['ma20']:.2f}",
                    "MA60 Stop":      f"${l_ma60_stop:.2f}",
                    "Best Stop":      f"${l_stop:.2f}",
                    "TP1 +10%":       f"${l_pt_short:.2f}",
                    "TP2 +15%":       f"${l_pt_swing1:.2f}",
                    "TP3 +20%":       f"${l_pt_swing2:.2f}",
                    "Smart TP":       smart_tp_str,
                    "Implied Move 2W": implied_move_str,
                    "IV vs RV":       iv_rank_str,
                    "Trail Stop":     f"${l_trail:.2f}",
                    "Time Stop":      l_time_stop,
                    "Pos/$1k risk":   int(1000 / l_risk) if l_risk > 0 else 0,
                    "Float":          float_str,
                    "Short %":        short_str,
                    "Signals":        " | ".join(l_tags) if l_tags else "–",
                    "Opt Flow":       " | ".join(opt_tags) if opt_tags else "–",
                    "RSI":            round(raw["rsi0"], 1),
                    "Vol Ratio":      round(vr, 2),
                    "BB Squeeze":     "YES" if long_sig["bb_bull_squeeze"] else "–",
                })

            # ── SHORT ─────────────────────────────────────────────────────────
            s_score        = sum(v for k, v in short_sig.items() if v)
            s_regime_bonus = 0.08 if regime == "BEAR" else 0.03 if regime == "CAUTION" else 0
            s_prob_raw     = bayesian_prob(SHORT_WEIGHTS, short_sig, s_regime_bonus)
            s_prob         = round(max(0.35, min(0.95,
                             s_prob_raw - monday_penalty)), 4)
            s_top3         = (short_sig["stoch_overbought"] or
                              short_sig["bb_bear_squeeze"]  or
                              short_sig["macd_decel"])

            # ── HIGH-ACCURACY SHORT GATE ──────────────────────────────────────
            # Same idea as the long gate: high Fall Prob alone is not enough.
            # A true SELL needs bearish trend + breakdown/distribution volume +
            # no gap-down chase + no obvious short-squeeze risk.
            short_volume_confirmed = (
                short_sig.get("vol_breakdown", False) or
                short_sig.get("high_volume_down", False)
            )
            short_momentum_confirmed = (
                short_sig.get("macd_decel", False) or
                short_sig.get("stoch_overbought", False) or
                short_sig.get("rsi_cross_bear", False)
            )
            high_accuracy_short = (
                s_prob >= 0.82 and
                s_score >= 5 and
                short_sig.get("trend_bearish", False) and
                short_momentum_confirmed and
                short_volume_confirmed and
                raw.get("today_chg_pct", 0) > -6.0 and   # avoid chasing big gap-downs
                raw.get("today_chg_pct", 0) < 2.0 and    # avoid shorting strong green days
                not squeeze_flag                         # avoid crowded squeeze risk
            )

            if high_accuracy_short:
                s_action = "STRONG SHORT"
            elif s_score >= min_score_strong_short and s_prob >= min_prob_strong_short and s_top3:
                s_action = "WATCH SHORT – HIGH QUALITY"
            elif s_score >= 4 and s_prob >= 0.60 and short_sig["trend_bearish"]:
                s_action = "WATCH SHORT – DEVELOPING"
            elif s_score >= 3 and short_sig["trend_bearish"]:
                s_action = "WATCH SHORT – EARLY"
            else:
                s_action = None

            if s_action:
                s_atr_stop   = round(p + 1.5 * atrv, 2)
                s_swing_stop = round(raw["last_swing_high"] * 1.005, 2)
                s_cover      = min(s_atr_stop, s_swing_stop)
                s_risk       = s_cover - p
                s_t1         = round(p - s_risk * 1.0, 2)
                s_t2         = round(p - s_risk * 2.0, 2)
                s_trail      = round(p - s_risk * 0.5, 2)

                s_tags = []
                if short_sig["stoch_overbought"]:  s_tags.append("STOCH ROLLOVER")
                if short_sig["bb_bear_squeeze"]:   s_tags.append("BB BEAR SQ")
                if short_sig["macd_decel"]:        s_tags.append("MACD DECEL")
                if short_sig["vol_breakdown"]:     s_tags.append("VOL BREAKDOWN")
                if short_sig["lower_highs"]:       s_tags.append("LOWER HIGHS")
                if short_sig["rsi_cross_bear"]:    s_tags.append("RSI<50")
                if short_sig["high_volume_down"]:  s_tags.append("DIST DAY")
                if high_accuracy_short:             s_tags.append("🎯HIGH-ACCURACY")
                elif s_prob >= 0.82:                s_tags.append("⚠️PROB-NO-GATE")
                if squeeze_flag:                    s_tags.append("⚡SQUEEZE-RISK")
                if is_monday:                       s_tags.append("⚠️MON")

                # ── v12: Options tags for short ───────────────────────────────
                opt_s_tags = []
                if opt_short.get("opt_unusual_put_flow"):  opt_s_tags.append("🔻PUT FLOW")
                if opt_short.get("opt_put_skew_bearish"):  opt_s_tags.append("📉PUT SKEW")
                if opt_short.get("opt_term_inversion"):    opt_s_tags.append("⚠️IV INVERTED")
                if opt_short.get("opt_pc_volume_high"):    opt_s_tags.append("P/C↑")
                if opt_raw.get("iv_rich"):                 opt_s_tags.append("⚠️IV RICH")
                s_tags.extend(opt_s_tags)

                # Implied move row data — same scaling as long branch
                im_2w_s = opt_raw.get("implied_move_2w")
                if im_2w_s is not None and 0.005 <= im_2w_s <= 0.30:
                    implied_move_str_s = f"±{im_2w_s*100:.1f}%"
                else:
                    implied_move_str_s = "–"
                ivr_s = opt_raw.get("iv_rank_proxy")
                iv_rank_str_s = f"{ivr_s:.2f}× RV" if ivr_s is not None else "–"

                # Short entry quality — mirror of long but for sell setups
                s_is_ideal   = short_sig["trend_bearish"] and raw.get("vol_declining", False) \
                               and not raw.get("ma60_stop_triggered", False)
                s_is_chasing = raw.get("today_chg_pct", 0) < -8.0   # gapped down >8%, avoid
                s_is_stopped = not short_sig["trend_bearish"] and raw.get("above_ma60", True)

                if s_is_stopped or squeeze_flag:
                    s_entry_quality = "🚫 AVOID"
                elif high_accuracy_short and (s_is_ideal or short_sig.get("operator_distribution", False)):
                    s_entry_quality = "✅ SELL"
                elif s_is_chasing:
                    s_entry_quality = "⏳ WAIT"
                else:
                    s_entry_quality = "👀 WATCH"

                short_results.append({
                    "Ticker":         ticker,
                    "Sector":         sector_label(ticker),
                    "Action":         s_action,
                    "Entry Quality":  s_entry_quality,
                    "Fall Prob":      f"{s_prob * 100:.1f}%",
                    "Prob Tier":      prob_label(s_prob),
                    "Score":          f"{s_score}/{len(short_sig)}",
                    "Operator":       raw.get("operator_label", "–"),
                    "Op Score":       str(raw.get("operator_score", 0)),
                    "VWAP":           "ABOVE" if raw.get("above_vwap") else "BELOW",
                    "Trap Risk":      raw.get("trap_risk_label", "–"),
                    "Today %":        f"{today_chg:+.2f}%",
                    "Price":          f"${p:.2f}",
                    "Cover Stop":     f"${s_cover:.2f}",
                    "Target 1:1":     f"${s_t1:.2f}",
                    "Target 1:2":     f"${s_t2:.2f}",
                    "Implied Move 2W": implied_move_str_s,
                    "IV vs RV":       iv_rank_str_s,
                    "Trail Stop":     f"${s_trail:.2f}",
                    "Regime bonus":   "YES" if regime in ("BEAR","CAUTION") else "–",
                    "Float":          float_str,
                    "Short %":        short_str,
                    "RSI":            round(raw["rsi0"], 1),
                    "Vol Ratio":      round(vr, 2),
                    "Signals":        " | ".join(s_tags) if s_tags else "–",
                    "Opt Flow":       " | ".join(opt_s_tags) if opt_s_tags else "–",
                })

        except Exception as e:
            scan_debug["ticker_errors"] += 1
            if len(scan_debug["ticker_error_samples"]) < 25:
                scan_debug["ticker_error_samples"].append({"ticker": ticker, "error": f"{type(e).__name__}: {e}"})
            try:
                _record_app_error("scan_ticker", e, ticker=ticker, extra={"index": i + 1, "total": total})
            except Exception:
                pass
        progress_bar.progress((i + 1) / total)

    status_text.empty()
    progress_bar.empty()

    def make_df(rows, prob_col):
        if not rows:
            return pd.DataFrame()
        df_out = pd.DataFrame(rows)
        df_out["_s"] = df_out[prob_col].str.rstrip("%").astype(float)
        return df_out.sort_values("_s", ascending=False).drop(columns="_s")

    def make_op_df(rows):
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(rows).sort_values(
            ["_high_count", "_trap_count", "_op_score"],
            ascending=[False, False, False]
        )

    df_long_out = make_df(long_results, "Rise Prob")
    df_short_out = make_df(short_results, "Fall Prob")
    df_operator_out = make_op_df(operator_results)
    scan_debug.update({
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "long_rows_raw": int(len(df_long_out)),
        "short_rows_raw": int(len(df_short_out)),
        "operator_rows_raw": int(len(df_operator_out)),
    })
    if df_long_out.empty and df_short_out.empty and df_operator_out.empty:
        scan_debug["empty_reason"] = (
            "No rows passed filters. Check: Yahoo returned data count, liquidity/ATR filter, "
            "min probability filters, market closed/flat sectors, and any ticker errors below."
        )
        try:
            _record_app_warning("fetch_analysis_empty", scan_debug["empty_reason"], extra=scan_debug)
        except Exception:
            pass
    try:
        st.session_state["last_scan_debug"] = scan_debug
    except Exception:
        pass
    return (df_long_out, df_short_out, df_operator_out)


# ─────────────────────────────────────────────────────────────────────────────
# DIAGNOSTICS  — v5 exact
# ─────────────────────────────────────────────────────────────────────────────
