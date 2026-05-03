"""
Swing Scanner v13.14 — Bayesian Ensemble
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
  pip install financedatabase ta streamlit yfinance pandas numpy nsepython requests
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import ta
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Swing Scanner v13.14",
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
    padding-top: 2.5rem !important;
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
    .block-container { padding: 0.3rem 0.4rem !important; }
    .stTabs [data-baseweb="tab"] { font-size: 9px !important; padding: 2px 5px !important; }
    .stButton button { width: 100% !important; }
    [data-testid="metric-container"] [data-testid="stMetricValue"] { font-size: 12px !important; }
}
</style>
""", unsafe_allow_html=True)

st.title("📈 Swing/Long Term Scanner v13.14 — Bayesian Ensemble")

# ─────────────────────────────────────────────────────────────────────────────
# TICKER UNIVERSE  — v4 curated high-quality list (always scanned)
# Sector stocks from live ETF holdings are ADDED on top of this baseline
# Neither list gates the other — every ticker is scanned for both long & short
# ─────────────────────────────────────────────────────────────────────────────
US_TICKERS = [
    # Semiconductors
    "NVDA","AMD","AVGO","ARM","MU","TSM","SMCI","ASML","KLAC","LRCX",
    "AMAT","TER","ON","MCHP","MPWR","MRVL","ADI","NXPI","LSCC",
    "WOLF","INTC","QCOM","ALAB","AMBA","CEVA",
    # Hardware / Cloud infra
    "DELL","HPE","PSTG","ANET","VRT","STX","WDC","NTAP",
    # Software / Cloud
    "PLTR","MDB","SNOW","DDOG","NET","CRWD","ZS","OKTA","PANW","WDAY",
    "TEAM","SHOP","TTD","U","PATH","CFLT","S","TENB","QLYS","GTLB","ESTC","SAIL","DT",
    # AI / Data
    "SOUN","BBAI","IREN","VSCO","GFAI","CXAI",
    # Crypto / Fintech
    "COIN","MSTR","MARA","RIOT","CLSK","WULF","HUT","BITF",
    "HOOD","PYPL","SOFI","AFRM","UPST","NU","MELI","BILL","TOST","FLYW","FUTU","TIGR",
    # China Tech
    "BABA","PDD","JD","SE","LI","XPEV","BIDU","TCOM","VIPS","HUYA",
    # Mega Cap
    "MA","V","AMZN","NFLX","META","GOOGL","MSFT","AAPL",
    # Consumer / Travel / Gaming
    "DASH","ABNB","BKNG","CVNA","APP","UBER","LYFT","RCL","CCL","NCLH",
    "RBLX","TTWO","EA","DKNG","PENN","MGAM","LVS","WYNN","MGM","W","OPEN",
    # EV / Auto
    "TSLA","RIVN","LCID","NIO","XPEV","F","GM","STLA","CHPT","BLNK","EVGO",
    # Defense / Space
    "PLTR","AXON","KTOS","RKLB","ASTS","LUNR","SPCE","LMT","NOC","RTX","BAC","GD",
    # Nuclear / Clean Energy
    "OKLO","SMR","NNE","CEG","ENPH","SEDG","FSLR","RUN","BE","PLUG","ARRY","FLNC","SHLS",
    # Energy / Materials
    "FCX","AA","NUE","LAC","ALB","MP","VALE","OXY","DVN","HAL","SLB",
    "GOLD","KGC","AG","PAAS","WPM","NEM",
    # Biotech
    "MRNA","BNTX","VRTX","REGN","GILD","AMGN","BIIB",
    "BEAM","CRSP","NTLA","EDIT","RXRX","PACB","ILMN","EXAS","TWST","SDGR","ALNY","BMRN",
    # Healthcare Tech / GLP-1
    "HIMS","LLY","NVO","VEEV","DOCS","DXCM","TDOC",
    # Quantum
    "IONQ","QUBT","RGTI","ARQQ","QBTS",
    # High-beta / Meme
    "NVTS","ACHR","JOBY","GME","AMC","BBWI","BIRD","CLOV","MVIS","CPSH","SKIN","XPOF","PRCT",
    # SE Asia (US-listed, high US-market correlation)
    "GRAB","SEA",
    "CEG","VST","GEV","BWXT","DNN","URG","NNE","SMR","URA","NLR","URNM","UUUU",
    "CCJ","UEC","PALAF","LEU","NNE","XE",
    #ETF
    "URA","NLR","URNM",
]

SG_TICKERS = [
    # Blue chips / STI 30
    "D05.SI",   # DBS Group
    "O39.SI",   # OCBC Bank
    "U11.SI",   # UOB
    "Z74.SI",   # Singtel
    "S68.SI",   # Singapore Exchange
    "BN4.SI",   # Keppel Corp
    "BS6.SI",   # Yangzijiang Shipbuilding — high beta
    "S58.SI",   # SATS
    "C6L.SI",   # Singapore Airlines
    "U96.SI",   # Sembcorp Industries
    "F34.SI",   # Wilmar International
    "V03.SI",   # Venture Corporation
    "C52.SI",   # ComfortDelGro
    "H78.SI",   # Hongkong Land
    "U14.SI",   # UOL Group
    "S51.SI",   # Seatrium — high beta offshore
    # REITs
    "C38U.SI",  # CapitaLand CICT
    "A17U.SI",  # CapitaLand Ascendas REIT
    "M44U.SI",  # Mapletree Logistics Trust
    "N2IU.SI",  # Mapletree Pan Asia Commercial
    # Growth / Higher beta
    "AIY.SI",   # iFAST — fintech
    "558.SI",   # UMS Holdings — semicon equipment
    "OYY.SI",   # PropNex
    "MZH.SI",   # Nanofilm Technologies
    "8AZ.SI",   # Aztech Global — volatile
    "40B.SI",   # HRnetGroup
    "1D0.SI",   # Nanofilm spin-off
]

INDIA_TICKERS = [
    # Nifty 50 Blue Chips
    "RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS",
    "SBIN.NS","AXISBANK.NS","WIPRO.NS","BAJFINANCE.NS","MARUTI.NS",
    "HCLTECH.NS","TECHM.NS","LTIM.NS","SUNPHARMA.NS","DRREDDY.NS",
    "CIPLA.NS","TATAMOTORS.NS","TATASTEEL.NS",
    # Adani Group (high beta)
    "ADANIENT.NS","ADANIPORTS.NS","ADANIGREEN.NS","ADANIPOWER.NS",
    # Metals
    "VEDL.NS","HINDALCO.NS","JSWSTEEL.NS","NMDC.NS","HINDZINC.NS","COALINDIA.NS",
    # New-age Tech / Fintech
    "ZOMATO.NS","PAYTM.NS","NYKAA.NS","DELHIVERY.NS","POLICYBZR.NS",
    # Defence / PSU
    "HAL.NS","BEL.NS","COCHINSHIP.NS","RVNL.NS","IRFC.NS","HUDCO.NS","NBCC.NS",
    # Renewable Energy
    "TATAPOWER.NS","SUZLON.NS","INOXWIND.NS",
    # Banking / Finance
    "INDUSINDBK.NS","KOTAKBANK.NS","PNB.NS","BANKBARODA.NS","HDFCAMC.NS",
    # Mid/Small-cap high beta
    "IRCTC.NS","BSESMD.NS","DIXON.NS","AMBER.NS","KAYNES.NS","GRAVITA.NS","PGEL.NS",
]

# Keep BASE_TICKERS as combined list for backward compatibility
BASE_TICKERS = US_TICKERS + SG_TICKERS + INDIA_TICKERS

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
# HELPERS  — exact v5 implementations
# ─────────────────────────────────────────────────────────────────────────────
def to_float(val):
    if isinstance(val, (pd.Series, np.ndarray)):
        return float(val.iloc[0] if hasattr(val, "iloc") else val[0])
    return float(val)


def find_swing_lows(low_series, lookback_bars=60, n_side=3):
    series = low_series.tail(lookback_bars).reset_index(drop=True)
    lows = []
    for i in range(n_side, len(series) - n_side):
        w = series.iloc[i - n_side: i + n_side + 1]
        if series.iloc[i] == w.min():
            lows.append((i, float(series.iloc[i])))
    return lows


def find_swing_highs(high_series, lookback_bars=60, n_side=3):
    series = high_series.tail(lookback_bars).reset_index(drop=True)
    highs = []
    for i in range(n_side, len(series) - n_side):
        w = series.iloc[i - n_side: i + n_side + 1]
        if series.iloc[i] == w.max():
            highs.append((i, float(series.iloc[i])))
    return highs


def bayesian_prob(weights_dict, active_signals, bonus=0.0, use_buckets=True):
    """
    Bayesian-style probability with bucket-capping for correlated signals.

    Many signals are statistically dependent ("trend_daily" + "weekly_trend"
    + "full_ma_stack" all measure the same uptrend). Naive Bayesian update
    multiplies their odds ratios as if independent, which over-counts evidence
    and pegs probability at 95% on setups that historically win much less.

    Bucket-cap groups active signals by SIGNAL_BUCKETS, sorts within each bucket
    by weight, and shrinks the k-th signal's distance from BASE_RATE by
    BUCKET_DECAY**k. The hand-set LONG_WEIGHTS / SHORT_WEIGHTS remain fixed.
    """
    # Allow runtime kill-switch from sidebar (debugging / A-B comparison)
    try:
        if not st.session_state.get("use_bucket_cap", True):
            use_buckets = False
    except Exception:
        pass

    # ── 2. Build effective (key, weight) list with optional bucket-cap ────
    eff = []
    if use_buckets and SIGNAL_BUCKETS:
        from collections import defaultdict
        by_bucket = defaultdict(list)
        for key, active in active_signals.items():
            if active and key in weights_dict:
                bucket = SIGNAL_BUCKETS.get(key, f"_solo_{key}")
                by_bucket[bucket].append((key, float(weights_dict[key])))
        for bucket, items in by_bucket.items():
            items.sort(key=lambda kv: -kv[1])
            for k, (key, w) in enumerate(items):
                w_eff = BASE_RATE + (w - BASE_RATE) * (BUCKET_DECAY ** k)
                eff.append((key, w_eff))
    else:
        for key, active in active_signals.items():
            if active and key in weights_dict:
                eff.append((key, float(weights_dict[key])))

    # ── 3. Bayesian update (unchanged math) ────────────────────────────────
    p = BASE_RATE
    for _key, w in eff:
        # Clip to avoid divide-by-zero on degenerate weights
        w = max(0.001, min(0.999, w))
        num = p * (w / BASE_RATE)
        den = num + (1 - p) * ((1 - w) / (1 - BASE_RATE))
        if den <= 0:
            continue
        p = num / den
    p = min(p + bonus, 0.97)
    p = 0.40 + (p - BASE_RATE) / (0.97 - BASE_RATE) * 0.55
    return round(max(0.35, min(0.95, p)), 4)


def prob_label(p):
    if p >= 0.82: return "VERY HIGH"
    if p >= 0.72: return "HIGH"
    if p >= 0.62: return "MODERATE-HIGH"
    if p >= 0.52: return "MODERATE"
    return "LOW"


def style_prob(val):
    try:
        v = float(str(val).rstrip("%"))
        if v >= 82: return "background-color:#D5F5E3;color:#1E8449;font-weight:700"
        if v >= 72: return "background-color:#D6EAF8;color:#1A5276;font-weight:600"
        if v >= 62: return "background-color:#FDEBD0;color:#784212;font-weight:500"
        return "background-color:#FDEDEC;color:#78281F"
    except: return ""


def style_short_prob(val):
    try:
        v = float(str(val).rstrip("%"))
        if v >= 82: return "background-color:#FADBD8;color:#78281F;font-weight:700"
        if v >= 72: return "background-color:#FDEBD0;color:#784212;font-weight:600"
        if v >= 62: return "background-color:#FEF9E7;color:#7D6608;font-weight:500"
        return "background-color:#EBF5FB;color:#1A5276"
    except: return ""

# ─────────────────────────────────────────────────────────────
# GRID SEARCH FILTER (NEW)
# Adds search to ALL tables automatically
# ─────────────────────────────────────────────────────────────
def grid_search_filter(df, label):
    if df.empty:
        return df
    search = st.text_input(f"🔎 Search {label}", key=f"search_{label}",
                           placeholder="ticker…").strip().upper()
    if search and "Ticker" in df.columns:
        df = df[df["Ticker"].str.contains(search, case=False, na=False)]
    return df

def show_table(df, label, prob_col="Rise Prob"):
    if df.empty:
        st.info(f"No {label} setups.")
        return

    df = grid_search_filter(df, label)

    # ── Sort by Entry Quality ─────────────────────────────────────────────────
    _quality_order = {"✅ BUY": 0, "👀 WATCH": 1, "⏳ WAIT": 2, "🚫 AVOID": 3}
    if "Entry Quality" in df.columns:
        df = df.copy()
        df["_eq_sort"] = df["Entry Quality"].map(_quality_order).fillna(9)
        df = df.sort_values(["_eq_sort", prob_col],
                            ascending=[True, False],
                            key=lambda s: s if s.name != prob_col
                                          else s.str.rstrip("%").astype(float))
        df = df.drop(columns="_eq_sort")

    # ── Column selection ──────────────────────────────────────────────────────
    if prob_col == "Rise Prob":
        display_cols = [c for c in [
            "Ticker", "Entry Quality", "Today %", "Rise Prob", 
            "Operator", "VWAP", "Trap Risk",
            "Price", "MA60 Stop", "TP1 +10%", "TP2 +15%", "TP3 +20%",
            "Sector", "Action",
            "Score","Op Score",
        ] if c in df.columns]
    else:
        display_cols = [c for c in [
            "Ticker", "Entry Quality", "Today %", "Fall Prob", 
            "Operator", "VWAP", "Trap Risk",
            "Price", "Cover Stop", "Target 1:1", "Target 1:2",
            "Sector", "Action",
            "Score","Op Score",
        ] if c in df.columns]

    df_disp = df[display_cols] if display_cols else df

    # ── Narrow column_config — makes grid appear smaller ─────────────────────
    col_cfg = {
        "Ticker":        st.column_config.TextColumn("Ticker",        width=60),
        "Entry Quality": st.column_config.TextColumn("Entry",         width=70),
        "Today %":       st.column_config.TextColumn("Today%",        width=58),
        "Rise Prob":     st.column_config.TextColumn("Rise%",         width=55),
        "Fall Prob":     st.column_config.TextColumn("Fall%",         width=55),
        "Operator":      st.column_config.TextColumn("Operator",      width=120),
        "VWAP":          st.column_config.TextColumn("VWAP",          width=60),
        "Trap Risk":     st.column_config.TextColumn("Trap",          width=80),
        "Price":         st.column_config.TextColumn("Price",         width=60),
        "MA60 Stop":     st.column_config.TextColumn("MA60Stop",      width=65),
        "Cover Stop":    st.column_config.TextColumn("CoverStop",     width=65),
        "TP1 +10%":      st.column_config.TextColumn("TP1+10%",       width=62),
        "TP2 +15%":      st.column_config.TextColumn("TP2+15%",       width=62),
        "TP3 +20%":      st.column_config.TextColumn("TP3+20%",       width=62),
        "Target 1:1":    st.column_config.TextColumn("T1",            width=62),
        "Target 1:2":    st.column_config.TextColumn("T2",            width=62),
        "Sector":        st.column_config.TextColumn("Sector",        width=90),
        "Action":        st.column_config.TextColumn("Action",        width=80),
        "Op Score":      st.column_config.TextColumn("Op",            width=45),
        "Score":         st.column_config.TextColumn("Score",         width=50),
    }
    # keep only configs for columns that exist
    cfg = {k: v for k, v in col_cfg.items() if k in df_disp.columns}

    n_rows = len(df_disp)
    row_h  = 35   # px per row
    height = min(35 + n_rows * row_h, 400)   # cap at 400px

    styler   = df_disp.style
    style_fn = styler.map if hasattr(styler, "map") else styler.applymap
    fn = style_short_prob if prob_col == "Fall Prob" else style_prob

    if prob_col in df_disp.columns:
        st.dataframe(
            style_fn(fn, subset=[prob_col]),
            width="stretch",
            hide_index=True,
            column_config=cfg,
            height=height,
        )
    else:
        st.dataframe(
            df_disp,
            width="stretch",
            hide_index=True,
            column_config=cfg,
            height=height,
        )


def _extract_closes(raw, ticker, n_tickers):
    """Robustly extract Close series from yfinance MultiIndex or flat DataFrame."""
    if n_tickers == 1:
        return raw["Close"].squeeze().ffill().dropna()
    if isinstance(raw.columns, pd.MultiIndex):
        lvl1 = raw.columns.get_level_values(1)
        lvl0 = raw.columns.get_level_values(0)
        if ticker in lvl1:
            return raw.xs(ticker, axis=1, level=1)["Close"].ffill().dropna()
        if ticker in lvl0:
            return raw[ticker]["Close"].ffill().dropna()
    if ticker in raw.columns:
        return raw[ticker]["Close"].squeeze().ffill().dropna()
    return pd.Series(dtype=float)


# ─────────────────────────────────────────────────────────────────────────────
# MARKET REGIME  — v5 exact logic
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=1800)
def get_market_regime():
    try:
        spy_raw = yf.download("SPY", period="3mo", interval="1d",
                              progress=False, auto_adjust=True)
        vix_raw = yf.download("^VIX", period="5d", interval="1d",
                              progress=False, auto_adjust=True)

        # Flatten MultiIndex if present (yfinance ≥0.2.x returns MultiIndex)
        for df in (spy_raw, vix_raw):
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

        if spy_raw.empty or "Close" not in spy_raw.columns:
            raise ValueError("SPY data empty or missing Close column")
        if vix_raw.empty or "Close" not in vix_raw.columns:
            raise ValueError("VIX data empty or missing Close column")

        spy_close = spy_raw["Close"].ffill().dropna()
        vix_close = vix_raw["Close"].ffill().dropna()

        if len(spy_close) < 50:
            raise ValueError(f"Insufficient SPY history: {len(spy_close)} bars")

        spy_ema20 = float(ta.trend.ema_indicator(spy_close, window=20).iloc[-1])
        spy_ema50 = float(ta.trend.ema_indicator(spy_close, window=50).iloc[-1])
        spy_now   = float(spy_close.iloc[-1])
        vix_now   = float(vix_close.iloc[-1])

        if spy_now > spy_ema20 and vix_now < 20:
            regime = "BULL"
        elif spy_now < spy_ema50 or vix_now > 25:
            regime = "BEAR"
        else:
            regime = "CAUTION"

        return {"regime": regime, "spy": round(spy_now, 2),
                "spy_ema20": round(spy_ema20, 2),
                "spy_ema50": round(spy_ema50, 2),
                "vix": round(vix_now, 2)}

    except Exception as e:
        # Surface the real error so user can diagnose
        st.warning(f"⚠️ Market regime fetch failed: {e}. Showing UNKNOWN. Try `pip install --upgrade yfinance`.")
        return {"regime": "UNKNOWN", "spy": 0,
                "spy_ema20": 0, "spy_ema50": 0, "vix": 0}


# ─────────────────────────────────────────────────────────────────────────────
# SECTOR PERFORMANCE  — v7 robust MultiIndex handling
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=900)
def get_sector_performance() -> pd.DataFrame:
    etf_list     = list(SECTOR_ETFS.values())
    sector_names = list(SECTOR_ETFS.keys())
    results      = []
    try:
        raw = yf.download(
            etf_list, period="5d", interval="1d",
            progress=False, auto_adjust=True, group_by="ticker"
        )
        if raw.empty:
            raise ValueError("Empty response from yfinance")

        for name, etf in zip(sector_names, etf_list):
            try:
                closes = _extract_closes(raw, etf, len(etf_list))
                if len(closes) < 2:
                    continue
                pct  = float((closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2] * 100)
                pct5 = float((closes.iloc[-1] - closes.iloc[0])  / closes.iloc[0]  * 100)
                results.append({
                    "Sector":  name, "ETF": etf,
                    "Today %": round(pct,  2),
                    "5d %":    round(pct5, 2),
                    "Price":   round(float(closes.iloc[-1]), 2),
                    "Status":  "🟢 GREEN" if pct > 0.1 else ("🔴 RED" if pct < -0.1 else "⚪ FLAT"),
                })
            except Exception:
                continue
    except Exception as e:
        st.warning(f"Sector fetch failed: {e}. Try: pip install --upgrade yfinance")

    if not results:
        return pd.DataFrame(columns=["Sector","ETF","Today %","5d %","Price","Status"])
    return pd.DataFrame(results).sort_values("Today %", ascending=False).reset_index(drop=True)


@st.cache_data(ttl=900)
def get_india_sector_performance() -> pd.DataFrame:
    """Fetch India NSE sector indices performance."""
    etf_list     = list(INDIA_SECTOR_ETFS.values())
    sector_names = list(INDIA_SECTOR_ETFS.keys())
    results      = []
    try:
        raw = yf.download(etf_list, period="5d", interval="1d",
                          progress=False, auto_adjust=True, group_by="ticker")
        if raw.empty:
            raise ValueError("Empty")
        for name, etf in zip(sector_names, etf_list):
            try:
                closes = _extract_closes(raw, etf, len(etf_list))
                if len(closes) < 2:
                    continue
                pct  = float((closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2] * 100)
                pct5 = float((closes.iloc[-1] - closes.iloc[0])  / closes.iloc[0]  * 100)
                results.append({
                    "Sector":  name, "ETF": etf,
                    "Today %": round(pct,  2),
                    "5d %":    round(pct5, 2),
                    "Price":   round(float(closes.iloc[-1]), 2),
                    "Status":  "🟢 GREEN" if pct > 0.1 else ("🔴 RED" if pct < -0.1 else "⚪ FLAT"),
                })
            except Exception:
                continue
    except Exception as e:
        st.warning(f"India sector fetch failed: {e}")
    if not results:
        return pd.DataFrame(columns=["Sector","ETF","Today %","5d %","Price","Status"])
    return pd.DataFrame(results).sort_values("Today %", ascending=False).reset_index(drop=True)


@st.cache_data(ttl=900)
def get_sg_sector_performance() -> pd.DataFrame:
    """Compute SGX sector heatmap by averaging stock returns within each sector group."""
    all_tickers = list({t for tickers in SG_SECTOR_GROUPS.values() for t in tickers})
    results     = []
    try:
        raw = yf.download(all_tickers, period="5d", interval="1d",
                          progress=False, auto_adjust=True, group_by="ticker")
        for sector_name, members in SG_SECTOR_GROUPS.items():
            pcts, pcts5, prices = [], [], []
            for t in members:
                try:
                    closes = _extract_closes(raw, t, len(all_tickers))
                    if len(closes) < 2:
                        continue
                    pcts.append(float((closes.iloc[-1]-closes.iloc[-2])/closes.iloc[-2]*100))
                    pcts5.append(float((closes.iloc[-1]-closes.iloc[0])/closes.iloc[0]*100))
                    prices.append(float(closes.iloc[-1]))
                except Exception:
                    continue
            if pcts:
                pct  = round(float(np.mean(pcts)),  2)
                pct5 = round(float(np.mean(pcts5)), 2)
                results.append({
                    "Sector":  sector_name,
                    "ETF":     "/".join(members[:2]),
                    "Today %": pct, "5d %": pct5,
                    "Price":   round(float(np.mean(prices)), 2),
                    "Status":  "🟢 GREEN" if pct > 0.1 else ("🔴 RED" if pct < -0.1 else "⚪ FLAT"),
                })
    except Exception as e:
        st.warning(f"SGX sector fetch failed: {e}")
    if not results:
        return pd.DataFrame(columns=["Sector","ETF","Today %","5d %","Price","Status"])
    return pd.DataFrame(results).sort_values("Today %", ascending=False).reset_index(drop=True)
@st.cache_data(ttl=3600)
def get_earnings_flag(ticker):
    try:
        info = yf.Ticker(ticker).calendar
        if info is None or info.empty:
            return False, "–"
        ed = info.loc["Earnings Date"].iloc[0] \
             if "Earnings Date" in info.index else info.iloc[0, 0]
        if pd.isnull(ed):
            return False, "–"
        days_out = (pd.Timestamp(ed).date() - datetime.today().date()).days
        return 0 <= days_out <= 7, str(pd.Timestamp(ed).date())
    except Exception:
        return False, "–"


# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL COMPUTATION  — exact v5 compute_all_signals
# accepts close/high/low/vol Series (not DataFrame)
# ─────────────────────────────────────────────────────────────────────────────
def compute_all_signals(close, high, low, vol, spy_close=None, sector_close=None):
    """
    Computes all long and short signals.
    spy_close:    optional SPY Close series for relative strength calculation
    sector_close: optional sector ETF Close series for sector leader calculation
    """
    ema8   = ta.trend.ema_indicator(close, window=8)
    ema21  = ta.trend.ema_indicator(close, window=21)
    ema50  = ta.trend.ema_indicator(close, window=50)
    ema200 = ta.trend.ema_indicator(close, window=200)
    rsi    = ta.momentum.rsi(close, window=14)
    srsi_k = ta.momentum.stochrsi_k(close, window=14, smooth1=3, smooth2=3)
    srsi_d = ta.momentum.stochrsi_d(close, window=14, smooth1=3, smooth2=3)
    macd_o = ta.trend.MACD(close)
    bb     = ta.volatility.BollingerBands(close, window=20, window_dev=2)
    adx    = ta.trend.adx(high, low, close, window=14)
    atr    = ta.volatility.average_true_range(high, low, close, window=14)
    obv    = ta.volume.on_balance_volume(close, vol)
    vol_avg  = vol.rolling(20).mean()
    high_10d = high.rolling(10).max()
    low_10d  = low.rolling(10).min()
    bb_width = (bb.bollinger_hband() - bb.bollinger_lband()) / bb.bollinger_mavg()

    # ── Scalars ───────────────────────────────────────────────────────────────
    p    = to_float(close.iloc[-1])
    e8   = to_float(ema8.iloc[-1])
    e21  = to_float(ema21.iloc[-1])
    e50  = to_float(ema50.iloc[-1])
    e200 = to_float(ema200.iloc[-1]) if len(close) >= 200 else 0
    rsi0 = to_float(rsi.iloc[-1]);   rsi1 = to_float(rsi.iloc[-2]); rsi2 = to_float(rsi.iloc[-3])
    k0   = to_float(srsi_k.iloc[-1]); k1  = to_float(srsi_k.iloc[-2]); k2 = to_float(srsi_k.iloc[-3])
    d0   = to_float(srsi_d.iloc[-1])
    ml   = to_float(macd_o.macd().iloc[-1]);      ms  = to_float(macd_o.macd_signal().iloc[-1])
    mh0  = to_float(macd_o.macd_diff().iloc[-1]); mh1 = to_float(macd_o.macd_diff().iloc[-2])
    mh2  = to_float(macd_o.macd_diff().iloc[-3])
    adxv = to_float(adx.iloc[-1]); atrv = to_float(atr.iloc[-1])
    vr   = to_float(vol.iloc[-1]) / to_float(vol_avg.iloc[-1]) \
           if to_float(vol_avg.iloc[-1]) > 0 else 0
    bbwn = to_float(bb_width.iloc[-1]); bbm = to_float(bb.bollinger_mavg().iloc[-1])
    bbws = bb_width.dropna().tail(126)
    bbp20 = float(np.percentile(bbws, 20)) if len(bbws) >= 20 else 0
    bbp10 = float(np.percentile(bbws, 10)) if len(bbws) >= 10 else 0
    bb_squeeze    = bbwn <= bbp20
    bb_very_tight = bbwn <= bbp10
    h10  = to_float(high_10d.iloc[-1]); l10 = to_float(low_10d.iloc[-1])
    candle_red = float(close.iloc[-1]) < float(close.iloc[-2])

    # ── 52-week high ──────────────────────────────────────────────────────────
    high_252 = float(high.rolling(252).max().iloc[-1]) if len(high) >= 50 else float(high.max())

    # ── Weekly trend ──────────────────────────────────────────────────────────
    weekly_ema20 = to_float(ta.trend.ema_indicator(close, window=20).iloc[-1])
    weekly_ema50 = to_float(ta.trend.ema_indicator(close, window=50).iloc[-1])
    # Standard: price > MA20 > MA60 (healthy uptrend)
    weekly_trend_ok = (p > weekly_ema20) and (weekly_ema20 > weekly_ema50)
    # Relaxed: price just broke above MA20 on high volume (early breakout — MA60 can lag)
    weekly_trend_breakout = (p > weekly_ema20) and (vr >= 1.8)

    # ── Golden cross ──────────────────────────────────────────────────────────
    gc_now     = (e50 > e200) if e200 > 0 else False
    # Fresh golden cross = EMA50 crossed EMA200 within last 10 bars
    gc_fresh   = False
    if e200 > 0 and len(close) >= 210:
        e50_10 = to_float(ema50.iloc[-10])
        e200_10 = to_float(ema200.iloc[-10])
        gc_fresh = gc_now and (e50_10 <= e200_10)  # was below, now above

    # ── OBV trend (rising for 5 consecutive days) ─────────────────────────────
    obv_vals = obv.dropna().tail(6)
    obv_rising = len(obv_vals) >= 5 and all(
        obv_vals.iloc[i] < obv_vals.iloc[i+1] for i in range(len(obv_vals)-1)
    )

    # ── Bullish candlestick patterns ──────────────────────────────────────────
    o_last  = float(close.iloc[-2])   # use prev close as proxy for open
    c_last  = float(close.iloc[-1])
    h_last  = float(high.iloc[-1])
    l_last  = float(low.iloc[-1])
    body    = abs(c_last - o_last)
    candle_range = h_last - l_last
    lower_wick   = min(c_last, o_last) - l_last
    upper_wick   = h_last - max(c_last, o_last)
    # Hammer: small body, long lower wick, at or near support
    hammer = (lower_wick >= 2 * body) and (c_last >= o_last) and (body > 0)
    # Bullish engulfing: today's body fully engulfs yesterday's
    o_prev = float(close.iloc[-3])
    c_prev = float(close.iloc[-2])
    bull_engulf = (c_last > o_last) and (c_prev < o_prev) and \
                  (c_last > o_prev) and (o_last < c_prev)
    bull_candle = hammer or bull_engulf

    # ── ATR expansion (today's range > 1.2× ATR = breakout energy) ───────────
    today_range  = float(high.iloc[-1]) - float(low.iloc[-1])
    atr_expansion = today_range > 1.2 * atrv

    # ── Consolidation (3–8 tight days before today) ───────────────────────────
    if len(close) >= 10:
        recent_ranges = [float(high.iloc[i]) - float(low.iloc[i])
                         for i in range(-9, -1)]
        avg_recent_range = np.mean(recent_ranges) if recent_ranges else atrv
        tight_days = sum(1 for r in recent_ranges if r < 0.7 * atrv)
        consolidation = 3 <= tight_days <= 8
    else:
        consolidation = False

    # ── RSI bullish divergence (price lower low but RSI higher low) ───────────
    rsi_div = False
    if len(close) >= 20:
        # Compare last 2 swing lows in price vs RSI
        price_lows = find_swing_lows(close, 30, 2)
        rsi_series = rsi.dropna()
        if len(price_lows) >= 2 and len(rsi_series) >= 20:
            # Price made lower low
            p_lower = price_lows[-1][1] < price_lows[-2][1]
            # RSI at those same approximate positions
            try:
                idx1 = -int(len(close) - price_lows[-1][0])
                idx2 = -int(len(close) - price_lows[-2][0])
                r1 = float(rsi_series.iloc[idx1]) if abs(idx1) < len(rsi_series) else rsi0
                r2 = float(rsi_series.iloc[idx2]) if abs(idx2) < len(rsi_series) else rsi1
                rsi_div = p_lower and (r1 > r2)   # price down, RSI up = divergence
            except Exception:
                pass

    # ── Relative strength vs SPY ──────────────────────────────────────────────
    rel_strength = False
    if spy_close is not None and len(spy_close) >= 6 and len(close) >= 6:
        stock_5d = (float(close.iloc[-1]) - float(close.iloc[-6])) / float(close.iloc[-6])
        spy_5d   = (float(spy_close.iloc[-1]) - float(spy_close.iloc[-6])) / float(spy_close.iloc[-6])
        rel_strength = stock_5d > spy_5d

    # ── Sector leader ─────────────────────────────────────────────────────────
    sector_leader = False
    if sector_close is not None and len(sector_close) >= 6 and len(close) >= 6:
        stock_5d   = (float(close.iloc[-1]) - float(close.iloc[-6])) / float(close.iloc[-6])
        sector_5d  = (float(sector_close.iloc[-1]) - float(sector_close.iloc[-6])) / float(sector_close.iloc[-6])
        sector_leader = stock_5d > sector_5d

    # ── Swing structure ───────────────────────────────────────────────────────
    swing_lows  = find_swing_lows(low,  60, 3)
    swing_highs = find_swing_highs(high, 60, 3)
    higher_lows  = len(swing_lows)  >= 2 and swing_lows[-1][1]  > swing_lows[-2][1]
    lower_highs  = len(swing_highs) >= 2 and swing_highs[-1][1] < swing_highs[-2][1]
    last_swing_low  = swing_lows[-1][1]  if swing_lows  else p * 0.95
    last_swing_high = swing_highs[-1][1] if swing_highs else p * 1.05

    # ── [NEW] VCP TIGHTNESS (Volatility Contraction) ──────────────────────────
    # High-probability setups often happen when volatility "shrinks" before a move
    atr5 = ta.volatility.average_true_range(high, low, close, window=5).iloc[-1]
    atr20 = ta.volatility.average_true_range(high, low, close, window=20).iloc[-1]
    vcp_tightness = (atr5 / atr20) < 0.85 if atr20 > 0 else False

    # ── [NEW] STRONG CLOSE (Institutional Support) ────────────────────────────
    # A strong finish implies buyers held control into the close
    day_range = float(high.iloc[-1]) - float(low.iloc[-1])
    closing_pos = (float(close.iloc[-1]) - float(low.iloc[-1])) / day_range if day_range > 0 else 0
    strong_close = closing_pos >= 0.75

    # ── [NEW] RS MOMENTUM (Relative Strength Line) ────────────────────────────
    # Does the stock continue to gain ground vs SPY?
    rs_momentum = False
    if spy_close is not None and len(close) >= 20:
        rs_line = close / spy_close.reindex(close.index).ffill()
        rs_ema = rs_line.rolling(20).mean()
        rs_momentum = rs_line.iloc[-1] > rs_ema.iloc[-1]

    # ── STRATEGY SIGNALS (MA20/MA60 dip rules) ───────────────────────────────
    # MA20 and MA60 (proxy: EMA20=daily 20, EMA60=daily 60)
    ma20 = ta.trend.sma_indicator(close, window=20)
    ma60 = ta.trend.sma_indicator(close, window=60)
    ma20_val = to_float(ma20.iloc[-1])
    ma60_val = to_float(ma60.iloc[-1])

    # Volume trend — is volume decreasing over last 3 bars? (dip with declining vol = healthy pullback)
    vol_3d_avg = float(vol.iloc[-4:-1].mean()) if len(vol) >= 4 else float(vol_avg.iloc[-1])
    vol_declining = float(vol.iloc[-1]) < vol_3d_avg

    # Dip to MA20: price within 1% below/above MA20 AND declining volume
    dip_to_ma20 = (p >= ma20_val * 0.99) and (p <= ma20_val * 1.015) and vol_declining

    # Dip to MA60: price within 1.5% below/above MA60 AND declining volume
    dip_to_ma60 = (p >= ma60_val * 0.985) and (p <= ma60_val * 1.015) and vol_declining

    # No-chase filter: price NOT running away from MA20 (not >5% above MA20 = avoid chasing highs)
    #not_chasing = p <= ma20_val * 1.05
    not_chasing  = p <= ma20_val * 1.10

    # Limit-up filter: today's move not >8% (avoid limit-up/gap-up chasing)
    today_chg_pct = float((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100) if len(close) >= 2 else 0
    #not_limit_up = today_chg_pct < 8.0
    not_limit_up = today_chg_pct < 12.0


    # Stop-loss trigger: price broke below MA60 with significant volume (>1.5× avg)
    ma60_stop_triggered = (p < ma60_val * 0.995) and (vr >= 1.5)

    # Support hold: price holding ABOVE MA60 (not stopped out)
    above_ma60 = p >= ma60_val

    # ── Full MA stack: price > EMA8 > EMA21 > MA20 (3-stack — doesn't require MA60 alignment)
    # Relaxed: MA60 alignment excluded — misses early breakouts and recovering stocks like UUUU
    full_ma_stack = (p > e8) and (e8 > e21) and (e21 > ma20_val)

    # ── Momentum continuation: up 3 of last 5 days ───────────────────────────
    if len(close) >= 6:
        daily_returns = [float(close.iloc[i]) - float(close.iloc[i-1])
                         for i in range(-5, 0)]
        momentum_3d = sum(1 for r in daily_returns if r > 0) >= 3
    else:
        momentum_3d = False

    # ── [NEW] VWAP + OPERATOR / SMART-MONEY ACTIVITY LAYER ───────────────────
    # These are confirmation filters, not standalone reasons to buy. They look
    # for footprints of accumulation/distribution: volume expansion, close
    # location, OBV, VWAP control, and failed breakouts.
    try:
        typical_price = (high + low + close) / 3
        cum_vol = vol.replace(0, np.nan).cumsum()
        vwap_series = ((typical_price * vol).cumsum() / cum_vol).replace([np.inf, -np.inf], np.nan).ffill()
        vwap_now = float(vwap_series.iloc[-1]) if len(vwap_series.dropna()) else p
    except Exception:
        vwap_now = p

    above_vwap = p >= vwap_now
    below_vwap = p < vwap_now
    vwap_support = p >= vwap_now * 0.995

    false_breakout = (p >= h10 * 0.995) and (vr >= 1.8) and (not strong_close)
    gap_chase_risk = (today_chg_pct > 7.0) and (vr > 2.5)
    operator_distribution = (vr >= 1.8) and (today_chg_pct <= 0.5) and (not strong_close)

    operator_score = 0
    if (not candle_red) and (vr >= 2.0):
        operator_score += 2
    if (vr >= 1.5) and strong_close:
        operator_score += 2
    if obv_rising:
        operator_score += 1
    if (p >= h10 * 0.995) and (vr >= 1.8):
        operator_score += 2
    if above_vwap:
        operator_score += 1
    if (p > ma20_val) and above_ma60:
        operator_score += 1
    if 0 < today_chg_pct < 8:
        operator_score += 1
    # Accumulation/absorption: red/high-volume day but price closes off lows.
    if candle_red and (vr >= 1.8) and (closing_pos >= 0.45) and (p >= ma20_val * 0.98):
        operator_score += 2

    if false_breakout or gap_chase_risk or operator_distribution:
        operator_score = max(0, operator_score - 2)

    if operator_score >= 6:
        operator_label = "🔥 STRONG OPERATOR"
    elif operator_score >= 4:
        operator_label = "🟢 ACCUMULATION"
    elif operator_score >= 2:
        operator_label = "🟡 WEAK SIGNS"
    else:
        operator_label = "⚪ NONE"

    trap_risk_label = "FALSE BO" if false_breakout else "GAP CHASE" if gap_chase_risk else "DISTRIB" if operator_distribution else "–"

    # ── LONG signals (scored) ─────────────────────────────────────────────────
    long_signals = {
        "trend_daily":     (p > e8) and (e8 > e21),
        "stoch_confirmed": (k2 < 20) and (k1 < 20) and (k0 > k1) and (k0 > d0) and (k0 < 80),
        "bb_bull_squeeze": bb_squeeze and (p > bbm),
        "macd_accel":      (mh0 > mh1 > mh2) and (mh0 > 0),
        "macd_cross":      (ml > ms) and (mh0 > 0),
        "rsi_confirmed":   (rsi2 < 50) and (rsi1 >= 50) and (rsi0 > rsi1) and (rsi0 < 72),
        "adx":             adxv > 20,
        "volume":          vr > 1.5,
        "vol_breakout":    (p >= h10 * 0.995) and (vr >= 1.8),
        "higher_lows":     higher_lows,
        "weekly_trend":    weekly_trend_ok or weekly_trend_breakout,
        "golden_cross":    gc_now,
        "rel_strength":    rel_strength,
        "near_52w_high":   (p >= high_252 * 0.90),
        "obv_rising":      obv_rising,
        "bull_candle":     bull_candle,
        "atr_expansion":   atr_expansion,
        "sector_leader":   sector_leader,
        "vcp_tightness":   vcp_tightness,
        "strong_close":    strong_close,
        "operator_accumulation": operator_score >= 4,
        "vwap_support":    vwap_support,
        "rs_momentum":     rs_momentum,
        "full_ma_stack":   full_ma_stack,
        "momentum_3d":     momentum_3d,
        "vol_surge_up":    (not candle_red) and (vr >= 2.0) and (today_chg_pct >= 1.5),
        "pocket_pivot":    (not candle_red) and (vr >= 1.5) and (p > ma20_val),
    }
    # Strategy entry signals — entry quality label only, NOT scored
    _strat = {
        "dip_to_ma20": dip_to_ma20,
        "dip_to_ma60": dip_to_ma60,
        "not_chasing": not_chasing and not_limit_up,
        "above_ma60":  above_ma60,
    }

    # ── SHORT signals ─────────────────────────────────────────────────────────
    short_signals = {
        "trend_bearish":    (p < e8) and (e8 < e21),
        "stoch_overbought": (k2 > 80) and (k1 > 80) and (k0 < k1) and (k0 < d0) and (k0 > 20),
        "bb_bear_squeeze":  bb_squeeze and (p < bbm),
        "macd_decel":       (mh0 < mh1 < mh2) and (mh0 < 0),
        "macd_cross_bear":  (ml < ms) and (mh0 < 0),
        "rsi_cross_bear":   (rsi2 > 50) and (rsi1 <= 50) and (rsi0 < rsi1) and (rsi0 > 28),
        "adx_bear":         adxv > 20 and (p < e21),
        "high_volume_down": candle_red and (vr >= 2.0),
        "operator_distribution": operator_distribution,
        "below_vwap":       below_vwap,
        "vol_breakdown":    (p <= l10 * 1.005) and (vr >= 1.8),
        "lower_highs":      lower_highs,
        # Strategy: MA60 stop-loss broken
        "ma60_stop":        ma60_stop_triggered,
    }

    raw = {
        "p": p, "e8": e8, "e21": e21, "e50": e50, "e200": e200,
        "rsi0": rsi0, "rsi1": rsi1, "rsi2": rsi2,
        "k0": k0, "k1": k1, "k2": k2, "d0": d0,
        "ml": ml, "ms": ms, "mh0": mh0, "mh1": mh1, "mh2": mh2,
        "adx": adxv, "atr": atrv, "vr": vr,
        "bbwn": bbwn, "bbp20": bbp20, "bbp10": bbp10, "bbm": bbm,
        "bb_squeeze": bb_squeeze, "bb_very_tight": bb_very_tight,
        "h10": h10, "l10": l10, "high_252": high_252,
        "last_swing_low":    last_swing_low,
        "last_swing_high":   last_swing_high,
        "swing_lows_count":  len(swing_lows),
        "swing_highs_count": len(swing_highs),
        "candle_red":        candle_red,
        "gc_fresh":          gc_fresh,
        "obv_rising":        obv_rising,
        "bull_candle":       bull_candle,
        "weekly_trend":      weekly_trend_ok,
        "full_ma_stack":     full_ma_stack,
        "momentum_3d":       momentum_3d,
        # Strategy fields (entry quality only — not scored)
        "ma20":              ma20_val,
        "ma60":              ma60_val,
        "dip_to_ma20":       _strat["dip_to_ma20"],
        "dip_to_ma60":       _strat["dip_to_ma60"],
        "not_chasing":       not_chasing,
        "not_limit_up":      not_limit_up,
        "vol_declining":     vol_declining,
        "above_ma60":        _strat["above_ma60"],
        "ma60_stop_triggered": ma60_stop_triggered,
        "today_chg_pct":     today_chg_pct,
        "vwap":              vwap_now,
        "above_vwap":        above_vwap,
        "below_vwap":        below_vwap,
        "vwap_support":      vwap_support,
        "operator_score":    operator_score,
        "operator_label":    operator_label,
        "false_breakout":    false_breakout,
        "gap_chase_risk":    gap_chase_risk,
        "operator_distribution": operator_distribution,
        "trap_risk_label":   trap_risk_label,
    }
    return long_signals, short_signals, raw


# ─────────────────────────────────────────────────────────────────────────────
# OPTIONS SIGNALS (v12)  — forward-looking flow / IV / positioning
#
# Why this exists: price/volume signals are reactive. Options markets aggregate
# the views of leveraged, often better-informed participants and price expected
# moves, fear, and positioning *before* spot moves. Folding a small set of
# option-derived flags into the existing Bayesian engine is purely additive:
# if the data is missing (no options market, illiquid chain, fetch failure),
# the keys aren't present and probabilities are unchanged.
#
# Backends supported:
#   • US (.US-listed)  → yfinance Ticker.options / option_chain
#   • India (.NS)      → nsepython (only the ~200 F&O-listed stocks have chains)
#   • SGX, HK, others  → no options market or no public chain → skipped
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
def _score_stocks_batch(symbols: list) -> dict:
    """
    ONE batch download → swing score for every symbol.
    Returns {sym: swing_score}
    """
    scored = {}
    if not symbols:
        return scored
    try:
        batch = yf.download(
            symbols, period="1mo", interval="1d",
            progress=False, group_by="ticker",
            threads=True, auto_adjust=True
        )
        for sym in symbols:
            try:
                c  = _extract_closes(batch, sym, len(symbols))
                if isinstance(batch.columns, pd.MultiIndex):
                    v  = batch.xs(sym, axis=1, level=1)["Volume"].ffill().dropna() \
                         if sym in batch.columns.get_level_values(1) \
                         else batch[sym]["Volume"].ffill().dropna()
                    h  = batch.xs(sym, axis=1, level=1)["High"].ffill().dropna() \
                         if sym in batch.columns.get_level_values(1) \
                         else batch[sym]["High"].ffill().dropna()
                    lo = batch.xs(sym, axis=1, level=1)["Low"].ffill().dropna() \
                         if sym in batch.columns.get_level_values(1) \
                         else batch[sym]["Low"].ffill().dropna()
                else:
                    v  = batch["Volume"].squeeze().ffill().dropna()
                    h  = batch["High"].squeeze().ffill().dropna()
                    lo = batch["Low"].squeeze().ffill().dropna()

                if len(c) < 10:
                    continue
                price      = float(c.iloc[-1])
                avg_vol    = float(v.mean())
                dollar_vol = price * avg_vol
                if price < 3 or dollar_vol < 5_000_000:
                    continue
                atr_pct = float(
                    ta.volatility.average_true_range(h, lo, c, window=14).iloc[-1]
                ) / price * 100
                atr_bonus = 1.5 if 2 <= atr_pct <= 12 else (0.7 if atr_pct < 2 else 0.4)
                scored[sym] = dollar_vol * atr_bonus
            except Exception:
                continue
    except Exception:
        pass
    return scored


@st.cache_data(ttl=21600)   # 6-hour cache
def fetch_sector_constituents(target_per_sector: int = 25) -> dict:
    sectors  = {}
    etf_items = list(SECTOR_ETFS.items())
    status   = st.empty()

    # ── Step 1: holdings via FinanceDatabase ──────────────────────────────────
    if _fd_available:
        status.text("📚 Loading ETF holdings...")
        try:
            etfs_db     = fd.ETFs()
            equities_db = fd.Equities()
            for sector_name, etf_ticker in etf_items:
                try:
                    etf_data = etfs_db.select(symbol=etf_ticker)
                    stocks   = []
                    if not etf_data.empty:
                        for col in ["holdings", "top_holdings", "constituents"]:
                            if col in etf_data.columns:
                                rv = etf_data[col].iloc[0]
                                if isinstance(rv, list):
                                    stocks = [str(s).upper().strip() for s in rv
                                              if str(s).strip().replace("-","").isalpha()
                                              and 1 <= len(str(s).strip()) <= 6]
                                elif isinstance(rv, str) and rv:
                                    stocks = [s.upper().strip() for s in rv.split(",")
                                              if s.strip().replace("-","").isalpha()
                                              and 1 <= len(s.strip()) <= 6]
                                if stocks:
                                    break
                        if not stocks and "category" in etf_data.columns:
                            cat = str(etf_data["category"].iloc[0])
                            if cat:
                                cat_df = equities_db.select(category=cat)
                                if not cat_df.empty:
                                    stocks = [s for s in cat_df.index.tolist()
                                              if str(s).replace("-","").isalpha()
                                              and 1 <= len(str(s)) <= 6]
                    if stocks:
                        sectors[sector_name] = {
                            "etf": etf_ticker,
                            "stocks": [s for s in stocks if s != etf_ticker][: target_per_sector * 2],
                            "source": "financedatabase",
                        }
                except Exception:
                    pass
        except Exception:
            pass

    # ── Step 2: yfinance fallback for any missing sector ──────────────────────
    for sector_name, etf_ticker in etf_items:
        if sectors.get(sector_name, {}).get("stocks"):
            continue
        status.text(f"📡 Fetching {etf_ticker} holdings ...")
        try:
            tkr    = yf.Ticker(etf_ticker)
            stocks = []
            for attr in ("portfolio_holdings", "equity_holdings", "top_holdings"):
                try:
                    df_h = getattr(tkr.funds_data, attr)
                    if df_h is None or df_h.empty:
                        continue
                    sym_col = next((c for c in ["Symbol","symbol","Ticker","ticker"]
                                    if c in df_h.columns), None)
                    raw_syms = df_h[sym_col].dropna().astype(str).tolist() if sym_col \
                               else [str(x) for x in df_h.index.tolist()]
                    stocks = [s.strip().upper() for s in raw_syms
                              if s.strip().replace("-","").isalpha()
                              and 1 <= len(s.strip()) <= 6
                              and s.strip().upper() != etf_ticker]
                    if stocks:
                        break
                except Exception:
                    continue
            sectors[sector_name] = {
                "etf": etf_ticker,
                "stocks": stocks[: target_per_sector * 2],
                "source": "",
            }
        except Exception:
            sectors[sector_name] = {"etf": etf_ticker, "stocks": [], "source": "none"}

    # ── Step 3: score ALL stocks in ONE batch download ────────────────────────
    all_syms = list(dict.fromkeys(
        s for d in sectors.values() for s in d.get("stocks", [])
    ))
    status.text(f"📊 Scoring {len(all_syms)} stocks for swing quality...")
    scored_map = _score_stocks_batch(all_syms)

    # ── Step 4: rank each sector by swing score ───────────────────────────────
    out = {}
    for sector_name, data in sectors.items():
        raw  = data.get("stocks", [])
        ranked = sorted(raw, key=lambda s: scored_map.get(s, 0), reverse=True)
        best   = ranked[:target_per_sector]
        out[sector_name] = {**data, "stocks": best, "count": len(best)}

    status.empty()
    return out


# ─────────────────────────────────────────────────────────────────────────────
# LIVE MARKET UNIVERSE — used by Operator Activity / scan source
# ─────────────────────────────────────────────────────────────────────────────
def _clean_symbol(sym: str, suffix: str = "") -> str:
    """Normalise symbols for yfinance and drop obvious non-equity junk."""
    if sym is None:
        return ""
    s = str(sym).strip().upper()
    if not s or s in ("NAN", "NONE", "-", "—"):
        return ""
    s = s.replace(" ", "")
    # yfinance uses '-' for US class shares (BRK-B), not '.'
    if suffix == "" and "." in s and not s.endswith((".SI", ".NS")):
        s = s.replace(".", "-")
    # Remove warrants/rights/preferreds that often break scans.
    bad_fragments = ("-W", "-WT", "-WS", "-R", "-U", "^", "/")
    if any(x in s for x in bad_fragments):
        return ""
    if suffix and not s.endswith(suffix):
        s = f"{s}{suffix}"
    return s


def _unique_keep_order(items):
    out, seen = [], set()
    for item in items:
        if item and item not in seen:
            out.append(item)
            seen.add(item)
    return out


@st.cache_data(ttl=30 * 60, show_spinner=False)
def fetch_yahoo_market_movers(max_per_screener: int = 250) -> list:
    """
    Fetch a broader LIVE Yahoo universe.

    Why count may still be < Max live stocks:
    - Max live stocks is only a cap, not a guaranteed count.
    - Yahoo screeners return only the names currently available in each bucket.
    - Duplicate symbols across screeners are removed before scanning.

    This function uses two Yahoo paths:
      1) yfinance.screen(...) when available
      2) Yahoo Finance screener endpoint as a fallback / expansion path

    The final scan step later merges these live tickers with the full existing
    curated ticker list, so UUUU, APP, etc. remain included even if Yahoo does
    not return them as current movers.
    """
    tickers = []

    # A broad set of Yahoo predefined screeners. Some names may be unsupported
    # depending on the yfinance/Yahoo version; failures are skipped safely.
    screen_names = (
        "most_actives", "day_gainers", "day_losers",
        "undervalued_growth_stocks", "growth_technology_stocks",
        "aggressive_small_caps", "small_cap_gainers", "most_shorted_stocks",
        "portfolio_anchors", "undervalued_large_caps",
        "solid_large_growth_funds", "high_yield_bond", "top_mutual_funds",
    )

    # Path 1: yfinance's built-in screener wrapper.
    try:
        if hasattr(yf, "screen"):
            for scr in screen_names:
                try:
                    res = yf.screen(scr, count=max_per_screener)
                    quotes = res.get("quotes", []) if isinstance(res, dict) else []
                    for q in quotes:
                        sym = _clean_symbol(q.get("symbol", ""))
                        if sym:
                            tickers.append(sym)
                except Exception:
                    continue
    except Exception:
        pass

    # Path 2: Yahoo Finance public screener endpoint with pagination. This often
    # returns more names than yfinance.screen alone.
    try:
        import requests
        url = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
        headers = {"User-Agent": "Mozilla/5.0"}
        per_page = min(max(int(max_per_screener), 25), 250)
        for scr in screen_names:
            for start in range(0, max_per_screener, per_page):
                try:
                    params = {
                        "scrIds": scr,
                        "count": per_page,
                        "start": start,
                        "formatted": "false",
                        "lang": "en-US",
                        "region": "US",
                    }
                    r = requests.get(url, params=params, headers=headers, timeout=12)
                    if not r.ok:
                        break
                    result = (r.json().get("finance", {})
                                      .get("result", [{}])[0])
                    quotes = result.get("quotes", []) or []
                    if not quotes:
                        break
                    for q in quotes:
                        sym = _clean_symbol(q.get("symbol", ""))
                        if sym:
                            tickers.append(sym)
                    # Stop early when Yahoo returned fewer than requested.
                    if len(quotes) < per_page:
                        break
                except Exception:
                    break
    except Exception:
        pass

    return _unique_keep_order(tickers)


@st.cache_data(ttl=12 * 60 * 60, show_spinner=False)
def fetch_us_index_universe(max_symbols: int = 450) -> list:
    """Fetch current US index constituents from public index tables."""
    tickers = []
    sources = [
        ("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", ["Symbol", "Ticker symbol"]),
        ("https://en.wikipedia.org/wiki/Nasdaq-100", ["Ticker", "Symbol"]),
        ("https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average", ["Symbol", "Ticker"]),
    ]
    for url, cols in sources:
        try:
            for tbl in pd.read_html(url):
                col = next((c for c in cols if c in tbl.columns), None)
                if not col:
                    continue
                vals = [_clean_symbol(x) for x in tbl[col].dropna().astype(str).tolist()]
                tickers.extend([v for v in vals if v])
                break
        except Exception:
            continue
    return _unique_keep_order(tickers)[:max_symbols]


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def fetch_sgx_market_universe(max_symbols: int = 180) -> list:
    """
    Fetch Singapore-listed names from live/public market sources.
    Primary source: SGX securities API. Fallback: current STI constituents table.
    """
    tickers = []

    # SGX public securities endpoint changes occasionally; keep it best-effort.
    try:
        import requests
        url = "https://api2.sgx.com/securities/v1.1"
        params = {"excludetypes": "bonds", "params": "nc,cn,code"}
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, params=params, headers=headers, timeout=12)
        if r.ok:
            data = r.json()
            rows = data.get("data", data if isinstance(data, list) else [])
            for row in rows:
                if isinstance(row, dict):
                    code = row.get("code") or row.get("nc") or row.get("symbol") or row.get("ticker")
                elif isinstance(row, (list, tuple)) and row:
                    code = row[0]
                else:
                    code = None
                sym = _clean_symbol(code, ".SI")
                if sym:
                    tickers.append(sym)
    except Exception:
        pass

    # Fallback to STI constituents if SGX endpoint is unavailable.
    if len(tickers) < 20:
        try:
            for tbl in pd.read_html("https://en.wikipedia.org/wiki/Straits_Times_Index"):
                possible_cols = [c for c in tbl.columns if str(c).lower() in ("stock symbol", "symbol", "ticker")]
                if not possible_cols:
                    continue
                vals = [_clean_symbol(x, ".SI") for x in tbl[possible_cols[0]].dropna().astype(str).tolist()]
                tickers.extend([v for v in vals if v])
                break
        except Exception:
            pass

    return _unique_keep_order(tickers)[:max_symbols]


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def fetch_nse_market_universe(max_symbols: int = 220) -> list:
    """Fetch current NSE index constituents from NSE's live index API."""
    tickers = []
    indices = ["NIFTY 50", "NIFTY NEXT 50", "NIFTY MIDCAP 50", "NIFTY SMALLCAP 50"]
    try:
        import requests
        sess = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "application/json,text/plain,*/*",
            "Referer": "https://www.nseindia.com/market-data/live-equity-market",
        }
        # Warm the NSE session/cookies.
        try:
            sess.get("https://www.nseindia.com", headers=headers, timeout=10)
        except Exception:
            pass
        for idx in indices:
            try:
                url = "https://www.nseindia.com/api/equity-stockIndices"
                r = sess.get(url, params={"index": idx}, headers=headers, timeout=12)
                if not r.ok:
                    continue
                data = r.json().get("data", [])
                for row in data:
                    sym = row.get("symbol")
                    if sym and sym not in ("NIFTY 50", "NIFTY NEXT 50"):
                        t = _clean_symbol(sym, ".NS")
                        if t:
                            tickers.append(t)
            except Exception:
                continue
    except Exception:
        pass
    return _unique_keep_order(tickers)[:max_symbols]


@st.cache_data(ttl=30 * 60, show_spinner=False)
def fetch_live_market_universe(market_name: str, max_symbols: int = 350) -> tuple:
    """
    Build the LIVE/Yahoo side of the scan universe.

    Important: this function returns only the live-market tickers, capped by
    max_symbols. The scan step later merges these with the full existing
    curated ticker list, so names like UUUU and APP are not lost simply because
    they are not in today's Yahoo movers/index response.
    """
    if market_name == "🇺🇸 US":
        movers = fetch_yahoo_market_movers(100)
        index_names = fetch_us_index_universe(max_symbols=max_symbols)
        tickers = _unique_keep_order(movers + index_names)
        source = "Yahoo expanded live screeners + current US index constituents"
    elif market_name == "🇸🇬 SGX":
        tickers = fetch_sgx_market_universe(max_symbols=max_symbols)
        source = "SGX securities feed / current STI constituents"
    else:
        tickers = fetch_nse_market_universe(max_symbols=max_symbols)
        source = "NSE live index constituents"

    tickers = _unique_keep_order(tickers)[:max_symbols]
    if len(tickers) < 10:
        return [], "live market universe unavailable"
    return tickers, source


# ─────────────────────────────────────────────────────────────────────────────
# OPERATOR + TRAP DETECTOR — reusable across Stock Analysis and main scan
# ─────────────────────────────────────────────────────────────────────────────
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
                   skip_earnings, top_n_sectors, live_sectors=None,
                   market_tickers=None, enable_options=True):
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
    if total == 0:
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

    # ── Batch OHLCV pre-fetch ─────────────────────────────────────────────────
    status_text.text(f"📥 Batch downloading {total} stocks...")
    batch_cache = {}
    try:
        raw_batch = yf.download(
            all_tickers, period="6mo", interval="1d",
            progress=False, group_by="ticker", threads=True, auto_adjust=True
        )
        for tkr in all_tickers:
            try:
                if isinstance(raw_batch.columns, pd.MultiIndex):
                    lvl1 = raw_batch.columns.get_level_values(1)
                    lvl0 = raw_batch.columns.get_level_values(0)
                    if tkr in lvl1:    df_t = raw_batch.xs(tkr, axis=1, level=1).copy()
                    elif tkr in lvl0:  df_t = raw_batch[tkr].copy()
                    else:              continue
                elif len(all_tickers) == 1:
                    df_t = raw_batch.copy()
                else:
                    continue
                df_t = df_t.ffill().dropna()
                if len(df_t) >= 60:
                    batch_cache[tkr] = df_t
            except Exception:
                continue
        status_text.text(f"✅ {len(batch_cache)}/{total} stocks loaded")
    except Exception as e:
        status_text.text(f"Batch failed ({e}), fetching individually...")

    # ── Regime thresholds — lowered to catch more real swing candidates ──────
    min_score_strong_long  = 5 if regime == "BULL"               else 6
    min_prob_strong_long   = 0.68 if regime == "BULL"            else 0.74
    min_score_strong_short = 4 if regime in ("BEAR", "CAUTION")  else 5
    min_prob_strong_short  = 0.65 if regime in ("BEAR", "CAUTION") else 0.68

    for i, ticker in enumerate(all_tickers):
        try:
            status_text.text(f"Scanning {ticker} ({i+1}/{total})...")

            # ── Earnings guard (14 days) ──────────────────────────────────────
            if skip_earnings:
                try:
                    info_cal = yf.Ticker(ticker).calendar
                    if info_cal is not None and not info_cal.empty:
                        ed = info_cal.loc["Earnings Date"].iloc[0] \
                             if "Earnings Date" in info_cal.index else info_cal.iloc[0, 0]
                        if not pd.isnull(ed):
                            days_out = (pd.Timestamp(ed).date() - datetime.today().date()).days
                            if 0 <= days_out <= 7:   # 7-day guard (was 14)
                                progress_bar.progress((i + 1) / total)
                                continue
                except Exception:
                    pass

            # Use pre-fetched batch or individual fallback
            if ticker in batch_cache:
                df = batch_cache[ticker]
            else:
                raw_ind = yf.download(ticker, period="6mo", interval="1d",
                                      progress=False, auto_adjust=True)
                if raw_ind.empty or len(raw_ind) < 60:
                    progress_bar.progress((i + 1) / total)
                    continue
                if isinstance(raw_ind.columns, pd.MultiIndex):
                    raw_ind.columns = raw_ind.columns.get_level_values(0)
                df = raw_ind.ffill().dropna()

            if len(df) < 60:
                progress_bar.progress((i + 1) / total)
                continue

            close = df["Close"].squeeze().ffill()
            high  = df["High"].squeeze().ffill()
            low   = df["Low"].squeeze().ffill()
            vol   = df["Volume"].squeeze().ffill()

            # ── Pre-filter: liquidity only ────────────────────────────────────
            _vol_avg_s = float(vol.rolling(20).mean().iloc[-1])
            _p_chk     = float(close.iloc[-1])
            _atr_pct   = float(ta.volatility.average_true_range(
                             high, low, close, window=14).iloc[-1]) / _p_chk * 100 \
                         if _p_chk > 0 else 0
            # Skip if dollar volume < $500k/day (illiquid) or ATR < 0.8% (can't swing 5-10%)
            if _p_chk * _vol_avg_s < 500_000 or _atr_pct < 0.8:
                progress_bar.progress((i + 1) / total)
                continue

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
            today_chg = float(
                (close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100
            ) if len(close) >= 2 else 0.0

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
                    try:
                        rets   = close.pct_change().dropna().tail(20)
                        rv_pct = float(rets.std() * (252 ** 0.5) * 100) \
                                 if len(rets) >= 10 else None
                        opt_long, opt_short, opt_raw = compute_options_signals(
                            ticker, p, rv_pct
                        )
                    except Exception:
                        opt_long, opt_short, opt_raw = ({}, {}, {})

            # Merge option signals into the existing signal dicts. The
            # Bayesian engine only consumes keys present in LONG_WEIGHTS /
            # SHORT_WEIGHTS, so this is purely additive.
            long_sig  = {**long_sig,  **opt_long}
            short_sig = {**short_sig, **opt_short}

            # ── Float and short interest from yfinance.info ───────────────────
            float_shares = short_pct = pe = None
            try:
                inf = yf.Ticker(ticker).info
                float_shares = inf.get("floatShares")
                short_pct    = inf.get("shortPercentOfFloat")
                pe           = inf.get("trailingPE")
            except Exception:
                pass

            float_str = f"{float_shares/1e6:.0f}M" if float_shares else "–"
            short_str = f"{short_pct*100:.1f}%" if short_pct else "–"
            # Short squeeze flag: high short interest + bullish signals
            squeeze_flag = (short_pct or 0) > 0.15

            # ── Signal combination quality multiplier ─────────────────────────
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
            high_accuracy_long = (
                l_prob >= 0.82 and
                l_score >= 8 and
                raw.get("above_ma60", False) and
                raw.get("not_chasing", False) and
                raw.get("not_limit_up", False) and
                raw.get("today_chg_pct", 99) < 6 and
                operator_confirmed and
                raw.get("vwap_support", False) and
                not trap_risk and
                long_sig.get("trend_daily", False) and
                long_sig.get("weekly_trend", False) and
                long_sig.get("rel_strength", False) and
                volume_confirmed
            )

            if high_accuracy_long:
                l_action = "STRONG BUY"
            elif trap_risk:
                l_action = "WATCH – TRAP RISK"
            elif l_score >= min_score_strong_long and l_prob >= min_prob_strong_long and l_top3:
                l_action = "WATCH – HIGH QUALITY"
            elif l_score >= 4 and l_prob >= 0.62 and long_sig["trend_daily"]:
                l_action = "WATCH – DEVELOPING"
            elif l_score >= 3 and long_sig["trend_daily"]:
                l_action = "WATCH – EARLY"
            else:
                l_action = None

            if l_action:
                # ── Strategy stop: MA60 or swing low (whichever is higher = tighter) ──
                l_atr_stop   = round(p - 1.5 * atrv, 2)
                l_swing_stop = round(raw["last_swing_low"] * 0.995, 2)
                l_ma60_stop  = round(raw["ma60"] * 0.995, 2)   # MA60 hard stop
                l_stop       = max(l_atr_stop, l_swing_stop, l_ma60_stop)
                l_risk       = max(p - l_stop, p * 0.001)       # prevent zero division

                # ── Strategy profit targets: 10% (short-term), 15%, 20% (swing) ────
                l_pt_short   = round(p * 1.10, 2)   # +10%  short-term take-profit (batch 1)
                l_pt_swing1  = round(p * 1.15, 2)   # +15%  swing take-profit (batch 2)
                l_pt_swing2  = round(p * 1.20, 2)   # +20%  swing full target (batch 3)
                l_trail      = round(p + l_risk * 0.5, 2)
                l_time_stop  = "Day 4 if < +5%"

                # ── Strategy filter tags ──────────────────────────────────────────
                strat_tags = []
                if raw.get("dip_to_ma20"):   strat_tags.append("📍DIP-MA20")
                if raw.get("dip_to_ma60"):   strat_tags.append("📍DIP-MA60")
                if raw.get("vol_declining"): strat_tags.append("📉VOL-DIP")
                if not raw.get("not_chasing", True):  strat_tags.append("⚠️CHASING")
                if not raw.get("not_limit_up", True): strat_tags.append("🚫LIMIT-UP")
                if raw.get("ma60_stop_triggered"):     strat_tags.append("🛑MA60-BREAK")

                # Strategy entry quality
                is_ideal_dip = (raw.get("dip_to_ma20") or raw.get("dip_to_ma60")) and \
                               raw.get("vol_declining") and raw.get("not_chasing") and \
                               raw.get("not_limit_up")
                is_vol_surge = long_sig.get("vol_surge_up", False)   # vol burst entry
                is_chasing   = not raw.get("not_chasing", True) or not raw.get("not_limit_up", True)
                is_stopped   = raw.get("ma60_stop_triggered", False)

                if is_stopped:
                    entry_quality = "🚫 AVOID"
                elif high_accuracy_long and (is_ideal_dip or is_vol_surge or long_sig.get("pocket_pivot", False) or long_sig.get("vol_breakout", False)):
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
                if is_monday:                   l_tags.append("⚠️MON")
                if combo_bonus > 0:             l_tags.append(f"COMBO+{combo_bonus:.0%}")
                if high_accuracy_long:          l_tags.append("🎯HIGH-ACCURACY")
                elif l_prob >= 0.82:            l_tags.append("⚠️PROB-NO-GATE")
                l_tags.extend(strat_tags)       # append strategy tags

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
                    "BB Squeeze":     "YES" if long_sig["bb_bull_squeeze"] else "–",
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
            high_accuracy_short = (
                s_prob >= 0.82 and
                s_score >= 5 and
                short_sig.get("trend_bearish", False) and
                short_momentum_confirmed and
                short_volume_confirmed and
                raw.get("today_chg_pct", 0) > -6.0 and   # avoid chasing big gap-downs
                raw.get("today_chg_pct", 0) < 2.0 and    # avoid shorting strong green days
                not squeeze_flag                         # avoid crowded squeeze risk
            )

            if high_accuracy_short:
                s_action = "STRONG SHORT"
            elif s_score >= min_score_strong_short and s_prob >= min_prob_strong_short and s_top3:
                s_action = "WATCH SHORT – HIGH QUALITY"
            elif s_score >= 4 and s_prob >= 0.60 and short_sig["trend_bearish"]:
                s_action = "WATCH SHORT – DEVELOPING"
            elif s_score >= 3 and short_sig["trend_bearish"]:
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
                elif high_accuracy_short and (s_is_ideal or short_sig.get("operator_distribution", False)):
                    s_entry_quality = "✅ SELL"
                elif s_is_chasing:
                    s_entry_quality = "⏳ WAIT"
                else:
                    s_entry_quality = "👀 WATCH"

                short_results.append({
                    "Ticker":         ticker,
                    "Sector":         sector_label(ticker),
                    "Action":         s_action,
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
                    "Signals":        " | ".join(s_tags) if s_tags else "–",
                    "Opt Flow":       " | ".join(opt_s_tags) if opt_s_tags else "–",
                })

        except Exception:
            pass
        progress_bar.progress((i + 1) / total)

    status_text.empty()
    progress_bar.empty()

    def make_df(rows, prob_col):
        if not rows:
            return pd.DataFrame()
        df_out = pd.DataFrame(rows)
        df_out["_s"] = df_out[prob_col].str.rstrip("%").astype(float)
        return df_out.sort_values("_s", ascending=False).drop(columns="_s")

    def make_op_df(rows):
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(rows).sort_values(
            ["_high_count", "_trap_count", "_op_score"],
            ascending=[False, False, False]
        )

    return (make_df(long_results, "Rise Prob"),
            make_df(short_results, "Fall Prob"),
            make_op_df(operator_results))


# ─────────────────────────────────────────────────────────────────────────────
# DIAGNOSTICS  — v5 exact
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def diagnose_ticker(ticker, regime):
    try:
        raw = yf.download(ticker, period="6mo", interval="1d",
                          progress=False, auto_adjust=True)
        if raw.empty or len(raw) < 60:
            return {"Error": f"Insufficient data ({len(raw)} bars)"}
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        close = raw["Close"].squeeze().ffill()
        high  = raw["High"].squeeze().ffill()
        low   = raw["Low"].squeeze().ffill()
        vol   = raw["Volume"].squeeze().ffill()
        long_sig, short_sig, rv = compute_all_signals(close, high, low, vol)
        l_score = sum(long_sig.values())
        s_score = sum(short_sig.values())
        l_prob  = bayesian_prob(LONG_WEIGHTS,  long_sig)
        s_prob  = bayesian_prob(SHORT_WEIGHTS, short_sig)

        def tick(ok, detail=""):
            return ("PASS  " + detail) if ok else ("FAIL  " + detail)

        return {
            "Regime":                   regime,
            "Price":                    f"${rv['p']:.2f}",
            "EMA8 / EMA21":             f"${rv['e8']:.2f} / ${rv['e21']:.2f}",
            "RSI [-3,-2,-1]":           f"{rv['rsi2']:.1f}→{rv['rsi1']:.1f}→{rv['rsi0']:.1f}",
            "Stoch K [-3,-2,-1]":       f"{rv['k2']:.1f}→{rv['k1']:.1f}→{rv['k0']:.1f}  D={rv['d0']:.1f}",
            "MACD hist [-3,-2,-1]":     f"{rv['mh2']:.4f}→{rv['mh1']:.4f}→{rv['mh0']:.4f}",
            "MACD line / signal":       f"{rv['ml']:.4f} / {rv['ms']:.4f}",
            "ADX / Vol ratio":          f"{rv['adx']:.1f} / {rv['vr']:.2f}×",
            "VWAP":                     f"${rv.get('vwap', rv['p']):.2f} · price {'ABOVE' if rv.get('above_vwap') else 'BELOW'} VWAP",
            "Operator activity":        f"{rv.get('operator_label','–')} · score {rv.get('operator_score',0)} · trap {rv.get('trap_risk_label','–')}",
            "BB squeeze":               f"{'YES' if rv['bb_squeeze'] else 'NO'}  price {'ABOVE' if rv['p']>rv['bbm'] else 'BELOW'} midline",
            "Last swing low":           f"${rv['last_swing_low']:.2f}  ({rv['swing_lows_count']} lows detected)",
            "Last swing high":          f"${rv['last_swing_high']:.2f}  ({rv['swing_highs_count']} highs detected)",
            "── LONG ──":              "",
            "1. Trend bullish":         tick(long_sig["trend_daily"],
                f"price={rv['p']:.2f} ema8={rv['e8']:.2f} ema21={rv['e21']:.2f}"),
            "2. Stoch bounce":          tick(long_sig["stoch_confirmed"],
                f"k2={rv['k2']:.0f}<20 k1={rv['k1']:.0f}<20 k0={rv['k0']:.0f}>D={rv['d0']:.0f}"),
            "3. BB bull squeeze":       tick(long_sig["bb_bull_squeeze"],
                f"squeeze={'YES' if rv['bb_squeeze'] else 'NO'}  above_mid={'YES' if rv['p']>rv['bbm'] else 'NO'}"),
            "4. MACD accel":            tick(long_sig["macd_accel"],
                f"mh0={rv['mh0']:.4f}>mh1={rv['mh1']:.4f}>mh2={rv['mh2']:.4f}"),
            "5. MACD cross bull":       tick(long_sig["macd_cross"],
                f"line={rv['ml']:.4f}>sig={rv['ms']:.4f}"),
            "6. RSI >50 confirmed":     tick(long_sig["rsi_confirmed"],
                f"rsi2={rv['rsi2']:.1f}<50 rsi1={rv['rsi1']:.1f}>=50 rsi0={rv['rsi0']:.1f}>rsi1"),
            "7. ADX >20":               tick(long_sig["adx"],   f"adx={rv['adx']:.1f}"),
            "8. Vol >1.5×":             tick(long_sig["volume"], f"ratio={rv['vr']:.2f}×"),
            "9. Vol breakout":          tick(long_sig["vol_breakout"],
                f"price={rv['p']:.2f} 10dH={rv['h10']:.2f} vol={rv['vr']:.2f}×"),
            "10. Higher lows":          tick(long_sig["higher_lows"],
                f"{rv['swing_lows_count']} swing lows in last 60 bars"),
            "11. Operator accumulation": tick(long_sig.get("operator_accumulation", False),
                f"score={rv.get('operator_score',0)} label={rv.get('operator_label','–')}"),
            "12. VWAP support":         tick(long_sig.get("vwap_support", False),
                f"price={rv['p']:.2f} vwap={rv.get('vwap', rv['p']):.2f}"),
            "LONG score / prob":        f"{l_score}/{len(long_sig)}  →  {l_prob*100:.1f}%  ({prob_label(l_prob)})",
            "── SHORT ──":             "",
            "1. Trend bearish":         tick(short_sig["trend_bearish"],
                f"price={rv['p']:.2f} ema8={rv['e8']:.2f} ema21={rv['e21']:.2f}"),
            "2. Stoch rollover":        tick(short_sig["stoch_overbought"],
                f"k2={rv['k2']:.0f}>80 k1={rv['k1']:.0f}>80 k0={rv['k0']:.0f}<D={rv['d0']:.0f}"),
            "3. BB bear squeeze":       tick(short_sig["bb_bear_squeeze"],
                f"squeeze={'YES' if rv['bb_squeeze'] else 'NO'}  below_mid={'YES' if rv['p']<rv['bbm'] else 'NO'}"),
            "4. MACD decel":            tick(short_sig["macd_decel"],
                f"mh0={rv['mh0']:.4f}<mh1={rv['mh1']:.4f}<mh2={rv['mh2']:.4f}"),
            "5. MACD cross bear":       tick(short_sig["macd_cross_bear"],
                f"line={rv['ml']:.4f}<sig={rv['ms']:.4f}"),
            "6. RSI <50 confirmed":     tick(short_sig["rsi_cross_bear"],
                f"rsi2={rv['rsi2']:.1f}>50 rsi1={rv['rsi1']:.1f}<=50 rsi0={rv['rsi0']:.1f}<rsi1"),
            "7. ADX >20 downtrend":     tick(short_sig["adx_bear"],
                f"adx={rv['adx']:.1f} price<ema21={rv['e21']:.2f}"),
            "8. Dist day (red+2×vol)":  tick(short_sig["high_volume_down"],
                f"red={'YES' if rv['candle_red'] else 'NO'}  vol={rv['vr']:.2f}×"),
            "9. Vol breakdown":         tick(short_sig["vol_breakdown"],
                f"price={rv['p']:.2f} 10dL={rv['l10']:.2f} vol={rv['vr']:.2f}×"),
            "10. Lower highs":          tick(short_sig["lower_highs"],
                f"{rv['swing_highs_count']} swing highs in last 60 bars"),
            "11. Operator distribution": tick(short_sig.get("operator_distribution", False),
                f"trap={rv.get('trap_risk_label','–')} vol={rv['vr']:.2f}×"),
            "12. Below VWAP":           tick(short_sig.get("below_vwap", False),
                f"price={rv['p']:.2f} vwap={rv.get('vwap', rv['p']):.2f}"),
            "SHORT score / prob":       f"{s_score}/{len(short_sig)}  →  {s_prob*100:.1f}%  ({prob_label(s_prob)})",
        }
    except Exception as e:
        return {"Error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
st.sidebar.header("Scan settings")
top_n_sectors  = st.sidebar.slider("Top N green/red sectors to scan", 1, 6, 3)
min_prob_long  = st.sidebar.slider("Min LONG rise prob (%)",  40, 95, 62)
min_prob_short = st.sidebar.slider("Min SHORT fall prob (%)", 40, 95, 60)
skip_earnings  = st.sidebar.checkbox("Skip earnings within 7 days", False)
use_live_universe = st.sidebar.checkbox(
    "Use live market universe",
    value=False,
    help="When ON, the scanner and Operator Activity tab fetch the market universe "
         "from live/public market sources first (Yahoo movers + index constituents, "
         "SGX securities feed, NSE index API), then merges them with the full existing "
         "curated ticker list. Tickers in 'Always include tickers' are also forced in. "
         "This means stocks like UUUU/APP remain scanned even if they are not in today's movers.",
)
max_live_universe = st.sidebar.slider(
    "Max live stocks to scan", 50, 1000, 250, step=25,
    help="Limits only the live/Yahoo side of the universe. Existing curated tickers "
         "and always-include tickers are added on top of this limit.",
)
always_include_text = st.sidebar.text_area(
    "Always include tickers",
    value="",
    height=68,
    help="Comma- or line-separated tickers that are always scanned, even when "
         "Use live market universe is ON. Example: UUUU, APP, NVDA, D05.SI",
)
always_include_tickers = [
    t.strip().upper()
    for t in always_include_text.replace("\n", ",").split(",")
    if t.strip()
]
enable_options = st.sidebar.checkbox(
    "Use options data (US + India F&O, +30–60s)",
    value=False,
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
    value=False,
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
    value=True,
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
req_stoch = st.sidebar.checkbox("Must have Stoch bounce",      False)
req_bb    = st.sidebar.checkbox("Must have BB bull squeeze",   False)
req_accel = st.sidebar.checkbox("Must have MACD acceleration", False)

st.sidebar.markdown("---")
st.sidebar.header("Short signal filters")
req_s_stoch = st.sidebar.checkbox("Must have Stoch rollover",    False)
req_s_bb    = st.sidebar.checkbox("Must have BB bear squeeze",   False)
req_s_decel = st.sidebar.checkbox("Must have MACD deceleration", False)

st.sidebar.markdown("---")
st.sidebar.header("Custom tickers")
extra_input = st.sidebar.text_input("Add tickers (comma-separated)", placeholder="HIMS, NVTS")

st.sidebar.markdown("---")
st.sidebar.markdown(
    f"**Data sources**\n\n"
    f"✅ yfinance · US options\n\n"
    f"{'✅' if _fd_available else '⚠️'} FinanceDatabase "
    f"({'installed' if _fd_available else 'pip install financedatabase'})\n\n"
    f"{'✅' if _nse_opt_available else '⚠️'} nsepython · India F&O options "
    f"({'installed' if _nse_opt_available else 'pip install nsepython'})"
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
    "🌍 Market", ["🇺🇸 US", "🇸🇬 SGX", "🇮🇳 India"],
    horizontal=True, key="market_selector", label_visibility="collapsed"
)

# Map selection → ticker list, sector map, currency symbol
if market_sel == "🇺🇸 US":
    _active_tickers = US_TICKERS;  _active_sectors = SECTOR_ETFS
    _currency_sym = "$";           _price_fmt = lambda p: f"${p:,.2f}"
elif market_sel == "🇸🇬 SGX":
    _active_tickers = SG_TICKERS;  _active_sectors = {}
    _currency_sym = "S$";          _price_fmt = lambda p: f"S${p:,.3f}"
else:
    _active_tickers = INDIA_TICKERS; _active_sectors = INDIA_SECTOR_ETFS
    _currency_sym = "₹";            _price_fmt = lambda p: f"₹{p:,.2f}"

# ─────────────────────────────────────────────────────────────────────────────


tab_sectors, tab_long, tab_swing_picks, tab_strategy, tab_short, tab_operator, tab_both, tab_etf, tab_stock, tab_earn, tab_event, tab_lt, tab_diag, tab_backtest, tab_help = st.tabs([
    "🗂️ Sector Heatmap",
    "📈 Long Setups",
    "🎯 Swing Picks",
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
with tab_sectors:
    st.caption("🗺️ Sector Heatmap")

    if market_sel == "🇺🇸 US":
        st.caption("US Sector ETFs · Refreshes every 15 min")
        sector_df = get_sector_performance()
    elif market_sel == "🇸🇬 SGX":
        st.caption("SGX sector groups (avg return) · Prices in S$ · Refreshes every 15 min")
        sector_df = get_sg_sector_performance()
        st.info("ℹ️ SGX has no liquid sector ETFs — sectors are computed as the average return of constituent stocks.")
    else:
        st.caption("NSE Sector Indices · Prices in ₹ · Refreshes every 15 min")
        sector_df = get_india_sector_performance()
        # Show Nifty 50 banner
        nifty = sector_df[sector_df["ETF"] == "^NSEI"]
        if not nifty.empty:
            n50p = nifty.iloc[0]["Today %"]
            n50v = nifty.iloc[0]["Price"]
            cc1, cc2 = st.columns(2)
            cc1.metric("🇮🇳 Nifty 50", f"₹{n50v:,.0f}", f"{n50p:+.2f}%")
            cc2.metric("Session", "NSE 09:15–15:30 IST")
        sector_df = sector_df[sector_df["ETF"] != "^NSEI"]

    if sector_df.empty or "Today %" not in sector_df.columns:
        st.warning(
            "Could not fetch sector data.\n\n"
            "- Markets may be closed (weekend/holiday)\n"
            "- Try: `pip install --upgrade yfinance`"
        )
    else:
        def tile_color(pct):
            if   pct >  2.0: return "#1a7a3a","#ffffff"
            elif pct >  0.5: return "#27ae60","#ffffff"
            elif pct >  0.1: return "#a9dfbf","#145a32"
            elif pct < -2.0: return "#922b21","#ffffff"
            elif pct < -0.5: return "#e74c3c","#ffffff"
            elif pct < -0.1: return "#f5b7b1","#7b241c"
            else:            return "#e8e8e8","#555555"

        p_sym = "₹" if market_sel == "🇮🇳 India" else ("S$" if market_sel == "🇸🇬 SGX" else "$")
        html = "<div style='display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-bottom:16px'>"
        for _, row in sector_df.iterrows():
            bg, fg = tile_color(row["Today %"])
            arrow  = "▲" if row["Today %"] > 0 else ("▼" if row["Today %"] < 0 else "—")
            fived  = row.get("5d %", 0.0)
            html += (
                f"<div style='background:{bg};color:{fg};border-radius:8px;padding:10px 12px'>"
                f"<div style='font-size:10px;font-weight:700;opacity:.8'>{row['ETF']}</div>"
                f"<div style='font-size:13px;font-weight:700;margin:2px 0'>{row['Sector']}</div>"
                f"<div style='font-size:22px;font-weight:800'>{arrow} {row['Today %']:+.2f}%</div>"
                f"<div style='font-size:11px;opacity:.85'>5d: {fived:+.2f}%  ·  {p_sym}{row['Price']:,.0f}</div>"
                f"</div>"
            )
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)

        green_list = sector_df[sector_df["Today %"] >  0.1]["Sector"].tolist()
        red_list   = sector_df[sector_df["Today %"] < -0.1]["Sector"].tolist()
        flat_list  = sector_df[
            (sector_df["Today %"] >= -0.1) & (sector_df["Today %"] <= 0.1)
        ]["Sector"].tolist()

        cg, cr = st.columns(2)
        with cg:
            body = " · ".join(f"**{s}** {sector_df.loc[sector_df['Sector']==s,'Today %'].values[0]:+.2f}%" for s in green_list)
            st.success(f"🟢 **{len(green_list)} Green**\n\n{body}" if body else "🟢 No green sectors")
        with cr:
            body = " · ".join(f"**{s}** {sector_df.loc[sector_df['Sector']==s,'Today %'].values[0]:+.2f}%" for s in red_list)
            st.error(f"🔴 **{len(red_list)} Red**\n\n{body}" if body else "🔴 No red sectors")
        if flat_list:
            st.info("⚪ **Flat:** " + " · ".join(flat_list))

# ─────────────────────────────────────────────────────────────────────────────
# SCAN BUTTON  (market-aware)
# ─────────────────────────────────────────────────────────────────────────────
col_btn, col_info = st.columns([1, 3])

with col_btn:
        run = st.button(f"🚀 Scan {market_sel} Stocks", type="primary")
with col_info:
    # Show sector preview for the active market
    if market_sel == "🇺🇸 US":
        sdf_preview = get_sector_performance()
    elif market_sel == "🇸🇬 SGX":
        sdf_preview = get_sg_sector_performance()
    else:
        sdf_preview = get_india_sector_performance()
        sdf_preview = sdf_preview[sdf_preview["ETF"] != "^NSEI"]

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
    # Get sector data for the selected market
    if market_sel == "🇺🇸 US":
        sdf = get_sector_performance()
        active_sector_etfs = SECTOR_ETFS
    elif market_sel == "🇸🇬 SGX":
        sdf = get_sg_sector_performance()
        active_sector_etfs = {}   # no ETF-based holdings for SGX
    else:
        sdf = get_india_sector_performance()
        sdf = sdf[sdf["ETF"] != "^NSEI"]   # exclude benchmark
        active_sector_etfs = INDIA_SECTOR_ETFS

    if sdf.empty or "Today %" not in sdf.columns:
        st.error("Cannot fetch sector data. Check connection or upgrade yfinance.")
        st.stop()

    green_sectors = sdf[sdf["Today %"] >  0.1]["Sector"].tolist()
    red_sectors   = sdf[sdf["Today %"] < -0.1]["Sector"].tolist()

    extra_tickers = [t.strip().upper() for t in extra_input.split(",") if t.strip()]

    if not green_sectors and not red_sectors:
        st.warning("All sectors flat — market may be closed or data unavailable.")
    else:
        # Fetch live ETF holdings only for US (India/SGX use static ticker lists)
        live_sectors = {}
        if market_sel == "🇺🇸 US":
            st.info("📡 Fetching live US ETF holdings...")
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

        st.info(
            f"📊 Scanning **{len(active_tickers)} {market_sel} stocks** for signals... "
            f"Universe: **{universe_source}** · "
            f"Live: **{len(live_tickers)}** · Existing: **{len(_active_tickers)}**"
        )

        with st.spinner(f"Scanning {len(active_tickers)} stocks..."):
            df_long, df_short, df_operator = fetch_analysis(
                tuple(green_sectors), tuple(red_sectors),
                regime, skip_earnings, top_n_sectors,
                live_sectors if live_sectors else None,
                market_tickers=tuple(active_tickers),
                enable_options=enable_options,
            )

        # Apply sidebar filters
        if not df_long.empty:
            df_long["_p"] = df_long["Rise Prob"].str.rstrip("%").astype(float)
            df_long = df_long[df_long["_p"] >= min_prob_long]
            if req_stoch: df_long = df_long[df_long["Signals"].str.contains("STOCH")]
            if req_bb:    df_long = df_long[df_long["BB Squeeze"] == "YES"]
            if req_accel: df_long = df_long[df_long["Signals"].str.contains("MACD ACCEL")]
            # v12: hard options filter
            if opt_required and enable_options and "Opt Flow" in df_long.columns:
                df_long = df_long[df_long["Opt Flow"] != "–"]
            df_long = df_long.drop(columns="_p")

        if not df_short.empty:
            df_short["_p"] = df_short["Fall Prob"].str.rstrip("%").astype(float)
            df_short = df_short[df_short["_p"] >= min_prob_short]
            if req_s_stoch: df_short = df_short[df_short["Signals"].str.contains("STOCH")]
            if req_s_bb:    df_short = df_short[df_short["Signals"].str.contains("BB BEAR")]
            if req_s_decel: df_short = df_short[df_short["Signals"].str.contains("MACD DECEL")]
            # v12: hard options filter
            if opt_required and enable_options and "Opt Flow" in df_short.columns:
                df_short = df_short[df_short["Opt Flow"] != "–"]
            df_short = df_short.drop(columns="_p")

        st.session_state["df_long"]            = df_long
        st.session_state["df_short"]           = df_short
        st.session_state["df_operator"]        = df_operator
        st.session_state["live_sectors_cache"] = live_sectors
        st.session_state["last_market"]        = market_sel
        st.session_state["last_universe_source"] = universe_source
        st.session_state["last_universe_count"]  = len(active_tickers)
        st.session_state["last_live_ticker_count"] = len(live_tickers)
        st.session_state["last_existing_ticker_count"] = len(_active_tickers)
        st.session_state["last_scanned_tickers"] = list(active_tickers)
        st.session_state["last_scanned_tickers_csv"] = ", ".join(active_tickers)
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
    if not df_long.empty:
        # v12: count how many of the displayed setups have option-flow tags
        _n_opt_l = int((df_long["Opt Flow"] != "–").sum()) \
                   if "Opt Flow" in df_long.columns else 0
        st.caption(
            f"Results for **{last_market}** · {len(df_long)} setups · "
            f"🧩 **{_n_opt_l}** options-confirmed"
        )
    st.info(
        "📐 **Strategy** — Stop: MA60 · Targets: TP1 +10% · TP2 +15% · TP3 +20% | "
        "**✅ BUY** = high-prob setup + operator accumulation + VWAP support + no trap risk · "
        "**⏳ WAIT** = price too extended · "
        "**👀 WATCH** = setup ok, no ideal dip yet · "
        "**🚫 AVOID** = MA60 broken. New columns: Operator, Op Score, VWAP, Trap Risk."
    )
    if df_long.empty:
        st.info("Run the scan to see long setups.")
    else:
        strong_l  = df_long[df_long["Action"] == "STRONG BUY"]
        watch_hql = df_long[df_long["Action"] == "WATCH – HIGH QUALITY"]
        watch_dvl = df_long[df_long["Action"] == "WATCH – DEVELOPING"]

        st.caption(
            f"🔥 **{len(strong_l)}** Strong Buy · "
            f"👀 **{len(watch_hql)}** High Quality · "
            f"📋 **{len(watch_dvl)}** Developing · "
            f"🗂️ **{df_long['Sector'].nunique()}** Sectors · "
            f"Top: **{df_long['Rise Prob'].iloc[0]}**"
        )

        # sec_cnt = df_long.groupby("Sector").size().reset_index(name="Setups")
        # st.dataframe(sec_cnt, width="stretch", hide_index=True)

        st.caption("🔥 Strong Buy")
        show_table(strong_l, "strong buy", "Rise Prob")
        st.caption("👀 High Quality")
        show_table(watch_hql, "high quality", "Rise Prob")
        st.caption("📋 Developing")
        show_table(watch_dvl, "developing", "Rise Prob")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — SHORT
# ─────────────────────────────────────────────────────────────────────────────
with tab_short:
    st.warning("⚠️ Short selling has unlimited loss potential. Always use a hard cover-stop.")
    if not df_short.empty:
        # v12: count how many of the displayed setups have option-flow tags
        _n_opt_s = int((df_short["Opt Flow"] != "–").sum()) \
                   if "Opt Flow" in df_short.columns else 0
        st.caption(
            f"Results for **{last_market}** · {len(df_short)} setups · "
            f"🧩 **{_n_opt_s}** options-confirmed"
        )
    st.info(
        "📐 **Strategy** — Stop: Cover Stop · Targets: T1 −10% · T2 −20% | "
        "**✅ SELL** = confirmed downtrend + below VWAP + distribution/volume confirmation · "
        "**⏳ WAIT** = gapped down too far, wait for bounce · "
        "**👀 WATCH** = setup forming · "
        "**🚫 AVOID** = above MA60, trend not confirmed. New columns: Operator, Op Score, VWAP, Trap Risk."
    )
    if df_short.empty:
        st.info("Run the scan to see short setups.")
    else:
        strong_s  = df_short[df_short["Action"] == "STRONG SHORT"]
        watch_hqs = df_short[df_short["Action"] == "WATCH SHORT – HIGH QUALITY"]
        watch_dvs = df_short[df_short["Action"] == "WATCH SHORT – DEVELOPING"]

        st.caption(
            f"🔥 **{len(strong_s)}** Strong Short · "
            f"👀 **{len(watch_hqs)}** High Quality · "
            f"📋 **{len(watch_dvs)}** Developing · "
            f"🗂️ **{df_short['Sector'].nunique()}** Sectors · "
            f"Top: **{df_short['Fall Prob'].iloc[0]}**"
        )

        # sec_cnt = df_short.groupby("Sector").size().reset_index(name="Setups")
        # st.dataframe(sec_cnt, width="stretch", hide_index=True)

        st.caption("🔥 Strong Short")
        show_table(strong_s, "strong short", "Fall Prob")
        st.caption("👀 High Quality")
        show_table(watch_hqs, "hq short", "Fall Prob")
        st.caption("📋 Developing")
        show_table(watch_dvs, "developing short", "Fall Prob")

        with st.expander("📖 How to read the short table"):
            st.markdown("""
**Fall Prob** — probability the price falls within 5–7 sessions.

**Cover Stop** — price at which you buy back to exit if wrong. Place as a hard stop-limit immediately.

**Signal tags:**
`STOCH ROLLOVER` — overbought K>80 × 2 bars, now crossing down  
`BB BEAR SQ` — BB squeeze with price below midline  
`MACD DECEL` — histogram declining 3 consecutive bars  
`DIST DAY` — large red candle on 2× average volume  
`VOL BREAKDOWN` — 10-day low on above-average volume  
`LOWER HIGHS` — two consecutive lower swing highs
            """)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3b — OPERATOR ACTIVITY (universe-wide manipulation footprint scan)
# ─────────────────────────────────────────────────────────────────────────────
with tab_operator:
    st.caption("🪤 Operator Activity — every stock from the latest scanned market universe with manipulation footprints")
    st.warning(
        "⚠️ Operator activity is a **directional bias signal**, not a trade trigger. "
        "Use it alongside the Long/Short scorecards. Pattern-based detection produces "
        "false positives in volatile but legitimate trends — confirm with the chart "
        "before entering."
    )

    if df_operator.empty:
        st.info(
            "Run the scan first. With **Use live market universe** ON, this tab fetches "
            "stocks from the selected market source instead of only using the hard-coded "
            "watchlist. Every stock with operator activity (op-score ≥ 2 or any trap "
            "pattern) will appear here."
        )
    else:
        df_op = df_operator.copy()

        # ── Headline metrics ─────────────────────────────────────────────────
        n_total   = len(df_op)
        n_high    = int((df_op["_high_count"] > 0).sum())
        n_bull    = int((df_op["_bias_score"] >  0).sum())
        n_bear    = int((df_op["_bias_score"] <  0).sum())

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("🪤 Total active",   n_total)
        m2.metric("🚨 High severity",  n_high)
        m3.metric("🟢 Bullish ops",    n_bull)
        m4.metric("🔴 Bearish ops",    n_bear)

        st.caption(
            f"Results for **{last_market}** · {n_total} of "
            f"{last_universe_count} scanned stocks show operator activity. "
            f"Universe: **{last_universe_source}**."
        )

        # ── Filters ──────────────────────────────────────────────────────────
        f1, f2, f3 = st.columns([2, 2, 1])
        with f1:
            bias_filter = st.selectbox(
                "Direction bias",
                ["All", "🟢 Bullish only", "🔴 Bearish only", "⚪ Neutral only"],
                key="op_bias_filter",
            )
        with f2:
            sev_filter = st.selectbox(
                "Severity",
                ["All", "High severity only", "Med+ severity",
                 "Op Score ≥ 4 (accumulation+)", "Op Score ≥ 6 (strong)"],
                key="op_sev_filter",
            )
        with f3:
            search = st.text_input("🔎 Ticker", key="op_search",
                                   placeholder="search…").strip().upper()

        df_view = df_op.copy()
        if bias_filter == "🟢 Bullish only":
            df_view = df_view[df_view["_bias_score"] > 0]
        elif bias_filter == "🔴 Bearish only":
            df_view = df_view[df_view["_bias_score"] < 0]
        elif bias_filter == "⚪ Neutral only":
            df_view = df_view[df_view["_bias_score"] == 0]

        if   sev_filter == "High severity only":
            df_view = df_view[df_view["_high_count"] >= 1]
        elif sev_filter == "Med+ severity":
            df_view = df_view[df_view["_trap_count"] >= 1]
        elif sev_filter == "Op Score ≥ 4 (accumulation+)":
            df_view = df_view[df_view["_op_score"] >= 4]
        elif sev_filter == "Op Score ≥ 6 (strong)":
            df_view = df_view[df_view["_op_score"] >= 6]

        if search:
            df_view = df_view[df_view["Ticker"].str.contains(search, na=False)]

        # ── Tier split: bullish vs bearish operator activity ─────────────────
        df_bull = df_view[df_view["_bias_score"] >  0].sort_values(
            ["_bias_score", "_op_score"], ascending=[False, False])
        df_bear = df_view[df_view["_bias_score"] <  0].sort_values(
            ["_bias_score", "_op_score"], ascending=[True, False])
        df_neut = df_view[df_view["_bias_score"] == 0].sort_values(
            "_op_score", ascending=False)

        display_cols = [c for c in df_view.columns if not c.startswith("_")]

        st.markdown(f"**Filtered: {len(df_view)} stocks**")

        if not df_bull.empty:
            st.markdown(f"### 🟢 Bullish operator activity ({len(df_bull)})")
            st.caption(
                "Accumulation, bear traps, downside stop hunts, sell-climax — operators "
                "appear to be loading up. Consider these as long candidates."
            )
            st.dataframe(df_bull[display_cols], width="stretch", hide_index=True)

        if not df_bear.empty:
            st.markdown(f"### 🔴 Bearish operator activity ({len(df_bear)})")
            st.caption(
                "Distribution, bull traps, upside stop hunts, buy-climax — operators "
                "appear to be unloading. Consider these as short candidates."
            )
            st.dataframe(df_bear[display_cols], width="stretch", hide_index=True)

        if not df_neut.empty:
            st.markdown(f"### ⚪ Neutral / churn ({len(df_neut)})")
            st.caption(
                "Operator footprint without a clear directional bias — usually churn "
                "or stop hunts in both directions. Wait for a directional break."
            )
            st.dataframe(df_neut[display_cols], width="stretch", hide_index=True)

        if df_view.empty:
            st.info("No stocks match the current filters.")

        # ── Column reference ─────────────────────────────────────────────────
        with st.expander("📋 Column reference"):
            st.markdown("""
- **Op Score** — the existing in-engine accumulation score (0–10ish). ≥4 = accumulation, ≥6 = strong operator buying.
- **Op Label** — text tier of the op-score (`🔥 STRONG OPERATOR`, `🟢 ACCUMULATION`, `🟡 WEAK SIGNS`, `⚪ NONE`).
- **Trap Bias** — net direction of detected trap patterns. 🟢 BULLISH = accumulation/bear traps dominate; 🔴 BEARISH = distribution/bull traps dominate.
- **Patterns** — count of active trap patterns, broken down by severity (`H` high · `M` medium · `L` low).
- **Detected** — comma-separated labels of the actual patterns (BULL TRAP, DISTRIBUTION, etc.).
- **Trap Risk** — single-flag fast-fail label from the engine: `FALSE BO` (failed breakout), `GAP CHASE`, `DISTRIB`.
- **VWAP** — close above or below today's VWAP (a quick proxy for institutional control).
- **Vol Ratio** — today's volume vs 20-day average. Anything ≥ 1.5 is meaningful; ≥ 2.5 is climactic.

### How to use
Open the **🔬 Stock Analysis** tab and search any ticker shown here for the full pattern explanations, the chart, and the trade plan. The bias here is a *screening* signal — it tells you where to look, not what to do.
            """)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 4 — SIDE BY SIDE
# ─────────────────────────────────────────────────────────────────────────────
with tab_both:
    if df_long.empty and df_short.empty:
        st.info("Run the scan to see results.")
    else:
        col_l, col_r = st.columns(2)
        with col_l:
            st.caption("📈 Top Longs")
            top_l = df_long[df_long["Action"] == "STRONG BUY"][
                ["Ticker","Sector","Entry Quality","Rise Prob","Score","Price","MA60 Stop","TP1 +10%","TP3 +20%"]
            ] if not df_long.empty else pd.DataFrame()
            show_table(top_l, "long", "Rise Prob")
        with col_r:
            st.caption("📉 Top Shorts")
            top_s = df_short[df_short["Action"] == "STRONG SHORT"][
                ["Ticker","Sector","Fall Prob","Score","Price","Cover Stop","Target 1:2"]
            ] if not df_short.empty else pd.DataFrame()
            show_table(top_s, "short", "Fall Prob")

        if not df_long.empty and not df_short.empty:
            both = set(df_long["Ticker"]) & set(df_short["Ticker"])
            if both:
                st.warning(f"⚠️ Mixed signals — avoid: {', '.join(sorted(both))}")

        # ── Portfolio correlation warning ─────────────────────────────────────
        if not df_long.empty:
            strong_buys = df_long[df_long["Action"] == "STRONG BUY"]["Ticker"].tolist()
            if len(strong_buys) >= 2:
                # Group by sector to detect concentration
                sector_counts: dict = {}
                for _, row in df_long[df_long["Action"] == "STRONG BUY"].iterrows():
                    sec = str(row.get("Sector","")).replace("🟢","").replace("🔴","").replace("⚪","").strip()
                    sector_counts[sec] = sector_counts.get(sec, 0) + 1
                concentrated = {s: n for s, n in sector_counts.items() if n >= 3}
                if concentrated:
                    st.error(
                        f"⚠️ **Concentration risk** — {len(strong_buys)} STRONG BUY setups found but "
                        + ", ".join(f"**{n} are in {s}**" for s, n in concentrated.items())
                        + ". Stocks in the same sector are 0.80+ correlated. "
                        "A single sector sell-off wipes all positions simultaneously. "
                        "Limit exposure to max 2–3 stocks per sector."
                    )

# ─────────────────────────────────────────────────────────────────────────────
# TAB 5 — ETF HOLDINGS
# ─────────────────────────────────────────────────────────────────────────────
with tab_etf:
    st.caption("📊 ETF Holdings")
    st.caption("Fetched · Cached 6 hours · Click a sector to expand")

    # ── SG INVESTOR ETF DASHBOARD ─────────────────────────────────────────────
    st.markdown("#### 🇸🇬 SG Investor ETF Dashboard — Performance & Fee Matrix")
    st.caption("Irish-domiciled UCITS · 15% WHT · No US Estate Tax Risk · ER & Yield fetched live")

    SG_ETF_UNIVERSE = {
        "CSPX.L":  {"Name": "iShares Core S&P 500 (Acc)",       "Focus": "US Large Cap"},
        "VUAA.L":  {"Name": "Vanguard S&P 500 (Acc)",           "Focus": "US Large Cap"},
        "VWRA.L":  {"Name": "Vanguard FTSE All-World",          "Focus": "Global (Dev + EM)"},
        "SWRD.L":  {"Name": "SPDR MSCI World",                  "Focus": "Developed Markets"},
        "ISAC.L":  {"Name": "iShares MSCI ACWI",                "Focus": "Global (Dev + EM)"},
        "ANAU.DE": {"Name": "AXA Nasdaq 100 (Acc)",             "Focus": "US Tech Growth"},
        "XNAS.L":  {"Name": "Xtrackers Nasdaq-100 UCITS (Acc)", "Focus": "US Tech Growth"},
        "2854.T":  {"Name": "Global X Japan Tech Top 20",       "Focus": "Japan Tech Growth"},
        "1475.T":  {"Name": "iShares Core TOPIX",               "Focus": "Japan Broad Market"},
    }

    # Fallback values in case live fetch fails
    _ER_FALLBACK    = {"CSPX.L":0.07,"VUAA.L":0.07,"VWRA.L":0.22,"SWRD.L":0.12,
                       "ISAC.L":0.20,"ANAU.DE":0.14,"XNAS.L":0.20,"2854.T":0.30,"1475.T":0.05}
    _YIELD_FALLBACK = {"CSPX.L":1.10,"VUAA.L":1.15,"VWRA.L":1.50,"SWRD.L":1.41,
                       "ISAC.L":1.45,"ANAU.DE":0.70,"XNAS.L":0.00,"2854.T":0.71,"1475.T":1.70}

    @st.cache_data(ttl=3600)
    def fetch_sg_etf_data():
        rows = []
        # FX rates
        try:    jpy_usd = 1 / yf.Ticker("JPY=X").fast_info["last_price"]
        except: jpy_usd = 0.0064
        try:    gbp_usd = yf.Ticker("GBPUSD=X").fast_info["last_price"]
        except: gbp_usd = 1.27
        try:    eur_usd = yf.Ticker("EURUSD=X").fast_info["last_price"]
        except: eur_usd = 1.08

        for ticker, meta in SG_ETF_UNIVERSE.items():
            # ── Fetch ER and Yield dynamically ───────────────────────────────
            er    = _ER_FALLBACK.get(ticker, np.nan)
            yield_ = _YIELD_FALLBACK.get(ticker, np.nan)
            try:
                tkr_obj = yf.Ticker(ticker)
                info    = tkr_obj.info

                # Expense ratio — multiple possible keys
                for key in ("annualReportExpenseRatio", "totalExpenseRatio",
                            "netExpenseRatio", "expenseRatio"):
                    v = info.get(key)
                    if v and v > 0:
                        # yfinance returns as decimal (0.0007) or percent (0.07)
                        er = round(v * 100 if v < 1 else v, 4)
                        break

                # Also try funds_data
                if er == _ER_FALLBACK.get(ticker, np.nan):
                    try:
                        fd_info = tkr_obj.funds_data.fund_overview
                        if fd_info is not None and not fd_info.empty:
                            for key in ("annualReportExpenseRatio","netExpenseRatio"):
                                if key in fd_info.index:
                                    v = float(fd_info.loc[key])
                                    if v > 0:
                                        er = round(v * 100 if v < 1 else v, 4)
                                        break
                    except Exception:
                        pass

                # Dividend yield — multiple possible keys
                for key in ("trailingAnnualDividendYield", "yield",
                            "dividendYield", "fiveYearAvgDividendYield"):
                    v = info.get(key)
                    if v and v > 0:
                        yield_ = round(v * 100 if v < 1 else v, 2)
                        break

            except Exception:
                pass  # keep fallback values

            # ── Price history and returns ─────────────────────────────────────
            try:
                raw = yf.download(ticker, period="max", interval="1d",
                                  progress=False, auto_adjust=True)
                if isinstance(raw.columns, pd.MultiIndex):
                    raw.columns = raw.columns.get_level_values(0)
                if raw.empty or "Close" not in raw.columns:
                    raise ValueError("no data")

                close  = raw["Close"].ffill().dropna()
                curr_p = float(close.iloc[-1])

                if ".T" in ticker:
                    price_usd = curr_p * jpy_usd
                elif ".L" in ticker:
                    price_usd = (curr_p / 100 * gbp_usd) if curr_p > 100 else (curr_p * gbp_usd)
                elif ".DE" in ticker:
                    price_usd = curr_p * eur_usd
                else:
                    price_usd = curr_p

                def ann_ret(years):
                    days = int(years * 252)
                    if len(close) >= days:
                        return ((curr_p / float(close.iloc[-days])) ** (1/years) - 1) * 100
                    total_yr = len(close) / 252
                    if total_yr >= 0.5:
                        return ((curr_p / float(close.iloc[0])) ** (1/total_yr) - 1) * 100
                    return np.nan

                vol = float(close.pct_change().dropna().std() * np.sqrt(252) * 100)

                rows.append({
                    "Ticker":      ticker,
                    "Fund Name":   meta["Name"],
                    "Focus":       meta["Focus"],
                    "Price (USD)": round(price_usd, 2),
                    "ER %":        er,
                    "1Y Ret %":    round(ann_ret(1), 2),
                    "3Y Ann %":    round(ann_ret(3), 2),
                    "5Y Ann %":    round(ann_ret(5), 2),
                    "Vol %":       round(vol, 2),
                    "Yield %":     yield_,
                    "Live ER":     "✅" if er != _ER_FALLBACK.get(ticker) else "〰️",
                    "Live Yield":  "✅" if yield_ != _YIELD_FALLBACK.get(ticker) else "〰️",
                })

            except Exception:
                rows.append({
                    "Ticker": ticker, "Fund Name": meta["Name"],
                    "Focus": meta["Focus"], "Price (USD)": np.nan,
                    "ER %": er, "1Y Ret %": np.nan, "3Y Ann %": np.nan,
                    "5Y Ann %": np.nan, "Vol %": np.nan, "Yield %": yield_,
                    "Live ER": "〰️", "Live Yield": "〰️",
                })
        return pd.DataFrame(rows)

    with st.spinner("Fetching SG ETF data (ER & Yield live)..."):
        sg_df = fetch_sg_etf_data()

    # Filter
    focus_opts  = sg_df["Focus"].unique().tolist()
    sel_focus   = st.multiselect("Filter by focus", focus_opts,
                                 default=focus_opts, key="sg_etf_focus")
    sg_filtered = sg_df[sg_df["Focus"].isin(sel_focus)]

    # Colour functions
    def colour_ret(val):
        try:
            v = float(val)
            if   v >= 20: return "background-color:#1a7a3a;color:#ffffff;font-weight:700"
            elif v >= 10: return "background-color:#27ae60;color:#ffffff;font-weight:600"
            elif v >=  0: return "background-color:#a9dfbf;color:#145a32;font-weight:500"
            elif v >= -5: return "background-color:#f5b7b1;color:#7b241c;font-weight:500"
            else:         return "background-color:#c0392b;color:#ffffff;font-weight:700"
        except: return ""

    def colour_er(val):
        try:
            v = float(val)
            if   v <= 0.07: return "background-color:#27ae60;color:#ffffff;font-weight:700"
            elif v <= 0.15: return "background-color:#a9dfbf;color:#145a32"
            elif v <= 0.25: return "background-color:#fdebd0;color:#784212"
            else:           return "background-color:#f5b7b1;color:#7b241c"
        except: return ""

    def colour_vol(val):
        try:
            v = float(val)
            if   v <= 12: return "background-color:#a9dfbf;color:#145a32"
            elif v <= 18: return "background-color:#fdebd0;color:#784212"
            else:         return "background-color:#f5b7b1;color:#7b241c"
        except: return ""

    styler   = sg_filtered.set_index("Ticker").sort_values("ER %").style
    style_fn = styler.map if hasattr(styler, "map") else styler.applymap
    styled   = style_fn(colour_ret, subset=["1Y Ret %","3Y Ann %","5Y Ann %"])
    styled   = (styled.map if hasattr(styled,"map") else styled.applymap)(colour_er,  subset=["ER %"])
    styled   = (styled.map if hasattr(styled,"map") else styled.applymap)(colour_vol, subset=["Vol %"])
    st.dataframe(styled, width="stretch")

    st.caption("✅ = fetched live ·  〰️ = using fallback value")
    st.markdown("---")
    # ── END SG ETF DASHBOARD ──────────────────────────────────────────────────

    live_holdings = st.session_state.get("live_sectors_cache", None)

    if live_holdings is None:
        st.info("Run the scan first — holdings are fetched as part of the scan.")
    else:
        # Summary metrics
        total_stocks = sum(len(v.get("stocks", [])) for v in live_holdings.values())
        c1, c2, c3 = st.columns(3)
        c1.metric("Sectors tracked", len(live_holdings))
        c2.metric("Total unique stocks", total_stocks)
        c3.metric("Source", "")

        st.markdown("---")

        # One expander per sector, with a colour-coded header
        sector_perf = get_sector_performance()
        perf_map = {}
        if not sector_perf.empty and "Today %" in sector_perf.columns:
            perf_map = dict(zip(sector_perf["Sector"], sector_perf["Today %"]))

        for sector_name, sec_data in live_holdings.items():
            stocks  = sec_data.get("stocks", [])
            etf     = sec_data.get("etf", "")
            source  = sec_data.get("source", "–")
            pct     = perf_map.get(sector_name, None)

            if pct is not None:
                arrow  = "▲" if pct > 0 else "▼" if pct < 0 else "—"
                colour = "🟢" if pct > 0.1 else "🔴" if pct < -0.1 else "⚪"
                header = f"{colour} **{sector_name}** ({etf})  {arrow} {pct:+.2f}% today · {len(stocks)} stocks · via {source}"
            else:
                header = f"⚪ **{sector_name}** ({etf}) · {len(stocks)} stocks · via {source}"

            with st.expander(header, expanded=False):
                if not stocks:
                    st.warning("No holdings fetched for this sector.")
                    continue

                # Show as a clean dataframe with rank
                rows = [{"Rank": i+1, "Ticker": t} for i, t in enumerate(stocks)]
                df_stocks = pd.DataFrame(rows)

                # Split into 3 columns for compact display
                n = len(stocks)
                col_size = max(1, (n + 2) // 3)
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.dataframe(
                        df_stocks.iloc[:col_size],
                        width="stretch", hide_index=True
                    )
                with c2:
                    st.dataframe(
                        df_stocks.iloc[col_size:col_size*2],
                        width="stretch", hide_index=True
                    )
                with c3:
                    st.dataframe(
                        df_stocks.iloc[col_size*2:],
                        width="stretch", hide_index=True
                    )

    # Refresh button
    if st.button("🔄 Refresh ETF Holdings"):
        st.cache_data.clear()
        st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# TAB 6 — INDIVIDUAL STOCK ANALYSIS
# Full chart + all indicators + signal scorecard + risk levels
# ─────────────────────────────────────────────────────────────────────────────
with tab_stock:
    st.caption("🔬 Stock Analysis")
    st.caption("Enter any ticker to get a full signal breakdown, chart, and trade plan")

    col_inp, col_per = st.columns([2, 1])
    with col_inp:
        stock_ticker = st.text_input(
            "Ticker symbol", placeholder="e.g. NVDA, D05.SI, TSLA",
            key="stock_analysis_ticker"
        ).strip().upper()
    with col_per:
        analysis_period = st.selectbox(
            "Chart period", ["3mo", "6mo", "1y", "2y"], index=1,
            key="stock_analysis_period"
        )

    if not stock_ticker:
        st.info("Enter a ticker above to analyse any stock — US, SGX (.SI), or any yfinance-supported symbol.")
    else:
        with st.spinner(f"Fetching {stock_ticker}..."):
            try:
                # ── Fetch data ────────────────────────────────────────────────
                raw_sa = yf.download(stock_ticker, period=analysis_period,
                                     interval="1d", progress=False, auto_adjust=True)
                if isinstance(raw_sa.columns, pd.MultiIndex):
                    raw_sa.columns = raw_sa.columns.get_level_values(0)

                if raw_sa.empty or len(raw_sa) < 30:
                    st.error(f"Not enough data for {stock_ticker}. Check the ticker symbol.")
                else:
                    close_sa = raw_sa["Close"].squeeze().ffill()
                    high_sa  = raw_sa["High"].squeeze().ffill()
                    low_sa   = raw_sa["Low"].squeeze().ffill()
                    vol_sa   = raw_sa["Volume"].squeeze().ffill()

                    # ── Compute all signals ───────────────────────────────────
                    long_sig_sa, short_sig_sa, rv_sa = compute_all_signals(
                        close_sa, high_sa, low_sa, vol_sa
                    )
                    l_score_sa = sum(long_sig_sa.values())
                    s_score_sa = sum(short_sig_sa.values())
                    l_prob_sa  = bayesian_prob(LONG_WEIGHTS,  long_sig_sa)
                    s_prob_sa  = bayesian_prob(SHORT_WEIGHTS, short_sig_sa)

                    # ── Fetch company info ────────────────────────────────────
                    try:
                        info_sa   = yf.Ticker(stock_ticker).info
                        comp_name = info_sa.get("longName") or info_sa.get("shortName") or stock_ticker
                        sector_sa = info_sa.get("sector", "–")
                        mktcap    = info_sa.get("marketCap", 0)
                        mktcap_str = f"${mktcap/1e9:.1f}B" if mktcap > 1e9 else (f"${mktcap/1e6:.0f}M" if mktcap else "–")
                        pe_ratio  = info_sa.get("trailingPE", None)
                        week52hi  = info_sa.get("fiftyTwoWeekHigh", None)
                        week52lo  = info_sa.get("fiftyTwoWeekLow",  None)
                    except Exception:
                        comp_name = stock_ticker
                        sector_sa = mktcap_str = "–"
                        pe_ratio = week52hi = week52lo = None

                    # ── Header ────────────────────────────────────────────────
                    st.markdown(f"## {comp_name} ({stock_ticker})")
                    c1,c2,c3 = st.columns(3)
                    c4,c5,c6 = st.columns(3)
                    c1.metric("Price",    f"${rv_sa['p']:.2f}")
                    c2.metric("Today %",  f"{float((close_sa.iloc[-1]-close_sa.iloc[-2])/close_sa.iloc[-2]*100):+.2f}%")
                    c3.metric("Sector",   sector_sa)
                    c4.metric("Mkt Cap",  mktcap_str)
                    c5.metric("52W High", f"${week52hi:.2f}" if week52hi else "–")
                    c6.metric("52W Low",  f"${week52lo:.2f}" if week52lo else "–")

                    st.markdown("---")

                    # ── Operator + Trap detection (consumed by scorecards) ───
                    # Uses the shared detect_traps() helper — same logic that
                    # powers the universe-wide Operator Activity tab.
                    try:
                        open_sa = raw_sa["Open"].squeeze().ffill()
                        traps = detect_traps(
                            open_sa, high_sa, low_sa, close_sa, vol_sa,
                            rv_sa["atr"], rv_sa["last_swing_high"], rv_sa["last_swing_low"]
                        )
                    except Exception as trap_err:
                        traps = []
                        st.caption(f"_trap detector skipped: {trap_err}_")

                    # Helper: classify recommendation based on traps + base tier
                    def _trap_adjust(base_rec, base_col, my_dir_idx):
                        """my_dir_idx: 3 for long_dir field, 4 for short_dir."""
                        contra = [t for t in traps if t[my_dir_idx] == -1]
                        supp   = [t for t in traps if t[my_dir_idx] == +1]
                        high_c = sum(1 for t in contra if t[0] == "high")
                        med_c  = sum(1 for t in contra if t[0] == "med")
                        high_s = sum(1 for t in supp   if t[0] == "high")

                        if high_c >= 1 and "STRONG" in base_rec:
                            return "⚠️ TRAP DOWNGRADE — capped at WATCH", "warning", contra, supp
                        if high_c >= 1:
                            return f"⚠️ {base_rec} · trap warning", "warning", contra, supp
                        if med_c >= 2 and "STRONG" in base_rec:
                            return f"⚠️ {base_rec} · multiple trap warnings", "warning", contra, supp
                        if high_s >= 1 and "STRONG" in base_rec:
                            return "💎 STRONG + trap confluence", "success", contra, supp
                        if high_s >= 1 and ("WATCH" in base_rec or "DEVELOPING" in base_rec):
                            return f"⭐ {base_rec} · trap support", base_col, contra, supp
                        return base_rec, base_col, contra, supp

                    # ── Signal scorecard (trap-aware) ────────────────────────
                    col_long_sc, col_short_sc = st.columns(2)

                    with col_long_sc:
                        st.markdown("#### 📈 Long Signal Scorecard")
                        l_tier_col = "🟢" if l_prob_sa >= 0.72 else "🟡" if l_prob_sa >= 0.62 else "🔴"
                        st.markdown(f"**Score: {l_score_sa}/10 · Rise Prob: {l_tier_col} {l_prob_sa*100:.1f}% ({prob_label(l_prob_sa)})**")

                        signal_display = [
                            ("Trend (price>EMA8>EMA21)",  long_sig_sa["trend_daily"]),
                            ("Stoch confirmed bounce",    long_sig_sa["stoch_confirmed"]),
                            ("BB bull squeeze",           long_sig_sa["bb_bull_squeeze"]),
                            ("MACD acceleration",         long_sig_sa["macd_accel"]),
                            ("MACD crossover",            long_sig_sa["macd_cross"]),
                            ("RSI >50 confirmed",         long_sig_sa["rsi_confirmed"]),
                            ("ADX >20",                   long_sig_sa["adx"]),
                            ("Volume >1.5×",              long_sig_sa["volume"]),
                            ("Volume breakout",           long_sig_sa["vol_breakout"]),
                            ("Higher lows",               long_sig_sa["higher_lows"]),
                        ]
                        for sig_name, sig_val in signal_display:
                            icon = "✅" if sig_val else "❌"
                            st.markdown(f"{icon} {sig_name}")

                        # Long action — base tier
                        l_bonus_sa = (0.06 if rv_sa["bb_very_tight"] else 0) + (0.05 if rv_sa["vr"] >= 2.5 else 0)
                        l_top3_sa  = long_sig_sa["stoch_confirmed"] or long_sig_sa["bb_bull_squeeze"] or long_sig_sa["macd_accel"]
                        regime_cur = get_market_regime()["regime"]
                        min_score_l = 6 if regime_cur == "BULL" else 7
                        min_prob_l  = 0.72 if regime_cur == "BULL" else 0.78
                        if l_score_sa >= min_score_l and l_prob_sa >= min_prob_l and l_top3_sa:
                            l_rec_base = "🔥 STRONG BUY"
                            l_col_base = "success"
                        elif l_score_sa >= 4 and l_prob_sa >= 0.62 and long_sig_sa["trend_daily"]:
                            l_rec_base = "👀 WATCH – HIGH QUALITY"
                            l_col_base = "info"
                        elif l_score_sa >= 3 and long_sig_sa["trend_daily"]:
                            l_rec_base = "📋 WATCH – DEVELOPING"
                            l_col_base = "info"
                        else:
                            l_rec_base = "⏸️ NO LONG SETUP"
                            l_col_base = "warning"

                        # Apply trap adjustment (long_dir = field index 3)
                        l_rec, l_col, l_contra, l_supp = _trap_adjust(l_rec_base, l_col_base, 3)
                        getattr(st, l_col)(f"**Long: {l_rec}**")
                        if l_rec != l_rec_base:
                            st.caption(f"_base tier was: {l_rec_base}_")

                        # Trap evidence affecting LONG side — always shown
                        n_supp_l, n_contra_l = len(l_supp), len(l_contra)
                        if n_supp_l == 0 and n_contra_l == 0:
                            st.caption("🪤 **Operator patterns:** ✅ none detected")
                        else:
                            parts = []
                            if n_supp_l:
                                parts.append(f"⭐ {n_supp_l} supporting")
                            if n_contra_l:
                                parts.append(f"⚠️ {n_contra_l} contradicting")
                            st.markdown(f"🪤 **Operator patterns:** {' · '.join(parts)}")
                            for sev, label, detail, _, _ in l_supp:
                                with st.expander(f"⭐ {label}  _(supports long)_", expanded=(sev == "high")):
                                    st.markdown(detail)
                            for sev, label, detail, _, _ in l_contra:
                                with st.expander(f"⚠️ {label}  _(contradicts long)_", expanded=(sev == "high")):
                                    st.markdown(detail)

                    with col_short_sc:
                        st.markdown("#### 📉 Short Signal Scorecard")
                        s_tier_col = "🔴" if s_prob_sa >= 0.72 else "🟡" if s_prob_sa >= 0.62 else "⚪"
                        st.markdown(f"**Score: {s_score_sa}/10 · Fall Prob: {s_tier_col} {s_prob_sa*100:.1f}% ({prob_label(s_prob_sa)})**")

                        short_display = [
                            ("Trend (price<EMA8<EMA21)",  short_sig_sa["trend_bearish"]),
                            ("Stoch rollover",            short_sig_sa["stoch_overbought"]),
                            ("BB bear squeeze",           short_sig_sa["bb_bear_squeeze"]),
                            ("MACD deceleration",         short_sig_sa["macd_decel"]),
                            ("MACD bearish cross",        short_sig_sa["macd_cross_bear"]),
                            ("RSI <50 confirmed",         short_sig_sa["rsi_cross_bear"]),
                            ("ADX >20 downtrend",         short_sig_sa["adx_bear"]),
                            ("Distribution day",          short_sig_sa["high_volume_down"]),
                            ("Volume breakdown",          short_sig_sa["vol_breakdown"]),
                            ("Lower highs",               short_sig_sa["lower_highs"]),
                        ]
                        for sig_name, sig_val in short_display:
                            icon = "✅" if sig_val else "❌"
                            st.markdown(f"{icon} {sig_name}")

                        min_score_s = 5 if regime_cur in ("BEAR","CAUTION") else 6
                        min_prob_s  = 0.68 if regime_cur in ("BEAR","CAUTION") else 0.72
                        s_top3_sa   = short_sig_sa["stoch_overbought"] or short_sig_sa["bb_bear_squeeze"] or short_sig_sa["macd_decel"]
                        if s_score_sa >= min_score_s and s_prob_sa >= min_prob_s and s_top3_sa:
                            s_rec_base = "🔥 STRONG SHORT"
                            s_col_base = "error"
                        elif s_score_sa >= 4 and s_prob_sa >= 0.60 and short_sig_sa["trend_bearish"]:
                            s_rec_base = "👀 WATCH SHORT – HQ"
                            s_col_base = "warning"
                        elif s_score_sa >= 3 and short_sig_sa["trend_bearish"]:
                            s_rec_base = "📋 WATCH SHORT – DEV"
                            s_col_base = "warning"
                        else:
                            s_rec_base = "⏸️ NO SHORT SETUP"
                            s_col_base = "info"

                        # Apply trap adjustment (short_dir = field index 4)
                        s_rec, s_col, s_contra, s_supp = _trap_adjust(s_rec_base, s_col_base, 4)
                        getattr(st, s_col)(f"**Short: {s_rec}**")
                        if s_rec != s_rec_base:
                            st.caption(f"_base tier was: {s_rec_base}_")

                        # Trap evidence affecting SHORT side — always shown
                        n_supp_s, n_contra_s = len(s_supp), len(s_contra)
                        if n_supp_s == 0 and n_contra_s == 0:
                            st.caption("🪤 **Operator patterns:** ✅ none detected")
                        else:
                            parts = []
                            if n_supp_s:
                                parts.append(f"⭐ {n_supp_s} supporting")
                            if n_contra_s:
                                parts.append(f"⚠️ {n_contra_s} contradicting")
                            st.markdown(f"🪤 **Operator patterns:** {' · '.join(parts)}")
                            for sev, label, detail, _, _ in s_supp:
                                with st.expander(f"⭐ {label}  _(supports short)_", expanded=(sev == "high")):
                                    st.markdown(detail)
                            for sev, label, detail, _, _ in s_contra:
                                with st.expander(f"⚠️ {label}  _(contradicts short)_", expanded=(sev == "high")):
                                    st.markdown(detail)

                    st.markdown("---")

                    # ── Live indicator values ─────────────────────────────────
                    st.markdown("#### 📊 Live Indicator Values")
                    ci1,ci2,ci3,ci4 = st.columns(4)
                    ci5,ci6,ci7,ci8 = st.columns(4)
                    ci1.metric("RSI",       round(rv_sa["rsi0"],1))
                    ci2.metric("Stoch K",   round(rv_sa["k0"],1))
                    ci3.metric("ADX",       round(rv_sa["adx"],1))
                    ci4.metric("Vol Ratio", f"{rv_sa['vr']:.2f}×")
                    ci5.metric("EMA8",      f"${rv_sa['e8']:.2f}")
                    ci6.metric("EMA21",     f"${rv_sa['e21']:.2f}")
                    ci7.metric("MACD Hist", f"{rv_sa['mh0']:.4f}")
                    ci8.metric("BB Squeeze","YES" if rv_sa["bb_squeeze"] else "NO")

                    st.markdown("---")

                    # ── Trade plan ────────────────────────────────────────────
                    st.markdown("#### 💼 Trade Plan")
                    p_sa   = rv_sa["p"]
                    atr_sa = rv_sa["atr"]

                    tp1, tp2, tp3 = st.columns(3)

                    with tp1:
                        st.markdown("**📈 Long trade plan**")
                        l_atr_s  = round(p_sa - 1.5 * atr_sa, 2)
                        l_sw_s   = round(rv_sa["last_swing_low"] * 0.995, 2)
                        l_stop   = max(l_atr_s, l_sw_s)
                        l_risk   = p_sa - l_stop
                        st.markdown(f"Entry:        **${p_sa:.2f}**")
                        st.markdown(f"ATR stop:     ${l_atr_s:.2f}")
                        st.markdown(f"Swing stop:   ${l_sw_s:.2f}")
                        st.markdown(f"**Best stop:  ${l_stop:.2f}**")
                        st.markdown(f"Target 1:1:   ${round(p_sa+l_risk,2):.2f}")
                        st.markdown(f"**Target 1:2: ${round(p_sa+l_risk*2,2):.2f}**")
                        if l_risk > 0:
                            st.markdown(f"Pos/$1k risk: {int(1000/l_risk)} shares")

                    with tp2:
                        st.markdown("**📉 Short trade plan**")
                        s_atr_s  = round(p_sa + 1.5 * atr_sa, 2)
                        s_sw_s   = round(rv_sa["last_swing_high"] * 1.005, 2)
                        s_cover  = min(s_atr_s, s_sw_s)
                        s_risk   = s_cover - p_sa
                        st.markdown(f"Entry:        **${p_sa:.2f}**")
                        st.markdown(f"ATR cover:    ${s_atr_s:.2f}")
                        st.markdown(f"Swing cover:  ${s_sw_s:.2f}")
                        st.markdown(f"**Best cover: ${s_cover:.2f}**")
                        st.markdown(f"Target 1:1:   ${round(p_sa-s_risk,2):.2f}")
                        st.markdown(f"**Target 1:2: ${round(p_sa-s_risk*2,2):.2f}**")
                        if s_risk > 0:
                            st.markdown(f"Pos/$1k risk: {int(1000/s_risk)} shares")

                    with tp3:
                        st.markdown("**📐 Key levels**")
                        st.markdown(f"14d ATR:      **${atr_sa:.2f}** ({atr_sa/p_sa*100:.1f}%)")
                        st.markdown(f"Last swing ↓: ${rv_sa['last_swing_low']:.2f}  ({rv_sa['swing_lows_count']} detected)")
                        st.markdown(f"Last swing ↑: ${rv_sa['last_swing_high']:.2f}  ({rv_sa['swing_highs_count']} detected)")
                        st.markdown(f"10d high:     ${rv_sa['h10']:.2f}")
                        st.markdown(f"10d low:      ${rv_sa['l10']:.2f}")
                        st.markdown(f"BB midline:   ${rv_sa['bbm']:.2f}")
                        st.markdown(f"BB squeeze:   {'🟡 YES — coiling' if rv_sa['bb_squeeze'] else 'NO'}")

                    st.markdown("---")

                    # ── Price + indicator chart ───────────────────────────────
                    st.markdown("#### 📈 Price Chart with Indicators")
                    try:
                        import plotly.graph_objects as go
                        from plotly.subplots import make_subplots

                        # Build indicators for chart
                        ema8_chart  = ta.trend.ema_indicator(close_sa, window=8)
                        ema21_chart = ta.trend.ema_indicator(close_sa, window=21)
                        rsi_chart   = ta.momentum.rsi(close_sa, window=14)
                        macd_chart  = ta.trend.MACD(close_sa)
                        vol_avg_chart = vol_sa.rolling(20).mean()

                        dates = raw_sa.index

                        fig = make_subplots(
                            rows=4, cols=1,
                            shared_xaxes=True,
                            row_heights=[0.50, 0.18, 0.18, 0.14],
                            vertical_spacing=0.03,
                            subplot_titles=["Price + EMA8/21", "Volume", "RSI", "MACD Histogram"]
                        )

                        # Candlestick
                        fig.add_trace(go.Candlestick(
                            x=dates, open=raw_sa["Open"], high=high_sa,
                            low=low_sa, close=close_sa,
                            name="Price",
                            increasing_line_color="#27ae60",
                            decreasing_line_color="#e74c3c"
                        ), row=1, col=1)

                        fig.add_trace(go.Scatter(x=dates, y=ema8_chart,
                            line=dict(color="#f39c12", width=1.5),
                            name="EMA8"), row=1, col=1)
                        fig.add_trace(go.Scatter(x=dates, y=ema21_chart,
                            line=dict(color="#3498db", width=1.5),
                            name="EMA21"), row=1, col=1)

                        # Stop / target lines
                        fig.add_hline(y=rv_sa["last_swing_low"],
                            line_dash="dot", line_color="#e74c3c",
                            annotation_text="Swing Low (stop ref)", row=1, col=1)
                        fig.add_hline(y=rv_sa["last_swing_high"],
                            line_dash="dot", line_color="#27ae60",
                            annotation_text="Swing High", row=1, col=1)

                        # Volume bars
                        vol_colors = ["#27ae60" if c >= o else "#e74c3c"
                                      for c, o in zip(close_sa, raw_sa["Open"])]
                        fig.add_trace(go.Bar(x=dates, y=vol_sa,
                            marker_color=vol_colors, name="Volume",
                            showlegend=False), row=2, col=1)
                        fig.add_trace(go.Scatter(x=dates, y=vol_avg_chart,
                            line=dict(color="#f39c12", width=1),
                            name="Vol MA20"), row=2, col=1)

                        # RSI
                        fig.add_trace(go.Scatter(x=dates, y=rsi_chart,
                            line=dict(color="#9b59b6", width=1.5),
                            name="RSI"), row=3, col=1)
                        fig.add_hline(y=70, line_dash="dash",
                            line_color="#e74c3c", line_width=1, row=3, col=1)
                        fig.add_hline(y=50, line_dash="dash",
                            line_color="#95a5a6", line_width=1, row=3, col=1)
                        fig.add_hline(y=30, line_dash="dash",
                            line_color="#27ae60", line_width=1, row=3, col=1)

                        # MACD histogram
                        macd_h = macd_chart.macd_diff()
                        macd_colors = ["#27ae60" if v >= 0 else "#e74c3c" for v in macd_h]
                        fig.add_trace(go.Bar(x=dates, y=macd_h,
                            marker_color=macd_colors, name="MACD Hist",
                            showlegend=False), row=4, col=1)

                        fig.update_layout(
                            height=700,
                            plot_bgcolor="rgba(0,0,0,0)",
                            paper_bgcolor="rgba(0,0,0,0)",
                            xaxis_rangeslider_visible=False,
                            legend=dict(orientation="h", y=1.02),
                            margin=dict(l=0, r=0, t=30, b=0),
                            font=dict(size=11),
                        )
                        fig.update_yaxes(gridcolor="rgba(128,128,128,0.15)")
                        fig.update_xaxes(gridcolor="rgba(128,128,128,0.05)")

                        st.plotly_chart(fig, width="stretch")

                    except ImportError:
                        st.warning("Install plotly for charts: `pip install plotly`")
                    except Exception as chart_err:
                        st.warning(f"Chart error: {chart_err}")

            except Exception as outer_err:
                st.error(f"Error analysing {stock_ticker}: {outer_err}")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 7 — DIAGNOSTICS
# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# TAB — EARNINGS CALENDAR
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def fetch_earnings_calendar(tickers: tuple, days_ahead: int = 15) -> pd.DataFrame:
    import time
    today  = datetime.today().date()
    cutoff = today + pd.Timedelta(days=days_ahead)
    rows   = []

    prog     = st.progress(0, text="Scanning earnings dates…")
    status   = st.empty()
    total    = len(tickers)
    found    = 0
    skipped  = 0   # rate-limited / empty responses

    def _get_info_with_retry(ticker, retries=2, delay=1.5):
        """Fetch tkr.info with retry on empty response (rate limit)."""
        for attempt in range(retries + 1):
            try:
                info = yf.Ticker(ticker).info or {}
                # If info is suspiciously empty (rate limited), retry
                if not info.get("regularMarketPrice") and not info.get("currentPrice") \
                   and not info.get("earningsTimestamp") and attempt < retries:
                    time.sleep(delay)
                    continue
                return info
            except Exception:
                if attempt < retries:
                    time.sleep(delay)
        return {}

    candidates = []

    for i, ticker in enumerate(tickers):
        status.caption(f"Checking {ticker} ({i+1}/{total}) · {found} with earnings found · {skipped} skipped")
        try:
            info = _get_info_with_retry(ticker)

            if not info:
                skipped += 1
                prog.progress((i + 1) / total)
                continue

            earn_date = None
            for key in ("earningsTimestamp", "earningsTimestampStart",
                        "earningsTimestampEnd", "earningsDate"):
                val = info.get(key)
                if val:
                    try:
                        d = pd.Timestamp(val, unit="s").date() \
                            if isinstance(val, (int, float)) and val > 0 \
                            else pd.Timestamp(val).date()
                        if d >= today:
                            earn_date = d
                            break
                    except Exception:
                        continue

            if earn_date and earn_date <= cutoff:
                candidates.append((ticker, earn_date, info))
                found += 1

            # Small delay every 10 tickers to avoid rate limiting
            if (i + 1) % 10 == 0:
                time.sleep(0.3)

        except Exception:
            skipped += 1
        prog.progress((i + 1) / total)

    prog.empty()
    status.empty()

    if not candidates:
        return pd.DataFrame()

    for ticker, earn_date, info in candidates:
        try:
            days_out    = (earn_date - today).days
            eps_est     = info.get("forwardEps") or info.get("epsForward")
            eps_last    = info.get("trailingEps")
            price       = info.get("currentPrice") or info.get("regularMarketPrice") or 0
            ma50        = info.get("fiftyDayAverage") or 0
            ma200       = info.get("twoHundredDayAverage") or 0
            w52lo       = info.get("fiftyTwoWeekLow") or 0
            fwd_pe      = info.get("forwardPE")
            tgt         = info.get("targetMeanPrice")
            rec         = info.get("recommendationKey", "").upper().replace("_", " ")

            if eps_est and eps_last and eps_last != 0:
                eps_chg   = (eps_est - eps_last) / abs(eps_last) * 100
                eps_trend = f"📈 +{eps_chg:.1f}%" if eps_chg > 0 else f"📉 {eps_chg:.1f}%"
            else:
                eps_chg, eps_trend = 0, "–"

            above_ma50  = bool(price > ma50)  if ma50  and price else None
            above_ma200 = bool(price > ma200) if ma200 and price else None
            analyst_up  = bool(tgt > price)   if tgt   and price else None
            near_52lo   = bool(price < w52lo * 1.15) if w52lo and price else False

            score = sum(filter(None, [
                above_ma50, above_ma200, analyst_up,
                eps_chg > 5,
                rec in ("BUY", "STRONG BUY"),
            ]))

            if score >= 4:   verdict, vcol = "✅ BUY",   "buy"
            elif score == 3: verdict, vcol = "👀 WATCH", "watch"
            elif score <= 1 or near_52lo: verdict, vcol = "🚫 AVOID", "avoid"
            else:            verdict, vcol = "⏳ WAIT",  "wait"

            rows.append({
                "Ticker":         ticker,
                "Earnings Date":  str(earn_date),
                "Days Out":       days_out,
                "Price":          f"${price:.2f}" if price else "–",
                "EPS Est":        f"${eps_est:.2f}" if eps_est else "–",
                "EPS Last":       f"${eps_last:.2f}" if eps_last else "–",
                "EPS Trend":      eps_trend,
                "Fwd PE":         f"{fwd_pe:.1f}x" if fwd_pe else "–",
                "Analyst Target": f"${tgt:.2f}" if tgt else "–",
                "Upside":         f"+{(tgt/price-1)*100:.1f}%" if tgt and price else "–",
                "Above MA50":     "✅" if above_ma50 else ("❌" if above_ma50 is False else "–"),
                "Above MA200":    "✅" if above_ma200 else ("❌" if above_ma200 is False else "–"),
                "Analyst Rec":    rec or "–",
                "Verdict":        verdict,
                "_vcol":          vcol,
                "_days":          days_out,
            })
        except Exception:
            pass

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
def _prob_to_float(val):
    try:
        return float(str(val).replace("%", "").strip())
    except Exception:
        return 0.0


def _event_verdict_rank(verdict):
    v = str(verdict or "").upper()
    if "BUY" in v: return 3
    if "WATCH" in v: return 2
    if "WAIT" in v: return 1
    return 0


def _parse_score_num(v, default=0.0):
    try:
        s = str(v).replace("%", "").replace("–", "0").strip()
        return float(s) if s else default
    except Exception:
        return default


def _sector_tailwind_score(sector_value):
    """Small ranking boost for sectors already showing green momentum.
    Works with sector text or numeric strings and safely returns 0 when unknown."""
    s = str(sector_value or "").upper()
    score = 0.0
    if any(k in s for k in ["SEMICON", "TECH", "AI", "CLOUD", "SOFTWARE"]):
        score += 2.0
    if any(k in s for k in ["GREEN", "LEADER", "STRONG"]):
        score += 1.0
    return score


def _news_score_from_event_row(row):
    """Convert Event Predictor text fields into a simple catalyst score."""
    score = 0.0
    news = str(row.get("News", "")).upper()
    orders = str(row.get("Orders", "")).upper()
    verdict = str(row.get("Verdict", "")).upper()
    evidence = str(row.get("Evidence", "")).upper()
    top_news = str(row.get("Top News", "")).upper()
    joined = " ".join([news, orders, verdict, evidence, top_news])

    if "POSITIVE" in news or "BUY" in verdict:
        score += 2.0
    if "WATCH" in verdict:
        score += 1.0
    if any(k in joined for k in ["ORDER", "CONTRACT", "GUIDANCE", "RAISE", "BEAT", "AWARD", "PARTNERSHIP", "UPGRADE"]):
        score += 2.0
    if any(k in joined for k in ["MISS", "CUT", "DOWNGRADE", "PROBE", "LAWSUIT", "DELAY", "WARNING"]):
        score -= 2.0
    return max(-4.0, min(6.0, score))


def _earnings_risk_penalty(days_out, earnings_text=""):
    """Penalty for upcoming earnings. Near earnings is event risk, not a clean swing."""
    try:
        if pd.notna(days_out):
            d = int(days_out)
            if 0 <= d <= 3:
                return 14.0
            if 4 <= d <= 7:
                return 10.0
            if 8 <= d <= 14:
                return 4.0
    except Exception:
        pass
    s = str(earnings_text or "")
    if "≤7" in s or "EARNINGS" in s.upper() and "SOON" in s.upper():
        return 10.0
    return 0.0


def _trap_risk_penalty(trap_risk):
    t = str(trap_risk or "–").upper().strip()
    if t == "FALSE BO":
        return 10.0
    if t == "GAP CHASE":
        return 8.0
    if t == "DISTRIB":
        return 9.0
    return 0.0


def _calc_final_swing_score(row):
    """Bayesian ensemble ranking score.

    This intentionally replaces the removed simple ML ranking. Bayesian remains
    the base model; other factors are additive/penalty layers that match real
    swing-trading workflow. Higher is better.
    """
    bayes_score = _parse_score_num(row.get("Rise Prob", 0), 0.0)
    op_score = _parse_score_num(row.get("Op Score", 0), 0.0)
    event_score = _parse_score_num(row.get("Event Score", 0), 0.0)
    news_score = _news_score_from_event_row(row)
    sector_score = _sector_tailwind_score(row.get("Sector", ""))
    earnings_pen = _earnings_risk_penalty(row.get("Days Out", None), row.get("Earnings", ""))
    trap_pen = _trap_risk_penalty(row.get("Trap Risk", "–"))

    # Main rank formula. Keep Bayesian dominant but not absolute.
    final = (
        bayes_score * 0.55
        + op_score * 4.0
        + news_score * 5.0
        + event_score * 0.8
        + sector_score * 3.0
        - earnings_pen
        - trap_pen
    )

    return {
        "Bayes Score": round(bayes_score, 2),
        "Operator Score": round(op_score, 2),
        "News Score": round(news_score, 2),
        "Sector Score": round(sector_score, 2),
        "Earnings Risk": round(earnings_pen, 2),
        "Trap Risk Score": round(trap_pen, 2),
        "Final Swing Score": round(final, 2),
    }


def _make_swing_picks_from_scan(df_long_in: pd.DataFrame, max_candidates: int = 25, event_days: int = 30) -> pd.DataFrame:
    """Merge latest long-signal output with Event Predictor scoring and
    v13.10 Bayesian ensemble ranking.

    Uses Bayesian probability as the base, then adds operator/smart-money,
    news/orders, sector tailwind and earnings/trap penalties. No simple ML is
    used in live ranking.
    """
    if df_long_in is None or df_long_in.empty or "Ticker" not in df_long_in.columns:
        return pd.DataFrame()

    tech = df_long_in.copy()
    tech["_rise"] = tech.get("Rise Prob", "0%").apply(_prob_to_float)

    # Prefer true BUY / high-quality WATCH setups; keep enough candidates for
    # earnings/news enrichment even when the market is quiet.
    action = tech.get("Action", pd.Series([""] * len(tech))).astype(str).str.upper()
    entry = tech.get("Entry Quality", pd.Series([""] * len(tech))).astype(str).str.upper()
    trap = tech.get("Trap Risk", pd.Series(["–"] * len(tech))).astype(str)
    tech_pref = tech[
        (tech["_rise"] >= 62) &
        (~trap.isin(["FALSE BO", "GAP CHASE", "DISTRIB"])) &
        (
            action.str.contains("BUY|HIGH QUALITY|DEVELOPING", na=False) |
            entry.str.contains("BUY|WATCH", na=False)
        )
    ].copy()
    if tech_pref.empty:
        tech_pref = tech.sort_values("_rise", ascending=False).head(max_candidates).copy()
    else:
        tech_pref = tech_pref.sort_values("_rise", ascending=False).head(max_candidates).copy()

    tickers = _unique_keep_order(tech_pref["Ticker"].astype(str).str.upper().tolist())
    if not tickers:
        return pd.DataFrame()

    event_df = fetch_event_predictions(tuple(tickers), days_ahead=event_days)
    if event_df.empty:
        # Still return technical shortlist when Yahoo earnings/news fetch fails.
        out = tech_pref[[c for c in [
            "Ticker", "Entry Quality", "Rise Prob", "Score", "Operator", "Op Score",
            "VWAP", "Trap Risk", "Today %", "Price", "Sector", "Action",
            "MA60 Stop", "TP1 +10%", "TP2 +15%", "TP3 +20%"
        ] if c in tech_pref.columns]].copy()
        out["Earnings"] = "–"
        out["News"] = "–"
        out["Event Score"] = 0
        out["Event Verdict"] = "–"
        # Build ensemble score even when event/news fetch fails.
        rank_rows = []
        for _, rr in out.iterrows():
            rank_rows.append(_calc_final_swing_score(rr))
        if rank_rows:
            out = pd.concat([out.reset_index(drop=True), pd.DataFrame(rank_rows)], axis=1)
        out["Swing Verdict"] = "👀 WATCH — tech only"
        out["Why"] = "Event/news fetch unavailable; ranking uses technical + operator factors only."
        return out.sort_values("Final Swing Score", ascending=False) if "Final Swing Score" in out.columns else out

    event_cols = [c for c in [
        "Ticker", "Earnings", "Days Out", "EPS Trend", "News", "Orders",
        "Trend Score", "Event Score", "Verdict", "Evidence", "Top News"
    ] if c in event_df.columns]
    merged = tech_pref.merge(event_df[event_cols], on="Ticker", how="left")

    rows = []
    for _, r in merged.iterrows():
        rise = _prob_to_float(r.get("Rise Prob", "0%"))
        op_score = 0
        try:
            op_score = int(float(str(r.get("Op Score", 0)).replace("–", "0")))
        except Exception:
            op_score = 0
        action_s = str(r.get("Action", "")).upper()
        entry_s = str(r.get("Entry Quality", "")).upper()
        event_v = str(r.get("Verdict", ""))
        earnings = str(r.get("Earnings", ""))
        news = str(r.get("News", ""))
        trap_risk = str(r.get("Trap Risk", "–"))
        event_rank = _event_verdict_rank(event_v)
        days_out = r.get("Days Out", None)

        tech_ok = (rise >= 72) or ("BUY" in action_s) or ("BUY" in entry_s)
        watch_ok = (rise >= 62) or ("WATCH" in action_s) or ("WATCH" in entry_s)
        near_earn = False
        try:
            near_earn = pd.notna(days_out) and int(days_out) <= 7 and int(days_out) >= 0
        except Exception:
            near_earn = "≤7" in earnings

        rank_bits = _calc_final_swing_score(r)
        final_score = rank_bits["Final Swing Score"]

        if near_earn:
            swing_verdict = "🚫 AVOID — earnings ≤7d"
        elif trap_risk in ("FALSE BO", "GAP CHASE", "DISTRIB"):
            swing_verdict = f"⏳ WAIT — {trap_risk} risk"
        elif tech_ok and event_rank >= 2 and op_score >= 4 and final_score >= 55:
            swing_verdict = "✅ BUY / WATCH ENTRY"
        elif watch_ok and final_score >= 48:
            swing_verdict = "👀 WATCH"
        elif watch_ok and final_score >= 40:
            swing_verdict = "⏳ WAIT"
        else:
            swing_verdict = "🚫 AVOID"

        why_parts = []
        why_parts.append(f"Tech {r.get('Rise Prob','–')} / {r.get('Action','–')}")
        if r.get("Operator", "–") != "–": why_parts.append(f"Operator {r.get('Operator','–')}")
        if r.get("VWAP", "–") != "–": why_parts.append(f"VWAP {r.get('VWAP','–')}")
        if earnings and earnings != "nan": why_parts.append(f"Earnings {earnings}")
        if news and news != "nan": why_parts.append(f"News {news}")
        if r.get("Orders", "–") not in ("–", "nan", None): why_parts.append(str(r.get("Orders")))

        item = r.to_dict()
        item.update(rank_bits)
        item["Event Verdict"] = event_v if event_v and event_v != "nan" else "–"
        item["Swing Verdict"] = swing_verdict
        item["Why"] = " · ".join(why_parts)
        item["_swing_rank"] = (
            (3 if swing_verdict.startswith("✅") else 2 if swing_verdict.startswith("👀") else 1 if swing_verdict.startswith("⏳") else 0),
            item.get("Final Swing Score", 0),
            rise,
            op_score,
        )
        rows.append(item)

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["_rank_a"] = out["_swing_rank"].apply(lambda x: x[0])
    out["_rank_b"] = out["_swing_rank"].apply(lambda x: x[1])
    out["_rank_c"] = out["_swing_rank"].apply(lambda x: x[2])
    out["_rank_d"] = out["_swing_rank"].apply(lambda x: x[3])
    out = out.sort_values(["_rank_a", "_rank_b", "_rank_c", "_rank_d"], ascending=False)
    return out.drop(columns=[c for c in ["_swing_rank", "_rank_a", "_rank_b", "_rank_c", "_rank_d", "_rise", "_score", "_vcol"] if c in out.columns])


with tab_swing_picks:
    st.caption("🎯 Swing Picks — Bayesian ensemble rank: scanner + operator + earnings + news + sector")
    st.info(
        "Run **🚀 Scan** first. This tab keeps Bayesian as the base model, then adds "
        "operator activity, recent Yahoo news sentiment, order/contract keywords, sector tailwind, "
        "and earnings/trap penalties. Strategy Lab ML is optional and only useful if it beats the baseline."
    )

    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        swing_max_candidates = st.slider("Candidates to enrich", 5, 50, 25, step=5, key="swing_pick_max")
    with c2:
        swing_event_days = st.slider("Earnings/news lookahead", 7, 45, 30, step=1, key="swing_pick_days")
    with c3:
        manual_swing_tickers = st.text_input(
            "➕ Force include from Long Setups",
            placeholder="UUUU, APP, NVDA",
            key="swing_pick_manual"
        ).strip().upper()

    if df_long.empty:
        st.warning("No Long Setups available yet. Click **🚀 Scan** in the main scanner first.")
    else:
        df_swing_source = df_long.copy()
        forced = [t.strip().upper() for t in manual_swing_tickers.replace("\n", ",").split(",") if t.strip()]
        if forced:
            forced_rows = df_long[df_long["Ticker"].astype(str).str.upper().isin(forced)]
            rest_rows = df_long[~df_long["Ticker"].astype(str).str.upper().isin(forced)]
            df_swing_source = pd.concat([forced_rows, rest_rows], ignore_index=True)

        if st.button("🎯 Build Swing Picks", type="primary", key="btn_build_swing_picks"):
            with st.spinner("Adding earnings/news scoring to current Long Setups…"):
                st.session_state["df_swing_picks"] = _make_swing_picks_from_scan(
                    df_swing_source,
                    max_candidates=swing_max_candidates,
                    event_days=swing_event_days,
                )

        swing_df = st.session_state.get("df_swing_picks", pd.DataFrame())
        if swing_df.empty:
            st.caption("Click **🎯 Build Swing Picks** to enrich the latest Long Setups.")
        else:
            buy_n = int(swing_df["Swing Verdict"].astype(str).str.startswith("✅").sum()) if "Swing Verdict" in swing_df.columns else 0
            watch_n = int(swing_df["Swing Verdict"].astype(str).str.startswith("👀").sum()) if "Swing Verdict" in swing_df.columns else 0
            wait_n = int(swing_df["Swing Verdict"].astype(str).str.startswith("⏳").sum()) if "Swing Verdict" in swing_df.columns else 0
            avoid_n = int(swing_df["Swing Verdict"].astype(str).str.startswith("🚫").sum()) if "Swing Verdict" in swing_df.columns else 0
            st.success(f"✅ {buy_n} BUY/WATCH ENTRY · 👀 {watch_n} WATCH · ⏳ {wait_n} WAIT · 🚫 {avoid_n} AVOID")

            display_cols = [c for c in [
                "Ticker", "Swing Verdict", "ML Trade Quality", "ML Failure Risk", "Suggested Size",
                "Final Swing Score", "Bayes Score", "Operator Score", "News Score", "Sector Score", "Earnings Risk",
                "Trap Risk Score", "Entry Quality", "Rise Prob", "Action",
                "Operator", "Op Score", "VWAP", "Trap Risk", "Today %", "Price",
                "Sector", "Earnings", "Days Out", "EPS Trend", "News", "Orders",
                "Event Score", "Event Verdict", "Why", "Top News",
                "MA60 Stop", "TP1 +10%", "TP2 +15%", "TP3 +20%"
            ] if c in swing_df.columns]
            st.dataframe(
                swing_df[display_cols],
                width="stretch",
                hide_index=True,
                height=min(420, 38 + 35 * len(swing_df)),
            )

            with st.expander("📋 Copy tickers by final verdict"):
                for label, prefix in [("BUY/WATCH ENTRY", "✅"), ("WATCH", "👀"), ("WAIT", "⏳"), ("AVOID", "🚫")]:
                    tickers_txt = ", ".join(swing_df[swing_df["Swing Verdict"].astype(str).str.startswith(prefix)]["Ticker"].astype(str).tolist()) if "Ticker" in swing_df.columns else ""
                    st.text_area(label, value=tickers_txt or "–", height=70, key=f"swing_copy_{prefix}")

# ─────────────────────────────────────────────────────────────────────────────
# TAB — STRATEGY LAB / OPTIONAL ML QUALITY FILTER
# ─────────────────────────────────────────────────────────────────────────────
def _strategy_auc(y_true, scores):
    try:
        y = np.asarray(y_true, dtype=int)
        s = np.asarray(scores, dtype=float)
        pos = s[y == 1]; neg = s[y == 0]
        if len(pos) == 0 or len(neg) == 0:
            return None
        wins = 0.0
        for ps in pos:
            wins += float(np.sum(ps > neg)) + 0.5 * float(np.sum(ps == neg))
        return wins / float(len(pos) * len(neg))
    except Exception:
        return None


def _strategy_first_hit_label(future_high, future_low, entry, tp_pct=6.0, sl_pct=4.0):
    """1 if +target is hit before -stop within horizon; same-day tie counts as stop first."""
    if entry <= 0:
        return 0, 0.0, 0.0, "bad_entry"
    tp = entry * (1.0 + tp_pct / 100.0)
    sl = entry * (1.0 - sl_pct / 100.0)
    max_gain, max_dd = 0.0, 0.0
    for hi, lo in zip(future_high, future_low):
        try:
            hi = float(hi); lo = float(lo)
        except Exception:
            continue
        max_gain = max(max_gain, (hi / entry - 1.0) * 100.0)
        max_dd = min(max_dd, (lo / entry - 1.0) * 100.0)
        if lo <= sl and hi >= tp:
            return 0, max_gain, max_dd, "same_day_stop_first"
        if lo <= sl:
            return 0, max_gain, max_dd, "stop_first"
        if hi >= tp:
            return 1, max_gain, max_dd, "target_first"
    return 0, max_gain, max_dd, "no_target"


def _strategy_feature_row(long_sig, raw):
    bayes_prob = bayesian_prob(LONG_WEIGHTS, long_sig, 0.0) * 100.0
    bucket_counts = {}
    for k, active in long_sig.items():
        if active:
            b = SIGNAL_BUCKETS.get(k, "other")
            bucket_counts[b] = bucket_counts.get(b, 0) + 1
    trap = 1 if raw.get("false_breakout") or raw.get("gap_chase_risk") or raw.get("operator_distribution") else 0
    p = float(raw.get("p", 0) or 0)
    ma20 = float(raw.get("ma20", p) or p or 1)
    ma60 = float(raw.get("ma60", p) or p or 1)
    vwap = float(raw.get("vwap", p) or p or 1)
    atr = float(raw.get("atr", 0) or 0)
    return {
        "BayesProb": round(bayes_prob, 4),
        "SignalCount": int(sum(1 for v in long_sig.values() if v)),
        "TrendCount": int(bucket_counts.get("trend", 0)),
        "MomentumCount": int(bucket_counts.get("momentum", 0)),
        "VolumeCount": int(bucket_counts.get("volume", 0)),
        "StructureCount": int(bucket_counts.get("structure", 0)),
        "RelativeCount": int(bucket_counts.get("relative", 0)),
        "VolatilityCount": int(bucket_counts.get("volatility", 0)),
        "OptionsCount": int(bucket_counts.get("options", 0)),
        "OperatorScore": float(raw.get("operator_score", 0) or 0),
        "VolumeRatio": float(raw.get("vr", 0) or 0),
        "TodayPct": float(raw.get("today_chg_pct", 0) or 0),
        "RSI": float(raw.get("rsi0", 50) or 50),
        "ADX": float(raw.get("adx", 0) or 0),
        "ATRpct": round((atr / p * 100.0), 4) if p else 0.0,
        "PriceVsMA20Pct": round(((p / ma20) - 1.0) * 100.0, 4) if ma20 else 0.0,
        "PriceVsMA60Pct": round(((p / ma60) - 1.0) * 100.0, 4) if ma60 else 0.0,
        "PriceVsVWAPPct": round(((p / vwap) - 1.0) * 100.0, 4) if vwap else 0.0,
        "AboveVWAP": 1 if raw.get("above_vwap") else 0,
        "AboveMA60": 1 if raw.get("above_ma60") else 0,
        "NotChasing": 1 if raw.get("not_chasing") and raw.get("not_limit_up") else 0,
        "TrapRisk": trap,
        "FalseBreakout": 1 if raw.get("false_breakout") else 0,
        "GapChaseRisk": 1 if raw.get("gap_chase_risk") else 0,
        "DistributionRisk": 1 if raw.get("operator_distribution") else 0,
    }


@st.cache_data(ttl=3600, show_spinner=False)
def _strategy_build_dataset(tickers_tuple, period="2y", horizon=10, tp_pct=6.0, sl_pct=4.0, step=3):
    rows = []
    for ticker in list(tickers_tuple):
        try:
            raw_df = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=True)
            df = raw_df.copy()
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.ffill().dropna()
            if df.empty or len(df) < 260:
                continue
            close = df["Close"].ffill().dropna()
            high = df["High"].ffill().dropna()
            low = df["Low"].ffill().dropna()
            vol = df["Volume"].ffill().dropna()
            for end in range(220, len(close) - horizon, max(1, int(step))):
                try:
                    long_sig, _short_sig, sig_raw = compute_all_signals(close.iloc[:end], high.iloc[:end], low.iloc[:end], vol.iloc[:end])
                except Exception:
                    continue
                entry = float(close.iloc[end - 1])
                label, max_gain, max_dd, outcome = _strategy_first_hit_label(high.iloc[end:end+horizon], low.iloc[end:end+horizon], entry, tp_pct, sl_pct)
                feat = _strategy_feature_row(long_sig, sig_raw)
                feat.update({
                    "Ticker": ticker,
                    "Date": str(close.index[end - 1])[:10],
                    "Target": int(label),
                    "MaxGain%": round(max_gain, 3),
                    "MaxDD%": round(max_dd, 3),
                    "PathOutcome": outcome,
                    "BaselineScore": round(feat["BayesProb"] * 0.55 + feat["OperatorScore"] * 4.0 - feat["TrapRisk"] * 10.0, 4),
                })
                rows.append(feat)
        except Exception:
            continue
    return pd.DataFrame(rows)


def _strategy_train_model(data: pd.DataFrame, feature_cols):
    if data is None or data.empty or len(data) < 150:
        return None, {"Error": "Need at least 150 historical samples. Add tickers or use longer history."}
    d = data.copy().sort_values("Date")
    X = d[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0).astype(float)
    y = d["Target"].astype(int)
    split = int(len(d) * 0.70)
    if split <= 20 or len(d) - split <= 20 or y.nunique() < 2:
        return None, {"Error": "Not enough class diversity after chronological split."}
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]
    if _lgbm_available:
        model = LGBMClassifier(n_estimators=250, learning_rate=0.035, max_depth=3, num_leaves=15, min_child_samples=25, subsample=0.85, colsample_bytree=0.85, reg_lambda=2.0, random_state=42, verbose=-1)
        model_name = "LightGBM Classifier"
    elif _sklearn_strategy_available:
        model = HistGradientBoostingClassifier(max_iter=180, learning_rate=0.05, max_leaf_nodes=15, l2_regularization=1.0, random_state=42)
        model_name = "sklearn HistGradientBoosting fallback"
    else:
        return None, {"Error": "Install lightgbm or scikit-learn to use Strategy Lab ML."}
    try:
        model.fit(X_train, y_train)
        proba = model.predict_proba(X_test)[:, 1]
        baseline = d["BaselineScore"].iloc[split:].astype(float).to_numpy()
        pred = (proba >= 0.50).astype(int)
        base_pred = (baseline >= np.nanpercentile(baseline, 60)).astype(int)
        y_arr = y_test.to_numpy()
        if _sklearn_strategy_available:
            auc_ml = roc_auc_score(y_test, proba) if len(np.unique(y_test)) > 1 else None
            auc_base = roc_auc_score(y_test, baseline) if len(np.unique(y_test)) > 1 else None
            acc_ml = accuracy_score(y_test, pred)
            acc_base = accuracy_score(y_test, base_pred)
            prec_ml = precision_score(y_test, pred, zero_division=0)
            brier = brier_score_loss(y_test, proba)
        else:
            auc_ml = _strategy_auc(y_arr, proba)
            auc_base = _strategy_auc(y_arr, baseline)
            acc_ml = float(np.mean(pred == y_arr))
            acc_base = float(np.mean(base_pred == y_arr))
            prec_ml = float(np.sum((pred == 1) & (y_arr == 1)) / max(1, np.sum(pred == 1)))
            brier = float(np.mean((proba - y_arr) ** 2))
        top_n = max(5, int(len(proba) * 0.10))
        top_ml_idx = np.argsort(-proba)[:top_n]
        top_base_idx = np.argsort(-baseline)[:top_n]
        top_ml_win = float(np.mean(y_arr[top_ml_idx])) if top_n else 0.0
        top_base_win = float(np.mean(y_arr[top_base_idx])) if top_n else 0.0
        max_gain_arr = d["MaxGain%"].iloc[split:].to_numpy()
        max_dd_arr = d["MaxDD%"].iloc[split:].to_numpy()
        importance = []
        if hasattr(model, "feature_importances_"):
            importance = sorted(zip(feature_cols, list(model.feature_importances_)), key=lambda x: -abs(float(x[1])))[:12]
        report = {
            "Model": model_name,
            "Samples": int(len(d)), "Train": int(len(X_train)), "Test": int(len(X_test)),
            "Base Rate": round(float(y.mean()) * 100.0, 2),
            "ML AUC": round(float(auc_ml), 4) if auc_ml is not None else None,
            "Baseline AUC": round(float(auc_base), 4) if auc_base is not None else None,
            "AUC Edge": round(float((auc_ml or 0) - (auc_base or 0)), 4) if auc_ml is not None and auc_base is not None else None,
            "ML Accuracy": round(float(acc_ml) * 100.0, 2),
            "Baseline Accuracy": round(float(acc_base) * 100.0, 2),
            "ML Precision": round(float(prec_ml) * 100.0, 2),
            "Top 10% ML Win%": round(top_ml_win * 100.0, 2),
            "Top 10% Baseline Win%": round(top_base_win * 100.0, 2),
            "Top 10% Avg MaxGain%": round(float(max_gain_arr[top_ml_idx].mean()), 2) if top_n else 0.0,
            "Top 10% Avg MaxDD%": round(float(max_dd_arr[top_ml_idx].mean()), 2) if top_n else 0.0,
            "Brier": round(float(brier), 4),
            "Split Date": str(d["Date"].iloc[split]),
            "Recommended": "YES" if (auc_ml is not None and auc_base is not None and auc_ml >= auc_base + 0.02 and top_ml_win >= top_base_win) else "NO — keep Bayesian ensemble primary",
            "Importance": importance,
        }
        return (model, feature_cols, report), report
    except Exception as e:
        return None, {"Error": f"Training failed: {type(e).__name__}: {e}"}


def _strategy_apply_to_current(model_bundle, df_current: pd.DataFrame):
    if model_bundle is None or df_current is None or df_current.empty:
        return df_current
    try:
        model, feature_cols, _metrics = model_bundle
        qs = []
        for _, r in df_current.iterrows():
            bayes = _parse_score_num(r.get("Bayes Score", r.get("Rise Prob", 0)), 0.0)
            op = _parse_score_num(r.get("Operator Score", r.get("Op Score", 0)), 0.0)
            trap = 1 if str(r.get("Trap Risk", "–")).upper() in ("FALSE BO", "GAP CHASE", "DISTRIB") else 0
            feat = {c: 0.0 for c in feature_cols}
            feat.update({"BayesProb": bayes, "OperatorScore": op, "TrapRisk": trap, "AboveVWAP": 1 if str(r.get("VWAP", "")).upper().startswith("ABOVE") else 0, "TodayPct": _parse_score_num(r.get("Today %", 0), 0.0), "SignalCount": _parse_score_num(r.get("Score", 0), 0.0)})
            x = pd.DataFrame([[feat.get(c, 0.0) for c in feature_cols]], columns=feature_cols)
            try:
                qs.append(float(model.predict_proba(x)[0, 1]))
            except Exception:
                qs.append(np.nan)
        out = df_current.copy()
        out["ML Trade Quality"] = [f"{q*100:.1f}%" if pd.notna(q) else "–" for q in qs]
        out["ML Failure Risk"] = [f"{(1-q)*100:.1f}%" if pd.notna(q) else "–" for q in qs]
        def _size(q, verdict):
            if pd.isna(q): return "–"
            v = str(verdict)
            if q >= 0.65 and v.startswith("✅"): return "Normal"
            if q >= 0.55 and (v.startswith("✅") or v.startswith("👀")): return "Half"
            if q >= 0.48: return "Small / Watch"
            return "Avoid"
        out["Suggested Size"] = [_size(q, v) for q, v in zip(qs, out.get("Swing Verdict", pd.Series([""]*len(out))))]
        return out
    except Exception:
        return df_current


with tab_strategy:
    st.caption("🧠 Strategy Lab — optional ML filter for trade quality, not a replacement for Bayesian")
    st.info(
        "This trains a model to answer: did this setup hit the profit target before the stop within N trading days? "
        "The live scanner remains Bayesian ensemble first. Use ML only if it beats the baseline on chronological test data."
    )
    backend = "LightGBM" if _lgbm_available else "sklearn fallback" if _sklearn_strategy_available else "not installed"
    st.caption(f"ML backend: **{backend}** · Preferred install: `pip install lightgbm scikit-learn`")

    sl1, sl2, sl3, sl4 = st.columns([2, 1, 1, 1])
    with sl1:
        lab_tickers_txt = st.text_area("Training tickers", value=", ".join(_active_tickers[:25]), height=80, key="strategy_lab_tickers")
    with sl2:
        lab_period = st.selectbox("History", ["1y", "2y", "3y", "5y"], index=1, key="strategy_lab_period")
        lab_horizon = st.slider("Horizon days", 5, 20, 10, step=1, key="strategy_lab_horizon")
    with sl3:
        lab_tp = st.slider("Target %", 3.0, 12.0, 6.0, step=0.5, key="strategy_lab_tp")
        lab_sl = st.slider("Stop %", 2.0, 10.0, 4.0, step=0.5, key="strategy_lab_sl")
    with sl4:
        lab_step = st.slider("Sample step", 1, 10, 3, step=1, key="strategy_lab_step")
        lab_max_tickers = st.slider("Max tickers", 5, 80, 30, step=5, key="strategy_lab_max_tickers")

    if not (_lgbm_available or _sklearn_strategy_available):
        st.warning("Install `lightgbm` or `scikit-learn` to train the Strategy Lab model.")

    if st.button("🧠 Train Strategy Lab model", type="primary", key="strategy_lab_train"):
        lab_tickers = _unique_keep_order([t.strip().upper() for t in lab_tickers_txt.replace("\n", ",").split(",") if t.strip()])[:lab_max_tickers]
        if not lab_tickers:
            st.error("Enter at least a few tickers.")
        else:
            with st.spinner("Building historical +target before -stop training set..."):
                ds = _strategy_build_dataset(tuple(lab_tickers), period=lab_period, horizon=lab_horizon, tp_pct=lab_tp, sl_pct=lab_sl, step=lab_step)
            if ds.empty:
                st.error("No usable training rows. Try longer history, more liquid tickers, or more tickers.")
            else:
                feature_cols = [c for c in ds.columns if c not in ["Ticker", "Date", "Target", "MaxGain%", "MaxDD%", "PathOutcome", "BaselineScore"]]
                bundle, report = _strategy_train_model(ds, feature_cols)
                st.session_state["strategy_lab_dataset"] = ds
                st.session_state["strategy_lab_model"] = bundle
                st.session_state["strategy_lab_report"] = report

    report = st.session_state.get("strategy_lab_report")
    if report:
        if "Error" in report:
            st.error(report["Error"])
        else:
            metric_cols = st.columns(5)
            metric_cols[0].metric("ML AUC", report.get("ML AUC", "–"))
            metric_cols[1].metric("Baseline AUC", report.get("Baseline AUC", "–"))
            metric_cols[2].metric("AUC Edge", report.get("AUC Edge", "–"))
            metric_cols[3].metric("Top 10% ML Win", f"{report.get('Top 10% ML Win%', '–')}%")
            metric_cols[4].metric("Use ML?", report.get("Recommended", "–"))
            summary_cols = ["Model", "Samples", "Train", "Test", "Base Rate", "ML Accuracy", "Baseline Accuracy", "ML Precision", "Top 10% Baseline Win%", "Top 10% Avg MaxGain%", "Top 10% Avg MaxDD%", "Brier", "Split Date", "Recommended"]
            st.dataframe(pd.DataFrame([{k: report.get(k) for k in summary_cols if k in report}]), width="stretch", hide_index=True)
            imp = report.get("Importance", [])
            if imp:
                st.markdown("**Top ML features**")
                st.dataframe(pd.DataFrame(imp, columns=["Feature", "Importance"]), width="stretch", hide_index=True)
            if str(report.get("Recommended", "")).startswith("YES"):
                st.success("ML improved the baseline on this test. Use it as a trade-quality filter, not as the only signal.")
            else:
                st.warning("ML did not clearly beat the Bayesian ensemble. Keep Bayesian ensemble primary.")

    ds_prev = st.session_state.get("strategy_lab_dataset")
    if isinstance(ds_prev, pd.DataFrame) and not ds_prev.empty:
        with st.expander("Training data sample"):
            st.dataframe(ds_prev.tail(200), width="stretch", hide_index=True)

    st.markdown("---")
    st.markdown("### Apply trained ML overlay to current Swing Picks")
    latest_swing = st.session_state.get("df_swing_picks", pd.DataFrame())
    if st.session_state.get("strategy_lab_model") is None:
        st.caption("Train a Strategy Lab model first.")
    elif latest_swing.empty:
        st.caption("Build 🎯 Swing Picks first, then return here to apply the ML overlay.")
    elif st.button("Add ML quality/risk columns to latest Swing Picks", key="strategy_apply_overlay"):
        st.session_state["latest_swing_picks_ml"] = _strategy_apply_to_current(st.session_state.get("strategy_lab_model"), latest_swing)

    latest_ml = st.session_state.get("latest_swing_picks_ml")
    if isinstance(latest_ml, pd.DataFrame) and not latest_ml.empty:
        show_cols = [c for c in ["Ticker", "Swing Verdict", "ML Trade Quality", "ML Failure Risk", "Suggested Size", "Final Swing Score", "Bayes Score", "Operator Score", "Trap Risk", "Why"] if c in latest_ml.columns]
        st.dataframe(latest_ml[show_cols], width="stretch", hide_index=True)

# ─────────────────────────────────────────────────────────────────────────────
# TAB — EARNINGS CALENDAR
# ─────────────────────────────────────────────────────────────────────────────
with tab_earn:
    st.caption("📅 Upcoming Earnings · Verdict: price vs MAs + analyst target + EPS trend")

    # ── Controls ──────────────────────────────────────────────────────────────
    ec1, ec2, ec3 = st.columns([1, 1, 2])
    with ec1:
        earn_days = st.slider("Days ahead", 5, 30, 15, key="earn_days")
    with ec2:
        earn_market = st.radio("Market", ["🇺🇸 US", "🇸🇬 SGX", "🇮🇳 India"],
                               horizontal=True, key="earn_market_sel")
    with ec3:
        # Custom tickers — always include these even if not in base list
        extra_earn = st.text_input("➕ Add tickers",
            placeholder="UUUU, NVDA, AAPL", key="earn_extra").strip().upper()

    if earn_market == "🇺🇸 US":
        earn_base = list(US_TICKERS)
    elif earn_market == "🇸🇬 SGX":
        earn_base = list(SG_TICKERS)
    else:
        earn_base = list(INDIA_TICKERS)

    # Inject extra tickers at the front so they're scanned first
    if extra_earn:
        for t in [x.strip() for x in extra_earn.split(",") if x.strip()]:
            if t not in earn_base:
                earn_base.insert(0, t)

    # ── Search + filter — always visible ─────────────────────────────────────
    sf1, sf2 = st.columns([2, 2])
    with sf1:
        earn_search = st.text_input("🔍 Search ticker",
            placeholder="e.g. UUUU, NVDA", key="earn_search").strip().upper()
    with sf2:
        verdict_filter = st.multiselect(
            "Filter verdict",
            ["✅ BUY", "👀 WATCH", "⏳ WAIT", "🚫 AVOID"],
            default=[], key="earn_verdict_filter", placeholder="All verdicts"
        )

    # ── Fetch button ──────────────────────────────────────────────────────────
    if st.button("📅 Fetch Earnings Calendar", type="primary", key="btn_earnings"):
        st.cache_data.clear()   # force fresh fetch
        earn_df = fetch_earnings_calendar(tuple(earn_base), earn_days)
        st.session_state["earn_df"] = earn_df

    earn_df = st.session_state.get("earn_df", pd.DataFrame())

    if earn_df.empty:
        st.info("Click 📅 Fetch Earnings Calendar. Add UUUU in the ➕ Add tickers box to include it.")
    else:
        buys   = (earn_df["_vcol"] == "buy").sum()
        watch  = (earn_df["_vcol"] == "watch").sum()
        waits  = (earn_df["_vcol"] == "wait").sum()
        avoids = (earn_df["_vcol"] == "avoid").sum()
        st.caption(f"✅ **{buys}** Buy · 👀 **{watch}** Watch · ⏳ **{waits}** Wait · 🚫 **{avoids}** Avoid · {len(earn_df)} stocks found")

        # ── Apply search + filter ─────────────────────────────────────────────
        df_filtered = earn_df.copy()
        if earn_search:
            df_filtered = df_filtered[
                df_filtered["Ticker"].str.contains(earn_search, case=False, na=False)
            ]
        if verdict_filter:
            df_filtered = df_filtered[
                df_filtered["_vcol"].isin([
                    v.split()[0].strip("✅👀⏳🚫").strip().lower()
                    .replace("buy","buy").replace("watch","watch")
                    .replace("wait","wait").replace("avoid","avoid")
                    for v in verdict_filter
                ]) | df_filtered["Verdict"].isin(verdict_filter)
            ]

        if df_filtered.empty:
            st.info("No results — try clearing the search or filter.")
        else:
            def style_verdict(val):
                s = str(val)
                if "BUY"   in s: return "background-color:#d4edda;color:#155724;font-weight:600"
                if "WATCH" in s: return "background-color:#d1ecf1;color:#0c5460;font-weight:500"
                if "WAIT"  in s: return "background-color:#fff3cd;color:#856404"
                if "AVOID" in s: return "background-color:#f8d7da;color:#721c24;font-weight:600"
                return ""

            def style_eps(val):
                if "📈" in str(val): return "color:#155724;font-weight:600"
                if "📉" in str(val): return "color:#721c24;font-weight:600"
                return ""

            disp_cols = [c for c in [
                "Ticker","Earnings Date","Days Out","Price",
                "EPS Est","EPS Last","EPS Trend","Fwd PE",
                "Analyst Target","Upside","Above MA50","Above MA200",
                "Analyst Rec","Verdict",
            ] if c in df_filtered.columns]

            df_show = df_filtered[disp_cols].copy()
            if "Days Out" in df_show.columns:
                df_show["Days Out"] = pd.to_numeric(df_show["Days Out"], errors="coerce")

            col_cfg = {
                "Ticker":         st.column_config.TextColumn("Ticker",  width=60),
                "Earnings Date":  st.column_config.TextColumn("Date",    width=80),
                "Days Out":       st.column_config.NumberColumn("Days",  width=45),
                "Price":          st.column_config.TextColumn("Price",   width=62),
                "EPS Est":        st.column_config.TextColumn("EPS Est", width=58),
                "EPS Last":       st.column_config.TextColumn("EPS Last",width=58),
                "EPS Trend":      st.column_config.TextColumn("Trend",   width=72),
                "Fwd PE":         st.column_config.TextColumn("Fwd PE",  width=52),
                "Analyst Target": st.column_config.TextColumn("Target",  width=62),
                "Upside":         st.column_config.TextColumn("Upside",  width=55),
                "Above MA50":     st.column_config.TextColumn("MA50",    width=42),
                "Above MA200":    st.column_config.TextColumn("MA200",   width=45),
                "Analyst Rec":    st.column_config.TextColumn("Rec",     width=68),
                "Verdict":        st.column_config.TextColumn("Verdict", width=100),
            }
            cfg = {k: v for k, v in col_cfg.items() if k in df_show.columns}

            styler = df_show.style
            sfn    = styler.map if hasattr(styler, "map") else styler.applymap
            styled = sfn(style_verdict, subset=["Verdict"])
            styled = (styled.map if hasattr(styled,"map") else styled.applymap)(
                      style_eps, subset=["EPS Trend"])

            st.dataframe(styled, width="stretch", hide_index=True,
                         column_config=cfg,
                         height=min(40 + len(df_show) * 35, 520))

        st.caption(
            "**✅ BUY** = ≥4/5: above MA50, above MA200, analyst target higher, EPS↑>5%, Buy rated · "
            "**👀 WATCH** = 3/5 · **⏳ WAIT** = 2/5 · **🚫 AVOID** = ≤1/5 or near 52W low"
        )
        st.warning(
            "⚠️ Earnings are binary — stocks can gap ±20% overnight. "
            "Never hold full position through earnings. "
            "Best strategy: buy the dip AFTER earnings on good results."
        )



# ─────────────────────────────────────────────────────────────────────────────
# TAB — EVENT PREDICTOR: Earnings + News + Orders
# ─────────────────────────────────────────────────────────────────────────────
with tab_event:
    st.caption("📰 Event Predictor · combines earnings risk, recent news sentiment, order/contract keywords and trend confirmation")

    ev1, ev2, ev3 = st.columns([1, 1, 2])
    with ev1:
        ev_days = st.slider("Earnings window", 7, 60, 30, key="event_days")
    with ev2:
        ev_market = st.radio("Market", ["🇺🇸 US", "🇸🇬 SGX", "🇮🇳 India"], horizontal=True, key="event_market")
    with ev3:
        ev_extra = st.text_input("Tickers to check", placeholder="AIY.SI, OYY.SI, UUUU, NVDA", key="event_extra").strip().upper()

    if ev_market == "🇺🇸 US":
        ev_base = list(US_TICKERS[:120])
    elif ev_market == "🇸🇬 SGX":
        ev_base = list(SG_TICKERS)
    else:
        ev_base = list(INDIA_TICKERS)

    if ev_extra:
        extras = [x.strip() for x in ev_extra.split(",") if x.strip()]
        ev_base = extras + [x for x in ev_base if x not in extras]

    f1, f2 = st.columns([2, 2])
    with f1:
        ev_search = st.text_input("🔍 Search", placeholder="ticker", key="event_search").strip().upper()
    with f2:
        ev_verdict_filter = st.multiselect("Filter verdict", ["✅ BUY", "👀 WATCH", "⏳ WAIT", "🚫 AVOID"], default=[], key="event_verdict_filter", placeholder="All verdicts")

    if st.button("📰 Predict from Earnings + News + Orders", type="primary", key="btn_event_predictor"):
        st.session_state["event_df"] = fetch_event_predictions(tuple(dict.fromkeys(ev_base)), ev_days)

    event_df = st.session_state.get("event_df", pd.DataFrame())

    if event_df.empty:
        st.info("Enter tickers or select a market, then click 📰 Predict from Earnings + News + Orders.")
        st.caption("BUY requires enough event score plus trend confirmation. Near earnings ≤7 days is forced AVOID because gap risk is high.")
    else:
        df_event = event_df.copy()
        if ev_search:
            df_event = df_event[df_event["Ticker"].str.contains(ev_search, case=False, na=False)]
        if ev_verdict_filter:
            df_event = df_event[df_event["Verdict"].isin(ev_verdict_filter)]

        b = (df_event["_vcol"] == "buy").sum()
        w = (df_event["_vcol"] == "watch").sum()
        wait = (df_event["_vcol"] == "wait").sum()
        a = (df_event["_vcol"] == "avoid").sum()
        st.caption(f"✅ **{b}** Buy · 👀 **{w}** Watch · ⏳ **{wait}** Wait · 🚫 **{a}** Avoid · {len(df_event)} shown")

        def _style_event_verdict(val):
            s = str(val)
            if "BUY" in s: return "background-color:#d4edda;color:#155724;font-weight:700"
            if "WATCH" in s: return "background-color:#d1ecf1;color:#0c5460;font-weight:600"
            if "WAIT" in s: return "background-color:#fff3cd;color:#856404"
            if "AVOID" in s: return "background-color:#f8d7da;color:#721c24;font-weight:700"
            return ""

        def _style_event_score(val):
            try:
                v = float(val)
                if v >= 8: return "color:#155724;font-weight:700"
                if v >= 6: return "color:#0c5460;font-weight:600"
                if v < 4: return "color:#721c24;font-weight:600"
            except Exception:
                pass
            return ""

        disp = [c for c in [
            "Ticker", "Price", "Earnings", "Days Out", "EPS Trend", "News", "Orders",
            "Trend Score", "Event Score", "Verdict", "Evidence", "Top News"
        ] if c in df_event.columns]
        df_show = df_event[disp].copy()
        if "Days Out" in df_show.columns:
            df_show["Days Out"] = pd.to_numeric(df_show["Days Out"], errors="coerce")

        col_cfg = {
            "Ticker": st.column_config.TextColumn("Ticker", width=70),
            "Price": st.column_config.TextColumn("Price", width=65),
            "Earnings": st.column_config.TextColumn("Earnings", width=120),
            "Days Out": st.column_config.NumberColumn("Days", width=50),
            "EPS Trend": st.column_config.TextColumn("EPS", width=70),
            "News": st.column_config.TextColumn("News", width=90),
            "Orders": st.column_config.TextColumn("Orders", width=110),
            "Trend Score": st.column_config.TextColumn("Trend", width=62),
            "Event Score": st.column_config.NumberColumn("Score", width=55),
            "Verdict": st.column_config.TextColumn("Verdict", width=90),
            "Evidence": st.column_config.TextColumn("Evidence", width=220),
            "Top News": st.column_config.TextColumn("Top News", width=420),
        }

        styler = df_show.style
        sfn = styler.map if hasattr(styler, "map") else styler.applymap
        styled = sfn(_style_event_verdict, subset=["Verdict"])
        styled = (styled.map if hasattr(styled, "map") else styled.applymap)(_style_event_score, subset=["Event Score"])

        st.dataframe(
            styled, width="stretch", hide_index=True,
            column_config={k:v for k,v in col_cfg.items() if k in df_show.columns},
            height=min(60 + len(df_show) * 36, 560)
        )
        st.warning("News/order detection uses recent yfinance headlines and keyword matching. Treat it as a watchlist filter, not a guarantee. Confirm important orders from SGX/company announcements before buying.")



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


with tab_lt:
    st.caption("🌱 Long-Term Portfolio Builder · Stocks from top ETFs · Quality scored")

    lt_sub_us, lt_sub_sg, lt_sub_sg_funds, lt_sub_us_funds = st.tabs([
        "🇺🇸 US Stocks",
        "🇸🇬 SG Stocks",
        "🇸🇬 SG Funds & ETFs",
        "🇺🇸 US Funds & ETFs",
    ])

    # ── Shared scan function — shows ETF returns + stock results ─────────────
    def run_lt_scan(etf_dict, session_key, default_etfs, min_score_key, search_key,
                    existing_tickers=None, live_market_name=None, include_etf_tickers=True):
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            search = st.text_input("🔍 Search stock", placeholder="e.g. NVDA, DBS, Keppel",
                                   key=search_key).strip().upper()
        with c2:
            min_sc = st.slider("Min quality score", 1, 10, 5, key=min_score_key)
        with c3:
            max_lt_scan = st.slider("Max LT scan", 50, 1000, 300, step=25,
                                    key=f"{session_key}_max_scan",
                                    help="Maximum combined long-term candidates to score: existing tickers + ETF tickers/holdings + Yahoo/live tickers.")

        horizon_f = st.multiselect(
            "Filter horizon",
            ["⭐ CORE HOLD (3–5yr)","✅ BUY & HOLD (1–3yr)",
             "👀 ACCUMULATE on dips","⏳ MONITOR only"],
            default=[], key=f"hf_{session_key}", placeholder="All horizons"
        )

        if st.button("🔍 Find Long-Term Stocks", type="primary", key=f"btn_{session_key}"):
            etfs = list(default_etfs)
            existing_tickers = list(existing_tickers or [])

            # Long Term tab now scans a combined universe:
            #   existing curated tickers + ETF tickers + ETF holdings + Yahoo/live tickers.
            # Existing tickers are intentionally placed first so names such as UUUU/APP
            # are not pushed out by the scan limit.
            etf_holdings = {}
            source_map = {}

            def _add_symbol(sym, source_label, etf_label=None):
                sym = _clean_symbol(sym)
                if not sym:
                    return
                source_map.setdefault(sym, [])
                if source_label not in source_map[sym]:
                    source_map[sym].append(source_label)
                if etf_label:
                    etf_holdings.setdefault(sym, [])
                    if etf_label not in etf_holdings[sym]:
                        etf_holdings[sym].append(etf_label)

            for t in existing_tickers:
                _add_symbol(t, "Existing")

            if include_etf_tickers:
                for etf in etf_dict.keys():
                    _add_symbol(etf, "ETF")

            p1 = st.progress(0, text="Loading ETF holdings…")
            for i, etf in enumerate(etfs):
                for t in fetch_lt_holdings(etf):
                    _add_symbol(t, "ETF holding", etf)
                p1.progress((i+1)/max(1, len(etfs)))
            p1.empty()

            live_tickers = []
            live_source = "Yahoo/live disabled"
            if use_live_universe and live_market_name:
                with st.spinner("Fetching Yahoo/live long-term universe…"):
                    live_tickers, live_source = fetch_live_market_universe(
                        live_market_name, max_symbols=max_live_universe
                    )
                for t in live_tickers:
                    _add_symbol(t, "Yahoo/live")

            # Preserve priority order: existing → ETF tickers → ETF holdings → Yahoo/live.
            combined = []
            combined.extend([_clean_symbol(t) for t in existing_tickers])
            if include_etf_tickers:
                combined.extend([_clean_symbol(t) for t in etf_dict.keys()])
            combined.extend(sorted(etf_holdings.keys(), key=lambda t: len(etf_holdings.get(t, [])), reverse=True))
            combined.extend(list(live_tickers))
            unique = [t for t in _unique_keep_order(combined) if t in source_map]
            scan_list = unique[:max_lt_scan]

            st.caption(
                f"Long-term universe: Existing **{len(existing_tickers)}** · ETFs **{len(etf_dict)}** · "
                f"ETF holdings **{len(etf_holdings)}** · Yahoo/live **{len(live_tickers)}** · "
                f"Scoring **{len(scan_list)}** / {len(unique)} candidates · Source: {live_source}"
            )

            results = []
            p2 = st.progress(0); st2 = st.empty()
            total = max(1, len(scan_list))
            for i, ticker in enumerate(scan_list):
                st2.caption(f"Scoring {ticker} ({i+1}/{len(scan_list)})…")
                row = score_lt_stock(ticker)
                if row and row.get("_score",0) >= min_sc:
                    row["In ETFs"]   = ", ".join(etf_holdings.get(ticker, [])[:4]) or "–"
                    row["ETF Count"] = len(etf_holdings.get(ticker, []))
                    row["Sources"]   = ", ".join(source_map.get(ticker, []))
                    results.append(row)
                p2.progress((i+1)/total)
            p2.empty(); st2.empty()

            results.sort(key=lambda x: (-x.get("ETF Count",0), -x.get("_score",0)))
            st.session_state[session_key] = results
            st.session_state[f"{session_key}_universe_csv"] = ", ".join(scan_list)
            st.session_state[f"{session_key}_universe_stats"] = {
                "existing": len(existing_tickers),
                "etfs": len(etf_dict),
                "etf_holdings": len(etf_holdings),
                "live": len(live_tickers),
                "scored": len(scan_list),
                "total_candidates": len(unique),
                "live_source": live_source,
            }

        results = st.session_state.get(session_key, [])
        if not results:
            return

        df_lt = pd.DataFrame(results)
        if search:
            df_lt = df_lt[df_lt["Ticker"].str.contains(search, na=False) |
                          df_lt["Name"].str.contains(search, case=False, na=False)]
        if horizon_f:
            df_lt = df_lt[df_lt["Horizon"].isin(horizon_f)]

        core = (df_lt["_hcol"]=="buy").sum()
        buyh = (df_lt["_hcol"]=="watch").sum()
        acc  = (df_lt["_hcol"]=="wait").sum()
        st.caption(f"⭐ **{core}** Core Hold · ✅ **{buyh}** Buy & Hold · 👀 **{acc}** Accumulate · {len(df_lt)} total")

        def style_horizon(val):
            s = str(val)
            if "CORE"  in s: return "background-color:#d4edda;color:#155724;font-weight:700"
            if "BUY"   in s: return "background-color:#d1ecf1;color:#0c5460;font-weight:600"
            if "ACCUM" in s: return "background-color:#fff3cd;color:#856404"
            return "color:#888"

        def style_exp1y(val):
            s = str(val)
            try:
                v = float(s.strip("+%"))
                if v >= 20: return "background-color:#1a7a3a;color:#fff;font-weight:700"
                if v >= 12: return "background-color:#27ae60;color:#fff;font-weight:600"
                if v >= 6:  return "background-color:#a9dfbf;color:#145a32"
            except: pass
            return ""

        def style_growth(val):
            try:
                v = float(str(val).strip("+%"))
                if v >= 20: return "color:#155724;font-weight:700"
                if v >= 10: return "color:#1a5276;font-weight:600"
            except: pass
            return ""

        disp = [c for c in ["Ticker","Name","Sector","Horizon","Exp 1Y Return",
                "Price","Mkt Cap","Return Breakdown",
                "Rev Growth","EPS Growth","ROE","Margin",
                "Fwd PE","Div Yield","Beta","MA200","Target","Upside","Rec",
                "Score","Sources","ETF Count","In ETFs"] if c in df_lt.columns]
        df_show = df_lt[disp].copy()

        col_cfg = {
            "Ticker":            st.column_config.TextColumn("Ticker",       width=62),
            "Name":              st.column_config.TextColumn("Name",         width=130),
            "Sector":            st.column_config.TextColumn("Sector",       width=95),
            "Sources":           st.column_config.TextColumn("Sources",      width=105),
            "ETF Count":         st.column_config.NumberColumn("ETFs",       width=42),
            "In ETFs":           st.column_config.TextColumn("In ETFs",      width=120),
            "Price":             st.column_config.TextColumn("Price",        width=60),
            "Mkt Cap":           st.column_config.TextColumn("Cap",          width=60),
            "Exp 1Y Return":     st.column_config.TextColumn("Exp 1Y Ret",   width=80),
            "Return Breakdown":  st.column_config.TextColumn("Div+Price",    width=130),
            "Rev Growth":        st.column_config.TextColumn("RevGrw",       width=58),
            "EPS Growth":        st.column_config.TextColumn("EPSGrw",       width=58),
            "ROE":               st.column_config.TextColumn("ROE",          width=48),
            "Margin":            st.column_config.TextColumn("Margin",       width=52),
            "Fwd PE":            st.column_config.TextColumn("FwdPE",        width=52),
            "Div Yield":         st.column_config.TextColumn("Yield",        width=48),
            "Beta":              st.column_config.TextColumn("Beta",         width=42),
            "MA200":             st.column_config.TextColumn("MA200",        width=42),
            "Target":            st.column_config.TextColumn("Target",       width=60),
            "Upside":            st.column_config.TextColumn("Upside",       width=52),
            "Rec":               st.column_config.TextColumn("Rec",          width=68),
            "Score":             st.column_config.TextColumn("Score",        width=48),
            "Horizon":           st.column_config.TextColumn("Horizon",      width=145),
        }
        cfg = {k:v for k,v in col_cfg.items() if k in df_show.columns}
        sfn = df_show.style.map if hasattr(df_show.style,"map") else df_show.style.applymap
        styled = sfn(style_horizon, subset=["Horizon"])
        if "Exp 1Y Return" in df_show.columns:
            styled = (styled.map if hasattr(styled,"map") else styled.applymap)(
                style_exp1y, subset=["Exp 1Y Return"])
        for col in ["Rev Growth","EPS Growth","Upside"]:
            if col in df_show.columns:
                styled = (styled.map if hasattr(styled,"map") else styled.applymap)(
                    style_growth, subset=[col])
        st.dataframe(styled, width="stretch", hide_index=True,
                     column_config=cfg, height=min(40+len(df_show)*35, 600))
        st.caption("Score/10: RevGrw(+2) EPSGrw(+2) ROE(+1) Margin(+1) LowDebt(+1) AboveMA200(+1) Target(+1) BuyRated(+1) · "
                   "ETF Count = held by how many ETFs (higher = more institutional conviction)")
        stats = st.session_state.get(f"{session_key}_universe_stats", {})
        csv_tickers = st.session_state.get(f"{session_key}_universe_csv", "")
        if stats:
            st.caption(
                f"Scanned universe: Existing {stats.get('existing',0)} · ETFs {stats.get('etfs',0)} · "
                f"ETF holdings {stats.get('etf_holdings',0)} · Yahoo/live {stats.get('live',0)} · "
                f"Scored {stats.get('scored',0)} / {stats.get('total_candidates',0)}"
            )
        if csv_tickers:
            with st.expander("📋 Long-term scanned tickers", expanded=False):
                st.text_area("Comma-separated tickers", value=csv_tickers, height=90,
                             key=f"{session_key}_universe_text")

    # ── Shared fund table function ────────────────────────────────────────────
    def show_fund_table(fund_rows, search_key):
        fsrch = st.text_input("🔍 Search fund", placeholder="Vanguard, REIT, Robo…",
                              key=search_key).strip()
        df_f = pd.DataFrame(fund_rows)
        if fsrch:
            df_f = df_f[df_f.apply(lambda r: fsrch.lower() in str(r).lower(), axis=1)]

        def sret(val):
            s = str(val)
            for p in ["17","18","19","20","21","22","15","16"]:
                if p in s: return "background-color:#d4edda;color:#155724;font-weight:700"
            for p in ["10","11","12","13","14"]:
                if p in s: return "background-color:#d1ecf1;color:#0c5460;font-weight:600"
            return "color:#888"

        def srisk(val):
            s = str(val)
            if s == "None": return "background-color:#d4edda;color:#155724"
            if s == "Med":  return "background-color:#d1ecf1;color:#0c5460"
            if "Med-H" in s:return "background-color:#fff3cd;color:#856404"
            if s == "High": return "background-color:#f8d7da;color:#721c24"
            return ""

        # Build display columns — include 1Y/3Y if present
        ret_cols = [c for c in ["Ret1Y","Ret3Y","Ret5Y"] if c in df_f.columns]
        col_cfg_f = {
            "Name":   st.column_config.TextColumn("Fund / ETF",    width=210),
            "Type":   st.column_config.TextColumn("Type",          width=100),
            "Ret1Y":  st.column_config.TextColumn("1Y Ann Return", width=90),
            "Ret3Y":  st.column_config.TextColumn("3Y Ann Return", width=90),
            "Ret5Y":  st.column_config.TextColumn("5Y Ann Return", width=90),
            "Min":    st.column_config.TextColumn("Min invest",    width=70),
            "Risk":   st.column_config.TextColumn("Risk",          width=58),
            "Access": st.column_config.TextColumn("Platform",      width=110),
            "Note":   st.column_config.TextColumn("Notes",         width=240),
        }
        sfn = df_f.style.map if hasattr(df_f.style,"map") else df_f.style.applymap
        styled = sfn(sret, subset=ret_cols) if ret_cols else df_f.style
        styled = (styled.map if hasattr(styled,"map") else styled.applymap)(srisk, subset=["Risk"])
        cfg = {k:v for k,v in col_cfg_f.items() if k in df_f.columns}
        st.dataframe(styled, width="stretch", hide_index=True,
                     column_config=cfg, height=min(40+len(df_f)*35, 560))
        st.caption("Returns are approximate annualised historical figures. Past performance ≠ future returns.")

    # ─────────────────────────────────────────────────────────────────────────
    with lt_sub_us:
        st.caption("🇺🇸 US long-term universe = existing US tickers + ETF tickers/holdings + Yahoo/live tickers · sorted by cross-ETF conviction")
        with st.expander("📊 Source ETFs — 1Y / 3Y / 5Y Ann Returns (click column to sort)", expanded=False):
            df_etf_us = pd.DataFrame([
                {"ETF":k, "Name":v["name"], "Theme":v["theme"],
                 "1Y Ann%": v.get('ret1y',0),
                 "3Y Ann%": v.get('ret3y',0),
                 "5Y Ann%": v.get('ret5y',0)}
                for k,v in LT_ETF_US.items()
            ])
            def _sc(val):
                v = float(val)
                if v>=15: return "background-color:#1a7a3a;color:#fff;font-weight:700"
                if v>=10: return "background-color:#1a5276;color:#fff;font-weight:600"
                if v>= 5: return "background-color:#f0c040;color:#333"
                if v< 0:  return "background-color:#922b21;color:#fff"
                return ""
            sfn = df_etf_us.style.map if hasattr(df_etf_us.style,"map") else df_etf_us.style.applymap
            st.dataframe(
                sfn(_sc, subset=["1Y Ann%","3Y Ann%","5Y Ann%"]),
                width="stretch", hide_index=True,
                column_config={
                    "ETF":     st.column_config.TextColumn("ETF",    width=70),
                    "Name":    st.column_config.TextColumn("Name",   width=190),
                    "Theme":   st.column_config.TextColumn("Theme",  width=120),
                    "1Y Ann%": st.column_config.NumberColumn("1Y Ann%", format="%.1f%%", width=80),
                    "3Y Ann%": st.column_config.NumberColumn("3Y Ann%", format="%.1f%%", width=80),
                    "5Y Ann%": st.column_config.NumberColumn("5Y Ann%", format="%.1f%%", width=80),
                },
                height=min(40+len(df_etf_us)*35, 450),
            )
        run_lt_scan(LT_ETF_US, "lt_us",
                    ["QQQ","QUAL","MOAT","SOXX","VGT","INDA","SMIN"],
                    "lt_us_min", "lt_us_search",
                    existing_tickers=US_TICKERS,
                    live_market_name="🇺🇸 US",
                    include_etf_tickers=True)

    # ─────────────────────────────────────────────────────────────────────────
    with lt_sub_sg:
        st.caption("🇸🇬 SGX long-term stocks · quality scored · curated list + ETF holdings")
        with st.expander("📊 Source ETFs — 1Y / 3Y / 5Y Ann Returns (click column to sort)", expanded=False):
            df_etf_sg = pd.DataFrame([
                {"ETF":k, "Name":v["name"], "Theme":v["theme"],
                 "1Y Ann%": v.get('ret1y',0),
                 "3Y Ann%": v.get('ret3y',0),
                 "5Y Ann%": v.get('ret5y',0)}
                for k,v in LT_ETF_SG.items()
            ])
            def _sc2(val):
                v = float(val)
                if v>=15: return "background-color:#1a7a3a;color:#fff;font-weight:700"
                if v>=10: return "background-color:#1a5276;color:#fff;font-weight:600"
                if v>= 5: return "background-color:#f0c040;color:#333"
                if v<  0: return "background-color:#922b21;color:#fff"
                return ""
            sfn2 = df_etf_sg.style.map if hasattr(df_etf_sg.style,"map") else df_etf_sg.style.applymap
            st.dataframe(
                sfn2(_sc2, subset=["1Y Ann%","3Y Ann%","5Y Ann%"]),
                width="stretch", hide_index=True,
                column_config={
                    "ETF":     st.column_config.TextColumn("ETF",    width=70),
                    "Name":    st.column_config.TextColumn("Name",   width=190),
                    "Theme":   st.column_config.TextColumn("Theme",  width=120),
                    "1Y Ann%": st.column_config.NumberColumn("1Y Ann%", format="%.1f%%", width=80),
                    "3Y Ann%": st.column_config.NumberColumn("3Y Ann%", format="%.1f%%", width=80),
                    "5Y Ann%": st.column_config.NumberColumn("5Y Ann%", format="%.1f%%", width=80),
                },
                height=min(40+len(df_etf_sg)*35, 420),
            )

        # Curated SGX long-term universe — reliable fallback when ETF holdings unavailable
        SG_LT_TICKERS = [
            # ── Banks (highest quality on SGX) ────────────────────────────────
            "D05.SI",   # DBS — strongest bank in SE Asia, consistent div growth
            "O39.SI",   # OCBC — wealth management + banking, capital strength
            "U11.SI",   # UOB — ASEAN expansion, steady compounder
            # ── Financials / Exchanges ─────────────────────────────────────────
            "S68.SI",   # SGX — monopoly exchange, record profits 2025-2026
            "AIY.SI",   # iFAST — UK ePension growth driver, fintech compounder
            # ── Technology / Semiconductor supply chain ────────────────────────
            "558.SI",   # UMS Holdings — semiconductor equipment, AI supply chain
            "E28.SI",   # Frencken — semicon EMS, 47.8% return Q1 2026
            "5AB.SI",   # AEM Holdings — semiconductor test, TSMC/Intel exposure
            "BN2.SI",   # Valuetronics — electronics, institutional buying
            "V03.SI",   # Venture Corp — high-mix electronics, quality manufacturer
            # ── Industrials / Offshore ─────────────────────────────────────────
            "S51.SI",   # Seatrium — offshore & marine, clean energy contracts
            "BN4.SI",   # Keppel Corp — asset-light transformation, infra
            "U96.SI",   # Sembcorp — clean energy, data centre power
            "S58.SI",   # SATS — aviation ground handling, post-COVID recovery
            # ── Telecoms ──────────────────────────────────────────────────────
            "Z74.SI",   # Singtel — 5G + regional associates (AIS, Airtel, Optus)
            # ── Consumer / Property ───────────────────────────────────────────
            "C52.SI",   # ComfortDelGro — transport, UK recovery
            "F34.SI",   # Wilmar International — agribusiness, Asia consumer
            "OYY.SI",   # PropNex — property agency, recurring commission
            # ── REITs (income + growth) ────────────────────────────────────────
            "C38U.SI",  # CapitaLand CICT — premium SG retail + commercial
            "A17U.SI",  # Ascendas REIT — industrial/logistics, quarterly div
            "M44U.SI",  # Mapletree Logistics — Asia logistics, quarterly div
            "AJBU.SI",  # Keppel DC REIT — data centres, AI tailwind
            "J91U.SI",  # AIMS APAC REIT — industrial, 6.5% yield
            "SK6U.SI",  # Frasers Centrepoint Trust — suburban malls
            # ── Civil construction / Infrastructure ────────────────────────────
            "P9D.SI",   # Civmec — industrial construction
            "5JS.SI",   # Dyna-Mac — offshore modules
        ]

        # Search + score controls
        sg_c1, sg_c2 = st.columns([3, 1])
        with sg_c1:
            sg_search = st.text_input("🔍 Search stock",
                placeholder="e.g. DBS, Keppel, REIT", key="lt_sg_search").strip().upper()
        with sg_c2:
            sg_min_sc = st.slider("Min score", 1, 10, 4, key="lt_sg_min")

        sg_horizon_f = st.multiselect(
            "Filter horizon",
            ["⭐ CORE HOLD (3–5yr)","✅ BUY & HOLD (1–3yr)",
             "👀 ACCUMULATE on dips","⏳ MONITOR only"],
            default=[], key="hf_lt_sg", placeholder="All horizons"
        )

        lt_sg_max_scan = st.slider("Max SG LT scan", 25, 1000, 250, step=25,
                                  key="lt_sg_max_scan",
                                  help="Maximum combined SG long-term candidates to score: SG curated/existing tickers + SG ETF tickers + SGX/live tickers.")

        if st.button("🔍 Score SGX Long-Term Stocks", type="primary", key="btn_lt_sg"):
            live_sg_tickers = []
            live_sg_source = "SGX/live disabled"
            if use_live_universe:
                with st.spinner("Fetching SGX/live long-term universe…"):
                    live_sg_tickers, live_sg_source = fetch_live_market_universe(
                        "🇸🇬 SGX", max_symbols=max_live_universe
                    )

            sg_sources = {}
            def _add_sg(sym, src, force_sg_suffix=True):
                suffix = ".SI" if force_sg_suffix and not str(sym).upper().endswith(".SI") and "." not in str(sym) else ""
                sym = _clean_symbol(sym, suffix)
                if not sym:
                    return
                sg_sources.setdefault(sym, [])
                if src not in sg_sources[sym]:
                    sg_sources[sym].append(src)

            for t in SG_LT_TICKERS:
                _add_sg(t, "LT curated")
            for t in SG_TICKERS:
                _add_sg(t, "Existing")
            for t in LT_ETF_SG.keys():
                _add_sg(t, "ETF", force_sg_suffix=False)
            for t in live_sg_tickers:
                _add_sg(t, "SGX/live")

            sg_scan_list = _unique_keep_order(
                [_clean_symbol(t, ".SI" if not str(t).upper().endswith(".SI") and "." not in str(t) else "") for t in SG_LT_TICKERS] +
                [_clean_symbol(t, ".SI" if not str(t).upper().endswith(".SI") and "." not in str(t) else "") for t in SG_TICKERS] +
                [_clean_symbol(t) for t in LT_ETF_SG.keys()] +
                [_clean_symbol(t, ".SI" if not str(t).upper().endswith(".SI") and "." not in str(t) else "") for t in live_sg_tickers]
            )[:lt_sg_max_scan]

            st.caption(
                f"SG long-term universe: LT curated {len(SG_LT_TICKERS)} · Existing {len(SG_TICKERS)} · "
                f"ETFs {len(LT_ETF_SG)} · SGX/live {len(live_sg_tickers)} · "
                f"Scoring {len(sg_scan_list)} / {len(sg_sources)} candidates · Source: {live_sg_source}"
            )

            results = []
            p = st.progress(0); st_s = st.empty()
            total = max(1, len(sg_scan_list))
            for i, ticker in enumerate(sg_scan_list):
                st_s.caption(f"Scoring {ticker} ({i+1}/{len(sg_scan_list)})…")
                row = score_lt_stock(ticker)
                if row and row.get("_score", 0) >= sg_min_sc:
                    row["Sources"] = ", ".join(sg_sources.get(ticker, []))
                    results.append(row)
                p.progress((i+1)/total)
            p.empty(); st_s.empty()
            results.sort(key=lambda x: -x.get("_score", 0))
            st.session_state["lt_sg"] = results
            st.session_state["lt_sg_universe_csv"] = ", ".join(sg_scan_list)
            st.session_state["lt_sg_universe_stats"] = {
                "lt_curated": len(SG_LT_TICKERS),
                "existing": len(SG_TICKERS),
                "etfs": len(LT_ETF_SG),
                "live": len(live_sg_tickers),
                "scored": len(sg_scan_list),
                "total_candidates": len(sg_sources),
                "live_source": live_sg_source,
            }

        results = st.session_state.get("lt_sg", [])
        if not results:
            st.info(f"Click 🔍 Score SGX Long-Term Stocks. Scores combined SGX universe: LT curated + existing tickers + SG ETFs + SGX/live tickers on: "
                    "revenue growth, EPS growth, ROE, margins, debt, price vs MA200, analyst target, Buy rating.")
        else:
            df_sg = pd.DataFrame(results)
            if sg_search:
                df_sg = df_sg[df_sg["Ticker"].str.contains(sg_search, na=False) |
                              df_sg["Name"].str.contains(sg_search, case=False, na=False)]
            if sg_horizon_f:
                df_sg = df_sg[df_sg["Horizon"].isin(sg_horizon_f)]

            core = (df_sg["_hcol"]=="buy").sum()
            buyh = (df_sg["_hcol"]=="watch").sum()
            acc  = (df_sg["_hcol"]=="wait").sum()
            st.caption(f"⭐ **{core}** Core Hold · ✅ **{buyh}** Buy & Hold · "
                       f"👀 **{acc}** Accumulate · {len(df_sg)} total")

            def _sth(val):
                s = str(val)
                if "CORE"  in s: return "background-color:#d4edda;color:#155724;font-weight:700"
                if "BUY"   in s: return "background-color:#d1ecf1;color:#0c5460;font-weight:600"
                if "ACCUM" in s: return "background-color:#fff3cd;color:#856404"
                return "color:#888"

            def _stg(val):
                try:
                    v = float(str(val).strip("+%"))
                    if v >= 20: return "color:#155724;font-weight:700"
                    if v >= 10: return "color:#1a5276;font-weight:600"
                except: pass
                return ""

            disp = [c for c in ["Ticker","Name","Sector","Sources","Price","Mkt Cap",
                    "Exp 1Y Return","Return Breakdown",
                    "Rev Growth","EPS Growth","ROE","Margin","Fwd PE",
                    "Div Yield","Beta","MA200","Target","Upside","Rec",
                    "Score","Horizon"] if c in df_sg.columns]
            df_show = df_sg[disp].copy()

            col_cfg_sg = {
                "Ticker":           st.column_config.TextColumn("Ticker",      width=70),
                "Name":             st.column_config.TextColumn("Name",        width=150),
                "Sector":           st.column_config.TextColumn("Sector",      width=95),
                "Sources":          st.column_config.TextColumn("Sources",     width=105),
                "Price":            st.column_config.TextColumn("Price",       width=62),
                "Mkt Cap":          st.column_config.TextColumn("Cap",         width=62),
                "Exp 1Y Return":    st.column_config.TextColumn("Exp 1Y Ret",  width=80),
                "Return Breakdown": st.column_config.TextColumn("Div+Price",   width=130),
                "Rev Growth":       st.column_config.TextColumn("RevGrw",      width=58),
                "EPS Growth":       st.column_config.TextColumn("EPSGrw",      width=58),
                "ROE":              st.column_config.TextColumn("ROE",         width=48),
                "Margin":           st.column_config.TextColumn("Margin",      width=52),
                "Fwd PE":           st.column_config.TextColumn("FwdPE",       width=52),
                "Div Yield":        st.column_config.TextColumn("Yield",       width=50),
                "Beta":             st.column_config.TextColumn("Beta",        width=42),
                "MA200":            st.column_config.TextColumn("MA200",       width=45),
                "Target":           st.column_config.TextColumn("Target",      width=62),
                "Upside":           st.column_config.TextColumn("Upside",      width=52),
                "Rec":              st.column_config.TextColumn("Rec",         width=68),
                "Score":            st.column_config.TextColumn("Score",       width=48),
                "Horizon":          st.column_config.TextColumn("Horizon",     width=145),
            }
            cfg = {k:v for k,v in col_cfg_sg.items() if k in df_show.columns}
            sfn = df_show.style.map if hasattr(df_show.style,"map") else df_show.style.applymap
            styled = sfn(_sth, subset=["Horizon"])
            if "Exp 1Y Return" in df_show.columns:
                def _se(val):
                    try:
                        v = float(str(val).strip("+%"))
                        if v >= 20: return "background-color:#1a7a3a;color:#fff;font-weight:700"
                        if v >= 12: return "background-color:#27ae60;color:#fff;font-weight:600"
                        if v >= 6:  return "background-color:#a9dfbf;color:#145a32"
                    except: pass
                    return ""
                styled = (styled.map if hasattr(styled,"map") else styled.applymap)(
                    _se, subset=["Exp 1Y Return"])
            for col in ["Rev Growth","EPS Growth","Upside"]:
                if col in df_show.columns:
                    styled = (styled.map if hasattr(styled,"map") else styled.applymap)(
                        _stg, subset=[col])
            st.dataframe(styled, width="stretch", hide_index=True,
                         column_config=cfg, height=min(40+len(df_show)*35, 600))
            st.caption("Score/10: RevGrw(+2) EPSGrw(+2) ROE>15%(+1) Margin>15%(+1) "
                       "LowDebt(+1) AboveMA200(+1) AnalystTarget(+1) BuyRated(+1)")
            sg_stats = st.session_state.get("lt_sg_universe_stats", {})
            sg_csv = st.session_state.get("lt_sg_universe_csv", "")
            if sg_stats:
                st.caption(
                    f"Scanned universe: LT curated {sg_stats.get('lt_curated',0)} · Existing {sg_stats.get('existing',0)} · "
                    f"ETFs {sg_stats.get('etfs',0)} · SGX/live {sg_stats.get('live',0)} · "
                    f"Scored {sg_stats.get('scored',0)} / {sg_stats.get('total_candidates',0)}"
                )
            if sg_csv:
                with st.expander("📋 SG long-term scanned tickers", expanded=False):
                    st.text_area("Comma-separated tickers", value=sg_csv, height=90,
                                 key="lt_sg_universe_text")

    # ─────────────────────────────────────────────────────────────────────────
    with lt_sub_sg_funds:
        st.caption("🇸🇬 SG-accessible ETFs & funds · UCITS, SGX-listed, Robo-advisors, CPF-investible")
        SG_FUNDS = [
            {"Name":"Vanguard S&P 500 (VUAA.L)",       "Type":"UCITS ETF",      "Ret1Y":"~10%","Ret3Y":"~12%","Ret5Y":"~15%","Min":"S$1",    "Risk":"Med",  "Access":"IBKR/Moomoo","Note":"Irish-domiciled, accumulating, 0% WHT"},
            {"Name":"iShares S&P 500 (CSPX.L)",        "Type":"UCITS ETF",      "Ret1Y":"~10%","Ret3Y":"~12%","Ret5Y":"~15%","Min":"S$1",    "Risk":"Med",  "Access":"IBKR",       "Note":"Acc, no dividend drag, ER 0.07%"},
            {"Name":"Xtrackers Nasdaq-100 (XNAS.L)",   "Type":"UCITS ETF",      "Ret1Y":"~11%","Ret3Y":"~14%","Ret5Y":"~17%","Min":"S$1",    "Risk":"Med-H","Access":"IBKR",       "Note":"Best UCITS Nasdaq option, ER 0.20%"},
            {"Name":"AXA Nasdaq-100 (ANAU.DE)",        "Type":"UCITS ETF",      "Ret1Y":"~11%","Ret3Y":"~14%","Ret5Y":"~17%","Min":"S$1",    "Risk":"Med-H","Access":"IBKR",       "Note":"EUR-denominated Nasdaq tracker"},
            {"Name":"Vanguard FTSE All-World (VWRA.L)","Type":"UCITS ETF",      "Ret1Y":"~ 8%","Ret3Y":"~10%","Ret5Y":"~13%","Min":"S$1",    "Risk":"Med",  "Access":"IBKR",       "Note":"Global diversification in 1 ETF"},
            {"Name":"SPDR MSCI World (SWRD.L)",        "Type":"UCITS ETF",      "Ret1Y":"~ 8%","Ret3Y":"~10%","Ret5Y":"~13%","Min":"S$1",    "Risk":"Med",  "Access":"IBKR",       "Note":"Developed markets only, ER 0.12%"},
            {"Name":"SPDR STI ETF (ES3.SI)",           "Type":"SGX ETF",        "Ret1Y":"~29%","Ret3Y":"~13%","Ret5Y":"~10%","Min":"S$500",  "Risk":"Med",  "Access":"Any broker", "Note":"CPF-OA investible, tracks STI 30"},
            {"Name":"Nikko AM STI ETF (G3B.SI)",       "Type":"SGX ETF",        "Ret1Y":"~29%","Ret3Y":"~13%","Ret5Y":"~10%","Min":"S$100",  "Risk":"Med",  "Access":"Any broker", "Note":"CPF-OA investible, lowest TER 0.21%"},
            {"Name":"CSOP S-REIT Leaders (SRT.SI)",    "Type":"SGX REIT ETF",   "Ret1Y":"~ 9%","Ret3Y":"~ 4%","Ret5Y":"~ 6%","Min":"S$1",    "Risk":"Med",  "Access":"Any broker", "Note":"5.6% dividend yield + REIT diversification"},
            {"Name":"Lion-Phillip S-REIT (CLR.SI)",    "Type":"SGX REIT ETF",   "Ret1Y":"~ 9%","Ret3Y":"~ 4%","Ret5Y":"~ 6%","Min":"S$1",    "Risk":"Med",  "Access":"Any broker", "Note":"Morningstar REIT index, 5.5% yield"},
            {"Name":"ABF SG Bond ETF (A35.SI)",        "Type":"SGX Bond ETF",   "Ret1Y":"~ 3%","Ret3Y":"~ 2%","Ret5Y":"~ 4%","Min":"S$1",    "Risk":"Low",  "Access":"Any broker", "Note":"Asia bond diversification, 4.6% yield"},
            {"Name":"Syfe Equity100",                  "Type":"Robo",           "Ret1Y":"~10%","Ret3Y":"~11%","Ret5Y":"~14%","Min":"S$1",    "Risk":"Med-H","Access":"Syfe",       "Note":"Global equity, auto-rebalanced"},
            {"Name":"Endowus Fund Smart (100% eq)",    "Type":"Robo/Fund",      "Ret1Y":"~ 9%","Ret3Y":"~10%","Ret5Y":"~12%","Min":"S$1k",   "Risk":"Med-H","Access":"Endowus",    "Note":"Dimensional/Vanguard funds, CPF/SRS eligible"},
            {"Name":"StashAway 36% Risk",              "Type":"Robo",           "Ret1Y":"~ 8%","Ret3Y":"~ 9%","Ret5Y":"~11%","Min":"S$0",    "Risk":"Med",  "Access":"StashAway",  "Note":"ERAA risk-managed, SRS eligible"},
            {"Name":"POEMS Share Builders Plan",       "Type":"RSP (DCA)",      "Ret1Y":"~29%","Ret3Y":"~13%","Ret5Y":"~12%","Min":"S$100/m","Risk":"Med",  "Access":"Phillip",    "Note":"Monthly DCA into STI/blue chips"},
            {"Name":"Singapore Savings Bonds (SSB)",   "Type":"Capital-safe",   "Ret1Y":"~ 3%","Ret3Y":"~ 3%","Ret5Y":"~ 3%","Min":"S$500",  "Risk":"None", "Access":"DBS/OCBC",   "Note":"Govt-backed, flexible redemption"},
            {"Name":"T-bills 6-month",                 "Type":"Capital-safe",   "Ret1Y":"~3.7%","Ret3Y":"~3.5%","Ret5Y":"~3%","Min":"S$1k",  "Risk":"None", "Access":"SGX/Banks",  "Note":"Current yield ~3.7%, park idle cash"},
        ]
        show_fund_table(SG_FUNDS, "sg_funds_search")
        st.warning("⚠️ UCITS ETFs with 15-17% returns are heavily US-tech weighted. Can drop 40-50% in bear markets. "
                   "Only invest if you have a 5+ year horizon. Capital-safe options (SSB, T-bills) give 3-4% with zero risk.")

    # ─────────────────────────────────────────────────────────────────────────
    with lt_sub_us_funds:
        st.caption("🇺🇸 US-listed ETFs & funds · best for IBKR/Tiger users · note US estate tax above USD 60k")
        US_FUNDS = [
            # Core index
            {"Name":"Vanguard S&P 500 ETF (VOO)",      "Type":"US ETF",         "Ret1Y":"~10%","Ret3Y":"~12%","Ret5Y":"~15%","Min":"$1",    "Risk":"Med",  "Access":"IBKR/Tiger", "Note":"Lowest cost S&P 500, ER 0.03%"},
            {"Name":"Invesco Nasdaq-100 (QQQ)",         "Type":"US ETF",         "Ret1Y":"~11%","Ret3Y":"~14%","Ret5Y":"~18%","Min":"$1",    "Risk":"Med-H","Access":"IBKR/Tiger", "Note":"Top 100 Nasdaq stocks"},
            {"Name":"Vanguard Total Mkt (VTI)",         "Type":"US ETF",         "Ret1Y":"~ 9%","Ret3Y":"~11%","Ret5Y":"~14%","Min":"$1",    "Risk":"Med",  "Access":"IBKR/Tiger", "Note":"Entire US stock market"},
            # Quality/factor
            {"Name":"iShares MSCI USA Quality (QUAL)",  "Type":"US ETF",         "Ret1Y":"~ 9%","Ret3Y":"~12%","Ret5Y":"~15%","Min":"$1",    "Risk":"Med",  "Access":"IBKR",       "Note":"High ROE, stable earnings, low leverage"},
            {"Name":"VanEck Wide Moat (MOAT)",          "Type":"US ETF",         "Ret1Y":"~ 9%","Ret3Y":"~11%","Ret5Y":"~14%","Min":"$1",    "Risk":"Med",  "Access":"IBKR",       "Note":"Morningstar wide-moat stocks at fair value"},
            {"Name":"WisdomTree Div Growth (DGRW)",     "Type":"US ETF",         "Ret1Y":"~ 8%","Ret3Y":"~11%","Ret5Y":"~13%","Min":"$1",    "Risk":"Med",  "Access":"IBKR",       "Note":"Dividend growers, quality tilt"},
            # Sector
            {"Name":"iShares Semiconductor (SOXX)",     "Type":"US ETF",         "Ret1Y":"~ 8%","Ret3Y":"~16%","Ret5Y":"~22%","Min":"$1",    "Risk":"High", "Access":"IBKR/Tiger", "Note":"AI & chips — highest 5Y return, high vol"},
            {"Name":"Vanguard IT ETF (VGT)",            "Type":"US ETF",         "Ret1Y":"~12%","Ret3Y":"~16%","Ret5Y":"~19%","Min":"$1",    "Risk":"Med-H","Access":"IBKR/Tiger", "Note":"MSFT, AAPL, NVDA heavy"},
            {"Name":"iShares Software (IGV)",           "Type":"US ETF",         "Ret1Y":"~10%","Ret3Y":"~14%","Ret5Y":"~17%","Min":"$1",    "Risk":"Med-H","Access":"IBKR",       "Note":"Pure software — MSFT, ORCL, CRM, ADBE"},
            {"Name":"Global X Robotics & AI (BOTZ)",    "Type":"US ETF",         "Ret1Y":"~ 6%","Ret3Y":"~ 9%","Ret5Y":"~12%","Min":"$1",    "Risk":"High", "Access":"IBKR/Tiger", "Note":"Robotics, AI, automation thematic"},
            {"Name":"Global X Cloud (CLOU)",            "Type":"US ETF",         "Ret1Y":"~ 8%","Ret3Y":"~ 9%","Ret5Y":"~11%","Min":"$1",    "Risk":"Med-H","Access":"IBKR",       "Note":"Cloud computing companies"},
            {"Name":"First Trust Cybersecurity (CIBR)", "Type":"US ETF",         "Ret1Y":"~10%","Ret3Y":"~12%","Ret5Y":"~14%","Min":"$1",    "Risk":"Med-H","Access":"IBKR",       "Note":"Cybersecurity sector leader"},
            {"Name":"Global X US Infrastructure (PAVE)","Type":"US ETF",         "Ret1Y":"~12%","Ret3Y":"~13%","Ret5Y":"~15%","Min":"$1",    "Risk":"Med",  "Access":"IBKR",       "Note":"US infrastructure spend beneficiary"},
            # India
            {"Name":"iShares MSCI India (INDA)",        "Type":"US ETF",         "Ret1Y":"~ 9%","Ret3Y":"~10%","Ret5Y":"~12%","Min":"$1",    "Risk":"Med-H","Access":"IBKR/Tiger", "Note":"India large cap broad exposure"},
            {"Name":"iShares India Small Cap (SMIN)",   "Type":"US ETF",         "Ret1Y":"~10%","Ret3Y":"~12%","Ret5Y":"~15%","Min":"$1",    "Risk":"High", "Access":"IBKR",       "Note":"India small cap premium, high growth"},
            # Funds
            {"Name":"Fidelity Contrafund (FCNTX)",      "Type":"US Mutual Fund", "Ret1Y":"~10%","Ret3Y":"~12%","Ret5Y":"~14%","Min":"$2.5k", "Risk":"Med-H","Access":"Fidelity",   "Note":"Active large-growth fund, long track record"},
            {"Name":"T. Rowe Price Growth (PRGFX)",     "Type":"US Mutual Fund", "Ret1Y":"~11%","Ret3Y":"~13%","Ret5Y":"~16%","Min":"$2.5k", "Risk":"Med-H","Access":"TRowe",      "Note":"Active large-growth, tech overweight"},
        ]
        show_fund_table(US_FUNDS, "us_funds_search")
        st.warning("⚠️ US-listed ETFs carry US estate tax risk for non-US persons above USD 60k total. "
                   "Consider Irish-domiciled UCITS equivalents (CSPX.L, VUAA.L, XNAS.L) in the 🇸🇬 SG Funds tab instead. "
                   "Not financial advice.")

with tab_diag:
    st.caption("🔍 Diagnostics")

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

# ─────────────────────────────────────────────────────────────────────────────
# TAB — ACCURACY LAB / WALK-FORWARD BACKTEST
# Keeps the scanner logic unchanged. This tab only validates past signal quality.
# ─────────────────────────────────────────────────────────────────────────────
with tab_backtest:
    st.caption("🧪 Accuracy Lab · walk-forward check of current swing signal quality")
    st.info(
        "This tab does not change BUY/SELL logic. It replays historical candles, "
        "runs the same signal engine, and checks forward returns after 5/10/15 days. "
        "Use it to verify real hit rate instead of trusting displayed probability alone."
    )

    bt_cols = st.columns([3, 1, 1, 1])
    with bt_cols[0]:
        bt_tickers_txt = st.text_input(
            "Tickers to test",
            value=", ".join(_active_tickers[:6]),
            key="bt_tickers",
            placeholder="D05.SI, O39.SI, AIY.SI"
        )
    with bt_cols[1]:
        bt_horizon = st.selectbox("Horizon", [5, 10, 15], index=1, key="bt_horizon")
    with bt_cols[2]:
        bt_period = st.selectbox("History", ["1y", "2y", "3y"], index=1, key="bt_period")
    with bt_cols[3]:
        bt_mode = st.selectbox("Signal", ["BUY/SELL", "High Prob Only"], index=0, key="bt_mode")

    def _bt_flatten(df: pd.DataFrame) -> pd.DataFrame:
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df.ffill().dropna()

    def _bt_pct(x):
        try:
            return float(str(x).replace("%", ""))
        except Exception:
            return np.nan

    def _quick_signal_backtest(ticker: str, horizon: int = 10, period: str = "2y", mode: str = "BUY/SELL") -> dict:
        """Backtest the current signal engine without changing live scanner behaviour."""
        try:
            raw = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=True)
            df = _bt_flatten(raw)
            if df.empty or len(df) < 260:
                return {"Ticker": ticker, "Samples": 0, "Long Win %": "–", "Short Win %": "–", "Note": "Not enough history"}

            closes = df["Close"].ffill().dropna()
            highs  = df["High"].ffill().dropna()
            lows   = df["Low"].ffill().dropna()
            vols   = df["Volume"].ffill().dropna()

            long_trades = long_wins = short_trades = short_wins = 0
            long_rets, short_rets = [], []

            # Step by 3 bars to keep UI responsive and reduce overlapping samples.
            for end in range(220, len(closes) - horizon, 3):
                c = closes.iloc[:end]
                h = highs.iloc[:end]
                l = lows.iloc[:end]
                v = vols.iloc[:end]
                try:
                    long_sig, short_sig, rv = compute_all_signals(c, h, l, v)
                except Exception:
                    continue

                p_now = float(c.iloc[-1])
                p_fut = float(closes.iloc[end + horizon])
                if p_now <= 0 or np.isnan(p_now) or np.isnan(p_fut):
                    continue

                fwd_ret = (p_fut / p_now - 1) * 100
                l_score = sum(1 for x in long_sig.values() if x)
                s_score = sum(1 for x in short_sig.values() if x)
                l_prob = bayesian_prob(LONG_WEIGHTS, long_sig, 0)
                s_prob = bayesian_prob(SHORT_WEIGHTS, short_sig, 0)

                # Keep this tab separate from live scanner logic. These gates mirror the current
                # scanner intent: probability + score + core trend/volume confirmation.
                long_gate = (l_prob >= 0.72 and l_score >= 6)
                short_gate = (s_prob >= 0.68 and s_score >= 4)

                if mode == "High Prob Only":
                    long_gate = long_gate and l_prob >= 0.82
                    short_gate = short_gate and s_prob >= 0.82

                # Simple safety checks for historical test only, to avoid counting junk bars.
                dollar_vol_20d = float((c.tail(20) * v.tail(20)).mean()) if len(c) >= 20 else 0
                if ticker.endswith(".SI"):
                    liq_ok = dollar_vol_20d >= 250_000
                elif ticker.endswith(".NS"):
                    liq_ok = dollar_vol_20d >= 1_000_000
                else:
                    liq_ok = dollar_vol_20d >= 3_000_000

                if not liq_ok:
                    continue

                if long_gate:
                    long_trades += 1
                    long_wins += int(fwd_ret > 0)
                    long_rets.append(fwd_ret)
                if short_gate:
                    short_trades += 1
                    short_wins += int(fwd_ret < 0)
                    short_rets.append(-fwd_ret)

            return {
                "Ticker": ticker,
                "Samples": int(long_trades + short_trades),
                "Long Trades": int(long_trades),
                "Long Win %": f"{(long_wins / long_trades * 100):.1f}%" if long_trades else "–",
                "Long Avg %": f"{np.mean(long_rets):.2f}%" if long_rets else "–",
                "Short Trades": int(short_trades),
                "Short Win %": f"{(short_wins / short_trades * 100):.1f}%" if short_trades else "–",
                "Short Avg %": f"{np.mean(short_rets):.2f}%" if short_rets else "–",
                "Note": "OK" if (long_trades + short_trades) else "No signal samples"
            }
        except Exception as e:
            return {"Ticker": ticker, "Samples": 0, "Long Win %": "–", "Short Win %": "–", "Note": str(e)[:80]}

    if st.button("🧪 Run Accuracy Backtest", type="primary", key="run_accuracy_lab"):
        bt_tickers = [t.strip().upper() for t in bt_tickers_txt.split(",") if t.strip()]
        rows = []
        prog = st.progress(0)
        msg = st.empty()
        max_n = min(len(bt_tickers), 20)
        for i, t in enumerate(bt_tickers[:20]):
            msg.caption(f"Backtesting {t} ({i+1}/{max_n})…")
            rows.append(_quick_signal_backtest(t, bt_horizon, bt_period, bt_mode))
            prog.progress((i + 1) / max_n)
        prog.empty(); msg.empty()

        df_bt = pd.DataFrame(rows)
        st.dataframe(
            df_bt,
            width="stretch",
            hide_index=True,
            column_config={
                "Ticker": st.column_config.TextColumn("Ticker", width=80),
                "Samples": st.column_config.NumberColumn("Samples", width=70),
                "Long Trades": st.column_config.NumberColumn("Long", width=60),
                "Long Win %": st.column_config.TextColumn("Long Win", width=80),
                "Long Avg %": st.column_config.TextColumn("Long Avg", width=80),
                "Short Trades": st.column_config.NumberColumn("Short", width=60),
                "Short Win %": st.column_config.TextColumn("Short Win", width=80),
                "Short Avg %": st.column_config.TextColumn("Short Avg", width=80),
                "Note": st.column_config.TextColumn("Note", width=180),
            }
        )
        st.caption(
            "Read this with sample count. A 90% win rate on 5 samples is weaker evidence than "
            "65–70% on 50+ samples. Past performance is not a guarantee."
        )


    st.info(
        "ML was removed because the simple model did not improve AUC over the "
        "bucket-capped Bayesian engine. The live scanner now uses Bayesian as "
        "the base signal and ranks candidates with an ensemble score: Bayesian "
        "+ operator activity + news/orders + sector strength - earnings/trap risk."
    )

    st.markdown(
        """
**New validation target for swing trading:** a setup is considered a useful winner only if it reaches a profit target before hitting a stop.

Default label used for manual validation:

```text
Winner = next 10 trading days hits +6% before -4% stop
Loser  = -4% stop hits first, or +6% is never reached
```

This is more realistic than the old binary label: `price is higher after N days`. Use this section as the rule for judging the scanner, not the removed simple ML AUC.
        """
    )

    st.caption(
        "Live ranking columns are visible in 🎯 Swing Picks: Bayes Score, Operator Score, "
        "News Score, Sector Score, Earnings Risk, Trap Risk and Final Swing Score."
    )

# ─────────────────────────────────────────────────────────────────────────────
# TAB 8 — HELP
# ─────────────────────────────────────────────────────────────────────────────
with tab_help:
    st.markdown("## ❓ How to Use the Swing/Long Term Scanner v13.14")
    st.caption(
        "Latest guide: fixed bucket-capped Bayesian scoring, Bayesian ensemble ranking, optional Strategy Lab ML filter, "
        "Yahoo/live + existing ticker universe, operator/smart-money activity, earnings/news "
        "risk checks, Swing Picks, Long Term combined universe, Diagnostics scanned ticker list, "
        "and compact searchable grids. Old simple ML and calibration tools have been removed; Strategy Lab adds optional LightGBM/sklearn quality filtering only when it beats the Bayesian baseline."
    )

    # ── VERSION SUMMARY ─────────────────────────────────────────────────────
    with st.expander("🆕 What changed in the latest version", expanded=True):
        st.markdown("""
### Current engine
The scanner now uses a simpler and more stable ranking stack:

```text
Fixed Bayesian signal weights
+ bucket-cap to reduce double-counting correlated signals
+ operator / smart-money confirmation
+ news and order/contract catalyst score
+ sector strength
- earnings risk
- trap risk such as false breakout, gap chase, distribution
```
        """)

# ── QUICK START ─────────────────────────────────────────────────────────
    with st.expander("🚀 Quick Start — what to do first"):
        st.markdown("""
1. Pick the market at the top: **US**, **SGX**, or **India**.
2. Turn on **Use live market universe** if you want Yahoo/live movers added to the existing list.
3. Keep **Always include tickers** for names you never want excluded, for example `UUUU, APP`.
4. Click **🚀 Scan**.
5. Start with **🎯 Swing Picks** for the final ranked shortlist.
6. Open **🔬 Stock Analysis** before entry to check support, resistance, stop, and chart context.

For normal swing trading, use this flow:

```text
Sector Heatmap → Long Setups → Swing Picks → Stock Analysis → Earnings / News check → Entry decision
```
        """)

    # ── TAB GUIDE ───────────────────────────────────────────────────────────
    with st.expander("🧭 Tab guide — latest tabs explained"):
        st.markdown("""
| Tab | Use it for | Latest behavior |
|---|---|---|
| 🗂️ **Sector Heatmap** | Check strongest / weakest sectors first | US uses sector ETFs; SGX uses stock-group averages; India uses NSE sector indices |
| 📈 **Long Setups** | Bullish swing candidates | Uses fixed Bayesian bucket-capped probability + operator/VWAP/trap columns |
| 🎯 **Swing Picks** | Final actionable shortlist | Ranks Long Setups using Final Swing Score: Bayes + operator + news + sector - earnings/trap risk |
| 📉 **Short Setups** | Bearish / breakdown candidates | Best suited to US market; SGX/India shorting may be limited by broker/product access |
| 🪤 **Operator Activity** | Smart-money / manipulation footprint scan | Uses actual scanned universe; live mode includes Yahoo/live + existing tickers |
| 🔄 **Side by Side** | Compare long and short ideas | Useful for spotting conflict, sector concentration, or weak market breadth |
| 📊 **ETF Holdings** | Add ETF constituents to scan universe | Mainly useful for US ETFs and thematic/sector lists |
| 🔬 **Stock Analysis** | Deep dive for one ticker | Shows chart, indicators, support/stop/target style analysis |
| 📅 **Earnings** | Earnings date and earnings-risk review | Helps avoid fresh swing buys just before earnings |
| 📰 **Event Predictor** | News / event catalyst scan | Uses news headlines, sentiment, order/contract/catalyst keywords where available |
| 🌱 **Long Term** | 1–3 year stock/fund ideas | Uses existing tickers + ETF tickers + ETF holdings + Yahoo/live tickers |
| 🔍 **Diagnostics** | Debug and verify scan logic | Shows market, universe source, counts, and comma-separated scanned ticker list |
| 🧪 **Accuracy Lab** | Backtest / validation notes | Quick walk-forward validation of signal behavior and swing-target logic |
| 🧠 **Strategy Lab** | Optional ML quality filter | Trains LightGBM/sklearn model on +6% before -4% target; use only if it beats baseline |
| ❓ **Help** | This guide | Updated for latest tabs and changes |
        """)

    # ── UNIVERSE ────────────────────────────────────────────────────────────
    with st.expander("🌍 Ticker universe — what gets scanned"):
        st.markdown("""
### Swing scan universe
When **Use live market universe** is OFF:

```text
Existing curated tickers + extra tickers + always-include tickers
```

When **Use live market universe** is ON:

```text
Yahoo/live tickers + current/index/live sources + existing curated tickers + extra tickers + always-include tickers
```

This means tickers already in your existing lists, such as **UUUU** and **APP**, should remain included even if Yahoo movers do not return them that day.

### Max live stocks to scan
This is a **cap**, not a guaranteed number. If Yahoo/live sources return only 274 unique names, and existing list overlap reduces duplicates, the final count may be below 1000.

### Long Term universe
The **🌱 Long Term** tab has its own combined universe:

```text
Existing tickers + ETF tickers + ETF holdings + Yahoo/live tickers
```

### Diagnostics check
Use **🔍 Diagnostics** after a scan to confirm:
- total scanned count
- live ticker count
- existing ticker count
- universe source
- exact comma-separated ticker list
        """)

    # ── BAYESIAN ENGINE ─────────────────────────────────────────────────────
    with st.expander("🧠 Scoring engine — Bayesian bucket-cap + ensemble ranking"):
        st.markdown("""
### 1. Bayesian probability
The scanner uses fixed signal weights from the code. Examples:
- volume breakout
- volume surge up
- pocket pivot
- trend daily
- weekly trend
- OBV rising
- strong close
- VWAP support
- relative strength
- options signals where available

### 2. Bucket-cap
Many signals overlap. For example:

```text
trend_daily + weekly_trend + full_ma_stack + near_52w_high
```

All of these partly measure trend. Bucket-cap reduces double-counting by allowing the strongest signal in a bucket to count most, and later signals in the same bucket count less.

### 3. Final Swing Score
The **🎯 Swing Picks** tab does not rely only on Rise Prob. It ranks using:

```text
Bayes Score
+ Operator Score
+ News Score
+ Sector Score
- Earnings Risk
- Trap Risk Score
= Final Swing Score
```

This is better for practical swing trading because a high-probability technical setup can still be bad if earnings are tomorrow, news is negative, or the move is a gap-chase trap.
        """)

    # ── SWING PICKS ─────────────────────────────────────────────────────────
    with st.expander("🎯 Swing Picks tab — how to read it"):
        st.markdown("""
The **Swing Picks** tab is the main shortlist tab.

It starts from the latest **Long Setups** scan and enriches each ticker with:
- **Bayes Score** — technical probability score
- **Operator Score** — smart-money / accumulation footprint
- **News Score** — recent catalyst/headline strength
- **Sector Score** — sector tailwind
- **Earnings Risk** — penalty for nearby earnings or event risk
- **Trap Risk Score** — penalty for false breakout, gap chase, or distribution risk
- **Final Swing Score** — final ranking score

### Verdicts
| Verdict | Meaning |
|---|---|
| ✅ **BUY / WATCH ENTRY** | Strong setup, but still wait for good entry and risk/reward |
| 👀 **WATCH** | Good candidate but needs confirmation or pullback |
| ⏳ **WAIT** | Mixed setup, earnings risk, or not enough confirmation |
| 🚫 **AVOID** | Weak setup, trap risk, or event risk too high |

### Best use
Do not blindly buy the top row. Prefer:

```text
High Final Swing Score
+ operator accumulation
+ no false breakout / gap chase
+ earnings not too close
+ clear stop below support
```
        """)

    # ── OPERATOR ────────────────────────────────────────────────────────────
    with st.expander("🪤 Operator / smart-money activity"):
        st.markdown("""
Operator activity is a confirmation layer, not a standalone buy signal.

The scanner looks for footprints such as:
- high volume with green candle
- strong close near day high
- OBV rising
- price holding above VWAP
- breakout with volume
- absorption: red/high-volume day but price closes off lows

### Operator labels
| Label | Meaning |
|---|---|
| 🔥 **STRONG OPERATOR** | Strong accumulation footprint |
| 🟢 **ACCUMULATION** | Good smart-money signs |
| 🟡 **WEAK SIGNS** | Some signs but not enough |
| ⚪ **NONE** | No clear operator activity |

### Trap labels
| Trap | Meaning |
|---|---|
| **FALSE BO** | Breakout attempt with weak close |
| **GAP CHASE** | Big move with high volume; avoid chasing |
| **DISTRIB** | High volume but poor price progress / weak close |
        """)

    # ── EARNINGS / NEWS ─────────────────────────────────────────────────────
    with st.expander("📅 Earnings and 📰 News / Event filters"):
        st.markdown("""
### Earnings guard
The scanner avoids treating a stock as a normal swing buy when earnings are very close. Earnings can create overnight gaps that ignore technical stops.

General rule:

```text
If earnings are within the next 7 days → reduce size, wait, or treat as event trade only
```

### News / event scoring
News and event features look for positive or negative catalyst clues such as:
- earnings beat / guidance raise
- contracts / orders / partnerships
- analyst upgrades / downgrades
- regulatory or legal risks
- offering / dilution / investigation headlines

News score improves ranking only when it supports the technical setup. Negative or risky news should reduce confidence.
        """)

    # ── LONG / SHORT LOGIC ──────────────────────────────────────────────────
    with st.expander("📈 Long Setups and 📉 Short Setups — signal logic"):
        st.markdown("""
### Long Setups
Important long signals include:
- price > EMA8 > EMA21
- weekly trend confirmation
- volume breakout near 10-day high
- pocket pivot / volume surge up
- MACD acceleration
- Stoch RSI confirmation
- OBV rising
- strong close
- VWAP support
- VCP tightness
- relative strength vs SPY / sector

### Short Setups
Important short signals include:
- price < EMA8 < EMA21
- high-volume down candle
- 10-day breakdown
- lower highs
- MACD deceleration / bearish cross
- below VWAP
- operator distribution
- MA60 stop break

### Entry quality
Use **BUY / WATCH / WAIT / AVOID** as a filter, not a command. Always confirm support, resistance, market regime, and stop level.
        """)

    # ── LONG TERM ───────────────────────────────────────────────────────────
    with st.expander("🌱 Long Term tab — latest behavior"):
        st.markdown("""
The Long Term tab is separate from swing trading. It is designed for 1–3 year ideas and portfolio building.

### Current Long Term universe
```text
Existing tickers + ETF tickers + ETF holdings + Yahoo/live tickers
```

### Sub-tabs
| Sub-tab | Use it for |
|---|---|
| 🇺🇸 **US Stocks** | Long-term US stock candidates from combined universe |
| 🇸🇬 **SG Stocks** | Singapore long-term stock candidates |
| 🇸🇬 **SG Funds & ETFs** | Singapore-friendly fund / ETF options |
| 🇺🇸 **US Funds & ETFs** | US-listed ETFs/funds with tax-risk warning |

### Long-term score considers
- revenue growth
- EPS growth
- ROE / margins
- debt level
- dividend yield
- MA200 trend
- analyst target upside
- analyst recommendation

The **Exp 1Y Return** is an estimate, not a guarantee. Dividend values are normalised/capped to avoid unrealistic yfinance dividend anomalies.
        """)

    # ── ACCURACY LAB ────────────────────────────────────────────────────────
    with st.expander("🧪 Accuracy Lab — current role"):
        st.markdown("""
The old ML and signal calibration controls have been removed.

The preferred validation idea is now the practical swing target:

```text
Winner = price hits +6% before hitting -4% stop within 10 trading days
Loser  = -4% stop hits first, or +6% is never reached
```

This is more useful than simply asking whether the close is higher after N days.

For daily use, rely on:

```text
Fixed Bayesian weights + bucket-cap + Final Swing Score
```
        """)

    # ── COLUMNS ─────────────────────────────────────────────────────────────
    with st.expander("🔎 Important columns explained"):
        st.markdown("""
| Column | Meaning |
|---|---|
| **Rise Prob / Fall Prob** | Bucket-capped Bayesian probability from active signals |
| **Score** | Count of active long/short signals |
| **Bayes Score** | Probability converted into ranking contribution |
| **Final Swing Score** | Ensemble score used in Swing Picks ranking |
| **Operator** | Operator/smart-money label |
| **Op Score / Operator Score** | Numeric smart-money accumulation score |
| **VWAP** | Whether price is above/below VWAP confirmation |
| **Trap Risk** | FALSE BO, GAP CHASE, DISTRIB, or none |
| **Trap Risk Score** | Penalty used in Final Swing Score |
| **News Score** | Catalyst/news contribution |
| **Sector Score** | Sector tailwind contribution |
| **Earnings Risk** | Penalty for upcoming earnings/event risk |
| **MA60 Stop** | Trend stop area around 60-day moving average |
| **TP1 / TP2 / TP3** | Example upside targets; not guaranteed |
| **Sources** | Long Term source: Existing, ETF, ETF holding, Yahoo/live, etc. |
        """)

    # ── PRACTICAL RULES ─────────────────────────────────────────────────────
    with st.expander("✅ Practical trading rules"):
        st.markdown("""
For cleaner swing trades, prefer:

```text
Final Swing Score high
+ Rise Prob high
+ Operator Score >= 4
+ price above VWAP
+ no Trap Risk
+ earnings not within 7 days
+ strong sector
```

Avoid or reduce size when:

```text
Gap chase
False breakout
Distribution label
Earnings very close
Very wide spread / low liquidity
Market regime is BEAR or VIX is high
```

Suggested risk framework:
- Risk small per trade.
- Put stop below support or MA60 stop area.
- Do not average down blindly.
- Take partial profit near TP1 if move is fast.
- For SGX names, use limit orders due to wider spreads.
        """)

    # ── INSTALL ─────────────────────────────────────────────────────────────
    with st.expander("🔧 Install & run"):
        st.markdown("""
```bash
pip install streamlit yfinance pandas numpy ta financedatabase plotly nsepython requests
python -m streamlit run swing_trader_sector_wise_yfin_simple.py
```

If data fetch fails:

```bash
pip install --upgrade yfinance nsepython requests
streamlit cache clear
```

Main packages:
- `streamlit` — app UI
- `yfinance` — prices, fundamentals, earnings, options where available
- `pandas`, `numpy` — data processing
- `ta` — technical indicators
- `financedatabase` — optional ETF/sector data
- `nsepython` — optional India F&O option chains
- `requests` — Yahoo/live universe and web data helpers
- `plotly` — charts where used
        """)

    # ── GLOSSARY ────────────────────────────────────────────────────────────
    with st.expander("📖 Glossary"):
        st.markdown("""
| Term | Meaning |
|---|---|
| **EMA8 / EMA21** | Short-term exponential moving averages |
| **MA50 / MA200** | Medium/long-term moving averages |
| **Golden Cross** | EMA50 crossing above EMA200 |
| **RSI** | Momentum oscillator; >70 overbought, <30 oversold |
| **Stoch RSI** | Faster RSI-based momentum signal |
| **MACD** | Momentum/trend indicator; histogram shows acceleration/deceleration |
| **Bollinger Squeeze** | Volatility compression before possible expansion |
| **ATR** | Average True Range; used for volatility and stops |
| **OBV** | On-Balance Volume; accumulation/distribution clue |
| **VWAP** | Volume-weighted average price; intraday/institutional control clue |
| **VCP** | Volatility contraction pattern |
| **RS>SPY** | Stock outperforming SPY over recent days |
| **Bucket-cap** | Reduces double-counting of overlapping signals |
| **Operator Score** | Smart-money/accumulation footprint score |
| **Trap Risk** | Warning for false breakout, gap chase, or distribution |
| **Final Swing Score** | Ensemble ranking score in Swing Picks |
| **MA60 Stop** | Trend stop around the 60-day moving average |
| **Exp 1Y Return** | Estimated price return plus estimated dividend return |
        """)

    # ── RISK WARNINGS ───────────────────────────────────────────────────────
    with st.expander("⚠️ Risk warnings — read before trading"):
        st.warning("""
This tool does not provide financial advice. All outputs are estimates and signals only.

1. Probability is not certainty. A 75% probability can still fail.
2. Earnings risk is high. Stocks can gap sharply overnight.
3. News can change quickly. Always check latest headlines before entry.
4. SGX liquidity is lower. Use limit orders; spreads can be wide.
5. Short selling risk is high. Losses can exceed initial capital if unmanaged.
6. Sector concentration matters. Many picks from one sector can fail together.
7. Currency risk matters for USD, SGD, INR, JPY, GBP, and EUR assets.
8. Model assumptions can be wrong. Always check support/resistance and risk tolerance.
        """)

    st.markdown("---")
    st.caption("Swing/Long Term Scanner v13.12 · Fixed Bayesian bucket-cap + ensemble ranking · US + SGX + India · Not financial advice · Created by Ripin")
