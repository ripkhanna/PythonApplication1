"""Strategy Lab Tab renderer.

Readable Streamlit tab code extracted from the original working monolith.
Each render function receives the main runtime globals as ``ctx`` and exposes
them to this module so the body behaves like it did in the single-file app.
"""

def _bind_runtime(ctx: dict) -> None:
    """Expose original app globals to this module for monolith-compatible tab code."""
    globals().update(ctx)

def render_strategy_lab(ctx: dict) -> None:
    _bind_runtime(ctx)
    st.caption("🧠 Strategy Lab — optional ML filter for trade quality, not a replacement for Bayesian")
    st.info(
        "This trains a model to answer: did this setup hit the profit target before the stop within N trading days? "
        "The live scanner remains Bayesian ensemble first. Use ML only if it beats the baseline on chronological test data."
    )
    backend = "LightGBM" if _lgbm_available else "sklearn fallback" if _sklearn_strategy_available else "not installed"
    st.caption(f"ML backend: **{backend}** · Preferred install: `pip install lightgbm scikit-learn`")

    sl1, sl2, sl3, sl4 = st.columns([2, 1, 1, 1])
    with sl1:
        lab_tickers_txt = st.text_area("Training tickers", value=", ".join(_active_tickers[:25]), height=80, key="strategy_lab_tickers")
    with sl2:
        lab_period = st.selectbox("History", ["1y", "2y", "3y", "5y"], index=1, key="strategy_lab_period")
        lab_horizon = st.slider("Horizon days", 5, 20, 10, step=1, key="strategy_lab_horizon")
    with sl3:
        lab_tp = st.slider("Target %", 3.0, 12.0, 6.0, step=0.5, key="strategy_lab_tp")
        lab_sl = st.slider("Stop %", 2.0, 10.0, 4.0, step=0.5, key="strategy_lab_sl")
    with sl4:
        lab_step = st.slider("Sample step", 1, 10, 3, step=1, key="strategy_lab_step")
        lab_max_tickers = st.slider("Max tickers", 5, 80, 30, step=5, key="strategy_lab_max_tickers")

    if not (_lgbm_available or _sklearn_strategy_available):
        st.warning("Install `lightgbm` or `scikit-learn` to train the Strategy Lab model.")

    if st.button("🧠 Train Strategy Lab model", type="primary", key="strategy_lab_train"):
        lab_tickers = _unique_keep_order([t.strip().upper() for t in lab_tickers_txt.replace("\n", ",").split(",") if t.strip()])[:lab_max_tickers]
        if not lab_tickers:
            st.error("Enter at least a few tickers.")
        else:
            with st.spinner("Building historical +target before -stop training set..."):
                ds = _strategy_build_dataset(tuple(lab_tickers), period=lab_period, horizon=lab_horizon, tp_pct=lab_tp, sl_pct=lab_sl, step=lab_step)
            if ds.empty:
                st.error("No usable training rows. Try longer history, more liquid tickers, or more tickers.")
            else:
                feature_cols = [c for c in ds.columns if c not in ["Ticker", "Date", "Target", "MaxGain%", "MaxDD%", "PathOutcome", "BaselineScore"]]
                bundle, report = _strategy_train_model(ds, feature_cols)
                st.session_state["strategy_lab_dataset"] = ds
                st.session_state["strategy_lab_model"] = bundle
                st.session_state["strategy_lab_report"] = report

    report = st.session_state.get("strategy_lab_report")
    if report:
        if "Error" in report:
            st.error(report["Error"])
        else:
            metric_cols = st.columns(5)
            metric_cols[0].metric("ML AUC", report.get("ML AUC", "–"))
            metric_cols[1].metric("Baseline AUC", report.get("Baseline AUC", "–"))
            metric_cols[2].metric("AUC Edge", report.get("AUC Edge", "–"))
            metric_cols[3].metric("Top 10% ML Win", f"{report.get('Top 10% ML Win%', '–')}%")
            metric_cols[4].metric("Use ML?", report.get("Recommended", "–"))
            summary_cols = ["Model", "Samples", "Train", "Test", "Base Rate", "ML Accuracy", "Baseline Accuracy", "ML Precision", "Top 10% Baseline Win%", "Top 10% Avg MaxGain%", "Top 10% Avg MaxDD%", "Brier", "Split Date", "Recommended"]
            st.dataframe(pd.DataFrame([{k: report.get(k) for k in summary_cols if k in report}]), width="stretch", hide_index=True)
            imp = report.get("Importance", [])
            if imp:
                st.markdown("**Top ML features**")
                st.dataframe(pd.DataFrame(imp, columns=["Feature", "Importance"]), width="stretch", hide_index=True)
            if str(report.get("Recommended", "")).startswith("YES"):
                st.success("ML improved the baseline on this test. Use it as a trade-quality filter, not as the only signal.")
            else:
                st.warning("ML did not clearly beat the Bayesian ensemble. Keep Bayesian ensemble primary.")

    ds_prev = st.session_state.get("strategy_lab_dataset")
    if isinstance(ds_prev, pd.DataFrame) and not ds_prev.empty:
        with st.expander("Training data sample"):
            st.dataframe(ds_prev.tail(200), width="stretch", hide_index=True)

    st.markdown("---")
    st.markdown("### Apply trained ML overlay to current Swing Picks")
    latest_swing = st.session_state.get("df_swing_picks", pd.DataFrame())
    if st.session_state.get("strategy_lab_model") is None:
        st.caption("Train a Strategy Lab model first.")
    elif latest_swing.empty:
        st.caption("Build 🎯 Swing Picks first, then return here to apply the ML overlay.")
    elif st.button("Add ML quality/risk columns to latest Swing Picks", key="strategy_apply_overlay"):
        st.session_state["latest_swing_picks_ml"] = _strategy_apply_to_current(st.session_state.get("strategy_lab_model"), latest_swing)

    latest_ml = st.session_state.get("latest_swing_picks_ml")
    if isinstance(latest_ml, pd.DataFrame) and not latest_ml.empty:
        show_cols = [c for c in ["Ticker", "Swing Verdict", "ML Trade Quality", "ML Failure Risk", "Suggested Size", "Final Swing Score", "Bayes Score", "Operator Score", "Trap Risk", "Why"] if c in latest_ml.columns]
        st.dataframe(latest_ml[show_cols], width="stretch", hide_index=True)

