"""
Swing Scanner v13.83 — Bayesian Ensemble
====================================================================
Architecture : v7  (batch download, sector heatmap, FD holdings, fast scan)
Signal logic : v5  (compute_all_signals, bayesian_prob, action tiers)
v11 add-ons  : weekly trend, earnings guard, regime-adjusted thresholds
v12 add-ons  : options-derived signals — call/put unusual flow, IV term
               structure, 10% OTM skew, P/C volume, IV vs RV regime,
               ATM-straddle implied move (informs Smart TP and downgrades
               fresh BUYs to WATCH on front-month IV inversion).
               Backends:
                 • US tickers     → yfinance Ticker.options
                 • India .NS F&O  → nsepython (only ~200 stocks)
                 • SGX            → no options market exists, layer skipped

Install:
  pip install financedatabase ta streamlit yfinance pandas numpy nsepython requests streamlit-autorefresh
"""
# v13.83: Python 3.14+ uses PEP 649 lazy annotation evaluation, which trips
# NotImplementedError from __annotate__ when @st.cache_data wraps functions
# with bare unsubscripted generics like `-> tuple`. This `from __future__`
# downgrades all annotations in this module to strings at parse time,
# bypassing __annotate__ entirely. Annotations here are documentation only.
from __future__ import annotations

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import ta
import json
from pathlib import Path
import streamlit.components.v1 as components
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os
import stat
import shutil
from pathlib import Path
import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Swing Scanner v13.83",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Mobile-responsive CSS ─────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Global font size reduction ───────────────────────────────── */
.stMarkdown, .stDataFrame, .stAlert, .stCaption,
.stRadio, .stCheckbox, .stSlider, .stSelectbox,
.stTextInput, .stButton, .stExpander { font-size: 12px !important; }

/* ── Top padding: give room for title ─────────────────────────── */
.block-container {
    padding-top: 3.0rem !important;
    padding-bottom: 0.5rem !important;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
    max-width: 100% !important;
}

/* ── Title / headers smaller ──────────────────────────────────── */
h1 { font-size: 1.4rem !important; font-weight: 700 !important; margin: 0 0 4px !important; text-align: center !important; }
h2 { font-size: 0.9rem !important; margin: 0 0 2px !important; }
h3 { font-size: 0.85rem !important;margin: 2px 0 !important; }
p, .stMarkdown p { font-size: 11px !important; margin: 2px 0 !important; }

/* ── Metrics compact ──────────────────────────────────────────── */
[data-testid="metric-container"] {
    padding: 3px 6px !important;
    border-radius: 4px !important;
}
[data-testid="metric-container"] label {
    font-size: 9px !important;
    line-height: 1.1 !important;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: 13px !important;
    line-height: 1.2 !important;
}
[data-testid="metric-container"] [data-testid="stMetricDelta"] {
    font-size: 9px !important;
}

/* ── Tabs compact ─────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    gap: 1px !important;
    flex-wrap: wrap !important;
}
.stTabs [data-baseweb="tab"] {
    font-size: 10px !important;
    padding: 3px 8px !important;
    min-width: 0 !important;
    height: auto !important;
}

/* ── Dataframe smaller text ───────────────────────────────────── */
.stDataFrame {
    font-size: 11px !important;
    overflow-x: auto !important;
}
.stDataFrame th { font-size: 10px !important; padding: 2px 6px !important; }
.stDataFrame td { font-size: 11px !important; padding: 2px 6px !important; }

/* ── Buttons compact ──────────────────────────────────────────── */
.stButton button {
    font-size: 11px !important;
    padding: 4px 10px !important;
    height: auto !important;
}

/* ── Inputs compact ───────────────────────────────────────────── */
.stTextInput input, .stSelectbox select,
.stMultiSelect div[data-baseweb] {
    font-size: 11px !important;
    min-height: 28px !important;
}

/* ── Radio horizontal tight ───────────────────────────────────── */
.stRadio > div {
    gap: 6px !important;
    flex-wrap: wrap !important;
}
.stRadio label { font-size: 11px !important; }

/* ── Caption / info / warning smaller ────────────────────────── */
.stAlert { padding: 4px 8px !important; font-size: 11px !important; }
.stAlert p { font-size: 11px !important; margin: 0 !important; }
[data-testid="stCaptionContainer"] { font-size: 10px !important; }

/* ── Sidebar compact ──────────────────────────────────────────── */
[data-testid="stSidebar"] .block-container {
    padding-top: 0.5rem !important;
}
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stCheckbox label,
[data-testid="stSidebar"] .stSlider label {
    font-size: 11px !important;
}

/* ── Expander compact ─────────────────────────────────────────── */
.streamlit-expanderHeader {
    font-size: 11px !important;
    padding: 4px 8px !important;
}
.streamlit-expanderContent { padding: 4px 8px !important; }

/* ── Remove default element spacing ──────────────────────────── */
div[data-testid="stVerticalBlock"] > div {
    gap: 0.2rem !important;
}

/* ── Mobile ───────────────────────────────────────────────────── */
@media (max-width: 768px) {
    /* Mobile browser + Streamlit toolbar can cover the first lines.
       Keep a larger top padding so the title is never hidden. */
    .block-container {
        padding-top: 4.2rem !important;
        padding-left: 0.4rem !important;
        padding-right: 0.4rem !important;
        padding-bottom: 0.3rem !important;
    }
    h1 {
        font-size: 1.05rem !important;
        line-height: 1.25 !important;
        white-space: normal !important;
        overflow: visible !important;
        text-align: left !important;
        margin-top: 0 !important;
        margin-bottom: 0.15rem !important;
    }
    [data-testid="stCaptionContainer"] { font-size: 0.78rem !important; }
    .stTabs [data-baseweb="tab"] { font-size: 9px !important; padding: 2px 5px !important; }
    .stButton button { width: 100% !important; }
    [data-testid="metric-container"] [data-testid="stMetricValue"] { font-size: 12px !important; }
}



/* ── Top scan-status spinner ───────────────────────────────────── */
.top-scan-box {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 10px;
    margin: 4px 0 8px 0;
    border-radius: 8px;
    background: rgba(49, 130, 206, 0.12);
    border: 1px solid rgba(49, 130, 206, 0.35);
    color: inherit;
    font-size: 12px;
    line-height: 1.35;
}
.top-scan-spinner {
    width: 15px;
    height: 15px;
    min-width: 15px;
    border: 2px solid rgba(49, 130, 206, 0.25);
    border-top-color: #3182ce;
    border-radius: 50%;
    animation: topScanSpin 0.8s linear infinite;
}
@keyframes topScanSpin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
}
@media (max-width: 768px) {
    .top-scan-box {
        position: sticky;
        top: 0;
        z-index: 999;
        font-size: 11px;
        padding: 7px 8px;
    }
}

/* Title uses native Streamlit elements so it remains visible on mobile. */

</style>
""", unsafe_allow_html=True)

st.title("📈 Swing/Long Term Scanner v13.83")

# v13.83: COMPACT SELF-STAMP
# The build identity (path, mtime, hash, size) is still computed so it can
# self-prove the running file, but only the short hash and mtime are visible
# in the caption. The full path and size are tucked into the tooltip — hover
# the caption to see them — so the page header stays compact.
try:
    import hashlib
    _src_path = Path(__file__).resolve()
    _src_mtime = datetime.fromtimestamp(_src_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    _src_hash = hashlib.sha256(_src_path.read_bytes()).hexdigest()[:8]
    _src_size = _src_path.stat().st_size
    st.caption(
        f"Bayesian Ensemble · build `{_src_hash}` · {_src_mtime}",
        help=f"Running file: {_src_path}\nSize: {_src_size:,} bytes\n"
             f"Full SHA-256 prefix: {_src_hash}\n\n"
             f"Hover this caption to verify which file Streamlit loaded. "
             f"To compare against your file on disk:\n"
             f"  PowerShell: Get-FileHash '{_src_path.name}' -Algorithm SHA256",
    )
except Exception as _e:
    st.caption(f"Bayesian Ensemble · build 2026-05-04 "
               f"(stamp failed: {type(_e).__name__})")


# ─────────────────────────────────────────────────────────────────────────────
# EXTRACTED CORE RUNTIME SECTIONS
# ─────────────────────────────────────────────────────────────────────────────
# The original working monolith kept constants, cache, signal engine, market
# data, options, scan, event, trade-desk, strategy and long-term helper
# functions in this file. They now live under swing_trader_app/core_runtime/.
#
# They are executed into this module's globals instead of imported normally so
# functions see the exact same global namespace they had in the original
# single-file app. This preserves behavior while making app_runtime.py smaller.
from pathlib import Path as _RuntimePath

def _load_runtime_piece(relative_path: str) -> None:
    _piece_path = _RuntimePath(__file__).resolve().parent / relative_path
    try:
        _code = _piece_path.read_text(encoding="utf-8")
        exec(compile(_code, str(_piece_path), "exec"), globals())
    except Exception as _e:
        try:
            if "_record_app_error" in globals():
                _record_app_error("load_runtime_piece", _e, extra={"piece": relative_path, "path": str(_piece_path)})
        except Exception:
            pass
        raise

for _runtime_piece in [
    "core_runtime/cache_core.py",
    "core_runtime/config_core.py",
    "core_runtime/table_utils_core.py",
    "core_runtime/market_data_core.py",
    "core_runtime/signals_core.py",
    "core_runtime/options_core.py",
    "core_runtime/universe_core.py",
    "core_runtime/analysis_scan_core.py",
    "core_runtime/diagnose_core.py",
    "core_runtime/event_core.py",
    "core_runtime/swing_picks_core.py",
    "core_runtime/trade_desk_core.py",
    "core_runtime/strategy_core.py",
    "core_runtime/long_term_core.py",
    "core_runtime/cache_management_core.py",
]:
    _load_runtime_piece(_runtime_piece)

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
# v13.9: PERSISTENT UI STATE
# Every sidebar widget binds to st.session_state via a stable `key=` and
# defaults are pre-seeded in one block below. This guarantees user changes
# survive every rerun, including cache-clear reruns, until the user
# explicitly resets them or restarts the Streamlit server.
#
# v13.31: DISK PERSISTENCE — settings now also survive browser reloads,
# server restarts, and new tabs. On first widget render of each session we
# overlay any saved values from ui_state.json on top of the factory defaults.
# After the sidebar finishes rendering, we write the current state back if
# anything changed. Crucially this is the same script-anchored directory as
# the CSV cache, so it lives next to the .py file and never gets lost.
#
# Pattern: widgets must NOT use both `key=` and `value=` — Streamlit
# deprecates that and the value parameter is silently ignored. The correct
# pattern is to seed defaults into session_state once, then pass key= only.
# ─────────────────────────────────────────────────────────────────────────────
_SIDEBAR_DEFAULTS = {
    # Top-of-page market selector (lives outside sidebar but persisted here)
    "market_selector":        "🇺🇸 US",
    # Scan settings
    "ui_top_n_sectors":       3,
    "ui_min_prob_long":       62,
    "ui_min_prob_short":      60,
    "ui_swing_mode":          "Balanced",  # Options: Strict/Balanced/Discovery/Support Entry/Premarket Momentum/High Volume/High Conviction/PSM Strategy
    "ui_skip_earnings":       False,
    "ui_use_live_universe":   True,
    "ui_max_live_universe":   1000,   # v15.9: reduced from 1000 — 350 is fast, 1000 scans 1200+ tickers
    "ui_always_include":      "",
    # Options layer
    "ui_enable_options":      False,
    "ui_opt_required":        False,
    # Bayesian / engine controls
    "ui_use_bucket_cap":      True,
    # Long filters
    "ui_req_stoch":           False,
    "ui_req_bb":              False,
    "ui_req_accel":           False,
    # Short filters
    "ui_req_s_stoch":         False,
    "ui_req_s_bb":            False,
    "ui_req_s_decel":         False,
    # Misc
    "ui_load_csv_on_start":   True,
    "ui_refresh_choice":      "15 min",
}

# Disk-backed persistence: load saved settings once per session
_UI_STATE_FILE = SCAN_CACHE_DIR / "ui_state.json"

def _load_ui_state() -> dict:
    """Load saved UI state from disk. Returns empty dict on any error."""
    try:
        if _UI_STATE_FILE.exists():
            return json.loads(_UI_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}

def _save_ui_state(state_dict: dict) -> None:
    """Save UI state to disk. Silent on error to avoid breaking the app."""
    try:
        _UI_STATE_FILE.write_text(
            json.dumps(state_dict, indent=2, default=str), encoding="utf-8"
        )
    except Exception:
        pass

# Once per session: seed defaults, then overlay saved overrides
if not st.session_state.get("_ui_state_loaded"):
    _saved = _load_ui_state()
    for _k, _v in _SIDEBAR_DEFAULTS.items():
        # Saved value takes precedence over factory default
        st.session_state[_k] = _saved.get(_k, _v)
    st.session_state["_ui_state_loaded"] = True
    # Track baseline so we can detect changes
    st.session_state["_ui_state_baseline"] = {
        _k: st.session_state.get(_k) for _k in _SIDEBAR_DEFAULTS
    }
else:
    # On every subsequent rerun, just ensure defaults exist for any keys
    # that might have been deleted (e.g. by Reset)
    for _k, _v in _SIDEBAR_DEFAULTS.items():
        if _k not in st.session_state:
            st.session_state[_k] = _v

st.sidebar.header("Scan settings")

# v13.9: One-click reset for users who want defaults back, plus cache-status
# diagnostic panel so the user can SEE whether scanner_cache/*.csv are
# being written and where.
with st.sidebar.expander("⚙️ UI settings · save & reset", expanded=False):
    if st.button("↩️ Reset all sidebar settings to defaults",
                 key="ui_reset_btn",
                 help="Reverts all sidebar controls to factory defaults AND "
                      "deletes the saved ui_state.json from disk. Does not "
                      "affect ML models, calibrated weights, or scan results.",
                 width="stretch"):
        for _k, _v in _SIDEBAR_DEFAULTS.items():
            st.session_state[_k] = _v
        # v13.31: also delete the on-disk file, otherwise the next rerun
        # would re-load the old saved values and the reset would silently
        # not stick.
        try:
            _UI_STATE_FILE.unlink(missing_ok=True)
        except Exception:
            pass
        st.session_state["_ui_state_baseline"] = dict(_SIDEBAR_DEFAULTS)
        st.rerun()
    st.caption(
        f"Settings persist across reruns, browser reloads, and server "
        f"restarts via `{_UI_STATE_FILE.name}` next to the script. "
        f"Click reset above to clear both memory and disk state."
    )

# v13.31: Cache & directory diagnostics moved to the 🔍 Diagnostics tab.
# This block previously lived in the sidebar; it's now merged with the
# existing CSV cache refresh block in the Diagnostics tab so all
# cache/storage-related signals are in one place.

top_n_sectors  = st.sidebar.slider(
    "Top N green/red sectors to scan", 1, 6, key="ui_top_n_sectors",
)
min_prob_long  = st.sidebar.slider(
    "Min LONG rise prob (%)",  40, 95, key="ui_min_prob_long",
)
min_prob_short = st.sidebar.slider(
    "Min SHORT fall prob (%)", 40, 95, key="ui_min_prob_short",
)
swing_mode = st.sidebar.selectbox(
    "📊 Swing strategy",
    ["Strict", "Balanced", "Discovery", "Support Entry", "Premarket Momentum", "High Volume", "High Conviction", "PSM Strategy"],
    key="ui_swing_mode",
    help=(
        "**Strict** — A+ setups only. High probability + full confirmation.\n\n"
        "**Balanced** — practical live candidates (default). Trend + volume + operator.\n\n"
        "**Discovery** — wider watchlist for quiet markets. More results, use Trade Desk to filter.\n\n"
        "**Support Entry** ⭐ — shows ONLY stocks sitting AT a known support level "
        "(MA20/MA60/VWAP/swing low) that haven't moved much yet. Best for morning scans. "
        "Stop is tight (just below support). Stocks already up >3% today are hidden.\n\n"
        "**Premarket Momentum** 🚀 — shows stocks with +1%–+8% pre-market gain AND "
        "a sound technical trend. Designed for the 15–30 min before market open. "
        "Stocks without pre-market data or with broken technicals are filtered out.\n\n"
        "**High Volume** 📊 — shows stocks with unusual volume / volume breakout / pocket pivot. "
        "Best for finding stocks where activity is increasing now.\n\n"
        "**High Conviction** 🎯 — highest win-rate strategy. Shows ONLY stocks where ALL 5 "
        "independent signal categories confirm simultaneously: Trend + Momentum + Volume + "
        "Structure + Market alignment. Gives 5-15 stocks instead of 40-80. "
        "Each pick has genuine multi-dimensional confirmation.\n\n"
        "**PSM Strategy** 🚀 — 5–7 day hold targeting ≥5% gain. Quality-first swing filter using "
        "PI Proxy, PSS Score, Rise Probability, Volume Ratio and Entry Quality. "
        "Elite/Strong picks are designed to be fewer and higher quality, while Watch keeps developing setups visible."
    ),
)
st.session_state["swing_mode"] = swing_mode

# When strategy changes, DO NOT call Yahoo again.
# We only re-filter the cached master scan and refresh the visible grid.
_prev_mode_seen = st.session_state.get("_last_seen_swing_mode")
if _prev_mode_seen is not None and _prev_mode_seen != swing_mode:
    st.session_state["_strategy_changed_notice"] = (
        f"🔄 Strategy changed from **{_prev_mode_seen}** to **{swing_mode}** — "
        "grid refreshed from cached Yahoo data. No Yahoo download needed."
    )
    st.session_state["_force_strategy_refilter"] = True
    st.session_state.pop("_loaded_csv_cache_key", None)
st.session_state["_last_seen_swing_mode"] = swing_mode

# Show strategy context banner under the selectbox
_sm_upper = swing_mode.upper()
if _sm_upper == "SUPPORT ENTRY":
    st.sidebar.info(
        "📍 **Support Entry mode**\n\n"
        "Shows only stocks AT support (MA20/MA60/VWAP/swing low). "
        "Stocks already up >3% today are hidden. "
        "Tier 1 = MA60 dip (strongest). Tier 4 = VWAP dip."
    )
elif _sm_upper == "PREMARKET MOMENTUM":
    st.sidebar.info(
        "🚀 **Premarket Momentum mode**\n\n"
        "Shows stocks with +1–8% pre-market gain + technical trend intact. "
        "Run this 15–30 min before market open for best results. "
        "Tier A = +3–8% (high conviction). Tier B = +1–3% (needs confirmation)."
    )
elif _sm_upper == "HIGH VOLUME":
    st.sidebar.info(
        "📊 **High Volume mode**\n\n"
        "Shows stocks with unusual volume, volume breakout, pocket pivot, or strong close on rising volume. "
        "This is useful for finding names where activity is increasing before price fully moves."
    )
elif _sm_upper == "HIGH CONVICTION":
    st.sidebar.info(
        "🎯 **High Conviction mode**\n\n"
        "Requires ALL 5 signal categories simultaneously:\n"
        "📈 Trend  ⚡ Momentum  🔊 Volume  🏗️ Structure  🌍 Market alignment\n\n"
        "The grid can still show all High Conviction candidates, but the Long Setups tab now "
        "shows a ranked Top Swing Buys panel above the grid so you know which names to focus on first."
    )
    st.sidebar.slider(
        "Top Swing Buys to show",
        min_value=3,
        max_value=25,
        value=int(st.session_state.get("ui_hc_top_n", 10)),
        step=1,
        key="ui_hc_top_n",
        help=(
            "Only affects the High Conviction display panel. It does not change the scanner logic "
            "or any other strategy."
        ),
    )
elif _sm_upper == "PSM STRATEGY":
    st.sidebar.info(
        "🚀 **PSM Strategy mode**\n\n"
        "Targets 5–7 day holds with ≥5% gain. Filters for stocks where ≥3 of 8 "
        "professional sub-signals confirm:\n"
        "🔹 PEAD (post-earnings drift)  🔹 Volume Dry-Up coil\n"
        "🔹 Flat Base (IBD 3-week tight)  🔹 Market-Weakness RS\n"
        "🔹 Institutional Accumulation Days  🔹 Power Trend\n"
        "🔹 Short-Squeeze Proxy  🔹 Catalyst Proxy\n\n"
        "PSS Score (e.g. 4/8) shown per stock. Elite ≥6 / Strong 4–5 / Valid 3."
    )
    st.sidebar.slider(
        "Top PSM picks to show",
        min_value=5,
        max_value=30,
        value=int(st.session_state.get("ui_psm_top_n", 15)),
        step=1,
        key="ui_psm_top_n",
        help="Controls how many ranked picks appear in the PSM Strategy panel. Does not affect scanner logic.",
    )
    st.sidebar.text_input(
        "PSM compare shortlist",
        value=st.session_state.get("ui_psm_compare_tickers", ""),
        key="ui_psm_compare_tickers",
        placeholder="Example: GRND, IREN, ATLC, KOP, ROAD, VPG",
        help=(
            "Optional. Paste tickers here when you want Rank/View/Buy Condition to be calculated "
            "only against your own shortlist. This is how to match a manual Monday comparison, "
            "instead of ranking against the full market PSM list."
        ),
    )
skip_earnings  = st.sidebar.checkbox(
    "Skip earnings within 7 days", key="ui_skip_earnings",
)
use_live_universe = st.sidebar.checkbox(
    "Use live market universe",
    key="ui_use_live_universe",
    help="When ON, the scanner and Operator Activity tab fetch the market universe "
         "from live/public market sources first (Yahoo movers + index constituents, "
         "SGX securities feed, NSE index API), then merges them with the full existing "
         "curated ticker list. Tickers in 'Always include tickers' are also forced in. "
         "This means stocks like UUUU/APP remain scanned even if they are not in today's movers.",
)
max_live_universe = st.sidebar.slider(
    "Max live stocks to scan", 50, 1000, step=25,
    key="ui_max_live_universe",
    help=(
        "Controls the live/Yahoo universe size. "
        "350 = fast (10-20s, recommended). "
        "1000 = slow (60-120s). "
        "Curated + always-include tickers are always added on top."
    ),
)
always_include_text = st.sidebar.text_area(
    "Always include tickers",
    key="ui_always_include",
    height=68,
    help="Comma- or line-separated tickers always scanned in every scan. "
         "Replaces the old 'Add tickers' field — same effect, one place. "
         "Example: UUUU, APP, NVDA, D05.SI, HIMS, NVTS",
)
always_include_tickers = [
    t.strip().upper()
    for t in always_include_text.replace("\n", ",").split(",")
    if t.strip()
]
# If the always-include list changed since the last scan, clear the CSV cache
# key so the next rerun (or Scan click) triggers a fresh scan with the new tickers.
_prev_always = st.session_state.get("_last_always_include", [])
if sorted(always_include_tickers) != sorted(_prev_always):
    st.session_state["_last_always_include"] = list(always_include_tickers)
    if always_include_tickers or _prev_always:   # only invalidate if something actually changed
        st.session_state.pop("_loaded_csv_cache_key", None)
        if always_include_tickers:
            st.sidebar.info(
                f"📌 Always-include changed — "
                f"**{', '.join(always_include_tickers)}** will be added on next **🚀 Scan**."
            )
enable_options = st.sidebar.checkbox(
    "Use options data (US + India F&O, +30–60s)",
    key="ui_enable_options",
    help="Adds call/put flow, IV term structure, skew, and implied-move "
         "signals on top of the technical Bayesian engine. "
         "US tickers use yfinance; Indian .NS tickers use nsepython "
         "(only F&O-listed stocks have option chains). SGX has no liquid "
         "single-stock options market and is skipped automatically. "
         "After toggling this, you must click 🚀 Scan again — results are "
         "only recomputed on Scan, not on checkbox change.",
)
# v12: When the toggle flips, invalidate ONLY fetch_analysis' cache so the
# next Scan click is guaranteed fresh. Other caches (sectors, holdings,
# regime) are untouched.
_prev_opt = st.session_state.get("_prev_enable_options")
if _prev_opt is not None and _prev_opt != enable_options:
    try:
        fetch_analysis.clear()
    except Exception:
        pass
st.session_state["_prev_enable_options"] = enable_options

# v12: Hard filter — when ON, only show stocks that fired ≥1 option signal.
# This is the surefire way to make the toggle's effect unmistakable: turn it
# on with the main toggle ON and you see only options-confirmed setups; turn
# the main toggle OFF and the tables empty out (because Opt Flow is "–" for
# every row). It's also the cleanest way to diagnose whether the options
# pipeline is reaching your machine — if the table empties even on a US
# scan with the main toggle ON, yfinance options aren't loading.
opt_required = st.sidebar.checkbox(
    "Filter: only options-confirmed setups",
    key="ui_opt_required",
    help="Hides any stock that didn't fire at least one option signal. "
         "Requires 'Use options data' ON. If the table empties on a US "
         "scan, it means yfinance is not returning option-chain data — "
         "try `pip install --upgrade yfinance` and `streamlit cache clear`.",
)

# ─────────────────────────────────────────────────────────────────────────────
# v13.7: Bucket-cap toggle for correlated-signal handling
# Default ON — this is a real fix for evidence over-counting in the
# Bayesian engine. Off only for A/B comparison or to debug a borderline
# case. Toggling this invalidates fetch_analysis cache so probabilities
# are recomputed on the next scan.
# ─────────────────────────────────────────────────────────────────────────────
use_bucket_cap = st.sidebar.checkbox(
    "Bucket-cap correlated signals (recommended)",
    key="ui_use_bucket_cap",
    help="Bayesian probability assumes signals are independent. They aren't — "
         "trend_daily, weekly_trend, full_ma_stack, golden_cross all measure "
         "the same uptrend. Default ON: within each bucket (trend / momentum / "
         "volume / volatility / structure / relative / options), the strongest "
         "signal counts in full, the next at half-strength, the third at "
         "quarter, and so on. This stops 5 correlated 'uptrend' signals from "
         "being scored as 5 independent witnesses, which previously pegged "
         "probability at 95% on setups that historically win ~60%.",
)
st.session_state["use_bucket_cap"] = use_bucket_cap
_prev_bucket = st.session_state.get("_prev_bucket_cap")
if _prev_bucket is not None and _prev_bucket != use_bucket_cap:
    try:
        fetch_analysis.clear()
    except Exception:
        pass
st.session_state["_prev_bucket_cap"] = use_bucket_cap

st.sidebar.markdown("---")
st.sidebar.header("Long signal filters")
req_stoch = st.sidebar.checkbox("Must have Stoch bounce",      key="ui_req_stoch")
req_bb    = st.sidebar.checkbox("Must have BB bull squeeze",   key="ui_req_bb")
req_accel = st.sidebar.checkbox("Must have MACD acceleration", key="ui_req_accel")

st.sidebar.markdown("---")
st.sidebar.header("Short signal filters")
req_s_stoch = st.sidebar.checkbox("Must have Stoch rollover",    key="ui_req_s_stoch")
req_s_bb    = st.sidebar.checkbox("Must have BB bear squeeze",   key="ui_req_s_bb")
req_s_decel = st.sidebar.checkbox("Must have MACD deceleration", key="ui_req_s_decel")

extra_input = ""  # merged into Always include tickers above

st.sidebar.markdown("---")
st.sidebar.header("CSV result cache")
load_csv_on_start = st.sidebar.checkbox(
    "Load latest CSV results on app start",
    key="ui_load_csv_on_start",
    help="Shows the last completed scan immediately from scanner_cache/*.csv so the UI does not stay blank while a new scan runs.",
)
refresh_choice = st.sidebar.radio(
    "Auto refresh scan",
    ["Off", "5 min","15 min", "30 min"],
    key="ui_refresh_choice",
    horizontal=True,
    help="When enabled, the app re-runs on this interval to refresh data. "
         "Requires `streamlit-autorefresh` (pip install streamlit-autorefresh) "
         "to do this WITHOUT reloading the browser — which would otherwise "
         "wipe your sidebar settings, market selection, and refresh interval. "
         "If the package isn't installed, auto-refresh is disabled and a "
         "manual 'Rerun now' button is shown instead.",
)
refresh_minutes = 0 if refresh_choice == "Off" else int(refresh_choice.split()[0])
# Market-aware effective refresh: this sidebar section renders before the
# market radio widget below, so do NOT read local variable `market_sel` here.
# Use Streamlit session state instead; the widget value is already present on
# reruns and has a safe default on first startup.
_refresh_market_sel = st.session_state.get("market_selector", "🇺🇸 US")
effective_refresh_minutes = _effective_scan_refresh_minutes(_refresh_market_sel, refresh_minutes)
freshness_cache_bucket = _freshness_cache_bucket(_refresh_market_sel, refresh_minutes)
try:
    _live_state = "LIVE" if _is_market_live_now(_refresh_market_sel) else "closed/off-hours"
    st.sidebar.caption(
        f"Data freshness: **{effective_refresh_minutes} min** cache while {_refresh_market_sel} is {_live_state}. "
        "Strategy changes reuse cache; Scan/expired cache refreshes Yahoo."
    )
except Exception:
    pass
# v13.31: Non-destructive auto-refresh
# OLD: <script>setTimeout(window.parent.location.reload, ...)</script>
#      ^ This destroyed the entire Streamlit session — every widget reset to
#      default, market selector flipped to US, refresh interval back to 15 min.
# NEW: streamlit-autorefresh, which triggers a server-side rerun WITHOUT
#      reloading the browser page. Session state is fully preserved.
if refresh_minutes:
    if _autorefresh_available:
        # Returns a counter that increments each refresh — we don't use the
        # value, but the call itself schedules the next rerun.
        st_autorefresh(
            interval=refresh_minutes * 60 * 1000,
            limit=None,
            key=f"_autorefresh_{refresh_minutes}m",
        )
    else:
        st.sidebar.warning(
            "⚠️ Auto-refresh disabled — `streamlit-autorefresh` not installed.\n\n"
            "Install with `pip install streamlit-autorefresh` and restart "
            "Streamlit. The previous browser-reload approach was removed "
            "because it wiped all sidebar settings on every refresh."
        )
        if st.sidebar.button("🔄 Rerun now", key="manual_rerun_btn",
                             width="stretch",
                             help="Manual fallback for auto-refresh."):
            st.rerun()

# v13.31: After all sidebar widgets have rendered, persist any changes to disk
# so a true browser reload, server restart, or new tab restores the user's
# last-known settings. We compare to the per-session baseline; if anything
# changed, write ui_state.json. Cheap because Python dict equality is fast,
# and writes are skipped when nothing changed.
_current_ui_state = {_k: st.session_state.get(_k) for _k in _SIDEBAR_DEFAULTS}
_baseline = st.session_state.get("_ui_state_baseline", {})
if _current_ui_state != _baseline:
    _save_ui_state(_current_ui_state)
    st.session_state["_ui_state_baseline"] = _current_ui_state

st.sidebar.markdown("---")
st.sidebar.markdown(
    f"**Data sources**\n\n"
    f"✅ yfinance · US options\n\n"
    f"{'✅' if _fd_available else '⚠️'} FinanceDatabase "
    f"({'installed' if _fd_available else 'pip install financedatabase'})\n\n"
    f"{'✅' if _nse_opt_available else '⚠️'} nsepython · India F&O options "
    f"({'installed' if _nse_opt_available else 'pip install nsepython'})\n\n"
    f"{'✅' if _autorefresh_available else '⚠️'} streamlit-autorefresh "
    f"({'installed' if _autorefresh_available else 'pip install streamlit-autorefresh'})"
)

# ─────────────────────────────────────────────────────────────────────────────
# v12: OPTIONS PIPELINE DIAGNOSTICS
# Lets the user run a live, single-ticker test against each backend and see
# exactly what came back. This bypasses the technical pre-filter, the cache,
# and every UI layer — so if the test fails here, the problem is in the data
# layer (library install, IP block, library bug), not in our integration.
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar.expander("🩺 Options diagnostics"):
    st.caption(
        "Tests both backends with a single liquid ticker each. "
        "Use this to find out *exactly* why options data isn't flowing."
    )
    st.write(f"**yfinance:** ✅ available")
    st.write(
        f"**nsepython:** {'✅ installed' if _nse_opt_available else '❌ NOT installed — `pip install nsepython` and restart Streamlit'}"
    )

    if st.button("Run live backend test", key="opt_diag_btn"):
        # ── US backend ────────────────────────────────────────────────────────
        st.markdown("**🇺🇸 US backend test — AAPL**")
        try:
            with st.spinner("Calling yfinance..."):
                _yf_chain = _fetch_chain_yf("AAPL", 2)
            if _yf_chain:
                _exp, _c, _p = _yf_chain[0]
                st.success(
                    f"✅ {len(_yf_chain)} expirations · "
                    f"front {_exp} · {len(_c)} calls · {len(_p)} puts"
                )
                if not _c.empty and "impliedVolatility" in _c.columns:
                    _ivs = _c["impliedVolatility"].dropna()
                    if not _ivs.empty:
                        st.caption(f"IV sanity: median {_ivs.median():.3f}, range {_ivs.min():.3f}–{_ivs.max():.3f}")
            else:
                st.error("❌ Empty result. yfinance returned no chain. "
                         "Try `pip install --upgrade yfinance` and restart.")
        except Exception as _e:
            st.error(f"❌ Exception: `{type(_e).__name__}: {_e}`")

        # ── India backend ─────────────────────────────────────────────────────
        st.markdown("**🇮🇳 India backend test — RELIANCE**")
        if not _nse_opt_available:
            st.warning(
                "Skipped — `nsepython` is not installed. "
                "Run `pip install nsepython` and restart Streamlit."
            )
        else:
            try:
                with st.spinner("Calling NSE (may take 5–10 seconds on first call)..."):
                    _nse_chain = _fetch_chain_nse("RELIANCE.NS", 2)
                if _nse_chain:
                    _exp, _c, _p = _nse_chain[0]
                    st.success(
                        f"✅ {len(_nse_chain)} expirations · "
                        f"front {_exp} · {len(_c)} calls · {len(_p)} puts"
                    )
                    if not _c.empty and "impliedVolatility" in _c.columns:
                        _ivs = _c["impliedVolatility"][_c["impliedVolatility"] > 0]
                        if not _ivs.empty:
                            st.caption(
                                f"IV sanity (should be 0.10–0.80 for RELIANCE): "
                                f"median {_ivs.median():.3f}, "
                                f"range {_ivs.min():.3f}–{_ivs.max():.3f}"
                            )
                        else:
                            st.warning(
                                "⚠️ Chain fetched but all IVs are 0. NSE often "
                                "returns 0 IV for OTM strikes; the integration "
                                "filters these out automatically."
                            )
                else:
                    # Try to discover whether nsepython is reachable at all
                    st.error(
                        "❌ Empty result from NSE. Most likely causes:\n\n"
                        "1. **NSE blocking your IP.** From Singapore (or any "
                        "non-IN/cloud IP), NSE can rate-limit aggressively. "
                        "Wait 60 seconds and retry.\n\n"
                        "2. **Cloudflare challenge.** `nsepython`'s cookie/"
                        "session bootstrap can fail silently if NSE returns a "
                        "Cloudflare interstitial. Try `pip install --upgrade nsepython`.\n\n"
                        "3. **Proxy/firewall.** If you're behind a corporate "
                        "proxy or VPN, NSE may refuse the connection."
                    )
                    # Show raw nsepython response for debugging
                    try:
                        _raw = _nse_oc("RELIANCE")
                        if not _raw:
                            st.caption("Debug: nsepython returned an empty/falsy value.")
                        elif isinstance(_raw, dict):
                            _keys = list(_raw.keys())[:5]
                            st.caption(f"Debug: nsepython returned a dict with keys {_keys} — "
                                       f"but `records` was missing or unparseable.")
                        else:
                            st.caption(f"Debug: nsepython returned type `{type(_raw).__name__}`.")
                    except Exception as _e2:
                        st.caption(f"Debug: nsepython raised `{type(_e2).__name__}: {_e2}`")
            except Exception as _e:
                st.error(
                    f"❌ Exception: `{type(_e).__name__}: {_e}`\n\n"
                    f"This is usually a network or NSE-blocking issue, not a "
                    f"code bug. Try again in 60 seconds."
                )

# ─────────────────────────────────────────────────────────────────────────────
# MARKET REGIME BANNER
# ─────────────────────────────────────────────────────────────────────────────
mkt    = get_market_regime()
regime = mkt["regime"]
emojis = {"BULL":"🟢","CAUTION":"🟡","BEAR":"🔴","UNKNOWN":"⚪"}

st.caption(
    f"{emojis.get(regime,'⚪')} **{regime}** · "
    f"SPY **${mkt['spy']}** (EMA20 ${mkt['spy_ema20']}) · "
    f"VIX **{mkt['vix']}** · "
    f"{'🟢 Normal' if regime=='BULL' else '🔴 Strict long / Short boost' if regime=='BEAR' else '🟡 Cautious'}"
)
if regime == "BEAR":
    st.error("🔴 Bear market — Long thresholds raised · Short probability boosted +8%")
elif regime == "CAUTION":
    st.warning("🟡 Caution zone — Long probabilities reduced 12% · Short boosted +3%")

market_sel = st.radio(
    "🌍 Market", ["🇺🇸 US", "🇸🇬 SGX", "🇮🇳 India", "🇭🇰 HK"],
    horizontal=True, key="market_selector", label_visibility="collapsed"
)

# Map selection → ticker list, sector map, currency symbol
if market_sel == "🇺🇸 US":
    _active_tickers = US_TICKERS;  _active_sectors = SECTOR_ETFS
    _currency_sym = "$";           _price_fmt = lambda p: f"${p:,.2f}"
elif market_sel == "🇸🇬 SGX":
    _active_tickers = SG_TICKERS;  _active_sectors = {}
    _currency_sym = "S$";          _price_fmt = lambda p: f"S${p:,.3f}"
elif market_sel == "🇭🇰 HK":
    _active_tickers = HK_TICKERS;  _active_sectors = {}
    _currency_sym = "HK$";         _price_fmt = lambda p: f"HK${p:,.3f}"
else:
    _active_tickers = INDIA_TICKERS; _active_sectors = INDIA_SECTOR_ETFS
    _currency_sym = "₹";            _price_fmt = lambda p: f"₹{p:,.2f}"

# When the user switches market, clear stale ticker-list session keys so
# Diagnostics immediately shows the correct market instead of the old one.
_last_diag_market = st.session_state.get("_diag_market", market_sel)
if _last_diag_market != market_sel:
    # Clear only the display-state keys — not the dataframes (those are
    # cleared naturally by the cache-key mismatch in the block below).
    for _k in ("last_scanned_tickers", "last_scanned_tickers_csv",
               "last_universe_source", "last_universe_count",
               "last_live_ticker_count", "last_existing_ticker_count",
               "last_always_include_csv", "last_always_include_list",
               "last_scan_debug", "_loaded_csv_cache_key",
               "_last_scan_signature"):   # v15.9: invalidate skip-rescan guard on market change
        st.session_state.pop(_k, None)
    st.session_state["_diag_market"] = market_sel
else:
    st.session_state.setdefault("_diag_market", market_sel)

def _pct_to_num(series, default=0.0):
    """Convert '72.3%' / numeric columns to float safely."""
    try:
        return pd.to_numeric(series.astype(str).str.replace("%", "", regex=False).str.replace("+", "", regex=False), errors="coerce").fillna(default)
    except Exception:
        return pd.Series([default] * len(series), index=getattr(series, "index", None))


def _score_to_num(series):
    try:
        return pd.to_numeric(series.astype(str).str.extract(r"(\d+)")[0], errors="coerce").fillna(0)
    except Exception:
        return pd.Series([0] * len(series), index=getattr(series, "index", None))


def _apply_strategy_from_master(df_long_master, df_short_master, df_operator_master, strategy_mode,
                                min_prob_long=40, min_prob_short=40,
                                req_stoch=False, req_bb=False, req_accel=False,
                                req_s_stoch=False, req_s_bb=False, req_s_decel=False,
                                opt_required=False, enable_options=True):
    """Filter the cached master Yahoo scan for the selected strategy.

    Yahoo is intentionally NOT called here. The master dataframe contains the
    full Discovery-mode scan; this function re-ranks and re-filters cached rows
    to match the selected strategy mode.

    v2 fixes:
      - BALANCED score gate lowered from >=5 to >=4 (was blanking results in weak markets)
      - Action labels normalised per mode so Results tab regex matches correctly
      - HIGH CONVICTION case added (was falling to bare `else` → wrong labels)
      - WATCH – CANDIDATE rows excluded from all modes except Discovery
      - Emergency fallback: if any non-Discovery mode produces 0 rows, return
        top-N Discovery rows so the tab is never completely blank
    """
    mode = str(strategy_mode or "Balanced").upper()
    df_long = df_long_master.copy() if isinstance(df_long_master, pd.DataFrame) else pd.DataFrame()
    df_short = df_short_master.copy() if isinstance(df_short_master, pd.DataFrame) else pd.DataFrame()
    df_operator = df_operator_master.copy() if isinstance(df_operator_master, pd.DataFrame) else pd.DataFrame()

    def _ensure_cols(df):
        if df.empty:
            return df
        for c in ["Action", "Setup Type", "Signals", "Opt Flow", "Rise Prob", "Fall Prob",
                  "Score", "Vol Ratio", "Support Tier", "PM Chg%", "Entry Quality"]:
            if c not in df.columns:
                df[c] = "–"
        return df

    df_long  = _ensure_cols(df_long)
    df_short = _ensure_cols(df_short)

    if not df_long.empty:
        p         = _pct_to_num(df_long["Rise Prob"], 0)
        score     = _score_to_num(df_long["Score"])
        action    = df_long["Action"].astype(str)
        signals   = df_long["Signals"].astype(str)
        opt_flow  = df_long["Opt Flow"].astype(str) if "Opt Flow" in df_long.columns else pd.Series(["–"] * len(df_long), index=df_long.index)
        vol_ratio = pd.to_numeric(df_long["Vol Ratio"], errors="coerce").fillna(0) if "Vol Ratio" in df_long.columns else pd.Series([0.0] * len(df_long), index=df_long.index)
        today_pct = _pct_to_num(df_long["Today %"], 0) if "Today %" in df_long.columns else pd.Series([0.0] * len(df_long), index=df_long.index)
        supp_num  = pd.to_numeric(df_long.get("Supp#", 0), errors="coerce").fillna(0) if "Supp#" in df_long.columns else pd.Series([0] * len(df_long), index=df_long.index)
        support_tier = df_long["Support Tier"].astype(str) if "Support Tier" in df_long.columns else pd.Series(["–"] * len(df_long), index=df_long.index)
        pm_chg    = _pct_to_num(df_long["PM Chg%"], 0) if "PM Chg%" in df_long.columns else pd.Series([0.0] * len(df_long), index=df_long.index)

        # Exclude WATCH – CANDIDATE (master-only rows) from all non-Discovery modes
        not_candidate = ~action.str.contains("CANDIDATE", na=False, regex=False)

        if mode == "STRICT":
            mask = (p >= max(float(min_prob_long), 76.0)) & (score >= 7) & not_candidate
            mask &= action.str.contains("STRONG BUY|STRICT|DISCOVERY QUALITY", na=False, regex=True) | signals.str.contains("🎯HIGH-ACCURACY|VOL BREAKOUT|POCKET PIVOT", na=False, regex=True)
            df_long = df_long[mask].copy()
            if not df_long.empty:
                # Normalise labels
                df_long["Action"] = "WATCH – STRICT QUALITY"
                strong = (p.reindex(df_long.index).fillna(0) >= max(float(min_prob_long), 80.0)) & (score.reindex(df_long.index).fillna(0) >= 8)
                df_long.loc[strong, "Action"] = "STRONG BUY – STRICT"

        elif mode == "BALANCED":
            # v2 fix: lowered score gate from 5 to 4 so weak-market sessions still show results.
            # BALANCED = real trades; Discovery master rows with score 4+ and p >= 58 qualify.
            mask = (p >= max(float(min_prob_long), 58.0)) & (score >= 4) & not_candidate
            # Also include high-vol operator signals even at score 3
            mask |= ((score >= 3) & (vol_ratio >= 2.0) & (p >= 58.0) & not_candidate)
            df_long = df_long[mask].copy()
            if not df_long.empty:
                # Normalise labels from Discovery → Balanced labels
                act = df_long["Action"].astype(str)
                df_long["Action"] = "WATCH – DEVELOPING"
                df_long.loc[act.str.contains("STRONG BUY|HIGH QUALITY|DISCOVERY QUALITY", na=False, regex=True) |
                            (p.reindex(df_long.index).fillna(0) >= 72), "Action"] = "WATCH – HIGH QUALITY"
                strong = (p.reindex(df_long.index).fillna(0) >= max(float(min_prob_long), 70.0)) & (score.reindex(df_long.index).fillna(0) >= 6)
                df_long.loc[strong & signals.reindex(df_long.index).fillna("").str.contains("🎯HIGH-ACCURACY", na=False), "Action"] = "STRONG BUY"
                df_long.loc[act.reindex(df_long.index).fillna("").str.contains("TRAP RISK", na=False), "Action"] = "WATCH – TRAP RISK"

        elif mode == "DISCOVERY":
            # Wide watchlist including CANDIDATE rows
            mask = (p >= min(float(min_prob_long), 44.0)) & (score >= 2)
            df_long = df_long[mask].copy()
            if not df_long.empty:
                # Keep original Discovery labels but rename None/blank
                act = df_long["Action"].astype(str)
                df_long.loc[act.isin(["None", "", "nan", "–"]), "Action"] = "WATCH – DISCOVERY"

        elif mode == "SUPPORT ENTRY":
            mask = (supp_num > 0) | (~support_tier.isin(["–", "", "nan", "None"]))
            mask &= (p >= 38) & (today_pct <= 6.0) & not_candidate
            df_long = df_long[mask].copy()
            if not df_long.empty:
                supp_n_r = supp_num.reindex(df_long.index).fillna(0)
                p_r      = p.reindex(df_long.index).fillna(0)
                df_long["Action"] = "WATCH – SUPPORT ENTRY"
                df_long.loc[p_r >= 58, "Action"] = "BUY – SUPPORT ENTRY"
                df_long.loc[(supp_n_r <= 2) & (p_r >= 60), "Action"] = "BUY – MA60/MA20 SUPPORT"
                df_long["Setup Type"] = df_long["Support Tier"].astype(str)
                df_long = df_long.sort_values(by=["Supp#", "Rise Prob"], ascending=[True, False], kind="stable") if "Supp#" in df_long.columns else df_long

        elif mode == "PREMARKET MOMENTUM":
            mask = (pm_chg > 0.1) | ((today_pct > 0.3) & (score >= 3)) | signals.str.contains("MACD ACCEL|VOL BREAKOUT|VOL SURGE|POCKET PIVOT|RS>SPY|WKLY TREND", na=False, regex=True)
            mask &= (p >= 35) & not_candidate
            df_long = df_long[mask].copy()
            if not df_long.empty:
                pm_r = pm_chg.reindex(df_long.index).fillna(0)
                p_r  = p.reindex(df_long.index).fillna(0)
                df_long["Action"] = "WATCH – MOMENTUM CANDIDATE"
                df_long.loc[pm_r >= 1.0, "Action"] = "WATCH – PM/LIVE MOMENTUM"
                df_long.loc[(pm_r >= 3.0) | (p_r >= 62), "Action"] = "BUY – PM/LIVE MOMENTUM"
                df_long["Setup Type"] = df_long.get("PM Chg%", "–").astype(str).where(df_long.get("PM Chg%", "–").astype(str) != "–", "TECH MOMENTUM")
                df_long = df_long.sort_values(by=["PM Chg%", "Rise Prob"], ascending=[False, False], kind="stable") if "PM Chg%" in df_long.columns else df_long

        elif mode == "HIGH VOLUME":
            mask = (vol_ratio >= 1.05) | signals.str.contains("VOL BREAKOUT|VOL SURGE|POCKET PIVOT|OBV", na=False, regex=True)
            mask &= (p >= 35) & not_candidate
            df_long = df_long[mask].copy()
            if not df_long.empty:
                vr_r = vol_ratio.reindex(df_long.index).fillna(0)
                df_long["Action"] = "WATCH – ACTIVE VOLUME"
                df_long.loc[vr_r >= 1.5, "Action"] = "WATCH – UNUSUAL VOLUME"
                df_long.loc[vr_r >= 2.0, "Action"] = "BUY – VOLUME BREAKOUT"
                df_long.loc[vr_r >= 3.0, "Action"] = "BUY – EXTREME VOLUME"
                df_long["Setup Type"] = "Vol " + vr_r.round(2).astype(str) + "x"
                df_long = df_long.assign(_vs=vr_r).sort_values("_vs", ascending=False, kind="stable").drop(columns="_vs")

        elif mode == "HIGH CONVICTION":
            # Require signals from multiple categories — detected via Signals column tags.
            # The HC[...](N/5) tag is added by analysis_scan_core when the HC block runs.
            # When not present (older scan), fall back to high-probability filter.
            hc_tag_mask = signals.str.contains("HC[", na=False, regex=False)
            hc_full_mask = signals.str.contains("(5/5)", na=False, regex=False)
            hc_part_mask = signals.str.contains("(4/5)", na=False, regex=False)
            if hc_tag_mask.any():
                # Use HC category tags if available (new scan with HC logic)
                mask = hc_tag_mask & (p >= 55) & not_candidate
            else:
                # Fallback: simulate HC requirements via signal column tags
                # Trend + Momentum + Volume each need at least one tag
                trend_ok    = signals.str.contains("WKLY TREND|RS>SPY|52W HIGH|GC", na=False, regex=True)
                momentum_ok = signals.str.contains("STOCH BOUNCE|MACD ACCEL|RSI>50|HIGHER LOWS", na=False, regex=True)
                volume_ok   = signals.str.contains("VOL BREAKOUT|VOL SURGE|POCKET PIVOT|OPERATOR|OBV", na=False, regex=True)
                mask = trend_ok & momentum_ok & volume_ok & (p >= 60) & (score >= 5) & not_candidate
            df_long = df_long[mask].copy()
            if not df_long.empty:
                p_r = p.reindex(df_long.index).fillna(0)
                full_r = hc_full_mask.reindex(df_long.index).fillna(False)
                df_long["Action"] = "WATCH – CONFLUENCE"
                df_long.loc[p_r >= 65, "Action"] = "BUY – PRECISION SETUP"
                df_long.loc[full_r & (p_r >= 70), "Action"] = "STRONG BUY – HIGH CONVICTION"

        elif mode == "PSM STRATEGY":
            # ═════════════════════════════════════════════════════════════
            # PSM Strategy v16 — QUALITY-FIRST 5–7 day swing filter
            #
            # Goal: stop weak/speculative names from appearing as BUY just
            # because they have high ATR/PI. A PSM BUY now needs:
            #   • return potential       (PI Proxy)
            #   • professional signals   (PSS Score)
            #   • probability            (Rise Prob)
            #   • volume confirmation    (Vol Ratio / volume signal)
            #   • acceptable entry/risk  (not extended/wait/avoid)
            #   • biotech/speculative cap (biotech must be exceptional)
            #
            # Watch candidates are allowed, but BUY tiers are deliberately
            # stricter so the grid gives fewer, higher-quality swing ideas.
            # ═════════════════════════════════════════════════════════════

            idx = df_long.index

            def _num_col(col_name, default=0.0):
                if col_name not in df_long.columns:
                    return pd.Series([default] * len(df_long), index=idx)
                return pd.to_numeric(
                    df_long[col_name].astype(str)
                        .str.replace("$", "", regex=False)
                        .str.replace("%", "", regex=False)
                        .str.replace("+", "", regex=False)
                        .str.replace("x", "", regex=False)
                        .str.replace(",", "", regex=False)
                        .str.strip(),
                    errors="coerce",
                ).fillna(default)

            op_score_num = pd.to_numeric(
                df_long["Op Score"].astype(str).str.extract(r"(\d+)", expand=False)
                if "Op Score" in df_long.columns else pd.Series(["0"]*len(df_long), index=idx),
                errors="coerce"
            ).fillna(0)

            pss_col = pd.to_numeric(
                df_long["PSS Score"].astype(str).str.extract(r"(\d+)", expand=False)
                if "PSS Score" in df_long.columns else pd.Series(["0"]*len(df_long), index=idx),
                errors="coerce"
            ).fillna(0)

            price_num = _num_col("Price", 0)
            today_num = _num_col("Today %", 0)

            # ── PI Proxy = ATR% × (Rise Prob / 100) ───────────────────────
            if "ATR%" in df_long.columns:
                _atr_pct = pd.to_numeric(
                    df_long["ATR%"].astype(str).str.replace("%", "", regex=False).str.strip(),
                    errors="coerce"
                ).fillna(0)
            else:
                _atr_pct = pd.Series([0.0] * len(df_long), index=idx)

            # If ATR% is missing in old cache, use a conservative volume proxy.
            if not _atr_pct.gt(0).any():
                _atr_pct = (vol_ratio * 1.5).fillna(0)

            pi_proxy = (_atr_pct * (p / 100)).round(2)

            # ── Entry/risk gates ───────────────────────────────────────────
            entry_text = df_long["Entry Quality"].astype(str) if "Entry Quality" in df_long.columns else pd.Series([""]*len(df_long), index=idx)
            setup_text = df_long["Setup Type"].astype(str) if "Setup Type" in df_long.columns else pd.Series([""]*len(df_long), index=idx)
            pos_text   = df_long["Pos Size"].astype(str) if "Pos Size" in df_long.columns else pd.Series([""]*len(df_long), index=idx)
            sector_txt = df_long["Sector"].astype(str) if "Sector" in df_long.columns else pd.Series([""]*len(df_long), index=idx)

            entry_bad = (entry_text + " " + setup_text).str.contains("EXTENDED|AVOID|WAIT|TRAP|⚠️|⏳", na=False, regex=True)
            entry_ideal = entry_text.str.contains("✅|IDEAL|SUPPORT|MA20|MA60|VWAP", na=False, regex=True)
            entry_ok = ~entry_bad

            # Avoid very cheap / illiquid / unusable names for PSM buy decisions.
            # Keep unknown prices out rather than accidentally promoting them.
            price_ok = price_num >= 5

            # PSM should target 5%+ swing potential, but avoid names so wild that
            # stops become unmanageable. Biotech can be volatile, so handled below.
            atr_ok = (_atr_pct >= 2.0) & (_atr_pct <= 14.0)

            # Avoid chasing huge one-day spikes for fresh buys. They may still be watchlist.
            not_chasing = today_num <= 12
            not_breaking_down = today_num >= -6

            # ── Sector / speculative caution ───────────────────────────────
            ticker_txt = df_long["Ticker"].astype(str).str.upper() if "Ticker" in df_long.columns else pd.Series([""]*len(df_long), index=idx)
            sig_txt    = df_long["Signals"].astype(str) if "Signals" in df_long.columns else pd.Series([""]*len(df_long), index=idx)
            pss_txt    = df_long["PSS Triggers"].astype(str) if "PSS Triggers" in df_long.columns else pd.Series([""]*len(df_long), index=idx)
            bio_text   = (ticker_txt + " " + pos_text + " " + sector_txt + " " + sig_txt + " " + pss_txt)

            # Clinical biotech/pharma names are binary-event trades, not repeatable
            # high-quality 5–7 day swing buys. Sector is often "Mixed" for small
            # caps, so use a ticker guard as well. This prevents ARCT-style names
            # from polluting PSM actionable results.
            high_risk_biotech_tickers = {
                "ARCT", "ACLX", "KALV", "TNYA", "VERV", "ABEO", "RIGL", "OPK",
                "STOK", "EXAS", "TNGX", "MRX", "PRCT", "MYGN", "ALKS", "LENZ",
                "SGHT", "LGND", "IRTC"
            }
            biotech_flag = bio_text.str.contains(
                "Biotech|Bio|Pharma|Therapeutic|Therapeutics|Clinical|Trial|Oncology|Gene|Genomic|Vaccine|Healthcare",
                na=False, regex=True
            ) | ticker_txt.isin(high_risk_biotech_tickers)
            slow_flag = pos_text.str.contains("ETF|Slow|Caution", na=False, regex=True)

            # Current PSM Gate from scan core remains useful as sector caution,
            # but do not let it alone promote a stock.
            if "PSM Gate" in df_long.columns:
                psm_gate = pd.to_numeric(df_long["PSM Gate"], errors="coerce").fillna(7)
            else:
                psm_gate = pd.Series([7.0] * len(df_long), index=idx)
            sector_ok = (score >= (psm_gate - 1)) | (pss_col >= 4) | (pi_proxy >= 3.0)

            # ── Signal confirmation ────────────────────────────────────────
            volume_signal = signals.str.contains("VOL BREAKOUT|VOL SURGE|POCKET PIVOT|OBV|ACTIVE VOLUME|HIGH VOLUME", na=False, regex=True)
            momentum_signal = signals.str.contains("MACD ACCEL|STOCH BOUNCE|RSI>50|HIGHER LOWS|RS>SPY|WKLY TREND|52W HIGH|BREAKOUT", na=False, regex=True)
            confirmation_ok = volume_signal | momentum_signal | (op_score_num >= 4) | (pss_col >= 4)

            # ── Quality composite used for gate + sorting ──────────────────
            pi_pts = (pi_proxy.clip(0, 4.0) / 4.0 * 100).fillna(0)
            pss_pts = (pss_col.clip(0, 8.0) / 8.0 * 100).fillna(0)
            vol_pts = (vol_ratio.clip(0, 4.0) / 4.0 * 100).fillna(0)
            op_pts = (op_score_num.clip(0, 10.0) / 10.0 * 100).fillna(0)
            entry_pts = pd.Series([55.0] * len(df_long), index=idx).mask(entry_ideal, 100).mask(entry_bad, 20)
            chase_penalty = pd.Series([0.0] * len(df_long), index=idx).mask(today_num > 12, 18).mask(today_num < -6, 12)
            biotech_penalty = pd.Series([0.0] * len(df_long), index=idx).mask(biotech_flag & (pss_col < 5), 14)
            slow_penalty = pd.Series([0.0] * len(df_long), index=idx).mask(slow_flag, 6)

            psm_quality = (
                pi_pts * 0.30 +
                pss_pts * 0.25 +
                p.clip(0, 100) * 0.20 +
                vol_pts * 0.12 +
                op_pts * 0.08 +
                entry_pts * 0.05 -
                chase_penalty - biotech_penalty - slow_penalty
            ).round(1).clip(lower=0, upper=100)

            # ── Buy tiers: stricter than previous version ──────────────────
            # PSM is now ACTIONABLE quality only. Exclude clinical biotech/pharma
            # from the buy universe by default because their moves are binary-event
            # driven and harder to manage with technical swing stops.
            common_quality = (
                price_ok & atr_ok & entry_ok & sector_ok & not_candidate &
                not_breaking_down & confirmation_ok & (~biotech_flag)
            )

            # Elite / Strong / Qualified tiers.
            # The previous version used only Elite + Strong, which became so strict
            # that PSM could return zero names. This version keeps PSM actionable,
            # but adds a third BUY tier for the best controlled-risk setups that
            # are not perfect. Biotech/event-driven names remain excluded.
            elite_ok = (
                common_quality & not_chasing &
                (psm_quality >= 82) &
                (pi_proxy >= 2.7) &
                (pss_col >= 4) &
                (p >= 64) &
                (vol_ratio >= 1.3) &
                ((op_score_num >= 4) | volume_signal | (pss_col >= 5))
            )

            strong_ok = (
                common_quality & not_chasing &
                (psm_quality >= 70) &
                (pi_proxy >= 1.8) &
                (pss_col >= 3) &
                (p >= 59) &
                (vol_ratio >= 1.0) &
                ((op_score_num >= 3) | volume_signal | momentum_signal | (pss_col >= 4))
            )

            qualified_ok = (
                common_quality &
                (psm_quality >= 62) &
                (pi_proxy >= 1.3) &
                (p >= 56) &
                (vol_ratio >= 0.8) &
                ((pss_col >= 2) | confirmation_ok) &
                (~slow_flag)
            )

            # No biotech exception in PSM actionable mode. Biotech may be traded
            # separately via High Volume / Premarket / Discovery, but not promoted
            # as a quality PSM buy. This keeps ARCT-style binary event names out.

            mask = elite_ok | strong_ok | qualified_ok

            # If market conditions are weak and no stock passes the three normal
            # tiers, still return a small "best available" quality shortlist.
            # This avoids a blank PSM grid while keeping the same hard exclusions:
            # no biotech, no bad entry, no breakdown, no unusable/cheap names.
            if not mask.any():
                fallback_ok = (
                    price_ok & entry_ok & not_candidate & not_breaking_down &
                    (~biotech_flag) & (~slow_flag) &
                    (psm_quality >= 56) & (pi_proxy >= 1.0) & (p >= 54) &
                    (vol_ratio >= 0.7) & ((pss_col >= 2) | confirmation_ok | (op_score_num >= 2))
                )
                if fallback_ok.any():
                    fallback_rank = psm_quality.where(fallback_ok, -1).sort_values(ascending=False)
                    keep_idx = fallback_rank.head(15).index
                    qualified_ok = pd.Series(False, index=idx)
                    qualified_ok.loc[keep_idx] = True
                    mask = qualified_ok

            df_long = df_long[mask].copy()

            if not df_long.empty:
                pss_r = pss_col.reindex(df_long.index).fillna(0)
                p_r   = p.reindex(df_long.index).fillna(0)
                vr_r  = vol_ratio.reindex(df_long.index).fillna(0)
                pi_r  = pi_proxy.reindex(df_long.index).fillna(0)
                q_r   = psm_quality.reindex(df_long.index).fillna(0)
                elite_r  = elite_ok.reindex(df_long.index).fillna(False)
                strong_r = strong_ok.reindex(df_long.index).fillna(False)
                biotech_r = biotech_flag.reindex(df_long.index).fillna(False)

                df_long["PI Proxy"] = pi_r.round(2)
                df_long["PI Proxy Raw"] = pi_r.round(2)
                df_long["PSM Quality"] = q_r.round(1)

                qualified_r = qualified_ok.reindex(df_long.index).fillna(False)

                df_long["Action"] = "BUY – PSM QUALIFIED"
                df_long.loc[strong_r, "Action"] = "BUY – PSM STRONG"
                df_long.loc[elite_r,  "Action"] = "STRONG BUY – PSM ELITE"

                df_long["PSM Decision"] = "QUALIFIED BUY – best available controlled-risk setup"
                df_long.loc[strong_r, "PSM Decision"] = "BUY CANDIDATE – strong controlled-risk setup"
                df_long.loc[elite_r,  "PSM Decision"] = "TOP SWING BUY – best PSM setup"

                df_long = (
                    df_long.assign(_q=q_r, _pi=pi_r, _prob=p_r, _vr=vr_r, _pss=pss_r)
                           .sort_values(["_q", "_pi", "_prob", "_vr", "_pss"], ascending=[False, False, False, False, False], kind="stable")
                           .drop(columns=["_q", "_pi", "_prob", "_vr", "_pss"])
                )

        else:
            # Unknown mode — show everything above probability threshold
            df_long = df_long[(p >= float(min_prob_long)) & not_candidate].copy()

        # ── Optional sidebar signal filters (Strict/Balanced/Discovery only) ──
        if not df_long.empty and mode in ("STRICT", "BALANCED", "DISCOVERY"):
            sig_col = df_long["Signals"].astype(str)
            if req_stoch: df_long = df_long[sig_col.str.contains("STOCH", na=False)]
            if req_bb and "BB Squeeze" in df_long.columns: df_long = df_long[df_long["BB Squeeze"].astype(str).eq("YES")]
            if req_accel: df_long = df_long[sig_col.str.contains("MACD ACCEL", na=False)]
            if opt_required and enable_options and "Opt Flow" in df_long.columns:
                df_long = df_long[df_long["Opt Flow"].astype(str) != "–"]
        elif not df_long.empty and opt_required and enable_options and "Opt Flow" in df_long.columns:
            tmp = df_long[df_long["Opt Flow"].astype(str) != "–"]
            if not tmp.empty:
                df_long = tmp

        # ── Emergency fallback: never show a completely blank long tab ─────────
        # If a non-Discovery mode filtered everything out, show the top Discovery
        # rows with a note so the user knows WHY results are limited.
        if df_long.empty and not df_long_master.empty and mode not in ("DISCOVERY",):
            top_n = min(20, len(df_long_master))
            master_p = _pct_to_num(df_long_master["Rise Prob"], 0) if "Rise Prob" in df_long_master.columns else pd.Series([0.0] * len(df_long_master))
            df_long = df_long_master.sort_values(master_p.name if hasattr(master_p, "name") and master_p.name in df_long_master.columns else df_long_master.columns[0], ascending=False).head(top_n).copy()
            if "Action" in df_long.columns:
                df_long["Action"] = f"WATCH – {mode} (no exact match – showing top Discovery)"

    if not df_short.empty:
        p_s     = _pct_to_num(df_short["Fall Prob"], 0)
        score_s = _score_to_num(df_short["Score"])
        sig_s   = df_short["Signals"].astype(str)
        if mode == "STRICT":
            df_short = df_short[(p_s >= max(float(min_prob_short), 72.0)) & (score_s >= 6)].copy()
        elif mode == "BALANCED":
            df_short = df_short[(p_s >= max(float(min_prob_short), 56.0)) & (score_s >= 4)].copy()
        elif mode == "DISCOVERY":
            df_short = df_short[(p_s >= min(float(min_prob_short), 44.0)) & (score_s >= 2)].copy()
        else:
            # Special long-only strategies should not force unrelated shorts
            df_short = pd.DataFrame(columns=df_short.columns)
        if not df_short.empty:
            sig_s = df_short["Signals"].astype(str)
            if req_s_stoch: df_short = df_short[sig_s.str.contains("STOCH", na=False)]
            if req_s_bb:    df_short = df_short[sig_s.str.contains("BB BEAR", na=False)]
            if req_s_decel: df_short = df_short[sig_s.str.contains("MACD DECEL", na=False)]
            if opt_required and enable_options and "Opt Flow" in df_short.columns:
                df_short = df_short[df_short["Opt Flow"].astype(str) != "–"]

    return df_long, df_short, df_operator




# ─────────────────────────────────────────────────────────────────────────────
# EARLY LATEST-BAR DISPLAY HELPER
# Needed before the tab-renderer section because cache-load messages are built
# before the later tab helpers are defined.
# ─────────────────────────────────────────────────────────────────────────────
def _latest_bar_display_value(latest_bar_time) -> str:
    """Return latest-bar timestamp formatted in SGT without the 'Latest bar:' label."""
    try:
        import pandas as pd
        if latest_bar_time is None or str(latest_bar_time).strip() == "":
            return "unknown"
        raw = str(latest_bar_time).strip().replace("Latest bar:", "").strip()
        if raw.endswith(" SGT"):
            return raw
        if raw.endswith(" ET"):
            ts = pd.to_datetime(raw[:-3].strip(), errors="coerce")
            if pd.isna(ts):
                return raw
            ts = ts.tz_localize("America/New_York") if ts.tzinfo is None else ts.tz_convert("America/New_York")
        else:
            ts = pd.to_datetime(raw, errors="coerce")
            if pd.isna(ts):
                return raw
            if ts.tzinfo is None:
                ts = ts.tz_localize("UTC")
        ts = ts.tz_convert("Asia/Singapore")
        return f"{ts.strftime('%Y-%m-%d %H:%M:%S')} SGT"
    except Exception:
        return str(latest_bar_time or "unknown").replace("Latest bar:", "").strip() or "unknown"

# ── Load cached MASTER CSV results immediately for the selected market ─────
# The CSV cache stores the broad Yahoo/master scan, not one strategy's final
# output. Strategy changes only re-filter this cached dataframe.
_cache_loaded_note = ""
_cache_refresh_due = False
_loaded_cache = None
if load_csv_on_start:
    _loaded_cache = _load_scan_cache(market_sel)
    if _loaded_cache is not None:
        _meta = _loaded_cache.get("meta", {})
        _is_master_cache = str(_meta.get("cache_type", "")).lower() == "master_scan_v1"
        _cache_age = _cache_age_minutes(_meta)
        _cache_timing = _cache_timing_info(_meta, effective_refresh_minutes)
        st.session_state["scan_cache_meta"] = _meta
        st.session_state["scan_cache_timing"] = _cache_timing
        st.session_state["scan_cache_refresh_minutes"] = effective_refresh_minutes
        st.session_state["scan_cache_refresh_due"] = bool(_cache_timing.get("is_due", False))

        if not _is_master_cache:
            _cache_strategy = str(_meta.get("strategy_mode", "Balanced"))
            if _cache_strategy != str(swing_mode):
                _loaded_cache = None
                _cache_loaded_note = (
                    f"📦 Old cache is for **{_cache_strategy}**. Click **Scan** once to build the new "
                    "master Yahoo cache; after that strategy changes will be instant."
                )
            else:
                st.session_state["df_long_master"] = _loaded_cache.get("df_long", pd.DataFrame())
                st.session_state["df_short_master"] = _loaded_cache.get("df_short", pd.DataFrame())
                st.session_state["df_operator_master"] = _loaded_cache.get("df_operator", pd.DataFrame())
        else:
            _cache_market_key = f"{market_sel}:MASTER:{_meta.get('saved_at','')}:{swing_mode}"
            if (st.session_state.get("_loaded_csv_cache_key") != _cache_market_key
                    or st.session_state.get("last_market") != market_sel
                    or st.session_state.get("last_scan_strategy") != swing_mode
                    or st.session_state.pop("_force_strategy_refilter", False)):
                _master_long  = _loaded_cache.get("df_long",     pd.DataFrame())
                _master_short = _loaded_cache.get("df_short",    pd.DataFrame())
                _master_op    = _loaded_cache.get("df_operator", pd.DataFrame())
                st.session_state["df_long_master"]     = _master_long
                st.session_state["df_short_master"]    = _master_short
                st.session_state["df_operator_master"] = _master_op
                _fl, _fs, _fo = _apply_strategy_from_master(
                    _master_long, _master_short, _master_op, swing_mode,
                    min_prob_long=min_prob_long, min_prob_short=min_prob_short,
                    req_stoch=req_stoch, req_bb=req_bb, req_accel=req_accel,
                    req_s_stoch=req_s_stoch, req_s_bb=req_s_bb, req_s_decel=req_s_decel,
                    opt_required=opt_required, enable_options=enable_options,
                )
                st.session_state["df_long"]     = _fl
                st.session_state["df_short"]    = _fs
                st.session_state["df_operator"] = _fo
                st.session_state["last_market"]            = market_sel
                st.session_state["last_scan_strategy"]     = swing_mode
                st.session_state["last_universe_source"]   = _meta.get("universe_source", "CSV cached master scan")
                st.session_state["last_universe_count"]    = int(_meta.get("universe_count", 0) or 0)
                st.session_state["last_live_ticker_count"] = int(_meta.get("live_ticker_count", 0) or 0)
                st.session_state["last_existing_ticker_count"] = int(_meta.get("existing_ticker_count", len(_active_tickers)) or len(_active_tickers))
                _tickers_csv = _meta.get("scanned_tickers_csv", "")
                st.session_state["last_scanned_tickers_csv"] = _tickers_csv
                st.session_state["last_scanned_tickers"]     = [t.strip() for t in _tickers_csv.split(",") if t.strip()]
                # Restore always-include info from meta so diagnostics is accurate
                _cached_always = _meta.get("always_include_tickers", "")
                st.session_state["last_always_include_csv"]  = _cached_always
                st.session_state["last_always_include_list"] = [t.strip() for t in _cached_always.split(",") if t.strip()]
                st.session_state["last_scan_opt_enabled"]    = bool(_meta.get("options_enabled", False))
                st.session_state["last_scan_opt_count"]      = int(_meta.get("options_count", 0) or 0)
                st.session_state["last_scan_market"]         = market_sel
                st.session_state["_loaded_csv_cache_key"]    = _cache_market_key
                if st.session_state.get("_strategy_changed_notice"):
                    _cache_loaded_note = st.session_state.pop("_strategy_changed_notice")
            if not _cache_loaded_note and _cache_age is not None:
                _cache_loaded_note = (
                    f"📦 Loaded cached Yahoo master scan from {_meta.get('saved_at', 'unknown')} "
                    f"({_cache_age:.0f} min old). Displaying **{swing_mode}** from cache · "
                    f"Latest bar: **{_latest_bar_display_value(_meta.get('latest_bar_time', 'unknown'))}** · "
                    f"Long {len(st.session_state.get('df_long', pd.DataFrame()))} · "
                    f"Short {len(st.session_state.get('df_short', pd.DataFrame()))}"
                )
            if effective_refresh_minutes and _cache_age is not None and _cache_age >= effective_refresh_minutes:
                _cache_refresh_due = True
    else:
        st.session_state["scan_cache_meta"]            = {}
        st.session_state["scan_cache_timing"]          = _cache_timing_info({}, effective_refresh_minutes)
        st.session_state["scan_cache_refresh_minutes"] = effective_refresh_minutes
        st.session_state["scan_cache_refresh_due"]     = False
        if effective_refresh_minutes:
            _cache_loaded_note = "📦 No master Yahoo cache found yet. Click Scan once to create it."

if st.session_state.get("scan_cache_warning"):
    _cw = st.session_state.get("scan_cache_warning")
    cw_cols = st.columns([10, 1])
    with cw_cols[0]:
        st.error(f"⚠️ {_cw}\n\n"
                 "See sidebar → 📦 CSV cache status for the directory and writability check.")
    with cw_cols[1]:
        if st.button("✕", key="dismiss_cache_warning"):
            st.session_state.pop("scan_cache_warning", None)
            st.rerun()



# ─────────────────────────────────────────────────────────────────────────────
# TOP SCAN STATUS PLACEHOLDER
# Shows loading / scan progress near the top of the page, before tab content.
# ─────────────────────────────────────────────────────────────────────────────
_top_scan_status = st.empty()


def _show_top_spinner(message: str):
    """Render a lightweight spinner in the top scan-status placeholder.
    This stays visible above the tabs, unlike normal st.spinner lower in the page.
    """
    try:
        _top_scan_status.markdown(
            f"""
            <div class="top-scan-box">
                <span class="top-scan-spinner"></span>
                <span>{message}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception:
        _top_scan_status.info(message)


tab_sectors, tab_trade_desk, tab_long, tab_swing_picks, tab_top_movers, tab_short, tab_operator, tab_both, tab_etf, tab_stock, tab_earn, tab_event, tab_lt, tab_diag, tab_backtest, tab_strategy, tab_help = st.tabs([
    "🗂️ Sector Heatmap",
    "📋 Trade Desk",
    "📈 Long Setups",
    "🎯 Swing Picks",
    "🚀 Movers/Losers",
    "📉 Short Setups",
    "🪤 Operator Activity",
    "🔄 Side by Side",
    "📊 ETF Holdings",
    "🔬 Stock Analysis",
    "📅 Earnings",
    "📰 Event Predictor",
    "🌱 Long Term",
    "🔍 Diagnostics",
    "🧪 Accuracy Lab",
    "🧠 Strategy Lab",
    "❓ Help",
])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — SECTOR HEATMAP  (market-aware)
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# TAB RENDERERS — extracted from the original working single-file script
# Each renderer executes the original tab body with the same globals dict,
# preserving behavior while keeping this runtime file much smaller.
# ─────────────────────────────────────────────────────────────────────────────
from swing_trader_app.tabs.accuracy_lab_tab import render_accuracy_lab
from swing_trader_app.tabs.diagnostics_tab import render_diagnostics
from swing_trader_app.tabs.earnings_tab import render_earnings
from swing_trader_app.tabs.etf_holdings_tab import render_etf_holdings
from swing_trader_app.tabs.event_predictor_tab import render_event_predictor
from swing_trader_app.tabs.help_tab import render_help
from swing_trader_app.tabs.long_term_tab import render_long_term
from swing_trader_app.tabs.operator_activity_tab import render_operator_activity
from swing_trader_app.tabs.scan_results_tabs import render_long, render_short, render_both
from swing_trader_app.tabs.sectors_tab import render_sectors
from swing_trader_app.tabs.stock_analysis_tab import render_stock_analysis
from swing_trader_app.tabs.strategy_lab_tab import render_strategy_lab
from swing_trader_app.tabs.swing_picks_tab import render_swing_picks
from swing_trader_app.tabs.trade_desk_tab import render_trade_desk
from swing_trader_app.tabs.top_movers_tab import render_top_movers

def format_latest_bar_time(latest_bar_time):
    import pandas as pd

    if latest_bar_time is None or str(latest_bar_time).strip() == "":
        return "Latest bar: unknown"

    raw = str(latest_bar_time).strip()

    # Remove duplicate label if already passed as "Latest bar: ..."
    raw = raw.replace("Latest bar:", "").strip()

    # Handle display strings ending with SGT before pandas parses them.
    # Pandas does not recognize the short label "SGT" reliably and emits a FutureWarning.
    # Example: "2026-05-08 08:00:00 SGT"
    if raw.endswith(" SGT"):
        raw_sgt = raw[:-4].strip()
        ts = pd.to_datetime(raw_sgt, errors="coerce")
        if pd.isna(ts):
            return f"Latest bar: {latest_bar_time}"
        ts = ts.tz_localize("Asia/Singapore") if ts.tzinfo is None else ts.tz_convert("Asia/Singapore")
        return f"Latest bar: {ts.strftime('%Y-%m-%d %H:%M:%S')} SGT"

    # Handle text ending with ET
    # Example: "2026-05-07 20:00:00 ET"
    if raw.endswith(" ET"):
        raw_et = raw[:-3].strip()
        ts = pd.to_datetime(raw_et, errors="coerce")
        if pd.isna(ts):
            return f"Latest bar: {latest_bar_time}"

        ts = ts.tz_localize("America/New_York") if ts.tzinfo is None else ts.tz_convert("America/New_York")
        ts_sgt = ts.tz_convert("Asia/Singapore")
        return f"Latest bar: {ts_sgt.strftime('%Y-%m-%d %H:%M:%S')} SGT"

    # Normal timestamp handling: UTC-aware / offset-aware / naive
    ts = pd.to_datetime(raw, errors="coerce")

    if pd.isna(ts):
        return f"Latest bar: {latest_bar_time}"

    # If no timezone, assume UTC from Yahoo
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")

    ts_sgt = ts.tz_convert("Asia/Singapore")
    return f"Latest bar: {ts_sgt.strftime('%Y-%m-%d %H:%M:%S')} SGT"

def _safe_render_tab(tab_name, render_fn):
    try:
        render_fn(globals())
    except Exception as e:
        import traceback as _traceback
        try:
            _record_app_error(f"tab:{tab_name}", e)
        except Exception:
            pass
        st.error(f"{tab_name} failed: {type(e).__name__}: {e}")
        with st.expander("Show traceback"):
            st.code(_traceback.format_exc())

with tab_sectors:
    _safe_render_tab('sectors', render_sectors)


def _latest_bar_display_value(latest_bar_time) -> str:
    """Return latest-bar timestamp formatted in SGT without the 'Latest bar:' label."""
    try:
        txt = str(format_latest_bar_time(latest_bar_time)).strip()
        if txt.lower().startswith("latest bar:"):
            txt = txt.split(":", 1)[1].strip()
        return txt or "unknown"
    except Exception:
        return str(latest_bar_time or "unknown")


def _normalise_bar_for_compare(latest_bar_time):
    """Parse Yahoo/cache latest-bar timestamps to comparable UTC seconds."""
    try:
        import pandas as pd
        if latest_bar_time is None:
            return None
        raw = str(latest_bar_time).strip()
        if not raw or raw in {"–", "unknown", "None"}:
            return None
        raw = raw.replace("Latest bar:", "").strip()
        # Handle readable labels that pandas may not reliably parse.
        if raw.endswith(" SGT"):
            raw = raw[:-4].strip()
            ts = pd.to_datetime(raw, errors="coerce")
            if pd.isna(ts):
                return None
            ts = ts.tz_localize("Asia/Singapore") if ts.tzinfo is None else ts.tz_convert("Asia/Singapore")
        elif raw.endswith(" ET"):
            raw = raw[:-3].strip()
            ts = pd.to_datetime(raw, errors="coerce")
            if pd.isna(ts):
                return None
            ts = ts.tz_localize("America/New_York") if ts.tzinfo is None else ts.tz_convert("America/New_York")
        else:
            ts = pd.to_datetime(raw, errors="coerce")
            if pd.isna(ts):
                return None
            if ts.tzinfo is None:
                # Yahoo batch/index strings in this app are treated as UTC if no tz.
                ts = ts.tz_localize("UTC")
        return int(ts.tz_convert("UTC").timestamp())
    except Exception:
        return None


def _newer_bar_time_value(a, b):
    """Return whichever bar timestamp is newer, preserving the original value.

    Used after a lightweight freshness probe: the full scan output can sometimes
    derive its latest bar only from rows that pass scanner construction, while
    the probe may have already proven Yahoo has a newer 5m bar.  In that case,
    cache metadata must not be saved with the older displayed bar.
    """
    an = _normalise_bar_for_compare(a)
    bn = _normalise_bar_for_compare(b)
    if an is None and bn is None:
        return a or b or ""
    if an is None:
        return b
    if bn is None:
        return a
    return a if an >= bn else b


def _quick_yahoo_latest_bar_for_market(market: str, meta: dict, sample_size: int = 25) -> dict:
    """Cheap freshness probe: download only 1d/5m bars for a small ticker sample.

    This avoids rebuilding the full scanner cache when Yahoo has not published a
    newer bar than the cache already contains. It is intentionally best-effort:
    on any error the caller should continue with the normal full refresh.
    """
    checked_at = datetime.now(ZoneInfo("Asia/Singapore")).strftime("%Y-%m-%d %H:%M:%S SGT")
    result = {
        "ok": False,
        "checked_at": checked_at,
        "sample_tickers": "",
        "latest_available_bar_time": "",
        "latest_available_bar_sgt": "unknown",
        "cached_latest_bar_time": str((meta or {}).get("latest_bar_time", "")),
        "cached_latest_bar_sgt": _latest_bar_display_value((meta or {}).get("latest_bar_time", "")),
        "previous_cached_bar_sgt": _latest_bar_display_value((meta or {}).get("latest_bar_time", "")),
        "is_newer": True,
        "message": "Freshness probe not run",
    }
    try:
        tickers_csv = str((meta or {}).get("scanned_tickers_csv", ""))
        tickers = [t.strip().upper() for t in tickers_csv.split(",") if t.strip()]
        # Prefer highly liquid/default front of the cached universe; include enough
        # names to survive occasional Yahoo no-data responses but not enough to be costly.
        tickers = list(dict.fromkeys(tickers))[:max(3, int(sample_size))]
        if not tickers:
            result["message"] = "No cached ticker list available for quick freshness check"
            return result
        result["sample_tickers"] = ", ".join(tickers)

        raw = yf.download(
            tickers if len(tickers) > 1 else tickers[0],
            period="1d",
            interval="5m",
            group_by="ticker",
            progress=False,
            threads=True,
            auto_adjust=True,
            prepost=True,
        )
        latest_ts = []
        if raw is None or raw.empty:
            result["message"] = "Yahoo returned empty data for quick freshness check"
            return result

        for tkr in tickers:
            try:
                if isinstance(raw.columns, pd.MultiIndex):
                    lvl0 = raw.columns.get_level_values(0)
                    lvl1 = raw.columns.get_level_values(1)
                    if tkr in lvl0:
                        df_t = raw[tkr].copy()
                    elif tkr in lvl1:
                        df_t = raw.xs(tkr, axis=1, level=1).copy()
                    else:
                        continue
                else:
                    # Single-symbol download returns flat columns.
                    if len(tickers) != 1:
                        continue
                    df_t = raw.copy()
                if df_t is None or df_t.empty or "Close" not in df_t.columns:
                    continue
                df_t = df_t[df_t["Close"].notna()]
                if df_t.empty:
                    continue
                latest_ts.append(pd.Timestamp(df_t.index[-1]))
            except Exception:
                continue
        if not latest_ts:
            result["message"] = "Could not extract any latest 5m bar from Yahoo freshness sample"
            return result

        latest = max(latest_ts)
        result["ok"] = True
        result["latest_available_bar_time"] = str(latest)
        result["latest_available_bar_sgt"] = _latest_bar_display_value(str(latest))
        cached_norm = _normalise_bar_for_compare(result["cached_latest_bar_time"])
        latest_norm = _normalise_bar_for_compare(str(latest))
        if cached_norm is None or latest_norm is None:
            result["is_newer"] = True
            result["message"] = "Could not compare bar timestamps safely; full refresh allowed"
        else:
            result["is_newer"] = latest_norm > cached_norm
            result["message"] = "Newer Yahoo bar available" if result["is_newer"] else "No newer Yahoo bar available"
        return result
    except Exception as e:
        result["message"] = f"Freshness check failed: {type(e).__name__}: {e}"
        return result


def _write_scan_cache_check_meta(market: str, check_info: dict) -> None:
    """Persist last lightweight freshness check into <market>_scan_meta.json for Diagnostics."""
    try:
        paths = _scan_cache_paths(market)
        if not paths["meta"].exists():
            return
        meta = json.loads(paths["meta"].read_text(encoding="utf-8"))
        meta.update({
            "last_data_check_at": check_info.get("checked_at", ""),
            "last_data_check_result": check_info.get("message", ""),
            "last_available_bar_time": check_info.get("latest_available_bar_time", ""),
            "last_available_bar_sgt": check_info.get("latest_available_bar_sgt", "unknown"),
            "last_cached_bar_sgt": check_info.get("cached_latest_bar_sgt", "unknown"),
            "last_previous_cached_bar_sgt": check_info.get("previous_cached_bar_sgt", check_info.get("cached_latest_bar_sgt", "unknown")),
            "last_data_check_sample": check_info.get("sample_tickers", ""),
            "last_data_check_newer": bool(check_info.get("is_newer", True)),
        })
        paths["meta"].write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
        st.session_state["scan_cache_meta"] = meta
    except Exception as e:
        try:
            _record_app_warning("cache_freshness_meta_write", f"Could not write freshness check meta: {e}", extra={"market": market})
        except Exception:
            pass


def _safe_sector_df_for_market(_market_sel: str, _context: str = "sector") -> pd.DataFrame:
    """Fetch sector data without allowing yfinance/cloud errors to break the page."""
    try:
        if _market_sel == "🇺🇸 US":
            return get_sector_performance()
        if _market_sel == "🇸🇬 SGX":
            return get_sg_sector_performance()
        if _market_sel == "🇭🇰 HK":
            return pd.DataFrame({"Sector": ["HK Mixed"], "ETF": ["HK curated"], "Today %": [0.0], "5d %": [0.0], "Price": [0.0], "Status": ["⚪ FLAT"]})
        _df = get_india_sector_performance()
        if isinstance(_df, pd.DataFrame) and not _df.empty and "ETF" in _df.columns:
            _df = _df[_df["ETF"] != "^NSEI"]
        return _df
    except Exception as _e:
        try:
            _record_app_error(_context, _e, extra={"market": _market_sel})
        except Exception:
            pass
        return pd.DataFrame(columns=["Sector", "ETF", "Today %", "5d %", "Price", "Status"])


# ─────────────────────────────────────────────────────────────────────────────
# SCAN BUTTON  (market-aware)
# ─────────────────────────────────────────────────────────────────────────────
col_btn, col_info = st.columns([1, 3])

with col_btn:
    _manual_scan = st.button(f"🚀 Scan {market_sel} Stocks", type="primary")
_strategy_auto_refresh = bool(st.session_state.pop("_force_strategy_rescan", False))

# If the CSV cache is due, first do a cheap Yahoo latest-bar probe.
# When Yahoo has not published a newer 5m bar than the cache already has,
# do NOT rebuild the expensive master scan.  Just record the check in
# Diagnostics and keep using the existing cache.
_cache_due_no_new_data = False
if _cache_refresh_due and not _manual_scan and _loaded_cache is not None:
    _probe = _quick_yahoo_latest_bar_for_market(market_sel, _loaded_cache.get("meta", {}))
    st.session_state["scan_cache_last_data_check"] = _probe
    _write_scan_cache_check_meta(market_sel, _probe)
    if _probe.get("ok") and not _probe.get("is_newer", True):
        _cache_refresh_due = False
        st.session_state["scan_cache_refresh_due"] = False
        _cache_due_no_new_data = True
        _msg = (
            f"✅ Cache freshness checked — no newer Yahoo bar available. "
            f"Available: {_probe.get('latest_available_bar_sgt', 'unknown')} · "
            f"Cached: {_probe.get('cached_latest_bar_sgt', 'unknown')}. "
            "Keeping existing scanner cache; no full Yahoo scan needed."
        )
        st.session_state["_cache_no_new_data_notice"] = _msg
        try:
            _record_scan_note(_msg, context="cache_freshness_check", extra=_probe)
        except Exception:
            pass

run = _manual_scan or _cache_refresh_due or _strategy_auto_refresh
if _strategy_auto_refresh:
    _show_top_spinner(st.session_state.get("_strategy_changed_notice", "🔄 Strategy changed — refreshing scan/grid..."))
elif _cache_due_no_new_data:
    _top_scan_status.info(st.session_state.get("_cache_no_new_data_notice", "Cache checked — no newer Yahoo data available."))
elif _cache_refresh_due and not _manual_scan:
    _show_top_spinner(
        f"⏱️ Cached CSV is older than {effective_refresh_minutes} min and Yahoo has a newer bar — refreshing scan and updating CSV files..."
    )
with col_info:
    # Show sector preview for the active market; never let Cloud/yfinance errors blank the UI
    sdf_preview = _safe_sector_df_for_market(market_sel, "sector_preview")

    if not sdf_preview.empty and "Today %" in sdf_preview.columns:
        gn = sdf_preview[sdf_preview["Today %"] >  0.1]["Sector"].tolist()
        rn = sdf_preview[sdf_preview["Today %"] < -0.1]["Sector"].tolist()
        _always_note = f" + {len(always_include_tickers)} always-include" if always_include_tickers else ""
        universe_note = (
            f"Yahoo/live up to {max_live_universe} + existing {len(_active_tickers)} stocks{_always_note}"
            if use_live_universe else
            f"existing curated watchlist · {len(_active_tickers)} stocks{_always_note}"
        )
        st.info(
            f"**{market_sel}** · {universe_note} · "
            f"Top **{top_n_sectors} green** → longs: {', '.join(gn[:top_n_sectors]) or 'none'} · "
            f"Top **{top_n_sectors} red** → shorts: {', '.join(rn[:top_n_sectors]) or 'none'}"
        )

if run:
    st.session_state.pop("_cache_no_new_data_notice", None)
    # Get sector data for the selected market; if unavailable, continue scanning the ticker universe
    sdf = _safe_sector_df_for_market(market_sel, "scan_sector_fetch")
    active_sector_etfs = SECTOR_ETFS if market_sel == "🇺🇸 US" else (INDIA_SECTOR_ETFS if market_sel == "🇮🇳 India" else {})

    if sdf.empty or "Today %" not in sdf.columns:
        try:
            _record_app_warning("scan_sector_fetch", "Sector data unavailable; continuing scan without sector filtering", extra={"market": market_sel})
        except Exception:
            pass
        st.warning("Sector data unavailable. Continuing scan using the selected market ticker universe without sector filtering.")
        sdf = pd.DataFrame({"Sector": ["Mixed"], "ETF": [""], "Today %": [0.0], "5d %": [0.0], "Price": [0.0], "Status": ["⚪ FLAT"]})

    green_sectors = sdf[sdf["Today %"] >  0.1]["Sector"].tolist()
    red_sectors   = sdf[sdf["Today %"] < -0.1]["Sector"].tolist()
    if not green_sectors and not red_sectors:
        # v15.6: suppress the warning when market is closed (all-flat is expected)
        # or when the sector df carries _market_closed=True from the new fetch logic.
        _mkt_closed = bool(sdf.get("_market_closed", pd.Series([False])).any()) if "_market_closed" in sdf.columns else False
        if not _mkt_closed:
            try:
                _record_app_warning("scan_flat_sectors", "All sectors flat or sector data unavailable; scanner will still run on the selected ticker universe", extra={"market": market_sel})
            except Exception:
                pass
            st.info("🕐 Sector data shows all-flat — market may be closed or data is loading. Scanner will run on the full ticker universe.")

    extra_tickers = [t.strip().upper() for t in extra_input.split(",") if t.strip()]

    if False and not green_sectors and not red_sectors:
        st.warning("All sectors flat — market may be closed or data unavailable.")
    else:
        # Fetch live ETF holdings only for US (India/SGX/HK use static ticker lists)
        live_sectors = {}
        if market_sel == "🇺🇸 US":
            _show_top_spinner("📡 Fetching live US ETF holdings...")
            live_sectors = fetch_sector_constituents(target_per_sector=25)
            if extra_tickers and green_sectors:
                first_green = green_sectors[0]
                existing    = live_sectors.get(first_green, {}).get("stocks", [])
                merged      = list(dict.fromkeys(extra_tickers + existing))
                if first_green in live_sectors:
                    live_sectors[first_green]["stocks"] = merged

            with st.expander("📋 Holdings per sector", expanded=False):
                rows = [{"Sector": sn, "ETF": sd.get("etf",""),
                         "Source": sd.get("source","–"),
                         "# Stocks": sd.get("count", len(sd.get("stocks",[]))),
                         "Top 8": ", ".join(sd.get("stocks",[])[:8])}
                        for sn, sd in live_sectors.items()]
                st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

        # Build active ticker list. In live mode this is deliberately:
        #   Yahoo/live market tickers + the full existing curated ticker list
        # Then forced tickers are added on top. This prevents existing names
        # such as UUUU or APP from disappearing from the scan/Diagnostics tab.
        if use_live_universe:
            _show_top_spinner("🌐 Fetching Yahoo/live market universe...")
            with st.spinner("🌐 Fetching Yahoo/live market universe..."):
                live_tickers, live_source = fetch_live_market_universe(
                    market_sel, max_symbols=max_live_universe
                )
            active_tickers = _unique_keep_order(list(live_tickers) + list(_active_tickers))
            universe_source = (
                f"{live_source} + existing curated watchlist"
                if live_tickers else
                "existing curated watchlist — live market universe unavailable"
            )
        else:
            live_tickers = []
            active_tickers = list(_active_tickers)
            universe_source = "existing curated watchlist"

        forced_tickers = _unique_keep_order(always_include_tickers + extra_tickers)
        if forced_tickers:
            active_tickers = _unique_keep_order(forced_tickers + active_tickers)
            universe_source = f"{universe_source} + always-include/extra tickers"

        _show_top_spinner(
            f"📊 Scanning <b>{len(active_tickers)} {market_sel} stocks</b> for signals... "
            f"Universe: <b>{universe_source}</b> · "
            f"Live: <b>{len(live_tickers)}</b> · Existing: <b>{len(_active_tickers)}</b>"
        )

        try:
            with st.spinner(f"Scanning {len(active_tickers)} stocks..."):
                # v15.9: check if the in-memory master scan is still valid for this
                # exact ticker set + sector context before calling fetch_analysis.
                # fetch_analysis HAS @st.cache_data(ttl=3600) but _cache_refresh_due
                # (disk CSV age check) fires on every rerender, causing unnecessary
                # rescans even when Streamlit's own cache has valid data.
                # Guard: if ticker list, market, and freshness bucket are unchanged
                # AND df_long_master is already populated, skip the re-scan.
                _scan_signature = (
                    tuple(sorted(active_tickers)),
                    market_sel,
                    str(freshness_cache_bucket),
                    str(regime),
                )
                _cached_sig = st.session_state.get("_last_scan_signature")
                _has_master  = (
                    not st.session_state.get("df_long_master", pd.DataFrame()).empty
                    or not st.session_state.get("df_short_master", pd.DataFrame()).empty
                )
                _skip_rescan = (
                    not _manual_scan            # not a user-triggered scan
                    and _has_master             # already have results
                    and _cached_sig == _scan_signature  # same context
                )
                if _skip_rescan:
                    # Reuse existing master without hitting Yahoo/yfinance
                    df_long    = st.session_state.get("df_long_master",    pd.DataFrame())
                    df_short   = st.session_state.get("df_short_master",   pd.DataFrame())
                    df_operator= st.session_state.get("df_operator_master",pd.DataFrame())
                    st.session_state["_cache_no_new_data_notice"] = (
                        "✅ Reusing cached scan results — ticker universe and market unchanged."
                    )
                else:
                    df_long, df_short, df_operator = fetch_analysis(
                        tuple(green_sectors), tuple(red_sectors),
                        regime, skip_earnings, top_n_sectors,
                        strategy_mode="Discovery",
                        live_sectors=live_sectors if live_sectors else None,
                        market_tickers=tuple(active_tickers),
                        enable_options=enable_options,
                        data_freshness_bucket=freshness_cache_bucket,
                    )
                    st.session_state["_last_scan_signature"] = _scan_signature
        except Exception as _scan_e:
            try:
                _record_app_error("fetch_analysis_call", _scan_e, extra={"market": market_sel, "ticker_count": len(active_tickers)})
            except Exception:
                pass
            _top_scan_status.error(f"❌ Scan failed: {type(_scan_e).__name__}: {_scan_e}. Open 🔍 Diagnostics → App errors for details.")
            df_long, df_short, df_operator = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        # Store the broad Yahoo scan as MASTER, then apply the selected strategy
        # locally.  Strategy dropdown changes can reuse these master dataframes
        # without another Yahoo download.
        df_long_master = df_long.copy()
        df_short_master = df_short.copy()
        df_operator_master = df_operator.copy()
        df_long, df_short, df_operator = _apply_strategy_from_master(
            df_long_master, df_short_master, df_operator_master, swing_mode,
            min_prob_long=min_prob_long, min_prob_short=min_prob_short,
            req_stoch=req_stoch, req_bb=req_bb, req_accel=req_accel,
            req_s_stoch=req_s_stoch, req_s_bb=req_s_bb, req_s_decel=req_s_decel,
            opt_required=opt_required, enable_options=enable_options,
        )

        _latest_bar_from_scan = _latest_bar_time_from_df(df_long_master) or _latest_bar_time_from_df(df_short_master) or "unknown"
        _fresh_probe = st.session_state.get("scan_cache_last_data_check", {}) or {}
        _probe_latest = _fresh_probe.get("latest_available_bar_time") if _fresh_probe.get("ok") else ""
        _latest_bar_for_cache = _newer_bar_time_value(_latest_bar_from_scan, _probe_latest)
        _latest_bar_for_status = format_latest_bar_time(_latest_bar_for_cache)
        _top_scan_status.success(
            f"✅ Yahoo master scan refreshed for **{len(active_tickers)} {market_sel} stocks** · "
            f"Latest bar: **{_latest_bar_display_value(_latest_bar_for_status)}** · "
            f"Displaying **{swing_mode}** from cache · "
            f"Long: **{len(df_long)}** / master {len(df_long_master)} · "
            f"Short: **{len(df_short)}** / master {len(df_short_master)} · Operator: **{len(df_operator)}**"
        )
        st.session_state["last_scan_strategy"] = swing_mode
        if _strategy_auto_refresh:
            st.session_state["_strategy_changed_notice"] = (
                f"✅ Strategy changed to **{swing_mode}** — grid refreshed with new scan results."
            )
        if df_long.empty and df_short.empty and df_operator.empty:
            try:
                _record_app_warning(
                    "scan_no_results_after_fetch",
                    "Scan completed but returned no long/short/operator rows before sidebar filters",
                    extra={"market": market_sel, "ticker_count": len(active_tickers), "debug": st.session_state.get("last_scan_debug", {})},
                )
            except Exception:
                pass
            st.warning("Scan completed but no stocks passed the current data/filters. Check 🔍 Diagnostics → App errors and Scan debug summary.")

        # Sidebar and strategy filters were already applied by _apply_strategy_from_master().

        st.session_state["df_long_master"]     = df_long_master
        st.session_state["df_short_master"]    = df_short_master
        st.session_state["df_operator_master"] = df_operator_master
        st.session_state["df_long"]            = df_long
        st.session_state["df_short"]           = df_short
        st.session_state["df_operator"]        = df_operator
        st.session_state["live_sectors_cache"] = live_sectors
        st.session_state["last_market"]        = market_sel
        st.session_state["last_universe_source"] = universe_source
        st.session_state["last_universe_count"]  = len(active_tickers)
        st.session_state["last_live_ticker_count"] = len(live_tickers)
        st.session_state["last_existing_ticker_count"] = len(_active_tickers)
        st.session_state["last_scanned_tickers"]     = list(active_tickers)
        st.session_state["last_scanned_tickers_csv"]  = ", ".join(active_tickers)
        st.session_state["last_always_include_csv"]   = ", ".join(always_include_tickers)
        st.session_state["last_always_include_list"]  = list(always_include_tickers)
        # v12: record the options state at scan time + how many candidates
        # actually received option-chain data. Used by the banner below to
        # tell the user when their toggle differs from the displayed scan.
        _opt_count_l = int((df_long["Implied Move 2W"] != "–").sum())  \
                       if (not df_long.empty and "Implied Move 2W" in df_long.columns) else 0
        _opt_count_s = int((df_short["Implied Move 2W"] != "–").sum()) \
                       if (not df_short.empty and "Implied Move 2W" in df_short.columns) else 0
        st.session_state["last_scan_opt_enabled"] = enable_options
        st.session_state["last_scan_opt_count"]   = _opt_count_l + _opt_count_s
        st.session_state["last_scan_market"]      = market_sel

        # Persist completed scan to CSV so future app starts load instantly.
        _saved_cache_meta = _save_scan_cache(
            market_sel,
            df_long_master,
            df_short_master,
            df_operator_master,
            {
                "cache_type": "master_scan_v1",
                "universe_source": universe_source,
                "universe_count": len(active_tickers),
                "live_ticker_count": len(live_tickers),
                "existing_ticker_count": len(_active_tickers),
                "scanned_tickers_csv": ", ".join(active_tickers),
                "options_enabled": bool(enable_options),
                "options_count": int(_opt_count_l + _opt_count_s),
                "strategy_mode": "MASTER",
                "display_strategy_mode": str(swing_mode),
                "bucket_cap": bool(use_bucket_cap),
                "top_n_sectors": int(top_n_sectors),
                "min_prob_long": int(min_prob_long),
                "min_prob_short": int(min_prob_short),
                "skip_earnings": bool(skip_earnings),
                "effective_refresh_minutes": int(effective_refresh_minutes),
                "market_live_now": bool(_is_market_live_now(market_sel)),
                "freshness_cache_bucket": str(freshness_cache_bucket),
                "latest_bar_time": _latest_bar_for_cache,
                "data_source": "yahoo_daily_6mo_plus_intraday_5m_overlay",
                "yahoo_delay_note": "Yahoo quotes may still be exchange-delayed; app cache TTL is shortened during market hours.",
                "always_include_tickers": ", ".join(always_include_tickers),
                "always_include_count": len(always_include_tickers),
            },
        )
        if _saved_cache_meta:
            # If this scan was triggered after a lightweight freshness probe,
            # update the diagnostics fields so Available latest bar and Current
            # cached latest bar no longer look inconsistent after the refresh.
            try:
                _fresh_probe = st.session_state.get("scan_cache_last_data_check", {}) or {}
                if _fresh_probe:
                    _saved_cache_meta.update({
                        "last_data_check_at": _fresh_probe.get("checked_at", ""),
                        "last_data_check_result": "Newer Yahoo bar was available — full scanner cache refreshed",
                        "last_available_bar_time": _fresh_probe.get("latest_available_bar_time", ""),
                        "last_available_bar_sgt": _fresh_probe.get("latest_available_bar_sgt", "unknown"),
                        "last_previous_cached_bar_sgt": _fresh_probe.get("previous_cached_bar_sgt", _fresh_probe.get("cached_latest_bar_sgt", "unknown")),
                        "last_cached_bar_sgt": _latest_bar_display_value(_saved_cache_meta.get("latest_bar_time", "")),
                        "last_data_check_sample": _fresh_probe.get("sample_tickers", ""),
                        "last_data_check_newer": False,
                    })
                    _paths = _scan_cache_paths(market_sel)
                    _paths["meta"].write_text(json.dumps(_saved_cache_meta, indent=2, default=str), encoding="utf-8")
                    st.session_state["scan_cache_last_data_check"] = {
                        **_fresh_probe,
                        "message": "Newer Yahoo bar was available — full scanner cache refreshed",
                        "cached_latest_bar_sgt": _saved_cache_meta.get("last_cached_bar_sgt", "unknown"),
                        "previous_cached_bar_sgt": _saved_cache_meta.get("last_previous_cached_bar_sgt", "unknown"),
                        "is_newer": False,
                    }
            except Exception as _e:
                try:
                    _record_app_warning("cache_freshness_post_save_meta", f"Could not update post-refresh freshness meta: {_e}", extra={"market": market_sel})
                except Exception:
                    pass
            st.session_state["scan_cache_meta"] = _saved_cache_meta
            st.session_state["scan_cache_timing"] = _cache_timing_info(_saved_cache_meta, effective_refresh_minutes)
            st.session_state["scan_cache_refresh_minutes"] = effective_refresh_minutes
            st.session_state["scan_cache_refresh_due"] = False

df_long  = st.session_state.get("df_long",  pd.DataFrame())
df_short = st.session_state.get("df_short", pd.DataFrame())
df_operator = st.session_state.get("df_operator", pd.DataFrame())
last_market = st.session_state.get("last_market", market_sel)
last_universe_source = st.session_state.get("last_universe_source", "curated hard-coded watchlist")
last_universe_count = st.session_state.get("last_universe_count", len(_active_tickers))
last_scanned_tickers = st.session_state.get("last_scanned_tickers", [])
last_scanned_tickers_csv = st.session_state.get("last_scanned_tickers_csv", "")
last_live_ticker_count = st.session_state.get("last_live_ticker_count", 0)
last_existing_ticker_count = st.session_state.get("last_existing_ticker_count", len(_active_tickers))

# ─────────────────────────────────────────────────────────────────────────────
# v12: Toggle-state banner
# Tells the user when the current "Use options data" checkbox value differs
# from what was used to produce the displayed tables, so they know whether
# they need to click 🚀 Scan again. Also reports how many candidates in the
# last scan actually received option-chain data — useful for diagnosing
# yfinance rate limits or non-US universes where options aren't available.
# ─────────────────────────────────────────────────────────────────────────────
if "last_scan_opt_enabled" in st.session_state:
    _last_state = st.session_state["last_scan_opt_enabled"]
    _last_n     = st.session_state.get("last_scan_opt_count", 0)
    _last_mkt   = st.session_state.get("last_scan_market", "")
    if _last_state != enable_options:
        st.warning(
            f"⚠️ Options toggle changed since the last scan "
            f"(was **{'ON' if _last_state else 'OFF'}**, now "
            f"**{'ON' if enable_options else 'OFF'}**). "
            f"Click **🚀 Scan** to refresh — toggling alone does not re-run the scan."
        )
    elif enable_options:
        if _last_n > 0:
            st.caption(
                f"🧩 Options enrichment was ON in the last scan · "
                f"{_last_n} candidate(s) received option-chain data "
                f"(market: {_last_mkt})."
            )
        elif _last_mkt == "🇸🇬 SGX":
            st.caption(
                "🧩 Options enrichment is ON, but SGX has no liquid single-stock "
                "options market — there is no option chain to fetch. The toggle "
                "has no effect on SGX scans by design."
            )
        elif _last_mkt == "🇭🇰 HK":
            st.info("🧩 Options enrichment is ON, but HK single-stock option-chain enrichment is not supported here. The stock scan still works using Yahoo price/volume data.")
        elif _last_mkt == "🇮🇳 India" and not _nse_opt_available:
            st.caption(
                "🧩 Options enrichment is ON, but `nsepython` is not installed. "
                "Run `pip install nsepython` and restart Streamlit to enable "
                "India F&O option signals."
            )
        elif _last_mkt == "🇮🇳 India":
            st.caption(
                "🧩 Options enrichment was ON for India, but no candidates "
                "received option-chain data. Likely causes: NSE rate-limited "
                "(wait ~60 seconds and retry), no candidate cleared the "
                "technical pre-filter, or the tickers scanned aren't in NSE's "
                "F&O list (~200 stocks have option chains)."
            )
        else:
            st.caption(
                "🧩 Options enrichment was ON in the last scan, but no candidates "
                "received option-chain data. Likely causes: yfinance rate-limited, "
                "or no candidate cleared the technical pre-filter "
                "(≥4 long signals or ≥3 short signals)."
            )

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — LONG
# ─────────────────────────────────────────────────────────────────────────────
with tab_long:
    _safe_render_tab('long', render_long)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — SHORT
# ─────────────────────────────────────────────────────────────────────────────
with tab_short:
    _safe_render_tab('short', render_short)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3b — OPERATOR ACTIVITY (universe-wide manipulation footprint scan)
# ─────────────────────────────────────────────────────────────────────────────
with tab_operator:
    _safe_render_tab('operator', render_operator_activity)



# ─────────────────────────────────────────────────────────────────────────────
# TAB 4 — SIDE BY SIDE
# ─────────────────────────────────────────────────────────────────────────────
with tab_both:
    _safe_render_tab('both', render_both)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 5 — ETF HOLDINGS
# ─────────────────────────────────────────────────────────────────────────────
with tab_etf:
    _safe_render_tab('etf', render_etf_holdings)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 6 — INDIVIDUAL STOCK ANALYSIS
# Full chart + all indicators + signal scorecard + risk levels
# ─────────────────────────────────────────────────────────────────────────────
with tab_stock:
    _safe_render_tab('stock', render_stock_analysis)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 7 — DIAGNOSTICS
# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# TAB — EARNINGS CALENDAR
# ─────────────────────────────────────────────────────────────────────────────
with tab_swing_picks:
    _safe_render_tab('swing_picks', render_swing_picks)


# ─────────────────────────────────────────────────────────────────────────────
# TAB — TOP MOVERS / LOSERS
# ─────────────────────────────────────────────────────────────────────────────
with tab_top_movers:
    _safe_render_tab('top_movers', render_top_movers)


# ─────────────────────────────────────────────────────────────────────────────
# TAB — TRADE DESK / EXECUTION TOOLS
# Adds practical swing-trading workflow tools without changing scanner logic:
# trade plans, position sizing, setup quality, market breadth/risk mode, journal.
# ─────────────────────────────────────────────────────────────────────────────
with tab_trade_desk:
    _safe_render_tab('trade_desk', render_trade_desk)



# ─────────────────────────────────────────────────────────────────────────────
# TAB — STRATEGY LAB / OPTIONAL ML QUALITY FILTER
# ─────────────────────────────────────────────────────────────────────────────
with tab_strategy:
    _safe_render_tab('strategy', render_strategy_lab)


# ─────────────────────────────────────────────────────────────────────────────
# TAB — EARNINGS CALENDAR
# ─────────────────────────────────────────────────────────────────────────────
with tab_earn:
    _safe_render_tab('earn', render_earnings)




# ─────────────────────────────────────────────────────────────────────────────
# TAB — EVENT PREDICTOR: Earnings + News + Orders
# ─────────────────────────────────────────────────────────────────────────────
with tab_event:
    _safe_render_tab('event', render_event_predictor)




# ─────────────────────────────────────────────────────────────────────────────
# LONG-TERM TAB — ETF-sourced holdings with quality scoring
# ─────────────────────────────────────────────────────────────────────────────

# ETFs/funds with strong long-term track records — we pull their TOP HOLDINGS
LT_ETF_US = {
    # ── Core Quality/Growth ───────────────────────────────────────────────────
    "QQQ":   {"name": "Invesco Nasdaq-100",           "theme": "US Tech/Growth",      "ret1y": 11.2, "ret3y": 14.8, "ret5y": 18.2},
    "VGT":   {"name": "Vanguard IT ETF",              "theme": "US Technology",        "ret1y": 12.1, "ret3y": 15.9, "ret5y": 19.4},
    "SCHG":  {"name": "Schwab US Large Cap Growth",   "theme": "US Growth",            "ret1y": 10.8, "ret3y": 14.1, "ret5y": 17.8},
    "QUAL":  {"name": "iShares MSCI USA Quality",     "theme": "Quality Factor",       "ret1y":  9.4, "ret3y": 12.3, "ret5y": 14.6},
    "MOAT":  {"name": "VanEck Wide Moat ETF",         "theme": "Wide Moat",            "ret1y":  8.7, "ret3y": 11.4, "ret5y": 13.9},
    "VUG":   {"name": "Vanguard Growth ETF",          "theme": "US Large Growth",      "ret1y": 10.2, "ret3y": 13.5, "ret5y": 16.2},
    "DGRW":  {"name": "WisdomTree Div Growth",        "theme": "US Div Growth",        "ret1y":  8.1, "ret3y": 10.9, "ret5y": 13.1},
    # ── High-returning sector ETFs ────────────────────────────────────────────
    "SOXX":  {"name": "iShares Semiconductor",        "theme": "Semiconductors",       "ret1y":  8.3, "ret3y": 16.2, "ret5y": 22.1},
    "IGV":   {"name": "iShares Software ETF",         "theme": "Software",             "ret1y": 10.4, "ret3y": 13.7, "ret5y": 16.8},
    "XLK":   {"name": "SPDR Technology",              "theme": "Technology",           "ret1y": 11.5, "ret3y": 14.9, "ret5y": 18.3},
    "XLV":   {"name": "SPDR Healthcare",              "theme": "Healthcare",           "ret1y":  6.2, "ret3y":  8.8, "ret5y": 11.4},
    "XLF":   {"name": "SPDR Financials",              "theme": "Financials",           "ret1y": 14.1, "ret3y": 11.2, "ret5y": 12.7},
    "CIBR":  {"name": "First Trust Cybersecurity",    "theme": "Cybersecurity",        "ret1y": 10.3, "ret3y": 12.1, "ret5y": 14.2},
    "PAVE":  {"name": "Global X US Infrastructure",   "theme": "Infrastructure",       "ret1y": 11.8, "ret3y": 13.4, "ret5y": 15.3},
    # ── Thematic ─────────────────────────────────────────────────────────────
    "BOTZ":  {"name": "Global X Robotics & AI",       "theme": "AI & Robotics",        "ret1y":  6.4, "ret3y":  8.9, "ret5y": 11.8},
    "AIQ":   {"name": "Global X AI & Tech",           "theme": "Artificial Intel",     "ret1y":  9.1, "ret3y": 11.2, "ret5y": 13.5},
    "CLOU":  {"name": "Global X Cloud Computing",     "theme": "Cloud Computing",      "ret1y":  7.8, "ret3y":  9.4, "ret5y": 10.9},
    "ARKK":  {"name": "ARK Innovation ETF",           "theme": "Disruptive Innov",     "ret1y": -2.1, "ret3y":  1.4, "ret5y":  8.1},
    "WCLD":  {"name": "WisdomTree Cloud",             "theme": "Cloud/SaaS",           "ret1y":  7.2, "ret3y":  9.1, "ret5y": 11.2},
    "DRIV":  {"name": "Global X Autonomous/EV",       "theme": "EV/Auto",              "ret1y":  5.1, "ret3y":  7.8, "ret5y": 10.3},
    "ICLN":  {"name": "iShares Clean Energy",         "theme": "Clean Energy",         "ret1y": -8.4, "ret3y": -3.1, "ret5y":  6.2},
    # ── India ────────────────────────────────────────────────────────────────
    "INDA":  {"name": "iShares MSCI India",           "theme": "India Broad",          "ret1y":  8.9, "ret3y": 10.2, "ret5y": 12.4},
    "INDY":  {"name": "iShares India 50",             "theme": "India Large Cap",      "ret1y":  8.4, "ret3y":  9.8, "ret5y": 11.9},
    "SMIN":  {"name": "iShares India Small Cap",      "theme": "India Small Cap",      "ret1y": 10.2, "ret3y": 12.4, "ret5y": 14.8},
    "EPI":   {"name": "WisdomTree India Earnings",    "theme": "India Value",          "ret1y":  9.1, "ret3y": 10.5, "ret5y": 12.1},
}

LT_ETF_SG = {
    # ── ETFs that hold actual SGX-listed stocks ───────────────────────────────
    "EWS":    {"name": "iShares MSCI Singapore",      "theme": "SG Broad Market",    "ret1y": 12.4, "ret3y":  6.8, "ret5y":  8.3},
    "EWS.SI": {"name": "iShares MSCI Singapore (SGX)","theme": "SG Broad Market",    "ret1y": 12.4, "ret3y":  6.8, "ret5y":  8.3},
    "VPL":    {"name": "Vanguard Pacific ETF",        "theme": "Asia Pacific",       "ret1y":  8.1, "ret3y":  5.9, "ret5y":  7.4},
    "AAXJ":   {"name": "iShares MSCI Asia ex-Japan",  "theme": "Asia ex-Japan",      "ret1y": 10.3, "ret3y":  7.2, "ret5y":  8.9},
    "EPHE":   {"name": "iShares MSCI Philippines",    "theme": "SE Asia",            "ret1y":  3.1, "ret3y":  2.4, "ret5y":  4.1},
    "ASEA":   {"name": "Global X ASEAN ETF",          "theme": "SE Asia",            "ret1y":  6.2, "ret3y":  4.1, "ret5y":  5.2},
    "AIA":    {"name": "iShares Asia 50 ETF",         "theme": "Asia Large Cap",     "ret1y": 11.2, "ret3y":  8.3, "ret5y":  9.1},
    # ── SGX-listed ETFs ───────────────────────────────────────────────────────
    "SRT.SI": {"name": "CSOP iEdge S-REIT Leaders",  "theme": "SG REITs",           "ret1y":  9.1, "ret3y":  4.2, "ret5y":  5.8},
    "CLR.SI": {"name": "Lion-Phillip S-REIT ETF",    "theme": "SG REITs",           "ret1y":  8.8, "ret3y":  4.0, "ret5y":  5.6},
    "ES3.SI": {"name": "SPDR STI ETF",               "theme": "STI Blue Chips",     "ret1y": 29.1, "ret3y": 13.4, "ret5y":  9.8},
    "G3B.SI": {"name": "Nikko AM STI ETF",           "theme": "STI Blue Chips",     "ret1y": 29.0, "ret3y": 13.3, "ret5y":  9.7},
}

# Funds/instruments giving 10-12%+ returns for Singapore investors
HIGH_RETURN_FUNDS = [
    # ETF / Index
    {"Name":"Vanguard S&P 500 (VUAA.L)",     "Type":"UCITS ETF",      "Ret5Y":"~15%", "Min":"S$1",    "Risk":"Med",  "Access":"IBKR/Moomoo","Note":"Irish-domiciled, 0% withholding tax for SG investors"},
    {"Name":"iShares S&P 500 (CSPX.L)",      "Type":"UCITS ETF",      "Ret5Y":"~15%", "Min":"S$1",    "Risk":"Med",  "Access":"IBKR",        "Note":"Accumulating — no dividend drag"},
    {"Name":"Nasdaq-100 (XNAS.L / ANAU.DE)", "Type":"UCITS ETF",      "Ret5Y":"~17%", "Min":"S$1",    "Risk":"Med-H","Access":"IBKR",        "Note":"Higher vol than S&P 500"},
    {"Name":"Semiconductor (SOXX)",           "Type":"US ETF",         "Ret5Y":"~22%", "Min":"S$1",    "Risk":"High", "Access":"IBKR/Tiger",  "Note":"High beta — best in upcycles"},
    {"Name":"iShares India Smallcap (SMIN)",  "Type":"US ETF",         "Ret5Y":"~15%", "Min":"S$1",    "Risk":"High", "Access":"IBKR",        "Note":"India structural growth + smallcap premium"},
    # RSPs / Regular savings
    {"Name":"POEMS Share Builders Plan",      "Type":"RSP",            "Ret5Y":"~12%", "Min":"S$100/m","Risk":"Med",  "Access":"Phillip",     "Note":"Monthly DCA into STI ETF or blue chips"},
    {"Name":"Endowus Fund Smart",             "Type":"Robo/Fund",      "Ret5Y":"~12%", "Min":"S$1k",   "Risk":"Med",  "Access":"Endowus",     "Note":"100% equity portfolio — Dimensional/Vanguard"},
    {"Name":"Syfe Equity100",                 "Type":"Robo",           "Ret5Y":"~14%", "Min":"S$1",    "Risk":"Med-H","Access":"Syfe",        "Note":"Global equity, auto-rebalanced"},
    {"Name":"StashAway 36% Risk",             "Type":"Robo",           "Ret5Y":"~11%", "Min":"S$0",    "Risk":"Med",  "Access":"StashAway",   "Note":"ERAA risk-managed, diversified"},
    {"Name":"Manulife Global Multi-Asset",    "Type":"Unit Trust",     "Ret5Y":"~10%", "Min":"S$1k",   "Risk":"Med",  "Access":"Banks/FAs",   "Note":"Available via CPF-OA investment scheme"},
    # CPF-investible
    {"Name":"NIKKO AM STI ETF (G3B)",         "Type":"CPF-investible", "Ret5Y":"~10%", "Min":"S$500",  "Risk":"Med",  "Access":"CPF-OA",      "Note":"29% STI return over 12m to Apr 2026"},
    {"Name":"SPDR STI ETF (ES3)",             "Type":"CPF-investible", "Ret5Y":"~10%", "Min":"S$500",  "Risk":"Med",  "Access":"CPF-OA",      "Note":"Track STI, liquid, low TER 0.30%"},
    # Bonds / alternatives
    {"Name":"Singapore Savings Bonds (SSB)",  "Type":"Capital-safe",   "Ret5Y":"~3%",  "Min":"S$500",  "Risk":"None", "Access":"DBS/OCBC/UOB","Note":"Govt-backed, current 10Y avg ~3.0% pa"},
    {"Name":"T-bills (6-month)",              "Type":"Capital-safe",   "Ret5Y":"~3.7%","Min":"S$1k",   "Risk":"None", "Access":"SGX/Banks",   "Note":"Current yield ~3.7% — parking cash"},
]


with tab_lt:
    _safe_render_tab('lt', render_long_term)


CACHE_DIR = Path("scanner_cache")

with tab_diag:
    _safe_render_tab('diag', render_diagnostics)


# ─────────────────────────────────────────────────────────────────────────────
# TAB — ACCURACY LAB / WALK-FORWARD BACKTEST
# Keeps the scanner logic unchanged. This tab only validates past signal quality.
# ─────────────────────────────────────────────────────────────────────────────
with tab_backtest:
    _safe_render_tab('backtest', render_accuracy_lab)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 8 — HELP
# ─────────────────────────────────────────────────────────────────────────────
with tab_help:
    _safe_render_tab('help', render_help)

