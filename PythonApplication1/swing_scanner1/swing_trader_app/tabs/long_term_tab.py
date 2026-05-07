"""Long Term Tab renderer — v4 (search criteria above grid).

Layout change in v4:
  ┌──────────────────────────────────────────────────────────────┐
  │ SCAN CONFIG (before button — sets WHAT gets fetched)         │
  │   Min quality score  |  Max scan count                       │
  │   [🔍 Find Long-Term Stocks]                                 │
  ├──────────────────────────────────────────────────────────────┤
  │ FILTER BAR (above grid — filters ALREADY-fetched results)    │
  │   🔍 Search ticker/name  |  Horizon  |  Sector               │
  │   📍 Near support  |  Min support score  |  Min upside        │
  ├──────────────────────────────────────────────────────────────┤
  │  RESULTS GRID                                                │
  └──────────────────────────────────────────────────────────────┘
"""


def _bind_runtime(ctx: dict) -> None:
    globals().update(ctx)


def render_long_term(ctx: dict) -> None:
    _bind_runtime(ctx)
    st.caption("🌱 Long-Term Portfolio Builder · Quality + Near-Support scoring")

    lt_sub_us, lt_sub_sg, lt_sub_sg_funds, lt_sub_us_funds = st.tabs([
        "🇺🇸 US Stocks",
        "🇸🇬 SG Stocks",
        "🇸🇬 SG Funds & ETFs",
        "🇺🇸 US Funds & ETFs",
    ])

    # ── Style helpers ──────────────────────────────────────────────────────────
    def style_horizon(v):
        s = str(v)
        if "CORE"  in s: return "background-color:#d4edda;color:#155724;font-weight:700"
        if "BUY"   in s: return "background-color:#d1ecf1;color:#0c5460;font-weight:600"
        if "ACCUM" in s: return "background-color:#fff3cd;color:#856404"
        return "color:#888"

    def style_exp1y(v):
        try:
            n = float(str(v).strip("+%"))
            if n >= 20: return "background-color:#1a7a3a;color:#fff;font-weight:700"
            if n >= 12: return "background-color:#27ae60;color:#fff;font-weight:600"
            if n >= 6:  return "background-color:#a9dfbf;color:#145a32"
        except Exception: pass
        return ""

    def style_growth(v):
        try:
            n = float(str(v).strip("+%"))
            if n >= 20: return "color:#155724;font-weight:700"
            if n >= 10: return "color:#1a5276;font-weight:600"
        except Exception: pass
        return ""

    def style_support(v):
        s = str(v)
        if "🟢" in s: return "background-color:#d4edda;color:#155724;font-weight:700"
        if "🟡" in s: return "background-color:#fff3cd;color:#856404;font-weight:600"
        if "🔴" in s: return "background-color:#f8d7da;color:#721c24"
        return "color:#888"

    def style_rsi(v):
        try:
            n = float(str(v))
            if n <= 35: return "background-color:#d4edda;color:#155724;font-weight:700"
            if n <= 50: return "background-color:#a9dfbf;color:#145a32"
            if n >= 70: return "background-color:#f8d7da;color:#721c24"
        except Exception: pass
        return ""

    def style_vs_ma(v):
        try:
            n = float(str(v).strip("+%"))
            if -8  <= n <= 18: return "background-color:#d4edda;color:#155724;font-weight:600"
            if  18 < n <= 30:  return "color:#555"
            if n > 30:         return "background-color:#fff3cd;color:#856404"
            if n < -8:         return "background-color:#f8d7da;color:#721c24"
        except Exception: pass
        return ""

    def _apply_styles(df_show):
        sfn = (df_show.style.map if hasattr(df_show.style, "map")
               else df_show.style.applymap)
        styled = sfn(style_horizon,
                     subset=[c for c in ["Horizon"] if c in df_show.columns])
        for fn, cols in [
            (style_exp1y,   ["Exp 1Y Return"]),
            (style_support, ["Support"]),
            (style_rsi,     ["RSI14"]),
            (style_vs_ma,   ["vsMA50%", "vsMA200%"]),
            (style_growth,  ["Rev Growth", "EPS Growth", "Upside"]),
        ]:
            targets = [c for c in cols if c in df_show.columns]
            if targets:
                styled = (styled.map if hasattr(styled, "map")
                          else styled.applymap)(fn, subset=targets)
        return styled

    # ── Column catalogue ──────────────────────────────────────────────────────
    QUALITY_COLS = [
        "Ticker","Name","Sector","Horizon","Exp 1Y Return","Price","Mkt Cap",
        "Return Breakdown","Rev Growth","EPS Growth","ROE","Margin",
        "Fwd PE","PEG","Div Yield","Beta","MA200","Target","Upside","Rec","Score",
    ]
    SUPPORT_COLS = [
        "Support","SuppScore","RSI14","vsMA50%","vsMA200%",
        "From52WHi%","VolRatio","FCFYield",
    ]
    SOURCE_COLS = ["Sources","ETF Count","In ETFs"]

    COL_CFG = {
        "Ticker":           st.column_config.TextColumn("Ticker",    width=65),
        "Name":             st.column_config.TextColumn("Name",      width=130),
        "Sector":           st.column_config.TextColumn("Sector",    width=95),
        "Sources":          st.column_config.TextColumn("Sources",   width=105),
        "ETF Count":        st.column_config.NumberColumn("ETFs",    width=42),
        "In ETFs":          st.column_config.TextColumn("In ETFs",   width=120),
        "Price":            st.column_config.TextColumn("Price",     width=62),
        "Mkt Cap":          st.column_config.TextColumn("Cap",       width=60),
        "Exp 1Y Return":    st.column_config.TextColumn("Exp 1Y",   width=75),
        "Return Breakdown": st.column_config.TextColumn("Div+Price", width=130),
        "Rev Growth":       st.column_config.TextColumn("RevGrw",   width=58),
        "EPS Growth":       st.column_config.TextColumn("EPSGrw",   width=58),
        "ROE":              st.column_config.TextColumn("ROE",       width=48),
        "Margin":           st.column_config.TextColumn("Margin",    width=52),
        "Fwd PE":           st.column_config.TextColumn("FwdPE",    width=52),
        "PEG":              st.column_config.TextColumn("PEG",       width=45),
        "Div Yield":        st.column_config.TextColumn("Yield",     width=48),
        "Beta":             st.column_config.TextColumn("Beta",      width=42),
        "MA200":            st.column_config.TextColumn("MA200",     width=42),
        "Target":           st.column_config.TextColumn("Target",    width=60),
        "Upside":           st.column_config.TextColumn("Upside",   width=52),
        "Rec":              st.column_config.TextColumn("Rec",       width=68),
        "Score":            st.column_config.TextColumn("Score",     width=48),
        "Horizon":          st.column_config.TextColumn("Horizon",   width=145),
        "Support":          st.column_config.TextColumn("Support",   width=140),
        "SuppScore":        st.column_config.TextColumn("Supp/5",   width=62),
        "RSI14":            st.column_config.TextColumn("RSI14",     width=50),
        "vsMA50%":          st.column_config.TextColumn("vs MA50",  width=65),
        "vsMA200%":         st.column_config.TextColumn("vs MA200", width=68),
        "From52WHi%":       st.column_config.TextColumn("vs 52W Hi",width=70),
        "VolRatio":         st.column_config.TextColumn("Vol20/60", width=65),
        "FCFYield":         st.column_config.TextColumn("FCF Yld",  width=65),
    }

    # ── Filter bar — renders above the grid when results are present ──────────
    def _render_filter_bar(session_key, df_all):
        """
        Compact filter bar shown between the scan button and the results grid.
        All widgets here operate on ALREADY-FETCHED results — no re-scan needed.
        Returns the filtered DataFrame.
        """
        st.markdown("**🔎 Filter results**")

        # Row 1: text search | horizon | sector
        r1c1, r1c2, r1c3 = st.columns([2, 2, 2])
        with r1c1:
            search = st.text_input(
                "🔍 Ticker or name",
                placeholder="e.g. NVDA, DBS, tech, REIT",
                key=f"{session_key}_search",
                label_visibility="collapsed",
            ).strip()
        with r1c2:
            horizon_f = st.multiselect(
                "Horizon",
                ["⭐ CORE HOLD (3–5yr)", "✅ BUY & HOLD (1–3yr)",
                 "👀 ACCUMULATE on dips", "⏳ MONITOR only"],
                default=[],
                key=f"{session_key}_horizon_f",
                placeholder="All horizons",
                label_visibility="collapsed",
            )
        with r1c3:
            # Build sector list from actual results
            sectors = sorted(
                {str(r.get("Sector","–")).strip()
                 for r in st.session_state.get(session_key, [])
                 if r.get("Sector") and r.get("Sector") != "–"}
            )
            sector_f = st.multiselect(
                "Sector",
                sectors,
                default=[],
                key=f"{session_key}_sector_f",
                placeholder="All sectors",
                label_visibility="collapsed",
            )

        # Row 2: near-support | min support score | min upside
        r2c1, r2c2, r2c3 = st.columns([1, 2, 2])
        with r2c1:
            near_supp = st.checkbox(
                "📍 Near support only",
                key=f"{session_key}_near_supp",
                help=(
                    "Keeps only stocks with Support Score ≥ 3/5.\n\n"
                    "Criteria (+1 each):\n"
                    "  • Price −20%…+8% of MA50\n"
                    "  • Price −8%…+18% of MA200\n"
                    "  • RSI-14 between 25–58\n"
                    "  • 8–45% below 52W high\n"
                    "  • 8–65% above 52W low\n\n"
                    "4–5 = 🟢 At support  |  2–3 = 🟡 Near"
                ),
            )
        with r2c2:
            min_supp = st.slider(
                "Min support score",
                0, 5, 0,
                key=f"{session_key}_min_supp",
                help="0 = show all.  3 = same as checkbox above.  "
                     "5 = strongest at-support picks only.",
            )
        with r2c3:
            min_upside = st.slider(
                "Min analyst upside %",
                0, 50, 0, step=5,
                key=f"{session_key}_min_upside",
                help="Only show stocks where analyst target price is ≥ this "
                     "% above current price. 0 = no filter.",
            )

        st.markdown("---")  # visual separator before grid

        # ── Apply all filters ────────────────────────────────────────────
        df = df_all.copy()

        if search:
            mask = (
                df["Ticker"].str.contains(search.upper(), na=False)
                | df["Name"].str.contains(search, case=False, na=False)
                | df["Sector"].str.contains(search, case=False, na=False)
            )
            df = df[mask]

        if horizon_f:
            df = df[df["Horizon"].isin(horizon_f)]

        if sector_f:
            df = df[df["Sector"].isin(sector_f)]

        has_supp = "_supp_score" in df.columns
        effective_min = max(3, min_supp) if near_supp else min_supp
        if effective_min > 0 and has_supp:
            df = df[df["_supp_score"] >= effective_min]

        if min_upside > 0 and "Upside" in df.columns:
            def _upside_val(v):
                try:
                    return float(str(v).strip("+%"))
                except Exception:
                    return 0.0
            df = df[df["Upside"].apply(_upside_val) >= min_upside]

        return df, near_supp

    # ── Grid renderer ──────────────────────────────────────────────────────────
    def _render_grid(df_lt, session_key,
                     near_support_only=False,
                     extra_source_cols=True):
        if df_lt.empty:
            st.info(
                "No stocks match the current filters. "
                "Try clearing the search box, widening the horizon or sector "
                "filter, or lowering the support/upside thresholds."
            )
            return

        has_supp = "_supp_score" in df_lt.columns

        sort_cols = (
            ["_supp_score","_score","_exp1y"]
            if near_support_only
            else ["_score","_supp_score","_exp1y"]
        )
        sort_cols = [c for c in sort_cols if c in df_lt.columns]
        if sort_cols:
            df_lt = df_lt.sort_values(sort_cols, ascending=False)

        # Summary
        total    = len(df_lt)
        at_supp  = int((df_lt["_supp_score"] >= 4).sum()) if has_supp else 0
        near_sup = int((df_lt["_supp_score"] >= 2).sum()) if has_supp else 0
        core = int((df_lt["_hcol"] == "buy").sum())
        buyh = int((df_lt["_hcol"] == "watch").sum())
        acc  = int((df_lt["_hcol"] == "wait").sum())
        st.caption(
            f"⭐ **{core}** Core Hold · ✅ **{buyh}** Buy & Hold · "
            f"👀 **{acc}** Accumulate · "
            f"🟢 **{at_supp}** at support · "
            f"🟡 **{near_sup - at_supp}** near support · "
            f"**{total}** shown"
        )

        disp_q   = [c for c in QUALITY_COLS  if c in df_lt.columns]
        disp_s   = [c for c in SUPPORT_COLS  if c in df_lt.columns]
        disp_src = ([c for c in SOURCE_COLS if c in df_lt.columns]
                    if extra_source_cols else [])
        disp = (disp_s + disp_q + disp_src) if near_support_only else (disp_q + disp_s + disp_src)

        df_show = df_lt[disp].copy()
        cfg = {k: v for k, v in COL_CFG.items() if k in df_show.columns}
        st.dataframe(
            _apply_styles(df_show),
            width="stretch", hide_index=True,
            column_config=cfg,
            height=min(40 + len(df_show) * 35, 640),
        )

        st.caption(
            "**Quality/10:** RevGrw(+2) EPSGrw(+2) ROE>15%(+1) Margin>15%(+1) "
            "LowDebt(+1) AboveMA200(+1) Target(+1) BuyRated(+1)  ·  "
            "**Support/5:** MA50zone(+1) MA200zone(+1) RSI25-58(+1) "
            "Pullback8-45%(+1) Floor8-65%(+1)  ·  ETF Count = institutional conviction"
        )

    # ── Shared scan launcher (scan config only — no filters here) ─────────────
    def run_lt_scan(etf_dict, session_key, default_etfs,
                    min_score_key,
                    existing_tickers=None, live_market_name=None,
                    include_etf_tickers=True):

        # ── SCAN CONFIG ─────────────────────────────────────────────────
        with st.expander("⚙️ Scan settings", expanded=True):
            sc1, sc2 = st.columns([1, 1])
            with sc1:
                min_sc = st.slider("Min quality score (0-10)", 1, 10, 4,
                                   key=min_score_key)
            with sc2:
                max_lt_scan = st.slider("Max stocks to scan", 50, 1000, 300,
                                        step=25, key=f"{session_key}_max_scan")

        if st.button("🔍 Find Long-Term Stocks",
                     type="primary", key=f"btn_{session_key}"):
            etfs = list(default_etfs)
            existing_tickers = list(existing_tickers or [])
            etf_holdings = {}
            source_map   = {}

            def _add_symbol(sym, source_label, etf_label=None):
                sym = _clean_symbol(sym)
                if not sym:
                    return
                source_map.setdefault(sym, [])
                if source_label not in source_map[sym]:
                    source_map[sym].append(source_label)
                if etf_label:
                    etf_holdings.setdefault(sym, [])
                    if etf_label not in etf_holdings[sym]:
                        etf_holdings[sym].append(etf_label)

            for t in existing_tickers:
                _add_symbol(t, "Existing")
            if include_etf_tickers:
                for etf in etf_dict.keys():
                    _add_symbol(etf, "ETF")

            p1 = st.progress(0, text="Loading ETF holdings…")
            for i, etf in enumerate(etfs):
                for t in fetch_lt_holdings(etf):
                    _add_symbol(t, "ETF holding", etf)
                p1.progress((i + 1) / max(1, len(etfs)))
            p1.empty()

            live_tickers = []
            live_source  = "Yahoo/live disabled"
            if use_live_universe and live_market_name:
                with st.spinner("Fetching Yahoo/live universe…"):
                    live_tickers, live_source = fetch_live_market_universe(
                        live_market_name, max_symbols=max_live_universe)
                for t in live_tickers:
                    _add_symbol(t, "Yahoo/live")

            combined = []
            combined.extend([_clean_symbol(t) for t in existing_tickers])
            if include_etf_tickers:
                combined.extend([_clean_symbol(t) for t in etf_dict.keys()])
            combined.extend(
                sorted(etf_holdings.keys(),
                       key=lambda t: len(etf_holdings.get(t, [])),
                       reverse=True)
            )
            combined.extend(list(live_tickers))
            unique    = [t for t in _unique_keep_order(combined) if t in source_map]
            scan_list = unique[:max_lt_scan]

            results = []
            p2 = st.progress(0); st2 = st.empty()
            for i, ticker in enumerate(scan_list):
                st2.caption(f"Scoring {ticker} ({i+1}/{len(scan_list)})…")
                row = score_lt_stock(ticker)
                if row and row.get("_score", 0) >= min_sc:
                    row["In ETFs"]   = ", ".join(etf_holdings.get(ticker, [])[:4]) or "–"
                    row["ETF Count"] = len(etf_holdings.get(ticker, []))
                    row["Sources"]   = ", ".join(source_map.get(ticker, []))
                    results.append(row)
                p2.progress((i + 1) / max(1, len(scan_list)))
            p2.empty(); st2.empty()

            results.sort(key=lambda x: (-x.get("ETF Count",0), -x.get("_score",0)))
            st.session_state[session_key] = results
            st.session_state[f"{session_key}_universe_csv"] = ", ".join(scan_list)
            st.caption(
                f"✅ Scanned: existing **{len(existing_tickers)}** · "
                f"ETFs **{len(etf_dict)}** · holdings **{len(etf_holdings)}** · "
                f"live **{len(live_tickers)}** · "
                f"scored **{len(scan_list)}** / {len(unique)} candidates · "
                f"found **{len(results)}** passing quality filter"
            )

        # ── FILTER BAR + GRID (only when results exist) ──────────────────
        raw = st.session_state.get(session_key, [])
        if not raw:
            st.info(
                "Click **🔍 Find Long-Term Stocks** above.  \n"
                "After scanning, a **filter bar** appears right above the results "
                "so you can instantly search, filter by sector/horizon, or "
                "show only near-support picks — without re-scanning."
            )
            return

        df_all = pd.DataFrame(raw)
        df_filtered, near_supp = _render_filter_bar(session_key, df_all)
        _render_grid(df_filtered, session_key,
                     near_support_only=near_supp,
                     extra_source_cols=True)

        csv_tickers = st.session_state.get(f"{session_key}_universe_csv", "")
        if csv_tickers:
            with st.expander("📋 Scanned tickers", expanded=False):
                st.text_area("Comma-separated", value=csv_tickers,
                             height=90, key=f"{session_key}_universe_text")

    # ── SG cloud-offline safety net ───────────────────────────────────────────
    def _sgx_cloud_fallback_rows(sg_scan, sg_sources, sg_min_sc):
        """Return conservative SGX rows when yfinance returns no usable .SI rows.

        This prevents the cloud deployment from showing an empty grid when SGX
        Yahoo requests are blocked/rate-limited. These rows are clearly marked
        as fallback/seed rows and should be refreshed by re-running the scan
        later or locally.
        """
        seed = {
            "D05.SI":  ("DBS Group", "Financial Services", 4.8, 5, "✅ BUY & HOLD (1–3yr)"),
            "O39.SI":  ("OCBC Bank", "Financial Services", 5.2, 5, "✅ BUY & HOLD (1–3yr)"),
            "U11.SI":  ("UOB", "Financial Services", 5.0, 5, "✅ BUY & HOLD (1–3yr)"),
            "S68.SI":  ("Singapore Exchange", "Financial Services", 3.5, 4, "👀 ACCUMULATE on dips"),
            "Z74.SI":  ("Singtel", "Communication Services", 5.5, 4, "👀 ACCUMULATE on dips"),
            "U96.SI":  ("Sembcorp Industries", "Utilities", 3.8, 4, "👀 ACCUMULATE on dips"),
            "BN4.SI":  ("Keppel", "Industrials", 4.7, 4, "👀 ACCUMULATE on dips"),
            "C38U.SI": ("CapitaLand Integrated Commercial Trust", "REIT", 5.4, 4, "👀 ACCUMULATE on dips"),
            "A17U.SI": ("CapitaLand Ascendas REIT", "REIT", 5.6, 4, "👀 ACCUMULATE on dips"),
            "M44U.SI": ("Mapletree Logistics Trust", "REIT", 6.0, 3, "⏳ MONITOR only"),
            "ME8U.SI": ("Mapletree Industrial Trust", "REIT", 5.9, 4, "👀 ACCUMULATE on dips"),
            "AJBU.SI": ("Keppel DC REIT", "REIT", 4.0, 3, "⏳ MONITOR only"),
            "C6L.SI":  ("Singapore Airlines", "Industrials", 4.0, 3, "⏳ MONITOR only"),
            "BS6.SI":  ("Yangzijiang Shipbuilding", "Industrials", 4.5, 4, "👀 ACCUMULATE on dips"),
            "S58.SI":  ("SATS", "Industrials", 1.5, 2, "⏳ MONITOR only"),
            "C52.SI":  ("ComfortDelGro", "Industrials", 4.5, 3, "⏳ MONITOR only"),
            "F34.SI":  ("Wilmar", "Consumer Defensive", 5.0, 3, "⏳ MONITOR only"),
            "V03.SI":  ("Venture", "Technology", 5.0, 3, "⏳ MONITOR only"),
            "AIY.SI":  ("iFAST", "Financial Services", 1.0, 3, "⏳ MONITOR only"),
            "C31.SI":  ("CapitaLand Investment", "Real Estate", 4.0, 3, "⏳ MONITOR only"),
        }
        rows = []
        for t in sg_scan:
            t = str(t).upper().strip()
            if t not in seed:
                continue
            name, sector, dy, score, horizon = seed[t]
            if score < sg_min_sc:
                continue
            exp_1y = min(14.0, max(2.0, dy + 3.0))
            rows.append({
                "Ticker": t,
                "Name": name[:28],
                "Sector": sector,
                "Price": "–",
                "Mkt Cap": "–",
                "Exp 1Y Return": f"+{exp_1y:.1f}%",
                "Return Breakdown": f"Cloud fallback: Div ~{dy:.1f}% + conservative price 3.0%",
                "Rev Growth": "–",
                "EPS Growth": "–",
                "ROE": "–",
                "Margin": "–",
                "Fwd PE": "–",
                "PEG": "–",
                "Div Yield": f"~{dy:.1f}%",
                "Beta": "–",
                "MA200": "–",
                "Target": "–",
                "Upside": "–",
                "Rec": "–",
                "Score": f"{score}/10",
                "Horizon": horizon,
                "_score": score,
                "_hcol": "wait" if score < 5 else "watch",
                "_exp1y": exp_1y,
                "Support": "⚪ Cloud fallback",
                "SuppScore": "–",
                "RSI14": "–",
                "vsMA50%": "–",
                "vsMA200%": "–",
                "From52WHi%": "–",
                "VolRatio": "–",
                "FCFYield": "–",
                "_supp_score": 0,
                "_rsi14": 50.0,
                "_supp_flags": ["Yahoo SGX data unavailable on cloud"],
                "Sources": ", ".join(sg_sources.get(t, [])) + ", cloud fallback seed",
            })
        rows.sort(key=lambda x: -x.get("_score", 0))
        return rows

    # ── SG standalone scan ────────────────────────────────────────────────────
    def run_sg_lt_scan():
        SG_LT_TICKERS = [
            "D05.SI","O39.SI","U11.SI","S68.SI","AIY.SI",
            "558.SI","E28.SI","5AB.SI","BN2.SI","V03.SI",
            "S51.SI","BN4.SI","U96.SI","S58.SI","Z74.SI",
            "C52.SI","F34.SI","OYY.SI",
            "C38U.SI","A17U.SI","M44U.SI","AJBU.SI","J91U.SI",
            "SK6U.SI","P9D.SI","5JS.SI",
        ]

        with st.expander("⚙️ Scan settings", expanded=True):
            sc1, sc2 = st.columns([1, 1])
            with sc1:
                sg_min_sc = st.slider("Min quality score (0-10)", 1, 10, 2,
                                      key="lt_sg_min")
            with sc2:
                lt_sg_max = st.slider("Max scan", 25, 1000, 250, step=25,
                                      key="lt_sg_max_scan")

        if st.button("🔍 Score SGX Long-Term Stocks",
                     type="primary", key="btn_lt_sg"):
            # Clear per-ticker fetch log so this run's diagnostics are fresh
            st.session_state.pop("lt_ticker_log", None)
            live_sg = []
            live_sg_src = "SGX/live disabled"
            if use_live_universe:
                with st.spinner("Fetching SGX/live universe…"):
                    live_sg, live_sg_src = fetch_live_market_universe(
                        "🇸🇬 SGX", max_symbols=max_live_universe)

            sg_sources = {}

            def _add_sg(sym, src):
                if not str(sym).upper().endswith(".SI") and "." not in str(sym):
                    sym = sym + ".SI"
                sym = _clean_symbol(sym)
                if not sym:
                    return
                sg_sources.setdefault(sym, [])
                if src not in sg_sources[sym]:
                    sg_sources[sym].append(src)

            sgx_fallback = globals().get("SGX_LIQUID_FALLBACK_TICKERS", [])
            for t in SG_LT_TICKERS: _add_sg(t, "LT curated")
            for t in SG_TICKERS:    _add_sg(t, "Existing")
            for t in sgx_fallback:  _add_sg(t, "SGX fallback")
            for t in LT_ETF_SG:     _add_sg(_clean_symbol(t), "ETF")
            for t in live_sg:        _add_sg(t, "SGX/live")

            sg_scan = _unique_keep_order([
                (_clean_symbol(t) if str(t).upper().endswith(".SI")
                 else _clean_symbol(t + ".SI"))
                for t in SG_LT_TICKERS + SG_TICKERS + list(sgx_fallback)
                       + list(LT_ETF_SG.keys()) + list(live_sg)
            ])[:lt_sg_max]

            results = []
            p = st.progress(0); st_s = st.empty()
            for i, ticker in enumerate(sg_scan):
                st_s.caption(f"Scoring {ticker} ({i+1}/{len(sg_scan)})…")
                row = score_lt_stock(ticker)
                # For SGX, Yahoo often lacks fundamental fields. Accept either
                # the quality score OR a reasonable support/dividend signal so
                # the grid is not empty just because ROE/EPS/analyst data is blank.
                if row and (row.get("_score", 0) >= sg_min_sc
                            or row.get("_supp_score", 0) >= 2
                            or row.get("Div Yield", "–") != "–"):
                    row["Sources"] = ", ".join(sg_sources.get(ticker, []))
                    results.append(row)
                p.progress((i + 1) / max(1, len(sg_scan)))
            p.empty(); st_s.empty()

            if not results:
                results = _sgx_cloud_fallback_rows(sg_scan, sg_sources, sg_min_sc)
                if results:
                    st.warning(
                        "Yahoo/SGX price or fundamentals returned no usable rows on cloud, "
                        "so I loaded conservative SGX fallback rows instead of showing an empty grid. "
                        "Price/MA/RSI fields are marked as unavailable. Try re-running later for live values."
                    )

            results.sort(key=lambda x: -x.get("_score", 0))
            st.session_state["lt_sg"] = results
            st.session_state["lt_sg_universe_csv"] = ", ".join(sg_scan)
            _lt_log = st.session_state.get("lt_ticker_log", {})
            _lt_ok   = sum(1 for d in _lt_log.values() if d.get("ok"))
            _lt_fail = sum(1 for d in _lt_log.values() if not d.get("ok"))
            _lt_funds = sum(1 for d in _lt_log.values() if d.get("ok") and d.get("has_fundamentals"))
            st.caption(
                f"✅ Scanned **{len(sg_scan)}** SGX stocks · "
                f"found **{len(results)}** passing filter · "
                f"source: {live_sg_src}"
            )
            if _lt_fail:
                st.warning(
                    f"⚠️ **{_lt_fail} ticker(s) returned no price** (yfinance blocked/empty on cloud). "
                    f"**{_lt_ok}** had price · **{_lt_funds}** had full fundamentals · "
                    f"**{_lt_ok - _lt_funds}** price-only (Yahoo omitted SGX info fields). "
                    "Open **🔍 Diagnostics → 🌱 Long-Term scan diagnostics** "
                    "to see exactly which step failed for each ticker."
                )
            elif _lt_ok and not _lt_funds:
                st.warning(
                    "⚠️ Prices were fetched but Yahoo returned no SGX fundamentals "
                    "(ROE/EPS/Rec all blank). Stocks still show via SGX bonus scoring. "
                    "See 🔍 Diagnostics for per-ticker details."
                )

        # ── FILTER BAR + GRID ────────────────────────────────────────────
        raw = st.session_state.get("lt_sg", [])
        if not raw:
            st.info(
                "Click **🔍 Score SGX Long-Term Stocks** above.  \n"
                "S58.SI, DBS, OCBC and 20+ SGX names are pre-loaded.  \n"
                "After scanning, use the **filter bar above the grid** to "
                "search by ticker/name, filter by sector, and tick "
                "**📍 Near support only** to instantly surface stocks at "
                "technically attractive entry points."
            )
            return

        df_all = pd.DataFrame(raw)
        df_filtered, near_supp = _render_filter_bar("lt_sg", df_all)
        _render_grid(df_filtered, "lt_sg",
                     near_support_only=near_supp,
                     extra_source_cols=False)

        csv_tickers = st.session_state.get("lt_sg_universe_csv", "")
        if csv_tickers:
            with st.expander("📋 Scanned tickers", expanded=False):
                st.text_area("Comma-separated", value=csv_tickers,
                             height=90, key="lt_sg_universe_text")

    # ── Fund table helper ──────────────────────────────────────────────────────
    def show_fund_table(fund_rows, search_key):
        fsrch = st.text_input(
            "🔍 Search fund",
            placeholder="Vanguard, REIT, Robo, CPF…",
            key=search_key,
        ).strip()
        df_f = pd.DataFrame(fund_rows)
        if fsrch:
            df_f = df_f[df_f.apply(
                lambda r: fsrch.lower() in str(r).lower(), axis=1)]

        def sret(val):
            s = str(val)
            for p in ["17","18","19","20","21","22","15","16"]:
                if p in s:
                    return "background-color:#d4edda;color:#155724;font-weight:700"
            for p in ["10","11","12","13","14"]:
                if p in s:
                    return "background-color:#d1ecf1;color:#0c5460;font-weight:600"
            return "color:#888"

        def srisk(val):
            s = str(val)
            if s == "None":  return "background-color:#d4edda;color:#155724"
            if s == "Med":   return "background-color:#d1ecf1;color:#0c5460"
            if "Med-H" in s: return "background-color:#fff3cd;color:#856404"
            if s == "High":  return "background-color:#f8d7da;color:#721c24"
            return ""

        ret_cols = [c for c in ["Ret1Y","Ret3Y","Ret5Y"] if c in df_f.columns]
        col_cfg_f = {
            "Name":   st.column_config.TextColumn("Fund / ETF",    width=210),
            "Type":   st.column_config.TextColumn("Type",          width=100),
            "Ret1Y":  st.column_config.TextColumn("1Y Ann Return", width=90),
            "Ret3Y":  st.column_config.TextColumn("3Y Ann Return", width=90),
            "Ret5Y":  st.column_config.TextColumn("5Y Ann Return", width=90),
            "Min":    st.column_config.TextColumn("Min invest",    width=70),
            "Risk":   st.column_config.TextColumn("Risk",          width=58),
            "Access": st.column_config.TextColumn("Platform",      width=110),
            "Note":   st.column_config.TextColumn("Notes",         width=240),
        }
        sfn = (df_f.style.map if hasattr(df_f.style, "map")
               else df_f.style.applymap)
        styled = sfn(sret, subset=ret_cols) if ret_cols else df_f.style
        styled = (styled.map if hasattr(styled, "map")
                  else styled.applymap)(srisk, subset=["Risk"])
        cfg = {k: v for k, v in col_cfg_f.items() if k in df_f.columns}
        st.dataframe(styled, width="stretch", hide_index=True,
                     column_config=cfg,
                     height=min(40 + len(df_f) * 35, 560))
        st.caption("Returns are approximate annualised historical figures. "
                   "Past performance ≠ future returns.")

    # ── Sub-tabs ──────────────────────────────────────────────────────────────
    with lt_sub_us:
        st.caption("🇺🇸 US long-term · quality + near-support scoring")
        with st.expander("📊 Source ETF returns", expanded=False):
            df_etf_us = pd.DataFrame([
                {"ETF": k, "Name": v["name"], "Theme": v["theme"],
                 "1Y Ann%": v.get("ret1y",0),
                 "3Y Ann%": v.get("ret3y",0),
                 "5Y Ann%": v.get("ret5y",0)}
                for k, v in LT_ETF_US.items()
            ])
            def _sc(val):
                v = float(val)
                if v>=15: return "background-color:#1a7a3a;color:#fff;font-weight:700"
                if v>=10: return "background-color:#1a5276;color:#fff;font-weight:600"
                if v>= 5: return "background-color:#f0c040;color:#333"
                if v< 0:  return "background-color:#922b21;color:#fff"
                return ""
            sfn_us = (df_etf_us.style.map if hasattr(df_etf_us.style, "map")
                      else df_etf_us.style.applymap)
            st.dataframe(sfn_us(_sc, subset=["1Y Ann%","3Y Ann%","5Y Ann%"]),
                width="stretch", hide_index=True,
                column_config={
                    "ETF":     st.column_config.TextColumn("ETF",    width=70),
                    "Name":    st.column_config.TextColumn("Name",   width=190),
                    "Theme":   st.column_config.TextColumn("Theme",  width=120),
                    "1Y Ann%": st.column_config.NumberColumn("1Y%", format="%.1f%%", width=70),
                    "3Y Ann%": st.column_config.NumberColumn("3Y%", format="%.1f%%", width=70),
                    "5Y Ann%": st.column_config.NumberColumn("5Y%", format="%.1f%%", width=70),
                }, height=min(40+len(df_etf_us)*35, 450))

        run_lt_scan(LT_ETF_US, "lt_us",
                    ["QQQ","QUAL","MOAT","SOXX","VGT","INDA","SMIN"],
                    "lt_us_min",
                    existing_tickers=US_TICKERS,
                    live_market_name="🇺🇸 US",
                    include_etf_tickers=True)

    with lt_sub_sg:
        st.caption("🇸🇬 SGX long-term · S58.SI and SGX names pre-loaded")
        with st.expander("📊 Source ETF returns", expanded=False):
            df_etf_sg = pd.DataFrame([
                {"ETF": k, "Name": v["name"], "Theme": v["theme"],
                 "1Y Ann%": v.get("ret1y",0),
                 "3Y Ann%": v.get("ret3y",0),
                 "5Y Ann%": v.get("ret5y",0)}
                for k, v in LT_ETF_SG.items()
            ])
            def _sc2(val):
                v = float(val)
                if v>=15: return "background-color:#1a7a3a;color:#fff;font-weight:700"
                if v>=10: return "background-color:#1a5276;color:#fff;font-weight:600"
                if v>= 5: return "background-color:#f0c040;color:#333"
                if v< 0:  return "background-color:#922b21;color:#fff"
                return ""
            sfn_sg = (df_etf_sg.style.map if hasattr(df_etf_sg.style, "map")
                      else df_etf_sg.style.applymap)
            st.dataframe(sfn_sg(_sc2, subset=["1Y Ann%","3Y Ann%","5Y Ann%"]),
                width="stretch", hide_index=True,
                column_config={
                    "ETF":     st.column_config.TextColumn("ETF",    width=70),
                    "Name":    st.column_config.TextColumn("Name",   width=190),
                    "Theme":   st.column_config.TextColumn("Theme",  width=120),
                    "1Y Ann%": st.column_config.NumberColumn("1Y%", format="%.1f%%", width=70),
                    "3Y Ann%": st.column_config.NumberColumn("3Y%", format="%.1f%%", width=70),
                    "5Y Ann%": st.column_config.NumberColumn("5Y%", format="%.1f%%", width=70),
                }, height=min(40+len(df_etf_sg)*35, 420))
        run_sg_lt_scan()

    with lt_sub_sg_funds:
        st.caption("🇸🇬 SG-accessible ETFs & funds · UCITS, SGX-listed, Robo-advisors, CPF")
        SG_FUNDS = [
            {"Name":"Vanguard S&P 500 (VUAA.L)",       "Type":"UCITS ETF",    "Ret1Y":"~10%","Ret3Y":"~12%","Ret5Y":"~15%","Min":"S$1",   "Risk":"Med",  "Access":"IBKR/Moomoo","Note":"Irish-domiciled, accumulating, 0% WHT"},
            {"Name":"iShares S&P 500 (CSPX.L)",         "Type":"UCITS ETF",    "Ret1Y":"~10%","Ret3Y":"~12%","Ret5Y":"~15%","Min":"S$1",   "Risk":"Med",  "Access":"IBKR",       "Note":"Acc, no dividend drag, ER 0.07%"},
            {"Name":"Xtrackers Nasdaq-100 (XNAS.L)",    "Type":"UCITS ETF",    "Ret1Y":"~11%","Ret3Y":"~14%","Ret5Y":"~17%","Min":"S$1",   "Risk":"Med-H","Access":"IBKR",       "Note":"Best UCITS Nasdaq option, ER 0.20%"},
            {"Name":"Vanguard FTSE All-World (VWRA.L)", "Type":"UCITS ETF",    "Ret1Y":"~ 8%","Ret3Y":"~10%","Ret5Y":"~13%","Min":"S$1",   "Risk":"Med",  "Access":"IBKR",       "Note":"Global diversification in 1 ETF"},
            {"Name":"SPDR STI ETF (ES3.SI)",             "Type":"SGX ETF",      "Ret1Y":"~29%","Ret3Y":"~13%","Ret5Y":"~10%","Min":"S$500", "Risk":"Med",  "Access":"Any broker", "Note":"CPF-OA investible, tracks STI 30"},
            {"Name":"Nikko AM STI ETF (G3B.SI)",         "Type":"SGX ETF",      "Ret1Y":"~29%","Ret3Y":"~13%","Ret5Y":"~10%","Min":"S$100", "Risk":"Med",  "Access":"Any broker", "Note":"CPF-OA investible, lowest TER 0.21%"},
            {"Name":"CSOP S-REIT Leaders (SRT.SI)",      "Type":"SGX REIT ETF", "Ret1Y":"~ 9%","Ret3Y":"~ 4%","Ret5Y":"~ 6%","Min":"S$1",   "Risk":"Med",  "Access":"Any broker", "Note":"5.6% dividend yield"},
            {"Name":"Lion-Phillip S-REIT (CLR.SI)",      "Type":"SGX REIT ETF", "Ret1Y":"~ 9%","Ret3Y":"~ 4%","Ret5Y":"~ 6%","Min":"S$1",   "Risk":"Med",  "Access":"Any broker", "Note":"5.5% yield, Morningstar REIT index"},
            {"Name":"Syfe Equity100",                    "Type":"Robo",         "Ret1Y":"~10%","Ret3Y":"~11%","Ret5Y":"~14%","Min":"S$1",   "Risk":"Med-H","Access":"Syfe",       "Note":"Global equity, auto-rebalanced"},
            {"Name":"Endowus Fund Smart (100% eq)",      "Type":"Robo/Fund",    "Ret1Y":"~ 9%","Ret3Y":"~10%","Ret5Y":"~12%","Min":"S$1k",  "Risk":"Med-H","Access":"Endowus",    "Note":"Dimensional/Vanguard, CPF/SRS eligible"},
            {"Name":"Singapore Savings Bonds (SSB)",     "Type":"Capital-safe", "Ret1Y":"~ 3%","Ret3Y":"~ 3%","Ret5Y":"~ 3%","Min":"S$500", "Risk":"None", "Access":"DBS/OCBC",   "Note":"Govt-backed, flexible redemption"},
            {"Name":"T-bills 6-month",                   "Type":"Capital-safe", "Ret1Y":"~3.7%","Ret3Y":"~3.5%","Ret5Y":"~3%","Min":"S$1k","Risk":"None", "Access":"SGX/Banks",  "Note":"~3.7% yield, park idle cash"},
        ]
        show_fund_table(SG_FUNDS, "sg_funds_search")
        st.warning("⚠️ UCITS ETFs with 15-17% returns are heavily US-tech weighted. "
                   "Can drop 40-50% in bear markets. Only invest with a 5+ year horizon.")

    with lt_sub_us_funds:
        st.caption("🇺🇸 US-listed ETFs · IBKR/Tiger users · note US estate tax above USD 60k")
        US_FUNDS = [
            {"Name":"Vanguard S&P 500 ETF (VOO)",     "Type":"US ETF",       "Ret1Y":"~10%","Ret3Y":"~12%","Ret5Y":"~15%","Min":"$1",   "Risk":"Med",  "Access":"IBKR/Tiger","Note":"Lowest cost S&P 500, ER 0.03%"},
            {"Name":"Invesco Nasdaq-100 (QQQ)",         "Type":"US ETF",       "Ret1Y":"~11%","Ret3Y":"~14%","Ret5Y":"~18%","Min":"$1",   "Risk":"Med-H","Access":"IBKR/Tiger","Note":"Top 100 Nasdaq stocks"},
            {"Name":"Vanguard Total Market (VTI)",      "Type":"US ETF",       "Ret1Y":"~ 9%","Ret3Y":"~11%","Ret5Y":"~14%","Min":"$1",   "Risk":"Med",  "Access":"IBKR/Tiger","Note":"Entire US stock market"},
            {"Name":"iShares MSCI USA Quality (QUAL)",  "Type":"US ETF",       "Ret1Y":"~ 9%","Ret3Y":"~12%","Ret5Y":"~15%","Min":"$1",   "Risk":"Med",  "Access":"IBKR",      "Note":"High ROE, stable earnings, low leverage"},
            {"Name":"VanEck Wide Moat (MOAT)",          "Type":"US ETF",       "Ret1Y":"~ 9%","Ret3Y":"~11%","Ret5Y":"~14%","Min":"$1",   "Risk":"Med",  "Access":"IBKR",      "Note":"Morningstar wide-moat at fair value"},
            {"Name":"iShares Semiconductor (SOXX)",     "Type":"US ETF",       "Ret1Y":"~ 8%","Ret3Y":"~16%","Ret5Y":"~22%","Min":"$1",   "Risk":"High", "Access":"IBKR/Tiger","Note":"AI & chips — highest 5Y return, high vol"},
            {"Name":"Vanguard IT ETF (VGT)",            "Type":"US ETF",       "Ret1Y":"~12%","Ret3Y":"~16%","Ret5Y":"~19%","Min":"$1",   "Risk":"Med-H","Access":"IBKR/Tiger","Note":"MSFT, AAPL, NVDA heavy"},
            {"Name":"iShares MSCI India (INDA)",        "Type":"US ETF",       "Ret1Y":"~ 9%","Ret3Y":"~10%","Ret5Y":"~12%","Min":"$1",   "Risk":"Med-H","Access":"IBKR/Tiger","Note":"India large cap broad exposure"},
        ]
        show_fund_table(US_FUNDS, "us_funds_search")
        st.warning("⚠️ US estate tax risk for non-US persons above USD 60k. "
                   "Consider Irish UCITS equivalents (CSPX.L, VUAA.L) in SG Funds tab.")
