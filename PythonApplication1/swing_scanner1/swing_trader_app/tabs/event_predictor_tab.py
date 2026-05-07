"""Event Predictor Tab renderer.

Readable Streamlit tab code extracted from the original working monolith.
Each render function receives the main runtime globals as ``ctx`` and exposes
them to this module so the body behaves like it did in the single-file app.
"""

def _bind_runtime(ctx: dict) -> None:
    """Expose original app globals to this module for monolith-compatible tab code."""
    globals().update(ctx)

def render_event_predictor(ctx: dict) -> None:
    _bind_runtime(ctx)
    st.caption("📰 Event Predictor · combines earnings risk, recent news sentiment, order/contract keywords and trend confirmation")

    ev1, ev2, ev3 = st.columns([1, 1, 2])
    with ev1:
        ev_days = st.slider("Earnings window", 7, 60, 30, key="event_days")
    with ev2:
        ev_market = st.radio("Market", ["🇺🇸 US", "🇸🇬 SGX", "🇮🇳 India"], horizontal=True, key="event_market")
    with ev3:
        ev_extra = st.text_input("Tickers to check", placeholder="AIY.SI, OYY.SI, UUUU, NVDA", key="event_extra").strip().upper()

    if ev_market == "🇺🇸 US":
        ev_base = list(US_TICKERS[:120])
    elif ev_market == "🇸🇬 SGX":
        ev_base = list(SG_TICKERS)
    else:
        ev_base = list(INDIA_TICKERS)

    if ev_extra:
        extras = [x.strip() for x in ev_extra.split(",") if x.strip()]
        ev_base = extras + [x for x in ev_base if x not in extras]

    f1, f2 = st.columns([2, 2])
    with f1:
        ev_search = st.text_input("🔍 Search", placeholder="ticker", key="event_search").strip().upper()
    with f2:
        ev_verdict_filter = st.multiselect("Filter verdict", ["✅ BUY", "👀 WATCH", "⏳ WAIT", "🚫 AVOID"], default=[], key="event_verdict_filter", placeholder="All verdicts")

    if st.button("📰 Predict from Earnings + News + Orders", type="primary", key="btn_event_predictor"):
        st.session_state["event_df"] = fetch_event_predictions(tuple(dict.fromkeys(ev_base)), ev_days)

    event_df = st.session_state.get("event_df", pd.DataFrame())

    if event_df.empty:
        st.info("Enter tickers or select a market, then click 📰 Predict from Earnings + News + Orders.")
        st.caption("BUY requires enough event score plus trend confirmation. Near earnings ≤7 days is forced AVOID because gap risk is high.")
    else:
        df_event = event_df.copy()
        if ev_search:
            df_event = df_event[df_event["Ticker"].astype(str).str.contains(ev_search, case=False, na=False)]
        if ev_verdict_filter:
            df_event = df_event[df_event["Verdict"].isin(ev_verdict_filter)]

        b = (df_event["_vcol"] == "buy").sum()
        w = (df_event["_vcol"] == "watch").sum()
        wait = (df_event["_vcol"] == "wait").sum()
        a = (df_event["_vcol"] == "avoid").sum()
        st.caption(f"✅ **{b}** Buy · 👀 **{w}** Watch · ⏳ **{wait}** Wait · 🚫 **{a}** Avoid · {len(df_event)} shown")

        def _style_event_verdict(val):
            s = str(val)
            if "BUY" in s: return "background-color:#d4edda;color:#155724;font-weight:700"
            if "WATCH" in s: return "background-color:#d1ecf1;color:#0c5460;font-weight:600"
            if "WAIT" in s: return "background-color:#fff3cd;color:#856404"
            if "AVOID" in s: return "background-color:#f8d7da;color:#721c24;font-weight:700"
            return ""

        def _style_event_score(val):
            try:
                v = float(val)
                if v >= 8: return "color:#155724;font-weight:700"
                if v >= 6: return "color:#0c5460;font-weight:600"
                if v < 4: return "color:#721c24;font-weight:600"
            except Exception:
                pass
            return ""

        disp = [c for c in [
            "Ticker", "Price", "Earnings", "Days Out", "EPS Trend", "News", "Orders",
            "Trend Score", "Event Score", "Verdict", "Evidence", "Top News"
        ] if c in df_event.columns]
        df_show = df_event[disp].copy()
        if "Days Out" in df_show.columns:
            df_show["Days Out"] = pd.to_numeric(df_show["Days Out"], errors="coerce")

        col_cfg = {
            "Ticker": st.column_config.TextColumn("Ticker", width=70),
            "Price": st.column_config.TextColumn("Price", width=65),
            "Earnings": st.column_config.TextColumn("Earnings", width=120),
            "Days Out": st.column_config.NumberColumn("Days", width=50),
            "EPS Trend": st.column_config.TextColumn("EPS", width=70),
            "News": st.column_config.TextColumn("News", width=90),
            "Orders": st.column_config.TextColumn("Orders", width=110),
            "Trend Score": st.column_config.TextColumn("Trend", width=62),
            "Event Score": st.column_config.NumberColumn("Score", width=55),
            "Verdict": st.column_config.TextColumn("Verdict", width=90),
            "Evidence": st.column_config.TextColumn("Evidence", width=220),
            "Top News": st.column_config.TextColumn("Top News", width=420),
        }

        styler = df_show.style
        sfn = styler.map if hasattr(styler, "map") else styler.applymap
        styled = sfn(_style_event_verdict, subset=["Verdict"])
        styled = (styled.map if hasattr(styled, "map") else styled.applymap)(_style_event_score, subset=["Event Score"])

        st.dataframe(
            styled, width="stretch", hide_index=True,
            column_config={k:v for k,v in col_cfg.items() if k in df_show.columns},
            height=min(60 + len(df_show) * 36, 560)
        )
        st.warning("News/order detection uses recent yfinance headlines and keyword matching. Treat it as a watchlist filter, not a guarantee. Confirm important orders from SGX/company announcements before buying.")

