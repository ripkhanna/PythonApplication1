"""Swing Picks Tab renderer.

Readable Streamlit tab code extracted from the original working monolith.
Each render function receives the main runtime globals as ``ctx`` and exposes
them to this module so the body behaves like it did in the single-file app.
"""

def _bind_runtime(ctx: dict) -> None:
    """Expose original app globals to this module for monolith-compatible tab code."""
    globals().update(ctx)

def render_swing_picks(ctx: dict) -> None:
    _bind_runtime(ctx)
    st.caption("🎯 Swing Picks — Bayesian ensemble rank: scanner + operator + earnings + news + sector")
    st.info(
        "Run **🚀 Scan** first. This tab keeps Bayesian as the base model, then adds "
        "operator activity, recent Yahoo news sentiment, order/contract keywords, sector tailwind, "
        "and earnings/trap penalties. Strategy Lab ML is optional and only useful if it beats the baseline."
    )

    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        swing_max_candidates = st.slider("Candidates to enrich", 5, 50, 25, step=5, key="swing_pick_max")
    with c2:
        swing_event_days = st.slider("Earnings/news lookahead", 7, 45, 30, step=1, key="swing_pick_days")
    with c3:
        manual_swing_tickers = st.text_input(
            "➕ Force include from Long Setups",
            placeholder="UUUU, APP, NVDA",
            key="swing_pick_manual"
        ).strip().upper()

    if df_long.empty:
        st.warning("No Long Setups available yet. Click **🚀 Scan** in the main scanner first.")
    else:
        df_swing_source = df_long.copy()
        forced = [t.strip().upper() for t in manual_swing_tickers.replace("\n", ",").split(",") if t.strip()]
        if forced:
            forced_rows = df_long[df_long["Ticker"].astype(str).str.upper().isin(forced)]
            rest_rows = df_long[~df_long["Ticker"].astype(str).str.upper().isin(forced)]
            df_swing_source = pd.concat([forced_rows, rest_rows], ignore_index=True)

        if st.button("🎯 Build Swing Picks", type="primary", key="btn_build_swing_picks"):
            with st.spinner("Adding earnings/news scoring to current Long Setups…"):
                st.session_state["df_swing_picks"] = _make_swing_picks_from_scan(
                    df_swing_source,
                    max_candidates=swing_max_candidates,
                    event_days=swing_event_days,
                )

        swing_df = st.session_state.get("df_swing_picks", pd.DataFrame())
        if swing_df.empty:
            st.caption("Click **🎯 Build Swing Picks** to enrich the latest Long Setups.")
        else:
            buy_n = int(swing_df["Swing Verdict"].astype(str).str.startswith("✅").sum()) if "Swing Verdict" in swing_df.columns else 0
            watch_n = int(swing_df["Swing Verdict"].astype(str).str.startswith("👀").sum()) if "Swing Verdict" in swing_df.columns else 0
            wait_n = int(swing_df["Swing Verdict"].astype(str).str.startswith("⏳").sum()) if "Swing Verdict" in swing_df.columns else 0
            avoid_n = int(swing_df["Swing Verdict"].astype(str).str.startswith("🚫").sum()) if "Swing Verdict" in swing_df.columns else 0
            st.success(f"✅ {buy_n} BUY/WATCH ENTRY · 👀 {watch_n} WATCH · ⏳ {wait_n} WAIT · 🚫 {avoid_n} AVOID")

            display_cols = [c for c in [
                "Ticker", "Swing Verdict",
                "Final Swing Score", "Bayes Score", "Operator Score", "News Score", "Sector Score", "Earnings Risk",
                "Trap Risk Score", "Entry Quality", "Rise Prob", "Action",
                "Operator", "Op Score", "VWAP", "Trap Risk", "Today %", "Price",
                "Sector", "Earnings", "Days Out", "EPS Trend", "News", "Orders",
                "Event Score", "Event Verdict", "Why", "Top News",
                "MA60 Stop", "TP1 +10%", "TP2 +15%", "TP3 +20%"
            ] if c in swing_df.columns]
            st.dataframe(
                swing_df[display_cols],
                width="stretch",
                hide_index=True,
                height=min(420, 38 + 35 * len(swing_df)),
            )

            with st.expander("📋 Copy tickers by final verdict"):
                for label, prefix in [("BUY/WATCH ENTRY", "✅"), ("WATCH", "👀"), ("WAIT", "⏳"), ("AVOID", "🚫")]:
                    tickers_txt = ", ".join(swing_df[swing_df["Swing Verdict"].astype(str).str.startswith(prefix)]["Ticker"].astype(str).tolist()) if "Ticker" in swing_df.columns else ""
                    st.text_area(label, value=tickers_txt or "–", height=70, key=f"swing_copy_{prefix}")

