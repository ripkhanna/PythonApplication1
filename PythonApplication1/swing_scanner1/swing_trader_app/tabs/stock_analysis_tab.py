"""Stock Analysis Tab renderer.

Readable Streamlit tab code extracted from the original working monolith.
Each render function receives the main runtime globals as ``ctx`` and exposes
them to this module so the body behaves like it did in the single-file app.
"""

def _bind_runtime(ctx: dict) -> None:
    """Expose original app globals to this module for monolith-compatible tab code."""
    globals().update(ctx)

def render_stock_analysis(ctx: dict) -> None:
    _bind_runtime(ctx)
    st.caption("🔬 Stock Analysis")
    st.caption("Enter any ticker to get a full signal breakdown, chart, and trade plan")

    col_inp, col_per = st.columns([2, 1])
    with col_inp:
        stock_ticker = st.text_input(
            "Ticker symbol", placeholder="e.g. NVDA, D05.SI, TSLA",
            key="stock_analysis_ticker"
        ).strip().upper()
    with col_per:
        analysis_period = st.selectbox(
            "Chart period", ["3mo", "6mo", "1y", "2y"], index=1,
            key="stock_analysis_period"
        )

    if not stock_ticker:
        st.info("Enter a ticker above to analyse any stock — US, SGX (.SI), or any yfinance-supported symbol.")
    else:
        with st.spinner(f"Fetching {stock_ticker}..."):
            try:
                # ── Fetch data ────────────────────────────────────────────────
                raw_sa = yf.download(stock_ticker, period=analysis_period,
                                     interval="1d", progress=False, auto_adjust=True)
                if isinstance(raw_sa.columns, pd.MultiIndex):
                    raw_sa.columns = raw_sa.columns.get_level_values(0)

                if raw_sa.empty or len(raw_sa) < 30:
                    st.error(f"Not enough data for {stock_ticker}. Check the ticker symbol.")
                else:
                    close_sa = raw_sa["Close"].squeeze().ffill()
                    high_sa  = raw_sa["High"].squeeze().ffill()
                    low_sa   = raw_sa["Low"].squeeze().ffill()
                    vol_sa   = raw_sa["Volume"].squeeze().ffill()

                    # ── Compute all signals ───────────────────────────────────
                    long_sig_sa, short_sig_sa, rv_sa = compute_all_signals(
                        close_sa, high_sa, low_sa, vol_sa
                    )
                    l_score_sa = sum(long_sig_sa.values())
                    s_score_sa = sum(short_sig_sa.values())
                    l_prob_sa  = bayesian_prob(LONG_WEIGHTS,  long_sig_sa)
                    s_prob_sa  = bayesian_prob(SHORT_WEIGHTS, short_sig_sa)

                    # ── Fetch company info ────────────────────────────────────
                    try:
                        info_sa   = yf.Ticker(stock_ticker).info
                        comp_name = info_sa.get("longName") or info_sa.get("shortName") or stock_ticker
                        sector_sa = info_sa.get("sector", "–")
                        mktcap    = info_sa.get("marketCap", 0)
                        mktcap_str = f"${mktcap/1e9:.1f}B" if mktcap > 1e9 else (f"${mktcap/1e6:.0f}M" if mktcap else "–")
                        pe_ratio  = info_sa.get("trailingPE", None)
                        week52hi  = info_sa.get("fiftyTwoWeekHigh", None)
                        week52lo  = info_sa.get("fiftyTwoWeekLow",  None)
                    except Exception:
                        comp_name = stock_ticker
                        sector_sa = mktcap_str = "–"
                        pe_ratio = week52hi = week52lo = None

                    # ── Header ────────────────────────────────────────────────
                    st.markdown(f"## {comp_name} ({stock_ticker})")
                    c1,c2,c3 = st.columns(3)
                    c4,c5,c6 = st.columns(3)
                    c1.metric("Price",    f"${rv_sa['p']:.2f}")
                    c2.metric("Today %",  f"{_safe_today_change_pct(close_sa):+.2f}%")
                    c3.metric("Sector",   sector_sa)
                    c4.metric("Mkt Cap",  mktcap_str)
                    c5.metric("52W High", f"${week52hi:.2f}" if week52hi else "–")
                    c6.metric("52W Low",  f"${week52lo:.2f}" if week52lo else "–")

                    st.markdown("---")

                    # ── Operator + Trap detection (consumed by scorecards) ───
                    # Uses the shared detect_traps() helper — same logic that
                    # powers the universe-wide Operator Activity tab.
                    try:
                        open_sa = raw_sa["Open"].squeeze().ffill()
                        traps = detect_traps(
                            open_sa, high_sa, low_sa, close_sa, vol_sa,
                            rv_sa["atr"], rv_sa["last_swing_high"], rv_sa["last_swing_low"]
                        )
                    except Exception as trap_err:
                        traps = []
                        st.caption(f"_trap detector skipped: {trap_err}_")

                    # Helper: classify recommendation based on traps + base tier
                    def _trap_adjust(base_rec, base_col, my_dir_idx):
                        """my_dir_idx: 3 for long_dir field, 4 for short_dir."""
                        contra = [t for t in traps if t[my_dir_idx] == -1]
                        supp   = [t for t in traps if t[my_dir_idx] == +1]
                        high_c = sum(1 for t in contra if t[0] == "high")
                        med_c  = sum(1 for t in contra if t[0] == "med")
                        high_s = sum(1 for t in supp   if t[0] == "high")

                        if high_c >= 1 and "STRONG" in base_rec:
                            return "⚠️ TRAP DOWNGRADE — capped at WATCH", "warning", contra, supp
                        if high_c >= 1:
                            return f"⚠️ {base_rec} · trap warning", "warning", contra, supp
                        if med_c >= 2 and "STRONG" in base_rec:
                            return f"⚠️ {base_rec} · multiple trap warnings", "warning", contra, supp
                        if high_s >= 1 and "STRONG" in base_rec:
                            return "💎 STRONG + trap confluence", "success", contra, supp
                        if high_s >= 1 and ("WATCH" in base_rec or "DEVELOPING" in base_rec):
                            return f"⭐ {base_rec} · trap support", base_col, contra, supp
                        return base_rec, base_col, contra, supp

                    # ── Signal scorecard (trap-aware) ────────────────────────
                    col_long_sc, col_short_sc = st.columns(2)

                    with col_long_sc:
                        st.markdown("#### 📈 Long Signal Scorecard")
                        l_tier_col = "🟢" if l_prob_sa >= 0.72 else "🟡" if l_prob_sa >= 0.62 else "🔴"
                        st.markdown(f"**Score: {l_score_sa}/10 · Rise Prob: {l_tier_col} {l_prob_sa*100:.1f}% ({prob_label(l_prob_sa)})**")

                        signal_display = [
                            ("Trend (price>EMA8>EMA21)",  long_sig_sa["trend_daily"]),
                            ("Stoch confirmed bounce",    long_sig_sa["stoch_confirmed"]),
                            ("BB bull squeeze",           long_sig_sa["bb_bull_squeeze"]),
                            ("MACD acceleration",         long_sig_sa["macd_accel"]),
                            ("MACD crossover",            long_sig_sa["macd_cross"]),
                            ("RSI >50 confirmed",         long_sig_sa["rsi_confirmed"]),
                            ("ADX >20",                   long_sig_sa["adx"]),
                            ("Volume >1.5×",              long_sig_sa["volume"]),
                            ("Volume breakout",           long_sig_sa["vol_breakout"]),
                            ("Higher lows",               long_sig_sa["higher_lows"]),
                        ]
                        for sig_name, sig_val in signal_display:
                            icon = "✅" if sig_val else "❌"
                            st.markdown(f"{icon} {sig_name}")

                        # Long action — base tier
                        l_bonus_sa = (0.06 if rv_sa["bb_very_tight"] else 0) + (0.05 if rv_sa["vr"] >= 2.5 else 0)
                        l_top3_sa  = long_sig_sa["stoch_confirmed"] or long_sig_sa["bb_bull_squeeze"] or long_sig_sa["macd_accel"]
                        regime_cur = get_market_regime()["regime"]
                        min_score_l = 6 if regime_cur == "BULL" else 7
                        min_prob_l  = 0.72 if regime_cur == "BULL" else 0.78
                        if l_score_sa >= min_score_l and l_prob_sa >= min_prob_l and l_top3_sa:
                            l_rec_base = "🔥 STRONG BUY"
                            l_col_base = "success"
                        elif l_score_sa >= 4 and l_prob_sa >= 0.62 and long_sig_sa["trend_daily"]:
                            l_rec_base = "👀 WATCH – HIGH QUALITY"
                            l_col_base = "info"
                        elif l_score_sa >= 3 and long_sig_sa["trend_daily"]:
                            l_rec_base = "📋 WATCH – DEVELOPING"
                            l_col_base = "info"
                        else:
                            l_rec_base = "⏸️ NO LONG SETUP"
                            l_col_base = "warning"

                        # Apply trap adjustment (long_dir = field index 3)
                        l_rec, l_col, l_contra, l_supp = _trap_adjust(l_rec_base, l_col_base, 3)
                        getattr(st, l_col)(f"**Long: {l_rec}**")
                        if l_rec != l_rec_base:
                            st.caption(f"_base tier was: {l_rec_base}_")

                        # Trap evidence affecting LONG side — always shown
                        n_supp_l, n_contra_l = len(l_supp), len(l_contra)
                        if n_supp_l == 0 and n_contra_l == 0:
                            st.caption("🪤 **Operator patterns:** ✅ none detected")
                        else:
                            parts = []
                            if n_supp_l:
                                parts.append(f"⭐ {n_supp_l} supporting")
                            if n_contra_l:
                                parts.append(f"⚠️ {n_contra_l} contradicting")
                            st.markdown(f"🪤 **Operator patterns:** {' · '.join(parts)}")
                            for sev, label, detail, _, _ in l_supp:
                                with st.expander(f"⭐ {label}  _(supports long)_", expanded=(sev == "high")):
                                    st.markdown(detail)
                            for sev, label, detail, _, _ in l_contra:
                                with st.expander(f"⚠️ {label}  _(contradicts long)_", expanded=(sev == "high")):
                                    st.markdown(detail)

                    with col_short_sc:
                        st.markdown("#### 📉 Short Signal Scorecard")
                        s_tier_col = "🔴" if s_prob_sa >= 0.72 else "🟡" if s_prob_sa >= 0.62 else "⚪"
                        st.markdown(f"**Score: {s_score_sa}/10 · Fall Prob: {s_tier_col} {s_prob_sa*100:.1f}% ({prob_label(s_prob_sa)})**")

                        short_display = [
                            ("Trend (price<EMA8<EMA21)",  short_sig_sa["trend_bearish"]),
                            ("Stoch rollover",            short_sig_sa["stoch_overbought"]),
                            ("BB bear squeeze",           short_sig_sa["bb_bear_squeeze"]),
                            ("MACD deceleration",         short_sig_sa["macd_decel"]),
                            ("MACD bearish cross",        short_sig_sa["macd_cross_bear"]),
                            ("RSI <50 confirmed",         short_sig_sa["rsi_cross_bear"]),
                            ("ADX >20 downtrend",         short_sig_sa["adx_bear"]),
                            ("Distribution day",          short_sig_sa["high_volume_down"]),
                            ("Volume breakdown",          short_sig_sa["vol_breakdown"]),
                            ("Lower highs",               short_sig_sa["lower_highs"]),
                        ]
                        for sig_name, sig_val in short_display:
                            icon = "✅" if sig_val else "❌"
                            st.markdown(f"{icon} {sig_name}")

                        min_score_s = 5 if regime_cur in ("BEAR","CAUTION") else 6
                        min_prob_s  = 0.68 if regime_cur in ("BEAR","CAUTION") else 0.72
                        s_top3_sa   = short_sig_sa["stoch_overbought"] or short_sig_sa["bb_bear_squeeze"] or short_sig_sa["macd_decel"]
                        if s_score_sa >= min_score_s and s_prob_sa >= min_prob_s and s_top3_sa:
                            s_rec_base = "🔥 STRONG SHORT"
                            s_col_base = "error"
                        elif s_score_sa >= 4 and s_prob_sa >= 0.60 and short_sig_sa["trend_bearish"]:
                            s_rec_base = "👀 WATCH SHORT – HQ"
                            s_col_base = "warning"
                        elif s_score_sa >= 3 and short_sig_sa["trend_bearish"]:
                            s_rec_base = "📋 WATCH SHORT – DEV"
                            s_col_base = "warning"
                        else:
                            s_rec_base = "⏸️ NO SHORT SETUP"
                            s_col_base = "info"

                        # Apply trap adjustment (short_dir = field index 4)
                        s_rec, s_col, s_contra, s_supp = _trap_adjust(s_rec_base, s_col_base, 4)
                        getattr(st, s_col)(f"**Short: {s_rec}**")
                        if s_rec != s_rec_base:
                            st.caption(f"_base tier was: {s_rec_base}_")

                        # Trap evidence affecting SHORT side — always shown
                        n_supp_s, n_contra_s = len(s_supp), len(s_contra)
                        if n_supp_s == 0 and n_contra_s == 0:
                            st.caption("🪤 **Operator patterns:** ✅ none detected")
                        else:
                            parts = []
                            if n_supp_s:
                                parts.append(f"⭐ {n_supp_s} supporting")
                            if n_contra_s:
                                parts.append(f"⚠️ {n_contra_s} contradicting")
                            st.markdown(f"🪤 **Operator patterns:** {' · '.join(parts)}")
                            for sev, label, detail, _, _ in s_supp:
                                with st.expander(f"⭐ {label}  _(supports short)_", expanded=(sev == "high")):
                                    st.markdown(detail)
                            for sev, label, detail, _, _ in s_contra:
                                with st.expander(f"⚠️ {label}  _(contradicts short)_", expanded=(sev == "high")):
                                    st.markdown(detail)

                    st.markdown("---")

                    # ── Live indicator values ─────────────────────────────────
                    st.markdown("#### 📊 Live Indicator Values")
                    ci1,ci2,ci3,ci4 = st.columns(4)
                    ci5,ci6,ci7,ci8 = st.columns(4)
                    ci1.metric("RSI",       round(rv_sa["rsi0"],1))
                    ci2.metric("Stoch K",   round(rv_sa["k0"],1))
                    ci3.metric("ADX",       round(rv_sa["adx"],1))
                    ci4.metric("Vol Ratio", f"{rv_sa['vr']:.2f}×")
                    ci5.metric("EMA8",      f"${rv_sa['e8']:.2f}")
                    ci6.metric("EMA21",     f"${rv_sa['e21']:.2f}")
                    ci7.metric("MACD Hist", f"{rv_sa['mh0']:.4f}")
                    ci8.metric("BB Squeeze","YES" if rv_sa["bb_squeeze"] else "NO")

                    st.markdown("---")

                    # ── Trade plan ────────────────────────────────────────────
                    st.markdown("#### 💼 Trade Plan")
                    p_sa   = rv_sa["p"]
                    atr_sa = rv_sa["atr"]

                    tp1, tp2, tp3 = st.columns(3)

                    with tp1:
                        st.markdown("**📈 Long trade plan**")
                        l_atr_s  = round(p_sa - 1.5 * atr_sa, 2)
                        l_sw_s   = round(rv_sa["last_swing_low"] * 0.995, 2)
                        l_stop   = max(l_atr_s, l_sw_s)
                        l_risk   = p_sa - l_stop
                        st.markdown(f"Entry:        **${p_sa:.2f}**")
                        st.markdown(f"ATR stop:     ${l_atr_s:.2f}")
                        st.markdown(f"Swing stop:   ${l_sw_s:.2f}")
                        st.markdown(f"**Best stop:  ${l_stop:.2f}**")
                        st.markdown(f"Target 1:1:   ${round(p_sa+l_risk,2):.2f}")
                        st.markdown(f"**Target 1:2: ${round(p_sa+l_risk*2,2):.2f}**")
                        if l_risk > 0:
                            st.markdown(f"Pos/$1k risk: {int(1000/l_risk)} shares")

                    with tp2:
                        st.markdown("**📉 Short trade plan**")
                        s_atr_s  = round(p_sa + 1.5 * atr_sa, 2)
                        s_sw_s   = round(rv_sa["last_swing_high"] * 1.005, 2)
                        s_cover  = min(s_atr_s, s_sw_s)
                        s_risk   = s_cover - p_sa
                        st.markdown(f"Entry:        **${p_sa:.2f}**")
                        st.markdown(f"ATR cover:    ${s_atr_s:.2f}")
                        st.markdown(f"Swing cover:  ${s_sw_s:.2f}")
                        st.markdown(f"**Best cover: ${s_cover:.2f}**")
                        st.markdown(f"Target 1:1:   ${round(p_sa-s_risk,2):.2f}")
                        st.markdown(f"**Target 1:2: ${round(p_sa-s_risk*2,2):.2f}**")
                        if s_risk > 0:
                            st.markdown(f"Pos/$1k risk: {int(1000/s_risk)} shares")

                    with tp3:
                        st.markdown("**📐 Key levels**")
                        st.markdown(f"14d ATR:      **${atr_sa:.2f}** ({atr_sa/p_sa*100:.1f}%)")
                        st.markdown(f"Last swing ↓: ${rv_sa['last_swing_low']:.2f}  ({rv_sa['swing_lows_count']} detected)")
                        st.markdown(f"Last swing ↑: ${rv_sa['last_swing_high']:.2f}  ({rv_sa['swing_highs_count']} detected)")
                        st.markdown(f"10d high:     ${rv_sa['h10']:.2f}")
                        st.markdown(f"10d low:      ${rv_sa['l10']:.2f}")
                        st.markdown(f"BB midline:   ${rv_sa['bbm']:.2f}")
                        st.markdown(f"BB squeeze:   {'🟡 YES — coiling' if rv_sa['bb_squeeze'] else 'NO'}")

                    st.markdown("---")

                    # ── Price + indicator chart ───────────────────────────────
                    st.markdown("#### 📈 Price Chart with Indicators")
                    try:
                        import plotly.graph_objects as go
                        from plotly.subplots import make_subplots

                        # Build indicators for chart
                        ema8_chart  = ta.trend.ema_indicator(close_sa, window=8)
                        ema21_chart = ta.trend.ema_indicator(close_sa, window=21)
                        rsi_chart   = ta.momentum.rsi(close_sa, window=14)
                        macd_chart  = ta.trend.MACD(close_sa)
                        vol_avg_chart = vol_sa.rolling(20).mean()

                        dates = raw_sa.index

                        fig = make_subplots(
                            rows=4, cols=1,
                            shared_xaxes=True,
                            row_heights=[0.50, 0.18, 0.18, 0.14],
                            vertical_spacing=0.03,
                            subplot_titles=["Price + EMA8/21", "Volume", "RSI", "MACD Histogram"]
                        )

                        # Candlestick
                        fig.add_trace(go.Candlestick(
                            x=dates, open=raw_sa["Open"], high=high_sa,
                            low=low_sa, close=close_sa,
                            name="Price",
                            increasing_line_color="#27ae60",
                            decreasing_line_color="#e74c3c"
                        ), row=1, col=1)

                        fig.add_trace(go.Scatter(x=dates, y=ema8_chart,
                            line=dict(color="#f39c12", width=1.5),
                            name="EMA8"), row=1, col=1)
                        fig.add_trace(go.Scatter(x=dates, y=ema21_chart,
                            line=dict(color="#3498db", width=1.5),
                            name="EMA21"), row=1, col=1)

                        # Stop / target lines
                        fig.add_hline(y=rv_sa["last_swing_low"],
                            line_dash="dot", line_color="#e74c3c",
                            annotation_text="Swing Low (stop ref)", row=1, col=1)
                        fig.add_hline(y=rv_sa["last_swing_high"],
                            line_dash="dot", line_color="#27ae60",
                            annotation_text="Swing High", row=1, col=1)

                        # Volume bars
                        vol_colors = ["#27ae60" if c >= o else "#e74c3c"
                                      for c, o in zip(close_sa, raw_sa["Open"])]
                        fig.add_trace(go.Bar(x=dates, y=vol_sa,
                            marker_color=vol_colors, name="Volume",
                            showlegend=False), row=2, col=1)
                        fig.add_trace(go.Scatter(x=dates, y=vol_avg_chart,
                            line=dict(color="#f39c12", width=1),
                            name="Vol MA20"), row=2, col=1)

                        # RSI
                        fig.add_trace(go.Scatter(x=dates, y=rsi_chart,
                            line=dict(color="#9b59b6", width=1.5),
                            name="RSI"), row=3, col=1)
                        fig.add_hline(y=70, line_dash="dash",
                            line_color="#e74c3c", line_width=1, row=3, col=1)
                        fig.add_hline(y=50, line_dash="dash",
                            line_color="#95a5a6", line_width=1, row=3, col=1)
                        fig.add_hline(y=30, line_dash="dash",
                            line_color="#27ae60", line_width=1, row=3, col=1)

                        # MACD histogram
                        macd_h = macd_chart.macd_diff()
                        macd_colors = ["#27ae60" if v >= 0 else "#e74c3c" for v in macd_h]
                        fig.add_trace(go.Bar(x=dates, y=macd_h,
                            marker_color=macd_colors, name="MACD Hist",
                            showlegend=False), row=4, col=1)

                        fig.update_layout(
                            height=700,
                            plot_bgcolor="rgba(0,0,0,0)",
                            paper_bgcolor="rgba(0,0,0,0)",
                            xaxis_rangeslider_visible=False,
                            legend=dict(orientation="h", y=1.02),
                            margin=dict(l=0, r=0, t=30, b=0),
                            font=dict(size=11),
                        )
                        fig.update_yaxes(gridcolor="rgba(128,128,128,0.15)")
                        fig.update_xaxes(gridcolor="rgba(128,128,128,0.05)")

                        st.plotly_chart(fig, width="stretch")

                    except ImportError:
                        st.warning("Install plotly for charts: `pip install plotly`")
                    except Exception as chart_err:
                        st.warning(f"Chart error: {chart_err}")

            except Exception as outer_err:
                st.error(f"Error analysing {stock_ticker}: {outer_err}")

