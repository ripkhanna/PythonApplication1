"""Strategy Finder helpers.

This module is executed into app_runtime.py globals, matching the existing
core_runtime pattern. It compares rule-based strategy templates against the
same target-before-stop label used by Accuracy Lab.
"""


STRATEGY_FINDER_NAMES = [
    "Discovery",
    "Balanced",
    "Strict",
    "High Conviction",
    "Support Entry",
    "Pullback Volume Dry-Up",
    "High Volume",
    "Momentum Runner",
    "Operator Accumulation",
    "PSM Proxy",
    "Early Breakout",
]


def _sf_float(value, default=0.0):
    try:
        if value is None:
            return float(default)
        if isinstance(value, str):
            value = (
                value.replace("%", "")
                .replace("x", "")
                .replace("$", "")
                .replace(",", "")
                .replace("+", "")
                .strip()
            )
            if value in ("", "-", "--", "nan", "None"):
                return float(default)
        out = float(value)
        if np.isnan(out) or np.isinf(out):
            return float(default)
        return out
    except Exception:
        return float(default)


def _sf_bool(value):
    try:
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "y")
        return bool(value)
    except Exception:
        return False


def _sf_flatten_ohlcv(raw_df):
    try:
        df = raw_df.copy()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        needed = ["Open", "High", "Low", "Close", "Volume"]
        for col in needed:
            if col not in df.columns:
                df[col] = np.nan
        return df[needed].replace([np.inf, -np.inf], np.nan).ffill().dropna()
    except Exception:
        return pd.DataFrame()


def _sf_first_hit_label(future_high, future_low, entry, tp_pct=6.0, sl_pct=4.0):
    """Return 1 when target is hit before stop; same-day tie is stop first."""
    entry = _sf_float(entry, 0.0)
    if entry <= 0:
        return 0, 0.0, 0.0, "bad_entry"
    target = entry * (1.0 + _sf_float(tp_pct, 6.0) / 100.0)
    stop = entry * (1.0 - _sf_float(sl_pct, 4.0) / 100.0)
    max_gain = 0.0
    max_dd = 0.0
    for hi, lo in zip(future_high, future_low):
        hi = _sf_float(hi, np.nan)
        lo = _sf_float(lo, np.nan)
        if np.isnan(hi) or np.isnan(lo):
            continue
        max_gain = max(max_gain, (hi / entry - 1.0) * 100.0)
        max_dd = min(max_dd, (lo / entry - 1.0) * 100.0)
        hit_stop = lo <= stop
        hit_target = hi >= target
        if hit_stop and hit_target:
            return 0, max_gain, max_dd, "same_day_stop_first"
        if hit_stop:
            return 0, max_gain, max_dd, "stop_first"
        if hit_target:
            return 1, max_gain, max_dd, "target_first"
    return 0, max_gain, max_dd, "no_target"


def _sf_path_first_hit_label(high_pct_seq, low_pct_seq, horizon=10, tp_pct=6.0, sl_pct=4.0):
    """Label from stored future high/low percentage paths."""
    try:
        highs = list(high_pct_seq or [])[:int(horizon)]
        lows = list(low_pct_seq or [])[:int(horizon)]
    except Exception:
        return 0, 0.0, 0.0, "bad_path"
    max_gain = 0.0
    max_dd = 0.0
    for hi, lo in zip(highs, lows):
        hi = _sf_float(hi, np.nan)
        lo = _sf_float(lo, np.nan)
        if np.isnan(hi) or np.isnan(lo):
            continue
        max_gain = max(max_gain, hi)
        max_dd = min(max_dd, lo)
        hit_stop = lo <= -_sf_float(sl_pct, 4.0)
        hit_target = hi >= _sf_float(tp_pct, 6.0)
        if hit_stop and hit_target:
            return 0, max_gain, max_dd, "same_day_stop_first"
        if hit_stop:
            return 0, max_gain, max_dd, "stop_first"
        if hit_target:
            return 1, max_gain, max_dd, "target_first"
    return 0, max_gain, max_dd, "no_target"


def _sf_bucket_counts(long_sig):
    counts = {}
    buckets = globals().get("SIGNAL_BUCKETS", {}) or {}
    try:
        for key, active in dict(long_sig or {}).items():
            if active:
                bucket = buckets.get(key, "other")
                counts[bucket] = counts.get(bucket, 0) + 1
    except Exception:
        pass
    return counts


def _sf_feature_row(long_sig, raw):
    raw = raw or {}
    counts = _sf_bucket_counts(long_sig)
    p = _sf_float(raw.get("p"), 0.0)
    ma20 = _sf_float(raw.get("ma20"), p or 1.0)
    ma60 = _sf_float(raw.get("ma60"), p or 1.0)
    vwap = _sf_float(raw.get("vwap"), p or 1.0)
    atr = _sf_float(raw.get("atr"), 0.0)
    atr_pct = _sf_float(raw.get("atr_pct"), (atr / p * 100.0) if p else 0.0)
    trend = int(counts.get("trend", 0))
    momentum = int(counts.get("momentum", 0))
    volume = int(counts.get("volume", 0))
    structure = int(counts.get("structure", 0))
    relative = int(counts.get("relative", 0))
    volatility = int(counts.get("volatility", 0))
    options = int(counts.get("options", 0))
    category_count = int(sum(1 for x in [trend, momentum, volume, structure, relative, volatility, options] if x > 0))
    trap_risk = bool(raw.get("false_breakout") or raw.get("gap_chase_risk") or raw.get("operator_distribution"))
    bayes_prob = 0.0
    try:
        bayes_prob = float(bayesian_prob(LONG_WEIGHTS, long_sig, 0.0) * 100.0)
    except Exception:
        bayes_prob = 0.0
    return {
        "BayesProb": round(bayes_prob, 4),
        "SignalCount": int(sum(1 for v in dict(long_sig or {}).values() if v)),
        "TrendCount": trend,
        "MomentumCount": momentum,
        "VolumeCount": volume,
        "StructureCount": structure,
        "RelativeCount": relative,
        "VolatilityCount": volatility,
        "OptionsCount": options,
        "CategoryCount": category_count,
        "OperatorScore": _sf_float(raw.get("operator_score"), 0.0),
        "VolumeRatio": _sf_float(raw.get("vr"), 0.0),
        "TodayPct": _sf_float(raw.get("today_chg_pct"), 0.0),
        "RSI": _sf_float(raw.get("rsi0"), 50.0),
        "ADX": _sf_float(raw.get("adx"), 0.0),
        "ATRpct": round(atr_pct, 4),
        "PriceVsMA20Pct": round(((p / ma20) - 1.0) * 100.0, 4) if ma20 else 0.0,
        "PriceVsMA60Pct": round(((p / ma60) - 1.0) * 100.0, 4) if ma60 else 0.0,
        "PriceVsVWAPPct": round(((p / vwap) - 1.0) * 100.0, 4) if vwap else 0.0,
        "AboveVWAP": 1 if raw.get("above_vwap") else 0,
        "AboveMA60": 1 if raw.get("above_ma60") else 0,
        "DipToMA20": 1 if raw.get("dip_to_ma20") else 0,
        "DipToMA60": 1 if raw.get("dip_to_ma60") else 0,
        "VWAPSupport": 1 if raw.get("vwap_support") else 0,
        "VolumeSignal": 1 if (long_sig or {}).get("vol_breakout") or (long_sig or {}).get("pocket_pivot") or (long_sig or {}).get("volume") else 0,
        "StrongClose": 1 if (long_sig or {}).get("strong_close") else 0,
        "TrapRisk": 1 if trap_risk else 0,
        "FalseBreakout": 1 if raw.get("false_breakout") else 0,
        "GapChaseRisk": 1 if raw.get("gap_chase_risk") else 0,
        "DistributionRisk": 1 if raw.get("operator_distribution") else 0,
    }


def _sf_strategy_hits(feature):
    p = _sf_float(feature.get("BayesProb"), 0.0)
    score = _sf_float(feature.get("SignalCount"), 0.0)
    categories = _sf_float(feature.get("CategoryCount"), 0.0)
    trend = _sf_float(feature.get("TrendCount"), 0.0)
    momentum = _sf_float(feature.get("MomentumCount"), 0.0)
    volume = _sf_float(feature.get("VolumeCount"), 0.0)
    structure = _sf_float(feature.get("StructureCount"), 0.0)
    relative = _sf_float(feature.get("RelativeCount"), 0.0)
    op = _sf_float(feature.get("OperatorScore"), 0.0)
    vr = _sf_float(feature.get("VolumeRatio"), 0.0)
    today = _sf_float(feature.get("TodayPct"), 0.0)
    atr_pct = _sf_float(feature.get("ATRpct"), 0.0)
    vs_ma20 = _sf_float(feature.get("PriceVsMA20Pct"), 0.0)
    vs_ma60 = _sf_float(feature.get("PriceVsMA60Pct"), 0.0)
    vs_vwap = _sf_float(feature.get("PriceVsVWAPPct"), 0.0)
    above_ma60 = _sf_bool(feature.get("AboveMA60"))
    trap = _sf_bool(feature.get("TrapRisk"))
    dip_ma20 = _sf_bool(feature.get("DipToMA20"))
    dip_ma60 = _sf_bool(feature.get("DipToMA60"))
    vwap_support = _sf_bool(feature.get("VWAPSupport"))
    vol_signal = _sf_bool(feature.get("VolumeSignal"))
    near_support = bool(above_ma60 and (
        dip_ma20 or dip_ma60 or vwap_support
        or abs(vs_ma20) <= 2.5
        or abs(vs_ma60) <= 3.5
        or abs(vs_vwap) <= 2.0
    ))
    not_extended = today <= 8.0
    not_broken = today >= -6.0
    clean = not trap
    return {
        "Discovery": bool(p >= 50 and score >= 3),
        "Balanced": bool(p >= 58 and score >= 4 and categories >= 2 and not_extended and clean),
        "Strict": bool(p >= 76 and score >= 7 and categories >= 3 and (volume > 0 or vol_signal) and clean),
        "High Conviction": bool(p >= 65 and score >= 6 and categories >= 4 and trend > 0 and momentum > 0 and clean),
        "Support Entry": bool(p >= 55 and near_support and today <= 6.0 and clean),
        "Pullback Volume Dry-Up": bool(p >= 52 and near_support and vr < 1.0 and -4.0 <= today <= 3.5 and clean),
        "High Volume": bool(p >= 55 and score >= 3 and (vr >= 1.5 or vol_signal) and today <= 10.0),
        "Momentum Runner": bool(p >= 58 and score >= 4 and momentum > 0 and 0.0 <= today <= 8.0 and clean),
        "Operator Accumulation": bool(p >= 55 and op >= 4 and today <= 8.0 and clean),
        "PSM Proxy": bool(p >= 60 and score >= 5 and 2.0 <= atr_pct <= 14.0 and vr >= 0.9 and not_broken and today <= 12.0 and categories >= 3 and clean),
        "Early Breakout": bool(p >= 62 and score >= 5 and (volume > 0 or vol_signal or vr >= 1.4) and structure > 0 and today <= 8.0 and clean),
    }


def _sf_sample_feature_cache(samples):
    idx = samples.index
    def _num(col, default=0):
        if col not in samples.columns:
            return pd.Series([default] * len(samples), index=idx)
        return pd.to_numeric(samples[col], errors="coerce").fillna(default)
    return {
        "idx": idx,
        "p": _num("BayesProb"),
        "score": _num("SignalCount"),
        "categories": _num("CategoryCount"),
        "trend": _num("TrendCount"),
        "momentum": _num("MomentumCount"),
        "volume": _num("VolumeCount"),
        "relative": _num("RelativeCount"),
        "op": _num("OperatorScore"),
        "vr": _num("VolumeRatio"),
        "today": _num("TodayPct"),
        "atr": _num("ATRpct"),
        "ma20": _num("PriceVsMA20Pct"),
        "ma60": _num("PriceVsMA60Pct"),
        "vwap": _num("PriceVsVWAPPct"),
        "above_ma60": _num("AboveMA60").astype(bool),
        "trap": _num("TrapRisk").astype(bool),
        "dip_ma20": _num("DipToMA20").astype(bool),
        "dip_ma60": _num("DipToMA60").astype(bool),
        "vwap_support": _num("VWAPSupport").astype(bool),
        "vol_signal": _num("VolumeSignal").astype(bool),
        "strong_close": _num("StrongClose").astype(bool),
    }


def _sf_sample_mask_from_spec(samples, spec, cache=None):
    cache = cache or _sf_sample_feature_cache(samples)
    idx = cache["idx"]
    p = cache["p"]
    score = cache["score"]
    categories = cache["categories"]
    trend = cache["trend"]
    momentum = cache["momentum"]
    volume = cache["volume"]
    relative = cache["relative"]
    op = cache["op"]
    vr = cache["vr"]
    today = cache["today"]
    atr = cache["atr"]
    ma20 = cache["ma20"]
    ma60 = cache["ma60"]
    vwap = cache["vwap"]
    above_ma60 = cache["above_ma60"]
    trap = cache["trap"]
    dip_ma20 = cache["dip_ma20"]
    dip_ma60 = cache["dip_ma60"]
    vwap_support = cache["vwap_support"]
    vol_signal = cache["vol_signal"]
    strong_close = cache["strong_close"]

    near_support = above_ma60 & (
        dip_ma20 | dip_ma60 | vwap_support
        | (ma20.abs() <= _sf_float(spec.get("support_ma20_pct"), 2.0))
        | (ma60.abs() <= _sf_float(spec.get("support_ma60_pct"), 3.0))
        | (vwap.abs() <= _sf_float(spec.get("support_vwap_pct"), 1.5))
    )
    volume_ok = vol_signal | (volume >= 1) | (vr >= _sf_float(spec.get("volume_fallback_vr"), 1.4))

    mask = pd.Series([True] * len(samples), index=idx)
    mask &= p >= _sf_float(spec.get("p_min"), 0)
    mask &= score >= _sf_float(spec.get("score_min"), 0)
    mask &= categories >= _sf_float(spec.get("cat_min"), 0)
    mask &= op >= _sf_float(spec.get("op_min"), 0)
    mask &= vr >= _sf_float(spec.get("vr_min"), 0)
    mask &= vr <= _sf_float(spec.get("vr_max"), 999)
    mask &= today >= _sf_float(spec.get("today_min"), -999)
    mask &= today <= _sf_float(spec.get("today_max"), 999)
    mask &= atr >= _sf_float(spec.get("atr_min"), 0)
    mask &= atr <= _sf_float(spec.get("atr_max"), 999)
    if spec.get("exclude_trap", True):
        mask &= ~trap
    if spec.get("above_ma60", True):
        mask &= above_ma60
    if spec.get("req_support", False):
        mask &= near_support
    if spec.get("req_volume", False):
        mask &= volume_ok
    if spec.get("req_strong_close", False):
        mask &= strong_close
    if spec.get("req_trend", False):
        mask &= trend >= 1
    if spec.get("req_momentum", False):
        mask &= momentum >= 1
    if spec.get("req_relative", False):
        mask &= relative >= 1
    return mask.fillna(False)


def _sf_strategy_metrics(d, name, base_rate, tp_pct, sl_pct, min_trades, min_win_pct, spec=None):
    trades = int(len(d))
    if trades <= 0:
        return None
    win_rate = float(d["Target"].mean() * 100.0)
    avg_gain = float(pd.to_numeric(d["MaxGain%"], errors="coerce").fillna(0.0).mean())
    avg_dd = float(pd.to_numeric(d["MaxDD%"], errors="coerce").fillna(0.0).mean())
    med_gain = float(pd.to_numeric(d["MaxGain%"], errors="coerce").fillna(0.0).median())
    ticker_count = int(d["Ticker"].nunique()) if "Ticker" in d.columns else 0
    expectancy = (win_rate / 100.0) * _sf_float(tp_pct, 6.0) - (1.0 - win_rate / 100.0) * _sf_float(sl_pct, 4.0)
    pi = (win_rate / 100.0) * avg_gain
    edge = win_rate - base_rate
    meets_target = bool(trades >= int(min_trades) and win_rate >= float(min_win_pct))
    finder_score = (
        (win_rate - float(min_win_pct)) * 0.70
        + edge * 0.20
        + expectancy * 1.20
        + pi * 0.90
        + min(trades, 80) * 0.025
    )
    if trades < int(min_trades):
        verdict = "Needs samples"
    elif win_rate < float(min_win_pct):
        verdict = f"Below {float(min_win_pct):.0f}%"
    elif expectancy <= 0:
        verdict = "Win ok, payoff weak"
    elif pi >= 3.0:
        verdict = "Qualified 70%+"
    else:
        verdict = "Qualified, verify"
    return {
        "Strategy": name,
        "Verdict": verdict,
        "Meets Target": "YES" if meets_target else "NO",
        "Trades": trades,
        "Tickers": ticker_count,
        "Win %": round(win_rate, 1),
        "Target Win %": round(float(min_win_pct), 1),
        "Base Win %": round(base_rate, 1),
        "Edge %": round(edge, 1),
        "Expectancy %": round(expectancy, 2),
        "PI": round(pi, 2),
        "Avg MaxGain %": round(avg_gain, 2),
        "Median MaxGain %": round(med_gain, 2),
        "Avg MaxDD %": round(avg_dd, 2),
        "Finder Score": round(finder_score, 2),
        "_spec": spec or {},
    }


def _sf_precision_name(spec):
    return (
        f"HP{int(_sf_float(spec.get('target_win_pct'), 70))} "
        f"{spec.get('profile', 'Precision')} "
        f"P{int(_sf_float(spec.get('p_min'), 0))} "
        f"S{int(_sf_float(spec.get('score_min'), 0))} "
        f"C{int(_sf_float(spec.get('cat_min'), 0))} "
        f"Op{int(_sf_float(spec.get('op_min'), 0))}"
    )


def _strategy_finder_add_precision_strategies(samples, min_trades=8, min_win_pct=70.0, tp_pct=6.0, sl_pct=4.0, max_variants=12):
    """Add generated high-precision strategy columns that try to clear min_win_pct."""
    if samples is None or samples.empty:
        return samples, {}
    out = samples.copy()
    base_rate = float(out["Target"].mean() * 100.0) if "Target" in out.columns and len(out) else 0.0
    cache = _sf_sample_feature_cache(out)
    profiles = [
        {
            "profile": "EliteConfluence", "req_trend": True, "req_momentum": True,
            "req_volume": True, "above_ma60": True, "exclude_trap": True,
            "p_grid": [70, 75, 80, 85], "score_grid": [6, 7, 8],
            "cat_grid": [3, 4], "op_grid": [2, 4],
            "vr_grid": [0.8, 1.2], "today_grid": [(-2, 5), (0, 5)],
            "atr_grid": [(2, 10), (2, 8)],
        },
        {
            "profile": "SupportAPlus", "req_support": True, "above_ma60": True,
            "exclude_trap": True, "p_grid": [65, 70, 75, 80],
            "score_grid": [5, 6, 7], "cat_grid": [2, 3],
            "op_grid": [0, 2, 4], "vr_grid": [0.0, 0.8],
            "today_grid": [(-4, 3), (-2, 3)], "atr_grid": [(1.5, 8), (2, 8)],
        },
        {
            "profile": "BreakoutAPlus", "req_volume": True, "req_strong_close": True,
            "req_trend": True, "exclude_trap": True, "above_ma60": True,
            "p_grid": [70, 75, 80, 85], "score_grid": [6, 7, 8],
            "cat_grid": [3, 4], "op_grid": [2, 4],
            "vr_grid": [1.2, 1.5], "today_grid": [(0, 5), (0, 6)],
            "atr_grid": [(2, 10), (3, 10)],
        },
        {
            "profile": "OperatorAPlus", "req_volume": True, "exclude_trap": True,
            "above_ma60": True, "p_grid": [65, 70, 75, 80],
            "score_grid": [5, 6, 7], "cat_grid": [2, 3],
            "op_grid": [4, 6], "vr_grid": [1.0, 1.2],
            "today_grid": [(-1, 5), (0, 6)], "atr_grid": [(2, 10), (2, 8)],
        },
        {
            "profile": "PSMAPlus", "req_trend": True, "req_momentum": True,
            "exclude_trap": True, "above_ma60": True, "p_grid": [70, 75, 80, 85],
            "score_grid": [6, 7, 8], "cat_grid": [3, 4],
            "op_grid": [2, 4], "vr_grid": [0.8, 1.2],
            "today_grid": [(-2, 6), (0, 6)], "atr_grid": [(2, 10), (3, 10)],
        },
    ]
    candidates = []
    seen_masks = set()
    for profile in profiles:
        for p_min in profile["p_grid"]:
            for score_min in profile["score_grid"]:
                for cat_min in profile["cat_grid"]:
                    for op_min in profile["op_grid"]:
                        for vr_min in profile["vr_grid"]:
                            for today_min, today_max in profile["today_grid"]:
                                for atr_min, atr_max in profile["atr_grid"]:
                                    spec = {
                                        "profile": profile["profile"],
                                        "target_win_pct": float(min_win_pct),
                                        "p_min": p_min,
                                        "score_min": score_min,
                                        "cat_min": cat_min,
                                        "op_min": op_min,
                                        "vr_min": vr_min,
                                        "vr_max": 8.0,
                                        "today_min": today_min,
                                        "today_max": today_max,
                                        "atr_min": atr_min,
                                        "atr_max": atr_max,
                                        "req_support": profile.get("req_support", False),
                                        "req_volume": profile.get("req_volume", False),
                                        "req_strong_close": profile.get("req_strong_close", False),
                                        "req_trend": profile.get("req_trend", False),
                                        "req_momentum": profile.get("req_momentum", False),
                                        "req_relative": profile.get("req_relative", False),
                                        "above_ma60": profile.get("above_ma60", True),
                                        "exclude_trap": profile.get("exclude_trap", True),
                                    }
                                    mask = _sf_sample_mask_from_spec(out, spec, cache)
                                    trades = int(mask.sum())
                                    if trades < int(min_trades):
                                        continue
                                    mask_key = tuple(np.flatnonzero(mask.to_numpy()).tolist())
                                    if mask_key in seen_masks:
                                        continue
                                    seen_masks.add(mask_key)
                                    metrics = _sf_strategy_metrics(out[mask].copy(), _sf_precision_name(spec), base_rate, tp_pct, sl_pct, min_trades, min_win_pct, spec)
                                    if not metrics:
                                        continue
                                    if metrics["Win %"] < float(min_win_pct):
                                        continue
                                    candidates.append((metrics, mask, spec))
    candidates = sorted(
        candidates,
        key=lambda x: (
            x[0]["Win %"],
            x[0]["Expectancy %"],
            x[0]["PI"],
            min(x[0]["Trades"], 80),
            x[0]["Finder Score"],
        ),
        reverse=True,
    )
    specs = {}
    profile_used = {}
    added = 0
    for metrics, mask, spec in candidates:
        profile_name = spec.get("profile", "Precision")
        profile_used[profile_name] = profile_used.get(profile_name, 0) + 1
        if profile_used[profile_name] > 3:
            continue
        name = metrics["Strategy"]
        base_name = name
        n = 2
        while f"Strategy::{name}" in out.columns:
            name = f"{base_name} #{n}"
            n += 1
        out[f"Strategy::{name}"] = mask.astype(bool)
        spec = dict(spec)
        spec["name"] = name
        specs[name] = spec
        added += 1
        if added >= int(max_variants):
            break
    return out, specs


@st.cache_data(ttl=3600, show_spinner=False)
def _strategy_finder_build_samples(tickers_tuple, period="2y", horizon=10, tp_pct=6.0, sl_pct=4.0, step=3):
    rows = []
    tickers = [str(t).strip().upper() for t in list(tickers_tuple or []) if str(t).strip()]
    for ticker in tickers:
        try:
            raw_df = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=True)
            df = _sf_flatten_ohlcv(raw_df)
            if df.empty or len(df) < 260:
                continue
            close = df["Close"].ffill().dropna()
            high = df["High"].ffill().dropna()
            low = df["Low"].ffill().dropna()
            vol = df["Volume"].ffill().dropna()
            for end in range(220, len(close) - int(horizon), max(1, int(step))):
                try:
                    long_sig, _short_sig, raw = compute_all_signals(
                        close.iloc[:end],
                        high.iloc[:end],
                        low.iloc[:end],
                        vol.iloc[:end],
                    )
                except Exception:
                    continue
                entry = _sf_float(close.iloc[end - 1], 0.0)
                future_high_pct = [
                    round((_sf_float(x, entry) / entry - 1.0) * 100.0, 4)
                    for x in high.iloc[end:end + int(horizon)]
                ] if entry > 0 else []
                future_low_pct = [
                    round((_sf_float(x, entry) / entry - 1.0) * 100.0, 4)
                    for x in low.iloc[end:end + int(horizon)]
                ] if entry > 0 else []
                label, max_gain, max_dd, outcome = _sf_first_hit_label(
                    high.iloc[end:end + int(horizon)],
                    low.iloc[end:end + int(horizon)],
                    entry,
                    tp_pct,
                    sl_pct,
                )
                feature = _sf_feature_row(long_sig, raw)
                hits = _sf_strategy_hits(feature)
                row = {
                    "Ticker": ticker,
                    "Date": str(close.index[end - 1])[:10],
                    "Entry": round(entry, 4),
                    "Target": int(label),
                    "MaxGain%": round(max_gain, 3),
                    "MaxDD%": round(max_dd, 3),
                    "PathOutcome": outcome,
                    "FutureHighPct": future_high_pct,
                    "FutureLowPct": future_low_pct,
                }
                row.update(feature)
                for name, matched in hits.items():
                    row[f"Strategy::{name}"] = bool(matched)
                rows.append(row)
        except Exception:
            continue
    return pd.DataFrame(rows)


def _strategy_finder_rank(samples, min_trades=8, tp_pct=6.0, sl_pct=4.0, min_win_pct=70.0):
    if samples is None or samples.empty:
        return pd.DataFrame()
    out_rows = []
    strategy_cols = [c for c in samples.columns if str(c).startswith("Strategy::")]
    base_rate = float(samples["Target"].mean() * 100.0) if "Target" in samples.columns and len(samples) else 0.0
    for col in strategy_cols:
        name = col.split("Strategy::", 1)[1]
        try:
            d = samples[samples[col].astype(bool)].copy()
        except Exception:
            d = pd.DataFrame()
        trades = int(len(d))
        if trades <= 0:
            continue
        metrics = _sf_strategy_metrics(d, name, base_rate, tp_pct, sl_pct, min_trades, min_win_pct)
        if metrics:
            out_rows.append(metrics)
    if not out_rows:
        return pd.DataFrame()
    ranked = pd.DataFrame(out_rows).drop(columns=["_spec"], errors="ignore")
    ranked["_meets_sort"] = ranked["Meets Target"].astype(str).eq("YES").astype(int)
    ranked = ranked.sort_values(
        ["_meets_sort", "Win %", "Expectancy %", "PI", "Trades", "Finder Score"],
        ascending=[False, False, False, False, False, False],
        kind="stable",
    ).drop(columns=["_meets_sort"], errors="ignore")
    return ranked.reset_index(drop=True)


def _strategy_finder_optimize_exits(samples, min_trades=8, min_win_pct=70.0):
    """Find payoff-aware target/stop/horizon profiles for each strategy family."""
    if samples is None or samples.empty:
        return pd.DataFrame()
    if "FutureHighPct" not in samples.columns or "FutureLowPct" not in samples.columns:
        return pd.DataFrame()
    strategy_cols = [c for c in samples.columns if str(c).startswith("Strategy::")]
    if not strategy_cols:
        return pd.DataFrame()
    target_grid = [2.0, 2.5, 3.0, 4.0, 5.0, 6.0]
    stop_grid = [2.0, 3.0, 4.0, 5.0, 6.0]
    horizon_grid = [5, 7, 10, 15, 20]
    rows = []
    for col in strategy_cols:
        strategy = col.split("Strategy::", 1)[1]
        try:
            d = samples[samples[col].astype(bool)].copy()
        except Exception:
            continue
        if len(d) < int(min_trades):
            continue
        max_path = 0
        try:
            max_path = int(d["FutureHighPct"].map(lambda x: len(x) if isinstance(x, (list, tuple)) else 0).max())
        except Exception:
            max_path = 0
        if max_path <= 0:
            continue
        for horizon in [h for h in horizon_grid if h <= max_path]:
            high_paths = d["FutureHighPct"].tolist()
            low_paths = d["FutureLowPct"].tolist()
            for target_pct in target_grid:
                for stop_pct in stop_grid:
                    labels = []
                    gains = []
                    dds = []
                    for hp, lp in zip(high_paths, low_paths):
                        label, max_gain, max_dd, _outcome = _sf_path_first_hit_label(hp, lp, horizon, target_pct, stop_pct)
                        labels.append(label)
                        gains.append(max_gain)
                        dds.append(max_dd)
                    trades = len(labels)
                    if trades < int(min_trades):
                        continue
                    win_rate = float(np.mean(labels) * 100.0) if labels else 0.0
                    expectancy = (win_rate / 100.0) * target_pct - (1.0 - win_rate / 100.0) * stop_pct
                    avg_gain = float(np.mean(gains)) if gains else 0.0
                    avg_dd = float(np.mean(dds)) if dds else 0.0
                    pi = (win_rate / 100.0) * avg_gain
                    payoff_ratio = target_pct / stop_pct if stop_pct else 0.0
                    meets = bool(win_rate >= float(min_win_pct) and expectancy > 0)
                    if trades >= int(min_trades):
                        rows.append({
                            "Strategy": strategy,
                            "Exit Profile": f"+{target_pct:g}% / -{stop_pct:g}% in {horizon}d",
                            "Meets Target": "YES" if meets else "NO",
                            "Trades": int(trades),
                            "Win %": round(win_rate, 1),
                            "Target Win %": round(float(min_win_pct), 1),
                            "Expectancy %": round(expectancy, 2),
                            "PI": round(pi, 2),
                            "Target %": target_pct,
                            "Stop %": stop_pct,
                            "Horizon": int(horizon),
                            "Payoff": round(payoff_ratio, 2),
                            "Avg MaxGain %": round(avg_gain, 2),
                            "Avg MaxDD %": round(avg_dd, 2),
                        })
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    out["_meets_sort"] = out["Meets Target"].astype(str).eq("YES").astype(int)
    out = out.sort_values(
        ["_meets_sort", "Win %", "Expectancy %", "PI", "Target %", "Trades"],
        ascending=[False, False, False, False, False, False],
        kind="stable",
    ).drop(columns=["_meets_sort"], errors="ignore")
    return out.reset_index(drop=True)


def _strategy_finder_strategy_trades(samples, strategy_name, limit=250):
    if samples is None or samples.empty or not strategy_name:
        return pd.DataFrame()
    col = f"Strategy::{strategy_name}"
    if col not in samples.columns:
        return pd.DataFrame()
    cols = [
        "Ticker", "Date", "Entry", "Target", "MaxGain%", "MaxDD%", "PathOutcome",
        "BayesProb", "SignalCount", "CategoryCount", "OperatorScore", "VolumeRatio",
        "TodayPct", "ATRpct", "PriceVsMA20Pct", "PriceVsMA60Pct", "TrapRisk",
    ]
    cols = [c for c in cols if c in samples.columns]
    out = samples[samples[col].astype(bool)][cols].copy()
    if "Date" in out.columns:
        out = out.sort_values(["Date", "Ticker"], ascending=[False, True], kind="stable")
    return out.head(int(limit))


def _sf_series_num(df, col, default=0.0):
    if col not in df.columns:
        return pd.Series([default] * len(df), index=df.index)
    return pd.to_numeric(
        df[col].astype(str)
        .str.replace("%", "", regex=False)
        .str.replace("x", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.replace("+", "", regex=False)
        .str.extract(r"([-]?\d+(?:\.\d+)?)", expand=False),
        errors="coerce",
    ).fillna(default)


def _sf_scan_mask_from_spec(df, spec):
    idx = df.index
    p = _sf_series_num(df, "Rise Prob", 0.0)
    score = _sf_series_num(df, "Score", 0.0)
    nds = _sf_series_num(df, "Next-Day Score", 0.0)
    qs = _sf_series_num(df, "Quality Score", 0.0)
    if not qs.gt(0).any():
        qs = nds.copy()
    vr = _sf_series_num(df, "Vol Ratio", 0.0)
    today = _sf_series_num(df, "Today %", 0.0)
    op = _sf_series_num(df, "Op Score", 0.0)
    if not op.gt(0).any():
        op = _sf_series_num(df, "Operator Score", 0.0)
    atr = _sf_series_num(df, "ATR%", 0.0)
    supp_num = _sf_series_num(df, "Supp#", 0.0)
    signals = df["Signals"].astype(str) if "Signals" in df.columns else pd.Series([""] * len(df), index=idx)
    support_text = df["Support Tier"].astype(str) if "Support Tier" in df.columns else pd.Series([""] * len(df), index=idx)
    trap_text = df["Trap Risk"].astype(str) if "Trap Risk" in df.columns else pd.Series([""] * len(df), index=idx)
    action_text = df["Action"].astype(str) if "Action" in df.columns else pd.Series([""] * len(df), index=idx)
    trend = signals.str.contains("WKLY TREND|RS>SPY|52W HIGH|GC|MA", na=False, regex=True)
    momentum = signals.str.contains("STOCH|MACD|RSI|MOMENTUM|HIGHER LOWS", na=False, regex=True)
    volume = signals.str.contains("VOL|POCKET PIVOT|OBV|OPERATOR|ACCUM", na=False, regex=True)
    relative = signals.str.contains("RS>|REL|SECTOR", na=False, regex=True)
    structure = signals.str.contains("VWAP|SUPPORT|CLOSE|CANDLE|BREAKOUT|BASE", na=False, regex=True)
    categories = trend.astype(int) + momentum.astype(int) + volume.astype(int) + structure.astype(int) + relative.astype(int)
    trap = trap_text.str.upper().str.contains("FALSE|GAP|DISTRIB|TRAP", na=False) | action_text.str.upper().str.contains("TRAP", na=False)
    support = (supp_num > 0) | support_text.str.upper().str.contains("MA20|MA60|VWAP|SUPPORT", na=False)
    vol_signal = (vr >= _sf_float(spec.get("volume_fallback_vr"), 1.4)) | volume

    mask = pd.Series([True] * len(df), index=idx)
    mask &= p >= _sf_float(spec.get("p_min"), 0)
    mask &= score >= _sf_float(spec.get("score_min"), 0)
    mask &= categories >= _sf_float(spec.get("cat_min"), 0)
    mask &= op >= _sf_float(spec.get("op_min"), 0)
    mask &= vr >= _sf_float(spec.get("vr_min"), 0)
    mask &= vr <= _sf_float(spec.get("vr_max"), 999)
    mask &= today >= _sf_float(spec.get("today_min"), -999)
    mask &= today <= _sf_float(spec.get("today_max"), 999)
    mask &= atr >= _sf_float(spec.get("atr_min"), 0)
    mask &= atr <= _sf_float(spec.get("atr_max"), 999)
    if spec.get("exclude_trap", True):
        mask &= ~trap
    if spec.get("req_support", False):
        mask &= support
    if spec.get("req_volume", False):
        mask &= vol_signal
    if spec.get("req_trend", False):
        mask &= trend
    if spec.get("req_momentum", False):
        mask &= momentum
    if spec.get("req_relative", False):
        mask &= relative
    if spec.get("req_strong_close", False):
        mask &= signals.str.contains("STRONG CLOSE|CLOSE", na=False, regex=True)
    return mask.fillna(False)


def _strategy_finder_apply_to_scan(df_scan, strategy_name, precision_specs=None):
    """Approximate a finder strategy against the latest cached scan dataframe."""
    if df_scan is None or df_scan.empty or not strategy_name:
        return pd.DataFrame()
    df = df_scan.copy()
    idx = df.index
    p = _sf_series_num(df, "Rise Prob", 0.0)
    score = _sf_series_num(df, "Score", 0.0)
    nds = _sf_series_num(df, "Next-Day Score", 0.0)
    qs = _sf_series_num(df, "Quality Score", 0.0)
    if not qs.gt(0).any():
        qs = nds.copy()
    vr = _sf_series_num(df, "Vol Ratio", 0.0)
    today = _sf_series_num(df, "Today %", 0.0)
    op = _sf_series_num(df, "Op Score", 0.0)
    if not op.gt(0).any():
        op = _sf_series_num(df, "Operator Score", 0.0)
    atr = _sf_series_num(df, "ATR%", 0.0)
    supp_num = _sf_series_num(df, "Supp#", 0.0)
    signals = df["Signals"].astype(str) if "Signals" in df.columns else pd.Series([""] * len(df), index=idx)
    support_text = df["Support Tier"].astype(str) if "Support Tier" in df.columns else pd.Series([""] * len(df), index=idx)
    trap_text = df["Trap Risk"].astype(str) if "Trap Risk" in df.columns else pd.Series([""] * len(df), index=idx)
    action_text = df["Action"].astype(str) if "Action" in df.columns else pd.Series([""] * len(df), index=idx)
    trend = signals.str.contains("WKLY TREND|RS>SPY|52W HIGH|GC|MA", na=False, regex=True)
    momentum = signals.str.contains("STOCH|MACD|RSI|MOMENTUM|HIGHER LOWS", na=False, regex=True)
    volume = signals.str.contains("VOL|POCKET PIVOT|OBV|OPERATOR|ACCUM", na=False, regex=True)
    structure = signals.str.contains("VWAP|SUPPORT|CLOSE|CANDLE|BREAKOUT|BASE", na=False, regex=True)
    relative = signals.str.contains("RS>|REL|SECTOR|LEADER", na=False, regex=True)
    categories = trend.astype(int) + momentum.astype(int) + volume.astype(int) + structure.astype(int) + relative.astype(int)
    trap = trap_text.str.upper().str.contains("FALSE|GAP|DISTRIB|TRAP", na=False) | action_text.str.upper().str.contains("TRAP", na=False)
    support = (supp_num > 0) | support_text.str.upper().str.contains("MA20|MA60|VWAP|SUPPORT", na=False)
    vol_signal = (vr >= 1.5) | volume
    name = str(strategy_name)
    precision_specs = precision_specs or {}
    if name in precision_specs:
        mask = _sf_scan_mask_from_spec(df, precision_specs[name])
    elif name == "Discovery":
        mask = (p >= 50) & (score >= 3)
    elif name == "Balanced":
        mask = (p >= 58) & (score >= 4) & (categories >= 2) & (today <= 8) & (~trap)
    elif name == "Strict":
        mask = (p >= 76) & (score >= 7) & (categories >= 3) & vol_signal & (~trap)
    elif name == "High Conviction":
        mask = (p >= 65) & (score >= 6) & (categories >= 4) & trend & momentum & (~trap)
    elif name == "Support Entry":
        mask = (p >= 55) & support & (today <= 6) & (~trap)
    elif name == "Pullback Volume Dry-Up":
        mask = (p >= 52) & support & (vr < 1.0) & (today >= -4) & (today <= 3.5) & (~trap)
    elif name == "High Volume":
        mask = (p >= 55) & (score >= 3) & vol_signal & (today <= 10)
    elif name == "Momentum Runner":
        mask = (p >= 58) & (score >= 4) & momentum & (today >= 0) & (today <= 8) & (~trap)
    elif name == "Operator Accumulation":
        mask = (p >= 55) & (op >= 4) & (today <= 8) & (~trap)
    elif name == "PSM Proxy":
        mask = (p >= 60) & (score >= 5) & (atr >= 2) & (atr <= 14) & (vr >= 0.9) & (today >= -6) & (today <= 12) & (categories >= 3) & (~trap)
    elif name == "Early Breakout":
        mask = (p >= 62) & (score >= 5) & vol_signal & structure & (today <= 8) & (~trap)
    else:
        mask = pd.Series([False] * len(df), index=idx)
    out = df[mask].copy()
    if out.empty:
        return out
    out["Finder Strategy"] = name
    out["Finder Rank Score"] = (
        p.reindex(out.index).fillna(0) * 0.45
        + score.reindex(out.index).fillna(0) * 3.0
        + nds.reindex(out.index).fillna(0) * 2.0
        + qs.reindex(out.index).fillna(0) * 2.0
        + vr.reindex(out.index).fillna(0) * 2.0
        + op.reindex(out.index).fillna(0) * 2.0
    ).round(2)
    return out.sort_values("Finder Rank Score", ascending=False, kind="stable")
