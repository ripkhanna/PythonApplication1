"""Diagnostics Tab renderer.

Readable Streamlit tab code extracted from the original working monolith.
Each render function receives the main runtime globals as ``ctx`` and exposes
them to this module so the body behaves like it did in the single-file app.
"""

def _bind_runtime(ctx: dict) -> None:
    """Expose original app globals to this module for monolith-compatible tab code."""
    globals().update(ctx)

def render_diagnostics(ctx: dict) -> None:
    _bind_runtime(ctx)
    st.caption("🔍 Diagnostics")

    st.subheader("🧹 Cache Management")

    st.info(f"Cache folder: {CACHE_DIR.resolve()}")

    if st.button("🗑️ Clear scanner cache files"):
        try:
            # Clear Streamlit memory cache first
            st.cache_data.clear()

            errors = clear_scanner_cache(CACHE_DIR)

            if errors:
                st.warning("Some cache files could not be deleted:")
                st.code("\n".join(errors))
                st.info("Close VS Code/Visual Studio/File Explorer windows opened inside scanner_cache, then try again.")
            else:
                st.success("scanner_cache files cleared successfully.")
                st.rerun()

        except Exception as e:
            st.error(f"Could not clear scanner cache: {e}")

    st.markdown("**CSV cache refresh status**")
    _diag_meta = st.session_state.get("scan_cache_meta", {})
    _diag_timing = _cache_timing_info(_diag_meta, refresh_minutes) if _diag_meta else st.session_state.get("scan_cache_timing", _cache_timing_info({}, refresh_minutes))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Last cache refreshed", _diag_timing.get("saved_at", "No cache yet"))
    c2.metric("Cache age", _diag_timing.get("age_text", "–"))
    c3.metric("Refresh interval", _diag_timing.get("refresh_interval", "Off"))
    c4.metric("Next refresh", _diag_timing.get("next_refresh_in", "Auto refresh off"))
    st.caption(
        f"Next expected refresh/check time: **{_diag_timing.get('next_refresh_at', 'Auto refresh off')}** · "
        f"Cache folder: `{SCAN_CACHE_DIR}`"
    )
    if _diag_timing.get("is_due"):
        st.warning("Cache is due for refresh. With auto refresh ON, the next page reload will run a fresh scan and write new CSV files.")
    elif refresh_minutes:
        st.success("Cache refresh timer is active. The app reloads on the selected interval and refreshes if the cache is old enough.")
    else:
        st.info("Auto refresh is Off. Use 🚀 Scan to refresh the CSV cache manually, or enable 15/30 min refresh in the sidebar.")

    # ─────────────────────────────────────────────────────────────────────────
    # v13.31: Cache & directory diagnostics (moved from sidebar)
    # Self-contained read-only panel showing where files actually live, whether
    # the directory is writable, what's in it, and when the last save happened.
    # Useful when "I don't see cache files" or "scan results aren't sticking".
    # ─────────────────────────────────────────────────────────────────────────
    with st.expander("📦 Cache & directory diagnostics", expanded=False):
        _diag_cache_abs = SCAN_CACHE_DIR.resolve()
        col_a, col_b = st.columns([3, 1])
        with col_a:
            st.markdown(f"**Script directory:** `{_SCRIPT_DIR}`")
            st.markdown(f"**Cache directory (absolute):** `{_diag_cache_abs}`")
            st.markdown(f"**UI state file:** `{_UI_STATE_FILE.resolve()}`  \n"
                        f"`{'exists' if _UI_STATE_FILE.exists() else 'not yet created'}`")
            st.caption(
                "From v13.31 onward, files are anchored to the script's own "
                "directory. If you ran an older version, an unrelated "
                "`scanner_cache/` may exist next to wherever you launched "
                "Streamlit from — that one can be safely deleted."
            )
        with col_b:
            # Live writability probe so permission issues surface immediately
            _diag_writable = False
            _diag_probe_err = None
            try:
                SCAN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                _probe = SCAN_CACHE_DIR / ".write_probe"
                _probe.write_text("ok", encoding="utf-8")
                _probe.unlink(missing_ok=True)
                _diag_writable = True
            except Exception as _e:
                _diag_probe_err = f"{type(_e).__name__}: {_e}"
            if _diag_writable:
                st.success("✅ Writable")
            else:
                st.error(f"❌ Not writable\n\n`{_diag_probe_err}`")

        # Last save status — set inside _save_scan_cache after every scan
        _diag_last = st.session_state.get("scan_cache_last_save")
        if _diag_last:
            if _diag_last.get("ok"):
                st.markdown(
                    f"**Last successful save:** ✅ {_diag_last['saved_at']} · "
                    f"market **{_diag_last['market']}** · "
                    f"long rows **{_diag_last['long_rows']}** · "
                    f"short rows **{_diag_last['short_rows']}**"
                )
            else:
                st.error(f"**Last save FAILED:** market {_diag_last.get('market','?')} · "
                         f"`{_diag_last.get('error','?')}`")
        else:
            st.info("No save attempted yet in this session — click 🚀 Scan to create cache files.")

        # File listing — what's actually on disk right now
        _diag_existing = []
        try:
            for p in sorted(SCAN_CACHE_DIR.glob("*")):
                if p.is_file():
                    size_kb = p.stat().st_size / 1024
                    mtime = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                    _diag_existing.append({"File": p.name, "Size (KB)": round(size_kb, 1), "Modified": mtime})
        except Exception:
            pass
        if _diag_existing:
            st.markdown(f"**Files currently in cache ({len(_diag_existing)}):**")
            st.dataframe(pd.DataFrame(_diag_existing), hide_index=True, width="stretch")
        else:
            st.info(
                "📭 **No cache files yet.** Click 🚀 Scan to create them. "
                "After a successful scan you should see 4 files per market: "
                "`<m>_long_setups.csv`, `<m>_short_setups.csv`, "
                "`<m>_operator_activity.csv`, `<m>_scan_meta.json` "
                "(where `<m>` is `us`, `sgx`, or `india`)."
            )

        st.caption(
            "**Open this folder from a terminal:**  \n"
            f"• macOS: `open '{_diag_cache_abs}'`  \n"
            f"• Linux: `xdg-open '{_diag_cache_abs}'`  \n"
            f"• Windows (cmd): `explorer \"{_diag_cache_abs}\"`"
        )


    st.markdown("**App errors / Cloud diagnostics**")
    st.caption("Any caught scan, Yahoo/yfinance, cache, tab, or startup errors are stored here instead of silently failing.")

    e_col1, e_col2, e_col3 = st.columns([1, 1, 2])
    with e_col1:
        if st.button("🧹 Clear app error log", key="diag_clear_app_errors"):
            try:
                _clear_app_error_log()
                st.success("App error log cleared.")
                st.rerun()
            except Exception as e:
                st.error(f"Could not clear app error log: {e}")
    with e_col2:
        st.metric("Session errors", len(st.session_state.get("app_error_events", [])))
    with e_col3:
        try:
            st.caption(f"Log file: `{APP_ERROR_LOG_FILE.resolve()}`")
        except Exception:
            st.caption("Log file path unavailable")

    _session_events = list(st.session_state.get("app_error_events", []))
    _file_events = []
    try:
        _file_events = _read_app_error_log(200)
    except Exception:
        _file_events = []

    # Merge recent session + file events, de-duplicate by key, latest first
    _seen = set()
    _events = []
    for _ev in (_session_events + _file_events):
        _key = (_ev.get("time"), _ev.get("context"), _ev.get("ticker"), _ev.get("message"))
        if _key in _seen:
            continue
        _seen.add(_key)
        _events.append(_ev)
    _events = sorted(_events, key=lambda x: x.get("time", ""), reverse=True)[:100]

    if _events:
        _err_rows = []
        for _ev in _events:
            _err_rows.append({
                "Time": _ev.get("time", ""),
                "Level": _ev.get("severity", ""),
                "Context": _ev.get("context", ""),
                "Ticker": _ev.get("ticker", ""),
                "Type": _ev.get("type", ""),
                "Message": str(_ev.get("message", ""))[:300],
            })
        st.dataframe(pd.DataFrame(_err_rows), hide_index=True, width="stretch", height=220)
        with st.expander("Show latest error tracebacks / full details", expanded=False):
            for _ev in _events[:25]:
                st.markdown(f"**{_ev.get('time','')} · {_ev.get('context','')} · {_ev.get('ticker','')}**")
                st.write(_ev.get("message", ""))
                if _ev.get("extra"):
                    st.json(_ev.get("extra"))
                if _ev.get("traceback"):
                    st.code(_ev.get("traceback"))
                st.divider()
    else:
        st.success("No captured app errors in this session/log file.")

    st.markdown("**Scan debug summary**")
    _scan_dbg = st.session_state.get("last_scan_debug", {})
    if _scan_dbg:
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Tickers attempted", _scan_dbg.get("total_tickers", 0))
        d2.metric("Batch loaded", _scan_dbg.get("batch_loaded", 0))
        d3.metric("Ticker errors", _scan_dbg.get("ticker_errors", 0))
        d4.metric("Skipped liquidity", _scan_dbg.get("skipped_liquidity", 0))
        d5, d6, d7, d8 = st.columns(4)
        d5.metric("Skipped history", _scan_dbg.get("skipped_history", 0))
        d6.metric("Skipped earnings", _scan_dbg.get("skipped_earnings", 0))
        d7.metric("Raw long rows", _scan_dbg.get("long_rows_raw", 0))
        d8.metric("Raw short rows", _scan_dbg.get("short_rows_raw", 0))
        if _scan_dbg.get("empty_reason"):
            st.warning(_scan_dbg.get("empty_reason"))
        if _scan_dbg.get("batch_error"):
            st.error(f"Batch yfinance error: {_scan_dbg.get('batch_error')}")
        if _scan_dbg.get("ticker_error_samples"):
            st.caption("Ticker error samples")
            st.dataframe(pd.DataFrame(_scan_dbg.get("ticker_error_samples")), hide_index=True, width="stretch")
        with st.expander("Full scan debug JSON", expanded=False):
            st.json(_scan_dbg)
    else:
        st.info("No scan debug summary yet. Run 🚀 Scan to populate it.")

    st.markdown("**Stocks scanned in last scan**")
    if last_scanned_tickers:
        st.caption(
            f"Market: **{last_market}** · Universe: **{last_universe_source}** · "
            f"Count: **{len(last_scanned_tickers)}** · "
            f"Live: **{last_live_ticker_count}** · Existing: **{last_existing_ticker_count}**"
        )
        if last_market == "🇺🇸 US":
            st.caption(
                f"UUUU included: **{'YES' if 'UUUU' in last_scanned_tickers else 'NO'}** · "
                f"APP included: **{'YES' if 'APP' in last_scanned_tickers else 'NO'}**"
            )
        st.text_area(
            "Comma-separated scanned tickers",
            value=last_scanned_tickers_csv,
            height=120,
            key="diag_scanned_tickers_csv",
            disabled=True,
        )
    else:
        st.info("Run 🚀 Scan first to show the exact comma-separated list of stocks scanned.")

    st.markdown("**Logs / scan notes**")
    st.caption("These are UI-level diagnostics from the latest scan/session. They are not a separate file log.")
    diag_logs = []
    try:
        diag_logs.append(f"Market selected: {market_sel}")
        diag_logs.append(f"Market regime: {regime}")
        diag_logs.append(f"Universe source: {last_universe_source if last_universe_source else 'No scan yet'}")
        diag_logs.append(f"Scanned tickers: {len(last_scanned_tickers) if last_scanned_tickers else 0}")
        diag_logs.append(f"Live tickers used: {last_live_ticker_count}")
        diag_logs.append(f"Existing tickers used: {last_existing_ticker_count}")
        diag_logs.append(f"Long setups shown: {len(df_long) if isinstance(df_long, pd.DataFrame) else 0}")
        diag_logs.append(f"Short setups shown: {len(df_short) if isinstance(df_short, pd.DataFrame) else 0}")
        diag_logs.append(f"Operator activity rows: {len(df_operator) if isinstance(df_operator, pd.DataFrame) else 0}")
        _lt = st.session_state.get("scan_cache_timing", _cache_timing_info(st.session_state.get("scan_cache_meta", {}), refresh_minutes))
        diag_logs.append(f"Cache last refreshed: {_lt.get('saved_at', 'No cache yet')}")
        diag_logs.append(f"Cache age: {_lt.get('age_text', '–')}")
        diag_logs.append(f"Auto refresh interval: {_lt.get('refresh_interval', 'Off')}")
        diag_logs.append(f"Next refresh/check: {_lt.get('next_refresh_in', 'Auto refresh off')} at {_lt.get('next_refresh_at', 'Auto refresh off')}")
        diag_logs.append(f"Bucket-cap Bayesian: {'ON' if st.session_state.get('use_bucket_cap', True) else 'OFF'}")
        diag_logs.append("Trade Journal: removed from Trade Desk in v13.46; current build v13.53")
    except Exception as e:
        diag_logs.append(f"Diagnostics log build error: {e}")
    st.text_area(
        "Latest UI logs",
        value="\n".join(diag_logs),
        height=190,
        key="diag_latest_logs",
        disabled=True,
    )
    st.info("To see these logs in the UI: run Scan, open 🔍 Diagnostics, then read the 'Logs / scan notes' box above. For ticker-level reasons, enter a ticker below.")

    diag_input = st.text_input("Enter ticker(s)", placeholder="NVDA, TSLA, AMD")
    for t in [x.strip().upper() for x in diag_input.split(",") if x.strip()]:
        with st.expander(f"{t} — full condition breakdown", expanded=True):
            result = diagnose_ticker(t, regime)
            for k, v in result.items():
                if str(v) == "":
                    st.markdown(f"**{k}**")
                    continue
                ca, cb = st.columns([3, 5])
                ca.markdown(f"`{k}`")
                vs = str(v)
                if vs.startswith("PASS"):   cb.success(vs)
                elif vs.startswith("FAIL"): cb.error(vs)
                else:                       cb.write(vs)

