"""Breakout Scanner — fully independent of the main strategy scan.

WHY STRATEGY CHANGES USED TO AFFECT THIS TAB:
  The old version called _get_mover_sets (Yahoo TTL=3 min) on EVERY render
  and passed the result as part of @st.cache_data key for _run_scan.
  Every 3 min → new frozenset → cache miss → full re-download.
  Streamlit reruns every tab on every widget change, so strategy dropdown
  changes triggered this 3-min cycle, making results appear to change.

THE FIX — single principle:
  NOTHING in this tab runs unless the user clicks "Run Scanner".
  Results live in st.session_state["bk_result"].
  On every render that is NOT a button click, we just read session_state
  and display — zero downloads, zero Yahoo calls, zero recomputation.
  Strategy changes → app reruns → we read session_state → same results shown.
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

_FLAG  = {"US": "🇺🇸", "SGX": "🇸🇬", "India": "🇮🇳", "Hong Kong": "🇭🇰"}
_YREGION = {"US": "US", "SGX": "SG", "India": "IN", "Hong Kong": "HK"}
_YSCREENERS = {"Top Gainers": "day_gainers",
               "Top Losers":  "day_losers",
               "Most Active": "most_actives"}
_TTL = 300          # seconds — scan shown as stale after this
_SK  = "bk_result"  # session_state key


# ─── tiny helpers ─────────────────────────────────────────────────────────────

def _f(v) -> float:
    try: return float(v)
    except Exception: return float("nan")


def _vol_str(v) -> str:
    try:
        v = float(v)
        if v >= 1e6: return f"{v/1e6:.1f}M"
        if v >= 1e3: return f"{v/1e3:.0f}K"
        return f"{v:.0f}"
    except Exception: return "—"


def _sgt(ts) -> str:
    try:
        t = pd.to_datetime(ts, errors="coerce")
        if pd.isna(t): return str(ts)
        if t.tzinfo is None: t = t.tz_localize("UTC")
        return t.tz_convert("Asia/Singapore").strftime("%d %b %H:%M")
    except Exception: return "—"


def _extract(raw: pd.DataFrame, sym: str, chunk: list) -> pd.DataFrame:
    if raw is None or raw.empty: return pd.DataFrame()
    if isinstance(raw.columns, pd.MultiIndex):
        for lvl in (0, 1):
            try:
                if sym in raw.columns.get_level_values(lvl):
                    if lvl == 0:
                        f = raw[sym].copy()
                        return f.dropna(how="all") if isinstance(f, pd.DataFrame) else pd.DataFrame()
                    return raw.xs(sym, axis=1, level=1).copy().dropna(how="all")
            except Exception: pass
        return pd.DataFrame()
    return raw.dropna(how="all").copy() if len(chunk) == 1 else pd.DataFrame()


# ─── Yahoo movers — fetched ONCE per scan, stored in session_state ─────────────

def _fetch_movers_once(region: str, count: int = 100) -> tuple[frozenset, dict]:
    """Fetch US market movers. Called only during a Run Scanner click."""
    symbols: set  = set()
    bucket:  dict = {}
    for label, sid in _YSCREENERS.items():
        params = urllib.parse.urlencode({
            "formatted": "false", "lang": "en-US",
            "region": region, "scrIds": sid, "count": int(count),
        })
        url = ("https://query1.finance.yahoo.com/v1/finance/screener"
               "/predefined/saved?" + params)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=12) as r:
                d = json.loads(r.read().decode("utf-8", errors="replace"))
            quotes = ((((d or {}).get("finance") or {}).get("result") or [{}])[0]
                      .get("quotes") or [])
        except Exception:
            quotes = []
        for q in quotes:
            sym = str(q.get("symbol") or "").strip().upper()
            if sym:
                symbols.add(sym)
                bucket.setdefault(sym, label)
    return frozenset(symbols), bucket


def _badge_movers(df: pd.DataFrame, ms: frozenset, mb: dict) -> pd.DataFrame:
    if df.empty or not ms: return df
    d = df.copy()
    for idx, row in d.iterrows():
        t = row["Ticker"]
        if t in ms:
            badge   = f"🚀 {mb.get(t,'')}" if mb.get(t) else "🚀 Mover"
            sig     = str(row.get("Signals", "—"))
            if "Mover" not in sig:
                clean = sig.strip("—").strip(" |")
                d.at[idx, "Signals"] = (clean + " | " + badge).lstrip(" |") if clean else badge
            d.at[idx, "Score"] = min(100, int(row.get("Score", 0)) + 10)
    return d


# ─── per-ticker analyser ───────────────────────────────────────────────────────

def _analyse(sym, raw_df, bdays, vmult, w52):
    if raw_df is None or raw_df.empty: return None
    df = pd.DataFrame(index=raw_df.index)
    for col in ("Close", "High", "Low", "Volume"):
        df[col] = pd.to_numeric(
            raw_df[col] if col in raw_df.columns else float("nan"),
            errors="coerce")
    df["Volume"] = df["Volume"].fillna(0)
    df["High"]   = df["High"].fillna(df["Close"])
    df["Low"]    = df["Low"].fillna(df["Close"])
    df           = df[df["Close"].notna()].copy()
    if len(df) < 30: return None

    c, h, l, v = df["Close"], df["High"], df["Low"], df["Volume"]
    price = _f(c.iloc[-1]);  prev = _f(c.iloc[-2]) if len(c) >= 2 else float("nan")
    if not (price > 0 and prev > 0): return None

    chg = (price - prev) / prev * 100
    va  = _f(v.iloc[-21:-1].mean()) if len(v) >= 21 else _f(v.mean())
    vr  = _f(v.iloc[-1]) / va if va > 0 else float("nan")

    h252 = _f(h.iloc[-252:].max()) if len(h) >= 50 else _f(h.max())
    l252 = _f(l.iloc[-252:].min()) if len(l) >= 50 else _f(l.min())
    vs52 = (price - h252) / h252 * 100 if h252 > 0 else -999.0
    ir   = (price - l252) / (h252 - l252) * 100 if (h252 - l252) > 0 else 0.0
    n52  = price >= h252 * 0.9995

    ndh  = _f(h.iloc[-(bdays+1):-1].max()) if len(h) > bdays else _f(h.max())
    brk  = (price > ndh) and np.isfinite(vr) and (vr >= vmult)
    bpct = (price - ndh) / ndh * 100 if ndh > 0 else 0.0
    s52  = vs52 >= -w52

    if len(c) >= 14:
        tr  = pd.concat([h-l, (h-c.shift(1)).abs(), (l-c.shift(1)).abs()], axis=1).max(axis=1)
        a14 = _f(tr.rolling(14).mean().iloc[-1])
        atr = a14 / price * 100 if (np.isfinite(a14) and price > 0) else 0.0
    else: atr = 0.0

    r3m = _f((c.iloc[-1]-c.iloc[-63])/c.iloc[-63]*100) if len(c) >= 63 else 0.0

    # Score: 0 unless a real signal fires
    sc = 0
    if brk:
        sc += 50
        if np.isfinite(vr): sc += min(20, int((vr-vmult)/3*20))
        sc += min(15, int(bpct*3))
        sc += 10 if n52 else (5 if s52 else 0)
    elif n52:
        sc += 15
        if np.isfinite(vr) and vr >= 1.5: sc += min(10, int((vr-1)/2*10))
    elif s52:
        sc += 10
        if np.isfinite(vr) and vr >= 1.5: sc += min(5, int((vr-1)/2*5))
    sc += min(5, max(0, int(abs(chg))))
    sc  = max(0, min(100, sc))

    badges = []
    if brk:      badges.append("🔥 Vol Breakout")
    if n52:      badges.append("🏆 New 52W High")
    elif s52:    badges.append("📈 52W Setup")

    return {
        "Ticker":      sym,
        "Score":       sc,
        "Signals":     " | ".join(badges) if badges else "—",
        "Price":       round(price, 3),
        "Chg %":       round(chg, 2),
        "Vol Ratio":   round(vr, 2) if np.isfinite(vr) else float("nan"),
        "Today Vol":   _f(v.iloc[-1]),
        "vs 52W %":    round(vs52, 2),
        "In Range %":  round(ir, 1),
        "Breakout %":  round(bpct, 2) if brk else 0.0,
        "ATR %":       round(atr, 2),
        "3M Return %": round(r3m, 1),
        "_new_52w":    n52,
        "_is_brk":     brk,
        "Last Bar":    _sgt(c.index[-1]),
    }


# ─── main scan (no @st.cache_data — called only on button press) ───────────────

def _do_scan(tickers, mkt, bdays, vmult, w52, market_key) -> tuple:
    rows, errs = [], []
    for i in range(0, len(tickers), 80):
        chunk = tickers[i:i+80]
        try:
            raw = yf.download(chunk, period="1y", interval="1d",
                              group_by="ticker", auto_adjust=True,
                              threads=True, progress=False)
        except Exception as e:
            errs.append(f"batch {i}: {e}"); continue
        if raw is None or raw.empty:
            errs.append(f"batch {i}: empty"); continue
        for sym in chunk:
            tdf = _extract(raw, sym, chunk)
            if tdf.empty: continue
            try:
                row = _analyse(sym, tdf, bdays, vmult, w52)
                if row: rows.append(row)
            except Exception as e:
                errs.append(f"{sym}: {e}")

    # Fetch movers (US only) and apply badges immediately
    if market_key == "US":
        ms, mb = _fetch_movers_once(_YREGION["US"])
    else:
        ms, mb = frozenset(), {}

    df = pd.DataFrame(rows)
    if not df.empty:
        df["Score"] = pd.to_numeric(df["Score"], errors="coerce").fillna(0).astype(int)
        df = df.sort_values("Score", ascending=False).reset_index(drop=True)
        df = _badge_movers(df, ms, mb)

    meta = {
        "mkt":         mkt,
        "scanned":     len(tickers),
        "vol_brk":     int(df["_is_brk"].sum())  if not df.empty else 0,
        "new_52w":     int(df["_new_52w"].sum()) if not df.empty else 0,
        "movers":      int(df["Signals"].str.contains("Mover", na=False).sum()) if not df.empty else 0,
        "with_signal": int((df["Score"] >= 15).sum()) if not df.empty else 0,
        "at":          datetime.now(timezone.utc).astimezone().strftime("%H:%M:%S %Z"),
        "errors":      errs[:10],
    }
    return df, meta


# ─── display ──────────────────────────────────────────────────────────────────

def _display(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    for col, fmt in [("Chg %","+.2f"),("vs 52W %","+.2f"),("Breakout %","+.2f"),("3M Return %","+.1f")]:
        if col in d.columns:
            d[col] = pd.to_numeric(d[col], errors="coerce").map(
                lambda x, f=fmt: f"{x:{f}}%" if pd.notna(x) and np.isfinite(x) else "—")
    if "Price" in d.columns:
        d["Price"] = pd.to_numeric(d["Price"], errors="coerce").map(
            lambda x: f"{x:,.3f}" if pd.notna(x) and np.isfinite(x) else "—")
    if "Vol Ratio" in d.columns:
        d["Vol Ratio"] = pd.to_numeric(d["Vol Ratio"], errors="coerce").map(
            lambda x: f"{x:.2f}x" if pd.notna(x) and np.isfinite(x) else "—")
    if "Today Vol" in d.columns:
        d["Today Vol"] = d["Today Vol"].map(_vol_str)
    for col in ("In Range %", "ATR %"):
        if col in d.columns:
            d[col] = pd.to_numeric(d[col], errors="coerce").map(
                lambda x: f"{x:.1f}%" if pd.notna(x) and np.isfinite(x) else "—")
    return d


# ─── render ───────────────────────────────────────────────────────────────────

def render_breakout_scanner(g: dict) -> None:
    """
    Completely independent of the main scan. Never reads df_long_master or
    any main-scan data from g. Results frozen in st.session_state[_SK].
    ONLY the Run Scanner button changes what's shown here.
    Strategy, market, and all other sidebar controls have zero effect.
    """
    st.subheader("⚡ Breakout Scanner")
    st.caption(
        "**Fully independent.** Strategy, market selector, and all sidebar controls "
        "have zero effect here. Results only change when you click **Run Scanner**."
    )
    st.markdown("---")

    # ── Controls ────────────────────────────────────────────────────────────
    col1, col2 = st.columns([1.2, 2.4])
    with col1:
        mkt = st.selectbox(
            "🌍 Market",
            ["US", "SGX", "India", "Hong Kong"],
            format_func=lambda m: f"{_FLAG.get(m,'')} {m}",
            index=0, key="bk_mkt",
        )

    uni_opts = universe_options_for_market(mkt)
    if not uni_opts:
        st.error(f"No universe presets for {mkt}.")
        return
    uid_list  = [u[0] for u in uni_opts]
    ulbl_list = [u[1] for u in uni_opts]

    with col2:
        uidx = st.selectbox(
            "📋 Universe",
            range(len(ulbl_list)),
            format_func=lambda i: ulbl_list[i],
            index=0, key=f"bk_uni_{mkt}",
            help="S&P 500 = 500 index components. All US = S&P500+NDX+Growth (~746).",
        )
    univ_id  = uid_list[uidx]
    univ_lbl = ulbl_list[uidx]

    p1, p2, p3, p4 = st.columns(4)
    with p1: max_t  = st.slider("Max tickers",            50, 650, 300, 50,   key="bk_max")
    with p2: bdays  = st.slider("Breakout window (days)", 5,  60,  20,  5,    key="bk_days")
    with p3: vmult  = st.slider("Min vol ratio x",        1.5,5.0, 2.0, 0.25, key="bk_vol")
    with p4: w52    = st.slider("52W high within %",      1.0,15.0,5.0, 0.5,  key="bk_52w")

    tickers = get_universe(mkt, univ_id)
    if not tickers:
        st.error(f"No tickers for {mkt}/{univ_id}.")
        return
    n   = min(len(tickers), max_t)
    flg = _FLAG.get(mkt, "")

    st.caption(
        f"{flg} **{mkt}** · **{univ_lbl}** · "
        f"{len(tickers)} tickers · scanning up to **{n}**"
    )

    # ── Button — THE ONLY THING THAT TRIGGERS A SCAN ────────────────────────
    col_btn, col_msg = st.columns([1, 5])
    with col_btn:
        run = st.button("🔄 Run Scanner", key="bk_run", type="primary")
    with col_msg:
        st.caption("Only this button changes the results. Strategy changes have no effect.")

    # Parameters fingerprint — detect if settings changed since last scan
    params = (tuple(tickers[:n]), mkt, bdays, vmult, w52)

    stored = st.session_state.get(_SK)
    same   = stored is not None and stored.get("params") == params
    age    = (datetime.now(timezone.utc).timestamp() - stored.get("ts", 0)
              if stored else 9999)

    # ── Scan (only on explicit button press) ────────────────────────────────
    if run:
        pb = st.progress(0, text="Starting scan…")
        pb.progress(10, text=f"Downloading 1y daily data for {n} {flg} tickers…")
        df_new, meta_new = _do_scan(list(tickers)[:n], mkt, bdays, vmult, w52, mkt)
        pb.progress(100, text="Done!")
        pb.empty()
        st.session_state[_SK] = {
            "df":     df_new,
            "meta":   meta_new,
            "params": params,
            "ts":     datetime.now(timezone.utc).timestamp(),
        }
        stored = st.session_state[_SK]
        same   = True
        age    = 0

    # ── No results yet ───────────────────────────────────────────────────────
    if stored is None:
        st.info(
            f"No scan results yet for {flg} {mkt} / {univ_lbl}.\n\n"
            "Click **Run Scanner** to download 1-year daily OHLCV data "
            "and score every stock for breakout signals."
        )
        return

    df:   pd.DataFrame = stored["df"]
    meta: dict         = stored["meta"]

    # Warn if params changed but don't auto-re-run
    if not same:
        st.warning(
            f"⚠️ Settings changed since last scan ({meta['at']}). "
            "Click **Run Scanner** to update results."
        )

    # ── Summary banner ───────────────────────────────────────────────────────
    st.markdown("---")
    age_str = f"{int(age/60)}m ago" if age > 60 else "just now"
    st.success(
        f"Scan results from **{meta['at']}** ({age_str}) · "
        f"{meta['scanned']} tickers · "
        f"🔥 {meta['vol_brk']} Vol Breakouts · "
        f"🏆 {meta['new_52w']} New 52W Highs · "
        f"🚀 {meta['movers']} Movers · "
        f"✅ {meta['with_signal']} with active signal"
    )

    if meta.get("errors"):
        with st.expander(f"⚠️ {len(meta['errors'])} fetch warning(s)"):
            for e in meta["errors"]:
                st.text(e)

    if df.empty:
        st.info("Scan returned no data. Market may be closed or Yahoo rate-limited. Try again in 60 s.")
        return

    st.markdown("---")

    # ── Filters ──────────────────────────────────────────────────────────────
    f1, f2, f3, f4 = st.columns([2, 2.2, 1.2, 1.2])
    with f1:
        srch = st.text_input("🔍 Ticker", "", key="bk_srch",
                             placeholder="e.g. NVDA, D05.SI…").strip().upper()
    with f2:
        sigf = st.multiselect("Signal filter",
                              ["🔥 Vol Breakout","📈 52W Setup","🏆 New 52W High","🚀 Mover"],
                              default=[], key="bk_sigf")
    with f3:
        minscore = st.slider("Min Score", 0, 80, 15, 5, key="bk_minscore",
                              help="15 = only stocks with active signal shown")
    with f4:
        srt = st.selectbox("Sort by",
                           ["Score","Vol Ratio","Breakout %","Chg %","vs 52W %","3M Return %"],
                           index=0, key="bk_srt")
    nrows = st.slider("Rows", 10, 100, 30, 10, key="bk_nrows")

    view = df.copy()
    if srch:
        view = view[view["Ticker"].str.upper().str.contains(srch, na=False)]
    if sigf:
        mask = pd.Series(False, index=view.index)
        for sig in sigf:
            if   sig == "🏆 New 52W High":   mask |= view["_new_52w"].astype(bool)
            elif sig == "🔥 Vol Breakout":   mask |= view["_is_brk"].astype(bool)
            else:
                txt = sig.split(" ", 1)[1] if " " in sig else sig
                mask |= view["Signals"].str.contains(txt, na=False)
        view = view[mask]
    view = view[view["Score"] >= minscore]
    view = view.sort_values(srt, ascending=(srt == "vs 52W %")).head(nrows)

    # ── Top picks ─────────────────────────────────────────────────────────
    brk_df = df[df["_is_brk"].astype(bool)] if "_is_brk" in df.columns else pd.DataFrame()
    top3   = brk_df.head(3) if not brk_df.empty else df[df["Score"] >= 40].head(3)

    if not top3.empty:
        st.markdown(f"#### 🏅 Top Breakouts — {flg} {mkt}")
        cols = st.columns(len(top3))
        for i, (_, r) in enumerate(top3.iterrows()):
            with cols[i]:
                pv = r.get("Price",      float("nan"))
                cv = r.get("Chg %",      float("nan"))
                vv = r.get("Vol Ratio",  float("nan"))
                bv = r.get("Breakout %", float("nan"))
                st.metric(
                    label=f"#{i+1}  {r['Ticker']}",
                    value=f"{pv:,.3f}" if (pd.notna(pv) and np.isfinite(pv)) else "—",
                    delta=f"{cv:+.2f}%" if (pd.notna(cv) and np.isfinite(cv)) else None,
                )
                pts = [f"Score {r['Score']}"]
                if pd.notna(vv) and np.isfinite(vv):  pts.append(f"Vol {vv:.1f}x")
                if pd.notna(bv) and np.isfinite(bv) and bv > 0: pts.append(f"+{bv:.1f}%")
                st.markdown("  ·  ".join(pts))
                st.caption(r.get("Signals", "—"))
        st.markdown("---")

    # ── Table ──────────────────────────────────────────────────────────────
    nsig = int((view["Score"] >= 15).sum())
    st.markdown(f"**{len(view)} stocks · {nsig} with active signal · {flg} {mkt} / {univ_lbl}**")

    COLS = ["Ticker","Score","Signals","Price","Chg %","Vol Ratio","Today Vol",
            "Breakout %","vs 52W %","In Range %","ATR %","3M Return %","Last Bar"]
    show = [c for c in COLS if c in view.columns]
    st.dataframe(_display(view[show]), use_container_width=True, hide_index=True)

    # ── Charts ─────────────────────────────────────────────────────────────
    sv = view[view["Score"] >= 15]
    if not sv.empty:
        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Score**")
            st.bar_chart(sv[["Ticker","Score"]].set_index("Ticker").head(20))
        with c2:
            st.markdown("**Vol Ratio — breakout stocks**")
            bv2 = sv[sv["_is_brk"].astype(bool)] if "_is_brk" in sv.columns else sv
            if bv2.empty: bv2 = sv
            vdf = bv2[["Ticker","Vol Ratio"]].copy()
            vdf["Vol Ratio"] = pd.to_numeric(vdf["Vol Ratio"], errors="coerce")
            vdf = vdf.dropna().sort_values("Vol Ratio", ascending=False).set_index("Ticker").head(20)
            if not vdf.empty: st.bar_chart(vdf)

        st.markdown("**Signal counts**")
        st.bar_chart(pd.DataFrame({"Count":{
            "🔥 Breakouts": meta["vol_brk"],
            "🏆 52W Highs":  meta["new_52w"],
            "🚀 Movers":     meta["movers"],
        }}))

    with st.expander("📖 Score guide"):
        st.markdown(f"""
**Score = 0 unless a real signal fires** (keeps results distinct from PSM):

| Signal | Score | Condition |
|--------|-------|-----------|
| 🔥 Vol Breakout | 50 + up to 35 | Price > {bdays}-day high AND vol ≥ {vmult:.1f}× avg |
| 🏆 New 52W High + breakout | +10 | At 52-week high while breaking out |
| 📈 52W Setup only | 10–15 | Within {w52}% of 52W high, no breakout |
| 🚀 Mover | +10 | Yahoo live feed (US only) |
| No signal | **0** | Hidden by Min Score = 15 default |

**Why independent of strategy:** scan result frozen in `session_state`. No
`@st.cache_data`, no Yahoo calls on every render. Only **Run Scanner** changes anything.
        """)
