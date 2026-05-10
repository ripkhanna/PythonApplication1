"""Extracted runtime section from app_runtime.py lines 1964-2374.
Loaded by app_runtime with exec(..., globals()) to preserve the original single-file behavior.
"""

def _score_stocks_batch(symbols: list) -> dict:
    """
    ONE batch download → swing score for every symbol.
    Returns {sym: swing_score}
    """
    scored = {}
    if not symbols:
        return scored
    try:
        batch = yf.download(
            symbols, period="1mo", interval="1d",
            progress=False, group_by="ticker",
            threads=True, auto_adjust=True
        )
        for sym in symbols:
            try:
                c  = _extract_closes(batch, sym, len(symbols))
                if isinstance(batch.columns, pd.MultiIndex):
                    v  = batch.xs(sym, axis=1, level=1)["Volume"].ffill().dropna() \
                         if sym in batch.columns.get_level_values(1) \
                         else batch[sym]["Volume"].ffill().dropna()
                    h  = batch.xs(sym, axis=1, level=1)["High"].ffill().dropna() \
                         if sym in batch.columns.get_level_values(1) \
                         else batch[sym]["High"].ffill().dropna()
                    lo = batch.xs(sym, axis=1, level=1)["Low"].ffill().dropna() \
                         if sym in batch.columns.get_level_values(1) \
                         else batch[sym]["Low"].ffill().dropna()
                else:
                    v  = batch["Volume"].squeeze().ffill().dropna()
                    h  = batch["High"].squeeze().ffill().dropna()
                    lo = batch["Low"].squeeze().ffill().dropna()

                if len(c) < 10:
                    continue
                price      = float(c.iloc[-1])
                avg_vol    = float(v.mean())
                dollar_vol = price * avg_vol
                if price < 3 or dollar_vol < 5_000_000:
                    continue
                atr_pct = float(
                    ta.volatility.average_true_range(h, lo, c, window=14).iloc[-1]
                ) / price * 100
                atr_bonus = 1.5 if 2 <= atr_pct <= 12 else (0.7 if atr_pct < 2 else 0.4)
                scored[sym] = dollar_vol * atr_bonus
            except Exception:
                continue
    except Exception:
        pass
    return scored


@st.cache_data(ttl=21600)   # 6-hour cache
def fetch_sector_constituents(target_per_sector: int = 25) -> dict:
    sectors  = {}
    etf_items = list(SECTOR_ETFS.items())
    status   = st.empty()

    # ── Step 1: holdings via FinanceDatabase ──────────────────────────────────
    if _fd_available:
        status.text("📚 Loading ETF holdings...")
        try:
            etfs_db     = fd.ETFs()
            equities_db = fd.Equities()
            for sector_name, etf_ticker in etf_items:
                try:
                    etf_data = etfs_db.select(symbol=etf_ticker)
                    stocks   = []
                    if not etf_data.empty:
                        for col in ["holdings", "top_holdings", "constituents"]:
                            if col in etf_data.columns:
                                rv = etf_data[col].iloc[0]
                                if isinstance(rv, list):
                                    stocks = [str(s).upper().strip() for s in rv
                                              if str(s).strip().replace("-","").isalpha()
                                              and 1 <= len(str(s).strip()) <= 6]
                                elif isinstance(rv, str) and rv:
                                    stocks = [s.upper().strip() for s in rv.split(",")
                                              if s.strip().replace("-","").isalpha()
                                              and 1 <= len(s.strip()) <= 6]
                                if stocks:
                                    break
                        if not stocks and "category" in etf_data.columns:
                            cat = str(etf_data["category"].iloc[0])
                            if cat:
                                cat_df = equities_db.select(category=cat)
                                if not cat_df.empty:
                                    stocks = [s for s in cat_df.index.tolist()
                                              if str(s).replace("-","").isalpha()
                                              and 1 <= len(str(s)) <= 6]
                    if stocks:
                        sectors[sector_name] = {
                            "etf": etf_ticker,
                            "stocks": [s for s in stocks if s != etf_ticker][: target_per_sector * 2],
                            "source": "financedatabase",
                        }
                except Exception:
                    pass
        except Exception:
            pass

    # ── Step 2: yfinance fallback for any missing sector ──────────────────────
    for sector_name, etf_ticker in etf_items:
        if sectors.get(sector_name, {}).get("stocks"):
            continue
        status.text(f"📡 Fetching {etf_ticker} holdings ...")
        try:
            tkr    = yf.Ticker(etf_ticker)
            stocks = []
            for attr in ("portfolio_holdings", "equity_holdings", "top_holdings"):
                try:
                    df_h = getattr(tkr.funds_data, attr)
                    if df_h is None or df_h.empty:
                        continue
                    sym_col = next((c for c in ["Symbol","symbol","Ticker","ticker"]
                                    if c in df_h.columns), None)
                    raw_syms = df_h[sym_col].dropna().astype(str).tolist() if sym_col \
                               else [str(x) for x in df_h.index.tolist()]
                    stocks = [s.strip().upper() for s in raw_syms
                              if s.strip().replace("-","").isalpha()
                              and 1 <= len(s.strip()) <= 6
                              and s.strip().upper() != etf_ticker]
                    if stocks:
                        break
                except Exception:
                    continue
            sectors[sector_name] = {
                "etf": etf_ticker,
                "stocks": stocks[: target_per_sector * 2],
                "source": "",
            }
        except Exception:
            sectors[sector_name] = {"etf": etf_ticker, "stocks": [], "source": "none"}

    # ── Step 3: score ALL stocks in ONE batch download ────────────────────────
    all_syms = list(dict.fromkeys(
        s for d in sectors.values() for s in d.get("stocks", [])
    ))
    status.text(f"📊 Scoring {len(all_syms)} stocks for swing quality...")
    scored_map = _score_stocks_batch(all_syms)

    # ── Step 4: rank each sector by swing score ───────────────────────────────
    out = {}
    for sector_name, data in sectors.items():
        raw  = data.get("stocks", [])
        ranked = sorted(raw, key=lambda s: scored_map.get(s, 0), reverse=True)
        best   = ranked[:target_per_sector]
        out[sector_name] = {**data, "stocks": best, "count": len(best)}

    status.empty()
    return out


# ─────────────────────────────────────────────────────────────────────────────
# LIVE MARKET UNIVERSE — used by Operator Activity / scan source
# ─────────────────────────────────────────────────────────────────────────────
def _clean_symbol(sym: str, suffix: str = "") -> str:
    """Normalise symbols for yfinance and drop obvious non-equity junk."""
    if sym is None:
        return ""
    s = str(sym).strip().upper()
    if not s or s in ("NAN", "NONE", "-", "—"):
        return ""
    s = s.replace(" ", "")
    # yfinance uses '-' for US class shares (BRK-B), not '.'
    if suffix == "" and "." in s and not s.endswith((".SI", ".NS")):
        s = s.replace(".", "-")
    # Remove warrants/rights/preferreds that often break scans.
    bad_fragments = ("-W", "-WT", "-WS", "-R", "-U", "^", "/")
    if any(x in s for x in bad_fragments):
        return ""
    if suffix and not s.endswith(suffix):
        s = f"{s}{suffix}"
    return s


def _unique_keep_order(items):
    out, seen = [], set()
    for item in items:
        if item and item not in seen:
            out.append(item)
            seen.add(item)
    return out


@st.cache_data(ttl=30 * 60, show_spinner=False)
def fetch_yahoo_market_movers(max_per_screener: int = 250) -> list:
    """
    Fetch a broader LIVE Yahoo universe.

    Why count may still be < Max live stocks:
    - Max live stocks is only a cap, not a guaranteed count.
    - Yahoo screeners return only the names currently available in each bucket.
    - Duplicate symbols across screeners are removed before scanning.

    This function uses two Yahoo paths:
      1) yfinance.screen(...) when available
      2) Yahoo Finance screener endpoint as a fallback / expansion path

    The final scan step later merges these live tickers with the full existing
    curated ticker list, so UUUU, APP, etc. remain included even if Yahoo does
    not return them as current movers.
    """
    tickers = []

    # A broad set of Yahoo predefined screeners. Some names may be unsupported
    # depending on the yfinance/Yahoo version; failures are skipped safely.
    screen_names = (
        "most_actives", "day_gainers", "day_losers",
        "undervalued_growth_stocks", "growth_technology_stocks",
        "aggressive_small_caps", "small_cap_gainers", "most_shorted_stocks",
        "portfolio_anchors", "undervalued_large_caps",
        "solid_large_growth_funds", "high_yield_bond", "top_mutual_funds",
    )

    # Path 1: yfinance's built-in screener wrapper.
    try:
        if hasattr(yf, "screen"):
            for scr in screen_names:
                try:
                    res = yf.screen(scr, count=max_per_screener)
                    quotes = res.get("quotes", []) if isinstance(res, dict) else []
                    for q in quotes:
                        sym = _clean_symbol(q.get("symbol", ""))
                        if sym:
                            tickers.append(sym)
                except Exception:
                    continue
    except Exception:
        pass

    # Path 2: Yahoo Finance public screener endpoint with pagination. This often
    # returns more names than yfinance.screen alone.
    try:
        import requests
        url = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
        headers = {"User-Agent": "Mozilla/5.0"}
        per_page = min(max(int(max_per_screener), 25), 250)
        for scr in screen_names:
            for start in range(0, max_per_screener, per_page):
                try:
                    params = {
                        "scrIds": scr,
                        "count": per_page,
                        "start": start,
                        "formatted": "false",
                        "lang": "en-US",
                        "region": "US",
                    }
                    r = requests.get(url, params=params, headers=headers, timeout=12)
                    if not r.ok:
                        break
                    result = (r.json().get("finance", {})
                                      .get("result", [{}])[0])
                    quotes = result.get("quotes", []) or []
                    if not quotes:
                        break
                    for q in quotes:
                        sym = _clean_symbol(q.get("symbol", ""))
                        if sym:
                            tickers.append(sym)
                    # Stop early when Yahoo returned fewer than requested.
                    if len(quotes) < per_page:
                        break
                except Exception:
                    break
    except Exception:
        pass

    return _unique_keep_order(tickers)


@st.cache_data(ttl=12 * 60 * 60, show_spinner=False)
def fetch_us_index_universe(max_symbols: int = 450) -> list:
    """Fetch current US index constituents from public index tables."""
    tickers = []
    sources = [
        ("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", ["Symbol", "Ticker symbol"]),
        ("https://en.wikipedia.org/wiki/Nasdaq-100", ["Ticker", "Symbol"]),
        ("https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average", ["Symbol", "Ticker"]),
    ]
    for url, cols in sources:
        try:
            for tbl in pd.read_html(url):
                col = next((c for c in cols if c in tbl.columns), None)
                if not col:
                    continue
                vals = [_clean_symbol(x) for x in tbl[col].dropna().astype(str).tolist()]
                tickers.extend([v for v in vals if v])
                break
        except Exception:
            continue
    return _unique_keep_order(tickers)[:max_symbols]


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def fetch_sgx_market_universe(max_symbols: int = 180) -> list:
    """
    Fetch Singapore-listed names from live/public market sources.
    Primary source: SGX securities API. Fallback: current STI constituents table.
    """
    tickers = []

    # SGX public securities endpoint changes occasionally; keep it best-effort.
    try:
        import requests
        url = "https://api2.sgx.com/securities/v1.1"
        params = {"excludetypes": "bonds", "params": "nc,cn,code"}
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, params=params, headers=headers, timeout=12)
        if r.ok:
            data = r.json()
            rows = data.get("data", data if isinstance(data, list) else [])
            for row in rows:
                if isinstance(row, dict):
                    code = row.get("code") or row.get("nc") or row.get("symbol") or row.get("ticker")
                elif isinstance(row, (list, tuple)) and row:
                    code = row[0]
                else:
                    code = None
                sym = _clean_symbol(code, ".SI")
                if sym:
                    tickers.append(sym)
    except Exception:
        pass

    # Fallback to STI constituents if SGX endpoint is unavailable.
    if len(tickers) < 20:
        try:
            for tbl in pd.read_html("https://en.wikipedia.org/wiki/Straits_Times_Index"):
                possible_cols = [c for c in tbl.columns if str(c).lower() in ("stock symbol", "symbol", "ticker")]
                if not possible_cols:
                    continue
                vals = [_clean_symbol(x, ".SI") for x in tbl[possible_cols[0]].dropna().astype(str).tolist()]
                tickers.extend([v for v in vals if v])
                break
        except Exception:
            pass

    # Final cloud-safe fallback. On Streamlit Cloud the SGX endpoint can be
    # blocked/empty and Wikipedia parsing can also fail. Do not return an empty
    # live universe in that case; merge the curated SGX fallback so scans still
    # cover a useful number of Singapore names.
    try:
        fallback = globals().get("SGX_LIQUID_FALLBACK_TICKERS", []) or globals().get("SG_TICKERS", [])
        if len(tickers) < 60 and fallback:
            tickers.extend([_clean_symbol(x, ".SI") for x in fallback])
    except Exception:
        pass

    return _unique_keep_order(tickers)[:max_symbols]


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def fetch_nse_market_universe(max_symbols: int = 220) -> list:
    """Fetch current NSE index constituents from NSE's live index API."""
    tickers = []
    indices = ["NIFTY 50", "NIFTY NEXT 50", "NIFTY MIDCAP 50", "NIFTY SMALLCAP 50"]
    try:
        import requests
        sess = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "application/json,text/plain,*/*",
            "Referer": "https://www.nseindia.com/market-data/live-equity-market",
        }
        # Warm the NSE session/cookies.
        try:
            sess.get("https://www.nseindia.com", headers=headers, timeout=10)
        except Exception:
            pass
        for idx in indices:
            try:
                url = "https://www.nseindia.com/api/equity-stockIndices"
                r = sess.get(url, params={"index": idx}, headers=headers, timeout=12)
                if not r.ok:
                    continue
                data = r.json().get("data", [])
                for row in data:
                    sym = row.get("symbol")
                    if sym and sym not in ("NIFTY 50", "NIFTY NEXT 50"):
                        t = _clean_symbol(sym, ".NS")
                        if t:
                            tickers.append(t)
            except Exception:
                continue
    except Exception:
        pass
    return _unique_keep_order(tickers)[:max_symbols]



@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def fetch_hk_market_universe(max_symbols: int = 160) -> list:
    """Return Hong Kong watchlist. Yahoo HK live universe is unreliable, so use curated liquid .HK names."""
    try:
        base = globals().get("HK_TICKERS", [])
        # Normalize numeric HK tickers to 4 digits for Yahoo, e.g. 700.HK -> 0700.HK.
        out = []
        for t in base:
            s = str(t or "").strip().upper()
            if not s:
                continue
            if s.endswith(".HK"):
                code = s[:-3]
                if code.isdigit():
                    s = f"{int(code):04d}.HK"
            out.append(s)
        return _unique_keep_order(out)[:max_symbols]
    except Exception:
        return []


# ─────────────────────────────────────────────────────────────────────────────
# v14 UNIVERSE UPGRADES
# Six new stock-sourcing methods that surface higher-quality swing candidates:
#
#   1. fetch_52w_high_breakouts   — stocks making new 52w highs on heavy volume
#   2. fetch_earnings_universe    — upcoming earnings + recent-beat candidates
#   3. fetch_finviz_screen        — pre-filtered by technical criteria (optional dep)
#   4. get_top_sector_etfs        — sector rotation: scan only top-N sectors
#   5. fetch_unusual_options_univ — stocks with unusual call volume (US only)
#   6. fetch_premarket_gappers    — pre-market gap ≥3% (run before 09:30 ET)
#
# All functions are @st.cache_data with appropriate TTLs and fail silently
# so the scanner degrades gracefully if any source is unavailable.
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60 * 60, show_spinner=False)
def fetch_52w_high_breakouts(universe: list, min_vol_ratio: float = 1.5) -> list:
    """
    Find tickers making new 52-week highs today on above-average volume.

    Why this matters: stocks at new 52w highs on volume are entering price
    discovery — there is no overhead resistance and institutions are chasing.
    These often run an additional 10–30% in following weeks.

    Returns list of tickers (subset of universe).
    """
    breakouts = []
    if not universe:
        return breakouts
    try:
        batch = yf.download(
            universe, period="1y", interval="1d",
            progress=False, group_by="ticker",
            threads=True, auto_adjust=True,
        )
        for sym in universe:
            try:
                c = _extract_closes(batch, sym, len(universe))
                if len(c) < 50:
                    continue
                # High series
                if isinstance(batch.columns, pd.MultiIndex):
                    h_s = batch.xs(sym, axis=1, level=1)["High"].ffill().dropna() \
                          if sym in batch.columns.get_level_values(1) else None
                    v_s = batch.xs(sym, axis=1, level=1)["Volume"].ffill().dropna() \
                          if sym in batch.columns.get_level_values(1) else None
                else:
                    h_s = batch["High"].squeeze().ffill().dropna()
                    v_s = batch["Volume"].squeeze().ffill().dropna()
                if h_s is None or v_s is None or len(h_s) < 50:
                    continue
                today_close = float(c.iloc[-1])
                year_high   = float(h_s.iloc[:-1].max())      # prior 252d high
                vol_20_avg  = float(v_s.tail(21).iloc[:-1].mean()) or 1.0
                vol_today   = float(v_s.iloc[-1])
                vol_ratio   = vol_today / vol_20_avg
                # Breakout: today's close at or above prior 52w high on heavy vol
                if today_close >= year_high * 0.995 and vol_ratio >= min_vol_ratio:
                    breakouts.append(sym)
            except Exception:
                continue
    except Exception:
        pass
    return breakouts


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def fetch_earnings_universe(universe: list, window_ahead: int = 7) -> dict:
    """
    Identify stocks with upcoming earnings (PEAD pre-loading) and recent beats.

    Returns:
        {
          "upcoming": [tickers reporting earnings in next window_ahead days],
          "recent_beat": [tickers that beat/gapped up 0–3 days ago],
        }

    Both lists can be merged into the scan universe so PEAD signals fire.
    Caps at 300 tickers to stay within free-tier rate limits.
    """
    from datetime import datetime, timedelta
    upcoming, recent_beat = [], []
    today = datetime.now().date()

    for sym in list(universe)[:300]:
        try:
            tkr = yf.Ticker(sym)
            cal = tkr.calendar
            if cal is None or (hasattr(cal, "empty") and cal.empty):
                continue
            # Support both DataFrame (old yfinance) and dict (new yfinance) formats
            if isinstance(cal, dict):
                earn_raw = cal.get("Earnings Date", [])
                earn_dates = [pd.Timestamp(d).date() for d in (earn_raw if isinstance(earn_raw, list) else [earn_raw]) if d]
            else:
                earn_dates = []
                for col in ["Earnings Date", "earnings_date"]:
                    if col in cal.columns:
                        earn_dates = [pd.Timestamp(d).date() for d in cal[col].dropna()]
                        break
            for ed in earn_dates:
                delta = (ed - today).days
                if 0 <= delta <= window_ahead:
                    upcoming.append(sym)
                elif -3 <= delta < 0:
                    # Check if it gapped ≥4% (beat signature)
                    hist = tkr.history(period="5d", auto_adjust=True)
                    if not hist.empty and len(hist) >= 2:
                        gap = (float(hist["Close"].iloc[-1]) - float(hist["Close"].iloc[0])) \
                              / max(float(hist["Close"].iloc[0]), 0.01)
                        if gap >= 0.04:
                            recent_beat.append(sym)
        except Exception:
            continue

    return {
        "upcoming":    list(dict.fromkeys(upcoming)),
        "recent_beat": list(dict.fromkeys(recent_beat)),
    }


@st.cache_data(ttl=4 * 60 * 60, show_spinner=False)
def get_top_sector_etfs(n: int = 3) -> list:
    """
    Rank the 11 US sector ETFs by 1-month price return and return the top N.

    Use this to bias the scan toward only the strongest sectors — trading
    sector leaders vs laggards is one of the highest-edge filters in
    professional swing trading.

    Returns list of ETF tickers (e.g. ["XLK", "XLY", "XLC"]).
    """
    SECTOR_ETF_UNIVERSE = [
        "XLK", "XLV", "XLF", "XLE", "XLI",
        "XLB", "XLP", "XLU", "XLY", "XLRE", "XLC",
    ]
    try:
        data = yf.download(
            SECTOR_ETF_UNIVERSE, period="2mo", interval="1d",
            progress=False, auto_adjust=True,
        )
        closes = data["Close"] if "Close" in data.columns else data
        returns = {}
        for etf in SECTOR_ETF_UNIVERSE:
            col = etf if etf in closes.columns else None
            if col is None:
                continue
            s = closes[col].dropna()
            if len(s) >= 21:
                ret_1m = (float(s.iloc[-1]) - float(s.iloc[-21])) / max(float(s.iloc[-21]), 0.01)
                returns[etf] = ret_1m
        ranked = sorted(returns.items(), key=lambda x: -x[1])
        return [etf for etf, _ in ranked[:n]]
    except Exception:
        return SECTOR_ETF_UNIVERSE[:n]


@st.cache_data(ttl=2 * 60 * 60, show_spinner=False)
def fetch_finviz_screen(preset: str = "swing_breakout") -> list:
    """
    Use finvizfinance to return technically pre-screened US tickers.

    No API key required. Requires: pip install finvizfinance

    Presets:
      "swing_breakout" — above SMA20/50, near 52w high, volume spike
      "swing_pullback" — above SMA50, pulled back to SMA20, RSI 35–55
      "swing_squeeze"  — high short interest + positive momentum

    Falls back to [] silently if finvizfinance is not installed.
    """
    PRESETS = {
        "swing_breakout": {
            "Price":                          "Over $5",
            "Average Volume":                 "Over 500K",
            "20-Day Simple Moving Average":   "Price above SMA20",
            "50-Day Simple Moving Average":   "Price above SMA50",
            "Change":                         "Up",
            "Volume":                         "Over 1M",
            "RSI (14)":                       "Not Overbought (>70)",
            "New High":                       "New 52-Week High",
        },
        "swing_pullback": {
            "Price":                          "Over $5",
            "Average Volume":                 "Over 300K",
            "50-Day Simple Moving Average":   "Price above SMA50",
            "20-Day Simple Moving Average":   "Price near SMA20 (±2%)",
            "RSI (14)":                       "Oversold (30-40)",
        },
        "swing_squeeze": {
            "Price":                          "Over $5",
            "Average Volume":                 "Over 500K",
            "Short Float":                    "Over 15%",
            "Change":                         "Up",
            "Volume":                         "Over 1M",
        },
    }
    try:
        from finvizfinance.screener.overview import Overview
        screen = Overview()
        filters = PRESETS.get(preset, PRESETS["swing_breakout"])
        screen.set_filter(filters_dict=filters)
        df = screen.screener_view()
        if df is None or df.empty:
            return []
        col = next((c for c in ["Ticker", "ticker", "Symbol"] if c in df.columns), None)
        return [_clean_symbol(str(t)) for t in df[col].dropna().tolist()] if col else []
    except ImportError:
        return []     # finvizfinance not installed — silent skip
    except Exception:
        return []


@st.cache_data(ttl=30 * 60, show_spinner=False)
def fetch_unusual_options_universe(
    universe: list,
    min_oi_ratio: float = 3.0,
    max_scan: int = 150,
) -> list:
    """
    Return US tickers with unusual near-money CALL volume (volume/OI ≥ min_oi_ratio).

    Options unusual activity is a leading indicator — it often precedes price
    moves by 1–3 days as informed traders position ahead of catalysts.
    Only meaningful for US-listed equities with liquid option chains.

    Caps at max_scan tickers to avoid rate-limit issues on free Yahoo data.
    """
    unusual = []
    for sym in list(universe)[:max_scan]:
        if "." in sym:          # skip SGX / NSE / HK — no liquid US options chain
            continue
        try:
            tkr = yf.Ticker(sym)
            exp_dates = tkr.options
            if not exp_dates:
                continue
            chain  = tkr.option_chain(exp_dates[0])
            calls  = chain.calls
            if calls.empty:
                continue
            price  = float(tkr.info.get("regularMarketPrice") or
                           tkr.info.get("currentPrice") or 0)
            if price <= 0:
                continue
            # ATM calls: strikes within ±10% of current price
            atm = calls[
                (calls["strike"] >= price * 0.90) &
                (calls["strike"] <= price * 1.10)
            ]
            if atm.empty:
                continue
            total_vol = float(atm["volume"].fillna(0).sum())
            total_oi  = float(atm["openInterest"].fillna(0).sum())
            if total_oi > 0 and total_vol / total_oi >= min_oi_ratio and total_vol >= 100:
                unusual.append(sym)
        except Exception:
            continue
    return unusual


@st.cache_data(ttl=15 * 60, show_spinner=False)
def fetch_premarket_gappers(
    universe: list,
    min_gap_pct: float = 3.0,
    min_price: float = 5.0,
    max_scan: int = 300,
) -> list:
    """
    Identify stocks with significant pre-market gaps (≥ min_gap_pct).

    Run this before 09:30 ET. Returns tickers sorted by |gap%| descending.
    Pre-market gappers driven by news/earnings are your highest-probability
    same-day catalyst plays and PEAD setups.

    Uses yfinance Ticker.info which returns preMarketPrice when available.
    Falls back gracefully when pre-market data is absent (weekend, post-close).
    """
    gappers = []
    for sym in list(universe)[:max_scan]:
        try:
            info       = yf.Ticker(sym).info
            pm_price   = info.get("preMarketPrice")
            prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
            if pm_price and prev_close and float(prev_close) >= min_price:
                gap_pct = (float(pm_price) - float(prev_close)) / float(prev_close) * 100.0
                if abs(gap_pct) >= min_gap_pct:
                    gappers.append(sym)
        except Exception:
            continue
    # Sort by absolute gap size so callers get the biggest movers first
    try:
        gappers.sort(
            key=lambda s: abs(
                (yf.Ticker(s).info.get("preMarketPrice", 0) or 0) /
                max(yf.Ticker(s).info.get("previousClose", 1) or 1, 0.01) - 1
            ),
            reverse=True,
        )
    except Exception:
        pass
    return gappers

@st.cache_data(ttl=30 * 60, show_spinner=False)
def fetch_live_market_universe(market_name: str, max_symbols: int = 350) -> tuple:
    """
    Build the LIVE/Yahoo side of the scan universe.

    v14 upgrade (US market):
      • 52-week high breakouts are prepended (highest priority)
      • Finviz swing_breakout screen pre-filters for technical quality
      • Top-3 sector ETF holdings are prioritised over random movers
      • Earnings universe (upcoming + recent beats) is merged in
      • Unusual options activity tickers are included
      • Pre-market gappers (when available) are prepended

    The final scan step later merges these live tickers with the full existing
    curated ticker list, so names like UUUU and APP are not lost simply because
    they are not in today's Yahoo movers/index response.
    """
    if market_name == "🇺🇸 US":
        movers       = fetch_yahoo_market_movers(100)
        index_names  = fetch_us_index_universe(max_symbols=max_symbols)
        base_pool    = _unique_keep_order(movers + index_names)

        # ── v14 enhancements ──────────────────────────────────────────────────
        # 1. 52-week high breakouts (prepend — highest quality momentum candidates)
        try:
            _52w = fetch_52w_high_breakouts(base_pool[:300], min_vol_ratio=1.5)
        except Exception:
            _52w = []

        # 2. Finviz pre-screened breakout candidates (optional dep)
        try:
            _fviz = fetch_finviz_screen("swing_breakout")
        except Exception:
            _fviz = []

        # 3. Top-3 sector ETF stocks (sector rotation filter)
        try:
            _top_sectors = get_top_sector_etfs(n=3)
            _sector_stocks = []
            for _etf in _top_sectors:
                _t = yf.Ticker(_etf)
                for _attr in ("portfolio_holdings", "equity_holdings", "top_holdings"):
                    try:
                        _df_h = getattr(_t.funds_data, _attr)
                        if _df_h is None or _df_h.empty:
                            continue
                        _sym_col = next(
                            (c for c in ["Symbol", "symbol", "Ticker", "ticker"] if c in _df_h.columns),
                            None,
                        )
                        _raw = _df_h[_sym_col].dropna().astype(str).tolist() if _sym_col else [str(x) for x in _df_h.index.tolist()]
                        _sector_stocks += [_clean_symbol(s) for s in _raw if _clean_symbol(s)]
                        break
                    except Exception:
                        continue
        except Exception:
            _sector_stocks = []

        # 4. Earnings universe (upcoming + recent beats)
        try:
            _earn = fetch_earnings_universe(base_pool[:300], window_ahead=7)
            _earn_tickers = _earn.get("upcoming", []) + _earn.get("recent_beat", [])
        except Exception:
            _earn_tickers = []

        # 5. Unusual options activity (US only)
        try:
            _opt_unusual = fetch_unusual_options_universe(base_pool[:200], min_oi_ratio=3.0)
        except Exception:
            _opt_unusual = []

        # 6. Pre-market gappers (best-effort; data present only during pre-market hours)
        try:
            _pm_gappers = fetch_premarket_gappers(base_pool[:300], min_gap_pct=3.0)
        except Exception:
            _pm_gappers = []

        # Combine: high-signal sources first (52w highs, pm gappers, finviz),
        # then earnings, unusual options, sector leaders, broad pool.
        tickers = _unique_keep_order(
            _52w +
            _pm_gappers +
            _fviz +
            _earn_tickers +
            _opt_unusual +
            _sector_stocks +
            base_pool
        )
        source = (
            "v14: 52w breakouts + PreMkt gappers + Finviz screen + "
            "Earnings calendar + Unusual options + Top sectors + Yahoo expanded"
        )

    elif market_name == "🇸🇬 SGX":
        tickers = fetch_sgx_market_universe(max_symbols=max_symbols)
        source = "SGX securities feed + STI/current curated SGX fallback"
    elif market_name == "🇭🇰 HK":
        tickers = fetch_hk_market_universe(max_symbols=max_symbols)
        source = "Hong Kong expanded curated high-beta/liquid .HK watchlist"
    else:
        tickers = fetch_nse_market_universe(max_symbols=max_symbols)
        source = "NSE live index constituents"

    tickers = _unique_keep_order(tickers)[:max_symbols]
    if len(tickers) < 10:
        return [], "live market universe unavailable"
    return tickers, source


# ─────────────────────────────────────────────────────────────────────────────
# OPERATOR + TRAP DETECTOR — reusable across Stock Analysis and main scan
# ─────────────────────────────────────────────────────────────────────────────
