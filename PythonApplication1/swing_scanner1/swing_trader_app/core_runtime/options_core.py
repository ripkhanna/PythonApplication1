"""Extracted runtime section from app_runtime.py lines 1609-1963.
Loaded by app_runtime with exec(..., globals()) to preserve the original single-file behavior.
"""

# ─────────────────────────────────────────────────────────────────────────────
def _options_backend(ticker: str) -> str:
    """
    Returns the data backend that can serve this ticker's option chain:
      'yfinance' for US-listed names, 'nse' for Indian F&O stocks (.NS),
      '' for everything else (SGX, HK, ASX, EU, etc.).
    """
    if not ticker or not isinstance(ticker, str):
        return ""
    if ticker.startswith("^"):
        return ""
    if ticker.endswith(".NS"):
        return "nse" if _nse_opt_available else ""
    # Any other non-US suffix is unsupported (SGX, HK, ASX, EU, JP, KR, etc.)
    non_us_suffixes = (".SI", ".BO", ".HK", ".T", ".L",
                       ".PA", ".DE", ".SW", ".AX", ".TO", ".KS", ".SS", ".SZ")
    if any(s in ticker for s in non_us_suffixes):
        return ""
    return "yfinance"


def _is_us_ticker_for_options(ticker: str) -> bool:
    """
    Backwards-compatible boolean check (kept so existing call sites in
    fetch_analysis don't need to change). True whenever ANY backend can
    fetch an option chain for the ticker — US via yfinance OR India via
    nsepython. The name is kept for compat; the meaning is now broader.
    """
    return _options_backend(ticker) != ""


def _fetch_chain_yf(ticker: str, max_expiries: int):
    """yfinance backend — used for US tickers. Returns list of
    (expiry_str, calls_df, puts_df). Empty list on failure."""
    try:
        tk = yf.Ticker(ticker)
        exps = tk.options
        if not exps:
            return []
        out = []
        for exp in exps[:max_expiries]:
            try:
                ch = tk.option_chain(exp)
                calls = ch.calls.copy() if ch.calls is not None else pd.DataFrame()
                puts  = ch.puts.copy()  if ch.puts  is not None else pd.DataFrame()
                if calls.empty and puts.empty:
                    continue
                out.append((exp, calls, puts))
            except Exception:
                continue
        return out
    except Exception:
        return []


def _fetch_chain_nse(ticker: str, max_expiries: int):
    """
    NSE backend — used for Indian .NS tickers via nsepython. Returns the
    same shape as the yfinance backend so downstream code is identical.

    NSE returns a single dict containing ALL strikes for ALL expiries; we
    split it per expiry and map fields to yfinance column names:
      strikePrice          → strike
      lastPrice            → lastPrice
      bidprice / askPrice  → bid / ask
      totalTradedVolume    → volume
      openInterest         → openInterest
      impliedVolatility    → impliedVolatility (NSE returns %, divide by 100
                              so it matches yfinance's fractional convention)

    Resilience: nsepython's first call after a cold start often fails because
    its Cloudflare cookie handshake hasn't run yet. We retry once after a
    1.5s pause before giving up — this dramatically improves first-scan
    success rates from non-Indian IPs.
    """
    if not _nse_opt_available:
        return []
    sym = ticker.replace(".NS", "")

    # Try up to 2 times; nsepython's first call frequently fails on cold session
    oc = None
    for attempt in range(2):
        try:
            oc = _nse_oc(sym)
            if oc and isinstance(oc, dict) and "records" in oc:
                break
        except Exception:
            oc = None
        if attempt == 0:
            try:
                import time
                time.sleep(1.5)
            except Exception:
                pass

    if not oc or not isinstance(oc, dict) or "records" not in oc:
        return []

    try:
        records = oc["records"]
        expiries = records.get("expiryDates", []) or []
        all_data = records.get("data", []) or []
        if not expiries or not all_data:
            return []

        out = []
        for exp in expiries[:max_expiries]:
            calls_rows, puts_rows = [], []
            for r in all_data:
                if r.get("expiryDate") != exp:
                    continue
                strike = r.get("strikePrice")
                if strike is None:
                    continue
                ce = r.get("CE", {}) or {}
                pe = r.get("PE", {}) or {}
                if ce:
                    calls_rows.append({
                        "strike":            float(strike),
                        "lastPrice":         float(ce.get("lastPrice", 0) or 0),
                        "bid":               float(ce.get("bidprice", 0) or 0),
                        "ask":               float(ce.get("askPrice", 0) or 0),
                        "volume":            float(ce.get("totalTradedVolume", 0) or 0),
                        "openInterest":      float(ce.get("openInterest", 0) or 0),
                        "impliedVolatility": float(ce.get("impliedVolatility", 0) or 0) / 100.0,
                    })
                if pe:
                    puts_rows.append({
                        "strike":            float(strike),
                        "lastPrice":         float(pe.get("lastPrice", 0) or 0),
                        "bid":               float(pe.get("bidprice", 0) or 0),
                        "ask":               float(pe.get("askPrice", 0) or 0),
                        "volume":            float(pe.get("totalTradedVolume", 0) or 0),
                        "openInterest":      float(pe.get("openInterest", 0) or 0),
                        "impliedVolatility": float(pe.get("impliedVolatility", 0) or 0) / 100.0,
                    })
            calls_df = pd.DataFrame(calls_rows)
            puts_df  = pd.DataFrame(puts_rows)
            if calls_df.empty and puts_df.empty:
                continue
            # Normalise NSE expiry string "DD-MMM-YYYY" → "YYYY-MM-DD" so the
            # downstream pd.Timestamp(...) call in compute_options_signals works.
            try:
                exp_iso = pd.Timestamp(exp).strftime("%Y-%m-%d")
            except Exception:
                exp_iso = exp
            out.append((exp_iso, calls_df, puts_df))
        return out
    except Exception:
        return []


@st.cache_data(ttl=15 * 60, show_spinner=False)
def fetch_options_chain(ticker: str, max_expiries: int = 2):
    """
    Unified entry point for option chain data — dispatches to the right
    backend (yfinance for US, nsepython for Indian F&O). Cached 15 min.
    Returns [] on failure / unsupported tickers.
    """
    backend = _options_backend(ticker)
    if backend == "yfinance":
        return _fetch_chain_yf(ticker, max_expiries)
    if backend == "nse":
        return _fetch_chain_nse(ticker, max_expiries)
    return []


def _atm_iv(df: pd.DataFrame, spot: float):
    """Implied vol at the strike closest to spot (rejects junk IVs)."""
    if df is None or df.empty or "strike" not in df.columns or "impliedVolatility" not in df.columns:
        return None
    d = df.dropna(subset=["strike", "impliedVolatility"])
    d = d[d["impliedVolatility"] > 0.01]
    if d.empty:
        return None
    idx = (d["strike"] - spot).abs().idxmin()
    iv = float(d.loc[idx, "impliedVolatility"])
    return iv if 0.05 <= iv <= 5.0 else None


def _iv_at_moneyness(df: pd.DataFrame, spot: float, moneyness_pct: float):
    """IV at the strike closest to spot * (1 + moneyness_pct/100)."""
    if df is None or df.empty:
        return None
    target = spot * (1 + moneyness_pct / 100.0)
    d = df.dropna(subset=["strike", "impliedVolatility"])
    d = d[d["impliedVolatility"] > 0.01]
    if d.empty:
        return None
    idx = (d["strike"] - target).abs().idxmin()
    iv = float(d.loc[idx, "impliedVolatility"])
    return iv if 0.05 <= iv <= 5.0 else None


def _atm_straddle_pct(calls: pd.DataFrame, puts: pd.DataFrame, spot: float):
    """ATM straddle (call mid + put mid) as a fraction of spot — the market's
    implied move for that expiry."""
    if calls is None or puts is None or calls.empty or puts.empty or spot <= 0:
        return None
    try:
        ci = (calls["strike"] - spot).abs().idxmin()
        pi = (puts["strike"]  - spot).abs().idxmin()
        c_ask = float(calls.loc[ci, "ask"]) if "ask" in calls.columns else 0
        c_bid = float(calls.loc[ci, "bid"]) if "bid" in calls.columns else 0
        p_ask = float(puts.loc[pi,  "ask"]) if "ask" in puts.columns  else 0
        p_bid = float(puts.loc[pi,  "bid"]) if "bid" in puts.columns  else 0
        cm = (c_bid + c_ask) / 2 if c_ask > 0 else float(calls.loc[ci, "lastPrice"])
        pm = (p_bid + p_ask) / 2 if p_ask > 0 else float(puts.loc[pi,  "lastPrice"])
        if cm <= 0 or pm <= 0:
            return None
        return float((cm + pm) / spot)
    except Exception:
        return None


def _unusual_flow(df: pd.DataFrame, spot: float,
                  near_pct: float = 10.0, vol_to_oi_min: float = 3.0,
                  min_total_vol: int = 100):
    """
    True if any near-the-money strike has today's volume > vol_to_oi_min × OI
    AND the near-money zone has meaningful overall volume. Catches "unusual
    options activity" that often front-runs price.
    """
    if df is None or df.empty:
        return False
    if "volume" not in df.columns or "openInterest" not in df.columns or "strike" not in df.columns:
        return False
    d = df.dropna(subset=["strike"]).copy()
    d["volume"]       = d["volume"].fillna(0)
    d["openInterest"] = d["openInterest"].fillna(0)
    lo = spot * (1 - near_pct / 100)
    hi = spot * (1 + near_pct / 100)
    near = d[(d["strike"] >= lo) & (d["strike"] <= hi)]
    if near.empty or near["volume"].sum() < min_total_vol:
        return False
    near = near[near["openInterest"] >= 50]
    if near.empty:
        return False
    near["ratio"] = near["volume"] / near["openInterest"].replace(0, np.nan)
    return bool((near["ratio"] >= vol_to_oi_min).any())


def _pc_volume_ratio(calls: pd.DataFrame, puts: pd.DataFrame):
    """Total put volume / total call volume across the chain."""
    if calls is None or puts is None or calls.empty or puts.empty:
        return None
    cv = float(calls.get("volume", pd.Series(dtype=float)).fillna(0).sum())
    pv = float(puts.get("volume",  pd.Series(dtype=float)).fillna(0).sum())
    if cv <= 0:
        return None
    return pv / cv


def compute_options_signals(ticker: str, spot: float,
                            realized_vol_20d_pct: float = None):
    """
    Forward-looking options-derived signals.

    Backend is auto-selected by ticker suffix via _options_backend():
      • US tickers          → yfinance Ticker.options
      • Indian .NS tickers  → nsepython (only F&O-listed stocks have chains)
      • SGX/HK/EU/etc.      → no backend, returns empty dicts

    Returns (long_signals, short_signals, raw) — same shape as
    compute_all_signals so dicts can be merged before bayesian_prob().

    On any failure or unsupported ticker: returns empty dicts → no effect.

    realized_vol_20d_pct: 20-day annualized realized vol in % (e.g. 35.0).
        Used as a poor-man's IV-Rank denominator since neither yfinance nor
        nsepython provides a historical IV time series.
    """
    empty = ({}, {}, {})
    if not _is_us_ticker_for_options(ticker) or spot is None or spot <= 0:
        return empty
    chains = fetch_options_chain(ticker, max_expiries=2)
    if not chains:
        return empty

    front_exp, front_calls, front_puts = chains[0]
    second = chains[1] if len(chains) > 1 else None

    front_atm_iv = _atm_iv(front_calls, spot) or _atm_iv(front_puts, spot)
    if front_atm_iv is None:
        return empty

    # ── Implied move: ATM straddle as % of spot, scaled to ~10 trading days ──
    front_im = _atm_straddle_pct(front_calls, front_puts, spot)
    try:
        days_front = max(1, (pd.Timestamp(front_exp).date() - datetime.today().date()).days)
    except Exception:
        days_front = 14
    implied_move_2w = (front_im * (10 / days_front) ** 0.5) if (front_im and days_front > 0) else None

    # ── IV term structure: front vs back month ───────────────────────────────
    term_inversion = False
    term_slope_pp  = None
    if second is not None:
        _, sc_calls, sc_puts = second
        back_atm_iv = _atm_iv(sc_calls, spot) or _atm_iv(sc_puts, spot)
        if back_atm_iv is not None:
            term_slope_pp  = (back_atm_iv - front_atm_iv) * 100      # IV pp
            term_inversion = front_atm_iv > back_atm_iv * 1.05       # ≥5% inverted

    # ── Skew: 10% OTM call IV vs 10% OTM put IV (proxy for 25Δ risk reversal)
    iv_call_otm = _iv_at_moneyness(front_calls, spot, +10.0)
    iv_put_otm  = _iv_at_moneyness(front_puts,  spot, -10.0)
    risk_reversal = (iv_call_otm - iv_put_otm) if (iv_call_otm is not None and iv_put_otm is not None) else None
    call_skew_bullish = (risk_reversal is not None) and (risk_reversal >= 0.0)
    put_skew_bearish  = (risk_reversal is not None) and (risk_reversal <= -0.05)

    # ── Flow / positioning ───────────────────────────────────────────────────
    unusual_call_flow = _unusual_flow(front_calls, spot)
    unusual_put_flow  = _unusual_flow(front_puts,  spot)
    pc_vol = _pc_volume_ratio(front_calls, front_puts)
    pc_volume_low  = (pc_vol is not None) and (pc_vol < 0.6)
    pc_volume_high = (pc_vol is not None) and (pc_vol > 1.5)

    # ── IV vs realized vol (proxy IV-Rank since true IVR needs history) ──────
    iv_rank_proxy = iv_rich = iv_cheap = None
    if realized_vol_20d_pct and realized_vol_20d_pct > 0:
        ratio = (front_atm_iv * 100) / realized_vol_20d_pct
        iv_rank_proxy = ratio
        iv_rich  = ratio > 1.40   # IV expensive vs realized — usually event premium
        iv_cheap = ratio < 0.85   # IV cheap — calm regime, often pre-trend

    long_signals = {
        "opt_unusual_call_flow":   bool(unusual_call_flow),
        "opt_call_skew_bullish":   bool(call_skew_bullish),
        "opt_pc_volume_low":       bool(pc_volume_low),
        "opt_iv_cheap":            bool(iv_cheap),
    }
    short_signals = {
        "opt_unusual_put_flow":    bool(unusual_put_flow),
        "opt_put_skew_bearish":    bool(put_skew_bearish),
        "opt_term_inversion":      bool(term_inversion),
        "opt_pc_volume_high":      bool(pc_volume_high),
    }
    raw = {
        "front_atm_iv":    front_atm_iv,
        "front_im_pct":    front_im,
        "implied_move_2w": implied_move_2w,
        "term_slope_pp":   term_slope_pp,
        "term_inversion":  term_inversion,
        "risk_reversal":   risk_reversal,
        "pc_volume":       pc_vol,
        "iv_rank_proxy":   iv_rank_proxy,
        "iv_rich":         bool(iv_rich) if iv_rich is not None else False,
        "iv_cheap":        bool(iv_cheap) if iv_cheap is not None else False,
        "front_expiry":    front_exp,
        "days_to_front":   days_front,
    }
    return long_signals, short_signals, raw
# ETF HOLDINGS  — v7 fast batch (FinanceDatabase + yfinance fallback)
# ─────────────────────────────────────────────────────────────────────────────
