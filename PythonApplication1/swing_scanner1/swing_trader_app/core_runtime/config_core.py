"""Extracted runtime section from app_runtime.py lines 419-757.
Loaded by app_runtime with exec(..., globals()) to preserve the original single-file behavior.

v-refactor: Ticker universe is now imported from universe_data.py (single source of truth).
US_TICKERS  = existing curated watchlist  +  S&P 500  +  NASDAQ-100  (merged, deduplicated)
SG_TICKERS  = existing SGX blue-chips/REITs/growth  +  SGX Mainboard liquid
INDIA_TICKERS = existing curated  +  Nifty 50  +  Nifty Next-50  +  Midcap-50
HK_TICKERS  = existing curated  +  Hang Seng  +  HSI Tech constituents
"""
import sys as _sys, pathlib as _pathlib

# ─────────────────────────────────────────────────────────────────────────────
# Import merged ticker lists from universe_data (single source of truth)
# ─────────────────────────────────────────────────────────────────────────────
_tabs_dir = _pathlib.Path(__file__).resolve().parent.parent / "tabs"
if str(_tabs_dir) not in _sys.path:
    _sys.path.insert(0, str(_tabs_dir.parent))

from swing_trader_app.tabs.universe_data import (
    US_TICKERS,
    SG_TICKERS,
    SGX_LIQUID_FALLBACK_TICKERS,
    HK_TICKERS,
    HK_VOLATILE_TICKERS,
    INDIA_TICKERS,
    BASE_TICKERS,
    get_tickers_for_market,
)


# ─────────────────────────────────────────────────────────────────────────────
# SECTOR ETF MAP
# ─────────────────────────────────────────────────────────────────────────────
SECTOR_ETFS = {
    "Technology":        "XLK",
    "Semiconductors":    "SOXX",
    "Communication":     "XLC",
    "Consumer Discret":  "XLY",
    "Financials":        "XLF",
    "Healthcare":        "XLV",
    "Energy":            "XLE",
    "Industrials":       "XLI",
    "Materials":         "XLB",
    "Clean Energy":      "ICLN",
    "Biotech":           "XBI",
    "Crypto/Blockchain": "BITO",
    "China Tech":        "KWEB",
    "EV / Autos":        "DRIV",
    "Cloud / SaaS":      "WCLD",
}

# ── India NSE sector indices ──────────────────────────────────────────────────
INDIA_SECTOR_ETFS = {
    "Nifty 50":       "^NSEI",
    "Banking":        "^NSEBANK",
    "IT":             "^CNXIT",
    "Pharma":         "^CNXPHARMA",
    "Auto":           "^CNXAUTO",
    "FMCG":           "^CNXFMCG",
    "PSU Bank":       "^CNXPSUBANK",
    "Energy":         "^CNXENERGY",
    "Metal":          "^CNXMETAL",
    "Realty":         "^CNXREALTY",
    "Infrastructure": "^CNXINFRA",
    "Financial Svc":  "^CNXFINSERVICE",
    "Midcap":         "^CNXMIDCAP",
    "Smallcap":       "^CNXSMALLCAP",
}

# ── SGX sector groups (avg of stocks — no liquid sector ETFs on SGX) ──────────
SG_SECTOR_GROUPS = {
    "Banks":       ["D05.SI","O39.SI","U11.SI"],
    "REITs":       ["C38U.SI","A17U.SI","M44U.SI","N2IU.SI"],
    "Industrials": ["BN4.SI","S58.SI","V03.SI"],
    "Telecoms":    ["Z74.SI"],
    "Transport":   ["C6L.SI","C52.SI"],
    "Property":    ["U14.SI","H78.SI"],
    "Energy":      ["U96.SI"],
    "Shipping":    ["BS6.SI","S51.SI"],
    "Finance":     ["S68.SI","AIY.SI"],
    "Tech":        ["558.SI","8AZ.SI","MZH.SI","1D0.SI"],
}

# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL WEIGHTS  — v5 exact values
# ─────────────────────────────────────────────────────────────────────────────
LONG_WEIGHTS = {
    # ── Tier 1: High accuracy (>0.68) — volume + momentum confirmation ────────
    "vol_surge_up":    0.76,   # green candle + 2x vol + 1.5% up — #1 predictor
    "vol_breakout":    0.73,   # price at 10d high + vol ≥1.8× — breakout confirmed
    "pocket_pivot":    0.71,   # above MA20, vol surge on up day
    "stoch_confirmed": 0.71,   # oversold bounce — works in uptrends
    "bb_bull_squeeze": 0.69,   # compression before expansion
    "rs_momentum":     0.70,   # RS line trending up vs SPY (20d)
    "rel_strength":    0.69,   # stock beat SPY last 5 days
    "weekly_trend":    0.72,   # MA20 > MA60 OR breakout above MA20 on volume
    # ── Tier 2: Good context signals (0.63–0.68) ──────────────────────────────
    "full_ma_stack":   0.68,   # NEW — price > EMA8 > EMA21 > MA20 > MA60
    "momentum_3d":     0.67,   # NEW — up 3 of last 5 days (continuation)
    "macd_accel":      0.67,   # histogram rising 3 bars — momentum building
    "obv_rising":      0.66,   # OBV rising 5 days — institutional accumulation
    "near_52w_high":   0.65,   # within 10% of 52W high — momentum continuation
    "golden_cross":    0.65,   # EMA50 > EMA200 — macro trend aligned
    "sector_leader":   0.65,   # outperforming sector ETF
    "strong_close":    0.65,   # closes in top 25% of range — buyers in control
    "operator_accumulation": 0.69, # smart-money accumulation: volume + strong close + OBV/VWAP
    "vwap_support":    0.64,   # price holding above VWAP = controlled buyer support
    "higher_lows":     0.63,   # uptrend structure
    "trend_daily":     0.63,   # price > EMA8 > EMA21
    "vcp_tightness":   0.63,   # ATR contracting — coiling before move
    # ── Tier 3: Weak / noisy (0.55–0.62) — low weight, rarely decisive ────────
    "rsi_confirmed":   0.60,   # reduced — lagging for swing
    "macd_cross":      0.58,   # reduced — too late for 1-2 week holds
    "volume":          0.68,   # raised — pure vol surge is predictive
    "adx":             0.57,   # reduced — direction agnostic
    "bull_candle":     0.59,   # reduced — single candle unreliable alone
    "atr_expansion":   0.60,   # reduced
    # ── Removed from scoring (noise): rsi_divergence, consolidation ──────────
    # rsi_divergence: ~52% win rate, too early, causes premature entries
    # consolidation: fires in downtrends too, not predictive enough
    # ── v12: Options-derived signals (US tickers only, gated by sidebar) ─────
    # These come from compute_options_signals() — if options data is not
    # available (non-US ticker, illiquid chain, fetch failure), the keys
    # simply aren't present in long_sig and contribute nothing to the
    # Bayesian update. Weights are intentionally conservative pending a
    # walk-forward backtest of each flag's hit rate.
    "opt_unusual_call_flow":  0.70,   # near-money call vol > 3× OI — fresh positioning
    "opt_call_skew_bullish":  0.65,   # 10% OTM call IV ≥ 10% OTM put IV — call demand
    "opt_pc_volume_low":      0.62,   # put/call volume < 0.6 — call-biased session
    "opt_iv_cheap":           0.62,   # ATM IV < 0.85× realized vol — calm-bull regime
    # ── v14: Pro Swing Setup composite ───────────────────────────────────────
    "pro_swing_setup":        0.75,
    # ── v15: High win-rate professional strategies ────────────────────────────
    # Weights calibrated to empirical win rates from professional trading literature.
    # Each signal is independently predictive — placed in isolated buckets.
    "nr7_setup":         0.70,   # NR7: narrowest range in 7 days — vol compression
    "inside_day":        0.68,   # Inside day in uptrend + declining vol
    "failed_breakdown":  0.73,   # Bear trap reversal — shorts squeezed above support
    "tight_flag":        0.70,   # Flag after strong pole — continuation setup
    "cup_handle":        0.68,   # O'Neil cup & handle — institutional base complete
    "pre_earnings_run":  0.68,   # 3-7 days before earnings + uptrend = drift signal
}
SHORT_WEIGHTS = {
    "stoch_overbought": 0.70, "bb_bear_squeeze": 0.68, "macd_decel":     0.66,
    "vol_breakdown":    0.65, "trend_bearish":   0.63, "lower_highs":    0.62,
    "macd_cross_bear":  0.60, "adx_bear":        0.57, "rsi_cross_bear": 0.59,
    "high_volume_down": 0.64,
    "operator_distribution": 0.67, # smart-money selling: high volume + weak close / failed breakout
    "below_vwap":       0.62, # price below VWAP confirms seller control
    # ── v12: Options-derived bearish signals (US tickers only) ────────────────
    "opt_unusual_put_flow":   0.68,   # near-money put vol > 3× OI — fresh hedging
    "opt_put_skew_bearish":   0.66,   # put IV >> call IV by ≥5 vol pts — fear bid
    "opt_term_inversion":     0.66,   # front-month IV > back-month IV — event/fear
    "opt_pc_volume_high":     0.64,   # put/call volume > 1.5 — defensive session
}
BASE_RATE = 0.50

# ─────────────────────────────────────────────────────────────────────────────
# v13.7: SIGNAL CORRELATION BUCKETS
# Bayesian probability assumes independent evidence. Many of our signals are
# heavily correlated — `trend_daily`, `weekly_trend`, `full_ma_stack`,
# `near_52w_high`, `golden_cross` all measure the same latent "uptrend"
# factor. When five correlated signals fire, the engine multiplies the odds
# ratio as if we had five independent witnesses, when really we have one
# witness shouting five times. This pegs probability at 95% on setups that
# historically win ~60%.
#
# Fix: group signals into categories. Within each bucket, sort by weight
# desc and shrink the k-th signal's contribution toward base rate by
# BUCKET_DECAY^k. So the strongest signal in a bucket counts in full, the
# next at half-strength, the third at quarter, etc. This preserves the
# Bayesian update math but stops correlated evidence from double-counting.
# ─────────────────────────────────────────────────────────────────────────────
SIGNAL_BUCKETS = {
    # ── Long buckets ──────────────────────────────────────────────────────────
    # Trend / structure of the prevailing direction
    "trend_daily":     "trend", "weekly_trend":   "trend",
    "full_ma_stack":   "trend", "golden_cross":   "trend",
    "near_52w_high":   "trend", "higher_lows":    "trend",
    # Momentum oscillators / acceleration
    "macd_accel":      "momentum", "macd_cross":      "momentum",
    "momentum_3d":     "momentum", "rsi_confirmed":   "momentum",
    "stoch_confirmed": "momentum", "atr_expansion":   "momentum",
    # Volume / accumulation footprints
    "volume":          "volume", "vol_surge_up":   "volume",
    "vol_breakout":    "volume", "pocket_pivot":   "volume",
    "obv_rising":      "volume", "operator_accumulation": "volume",
    # Volatility regime
    "bb_bull_squeeze": "volatility", "vcp_tightness": "volatility",
    # Intra-day / candle / VWAP structure
    "strong_close":    "structure", "vwap_support":  "structure",
    "bull_candle":     "structure",
    # Relative strength vs market / sector
    "rel_strength":    "relative", "rs_momentum":   "relative",
    "sector_leader":   "relative",
    # Forward-looking options layer
    "opt_unusual_call_flow": "options", "opt_call_skew_bullish": "options",
    "opt_pc_volume_low":     "options", "opt_iv_cheap":          "options",
    # Trend-strength regulator (single-signal bucket — never decayed)
    "adx":             "adx_long",
    # v14: Pro Swing Setup — own isolated bucket
    "pro_swing_setup": "catalyst",
    # v15: High win-rate strategies — each in own isolated bucket
    # (they are structurally independent of each other and existing signals)
    "nr7_setup":        "nr7",
    "inside_day":       "inside_day",
    "failed_breakdown": "failed_bd",
    "tight_flag":       "tight_flag",
    "cup_handle":       "cup_handle",
    "pre_earnings_run": "pre_earnings",

    # ── Short buckets (parallel categories) ───────────────────────────────────
    "trend_bearish":   "trend",    "lower_highs":    "trend",
    "macd_decel":      "momentum", "macd_cross_bear":"momentum",
    "rsi_cross_bear":  "momentum", "stoch_overbought":"momentum",
    "vol_breakdown":   "volume",   "high_volume_down":"volume",
    "operator_distribution": "volume",
    "bb_bear_squeeze": "volatility",
    "below_vwap":      "structure",
    "opt_unusual_put_flow":  "options", "opt_put_skew_bearish": "options",
    "opt_term_inversion":    "options", "opt_pc_volume_high":   "options",
    "adx_bear":        "adx_short",
}
BUCKET_DECAY = 0.5   # 1st in bucket: full · 2nd: half · 3rd: quarter · ...

# ─────────────────────────────────────────────────────────────────────────────
# FinanceDatabase
# ─────────────────────────────────────────────────────────────────────────────
try:
    import financedatabase as fd
    _fd_available = True
except ImportError:
    _fd_available = False

# ─────────────────────────────────────────────────────────────────────────────
# nsepython — optional dependency for NSE option chains (.NS tickers)
# Without this, India scans skip the options layer (same behaviour as SGX).
# Install: pip install nsepython
# ─────────────────────────────────────────────────────────────────────────────
try:
    from nsepython import nse_optionchain_scrapper as _nse_oc
    _nse_opt_available = True
except Exception:
    _nse_opt_available = False

# ─────────────────────────────────────────────────────────────────────────────
# Strategy Lab ML backends (optional)
# Install preferred backend: pip install lightgbm scikit-learn
# ─────────────────────────────────────────────────────────────────────────────
try:
    from lightgbm import LGBMClassifier
    _lgbm_available = True
except Exception:
    _lgbm_available = False

try:
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score, accuracy_score, precision_score, brier_score_loss
    _sklearn_strategy_available = True
except Exception:
    _sklearn_strategy_available = False

# ─────────────────────────────────────────────────────────────────────────────
# streamlit-autorefresh — optional dependency for non-destructive auto-rerun
# Without this, the auto-refresh feature falls back to a manual "Rerun now"
# button. The previous implementation used window.parent.location.reload(),
# which destroyed the entire Streamlit session — including all sidebar
# widget values (market selector, refresh interval, every checkbox/slider).
# `st_autorefresh` triggers a server-side rerun without reloading the
# browser page, preserving session state perfectly.
# Install: pip install streamlit-autorefresh
# ─────────────────────────────────────────────────────────────────────────────
try:
    from streamlit_autorefresh import st_autorefresh
    _autorefresh_available = True
except Exception:
    _autorefresh_available = False

# ─────────────────────────────────────────────────────────────────────────────
