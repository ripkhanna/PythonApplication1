"""Strategy Finder tab renderer."""


def _bind_runtime(ctx: dict) -> None:
    """Expose original app globals to this module for monolith-compatible tab code."""
    globals().update(ctx)


def render_strategy_finder(ctx: dict) -> None:
    _bind_runtime(ctx)

    def _sort_ranked(df: pd.DataFrame, col: str) -> pd.DataFrame:
        if df is None or df.empty:
            return df
        out = df.copy()
        if "Meets Target" in out.columns:
            out["_meets_sort"] = out["Meets Target"].astype(str).eq("YES").astype(int)
            by = ["_meets_sort"]
            ascending = [False]
        else:
            by = []
            ascending = []
        if col in out.columns:
            by.append(col)
            ascending.append(False)
        if "Finder Score" in out.columns and col != "Finder Score":
            by.append("Finder Score")
            ascending.append(False)
        return out.sort_values(by, ascending=ascending, kind="stable").drop(columns=["_meets_sort"], errors="ignore").reset_index(drop=True) if by else out

    st.caption("Strategy Finder - historical rule search for the best swing setup template")
    st.info(
        "This tab replays historical candles with the existing signal engine, then ranks strategy templates by "
        "whether they hit the profit target before the stop. It is a finder, not a live buy button: use it to "
        "choose which strategy mode deserves attention for the current ticker basket."
    )

    c1, c2, c3, c4 = st.columns([2.4, 1, 1, 1])
    default_tickers = st.session_state.get("last_scanned_tickers", None) or _active_tickers[:25]
    with c1:
        tickers_txt = st.text_area(
            "Tickers to research",
            value=", ".join(default_tickers[:40]),
            height=88,
            key="strategy_finder_tickers",
            placeholder="AAPL, MSFT, NVDA, D05.SI, O39.SI",
        )
    with c2:
        period = st.selectbox("History", ["1y", "2y", "3y", "5y"], index=1, key="strategy_finder_period")
        horizon = st.selectbox("Max hold window", [5, 7, 10, 15, 20], index=4, key="strategy_finder_horizon")
    with c3:
        target_pct = st.slider("Target %", 3.0, 12.0, 6.0, step=0.5, key="strategy_finder_target")
        stop_pct = st.slider("Stop %", 2.0, 10.0, 4.0, step=0.5, key="strategy_finder_stop")
    with c4:
        step = st.slider("Sample step", 1, 10, 3, step=1, key="strategy_finder_step")
        max_tickers = st.slider("Max tickers", 5, 100, 30, step=5, key="strategy_finder_max_tickers")

    c5, c6, c7 = st.columns([1, 1, 2])
    with c5:
        min_trades = st.slider("Min trades", 3, 50, 8, step=1, key="strategy_finder_min_trades")
    with c6:
        min_win_pct = st.slider("Min win %", 50, 90, 70, step=5, key="strategy_finder_min_win_pct")
    with c7:
        sort_by = st.selectbox(
            "Rank by",
            ["Win %", "Finder Score", "Expectancy %", "PI", "Trades"],
            index=0,
            key="strategy_finder_sort_by",
        )
        st.caption(
            "Winner label: target before stop inside the hold window. Same-day target/stop ties count as stop first. "
            "A setup is not qualified unless it clears the selected Min win %."
        )

    click_cb = globals().get("_set_top_status_for_next_run")
    btn_kwargs = {}
    if callable(click_cb):
        btn_kwargs = {
            "on_click": click_cb,
            "args": ("Finding historically strongest strategy templates...", "Strategy Finder", "SF", "running"),
        }

    if st.button("Find Best Strategy", type="primary", key="strategy_finder_run", **btn_kwargs):
        tickers = [t.strip().upper() for t in tickers_txt.replace("\n", ",").split(",") if t.strip()]
        try:
            tickers = _unique_keep_order(tickers)
        except Exception:
            tickers = list(dict.fromkeys(tickers))
        tickers = tickers[:max_tickers]
        if not tickers:
            st.error("Enter at least one ticker.")
        else:
            with st.spinner("Building strategy-finder samples..."):
                samples = _strategy_finder_build_samples(
                    tuple(tickers),
                    period=period,
                    horizon=horizon,
                    tp_pct=target_pct,
                    sl_pct=stop_pct,
                    step=step,
                )
            samples, precision_specs = _strategy_finder_add_precision_strategies(
                samples,
                min_trades=min_trades,
                min_win_pct=min_win_pct,
                tp_pct=target_pct,
                sl_pct=stop_pct,
                max_variants=12,
            )
            ranked = _strategy_finder_rank(
                samples,
                min_trades=min_trades,
                tp_pct=target_pct,
                sl_pct=stop_pct,
                min_win_pct=min_win_pct,
            )
            exit_profiles = _strategy_finder_optimize_exits(
                samples,
                min_trades=min_trades,
                min_win_pct=min_win_pct,
            )
            ranked = _sort_ranked(ranked, sort_by)
            st.session_state["strategy_finder_samples"] = samples
            st.session_state["strategy_finder_ranked"] = ranked
            st.session_state["strategy_finder_exit_profiles"] = exit_profiles
            st.session_state["strategy_finder_precision_specs"] = precision_specs
            st.session_state["strategy_finder_params"] = {
                "tickers": tickers,
                "period": period,
                "horizon": horizon,
                "target_pct": target_pct,
                "stop_pct": stop_pct,
                "step": step,
                "min_trades": min_trades,
                "min_win_pct": min_win_pct,
                "precision_variants": len(precision_specs),
            }
            if not ranked.empty:
                st.session_state["strategy_finder_selected"] = str(ranked.iloc[0]["Strategy"])

    samples = st.session_state.get("strategy_finder_samples", pd.DataFrame())
    ranked = st.session_state.get("strategy_finder_ranked", pd.DataFrame())
    exit_profiles = st.session_state.get("strategy_finder_exit_profiles", pd.DataFrame())
    precision_specs = st.session_state.get("strategy_finder_precision_specs", {})
    params = st.session_state.get("strategy_finder_params", {})

    if isinstance(samples, pd.DataFrame) and not samples.empty and isinstance(ranked, pd.DataFrame) and not ranked.empty:
        ranked = _sort_ranked(ranked, sort_by)

        best = ranked.iloc[0].to_dict()
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Best strategy", best.get("Strategy", "-"))
        m2.metric("Verdict", best.get("Verdict", "-"))
        m3.metric("Win %", f"{best.get('Win %', 0):.1f}%")
        m4.metric("Expectancy", f"{best.get('Expectancy %', 0):.2f}%")
        m5.metric("Samples", f"{len(samples):,}")

        qualified_count = int((ranked.get("Meets Target", pd.Series(dtype=str)).astype(str) == "YES").sum()) if "Meets Target" in ranked.columns else 0
        if qualified_count <= 0:
            st.error(
                f"No strategy reached the {min_win_pct}% win-rate gate with at least {min_trades} trades. "
                "That is a useful result: this basket should not be traded with these target/stop settings."
            )
        else:
            st.success(f"{qualified_count} strategy variant(s) cleared the {min_win_pct}% win-rate gate.")

        st.dataframe(
            ranked,
            width="stretch",
            hide_index=True,
            column_config={
                "Strategy": st.column_config.TextColumn("Strategy", width=160),
                "Verdict": st.column_config.TextColumn("Verdict", width=110),
                "Meets Target": st.column_config.TextColumn("70% Gate", width=80),
                "Trades": st.column_config.NumberColumn("Trades", width=70),
                "Tickers": st.column_config.NumberColumn("Tickers", width=70),
                "Win %": st.column_config.NumberColumn("Win %", format="%.1f", width=75),
                "Target Win %": st.column_config.NumberColumn("Target", format="%.0f", width=70),
                "Base Win %": st.column_config.NumberColumn("Base %", format="%.1f", width=75),
                "Edge %": st.column_config.NumberColumn("Edge", format="%.1f", width=70),
                "Expectancy %": st.column_config.NumberColumn("Exp %", format="%.2f", width=75),
                "PI": st.column_config.NumberColumn("PI", format="%.2f", width=65),
                "Avg MaxGain %": st.column_config.NumberColumn("Avg Gain", format="%.2f", width=85),
                "Avg MaxDD %": st.column_config.NumberColumn("Avg DD", format="%.2f", width=80),
                "Finder Score": st.column_config.NumberColumn("Finder", format="%.2f", width=80),
            },
        )

        chart_cols = ["Strategy", "Finder Score", "Expectancy %", "PI", "Win %"]
        chart_df = ranked[chart_cols].head(12).set_index("Strategy")
        st.bar_chart(chart_df[["Finder Score", "Expectancy %", "PI"]])

        st.markdown("### Improved Exit Profiles")
        if isinstance(exit_profiles, pd.DataFrame) and not exit_profiles.empty:
            exit_ok = exit_profiles["Meets Target"].astype(str).eq("YES")
            if exit_ok.any():
                best_exit = exit_profiles[exit_ok].iloc[0].to_dict()
                st.success(
                    f"Best qualified profile: {best_exit.get('Strategy')} "
                    f"{best_exit.get('Exit Profile')} with {best_exit.get('Win %')}% win "
                    f"and {best_exit.get('Expectancy %')}% expectancy."
                )
            else:
                st.warning(
                    f"No payoff-aware exit profile reached {min_win_pct}% with positive expectancy. "
                    "The strategy problem is not just the entry filter."
                )
            st.dataframe(
                exit_profiles.head(60),
                width="stretch",
                hide_index=True,
                column_config={
                    "Strategy": st.column_config.TextColumn("Strategy", width=160),
                    "Exit Profile": st.column_config.TextColumn("Exit", width=120),
                    "Meets Target": st.column_config.TextColumn("70% + Exp", width=90),
                    "Trades": st.column_config.NumberColumn("Trades", width=70),
                    "Win %": st.column_config.NumberColumn("Win %", format="%.1f", width=70),
                    "Expectancy %": st.column_config.NumberColumn("Exp %", format="%.2f", width=75),
                    "PI": st.column_config.NumberColumn("PI", format="%.2f", width=65),
                    "Payoff": st.column_config.NumberColumn("Payoff", format="%.2f", width=70),
                    "Avg MaxGain %": st.column_config.NumberColumn("Avg Gain", format="%.2f", width=85),
                    "Avg MaxDD %": st.column_config.NumberColumn("Avg DD", format="%.2f", width=80),
                },
            )
        else:
            st.caption("No exit profiles available. Use a max hold window of at least 10-20 days for exit optimization.")

        st.markdown("### Strategy Drilldown")
        selected_default = st.session_state.get("strategy_finder_selected", str(best.get("Strategy", "")))
        options = ranked["Strategy"].astype(str).tolist()
        selected_index = options.index(selected_default) if selected_default in options else 0
        selected = st.selectbox(
            "Strategy to inspect",
            options,
            index=selected_index,
            key="strategy_finder_selected",
        )

        trades = _strategy_finder_strategy_trades(samples, selected, limit=250)
        if not trades.empty:
            st.dataframe(trades, width="stretch", hide_index=True)
        else:
            st.caption("No historical trades matched this strategy.")

        st.markdown("### Apply To Latest Scan")
        latest_long = st.session_state.get("df_long_master", pd.DataFrame())
        if latest_long.empty:
            latest_long = st.session_state.get("df_long", pd.DataFrame())
        if latest_long.empty:
            st.caption("Run a market scan first to see current candidates for the selected finder strategy.")
        else:
            current = _strategy_finder_apply_to_scan(latest_long, selected, precision_specs)
            if current.empty:
                st.caption("No latest-scan rows match this finder strategy.")
            else:
                show_cols = [
                    "Ticker", "Action", "Finder Strategy", "Finder Rank Score", "Rise Prob",
                    "Score", "Quality Score", "Next-Day Score", "Vol Ratio", "Today %",
                    "Setup Type", "Support Tier", "Trap Risk", "Signals",
                ]
                show_cols = [c for c in show_cols if c in current.columns]
                st.dataframe(current[show_cols].head(100), width="stretch", hide_index=True)

        with st.expander("Finder run details"):
            st.write(params)
            st.caption(
                "Finder Score combines edge over the sample base rate, expectancy, PI, and enough opportunity count "
                "to avoid over-ranking tiny sample winners."
            )
    elif isinstance(samples, pd.DataFrame) and samples.empty and st.session_state.get("strategy_finder_params"):
        st.error("No usable historical samples. Try more liquid tickers, longer history, or a larger ticker basket.")
    else:
        st.caption("Choose a ticker basket and click Find Best Strategy.")
