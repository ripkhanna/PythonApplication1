"""Extracted runtime section from app_runtime.py lines 2375-3192.
Loaded by app_runtime with exec(..., globals()) to preserve the original single-file behavior.
"""

def detect_traps(open_, high_, low_, close_, vol_, atr, swing_high, swing_low):
    """
    Detect classic operator manipulation patterns.

    Returns a list of tuples:
        (severity, label, detail, long_dir, short_dir)
    where severity ∈ {"high","med","low"} and *_dir ∈ {-1, 0, +1}.
    long_dir = +1 means the pattern supports going long; -1 contradicts long.
    short_dir is the mirror for shorts. 0 means neutral / informational.
    """
    traps = []
    try:
        N = 20
        if len(close_) < N + 5:
            return traps

        body_size  = (close_ - open_).abs()
        day_range  = (high_ - low_).replace(0, np.nan)
        body_top   = close_.combine(open_, max)
        body_bot   = close_.combine(open_, min)
        upper_wick = high_ - body_top
        lower_wick = body_bot - low_
        close_pos  = (close_ - low_) / day_range
        vol_avg20  = vol_.rolling(20).mean()
        vol_rat    = vol_ / vol_avg20

        p_now   = float(close_.iloc[-1])
        atr_now = float(atr)
        sw_hi   = float(swing_high)
        sw_lo   = float(swing_low)

        # 1) BULL TRAP — find highest-vol breakout in last 7d, check if trapped
        best_k = None; best_vr = 0; best_hi = 0
        for k in range(-min(7, len(high_) - N - 1), 0):
            pre_window = high_.iloc[k - N : k]
            if len(pre_window) < N:
                continue
            pre_hi = float(pre_window.max())
            if float(high_.iloc[k]) > pre_hi * 1.001:
                vk = float(vol_rat.iloc[k]) if pd.notna(vol_rat.iloc[k]) else 1.0
                if vk > best_vr:
                    best_vr = vk
                    best_k  = k
                    best_hi = float(high_.iloc[k])
        if best_k is not None and best_vr >= 1.3 and p_now < best_hi * 0.99:
            traps.append(("high",
                "🚨 BULL TRAP — failed breakout",
                f"Broke above ${best_hi:.2f} on {best_vr:.1f}× volume {abs(best_k)} session(s) ago, "
                f"now back below at ${p_now:.2f}.",
                -1, +1))

        # 2) BEAR TRAP — strongest-vol breakdown in last 7d, check if trapped
        best_k = None; best_vr = 0; best_lo = 0
        for k in range(-min(7, len(low_) - N - 1), 0):
            pre_window = low_.iloc[k - N : k]
            if len(pre_window) < N:
                continue
            pre_lo = float(pre_window.min())
            if float(low_.iloc[k]) < pre_lo * 0.999:
                vk = float(vol_rat.iloc[k]) if pd.notna(vol_rat.iloc[k]) else 1.0
                if vk > best_vr:
                    best_vr = vk
                    best_k  = k
                    best_lo = float(low_.iloc[k])
        if best_k is not None and best_vr >= 1.3 and p_now > best_lo * 1.01:
            traps.append(("high",
                "🚨 BEAR TRAP — failed breakdown",
                f"Broke below ${best_lo:.2f} on {best_vr:.1f}× volume {abs(best_k)} session(s) ago, "
                f"now back above at ${p_now:.2f}.",
                +1, -1))

        # 3) STOP HUNT — wick beyond swing on volume
        for k in [-1, -2, -3]:
            if -k > len(close_):
                continue
            uw = float(upper_wick.iloc[k]) if pd.notna(upper_wick.iloc[k]) else 0
            lw = float(lower_wick.iloc[k]) if pd.notna(lower_wick.iloc[k]) else 0
            bd = float(body_size.iloc[k])  if pd.notna(body_size.iloc[k])  else 0
            vk = float(vol_rat.iloc[k])    if pd.notna(vol_rat.iloc[k])    else 1.0
            hi_k = float(high_.iloc[k]); lo_k = float(low_.iloc[k]); cl_k = float(close_.iloc[k])

            if uw > 2 * bd and uw > 0.6 * atr_now and vk >= 1.3 \
                    and hi_k > sw_hi * 0.998 and cl_k < sw_hi:
                traps.append(("med",
                    "🎯 UPSIDE stop hunt",
                    f"{abs(k)} session(s) ago: long upper wick (${uw:.2f}) on {vk:.1f}× volume "
                    f"probed swing high ${sw_hi:.2f} and rejected.",
                    -1, +1))
                break
            if lw > 2 * bd and lw > 0.6 * atr_now and vk >= 1.3 \
                    and lo_k < sw_lo * 1.002 and cl_k > sw_lo:
                traps.append(("med",
                    "🎯 DOWNSIDE stop hunt",
                    f"{abs(k)} session(s) ago: long lower wick (${lw:.2f}) on {vk:.1f}× volume "
                    f"probed swing low ${sw_lo:.2f} and rejected.",
                    +1, -1))
                break

        cp10 = float(close_pos.iloc[-10:].mean()) if pd.notna(close_pos.iloc[-10:].mean()) else 0.5
        vr10 = float(vol_rat.iloc[-10:].mean())   if pd.notna(vol_rat.iloc[-10:].mean())   else 1.0
        ret10 = float((close_.iloc[-1] - close_.iloc[-10]) / close_.iloc[-10])

        # 4) DISTRIBUTION at top
        high20 = float(high_.iloc[-20:].max())
        if p_now > high20 * 0.95 and cp10 < 0.45 and vr10 > 1.15 and abs(ret10) < 0.04:
            traps.append(("high",
                "📤 DISTRIBUTION at top",
                f"Within 5% of recent high but last 10d: avg close in lower {cp10*100:.0f}% "
                f"of daily range, volume {vr10:.1f}× avg, net move {ret10*100:+.1f}%.",
                -1, +1))

        # 5) ACCUMULATION at bottom
        low20 = float(low_.iloc[-20:].min())
        if p_now < low20 * 1.05 and cp10 > 0.55 and vr10 > 1.15 and abs(ret10) < 0.04:
            traps.append(("high",
                "📥 ACCUMULATION at bottom",
                f"Within 5% of recent low but last 10d: avg close in upper {cp10*100:.0f}% "
                f"of daily range, volume {vr10:.1f}× avg, net move {ret10*100:+.1f}%.",
                +1, -1))

        # 6) GAP & REVERSE
        for k in [-1, -2]:
            if -k > len(close_) - 1:
                continue
            op_k = float(open_.iloc[k]); cl_k = float(close_.iloc[k]); pc_k = float(close_.iloc[k-1])
            gap  = (op_k - pc_k) / pc_k if pc_k else 0
            vk   = float(vol_rat.iloc[k]) if pd.notna(vol_rat.iloc[k]) else 1.0
            if gap > 0.012 and cl_k < pc_k and vk >= 1.2:
                traps.append(("med",
                    "🪤 GAP-UP and reverse",
                    f"{abs(k)}d ago: gapped up {gap*100:+.1f}%, closed {(cl_k-pc_k)/pc_k*100:+.1f}% "
                    f"on {vk:.1f}× volume.",
                    -1, +1))
                break
            if gap < -0.012 and cl_k > pc_k and vk >= 1.2:
                traps.append(("med",
                    "🪤 GAP-DOWN and reverse",
                    f"{abs(k)}d ago: gapped down {gap*100:+.1f}%, closed {(cl_k-pc_k)/pc_k*100:+.1f}% "
                    f"on {vk:.1f}× volume.",
                    +1, -1))
                break

        # 7) CLIMAX / EXHAUSTION
        vr_today  = float(vol_rat.iloc[-1])  if pd.notna(vol_rat.iloc[-1])  else 1.0
        cp_today  = float(close_pos.iloc[-1]) if pd.notna(close_pos.iloc[-1]) else 0.5
        ret_today = float((close_.iloc[-1] - close_.iloc[-2]) / close_.iloc[-2])
        if vr_today >= 2.5 and ret_today > 0.02 and cp_today < 0.4:
            traps.append(("med",
                "🌋 BUY climax (exhaustion)",
                f"Today: +{ret_today*100:.1f}% on {vr_today:.1f}× volume, closed in lower "
                f"{cp_today*100:.0f}% of range.",
                -1, +1))
        elif vr_today >= 2.5 and ret_today < -0.02 and cp_today > 0.6:
            traps.append(("med",
                "🌋 SELL climax (capitulation)",
                f"Today: {ret_today*100:.1f}% on {vr_today:.1f}× volume, closed in upper "
                f"{cp_today*100:.0f}% of range.",
                +1, -1))

        # 8) CHURN
        range10_pct = float((close_.iloc[-10:].max() - close_.iloc[-10:].min()) / close_.iloc[-10])
        if range10_pct < 0.04 and vr10 > 1.30:
            traps.append(("low",
                "🔄 CHURN — sideways heavy volume",
                f"Last 10d: only {range10_pct*100:.1f}% range, volume {vr10:.1f}× avg.",
                0, 0))

    except Exception:
        pass
    return traps


def summarize_traps(traps):
    """Summarize a traps list into compact strings for display in tables."""
    if not traps:
        return {"count": 0, "high": 0, "med": 0, "low": 0,
                "patterns": "–", "bias": "–", "bias_score": 0}
    high = sum(1 for t in traps if t[0] == "high")
    med  = sum(1 for t in traps if t[0] == "med")
    low  = sum(1 for t in traps if t[0] == "low")
    # Direction bias: positive = bullish operator activity (accumulation/bear traps)
    # Negative = bearish operator activity (distribution/bull traps)
    sev_w = {"high": 3, "med": 2, "low": 1}
    bias_score = sum(sev_w[t[0]] * t[3] for t in traps)  # use long_dir
    if   bias_score >=  4: bias = "🟢 BULLISH"
    elif bias_score >=  1: bias = "🟢 mild bull"
    elif bias_score <= -4: bias = "🔴 BEARISH"
    elif bias_score <= -1: bias = "🔴 mild bear"
    else:                  bias = "⚪ NEUTRAL"
    # Compact pattern list — just labels, comma-joined
    patterns = " · ".join(t[1].split(" — ")[0].split(" (")[0] for t in traps)
    return {"count": len(traps), "high": high, "med": med, "low": low,
            "patterns": patterns, "bias": bias, "bias_score": bias_score}


# ─────────────────────────────────────────────────────────────────────────────
# MAIN SCANNER  — v5 signal logic + v7 batch OHLCV pre-fetch
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=4 * 3600, show_spinner=False)
def _download_daily_history_chunk_cached(chunk_tuple):
    """Cache stable one-year daily bars; live intraday bars are overlaid later."""
    chunk = list(chunk_tuple)
    out = {}
    err = ""
    try:
        raw = yf.download(
            chunk if len(chunk) > 1 else chunk[0],
            period="1y", interval="1d",
            progress=False, group_by="ticker", threads=True, auto_adjust=True,
        )
        if raw is None or getattr(raw, "empty", True):
            return out, "empty"
        for tkr in chunk:
            try:
                if isinstance(raw.columns, pd.MultiIndex):
                    lvl1 = raw.columns.get_level_values(1)
                    lvl0 = raw.columns.get_level_values(0)
                    if tkr in lvl1:
                        df_t = raw.xs(tkr, axis=1, level=1).copy()
                    elif tkr in lvl0:
                        df_t = raw[tkr].copy()
                    else:
                        continue
                elif len(chunk) == 1:
                    df_t = raw.copy()
                else:
                    continue
                df_t = _clean_scan_ohlcv(df_t)
                if len(df_t) >= 60:
                    out[tkr] = df_t
            except Exception:
                continue
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
    return out, err


@st.cache_data(ttl=3600)
def fetch_analysis(green_sectors, red_sectors, regime,
                   skip_earnings, top_n_sectors, strategy_mode="Balanced", live_sectors=None,
                   market_tickers=None, enable_options=True, data_freshness_bucket=None):
    sectors_data = live_sectors or {}
    sector_membership = {}
    for sec_name, sec_data in sectors_data.items():
        for t in sec_data.get("stocks", []):
            if t not in sector_membership:
                sector_membership[t] = sec_name

    # Use market-specific tickers if provided, else fall back to full BASE_TICKERS
    all_tickers = list(market_tickers) if market_tickers else list(BASE_TICKERS)
    for sec_name, sec_data in sectors_data.items():
        for t in sec_data.get("stocks", []):
            if t not in all_tickers:
                all_tickers.append(t)

    total = len(all_tickers)
    scan_debug = {
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "total_tickers": int(total),
        "strategy_mode": str(strategy_mode or "Balanced"),
        "batch_loaded": 0,
        "individual_loaded": 0,
        "skipped_history": 0,
        "skipped_liquidity": 0,
        "skipped_earnings": 0,
        "ticker_errors": 0,
        "ticker_error_samples": [],
        "batch_error": "",
        "intraday_loaded": 0,
        "intraday_error": "",
        "latest_intraday_bar": "",
        "data_freshness_bucket": str(data_freshness_bucket or ""),
        "empty_reason": "",
        # v15.7 speed: full universe is still checked, but the expensive
        # Bayesian signal engine is only run on tickers that pass a cheap
        # price/volume/structure pre-filter.
        "cheap_prefilter_skipped": 0,
        "signal_engine_ran": 0,
        # v15.8 speed: if the full batch download already completed, do not
        # make slow per-ticker Yahoo fallback calls for symbols missing from
        # the batch. Missing batch symbols are usually invalid/delisted/funds
        # and per-ticker fallback is the main reason the signal loop stays slow.
        "skipped_batch_miss_no_fallback": 0,
        "options_enriched": 0,
        "options_skipped_speed_cap": 0,
        "meta_prefetch_targets": 0,
        "fast_meta_candidates": 0,
        "stage2_fast_candidates": 0,
        "stage2_promoted_to_deep_scan": 0,
        # v15.6: per-phase timing breakdown
        "timing": {
            "spy_sector_fetch_s":   0.0,
            "intraday_fetch_s":     0.0,
            "batch_ohlcv_s":        0.0,
            "meta_prefetch_s":      0.0,
            "meta_prefilter_s":    0.0,
            "signal_loop_s":        0.0,
            "total_s":              0.0,
        },
    }
    import time as _time_mod
    _t_start = _time_mod.perf_counter()
    _t_phase = _t_start
    if total == 0:
        scan_debug["empty_reason"] = "No tickers were passed to fetch_analysis"
        try:
            st.session_state["last_scan_debug"] = scan_debug
            _record_app_warning("fetch_analysis", "No tickers were passed to fetch_analysis")
        except Exception:
            pass
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    green_set = set(green_sectors[:top_n_sectors])
    red_set   = set(red_sectors[:top_n_sectors])

    def sector_label(ticker):
        sec = sector_membership.get(ticker, "")
        if sec in green_set:  return f"🟢 {sec}"
        if sec in red_set:    return f"🔴 {sec}"
        return f"⚪ {sec}" if sec else "⚪ Mixed"

    long_results  = []
    short_results = []
    operator_results = []
    progress_bar  = st.progress(0)
    status_text   = st.empty()

    # v15.7 speed: Streamlit rerendering on every ticker is surprisingly
    # expensive for 1,000+ names. Update the UI only periodically while still
    # keeping the final progress accurate.
    def _scan_progress(i, msg=None, force=False):
        try:
            if force or i == 0 or (i + 1) == total or (i % 25 == 0):
                if msg:
                    status_text.text(msg)
                progress_bar.progress(min(1.0, max(0.0, (i + 1) / max(total, 1))))
        except Exception:
            pass

    # ── Monday filter ─────────────────────────────────────────────────────────
    is_monday = datetime.today().weekday() == 0

    # ── Pre-fetch SPY for relative strength ───────────────────────────────────
    spy_close_global = None
    try:
        import contextlib as _cl_spy, io as _io_spy
        with _cl_spy.redirect_stderr(_io_spy.StringIO()), _cl_spy.redirect_stdout(_io_spy.StringIO()):
            spy_raw = yf.download("SPY", period="1mo", interval="1d",
                                  progress=False, auto_adjust=True)
        if isinstance(spy_raw.columns, pd.MultiIndex):
            spy_raw.columns = spy_raw.columns.get_level_values(0)
        if spy_raw is not None and not spy_raw.empty and "Close" in spy_raw.columns:
            spy_close_global = spy_raw["Close"].squeeze().ffill()
    except Exception as e:
        try:
            _record_app_warning("spy_relative_strength_fetch", f"{type(e).__name__}: {e}")
        except Exception:
            pass

    # ── Pre-fetch sector ETF closes for sector leader signal ─────────────────
    sector_etf_closes = {}
    try:
        etf_list = list(SECTOR_ETFS.values())
        import contextlib as _cl_etf, io as _io_etf
        with _cl_etf.redirect_stderr(_io_etf.StringIO()), _cl_etf.redirect_stdout(_io_etf.StringIO()):
            etf_raw  = yf.download(etf_list, period="1mo", interval="1d",
                                   progress=False, auto_adjust=True, group_by="ticker")
        for etf in etf_list:
            try:
                c = _extract_closes(etf_raw, etf, len(etf_list))
                if len(c) >= 6:
                    sector_etf_closes[etf] = c
            except Exception:
                continue
    except Exception:
        pass

    # timing checkpoint: SPY + sector ETF fetch
    _t_now = _time_mod.perf_counter()
    scan_debug["timing"]["spy_sector_fetch_s"] = round(_t_now - _t_phase, 1)
    _t_phase = _t_now

    # ── Intraday overlay pre-fetch ────────────────────────────────────────────
    # The 6-month daily Yahoo bars can remain on yesterday's candle for a while
    # after SGX/NSE/US open.  Pull a lightweight 5-minute intraday snapshot and
    # overlay the latest day into the daily dataframe before signals are built.
    intraday_cache = {}

    def _extract_from_yf_batch(raw_obj, tkr, ticker_count):
        try:
            if raw_obj is None or getattr(raw_obj, "empty", True):
                return pd.DataFrame()
            if isinstance(raw_obj.columns, pd.MultiIndex):
                lvl0 = raw_obj.columns.get_level_values(0)
                lvl1 = raw_obj.columns.get_level_values(1)
                if tkr in lvl1:
                    return raw_obj.xs(tkr, axis=1, level=1).copy()
                if tkr in lvl0:
                    return raw_obj[tkr].copy()
                return pd.DataFrame()
            if ticker_count == 1:
                return raw_obj.copy()
        except Exception:
            return pd.DataFrame()
        return pd.DataFrame()

    def _overlay_intraday_daily(daily_df, intra_df):
        try:
            if daily_df is None or daily_df.empty or intra_df is None or intra_df.empty:
                return daily_df
            intra_df = _clean_scan_ohlcv(intra_df).dropna(how="all")
            if intra_df.empty or "Close" not in intra_df.columns:
                return daily_df
            intra_df = intra_df[intra_df["Close"].notna()]
            if intra_df.empty:
                return daily_df
            last_ts = pd.Timestamp(intra_df.index[-1])
            # Use the exchange-local date embedded in Yahoo's timestamp.
            last_date = last_ts.date()
            day_rows = intra_df[[pd.Timestamp(x).date() == last_date for x in intra_df.index]]
            if day_rows.empty:
                day_rows = intra_df.tail(1)
            row = {
                "Open": float(day_rows["Open"].dropna().iloc[0]) if "Open" in day_rows and not day_rows["Open"].dropna().empty else float(day_rows["Close"].iloc[0]),
                "High": float(day_rows["High"].max()) if "High" in day_rows else float(day_rows["Close"].max()),
                "Low": float(day_rows["Low"].min()) if "Low" in day_rows else float(day_rows["Close"].min()),
                "Close": float(day_rows["Close"].dropna().iloc[-1]),
                "Volume": float(day_rows["Volume"].fillna(0).sum()) if "Volume" in day_rows else 0.0,
            }
            out = daily_df.copy()
            out.index = pd.to_datetime(out.index)
            last_day_idx = None
            if len(out.index):
                matches = [idx for idx in out.index if pd.Timestamp(idx).date() == last_date]
                if matches:
                    last_day_idx = matches[-1]
            if last_day_idx is not None:
                for c, v in row.items():
                    out.loc[last_day_idx, c] = v
                out.loc[last_day_idx, "Last Bar"] = str(last_ts)
            else:
                new_idx = pd.Timestamp(last_date)
                out.loc[new_idx, ["Open", "High", "Low", "Close", "Volume"]] = [row["Open"], row["High"], row["Low"], row["Close"], row["Volume"]]
                out.loc[new_idx, "Last Bar"] = str(last_ts)
                out = out.sort_index()
            return out
        except Exception:
            return daily_df

    # ── Recent earners set (Nasdaq calendar, last 3 days) ─────────────────
    # post_earnings_gap later checks this to bypass gap_chase_risk / not_limit_up.
    recent_earners_set: set = set()
    try:
        from swing_trader_app.core_runtime.event_core import _nasdaq_earnings_for_date
        _rne_today = pd.Timestamp.now().date()
        for _rne_back in range(4):
            _rne_d = _rne_today - pd.Timedelta(days=_rne_back)
            for _rne_r in _nasdaq_earnings_for_date(_rne_d.strftime("%Y-%m-%d")):
                _rne_sym = str((_rne_r or {}).get("symbol") or "").strip().upper()
                if _rne_sym:
                    recent_earners_set.add(_rne_sym)
    except Exception:
        pass

    # Skip intraday fetch outside market hours — saves ~30s when market is closed
    _market_is_open = False
    try:
        _market_is_open = _is_market_live_now(
            st.session_state.get("market_selector", "🇺🇸 US"))
    except Exception:
        pass

    if _market_is_open:
        status_text.text(f"📥 Fetching latest 5-minute bars for {total} stocks...")
        try:
            _intraday_tickers = list(all_tickers)
            if total >= 700:
                _live_intraday_count = min(
                    total, max(50, int(st.session_state.get("ui_max_live_universe", 150)))
                )
                _forced_intraday = (
                    list(globals().get("always_include_tickers", []) or [])
                    + list(globals().get("extra_tickers", []) or [])
                )
                _intraday_tickers = list(dict.fromkeys(
                    list(all_tickers[:_live_intraday_count]) + _forced_intraday
                ))
            raw_intraday = yf.download(
                _intraday_tickers, period="1d", interval="5m",
                progress=False, group_by="ticker", threads=True, auto_adjust=True,
                prepost=True,
            )
            latest_bars = []
            for tkr in _intraday_tickers:
                try:
                    idf = _extract_from_yf_batch(raw_intraday, tkr, len(_intraday_tickers))
                    idf = _clean_scan_ohlcv(idf).dropna(how="all") if not idf.empty else pd.DataFrame()
                    if len(idf) >= 1 and "Close" in idf.columns and idf["Close"].notna().any():
                        intraday_cache[tkr] = idf
                        latest_bars.append(str(pd.Timestamp(idf.index[-1])))
                except Exception:
                    continue
            scan_debug["intraday_requested"] = int(len(_intraday_tickers))
            scan_debug["intraday_loaded"] = int(len(intraday_cache))
            scan_debug["latest_intraday_bar"] = max(latest_bars) if latest_bars else ""
        except Exception as e:
            scan_debug["intraday_error"] = f"{type(e).__name__}: {e}"
            try:
                _record_app_warning("intraday_yfinance_download",
                                    scan_debug["intraday_error"],
                                    extra={"total_tickers": total})
            except Exception:
                pass

    # timing checkpoint: intraday fetch (only runs when market is open)
    _t_now = _time_mod.perf_counter()
    scan_debug["timing"]["intraday_fetch_s"] = round(_t_now - _t_phase, 1)
    _t_phase = _t_now

    # ── Batch OHLCV pre-fetch ─────────────────────────────────────────────────
    status_text.text(f"📥 Batch downloading {total} stocks...")
    batch_cache = {}

    # v15.9 speed: one giant yf.download(all 1200+) can randomly take 70s+ or
    # stall behind a few bad symbols.  Download fixed-size chunks concurrently;
    # each chunk is parsed independently so one slow/failed chunk does not block
    # the whole universe.  This still scans the full universe — it only changes
    # the transport layer.
    def _chunks(seq, n):
        for _i in range(0, len(seq), n):
            yield list(seq[_i:_i + n])

    def _download_daily_chunk(chunk, chunk_no=0):
        out, err = _download_daily_history_chunk_cached(tuple(chunk))
        out = {tkr: df_t.copy() for tkr, df_t in out.items()}
        for tkr, intra_df in intraday_cache.items():
            if tkr in out:
                out[tkr] = _overlay_intraday_daily(out[tkr], intra_df)
        return out, err

    try:
        # Tune for Yahoo reliability: enough parallelism to avoid a 70s single
        # batch, but not so many connections that Yahoo starts throttling.
        if total >= 900:
            _chunk_size, _dl_workers = 225, 4
        elif total >= 700:
            _chunk_size, _dl_workers = 225, 4
        elif total >= 400:
            _chunk_size, _dl_workers = 225, 3
        else:
            _chunk_size, _dl_workers = max(total, 1), 1

        if total >= 400:
            # Stable buckets preserve daily-history cache hits even when a few
            # live mover symbols enter or leave the universe between refreshes.
            import zlib as _zlib
            _stable_buckets = [[] for _ in range(4)]
            for _ticker in sorted(set(all_tickers)):
                _bucket_idx = _zlib.crc32(_ticker.encode("utf-8")) % len(_stable_buckets)
                _stable_buckets[_bucket_idx].append(_ticker)
            _ticker_chunks = [bucket for bucket in _stable_buckets if bucket]
            scan_debug["batch_stable_buckets"] = int(len(_ticker_chunks))
        else:
            _ticker_chunks = list(_chunks(all_tickers, _chunk_size))
            scan_debug["batch_stable_buckets"] = 0
        scan_debug["batch_chunk_size"] = int(_chunk_size)
        scan_debug["batch_chunk_workers"] = int(_dl_workers)
        scan_debug["batch_chunks"] = int(len(_ticker_chunks))
        scan_debug["batch_chunk_errors"] = []

        if len(_ticker_chunks) <= 1:
            _out, _err = _download_daily_chunk(_ticker_chunks[0] if _ticker_chunks else [], 1)
            batch_cache.update(_out)
            if _err:
                scan_debug["batch_chunk_errors"].append(f"chunk 1: {_err}")
        else:
            from concurrent.futures import ThreadPoolExecutor as _DLThreadPoolExecutor, as_completed as _dl_as_completed
            status_text.text(
                f"📥 Batch downloading {total} stocks in {len(_ticker_chunks)} chunks "
                f"({_dl_workers} workers)..."
            )
            with _DLThreadPoolExecutor(max_workers=_dl_workers) as _pool:
                _futs = {
                    _pool.submit(_download_daily_chunk, ch, idx + 1): idx + 1
                    for idx, ch in enumerate(_ticker_chunks)
                }
                _done_chunks = 0
                for _fut in _dl_as_completed(_futs):
                    _done_chunks += 1
                    _idx = _futs[_fut]
                    try:
                        _out, _err = _fut.result(timeout=90)
                        batch_cache.update(_out)
                        if _err:
                            scan_debug["batch_chunk_errors"].append(f"chunk {_idx}: {_err}")
                    except Exception as _e:
                        scan_debug["batch_chunk_errors"].append(f"chunk {_idx}: {type(_e).__name__}: {_e}")
                    if _done_chunks == 1 or _done_chunks == len(_ticker_chunks) or _done_chunks % 2 == 0:
                        status_text.text(
                            f"📥 Loaded {len(batch_cache)}/{total} stocks "
                            f"({ _done_chunks }/{len(_ticker_chunks)} chunks)..."
                        )

        scan_debug["batch_loaded"] = int(len(batch_cache))
        if scan_debug.get("batch_chunk_errors"):
            scan_debug["batch_error"] = " | ".join(scan_debug["batch_chunk_errors"][:5])
        status_text.text(f"✅ {len(batch_cache)}/{total} stocks loaded")
    except Exception as e:
        scan_debug["batch_error"] = f"{type(e).__name__}: {e}"
        try:
            _record_app_error("batch_yfinance_download", e, extra={"total_tickers": total})
        except Exception:
            pass
        status_text.text(f"Batch failed ({e}), fetching individually...")

    # timing checkpoint: batch OHLCV download
    _t_now = _time_mod.perf_counter()
    scan_debug["timing"]["batch_ohlcv_s"] = round(_t_now - _t_phase, 1)
    _t_phase = _t_now

    # ── Regime + mode thresholds ─────────────────────────────────────────────
    # v13.52: The old scanner was too strict for live markets: a stock needed
    # near-perfect Bayesian probability + operator score + rel strength before
    # it became actionable. That caused many good swing setups to appear only
    # as WATCH or not at all. Keep Strict mode available, but default Balanced
    # is designed for real trading workflow: BUY = actionable setup with trend,
    # volume/operator support, above MA60, and no major trap; WATCH = forming.
    # IMPORTANT: strategy_mode is part of the @st.cache_data key.
    # Do not read the strategy only from st.session_state here; otherwise
    # Strict/Balanced/Discovery/Support/PM/High Volume can reuse the same
    # cached result and appear identical until cache expires.
    swing_mode = str(strategy_mode or "Balanced").upper()
    if swing_mode == "STRICT":
        min_score_strong_long  = 7 if regime == "BULL" else 8
        min_prob_strong_long   = 0.80 if regime == "BULL" else 0.84
        min_score_strong_short = 6 if regime in ("BEAR", "CAUTION") else 7
        min_prob_strong_short  = 0.76 if regime in ("BEAR", "CAUTION") else 0.80
    elif swing_mode == "DISCOVERY":
        min_score_strong_long  = 4 if regime == "BULL" else 5
        min_prob_strong_long   = 0.62 if regime == "BULL" else 0.68
        min_score_strong_short = 4 if regime in ("BEAR", "CAUTION") else 5
        min_prob_strong_short  = 0.60 if regime in ("BEAR", "CAUTION") else 0.64
    elif swing_mode in ("SUPPORT ENTRY", "PREMARKET MOMENTUM", "HIGH VOLUME"):
        min_score_strong_long  = 5 if regime == "BULL" else 6
        min_prob_strong_long   = 0.65 if regime == "BULL" else 0.70
        min_score_strong_short = 4 if regime in ("BEAR", "CAUTION") else 5
        min_prob_strong_short  = 0.62 if regime in ("BEAR", "CAUTION") else 0.66
    elif swing_mode == "HIGH CONVICTION":
        # Category gates do the filtering — lower probability bar than Balanced.
        min_score_strong_long  = 4 if regime == "BULL" else 5
        min_prob_strong_long   = 0.62 if regime == "BULL" else 0.66
        min_score_strong_short = 4 if regime in ("BEAR", "CAUTION") else 5
        min_prob_strong_short  = 0.60 if regime in ("BEAR", "CAUTION") else 0.64
    else:  # Balanced
        min_score_strong_long  = 5 if regime == "BULL" else 6
        min_prob_strong_long   = 0.68 if regime == "BULL" else 0.72
        min_score_strong_short = 4 if regime in ("BEAR", "CAUTION") else 5
        min_prob_strong_short  = 0.64 if regime in ("BEAR", "CAUTION") else 0.68

    # ─────────────────────────────────────────────────────────────────────────
    _stage2_scan_requested = str(st.session_state.get("ui_swing_mode", "")).upper() == "STAGE 2 BREAKOUT"

    def _fast_stage2_prefilter_ok(_df):
        """Cheap full-universe Stage 2 base check before the deep signal engine."""
        try:
            if _df is None or _df.empty or len(_df) < 65:
                return False
            _close = _df["Close"].squeeze().ffill()
            _high = _df["High"].squeeze().ffill()
            _low = _df["Low"].squeeze().ffill()
            _vol = _df["Volume"].squeeze().ffill()
            _p = float(_close.iloc[-1])
            if _p <= 0 or float(_vol.tail(20).mean()) <= 0:
                return False

            _ma50 = float(_close.tail(50).mean())
            _ma200 = float(_close.tail(200).mean()) if len(_close) >= 200 else float(_close.tail(60).mean())
            _trend = _p > _ma50 and _ma50 >= _ma200 * 0.98
            if not _trend:
                return False

            _best = None
            for _window in (20, 30, 40, 60):
                if len(_close) < _window + 1:
                    continue
                _base_hi = float(_high.iloc[-(_window + 1):-1].max())
                _base_lo = float(_low.iloc[-(_window + 1):-1].min())
                _base_range = ((_base_hi / max(_base_lo, 0.01)) - 1.0) * 100.0
                if _base_range <= 22.0 and (_best is None or _base_range < _best[0]):
                    _best = (_base_range, _base_hi, _base_lo)
            if _best is None:
                return False

            _base_range, _pivot, _base_low = _best
            _pivot_dist = ((_p / max(_pivot, 0.01)) - 1.0) * 100.0
            _inner_hi = float(_high.iloc[-11:-1].max())
            _inner_lo = float(_low.iloc[-11:-1].min())
            _inner_range = ((_inner_hi / max(_inner_lo, 0.01)) - 1.0) * 100.0
            _contraction = _inner_range / max(_base_range, 0.01)
            _quiet_vol = float(_vol.iloc[-11:-1].mean())
            _prior_vol = float(_vol.iloc[-31:-11].mean())
            _vdu = _quiet_vol / max(_prior_vol, 1.0)
            _today = ((_p / max(float(_close.iloc[-2]), 0.01)) - 1.0) * 100.0
            _five = ((_p / max(float(_close.iloc[-6]), 0.01)) - 1.0) * 100.0
            _twenty = ((_p / max(float(_close.iloc[-21]), 0.01)) - 1.0) * 100.0
            return bool(
                _p >= _base_low * 1.02
                and -10.0 <= _pivot_dist <= -0.20
                and _contraction <= 0.95
                and _vdu <= 1.35
                and -4.0 <= _today <= 3.0
                and -8.0 <= _five <= 7.0
                and -14.0 <= _twenty <= 14.0
            )
        except Exception:
            return False

    _stage2_fast_candidates = set()
    if _stage2_scan_requested:
        _stage2_fast_candidates = {
            _ticker for _ticker, _df in batch_cache.items()
            if _fast_stage2_prefilter_ok(_df)
        }
    scan_debug["stage2_fast_candidates"] = int(len(_stage2_fast_candidates))

    # v16 speed: compute a cheap candidate set BEFORE Yahoo metadata calls.
    #
    # The batch OHLCV download is comparatively fast. The slowest step on broad
    # scans is usually yf.Ticker(...).info/calendar for every symbol. Most
    # symbols later fail the cheap price/volume/structure gate, so fetching rich
    # metadata for all of them is wasted time. This prefilter mirrors the cheap
    # gate used in the signal loop and limits metadata fetches to plausible
    # candidates, while still scanning price/volume for the whole universe.
    # ─────────────────────────────────────────────────────────────────────────
    def _fast_meta_prefilter_ok(_ticker, _df):
        try:
            if _df is None or _df.empty or len(_df) < 60:
                return False
            _close = _df["Close"].squeeze().ffill()
            _high  = _df["High"].squeeze().ffill()
            _low   = _df["Low"].squeeze().ffill()
            _vol   = _df["Volume"].squeeze().ffill()
            if len(_close) < 60 or _close.dropna().empty:
                return False
            _vol_avg_s = float(_vol.rolling(20).mean().iloc[-1])
            _p_chk     = float(_close.iloc[-1])
            if _p_chk <= 0 or _vol_avg_s <= 0:
                return False
            try:
                _prev_close = _close.shift(1)
                _tr_fast = pd.concat([
                    (_high - _low).abs(),
                    (_high - _prev_close).abs(),
                    (_low - _prev_close).abs(),
                ], axis=1).max(axis=1)
                _atr_pct = float(_tr_fast.tail(14).mean()) / _p_chk * 100
            except Exception:
                _atr_pct = float((_high.tail(14).max() - _low.tail(14).min()) / _p_chk * 100 / 3)

            _tu = str(_ticker).upper()
            if _tu.endswith(".SI"):
                _min_turnover = 120_000; _min_atr_pct = 0.30
            elif _tu.endswith(".NS"):
                _min_turnover = 250_000; _min_atr_pct = 0.50
            else:
                _min_turnover = 500_000; _min_atr_pct = 0.80

            _ui_strategy_mode = str(st.session_state.get("ui_swing_mode", swing_mode)).upper()
            if swing_mode == "HIGH VOLUME":
                _liquid_ok = True
            elif swing_mode in ("SUPPORT ENTRY", "PREMARKET MOMENTUM") or _ui_strategy_mode == "STAGE 2 BREAKOUT":
                _liquid_ok = (_p_chk * _vol_avg_s >= max(_min_turnover * 0.25, 50_000)
                              and _atr_pct >= max(_min_atr_pct * 0.35, 0.15))
            else:
                _liquid_ok = (_p_chk * _vol_avg_s >= _min_turnover and _atr_pct >= _min_atr_pct)
            if not _liquid_ok:
                return False

            _c_now = float(_close.iloc[-1])
            _c_prev = float(_close.iloc[-2]) if len(_close) >= 2 and float(_close.iloc[-2]) != 0 else _c_now
            _today_pct_fast = (_c_now / _c_prev - 1.0) * 100 if _c_prev else 0.0
            _ma20_fast = float(_close.tail(20).mean()) if len(_close) >= 20 else _c_now
            _ma60_fast = float(_close.tail(60).mean()) if len(_close) >= 60 else _ma20_fast
            _hi20_fast = float(_high.tail(20).max()) if len(_high) >= 20 else _c_now
            _lo20_fast = float(_low.tail(20).min()) if len(_low) >= 20 else _c_now
            _vol20_fast = float(_vol.tail(21).iloc[:-1].mean()) if len(_vol) >= 21 else _vol_avg_s
            _vr_fast = float(_vol.iloc[-1]) / _vol20_fast if _vol20_fast > 0 else 0.0
            _range_fast = max(float(_high.iloc[-1]) - float(_low.iloc[-1]), 0.0)
            _close_pos_fast = ((_c_now - float(_low.iloc[-1])) / _range_fast) if _range_fast > 0 else 0.5
            _near_support_fast = (
                (_ma20_fast > 0 and abs(_c_now / _ma20_fast - 1.0) <= 0.045) or
                (_ma60_fast > 0 and abs(_c_now / _ma60_fast - 1.0) <= 0.055) or
                (_lo20_fast > 0 and _c_now <= _lo20_fast * 1.08)
            )
            _breakout_fast = (_hi20_fast > 0 and _c_now >= _hi20_fast * 0.985)
            _breakdown_fast = (_lo20_fast > 0 and _c_now <= _lo20_fast * 1.015)
            _trend_fast = (_c_now >= _ma20_fast * 0.99 and _ma20_fast >= _ma60_fast * 0.985)
            _long_candidate_fast = (
                _today_pct_fast >= 1.2 or _vr_fast >= 1.25 or _breakout_fast or
                _trend_fast or _near_support_fast
            )
            _short_candidate_fast = (
                _today_pct_fast <= -1.2 or _breakdown_fast or
                (_vr_fast >= 1.35 and _close_pos_fast <= 0.40) or
                (_c_now < _ma20_fast * 0.985 and _ma20_fast < _ma60_fast)
            )
            if abs(_today_pct_fast) >= 5.0 and _vr_fast >= 1.5:
                return True
            if swing_mode == "HIGH VOLUME":
                return (_vr_fast >= 1.05 or abs(_today_pct_fast) >= 0.8 or _vol_avg_s > 0)
            if swing_mode == "SUPPORT ENTRY":
                return (_near_support_fast or _vr_fast >= 1.10 or abs(_today_pct_fast) >= 0.8)
            if swing_mode == "PREMARKET MOMENTUM":
                return (_today_pct_fast >= 0.2 or _vr_fast >= 1.10 or _breakout_fast or _trend_fast)
            return bool(_long_candidate_fast or _short_candidate_fast)
        except Exception:
            # Fail open for metadata only; the main loop still has its own gate.
            return True

    _meta_targets = list(all_tickers)
    try:
        if total >= 300 and not skip_earnings:
            _candidate_set = {t for t, _df in batch_cache.items() if _fast_meta_prefilter_ok(t, _df)}
            # Always include forced tickers typed by the user.
            try:
                _forced = set(always_include_tickers + extra_tickers)
            except Exception:
                _forced = set()
            _candidate_set |= {t for t in all_tickers if t in _forced}
            _meta_targets = [t for t in all_tickers if t in _candidate_set]
            scan_debug["fast_meta_candidates"] = int(len(_candidate_set))
        else:
            scan_debug["fast_meta_candidates"] = int(len(all_tickers))
    except Exception:
        _meta_targets = list(all_tickers)
        scan_debug["fast_meta_candidates"] = int(len(all_tickers))

    # Limit rich metadata on very broad scans. Missing metadata fields are shown
    # as '–' but price/technical signals still run normally.
    if _stage2_scan_requested:
        # Stage 2 needs earnings and sector context for quiet bases that the
        # normal activity-ranked metadata cap would otherwise omit.
        _stage2_meta_first = [t for t in all_tickers if t in _stage2_fast_candidates]
        _meta_targets = list(dict.fromkeys(_stage2_meta_first + _meta_targets))
    if total >= 700 and len(_meta_targets) > 75 and not skip_earnings:
        _meta_cap = max(75, min(150, len(_stage2_fast_candidates))) if _stage2_scan_requested else 75
        _meta_targets = _meta_targets[:_meta_cap]

    scan_debug["meta_prefetch_targets"] = int(len(_meta_targets))
    # EPS revision history is useful for Stage 2 confirmation, but it requires
    # an extra Yahoo fundamentals request. Keep it optional, cached, and capped
    # so selecting other strategies does not slow broad US scans.
    _stage2_eps_requested = _stage2_scan_requested
    _stage2_eps_targets = set(_meta_targets[:30]) if _stage2_eps_requested else set()
    scan_debug["stage2_eps_targets"] = int(len(_stage2_eps_targets))
    _t_now = _time_mod.perf_counter()
    scan_debug["timing"]["meta_prefilter_s"] = round(_t_now - _t_phase, 1)
    _t_phase = _t_now

    # ─────────────────────────────────────────────────────────────────────────
    # SPEED FIX: parallel pre-fetch of .calendar / .info / .fast_info
    #
    # Uses a SHARED requests.Session so every worker thread uses the same
    # Yahoo crumb cookie. Without a shared session, parallel Ticker() calls
    # each try to refresh the crumb simultaneously → HTTP 401 "Invalid Crumb".
    #
    # Worker count is kept at 5 (not 25+) for the same reason: too many
    # simultaneous Yahoo connections trigger rate-limiting and crumb errors.
    # 5 workers still cuts 15 min of serial fetches down to ~2-3 min.
    # ─────────────────────────────────────────────────────────────────────────
    from concurrent.futures import ThreadPoolExecutor, as_completed as _as_completed
    import threading as _threading
    import time as _time
    try:
        import requests as _requests_mod
        _shared_session = _requests_mod.Session()
        _shared_session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })
    except Exception:
        _shared_session = None

    _meta_cache = {}          # ticker → {cal_days, float_shares, short_pct, pe, pm_chg, ...}
    _meta_lock  = _threading.Lock()
    _in_batch   = set(batch_cache.keys())   # only fetch meta for tickers with OHLCV
    _WORKERS    = 5           # keep low — Yahoo crumb invalidates under heavy parallelism

    _stable_meta_cache = globals().setdefault("_analysis_stable_meta_cache_v1", {})
    _stable_meta_ttl_s = 4 * 3600
    _stable_meta_fields = (
        "cal_days", "float_shares", "short_pct", "pe", "cash_ratio",
        "analyst_rec", "industry", "sector_detail", "quote_type",
        "eps_revision_60d", "eps_revision_available",
    )

    def _fetch_one_meta(t):
        result = {
            "cal_days": None, "float_shares": None,
            "short_pct": None, "pe": None,
            "pm_chg": 0.0, "pm_price": 0.0, "pm_ok": False,
            "cash_ratio":    None,
            "analyst_rec":   None,
            "eps_revision_60d": None,
            "eps_revision_available": False,
            "industry":      "",
            "sector_detail": "",
            "quote_type":    "",   # "ETF" | "EQUITY" | ""
        }
        _stable_ready = False
        try:
            _cached_stable = _stable_meta_cache.get(t, {})
            if _cached_stable and (_time.time() - float(_cached_stable.get("saved_at", 0))) < _stable_meta_ttl_s:
                result.update(_cached_stable.get("data", {}))
                _stable_ready = True
        except Exception:
            _stable_ready = False

        for _attempt in range(2):   # retry once on 401
            try:
                tkr_obj = (yf.Ticker(t, session=_shared_session)
                           if _shared_session else yf.Ticker(t))
                _eps_ready = (t not in _stage2_eps_targets) or bool(result.get("eps_revision_available"))
                if _stable_ready and _market_is_open and _eps_ready:
                    break

                # ── calendar ────────────────────────────────────────────
                try:
                    _cal = tkr_obj.calendar
                    if _cal is not None and not (hasattr(_cal, "empty") and _cal.empty):
                        _ed = (_cal.loc["Earnings Date"].iloc[0]
                               if "Earnings Date" in _cal.index else _cal.iloc[0, 0])
                        if not pd.isnull(_ed):
                            result["cal_days"] = (
                                pd.Timestamp(_ed).date() - datetime.today().date()
                            ).days
                except Exception:
                    pass

                # ── info + fast_info (only if OHLCV loaded) ─────────────
                if t in _in_batch:
                    try:
                        _inf = tkr_obj.info or {}
                        result["float_shares"] = _inf.get("floatShares")
                        result["short_pct"]    = _inf.get("shortPercentOfFloat")
                        result["pe"]           = _inf.get("trailingPE")
                        # v14.1: fundamental floor + analyst consensus
                        _cash  = _inf.get("totalCash") or _inf.get("cash")
                        _mcap  = _inf.get("marketCap")
                        if _cash and _mcap and float(_mcap) > 0:
                            result["cash_ratio"] = round(float(_cash) / float(_mcap), 3)
                        _rec = _inf.get("recommendationMean")
                        if _rec is not None:
                            result["analyst_rec"] = round(float(_rec), 2)
                        result["industry"]      = str(_inf.get("industry", "") or "")
                        result["sector_detail"] = str(_inf.get("sector",   "") or "")
                        result["quote_type"]    = str(_inf.get("quoteType", "") or "")
                    except Exception:
                        pass
                    if t in _stage2_eps_targets and not result.get("eps_revision_available"):
                        try:
                            _eps_getter = getattr(tkr_obj, "get_eps_trend", None)
                            _eps_trend = _eps_getter() if callable(_eps_getter) else getattr(tkr_obj, "eps_trend", None)
                            if isinstance(_eps_trend, pd.DataFrame) and not _eps_trend.empty:
                                _eps_rows = ["0q", "+1q", "0y", "+1y"]
                                for _eps_row in _eps_rows:
                                    if _eps_row not in _eps_trend.index:
                                        continue
                                    _cur = pd.to_numeric(_eps_trend.loc[_eps_row].get("current"), errors="coerce")
                                    _old = pd.to_numeric(_eps_trend.loc[_eps_row].get("60daysAgo"), errors="coerce")
                                    if pd.notna(_cur) and pd.notna(_old) and abs(float(_old)) >= 0.01:
                                        result["eps_revision_60d"] = round(
                                            (float(_cur) - float(_old)) / abs(float(_old)) * 100.0, 1
                                        )
                                        result["eps_revision_available"] = True
                                        break
                        except Exception:
                            pass
                    if not _stable_ready or (
                        t in _stage2_eps_targets and result.get("eps_revision_available")
                    ):
                        with _meta_lock:
                            _stable_meta_cache[t] = {
                                "saved_at": _time.time(),
                                "data": {field: result.get(field) for field in _stable_meta_fields},
                            }
                    try:
                        _fi = getattr(tkr_obj, "fast_info", None)
                        if _fi is not None:
                            _pm_p  = getattr(_fi, "pre_market_price", None)
                            _pm_pc = getattr(_fi, "previous_close",   None)
                            if _pm_p is None and hasattr(_fi, "get"):
                                _pm_p  = (_fi.get("preMarketPrice")
                                          or _fi.get("pre_market_price"))
                                _pm_pc = (_fi.get("regularMarketPreviousClose")
                                          or _fi.get("previous_close"))
                            if _pm_p and _pm_pc and float(_pm_pc) > 0:
                                result["pm_price"] = float(_pm_p)
                                result["pm_chg"]   = round(
                                    (float(_pm_p) / float(_pm_pc) - 1) * 100, 2)
                                result["pm_ok"]    = True
                    except Exception:
                        pass
                break  # success — don't retry

            except Exception as _e:
                _emsg = str(_e).lower()
                if "401" in _emsg or "crumb" in _emsg or "unauthorized" in _emsg:
                    # Crumb expired — wait briefly and retry with a fresh Ticker
                    _time.sleep(0.5 + _attempt * 0.5)
                    _shared_session = None   # drop session so next attempt re-initialises
                    continue
                break  # non-auth error — don't retry

        return t, result

    status_text.text(
        f"⚡ Pre-fetching meta for {len(_meta_targets)}/{len(all_tickers)} tickers "
        f"({_WORKERS} parallel workers)…"
    )
    try:
        with ThreadPoolExecutor(max_workers=_WORKERS) as _pool:
            _futs = {_pool.submit(_fetch_one_meta, t): t for t in _meta_targets}
            _done = 0
            for _fut in _as_completed(_futs):
                _done += 1
                if _done % 50 == 0:
                    status_text.text(
                        f"⚡ Pre-fetching meta {_done}/{len(_meta_targets)}…"
                    )
                try:
                    _t, _res = _fut.result(timeout=15)
                    with _meta_lock:
                        _meta_cache[_t] = _res
                except Exception:
                    pass
    except Exception:
        # ThreadPool failed entirely — _meta_cache stays empty.
        # The main loop will still run; it just won't have float/short/PE/PM data.
        pass
    status_text.text("✅ Meta ready — computing signals…")

    # timing checkpoint: meta prefetch
    _t_now = _time_mod.perf_counter()
    scan_debug["timing"]["meta_prefetch_s"] = round(_t_now - _t_phase, 1)
    _t_phase = _t_now

    # Screen every symbol cheaply, then reserve expensive deep analysis for
    # the strongest dynamic candidates on very broad live scans.
    _deep_signal_targets = set(all_tickers)
    if total >= 700:
        try:
            _live_priority_count = min(
                total, max(0, int(st.session_state.get("ui_max_live_universe", 150)))
            )
            _forced_signal_targets = set(
                list(globals().get("always_include_tickers", []) or [])
                + list(globals().get("extra_tickers", []) or [])
            )
            _deep_ranked = []
            _must_deep_scan = (
                set(all_tickers[:_live_priority_count])
                | _forced_signal_targets
                | _stage2_fast_candidates
            )
            for _rank_ticker in all_tickers:
                _rank_df = batch_cache.get(_rank_ticker)
                if _rank_df is None or _rank_df.empty or len(_rank_df) < 60:
                    continue
                _rank_close = _rank_df["Close"].squeeze().ffill()
                _rank_high = _rank_df["High"].squeeze().ffill()
                _rank_low = _rank_df["Low"].squeeze().ffill()
                _rank_vol = _rank_df["Volume"].squeeze().ffill()
                _rank_p = float(_rank_close.iloc[-1])
                _rank_prev = float(_rank_close.iloc[-2]) if float(_rank_close.iloc[-2]) else _rank_p
                _rank_today = (_rank_p / _rank_prev - 1.0) * 100 if _rank_prev else 0.0
                _rank_vavg = float(_rank_vol.tail(21).iloc[:-1].mean())
                _rank_vr = float(_rank_vol.iloc[-1]) / _rank_vavg if _rank_vavg > 0 else 0.0
                _rank_ma20 = float(_rank_close.tail(20).mean())
                _rank_ma60 = float(_rank_close.tail(60).mean())
                _rank_hi20 = float(_rank_high.tail(20).max())
                _rank_lo20 = float(_rank_low.tail(20).min())
                _rank_breakout = _rank_hi20 > 0 and _rank_p >= _rank_hi20 * 0.985
                _rank_breakdown = _rank_lo20 > 0 and _rank_p <= _rank_lo20 * 1.015
                _rank_support = (
                    (_rank_ma20 > 0 and abs(_rank_p / _rank_ma20 - 1.0) <= 0.025)
                    or (_rank_ma60 > 0 and abs(_rank_p / _rank_ma60 - 1.0) <= 0.035)
                )
                _rank_trend = _rank_p >= _rank_ma20 and _rank_ma20 >= _rank_ma60
                _rank_score = (
                    abs(_rank_today) * 12.0
                    + max(0.0, _rank_vr - 0.8) * 18.0
                    + (18.0 if _rank_breakout or _rank_breakdown else 0.0)
                    + (6.0 if _rank_support else 0.0)
                    + (3.0 if _rank_trend else 0.0)
                )
                if abs(_rank_today) >= 5.0 or _rank_vr >= 2.0:
                    _must_deep_scan.add(_rank_ticker)
                _deep_ranked.append((_rank_score, _rank_ticker))

            _deep_scan_cap = min(
                total, max(_live_priority_count + 50, int(round(total * 0.25)))
            )
            _deep_ranked.sort(reverse=True)
            _deep_signal_targets = set(_must_deep_scan)
            _deep_signal_targets.update(t for _, t in _deep_ranked[:_deep_scan_cap])
            scan_debug["deep_signal_cap"] = int(_deep_scan_cap)
            scan_debug["deep_signal_targets"] = int(len(_deep_signal_targets))
            scan_debug["stage2_promoted_to_deep_scan"] = int(
                len(_stage2_fast_candidates & _deep_signal_targets)
            )
            scan_debug["deep_signal_full_universe_screened"] = int(total)
        except Exception as _deep_rank_e:
            _deep_signal_targets = set(all_tickers)
            scan_debug["deep_signal_rank_error"] = f"{type(_deep_rank_e).__name__}: {_deep_rank_e}"
            scan_debug["stage2_promoted_to_deep_scan"] = int(len(_stage2_fast_candidates))
    else:
        scan_debug["deep_signal_cap"] = int(total)
        scan_debug["deep_signal_targets"] = int(total)
        scan_debug["deep_signal_full_universe_screened"] = int(total)
        scan_debug["stage2_promoted_to_deep_scan"] = int(len(_stage2_fast_candidates))

    # v15.8 speed: cap expensive option-chain HTTP calls during broad
    # master scans. Price/volume signals still run for the whole universe;
    # options are only additive and should not dominate scan time.
    _option_enrich_count = 0
    _max_option_enrich = 40 if total >= 700 else 80
    _skip_individual_fallback = bool(batch_cache) and total >= 200

    for i, ticker in enumerate(all_tickers):
        try:
            _options_bullish = False
            _scan_progress(i, f"Scanning {ticker} ({i+1}/{total})...")
            if ticker not in _deep_signal_targets:
                scan_debug["cheap_prefilter_skipped"] += 1
                _scan_progress(i)
                continue

            # ── Earnings guard — pre-fetched calendar cache ──────────────
            if skip_earnings:
                _cal_days = _meta_cache.get(ticker, {}).get("cal_days")
                if _cal_days is not None and 0 <= _cal_days <= 7:
                    scan_debug["skipped_earnings"] += 1
                    _scan_progress(i)
                    continue


            # Use pre-fetched batch. For large universe scans, do NOT fall
            # back to one-by-one Yahoo downloads for symbols missing from the
            # batch. That fallback is very costly and mostly hits invalid,
            # delisted, mutual-fund, or temporarily unavailable symbols.
            if ticker in batch_cache:
                df = batch_cache[ticker]
            else:
                if _skip_individual_fallback:
                    scan_debug["skipped_history"] += 1
                    scan_debug["skipped_batch_miss_no_fallback"] += 1
                    _scan_progress(i)
                    continue
                raw_ind = yf.download(ticker, period="1y", interval="1d",
                                      progress=False, auto_adjust=True)
                if raw_ind.empty or len(raw_ind) < 60:
                    scan_debug["skipped_history"] += 1
                    _scan_progress(i)
                    continue
                if isinstance(raw_ind.columns, pd.MultiIndex):
                    raw_ind.columns = raw_ind.columns.get_level_values(0)
                df = _clean_scan_ohlcv(raw_ind)
                if ticker in intraday_cache:
                    df = _overlay_intraday_daily(df, intraday_cache[ticker])
                if len(df) >= 60:
                    scan_debug["individual_loaded"] += 1

            if len(df) < 60:
                scan_debug["skipped_history"] += 1
                _scan_progress(i)
                continue

            close = df["Close"].squeeze().ffill()
            high  = df["High"].squeeze().ffill()
            low   = df["Low"].squeeze().ffill()
            vol   = df["Volume"].squeeze().ffill()
            try:
                last_bar_ts = str(df["Last Bar"].dropna().iloc[-1]) if "Last Bar" in df.columns and not df["Last Bar"].dropna().empty else str(pd.Timestamp(df.index[-1]))
            except Exception:
                last_bar_ts = "–"

            # ── Pre-filter: liquidity only ────────────────────────────────────
            _vol_avg_s = float(vol.rolling(20).mean().iloc[-1])
            _p_chk     = float(close.iloc[-1])
            # v15.7 speed: avoid calling ta.average_true_range for every ticker
            # before we know it is a real candidate. A simple ATR approximation
            # is enough for the early liquidity/range gate and is much faster.
            if _p_chk > 0:
                try:
                    _prev_close = close.shift(1)
                    _tr_fast = pd.concat([
                        (high - low).abs(),
                        (high - _prev_close).abs(),
                        (low - _prev_close).abs(),
                    ], axis=1).max(axis=1)
                    _atr_pct = float(_tr_fast.tail(14).mean()) / _p_chk * 100
                except Exception:
                    _atr_pct = float((high.tail(14).max() - low.tail(14).min()) / _p_chk * 100 / 3)
            else:
                _atr_pct = 0.0
            # Market-aware liquidity gate. The old single threshold was tuned
            # for US names and was too harsh for SGX on Streamlit Cloud, where
            # only a smaller universe may load and many valid Singapore stocks
            # trade with lower SGD turnover. Keep US strict, but allow SGX to
            # pass when it is reasonably liquid and has enough movement.
            if str(ticker).upper().endswith(".SI"):
                _min_turnover = 120_000   # SGD/day approximation from yfinance price × volume
                _min_atr_pct  = 0.30
            elif str(ticker).upper().endswith(".NS"):
                _min_turnover = 250_000
                _min_atr_pct  = 0.50
            else:
                _min_turnover = 500_000
                _min_atr_pct  = 0.80

            # In strategy modes, keep the liquidity gate light. Otherwise a whole
            # strategy can show 0 rows simply because ATR/turnover is below the
            # default US-style gate, especially for SGX and cloud Yahoo data.
            if swing_mode == "HIGH VOLUME":
                # High Volume mode must rank activity first.  Do not use the
                # normal ATR/turnover gate here; it can remove every SGX/cloud
                # candidate before the volume strategy gets a chance to score it.
                # Only skip rows with unusable price/volume data.
                if _p_chk <= 0 or _vol_avg_s <= 0:
                    scan_debug["skipped_liquidity"] += 1
                    _scan_progress(i)
                    continue
            elif swing_mode in ("SUPPORT ENTRY", "PREMARKET MOMENTUM"):
                _strategy_min_turnover = max(_min_turnover * 0.25, 50_000)
                _strategy_min_atr_pct = max(_min_atr_pct * 0.35, 0.15)
                if _p_chk * _vol_avg_s < _strategy_min_turnover or _atr_pct < _strategy_min_atr_pct:
                    scan_debug["skipped_liquidity"] += 1
                    _scan_progress(i)
                    continue
            else:
                if _p_chk * _vol_avg_s < _min_turnover or _atr_pct < _min_atr_pct:
                    scan_debug["skipped_liquidity"] += 1
                    _scan_progress(i)
                    continue

            # v15.7 SPEED PREFILTER -------------------------------------------------
            # This still evaluates every ticker in the universe, but avoids the
            # expensive full signal engine for quiet/flat names with no useful
            # swing setup today.  It keeps broad conditions for long, short,
            # support, high-volume, and PM/live-momentum strategies.
            try:
                _c_now = float(close.iloc[-1])
                _c_prev = float(close.iloc[-2]) if len(close) >= 2 and float(close.iloc[-2]) != 0 else _c_now
                _today_pct_fast = (_c_now / _c_prev - 1.0) * 100 if _c_prev else 0.0
                _ma20_fast = float(close.tail(20).mean()) if len(close) >= 20 else _c_now
                _ma60_fast = float(close.tail(60).mean()) if len(close) >= 60 else _ma20_fast
                _hi20_fast = float(high.tail(20).max()) if len(high) >= 20 else _c_now
                _lo20_fast = float(low.tail(20).min()) if len(low) >= 20 else _c_now
                _vol20_fast = float(vol.tail(21).iloc[:-1].mean()) if len(vol) >= 21 else _vol_avg_s
                _vr_fast = float(vol.iloc[-1]) / _vol20_fast if _vol20_fast > 0 else 0.0
                _range_fast = max(float(high.iloc[-1]) - float(low.iloc[-1]), 0.0)
                _close_pos_fast = ((_c_now - float(low.iloc[-1])) / _range_fast) if _range_fast > 0 else 0.5
                _near_support_fast = (
                    (_ma20_fast > 0 and abs(_c_now / _ma20_fast - 1.0) <= 0.045) or
                    (_ma60_fast > 0 and abs(_c_now / _ma60_fast - 1.0) <= 0.055) or
                    (_lo20_fast > 0 and _c_now <= _lo20_fast * 1.08)
                )
                _breakout_fast = (_hi20_fast > 0 and _c_now >= _hi20_fast * 0.985)
                _breakdown_fast = (_lo20_fast > 0 and _c_now <= _lo20_fast * 1.015)
                _trend_fast = (_c_now >= _ma20_fast * 0.99 and _ma20_fast >= _ma60_fast * 0.985)
                _long_candidate_fast = (
                    _today_pct_fast >= 1.2 or _vr_fast >= 1.25 or _breakout_fast or
                    _trend_fast or _near_support_fast
                )
                _short_candidate_fast = (
                    _today_pct_fast <= -1.2 or _breakdown_fast or
                    (_vr_fast >= 1.35 and _close_pos_fast <= 0.40) or
                    (_c_now < _ma20_fast * 0.985 and _ma20_fast < _ma60_fast)
                )
                if abs(_today_pct_fast) >= 5.0 and _vr_fast >= 1.5:
                    _cheap_ok = True   # big mover: earnings gap, catalyst
                elif swing_mode == "HIGH VOLUME":
                    _cheap_ok = (_vr_fast >= 1.05 or abs(_today_pct_fast) >= 0.8 or _vol_avg_s > 0)
                elif swing_mode == "SUPPORT ENTRY":
                    _cheap_ok = (_near_support_fast or _vr_fast >= 1.10 or abs(_today_pct_fast) >= 0.8)
                elif swing_mode == "PREMARKET MOMENTUM":
                    _cheap_ok = (_today_pct_fast >= 0.2 or _vr_fast >= 1.10 or _breakout_fast or _trend_fast)
                elif _stage2_scan_requested and ticker in _stage2_fast_candidates:
                    _cheap_ok = True
                else:
                    _cheap_ok = (_long_candidate_fast or _short_candidate_fast)
                if not _cheap_ok:
                    scan_debug["cheap_prefilter_skipped"] += 1
                    _scan_progress(i)
                    continue
            except Exception:
                # If the cheap gate itself has trouble, fall through to the
                # original full signal engine rather than risk missing a ticker.
                pass

            scan_debug["signal_engine_ran"] += 1

            # Get sector ETF close for this ticker
            sec_name   = sector_membership.get(ticker, "")
            sec_etf    = SECTOR_ETFS.get(sec_name, "")
            sec_close  = sector_etf_closes.get(sec_etf, None)

            try:
                open_for_signals = df["Open"].squeeze().ffill()
            except Exception:
                open_for_signals = None
            long_sig, short_sig, raw = compute_all_signals(
                close, high, low, vol,
                spy_close=spy_close_global,
                sector_close=sec_close,
                open_=open_for_signals,
            )
            p    = raw["p"]
            atrv = raw["atr"]
            vr   = raw["vr"]
            today_chg = _safe_today_change_pct(close)

            # ── Operator + Trap detection (universe-wide) ─────────────────────
            # Runs for every scanned ticker so the Operator Activity tab can
            # surface stocks with manipulation patterns even when they don't
            # show a long/short setup.
            try:
                open_s = df["Open"].squeeze().ffill()
                _traps = detect_traps(
                    open_s, high, low, close, vol,
                    atrv, raw["last_swing_high"], raw["last_swing_low"]
                )
                _tsum = summarize_traps(_traps)
                _op_score = int(raw.get("operator_score", 0))
                # Include any ticker with meaningful operator/trap activity:
                # operator_score ≥ 2, OR any pattern detected, OR a trap-risk flag.
                if _op_score >= 2 or _tsum["count"] >= 1 or raw.get("false_breakout") \
                        or raw.get("gap_chase_risk") or raw.get("operator_distribution"):
                    operator_results.append({
                        "Ticker":       ticker,
                        "Sector":       sector_label(ticker),
                        "Price":        f"${p:.2f}",
                        "Today %":      f"{today_chg:+.2f}%",
                        "Op Score":     _op_score,
                        "Op Label":     raw.get("operator_label", "–"),
                        "Trap Bias":    _tsum["bias"],
                        "Patterns":     f"{_tsum['count']} ({_tsum['high']}H · {_tsum['med']}M · {_tsum['low']}L)" if _tsum["count"] else "–",
                        "Detected":     _tsum["patterns"],
                        "Trap Risk":    raw.get("trap_risk_label", "–"),
                        "Vol Ratio":    round(vr, 2),
                        "Last Bar":     last_bar_ts,
                        "VWAP":         "ABOVE" if raw.get("above_vwap") else "BELOW",
                        "RSI":          round(raw["rsi0"], 1),
                        "_bias_score":  _tsum["bias_score"],
                        "_op_score":    _op_score,
                        "_trap_count":  _tsum["count"],
                        "_high_count":  _tsum["high"],
                    })
            except Exception:
                pass

            # ── v12: OPTIONS ENRICHMENT ───────────────────────────────────────
            # Run only on US tickers that already show technical interest, so
            # we don't pay the option-chain HTTP cost on the full universe.
            # Failures fall through silently — keys simply won't be present
            # in long_sig/short_sig and bayesian_prob is unaffected.
            opt_long, opt_short, opt_raw = ({}, {}, {})
            if enable_options and _is_us_ticker_for_options(ticker):
                pre_l = sum(1 for v in long_sig.values()  if v)
                pre_s = sum(1 for v in short_sig.values() if v)
                if pre_l >= 4 or pre_s >= 3:
                    if _option_enrich_count >= _max_option_enrich:
                        scan_debug["options_skipped_speed_cap"] += 1
                    else:
                        try:
                            rets   = close.pct_change().dropna().tail(20)
                            rv_pct = float(rets.std() * (252 ** 0.5) * 100) \
                                     if len(rets) >= 10 else None
                            opt_long, opt_short, opt_raw = compute_options_signals(
                                ticker, p, rv_pct
                            )
                            _option_enrich_count += 1
                            scan_debug["options_enriched"] = int(_option_enrich_count)
                        except Exception:
                            opt_long, opt_short, opt_raw = ({}, {}, {})

            # Merge option signals into the existing signal dicts. The
            # Bayesian engine only consumes keys present in LONG_WEIGHTS /
            # SHORT_WEIGHTS, so this is purely additive.
            long_sig  = {**long_sig,  **opt_long}
            short_sig = {**short_sig, **opt_short}
            _options_bullish = bool(
                opt_long.get("opt_unusual_call_flow")
                or opt_long.get("opt_call_skew_bullish")
                or opt_long.get("opt_pc_volume_low")
            )

            # ── Float / short / PE — pre-fetched meta cache ──────────────────
            _m          = _meta_cache.get(ticker, {})
            float_shares = _m.get("float_shares")
            short_pct    = _m.get("short_pct")
            pe           = _m.get("pe")
            # v14.1: new fundamental fields
            cash_ratio   = _m.get("cash_ratio")     # totalCash/marketCap
            analyst_rec  = _m.get("analyst_rec")    # 1=Strong Buy … 5=Sell
            eps_revision_60d = _m.get("eps_revision_60d")
            eps_revision_available = bool(_m.get("eps_revision_available"))
            industry     = _m.get("industry", "")
            sector_detail= _m.get("sector_detail", "")

            float_str = f"{float_shares/1e6:.0f}M" if float_shares else "–"
            short_str = f"{short_pct*100:.1f}%"    if short_pct    else "–"
            # Short squeeze flag: high short interest + bullish signals
            squeeze_flag = (short_pct or 0) > 0.15

            # ── Cash floor string (Pro Swing fundamental context) ─────────────
            cash_floor_str = f"{cash_ratio:.0%}" if cash_ratio is not None else "–"
            # Flag: cash > 40% of market cap = meaningful downside buffer
            cash_floor_flag = (cash_ratio or 0) >= 0.40

            # ── Analyst consensus label ───────────────────────────────────────
            if analyst_rec is not None:
                if   analyst_rec <= 1.5: analyst_label = "💚 Strong Buy"
                elif analyst_rec <= 2.2: analyst_label = "🟢 Buy"
                elif analyst_rec <= 3.0: analyst_label = "🟡 Hold"
                elif analyst_rec <= 3.8: analyst_label = "🟠 Underperform"
                else:                    analyst_label = "🔴 Sell"
            else:
                analyst_label = "–"
            eps_revision_str = (
                f"{float(eps_revision_60d):+.1f}%"
                if eps_revision_available and eps_revision_60d is not None
                else "Unavailable"
            )

            # ── Biotech / high-risk sector flag ──────────────────────────────
            _high_risk_industries = {
                "Biotechnology", "Drug Manufacturers—Specialty & Generic",
                "Drug Manufacturers—General", "Pharmaceutical Retailers",
                "Medical Devices", "Diagnostics & Research",
                "Health Information Services",
            }
            # PSM caution sectors — signals work but moves are small or event-driven
            _caution_industries = {
                "Gambling", "Casinos & Gaming",
                "Entertainment", "Entertainment—Diversified",
                "Publishing", "Broadcasting",
                "Leisure", "Amusement Parks", "Hotels & Motels",
                "Restaurants", "Apparel Retail",
            }
            # Low-momentum sectors — directionally ok but rarely hit 5% in 7 days
            _low_momentum_industries = {
                "Utilities—Regulated Electric", "Utilities—Regulated Gas",
                "Utilities—Regulated Water", "Utilities—Diversified",
                "REIT—Retail", "REIT—Residential", "REIT—Office",
                "REIT—Industrial", "REIT—Diversified",
                "Insurance—Life", "Insurance—Property & Casualty",
                "Banks—Regional", "Banks—Diversified",
                "Grocery Stores", "Discount Stores",
            }
            # Use industry + sector label + cached sector detail. Yahoo often leaves
            # small biotech/pharma names as "Mixed", so industry-only checks miss
            # binary-event names and allow too many weak STRONG BUY labels.
            _sector_text = f"{industry} {sector_detail} {sector_label(ticker)}".lower()
            is_biotech   = (
                industry in _high_risk_industries
                or "biotech" in _sector_text
                or "biotechnology" in _sector_text
                or "drug manufacturers" in _sector_text
                or "pharma" in _sector_text
            )
            is_caution   = industry in _caution_industries
            is_slow      = industry in _low_momentum_industries

            # ETF detection via yfinance quoteType (already in info dict)
            is_etf = str(_m.get("quote_type", "")).upper() == "ETF"

            # PSM score gate — how many signals required for this sector
            if is_biotech:
                psm_min_score = 9     # very high bar: must have exceptional tech setup
                pos_size_note = "⚠️ Half — Biotech"
            elif is_etf:
                psm_min_score = 9     # ETFs rarely produce 5%+ moves in 7 days
                pos_size_note = "⚠️ Skip — ETF (low individual alpha)"
            elif is_caution:
                psm_min_score = 8     # event-driven sector, needs stronger confirmation
                pos_size_note = "⚠️ Caution — Event Sector"
            elif is_slow:
                psm_min_score = 8     # defensive/slow sectors
                pos_size_note = "⚠️ Caution — Low Momentum Sector"
            else:
                psm_min_score = 7     # standard PSM bar
                pos_size_note = "Normal"

            # ── v15: Pre-Earnings Run ─────────────────────────────────────────
            cal_days = _m.get("cal_days")
            pre_earnings_run = bool(
                cal_days is not None and
                3 <= int(cal_days) <= 7 and
                raw.get("weekly_trend", False) and
                raw.get("above_ma60",   False) and
                float(raw.get("rsi0", 50)) < 72
            )
            # Inject v15 signals into long_sig for Bayesian scoring
            long_sig["pre_earnings_run"] = pre_earnings_run
            # Specific combos proven to be more accurate than raw score alone
            combo_bonus = 0.0
            # Combo A: compression → explosion (BB squeeze + vol breakout + stoch)
            if long_sig["bb_bull_squeeze"] and long_sig["vol_breakout"] and long_sig["stoch_confirmed"]:
                combo_bonus += 0.07
            # Combo B: momentum alignment (MACD accel + RSI>50 + higher lows)
            if long_sig["macd_accel"] and long_sig["rsi_confirmed"] and long_sig["higher_lows"]:
                combo_bonus += 0.06
            # Combo C: trend + structure + market alignment
            if long_sig["trend_daily"] and long_sig["weekly_trend"] and long_sig["rel_strength"]:
                combo_bonus += 0.05
            # Combo D: fresh golden cross + breakout = highest quality setup
            if raw.get("gc_fresh") and long_sig["vol_breakout"]:
                combo_bonus += 0.08

            # Monday penalty — reduce probability on Mondays
            monday_penalty = 0.06 if is_monday else 0.0

            # ── LONG ──────────────────────────────────────────────────────────
            l_score       = sum(v for k, v in long_sig.items() if v)
            l_bonus       = (0.06 if raw["bb_very_tight"] else 0) + \
                            (0.05 if vr >= 2.5 else 0) + combo_bonus
            l_regime_mult = 0.75 if regime == "BEAR" else 0.88 if regime == "CAUTION" else 1.0
            l_prob_raw    = bayesian_prob(LONG_WEIGHTS, long_sig, l_bonus)
            l_prob        = round(max(0.35, min(0.95,
                            l_prob_raw * l_regime_mult
                            + (1 - l_regime_mult) * 0.40
                            - monday_penalty)), 4)
            l_top3 = (
                long_sig["stoch_confirmed"] or
                long_sig["bb_bull_squeeze"] or
                long_sig["macd_accel"]      or
                long_sig["vol_breakout"]    or   # breakout on 10d high + vol
                long_sig.get("vol_surge_up", False)  # green candle + 2x vol + 1.5% up
            )

            operator_score = int(raw.get("operator_score", 0))
            operator_confirmed = operator_score >= 4
            false_breakout = bool(raw.get("false_breakout", False))
            gap_chase_risk = bool(raw.get("gap_chase_risk", False))
            distribution_risk = bool(raw.get("operator_distribution", False))
            trap_risk = false_breakout or gap_chase_risk or distribution_risk

            # ── HIGH-ACCURACY GATE ─────────────────────────────────────────────
            # This prevents the Bayesian score from becoming over-confident when
            # many correlated trend signals fire together. Only these setups are
            # allowed to become STRONG BUY / ✅ BUY. Everything else is WATCH/WAIT.
            volume_confirmed = (
                long_sig.get("vol_breakout", False) or
                long_sig.get("pocket_pivot", False) or
                long_sig.get("vol_surge_up", False)
            )
            # Practical live-market setup types. These make the screener useful
            # even when a stock has no news catalyst or only moderate operator score.
            # _today_chg_abs and post_earnings_gap defined here so they
            # are available to is_chasing (defined further down).
            _today_chg_abs = float(raw.get("today_chg_pct", 0) or 0)
            _strong_close_sig = bool(
                raw.get("strong_close") or raw.get("vwap_support")
                or raw.get("above_vwap")
                or (vr >= 2.5 and _today_chg_abs >= 8.0)
            )
            _pure_vol_gap = (
                _today_chg_abs >= 8.0 and vr >= 2.5 and _strong_close_sig
            )
            post_earnings_gap = (
                (ticker.upper() in recent_earners_set or _pure_vol_gap)
                and _today_chg_abs >= 5.0
                and vr >= 1.5
            )
            major_trap_risk = (
                (false_breakout or distribution_risk
                 or (gap_chase_risk and _today_chg_abs > 10))
                and not post_earnings_gap
            )
            core_long_trend = (
                long_sig.get("trend_daily", False) or
                long_sig.get("full_ma_stack", False) or
                (raw.get("above_ma60", False) and raw.get("p", 0) > raw.get("ma20", 0))
            )
            momentum_confirmed = (
                long_sig.get("macd_accel", False) or
                long_sig.get("stoch_confirmed", False) or
                long_sig.get("momentum_3d", False) or
                long_sig.get("vol_breakout", False)
            )
            operator_or_vwap = operator_score >= 3 or raw.get("vwap_support", False) or long_sig.get("strong_close", False)
            pullback_setup = (
                (raw.get("dip_to_ma20", False) or raw.get("dip_to_ma60", False)) and
                raw.get("vol_declining", False) and raw.get("above_ma60", False) and
                core_long_trend
            )
            breakout_setup = (
                (long_sig.get("vol_breakout", False) or long_sig.get("pocket_pivot", False) or long_sig.get("vol_surge_up", False)) and
                core_long_trend and raw.get("above_ma60", False)
            )
            continuation_setup = (
                core_long_trend and long_sig.get("weekly_trend", False) and
                (long_sig.get("macd_accel", False) or long_sig.get("momentum_3d", False) or long_sig.get("rs_momentum", False))
            )

            # v14.1: Stabilization — post-gap-down base forming
            stabilization_setup = (
                raw.get("pss_breakdown", {}).get("PEAD-Stab", False) or
                raw.get("pss_breakdown", {}).get("Absorption", False)
            ) and not pullback_setup and not breakout_setup

            # v15: new pattern-based setup types
            nr7_active   = raw.get("nr7_setup",        False)
            id_active    = raw.get("inside_day",       False)
            fbd_active   = raw.get("failed_breakdown", False)
            flag_active  = raw.get("tight_flag",       False)
            cup_active   = raw.get("cup_handle",       False)
            per_active   = pre_earnings_run

            setup_type_long = (
                "Pullback"              if pullback_setup else
                "Breakout"              if breakout_setup else
                "Cup & Handle"          if cup_active else
                "Failed Breakdown"      if fbd_active else
                "Tight Flag"            if flag_active else
                "NR7 Coil"              if nr7_active else
                "Inside Day"            if id_active else
                "Pre-Earnings Run"      if per_active else
                "Stabilization"         if stabilization_setup else
                "Continuation"          if continuation_setup else
                "Operator Accumulation" if operator_score >= 4 else
                "Pro Swing"             if long_sig.get("pro_swing_setup", False) else
                "Early Trend"           if core_long_trend else
                "Mixed"
            )

            # ── Next-day swing score: ranks likely continuation/pullback buys ──
            # This is deliberately separate from the Bayesian probability because
            # many correlated trend signals can over-saturate Rise Prob. The goal
            # is fewer, cleaner 5–10% swing candidates rather than every mover.
            rsi_now = float(raw.get("rsi0", 50) or 50)
            atr_pct_live = float(raw.get("atr_pct", 0.0) or 0.0)
            has_vol_live = bool(raw.get("has_enough_volatility", atr_pct_live >= 2.5))
            high_vol_live = bool(raw.get("high_volatility", atr_pct_live >= 4.0))
            low_vol_exception = bool(post_earnings_gap and vr >= 2.5 and _today_chg_abs >= 5.0)

            # v16.5 fix: define earnings/post-event momentum BEFORE the v16
            # accuracy gate uses it for risk/reward and valid setup checks.
            # Previously this was assigned later in the function, causing
            # UnboundLocalError for tickers such as SEDG/ENPH during scan.
            _earn_momentum_long = bool(
                post_earnings_gap
                and vr >= 2.0
                and 8.0 <= _today_chg_abs <= 25.0
                and l_prob >= 0.45
                and not false_breakout
                and not distribution_risk
            )

            setup_family_ok = bool(
                pullback_setup or breakout_setup or continuation_setup
                or raw.get("failed_breakdown", False)
                or raw.get("tight_flag", False)
                or raw.get("nr7_setup", False)
                or raw.get("inside_day", False)
                or raw.get("cup_handle", False)
                or pre_earnings_run
            )
            confirmation_ok = bool(
                volume_confirmed or operator_score >= 4 or raw.get("vwap_support", False)
                or long_sig.get("strong_close", False) or post_earnings_gap
            )

            p_raw = float(raw.get("p", 0) or p)

            # ── v13 accuracy gate: can it realistically make +5–10% in 5–7 days?
            # The old score could mark a stock A+ even when entry quality later said
            # WAIT/AVOID. These gates align the whole scanner around the practical
            # swing target: target before stop, room to resistance, and enough ATR.
            expected_7d_move = round(float(atr_pct_live) * (7 ** 0.5), 2) if atr_pct_live > 0 else 0.0
            move_feasible = bool((2.8 <= atr_pct_live <= 10.0 and expected_7d_move >= 6.0) or low_vol_exception)
            extreme_volatility = bool(atr_pct_live > 12.0 and not post_earnings_gap)

            try:
                _h20 = float(high.iloc[-21:-1].max()) if len(high) >= 21 else float(raw.get("h10", 0) or 0)
                _h60 = float(high.iloc[-61:-1].max()) if len(high) >= 61 else _h20
            except Exception:
                _h20, _h60 = float(raw.get("h10", 0) or 0), 0.0
            _swing_hi = float(raw.get("last_swing_high", 0) or 0)
            _res_candidates = [x for x in [_h20, _h60, _swing_hi] if x and x > p_raw * 1.005]
            nearest_resistance = min(_res_candidates) if _res_candidates else 0.0
            upside_to_resistance = round(((nearest_resistance / p_raw) - 1.0) * 100.0, 2) if nearest_resistance > 0 and p_raw > 0 else 99.0
            confirmed_breakout = bool(((_h20 > 0 and p_raw >= _h20 * 1.003) or long_sig.get("vol_breakout", False)) and (volume_confirmed or post_earnings_gap))
            resistance_clearance_ok = bool(upside_to_resistance >= 6.0 or confirmed_breakout or post_earnings_gap or raw.get("failed_breakdown", False))

            # v14-patch: market-type flags — drive market-specific thresholds
            _t_upper = str(ticker).upper()
            is_sgx = _t_upper.endswith(".SI")
            is_hk  = _t_upper.endswith(".HK")
            # HK stocks (HKEX) have similar characteristics to SGX: lower ATR%,
            # lower vol ratios, tighter natural price moves — apply SGX-like gates.
            is_asia_market = is_sgx or is_hk
            _asia_vr_floor = 0.85 if is_hk else (0.60 if is_sgx else 1.00)
            # v14-patch: pullback volume confirmation (vol declining on dip = healthy)
            pullback_vol_ok = bool(long_sig.get("vol_declining", False) and vr < 1.0)
            hk_participation_ok = bool(
                (not is_hk)
                or vr >= _asia_vr_floor
                or volume_confirmed
                or _today_chg_abs >= 1.2
                or long_sig.get("vol_breakout", False)
                or long_sig.get("pocket_pivot", False)
                or operator_score >= 4
                or post_earnings_gap
                or pre_earnings_run
            )
            # v14-patch: support-aware stops + tighter SGX floor
            _stop_floor = 0.97 if is_asia_market else 0.94
            if raw.get("dip_to_ma60", False) and pullback_setup:
                _ma60_val = float(raw.get("ma60", p_raw * 0.97))
                approx_stop = round(_ma60_val * 0.993, 2)
            elif raw.get("dip_to_ma20", False) and pullback_setup:
                _ma20_val = float(raw.get("ma20", p_raw * 0.98))
                approx_stop = round(_ma20_val * 0.993, 2)
            else:
                approx_stop = max(
                    round(p_raw - 1.5 * atrv, 2),
                    round(float(raw.get("last_swing_low", p_raw * 0.95)) * 0.995, 2),
                    round(float(raw.get("ma60", p_raw * 0.95)) * 0.995, 2),
                    round(p_raw * _stop_floor, 2),
                )
            stop_risk_pct = round(max((p_raw - approx_stop) / max(p_raw, 0.01) * 100.0, 0.5), 2)
            # v14-patch: dynamic target = max(fixed, upside-to-resistance, 2×risk)
            _fixed_target = 8.0 if atr_pct_live >= 4.0 else 6.0
            _atr_target = expected_7d_move if expected_7d_move > 0 else _fixed_target
            _dynamic_target = min(max(4.0, min(_fixed_target, _atr_target)), 12.0)
            if 0 < upside_to_resistance < 50 and not confirmed_breakout:
                _dynamic_target = min(_dynamic_target, upside_to_resistance)
            elif confirmed_breakout and 0 < upside_to_resistance < 50:
                _dynamic_target = max(_dynamic_target, min(upside_to_resistance, 12.0))
            rr_est = round(min(_dynamic_target / max(stop_risk_pct, 0.5), 5.0), 2)
            risk_reward_ok = bool(
                rr_est >= 2.0 or
                (_earn_momentum_long and rr_est >= 1.5) or
                (upside_to_resistance >= 8.0 and rr_est >= 1.3)
            )

            not_overextended = bool((_today_chg_abs <= 7.5) or post_earnings_gap)
            healthy_pullback = bool(-4.5 <= _today_chg_abs <= 3.5 and pullback_setup and raw.get("above_ma60", False))
            fresh_breakout = bool(0.0 <= _today_chg_abs <= 7.5 and breakout_setup and volume_confirmed)
            valid_next_day_setup = bool(healthy_pullback or fresh_breakout or flag_active or nr7_active or fbd_active or _earn_momentum_long)

            next_day_score = 0
            if core_long_trend: next_day_score += 2
            if raw.get("above_ma60", False): next_day_score += 1
            if volume_confirmed: next_day_score += 3
            if operator_score >= 4: next_day_score += 2
            elif operator_score >= 3: next_day_score += 1
            if pullback_setup: next_day_score += 2
            if breakout_setup: next_day_score += 2
            if continuation_setup: next_day_score += 1
            if raw.get("failed_breakdown", False): next_day_score += 2
            if raw.get("tight_flag", False): next_day_score += 2
            if raw.get("nr7_setup", False): next_day_score += 1
            if raw.get("inside_day", False): next_day_score += 1
            if raw.get("cup_handle", False): next_day_score += 1
            if pre_earnings_run: next_day_score += 1
            if high_vol_live: next_day_score += 2
            elif has_vol_live: next_day_score += 1
            else: next_day_score -= 3
            if move_feasible: next_day_score += 2
            else: next_day_score -= 3
            if resistance_clearance_ok: next_day_score += 2
            else: next_day_score -= 3
            if risk_reward_ok: next_day_score += 2
            else: next_day_score -= 3
            if valid_next_day_setup: next_day_score += 2
            else: next_day_score -= 2
            if major_trap_risk: next_day_score -= 5
            if _today_chg_abs > 8 and not post_earnings_gap: next_day_score -= 4
            if _today_chg_abs < -6 and not raw.get("failed_breakdown", False): next_day_score -= 3
            if rsi_now > 76: next_day_score -= 3
            # v14-patch: SGX has lower vol ratios — lighter penalty
            _vr_floor = _asia_vr_floor if is_asia_market else 1.0
            if vr < _vr_floor and not pullback_setup: next_day_score -= 3
            elif pullback_vol_ok: next_day_score += 1
            if is_biotech and not post_earnings_gap and operator_score < 5: next_day_score -= 3
            if extreme_volatility: next_day_score -= 3

            quality_score = 0
            if core_long_trend: quality_score += 2
            if volume_confirmed: quality_score += 3
            if long_sig.get("rel_strength", False) or long_sig.get("rs_momentum", False) or long_sig.get("sector_leader", False): quality_score += 2
            if move_feasible: quality_score += 2
            if resistance_clearance_ok: quality_score += 2
            if risk_reward_ok: quality_score += 2
            if setup_family_ok: quality_score += 2
            if operator_score >= 4: quality_score += 2
            elif operator_score >= 3: quality_score += 1
            if not_overextended: quality_score += 1
            if valid_next_day_setup: quality_score += 2
            if not raw.get("not_chasing", True) or not raw.get("not_limit_up", True): quality_score -= 4
            if major_trap_risk: quality_score -= 5
            if _today_chg_abs > 8 and not post_earnings_gap: quality_score -= 3
            # v14-patch: pullback vol partial credit + SGX-aware thresholds
            if pullback_vol_ok and not volume_confirmed: quality_score += 2
            _qs_vr_floor = _asia_vr_floor if is_asia_market else 1.0
            if vr < _qs_vr_floor and not pullback_setup: quality_score -= 3
            if rsi_now > 75: quality_score -= 2
            _atr_min_qs = 1.5 if is_asia_market else 2.8
            if atr_pct_live < _atr_min_qs: quality_score -= 3
            elif atr_pct_live < 2.8 and is_asia_market: quality_score -= 1
            if atr_pct_live > 12.0 and not post_earnings_gap: quality_score -= 3
            if is_biotech and not post_earnings_gap and operator_score < 5: quality_score -= 3
            if is_hk and not hk_participation_ok:
                next_day_score -= 4
                quality_score -= 3

            # ── Pre-Mover score: designed for "tomorrow's movers" ─────────────
            # Long Setups can include good quality stocks that are simply slow.
            # This score is stricter: it wants compression + enough ATR + quiet
            # accumulation/relative strength before the big daily % move.
            _pss_breakdown = raw.get("pss_breakdown", {}) or {}
            _compression_signals = [
                raw.get("nr7_setup", False),
                raw.get("inside_day", False),
                raw.get("tight_flag", False),
                raw.get("cup_handle", False),
                raw.get("bb_squeeze", False),
                raw.get("bb_very_tight", False),
                long_sig.get("vcp_tightness", False),
                _pss_breakdown.get("VDU", False),
                _pss_breakdown.get("FlatBase", False),
            ]
            _compression_count = sum(1 for _x in _compression_signals if _x)
            _compression_ok = _compression_count >= 1

            _accumulation_count = sum(1 for _x in [
                operator_score >= 2,
                long_sig.get("obv_rising", False),
                raw.get("above_vwap", False),
                raw.get("vol_declining", False),
                _pss_breakdown.get("InstAcc", False),
                _pss_breakdown.get("Absorption", False),
                long_sig.get("pocket_pivot", False),
            ] if _x)
            _accumulation_ok = _accumulation_count >= 1

            _near_trigger = bool(
                (raw.get("h10", 0) and p_raw >= float(raw.get("h10", 0)) * 0.970) or
                (_swing_hi and p_raw >= float(_swing_hi) * 0.970) or
                (raw.get("ma20", 0) and p_raw >= float(raw.get("ma20", 0)) * 0.985)
            )
            _relative_ok = bool(
                long_sig.get("rel_strength", False) or
                long_sig.get("rs_momentum", False) or
                long_sig.get("sector_leader", False) or
                _pss_breakdown.get("MktWeakRS", False)
            )
            _catalyst_ok = bool(
                pre_earnings_run or
                _pss_breakdown.get("PEAD-Stab", False) or
                _pss_breakdown.get("Absorption", False) or
                _pss_breakdown.get("CatalystNews", False)
            )
            _quiet_before_move = bool(-1.5 <= _today_chg_abs <= 2.5)
            _not_yet_moved = bool(_today_chg_abs <= 3.5)
            _pre_volatility_ok = bool((atr_pct_live >= (1.6 if is_asia_market else 2.8)) and expected_7d_move >= (4.5 if is_asia_market else 6.0))

            pre_mover_score = 0
            if core_long_trend: pre_mover_score += 10
            if raw.get("above_ma60", False): pre_mover_score += 5
            pre_mover_score += min(_compression_count, 3) * 10
            pre_mover_score += min(_accumulation_count, 3) * 7
            if _near_trigger: pre_mover_score += 12
            if _relative_ok: pre_mover_score += 10
            if _catalyst_ok: pre_mover_score += 8
            if _quiet_before_move: pre_mover_score += 10
            elif _today_chg_abs > 3.5: pre_mover_score -= 18
            elif _today_chg_abs < -3.0: pre_mover_score -= 8
            if _pre_volatility_ok: pre_mover_score += 12
            else: pre_mover_score -= 16
            if volume_confirmed and _not_yet_moved: pre_mover_score += 5
            if major_trap_risk: pre_mover_score -= 20
            if is_slow and not _catalyst_ok: pre_mover_score -= 10
            if is_etf: pre_mover_score -= 12
            if rsi_now > 74: pre_mover_score -= 8
            if _today_chg_abs > 6.0 and not post_earnings_gap: pre_mover_score -= 15
            pre_mover_score = int(max(0, min(100, pre_mover_score)))

            # Calibration: quiet compression is useful only when close to a
            # trigger. This prevents large/steady names from scoring 80+ while
            # sitting 8-12% below their 10d/swing breakout area on weak volume.
            if not _near_trigger:
                pre_mover_score = min(pre_mover_score, 58)
            if not _compression_ok:
                pre_mover_score = min(pre_mover_score, 52)
            if not _accumulation_ok:
                pre_mover_score = min(pre_mover_score, 56)
            if vr < (_asia_vr_floor if is_asia_market else 1.0) and not _catalyst_ok and not _options_bullish:
                pre_mover_score = min(pre_mover_score, 62)
            if is_hk and not hk_participation_ok:
                pre_mover_score = min(pre_mover_score, 45)
            if _today_chg_abs < -1.5 and not raw.get("failed_breakdown", False):
                pre_mover_score = min(pre_mover_score, 60)

            pre_mover_ready = bool(
                pre_mover_score >= 70 and _compression_ok and _accumulation_ok
                and _near_trigger and _pre_volatility_ok and _not_yet_moved
                and not major_trap_risk
            )
            pre_mover_watch = bool(
                pre_mover_score >= 55 and _compression_ok and _pre_volatility_ok
                and _not_yet_moved and not major_trap_risk
            )
            if pre_mover_ready:
                pre_mover_tier = "A - PRE-MOVER READY"
            elif pre_mover_watch:
                pre_mover_tier = "B - COIL WATCH"
            elif pre_mover_score >= 40 and _not_yet_moved:
                pre_mover_tier = "C - EARLY WATCH"
            elif _today_chg_abs > 3.5:
                pre_mover_tier = "MOVED ALREADY"
            else:
                pre_mover_tier = "SLOW / NOT READY"

            _pm_reasons = []
            if _compression_ok: _pm_reasons.append(f"compression x{_compression_count}")
            if _accumulation_ok: _pm_reasons.append(f"accumulation x{_accumulation_count}")
            if _near_trigger: _pm_reasons.append("near trigger")
            if _relative_ok: _pm_reasons.append("relative strength")
            if _catalyst_ok: _pm_reasons.append("catalyst/absorption")
            if _quiet_before_move: _pm_reasons.append("quiet before move")
            if not _pre_volatility_ok: _pm_reasons.append("low ATR/move potential")
            if _today_chg_abs > 3.5: _pm_reasons.append("already moved today")
            if is_slow and not _catalyst_ok: _pm_reasons.append("slow sector")
            pre_mover_why = " | ".join(_pm_reasons[:6]) if _pm_reasons else "quality setup, but no pre-mover evidence"

            # ── Explosion score: style early watch ───────────────────────────
            # Separate from normal pre-movers. This looks for names that can
            # realistically jump 10-20% when the trigger arrives: high ATR,
            # smaller float/short interest, catalyst/options activity, and a
            # coiled chart before the big daily move.
            _short_pct_val = float(short_pct or 0.0)
            _float_val = float(float_shares or 0.0)
            _float_small = bool(_float_val > 0 and _float_val <= 120_000_000)
            _float_mid = bool(_float_val > 0 and _float_val <= 300_000_000)
            _short_squeeze_fuel = bool(_short_pct_val >= 0.10 or squeeze_flag)
            try:
                _recent_5d_pct = float((close.iloc[-1] / close.iloc[-6] - 1.0) * 100.0) if len(close) >= 6 else 0.0
            except Exception:
                _recent_5d_pct = 0.0
            try:
                _recent_20d_pct = float((close.iloc[-1] / close.iloc[-21] - 1.0) * 100.0) if len(close) >= 21 else 0.0
            except Exception:
                _recent_20d_pct = 0.0
            try:
                _recent_60d_pct = float((close.iloc[-1] / close.iloc[-61] - 1.0) * 100.0) if len(close) >= 61 else 0.0
            except Exception:
                _recent_60d_pct = 0.0
            try:
                _recent_120d_pct = float((close.iloc[-1] / close.iloc[-121] - 1.0) * 100.0) if len(close) >= 121 else 0.0
            except Exception:
                _recent_120d_pct = 0.0
            _recent_run_extended = bool((_recent_5d_pct >= 25.0) or (_recent_20d_pct >= 50.0))

            # 7-star early swing filter: range shift + divergence + one-red hold.
            # This is a ranking layer for Pre-Movers; it does not turn a stock
            # into a buy without confirmation.
            try:
                _range20_hi = float(high.tail(20).max()) if len(high) >= 20 else float(raw.get("h10", p_raw) or p_raw)
                _range20_lo = float(low.tail(20).min()) if len(low) >= 20 else float(raw.get("last_swing_low", p_raw) or p_raw)
                _range20_pos = (p_raw - _range20_lo) / max(_range20_hi - _range20_lo, 0.01)
            except Exception:
                _range20_pos = 0.0
            _ma20_star = float(raw.get("ma20", 0) or 0)
            _ma60_star = float(raw.get("ma60", 0) or 0)
            _liq_floor = 120_000 if is_asia_market else 500_000
            _star_liquidity = bool(p_raw > 0 and _vol_avg_s > 0 and (p_raw * _vol_avg_s >= _liq_floor))
            _star_move_potential = bool(_pre_volatility_ok and not extreme_volatility)
            _star_compression = bool(_compression_ok)
            _star_range_shift = bool(
                (
                    (_ma20_star > 0 and p_raw >= _ma20_star * 0.995)
                    or raw.get("above_vwap", False)
                    or raw.get("failed_breakdown", False)
                    or _near_trigger
                )
                and _range20_pos >= 0.55
                and -3.5 <= _today_chg_abs <= 3.5
                and not _recent_run_extended
            )
            _star_divergence = bool(
                _accumulation_ok
                and (_relative_ok or long_sig.get("obv_rising", False) or operator_score >= 3)
                and _recent_5d_pct <= 12.0
                and _today_chg_abs <= 3.5
                and not _recent_run_extended
            )
            _holds_key_area = bool(
                raw.get("above_vwap", False)
                or raw.get("failed_breakdown", False)
                or (_ma20_star > 0 and p_raw >= _ma20_star * 0.985)
                or (_ma60_star > 0 and p_raw >= _ma60_star * 0.985)
            )
            _panic_red = bool(vr >= 1.8 and _today_chg_abs <= -2.5)
            _star_one_red = bool(
                -3.5 <= _today_chg_abs <= -0.15
                and _holds_key_area
                and (_recent_5d_pct >= 1.5 or _relative_ok or _accumulation_ok)
                and not _panic_red
                and not _recent_run_extended
            )
            _star_risk_reward = bool(
                risk_reward_ok
                and resistance_clearance_ok
                and not major_trap_risk
                and not _recent_run_extended
                and _today_chg_abs <= 5.0
            )
            _seven_flags = [
                ("liquid", _star_liquidity),
                ("move potential", _star_move_potential),
                ("compression", _star_compression),
                ("range shift", _star_range_shift),
                ("divergence/accumulation", _star_divergence),
                ("one red hold", _star_one_red),
                ("risk/reward", _star_risk_reward),
            ]
            seven_star_score = sum(1 for _, _ok in _seven_flags if _ok)
            if is_hk and not hk_participation_ok:
                seven_star_score = min(seven_star_score, 4)
            if _recent_run_extended and not post_earnings_gap:
                seven_star_score = min(seven_star_score, 4)
            if _today_chg_abs <= -5.0 and not raw.get("failed_breakdown", False):
                seven_star_score = min(seven_star_score, 3)
            if seven_star_score >= 7:
                seven_star_tier = "7 - PRIME"
            elif seven_star_score == 6:
                seven_star_tier = "6 - READY"
            elif seven_star_score == 5:
                seven_star_tier = "5 - WATCH"
            elif seven_star_score == 4:
                seven_star_tier = "4 - EARLY"
            else:
                seven_star_tier = "LOW"
            if _recent_run_extended and not post_earnings_gap:
                seven_star_tier = "MOVED ALREADY"
            _seven_reasons = [name for name, ok in _seven_flags if ok]
            if _recent_run_extended:
                _seven_reasons.append(f"already ran 5D {_recent_5d_pct:.1f}% / 20D {_recent_20d_pct:.1f}%")
            seven_star_why = " | ".join(_seven_reasons[:7]) if _seven_reasons else "not enough 7-star evidence"
            _pss_score_val = int(raw.get("pss_score", 0) or 0)
            _explosive_breakout_trigger = bool(
                (raw.get("h10", 0) and p_raw >= float(raw.get("h10", 0)) * 0.940) or
                (_swing_hi and p_raw >= float(_swing_hi) * 0.940)
            )
            _pss_explosive_fuel = bool(
                _pss_breakdown.get("PEAD-Up", False)
                or _pss_breakdown.get("PEAD-Stab", False)
                or _pss_breakdown.get("SqzProxy", False)
                or _pss_breakdown.get("Absorption", False)
                or _pss_breakdown.get("CatalystNews", False)
            )
            _style_explosive_fuel = bool(
                _short_squeeze_fuel or _float_mid or _options_bullish or _pss_explosive_fuel
            )
            _explosive_vol_ok = bool(atr_pct_live >= (2.2 if is_asia_market else 4.0) and expected_7d_move >= (5.5 if is_asia_market else 8.0))
            _explosive_catalyst = bool(_catalyst_ok or _options_bullish or pre_earnings_run or _pss_explosive_fuel)
            _explosive_structure = bool(_compression_ok or _explosive_breakout_trigger or raw.get("failed_breakdown", False) or raw.get("tight_flag", False))
            _explosive_flow = bool(_accumulation_ok or operator_score >= 3 or long_sig.get("pocket_pivot", False) or long_sig.get("obv_rising", False))

            explosion_score = 0
            if atr_pct_live >= 7.0: explosion_score += 24
            elif atr_pct_live >= 5.0: explosion_score += 18
            elif atr_pct_live >= (2.2 if is_asia_market else 4.0): explosion_score += 12
            else: explosion_score -= 18
            if expected_7d_move >= 12.0: explosion_score += 12
            elif expected_7d_move >= 8.0: explosion_score += 8
            if _short_pct_val >= 0.18: explosion_score += 16
            elif _short_pct_val >= 0.10: explosion_score += 10
            elif _short_pct_val >= 0.06: explosion_score += 5
            if _float_small: explosion_score += 12
            elif _float_mid: explosion_score += 6
            if _compression_ok: explosion_score += 10
            if _accumulation_ok: explosion_score += 10
            if _near_trigger: explosion_score += 8
            if _relative_ok: explosion_score += 8
            if _explosive_catalyst: explosion_score += 12
            if _options_bullish: explosion_score += 10
            if p_raw <= 25 and atr_pct_live >= 4.0 and not is_etf: explosion_score += 4
            if _quiet_before_move: explosion_score += 8
            elif _today_chg_abs > 3.5: explosion_score -= 18
            if _today_chg_abs > 8.0 and not post_earnings_gap: explosion_score -= 25
            if major_trap_risk: explosion_score -= 22
            if is_slow and not _explosive_catalyst: explosion_score -= 15
            if is_etf: explosion_score -= 18
            if rsi_now > 78: explosion_score -= 10
            explosion_score = int(max(0, min(100, explosion_score)))

            # Calibration: large-cap / low-volume names can have ATR and generic
            # PSS structure, but they are not NVTS-style explosive candidates
            # unless they have true fuel and are near a breakout trigger.
            if not _style_explosive_fuel:
                no_fuel_cap = 58
                if not _explosive_breakout_trigger:
                    no_fuel_cap -= 8
                if vr < (_asia_vr_floor if is_asia_market else 1.0):
                    no_fuel_cap -= 8
                if p_raw > 100 and not _short_squeeze_fuel:
                    no_fuel_cap -= 6
                if not _compression_ok:
                    no_fuel_cap -= 6
                explosion_score = min(explosion_score, max(25, no_fuel_cap))
            if not _explosive_breakout_trigger and not _explosive_catalyst:
                trigger_cap = 60
                if vr < (_asia_vr_floor if is_asia_market else 1.0):
                    trigger_cap -= 8
                explosion_score = min(explosion_score, trigger_cap)
            if vr < (_asia_vr_floor if is_asia_market else 1.0) and not _options_bullish and not _pss_explosive_fuel:
                explosion_score = min(explosion_score, 54)
            if is_hk and not hk_participation_ok:
                explosion_score = min(explosion_score, 42)
            if _float_val >= 1_000_000_000 and not _short_squeeze_fuel and not _options_bullish and not _pss_explosive_fuel:
                explosion_score = min(explosion_score, 55)
            if _recent_run_extended and not post_earnings_gap:
                explosion_score = min(explosion_score, 42)
                pre_mover_score = min(pre_mover_score, 45)
            if _today_chg_abs <= -5.0 and not raw.get("failed_breakdown", False):
                explosion_score = min(explosion_score, 38)
                pre_mover_score = min(pre_mover_score, 35)

            explosion_ready = bool(
                explosion_score >= 75
                and _explosive_vol_ok
                and _not_yet_moved
                and _explosive_structure
                and _explosive_flow
                and _style_explosive_fuel
                and (_explosive_breakout_trigger or _explosive_catalyst)
                and not major_trap_risk
            )
            explosion_watch = bool(
                explosion_score >= 55
                and _explosive_vol_ok
                and _not_yet_moved
                and (_explosive_structure or _explosive_flow)
                and _style_explosive_fuel
                and not major_trap_risk
            )
            if explosion_ready:
                explosion_tier = "X - STYLE EXPLOSIVE"
            elif explosion_watch:
                explosion_tier = "A - EXPLOSIVE WATCH"
            elif explosion_score >= 45 and _not_yet_moved:
                explosion_tier = "B - SPECULATIVE WATCH"
            elif _recent_run_extended:
                explosion_tier = "MOVED ALREADY"
            elif _today_chg_abs > 3.5:
                explosion_tier = "MOVED ALREADY"
            else:
                explosion_tier = "LOW EXPLOSION"

            _expl_reasons = []
            if _explosive_vol_ok: _expl_reasons.append(f"ATR {atr_pct_live:.1f}% / 7D {expected_7d_move:.1f}%")
            else: _expl_reasons.append("not enough ATR")
            if _short_squeeze_fuel: _expl_reasons.append(f"short {(_short_pct_val*100):.1f}%")
            if _float_small: _expl_reasons.append("small float")
            elif _float_mid: _expl_reasons.append("mid float")
            if _explosive_breakout_trigger: _expl_reasons.append("near breakout trigger")
            if _compression_ok: _expl_reasons.append("coil/compression")
            if _accumulation_ok: _expl_reasons.append("accumulation")
            if _explosive_catalyst: _expl_reasons.append("catalyst/options/fuel")
            if not _style_explosive_fuel: _expl_reasons.append("no squeeze/float/catalyst fuel")
            if _recent_run_extended: _expl_reasons.append(f"already ran 5D {_recent_5d_pct:.1f}% / 20D {_recent_20d_pct:.1f}%")
            if _today_chg_abs > 3.5: _expl_reasons.append("already moved today")
            if is_slow and not _explosive_catalyst: _expl_reasons.append("slow sector")
            explosion_why = " | ".join(_expl_reasons[:7])

            # provisional only; final rating is recomputed after entry-quality gates
            if next_day_score >= 10 and quality_score >= 12:
                next_day_rating = "🔥 A+ NEXT-DAY BUY"
            elif next_day_score >= 8 and quality_score >= 9:
                next_day_rating = "✅ BUY"
            elif next_day_score >= 5 or quality_score >= 6:
                next_day_rating = "👀 WATCH"
            else:
                next_day_rating = "SKIP"

            # v14-patch: setup-type and market-aware NDS/QS gates
            _nds_gate = 6 if is_hk else (4 if is_sgx else (6 if (pullback_setup or continuation_setup) else 8))
            _qs_gate  = 9 if is_hk else (7 if is_sgx else 9)
            next_day_buy_ok = bool(
                raw.get("above_ma60", False)
                and core_long_trend
                and move_feasible
                and resistance_clearance_ok
                and risk_reward_ok
                and valid_next_day_setup
                and not major_trap_risk
                and 35 <= rsi_now <= 75
                and setup_family_ok
                and confirmation_ok
                and hk_participation_ok
                and next_day_score >= _nds_gate
                and quality_score >= _qs_gate
            )

            # Probability calibration: do not allow weak/no-volume setups to show
            # unrealistic 90–95% probabilities. This fixes the main false sense of
            # accuracy in Discovery/Balanced outputs.
            if not volume_confirmed and operator_score < 4 and not pullback_setup and not post_earnings_gap:
                l_prob = min(l_prob, 0.72)
            if _today_chg_abs < -6 and not raw.get("failed_breakdown", False):
                l_prob = min(l_prob, 0.62)
            if vr < 1.0 and not pullback_setup and not post_earnings_gap:
                l_prob = min(l_prob, 0.70)
            if (not has_vol_live) and not low_vol_exception:
                l_prob = min(l_prob, 0.68)
            if major_trap_risk:
                l_prob = min(l_prob, 0.60)
            if is_biotech and not post_earnings_gap and operator_score < 5:
                l_prob = min(l_prob, 0.68)
            l_prob = round(float(l_prob), 4)

            # ── HIGH CONVICTION: category-based confluence (5 independent groups) ──
            # Requiring 1+ signal from each of 5 unrelated categories is much
            # stronger than requiring N signals from one correlated pool.
            # A stock confirming in all 5 has genuine multi-dimensional strength.
            _hc_trend = any([
                long_sig.get("trend_daily", False),
                long_sig.get("weekly_trend", False),
                long_sig.get("golden_cross", False),
                long_sig.get("full_ma_stack", False),
            ])
            _hc_momentum = any([
                long_sig.get("macd_accel", False),
                long_sig.get("stoch_confirmed", False),
                long_sig.get("rsi_confirmed", False),
                long_sig.get("momentum_3d", False),
            ])
            _hc_volume = any([
                long_sig.get("vol_breakout", False),
                long_sig.get("vol_surge_up", False),
                long_sig.get("pocket_pivot", False),
                long_sig.get("operator_accumulation", False),
            ])
            _hc_structure = any([
                long_sig.get("higher_lows", False),
                long_sig.get("vcp_tightness", False),
                long_sig.get("strong_close", False),
                long_sig.get("bull_candle", False),
            ])
            _hc_market = any([
                long_sig.get("rel_strength", False),
                long_sig.get("rs_momentum", False),
                long_sig.get("sector_leader", False),
                long_sig.get("near_52w_high", False),
            ])
            _hc_cats_hit = sum([_hc_trend, _hc_momentum, _hc_volume, _hc_structure, _hc_market])
            _hc_rsi_ok   = 32 <= rsi_now <= 76
            _hc_no_trap  = not major_trap_risk and raw.get("above_ma60", False)
            _hc_full     = (_hc_cats_hit == 5 and _hc_rsi_ok and _hc_no_trap)
            _hc_partial  = (_hc_cats_hit == 4 and _hc_rsi_ok and _hc_no_trap)
            # Build a readable tag for the Signals column
            _hc_parts = []
            if _hc_trend:     _hc_parts.append("T")
            if _hc_momentum:  _hc_parts.append("M")
            if _hc_volume:    _hc_parts.append("V")
            if _hc_structure: _hc_parts.append("S")
            if _hc_market:    _hc_parts.append("X")
            _hc_tag = f"HC[{'+'.join(_hc_parts)}]({_hc_cats_hit}/5)" if _hc_parts else ""

            # ═══════════════════════════════════════════════════════════════════
            # STRATEGY HELPERS: SUPPORT ENTRY / PREMARKET MOMENTUM
            #
            # Fix: do not depend only on exact dip_to_ma20/dip_to_ma60 flags or
            # yfinance pre_market_price. Those are often False/blank on Cloud.
            # Compute support proximity directly and use true PM data when
            # available, otherwise a clearly-labelled LIVE momentum fallback.
            # ═══════════════════════════════════════════════════════════════════
            p_raw        = raw.get("p", 0) or p
            rsi_now      = raw.get("rsi0", 50) or 50
            today_pct    = raw.get("today_chg_pct", 0) or 0
            ma20_now     = raw.get("ma20", 0) or 0
            ma60_now     = raw.get("ma60", 0) or 0
            ma200_now    = raw.get("ma200", 0) or raw.get("e200", 0) or 0
            vwap_now     = raw.get("vwap", 0) or 0
            swing_lo_val = raw.get("last_swing_low", 0) or 0

            def _pct_dist(price, level):
                try:
                    return (float(price) / float(level) - 1.0) if float(level) > 0 else 999.0
                except Exception:
                    return 999.0

            dist_ma20  = _pct_dist(p_raw, ma20_now)
            dist_ma60  = _pct_dist(p_raw, ma60_now)
            dist_ma200 = _pct_dist(p_raw, ma200_now)
            dist_vwap  = _pct_dist(p_raw, vwap_now)
            dist_swing = _pct_dist(p_raw, swing_lo_val)

            near_ma60      = (-0.020 <= dist_ma60  <= 0.040)
            near_ma20      = (-0.020 <= dist_ma20  <= 0.035)
            near_ma200     = (ma200_now > 0 and -0.020 <= dist_ma200 <= 0.040)
            near_swing_lo  = (swing_lo_val > 0 and -0.010 <= dist_swing <= 0.045)
            near_vwap      = (vwap_now > 0 and abs(dist_vwap) <= 0.018)
            support_distance_abs = min(
                abs(dist_ma20) if ma20_now > 0 else 999.0,
                abs(dist_ma60) if ma60_now > 0 else 999.0,
                abs(dist_ma200) if ma200_now > 0 else 999.0,
                abs(dist_vwap) if vwap_now > 0 else 999.0,
                abs(dist_swing) if swing_lo_val > 0 else 999.0,
            )
            near_any_support = support_distance_abs <= 0.080

            trend_ok_for_support = bool(
                raw.get("above_ma60", False) or
                long_sig.get("trend_daily", False) or
                long_sig.get("full_ma_stack", False) or
                (ma20_now > 0 and p_raw >= ma20_now * 0.98)
            )
            not_extended = today_pct <= 5.0
            rsi_support_ok = 25 <= rsi_now <= 72
            support_quality_ok = bool(
                l_prob >= 0.50 or l_score >= 3 or
                long_sig.get("trend_daily", False) or
                long_sig.get("higher_lows", False) or
                long_sig.get("obv_rising", False)
            )

            if near_ma60 and trend_ok_for_support:
                support_tier = 1; support_zone = "🔵 MA60 SUPPORT"
            elif near_ma20 and trend_ok_for_support:
                support_tier = 2; support_zone = "🟢 MA20 SUPPORT"
            elif near_swing_lo and trend_ok_for_support:
                support_tier = 3; support_zone = "🟡 SWING LOW SUPPORT"
            elif near_ma200 and not major_trap_risk:
                support_tier = 4; support_zone = "🟣 MA200 SUPPORT"
            elif near_vwap and trend_ok_for_support and rsi_support_ok:
                support_tier = 5; support_zone = "⚪ VWAP SUPPORT"
            elif near_any_support and trend_ok_for_support and rsi_support_ok:
                # Final fallback: still filtered, but prevents an empty Support
                # Entry tab when no stock is exactly on MA20/MA60/VWAP today.
                support_tier = 6; support_zone = "🟤 NEAR SUPPORT"
            else:
                support_tier = 0; support_zone = "–"

            at_support_entry = bool(
                support_tier >= 1 and
                rsi_support_ok and
                not raw.get("ma60_stop_triggered", False) and
                not major_trap_risk and
                (support_quality_ok or trend_ok_for_support or l_score >= 1 or l_prob >= 0.38)
            )

            # ── Pre-market price — pre-fetched meta cache ────────────────────
            _pm_m       = _meta_cache.get(ticker, {})
            pm_chg_pct  = float(_pm_m.get("pm_chg",   0.0) or 0.0)
            pm_price    = float(_pm_m.get("pm_price", 0.0) or 0.0)
            pm_data_ok  = bool(_pm_m.get("pm_ok",    False))
            pm_source   = "PM" if pm_data_ok else "LIVE"


            # Premarket data is unreliable in yfinance/Streamlit Cloud.
            # When true PM fields are missing, do NOT return an empty strategy.
            # Fall back in this order:
            #   1) LIVE day move versus previous daily close
            #   2) recent technical momentum candidate when live % is flat/blank
            if not pm_data_ok:
                pm_chg_pct = round(float(today_pct or 0.0), 2)
                pm_price = float(p_raw or 0.0)
                pm_data_ok = pm_chg_pct > 0
                pm_source = "LIVE"

            if pm_data_ok and 3.0 <= pm_chg_pct <= 8.0:
                pm_tier = "A"; pm_zone = f"🚀 {pm_source} +{pm_chg_pct:.1f}%"
            elif pm_data_ok and 1.0 <= pm_chg_pct < 3.0:
                pm_tier = "B"; pm_zone = f"📈 {pm_source} +{pm_chg_pct:.1f}%"
            elif pm_source == "LIVE" and pm_data_ok and 0.2 <= pm_chg_pct < 1.0:
                pm_tier = "C"; pm_zone = f"👀 LIVE +{pm_chg_pct:.1f}%"
            elif (momentum_confirmed or volume_confirmed or long_sig.get("rs_momentum", False) or long_sig.get("trend_daily", False) or vr >= 1.00 or l_score >= 1) and \
                 (core_long_trend or raw.get("above_ma60", False) or long_sig.get("full_ma_stack", False) or today_pct > -4.0 or l_score >= 2) and \
                 (l_prob >= 0.35 or l_score >= 1 or vr >= 1.00):
                # This is the important empty-result fix: outside premarket hours,
                # many valid momentum stocks have no PM/live percentage available.
                # Show them as technical momentum candidates instead of returning 0 rows.
                pm_tier = "D"
                pm_zone = "🟡 MOMENTUM CANDIDATE"
                pm_source = "TECH"
                pm_data_ok = True
            else:
                pm_tier = None; pm_zone = "–"

            has_pm_signal = bool(
                pm_tier is not None and
                rsi_now < 88 and
                not major_trap_risk and
                -6.0 <= today_pct <= 18.0
            )

            # HIGH VOLUME strategy helper. Rank volume from raw OHLCV first.
            # yfinance/Cloud can produce weak signal flags, so do not rely only
            # on long_sig["vol_breakout"].  Use a robust relative-volume score.
            try:
                _last_vol = float(vol.iloc[-1])
                _avg20_vol = float(vol.tail(21).iloc[:-1].mean()) if len(vol) >= 21 else float(vol.rolling(20).mean().iloc[-1])
                _med50_vol = float(vol.tail(50).median()) if len(vol) >= 10 else _avg20_vol
                _avg3_vol = float(vol.tail(3).mean()) if len(vol) >= 3 else _last_vol
                _vr1 = _last_vol / _avg20_vol if _avg20_vol > 0 else 0.0
                _vr_med = _last_vol / _med50_vol if _med50_vol > 0 else 0.0
                _vr3 = _avg3_vol / _avg20_vol if _avg20_vol > 0 else 0.0
                hv_vr = max(float(vr or 0.0), _vr1, _vr_med, _vr3)
                _vol_rank = float((vol.tail(60) <= _last_vol).mean()) if len(vol) >= 10 else 0.0
            except Exception:
                hv_vr = float(vr or 0.0)
                _vol_rank = 0.0

            hv_score = 0
            if hv_vr >= 3.0: hv_score += 4
            elif hv_vr >= 2.0: hv_score += 3
            elif hv_vr >= 1.5: hv_score += 2
            elif hv_vr >= 1.15: hv_score += 1
            if _vol_rank >= 0.90: hv_score += 2
            elif _vol_rank >= 0.75: hv_score += 1
            if long_sig.get("vol_breakout", False): hv_score += 3
            if long_sig.get("vol_surge_up", False): hv_score += 2
            if long_sig.get("pocket_pivot", False): hv_score += 2
            if long_sig.get("strong_close", False): hv_score += 1
            if long_sig.get("obv_rising", False): hv_score += 1
            if today_pct >= 0.0: hv_score += 1
            if today_pct >= 2.0: hv_score += 1
            if core_long_trend or raw.get("above_ma60", False): hv_score += 1
            if today_pct > 15.0 or rsi_now >= 92:
                hv_score = max(0, hv_score - 2)

            if hv_vr >= 3.0 and today_pct >= -1.0:
                hv_tier = "A"; hv_zone = f"🔥 EXTREME VOLUME {hv_vr:.1f}x"
            elif hv_vr >= 2.0 and today_pct >= -1.5:
                hv_tier = "B"; hv_zone = f"🚀 VOLUME BREAKOUT {hv_vr:.1f}x"
            elif long_sig.get("pocket_pivot", False) or (hv_vr >= 1.6 and today_pct >= 0 and raw.get("above_ma20", True)):
                hv_tier = "C"; hv_zone = f"📌 POCKET PIVOT / ACCUMULATION {hv_vr:.1f}x"
            elif hv_vr >= 1.15 and today_pct >= -3.0:
                hv_tier = "D"; hv_zone = f"👀 UNUSUAL VOLUME {hv_vr:.1f}x"
            elif swing_mode == "HIGH VOLUME" and _vol_rank >= 0.65 and today_pct >= -4.0:
                # Last-resort but still volume-based: show the most active names
                # instead of a blank strategy tab.
                hv_tier = "E"; hv_zone = f"👀 ACTIVE VOLUME rank {int(_vol_rank*100)}%"
                hv_score = max(hv_score, 1)
            else:
                hv_tier = None; hv_zone = "–"

            has_hv_signal = bool(hv_tier is not None and rsi_now < 95 and -8.0 <= today_pct <= 25.0)

            _earn_momentum_long = (
                post_earnings_gap
                and vr >= 2.0
                and 8.0 <= _today_chg_abs <= 25.0
                and l_prob >= 0.45
                and not false_breakout
                and not distribution_risk
            )
            high_accuracy_long = (
                (_earn_momentum_long and next_day_score >= 7)
                or (
                    next_day_buy_ok and
                    l_prob >= min_prob_strong_long and
                    l_score >= min_score_strong_long and
                    raw.get("not_limit_up", False) and
                    raw.get("today_chg_pct", 99) < (8 if swing_mode != "DISCOVERY" else 10) and
                    momentum_confirmed and
                    (volume_confirmed or operator_score >= 4 or raw.get("vwap_support", False) or pullback_setup)
                )
            )

            # ── 90% CONFIDENCE TIER ────────────────────────────────────────────
            # Important: this is NOT a guaranteed win rate. It is a strict display
            # tier used to avoid showing 90-95% confidence on WATCH/DISCOVERY rows.
            # A row can show 90%+ only if it is tradeable, has room to target,
            # confirmed participation, no trap/chase risk, and multiple independent
            # confluence layers. Actual win-rate must be validated in Accuracy Lab.
            ninety_confidence_long = bool(
                high_accuracy_long
                and next_day_buy_ok
                and next_day_score >= (16 if not is_asia_market else 14)
                and quality_score >= (14 if not is_asia_market else 12)
                and rr_est >= 2.0
                and not major_trap_risk
                and not is_chasing
                and not extreme_volatility
                and 35 <= rsi_now <= 72
                and _today_chg_abs <= (6.0 if not post_earnings_gap else 18.0)
                and (
                    (volume_confirmed and operator_score >= 4)
                    or (pre_mover_ready and seven_star_score >= 5)
                    or (raw.get("tight_flag", False) and raw.get("above_vwap", False))
                    or (raw.get("failed_breakdown", False) and operator_score >= 3)
                )
            )
            actionable_long = (
                next_day_score >= 6 and
                l_prob >= (0.64 if swing_mode == "DISCOVERY" else 0.68) and
                l_score >= (4 if swing_mode == "DISCOVERY" else 5) and
                raw.get("above_ma60", False) and
                not major_trap_risk and
                core_long_trend and
                setup_family_ok and
                (confirmation_ok or pullback_setup)
            )

            _er_trend = bool(core_long_trend or raw.get("stage2_ready") or raw.get("stage2_phase") in ("EARLY COIL", "READY AT PIVOT", "BASE BUILDING", "BREAKOUT - TOO LATE"))
            _er_relative = bool(_relative_ok or raw.get("stage2_rs_lead") or raw.get("stage2_sector_lead"))
            _er_volume = bool(
                _accumulation_ok
                or volume_confirmed
                or vr >= 1.25
                or operator_score >= 2
                or raw.get("pss_score", 0) >= 2
            )
            _er_base = bool(
                raw.get("stage2_base_weeks", 0) >= 3
                or _compression_ok
                or _near_trigger
                or support_tier >= 1
                or raw.get("tight_flag", False)
                or raw.get("cup_handle", False)
            )
            _er_trigger = bool(
                raw.get("stage2_phase") in ("READY AT PIVOT", "BREAKOUT - TOO LATE")
                or _near_trigger
                or long_sig.get("vol_breakout", False)
                or long_sig.get("pocket_pivot", False)
                or raw.get("failed_breakdown", False)
            )
            _er_move_potential = bool(expected_7d_move >= 5.0 or atr_pct_live >= 2.0 or resistance_clearance_ok)
            _er_rr_ok = bool(risk_reward_ok or rr_est >= 1.5 or upside_to_resistance >= 5.0 or raw.get("stage2_blue_sky", False))
            _er_buy_rr = bool(rr_est >= 1.5 and (upside_to_resistance >= 5.0 or raw.get("stage2_blue_sky", False) or confirmed_breakout))
            _er_stage_base = bool(
                3 <= float(raw.get("stage2_base_weeks", 0) or 0) <= 16
                and float(raw.get("stage2_base_range_pct", 99) or 99) <= 25.0
                and raw.get("stage2_phase") in ("EARLY COIL", "READY AT PIVOT", "BASE BUILDING")
            )
            _er_coil_base = bool(
                float(raw.get("stage2_early_score", 0) or 0) >= 5
                and float(raw.get("stage2_base_range_pct", 99) or 99) <= 25.0
                and float(raw.get("stage2_contraction_ratio", 99) or 99) <= 0.85
                and float(raw.get("stage2_volume_dryup_ratio", 99) or 99) <= 1.20
            )
            _er_compact_base = bool(
                3 <= float(raw.get("stage2_base_weeks", 0) or 0) <= 16
                and float(raw.get("stage2_base_range_pct", 99) or 99) <= 25.0
                and float(raw.get("stage2_contraction_ratio", 99) or 99) <= 0.90
                and float(raw.get("stage2_early_score", 0) or 0) >= 4
            )
            _er_fresh_room = bool(
                float(raw.get("stage2_post_pivot_room_pct", 0) or 0) >= 6.0
                or upside_to_resistance >= 8.0
                or (
                    raw.get("stage2_blue_sky", False)
                    and float(raw.get("stage2_post_pivot_room_pct", 0) or 0) <= 0.0
                )
            )
            _er_fresh_structure = bool(
                (_er_stage_base or _er_coil_base or _er_compact_base)
                and _er_fresh_room
            )
            _er_dist_ma20_pct = (
                (p_raw / float(raw.get("ma20", 0)) - 1.0) * 100.0
                if float(raw.get("ma20", 0) or 0) > 0
                else 0.0
            )
            _er_moved_label = bool(
                "MOVED ALREADY" in str(pre_mover_tier).upper()
                or "MOVED ALREADY" in str(explosion_tier).upper()
            )
            _er_mature_run = bool(
                raw.get("stage2_phase") == "BREAKOUT - TOO LATE"
                or _recent_60d_pct > 30.0
                or _recent_120d_pct > 55.0
                or (_er_moved_label and not _er_fresh_structure)
            )
            _er_not_extended = bool(
                -3.0 <= today_chg <= 3.5
                and -6.0 <= _recent_5d_pct <= 12.0
                and -12.0 <= _recent_20d_pct <= 20.0
                and -18.0 <= _recent_60d_pct <= 30.0
                and -25.0 <= _recent_120d_pct <= 55.0
                and _er_dist_ma20_pct <= 5.0
                and rsi_now <= 68.0
                and not _er_mature_run
            )
            _er_pullback_needed = bool(
                today_chg > 3.5
                or _recent_5d_pct > 12.0
                or _recent_20d_pct > 20.0
                or _er_dist_ma20_pct > 5.0
                or rsi_now > 68.0
            )
            _er_too_late = _er_mature_run
            _er_entry_ok = bool(
                not raw.get("ma60_stop_triggered", False)
                and not is_chasing
                and not major_trap_risk
            )
            early_rally_score = (
                (12 if _er_trend else 0)
                + (10 if _er_relative else 0)
                + (14 if _er_volume else 0)
                + (12 if _er_base else 0)
                + (10 if _er_trigger else 0)
                + (10 if _er_move_potential else 0)
                + (8 if _er_rr_ok else 0)
                + (7 if _er_entry_ok else 0)
                + (7 if _er_not_extended else 0)
                + (5 if l_prob >= 0.55 else 0)
                + (3 if l_score >= 3 else 0)
                + (2 if quality_score >= 5 else 0)
                + (10 if _er_fresh_structure else 0)
                + min(int(raw.get("stage2_score", 0) or 0), 10) * 0.8
                + min(int(raw.get("stage2_early_score", 0) or 0), 10) * 0.8
                - (12 if not _er_fresh_structure else 0)
                - (12 if _er_pullback_needed else 0)
                - (25 if _er_too_late else 0)
                - (10 if not next_day_buy_ok else 0)
            )
            early_rally_score = int(max(0, min(100, round(early_rally_score))))
            early_rally_buy = bool(
                early_rally_score >= 72
                and _er_trend and _er_relative and _er_volume and (_er_base or _er_trigger)
                and _er_move_potential and _er_buy_rr and _er_fresh_structure
                and _er_not_extended and _er_entry_ok
                and next_day_buy_ok and not _er_too_late
            )
            early_rally_trigger_watch = bool(
                not early_rally_buy and early_rally_score >= 60
                and _er_trend and _er_volume and (_er_base or _er_trigger)
                and _er_move_potential and _er_rr_ok and _er_fresh_structure
                and _er_not_extended and not _er_pullback_needed and not _er_too_late
            )
            early_rally_accum_watch = bool(
                not early_rally_buy and not early_rally_trigger_watch and early_rally_score >= 50
                and (_er_trend or _er_relative) and _er_volume and _er_base
                and _er_rr_ok and _er_fresh_structure and _er_not_extended
                and not _er_pullback_needed and not _er_too_late
            )
            early_rally_pullback_watch = bool(
                not early_rally_buy and early_rally_score >= 55 and _er_pullback_needed
                and _er_fresh_structure and not _er_mature_run
                and (_er_trend or _er_relative) and (_er_volume or _er_trigger)
            )
            if not early_rally_buy:
                early_rally_score = min(early_rally_score, 79)
            if early_rally_accum_watch:
                early_rally_score = min(early_rally_score, 69)
            early_rally_missing_parts = []
            if not _er_trend: early_rally_missing_parts.append("trend")
            if not _er_relative: early_rally_missing_parts.append("relative strength")
            if not _er_volume: early_rally_missing_parts.append("volume/accumulation")
            if not (_er_base or _er_trigger): early_rally_missing_parts.append("base or trigger")
            if not _er_move_potential: early_rally_missing_parts.append("move potential")
            if not _er_rr_ok: early_rally_missing_parts.append("R:R/upside")
            if not _er_buy_rr: early_rally_missing_parts.append("buy R:R/upside")
            if not _er_fresh_structure: early_rally_missing_parts.append("fresh base + usable room")
            if not _er_entry_ok: early_rally_missing_parts.append("entry quality")
            if not next_day_buy_ok: early_rally_missing_parts.append("tradeable buy")
            if not _er_not_extended: early_rally_missing_parts.append("not extended")
            if _er_mature_run: early_rally_missing_parts.append("mature/already moved")
            early_rally_missing = ", ".join(early_rally_missing_parts[:6]) if early_rally_missing_parts else "None - buy gate passed"

            if swing_mode == "EARLY RALLY FINDER":
                if early_rally_buy:
                    l_action = "BUY - CONFIRMED EARLY RALLY"
                elif early_rally_pullback_watch:
                    l_action = None
                elif early_rally_trigger_watch:
                    l_action = "WATCH - EARLY RALLY TRIGGER"
                elif early_rally_accum_watch:
                    l_action = "WATCH - EARLY ACCUMULATION"
                else:
                    l_action = None

            elif swing_mode == "SUPPORT ENTRY":
                if not at_support_entry:
                    l_action = None
                elif support_tier == 1 and (l_prob >= 0.60 or l_score >= 4 or actionable_long):
                    l_action = "BUY – MA60 SUPPORT"
                elif support_tier == 2 and (l_prob >= 0.56 or l_score >= 4 or actionable_long):
                    l_action = "BUY – MA20 SUPPORT"
                elif support_tier == 3 and (l_prob >= 0.52 or l_score >= 3):
                    l_action = "WATCH – SWING LOW SUPPORT"
                elif support_tier == 4 and (l_prob >= 0.52 or l_score >= 3):
                    l_action = "WATCH – MA200 SUPPORT"
                elif support_tier == 5 and (l_prob >= 0.52 or l_score >= 3):
                    l_action = "WATCH – VWAP SUPPORT"
                elif support_tier == 6:
                    l_action = "WATCH – NEAR SUPPORT"
                else:
                    l_action = "WATCH – SUPPORT CANDIDATE" if support_tier >= 1 else None

            elif swing_mode == "PREMARKET MOMENTUM":
                if not has_pm_signal:
                    l_action = None
                elif pm_tier == "A" and (high_accuracy_long or l_prob >= 0.56 or l_score >= 4 or momentum_confirmed):
                    l_action = "BUY – PM MOMENTUM" if pm_source == "PM" else "BUY – LIVE MOMENTUM"
                elif pm_tier == "B" and (l_prob >= 0.50 or l_score >= 3 or momentum_confirmed):
                    l_action = "WATCH – PM BUILDING" if pm_source == "PM" else "WATCH – LIVE MOMENTUM"
                elif pm_tier == "C" and (l_score >= 2 or momentum_confirmed or volume_confirmed):
                    l_action = "WATCH – LIVE MOMENTUM"
                elif pm_tier == "D":
                    l_action = "WATCH – MOMENTUM CANDIDATE"
                else:
                    l_action = "WATCH – MOMENTUM CANDIDATE" if pm_tier else None

            elif swing_mode == "HIGH VOLUME":
                if not has_hv_signal:
                    l_action = None
                elif hv_tier == "A":
                    l_action = "BUY – EXTREME VOLUME" if hv_score >= 4 else "WATCH – EXTREME VOLUME"
                elif hv_tier == "B":
                    l_action = "BUY – VOLUME BREAKOUT" if hv_score >= 4 else "WATCH – VOLUME BREAKOUT"
                elif hv_tier == "C":
                    l_action = "WATCH – POCKET PIVOT"
                elif hv_tier == "D":
                    l_action = "WATCH – UNUSUAL VOLUME"
                elif hv_tier == "E":
                    l_action = "WATCH – ACTIVE VOLUME"
                else:
                    l_action = "WATCH – VOLUME CANDIDATE" if hv_tier else None

            elif swing_mode == "HIGH CONVICTION":
                if _hc_full and _hc_volume and high_accuracy_long:
                    l_action = "STRONG BUY – HIGH CONVICTION"
                elif _hc_full and l_prob >= min_prob_strong_long:
                    l_action = "BUY – PRECISION SETUP"
                elif _hc_full and l_prob >= 0.57:
                    l_action = "BUY – PRECISION SETUP"
                elif _hc_partial and l_prob >= 0.60 and core_long_trend:
                    l_action = "WATCH – CONFLUENCE"
                else:
                    l_action = None

            else:
                # Standard strategy modes must be meaningfully different.
                # Previous fallback rules were too broad, so Strict/Balanced/Discovery
                # often displayed the same tickers.  Keep the same signal engine, but
                # apply different final gates per mode.
                if swing_mode == "STRICT":
                    # A+ only: strong probability, score, trend and confirmation.
                    if high_accuracy_long:
                        l_action = "STRONG BUY – STRICT"
                    elif (
                        l_prob >= max(min_prob_strong_long, 0.78)
                        and l_score >= max(min_score_strong_long, 7)
                        and raw.get("above_ma60", False)
                        and core_long_trend
                        and momentum_confirmed
                        and volume_confirmed
                        and not trap_risk
                        and not major_trap_risk
                    ):
                        l_action = "WATCH – STRICT QUALITY"
                    else:
                        l_action = None

                elif swing_mode == "DISCOVERY":
                    # Wide watchlist: allow earlier trend + probability combinations.
                    # IMPORTANT: Discovery is used as the MASTER SCAN that feeds
                    # all other strategies via _apply_strategy_from_master(). It must
                    # catch every stock with any meaningful signal — even in bearish
                    # sessions where trend_daily=False and above_ma60=False.
                    # Do NOT gate WATCH-EARLY on core_long_trend: that causes empty
                    # master → all strategies show zero results in down markets.
                    if high_accuracy_long and _earn_momentum_long:
                        l_action = "STRONG BUY – EARNINGS GAP"
                    elif high_accuracy_long:
                        l_action = "STRONG BUY – DISCOVERY"
                    elif actionable_long:
                        l_action = "WATCH – DISCOVERY QUALITY"
                    elif raw.get("stage2_phase") in ("EARLY COIL", "BREAKOUT - TOO LATE", "BASE BUILDING"):
                        # Discovery is the reusable master scan. Preserve valid
                        # Stage 2 bases even when short-term momentum is still quiet.
                        l_action = "WATCH – STAGE 2 BASE"
                    elif trap_risk and l_score >= 4 and l_prob >= 0.58:
                        l_action = "WATCH – TRAP RISK"
                    elif l_score >= 4 and l_prob >= 0.55:
                        l_action = "WATCH – DEVELOPING"
                    elif l_score >= 3 and l_prob >= 0.48:
                        l_action = "WATCH – EARLY"
                    elif l_score >= 2 and l_prob >= 0.44:
                        # Minimum threshold: ensures the master always has content
                        # even in choppy/bearish sessions. Filtered out by every mode
                        # except Discovery itself, but keeps the master non-empty.
                        l_action = "WATCH – CANDIDATE"
                    else:
                        l_action = None

                else:  # BALANCED
                    # Practical mode: stricter than Discovery, looser than Strict.
                    if high_accuracy_long and _earn_momentum_long:
                        l_action = "STRONG BUY – EARNINGS GAP"
                    elif high_accuracy_long:
                        l_action = "STRONG BUY"
                    elif actionable_long:
                        l_action = "WATCH – HIGH QUALITY"
                    elif trap_risk and l_score >= 5 and l_prob >= 0.66 and core_long_trend:
                        l_action = "WATCH – TRAP RISK"
                    elif (
                        l_score >= 5
                        and l_prob >= 0.66
                        and core_long_trend
                        and (momentum_confirmed or volume_confirmed or pullback_setup or breakout_setup)
                    ):
                        l_action = "WATCH – DEVELOPING"
                    else:
                        l_action = None

            if l_action:
                # ── v15.2: ATR% flag surfaced in scan row ─────────────────────
                atr_pct_val = raw.get("atr_pct", 0.0)
                has_vol     = raw.get("has_enough_volatility", True)
                high_vol    = raw.get("high_volatility", False)

                # ── Fix 3: Tighter stop = ATR×1.5 max (was effectively wider) ──
                # Research: stops wider than 1.5×ATR on swing trades reduce EV.
                # ARCT had avg loss of -4.19% — tighter stop limits the damage.
                l_atr_stop   = round(p - 1.5 * atrv, 2)          # hard: 1.5×ATR
                l_swing_stop = round(raw["last_swing_low"] * 0.995, 2)
                l_ma60_stop  = round(raw["ma60"] * 0.995, 2)
                l_stop       = max(l_atr_stop, l_swing_stop, l_ma60_stop)
                # Absolute floor: never risk more than 6% on any single trade
                l_stop       = max(l_stop, round(p * 0.94, 2))
                l_risk       = max(p - l_stop, p * 0.001)

                # ── Fix 2: ATR-scaled targets (BOTZ issue — targets too far) ──
                # High-vol stocks (ATR% ≥ 4%): keep 10/15/20% targets
                # Med-vol stocks (2.5-4%): use 7/12/17% targets
                # Low-vol (<2.5%): flag — unlikely to hit 5% in 7 days
                if high_vol:          # ATR% >= 4% — IREN/BB type
                    tp1_mult, tp2_mult, tp3_mult = 1.10, 1.15, 1.20
                    l_time_stop = "Day 5 if < +4%"
                elif has_vol:         # ATR% 2.5-4% — GRND/DKNG type
                    tp1_mult, tp2_mult, tp3_mult = 1.07, 1.12, 1.17
                    l_time_stop = "Day 4 if < +3%"
                else:                 # ATR% < 2.5% — BOTZ/ARKG type
                    tp1_mult, tp2_mult, tp3_mult = 1.05, 1.08, 1.12
                    l_time_stop = "⚠️ Low vol — skip or Day 3 if < +2%"

                l_pt_short  = round(p * tp1_mult, 2)
                l_pt_swing1 = round(p * tp2_mult, 2)
                l_pt_swing2 = round(p * tp3_mult, 2)

                # ── Fix 4: Trailing stop — lock in profits after +4% ──────────
                # Problem: LYFT +4.91x RR but avg 2.35% means exits too late/early.
                # Solution: once trade hits +4%, trail at breakeven+1% (protect capital).
                # Once hits +7%, trail at +4% (lock in meaningful gain).
                # Show the Trail Stop as price level where we'd start trailing.
                trail_trigger_pct = 0.04    # start trailing after +4%
                l_trail = round(p * (1 + trail_trigger_pct - 0.01), 2)  # trail = entry+3%

                # ── ATR% label for display ────────────────────────────────────
                atr_pct_str = f"{atr_pct_val:.1f}%"
                atr_vol_tag = "🔥 High" if high_vol else ("✅ OK" if has_vol else "⚠️ Low")

                # ── Strategy filter tags ──────────────────────────────────────────
                strat_tags = []
                if post_earnings_gap:          strat_tags.append("📅EARNINGS GAP")
                if _earn_momentum_long:         strat_tags.append("🚀PEAD")
                if raw.get("dip_to_ma20"):     strat_tags.append("📍DIP-MA20")
                if raw.get("dip_to_ma60"):     strat_tags.append("📍DIP-MA60")
                if raw.get("vol_declining"): strat_tags.append("📉VOL-DIP")
                if not raw.get("not_chasing", True):  strat_tags.append("⚠️CHASING")
                if not raw.get("not_limit_up", True): strat_tags.append("🚫LIMIT-UP")
                if raw.get("ma60_stop_triggered"):     strat_tags.append("🛑MA60-BREAK")
                if raw.get("stage2_ready"):             strat_tags.append("STAGE2 EARLY COIL")
                elif raw.get("stage2_breakout"):        strat_tags.append("STAGE2 BREAKOUT LATE")
                elif raw.get("stage2_phase") == "BASE BUILDING":
                    strat_tags.append("STAGE2 BASE")

                # Strategy entry quality
                is_ideal_dip = (raw.get("dip_to_ma20") or raw.get("dip_to_ma60")) and \
                               raw.get("vol_declining") and raw.get("not_chasing") and \
                               raw.get("not_limit_up")
                is_vol_surge = long_sig.get("vol_surge_up", False)   # vol burst entry
                # post_earnings_gap is defined above (near major_trap_risk)
                # so this reference is safe.
                is_chasing   = (
                    (not raw.get("not_chasing", True) or not raw.get("not_limit_up", True))
                    and not post_earnings_gap
                )
                is_stopped   = raw.get("ma60_stop_triggered", False)

                if is_stopped:
                    entry_quality = "🚫 AVOID"
                elif major_trap_risk or is_chasing:
                    entry_quality = "⏳ WAIT"
                elif next_day_buy_ok and (is_ideal_dip or is_vol_surge or long_sig.get("pocket_pivot", False) or long_sig.get("vol_breakout", False) or continuation_setup or _earn_momentum_long or valid_next_day_setup):
                    entry_quality = "✅ BUY"
                elif quality_score >= 6 or next_day_score >= 5:
                    entry_quality = "👀 WATCH"
                else:
                    entry_quality = "SKIP"

                # Final unified tradeability gate for 5–10% in 5–7 trading days.
                # This prevents contradictory rows such as A+ Next-Day but WAIT/AVOID.
                tradeable_buy = bool(
                    entry_quality == "✅ BUY"
                    and next_day_buy_ok
                    and not is_chasing
                    and not is_stopped
                    and not major_trap_risk
                    and confirmation_ok
                    and move_feasible
                    and resistance_clearance_ok
                    and risk_reward_ok
                    and quality_score >= _qs_gate    # v14-patch
                    and next_day_score >= _nds_gate  # v14-patch
                )
                a_plus_buy = bool(
                    tradeable_buy
                    and quality_score >= 12
                    and next_day_score >= 10
                    and (vr >= 1.5 or post_earnings_gap)
                    and operator_score >= 3
                    and expected_7d_move >= 7.0
                )

                # v14-patch: Discovery Buy — high Rise Prob near-miss
                discovery_buy = bool(
                    not tradeable_buy
                    and entry_quality not in ("🚫 AVOID",)
                    and l_prob >= 0.82
                    and quality_score >= 8
                    and next_day_score >= 5
                    and risk_reward_ok
                    and core_long_trend
                    and not major_trap_risk
                    and not is_chasing
                    and hk_participation_ok
                )
                # v14-patch: Near-Miss Buy — pullback/continuation just below gate
                near_miss_buy = bool(
                    not tradeable_buy
                    and not discovery_buy
                    and quality_score >= 7
                    and next_day_score >= 5
                    and risk_reward_ok
                    and core_long_trend
                    and not is_chasing
                    and not major_trap_risk
                    and (pullback_setup or continuation_setup)
                    and vr >= (0.85 if is_hk else (0.5 if is_sgx else 0.7))
                    and entry_quality not in ("🚫 AVOID",)
                )
                if a_plus_buy:
                    entry_quality = "✅ BUY"
                    next_day_rating = "🔥 A+ NEXT-DAY BUY"
                elif tradeable_buy:
                    entry_quality = "✅ BUY"
                    next_day_rating = "✅ BUY"
                elif discovery_buy:
                    entry_quality = "🔍 DISCOVERY BUY"
                    next_day_rating = "🔍 DISCOVERY"
                elif near_miss_buy:
                    entry_quality = "⚡ NEAR-MISS BUY"
                    next_day_rating = "⚡ NEAR-MISS"
                elif entry_quality in ("🚫 AVOID", "⏳ WAIT"):
                    next_day_rating = "SKIP" if entry_quality == "🚫 AVOID" else "⏳ WAIT"
                elif quality_score >= 6 or next_day_score >= 5:
                    entry_quality = "👀 WATCH"
                    next_day_rating = "👀 WATCH"
                else:
                    entry_quality = "SKIP"
                    next_day_rating = "SKIP"
                if a_plus_buy:
                    trade_tier = "A+"
                elif tradeable_buy:
                    trade_tier = "Full"
                elif discovery_buy:
                    trade_tier = "Discovery"
                elif near_miss_buy:
                    trade_tier = "Near-Miss"
                else:
                    trade_tier = "Watch"

                display_pos_size_note = pos_size_note
                if discovery_buy:
                    display_pos_size_note = "Half - discovery"
                elif near_miss_buy:
                    display_pos_size_note = "Small - near miss"
                elif not tradeable_buy:
                    display_pos_size_note = "Watch only"

                if l_action and "STRONG BUY" in str(l_action) and not tradeable_buy:
                    if is_chasing:
                        l_action = "WATCH – CHASING"
                    elif not move_feasible:
                        l_action = "WATCH – MOVE NOT FEASIBLE"
                    elif not resistance_clearance_ok:
                        l_action = "WATCH – NEAR RESISTANCE"
                    elif not risk_reward_ok:
                        l_action = "WATCH – RR TOO LOW"
                    elif (not has_vol_live and not low_vol_exception) or not confirmation_ok:
                        l_action = "WATCH – LOW VOL/NO CONFIRM"
                    elif is_biotech and not post_earnings_gap and operator_score < 5:
                        l_action = "WATCH – BIOTECH RISK"
                    else:
                        l_action = "WATCH – NEED CONFIRMATION"

                # Calibrate displayed probability separately from internal Bayesian score.
                # Internal l_prob still drives ranking, but displayed confidence should
                # never imply 90%+ unless the strict 90% tier passes.
                display_prob = float(l_prob)
                if ninety_confidence_long:
                    display_prob = max(display_prob, 0.90)
                    display_prob = min(display_prob, 0.93)
                    confidence_tier = "90% CONFIDENCE"
                elif high_accuracy_long:
                    display_prob = min(display_prob, 0.88)
                    confidence_tier = "HIGH ACCURACY"
                elif tradeable_buy:
                    display_prob = min(display_prob, 0.84)
                    confidence_tier = "TRADEABLE"
                elif discovery_buy:
                    display_prob = min(display_prob, 0.78)
                    confidence_tier = "DISCOVERY"
                elif near_miss_buy:
                    display_prob = min(display_prob, 0.74)
                    confidence_tier = "NEAR MISS"
                else:
                    display_prob = min(display_prob, 0.70)
                    confidence_tier = "WATCH ONLY"

                l_tags = []
                if long_sig["stoch_confirmed"]: l_tags.append("STOCH BOUNCE")
                if long_sig["bb_bull_squeeze"]: l_tags.append("BB BULL SQ")
                if long_sig["macd_accel"]:      l_tags.append("MACD ACCEL")
                if long_sig["vol_breakout"]:    l_tags.append("VOL BREAKOUT")
                if long_sig["higher_lows"]:     l_tags.append("HIGHER LOWS")
                if long_sig["rsi_confirmed"]:   l_tags.append("RSI>50")
                if long_sig["weekly_trend"]:    l_tags.append("WKLY TREND")
                if long_sig["golden_cross"]:    l_tags.append("🟡GC" if not raw.get("gc_fresh") else "🔥FRESH GC")
                if long_sig["rel_strength"]:    l_tags.append("RS>SPY")
                if long_sig["near_52w_high"]:   l_tags.append("52W HIGH")
                if long_sig["obv_rising"]:      l_tags.append("OBV↑")
                if long_sig["bull_candle"]:     l_tags.append("BULL CANDLE")
                if long_sig["sector_leader"]:   l_tags.append("SEC LEAD")
                if long_sig.get("vol_surge_up"):   l_tags.append("🚀VOL SURGE UP")
                if long_sig.get("pocket_pivot"):   l_tags.append("📌POCKET PIVOT")
                if squeeze_flag:                   l_tags.append("⚡SQUEEZE")
                if vr >= 2.5:                   l_tags.append("VOL SURGE")
                if swing_mode == "HIGH VOLUME" and hv_tier: l_tags.append(f"HV-{hv_tier}:{hv_score}")
                if swing_mode == "HIGH CONVICTION" and _hc_tag: l_tags.append(_hc_tag)
                # v14-patch: only flag Monday on actionable entries
                if is_monday and entry_quality in ("✅ BUY", "🔍 DISCOVERY BUY", "⚡ NEAR-MISS BUY"):
                    l_tags.append("⚠️MON")
                if combo_bonus > 0:             l_tags.append(f"COMBO+{combo_bonus:.0%}")
                if ninety_confidence_long:     l_tags.append("🎯90-CONFIDENCE")
                elif high_accuracy_long:        l_tags.append("🎯HIGH-ACCURACY")
                elif discovery_buy:             l_tags.append("🔍DISCOVERY-BUY")  # v14-patch
                elif display_prob >= 0.82:      l_tags.append("⚠️PROB-NO-GATE")
                if is_hk and not hk_participation_ok:
                    l_tags.append("HK-LOW-ACTIVITY")
                if next_day_score >= 9:         l_tags.append("🔥NEXT-DAY-A+")
                elif next_day_score >= 7:       l_tags.append("✅NEXT-DAY")
                elif next_day_score >= 5:       l_tags.append("👀NEXT-DAY-WATCH")
                if pre_mover_ready:             l_tags.append("⏳PRE-MOVER-A")
                elif pre_mover_watch:           l_tags.append("⏳PRE-MOVER-B")
                if explosion_ready:             l_tags.append("💥STYLE-EXPLOSIVE")
                elif explosion_watch:           l_tags.append("💥EXPLOSIVE-WATCH")
                l_tags.extend(strat_tags)
                # ── v15: High win-rate pattern tags ───────────────────────────
                if raw.get("nr7_setup"):        l_tags.append("📐NR7")
                if raw.get("inside_day"):       l_tags.append("🔲INSIDE DAY")
                if raw.get("failed_breakdown"): l_tags.append("🪤FAILED BRKDN")
                if raw.get("tight_flag"):       l_tags.append("🚩TIGHT FLAG")
                if raw.get("cup_handle"):       l_tags.append("🏆CUP+HANDLE")
                if pre_earnings_run:            l_tags.append(f"📅PRE-EARN({cal_days}d)")

                # ── v12: Options tags + smart targets + entry-tier downgrades ─
                opt_tags = []
                if opt_long.get("opt_unusual_call_flow"): opt_tags.append("🔥CALL FLOW")
                if opt_long.get("opt_call_skew_bullish"): opt_tags.append("📈CALL SKEW")
                if opt_long.get("opt_pc_volume_low"):     opt_tags.append("P/C↓")
                if opt_long.get("opt_iv_cheap"):          opt_tags.append("IV CHEAP")
                if opt_raw.get("term_inversion"):         opt_tags.append("⚠️IV INVERTED")
                if opt_raw.get("iv_rich"):                opt_tags.append("⚠️IV RICH")

                # If front-month IV is inverted, near-term event/fear is
                # priced in — downgrade a fresh ✅ BUY to 👀 WATCH.
                if opt_raw.get("term_inversion") and entry_quality == "✅ BUY":
                    entry_quality = "👀 WATCH"

                l_tags.extend(opt_tags)

                # Implied move (scaled to ~10 trading days) and "smart" TP
                # derived from it. Falls back to "–" when options data
                # is unavailable so the column behaviour is uniform.
                im_2w = opt_raw.get("implied_move_2w")
                if im_2w is not None and 0.005 <= im_2w <= 0.30:
                    implied_move_str = f"±{im_2w*100:.1f}%"
                    smart_tp_val     = round(p * (1 + max(im_2w, 0.05)), 2)
                    smart_tp_str     = f"${smart_tp_val:.2f}"
                else:
                    implied_move_str = "–"
                    smart_tp_str     = "–"

                ivr = opt_raw.get("iv_rank_proxy")
                iv_rank_str = f"{ivr:.2f}× RV" if ivr is not None else "–"

                # Stage 2 trade-plan context. Qualification remains pre-breakout;
                # these fields define the future entry trigger and risk controls.
                _s2_entry = float(raw.get("stage2_entry_price", raw.get("stage2_pivot", p)) or p)
                _s2_stop = float(raw.get("stage2_initial_stop", raw.get("stage2_handle_low", p)) or p)
                _s2_failed_exit = float(raw.get("stage2_failed_breakout_exit", raw.get("stage2_pivot", p)) or p)
                _s2_target = float(raw.get("stage2_target_price", p) or p)
                _s2_trail_trigger = float(raw.get("stage2_trail_trigger", p) or p)
                _s2_trail_stop = float(raw.get("stage2_trail_stop", p) or p)
                _s2_market_gate = "PASS" if regime == "BULL" else ("BLOCK" if regime == "BEAR" else "CHECK")
                if sec_name in green_set or raw.get("stage2_sector_lead"):
                    _s2_sector_gate = "PASS"
                elif sec_name in red_set:
                    _s2_sector_gate = "BLOCK"
                else:
                    _s2_sector_gate = "CHECK"
                if cal_days is None:
                    _s2_earnings_gate = "CHECK"
                    _s2_earnings_days = "UNKNOWN"
                elif 0 <= int(cal_days) <= 7:
                    _s2_earnings_gate = "BLOCK"
                    _s2_earnings_days = str(int(cal_days))
                else:
                    _s2_earnings_gate = "PASS"
                    _s2_earnings_days = str(int(cal_days))

                _s2_rvol_pace = float(vr)
                _s2_rvol_source = "DAILY PROXY"
                try:
                    if ticker in intraday_cache and not intraday_cache[ticker].empty:
                        _s2_intra = _clean_scan_ohlcv(intraday_cache[ticker])
                        _s2_last_date = pd.Timestamp(_s2_intra.index[-1]).date()
                        _s2_today_bars = _s2_intra[
                            [pd.Timestamp(x).date() == _s2_last_date for x in _s2_intra.index]
                        ]
                        if ticker.upper().endswith(".HK"):
                            _s2_expected_bars = 66
                        elif ticker.upper().endswith(".SI"):
                            _s2_expected_bars = 84
                        elif ticker.upper().endswith(".NS"):
                            _s2_expected_bars = 75
                        else:
                            _s2_expected_bars = 78
                        _s2_progress = min(1.0, max(len(_s2_today_bars) / max(_s2_expected_bars, 1), 0.10))
                        _s2_rvol_pace = min(20.0, float(vr) / _s2_progress)
                        _s2_rvol_source = "LIVE PROJECTED PACE"
                except Exception:
                    pass
                _s2_volume_gate = "PASS" if p >= _s2_entry and _s2_rvol_pace >= 1.5 else "WAIT"
                _s2_buy_trigger = f"Break ${_s2_entry:.2f} with >=1.5x {_s2_rvol_source.lower()}"
                _s2_exit_plan = (
                    f"Exit failed breakout <${_s2_failed_exit:.2f}; hard stop ${_s2_stop:.2f}; "
                    f"trail to ${_s2_trail_stop:.2f} after ${_s2_trail_trigger:.2f}; "
                    f"time stop Day {int(raw.get('stage2_time_stop_days', 5))}"
                )
                if early_rally_buy:
                    _er_phase = "CONFIRMED EARLY BUY"
                    _er_gate = "BUY GATE PASS"
                    _er_buy = "YES"
                elif early_rally_pullback_watch:
                    _er_phase = "MOVED ALREADY - WAIT PULLBACK"
                    _er_gate = "WAIT PULLBACK / RESET"
                    _er_buy = "NO"
                elif early_rally_trigger_watch:
                    _er_phase = "TRIGGER WATCH"
                    _er_gate = "WAIT FOR BREAKOUT + VOLUME"
                    _er_buy = "NO"
                elif early_rally_accum_watch:
                    _er_phase = "ACCUMULATION WATCH"
                    _er_gate = "WATCH ONLY"
                    _er_buy = "NO"
                else:
                    _er_phase = "NOT EARLY RALLY"
                    _er_gate = "FAIL"
                    _er_buy = "NO"
                _er_trigger = _s2_buy_trigger if raw.get("stage2_score", 0) else "Break pivot/recent high with >=1.5x volume; stop near support"
                if early_rally_pullback_watch:
                    _er_trigger = "Do not chase; wait for pullback, tight base, or reset near support"
                _er_why = (
                    f"Score={early_rally_score}; 5D={_recent_5d_pct:.1f}%; 20D={_recent_20d_pct:.1f}%; "
                    f"60D={_recent_60d_pct:.1f}%; 120D={_recent_120d_pct:.1f}%; "
                    f"Vol={vr:.2f}x; RR={rr_est:.1f}; Room={upside_to_resistance:.1f}%; "
                    f"BaseRoom={float(raw.get('stage2_post_pivot_room_pct', 0) or 0):.1f}%"
                )

                long_results.append({
                    "Ticker":         ticker,
                    "Sector":         sector_label(ticker),
                    "Action":         l_action,
                    "Setup Type":     (
                        support_zone if swing_mode == "SUPPORT ENTRY" else
                        pm_zone      if swing_mode == "PREMARKET MOMENTUM" else
                        hv_zone      if swing_mode == "HIGH VOLUME" else
                        _er_phase    if swing_mode == "EARLY RALLY FINDER" else
                        setup_type_long
                    ),
                    "PM Chg%":        f"+{pm_chg_pct:.1f}%" if pm_data_ok and pm_chg_pct > 0 else "–",
                    "PM Price":       f"${pm_price:.2f}" if pm_data_ok and pm_price > 0 else "–",
                    "Support Tier":   support_zone,
                    "Supp#":          support_tier,
                    "RSI Now":        round(rsi_now, 1),
                    "Entry Quality":  entry_quality,
                    "Next-Day Score": int(next_day_score),
                    "Quality Score": int(quality_score),
                    "Tradeable Buy": "YES" if tradeable_buy else "NO",
                    "Trade Tier": trade_tier,
                    "7-Star Score": int(seven_star_score),
                    "7-Star Tier": seven_star_tier,
                    "7-Star Why": seven_star_why,
                    "Pre-Mover Score": pre_mover_score,
                    "Pre-Mover Tier": pre_mover_tier,
                    "Pre-Mover Why": pre_mover_why,
                    "Explosion Score": explosion_score,
                    "Explosion Tier": explosion_tier,
                    "Explosion Why": explosion_why,
                    "Next-Day Rating": next_day_rating,
                    "Next-Day Move": f"{expected_7d_move:.1f}%",
                    "7D Move Est": f"{expected_7d_move:.1f}%",
                    "Upside to Res": f"{upside_to_resistance:.1f}%",
                    "RR Est": f"1:{rr_est:.1f}",
                    "Rise Prob":      f"{display_prob * 100:.1f}%",
                    "Prob Tier":      confidence_tier,
                    "90% Qualified":  "YES" if ninety_confidence_long else "NO",
                    "Score":          f"{l_score}/{len(long_sig)}",
                    "Operator":       raw.get("operator_label", "–"),
                    "Op Score":       str(raw.get("operator_score", 0)),
                    "VWAP":           "ABOVE" if raw.get("above_vwap") else "BELOW",
                    "Trap Risk":      raw.get("trap_risk_label", "–"),
                    "Today %":        f"{today_chg:+.2f}%",
                    "5D %":           f"{_recent_5d_pct:+.2f}%",
                    "20D %":          f"{_recent_20d_pct:+.2f}%",
                    "60D %":          f"{_recent_60d_pct:+.2f}%",
                    "120D %":         f"{_recent_120d_pct:+.2f}%",
                    "Price":          f"${p:.2f}",
                    "MA5":            f"${raw.get('ma5', p):.2f}",
                    "MA10":           f"${raw.get('ma10', p):.2f}",
                    "MA20":           f"${raw['ma20']:.2f}",
                    "MA5 Rising":     "YES" if raw.get("ma5_rising") else "NO",
                    "MA10 Rising":    "YES" if raw.get("ma10_rising") else "NO",
                    "MA5/10 Cross":   "BULL" if raw.get("ma5_cross_up_ma10") else "–",
                    "MA60 Stop":      f"${l_ma60_stop:.2f}",
                    "Best Stop":      f"${l_stop:.2f}",
                    "TP1 +10%":       f"${l_pt_short:.2f}",
                    "TP2 +15%":       f"${l_pt_swing1:.2f}",
                    "TP3 +20%":       f"${l_pt_swing2:.2f}",
                    "Smart TP":       smart_tp_str,
                    "Implied Move 2W": implied_move_str,
                    "IV vs RV":       iv_rank_str,
                    "Trail Stop":     f"${l_trail:.2f}",
                    "Time Stop":      l_time_stop,
                    "Pos/$1k risk":   int(1000 / l_risk) if l_risk > 0 else 0,
                    "Float":          float_str,
                    "Short %":        short_str,
                    "Signals":        " | ".join(l_tags) if l_tags else "–",
                    "Opt Flow":       " | ".join(opt_tags) if opt_tags else "–",
                    "RSI":            round(raw["rsi0"], 1),
                    "Vol Ratio":      round(vr, 2),
                    "Last Bar":       last_bar_ts,
                    "BB Squeeze":     "YES" if long_sig["bb_bull_squeeze"] else "–",
                    # ── v14: Pro Swing Setup columns ──────────────────────────
                    "PSS Score":      f"{raw.get('pss_score', 0)}/8",
                    "PSS Label":      raw.get("pss_label", "–"),
                    "PSS Triggers":   " · ".join(raw.get("pss_active", [])) or "–",
                    # Stage 1 -> Stage 2 base-breakout context
                    "Stage 2 Score":  int(raw.get("stage2_score", 0)),
                    "Early Score":    int(raw.get("stage2_early_score", 0)),
                    "Stage 2 Phase":  raw.get("stage2_phase", "NOT STAGE 2"),
                    "Base Weeks":     raw.get("stage2_base_weeks", 0),
                    "Base Range%":    raw.get("stage2_base_range_pct", 99.0),
                    "Contraction":    raw.get("stage2_contraction_ratio", 1.0),
                    "VDU Ratio":      raw.get("stage2_volume_dryup_ratio", 1.0),
                    "Pivot":          f"${raw.get('stage2_pivot', p):.2f}",
                    "Pivot Dist%":    f"{raw.get('stage2_pivot_distance_pct', 0.0):+.1f}%",
                    "Stage 2 Stop":   f"${raw.get('stage2_handle_low', p):.2f}",
                    "Stage 2 Risk%":  f"{raw.get('stage2_risk_pct', 99.0):.1f}%",
                    "Post-Pivot Room": f"{raw.get('stage2_post_pivot_room_pct', 0.0):.1f}%",
                    "Stage 2 Reward": f"{raw.get('stage2_breakout_reward_pct', 0.0):.1f}%",
                    "Stage 2 R:R":    f"1:{raw.get('stage2_breakout_rr', 0.0):.1f}",
                    "Stage 2 Entry":  f"${_s2_entry:.2f}",
                    "Stage 2 Target": f"${_s2_target:.2f}",
                    "Failed BO Exit": f"${_s2_failed_exit:.2f}",
                    "Stage 2 Hard Stop": f"${_s2_stop:.2f}",
                    "S2 Shares/$1k": int(raw.get("stage2_shares_per_1k_risk", 0)),
                    "S2 Time Stop": f"Day {int(raw.get('stage2_time_stop_days', 5))}",
                    "Market Regime": str(regime),
                    "Stage 2 Market Gate": _s2_market_gate,
                    "Stage 2 Sector Gate": _s2_sector_gate,
                    "Earnings Days": _s2_earnings_days,
                    "Earnings Gate": _s2_earnings_gate,
                    "S2 RVOL Pace": f"{_s2_rvol_pace:.2f}x",
                    "S2 RVOL Source": _s2_rvol_source,
                    "Stage 2 Volume Gate": _s2_volume_gate,
                    "Stage 2 Buy Trigger": _s2_buy_trigger,
                    "Stage 2 Exit Plan": _s2_exit_plan,
                    "Early Rally Score": early_rally_score,
                    "Early Rally Phase": _er_phase,
                    "Early Rally Gate": _er_gate,
                    "Early Rally Buy?": _er_buy,
                    "Early Rally Trigger": _er_trigger,
                    "Early Rally Why": _er_why,
                    "Early Rally Missing": early_rally_missing,
                    "Blue Sky":       "YES" if raw.get("stage2_blue_sky") else "NO",
                    "Flat Top Touches": int(raw.get("stage2_flat_top_touches", 0)),
                    "RS Lead":        "YES" if raw.get("stage2_rs_lead") else "NO",
                    "Sector Lead":    "YES" if raw.get("stage2_sector_lead") else "NO",
                    "EPS Rev 60D":    eps_revision_str,
                    "Stage 2 Why":    raw.get("stage2_why", "–"),
                    "Early Why":      raw.get("stage2_early_why", "–"),
                    # ── v14.1: Fundamental context ────────────────────────────
                    "Cash/MCap":      cash_floor_str,
                    "Analyst":        analyst_label,
                    "Pos Size":       display_pos_size_note,
                    "PSM Gate":       str(psm_min_score),
                    # ── v15.2: ATR% volatility quality ────────────────────────
                    "ATR%":           atr_pct_str,
                    "Vol Quality":    atr_vol_tag,
                })

            # ── SHORT ─────────────────────────────────────────────────────────
            s_score        = sum(v for k, v in short_sig.items() if v)
            s_regime_bonus = 0.08 if regime == "BEAR" else 0.03 if regime == "CAUTION" else 0
            s_prob_raw     = bayesian_prob(SHORT_WEIGHTS, short_sig, s_regime_bonus)
            s_prob         = round(max(0.35, min(0.95,
                             s_prob_raw - monday_penalty)), 4)
            s_top3         = (short_sig["stoch_overbought"] or
                              short_sig["bb_bear_squeeze"]  or
                              short_sig["macd_decel"])

            # ── HIGH-ACCURACY SHORT GATE ──────────────────────────────────────
            # Same idea as the long gate: high Fall Prob alone is not enough.
            # A true SELL needs bearish trend + breakdown/distribution volume +
            # no gap-down chase + no obvious short-squeeze risk.
            short_volume_confirmed = (
                short_sig.get("vol_breakdown", False) or
                short_sig.get("high_volume_down", False)
            )
            short_momentum_confirmed = (
                short_sig.get("macd_decel", False) or
                short_sig.get("stoch_overbought", False) or
                short_sig.get("rsi_cross_bear", False)
            )
            short_below_structure = short_sig.get("trend_bearish", False) or raw.get("below_vwap", False)
            short_distribution = short_sig.get("operator_distribution", False) or short_sig.get("high_volume_down", False)
            breakdown_setup = short_sig.get("vol_breakdown", False) and short_below_structure
            rollover_setup = short_sig.get("macd_decel", False) and (short_sig.get("lower_highs", False) or raw.get("below_vwap", False))
            setup_type_short = (
                "Breakdown" if breakdown_setup else
                "Distribution" if short_distribution else
                "Rollover" if rollover_setup else
                "Early Downtrend" if short_below_structure else
                "Mixed"
            )
            high_accuracy_short = (
                s_prob >= min_prob_strong_short and
                s_score >= min_score_strong_short and
                short_below_structure and
                (short_momentum_confirmed or short_volume_confirmed or short_distribution) and
                raw.get("today_chg_pct", 0) > (-8.0 if swing_mode != "STRICT" else -6.0) and
                raw.get("today_chg_pct", 0) < 3.0 and
                not squeeze_flag
            )
            actionable_short = (
                s_prob >= (0.62 if swing_mode == "DISCOVERY" else 0.66) and
                s_score >= 4 and short_below_structure and
                (breakdown_setup or rollover_setup or short_distribution or short_momentum_confirmed) and
                raw.get("today_chg_pct", 0) > -10.0 and
                not squeeze_flag
            )

            if high_accuracy_short:
                s_action = "STRONG SHORT"
            elif actionable_short:
                s_action = "WATCH SHORT – HIGH QUALITY"
            elif s_score >= min_score_strong_short and s_prob >= min_prob_strong_short and s_top3:
                s_action = "WATCH SHORT – HIGH QUALITY"
            elif s_score >= 4 and s_prob >= 0.58 and short_below_structure:
                s_action = "WATCH SHORT – DEVELOPING"
            elif s_score >= 3 and short_below_structure:
                s_action = "WATCH SHORT – EARLY"
            else:
                s_action = None

            if s_action:
                s_atr_stop   = round(p + 1.5 * atrv, 2)
                s_swing_stop = round(raw["last_swing_high"] * 1.005, 2)
                s_cover      = min(s_atr_stop, s_swing_stop)
                s_risk       = s_cover - p
                s_t1         = round(p - s_risk * 1.0, 2)
                s_t2         = round(p - s_risk * 2.0, 2)
                s_trail      = round(p - s_risk * 0.5, 2)

                s_tags = []
                if short_sig["stoch_overbought"]:  s_tags.append("STOCH ROLLOVER")
                if short_sig["bb_bear_squeeze"]:   s_tags.append("BB BEAR SQ")
                if short_sig["macd_decel"]:        s_tags.append("MACD DECEL")
                if short_sig["vol_breakdown"]:     s_tags.append("VOL BREAKDOWN")
                if short_sig["lower_highs"]:       s_tags.append("LOWER HIGHS")
                if short_sig["rsi_cross_bear"]:    s_tags.append("RSI<50")
                if short_sig["high_volume_down"]:  s_tags.append("DIST DAY")
                if high_accuracy_short:             s_tags.append("🎯HIGH-ACCURACY")
                elif s_prob >= 0.82:                s_tags.append("⚠️PROB-NO-GATE")
                if squeeze_flag:                    s_tags.append("⚡SQUEEZE-RISK")
                if is_monday:                       s_tags.append("⚠️MON")

                # ── v12: Options tags for short ───────────────────────────────
                opt_s_tags = []
                if opt_short.get("opt_unusual_put_flow"):  opt_s_tags.append("🔻PUT FLOW")
                if opt_short.get("opt_put_skew_bearish"):  opt_s_tags.append("📉PUT SKEW")
                if opt_short.get("opt_term_inversion"):    opt_s_tags.append("⚠️IV INVERTED")
                if opt_short.get("opt_pc_volume_high"):    opt_s_tags.append("P/C↑")
                if opt_raw.get("iv_rich"):                 opt_s_tags.append("⚠️IV RICH")
                s_tags.extend(opt_s_tags)

                # Implied move row data — same scaling as long branch
                im_2w_s = opt_raw.get("implied_move_2w")
                if im_2w_s is not None and 0.005 <= im_2w_s <= 0.30:
                    implied_move_str_s = f"±{im_2w_s*100:.1f}%"
                else:
                    implied_move_str_s = "–"
                ivr_s = opt_raw.get("iv_rank_proxy")
                iv_rank_str_s = f"{ivr_s:.2f}× RV" if ivr_s is not None else "–"

                # Short entry quality — mirror of long but for sell setups
                s_is_ideal   = short_sig["trend_bearish"] and raw.get("vol_declining", False) \
                               and not raw.get("ma60_stop_triggered", False)
                s_is_chasing = raw.get("today_chg_pct", 0) < -8.0   # gapped down >8%, avoid
                s_is_stopped = not short_sig["trend_bearish"] and raw.get("above_ma60", True)

                if s_is_stopped or squeeze_flag:
                    s_entry_quality = "🚫 AVOID"
                elif high_accuracy_short and (s_is_ideal or short_sig.get("operator_distribution", False) or breakdown_setup or rollover_setup):
                    s_entry_quality = "✅ SELL"
                elif actionable_short and not s_is_chasing:
                    s_entry_quality = "✅ SELL"
                elif s_is_chasing:
                    s_entry_quality = "⏳ WAIT"
                else:
                    s_entry_quality = "👀 WATCH"

                short_results.append({
                    "Ticker":         ticker,
                    "Sector":         sector_label(ticker),
                    "Action":         s_action,
                    "Setup Type":     setup_type_short,
                    "Entry Quality":  s_entry_quality,
                    "Fall Prob":      f"{s_prob * 100:.1f}%",
                    "Prob Tier":      prob_label(s_prob),
                    "Score":          f"{s_score}/{len(short_sig)}",
                    "Operator":       raw.get("operator_label", "–"),
                    "Op Score":       str(raw.get("operator_score", 0)),
                    "VWAP":           "ABOVE" if raw.get("above_vwap") else "BELOW",
                    "Trap Risk":      raw.get("trap_risk_label", "–"),
                    "Today %":        f"{today_chg:+.2f}%",
                    "Price":          f"${p:.2f}",
                    "Cover Stop":     f"${s_cover:.2f}",
                    "Target 1:1":     f"${s_t1:.2f}",
                    "Target 1:2":     f"${s_t2:.2f}",
                    "Implied Move 2W": implied_move_str_s,
                    "IV vs RV":       iv_rank_str_s,
                    "Trail Stop":     f"${s_trail:.2f}",
                    "Regime bonus":   "YES" if regime in ("BEAR","CAUTION") else "–",
                    "Float":          float_str,
                    "Short %":        short_str,
                    "RSI":            round(raw["rsi0"], 1),
                    "Vol Ratio":      round(vr, 2),
                    "Last Bar":       last_bar_ts,
                    "Signals":        " | ".join(s_tags) if s_tags else "–",
                    "Opt Flow":       " | ".join(opt_s_tags) if opt_s_tags else "–",
                })

        except Exception as e:
            scan_debug["ticker_errors"] += 1
            if len(scan_debug["ticker_error_samples"]) < 25:
                scan_debug["ticker_error_samples"].append({"ticker": ticker, "error": f"{type(e).__name__}: {e}"})
            try:
                _record_app_error("scan_ticker", e, ticker=ticker, extra={"index": i + 1, "total": total})
            except Exception:
                pass
        _scan_progress(i)

    status_text.empty()
    progress_bar.empty()

    def make_df(rows, prob_col):
        if not rows:
            return pd.DataFrame()
        df_out = pd.DataFrame(rows)
        df_out["_s"] = df_out[prob_col].astype(str).str.rstrip("%").astype(float)
        return df_out.sort_values("_s", ascending=False).drop(columns="_s")

    def make_op_df(rows):
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(rows).sort_values(
            ["_high_count", "_trap_count", "_op_score"],
            ascending=[False, False, False]
        )

    df_long_out = make_df(long_results, "Rise Prob")
    df_short_out = make_df(short_results, "Fall Prob")
    df_operator_out = make_op_df(operator_results)

    # timing checkpoint: signal loop (everything after meta prefetch)
    _t_now = _time_mod.perf_counter()
    scan_debug["timing"]["signal_loop_s"] = round(_t_now - _t_phase, 1)
    scan_debug["timing"]["total_s"]       = round(_t_now - _t_start, 1)

    scan_debug.update({
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "long_rows_raw": int(len(df_long_out)),
        "short_rows_raw": int(len(df_short_out)),
        "operator_rows_raw": int(len(df_operator_out)),
    })
    if df_long_out.empty and df_short_out.empty and df_operator_out.empty:
        scan_debug["empty_reason"] = (
            "No rows passed filters. Check: Yahoo returned data count, liquidity/ATR filter, "
            "min probability filters, market closed/flat sectors, and any ticker errors below."
        )
        try:
            _record_app_warning("fetch_analysis_empty", scan_debug["empty_reason"], extra=scan_debug)
        except Exception:
            pass
    try:
        st.session_state["last_scan_debug"] = scan_debug
    except Exception:
        pass
    globals()["_last_scan_debug_global"] = scan_debug
    return (df_long_out, df_short_out, df_operator_out)


# ─────────────────────────────────────────────────────────────────────────────
# DIAGNOSTICS  — v5 exact
# ─────────────────────────────────────────────────────────────────────────────
