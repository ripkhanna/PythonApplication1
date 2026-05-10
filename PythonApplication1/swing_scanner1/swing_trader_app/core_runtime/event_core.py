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
def _yahoo_json(url: str) -> dict:
    """Small Yahoo HTTP helper that does not use yfinance crumb/cookie state.

    yfinance earnings/info methods can throw noisy 401 Invalid Crumb errors,
    especially when called in parallel.  The Earnings tab uses this helper first
    because Yahoo's public JSON endpoints usually work without a crumb.
    """
    import json as _json
    import urllib.request as _urlreq
    try:
        req = _urlreq.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
                "Accept": "application/json,text/plain,*/*",
            },
        )
        with _urlreq.urlopen(req, timeout=8) as resp:
            return _json.loads(resp.read().decode("utf-8", errors="ignore"))
    except Exception:
        return {}


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _fast_earnings_date_for_ticker(ticker: str):
    """Return next earnings date as ISO string, or an empty string.

    Important: this function intentionally avoids ``Ticker.get_earnings_dates``
    and heavy ``Ticker.info`` first because those calls frequently emit Yahoo
    401 Invalid Crumb / Unauthorized errors.  We use crumb-free Yahoo JSON
    endpoints first, then only light yfinance calendar fallbacks.
    """
    import datetime as _dt
    import contextlib as _contextlib
    import io as _io

    def _today_date():
        try:
            return pd.Timestamp.now(tz="Asia/Singapore").date()
        except Exception:
            return _dt.datetime.today().date()

    def _coerce_earnings_date(value):
        """Coerce Yahoo's many date shapes into a plain date."""
        if value is None:
            return None
        try:
            if isinstance(value, (list, tuple, set)):
                for item in value:
                    d = _coerce_earnings_date(item)
                    if d is not None:
                        return d
                return None
            if hasattr(value, "tolist") and not isinstance(value, (str, bytes)):
                return _coerce_earnings_date(value.tolist())
            if pd.isna(value):
                return None
        except Exception:
            pass
        try:
            if isinstance(value, dict):
                for k in ("raw", "fmt", "date", "startdatetime", "start", "end"):
                    if k in value:
                        d = _coerce_earnings_date(value.get(k))
                        if d is not None:
                            return d
                return None
            if isinstance(value, (int, float)) and value > 0:
                return pd.to_datetime(value, unit="s", utc=True).tz_convert("Asia/Singapore").date()
            raw = str(value).strip()
            if not raw:
                return None
            # Avoid pandas FutureWarning for display suffixes like SGT.
            for suffix, tz_name in ((" SGT", "Asia/Singapore"), (" ET", "America/New_York")):
                if raw.endswith(suffix):
                    ts = pd.to_datetime(raw[:-len(suffix)].strip(), errors="coerce")
                    if pd.isna(ts):
                        return None
                    return ts.tz_localize(tz_name).tz_convert("Asia/Singapore").date()
            ts = pd.to_datetime(raw, errors="coerce", utc=False)
            if pd.isna(ts):
                return None
            try:
                if getattr(ts, "tzinfo", None) is not None:
                    ts = ts.tz_convert("Asia/Singapore")
            except Exception:
                pass
            return ts.date()
        except Exception:
            return None

    def _first_future_date(values):
        today = _today_date()
        best = None
        for v in values:
            d = _coerce_earnings_date(v)
            if d is None or d < today:
                continue
            if best is None or d < best:
                best = d
        return best

    try:
        ticker = str(ticker).strip().upper()
        if not ticker:
            return ""
        today = _today_date()

        # 1) Crumb-free calendar endpoint.  This prevents most Invalid Crumb noise.
        try:
            url = f"https://query1.finance.yahoo.com/v7/finance/calendar/earnings?symbol={ticker}"
            js = _yahoo_json(url)
            vals = []
            earnings = (((js.get("finance") or {}).get("result") or [{}])[0].get("earnings") or []) if isinstance(js, dict) else []
            for item in earnings:
                if not isinstance(item, dict):
                    continue
                # Different Yahoo responses use different field names.
                for k in ("startdatetime", "startDate", "date", "earningsDate", "epsestimate", "time"):
                    if k in item:
                        vals.append(item.get(k))
            d = _first_future_date(vals)
            if d is not None and d >= today:
                return str(d)
        except Exception:
            pass

        # 2) quoteSummary calendarEvents endpoint.
        try:
            url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker}?modules=calendarEvents"
            js = _yahoo_json(url)
            vals = []
            result = (((js.get("quoteSummary") or {}).get("result") or []) if isinstance(js, dict) else [])
            if result:
                ce = (result[0].get("calendarEvents") or {})
                earnings = ce.get("earnings") or {}
                for k in ("earningsDate", "earningsAverage", "earningsLow", "earningsHigh"):
                    if k in earnings:
                        vals.append(earnings.get(k))
            d = _first_future_date(vals)
            if d is not None and d >= today:
                return str(d)
        except Exception:
            pass

        # 3) Light yfinance fallbacks.  Suppress stderr/stdout because Yahoo/yfinance
        # may print 401 crumb errors even when exceptions are caught.
        try:
            with _contextlib.redirect_stderr(_io.StringIO()), _contextlib.redirect_stdout(_io.StringIO()):
                tkr = yf.Ticker(ticker)
                cal = tkr.calendar
            vals = []
            if cal is not None:
                if isinstance(cal, dict):
                    for key in ("Earnings Date", "EarningsDate", "earningsDate", "Earnings Date Start", "Earnings Date End"):
                        if key in cal:
                            vals.append(cal.get(key))
                elif hasattr(cal, "empty") and not cal.empty:
                    try:
                        if "Earnings Date" in getattr(cal, "index", []):
                            vals.append(cal.loc["Earnings Date"])
                    except Exception:
                        pass
                    for col in ("Earnings Date", "Earnings Date Start", "Earnings Date End"):
                        if col in getattr(cal, "columns", []):
                            try:
                                vals.extend(cal[col].dropna().tolist())
                            except Exception:
                                pass
                    try:
                        vals.extend(list(cal.values.flatten()))
                    except Exception:
                        pass
            d = _first_future_date(vals)
            if d is not None and d >= today:
                return str(d)
        except Exception:
            pass

        try:
            with _contextlib.redirect_stderr(_io.StringIO()), _contextlib.redirect_stdout(_io.StringIO()):
                cal2 = yf.Ticker(ticker).get_calendar()
            vals = []
            if isinstance(cal2, dict):
                for key in ("Earnings Date", "EarningsDate", "earningsDate", "Earnings Date Start", "Earnings Date End"):
                    if key in cal2:
                        vals.append(cal2.get(key))
            elif cal2 is not None and hasattr(cal2, "empty") and not cal2.empty:
                for col in ("Earnings Date", "Earnings Date Start", "Earnings Date End"):
                    if col in getattr(cal2, "columns", []):
                        vals.extend(cal2[col].dropna().tolist())
                try:
                    vals.extend(list(cal2.index))
                except Exception:
                    pass
            d = _first_future_date(vals)
            if d is not None and d >= today:
                return str(d)
        except Exception:
            pass
    except Exception:
        pass
    return ""


def _norm_key_for_eps(key) -> str:
    """Normalize vendor field names like "EPS Forecast", "Last Year's EPS"."""
    import re as _re
    return _re.sub(r"[^a-z0-9]", "", str(key).lower())


def _unwrap_vendor_value(v):
    """Unwrap Nasdaq/Yahoo cell values. Nasdaq sometimes returns {value: ...}."""
    if isinstance(v, dict):
        for k in ("raw", "fmt", "value", "text", "label", "display", "displayValue"):
            if k in v and v.get(k) not in (None, "", "--", "-", "N/A", "n/a"):
                return v.get(k)
    return v


def _is_non_empty_vendor_value(v) -> bool:
    v = _unwrap_vendor_value(v)
    if v is None:
        return False
    try:
        if pd.isna(v):
            return False
    except Exception:
        pass
    return str(v).strip() not in ("", "--", "-", "N/A", "n/a", "None", "null")


def _first_present(row: dict, keys):
    """Return first non-empty value from a row using robust key matching."""
    if not isinstance(row, dict):
        return None
    lower_map = {_norm_key_for_eps(k): v for k, v in row.items()}
    for key in keys:
        norm = _norm_key_for_eps(key)
        if norm in lower_map:
            v = lower_map[norm]
            if _is_non_empty_vendor_value(v):
                return _unwrap_vendor_value(v)
    return None


def _clean_eps_value(v):
    """Convert Nasdaq/Yahoo EPS text such as '$1.23', '(0.12)', '<span>$1.23</span>' to float or None."""
    import re as _re
    try:
        if v is None:
            return None
        v = _unwrap_vendor_value(v)
        if v is None or pd.isna(v):
            return None
    except Exception:
        if v is None:
            return None
        v = _unwrap_vendor_value(v)

    txt = str(v).strip()
    if not txt:
        return None

    # Remove common HTML from Nasdaq cells and normalize spaces/minus signs.
    txt = _re.sub(r"<[^>]+>", "", txt)
    txt = txt.replace("&nbsp;", " ").replace("\xa0", " ").strip()
    txt = txt.replace("−", "-").replace("–", "-").replace("—", "-")

    upper = txt.upper().strip()
    if upper in {"N/A", "NA", "--", "-", "NONE", "NULL", "NAN"}:
        return None

    neg = txt.startswith("(") and txt.endswith(")")
    # Keep only first numeric token after removing currency/commas/percent signs.
    cleaned = txt.replace("$", "").replace(",", "").replace("%", "")
    cleaned = cleaned.replace("(", "").replace(")", "").strip()
    m = _re.search(r"[-+]?\d*\.?\d+", cleaned)
    if not m:
        return None
    try:
        val = float(m.group(0))
        return -abs(val) if neg else val
    except Exception:
        return None


def _flatten_eps_fields(obj, prefix=""):
    """Return [(normalized_key_path, value)] for nested Nasdaq/Yahoo rows.

    Nasdaq has changed the calendar row shape more than once.  Sometimes EPS
    fields are flat (epsForecast), sometimes nested under data/row objects, and
    sometimes wrapped as {value: ..., raw: ...}.  This helper lets the mapper
    find EPS values without depending on one exact field name.
    """
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, (dict, list, tuple)):
                out.extend(_flatten_eps_fields(v, key))
            else:
                norm = _norm_key_for_eps(key)
                out.append((norm, v))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            key = f"{prefix}.{i}" if prefix else str(i)
            if isinstance(v, (dict, list, tuple)):
                out.extend(_flatten_eps_fields(v, key))
    return out


def _pick_eps_value(fields, mode: str):
    """Pick one EPS estimate/last value from flattened fields."""
    if not fields:
        return None

    if mode == "estimate":
        preferred = (
            "epsforecast", "epsforecasted", "epsestimate", "epsestimated",
            "epsforecastestimate", "consensuseps", "epsconsensus", "forecastedeps", "estimatedeps",
            "epsavg", "earningsepsavg", "earningsaverage", "earningsforecast", "earningsestimate"
        )
        include_words = ("forecast", "estimate", "estimated", "consensus", "average", "avg")
        exclude_words = ("last", "previous", "prior", "reported", "actual", "yearago", "surprise")
    else:
        preferred = (
            "lastyeareps", "lastyearseps", "previouseps", "prioryeareps", "epslastyear",
            "reportedeps", "actualeps", "lasteps", "yearagoeps", "epsactual", "epsreported"
        )
        include_words = ("last", "previous", "prior", "reported", "actual", "yearago")
        exclude_words = ("forecast", "estimate", "estimated", "consensus", "average", "avg", "surprise")

    # Exact-ish normalized field-name match first.
    for key, val in fields:
        compact_leaf = key.split(".")[-1]
        if compact_leaf in preferred or any(compact_leaf.endswith(p) for p in preferred):
            parsed = _clean_eps_value(val)
            if parsed is not None:
                return parsed

    # Then broad fuzzy search: key must contain EPS plus desired context words.
    for key, val in fields:
        if "eps" not in key:
            continue
        if any(w in key for w in exclude_words):
            continue
        if any(w in key for w in include_words):
            parsed = _clean_eps_value(val)
            if parsed is not None:
                return parsed

    return None


def _eps_from_nasdaq_row(nasdaq_row: dict):
    """Extract EPS estimate/last from Nasdaq earnings-calendar row.

    The Nasdaq API field names are not stable.  This version handles flat keys,
    nested keys, wrapped values, and multiple naming styles.  If no EPS exists
    in the row, it returns (None, None) rather than showing fake data.
    """
    if not isinstance(nasdaq_row, dict):
        return None, None

    # Fast path for common flat fields.
    est = _first_present(nasdaq_row, [
        "epsForecast", "epsForecasted", "epsEstimate", "epsEstimated",
        "EPS Forecast", "EPS Estimate", "Consensus EPS", "Eps Forecast",
        "consensusEPS", "consensusEps", "epsConsensus", "forecastEps",
        "estimatedEPS", "eps_est", "eps est", "earningsAverage", "earnings forecast"
    ])
    last = _first_present(nasdaq_row, [
        "lastYearEPS", "lastYearEps", "Last Year EPS", "Last Year's EPS", "previousEPS", "previousEps",
        "epsLastYear", "reportedEPS", "reportedEps", "actualEPS",
        "lastEPS", "priorYearEPS", "eps last", "EPS Actual", "Reported EPS"
    ])

    est_val = _clean_eps_value(est)
    last_val = _clean_eps_value(last)

    # Robust nested/fuzzy fallback.
    fields = _flatten_eps_fields(nasdaq_row)
    if est_val is None:
        est_val = _pick_eps_value(fields, "estimate")
    if last_val is None:
        last_val = _pick_eps_value(fields, "last")

    return est_val, last_val

def _earnings_info_for_candidate(ticker: str) -> dict:
    """Return quote/fundamental fields without using heavy yfinance .info.

    Most blank columns came from ``yf.Ticker(ticker).info`` failing with Yahoo
    crumb/authorization errors.  This helper uses public JSON endpoints and a
    chart endpoint for price/MA data.  It never raises.
    """
    def _raw(v):
        if isinstance(v, dict):
            if "raw" in v:
                return v.get("raw")
            if "fmt" in v:
                return v.get("fmt")
        return v

    out = {}

    # First use Yahoo quote endpoint. It is usually crumb-free and often has EPS
    # fields even when quoteSummary/calendar endpoints are blocked or blank.
    try:
        jsq = _yahoo_json(f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={ticker}")
        qres = (((jsq.get("quoteResponse") or {}).get("result") or []) if isinstance(jsq, dict) else [])
        if qres:
            q = qres[0]
            out.update({
                "currentPrice": q.get("regularMarketPrice") or q.get("postMarketPrice") or q.get("preMarketPrice"),
                "regularMarketPrice": q.get("regularMarketPrice"),
                # These are not always the same as the next quarterly EPS, but
                # they are a useful fallback so EPS columns are not blank when
                # Nasdaq/yfinance earnings endpoints omit consensus EPS.
                "forwardEps": q.get("epsForward") or q.get("epsCurrentYear") or q.get("epsNextQuarter"),
                "epsForward": q.get("epsForward"),
                "epsNextQuarter": q.get("epsNextQuarter"),
                "epsCurrentYear": q.get("epsCurrentYear"),
                "trailingEps": q.get("epsTrailingTwelveMonths"),
                "epsTrailingTwelveMonths": q.get("epsTrailingTwelveMonths"),
                "forwardPE": q.get("forwardPE") or q.get("priceEpsCurrentYear"),
                "targetMeanPrice": q.get("targetMeanPrice"),
                "fiftyDayAverage": q.get("fiftyDayAverage"),
                "twoHundredDayAverage": q.get("twoHundredDayAverage"),
                "fiftyTwoWeekLow": q.get("fiftyTwoWeekLow"),
                "recommendationKey": str(q.get("recommendationKey") or q.get("averageAnalystRating") or "").lower(),
            })
    except Exception:
        pass

    try:
        modules = "price,summaryDetail,financialData,defaultKeyStatistics,recommendationTrend,calendarEvents"
        js = _yahoo_json(f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker}?modules={modules}")
        result = (((js.get("quoteSummary") or {}).get("result") or []) if isinstance(js, dict) else [])
        if result:
            r = result[0]
            price = r.get("price") or {}
            fd = r.get("financialData") or {}
            ks = r.get("defaultKeyStatistics") or {}
            sd = r.get("summaryDetail") or {}
            rec_trend = r.get("recommendationTrend") or {}
            ce = r.get("calendarEvents") or {}
            earnings = ce.get("earnings") or {}
            qs_vals = {
                "currentPrice": _raw(price.get("regularMarketPrice")) or _raw(fd.get("currentPrice")),
                "regularMarketPrice": _raw(price.get("regularMarketPrice")),
                "forwardEps": _raw(ks.get("forwardEps")) or _raw(fd.get("forwardEps")),
                "trailingEps": _raw(ks.get("trailingEps")),
                "forwardPE": _raw(ks.get("forwardPE")) or _raw(sd.get("forwardPE")),
                "targetMeanPrice": _raw(fd.get("targetMeanPrice")),
                "recommendationKey": str(_raw(fd.get("recommendationKey")) or "").lower(),
                "earningsAverage": _raw(earnings.get("earningsAverage")),
            }
            # Preserve values already obtained from the lighter quote endpoint;
            # quoteSummary often returns None/blank under Yahoo crumb limits.
            for _k, _v in qs_vals.items():
                if _v not in (None, "", "none", "nan"):
                    out[_k] = _v if not out.get(_k) else out.get(_k)
            # Convert recommendation trend to a rough text if recommendationKey is absent.
            if not out.get("recommendationKey"):
                try:
                    trend = (rec_trend.get("trend") or [{}])[0]
                    buy_count = int(_raw(trend.get("buy")) or 0) + int(_raw(trend.get("strongBuy")) or 0)
                    sell_count = int(_raw(trend.get("sell")) or 0) + int(_raw(trend.get("strongSell")) or 0)
                    hold_count = int(_raw(trend.get("hold")) or 0)
                    if buy_count > max(sell_count, hold_count):
                        out["recommendationKey"] = "buy"
                    elif sell_count > max(buy_count, hold_count):
                        out["recommendationKey"] = "sell"
                    elif hold_count:
                        out["recommendationKey"] = "hold"
                except Exception:
                    pass
    except Exception:
        pass

    # Chart endpoint for price, MA50, MA200, 52-week low fallback.  This is more
    # reliable than info and keeps columns populated even when quoteSummary is sparse.
    try:
        js = _yahoo_json(f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=1y&interval=1d")
        result = (((js.get("chart") or {}).get("result") or []) if isinstance(js, dict) else [])
        if result:
            r = result[0]
            meta = r.get("meta") or {}
            quote = (((r.get("indicators") or {}).get("quote") or [{}])[0])
            closes = [x for x in (quote.get("close") or []) if x is not None]
            lows = [x for x in (quote.get("low") or []) if x is not None]
            if closes:
                out["currentPrice"] = out.get("currentPrice") or closes[-1]
                out["regularMarketPrice"] = out.get("regularMarketPrice") or closes[-1]
                out["fiftyDayAverage"] = sum(closes[-50:]) / min(len(closes), 50)
                out["twoHundredDayAverage"] = sum(closes[-200:]) / min(len(closes), 200)
            if lows:
                out["fiftyTwoWeekLow"] = min(lows)
            out["currentPrice"] = out.get("currentPrice") or meta.get("regularMarketPrice")
    except Exception:
        pass

    # v15.5: earningsEstimate + earningsTrend + earningsHistory modules
    # Better EPS source than calendarEvents.earningsAverage. Works for US and non-US.
    def _raw2(v):
        if isinstance(v, dict):
            return v.get("raw") or v.get("avg") or v.get("fmt")
        return v

    try:
        url_ee = (f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
                  "?modules=earningsEstimate,earningsTrend,earningsHistory")
        js_ee   = _yahoo_json(url_ee)
        res_ee  = (((js_ee.get("quoteSummary") or {}).get("result") or [])
                   if isinstance(js_ee, dict) else [])
        if res_ee:
            r_ee = res_ee[0]
            # earningsEstimate quarterly — next quarter consensus avg EPS
            ee      = r_ee.get("earningsEstimate") or {}
            ee_list = ee.get("quarterly") or ee.get("yearly") or []
            if isinstance(ee_list, list) and ee_list:
                ep_val = _raw2((ee_list[0] if isinstance(ee_list[0], dict) else {}).get("avg"))
                if ep_val not in (None, "", "N/A"):
                    out.setdefault("forwardEps", ep_val)
            # earningsTrend — current quarter estimate
            et_list = (r_ee.get("earningsTrend") or {}).get("trend") or []
            for et_item in et_list[:2]:
                if isinstance(et_item, dict):
                    ep_val = _raw2((et_item.get("epsTrend") or {}).get("current"))
                    if ep_val not in (None, "", "N/A"):
                        out.setdefault("epsNextQuarter", ep_val)
                        break
            # earningsHistory — most recent actual EPS (replaces trailingEps when absent)
            eh_list = (r_ee.get("earningsHistory") or {}).get("history") or []
            if isinstance(eh_list, list) and eh_list:
                last_actual = _raw2((eh_list[-1] if isinstance(eh_list[-1], dict) else {}).get("epsActual"))
                if last_actual not in (None, "", "N/A"):
                    out.setdefault("trailingEps", last_actual)
    except Exception:
        pass

    # v15.6: yfinance targeted fallback for the 3 columns that are most often blank.
    #
    # Root cause: targetMeanPrice is NEVER in Yahoo's v7/finance/quote endpoint.
    # It is only in v10/quoteSummary?modules=financialData, which requires Yahoo's
    # crumb/cookie and fails with 401 on Streamlit Cloud when called via bare urllib.
    # yf.Ticker handles the crumb correctly, so we use it here as a last resort
    # ONLY for the specific fields that the other endpoints don't supply.
    _needs_target = out.get("targetMeanPrice") in (None, "", "none", "nan")
    _needs_fwdpe  = out.get("forwardPE")       in (None, "", "none", "nan")
    _needs_eps    = out.get("forwardEps")      in (None, "", "none", "nan")

    if _needs_target or _needs_fwdpe or _needs_eps:
        try:
            import contextlib as _cl2, io as _io2
            with _cl2.redirect_stderr(_io2.StringIO()), _cl2.redirect_stdout(_io2.StringIO()):
                _tkr2  = yf.Ticker(ticker)
                # fast_info is lightweight and usually returns price/PE quickly
                _fi    = getattr(_tkr2, "fast_info", None)
            if _fi is not None:
                _fp = getattr(_fi, "forward_pe",    None) or getattr(_fi, "forwardPE", None)
                _pr = getattr(_fi, "last_price",    None) or getattr(_fi, "price",     None)
                if _fp and _needs_fwdpe:
                    out["forwardPE"] = float(_fp)
                if _pr and not out.get("currentPrice"):
                    out["currentPrice"] = float(_pr)
        except Exception:
            pass

        # Full .info only if we still need targetMeanPrice (heavier call)
        if out.get("targetMeanPrice") in (None, "", "none", "nan"):
            try:
                import contextlib as _cl3, io as _io3
                with _cl3.redirect_stderr(_io3.StringIO()), _cl3.redirect_stdout(_io3.StringIO()):
                    _info2 = yf.Ticker(ticker).info or {}
                for _k, _yk in [
                    ("targetMeanPrice", "targetMeanPrice"),
                    ("forwardPE",       "forwardPE"),
                    ("forwardEps",      "forwardEps"),
                    ("trailingEps",     "trailingEps"),
                    ("recommendationKey", "recommendationKey"),
                ]:
                    _v = _info2.get(_yk)
                    if _v not in (None, "", "none", "nan") and not out.get(_k):
                        out[_k] = _v
            except Exception:
                pass

    # Computed fallback: if forwardPE still missing but we have price and forwardEps
    if out.get("forwardPE") in (None, "", "none", "nan"):
        try:
            _fp_price = float(out.get("currentPrice") or out.get("regularMarketPrice") or 0)
            _fp_eps   = float(out.get("forwardEps")   or out.get("epsNextQuarter")     or 0)
            if _fp_price > 0 and _fp_eps > 0:
                out["forwardPE"] = round(_fp_price / _fp_eps, 1)
        except Exception:
            pass

    return out


def _safe_fmt_money(v):
    try:
        if v is None or pd.isna(v):
            return "–"
        return f"${float(v):.2f}"
    except Exception:
        return "–"


def _safe_fmt_num(v, suffix=""):
    try:
        if v is None or pd.isna(v):
            return "–"
        return f"{float(v):.1f}{suffix}"
    except Exception:
        return "–"


def _build_earnings_row(ticker: str, earn_date, today, nasdaq_row: dict | None = None) -> dict:
    """Build one display row for an earnings candidate. Kept small so it can run in threads."""
    info = _earnings_info_for_candidate(ticker)
    ns_eps_est, ns_eps_last = _eps_from_nasdaq_row(nasdaq_row or {})
    try:
        if nasdaq_row and (ns_eps_est is None and ns_eps_last is None):
            # Keep a tiny debug sample so the Diagnostics/console can reveal
            # the exact Nasdaq row keys if EPS is blank again.
            _sample = st.session_state.setdefault("earn_eps_blank_row_keys", [])
            if len(_sample) < 5:
                _sample.append({"ticker": ticker, "keys": list(nasdaq_row.keys())[:40], "row": {k: str(v)[:80] for k, v in list(nasdaq_row.items())[:12]}})
    except Exception:
        pass

    def _to_float(v, default=0.0):
        try:
            if v is None or pd.isna(v):
                return default
            return float(v)
        except Exception:
            return default

    days_out    = (earn_date - today).days
    eps_est     = ns_eps_est if ns_eps_est is not None else (
        info.get("earningsAverage") or info.get("epsNextQuarter") or
        info.get("forwardEps") or info.get("epsForward") or info.get("epsCurrentYear")
    )
    eps_last    = ns_eps_last if ns_eps_last is not None else (
        info.get("trailingEps") or info.get("epsTrailingTwelveMonths")
    )
    price       = _to_float(info.get("currentPrice") or info.get("regularMarketPrice"), 0)
    ma50        = _to_float(info.get("fiftyDayAverage"), 0)
    ma200       = _to_float(info.get("twoHundredDayAverage"), 0)
    w52lo       = _to_float(info.get("fiftyTwoWeekLow"), 0)
    fwd_pe      = info.get("forwardPE")
    tgt         = _to_float(info.get("targetMeanPrice"), 0)
    rec         = str(info.get("recommendationKey", "")).upper().replace("_", " ")

    try:
        if eps_est and eps_last and float(eps_last) != 0:
            eps_chg   = (float(eps_est) - float(eps_last)) / abs(float(eps_last)) * 100
            eps_trend = f"📈 +{eps_chg:.1f}%" if eps_chg > 0 else f"📉 {eps_chg:.1f}%"
        else:
            eps_chg, eps_trend = 0, "–"
    except Exception:
        eps_chg, eps_trend = 0, "–"

    above_ma50  = bool(price > ma50)  if ma50  and price else None
    above_ma200 = bool(price > ma200) if ma200 and price else None
    analyst_up  = bool(tgt > price)   if tgt   and price else None
    near_52lo   = bool(price < w52lo * 1.15) if w52lo and price else False

    # v15.5: adaptive scoring — only count criteria where data is actually present.
    # For SGX/HK/India, analyst target and rec are often absent; scoring them as 0
    # unfairly pushes everything into AVOID/WAIT. Instead, score out of criteria
    # that have real values and scale the threshold accordingly.
    criteria_present = []   # (passed: bool)
    criteria_available = 0

    if above_ma50 is not None:
        criteria_present.append(above_ma50)
        criteria_available += 1
    if above_ma200 is not None:
        criteria_present.append(above_ma200)
        criteria_available += 1
    if analyst_up is not None:
        criteria_present.append(analyst_up)
        criteria_available += 1
    if eps_est is not None and eps_last is not None:
        criteria_present.append(eps_chg > 5)
        criteria_available += 1
    if rec and rec not in ("–", "N/A", ""):
        criteria_present.append(rec in ("BUY", "STRONG BUY", "STRONG_BUY"))
        criteria_available += 1

    score = sum(criteria_present)

    # Scale thresholds: require same proportion as the original 5-criteria model
    # Original: BUY ≥ 4/5 = 80%, WATCH = 3/5 = 60%
    if criteria_available >= 4:
        buy_thresh   = 4
        watch_thresh = 3
    elif criteria_available == 3:
        buy_thresh   = 3
        watch_thresh = 2
    elif criteria_available == 2:
        buy_thresh   = 2
        watch_thresh = 1
    else:
        buy_thresh   = 1
        watch_thresh = 1

    # Data quality tag shown in Verdict column
    if criteria_available >= 4:
        dq = ""
    elif criteria_available >= 2:
        dq = " ⚠️partial"
    else:
        dq = " ❓low data"

    if score >= buy_thresh:            verdict, vcol = "✅ BUY" + dq,   "buy"
    elif score >= watch_thresh:        verdict, vcol = "👀 WATCH" + dq, "watch"
    elif score <= 1 or near_52lo:      verdict, vcol = "🚫 AVOID",      "avoid"
    else:                              verdict, vcol = "⏳ WAIT" + dq,  "wait"

    return {
        "Ticker":         ticker,
        "Earnings Date":  str(earn_date),
        "Days Out":       days_out,
        "Price":          _safe_fmt_money(price) if price else "–",
        "EPS Est":        _safe_fmt_money(eps_est),
        "EPS Last":       _safe_fmt_money(eps_last),
        "EPS Trend":      eps_trend,
        "Fwd PE":         _safe_fmt_num(fwd_pe, "x"),
        "Analyst Target": _safe_fmt_money(tgt) if tgt else "–",
        "Upside":         (
            f"+{(tgt/price-1)*100:.1f}%" if tgt and price and tgt > price else
            f"{(tgt/price-1)*100:.1f}%" if tgt and price and tgt < price else
            "–"
        ),
        "Above MA50":     "✅" if above_ma50 else ("❌" if above_ma50 is False else "–"),
        "Above MA200":    "✅" if above_ma200 else ("❌" if above_ma200 is False else "–"),
        "Analyst Rec":    rec or "–",
        "Data":           f"{criteria_available}/5",
        "Verdict":        verdict,
        "_vcol":          vcol,
        "_days":          days_out,
    }



@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _nasdaq_earnings_for_date(date_iso: str) -> list:
    """Return Nasdaq earnings-calendar rows for one date.

    Yahoo/yfinance frequently returns no earnings dates or 401 crumb errors.
    Nasdaq's public earnings calendar is a better primary source for US
    earnings dates and avoids one-request-per-ticker scanning.
    """
    import json as _json
    import urllib.request as _urlreq
    import urllib.parse as _urlparse

    url = "https://api.nasdaq.com/api/calendar/earnings?" + _urlparse.urlencode({"date": date_iso})
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://www.nasdaq.com",
        "Referer": "https://www.nasdaq.com/market-activity/earnings",
    }
    try:
        req = _urlreq.Request(url, headers=headers)
        with _urlreq.urlopen(req, timeout=10) as resp:
            js = _json.loads(resp.read().decode("utf-8", errors="ignore"))
        rows = (((js.get("data") or {}).get("rows") or []) if isinstance(js, dict) else [])
        return rows if isinstance(rows, list) else []
    except Exception:
        return []


def _nasdaq_us_earnings_candidates(clean_tickers, days_ahead: int):
    """Return [(ticker, date, nasdaq_row)] for US tickers using Nasdaq's calendar first."""
    import datetime as _dt

    try:
        today = pd.Timestamp.now(tz="Asia/Singapore").date()
    except Exception:
        today = _dt.datetime.today().date()

    ticker_set = {str(t).strip().upper().replace("-", ".") for t in clean_tickers if str(t).strip()}
    ticker_set |= {str(t).strip().upper() for t in clean_tickers if str(t).strip()}
    out = []
    seen = set()

    for i in range(int(days_ahead) + 1):
        d = today + pd.Timedelta(days=i)
        rows = _nasdaq_earnings_for_date(d.strftime("%Y-%m-%d"))
        for r in rows:
            if not isinstance(r, dict):
                continue
            sym = str(r.get("symbol") or r.get("Symbol") or "").strip().upper()
            if not sym:
                continue
            # Nasdaq sometimes uses dots for class shares; app universe may use hyphen.
            sym_alt = sym.replace(".", "-")
            if sym not in ticker_set and sym_alt not in ticker_set:
                continue
            app_sym = sym_alt if sym_alt in {str(t).strip().upper() for t in clean_tickers} else sym
            key = (app_sym, d)
            if key in seen:
                continue
            seen.add(key)
            out.append((app_sym, d, r))

    order = {str(t).strip().upper(): i for i, t in enumerate(clean_tickers)}
    out.sort(key=lambda x: (x[1], order.get(x[0], 999999)))
    return out

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_earnings_calendar(tickers: tuple, days_ahead: int = 15, max_tickers: int = 120) -> pd.DataFrame:
    """Fast two-phase earnings scan.

    v13.50: phase 1 and phase 2 now run concurrently with a small worker pool.
    This avoids the previous one-ticker-at-a-time Yahoo calls, which made the
    Earnings tab feel very slow.  The ticker-level functions are still cached,
    so repeated scans remain fast.
    """
    import concurrent.futures as _fut

    today  = pd.Timestamp.now(tz="Asia/Singapore").date()
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

    # Keep worker count modest to avoid Yahoo throttling / Streamlit Cloud stalls.
    workers = 8 if total >= 80 else (6 if total >= 30 else min(4, total))

    # v15.5: per-ticker market detection — split list into US and non-US pools
    # instead of a fragile universe-wide flag that breaks when mixed markets are scanned.
    def _is_non_us(t: str) -> bool:
        return str(t).upper().endswith((".SI", ".HK", ".NS", ".BO", ".KL", ".BK", ".NZ", ".AX"))

    us_tickers     = [t for t in clean_tickers if not _is_non_us(t)]
    non_us_tickers = [t for t in clean_tickers if _is_non_us(t)]

    def _date_job(ticker):
        try:
            ed_str = _fast_earnings_date_for_ticker(ticker)
            if not ed_str:
                return None
            earn_date = pd.Timestamp(ed_str).date()
            if today <= earn_date <= cutoff:
                return (ticker, earn_date)
        except Exception:
            return None
        return None

    candidates = []

    # US tickers: Nasdaq market-wide calendar (fast, no per-ticker call)
    if us_tickers:
        try:
            us_cands = _nasdaq_us_earnings_candidates(tuple(us_tickers), int(days_ahead))
            if us_cands:
                candidates.extend(us_cands)
                st.caption(f"US earnings source: Nasdaq calendar · {len(us_cands)} matching tickers")
        except Exception:
            pass
        # US fallback: Yahoo per-ticker if Nasdaq returned nothing
        if not [c for c in candidates if not _is_non_us(c[0])]:
            prog_us = st.progress(0, text=f"Scanning {len(us_tickers)} US tickers via Yahoo…")
            st_us   = st.empty()
            done_us = 0
            try:
                with _fut.ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
                    fm = {ex.submit(_date_job, t): t for t in us_tickers}
                    for fut in _fut.as_completed(fm):
                        done_us += 1
                        res = fut.result()
                        if res is not None:
                            candidates.append(res)
                        if done_us % 5 == 0 or done_us == len(us_tickers):
                            prog_us.progress(min(1.0, done_us / max(len(us_tickers), 1)))
            finally:
                prog_us.empty(); st_us.empty()

    # Non-US tickers (SGX/HK/India): Yahoo per-ticker — Nasdaq calendar doesn't cover them
    if non_us_tickers:
        prog_nu = st.progress(0, text=f"Scanning {len(non_us_tickers)} SGX/HK/India tickers…")
        st_nu   = st.empty()
        done_nu = 0
        try:
            with _fut.ThreadPoolExecutor(max_workers=min(6, max(1, len(non_us_tickers)))) as ex:
                fm = {ex.submit(_date_job, t): t for t in non_us_tickers}
                for fut in _fut.as_completed(fm):
                    done_nu += 1
                    res = fut.result()
                    if res is not None:
                        candidates.append(res)
                    if done_nu % 3 == 0 or done_nu == len(non_us_tickers):
                        st_nu.caption(f"SGX/HK/India ({done_nu}/{len(non_us_tickers)}) · {len([c for c in candidates if _is_non_us(c[0])])} found")
                        prog_nu.progress(min(1.0, done_nu / max(len(non_us_tickers), 1)))
        finally:
            prog_nu.empty(); st_nu.empty()

    if not candidates:
        st.session_state["earn_last_debug"] = {
            "scanned": total, "candidates": 0, "workers": workers,
            "days_ahead": days_ahead, "mode": "v15.5-split-market-scan",
        }
        return pd.DataFrame()

    # Preserve market/universe ordering but only for candidates.
    order = {t: i for i, t in enumerate(clean_tickers)}
    candidates = sorted(candidates, key=lambda x: (x[1], order.get(x[0], 999999)))

    # Phase 2: enrich only candidates in parallel.
    prog2 = st.progress(0, text=f"Loading details for {len(candidates)} earnings candidates…")
    status2 = st.empty()
    done = 0
    cand_total = len(candidates)

    def _row_job(item):
        try:
            if len(item) >= 3:
                ticker, earn_date, ns_row = item[0], item[1], item[2]
            else:
                ticker, earn_date, ns_row = item[0], item[1], None
            return _build_earnings_row(ticker, earn_date, today, ns_row)
        except Exception:
            return None

    try:
        with _fut.ThreadPoolExecutor(max_workers=min(workers, max(1, cand_total))) as ex:
            future_map = {ex.submit(_row_job, item): item[0] for item in candidates}
            for fut in _fut.as_completed(future_map):
                done += 1
                row = fut.result()
                if row:
                    rows.append(row)
                if done == 1 or done % 3 == 0 or done == cand_total:
                    status2.caption(f"Loading details ({done}/{cand_total})…")
                    prog2.progress(min(1.0, done / max(cand_total, 1)))
    finally:
        prog2.empty()
        status2.empty()

    st.session_state["earn_last_debug"] = {
        "scanned": total, "candidates": cand_total, "rows": len(rows),
        "workers": workers, "days_ahead": days_ahead, "mode": "nasdaq-then-yahoo-date-and-detail-scan",
        "eps_blank_row_keys_sample": st.session_state.get("earn_eps_blank_row_keys", []),
    }

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
