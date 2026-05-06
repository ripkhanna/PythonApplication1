"""Accuracy Lab Tab renderer.

Readable Streamlit tab code extracted from the original working monolith.
Each render function receives the main runtime globals as ``ctx`` and exposes
them to this module so the body behaves like it did in the single-file app.
"""

def _bind_runtime(ctx: dict) -> None:
    """Expose original app globals to this module for monolith-compatible tab code."""
    globals().update(ctx)

def render_accuracy_lab(ctx: dict) -> None:
    _bind_runtime(ctx)
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
        return _clean_scan_ohlcv(df)

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

