"""Momentum Runner tab.

Finds early ignition stocks and already-running names from the latest scan
cache. This is intentionally separate from Best 7-10%, which stays focused on
clean swing entries before a move is extended.
"""

from __future__ import annotations

import re
from datetime import datetime

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


def _rr_num(df: pd.DataFrame, col: str, default: float = 0.0) -> pd.Series:
    """Parse risk:reward values like '1:2.5' as 2.5, not 1.0."""
    if col not in df.columns:
        return pd.Series([default] * len(df), index=df.index, dtype="float64")
    raw = df[col].astype(str).str.strip()
    ratio = raw.str.extract(r"1\s*[:/]\s*(-?\d+(?:\.\d+)?)")[0]
    fallback = (
        raw.str.replace("%", "", regex=False)
        .str.replace("+", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.replace("x", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.extract(r"(-?\d+(?:\.\d+)?)")[0]
    )
    return pd.to_numeric(ratio.fillna(fallback), errors="coerce").fillna(default)


def _txt(df: pd.DataFrame, col: str, default: str = "") -> pd.Series:
    if col not in df.columns:
        return pd.Series([default] * len(df), index=df.index)
    return df[col].astype(str).fillna(default)



def _is_monthly_options_expiry(now: datetime) -> bool:
    """Best-effort event guard: US monthly options expiry = third Friday."""
    if now.weekday() != 4:  # Friday
        return False
    first = now.replace(day=1)
    first_friday_offset = (4 - first.weekday()) % 7
    third_friday_day = 1 + first_friday_offset + 14
    return now.day == third_friday_day


def _market_event_label() -> str:
    """Calendar-aware guard without external APIs.

    This is intentionally conservative. It catches fixed/regular risk days from
    local time only. For RBI policy, Budget, CPI/FOMC, earnings dates etc., add a
    proper events CSV/API later and map tickers/markets to event dates.
    """
    market = str(st.session_state.get("market_selector", globals().get("market_selector", ""))).upper()
    now = datetime.now()
    if "INDIA" in market:
        # NSE weekly index/options expiry is usually Thursday. Budget/RBI days
        # must come from an explicit calendar feed; don't guess them here.
        if now.weekday() == 3:
            return "CAUTION - India weekly expiry day; smaller size / wait ORB"
        return "CLEAR - no built-in India fixed event detected"
    if "US" in market:
        if _is_monthly_options_expiry(now):
            return "CAUTION - US monthly options expiry; avoid late chase"
        return "CLEAR - no built-in US expiry event detected"
    if "HK" in market or "SGX" in market or "SINGAPORE" in market:
        return "CLEAR - no built-in local event detected"
    return "CLEAR - no event calendar loaded"


def _event_is_blocking(label: str) -> bool:
    return str(label).upper().startswith("BLOCK")


def _sector_tailwind_label(sector_text: str, signals_text: str = "") -> str:
    """Classify whether the stock belongs to a green/moving sector.

    The main scan prefixes sector names with 🟢 / 🔴 based on current sector ETF
    performance. Signals may also include SEC LEAD or RS>SPY when the stock is
    outperforming its sector/market. This helper converts that into a visible
    decision field for Momentum Runner.
    """
    sec = str(sector_text or "").upper()
    sig = str(signals_text or "").upper()
    if any(x in sec for x in ["🔴", "RED", "WEAK"]) and not any(x in sig for x in ["SEC LEAD", "RS>SPY"]):
        return "RED/WEAK - avoid unless exceptional"
    if any(x in sec for x in ["🟢", "GREEN", "STRONG"]) or any(x in sig for x in ["SEC LEAD", "RS>SPY", "REL STRENGTH"]):
        return "GREEN/LEADER - preferred"
    if "MIXED" in sec or not sec.strip():
        return "UNKNOWN/MIXED - needs stock-level confirmation"
    return "NEUTRAL - not a sector leader"

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
    rr = _rr_num(out, "RR Est", 0)
    rise = _num(out, "Rise Prob", 0)
    vol = _num(out, "Vol Ratio", 0)
    atr = _num(out, "ATR%", 0)
    quality = _num(out, "Quality Score", 0)
    seven = _num(out, "7-Star Score", 0)
    pre_score = _num(out, "Pre-Mover Score", 0)
    expl_score = _num(out, "Explosion Score", 0)
    op_score = _num(out, "Op Score", 0)
    price = _num(out, "Price", 0)
    sector_txt = _txt(out, "Sector").str.upper()
    sector_green = sector_txt.str.contains("🟢|GREEN|STRONG", regex=True, na=False)
    sector_red = sector_txt.str.contains("🔴|RED|WEAK", regex=True, na=False)
    sector_mixed = sector_txt.str.contains("MIXED|UNKNOWN", regex=True, na=False) | sector_txt.eq("")
    sector_leader_signal = signals.str.contains(r"SEC LEAD|RS>SPY|REL STRENGTH|SECTOR LEADER", regex=True, na=False)
    sector_tailwind_ok = sector_green | sector_leader_signal
    sector_not_bad = ~sector_red | sector_leader_signal | sector_mixed

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
    score += sector_tailwind_ok.astype(int) * 8
    score -= (sector_red & ~sector_leader_signal).astype(int) * 10
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
        & sector_not_bad
        & ~avoid_entry
        & ~trap
        & ~broken
    )

    # ── Firefly-style 5-layer gate for explosive intraday runners ─────────────
    # Layer 1: market/stock structure. We need a trending/ignition structure,
    # not a dead sideways range. Compression is allowed only if it is breaking.
    structure_trending = breakout | signals.str.contains(
        r"WKLY TREND|RS>SPY|HIGHER LOWS|52W|VOLUME BREAKOUT|VOL BREAKOUT|HOD|ORB|VWAP",
        regex=True, na=False,
    )
    structure_ranging = signals.str.contains(r"NR7|INSIDE|BB BULL SQ|VCP", regex=True, na=False) & ~structure_trending
    firefly_structure_ok = structure_trending & ~structure_ranging & ~trap & ~broken

    # Layer 2: volatility window. High volatility alone is not enough; we want
    # enough movement potential but not a blown-out, unstable spike.
    firefly_vol_ok = (atr.between(3.0, 10.5) | move7.between(7.0, 18.0)) & vol.between(1.2, 7.0)

    # Layer 3: event guard. This is best-effort without an external events API.
    # Earnings/news/catalyst names are allowed only with ORB/VWAP confirmation.
    event_label = _market_event_label()
    event_block = _event_is_blocking(event_label)
    event_risky_signal = signals.str.contains(r"EARNINGS|PRE-EARN|FDA|FOMC|CPI|BUDGET|RBI|EXPIRY", regex=True, na=False)
    firefly_event_ok = pd.Series(not event_block, index=idx)

    # Layer 4: entry precision = signal + volume + structure simultaneously.
    firefly_entry_ok = explosive_fuel & explosive_volume & firefly_structure_ok & ~avoid_entry

    # Layer 5: dynamic exit plan. The scanner cannot manage a live order, but it
    # now gives a rule that adapts to intraday momentum/VWAP instead of a static
    # stop only.
    firefly_dynamic_exit = np.where(
        explosive_setup,
        "Trail: below VWAP/9EMA after +3%; after +5% move stop to breakeven; exit if 2 candles close below VWAP",
        "Use normal stop; no dynamic runner mode"
    )

    # Extra sector-strength layer: prefer explosive stocks in sectors that are
    # green today or where the stock is leading its sector/market. This prevents
    # buying a lone weak-sector spike unless there is exceptional stock-level RS.
    firefly_sector_ok = sector_tailwind_ok | (sector_mixed & sector_leader_signal)

    firefly_pass = (
        explosive_setup
        & firefly_structure_ok
        & firefly_vol_ok
        & firefly_event_ok
        & firefly_entry_ok
        & firefly_sector_ok
    )

    firefly_layer_summary = []
    for i in idx:
        parts = []
        parts.append("L1 structure OK" if firefly_structure_ok.loc[i] else "L1 range/weak")
        parts.append("L2 vol window OK" if firefly_vol_ok.loc[i] else "L2 vol outside")
        parts.append("L3 event OK" if firefly_event_ok.loc[i] else "L3 event block")
        parts.append("L4 entry OK" if firefly_entry_ok.loc[i] else "L4 wait trigger")
        parts.append("Sector✅" if sector_tailwind_ok.loc[i] else ("Sector⚠" if sector_mixed.loc[i] else "Sector❌"))
        parts.append("L5 dynamic exit")
        if event_risky_signal.loc[i]:
            parts.append("event/catalyst name: size down")
        firefly_layer_summary.append(" | ".join(parts))

    tier = pd.Series("D - Not A Runner", index=idx)
    tier.loc[controlled_runner & quality_ok & liq_ok & vol_ok & ~avoid_entry] = "B - Controlled Runner"
    tier.loc[ignition_move & runner_quality & liq_ok & vol_ok & ~avoid_entry & ~trap & ~too_hot] = "A - Day-1 Ignition"
    tier.loc[explosive_setup] = "A+ Explosive 5-10% Today"
    tier.loc[firefly_pass] = "A++ Firefly 5-Layer Explosive"
    tier.loc[reset_watch & ~broken] = "C - Hot Runner / Wait Reset"
    tier.loc[trap | chase_flag] = "C - Hot Runner / Wait Reset"
    tier.loc[broken] = "Reject - Broken Move"

    invalid = price * 0.94
    invalid = invalid.where(~(tier.eq("A - Day-1 Ignition")), price * 0.965)
    invalid = invalid.where(~(tier.eq("A+ Explosive 5-10% Today")), price * 0.975)
    invalid = invalid.where(~(tier.eq("A++ Firefly 5-Layer Explosive")), price * 0.98)
    trigger = price * 1.006
    trigger = trigger.where(today <= 0, price * 1.003)
    trigger = trigger.where(~(tier.eq("A+ Explosive 5-10% Today")), price * 1.004)
    trigger = trigger.where(~(tier.eq("A++ Firefly 5-Layer Explosive")), price * 1.003)

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
        if sector_tailwind_ok.loc[i]: parts.append("green/leader sector")
        elif sector_red.loc[i]: parts.append("weak/red sector")
        if fuel.loc[i]: parts.append("fuel")
        if firefly_pass.loc[i]: parts.append("A++ Firefly 5-layer pass")
        elif explosive_setup.loc[i]: parts.append("A+ explosive 5-10% candidate")
        if explosive_volume.loc[i]: parts.append("volume fuel")
        if explosive_atr.loc[i]: parts.append("ATR can move")
        if too_hot.loc[i]: parts.append("too hot")
        if trap.loc[i]: parts.append("trap risk")
        if broken.loc[i]: parts.append("broken")
        why.append(" | ".join(parts[:8]) if parts else "no runner evidence")

    # Final buy decision: this is the column to use first.
    # It combines the Firefly/Explosive gates with entry quality, tradeability,
    # volume confirmation, risk:reward and trap/chase filters.
    tradeable_buy = _txt(out, "Tradeable Buy").str.upper().eq("YES")

    # Entry Quality is a timing filter, not a hard blocker for all explosive setups.
    # The earlier patch was too strict: it required Firefly + Tradeable Buy + Entry=A + RR + Vol.
    # In real pre-market/live momentum scans, Tradeable Buy or RR Est can be blank/NO even when
    # the runner setup is valid. This caused nearly every row to show WAIT.
    entry_bad = entry.str.contains(r"AVOID|SKIP|TRAP|CHASE|BROKEN", regex=True, na=False)
    entry_good = (
        entry.str.contains(r"✅|A\+|\bA\b|GOOD|IDEAL|CLEAN|BUY", regex=True, na=False)
        & ~entry_bad
        & ~entry.str.contains(r"WATCH|WAIT", regex=True, na=False)
    )
    entry_acceptable = (
        entry_good
        | (entry.str.contains(r"DISCOVERY|NEAR-MISS|WATCH|WAIT", regex=True, na=False) & ~entry_bad)
        | entry.eq("")
    )

    # RR Est is often not available or remains 0 for live explosive runners.
    # If the row is A+/A++ runner, the generated trigger/invalid/targets imply roughly 1:2+.
    rr_missing = (rr <= 0)
    rr_ok = (rr >= 1.8) | (rr_missing & tier.isin(["A++ Firefly 5-Layer Explosive", "A+ Explosive 5-10% Today"]))

    vol_confirm = explosive_volume | (vol >= 1.3) | (pm >= 3.0) | (today >= 3.0)
    clean_risk = ~trap & ~avoid_entry & ~broken & ~chase_flag
    sector_confirm = sector_tailwind_ok

    # Final decision levels:
    # READY = all major gates pass; buy only above trigger/VWAP/ORB.
    # BUY WATCH = explosive candidate, but needs entry confirmation or Firefly layer improvement.
    # WAIT = runner exists but not enough explosive/volume/entry alignment yet.
    ready_best = firefly_pass & sector_confirm & entry_good & rr_ok & vol_confirm & clean_risk
    ready_trigger = firefly_pass & entry_acceptable & rr_ok & vol_confirm & clean_risk & ~ready_best
    explosive_ready = explosive_setup & sector_not_bad & entry_good & rr_ok & vol_confirm & clean_risk & ~firefly_pass
    explosive_watch_setup = explosive_setup & clean_risk & ~(ready_best | ready_trigger | explosive_ready)
    normal_watch_setup = tier.isin(["A - Day-1 Ignition", "B - Controlled Runner"]) & clean_risk

    buy_decision = pd.Series("⚪ IGNORE - no edge", index=idx, dtype="object")
    buy_decision.loc[normal_watch_setup] = "⏳ WAIT - not explosive enough"
    buy_decision.loc[explosive_watch_setup] = "⚡ WATCH - needs Firefly/VWAP confirmation"
    buy_decision.loc[explosive_ready] = "🟢 BUY WATCH - explosive; confirm VWAP/ORB"
    buy_decision.loc[ready_trigger] = "✅ BUY ABOVE TRIGGER - confirm entry"
    buy_decision.loc[ready_best] = "✅ BUY ABOVE TRIGGER - best candidate"
    buy_decision.loc[trap | avoid_entry | broken] = "🚫 SKIP - trap/avoid/broken"
    buy_decision.loc[chase_flag & ~(trap | avoid_entry | broken)] = "🚫 SKIP - chase risk / wait reset"

    checklist = []
    for i in idx:
        checks = []
        checks.append("Firefly✅" if firefly_pass.loc[i] else "Firefly❌")
        checks.append("Entry✅" if entry_good.loc[i] else ("Entry⚠" if entry_acceptable.loc[i] else "Entry❌"))
        checks.append("Tradeable✅" if (tradeable_buy.loc[i] or explosive_setup.loc[i] or firefly_pass.loc[i]) else "Tradeable❌")
        checks.append("Sector✅" if sector_tailwind_ok.loc[i] else ("Sector⚠" if sector_mixed.loc[i] else "Sector❌"))
        checks.append("Vol✅" if vol_confirm.loc[i] else "Vol❌")
        checks.append("RR✅" if rr_ok.loc[i] else "RR❌")
        checks.append("Risk✅" if clean_risk.loc[i] else "Risk❌")
        checklist.append(" | ".join(checks))

    out["Buy Decision"] = buy_decision
    out["Buy Checklist"] = checklist
    out["Sector Tailwind"] = [
        _sector_tailwind_label(out.at[i, "Sector"] if "Sector" in out.columns else "", out.at[i, "Signals"] if "Signals" in out.columns else "")
        for i in idx
    ]
    out["Runner Score"] = score
    out["Runner Tier"] = tier
    out["Runner Why"] = why
    out["Firefly Pass"] = np.where(firefly_pass, "YES", "NO")
    out["Firefly Layers"] = firefly_layer_summary
    out["Event Guard"] = event_label
    out["Dynamic Exit"] = firefly_dynamic_exit
    out["Explosive Buy"] = np.where(
        tier.eq("A++ Firefly 5-Layer Explosive"),
        "YES - Firefly pass; buy only ORB/VWAP trigger",
        np.where(tier.eq("A+ Explosive 5-10% Today"), "YES - only above trigger / VWAP", "NO")
    )
    out["Runner Trigger"] = trigger.round(2).map(lambda x: f"${x:.2f}" if x > 0 else "-")
    out["Runner Invalid"] = invalid.round(2).map(lambda x: f"${x:.2f}" if x > 0 else "-")
    out["Target 1 +5%"] = explosive_target_1.round(2).map(lambda x: f"${x:.2f}" if x > 0 else "-")
    out["Target 2 +10%"] = explosive_target_2.round(2).map(lambda x: f"${x:.2f}" if x > 0 else "-")
    out["_tier_sort"] = tier.map({
        "A++ Firefly 5-Layer Explosive": 6,
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
        # Decision block: keep these together so the buy/no-buy call and exact trigger are visible.
        "Ticker", "Buy Decision", "Buy Checklist", "Runner Trigger",
        "Runner Tier", "Firefly Pass", "Explosive Buy", "Entry Quality", "Tradeable Buy",
        "Sector Tailwind", "Sector",
        "Runner Invalid", "Target 1 +5%", "Target 2 +10%",
        # Confirmation/risk block.
        "Runner Score", "Vol Ratio", "RR Est", "Trap Risk", "ATR%", "Rise Prob",
        "Today %", "PM Chg%", "PM Price", "5D %", "20D %", "7D Move Est", "Upside to Res",
        # Explanation block.
        "Runner Why", "Firefly Layers", "Event Guard", "Dynamic Exit",
        "Action", "7-Star Score", "Pre-Mover Score", "Explosion Score", "Price", "Signals",
    ]
    cols = [c for c in preferred if c in df.columns]
    st.dataframe(df[cols].reset_index(drop=True), width="stretch", hide_index=True, key=key)
    if "Ticker" in df.columns:
        st.code(", ".join(df["Ticker"].astype(str).head(80).tolist()))


def render_momentum_runner(ctx: dict) -> None:
    _bind_runtime(ctx)

    st.markdown("## Momentum Runner / Explosive 5-10%")
    st.caption("Use this tab for explosive same-day 5-10% movers. It separates A+ explosive candidates from normal swing picks and hot names that need a reset.")
    st.warning("Use Buy Decision first, then buy only when price breaks Runner Trigger with VWAP/opening-range confirmation. Do not buy blindly at open.")

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
    firefly_only = st.checkbox("Firefly 5-layer pass only", value=False, key="runner_firefly_only")

    ranked = _classify(src, min_score=min_score, show_chase=show_chase)
    if firefly_only and "Firefly Pass" in ranked.columns:
        ranked = ranked[ranked["Firefly Pass"].eq("YES")].copy()

    search = st.text_input("Filter ticker / signal", "", key="runner_search").strip().upper()
    if search:
        hay = (
            ranked.get("Ticker", pd.Series("", index=ranked.index)).astype(str).str.upper()
            + " " + ranked.get("Signals", pd.Series("", index=ranked.index)).astype(str).str.upper()
            + " " + ranked.get("Runner Why", pd.Series("", index=ranked.index)).astype(str).str.upper()
        )
        ranked = ranked[hay.str.contains(re.escape(search), na=False)].copy()

    firefly = ranked[ranked["Runner Tier"].eq("A++ Firefly 5-Layer Explosive")].head(show_n)
    explosive = ranked[ranked["Runner Tier"].eq("A+ Explosive 5-10% Today")].head(show_n)
    ignition = ranked[ranked["Runner Tier"].eq("A - Day-1 Ignition")].head(show_n)
    controlled = ranked[ranked["Runner Tier"].eq("B - Controlled Runner")].head(show_n)
    reset = ranked[ranked["Runner Tier"].eq("C - Hot Runner / Wait Reset")].head(show_n)

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("A++ Firefly", len(firefly))
    m2.metric("Ignition", len(ignition))
    m3.metric("Controlled", len(controlled))
    m4.metric("Wait Reset", len(reset))
    m5.metric("Rows", len(ranked))

    st.markdown("### A++ Firefly 5-Layer Explosive")
    st.caption("Strictest bucket: market/stock structure + volatility window + event guard + precise entry + dynamic exit plan. This is the closest match to the Firefly framework.")
    _show(firefly, "runner_firefly")

    with st.expander(f"A+ Explosive 5-10% Today ({len(explosive)})", expanded=True):
        st.caption("Aggressive explosive candidates that may not pass every Firefly layer. Entry should be above trigger/VWAP, not a blind buy.")
        _show(explosive, "runner_explosive")

    with st.expander(f"A - Day-1 Ignition ({len(ignition)})", expanded=True):
        _show(ignition, "runner_ignition")

    with st.expander(f"B - Controlled Runner ({len(controlled)})", expanded=True):
        _show(controlled, "runner_controlled")

    with st.expander(f"C - Hot Runner / Wait Reset ({len(reset)})", expanded=False):
        _show(reset, "runner_reset")

    with st.expander("Exact rule for A+ Explosive 5-10% Today"):
        st.markdown("""
A stock enters the **A++ Firefly** bucket only when all 5 layers pass:

1. **Market/stock structure:** trending/ignition structure, not dead range
2. **Volatility window:** ATR/move potential is high enough but not blown out
3. **Event guard:** fixed high-risk event days are flagged; no event block
4. **Entry precision:** signal + volume + structure must align
5. **Dynamic exit:** VWAP/9EMA trailing logic is shown instead of static stop only

A stock enters the A+ explosive bucket when it has:

- PM or current day move between about **+2% and +9.5%**
- volume fuel, usually **Vol Ratio 1.5x-7x** or strong PM/current move
- enough movement potential: **ATR% 3-12** or estimated 7D move >= 7%
- breakout/catalyst/fuel signal such as news, earnings, gapper, 52W, VWAP, ORB, volume breakout
- price >= $2 and no trap/broken/chase flags

Use **Buy Decision** as the final decision column:

- ✅ **BUY ABOVE TRIGGER** = best candidate, but still requires ORB/VWAP trigger confirmation
- 🟡 **WAIT** = good setup but entry/RR/volume is not perfect yet
- ⚡ **WATCH** = explosive candidate but Firefly confirmation is missing
- 🚫 **SKIP** = trap/chase/broken/avoid condition

This is intentionally aggressive. Use it for intraday momentum, not long-term investing.
        """)
