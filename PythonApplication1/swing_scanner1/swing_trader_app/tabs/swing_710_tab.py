"""
7-10% Swing tab.

Ranks the latest scanner output for short-term swing candidates using the
existing computed columns. This tab does not download data again.
"""

import re

import numpy as np
import pandas as pd
import streamlit as st


def _bind_runtime(ctx: dict) -> None:
    globals().update(ctx)


def _num_series(df: pd.DataFrame, col: str, default: float = 0.0) -> pd.Series:
    if col not in df.columns:
        return pd.Series([default] * len(df), index=df.index, dtype="float64")
    cleaned = (
        df[col]
        .astype(str)
        .str.replace("%", "", regex=False)
        .str.replace("+", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.replace("x", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.strip()
    )
    return pd.to_numeric(cleaned, errors="coerce").fillna(default)


def _text_series(df: pd.DataFrame, col: str, default: str = "") -> pd.Series:
    if col not in df.columns:
        return pd.Series([default] * len(df), index=df.index)
    return df[col].astype(str).fillna(default)


def _rr_series(df: pd.DataFrame) -> pd.Series:
    if "RR Est" not in df.columns:
        return pd.Series([0.0] * len(df), index=df.index)

    def parse(v) -> float:
        text = str(v).strip()
        if not text or text.lower() in {"nan", "none", "-"}:
            return 0.0
        m = re.search(r"1\s*[:/]\s*([0-9]+(?:\.[0-9]+)?)", text)
        if m:
            return float(m.group(1))
        m = re.search(r"([0-9]+(?:\.[0-9]+)?)", text)
        return float(m.group(1)) if m else 0.0

    return df["RR Est"].map(parse).astype(float).fillna(0.0)


def _source_frame() -> pd.DataFrame:
    candidates = [
        st.session_state.get("df_long_master", pd.DataFrame()),
        st.session_state.get("df_long", pd.DataFrame()),
    ]
    for df in candidates:
        if isinstance(df, pd.DataFrame) and not df.empty:
            return df.copy()
    return pd.DataFrame()


def _reason(row) -> str:
    reasons = []
    if row["_upside"] >= 8:
        reasons.append(f"room {row['_upside']:.1f}%")
    if row["_move7"] >= 7:
        reasons.append(f"7D est {row['_move7']:.1f}%")
    if row["_atr_proxy"] >= 3.5:
        reasons.append(f"range {row['_atr_proxy']:.1f}%")
    if row["_rr"] >= 2:
        reasons.append(f"RR 1:{row['_rr']:.1f}")
    if row["_vol"] >= 1.2:
        reasons.append(f"vol {row['_vol']:.2f}x")
    if row["_supportish"]:
        reasons.append("support nearby")
    if row["_breakoutish"]:
        reasons.append("breakout/momentum")
    if row["_today"] > row["_max_fresh_today"]:
        reasons.append(f"already +{row['_today']:.1f}% today")
    if row["_trap"]:
        reasons.append("trap risk")
    return " | ".join(reasons[:6]) if reasons else "Needs more confirmation"


def _classify(df: pd.DataFrame, min_upside: float, min_atr: float, max_fresh_today: float, min_rr: float) -> pd.DataFrame:
    out = df.copy()
    idx = out.index

    if "Ticker" not in out.columns:
        out["Ticker"] = idx.astype(str)

    signals = _text_series(out, "Signals").str.upper()
    action = _text_series(out, "Action").str.upper()
    setup = _text_series(out, "Setup Type").str.upper()
    support = _text_series(out, "Support Tier").str.upper()
    entry = _text_series(out, "Entry Quality").str.upper()
    trap = _text_series(out, "Trap Risk").str.upper()
    tradeable = _text_series(out, "Tradeable Buy").str.upper().eq("YES")

    rise = _num_series(out, "Rise Prob", 0)
    today = _num_series(out, "Today %", 0)
    upside = _num_series(out, "Upside to Res", 0)
    move7 = _num_series(out, "7D Move Est", 0)
    vol = _num_series(out, "Vol Ratio", 0)
    rr = _rr_series(out)
    quality = _num_series(out, "Quality Score", 0)
    nds = _num_series(out, "Next-Day Score", 0)

    if "ATR%" in out.columns:
        atr_proxy = _num_series(out, "ATR%", 0)
    else:
        atr_proxy = pd.Series(np.maximum(move7 * 0.55, today.abs()), index=idx).fillna(0)

    supportish = (
        support.str.contains("SUPPORT|MA20|MA60|MA200|VWAP|SWING|DIP", regex=True, na=False)
        | setup.str.contains("SUPPORT|MA20|MA60|MA200|VWAP|DIP|PULLBACK", regex=True, na=False)
        | signals.str.contains("DIP|VOL-DIP|FAILED BRKDN|VWAP|MA20|MA60|MA200|SUPPORT", regex=True, na=False)
        | action.str.contains("SUPPORT|DIP|PULLBACK", regex=True, na=False)
    )
    breakoutish = (
        signals.str.contains("VOL BREAKOUT|POCKET PIVOT|52W|HIGH|MOMENTUM|EARNINGS GAP|PEAD|LIVE", regex=True, na=False)
        | action.str.contains("BREAKOUT|MOMENTUM|EARNINGS|GAP|VOLUME", regex=True, na=False)
        | setup.str.contains("BREAKOUT|MOMENTUM|PM|VOLUME", regex=True, na=False)
    )
    trap_risk = trap.str.contains("TRAP|CHASING|DISTRIBUTION|LIMIT|WAIT", regex=True, na=False)
    volume_ok = (vol >= 1.05) | signals.str.contains("VOL|POCKET|OBV", regex=True, na=False)

    enough_upside = (upside >= min_upside) | (move7 >= min_upside)
    enough_range = (atr_proxy >= min_atr) | (move7 >= min_upside)
    rr_ok = rr >= min_rr
    not_extended = today <= max_fresh_today
    not_dumping = today >= -5.0
    confirmation = supportish | breakoutish | volume_ok | tradeable

    fresh = enough_upside & enough_range & rr_ok & not_extended & not_dumping & confirmation & (~trap_risk) & (rise >= 45)
    breakout = enough_upside & enough_range & (today > 0.5) & (today <= 8.5) & (breakoutish | volume_ok) & (~trap_risk)
    pullback = enough_upside & enough_range & supportish & (~fresh) & (~trap_risk)

    score = (
        np.minimum(upside.clip(lower=0), 15) / 15 * 23
        + np.minimum(move7.clip(lower=0), 12) / 12 * 20
        + np.minimum(atr_proxy.clip(lower=0), 12) / 12 * 15
        + np.minimum(rise.clip(lower=0), 100) / 100 * 13
        + np.minimum(vol.clip(lower=0), 3) / 3 * 10
        + np.minimum(rr.clip(lower=0), 4) / 4 * 10
        + np.minimum(np.maximum(quality, nds).clip(lower=0), 15) / 15 * 9
    )
    score = score + np.where(supportish, 4, 0) + np.where(breakoutish, 4, 0) + np.where(tradeable, 5, 0)
    score = score - np.where(today > max_fresh_today, 7, 0) - np.where(trap_risk, 15, 0)
    score = pd.Series(score, index=idx).clip(lower=0, upper=100).round(1)

    tier = pd.Series("Avoid / Not Ready", index=idx)
    tier.loc[pullback] = "Tier C - Pullback Watch"
    tier.loc[breakout] = "Tier B - Breakout / Momentum"
    tier.loc[fresh] = "Tier A - Fresh Entry"

    out["_upside"] = upside
    out["_move7"] = move7
    out["_atr_proxy"] = atr_proxy
    out["_rr"] = rr
    out["_vol"] = vol
    out["_today"] = today
    out["_max_fresh_today"] = max_fresh_today
    out["_supportish"] = supportish
    out["_breakoutish"] = breakoutish
    out["_trap"] = trap_risk
    out["710 Tier"] = tier
    out["710 Score"] = score
    out["Why 7-10%"] = out.apply(_reason, axis=1)
    out["ATR/Move Proxy"] = atr_proxy.round(2)

    return out.sort_values(["710 Tier", "710 Score"], ascending=[True, False], kind="stable")


def _show(df: pd.DataFrame, key: str) -> None:
    if df.empty:
        st.info("No rows in this tier with the current filters.")
        return
    preferred = [
        "Ticker", "710 Tier", "710 Score", "Why 7-10%", "Action", "Setup Type",
        "Support Tier", "Rise Prob", "Today %", "Upside to Res", "7D Move Est",
        "ATR/Move Proxy", "RR Est", "Vol Ratio", "Price", "Entry Quality",
        "Trap Risk", "Signals", "Buy Condition",
    ]
    cols = [c for c in preferred if c in df.columns]
    st.dataframe(df[cols].reset_index(drop=True), width="stretch", hide_index=True, key=key)
    st.code(", ".join(df["Ticker"].astype(str).head(80).tolist()))


def render_swing_710(ctx: dict) -> None:
    _bind_runtime(ctx)

    st.markdown("## 7-10% Swing Candidates")
    st.caption("Ranks the latest scan for short-term 7-10% potential. No extra Yahoo download is run from this tab.")

    src = _source_frame()
    if src.empty:
        st.info("Run a market scan first. This tab reuses Long Setups / master scan rows.")
        return

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        min_upside = st.slider("Minimum upside room %", 5.0, 15.0, 8.0, 0.5, key="s710_min_upside")
    with c2:
        min_atr = st.slider("Minimum move/range %", 2.0, 12.0, 3.5, 0.5, key="s710_min_atr")
    with c3:
        max_fresh_today = st.slider("Max today move for fresh buy %", 2.0, 8.0, 5.0, 0.5, key="s710_max_fresh_today")
    with c4:
        min_rr = st.slider("Minimum R:R", 1.0, 4.0, 2.0, 0.25, key="s710_min_rr")

    ranked = _classify(src, min_upside, min_atr, max_fresh_today, min_rr)

    search = st.text_input("Filter ticker / signal", "", key="s710_search").strip().upper()
    if search:
        hay = (
            ranked.get("Ticker", pd.Series("", index=ranked.index)).astype(str).str.upper()
            + " "
            + ranked.get("Signals", pd.Series("", index=ranked.index)).astype(str).str.upper()
            + " "
            + ranked.get("Action", pd.Series("", index=ranked.index)).astype(str).str.upper()
        )
        ranked = ranked[hay.str.contains(re.escape(search), na=False)].copy()

    tier_a = ranked[ranked["710 Tier"].eq("Tier A - Fresh Entry")]
    tier_b = ranked[ranked["710 Tier"].eq("Tier B - Breakout / Momentum")]
    tier_c = ranked[ranked["710 Tier"].eq("Tier C - Pullback Watch")]
    avoid = ranked[ranked["710 Tier"].eq("Avoid / Not Ready")]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Fresh Entry", len(tier_a))
    m2.metric("Breakout / Momentum", len(tier_b))
    m3.metric("Pullback Watch", len(tier_c))
    m4.metric("Avoid / Not Ready", len(avoid))

    st.markdown("### Tier A - Fresh Entry")
    st.caption("Best fit for a new position now: enough room, range, R:R, confirmation, and not too extended today.")
    _show(tier_a, "s710_tier_a")

    with st.expander(f"Tier B - Breakout / Momentum ({len(tier_b)})", expanded=True):
        st.caption("Active movers with volume or breakout evidence. Use tighter entries because they may already be moving.")
        _show(tier_b, "s710_tier_b")

    with st.expander(f"Tier C - Pullback Watch ({len(tier_c)})", expanded=True):
        st.caption("Support candidates that have potential but may need a better entry, pullback, or confirmation.")
        _show(tier_c, "s710_tier_c")

    with st.expander(f"Avoid / Not Ready ({len(avoid)})", expanded=False):
        st.caption("Rows failing room, range, R:R, extension, or trap filters.")
        _show(avoid, "s710_avoid")
