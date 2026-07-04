"""Current Help tab renderer for the Swing Scanner.

This help page is intentionally kept in sync with the current tab layout.
It explains what each top-level and nested tab is for, which tab to use for
same-day vs next-day vs multi-day swing trades, and how to interpret the
new Catalyst Shock workflow.
"""


def render_help(ctx: dict) -> None:
    st = ctx["st"]

    st.markdown("## Swing Scanner - Current Guide")
    st.caption(
        "Updated guide for all 13 top tabs: Market Map, Market Activity, Momentum Runner, "
        "Pre-Movers, Best 7-10%, Long/Short Setups, Trade Tools, Stock Analysis, Events, "
        "Long Term/ETF, Advanced, and Help."
    )

    st.markdown(
        """
### Daily Workflow

Use the scanner in this order so you do not chase a stock after the easy move is already gone:

```text
1 Market Map
-> 2 Market Activity: Pre-Market -> Catalyst Shock -> Movers -> Big Money -> Breakouts
-> 3 Momentum Runner
-> 4 Pre-Movers
-> 5 Best 7-10%
-> 6 Long Setups / 7 Short Setups
-> 8 Trade Tools
-> 9 Stock Analysis
-> 10 Events
-> 12 Advanced checks if needed
```

Main rule: **watchlist first, trigger second, trade plan third**. A green stock is not automatically a buy. For fast runners, use VWAP/opening-range confirmation. For multi-day swings, use trigger, invalidation, reward:risk, and event risk.
        """
    )

    with st.expander("Tab Map - All Current Tabs", expanded=True):
        st.markdown(
            """
| Top tab | Nested tabs / content | Main use |
|---|---|---|
| **1 Market Map** | Sector heatmap and broad market context | Check whether the selected market and sectors support longs, shorts, or cash |
| **2 Market Activity** | **Pre-Market**, **Catalyst Shock**, **Movers**, **Big Money**, **Breakouts** | Find what is active now, what may explode on volume, and where institutional-style activity appears |
| **3 Momentum Runner** | Day-1 Ignition, Controlled Runner, Hot Runner / Wait Reset | Same-day explosive 5-10% candidates; use only with trigger + VWAP/ORB confirmation |
| **4 Pre-Movers** | Next-Day 5-10%, Pre-Mover Score, 7-Star Score, Explosion Score | Find candidates before they become obvious movers |
| **5 Best 7-10%** | Combined shortlist from multiple scan layers | Strictest list for the 7-10% swing objective |
| **6 Long Setups** | Full bullish scan grid | Review all BUY/WATCH/WAIT long candidates and supporting columns |
| **7 Short Setups** | Full bearish scan grid | Find weak names, short candidates, or hedges |
| **8 Trade Tools** | Trade Desk, Operator Activity, Range Trader | Convert a candidate into entry, stop, target, position size, and range plan |
| **9 Stock Analysis** | One-stock deep dive | Confirm one ticker with indicators, operator signals, traps, chart, and trade plan |
| **10 Events** | Earnings, Event Predictor | Check earnings risk, event risk, catalyst/fuel, and squeeze conditions |
| **11 Long Term / ETF** | Long Term, ETF Holdings | Longer-term stock/ETF support, quality, and portfolio research |
| **12 Advanced** | 7-10% Swing, Swing Picks, Pullback Reclaim, Pro Setups, Side by Side, Strategy Finder, Strategy Lab, Accuracy Lab, Performance Tracker, Test Cases, Diagnostics | Specialist scoring, research, validation, QA, and debugging |
| **13 Help** | This guide | How to use each tab and what to check before buying/selling |
            """
        )

    with st.expander("Which Tab Should I Use?", expanded=True):
        st.markdown(
            """
| Your question | Best tab | What to look for |
|---|---|---|
| **What is the market mood?** | 1 Market Map | Green/red sectors, sector leadership, risk-on/risk-off backdrop |
| **Which stock may jump like QS on sudden volume?** | 2 Market Activity -> **Catalyst Shock** | Loaded Spring, Shock Score, Catalyst Strength, Shock RVOL, Trigger Plan |
| **What is moving before market open?** | 2 Market Activity -> Pre-Market | PM Chg%, PM Price, PM volume/gap confirmation |
| **What is already up/down today?** | 2 Market Activity -> Movers | Top Gainers, Top Losers, Volume Leaders |
| **Where is operator / smart-money style accumulation?** | 2 Market Activity -> Big Money or 8 Trade Tools -> Operator Activity | Operator, Op Score, VWAP control, accumulation clues |
| **What can give 5-10% today?** | 3 Momentum Runner | Buy Decision, Runner Trigger, Firefly Pass, Entry Quality, VWAP/ORB |
| **What can give 5-10% tomorrow?** | 4 Pre-Movers | Next-Day 5-10%, Pre-Mover Score, 7-Star Score, not already extended |
| **What is the strict best swing shortlist?** | 5 Best 7-10% | A+ / A candidates, trigger, invalidation, PM confirmation, trap risk |
| **Should I buy this ticker?** | 9 Stock Analysis | Long score, short score, trap check, indicators, trade plan |
| **How many shares should I buy?** | 8 Trade Tools -> Position Sizing | Account risk, entry, stop, quantity |
| **Did the scanner actually work?** | 12 Advanced -> Performance Tracker | 1D/3D/5D/7D outcomes, hit rate, drawdown, stop-first rate |
            """
        )

    with st.expander("2 Market Activity - Pre-Market, Catalyst Shock, Movers, Big Money, Breakouts", expanded=True):
        st.markdown(
            """
### Pre-Market

Use before the US market opens. It attempts multiple data paths such as Yahoo quote fields, fast_info, and 5-minute intraday bars with prepost data. Treat it as **confirmation**, not a final buy signal.

Good pre-market signs:
- PM gap is positive but not already too stretched.
- PM price is above key trigger/VWAP area.
- Volume is active enough to matter.
- The stock already appears in Long Setups, Pre-Movers, Best 7-10%, or Catalyst Shock.

### Catalyst Shock

Use this for **QS-style moves** where a catalyst or fuel plus unusual volume can create a sudden 5-15% move. It reuses the latest Long Setups scan/cache, so it is fast and does not run another full Yahoo scan.

Important left-side columns are placed first to reduce horizontal scrolling:

```text
Ticker -> Buy/Sell -> Action -> Move Price -> Current Price -> Operator -> Op Score
-> VWAP -> Today % -> PM Chg% -> Gap Used % -> Shock RVOL
```

Status meaning:

| Shock Status | Meaning | Action |
|---|---|---|
| **BUY TRIGGER - ORB/VWAP ONLY** | Volume/catalyst shock is live | Do not market-buy blindly; buy only after 5/15-minute opening range or VWAP reclaim confirms |
| **WATCH - LOADED SPRING** | Coiled setup before the volume explosion | Set alert near Move Price / Trigger Plan; wait for live RVOL >= 1.5x and breakout confirmation |
| **WATCH - CONFIRM VOLUME** | Some setup exists but volume/catalyst is not strong enough yet | Watch only until news/volume confirms |
| **MOVED - WAIT PULLBACK** | Stock already made the big move | Wait for VWAP/EMA pullback or next-day high-tight flag |
| **AVOID - TRAP/CHASE RISK** | Overextended, weak, or trap flagged | Skip fresh entry |

Manual catalyst boost: if you already know a headline, type one ticker per line, for example `QS: Honda deal`. This boosts Catalyst Strength, but it still requires live price/volume confirmation.

### Movers

Use for the market-aware **Top Gainers**, **Top Losers**, and **Volume Leaders**. Movers tells you what already moved. It is useful for idea discovery, but a top gainer still needs VWAP/entry confirmation before buying.

### Big Money

Ranks institutional-style sponsorship plus short-term move potential. It scores operator accumulation, VWAP control, volume expansion, pocket-pivot/accumulation clues, relative strength, pre-mover evidence, quality, ATR, and extension risk.

Use **A - Big Money + Short-Term** and **B - Institutional Watch** as the first institutional watchlist, then confirm entry in Long Setups, Stock Analysis, or Trade Desk.

### Breakouts

Scans for breakout candidates and next-day scoring. Use it to find stocks near price triggers, volume expansion, and continuation patterns. A breakout should still pass reward:risk and should not be bought far above the trigger.
            """
        )

    with st.expander("Core Swing Tabs - Market Map, Momentum Runner, Pre-Movers, Best 7-10%, Long/Short", expanded=True):
        st.markdown(
            """
### 1 Market Map

Start here. Prefer long trades when market/sector breadth is supportive. If the broad market is weak, reduce position size, demand stronger confirmation, or focus on Short Setups.

### 3 Momentum Runner

Use for **same-day explosive 5-10% candidates** and stocks already running now. It is intentionally separate from Best 7-10% so hot runners do not pollute the stricter multi-day swing list.

Main decision stack:

```text
Ticker -> Buy Decision -> Buy Checklist -> Runner Trigger -> Runner Tier
-> Firefly Pass -> Explosive Buy -> Entry Quality -> Tradeable Buy
-> Sector Tailwind -> Runner Invalid -> Target 1 +5% -> Target 2 +10%
```

Best same-day buy stack:

```text
Buy Decision = BUY ABOVE TRIGGER - best candidate / confirm entry
Runner Tier = A++ Firefly 5-Layer Explosive or A+ Explosive 5-10% Today
Firefly Pass = YES
Entry Quality = A+ or A
RR Est >= 1:2
Trap Risk = blank/low
Live price breaks Runner Trigger and holds VWAP/opening range
```

If the ticker is marked **Hot Runner / Wait Reset**, do not chase. Wait for VWAP hold, inside day, pullback, or next-day high-tight flag.

### 4 Pre-Movers

Designed to find stocks before they become Movers. Use after the prior close or before the next session.

Key fields:
- **Next-Day 5-10% Watchlist**: previous-day close / before-open prep list.
- **Pre-Mover Score/Tier/Why**: coil, accumulation, ATR, trigger proximity, relative strength, and controlled current move.
- **7-Star Score/Tier/Why**: liquidity, move potential, compression, range shift, accumulation/divergence, one-red hold, reward:risk.
- **Explosion Score/Tier/Why**: higher-risk 10-20% watchlist using volatility, squeeze/float/catalyst fuel, and accumulation.

### 5 Best 7-10%

This is the strict shortlist for your main goal: realistic 7-10% swing potential with cleaner risk. It combines evidence from Long Setups, 7-10% Swing, Swing Picks, Pro Setups, Pre-Movers, and pre-market strength.

Use A+ rows first. Always check Trigger Above, Invalid Below, PM Chg%, PM Price, reward:risk, and trap/chase risk.

### 6 Long Setups

Full bullish scanner grid. Use it to inspect all BUY/WATCH/WAIT long candidates, quality score, probability, support/dip labels, pre-mover fields, 7-Star fields, Stage 2 fields, operator data, and tradeability gates.

### 7 Short Setups

Bearish scanner grid. Use when market is weak, a stock loses support, or you need hedge candidates. Confirm with short score, downside room, volume, trend, and invalidation level.
            """
        )

    with st.expander("8 Trade Tools, 9 Stock Analysis, 10 Events"):
        st.markdown(
            """
### 8 Trade Tools

Nested tabs:
- **Trade Desk**: entry zone, stop, targets, risk/reward, and position sizing.
- **Operator Activity**: accumulation/distribution footprints from scan data.
- **Range Trader**: support/resistance channel trades with buy/sell zones.

Use Trade Desk after you have selected a candidate from Catalyst Shock, Momentum Runner, Best 7-10%, Long Setups, or Short Setups.

### 9 Stock Analysis

Use this for one ticker at a time. It checks price history, moving averages, RSI, support/resistance, volume, operator labels, trap patterns, and scanner context. It also provides a long/short trade plan with stops and target levels.

### 10 Events

Nested tabs:
- **Earnings**: upcoming earnings risk and verdict based on price vs moving averages, analyst target, and EPS trend.
- **Event Predictor**: event/catalyst/squeeze watchlist using earnings risk, news sentiment, order/contract keywords, and trend confirmation.

Events are watchlist signals. Near earnings can create gap risk; do not treat event rows as automatic buys.
            """
        )

    with st.expander("11 Long Term / ETF"):
        st.markdown(
            """
### Long Term

Long-term quality plus near-support scoring for US and SGX stocks. Use it for 6-24 month or longer ideas, not 3-10 day swing entries.

Notes:
- If Yahoo fundamentals are sparse, conservative fallback rows may appear.
- Fallback rows should be refreshed later before acting.
- Near-support does not mean immediate buy; confirm trend and risk.

### ETF Holdings

Use this to inspect ETF constituents and SG investor ETF choices. It helps you discover tickers and compare ETF/fund exposure, fees, yields, and long-term return context.
            """
        )

    with st.expander("12 Advanced Tabs - Full Map"):
        st.markdown(
            """
| Advanced tab | Use |
|---|---|
| **7-10% Swing** | Specialist 7-10% scoring view from the latest scan. Tier A is freshest; Tier B may already be moving; Tier C often needs pullback/confirmation |
| **Swing Picks** | Bayesian/enriched shortlist using scanner, operator, earnings, news, and sector evidence |
| **Pullback Reclaim** | Stocks that rallied, corrected toward support, and may become valid only after reclaim trigger holds |
| **Pro Setups** | Professional confluence scoring and trade cards |
| **Side by Side** | Compare long and short candidates in one view |
| **Strategy Finder** | Historical rule search for which strategy template has worked best on a ticker basket |
| **Strategy Lab** | Optional ML overlay for trade quality; it is a filter, not a replacement for scanner rules |
| **Accuracy Lab** | Walk-forward/backtest checks of current swing signal quality |
| **Performance Tracker** | Capture picks and later measure 1D/3D/5D/7D hit rate, drawdown, and stop-first outcomes |
| **Test Cases** | Built-in smoke/regression checks for important scanner logic |
| **Diagnostics** | Cache, ticker, Yahoo/yfinance, file, and data-source debugging |
            """
        )

    with st.expander("Pullback Reclaim Strategy"):
        st.markdown(
            """
Use **12 Advanced -> Pullback Reclaim** for stocks that rallied strongly and are now correcting toward support.

MA5/MA10 timing:
- Below both = watch only.
- Reclaim MA5 = early rebound.
- Above MA5 and MA10 with MA5 > MA10 = confirmed short-term recovery.

Decision meanings:
- **BUY ABOVE RECLAIM**: support held, momentum improved, reclaim and volume evidence are present. Buy only after the displayed trigger holds.
- **SMALL ENTRY / CONFIRM RECLAIM**: early and higher risk; use smaller size.
- **WATCH SUPPORT**: not a buy yet.
- **SKIP - SUPPORT BROKEN**: setup is invalid.

Decision order:

```text
Pullback Decision -> Pullback Checklist -> Reclaim Trigger -> Invalidation -> Targets
```
            """
        )

    with st.expander("How To Decide What To Buy", expanded=True):
        st.markdown(
            """
### Same-Day 5-10% Runner

Use **3 Momentum Runner** or **2 Market Activity -> Catalyst Shock**.

Buy only when:

```text
1. Buy/Watch status is positive
2. Trigger price is clear
3. Live price breaks trigger or reclaims VWAP
4. Volume/RVOL confirms
5. Trap/chase risk is low
6. Stop and target give at least 1:2 reward:risk
```

### Next-Day 5-10% Candidate

Use **4 Pre-Movers** and **5 Best 7-10%** after the prior close. The stock should be coiled, near trigger, not extended, and in a supportive sector/theme.

### Multi-Day Swing Buy

Use **5 Best 7-10%**, then confirm in **6 Long Setups**, **9 Stock Analysis**, and **8 Trade Desk**.

### Sell / Short Candidate

Use **7 Short Setups** and **9 Stock Analysis**. Confirm breakdown, trend weakness, volume, downside room, and cover/invalid level.

### Sector Tailwind Rule

Prefer stocks from strong sectors/themes. If sector is red or weak, require stronger trigger + volume confirmation and consider smaller size.

| Column / concept | Meaning | How to use |
|---|---|---|
| **Buy Decision** | Combined same-day momentum decision | First decision field in Momentum Runner |
| **Shock Status** | Catalyst/volume-shock decision | First decision field in Catalyst Shock |
| **Entry Quality** | Is the current area good for entry? | Timing filter only; not enough by itself |
| **Operator / Op Score** | Accumulation/distribution evidence | Confirmation, not standalone buy signal |
| **VWAP** | Intraday control line | Longs are safer above VWAP; avoid chasing far above VWAP |
| **Today % / PM Chg%** | How much it already moved | Helps detect momentum, but also chase risk |
| **Move Price / Runner Trigger** | Price area to watch | Buy only if trigger holds with volume |
| **Trap Risk / Chase Risk** | Overextension or weak pattern warning | Skip or wait reset |
            """
        )

    with st.expander("Performance Tracking"):
        st.markdown(
            """
Use **12 Advanced -> Performance Tracker** to judge the scanner by real follow-through.

Workflow:
- After a scan, click **Capture Current Candidates** to save candidates from Best 7-10%, Next-Day 5-10%, Long Buy, and optional Momentum Runner.
- After 1-7 trading days, click **Update Outcomes** to fetch daily bars and calculate max gain, drawdown, +3/+5/+7/+10 hits, and whether the stop hit before +5%.
- Review **What Is Working** by Source and Tier. If a tab has low +5% hit rate or high Stop First rate, treat it as watchlist-only until filters improve.

The tracker is saved permanently in `user_data/performance_tracker.sqlite3`,
outside `scanner_cache`. Clearing Diagnostics scan caches does not remove
captured picks or outcome updates. Existing
`scanner_cache/performance_tracker.csv` records are imported automatically the
first time the database opens.
            """
        )

    with st.expander("Market And Universe Behavior"):
        st.markdown(
            """
- The top market selector controls US, SGX, India, and HK-aware tabs.
- Manual/always-include tickers are merged into the selected market universe.
- SGX/HK/India tickers keep Yahoo suffixes such as `.SI`, `.HK`, `.NS`, and `.BO`.
- Movers and Breakouts combine selected-market tickers with live/high-activity sources where available.
- Pre-Market is most useful for US because extended-hours data is more available there.
- Catalyst Shock reuses the latest Long Setups dataframe/cache and does not run a new slow scan.
- HK quality tabs apply a stricter participation gate. A weak-volume `.HK` row may remain as watch-only but should not be promoted as a high-confidence 5-10% candidate.
- If Yahoo rate-limits or blocks data, use cached results carefully and check Diagnostics before relying on the numbers.
            """
        )

    with st.expander("Quick Troubleshooting"):
        st.markdown(
            """
| Symptom | What to try |
|---|---|
| No rows in a tab | Run a fresh scan for the selected market and check filter sliders/search boxes |
| Catalyst Shock is empty | Run Long Setups / market scan first; Catalyst Shock reuses latest scan/cache |
| QS-style stock appears after it already jumped | Treat **MOVED - WAIT PULLBACK** as no fresh buy; wait for VWAP/EMA pullback or next-day flag |
| Need sudden-volume candidates before they move | Use Catalyst Shock **WATCH - LOADED SPRING** plus alerts near Move Price |
| Need same-day 5-10% explosive stocks | Use Momentum Runner; filter Buy Decision for BUY ABOVE TRIGGER rows |
| Buy Decision shows mostly WAIT | Check Runner Trigger, Entry Quality, Volume Ratio, RR Est, and Trap Risk |
| Hot Runner / Wait Reset appears | Wait for VWAP hold, opening-range reclaim, inside day, or pullback/reset |
| Need tomorrow's 5-10% candidates | Use Pre-Movers -> Next-Day 5-10% Watchlist after the prior close |
| A ticker is missing | Add it to Always include tickers, then rerun scan |
| A hot stock is missing from Best 7-10% | It may be too extended; check Momentum Runner, Catalyst Shock, or Movers instead |
| Need institutional-style candidates | Use Big Money and Operator Activity, then confirm in Stock Analysis/Trade Desk |
| Premarket stock is missing | Refresh Pre-Market, lower Min gap %, raise Show top N, and confirm selected market is US |
| HK stocks appear but do not move much | Prefer high-participation rows; low-volume `.HK` rows should stay watch-only |
| Long Term US fallback rows appear | Yahoo live data was blocked or blank; refresh later before acting |
| Yahoo rate-limit warning | Use cached rows only as a reference; rerun later and inspect Diagnostics |
| Wrong market appears | Change the top market radio and scan again |
| Need debugging | Open Advanced -> Diagnostics |
            """
        )

    st.markdown("---")
    st.caption(
        "This scanner is a decision-support tool, not financial advice. Always confirm liquidity, "
        "news/catalyst risk, entry trigger, stop, position size, and reward:risk before trading."
    )
