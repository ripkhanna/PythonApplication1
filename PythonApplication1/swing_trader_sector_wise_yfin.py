"""
Swing Scanner v9 — Sector-Driven Long & Short
================================================
Architecture : v7  (batch download, sector heatmap, FD holdings, fast scan)
Signal logic : v5  (exact compute_all_signals, bayesian_prob, action tiers)
Accuracy     : improved (weekly trend, earnings guard, regime-adjusted thresholds)

Install:
  pip install financedatabase ta streamlit yfinance pandas numpy
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
st.set_page_config(page_title="Swing Scanner v9", layout="wide")
st.title("5–7 Day Swing Scanner v9 — Sector-Driven Long & Short")
st.markdown(
    "🟢 Green sectors → best **long** candidates · "
    "🔴 Red sectors → best **short** candidates · "
    "v9 signal accuracy"
)

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
    # ── INDIA NSE (yfinance suffix: .NS) ─────────────────────────────────────
    # Nifty 50 Blue Chips — Large-cap, high liquidity
    "RELIANCE.NS",    # Reliance Industries — conglomerate, energy + retail + Jio
    "TCS.NS",         # Tata Consultancy Services — IT services
    "INFY.NS",        # Infosys — IT services
    "HDFCBANK.NS",    # HDFC Bank — largest private bank
    "ICICIBANK.NS",   # ICICI Bank — private bank, high beta
    "SBIN.NS",        # State Bank of India — largest PSU bank
    "AXISBANK.NS",    # Axis Bank — private bank
    "WIPRO.NS",       # Wipro — IT services
    "BAJFINANCE.NS",  # Bajaj Finance — NBFC, high beta financial
    "MARUTI.NS",      # Maruti Suzuki — auto, cyclical
    "HCLTECH.NS",     # HCL Technologies — IT services
    "TECHM.NS",       # Tech Mahindra — IT services
    "LTIM.NS",        # LTIMindtree — IT services mid-cap
    "SUNPHARMA.NS",   # Sun Pharma — pharma large-cap
    "DRREDDY.NS",     # Dr Reddy's — pharma
    "CIPLA.NS",       # Cipla — pharma
    "TATAMOTORS.NS",  # Tata Motors — auto + JLR + EV high beta
    "TATASTEEL.NS",   # Tata Steel — metal cyclical
    # High-beta / Adani group
    "ADANIENT.NS",    # Adani Enterprises — beta ~1.95, infrastructure
    "ADANIPORTS.NS",  # Adani Ports — logistics
    "ADANIGREEN.NS",  # Adani Green Energy — renewable, very high beta
    "ADANIPOWER.NS",  # Adani Power — energy
    # Metals / Commodities
    "VEDL.NS",        # Vedanta — diversified metals, beta ~1.82
    "HINDALCO.NS",    # Hindalco — aluminium + Novelis
    "JSWSTEEL.NS",    # JSW Steel — steel, global beta
    "NMDC.NS",        # NMDC — iron ore mining
    "HINDZINC.NS",    # Hindustan Zinc — zinc/silver
    "COALINDIA.NS",   # Coal India — energy commodity
    # New-age Tech / Fintech
    "ZOMATO.NS",      # Zomato (Eternal) — food delivery, high beta growth
    "PAYTM.NS",       # Paytm (One97) — fintech, volatile
    "NYKAA.NS",       # Nykaa (FSN) — beauty commerce
    "DELHIVERY.NS",   # Delhivery — logistics tech
    "POLICYBZR.NS",   # PB Fintech (PolicyBazaar) — insurtech
    # Defence / PSU
    "HAL.NS",         # Hindustan Aeronautics — defence, strong momentum
    "BEL.NS",         # Bharat Electronics — defence electronics
    "COCHINSHIP.NS",  # Cochin Shipyard — defence shipbuilding
    "RVNL.NS",        # Rail Vikas Nigam — railway infra, high beta
    "IRFC.NS",        # Indian Railway Finance Corp — PSU
    "HUDCO.NS",       # Housing & Urban Dev Corp — PSU infra
    "NBCC.NS",        # NBCC India — govt construction
    # Renewable Energy
    "TATAPOWER.NS",   # Tata Power — renewable energy transition
    "SUZLON.NS",      # Suzlon Energy — wind, very high beta
    "INOXWIND.NS",    # Inox Wind — wind energy, beta ~2.2
    # Banking / Finance
    "INDUSINDBK.NS",  # IndusInd Bank — private bank, high beta
    "KOTAKBANK.NS",   # Kotak Mahindra Bank
    "PNB.NS",         # Punjab National Bank — PSU bank
    "BANKBARODA.NS",  # Bank of Baroda — PSU bank
    "HDFCAMC.NS",     # HDFC AMC — asset manager, market beta play
    # Mid / Small-cap high beta
    "IRCTC.NS",       # IRCTC — railway monopoly, retail favourite
    "BSESMD.NS",      # BSE Ltd — stock exchange, high beta
    "DIXON.NS",       # Dixon Technologies — electronics manufacturing (PLI)
    "AMBER.NS",       # Amber Enterprises — AC components
    "KAYNES.NS",      # Kaynes Technology — EMS / IoT
    "GRAVITA.NS",     # Gravita India — recycling, beta ~2.2
    "PGEL.NS",        # PG Electroplast — EMS, beta ~2.2
    # Indices for regime reference
    # "^NSEI",        # Nifty 50 index (comment out — not tradeable)
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
    # Original v5 signals
    "stoch_confirmed": 0.71, "bb_bull_squeeze": 0.69, "macd_accel":  0.67,
    "vol_breakout":    0.66, "trend_daily":     0.63, "higher_lows": 0.63,
    "macd_cross":      0.60, "adx":             0.58, "volume":      0.56,
    "rsi_confirmed":   0.59,
    # New next-day accuracy signals
    "weekly_trend":    0.65,   # weekly EMA20 > EMA50 — prevents buying in weekly downtrend
    "golden_cross":    0.65,   # EMA50 > EMA200 — long-term trend aligned
    "rel_strength":    0.64,   # stock outperforming SPY last 5 days
    "near_52w_high":   0.63,   # price within 10% of 52W high — momentum continuation
    "obv_rising":      0.62,   # OBV rising 5 days — institutional accumulation
    "bull_candle":     0.64,   # hammer / bullish engulfing on last candle
    "atr_expansion":   0.61,   # today's range > 1.2× ATR — breakout day
    "consolidation":   0.62,   # 3–8 days tight range before move
    "rsi_divergence":  0.63,   # price lower low but RSI higher low
    "sector_leader":   0.62,   # stock outperforming its sector ETF 5d
}
SHORT_WEIGHTS = {
    "stoch_overbought": 0.70, "bb_bear_squeeze": 0.68, "macd_decel":     0.66,
    "vol_breakdown":    0.65, "trend_bearish":   0.63, "lower_highs":    0.62,
    "macd_cross_bear":  0.60, "adx_bear":        0.57, "rsi_cross_bear": 0.59,
    "high_volume_down": 0.64,
}
BASE_RATE = 0.50

# ─────────────────────────────────────────────────────────────────────────────
# FinanceDatabase
# ─────────────────────────────────────────────────────────────────────────────
try:
    import financedatabase as fd
    _fd_available = True
except ImportError:
    _fd_available = False

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


def bayesian_prob(weights_dict, active_signals, bonus=0.0):
    """Exact v5 Bayesian probability engine."""
    p = BASE_RATE
    for key, active in active_signals.items():
        if active and key in weights_dict:
            w   = weights_dict[key]
            num = p * (w / BASE_RATE)
            den = num + (1 - p) * ((1 - w) / (1 - BASE_RATE))
            p   = num / den
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

    search = st.text_input(
        f"🔎 Search {label}",
        key=f"search_{label}"
    )

    if search:
        search = search.lower()

        mask = df.astype(str).apply(
            lambda col: col.str.lower().str.contains(search, na=False)
        )

        df = df[mask.any(axis=1)]

    return df

def show_table(df, label, prob_col="Rise Prob"):

    if df.empty:
        st.info(f"No {label} setups.")
        return

    # ✅ SEARCH ENABLED FOR ALL GRIDS
    df = grid_search_filter(df, label)

    styler   = df.style
    style_fn = styler.map if hasattr(styler, "map") else styler.applymap
    fn = style_short_prob if prob_col == "Fall Prob" else style_prob

    st.dataframe(
        style_fn(fn, subset=[prob_col]),
        use_container_width=True
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

        # Flatten MultiIndex (yfinance ≥0.2.x returns MultiIndex columns)
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
        st.warning(f"⚠️ Market regime fetch failed: {e}. Try: pip install --upgrade yfinance")
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
LONG_WEIGHTS.update({
    "vcp_tightness":   0.68,   # [NEW] ATR 5/20 < 0.85 — breakout ready
    "strong_close":    0.65,   # [NEW] Close in top 25% of daily range
    "rs_momentum":     0.67,   # [NEW] Relative Strength line is trending up (20d)
    "weekly_trend":    0.72,   # [WEIGHT INCREASED]
})
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

    # ── Weekly trend (using daily data, last 10 weeks = 50 bars) ─────────────
    weekly_ema20 = to_float(ta.trend.ema_indicator(close, window=20).iloc[-1])  # proxy for weekly EMA4
    weekly_ema50 = to_float(ta.trend.ema_indicator(close, window=50).iloc[-1])  # proxy for weekly EMA10
    weekly_trend_ok = (p > weekly_ema20) and (weekly_ema20 > weekly_ema50)

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

    # ── LONG signals ─────────────────────────────────────────────────────────
    long_signals = {
        # Original v5
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
        # New next-day accuracy signals
        "weekly_trend":    weekly_trend_ok,
        "golden_cross":    gc_now,
        "rel_strength":    rel_strength,
        "near_52w_high":   (p >= high_252 * 0.90),
        "obv_rising":      obv_rising,
        "bull_candle":     bull_candle,
        "atr_expansion":   atr_expansion,
        "consolidation":   consolidation,
        "rsi_divergence":  rsi_div,
        "sector_leader":   sector_leader,
        "vcp_tightness":   vcp_tightness,
        "strong_close":    strong_close,
        "rs_momentum":     rs_momentum,
        "weekly_trend":    weekly_trend_ok,
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
        "vol_breakdown":    (p <= l10 * 1.005) and (vr >= 1.8),
        "lower_highs":      lower_highs,
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
    }
    return long_signals, short_signals, raw


# ─────────────────────────────────────────────────────────────────────────────
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
# MAIN SCANNER  — v5 signal logic + v7 batch OHLCV pre-fetch
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def fetch_analysis(green_sectors, red_sectors, regime,
                   skip_earnings, top_n_sectors, live_sectors=None,
                   market_tickers=None):
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
        return pd.DataFrame(), pd.DataFrame()

    green_set = set(green_sectors[:top_n_sectors])
    red_set   = set(red_sectors[:top_n_sectors])

    def sector_label(ticker):
        sec = sector_membership.get(ticker, "")
        if sec in green_set:  return f"🟢 {sec}"
        if sec in red_set:    return f"🔴 {sec}"
        return f"⚪ {sec}" if sec else "⚪ Mixed"

    long_results  = []
    short_results = []
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

    # ── Regime thresholds ─────────────────────────────────────────────────────
    min_score_strong_long  = 6 if regime == "BULL"               else 7
    min_prob_strong_long   = 0.72 if regime == "BULL"            else 0.78
    min_score_strong_short = 5 if regime in ("BEAR", "CAUTION")  else 6
    min_prob_strong_short  = 0.68 if regime in ("BEAR", "CAUTION") else 0.72

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
                            if 0 <= days_out <= 14:   # extended to 14 days
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
            l_top3        = (long_sig["stoch_confirmed"] or
                             long_sig["bb_bull_squeeze"]  or
                             long_sig["macd_accel"])

            if l_score >= min_score_strong_long and l_prob >= min_prob_strong_long and l_top3:
                l_action = "STRONG BUY"
            elif l_score >= 4 and l_prob >= 0.62 and long_sig["trend_daily"]:
                l_action = "WATCH – HIGH QUALITY"
            elif l_score >= 3 and long_sig["trend_daily"]:
                l_action = "WATCH – DEVELOPING"
            else:
                l_action = None

            if l_action:
                l_atr_stop   = round(p - 1.5 * atrv, 2)
                l_swing_stop = round(raw["last_swing_low"] * 0.995, 2)
                l_stop       = max(l_atr_stop, l_swing_stop)
                l_risk       = p - l_stop
                l_t1         = round(p + l_risk * 1.0, 2)
                l_t2         = round(p + l_risk * 2.0, 2)
                # Trailing stop: move to breakeven + 0.5× risk after T1 hit
                l_trail      = round(p + l_risk * 0.5, 2)
                # Time stop: exit day 4 if no movement
                l_time_stop  = "Day 4 if < T1"

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
                if long_sig["consolidation"]:   l_tags.append("COIL")
                if long_sig["rsi_divergence"]:  l_tags.append("RSI DIV")
                if long_sig["sector_leader"]:   l_tags.append("SEC LEAD")
                if squeeze_flag:                l_tags.append("⚡SQUEEZE")
                if vr >= 2.5:                   l_tags.append("VOL SURGE")
                if is_monday:                   l_tags.append("⚠️MON")
                if combo_bonus > 0:             l_tags.append(f"COMBO+{combo_bonus:.0%}")

                long_results.append({
                    "Ticker":       ticker,
                    "Sector":       sector_label(ticker),
                    "Rise Prob":    f"{l_prob * 100:.1f}%",
                    "Prob Tier":    prob_label(l_prob),
                    "Score":        f"{l_score}/20",
                    "Today %":      f"{today_chg:+.2f}%",
                    "Price":        f"${p:.2f}",
                    "Best Stop":    f"${l_stop:.2f}",
                    "Trail Stop":   f"${l_trail:.2f}",
                    "Time Stop":    l_time_stop,
                    "Target 1:1":   f"${l_t1:.2f}",
                    "Target 1:2":   f"${l_t2:.2f}",
                    "Pos/$1k risk": int(1000 / l_risk) if l_risk > 0 else 0,
                    "Float":        float_str,
                    "Short %":      short_str,
                    "RSI":          round(raw["rsi0"], 1),
                    "Stoch K":      round(raw["k0"],   1),
                    "ADX":          round(raw["adx"],  1),
                    "Vol Ratio":    round(vr, 2),
                    "BB Squeeze":   "YES" if long_sig["bb_bull_squeeze"] else "–",
                    "Action":       l_action,
                    "Signals":      " | ".join(l_tags) if l_tags else "–",
                    
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

            if s_score >= min_score_strong_short and s_prob >= min_prob_strong_short and s_top3:
                s_action = "STRONG SHORT"
            elif s_score >= 4 and s_prob >= 0.60 and short_sig["trend_bearish"]:
                s_action = "WATCH SHORT – HIGH QUALITY"
            elif s_score >= 3 and short_sig["trend_bearish"]:
                s_action = "WATCH SHORT – DEVELOPING"
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
                if is_monday:                      s_tags.append("⚠️MON")

                short_results.append({
                    "Ticker":       ticker,
                    "Sector":       sector_label(ticker),
                    "Fall Prob":    f"{s_prob * 100:.1f}%",
                    "Prob Tier":    prob_label(s_prob),
                    "Score":        f"{s_score}/10",
                    "Today %":      f"{today_chg:+.2f}%",
                    "Price":        f"${p:.2f}",
                    "Target 1:1":   f"${s_t1:.2f}",
                    "Target 1:2":   f"${s_t2:.2f}",
                    "Regime bonus": "YES" if regime in ("BEAR","CAUTION") else "–",
                    "Float":        float_str,
                    "Short %":      short_str,
                    "RSI":          round(raw["rsi0"], 1),
                    "Stoch K":      round(raw["k0"],   1),
                    "ADX":          round(raw["adx"],  1),
                    "Vol Ratio":    round(vr, 2),
                    "Cover Stop":   f"${s_cover:.2f}",
                    "Trail Stop":   f"${s_trail:.2f}",
                    "Time Stop":    "Day 4 if > Cover",
                    "Action":       s_action,
                    "Signals":      " | ".join(s_tags) if s_tags else "–",
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

    return make_df(long_results, "Rise Prob"), make_df(short_results, "Fall Prob")


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
            "LONG score / prob":        f"{l_score}/10  →  {l_prob*100:.1f}%  ({prob_label(l_prob)})",
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
            "SHORT score / prob":       f"{s_score}/10  →  {s_prob*100:.1f}%  ({prob_label(s_prob)})",
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
skip_earnings  = st.sidebar.checkbox("Skip earnings within 7 days", True)

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
    f"✅\n\n"
    f"{'✅' if _fd_available else '⚠️'} FinanceDatabase "
    f"({'installed' if _fd_available else 'pip install financedatabase'})"
)

# ─────────────────────────────────────────────────────────────────────────────
# MARKET REGIME BANNER
# ─────────────────────────────────────────────────────────────────────────────
mkt    = get_market_regime()
regime = mkt["regime"]
emojis = {"BULL":"🟢","CAUTION":"🟡","BEAR":"🔴","UNKNOWN":"⚪"}

c1, c2, c3, c4 = st.columns(4)
c1.metric("Market Regime", f"{emojis.get(regime,'⚪')} {regime}")
c2.metric("SPY",  f"${mkt['spy']}", f"EMA20 ${mkt['spy_ema20']}")
c3.metric("VIX",  f"{mkt['vix']}")
c4.metric("Scan", "Normal" if regime=="BULL" else
                  "Strict long / Boost short" if regime=="BEAR" else "Cautious")

if regime == "BEAR":
    st.error("🔴 Bear market — Long thresholds raised · Short probability boosted +8%")
elif regime == "CAUTION":
    st.warning("🟡 Caution zone — Long probabilities reduced 12% · Short boosted +3%")

st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# MARKET SELECTOR  — controls heatmap + scan scope
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("#### 🌍 Select Market to Scan")
market_sel = st.radio(
    "Market", ["🇺🇸 US", "🇸🇬 Singapore (SGX)", "🇮🇳 India (NSE)"],
    horizontal=True, key="market_selector"
)

# Map selection → ticker list, sector map, currency symbol
if market_sel == "🇺🇸 US":
    _active_tickers = US_TICKERS
    _active_sectors = SECTOR_ETFS
    _currency_sym   = "$"
    _price_fmt      = lambda p: f"${p:,.2f}"
elif market_sel == "🇸🇬 Singapore (SGX)":
    _active_tickers = SG_TICKERS
    _active_sectors = {}       # SGX uses stock-group heatmap, not ETF sectors
    _currency_sym   = "S$"
    _price_fmt      = lambda p: f"S${p:,.3f}"
else:
    _active_tickers = INDIA_TICKERS
    _active_sectors = INDIA_SECTOR_ETFS
    _currency_sym   = "₹"
    _price_fmt      = lambda p: f"₹{p:,.2f}"

st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────────────────────────
tab_sectors, tab_long, tab_short, tab_both, tab_etf, tab_stock, tab_diag, tab_help = st.tabs([
    "🗂️ Sector Heatmap",
    "📈 Long Setups",
    "📉 Short Setups",
    "🔄 Side by Side",
    "📊 ETF Holdings",
    "🔬 Stock Analysis",
    "🔍 Diagnostics",
    "❓ Help",
])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — SECTOR HEATMAP  (market-aware)
# ─────────────────────────────────────────────────────────────────────────────
with tab_sectors:
    st.markdown("### Live Sector Heatmap")

    if market_sel == "🇺🇸 US":
        st.caption("US Sector ETFs · Refreshes every 15 min")
        sector_df = get_sector_performance()
    elif market_sel == "🇸🇬 Singapore (SGX)":
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

        p_sym = "₹" if market_sel == "🇮🇳 India (NSE)" else ("S$" if market_sel == "🇸🇬 Singapore (SGX)" else "$")
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

        cg, cr, cf = st.columns(3)
        with cg:
            body = "\n\n".join(
                f"**{s}** ({sector_df.loc[sector_df['Sector']==s,'Today %'].values[0]:+.2f}%)"
                for s in green_list
            )
            st.success(f"🟢 **{len(green_list)} Green — scan for LONGS**\n\n{body}" if body else "🟢 No green sectors")
        with cr:
            body = "\n\n".join(
                f"**{s}** ({sector_df.loc[sector_df['Sector']==s,'Today %'].values[0]:+.2f}%)"
                for s in red_list
            )
            st.error(f"🔴 **{len(red_list)} Red — scan for SHORTS**\n\n{body}" if body else "🔴 No red sectors")
        with cf:
            st.info(f"⚪ **Flat — skip**\n\n" + "\n\n".join(flat_list) if flat_list else "⚪ None flat")

# ─────────────────────────────────────────────────────────────────────────────
# SCAN BUTTON  (market-aware)
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
col_btn, col_info = st.columns([1, 3])
with col_btn:
    run = st.button(f"🚀 Scan {market_sel} Stocks", type="primary")
with col_info:
    # Show sector preview for the active market
    if market_sel == "🇺🇸 US":
        sdf_preview = get_sector_performance()
    elif market_sel == "🇸🇬 Singapore (SGX)":
        sdf_preview = get_sg_sector_performance()
    else:
        sdf_preview = get_india_sector_performance()
        sdf_preview = sdf_preview[sdf_preview["ETF"] != "^NSEI"]

    if not sdf_preview.empty and "Today %" in sdf_preview.columns:
        gn = sdf_preview[sdf_preview["Today %"] >  0.1]["Sector"].tolist()
        rn = sdf_preview[sdf_preview["Today %"] < -0.1]["Sector"].tolist()
        st.info(
            f"**{market_sel}** · {len(_active_tickers)} stocks · "
            f"Top **{top_n_sectors} green** → longs: {', '.join(gn[:top_n_sectors]) or 'none'} · "
            f"Top **{top_n_sectors} red** → shorts: {', '.join(rn[:top_n_sectors]) or 'none'}"
        )

if run:
    # Get sector data for the selected market
    if market_sel == "🇺🇸 US":
        sdf = get_sector_performance()
        active_sector_etfs = SECTOR_ETFS
    elif market_sel == "🇸🇬 Singapore (SGX)":
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
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # Build active ticker list (market-specific + custom)
        active_tickers = list(_active_tickers)
        if extra_tickers:
            for t in extra_tickers:
                if t not in active_tickers:
                    active_tickers.insert(0, t)

        st.info(f"📊 Scanning **{len(active_tickers)} {market_sel} stocks** for signals...")

        with st.spinner(f"Scanning {len(active_tickers)} stocks..."):
            df_long, df_short = fetch_analysis(
                tuple(green_sectors), tuple(red_sectors),
                regime, skip_earnings, top_n_sectors,
                live_sectors if live_sectors else None,
                market_tickers=tuple(active_tickers),
            )

        # Apply sidebar filters
        if not df_long.empty:
            df_long["_p"] = df_long["Rise Prob"].str.rstrip("%").astype(float)
            df_long = df_long[df_long["_p"] >= min_prob_long]
            if req_stoch: df_long = df_long[df_long["Signals"].str.contains("STOCH")]
            if req_bb:    df_long = df_long[df_long["BB Squeeze"] == "YES"]
            if req_accel: df_long = df_long[df_long["Signals"].str.contains("MACD ACCEL")]
            df_long = df_long.drop(columns="_p")

        if not df_short.empty:
            df_short["_p"] = df_short["Fall Prob"].str.rstrip("%").astype(float)
            df_short = df_short[df_short["_p"] >= min_prob_short]
            if req_s_stoch: df_short = df_short[df_short["Signals"].str.contains("STOCH")]
            if req_s_bb:    df_short = df_short[df_short["Signals"].str.contains("BB BEAR")]
            if req_s_decel: df_short = df_short[df_short["Signals"].str.contains("MACD DECEL")]
            df_short = df_short.drop(columns="_p")

        st.session_state["df_long"]            = df_long
        st.session_state["df_short"]           = df_short
        st.session_state["live_sectors_cache"] = live_sectors
        st.session_state["last_market"]        = market_sel

df_long  = st.session_state.get("df_long",  pd.DataFrame())
df_short = st.session_state.get("df_short", pd.DataFrame())
last_market = st.session_state.get("last_market", market_sel)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — LONG
# ─────────────────────────────────────────────────────────────────────────────
with tab_long:
    if not df_long.empty:
        st.caption(f"Results for **{last_market}** · {len(df_long)} setups found")
    if df_long.empty:
        st.info("Run the scan to see long setups.")
    else:
        strong_l  = df_long[df_long["Action"] == "STRONG BUY"]
        watch_hql = df_long[df_long["Action"] == "WATCH – HIGH QUALITY"]
        watch_dvl = df_long[df_long["Action"] == "WATCH – DEVELOPING"]

        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("Strong Buy",    len(strong_l))
        c2.metric("High Quality",  len(watch_hql))
        c3.metric("Developing",    len(watch_dvl))
        c4.metric("Sectors",       df_long["Sector"].nunique())
        c5.metric("Top Rise Prob", df_long["Rise Prob"].iloc[0] if not df_long.empty else "–")

        # sec_cnt = df_long.groupby("Sector").size().reset_index(name="Setups")
        # st.dataframe(sec_cnt, use_container_width=True, hide_index=True)

        st.markdown("### 🔥 Strong Buy")
        show_table(strong_l, "strong buy", "Rise Prob")
        st.markdown("### 👀 High Quality Watch")
        show_table(watch_hql, "high quality", "Rise Prob")
        st.markdown("### 📋 Developing")
        show_table(watch_dvl, "developing", "Rise Prob")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — SHORT
# ─────────────────────────────────────────────────────────────────────────────
with tab_short:
    st.warning("⚠️ Short selling has unlimited loss potential. Always use a hard cover-stop.")
    if not df_short.empty:
        st.caption(f"Results for **{last_market}** · {len(df_short)} setups found")
    if df_short.empty:
        st.info("Run the scan to see short setups.")
    else:
        strong_s  = df_short[df_short["Action"] == "STRONG SHORT"]
        watch_hqs = df_short[df_short["Action"] == "WATCH SHORT – HIGH QUALITY"]
        watch_dvs = df_short[df_short["Action"] == "WATCH SHORT – DEVELOPING"]

        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("Strong Short",  len(strong_s))
        c2.metric("High Quality",  len(watch_hqs))
        c3.metric("Developing",    len(watch_dvs))
        c4.metric("Sectors",       df_short["Sector"].nunique())
        c5.metric("Top Fall Prob", df_short["Fall Prob"].iloc[0] if not df_short.empty else "–")

        # sec_cnt = df_short.groupby("Sector").size().reset_index(name="Setups")
        # st.dataframe(sec_cnt, use_container_width=True, hide_index=True)

        st.markdown("### 🔥 Strong Short")
        show_table(strong_s, "strong short", "Fall Prob")
        st.markdown("### 👀 High Quality Short Watch")
        show_table(watch_hqs, "hq short", "Fall Prob")
        st.markdown("### 📋 Developing Short Setups")
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
# TAB 4 — SIDE BY SIDE
# ─────────────────────────────────────────────────────────────────────────────
with tab_both:
    if df_long.empty and df_short.empty:
        st.info("Run the scan to see results.")
    else:
        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown("### 📈 Top Long Setups")
            top_l = df_long[df_long["Action"] == "STRONG BUY"][
                ["Ticker","Sector","Rise Prob","Score","Price","Best Stop","Target 1:2"]
            ] if not df_long.empty else pd.DataFrame()
            show_table(top_l, "long", "Rise Prob")
        with col_r:
            st.markdown("### 📉 Top Short Setups")
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
    st.markdown("### ETF Holdings — Live Constituents per Sector")
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
    st.dataframe(styled, use_container_width=True)

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
                        use_container_width=True, hide_index=True
                    )
                with c2:
                    st.dataframe(
                        df_stocks.iloc[col_size:col_size*2],
                        use_container_width=True, hide_index=True
                    )
                with c3:
                    st.dataframe(
                        df_stocks.iloc[col_size*2:],
                        use_container_width=True, hide_index=True
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
    st.markdown("### 🔬 Individual Stock Analysis")
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
                    c1,c2,c3,c4,c5,c6 = st.columns(6)
                    c1.metric("Price",   f"${rv_sa['p']:.2f}")
                    c2.metric("Today %", f"{float((close_sa.iloc[-1]-close_sa.iloc[-2])/close_sa.iloc[-2]*100):+.2f}%")
                    c3.metric("Sector",  sector_sa)
                    c4.metric("Mkt Cap", mktcap_str)
                    c5.metric("52W High", f"${week52hi:.2f}" if week52hi else "–")
                    c6.metric("52W Low",  f"${week52lo:.2f}" if week52lo else "–")

                    st.markdown("---")

                    # ── Signal scorecard ──────────────────────────────────────
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

                        # Long action
                        l_bonus_sa = (0.06 if rv_sa["bb_very_tight"] else 0) + (0.05 if rv_sa["vr"] >= 2.5 else 0)
                        l_top3_sa  = long_sig_sa["stoch_confirmed"] or long_sig_sa["bb_bull_squeeze"] or long_sig_sa["macd_accel"]
                        regime_cur = get_market_regime()["regime"]
                        min_score_l = 6 if regime_cur == "BULL" else 7
                        min_prob_l  = 0.72 if regime_cur == "BULL" else 0.78
                        if l_score_sa >= min_score_l and l_prob_sa >= min_prob_l and l_top3_sa:
                            l_rec = "🔥 STRONG BUY"
                            l_col = "success"
                        elif l_score_sa >= 4 and l_prob_sa >= 0.62 and long_sig_sa["trend_daily"]:
                            l_rec = "👀 WATCH – HIGH QUALITY"
                            l_col = "info"
                        elif l_score_sa >= 3 and long_sig_sa["trend_daily"]:
                            l_rec = "📋 WATCH – DEVELOPING"
                            l_col = "info"
                        else:
                            l_rec = "⏸️ NO LONG SETUP"
                            l_col = "warning"
                        getattr(st, l_col)(f"**Long: {l_rec}**")

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
                            s_rec = "🔥 STRONG SHORT"
                            s_col = "error"
                        elif s_score_sa >= 4 and s_prob_sa >= 0.60 and short_sig_sa["trend_bearish"]:
                            s_rec = "👀 WATCH SHORT – HQ"
                            s_col = "warning"
                        elif s_score_sa >= 3 and short_sig_sa["trend_bearish"]:
                            s_rec = "📋 WATCH SHORT – DEV"
                            s_col = "warning"
                        else:
                            s_rec = "⏸️ NO SHORT SETUP"
                            s_col = "info"
                        getattr(st, s_col)(f"**Short: {s_rec}**")

                    st.markdown("---")

                    # ── Live indicator values ─────────────────────────────────
                    st.markdown("#### 📊 Live Indicator Values")
                    ci1,ci2,ci3,ci4,ci5,ci6,ci7,ci8 = st.columns(8)
                    ci1.metric("RSI",        round(rv_sa["rsi0"],1))
                    ci2.metric("Stoch K",    round(rv_sa["k0"],1))
                    ci3.metric("ADX",        round(rv_sa["adx"],1))
                    ci4.metric("EMA8",       f"${rv_sa['e8']:.2f}")
                    ci5.metric("EMA21",      f"${rv_sa['e21']:.2f}")
                    ci6.metric("MACD Hist",  f"{rv_sa['mh0']:.4f}")
                    ci7.metric("Vol Ratio",  f"{rv_sa['vr']:.2f}×")
                    ci8.metric("BB Squeeze", "YES" if rv_sa["bb_squeeze"] else "NO")

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

                        st.plotly_chart(fig, use_container_width=True)

                    except ImportError:
                        st.warning("Install plotly for charts: `pip install plotly`")
                    except Exception as chart_err:
                        st.warning(f"Chart error: {chart_err}")

            except Exception as outer_err:
                st.error(f"Error analysing {stock_ticker}: {outer_err}")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 7 — DIAGNOSTICS
# ─────────────────────────────────────────────────────────────────────────────
with tab_diag:
    st.markdown("### Ticker diagnostics")
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
# TAB 8 — HELP
# ─────────────────────────────────────────────────────────────────────────────
with tab_help:
    st.markdown("## ❓ How to Use the Swing Scanner v9")
    st.caption("Complete guide — updated for v9 multi-market logic")

    # ── QUICK START ───────────────────────────────────────────────────────────
    with st.expander("🚀 Quick Start — 5 steps to your first scan", expanded=True):
        st.markdown("""
**Step 1 — Pick your market**
Use the **🌍 Market Selector** radio button above the tabs:
- 🇺🇸 **US** — ~220 US stocks (Nasdaq, NYSE). Sector heatmap uses 15 US ETFs (XLK, SOXX, XLF…)
- 🇸🇬 **Singapore (SGX)** — 27 SGX stocks (.SI suffix). Heatmap uses 10 sector groups (Banks, REITs, Transport…)
- 🇮🇳 **India (NSE)** — 55 NSE stocks (.NS suffix). Heatmap uses 14 NSE indices (^NSEBANK, ^CNXIT…)

**Step 2 — Check the Sector Heatmap tab**
Green tiles = sectors gaining today → scan for **longs**.
Red tiles = sectors falling today → scan for **shorts**.
The heatmap automatically shows the correct market based on your selection.

**Step 3 — Set sidebar filters**
- **Top N sectors**: Start with 3.
- **Min LONG rise prob**: Default 62%. Raise to 72%+ for high conviction only.
- **Skip earnings**: Keep ON — earnings gaps destroy swing trades (14-day guard).

**Step 4 — Click 🚀 Scan [Market] Stocks**
The button label changes to match your market. The scanner:
1. Downloads only that market's stocks in one batch
2. Computes 20 long + 10 short signals per stock
3. Applies Bayesian probability + regime + Monday penalty
4. Shows results sorted by probability

**Step 5 — Verify with 🔬 Stock Analysis tab**
Type any ticker (NVDA, D05.SI, RELIANCE.NS) to see full chart + trade plan.
Confirm risk:reward ≥ 1:2 and stop loss is within your tolerance before entering.
        """)

    # ── MARKET SELECTOR ───────────────────────────────────────────────────────
    with st.expander("🌍 Market Selector — what changes per market"):
        st.markdown("""
| | 🇺🇸 US | 🇸🇬 Singapore (SGX) | 🇮🇳 India (NSE) |
|---|---|---|---|
| **Ticker count** | ~220 stocks | 27 stocks (.SI) | 55 stocks (.NS) |
| **Sector heatmap** | 15 US ETFs (XLK, SOXX, etc.) | 10 stock-group averages | 14 NSE indices (^NSEBANK, etc.) |
| **Currency** | USD ($) | SGD (S$) | INR (₹) |
| **Trading hours** | NYSE/Nasdaq 09:30–16:00 EST | SGX 09:00–17:00 SGT | NSE 09:15–15:30 IST |
| **Live ETF holdings** | ✅ Fetched via FinanceDatabase/yfinance | ❌ Not available (uses fixed list) | ❌ Not available (uses fixed list) |
| **Short selling** | ✅ Available (IBKR, etc.) | ⚠️ Limited on SGX | ❌ Not available for retail in India |
| **Liquidity note** | High — tight spreads | Low — use limit orders | Medium — NSE is liquid for large-caps |

**SGX heatmap note:** SGX has no liquid sector ETFs so the heatmap is computed as the average % change of constituent stocks within each sector group. It is directionally accurate but may differ slightly from an official sector index.
        """)

    # ── SIGNAL GUIDE ─────────────────────────────────────────────────────────
    with st.expander("📊 Signal Guide — all 20 long + 10 short signals"):
        st.markdown("### Long Signals (20 total → Score /20)")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
**Original 10 signals**

| Tag | What it detects |
|-----|----------------|
| `TREND` | Price > EMA8 > EMA21 — short-term uptrend |
| `STOCH BOUNCE` | Stoch K was <20 for 2 bars, now crossing above D-line |
| `BB BULL SQ` | BB squeeze + price above midline — coil before explosion |
| `MACD ACCEL` | MACD histogram rising 3 bars — momentum accelerating |
| `MACD CROSS` | MACD line crossed above signal with +ve histogram |
| `RSI>50` | RSI crossed above 50 — bullish shift confirmed |
| `ADX>20` | Trend strength confirmed |
| `VOL>1.5×` | Volume 1.5× 20-day average |
| `VOL BREAKOUT` | Price at 10-day high + vol ≥1.8× |
| `HIGHER LOWS` | Two consecutive higher swing lows |
            """)
        with col2:
            st.markdown("""
**New accuracy signals (10)**

| Tag | What it detects |
|-----|----------------|
| `WKLY TREND` | EMA20 > EMA50 — macro uptrend on weekly timeframe |
| `🟡GC` / `🔥FRESH GC` | EMA50 > EMA200 golden cross. Fresh = last 10 bars |
| `RS>SPY` | Stock beat SPY over last 5 days |
| `52W HIGH` | Price within 10% of 52-week high — momentum |
| `OBV↑` | On-Balance Volume rising 5 consecutive days |
| `BULL CANDLE` | Hammer or bullish engulfing on last candle |
| `ATR EXP` | Today's range > 1.2× ATR — breakout energy |
| `COIL` | 3–8 tight-range days before today |
| `RSI DIV` | Price lower low but RSI higher low — divergence |
| `SEC LEAD` | Stock outperforming its sector ETF last 5 days |
| `⚡SQUEEZE` | Short interest >15% + bullish — squeeze potential |
| `COMBO+%` | High-win signal cluster bonus (up to +8% probability) |
| `⚠️MON` | Monday flag — probability reduced 6% (gap risk) |
            """)

        st.markdown("### Short Signals (10 total → Score /10)")
        st.markdown("""
| Tag | What it detects |
|-----|----------------|
| `TREND BEAR` | Price < EMA8 < EMA21 — short-term downtrend |
| `STOCH ROLLOVER` | Stoch K was >80 for 2 bars, now crossing below D-line |
| `BB BEAR SQ` | BB squeeze + price below midline |
| `MACD DECEL` | MACD histogram declining 3 consecutive bars |
| `MACD BEAR` | MACD line below signal with –ve histogram |
| `RSI<50` | RSI crossed below 50 — bearish shift confirmed |
| `ADX BEAR` | ADX >20 with price below EMA21 |
| `DIST DAY` | Large red candle on 2× average volume |
| `VOL BREAKDOWN` | Price at 10-day low + high volume |
| `LOWER HIGHS` | Two consecutive lower swing highs |
        """)

    # ── ACTION TIERS ─────────────────────────────────────────────────────────
    with st.expander("🎯 Action tiers — how STRONG BUY is determined"):
        st.markdown("""
### Long tiers (score out of 20)

| Action | Score | Rise Prob | Also needs | What to do |
|--------|-------|-----------|------------|------------|
| 🔥 **STRONG BUY** | ≥6 (BULL) / ≥7 (BEAR/CAUTION) | ≥72% (BULL) / ≥78% | One of: Stoch/BB/MACD | Enter next day at open. Set stop immediately. |
| 👀 **WATCH – HIGH QUALITY** | ≥4 | ≥62% | Daily trend | Watchlist. Enter if opens strong. |
| 📋 **WATCH – DEVELOPING** | ≥3 | any | Daily trend | Monitor only. Setup not confirmed. |

### Short tiers (score out of 10)

| Action | Score | Fall Prob | Also needs | What to do |
|--------|-------|-----------|------------|------------|
| 🔥 **STRONG SHORT** | ≥5 (BEAR/CAUTION) / ≥6 (BULL) | ≥68% (BEAR) / ≥72% | One of: Stoch/BB/MACD | Enter short. Place cover stop immediately. |
| 👀 **WATCH SHORT – HQ** | ≥4 | ≥60% | Bearish trend | Watchlist. Short if continues lower. |
| 📋 **WATCH SHORT – DEV** | ≥3 | any | Bearish trend | Monitor only. |

### Market regime effect

| Regime | Detected when | Long adjustment | Short adjustment |
|--------|--------------|-----------------|------------------|
| 🟢 **BULL** | SPY > EMA20 and VIX < 20 | Normal thresholds | Normal |
| 🟡 **CAUTION** | Between BULL and BEAR | Prob × 0.88 (–12%) | Bonus +3% |
| 🔴 **BEAR** | SPY < EMA50 or VIX > 25 | Prob × 0.75 (–25%), score ≥7 | Bonus +8% |

### Signal combo bonuses (added to probability)

| Combo | Bonus |
|-------|-------|
| BB squeeze + Vol breakout + Stoch bounce | +7% |
| MACD accel + RSI>50 + Higher lows | +6% |
| Daily trend + Weekly trend + RS>SPY | +5% |
| Fresh golden cross + Vol breakout | +8% |
        """)

    # ── TRADE PLAN ───────────────────────────────────────────────────────────
    with st.expander("💼 Trade plan — stops, targets, sizing"):
        st.markdown("""
### Stop loss

**Best Stop** = higher of:
- **ATR Stop**: Entry − 1.5 × 14-day ATR
- **Swing Stop**: Last swing low × 0.995

**Trail Stop** — move stop to Entry + 0.5× risk once Target 1:1 is hit. Locks in profit.

**Time Stop** — exit on Day 4 if price hasn't reached Target 1:1. Prevents dead money.

### Targets

| Target | Formula | Action |
|--------|---------|--------|
| **1:1** | Entry + (Entry − Stop) | Take 50% off position here |
| **1:2** | Entry + 2× risk | Exit remainder here |

### Position sizing

`Pos/$1k risk` = 1000 ÷ risk per share

**Example:** NVDA at ₹150, stop ₹145 → risk = ₹5 → buy 200 shares per ₹1,000 risked.
Risk max 1–2% of portfolio per trade.

### Short trade plan (reversed)

- **Cover Stop** = Entry + 1.5× ATR or last swing high × 1.005 (whichever is closer)
- **Targets** are BELOW entry price
- **Time Stop**: exit Day 4 if price hasn't reached Target 1:1
        """)

    # ── RISK WARNINGS ────────────────────────────────────────────────────────
    with st.expander("⚠️ Risk warnings — read before trading"):
        st.warning("""
**This tool does not provide financial advice. All signals are for informational purposes only.**

**1. Signal accuracy is not 100%** — even 78% probability means 22 in 100 trades lose. Always use stops.

**2. Short selling — US only** — Short selling has unlimited loss potential. SGX is limited; India retail cannot short individual stocks. Never short without a hard cover-stop placed immediately.

**3. Earnings risk** — 14-day guard is active, but surprise earnings/guidance can still gap stocks 20–30% overnight.

**4. Concentration risk** — Side-by-Side tab warns when ≥3 STRONG BUY setups are in the same sector. Stocks in the same sector are 0.80+ correlated — a sector sell-off wipes all positions simultaneously.

**5. Monday penalty** — Probability is reduced 6% on Mondays. Setups tagged ⚠️MON have lower reliability. Consider waiting for Tuesday entry.

**6. SGX liquidity** — SGX stocks have much lower daily volume. Use limit orders and expect wider spreads. Position size accordingly.

**7. India FX risk** — India NSE prices are in INR. If you are investing from Singapore, add INR/SGD currency risk to your position sizing.

**8. Market hours** — Data is only live during respective market hours. Outside hours, sector heatmap shows previous close data.
        """)

    # ── SIDEBAR SETTINGS ─────────────────────────────────────────────────────
    with st.expander("⚙️ Sidebar settings explained"):
        st.markdown("""
| Setting | What it does | Recommended |
|---------|-------------|-------------|
| **Top N green/red sectors** | How many sectors to pull candidates from. Higher = more stocks, slower scan. | 3 |
| **Min LONG rise prob** | Minimum Bayesian probability to show in results. | 62% (strict: 72%) |
| **Min SHORT fall prob** | Minimum probability for short setups. | 60% (strict: 70%) |
| **Skip earnings within 7 days** | Skips stocks with earnings in the next 14 days (guard is extended to 14). | ON always |
| **Must have Stoch bounce** | Only show longs with confirmed Stoch RSI oversold bounce. | OFF normally |
| **Must have BB bull squeeze** | Only show longs with BB squeeze + price above midline. | OFF normally |
| **Must have MACD acceleration** | Only show longs with MACD histogram accelerating up. | OFF normally |
| **Custom tickers** | Add tickers not in the base list. Works for any market suffix (.SI, .NS, etc.). | e.g. HIMS, RVNL.NS |

**Market Selector (above tabs)** — controls which ticker list is scanned AND which heatmap is shown. Changing the market does NOT automatically re-run the scan — click the scan button again.
        """)

    # ── GLOSSARY ─────────────────────────────────────────────────────────────
    with st.expander("📖 Glossary"):
        st.markdown("""
| Term | Meaning |
|------|---------|
| **EMA8 / EMA21** | Exponential Moving Averages. Price > EMA8 > EMA21 = short-term uptrend |
| **EMA50 / EMA200** | Long-term trend. Golden Cross = EMA50 crosses above EMA200 |
| **RSI** | Relative Strength Index (0–100). >70 overbought, <30 oversold, 50 = neutral |
| **Stochastic RSI** | K line = RSI position vs recent range. D line = 3-day avg of K |
| **MACD** | Moving Average Convergence Divergence. Histogram = MACD line minus signal |
| **Bollinger Bands** | ±2 std dev envelope around 20-day MA. Squeeze = bands narrowing before a move |
| **ADX** | Average Directional Index. >20 = trending, >40 = strongly trending |
| **ATR** | Average True Range. Daily volatility measure used for stop placement |
| **OBV** | On-Balance Volume. Rising = buying pressure / accumulation |
| **Bayesian probability** | Sequential update: each signal adjusts probability based on its historical win rate |
| **Combo bonus** | Extra probability boost when specific high-win signal combinations fire together |
| **Monday penalty** | –6% probability adjustment on Mondays to account for weekend gap risk |
| **VCP** | Volatility Contraction Pattern. ATR5/ATR20 < 0.85 = stock coiling before a move |
| **RS>SPY** | Stock's 5-day return greater than SPY's 5-day return = market outperformer |
| **Short interest** | % of float sold short. >15% with bullish signals = squeeze candidate |
| **Float** | Number of shares available to trade publicly |
| **Dollar volume** | Price × average daily volume. >$5M filter ensures liquid swing trades |
| **Trail Stop** | Stop moved to breakeven + 0.5× risk after Target 1:1 is hit |
| **Time Stop** | Exit on Day 4 if Target 1:1 not reached regardless of P&L |
        """)

    # ── INSTALL ──────────────────────────────────────────────────────────────
    with st.expander("🔧 Install & run"):
        st.markdown("""
```bash
pip install streamlit yfinance pandas numpy ta financedatabase plotly
python -m streamlit run swing_trader_v9.py
```

| Data | Cache | Notes |
|------|-------|-------|
| Sector heatmaps | 15 min | All 3 markets cached separately |
| Market regime (SPY/VIX) | 30 min | Shows warning if fetch fails |
| Scan results | 60 min | Re-run scan to refresh |
| US ETF holdings | 6 hours | Only fetched for US market scans |
| ETF performance table | 60 min | Click 🔄 Refresh to force update |

**Market regime shows UNKNOWN?** Run `pip install --upgrade yfinance` — this is the most common cause. The regime banner now shows the exact error message to help diagnose.
        """)

    st.markdown("---")
    st.caption("Swing Scanner v9 · US + SGX + India · Not financial advice · Created by Ripin")