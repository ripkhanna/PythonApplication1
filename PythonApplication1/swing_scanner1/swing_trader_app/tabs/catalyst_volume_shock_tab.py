"""Catalyst Volume Shock tab.

Finds QS-style candidates where a catalyst/volume shock can turn a coiled
setup into a fast 5-15% move.  The tab is display/ranking only: it reuses the
latest scanner dataframe or CSV cache and does not slow the main scan.
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Iterable

import numpy as np
import pandas as pd
import streamlit as st


MARKET_SUFFIX = {
    "us": (),
    "sgx": (".SI",),
    "india": (".NS", ".BO"),
    "hk": (".HK",),
}


def _bind_runtime(ctx: dict) -> None:
    globals().update(ctx)


def _market_token() -> str:
    raw = str(st.session_state.get("market_selector", "🇺🇸 US")).upper()
    if "HK" in raw or "HONG" in raw:
        return "hk"
    if "INDIA" in raw or "🇮🇳" in raw or ".NS" in raw:
        return "india"
    if "SGX" in raw or "🇸🇬" in raw or "SINGAPORE" in raw or ".SI" in raw:
        return "sgx"
    return "us"


def _num(df: pd.DataFrame, col: str, default: float = 0.0) -> pd.Series:
    """Robust numeric parser for scanner display columns like '+16.5%', '$8.04', '3.2x', '9/34'."""
    if col not in df.columns:
        return pd.Series([default] * len(df), index=df.index, dtype="float64")
    s = df[col]
    if pd.api.types.is_numeric_dtype(s):
        return pd.to_numeric(s, errors="coerce").fillna(default).astype(float)
    extracted = (
        s.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("%", "", regex=False)
        .str.replace("+", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.replace("S$", "", regex=False)
        .str.replace("HK$", "", regex=False)
        .str.replace("₹", "", regex=False)
        .str.replace("x", "", regex=False)
        .str.extract(r"(-?\d+(?:\.\d+)?)")[0]
    )
    return pd.to_numeric(extracted, errors="coerce").fillna(default).astype(float)


def _txt(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series([""] * len(df), index=df.index)
    return df[col].astype(str).fillna("")


def _unique_keep_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items or []:
        t = str(item or "").strip().upper()
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def _filter_market(df: pd.DataFrame, token: str) -> pd.DataFrame:
    if df.empty or "Ticker" not in df.columns:
        return df
    out = df.copy()
    out["Ticker"] = out["Ticker"].astype(str).str.upper().str.strip()
    if token == "us":
        mask = ~out["Ticker"].str.endswith((".SI", ".HK", ".NS", ".BO"), na=False)
    else:
        suffixes = MARKET_SUFFIX.get(token, ())
        mask = out["Ticker"].str.endswith(suffixes, na=False) if suffixes else pd.Series(True, index=out.index)
    return out[mask].drop_duplicates("Ticker").reset_index(drop=True)


def _source_frame() -> pd.DataFrame:
    token = _market_token()
    sources: list[tuple[str, object]] = []
    for key in ("df_long_master", "df_long", "df_swing_picks"):
        sources.append((f"session:{key}", st.session_state.get(key, pd.DataFrame())))
    for key in ("df_long_master", "df_long", "df_swing_picks"):
        sources.append((f"runtime:{key}", globals().get(key, pd.DataFrame())))

    for label, df in sources:
        if isinstance(df, pd.DataFrame) and not df.empty:
            out = df.copy()
            if "Ticker" not in out.columns:
                out.insert(0, "Ticker", out.index.astype(str))
            out = _filter_market(out, token)
            if not out.empty:
                st.session_state["cvs_source_label"] = label
                st.session_state["cvs_source_rows"] = len(out)
                return out

    cache_dir = Path(__file__).resolve().parents[1] / "scanner_cache"
    names = {
        "us": ["us_long_setups.csv"],
        "sgx": ["sgx_long_setups.csv", "sg_long_setups.csv"],
        "india": ["india_long_setups.csv"],
        "hk": ["hk_long_setups.csv"],
    }.get(token, [])
    for name in names:
        path = cache_dir / name
        if not path.exists():
            continue
        try:
            out = pd.read_csv(path, keep_default_na=False)
            if "Ticker" not in out.columns:
                out.insert(0, "Ticker", out.index.astype(str))
            out = _filter_market(out, token)
            if not out.empty:
                st.session_state["cvs_source_label"] = f"cache:{name}"
                st.session_state["cvs_source_rows"] = len(out)
                return out
        except Exception:
            continue

    st.session_state["cvs_source_label"] = "none"
    st.session_state["cvs_source_rows"] = 0
    return pd.DataFrame()


def _parse_manual_catalyst_tickers(text: str) -> set[str]:
    """Extract ticker boosts from user notes like 'QS: Honda deal' or 'QS Honda deal'."""
    out: set[str] = set()
    for line in str(text or "").splitlines():
        line = line.strip().upper()
        if not line:
            continue
        first = re.split(r"[\s:,-]+", line, maxsplit=1)[0].strip()
        if re.fullmatch(r"[A-Z0-9.]{1,12}", first):
            out.add(first)
    return out


def _fmt_price(value: float, ticker: str) -> str:
    try:
        v = float(value)
        if not np.isfinite(v) or v <= 0:
            return "–"
        t = str(ticker).upper()
        if t.endswith(".SI"):
            return f"S${v:.3f}"
        if t.endswith(".HK"):
            return f"HK${v:.3f}"
        if t.endswith((".NS", ".BO")):
            return f"₹{v:.2f}"
        return f"${v:.2f}"
    except Exception:
        return "–"


def _rank(df: pd.DataFrame, manual_catalysts: set[str]) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        return out
    if "Ticker" not in out.columns:
        out.insert(0, "Ticker", out.index.astype(str))
    out["Ticker"] = out["Ticker"].astype(str).str.upper().str.strip()
    out = out[out["Ticker"].ne("")].drop_duplicates("Ticker").reset_index(drop=True)
    idx = out.index

    joined = (
        _txt(out, "Signals") + " " +
        _txt(out, "Setup Type") + " " +
        _txt(out, "Action") + " " +
        _txt(out, "Entry Quality") + " " +
        _txt(out, "PSS Triggers") + " " +
        _txt(out, "PSS Label") + " " +
        _txt(out, "Pre-Mover Why") + " " +
        _txt(out, "Explosion Why") + " " +
        _txt(out, "Stage 2 Why") + " " +
        _txt(out, "Early Why") + " " +
        _txt(out, "Vol Quality")
    ).str.upper()

    today = _num(out, "Today %", 0)
    pm_chg = _num(out, "PM Chg%", 0)
    gap = pm_chg.where(pm_chg.abs() >= 0.1, today)
    move5 = _num(out, "5D %", 0)
    move20 = _num(out, "20D %", 0)
    atr = _num(out, "ATR%", 0)
    move7 = _num(out, "7D Move Est", 0)
    vol = pd.concat([
        _num(out, "Vol Ratio", 0),
        _num(out, "S2 RVOL Pace", 0),
    ], axis=1).max(axis=1)
    rsi = _num(out, "RSI Now", np.nan)
    rsi = rsi.where(rsi.notna(), _num(out, "RSI", np.nan))
    op = _num(out, "Op Score", 0)
    pss = _num(out, "PSS Score", 0)
    stage2_score = _num(out, "Stage 2 Score", 0)
    early_score = _num(out, "Early Score", 0)
    pre_score = _num(out, "Pre-Mover Score", 0)
    explosion_score = _num(out, "Explosion Score", 0)
    seven = _num(out, "7-Star Score", 0)
    short_pct = _num(out, "Short %", 0)
    float_m = _num(out, "Float", 0)
    price = _num(out, "Price", 0)
    pivot = _num(out, "Stage 2 Entry", 0).where(_num(out, "Stage 2 Entry", 0) > 0, _num(out, "Pivot", 0))
    pivot = pivot.where(pivot > 0, price * 1.01)
    stop = _num(out, "Stage 2 Hard Stop", 0)
    stop = stop.where(stop > 0, _num(out, "Best Stop", 0))
    stop = stop.where(stop > 0, _num(out, "MA60 Stop", 0))
    stop = stop.where((stop > 0) & (stop < price), price * 0.94)

    manual = out["Ticker"].isin(manual_catalysts)
    catalyst_proxy = (
        joined.str.contains(
            r"CATALYST|CATALYSTNEWS|PEAD|EARNINGS|PRE-EARN|POST-EARN|FDA|APPROVAL|CONTRACT|PARTNER|DEAL|ABSORPTION|SQZPROXY|CALL FLOW|OPTIONS/FUEL",
            regex=True,
            na=False,
        )
        | (pss >= 3)
        | manual
    )
    event_like = joined.str.contains(r"EARNINGS GAP|PEAD|CATALYSTNEWS|ABSORPTION|OPTIONS/FUEL", regex=True, na=False) | manual

    compression = (
        joined.str.contains(r"BB BULL SQ|SQUEEZE|VCP|COIL|TIGHT|VDU|VOLUME DRY|FLATBASE|FLAT TOP|BASE|NR7|INSIDE", regex=True, na=False)
        | (_num(out, "VDU Ratio", 9) <= 1.10)
        | (_num(out, "Contraction", 9) <= 0.85)
        | ((stage2_score >= 2) | (early_score >= 2))
    )
    trigger_near = (
        joined.str.contains(r"BREAKOUT|PIVOT|NEAR TRIGGER|52W|HIGHER LOWS|FAILED BRKDN|RECLAIM|SUPPORT|VWAP|MA20|MA60", regex=True, na=False)
        | (_num(out, "Pivot Dist%", 99).between(-8, 4))
        | (pre_score >= 45)
    )
    accumulation = (
        joined.str.contains(r"ACCUM|OBV|POCKET|VOL SURGE|VOL BREAKOUT|OPERATOR|ABSORPTION|ACTIVE VOLUME", regex=True, na=False)
        | (op >= 3)
    )
    relative_strength = (
        joined.str.contains(r"RS>SPY|RSLEAD|RS LEAD|RELATIVE STRENGTH|WKLY TREND|SECTOR LEAD|POWER TREND", regex=True, na=False)
        | (_txt(out, "RS Lead").str.upper().eq("YES"))
    )
    vwap_ok = _txt(out, "VWAP").str.upper().str.contains("ABOVE|SUPPORT", regex=True, na=False)
    volume_gate_pass = _txt(out, "Stage 2 Volume Gate").str.upper().str.contains("PASS", regex=True, na=False)

    gap_ideal = gap.between(3.0, 12.0)
    gap_early = gap.between(1.0, 3.0)
    gap_hot = gap.between(12.0, 18.0)
    live_shock = ((gap >= 3.0) | (today >= 3.0)) & (vol >= 1.5)
    loaded_spring = (gap <= 3.5) & compression & trigger_near & (vol.between(0.35, 1.6) | accumulation)
    trap_text = (_txt(out, "Trap Risk") + " " + _txt(out, "Action") + " " + joined).str.upper()
    chase_words = trap_text.str.contains(r"CHASING|LIMIT-UP|BLOW-OFF", regex=True, na=False)
    chase_risk = (today > 14.0) | (gap > 18.0) | (move5 > 25.0) | (move20 > 50.0) | chase_words
    extended_rsi = rsi.fillna(50) > 78
    # Separate true trap/distribution from normal post-gap chase risk.  Chased names
    # should usually be displayed as "Moved - wait pullback" rather than hidden.
    trap_risk = trap_text.str.contains(r"TRAP|DISTRIB|AVOID", regex=True, na=False)

    score = pd.Series(0.0, index=idx)
    # 1) Catalyst / event fuel, max roughly 26
    score += catalyst_proxy.astype(int) * 16
    score += event_like.astype(int) * 6
    score += manual.astype(int) * 4
    # 2) Volume shock / participation, max roughly 22
    score += (vol >= 3.0).astype(int) * 22
    score += ((vol >= 2.0) & (vol < 3.0)).astype(int) * 18
    score += ((vol >= 1.5) & (vol < 2.0)).astype(int) * 14
    score += ((vol >= 1.0) & (vol < 1.5)).astype(int) * 7
    # 3) Gap strength, max 16
    score += gap_ideal.astype(int) * 16
    score += gap_early.astype(int) * 10
    score += gap_hot.astype(int) * 8
    # 4) Loaded spring / setup structure, max roughly 22
    score += compression.astype(int) * 10
    score += trigger_near.astype(int) * 8
    score += accumulation.astype(int) * 8
    score += relative_strength.astype(int) * 6
    # 5) Explosive style fuel, max roughly 14
    score += (atr >= 6.0).astype(int) * 8
    score += ((atr >= 4.0) & (atr < 6.0)).astype(int) * 5
    score += (move7 >= 8.0).astype(int) * 4
    score += (short_pct >= 10.0).astype(int) * 5
    score += ((float_m > 0) & (float_m <= 300)).astype(int) * 4
    # 6) Scanner confidence overlays
    score += (pre_score >= 55).astype(int) * 5
    score += (explosion_score >= 55).astype(int) * 7
    score += (seven >= 5).astype(int) * 4
    score += vwap_ok.astype(int) * 3
    score += volume_gate_pass.astype(int) * 3

    # Risk controls: do not reward stocks after the whole move is already done.
    score -= chase_risk.astype(int) * 22
    score -= extended_rsi.astype(int) * 8
    score -= trap_risk.astype(int) * 14
    score -= (today < -4.0).astype(int) * 8
    score = score.clip(0, 100).round().astype(int)

    status = pd.Series("LOW / IGNORE", index=idx)
    status.loc[(score >= 80) & live_shock & ~chase_risk & ~trap_risk] = "BUY TRIGGER - ORB/VWAP ONLY"
    status.loc[(score >= 70) & loaded_spring & ~live_shock & ~chase_risk] = "WATCH - LOADED SPRING"
    status.loc[(score >= 65) & ~chase_risk & status.eq("LOW / IGNORE")] = "WATCH - CONFIRM VOLUME"
    status.loc[(score >= 60) & chase_risk] = "MOVED - WAIT PULLBACK"
    status.loc[trap_risk & (score >= 45)] = "AVOID - TRAP/CHASE RISK"

    catalyst_strength = pd.Series("None", index=idx)
    catalyst_strength.loc[catalyst_proxy] = "Proxy"
    catalyst_strength.loc[event_like] = "Event/Fuel"
    catalyst_strength.loc[manual] = "Manual headline"

    gate_notes: list[str] = []
    trigger_plan: list[str] = []
    risk_plan: list[str] = []
    for i, row in out.iterrows():
        parts: list[str] = []
        if catalyst_proxy.loc[i]: parts.append("catalyst/fuel")
        if vol.loc[i] >= 1.5: parts.append(f"RVOL {vol.loc[i]:.1f}x")
        elif vol.loc[i] >= 1.0: parts.append(f"vol improving {vol.loc[i]:.1f}x")
        if gap_ideal.loc[i]: parts.append(f"ideal gap {gap.loc[i]:.1f}%")
        elif gap_early.loc[i]: parts.append(f"early gap {gap.loc[i]:.1f}%")
        elif gap_hot.loc[i]: parts.append(f"hot gap {gap.loc[i]:.1f}%")
        if compression.loc[i]: parts.append("compression/base")
        if trigger_near.loc[i]: parts.append("near trigger")
        if accumulation.loc[i]: parts.append("accumulation")
        if relative_strength.loc[i]: parts.append("relative strength")
        if atr.loc[i] >= 4.0: parts.append(f"ATR {atr.loc[i]:.1f}%")
        if chase_risk.loc[i]: parts.append("already extended")
        if trap_risk.loc[i]: parts.append("trap/chase flag")
        if not parts:
            parts.append("not enough catalyst-volume evidence")
        gate_notes.append(" | ".join(parts[:8]))

        tkr = str(row.get("Ticker", "")).upper()
        trig = _fmt_price(float(pivot.loc[i]), tkr)
        stk_stop = _fmt_price(float(stop.loc[i]), tkr)
        px = _fmt_price(float(price.loc[i]), tkr)
        if status.loc[i].startswith("BUY TRIGGER"):
            trigger_plan.append(f"Buy only above 5/15m ORB or VWAP reclaim; do not chase far above {px}")
        elif status.loc[i].startswith("WATCH - LOADED"):
            trigger_plan.append(f"Set alert above {trig} with >=1.5x live RVOL")
        elif status.loc[i].startswith("WATCH"):
            trigger_plan.append(f"Needs news/volume confirmation; alert above {trig}")
        elif status.loc[i].startswith("MOVED"):
            trigger_plan.append("Wait for VWAP/EMA pullback or next-day high-tight flag")
        elif status.loc[i].startswith("AVOID"):
            trigger_plan.append("Avoid fresh entry until risk flag clears")
        else:
            trigger_plan.append("No trade trigger yet")
        risk_plan.append(f"Invalid below VWAP/ORB low; swing stop near {stk_stop}")

    out["Shock Score"] = score
    out["Shock Status"] = status
    out["Catalyst Strength"] = catalyst_strength
    out["Shock Why"] = gate_notes
    out["Trigger Plan"] = trigger_plan
    out["Risk Plan"] = risk_plan
    out["Gap Used %"] = gap.round(2)
    out["Shock RVOL"] = vol.round(2)
    out["Chase Risk"] = np.where(chase_risk, "YES", "NO")
    out["Loaded Spring"] = np.where(loaded_spring, "YES", "NO")
    out["Live Shock"] = np.where(live_shock, "YES", "NO")

    # High-action display columns kept on the left side of every table, so the
    # user does not need horizontal scrolling to see the decision, trigger price,
    # operator activity, VWAP context, and today's move.
    side = pd.Series("WATCH", index=idx)
    side.loc[status.str.startswith("BUY TRIGGER")] = "BUY"
    side.loc[status.str.startswith("MOVED")] = "WAIT"
    side.loc[status.str.startswith("AVOID")] = "AVOID"
    action_txt = _txt(out, "Action").str.upper()
    side.loc[action_txt.str.contains("SELL|SHORT", regex=True, na=False)] = "SELL"
    side.loc[action_txt.str.contains("BUY|LONG", regex=True, na=False) & ~side.isin(["SELL", "AVOID"])] = "BUY"
    out["Buy/Sell"] = side
    out["Move Price"] = [
        _fmt_price(float(pivot.loc[i] if np.isfinite(pivot.loc[i]) and pivot.loc[i] > 0 else price.loc[i]), str(out.loc[i, "Ticker"]))
        for i in idx
    ]
    out["Current Price"] = [
        _fmt_price(float(price.loc[i]), str(out.loc[i, "Ticker"]))
        for i in idx
    ]
    if "Today %" not in out.columns:
        out["Today %"] = today.round(2)
    if "Operator" not in out.columns:
        out["Operator"] = np.where(accumulation, "YES", "NO")

    order = {
        "BUY TRIGGER - ORB/VWAP ONLY": 5,
        "WATCH - LOADED SPRING": 4,
        "WATCH - CONFIRM VOLUME": 3,
        "MOVED - WAIT PULLBACK": 2,
        "AVOID - TRAP/CHASE RISK": 1,
        "LOW / IGNORE": 0,
    }
    out["_shock_sort"] = out["Shock Status"].map(order).fillna(0)
    out["_rvol_sort"] = vol
    return out.sort_values(["_shock_sort", "Shock Score", "_rvol_sort"], ascending=[False, False, False], kind="stable")


def _show(df: pd.DataFrame, key: str, limit: int = 80) -> None:
    if df.empty:
        st.info("No rows in this bucket with the current filters.")
        return
    preferred = [
        # Keep the highest-action fields at the far left to reduce horizontal scrolling.
        "Ticker", "Buy/Sell", "Action", "Move Price", "Current Price", "Operator", "Op Score",
        "VWAP", "Today %", "PM Chg%", "Gap Used %", "Shock RVOL",
        "Shock Score", "Shock Status", "Catalyst Strength", "Shock Why",
        "Trigger Plan", "Risk Plan", "Vol Ratio", "S2 RVOL Pace", "ATR%", "7D Move Est",
        "Loaded Spring", "Live Shock", "Chase Risk", "Stage 2 Phase", "Stage 2 Score",
        "Early Score", "Stage 2 Entry", "Pivot", "Price", "Explosion Score", "Explosion Tier",
        "Pre-Mover Score", "Pre-Mover Tier", "PSS Score", "PSS Triggers",
        "Short %", "Float", "Entry Quality", "Trap Risk", "Signals",
    ]
    cols = [c for c in preferred if c in df.columns]
    st.dataframe(df[cols].head(limit).reset_index(drop=True), width="stretch", hide_index=True, key=key)
    if "Ticker" in df.columns:
        st.code(", ".join(_unique_keep_order(df["Ticker"].astype(str).head(80).tolist())))


def render_catalyst_volume_shock(ctx: dict) -> None:
    _bind_runtime(ctx)

    st.markdown("## Catalyst Volume Shock")
    st.caption(
        "QS-style scanner: finds coiled stocks where catalyst/fuel + unusual volume can create a sudden 5-15% move. "
        "It reuses the latest Long Setups scan/cache, so it is fast and does not call Yahoo again."
    )

    src = _source_frame()
    if src.empty:
        st.info("Run a market scan first. This tab reuses the latest Long Setups master scan or scanner_cache CSV.")
        return

    c0, c1, c2, c3 = st.columns([2, 1, 1, 1])
    with c0:
        manual_text = st.text_area(
            "Optional manual catalyst boost",
            value="",
            height=80,
            placeholder="Example: QS: Honda solid-state battery agreement",
            help="One ticker per line. This boosts Catalyst Strength when you already know a headline before/after market open.",
            key="cvs_manual_catalysts",
        )
    with c1:
        min_score = st.slider("Min shock score", 0, 100, 45, step=5, key="cvs_min_score")
    with c2:
        max_chase = st.slider("Max today % for fresh buys", 3.0, 25.0, 14.0, step=1.0, key="cvs_max_chase")
    with c3:
        only_actionable = st.checkbox("Only actionable", value=False, key="cvs_only_actionable")

    manual = _parse_manual_catalyst_tickers(manual_text)
    ranked = _rank(src, manual)
    if ranked.empty:
        st.info("No rows available after market filtering.")
        return

    # User filter: keep all moved rows visible unless Only actionable is selected.
    today = _num(ranked, "Today %", 0)
    ranked = ranked[(ranked["Shock Score"] >= int(min_score)) & ((today <= float(max_chase)) | ranked["Shock Status"].str.startswith("MOVED"))].copy()
    if only_actionable:
        ranked = ranked[ranked["Shock Status"].isin([
            "BUY TRIGGER - ORB/VWAP ONLY",
            "WATCH - LOADED SPRING",
            "WATCH - CONFIRM VOLUME",
        ])].copy()

    search = st.text_input("Filter ticker / reason", "", key="cvs_search").strip().upper()
    if search:
        hay = (
            _txt(ranked, "Ticker") + " " + _txt(ranked, "Shock Status") + " " +
            _txt(ranked, "Shock Why") + " " + _txt(ranked, "Signals") + " " +
            _txt(ranked, "PSS Triggers")
        ).str.upper()
        ranked = ranked[hay.str.contains(re.escape(search), na=False)].copy()

    buy_now = ranked[ranked["Shock Status"].eq("BUY TRIGGER - ORB/VWAP ONLY")].copy()
    loaded = ranked[ranked["Shock Status"].eq("WATCH - LOADED SPRING")].copy()
    confirm = ranked[ranked["Shock Status"].eq("WATCH - CONFIRM VOLUME")].copy()
    moved = ranked[ranked["Shock Status"].eq("MOVED - WAIT PULLBACK")].copy()
    avoid = ranked[ranked["Shock Status"].eq("AVOID - TRAP/CHASE RISK")].copy()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Buy trigger", len(buy_now))
    m2.metric("Loaded spring", len(loaded))
    m3.metric("Confirm volume", len(confirm))
    m4.metric("Moved / avoid", len(moved) + len(avoid))
    st.caption(
        f"Source: {st.session_state.get('cvs_source_label', 'unknown')} · "
        f"{st.session_state.get('cvs_source_rows', len(src))} rows · "
        "BUY TRIGGER still requires 5/15-minute ORB or VWAP reclaim confirmation."
    )

    st.markdown("### 1) Buy Trigger Now")
    st.caption("Live shock already present. Do not market-buy blindly; use ORB/VWAP confirmation and tight invalidation.")
    _show(buy_now, "cvs_buy_now")

    st.markdown("### 2) Loaded Spring Before Volume")
    st.caption("Best watchlist for the next QS-style sudden volume move: coiled, near trigger, not already extended.")
    _show(loaded, "cvs_loaded")

    with st.expander(f"Watch - confirm volume ({len(confirm)})", expanded=True):
        _show(confirm, "cvs_confirm")

    with st.expander(f"Moved already - wait pullback ({len(moved)})", expanded=True):
        _show(moved, "cvs_moved")

    with st.expander(f"Avoid / trap risk ({len(avoid)})", expanded=False):
        _show(avoid, "cvs_avoid")

    with st.expander(f"All ranked rows ({len(ranked)})", expanded=False):
        _show(ranked, "cvs_all", limit=200)

    st.info(
        "How to use: run the normal market scan, open this tab, then set alerts on the Loaded Spring tickers. "
        "A trade is valid only after news/catalyst plus live RVOL and ORB/VWAP confirmation. The scanner estimates probability; it cannot know future sudden volume with certainty."
    )
