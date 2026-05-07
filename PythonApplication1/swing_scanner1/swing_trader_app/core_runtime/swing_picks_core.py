"""Extracted runtime section from app_runtime.py lines 4496-4755.
Loaded by app_runtime with exec(..., globals()) to preserve the original single-file behavior.
"""

def _prob_to_float(val):
    try:
        return float(str(val).replace("%", "").strip())
    except Exception:
        return 0.0


def _event_verdict_rank(verdict):
    v = str(verdict or "").upper()
    if "BUY" in v: return 3
    if "WATCH" in v: return 2
    if "WAIT" in v: return 1
    return 0


def _parse_score_num(v, default=0.0):
    try:
        s = str(v).replace("%", "").replace("–", "0").strip()
        return float(s) if s else default
    except Exception:
        return default


def _sector_tailwind_score(sector_value):
    """Small ranking boost for sectors already showing green momentum.
    Works with sector text or numeric strings and safely returns 0 when unknown."""
    s = str(sector_value or "").upper()
    score = 0.0
    if any(k in s for k in ["SEMICON", "TECH", "AI", "CLOUD", "SOFTWARE"]):
        score += 2.0
    if any(k in s for k in ["GREEN", "LEADER", "STRONG"]):
        score += 1.0
    return score


def _news_score_from_event_row(row):
    """Convert Event Predictor text fields into a simple catalyst score."""
    score = 0.0
    news = str(row.get("News", "")).upper()
    orders = str(row.get("Orders", "")).upper()
    verdict = str(row.get("Verdict", "")).upper()
    evidence = str(row.get("Evidence", "")).upper()
    top_news = str(row.get("Top News", "")).upper()
    joined = " ".join([news, orders, verdict, evidence, top_news])

    if "POSITIVE" in news or "BUY" in verdict:
        score += 2.0
    if "WATCH" in verdict:
        score += 1.0
    if any(k in joined for k in ["ORDER", "CONTRACT", "GUIDANCE", "RAISE", "BEAT", "AWARD", "PARTNERSHIP", "UPGRADE"]):
        score += 2.0
    if any(k in joined for k in ["MISS", "CUT", "DOWNGRADE", "PROBE", "LAWSUIT", "DELAY", "WARNING"]):
        score -= 2.0
    return max(-4.0, min(6.0, score))


def _earnings_risk_penalty(days_out, earnings_text=""):
    """Penalty for upcoming earnings. Near earnings is event risk, not a clean swing."""
    try:
        if pd.notna(days_out):
            d = int(days_out)
            if 0 <= d <= 3:
                return 14.0
            if 4 <= d <= 7:
                return 10.0
            if 8 <= d <= 14:
                return 4.0
    except Exception:
        pass
    s = str(earnings_text or "")
    if "≤7" in s or "EARNINGS" in s.upper() and "SOON" in s.upper():
        return 10.0
    return 0.0


def _trap_risk_penalty(trap_risk):
    t = str(trap_risk or "–").upper().strip()
    if t == "FALSE BO":
        return 10.0
    if t == "GAP CHASE":
        return 8.0
    if t == "DISTRIB":
        return 9.0
    return 0.0


def _calc_final_swing_score(row):
    """Bayesian ensemble ranking score.

    This intentionally replaces the removed simple ML ranking. Bayesian remains
    the base model; other factors are additive/penalty layers that match real
    swing-trading workflow. Higher is better.
    """
    bayes_score = _parse_score_num(row.get("Rise Prob", 0), 0.0)
    op_score = _parse_score_num(row.get("Op Score", 0), 0.0)
    event_score = _parse_score_num(row.get("Event Score", 0), 0.0)
    news_score = _news_score_from_event_row(row)
    sector_score = _sector_tailwind_score(row.get("Sector", ""))
    earnings_pen = _earnings_risk_penalty(row.get("Days Out", None), row.get("Earnings", ""))
    trap_pen = _trap_risk_penalty(row.get("Trap Risk", "–"))

    # Main rank formula. Keep Bayesian dominant but add practical swing factors.
    # v13.52: news/event is optional; do not punish a technically strong setup
    # just because Yahoo news/earnings was unavailable.
    setup_txt = str(row.get("Setup Type", "")).upper()
    setup_bonus = 0.0
    if any(k in setup_txt for k in ["PULLBACK", "BREAKOUT", "CONTINUATION"]):
        setup_bonus += 4.0
    if "OPERATOR" in setup_txt:
        setup_bonus += 2.0
    final = (
        bayes_score * 0.50
        + op_score * 4.5
        + news_score * 3.0
        + event_score * 0.5
        + sector_score * 3.0
        + setup_bonus
        - earnings_pen
        - trap_pen
    )

    return {
        "Bayes Score": round(bayes_score, 2),
        "Operator Score": round(op_score, 2),
        "News Score": round(news_score, 2),
        "Sector Score": round(sector_score, 2),
        "Earnings Risk": round(earnings_pen, 2),
        "Trap Risk Score": round(trap_pen, 2),
        "Final Swing Score": round(final, 2),
    }


def _make_swing_picks_from_scan(df_long_in: pd.DataFrame, max_candidates: int = 25, event_days: int = 30) -> pd.DataFrame:
    """Merge latest long-signal output with Event Predictor scoring and
    v13.10 Bayesian ensemble ranking.

    Uses Bayesian probability as the base, then adds operator/smart-money,
    news/orders, sector tailwind and earnings/trap penalties. No simple ML is
    used in live ranking.
    """
    if df_long_in is None or df_long_in.empty or "Ticker" not in df_long_in.columns:
        return pd.DataFrame()

    tech = df_long_in.copy()
    tech["_rise"] = tech.get("Rise Prob", "0%").apply(_prob_to_float)

    # Prefer true BUY / high-quality WATCH setups; keep enough candidates for
    # earnings/news enrichment even when the market is quiet.
    action = tech.get("Action", pd.Series([""] * len(tech))).astype(str).str.upper()
    entry = tech.get("Entry Quality", pd.Series([""] * len(tech))).astype(str).str.upper()
    trap = tech.get("Trap Risk", pd.Series(["–"] * len(tech))).astype(str)
    tech_pref = tech[
        (tech["_rise"] >= 62) &
        (~trap.isin(["FALSE BO", "GAP CHASE", "DISTRIB"])) &
        (
            action.str.contains("BUY|HIGH QUALITY|DEVELOPING", na=False) |
            entry.str.contains("BUY|WATCH", na=False)
        )
    ].copy()
    if tech_pref.empty:
        tech_pref = tech.sort_values("_rise", ascending=False).head(max_candidates).copy()
    else:
        tech_pref = tech_pref.sort_values("_rise", ascending=False).head(max_candidates).copy()

    tickers = _unique_keep_order(tech_pref["Ticker"].astype(str).str.upper().tolist())
    if not tickers:
        return pd.DataFrame()

    event_df = fetch_event_predictions(tuple(tickers), days_ahead=event_days)
    if event_df.empty:
        # Still return technical shortlist when Yahoo earnings/news fetch fails.
        out = tech_pref[[c for c in [
            "Ticker", "Setup Type", "Entry Quality", "Rise Prob", "Score", "Operator", "Op Score",
            "VWAP", "Trap Risk", "Today %", "Price", "Sector", "Action",
            "MA60 Stop", "TP1 +10%", "TP2 +15%", "TP3 +20%"
        ] if c in tech_pref.columns]].copy()
        out["Earnings"] = "–"
        out["News"] = "–"
        out["Event Score"] = 0
        out["Event Verdict"] = "–"
        # Build ensemble score even when event/news fetch fails.
        rank_rows = []
        for _, rr in out.iterrows():
            rank_rows.append(_calc_final_swing_score(rr))
        if rank_rows:
            out = pd.concat([out.reset_index(drop=True), pd.DataFrame(rank_rows)], axis=1)
        def _tech_only_verdict(rr):
            rise = _prob_to_float(rr.get("Rise Prob", "0%"))
            entry_s = str(rr.get("Entry Quality", "")).upper()
            trap_s = str(rr.get("Trap Risk", "–")).upper()
            final_s = _parse_score_num(rr.get("Final Swing Score", 0), 0)
            if trap_s in ("FALSE BO", "GAP CHASE", "DISTRIB"):
                return f"⏳ WAIT — {trap_s} risk"
            if "BUY" in entry_s and rise >= 66 and final_s >= 48:
                return "✅ BUY / WATCH ENTRY"
            if rise >= 62 and final_s >= 42:
                return "👀 WATCH"
            return "⏳ WAIT"
        out["Swing Verdict"] = out.apply(_tech_only_verdict, axis=1)
        out["Why"] = "Event/news unavailable; ranked by technical setup, operator activity, sector and risk."
        return out.sort_values("Final Swing Score", ascending=False) if "Final Swing Score" in out.columns else out

    event_cols = [c for c in [
        "Ticker", "Earnings", "Days Out", "EPS Trend", "News", "Orders",
        "Trend Score", "Event Score", "Verdict", "Evidence", "Top News"
    ] if c in event_df.columns]
    merged = tech_pref.merge(event_df[event_cols], on="Ticker", how="left")

    rows = []
    for _, r in merged.iterrows():
        rise = _prob_to_float(r.get("Rise Prob", "0%"))
        op_score = 0
        try:
            op_score = int(float(str(r.get("Op Score", 0)).replace("–", "0")))
        except Exception:
            op_score = 0
        action_s = str(r.get("Action", "")).upper()
        entry_s = str(r.get("Entry Quality", "")).upper()
        event_v = str(r.get("Verdict", ""))
        earnings = str(r.get("Earnings", ""))
        news = str(r.get("News", ""))
        trap_risk = str(r.get("Trap Risk", "–"))
        event_rank = _event_verdict_rank(event_v)
        days_out = r.get("Days Out", None)

        tech_ok = (rise >= 72) or ("BUY" in action_s) or ("BUY" in entry_s)
        watch_ok = (rise >= 62) or ("WATCH" in action_s) or ("WATCH" in entry_s)
        near_earn = False
        try:
            near_earn = pd.notna(days_out) and int(days_out) <= 7 and int(days_out) >= 0
        except Exception:
            near_earn = "≤7" in earnings

        rank_bits = _calc_final_swing_score(r)
        final_score = rank_bits["Final Swing Score"]

        event_missing = event_v in ("", "–", "nan", "None") or pd.isna(r.get("Verdict", np.nan))
        strong_technical = (
            ("BUY" in entry_s or rise >= 72) and
            final_score >= 50 and
            op_score >= 2 and
            str(r.get("VWAP", "")).upper() != "BELOW"
        )
        good_watch = watch_ok and final_score >= 42

        if near_earn:
            swing_verdict = "🚫 AVOID — earnings ≤7d"
        elif trap_risk in ("FALSE BO", "GAP CHASE", "DISTRIB"):
            swing_verdict = f"⏳ WAIT — {trap_risk} risk"
        elif strong_technical and (event_rank >= 1 or event_missing):
            swing_verdict = "✅ BUY / WATCH ENTRY"
        elif tech_ok and event_rank >= 2 and final_score >= 48:
            swing_verdict = "✅ BUY / WATCH ENTRY"
        elif good_watch:
            swing_verdict = "👀 WATCH"
        elif watch_ok and final_score >= 36:
            swing_verdict = "⏳ WAIT"
        else:
            swing_verdict = "🚫 AVOID"

        why_parts = []
        why_parts.append(f"Tech {r.get('Rise Prob','–')} / {r.get('Action','–')}")
        if r.get("Operator", "–") != "–": why_parts.append(f"Operator {r.get('Operator','–')}")
        if r.get("VWAP", "–") != "–": why_parts.append(f"VWAP {r.get('VWAP','–')}")
        if earnings and earnings != "nan": why_parts.append(f"Earnings {earnings}")
        if news and news != "nan": why_parts.append(f"News {news}")
        if r.get("Orders", "–") not in ("–", "nan", None): why_parts.append(str(r.get("Orders")))

        item = r.to_dict()
        item.update(rank_bits)
        item["Event Verdict"] = event_v if event_v and event_v != "nan" else "–"
        item["Swing Verdict"] = swing_verdict
        item["Why"] = " · ".join(why_parts)
        item["_swing_rank"] = (
            (3 if swing_verdict.startswith("✅") else 2 if swing_verdict.startswith("👀") else 1 if swing_verdict.startswith("⏳") else 0),
            item.get("Final Swing Score", 0),
            rise,
            op_score,
        )
        rows.append(item)

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["_rank_a"] = out["_swing_rank"].apply(lambda x: x[0])
    out["_rank_b"] = out["_swing_rank"].apply(lambda x: x[1])
    out["_rank_c"] = out["_swing_rank"].apply(lambda x: x[2])
    out["_rank_d"] = out["_swing_rank"].apply(lambda x: x[3])
    out = out.sort_values(["_rank_a", "_rank_b", "_rank_c", "_rank_d"], ascending=False)
    return out.drop(columns=[c for c in ["_swing_rank", "_rank_a", "_rank_b", "_rank_c", "_rank_d", "_rise", "_score", "_vcol"] if c in out.columns])


