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
    ec1, ec2, ec3, ec4 = st.columns([1, 1, 1, 2])
    with ec1:
        earn_days = st.slider("Days ahead", 5, 30, 15, key="earn_days")
    with ec2:
        earn_market = st.radio("Market", ["🇺🇸 US", "🇸🇬 SGX", "🇮🇳 India", "🇭🇰 HK"],
                               horizontal=True, key="earn_market_sel")
    with ec3:
        earn_max = st.selectbox("Max scan", [50, 100, 150, 250, 500, 1000],
                                index=1, key="earn_max_scan",
                                help="Keeps Earnings Calendar fast. Extra tickers are always scanned first.")
    with ec4:
        extra_earn = st.text_input("➕ Add tickers",
            placeholder="UUUU, NVDA, AAPL", key="earn_extra").strip().upper()

    # ── Market-aware state: clear earn_df when user switches market ───────────
    _prev_earn_market = st.session_state.get("earn_df_market", "")
    if _prev_earn_market and _prev_earn_market != earn_market:
        st.session_state.pop("earn_df", None)
        st.session_state.pop("earn_last_checked_sgt", None)
        st.session_state.pop("earn_last_scan_count", None)

    if earn_market == "🇺🇸 US":
        earn_base = list(US_TICKERS)
    elif earn_market == "🇸🇬 SGX":
        earn_base = list(SG_TICKERS)
    elif earn_market == "🇭🇰 HK":
        earn_base = list(HK_TICKERS)
    else:
        earn_base = list(INDIA_TICKERS)

    # Prioritize latest scan results first, then curated market list.
    # This makes the tab useful and faster after a scan because it checks the
    # stocks you are actually looking at before the rest of the universe.
    try:
        scan_priority = []
        for _df_name in ("df_long", "df_short", "df_swing_picks"):
            _df = st.session_state.get(_df_name, pd.DataFrame())
            if isinstance(_df, pd.DataFrame) and not _df.empty and "Ticker" in _df.columns:
                scan_priority.extend([str(x).strip().upper() for x in _df["Ticker"].head(150).tolist()])
        for _t in reversed([x for x in scan_priority if x]):
            if _t in earn_base:
                earn_base.remove(_t)
            earn_base.insert(0, _t)
    except Exception:
        pass

    # Inject extra tickers at the very front so they're scanned first.
    if extra_earn:
        for t in reversed([x.strip().upper() for x in extra_earn.split(",") if x.strip()]):
            if t in earn_base:
                earn_base.remove(t)
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
        # Clear all earnings-specific caches.  Clearing only the outer
        # fetch_earnings_calendar cache can still leave stale empty
        # per-ticker results from _fast_earnings_date_for_ticker.
        for _fn_name in (
            "fetch_earnings_calendar",
            "_fast_earnings_date_for_ticker",
            "_earnings_info_for_candidate",
            "_nasdaq_earnings_for_date_cached_near",    # v15.6: was missing — caused stale empty dates
            "_nasdaq_earnings_for_date_cached_stable",  # v15.6: also clear stable cache on manual refresh
        ):
            try:
                _fn = globals().get(_fn_name)
                if _fn is not None and hasattr(_fn, "clear"):
                    _fn.clear()
            except Exception:
                pass
        with st.spinner(f"Scanning earnings for up to {earn_max} tickers…"):
            earn_df = fetch_earnings_calendar(tuple(earn_base), earn_days, int(earn_max))
        st.session_state["earn_df"] = earn_df
        st.session_state["earn_df_market"] = earn_market           # ← market tag
        st.session_state["earn_last_scan_count"] = min(len(earn_base), int(earn_max))
        st.session_state["earn_last_checked_sgt"] = pd.Timestamp.now(tz="Asia/Singapore").strftime("%Y-%m-%d %H:%M:%S SGT")

    st.caption(
        f"Fast mode: checks earnings dates first, then loads full Yahoo info only for matching candidates. "
        f"Current cap: {earn_max} tickers. "
        f"**Note:** Nasdaq calendar uses US Eastern dates. "
        f"Today ET: **{pd.Timestamp.now(tz='America/New_York').strftime('%Y-%m-%d %H:%M ET')}** — "
        "if your local date is ahead of ET (SGT users), Monday earnings appear only after ~midnight ET Sunday."
    )

    earn_df = st.session_state.get("earn_df", pd.DataFrame())

    # Show stale-market warning if df is from a different market
    _df_market = st.session_state.get("earn_df_market", "")
    if not earn_df.empty and _df_market and _df_market != earn_market:
        st.warning(f"⚠️ Showing **{_df_market}** results — click 📅 Fetch to load **{earn_market}** earnings.")

    if earn_df.empty:
        _last_checked = st.session_state.get("earn_last_checked_sgt")
        _last_count   = st.session_state.get("earn_last_scan_count")
        _is_sgx_hk    = earn_market in ("🇸🇬 SGX", "🇭🇰 HK")
        if _last_checked:
            if _is_sgx_hk:
                st.warning(
                    f"No earnings rows found for **{earn_market}** (last checked: {_last_checked}). \n\n"
                    "**Why SGX/HK earnings are sparse:** Yahoo Finance does not maintain an earnings "
                    "calendar for most SGX/HK tickers. The scan relies on per-ticker Yahoo data which "
                    "is rarely populated for these markets.\n\n"
                    "**Workarounds:**\n"
                    "- Use **➕ Add tickers** to force-check specific stocks you know are reporting\n"
                    "- Check [SGX announcements](https://www.sgx.com/securities/company-announcements) directly\n"
                    "- Increase **Days ahead** to 30 and **Max scan** to 500"
                )
            else:
                st.warning(
                    f"No earnings rows found in the selected window. Last checked: {_last_checked}. "
                    f"Tickers scanned: {_last_count or 0}. Try Days ahead = 30, Max scan = 500/1000, "
                    "or add known tickers manually in ➕ Add tickers."
                )
        else:
            if _is_sgx_hk:
                st.info(
                    f"Click 📅 Fetch Earnings Calendar to scan **{earn_market}** earnings.\n\n"
                    "**Tip for SGX/HK:** Add specific tickers in ➕ Add tickers (e.g. `D05.SI, O39.SI`) "
                    "since Yahoo's earnings calendar coverage for these markets is limited."
                )
            else:
                st.info("Click 📅 Fetch Earnings Calendar. Add tickers in the ➕ Add tickers box to force-check them. Default scan is capped for speed; raise Max scan only when needed.")
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
                df_filtered["Ticker"].astype(str).str.contains(earn_search, case=False, na=False)
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
                "Analyst Rec","Data","Verdict",
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
                "Data":           st.column_config.TextColumn("Data",    width=48,
                    help="Data quality: criteria available out of 5. SGX/HK/India often 2-3/5 due to sparse Yahoo coverage."),
                "Verdict":        st.column_config.TextColumn("Verdict", width=120),
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
            "**✅ BUY** — majority of available criteria pass (MA50, MA200, analyst target, EPS trend, analyst rec) · "
            "**👀 WATCH** — roughly half pass · **⏳ WAIT** — minority pass · **🚫 AVOID** — fails or near 52W low · "
            "**Data** = criteria with real data out of 5. SGX/HK/India typically 2–3/5 (Yahoo coverage sparse). "
            "⚠️partial = verdict based on incomplete data — treat with caution."
        )
        st.warning(
            "⚠️ Earnings are binary — stocks can gap ±20% overnight. "
            "Never hold full position through earnings. "
            "Best strategy: buy the dip AFTER earnings on good results."
        )

