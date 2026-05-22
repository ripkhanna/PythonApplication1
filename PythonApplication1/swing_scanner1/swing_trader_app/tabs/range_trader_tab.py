"""
Range Trader Tab  —  v15.2
Finds stocks oscillating in a price channel and gives exact
BUY (near range floor) and SELL (near range ceiling) levels.

v15.2 fixes:
  - Slider min/max crash fixed (safe clamping)
  - Two scan modes: (A) your scanned universe, (B) built-in blue-chip list
  - Rolling-percentile support/resistance (works without pivot points)
  - Slope threshold raised to 1.5%/day (inclusive of mild trends)
  - Min bounces default = 1, with option for 0 (show all range structures)
  - Debug column shows WHY each stock was rejected
"""

import time
import pandas as pd
import numpy as np
import streamlit as st

def _bind_runtime(ctx: dict) -> None:
    globals().update(ctx)


def _get_market_tickers(market_key: str) -> list:
    """Get the full ticker universe for a market — same source as all other tabs."""
    try:
        from swing_trader_app.tabs.universe_data import get_tickers_for_market
        return get_tickers_for_market(market_key)
    except ImportError:
        pass
    import streamlit as _st, pandas as _pd
    df = _st.session_state.get("df_long", _pd.DataFrame())
    if isinstance(df, _pd.DataFrame) and not df.empty and "Ticker" in df.columns:
        return df["Ticker"].dropna().unique().tolist()
    return []


# ── Technical helpers ────────────────────────────────────────────────────────

def _rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(com=n-1, min_periods=max(1,n//2)).mean()
    loss = (-delta.clip(upper=0)).ewm(com=n-1, min_periods=max(1,n//2)).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


def _slope_pct_day(series: pd.Series) -> float:
    if len(series) < 5: return 0.0
    x = np.arange(len(series), dtype=float)
    y = series.values.astype(float)
    mask = ~np.isnan(y)
    if mask.sum() < 5: return 0.0
    c = np.polyfit(x[mask], y[mask], 1)
    return float(c[0] / max(float(np.nanmean(y)), 1e-6) * 100)


def _support_resistance_robust(high: pd.Series, low: pd.Series,
                                close: pd.Series) -> tuple:
    """Rolling-percentile S/R — works even when there are no pivot points."""
    look = len(close)
    # Method 1: rolling percentiles (always works)
    h_arr = high.values.astype(float)
    l_arr = low.values.astype(float)

    resistance = float(np.nanpercentile(h_arr, 80))  # 80th pct of highs
    support    = float(np.nanpercentile(l_arr, 20))  # 20th pct of lows

    # Method 2: pivot points (for confirmation when available)
    ph, pl = [], []
    for i in range(2, look - 2):
        if h_arr[i] > h_arr[i-1] and h_arr[i] > h_arr[i-2] and \
           h_arr[i] > h_arr[i+1] and h_arr[i] > h_arr[i+2]:
            ph.append(h_arr[i])
        if l_arr[i] < l_arr[i-1] and l_arr[i] < l_arr[i-2] and \
           l_arr[i] < l_arr[i+1] and l_arr[i] < l_arr[i+2]:
            pl.append(l_arr[i])

    if len(ph) >= 2:
        resistance = float(np.percentile(ph, 65))
    if len(pl) >= 2:
        support = float(np.percentile(pl, 35))

    return round(float(support), 4), round(float(resistance), 4)


def _count_range_touches(close: pd.Series, floor: float,
                         ceiling: float, tol: float = 0.03) -> tuple:
    """Count floor touches and ceiling touches separately."""
    floor_touches   = int((close <= floor * (1 + tol)).sum())
    ceiling_touches = int((close >= ceiling * (1 - tol)).sum())
    return floor_touches, ceiling_touches


def _normalise_cols(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        PRICE = {"open","high","low","close","volume","adj close","adjclose"}
        lvl0 = [str(v).lower() for v in df.columns.get_level_values(0)]
        df.columns = df.columns.get_level_values(0) if any(v in PRICE for v in lvl0) \
                     else df.columns.get_level_values(1)
    if "Adj Close" in df.columns and "Close" not in df.columns:
        df = df.rename(columns={"Adj Close": "Close"})
    # normalise column names to Title Case
    col_map = {c: c.title() for c in df.columns}
    df = df.rename(columns=col_map)
    return df


def _fetch(ticker: str, period: str = "3mo") -> pd.DataFrame:
    try:
        import yfinance as yf
        df = yf.download(ticker, period=period, interval="1d",
                         progress=False, auto_adjust=True)
        if df.empty: return pd.DataFrame()
        df = _normalise_cols(df)
        needed = {"Open","High","Low","Close","Volume"}
        if not needed.issubset(set(df.columns)):
            # Try lowercase fallback
            df.columns = [c.title() for c in df.columns]
        if not needed.issubset(set(df.columns)):
            return pd.DataFrame()
        return df.dropna(subset=["Close"])
    except Exception:
        return pd.DataFrame()


def _analyse_range(ticker: str, max_range: float, max_slope: float,
                   min_floor_touches: int) -> dict | None:
    """Returns result dict or None. Reason for rejection stored in _reject."""
    df = _fetch(ticker, "3mo")
    if len(df) < 15:
        df = _fetch(ticker, "6mo")
    if len(df) < 15:
        return None  # not enough data

    close = df["Close"].squeeze().astype(float)
    high  = df["High"].squeeze().astype(float)
    low   = df["Low"].squeeze().astype(float)
    vol   = df["Volume"].squeeze().astype(float)
    look  = min(len(close), 45)

    support, resistance = _support_resistance_robust(
        high.iloc[-look:], low.iloc[-look:], close.iloc[-look:]
    )

    if resistance <= support * 1.01:
        return None  # degenerate range

    rng_w_pct = (resistance - support) / support * 100

    if rng_w_pct > max_range:
        return None  # too volatile

    if rng_w_pct < 3.5:
        return None  # range too narrow to trade

    slope = abs(_slope_pct_day(close.iloc[-look:]))
    if slope > max_slope:
        return None  # trending too strongly

    ft, ct = _count_range_touches(close.iloc[-look:], support, resistance)
    if ft < min_floor_touches and ct < min_floor_touches:
        return None  # price never visited the range extremes

    # Current metrics
    price     = float(close.iloc[-1])
    rsi14     = float(_rsi(close).iloc[-1])
    avg_vol   = float(vol.iloc[-20:].mean()) if len(vol) >= 5 else 1.0
    vol_ratio = round(float(vol.iloc[-1]) / max(avg_vol, 1), 2)

    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs()
    ], axis=1).max(axis=1)
    atr     = float(tr.rolling(14, min_periods=5).mean().iloc[-1])
    atr_pct = round(atr / max(price, 0.01) * 100, 2)

    rng_pos = max(0.0, min(100.0, (price - support) / max(resistance - support, 0.0001) * 100))

    # Trade levels
    buy_at   = round(support    * 1.005, 4)
    sell_at  = round(resistance * 0.995, 4)
    stop_buy = round(support    * 0.975, 4)
    rr_buy   = round((sell_at - buy_at) / max(buy_at - stop_buy, 0.0001), 2)

    # Signal
    near_sup = price <= support * 1.03
    near_res = price >= resistance * 0.97

    if near_sup and rsi14 < 55:
        signal = "🟢 BUY"
        reason = f"Near support ${support:.2f} · RSI {rsi14:.0f}"
        conf   = min(92, 60 + max(0, 50 - rsi14) + max(0, 3 - rng_pos/10) * 5)
    elif near_res and rsi14 > 45:
        signal = "🔴 SELL / EXIT"
        reason = f"Near resistance ${resistance:.2f} · RSI {rsi14:.0f}"
        conf   = min(92, 58 + max(0, rsi14 - 50) + max(0, (rng_pos - 90) / 2))
    elif rng_pos < 35:
        signal = "👀 WATCH BUY"
        reason = f"Lower half ({rng_pos:.0f}%) · wait for RSI < 55 at ${support:.2f}"
        conf   = 55
    elif rng_pos > 65:
        signal = "⏳ NEAR SELL"
        reason = f"Upper half ({rng_pos:.0f}%) · prepare exit near ${resistance:.2f}"
        conf   = 50
    else:
        signal = "⏸ MID-RANGE"
        reason = f"Mid-channel ({rng_pos:.0f}%) · no edge here, wait"
        conf   = 40

    return {
        "Ticker":        ticker,
        "Price":         round(price, 2),
        "Signal":        signal,
        "Reason":        reason,
        "Confidence":    int(conf),
        "Support":       round(support, 2),
        "Resistance":    round(resistance, 2),
        "Range Width%":  round(rng_w_pct, 1),
        "Range Pos%":    round(rng_pos, 1),
        "Buy at":        round(buy_at, 2),
        "Sell at":       round(sell_at, 2),
        "Stop (buy)":    round(stop_buy, 2),
        "R:R (buy)":     rr_buy,
        "RSI":           round(rsi14, 1),
        "ATR%":          atr_pct,
        "Vol Ratio":     vol_ratio,
        "Floor Touches": ft,
        "Ceil Touches":  ct,
        "Slope%/day":    round(slope, 3),
    }


# ── Tab renderer ──────────────────────────────────────────────────────────────

def render_range_trader(ctx: dict) -> None:
    _bind_runtime(ctx)
    st.caption("📦 Range Trader — Exact Buy & Sell in Oscillating Stocks")

    # ── Universe selector ─────────────────────────────────────────────────────
    # Market follows the top radio button (same as all other tabs)
    market_u = st.session_state.get("market_selector", "🇺🇸 US")
    is_sgx_rt = "SGX" in str(market_u)
    st.caption(f"Market: **{market_u}** (follows the top radio button)")

    universe_mode = st.selectbox(
        "Scan universe",
        ["🌍 Full market universe (same as main scan)",
         "🔍 Scanned results only (last scan tickers)",
         "✏️ Custom tickers (enter below)"],
        key="rt_universe_mode",
        help="Full market universe uses all tickers for the selected market — same list the main scanner uses."
    )

    if universe_mode == "✏️ Custom tickers (enter below)":
        custom_raw = st.text_area(
            "Enter tickers (comma or newline separated)",
            placeholder="AAPL, MSFT, KO, PEP, D05.SI ...",
            key="rt_custom_tickers", height=80
        )
        tickers_src = [t.strip().upper() for t in custom_raw.replace("\n",",").split(",") if t.strip()]
    elif universe_mode == "🔍 Scanned results only (last scan tickers)":
        df_long = st.session_state.get("df_long", pd.DataFrame())
        if df_long is None or (isinstance(df_long, pd.DataFrame) and df_long.empty):
            st.warning("Run a **🚀 Scan** first to populate the scanned universe.", icon="⚠️")
            tickers_src = []
        else:
            tickers_src = df_long["Ticker"].dropna().unique().tolist()
    else:
        tickers_src = _get_market_tickers(market_u)

    if not tickers_src:
        st.info("No tickers to scan. Select a universe above or enter custom tickers.")
        return

    # ── Parameters ────────────────────────────────────────────────────────────
    pc1, pc2, pc3, pc4 = st.columns(4)
    with pc1:
        max_range = st.slider("Max range width %", 8, 50, 30, key="rt_max_range",
                              help="Max % between support and resistance")
    with pc2:
        max_slope = st.slider("Max slope %/day", 0.1, 2.0, 1.5, step=0.1,
                              key="rt_slope",
                              help="Higher = allows trending stocks; lower = flat range only")
    with pc3:
        min_touches = st.selectbox("Min touches at floor/ceiling",
                                   [0, 1, 2, 3], index=1, key="rt_min_touches",
                                   help="Min times price visited support or resistance zone")
    with pc4:
        sig_filter = st.multiselect(
            "Show signals",
            ["🟢 BUY","🔴 SELL / EXIT","👀 WATCH BUY","⏳ NEAR SELL","⏸ MID-RANGE"],
            default=["🟢 BUY","🔴 SELL / EXIT","👀 WATCH BUY"],
            key="rt_sigs"
        )

    # Safe slider for max tickers (no crash when universe is small)
    n_src = max(len(tickers_src), 1)
    sl_min = min(5,  n_src)
    sl_max = min(200, n_src)
    sl_max = max(sl_max, sl_min + 1)   # ensure max > min
    sl_def = max(sl_min, min(60, n_src))
    sl_def = min(sl_def, sl_max)

    max_scan = st.slider(
        f"Max tickers to scan (universe: {n_src})",
        min_value=sl_min, max_value=sl_max,
        value=sl_def, step=max(1, (sl_max - sl_min) // 10),
        key="rt_max_scan"
    )

    col_btn, col_hint = st.columns([1, 3])
    run = col_btn.button("🔄 Scan for ranges", type="primary", key="rt_run")
    col_hint.caption(
        "Tip: The full market universe gives the most results. "
        "If 0 results: increase **Max range width %**, raise **Max slope**, or set **Min touches = 0**."
    )

    if not run and "rt_results" not in st.session_state:
        with st.expander("📖 How range trading works", expanded=True):
            st.markdown("""
**The range trading edge — why it works:**

Stocks oscillate between a support floor and resistance ceiling. Professionals exploit this by buying the dip to support and selling the rally to resistance — repeatedly.

| Signal | Meaning | Action |
|---|---|---|
| 🟢 **BUY** | Price within 3% of support + RSI < 55 | Enter long at **Buy at** price |
| 🔴 **SELL / EXIT** | Price within 3% of resistance + RSI > 45 | Close long at **Sell at** price |
| 👀 **WATCH BUY** | Lower half of channel, not yet at floor | Monitor — enter when RSI drops |
| ⏳ **NEAR SELL** | Upper half, approaching ceiling | Prepare to exit |
| ⏸ **MID-RANGE** | Middle of channel | No edge — wait |

**Stop rule:** Always stop out 2.5% below support. If the floor breaks, the range is over — exit immediately.

**Tip:** The full market universe covers all tickers for the selected market — same as the main scanner. The slope filter naturally removes trending stocks, leaving only the oscillating ones.
            """)
        return

    if run:
        tickers = tickers_src[:max_scan]
        results, errors, rejected = [], [], []
        prog = st.progress(0, text=f"Scanning {len(tickers)} tickers for range structures…")

        for i, ticker in enumerate(tickers):
            prog.progress((i+1)/len(tickers),
                          text=f"Checking {ticker} ({i+1}/{len(tickers)})…")
            try:
                r = _analyse_range(ticker, max_range, max_slope, min_touches)
                if r:
                    results.append(r)
                else:
                    rejected.append(ticker)
            except Exception as e:
                errors.append(f"{ticker}: {e}")
            time.sleep(0.04)

        prog.empty()
        st.session_state["rt_results"]  = results
        st.session_state["rt_rejected"] = rejected
        st.session_state["rt_errors"]   = errors
        st.session_state["rt_n_scan"]   = len(tickers)

    results  = st.session_state.get("rt_results",  [])
    rejected = st.session_state.get("rt_rejected", [])
    errors   = st.session_state.get("rt_errors",   [])
    n_scan   = st.session_state.get("rt_n_scan",   0)

    st.caption(
        f"Scanned {n_scan} · **{len(results)} range-bound** · "
        f"{len(rejected)} trending/no-range · {len(errors)} data errors"
    )

    if errors and st.checkbox("Show fetch errors", key="rt_show_err"):
        st.code("\n".join(errors[:15]))

    if not results:
        st.warning(
            "**No range-bound stocks found** with current settings.\n\n"
            "Try these adjustments:\n"
            
            "- Increase **Max range width %** to 40–50%\n"
            "- Increase **Max slope** to 1.5–2.0 (allows mild trends)\n"
            "- Set **Min touches = 0** (show all range structures)\n"
            "- Increase tickers to scan"
        )
        return

    df_r = pd.DataFrame(results)
    if sig_filter:
        df_r = df_r[df_r["Signal"].isin(sig_filter)]
    if df_r.empty:
        st.warning("No stocks match selected signal filters — try adding more signals above.")
        return

    sig_order = {"🟢 BUY":0,"🔴 SELL / EXIT":1,"👀 WATCH BUY":2,"⏳ NEAR SELL":3,"⏸ MID-RANGE":4}
    df_r["_ord"] = df_r["Signal"].map(sig_order).fillna(5)
    df_r = df_r.sort_values(["_ord","Confidence"], ascending=[True,False]).reset_index(drop=True)

    # Summary
    vc = df_r["Signal"].value_counts()
    sm1, sm2, sm3, sm4 = st.columns(4)
    sm1.metric("Range stocks",    len(df_r))
    sm2.metric("🟢 BUY",          vc.get("🟢 BUY", 0))
    sm3.metric("🔴 SELL / EXIT",   vc.get("🔴 SELL / EXIT", 0))
    sm4.metric("👀 Watch buy",     vc.get("👀 WATCH BUY", 0))
    st.divider()

    # Cards
    for _, row in df_r.iterrows():
        ticker  = row["Ticker"]
        signal  = row["Signal"]
        conf    = row["Confidence"]
        price   = row["Price"]
        support = row["Support"]
        resist  = row["Resistance"]
        rng_w   = row["Range Width%"]
        rng_pos = row["Range Pos%"]
        buy_at  = row["Buy at"]
        sell_at = row["Sell at"]
        stop_b  = row["Stop (buy)"]
        rr      = row["R:R (buy)"]
        rsi     = row["RSI"]
        atr_pct = row["ATR%"]
        ft      = row["Floor Touches"]
        ct      = row["Ceil Touches"]
        reason  = row["Reason"]

        sc = {"🟢 BUY":("#E1F5EE","#0A9C6A"),
              "🔴 SELL / EXIT":("#FCEBEB","#A32D2D"),
              "👀 WATCH BUY":("#FAEEDA","#633806"),
              "⏳ NEAR SELL":("#FFF5E0","#BA7517"),
              "⏸ MID-RANGE":("#F1EFE8","#5F5E5A")}.get(signal,("#F1EFE8","#5F5E5A"))

        with st.container():
            h1, h2 = st.columns([3,1])
            with h1:
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:2px">'
                    f'<span style="font-size:17px;font-weight:600">{ticker}</span>'
                    f'<span style="background:{sc[0]};color:{sc[1]};font-size:12px;'
                    f'padding:2px 10px;border-radius:4px;font-weight:500">{signal}</span>'
                    f'<span style="font-size:11px;color:#888">Confidence {conf}%</span></div>',
                    unsafe_allow_html=True)
                st.caption(reason)
            with h2:
                st.markdown(
                    f'<div style="text-align:right">'
                    f'<div style="font-size:18px;font-weight:600">${price}</div>'
                    f'<div style="font-size:11px;color:#888">RSI {rsi} · ATR {atr_pct}%</div></div>',
                    unsafe_allow_html=True)

            bp = min(max(rng_pos,0),100)
            bc = "#1D9E75" if rng_pos<35 else ("#E24B4A" if rng_pos>65 else "#BA7517")
            st.markdown(
                f'<div style="margin:6px 0 4px">'
                f'<div style="display:flex;justify-content:space-between;font-size:10px;'
                f'color:#888;margin-bottom:3px">'
                f'<span>Support ${support}&nbsp;(floor touches: {ft})</span>'
                f'<span style="font-weight:500;color:{bc}">● {rng_pos:.0f}%</span>'
                f'<span>Resistance ${resist}&nbsp;(ceiling touches: {ct})</span></div>'
                f'<div style="height:8px;background:#e0e0e0;border-radius:4px;position:relative">'
                f'<div style="position:absolute;left:{bp}%;top:-4px;width:16px;height:16px;'
                f'background:{bc};border-radius:50%;transform:translateX(-50%);'
                f'border:2px solid white"></div>'
                f'<div style="height:8px;width:{bp}%;background:{bc};'
                f'border-radius:4px;opacity:0.25"></div></div></div>',
                unsafe_allow_html=True)

            c1,c2,c3,c4,c5,c6 = st.columns(6)
            c1.metric("Range",   f"{rng_w:.1f}%")
            c2.metric("Slope/d", f"{row['Slope%/day']:.2f}%")
            c3.metric("Buy at",  f"${buy_at}")
            c4.metric("Sell at", f"${sell_at}")
            c5.metric("Stop",    f"${stop_b}")
            c6.metric("R:R",     f"1:{rr:.1f}" if rr > 0 else "–")
            st.divider()

    st.caption("⚠️ Always use a stop loss. Ranges break. Not financial advice. Data via yfinance.")
