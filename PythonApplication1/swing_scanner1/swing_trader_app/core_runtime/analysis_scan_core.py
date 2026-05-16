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
        # v15.6: per-phase timing breakdown
        "timing": {
            "spy_sector_fetch_s":   0.0,
            "intraday_fetch_s":     0.0,
            "batch_ohlcv_s":        0.0,
            "meta_prefetch_s":      0.0,
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
        spy_raw = yf.download("SPY", period="1mo", interval="1d",
                              progress=False, auto_adjust=True)
        if isinstance(spy_raw.columns, pd.MultiIndex):
            spy_raw.columns = spy_raw.columns.get_level_values(0)
        spy_close_global = spy_raw["Close"].squeeze().ffill()
    except Exception:
        pass

    # ── Pre-fetch sector ETF closes for sector leader signal ─────────────────
    sector_etf_closes = {}
    try:
        etf_list = list(SECTOR_ETFS.values())
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
            raw_intraday = yf.download(
                all_tickers, period="1d", interval="5m",
                progress=False, group_by="ticker", threads=True, auto_adjust=True,
                prepost=True,
            )
            latest_bars = []
            for tkr in all_tickers:
                try:
                    idf = _extract_from_yf_batch(raw_intraday, tkr, len(all_tickers))
                    idf = _clean_scan_ohlcv(idf).dropna(how="all") if not idf.empty else pd.DataFrame()
                    if len(idf) >= 1 and "Close" in idf.columns and idf["Close"].notna().any():
                        intraday_cache[tkr] = idf
                        latest_bars.append(str(pd.Timestamp(idf.index[-1])))
                except Exception:
                    continue
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
        out = {}
        err = ""
        try:
            raw = yf.download(
                chunk if len(chunk) > 1 else chunk[0],
                period="3mo", interval="1d",  # 3mo is enough for 60d MA + all signals
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
                    if tkr in intraday_cache:
                        df_t = _overlay_intraday_daily(df_t, intraday_cache[tkr])
                    if len(df_t) >= 60:
                        out[tkr] = df_t
                except Exception:
                    continue
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        return out, err

    try:
        # Tune for Yahoo reliability: enough parallelism to avoid a 70s single
        # batch, but not so many connections that Yahoo starts throttling.
        if total >= 900:
            _chunk_size, _dl_workers = 225, 4
        elif total >= 400:
            _chunk_size, _dl_workers = 225, 3
        else:
            _chunk_size, _dl_workers = max(total, 1), 1

        _ticker_chunks = list(_chunks(all_tickers, _chunk_size))
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

    def _fetch_one_meta(t):
        result = {
            "cal_days": None, "float_shares": None,
            "short_pct": None, "pe": None,
            "pm_chg": 0.0, "pm_price": 0.0, "pm_ok": False,
            "cash_ratio":    None,
            "analyst_rec":   None,
            "industry":      "",
            "sector_detail": "",
            "quote_type":    "",   # "ETF" | "EQUITY" | ""
        }
        for _attempt in range(2):   # retry once on 401
            try:
                tkr_obj = (yf.Ticker(t, session=_shared_session)
                           if _shared_session else yf.Ticker(t))

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
        f"⚡ Pre-fetching meta for {len(all_tickers)} tickers "
        f"({_WORKERS} parallel workers)…"
    )
    try:
        with ThreadPoolExecutor(max_workers=_WORKERS) as _pool:
            _futs = {_pool.submit(_fetch_one_meta, t): t for t in all_tickers}
            _done = 0
            for _fut in _as_completed(_futs):
                _done += 1
                if _done % 50 == 0:
                    status_text.text(
                        f"⚡ Pre-fetching meta {_done}/{len(all_tickers)}…"
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

    # v15.8 speed: cap expensive option-chain HTTP calls during broad
    # master scans. Price/volume signals still run for the whole universe;
    # options are only additive and should not dominate scan time.
    _option_enrich_count = 0
    _max_option_enrich = 40 if total >= 700 else 80
    _skip_individual_fallback = bool(batch_cache) and total >= 200

    for i, ticker in enumerate(all_tickers):
        try:
            _scan_progress(i, f"Scanning {ticker} ({i+1}/{total})...")

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
                raw_ind = yf.download(ticker, period="6mo", interval="1d",
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

            long_sig, short_sig, raw = compute_all_signals(
                close, high, low, vol,
                spy_close=spy_close_global,
                sector_close=sec_close,
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

            # ── Float / short / PE — pre-fetched meta cache ──────────────────
            _m          = _meta_cache.get(ticker, {})
            float_shares = _m.get("float_shares")
            short_pct    = _m.get("short_pct")
            pe           = _m.get("pe")
            # v14.1: new fundamental fields
            cash_ratio   = _m.get("cash_ratio")     # totalCash/marketCap
            analyst_rec  = _m.get("analyst_rec")    # 1=Strong Buy … 5=Sell
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
            is_biotech   = (industry in _high_risk_industries or
                            "biotech" in industry.lower() or
                            "pharma"  in industry.lower())
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

            # Pre-extract the two scalars the HC block needs.
            # (The full support/PM variable block runs after HC, so we read
            # directly from raw{} here rather than waiting for that block.)
            rsi_now = float(raw.get("rsi0", 50) or 50)
            p_raw   = float(raw.get("p", 0) or p)

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
            ma200_now    = raw.get("e200", 0) or 0
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
                and 8.0 <= _today_chg_abs <= 70.0
                and l_prob >= 0.45
                and not false_breakout
                and not distribution_risk
            )
            high_accuracy_long = (
                _earn_momentum_long
                or (
                    l_prob >= min_prob_strong_long and
                    l_score >= min_score_strong_long and
                    raw.get("above_ma60", False) and
                    raw.get("not_limit_up", False) and
                    raw.get("today_chg_pct", 99) < (8 if swing_mode != "DISCOVERY" else 10) and
                    not major_trap_risk and
                    core_long_trend and
                    momentum_confirmed and
                    (volume_confirmed or operator_or_vwap or pullback_setup)
                )
            )
            actionable_long = (
                l_prob >= (0.66 if swing_mode == "DISCOVERY" else 0.70) and
                l_score >= (4 if swing_mode == "DISCOVERY" else 5) and
                raw.get("above_ma60", False) and
                not major_trap_risk and
                core_long_trend and
                (pullback_setup or breakout_setup or continuation_setup or operator_or_vwap)
            )

            if swing_mode == "SUPPORT ENTRY":
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
                elif major_trap_risk:
                    entry_quality = "⏳ WAIT"
                elif _earn_momentum_long:
                    entry_quality = "✅ BUY"
                elif high_accuracy_long and (is_ideal_dip or is_vol_surge or long_sig.get("pocket_pivot", False) or long_sig.get("vol_breakout", False) or continuation_setup):
                    entry_quality = "✅ BUY"
                elif actionable_long and not is_chasing:
                    entry_quality = "✅ BUY"
                elif is_chasing:
                    entry_quality = "⏳ WAIT"
                else:
                    entry_quality = "👀 WATCH"

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
                if is_monday:                   l_tags.append("⚠️MON")
                if combo_bonus > 0:             l_tags.append(f"COMBO+{combo_bonus:.0%}")
                if high_accuracy_long:          l_tags.append("🎯HIGH-ACCURACY")
                elif l_prob >= 0.82:            l_tags.append("⚠️PROB-NO-GATE")
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

                long_results.append({
                    "Ticker":         ticker,
                    "Sector":         sector_label(ticker),
                    "Action":         l_action,
                    "Setup Type":     (
                        support_zone if swing_mode == "SUPPORT ENTRY" else
                        pm_zone      if swing_mode == "PREMARKET MOMENTUM" else
                        hv_zone      if swing_mode == "HIGH VOLUME" else
                        setup_type_long
                    ),
                    "PM Chg%":        f"+{pm_chg_pct:.1f}%" if pm_data_ok and pm_chg_pct > 0 else "–",
                    "PM Price":       f"${pm_price:.2f}" if pm_data_ok and pm_price > 0 else "–",
                    "Support Tier":   support_zone,
                    "Supp#":          support_tier,
                    "RSI Now":        round(rsi_now, 1),
                    "Entry Quality":  entry_quality,
                    "Rise Prob":      f"{l_prob * 100:.1f}%",
                    "Prob Tier":      prob_label(l_prob),
                    "Score":          f"{l_score}/{len(long_sig)}",
                    "Operator":       raw.get("operator_label", "–"),
                    "Op Score":       str(raw.get("operator_score", 0)),
                    "VWAP":           "ABOVE" if raw.get("above_vwap") else "BELOW",
                    "Trap Risk":      raw.get("trap_risk_label", "–"),
                    "Today %":        f"{today_chg:+.2f}%",
                    "Price":          f"${p:.2f}",
                    "MA20":           f"${raw['ma20']:.2f}",
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
                    # ── v14.1: Fundamental context ────────────────────────────
                    "Cash/MCap":      cash_floor_str,
                    "Analyst":        analyst_label,
                    "Pos Size":       pos_size_note,
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
                    "Signals":        " | ".join(l_tags) if l_tags else "–",
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
        _scan_progress(i, force=True)

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
    return (df_long_out, df_short_out, df_operator_out)


# ─────────────────────────────────────────────────────────────────────────────
# DIAGNOSTICS  — v5 exact
# ─────────────────────────────────────────────────────────────────────────────
