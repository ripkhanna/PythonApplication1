import pandas as pd
import streamlit as st

"""Scan Results Tabs renderer — v2 (strategy-aware).

Supports 6 swing strategy modes set in the sidebar:
  Strict / Balanced / Discovery  — existing behaviour, unchanged
  Support Entry                  — only stocks AT support levels
  Premarket Momentum             — only stocks with PM strength + intact trend
  High Volume                    — unusual volume / volume breakout / pocket pivot
"""


def _bind_runtime(ctx: dict) -> None:
    globals().update(ctx)


def _mode_banner(m: str) -> None:
    if m == "SUPPORT ENTRY":
        st.info(
            "📍 **Support Entry mode** — only stocks AT a known support level are shown. "
            "Stocks already up >3% today are filtered out (extended, bad R/R). "
            "**Tier 1 🔵 MA60 dip** = strongest. **Tier 2 🟢 MA20 dip**. "
            "**Tier 3 🟡 Swing low**. **Tier 4 ⚪ VWAP / MA200 / Near support**.  \n"
            "Stop sits just below support → tight risk, unchanged upside target."
        )
    elif m == "PREMARKET MOMENTUM":
        st.info(
            "🚀 **Premarket Momentum mode** — stocks with +1–8% pre-market gain + intact trend.  \n"
            "**Tier A 🚀 +3–8%** = high conviction open-gap. "
            "**Tier B 📈 +1–3%** = building momentum.  \n"
            "Run 15–30 min before market open for best results. "
            "Stocks with broken technicals are removed even if PM gain is large."
        )
    elif m == "HIGH VOLUME":
        st.info(
            "📊 **High Volume mode** — stocks with unusual volume / volume breakout / pocket pivot.  \n"
            "Tier A = extreme volume, Tier B = breakout volume, Tier C = pocket pivot, Tier D = unusual volume watchlist."
        )
    elif m == "STAGE 2 BREAKOUT":
        st.info(
            "**Stage 2 Breakout mode** — qualified early pre-breakout scan plus a transparent developing watch layer. "
            "Already-moved stocks stay excluded. Developing rows are marked NOT QUALIFIED and show exactly why they failed."
        )
    elif m == "EARLY RALLY FINDER":
        st.info(
            "**Early Rally Finder** - all-market scan for early accumulation and first-trigger names. "
            "BUY rows passed freshness, extension, entry, trap, volume, and R:R gates. "
            "Watch rows may use a compact contracting base with usable Stage 2 or resistance runway. "
            "Re-accumulation rows identify a prior impulse followed by a quiet reset and reclaim; "
            "they stay watch-only until the prior peak breaks on volume. "
            "Mature and already-extended names are excluded."
        )




# ─────────────────────────────────────────────────────────────────────────────
# High Conviction display-only ranking helpers
# These helpers do NOT change scanner/strategy logic. They only rank the already
# returned High Conviction dataframe so the user can focus on the best few names.
# ─────────────────────────────────────────────────────────────────────────────
def _hc_num(series, default=0.0):
    try:
        return pd.to_numeric(
            series.astype(str)
                  .str.replace("%", "", regex=False)
                  .str.replace("+", "", regex=False)
                  .str.replace("x", "", regex=False)
                  .str.replace("–", "", regex=False)
                  .str.strip(),
            errors="coerce",
        ).fillna(default)
    except Exception:
        return pd.Series([default] * len(series), index=getattr(series, "index", None))


def _hc_score_num(series, default=0.0):
    try:
        # Handles "7", "7/10", "Score 7", etc.
        out = pd.to_numeric(series.astype(str).str.extract(r"(\d+(?:\.\d+)?)")[0], errors="coerce")
        return out.fillna(default)
    except Exception:
        return pd.Series([default] * len(series), index=getattr(series, "index", None))


def _build_top_swing_buys(df, top_n=10):
    """Return a display-only ranked Top Swing Buys dataframe for High Conviction."""
    if df is None or df.empty:
        return pd.DataFrame()

    ranked = df.copy()
    idx = ranked.index

    rise = _hc_num(ranked.get("Rise Prob", pd.Series([0] * len(ranked), index=idx)), 0).clip(0, 100)
    raw_score = _hc_score_num(ranked.get("Score", pd.Series([0] * len(ranked), index=idx)), 0)
    # If Score is on 0-10 scale, normalize to 0-100; if already 0-100, keep it.
    score_norm = raw_score.where(raw_score > 10, raw_score * 10).clip(0, 100)
    vol_ratio = _hc_num(ranked.get("Vol Ratio", pd.Series([0] * len(ranked), index=idx)), 0)
    vol_score = (vol_ratio.clip(0, 3.0) / 3.0 * 100).fillna(0)
    today = _hc_num(ranked.get("Today %", pd.Series([0] * len(ranked), index=idx)), 0)

    # Prefer stocks that have moved, but are not too extended. This is display-only.
    today_score = pd.Series([60.0] * len(ranked), index=idx)
    today_score = today_score.mask((today >= 0) & (today <= 6), 95)
    today_score = today_score.mask((today > 6) & (today <= 10), 70)
    today_score = today_score.mask(today > 10, 35)
    today_score = today_score.mask(today < -3, 40)

    entry_text = (
        ranked.get("Entry Quality", pd.Series([""] * len(ranked), index=idx)).astype(str) + " " +
        ranked.get("Setup Type", pd.Series([""] * len(ranked), index=idx)).astype(str) + " " +
        ranked.get("Support Tier", pd.Series([""] * len(ranked), index=idx)).astype(str) + " " +
        ranked.get("Action", pd.Series([""] * len(ranked), index=idx)).astype(str)
    )
    entry_score = pd.Series([60.0] * len(ranked), index=idx)
    entry_score = entry_score.mask(entry_text.str.contains("✅|SUPPORT|MA20|MA60|VWAP|PRECISION|STRONG BUY", na=False, regex=True), 90)
    entry_score = entry_score.mask(entry_text.str.contains("WAIT|EXTENDED|TRAP|AVOID", na=False, regex=True), 35)

    opt_text = ranked.get("Opt Flow", pd.Series(["–"] * len(ranked), index=idx)).astype(str)
    opt_score = pd.Series([50.0] * len(ranked), index=idx).mask(opt_text.ne("–") & opt_text.ne(""), 100)

    final = (
        rise * 0.35 +
        score_norm * 0.20 +
        vol_score * 0.15 +
        entry_score * 0.15 +
        today_score * 0.10 +
        opt_score * 0.05
    ).round(1)

    ranked.insert(0, "Final Swing Score", final)
    ranked.insert(1, "Rank", final.rank(method="first", ascending=False).astype(int))

    decision = pd.Series(["WATCH – GOOD SETUP"] * len(ranked), index=idx)
    decision = decision.mask(final >= 85, "TOP BUY – SWING")
    decision = decision.mask((final >= 78) & (final < 85), "BUY – HIGH PROBABILITY")
    decision = decision.mask((final >= 70) & (final < 78), "WATCH – WAIT FOR ENTRY")
    decision = decision.mask(final < 70, "WATCH ONLY")
    ranked.insert(2, "Decision", decision)

    why = []
    for i in ranked.index:
        reasons = []
        try:
            if rise.loc[i] >= 70: reasons.append("high rise probability")
            if score_norm.loc[i] >= 70: reasons.append("strong signal score")
            if vol_ratio.loc[i] >= 2: reasons.append("volume expansion")
            elif vol_ratio.loc[i] >= 1.3: reasons.append("rising volume")
            if entry_score.loc[i] >= 85: reasons.append("good entry/support")
            if 0 <= today.loc[i] <= 6: reasons.append("not over-extended")
            if opt_score.loc[i] >= 100: reasons.append("options confirmed")
        except Exception:
            pass
        why.append(", ".join(reasons[:4]) if reasons else "best ranked High Conviction candidate")
    ranked.insert(3, "Why Selected", why)

    ranked = ranked.sort_values("Final Swing Score", ascending=False, kind="stable")
    try:
        n = int(top_n)
    except Exception:
        n = 10
    return ranked.head(max(1, n)).copy()

# ─────────────────────────────────────────────────────────────────────────────
# PRO SWING — display-only decision layer
# Ranks the filtered Pro Swing dataframe so the user can see instantly which
# stocks to buy, which to watch, and why — without reading 40 rows.
#
# Scoring (0–100 composite):
#   PSS Score   30 pts  — primary: how many of 8 pro sub-signals fired
#   Rise Prob   25 pts  — probability engine confidence
#   Vol Ratio   20 pts  — volume expansion (confirms institutional interest)
#   Op Score    15 pts  — smart-money accumulation footprint
#   Entry Qual  10 pts  — ✅ ideal entry vs extended/wait
#
# Tiers:  🔥 Elite ≥82  |  ✅ Buy ≥68  |  👀 Watch ≥55  |  ⏳ Lower priority
# ─────────────────────────────────────────────────────────────────────────────
def _build_pro_swing_ranking(df, top_n=15):
    """
    Return a ranked, display-ready dataframe for the Pro Swing decision panel.
    Works whether PSS Score column is present (new scan) or absent (old cache).
    """
    if df is None or df.empty:
        return pd.DataFrame()

    ranked = df.copy()
    idx    = ranked.index

    # ── Parse PSS Score (e.g. "5/8" → 5, or 0 if absent) ────────────────────
    has_pss = "PSS Score" in ranked.columns
    if has_pss:
        pss_num = pd.to_numeric(
            ranked["PSS Score"].astype(str).str.extract(r"(\d+)", expand=False),
            errors="coerce"
        ).fillna(0)
    elif m == "EARLY RALLY FINDER":
        st.info(
            "**Early Rally Finder** - catches accumulation, trigger-watch, and confirmed early-rally setups across markets. "
            "Already-extended and mature-trend names are excluded instead of being recycled as watch candidates."
        )
    else:
        pss_num = pd.Series([0.0] * len(ranked), index=idx)

    pss_score_pts = (pss_num / 8.0 * 100).clip(0, 100)

    # ── Rise Prob → 0-100 ────────────────────────────────────────────────────
    rise = _hc_num(ranked.get("Rise Prob", pd.Series([0]*len(ranked), index=idx)), 0).clip(0, 100)

    # ── Vol Ratio → 0-100 ────────────────────────────────────────────────────
    vr = _hc_num(ranked.get("Vol Ratio", pd.Series([0]*len(ranked), index=idx)), 0)
    vol_pts = (vr.clip(0, 4.0) / 4.0 * 100).fillna(0)

    # ── Op Score → 0-100 ─────────────────────────────────────────────────────
    op_raw = _hc_score_num(ranked.get("Op Score", pd.Series([0]*len(ranked), index=idx)), 0)
    op_pts = (op_raw.clip(0, 10.0) / 10.0 * 100).fillna(0)

    # ── Entry Quality → 0-100 ────────────────────────────────────────────────
    eq_text = ranked.get("Entry Quality", pd.Series([""]*len(ranked), index=idx)).astype(str)
    eq_pts  = pd.Series([60.0] * len(ranked), index=idx)
    eq_pts  = eq_pts.mask(eq_text.str.contains(r"✅", na=False), 100)
    eq_pts  = eq_pts.mask(eq_text.str.contains("EXTENDED|WAIT|AVOID", na=False, regex=True), 30)

    # ── Options confirmed ─────────────────────────────────────────────────────
    opt_text = ranked.get("Opt Flow", pd.Series(["–"]*len(ranked), index=idx)).astype(str)
    opt_bonus = pd.Series([0.0] * len(ranked), index=idx).mask(
        opt_text.ne("–") & opt_text.ne(""), 5.0
    )

    # ── v14.1: Cash/MCap floor bonus ─────────────────────────────────────────
    # Cash-rich companies have downside buffered. Bonus to Pro Score.
    cash_mcap_raw = ranked.get("Cash/MCap", pd.Series(["–"]*len(ranked), index=idx)).astype(str)
    cash_num = pd.to_numeric(
        cash_mcap_raw.str.replace("%", "", regex=False).str.strip(),
        errors="coerce"
    ).fillna(0) / 100.0
    cash_bonus = pd.Series([0.0] * len(ranked), index=idx)
    cash_bonus = cash_bonus.mask(cash_num >= 0.70, 8.0)
    cash_bonus = cash_bonus.mask((cash_num >= 0.40) & (cash_num < 0.70), 4.0)
    cash_bonus = cash_bonus.mask((cash_num >= 0.20) & (cash_num < 0.40), 1.5)

    # ── v14.1: Analyst consensus bonus ───────────────────────────────────────
    analyst_text = ranked.get("Analyst", pd.Series(["–"]*len(ranked), index=idx)).astype(str)
    analyst_bonus = pd.Series([0.0] * len(ranked), index=idx)
    analyst_bonus = analyst_bonus.mask(analyst_text.str.contains("Strong Buy", na=False),  6.0)
    analyst_bonus = analyst_bonus.mask(analyst_text.str.contains("🟢 Buy",     na=False),  3.0)
    analyst_bonus = analyst_bonus.mask(analyst_text.str.contains("Sell",       na=False), -5.0)

    # ── v14.1: Biotech/pharma half-size flag ─────────────────────────────────
    # We don't reduce Pro Score (biotech can still be a great swing),
    # but we cap Elite tier to "Buy" for biotech unless PSS >= 5.
    pos_note_text = ranked.get("Pos Size", pd.Series(["Normal"]*len(ranked), index=idx)).astype(str)
    biotech_flag  = pos_note_text.str.contains("Biotech|Bio|Pharma", na=False, regex=True)

    # ── Detect whether PSS Score is populated (new scan) or absent (old cache) ─
    has_pss = (
        "PSS Score" in ranked.columns and
        pd.to_numeric(
            ranked["PSS Score"].astype(str).str.extract(r"(\d+)", expand=False),
            errors="coerce"
        ).fillna(0).gt(0).any()
    )

    # ── PI Proxy = ATR% × (Rise Prob / 100) ───────────────────────────────
    # PI is the return-potential engine. It gives priority to stocks that have
    # enough daily range to realistically move 5%+ in a 5–7 day swing, while the
    # rest of the score checks quality/confirmation.
    if "PI Proxy" in ranked.columns:
        pi_proxy = _hc_num(ranked["PI Proxy"], 0).fillna(0)
    elif "PI Proxy Raw" in ranked.columns:
        pi_proxy = _hc_num(ranked["PI Proxy Raw"], 0).fillna(0)
    else:
        if "ATR%" in ranked.columns:
            _atr_check = pd.to_numeric(
                ranked["ATR%"].astype(str).str.replace("%", "", regex=False).str.strip(), errors="coerce"
            ).fillna(0)
            atr_vals = _atr_check if _atr_check.gt(0).any() else vr * 1.5
        else:
            atr_vals = vr * 1.5
        pi_proxy = (atr_vals * (rise / 100)).round(2)

    # Convert PI to 0–100. PI≈2 is trade-worthy, PI≈3+ is strong, PI≈4+ is elite.
    pi_pts = (pi_proxy.clip(0, 4.0) / 4.0 * 100).fillna(0)

    # ── Final composite score — quality + return potential ──────────────────
    # With PSS:    PI 30% | PSS 25% | Rise 20% | Vol 12% | Op 8% | Entry 5% + bonuses
    # Without PSS: PI 38% | Rise 27% | Vol 18% | Op 10% | Entry 7% + bonuses
    # This makes the Top PSM list stricter and more useful for actual swing buys.
    if has_pss:
        final = (
            pi_pts        * 0.28 +
            pss_score_pts * 0.27 +
            rise          * 0.20 +
            vol_pts       * 0.12 +
            op_pts        * 0.08 +
            eq_pts        * 0.05 +
            opt_bonus + cash_bonus + analyst_bonus
        ).round(1)
        watch_t, buy_t, elite_t = 60, 74, 86
    else:
        final = (
            pi_pts * 0.34 +
            rise   * 0.28 +
            vol_pts * 0.18 +
            op_pts  * 0.12 +
            eq_pts  * 0.08 +
            opt_bonus + cash_bonus + analyst_bonus
        ).round(1)
        watch_t, buy_t, elite_t = 50, 66, 82

    # If the scanner produced PSM Quality, blend it in. This keeps the
    # display panel aligned with the actual PSM strategy gate and stops
    # high-ATR speculative names from ranking above cleaner setups.
    if "PSM Quality" in ranked.columns:
        psm_q = _hc_num(ranked["PSM Quality"], 0).clip(0, 100)
        final = (psm_q * 0.70 + final * 0.30).round(1)
        watch_t, buy_t, elite_t = 60, 74, 86

    def _pi_label(v):
        if v >= 4.0: return f"🔥 {v:.1f}"
        if v >= 2.0: return f"✅ {v:.1f}"
        if v >= 1.0: return f"👀 {v:.1f}"
        return f"❌ {v:.1f}"

    pi_label_col = pi_proxy.apply(_pi_label)

    def _safe_float(v, default=0.0):
        try:
            if pd.isna(v):
                return default
            return float(v)
        except Exception:
            return default

    # Tier is aligned to actual PSM Action when available. This prevents
    # Watch-only rows from being promoted to Buy purely by display ranking.
    action_text = ranked.get("Action", pd.Series([""] * len(ranked), index=idx)).astype(str)
    tier = pd.Series(["👀 Watch"] * len(ranked), index=idx)
    tier = tier.mask((final >= buy_t) | action_text.str.contains("PSM STRONG|PSM QUALIFIED", na=False, regex=True), "✅ Buy")
    tier = tier.mask(((final >= elite_t) | action_text.str.contains("PSM ELITE", na=False)) & (pss_num >= 4) & (pi_proxy >= 2.5), "🔥 Elite Buy")

    # Biotech/pharma safety cap: biotech must have exceptional PSS to appear
    # as Buy; otherwise it remains watch-only, even if volatility/PI is high.
    bio_watch_cap = biotech_flag & (pss_num < 5)
    tier = tier.mask(bio_watch_cap, "👀 Watch")

    # ── Swing Rank Score — practical Monday-style tradability rank ──────────
    # Pro Score tells whether PSM conditions exist. Swing Rank Score decides
    # which one is easier to trade now: manageable price, strong-but-not-crazy
    # move, volume confirmation and acceptable stop distance. This is why a
    # cleaner name such as GRND can rank above expensive/wide-stop names even
    # when their PI/Pro Score is higher.
    price_vals = _hc_num(ranked.get("Price", pd.Series([0]*len(ranked), index=idx)), 0).fillna(0)
    today_vals = _hc_num(ranked.get("Today %", pd.Series([0]*len(ranked), index=idx)), 0).fillna(0)

    price_pts = pd.Series([45.0] * len(ranked), index=idx)
    price_pts = price_pts.mask((price_vals >= 5) & (price_vals <= 60), 100)
    price_pts = price_pts.mask((price_vals > 60) & (price_vals <= 90), 78)
    price_pts = price_pts.mask((price_vals > 90) & (price_vals <= 130), 55)
    price_pts = price_pts.mask(price_vals > 130, 25)
    price_pts = price_pts.mask((price_vals > 0) & (price_vals < 3), 20)

    move_pts = pd.Series([45.0] * len(ranked), index=idx)
    move_pts = move_pts.mask((today_vals >= 2) & (today_vals <= 10), 100)
    move_pts = move_pts.mask((today_vals > 10) & (today_vals <= 14), 60)
    move_pts = move_pts.mask(today_vals > 14, 25)
    move_pts = move_pts.mask((today_vals >= 0) & (today_vals < 2), 65)
    move_pts = move_pts.mask(today_vals < 0, 25)

    # Use the displayed stop if available. Wide stops reduce practical swing
    # attractiveness even when return potential is high.
    stop_raw = ranked.get("Best Stop", ranked.get("MA60 Stop", pd.Series([0]*len(ranked), index=idx)))
    stop_vals = _hc_num(stop_raw, 0).fillna(0)

    # Safe stop-distance calculation. Avoid pd.NA inside float conversion,
    # which can crash Streamlit with:
    #   TypeError: float() argument must be a string or a real number, not 'NAType'
    _denom = price_vals.where(price_vals > 0)
    stop_dist = pd.to_numeric(((price_vals - stop_vals) / _denom * 100), errors="coerce")
    stop_dist = stop_dist.replace([float("inf"), float("-inf")], pd.NA).fillna(999.0)

    risk_pts = pd.Series([55.0] * len(ranked), index=idx)
    risk_pts = risk_pts.mask((stop_dist > 0) & (stop_dist <= 12), 95)
    risk_pts = risk_pts.mask((stop_dist > 12) & (stop_dist <= 22), 85)
    risk_pts = risk_pts.mask((stop_dist > 22) & (stop_dist <= 30), 60)
    risk_pts = risk_pts.mask(stop_dist > 30, 25)

    vol_rank_pts = (vr.clip(0, 4.0) / 4.0 * 100).fillna(0)

    entry_rank_pts = pd.Series([60.0] * len(ranked), index=idx)
    entry_rank_pts = entry_rank_pts.mask(eq_text.str.contains(r"✅|BUY|IDEAL", na=False, regex=True), 100)
    entry_rank_pts = entry_rank_pts.mask(eq_text.str.contains("WAIT|EXTENDED|AVOID", na=False, regex=True), 25)

    # Keep PSM quality involved, but do not allow PI/Pro Score alone to push
    # expensive or wide-stop stocks ahead of cleaner swing trades.
    swing_rank_score = (
        final          * 0.22 +
        price_pts      * 0.22 +
        move_pts       * 0.18 +
        vol_rank_pts   * 0.16 +
        risk_pts       * 0.14 +
        entry_rank_pts * 0.08
    ).round(1)

    # Practical Monday-style adjustments. These are display-rank only and do
    # not change PSM scan logic. They make the rank closer to an actual swing
    # decision: avoid chasing high-priced/wide-range names, demote biotech/event
    # risk, and surface liquid high-volume momentum names like IREN.
    high_price_chase = (price_vals > 100) & (today_vals >= 5)
    very_high_price = price_vals > 130
    clean_momentum = (price_vals >= 5) & (price_vals <= 80) & (today_vals >= 4) & (today_vals <= 10) & (vr >= 2.0)
    high_pi_momentum = clean_momentum & (pi_proxy >= 5.0)
    ticker_text = ranked.get("Ticker", pd.Series([""] * len(ranked), index=idx)).astype(str).str.upper()
    aggressive_tickers = {"IREN", "MARA", "RIOT", "CLSK", "CIFR", "BTBT", "BITF", "WULF", "HUT", "CORZ", "HIVE"}
    event_biotech_tickers = {"NVAX", "ARCT", "KALV", "TNYA", "VERV", "ABEO", "RIGL", "OPK", "STOK", "TNGX", "MRX", "PRCT", "MYGN", "ALKS"}
    low_liq_watch_tickers = {"LEGH", "XPER", "PRKS", "WEN", "KOP"}
    quality_swing_tickers = {"WMG", "GLW", "DDOG", "QCOM"}
    momentum_trade_tickers = {"BB", "RKT"}
    aggressive_momentum = ticker_text.isin(aggressive_tickers) & clean_momentum & (pi_proxy >= 4.0)

    swing_rank_score = swing_rank_score.mask(high_price_chase, swing_rank_score - 10)
    swing_rank_score = swing_rank_score.mask(very_high_price, swing_rank_score - 6)
    swing_rank_score = swing_rank_score.mask(clean_momentum, swing_rank_score + 4)
    swing_rank_score = swing_rank_score.mask(high_pi_momentum, swing_rank_score + 4)
    # Symbol-risk adjustments for practical swing-trading display rank. These
    # are intentionally display-only: PSM can still find the row, but the Rank
    # and View now reflect how a trader would choose among candidates.
    swing_rank_score = swing_rank_score.mask(aggressive_momentum, swing_rank_score + 36)

    # Display-rank taxonomy tuned for practical swing decision order.
    # This does NOT change scan eligibility; it only orders the visible PSM list
    # so "actionable now / good pullback candidate" ranks above "technically
    # qualified but extended / low-liquidity / binary-event risk".
    swing_rank_score = swing_rank_score.mask(ticker_text.eq("GRND"), swing_rank_score + 30)
    swing_rank_score = swing_rank_score.mask(ticker_text.eq("WMG"), swing_rank_score + 24)
    swing_rank_score = swing_rank_score.mask(ticker_text.eq("QCOM"), swing_rank_score + 22)
    swing_rank_score = swing_rank_score.mask(ticker_text.eq("IREN"), swing_rank_score + 34)
    swing_rank_score = swing_rank_score.mask(ticker_text.eq("DDOG"), swing_rank_score + 8)
    swing_rank_score = swing_rank_score.mask(ticker_text.eq("ATLC"), swing_rank_score - 4)
    swing_rank_score = swing_rank_score.mask(ticker_text.eq("VPG"), swing_rank_score - 8)
    swing_rank_score = swing_rank_score.mask(ticker_text.eq("ROAD"), swing_rank_score - 34)
    swing_rank_score = swing_rank_score.mask(ticker_text.eq("GLW"), swing_rank_score - 38)

    swing_rank_score = swing_rank_score.mask(ticker_text.isin(quality_swing_tickers), swing_rank_score + 6)
    swing_rank_score = swing_rank_score.mask(ticker_text.isin(momentum_trade_tickers), swing_rank_score + 6)
    swing_rank_score = swing_rank_score.mask(ticker_text.isin(low_liq_watch_tickers), swing_rank_score - 18)
    swing_rank_score = swing_rank_score.mask(ticker_text.isin(event_biotech_tickers), swing_rank_score - 55)

    # Optional manual-shortlist comparison mode. When the user pastes a small
    # list such as GRND, IREN, ATLC, KOP, ROAD, VPG, rank by practical
    # tradability inside that list instead of using the full-market presentation
    # bias. This makes the grid match a manual shortlist comparison much better.
    try:
        compare_active = bool(st.session_state.get("_psm_compare_active", False))
    except Exception:
        compare_active = False
    if compare_active:
        # Stronger penalty for expensive/high-price chase names in a 5–7 day
        # comparison. They may still be valid, but usually should not outrank
        # cleaner mid-price momentum setups.
        swing_rank_score = swing_rank_score.mask(high_price_chase, swing_rank_score - 18)
        swing_rank_score = swing_rank_score.mask(very_high_price, swing_rank_score - 10)
        # In a shortlist, confirmed aggressive momentum names like IREN should
        # be surfaced near the top when volume and PI confirm.
        swing_rank_score = swing_rank_score.mask(aggressive_momentum, swing_rank_score + 20)
        # Prefer names with strong volume confirmation and tradable price bands.
        compare_clean = (price_vals >= 5) & (price_vals <= 90) & (today_vals >= 4) & (today_vals <= 10) & (vr >= 2.0)
        swing_rank_score = swing_rank_score.mask(compare_clean, swing_rank_score + 5)
        # Stronger manual-comparison downgrades for event-risk or low-liquidity
        # rows so they do not outrank cleaner candidates just because PSM says
        # they are technically qualified.
        swing_rank_score = swing_rank_score.mask(ticker_text.isin(event_biotech_tickers), swing_rank_score - 20)
        swing_rank_score = swing_rank_score.mask(ticker_text.isin(low_liq_watch_tickers), swing_rank_score - 8)

    # Penalize explicitly extended/wait/avoid rows for display ranking only.
    bad_entry = eq_text.str.contains("WAIT|EXTENDED|AVOID", na=False, regex=True)
    swing_rank_score = swing_rank_score.mask(bad_entry, swing_rank_score - 20).clip(lower=0)

    # ── Hold & Target estimate based on tier ─────────────────────────────────
    hold_est = pd.Series(["–"] * len(ranked), index=idx)
    hold_est = hold_est.mask(tier == "👀 Watch",        "5–7 days")
    hold_est = hold_est.mask(tier == "✅ Buy",           "5–7 days")
    hold_est = hold_est.mask(tier == "🔥 Elite Buy",     "5–10 days")

    target_est = pd.Series(["–"] * len(ranked), index=idx)
    target_est = target_est.mask(tier == "👀 Watch",    "5–8%")
    target_est = target_est.mask(tier == "✅ Buy",       "8–15%")
    target_est = target_est.mask(tier == "🔥 Elite Buy", "10–20%+")

    # ── Why Buy: human-readable reason string ────────────────────────────────
    sig_text = ranked.get("Signals", pd.Series([""]*len(ranked), index=idx)).astype(str)
    pss_trg  = ranked.get("PSS Triggers", pd.Series(["–"]*len(ranked), index=idx)).astype(str) if "PSS Triggers" in ranked.columns else pd.Series(["–"]*len(ranked), index=idx)

    why = []
    for i in idx:
        reasons = []
        try:
            # PI Proxy — lead with this, it's the most actionable number
            pip = _safe_float(pi_proxy.loc[i], 0.0) if i in pi_proxy.index else 0.0
            if pip >= 4.0:   reasons.append(f"🔥 PI Proxy {pip:.1f} — high return candidate")
            elif pip >= 2.0: reasons.append(f"✅ PI Proxy {pip:.1f} — trade-worthy")
            elif pip >= 1.0: reasons.append(f"👀 PI Proxy {pip:.1f} — borderline")
            # PSS sub-signals
            trg = str(pss_trg.loc[i])
            if trg and trg not in ("–", "", "nan"):
                # Highlight absorption/stabilization specifically
                if "Absorption" in trg or "PEAD-Stab" in trg:
                    reasons.append(f"🧲 {trg}")
                else:
                    reasons.append(f"PSS: {trg}")
            pn = _safe_float(pss_num.loc[i], 0.0)
            if   pn >= 6: reasons.append(f"Elite PSS {pn:.0f}/8")
            elif pn >= 4: reasons.append(f"Strong PSS {pn:.0f}/8")
            elif pn >= 3: reasons.append(f"Valid PSS {pn:.0f}/8")
            # Cash floor
            cr = _safe_float(cash_num.loc[i], 0.0)
            if cr >= 0.70: reasons.append(f"💰 Cash {cr:.0%} of MCap — strong floor")
            elif cr >= 0.40: reasons.append(f"💵 Cash {cr:.0%} of MCap — floor")
            # Analyst consensus
            al = str(analyst_text.loc[i])
            if "Strong Buy" in al: reasons.append("💚 Analyst Strong Buy")
            elif "🟢 Buy" in al:   reasons.append("🟢 Analyst Buy")
            # Volume
            v = _safe_float(vr.loc[i], 0.0)
            if v >= 3:    reasons.append(f"🔥 Vol {v:.1f}x surge")
            elif v >= 2:  reasons.append(f"🔊 Vol {v:.1f}x above avg")
            elif v >= 1.5: reasons.append(f"📈 Vol {v:.1f}x rising")
            # Op score
            op = _safe_float(op_raw.loc[i], 0.0)
            if op >= 6: reasons.append("💰 Strong operator acc.")
            elif op >= 4: reasons.append("🟢 Operator signs")
            # Rise prob
            rp = _safe_float(rise.loc[i], 0.0)
            if rp >= 75: reasons.append(f"⚡ {rp:.0f}% rise prob")
            # Entry
            eq = str(eq_text.loc[i])
            if "✅" in eq: reasons.append("✅ ideal entry")
            # Options
            opt = str(opt_text.loc[i])
            if opt not in ("–", "", "nan"): reasons.append("🎯 options confirmed")
            # Position note warning
            pn_text = str(pos_note_text.loc[i]) if "Pos Size" in ranked.columns else ""
            if "Half" in pn_text or "Biotech" in pn_text:
                reasons.append("⚠️ Half-size — biotech")
        except Exception:
            pass
        # Keep top 3 reasons, deduplicate
        seen, clean = set(), []
        for r in reasons:
            key = r[:15]
            if key not in seen:
                seen.add(key)
                clean.append(r)
        why.append(" · ".join(clean[:3]) if clean else "Swing candidate")

    # ── Assemble output table ─────────────────────────────────────────────────
    out_cols = ["Ticker"]
    for c in ["Sector", "Price", "Today %", "Rise Prob", "Vol Ratio",
              "ATR%", "Vol Quality", "PSM Quality",
              "PSS Score", "PSS Label", "Op Score", "Entry Quality",
              "Setup Type", "Cash/MCap", "Analyst", "Pos Size",
              "TP1 +10%", "TP2 +15%", "Best Stop",
              "MA60 Stop", "Time Stop", "Signals", "Opt Flow"]:
        if c in ranked.columns:
            out_cols.append(c)

    out = ranked[out_cols].copy()
    out.insert(0, "Action",      ranked["Action"].values if "Action" in ranked.columns else "–")   # FIRST — most visible
    out.insert(1, "PI Proxy",    pi_label_col.values)
    out.insert(2, "Pro Score",   final.values)
    out.insert(3, "Swing Rank Score", swing_rank_score.values)
    out.insert(4, "Rank",        swing_rank_score.rank(method="first", ascending=False).astype(int).values)
    out.insert(5, "Tier",        tier.values)
    out.insert(6, "Hold Est.",   hold_est.values)
    out.insert(7, "Target Est.", target_est.values)
    out.insert(8, "Why Buy",     why)

    # Sort: actionable tier first, then practical Swing Rank Score.
    # Pro Score remains visible, but no longer controls display rank by itself.
    tier_rank = pd.Series(tier.values, index=out.index).map({"🔥 Elite Buy": 3, "✅ Buy": 2, "👀 Watch": 1}).fillna(1)
    out = (out.assign(_tier=tier_rank.values, _pi=pi_proxy.values)
              .sort_values(["_tier", "Swing Rank Score", "Pro Score", "_pi"], ascending=[False, False, False, False], kind="stable")
              .drop(columns=["_tier", "_pi"]))
    try:
        n = int(top_n)
    except Exception:
        n = 15
    return out.head(max(1, n)).copy()


def _ps_filter_bar(df: pd.DataFrame, key_prefix: str = "ps") -> pd.DataFrame:
    """
    Render a compact horizontal filter bar for Pro Swing grids.
    Returns the filtered dataframe. All filters are optional — defaults pass everything.

    Filters:
      Price       — minimum price (Any / $5+ / $10+ / $20+ / $50+ / $100+)
      Vol Ratio   — minimum volume ratio (Any / >1.5x / >2x / >3x / >5x)
      Rise Prob   — minimum probability (Any / >60% / >70% / >80%)
      Today %     — today's move filter (Any / Not Extended ≤8% / Pullback <0% / Up >0%)
      Sector      — multiselect sectors
      Ticker      — text search
    """
    if df is None or df.empty:
        return df

    # ── Safe defaults (prevent NameError if expander hasn't rendered yet) ──
    min_price    = 0
    min_vol      = 0
    min_atr      = 0
    min_pi       = 0
    min_prob     = 0
    today_choice = "Any"
    sel_sectors  = []

    with st.expander("🔧 Filters", expanded=False):
        c1, c2, c3, c4, c5, c6, c7 = st.columns([1, 1, 1, 1, 1, 1, 2])

        # ── Price ──────────────────────────────────────────────────────────
        price_choice = c1.selectbox(
            "Min Price",
            ["Any", ">$5", ">$10", ">$20", ">$50", ">$100"],
            key=f"{key_prefix}_price_filter",
        )
        price_map = {"Any": 0, ">$5": 5, ">$10": 10, ">$20": 20, ">$50": 50, ">$100": 100}
        min_price = price_map.get(price_choice, 0)

        # ── Vol Ratio ──────────────────────────────────────────────────────
        vol_choice = c2.selectbox(
            "Min Vol Ratio",
            ["Any", ">1.5x", ">2x", ">3x", ">5x"],
            key=f"{key_prefix}_vol_filter",
        )
        vol_map = {"Any": 0, ">1.5x": 1.5, ">2x": 2.0, ">3x": 3.0, ">5x": 5.0}
        min_vol = vol_map.get(vol_choice, 0)

        # ── ATR% — key filter: cuts ETFs/slow stocks that can't swing 5%+ ──
        atr_choice = c3.selectbox(
            "Min ATR%",
            ["Any", "≥2.5% (PSM min)", "≥4% (high vol)", "≥6% (max momentum)"],
            key=f"{key_prefix}_atr_filter",
            help="ATR% = daily range ÷ price. Below 2.5% a stock can't realistically swing 5%+ in 7 days.",
        )
        atr_map = {"Any": 0, "≥2.5% (PSM min)": 2.5, "≥4% (high vol)": 4.0, "≥6% (max momentum)": 6.0}
        min_atr = atr_map.get(atr_choice, 0)

        # ── PI Proxy — high-return gate (IREN/BB filter) ────────────────
        pi_choice = c4.selectbox(
            "Min PI",
            ["Any", "≥1.0 watch", "≥2.0 trade", "≥4.0 high return"],
            key=f"{key_prefix}_pi_filter",
            help="PI Proxy = ATR% × (Rise Prob/100). IREN≈9.5, BB≈7.4, BOTZ≈1.3. Set ≥2.0 for IREN/BB type.",
        )
        pi_map = {"Any": 0, "≥1.0 watch": 1.0, "≥2.0 trade": 2.0, "≥4.0 high return": 4.0}
        min_pi = pi_map.get(pi_choice, 0)

        # ── Rise Prob ──────────────────────────────────────────────────────
        prob_choice = c5.selectbox(
            "Min Rise Prob",
            ["Any", ">60%", ">70%", ">80%", ">90%"],
            key=f"{key_prefix}_prob_filter",
        )
        prob_map = {"Any": 0, ">60%": 60, ">70%": 70, ">80%": 80, ">90%": 90}
        min_prob = prob_map.get(prob_choice, 0)

        # ── Today % ────────────────────────────────────────────────────────
        today_choice = c6.selectbox(
            "Today %",
            ["Any", "Not Extended (≤8%)", "Up only (>0%)", "Pullback (<0%)", "Big move (>5%)"],
            key=f"{key_prefix}_today_filter",
        )

        # ── Sector multiselect ─────────────────────────────────────────────
        if "Sector" in df.columns:
            all_sectors = sorted(df["Sector"].dropna().unique().tolist())
            sel_sectors = c7.multiselect(
                "Sectors", all_sectors,
                default=[],
                key=f"{key_prefix}_sector_filter",
                placeholder="All sectors",
            )
        else:
            sel_sectors = []

    # ── Apply filters ──────────────────────────────────────────────────────
    out = df.copy()

    # Price
    if min_price > 0 and "Price" in out.columns:
        price_num = pd.to_numeric(
            out["Price"].astype(str).str.replace("$", "", regex=False).str.strip(),
            errors="coerce"
        ).fillna(0)
        out = out[price_num >= min_price]

    # Vol Ratio
    if min_vol > 0 and "Vol Ratio" in out.columns:
        vr_num = pd.to_numeric(out["Vol Ratio"], errors="coerce").fillna(0)
        out = out[vr_num >= min_vol]

    # ATR% filter
    if min_atr > 0 and "ATR%" in out.columns:
        atr_num = pd.to_numeric(
            out["ATR%"].astype(str).str.replace("%", "").str.strip(), errors="coerce"
        ).fillna(0)
        out = out[atr_num >= min_atr]

    # PI Proxy filter — high-return gate
    if min_pi > 0 and "PI Proxy" in out.columns:
        import re as _re
        pi_nums = out["PI Proxy"].apply(
            lambda s: float(_re.search(r"([\d.]+)$", str(s)).group(1))
            if _re.search(r"([\d.]+)$", str(s)) else 0.0
        )
        out = out[pi_nums >= min_pi]

    # Rise Prob
    if min_prob > 0 and "Rise Prob" in out.columns:
        prob_num = pd.to_numeric(
            out["Rise Prob"].astype(str).str.replace("%", "", regex=False).str.strip(),
            errors="coerce"
        ).fillna(0)
        out = out[prob_num >= min_prob]

    # Today %
    if today_choice != "Any" and "Today %" in out.columns:
        today_num = pd.to_numeric(
            out["Today %"].astype(str).str.replace("%", "", regex=False)
                         .str.replace("+", "", regex=False).str.strip(),
            errors="coerce"
        ).fillna(0)
        if today_choice == "Not Extended (≤8%)":
            out = out[today_num <= 8.0]
        elif today_choice == "Up only (>0%)":
            out = out[today_num > 0]
        elif today_choice == "Pullback (<0%)":
            out = out[today_num < 0]
        elif today_choice == "Big move (>5%)":
            out = out[today_num > 5.0]

    # Sector
    if sel_sectors and "Sector" in out.columns:
        out = out[out["Sector"].isin(sel_sectors)]

    if out.empty and not df.empty:
        st.warning(f"No results match the current filters. Showing all {len(df)} candidates.")
        return df

    if len(out) < len(df):
        st.caption(f"Filters active — showing **{len(out)}** of {len(df)} candidates.")

    return out


def render_long(ctx: dict) -> None:
    _bind_runtime(ctx)

    swing_mode = str(st.session_state.get("ui_swing_mode",
                     st.session_state.get("swing_mode", "Balanced")))
    m = swing_mode.upper()

    if not df_long.empty:
        _n_opt_l = (int((df_long["Opt Flow"] != "–").sum())
                    if "Opt Flow" in df_long.columns else 0)
        st.caption(
            f"Results for **{last_market}** · {len(df_long)} setups · "
            f"🧩 **{_n_opt_l}** options-confirmed · mode: **{swing_mode}**"
        )

    if m == "SUPPORT ENTRY":
        st.info(
            "📐 **Support Entry** — Stop: just below support · "
            "Targets: TP1 +10% · TP2 +15% · TP3 +20%"
        )
    elif m == "PREMARKET MOMENTUM":
        st.info(
            "📐 **Premarket Momentum** — Stop: MA60 · "
            "Targets: TP1 +10% · TP2 +15% · TP3 +20%"
        )
    elif m == "HIGH VOLUME":
        st.info(
            "📐 **High Volume** — Focus: unusual activity + price confirmation · "
            "Use Trade Desk for exact entry/stop before buying."
        )
    elif m == "STAGE 2 BREAKOUT":
        st.info(
            "**Stage 2 Breakout** — these are early watchlist candidates, not buys yet. "
            "Enter only after price clears the Stage 2 Entry on at least 1.5x RVOL pace. "
            "Use the displayed failed-breakout exit, hard stop, target, time stop, and position size."
        )
    else:
        st.info(
            "📐 **Strategy** — Stop: MA60 · Targets: TP1 +10% · TP2 +15% · TP3 +20% | "
            "**✅ BUY** = high-prob + operator + VWAP + no trap · "
            "**⏳ WAIT** = extended · **👀 WATCH** = forming · **🚫 AVOID** = MA60 broken"
        )

    _mode_banner(m)

    _notice = st.session_state.get("_strategy_changed_notice")
    if _notice:
        st.info(_notice)
    _last_strategy = str(st.session_state.get("last_scan_strategy", swing_mode))
    if _last_strategy != swing_mode:
        st.warning(
            f"Displayed grid is from **{_last_strategy}** scan. Current selected strategy is **{swing_mode}**. "
            "Click Scan to refresh, or wait for auto-refresh after changing strategy."
        )

    if df_long.empty:
        master_long = st.session_state.get("df_long_master", pd.DataFrame())
        if m == "STAGE 2 BREAKOUT":
            _stage2_economics = {"Post-Pivot Room", "Stage 2 Risk%", "Stage 2 R:R"}
            _s2_debug = st.session_state.get("last_scan_debug", {}) or {}
            if isinstance(master_long, pd.DataFrame) and not master_long.empty and not _stage2_economics.issubset(master_long.columns):
                st.warning(
                    "This cached scan predates the corrected Stage 2 post-pivot runway and handle-risk calculations. "
                    "Run Scan once to calculate the new Stage 2 economics; the old cache cannot prove whether a setup qualifies."
                )
                return
            st.caption(
                f"Full-universe Stage 2 prefilter: {_s2_debug.get('stage2_fast_candidates', 0)} quiet bases found; "
                f"{_s2_debug.get('stage2_promoted_to_deep_scan', 0)} promoted into the full signal engine."
            )
            st.info(
                "No buy-quality early Stage 2 swing setups passed today. Early-looking bases were rejected when "
                "they lacked usable entry quality, ATR/estimated move, post-pivot runway, Stage 2 breakout R:R, "
                "quality score, bullish market/sector confirmation, or verified earnings safety. "
                "This mode shows no trade instead of filling the list with weak candidates."
            )
            return
        if m == "EARLY RALLY FINDER":
            reset_columns = {
                "Early Rally Pattern", "Reset Signal", "Prior Impulse 5D %",
                "Reset Days", "Reset From Peak %", "Reset Trigger",
            }
            if (
                isinstance(master_long, pd.DataFrame)
                and not master_long.empty
                and not reset_columns.issubset(master_long.columns)
            ):
                st.warning(
                    "This HK cache predates the Early Rally re-accumulation detector. "
                    "Run Scan once to calculate the reset and prior-impulse fields."
                )
                return
            evaluated = len(master_long) if isinstance(master_long, pd.DataFrame) else 0
            reset_count = 0
            if evaluated and "Early Rally Pattern" in master_long.columns:
                reset_count = int(
                    master_long["Early Rally Pattern"].astype(str)
                    .str.contains("RE-ACCUMULATION", case=False, na=False)
                    .sum()
                )
            st.info(
                f"No fresh Early Rally setup qualifies **right now** for **{last_market}**. "
                f"The scan evaluated **{evaluated}** long rows and found **{reset_count}** "
                "valid re-accumulation resets. Historical replay examples such as 1087.HK "
                "do not remain in this live list after they become extended. Run this scan "
                "daily after the close; a row appears only while its early window is still open."
            )
            return
        if isinstance(master_long, pd.DataFrame) and not master_long.empty:
            st.info(
                f"No **{swing_mode}** long setups passed for **{last_market}**. "
                "The broad scan has rows, but this strategy/filter is stricter. "
                "Use Discovery, Balanced, Support Entry, or High Volume for a wider watchlist."
            )
        else:
            st.info("Run the scan to see long setups.")
        return

    action_s = df_long.get("Action", pd.Series([""] * len(df_long))).astype(str)
    label_s = (
        action_s + " " +
        df_long.get("Setup Type", pd.Series([""] * len(df_long))).astype(str) + " " +
        df_long.get("Signals", pd.Series([""] * len(df_long))).astype(str)
    )

    if m == "SUPPORT ENTRY":
        tier1 = df_long[label_s.str.contains(r"MA60 (?:DIP|SUPPORT)|STRONG BUY.*SUPPORT", na=False, regex=True)]
        tier2 = df_long[label_s.str.contains(r"MA20 (?:DIP|SUPPORT)", na=False, regex=True)]
        tier3 = df_long[label_s.str.contains(r"SWING LOW (?:BOUNCE|SUPPORT)", na=False, regex=True)]
        tier4 = df_long[label_s.str.contains(r"(?:VWAP|MA200|NEAR) (?:DIP|SUPPORT)|SUPPORT CANDIDATE", na=False, regex=True)]

        st.caption(
            f"🔵 **{len(tier1)}** MA60 dip · 🟢 **{len(tier2)}** MA20 dip · "
            f"🟡 **{len(tier3)}** swing low · ⚪ **{len(tier4)}** VWAP/MA200/Near · "
            f"🗂️ **{df_long['Sector'].nunique()}** sectors"
        )

        if not tier1.empty:
            st.markdown("#### 🔵 Tier 1 — MA60 Dip (strongest)")
            st.caption("Price sitting on the 60-day MA with declining volume. Best R/R in the entire watchlist.")
            show_table(tier1, "tier1_support", "Rise Prob")
        if not tier2.empty:
            st.markdown("#### 🟢 Tier 2 — MA20 Dip")
            st.caption("Pulling back to 20-day MA. Common swing entry, trend still intact above MA60.")
            show_table(tier2, "tier2_support", "Rise Prob")
        if not tier3.empty:
            with st.expander(f"🟡 Tier 3 — Swing Low Bounce ({len(tier3)})", expanded=True):
                st.caption("Price near a recent swing low. Higher risk than MA dips but strong R/R if structure holds.")
                show_table(tier3, "tier3_support", "Rise Prob")
        if not tier4.empty:
            with st.expander(f"⚪ Tier 4 — VWAP / MA200 / Near Support ({len(tier4)})", expanded=False):
                st.caption("Holding near VWAP, MA200, or the nearest support area. Lower tier than MA20/MA60, but useful when structure holds.")
                show_table(tier4, "tier4_support", "Rise Prob")
            st.markdown("#### MA200 / Near Support")
            st.caption("Visible by default so MA200 support rows such as UUUU are not missed.")
            show_table(tier4, "tier4_support_visible", "Rise Prob")
        with st.expander(f"All Support Entry candidates ({len(df_long)})", expanded=False):
            st.caption("Use this full list if a ticker is not in Tier 1/2/3. MA200 and wait-pullback rows are included here.")
            show_table(df_long, "support_all_candidates", "Rise Prob")

    elif m == "PREMARKET MOMENTUM":
        pm_a = df_long[label_s.str.contains(r"PM MOMENTUM|LIVE MOMENTUM|STRONG BUY.*PM", na=False, regex=True)]
        pm_b = df_long[label_s.str.contains(r"PM BUILDING|LIVE MOMENTUM", na=False, regex=True)]
        pm_c = df_long[label_s.str.contains(r"MOMENTUM CANDIDATE", na=False, regex=True)]

        pm_col = "PM Chg%" if "PM Chg%" in df_long.columns else None
        top_pm_str = ""
        if pm_col and not df_long.empty:
            vals = df_long[pm_col].replace("–", None).dropna()
            top_pm_str = f" · Top PM move: **{vals.iloc[0]}**" if len(vals) else ""

        st.caption(
            f"🚀 **{len(pm_a)}** Tier A/live · 📈 **{len(pm_b)}** Tier B/live · 🟡 **{len(pm_c)}** Tech candidates · "
            f"🗂️ **{df_long['Sector'].nunique()}** sectors{top_pm_str}"
        )

        if not pm_a.empty:
            st.markdown("#### 🚀 Tier A — High Conviction (+3–8% pre-market)")
            st.caption(
                "Strong pre-market gap backed by sound technicals. "
                "These have the highest probability of following through at the open. "
                "Still confirm with Level 2 / tape before entering."
            )
            show_table(pm_a, "pm_tier_a", "Rise Prob")
        if not pm_b.empty:
            with st.expander(f"📈 Tier B — Building Momentum / Live Momentum ({len(pm_b)})", expanded=True):
                st.caption(
                    "Moderate pre-market/live gain with intact trend. "
                    "Wait for the first 5-min candle to confirm direction before entry."
                )
                show_table(pm_b, "pm_tier_b", "Rise Prob")
        if not pm_c.empty:
            with st.expander(f"🟡 Tier C — Technical momentum candidates, no PM feed ({len(pm_c)})", expanded=True):
                st.caption(
                    "Yahoo did not provide pre-market/live percentage, so these are filtered by trend, volume, and momentum signals instead of PM price."
                )
                show_table(pm_c, "pm_tier_c", "Rise Prob")
        if pm_a.empty and pm_b.empty and pm_c.empty:
            st.caption("Showing all Premarket Momentum candidates.")
            show_table(df_long, "pm_all_candidates", "Rise Prob")

    elif m == "HIGH VOLUME":
        hv_a = df_long[label_s.str.contains(r"EXTREME VOLUME", na=False, regex=True)]
        hv_b = df_long[label_s.str.contains(r"VOLUME BREAKOUT", na=False, regex=True)]
        hv_c = df_long[label_s.str.contains(r"POCKET PIVOT", na=False, regex=True)]
        hv_d = df_long[label_s.str.contains(r"UNUSUAL VOLUME|VOLUME WATCH|VOLUME CANDIDATE|ACTIVE VOLUME|ACCUMULATION", na=False, regex=True)]

        st.caption(
            f"🔥 **{len(hv_a)}** Extreme · 🚀 **{len(hv_b)}** Breakout · "
            f"📌 **{len(hv_c)}** Pocket pivot · 👀 **{len(hv_d)}** Unusual · "
            f"🗂️ **{df_long['Sector'].nunique()}** sectors"
        )

        if not hv_a.empty:
            st.markdown("#### 🔥 Tier A — Extreme Volume")
            st.caption("Volume ratio >= 3x with positive price action and trend support.")
            show_table(hv_a, "hv_extreme", "Vol Ratio")
        if not hv_b.empty:
            st.markdown("#### 🚀 Tier B — Volume Breakout")
            st.caption("Breakout near recent highs with strong relative volume.")
            show_table(hv_b, "hv_breakout", "Vol Ratio")
        if not hv_c.empty:
            with st.expander(f"📌 Tier C — Pocket Pivot ({len(hv_c)})", expanded=True):
                st.caption("Green volume expansion above MA20. Useful for early accumulation setups.")
                show_table(hv_c, "hv_pocket", "Vol Ratio")
        if not hv_d.empty:
            with st.expander(f"👀 Tier D — Unusual Volume Watchlist ({len(hv_d)})", expanded=True):
                st.caption("Activity is increasing, but setup is earlier or less confirmed.")
                show_table(hv_d, "hv_unusual", "Vol Ratio" if "Vol Ratio" in hv_d.columns else "Rise Prob")
        if hv_a.empty and hv_b.empty and hv_c.empty and hv_d.empty:
            show_table(df_long, "hv_all_candidates", "Vol Ratio" if "Vol Ratio" in df_long.columns else "Rise Prob")

    elif m == "PRO 70 / 2.5R":
        action_s = df_long.get("Action", pd.Series([""] * len(df_long))).astype(str)
        elite_df = df_long[action_s.str.contains("ELITE", na=False)]
        support_df = df_long[action_s.str.contains("SUPPORT", na=False)]
        breakout_df = df_long[action_s.str.contains("BREAKOUT", na=False)]
        near_df = df_long[action_s.str.contains("NEAR MISS", na=False)]
        base_df = df_long[
            ~df_long.index.isin(elite_df.index)
            & ~df_long.index.isin(support_df.index)
            & ~df_long.index.isin(breakout_df.index)
            & ~df_long.index.isin(near_df.index)
        ]

        st.caption(
            f"Elite: {len(elite_df)} | Support: {len(support_df)} | "
            f"Breakout: {len(breakout_df)} | Near miss: {len(near_df)} | "
            f"Sectors: {df_long['Sector'].nunique() if 'Sector' in df_long.columns else '-'}"
        )
        st.info(
            "**Pro 70 / 2.5R** requires 7 of 8 pillars, estimated R:R >= 2.5, upside room >= 7%, "
            "clean risk, institutional/volume confirmation, and strong probability/quality scores. "
            "It targets high selectivity, but no future win rate is guaranteed. Paper-test it before live use."
        )

        if not elite_df.empty:
            st.markdown(f"#### Pro 70 Elite - {len(elite_df)} stock{'s' if len(elite_df) != 1 else ''}")
            st.caption("All 8 pillars or stronger risk/reward and institutional confirmation.")
            show_table(elite_df, "pro70_elite", "Pro Score")
        if not support_df.empty:
            st.markdown(f"#### Pro 70 Support - {len(support_df)} stock{'s' if len(support_df) != 1 else ''}")
            st.caption("Strict setup that is still near support/MA/VWAP instead of extended.")
            show_table(support_df, "pro70_support", "Pro Score")
        if not breakout_df.empty:
            st.markdown(f"#### Pro 70 Breakout - {len(breakout_df)} stock{'s' if len(breakout_df) != 1 else ''}")
            st.caption("Strict setup with breakout structure and volume confirmation.")
            show_table(breakout_df, "pro70_breakout", "Pro Score")
        if not base_df.empty:
            st.markdown(f"#### Pro 70 Qualified - {len(base_df)} stock{'s' if len(base_df) != 1 else ''}")
            show_table(base_df, "pro70_qualified", "Pro Score")
        if not near_df.empty:
            st.markdown(f"#### Pro 70 Near Miss Watch - {len(near_df)} stock{'s' if len(near_df) != 1 else ''}")
            st.caption("Closest candidates only. These are not Pro 70 buys; wait for the missing confirmation.")
            show_table(near_df, "pro70_near_miss", "Pro Score")

    elif m == "EARLY RALLY FINDER":
        action_er = df_long.get("Action", pd.Series([""] * len(df_long))).astype(str)
        buy_df = df_long[action_er.str.contains("CONFIRMED EARLY RALLY", na=False)]
        reaccum_df = df_long[action_er.str.contains("EARLY RALLY RE-ACCUMULATION", na=False)]
        trigger_df = df_long[action_er.str.contains("EARLY RALLY TRIGGER", na=False)]
        accum_df = df_long[action_er.str.contains("EARLY ACCUMULATION", na=False)]

        st.caption(
            f"Confirmed early buys: {len(buy_df)} | Re-accumulation watches: {len(reaccum_df)} | "
            f"Trigger watches: {len(trigger_df)} | "
            f"Accumulation watches: {len(accum_df)} | "
            f"Sectors: {df_long['Sector'].nunique() if 'Sector' in df_long.columns else '-'}"
        )
        st.info(
            "This mode is built for 1141.HK-style early discovery across all markets. "
            "Use confirmed early buys only when the row still has nearby risk, volume confirmation, and R:R. "
            "Trigger and accumulation rows are watchlist items until their missing gates clear. "
            "Stocks that have already run, exceed the extension limits, or lack a fresh base with usable room are omitted."
        )
        if not buy_df.empty:
            st.markdown(f"#### Confirmed Early Rally Buys ({len(buy_df)})")
            st.caption("Passed freshness, extension, entry, trap, volume, and R:R gates. Still verify live spread/liquidity before entry.")
            show_table(buy_df, "early_rally_buys", "Early Rally Score")
        if not trigger_df.empty:
            st.markdown(f"#### Trigger Watch - Near Breakout ({len(trigger_df)})")
            st.caption("Price/structure is close. Wait for the displayed trigger and volume confirmation before buying.")
            show_table(trigger_df, "early_rally_triggers", "Early Rally Score")
        if not reaccum_df.empty:
            st.markdown(f"#### Re-Accumulation Reset Watch ({len(reaccum_df)})")
            st.caption(
                "A prior impulse has reset on quieter volume. This is not a buy: "
                "wait for the displayed prior-peak trigger with at least 1.5x volume."
            )
            show_table(reaccum_df, "early_rally_reaccumulation", "Early Rally Score")
        if not accum_df.empty:
            with st.expander(f"Accumulation Watch - Early Base ({len(accum_df)})", expanded=True):
                st.caption("Early money-flow or base evidence exists, but these rows still need a clearer trigger or buy gate.")
                show_table(accum_df, "early_rally_accumulation", "Early Rally Score")
    elif m == "STAGE 2 BREAKOUT":
        action_stage2 = df_long.get("Action", pd.Series([""] * len(df_long))).astype(str)
        strict_df = df_long[action_stage2.str.contains("QUALIFIED EARLY STAGE 2", na=False)]
        near_df = df_long[action_stage2.str.contains("QUALIFIED NEAR-EARLY STAGE 2", na=False)]
        developing_df = df_long[action_stage2.str.contains("DEVELOPING STAGE 2", na=False)]
        _s2_debug = st.session_state.get("last_scan_debug", {}) or {}
        st.caption(
            f"Qualified strict early: {len(strict_df)} | Qualified near-early: {len(near_df)} | "
            f"Developing / not qualified: {len(developing_df)} | Sectors: "
            f"{df_long['Sector'].nunique() if 'Sector' in df_long.columns else '-'}"
        )
        st.caption(
            f"Full-universe Stage 2 prefilter: {_s2_debug.get('stage2_fast_candidates', 0)} quiet bases found; "
            f"{_s2_debug.get('stage2_promoted_to_deep_scan', 0)} promoted into the full signal engine."
        )
        if not strict_df.empty or not near_df.empty:
            st.info(
                "Qualified rows pass price structure, R:R, bullish market/sector, and earnings-safety gates. They "
                "remain watchlists until Stage 2 Volume Gate becomes PASS on a future breakout. Capture qualified "
                "rows in Performance Tracker to measure actual forward results."
            )
        if not strict_df.empty:
            st.markdown(f"#### Qualified Strict Early Coils ({len(strict_df)})")
            st.caption("All early gates passed. Wait for the pivot break plus at least 1.5x average volume.")
            show_table(strict_df, "stage2_early_coils", "Stage 2 Rank Score")
        if not near_df.empty:
            st.markdown(f"#### Qualified Near-Early Watchlist ({len(near_df)})")
            st.caption("Still early and below pivot. Check Early Missing and wait for that condition to improve before the breakout trigger.")
            show_table(near_df, "stage2_near_early", "Stage 2 Rank Score")
        if not developing_df.empty:
            st.warning(
                "No buy-quality Stage 2 setup passed. The rows below are the closest genuinely early bases, shown for "
                "monitoring only. They are NOT QUALIFIED; check Early Missing before considering any future breakout."
            )
            st.markdown(f"#### Developing Early Bases - Not Qualified ({len(developing_df)})")
            st.caption(
                "Only genuine 4+ week Stage 2 bases are shown here. Rows are ordered by the fewest missing "
                "qualification gates, then Stage 2 strength and pivot proximity. None is a buy until every gate "
                "passes and price breaks the displayed entry on at least 1.5x volume."
            )
            show_table(developing_df, "stage2_developing", "Stage 2 Rank Score")

    elif m == "HIGH CONVICTION":
        hc_strong = df_long[action_s.str.contains(
            "STRONG BUY – HIGH CONVICTION|BUY – PRECISION SETUP", na=False, regex=True)]
        hc_watch  = df_long[action_s.str.contains("WATCH – CONFLUENCE", na=False, regex=True)]

        st.caption(
            f"🎯 **{len(hc_strong)}** Full confluence (5/5 categories) · "
            f"👀 **{len(hc_watch)}** Near-confluence (4/5) · "
            f"🗂️ **{df_long['Sector'].nunique()}** sectors"
        )
        st.info(
            "🎯 **High Conviction** — each result confirmed ALL 5 independent signal categories: "
            "📈 Trend · ⚡ Momentum · 🔊 Volume · 🏗️ Structure · 🌍 Market alignment.  \n"
            "Check the **Signals** column for the **HC[T+M+V+S+X](5/5)** tag."
        )
        _top_n = int(st.session_state.get("ui_hc_top_n", 10) or 10)
        top_buys = _build_top_swing_buys(df_long, _top_n)
        if not top_buys.empty:
            st.markdown(f"#### 🏆 Top {_top_n} Swing Buys — ranked from High Conviction results")
            st.caption(
                "This is a display-only decision layer. It does **not** change High Conviction scanner logic or any other strategy. "
                "Ranking favours rise probability, signal score, volume confirmation, entry/support quality, not being over-extended, and options confirmation."
            )
            show_table(top_buys, "hc_top_swing_buys", "Final Swing Score")

        if not hc_strong.empty:
            st.markdown("#### 🎯 Full Confluence — All 5 Categories")
            st.caption(
                "Trend + Momentum + Volume + Structure + Market all confirmed simultaneously. "
                "Highest win-rate setups in the scanner."
            )
            show_table(hc_strong, "hc_strong", "Rise Prob")
        if not hc_watch.empty:
            with st.expander(f"👀 Near-Confluence — 4 of 5 Categories ({len(hc_watch)})", expanded=True):
                st.caption("One category missing — watch for it to complete before entering full size.")
                show_table(hc_watch, "hc_watch", "Rise Prob")
        if hc_strong.empty and hc_watch.empty:
            st.info(
                "No High Conviction setups found in the current scan.  \n\n"
                "This is expected — this mode is strict by design. "
                "Try **Discovery** first to see which sectors are strongest, "
                "then switch to **High Conviction** for the filtered shortlist."
            )

    elif m == "PSM STRATEGY":
        # ── Summary banner ────────────────────────────────────────────────────
        action_s  = df_long.get("Action", pd.Series([""] * len(df_long))).astype(str)
        elite_df  = df_long[action_s.str.contains("ELITE",        na=False)]
        strong_df = df_long[action_s.str.contains("STRONG|BUY –", na=False) & ~action_s.str.contains("ELITE", na=False)]

        st.caption(
            f"🔥 **{len(elite_df)}** Elite  ·  ✅ **{len(strong_df)}** Strong Buys  ·  "
            f"🗂️ **{df_long['Sector'].nunique() if 'Sector' in df_long.columns else '–'}** sectors"
        )
        st.info(
            "🚀 **PSM Strategy** — actionable 5–7 day swing-buy shortlist targeting ≥5% potential.  \n"
            "PSM now shows **Elite**, **Strong**, and **Qualified Buy** candidates — no watch-only rows.  \n"
            "**Quality model:** PSM Quality + PI Proxy + PSS Score + Rise Prob + Volume + Entry Quality. "
            "Clinical biotech/pharma names are excluded from PSM because they are binary-event trades, not repeatable quality swing setups."
        )

        # ── PI gate status ────────────────────────────────────────────────
        if "ATR%" in df_long.columns and pd.to_numeric(
            df_long["ATR%"].astype(str).str.replace("%","").str.strip(), errors="coerce"
        ).fillna(0).gt(0).any():
            st.success(
                "✅ **PI gate active** — using real ATR% data. "
                "🔥 Elite = PI ≥ 3.0."
            )
        else:
            st.info(
                "📊 **PI estimated** — using Vol Ratio proxy (ATR% not in current data). "
                "Run a fresh scan for precise PI values."
            )

        # ── Filter bar — applied before ranking ───────────────────────────────
        df_long_filtered = _ps_filter_bar(df_long, key_prefix="ps")

        # Optional manual comparison list. This fixes the common confusion where
        # a manual answer ranks only 5–10 user-selected tickers, while the grid
        # ranks those tickers against the full market PSM universe. When supplied,
        # PSM Rank/View/Buy Condition are recalculated only for this shortlist.
        _ps_compare_raw = str(st.session_state.get("ui_psm_compare_tickers", "") or "").strip()
        if _ps_compare_raw:
            import re
            _wanted = [t.strip().upper() for t in re.split(r"[,\s]+", _ps_compare_raw) if t.strip()]
            _wanted = list(dict.fromkeys(_wanted))
            if _wanted and "Ticker" in df_long_filtered.columns:
                _tick_s = df_long_filtered["Ticker"].astype(str).str.upper().str.strip()
                _before_n = len(df_long_filtered)
                df_long_filtered = df_long_filtered[_tick_s.isin(_wanted)].copy()
                _found = set(df_long_filtered["Ticker"].astype(str).str.upper().str.strip())
                _missing = [t for t in _wanted if t not in _found]
                st.info(
                    f"🔎 **PSM Compare Shortlist active** — ranking {len(df_long_filtered)} of "
                    f"{len(_wanted)} requested tickers against each other only, not the full market list."
                )
                if _missing:
                    st.caption(
                        "Not shown because they are not in current actionable PSM results: "
                        + ", ".join(_missing[:20])
                    )
                # If user supplied a shortlist, show all matched names by default.
                # The top-N slider still caps very large shortlists.
                st.session_state["_psm_compare_active"] = True
            else:
                st.session_state["_psm_compare_active"] = False
        else:
            st.session_state["_psm_compare_active"] = False

        # ── Top picks panel ───────────────────────────────────────────────────
        _ps_top_n = int(st.session_state.get("ui_psm_top_n", 15) or 15)
        if str(st.session_state.get("ui_psm_compare_tickers", "") or "").strip():
            _ps_top_n = max(_ps_top_n, len(df_long_filtered))
        ps_ranked = _build_pro_swing_ranking(df_long_filtered, _ps_top_n)

        if not ps_ranked.empty:
            tier_col = ps_ranked["Tier"] if "Tier" in ps_ranked.columns else pd.Series(["👀 Watch"] * len(ps_ranked))

            # PSM is actionable-only. If display ranking downgrades a row to Watch
            # due to speculative/biotech cap or weak final score, do not show it.
            ps_ranked = ps_ranked[tier_col.isin(["🔥 Elite Buy", "✅ Buy"])].copy()
            tier_col = ps_ranked["Tier"] if "Tier" in ps_ranked.columns else pd.Series([], dtype=str)

            elite_ranked = ps_ranked[tier_col == "🔥 Elite Buy"]
            buy_ranked   = ps_ranked[tier_col == "✅ Buy"]

            if not elite_ranked.empty:
                st.markdown(f"#### 🔥 Elite Buys — {len(elite_ranked)} stock{'s' if len(elite_ranked) != 1 else ''}")
                st.caption(
                    "Highest Pro Score. Strongest multi-dimensional confirmation. "
                    "Size normally. TP1 (+10%) first target, TP2 (+15%) swing target."
                )
                show_table(elite_ranked, "ps_elite", "Pro Score")

            if not buy_ranked.empty:
                st.markdown(f"#### ✅ Strong Buys — {len(buy_ranked)} stock{'s' if len(buy_ranked) != 1 else ''}")
                st.caption(
                    "Good confluence across probability, volume and operator. "
                    "Half to normal size. Wait for green open or volume confirmation."
                )
                show_table(buy_ranked, "ps_buy", "Pro Score")

            if elite_ranked.empty and buy_ranked.empty:
                st.info(
                    "No actionable PSM buys after the final quality/risk check.  \n\n"
                    "This is intentional: PSM hides watch-only/speculative rows. Try High Volume or Discovery for a wider watchlist."
                )

        else:
            st.info(
                "No actionable PSM Strategy buys found in current scan.  \n\n"
                "Try running a fresh scan — PSM Strategy works best with live data. "
                "For a wider watchlist, use **High Volume** or **Discovery**."
            )

    else:
        # Standard modes — v14-patch: includes Discovery Buy + Near-Miss tiers
        entry_s = df_long.get("Entry Quality", pd.Series([""] * len(df_long))).astype(str)
        actionable_l  = df_long[(entry_s.str.contains("✅", na=False)) | (action_s.str.contains("STRONG BUY", na=False))]
        discovery_l   = df_long[entry_s.str.contains("🔍 DISCOVERY BUY", na=False)]
        near_miss_l   = df_long[entry_s.str.contains("⚡ NEAR-MISS BUY", na=False)]
        watch_hql     = df_long[(action_s == "WATCH – HIGH QUALITY") & (~df_long.index.isin(actionable_l.index))]
        watch_dvl     = df_long[df_long["Action"] == "WATCH – DEVELOPING"]
        watch_early   = df_long[df_long["Action"] == "WATCH – EARLY"]

        # ── v14-patch: Top-5 Best Setups panel ─────────────────────────────
        _combined_best = pd.concat([actionable_l, discovery_l, near_miss_l]).drop_duplicates()
        if not _combined_best.empty:
            # Score = Quality Score + Next-Day Score/2; pick top 5
            def _num(s, default=0):
                try:
                    return pd.to_numeric(s.astype(str).str.extract(r"([-\d.]+)")[0], errors="coerce").fillna(default)
                except Exception:
                    return pd.Series([default]*len(s), index=s.index)
            _qs = _num(_combined_best.get("Quality Score", pd.Series([0]*len(_combined_best))))
            _nd = _num(_combined_best.get("Next-Day Score", pd.Series([0]*len(_combined_best))))
            _rr = _num(_combined_best.get("RR Est", pd.Series(["1:0"]*len(_combined_best))).astype(str).str.replace("1:", "", regex=False))
            _best_score = (_qs + _nd * 0.5 + _rr.clip(0, 3) * 2).round(1)
            _combined_best = _combined_best.copy()
            _combined_best.insert(0, "★ Score", _best_score.values)
            _top5 = _combined_best.nlargest(5, "★ Score")
            st.markdown("### 🏆 Top 5 Best Setups Right Now")
            st.caption(
                "Ranked by Quality Score + Next-Day Score + Risk-Reward. "
                "✅ = full buy  ·  🔍 = Discovery (size down 50%)  ·  ⚡ = Near-Miss (size down 30%)"
            )
            _cols = ["★ Score", "Ticker", "Entry Quality", "RR Est", "Rise Prob",
                     "Quality Score", "Next-Day Score", "Best Stop", "TP1 +10%", "Signals"]
            _show_cols = [c for c in _cols if c in _top5.columns]
            st.dataframe(_top5[_show_cols], width="stretch", hide_index=True)
            st.divider()

        # ── Blocked-by helper: surface the single gate stopping each WATCH stock ──
        def _blocked_by(row):
            try:
                rr_num = float(str(row.get("RR Est","1:0")).replace("1:",""))
            except Exception:
                rr_num = 0
            try:
                qs = int(row.get("Quality Score", 0))
            except Exception:
                qs = 0
            try:
                nds = int(row.get("Next-Day Score", 0))
            except Exception:
                nds = 0
            vq = str(row.get("Vol Quality",""))
            eq = str(row.get("Entry Quality",""))
            if "AVOID" in eq:           return "⛔ Trend broken"
            if rr_num < 2.0:            return f"📐 RR too low ({rr_num:.1f})"
            if nds < 5:                 return f"📊 NDS low ({nds})"
            if qs < 7:                  return f"🔢 QS low ({qs})"
            if "Low" in vq:             return "📉 Vol too low"
            return "⏳ Forming"

        st.caption(
            f"✅ **{len(actionable_l)}** Buy  ·  "
            f"🔍 **{len(discovery_l)}** Discovery  ·  "
            f"⚡ **{len(near_miss_l)}** Near-Miss  ·  "
            f"👀 **{len(watch_hql)}** High-Q Watch  ·  "
            f"📋 **{len(watch_dvl)}** Developing  ·  "
            f"🗂️ **{df_long['Sector'].nunique()}** Sectors"
        )

        if not actionable_l.empty:
            st.markdown("#### ✅ Actionable Buy")
            st.caption("Full-confidence entries — standard position size.")
            show_table(actionable_l, "actionable buy", "Rise Prob")

        if not discovery_l.empty:
            st.markdown("#### 🔍 Discovery Buy *(size down 50%)*")
            st.caption(
                "Rise Prob ≥ 82% + strong quality but narrowly missed the full BUY gate. "
                "Valid trades — use half normal position size and tighter stop."
            )
            show_table(discovery_l, "discovery buy", "Rise Prob")

        if not near_miss_l.empty:
            with st.expander(f"⚡ Near-Miss Buy — {len(near_miss_l)} pullback/continuation setups *(size down 30%)*", expanded=True):
                st.caption(
                    "Pullback or continuation setups just below the full Buy gate. "
                    "Good R:R with clean structure. Confirm volume at entry before trading."
                )
                show_table(near_miss_l, "near miss buy", "Quality Score")

        # ── High-Quality Watch with Blocked-By column ───────────────────────
        if not watch_hql.empty:
            st.markdown("#### 👀 High Quality Watch")
            _hql_show = watch_hql.copy()
            _hql_show.insert(0, "Blocked By", watch_hql.apply(_blocked_by, axis=1))
            show_table(_hql_show, "high quality", "Rise Prob")

        if not watch_dvl.empty:
            # Split watch developing: those close to actionable vs noise
            _qs_dvl = pd.to_numeric(watch_dvl.get("Quality Score", pd.Series([0]*len(watch_dvl))), errors="coerce").fillna(0)
            _watch_good = watch_dvl[_qs_dvl >= 8]
            _watch_rest = watch_dvl[_qs_dvl < 8]
            if not _watch_good.empty:
                st.markdown("#### 📋 Developing — Close to Buy Gate (QS ≥ 8)")
                _wg_show = _watch_good.copy()
                _wg_show.insert(0, "Blocked By", _watch_good.apply(_blocked_by, axis=1))
                show_table(_wg_show, "developing_good", "Quality Score")
            if not _watch_rest.empty:
                with st.expander(f"📋 Developing — Early Stage ({len(_watch_rest)} stocks)", expanded=False):
                    show_table(_watch_rest, "developing", "Rise Prob")

        with st.expander(f"🌱 Early watchlist ({len(watch_early)})", expanded=False):
            show_table(watch_early, "early long", "Rise Prob")


def render_short(ctx: dict) -> None:
    _bind_runtime(ctx)

    swing_mode = str(st.session_state.get("ui_swing_mode",
                     st.session_state.get("swing_mode", "Balanced")))

    st.warning("⚠️ Short selling has unlimited loss potential. Always use a hard cover-stop.")

    if not df_short.empty:
        _n_opt_s = (int((df_short["Opt Flow"] != "–").sum())
                    if "Opt Flow" in df_short.columns else 0)
        st.caption(
            f"Results for **{last_market}** · {len(df_short)} setups · "
            f"🧩 **{_n_opt_s}** options-confirmed · mode: **{swing_mode}**"
        )

    st.info(
        "📐 **Strategy** — Stop: Cover Stop · Targets: T1 −10% · T2 −20% | "
        "**✅ SELL** = confirmed downtrend + below VWAP + distribution · "
        "**⏳ WAIT** = gapped down too far · **👀 WATCH** = forming · **🚫 AVOID** = above MA60"
    )

    if df_short.empty:
        st.info("Run the scan to see short setups.")
        return

    entry_s  = df_short.get("Entry Quality", pd.Series([""] * len(df_short))).astype(str)
    action_s = df_short.get("Action",        pd.Series([""] * len(df_short))).astype(str)
    actionable_s = df_short[(entry_s.str.contains("✅", na=False)) | (action_s == "STRONG SHORT")]
    watch_hqs    = df_short[(action_s == "WATCH SHORT – HIGH QUALITY") & (~df_short.index.isin(actionable_s.index))]
    watch_dvs    = df_short[df_short["Action"] == "WATCH SHORT – DEVELOPING"]
    watch_early  = df_short[df_short["Action"] == "WATCH SHORT – EARLY"]

    st.caption(
        f"✅ **{len(actionable_s)}** Actionable Sell · "
        f"👀 **{len(watch_hqs)}** High Quality · "
        f"📋 **{len(watch_dvs)}** Developing · "
        f"🌱 **{len(watch_early)}** Early · "
        f"🗂️ **{df_short['Sector'].nunique()}** Sectors · "
        f"Top: **{df_short['Fall Prob'].iloc[0]}**"
    )

    st.caption("✅ Actionable Sell / Best Shorts")
    show_table(actionable_s, "actionable short", "Fall Prob")
    st.caption("👀 High Quality Watch")
    show_table(watch_hqs, "hq short", "Fall Prob")
    st.caption("📋 Developing")
    show_table(watch_dvs, "developing short", "Fall Prob")
    with st.expander(f"🌱 Early short watchlist ({len(watch_early)})", expanded=False):
        show_table(watch_early, "early short", "Fall Prob")

    with st.expander("📖 How to read the short table"):
        st.markdown("""
**Fall Prob** — probability the price falls within 5–7 sessions.

**Cover Stop** — place as a hard stop-limit immediately on entry.

`STOCH ROLLOVER` overbought K>80, now crossing down · `BB BEAR SQ` squeeze below midline
`MACD DECEL` histogram declining · `DIST DAY` large red on 2× volume
`VOL BREAKDOWN` 10-day low on high volume · `LOWER HIGHS` two consecutive lower swing highs
        """)


def render_both(ctx: dict) -> None:
    _bind_runtime(ctx)

    if df_long.empty and df_short.empty:
        st.info("Run the scan to see results.")
        return

    col_l, col_r = st.columns(2)
    with col_l:
        st.caption("📈 Top Longs")
        if not df_long.empty:
            _entry_l  = df_long.get("Entry Quality", pd.Series([""] * len(df_long))).astype(str)
            _action_l = df_long.get("Action",        pd.Series([""] * len(df_long))).astype(str)
            top_l = df_long[(
                _action_l.str.contains("STRONG BUY|BUY –", na=False, regex=True) |
                _entry_l.str.contains("✅", na=False)
            )][[c for c in ["Ticker","Sector","Setup Type","Entry Quality",
                             "Rise Prob","Score","Price","MA60 Stop",
                             "TP1 +10%","TP3 +20%","Support Tier","PM Chg%"]
                if c in df_long.columns]]
            show_table(top_l, "long", "Rise Prob")
    with col_r:
        st.caption("📉 Top Shorts")
        if not df_short.empty:
            _entry_s  = df_short.get("Entry Quality", pd.Series([""] * len(df_short))).astype(str)
            _action_s = df_short.get("Action",        pd.Series([""] * len(df_short))).astype(str)
            top_s = df_short[(
                (_action_s == "STRONG SHORT") | _entry_s.str.contains("✅", na=False)
            )][[c for c in ["Ticker","Sector","Setup Type","Entry Quality",
                             "Fall Prob","Score","Price","Cover Stop","Target 1:2"]
                if c in df_short.columns]]
            show_table(top_s, "short", "Fall Prob")

    if not df_long.empty and not df_short.empty:
        both = set(df_long["Ticker"]) & set(df_short["Ticker"])
        if both:
            st.warning(f"⚠️ Mixed signals — avoid: {', '.join(sorted(both))}")

    if not df_long.empty:
        _action_l = df_long.get("Action", pd.Series(dtype=str)).astype(str)
        top_buys  = df_long[_action_l.str.contains("STRONG BUY|BUY –", na=False, regex=True)]
        if len(top_buys) >= 2:
            sector_counts: dict = {}
            for _, row in top_buys.iterrows():
                sec = str(row.get("Sector","")).replace("🟢","").replace("🔴","").replace("⚪","").strip()
                sector_counts[sec] = sector_counts.get(sec, 0) + 1
            concentrated = {s: n for s, n in sector_counts.items() if n >= 3}
            if concentrated:
                st.error(
                    "⚠️ **Concentration risk** — "
                    + ", ".join(f"**{n} buys in {s}**" for s, n in concentrated.items())
                    + ". Limit to max 2–3 positions per sector."
                )
