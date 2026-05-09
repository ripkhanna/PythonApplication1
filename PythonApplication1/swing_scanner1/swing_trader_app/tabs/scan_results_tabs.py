"""Scan Results Tabs renderer — v2 (strategy-aware).

Supports 6 swing strategy modes set in the sidebar:
  Strict / Balanced / Discovery  — existing behaviour, unchanged
  Support Entry                  — only stocks AT support levels
  Premarket Momentum             — only stocks with PM strength + intact trend
  High Volume                    — unusual volume / volume breakout / pocket pivot
"""


def _bind_runtime(ctx: dict) -> None:
    globals().update(ctx)


def _mode_banner(m: str) -> None:
    if m == "SUPPORT ENTRY":
        st.info(
            "📍 **Support Entry mode** — only stocks AT a known support level are shown. "
            "Stocks already up >3% today are filtered out (extended, bad R/R). "
            "**Tier 1 🔵 MA60 dip** = strongest. **Tier 2 🟢 MA20 dip**. "
            "**Tier 3 🟡 Swing low**. **Tier 4 ⚪ VWAP dip**.  \n"
            "Stop sits just below support → tight risk, unchanged upside target."
        )
    elif m == "PREMARKET MOMENTUM":
        st.info(
            "🚀 **Premarket Momentum mode** — stocks with +1–8% pre-market gain + intact trend.  \n"
            "**Tier A 🚀 +3–8%** = high conviction open-gap. "
            "**Tier B 📈 +1–3%** = building momentum.  \n"
            "Run 15–30 min before market open for best results. "
            "Stocks with broken technicals are removed even if PM gain is large."
        )
    elif m == "HIGH VOLUME":
        st.info(
            "📊 **High Volume mode** — stocks with unusual volume / volume breakout / pocket pivot.  \n"
            "Tier A = extreme volume, Tier B = breakout volume, Tier C = pocket pivot, Tier D = unusual volume watchlist."
        )




# ─────────────────────────────────────────────────────────────────────────────
# High Conviction display-only ranking helpers
# These helpers do NOT change scanner/strategy logic. They only rank the already
# returned High Conviction dataframe so the user can focus on the best few names.
# ─────────────────────────────────────────────────────────────────────────────
def _hc_num(series, default=0.0):
    try:
        return pd.to_numeric(
            series.astype(str)
                  .str.replace("%", "", regex=False)
                  .str.replace("+", "", regex=False)
                  .str.replace("x", "", regex=False)
                  .str.replace("–", "", regex=False)
                  .str.strip(),
            errors="coerce",
        ).fillna(default)
    except Exception:
        return pd.Series([default] * len(series), index=getattr(series, "index", None))


def _hc_score_num(series, default=0.0):
    try:
        # Handles "7", "7/10", "Score 7", etc.
        out = pd.to_numeric(series.astype(str).str.extract(r"(\d+(?:\.\d+)?)")[0], errors="coerce")
        return out.fillna(default)
    except Exception:
        return pd.Series([default] * len(series), index=getattr(series, "index", None))


def _build_top_swing_buys(df, top_n=10):
    """Return a display-only ranked Top Swing Buys dataframe for High Conviction."""
    if df is None or df.empty:
        return pd.DataFrame()

    ranked = df.copy()
    idx = ranked.index

    rise = _hc_num(ranked.get("Rise Prob", pd.Series([0] * len(ranked), index=idx)), 0).clip(0, 100)
    raw_score = _hc_score_num(ranked.get("Score", pd.Series([0] * len(ranked), index=idx)), 0)
    # If Score is on 0-10 scale, normalize to 0-100; if already 0-100, keep it.
    score_norm = raw_score.where(raw_score > 10, raw_score * 10).clip(0, 100)
    vol_ratio = _hc_num(ranked.get("Vol Ratio", pd.Series([0] * len(ranked), index=idx)), 0)
    vol_score = (vol_ratio.clip(0, 3.0) / 3.0 * 100).fillna(0)
    today = _hc_num(ranked.get("Today %", pd.Series([0] * len(ranked), index=idx)), 0)

    # Prefer stocks that have moved, but are not too extended. This is display-only.
    today_score = pd.Series([60.0] * len(ranked), index=idx)
    today_score = today_score.mask((today >= 0) & (today <= 6), 95)
    today_score = today_score.mask((today > 6) & (today <= 10), 70)
    today_score = today_score.mask(today > 10, 35)
    today_score = today_score.mask(today < -3, 40)

    entry_text = (
        ranked.get("Entry Quality", pd.Series([""] * len(ranked), index=idx)).astype(str) + " " +
        ranked.get("Setup Type", pd.Series([""] * len(ranked), index=idx)).astype(str) + " " +
        ranked.get("Support Tier", pd.Series([""] * len(ranked), index=idx)).astype(str) + " " +
        ranked.get("Action", pd.Series([""] * len(ranked), index=idx)).astype(str)
    )
    entry_score = pd.Series([60.0] * len(ranked), index=idx)
    entry_score = entry_score.mask(entry_text.str.contains("✅|SUPPORT|MA20|MA60|VWAP|PRECISION|STRONG BUY", na=False, regex=True), 90)
    entry_score = entry_score.mask(entry_text.str.contains("WAIT|EXTENDED|TRAP|AVOID", na=False, regex=True), 35)

    opt_text = ranked.get("Opt Flow", pd.Series(["–"] * len(ranked), index=idx)).astype(str)
    opt_score = pd.Series([50.0] * len(ranked), index=idx).mask(opt_text.ne("–") & opt_text.ne(""), 100)

    final = (
        rise * 0.35 +
        score_norm * 0.20 +
        vol_score * 0.15 +
        entry_score * 0.15 +
        today_score * 0.10 +
        opt_score * 0.05
    ).round(1)

    ranked.insert(0, "Final Swing Score", final)
    ranked.insert(1, "Rank", final.rank(method="first", ascending=False).astype(int))

    decision = pd.Series(["WATCH – GOOD SETUP"] * len(ranked), index=idx)
    decision = decision.mask(final >= 85, "TOP BUY – SWING")
    decision = decision.mask((final >= 78) & (final < 85), "BUY – HIGH PROBABILITY")
    decision = decision.mask((final >= 70) & (final < 78), "WATCH – WAIT FOR ENTRY")
    decision = decision.mask(final < 70, "WATCH ONLY")
    ranked.insert(2, "Decision", decision)

    why = []
    for i in ranked.index:
        reasons = []
        try:
            if rise.loc[i] >= 70: reasons.append("high rise probability")
            if score_norm.loc[i] >= 70: reasons.append("strong signal score")
            if vol_ratio.loc[i] >= 2: reasons.append("volume expansion")
            elif vol_ratio.loc[i] >= 1.3: reasons.append("rising volume")
            if entry_score.loc[i] >= 85: reasons.append("good entry/support")
            if 0 <= today.loc[i] <= 6: reasons.append("not over-extended")
            if opt_score.loc[i] >= 100: reasons.append("options confirmed")
        except Exception:
            pass
        why.append(", ".join(reasons[:4]) if reasons else "best ranked High Conviction candidate")
    ranked.insert(3, "Why Selected", why)

    ranked = ranked.sort_values("Final Swing Score", ascending=False, kind="stable")
    try:
        n = int(top_n)
    except Exception:
        n = 10
    return ranked.head(max(1, n)).copy()

def render_long(ctx: dict) -> None:
    _bind_runtime(ctx)

    swing_mode = str(st.session_state.get("ui_swing_mode",
                     st.session_state.get("swing_mode", "Balanced")))
    m = swing_mode.upper()

    if not df_long.empty:
        _n_opt_l = (int((df_long["Opt Flow"] != "–").sum())
                    if "Opt Flow" in df_long.columns else 0)
        st.caption(
            f"Results for **{last_market}** · {len(df_long)} setups · "
            f"🧩 **{_n_opt_l}** options-confirmed · mode: **{swing_mode}**"
        )

    if m == "SUPPORT ENTRY":
        st.info(
            "📐 **Support Entry** — Stop: just below support · "
            "Targets: TP1 +10% · TP2 +15% · TP3 +20%"
        )
    elif m == "PREMARKET MOMENTUM":
        st.info(
            "📐 **Premarket Momentum** — Stop: MA60 · "
            "Targets: TP1 +10% · TP2 +15% · TP3 +20%"
        )
    elif m == "HIGH VOLUME":
        st.info(
            "📐 **High Volume** — Focus: unusual activity + price confirmation · "
            "Use Trade Desk for exact entry/stop before buying."
        )
    else:
        st.info(
            "📐 **Strategy** — Stop: MA60 · Targets: TP1 +10% · TP2 +15% · TP3 +20% | "
            "**✅ BUY** = high-prob + operator + VWAP + no trap · "
            "**⏳ WAIT** = extended · **👀 WATCH** = forming · **🚫 AVOID** = MA60 broken"
        )

    _mode_banner(m)

    _notice = st.session_state.get("_strategy_changed_notice")
    if _notice:
        st.info(_notice)
    _last_strategy = str(st.session_state.get("last_scan_strategy", swing_mode))
    if _last_strategy != swing_mode:
        st.warning(
            f"Displayed grid is from **{_last_strategy}** scan. Current selected strategy is **{swing_mode}**. "
            "Click Scan to refresh, or wait for auto-refresh after changing strategy."
        )

    if df_long.empty:
        st.info("Run the scan to see long setups.")
        return

    action_s = df_long.get("Action", pd.Series([""] * len(df_long))).astype(str)
    label_s = (
        action_s + " " +
        df_long.get("Setup Type", pd.Series([""] * len(df_long))).astype(str) + " " +
        df_long.get("Signals", pd.Series([""] * len(df_long))).astype(str)
    )

    if m == "SUPPORT ENTRY":
        tier1 = df_long[label_s.str.contains(r"MA60 (?:DIP|SUPPORT)|STRONG BUY.*SUPPORT", na=False, regex=True)]
        tier2 = df_long[label_s.str.contains(r"MA20 (?:DIP|SUPPORT)", na=False, regex=True)]
        tier3 = df_long[label_s.str.contains(r"SWING LOW (?:BOUNCE|SUPPORT)", na=False, regex=True)]
        tier4 = df_long[label_s.str.contains(r"(?:VWAP|MA200|NEAR) (?:DIP|SUPPORT)|SUPPORT CANDIDATE", na=False, regex=True)]

        st.caption(
            f"🔵 **{len(tier1)}** MA60 dip · 🟢 **{len(tier2)}** MA20 dip · "
            f"🟡 **{len(tier3)}** swing low · ⚪ **{len(tier4)}** VWAP/MA200/Near · "
            f"🗂️ **{df_long['Sector'].nunique()}** sectors"
        )

        if not tier1.empty:
            st.markdown("#### 🔵 Tier 1 — MA60 Dip (strongest)")
            st.caption("Price sitting on the 60-day MA with declining volume. Best R/R in the entire watchlist.")
            show_table(tier1, "tier1_support", "Rise Prob")
        if not tier2.empty:
            st.markdown("#### 🟢 Tier 2 — MA20 Dip")
            st.caption("Pulling back to 20-day MA. Common swing entry, trend still intact above MA60.")
            show_table(tier2, "tier2_support", "Rise Prob")
        if not tier3.empty:
            with st.expander(f"🟡 Tier 3 — Swing Low Bounce ({len(tier3)})", expanded=True):
                st.caption("Price near a recent swing low. Higher risk than MA dips but strong R/R if structure holds.")
                show_table(tier3, "tier3_support", "Rise Prob")
        if not tier4.empty:
            with st.expander(f"⚪ Tier 4 — VWAP / MA200 / Near Support ({len(tier4)})", expanded=False):
                st.caption("Holding near VWAP, MA200, or the nearest support area. Lower tier than MA20/MA60, but useful when structure holds.")
                show_table(tier4, "tier4_support", "Rise Prob")
        if tier1.empty and tier2.empty and tier3.empty and tier4.empty:
            st.caption("Showing all Support Entry candidates.")
            show_table(df_long, "support_all_candidates", "Rise Prob")

    elif m == "PREMARKET MOMENTUM":
        pm_a = df_long[label_s.str.contains(r"PM MOMENTUM|LIVE MOMENTUM|STRONG BUY.*PM", na=False, regex=True)]
        pm_b = df_long[label_s.str.contains(r"PM BUILDING|LIVE MOMENTUM", na=False, regex=True)]
        pm_c = df_long[label_s.str.contains(r"MOMENTUM CANDIDATE", na=False, regex=True)]

        pm_col = "PM Chg%" if "PM Chg%" in df_long.columns else None
        top_pm_str = ""
        if pm_col and not df_long.empty:
            vals = df_long[pm_col].replace("–", None).dropna()
            top_pm_str = f" · Top PM move: **{vals.iloc[0]}**" if len(vals) else ""

        st.caption(
            f"🚀 **{len(pm_a)}** Tier A/live · 📈 **{len(pm_b)}** Tier B/live · 🟡 **{len(pm_c)}** Tech candidates · "
            f"🗂️ **{df_long['Sector'].nunique()}** sectors{top_pm_str}"
        )

        if not pm_a.empty:
            st.markdown("#### 🚀 Tier A — High Conviction (+3–8% pre-market)")
            st.caption(
                "Strong pre-market gap backed by sound technicals. "
                "These have the highest probability of following through at the open. "
                "Still confirm with Level 2 / tape before entering."
            )
            show_table(pm_a, "pm_tier_a", "Rise Prob")
        if not pm_b.empty:
            with st.expander(f"📈 Tier B — Building Momentum / Live Momentum ({len(pm_b)})", expanded=True):
                st.caption(
                    "Moderate pre-market/live gain with intact trend. "
                    "Wait for the first 5-min candle to confirm direction before entry."
                )
                show_table(pm_b, "pm_tier_b", "Rise Prob")
        if not pm_c.empty:
            with st.expander(f"🟡 Tier C — Technical momentum candidates, no PM feed ({len(pm_c)})", expanded=True):
                st.caption(
                    "Yahoo did not provide pre-market/live percentage, so these are filtered by trend, volume, and momentum signals instead of PM price."
                )
                show_table(pm_c, "pm_tier_c", "Rise Prob")
        if pm_a.empty and pm_b.empty and pm_c.empty:
            st.caption("Showing all Premarket Momentum candidates.")
            show_table(df_long, "pm_all_candidates", "Rise Prob")

    elif m == "HIGH VOLUME":
        hv_a = df_long[label_s.str.contains(r"EXTREME VOLUME", na=False, regex=True)]
        hv_b = df_long[label_s.str.contains(r"VOLUME BREAKOUT", na=False, regex=True)]
        hv_c = df_long[label_s.str.contains(r"POCKET PIVOT", na=False, regex=True)]
        hv_d = df_long[label_s.str.contains(r"UNUSUAL VOLUME|VOLUME WATCH|VOLUME CANDIDATE|ACTIVE VOLUME|ACCUMULATION", na=False, regex=True)]

        st.caption(
            f"🔥 **{len(hv_a)}** Extreme · 🚀 **{len(hv_b)}** Breakout · "
            f"📌 **{len(hv_c)}** Pocket pivot · 👀 **{len(hv_d)}** Unusual · "
            f"🗂️ **{df_long['Sector'].nunique()}** sectors"
        )

        if not hv_a.empty:
            st.markdown("#### 🔥 Tier A — Extreme Volume")
            st.caption("Volume ratio >= 3x with positive price action and trend support.")
            show_table(hv_a, "hv_extreme", "Vol Ratio")
        if not hv_b.empty:
            st.markdown("#### 🚀 Tier B — Volume Breakout")
            st.caption("Breakout near recent highs with strong relative volume.")
            show_table(hv_b, "hv_breakout", "Vol Ratio")
        if not hv_c.empty:
            with st.expander(f"📌 Tier C — Pocket Pivot ({len(hv_c)})", expanded=True):
                st.caption("Green volume expansion above MA20. Useful for early accumulation setups.")
                show_table(hv_c, "hv_pocket", "Vol Ratio")
        if not hv_d.empty:
            with st.expander(f"👀 Tier D — Unusual Volume Watchlist ({len(hv_d)})", expanded=True):
                st.caption("Activity is increasing, but setup is earlier or less confirmed.")
                show_table(hv_d, "hv_unusual", "Vol Ratio" if "Vol Ratio" in hv_d.columns else "Rise Prob")
        if hv_a.empty and hv_b.empty and hv_c.empty and hv_d.empty:
            show_table(df_long, "hv_all_candidates", "Vol Ratio" if "Vol Ratio" in df_long.columns else "Rise Prob")

    elif m == "HIGH CONVICTION":
        hc_strong = df_long[action_s.str.contains(
            "STRONG BUY – HIGH CONVICTION|BUY – PRECISION SETUP", na=False, regex=True)]
        hc_watch  = df_long[action_s.str.contains("WATCH – CONFLUENCE", na=False, regex=True)]

        st.caption(
            f"🎯 **{len(hc_strong)}** Full confluence (5/5 categories) · "
            f"👀 **{len(hc_watch)}** Near-confluence (4/5) · "
            f"🗂️ **{df_long['Sector'].nunique()}** sectors"
        )
        st.info(
            "🎯 **High Conviction** — each result confirmed ALL 5 independent signal categories: "
            "📈 Trend · ⚡ Momentum · 🔊 Volume · 🏗️ Structure · 🌍 Market alignment.  \n"
            "Check the **Signals** column for the **HC[T+M+V+S+X](5/5)** tag."
        )
        _top_n = int(st.session_state.get("ui_hc_top_n", 10) or 10)
        top_buys = _build_top_swing_buys(df_long, _top_n)
        if not top_buys.empty:
            st.markdown(f"#### 🏆 Top {_top_n} Swing Buys — ranked from High Conviction results")
            st.caption(
                "This is a display-only decision layer. It does **not** change High Conviction scanner logic or any other strategy. "
                "Ranking favours rise probability, signal score, volume confirmation, entry/support quality, not being over-extended, and options confirmation."
            )
            show_table(top_buys, "hc_top_swing_buys", "Final Swing Score")

        if not hc_strong.empty:
            st.markdown("#### 🎯 Full Confluence — All 5 Categories")
            st.caption(
                "Trend + Momentum + Volume + Structure + Market all confirmed simultaneously. "
                "Highest win-rate setups in the scanner."
            )
            show_table(hc_strong, "hc_strong", "Rise Prob")
        if not hc_watch.empty:
            with st.expander(f"👀 Near-Confluence — 4 of 5 Categories ({len(hc_watch)})", expanded=True):
                st.caption("One category missing — watch for it to complete before entering full size.")
                show_table(hc_watch, "hc_watch", "Rise Prob")
        if hc_strong.empty and hc_watch.empty:
            st.info(
                "No High Conviction setups found in the current scan.  \n\n"
                "This is expected — this mode is strict by design. "
                "Try **Discovery** first to see which sectors are strongest, "
                "then switch to **High Conviction** for the filtered shortlist."
            )

    else:
        # Standard modes — unchanged behaviour
        entry_s = df_long.get("Entry Quality", pd.Series([""] * len(df_long))).astype(str)
        actionable_l = df_long[(entry_s.str.contains("✅", na=False)) | (action_s.str.contains("STRONG BUY", na=False))]
        watch_hql    = df_long[(action_s == "WATCH – HIGH QUALITY") & (~df_long.index.isin(actionable_l.index))]
        watch_dvl    = df_long[df_long["Action"] == "WATCH – DEVELOPING"]
        watch_early  = df_long[df_long["Action"] == "WATCH – EARLY"]

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

    swing_mode = str(st.session_state.get("ui_swing_mode",
                     st.session_state.get("swing_mode", "Balanced")))

    st.warning("⚠️ Short selling has unlimited loss potential. Always use a hard cover-stop.")

    if not df_short.empty:
        _n_opt_s = (int((df_short["Opt Flow"] != "–").sum())
                    if "Opt Flow" in df_short.columns else 0)
        st.caption(
            f"Results for **{last_market}** · {len(df_short)} setups · "
            f"🧩 **{_n_opt_s}** options-confirmed · mode: **{swing_mode}**"
        )

    st.info(
        "📐 **Strategy** — Stop: Cover Stop · Targets: T1 −10% · T2 −20% | "
        "**✅ SELL** = confirmed downtrend + below VWAP + distribution · "
        "**⏳ WAIT** = gapped down too far · **👀 WATCH** = forming · **🚫 AVOID** = above MA60"
    )

    if df_short.empty:
        st.info("Run the scan to see short setups.")
        return

    entry_s  = df_short.get("Entry Quality", pd.Series([""] * len(df_short))).astype(str)
    action_s = df_short.get("Action",        pd.Series([""] * len(df_short))).astype(str)
    actionable_s = df_short[(entry_s.str.contains("✅", na=False)) | (action_s == "STRONG SHORT")]
    watch_hqs    = df_short[(action_s == "WATCH SHORT – HIGH QUALITY") & (~df_short.index.isin(actionable_s.index))]
    watch_dvs    = df_short[df_short["Action"] == "WATCH SHORT – DEVELOPING"]
    watch_early  = df_short[df_short["Action"] == "WATCH SHORT – EARLY"]

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

**Cover Stop** — place as a hard stop-limit immediately on entry.

`STOCH ROLLOVER` overbought K>80, now crossing down · `BB BEAR SQ` squeeze below midline
`MACD DECEL` histogram declining · `DIST DAY` large red on 2× volume
`VOL BREAKDOWN` 10-day low on high volume · `LOWER HIGHS` two consecutive lower swing highs
        """)


def render_both(ctx: dict) -> None:
    _bind_runtime(ctx)

    if df_long.empty and df_short.empty:
        st.info("Run the scan to see results.")
        return

    col_l, col_r = st.columns(2)
    with col_l:
        st.caption("📈 Top Longs")
        if not df_long.empty:
            _entry_l  = df_long.get("Entry Quality", pd.Series([""] * len(df_long))).astype(str)
            _action_l = df_long.get("Action",        pd.Series([""] * len(df_long))).astype(str)
            top_l = df_long[(
                _action_l.str.contains("STRONG BUY|BUY –", na=False, regex=True) |
                _entry_l.str.contains("✅", na=False)
            )][[c for c in ["Ticker","Sector","Setup Type","Entry Quality",
                             "Rise Prob","Score","Price","MA60 Stop",
                             "TP1 +10%","TP3 +20%","Support Tier","PM Chg%"]
                if c in df_long.columns]]
            show_table(top_l, "long", "Rise Prob")
    with col_r:
        st.caption("📉 Top Shorts")
        if not df_short.empty:
            _entry_s  = df_short.get("Entry Quality", pd.Series([""] * len(df_short))).astype(str)
            _action_s = df_short.get("Action",        pd.Series([""] * len(df_short))).astype(str)
            top_s = df_short[(
                (_action_s == "STRONG SHORT") | _entry_s.str.contains("✅", na=False)
            )][[c for c in ["Ticker","Sector","Setup Type","Entry Quality",
                             "Fall Prob","Score","Price","Cover Stop","Target 1:2"]
                if c in df_short.columns]]
            show_table(top_s, "short", "Fall Prob")

    if not df_long.empty and not df_short.empty:
        both = set(df_long["Ticker"]) & set(df_short["Ticker"])
        if both:
            st.warning(f"⚠️ Mixed signals — avoid: {', '.join(sorted(both))}")

    if not df_long.empty:
        _action_l = df_long.get("Action", pd.Series(dtype=str)).astype(str)
        top_buys  = df_long[_action_l.str.contains("STRONG BUY|BUY –", na=False, regex=True)]
        if len(top_buys) >= 2:
            sector_counts: dict = {}
            for _, row in top_buys.iterrows():
                sec = str(row.get("Sector","")).replace("🟢","").replace("🔴","").replace("⚪","").strip()
                sector_counts[sec] = sector_counts.get(sec, 0) + 1
            concentrated = {s: n for s, n in sector_counts.items() if n >= 3}
            if concentrated:
                st.error(
                    "⚠️ **Concentration risk** — "
                    + ", ".join(f"**{n} buys in {s}**" for s, n in concentrated.items())
                    + ". Limit to max 2–3 positions per sector."
                )
