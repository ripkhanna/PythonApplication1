"""Top Movers / Losers tab.

Market-aware intraday movers dashboard.  This module is intentionally
separate from the main scanner so changing this tab does not affect the
long/short strategy engine.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable
import json
import urllib.parse
import urllib.request

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf


HK_VOLATILE_TICKERS = [
    "0700.HK","9988.HK","3690.HK","1810.HK","1024.HK","9618.HK","9888.HK","9999.HK","2015.HK","9868.HK",
    "1211.HK","0981.HK","2382.HK","2018.HK","6618.HK","1347.HK","0241.HK","9961.HK","3888.HK","6690.HK",
    "0772.HK","6611.HK","6060.HK","9992.HK","2318.HK","0388.HK","2331.HK","2333.HK","0175.HK","1929.HK",
    "0005.HK","0027.HK","0268.HK","0285.HK","0522.HK","0688.HK","0728.HK","0762.HK","0788.HK","0823.HK",
    "0857.HK","0880.HK","0883.HK","0939.HK","0960.HK","0968.HK","0992.HK","1088.HK","1093.HK","1109.HK",
    "1177.HK","1209.HK","1299.HK","1378.HK","1398.HK","1801.HK","1919.HK","1928.HK","2020.HK","2238.HK",
    "2268.HK","2269.HK","2359.HK","2628.HK","2688.HK","2899.HK","3800.HK","3968.HK","3988.HK","6030.HK",
    "6160.HK","6862.HK","6881.HK","6886.HK","6969.HK","9633.HK","9863.HK","9866.HK","9896.HK","9926.HK",
    "9969.HK","1128.HK","1336.HK","1658.HK","1776.HK","2007.HK","2282.HK","6066.HK","6098.HK","9600.HK",
]


MARKET_TZ = {
    "US": "America/New_York",
    "SGX": "Asia/Singapore",
    "India": "Asia/Kolkata",
    "Hong Kong": "Asia/Hong_Kong",
}

MARKET_LABEL = {
    "🇺🇸 US": "US",
    "🇸🇬 SGX": "SGX",
    "🇮🇳 India": "India",
    "🇭🇰 HK": "Hong Kong",
}

YAHOO_REGION = {
    "US": "US",
    "SGX": "SG",
    "India": "IN",
    "Hong Kong": "HK",
}

YAHOO_SCREENER_IDS = {
    "Top Gainers": "day_gainers",
    "Top Losers": "day_losers",
    "Most Active": "most_actives",
}


def _unique_keep_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        t = str(item or "").strip().upper()
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def _market_key_from_selection(selection: str, current_market_label: str) -> str:
    if selection == "Current selected market":
        return MARKET_LABEL.get(current_market_label, "US")
    return selection


def _tickers_for_market(g: dict, market_key: str) -> list[str]:
    if market_key == "US":
        return _unique_keep_order(g.get("US_TICKERS", []))
    if market_key == "SGX":
        return _unique_keep_order(g.get("SG_TICKERS", []))
    if market_key == "India":
        return _unique_keep_order(g.get("INDIA_TICKERS", []))
    if market_key == "Hong Kong":
        return _unique_keep_order(g.get("HK_TICKERS", HK_VOLATILE_TICKERS))
    return []


def _fmt_sgt(ts) -> str:
    if ts is None or str(ts).strip() == "":
        return "unknown"
    try:
        t = pd.to_datetime(ts, errors="coerce")
        if pd.isna(t):
            return str(ts)
        if t.tzinfo is None:
            t = t.tz_localize("UTC")
        return t.tz_convert("Asia/Singapore").strftime("%Y-%m-%d %H:%M:%S SGT")
    except Exception:
        return str(ts)


def _extract_ticker_frame(raw: pd.DataFrame, ticker: str, all_tickers: list[str]) -> pd.DataFrame:
    """Return OHLCV dataframe for one ticker from yfinance multi/single output."""
    if raw is None or raw.empty:
        return pd.DataFrame()

    if isinstance(raw.columns, pd.MultiIndex):
        # yfinance with group_by='ticker' usually gives level 0 = ticker.
        try:
            if ticker in raw.columns.get_level_values(0):
                return raw[ticker].dropna(how="all")
        except Exception:
            pass
        # Some versions return level 1 = ticker.
        try:
            if ticker in raw.columns.get_level_values(1):
                return raw.xs(ticker, axis=1, level=1).dropna(how="all")
        except Exception:
            pass
        return pd.DataFrame()

    # Single ticker download returns simple columns.
    if len(all_tickers) == 1:
        return raw.dropna(how="all")

    return pd.DataFrame()


def _row_from_intraday_df(ticker: str, df: pd.DataFrame, market_key: str) -> dict | None:
    if df is None or df.empty or "Close" not in df.columns:
        return None

    close = pd.to_numeric(df.get("Close"), errors="coerce").dropna()
    if close.empty:
        return None

    vol = pd.to_numeric(df.get("Volume", pd.Series(index=df.index, dtype=float)), errors="coerce").fillna(0)
    latest_price = float(close.iloc[-1])
    latest_ts = close.index[-1]

    tz = MARKET_TZ.get(market_key, "Asia/Singapore")
    try:
        idx = pd.DatetimeIndex(df.index)
        if idx.tz is None:
            # Yahoo intraday usually returns tz-aware timestamps.  If not, assume UTC.
            idx = idx.tz_localize("UTC")
        local_dates = idx.tz_convert(tz).date
    except Exception:
        local_dates = pd.to_datetime(df.index, errors="coerce").date

    close_by_date = pd.Series(close.values, index=pd.Index(local_dates[-len(close):])).groupby(level=0).last()
    if len(close_by_date) >= 2:
        prev_close = float(close_by_date.iloc[-2])
    elif len(close) >= 2:
        prev_close = float(close.iloc[-2])
    else:
        prev_close = np.nan

    if not np.isfinite(prev_close) or prev_close <= 0:
        return None

    change_pct = ((latest_price - prev_close) / prev_close) * 100.0

    # Current-day total volume vs previous daily average volume.
    vol_by_date = pd.Series(vol.values, index=pd.Index(local_dates[-len(vol):])).groupby(level=0).sum()
    today_volume = float(vol_by_date.iloc[-1]) if len(vol_by_date) else 0.0
    prev_avg_volume = float(vol_by_date.iloc[:-1].tail(4).mean()) if len(vol_by_date) > 1 else 0.0
    vol_ratio = today_volume / prev_avg_volume if prev_avg_volume > 0 else np.nan

    last_20_vol_avg = float(vol.tail(20).mean()) if len(vol) >= 3 else 0.0
    latest_bar_vol = float(vol.iloc[-1]) if len(vol) else 0.0
    bar_vol_ratio = latest_bar_vol / last_20_vol_avg if last_20_vol_avg > 0 else np.nan

    high = pd.to_numeric(df.get("High", close), errors="coerce").dropna()
    low = pd.to_numeric(df.get("Low", close), errors="coerce").dropna()
    day_high = float(high.tail(78).max()) if not high.empty else latest_price
    day_low = float(low.tail(78).min()) if not low.empty else latest_price

    return {
        "Ticker": ticker,
        "Price": latest_price,
        "Prev Close": prev_close,
        "Chg %": change_pct,
        "Today Volume": today_volume,
        "Vol Ratio": vol_ratio,
        "Last Bar Vol Ratio": bar_vol_ratio,
        "Day High": day_high,
        "Day Low": day_low,
        "Latest Bar SGT": _fmt_sgt(latest_ts),
    }



def _epoch_to_sgt(epoch_value) -> str:
    try:
        if epoch_value is None or (isinstance(epoch_value, float) and not np.isfinite(epoch_value)):
            return "unknown"
        ts = pd.to_datetime(int(epoch_value), unit="s", utc=True, errors="coerce")
        if pd.isna(ts):
            return "unknown"
        return ts.tz_convert("Asia/Singapore").strftime("%Y-%m-%d %H:%M:%S SGT")
    except Exception:
        return "unknown"


def _safe_quote_value(quote: dict, *names):
    for name in names:
        if name in quote and quote.get(name) is not None:
            val = quote.get(name)
            if isinstance(val, dict):
                if "raw" in val:
                    return val.get("raw")
                if "fmt" in val:
                    return val.get("fmt")
            return val
    return np.nan


def _quote_to_mover_row(quote: dict, source_bucket: str) -> dict | None:
    symbol = str(quote.get("symbol") or "").strip().upper()
    if not symbol:
        return None

    price = _safe_quote_value(quote, "regularMarketPrice", "postMarketPrice", "preMarketPrice")
    prev_close = _safe_quote_value(quote, "regularMarketPreviousClose")
    change_pct = _safe_quote_value(quote, "regularMarketChangePercent")
    volume = _safe_quote_value(quote, "regularMarketVolume", "averageDailyVolume3Month")
    market_time = _safe_quote_value(quote, "regularMarketTime")

    try:
        price = float(price)
    except Exception:
        price = np.nan
    try:
        prev_close = float(prev_close)
    except Exception:
        prev_close = np.nan
    try:
        change_pct = float(change_pct)
    except Exception:
        if np.isfinite(price) and np.isfinite(prev_close) and prev_close > 0:
            change_pct = ((price - prev_close) / prev_close) * 100.0
        else:
            change_pct = np.nan
    try:
        volume = float(volume)
    except Exception:
        volume = np.nan

    if not np.isfinite(change_pct):
        return None

    return {
        "Ticker": symbol,
        "Name": str(quote.get("shortName") or quote.get("longName") or ""),
        "Price": price,
        "Prev Close": prev_close,
        "Chg %": change_pct,
        "Today Volume": volume,
        "Vol Ratio": np.nan,
        "Last Bar Vol Ratio": np.nan,
        "Day High": _safe_quote_value(quote, "regularMarketDayHigh"),
        "Day Low": _safe_quote_value(quote, "regularMarketDayLow"),
        "Latest Bar SGT": _epoch_to_sgt(market_time),
        "Mover Source": source_bucket,
    }


def _fetch_yahoo_predefined_screener(region: str, screener_id: str, count: int) -> tuple[list[dict], str | None]:
    """Fetch Yahoo's own predefined market movers list.

    This is intentionally universe-independent.  It asks Yahoo for the market's
    top gainers / losers / most active symbols instead of starting from our
    scanner universe.  If Yahoo blocks or returns nothing, caller falls back to
    universe scanning.
    """
    params = urllib.parse.urlencode({
        "formatted": "false",
        "lang": "en-US",
        "region": region,
        "scrIds": screener_id,
        "count": int(count),
    })
    url = f"https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?{params}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json,text/plain,*/*",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
        result = (((payload or {}).get("finance") or {}).get("result") or [])
        quotes = (result[0].get("quotes") if result else []) or []
        return quotes, None
    except Exception as exc:
        return [], f"{screener_id}: {type(exc).__name__}: {exc}"


@st.cache_data(ttl=180, show_spinner=False)
def _download_market_movers_feed_cached(market_key: str, count_per_bucket: int) -> tuple[pd.DataFrame, dict]:
    region = YAHOO_REGION.get(market_key, "US")
    rows: list[dict] = []
    errors: list[str] = []
    seen: set[str] = set()

    for bucket_name, screener_id in YAHOO_SCREENER_IDS.items():
        quotes, err = _fetch_yahoo_predefined_screener(region, screener_id, int(count_per_bucket))
        if err:
            errors.append(err)
        for quote in quotes:
            row = _quote_to_mover_row(quote, bucket_name)
            if not row:
                continue
            key = row["Ticker"]
            # Keep first bucket assignment, but do not duplicate rows across tabs.
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)

    df = pd.DataFrame(rows)
    if not df.empty:
        for col in ["Chg %", "Today Volume", "Price", "Prev Close", "Day High", "Day Low"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["Chg %"]).sort_values("Chg %", ascending=False).reset_index(drop=True)

    latest_vals = []
    if not df.empty and "Latest Bar SGT" in df.columns:
        latest_vals = [v for v in df["Latest Bar SGT"].astype(str).tolist() if v and v != "unknown"]
    meta = {
        "market": market_key,
        "region": region,
        "rows": int(len(df)),
        "source": "Yahoo predefined market movers feed",
        "latest_bar_sgt": max(latest_vals) if latest_vals else "unknown",
        "refreshed_at_sgt": datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
        "errors": errors[:8],
    }
    return df, meta


@st.cache_data(ttl=180, show_spinner=False)
def _download_nonUS_movers_cached(tickers_tuple: tuple, market_key: str, max_tickers: int) -> tuple[pd.DataFrame, dict]:
    """Fetch movers for SGX / HK / India using yf.Ticker.fast_info.

    Why not the intraday download path for non-US?
    1. Yahoo predefined screeners (day_gainers etc.) are US-only — always empty for SG/HK/IN.
    2. yf.download with period='5d' interval='5m' returns empty for most .SI / .HK / .NS tickers.
    3. fast_info is a lightweight single-ticker call that reliably returns last_price,
       previous_close, last_volume, year_high for non-US exchange tickers.
    Parallelised with ThreadPoolExecutor for speed.
    """
    import concurrent.futures as _fut
    import contextlib as _cl
    import io as _io

    tickers = list(tickers_tuple)[:int(max_tickers)]
    rows: list[dict] = []
    errors: list[str] = []

    def _fetch_one(sym: str):
        try:
            with _cl.redirect_stderr(_io.StringIO()), _cl.redirect_stdout(_io.StringIO()):
                fi = yf.Ticker(sym).fast_info
            price = float(getattr(fi, "last_price",     None) or 0)
            prev  = float(getattr(fi, "previous_close", None) or 0)
            vol   = float(getattr(fi, "last_volume",    None) or 0)
            avg3m = float(getattr(fi, "three_month_average_volume", None) or 0)
            hi52  = float(getattr(fi, "year_high",  None) or 0)
            lo52  = float(getattr(fi, "year_low",   None) or 0)
            mktts = getattr(fi, "regular_market_time", None) or getattr(fi, "regularMarketTime", None)

            if price <= 0 or prev <= 0:
                return None
            chg_pct  = (price - prev) / prev * 100.0
            vol_ratio = vol / avg3m if avg3m > 0 else float("nan")
            return {
                "Ticker":            sym,
                "Price":             round(price, 3),
                "Prev Close":        round(prev,  3),
                "Chg %":             round(chg_pct, 2),
                "Today Volume":      vol,
                "Vol Ratio":         round(vol_ratio, 2) if np.isfinite(vol_ratio) else float("nan"),
                "Last Bar Vol Ratio":float("nan"),
                "Day High":          round(hi52, 3),   # best available; intraday not in fast_info
                "Day Low":           round(lo52, 3),
                "Latest Bar SGT":    _epoch_to_sgt(int(mktts)) if mktts else "unknown",
                "Mover Source":      market_key,
            }
        except Exception as e:
            errors.append(f"{sym}: {e}")
            return None

    workers = min(20, max(1, len(tickers)))
    with _fut.ThreadPoolExecutor(max_workers=workers) as ex:
        for result in ex.map(_fetch_one, tickers):
            if result:
                rows.append(result)

    df = pd.DataFrame(rows)
    if not df.empty:
        df["Chg %"] = pd.to_numeric(df["Chg %"], errors="coerce")
        df = df.dropna(subset=["Chg %"]).sort_values("Chg %", ascending=False).reset_index(drop=True)

    latest_vals = [v for v in df["Latest Bar SGT"].astype(str).tolist() if v and v != "unknown"] if not df.empty else []
    meta = {
        "market":          market_key,
        "source":          "fast_info parallel scan",
        "tickers_requested": len(tickers),
        "rows":            int(len(df)),
        "latest_bar_sgt":  max(latest_vals) if latest_vals else "unknown",
        "refreshed_at_sgt":datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
        "errors":          errors[:8],
    }
    return df, meta


@st.cache_data(ttl=180, show_spinner=False)
def _download_top_movers_cached(tickers_tuple: tuple[str, ...], market_key: str, period: str, interval: str, prepost: bool, max_tickers: int) -> tuple[pd.DataFrame, dict]:
    """Download intraday Yahoo data and calculate top movers/losers.

    Cache TTL is short because this tab is intended for live market monitoring.
    Strategy scans remain separate and are not affected by this function.
    """
    tickers = list(tickers_tuple)[: int(max_tickers)]
    rows: list[dict] = []
    errors: list[str] = []
    latest_seen = None

    # Chunk to reduce Yahoo failures on large universes.
    chunk_size = 80 if market_key == "US" else 60
    for start in range(0, len(tickers), chunk_size):
        chunk = tickers[start:start + chunk_size]
        if not chunk:
            continue
        try:
            raw = yf.download(
                tickers=chunk,
                period=period,
                interval=interval,
                group_by="ticker",
                auto_adjust=False,
                prepost=bool(prepost),
                threads=True,
                progress=False,
            )
        except Exception as exc:
            errors.append(f"{chunk[0]}..{chunk[-1]}: {type(exc).__name__}: {exc}")
            continue

        if raw is None or raw.empty:
            errors.append(f"{chunk[0]}..{chunk[-1]}: empty Yahoo response")
            continue

        for ticker in chunk:
            tdf = _extract_ticker_frame(raw, ticker, chunk)
            if tdf.empty:
                continue
            try:
                row = _row_from_intraday_df(ticker, tdf, market_key)
                if row:
                    rows.append(row)
                    latest_seen = tdf.index[-1]
            except Exception:
                continue

    df = pd.DataFrame(rows)
    if not df.empty:
        df["Chg %"] = pd.to_numeric(df["Chg %"], errors="coerce")
        df["Vol Ratio"] = pd.to_numeric(df["Vol Ratio"], errors="coerce")
        df["Last Bar Vol Ratio"] = pd.to_numeric(df["Last Bar Vol Ratio"], errors="coerce")
        df = df.dropna(subset=["Chg %"]).sort_values("Chg %", ascending=False).reset_index(drop=True)

    meta = {
        "market": market_key,
        "tickers_requested": len(tickers),
        "rows": int(len(df)),
        "period": period,
        "interval": interval,
        "latest_bar_sgt": _fmt_sgt(latest_seen),
        "refreshed_at_sgt": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
        "errors": errors[:8],
    }
    return df, meta


def _display_mover_table(df: pd.DataFrame, title: str, sort_col: str, ascending: bool, n: int) -> None:
    st.markdown(f"#### {title}")
    if df.empty:
        st.info("No rows available. Try Refresh movers or reduce the universe size.")
        return
    view = df.sort_values(sort_col, ascending=ascending).head(int(n)).copy()
    for col in ["Price", "Prev Close", "Day High", "Day Low"]:
        if col in view.columns:
            view[col] = pd.to_numeric(view[col], errors="coerce").map(lambda x: f"{x:,.3f}" if pd.notna(x) else "–")
    if "Chg %" in view.columns:
        view["Chg %"] = pd.to_numeric(view["Chg %"], errors="coerce").map(lambda x: f"{x:+.2f}%" if pd.notna(x) else "–")
    for col in ["Vol Ratio", "Last Bar Vol Ratio"]:
        if col in view.columns:
            view[col] = pd.to_numeric(view[col], errors="coerce").map(lambda x: f"{x:.2f}x" if pd.notna(x) and np.isfinite(x) else "–")
    if "Today Volume" in view.columns:
        view["Today Volume"] = pd.to_numeric(view["Today Volume"], errors="coerce").map(lambda x: f"{x:,.0f}" if pd.notna(x) else "–")
    st.dataframe(view, width="stretch", hide_index=True)


def render_top_movers(g: dict) -> None:
    st.subheader("🚀 Top Movers / Losers")
    st.caption("Market-aware intraday movers from Yahoo. Times are shown in Singapore time. Yahoo quotes may still be exchange-delayed.")

    current_market_label = g.get("market_sel", st.session_state.get("market_selector", "🇺🇸 US"))
    c1, c2, c3, c4 = st.columns([1.25, 1, 1, 1])
    with c1:
        market_choice = st.selectbox(
            "Market",
            ["Current selected market", "US", "SGX", "India", "Hong Kong"],
            index=0,
            key="top_movers_market",
        )
    market_key = _market_key_from_selection(market_choice, current_market_label)

    with c2:
        rows_to_show = st.slider("Rows", 5, 50, 15, 5, key="top_movers_rows")
    with c3:
        mover_count = st.slider("Movers per list", 25, 250, 100, 25, key="top_movers_feed_count")
    with c4:
        interval = st.selectbox("Fallback interval", ["5m", "15m", "1d"], index=0, key="top_movers_interval")

    use_market_feed = st.checkbox(
        "Use Yahoo market movers feed (US only), not scanner universe",
        value=(market_key == "US"),   # ← default True only for US; False for SGX/HK/India
        key="top_movers_use_feed",
        help="US: asks Yahoo for day gainers/losers/most active. SGX/HK/India: always uses fast_info universe scan (Yahoo screeners are US-only).",
    )

    period = "5d" if interval in ("5m", "15m") else "1mo"
    prepost = market_key == "US"
    tickers = _tickers_for_market(g, market_key)

    b1, b2 = st.columns([1, 5])
    with b1:
        if st.button("🔄 Refresh movers", key="refresh_top_movers"):
            _download_market_movers_feed_cached.clear()
            _download_top_movers_cached.clear()
            _download_nonUS_movers_cached.clear()
            st.rerun()
    with b2:
        if market_key != "US":
            st.caption(f"Market: **{market_key}** · source: **fast_info parallel scan** ({len(tickers)} tickers) · cache TTL **3 min**")
        elif use_market_feed:
            st.caption(f"Market: **{market_key}** · source: **Yahoo day gainers / losers / most active** · cache TTL **3 min**")
        else:
            st.caption(f"Fallback universe mode: **{market_key}** · requested up to **{min(len(tickers), mover_count)}** tickers · cache TTL **3 min**")

    # ── Data fetch: route by market ────────────────────────────────────────────
    # Non-US markets (SGX/HK/India): Yahoo predefined screeners are US-only and
    # always return empty for other regions. Use fast_info parallel scan instead.
    if market_key != "US":
        if not tickers:
            st.warning(f"No ticker universe found for {market_key}. Add tickers in the scanner sidebar.")
            return
        with st.spinner(f"Loading {market_key} movers via fast_info scan ({len(tickers)} tickers)…"):
            df, meta = _download_nonUS_movers_cached(tuple(tickers), market_key, int(mover_count))
        if df.empty:
            st.warning(
                f"No movers data returned for **{market_key}**. "
                "This usually means the market is closed or Yahoo has no recent prices for these tickers. "
                "Check that tickers are correct (e.g. `D05.SI`, `0700.HK`, `RELIANCE.NS`)."
            )
            if meta.get("errors"):
                with st.expander("Errors"):
                    st.write(meta["errors"])
            return

    elif use_market_feed:
        with st.spinner(f"Loading {market_key} movers directly from Yahoo market movers feed..."):
            df, meta = _download_market_movers_feed_cached(market_key, int(mover_count))
        if df.empty:
            st.warning("Yahoo market movers feed returned no rows. Falling back to scanner-universe intraday scan.")
            use_market_feed = False

    if market_key == "US" and not use_market_feed:
        if not tickers:
            st.warning(f"No ticker universe found for {market_key}.")
            return
        with st.spinner(f"Loading {market_key} movers from scanner universe fallback..."):
            df, meta = _download_top_movers_cached(tuple(tickers), market_key, period, interval, prepost, int(mover_count))

    source_label = meta.get("source") or "Scanner universe fallback"
    loaded_against = meta.get("tickers_requested", "Yahoo feed")
    st.success(
        f"Loaded **{meta.get('rows', 0)}** rows · Source: **{source_label}** · "
        f"Latest bar: **{meta.get('latest_bar_sgt', 'unknown')}**"
    )

    if meta.get("errors"):
        with st.expander("Yahoo warnings / skipped chunks"):
            st.write(meta.get("errors"))

    search = st.text_input("Search ticker", "", key="top_movers_search").strip().upper()
    if search and not df.empty:
        df = df[df["Ticker"].astype(str).str.upper().str.contains(search, na=False)]

    if df.empty:
        st.info("No movers data returned. Try smaller universe size, another interval, or Refresh movers.")
        return

    gainers, losers, volume = st.tabs(["Top Gainers", "Top Losers", "Volume Leaders"])
    with gainers:
        _display_mover_table(df[df["Chg %"] > 0], "Top Gainers", "Chg %", False, rows_to_show)
    with losers:
        _display_mover_table(df[df["Chg %"] < 0], "Top Losers", "Chg %", True, rows_to_show)
    with volume:
        vol_df = df.copy()
        # Prefer day-volume ratio; fallback to last-bar ratio.
        vol_df["_vol_sort"] = pd.to_numeric(vol_df["Vol Ratio"], errors="coerce").fillna(0)
        fallback = pd.to_numeric(vol_df["Last Bar Vol Ratio"], errors="coerce").fillna(0)
        vol_df["_vol_sort"] = np.maximum(vol_df["_vol_sort"], fallback)
        _display_mover_table(vol_df.drop(columns=["_vol_sort"], errors="ignore").assign(**{"Vol Sort": vol_df["_vol_sort"]}), "Volume Leaders", "Vol Sort", False, rows_to_show)
