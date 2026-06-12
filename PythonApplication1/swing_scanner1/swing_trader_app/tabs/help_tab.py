"""Current Help tab renderer for the Swing Scanner."""


def render_help(ctx: dict) -> None:
    st = ctx["st"]

    st.markdown("## Swing Scanner - Current Guide")
    st.caption(
        "13 top tabs - US, SGX, India, HK - market activity, Big Money Radar, momentum runners, "
        "pre-movers, 7-10% candidates, long/short setups, trade tools, events, and long-term/ETF tools"
    )

    st.markdown(
        """
### Daily Workflow

Use the tabs from left to right:

```text
1 Market Map -> 2 Market Activity / Big Money -> 3 Momentum Runner -> 4 Pre-Movers
    -> 5 Best 7-10% -> 6 Long Setups -> 7 Short Setups
    -> 8 Trade Tools -> 9 Stock Analysis -> 10 Events
    -> 11 Long Term / ETF -> 12 Advanced -> 13 Help
```

Start with market direction, then active movers and Big Money Radar. For **same-day explosive 5-10% trades**, go to **3 Momentum Runner** and use the **Buy Decision** column first. For tomorrow or multi-day swings, use Pre-Movers and Best 7-10%. Confirm the setup in Long Setups and Stock Analysis before using Trade Tools for entry, stop, target, and position sizing.
        """
    )

    with st.expander("Tab Map", expanded=True):
        st.markdown(
            """
| Top tab | What it contains | Main use |
|---|---|---|
| **1 Market Map** | Sector heatmap and broad market context | Check whether the market/sector backdrop supports long or short trades |
| **2 Market Activity** | Pre-Market, Movers, Big Money, Breakouts | See what is active now, where institutional-style accumulation appears, and which stocks are breaking out |
| **3 Momentum Runner** | Day-1 Ignition, Controlled Runner, Hot Runner / Wait Reset | Track stocks that are already running without weakening strict swing filters |
| **4 Pre-Movers** | Next-Day 5-10% Watchlist, Pre-Mover score, 7-Star score, Style Explosive Watch | Find names before the large daily move or prepare the previous-day list for tomorrow |
| **5 Best 7-10%** | Combined shortlist from Long Setups, Swing Picks, 7-10% Swing, Pro Setups, Pre-Movers, and PM strength | Strictest shortlist for the 7-10% swing objective |
| **6 Long Setups** | Main bullish scanner results | Review BUY/WATCH/WAIT long candidates and all scan columns |
| **7 Short Setups** | Bearish scanner results | Find weak names or hedge candidates |
| **8 Trade Tools** | Trade Desk, Operator Activity, Range Trader | Plan entries/exits and check smart-money/range behavior |
| **9 Stock Analysis** | Single-stock deep dive | Confirm a specific ticker before action |
| **10 Events** | Earnings, Event Predictor | Check earnings/catalyst risk and event/squeeze watchlists |
| **11 Long Term / ETF** | Long Term, ETF Holdings | Longer-term quality/support scoring and ETF universe tools |
| **12 Advanced** | 7-10% Swing, Swing Picks, Pro Setups, Side by Side, Strategy Lab, Accuracy Lab, Performance Tracker, Test Cases, Diagnostics | Research, QA, diagnostics, and specialist views |
| **13 Help** | This guide | Current workflow and troubleshooting |
            """
        )

    with st.expander("Main Swing Tabs"):
        st.markdown(
            """
### Momentum Runner

Use this tab for **explosive same-day 5-10% candidates** and stocks already moving now. It is separate from Best 7-10%, so hot runners do not pollute the stricter multi-day swing shortlist.

Main decision columns are now grouped at the start of the table. **Runner Trigger is placed immediately after Buy Checklist** because it is the exact price/level to watch before entering:

```text
Ticker -> Buy Decision -> Buy Checklist -> Runner Trigger -> Runner Tier -> Firefly Pass -> Explosive Buy -> Entry Quality -> Tradeable Buy -> Sector Tailwind -> Sector -> Runner Invalid -> Target 1 +5% -> Target 2 +10%
```

Use **Buy Decision** as the first decision field:

| Buy Decision | Meaning | Action |
|---|---|---|
| **BUY ABOVE TRIGGER - best candidate** | Best combination of Firefly, entry quality, volume, reward:risk, and risk controls | Prepare buy only above Runner Trigger with VWAP/ORB confirmation |
| **BUY ABOVE TRIGGER - confirm entry** | Good candidate, but still needs live trigger confirmation | Buy only if price breaks trigger and holds VWAP |
| **BUY WATCH - explosive; confirm VWAP/ORB** | Explosive watch candidate but not perfect yet | Alert only; wait for VWAP/opening-range confirmation |
| **WATCH - needs Firefly/VWAP confirmation** | Moving name but missing one or more safety layers | Do not buy yet |
| **WAIT - not explosive enough** | Not a 5-10% same-day priority | Ignore for momentum trade |
| **SKIP - trap/avoid/broken** | Risk, trap, or avoid condition detected | Do not trade |
| **SKIP - chase risk / wait reset** | Already too extended | Wait for pullback/reset |

Strongest filter for your 5-10% same-day goal:

```text
Runner Tier = A++ Firefly 5-Layer Explosive
Buy Decision = BUY ABOVE TRIGGER - best candidate OR BUY ABOVE TRIGGER - confirm entry
Firefly Pass = YES
Entry Quality = A+ or A
Trap Risk = blank/low
RR Est >= 1:2
Price breaks Runner Trigger
Volume remains strong after the open
```

Firefly 5-layer logic:
- **Layer 1 - Market Structure**: stock/sector/market structure should support momentum, not a range-bound chop.
- **Layer 2 - Volatility Window**: ATR/move potential should be high enough for 5-10%, but not so extreme that it becomes a random trap.
- **Layer 3 - Event Guard**: event-risk days and abnormal catalyst days are flagged so the setup is not treated as normal.
- **Layer 4 - Entry Precision**: signal + volume + structure alignment must occur together.
- **Layer 5 - Dynamic Exit**: use VWAP/9EMA/momentum fade rules instead of a fixed static stop only.

Buckets:
- **A++ Firefly 5-Layer Explosive**: strictest same-day 5-10% candidate bucket.
- **A+ Explosive 5-10% Today**: strong explosive candidate, but may need extra confirmation.
- **A - Day-1 Ignition**: early runner with PM/today strength, quality/fuel, liquidity, and no avoid/trap flag.
- **B - Controlled Runner**: moving but not yet overheated.
- **C - Hot Runner / Wait Reset**: already extended; wait for VWAP hold, inside day, pullback, or reset before considering entry.

Example behavior: a stock like NVTS can appear as **Hot Runner / Wait Reset** when it is +20% today and already up strongly over 5-20 days. That means "track it, but do not force it into a clean swing entry."

Do not buy just because a stock is green. For same-day runners, buy only after **Runner Trigger + VWAP/opening-range confirmation**.

### Pre-Movers

Designed to find stocks that may become Movers soon, before the move is already obvious.

Key fields:
- **Next-Day 5-10% Watchlist**: previous-day close / before-open prep list for stocks with room, quality, reward:risk, and controlled extension that can attempt a 5-10% next-day move.
- **Pre-Mover Score/Tier/Why**: coil, accumulation, ATR, trigger proximity, relative strength, and whether today's move is still small enough.
- **7-Star Score/Tier/Why**: liquidity, move potential, compression, range shift, divergence/accumulation, one-red hold, and risk/reward.
- **Explosion Score/Tier/Why**: higher-risk 10-20% style watchlist using volatility, squeeze/float/catalyst fuel, and accumulation.

Use **Next-Day 5-10% Watchlist** after the prior close and before the next market session. It is meant for planning triggers, not chasing green candles after the move has already stretched. HK names now need participation confirmation, so low-volume watch rows are capped instead of promoted as 5-10% candidates.

### Big Money Radar

Located under **2 Market Activity -> Big Money**. This ranks the latest scan for institutional-style sponsorship plus short-term move potential. It does not hardcode tickers. It scores operator accumulation, VWAP control, volume expansion, pocket-pivot/accumulation clues, relative strength, pre-mover score, quality, ATR, and extension risk.

Use the **A - Big Money + Short-Term** and **B - Institutional Watch** tiers as the first institutional watchlist. The optional holder snapshot button checks Yahoo institutional/mutual-fund holder names for the displayed top rows, but holder/13F data is delayed and should be treated as confirmation only.

### Best 7-10%

This is the strict combined tab for the user's main goal: candidates with realistic 7-10% swing potential. It checks multiple evidence sources and rejects names with poor room, weak range, bad reward:risk, overextension, or trap/chase risk.

Latest behavior:
- **PM Chg%** is now included as a quality confirmation when the setup already has supporting evidence.
- Constructive PM strength can improve the score.
- Overextended PM moves and red PM moves are penalized.
- The grid shows **PM Chg%** and **PM Price** next to trigger/invalid levels.

### Long Setups

This is now a main top-level tab after Best 7-10%. Use it to review the full bullish scanner grid, including strategy results, quality score, probability, support/dip labels, pre-mover fields, 7-Star fields, and tradeability gates.

### Short Setups

Use after Long Setups to find weak names, possible hedges, and bearish continuation candidates.
            """
        )

    with st.expander("Trade And Confirmation Tools"):
        st.markdown(
            """
### Trade Tools

Nested tabs:
- **Trade Desk**: entry zone, stop, targets, risk/reward, and position sizing.
- **Operator Activity**: accumulation/distribution footprints from scan data.
- **Range Trader**: support/resistance channel trades with buy/sell zones.

### Stock Analysis

Use this for one ticker at a time. It checks price history, moving averages, RSI, support/resistance, volume, operator labels, and scanner context.

### Events

Nested tabs:
- **Earnings**: upcoming earnings risk.
- **Event Predictor**: event/catalyst/squeeze watchlist. These are watchlist signals, not automatic buys.
            """
        )

    with st.expander("Long Term / ETF"):
        st.markdown(
            """
### Long Term

Long-term quality plus near-support scoring for US and SGX stocks.

The US Stocks view has no-empty-grid protection:
- If Yahoo fundamentals are sparse, the scorer can still keep conservative rows when price history has enough evidence.
- If Yahoo blocks every row, fallback rows are marked as **US fallback seed** and should be refreshed later before acting.
- Grid labels are ASCII-cleaned so fallback rows display as readable text.

### ETF Holdings

Use this to inspect ETF constituents and add universe ideas for scans.
            """
        )

    with st.expander("Advanced Tabs"):
        st.markdown(
            """
| Advanced tab | Use |
|---|---|
| **7-10% Swing** | Specialist 7-10% scoring view from the latest scan |
| **Swing Picks** | Enriched shortlist with probability, operator, sector, and event evidence |
| **Pro Setups** | Professional confluence scoring and trade cards |
| **Side by Side** | Compare long and short candidates |
| **Strategy Lab** | Research layer for strategy experiments |
| **Accuracy Lab** | Backtest and validation tools |
| **Performance Tracker** | Save each day's scanner picks, then update 1D/3D/5D/7D max gain, drawdown, hit rate, and stop-first outcomes |
| **Test Cases** | Built-in smoke/regression checks |
| **Diagnostics** | Cache, ticker, error, and data-source debugging |
            """
        )

    with st.expander("Performance Tracking"):
        st.markdown(
            """
Use **12 Advanced -> Performance Tracker** to judge the scanner by real follow-through.

Workflow:
- After a scan, click **Capture Current Candidates** to save candidates from Best 7-10%, Next-Day 5-10%, Long Buy, and optional Momentum Runner.
- After 1-7 trading days, click **Update Outcomes** to fetch daily bars and calculate max gain, drawdown, +3/+5/+7/+10 hits, and whether the stop hit before +5%.
- Review **What Is Working** by Source and Tier. If a tab has low +5% hit rate or high Stop First rate, treat it as watchlist-only until the filters improve.

The tracker is saved at `scanner_cache/performance_tracker.csv` and is kept when Diagnostics clears normal scan cache files.
            """
        )

    with st.expander("Market And Universe Behavior"):
        st.markdown(
            """
- The top market selector controls US, SGX, India, and HK aware tabs.
- Manual/always-include tickers are merged into the selected market universe.
- Movers and Breakouts combine selected-market tickers with live/high-activity sources where available.
- Pre-Market uses multiple generic data paths: Yahoo quote fields, `fast_info`, then 5-minute intraday bars with `prepost=True`. No ticker is hardcoded.
- HK quality tabs apply a stricter participation gate. A .HK ticker with weak volume ratio and no live/technical participation can remain in Long Setups as a watch row, but it should be rejected from Best 7-10% and Next-Day 5-10%.
- SGX/HK/India tickers keep their native Yahoo suffixes such as `.SI`, `.HK`, and `.NS`.
- If Yahoo rate-limits, use Diagnostics to inspect errors and rerun later.
            """
        )

    with st.expander("Quick Troubleshooting"):
        st.markdown(
            """
| Symptom | What to try |
|---|---|
| No rows in a tab | Run a fresh scan for the selected market and check filter sliders/search boxes |
| A hot stock is not in Best 7-10% | Check **3 Momentum Runner**; it may be too extended for a clean swing entry |
| Need 5-10% same-day explosive stocks | Use **3 Momentum Runner**, then filter **Buy Decision** for BUY ABOVE TRIGGER rows |
| Buy Decision shows mostly WAIT | Check Runner Trigger, Entry Quality, Volume Ratio, RR Est, and Trap Risk. WAIT means the stock is not ready yet, not necessarily bad |
| A stock is marked Hot Runner / Wait Reset | Wait for VWAP hold, opening-range reclaim, inside day, or pullback/reset |
| Need tomorrow's 5-10% candidates before market opens | Use **4 Pre-Movers -> Next-Day 5-10% Watchlist** after the prior close |
| Stocks selected do not give returns | Use **12 Advanced -> Performance Tracker** to capture picks and compare hit rate by tab/tier after 1D/3D/5D/7D |
| HK stocks appear but do not move much | Prefer **5 Best 7-10%** or **4 Pre-Movers -> Next-Day 5-10%**; low-volume .HK watch rows are now marked/rejected as low HK participation |
| Premarket stock is missing | Click Refresh in Pre-Market, lower Min gap %, raise Show top N, and confirm the selected market is US |
| A ticker is missing from scan results | Add it to Always include tickers for the next full scan |
| Need institutional / hedge-fund style candidates | Use **2 Market Activity -> Big Money**; then confirm entries in Long Setups and Stock Analysis |
| Yahoo rate-limit warning | Wait and rerun later; cached data may still show previous scan results |
| Long Term US fallback rows appear | Yahoo live data was blocked or blank; refresh later for live values before acting |
| Wrong market appears | Use the top market radio, then scan again |
| Need debugging | Open **12 Advanced -> Diagnostics** |
            """
        )


    with st.expander("How To Decide What To Buy", expanded=True):
        st.markdown(
            """
### Sector Tailwind Rule

For 5-10% explosive trades, prefer stocks from the strongest sector/theme of the day. The scanner now shows **Sector Tailwind** beside the decision columns:

| Sector Tailwind | Meaning | Action |
|---|---|---|
| **GREEN/LEADER - preferred** | Sector is green today, or stock is showing sector/market leadership | Best candidates |
| **UNKNOWN/MIXED** | Sector data unavailable or mixed | Trade only if Firefly/VWAP/volume are strong |
| **NEUTRAL** | Stock is moving but sector is not clearly strong | Lower priority |
| **RED/WEAK** | Sector is weak/red | Usually skip unless exceptional news + volume |

Best same-day buys should have:

```text
Buy Decision = BUY ABOVE TRIGGER
Sector Tailwind = GREEN/LEADER - preferred
Firefly Pass = YES
Entry Quality = A or A+
Volume confirmation
```

### Fast Buy Decision Rule

For explosive same-day trades, buy from **3 Momentum Runner** only when the decision stack agrees.

```text
1. Buy Decision = BUY ABOVE TRIGGER - best candidate / confirm entry
2. Runner Tier = A++ Firefly 5-Layer Explosive or A+ Explosive 5-10% Today
3. Firefly Pass = YES
4. Entry Quality = A+ or A
5. Explosive Buy is positive
6. RR Est >= 1:2
7. Trap Risk is blank/low
8. Live price breaks Runner Trigger and holds VWAP/opening range
```

If any of these fail, the correct action is usually **WAIT**, not chase.

### Difference Between Entry Quality And Buy Decision

| Column | Meaning | How to use |
|---|---|---|
| **Entry Quality** | Is the current price area good for entry? | Timing filter only |
| **Firefly Pass** | Do the 5 market/volatility/event/entry/exit layers align? | Setup quality filter |
| **Explosive Buy** | Is the stock a possible 5-10% same-day runner? | Momentum filter |
| **Buy Decision** | Combines all key conditions into one action label | Final decision field |

Entry Quality alone is not enough. A+ entry with weak volume or trap risk should still be skipped.
            """
        )


    st.markdown(
        """
### Pullback Reclaim strategy

Use **Advanced → Pullback Reclaim** for stocks that rallied strongly and are now correcting toward support.

**MA5/MA10 timing:** below both = watch only; reclaim MA5 = early rebound; above MA5 and MA10 with MA5 > MA10 = confirmed short-term recovery. A fresh market scan is required to populate these values.

- **BUY ABOVE RECLAIM**: support held, momentum improved, reclaim and volume evidence are present. Buy only after the displayed trigger holds.
- **SMALL ENTRY / CONFIRM RECLAIM**: early and higher risk; use smaller size.
- **WATCH SUPPORT**: not a buy yet.
- **SKIP – SUPPORT BROKEN**: setup is invalid.

Decision order: `Pullback Decision → Pullback Checklist → Reclaim Trigger → Invalidation → Targets`.
        """
    )

    st.markdown("---")
    st.caption(
        "This scanner is a decision-support tool, not financial advice. "
        "Always confirm liquidity, catalyst risk, entry trigger, stop, and reward:risk before trading."
    )
