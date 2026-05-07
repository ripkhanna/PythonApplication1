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
        entry_s = df_long.get("Entry Quality", pd.Series([""] * len(df_long))).astype(str)
        action_s = df_long.get("Action", pd.Series([""] * len(df_long))).astype(str)
        actionable_l = df_long[(entry_s.str.contains("✅", na=False)) | (action_s == "STRONG BUY")]
        watch_hql = df_long[(action_s == "WATCH – HIGH QUALITY") & (~df_long.index.isin(actionable_l.index))]
        watch_dvl = df_long[df_long["Action"] == "WATCH – DEVELOPING"]
        watch_early = df_long[df_long["Action"] == "WATCH – EARLY"]

        st.caption(
            f"✅ **{len(actionable_l)}** Actionable Buy · "
            f"👀 **{len(watch_hql)}** High Quality · "
            f"📋 **{len(watch_dvl)}** Developing · "
            f"🌱 **{len(watch_early)}** Early · "
            f"🗂️ **{df_long['Sector'].nunique()}** Sectors · "
            f"Top: **{df_long['Rise Prob'].iloc[0]}**"
        )

        st.caption("✅ Actionable Buy / Best Setups")
        show_table(actionable_l, "actionable buy", "Rise Prob")
        st.caption("👀 High Quality Watch")
        show_table(watch_hql, "high quality", "Rise Prob")
        st.caption("📋 Developing")
        show_table(watch_dvl, "developing", "Rise Prob")
        with st.expander(f"🌱 Early watchlist ({len(watch_early)})", expanded=False):
            show_table(watch_early, "early long", "Rise Prob")

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
        entry_s = df_short.get("Entry Quality", pd.Series([""] * len(df_short))).astype(str)
        action_s = df_short.get("Action", pd.Series([""] * len(df_short))).astype(str)
        actionable_s = df_short[(entry_s.str.contains("✅", na=False)) | (action_s == "STRONG SHORT")]
        watch_hqs = df_short[(action_s == "WATCH SHORT – HIGH QUALITY") & (~df_short.index.isin(actionable_s.index))]
        watch_dvs = df_short[df_short["Action"] == "WATCH SHORT – DEVELOPING"]
        watch_early = df_short[df_short["Action"] == "WATCH SHORT – EARLY"]

        st.caption(
            f"✅ **{len(actionable_s)}** Actionable Sell · "
            f"👀 **{len(watch_hqs)}** High Quality · "
            f"📋 **{len(watch_dvs)}** Developing · "
            f"🌱 **{len(watch_early)}** Early · "
            f"🗂️ **{df_short['Sector'].nunique()}** Sectors · "
            f"Top: **{df_short['Fall Prob'].iloc[0]}**"
        )

        st.caption("✅ Actionable Sell / Best Shorts")
        show_table(actionable_s, "actionable short", "Fall Prob")
        st.caption("👀 High Quality Watch")
        show_table(watch_hqs, "hq short", "Fall Prob")
        st.caption("📋 Developing")
        show_table(watch_dvs, "developing short", "Fall Prob")
        with st.expander(f"🌱 Early short watchlist ({len(watch_early)})", expanded=False):
            show_table(watch_early, "early short", "Fall Prob")

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
            _entry_l = df_long.get("Entry Quality", pd.Series([""] * len(df_long))).astype(str) if not df_long.empty else pd.Series(dtype=str)
            top_l = df_long[((df_long["Action"] == "STRONG BUY") | _entry_l.str.contains("✅", na=False))][
                [c for c in ["Ticker","Sector","Setup Type","Entry Quality","Rise Prob","Score","Price","MA60 Stop","TP1 +10%","TP3 +20%"] if c in df_long.columns]
            ] if not df_long.empty else pd.DataFrame()
            show_table(top_l, "long", "Rise Prob")
        with col_r:
            st.caption("📉 Top Shorts")
            _entry_s = df_short.get("Entry Quality", pd.Series([""] * len(df_short))).astype(str) if not df_short.empty else pd.Series(dtype=str)
            top_s = df_short[((df_short["Action"] == "STRONG SHORT") | _entry_s.str.contains("✅", na=False))][
                [c for c in ["Ticker","Sector","Setup Type","Entry Quality","Fall Prob","Score","Price","Cover Stop","Target 1:2"] if c in df_short.columns]
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

