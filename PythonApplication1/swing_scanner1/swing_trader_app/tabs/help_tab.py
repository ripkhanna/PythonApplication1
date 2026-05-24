"""Current Help tab renderer for the Swing Scanner."""


def render_help(ctx: dict) -> None:
    st = ctx["st"]

    st.markdown("## Swing Scanner - Current Guide")
    st.caption(
        "12 top tabs - US, SGX, India, HK - swing trading, pre-movers, "
        "7-10% candidates, long/short setups, trade tools, events, and long-term/ETF tools"
    )

    st.markdown(
        """
### Daily Workflow

Use the tabs from left to right:

```text
1 Market Map -> 2 Market Activity -> 3 Pre-Movers -> 4 Best 7-10%
    -> 5 Long Setups -> 6 Short Setups -> 7 Trade Tools
    -> 8 Stock Analysis -> 9 Events -> 10 Long Term / ETF
    -> 11 Advanced -> 12 Help
```

Start with market direction, then active movers, then early candidates, then the strict 7-10% shortlist. Confirm the setup in Long Setups and Stock Analysis before using Trade Tools for entry, stop, target, and position sizing.
        """
    )

    with st.expander("Tab Map", expanded=True):
        st.markdown(
            """
| Top tab | What it contains | Main use |
|---|---|---|
| **1 Market Map** | Sector heatmap and broad market context | Check whether the market/sector backdrop supports long or short trades |
| **2 Market Activity** | Pre-Market, Movers, Breakouts | See what is active now and which stocks are breaking out |
| **3 Pre-Movers** | Pre-Mover score, 7-Star score, Style Explosive Watch | Find names before the large daily move |
| **4 Best 7-10%** | Combined shortlist from Long Setups, Swing Picks, 7-10% Swing, Pro Setups, Pre-Movers | Strictest shortlist for the 7-10% swing objective |
| **5 Long Setups** | Main bullish scanner results | Review BUY/WATCH/WAIT long candidates and all scan columns |
| **6 Short Setups** | Bearish scanner results | Find weak names or hedge candidates |
| **7 Trade Tools** | Trade Desk, Operator Activity, Range Trader | Plan entries/exits and check smart-money/range behavior |
| **8 Stock Analysis** | Single-stock deep dive | Confirm a specific ticker before action |
| **9 Events** | Earnings, Event Predictor | Check earnings/catalyst risk and event/squeeze watchlists |
| **10 Long Term / ETF** | Long Term, ETF Holdings | Longer-term quality/support scoring and ETF universe tools |
| **11 Advanced** | 7-10% Swing, Swing Picks, Pro Setups, Side by Side, Strategy Lab, Accuracy Lab, Test Cases, Diagnostics | Research, QA, diagnostics, and specialist views |
| **12 Help** | This guide | Current workflow and troubleshooting |
            """
        )

    with st.expander("Main Swing Tabs"):
        st.markdown(
            """
### Pre-Movers

Designed to find stocks that may become Movers soon, before the move is already obvious.

Key fields:
- **Pre-Mover Score/Tier/Why**: coil, accumulation, ATR, trigger proximity, relative strength, and whether today's move is still small enough.
- **7-Star Score/Tier/Why**: liquidity, move potential, compression, range shift, divergence/accumulation, one-red hold, and risk/reward.
- **Explosion Score/Tier/Why**: higher-risk 10-20% style watchlist using volatility, squeeze/float/catalyst fuel, and accumulation.

### Best 7-10%

This is the strict combined tab for the user's main goal: candidates with realistic 7-10% swing potential. It checks multiple evidence sources and rejects names with poor room, weak range, bad reward:risk, overextension, or trap/chase risk.

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
| **Test Cases** | Built-in smoke/regression checks |
| **Diagnostics** | Cache, ticker, error, and data-source debugging |
            """
        )

    with st.expander("Market And Universe Behavior"):
        st.markdown(
            """
- The top market selector controls US, SGX, India, and HK aware tabs.
- Manual/always-include tickers are merged into the selected market universe.
- Movers and Breakouts combine selected-market tickers with live/high-activity sources where available.
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
| A ticker is missing | Add it to Always include tickers, then scan again |
| Yahoo rate-limit warning | Wait and rerun later; cached data may still show previous scan results |
| Long Term US fallback rows appear | Yahoo live data was blocked or blank; refresh later for live values before acting |
| Wrong market appears | Use the top market radio, then scan again |
| Need debugging | Open **11 Advanced -> Diagnostics** |
            """
        )

    st.markdown("---")
    st.caption(
        "This scanner is a decision-support tool, not financial advice. "
        "Always confirm liquidity, catalyst risk, entry trigger, stop, and reward:risk before trading."
    )
