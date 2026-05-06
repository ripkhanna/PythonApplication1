"""Extracted runtime section from app_runtime.py lines 4201-4495.
Loaded by app_runtime with exec(..., globals()) to preserve the original single-file behavior.
"""

@st.cache_data(ttl=3600)
def fetch_earnings_calendar(tickers: tuple, days_ahead: int = 15) -> pd.DataFrame:
    import time
    today  = datetime.today().date()
    cutoff = today + pd.Timedelta(days=days_ahead)
    rows   = []

    prog     = st.progress(0, text="Scanning earnings dates…")
    status   = st.empty()
    total    = len(tickers)
    found    = 0
    skipped  = 0   # rate-limited / empty responses

    def _get_info_with_retry(ticker, retries=2, delay=1.5):
        """Fetch tkr.info with retry on empty response (rate limit)."""
        for attempt in range(retries + 1):
            try:
                info = yf.Ticker(ticker).info or {}
                # If info is suspiciously empty (rate limited), retry
                if not info.get("regularMarketPrice") and not info.get("currentPrice") \
                   and not info.get("earningsTimestamp") and attempt < retries:
                    time.sleep(delay)
                    continue
                return info
            except Exception:
                if attempt < retries:
                    time.sleep(delay)
        return {}

    candidates = []

    for i, ticker in enumerate(tickers):
        status.caption(f"Checking {ticker} ({i+1}/{total}) · {found} with earnings found · {skipped} skipped")
        try:
            info = _get_info_with_retry(ticker)

            if not info:
                skipped += 1
                prog.progress((i + 1) / total)
                continue

            earn_date = None
            for key in ("earningsTimestamp", "earningsTimestampStart",
                        "earningsTimestampEnd", "earningsDate"):
                val = info.get(key)
                if val:
                    try:
                        d = pd.Timestamp(val, unit="s").date() \
                            if isinstance(val, (int, float)) and val > 0 \
                            else pd.Timestamp(val).date()
                        if d >= today:
                            earn_date = d
                            break
                    except Exception:
                        continue

            if earn_date and earn_date <= cutoff:
                candidates.append((ticker, earn_date, info))
                found += 1

            # Small delay every 10 tickers to avoid rate limiting
            if (i + 1) % 10 == 0:
                time.sleep(0.3)

        except Exception:
            skipped += 1
        prog.progress((i + 1) / total)

    prog.empty()
    status.empty()

    if not candidates:
        return pd.DataFrame()

    for ticker, earn_date, info in candidates:
        try:
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
