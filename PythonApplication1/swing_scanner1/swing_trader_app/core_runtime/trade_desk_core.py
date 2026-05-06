"""Extracted runtime section from app_runtime.py lines 4765-5035.
Loaded by app_runtime with exec(..., globals()) to preserve the original single-file behavior.
"""

def _td_num(x, default=0.0):
    try:
        if x is None:
            return default
        if isinstance(x, (int, float, np.integer, np.floating)):
            return float(x)
        s = str(x).replace("%", "").replace("$", "").replace("S$", "").replace("₹", "").replace(",", "").strip()
        if s in ("", "–", "nan", "None"):
            return default
        return float(s)
    except Exception:
        return default


def _td_score_setup(row, side="BUY"):
    """Return setup-quality labels from existing row columns only.
    BUY uses breakout/pullback language. SELL uses breakdown/rally-fade language.
    This is Trade Desk only; it does not change scanner signals.
    """
    side = str(side or "BUY").upper()
    prob_key = "Fall Prob" if side == "SELL" else "Rise Prob"
    alt_key = "Bayes Score"
    prob = _td_num(row.get(prob_key, row.get(alt_key, 0)), 0)
    if prob <= 1:
        prob *= 100
    op = _td_num(row.get("Op Score", row.get("Operator Score", 0)), 0)
    today = _td_num(row.get("Today %", 0), 0)
    trap = str(row.get("Trap Risk", "–")).upper()
    vwap = str(row.get("VWAP", "")).upper()
    entry_q = str(row.get("Entry Quality", ""))
    action = str(row.get("Action", "")).upper()

    if side == "SELL":
        breakdown_score = 0
        breakdown_score += 2 if prob >= 72 else 1 if prob >= 62 else 0
        breakdown_score += 2 if op >= 2 else 0   # bearish operator/distribution signs can still appear here
        breakdown_score += 1 if "BELOW" in vwap else 0
        breakdown_score += 1 if today < 0 else 0
        breakdown_score += 1 if "BREAK" in action or "SELL" in action or "SHORT" in action else 0
        breakdown_score -= 2 if trap == "GAP CHASE" else 0

        fade_score = 0
        fade_score += 2 if prob >= 68 else 1 if prob >= 58 else 0
        fade_score += 2 if "DISTRIB" in trap or "FALSE BO" in trap else 0
        fade_score += 1 if "BELOW" in vwap else 0
        fade_score += 1 if today <= 0 else 0
        fade_score += 1 if "WATCH" in entry_q or "AVOID" not in entry_q else 0

        if breakdown_score >= 6:
            b_label = "A+ Breakdown"
        elif breakdown_score >= 4:
            b_label = "Valid Breakdown"
        elif breakdown_score >= 2:
            b_label = "Weak Breakdown"
        else:
            b_label = "No Breakdown"

        if fade_score >= 5:
            p_label = "A+ Rally Fade"
        elif fade_score >= 3:
            p_label = "Valid Fade"
        elif fade_score >= 2:
            p_label = "Early Fade"
        else:
            p_label = "No Fade"
        return int(max(0, breakdown_score)), b_label, int(max(0, fade_score)), p_label

    # BUY side
    breakout_score = 0
    breakout_score += 2 if prob >= 72 else 1 if prob >= 62 else 0
    breakout_score += 2 if op >= 4 else 1 if op >= 2 else 0
    breakout_score += 1 if "ABOVE" in vwap else 0
    breakout_score += 1 if today > 0 else 0
    breakout_score -= 3 if trap in ("FALSE BO", "GAP CHASE", "DISTRIB") else 0
    breakout_score -= 1 if today > 7 else 0

    pullback_score = 0
    pullback_score += 2 if prob >= 68 else 1 if prob >= 58 else 0
    pullback_score += 2 if op >= 4 else 1 if op >= 2 else 0
    pullback_score += 2 if "PULLBACK" in action or "DIP" in action or "WATCH" in entry_q else 0
    pullback_score += 1 if "ABOVE" in vwap else 0
    pullback_score -= 2 if trap in ("FALSE BO", "GAP CHASE", "DISTRIB") else 0

    if breakout_score >= 6:
        b_label = "A+ Breakout"
    elif breakout_score >= 4:
        b_label = "A/B Breakout"
    elif breakout_score >= 2:
        b_label = "Weak Breakout"
    else:
        b_label = "No Breakout"
    if trap in ("FALSE BO", "GAP CHASE", "DISTRIB"):
        b_label = "Trap Risk"

    if pullback_score >= 6:
        p_label = "A+ Pullback"
    elif pullback_score >= 4:
        p_label = "Valid Pullback"
    elif pullback_score >= 2:
        p_label = "Early Pullback"
    else:
        p_label = "No Pullback"

    return int(max(0, breakout_score)), b_label, int(max(0, pullback_score)), p_label


def _td_make_trade_plan(df, side="BUY", account_size=10000.0, risk_pct=1.0, max_cap_pct=20.0, default_stop_pct=5.0):
    """Build execution plans for BUY or SELL/SHORT candidates.
    For SELL, risk is stop above entry and target below entry.
    """
    if df is None or df.empty:
        return pd.DataFrame()
    side = str(side or "BUY").upper()
    rows = []
    risk_amount = float(account_size) * float(risk_pct) / 100.0
    max_capital = float(account_size) * float(max_cap_pct) / 100.0
    for _, row in df.iterrows():
        r = row.to_dict()
        price = _td_num(r.get("Price", 0), 0)
        if price <= 0:
            continue

        if side == "SELL":
            stop = _td_num(r.get("Cover Stop", r.get("MA60 Stop", 0)), 0)
            if stop <= price:
                stop = price * (1.0 + float(default_stop_pct) / 100.0)
            target = _td_num(r.get("Target 1:1", r.get("Target 1:2", 0)), 0)
            if target <= 0 or target >= price:
                target = price * 0.92
            risk_per_share = max(stop - price, 0.01)
            reward_per_share = max(price - target, 0.0)
            entry_zone = f"{price*0.995:.2f} - {price*1.005:.2f}"
            invalidation = f"Close above {stop:.2f} or short squeeze / bullish reversal appears"
            target_name = "Cover Target"
        else:
            stop = _td_num(r.get("MA60 Stop", r.get("Cover Stop", 0)), 0)
            if stop <= 0 or stop >= price:
                stop = price * (1.0 - float(default_stop_pct) / 100.0)
            target = _td_num(r.get("TP1 +10%", r.get("Target 1:1", 0)), 0)
            if target <= price:
                target = price * 1.08
            risk_per_share = max(price - stop, 0.01)
            reward_per_share = max(target - price, 0.0)
            entry_zone = f"{price*0.995:.2f} - {price*1.005:.2f}"
            invalidation = f"Close below {stop:.2f} or trap risk appears"
            target_name = "Target 1"

        qty_by_risk = int(risk_amount // risk_per_share) if risk_per_share > 0 else 0
        qty_by_cap = int(max_capital // price) if price > 0 else 0
        qty = max(0, min(qty_by_risk, qty_by_cap))
        capital = qty * price
        max_loss = qty * risk_per_share
        rr = reward_per_share / risk_per_share if risk_per_share else 0
        b_score, b_label, p_score, p_label = _td_score_setup(r, side=side)
        verdict = str(r.get("Swing Verdict", r.get("Entry Quality", "")))
        trap = str(r.get("Trap Risk", "–")).upper()
        if side == "BUY" and trap in ("FALSE BO", "GAP CHASE", "DISTRIB"):
            allowed_size = "Avoid"
        elif side == "SELL" and trap == "GAP CHASE":
            allowed_size = "Avoid"
        elif verdict.startswith("✅") and rr >= 1.5:
            allowed_size = "Normal"
        elif verdict.startswith(("✅", "👀")) and rr >= 1.0:
            allowed_size = "Half"
        else:
            allowed_size = "Watch only"

        rows.append({
            "Side": "SELL/SHORT" if side == "SELL" else "BUY/LONG",
            "Ticker": r.get("Ticker", ""),
            "Plan Verdict": verdict or "–",
            "Entry Zone": entry_zone,
            "Entry": round(price, 3),
            "Stop": round(stop, 3),
            target_name: round(target, 3),
            "Risk %": round((risk_per_share / price) * 100.0, 2),
            "R:R": round(rr, 2),
            "Suggested Qty": qty,
            "Capital Needed": round(capital, 2),
            "Max Loss": round(max_loss, 2),
            "Allowed Size": allowed_size,
            "Primary Quality": b_label,
            "Secondary Quality": p_label,
            "Operator": r.get("Operator", "–"),
            "Trap Risk": r.get("Trap Risk", "–"),
            "Invalidation": invalidation,
        })
    return pd.DataFrame(rows)


def _td_sort_trade_plans(plan_df, side="BUY"):
    """Sort Trade Desk plans so executable BUY/SELL verdicts appear first.
    This is display-only and does not change scanner signals.
    """
    if plan_df is None or plan_df.empty or "Plan Verdict" not in plan_df.columns:
        return plan_df
    side = str(side or "BUY").upper()

    def _rank_verdict(v):
        s = str(v).upper()
        # Put the true action for the selected side first.
        if side == "SELL":
            if "SELL" in s or "SHORT" in s or s.startswith("✅"):
                return 0
            if "WATCH" in s or s.startswith("👀"):
                return 1
            if "WAIT" in s or s.startswith("⏳"):
                return 2
            if "AVOID" in s or s.startswith("🚫"):
                return 4
            return 3
        else:
            if "BUY" in s or "LONG" in s or s.startswith("✅"):
                return 0
            if "WATCH" in s or s.startswith("👀"):
                return 1
            if "WAIT" in s or s.startswith("⏳"):
                return 2
            if "AVOID" in s or s.startswith("🚫"):
                return 4
            return 3

    out = plan_df.copy()
    out["_plan_rank"] = out["Plan Verdict"].apply(_rank_verdict)
    sort_cols = ["_plan_rank"]
    asc = [True]
    for c in ["Allowed Size", "R:R", "Primary Quality", "Risk %"]:
        if c in out.columns:
            sort_cols.append(c)
            # R:R should be high first; Risk % low first; text columns stable enough.
            asc.append(False if c in ("R:R", "Primary Quality") else True)
    out = out.sort_values(sort_cols, ascending=asc, kind="mergesort")
    return out.drop(columns=["_plan_rank"], errors="ignore")


def _td_market_breadth(df_long, df_short, df_operator, regime_dict):
    long_n = 0 if df_long is None or df_long.empty else len(df_long)
    short_n = 0 if df_short is None or df_short.empty else len(df_short)
    op_strong = 0
    if df_operator is not None and not df_operator.empty and "Operator" in df_operator.columns:
        op_strong = int(df_operator["Operator"].astype(str).str.contains("STRONG|ACCUMULATION", case=False, na=False).sum())
    total = max(long_n + short_n, 1)
    long_pct = long_n / total * 100.0
    short_pct = short_n / total * 100.0
    regime = str(regime_dict.get("regime", "UNKNOWN")) if isinstance(regime_dict, dict) else "UNKNOWN"
    vix = float(regime_dict.get("vix", 0) or 0) if isinstance(regime_dict, dict) else 0
    if regime == "BULL" and long_pct >= 60 and vix < 22:
        mode = "Aggressive"
        max_size = "Normal size allowed"
    elif regime in ("BULL", "CAUTION") and long_pct >= 50 and vix < 25:
        mode = "Normal"
        max_size = "Normal / half size"
    elif regime == "BEAR" or short_pct > long_pct or vix >= 25:
        mode = "Defensive"
        max_size = "Half size or cash; shorts allowed if liquid"
    else:
        mode = "Selective"
        max_size = "Only A+ setups"
    return pd.DataFrame([{
        "Regime": regime,
        "VIX": round(vix, 2),
        "Long Setups": long_n,
        "Short Setups": short_n,
        "Long % of Setups": round(long_pct, 1),
        "Short % of Setups": round(short_pct, 1),
        "Strong Operator Count": op_strong,
        "Risk Mode": mode,
        "Position Guidance": max_size,
    }])


