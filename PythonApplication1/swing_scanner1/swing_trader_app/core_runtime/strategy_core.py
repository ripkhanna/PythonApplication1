"""Extracted runtime section from app_runtime.py lines 5044-5269.
Loaded by app_runtime with exec(..., globals()) to preserve the original single-file behavior.
"""

def _strategy_auc(y_true, scores):
    try:
        y = np.asarray(y_true, dtype=int)
        s = np.asarray(scores, dtype=float)
        pos = s[y == 1]; neg = s[y == 0]
        if len(pos) == 0 or len(neg) == 0:
            return None
        wins = 0.0
        for ps in pos:
            wins += float(np.sum(ps > neg)) + 0.5 * float(np.sum(ps == neg))
        return wins / float(len(pos) * len(neg))
    except Exception:
        return None


def _strategy_first_hit_label(future_high, future_low, entry, tp_pct=6.0, sl_pct=4.0):
    """1 if +target is hit before -stop within horizon; same-day tie counts as stop first."""
    if entry <= 0:
        return 0, 0.0, 0.0, "bad_entry"
    tp = entry * (1.0 + tp_pct / 100.0)
    sl = entry * (1.0 - sl_pct / 100.0)
    max_gain, max_dd = 0.0, 0.0
    for hi, lo in zip(future_high, future_low):
        try:
            hi = float(hi); lo = float(lo)
        except Exception:
            continue
        max_gain = max(max_gain, (hi / entry - 1.0) * 100.0)
        max_dd = min(max_dd, (lo / entry - 1.0) * 100.0)
        if lo <= sl and hi >= tp:
            return 0, max_gain, max_dd, "same_day_stop_first"
        if lo <= sl:
            return 0, max_gain, max_dd, "stop_first"
        if hi >= tp:
            return 1, max_gain, max_dd, "target_first"
    return 0, max_gain, max_dd, "no_target"


def _strategy_feature_row(long_sig, raw):
    bayes_prob = bayesian_prob(LONG_WEIGHTS, long_sig, 0.0) * 100.0
    bucket_counts = {}
    for k, active in long_sig.items():
        if active:
            b = SIGNAL_BUCKETS.get(k, "other")
            bucket_counts[b] = bucket_counts.get(b, 0) + 1
    trap = 1 if raw.get("false_breakout") or raw.get("gap_chase_risk") or raw.get("operator_distribution") else 0
    p = float(raw.get("p", 0) or 0)
    ma20 = float(raw.get("ma20", p) or p or 1)
    ma60 = float(raw.get("ma60", p) or p or 1)
    vwap = float(raw.get("vwap", p) or p or 1)
    atr = float(raw.get("atr", 0) or 0)
    return {
        "BayesProb": round(bayes_prob, 4),
        "SignalCount": int(sum(1 for v in long_sig.values() if v)),
        "TrendCount": int(bucket_counts.get("trend", 0)),
        "MomentumCount": int(bucket_counts.get("momentum", 0)),
        "VolumeCount": int(bucket_counts.get("volume", 0)),
        "StructureCount": int(bucket_counts.get("structure", 0)),
        "RelativeCount": int(bucket_counts.get("relative", 0)),
        "VolatilityCount": int(bucket_counts.get("volatility", 0)),
        "OptionsCount": int(bucket_counts.get("options", 0)),
        "OperatorScore": float(raw.get("operator_score", 0) or 0),
        "VolumeRatio": float(raw.get("vr", 0) or 0),
        "TodayPct": float(raw.get("today_chg_pct", 0) or 0),
        "RSI": float(raw.get("rsi0", 50) or 50),
        "ADX": float(raw.get("adx", 0) or 0),
        "ATRpct": round((atr / p * 100.0), 4) if p else 0.0,
        "PriceVsMA20Pct": round(((p / ma20) - 1.0) * 100.0, 4) if ma20 else 0.0,
        "PriceVsMA60Pct": round(((p / ma60) - 1.0) * 100.0, 4) if ma60 else 0.0,
        "PriceVsVWAPPct": round(((p / vwap) - 1.0) * 100.0, 4) if vwap else 0.0,
        "AboveVWAP": 1 if raw.get("above_vwap") else 0,
        "AboveMA60": 1 if raw.get("above_ma60") else 0,
        "NotChasing": 1 if raw.get("not_chasing") and raw.get("not_limit_up") else 0,
        "TrapRisk": trap,
        "FalseBreakout": 1 if raw.get("false_breakout") else 0,
        "GapChaseRisk": 1 if raw.get("gap_chase_risk") else 0,
        "DistributionRisk": 1 if raw.get("operator_distribution") else 0,
    }


@st.cache_data(ttl=3600, show_spinner=False)
def _strategy_build_dataset(tickers_tuple, period="2y", horizon=10, tp_pct=6.0, sl_pct=4.0, step=3):
    rows = []
    for ticker in list(tickers_tuple):
        try:
            raw_df = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=True)
            df = raw_df.copy()
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.ffill().dropna()
            if df.empty or len(df) < 260:
                continue
            close = df["Close"].ffill().dropna()
            high = df["High"].ffill().dropna()
            low = df["Low"].ffill().dropna()
            vol = df["Volume"].ffill().dropna()
            for end in range(220, len(close) - horizon, max(1, int(step))):
                try:
                    long_sig, _short_sig, sig_raw = compute_all_signals(close.iloc[:end], high.iloc[:end], low.iloc[:end], vol.iloc[:end])
                except Exception:
                    continue
                entry = float(close.iloc[end - 1])
                label, max_gain, max_dd, outcome = _strategy_first_hit_label(high.iloc[end:end+horizon], low.iloc[end:end+horizon], entry, tp_pct, sl_pct)
                feat = _strategy_feature_row(long_sig, sig_raw)
                feat.update({
                    "Ticker": ticker,
                    "Date": str(close.index[end - 1])[:10],
                    "Target": int(label),
                    "MaxGain%": round(max_gain, 3),
                    "MaxDD%": round(max_dd, 3),
                    "PathOutcome": outcome,
                    "BaselineScore": round(feat["BayesProb"] * 0.55 + feat["OperatorScore"] * 4.0 - feat["TrapRisk"] * 10.0, 4),
                })
                rows.append(feat)
        except Exception:
            continue
    return pd.DataFrame(rows)


def _strategy_train_model(data: pd.DataFrame, feature_cols):
    if data is None or data.empty or len(data) < 150:
        return None, {"Error": "Need at least 150 historical samples. Add tickers or use longer history."}
    d = data.copy().sort_values("Date")
    X = d[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0).astype(float)
    y = d["Target"].astype(int)
    split = int(len(d) * 0.70)
    if split <= 20 or len(d) - split <= 20 or y.nunique() < 2:
        return None, {"Error": "Not enough class diversity after chronological split."}
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]
    if _lgbm_available:
        model = LGBMClassifier(n_estimators=250, learning_rate=0.035, max_depth=3, num_leaves=15, min_child_samples=25, subsample=0.85, colsample_bytree=0.85, reg_lambda=2.0, random_state=42, verbose=-1)
        model_name = "LightGBM Classifier"
    elif _sklearn_strategy_available:
        model = HistGradientBoostingClassifier(max_iter=180, learning_rate=0.05, max_leaf_nodes=15, l2_regularization=1.0, random_state=42)
        model_name = "sklearn HistGradientBoosting fallback"
    else:
        return None, {"Error": "Install lightgbm or scikit-learn to use Strategy Lab ML."}
    try:
        model.fit(X_train, y_train)
        proba = model.predict_proba(X_test)[:, 1]
        baseline = d["BaselineScore"].iloc[split:].astype(float).to_numpy()
        pred = (proba >= 0.50).astype(int)
        base_pred = (baseline >= np.nanpercentile(baseline, 60)).astype(int)
        y_arr = y_test.to_numpy()
        if _sklearn_strategy_available:
            auc_ml = roc_auc_score(y_test, proba) if len(np.unique(y_test)) > 1 else None
            auc_base = roc_auc_score(y_test, baseline) if len(np.unique(y_test)) > 1 else None
            acc_ml = accuracy_score(y_test, pred)
            acc_base = accuracy_score(y_test, base_pred)
            prec_ml = precision_score(y_test, pred, zero_division=0)
            brier = brier_score_loss(y_test, proba)
        else:
            auc_ml = _strategy_auc(y_arr, proba)
            auc_base = _strategy_auc(y_arr, baseline)
            acc_ml = float(np.mean(pred == y_arr))
            acc_base = float(np.mean(base_pred == y_arr))
            prec_ml = float(np.sum((pred == 1) & (y_arr == 1)) / max(1, np.sum(pred == 1)))
            brier = float(np.mean((proba - y_arr) ** 2))
        top_n = max(5, int(len(proba) * 0.10))
        top_ml_idx = np.argsort(-proba)[:top_n]
        top_base_idx = np.argsort(-baseline)[:top_n]
        top_ml_win = float(np.mean(y_arr[top_ml_idx])) if top_n else 0.0
        top_base_win = float(np.mean(y_arr[top_base_idx])) if top_n else 0.0
        max_gain_arr = d["MaxGain%"].iloc[split:].to_numpy()
        max_dd_arr = d["MaxDD%"].iloc[split:].to_numpy()
        importance = []
        if hasattr(model, "feature_importances_"):
            importance = sorted(zip(feature_cols, list(model.feature_importances_)), key=lambda x: -abs(float(x[1])))[:12]
        report = {
            "Model": model_name,
            "Samples": int(len(d)), "Train": int(len(X_train)), "Test": int(len(X_test)),
            "Base Rate": round(float(y.mean()) * 100.0, 2),
            "ML AUC": round(float(auc_ml), 4) if auc_ml is not None else None,
            "Baseline AUC": round(float(auc_base), 4) if auc_base is not None else None,
            "AUC Edge": round(float((auc_ml or 0) - (auc_base or 0)), 4) if auc_ml is not None and auc_base is not None else None,
            "ML Accuracy": round(float(acc_ml) * 100.0, 2),
            "Baseline Accuracy": round(float(acc_base) * 100.0, 2),
            "ML Precision": round(float(prec_ml) * 100.0, 2),
            "Top 10% ML Win%": round(top_ml_win * 100.0, 2),
            "Top 10% Baseline Win%": round(top_base_win * 100.0, 2),
            "Top 10% Avg MaxGain%": round(float(max_gain_arr[top_ml_idx].mean()), 2) if top_n else 0.0,
            "Top 10% Avg MaxDD%": round(float(max_dd_arr[top_ml_idx].mean()), 2) if top_n else 0.0,
            "Brier": round(float(brier), 4),
            "Split Date": str(d["Date"].iloc[split]),
            "Recommended": "YES" if (auc_ml is not None and auc_base is not None and auc_ml >= auc_base + 0.02 and top_ml_win >= top_base_win) else "NO — keep Bayesian ensemble primary",
            "Importance": importance,
        }
        return (model, feature_cols, report), report
    except Exception as e:
        return None, {"Error": f"Training failed: {type(e).__name__}: {e}"}


def _strategy_apply_to_current(model_bundle, df_current: pd.DataFrame):
    if model_bundle is None or df_current is None or df_current.empty:
        return df_current
    try:
        model, feature_cols, _metrics = model_bundle
        qs = []
        for _, r in df_current.iterrows():
            bayes = _parse_score_num(r.get("Bayes Score", r.get("Rise Prob", 0)), 0.0)
            op = _parse_score_num(r.get("Operator Score", r.get("Op Score", 0)), 0.0)
            trap = 1 if str(r.get("Trap Risk", "–")).upper() in ("FALSE BO", "GAP CHASE", "DISTRIB") else 0
            feat = {c: 0.0 for c in feature_cols}
            feat.update({"BayesProb": bayes, "OperatorScore": op, "TrapRisk": trap, "AboveVWAP": 1 if str(r.get("VWAP", "")).upper().startswith("ABOVE") else 0, "TodayPct": _parse_score_num(r.get("Today %", 0), 0.0), "SignalCount": _parse_score_num(r.get("Score", 0), 0.0)})
            x = pd.DataFrame([[feat.get(c, 0.0) for c in feature_cols]], columns=feature_cols)
            try:
                qs.append(float(model.predict_proba(x)[0, 1]))
            except Exception:
                qs.append(np.nan)
        out = df_current.copy()
        out["ML Trade Quality"] = [f"{q*100:.1f}%" if pd.notna(q) else "–" for q in qs]
        out["ML Failure Risk"] = [f"{(1-q)*100:.1f}%" if pd.notna(q) else "–" for q in qs]
        def _size(q, verdict):
            if pd.isna(q): return "–"
            v = str(verdict)
            if q >= 0.65 and v.startswith("✅"): return "Normal"
            if q >= 0.55 and (v.startswith("✅") or v.startswith("👀")): return "Half"
            if q >= 0.48: return "Small / Watch"
            return "Avoid"
        out["Suggested Size"] = [_size(q, v) for q, v in zip(qs, out.get("Swing Verdict", pd.Series([""]*len(out))))]
        return out
    except Exception:
        return df_current


