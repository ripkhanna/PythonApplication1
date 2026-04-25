"""
Swing Scanner v6 — Polygon.io + FinanceDatabase
================================================
• Price/OHLCV data    → polygon.io REST API (stable, versioned)
• ETF holdings        → financedatabase (local offline DB, full constituent lists)
• Earnings dates      → yfinance (fallback only)
• Sector performance  → polygon.io snapshot endpoint

API KEY SETUP (keep secret — never hardcode):
  1. Create a file called .env in the same folder as this script
  2. Add one line:  POLYGON_API_KEY=your_key_here
  3. Run:  pip install python-dotenv polygon-api-client financedatabase ta streamlit yfinance
"""

import os
import time
import streamlit as st
import pandas as pd
import numpy as np
import ta
import yfinance as yf
from datetime import datetime, date, timedelta

# ── Load API key from .env (safe — never hardcoded) ───────────────────────────
try:
    from dotenv import load_dotenv
    from pathlib import Path
    # Load from same directory as this script — works regardless of working directory
    _env_path = Path(__file__).parent / ".env"
    load_dotenv(dotenv_path=_env_path, override=True)
except ImportError:
    pass   # dotenv optional if key is set as system env var

POLYGON_API_KEY = os.environ.get("POLYGON_API_KEY", "").strip()

# ── Polygon client ─────────────────────────────────────────────────────────────
try:
    from polygon import RESTClient as PolygonClient
    _polygon_available = bool(POLYGON_API_KEY)
except ImportError:
    try:
        from polygon.rest import RESTClient as PolygonClient
        _polygon_available = bool(POLYGON_API_KEY)
    except ImportError:
        _polygon_available = False
        PolygonClient = None

# ── FinanceDatabase ────────────────────────────────────────────────────────────
try:
    import financedatabase as fd
    _fd_available = True
except ImportError:
    _fd_available = False

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Swing Scanner v6 — Polygon", layout="wide")
st.title("5–7 Day Swing Scanner v6 — Polygon.io + FinanceDatabase")
st.markdown(
    "🟢 Green sectors → best **long** candidates · "
    "🔴 Red sectors → best **short** candidates · "
    "Powered by **Polygon.io** + **FinanceDatabase**"
)

# ─────────────────────────────────────────────────────────────────────────────
# API KEY INPUT (shown only if not in .env)
# ─────────────────────────────────────────────────────────────────────────────
if not POLYGON_API_KEY:
    st.sidebar.markdown("---")
    st.sidebar.header("🔑 Polygon API Key")
    entered_key = st.sidebar.text_input(
        "Enter your Polygon.io API key",
        type="password",
        help="Get a free key at polygon.io — store in .env file for safety"
    )
    if entered_key:
        POLYGON_API_KEY = entered_key
        _polygon_available = True
    else:
        st.warning(
            "⚠️ No Polygon API key found. "
            "Add `POLYGON_API_KEY=your_key` to a `.env` file in the same folder, "
            "or enter it in the sidebar. Get a free key at **polygon.io**"
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

# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL WEIGHTS
# ─────────────────────────────────────────────────────────────────────────────
LONG_WEIGHTS = {
    "stoch_confirmed": 0.71, "bb_bull_squeeze": 0.69, "macd_accel": 0.67,
    "vol_breakout":    0.66, "trend_daily":     0.63, "higher_lows": 0.63,
    "macd_cross":      0.60, "adx":             0.58, "volume":      0.56,
    "rsi_confirmed":   0.59,
}
SHORT_WEIGHTS = {
    "stoch_overbought": 0.70, "bb_bear_squeeze":  0.68, "macd_decel":     0.66,
    "vol_breakdown":    0.65, "trend_bearish":    0.63, "lower_highs":    0.62,
    "macd_cross_bear":  0.60, "adx_bear":         0.57, "rsi_cross_bear": 0.59,
    "high_volume_down": 0.64,
}
BASE_RATE = 0.50

# ─────────────────────────────────────────────────────────────────────────────
# POLYGON HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def _poly_client():
    return PolygonClient(POLYGON_API_KEY)


def _date_str(d: date) -> str:
    return d.strftime("%Y-%m-%d")


@st.cache_data(ttl=900)   # 15-min cache
def get_sector_performance_polygon() -> pd.DataFrame:
    """
    Fetches today's % change for all sector ETFs.
    Uses Polygon get_aggs() (FREE tier) — last 5 trading days of daily bars.
    get_snapshot_all() is paid-only so we never call it.
    Falls back to yfinance if polygon unavailable.
    """
    etf_tickers  = list(SECTOR_ETFS.values())
    sector_names = list(SECTOR_ETFS.keys())
    results      = []

    if _polygon_available:
        try:
            client  = _poly_client()
            today_d = date.today()
            from_d  = today_d - timedelta(days=10)  # enough to get 5 trading days
            success = 0

            for name, etf in zip(sector_names, etf_tickers):
                try:
                    bars = list(client.get_aggs(
                        etf, 1, "day",
                        _date_str(from_d), _date_str(today_d),
                        adjusted=True, limit=10,
                    ))
                    time.sleep(0.13)   # stay under 5 req/min on free tier

                    if len(bars) < 2:
                        continue

                    prev_close  = float(bars[-2].close)
                    today_close = float(bars[-1].close)
                    pct         = (today_close - prev_close) / prev_close * 100 if prev_close > 0 else 0.0
                    pct5        = (today_close - float(bars[0].close)) / float(bars[0].close) * 100 \
                                  if len(bars) >= 5 else 0.0

                    results.append({
                        "Sector":  name,
                        "ETF":     etf,
                        "Today %": round(pct,  2),
                        "5d %":    round(pct5, 2),
                        "Price":   round(today_close, 2),
                        "Status":  "🟢 GREEN" if pct > 0.1 else ("🔴 RED" if pct < -0.1 else "⚪ FLAT"),
                        "Source":  "polygon",
                    })
                    success += 1

                except Exception:
                    continue   # this ETF failed — skip, don't abort whole loop

            if results:
                return pd.DataFrame(results).sort_values("Today %", ascending=False)

        except Exception as e:
            st.warning(f"Polygon sector fetch failed ({e}), using yfinance...")

    # ── yfinance fallback ─────────────────────────────────────────────────────
    try:
        raw = yf.download(
            etf_tickers, period="5d", interval="1d",
            progress=False, group_by="ticker"
        )
        for name, etf in zip(sector_names, etf_tickers):
            try:
                closes = raw[etf]["Close"].squeeze().ffill().dropna() \
                         if len(etf_tickers) > 1 \
                         else raw["Close"].squeeze().ffill().dropna()
                if len(closes) < 2:
                    continue
                pct  = (closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2] * 100
                pct5 = (closes.iloc[-1] - closes.iloc[0])  / closes.iloc[0]  * 100
                results.append({
                    "Sector":  name, "ETF": etf,
                    "Today %": round(float(pct),  2),
                    "5d %":    round(float(pct5), 2),
                    "Price":   round(float(closes.iloc[-1]), 2),
                    "Status":  "🟢 GREEN" if pct > 0.1 else ("🔴 RED" if pct < -0.1 else "⚪ FLAT"),
                    "Source":  "yfinance",
                })
            except Exception:
                continue
    except Exception:
        pass

    return pd.DataFrame(results).sort_values("Today %", ascending=False) \
           if results else pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# ETF HOLDINGS — financedatabase (offline, full lists)
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=21600)   # 6-hour cache — holdings rarely change
def fetch_sector_constituents_fd(target_per_sector: int = 25) -> dict:
    """
    FAST version — three speed improvements:
    1. Load financedatabase ONCE (not once per ETF)
    2. Score ALL stocks across ALL sectors in ONE yfinance batch download
    3. Polygon used only for OHLCV bars in the main scan, not here
    Target: <30 seconds total instead of 12 minutes
    """
    etf_items = list(SECTOR_ETFS.items())
    sectors   = {}

    # ── Step 1: Get raw holdings for all ETFs ─────────────────────────────────
    status = st.empty()
    status.text("📚 Loading ETF holdings...")

    if _fd_available:
        try:
            # Load FD database ONCE
            etfs_db = fd.ETFs()
            equities_db = fd.Equities()

            for sector_name, etf_ticker in etf_items:
                try:
                    etf_data = etfs_db.select(symbol=etf_ticker)
                    stocks   = []

                    if not etf_data.empty:
                        for col in ["holdings", "top_holdings", "constituents"]:
                            if col in etf_data.columns:
                                raw_val = etf_data[col].iloc[0]
                                if isinstance(raw_val, list):
                                    stocks = [str(s).upper().strip() for s in raw_val
                                              if str(s).strip().replace("-","").isalpha()
                                              and 1 <= len(str(s).strip()) <= 6]
                                elif isinstance(raw_val, str) and raw_val:
                                    stocks = [s.upper().strip() for s in raw_val.split(",")
                                              if s.strip().replace("-","").isalpha()
                                              and 1 <= len(s.strip()) <= 6]
                                if stocks:
                                    break

                        # Fallback: use equities DB filtered by category
                        if not stocks and "category" in etf_data.columns:
                            cat = str(etf_data["category"].iloc[0])
                            if cat:
                                cat_df = equities_db.select(category=cat)
                                if not cat_df.empty:
                                    stocks = cat_df.index.tolist()

                    sectors[sector_name] = {
                        "etf": etf_ticker,
                        "stocks": [s for s in stocks if s != etf_ticker][:target_per_sector * 2],
                        "source": "financedatabase",
                    }
                except Exception:
                    sectors[sector_name] = {"etf": etf_ticker, "stocks": [], "source": "fd_error"}

        except Exception:
            pass   # FD failed entirely — fall through to yfinance below

    # ── Fallback: yfinance batch for any sector that got 0 stocks ─────────────
    missing = [etf for name, etf in etf_items
               if not sectors.get(name, {}).get("stocks")]

    if missing:
        status.text(f"📡 Fetching holdings for {len(missing)} ETFs via yfinance...")
        for sector_name, etf_ticker in etf_items:
            if sectors.get(sector_name, {}).get("stocks"):
                continue   # already have stocks
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
                    "stocks": stocks[:target_per_sector * 2],
                    "source": "yfinance",
                }
            except Exception:
                sectors[sector_name] = {"etf": etf_ticker, "stocks": [], "source": "none"}

    # ── Step 2: Score ALL stocks in ONE batch download ────────────────────────
    # Collect every unique ticker across all sectors
    all_symbols = list(dict.fromkeys(
        sym
        for data in sectors.values()
        for sym in data.get("stocks", [])
    ))

    status.text(f"📊 Scoring {len(all_symbols)} stocks in one batch download...")

    scored_map = {}   # sym → swing_score
    if all_symbols:
        try:
            # ONE yfinance download for everything — fastest possible
            batch = yf.download(
                all_symbols,
                period="1mo",
                interval="1d",
                progress=False,
                group_by="ticker",
                threads=True,
                auto_adjust=True,
            )

            for sym in all_symbols:
                try:
                    if len(all_symbols) == 1:
                        c = batch["Close"].squeeze().ffill().dropna()
                        v = batch["Volume"].squeeze().ffill().dropna()
                        h = batch["High"].squeeze().ffill().dropna()
                        lo= batch["Low"].squeeze().ffill().dropna()
                    else:
                        if sym not in batch.columns.get_level_values(1) \
                           if isinstance(batch.columns, pd.MultiIndex) else []:
                            continue
                        c  = batch["Close"][sym].ffill().dropna()
                        v  = batch["Volume"][sym].ffill().dropna()
                        h  = batch["High"][sym].ffill().dropna()
                        lo = batch["Low"][sym].ffill().dropna()

                    if len(c) < 10:
                        continue

                    price      = float(c.iloc[-1])
                    avg_vol    = float(v.mean())
                    dollar_vol = price * avg_vol

                    # Quality filters
                    if price < 3 or dollar_vol < 5_000_000:
                        continue

                    atr_val = float(
                        ta.volatility.average_true_range(h, lo, c, window=14).iloc[-1]
                    )
                    atr_pct = atr_val / price * 100

                    # Sweet spot: ATR 2–12% = moves enough for swing, not too wild
                    atr_bonus = 1.5 if 2 <= atr_pct <= 12 else (0.7 if atr_pct < 2 else 0.4)
                    scored_map[sym] = dollar_vol * atr_bonus

                except Exception:
                    continue

        except Exception as e:
            status.text(f"Batch scoring failed ({e}), using raw order...")

    # ── Step 3: Rank each sector's stocks by swing score ─────────────────────
    out = {}
    for sector_name, data in sectors.items():
        raw = data.get("stocks", [])
        if not raw:
            out[sector_name] = {**data, "count": 0}
            continue

        # Sort by score, keep unscored stocks at the end
        ranked = sorted(raw, key=lambda s: scored_map.get(s, 0), reverse=True)
        best   = ranked[:target_per_sector]

        out[sector_name] = {
            **data,
            "stocks": best,
            "count":  len(best),
        }

    status.empty()
    return out


def _score_via_polygon(symbols: list) -> list:
    """
    Score stocks for swing quality using Polygon get_aggs() — FREE tier.
    Downloads last 30 days of daily bars per stock.
    Uses 130ms sleep between calls to stay under 5 req/min free limit.
    """
    scored    = []
    client    = _poly_client()
    today_d   = date.today()
    from_d    = today_d - timedelta(days=45)   # ~30 trading days

    for sym in symbols:
        try:
            bars = list(client.get_aggs(
                sym, 1, "day",
                _date_str(from_d), _date_str(today_d),
                adjusted=True, limit=45,
            ))
            time.sleep(0.13)   # free tier: 5 req/min = 12s per request — 130ms is safe with batching

            if len(bars) < 10:
                continue

            closes  = np.array([float(b.close)  for b in bars])
            highs   = np.array([float(b.high)   for b in bars])
            lows    = np.array([float(b.low)    for b in bars])
            volumes = np.array([float(b.volume) for b in bars])

            price      = closes[-1]
            avg_vol    = float(np.mean(volumes))
            dollar_vol = price * avg_vol

            if price < 3 or dollar_vol < 10_000_000:
                continue

            # ATR calculation (manual — no ta dependency here)
            tr = np.maximum(
                highs[1:] - lows[1:],
                np.maximum(
                    np.abs(highs[1:] - closes[:-1]),
                    np.abs(lows[1:]  - closes[:-1])
                )
            )
            atr_pct = float(np.mean(tr[-14:])) / price * 100

            atr_bonus   = 1.5 if 3 <= atr_pct <= 10 else (0.8 if atr_pct <= 2 else 0.5)
            swing_score = dollar_vol * atr_bonus

            scored.append({
                "sym":         sym,
                "price":       round(price, 2),
                "avg_vol":     int(avg_vol),
                "dollar_vol":  dollar_vol,
                "atr_pct":     round(atr_pct, 2),
                "swing_score": swing_score,
                "source":      "polygon",
            })

        except Exception:
            continue

    return scored


def _score_via_yfinance(symbols: list) -> list:
    """Score stocks using yfinance batch download (fallback)."""
    scored = []
    try:
        batch = yf.download(
            symbols[:60], period="1mo", interval="1d",
            progress=False, group_by="ticker", threads=True
        )
        for sym in symbols[:60]:
            try:
                if len(symbols[:60]) == 1:
                    c = batch["Close"].squeeze().ffill().dropna()
                    v = batch["Volume"].squeeze().ffill().dropna()
                    h = batch["High"].squeeze().ffill().dropna()
                    lo= batch["Low"].squeeze().ffill().dropna()
                else:
                    c = batch[sym]["Close"].squeeze().ffill().dropna()
                    v = batch[sym]["Volume"].squeeze().ffill().dropna()
                    h = batch[sym]["High"].squeeze().ffill().dropna()
                    lo= batch[sym]["Low"].squeeze().ffill().dropna()

                if len(c) < 10:
                    continue
                price     = float(c.iloc[-1])
                avg_vol   = float(v.mean())
                dollar_vol = price * avg_vol
                if price < 3 or dollar_vol < 10_000_000:
                    continue
                atr_pct = float(
                    ta.volatility.average_true_range(h, lo, c, window=14).iloc[-1]
                ) / price * 100
                atr_bonus  = 1.5 if 3 <= atr_pct <= 10 else (0.8 if atr_pct <= 2 else 0.5)
                scored.append({
                    "sym": sym, "price": round(price, 2),
                    "avg_vol": int(avg_vol), "dollar_vol": dollar_vol,
                    "atr_pct": round(atr_pct, 2),
                    "swing_score": dollar_vol * atr_bonus,
                    "source": "yfinance",
                })
            except Exception:
                continue
    except Exception:
        pass
    return scored


# ─────────────────────────────────────────────────────────────────────────────
# OHLCV FETCHER — Polygon primary, yfinance fallback
# ─────────────────────────────────────────────────────────────────────────────
def fetch_ohlcv(ticker: str, days: int = 130) -> pd.DataFrame | None:
    """
    Returns a DataFrame with columns [Open, High, Low, Close, Volume]
    sorted oldest-first. Uses Polygon, falls back to yfinance.
    """
    today_d = date.today()
    from_d  = today_d - timedelta(days=days)

    if _polygon_available:
        try:
            client = _poly_client()
            bars   = list(client.get_aggs(
                ticker, 1, "day",
                _date_str(from_d), _date_str(today_d),
                limit=days + 10,
                adjusted=True,
            ))
            time.sleep(0.05)   # gentle rate limiting
            if len(bars) < 60:
                raise ValueError("Insufficient bars from Polygon")
            df = pd.DataFrame([{
                "Date":   pd.Timestamp(b.timestamp, unit="ms"),
                "Open":   float(b.open),
                "High":   float(b.high),
                "Low":    float(b.low),
                "Close":  float(b.close),
                "Volume": float(b.volume),
            } for b in bars]).set_index("Date").sort_index()
            return df
        except Exception:
            pass   # fall through to yfinance

    # yfinance fallback
    try:
        raw = yf.download(ticker, period="6mo", interval="1d", progress=False)
        if raw.empty or len(raw) < 60:
            return None
        raw.columns = [c[0] if isinstance(c, tuple) else c for c in raw.columns]
        return raw[["Open","High","Low","Close","Volume"]].ffill().dropna()
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
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
    if p >= 0.62: return "MOD-HIGH"
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


def show_table(df, label, prob_col="Rise Prob"):
    if df.empty:
        st.info(f"No {label} setups.")
        return
    styler   = df.style
    style_fn = styler.map if hasattr(styler, "map") else styler.applymap
    fn = style_short_prob if prob_col == "Fall Prob" else style_prob
    st.dataframe(style_fn(fn, subset=[prob_col]), use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# MARKET REGIME
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=1800)
def get_market_regime():
    df = fetch_ohlcv("SPY", days=90)
    try:
        vix_raw = yf.download("^VIX", period="5d", interval="1d", progress=False)
        vix_now = float(vix_raw["Close"].squeeze().ffill().iloc[-1])
    except Exception:
        vix_now = 20.0

    if df is None or df.empty:
        return {"regime": "UNKNOWN", "spy": 0, "spy_ema20": 0, "spy_ema50": 0, "vix": vix_now}

    close     = df["Close"].squeeze()
    spy_ema20 = float(ta.trend.ema_indicator(close, window=20).iloc[-1])
    spy_ema50 = float(ta.trend.ema_indicator(close, window=50).iloc[-1])
    spy_now   = float(close.iloc[-1])

    if spy_now > spy_ema20 and vix_now < 20:
        regime = "BULL"
    elif spy_now < spy_ema50 or vix_now > 25:
        regime = "BEAR"
    else:
        regime = "CAUTION"

    return {"regime": regime, "spy": round(spy_now, 2),
            "spy_ema20": round(spy_ema20, 2), "spy_ema50": round(spy_ema50, 2),
            "vix": round(vix_now, 2)}


# ─────────────────────────────────────────────────────────────────────────────
# EARNINGS GUARD  — yfinance (polygon free tier doesn't cover earnings)
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def get_earnings_flag(ticker):
    try:
        info = yf.Ticker(ticker).calendar
        if info is None or info.empty:
            return False, "–"
        ed = info.loc["Earnings Date"].iloc[0] if "Earnings Date" in info.index else info.iloc[0, 0]
        if pd.isnull(ed):
            return False, "–"
        days_out = (pd.Timestamp(ed).date() - datetime.today().date()).days
        return 0 <= days_out <= 7, str(pd.Timestamp(ed).date())
    except:
        return False, "–"


# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL COMPUTATION
# ─────────────────────────────────────────────────────────────────────────────
def compute_all_signals(df: pd.DataFrame):
    close = df["Close"].squeeze()
    high  = df["High"].squeeze()
    low   = df["Low"].squeeze()
    vol   = df["Volume"].squeeze()

    ema8   = ta.trend.ema_indicator(close, window=8)
    ema21  = ta.trend.ema_indicator(close, window=21)
    rsi    = ta.momentum.rsi(close, window=14)
    srsi_k = ta.momentum.stochrsi_k(close, window=14, smooth1=3, smooth2=3)
    srsi_d = ta.momentum.stochrsi_d(close, window=14, smooth1=3, smooth2=3)
    macd_o = ta.trend.MACD(close)
    bb     = ta.volatility.BollingerBands(close, window=20, window_dev=2)
    adx    = ta.trend.adx(high, low, close, window=14)
    atr    = ta.volatility.average_true_range(high, low, close, window=14)
    vol_avg  = vol.rolling(20).mean()
    high_10d = high.rolling(10).max()
    low_10d  = low.rolling(10).min()
    bb_width = (bb.bollinger_hband() - bb.bollinger_lband()) / bb.bollinger_mavg()

    p    = to_float(close.iloc[-1])
    e8   = to_float(ema8.iloc[-1]); e21 = to_float(ema21.iloc[-1])
    rsi0 = to_float(rsi.iloc[-1]);  rsi1 = to_float(rsi.iloc[-2]); rsi2 = to_float(rsi.iloc[-3])
    k0   = to_float(srsi_k.iloc[-1]); k1 = to_float(srsi_k.iloc[-2]); k2 = to_float(srsi_k.iloc[-3])
    d0   = to_float(srsi_d.iloc[-1])
    ml   = to_float(macd_o.macd().iloc[-1]);       ms  = to_float(macd_o.macd_signal().iloc[-1])
    mh0  = to_float(macd_o.macd_diff().iloc[-1]);  mh1 = to_float(macd_o.macd_diff().iloc[-2])
    mh2  = to_float(macd_o.macd_diff().iloc[-3])
    adxv = to_float(adx.iloc[-1]); atrv = to_float(atr.iloc[-1])
    vr   = to_float(vol.iloc[-1]) / to_float(vol_avg.iloc[-1]) if to_float(vol_avg.iloc[-1]) > 0 else 0
    bbwn = to_float(bb_width.iloc[-1]); bbm = to_float(bb.bollinger_mavg().iloc[-1])
    bbws = bb_width.dropna().tail(126)
    bbp20 = float(np.percentile(bbws, 20)) if len(bbws) >= 20 else 0
    bbp10 = float(np.percentile(bbws, 10)) if len(bbws) >= 10 else 0
    bb_squeeze    = bbwn <= bbp20
    bb_very_tight = bbwn <= bbp10
    h10  = to_float(high_10d.iloc[-1]); l10 = to_float(low_10d.iloc[-1])
    candle_red = float(close.iloc[-1]) < float(close.iloc[-2])

    swing_lows  = find_swing_lows(low,  60, 3)
    swing_highs = find_swing_highs(high, 60, 3)
    last_swing_low  = swing_lows[-1][1]  if swing_lows  else p * 0.95
    last_swing_high = swing_highs[-1][1] if swing_highs else p * 1.05
    higher_lows = len(swing_lows)  >= 2 and swing_lows[-1][1]  > swing_lows[-2][1]
    lower_highs = len(swing_highs) >= 2 and swing_highs[-1][1] < swing_highs[-2][1]

    today_chg = (float(close.iloc[-1]) - float(close.iloc[-2])) / float(close.iloc[-2]) * 100 \
                if len(close) >= 2 else 0

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
    }
    short_signals = {
        "trend_bearish":     (p < e8) and (e8 < e21),
        "stoch_overbought":  (k2 > 80) and (k1 > 80) and (k0 < k1) and (k0 < d0) and (k0 > 20),
        "bb_bear_squeeze":   bb_squeeze and (p < bbm),
        "macd_decel":        (mh0 < mh1 < mh2) and (mh0 < 0),
        "macd_cross_bear":   (ml < ms) and (mh0 < 0),
        "rsi_cross_bear":    (rsi2 > 50) and (rsi1 <= 50) and (rsi0 < rsi1) and (rsi0 > 28),
        "adx_bear":          adxv > 20 and (p < e21),
        "high_volume_down":  candle_red and (vr >= 2.0),
        "vol_breakdown":     (p <= l10 * 1.005) and (vr >= 1.8),
        "lower_highs":       lower_highs,
    }
    raw = {
        "p": p, "e8": e8, "e21": e21, "rsi0": rsi0, "rsi1": rsi1, "rsi2": rsi2,
        "k0": k0, "k1": k1, "k2": k2, "d0": d0, "ml": ml, "ms": ms,
        "mh0": mh0, "mh1": mh1, "mh2": mh2, "adx": adxv, "atr": atrv, "vr": vr,
        "bbwn": bbwn, "bbp20": bbp20, "bbm": bbm, "bb_squeeze": bb_squeeze,
        "bb_very_tight": bb_very_tight, "h10": h10, "l10": l10,
        "last_swing_low": last_swing_low, "last_swing_high": last_swing_high,
        "candle_red": candle_red, "today_chg": today_chg,
    }
    return long_signals, short_signals, raw


# ─────────────────────────────────────────────────────────────────────────────
# MAIN SCANNER
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def fetch_analysis(green_sectors, red_sectors, regime, skip_earnings,
                   top_n_sectors, live_sectors=None):
    sectors_data = live_sectors or {}
    long_results = []
    short_results= []

    long_ticker_sector  = {}
    short_ticker_sector = {}

    for sec in green_sectors[:top_n_sectors]:
        for t in sectors_data.get(sec, {}).get("stocks", []):
            if t not in long_ticker_sector:
                long_ticker_sector[t] = sec

    for sec in red_sectors[:top_n_sectors]:
        for t in sectors_data.get(sec, {}).get("stocks", []):
            if t not in short_ticker_sector:
                short_ticker_sector[t] = sec

    all_tickers = list(set(long_ticker_sector) | set(short_ticker_sector))
    total = len(all_tickers)
    if total == 0:
        return pd.DataFrame(), pd.DataFrame()

    progress_bar = st.progress(0)
    status_text  = st.empty()

    # ── PRE-FETCH all OHLCV in ONE batch call — massive speed improvement ──────
    status_text.text(f"📥 Batch downloading {total} stocks (one call)...")
    batch_data = {}
    try:
        raw_batch = yf.download(
            all_tickers,
            period="6mo",
            interval="1d",
            progress=False,
            group_by="ticker",
            threads=True,
            auto_adjust=True,
        )
        for tkr in all_tickers:
            try:
                if len(all_tickers) == 1:
                    df_t = raw_batch.copy()
                else:
                    if isinstance(raw_batch.columns, pd.MultiIndex):
                        df_t = raw_batch.xs(tkr, axis=1, level=1).copy()
                    else:
                        continue
                df_t = df_t.ffill().dropna()
                if len(df_t) >= 60:
                    batch_data[tkr] = df_t
            except Exception:
                continue
        status_text.text(f"✅ Batch download done — {len(batch_data)}/{total} stocks loaded")
    except Exception as e:
        status_text.text(f"Batch download failed ({e}), will fetch individually...")
    # ──────────────────────────────────────────────────────────────────────────

    min_score_strong_long  = 6 if regime == "BULL"               else 7
    min_prob_strong_long   = 0.72 if regime == "BULL"            else 0.78
    min_score_strong_short = 5 if regime in ("BEAR","CAUTION")   else 6
    min_prob_strong_short  = 0.68 if regime in ("BEAR","CAUTION") else 0.72

    for i, ticker in enumerate(all_tickers):
        try:
            status_text.text(f"Analysing {ticker} ({i+1}/{total})...")

            if skip_earnings:
                flag, _ = get_earnings_flag(ticker)
                if flag:
                    progress_bar.progress((i + 1) / total)
                    continue

            # Use pre-fetched batch data — fallback to individual fetch only if missing
            if ticker in batch_data:
                df = batch_data[ticker]
            else:
                df = fetch_ohlcv(ticker, days=130)

            if df is None or len(df) < 60:
                progress_bar.progress((i + 1) / total)
                continue

            long_sig, short_sig, raw = compute_all_signals(df)
            p    = raw["p"]
            atrv = raw["atr"]
            vr   = raw["vr"]
            today_chg = raw["today_chg"]

            # ── LONG ───────────────────────────────────────────────────────
            if ticker in long_ticker_sector:
                l_score    = sum(long_sig.values())
                l_bonus    = (0.06 if raw["bb_very_tight"] else 0) + (0.05 if vr >= 2.5 else 0)
                l_prob_raw = bayesian_prob(LONG_WEIGHTS, long_sig, l_bonus)
                rm         = 0.75 if regime == "BEAR" else 0.88 if regime == "CAUTION" else 1.0
                l_prob     = round(max(0.35, min(0.95, l_prob_raw * rm + (1-rm) * 0.40)), 4)
                l_top3     = (long_sig["stoch_confirmed"] or
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
                    l_risk       = max(p - l_stop, 0.01)
                    l_t1         = round(p + l_risk * 1.0, 2)
                    l_t2         = round(p + l_risk * 2.0, 2)

                    l_tags = []
                    if long_sig["stoch_confirmed"]: l_tags.append("STOCH BOUNCE")
                    if long_sig["bb_bull_squeeze"]: l_tags.append("BB BULL SQ")
                    if long_sig["macd_accel"]:      l_tags.append("MACD ACCEL")
                    if long_sig["vol_breakout"]:    l_tags.append("VOL BREAKOUT")
                    if long_sig["higher_lows"]:     l_tags.append("HIGHER LOWS")
                    if long_sig["rsi_confirmed"]:   l_tags.append("RSI>50")
                    if vr >= 2.5:                   l_tags.append("VOL SURGE")

                    long_results.append({
                        "Ticker":       ticker,
                        "Sector":       f"🟢 {long_ticker_sector[ticker]}",
                        "Action":       l_action,
                        "Rise Prob":    f"{l_prob * 100:.1f}%",
                        "Prob Tier":    prob_label(l_prob),
                        "Score":        f"{l_score}/10",
                        "Today %":      f"{today_chg:+.2f}%",
                        "Signals":      " | ".join(l_tags) if l_tags else "–",
                        "Price":        f"${p:.2f}",
                        "RSI":          round(raw["rsi0"], 1),
                        "Stoch K":      round(raw["k0"],   1),
                        "ADX":          round(raw["adx"],  1),
                        "Vol Ratio":    round(vr, 2),
                        "BB Squeeze":   "YES" if long_sig["bb_bull_squeeze"] else "–",
                        "ATR Stop":     f"${l_atr_stop:.2f}",
                        "Swing Stop":   f"${l_swing_stop:.2f}",
                        "Best Stop":    f"${l_stop:.2f}",
                        "Target 1:1":   f"${l_t1:.2f}",
                        "Target 1:2":   f"${l_t2:.2f}",
                        "Pos/$1k risk": int(1000 / l_risk) if l_risk > 0 else 0,
                        "Source":       "polygon" if _polygon_available else "yfinance",
                    })

            # ── SHORT ──────────────────────────────────────────────────────
            if ticker in short_ticker_sector:
                s_score        = sum(short_sig.values())
                s_regime_bonus = 0.08 if regime == "BEAR" else 0.03 if regime == "CAUTION" else 0
                s_prob_raw     = bayesian_prob(SHORT_WEIGHTS, short_sig, s_regime_bonus)
                s_prob         = round(max(0.35, min(0.95, s_prob_raw)), 4)
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
                    s_risk       = max(s_cover - p, 0.01)
                    s_t1         = round(p - s_risk * 1.0, 2)
                    s_t2         = round(p - s_risk * 2.0, 2)

                    s_tags = []
                    if short_sig["stoch_overbought"]:  s_tags.append("STOCH ROLLOVER")
                    if short_sig["bb_bear_squeeze"]:   s_tags.append("BB BEAR SQ")
                    if short_sig["macd_decel"]:        s_tags.append("MACD DECEL")
                    if short_sig["vol_breakdown"]:     s_tags.append("VOL BREAKDOWN")
                    if short_sig["lower_highs"]:       s_tags.append("LOWER HIGHS")
                    if short_sig["rsi_cross_bear"]:    s_tags.append("RSI<50")
                    if short_sig["high_volume_down"]:  s_tags.append("DIST DAY")

                    short_results.append({
                        "Ticker":          ticker,
                        "Sector":          f"🔴 {short_ticker_sector[ticker]}",
                        "Action":          s_action,
                        "Fall Prob":       f"{s_prob * 100:.1f}%",
                        "Prob Tier":       prob_label(s_prob),
                        "Score":           f"{s_score}/10",
                        "Today %":         f"{today_chg:+.2f}%",
                        "Signals":         " | ".join(s_tags) if s_tags else "–",
                        "Price":           f"${p:.2f}",
                        "RSI":             round(raw["rsi0"], 1),
                        "Stoch K":         round(raw["k0"],   1),
                        "ADX":             round(raw["adx"],  1),
                        "Vol Ratio":       round(vr, 2),
                        "ATR Stop":        f"${s_atr_stop:.2f}",
                        "Swing Stop":      f"${s_swing_stop:.2f}",
                        "Cover Stop":      f"${s_cover:.2f}",
                        "Target 1:1":      f"${s_t1:.2f}",
                        "Target 1:2":      f"${s_t2:.2f}",
                        "Pos/$1k risk":    int(1000 / s_risk) if s_risk > 0 else 0,
                        "Regime Boost":    "YES" if regime in ("BEAR","CAUTION") else "–",
                        "Source":          "polygon" if _polygon_available else "yfinance",
                    })

        except Exception:
            pass
        progress_bar.progress((i + 1) / total)

    status_text.empty()
    progress_bar.empty()

    def make_df(rows, prob_col):
        if not rows: return pd.DataFrame()
        df_out = pd.DataFrame(rows)
        df_out["_s"] = df_out[prob_col].str.rstrip("%").astype(float)
        return df_out.sort_values("_s", ascending=False).drop(columns="_s")

    return make_df(long_results, "Rise Prob"), make_df(short_results, "Fall Prob")


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
st.sidebar.header("Scan settings")
top_n_sectors  = st.sidebar.slider("Top N green/red sectors to scan", 1, 6, 3)
min_prob_long  = st.sidebar.slider("Min LONG rise prob (%)",  40, 95, 62)
min_prob_short = st.sidebar.slider("Min SHORT fall prob (%)", 40, 95, 60)
skip_earnings  = st.sidebar.checkbox("Skip earnings within 7 days", True)

st.sidebar.markdown("---")
st.sidebar.header("Long filters")
req_stoch = st.sidebar.checkbox("Must have Stoch bounce",      False)
req_bb    = st.sidebar.checkbox("Must have BB bull squeeze",   False)
req_accel = st.sidebar.checkbox("Must have MACD acceleration", False)

st.sidebar.markdown("---")
st.sidebar.header("Short filters")
req_s_stoch = st.sidebar.checkbox("Must have Stoch rollover",    False)
req_s_bb    = st.sidebar.checkbox("Must have BB bear squeeze",   False)
req_s_decel = st.sidebar.checkbox("Must have MACD deceleration", False)

st.sidebar.markdown("---")
# Show data source status
st.sidebar.header("Data source status")
st.sidebar.markdown(
    f"{'✅' if _polygon_available else '❌'} **Polygon.io** "
    f"({'connected' if _polygon_available else 'no key'})\n\n"
    f"{'✅' if _fd_available else '⚠️'} **FinanceDatabase** "
    f"({'installed' if _fd_available else 'not installed — run: pip install financedatabase'})\n\n"
    f"✅ **yfinance** (fallback)"
)

if not _fd_available:
    st.sidebar.warning("Install financedatabase for better ETF holdings:\n`pip install financedatabase`")

# Debug — shows whether key was found (never shows the actual key)
st.sidebar.markdown("---")
st.sidebar.markdown("**🔍 Key debug**")
st.sidebar.markdown(
    f"`.env` path: `{Path(__file__).parent / '.env'}`\n\n"
    f"`.env` exists: `{(Path(__file__).parent / '.env').exists()}`\n\n"
    f"Key loaded: `{'YES ✅ (' + str(len(POLYGON_API_KEY)) + ' chars)' if POLYGON_API_KEY else 'NO ❌'}`"
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
c4.metric("Data", "Polygon" if _polygon_available else "yfinance")

if regime == "BEAR":
    st.error("🔴 **Bear market** — Long thresholds raised · Short probability boosted")
elif regime == "CAUTION":
    st.warning("🟡 **Caution zone** — Long probabilities reduced · Short boosted slightly")

st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────────────────────────
tab_sectors, tab_long, tab_short, tab_both, tab_diag = st.tabs([
    "🗂️ Sector Heatmap",
    "📈 Long Setups",
    "📉 Short Setups",
    "🔄 Side by Side",
    "🔍 Diagnostics",
])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — SECTOR HEATMAP
# ─────────────────────────────────────────────────────────────────────────────
with tab_sectors:
    st.markdown("### Live Sector Heatmap")
    st.caption(f"Data source: {'Polygon.io' if _polygon_available else 'yfinance'} · Refreshes every 15 min")
    sector_df = get_sector_performance_polygon()

    if sector_df.empty:
        st.warning("Could not fetch sector data.")
    else:
        def tile_color(pct):
            if   pct >  2.0: return "#1a7a3a","#ffffff"
            elif pct >  0.5: return "#27ae60","#ffffff"
            elif pct >  0.1: return "#a9dfbf","#145a32"
            elif pct < -2.0: return "#922b21","#ffffff"
            elif pct < -0.5: return "#e74c3c","#ffffff"
            elif pct < -0.1: return "#f5b7b1","#7b241c"
            else:            return "#e8e8e8","#555555"

        html = "<div style='display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-bottom:16px'>"
        for _, row in sector_df.iterrows():
            bg, fg = tile_color(row["Today %"])
            arrow  = "▲" if row["Today %"] > 0 else ("▼" if row["Today %"] < 0 else "—")
            fived  = row.get("5d %", 0.0)
            html += f"""<div style='background:{bg};color:{fg};border-radius:8px;padding:10px 12px'>
              <div style='font-size:10px;font-weight:700;opacity:.8'>{row['ETF']}</div>
              <div style='font-size:13px;font-weight:700;margin:2px 0'>{row['Sector']}</div>
              <div style='font-size:22px;font-weight:800'>{arrow} {row['Today %']:+.2f}%</div>
              <div style='font-size:11px;opacity:.85'>5d: {fived:+.2f}%  ·  ${row['Price']}</div>
            </div>"""
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)

        green_list = sector_df[sector_df["Today %"] >  0.1]["Sector"].tolist()
        red_list   = sector_df[sector_df["Today %"] < -0.1]["Sector"].tolist()
        flat_list  = sector_df[(sector_df["Today %"] >= -0.1) & (sector_df["Today %"] <= 0.1)]["Sector"].tolist()

        cg, cr, cf = st.columns(3)
        with cg:
            st.success("🟢 **Green — scan for LONGS**\n\n" +
                       "\n\n".join(f"**{s}** ({sector_df[sector_df['Sector']==s]['Today %'].values[0]:+.2f}%)"
                                   for s in green_list))
        with cr:
            st.error("🔴 **Red — scan for SHORTS**\n\n" +
                     "\n\n".join(f"**{s}** ({sector_df[sector_df['Sector']==s]['Today %'].values[0]:+.2f}%)"
                                 for s in red_list))
        with cf:
            st.info("⚪ **Flat — skip**\n\n" + "\n\n".join(flat_list))

# ─────────────────────────────────────────────────────────────────────────────
# SCAN BUTTON
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
col_btn, col_info = st.columns([1, 3])
with col_btn:
    run = st.button("🚀 Run Sector-Driven Scan", type="primary",
                    disabled=not POLYGON_API_KEY and not _fd_available)
with col_info:
    sdf = get_sector_performance_polygon()
    if not sdf.empty:
        gn = sdf[sdf["Today %"] >  0.1]["Sector"].tolist()
        rn = sdf[sdf["Today %"] < -0.1]["Sector"].tolist()
        st.info(
            f"Scanning top **{top_n_sectors} green**: {', '.join(gn[:top_n_sectors]) or 'none'} · "
            f"top **{top_n_sectors} red**: {', '.join(rn[:top_n_sectors]) or 'none'}"
        )

if run:
    sdf = get_sector_performance_polygon()
    green_sectors = sdf[sdf["Today %"] >  0.1]["Sector"].tolist()
    red_sectors   = sdf[sdf["Today %"] < -0.1]["Sector"].tolist()

    if not green_sectors and not red_sectors:
        st.warning("All sectors flat. Try again when markets are moving.")
    else:
        # Step 1 — fetch live ETF holdings
        st.info("📡 Fetching live ETF holdings (FinanceDatabase + Polygon)...")
        live_sectors = fetch_sector_constituents_fd(target_per_sector=40)

        with st.expander("📋 Holdings fetched per sector", expanded=False):
            rows = []
            for sn, sd in live_sectors.items():
                rows.append({
                    "Sector":    sn,
                    "ETF":       sd.get("etf",""),
                    "Source":    sd.get("source","–"),
                    "# Stocks":  sd.get("count", len(sd.get("stocks",[]))),
                    "Top picks": ", ".join(sd.get("stocks",[])[:8])+"..."
                                 if sd.get("stocks") else "none",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # Step 2 — run signal scan
        with st.spinner("Scanning stocks..."):
            df_long, df_short = fetch_analysis(
                tuple(green_sectors), tuple(red_sectors),
                regime, skip_earnings, top_n_sectors, live_sectors
            )

        # Apply filters
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

        st.session_state["df_long"]  = df_long
        st.session_state["df_short"] = df_short

df_long  = st.session_state.get("df_long",  pd.DataFrame())
df_short = st.session_state.get("df_short", pd.DataFrame())

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — LONG
# ─────────────────────────────────────────────────────────────────────────────
with tab_long:
    if df_long.empty:
        st.info("Run the scan to see long setups from green sectors.")
    else:
        strong_l  = df_long[df_long["Action"] == "STRONG BUY"]
        watch_hql = df_long[df_long["Action"] == "WATCH – HQ"]
        watch_dvl = df_long[df_long["Action"] == "WATCH – DEV"]

        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("Strong Buy",    len(strong_l))
        c2.metric("High Quality",  len(watch_hql))
        c3.metric("Developing",    len(watch_dvl))
        c4.metric("Sectors",       df_long["Sector"].nunique())
        c5.metric("Top Rise Prob", df_long["Rise Prob"].iloc[0] if not df_long.empty else "–")

        if not df_long.empty:
            sec_cnt = df_long.groupby("Sector").size().reset_index(name="Setups")
            st.dataframe(sec_cnt, use_container_width=True, hide_index=True)

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
    if df_short.empty:
        st.info("Run the scan to see short setups from red sectors.")
    else:
        strong_s  = df_short[df_short["Action"] == "STRONG SHORT"]
        watch_hqs = df_short[df_short["Action"] == "WATCH SHORT – HQ"]
        watch_dvs = df_short[df_short["Action"] == "WATCH SHORT – DEV"]

        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("Strong Short",  len(strong_s))
        c2.metric("High Quality",  len(watch_hqs))
        c3.metric("Developing",    len(watch_dvs))
        c4.metric("Sectors",       df_short["Sector"].nunique())
        c5.metric("Top Fall Prob", df_short["Fall Prob"].iloc[0] if not df_short.empty else "–")

        if not df_short.empty:
            sec_cnt = df_short.groupby("Sector").size().reset_index(name="Setups")
            st.dataframe(sec_cnt, use_container_width=True, hide_index=True)

        st.markdown("### 🔥 Strong Short")
        show_table(strong_s, "strong short", "Fall Prob")
        st.markdown("### 👀 High Quality Short Watch")
        show_table(watch_hqs, "high quality short", "Fall Prob")
        st.markdown("### 📋 Developing Short Setups")
        show_table(watch_dvs, "developing short", "Fall Prob")

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

# ─────────────────────────────────────────────────────────────────────────────
# TAB 5 — DIAGNOSTICS
# ─────────────────────────────────────────────────────────────────────────────
with tab_diag:
    st.markdown("### Ticker diagnostics")
    diag_input = st.text_input("Enter ticker(s)", placeholder="NVDA, TSLA")
    for t in [x.strip().upper() for x in diag_input.split(",") if x.strip()]:
        with st.expander(f"{t} — condition breakdown", expanded=True):
            df_t = fetch_ohlcv(t, days=130)
            if df_t is None or len(df_t) < 60:
                st.error(f"Insufficient data for {t}")
                continue
            ls, ss, raw = compute_all_signals(df_t)
            l_score = sum(ls.values()); s_score = sum(ss.values())
            l_prob  = bayesian_prob(LONG_WEIGHTS,  ls)
            s_prob  = bayesian_prob(SHORT_WEIGHTS, ss)

            def tick(ok, detail=""):
                return ("PASS  " + detail) if ok else ("FAIL  " + detail)

            result = {
                "Data source":        "Polygon" if _polygon_available else "yfinance",
                "Price":              f"${raw['p']:.2f}",
                "EMA8 / EMA21":       f"${raw['e8']:.2f} / ${raw['e21']:.2f}",
                "RSI":                f"{raw['rsi2']:.1f}→{raw['rsi1']:.1f}→{raw['rsi0']:.1f}",
                "Stoch K":            f"{raw['k2']:.1f}→{raw['k1']:.1f}→{raw['k0']:.1f}  D={raw['d0']:.1f}",
                "MACD hist":          f"{raw['mh2']:.4f}→{raw['mh1']:.4f}→{raw['mh0']:.4f}",
                "ADX / Vol ratio":    f"{raw['adx']:.1f} / {raw['vr']:.2f}×",
                "── LONG ──": "",
                "1. Trend bullish":   tick(ls["trend_daily"]),
                "2. Stoch bounce":    tick(ls["stoch_confirmed"]),
                "3. BB bull squeeze": tick(ls["bb_bull_squeeze"]),
                "4. MACD accel":      tick(ls["macd_accel"]),
                "5. MACD cross":      tick(ls["macd_cross"]),
                "6. RSI >50 conf":    tick(ls["rsi_confirmed"]),
                "7. ADX >20":         tick(ls["adx"],   f"{raw['adx']:.1f}"),
                "8. Vol >1.5×":       tick(ls["volume"],f"{raw['vr']:.2f}×"),
                "9. Vol breakout":    tick(ls["vol_breakout"]),
                "10. Higher lows":    tick(ls["higher_lows"]),
                "LONG result":        f"{l_score}/10  →  {l_prob*100:.1f}%  ({prob_label(l_prob)})",
                "── SHORT ──": "",
                "1. Trend bearish":   tick(ss["trend_bearish"]),
                "2. Stoch rollover":  tick(ss["stoch_overbought"]),
                "3. BB bear squeeze": tick(ss["bb_bear_squeeze"]),
                "4. MACD decel":      tick(ss["macd_decel"]),
                "5. MACD cross bear": tick(ss["macd_cross_bear"]),
                "6. RSI <50 conf":    tick(ss["rsi_cross_bear"]),
                "7. ADX >20 down":    tick(ss["adx_bear"]),
                "8. Dist day":        tick(ss["high_volume_down"]),
                "9. Vol breakdown":   tick(ss["vol_breakdown"]),
                "10. Lower highs":    tick(ss["lower_highs"]),
                "SHORT result":       f"{s_score}/10  →  {s_prob*100:.1f}%  ({prob_label(s_prob)})",
            }
            for k, v in result.items():
                if str(v) == "":
                    st.markdown(f"**{k}**"); continue
                ca, cb = st.columns([3, 5])
                ca.markdown(f"`{k}`"); vs = str(v)
                if vs.startswith("PASS"):   cb.success(vs)
                elif vs.startswith("FAIL"): cb.error(vs)
                else:                       cb.write(vs)