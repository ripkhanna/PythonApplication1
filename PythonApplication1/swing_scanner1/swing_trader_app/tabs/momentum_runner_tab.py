"""Momentum Runner tab.

Finds early ignition stocks and already-running names from the latest scan
cache. This is intentionally separate from Best 7-10%, which stays focused on
clean swing entries before a move is extended.
"""

from __future__ import annotations

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


def _txt(df: pd.DataFrame, col: str, default: str = "") -> pd.Series:
    if col not in df.columns:
        return pd.Series([default] * len(df), index=df.index)
    return df[col].astype(str).fillna(default)


def _source_frame() -> pd.DataFrame:
    sources = []
    for key in ("df_long_master", "df_long"):
        sources.append(st.session_state.get(key, pd.DataFrame()))
        sources.append(globals().get(key, pd.DataFrame()))

    for df in sources:
        if isinstance(df, pd.DataFrame) and not df.empty:
            out = df.copy()
            if "Ticker" not in out.columns:
                out.insert(0, "Ticker", out.index.astype(str))
            out["Ticker"] = out["Ticker"].astype(str).str.upper()
            return out.drop_duplicates("Ticker").reset_index(drop=True)
    return pd.DataFrame()


def _classify(df: pd.DataFrame, min_score: int, show_chase: bool) -> pd.DataFrame:
    out = df.copy()
    idx = out.index

    signals = _txt(out, "Signals").str.upper()
    action = _txt(out, "Action").str.upper()
    entry = _txt(out, "Entry Quality").str.upper()
    trap_label = _txt(out, "Trap Risk").str.upper()
    pre_tier = _txt(out, "Pre-Mover Tier").str.upper()
    expl_tier = _txt(out, "Explosion Tier").str.upper()
    seven_tier = _txt(out, "7-Star Tier").str.upper()

    today = _num(out, "Today %", 0)
    pm = _num(out, "PM Chg%", 0)
    move5 = _num(out, "5D %", 0)
    move20 = _num(out, "20D %", 0)
    move7 = _num(out, "7D Move Est", 0)
    upside = _num(out, "Upside to Res", 0)
    rr = _num(out, "RR Est", 0)
    rise = _num(out, "Rise Prob", 0)
    vol = _num(out, "Vol Ratio", 0)
    atr = _num(out, "ATR%", 0)
    quality = _num(out, "Quality Score", 0)
    seven = _num(out, "7-Star Score", 0)
    pre_score = _num(out, "Pre-Mover Score", 0)
    expl_score = _num(out, "Explosion Score", 0)
    op_score = _num(out, "Op Score", 0)
    price = _num(out, "Price", 0)

    has_live_move = (pm >= 2.0) | (today >= 2.0)
    ignition_move = ((pm >= 3.0) | (today >= 3.0)) & (pm <= 12.0) & (today <= 15.0)
    controlled_runner = (
        ((pm >= 1.0) | (today >= 1.0) | (move5 >= 5.0))
        & (today <= 8.0)
        & (move5 <= 30.0)
        & (move20 <= 55.0)
    )
    too_hot = (pm >= 15.0) | (today >= 15.0) | (move5 >= 35.0) | (move20 >= 65.0)
    reset_watch = too_hot & (rise >= 55.0) & (atr >= 5.0)

    breakout = signals.str.contains(
        r"BREAKOUT|HIGHER LOWS|COMBO\+5|POCKET|NR7|INSIDE|BB BULL SQ|MACD|RS>SPY|WKLY TREND",
        regex=True,
        na=False,
    )
    fuel = signals.str.contains(
        r"CALL FLOW|CALL SKEW|PRE-EARN|PEAD|EARNINGS|CATALYST|SQZ|ABSORPTION|HIGH-ACCURACY|NEXT-DAY",
        regex=True,
        na=False,
    )
    runner_quality = (
        (quality >= 8)
        | (seven >= 4)
        | (pre_score >= 45)
        | (expl_score >= 35)
        | (rise >= 65)
        | fuel
    )
    quality_ok = (
        runner_quality
        | breakout
    )
    avoid_entry = entry.str.contains("AVOID|SKIP", regex=True, na=False) | action.str.contains("TRAP RISK", regex=True, na=False)
    liq_ok = (price >= 1.0) & ((vol >= 0.5) | (today >= 5.0) | (pm >= 5.0))
    vol_ok = (atr >= 3.5) | (move7 >= 7.0)
    trap = (
        trap_label.str.contains("TRAP|DISTRIB|LIMIT", regex=True, na=False)
        | signals.str.contains("LIMIT-UP", regex=True, na=False)
    )
    chase_flag = signals.str.contains("CHASING", regex=False, na=False) | too_hot
    broken = (today <= -5.0) | (pm <= -5.0)

    score = pd.Series(0.0, index=idx)
    score += np.minimum(pm.clip(lower=0), 12) / 12 * 18
    score += np.minimum(today.clip(lower=0), 15) / 15 * 22
    score += np.minimum(move5.clip(lower=0), 30) / 30 * 12
    score += np.minimum(atr.clip(lower=0), 10) / 10 * 12
    score += np.minimum(vol.clip(lower=0), 3) / 3 * 10
    score += breakout.astype(int) * 12
    score += fuel.astype(int) * 8
    score += quality_ok.astype(int) * 10
    score += (op_score >= 2).astype(int) * 4
    score -= trap.astype(int) * 18
    score -= avoid_entry.astype(int) * 10
    score -= broken.astype(int) * 25
    score -= ((move20 >= 90) | (move5 >= 50)).astype(int) * 15
    score = score.clip(0, 100).round(1)

    # A+ Explosive is for the user's 5-10% same-day momentum objective.
    # It is deliberately separate from normal swing accuracy: these are fast movers
    # that need opening-range/VWAP confirmation, not blind entries.
    explosive_live_move = (pm.between(2.0, 9.5) | today.between(2.0, 9.5))
    explosive_volume = vol.between(1.5, 7.0) | ((pm >= 4.0) | (today >= 4.0))
    explosive_atr = atr.between(3.0, 12.0) | (move7 >= 7.0)
    explosive_fuel = breakout | fuel | signals.str.contains(
        r"PREMARKET|PRE-MARKET|GAPPER|GAP|NEWS|CATALYST|EARNINGS|FDA|CONTRACT|GUIDANCE|UPGRADE|SHORT SQUEEZE|VOLUME BREAKOUT|VOL BREAKOUT|52W|HOD|ORB|VWAP",
        regex=True,
        na=False,
    )
    explosive_liq = (price >= 2.0) & ((vol >= 1.0) | (pm >= 3.0) | (today >= 3.0))
    explosive_not_chase = (pm <= 12.0) & (today <= 12.0) & (move5 <= 45.0) & (move20 <= 85.0)
    explosive_setup = (
        explosive_live_move
        & explosive_volume
        & explosive_atr
        & explosive_fuel
        & explosive_liq
        & explosive_not_chase
        & ~avoid_entry
        & ~trap
        & ~broken
    )

    tier = pd.Series("D - Not A Runner", index=idx)
    tier.loc[controlled_runner & quality_ok & liq_ok & vol_ok & ~avoid_entry] = "B - Controlled Runner"
    tier.loc[ignition_move & runner_quality & liq_ok & vol_ok & ~avoid_entry & ~trap & ~too_hot] = "A - Day-1 Ignition"
    tier.loc[explosive_setup] = "A+ Explosive 5-10% Today"
    tier.loc[reset_watch & ~broken] = "C - Hot Runner / Wait Reset"
    tier.loc[trap | chase_flag] = "C - Hot Runner / Wait Reset"
    tier.loc[broken] = "Reject - Broken Move"

    invalid = price * 0.94
    invalid = invalid.where(~(tier.eq("A - Day-1 Ignition")), price * 0.965)
    invalid = invalid.where(~(tier.eq("A+ Explosive 5-10% Today")), price * 0.975)
    trigger = price * 1.006
    trigger = trigger.where(today <= 0, price * 1.003)
    trigger = trigger.where(~(tier.eq("A+ Explosive 5-10% Today")), price * 1.004)

    explosive_target_1 = price * 1.05
    explosive_target_2 = price * 1.10

    why = []
    for i in idx:
        parts = []
        if ignition_move.loc[i]: parts.append("ignition move")
        if controlled_runner.loc[i]: parts.append("controlled runner")
        if reset_watch.loc[i]: parts.append("wait reset")
        if pm.loc[i] >= 2.0: parts.append(f"PM +{pm.loc[i]:.1f}%")
        if today.loc[i] >= 2.0: parts.append(f"today +{today.loc[i]:.1f}%")
        if move5.loc[i] >= 10.0: parts.append(f"5D +{move5.loc[i]:.1f}%")
        if breakout.loc[i]: parts.append("breakout/RS")
        if fuel.loc[i]: parts.append("fuel")
        if explosive_setup.loc[i]: parts.append("A+ explosive 5-10% candidate")
        if explosive_volume.loc[i]: parts.append("volume fuel")
        if explosive_atr.loc[i]: parts.append("ATR can move")
        if too_hot.loc[i]: parts.append("too hot")
        if trap.loc[i]: parts.append("trap risk")
        if broken.loc[i]: parts.append("broken")
        why.append(" | ".join(parts[:8]) if parts else "no runner evidence")

    out["Runner Score"] = score
    out["Runner Tier"] = tier
    out["Runner Why"] = why
    out["Explosive Buy"] = np.where(tier.eq("A+ Explosive 5-10% Today"), "YES - only above trigger / VWAP", "NO")
    out["Runner Trigger"] = trigger.round(2).map(lambda x: f"${x:.2f}" if x > 0 else "-")
    out["Runner Invalid"] = invalid.round(2).map(lambda x: f"${x:.2f}" if x > 0 else "-")
    out["Target 1 +5%"] = explosive_target_1.round(2).map(lambda x: f"${x:.2f}" if x > 0 else "-")
    out["Target 2 +10%"] = explosive_target_2.round(2).map(lambda x: f"${x:.2f}" if x > 0 else "-")
    out["_tier_sort"] = tier.map({
        "A+ Explosive 5-10% Today": 5,
        "A - Day-1 Ignition": 4,
        "B - Controlled Runner": 3,
        "C - Hot Runner / Wait Reset": 2,
        "D - Not A Runner": 1,
        "Reject - Broken Move": 0,
    }).fillna(0)
    out["_runner_sort"] = score

    keep = out["Runner Score"] >= min_score
    if not show_chase:
        keep &= ~out["Runner Tier"].eq("C - Hot Runner / Wait Reset")
    return out[keep].sort_values(["_tier_sort", "_runner_sort"], ascending=[False, False], kind="stable")


def _show(df: pd.DataFrame, key: str) -> None:
    if df.empty:
        st.info("No rows in this bucket with the current filters.")
        return
    preferred = [
        "Ticker", "Runner Score", "Runner Tier", "Explosive Buy", "Runner Why",
        "Runner Trigger", "Runner Invalid", "Target 1 +5%", "Target 2 +10%", "PM Chg%", "PM Price",
        "Today %", "5D %", "20D %", "Vol Ratio", "ATR%",
        "7D Move Est", "Upside to Res", "RR Est", "Rise Prob",
        "Action", "Entry Quality", "Tradeable Buy", "7-Star Score",
        "Pre-Mover Score", "Explosion Score", "Trap Risk", "Price", "Signals",
    ]
    cols = [c for c in preferred if c in df.columns]
    st.dataframe(df[cols].reset_index(drop=True), width="stretch", hide_index=True, key=key)
    if "Ticker" in df.columns:
        st.code(", ".join(df["Ticker"].astype(str).head(80).tolist()))


def render_momentum_runner(ctx: dict) -> None:
    _bind_runtime(ctx)

    st.markdown("## Momentum Runner / Explosive 5-10%")
    st.caption("Use this tab for explosive same-day 5-10% movers. It separates A+ explosive candidates from normal swing picks and hot names that need a reset.")
    st.warning("For 5-10% same-day trades, do not buy only from the scan row. Wait for opening-range breakout or VWAP reclaim/hold, then use the trigger/invalid levels.")

    src = _source_frame()
    if src.empty:
        st.info("Run a market scan first. This tab ranks the latest long-scan rows and does not download fresh prices.")
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        min_score = st.slider("Minimum runner score", 0, 100, 35, step=5, key="runner_min_score")
    with c2:
        show_chase = st.checkbox("Show hot wait-reset names", value=True, key="runner_show_chase")
    with c3:
        show_n = st.slider("Show top N", 10, 150, 60, step=10, key="runner_show_n")

    ranked = _classify(src, min_score=min_score, show_chase=show_chase)

    search = st.text_input("Filter ticker / signal", "", key="runner_search").strip().upper()
    if search:
        hay = (
            ranked.get("Ticker", pd.Series("", index=ranked.index)).astype(str).str.upper()
            + " " + ranked.get("Signals", pd.Series("", index=ranked.index)).astype(str).str.upper()
            + " " + ranked.get("Runner Why", pd.Series("", index=ranked.index)).astype(str).str.upper()
        )
        ranked = ranked[hay.str.contains(re.escape(search), na=False)].copy()

    explosive = ranked[ranked["Runner Tier"].eq("A+ Explosive 5-10% Today")].head(show_n)
    ignition = ranked[ranked["Runner Tier"].eq("A - Day-1 Ignition")].head(show_n)
    controlled = ranked[ranked["Runner Tier"].eq("B - Controlled Runner")].head(show_n)
    reset = ranked[ranked["Runner Tier"].eq("C - Hot Runner / Wait Reset")].head(show_n)

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("A+ Explosive", len(explosive))
    m2.metric("Ignition", len(ignition))
    m3.metric("Controlled", len(controlled))
    m4.metric("Wait Reset", len(reset))
    m5.metric("Rows", len(ranked))

    st.markdown("### A+ Explosive 5-10% Today")
    st.caption("Primary bucket for your requirement: stocks already showing ignition but not yet too extended. Entry should be above trigger/VWAP, not a blind buy.")
    _show(explosive, "runner_explosive")

    with st.expander(f"A - Day-1 Ignition ({len(ignition)})", expanded=True):
        _show(ignition, "runner_ignition")

    with st.expander(f"B - Controlled Runner ({len(controlled)})", expanded=True):
        _show(controlled, "runner_controlled")

    with st.expander(f"C - Hot Runner / Wait Reset ({len(reset)})", expanded=False):
        _show(reset, "runner_reset")

    with st.expander("Exact rule for A+ Explosive 5-10% Today"):
        st.markdown("""
A stock enters the A+ explosive bucket only when it has:

- PM or current day move between about **+2% and +9.5%**
- volume fuel, usually **Vol Ratio 1.5x-7x** or strong PM/current move
- enough movement potential: **ATR% 3-12** or estimated 7D move >= 7%
- breakout/catalyst/fuel signal such as news, earnings, gapper, 52W, VWAP, ORB, volume breakout
- price >= $2 and no trap/broken/chase flags

This is intentionally aggressive. Use it for intraday momentum, not long-term investing.
        """)
