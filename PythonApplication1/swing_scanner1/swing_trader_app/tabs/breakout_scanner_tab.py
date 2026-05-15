"""Breakout Scanner Tab — Unified single-view scanner.

All three signals combined into ONE ranked table:
  * High Volume Breakout  — price > N-day high AND vol >= Xx 20-day avg
  * 52-Week High Setup    — within Y% of the 52-week high
  * Market Mover          — Yahoo live gainers/losers/most-active (US only)

Market dropdown -> Universe dropdown -> filters the exact ticker pool scanned.
  US:   S&P 500 / NASDAQ 100 / S&P500+NDX / Growth / All US
  SGX:  SGX Mainboard
  India: Nifty 50 / Nifty 150
  HK:   Hang Seng + HSI Tech

Score (0-100) ranks every stock by combined signal strength.

KEY FIXES:
  1. Universe driven by universe_data.py index lists - S&P 500 scan = all 500 components.
  2. _get_mover_sets called in render() OUTSIDE the cached scan function.
  3. Yahoo mover feed is US-only - SGX/India/HK skips it entirely (no contamination).
  4. Extra movers injection removed - movers only badge existing universe stocks.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

from swing_trader_app.tabs.universe_data import (
    get_universe,
    universe_options_for_market,
)

MARKET_EMOJI = {"US": "US", "SGX": "SGX", "India": "India", "Hong Kong": "HK"}
YAHOO_REGION = {"US": "US", "SGX": "SG", "India": "IN", "Hong Kong": "HK"}
YAHOO_SCREENER_IDS = {
    "Top Gainers": "day_gainers",
    "Top Losers":  "day_losers",
    "Most Active": "most_actives",
}


def _f(v) -> float:
    try:
        return float(v)
    except Exception:
        return float("nan")


def _fmt_vol(v) -> str:
    try:
        v = float(v)
        if v >= 1_000_000:
            return f"{v/1_000_000:.1f}M"
        if v >= 1_000:
            return f"{v/1_000:.0f}K"
        return f"{v:.0f}"
    except Exception:
        return "---"


def _fmt_sgt(ts) -> str:
    if ts is None or str(ts).strip() == "":
        return "---"
    try:
        t = pd.to_datetime(ts, errors="coerce")
        if pd.isna(t):
            return str(ts)
        if t.tzinfo is None:
            t = t.tz_localize("UTC")
        return t.tz_convert("Asia/Singapore").strftime("%d %b %H:%M")
    except Exception:
        return "---"


def _extract_ticker_frame(raw: pd.DataFrame, ticker: str, chunk: list) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame()
    if isinstance(raw.columns, pd.MultiIndex):
        try:
            if ticker in raw.columns.get_level_values(0):
                return raw[ticker].dropna(how="all")
        except Exception:
            pass
        try:
            if ticker in raw.columns.get_level_values(1):
                return raw.xs(ticker, axis=1, level=1).dropna(how="all")
        except Exception:
            pass
        return pd.DataFrame()
    if len(chunk) == 1:
        return raw.dropna(how="all")
    return pd.DataFrame()


def _fetch_screener(region: str, screener_id: str, count: int) -> list:
    params = urllib.parse.urlencode({
        "formatted": "false", "lang": "en-US",
        "region": region, "scrIds": screener_id, "count": int(count),
    })
    url = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?" + params
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            payload = json.loads(r.read().decode("utf-8", errors="replace"))
        result = (((payload or {}).get("finance") or {}).get("result") or [])
        return (result[0].get("quotes") if result else []) or []
    except Exception:
        return []


@st.cache_data(ttl=180, show_spinner=False)
def _get_mover_sets(region: str, count: int):
    symbols = set()
    bucket = {}
    for label, sid in YAHOO_SCREENER_IDS.items():
        for q in _fetch_screener(region, sid, count):
            sym = str(q.get("symbol") or "").strip().upper()
            if sym:
                symbols.add(sym)
                bucket.setdefault(sym, label)
    return frozenset(symbols), tuple(bucket.items())


def _analyse(ticker, df, breakout_days, vol_mult, w52_within, mover_symbols, mover_bucket):
    if df is None or df.empty or "Close" not in df.columns or len(df) < 30:
        return None
    close = pd.to_numeric(df["Close"], errors="coerce").dropna()
    high  = pd.to_numeric(df.get("High",   close), errors="coerce").dropna()
    low   = pd.to_numeric(df.get("Low",    close), errors="coerce").dropna()
    vol   = pd.to_numeric(df.get("Volume", pd.Series(dtype=float)), errors="coerce").fillna(0)
    if len(close) < 30:
        return None
    price = _f(close.iloc[-1])
    prev  = _f(close.iloc[-2]) if len(close) >= 2 else float("nan")
    if not (price > 0 and prev > 0):
        return None
    chg_pct = (price - prev) / prev * 100
    vol_avg20 = _f(vol.iloc[-21:-1].mean()) if len(vol) >= 21 else _f(vol.mean())
    today_vol = _f(vol.iloc[-1])
    vol_ratio = today_vol / vol_avg20 if vol_avg20 > 0 else float("nan")
    high_252 = _f(high.iloc[-252:].max()) if len(high) >= 50 else _f(high.max())
    low_252  = _f(low.iloc[-252:].min())  if len(low)  >= 50 else _f(low.min())
    vs_52w   = (price - high_252) / high_252 * 100 if high_252 > 0 else -999.0
    range_52 = high_252 - low_252
    in_range = (price - low_252) / range_52 * 100 if range_52 > 0 else 0.0
    new_52w  = price >= high_252 * 0.9995
    nd_high      = _f(high.iloc[-(breakout_days+1):-1].max()) if len(high) > breakout_days else _f(high.max())
    is_brk       = (price > nd_high) and np.isfinite(vol_ratio) and vol_ratio >= vol_mult
    breakout_pct = (price - nd_high) / nd_high * 100 if nd_high > 0 else 0.0
    is_52w       = vs_52w >= -w52_within
    is_mover     = ticker in mover_symbols
    mover_label  = mover_bucket.get(ticker, "")
    if len(close) >= 14:
        tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
        atr_pct = _f(tr.rolling(14).mean().iloc[-1]) / price * 100 if price > 0 else 0.0
    else:
        atr_pct = 0.0
    ret_3m = _f((close.iloc[-1] - close.iloc[-63]) / close.iloc[-63] * 100) if len(close) >= 63 else 0.0
    score = 0
    if np.isfinite(vol_ratio):
        score += min(30, int((vol_ratio - 1.0) / 4.0 * 30))
    if np.isfinite(vs_52w) and vs_52w >= -20:
        score += max(0, int(25 + vs_52w * 1.25))
    if is_brk:
        score += 10 + min(10, int(breakout_pct * 5))
    if new_52w:
        score += 10
    if is_mover:
        score += 5
    score += min(10, max(0, int(abs(chg_pct) * 2)))
    score = max(0, min(100, score))
    badges = []
    if is_brk:   badges.append("Vol Breakout")
    if new_52w:  badges.append("New 52W High")
    elif is_52w: badges.append("52W Setup")
    if is_mover: badges.append(mover_label if mover_label else "Mover")
    return {
        "Ticker":      ticker,
        "Score":       score,
        "Signals":     " | ".join(badges) if badges else "---",
        "Price":       round(price, 3),
        "Chg %":       round(chg_pct, 2),
        "Vol Ratio":   round(vol_ratio, 2) if np.isfinite(vol_ratio) else float("nan"),
        "Today Vol":   today_vol,
        "vs 52W %":    round(vs_52w, 2),
        "In Range %":  round(in_range, 1),
        "Breakout %":  round(breakout_pct, 2) if is_brk else 0.0,
        "ATR %":       round(atr_pct, 2),
        "3M Return %": round(ret_3m, 1),
        "_new_52w":    new_52w,
        "Last Bar":    _fmt_sgt(close.index[-1]),
    }


@st.cache_data(ttl=300, show_spinner=False)
def _run_scan(tickers_tuple, market_key, breakout_days, vol_mult, w52_within,
              max_tickers, mover_symbols_frz, mover_bucket_items):
    tickers    = list(tickers_tuple)[:max_tickers]
    mover_dict = dict(mover_bucket_items)
    rows   = []
    errors = []
    for start in range(0, len(tickers), 80):
        chunk = tickers[start: start + 80]
        try:
            raw = yf.download(chunk, period="1y", interval="1d",
                              group_by="ticker", auto_adjust=True,
                              threads=True, progress=False)
        except Exception as exc:
            errors.append(f"batch {start}: {exc}")
            continue
        if raw is None or raw.empty:
            continue
        for sym in chunk:
            tdf = _extract_ticker_frame(raw, sym, chunk)
            if tdf.empty:
                continue
            try:
                row = _analyse(sym, tdf, breakout_days, vol_mult, w52_within,
                               mover_symbols_frz, mover_dict)
                if row:
                    rows.append(row)
            except Exception:
                continue
    df = pd.DataFrame(rows)
    if not df.empty:
        df["Score"] = pd.to_numeric(df["Score"], errors="coerce").fillna(0).astype(int)
        df = df.sort_values("Score", ascending=False).reset_index(drop=True)
    meta = {
        "market":    market_key,
        "scanned":   len(tickers),
        "hits":      len(df),
        "vol_brk":   int(df["Signals"].str.contains("Vol Breakout", na=False).sum()) if not df.empty else 0,
        "new_52w":   int(df["_new_52w"].sum()) if not df.empty else 0,
        "movers":    int(df["Signals"].str.contains("Mover", na=False).sum()) if not df.empty else 0,
        "refreshed": datetime.now(timezone.utc).astimezone().strftime("%H:%M:%S %Z"),
        "errors":    errors[:5],
    }
    return df, meta


def _fmt_df(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    for col, fmt in [("Chg %", "+.2f"), ("vs 52W %", "+.2f"),
                     ("Breakout %", "+.2f"), ("3M Return %", "+.1f")]:
        if col in d.columns:
            d[col] = pd.to_numeric(d[col], errors="coerce").map(
                lambda x, f=fmt: f"{x:{f}}%" if pd.notna(x) else "---")
    if "Price" in d.columns:
        d["Price"] = pd.to_numeric(d["Price"], errors="coerce").map(
            lambda x: f"{x:,.3f}" if pd.notna(x) else "---")
    if "Vol Ratio" in d.columns:
        d["Vol Ratio"] = pd.to_numeric(d["Vol Ratio"], errors="coerce").map(
            lambda x: f"{x:.2f}x" if pd.notna(x) and np.isfinite(x) else "---")
    if "Today Vol" in d.columns:
        d["Today Vol"] = d["Today Vol"].map(_fmt_vol)
    for col in ("In Range %", "ATR %"):
        if col in d.columns:
            d[col] = pd.to_numeric(d[col], errors="coerce").map(
                lambda x: f"{x:.1f}%" if pd.notna(x) else "---")
    return d


def render_breakout_scanner(g: dict) -> None:
    st.subheader("Breakout Scanner")
    st.caption(
        "Unified scanner: every stock scored across Vol Breakout, 52W High Setup, and Market Mover signals. "
        "Score 0-100 ranks all three combined. Market dropdown filters the universe."
    )
    st.markdown("---")

    r1, r2 = st.columns([1.1, 2.4])
    with r1:
        market_key = st.selectbox(
            "Market",
            ["US", "SGX", "India", "Hong Kong"],
            index=0,
            key="bk_market",
            help="Selects which market's stock pool to scan.",
        )

    uni_options = universe_options_for_market(market_key)
    uni_ids     = [u[0] for u in uni_options]
    uni_labels  = [u[1] for u in uni_options]

    with r2:
        uni_idx = st.selectbox(
            "Universe (stock pool to scan)",
            range(len(uni_labels)),
            format_func=lambda i: uni_labels[i],
            index=0,
            key="bk_uni_" + market_key,
            help="S&P 500 scans all ~500 components. All US combines S&P500 + NDX + Growth (~650 stocks).",
        )
    universe_id  = uni_ids[uni_idx]
    universe_lbl = uni_labels[uni_idx]

    p1, p2, p3, p4 = st.columns(4)
    with p1:
        max_tickers = st.slider("Max tickers", 50, 650, 300, 50, key="bk_max")
    with p2:
        breakout_days = st.slider("Breakout window (days)", 5, 60, 20, 5, key="bk_days")
    with p3:
        vol_mult = st.slider("Min vol ratio x", 1.5, 5.0, 2.0, 0.25, key="bk_vol")
    with p4:
        w52_within = st.slider("52W high within %", 1.0, 15.0, 5.0, 0.5, key="bk_52w")

    tickers = get_universe(market_key, universe_id)
    n_scan  = min(len(tickers), max_tickers)

    if not tickers:
        st.error(f"No tickers found for {market_key} / {universe_id}.")
        return

    st.caption(
        f"{market_key} | {universe_lbl} | "
        f"{len(tickers)} tickers available | scanning up to {n_scan}"
    )

    bc, nc = st.columns([1, 6])
    with bc:
        if st.button("Run Scanner", key="bk_run", type="primary"):
            _run_scan.clear()
            _get_mover_sets.clear()
            st.rerun()
    with nc:
        st.caption("Results cached 5 min. Click Run Scanner to force refresh.")

    # Fetch movers US-only - Yahoo screeners return US tickers regardless of region param
    if market_key == "US":
        with st.spinner("Fetching live US market movers..."):
            mover_frz, mover_items = _get_mover_sets(YAHOO_REGION["US"], 100)
    else:
        mover_frz   = frozenset()
        mover_items = tuple()

    with st.spinner(f"Scanning {n_scan} {market_key} stocks from {universe_lbl}..."):
        df, meta = _run_scan(
            tuple(tickers), market_key,
            breakout_days, vol_mult, w52_within, max_tickers,
            mover_frz, mover_items,
        )

    st.markdown("---")
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Stocks Found",    meta["hits"])
    m2.metric("Vol Breakouts",   meta["vol_brk"])
    m3.metric("New 52W Highs",   meta["new_52w"])
    m4.metric("Movers",          meta["movers"])
    m5.metric("Tickers Scanned", meta["scanned"])
    m6.metric("Refreshed",       meta["refreshed"])

    if meta.get("errors"):
        with st.expander("Fetch warnings"):
            for e in meta["errors"]:
                st.text(e)

    if df.empty:
        st.info("No results. Try lowering vol ratio, widening 52W %, or increasing max tickers.")
        return

    st.markdown("---")

    f1, f2, f3, f4 = st.columns([2, 2, 1.2, 1.2])
    with f1:
        search = st.text_input("Search ticker", "", key="bk_search",
                               placeholder="e.g. NVDA, D05.SI").strip().upper()
    with f2:
        sig_filter = st.multiselect(
            "Filter by signal",
            ["Vol Breakout", "52W Setup", "New 52W High", "Mover"],
            default=[], key="bk_sigf",
        )
    with f3:
        min_score = st.slider("Min Score", 0, 80, 0, 5, key="bk_minscore")
    with f4:
        sort_col = st.selectbox(
            "Sort by",
            ["Score", "Vol Ratio", "Chg %", "vs 52W %", "3M Return %", "Breakout %"],
            index=0, key="bk_sort",
        )

    rows_show = st.slider("Rows to show", 10, 100, 30, 10, key="bk_rows")

    view = df.copy()
    if search:
        view = view[view["Ticker"].str.upper().str.contains(search, na=False)]
    if sig_filter:
        mask = pd.Series(False, index=view.index)
        for sig in sig_filter:
            if sig == "New 52W High":
                mask = mask | view["_new_52w"].astype(bool)
            else:
                mask = mask | view["Signals"].str.contains(sig, na=False)
        view = view[mask]
    view = view[view["Score"] >= min_score]
    view = view.sort_values(sort_col, ascending=(sort_col == "vs 52W %")).head(rows_show)

    top3 = df[df["Score"] >= 40].head(3)
    if not top3.empty:
        st.markdown(f"#### Top Picks — {market_key} | {universe_lbl}")
        pcols = st.columns(len(top3))
        for i, (_, row) in enumerate(top3.iterrows()):
            with pcols[i]:
                chg = row.get("Chg %")
                st.metric(
                    label=f"#{i+1}  {row['Ticker']}",
                    value=f"{row['Price']:,.3f}",
                    delta=f"{chg:+.2f}%" if pd.notna(chg) else None,
                )
                vr = row.get("Vol Ratio", float("nan"))
                vs = row.get("vs 52W %",  float("nan"))
                parts = [f"Score: {row['Score']}"]
                if pd.notna(vr) and np.isfinite(vr):
                    parts.append(f"Vol: {vr:.1f}x")
                if np.isfinite(vs):
                    parts.append(f"52W: {vs:+.1f}%")
                st.markdown("  |  ".join(parts))
                st.caption(row.get("Signals", "---"))
        st.markdown("---")

    st.markdown(f"#### {len(view)} stocks  |  filtered from {len(df)}  |  {market_key} / {universe_lbl}")
    cols_show = ["Ticker","Score","Signals","Price","Chg %","Vol Ratio","Today Vol",
                 "vs 52W %","In Range %","Breakout %","ATR %","3M Return %","Last Bar"]
    cols_show = [c for c in cols_show if c in view.columns]
    st.dataframe(_fmt_df(view[cols_show]), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("#### Signal Breakdown")
    cc1, cc2 = st.columns(2)
    with cc1:
        st.markdown("**Score — top stocks**")
        sdf = view[["Ticker","Score"]].set_index("Ticker").head(20)
        if not sdf.empty:
            st.bar_chart(sdf)
    with cc2:
        st.markdown("**Volume Ratio — top stocks**")
        vdf = view[["Ticker","Vol Ratio"]].copy()
        vdf["Vol Ratio"] = pd.to_numeric(vdf["Vol Ratio"], errors="coerce")
        vdf = vdf.dropna().sort_values("Vol Ratio", ascending=False).set_index("Ticker").head(20)
        if not vdf.empty:
            st.bar_chart(vdf)

    st.markdown("**Signal counts across full scan**")
    st.bar_chart(pd.DataFrame({"Count": {
        "Vol Breakouts": meta["vol_brk"],
        "New 52W Highs": meta["new_52w"],
        "Market Movers": meta["movers"],
    }}))

    with st.expander("How the Score works"):
        st.markdown(f"""
Score 0-100 combines all three signals:

| Component | Condition | Max Pts |
|-----------|-----------|---------|
| Volume surge | Today vol vs 20-day avg | 30 |
| 52W proximity | Within {w52_within}% of 52-week high | 25 |
| Price breakout | Price > {breakout_days}-day high | 20 |
| New 52W High | Price = 52-week high | 10 |
| Market mover | Yahoo gainers/losers/active | 5 |
| Momentum | Abs daily Chg % | 10 |

Universe source: actual index components (S&P 500, NASDAQ 100, Nifty, Hang Seng) — not a curated watchlist.
        """)
