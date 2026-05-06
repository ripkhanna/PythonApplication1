"""Earnings Tab renderer.

Readable Streamlit tab code extracted from the original working monolith.
Each render function receives the main runtime globals as ``ctx`` and exposes
them to this module so the body behaves like it did in the single-file app.
"""

def _bind_runtime(ctx: dict) -> None:
    """Expose original app globals to this module for monolith-compatible tab code."""
    globals().update(ctx)

def render_earnings(ctx: dict) -> None:
    _bind_runtime(ctx)
    st.caption("📅 Upcoming Earnings · Verdict: price vs MAs + analyst target + EPS trend")

    # ── Controls ──────────────────────────────────────────────────────────────
    ec1, ec2, ec3 = st.columns([1, 1, 2])
    with ec1:
        earn_days = st.slider("Days ahead", 5, 30, 15, key="earn_days")
    with ec2:
        earn_market = st.radio("Market", ["🇺🇸 US", "🇸🇬 SGX", "🇮🇳 India"],
                               horizontal=True, key="earn_market_sel")
    with ec3:
        # Custom tickers — always include these even if not in base list
        extra_earn = st.text_input("➕ Add tickers",
            placeholder="UUUU, NVDA, AAPL", key="earn_extra").strip().upper()

    if earn_market == "🇺🇸 US":
        earn_base = list(US_TICKERS)
    elif earn_market == "🇸🇬 SGX":
        earn_base = list(SG_TICKERS)
    else:
        earn_base = list(INDIA_TICKERS)

    # Inject extra tickers at the front so they're scanned first
    if extra_earn:
        for t in [x.strip() for x in extra_earn.split(",") if x.strip()]:
            if t not in earn_base:
                earn_base.insert(0, t)

    # ── Search + filter — always visible ─────────────────────────────────────
    sf1, sf2 = st.columns([2, 2])
    with sf1:
        earn_search = st.text_input("🔍 Search ticker",
            placeholder="e.g. UUUU, NVDA", key="earn_search").strip().upper()
    with sf2:
        verdict_filter = st.multiselect(
            "Filter verdict",
            ["✅ BUY", "👀 WATCH", "⏳ WAIT", "🚫 AVOID"],
            default=[], key="earn_verdict_filter", placeholder="All verdicts"
        )

    # ── Fetch button ──────────────────────────────────────────────────────────
    if st.button("📅 Fetch Earnings Calendar", type="primary", key="btn_earnings"):
        # Scoped clear — see ETF holdings note. Only invalidate the
        # earnings-calendar function's own cache; leave other cached data
        # (sector heatmaps, dividends, prices) intact. This also avoids
        # the side-effect of resetting unkeyed sidebar widgets.
        try:
            fetch_earnings_calendar.clear()
        except Exception:
            pass
        earn_df = fetch_earnings_calendar(tuple(earn_base), earn_days)
        st.session_state["earn_df"] = earn_df

    earn_df = st.session_state.get("earn_df", pd.DataFrame())

    if earn_df.empty:
        st.info("Click 📅 Fetch Earnings Calendar. Add UUUU in the ➕ Add tickers box to include it.")
    else:
        buys   = (earn_df["_vcol"] == "buy").sum()
        watch  = (earn_df["_vcol"] == "watch").sum()
        waits  = (earn_df["_vcol"] == "wait").sum()
        avoids = (earn_df["_vcol"] == "avoid").sum()
        st.caption(f"✅ **{buys}** Buy · 👀 **{watch}** Watch · ⏳ **{waits}** Wait · 🚫 **{avoids}** Avoid · {len(earn_df)} stocks found")

        # ── Apply search + filter ─────────────────────────────────────────────
        df_filtered = earn_df.copy()
        if earn_search:
            df_filtered = df_filtered[
                df_filtered["Ticker"].str.contains(earn_search, case=False, na=False)
            ]
        if verdict_filter:
            df_filtered = df_filtered[
                df_filtered["_vcol"].isin([
                    v.split()[0].strip("✅👀⏳🚫").strip().lower()
                    .replace("buy","buy").replace("watch","watch")
                    .replace("wait","wait").replace("avoid","avoid")
                    for v in verdict_filter
                ]) | df_filtered["Verdict"].isin(verdict_filter)
            ]

        if df_filtered.empty:
            st.info("No results — try clearing the search or filter.")
        else:
            def style_verdict(val):
                s = str(val)
                if "BUY"   in s: return "background-color:#d4edda;color:#155724;font-weight:600"
                if "WATCH" in s: return "background-color:#d1ecf1;color:#0c5460;font-weight:500"
                if "WAIT"  in s: return "background-color:#fff3cd;color:#856404"
                if "AVOID" in s: return "background-color:#f8d7da;color:#721c24;font-weight:600"
                return ""

            def style_eps(val):
                if "📈" in str(val): return "color:#155724;font-weight:600"
                if "📉" in str(val): return "color:#721c24;font-weight:600"
                return ""

            disp_cols = [c for c in [
                "Ticker","Earnings Date","Days Out","Price",
                "EPS Est","EPS Last","EPS Trend","Fwd PE",
                "Analyst Target","Upside","Above MA50","Above MA200",
                "Analyst Rec","Verdict",
            ] if c in df_filtered.columns]

            df_show = df_filtered[disp_cols].copy()
            if "Days Out" in df_show.columns:
                df_show["Days Out"] = pd.to_numeric(df_show["Days Out"], errors="coerce")

            col_cfg = {
                "Ticker":         st.column_config.TextColumn("Ticker",  width=60),
                "Earnings Date":  st.column_config.TextColumn("Date",    width=80),
                "Days Out":       st.column_config.NumberColumn("Days",  width=45),
                "Price":          st.column_config.TextColumn("Price",   width=62),
                "EPS Est":        st.column_config.TextColumn("EPS Est", width=58),
                "EPS Last":       st.column_config.TextColumn("EPS Last",width=58),
                "EPS Trend":      st.column_config.TextColumn("Trend",   width=72),
                "Fwd PE":         st.column_config.TextColumn("Fwd PE",  width=52),
                "Analyst Target": st.column_config.TextColumn("Target",  width=62),
                "Upside":         st.column_config.TextColumn("Upside",  width=55),
                "Above MA50":     st.column_config.TextColumn("MA50",    width=42),
                "Above MA200":    st.column_config.TextColumn("MA200",   width=45),
                "Analyst Rec":    st.column_config.TextColumn("Rec",     width=68),
                "Verdict":        st.column_config.TextColumn("Verdict", width=100),
            }
            cfg = {k: v for k, v in col_cfg.items() if k in df_show.columns}

            styler = df_show.style
            sfn    = styler.map if hasattr(styler, "map") else styler.applymap
            styled = sfn(style_verdict, subset=["Verdict"])
            styled = (styled.map if hasattr(styled,"map") else styled.applymap)(
                      style_eps, subset=["EPS Trend"])

            st.dataframe(styled, width="stretch", hide_index=True,
                         column_config=cfg,
                         height=min(40 + len(df_show) * 35, 520))

        st.caption(
            "**✅ BUY** = ≥4/5: above MA50, above MA200, analyst target higher, EPS↑>5%, Buy rated · "
            "**👀 WATCH** = 3/5 · **⏳ WAIT** = 2/5 · **🚫 AVOID** = ≤1/5 or near 52W low"
        )
        st.warning(
            "⚠️ Earnings are binary — stocks can gap ±20% overnight. "
            "Never hold full position through earnings. "
            "Best strategy: buy the dip AFTER earnings on good results."
        )

