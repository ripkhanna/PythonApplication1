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


@st.cache_data(ttl=30 * 60, show_spinner=False)
def fetch_live_market_universe(market_name: str, max_symbols: int = 350) -> tuple:
    """
    Build the LIVE/Yahoo side of the scan universe.

    Important: this function returns only the live-market tickers, capped by
    max_symbols. The scan step later merges these with the full existing
    curated ticker list, so names like UUUU and APP are not lost simply because
    they are not in today's Yahoo movers/index response.
    """
    if market_name == "🇺🇸 US":
        movers = fetch_yahoo_market_movers(100)
        index_names = fetch_us_index_universe(max_symbols=max_symbols)
        tickers = _unique_keep_order(movers + index_names)
        source = "Yahoo expanded live screeners + current US index constituents"
    elif market_name == "🇸🇬 SGX":
        tickers = fetch_sgx_market_universe(max_symbols=max_symbols)
        source = "SGX securities feed / current STI constituents"
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
