"""Operator Activity Tab renderer.

Readable Streamlit tab code extracted from the original working monolith.
Each render function receives the main runtime globals as ``ctx`` and exposes
them to this module so the body behaves like it did in the single-file app.
"""

def _bind_runtime(ctx: dict) -> None:
    """Expose original app globals to this module for monolith-compatible tab code."""
    globals().update(ctx)

def render_operator_activity(ctx: dict) -> None:
    _bind_runtime(ctx)
    st.caption("🪤 Operator Activity — every stock from the latest scanned market universe with manipulation footprints")
    st.warning(
        "⚠️ Operator activity is a **directional bias signal**, not a trade trigger. "
        "Use it alongside the Long/Short scorecards. Pattern-based detection produces "
        "false positives in volatile but legitimate trends — confirm with the chart "
        "before entering."
    )

    if df_operator.empty:
        st.info(
            "Run the scan first. With **Use live market universe** ON, this tab fetches "
            "stocks from the selected market source instead of only using the hard-coded "
            "watchlist. Every stock with operator activity (op-score ≥ 2 or any trap "
            "pattern) will appear here."
        )
    else:
        df_op = df_operator.copy()

        # ── Headline metrics ─────────────────────────────────────────────────
        n_total   = len(df_op)
        n_high    = int((df_op["_high_count"] > 0).sum())
        n_bull    = int((df_op["_bias_score"] >  0).sum())
        n_bear    = int((df_op["_bias_score"] <  0).sum())

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("🪤 Total active",   n_total)
        m2.metric("🚨 High severity",  n_high)
        m3.metric("🟢 Bullish ops",    n_bull)
        m4.metric("🔴 Bearish ops",    n_bear)

        st.caption(
            f"Results for **{last_market}** · {n_total} of "
            f"{last_universe_count} scanned stocks show operator activity. "
            f"Universe: **{last_universe_source}**."
        )

        # ── Filters ──────────────────────────────────────────────────────────
        f1, f2, f3 = st.columns([2, 2, 1])
        with f1:
            bias_filter = st.selectbox(
                "Direction bias",
                ["All", "🟢 Bullish only", "🔴 Bearish only", "⚪ Neutral only"],
                key="op_bias_filter",
            )
        with f2:
            sev_filter = st.selectbox(
                "Severity",
                ["All", "High severity only", "Med+ severity",
                 "Op Score ≥ 4 (accumulation+)", "Op Score ≥ 6 (strong)"],
                key="op_sev_filter",
            )
        with f3:
            search = st.text_input("🔎 Ticker", key="op_search",
                                   placeholder="search…").strip().upper()

        df_view = df_op.copy()
        if bias_filter == "🟢 Bullish only":
            df_view = df_view[df_view["_bias_score"] > 0]
        elif bias_filter == "🔴 Bearish only":
            df_view = df_view[df_view["_bias_score"] < 0]
        elif bias_filter == "⚪ Neutral only":
            df_view = df_view[df_view["_bias_score"] == 0]

        if   sev_filter == "High severity only":
            df_view = df_view[df_view["_high_count"] >= 1]
        elif sev_filter == "Med+ severity":
            df_view = df_view[df_view["_trap_count"] >= 1]
        elif sev_filter == "Op Score ≥ 4 (accumulation+)":
            df_view = df_view[df_view["_op_score"] >= 4]
        elif sev_filter == "Op Score ≥ 6 (strong)":
            df_view = df_view[df_view["_op_score"] >= 6]

        if search:
            df_view = df_view[df_view["Ticker"].astype(str).str.contains(search, na=False)]

        # ── Tier split: bullish vs bearish operator activity ─────────────────
        df_bull = df_view[df_view["_bias_score"] >  0].sort_values(
            ["_bias_score", "_op_score"], ascending=[False, False])
        df_bear = df_view[df_view["_bias_score"] <  0].sort_values(
            ["_bias_score", "_op_score"], ascending=[True, False])
        df_neut = df_view[df_view["_bias_score"] == 0].sort_values(
            "_op_score", ascending=False)

        display_cols = [c for c in df_view.columns if not c.startswith("_")]

        st.markdown(f"**Filtered: {len(df_view)} stocks**")

        if not df_bull.empty:
            st.markdown(f"### 🟢 Bullish operator activity ({len(df_bull)})")
            st.caption(
                "Accumulation, bear traps, downside stop hunts, sell-climax — operators "
                "appear to be loading up. Consider these as long candidates."
            )
            st.dataframe(df_bull[display_cols], width="stretch", hide_index=True)

        if not df_bear.empty:
            st.markdown(f"### 🔴 Bearish operator activity ({len(df_bear)})")
            st.caption(
                "Distribution, bull traps, upside stop hunts, buy-climax — operators "
                "appear to be unloading. Consider these as short candidates."
            )
            st.dataframe(df_bear[display_cols], width="stretch", hide_index=True)

        if not df_neut.empty:
            st.markdown(f"### ⚪ Neutral / churn ({len(df_neut)})")
            st.caption(
                "Operator footprint without a clear directional bias — usually churn "
                "or stop hunts in both directions. Wait for a directional break."
            )
            st.dataframe(df_neut[display_cols], width="stretch", hide_index=True)

        if df_view.empty:
            st.info("No stocks match the current filters.")

        # ── Column reference ─────────────────────────────────────────────────
        with st.expander("📋 Column reference"):
            st.markdown("""
    - **Op Score** — the existing in-engine accumulation score (0–10ish). ≥4 = accumulation, ≥6 = strong operator buying.
    - **Op Label** — text tier of the op-score (`🔥 STRONG OPERATOR`, `🟢 ACCUMULATION`, `🟡 WEAK SIGNS`, `⚪ NONE`).
    - **Trap Bias** — net direction of detected trap patterns. 🟢 BULLISH = accumulation/bear traps dominate; 🔴 BEARISH = distribution/bull traps dominate.
    - **Patterns** — count of active trap patterns, broken down by severity (`H` high · `M` medium · `L` low).
    - **Detected** — comma-separated labels of the actual patterns (BULL TRAP, DISTRIBUTION, etc.).
    - **Trap Risk** — single-flag fast-fail label from the engine: `FALSE BO` (failed breakout), `GAP CHASE`, `DISTRIB`.
    - **VWAP** — close above or below today's VWAP (a quick proxy for institutional control).
    - **Vol Ratio** — today's volume vs 20-day average. Anything ≥ 1.5 is meaningful; ≥ 2.5 is climactic.

    ### How to use
    Open the **🔬 Stock Analysis** tab and search any ticker shown here for the full pattern explanations, the chart, and the trade plan. The bias here is a *screening* signal — it tells you where to look, not what to do.
            """)

