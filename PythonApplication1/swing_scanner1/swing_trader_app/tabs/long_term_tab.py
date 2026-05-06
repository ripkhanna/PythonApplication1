"""Long Term Tab renderer.

Readable Streamlit tab code extracted from the original working monolith.
Each render function receives the main runtime globals as ``ctx`` and exposes
them to this module so the body behaves like it did in the single-file app.
"""

def _bind_runtime(ctx: dict) -> None:
    """Expose original app globals to this module for monolith-compatible tab code."""
    globals().update(ctx)

def render_long_term(ctx: dict) -> None:
    _bind_runtime(ctx)
    st.caption("🌱 Long-Term Portfolio Builder · Stocks from top ETFs · Quality scored")

    lt_sub_us, lt_sub_sg, lt_sub_sg_funds, lt_sub_us_funds = st.tabs([
        "🇺🇸 US Stocks",
        "🇸🇬 SG Stocks",
        "🇸🇬 SG Funds & ETFs",
        "🇺🇸 US Funds & ETFs",
    ])

    # ── Shared scan function — shows ETF returns + stock results ─────────────
    def run_lt_scan(etf_dict, session_key, default_etfs, min_score_key, search_key,
                    existing_tickers=None, live_market_name=None, include_etf_tickers=True):
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            search = st.text_input("🔍 Search stock", placeholder="e.g. NVDA, DBS, Keppel",
                                   key=search_key).strip().upper()
        with c2:
            min_sc = st.slider("Min quality score", 1, 10, 5, key=min_score_key)
        with c3:
            max_lt_scan = st.slider("Max LT scan", 50, 1000, 300, step=25,
                                    key=f"{session_key}_max_scan",
                                    help="Maximum combined long-term candidates to score: existing tickers + ETF tickers/holdings + Yahoo/live tickers.")

        horizon_f = st.multiselect(
            "Filter horizon",
            ["⭐ CORE HOLD (3–5yr)","✅ BUY & HOLD (1–3yr)",
             "👀 ACCUMULATE on dips","⏳ MONITOR only"],
            default=[], key=f"hf_{session_key}", placeholder="All horizons"
        )

        if st.button("🔍 Find Long-Term Stocks", type="primary", key=f"btn_{session_key}"):
            etfs = list(default_etfs)
            existing_tickers = list(existing_tickers or [])

            # Long Term tab now scans a combined universe:
            #   existing curated tickers + ETF tickers + ETF holdings + Yahoo/live tickers.
            # Existing tickers are intentionally placed first so names such as UUUU/APP
            # are not pushed out by the scan limit.
            etf_holdings = {}
            source_map = {}

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
                p1.progress((i+1)/max(1, len(etfs)))
            p1.empty()

            live_tickers = []
            live_source = "Yahoo/live disabled"
            if use_live_universe and live_market_name:
                with st.spinner("Fetching Yahoo/live long-term universe…"):
                    live_tickers, live_source = fetch_live_market_universe(
                        live_market_name, max_symbols=max_live_universe
                    )
                for t in live_tickers:
                    _add_symbol(t, "Yahoo/live")

            # Preserve priority order: existing → ETF tickers → ETF holdings → Yahoo/live.
            combined = []
            combined.extend([_clean_symbol(t) for t in existing_tickers])
            if include_etf_tickers:
                combined.extend([_clean_symbol(t) for t in etf_dict.keys()])
            combined.extend(sorted(etf_holdings.keys(), key=lambda t: len(etf_holdings.get(t, [])), reverse=True))
            combined.extend(list(live_tickers))
            unique = [t for t in _unique_keep_order(combined) if t in source_map]
            scan_list = unique[:max_lt_scan]

            st.caption(
                f"Long-term universe: Existing **{len(existing_tickers)}** · ETFs **{len(etf_dict)}** · "
                f"ETF holdings **{len(etf_holdings)}** · Yahoo/live **{len(live_tickers)}** · "
                f"Scoring **{len(scan_list)}** / {len(unique)} candidates · Source: {live_source}"
            )

            results = []
            p2 = st.progress(0); st2 = st.empty()
            total = max(1, len(scan_list))
            for i, ticker in enumerate(scan_list):
                st2.caption(f"Scoring {ticker} ({i+1}/{len(scan_list)})…")
                row = score_lt_stock(ticker)
                if row and row.get("_score",0) >= min_sc:
                    row["In ETFs"]   = ", ".join(etf_holdings.get(ticker, [])[:4]) or "–"
                    row["ETF Count"] = len(etf_holdings.get(ticker, []))
                    row["Sources"]   = ", ".join(source_map.get(ticker, []))
                    results.append(row)
                p2.progress((i+1)/total)
            p2.empty(); st2.empty()

            results.sort(key=lambda x: (-x.get("ETF Count",0), -x.get("_score",0)))
            st.session_state[session_key] = results
            st.session_state[f"{session_key}_universe_csv"] = ", ".join(scan_list)
            st.session_state[f"{session_key}_universe_stats"] = {
                "existing": len(existing_tickers),
                "etfs": len(etf_dict),
                "etf_holdings": len(etf_holdings),
                "live": len(live_tickers),
                "scored": len(scan_list),
                "total_candidates": len(unique),
                "live_source": live_source,
            }

        results = st.session_state.get(session_key, [])
        if not results:
            return

        df_lt = pd.DataFrame(results)
        if search:
            df_lt = df_lt[df_lt["Ticker"].str.contains(search, na=False) |
                          df_lt["Name"].str.contains(search, case=False, na=False)]
        if horizon_f:
            df_lt = df_lt[df_lt["Horizon"].isin(horizon_f)]

        core = (df_lt["_hcol"]=="buy").sum()
        buyh = (df_lt["_hcol"]=="watch").sum()
        acc  = (df_lt["_hcol"]=="wait").sum()
        st.caption(f"⭐ **{core}** Core Hold · ✅ **{buyh}** Buy & Hold · 👀 **{acc}** Accumulate · {len(df_lt)} total")

        def style_horizon(val):
            s = str(val)
            if "CORE"  in s: return "background-color:#d4edda;color:#155724;font-weight:700"
            if "BUY"   in s: return "background-color:#d1ecf1;color:#0c5460;font-weight:600"
            if "ACCUM" in s: return "background-color:#fff3cd;color:#856404"
            return "color:#888"

        def style_exp1y(val):
            s = str(val)
            try:
                v = float(s.strip("+%"))
                if v >= 20: return "background-color:#1a7a3a;color:#fff;font-weight:700"
                if v >= 12: return "background-color:#27ae60;color:#fff;font-weight:600"
                if v >= 6:  return "background-color:#a9dfbf;color:#145a32"
            except: pass
            return ""

        def style_growth(val):
            try:
                v = float(str(val).strip("+%"))
                if v >= 20: return "color:#155724;font-weight:700"
                if v >= 10: return "color:#1a5276;font-weight:600"
            except: pass
            return ""

        disp = [c for c in ["Ticker","Name","Sector","Horizon","Exp 1Y Return",
                "Price","Mkt Cap","Return Breakdown",
                "Rev Growth","EPS Growth","ROE","Margin",
                "Fwd PE","Div Yield","Beta","MA200","Target","Upside","Rec",
                "Score","Sources","ETF Count","In ETFs"] if c in df_lt.columns]
        df_show = df_lt[disp].copy()

        col_cfg = {
            "Ticker":            st.column_config.TextColumn("Ticker",       width=62),
            "Name":              st.column_config.TextColumn("Name",         width=130),
            "Sector":            st.column_config.TextColumn("Sector",       width=95),
            "Sources":           st.column_config.TextColumn("Sources",      width=105),
            "ETF Count":         st.column_config.NumberColumn("ETFs",       width=42),
            "In ETFs":           st.column_config.TextColumn("In ETFs",      width=120),
            "Price":             st.column_config.TextColumn("Price",        width=60),
            "Mkt Cap":           st.column_config.TextColumn("Cap",          width=60),
            "Exp 1Y Return":     st.column_config.TextColumn("Exp 1Y Ret",   width=80),
            "Return Breakdown":  st.column_config.TextColumn("Div+Price",    width=130),
            "Rev Growth":        st.column_config.TextColumn("RevGrw",       width=58),
            "EPS Growth":        st.column_config.TextColumn("EPSGrw",       width=58),
            "ROE":               st.column_config.TextColumn("ROE",          width=48),
            "Margin":            st.column_config.TextColumn("Margin",       width=52),
            "Fwd PE":            st.column_config.TextColumn("FwdPE",        width=52),
            "Div Yield":         st.column_config.TextColumn("Yield",        width=48),
            "Beta":              st.column_config.TextColumn("Beta",         width=42),
            "MA200":             st.column_config.TextColumn("MA200",        width=42),
            "Target":            st.column_config.TextColumn("Target",       width=60),
            "Upside":            st.column_config.TextColumn("Upside",       width=52),
            "Rec":               st.column_config.TextColumn("Rec",          width=68),
            "Score":             st.column_config.TextColumn("Score",        width=48),
            "Horizon":           st.column_config.TextColumn("Horizon",      width=145),
        }
        cfg = {k:v for k,v in col_cfg.items() if k in df_show.columns}
        sfn = df_show.style.map if hasattr(df_show.style,"map") else df_show.style.applymap
        styled = sfn(style_horizon, subset=["Horizon"])
        if "Exp 1Y Return" in df_show.columns:
            styled = (styled.map if hasattr(styled,"map") else styled.applymap)(
                style_exp1y, subset=["Exp 1Y Return"])
        for col in ["Rev Growth","EPS Growth","Upside"]:
            if col in df_show.columns:
                styled = (styled.map if hasattr(styled,"map") else styled.applymap)(
                    style_growth, subset=[col])
        st.dataframe(styled, width="stretch", hide_index=True,
                     column_config=cfg, height=min(40+len(df_show)*35, 600))
        st.caption("Score/10: RevGrw(+2) EPSGrw(+2) ROE(+1) Margin(+1) LowDebt(+1) AboveMA200(+1) Target(+1) BuyRated(+1) · "
                   "ETF Count = held by how many ETFs (higher = more institutional conviction)")
        stats = st.session_state.get(f"{session_key}_universe_stats", {})
        csv_tickers = st.session_state.get(f"{session_key}_universe_csv", "")
        if stats:
            st.caption(
                f"Scanned universe: Existing {stats.get('existing',0)} · ETFs {stats.get('etfs',0)} · "
                f"ETF holdings {stats.get('etf_holdings',0)} · Yahoo/live {stats.get('live',0)} · "
                f"Scored {stats.get('scored',0)} / {stats.get('total_candidates',0)}"
            )
        if csv_tickers:
            with st.expander("📋 Long-term scanned tickers", expanded=False):
                st.text_area("Comma-separated tickers", value=csv_tickers, height=90,
                             key=f"{session_key}_universe_text")

    # ── Shared fund table function ────────────────────────────────────────────
    def show_fund_table(fund_rows, search_key):
        fsrch = st.text_input("🔍 Search fund", placeholder="Vanguard, REIT, Robo…",
                              key=search_key).strip()
        df_f = pd.DataFrame(fund_rows)
        if fsrch:
            df_f = df_f[df_f.apply(lambda r: fsrch.lower() in str(r).lower(), axis=1)]

        def sret(val):
            s = str(val)
            for p in ["17","18","19","20","21","22","15","16"]:
                if p in s: return "background-color:#d4edda;color:#155724;font-weight:700"
            for p in ["10","11","12","13","14"]:
                if p in s: return "background-color:#d1ecf1;color:#0c5460;font-weight:600"
            return "color:#888"

        def srisk(val):
            s = str(val)
            if s == "None": return "background-color:#d4edda;color:#155724"
            if s == "Med":  return "background-color:#d1ecf1;color:#0c5460"
            if "Med-H" in s:return "background-color:#fff3cd;color:#856404"
            if s == "High": return "background-color:#f8d7da;color:#721c24"
            return ""

        # Build display columns — include 1Y/3Y if present
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
        sfn = df_f.style.map if hasattr(df_f.style,"map") else df_f.style.applymap
        styled = sfn(sret, subset=ret_cols) if ret_cols else df_f.style
        styled = (styled.map if hasattr(styled,"map") else styled.applymap)(srisk, subset=["Risk"])
        cfg = {k:v for k,v in col_cfg_f.items() if k in df_f.columns}
        st.dataframe(styled, width="stretch", hide_index=True,
                     column_config=cfg, height=min(40+len(df_f)*35, 560))
        st.caption("Returns are approximate annualised historical figures. Past performance ≠ future returns.")

    # ─────────────────────────────────────────────────────────────────────────
    with lt_sub_us:
        st.caption("🇺🇸 US long-term universe = existing US tickers + ETF tickers/holdings + Yahoo/live tickers · sorted by cross-ETF conviction")
        with st.expander("📊 Source ETFs — 1Y / 3Y / 5Y Ann Returns (click column to sort)", expanded=False):
            df_etf_us = pd.DataFrame([
                {"ETF":k, "Name":v["name"], "Theme":v["theme"],
                 "1Y Ann%": v.get('ret1y',0),
                 "3Y Ann%": v.get('ret3y',0),
                 "5Y Ann%": v.get('ret5y',0)}
                for k,v in LT_ETF_US.items()
            ])
            def _sc(val):
                v = float(val)
                if v>=15: return "background-color:#1a7a3a;color:#fff;font-weight:700"
                if v>=10: return "background-color:#1a5276;color:#fff;font-weight:600"
                if v>= 5: return "background-color:#f0c040;color:#333"
                if v< 0:  return "background-color:#922b21;color:#fff"
                return ""
            sfn = df_etf_us.style.map if hasattr(df_etf_us.style,"map") else df_etf_us.style.applymap
            st.dataframe(
                sfn(_sc, subset=["1Y Ann%","3Y Ann%","5Y Ann%"]),
                width="stretch", hide_index=True,
                column_config={
                    "ETF":     st.column_config.TextColumn("ETF",    width=70),
                    "Name":    st.column_config.TextColumn("Name",   width=190),
                    "Theme":   st.column_config.TextColumn("Theme",  width=120),
                    "1Y Ann%": st.column_config.NumberColumn("1Y Ann%", format="%.1f%%", width=80),
                    "3Y Ann%": st.column_config.NumberColumn("3Y Ann%", format="%.1f%%", width=80),
                    "5Y Ann%": st.column_config.NumberColumn("5Y Ann%", format="%.1f%%", width=80),
                },
                height=min(40+len(df_etf_us)*35, 450),
            )
        run_lt_scan(LT_ETF_US, "lt_us",
                    ["QQQ","QUAL","MOAT","SOXX","VGT","INDA","SMIN"],
                    "lt_us_min", "lt_us_search",
                    existing_tickers=US_TICKERS,
                    live_market_name="🇺🇸 US",
                    include_etf_tickers=True)

    # ─────────────────────────────────────────────────────────────────────────
    with lt_sub_sg:
        st.caption("🇸🇬 SGX long-term stocks · quality scored · curated list + ETF holdings")
        with st.expander("📊 Source ETFs — 1Y / 3Y / 5Y Ann Returns (click column to sort)", expanded=False):
            df_etf_sg = pd.DataFrame([
                {"ETF":k, "Name":v["name"], "Theme":v["theme"],
                 "1Y Ann%": v.get('ret1y',0),
                 "3Y Ann%": v.get('ret3y',0),
                 "5Y Ann%": v.get('ret5y',0)}
                for k,v in LT_ETF_SG.items()
            ])
            def _sc2(val):
                v = float(val)
                if v>=15: return "background-color:#1a7a3a;color:#fff;font-weight:700"
                if v>=10: return "background-color:#1a5276;color:#fff;font-weight:600"
                if v>= 5: return "background-color:#f0c040;color:#333"
                if v<  0: return "background-color:#922b21;color:#fff"
                return ""
            sfn2 = df_etf_sg.style.map if hasattr(df_etf_sg.style,"map") else df_etf_sg.style.applymap
            st.dataframe(
                sfn2(_sc2, subset=["1Y Ann%","3Y Ann%","5Y Ann%"]),
                width="stretch", hide_index=True,
                column_config={
                    "ETF":     st.column_config.TextColumn("ETF",    width=70),
                    "Name":    st.column_config.TextColumn("Name",   width=190),
                    "Theme":   st.column_config.TextColumn("Theme",  width=120),
                    "1Y Ann%": st.column_config.NumberColumn("1Y Ann%", format="%.1f%%", width=80),
                    "3Y Ann%": st.column_config.NumberColumn("3Y Ann%", format="%.1f%%", width=80),
                    "5Y Ann%": st.column_config.NumberColumn("5Y Ann%", format="%.1f%%", width=80),
                },
                height=min(40+len(df_etf_sg)*35, 420),
            )

        # Curated SGX long-term universe — reliable fallback when ETF holdings unavailable
        SG_LT_TICKERS = [
            # ── Banks (highest quality on SGX) ────────────────────────────────
            "D05.SI",   # DBS — strongest bank in SE Asia, consistent div growth
            "O39.SI",   # OCBC — wealth management + banking, capital strength
            "U11.SI",   # UOB — ASEAN expansion, steady compounder
            # ── Financials / Exchanges ─────────────────────────────────────────
            "S68.SI",   # SGX — monopoly exchange, record profits 2025-2026
            "AIY.SI",   # iFAST — UK ePension growth driver, fintech compounder
            # ── Technology / Semiconductor supply chain ────────────────────────
            "558.SI",   # UMS Holdings — semiconductor equipment, AI supply chain
            "E28.SI",   # Frencken — semicon EMS, 47.8% return Q1 2026
            "5AB.SI",   # AEM Holdings — semiconductor test, TSMC/Intel exposure
            "BN2.SI",   # Valuetronics — electronics, institutional buying
            "V03.SI",   # Venture Corp — high-mix electronics, quality manufacturer
            # ── Industrials / Offshore ─────────────────────────────────────────
            "S51.SI",   # Seatrium — offshore & marine, clean energy contracts
            "BN4.SI",   # Keppel Corp — asset-light transformation, infra
            "U96.SI",   # Sembcorp — clean energy, data centre power
            "S58.SI",   # SATS — aviation ground handling, post-COVID recovery
            # ── Telecoms ──────────────────────────────────────────────────────
            "Z74.SI",   # Singtel — 5G + regional associates (AIS, Airtel, Optus)
            # ── Consumer / Property ───────────────────────────────────────────
            "C52.SI",   # ComfortDelGro — transport, UK recovery
            "F34.SI",   # Wilmar International — agribusiness, Asia consumer
            "OYY.SI",   # PropNex — property agency, recurring commission
            # ── REITs (income + growth) ────────────────────────────────────────
            "C38U.SI",  # CapitaLand CICT — premium SG retail + commercial
            "A17U.SI",  # Ascendas REIT — industrial/logistics, quarterly div
            "M44U.SI",  # Mapletree Logistics — Asia logistics, quarterly div
            "AJBU.SI",  # Keppel DC REIT — data centres, AI tailwind
            "J91U.SI",  # AIMS APAC REIT — industrial, 6.5% yield
            "SK6U.SI",  # Frasers Centrepoint Trust — suburban malls
            # ── Civil construction / Infrastructure ────────────────────────────
            "P9D.SI",   # Civmec — industrial construction
            "5JS.SI",   # Dyna-Mac — offshore modules
        ]

        # Search + score controls
        sg_c1, sg_c2 = st.columns([3, 1])
        with sg_c1:
            sg_search = st.text_input("🔍 Search stock",
                placeholder="e.g. DBS, Keppel, REIT", key="lt_sg_search").strip().upper()
        with sg_c2:
            sg_min_sc = st.slider("Min score", 1, 10, 4, key="lt_sg_min")

        sg_horizon_f = st.multiselect(
            "Filter horizon",
            ["⭐ CORE HOLD (3–5yr)","✅ BUY & HOLD (1–3yr)",
             "👀 ACCUMULATE on dips","⏳ MONITOR only"],
            default=[], key="hf_lt_sg", placeholder="All horizons"
        )

        lt_sg_max_scan = st.slider("Max SG LT scan", 25, 1000, 250, step=25,
                                  key="lt_sg_max_scan",
                                  help="Maximum combined SG long-term candidates to score: SG curated/existing tickers + SG ETF tickers + SGX/live tickers.")

        if st.button("🔍 Score SGX Long-Term Stocks", type="primary", key="btn_lt_sg"):
            live_sg_tickers = []
            live_sg_source = "SGX/live disabled"
            if use_live_universe:
                with st.spinner("Fetching SGX/live long-term universe…"):
                    live_sg_tickers, live_sg_source = fetch_live_market_universe(
                        "🇸🇬 SGX", max_symbols=max_live_universe
                    )

            sg_sources = {}
            def _add_sg(sym, src, force_sg_suffix=True):
                suffix = ".SI" if force_sg_suffix and not str(sym).upper().endswith(".SI") and "." not in str(sym) else ""
                sym = _clean_symbol(sym, suffix)
                if not sym:
                    return
                sg_sources.setdefault(sym, [])
                if src not in sg_sources[sym]:
                    sg_sources[sym].append(src)

            for t in SG_LT_TICKERS:
                _add_sg(t, "LT curated")
            for t in SG_TICKERS:
                _add_sg(t, "Existing")
            for t in LT_ETF_SG.keys():
                _add_sg(t, "ETF", force_sg_suffix=False)
            for t in live_sg_tickers:
                _add_sg(t, "SGX/live")

            sg_scan_list = _unique_keep_order(
                [_clean_symbol(t, ".SI" if not str(t).upper().endswith(".SI") and "." not in str(t) else "") for t in SG_LT_TICKERS] +
                [_clean_symbol(t, ".SI" if not str(t).upper().endswith(".SI") and "." not in str(t) else "") for t in SG_TICKERS] +
                [_clean_symbol(t) for t in LT_ETF_SG.keys()] +
                [_clean_symbol(t, ".SI" if not str(t).upper().endswith(".SI") and "." not in str(t) else "") for t in live_sg_tickers]
            )[:lt_sg_max_scan]

            st.caption(
                f"SG long-term universe: LT curated {len(SG_LT_TICKERS)} · Existing {len(SG_TICKERS)} · "
                f"ETFs {len(LT_ETF_SG)} · SGX/live {len(live_sg_tickers)} · "
                f"Scoring {len(sg_scan_list)} / {len(sg_sources)} candidates · Source: {live_sg_source}"
            )

            results = []
            p = st.progress(0); st_s = st.empty()
            total = max(1, len(sg_scan_list))
            for i, ticker in enumerate(sg_scan_list):
                st_s.caption(f"Scoring {ticker} ({i+1}/{len(sg_scan_list)})…")
                row = score_lt_stock(ticker)
                if row and row.get("_score", 0) >= sg_min_sc:
                    row["Sources"] = ", ".join(sg_sources.get(ticker, []))
                    results.append(row)
                p.progress((i+1)/total)
            p.empty(); st_s.empty()
            results.sort(key=lambda x: -x.get("_score", 0))
            st.session_state["lt_sg"] = results
            st.session_state["lt_sg_universe_csv"] = ", ".join(sg_scan_list)
            st.session_state["lt_sg_universe_stats"] = {
                "lt_curated": len(SG_LT_TICKERS),
                "existing": len(SG_TICKERS),
                "etfs": len(LT_ETF_SG),
                "live": len(live_sg_tickers),
                "scored": len(sg_scan_list),
                "total_candidates": len(sg_sources),
                "live_source": live_sg_source,
            }

        results = st.session_state.get("lt_sg", [])
        if not results:
            st.info(f"Click 🔍 Score SGX Long-Term Stocks. Scores combined SGX universe: LT curated + existing tickers + SG ETFs + SGX/live tickers on: "
                    "revenue growth, EPS growth, ROE, margins, debt, price vs MA200, analyst target, Buy rating.")
        else:
            df_sg = pd.DataFrame(results)
            if sg_search:
                df_sg = df_sg[df_sg["Ticker"].str.contains(sg_search, na=False) |
                              df_sg["Name"].str.contains(sg_search, case=False, na=False)]
            if sg_horizon_f:
                df_sg = df_sg[df_sg["Horizon"].isin(sg_horizon_f)]

            core = (df_sg["_hcol"]=="buy").sum()
            buyh = (df_sg["_hcol"]=="watch").sum()
            acc  = (df_sg["_hcol"]=="wait").sum()
            st.caption(f"⭐ **{core}** Core Hold · ✅ **{buyh}** Buy & Hold · "
                       f"👀 **{acc}** Accumulate · {len(df_sg)} total")

            def _sth(val):
                s = str(val)
                if "CORE"  in s: return "background-color:#d4edda;color:#155724;font-weight:700"
                if "BUY"   in s: return "background-color:#d1ecf1;color:#0c5460;font-weight:600"
                if "ACCUM" in s: return "background-color:#fff3cd;color:#856404"
                return "color:#888"

            def _stg(val):
                try:
                    v = float(str(val).strip("+%"))
                    if v >= 20: return "color:#155724;font-weight:700"
                    if v >= 10: return "color:#1a5276;font-weight:600"
                except: pass
                return ""

            disp = [c for c in ["Ticker","Name","Sector","Sources","Price","Mkt Cap",
                    "Exp 1Y Return","Return Breakdown",
                    "Rev Growth","EPS Growth","ROE","Margin","Fwd PE",
                    "Div Yield","Beta","MA200","Target","Upside","Rec",
                    "Score","Horizon"] if c in df_sg.columns]
            df_show = df_sg[disp].copy()

            col_cfg_sg = {
                "Ticker":           st.column_config.TextColumn("Ticker",      width=70),
                "Name":             st.column_config.TextColumn("Name",        width=150),
                "Sector":           st.column_config.TextColumn("Sector",      width=95),
                "Sources":          st.column_config.TextColumn("Sources",     width=105),
                "Price":            st.column_config.TextColumn("Price",       width=62),
                "Mkt Cap":          st.column_config.TextColumn("Cap",         width=62),
                "Exp 1Y Return":    st.column_config.TextColumn("Exp 1Y Ret",  width=80),
                "Return Breakdown": st.column_config.TextColumn("Div+Price",   width=130),
                "Rev Growth":       st.column_config.TextColumn("RevGrw",      width=58),
                "EPS Growth":       st.column_config.TextColumn("EPSGrw",      width=58),
                "ROE":              st.column_config.TextColumn("ROE",         width=48),
                "Margin":           st.column_config.TextColumn("Margin",      width=52),
                "Fwd PE":           st.column_config.TextColumn("FwdPE",       width=52),
                "Div Yield":        st.column_config.TextColumn("Yield",       width=50),
                "Beta":             st.column_config.TextColumn("Beta",        width=42),
                "MA200":            st.column_config.TextColumn("MA200",       width=45),
                "Target":           st.column_config.TextColumn("Target",      width=62),
                "Upside":           st.column_config.TextColumn("Upside",      width=52),
                "Rec":              st.column_config.TextColumn("Rec",         width=68),
                "Score":            st.column_config.TextColumn("Score",       width=48),
                "Horizon":          st.column_config.TextColumn("Horizon",     width=145),
            }
            cfg = {k:v for k,v in col_cfg_sg.items() if k in df_show.columns}
            sfn = df_show.style.map if hasattr(df_show.style,"map") else df_show.style.applymap
            styled = sfn(_sth, subset=["Horizon"])
            if "Exp 1Y Return" in df_show.columns:
                def _se(val):
                    try:
                        v = float(str(val).strip("+%"))
                        if v >= 20: return "background-color:#1a7a3a;color:#fff;font-weight:700"
                        if v >= 12: return "background-color:#27ae60;color:#fff;font-weight:600"
                        if v >= 6:  return "background-color:#a9dfbf;color:#145a32"
                    except: pass
                    return ""
                styled = (styled.map if hasattr(styled,"map") else styled.applymap)(
                    _se, subset=["Exp 1Y Return"])
            for col in ["Rev Growth","EPS Growth","Upside"]:
                if col in df_show.columns:
                    styled = (styled.map if hasattr(styled,"map") else styled.applymap)(
                        _stg, subset=[col])
            st.dataframe(styled, width="stretch", hide_index=True,
                         column_config=cfg, height=min(40+len(df_show)*35, 600))
            st.caption("Score/10: RevGrw(+2) EPSGrw(+2) ROE>15%(+1) Margin>15%(+1) "
                       "LowDebt(+1) AboveMA200(+1) AnalystTarget(+1) BuyRated(+1)")
            sg_stats = st.session_state.get("lt_sg_universe_stats", {})
            sg_csv = st.session_state.get("lt_sg_universe_csv", "")
            if sg_stats:
                st.caption(
                    f"Scanned universe: LT curated {sg_stats.get('lt_curated',0)} · Existing {sg_stats.get('existing',0)} · "
                    f"ETFs {sg_stats.get('etfs',0)} · SGX/live {sg_stats.get('live',0)} · "
                    f"Scored {sg_stats.get('scored',0)} / {sg_stats.get('total_candidates',0)}"
                )
            if sg_csv:
                with st.expander("📋 SG long-term scanned tickers", expanded=False):
                    st.text_area("Comma-separated tickers", value=sg_csv, height=90,
                                 key="lt_sg_universe_text")

    # ─────────────────────────────────────────────────────────────────────────
    with lt_sub_sg_funds:
        st.caption("🇸🇬 SG-accessible ETFs & funds · UCITS, SGX-listed, Robo-advisors, CPF-investible")
        SG_FUNDS = [
            {"Name":"Vanguard S&P 500 (VUAA.L)",       "Type":"UCITS ETF",      "Ret1Y":"~10%","Ret3Y":"~12%","Ret5Y":"~15%","Min":"S$1",    "Risk":"Med",  "Access":"IBKR/Moomoo","Note":"Irish-domiciled, accumulating, 0% WHT"},
            {"Name":"iShares S&P 500 (CSPX.L)",        "Type":"UCITS ETF",      "Ret1Y":"~10%","Ret3Y":"~12%","Ret5Y":"~15%","Min":"S$1",    "Risk":"Med",  "Access":"IBKR",       "Note":"Acc, no dividend drag, ER 0.07%"},
            {"Name":"Xtrackers Nasdaq-100 (XNAS.L)",   "Type":"UCITS ETF",      "Ret1Y":"~11%","Ret3Y":"~14%","Ret5Y":"~17%","Min":"S$1",    "Risk":"Med-H","Access":"IBKR",       "Note":"Best UCITS Nasdaq option, ER 0.20%"},
            {"Name":"AXA Nasdaq-100 (ANAU.DE)",        "Type":"UCITS ETF",      "Ret1Y":"~11%","Ret3Y":"~14%","Ret5Y":"~17%","Min":"S$1",    "Risk":"Med-H","Access":"IBKR",       "Note":"EUR-denominated Nasdaq tracker"},
            {"Name":"Vanguard FTSE All-World (VWRA.L)","Type":"UCITS ETF",      "Ret1Y":"~ 8%","Ret3Y":"~10%","Ret5Y":"~13%","Min":"S$1",    "Risk":"Med",  "Access":"IBKR",       "Note":"Global diversification in 1 ETF"},
            {"Name":"SPDR MSCI World (SWRD.L)",        "Type":"UCITS ETF",      "Ret1Y":"~ 8%","Ret3Y":"~10%","Ret5Y":"~13%","Min":"S$1",    "Risk":"Med",  "Access":"IBKR",       "Note":"Developed markets only, ER 0.12%"},
            {"Name":"SPDR STI ETF (ES3.SI)",           "Type":"SGX ETF",        "Ret1Y":"~29%","Ret3Y":"~13%","Ret5Y":"~10%","Min":"S$500",  "Risk":"Med",  "Access":"Any broker", "Note":"CPF-OA investible, tracks STI 30"},
            {"Name":"Nikko AM STI ETF (G3B.SI)",       "Type":"SGX ETF",        "Ret1Y":"~29%","Ret3Y":"~13%","Ret5Y":"~10%","Min":"S$100",  "Risk":"Med",  "Access":"Any broker", "Note":"CPF-OA investible, lowest TER 0.21%"},
            {"Name":"CSOP S-REIT Leaders (SRT.SI)",    "Type":"SGX REIT ETF",   "Ret1Y":"~ 9%","Ret3Y":"~ 4%","Ret5Y":"~ 6%","Min":"S$1",    "Risk":"Med",  "Access":"Any broker", "Note":"5.6% dividend yield + REIT diversification"},
            {"Name":"Lion-Phillip S-REIT (CLR.SI)",    "Type":"SGX REIT ETF",   "Ret1Y":"~ 9%","Ret3Y":"~ 4%","Ret5Y":"~ 6%","Min":"S$1",    "Risk":"Med",  "Access":"Any broker", "Note":"Morningstar REIT index, 5.5% yield"},
            {"Name":"ABF SG Bond ETF (A35.SI)",        "Type":"SGX Bond ETF",   "Ret1Y":"~ 3%","Ret3Y":"~ 2%","Ret5Y":"~ 4%","Min":"S$1",    "Risk":"Low",  "Access":"Any broker", "Note":"Asia bond diversification, 4.6% yield"},
            {"Name":"Syfe Equity100",                  "Type":"Robo",           "Ret1Y":"~10%","Ret3Y":"~11%","Ret5Y":"~14%","Min":"S$1",    "Risk":"Med-H","Access":"Syfe",       "Note":"Global equity, auto-rebalanced"},
            {"Name":"Endowus Fund Smart (100% eq)",    "Type":"Robo/Fund",      "Ret1Y":"~ 9%","Ret3Y":"~10%","Ret5Y":"~12%","Min":"S$1k",   "Risk":"Med-H","Access":"Endowus",    "Note":"Dimensional/Vanguard funds, CPF/SRS eligible"},
            {"Name":"StashAway 36% Risk",              "Type":"Robo",           "Ret1Y":"~ 8%","Ret3Y":"~ 9%","Ret5Y":"~11%","Min":"S$0",    "Risk":"Med",  "Access":"StashAway",  "Note":"ERAA risk-managed, SRS eligible"},
            {"Name":"POEMS Share Builders Plan",       "Type":"RSP (DCA)",      "Ret1Y":"~29%","Ret3Y":"~13%","Ret5Y":"~12%","Min":"S$100/m","Risk":"Med",  "Access":"Phillip",    "Note":"Monthly DCA into STI/blue chips"},
            {"Name":"Singapore Savings Bonds (SSB)",   "Type":"Capital-safe",   "Ret1Y":"~ 3%","Ret3Y":"~ 3%","Ret5Y":"~ 3%","Min":"S$500",  "Risk":"None", "Access":"DBS/OCBC",   "Note":"Govt-backed, flexible redemption"},
            {"Name":"T-bills 6-month",                 "Type":"Capital-safe",   "Ret1Y":"~3.7%","Ret3Y":"~3.5%","Ret5Y":"~3%","Min":"S$1k",  "Risk":"None", "Access":"SGX/Banks",  "Note":"Current yield ~3.7%, park idle cash"},
        ]
        show_fund_table(SG_FUNDS, "sg_funds_search")
        st.warning("⚠️ UCITS ETFs with 15-17% returns are heavily US-tech weighted. Can drop 40-50% in bear markets. "
                   "Only invest if you have a 5+ year horizon. Capital-safe options (SSB, T-bills) give 3-4% with zero risk.")

    # ─────────────────────────────────────────────────────────────────────────
    with lt_sub_us_funds:
        st.caption("🇺🇸 US-listed ETFs & funds · best for IBKR/Tiger users · note US estate tax above USD 60k")
        US_FUNDS = [
            # Core index
            {"Name":"Vanguard S&P 500 ETF (VOO)",      "Type":"US ETF",         "Ret1Y":"~10%","Ret3Y":"~12%","Ret5Y":"~15%","Min":"$1",    "Risk":"Med",  "Access":"IBKR/Tiger", "Note":"Lowest cost S&P 500, ER 0.03%"},
            {"Name":"Invesco Nasdaq-100 (QQQ)",         "Type":"US ETF",         "Ret1Y":"~11%","Ret3Y":"~14%","Ret5Y":"~18%","Min":"$1",    "Risk":"Med-H","Access":"IBKR/Tiger", "Note":"Top 100 Nasdaq stocks"},
            {"Name":"Vanguard Total Mkt (VTI)",         "Type":"US ETF",         "Ret1Y":"~ 9%","Ret3Y":"~11%","Ret5Y":"~14%","Min":"$1",    "Risk":"Med",  "Access":"IBKR/Tiger", "Note":"Entire US stock market"},
            # Quality/factor
            {"Name":"iShares MSCI USA Quality (QUAL)",  "Type":"US ETF",         "Ret1Y":"~ 9%","Ret3Y":"~12%","Ret5Y":"~15%","Min":"$1",    "Risk":"Med",  "Access":"IBKR",       "Note":"High ROE, stable earnings, low leverage"},
            {"Name":"VanEck Wide Moat (MOAT)",          "Type":"US ETF",         "Ret1Y":"~ 9%","Ret3Y":"~11%","Ret5Y":"~14%","Min":"$1",    "Risk":"Med",  "Access":"IBKR",       "Note":"Morningstar wide-moat stocks at fair value"},
            {"Name":"WisdomTree Div Growth (DGRW)",     "Type":"US ETF",         "Ret1Y":"~ 8%","Ret3Y":"~11%","Ret5Y":"~13%","Min":"$1",    "Risk":"Med",  "Access":"IBKR",       "Note":"Dividend growers, quality tilt"},
            # Sector
            {"Name":"iShares Semiconductor (SOXX)",     "Type":"US ETF",         "Ret1Y":"~ 8%","Ret3Y":"~16%","Ret5Y":"~22%","Min":"$1",    "Risk":"High", "Access":"IBKR/Tiger", "Note":"AI & chips — highest 5Y return, high vol"},
            {"Name":"Vanguard IT ETF (VGT)",            "Type":"US ETF",         "Ret1Y":"~12%","Ret3Y":"~16%","Ret5Y":"~19%","Min":"$1",    "Risk":"Med-H","Access":"IBKR/Tiger", "Note":"MSFT, AAPL, NVDA heavy"},
            {"Name":"iShares Software (IGV)",           "Type":"US ETF",         "Ret1Y":"~10%","Ret3Y":"~14%","Ret5Y":"~17%","Min":"$1",    "Risk":"Med-H","Access":"IBKR",       "Note":"Pure software — MSFT, ORCL, CRM, ADBE"},
            {"Name":"Global X Robotics & AI (BOTZ)",    "Type":"US ETF",         "Ret1Y":"~ 6%","Ret3Y":"~ 9%","Ret5Y":"~12%","Min":"$1",    "Risk":"High", "Access":"IBKR/Tiger", "Note":"Robotics, AI, automation thematic"},
            {"Name":"Global X Cloud (CLOU)",            "Type":"US ETF",         "Ret1Y":"~ 8%","Ret3Y":"~ 9%","Ret5Y":"~11%","Min":"$1",    "Risk":"Med-H","Access":"IBKR",       "Note":"Cloud computing companies"},
            {"Name":"First Trust Cybersecurity (CIBR)", "Type":"US ETF",         "Ret1Y":"~10%","Ret3Y":"~12%","Ret5Y":"~14%","Min":"$1",    "Risk":"Med-H","Access":"IBKR",       "Note":"Cybersecurity sector leader"},
            {"Name":"Global X US Infrastructure (PAVE)","Type":"US ETF",         "Ret1Y":"~12%","Ret3Y":"~13%","Ret5Y":"~15%","Min":"$1",    "Risk":"Med",  "Access":"IBKR",       "Note":"US infrastructure spend beneficiary"},
            # India
            {"Name":"iShares MSCI India (INDA)",        "Type":"US ETF",         "Ret1Y":"~ 9%","Ret3Y":"~10%","Ret5Y":"~12%","Min":"$1",    "Risk":"Med-H","Access":"IBKR/Tiger", "Note":"India large cap broad exposure"},
            {"Name":"iShares India Small Cap (SMIN)",   "Type":"US ETF",         "Ret1Y":"~10%","Ret3Y":"~12%","Ret5Y":"~15%","Min":"$1",    "Risk":"High", "Access":"IBKR",       "Note":"India small cap premium, high growth"},
            # Funds
            {"Name":"Fidelity Contrafund (FCNTX)",      "Type":"US Mutual Fund", "Ret1Y":"~10%","Ret3Y":"~12%","Ret5Y":"~14%","Min":"$2.5k", "Risk":"Med-H","Access":"Fidelity",   "Note":"Active large-growth fund, long track record"},
            {"Name":"T. Rowe Price Growth (PRGFX)",     "Type":"US Mutual Fund", "Ret1Y":"~11%","Ret3Y":"~13%","Ret5Y":"~16%","Min":"$2.5k", "Risk":"Med-H","Access":"TRowe",      "Note":"Active large-growth, tech overweight"},
        ]
        show_fund_table(US_FUNDS, "us_funds_search")
        st.warning("⚠️ US-listed ETFs carry US estate tax risk for non-US persons above USD 60k total. "
                   "Consider Irish-domiciled UCITS equivalents (CSPX.L, VUAA.L, XNAS.L) in the 🇸🇬 SG Funds tab instead. "
                   "Not financial advice.")

