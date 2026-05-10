"""Extracted runtime section from app_runtime.py lines 1050-1228.
Loaded by app_runtime with exec(..., globals()) to preserve the original single-file behavior.
"""

# ─────────────────────────────────────────────────────────────────────────────
# MARKET REGIME  — v5 exact logic
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=1800)
def get_market_regime():
    try:
        spy_raw = yf.download("SPY", period="3mo", interval="1d",
                              progress=False, auto_adjust=True)
        vix_raw = yf.download("^VIX", period="5d", interval="1d",
                              progress=False, auto_adjust=True)

        # Flatten MultiIndex if present (yfinance ≥0.2.x returns MultiIndex)
        for df in (spy_raw, vix_raw):
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

        if spy_raw.empty or "Close" not in spy_raw.columns:
            raise ValueError("SPY data empty or missing Close column")
        if vix_raw.empty or "Close" not in vix_raw.columns:
            raise ValueError("VIX data empty or missing Close column")

        spy_close = spy_raw["Close"].ffill().dropna()
        vix_close = vix_raw["Close"].ffill().dropna()

        if len(spy_close) < 50:
            raise ValueError(f"Insufficient SPY history: {len(spy_close)} bars")

        spy_ema20 = float(ta.trend.ema_indicator(spy_close, window=20).iloc[-1])
        spy_ema50 = float(ta.trend.ema_indicator(spy_close, window=50).iloc[-1])
        spy_now   = float(spy_close.iloc[-1])
        vix_now   = float(vix_close.iloc[-1])

        if spy_now > spy_ema20 and vix_now < 20:
            regime = "BULL"
        elif spy_now < spy_ema50 or vix_now > 25:
            regime = "BEAR"
        else:
            regime = "CAUTION"

        return {"regime": regime, "spy": round(spy_now, 2),
                "spy_ema20": round(spy_ema20, 2),
                "spy_ema50": round(spy_ema50, 2),
                "vix": round(vix_now, 2)}

    except Exception as e:
        # Surface the real error so user can diagnose
        st.warning(f"⚠️ Market regime fetch failed: {e}. Showing UNKNOWN. Try `pip install --upgrade yfinance`.")
        return {"regime": "UNKNOWN", "spy": 0,
                "spy_ema20": 0, "spy_ema50": 0, "vix": 0}


# ─────────────────────────────────────────────────────────────────────────────
# SECTOR PERFORMANCE  — v7 robust MultiIndex handling
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=900)
@st.cache_data(ttl=600, show_spinner=False)          # ← was missing — caused rate-limit hammering on Cloud
def get_sector_performance() -> pd.DataFrame:
    """Fetch US sector ETF performance with Cloud-safe fallback chain.

    Cloud issues fixed (v15.6):
    1. Added @st.cache_data(ttl=600) — was missing, causing every rerender
       to hit Yahoo, quickly exhausting the shared Streamlit Cloud IP quota.
    2. Fallback to individual Ticker.fast_info when yf.download() returns
       all-zero prices (happens when Cloud IP is rate-limited by Yahoo).
    3. Market-closed detection — when all bars are from prior session,
       returns data with a 'Market closed' note instead of showing warning.
    """
    import datetime as _dt

    etf_list     = list(SECTOR_ETFS.values())
    sector_names = list(SECTOR_ETFS.keys())
    results      = []

    def _pct_from_closes(closes):
        if len(closes) < 2:
            return None, None
        pct  = float((closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2] * 100)
        pct5 = float((closes.iloc[-1] - closes.iloc[0])  / closes.iloc[0]  * 100)
        return round(pct, 2), round(pct5, 2)

    # ── Attempt 1: yf.download batch (fast, but fails on Cloud rate limits) ──
    raw = None
    try:
        raw = yf.download(
            etf_list, period="5d", interval="1d",
            progress=False, auto_adjust=True, group_by="ticker",
            threads=False,   # disable threads — reduces Cloud connection errors
        )
        if raw.empty:
            raw = None
    except Exception:
        raw = None

    # Check if batch download gave us real data (non-zero prices)
    _batch_ok = False
    if raw is not None and not raw.empty:
        try:
            _test_closes = _extract_closes(raw, etf_list[0], len(etf_list))
            _batch_ok = len(_test_closes) >= 2 and float(_test_closes.iloc[-1]) > 0
        except Exception:
            _batch_ok = False

    if _batch_ok:
        for name, etf in zip(sector_names, etf_list):
            try:
                closes = _extract_closes(raw, etf, len(etf_list))
                pct, pct5 = _pct_from_closes(closes)
                if pct is None:
                    continue
                results.append({
                    "Sector":  name, "ETF": etf,
                    "Today %": pct, "5d %": pct5,
                    "Price":   round(float(closes.iloc[-1]), 2),
                    "Status":  "🟢 GREEN" if pct > 0.1 else ("🔴 RED" if pct < -0.1 else "⚪ FLAT"),
                })
            except Exception:
                continue

    # ── Attempt 2: individual Ticker.fast_info fallback (Cloud-safe) ─────────
    # Fires when batch download returned empty or all-zero prices.
    # fast_info is a lightweight single-ticker call that bypasses the batch
    # download endpoint — much less likely to be rate-limited.
    if not results:
        for name, etf in zip(sector_names, etf_list):
            try:
                import contextlib as _cl, io as _io
                with _cl.redirect_stderr(_io.StringIO()), _cl.redirect_stdout(_io.StringIO()):
                    _fi = yf.Ticker(etf).fast_info
                _price      = float(getattr(_fi, "last_price",         0) or 0)
                _prev_close = float(getattr(_fi, "previous_close",     0) or 0)
                _open       = float(getattr(_fi, "open",               0) or 0)
                if _price <= 0:
                    continue
                if _prev_close > 0:
                    pct = round((_price - _prev_close) / _prev_close * 100, 2)
                elif _open > 0:
                    pct = round((_price - _open) / _open * 100, 2)
                else:
                    pct = 0.0
                results.append({
                    "Sector":  name, "ETF": etf,
                    "Today %": pct, "5d %": pct,
                    "Price":   round(_price, 2),
                    "Status":  "🟢 GREEN" if pct > 0.1 else ("🔴 RED" if pct < -0.1 else "⚪ FLAT"),
                })
            except Exception:
                continue

    if not results:
        return pd.DataFrame(columns=["Sector","ETF","Today %","5d %","Price","Status"])

    df = pd.DataFrame(results).sort_values("Today %", ascending=False).reset_index(drop=True)

    # ── Market-closed detection ───────────────────────────────────────────────
    # When the market is closed, all ETFs return ~0% change.
    # This is NORMAL — suppress the "All sectors flat" warning in app_runtime
    # by adding a metadata column the app can check.
    all_flat = df["Today %"].abs().max() < 0.05
    now_utc  = _dt.datetime.utcnow()
    # NYSE hours: Mon-Fri 13:30–20:00 UTC
    market_open = (now_utc.weekday() < 5 and
                   _dt.time(13, 30) <= now_utc.time() <= _dt.time(20, 0))
    df["_market_closed"] = all_flat and not market_open

    return df


@st.cache_data(ttl=900, show_spinner=False)
def get_india_sector_performance() -> pd.DataFrame:
    """Fetch India NSE sector indices performance with Cloud-safe fallback."""
    etf_list     = list(INDIA_SECTOR_ETFS.values())
    sector_names = list(INDIA_SECTOR_ETFS.keys())
    results      = []
    raw = None
    try:
        raw = yf.download(etf_list, period="5d", interval="1d",
                          progress=False, auto_adjust=True, group_by="ticker",
                          threads=False)
        if raw.empty:
            raw = None
    except Exception:
        raw = None

    if raw is not None and not raw.empty:
        for name, etf in zip(sector_names, etf_list):
            try:
                closes = _extract_closes(raw, etf, len(etf_list))
                if len(closes) < 2:
                    continue
                pct  = float((closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2] * 100)
                pct5 = float((closes.iloc[-1] - closes.iloc[0])  / closes.iloc[0]  * 100)
                results.append({
                    "Sector": name, "ETF": etf,
                    "Today %": round(pct, 2), "5d %": round(pct5, 2),
                    "Price": round(float(closes.iloc[-1]), 2),
                    "Status": "🟢 GREEN" if pct > 0.1 else ("🔴 RED" if pct < -0.1 else "⚪ FLAT"),
                })
            except Exception:
                continue

    # fast_info fallback for Cloud rate-limit resilience
    if not results:
        for name, etf in zip(sector_names, etf_list):
            try:
                import contextlib as _cl, io as _io
                with _cl.redirect_stderr(_io.StringIO()), _cl.redirect_stdout(_io.StringIO()):
                    _fi = yf.Ticker(etf).fast_info
                _price = float(getattr(_fi, "last_price",     0) or 0)
                _prev  = float(getattr(_fi, "previous_close", 0) or 0)
                if _price <= 0:
                    continue
                pct = round((_price - _prev) / _prev * 100, 2) if _prev > 0 else 0.0
                results.append({
                    "Sector": name, "ETF": etf,
                    "Today %": pct, "5d %": pct,
                    "Price": round(_price, 2),
                    "Status": "🟢 GREEN" if pct > 0.1 else ("🔴 RED" if pct < -0.1 else "⚪ FLAT"),
                })
            except Exception:
                continue

    if not results:
        return pd.DataFrame(columns=["Sector","ETF","Today %","5d %","Price","Status"])
    return pd.DataFrame(results).sort_values("Today %", ascending=False).reset_index(drop=True)


@st.cache_data(ttl=900, show_spinner=False)
def get_sg_sector_performance() -> pd.DataFrame:
    """Compute SGX sector heatmap with Cloud-safe fallback."""
    all_tickers = list({t for tickers in SG_SECTOR_GROUPS.values() for t in tickers})
    results     = []
    raw = None
    try:
        raw = yf.download(all_tickers, period="5d", interval="1d",
                          progress=False, auto_adjust=True, group_by="ticker",
                          threads=False)
    except Exception:
        raw = pd.DataFrame()

    for sector_name, members in SG_SECTOR_GROUPS.items():
        pcts, pcts5, prices = [], [], []
        for t in members:
            try:
                if raw is not None and not raw.empty:
                    closes = _extract_closes(raw, t, len(all_tickers))
                    if len(closes) >= 2 and float(closes.iloc[-1]) > 0:
                        pcts.append(float((closes.iloc[-1]-closes.iloc[-2])/closes.iloc[-2]*100))
                        pcts5.append(float((closes.iloc[-1]-closes.iloc[0])/closes.iloc[0]*100))
                        prices.append(float(closes.iloc[-1]))
                        continue
                # fast_info fallback per ticker
                import contextlib as _cl, io as _io
                with _cl.redirect_stderr(_io.StringIO()), _cl.redirect_stdout(_io.StringIO()):
                    _fi = yf.Ticker(t).fast_info
                _p   = float(getattr(_fi, "last_price",     0) or 0)
                _prev = float(getattr(_fi, "previous_close", 0) or 0)
                if _p > 0 and _prev > 0:
                    pcts.append(round((_p - _prev) / _prev * 100, 2))
                    pcts5.append(pcts[-1])
                    prices.append(_p)
            except Exception:
                continue
        if pcts:
            pct  = round(float(np.mean(pcts)),  2)
            pct5 = round(float(np.mean(pcts5)), 2)
            results.append({
                "Sector":  sector_name,
                "ETF":     "/".join(members[:2]),
                "Today %": pct, "5d %": pct5,
                "Price":   round(float(np.mean(prices)), 2),
                "Status":  "🟢 GREEN" if pct > 0.1 else ("🔴 RED" if pct < -0.1 else "⚪ FLAT"),
            })
    if not results:
        return pd.DataFrame(columns=["Sector","ETF","Today %","5d %","Price","Status"])
    return pd.DataFrame(results).sort_values("Today %", ascending=False).reset_index(drop=True)
@st.cache_data(ttl=3600)
def get_earnings_flag(ticker):
    try:
        info = yf.Ticker(ticker).calendar
        if info is None or info.empty:
            return False, "–"
        ed = info.loc["Earnings Date"].iloc[0] \
             if "Earnings Date" in info.index else info.iloc[0, 0]
        if pd.isnull(ed):
            return False, "–"
        days_out = (pd.Timestamp(ed).date() - datetime.today().date()).days
        return 0 <= days_out <= 7, str(pd.Timestamp(ed).date())
    except Exception:
        return False, "–"


# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL COMPUTATION  — exact v5 compute_all_signals
# accepts close/high/low/vol Series (not DataFrame)
