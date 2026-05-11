"""Pre-Market Scanner tab — US stocks only, 4:00am–9:30am ET (4pm–9:30pm SGT).

Shows:
  • Live pre-market gappers with price, PM%, volume, sector, catalyst context
  • PM leaders sorted by absolute gap size
  • Warning banner when outside pre-market window
"""
from __future__ import annotations

import concurrent.futures as _fut
import contextlib as _cl
import io as _io
import datetime as _dt
from typing import Optional

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

# ── Market window helpers ──────────────────────────────────────────────────────

def _now_et() -> _dt.datetime:
    try:
        return _dt.datetime.now(_dt.timezone.utc).astimezone(
            __import__("zoneinfo").ZoneInfo("America/New_York")
        )
    except Exception:
        import pytz
        return _dt.datetime.now(pytz.timezone("America/New_York"))


def _now_sgt() -> _dt.datetime:
    try:
        return _dt.datetime.now(_dt.timezone.utc).astimezone(
            __import__("zoneinfo").ZoneInfo("Asia/Singapore")
        )
    except Exception:
        import pytz
        return _dt.datetime.now(pytz.timezone("Asia/Singapore"))


def _is_premarket_now() -> bool:
    """True between 4:00am and 9:29am ET on weekdays."""
    now = _now_et()
    if now.weekday() >= 5:
        return False
    mins = now.hour * 60 + now.minute
    return (4 * 60) <= mins < (9 * 60 + 30)


def _is_regular_session_now() -> bool:
    now = _now_et()
    if now.weekday() >= 5:
        return False
    mins = now.hour * 60 + now.minute
    return (9 * 60 + 30) <= mins <= (16 * 60)


def _session_label() -> str:
    now_et  = _now_et()
    now_sgt = _now_sgt()
    if now_et.weekday() >= 5:
        return "weekend", "⚫"
    mins = now_et.hour * 60 + now_et.minute
    if   mins < 4 * 60:          return "closed (pre-dawn)",      "⚫"
    elif mins < 9 * 60 + 30:     return "🌅 PRE-MARKET",           "🟡"
    elif mins <= 16 * 60:        return "📈 REGULAR SESSION",       "🟢"
    elif mins <= 20 * 60:        return "🌙 AFTER-HOURS",           "🔵"
    else:                        return "closed (overnight)",       "⚫"


# ── Data fetch ─────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3 * 60, show_spinner=False)   # 3-min cache — PM moves fast
def _fetch_premarket_data(tickers_tuple: tuple, min_gap_pct: float) -> pd.DataFrame:
    """Fetch pre-market and post-market data for all US tickers using fast_info + 1-min bars."""
    tickers  = list(tickers_tuple)
    rows: list[dict] = []

    def _one(sym: str) -> Optional[dict]:
        try:
            with _cl.redirect_stderr(_io.StringIO()), _cl.redirect_stdout(_io.StringIO()):
                fi = yf.Ticker(sym).fast_info

            # Pre-market fields
            pm_price  = float(getattr(fi, "pre_market_price",  None) or 0)
            prev_close= float(getattr(fi, "previous_close",    None) or 0)
            last_price= float(getattr(fi, "last_price",        None) or 0)
            last_vol  = float(getattr(fi, "last_volume",       None) or 0)
            avg3m_vol = float(getattr(fi, "three_month_average_volume", None) or 0)
            hi52      = float(getattr(fi, "year_high",         None) or 0)
            lo52      = float(getattr(fi, "year_low",          None) or 0)
            mktts     = getattr(fi, "regular_market_time",     None)

            # Use pre-market price if available, else last price
            ref_price = pm_price if pm_price > 0 else last_price
            if ref_price <= 0 or prev_close <= 0:
                return None

            pm_chg = (ref_price - prev_close) / prev_close * 100.0
            if abs(pm_chg) < min_gap_pct:
                return None

            vol_ratio = round(last_vol / avg3m_vol, 2) if avg3m_vol > 0 else float("nan")

            # Distance from 52w high/low
            hi52_dist = round((ref_price / hi52 - 1) * 100, 1) if hi52 > 0 else float("nan")
            lo52_dist = round((ref_price / lo52 - 1) * 100, 1) if lo52 > 0 else float("nan")

            # Format latest bar time in SGT
            if mktts:
                try:
                    ts = pd.Timestamp(int(mktts), unit="s", tz="UTC")
                    bar_sgt = ts.tz_convert("Asia/Singapore").strftime("%H:%M SGT")
                except Exception:
                    bar_sgt = "–"
            else:
                bar_sgt = "–"

            return {
                "Ticker":       sym,
                "PM Price":     round(ref_price, 2),
                "Prev Close":   round(prev_close, 2),
                "PM Chg %":     round(pm_chg, 2),
                "Vol Ratio":    vol_ratio,
                "52W High":     round(hi52, 2) if hi52 > 0 else float("nan"),
                "52W Low":      round(lo52, 2) if lo52 > 0 else float("nan"),
                "vs 52W Hi":    hi52_dist,
                "vs 52W Lo":    lo52_dist,
                "Last Updated": bar_sgt,
                "PM Source":    "PM" if pm_price > 0 else "LIVE",
            }
        except Exception:
            return None

    workers = min(25, max(1, len(tickers)))
    with _fut.ThreadPoolExecutor(max_workers=workers) as ex:
        for r in ex.map(_one, tickers):
            if r:
                rows.append(r)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["PM Chg %"] = pd.to_numeric(df["PM Chg %"], errors="coerce")
    df = df.dropna(subset=["PM Chg %"])
    # Sort by absolute gap descending (biggest movers first)
    df["_abs"] = df["PM Chg %"].abs()
    df = df.sort_values("_abs", ascending=False).drop(columns="_abs").reset_index(drop=True)
    return df


# ── Render ────────────────────────────────────────────────────────────────────

def render_premarket(g: dict) -> None:
    st.subheader("🌅 Pre-Market Scanner — US Stocks")

    # ── Session status banner ──────────────────────────────────────────────
    session_label, session_icon = _session_label()
    now_et  = _now_et()
    now_sgt = _now_sgt()
    is_pm   = _is_premarket_now()
    is_reg  = _is_regular_session_now()

    col_st, col_et, col_sg = st.columns([1, 1, 1])
    col_st.metric("Session",  session_label)
    col_et.metric("US Eastern", now_et.strftime("%H:%M ET %a"))
    col_sg.metric("Singapore",  now_sgt.strftime("%H:%M SGT"))

    if not is_pm and not is_reg:
        if now_et.weekday() >= 5:
            st.info("📅 Weekend — no pre-market activity. Pre-market opens Monday 4:00am ET (4:00pm SGT).")
        else:
            mins_et = now_et.hour * 60 + now_et.minute
            if mins_et < 4 * 60:
                mins_to_pm = 4 * 60 - mins_et
                st.info(f"⏰ Pre-market opens in **{mins_to_pm // 60}h {mins_to_pm % 60}m** (4:00am ET = 4:00pm SGT). Data will appear automatically.")
            else:
                st.info("🌙 After-hours session. Last pre-market data shown below may be stale.")

    st.caption(
        "Pre-market data from Yahoo Finance via `fast_info`. "
        "Available **4:00am–9:30am ET** (4:00pm–9:30pm SGT) on weekdays. "
        "During regular session: shows live intraday % instead. "
        "Refresh every 3 minutes automatically — click 🔄 to force refresh."
    )

    st.divider()

    # ── Controls ──────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
    with c1:
        min_gap = st.slider("Min gap %", 0.5, 10.0, 2.0, 0.5, key="pm_min_gap",
                            help="Minimum absolute PM gap to show. 2% = meaningful catalyst. 5% = significant gap.")
    with c2:
        show_n = st.slider("Show top N", 5, 100, 30, 5, key="pm_show_n")
    with c3:
        direction = st.radio("Direction", ["All", "Gapping Up ↑", "Gapping Down ↓"],
                             horizontal=True, key="pm_direction")
    with c4:
        st.write("")
        st.write("")
        do_refresh = st.button("🔄 Refresh", key="pm_refresh")
        if do_refresh:
            _fetch_premarket_data.clear()
            st.rerun()

    # ── Ticker universe — US only ─────────────────────────────────────────
    us_tickers = [
        t for t in g.get("US_TICKERS", [])
        if t and not str(t).endswith((".SI", ".HK", ".NS", ".BO"))
    ]
    # Add any always-include tickers
    extra_raw = st.text_input(
        "➕ Add tickers (comma-separated)",
        placeholder="IREN, NVDA, TSLA",
        key="pm_extra_tickers",
    ).strip().upper()
    if extra_raw:
        extra_list = [t.strip() for t in extra_raw.split(",") if t.strip()]
        us_tickers = list(dict.fromkeys(extra_list + us_tickers))

    max_scan = st.slider("Max tickers to scan", 50, 500, 200, 50, key="pm_max_scan",
                         help="More tickers = more complete results but slower fetch (~8s per 100)")

    us_tickers = us_tickers[:max_scan]

    # ── Fetch ─────────────────────────────────────────────────────────────
    with st.spinner(f"Scanning {len(us_tickers)} US tickers for pre-market data…"):
        df = _fetch_premarket_data(tuple(us_tickers), float(min_gap))

    if df.empty:
        if is_pm:
            st.warning(
                f"No pre-market gaps found ≥ {min_gap}% in {len(us_tickers)} tickers. "
                "Market may be very quiet or Yahoo data is loading. Try 🔄 Refresh or lower Min gap %."
            )
        else:
            st.info(
                f"Outside pre-market window. Showing any available live data. "
                f"No moves ≥ {min_gap}% found in {len(us_tickers)} tickers. "
                "Pre-market data is available 4:00am–9:30am ET (4pm–9:30pm SGT)."
            )
        return

    # ── Filter by direction ───────────────────────────────────────────────
    if direction == "Gapping Up ↑":
        df = df[df["PM Chg %"] > 0]
    elif direction == "Gapping Down ↓":
        df = df[df["PM Chg %"] < 0]

    if df.empty:
        st.info(f"No {direction.lower()} moves found at ≥ {min_gap}%.")
        return

    # ── Summary metrics ───────────────────────────────────────────────────
    gainers  = (df["PM Chg %"] > 0).sum()
    losers   = (df["PM Chg %"] < 0).sum()
    avg_gap  = df["PM Chg %"].abs().mean()
    big_move = df.iloc[0]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total gappers",    f"{len(df)}")
    m2.metric("Gapping up ↑",     f"{gainers}", delta=f"+{gainers}")
    m3.metric("Gapping down ↓",   f"{losers}",  delta=f"-{losers}", delta_color="inverse")
    m4.metric("Avg gap size",     f"{avg_gap:.1f}%")

    if len(big_move) > 0:
        chg = big_move["PM Chg %"]
        icon = "🚀" if chg > 0 else "💥"
        st.success(
            f"{icon} **Biggest mover:** {big_move['Ticker']} "
            f"{'↑' if chg > 0 else '↓'} **{chg:+.1f}%** at ${big_move['PM Price']:.2f} "
            f"(prev close ${big_move['Prev Close']:.2f}) · "
            f"Last update: {big_move['Last Updated']} · "
            f"Vol Ratio: {big_move['Vol Ratio'] if pd.notna(big_move['Vol Ratio']) else '–'}"
        )

    st.divider()

    # ── Gainers / Losers tabs ─────────────────────────────────────────────
    t_all, t_up, t_down = st.tabs([
        f"📊 All ({len(df)})",
        f"🟢 Gapping Up ({gainers})",
        f"🔴 Gapping Down ({losers})",
    ])

    def _show_pm_table(data: pd.DataFrame, title: str) -> None:
        if data.empty:
            st.info(f"No {title} results.")
            return
        view = data.head(show_n).reset_index(drop=True).copy()

        # Format columns for display
        def _fmt_chg(x):
            if pd.isna(x): return "–"
            arrow = "↑" if x > 0 else "↓"
            clr   = "🟢" if x > 3 else ("📈" if x > 0 else ("🔴" if x < -3 else "📉"))
            return f"{clr} {arrow}{abs(x):.2f}%"

        def _fmt_vr(x):
            if pd.isna(x) or not np.isfinite(x): return "–"
            tag = "🔥" if x >= 3 else ("✅" if x >= 1.5 else "")
            return f"{tag} {x:.2f}×"

        def _fmt_52w(pct, dist):
            if pd.isna(pct) or pd.isna(dist): return "–"
            arrow = "↑" if dist > 0 else "↓"
            return f"${pct:,.2f} ({arrow}{abs(dist):.1f}%)"

        disp = view[["Ticker","PM Source","PM Price","Prev Close","PM Chg %",
                      "Vol Ratio","vs 52W Hi","vs 52W Lo","Last Updated"]].copy()
        disp["PM Chg %"]   = view["PM Chg %"].apply(_fmt_chg)
        disp["Vol Ratio"]  = view["Vol Ratio"].apply(_fmt_vr)
        disp["PM Price"]   = view["PM Price"].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "–")
        disp["Prev Close"] = view["Prev Close"].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "–")
        disp["vs 52W Hi"]  = view["vs 52W Hi"].apply(lambda x: f"{x:+.1f}%" if pd.notna(x) else "–")
        disp["vs 52W Lo"]  = view["vs 52W Lo"].apply(lambda x: f"+{x:.1f}%" if pd.notna(x) else "–")

        st.dataframe(
            disp,
            width="stretch",
            hide_index=True,
            column_config={
                "Ticker":      st.column_config.TextColumn("Ticker",      width=70),
                "PM Source":   st.column_config.TextColumn("Source",      width=55,
                    help="PM = true pre-market price. LIVE = regular session price used."),
                "PM Price":    st.column_config.TextColumn("PM Price",    width=80),
                "Prev Close":  st.column_config.TextColumn("Prev Close",  width=85),
                "PM Chg %":    st.column_config.TextColumn("PM Chg %",    width=100),
                "Vol Ratio":   st.column_config.TextColumn("Vol Ratio",   width=85),
                "vs 52W Hi":   st.column_config.TextColumn("vs 52W Hi",   width=80,
                    help="Distance from 52-week high. Near high = breakout candidate."),
                "vs 52W Lo":   st.column_config.TextColumn("vs 52W Lo",   width=80),
                "Last Updated":st.column_config.TextColumn("Last Bar",    width=80),
            },
        )
        st.caption(f"Showing {min(show_n, len(data))} of {len(data)} results. Sorted by |PM Chg %| descending.")

    with t_all:
        _show_pm_table(df, "all gappers")

    with t_up:
        _show_pm_table(df[df["PM Chg %"] > 0].copy(), "upside gappers")

    with t_down:
        _show_pm_table(df[df["PM Chg %"] < 0].copy(), "downside gappers")

    # ── PSM cross-reference ───────────────────────────────────────────────
    st.divider()
    df_long_master = g.get("df_long_master")
    if not isinstance(df_long_master, pd.DataFrame):
        df_long_master = pd.DataFrame()
    if not df_long_master.empty and "Ticker" in df_long_master.columns:
        pm_tickers = set(df["Ticker"].tolist())
        in_scan    = df_long_master[df_long_master["Ticker"].isin(pm_tickers)]
        if not in_scan.empty:
            st.markdown("#### 🎯 Pre-market movers also in Long Setups scan")
            # Merge PM% into scan results for context
            pm_lookup = (
                df.drop_duplicates(subset=["Ticker"])
                  .set_index("Ticker")[["PM Chg %","PM Price","Vol Ratio"]]
                  .to_dict("index")
            )
            cross = in_scan.reset_index(drop=True).copy()
            cross["PM Chg %"] = cross["Ticker"].map(lambda t: f"{pm_lookup.get(t,{}).get('PM Chg %',0):+.2f}%" if t in pm_lookup else "–")
            disp_cols = [c for c in ["Ticker","Action","PM Chg %","Entry Quality","Rise Prob","Vol Ratio","Sector"] if c in cross.columns]
            st.dataframe(cross[disp_cols].head(15), width="stretch", hide_index=True)
            st.caption("These stocks have a pre-market move AND appeared in your last scanner run — highest priority watchlist.")
        else:
            st.info("No overlap between pre-market gappers and last scan results. Run a fresh scan to cross-reference.")
    else:
        st.info("Run a scan first to cross-reference pre-market gappers with PSM strategy picks.")
