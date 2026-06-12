"""Pullback Reclaim strategy tab.

Finds previously strong stocks correcting toward support and waits for a
reclaim/volume confirmation before declaring an actionable swing entry.
Uses the latest scanner DataFrame; it performs no additional market download.
"""

from __future__ import annotations

import re
import numpy as np
import pandas as pd
import streamlit as st


def _bind_runtime(ctx: dict) -> None:
    globals().update(ctx)


def _source_frame() -> pd.DataFrame:
    candidates = [
        st.session_state.get("df_long_master", pd.DataFrame()),
        st.session_state.get("df_long", pd.DataFrame()),
        globals().get("df_long_master", pd.DataFrame()),
        globals().get("df_long", pd.DataFrame()),
    ]
    for frame in candidates:
        if isinstance(frame, pd.DataFrame) and not frame.empty:
            out = frame.copy()
            if "Ticker" not in out.columns:
                out.insert(0, "Ticker", out.index.astype(str))
            out["Ticker"] = out["Ticker"].astype(str).str.upper()
            return out.drop_duplicates("Ticker").reset_index(drop=True)
    return pd.DataFrame()


def _num(df: pd.DataFrame, col: str, default: float = 0.0) -> pd.Series:
    if col not in df.columns:
        return pd.Series(default, index=df.index, dtype="float64")
    s = (
        df[col].astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("%", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.replace("S$", "", regex=False)
        .str.replace("HK$", "", regex=False)
        .str.replace("₹", "", regex=False)
        .str.extract(r"(-?\d+(?:\.\d+)?)", expand=False)
    )
    return pd.to_numeric(s, errors="coerce").fillna(default)


def _rr(df: pd.DataFrame) -> pd.Series:
    if "RR Est" not in df.columns:
        return pd.Series(0.0, index=df.index)
    def parse(v: object) -> float:
        m = re.search(r"1\s*[:/]\s*([0-9]+(?:\.[0-9]+)?)", str(v))
        if m:
            return float(m.group(1))
        m = re.search(r"([0-9]+(?:\.[0-9]+)?)", str(v))
        return float(m.group(1)) if m else 0.0
    return df["RR Est"].map(parse).fillna(0.0)


def _currency(ticker: str) -> str:
    t = str(ticker).upper()
    if t.endswith(".SI"):
        return "S$"
    if t.endswith(".HK"):
        return "HK$"
    if t.endswith(".NS") or t.endswith(".BO"):
        return "₹"
    return "$"


def _fmt_price(v: float, ticker: str) -> str:
    if not np.isfinite(v) or v <= 0:
        return "–"
    return f"{_currency(ticker)}{v:.2f}"


def _classify(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    signals = out.get("Signals", "").astype(str).str.upper()
    setup = out.get("Setup Type", "").astype(str).str.upper()
    entry = out.get("Entry Quality", "").astype(str).str.upper()
    sector = out.get("Sector", "").astype(str).str.upper()
    trap = out.get("Trap Risk", "").astype(str).str.upper()

    price = _num(out, "Price")
    ma5 = _num(out, "MA5")
    ma10 = _num(out, "MA10")
    ma20 = _num(out, "MA20")
    stop = _num(out, "Best Stop")
    ma60_stop = _num(out, "MA60 Stop")
    move5 = _num(out, "5D %")
    move20 = _num(out, "20D %")
    today = _num(out, "Today %")
    rsi = _num(out, "RSI", 50)
    vol = _num(out, "Vol Ratio")
    atr = _num(out, "ATR%")
    rr = _rr(out)
    quality = _num(out, "Quality Score")
    nd_score = _num(out, "Next-Day Score")

    dist_ma5 = np.where(ma5 > 0, (price / ma5 - 1.0) * 100.0, np.nan)
    dist_ma10 = np.where(ma10 > 0, (price / ma10 - 1.0) * 100.0, np.nan)
    dist_ma20 = np.where(ma20 > 0, (price / ma20 - 1.0) * 100.0, np.nan)

    # Backward compatibility: old caches may not yet contain MA5/MA10.
    has_short_ma = (ma5 > 0) & (ma10 > 0)
    above_ma5 = has_short_ma & (price > ma5)
    above_ma10 = has_short_ma & (price > ma10)
    ma5_above_ma10 = has_short_ma & (ma5 > ma10)
    ma5_rising = out.get("MA5 Rising", "").astype(str).str.upper().eq("YES") if "MA5 Rising" in out.columns else pd.Series(False, index=out.index)
    ma10_rising = out.get("MA10 Rising", "").astype(str).str.upper().eq("YES") if "MA10 Rising" in out.columns else pd.Series(False, index=out.index)
    ma_cross = out.get("MA5/10 Cross", "").astype(str).str.upper().eq("BULL") if "MA5/10 Cross" in out.columns else pd.Series(False, index=out.index)
    short_ma_early = above_ma5 & (~above_ma10 | ~ma5_above_ma10)
    short_ma_confirmed = above_ma5 & above_ma10 & ma5_above_ma10 & (ma5_rising | ma_cross)
    short_ma_weak = has_short_ma & (price < ma5) & (price < ma10)

    prior_rally = (move20 >= 8.0) | ((move20 >= 5.0) & (move5 < move20 * 0.6))
    controlled_pullback = (
        (today >= -6.0) & (today <= 2.0)
        & (move5 <= 3.0)
        & (atr.between(1.5, 12.0) | atr.eq(0))
    )
    near_support = (
        pd.Series(dist_ma20, index=out.index).between(-4.0, 4.0)
        | setup.str.contains("SUPPORT|PULLBACK|DIP|MA20|MA60|MA200|VWAP|FAILED", regex=True, na=False)
        | signals.str.contains("DIP-MA20|DIP-MA60|VOL-DIP|FAILED BRKDN|SUPPORT|VWAP", regex=True, na=False)
    )
    macd_bear = signals.str.contains("MACD DECEL|MACD BEAR|MACD CROSS BEAR", regex=True, na=False)
    macd_improving = signals.str.contains("MACD ACCEL|STOCH BOUNCE|FAILED BRKDN|HIGHER LOWS", regex=True, na=False)
    technical_reclaim = (
        signals.str.contains("MACD ACCEL|HIGHER LOWS|FAILED BRKDN|POCKET PIVOT|VOL SURGE|BREAKOUT|VWAP", regex=True, na=False)
        | setup.str.contains("BREAKOUT|REVERSAL|SUPPORT BOUNCE", regex=True, na=False)
        | (today > 0.3)
    )
    # With fresh scan data, require MA5/MA10 evidence. Old cache rows fall back to technical reclaim.
    early_reclaim = np.where(has_short_ma, short_ma_early | short_ma_confirmed, technical_reclaim)
    confirmed_reclaim = np.where(has_short_ma, short_ma_confirmed, technical_reclaim)
    early_reclaim = pd.Series(early_reclaim, index=out.index, dtype=bool)
    confirmed_reclaim = pd.Series(confirmed_reclaim, index=out.index, dtype=bool)
    # 1.15x is enough for reclaim confirmation; stronger named volume signals
    # remain valid. This is more suitable for SGX/HK/India, where vendor volume
    # ratios are often understated compared with US feeds.
    volume_confirm = (vol >= 1.15) | signals.str.contains("VOL SURGE|POCKET PIVOT|VOLUME|VOL-DIP", regex=True, na=False)
    sector_ok = ~sector.str.contains("🔴|RED|WEAK", regex=True, na=False)
    clean_risk = ~trap.str.contains("TRAP|HIGH|AVOID|BROKEN|CHASE", regex=True, na=False)
    support_broken = (
        ((stop > 0) & (price < stop))
        | ((ma60_stop > 0) & (price < ma60_stop * 0.995))
        | signals.str.contains("BREAKDOWN|SUPPORT BROKEN|LOWER LOW", regex=True, na=False)
    )

    score = (
        prior_rally.astype(int) * 16
        + controlled_pullback.astype(int) * 12
        + near_support.astype(int) * 18
        + macd_improving.astype(int) * 8
        + early_reclaim.astype(int) * 8
        + confirmed_reclaim.astype(int) * 12
        + ma5_rising.astype(int) * 4
        + ma10_rising.astype(int) * 3
        + volume_confirm.astype(int) * 12
        + sector_ok.astype(int) * 8
        + clean_risk.astype(int) * 6
        + (rr >= 2.0).astype(int) * 10
        + (quality >= 12).astype(int) * 6
        + (nd_score >= 12).astype(int) * 4
        - support_broken.astype(int) * 60
        - ((rsi > 75) | (today > 7)).astype(int) * 15
    ).clip(0, 100)

    # A confirmed reclaim normally moves away from the exact support zone. Do not
    # require it to remain within the near-support band after MA5/MA10 recovery.
    # Also, RR Est may belong to another strategy or be unavailable, so treat a
    # missing value as neutral and only reject clearly poor RR values.
    rr_ok = (rr >= 1.5) | rr.eq(0)
    post_support_reclaim = confirmed_reclaim & (
        technical_reclaim
        | ma5_rising
        | ma10_rising
        | ma_cross
        | (today >= 0.3)
    )
    confirmed = (
        prior_rally
        & post_support_reclaim
        & volume_confirm
        & sector_ok
        & clean_risk
        & rr_ok
        & ~support_broken
    )
    early = prior_rally & near_support & (early_reclaim | macd_improving) & clean_risk & ~support_broken
    watch = prior_rally & controlled_pullback & near_support & ~support_broken
    # A fresh cache with price below both MA5 and MA10 must remain WATCH, not an early buy.
    early = early & ~short_ma_weak

    decision = np.select(
        [support_broken, confirmed, early, watch, prior_rally],
        [
            "🚫 SKIP – SUPPORT BROKEN",
            "✅ BUY ABOVE RECLAIM",
            "🟢 SMALL ENTRY / CONFIRM RECLAIM",
            "🟡 WATCH SUPPORT",
            "⚪ WAIT – PULLBACK NOT AT SUPPORT",
        ],
        default="🚫 SKIP – NO PRIOR RALLY",
    )
    stage = np.select(
        [support_broken, confirmed, early, watch],
        ["4 Invalidated", "3 Confirmed Reclaim", "2 Early Reclaim", "1 Support Watch"],
        default="0 Not Qualified",
    )

    support_price = np.where(ma20 > 0, ma20, np.where(stop > 0, stop * 1.02, price * 0.97))
    # Trigger ladder: first reclaim MA5, then MA10; confirmed entries must clear the higher short MA.
    short_ma_trigger = np.maximum(np.where(ma5 > 0, ma5, price), np.where(ma10 > 0, ma10, price))
    reclaim_trigger = np.maximum(price * 1.003, short_ma_trigger * 1.002)
    # If price is still below MA20, MA20 remains the stronger confirmation trigger.
    reclaim_trigger = np.where((ma20 > 0) & (price < ma20), np.maximum(reclaim_trigger, ma20 * 1.002), reclaim_trigger)
    invalidation = np.where(stop > 0, stop, np.where(ma60_stop > 0, ma60_stop, support_price * 0.97))
    risk = np.maximum(reclaim_trigger - invalidation, price * 0.005)
    target1 = reclaim_trigger + risk * 2.0
    target2 = reclaim_trigger + risk * 3.0

    out["Pullback Rank Score"] = score.astype(int)
    out["Pullback Decision"] = decision
    out["Pullback Stage"] = stage
    out["Prior Rally %"] = move20.round(2)
    out["Distance MA5 %"] = pd.Series(dist_ma5, index=out.index).round(2)
    out["Distance MA10 %"] = pd.Series(dist_ma10, index=out.index).round(2)
    out["Distance MA20 %"] = pd.Series(dist_ma20, index=out.index).round(2)
    out["MA5/10 Status"] = np.select(
        [
            short_ma_confirmed,
            above_ma5 & above_ma10,
            above_ma5 & ~above_ma10,
            short_ma_weak,
            ~has_short_ma,
        ],
        [
            "CONFIRMED: Price > MA5 > MA10",
            "IMPROVING: Above MA5 & MA10",
            "EARLY: Above MA5 only",
            "WEAK: Below MA5 & MA10",
            "UNAVAILABLE: rescan required",
        ],
        default="MIXED / WAIT",
    )
    out["MACD State"] = np.select(
        [macd_improving, macd_bear], ["Improving", "Bearish / still correcting"], default="Neutral / unavailable"
    )
    out["Volume Confirmation"] = np.where(volume_confirm, "YES", "NO")
    out["Sector Alignment"] = np.where(sector_ok, "OK", "WEAK")
    out["Why Not Confirmed"] = np.select(
        [
            confirmed,
            ~prior_rally,
            support_broken,
            ~confirmed_reclaim,
            ~volume_confirm,
            ~sector_ok,
            ~clean_risk,
            ~rr_ok,
        ],
        [
            "CONFIRMED",
            "No qualifying prior rally",
            "Support/invalidation broken",
            "MA5/MA10 reclaim not confirmed",
            "Volume confirmation missing",
            "Sector is weak",
            "Trap/chase risk present",
            "RR below 1:1.5",
        ],
        default="Waiting for trigger confirmation",
    )
    out["Support Zone"] = [_fmt_price(float(v), t) for v, t in zip(support_price, out["Ticker"])]
    out["Reclaim Trigger"] = [_fmt_price(float(v), t) for v, t in zip(reclaim_trigger, out["Ticker"])]
    out["Invalidation"] = [_fmt_price(float(v), t) for v, t in zip(invalidation, out["Ticker"])]
    out["Target 1 (2R)"] = [_fmt_price(float(v), t) for v, t in zip(target1, out["Ticker"])]
    out["Target 2 (3R)"] = [_fmt_price(float(v), t) for v, t in zip(target2, out["Ticker"])]
    out["Pullback Checklist"] = [
        " | ".join([
            "Rally✅" if a else "Rally❌",
            "Support✅" if b else "Support⏳",
            "Momentum✅" if c else "Momentum⏳",
            "Volume✅" if d else "Volume⏳",
            "Sector✅" if e else "Sector❌",
            "RR✅" if f else "RR❌",
        ])
        for a, b, c, d, e, f in zip(prior_rally, near_support | confirmed_reclaim, early_reclaim | macd_improving, volume_confirm, sector_ok, rr_ok)
    ]
    return out.sort_values(["Pullback Rank Score", "Quality Score", "Next-Day Score"], ascending=[False, False, False], na_position="last")


def render_pullback_reclaim(ctx: dict | None = None) -> None:
    if ctx:
        _bind_runtime(ctx)
    st.markdown("## Pullback Reclaim Strategy")
    st.caption("Strong prior rally → controlled pullback → support hold → reclaim + volume confirmation. This is a 3–15 trading-day swing strategy, not an automatic dip-buy signal.")

    src = _source_frame()
    if src.empty:
        st.info("Run a market scan first. This strategy reuses the latest Long Setups scan data.")
        return

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        min_score = st.slider("Minimum pullback score", 0, 100, 45, 5, key="pullback_min_score")
    with c2:
        min_rally = st.slider("Minimum prior 20D rally %", 0, 30, 8, 1, key="pullback_min_rally")
    with c3:
        only_actionable = st.checkbox("Actionable only", value=False, key="pullback_actionable")
    with c4:
        require_volume = st.checkbox("Require volume confirmation", value=False, key="pullback_volume")

    out = _classify(src)
    out = out[(out["Pullback Rank Score"] >= min_score) & (out["Prior Rally %"] >= min_rally)]
    if only_actionable:
        out = out[out["Pullback Decision"].str.contains("BUY ABOVE|SMALL ENTRY", regex=True, na=False)]
    if require_volume:
        out = out[out["Volume Confirmation"].eq("YES")]

    if out.empty:
        st.warning("No pullback-reclaim candidates pass these settings. Lower the minimum score/rally threshold or wait for support/reclaim confirmation.")
        return

    out = out.reset_index(drop=True)
    out.insert(0, "Rank", np.arange(1, len(out) + 1))

    display_order = [
        "Rank", "Ticker", "Pullback Decision", "Pullback Checklist", "Why Not Confirmed", "Reclaim Trigger",
        "Pullback Stage", "Pullback Rank Score", "Price", "Today %", "Prior Rally %",
        "MA5", "MA10", "MA20", "MA5/10 Status",
        "Support Zone", "Invalidation", "Target 1 (2R)", "Target 2 (3R)", "RR Est",
        "Entry Quality", "MACD State", "Volume Confirmation", "Vol Ratio",
        "Sector Alignment", "Sector", "Distance MA5 %", "Distance MA10 %", "Distance MA20 %", "RSI", "ATR%", "Signals",
    ]
    cols = [c for c in display_order if c in out.columns]
    st.dataframe(out[cols], use_container_width=True, hide_index=True, height=620)

    st.info(
        "Decision rule: MA5 reclaim is the first rebound signal; MA10 reclaim and MA5 > MA10 confirm improving short-term structure. "
        "BUY ABOVE RECLAIM requires the trigger to hold with volume. SMALL ENTRY is early/higher-risk. "
        "WATCH SUPPORT is not a buy. Exit if Invalidation is broken."
    )
