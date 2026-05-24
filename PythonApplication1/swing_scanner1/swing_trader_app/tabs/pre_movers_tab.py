"""Pre-Movers tab.

Looks for stocks that resemble tomorrow's Movers candidates: compressed,
accumulating, volatile enough, near a trigger, and not already up big today.
"""

import re

import pandas as pd
import streamlit as st


def _bind_runtime(ctx: dict) -> None:
    globals().update(ctx)


def _num(df: pd.DataFrame, col: str, default: float = 0.0) -> pd.Series:
    if col not in df.columns:
        return pd.Series([default] * len(df), index=df.index, dtype="float64")
    return pd.to_numeric(
        df[col].astype(str)
        .str.replace("%", "", regex=False)
        .str.replace("+", "", regex=False)
        .str.replace("x", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.extract(r"(-?\d+(?:\.\d+)?)")[0],
        errors="coerce",
    ).fillna(default)


def _txt(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series([""] * len(df), index=df.index)
    return df[col].astype(str).fillna("")


def _source_frame() -> pd.DataFrame:
    sources = []
    for key in ("df_long_master", "df_long", "df_swing_picks"):
        sources.append((f"session:{key}", st.session_state.get(key, pd.DataFrame())))
    for key in ("df_long_master", "df_long", "df_swing_picks"):
        sources.append((f"runtime:{key}", globals().get(key, pd.DataFrame())))

    for label, df in sources:
        if isinstance(df, pd.DataFrame) and not df.empty:
            out = df.copy()
            if "Ticker" not in out.columns:
                out.insert(0, "Ticker", out.index.astype(str))
            st.session_state["pmv_source_label"] = label
            st.session_state["pmv_source_rows"] = len(out)
            return out
    st.session_state["pmv_source_label"] = "none"
    st.session_state["pmv_source_rows"] = 0
    return pd.DataFrame()


def _fallback_rank(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    idx = out.index
    joined = (
        _txt(out, "Signals") + " " +
        _txt(out, "Setup Type") + " " +
        _txt(out, "Action") + " " +
        _txt(out, "Pre-Mover Why")
    ).str.upper()

    today = _num(out, "Today %", 0)
    move5_recent = _num(out, "5D %", 0)
    move20_recent = _num(out, "20D %", 0)
    recent_run_extended = (move5_recent >= 25.0) | (move20_recent >= 50.0)
    atr = _num(out, "ATR%", 0)
    move7 = _num(out, "7D Move Est", 0)
    vol = _num(out, "Vol Ratio", 0)
    op = _num(out, "Op Score", 0)
    pss = _num(out, "PSS Score", 0)
    rise = _num(out, "Rise Prob", 0)

    compression = joined.str.contains(
        r"NR7|INSIDE|BB BULL SQ|SQUEEZE|TIGHT FLAG|CUP|HANDLE|VDU|FLATBASE|COIL|VCP",
        regex=True,
        na=False,
    )
    accumulation = joined.str.contains(
        r"ACCUM|OBV|POCKET|VOL-DIP|ABSORPTION|VWAP|OPERATOR",
        regex=True,
        na=False,
    ) | (op >= 2)
    near_trigger = joined.str.contains(
        r"52W|BREAKOUT|HIGHER LOWS|SUPPORT|MA20|MA60|VWAP|FAILED BRKDN",
        regex=True,
        na=False,
    )
    explosive_trigger = joined.str.contains(
        r"52W|BREAKOUT|HIGHER LOWS|FAILED BRKDN|CUP|HANDLE|TIGHT FLAG",
        regex=True,
        na=False,
    )
    support_trigger = joined.str.contains(
        r"SUPPORT|MA20|MA60|VWAP",
        regex=True,
        na=False,
    )
    relative = joined.str.contains(r"RS>|RS MOM|SEC LEAD|WKLY TREND", regex=True, na=False)
    catalyst = joined.str.contains(r"PRE-EARN|PEAD|EARNINGS|CATALYST|ABSORPTION", regex=True, na=False)
    quiet = today.between(-1.5, 2.5)
    not_moved = today <= 3.5
    vol_ok = (atr >= 2.8) | (move7 >= 6.0)
    liquidity_ok = (vol >= 0.35) | (_num(out, "Price", 0) >= 1.0)
    range_shift = (
        joined.str.contains(r"RANGE SHIFT|BREAKOUT|HIGHER LOWS|RECLAIM|SUPPORT|MA20|MA60|VWAP|FAILED BRKDN", regex=True, na=False)
        & today.between(-3.5, 3.5)
        & ~recent_run_extended
    )
    divergence = (
        accumulation
        & (relative | joined.str.contains(r"OBV|OPERATOR|ABSORPTION|RS MOM", regex=True, na=False))
        & (move5_recent <= 12.0)
        & (today <= 3.5)
        & ~recent_run_extended
    )
    one_red = (
        today.between(-3.5, -0.15)
        & support_trigger
        & ((move5_recent >= 1.5) | relative | accumulation)
        & ((vol <= 1.6) | accumulation)
        & ~recent_run_extended
    )
    rr_ok = (
        (_num(out, "RR Est", 0) >= 1.5)
        | (_num(out, "Upside to Res", 0) >= 6.0)
        | near_trigger
    ) & ~recent_run_extended & (today <= 5.0)

    seven_star = pd.Series([0] * len(out), index=idx, dtype="int64")
    for _flag in (liquidity_ok, vol_ok, compression, range_shift, divergence, one_red, rr_ok):
        seven_star += _flag.astype(int)
    seven_star = seven_star.mask(recent_run_extended, seven_star.clip(upper=4))
    seven_star = seven_star.mask((today <= -5.0) & (~joined.str.contains("FAILED BRKDN", regex=False, na=False)), seven_star.clip(upper=3))

    seven_tier = pd.Series("LOW", index=idx)
    seven_tier.loc[seven_star >= 7] = "7 - PRIME"
    seven_tier.loc[seven_star == 6] = "6 - READY"
    seven_tier.loc[seven_star == 5] = "5 - WATCH"
    seven_tier.loc[seven_star == 4] = "4 - EARLY"
    seven_tier.loc[recent_run_extended] = "MOVED ALREADY"

    seven_why = []
    for i in idx:
        parts = []
        if liquidity_ok.loc[i]: parts.append("liquid")
        if vol_ok.loc[i]: parts.append("move potential")
        if compression.loc[i]: parts.append("compression")
        if range_shift.loc[i]: parts.append("range shift")
        if divergence.loc[i]: parts.append("divergence/accumulation")
        if one_red.loc[i]: parts.append("one red hold")
        if rr_ok.loc[i]: parts.append("risk/reward")
        if recent_run_extended.loc[i]: parts.append(f"already ran 5D {move5_recent.loc[i]:.1f}% / 20D {move20_recent.loc[i]:.1f}%")
        seven_why.append(" | ".join(parts[:7]) if parts else "not enough 7-star evidence")

    out["7-Star Score"] = seven_star.astype(int)
    out["7-Star Tier"] = seven_tier
    out["7-Star Why"] = seven_why

    score = pd.Series([0] * len(out), index=idx, dtype="float64")
    score += compression.astype(int) * 25
    score += accumulation.astype(int) * 18
    score += near_trigger.astype(int) * 13
    score += relative.astype(int) * 10
    score += catalyst.astype(int) * 8
    score += quiet.astype(int) * 10
    score += vol_ok.astype(int) * 12
    score += (vol.between(0.45, 1.40)).astype(int) * 5
    score += (vol >= 1.40).astype(int) * 6
    score += (pss >= 2).astype(int) * 8
    score += (rise >= 60).astype(int) * 4
    score -= (today > 3.5).astype(int) * 18
    score -= (today < -3.0).astype(int) * 8
    score -= (~vol_ok).astype(int) * 14
    score = score.clip(0, 100).round().astype(int)
    score = score.mask(~near_trigger, score.clip(upper=58))
    score = score.mask(~compression, score.clip(upper=52))
    score = score.mask(~accumulation, score.clip(upper=56))
    score = score.mask((vol < 1.0) & (~catalyst), score.clip(upper=62))
    score = score.mask((today < -1.5) & (~joined.str.contains("FAILED BRKDN", regex=False, na=False)), score.clip(upper=60))
    score = score.mask(recent_run_extended, score.clip(upper=45))
    score = score.mask((today <= -5.0) & (~joined.str.contains("FAILED BRKDN", regex=False, na=False)), score.clip(upper=35))

    tier = pd.Series("SLOW / NOT READY", index=idx)
    tier.loc[(score >= 70) & compression & accumulation & near_trigger & vol_ok & not_moved] = "A - PRE-MOVER READY"
    tier.loc[(score >= 55) & compression & vol_ok & not_moved & ~tier.eq("A - PRE-MOVER READY")] = "B - COIL WATCH"
    tier.loc[(score >= 40) & not_moved & tier.eq("SLOW / NOT READY")] = "C - EARLY WATCH"
    tier.loc[recent_run_extended] = "MOVED ALREADY"
    tier.loc[today > 3.5] = "MOVED ALREADY"

    why = []
    for i in idx:
        parts = []
        if compression.loc[i]: parts.append("compression")
        if accumulation.loc[i]: parts.append("accumulation")
        if near_trigger.loc[i]: parts.append("near trigger")
        if relative.loc[i]: parts.append("relative strength")
        if catalyst.loc[i]: parts.append("catalyst")
        if quiet.loc[i]: parts.append("quiet before move")
        if not vol_ok.loc[i]: parts.append("low ATR/move potential")
        if recent_run_extended.loc[i]: parts.append(f"already ran 5D {move5_recent.loc[i]:.1f}% / 20D {move20_recent.loc[i]:.1f}%")
        if today.loc[i] > 3.5: parts.append("already moved today")
        why.append(" | ".join(parts[:6]) if parts else "no pre-mover evidence")

    out["Pre-Mover Score"] = score
    out["Pre-Mover Tier"] = tier
    out["Pre-Mover Why"] = why

    short_pct = _num(out, "Short %", 0)
    float_m = _num(out, "Float", 0)
    price = _num(out, "Price", 0)
    explosive_vol_ok = (atr >= 4.0) | (move7 >= 8.0)
    squeeze_fuel = short_pct >= 10.0
    small_float = (float_m > 0) & (float_m <= 120)
    mid_float = (float_m > 0) & (float_m <= 300)
    options_or_catalyst = joined.str.contains(
        r"CALL FLOW|CALL SKEW|P/C|IV CHEAP|PRE-EARN|PEAD|EARNINGS|CATALYST|SQZPROXY|ABSORPTION",
        regex=True,
        na=False,
    )
    style_fuel = squeeze_fuel | mid_float | options_or_catalyst

    explosion = pd.Series([0] * len(out), index=idx, dtype="float64")
    explosion += (atr >= 7.0).astype(int) * 24
    explosion += ((atr >= 5.0) & (atr < 7.0)).astype(int) * 18
    explosion += ((atr >= 4.0) & (atr < 5.0)).astype(int) * 12
    explosion -= (atr < 4.0).astype(int) * 18
    explosion += (move7 >= 12.0).astype(int) * 12
    explosion += ((move7 >= 8.0) & (move7 < 12.0)).astype(int) * 8
    explosion += (short_pct >= 18.0).astype(int) * 16
    explosion += ((short_pct >= 10.0) & (short_pct < 18.0)).astype(int) * 10
    explosion += ((short_pct >= 6.0) & (short_pct < 10.0)).astype(int) * 5
    explosion += small_float.astype(int) * 12
    explosion += ((~small_float) & mid_float).astype(int) * 6
    explosion += compression.astype(int) * 10
    explosion += accumulation.astype(int) * 10
    explosion += explosive_trigger.astype(int) * 8
    explosion += relative.astype(int) * 8
    explosion += options_or_catalyst.astype(int) * 12
    explosion += ((price > 0) & (price <= 25) & (atr >= 4.0)).astype(int) * 4
    explosion += quiet.astype(int) * 8
    explosion -= (today > 3.5).astype(int) * 18
    explosion -= (today > 8.0).astype(int) * 10
    explosion = explosion.clip(0, 100).round().astype(int)
    no_fuel_cap = pd.Series([58] * len(out), index=idx, dtype="float64")
    no_fuel_cap = no_fuel_cap.mask(~explosive_trigger, no_fuel_cap - 8)
    no_fuel_cap = no_fuel_cap.mask(vol < 1.0, no_fuel_cap - 8)
    no_fuel_cap = no_fuel_cap.mask((price > 100) & (~squeeze_fuel), no_fuel_cap - 6)
    no_fuel_cap = no_fuel_cap.mask(~compression, no_fuel_cap - 6)
    no_fuel_cap = no_fuel_cap.clip(lower=25)
    explosion = explosion.mask(~style_fuel, pd.concat([explosion, no_fuel_cap], axis=1).min(axis=1))
    trigger_cap = pd.Series([60] * len(out), index=idx, dtype="float64").mask(vol < 1.0, 52)
    explosion = explosion.mask((~explosive_trigger) & (~options_or_catalyst) & (~(squeeze_fuel & support_trigger)), pd.concat([explosion, trigger_cap], axis=1).min(axis=1))
    explosion = explosion.mask((vol < 1.0) & (~options_or_catalyst), explosion.clip(upper=54))
    explosion = explosion.mask((float_m >= 1000) & (~squeeze_fuel) & (~options_or_catalyst), explosion.clip(upper=55))
    explosion = explosion.mask(recent_run_extended, explosion.clip(upper=42))
    explosion = explosion.mask((today <= -5.0) & (~joined.str.contains("FAILED BRKDN", regex=False, na=False)), explosion.clip(upper=38))

    explosion_tier = pd.Series("LOW EXPLOSION", index=idx)
    explosion_tier.loc[
        (explosion >= 75) & explosive_vol_ok & not_moved & (compression | explosive_trigger | (squeeze_fuel & support_trigger)) &
        accumulation & style_fuel & (explosive_trigger | options_or_catalyst)
    ] = "X - STYLE EXPLOSIVE"
    explosion_tier.loc[
        (explosion >= 55) & explosive_vol_ok & not_moved &
        (compression | explosive_trigger | accumulation | (squeeze_fuel & support_trigger)) &
        style_fuel &
        ~explosion_tier.eq("X - STYLE EXPLOSIVE")
    ] = "A - EXPLOSIVE WATCH"
    explosion_tier.loc[
        (explosion >= 45) & not_moved & explosion_tier.eq("LOW EXPLOSION")
    ] = "B - SPECULATIVE WATCH"
    explosion_tier.loc[recent_run_extended] = "MOVED ALREADY"
    explosion_tier.loc[today > 3.5] = "MOVED ALREADY"

    explosion_why = []
    for i in idx:
        parts = []
        if explosive_vol_ok.loc[i]: parts.append(f"ATR {atr.loc[i]:.1f}% / 7D {move7.loc[i]:.1f}%")
        else: parts.append("not enough ATR")
        if squeeze_fuel.loc[i]: parts.append(f"short {short_pct.loc[i]:.1f}%")
        if small_float.loc[i]: parts.append("small float")
        elif mid_float.loc[i]: parts.append("mid float")
        if explosive_trigger.loc[i]: parts.append("near breakout trigger")
        if compression.loc[i]: parts.append("coil/compression")
        if accumulation.loc[i]: parts.append("accumulation")
        if options_or_catalyst.loc[i]: parts.append("catalyst/options/fuel")
        if not style_fuel.loc[i]: parts.append("no squeeze/float/catalyst fuel")
        if recent_run_extended.loc[i]: parts.append(f"already ran 5D {move5_recent.loc[i]:.1f}% / 20D {move20_recent.loc[i]:.1f}%")
        if today.loc[i] > 3.5: parts.append("already moved today")
        explosion_why.append(" | ".join(parts[:7]))

    out["Explosion Score"] = explosion
    out["Explosion Tier"] = explosion_tier
    out["Explosion Why"] = explosion_why
    return out


def _rank(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if (
        "Pre-Mover Score" not in out.columns or
        "Pre-Mover Tier" not in out.columns or
        "Explosion Score" not in out.columns or
        "7-Star Score" not in out.columns or
        "7-Star Tier" not in out.columns
    ):
        out = _fallback_rank(out)
    else:
        out["Pre-Mover Score"] = _num(out, "Pre-Mover Score", 0).round().astype(int)
        out["Explosion Score"] = _num(out, "Explosion Score", 0).round().astype(int)
        out["7-Star Score"] = _num(out, "7-Star Score", 0).clip(0, 7).round().astype(int)
        if "7-Star Why" not in out.columns:
            out["7-Star Why"] = "-"
        if "Pre-Mover Why" not in out.columns:
            out["Pre-Mover Why"] = "–"
        if "Explosion Tier" not in out.columns:
            out["Explosion Tier"] = "LOW EXPLOSION"
        if "Explosion Why" not in out.columns:
            out["Explosion Why"] = "–"
    order = {
        "A - PRE-MOVER READY": 4,
        "B - COIL WATCH": 3,
        "C - EARLY WATCH": 2,
        "MOVED ALREADY": 1,
        "SLOW / NOT READY": 0,
    }
    out["_tier_sort"] = out["Pre-Mover Tier"].map(order).fillna(0)
    out["_best_candidate_score"] = pd.concat([
        out["Pre-Mover Score"].astype(float),
        out["Explosion Score"].astype(float),
        out["7-Star Score"].astype(float) * 14.0,
    ], axis=1).max(axis=1)
    return out.sort_values(["7-Star Score", "_tier_sort", "Explosion Score", "Pre-Mover Score"], ascending=[False, False, False, False], kind="stable")


def _show(df: pd.DataFrame, key: str) -> None:
    if df.empty:
        st.info("No rows in this tier.")
        return
    preferred = [
        "Ticker", "7-Star Score", "7-Star Tier", "7-Star Why",
        "Explosion Score", "Explosion Tier", "Explosion Why",
        "Pre-Mover Score", "Pre-Mover Tier", "Pre-Mover Why",
        "Today %", "5D %", "20D %", "Vol Ratio", "ATR%", "7D Move Est", "Setup Type", "Action",
        "Rise Prob", "Quality Score", "Next-Day Score", "PSS Score", "PSS Label",
        "Operator", "Op Score", "VWAP", "Trap Risk", "Short %", "Float", "Upside to Res", "RR Est",
        "Price", "Signals",
    ]
    cols = [c for c in preferred if c in df.columns]
    st.dataframe(df[cols].reset_index(drop=True), use_container_width=True, hide_index=True, key=key)
    st.code(", ".join(df["Ticker"].astype(str).head(80).tolist()) if "Ticker" in df.columns else "")


def render_pre_movers(ctx: dict) -> None:
    _bind_runtime(ctx)

    st.markdown("## Pre-Movers")
    st.caption("Finds stocks that may become Movers soon, including style explosive candidates before the big daily move.")

    src = _source_frame()
    if src.empty:
        st.info("Run a market scan first. Pre-Movers reuses the latest Long Setups master scan.")
        with st.expander("Pre-Movers source diagnostics", expanded=True):
            checks = []
            for key in ("df_long_master", "df_long", "df_swing_picks"):
                ss_df = st.session_state.get(key, pd.DataFrame())
                rt_df = globals().get(key, pd.DataFrame())
                checks.append({
                    "Source": f"session:{key}",
                    "Rows": len(ss_df) if isinstance(ss_df, pd.DataFrame) else 0,
                    "Columns": ", ".join(list(ss_df.columns)[:8]) if isinstance(ss_df, pd.DataFrame) and not ss_df.empty else "–",
                })
                checks.append({
                    "Source": f"runtime:{key}",
                    "Rows": len(rt_df) if isinstance(rt_df, pd.DataFrame) else 0,
                    "Columns": ", ".join(list(rt_df.columns)[:8]) if isinstance(rt_df, pd.DataFrame) and not rt_df.empty else "–",
                })
            st.dataframe(pd.DataFrame(checks), use_container_width=True, hide_index=True)
        return

    ranked = _rank(src)
    st.caption(
        f"Source: {st.session_state.get('pmv_source_label', 'unknown')} · "
        f"{st.session_state.get('pmv_source_rows', len(src))} source rows"
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        min_score = st.slider("Minimum candidate score", 0, 100, 20, step=5, key="pmv_min_score")
    with c2:
        max_today = st.slider("Max today move %", 0.5, 8.0, 3.5, step=0.5, key="pmv_max_today")
    with c3:
        only_ready = st.checkbox("Only A/B candidates", value=False, key="pmv_only_ready")

    today = _num(ranked, "Today %", 0)
    explosion_score = _num(ranked, "Explosion Score", 0)
    candidate_score = pd.concat([
        ranked["7-Star Score"].astype(float) * 14.0,
        ranked["Pre-Mover Score"].astype(float),
        explosion_score.astype(float),
    ], axis=1).max(axis=1)
    best_available = ranked.sort_values("_best_candidate_score", ascending=False, kind="stable").head(30).copy()
    ranked = ranked[(candidate_score >= min_score) & (today <= max_today)].copy()
    if only_ready:
        ranked = ranked[
            ranked["Pre-Mover Tier"].isin(["A - PRE-MOVER READY", "B - COIL WATCH"]) |
            ranked["Explosion Tier"].isin(["X - STYLE EXPLOSIVE", "A - EXPLOSIVE WATCH"]) |
            (ranked["7-Star Score"] >= 5)
        ].copy()

    search = st.text_input("Filter ticker / setup", "", key="pmv_search").strip().upper()
    if search:
        hay = (
            _txt(ranked, "Ticker") + " " +
            _txt(ranked, "Signals") + " " +
            _txt(ranked, "Setup Type") + " " +
            _txt(ranked, "Pre-Mover Why")
        ).str.upper()
        ranked = ranked[hay.str.contains(re.escape(search), na=False)].copy()

    ranked = ranked.assign(_expl_sort=_num(ranked, "Explosion Score", 0))
    _expl_why = ranked.get("Explosion Why", pd.Series([""] * len(ranked), index=ranked.index)).astype(str).str.upper()
    style_pool = ranked[
        (_num(ranked, "Explosion Score", 0) >= min_score) &
        (_num(ranked, "Explosion Score", 0) > 0)
    ].sort_values("Explosion Score", ascending=False, kind="stable")
    explosive = style_pool.head(30).copy()
    speculative = ranked[ranked["Explosion Tier"].eq("B - SPECULATIVE WATCH")]
    tier_a = ranked[ranked["Pre-Mover Tier"].eq("A - PRE-MOVER READY")]
    tier_b = ranked[ranked["Pre-Mover Tier"].eq("B - COIL WATCH")]
    tier_c = ranked[ranked["Pre-Mover Tier"].eq("C - EARLY WATCH")]
    slow = ranked[ranked["Pre-Mover Tier"].isin(["SLOW / NOT READY", "MOVED ALREADY"])]
    visible_count = len(explosive) + len(speculative) + len(tier_a) + len(tier_b) + len(tier_c)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Style Watch", len(explosive))
    m2.metric("Ready", len(tier_a))
    m3.metric("Coil Watch", len(tier_b))
    m4.metric("Early/slow", len(tier_c) + len(slow))

    st.markdown("### Best Available Candidates")
    st.caption("Always shown from the latest scan, even when strict Style Explosive / Pre-Mover filters find no perfect setup.")
    _show(best_available, "pmv_best_available_top")

    st.markdown("### Style Explosive Watch")
    st.caption("Best style-explosive candidates ranked by Explosion Score. Use Explosion Tier/Why to separate true X/A setups from speculative watch names.")
    _show(explosive, "pmv_explosive")

    with st.expander(f"Speculative explosive watch detail ({len(speculative)})", expanded=False):
        _show(speculative, "pmv_speculative")

    st.markdown("### A - Pre-Mover Ready")
    st.caption("Best match: compression, accumulation, near trigger, enough ATR, and not already moved today.")
    _show(tier_a, "pmv_a")

    with st.expander(f"B - Coil Watch ({len(tier_b)})", expanded=True):
        _show(tier_b, "pmv_b")

    with st.expander(f"C - Early Watch ({len(tier_c)})", expanded=True):
        _show(tier_c, "pmv_c")

    with st.expander(f"Slow / moved already ({len(slow)})", expanded=False):
        _show(slow, "pmv_slow")

    if visible_count == 0:
        st.warning(
            "No strict Pre-Mover rows matched the current filters. "
            "Use Best Available Candidates above, or lower filters further."
        )
