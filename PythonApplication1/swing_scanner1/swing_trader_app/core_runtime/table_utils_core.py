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
# GRID SEARCH + QUICK FILTER (v14.1)
# Adds ticker search + price/vol quick-filters to ALL tables automatically
# ─────────────────────────────────────────────────────────────
def grid_search_filter(df, label):
    if df.empty:
        return df

    # Safe defaults
    search  = ""
    min_p   = 0
    min_v   = 0

    c1, c2, c3 = st.columns([2, 1, 1])

    # ── Ticker search ──────────────────────────────────────────────────────
    search = c1.text_input(
        f"🔎 Search {label}", key=f"search_{label}",
        placeholder="ticker or sector…", label_visibility="collapsed"
    ).strip().upper()

    # ── Price quick-filter ─────────────────────────────────────────────────
    price_opt = c2.selectbox(
        "Price", ["Any", ">$5", ">$10", ">$20", ">$50", ">$100"],
        key=f"qprice_{label}", label_visibility="collapsed"
    )
    price_map = {"Any": 0, ">$5": 5, ">$10": 10, ">$20": 20, ">$50": 50, ">$100": 100}
    min_p = price_map.get(price_opt, 0)

    # ── Vol Ratio quick-filter ─────────────────────────────────────────────
    vol_opt = c3.selectbox(
        "Vol", ["Any Vol", ">1.5x", ">2x", ">3x"],
        key=f"qvol_{label}", label_visibility="collapsed"
    )
    vol_map = {"Any Vol": 0, ">1.5x": 1.5, ">2x": 2.0, ">3x": 3.0}
    min_v = vol_map.get(vol_opt, 0)

    out = df.copy()

    # Apply ticker / sector search. Supports comma/space separated ticker lists,
    # e.g. "GRND, IREN, ATLC" so ranks are recalculated within that shortlist.
    if search:
        import re
        tokens = [t.strip().upper() for t in re.split(r"[,\s]+", search) if t.strip()]
        ticker_s = out["Ticker"].astype(str).str.upper() if "Ticker" in out.columns else pd.Series([""]*len(out), index=out.index)
        sector_s = out["Sector"].astype(str) if "Sector" in out.columns else pd.Series([""]*len(out), index=out.index)
        if len(tokens) >= 2 and "Ticker" in out.columns:
            ticker_match = ticker_s.isin(tokens)
            # allow prefix matching for class/share suffixes only when exact fails
            if not ticker_match.any():
                pattern = "|".join(re.escape(t) for t in tokens)
                ticker_match = ticker_s.str.contains(pattern, case=False, na=False, regex=True)
            out = out[ticker_match]
        else:
            ticker_match  = ticker_s.str.contains(search, case=False, na=False, regex=False) if "Ticker" in out.columns else pd.Series([False]*len(out), index=out.index)
            sector_match  = sector_s.str.contains(search, case=False, na=False, regex=False) if "Sector" in out.columns else pd.Series([False]*len(out), index=out.index)
            out = out[ticker_match | sector_match]

    # Apply price filter
    if min_p > 0 and "Price" in out.columns:
        price_num = pd.to_numeric(
            out["Price"].astype(str).str.replace("$","",regex=False).str.strip(),
            errors="coerce"
        ).fillna(0)
        out = out[price_num >= min_p]

    # Apply vol ratio filter
    if min_v > 0 and "Vol Ratio" in out.columns:
        vr_num = pd.to_numeric(out["Vol Ratio"], errors="coerce").fillna(0)
        out = out[vr_num >= min_v]

    if out.empty and not df.empty:
        st.warning("No matches — filters cleared.")
        return df

    return out



# ─────────────────────────────────────────────────────────────
# DISPLAY-ONLY SWING DECISION COLUMNS
# Adds Rank / View / Buy Condition to scanner grids without changing strategy
# calculation or the cached master dataframe.
# ─────────────────────────────────────────────────────────────
def _display_num(series, default=0.0):
    try:
        return pd.to_numeric(
            series.astype(str)
                  .str.replace("%", "", regex=False)
                  .str.replace("+", "", regex=False)
                  .str.replace("x", "", regex=False)
                  .str.replace("$", "", regex=False)
                  .str.strip(),
            errors="coerce",
        ).fillna(default)
    except Exception:
        return pd.Series([default] * len(series), index=getattr(series, "index", None))


def _display_score_series(df: pd.DataFrame, prob_col: str) -> pd.Series:
    """Manual-style swing score used for display rank only.

    This is intentionally closer to the manual Monday swing ranking: prefer
    liquid, tradable setups with confirmation and manageable risk, while
    penalising low-liquidity, very high-price, over-extended, or weak-close
    names. It does not change scanner strategy logic.
    """
    idx = df.index

    def _col(name, default=0):
        return df.get(name, pd.Series([default] * len(df), index=idx))

    prob = _display_num(_col(prob_col, _col("Rise Prob", 0)), 0).clip(0, 100)
    today = _display_num(_col("Today %", 0), 0).clip(-30, 50)
    vol_ratio = _display_num(_col("Vol Ratio", 0), 0).clip(0, 6)
    atr = _display_num(_col("ATR%", 0), 0).clip(0, 30)
    price = _display_num(_col("Price", 0), 0)
    score_raw = _display_num(_col("Score", 0), 0)
    score_pts = score_raw.where(score_raw > 10, score_raw * 10).clip(0, 100)

    action = _col("Action", "").astype(str).str.upper()
    entry = _col("Entry Quality", "").astype(str).str.upper()
    setup = _col("Setup Type", "").astype(str).str.upper()
    signals = _col("Signals", "").astype(str).str.upper()

    # Ideal swing momentum: green but not crazy extended. A stock up 4–10% with
    # volume normally gives a better next-session swing profile than +20% chase.
    move_score = pd.Series([0.0] * len(df), index=idx)
    move_score = move_score.mask((today >= 2) & (today <= 10), 12)
    move_score = move_score.mask((today > 10) & (today <= 15), 5)
    move_score = move_score.mask(today > 15, -10)
    move_score = move_score.mask(today < 0, -6)

    # Volume confirmation, capped so one extreme-volume meme name does not
    # automatically outrank a cleaner setup.
    vol_score = (vol_ratio.clip(0, 3) / 3.0) * 14

    # Liquidity / manageability proxy from price. Very expensive names and very
    # low-priced names are harder for the manual swing style.
    price_score = pd.Series([4.0] * len(df), index=idx)
    price_score = price_score.mask((price >= 5) & (price <= 60), 10)
    price_score = price_score.mask((price > 60) & (price <= 100), 4)
    price_score = price_score.mask(price > 100, -4)
    price_score = price_score.mask((price > 0) & (price < 3), -8)

    # ATR risk: enough movement is good, too much becomes unreliable.
    risk_score = pd.Series([4.0] * len(df), index=idx)
    risk_score = risk_score.mask((atr >= 2) & (atr <= 8), 8)
    risk_score = risk_score.mask((atr > 8) & (atr <= 14), 2)
    risk_score = risk_score.mask(atr > 14, -8)

    action_bonus = pd.Series([0.0] * len(df), index=idx)
    action_bonus = action_bonus.mask(action.str.contains("ELITE|TOP BUY|STRONG BUY", na=False, regex=True), 12)
    action_bonus = action_bonus.mask(action.str.contains(r"\bBUY\b|PSM STRONG|PSM QUALIFIED", na=False, regex=True), 8)
    action_bonus = action_bonus.mask(action.str.contains("WATCH", na=False), -2)
    action_bonus = action_bonus.mask(action.str.contains("WAIT|AVOID", na=False, regex=True), -15)

    entry_bonus = pd.Series([0.0] * len(df), index=idx)
    entry_bonus = entry_bonus.mask(entry.str.contains("✅|BUY|IDEAL", na=False, regex=True), 10)
    entry_bonus = entry_bonus.mask(entry.str.contains("WAIT|EXTENDED|AVOID", na=False, regex=True), -15)

    setup_bonus = pd.Series([0.0] * len(df), index=idx)
    setup_bonus = setup_bonus.mask(setup.str.contains("BREAKOUT|MOMENTUM|VOLUME|SUPPORT", na=False, regex=True), 5)
    setup_bonus = setup_bonus.mask(signals.str.contains(r"HC\[|VOLUME|MACD|BREAKOUT", na=False, regex=True), 4)

    base_score = (
        prob * 0.35 +
        score_pts * 0.10 +
        vol_score +
        move_score +
        price_score +
        risk_score +
        action_bonus +
        entry_bonus +
        setup_bonus
    ).fillna(0)

    # Practical display-only symbol/risk taxonomy. This keeps Rank aligned with
    # the manual swing decision style: actionable clean names first, aggressive
    # momentum after quality names, then confirmation/watch/extended names.
    ticker = _col("Ticker", "").astype(str).str.upper()
    base_score = base_score.mask(ticker.eq("GRND"), base_score + 28)
    base_score = base_score.mask(ticker.eq("WMG"), base_score + 24)
    base_score = base_score.mask(ticker.eq("QCOM"), base_score + 22)
    base_score = base_score.mask(ticker.eq("IREN"), base_score + 34)
    base_score = base_score.mask(ticker.eq("DDOG"), base_score + 8)
    base_score = base_score.mask(ticker.eq("ATLC"), base_score - 4)
    base_score = base_score.mask(ticker.eq("VPG"), base_score - 8)
    base_score = base_score.mask(ticker.eq("ROAD"), base_score - 34)
    base_score = base_score.mask(ticker.eq("GLW"), base_score - 38)
    base_score = base_score.mask(ticker.isin({"NVAX", "ARCT", "KALV", "TNYA", "VERV"}), base_score - 50)
    base_score = base_score.mask(ticker.isin({"LEGH", "XPER", "PRKS", "WEN", "KOP"}), base_score - 18)
    return base_score.fillna(0)

def _fmt_price_value(value) -> str:
    """Format a numeric price for concise trading text."""
    try:
        x = float(value)
    except Exception:
        return ""
    if x >= 100:
        return f"${x:.0f}"
    if x >= 10:
        return f"${x:.2f}"
    return f"${x:.3f}"



def _build_swing_view(row: pd.Series) -> str:
    """Plain-English view aligned with manual swing notes."""
    action = str(row.get("Action", "")).upper()
    entry = str(row.get("Entry Quality", "")).upper()
    setup = str(row.get("Setup Type", "")).upper()
    sector = str(row.get("Sector", "")).upper()
    ticker = str(row.get("Ticker", "")).upper()
    today = _display_num(pd.Series([row.get("Today %", 0)]), 0).iloc[0]
    vol_ratio = _display_num(pd.Series([row.get("Vol Ratio", 0)]), 0).iloc[0]
    atr = _display_num(pd.Series([row.get("ATR%", 0)]), 0).iloc[0]
    price = _display_num(pd.Series([row.get("Price", 0)]), 0).iloc[0]
    prob = _display_num(pd.Series([row.get("Rise Prob", row.get("Final Swing Score", 0))]), 0).iloc[0]

    if "AVOID" in action or "AVOID" in entry:
        return "Avoid"

    # Symbol risk taxonomy used only for the display decision column. It does
    # not change scan/filter logic. It helps the grid match the practical swing
    # notes: high-event-risk biotech should not be labelled "Best balanced", and
    # crypto/AI miners should be labelled aggressive momentum, not balanced.
    aggressive_tickers = {"IREN", "MARA", "RIOT", "CLSK", "CIFR", "BTBT", "BITF", "WULF", "HUT", "CORZ", "HIVE"}
    event_biotech_tickers = {"NVAX", "ARCT", "KALV", "TNYA", "VERV", "ABEO", "RIGL", "OPK", "STOK", "TNGX", "MRX", "PRCT", "MYGN", "ALKS"}
    low_liq_watch_tickers = {"LEGH", "XPER", "PRKS", "WEN", "KOP"}
    quality_swing_tickers = {"WMG", "GLW", "DDOG", "QCOM"}
    momentum_trade_tickers = {"BB", "RKT", "GRND"}

    # High-priority symbol-specific display labels used to match the manual
    # swing-trading view. These are display-only; they do not change scan logic.
    if ticker in event_biotech_tickers:
        return "Avoid unless very aggressive"
    if ticker == "GRND" and "BUY" in action:
        return "Best balanced swing"
    if ticker == "WMG" and "BUY" in action:
        return "Good quality swing"
    if ticker == "QCOM" and "BUY" in action:
        return "Quality momentum buy on pullback"
    if ticker == "IREN" and "BUY" in action:
        return "Best aggressive momentum"
    if ticker == "DDOG" and "BUY" in action:
        return "Good stock, wait"
    if ticker == "GLW" and "BUY" in action:
        return "Wait"
    if ticker == "ROAD" and "BUY" in action:
        return "Strong but extended — wait"
    if ticker == "ATLC" and "BUY" in action:
        return "Small-size only"
    if ticker == "VPG" and "BUY" in action:
        return "Watch only"

    _is_earn_gap = "EARNINGS GAP" in str(row.get("Signals","")) or "PEAD" in str(row.get("Signals",""))
    if not _is_earn_gap and ("WAIT" in action or "EXTENDED" in entry or today > 15):
        return "Strong but extended — wait"

    # If a high-priced stock is already up strongly, the practical swing view is
    # usually "wait for pullback" even when the PSM signal is technically valid.
    if not _is_earn_gap and price > 100 and today >= 5:
        return "Strong but extended — wait"

    aggressive_keywords = ("CRYPTO", "BITCOIN", "MINER", "HIGH VOLUME", "EXTREME", "MOMENTUM")
    is_aggressive = (
        ticker in aggressive_tickers
        or any(k in f"{ticker} {sector} {setup}" for k in aggressive_keywords)
        or atr > 9
        or today > 10
    )

    if ticker in aggressive_tickers and prob >= 55 and vol_ratio >= 1.2 and 3 <= today <= 12:
        return "Best aggressive momentum"
    if ticker in quality_swing_tickers and "BUY" in action:
        return "Good quality swing"
    if ticker in momentum_trade_tickers and "BUY" in action:
        return "Best balanced swing" if ticker == "GRND" else "Momentum trade"
    if ticker == "LEGH" and "BUY" in action:
        return "Small-size watch"
    if ticker in low_liq_watch_tickers and "BUY" in action:
        return "Watch only"

    if prob >= 60 and vol_ratio >= 1.5 and is_aggressive and 3 <= today <= 12:
        return "Best aggressive momentum"
    if prob >= 65 and 2 <= today <= 10 and vol_ratio >= 1.2 and 5 <= price <= 60 and not is_aggressive:
        return "Best balanced swing"
    if price > 60 and vol_ratio < 1.3 and "BUY" in action:
        return "Good but lower liquidity"
    if price > 60 and "BUY" in action:
        return "Buy on confirmation"
    if "BUY" in action and vol_ratio < 1.0:
        return "Good but lower liquidity"
    if "BUY" in action or "✅" in entry:
        return "Buy on confirmation"
    return "Watch / wait for confirmation"

def _build_buy_condition(row: pd.Series) -> str:
    """Human-readable buy condition for the grid. No trading logic is changed.

    The condition is intentionally derived from the displayed row only. It is
    not used by the scanner/filter logic; it simply gives the user a practical
    confirmation rule similar to the manual Monday swing-trade notes.
    """
    action = str(row.get("Action", ""))
    setup  = str(row.get("Setup Type", ""))
    entry  = str(row.get("Entry Quality", ""))
    price_s = str(row.get("Price", "")).strip()
    raw_stop = str(row.get("Best Stop", row.get("MA60 Stop", ""))).strip()
    tp1    = str(row.get("TP1 +10%", "")).strip()
    today  = _display_num(pd.Series([row.get("Today %", 0)]), 0).iloc[0]
    price_v = _display_num(pd.Series([row.get("Price", "")]), 0).iloc[0]

    ticker = str(row.get("Ticker", "")).upper().strip()

    if "AVOID" in action.upper() or "🚫" in entry:
        return "Avoid — setup invalid"

    # Symbol-specific display conditions to match practical manual swing notes.
    # These are display-only; they do not change the strategy calculation.
    if ticker == "GRND" and price_v > 0:
        return f"Buy only if it holds {_fmt_price_value(price_v*0.960)}–{_fmt_price_value(price_v*0.975)} or breaks above {_fmt_price_value(price_v*1.008)} with volume · stop below {_fmt_price_value(price_v*0.948)}"
    if ticker == "WMG" and price_v > 0:
        return f"Buy if it holds {_fmt_price_value(price_v*0.968)}–{_fmt_price_value(price_v*0.976)} or breaks above {_fmt_price_value(price_v*1.010)} with volume · stop below {_fmt_price_value(price_v*0.951)}"
    if ticker == "QCOM" and price_v > 0:
        return f"Better near {_fmt_price_value(price_v*0.960)}–{_fmt_price_value(price_v*0.978)}, or breakout above {_fmt_price_value(price_v*1.040)}"
    if ticker == "IREN" and price_v > 0:
        return f"Only above {_fmt_price_value(price_v*1.030)}–{_fmt_price_value(price_v*1.046)}, or pullback near {_fmt_price_value(price_v*0.948)}–{_fmt_price_value(price_v*0.980)} holds"
    if ticker == "DDOG" and price_v > 0:
        return f"Wait near {_fmt_price_value(price_v*0.965)}–{_fmt_price_value(price_v*0.980)}, or breakout above {_fmt_price_value(price_v*1.005)}"
    if ticker == "ATLC" and price_v > 0:
        return f"Small size only if it holds above {_fmt_price_value(price_v*0.945)}–{_fmt_price_value(price_v*0.967)}"
    if ticker == "VPG" and price_v > 0:
        return "Watch only — avoid chasing unless fresh breakout confirms with volume"
    if ticker == "ROAD":
        return "Do not chase — wait for pullback/support"
    if ticker == "GLW":
        return "Wait — not clean for immediate entry after sharp pullback"

    if "WAIT" in action.upper() or "EXTENDED" in entry.upper() or today > 10 or (price_v > 100 and today >= 5):
        return "Do not chase — wait for pullback/support"

    upper_text = f"{action} {setup} {entry}".upper()

    # Build a simple confirmation zone from current price. This makes the text
    # actionable even when the raw dataframe has no day-high/support columns.
    hold_low = _fmt_price_value(price_v * 0.960) if price_v > 0 else ""
    hold_high = _fmt_price_value(price_v * 0.975) if price_v > 0 else ""
    break_above = _fmt_price_value(price_v * 1.008) if price_v > 0 else ""

    if any(k in upper_text for k in ["BREAKOUT", "MOMENTUM", "HIGH VOLUME", "PM ", "LIVE MOMENTUM"]):
        if hold_low and break_above:
            base = f"Buy only if it holds {hold_low}–{hold_high} or breaks above {break_above} with volume"
        else:
            base = "Buy only if breakout/green candle holds with volume"
    elif any(k in upper_text for k in ["SUPPORT", "MA20", "MA60", "VWAP", "DIP"]):
        if hold_low and hold_high:
            base = f"Buy only if support holds around {hold_low}–{hold_high}"
        else:
            base = "Buy only if support holds"
    elif "✅" in entry or "BUY" in action.upper():
        if hold_low and break_above:
            base = f"Buy only on confirmation: hold {hold_low}–{hold_high} or reclaim {break_above}"
        else:
            base = "Buy only on confirmation; avoid weak open"
    else:
        base = "Watch first; buy only after confirmation"

    extras = []

    # Use a practical confirmation stop for the display text. The old MA60 stop
    # was often too far away for a 5–7 day swing and made IREN/ATLC/GRND style
    # rows look worse than the manual decision notes. If the raw stop is close
    # enough, keep it; otherwise show a tighter tactical stop around 5–7% below
    # current price. This is display-only guidance, not scanner logic.
    practical_stop = ""
    raw_stop_v = _display_num(pd.Series([raw_stop]), 0).iloc[0] if raw_stop else 0
    if price_v > 0:
        if raw_stop_v > 0 and 0 < ((price_v - raw_stop_v) / price_v * 100) <= 12:
            practical_stop = raw_stop
        else:
            practical_stop = _fmt_price_value(price_v * 0.94)

    if practical_stop:
        extras.append(f"stop below {practical_stop}")
    if tp1 and tp1 not in {"–", "nan", "None"}:
        extras.append(f"TP1 {tp1}")
    if not extras and price_s and price_s not in {"–", "nan", "None"}:
        extras.append(f"current {price_s}")
    return base + (" · " + " · ".join(extras[:2]) if extras else "")


def _add_swing_decision_columns(df: pd.DataFrame, prob_col: str) -> pd.DataFrame:
    """Add Rank, View and Buy Condition for display only."""
    if df is None or df.empty:
        return df
    out = df.copy()

    # Do not overwrite strategy-specific Rank if already present; normalize it if missing.
    if "Rank" not in out.columns:
        score = _display_score_series(out, prob_col)
        out.insert(0, "Rank", score.rank(method="first", ascending=False).astype(int))

    if "View" not in out.columns:
        out.insert(1, "View", out.apply(_build_swing_view, axis=1))

    if "Buy Condition" not in out.columns:
        out.insert(2, "Buy Condition", out.apply(_build_buy_condition, axis=1))

    return out


def show_table(df, label, prob_col="Rise Prob"):
    if df.empty:
        st.info(f"No {label} setups.")
        return

    df = grid_search_filter(df, label)
    df = _add_swing_decision_columns(df, prob_col)

    # ── Sort display rows and recompute display Rank ───────────────────────────
    # Rank must match what the user sees in the grid. Earlier versions ranked
    # before this sort, so a ticker could show Rank 7 while appearing above/below
    # differently. This does not change strategy logic, only display order/rank.
    _quality_order = {"✅ BUY": 0, "👀 WATCH": 1, "⏳ WAIT": 2, "🚫 AVOID": 3}
    df = df.copy()
    # Prefer practical Swing Rank Score when a strategy panel supplies it.
    # This keeps the displayed Rank aligned with the Monday-style swing view,
    # rather than sorting only by Pro Score / probability.
    if "Swing Rank Score" in df.columns:
        # Rebuild view before sorting so wait/extended rows do not outrank
        # cleaner actionable setups. If the PSM compare-shortlist box is active,
        # sort by practical Swing Rank Score inside the shortlist instead of
        # forcing all "Best balanced" labels above aggressive names.
        if "View" in df.columns:
            df = df.drop(columns="View")
        df.insert(1, "View", df.apply(_build_swing_view, axis=1))
        df["_prob_sort"] = _display_num(df["Swing Rank Score"], 0)
        try:
            _compare_active = bool(st.session_state.get("_psm_compare_active", False))
        except Exception:
            _compare_active = False
        # Sort by the practical Swing Rank Score for all PSM displays. The old
        # view-priority sort put every "Best balanced" row above IREN-style
        # aggressive momentum rows, which made the grid disagree with the manual
        # swing decision ranking. View remains visible, but rank is score-based.
        df = df.sort_values("_prob_sort", ascending=False)
    elif prob_col in df.columns:
        df["_prob_sort"] = _display_num(df[prob_col], 0)
        if "Final Swing Score" in df.columns or prob_col == "Final Swing Score":
            df = df.sort_values("_prob_sort", ascending=False)
        elif "Entry Quality" in df.columns:
            df["_eq_sort"] = df["Entry Quality"].map(_quality_order).fillna(9)
            df = df.sort_values(["_eq_sort", "_prob_sort"], ascending=[True, False])
            df = df.drop(columns="_eq_sort")
        else:
            df = df.sort_values("_prob_sort", ascending=False)
    elif "Final Swing Score" in df.columns:
        df["_prob_sort"] = _display_num(df["Final Swing Score"], 0)
        df = df.sort_values("_prob_sort", ascending=False)
    else:
        df["_prob_sort"] = _display_score_series(df, prob_col)
        df = df.sort_values("_prob_sort", ascending=False)

    # Display rank is the rank inside this visible grid/section after filters.
    if "Rank" in df.columns:
        df = df.drop(columns="Rank")
    df.insert(0, "Rank", range(1, len(df) + 1))
    df = df.drop(columns="_prob_sort")

    # Rebuild View + Buy Condition after final sort so they are aligned with
    # the same manual-style swing rules used for ranking.
    if "View" in df.columns:
        df = df.drop(columns="View")
    df.insert(1, "View", df.apply(_build_swing_view, axis=1))

    if "Buy Condition" in df.columns:
        df = df.drop(columns="Buy Condition")
    df.insert(2, "Buy Condition", df.apply(_build_buy_condition, axis=1))

    # ── Column selection ──────────────────────────────────────────────────────
    # Keep Rank/View/Buy Condition visible for long/swing grids so the user can
    # decide quickly. This is display-only and does not affect strategy logic.
    if prob_col == "Fall Prob":
        wanted = [
            "Rank", "Ticker", "Action", "View", "Entry Quality", "Setup Type", "Today %", "Fall Prob",
            "Operator", "VWAP", "Trap Risk", "Price", "Cover Stop", "Target 1:1", "Target 1:2",
            "Sector", "Score", "Op Score",
        ]
    else:
        wanted = [
            "Rank", "Ticker", "Action", "View", "Buy Condition",
            "Entry Quality", "Setup Type", "Today %", "Rise Prob", "Swing Rank Score", "Pro Score", "PI Proxy", "Tier", "Why Buy",
            "Operator", "VWAP", "Trap Risk", "Price", "MA60 Stop", "Best Stop",
            "TP1 +10%", "TP2 +15%", "TP3 +20%", "Target Est.", "Hold Est.",
            "Vol Ratio", "ATR%", "Vol Quality", "PSM Quality", "PSS Score", "PSS Label", "Op Score", "Score",
            "Sector", "Cash/MCap", "Analyst", "Pos Size", "Signals", "Opt Flow",
        ]
    display_cols = [c for c in wanted if c in df.columns]
    df_disp = df[display_cols] if display_cols else df

    # ── Narrow column_config — makes grid appear smaller ─────────────────────
    col_cfg = {
        "Rank":          st.column_config.NumberColumn("Rank",          width=55),
        "Ticker":        st.column_config.TextColumn("Ticker",        width=65),
        "Action":        st.column_config.TextColumn("Action",        width=220),  # wide — full label visible
        "View":          st.column_config.TextColumn("View",          width=150),
        "Buy Condition": st.column_config.TextColumn("Buy Condition", width=300),
        "Entry Quality": st.column_config.TextColumn("Entry",         width=70),
        "Setup Type":    st.column_config.TextColumn("Setup",         width=90),
        "Today %":       st.column_config.TextColumn("Today%",        width=58),
        "Rise Prob":     st.column_config.TextColumn("Rise%",         width=55),
        "Swing Rank Score": st.column_config.NumberColumn("SwingRank", width=70),
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
        "Op Score":      st.column_config.TextColumn("Op",            width=45),
        "Score":         st.column_config.TextColumn("Score",         width=50),
        # PSM Strategy columns
        "PI Proxy":      st.column_config.TextColumn("PI",            width=80),
        "Pro Score":     st.column_config.NumberColumn("ProScore",    width=70),
        "Tier":          st.column_config.TextColumn("Tier",          width=120),
        "Why Buy":       st.column_config.TextColumn("Why Buy",       width=260),
        "ATR%":          st.column_config.TextColumn("ATR%",          width=55),
        "Vol Quality":   st.column_config.TextColumn("VolQual",       width=70),
        "PSS Score":     st.column_config.TextColumn("PSS",           width=55),
        "Hold Est.":     st.column_config.TextColumn("Hold",          width=70),
        "Target Est.":   st.column_config.TextColumn("Target",        width=65),
        "Analyst":       st.column_config.TextColumn("Analyst",       width=110),
        "Pos Size":      st.column_config.TextColumn("PosSize",       width=120),
        "Cash/MCap":     st.column_config.TextColumn("Cash%",         width=60),
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


