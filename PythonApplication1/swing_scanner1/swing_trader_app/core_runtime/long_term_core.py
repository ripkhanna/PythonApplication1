"""Long-term scoring core — v3 (near-support fixed).

v3 changes vs v2:
  • RSI and support logic INLINED inside score_lt_stock — eliminates any
    exec/scope issue where helper functions defined outside the cached
    function body might not resolve at call time.
  • Thresholds FIXED after calibrating against real stocks:
        MA50 zone:   -20% … +8%   (was -3%…+8%, broke for any 10%+ pullback)
        MA200 zone:  -8%  … +18%  (was -5%…+12%)
        RSI zone:    25   … 58    (was 28…54)
        Pullback:    8%   … 45%   (was 15%…40%, missed mild corrections)
        Floor:       8%   … 65%   (was 15%…55%)
  • Filter threshold raised from >=2 to >=3 in the tab (see long_term_tab.py)
    so that overbought/barely-off-high stocks don't leak through.
  • Support block wrapped in its own try/except — a data quirk never
    silently prevents the entire row from being returned.
"""

# st, yf, pd, np injected by exec context (app_runtime.py)


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
                if sym_col:
                    syms = df_h[sym_col].dropna().astype(str).tolist()
                else:
                    syms = [str(x) for x in df_h.index.tolist()]
                clean = [s.strip().upper() for s in syms
                         if s.strip().replace("-", "").isalpha()
                         and 1 <= len(s.strip()) <= 6
                         and s.strip().upper() != etf_ticker]
                if clean:
                    return clean[:30]
            except Exception:
                continue
    except Exception:
        pass
    return []


@st.cache_data(ttl=3600)
def score_lt_stock(ticker: str) -> dict:
    """
    Long-term quality + support score for a single stock.

    Quality score  0-10 (unchanged):
        RevGrw>10%(+2)  EPSGrw>15%(+2)  ROE>15%(+1)  Margin>15%(+1)
        LowDebt(+1)     AboveMA200(+1)  Target(+1)   BuyRated(+1)

    Support score  0-5 (all 5 criteria computed from data already fetched):
        1. Near MA50    price in −20% … +8%  of MA50
        2. Near MA200   price in  −8% … +18% of MA200
        3. RSI zone     RSI-14 in 25 … 58
        4. Healthy pull price 8–45% below 52W high
        5. Floor intact price 8–65% above 52W low

    All helpers (RSI calc, support signals) are INLINED so they're always
    in scope regardless of how this module is loaded.
    """
    try:
        info = yf.Ticker(ticker).info or {}
        if not info.get("regularMarketPrice") and not info.get("currentPrice"):
            return {}

        price      = info.get("currentPrice") or info.get("regularMarketPrice") or 0
        if not price:
            return {}

        fwd_pe     = info.get("forwardPE")
        trail_pe   = info.get("trailingPE")
        peg        = info.get("trailingPegRatio") or info.get("pegRatio")
        roe        = info.get("returnOnEquity")
        roa        = info.get("returnOnAssets")
        profit_mg  = info.get("profitMargins")
        rev_growth = info.get("revenueGrowth")
        earn_growth = (info.get("earningsGrowth")
                       or info.get("earningsQuarterlyGrowth"))
        debt_eq    = info.get("debtToEquity")
        fcf        = info.get("freeCashflow")
        mktcap     = info.get("marketCap") or 0
        div_yield  = info.get("dividendYield") or 0
        tgt        = info.get("targetMeanPrice")
        rec        = (info.get("recommendationKey", "")
                      .upper().replace("_", " "))
        ma50       = info.get("fiftyDayAverage") or 0
        ma200      = info.get("twoHundredDayAverage") or 0
        w52hi      = info.get("fiftyTwoWeekHigh") or 0
        w52lo      = info.get("fiftyTwoWeekLow") or 0
        beta       = info.get("beta") or 1.0
        sector     = info.get("sector", "–")
        name       = (info.get("longName") or info.get("shortName") or ticker)

        # ── Quality scoring (0-10) ─────────────────────────────────────────
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

        # ── History fetch (18 months) ─────────────────────────────────────
        # Used for: momentum, RSI-14, volume ratio. One fetch, three signals.
        rsi14      = 50.0
        trailing_1y = 0.0
        vol_ratio   = 1.0
        try:
            hist = yf.Ticker(ticker).history(period="18mo", auto_adjust=True)
            if hist is not None and not hist.empty and "Close" in hist.columns:
                closes = hist["Close"].dropna()

                # Trailing 1Y return
                if len(closes) >= 252:
                    trailing_1y = (float(closes.iloc[-1])
                                   / float(closes.iloc[-252]) - 1) * 100
                elif len(closes) >= 120:
                    trailing_1y = (float(closes.iloc[-1])
                                   / float(closes.iloc[0]) - 1) * 100

                # ── RSI-14 (inlined) — no separate function call ───────────
                # Wilder EWM. Inlined here so it's always in scope regardless
                # of how this module was loaded (exec vs import).
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
                except Exception:
                    rsi14 = 50.0

                # 20d vs 60d volume ratio (accumulation signal)
                if "Volume" in hist.columns:
                    vol = hist["Volume"].dropna()
                    if len(vol) >= 60:
                        v20 = float(vol.iloc[-20:].mean())
                        v60 = float(vol.iloc[-60:].mean())
                        if v60 > 0:
                            vol_ratio = round(v20 / v60, 2)
        except Exception:
            pass

        # ── Support scoring (0-5) — inlined, no external function ─────────
        # Computed from ma50/ma200/w52hi/w52lo already in `info` + rsi14 from
        # history. Zero extra API calls.
        supp_score = 0
        supp_label = "⚪ Approaching"
        supp_flags = []
        vs_ma50_v  = None
        vs_ma200_v = None
        from_hi_v  = None
        from_lo_v  = None
        try:
            def _pct(a, b):
                try:
                    if not b or float(b) == 0:
                        return None
                    return round((float(a) / float(b) - 1) * 100, 1)
                except Exception:
                    return None

            vs_ma50_v  = _pct(price, ma50)
            vs_ma200_v = _pct(price, ma200)
            from_hi_v  = _pct(price, w52hi)   # negative = below high
            from_lo_v  = _pct(price, w52lo)   # positive = above low

            # 1. MA50 support zone — wider because MA50 lags during pullbacks.
            #    A stock 15% below its 52W high is typically 8-15% below MA50.
            if vs_ma50_v is not None and -20 <= vs_ma50_v <= 8:
                supp_score += 1
                supp_flags.append(f"At MA50 ({vs_ma50_v:+.0f}%)")

            # 2. MA200 support zone — the key long-term entry zone.
            if vs_ma200_v is not None and -8 <= vs_ma200_v <= 18:
                supp_score += 1
                supp_flags.append(f"At MA200 ({vs_ma200_v:+.0f}%)")

            # 3. RSI in accumulation/near-oversold zone.
            if 25 <= rsi14 <= 58:
                supp_score += 1
                supp_flags.append(f"RSI {rsi14:.0f}")

            # 4. Healthy pullback from 52W high (not just -3%, not totally broken).
            if from_hi_v is not None and -45 <= from_hi_v <= -8:
                supp_score += 1
                supp_flags.append(f"Off hi {from_hi_v:.0f}%")

            # 5. Support floor intact above 52W low.
            if from_lo_v is not None and 8 <= from_lo_v <= 65:
                supp_score += 1
                supp_flags.append(f"Floor +{from_lo_v:.0f}%")

            if supp_score >= 4:
                supp_label = "🟢 At support"
            elif supp_score >= 2:
                supp_label = "🟡 Near support"
            elif supp_score == 1:
                supp_label = "⚪ Approaching"
            else:
                supp_label = "🔴 Extended/Broken"
        except Exception:
            # Support scoring is best-effort — never prevent the quality row
            supp_score = 0
            supp_label = "⚪ –"

        # ── FCF yield ─────────────────────────────────────────────────────
        fcf_yield_pct = None
        try:
            if fcf and mktcap and mktcap > 0:
                fcf_yield_pct = round(float(fcf) / float(mktcap) * 100, 1)
        except Exception:
            pass

        # ── Expected 1Y return ────────────────────────────────────────────
        def _clip(x, lo, hi, d=0.0):
            try:
                if x is None or (isinstance(x, float) and
                                 (x != x)):   # nan check
                    return d
                return max(lo, min(hi, float(x)))
            except Exception:
                return d

        momentum_component = _clip(trailing_1y, -20, 35) * 0.10
        analyst_component  = 0.0
        if tgt and price and float(tgt) > 0 and float(price) > 0:
            analyst_component = _clip(
                (float(tgt) / float(price) - 1) * 100, -20, 30) * 0.35
        quality_component = (6.0 if score >= 8 else 4.0 if score >= 6
                             else 2.0 if score >= 4 else 0.0)
        rg = _clip((rev_growth  or 0) * 100, -20, 30)
        eg = _clip((earn_growth or 0) * 100, -20, 30)
        growth_component = _clip(max(0.0, (rg + eg) / 2.0) * 0.10, 0, 4)
        price_return = _clip(
            quality_component + momentum_component
            + analyst_component + growth_component, -10, 18)

        exp_parts = []
        if abs(price_return) >= 0.1:
            exp_parts.append(f"Price {price_return:.1f}%")

        # Dividend
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
                if ticker in ("D05.SI", "O39.SI", "U11.SI"):
                    dr = min(dr, 6.5)
                else:
                    dr = min(dr, 8.0)
                div_return = max(0.0, dr)
        except Exception:
            pass

        div_yield = div_return / 100
        if div_return > 0:
            exp_parts.append(f"Div {div_return:.1f}%")
        exp_1y     = _clip(price_return + div_return, -10, 24)
        exp_1y_str = f"+{exp_1y:.1f}%" if exp_1y > 0 else f"{exp_1y:.1f}%"
        exp_1y_note = " + ".join(exp_parts) if exp_parts else "–"

        # ── Hold horizon ──────────────────────────────────────────────────
        if score >= 8:
            horizon = "⭐ CORE HOLD (3–5yr)";  hcol = "buy"
        elif score >= 6:
            horizon = "✅ BUY & HOLD (1–3yr)"; hcol = "watch"
        elif score >= 4:
            horizon = "👀 ACCUMULATE on dips"; hcol = "wait"
        else:
            horizon = "⏳ MONITOR only";        hcol = "avoid"

        mktcap_str = (f"${mktcap/1e9:.1f}B" if mktcap > 1e9
                      else f"${mktcap/1e6:.0f}M")

        def _fmt(v):
            if v is None:
                return "–"
            return f"{v:+.1f}%"

        return {
            # ── Quality fields (unchanged) ─────────────────────────────────
            "Ticker":           ticker,
            "Name":             name[:28],
            "Sector":           sector,
            "Price":            f"${price:.2f}",
            "Mkt Cap":          mktcap_str,
            "Exp 1Y Return":    exp_1y_str,
            "Return Breakdown": exp_1y_note,
            "Rev Growth":       (f"+{rev_growth*100:.0f}%"
                                 if rev_growth else "–"),
            "EPS Growth":       (f"+{earn_growth*100:.0f}%"
                                 if earn_growth else "–"),
            "ROE":              f"{roe*100:.0f}%"      if roe       else "–",
            "Margin":           f"{profit_mg*100:.0f}%" if profit_mg else "–",
            "Fwd PE":           f"{fwd_pe:.1f}x"        if fwd_pe   else "–",
            "PEG":              f"{peg:.2f}"             if peg      else "–",
            "Div Yield":        (f"{div_yield*100:.1f}%"
                                 if div_yield else "–"),
            "Beta":             f"{beta:.2f}"            if beta     else "–",
            "MA200":            "✅" if (price and ma200 and price > ma200)
                                else "❌",
            "Target":           f"${tgt:.2f}"            if tgt      else "–",
            "Upside":           (f"+{upside_pct:.0f}%"
                                 if upside_pct else "–"),
            "Rec":              rec or "–",
            "Score":            f"{score}/10",
            "Horizon":          horizon,
            "_score":           score,
            "_hcol":            hcol,
            "_exp1y":           exp_1y,
            # ── Support fields (new) ───────────────────────────────────────
            "Support":          supp_label,
            "SuppScore":        f"{supp_score}/5",
            "RSI14":            f"{rsi14:.0f}",
            "vsMA50%":          _fmt(vs_ma50_v),
            "vsMA200%":         _fmt(vs_ma200_v),
            "From52WHi%":       _fmt(from_hi_v),
            "VolRatio":         (f"{vol_ratio:.2f}x"
                                 if vol_ratio != 1.0 else "–"),
            "FCFYield":         (f"{fcf_yield_pct:.1f}%"
                                 if fcf_yield_pct else "–"),
            "_supp_score":      supp_score,
            "_rsi14":           rsi14,
            "_supp_flags":      supp_flags,
            "_vs_ma50":         vs_ma50_v,
            "_vs_ma200":        vs_ma200_v,
            "_from_hi":         from_hi_v,
        }
    except Exception:
        return {}
