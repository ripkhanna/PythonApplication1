"""Etf Holdings Tab renderer.

Readable Streamlit tab code extracted from the original working monolith.
Each render function receives the main runtime globals as ``ctx`` and exposes
them to this module so the body behaves like it did in the single-file app.
"""

def _bind_runtime(ctx: dict) -> None:
    """Expose original app globals to this module for monolith-compatible tab code."""
    globals().update(ctx)

def render_etf_holdings(ctx: dict) -> None:
    _bind_runtime(ctx)
    st.caption("📊 ETF Holdings")
    st.caption("Fetched · Cached 6 hours · Click a sector to expand")

    # ── SG INVESTOR ETF DASHBOARD ─────────────────────────────────────────────
    st.markdown("#### 🇸🇬 SG Investor ETF Dashboard — Performance & Fee Matrix")
    st.caption("Irish-domiciled UCITS · 15% WHT · No US Estate Tax Risk · ER & Yield fetched live")

    SG_ETF_UNIVERSE = {
        "CSPX.L":  {"Name": "iShares Core S&P 500 (Acc)",       "Focus": "US Large Cap"},
        "VUAA.L":  {"Name": "Vanguard S&P 500 (Acc)",           "Focus": "US Large Cap"},
        "VWRA.L":  {"Name": "Vanguard FTSE All-World",          "Focus": "Global (Dev + EM)"},
        "SWRD.L":  {"Name": "SPDR MSCI World",                  "Focus": "Developed Markets"},
        "ISAC.L":  {"Name": "iShares MSCI ACWI",                "Focus": "Global (Dev + EM)"},
        "ANAU.DE": {"Name": "AXA Nasdaq 100 (Acc)",             "Focus": "US Tech Growth"},
        "XNAS.L":  {"Name": "Xtrackers Nasdaq-100 UCITS (Acc)", "Focus": "US Tech Growth"},
        "2854.T":  {"Name": "Global X Japan Tech Top 20",       "Focus": "Japan Tech Growth"},
        "1475.T":  {"Name": "iShares Core TOPIX",               "Focus": "Japan Broad Market"},
    }

    # Fallback values in case live fetch fails
    _ER_FALLBACK    = {"CSPX.L":0.07,"VUAA.L":0.07,"VWRA.L":0.22,"SWRD.L":0.12,
                       "ISAC.L":0.20,"ANAU.DE":0.14,"XNAS.L":0.20,"2854.T":0.30,"1475.T":0.05}
    _YIELD_FALLBACK = {"CSPX.L":1.10,"VUAA.L":1.15,"VWRA.L":1.50,"SWRD.L":1.41,
                       "ISAC.L":1.45,"ANAU.DE":0.70,"XNAS.L":0.00,"2854.T":0.71,"1475.T":1.70}

    @st.cache_data(ttl=3600)
    def fetch_sg_etf_data():
        rows = []
        # FX rates
        try:    jpy_usd = 1 / yf.Ticker("JPY=X").fast_info["last_price"]
        except: jpy_usd = 0.0064
        try:    gbp_usd = yf.Ticker("GBPUSD=X").fast_info["last_price"]
        except: gbp_usd = 1.27
        try:    eur_usd = yf.Ticker("EURUSD=X").fast_info["last_price"]
        except: eur_usd = 1.08

        for ticker, meta in SG_ETF_UNIVERSE.items():
            # ── Fetch ER and Yield dynamically ───────────────────────────────
            er    = _ER_FALLBACK.get(ticker, np.nan)
            yield_ = _YIELD_FALLBACK.get(ticker, np.nan)
            try:
                tkr_obj = yf.Ticker(ticker)
                info    = tkr_obj.info

                # Expense ratio — multiple possible keys
                for key in ("annualReportExpenseRatio", "totalExpenseRatio",
                            "netExpenseRatio", "expenseRatio"):
                    v = info.get(key)
                    if v and v > 0:
                        # yfinance returns as decimal (0.0007) or percent (0.07)
                        er = round(v * 100 if v < 1 else v, 4)
                        break

                # Also try funds_data
                if er == _ER_FALLBACK.get(ticker, np.nan):
                    try:
                        fd_info = tkr_obj.funds_data.fund_overview
                        if fd_info is not None and not fd_info.empty:
                            for key in ("annualReportExpenseRatio","netExpenseRatio"):
                                if key in fd_info.index:
                                    v = float(fd_info.loc[key])
                                    if v > 0:
                                        er = round(v * 100 if v < 1 else v, 4)
                                        break
                    except Exception:
                        pass

                # Dividend yield — multiple possible keys
                for key in ("trailingAnnualDividendYield", "yield",
                            "dividendYield", "fiveYearAvgDividendYield"):
                    v = info.get(key)
                    if v and v > 0:
                        yield_ = round(v * 100 if v < 1 else v, 2)
                        break

            except Exception:
                pass  # keep fallback values

            # ── Price history and returns ─────────────────────────────────────
            try:
                raw = yf.download(ticker, period="max", interval="1d",
                                  progress=False, auto_adjust=True)
                if isinstance(raw.columns, pd.MultiIndex):
                    raw.columns = raw.columns.get_level_values(0)
                if raw.empty or "Close" not in raw.columns:
                    raise ValueError("no data")

                close  = raw["Close"].ffill().dropna()
                curr_p = float(close.iloc[-1])

                if ".T" in ticker:
                    price_usd = curr_p * jpy_usd
                elif ".L" in ticker:
                    price_usd = (curr_p / 100 * gbp_usd) if curr_p > 100 else (curr_p * gbp_usd)
                elif ".DE" in ticker:
                    price_usd = curr_p * eur_usd
                else:
                    price_usd = curr_p

                def ann_ret(years):
                    days = int(years * 252)
                    if len(close) >= days:
                        return ((curr_p / float(close.iloc[-days])) ** (1/years) - 1) * 100
                    total_yr = len(close) / 252
                    if total_yr >= 0.5:
                        return ((curr_p / float(close.iloc[0])) ** (1/total_yr) - 1) * 100
                    return np.nan

                vol = float(close.pct_change().dropna().std() * np.sqrt(252) * 100)

                rows.append({
                    "Ticker":      ticker,
                    "Fund Name":   meta["Name"],
                    "Focus":       meta["Focus"],
                    "Price (USD)": round(price_usd, 2),
                    "ER %":        er,
                    "1Y Ret %":    round(ann_ret(1), 2),
                    "3Y Ann %":    round(ann_ret(3), 2),
                    "5Y Ann %":    round(ann_ret(5), 2),
                    "Vol %":       round(vol, 2),
                    "Yield %":     yield_,
                    "Live ER":     "✅" if er != _ER_FALLBACK.get(ticker) else "〰️",
                    "Live Yield":  "✅" if yield_ != _YIELD_FALLBACK.get(ticker) else "〰️",
                })

            except Exception:
                rows.append({
                    "Ticker": ticker, "Fund Name": meta["Name"],
                    "Focus": meta["Focus"], "Price (USD)": np.nan,
                    "ER %": er, "1Y Ret %": np.nan, "3Y Ann %": np.nan,
                    "5Y Ann %": np.nan, "Vol %": np.nan, "Yield %": yield_,
                    "Live ER": "〰️", "Live Yield": "〰️",
                })
        return pd.DataFrame(rows)

    with st.spinner("Fetching SG ETF data (ER & Yield live)..."):
        sg_df = fetch_sg_etf_data()

    # Filter
    focus_opts  = sg_df["Focus"].unique().tolist()
    sel_focus   = st.multiselect("Filter by focus", focus_opts,
                                 default=focus_opts, key="sg_etf_focus")
    sg_filtered = sg_df[sg_df["Focus"].isin(sel_focus)]

    # Colour functions
    def colour_ret(val):
        try:
            v = float(val)
            if   v >= 20: return "background-color:#1a7a3a;color:#ffffff;font-weight:700"
            elif v >= 10: return "background-color:#27ae60;color:#ffffff;font-weight:600"
            elif v >=  0: return "background-color:#a9dfbf;color:#145a32;font-weight:500"
            elif v >= -5: return "background-color:#f5b7b1;color:#7b241c;font-weight:500"
            else:         return "background-color:#c0392b;color:#ffffff;font-weight:700"
        except: return ""

    def colour_er(val):
        try:
            v = float(val)
            if   v <= 0.07: return "background-color:#27ae60;color:#ffffff;font-weight:700"
            elif v <= 0.15: return "background-color:#a9dfbf;color:#145a32"
            elif v <= 0.25: return "background-color:#fdebd0;color:#784212"
            else:           return "background-color:#f5b7b1;color:#7b241c"
        except: return ""

    def colour_vol(val):
        try:
            v = float(val)
            if   v <= 12: return "background-color:#a9dfbf;color:#145a32"
            elif v <= 18: return "background-color:#fdebd0;color:#784212"
            else:         return "background-color:#f5b7b1;color:#7b241c"
        except: return ""

    styler   = sg_filtered.set_index("Ticker").sort_values("ER %").style
    style_fn = styler.map if hasattr(styler, "map") else styler.applymap
    styled   = style_fn(colour_ret, subset=["1Y Ret %","3Y Ann %","5Y Ann %"])
    styled   = (styled.map if hasattr(styled,"map") else styled.applymap)(colour_er,  subset=["ER %"])
    styled   = (styled.map if hasattr(styled,"map") else styled.applymap)(colour_vol, subset=["Vol %"])
    st.dataframe(styled, width="stretch")

    st.caption("✅ = fetched live ·  〰️ = using fallback value")
    st.markdown("---")
    # ── END SG ETF DASHBOARD ──────────────────────────────────────────────────

    live_holdings = st.session_state.get("live_sectors_cache", None)

    if live_holdings is None:
        st.info("Run the scan first — holdings are fetched as part of the scan.")
    else:
        # Summary metrics
        total_stocks = sum(len(v.get("stocks", [])) for v in live_holdings.values())
        c1, c2, c3 = st.columns(3)
        c1.metric("Sectors tracked", len(live_holdings))
        c2.metric("Total unique stocks", total_stocks)
        c3.metric("Source", "")

        st.markdown("---")

        # One expander per sector, with a colour-coded header
        sector_perf = get_sector_performance()
        perf_map = {}
        if not sector_perf.empty and "Today %" in sector_perf.columns:
            perf_map = dict(zip(sector_perf["Sector"], sector_perf["Today %"]))

        for sector_name, sec_data in live_holdings.items():
            stocks  = sec_data.get("stocks", [])
            etf     = sec_data.get("etf", "")
            source  = sec_data.get("source", "–")
            pct     = perf_map.get(sector_name, None)

            if pct is not None:
                arrow  = "▲" if pct > 0 else "▼" if pct < 0 else "—"
                colour = "🟢" if pct > 0.1 else "🔴" if pct < -0.1 else "⚪"
                header = f"{colour} **{sector_name}** ({etf})  {arrow} {pct:+.2f}% today · {len(stocks)} stocks · via {source}"
            else:
                header = f"⚪ **{sector_name}** ({etf}) · {len(stocks)} stocks · via {source}"

            with st.expander(header, expanded=False):
                if not stocks:
                    st.warning("No holdings fetched for this sector.")
                    continue

                # Show as a clean dataframe with rank
                rows = [{"Rank": i+1, "Ticker": t} for i, t in enumerate(stocks)]
                df_stocks = pd.DataFrame(rows)

                # Split into 3 columns for compact display
                n = len(stocks)
                col_size = max(1, (n + 2) // 3)
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.dataframe(
                        df_stocks.iloc[:col_size],
                        width="stretch", hide_index=True
                    )
                with c2:
                    st.dataframe(
                        df_stocks.iloc[col_size:col_size*2],
                        width="stretch", hide_index=True
                    )
                with c3:
                    st.dataframe(
                        df_stocks.iloc[col_size*2:],
                        width="stretch", hide_index=True
                    )

    # Refresh button
    if st.button("🔄 Refresh ETF Holdings"):
        # Scoped cache clear — only nukes the ETF-holdings function, not the
        # full app cache. The previous `st.cache_data.clear()` wiped every
        # cached function (sector data, dividends, EPS, prices...) and the
        # subsequent rerun caused sidebar widgets without persistent keys
        # to fall back to their hardcoded defaults, which looked like the
        # user's settings had been reset.
        try:
            fetch_etf_holdings.clear()
        except Exception:
            pass
        st.rerun()

