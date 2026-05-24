"""
Best 7-10% tab.

Strict combined view across Long Setups, Swing Picks, 7-10% Swing logic,
Pro Setups confluence, and Pre-Movers/7-Star evidence. It reuses the latest
scan data and does not download prices again.
"""

import re

import numpy as np
import pandas as pd
import streamlit as st


def _bind_runtime(ctx: dict) -> None:
    globals().update(ctx)


def _num(df: pd.DataFrame, col: str, default: float = 0.0) -> pd.Series:
    if col not in df.columns:
        return pd.Series([default] * len(df), index=df.index, dtype="float64")
    cleaned = (
        df[col].astype(str)
        .str.replace("%", "", regex=False)
        .str.replace("+", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.replace("x", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.extract(r"(-?\d+(?:\.\d+)?)")[0]
    )
    return pd.to_numeric(cleaned, errors="coerce").fillna(default)


def _text(df: pd.DataFrame, col: str, default: str = "") -> pd.Series:
    if col not in df.columns:
        return pd.Series([default] * len(df), index=df.index)
    return df[col].astype(str).fillna(default)


def _rr(df: pd.DataFrame) -> pd.Series:
    if "RR Est" not in df.columns:
        return pd.Series([0.0] * len(df), index=df.index)

    def parse(v) -> float:
        m = re.search(r"1\s*[:/]\s*([0-9]+(?:\.[0-9]+)?)", str(v))
        if m:
            return float(m.group(1))
        m = re.search(r"([0-9]+(?:\.[0-9]+)?)", str(v))
        return float(m.group(1)) if m else 0.0

    return df["RR Est"].map(parse).astype(float).fillna(0.0)


def _pro_score_from_signals(sig: str) -> int:
    sig = str(sig).upper()
    score = 0
    score += 3 if "HIGH-ACCURACY" in sig else 0
    score += 2 if "NEXT-DAY-A+" in sig else 0
    score += 2 if "DIP-MA20" in sig else 0
    score += 2 if "DIP-MA60" in sig else 0
    score += 2 if "VOL-DIP" in sig else 0
    score += 2 if "NR7" in sig else 0
    score += 2 if "INSIDE DAY" in sig else 0
    score += 2 if "BB BULL SQ" in sig else 0
    score += 2 if "RS>SPY" in sig else 0
    score += 2 if "WKLY TREND" in sig else 0
    score += 2 if "STOCH BOUNCE" in sig else 0
    score += 2 if "CUP+HANDLE" in sig else 0
    score += 1 if "MACD ACCEL" in sig else 0
    score += 1 if "HIGHER LOWS" in sig else 0
    score += 1 if "POCKET PIVOT" in sig else 0
    score += 1 if "FAILED BRKDN" in sig else 0
    score -= 5 if "CHASING" in sig else 0
    score -= 3 if "LIMIT-UP" in sig else 0
    return max(score, 0)


def _source_frame() -> pd.DataFrame:
    sources = []
    for key in ("df_long_master", "df_long"):
        sources.append(st.session_state.get(key, pd.DataFrame()))
        sources.append(globals().get(key, pd.DataFrame()))

    base = pd.DataFrame()
    for df in sources:
        if isinstance(df, pd.DataFrame) and not df.empty:
            base = df.copy()
            break

    if base.empty:
        return base
    if "Ticker" not in base.columns:
        base.insert(0, "Ticker", base.index.astype(str))
    base["Ticker"] = base["Ticker"].astype(str).str.upper()

    swing = st.session_state.get("df_swing_picks", pd.DataFrame())
    if isinstance(swing, pd.DataFrame) and not swing.empty and "Ticker" in swing.columns:
        swing = swing.copy()
        swing["Ticker"] = swing["Ticker"].astype(str).str.upper()
        keep = [c for c in [
            "Ticker", "Swing Verdict", "Final Swing Score", "Bayes Score",
            "Operator Score", "News Score", "Sector Score", "Earnings Risk",
            "Trap Risk Score", "Why",
        ] if c in swing.columns]
        swing = swing[keep].drop_duplicates("Ticker")
        base = base.merge(swing, on="Ticker", how="left", suffixes=("", " Swing"))

    return base.drop_duplicates("Ticker").reset_index(drop=True)


def _classify(df: pd.DataFrame, min_score: int, max_today: float, strict: bool) -> pd.DataFrame:
    out = df.copy()
    idx = out.index

    signals = _text(out, "Signals").str.upper()
    action = _text(out, "Action").str.upper()
    setup = _text(out, "Setup Type").str.upper()
    entry = _text(out, "Entry Quality").str.upper()
    tradeable = _text(out, "Tradeable Buy").str.upper().eq("YES")
    swing_verdict = _text(out, "Swing Verdict").str.upper()
    swing_pick_signal = swing_verdict.str.contains("BUY|WATCH", regex=True, na=False)
    premover_tier = _text(out, "Pre-Mover Tier").str.upper()
    explosion_tier = _text(out, "Explosion Tier").str.upper()
    seven_tier = _text(out, "7-Star Tier").str.upper()
    trap_label = _text(out, "Trap Risk").str.upper()

    today = _num(out, "Today %", 0)
    move5 = _num(out, "5D %", 0)
    move20 = _num(out, "20D %", 0)
    upside = _num(out, "Upside to Res", 0)
    move7 = _num(out, "7D Move Est", 0)
    atr = _num(out, "ATR%", 0)
    vol = _num(out, "Vol Ratio", 0)
    rise = _num(out, "Rise Prob", 0)
    quality = _num(out, "Quality Score", 0)
    nds = _num(out, "Next-Day Score", 0)
    seven = _num(out, "7-Star Score", 0).clip(0, 7)
    pm_score = _num(out, "Pre-Mover Score", 0)
    expl_score = _num(out, "Explosion Score", 0)
    swing_score = _num(out, "Final Swing Score", 0)
    rr = _rr(out)
    pro_score = signals.map(_pro_score_from_signals).astype(float)

    supportish = (
        setup.str.contains("SUPPORT|PULLBACK|DIP|MA20|MA60|MA200|VWAP|FAILED", regex=True, na=False)
        | signals.str.contains("SUPPORT|DIP|VOL-DIP|VWAP|MA20|MA60|MA200|FAILED BRKDN", regex=True, na=False)
    )
    breakoutish = (
        setup.str.contains("BREAKOUT|MOMENTUM|VOLUME|NR7|INSIDE|FLAG|CUP", regex=True, na=False)
        | signals.str.contains("BREAKOUT|POCKET|VOLUME|NR7|INSIDE|BB BULL SQ|HIGHER LOWS|MACD", regex=True, na=False)
    )

    moved_already = (today > max_today) | (move5 >= 25) | (move20 >= 50) | premover_tier.str.contains("MOVED", na=False) | explosion_tier.str.contains("MOVED", na=False) | seven_tier.str.contains("MOVED", na=False)
    hard_red = (today <= -5.0) & ~signals.str.contains("FAILED BRKDN", na=False)
    trap = trap_label.str.contains("TRAP|CHASING|DISTRIBUTION|LIMIT", regex=True, na=False) | signals.str.contains("CHASING|LIMIT-UP", regex=True, na=False)

    swing_component = pd.Series(np.maximum(
        np.minimum(swing_score.clip(lower=0), 100),
        np.where(swing_verdict.str.contains("BUY|WATCH ENTRY", regex=True, na=False), 85,
                 np.where(swing_verdict.str.contains("WATCH", na=False), 65,
                          np.where(tradeable, 70, 0))),
    ), index=idx)
    swing710_component = (
        np.minimum(upside.clip(lower=0), 14) / 14 * 35
        + np.minimum(move7.clip(lower=0), 12) / 12 * 25
        + np.minimum(rr.clip(lower=0), 3.5) / 3.5 * 25
        + np.where((supportish | breakoutish), 15, 0)
    )
    swing710_component = pd.Series(swing710_component, index=idx)
    premover_component = pd.Series(np.maximum(seven * 14.0, np.maximum(pm_score, expl_score)), index=idx)
    pro_component = np.minimum(pro_score, 20) / 20 * 100
    long_component = (
        np.minimum(np.maximum(quality, nds).clip(lower=0), 15) / 15 * 55
        + np.minimum(rise.clip(lower=0), 100) / 100 * 35
        + np.where(entry.str.contains("BUY", na=False) | action.str.contains("BUY", na=False), 10, 0)
    )
    long_component = pd.Series(long_component, index=idx)

    combo = (
        swing710_component * 0.30
        + swing_component * 0.25
        + premover_component * 0.20
        + pro_component * 0.15
        + long_component * 0.10
    )
    combo = pd.Series(combo, index=idx).clip(0, 100)
    combo -= np.where(moved_already, 18, 0)
    combo -= np.where(hard_red, 18, 0)
    combo -= np.where(trap, 18, 0)
    combo -= np.where((vol < 0.75) & ~supportish, 6, 0)
    combo = combo.clip(0, 100).round(1)

    passes_core = (
        (move7 >= 6.0)
        & ((upside >= 7.0) | breakoutish)
        & (rr >= (1.8 if strict else 1.5))
        & (today <= max_today)
        & (today >= -5.0)
        & ~moved_already
        & ~trap
    )
    multi_confirm = (
        tradeable.astype(int)
        + (seven >= 5).astype(int)
        + swing_pick_signal.astype(int)
        + (pro_score >= 8).astype(int)
        + (pm_score >= 55).astype(int)
        + (expl_score >= 45).astype(int)
    )
    confirm_needed = 3 if strict else 2

    tier = pd.Series("Reject / Too Risky", index=idx)
    tier.loc[(combo >= 62) & passes_core & (multi_confirm >= confirm_needed)] = "A - Watch For Trigger"
    tier.loc[(combo >= 75) & passes_core & (multi_confirm >= confirm_needed + 1) & (seven >= 5) & (tradeable | swing_pick_signal)] = "A+ - Best 7-10%"
    tier.loc[(combo >= 52) & ~tier.str.startswith("A") & ~moved_already & ~trap & (today <= max_today)] = "B - Early Watch"
    tier.loc[moved_already] = "Reject - Moved Already"
    tier.loc[hard_red] = "Reject - Weak Red"
    tier.loc[trap] = "Reject - Trap Risk"

    price = _num(out, "Price", 0)
    best_stop = _num(out, "Best Stop", 0)
    ma_stop = _num(out, "MA60 Stop", 0)
    stop = best_stop.where(best_stop > 0, ma_stop)
    stop = stop.where(stop > 0, price * 0.94)
    trigger = price * 1.008
    trigger = trigger.where(today <= 0, price * 1.004)

    why = []
    for i in idx:
        parts = []
        if passes_core.loc[i]: parts.append("7-10% gates pass")
        if tradeable.loc[i]: parts.append("tradeable buy")
        if seven.loc[i] >= 5: parts.append(f"7-star {int(seven.loc[i])}")
        if swing_pick_signal.loc[i]: parts.append("swing pick support")
        if pro_score.loc[i] >= 8: parts.append(f"pro {int(pro_score.loc[i])}")
        if pm_score.loc[i] >= 55: parts.append("pre-mover")
        if expl_score.loc[i] >= 45: parts.append("explosive watch")
        if moved_already.loc[i]: parts.append("already ran")
        if hard_red.loc[i]: parts.append("hard red")
        if trap.loc[i]: parts.append("trap/chase risk")
        why.append(" | ".join(parts[:7]) if parts else "not enough combined evidence")

    out["Best 710 Score"] = combo
    out["Best 710 Tier"] = tier
    out["Best 710 Why"] = why
    if "7-Star Score" not in out.columns:
        out["7-Star Score"] = seven.astype(int)
    if "Pro Score" not in out.columns:
        out["Pro Score"] = pro_score.astype(int)
    out["Trigger Above"] = trigger.round(2).map(lambda x: f"${x:.2f}" if x > 0 else "-")
    out["Invalid Below"] = stop.round(2).map(lambda x: f"${x:.2f}" if x > 0 else "-")
    out["_combo_sort"] = combo
    out["_tier_sort"] = tier.map({
        "A+ - Best 7-10%": 4,
        "A - Watch For Trigger": 3,
        "B - Early Watch": 2,
        "Reject - Moved Already": 1,
        "Reject / Too Risky": 0,
        "Reject - Weak Red": 0,
        "Reject - Trap Risk": 0,
    }).fillna(0)
    out = out[out["Best 710 Score"] >= min_score].copy()
    return out.sort_values(["_tier_sort", "_combo_sort"], ascending=[False, False], kind="stable")


def _show(df: pd.DataFrame, key: str) -> None:
    if df.empty:
        st.info("No rows in this bucket with the current filters.")
        return
    preferred = [
        "Ticker", "Best 710 Score", "Best 710 Tier", "Best 710 Why",
        "Trigger Above", "Invalid Below", "Tradeable Buy", "7-Star Score",
        "7-Star Tier", "Pre-Mover Score", "Explosion Score", "Quality Score",
        "Next-Day Score", "Final Swing Score", "Rise Prob", "Today %",
        "5D %", "20D %", "7D Move Est", "Upside to Res", "RR Est",
        "Vol Ratio", "ATR%", "Action", "Entry Quality", "Setup Type",
        "Swing Verdict", "Trap Risk", "Price", "Signals",
    ]
    cols = [c for c in preferred if c in df.columns]
    st.dataframe(df[cols].reset_index(drop=True), use_container_width=True, hide_index=True, key=key)
    if "Ticker" in df.columns:
        st.code(", ".join(df["Ticker"].astype(str).head(80).tolist()))


def render_best_710(ctx: dict) -> None:
    _bind_runtime(ctx)

    st.markdown("## Best 7-10% Candidates")
    st.caption("Strict combined view across Long Setups, 7-10% Swing, Swing Picks, Pro Setups, and Pre-Movers. No extra Yahoo download is run.")

    src = _source_frame()
    if src.empty:
        st.info("Run a market scan first. Build Swing Picks too if you want the combined score to include enriched news/earnings evidence.")
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        min_score = st.slider("Minimum combined score", 0, 100, 50, step=5, key="best710_min_score")
    with c2:
        max_today = st.slider("Max today move %", 2.0, 8.0, 3.5, step=0.5, key="best710_max_today")
    with c3:
        strict = st.checkbox("Strict multi-confirmation", value=True, key="best710_strict")

    ranked = _classify(src, min_score=min_score, max_today=max_today, strict=strict)

    search = st.text_input("Filter ticker / signal", "", key="best710_search").strip().upper()
    if search:
        hay = (
            ranked.get("Ticker", pd.Series("", index=ranked.index)).astype(str).str.upper()
            + " " + ranked.get("Signals", pd.Series("", index=ranked.index)).astype(str).str.upper()
            + " " + ranked.get("Best 710 Why", pd.Series("", index=ranked.index)).astype(str).str.upper()
        )
        ranked = ranked[hay.str.contains(re.escape(search), na=False)].copy()

    best = ranked[ranked["Best 710 Tier"].eq("A+ - Best 7-10%")]
    trigger = ranked[ranked["Best 710 Tier"].eq("A - Watch For Trigger")]
    early = ranked[ranked["Best 710 Tier"].eq("B - Early Watch")]
    reject = ranked[ranked["Best 710 Tier"].str.startswith("Reject", na=False)]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("A+ Best", len(best))
    m2.metric("A Trigger", len(trigger))
    m3.metric("B Early", len(early))
    m4.metric("Rejected", len(reject))

    st.markdown("### A+ - Best 7-10%")
    st.caption("Strongest combined evidence. Still use Trigger Above and Invalid Below.")
    _show(best, "best710_best")

    with st.expander(f"A - Watch For Trigger ({len(trigger)})", expanded=True):
        _show(trigger, "best710_trigger")

    with st.expander(f"B - Early Watch ({len(early)})", expanded=True):
        _show(early, "best710_early")

    with st.expander(f"Rejected / Too Risky ({len(reject)})", expanded=False):
        _show(reject, "best710_reject")
