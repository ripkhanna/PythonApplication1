"""Fast earnings/event helper functions.

v13.49 change: the original earnings calendar called ``yf.Ticker(ticker).info``
for every ticker in the market list. That is very slow on Streamlit Cloud and
can make the Earnings tab feel frozen. This version uses a two-step flow:

1. Fetch only the earnings date first, using ``Ticker.calendar`` where possible.
2. Fetch the heavy ``Ticker.info`` payload only for tickers whose earnings date
   is inside the requested window.

Both ticker-level calls are cached, so repeated button clicks are fast.
"""

@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _fast_earnings_date_for_ticker(ticker: str):
    """Return next earnings date as ISO string, or an empty string.

    Uses Yahoo calendar first because it is generally lighter than ``info``.
    Falls back to selected timestamp fields from ``info`` only if needed.
    """
    try:
        tkr = yf.Ticker(ticker)
        today = datetime.today().date()

        # Newer yfinance may return a DataFrame or dict-like calendar.
        try:
            cal = tkr.calendar
            ed = None
            if cal is not None:
                if hasattr(cal, "empty") and not cal.empty:
                    # Common DataFrame form: index contains "Earnings Date".
                    if "Earnings Date" in getattr(cal, "index", []):
                        val = cal.loc["Earnings Date"]
                        if hasattr(val, "iloc"):
                            ed = val.iloc[0]
                        else:
                            ed = val
                    elif "Earnings Date" in getattr(cal, "columns", []):
                        ed = cal["Earnings Date"].iloc[0]
                    elif len(cal.values.flatten()) > 0:
                        ed = cal.values.flatten()[0]
                elif isinstance(cal, dict):
                    ed = cal.get("Earnings Date") or cal.get("EarningsDate")
            if ed is not None and not pd.isna(ed):
                if isinstance(ed, (list, tuple)) and ed:
                    ed = ed[0]
                d = pd.Timestamp(ed).date()
                if d >= today:
                    return str(d)
        except Exception:
            pass

        # Fallback: info timestamps, but only once per ticker and cached.
        try:
            info = tkr.info or {}
            for key in ("earningsTimestamp", "earningsTimestampStart", "earningsTimestampEnd", "earningsDate"):
                val = info.get(key)
                if not val:
                    continue
                try:
                    d = pd.Timestamp(val, unit="s").date() if isinstance(val, (int, float)) and val > 0 else pd.Timestamp(val).date()
                    if d >= today:
                        return str(d)
                except Exception:
                    continue
        except Exception:
            pass
    except Exception:
        pass
    return ""


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _earnings_info_for_candidate(ticker: str) -> dict:
    """Return the heavier info payload only for confirmed earnings candidates."""
    try:
        return yf.Ticker(ticker).info or {}
    except Exception:
        return {}


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_earnings_calendar(tickers: tuple, days_ahead: int = 15, max_tickers: int = 120) -> pd.DataFrame:
    today  = datetime.today().date()
    cutoff = today + pd.Timedelta(days=days_ahead)
    rows   = []

    # Keep order but remove duplicates / blanks.
    clean_tickers = []
    seen = set()
    for t in tickers:
        t = str(t).strip().upper()
        if not t or t in seen:
            continue
        seen.add(t)
        clean_tickers.append(t)

    if max_tickers and max_tickers > 0:
        clean_tickers = clean_tickers[:int(max_tickers)]

    total = len(clean_tickers)
    if total == 0:
        return pd.DataFrame()

    prog   = st.progress(0, text="Scanning earnings dates…")
    status = st.empty()
    candidates = []

    # Phase 1: light earnings-date scan only.
    for i, ticker in enumerate(clean_tickers):
        try:
            status.caption(f"Checking earnings date {ticker} ({i+1}/{total}) · {len(candidates)} found")
            ed_str = _fast_earnings_date_for_ticker(ticker)
            if ed_str:
                earn_date = pd.Timestamp(ed_str).date()
                if today <= earn_date <= cutoff:
                    candidates.append((ticker, earn_date))
        except Exception:
            pass
        prog.progress((i + 1) / total)

    prog.empty()
    status.empty()

    if not candidates:
        return pd.DataFrame()

    # Phase 2: enrich only candidates with heavier info fields.
    prog2 = st.progress(0, text="Loading details for earnings candidates…")
    status2 = st.empty()
    cand_total = len(candidates)

    for i, (ticker, earn_date) in enumerate(candidates):
        try:
            status2.caption(f"Loading details {ticker} ({i+1}/{cand_total})…")
            info = _earnings_info_for_candidate(ticker)

            days_out    = (earn_date - today).days
            eps_est     = info.get("forwardEps") or info.get("epsForward")
            eps_last    = info.get("trailingEps")
            price       = info.get("currentPrice") or info.get("regularMarketPrice") or 0
            ma50        = info.get("fiftyDayAverage") or 0
            ma200       = info.get("twoHundredDayAverage") or 0
            w52lo       = info.get("fiftyTwoWeekLow") or 0
            fwd_pe      = info.get("forwardPE")
            tgt         = info.get("targetMeanPrice")
            rec         = info.get("recommendationKey", "").upper().replace("_", " ")

            if eps_est and eps_last and eps_last != 0:
                eps_chg   = (eps_est - eps_last) / abs(eps_last) * 100
                eps_trend = f"📈 +{eps_chg:.1f}%" if eps_chg > 0 else f"📉 {eps_chg:.1f}%"
            else:
                eps_chg, eps_trend = 0, "–"

            above_ma50  = bool(price > ma50)  if ma50  and price else None
            above_ma200 = bool(price > ma200) if ma200 and price else None
            analyst_up  = bool(tgt > price)   if tgt   and price else None
            near_52lo   = bool(price < w52lo * 1.15) if w52lo and price else False

            score = sum(filter(None, [
                above_ma50, above_ma200, analyst_up,
                eps_chg > 5,
                rec in ("BUY", "STRONG BUY"),
            ]))

            if score >= 4:   verdict, vcol = "✅ BUY",   "buy"
            elif score == 3: verdict, vcol = "👀 WATCH", "watch"
            elif score <= 1 or near_52lo: verdict, vcol = "🚫 AVOID", "avoid"
            else:            verdict, vcol = "⏳ WAIT",  "wait"

            rows.append({
                "Ticker":         ticker,
                "Earnings Date":  str(earn_date),
                "Days Out":       days_out,
                "Price":          f"${price:.2f}" if price else "–",
                "EPS Est":        f"${eps_est:.2f}" if eps_est else "–",
                "EPS Last":       f"${eps_last:.2f}" if eps_last else "–",
                "EPS Trend":      eps_trend,
                "Fwd PE":         f"{fwd_pe:.1f}x" if fwd_pe else "–",
                "Analyst Target": f"${tgt:.2f}" if tgt else "–",
                "Upside":         f"+{(tgt/price-1)*100:.1f}%" if tgt and price else "–",
                "Above MA50":     "✅" if above_ma50 else ("❌" if above_ma50 is False else "–"),
                "Above MA200":    "✅" if above_ma200 else ("❌" if above_ma200 is False else "–"),
                "Analyst Rec":    rec or "–",
                "Verdict":        verdict,
                "_vcol":          vcol,
                "_days":          days_out,
            })
        except Exception:
            pass
        prog2.progress((i + 1) / cand_total)

    prog2.empty()
    status2.empty()

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("_days").reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# EVENT PREDICTOR HELPERS — earnings + market/news + orders/contracts
# ─────────────────────────────────────────────────────────────────────────────
_POSITIVE_NEWS_WORDS = ["beat", "beats", "raise", "raised", "upgrade", "upgraded", "buyback", "record", "strong", "growth", "profit", "surge", "rally", "partnership", "deal", "contract", "order", "award", "backlog", "approval", "launch", "expansion", "guidance raised"]
_NEGATIVE_NEWS_WORDS = ["miss", "misses", "cut", "cuts", "downgrade", "downgraded", "lawsuit", "probe", "investigation", "fraud", "weak", "loss", "decline", "falls", "plunge", "warning", "guidance cut", "delay", "cancel", "cancelled", "recall"]
_ORDER_WORDS = ["contract", "order", "award", "awarded", "backlog", "tender", "project", "supply", "shipbuilding", "data centre", "data center", "defence", "defense", "semiconductor", "government", "framework agreement", "purchase agreement"]
def _safe_float_event(v, default=0.0):
    try:
        if v is None or pd.isna(v):
            return default
        return float(v)
    except Exception:
        return default

def _extract_news_titles(ticker_obj, limit=12):
    items = []
    try:
        raw_news = ticker_obj.news or []
        for n in raw_news[:limit]:
            title = ""; publisher = ""; link = ""; pub_time = ""
            if isinstance(n, dict):
                title = n.get("title") or n.get("content", {}).get("title") or ""
                publisher = n.get("publisher") or n.get("content", {}).get("provider", {}).get("displayName") or ""
                link = n.get("link") or n.get("content", {}).get("canonicalUrl", {}).get("url") or ""
                pub_time = n.get("providerPublishTime") or n.get("content", {}).get("pubDate") or ""
            if title:
                items.append({"title": str(title), "publisher": str(publisher), "link": str(link), "time": str(pub_time)})
    except Exception:
        pass
    return items

def _score_news_titles(news_items):
    titles = " ".join([x.get("title", "") for x in news_items]).lower()
    pos_hits = sorted({w for w in _POSITIVE_NEWS_WORDS if w in titles})
    neg_hits = sorted({w for w in _NEGATIVE_NEWS_WORDS if w in titles})
    order_hits = sorted({w for w in _ORDER_WORDS if w in titles})
    news_score = min(3, len(pos_hits)) - min(4, len(neg_hits))
    order_score = 3 if len(order_hits) >= 2 else (2 if len(order_hits) == 1 else 0)
    sentiment = "🔴 Negative" if (neg_hits and len(neg_hits) >= len(pos_hits)) else ("🟢 Positive" if pos_hits else "⚪ Neutral")
    order_tag = "✅ Order/Contract" if order_score >= 2 else "–"
    return news_score, order_score, sentiment, order_tag, pos_hits, neg_hits, order_hits

@st.cache_data(ttl=1800)
def fetch_event_predictions(tickers: tuple, days_ahead: int = 30) -> pd.DataFrame:
    today = datetime.today().date()
    rows = []
    total = len(tickers)
    prog = st.progress(0, text="Scanning earnings, news and orders…")
    status = st.empty()
    for i, ticker in enumerate(tickers):
        try:
            status.caption(f"Event scoring {ticker} ({i+1}/{total})…")
            tkr = yf.Ticker(ticker)
            info = tkr.info or {}
            price = _safe_float_event(info.get("currentPrice") or info.get("regularMarketPrice"))
            ma50 = _safe_float_event(info.get("fiftyDayAverage"))
            ma200 = _safe_float_event(info.get("twoHundredDayAverage"))
            tgt = _safe_float_event(info.get("targetMeanPrice"))
            rec = str(info.get("recommendationKey", "")).upper().replace("_", " ")
            eps_est = info.get("forwardEps") or info.get("epsForward")
            eps_last = info.get("trailingEps")

            earn_date = None
            for key in ("earningsTimestamp", "earningsTimestampStart", "earningsTimestampEnd", "earningsDate"):
                val = info.get(key)
                if val:
                    try:
                        d = pd.Timestamp(val, unit="s").date() if isinstance(val, (int, float)) and val > 0 else pd.Timestamp(val).date()
                        if d >= today:
                            earn_date = d
                            break
                    except Exception:
                        continue
            days_out = (earn_date - today).days if earn_date else None
            if days_out is not None and 0 <= days_out <= 7:
                earnings_score, earnings_tag = -4, "🚫 Earnings ≤7d"
            elif days_out is not None and 8 <= days_out <= 21:
                earnings_score, earnings_tag = -1, "👀 Earnings 8–21d"
            elif days_out is not None and days_out <= days_ahead:
                earnings_score, earnings_tag = 0, "⚪ Earnings ahead"
            else:
                earnings_score, earnings_tag = 1, "✅ No near earnings"

            eps_chg = 0.0
            try:
                if eps_est and eps_last and float(eps_last) != 0:
                    eps_chg = (float(eps_est) - float(eps_last)) / abs(float(eps_last)) * 100
            except Exception:
                eps_chg = 0.0
            if eps_chg > 10:
                earnings_score += 2
            elif eps_chg > 5:
                earnings_score += 1
            elif eps_chg < -10:
                earnings_score -= 2

            news_items = _extract_news_titles(tkr, limit=12)
            news_score, order_score, sentiment, order_tag, pos_hits, neg_hits, order_hits = _score_news_titles(news_items)

            trend_score = 0
            if price and ma50 and price > ma50:
                trend_score += 1
            if price and ma200 and price > ma200:
                trend_score += 1
            if price and tgt and tgt > price:
                trend_score += 1
            if rec in ("BUY", "STRONG BUY"):
                trend_score += 1

            total_score = earnings_score + news_score + order_score + trend_score
            if total_score >= 8 and trend_score >= 2 and earnings_score >= 0:
                verdict, vcol = "✅ BUY", "buy"
            elif total_score >= 6:
                verdict, vcol = "👀 WATCH", "watch"
            elif total_score >= 4:
                verdict, vcol = "⏳ WAIT", "wait"
            else:
                verdict, vcol = "🚫 AVOID", "avoid"
            if days_out is not None and 0 <= days_out <= 7:
                verdict, vcol = "🚫 AVOID", "avoid"

            top_news = " | ".join([x["title"] for x in news_items[:3]]) if news_items else "–"
            evidence = []
            if pos_hits: evidence.append("+" + ", ".join(pos_hits[:4]))
            if neg_hits: evidence.append("-" + ", ".join(neg_hits[:4]))
            if order_hits: evidence.append("Orders: " + ", ".join(order_hits[:4]))

            rows.append({
                "Ticker": ticker,
                "Price": f"${price:.2f}" if price else "–",
                "Earnings": earnings_tag,
                "Days Out": int(days_out) if days_out is not None else None,
                "EPS Trend": f"{eps_chg:+.1f}%" if eps_chg else "–",
                "News": sentiment,
                "Orders": order_tag,
                "Trend Score": f"{trend_score}/4",
                "Event Score": total_score,
                "Verdict": verdict,
                "Evidence": " ; ".join(evidence) if evidence else "–",
                "Top News": top_news,
                "_vcol": vcol,
                "_score": total_score,
            })
        except Exception:
            pass
        prog.progress((i + 1) / max(total, 1))

    prog.empty(); status.empty()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["_score", "Ticker"], ascending=[False, True]).reset_index(drop=True)




# ─────────────────────────────────────────────────────────────────────────────
# TAB — SWING PICKS  (technical setup + earnings + news)
# ─────────────────────────────────────────────────────────────────────────────
