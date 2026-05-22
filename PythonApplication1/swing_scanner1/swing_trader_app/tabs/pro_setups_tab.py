"""
Pro Setups Tab  —  v15.1
Surfaces the highest-confidence swing trade candidates using the
professional trader confluence framework. Reads data directly from
st.session_state["df_long"] — the same dataframe already loaded by the
main scanner, so no file-path issues and no extra reads.
"""

import pandas as pd
import streamlit as st


def _bind_runtime(ctx: dict) -> None:
    globals().update(ctx)


def _rr_float(v):
    try:
        return float(str(v).split(":")[1])
    except Exception:
        return 0.0


def _pro_score(row):
    sig = str(row.get("Signals", ""))
    s = 0
    s += 3 if "HIGH-ACCURACY"  in sig else 0
    s += 2 if "NEXT-DAY-A+"    in sig else 0
    s += 2 if "DIP-MA20"       in sig else 0
    s += 2 if "DIP-MA60"       in sig else 0
    s += 2 if "VOL-DIP"        in sig else 0
    s += 2 if "NR7"            in sig else 0
    s += 2 if "INSIDE DAY"     in sig else 0
    s += 2 if "BB BULL SQ"     in sig else 0
    s += 2 if "RS>SPY"         in sig else 0
    s += 2 if "WKLY TREND"     in sig else 0
    s += 2 if "STOCH BOUNCE"   in sig else 0
    s += 1 if "MACD ACCEL"     in sig else 0
    s += 1 if "HIGHER LOWS"    in sig else 0
    s += 1 if "POCKET PIVOT"   in sig else 0
    s += 2 if "CUP+HANDLE"     in sig else 0
    s += 1 if "FAILED BRKDN"   in sig else 0
    s -= 5 if "CHASING"        in sig else 0
    s -= 3 if "LIMIT-UP"       in sig else 0
    return s


def _tier_label(score, rr):
    if score >= 20 and rr >= 4.0:
        return "🏆 Elite",  "#0A9C6A", "#E1F5EE"
    if score >= 16:
        return "🔥 Tier 1", "#0F6E56", "#E1F5EE"
    if score >= 12:
        return "✅ Tier 2", "#185FA5", "#E6F1FB"
    return "👀 Tier 3",     "#BA7517", "#FAEEDA"


def _badge_html(sig_str):
    badges = []
    sig = str(sig_str)
    checks = [
        ("HIGH-ACCURACY",  "HIGH-ACCURACY",  "#B5D4F4", "#0C447C"),
        ("DIP-MA20",       "DIP-MA20",        "#C0DD97", "#27500A"),
        ("DIP-MA60",       "DIP-MA60",        "#C0DD97", "#27500A"),
        ("VOL-DIP",        "VOL declining",   "#FAC775", "#633806"),
        ("NR7",            "NR7 coil",        "#CECBF6", "#3C3489"),
        ("INSIDE DAY",     "Inside day",      "#CECBF6", "#3C3489"),
        ("BB BULL SQ",     "BB squeeze",      "#CECBF6", "#3C3489"),
        ("RS>SPY",         "RS>SPY",          "#9FE1CB", "#085041"),
        ("WKLY TREND",     "Weekly trend",    "#9FE1CB", "#085041"),
        ("STOCH BOUNCE",   "Stoch bounce",    "#F5C4B3", "#712B13"),
        ("CUP+HANDLE",     "Cup+handle",      "#CECBF6", "#3C3489"),
        ("POCKET PIVOT",   "Pocket pivot",    "#9FE1CB", "#085041"),
        ("FAILED BRKDN",   "Failed breakdn",  "#F7C1C1", "#791F1F"),
        ("MACD ACCEL",     "MACD accel",      "#FAC775", "#633806"),
        ("HIGHER LOWS",    "Higher lows",     "#C0DD97", "#27500A"),
        ("DISCOVERY-BUY",  "Discovery",       "#FAC775", "#633806"),
        ("NEAR-MISS",      "Near-miss",       "#FAC775", "#633806"),
    ]
    for key, label, bg, fg in checks:
        if key in sig:
            badges.append(
                f'<span style="background:{bg};color:{fg};font-size:10px;'
                f'padding:2px 7px;border-radius:4px;border:0.5px solid {bg};'
                f'margin-right:3px;margin-bottom:3px;display:inline-block">{label}</span>'
            )
    return "".join(badges)


def render_pro_setups(ctx: dict) -> None:
    _bind_runtime(ctx)
    st.caption("⭐ Pro Setups — Professional Confluence Framework")

    # ── Load data from session_state (already loaded by main scanner) ────────
    df = st.session_state.get("df_long", pd.DataFrame())

    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        st.info(
            "No scan data loaded yet. Run a scan first using the **🚀 Scan** button, "
            "then come back to this tab.",
            icon="ℹ️"
        )
        return

    df = df.copy()

    # ── Controls ─────────────────────────────────────────────────────────────
    col_a, col_b, col_c, col_d = st.columns([1, 1, 1, 1])
    with col_a:
        min_tier = st.selectbox(
            "Min setup tier",
            ["All actionable (BUY + WATCH)", "BUY & Discovery only"],
            key="pro_min_tier"
        )
    with col_b:
        min_rr = st.selectbox(
            "Min R:R", ["Any", "1:2+", "1:3+", "1:4+"],
            key="pro_min_rr", index=0
        )
    with col_c:
        no_chasing = st.checkbox("Hide chasing", value=True, key="pro_no_chase")
    with col_d:
        min_qs = st.number_input("Min Quality Score", 1, 20, 8, key="pro_min_qs")

    rr_map = {"Any": 0.0, "1:2+": 2.0, "1:3+": 3.0, "1:4+": 4.0}
    min_rr_val = rr_map[min_rr]

    # ── Build the actionable set ──────────────────────────────────────────────
    eq_col    = df.get("Entry Quality", pd.Series([""] * len(df), index=df.index)).astype(str)
    action_s  = df.get("Action",        pd.Series([""] * len(df), index=df.index)).astype(str)
    sig_col   = df.get("Signals",       pd.Series([""] * len(df), index=df.index)).astype(str)

    if min_tier == "BUY & Discovery only":
        mask = (
            eq_col.str.contains("BUY", na=False) |
            action_s.str.contains("STRONG BUY", na=False)
        )
    else:
        # All actionable: BUY + high-quality WATCH (QS >= min_qs)
        qs_num = pd.to_numeric(
            df.get("Quality Score", pd.Series([0]*len(df), index=df.index)),
            errors="coerce"
        ).fillna(0)
        mask = (
            eq_col.str.contains("BUY", na=False) |
            action_s.str.contains("STRONG BUY", na=False) |
            (action_s.str.contains("WATCH", na=False) & (qs_num >= min_qs))
        )

    df = df[mask].copy()

    if no_chasing:
        df = df[~sig_col.reindex(df.index).str.contains("CHASING|LIMIT-UP", na=False)]

    # ── Score and filter ──────────────────────────────────────────────────────
    df["_pro_score"] = df.apply(_pro_score, axis=1)
    df["_rr"]        = df.get("RR Est", pd.Series(["1:0"] * len(df), index=df.index)).apply(_rr_float)

    qs_num2 = pd.to_numeric(df.get("Quality Score", pd.Series([0]*len(df), index=df.index)), errors="coerce").fillna(0)
    df = df[qs_num2 >= min_qs]

    if min_rr_val > 0:
        df = df[df["_rr"] >= min_rr_val]

    df = df.sort_values("_pro_score", ascending=False).reset_index(drop=True)

    if df.empty:
        st.warning(
            "No setups match the current filters.\n\n"
            "Try: lower **Min Quality Score**, set **Min R:R → Any**, "
            "or select **All actionable** in Min setup tier."
        )
        return

    # ── Summary bar ───────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    elite = len(df[df["_pro_score"] >= 20])
    tier1 = len(df[df["_pro_score"] >= 16])
    rr_mean = df["_rr"].mean()
    rise_vals = pd.to_numeric(
        df.get("Rise Prob", pd.Series(["0"]*len(df))).astype(str).str.replace("%","", regex=False),
        errors="coerce"
    ).mean()
    c1.metric("Setups shown",    len(df))
    c2.metric("🏆 Elite / Tier1", f"{elite} / {tier1}")
    c3.metric("Avg R:R",         f"1:{rr_mean:.1f}")
    c4.metric("Avg Rise Prob",   f"{rise_vals:.0f}%" if not pd.isna(rise_vals) else "–")

    st.divider()

    with st.expander("📖 Why these signals = high probability", expanded=False):
        st.markdown("""
**Professional confluence scoring** — each signal adds weight:

| Signal | Points | Why it matters |
|---|---|---|
| `HIGH-ACCURACY` | +3 | Scanner's Bayesian model confirmed this exact pattern historically |
| `DIP-MA20 / DIP-MA60` | +2 | Price at a real support level, not random air |
| `VOL-DIP` | +2 | Volume declining on pullback = institutions NOT distributing |
| `NR7 / Inside Day` | +2 | Tightest range in 7 days = volatility compression = coiled spring |
| `BB BULL SQ` | +2 | Bollinger Band squeeze — explosive move imminent |
| `RS>SPY` | +2 | Stock stronger than market — sector tailwind, not headwind |
| `STOCH BOUNCE` | +2 | Stochastic bouncing from oversold — clean mechanical entry |
| `WKLY TREND` | +2 | Weekly chart confirmed — never fight the higher timeframe |
| `CHASING` | −5 | Price already ran — entry here has no edge |

**The edge:** 5+ signals aligning simultaneously raises historical win rate to 70–85% because trend, institutional positioning, compression, momentum, and support all point the same direction.
        """)

    # ── Render cards ─────────────────────────────────────────────────────────
    for rank, (_, row) in enumerate(df.iterrows(), 1):
        ticker   = str(row.get("Ticker",        "–"))
        price    = str(row.get("Price",         "–"))
        stop     = str(row.get("Best Stop",     row.get("MA60 Stop", "–")))
        tp1      = str(row.get("TP1 +10%",      "–"))
        tp2      = str(row.get("TP2 +15%",      "–"))
        smart_tp = str(row.get("Smart TP",      "–"))
        rr_str   = str(row.get("RR Est",        "–"))
        rise     = str(row.get("Rise Prob",     "–"))
        qs       = str(row.get("Quality Score", "–"))
        nds      = str(row.get("Next-Day Score","–"))
        rsi      = str(row.get("RSI Now",       "–"))
        atr      = str(row.get("ATR%",          "–"))
        setup    = str(row.get("Setup Type",    "–"))
        eq       = str(row.get("Entry Quality", "–"))
        sector   = str(row.get("Sector",        "–"))
        upside   = str(row.get("Upside to Res", "–"))
        sig      = str(row.get("Signals",       ""))
        pro_s    = int(row.get("_pro_score",    0))
        rr_f     = float(row.get("_rr",         0.0))
        tier_lbl, tier_fg, tier_bg = _tier_label(pro_s, rr_f)
        tp_show  = smart_tp if smart_tp not in ("–", "", "nan") else tp2

        with st.container():
            hcol1, hcol2 = st.columns([3, 1])
            with hcol1:
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">'
                    f'<span style="font-size:18px;font-weight:600">#{rank} &nbsp;{ticker}</span>'
                    f'<span style="background:{tier_bg};color:{tier_fg};font-size:11px;'
                    f'padding:2px 8px;border-radius:4px;font-weight:500">{tier_lbl}</span>'
                    f'<span style="font-size:11px;color:#888">{sector} · {setup}</span>'
                    f'</div>',
                    unsafe_allow_html=True)
                st.markdown(
                    f'<div style="margin-bottom:6px">{_badge_html(sig)}</div>',
                    unsafe_allow_html=True)
            with hcol2:
                st.markdown(
                    f'<div style="text-align:right">'
                    f'<div style="font-size:20px;font-weight:600">{price}</div>'
                    f'<div style="font-size:11px;color:#888">Rise Prob {rise} · ProScore {pro_s}</div>'
                    f'</div>',
                    unsafe_allow_html=True)

            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Quality Score", qs)
            m2.metric("Next-Day Score", nds)
            m3.metric("R:R", rr_str)
            m4.metric("RSI", rsi)
            m5.metric("ATR%", atr)

            t1, t2, t3, t4 = st.columns(4)
            t1.markdown(
                f'<div style="background:#E1F5EE;border-radius:6px;padding:7px 10px">'
                f'<div style="font-size:10px;color:#0A9C6A">Entry zone</div>'
                f'<div style="font-size:13px;font-weight:600;color:#085041">{price}</div></div>',
                unsafe_allow_html=True)
            t2.markdown(
                f'<div style="background:#FCEBEB;border-radius:6px;padding:7px 10px">'
                f'<div style="font-size:10px;color:#E24B4A">Stop loss</div>'
                f'<div style="font-size:13px;font-weight:600;color:#A32D2D">{stop}</div></div>',
                unsafe_allow_html=True)
            t3.markdown(
                f'<div style="background:#E6F1FB;border-radius:6px;padding:7px 10px">'
                f'<div style="font-size:10px;color:#185FA5">Target 1</div>'
                f'<div style="font-size:13px;font-weight:600;color:#0C447C">{tp1}</div></div>',
                unsafe_allow_html=True)
            t4.markdown(
                f'<div style="background:#EEEDFE;border-radius:6px;padding:7px 10px">'
                f'<div style="font-size:10px;color:#534AB7">Target 2</div>'
                f'<div style="font-size:13px;font-weight:600;color:#3C3489">{tp2}</div></div>',
                unsafe_allow_html=True)

            st.caption(
                f"Upside to resistance: {upside}  ·  Entry quality: {eq}  ·  "
                f"Smart TP: {smart_tp}"
            )
            st.divider()

    st.caption(
        "⚠️ Always verify live price before entry. Risk max 1–2% of account per trade. "
        "Not financial advice."
    )
