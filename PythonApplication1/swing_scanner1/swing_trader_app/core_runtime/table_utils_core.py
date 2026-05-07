"""Extracted runtime section from app_runtime.py lines 758-1049.
Loaded by app_runtime with exec(..., globals()) to preserve the original single-file behavior.
"""

# HELPERS  — exact v5 implementations
# ─────────────────────────────────────────────────────────────────────────────
def to_float(val):
    if isinstance(val, (pd.Series, np.ndarray)):
        return float(val.iloc[0] if hasattr(val, "iloc") else val[0])
    return float(val)


def find_swing_lows(low_series, lookback_bars=60, n_side=3):
    series = low_series.tail(lookback_bars).reset_index(drop=True)
    lows = []
    for i in range(n_side, len(series) - n_side):
        w = series.iloc[i - n_side: i + n_side + 1]
        if series.iloc[i] == w.min():
            lows.append((i, float(series.iloc[i])))
    return lows


def find_swing_highs(high_series, lookback_bars=60, n_side=3):
    series = high_series.tail(lookback_bars).reset_index(drop=True)
    highs = []
    for i in range(n_side, len(series) - n_side):
        w = series.iloc[i - n_side: i + n_side + 1]
        if series.iloc[i] == w.max():
            highs.append((i, float(series.iloc[i])))
    return highs


def bayesian_prob(weights_dict, active_signals, bonus=0.0, use_buckets=True):
    """
    Bayesian-style probability with bucket-capping for correlated signals.

    Many signals are statistically dependent ("trend_daily" + "weekly_trend"
    + "full_ma_stack" all measure the same uptrend). Naive Bayesian update
    multiplies their odds ratios as if independent, which over-counts evidence
    and pegs probability at 95% on setups that historically win much less.

    Bucket-cap groups active signals by SIGNAL_BUCKETS, sorts within each bucket
    by weight, and shrinks the k-th signal's distance from BASE_RATE by
    BUCKET_DECAY**k. The hand-set LONG_WEIGHTS / SHORT_WEIGHTS remain fixed.
    """
    # Allow runtime kill-switch from sidebar (debugging / A-B comparison)
    try:
        if not st.session_state.get("use_bucket_cap", True):
            use_buckets = False
    except Exception:
        pass

    # ── 2. Build effective (key, weight) list with optional bucket-cap ────
    eff = []
    if use_buckets and SIGNAL_BUCKETS:
        from collections import defaultdict
        by_bucket = defaultdict(list)
        for key, active in active_signals.items():
            if active and key in weights_dict:
                bucket = SIGNAL_BUCKETS.get(key, f"_solo_{key}")
                by_bucket[bucket].append((key, float(weights_dict[key])))
        for bucket, items in by_bucket.items():
            items.sort(key=lambda kv: -kv[1])
            for k, (key, w) in enumerate(items):
                w_eff = BASE_RATE + (w - BASE_RATE) * (BUCKET_DECAY ** k)
                eff.append((key, w_eff))
    else:
        for key, active in active_signals.items():
            if active and key in weights_dict:
                eff.append((key, float(weights_dict[key])))

    # ── 3. Bayesian update (unchanged math) ────────────────────────────────
    p = BASE_RATE
    for _key, w in eff:
        # Clip to avoid divide-by-zero on degenerate weights
        w = max(0.001, min(0.999, w))
        num = p * (w / BASE_RATE)
        den = num + (1 - p) * ((1 - w) / (1 - BASE_RATE))
        if den <= 0:
            continue
        p = num / den
    p = min(p + bonus, 0.97)
    p = 0.40 + (p - BASE_RATE) / (0.97 - BASE_RATE) * 0.55
    return round(max(0.35, min(0.95, p)), 4)


def prob_label(p):
    if p >= 0.82: return "VERY HIGH"
    if p >= 0.72: return "HIGH"
    if p >= 0.62: return "MODERATE-HIGH"
    if p >= 0.52: return "MODERATE"
    return "LOW"


def style_prob(val):
    try:
        v = float(str(val).rstrip("%"))
        if v >= 82: return "background-color:#D5F5E3;color:#1E8449;font-weight:700"
        if v >= 72: return "background-color:#D6EAF8;color:#1A5276;font-weight:600"
        if v >= 62: return "background-color:#FDEBD0;color:#784212;font-weight:500"
        return "background-color:#FDEDEC;color:#78281F"
    except: return ""


def style_short_prob(val):
    try:
        v = float(str(val).rstrip("%"))
        if v >= 82: return "background-color:#FADBD8;color:#78281F;font-weight:700"
        if v >= 72: return "background-color:#FDEBD0;color:#784212;font-weight:600"
        if v >= 62: return "background-color:#FEF9E7;color:#7D6608;font-weight:500"
        return "background-color:#EBF5FB;color:#1A5276"
    except: return ""

# ─────────────────────────────────────────────────────────────
# GRID SEARCH FILTER (NEW)
# Adds search to ALL tables automatically
# ─────────────────────────────────────────────────────────────
def grid_search_filter(df, label):
    if df.empty:
        return df
    search = st.text_input(f"🔎 Search {label}", key=f"search_{label}",
                           placeholder="ticker…").strip().upper()
    if search and "Ticker" in df.columns:
        df = df[df["Ticker"].str.contains(search, case=False, na=False)]
    return df

def show_table(df, label, prob_col="Rise Prob"):
    if df.empty:
        st.info(f"No {label} setups.")
        return

    df = grid_search_filter(df, label)

    # ── Sort by Entry Quality ─────────────────────────────────────────────────
    _quality_order = {"✅ BUY": 0, "👀 WATCH": 1, "⏳ WAIT": 2, "🚫 AVOID": 3}
    if "Entry Quality" in df.columns:
        df = df.copy()
        df["_eq_sort"] = df["Entry Quality"].map(_quality_order).fillna(9)
        df = df.sort_values(["_eq_sort", prob_col],
                            ascending=[True, False],
                            key=lambda s: s if s.name != prob_col
                                          else s.str.rstrip("%").astype(float))
        df = df.drop(columns="_eq_sort")

    # ── Column selection ──────────────────────────────────────────────────────
    if prob_col == "Rise Prob":
        display_cols = [c for c in [
            "Ticker", "Entry Quality", "Setup Type", "Today %", "Rise Prob", 
            "Operator", "VWAP", "Trap Risk",
            "Price", "MA60 Stop", "TP1 +10%", "TP2 +15%", "TP3 +20%",
            "Sector", "Action",
            "Score","Op Score",
        ] if c in df.columns]
    else:
        display_cols = [c for c in [
            "Ticker", "Entry Quality", "Setup Type", "Today %", "Fall Prob", 
            "Operator", "VWAP", "Trap Risk",
            "Price", "Cover Stop", "Target 1:1", "Target 1:2",
            "Sector", "Action",
            "Score","Op Score",
        ] if c in df.columns]

    df_disp = df[display_cols] if display_cols else df

    # ── Narrow column_config — makes grid appear smaller ─────────────────────
    col_cfg = {
        "Ticker":        st.column_config.TextColumn("Ticker",        width=60),
        "Entry Quality": st.column_config.TextColumn("Entry",         width=70),
        "Setup Type":    st.column_config.TextColumn("Setup",         width=90),
        "Today %":       st.column_config.TextColumn("Today%",        width=58),
        "Rise Prob":     st.column_config.TextColumn("Rise%",         width=55),
        "Fall Prob":     st.column_config.TextColumn("Fall%",         width=55),
        "Operator":      st.column_config.TextColumn("Operator",      width=120),
        "VWAP":          st.column_config.TextColumn("VWAP",          width=60),
        "Trap Risk":     st.column_config.TextColumn("Trap",          width=80),
        "Price":         st.column_config.TextColumn("Price",         width=60),
        "MA60 Stop":     st.column_config.TextColumn("MA60Stop",      width=65),
        "Cover Stop":    st.column_config.TextColumn("CoverStop",     width=65),
        "TP1 +10%":      st.column_config.TextColumn("TP1+10%",       width=62),
        "TP2 +15%":      st.column_config.TextColumn("TP2+15%",       width=62),
        "TP3 +20%":      st.column_config.TextColumn("TP3+20%",       width=62),
        "Target 1:1":    st.column_config.TextColumn("T1",            width=62),
        "Target 1:2":    st.column_config.TextColumn("T2",            width=62),
        "Sector":        st.column_config.TextColumn("Sector",        width=90),
        "Action":        st.column_config.TextColumn("Action",        width=80),
        "Op Score":      st.column_config.TextColumn("Op",            width=45),
        "Score":         st.column_config.TextColumn("Score",         width=50),
    }
    # keep only configs for columns that exist
    cfg = {k: v for k, v in col_cfg.items() if k in df_disp.columns}

    n_rows = len(df_disp)
    row_h  = 35   # px per row
    height = min(35 + n_rows * row_h, 400)   # cap at 400px

    styler   = df_disp.style
    style_fn = styler.map if hasattr(styler, "map") else styler.applymap
    fn = style_short_prob if prob_col == "Fall Prob" else style_prob

    if prob_col in df_disp.columns:
        st.dataframe(
            style_fn(fn, subset=[prob_col]),
            width="stretch",
            hide_index=True,
            column_config=cfg,
            height=height,
        )
    else:
        st.dataframe(
            df_disp,
            width="stretch",
            hide_index=True,
            column_config=cfg,
            height=height,
        )


def _extract_closes(raw, ticker, n_tickers):
    """Robustly extract Close series from yfinance MultiIndex or flat DataFrame."""
    if n_tickers == 1:
        return raw["Close"].squeeze().ffill().dropna()
    if isinstance(raw.columns, pd.MultiIndex):
        lvl1 = raw.columns.get_level_values(1)
        lvl0 = raw.columns.get_level_values(0)
        if ticker in lvl1:
            return raw.xs(ticker, axis=1, level=1)["Close"].ffill().dropna()
        if ticker in lvl0:
            return raw[ticker]["Close"].ffill().dropna()
    if ticker in raw.columns:
        return raw[ticker]["Close"].squeeze().ffill().dropna()
    return pd.Series(dtype=float)


# ─────────────────────────────────────────────────────────────
# OHLCV CLEANING FOR STREAMLIT CLOUD / YFINANCE PARTIAL BARS
# ─────────────────────────────────────────────────────────────
def _clean_scan_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Clean yfinance OHLCV before signal calculation.

    On Streamlit Cloud, Yahoo sometimes returns the current in-progress day
    as a partial/empty row. The old code used `ffill().dropna()`, which could
    forward-fill that empty row with yesterday's Close. Then the latest Close
    and previous Close became identical and `Today %` showed 0.00% for many
    or all stocks.

    This cleaner drops incomplete / zero-volume OHLCV rows BEFORE any forward
    fill so Today % is calculated from the last two real trading bars.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = out.columns.get_level_values(0)

    # Keep only useful columns that exist.
    cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in out.columns]
    if "Close" not in cols:
        return pd.DataFrame()
    out = out[cols]

    # Convert to numeric and remove fully invalid rows.
    for c in cols:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    out = out.replace([np.inf, -np.inf], np.nan)

    required = [c for c in ["High", "Low", "Close"] if c in out.columns]
    out = out.dropna(subset=required)

    # For stocks, a zero/NaN volume row is usually a partial/stub Cloud row.
    # Dropping it prevents false 0.00% Today values caused by forward fill.
    if "Volume" in out.columns:
        out = out.dropna(subset=["Volume"])
        out = out[out["Volume"] > 0]

    # De-duplicate and sort, then fill only small internal gaps after invalid
    # trailing rows have been removed.
    out = out[~out.index.duplicated(keep="last")].sort_index()
    out = out.ffill().dropna(subset=required)
    return out


def _safe_today_change_pct(close: pd.Series) -> float:
    """Return latest close vs previous real close in percent."""
    try:
        c = pd.to_numeric(close, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        if len(c) < 2:
            return 0.0
        prev = float(c.iloc[-2])
        last = float(c.iloc[-1])
        if prev == 0:
            return 0.0
        return float((last - prev) / prev * 100.0)
    except Exception:
        return 0.0


