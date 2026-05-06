"""Scan Results Tabs renderer.

Readable Streamlit tab code extracted from the original working monolith.
Each render function receives the main runtime globals as ``ctx`` and exposes
them to this module so the body behaves like it did in the single-file app.
"""

def _bind_runtime(ctx: dict) -> None:
    """Expose original app globals to this module for monolith-compatible tab code."""
    globals().update(ctx)

def render_long(ctx: dict) -> None:
    _bind_runtime(ctx)
    if not df_long.empty:
        # v12: count how many of the displayed setups have option-flow tags
        _n_opt_l = int((df_long["Opt Flow"] != "–").sum()) \
                   if "Opt Flow" in df_long.columns else 0
        st.caption(
            f"Results for **{last_market}** · {len(df_long)} setups · "
            f"🧩 **{_n_opt_l}** options-confirmed"
        )
    st.info(
        "📐 **Strategy** — Stop: MA60 · Targets: TP1 +10% · TP2 +15% · TP3 +20% | "
        "**✅ BUY** = high-prob setup + operator accumulation + VWAP support + no trap risk · "
        "**⏳ WAIT** = price too extended · "
        "**👀 WATCH** = setup ok, no ideal dip yet · "
        "**🚫 AVOID** = MA60 broken. New columns: Operator, Op Score, VWAP, Trap Risk."
    )
    if df_long.empty:
        st.info("Run the scan to see long setups.")
    else:
        strong_l  = df_long[df_long["Action"] == "STRONG BUY"]
        watch_hql = df_long[df_long["Action"] == "WATCH – HIGH QUALITY"]
        watch_dvl = df_long[df_long["Action"] == "WATCH – DEVELOPING"]

        st.caption(
            f"🔥 **{len(strong_l)}** Strong Buy · "
            f"👀 **{len(watch_hql)}** High Quality · "
            f"📋 **{len(watch_dvl)}** Developing · "
            f"🗂️ **{df_long['Sector'].nunique()}** Sectors · "
            f"Top: **{df_long['Rise Prob'].iloc[0]}**"
        )

        # sec_cnt = df_long.groupby("Sector").size().reset_index(name="Setups")
        # st.dataframe(sec_cnt, width="stretch", hide_index=True)

        st.caption("🔥 Strong Buy")
        show_table(strong_l, "strong buy", "Rise Prob")
        st.caption("👀 High Quality")
        show_table(watch_hql, "high quality", "Rise Prob")
        st.caption("📋 Developing")
        show_table(watch_dvl, "developing", "Rise Prob")

def render_short(ctx: dict) -> None:
    _bind_runtime(ctx)
    st.warning("⚠️ Short selling has unlimited loss potential. Always use a hard cover-stop.")
    if not df_short.empty:
        # v12: count how many of the displayed setups have option-flow tags
        _n_opt_s = int((df_short["Opt Flow"] != "–").sum()) \
                   if "Opt Flow" in df_short.columns else 0
        st.caption(
            f"Results for **{last_market}** · {len(df_short)} setups · "
            f"🧩 **{_n_opt_s}** options-confirmed"
        )
    st.info(
        "📐 **Strategy** — Stop: Cover Stop · Targets: T1 −10% · T2 −20% | "
        "**✅ SELL** = confirmed downtrend + below VWAP + distribution/volume confirmation · "
        "**⏳ WAIT** = gapped down too far, wait for bounce · "
        "**👀 WATCH** = setup forming · "
        "**🚫 AVOID** = above MA60, trend not confirmed. New columns: Operator, Op Score, VWAP, Trap Risk."
    )
    if df_short.empty:
        st.info("Run the scan to see short setups.")
    else:
        strong_s  = df_short[df_short["Action"] == "STRONG SHORT"]
        watch_hqs = df_short[df_short["Action"] == "WATCH SHORT – HIGH QUALITY"]
        watch_dvs = df_short[df_short["Action"] == "WATCH SHORT – DEVELOPING"]

        st.caption(
            f"🔥 **{len(strong_s)}** Strong Short · "
            f"👀 **{len(watch_hqs)}** High Quality · "
            f"📋 **{len(watch_dvs)}** Developing · "
            f"🗂️ **{df_short['Sector'].nunique()}** Sectors · "
            f"Top: **{df_short['Fall Prob'].iloc[0]}**"
        )

        # sec_cnt = df_short.groupby("Sector").size().reset_index(name="Setups")
        # st.dataframe(sec_cnt, width="stretch", hide_index=True)

        st.caption("🔥 Strong Short")
        show_table(strong_s, "strong short", "Fall Prob")
        st.caption("👀 High Quality")
        show_table(watch_hqs, "hq short", "Fall Prob")
        st.caption("📋 Developing")
        show_table(watch_dvs, "developing short", "Fall Prob")

        with st.expander("📖 How to read the short table"):
            st.markdown("""
    **Fall Prob** — probability the price falls within 5–7 sessions.

    **Cover Stop** — price at which you buy back to exit if wrong. Place as a hard stop-limit immediately.

    **Signal tags:**
    `STOCH ROLLOVER` — overbought K>80 × 2 bars, now crossing down  
    `BB BEAR SQ` — BB squeeze with price below midline  
    `MACD DECEL` — histogram declining 3 consecutive bars  
    `DIST DAY` — large red candle on 2× average volume  
    `VOL BREAKDOWN` — 10-day low on above-average volume  
    `LOWER HIGHS` — two consecutive lower swing highs
            """)

def render_both(ctx: dict) -> None:
    _bind_runtime(ctx)
    if df_long.empty and df_short.empty:
        st.info("Run the scan to see results.")
    else:
        col_l, col_r = st.columns(2)
        with col_l:
            st.caption("📈 Top Longs")
            top_l = df_long[df_long["Action"] == "STRONG BUY"][
                ["Ticker","Sector","Entry Quality","Rise Prob","Score","Price","MA60 Stop","TP1 +10%","TP3 +20%"]
            ] if not df_long.empty else pd.DataFrame()
            show_table(top_l, "long", "Rise Prob")
        with col_r:
            st.caption("📉 Top Shorts")
            top_s = df_short[df_short["Action"] == "STRONG SHORT"][
                ["Ticker","Sector","Fall Prob","Score","Price","Cover Stop","Target 1:2"]
            ] if not df_short.empty else pd.DataFrame()
            show_table(top_s, "short", "Fall Prob")

        if not df_long.empty and not df_short.empty:
            both = set(df_long["Ticker"]) & set(df_short["Ticker"])
            if both:
                st.warning(f"⚠️ Mixed signals — avoid: {', '.join(sorted(both))}")

        # ── Portfolio correlation warning ─────────────────────────────────────
        if not df_long.empty:
            strong_buys = df_long[df_long["Action"] == "STRONG BUY"]["Ticker"].tolist()
            if len(strong_buys) >= 2:
                # Group by sector to detect concentration
                sector_counts: dict = {}
                for _, row in df_long[df_long["Action"] == "STRONG BUY"].iterrows():
                    sec = str(row.get("Sector","")).replace("🟢","").replace("🔴","").replace("⚪","").strip()
                    sector_counts[sec] = sector_counts.get(sec, 0) + 1
                concentrated = {s: n for s, n in sector_counts.items() if n >= 3}
                if concentrated:
                    st.error(
                        f"⚠️ **Concentration risk** — {len(strong_buys)} STRONG BUY setups found but "
                        + ", ".join(f"**{n} are in {s}**" for s, n in concentrated.items())
                        + ". Stocks in the same sector are 0.80+ correlated. "
                        "A single sector sell-off wipes all positions simultaneously. "
                        "Limit exposure to max 2–3 stocks per sector."
                    )

