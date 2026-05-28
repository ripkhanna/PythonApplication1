"""Big Money Radar tab.

Ranks the latest scanner rows for institutional-style accumulation plus
short-term move potential. This is a proxy view, not a live 13F feed.
"""

from __future__ import annotations

from pathlib import Path
import re

import numpy as np
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
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.replace("x", "", regex=False)
        .str.extract(r"(-?\d+(?:\.\d+)?)")[0],
        errors="coerce",
    ).fillna(default)


def _txt(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series([""] * len(df), index=df.index)
    return df[col].astype(str).fillna("")


def _market_token() -> str:
    raw = str(st.session_state.get("market_selector") or globals().get("market_sel") or "US").upper()
    if "HK" in raw or "HONG" in raw:
        return "hk"
    if "INDIA" in raw or "NSE" in raw or ".NS" in raw:
        return "india"
    if "SGX" in raw or "SINGAPORE" in raw or ".SI" in raw:
        return "sgx"
    return "us"


def _source_frame() -> pd.DataFrame:
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
            st.session_state["big_money_source_label"] = label
            st.session_state["big_money_source_rows"] = len(out)
            return out

    cache_dir = Path(__file__).resolve().parents[1] / "scanner_cache"
    token = _market_token()
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
            out = pd.read_csv(path)
            if "Ticker" not in out.columns:
                out.insert(0, "Ticker", out.index.astype(str))
            st.session_state["big_money_source_label"] = f"cache:{name}"
            st.session_state["big_money_source_rows"] = len(out)
            return out
        except Exception:
            continue

    st.session_state["big_money_source_label"] = "none"
    st.session_state["big_money_source_rows"] = 0
    return pd.DataFrame()


def _clip(series: pd.Series, low: float = 0.0, high: float = 100.0) -> pd.Series:
    return series.astype(float).clip(lower=low, upper=high)


def _rank_big_money(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        return out
    if "Ticker" not in out.columns:
        out.insert(0, "Ticker", out.index.astype(str))
    out["Ticker"] = out["Ticker"].astype(str).str.upper().str.strip()
    out = out[out["Ticker"].ne("")].drop_duplicates("Ticker").reset_index(drop=True)

    joined = (
        _txt(out, "Signals") + " " +
        _txt(out, "Setup Type") + " " +
        _txt(out, "Action") + " " +
        _txt(out, "Entry Quality") + " " +
        _txt(out, "Pre-Mover Why") + " " +
        _txt(out, "7-Star Why") + " " +
        _txt(out, "Explosion Why")
    ).str.upper()

    op = _num(out, "Op Score", 0)
    vol = _num(out, "Vol Ratio", 0)
    pre = _num(out, "Pre-Mover Score", 0)
    seven = _num(out, "7-Star Score", 0)
    explosion = _num(out, "Explosion Score", 0)
    quality = _num(out, "Quality Score", 0)
    next_day = _num(out, "Next-Day Score", 0)
    rise_prob = _num(out, "Rise Prob", 0)
    today = _num(out, "Today %", 0)
    move5 = _num(out, "5D %", 0)
    move20 = _num(out, "20D %", 0)
    atr = _num(out, "ATR%", 0)
    rsi = _num(out, "RSI", 0)
    if "RSI" not in out.columns and "RSI Now" in out.columns:
        rsi = _num(out, "RSI Now", 0)
    vwap = _txt(out, "VWAP").str.upper()
    trap = (_txt(out, "Trap Risk") + " " + _txt(out, "Operator")).str.upper()
    risk_text = (trap + " " + _txt(out, "Action") + " " + _txt(out, "Entry Quality") + " " + joined).str.upper()

    above_vwap = vwap.str.contains("ABOVE", na=False)
    below_vwap = vwap.str.contains("BELOW", na=False)
    strong_operator = _txt(out, "Operator").str.upper().str.contains("ACCUM|STRONG", regex=True, na=False)
    accumulation_words = joined.str.contains(
        r"ACCUM|OBV|ABSORPTION|POCKET|VOL-DIP|INSTIT|OPERATOR|SUPPORT HOLD",
        regex=True,
        na=False,
    )
    volume_confirm = joined.str.contains(r"VOL SURGE|VOLUME|POCKET PIVOT|BREAKOUT", regex=True, na=False)
    relative_strength = joined.str.contains(r"RS>|RS MOM|WKLY TREND|SEC LEAD|HIGHER LOWS", regex=True, na=False)
    compression = joined.str.contains(r"BB BULL SQ|SQUEEZE|NR7|INSIDE|COIL|VCP|CUP|HANDLE|TIGHT", regex=True, na=False)
    catalyst = joined.str.contains(r"EARN|PEAD|CATALYST|NEWS|CONTRACT|ORDER|CALL FLOW|SQUEEZE", regex=True, na=False)
    bad_risk = risk_text.str.contains(
        r"DISTRIB|FALSE BO|BULL TRAP|GAP CHASE|AVOID|SKIP|CHASING|FAILED BRKDN",
        regex=True,
        na=False,
    )
    already_moved = (today >= 8) | (move5 >= 25) | (move20 >= 55) | _txt(out, "Pre-Mover Tier").str.upper().str.contains("MOVED ALREADY", na=False)

    sponsor_score = (
        _clip(op, 0, 6) * 4.0 +
        above_vwap.astype(int) * 12.0 +
        strong_operator.astype(int) * 12.0 +
        accumulation_words.astype(int) * 10.0 +
        _clip(vol, 0, 3) * 5.0 +
        volume_confirm.astype(int) * 8.0 +
        relative_strength.astype(int) * 7.0 +
        compression.astype(int) * 5.0
    )

    move_score = (
        _clip(pre, 0, 100) * 0.22 +
        _clip(explosion, 0, 70) * 0.18 +
        _clip(seven, 0, 8) * 2.0 +
        _clip(quality, -5, 18).clip(lower=0) * 1.3 +
        _clip(next_day, -15, 20).clip(lower=0) * 0.9 +
        _clip(rise_prob - 55, 0, 45) * 0.18 +
        _clip(atr, 0, 9) * 1.2 +
        catalyst.astype(int) * 6.0
    )

    setup_bonus = pd.Series(0.0, index=out.index)
    setup_bonus += today.between(-2.5, 3.5).astype(int) * 7.0
    setup_bonus += move5.between(-4, 15).astype(int) * 5.0
    setup_bonus += move20.between(-8, 35).astype(int) * 4.0
    setup_bonus += rsi.between(45, 72).astype(int) * 5.0

    penalty = pd.Series(0.0, index=out.index)
    penalty += below_vwap.astype(int) * 8.0
    penalty += bad_risk.astype(int) * 14.0
    penalty += already_moved.astype(int) * 18.0
    penalty += (rsi >= 78).astype(int) * 8.0
    penalty += (vol < 0.55).astype(int) * 6.0

    score = (sponsor_score * 0.52 + move_score * 0.38 + setup_bonus - penalty).round(1)
    out["Big Money Score"] = score.clip(lower=0, upper=100)
    out["Sponsor Score"] = sponsor_score.round(1).clip(lower=0, upper=100)
    out["Move Potential"] = move_score.round(1).clip(lower=0, upper=100)
    out["Extension Risk"] = np.select(
        [already_moved, today >= 5, move5 >= 18],
        ["High - wait reset", "Medium - chase risk", "Medium - extended"],
        default="Controlled",
    )

    tier = np.select(
        [
            (out["Big Money Score"] >= 78) & above_vwap & ~already_moved & ~bad_risk,
            (out["Big Money Score"] >= 66) & ~already_moved & ~bad_risk,
            (out["Big Money Score"] >= 55) & ~bad_risk,
            already_moved,
        ],
        [
            "A - Big Money + Short-Term",
            "B - Institutional Watch",
            "C - Early Sponsorship",
            "D - Extended / Wait Reset",
        ],
        default="Watch Only",
    )
    out["Big Money Tier"] = tier

    reasons: list[str] = []
    triggers: list[str] = []
    for i, row in out.iterrows():
        parts: list[str] = []
        if op.iloc[i] >= 4 or strong_operator.iloc[i]:
            parts.append(f"operator score {op.iloc[i]:.0f}")
        if above_vwap.iloc[i]:
            parts.append("above VWAP")
        if vol.iloc[i] >= 1.5:
            parts.append(f"volume {vol.iloc[i]:.1f}x")
        elif vol.iloc[i] >= 1.0:
            parts.append("volume firm")
        if accumulation_words.iloc[i]:
            parts.append("accumulation/pocket-pivot clue")
        if pre.iloc[i] >= 70:
            parts.append(f"pre-mover {pre.iloc[i]:.0f}")
        elif pre.iloc[i] >= 50:
            parts.append("coil watch")
        if relative_strength.iloc[i]:
            parts.append("relative strength")
        if catalyst.iloc[i]:
            parts.append("catalyst/fuel")
        if already_moved.iloc[i]:
            parts.append("already extended")
        if bad_risk.iloc[i]:
            parts.append("trap/distribution risk")
        reasons.append(" | ".join(parts[:6]) if parts else "needs stronger institutional evidence")

        trigger = str(row.get("Buy Condition", "") or "").strip()
        if not trigger or trigger.lower() in {"nan", "none", "-"}:
            trigger = "Use only after VWAP reclaim/hold plus volume expansion; avoid chasing extended candles."
        triggers.append(trigger)

    out["Big Money Why"] = reasons
    out["Trigger / Risk Plan"] = triggers
    return out.sort_values(["Big Money Score", "Sponsor Score", "Move Potential"], ascending=[False, False, False]).reset_index(drop=True)


@st.cache_data(ttl=60 * 60 * 12, show_spinner=False)
def _holder_snapshot(ticker: str) -> dict:
    """Best-effort holder snapshot from Yahoo. This is delayed, not live buying."""
    result = {
        "Ticker": ticker,
        "Holder Snapshot": "Unavailable",
        "Top Holders": "-",
        "Holder Date": "-",
    }
    try:
        import yfinance as yf

        tkr = yf.Ticker(ticker)
        frames = []
        for attr in ("institutional_holders", "mutualfund_holders"):
            try:
                frame = getattr(tkr, attr)
                if isinstance(frame, pd.DataFrame) and not frame.empty:
                    frames.append(frame.copy())
            except Exception:
                continue
        if not frames:
            return result
        holders = pd.concat(frames, ignore_index=True, sort=False)
        holder_col = next((c for c in holders.columns if "holder" in str(c).lower()), None)
        date_col = next((c for c in holders.columns if "date" in str(c).lower()), None)
        if holder_col:
            names = holders[holder_col].astype(str).replace({"nan": ""})
            names = [x for x in names.tolist() if x.strip()]
            result["Top Holders"] = ", ".join(names[:3]) if names else "-"
        if date_col:
            dates = pd.to_datetime(holders[date_col], errors="coerce").dropna()
            if not dates.empty:
                result["Holder Date"] = dates.max().strftime("%Y-%m-%d")
        result["Holder Snapshot"] = "Yahoo holder data"
    except Exception as exc:
        result["Holder Snapshot"] = f"Unavailable: {str(exc)[:80]}"
    return result


def _style_score(val):
    try:
        v = float(val)
        if v >= 78:
            return "background-color:#d4edda;color:#155724;font-weight:700"
        if v >= 66:
            return "background-color:#d1ecf1;color:#0c5460;font-weight:700"
        if v < 50:
            return "color:#721c24;font-weight:600"
    except Exception:
        pass
    return ""


def render_big_money(ctx: dict) -> None:
    _bind_runtime(ctx)
    st.markdown("## Big Money Radar")
    st.caption(
        "Find scan names with institutional-style accumulation plus short-term move potential. "
        "This uses operator/VWAP/volume/pre-mover evidence; 13F and holder data are delayed."
    )
    st.warning(
        "Use this as a shortlist, not a buy signal. Real hedge-fund 13F data is delayed by weeks. "
        "For short-term trades, confirm VWAP hold, relative volume, trigger level, stop, and reward:risk."
    )

    src = _source_frame()
    if src.empty:
        st.info("Run a market scan first. Big Money Radar uses the latest Long Setups scan or cache.")
        return

    ranked = _rank_big_money(src)
    source_label = st.session_state.get("big_money_source_label", "unknown")
    source_rows = st.session_state.get("big_money_source_rows", len(src))
    st.caption(f"Source: {source_label} - {source_rows} rows. Ranking is market-aware and uses no hardcoded ticker list.")

    f1, f2, f3, f4 = st.columns([1.4, 1.2, 1.2, 1.0])
    with f1:
        tier_filter = st.multiselect(
            "Tier",
            ["A - Big Money + Short-Term", "B - Institutional Watch", "C - Early Sponsorship", "D - Extended / Wait Reset", "Watch Only"],
            default=["A - Big Money + Short-Term", "B - Institutional Watch", "C - Early Sponsorship"],
            key="big_money_tier_filter",
        )
    with f2:
        min_score = st.slider("Min score", 0, 100, 55, 1, key="big_money_min_score")
    with f3:
        hide_extended = st.checkbox("Hide extended/chase risk", value=True, key="big_money_hide_extended")
    with f4:
        search = st.text_input("Ticker", key="big_money_search", placeholder="search").strip().upper()

    view = ranked.copy()
    if tier_filter:
        view = view[view["Big Money Tier"].isin(tier_filter)]
    view = view[view["Big Money Score"] >= float(min_score)]
    if hide_extended:
        view = view[~view["Extension Risk"].astype(str).str.contains("High|chase", case=False, na=False)]
    if search:
        view = view[view["Ticker"].astype(str).str.contains(search, case=False, na=False)]

    a_count = int((ranked["Big Money Tier"] == "A - Big Money + Short-Term").sum())
    b_count = int((ranked["Big Money Tier"] == "B - Institutional Watch").sum())
    c_count = int((ranked["Big Money Tier"] == "C - Early Sponsorship").sum())
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("A candidates", a_count)
    m2.metric("B watch", b_count)
    m3.metric("Early", c_count)
    m4.metric("Shown", len(view))

    if view.empty:
        st.info("No rows match the current filters. Lower Min score or uncheck Hide extended/chase risk.")
        view = ranked.head(25).copy()
        st.caption("Showing top 25 unfiltered rows below for diagnostics.")

    holder_key = "big_money_holder_df"
    h1, h2 = st.columns([1, 3])
    with h1:
        fetch_holders = st.button("Fetch holder snapshot for top 20", key="big_money_fetch_holders")
    if fetch_holders:
        top = view["Ticker"].head(20).astype(str).tolist()
        holder_rows = [_holder_snapshot(t) for t in top]
        st.session_state[holder_key] = pd.DataFrame(holder_rows)
    holders = st.session_state.get(holder_key, pd.DataFrame())
    if isinstance(holders, pd.DataFrame) and not holders.empty:
        view = view.merge(holders, on="Ticker", how="left")
        h2.caption("Yahoo holder snapshot is delayed and may be unavailable for some tickers.")

    display_cols = [
        "Ticker", "Big Money Tier", "Big Money Score", "Sponsor Score", "Move Potential",
        "Extension Risk", "Price", "Today %", "5D %", "20D %", "Vol Ratio", "ATR%",
        "Operator", "Op Score", "VWAP", "Pre-Mover Score", "Pre-Mover Tier",
        "Quality Score", "Next-Day Score", "Rise Prob", "Big Money Why",
        "Trigger / Risk Plan", "Holder Snapshot", "Top Holders", "Holder Date",
    ]
    display_cols = [c for c in display_cols if c in view.columns]
    df_show = view[display_cols].head(80).copy()

    for col in ["Big Money Score", "Sponsor Score", "Move Potential", "Pre-Mover Score", "Quality Score", "Next-Day Score", "Op Score"]:
        if col in df_show.columns:
            df_show[col] = pd.to_numeric(df_show[col], errors="coerce")

    col_cfg = {
        "Ticker": st.column_config.TextColumn("Ticker", width=70),
        "Big Money Tier": st.column_config.TextColumn("Tier", width=190),
        "Big Money Score": st.column_config.NumberColumn("BM Score", width=80),
        "Sponsor Score": st.column_config.NumberColumn("Sponsor", width=80),
        "Move Potential": st.column_config.NumberColumn("Move", width=70),
        "Extension Risk": st.column_config.TextColumn("Risk", width=130),
        "Price": st.column_config.TextColumn("Price", width=70),
        "Today %": st.column_config.TextColumn("Today", width=65),
        "5D %": st.column_config.TextColumn("5D", width=65),
        "20D %": st.column_config.TextColumn("20D", width=65),
        "Vol Ratio": st.column_config.TextColumn("Vol", width=60),
        "ATR%": st.column_config.TextColumn("ATR", width=60),
        "Operator": st.column_config.TextColumn("Operator", width=120),
        "Op Score": st.column_config.NumberColumn("Op", width=50),
        "VWAP": st.column_config.TextColumn("VWAP", width=60),
        "Pre-Mover Score": st.column_config.NumberColumn("Pre", width=60),
        "Pre-Mover Tier": st.column_config.TextColumn("Pre Tier", width=140),
        "Quality Score": st.column_config.NumberColumn("Quality", width=70),
        "Next-Day Score": st.column_config.NumberColumn("Next", width=60),
        "Rise Prob": st.column_config.TextColumn("Rise", width=70),
        "Big Money Why": st.column_config.TextColumn("Why", width=340),
        "Trigger / Risk Plan": st.column_config.TextColumn("Trigger / Risk Plan", width=360),
        "Holder Snapshot": st.column_config.TextColumn("Holder Data", width=130),
        "Top Holders": st.column_config.TextColumn("Top Holders", width=280),
        "Holder Date": st.column_config.TextColumn("Holder Date", width=100),
    }

    styler = df_show.style
    sfn = styler.map if hasattr(styler, "map") else styler.applymap
    styled = sfn(_style_score, subset=["Big Money Score"]) if "Big Money Score" in df_show.columns else styler
    st.dataframe(
        styled,
        width="stretch",
        hide_index=True,
        column_config={k: v for k, v in col_cfg.items() if k in df_show.columns},
        height=min(92 + len(df_show) * 35, 620),
    )

    with st.expander("How Big Money Radar ranks stocks"):
        st.markdown(
            """
- **Sponsor Score**: operator accumulation, VWAP control, volume expansion, pocket-pivot/accumulation clues, relative strength, and compression.
- **Move Potential**: pre-mover score, explosion score, 7-star score, quality, next-day score, ATR, rise probability, and catalyst/fuel words.
- **Penalties**: below VWAP, distribution/trap risk, low participation, RSI exhaustion, and stocks already up too much over today/5D/20D.
- **Holder snapshot**: optional Yahoo institutional/mutual-fund holder names. It is delayed and should confirm sponsorship, not replace the technical setup.
            """
        )
