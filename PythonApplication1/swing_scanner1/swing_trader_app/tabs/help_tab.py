"""Help tab renderer for Swing Scanner v13.60."""


def render_help(ctx: dict) -> None:
    """Render the Help tab using objects supplied by the main runtime context."""
    st = ctx["st"]

    st.markdown("## ❓ How to Use the Swing/Long Term Scanner v13.60")
    st.caption(
        "Latest guide: v13.60 help refresh for the v13.52 live-market swing criteria, "
        "v13.51 cloud diagnostics, fast earnings calendar, expanded US/SGX ticker universe, "
        "Trade Desk execution tools, Swing Picks ranking, and readable modular tabs/core files."
    )

    with st.expander("🆕 What changed recently", expanded=True):
        st.markdown("""
### v13.60
- Help tab updated for the latest app behavior.
- Version labels updated to **v13.60**.
- Guide now explains the latest Long / Short / Swing Picks / Trade Desk / Stock Analysis criteria.

### v13.52 — better live-market swing criteria
- Added **Swing signal mode** in the sidebar:
  - **Strict** — A+ confirmed setups only.
  - **Balanced** — practical live swing candidates; this is the default.
  - **Discovery** — wider watchlist for quiet markets.
  - **High Volume** — unusual volume / volume breakout / pocket pivot setups.
- Long setup logic now recognises **Pullback**, **Breakout**, **Continuation**, **Operator Accumulation**, and **Early Trend** setups.
- Short setup logic now recognises **Breakdown**, **Distribution**, **Rollover**, and **Early Downtrend** setups.
- Swing Picks no longer requires news/event data to be present before a strong technical setup can rank well.
- Stock Analysis thresholds now match the practical live-market scanner instead of being too strict.

### v13.51 — Cloud diagnostics hardening
- Scan/runtime errors are captured into Diagnostics instead of silently producing empty grids.
- Errors are also logged to `scanner_cache/app_error_log.jsonl` where possible.
- Diagnostics now shows scan debug summaries: tickers attempted, batch-loaded count, per-ticker errors, skipped history/liquidity/earnings, and empty-result reasons.

### v13.49 / v13.50
- Earnings Calendar became faster by avoiding full Yahoo `info` calls for every ticker.
- SGX universe was expanded with names such as `E28.SI`.
        """)

    with st.expander("🚀 Quick Start — best daily workflow"):
        st.markdown("""
1. Pick market: **US**, **SGX**, or **India**.
2. Choose **Swing signal mode**:
   - Start with **Balanced** for normal live trading.
   - Use **Discovery** when markets are quiet and you want more watchlist ideas.
   - Use **Strict** when you only want the strongest confirmed setups.
3. Turn on **Use live market universe** when you want Yahoo/live movers added to existing tickers.
4. Add must-scan names in **Always include tickers**, for example `UUUU, APP, NVDA`.
5. Click **🚀 Scan**.
6. Review tabs in this order:

```text
Sector Heatmap → Long Setups / Short Setups → Swing Picks → Trade Desk → Stock Analysis → Earnings / News check
```

For actual entry, always confirm:

```text
Setup Type + VWAP + Operator Score + Trap Risk + Earnings Risk + Stop level
```
        """)

    with st.expander("🧭 Tab guide — what each tab is for"):
        st.markdown("""
| Tab | Use it for | Current behavior |
|---|---|---|
| 🗂️ **Sector Heatmap** | Market/sector direction first | US uses sector ETFs; SGX uses stock-group averages/fallback; India uses NSE indices |
| 📋 **Trade Desk** | Execution planning | Buy/Sell selector, filters, trade plan, stop/target, risk sizing, setup quality, market breadth |
| 📈 **Long Setups** | Bullish swing candidates | Practical setup detection: Pullback, Breakout, Continuation, Operator Accumulation, Early Trend |
| 🎯 **Swing Picks** | Final actionable shortlist | Final Swing Score = Bayes + operator + setup type + sector/news - earnings/trap risk |
| 📉 **Short Setups** | Bearish swing candidates | Breakdown, Distribution, Rollover, Early Downtrend; best suited to liquid US names |
| 🪤 **Operator Activity** | Smart-money footprints | Uses scanned universe, not hard-coded symbols only |
| 🔄 **Side by Side** | Compare longs vs shorts | Helps identify conflict and market breadth weakness |
| 📊 **ETF Holdings** | Add ETF/theme constituents | Useful for US ETF/sector/thematic universe expansion |
| 🔬 **Stock Analysis** | One-stock deep dive | Long/short scorecard, support/resistance, trend, volume, VWAP, trap risk |
| 📅 **Earnings** | Earnings risk review | Faster scan; max-scan control; extra tickers scanned first |
| 📰 **Event Predictor** | News/catalyst clues | Contract/order/upgrade/downgrade/legal/dilution keywords where available |
| 🌱 **Long Term** | 1–3 year ideas | Separate long-term scoring; not a swing signal |
| 🔍 **Diagnostics** | Debug Cloud/data issues | App errors, scan debug summary, cache status, ticker counts, scanned ticker list |
| 🧪 **Accuracy Lab** | Signal validation | Backtest/validation notes for swing target logic |
| 🧠 **Strategy Lab** | Optional ML research | ML is only a research/filter layer; Bayesian remains primary unless ML clearly beats it |
| ❓ **Help** | This guide | Updated for v13.60 |
        """)

    with st.expander("🎚️ Swing signal mode — Strict vs Balanced vs Discovery"):
        st.markdown("""
Use this to control how many stocks appear in Long/Short/Swing Picks.

| Mode | Best for | Behavior |
|---|---|---|
| **Strict** | Strong markets or when you want fewer trades | Requires cleaner confirmation and stronger setup quality |
| **Balanced** | Normal live swing trading | Shows practical actionable candidates without being too restrictive |
| **Discovery** | Quiet/choppy markets | Shows more early/developing setups for watchlist building |

Recommended default:

```text
Balanced
```

Use **Discovery** if you are seeing too few good names, but do not buy blindly. Treat it as a watchlist mode. Use **High Volume** when you want stocks where activity is increasing now.
        """)

    with st.expander("📈 Long Setups — updated live-market criteria"):
        st.markdown("""
Long Setups now tries to identify real swing patterns instead of only perfect textbook setups.

### Setup types
| Setup Type | What it means |
|---|---|
| **Breakout** | Price breaking above recent range/high with volume confirmation |
| **Pullback** | Uptrend stock pulling back near MA20/EMA21/VWAP support |
| **Continuation** | Trend already strong and momentum continues without excessive trap risk |
| **Operator Accumulation** | Smart-money style volume/close/VWAP/OBV accumulation footprint |
| **Early Trend** | Recovering or newly improving trend before all classic signals align |

### Important bullish confirmations
- Price above EMA8/EMA21 or reclaiming key moving averages.
- Volume breakout, volume surge, or pocket pivot.
- VWAP support.
- OBV rising or strong close.
- Relative strength vs SPY/sector.
- No serious **FALSE BO**, **GAP CHASE**, or **DISTRIB** trap label.

### Best BUY candidates
Prefer rows where:

```text
Entry Quality = ✅ BUY or 👀 WATCH
Setup Type is clear
Rise Prob is strong
Operator Score is positive
Trap Risk is blank/low
Earnings are not very close
```
        """)

    with st.expander("📉 Short Setups — updated live-market criteria"):
        st.markdown("""
Short setups are best for liquid US names. For SGX/India, check whether your broker/product supports shorting.

### Setup types
| Setup Type | What it means |
|---|---|
| **Breakdown** | Price breaks support/recent low with volume |
| **Distribution** | High volume but weak close / failed breakout / seller control |
| **Rollover** | Uptrend losing momentum and rolling below short averages/VWAP |
| **Early Downtrend** | Trend structure turning bearish before full confirmation |

### Important bearish confirmations
- Price below EMA8/EMA21 or below VWAP.
- High-volume down day.
- MACD deceleration or bearish cross.
- Lower highs or 10-day breakdown.
- Operator distribution.

### Best SELL/SHORT candidates
Prefer rows where:

```text
Entry Quality = ✅ SELL / SHORT or 👀 WATCH
Fall Prob is strong
Price below VWAP
Distribution or Breakdown setup type
Cover stop is clear
```
        """)

    with st.expander("🎯 Swing Picks — how final ranking works"):
        st.markdown("""
Swing Picks is the main shortlist for bullish swing trades.

Final ranking uses:

```text
Bayesian technical score
+ Operator / smart-money score
+ Setup Type bonus
+ Sector strength
+ News/catalyst score when available
- Earnings risk
- Trap risk
= Final Swing Score
```

### Important v13.52 change
News/event data is now **optional**, not mandatory. A stock with strong technicals, operator confirmation, and no trap risk can still rank well even when news data is missing.

### How to use Swing Picks
Use Swing Picks to decide **what deserves further review**, then use Stock Analysis and Trade Desk to decide **how to trade it**.

Best rows usually have:

```text
Final Swing Score high
+ BUY/WATCH verdict
+ clear Setup Type
+ operator accumulation
+ no nearby earnings
+ no trap risk
```
        """)

    with st.expander("📋 Trade Desk — execution layer"):
        st.markdown("""
Trade Desk is for execution, not discovery.

### BUY mode
Uses Long/Swing data and sorts the best BUY/WATCH plans to the top.

### SELL mode
Uses Short Setups and sorts best SELL/SHORT plans to the top.

### Filters at top
- Buy/Sell side.
- Minimum probability.
- Entry filter.
- Trap filter.
- Ticker search.

### Trade plan columns
- Entry zone.
- Stop.
- Target / cover target.
- Reward:risk.
- Suggested quantity.
- Max loss.
- Invalidation reason.

Use Trade Desk to answer:

```text
Where do I enter?
Where is the stop?
What is the target?
How much should I buy/sell?
When is the setup invalid?
```
        """)

    with st.expander("🔬 Stock Analysis — final check before entry"):
        st.markdown("""
Stock Analysis is the final single-ticker review.

Use it for:
- Long/short scorecard.
- Support/resistance.
- VWAP/trend confirmation.
- Volume breakout or pocket pivot.
- Trap risk review.
- Earnings/news risk check.

The Stock Analysis scorecard now aligns with the practical v13.52 live-market criteria. It should not be much stricter than the Long/Short tabs.

Before taking a trade, check:

```text
Does the setup type match the chart?
Is the stop logical?
Is reward:risk at least acceptable?
Is earnings risk manageable?
Is the market/sector supporting the trade?
```
        """)

    with st.expander("🪤 Operator / smart-money activity"):
        st.markdown("""
Operator activity is a confirmation layer, not a standalone buy signal.

The scanner looks for:
- high volume with green candle
- strong close near day high
- OBV rising
- price holding above VWAP
- breakout with volume
- absorption / accumulation footprints
- high-volume weak close or failed breakout for distribution

### Labels
| Label | Meaning |
|---|---|
| 🔥 **STRONG OPERATOR** | Strong accumulation footprint |
| 🟢 **ACCUMULATION** | Good smart-money signs |
| 🟡 **WEAK SIGNS** | Some signs but not enough |
| ⚪ **NONE** | No clear operator activity |
| 🔴 **DISTRIBUTION** | Seller/operator distribution warning |

Do not buy only because of operator score. Combine it with trend, entry quality, VWAP, and trap risk.
        """)

    with st.expander("🌍 Universe and tickers"):
        st.markdown("""
### Existing + live universe
When live universe is ON, the app combines:

```text
Yahoo/live movers + index/current sources + existing curated tickers + extra tickers + always-include tickers
```

When live universe is OFF:

```text
Existing curated tickers + extra tickers + always-include tickers
```

### Expanded ticker universe
Recent builds added more high-beta / swing-friendly names, including:
- SGX additions such as `E28.SI`.
- More US AI, semis, nuclear/uranium, quantum, crypto, photonics, biotech, and high-beta ETFs when added to config.

### Max live stocks
This is a cap, not a guaranteed count. If Yahoo only returns fewer unique names, the final count may be below your selected max.

### Diagnostics check
After scan, open Diagnostics to verify:
- total scanned count
- live/existing ticker count
- exact scanned ticker list
- ticker errors
- skipped history/liquidity counts
        """)

    with st.expander("📅 Earnings and 📰 News / Event filters"):
        st.markdown("""
### Earnings guard
Earnings can gap through stops. Treat nearby earnings as event risk.

General rule:

```text
Earnings within 7 days → reduce size, wait, or treat only as event trade
```

### Faster earnings calendar
The Earnings tab now avoids heavy full-market Yahoo `info` calls. It checks earnings dates first, loads heavier details only when needed, and lets you control max scan count.

### News/event scoring
News/event score looks for clues such as:
- earnings beat / guidance raise
- contracts / orders / partnerships
- analyst upgrades / downgrades
- legal/regulatory risk
- offering/dilution/investigation headlines

News helps ranking only when it supports the technical setup. Missing news should not automatically kill a strong technical setup.
        """)

    with st.expander("🔍 Diagnostics — when Cloud shows no stocks"):
        st.markdown("""
If deployed Cloud app shows no stocks, open:

```text
🔍 Diagnostics → App errors / Cloud diagnostics
```

Diagnostics should show:
- app/runtime errors
- scan errors
- Yahoo download failures
- ticker error samples
- tickers attempted
- batch loaded count
- skipped history/liquidity/earnings
- long/short/operator rows produced
- empty-result reason
- cache folder and last cache time

Errors are also written to:

```text
scanner_cache/app_error_log.jsonl
```

Use this instead of guessing why grids are empty.
        """)

    with st.expander("🧠 Scoring engine — Bayesian bucket-cap"):
        st.markdown("""
The core technical score is still Bayesian with fixed weights.

It uses signals such as:
- volume breakout
- volume surge
- pocket pivot
- trend daily
- weekly trend
- OBV rising
- strong close
- VWAP support
- relative strength
- options signals where available

### Bucket-cap
Overlapping signals are grouped so they do not double-count too much.

Example overlapping trend signals:

```text
trend_daily + weekly_trend + full_ma_stack + near_52w_high
```

Bucket-cap lets the strongest signal in a bucket count most, and later signals in the same bucket count less.
        """)

    with st.expander("🧪 Accuracy Lab and 🧠 Strategy Lab"):
        st.markdown("""
### Accuracy Lab
Preferred swing target:

```text
Winner = price hits +6% before -4% stop within 10 trading days
Loser  = -4% stop hits first, or +6% is never reached
```

### Strategy Lab
ML is optional and should not replace the Bayesian ensemble unless it clearly beats it.

Use ML only if:

```text
AUC Edge >= +0.02
and Top 10% ML win rate > Top 10% Bayesian win rate
```

If ML does not clearly beat Bayesian, keep Bayesian primary.
        """)

    with st.expander("🔎 Important columns explained"):
        st.markdown("""
| Column | Meaning |
|---|---|
| **Setup Type** | Breakout, Pullback, Continuation, Operator Accumulation, Early Trend, Breakdown, Distribution, etc. |
| **Rise Prob / Fall Prob** | Bucket-capped Bayesian probability |
| **Entry Quality** | BUY / WATCH / WAIT / AVOID or SELL/SHORT equivalents |
| **Score** | Count/strength of active setup signals |
| **Final Swing Score** | Main Swing Picks ranking score |
| **Operator / Op Score** | Smart-money/accumulation or distribution footprint |
| **VWAP** | Buyer/seller control confirmation |
| **Trap Risk** | FALSE BO, GAP CHASE, DISTRIB, or none |
| **News Score** | Catalyst/news contribution when available |
| **Sector Score** | Sector tailwind contribution |
| **Earnings Risk** | Penalty for nearby earnings/event risk |
| **MA60 Stop / Cover Stop** | Suggested invalidation/stop area |
| **TP1 / TP2 / TP3** | Example targets; not guaranteed |
        """)

    with st.expander("✅ Practical trading rules"):
        st.markdown("""
Prefer long trades with:

```text
Clear Setup Type
+ BUY/WATCH Entry Quality
+ strong Rise Prob
+ operator accumulation or VWAP support
+ no major Trap Risk
+ earnings not too close
+ acceptable reward:risk
```

Prefer short trades with:

```text
Breakdown/Distribution/Rollover setup
+ strong Fall Prob
+ below VWAP
+ clear cover stop
+ weak sector/market breadth
```

Avoid or reduce size when:

```text
Gap chase
False breakout
Distribution warning on a long
Earnings very close
Very wide spread / low liquidity
Market regime is BEAR or VIX is high
```

Risk framework:
- Risk small per trade.
- Place stops where the setup is invalidated, not randomly.
- Do not average down blindly.
- Take partial profit if move is fast into TP1.
- For SGX names, prefer limit orders because spreads can be wide.
        """)

    with st.expander("🔧 Install & run"):
        st.markdown("""
```bash
pip install -r requirements.txt
streamlit run main.py
```

If data fetch fails:

```bash
pip install --upgrade yfinance nsepython requests streamlit-autorefresh
streamlit cache clear
```

Main packages:
- `streamlit`
- `yfinance`
- `pandas`, `numpy`
- `ta`
- `financedatabase`
- `nsepython`
- `requests`
- `plotly` where used
- `streamlit-autorefresh` for non-destructive refresh
        """)

    with st.expander("⚠️ Risk warnings"):
        st.warning("""
This tool does not provide financial advice. All outputs are estimates and signals only.

1. Probability is not certainty.
2. Earnings and news can create overnight gaps.
3. SGX liquidity is lower; use limit orders.
4. Short selling risk can exceed initial capital if unmanaged.
5. Sector concentration can make many trades fail together.
6. Model assumptions can be wrong; always check chart, stop, and position size.
        """)

    st.markdown("---")
    st.caption("Swing/Long Term Scanner v13.60 · Practical live-market swing criteria · Cloud diagnostics · US + SGX + India · Not financial advice · Created by Ripin")
