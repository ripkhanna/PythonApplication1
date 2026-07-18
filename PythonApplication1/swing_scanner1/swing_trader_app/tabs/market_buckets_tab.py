"""Market Buckets tab renderer.

Classifies the latest scanner rows into practical trading buckets:
buy candidate, starter/discovery, wait for pullback, oversold/reversal watch,
wait for trigger/base, and avoid/short bias. The output grid is searchable and
filterable without adding new Streamlit dependencies.
"""

from __future__ import annotations

import math
import re

import pandas as pd


def _bind_runtime(ctx: dict) -> None:
    """Expose original app globals to this module for monolith-compatible tab code."""
    globals().update(ctx)


def _num(value, default: float = math.nan) -> float:
    if value is None:
        return default
    try:
        if isinstance(value, float) and math.isnan(value):
            return default
    except Exception:
        pass
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none"} or text in {"-", "--", "–", "—"}:
        return default
    text = text.replace(",", "").replace("$", "").replace("%", "").replace("+", "")
    if text.startswith("1:"):
        text = text[2:]
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else default


def _series_num(df: pd.DataFrame, col: str, default: float = 0.0) -> pd.Series:
    if col not in df.columns:
        return pd.Series([default] * len(df), index=df.index, dtype="float64")
    return df[col].map(lambda value: _num(value, default))


def _series_text(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series([""] * len(df), index=df.index, dtype="object")
    return df[col].fillna("").astype(str)


def _rank_score(df: pd.DataFrame) -> pd.Series:
    qs = _series_num(df, "Quality Score", 0)
    nds = _series_num(df, "Next-Day Score", 0)
    prob = _series_num(df, "Rise Prob", 0)
    rr = _series_num(df, "RR Est", 0).clip(upper=5)
    upside = _series_num(df, "Upside to Res", 0).clip(lower=0, upper=30)
    op = _series_num(df, "Op Score", 0)
    return qs * 2.0 + nds * 1.5 + prob / 8.0 + rr * 1.5 + upside / 4.0 + op


def _classify_long_rows(df_long: pd.DataFrame) -> pd.DataFrame:
    if df_long is None or df_long.empty:
        return pd.DataFrame()

    out = df_long.copy()
    action = _series_text(out, "Action")
    entry = _series_text(out, "Entry Quality")
    tier = _series_text(out, "Trade Tier")
    setup = _series_text(out, "Setup Type")
    phase = _series_text(out, "Early Rally Phase")
    gate = _series_text(out, "Early Rally Gate")
    missing = _series_text(out, "Early Rally Missing")
    explosion = _series_text(out, "Explosion Tier")
    signals = _series_text(out, "Signals")

    qs = _series_num(out, "Quality Score", 0)
    nds = _series_num(out, "Next-Day Score", 0)
    rsi = _series_num(out, "RSI Now", math.nan)
    rsi = rsi.where(rsi.notna(), _series_num(out, "RSI", math.nan))
    five_day = _series_num(out, "5D %", 0)
    twenty_day = _series_num(out, "20D %", 0)
    today = _series_num(out, "Today %", 0)
    rr = _series_num(out, "RR Est", 0)
    upside = _series_num(out, "Upside to Res", 0)

    tradeable = _series_text(out, "Tradeable Buy").str.upper().eq("YES")
    full_buy = tradeable | (entry.str.contains("BUY", case=False, na=False) & tier.isin(["A+", "Full"]))
    starter = tier.isin(["Discovery", "Near-Miss"]) | entry.str.contains("DISCOVERY|NEAR-MISS", case=False, na=False)
    extended = (
        action.str.contains("CHASING", case=False, na=False)
        | phase.str.contains("MOVED ALREADY|WAIT PULLBACK", case=False, na=False)
        | explosion.str.contains("MOVED ALREADY", case=False, na=False)
        | (rsi >= 70)
        | (today >= 6)
        | (five_day >= 8)
        | (twenty_day >= 15)
    )
    oversold = (
        (rsi <= 40)
        | (five_day <= -7)
        | (twenty_day <= -12)
        | setup.str.contains("Failed Breakdown|Stabilization", case=False, na=False)
        | signals.str.contains("SELL climax|BEAR TRAP|climax", case=False, na=False)
    )
    trigger_watch = (
        (qs >= 8)
        & action.str.contains("WATCH", case=False, na=False)
        & entry.str.contains("WATCH|WAIT", case=False, na=False)
    )

    bucket = pd.Series(["Watch / Lower Priority"] * len(out), index=out.index)
    reason = pd.Series(["Lower scanner priority; revisit only if a fresh trigger appears."] * len(out), index=out.index)
    wait_for = pd.Series(["Fresh volume, support reclaim, or base breakout."] * len(out), index=out.index)

    bucket.loc[trigger_watch] = "Wait For Trigger/Base"
    reason.loc[trigger_watch] = "Watchlist-quality row, but confirmation gates are incomplete."
    wait_for.loc[trigger_watch] = "Breakout/volume trigger or base completion."

    bucket.loc[starter] = "Starter / Discovery"
    reason.loc[starter] = "Discovery or near-miss row, not a full tradeable gate pass."
    wait_for.loc[starter] = "Small starter only after trigger; add only if volume/RR improves."

    bucket.loc[full_buy & ~extended & ~oversold] = "Buy Candidate"
    reason.loc[full_buy & ~extended & ~oversold] = "Scanner buy gate passed and entry is not marked extended."
    wait_for.loc[full_buy & ~extended & ~oversold] = "Fresh next-session confirmation plus defined stop."

    bucket.loc[extended & (qs >= 7)] = "Wait For Pullback"
    reason.loc[extended & (qs >= 7)] = "Quality/momentum exists, but chase or extension risk is high."
    wait_for.loc[extended & (qs >= 7)] = "Pullback/reset near MA20/support or a fresh high-volume breakout."

    bucket.loc[oversold] = "Oversold / Reversal Watch"
    reason.loc[oversold] = "Momentum is damaged or oversold; do not catch the falling move."
    wait_for.loc[oversold] = "Bullish reversal close, MA5/MA10 reclaim, or support hold on volume."

    out["Market Bucket"] = bucket
    out["Bucket Reason"] = reason
    out["Wait For / Trigger"] = wait_for
    out["Bucket Rank"] = _rank_score(out)
    out["RSI Used"] = rsi
    out["RR Numeric"] = rr
    out["Upside Numeric"] = upside
    out["Quality Numeric"] = qs
    out["Next-Day Numeric"] = nds
    return out


def _classify_short_rows(df_short: pd.DataFrame) -> pd.DataFrame:
    if df_short is None or df_short.empty:
        return pd.DataFrame()

    out = df_short.copy()
    action = _series_text(out, "Action")
    entry = _series_text(out, "Entry Quality")
    mask = action.str.contains("SHORT|SELL", case=False, na=False) | entry.str.contains("SELL", case=False, na=False)
    out = out[mask].copy()
    if out.empty:
        return out

    out["Market Bucket"] = "Avoid / Short Bias"
    out["Bucket Reason"] = "Short/distribution row from the scanner; not a long-buy candidate."
    out["Wait For / Trigger"] = "Avoid long entry until base repair or reclaim above moving averages."
    out["Bucket Rank"] = _series_num(out, "Fall Prob", 0) / 5 + _series_num(out, "Op Score", 0)
    out["RSI Used"] = _series_num(out, "RSI", math.nan)
    out["RR Numeric"] = math.nan
    out["Upside Numeric"] = math.nan
    out["Quality Numeric"] = math.nan
    out["Next-Day Numeric"] = math.nan
    return out


def _bucket_order(bucket: str) -> int:
    order = {
        "Buy Candidate": 1,
        "Starter / Discovery": 2,
        "Wait For Pullback": 3,
        "Oversold / Reversal Watch": 4,
        "Wait For Trigger/Base": 5,
        "Avoid / Short Bias": 6,
        "Watch / Lower Priority": 7,
    }
    return order.get(str(bucket), 99)


def _build_bucket_df(df_long: pd.DataFrame, df_short: pd.DataFrame) -> pd.DataFrame:
    parts = []
    long_rows = _classify_long_rows(df_long)
    if not long_rows.empty:
        parts.append(long_rows)
    short_rows = _classify_short_rows(df_short)
    if not short_rows.empty:
        parts.append(short_rows)
    if not parts:
        return pd.DataFrame()

    out = pd.concat(parts, ignore_index=True, sort=False)
    out["Bucket Order"] = out["Market Bucket"].map(_bucket_order)
    out = out.sort_values(["Bucket Order", "Bucket Rank"], ascending=[True, False])
    return out


def _first_dataframe(*values) -> pd.DataFrame:
    for value in values:
        if isinstance(value, pd.DataFrame) and not value.empty:
            return value.copy()
    return pd.DataFrame()


def _filter_search(df: pd.DataFrame, query: str) -> pd.DataFrame:
    raw_query = (query or "").strip()
    if not raw_query:
        return df
    text = df.fillna("").astype(str).agg(" ".join, axis=1).str.lower()

    def _term_mask(terms: list[str], require_all: bool) -> pd.Series:
        if not terms:
            return pd.Series([True] * len(df), index=df.index)
        masks = [text.str.contains(re.escape(term), na=False) for term in terms]
        if require_all:
            out = pd.Series([True] * len(df), index=df.index)
            for mask in masks:
                out &= mask
            return out
        out = pd.Series([False] * len(df), index=df.index)
        for mask in masks:
            out |= mask
        return out

    # Commas/semicolons/new lines mean "show any of these", so searches like
    # O39,D05,U11 work naturally. Space-only text remains AND search unless all
    # tokens look like ticker symbols.
    groups = [g.strip().lower() for g in re.split(r"[,;\n]+", raw_query) if g.strip()]
    if not groups:
        return df
    if len(groups) > 1:
        mask = pd.Series([False] * len(df), index=df.index)
        for group in groups:
            terms = [term.strip() for term in group.split() if term.strip()]
            mask |= _term_mask(terms, require_all=True)
        return df[mask]

    terms = [term.strip().lower() for term in groups[0].split() if term.strip()]
    ticker_like = bool(terms) and all(re.search(r"\d|\.", term) for term in terms)
    return df[_term_mask(terms, require_all=not ticker_like)]


def _selected_columns(df: pd.DataFrame) -> list[str]:
    wanted = [
        "Ticker",
        "Market Bucket",
        "Bucket Reason",
        "Wait For / Trigger",
        "Action",
        "Setup Type",
        "Entry Quality",
        "Tradeable Buy",
        "Trade Tier",
        "Quality Score",
        "Next-Day Score",
        "Rise Prob",
        "RR Est",
        "Upside to Res",
        "RSI Used",
        "Today %",
        "5D %",
        "20D %",
        "60D %",
        "Price",
        "Vol Ratio",
        "Operator",
        "Op Score",
        "VWAP",
        "Trap Risk",
        "Early Rally Phase",
        "Early Rally Gate",
        "Early Rally Missing",
        "Signals",
    ]
    return [col for col in wanted if col in df.columns]


def render_market_buckets(ctx: dict) -> None:
    _bind_runtime(ctx)
    st.caption("Market Buckets - buy, starter, pullback, oversold, trigger, and avoid lists from the latest scanner results")

    source_mode = st.radio(
        "Source rows",
        ["Master scan (all scanned rows)", "Visible strategy grid"],
        horizontal=True,
        key="bucket_grid_source_mode",
        help=(
            "Master scan keeps names that the current strategy view may hide. "
            "Visible strategy grid mirrors the current Long/Short tabs."
        ),
    )
    if source_mode.startswith("Master"):
        source_long = _first_dataframe(
            globals().get("df_long_master"),
            st.session_state.get("df_long_master"),
            globals().get("df_long"),
            st.session_state.get("df_long"),
        )
        source_short = _first_dataframe(
            globals().get("df_short_master"),
            st.session_state.get("df_short_master"),
            globals().get("df_short"),
            st.session_state.get("df_short"),
        )
    else:
        source_long = _first_dataframe(globals().get("df_long"), st.session_state.get("df_long"))
        source_short = _first_dataframe(globals().get("df_short"), st.session_state.get("df_short"))

    bucket_df = _build_bucket_df(source_long, source_short)
    if bucket_df.empty:
        st.warning("No scan rows available. Run Scan first or enable CSV result cache loading.")
        return

    market_label = globals().get("market_sel", st.session_state.get("market_selector", "current market"))
    last_market = st.session_state.get("last_market", market_label)
    st.info(
        f"Using latest scanner rows for {last_market}. Buckets are based on scanner fields only; "
        "re-run Scan for live decisions."
    )

    counts = bucket_df["Market Bucket"].value_counts().to_dict()
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Buy", int(counts.get("Buy Candidate", 0)))
    c2.metric("Starter", int(counts.get("Starter / Discovery", 0)))
    c3.metric("Pullback", int(counts.get("Wait For Pullback", 0)))
    c4.metric("Oversold", int(counts.get("Oversold / Reversal Watch", 0)))
    c5.metric("Trigger", int(counts.get("Wait For Trigger/Base", 0)))
    c6.metric("Avoid", int(counts.get("Avoid / Short Bias", 0)))

    buckets = list(dict.fromkeys(bucket_df["Market Bucket"].astype(str).tolist()))
    setups = sorted([x for x in bucket_df.get("Setup Type", pd.Series(dtype=str)).dropna().astype(str).unique() if x])
    entries = sorted([x for x in bucket_df.get("Entry Quality", pd.Series(dtype=str)).dropna().astype(str).unique() if x])

    f1, f2, f3, f4 = st.columns([1.8, 1.3, 1.2, 1.0])
    with f1:
        search = st.text_input(
            "Search grid",
            "",
            key="bucket_grid_search",
            placeholder="Ticker, bucket, action, signal, reason...",
        )
    with f2:
        selected_buckets = st.multiselect("Buckets", buckets, default=buckets, key="bucket_grid_buckets")
    with f3:
        selected_setups = st.multiselect("Setup type", setups, default=[], key="bucket_grid_setups")
    with f4:
        min_quality = st.slider("Min quality", 0, 25, 0, key="bucket_grid_min_quality")

    f5, f6, f7 = st.columns([1.2, 1.2, 1.4])
    with f5:
        selected_entries = st.multiselect("Entry quality", entries, default=[], key="bucket_grid_entries")
    with f6:
        hide_lower = st.checkbox("Hide lower priority", value=True, key="bucket_grid_hide_lower")
    with f7:
        max_rows = st.slider("Rows shown", 25, 300, 150, step=25, key="bucket_grid_max_rows")

    filtered = bucket_df.copy()
    if selected_buckets:
        filtered = filtered[filtered["Market Bucket"].astype(str).isin(selected_buckets)]
    if selected_setups and "Setup Type" in filtered.columns:
        filtered = filtered[filtered["Setup Type"].astype(str).isin(selected_setups)]
    if selected_entries and "Entry Quality" in filtered.columns:
        filtered = filtered[filtered["Entry Quality"].astype(str).isin(selected_entries)]
    if hide_lower:
        filtered = filtered[filtered["Market Bucket"].astype(str) != "Watch / Lower Priority"]
    filtered = filtered[_series_num(filtered, "Quality Score", 0) >= min_quality]
    filtered = _filter_search(filtered, search)
    filtered = filtered.sort_values(["Bucket Order", "Bucket Rank"], ascending=[True, False]).head(max_rows)

    st.caption(f"Showing {len(filtered)} of {len(bucket_df)} classified rows.")
    display_cols = _selected_columns(filtered)
    st.dataframe(
        filtered[display_cols],
        width="stretch",
        hide_index=True,
        height=min(650, 42 + 31 * max(1, len(filtered))),
    )

    csv = filtered[display_cols].to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download filtered bucket grid CSV",
        csv,
        "market_buckets_filtered.csv",
        "text/csv",
        key="bucket_grid_download",
    )

    with st.expander("Copy tickers by bucket", expanded=False):
        for bucket_name in buckets:
            tickers = []
            if "Ticker" in bucket_df.columns:
                tickers = (
                    bucket_df[bucket_df["Market Bucket"].astype(str).eq(bucket_name)]["Ticker"]
                    .dropna()
                    .astype(str)
                    .tolist()
                )
            st.text_area(bucket_name, ", ".join(tickers) or "-", height=70, key=f"bucket_copy_{bucket_name}")
