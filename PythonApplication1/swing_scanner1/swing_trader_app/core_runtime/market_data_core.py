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
def get_sector_performance() -> pd.DataFrame:
    etf_list     = list(SECTOR_ETFS.values())
    sector_names = list(SECTOR_ETFS.keys())
    results      = []
    try:
        raw = yf.download(
            etf_list, period="5d", interval="1d",
            progress=False, auto_adjust=True, group_by="ticker"
        )
        if raw.empty:
            raise ValueError("Empty response from yfinance")

        for name, etf in zip(sector_names, etf_list):
            try:
                closes = _extract_closes(raw, etf, len(etf_list))
                if len(closes) < 2:
                    continue
                pct  = float((closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2] * 100)
                pct5 = float((closes.iloc[-1] - closes.iloc[0])  / closes.iloc[0]  * 100)
                results.append({
                    "Sector":  name, "ETF": etf,
                    "Today %": round(pct,  2),
                    "5d %":    round(pct5, 2),
                    "Price":   round(float(closes.iloc[-1]), 2),
                    "Status":  "🟢 GREEN" if pct > 0.1 else ("🔴 RED" if pct < -0.1 else "⚪ FLAT"),
                })
            except Exception:
                continue
    except Exception as e:
        st.warning(f"Sector fetch failed: {e}. Try: pip install --upgrade yfinance")

    if not results:
        return pd.DataFrame(columns=["Sector","ETF","Today %","5d %","Price","Status"])
    return pd.DataFrame(results).sort_values("Today %", ascending=False).reset_index(drop=True)


@st.cache_data(ttl=900)
def get_india_sector_performance() -> pd.DataFrame:
    """Fetch India NSE sector indices performance."""
    etf_list     = list(INDIA_SECTOR_ETFS.values())
    sector_names = list(INDIA_SECTOR_ETFS.keys())
    results      = []
    try:
        raw = yf.download(etf_list, period="5d", interval="1d",
                          progress=False, auto_adjust=True, group_by="ticker")
        if raw.empty:
            raise ValueError("Empty")
        for name, etf in zip(sector_names, etf_list):
            try:
                closes = _extract_closes(raw, etf, len(etf_list))
                if len(closes) < 2:
                    continue
                pct  = float((closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2] * 100)
                pct5 = float((closes.iloc[-1] - closes.iloc[0])  / closes.iloc[0]  * 100)
                results.append({
                    "Sector":  name, "ETF": etf,
                    "Today %": round(pct,  2),
                    "5d %":    round(pct5, 2),
                    "Price":   round(float(closes.iloc[-1]), 2),
                    "Status":  "🟢 GREEN" if pct > 0.1 else ("🔴 RED" if pct < -0.1 else "⚪ FLAT"),
                })
            except Exception:
                continue
    except Exception as e:
        st.warning(f"India sector fetch failed: {e}")
    if not results:
        return pd.DataFrame(columns=["Sector","ETF","Today %","5d %","Price","Status"])
    return pd.DataFrame(results).sort_values("Today %", ascending=False).reset_index(drop=True)


@st.cache_data(ttl=900)
def get_sg_sector_performance() -> pd.DataFrame:
    """Compute SGX sector heatmap by averaging stock returns within each sector group."""
    all_tickers = list({t for tickers in SG_SECTOR_GROUPS.values() for t in tickers})
    results     = []
    try:
        raw = yf.download(all_tickers, period="5d", interval="1d",
                          progress=False, auto_adjust=True, group_by="ticker")
        for sector_name, members in SG_SECTOR_GROUPS.items():
            pcts, pcts5, prices = [], [], []
            for t in members:
                try:
                    closes = _extract_closes(raw, t, len(all_tickers))
                    if len(closes) < 2:
                        continue
                    pcts.append(float((closes.iloc[-1]-closes.iloc[-2])/closes.iloc[-2]*100))
                    pcts5.append(float((closes.iloc[-1]-closes.iloc[0])/closes.iloc[0]*100))
                    prices.append(float(closes.iloc[-1]))
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
    except Exception as e:
        st.warning(f"SGX sector fetch failed: {e}")
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
