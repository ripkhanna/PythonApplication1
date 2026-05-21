"""Extracted runtime section from app_runtime.py lines 1964-2374.
Loaded by app_runtime with exec(..., globals()) to preserve the original single-file behavior.
"""

# universe_data is the single source of truth for all ticker lists.
# Import here so fetch_hk_market_universe / fetch_sgx_market_universe
# can use the merged lists as their authoritative fallback.
import sys as _sys_uc, pathlib as _pl_uc
_app_root = _pl_uc.Path(__file__).resolve().parent.parent
if str(_app_root) not in _sys_uc.path if hasattr(_sys_uc, 'path') else True:
    _sys_uc.path.insert(0, str(_app_root))
try:
    from swing_trader_app.tabs.universe_data import (
        US_TICKERS as _UD_US_TICKERS,
        HK_TICKERS as _UD_HK_TICKERS,
        SG_TICKERS as _UD_SG_TICKERS,
        INDIA_TICKERS as _UD_INDIA_TICKERS,
    )
    _universe_data_available = True
except ImportError:
    _UD_US_TICKERS = []
    _UD_HK_TICKERS = []
    _UD_SG_TICKERS = []
    _UD_INDIA_TICKERS = []
    _universe_data_available = False


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


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_active_from_universe(symbols_tuple, market_name: str = "", max_active: int = 120) -> list:
    """Return active symbols from a known universe by move, volume, and ATR.

    This avoids missing SGX/HK/India names simply because they are not in a
    hand-picked watchlist. The caller still merges these with the full universe
    and user-added tickers before scanning.
    """
    symbols = _unique_keep_order([str(s).strip().upper() for s in list(symbols_tuple or []) if str(s).strip()])
    if not symbols:
        return []

    is_asia = any(x in str(market_name).upper() for x in ("SGX", "HK", "INDIA", "NSE"))
    min_move = 1.2 if is_asia else 2.0
    min_vr = 1.25 if is_asia else 1.5
    min_atr = 1.5 if is_asia else 2.5
    scored = []

    def _field(raw, sym, field, n):
        try:
            if n == 1:
                return raw[field].squeeze().ffill().dropna()
            if isinstance(raw.columns, pd.MultiIndex):
                lvl1 = raw.columns.get_level_values(1)
                lvl0 = raw.columns.get_level_values(0)
                if sym in lvl1:
                    return raw.xs(sym, axis=1, level=1)[field].squeeze().ffill().dropna()
                if sym in lvl0:
                    return raw[sym][field].squeeze().ffill().dropna()
            if sym in raw.columns:
                return raw[sym][field].squeeze().ffill().dropna()
            return raw[field].squeeze().ffill().dropna()
        except Exception:
            return pd.Series(dtype=float)

    # Keep batches moderate; Yahoo often returns partial failures on very large
    # non-US requests.
    for start in range(0, len(symbols), 80):
        chunk = symbols[start:start + 80]
        try:
            raw = yf.download(
                chunk, period="3mo", interval="1d",
                progress=False, group_by="ticker",
                threads=True, auto_adjust=True,
            )
            if raw is None or raw.empty:
                continue
        except Exception:
            continue

        for sym in chunk:
            try:
                c = _field(raw, sym, "Close", len(chunk))
                h = _field(raw, sym, "High", len(chunk))
                lo = _field(raw, sym, "Low", len(chunk))
                v = _field(raw, sym, "Volume", len(chunk))
                if len(c) < 22 or len(h) < 22 or len(lo) < 22:
                    continue
                price = float(c.iloc[-1])
                prev = float(c.iloc[-2])
                if price <= 0 or prev <= 0:
                    continue
                today_pct = abs((price / prev - 1.0) * 100.0)
                five_pct = abs((price / float(c.iloc[-6]) - 1.0) * 100.0) if len(c) >= 6 and float(c.iloc[-6]) > 0 else 0.0
                twenty_pct = abs((price / float(c.iloc[-21]) - 1.0) * 100.0) if len(c) >= 21 and float(c.iloc[-21]) > 0 else 0.0
                sixty_pct = abs((price / float(c.iloc[-61]) - 1.0) * 100.0) if len(c) >= 61 and float(c.iloc[-61]) > 0 else 0.0
                vol_last = float(v.iloc[-1]) if len(v) else 0.0
                vol_avg = float(v.tail(21).iloc[:-1].mean()) if len(v) >= 21 else float(v.mean() or 0.0)
                vr = vol_last / vol_avg if vol_avg > 0 else 0.0
                atr = float(ta.volatility.average_true_range(h, lo, c, window=14).iloc[-1])
                atr_pct = atr / price * 100.0 if price > 0 else 0.0
                if today_pct < min_move and five_pct < 3.0 and twenty_pct < 6.0 and sixty_pct < 12.0 and vr < min_vr and atr_pct < min_atr:
                    continue
                dollar_vol = price * max(vol_last, vol_avg, 0.0)
                liquidity = np.log10(max(dollar_vol, vol_last, 1.0))
                activity_score = (
                    min(today_pct, 20.0) * 3.0 +
                    min(five_pct, 30.0) * 0.8 +
                    min(twenty_pct, 50.0) * 0.45 +
                    min(sixty_pct, 80.0) * 0.25 +
                    min(vr, 6.0) * 6.0 +
                    min(atr_pct, 15.0) * 2.5 +
                    liquidity
                )
                scored.append((sym, activity_score))
            except Exception:
                continue

    scored.sort(key=lambda x: -x[1])
    return [s for s, _ in scored[:max_active]]


@st.cache_data(ttl=10 * 60, show_spinner=False)
def fetch_quote_activity_from_universe(symbols_tuple, market_name: str = "", max_active: int = 120) -> list:
    """Rank a known universe by today's live quote move and traded value.

    This is the cross-market equivalent of the SGX active-first patch: if a
    ticker is moving today, it should be promoted before max_symbols trimming
    even when it is deep in the curated/index universe.
    """
    symbols = _unique_keep_order([str(s).strip().upper() for s in list(symbols_tuple or []) if str(s).strip()])
    if not symbols:
        return []

    import json as _json_quote
    import concurrent.futures as _fut_quote
    import urllib.parse as _urlparse_quote
    import urllib.request as _urlreq_quote

    m = str(market_name or "").upper()
    if "US" in m:
        min_dollar_vol = 1_000_000
    elif "HK" in m:
        min_dollar_vol = 500_000
    elif "INDIA" in m or "NSE" in m:
        min_dollar_vol = 5_000_000
    elif "SGX" in m:
        min_dollar_vol = 120_000
    else:
        min_dollar_vol = 250_000

    scored = []
    headers = {"User-Agent": "Mozilla/5.0"}

    def _chart_score(sym):
        try:
            safe_sym = _urlparse_quote.quote(sym, safe="")
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{safe_sym}?range=5d&interval=1d"
            req = _urlreq_quote.Request(url, headers=headers)
            with _urlreq_quote.urlopen(req, timeout=12) as resp:
                payload = _json_quote.loads(resp.read().decode("utf-8", errors="replace"))
            result = (payload.get("chart", {}).get("result", []) or [{}])[0]
            meta = result.get("meta", {}) or {}
            quote = (result.get("indicators", {}).get("quote", []) or [{}])[0]
            closes = [float(x) for x in (quote.get("close") or []) if x is not None]
            volumes = [float(x) for x in (quote.get("volume") or []) if x is not None]
            price = float(meta.get("regularMarketPrice") or (closes[-1] if closes else 0.0) or 0.0)
            prev = float(meta.get("chartPreviousClose") or meta.get("previousClose") or 0.0)
            if prev <= 0 and len(closes) >= 2:
                prev = float(closes[-2])
            volume = float(volumes[-1] if volumes else 0.0)
            if price <= 0 or prev <= 0:
                return None
            pct = abs((price / prev - 1.0) * 100.0)
            dollar_vol = price * volume
            if pct <= 0 or dollar_vol < min_dollar_vol:
                return None
            score = min(pct, 25.0) * 25.0 + np.log10(max(dollar_vol, 1.0)) * 8.0
            return (sym, score)
        except Exception:
            return None

    with _fut_quote.ThreadPoolExecutor(max_workers=12) as ex:
        for item in ex.map(_chart_score, symbols):
            if item:
                scored.append(item)

    score_map = {}
    for sym, score in scored:
        score_map[sym] = max(score_map.get(sym, 0.0), score)
    return [s for s, _ in sorted(score_map.items(), key=lambda kv: -kv[1])[:max_active]]


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
    """Fetch live Yahoo universe using concurrent screener requests.

    v15.6 rewrite: replaced 26 sequential HTTP requests (13 screeners × 2 paths)
    with ThreadPoolExecutor — all screeners fetched in parallel.
    Old time: 30-78s. New time: ~3-8s (= slowest single request).
    """
    import concurrent.futures as _fut
    import requests as _req

    screen_names = (
        "most_actives", "day_gainers", "day_losers",
        "undervalued_growth_stocks", "growth_technology_stocks",
        "aggressive_small_caps", "small_cap_gainers", "most_shorted_stocks",
        "portfolio_anchors", "undervalued_large_caps",
        "solid_large_growth_funds", "high_yield_bond", "top_mutual_funds",
    )

    # ── Path 1: yfinance.screen() — parallel ──────────────────────────────
    yf_tickers: list = []
    if hasattr(yf, "screen"):
        def _yf_screen(scr):
            try:
                res = yf.screen(scr, count=min(max_per_screener, 100))
                quotes = res.get("quotes", []) if isinstance(res, dict) else []
                return [_clean_symbol(q.get("symbol", "")) for q in quotes if q.get("symbol")]
            except Exception:
                return []

        with _fut.ThreadPoolExecutor(max_workers=len(screen_names)) as ex:
            for batch in ex.map(_yf_screen, screen_names):
                yf_tickers.extend(batch)

    # ── Path 2: Yahoo screener endpoint — parallel ────────────────────────
    yahoo_tickers: list = []
    url     = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
    headers = {"User-Agent": "Mozilla/5.0 (compatible)"}
    per_page = min(max(int(max_per_screener), 25), 100)   # cap 100 per call

    def _yahoo_screen(scr):
        results = []
        try:
            params = {
                "scrIds": scr, "count": per_page, "start": 0,
                "formatted": "false", "lang": "en-US", "region": "US",
            }
            r = _req.get(url, params=params, headers=headers, timeout=10)
            if not r.ok:
                return results
            quotes = ((r.json().get("finance", {})
                                .get("result", [{}])[0])
                                .get("quotes", []) or [])
            for q in quotes:
                sym = _clean_symbol(q.get("symbol", ""))
                if sym:
                    results.append(sym)
        except Exception:
            pass
        return results

    try:
        with _fut.ThreadPoolExecutor(max_workers=len(screen_names)) as ex:
            for batch in ex.map(_yahoo_screen, screen_names):
                yahoo_tickers.extend(batch)
    except Exception:
        pass

    return _unique_keep_order(yf_tickers + yahoo_tickers)


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_yahoo_region_movers(region: str, suffix: str = "", max_per_screener: int = 100) -> list:
    """Fetch active regional movers from Yahoo predefined screeners."""
    import concurrent.futures as _fut
    import requests as _req

    region = str(region or "").upper()
    screen_names = ("most_actives", "day_gainers", "day_losers", "small_cap_gainers")
    url = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
    headers = {"User-Agent": "Mozilla/5.0 (compatible)"}
    per_page = min(max(int(max_per_screener), 25), 100)

    def _screen(scr):
        out = []
        try:
            params = {
                "scrIds": scr, "count": per_page, "start": 0,
                "formatted": "false", "lang": "en-US", "region": region,
            }
            r = _req.get(url, params=params, headers=headers, timeout=10)
            if not r.ok:
                return out
            quotes = ((r.json().get("finance", {})
                                .get("result", [{}])[0])
                                .get("quotes", []) or [])
            for q in quotes:
                sym = _clean_symbol(q.get("symbol", ""), suffix)
                if suffix and not str(sym).upper().endswith(str(suffix).upper()):
                    continue
                if sym:
                    out.append(sym)
        except Exception:
            pass
        return out

    found = []
    try:
        with _fut.ThreadPoolExecutor(max_workers=len(screen_names)) as ex:
            for batch in ex.map(_screen, screen_names):
                found.extend(batch)
    except Exception:
        pass
    return _unique_keep_order(found)


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
    scored_tickers = []

    # SGX public securities endpoint changes occasionally; keep it best-effort.
    try:
        import json as _json_sgx
        import urllib.parse as _urlparse_sgx
        import urllib.request as _urlreq_sgx
        try:
            import requests as _requests_sgx
        except Exception:
            _requests_sgx = None
        urls = (
            "https://api.sgx.com/securities/v1.1",
            "https://api2.sgx.com/securities/v1.1",
        )
        params = {
            "excludetypes": "bonds",
            "params": "nc,cn,c,v,lt",
        }
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json,text/plain,*/*",
            "Referer": "https://www.sgx.com/",
        }

        def _fetch_sgx_json(url):
            if _requests_sgx is not None:
                r = _requests_sgx.get(url, params=params, headers=headers, timeout=15)
                if not r.ok:
                    return None
                return r.json()
            query = _urlparse_sgx.urlencode(params)
            req = _urlreq_sgx.Request(f"{url}?{query}", headers=headers)
            with _urlreq_sgx.urlopen(req, timeout=15) as resp:
                return _json_sgx.loads(resp.read().decode("utf-8", errors="replace"))

        for url in urls:
            try:
                data = _fetch_sgx_json(url)
                if not data:
                    continue
                payload = data.get("data", data if isinstance(data, list) else [])
                rows = payload.get("prices", []) if isinstance(payload, dict) else payload
                for row in rows:
                    if isinstance(row, dict):
                        code = row.get("code") or row.get("nc") or row.get("symbol") or row.get("ticker")
                        sec_type = str(row.get("type", "")).lower()
                        if sec_type and sec_type not in ("stocks", "reits", "business trusts", "stapled securities", "etfs"):
                            continue
                    elif isinstance(row, (list, tuple)) and row:
                        code = row[0]
                    else:
                        code = None
                    sym = _clean_symbol(code, ".SI")
                    if sym:
                        tickers.append(sym)
                        if isinstance(row, dict):
                            try:
                                last_price = float(row.get("lt") or row.get("l") or row.get("last") or 0.0)
                                change_abs = abs(float(row.get("c") or row.get("change_vs_pc") or 0.0))
                                volume = float(row.get("v") or row.get("volume") or 0.0)
                                prev_price = last_price - change_abs if last_price > change_abs else 0.0
                                move_pct = (change_abs / prev_price * 100.0) if prev_price > 0 else 0.0
                                dollar_vol = last_price * volume
                                activity_score = min(move_pct, 25.0) * 25.0 + np.log10(max(dollar_vol, 1.0)) * 8.0
                                if activity_score > 0 and dollar_vol >= 120_000:
                                    scored_tickers.append((sym, activity_score))
                            except Exception:
                                pass
                if tickers:
                    break
            except Exception:
                continue
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
        fallback = (_UD_SG_TICKERS if _UD_SG_TICKERS else globals().get("SGX_LIQUID_FALLBACK_TICKERS", []) or globals().get("SG_TICKERS", []))
        if len(tickers) < 60 and fallback:
            tickers.extend([_clean_symbol(x, ".SI") for x in fallback])
    except Exception:
        pass

    if scored_tickers:
        score_map = {}
        for sym, score in scored_tickers:
            score_map[sym] = max(score_map.get(sym, 0.0), score)
        active_first = [sym for sym, _ in sorted(score_map.items(), key=lambda kv: -kv[1])]
        tickers = active_first + tickers

    return _unique_keep_order(tickers)[:max_symbols]


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def fetch_nse_market_universe(max_symbols: int = 220) -> list:
    """Fetch current NSE index constituents from NSE's live index API."""
    tickers = []
    scored_tickers = []
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
                    if sym and "NIFTY" not in str(sym).upper():
                        t = _clean_symbol(sym, ".NS")
                        if t:
                            tickers.append(t)
                            try:
                                pct = abs(float(row.get("pChange") or row.get("perChange365d") or 0.0))
                                price = float(row.get("lastPrice") or row.get("previousClose") or 0.0)
                                volume = float(row.get("totalTradedVolume") or row.get("quantityTraded") or 0.0)
                                traded_value = price * volume
                                score = min(pct, 25.0) * 25.0 + np.log10(max(traded_value, 1.0)) * 8.0
                                if pct > 0 and traded_value >= 5_000_000:
                                    scored_tickers.append((t, score))
                            except Exception:
                                pass
            except Exception:
                continue
    except Exception:
        pass
    if scored_tickers:
        score_map = {}
        for sym, score in scored_tickers:
            score_map[sym] = max(score_map.get(sym, 0.0), score)
        active_first = [sym for sym, _ in sorted(score_map.items(), key=lambda kv: -kv[1])]
        tickers = active_first + tickers
    return _unique_keep_order(tickers)[:max_symbols]



@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def fetch_hk_market_universe(max_symbols: int = 160) -> list:
    """Return Hong Kong watchlist. Yahoo HK live universe is unreliable, so use curated liquid .HK names."""
    try:
        # Use universe_data merged list; fall back to globals for older exec() contexts
        base = _UD_HK_TICKERS if _UD_HK_TICKERS else globals().get("HK_TICKERS", [])
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

@st.cache_data(ttl=60 * 60, show_spinner=False)   # cache 1h — was missing entirely
def fetch_52w_high_breakouts(universe: list, min_vol_ratio: float = 1.5) -> list:
    """Find tickers making new 52-week highs today on above-average volume.

    v15.6 rewrite: replaced yf.download(300 tickers, period='1y') — which
    downloads ~450k data points and takes 60-120s — with yf.Ticker.fast_info
    which returns year_high/year_low/last_price/3m_avg_vol in a single
    lightweight call per ticker.  Parallelised with ThreadPoolExecutor.
    """
    import concurrent.futures as _fut

    breakouts = []
    if not universe:
        return breakouts

    def _check_one(sym: str):
        try:
            import contextlib as _cl, io as _io
            with _cl.redirect_stderr(_io.StringIO()), _cl.redirect_stdout(_io.StringIO()):
                fi = yf.Ticker(sym).fast_info
            price     = float(getattr(fi, "last_price",              0) or 0)
            year_high = float(getattr(fi, "year_high",               0) or 0)
            vol_3m    = float(getattr(fi, "three_month_average_volume", 0) or 0)
            last_vol  = float(getattr(fi, "last_volume",             0) or 0)
            if price <= 0 or year_high <= 0:
                return None
            vol_ratio = (last_vol / vol_3m) if vol_3m > 0 else 0
            # At or above prior 52w high on heavy volume
            if price >= year_high * 0.995 and vol_ratio >= min_vol_ratio:
                return sym
        except Exception:
            pass
        return None

    workers = min(12, max(1, len(universe[:150])))
    with _fut.ThreadPoolExecutor(max_workers=workers) as ex:
        for result in ex.map(_check_one, universe[:150]):   # cap at 150 for speed
            if result:
                breakouts.append(result)

    return breakouts


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def fetch_earnings_universe(universe: list, window_ahead: int = 7) -> dict:
    """Identify upcoming earnings + recent beats for the PEAD universe.

    v15.6 rewrite: replaced 300 sequential yf.Ticker.calendar calls
    (took 120-150s) with the Nasdaq bulk earnings calendar (single HTTP
    request per day, already used by the Earnings tab).  Falls back to a
    concurrent yfinance scan capped at 100 tickers.
    """
    import concurrent.futures as _fut
    from datetime import datetime

    upcoming: list     = []
    recent_beat: list  = []
    today  = pd.Timestamp.now(tz="Asia/Singapore").date()
    cutoff = today + pd.Timedelta(days=window_ahead)

    # US tickers only — non-US tickers not in Nasdaq calendar
    us_universe = [t for t in list(universe)[:300]
                   if not str(t).upper().endswith((".SI", ".HK", ".NS", ".BO"))]
    ticker_set  = {str(t).strip().upper() for t in us_universe}

    # ── Fast path: Nasdaq bulk calendar (one request per day) ─────────────
    try:
        from swing_trader_app.core_runtime.event_core import _nasdaq_earnings_for_date
        for _i in range(window_ahead + 4):   # +4 to catch recent beats
            _d = today + pd.Timedelta(days=_i - 3)   # 3 days back for recent beats
            _rows = _nasdaq_earnings_for_date(_d.strftime("%Y-%m-%d"))
            for _r in _rows:
                if not isinstance(_r, dict):
                    continue
                sym = str(_r.get("symbol") or _r.get("Symbol") or "").strip().upper()
                if sym not in ticker_set:
                    continue
                delta = (_d - today).days
                if 0 <= delta <= window_ahead:
                    upcoming.append(sym)
                elif -3 <= delta < 0:
                    recent_beat.append(sym)   # reported recently — could be PEAD setup
    except Exception:
        pass

    # ── Fallback: concurrent yfinance for remaining tickers ───────────────
    # Only runs if Nasdaq calendar returned nothing (non-US or blocked)
    if not upcoming and not recent_beat:
        def _cal_job(sym):
            try:
                import contextlib as _cl, io as _io
                with _cl.redirect_stderr(_io.StringIO()), _cl.redirect_stdout(_io.StringIO()):
                    cal = yf.Ticker(sym).calendar
                if cal is None:
                    return []
                earn_dates = []
                if isinstance(cal, dict):
                    raw = cal.get("Earnings Date", [])
                    earn_dates = [pd.Timestamp(d).date()
                                  for d in (raw if isinstance(raw, list) else [raw]) if d]
                elif hasattr(cal, "columns"):
                    for col in ("Earnings Date", "earnings_date"):
                        if col in cal.columns:
                            earn_dates = [pd.Timestamp(d).date() for d in cal[col].dropna()]
                            break
                hits = []
                for ed in earn_dates:
                    delta = (ed - today).days
                    if 0 <= delta <= window_ahead:
                        hits.append(("upcoming", sym))
                    elif -3 <= delta < 0:
                        hits.append(("recent", sym))
                return hits
            except Exception:
                return []

        with _fut.ThreadPoolExecutor(max_workers=10) as ex:
            for hits in ex.map(_cal_job, us_universe[:100]):
                for kind, sym in hits:
                    if kind == "upcoming":
                        upcoming.append(sym)
                    else:
                        recent_beat.append(sym)

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
    max_scan: int = 60,          # FIX: reduced from 150 — options chain calls are slow
) -> list:
    """
    Return US tickers with unusual near-money CALL volume (volume/OI >= min_oi_ratio).

    v15.7 speed fix: parallelised with ThreadPoolExecutor (was fully sequential —
    3 serial yfinance calls × 150 tickers = ~450 HTTP requests, 90-150s alone).
    Also uses fast_info.last_price instead of tkr.info (heavy call, ~0.5s each).
    max_scan reduced from 150 → 60 to stay within Yahoo rate limits when parallel.
    """
    import concurrent.futures as _fut

    candidates = [s for s in list(universe)[:max_scan] if "." not in str(s)]

    def _check_options(sym: str):
        try:
            tkr       = yf.Ticker(sym)
            exp_dates = tkr.options
            if not exp_dates:
                return None
            chain = tkr.option_chain(exp_dates[0])
            calls = chain.calls
            if calls is None or calls.empty:
                return None
            # Use fast_info instead of tkr.info (fast_info is ~10x faster)
            import contextlib as _cl, io as _io
            with _cl.redirect_stderr(_io.StringIO()), _cl.redirect_stdout(_io.StringIO()):
                price = float(getattr(yf.Ticker(sym).fast_info, "last_price", 0) or 0)
            if price <= 0:
                return None
            atm = calls[
                (calls["strike"] >= price * 0.90) &
                (calls["strike"] <= price * 1.10)
            ]
            if atm.empty:
                return None
            total_vol = float(atm["volume"].fillna(0).sum())
            total_oi  = float(atm["openInterest"].fillna(0).sum())
            if total_oi > 0 and total_vol / total_oi >= min_oi_ratio and total_vol >= 100:
                return sym
        except Exception:
            pass
        return None

    unusual = []
    # 6 workers: enough parallelism without hammering Yahoo rate limits
    with _fut.ThreadPoolExecutor(max_workers=6) as ex:
        for result in ex.map(_check_options, candidates):
            if result:
                unusual.append(result)
    return unusual


@st.cache_data(ttl=15 * 60, show_spinner=False)
def fetch_premarket_gappers(
    universe: list,
    min_gap_pct: float = 3.0,
    min_price: float = 5.0,
    max_scan: int = 200,   # v15.6: reduced from 300; fast_info covers well
) -> list:
    """Identify pre-market gappers using fast_info + ThreadPoolExecutor.

    v15.6 rewrite: replaced sequential yf.Ticker.info calls (heaviest yfinance
    call, ~90-180s for 300 tickers) with fast_info + parallel execution.
    """
    import concurrent.futures as _fut

    tickers = [t for t in list(universe)[:max_scan] if "." not in str(t)]

    def _check_gap(sym):
        try:
            import contextlib as _cl, io as _io
            with _cl.redirect_stderr(_io.StringIO()), _cl.redirect_stdout(_io.StringIO()):
                fi = yf.Ticker(sym).fast_info
            pm_pct = getattr(fi, "pre_market_change_percent", None)
            if pm_pct is not None:
                pm_abs = abs(float(pm_pct) * 100)
                if pm_abs >= min_gap_pct:
                    return (sym, pm_abs)
            last = float(getattr(fi, "last_price",     0) or 0)
            prev = float(getattr(fi, "previous_close", 0) or 0)
            if last >= min_price and prev > 0:
                pct = abs((last - prev) / prev * 100)
                if pct >= min_gap_pct:
                    return (sym, pct)
        except Exception:
            pass
        return None

    results = []
    with _fut.ThreadPoolExecutor(max_workers=min(15, max(1, len(tickers)))) as ex:
        for r in ex.map(_check_gap, tickers):
            if r:
                results.append(r)

    results.sort(key=lambda x: x[1], reverse=True)
    return [sym for sym, _ in results]

@st.cache_data(ttl=15 * 60, show_spinner=False)
def fetch_post_earnings_gappers(universe: list, min_gap_pct: float = 5.0, max_scan: int = 100) -> list:
    """Recent earnings reporters gapping today. Catches SEDG-type moves."""
    import concurrent.futures as _fut
    today = pd.Timestamp.now(tz="Asia/Singapore").date()
    us_set = {str(t).strip().upper() for t in list(universe)[:max_scan]
              if not str(t).upper().endswith((".SI",".HK",".NS",".BO"))}
    recent: set = set()
    try:
        from swing_trader_app.core_runtime.event_core import _nasdaq_earnings_for_date
        for _b in range(4):
            _d = today - pd.Timedelta(days=_b)
            for _r in _nasdaq_earnings_for_date(_d.strftime("%Y-%m-%d")):
                s = str((_r or {}).get("symbol") or "").strip().upper()
                if s in us_set: recent.add(s)
    except Exception: pass
    candidates = list(recent) if recent else list(us_set)[:40]
    def _chk(sym):
        try:
            import contextlib as _cl, io as _io
            with _cl.redirect_stderr(_io.StringIO()), _cl.redirect_stdout(_io.StringIO()):
                fi = yf.Ticker(sym).fast_info
            last = float(getattr(fi, "last_price", 0) or 0)
            prev = float(getattr(fi, "previous_close", 0) or 0)
            vol  = float(getattr(fi, "last_volume", 0) or 0)
            avg3m = float(getattr(fi, "three_month_average_volume", 1) or 1)
            if last > 0 and prev > 0:
                pct = (last - prev) / prev * 100
                if pct >= min_gap_pct and (vol / avg3m if avg3m > 0 else 0) >= 1.5:
                    return (sym, pct)
        except Exception: pass
        return None
    results = []
    with _fut.ThreadPoolExecutor(max_workers=8) as ex:
        for r in ex.map(_chk, candidates[:80]):
            if r: results.append(r)
    results.sort(key=lambda x: -x[1])
    return [s for s, _ in results]


@st.cache_data(ttl=30 * 60, show_spinner=False)
def fetch_live_market_universe(market_name: str, max_symbols: int = 350,
                               enable_slow_enrichment: bool = False) -> tuple:
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
        index_names  = fetch_us_index_universe(max_symbols=max(max_symbols, 600))
        base_pool    = _unique_keep_order(movers + index_names + list(_UD_US_TICKERS or []))
        quote_active = fetch_quote_activity_from_universe(
            tuple(base_pool), market_name, max_active=min(160, max_symbols)
        )
        active_from_universe = fetch_active_from_universe(
            tuple(base_pool), market_name, max_active=min(160, max_symbols)
        )

        # ── v15.6: enhancement sources ────────────────────────────────────────
        # NOTE: These are called sequentially here, but fetch_live_market_universe
        # itself is @st.cache_data(ttl=30min), so this block only runs on a cold
        # cache miss (~once per 30 minutes). Each sub-function is also individually
        # cached, so repeated calls within the same session are instant.
        # DO NOT run these in ThreadPoolExecutor — @st.cache_data functions must
        # be called from the main thread to use their cache correctly.
        _52w           = []
        _fviz          = []
        _sector_stocks = []
        _earn_tickers  = []
        _opt_unusual   = []
        _pm_gappers    = []

        try:
            _52w = fetch_52w_high_breakouts(base_pool[:150], min_vol_ratio=1.5)
        except Exception:
            pass

        if enable_slow_enrichment:
            try:
                _fviz = fetch_finviz_screen("swing_breakout")
            except Exception:
                pass

        try:
            top = get_top_sector_etfs(n=3)
            for _etf in top:
                _t = yf.Ticker(_etf)
                for _attr in ("portfolio_holdings", "equity_holdings", "top_holdings"):
                    try:
                        _df_h = getattr(_t.funds_data, _attr)
                        if _df_h is None or _df_h.empty:
                            continue
                        _sym_col = next(
                            (c for c in ["Symbol","symbol","Ticker","ticker"] if c in _df_h.columns),
                            None,
                        )
                        _raw = _df_h[_sym_col].dropna().astype(str).tolist() if _sym_col else [str(x) for x in _df_h.index.tolist()]
                        _sector_stocks += [_clean_symbol(s) for s in _raw if _clean_symbol(s)]
                        break
                    except Exception:
                        continue
        except Exception:
            pass

        if enable_slow_enrichment:
            try:
                _e = fetch_earnings_universe(base_pool[:200], window_ahead=7)
                _earn_tickers = _e.get("upcoming", []) + _e.get("recent_beat", [])
            except Exception:
                pass

            try:
                _opt_unusual = fetch_unusual_options_universe(base_pool[:60], min_oi_ratio=3.0)
            except Exception:
                pass

        try:
            _pm_gappers = fetch_premarket_gappers(base_pool[:200], min_gap_pct=3.0)
        except Exception:
            pass
        _earn_gappers: list = []
        try:
            _earn_gappers = fetch_post_earnings_gappers(base_pool[:200], min_gap_pct=5.0)
        except Exception:
            pass

        tickers = _unique_keep_order(
            _earn_gappers + _52w + _pm_gappers + quote_active + active_from_universe + _fviz + _earn_tickers + _opt_unusual + _sector_stocks + base_pool
        )
        source = (
            "v15.11: live quote activity + active universe movers/volatility + 52w breakouts + PreMkt gappers + Top sectors + Yahoo"
            + (" + Finviz + Earnings + Unusual options" if enable_slow_enrichment else "")
            + " (all cached)"
        )

    elif market_name == "🇸🇬 SGX":
        regional_movers = fetch_yahoo_region_movers("SG", ".SI", max_per_screener=100)
        base_pool = _unique_keep_order(
            regional_movers + fetch_sgx_market_universe(max_symbols=max(max_symbols, 5000))
        )
        quote_active = fetch_quote_activity_from_universe(
            tuple(base_pool), market_name, max_active=min(120, max_symbols)
        )
        active_from_universe = fetch_active_from_universe(
            tuple(base_pool), market_name, max_active=min(120, max_symbols)
        )
        tickers = _unique_keep_order(regional_movers + quote_active + active_from_universe + base_pool)
        source = "SGX live quote activity + active volume/volatility + securities feed + curated fallback"
    elif market_name == "🇭🇰 HK":
        regional_movers = fetch_yahoo_region_movers("HK", ".HK", max_per_screener=100)
        base_pool = _unique_keep_order(
            regional_movers + fetch_hk_market_universe(max_symbols=max(max_symbols, 500))
        )
        quote_active = fetch_quote_activity_from_universe(
            tuple(base_pool), market_name, max_active=min(120, max_symbols)
        )
        active_from_universe = fetch_active_from_universe(
            tuple(base_pool), market_name, max_active=min(120, max_symbols)
        )
        tickers = _unique_keep_order(regional_movers + quote_active + active_from_universe + base_pool)
        source = "Hong Kong live quote activity + active volume/volatility + expanded .HK watchlist"
    else:
        regional_movers = fetch_yahoo_region_movers("IN", ".NS", max_per_screener=100)
        base_pool = _unique_keep_order(
            regional_movers + fetch_nse_market_universe(max_symbols=max(max_symbols, 500))
        )
        quote_active = fetch_quote_activity_from_universe(
            tuple(base_pool), market_name, max_active=min(120, max_symbols)
        )
        active_from_universe = fetch_active_from_universe(
            tuple(base_pool), market_name, max_active=min(120, max_symbols)
        )
        tickers = _unique_keep_order(regional_movers + quote_active + active_from_universe + base_pool)
        source = "NSE live quote activity + active volume/volatility + live index constituents"

    tickers = _unique_keep_order(tickers)[:max_symbols]
    if len(tickers) < 10:
        return [], "live market universe unavailable"
    return tickers, source


# ─────────────────────────────────────────────────────────────────────────────
# OPERATOR + TRAP DETECTOR — reusable across Stock Analysis and main scan
# ─────────────────────────────────────────────────────────────────────────────
