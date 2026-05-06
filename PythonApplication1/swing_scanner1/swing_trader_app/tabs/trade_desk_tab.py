"""Trade Desk Tab renderer.

Readable Streamlit tab code extracted from the original working monolith.
Each render function receives the main runtime globals as ``ctx`` and exposes
them to this module so the body behaves like it did in the single-file app.
"""

def _bind_runtime(ctx: dict) -> None:
    """Expose original app globals to this module for monolith-compatible tab code."""
    globals().update(ctx)

def render_trade_desk(ctx: dict) -> None:
    _bind_runtime(ctx)
    st.caption("📋 Trade Desk — execution tools added without changing scanner signals")
    st.info("Trade Desk supports both BUY/LONG and SELL/SHORT planning. By default it mirrors Long Setups for BUY and Short Setups for SELL; filters only reduce rows when you apply them.")

    # ── Top controls: side + filters before any grid ───────────────────────
    tc1, tc2, tc3, tc4, tc5 = st.columns([1.1, 1.1, 1.1, 1.1, 1.4])
    with tc1:
        td_side = st.radio("Buy / Sell", ["BUY", "SELL"], horizontal=True, key="td_side_top")
    with tc2:
        td_min_prob = st.slider("Min probability %", 0, 95, 0, step=5, key="td_min_prob")
    with tc3:
        td_entry_filter = st.selectbox("Entry filter", ["All", "✅ BUY", "👀 WATCH", "⏳ WAIT", "🚫 AVOID"], key="td_entry_filter")
    with tc4:
        td_trap_filter = st.selectbox("Trap filter", ["All", "No trap only", "Trap only"], key="td_trap_filter")
    with tc5:
        td_ticker_filter = st.text_input("Ticker contains", "", key="td_ticker_filter").upper().strip()

    if td_side == "SELL":
        # Trade Desk SELL must mirror the Short Setups tab by default.
        # Filters below are optional and default to showing everything.
        source_df = df_short.copy() if isinstance(df_short, pd.DataFrame) else pd.DataFrame()
        source_label = "Short Setups"
        prob_col = "Fall Prob"
    else:
        # Trade Desk BUY must mirror the Long Setups tab by default.
        # Swing Picks is a stricter shortlist, so using it here made Trade Desk
        # show fewer trades than the Long Setups tab. Keep Trade Desk execution
        # plans based on df_long and let the user filter down manually.
        source_df = df_long.copy() if isinstance(df_long, pd.DataFrame) else pd.DataFrame()
        source_label = "Long Setups"
        prob_col = "Rise Prob"

    filtered_source_df = source_df.copy() if isinstance(source_df, pd.DataFrame) else pd.DataFrame()
    if filtered_source_df is not None and not filtered_source_df.empty:
        if prob_col in filtered_source_df.columns:
            _p = filtered_source_df[prob_col].astype(str).str.replace("%", "", regex=False).replace("", np.nan)
            filtered_source_df = filtered_source_df[pd.to_numeric(_p, errors="coerce").fillna(0) >= td_min_prob]
        if td_entry_filter != "All" and "Entry Quality" in filtered_source_df.columns:
            filtered_source_df = filtered_source_df[filtered_source_df["Entry Quality"].astype(str).str.startswith(td_entry_filter.split()[0], na=False)]
        if td_trap_filter != "All" and "Trap Risk" in filtered_source_df.columns:
            trap_series = filtered_source_df["Trap Risk"].astype(str).str.strip()
            no_trap = trap_series.isin(["–", "-", "", "None", "nan"])
            filtered_source_df = filtered_source_df[no_trap] if td_trap_filter == "No trap only" else filtered_source_df[~no_trap]
        if td_ticker_filter and "Ticker" in filtered_source_df.columns:
            filtered_source_df = filtered_source_df[filtered_source_df["Ticker"].astype(str).str.upper().str.contains(td_ticker_filter, na=False)]

    st.caption(f"Side: {td_side} · Source: {source_label} · Filtered candidates: {0 if filtered_source_df is None else len(filtered_source_df)}")

    td_tabs = st.tabs(["🧾 Trade Plans", "⚖️ Position Sizing", "⭐ Setup Quality", "🌊 Market Breadth"])

    with td_tabs[0]:
        st.markdown("### Trade Plan Generator")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            td_account = st.number_input("Account size", min_value=1000.0, value=10000.0, step=1000.0, key="td_account")
        with c2:
            td_risk = st.slider("Risk per trade %", 0.25, 5.0, 1.0, step=0.25, key="td_risk")
        with c3:
            td_cap = st.slider("Max capital per trade %", 2.0, 50.0, 20.0, step=1.0, key="td_cap")
        with c4:
            td_stop = st.slider("Fallback stop %", 2.0, 12.0, 5.0, step=0.5, key="td_stop")
        if filtered_source_df is None or filtered_source_df.empty:
            st.warning("Run 🚀 Scan or relax the top filters to build trade plans.")
        else:
            plan_df = _td_make_trade_plan(filtered_source_df, side=td_side, account_size=td_account, risk_pct=td_risk, max_cap_pct=td_cap, default_stop_pct=td_stop)
            plan_df = _td_sort_trade_plans(plan_df, side=td_side)
            st.caption(f"Side: {td_side} · Source: {source_label} · {len(plan_df)} planned candidates · Action verdicts sorted first")
            st.dataframe(plan_df, width="stretch", hide_index=True, height=min(460, 38 + 35 * len(plan_df)))
            st.download_button("Download trade plans CSV", plan_df.to_csv(index=False).encode("utf-8"), "trade_plans.csv", "text/csv", key="td_plan_download")

    with td_tabs[1]:
        st.markdown("### Position Size Calculator")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            calc_account = st.number_input("Account", min_value=1000.0, value=float(st.session_state.get("td_account", 10000.0)), step=1000.0, key="td_calc_account")
        with c2:
            calc_risk = st.slider("Risk %", 0.25, 5.0, float(st.session_state.get("td_risk", 1.0)), step=0.25, key="td_calc_risk")
        with c3:
            calc_entry = st.number_input("Entry price", min_value=0.0001, value=100.0, step=1.0, key="td_calc_entry")
        with c4:
            calc_stop = st.number_input("Stop price", min_value=0.0001, value=95.0, step=1.0, key="td_calc_stop")
        risk_amt = calc_account * calc_risk / 100.0
        risk_per_share = abs(calc_entry - calc_stop)
        if risk_per_share <= 0:
            risk_per_share = 0.0001
        qty = int(risk_amt // risk_per_share)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Risk amount", f"{risk_amt:,.2f}")
        c2.metric("Risk/share", f"{risk_per_share:,.2f}")
        c3.metric("Suggested Qty", f"{qty:,}")
        c4.metric("Capital needed", f"{qty * calc_entry:,.2f}")
        st.caption(f"Side: {td_side}. Formula: quantity = account risk amount / absolute entry-stop risk.")

    with td_tabs[2]:
        st.markdown("### Breakout / Pullback Quality Score")
        if filtered_source_df is None or filtered_source_df.empty:
            st.warning("No setup data after filters.")
        else:
            rows = []
            for _, r in filtered_source_df.iterrows():
                b_score, b_label, p_score, p_label = _td_score_setup(r, side=td_side)
                rows.append({
                    "Side": "SELL/SHORT" if td_side == "SELL" else "BUY/LONG",
                    "Ticker": r.get("Ticker", ""),
                    "Primary Score": b_score,
                    "Primary Quality": b_label,
                    "Secondary Score": p_score,
                    "Secondary Quality": p_label,
                    prob_col: r.get(prob_col, r.get("Bayes Score", "–")),
                    "Operator": r.get("Operator", "–"),
                    "Op Score": r.get("Op Score", r.get("Operator Score", "–")),
                    "VWAP": r.get("VWAP", "–"),
                    "Trap Risk": r.get("Trap Risk", "–"),
                    "Today %": r.get("Today %", "–"),
                    "Entry Quality": r.get("Entry Quality", "–"),
                })
            qdf = pd.DataFrame(rows).sort_values(["Primary Score", "Secondary Score"], ascending=False)
            st.dataframe(qdf, width="stretch", hide_index=True, height=min(460, 38 + 35 * len(qdf)))

    with td_tabs[3]:
        st.markdown("### Market Breadth + Risk Mode")
        regime_info = get_market_regime() if market_sel == "🇺🇸 US" else {"regime": "LOCAL", "vix": 0}
        breadth_df = _td_market_breadth(df_long, df_short, df_operator, regime_info)
        st.dataframe(breadth_df, width="stretch", hide_index=True)
        mode = str(breadth_df.iloc[0].get("Risk Mode", "Selective")) if not breadth_df.empty else "Selective"
        if mode == "Aggressive":
            st.success("Market breadth supports taking the best long setups with normal risk controls.")
        elif mode == "Normal":
            st.info("Market breadth is acceptable. Prefer high-quality setups and avoid trap-risk names.")
        elif mode == "Defensive":
            st.warning("Defensive mode: reduce size, avoid marginal longs, and consider short setups only if liquid/borrowable.")
        else:
            st.warning("Selective mode: only trade A+ setups with strong operator confirmation.")
        st.caption("Breadth uses current scan counts plus SPY/VIX regime for US. It is a risk overlay, not a signal replacement.")

