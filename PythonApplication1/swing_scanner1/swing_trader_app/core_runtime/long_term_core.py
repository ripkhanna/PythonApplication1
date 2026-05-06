"""Extracted runtime section from app_runtime.py lines 5368-5648.
Loaded by app_runtime with exec(..., globals()) to preserve the original single-file behavior.
"""

@st.cache_data(ttl=21600)   # 6-hour cache
def fetch_lt_holdings(etf_ticker: str) -> list:
    """Pull top holdings from an ETF via yfinance funds_data."""
    try:
        tkr = yf.Ticker(etf_ticker)
        for attr in ("portfolio_holdings", "equity_holdings", "top_holdings"):
            try:
                df_h = getattr(tkr.funds_data, attr)
                if df_h is None or df_h.empty:
                    continue
                sym_col = next((c for c in ["Symbol","symbol","Ticker","ticker"]
                                if c in df_h.columns), None)
                if sym_col:
                    syms = df_h[sym_col].dropna().astype(str).tolist()
                else:
                    syms = [str(x) for x in df_h.index.tolist()]
                clean = [s.strip().upper() for s in syms
                         if s.strip().replace("-","").isalpha()
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
    Long-term quality score for a single stock.
    Uses: revenue growth, EPS growth, ROE, debt/equity, analyst target, momentum.
    """
    try:
        info = yf.Ticker(ticker).info or {}
        if not info.get("regularMarketPrice") and not info.get("currentPrice"):
            return {}

        price       = info.get("currentPrice") or info.get("regularMarketPrice") or 0
        fwd_pe      = info.get("forwardPE")
        trail_pe    = info.get("trailingPE")
        peg         = info.get("trailingPegRatio") or info.get("pegRatio")
        roe         = info.get("returnOnEquity")        # decimal
        roa         = info.get("returnOnAssets")
        profit_mg   = info.get("profitMargins")
        rev_growth  = info.get("revenueGrowth")         # YoY decimal
        earn_growth = info.get("earningsGrowth") or info.get("earningsQuarterlyGrowth")
        debt_eq     = info.get("debtToEquity")
        fcf         = info.get("freeCashflow")
        mktcap      = info.get("marketCap") or 0
        div_yield   = info.get("dividendYield") or 0
        tgt         = info.get("targetMeanPrice")
        rec         = info.get("recommendationKey","").upper().replace("_"," ")
        ma50        = info.get("fiftyDayAverage") or 0
        ma200       = info.get("twoHundredDayAverage") or 0
        w52hi       = info.get("fiftyTwoWeekHigh") or 0
        w52lo       = info.get("fiftyTwoWeekLow") or 0
        beta        = info.get("beta") or 1.0
        sector      = info.get("sector","–")
        name        = info.get("longName") or info.get("shortName") or ticker

        # ── Quality scoring (0–10) ─────────────────────────────────────────
        score = 0
        notes = []

        # Revenue growth >10% YoY
        if rev_growth and rev_growth > 0.10:
            score += 2
            notes.append(f"Rev +{rev_growth*100:.0f}%")
        elif rev_growth and rev_growth > 0:
            score += 1
            notes.append(f"Rev +{rev_growth*100:.0f}%")

        # Earnings growth >15% YoY
        if earn_growth and earn_growth > 0.15:
            score += 2
            notes.append(f"EPS +{earn_growth*100:.0f}%")
        elif earn_growth and earn_growth > 0:
            score += 1

        # ROE >15%
        if roe and roe > 0.15:
            score += 1
            notes.append(f"ROE {roe*100:.0f}%")

        # Profit margin >15%
        if profit_mg and profit_mg > 0.15:
            score += 1
            notes.append(f"Margin {profit_mg*100:.0f}%")

        # Reasonable debt: D/E < 1.0 or no debt
        if debt_eq is not None and debt_eq < 100:   # yfinance in %, not ratio
            score += 1
            notes.append("Low debt")

        # Price above MA200 (long-term uptrend)
        if price and ma200 and price > ma200:
            score += 1
            notes.append("Above MA200")

        # Analyst target > price
        upside_pct = 0
        if tgt and price and tgt > price:
            upside_pct = (tgt / price - 1) * 100
            score += 1
            notes.append(f"Upside {upside_pct:.0f}%")

        # Analyst Buy rating
        if rec in ("BUY","STRONG BUY"):
            score += 1
            notes.append(rec)

        # ───────── CONSERVATIVE EXPECTED 1Y RETURN (FIXED) ─────────
        # Previous logic used 30% of the last 1-year price move + dividend.
        # That made stocks that already ran up strongly show unrealistic forward
        # returns. Example: DBS/SG banks could show ~20-35% after a big run.
        # New logic: expected return = conservative price estimate + dividend.
        # It uses capped momentum, analyst upside, quality score and growth,
        # so mature SG banks/blue chips stay closer to realistic 10-14% ranges.

        exp_parts = []

        def _clip_num(x, low, high, default=0.0):
            try:
                if x is None or pd.isna(x):
                    return default
                x = float(x)
                return max(low, min(high, x))
            except Exception:
                return default

        # --- Trailing 1Y momentum: small input only, NOT a forecast ---
        trailing_1y = 0.0
        try:
            hist = yf.Ticker(ticker).history(period="18mo", auto_adjust=True)
            if hist is not None and not hist.empty and "Close" in hist.columns:
                closes = hist["Close"].dropna()
                if len(closes) >= 252:
                    trailing_1y = (float(closes.iloc[-1]) / float(closes.iloc[-252]) - 1) * 100
                elif len(closes) >= 120:
                    trailing_1y = (float(closes.iloc[-1]) / float(closes.iloc[0]) - 1) * 100
        except Exception:
            trailing_1y = 0.0

        # Cap very high past returns; only 10% of past move is counted.
        momentum_component = _clip_num(trailing_1y, -20, 35) * 0.10

        # --- Analyst target upside: useful but capped and discounted ---
        analyst_component = 0.0
        if tgt and price and tgt > 0 and price > 0:
            analyst_component = _clip_num((float(tgt) / float(price) - 1) * 100, -20, 30) * 0.35

        # --- Quality component from score: stable forward return assumption ---
        if score >= 8:
            quality_component = 6.0
        elif score >= 6:
            quality_component = 4.0
        elif score >= 4:
            quality_component = 2.0
        else:
            quality_component = 0.0

        # --- Growth component: capped so high growth does not explode estimate ---
        rg = _clip_num((rev_growth or 0) * 100, -20, 30)
        eg = _clip_num((earn_growth or 0) * 100, -20, 30)
        growth_component = max(0.0, (rg + eg) / 2.0) * 0.10
        growth_component = _clip_num(growth_component, 0, 4)

        # Conservative expected PRICE return before dividends.
        price_return = quality_component + momentum_component + analyst_component + growth_component
        price_return = _clip_num(price_return, -10, 18)

        if abs(price_return) >= 0.1:
            exp_parts.append(f"Price {price_return:.1f}%")

        # --- Dividend return: FIXED / conservative ---
        # yfinance dividendYield can be unreliable for SG stocks.
        # For example DBS may come as 0.10 = 10%, while true forward/trailing
        # yield is usually closer to annual dividend per share / current price.
        def _safe_dividend_return(info_dict, last_price, symbol):
            candidates = []

            # Best source: annual dividend per share divided by current price.
            # This avoids inflated yfinance dividendYield values.
            for k in ("trailingAnnualDividendRate", "dividendRate"):
                try:
                    rate = info_dict.get(k)
                    if rate is not None and last_price:
                        pct = float(rate) / float(last_price) * 100
                        if 0 < pct <= 15:
                            candidates.append(pct)
                except Exception:
                    pass

            # Secondary source: yield fields. Normalize decimal vs percent.
            for k in ("trailingAnnualDividendYield", "dividendYield", "yield", "fiveYearAvgDividendYield"):
                try:
                    v = info_dict.get(k)
                    if v is None:
                        continue
                    pct = float(v) * 100 if float(v) < 1 else float(v)
                    if 0 < pct <= 15:
                        candidates.append(pct)
                except Exception:
                    pass

            if not candidates:
                return 0.0

            # Use the lowest reasonable value to avoid overstating income.
            div_pct = min(candidates)

            # SG banks rarely sustain 8-10% dividend yield; cap them lower.
            if symbol in ("D05.SI", "O39.SI", "U11.SI"):
                div_pct = min(div_pct, 6.5)
            else:
                div_pct = min(div_pct, 8.0)

            return round(max(0.0, div_pct), 1)

        div_return = _safe_dividend_return(info, price, ticker)
        div_yield = div_return / 100

        if div_return > 0:
            exp_parts.append(f"Div {div_return:.1f}%")

        # --- FINAL EXPECTED RETURN ---
        exp_1y = round(price_return + div_return, 1)
        exp_1y = _clip_num(exp_1y, -10, 24)

        exp_1y_str  = f"+{exp_1y:.1f}%" if exp_1y > 0 else f"{exp_1y:.1f}%"
        exp_1y_note = " + ".join(exp_parts) if exp_parts else "-"

        # ── Hold horizon ──────────────────────────────────────────────────
        if score >= 8:
            horizon = "⭐ CORE HOLD (3–5yr)"
            hcol    = "buy"
        elif score >= 6:
            horizon = "✅ BUY & HOLD (1–3yr)"
            hcol    = "watch"
        elif score >= 4:
            horizon = "👀 ACCUMULATE on dips"
            hcol    = "wait"
        else:
            horizon = "⏳ MONITOR only"
            hcol    = "avoid"

        mktcap_str = f"${mktcap/1e9:.1f}B" if mktcap > 1e9 else f"${mktcap/1e6:.0f}M"

        return {
            "Ticker":        ticker,
            "Name":          name[:28],
            "Sector":        sector,
            "Price":         f"${price:.2f}" if price else "–",
            "Mkt Cap":       mktcap_str,
            "Exp 1Y Return": exp_1y_str,
            "Return Breakdown": exp_1y_note,
            "Rev Growth":    f"+{rev_growth*100:.0f}%" if rev_growth else "–",
            "EPS Growth":    f"+{earn_growth*100:.0f}%" if earn_growth else "–",
            "ROE":           f"{roe*100:.0f}%" if roe else "–",
            "Margin":        f"{profit_mg*100:.0f}%" if profit_mg else "–",
            "Fwd PE":        f"{fwd_pe:.1f}x" if fwd_pe else "–",
            "PEG":           f"{peg:.2f}" if peg else "–",
            "Div Yield":     f"{div_yield*100:.1f}%" if div_yield else "–",
            "Beta":          f"{beta:.2f}" if beta else "–",
            "MA200":         "✅" if (price and ma200 and price > ma200) else "❌",
            "Target":        f"${tgt:.2f}" if tgt else "–",
            "Upside":        f"+{upside_pct:.0f}%" if upside_pct else "–",
            "Rec":           rec or "–",
            "Score":         f"{score}/10",
            "Horizon":       horizon,
            "_score":        score,
            "_hcol":         hcol,
            "_exp1y":        exp_1y,
        }
    except Exception:
        return {}


