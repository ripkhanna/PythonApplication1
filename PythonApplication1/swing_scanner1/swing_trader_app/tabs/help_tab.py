"""Help tab renderer.

This file contains the normal, readable Streamlit code for the Help tab.
It was expanded from the temporary compile/exec wrapper used during the first
split so the tab can be maintained directly.
"""


def render_help(ctx: dict) -> None:
    """Render the Help tab using objects supplied by the main runtime context."""
    st = ctx["st"]

    st.markdown("## ❓ How to Use the Swing/Long Term Scanner v13.45")
    st.caption(
        "Latest guide: fixed bucket-capped Bayesian scoring, Bayesian ensemble ranking, Trade Desk execution tools, optional Strategy Lab ML filter, "
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
    | 🔍 **Diagnostics** | Debug and verify scan logic | Shows market, universe source, counts, comma-separated scanned ticker list, and latest UI logs |
    | 🧪 **Accuracy Lab** | Backtest / validation notes | Quick walk-forward validation of signal behavior and swing-target logic |
    | 📋 **Trade Desk** | Execution workflow | Buy/Sell trade plans, position sizing, breakout/pullback or breakdown quality, and market breadth risk mode |
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
