"""Help tab renderer — updated for all new strategies and features."""


def render_help(ctx: dict) -> None:
    st = ctx["st"]

    st.markdown("## ❓ Swing Scanner — Complete Guide")
    st.caption(
        "Covers all 7 strategies · Pre-market & Support Entry · High Conviction · "
        "Speed fixes · Always-include tickers · Diagnostics · Stock Analysis sync"
    )

    # ── What's new ────────────────────────────────────────────────────────────
    with st.expander("🆕 What changed recently", expanded=True):
        st.markdown("""
### Latest build
- **🇭🇰 Hong Kong market added** as a full market radio option.
- **HK expanded universe**: 137 curated liquid/high-beta `.HK` stocks, including your original 30 core names.
- **🚀 Movers/Losers tab added** — Top Gainers, Top Losers, and Volume Leaders for US/SGX/India/HK.
- **Master Yahoo cache architecture** — Yahoo data is downloaded once, then strategy changes only re-filter cached data.
- **Latest bar time formatting** — latest bar display can be converted to Singapore time for clearer diagnostics.
- **7 Swing Strategies** in the sidebar dropdown (was 3).
- **Speed**: parallel pre-fetch cuts scan time from ~15 min → ~2 min for 410 tickers.
- **Always include tickers** is the single place to add custom tickers (duplicate "Custom tickers" field removed).
- **Stock Analysis** operator label now matches the scanner exactly.
- **Diagnostics** shows always-include status, ticker search box, and per-ticker fetch log.
- **High Conviction** strategy added — requires all 5 signal categories simultaneously.
- **Support Entry** strategy — only shows stocks AT a support level, not already extended.
- **Premarket Momentum** strategy — stocks with +1–8% pre-market gain + intact trend.
- Master scan empty-result fix: Discovery mode now catches all stocks regardless of market direction.

### Previous major milestones
- **v13.52** — Balanced/Strict/Discovery/High Volume strategies, live-market swing criteria.
- **v12** — Options signals (US + India F&O), operator activity layer.
- **v11** — SGX/India markets, intraday overlay, sector heatmap.
        """)

    # ── Quick start ───────────────────────────────────────────────────────────
    with st.expander("🚀 Quick start — daily workflow"):
        st.markdown("""
1. Pick market: **US**, **SGX**, **India**, or **HK**.
2. Choose a **Swing strategy** (see table below).
3. Add must-scan names in **Always include tickers** — e.g. `UUUU, APP, NVDA, S58.SI, 0700.HK`.
4. Click **🚀 Scan**.
5. Review tabs:

```
Movers/Losers → Sector Heatmap → Long Setups → Swing Picks → Trade Desk → Stock Analysis
```

**Best strategy by time of day:**

| Time (local market) | Strategy to use |
|---|---|
| 30 min before open | **Premarket Momentum** — catch gap-up names |
| First 30 min after open | **Support Entry** — buy dips that have pulled to MA |
| Mid-day / end of day | **Balanced** or **High Conviction** |
| Quiet/choppy markets | **Discovery** for watchlist building |
| Want fewer but stronger | **High Conviction** |
        """)

    # ── 7 strategies ─────────────────────────────────────────────────────────
    with st.expander("🎯 All 7 strategies — when to use each"):
        st.markdown("""
| Strategy | Best for | How it works | Expected results |
|---|---|---|---|
| **Strict** | Strong markets, want A+ only | Very high probability + score gate | 3–10 stocks |
| **Balanced** | Normal daily trading (default) | Practical trend + volume + operator | 15–40 stocks |
| **Discovery** | Quiet markets, building watchlist | Wide net, lower thresholds | 40–80+ stocks |
| **Support Entry ⭐** | Morning scan, before move happens | Only stocks AT MA20/MA60/VWAP/swing low, not already up | 5–20 stocks |
| **Premarket Momentum 🚀** | 30 min before open | +1–8% PM gain + intact technical trend | 5–15 stocks |
| **High Volume 📊** | Finding active names right now | Unusual volume / breakout / pocket pivot | 10–30 stocks |
| **High Conviction 🎯** | Highest win-rate shortlist | ALL 5 signal categories must confirm simultaneously | 5–15 stocks |

### Support Entry — tiers explained
| Tier | Signal | Meaning |
|---|---|---|
| 🔵 Tier 1 — MA60 dip | Price ±1.5% of MA60 + vol declining | Strongest — institutional buyers step in here |
| 🟢 Tier 2 — MA20 dip | Price ±1.5% of MA20 | Common swing entry, trend intact above MA60 |
| 🟡 Tier 3 — Swing low | Within 2% of last swing low | Structural support from price action |
| 🟣 Tier 4 — MA200 | Near 200-day MA | Long-term support, recovery play |
| ⚪ Tier 5 — VWAP | Holding above VWAP | Intraday level, weakest |

**Gate:** `today_chg_pct ≤ 5%` — stocks already up more than 5% today are hidden. That's the whole point: you want the entry BEFORE the move.

### Premarket Momentum — tiers explained
| Tier | PM Change | Action |
|---|---|---|
| 🚀 Tier A | +3% to +8% | High conviction — enter near the open |
| 📈 Tier B | +1% to +3% | Wait for first 5-min candle to confirm direction |
| 🟡 Tier C/D | Live momentum | Technical momentum when PM data unavailable |

**Gate:** above MA60 + core trend intact + RSI < 72 + no trap risk. A large PM move on a broken stock is filtered out.

### High Conviction — 5 categories
All five must fire at least one signal:

| Category | Signals checked |
|---|---|
| 📈 Trend | EMA8>EMA21, weekly trend, golden cross, full MA stack |
| ⚡ Momentum | MACD accel, stoch bounce, RSI>50, momentum 3d |
| 🔊 Volume | Vol breakout, vol surge, pocket pivot, operator accumulation |
| 🏗️ Structure | Higher lows, VCP tightness, strong close, bull candle |
| 🌍 Market | RS > SPY, RS momentum, sector leader, near 52W high |

Look for `HC[T+M+V+S+X](5/5)` in the Signals column to see which fired.
        """)

    # ── Tab guide ─────────────────────────────────────────────────────────────
    with st.expander("🧭 Tab guide"):
        st.markdown("""
| Tab | Purpose |
|---|---|
| 🚀 **Movers/Losers** | Top Gainers, Top Losers, and Volume Leaders across US/SGX/India/HK |
| 🗂️ **Sector Heatmap** | Market direction first — color tiles, green/red summary |
| 📋 **Trade Desk** | Execution: entry zone, stop, target, R/R, position size |
| 📈 **Long Setups** | Bullish swing candidates — strategy-aware sections |
| 🎯 **Swing Picks** | Final shortlist — Bayesian + operator + sector + news ranking |
| 📉 **Short Setups** | Bearish candidates — best for liquid US names |
| 🪤 **Operator Activity** | Smart-money footprints across scanned universe |
| 🔄 **Side by Side** | Compare best longs vs best shorts, spot conflict |
| 📊 **ETF Holdings** | Add ETF constituents to universe |
| 🔬 **Stock Analysis** | One-stock deep dive — operator label matches scanner |
| 📅 **Earnings** | Earnings risk calendar — avoid nearby events |
| 📰 **Event Predictor** | Contract/order/upgrade/dilution keyword scan |
| 🌱 **Long Term** | 1–5 year quality scoring + near-support filter |
| 🔍 **Diagnostics** | Cloud debug — errors, ticker list, always-include check |
| 🧪 **Accuracy Lab** | Signal backtest / validation |
| 🧠 **Strategy Lab** | ML research layer |
| ❓ **Help** | This guide |
        """)

    # ── Long/Short setups ─────────────────────────────────────────────────────
    with st.expander("📈 Long / 📉 Short Setups — columns explained"):
        st.markdown("""
### Long setup action labels (Balanced mode)
| Label | Meaning |
|---|---|
| 🔥 STRONG BUY | Highest accuracy: prob + score + trend + volume + no trap |
| WATCH – HIGH QUALITY | Actionable setup, one confirmation short of STRONG BUY |
| WATCH – DEVELOPING | Setup forming, not yet fully confirmed |
| WATCH – TRAP RISK | Looks good but has false breakout / gap chase warning |

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
| **Trap Risk** | FALSE BO / GAP CHASE / DISTRIB — avoid or reduce size |
| **VWAP** | ABOVE = buyers in control |
| **MA60 Stop** | Place stop just below this — setup is invalid if broken |
| **TP1/2/3** | +10% / +15% / +20% targets — take partial at TP1 |
| **RSI Now** | Only visible in Support Entry mode — want 28–65 |
| **PM Chg%** | Only visible in Premarket mode — pre-market move % |
| **Support Tier** | Only visible in Support Entry mode — tier 1 is strongest |
        """)

    # ── Operator / Trap ───────────────────────────────────────────────────────
    with st.expander("🪤 Operator Activity vs Trap Patterns — they are different"):
        st.markdown("""
These are two separate scoring systems. Both are shown in **Stock Analysis**.

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
| 🔥 STRONG OPERATOR | ≥ 6 | Strong accumulation — multiple confirmation signals |
| 🟢 ACCUMULATION | ≥ 4 | Good signs of buying pressure |
| 🟡 WEAK SIGNS | ≥ 2 | Some activity, not conclusive |
| ⚪ NONE | 0–1 | No operator footprint |

### Trap Patterns (manipulation / risk flags)
Looks for failed breakouts and distribution:
- False breakout — new high on volume but closes weak
- Gap chase risk — today up >7% on 2.5× volume
- Distribution — high volume + tiny move + weak close

**A stock can have 🔥 STRONG OPERATOR and zero trap patterns simultaneously — that is the ideal setup.**
The Stock Analysis tab now shows both clearly and labels them differently.
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

### Support score (0–5) — added criteria
Each worth +1:
1. Price within −20%…+8% of MA50
2. Price within −8%…+18% of MA200
3. RSI-14 between 25 and 58 (accumulation zone)
4. Price 8–45% below 52-week high (healthy correction)
5. Price 8–65% above 52-week low (support floor intact)

Tick **📍 Near support only** to filter to stocks at technically attractive long-term entry points.

### Filter bar (above the grid)
| Filter | Use |
|---|---|
| 🔍 Ticker / name | Search any stock |
| Horizon | Core Hold / Buy & Hold / Accumulate |
| Sector | Filter by sector |
| 📍 Near support | Only stocks at support |
| Min support score | 0–5 slider |
| Min analyst upside | Skip low-conviction analyst targets |
        """)

    # ── Movers and cache ──────────────────────────────────────────────────────
    with st.expander("🚀 Movers/Losers tab + master cache"):
        st.markdown("""
### Movers/Losers tab
Use this tab to quickly see what is active before selecting a strategy.

| Section | Meaning |
|---|---|
| **Top Gainers** | Biggest positive movers for selected market/timeframe |
| **Top Losers** | Biggest negative movers for selected market/timeframe |
| **Volume Leaders** | Most active names by relative/absolute volume |

Supported markets:
```
Current selected market, US, SGX, India, HK
```

### Master Yahoo cache
The scanner now stores one broad Yahoo-enriched master scan per market.
Strategy changes should re-filter cached data instead of downloading Yahoo again.

Expected cache examples:
```
us_long_setups.csv
sgx_long_setups.csv
india_long_setups.csv
hk_long_setups.csv
```

Metadata file:
```
*_scan_meta.json
```

Look for:
```json
"cache_type": "master_scan_v1",
"strategy_mode": "MASTER"
```

### Freshness rule
- During market hours: shorter refresh interval for minimum delay.
- Outside market hours: longer cache is used.
- Changing Strategy should show a grid refresh message and should not force a Yahoo download unless cache expired or you manually refresh.
        """)

    # ── Diagnostics ───────────────────────────────────────────────────────────
    with st.expander("🔍 Diagnostics — debugging no-data issues"):
        st.markdown("""
Open **🔍 Diagnostics** when scan completes but shows no stocks.

### Scan debug summary
Shows exactly why stocks were dropped:
- **Batch loaded** — how many had OHLCV data
- **Skipped history** — no price data
- **Skipped liquidity** — too thin / low ATR
- **Skipped earnings** — earnings within 7 days (if guard is ON)
- **Ticker errors** — exceptions per ticker
- **Raw long/short rows** — rows before strategy filter

If **Raw long rows = 0** but **Batch loaded = 410**, it means:
- signals computed but all tickers produced `l_action = None`
- Check market direction — bearish sessions produce fewer signals

### Always-include tickers status
- ✅ Green — all always-include tickers were in the last scan
- ⚠️ Warning — tickers added after last scan → click **🚀 Scan** again
- 🔍 Search box — check any specific ticker

### Long-Term scan diagnostics
After a 🌱 Long Term scan, shows per-ticker fetch log:
- OK / FAIL for each SGX/US stock
- Which step failed (info empty, history blocked, no price)
- Score and support score per ticker

### Common cloud fixes
```
HTTP 401 Invalid Crumb  → yfinance rate-limited; wait 60s and scan again
Latest bar: unknown     → df_long_master is empty; check Raw long rows above
Operator: 274, Long: 0  → signals compute but action assignment failing; update app
```
        """)

    # ── Universe / tickers ────────────────────────────────────────────────────
    with st.expander("🌍 Universe — curated + live + always-include"):
        st.markdown("""
### How the scan universe is built

```
Always include tickers  ← highest priority, always present
+ Curated hard-coded watchlist (US/SGX/India/HK)
+ Live movers / Yahoo-derived universe where available
= active_tickers passed to the scan
```

### Hong Kong universe
HK is now a full market option, not only a Movers/Losers filter.

- Default universe: **137 curated `.HK` stocks**.
- Includes your original core HK tickers first.
- Covers Hang Seng blue chips, Hang Seng TECH, EV/auto, semiconductors, brokers, casino, property, and biotech names.
- HK cache files use the `hk_` prefix, for example:

```
hk_long_setups.csv
hk_short_setups.csv
hk_operator_activity.csv
hk_scan_meta.json
```

Core HK examples:
```
0700.HK,9988.HK,3690.HK,1810.HK,1024.HK,9618.HK,9888.HK,9999.HK,2015.HK,9868.HK,1211.HK,0981.HK,2382.HK,2018.HK,6618.HK
```

**Always include tickers** (sidebar) is the single place to add custom stocks. Type comma-separated or line-separated:
```
UUUU, APP, NVDA
S58.SI, D05.SI
RELIANCE.NS
0700.HK, 9988.HK
```

### Speed: why scanning is faster now
Previously: `.calendar`, `.info`, and `.fast_info` were called **serially inside the loop** — 0.8s + 1.0s + 0.4s × 410 tickers = **15 minutes**.

Now: a `ThreadPoolExecutor` with 5 workers and a shared session pre-fetches all meta **before** the loop in **~2 minutes**. The loop itself only does signal computation (fast pandas/ta-lib).

### HTTP 401 Invalid Crumb
Caused by too many parallel Yahoo requests invalidating the auth token. Fixed by:
- Shared `requests.Session` across all workers (same crumb)
- Workers capped at 5 (not 25)
- Retry with backoff on 401
        """)

    # ── Columns reference ──────────────────────────────────────────────────────
    with st.expander("🔎 All columns explained"):
        st.markdown("""
| Column | Meaning |
|---|---|
| **Action** | Strategy-specific label (STRONG BUY / BUY – MA60 SUPPORT / BUY – PM MOMENTUM etc.) |
| **Setup Type** | Pullback / Breakout / Support zone / PM% / Volume tier |
| **Entry Quality** | ✅ BUY · 👀 WATCH · ⏳ WAIT · 🚫 AVOID |
| **Rise Prob / Fall Prob** | Bucket-capped Bayesian probability |
| **Score** | Count of active setup signals |
| **Operator / Op Score** | Smart-money accumulation label and score |
| **VWAP** | ABOVE = buyers winning · BELOW = sellers winning |
| **Trap Risk** | FALSE BO · GAP CHASE · DISTRIB · — (none) |
| **Today %** | Current day change |
| **RSI Now** | RSI-14 at time of scan (Support Entry mode) |
| **PM Chg%** | Pre-market price change (Premarket Momentum mode) |
| **Support Tier** | 🔵🟢🟡🟣⚪ tier for Support Entry mode |
| **MA60 Stop** | Hard stop — exit if price closes below |
| **TP1 / TP2 / TP3** | +10% / +15% / +20% targets |
| **Smart TP** | Options-implied target when available |
| **Implied Move 2W** | Options market's expected ±% over 2 weeks |
| **Float / Short %** | Float size and short interest (US only) |
| **Signals** | Raw signal tags — HC[T+M+V+S+X](5/5) for High Conviction |
| **Opt Flow** | Options-derived signals: CALL FLOW / CALL SKEW / P/C↓ etc. |
| **Last Bar** | Timestamp of the latest OHLCV bar used |
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
- Risk fixed small amount per trade (e.g. 1% of portfolio).
- Stop = where the setup is **invalid**, not a random percentage.
- Take partial at TP1 (+10%) — let rest run with trailing stop.
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
        "Swing Scanner · 7 strategies · US + SGX + India + HK · "
        "Bayesian engine + operator layer + options signals · "
        "Not financial advice"
    )
