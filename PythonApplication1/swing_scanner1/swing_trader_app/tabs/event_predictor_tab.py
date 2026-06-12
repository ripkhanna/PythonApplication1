"""Event Predictor Tab renderer.

Readable Streamlit tab code extracted from the original working monolith.
Each render function receives the main runtime globals as ``ctx`` and exposes
them to this module so the body behaves like it did in the single-file app.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import streamlit as st


def _bind_runtime(ctx: dict) -> None:
    """Expose original app globals to this module for monolith-compatible tab code."""
    globals().update(ctx)


def _event_market_token(market: str) -> str:
    m = str(market or "").upper()
    if "HK" in m or "HONG" in m:
        return "HK"
    if "INDIA" in m or "NSE" in m or ".NS" in m:
        return "India"
    if "SGX" in m or "SINGAPORE" in m or ".SI" in m:
        return "SGX"
    return "US"


def _market_tickers_for_event(token: str) -> list[str]:
    if token == "HK":
        dynamic_hk = globals().get("fetch_hk_market_universe")
        if callable(dynamic_hk):
            try:
                return list(dynamic_hk(max_symbols=500))
            except Exception:
                return []
    getter = globals().get("get_tickers_for_market")
    try:
        if callable(getter):
            if token == "HK":
                return list(getter("Hong Kong"))
            if token == "India":
                return list(getter("India"))
            if token == "SGX":
                return list(getter("SGX"))
            return list(getter("US"))
    except Exception:
        pass
    if token == "HK":
        return list(globals().get("HK_TICKERS", []))
    if token == "India":
        return list(globals().get("INDIA_TICKERS", []))
    if token == "SGX":
        return list(globals().get("SG_TICKERS", []))
    return list(globals().get("US_TICKERS", []))


def _latest_scan_frame_for_event(token: str) -> pd.DataFrame:
    sources = []
    for key in ("df_long_master", "df_long", "df_swing_picks"):
        sources.append(st.session_state.get(key, pd.DataFrame()))
        sources.append(globals().get(key, pd.DataFrame()))
    for df in sources:
        if isinstance(df, pd.DataFrame) and not df.empty:
            out = df.copy()
            if "Ticker" not in out.columns:
                out.insert(0, "Ticker", out.index.astype(str))
            out["Ticker"] = out["Ticker"].astype(str).str.upper().str.strip()
            if token == "US":
                mask = ~out["Ticker"].str.endswith((".SI", ".HK", ".NS", ".BO"))
            elif token == "SGX":
                mask = out["Ticker"].str.endswith(".SI")
            elif token == "HK":
                mask = out["Ticker"].str.endswith(".HK")
            else:
                mask = out["Ticker"].str.endswith((".NS", ".BO"))
            out = out[mask].drop_duplicates("Ticker").reset_index(drop=True)
            if not out.empty:
                return out
    cache_dir = Path(__file__).resolve().parents[1] / "scanner_cache"
    cache_names = {
        "US": ["us_long_setups.csv"],
        "SGX": ["sgx_long_setups.csv", "sg_long_setups.csv"],
        "HK": ["hk_long_setups.csv"],
        "India": ["india_long_setups.csv"],
    }.get(token, [])
    for name in cache_names:
        cache_path = cache_dir / name
        if not cache_path.exists():
            continue
        try:
            cached = pd.read_csv(cache_path)
            if "Ticker" not in cached.columns:
                cached.insert(0, "Ticker", cached.index.astype(str))
            cached["Ticker"] = cached["Ticker"].astype(str).str.upper().str.strip()
            cached = cached.drop_duplicates("Ticker").reset_index(drop=True)
            if not cached.empty:
                return cached
        except Exception:
            continue
    return pd.DataFrame()


def _event_base_from_scan_and_market(token: str, limit: int = 160) -> list[str]:
    tickers: list[str] = []
    scan = _latest_scan_frame_for_event(token)
    if not scan.empty and "Ticker" in scan.columns:
        tickers.extend(scan["Ticker"].astype(str).str.upper().tolist())
    tickers.extend(str(t).upper().strip() for t in _market_tickers_for_event(token))
    out = []
    seen = set()
    for t in tickers:
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(t)
        if len(out) >= limit:
            break
    return out


def _num_event(value, default: float = 0.0) -> float:
    try:
        text = (
            str(value)
            .replace("%", "")
            .replace("+", "")
            .replace("$", "")
            .replace("HK$", "")
            .replace("S$", "")
            .replace("x", "")
            .replace(",", "")
            .strip()
        )
        if text.lower() in {"", "nan", "none", "-", "–"}:
            return float(default)
        if text.startswith("1:"):
            text = text.split("1:", 1)[1]
        val = pd.to_numeric(text, errors="coerce")
        return float(default) if pd.isna(val) else float(val)
    except Exception:
        return float(default)


def _fallback_event_predictions(tickers: list[str], token: str) -> pd.DataFrame:
    """Build a non-empty event/watchlist table from latest scan rows.

    This is used only when live Yahoo event/news calls return no rows. It keeps
    the tab useful while clearly marking the evidence as scan-fallback data.
    """
    scan = _latest_scan_frame_for_event(token)
    if scan.empty:
        scan = pd.DataFrame({"Ticker": list(dict.fromkeys(tickers))[:80]})
    elif tickers:
        wanted = set(str(t).upper().strip() for t in tickers)
        filtered = scan[scan["Ticker"].astype(str).str.upper().isin(wanted)].copy()
        if not filtered.empty:
            scan = filtered
    scan = scan.drop_duplicates("Ticker").head(120)

    rows = []
    for _, r in scan.iterrows():
        ticker = str(r.get("Ticker", "")).upper().strip()
        if not ticker:
            continue
        price = _num_event(r.get("Price", 0))
        action = str(r.get("Action", "")).upper()
        entry = str(r.get("Entry Quality", "")).upper()
        signals = str(r.get("Signals", "")).upper()
        quality = _num_event(r.get("Quality Score", 0))
        nds = _num_event(r.get("Next-Day Score", 0))
        rise = _num_event(r.get("Rise Prob", 0))
        vol = _num_event(r.get("Vol Ratio", 0))
        atr = _num_event(r.get("ATR%", 0))
        today = _num_event(r.get("Today %", 0))
        short_float = _num_event(r.get("Short %", 0))

        eventish = bool(re.search(r"EARN|PEAD|CATALYST|ORDER|CONTRACT|CALL FLOW|CALL SKEW|NEWS|SQUEEZE|SQZ", signals))
        trend_score = 0
        if "BUY" in action or "BUY" in entry:
            trend_score += 2
        elif "WATCH" in action or "WATCH" in entry:
            trend_score += 1
        if quality >= 10:
            trend_score += 1
        if nds >= 8:
            trend_score += 1
        trend_score = min(trend_score, 4)

        squeeze_score = 0
        if short_float >= 10:
            squeeze_score += 2
        if atr >= 5:
            squeeze_score += 1
        if vol >= 2:
            squeeze_score += 2
        elif vol >= 1.2:
            squeeze_score += 1
        if eventish:
            squeeze_score += 2

        post_score = 0
        if 3 <= today <= 25:
            post_score += 2
        if vol >= 1.5:
            post_score += 2
        if "BREAKOUT" in signals or "POCKET" in signals or "NEXT-DAY" in signals:
            post_score += 2

        score = 1 + min(3, trend_score) + min(3, squeeze_score) + min(2, post_score)
        if eventish:
            score += 2
        if "AVOID" in entry or "SKIP" in entry or "TRAP" in action or "CHASING" in signals:
            score -= 3
        if rise >= 75:
            score += 1
        score = int(max(0, min(10, score)))

        if score >= 8 and eventish and trend_score >= 2:
            verdict, vcol = "✅ BUY", "buy"
        elif score >= 6:
            verdict, vcol = "👀 WATCH", "watch"
        elif score >= 4:
            verdict, vcol = "⏳ WAIT", "wait"
        else:
            verdict, vcol = "🚫 AVOID", "avoid"

        label = "⚡ POST-EVENT MOMENTUM" if post_score >= 5 else ("👀 EVENT WATCH" if eventish else "Scan fallback")
        trigger = str(r.get("Buy Condition", "") or "")
        if not trigger or trigger in {"-", "–", "nan"}:
            trigger = "Live event/news unavailable; wait for volume + price confirmation."

        rows.append({
            "Ticker": ticker,
            "Price": f"${price:.2f}" if price else str(r.get("Price", "–") or "–"),
            "Earnings": "Live source unavailable",
            "Days Out": None,
            "EPS Trend": "–",
            "News": "⚪ Scan fallback",
            "Orders": "–",
            "Trend Score": f"{trend_score}/4",
            "Squeeze Score": int(squeeze_score),
            "Post-Event Score": int(post_score),
            "SEDG-Type": label,
            "52W Dist": "–",
            "Short Float": str(r.get("Short %", "–") or "–"),
            "Vol Ratio": f"{vol:.1f}x" if vol else str(r.get("Vol Ratio", "–") or "–"),
            "Today %": f"{today:+.1f}%" if today else str(r.get("Today %", "–") or "–"),
            "Trigger": trigger,
            "Event Score": score,
            "Verdict": verdict,
            "Evidence": "scan fallback" + (" ; event/catalyst tag" if eventish else ""),
            "Top News": "Yahoo event/news returned no rows; using latest scan evidence.",
            "_vcol": vcol,
            "_score": score,
        })

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["_score", "Ticker"], ascending=[False, True]).reset_index(drop=True)


def render_event_predictor(ctx: dict) -> None:
    _bind_runtime(ctx)
    st.caption("📰 Event Predictor · combines earnings risk, recent news sentiment, order/contract keywords and trend confirmation")

    ev_market = str(st.session_state.get("market_selector") or globals().get("market_sel") or "🇺🇸 US")
    ev_token = _event_market_token(ev_market)
    st.info(f"🌍 Event Predictor market: **{ev_market}** — controlled by the top market selector.")
    _ev_placeholder = "UUUU, NVDA, SEDG"
    if ev_token == "SGX":
        _ev_placeholder = "D05.SI, O39.SI, U11.SI"
    elif ev_token == "India":
        _ev_placeholder = "RELIANCE.NS, TCS.NS, INFY.NS"
    elif ev_token == "HK":
        _ev_placeholder = "e.g. 4-digit-code.HK"

    ev1, ev3 = st.columns([1, 2])
    with ev1:
        ev_days = st.slider("Earnings window", 7, 60, 30, key="event_days")
    with ev3:
        ev_extra = st.text_input("Tickers to check", placeholder=_ev_placeholder, key="event_extra").strip().upper()

    ev_base = _event_base_from_scan_and_market(ev_token, limit=160)

    if ev_extra:
        extras = [x.strip().upper() for x in re.split(r"[,\s]+", ev_extra) if x.strip()]
        ev_base = extras + [x for x in ev_base if x not in extras]

    f1, f2 = st.columns([2, 2])
    with f1:
        ev_search = st.text_input("🔍 Search", placeholder="ticker", key="event_search").strip().upper()
    with f2:
        ev_verdict_filter = st.multiselect("Filter verdict", ["✅ BUY", "👀 WATCH", "⏳ WAIT", "🚫 AVOID"], default=[], key="event_verdict_filter", placeholder="All verdicts")

    _prev_event_market = st.session_state.get("event_df_market", "")
    if _prev_event_market and _prev_event_market != ev_market:
        st.session_state.pop("event_df", None)
        st.session_state.pop("event_df_source", None)
        st.session_state.pop("event_df_error", None)

    _event_click_cb = globals().get("_set_top_status_for_next_run")
    _event_btn_kwargs = {}
    if callable(_event_click_cb):
        _event_btn_kwargs = {
            "on_click": _event_click_cb,
            "args": (f"Predicting {ev_market} event/news/order setups for {len(dict.fromkeys(ev_base))} tickers...", "Event Predictor", "📰", "running"),
        }
    if st.button("📰 Predict from Earnings + News + Orders", type="primary", key="btn_event_predictor", **_event_btn_kwargs):
        _top_status = globals().get("_show_top_status")
        if callable(_top_status):
            _top_status(f"Predicting {ev_market} event/news/order setups for {len(dict.fromkeys(ev_base))} tickers...", stage="Event Predictor", icon="📰")
        _event_error = ""
        try:
            _event_rows = fetch_event_predictions(tuple(dict.fromkeys(ev_base)), ev_days)
        except Exception as exc:
            _event_rows = pd.DataFrame()
            _event_error = str(exc)
        if not isinstance(_event_rows, pd.DataFrame) or _event_rows.empty:
            _event_rows = _fallback_event_predictions(list(dict.fromkeys(ev_base)), ev_token)
            st.session_state["event_df_source"] = "fallback"
            if _event_error:
                st.session_state["event_df_error"] = _event_error
            else:
                st.session_state.pop("event_df_error", None)
        else:
            st.session_state["event_df_source"] = "live"
            st.session_state.pop("event_df_error", None)
        st.session_state["event_df"] = _event_rows
        st.session_state["event_df_market"] = ev_market
        if callable(_top_status):
            _top_status(f"Event Predictor loaded {len(st.session_state.get('event_df', pd.DataFrame()))} {ev_market} rows.", stage="Done", icon="✅", status="done")

    event_df = st.session_state.get("event_df", pd.DataFrame())
    _df_event_market = st.session_state.get("event_df_market", "")
    if isinstance(event_df, pd.DataFrame) and not event_df.empty and _df_event_market and _df_event_market != ev_market:
        st.warning(f"⚠️ Showing **{_df_event_market}** event rows — click Predict to load **{ev_market}**.")

    if event_df.empty:
        st.info("Enter tickers or select a market, then click 📰 Predict from Earnings + News + Orders.")
        st.caption("BUY requires enough event score plus trend confirmation. Near earnings ≤7 days is forced AVOID because gap risk is high.")
    else:
        df_event = event_df.copy()
        if st.session_state.get("event_df_source") == "fallback":
            st.warning("Live Yahoo event/news returned no rows. Showing fallback rows from the latest scanner cache so the tab is not blank.")
            _event_error = str(st.session_state.get("event_df_error") or "").strip()
            if _event_error:
                st.caption(f"Live source error: {_event_error[:180]}")
        if ev_search:
            df_event = df_event[df_event["Ticker"].astype(str).str.contains(ev_search, case=False, na=False)]
        if ev_verdict_filter:
            df_event = df_event[df_event["Verdict"].isin(ev_verdict_filter)]

        b = (df_event["_vcol"] == "buy").sum()
        w = (df_event["_vcol"] == "watch").sum()
        wait = (df_event["_vcol"] == "wait").sum()
        a = (df_event["_vcol"] == "avoid").sum()
        st.caption(f"✅ **{b}** Buy · 👀 **{w}** Watch · ⏳ **{wait}** Wait · 🚫 **{a}** Avoid · {len(df_event)} shown")

        def _style_event_verdict(val):
            s = str(val)
            if "BUY" in s: return "background-color:#d4edda;color:#155724;font-weight:700"
            if "WATCH" in s: return "background-color:#d1ecf1;color:#0c5460;font-weight:600"
            if "WAIT" in s: return "background-color:#fff3cd;color:#856404"
            if "AVOID" in s: return "background-color:#f8d7da;color:#721c24;font-weight:700"
            return ""

        def _style_event_score(val):
            try:
                v = float(val)
                if v >= 8: return "color:#155724;font-weight:700"
                if v >= 6: return "color:#0c5460;font-weight:600"
                if v < 4: return "color:#721c24;font-weight:600"
            except Exception:
                pass
            return ""

        disp = [c for c in [
            "Ticker", "Verdict","Price", "Earnings", "Days Out", "EPS Trend", "News", "Orders",
            "Trend Score", "Squeeze Score", "Post-Event Score", "SEDG-Type",
            "52W Dist", "Short Float", "Vol Ratio", "Today %", "Trigger",
            "Event Score", "Evidence", "Top News"
        ] if c in df_event.columns]
        df_show = df_event[disp].copy()
        if "Days Out" in df_show.columns:
            df_show["Days Out"] = pd.to_numeric(df_show["Days Out"], errors="coerce")

        col_cfg = {
            "Ticker": st.column_config.TextColumn("Ticker", width=70),
            "Price": st.column_config.TextColumn("Price", width=65),
            "Earnings": st.column_config.TextColumn("Earnings", width=120),
            "Days Out": st.column_config.NumberColumn("Days", width=50),
            "EPS Trend": st.column_config.TextColumn("EPS", width=70),
            "News": st.column_config.TextColumn("News", width=90),
            "Orders": st.column_config.TextColumn("Orders", width=110),
            "Trend Score": st.column_config.TextColumn("Trend", width=62),
            "Squeeze Score": st.column_config.NumberColumn("Squeeze", width=70),
            "Post-Event Score": st.column_config.NumberColumn("PostEvt", width=70),
            "SEDG-Type": st.column_config.TextColumn("SEDG-Type", width=160),
            "52W Dist": st.column_config.TextColumn("52W Dist", width=75),
            "Short Float": st.column_config.TextColumn("Short", width=65),
            "Vol Ratio": st.column_config.TextColumn("Vol", width=55),
            "Today %": st.column_config.TextColumn("Today", width=65),
            "Trigger": st.column_config.TextColumn("Trigger", width=260),
            "Event Score": st.column_config.NumberColumn("Score", width=55),
            "Verdict": st.column_config.TextColumn("Verdict", width=90),
            "Evidence": st.column_config.TextColumn("Evidence", width=220),
            "Top News": st.column_config.TextColumn("Top News", width=420),
        }

        styler = df_show.style
        sfn = styler.map if hasattr(styler, "map") else styler.applymap
        styled = sfn(_style_event_verdict, subset=["Verdict"])
        styled = (styled.map if hasattr(styled, "map") else styled.applymap)(_style_event_score, subset=["Event Score"])
        for _score_col in ["Squeeze Score", "Post-Event Score"]:
            if _score_col in df_show.columns:
                styled = (styled.map if hasattr(styled, "map") else styled.applymap)(_style_event_score, subset=[_score_col])

        st.dataframe(
            styled, width="stretch", hide_index=True,
            column_config={k:v for k,v in col_cfg.items() if k in df_show.columns},
            height=min(60 + len(df_show) * 36, 560)
        )
        st.warning("News/order detection uses recent yfinance headlines and keyword matching. SEDG-Type / squeeze labels are watchlist signals only — confirm VWAP/gap hold, volume follow-through, and risk:reward before buying.")
