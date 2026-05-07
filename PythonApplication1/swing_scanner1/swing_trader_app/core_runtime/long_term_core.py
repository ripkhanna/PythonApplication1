"""Long-term scoring core — v4 (cloud-robust + full diagnostics).

v4 fixes vs v3:
  1. _record_app_error called at every failure point inside score_lt_stock,
     so Diagnostics tab shows exactly which step failed for each ticker.
  2. For .SI symbols yf.download is attempted FIRST (not as last resort)
     because it uses a different Yahoo endpoint less prone to cloud 429s.
  3. Per-ticker fetch result stored in st.session_state["lt_ticker_log"]
     so the SG scan section can show a "last scan diagnostics" expander.
  4. Outer except no longer silently swallows — it logs before returning {}.
  5. History-based MA/52W backfill confirmed to run before support scoring.
"""

# st, yf, pd, np, datetime, _record_app_error injected by exec context


def _lt_dl_history(ticker: str):
    """Download 18-month history for a ticker via yf.download.
    Returns a flat-column DataFrame with at least a 'Close' column,
    or None on any failure.
    """
    try:
        dl = yf.download(
            ticker, period="18mo", auto_adjust=True,
            progress=False, threads=False
        )
        if dl is None or dl.empty:
            return None
        # yfinance ≥0.2.18 may return MultiIndex columns for single tickers.
        # Normalise to flat so the rest of the code is version-agnostic.
        if getattr(dl.columns, "nlevels", 1) > 1:
            lvl0 = dl.columns.get_level_values(0)
            lvl1 = dl.columns.get_level_values(1)
            if "Close" in lvl0:
                # (field, ticker) ordering
                dl = dl.xs("Close", axis=1, level=0).to_frame("Close")
                # Bring other columns back if available
                for col in ("High", "Low", "Volume", "Open"):
                    try:
                        s = dl.xs(col, axis=1, level=0) if col in lvl0 else None
                        if s is not None:
                            dl[col] = s
                    except Exception:
                        pass
            elif "Close" in lvl1:
                # (ticker, field) ordering
                dl = dl.xs("Close", axis=1, level=1).to_frame("Close")
        # Final safety: keep only the Close column if anything above went wrong
        if "Close" not in dl.columns:
            return None
        return dl
    except Exception as e:
        _record_app_error(
            "lt_dl_history",
            e,
            ticker=ticker,
            message=f"yf.download failed for {ticker}: {type(e).__name__}: {e}",
        )
        return None


@st.cache_data(ttl=21600)
def fetch_lt_holdings(etf_ticker: str) -> list:
    """Pull top holdings from an ETF via yfinance funds_data."""
    try:
        tkr = yf.Ticker(etf_ticker)
        for attr in ("portfolio_holdings", "equity_holdings", "top_holdings"):
            try:
                df_h = getattr(tkr.funds_data, attr)
                if df_h is None or df_h.empty:
                    continue
                sym_col = next(
                    (c for c in ["Symbol", "symbol", "Ticker", "ticker"]
                     if c in df_h.columns), None
                )
                syms = (
                    df_h[sym_col].dropna().astype(str).tolist()
                    if sym_col else
                    [str(x) for x in df_h.index.tolist()]
                )
                clean = [s.strip().upper() for s in syms
                         if s.strip().replace("-", "").isalpha()
                         and 1 <= len(s.strip()) <= 6
                         and s.strip().upper() != etf_ticker]
                if clean:
                    return clean[:30]
            except Exception:
                continue
    except Exception as e:
        _record_app_error("fetch_lt_holdings", e, ticker=etf_ticker)
    return []


@st.cache_data(ttl=3600)
def score_lt_stock(ticker: str) -> dict:
    """
    Long-term quality + support score for a single stock.
    Logs every failure step to _record_app_error so the Diagnostics tab
    shows exactly what went wrong for each ticker on cloud deployments.

    Returns {} only when a price cannot be obtained at all.
    Returns a partial row (price present, fundamentals may be "–") rather
    than {} when yf.info is empty but history worked — this way the ticker
    still appears in the grid even when Yahoo omits SGX fundamentals.
    """
    _log_steps = []   # per-ticker mini-log stored in session_state after return

    def _step(msg):
        _log_steps.append(msg)

    def _fail(step_msg, exc=None):
        full = f"{step_msg}: {type(exc).__name__}: {exc}" if exc else step_msg
        _log_steps.append(f"FAIL {full}")
        _record_app_error(
            context="score_lt_stock",
            exc=exc,
            message=full,
            ticker=ticker,
            severity="warning",
        )

    try:
        is_sgx = str(ticker).upper().endswith(".SI")
        tkr_obj = yf.Ticker(ticker)

        # ── STEP 1: info (fundamental metadata) ───────────────────────────
        info = {}
        try:
            info = tkr_obj.info or {}
            if not isinstance(info, dict):
                info = {}
            _step(f"info ok, keys={len(info)}")
        except Exception as e:
            _fail("info fetch", e)
            info = {}

        # ── STEP 2: price — try info first, then fast_info, then history ──
        # For .SI symbols on cloud, info regularly omits price, so we try
        # yf.download early rather than as a last resort.
        price = (
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or 0
        )
        _hist = None  # shared history DataFrame, filled below

        if not price:
            try:
                fi = getattr(tkr_obj, "fast_info", None) or {}
                price = (
                    fi.get("last_price") or fi.get("lastPrice")
                    or fi.get("regular_market_price") or 0
                )
                if price:
                    _step(f"price from fast_info: {price:.3f}")
            except Exception as e:
                _fail("fast_info", e)

        if not price:
            # For .SI symbols try yf.download first — it hits a different
            # Yahoo endpoint that is more reliable on Streamlit Cloud.
            if is_sgx:
                _hist = _lt_dl_history(ticker)
                if _hist is not None and "Close" in _hist.columns:
                    closes = _hist["Close"].dropna()
                    if len(closes):
                        price = float(closes.iloc[-1])
                        _step(f"price from yf.download: {price:.3f}")
            if not price:
                try:
                    raw_hist = tkr_obj.history(period="18mo", auto_adjust=True)
                    if (raw_hist is not None and not raw_hist.empty
                            and "Close" in raw_hist.columns):
                        closes = raw_hist["Close"].dropna()
                        if len(closes):
                            price = float(closes.iloc[-1])
                            _hist = raw_hist
                            _step(f"price from tkr.history: {price:.3f}")
                except Exception as e:
                    _fail("tkr.history for price", e)

            # Non-.SI: also try download if still no price
            if not price and not is_sgx:
                _hist = _lt_dl_history(ticker)
                if _hist is not None and "Close" in _hist.columns:
                    closes = _hist["Close"].dropna()
                    if len(closes):
                        price = float(closes.iloc[-1])
                        _step(f"price from yf.download (non-.SI): {price:.3f}")

        if not price:
            _fail("no price after all fallbacks — returning {}")
            # Flush the step log before returning
            try:
                log = st.session_state.setdefault("lt_ticker_log", {})
                log[ticker] = {"steps": _log_steps, "ok": False, "price": 0}
            except Exception:
                pass
            return {}

        _step(f"price confirmed: {price:.3f}")

        # ── STEP 3: pull fundamental fields from info ─────────────────────
        fwd_pe      = info.get("forwardPE")
        peg         = info.get("trailingPegRatio") or info.get("pegRatio")
        roe         = info.get("returnOnEquity")
        profit_mg   = info.get("profitMargins")
        rev_growth  = info.get("revenueGrowth")
        earn_growth = (info.get("earningsGrowth")
                       or info.get("earningsQuarterlyGrowth"))
        debt_eq     = info.get("debtToEquity")
        fcf         = info.get("freeCashflow")
        mktcap      = info.get("marketCap") or 0
        tgt         = info.get("targetMeanPrice")
        rec         = (info.get("recommendationKey", "")
                       .upper().replace("_", " "))
        ma50        = info.get("fiftyDayAverage") or 0
        ma200       = info.get("twoHundredDayAverage") or 0
        w52hi       = info.get("fiftyTwoWeekHigh") or 0
        w52lo       = info.get("fiftyTwoWeekLow") or 0
        beta        = info.get("beta") or 1.0
        sector      = info.get("sector", "–")
        name        = info.get("longName") or info.get("shortName") or ticker

        has_fundamentals = any([roe, profit_mg, rev_growth, earn_growth, tgt, rec])
        _step(f"fundamentals present: {has_fundamentals}")

        # ── STEP 4: quality scoring (0-10) ────────────────────────────────
        score = 0
        notes = []

        if rev_growth and rev_growth > 0.10:
            score += 2; notes.append(f"Rev +{rev_growth*100:.0f}%")
        elif rev_growth and rev_growth > 0:
            score += 1; notes.append(f"Rev +{rev_growth*100:.0f}%")

        if earn_growth and earn_growth > 0.15:
            score += 2; notes.append(f"EPS +{earn_growth*100:.0f}%")
        elif earn_growth and earn_growth > 0:
            score += 1

        if roe and roe > 0.15:
            score += 1; notes.append(f"ROE {roe*100:.0f}%")

        if profit_mg and profit_mg > 0.15:
            score += 1; notes.append(f"Margin {profit_mg*100:.0f}%")

        if debt_eq is not None and debt_eq < 100:
            score += 1; notes.append("Low debt")

        if price and ma200 and price > ma200:
            score += 1; notes.append("Above MA200")

        upside_pct = 0
        if tgt and price and tgt > price:
            upside_pct = (tgt / price - 1) * 100
            score += 1; notes.append(f"Upside {upside_pct:.0f}%")

        if rec in ("BUY", "STRONG BUY"):
            score += 1; notes.append(rec)

        _step(f"quality score before history: {score}/10")

        # ── STEP 5: history for RSI, MA backfill, volume ──────────────────
        rsi14       = 50.0
        trailing_1y = 0.0
        vol_ratio   = 1.0

        try:
            # Re-use history already fetched in the price step if available
            if _hist is None:
                try:
                    _hist = tkr_obj.history(period="18mo", auto_adjust=True)
                except Exception as e:
                    _fail("history for indicators", e)
                    _hist = None

            if _hist is not None and not _hist.empty and "Close" in _hist.columns:
                closes = _hist["Close"].dropna()
                _step(f"history bars: {len(closes)}")

                # Trailing 1Y return
                if len(closes) >= 252:
                    trailing_1y = (float(closes.iloc[-1])
                                   / float(closes.iloc[-252]) - 1) * 100
                elif len(closes) >= 120:
                    trailing_1y = (float(closes.iloc[-1])
                                   / float(closes.iloc[0]) - 1) * 100

                # RSI-14 (Wilder EWM, inlined)
                try:
                    if len(closes) >= 16:
                        delta = closes.diff().dropna()
                        gain  = delta.clip(lower=0)
                        loss  = (-delta).clip(lower=0)
                        avg_g = gain.ewm(com=13, min_periods=14).mean()
                        avg_l = loss.ewm(com=13, min_periods=14).mean()
                        rs    = avg_g / avg_l.replace(0, 1e-9)
                        rsi_s = 100 - (100 / (1 + rs))
                        rsi14 = float(round(rsi_s.iloc[-1], 1))
                        _step(f"RSI14={rsi14:.1f}")
                except Exception as e:
                    _fail("RSI calc", e)

                # Backfill MA/52W from history when info omitted them
                try:
                    if not ma50 and len(closes) >= 50:
                        ma50 = float(closes.iloc[-50:].mean())
                    if not ma200 and len(closes) >= 200:
                        ma200 = float(closes.iloc[-200:].mean())
                    if not w52hi and len(closes) >= 60:
                        w52hi = float(
                            closes.iloc[-252:].max()
                            if len(closes) >= 252 else closes.max()
                        )
                    if not w52lo and len(closes) >= 60:
                        w52lo = float(
                            closes.iloc[-252:].min()
                            if len(closes) >= 252 else closes.min()
                        )
                    if any([ma50, ma200, w52hi, w52lo]):
                        _step(
                            f"MA backfill: ma50={ma50:.2f} ma200={ma200:.2f} "
                            f"hi={w52hi:.2f} lo={w52lo:.2f}"
                        )
                except Exception as e:
                    _fail("MA backfill", e)

                # Give AboveMA200 quality point now that ma200 may be filled
                if price and ma200 and price > ma200 and "Above MA200" not in notes:
                    score += 1; notes.append("Above MA200 (hist)")
                    _step("AboveMA200 from history backfill +1")

                # Volume ratio 20d/60d
                if "Volume" in _hist.columns:
                    try:
                        vol = _hist["Volume"].dropna()
                        if len(vol) >= 60:
                            v20 = float(vol.iloc[-20:].mean())
                            v60 = float(vol.iloc[-60:].mean())
                            if v60 > 0:
                                vol_ratio = round(v20 / v60, 2)
                    except Exception:
                        pass
            else:
                _fail("history empty or missing Close column — using defaults for indicators")

        except Exception as e:
            _fail("history block outer", e)

        # ── STEP 6: SGX sparse-data bonus ─────────────────────────────────
        if is_sgx and score < 4:
            sgx_added = []
            div_pct = 0.0
            try:
                for k in ("trailingAnnualDividendRate", "dividendRate"):
                    v = info.get(k)
                    if v and price:
                        p = float(v) / float(price) * 100
                        if 0 < p <= 15:
                            div_pct = p
                            break
                if not div_pct:
                    for k in ("trailingAnnualDividendYield", "dividendYield"):
                        v = info.get(k)
                        if v:
                            p = float(v) * 100 if float(v) < 1 else float(v)
                            if 0 < p <= 15:
                                div_pct = p
                                break
            except Exception:
                pass
            if div_pct >= 3.0:
                score += 1; sgx_added.append(f"Div {div_pct:.1f}%")
            if trailing_1y > 0:
                score += 1; sgx_added.append("1Y momentum")
            if price and ma200 and price > ma200 and "Above MA200" not in notes and "Above MA200 (hist)" not in notes:
                score += 1; sgx_added.append("Above MA200")
            if vol_ratio >= 1.05:
                score += 1; sgx_added.append("Volume improving")
            score = min(score, 6)
            if sgx_added:
                notes.extend(sgx_added)
                _step(f"SGX bonus: {sgx_added} → score={score}")

        _step(f"final quality score: {score}/10")

        # ── STEP 7: support scoring (0-5) — inlined ───────────────────────
        supp_score = 0
        supp_label = "⚪ Approaching"
        supp_flags = []
        vs_ma50_v = vs_ma200_v = from_hi_v = from_lo_v = None

        try:
            def _pct(a, b):
                try:
                    return round((float(a) / float(b) - 1) * 100, 1) if b and float(b) != 0 else None
                except Exception:
                    return None

            vs_ma50_v  = _pct(price, ma50)
            vs_ma200_v = _pct(price, ma200)
            from_hi_v  = _pct(price, w52hi)
            from_lo_v  = _pct(price, w52lo)

            if vs_ma50_v  is not None and -20 <= vs_ma50_v  <= 8:
                supp_score += 1; supp_flags.append(f"At MA50 ({vs_ma50_v:+.0f}%)")
            if vs_ma200_v is not None and -8  <= vs_ma200_v <= 18:
                supp_score += 1; supp_flags.append(f"At MA200 ({vs_ma200_v:+.0f}%)")
            if 25 <= rsi14 <= 58:
                supp_score += 1; supp_flags.append(f"RSI {rsi14:.0f}")
            if from_hi_v  is not None and -45 <= from_hi_v  <= -8:
                supp_score += 1; supp_flags.append(f"Off hi {from_hi_v:.0f}%")
            if from_lo_v  is not None and 8   <= from_lo_v  <= 65:
                supp_score += 1; supp_flags.append(f"Floor +{from_lo_v:.0f}%")

            supp_label = (
                "🟢 At support"       if supp_score >= 4 else
                "🟡 Near support"     if supp_score >= 2 else
                "⚪ Approaching"      if supp_score == 1 else
                "🔴 Extended/Broken"
            )
            _step(
                f"support {supp_score}/5 — {supp_label} — "
                f"vsMA50={vs_ma50_v} vsMA200={vs_ma200_v} "
                f"fromHi={from_hi_v} fromLo={from_lo_v} RSI={rsi14}"
            )
        except Exception as e:
            _fail("support scoring", e)

        # ── STEP 8: expected 1Y return ────────────────────────────────────
        def _clip(x, lo, hi, d=0.0):
            try:
                return d if (x is None or x != x) else max(lo, min(hi, float(x)))
            except Exception:
                return d

        momentum_component = _clip(trailing_1y, -20, 35) * 0.10
        analyst_component  = 0.0
        if tgt and price and float(tgt) > 0:
            analyst_component = _clip((float(tgt) / float(price) - 1) * 100, -20, 30) * 0.35
        quality_component = 6.0 if score >= 8 else 4.0 if score >= 6 else 2.0 if score >= 4 else 0.0
        rg = _clip((rev_growth  or 0) * 100, -20, 30)
        eg = _clip((earn_growth or 0) * 100, -20, 30)
        growth_component = _clip(max(0.0, (rg + eg) / 2.0) * 0.10, 0, 4)
        price_return = _clip(
            quality_component + momentum_component + analyst_component + growth_component,
            -10, 18
        )
        exp_parts = []
        if abs(price_return) >= 0.1:
            exp_parts.append(f"Price {price_return:.1f}%")

        div_return = 0.0
        try:
            candidates = []
            for k in ("trailingAnnualDividendRate", "dividendRate"):
                v = info.get(k)
                if v is not None and price:
                    p = float(v) / float(price) * 100
                    if 0 < p <= 15:
                        candidates.append(p)
            for k in ("trailingAnnualDividendYield", "dividendYield",
                       "yield", "fiveYearAvgDividendYield"):
                v = info.get(k)
                if v is None:
                    continue
                p = float(v) * 100 if float(v) < 1 else float(v)
                if 0 < p <= 15:
                    candidates.append(p)
            if candidates:
                dr = min(candidates)
                dr = min(dr, 6.5 if ticker in ("D05.SI", "O39.SI", "U11.SI") else 8.0)
                div_return = max(0.0, dr)
        except Exception:
            pass

        div_yield = div_return / 100
        if div_return > 0:
            exp_parts.append(f"Div {div_return:.1f}%")
        exp_1y = _clip(price_return + div_return, -10, 24)
        exp_1y_str  = f"+{exp_1y:.1f}%" if exp_1y > 0 else f"{exp_1y:.1f}%"
        exp_1y_note = " + ".join(exp_parts) if exp_parts else "–"

        # ── STEP 9: horizon ───────────────────────────────────────────────
        if score >= 8:
            horizon = "⭐ CORE HOLD (3–5yr)";  hcol = "buy"
        elif score >= 6:
            horizon = "✅ BUY & HOLD (1–3yr)"; hcol = "watch"
        elif score >= 4:
            horizon = "👀 ACCUMULATE on dips"; hcol = "wait"
        else:
            horizon = "⏳ MONITOR only";        hcol = "avoid"

        fcf_yield_pct = None
        try:
            if fcf and mktcap and mktcap > 0:
                fcf_yield_pct = round(float(fcf) / float(mktcap) * 100, 1)
        except Exception:
            pass

        mktcap_str = (f"${mktcap/1e9:.1f}B" if mktcap > 1e9 else f"${mktcap/1e6:.0f}M") if mktcap else "–"

        def _fmt(v):
            return "–" if v is None else f"{v:+.1f}%"

        _step(f"OK — horizon={horizon} supp={supp_score}/5")

        # Flush per-ticker log to session_state
        try:
            log = st.session_state.setdefault("lt_ticker_log", {})
            log[ticker] = {
                "ok": True, "price": round(float(price), 3),
                "score": score, "supp": supp_score,
                "has_fundamentals": has_fundamentals,
                "steps": _log_steps,
            }
        except Exception:
            pass

        return {
            "Ticker":           ticker,
            "Name":             str(name)[:28],
            "Sector":           sector,
            "Price":            f"${price:.2f}",
            "Mkt Cap":          mktcap_str,
            "Exp 1Y Return":    exp_1y_str,
            "Return Breakdown": exp_1y_note,
            "Rev Growth":       (f"+{rev_growth*100:.0f}%" if rev_growth else "–"),
            "EPS Growth":       (f"+{earn_growth*100:.0f}%" if earn_growth else "–"),
            "ROE":              f"{roe*100:.0f}%" if roe else "–",
            "Margin":           f"{profit_mg*100:.0f}%" if profit_mg else "–",
            "Fwd PE":           f"{fwd_pe:.1f}x" if fwd_pe else "–",
            "PEG":              f"{peg:.2f}" if peg else "–",
            "Div Yield":        f"{div_yield*100:.1f}%" if div_yield else "–",
            "Beta":             f"{beta:.2f}" if beta else "–",
            "MA200":            "✅" if (price and ma200 and price > ma200) else "❌",
            "Target":           f"${tgt:.2f}" if tgt else "–",
            "Upside":           f"+{upside_pct:.0f}%" if upside_pct else "–",
            "Rec":              rec or "–",
            "Score":            f"{score}/10",
            "Horizon":          horizon,
            "_score":           score,
            "_hcol":            hcol,
            "_exp1y":           exp_1y,
            "Support":          supp_label,
            "SuppScore":        f"{supp_score}/5",
            "RSI14":            f"{rsi14:.0f}",
            "vsMA50%":          _fmt(vs_ma50_v),
            "vsMA200%":         _fmt(vs_ma200_v),
            "From52WHi%":       _fmt(from_hi_v),
            "VolRatio":         f"{vol_ratio:.2f}x" if vol_ratio != 1.0 else "–",
            "FCFYield":         f"{fcf_yield_pct:.1f}%" if fcf_yield_pct else "–",
            "_supp_score":      supp_score,
            "_rsi14":           rsi14,
            "_supp_flags":      supp_flags,
            "_vs_ma50":         vs_ma50_v,
            "_vs_ma200":        vs_ma200_v,
            "_from_hi":         from_hi_v,
        }

    except Exception as e:
        _record_app_error(
            "score_lt_stock_outer",
            e,
            ticker=ticker,
            message=f"Unhandled exception: {type(e).__name__}: {e}",
            extra={"steps_so_far": _log_steps},
        )
        try:
            log = st.session_state.setdefault("lt_ticker_log", {})
            log[ticker] = {"ok": False, "price": 0,
                           "error": str(e), "steps": _log_steps}
        except Exception:
            pass
        return {}
