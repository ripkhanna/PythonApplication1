"""Help tab renderer — updated for Breakout Scanner, universe_data refactor, and all features."""


def render_help(ctx: dict) -> None:
    st = ctx["st"]

    st.markdown("## ❓ Swing Scanner — Complete Guide")
    st.caption(
        "19 tabs · 8 strategies · US + SGX + India + HK · "
        "Breakout Scanner · Bayesian engine · Operator layer · Options signals"
    )

    # ── What's new ────────────────────────────────────────────────────────────
    with st.expander("🆕 What changed recently", expanded=True):
        st.markdown("""
### Latest build — v13.90

#### ⚡ Breakout Scanner (new tab)
A unified, market-aware breakout discovery engine added as a dedicated tab.
Three signals are combined into a single ranked table with a **Score 0–100**:
- **🔥 High-Volume Breakout** — price > N-day high with volume ≥ N× 20-day average
- **📈 52-Week High Setup** — stock within X% of its 52-week high
- **🚀 Market Mover** — Yahoo live gainers / losers / most-active feed (US only)

Universe dropdown lets you pick which index pool to scan (S&P 500, NASDAQ-100, All US, etc.).
Market dropdown correctly filters to market-specific stocks only — SGX shows only `.SI`, India only `.NS`, HK only `.HK`.

#### 🌍 Universe refactor (universe_data.py)
All ticker lists are now defined in a single file (`tabs/universe_data.py`) and imported everywhere:
- `config_core.py` no longer defines its own lists — it imports from `universe_data`
- `top_movers_tab.py` delegates to `get_tickers_for_market()` instead of reading `g` globals directly
- Every market is now `existing curated list + actual index components`, merged and deduplicated
- Zero ticker overlap between markets (verified)

| Market | Total tickers | How built |
|--------|--------------|-----------|
| 🇺🇸 US | 746 | Curated watchlist + S&P 500 (~489) + NASDAQ-100 (~108) |
| 🇸🇬 SGX | 111 | STI-30 + REITs + growth + SGX Mainboard liquid |
| 🇮🇳 India | 172 | Curated + Nifty 50 + Nifty Next-50 + Midcap-50 |
| 🇭🇰 HK | 137 | Curated + Hang Seng + HSI Tech constituents |

#### Previous milestones
- **HK market** added as full market radio option with 137 `.HK` tickers.
- **PSM Strategy** — 5–7 day swing ranking with PI Proxy, PSS Score, Buy Condition.
- **High Conviction** strategy — all 5 signal categories must fire simultaneously.
- **Support Entry** — surfaces stocks AT support, not already extended.
- **Premarket Momentum** — gap-up names 30 min before open.
- **8 Swing Strategies** in sidebar.
- **Master Yahoo cache** — one broad download per market, strategies refilter it.
- **No-new-bar optimization** — skips expensive re-download when Yahoo has no newer bar.
- **Movers/Losers tab** — Top Gainers, Losers, Volume Leaders across all markets.
- **Speed**: ~2 min scan (was ~15 min) via parallel pre-fetch + shared session.
        """)

    # ── Quick start ───────────────────────────────────────────────────────────
    with st.expander("🚀 Quick start — daily workflow"):
        st.markdown("""
1. Pick market in sidebar: **US · SGX · India · HK**.
2. Choose a **Swing strategy** from the dropdown.
3. Add must-scan names in **Always include tickers** — e.g. `UUUU, APP, NVDA, S58.SI, 0700.HK`.
4. Click **🚀 Scan**.
5. Review tabs in this order:

```
🚀 Movers/Losers → 🗂️ Sector Heatmap → ⚡ Breakout Scanner
    → 📈 Long Setups → 🎯 Swing Picks → 📋 Trade Desk → 🔬 Stock Analysis
```

**Best strategy by time of day:**

| Time (local market) | Best strategy |
|---|---|
| 30 min before open | **Premarket Momentum** — catch gap-up names |
| First 30 min after open | **Support Entry** — dips at MA levels |
| Mid-day / end of day | **Balanced**, **High Conviction**, or **PSM Strategy** |
| Any time for breakouts | **⚡ Breakout Scanner** tab — independent of main scan |
| Quiet/choppy markets | **Discovery** for watchlist building |
| Want fewer but stronger | **High Conviction** or **PSM Strategy** |
        """)

    # ── 8 strategies ─────────────────────────────────────────────────────────
    with st.expander("🎯 All 8 strategies — when to use each"):
        st.markdown("""
| Strategy | Best for | How it works | Expected results |
|---|---|---|---|
| **Strict** | Strong markets, want A+ only | Very high probability + score gate | 3–10 stocks |
| **Balanced** | Normal daily trading (default) | Practical trend + volume + operator | 15–40 stocks |
| **Discovery** | Quiet markets, building watchlist | Wide net, lower thresholds | 40–80+ stocks |
| **Support Entry ⭐** | Morning scan, before the move | Only stocks AT MA20/MA60/VWAP/swing low | 5–20 stocks |
| **Premarket Momentum 🚀** | 30 min before open | +1–8% PM gain + intact technical trend | 5–15 stocks |
| **High Volume 📊** | Finding active names right now | Unusual volume / breakout / pocket pivot | 10–30 stocks |
| **High Conviction 🎯** | Highest win-rate shortlist | ALL 5 signal categories must confirm | 5–15 stocks |
| **PSM Strategy 🏆** | 5–7 day swing candidates | PI Proxy + PSS Score + rise prob + volume + entry quality | 5–25 stocks |

### PSM Strategy — practical swing ranking
PSM answers: **which stocks are worth a 5–7 day swing trade right now?**

| Component | Meaning |
|---|---|
| **PI Proxy** | Return-potential proxy; higher = stronger potential move |
| **PSS Score** | Professional Swing Signal score; counts institutional confirmations |
| **Rise Probability** | Bayesian probability from the scanner engine |
| **Volume Ratio** | Move has real activity behind it |
| **Entry Quality** | Buyable now / confirmation-only / extended / avoid |
| **Practical Swing Rank** | Penalises extended/high-risk, rewards tradable setups |

### PSM tiers
| Tier | Meaning |
|---|---|
| **STRONG BUY – PSM ELITE** | Highest-quality setup; strongest confirmation and practical entry |
| **BUY – PSM STRONG** | Strong setup; good probability, volume, and entry quality |
| **BUY – PSM QUALIFIED** | Actionable but condition-based — follow the Buy Condition column |

### PSM display columns
| Column | Meaning |
|---|---|
| **Rank** | Practical swing rank in the PSM grid |
| **View** | Plain-English decision: Best balanced swing / Best aggressive momentum / Good quality swing / Watch only / Strong but extended |
| **Buy Condition** | Practical trigger with stop and TP1 where available |
| **PI Proxy** | Return-potential proxy |
| **Why Selected** | Short explanation of PI / PSS / volume signals that passed PSM |

### PSM compare shortlist
When you want PSM to rank **only a custom list** (e.g. `GRND, IREN, WMG, QCOM, DDOG`):
type those tickers into the compare shortlist box. PSM recalculates Rank/View/Buy Condition
for that shortlist only instead of the full universe.

### Support Entry — tiers explained
| Tier | Signal | Meaning |
|---|---|---|
| 🔵 Tier 1 — MA60 dip | Price ±1.5% of MA60 + vol declining | Strongest — institutional buyers step in here |
| 🟢 Tier 2 — MA20 dip | Price ±1.5% of MA20 | Common swing entry, trend intact above MA60 |
| 🟡 Tier 3 — Swing low | Within 2% of last swing low | Structural support from price action |
| 🟣 Tier 4 — MA200 | Near 200-day MA | Long-term support, recovery play |
| ⚪ Tier 5 — VWAP | Holding above VWAP | Intraday level, weakest |

**Gate:** `today_chg_pct ≤ 5%` — stocks already up >5% are hidden.

### Premarket Momentum — tiers explained
| Tier | PM Change | Action |
|---|---|---|
| 🚀 Tier A | +3% to +8% | High conviction — enter near the open |
| 📈 Tier B | +1% to +3% | Wait for first 5-min candle to confirm direction |
| 🟡 Tier C/D | Live momentum | Technical momentum when PM data unavailable |

**Gate:** above MA60 + core trend intact + RSI < 72 + no trap risk.

### High Conviction — 5 categories
All five must fire at least one signal:

| Category | Signals checked |
|---|---|
| 📈 Trend | EMA8>EMA21, weekly trend, golden cross, full MA stack |
| ⚡ Momentum | MACD accel, stoch bounce, RSI>50, momentum 3d |
| 🔊 Volume | Vol breakout, vol surge, pocket pivot, operator accumulation |
| 🏗️ Structure | Higher lows, VCP tightness, strong close, bull candle |
| 🌍 Market | RS > SPY, RS momentum, sector leader, near 52W high |

Look for `HC[T+M+V+S+X](5/5)` in the Signals column to confirm all five fired.
        """)

    # ── Breakout Scanner ──────────────────────────────────────────────────────
    with st.expander("⚡ Breakout Scanner — unified breakout discovery"):
        st.markdown("""
The **⚡ Breakout Scanner** is an independent tab that scores every stock across
three signals simultaneously and ranks them by a composite **Score (0–100)**.
It does not use the sidebar strategy — it runs its own market-filtered scan.

### How to use it
1. Select **Market** (US / SGX / India / HK) — this filters the stock pool.
2. Select **Universe** — which index or group to scan.
3. Adjust signal parameters (optional).
4. Click **Run Scanner**.

### Universe options per market
| Market | Universe choices |
|---|---|
| 🇺🇸 US | S&P 500 (~489) · NASDAQ-100 (~108) · S&P500+NDX (~517) · Growth watchlist (~337) · S&P500+Growth (~742) · All US (~746) |
| 🇸🇬 SGX | SGX Mainboard (~111 stocks) |
| 🇮🇳 India | Nifty 50 · Nifty 150 (50 + Next-50 + Midcap-50) |
| 🇭🇰 HK | Hang Seng + HSI Tech (~137 stocks) |

### Three signals combined
| Signal | What it detects | Max Score |
|---|---|---|
| 🔥 **High-Volume Breakout** | Price > N-day high AND volume ≥ N× 20-day average | 30 pts (vol) + 20 pts (breakout) |
| 📈 **52-Week High Setup** | Stock within X% of its 52-week high | 25 pts |
| 🚀 **Market Mover** | Yahoo live gainers / losers / most-active (US only) | 5 pts |
| 📊 **Momentum** | Absolute daily Chg % | 10 pts |
| 🏆 **New 52W High bonus** | Price = 52-week high | 10 pts |

### Score breakdown
```
0–20   Low activity — watchlist only
21–40  Moderate signal — worth monitoring
41–60  Good setup — one or two signals confirmed
61–80  Strong — multiple signals confirmed simultaneously
81–100 Elite — breakout + 52W high + mover + momentum all firing
```

### Key columns
| Column | Meaning |
|---|---|
| **Score** | Composite 0–100 combining all three signals |
| **Signals** | Active signal badges: Vol Breakout · 52W Setup · New 52W High · Mover |
| **Vol Ratio** | Today's volume ÷ 20-day average volume |
| **Today Vol** | Absolute volume today |
| **vs 52W %** | How far price is below the 52-week high (0% = at the high) |
| **In Range %** | Where price sits in the 52-week low→high range (100% = at the high) |
| **Breakout %** | % above the N-day high |
| **ATR %** | Daily volatility as % of price — ≥3% is useful swing range |
| **3M Return %** | 63-session return — momentum context |

### Signal parameters
| Parameter | Default | Effect |
|---|---|---|
| Breakout window (days) | 20 | Price must exceed the prior N-day high |
| Min vol ratio × | 2.0 | Volume must be ≥ N× the 20-day average |
| 52W high within % | 5% | Include stocks within this % of their 52-week high |
| Max tickers | 300 | Cap on universe size scanned (larger = slower) |

### Top Picks panel
Stocks scoring ≥ 40 appear as metric cards above the table showing Price, Chg%, Score, Vol Ratio, and 52W proximity.

### Market filter note
Yahoo's predefined screeners (day_gainers, day_losers, most_actives) return **US-listed stocks regardless of region parameter**.
For SGX, India, and HK scans the mover feed is skipped entirely — results contain only tickers from the selected market's universe.
        """)

    # ── Tab guide ─────────────────────────────────────────────────────────────
    with st.expander("🧭 Tab guide — all 19 tabs"):
        st.markdown("""
| Tab | Purpose |
|---|---|
| 🗂️ **Sector Heatmap** | Market direction first — color tiles, green/red sector summary |
| 📋 **Trade Desk** | Execution: entry zone, stop, target, R/R, position size calculator |
| 📈 **Long Setups** | Bullish swing candidates — strategy-aware sections and columns |
| 🎯 **Swing Picks** | Final shortlist — Bayesian + operator + sector + news ranking |
| 🚀 **Movers/Losers** | Top Gainers, Top Losers, and Volume Leaders across all markets |
| 🌅 **Pre-Market** | Pre-market gappers and overnight movers before the open |
| 📉 **Short Setups** | Bearish candidates — best for liquid US names |
| 🪤 **Operator Activity** | Smart-money footprints across scanned universe |
| ⚡ **Breakout Scanner** | Independent scanner: Vol Breakout + 52W High + Market Mover combined score |
| 🔄 **Side by Side** | Compare best longs vs best shorts simultaneously |
| 📊 **ETF Holdings** | Add ETF constituents to the scan universe |
| 🔬 **Stock Analysis** | One-stock deep dive — operator label matches scanner |
| 📅 **Earnings** | Earnings risk calendar — avoid or trade upcoming events |
| 📰 **Event Predictor** | Contract / order / upgrade / dilution keyword scan |
| 🌱 **Long Term** | 1–5 year quality scoring + near-support filter |
| 🔍 **Diagnostics** | Cloud debug — errors, ticker list, cache status, always-include check |
| 🧪 **Accuracy Lab** | Signal backtest and validation |
| 🧠 **Strategy Lab** | ML research layer |
| ❓ **Help** | This guide |

### Recommended daily workflow order
```
🚀 Movers/Losers    ← what's moving right now?
🗂️ Sector Heatmap  ← which sectors are leading?
⚡ Breakout Scanner ← which stocks are breaking out?
📈 Long Setups      ← strategy scan results
🎯 Swing Picks      ← final shortlist
📋 Trade Desk       ← position sizing and execution
🔬 Stock Analysis   ← confirm your top 1–3 names
```
        """)

    # ── Long/Short setups columns ─────────────────────────────────────────────
    with st.expander("📈 Long / 📉 Short Setups — columns explained"):
        st.markdown("""
### Long setup action labels (Balanced mode)
| Label | Meaning |
|---|---|
| 🔥 STRONG BUY | Highest accuracy: prob + score + trend + volume + no trap |
| WATCH – HIGH QUALITY | Actionable, one confirmation short of STRONG BUY |
| WATCH – DEVELOPING | Setup forming, not yet fully confirmed |
| WATCH – TRAP RISK | Looks good but has false breakout / gap chase warning |

### Long setup action labels (PSM Strategy)
| Label | Meaning |
|---|---|
| STRONG BUY – PSM ELITE | Highest-quality 5–7 day swing candidate |
| BUY – PSM STRONG | Strong PSM setup with good confirmation |
| BUY – PSM QUALIFIED | Actionable but condition-based — follow Buy Condition column |

### Long setup action labels (Support Entry mode)
| Label | Meaning |
|---|---|
| BUY – MA60 SUPPORT | Tier 1 support, cleanest R/R |
| BUY – MA20 SUPPORT | Tier 2 support |
| WATCH – SWING LOW SUPPORT | Tier 3, structural level |
| WATCH – VWAP SUPPORT | Tier 5, intraday level |

### Key columns
| Column | What to look for |
|---|---|
| **Entry Quality** | ✅ BUY = enter now · 👀 WATCH = monitor · ⏳ WAIT = extended · 🚫 AVOID = broken |
| **Rise Prob** | Bayesian probability — above 70% is high quality |
| **Setup Type** | Pullback / Breakout / Continuation / Support / PM Momentum |
| **Operator** | 🔥 STRONG OPERATOR = smart money accumulating |
| **Trap Risk** | FALSE BO / GAP CHASE / DISTRIB — reduce size or skip |
| **VWAP** | ABOVE = buyers in control |
| **MA60 Stop** | Place stop just below — setup is invalid if broken |
| **TP1/2/3** | +10% / +15% / +20% targets — take partial at TP1 |
| **RSI Now** | Support Entry mode only — want 28–65 |
| **PM Chg%** | Premarket mode only — pre-market move % |
| **Support Tier** | Support Entry mode only — Tier 1 is strongest |
        """)

    # ── Operator / Trap ───────────────────────────────────────────────────────
    with st.expander("🪤 Operator Activity vs Trap Patterns"):
        st.markdown("""
Two separate scoring systems — both visible in **Stock Analysis** and the **Operator Activity** tab.

### Operator Score (accumulation)
Measures smart-money buying footprints:
- Green candle on 2× average volume
- Strong close (price in top 25% of day range)
- OBV rising 5 consecutive days
- Price at 10-day high with volume
- Above VWAP
- Red candle but closes off lows on high volume (absorption)

| Label | Score | Meaning |
|---|---|---|
| 🔥 STRONG OPERATOR | ≥ 6 | Multiple accumulation confirmations |
| 🟢 ACCUMULATION | ≥ 4 | Good signs of buying pressure |
| 🟡 WEAK SIGNS | ≥ 2 | Some activity, not conclusive |
| ⚪ NONE | 0–1 | No operator footprint |

### Trap Patterns (manipulation / risk flags)
- **False breakout** — new high on volume but closes weak
- **Gap chase risk** — today up >7% on 2.5× volume
- **Distribution** — high volume + tiny move + weak close

**A stock can show 🔥 STRONG OPERATOR and zero trap patterns — that is the ideal setup.**
        """)

    # ── Long Term tab ─────────────────────────────────────────────────────────
    with st.expander("🌱 Long Term tab — quality + support scoring"):
        st.markdown("""
Separate from swing trading — for 1–5 year holds.

### Quality score (0–10)
| Signal | Points |
|---|---|
| Revenue growth > 10% | +2 |
| EPS growth > 15% | +2 |
| ROE > 15% | +1 |
| Profit margin > 15% | +1 |
| Debt/equity < 100 | +1 |
| Price above MA200 | +1 |
| Analyst target above price | +1 |
| BUY/STRONG BUY rating | +1 |

### Support score (0–5)
Each worth +1:
1. Price within −20%…+8% of MA50
2. Price within −8%…+18% of MA200
3. RSI-14 between 25 and 58 (accumulation zone)
4. Price 8–45% below 52-week high (healthy correction)
5. Price 8–65% above 52-week low (support floor intact)

Tick **📍 Near support only** to show only stocks at technically attractive long-term entries.

### Filter bar
| Filter | Use |
|---|---|
| 🔍 Ticker / name | Search any stock |
| Horizon | Core Hold / Buy & Hold / Accumulate |
| Sector | Filter by sector |
| 📍 Near support | Only stocks at support |
| Min support score | 0–5 slider |
| Min analyst upside | Skip low-conviction targets |
        """)

    # ── Movers and cache ──────────────────────────────────────────────────────
    with st.expander("🚀 Movers/Losers tab + master cache"):
        st.markdown("""
### Movers/Losers tab
Use this tab to see what is active before selecting a strategy.

| Section | Meaning |
|---|---|
| **Top Gainers** | Biggest positive movers for the selected market / timeframe |
| **Top Losers** | Biggest negative movers |
| **Volume Leaders** | Most active names by relative/absolute volume |

Supported markets: US · SGX · India · HK

### Master Yahoo cache
The scanner stores one broad Yahoo-enriched master scan per market.
Strategy changes refilter the cached data rather than downloading Yahoo again.

Cache files per market:
```
us_long_setups.csv      sgx_long_setups.csv
india_long_setups.csv   hk_long_setups.csv
*_scan_meta.json
```

### Freshness rule and no-new-bar optimisation
- **During market hours**: shorter refresh interval.
- **Outside market hours**: longer cache is used.
- When cache TTL expires the app first does a **lightweight latest-bar check**.
- If Yahoo has a newer bar → full master scan is refreshed.
- If Yahoo's latest bar equals the cached bar → existing cache is kept; this is logged in Diagnostics.

```
No newer Yahoo bar available — existing scanner cache was kept.
Last checked: 2026-05-08 16:05:00 SGT
Cached latest bar: 2026-05-08 16:00:00 SGT
Available latest bar: 2026-05-08 16:00:00 SGT
```
        """)

    # ── Universe ──────────────────────────────────────────────────────────────
    with st.expander("🌍 Universe — how ticker lists are built"):
        st.markdown("""
### Single source of truth: universe_data.py
All ticker lists are defined once in `tabs/universe_data.py` and imported everywhere.
`config_core.py` imports from it; `top_movers_tab.py` calls `get_tickers_for_market()`.
Adding a ticker in `universe_data.py` makes it available in every tab immediately.

### How the scan universe is built
```
Always include tickers  ← highest priority, always present
+ get_tickers_for_market(selected_market)
    = existing curated watchlist
    + actual index components (S&P 500 / NASDAQ-100 / Nifty / Hang Seng)
    deduplicated, market-isolated
= _active_tickers passed to all tabs
```

### Per-market universe
| Market | Tickers | Composition |
|---|---|---|
| 🇺🇸 US | 746 | Curated high-beta/sector watchlist + S&P 500 (~489) + NASDAQ-100 (~108) |
| 🇸🇬 SGX | 111 | STI-30 + REITs + growth names + SGX Mainboard liquid fallback |
| 🇮🇳 India | 172 | Curated high-beta + Nifty 50 + Nifty Next-50 + Nifty Midcap-50 |
| 🇭🇰 HK | 137 | Curated volatile/liquid + Hang Seng + HSI Tech constituents |

### Breakout Scanner universe presets (independent from main scan)
| Market | Preset | Size |
|---|---|---|
| US | S&P 500 | ~489 |
| US | NASDAQ-100 | ~108 |
| US | S&P 500 + NASDAQ-100 | ~517 |
| US | High-Beta / Growth | ~337 |
| US | S&P 500 + Growth | ~742 |
| US | All US | ~746 |
| SGX | SGX Mainboard | ~111 |
| India | Nifty 50 | 50 |
| India | Nifty 150 | 172 |
| HK | Hang Seng + HSI Tech | ~137 |

### Always include tickers
The sidebar **Always include tickers** field is the single place to add custom stocks.
They are guaranteed to be present in every scan regardless of market/strategy.
```
UUUU, APP, NVDA
S58.SI, D05.SI
RELIANCE.NS
0700.HK, 9988.HK
```

### Speed: why scanning is faster
- `ThreadPoolExecutor` with 5 workers pre-fetches all meta before the loop.
- Shared `requests.Session` across workers preserves Yahoo auth token.
- Result: ~2 minutes per scan (was ~15 minutes for 410 tickers).
        """)

    # ── Diagnostics ───────────────────────────────────────────────────────────
    with st.expander("🔍 Diagnostics — debugging no-data issues"):
        st.markdown("""
Open **🔍 Diagnostics** when the scan completes but shows no stocks.

### Cache freshness diagnostics
| Field | Meaning |
|---|---|
| **Last checked** | When the lightweight Yahoo latest-bar check ran |
| **Cached latest bar** | Latest bar currently stored in the scanner cache |
| **Available latest bar** | Latest bar Yahoo currently has from the sample check |
| **Decision** | Full refresh performed, or no newer bar so existing cache was kept |

### Scan debug summary
- **Batch loaded** — how many had OHLCV data
- **Skipped history** — no price data
- **Skipped liquidity** — too thin / low ATR
- **Skipped earnings** — earnings within 7 days (if guard is ON)
- **Ticker errors** — exceptions per ticker
- **Raw long/short rows** — rows before strategy filter

If **Raw long rows = 0** but **Batch loaded = 410**, signals computed but all produced `l_action = None` — usually a bear-market session.

### Always-include tickers status
- ✅ Green — all always-include tickers were in the last scan
- ⚠️ Warning — tickers added after last scan → click **🚀 Scan** again
- 🔍 Search box — check any specific ticker

### Common cloud fixes
```
HTTP 401 Invalid Crumb  → yfinance rate-limited; wait 60s and scan again
Latest bar: unknown     → df_long_master is empty; check Raw long rows
Operator: 274, Long: 0  → action assignment failing; update app
```
        """)

    # ── All columns reference ─────────────────────────────────────────────────
    with st.expander("🔎 All columns explained"):
        st.markdown("""
### Main scanner columns
| Column | Meaning |
|---|---|
| **Rank** | Display-only rank inside the shown grid |
| **Action** | Strategy label (STRONG BUY / BUY – MA60 SUPPORT / etc.) |
| **View** | Plain-English decision: Best swing buy / Buy on confirmation / Watchlist / Wait / Avoid |
| **Buy Condition** | Practical entry rule with stop and target where available |
| **Setup Type** | Pullback / Breakout / Support zone / PM% / Volume tier |
| **Entry Quality** | ✅ BUY · 👀 WATCH · ⏳ WAIT · 🚫 AVOID |
| **Rise Prob / Fall Prob** | Bayesian probability (bucket-capped) |
| **Score** | Count of active setup signals |
| **Operator / Op Score** | Smart-money accumulation label and raw score |
| **VWAP** | ABOVE = buyers winning · BELOW = sellers winning |
| **Trap Risk** | FALSE BO · GAP CHASE · DISTRIB · — (none) |
| **Today %** | Current day change |
| **RSI Now** | RSI-14 at time of scan (Support Entry mode) |
| **PM Chg%** | Pre-market price change (Premarket Momentum mode) |
| **Support Tier** | 🔵🟢🟡🟣⚪ tier for Support Entry mode |
| **MA60 Stop** | Hard stop — exit if price closes below |
| **TP1 / TP2 / TP3** | +10% / +15% / +20% targets |
| **Smart TP** | Options-implied target when available |
| **Implied Move 2W** | Options market expected ±% over 2 weeks |
| **Float / Short %** | Float size and short interest (US only) |
| **PI Proxy** | PSM return-potential proxy |
| **PSS Score** | PSM professional swing signal score |
| **Why Selected** | PSM/High Conviction key reasons for selection |
| **Signals** | Raw signal tags — HC[T+M+V+S+X](5/5) for High Conviction |
| **Opt Flow** | Options signals: CALL FLOW / CALL SKEW / P/C↓ etc. |
| **Last Bar** | Timestamp of the latest OHLCV bar used |

### Breakout Scanner columns
| Column | Meaning |
|---|---|
| **Score** | Composite 0–100 combining all three signals |
| **Signals** | Active badges: Vol Breakout · 52W Setup · New 52W High · Mover |
| **Vol Ratio** | Today's volume ÷ 20-day average volume |
| **Today Vol** | Absolute volume today |
| **vs 52W %** | Distance below 52-week high (0% = at the high) |
| **In Range %** | Position in 52W low→high range (100% = at the high) |
| **Breakout %** | % above the N-day high |
| **ATR %** | Daily volatility as % of price |
| **3M Return %** | 63-session return |
        """)

    # ── Risk ──────────────────────────────────────────────────────────────────
    with st.expander("✅ Practical rules + ⚠️ risk warnings"):
        st.markdown("""
### Trade checklist before entry
```
✅ Setup type is clear and matches the chart
✅ Entry Quality is BUY or WATCH (not WAIT/AVOID)
✅ MA60 Stop is logical and not too far
✅ Reward:risk is at least 2:1
✅ No major Trap Risk flag
✅ Earnings are not within 7 days
✅ Sector and market regime support the direction
✅ Volume confirms — not buying into a silent drift
```

### Reduce size or skip when
```
❌ Gap chase (already up >8% today)
❌ False breakout warning
❌ Distribution warning on a long
❌ Earnings within 2 days
❌ Low liquidity / wide spread (especially SGX)
❌ Market regime is BEAR
❌ VIX spike without clear catalyst
```

### Risk management
- Risk a fixed small amount per trade (e.g. 1% of portfolio).
- Stop = where the setup is **invalid**, not a random percentage.
- Take partial at TP1 (+10%) — let the rest run with a trailing stop.
- For SGX names use **limit orders** — spreads can be wide.
- Do not average down on losing trades without a clear reason.
        """)
        st.warning(
            "This tool does not provide financial advice. All outputs are signals and estimates only. "
            "Probability is not certainty. Earnings, news, and macro events can override any signal."
        )

    # ── Install ───────────────────────────────────────────────────────────────
    with st.expander("🔧 Install and run"):
        st.markdown("""
```bash
pip install -r requirements.txt
streamlit run main.py
```

If Yahoo data fails:
```bash
pip install --upgrade yfinance requests
streamlit cache clear
```

Key packages: `streamlit` · `yfinance` · `pandas` · `numpy` · `ta` ·
`financedatabase` · `nsepython` · `requests` · `streamlit-autorefresh`
        """)

    st.markdown("---")
    st.caption(
        "Swing Scanner v13.90 · 19 tabs · 8 strategies · US + SGX + India + HK · "
        "⚡ Breakout Scanner · Bayesian engine · Operator layer · Options signals · "
        "Not financial advice"
    )
