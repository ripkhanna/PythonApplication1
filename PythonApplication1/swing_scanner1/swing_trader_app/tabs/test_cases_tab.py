
from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import streamlit as st


STRATEGIES = [
    "Strict",
    "Balanced",
    "Discovery",
    "Support Entry",
    "Premarket Momentum",
    "High Volume",
    "High Conviction",
    "PSM Strategy",
]

REQUIRED_LONG_COLUMNS = [
    "Ticker", "Action", "Entry Quality", "Tradeable Buy", "Quality Score",
    "Next-Day Score", "Next-Day Rating", "Next-Day Move", "7D Move Est",
    "Upside to Res", "RR Est", "Rise Prob", "Score", "Signals",
]

REQUIRED_EVENT_COLUMNS = [
    "Ticker", "SEDG-Type", "Squeeze Score", "Post-Event Score", "Trigger",
    "Vol Ratio", "Today %", "52W Dist",
]

REQUIRED_PREMARKET_COLUMNS = [
    "Ticker", "Price", "PM Chg%", "Vol Ratio", "Signal",
]

TAB_MODULES = {
    "Sector Heatmap": "swing_trader_app.tabs.sectors_tab",
    "Trade Desk": "swing_trader_app.tabs.trade_desk_tab",
    "Long Setups": "swing_trader_app.tabs.scan_results_tabs",
    "Swing Picks": "swing_trader_app.tabs.swing_picks_tab",
    "Movers/Losers": "swing_trader_app.tabs.top_movers_tab",
    "Pre-Market": "swing_trader_app.tabs.premarket_tab",
    "Short Setups": "swing_trader_app.tabs.scan_results_tabs",
    "Operator Activity": "swing_trader_app.tabs.operator_activity_tab",
    "Breakout Scanner": "swing_trader_app.tabs.breakout_scanner_tab",
    "Side by Side": "swing_trader_app.tabs.scan_results_tabs",
    "ETF Holdings": "swing_trader_app.tabs.etf_holdings_tab",
    "Stock Analysis": "swing_trader_app.tabs.stock_analysis_tab",
    "Earnings": "swing_trader_app.tabs.earnings_tab",
    "Event Predictor": "swing_trader_app.tabs.event_predictor_tab",
    "Long Term": "swing_trader_app.tabs.long_term_tab",
    "Diagnostics": "swing_trader_app.tabs.diagnostics_tab",
    "Accuracy Lab": "swing_trader_app.tabs.accuracy_lab_tab",
    "Strategy Lab": "swing_trader_app.tabs.strategy_lab_tab",
    "Help": "swing_trader_app.tabs.help_tab",
}


def _status(ok: bool | None) -> str:
    if ok is True:
        return "✅ PASS"
    if ok is False:
        return "❌ FAIL"
    return "⚪ N/A"


def _result(name: str, ok: bool | None, detail: str, fix: str = "") -> dict[str, Any]:
    return {"Test": name, "Status": _status(ok), "Detail": detail, "Fix / Notes": fix}


def _df(globals_dict: dict[str, Any], name: str) -> pd.DataFrame:
    obj = st.session_state.get(name)
    if isinstance(obj, pd.DataFrame):
        return obj.copy()
    obj = globals_dict.get(name)
    if isinstance(obj, pd.DataFrame):
        return obj.copy()
    return pd.DataFrame()


def _has_cols(df: pd.DataFrame, cols: list[str]) -> tuple[bool | None, str, list[str]]:
    if df.empty:
        return None, "No scan dataframe available. Run a scan first.", cols
    missing = [c for c in cols if c not in df.columns]
    if missing:
        return False, f"Missing columns: {', '.join(missing)}", missing
    return True, "All required columns present.", []


def _import_test(_: dict[str, Any], module_name: str) -> dict[str, Any]:
    try:
        importlib.import_module(module_name)
        return _result(f"Import {module_name.split('.')[-1]}", True, "Module imports successfully.")
    except Exception as exc:
        return _result(f"Import {module_name.split('.')[-1]}", False, f"{type(exc).__name__}: {exc}", "Fix syntax/import errors in the listed tab module.")


def _all_tab_imports(globals_dict: dict[str, Any]) -> list[dict[str, Any]]:
    return [_import_test(globals_dict, mod) for mod in TAB_MODULES.values()]


def _long_columns(globals_dict: dict[str, Any]) -> list[dict[str, Any]]:
    df = _df(globals_dict, "df_long")
    ok, detail, _ = _has_cols(df, REQUIRED_LONG_COLUMNS)
    return [_result("Long Setups required columns", ok, detail, "Run a fresh scan if this is N/A. If FAIL, check analysis_scan_core row output.")]


def _no_contradictory_next_day(globals_dict: dict[str, Any]) -> list[dict[str, Any]]:
    df = _df(globals_dict, "df_long")
    if df.empty:
        return [_result("No A+ vs WAIT contradiction", None, "No long scan dataframe available. Run a scan first.")]
    needed = ["Next-Day Rating", "Entry Quality"]
    missing = [c for c in needed if c not in df.columns]
    if missing:
        return [_result("No A+ vs WAIT contradiction", False, f"Missing columns: {missing}")]
    nd = df["Next-Day Rating"].astype(str).str.upper()
    eq = df["Entry Quality"].astype(str).str.upper()
    bad = df[nd.str.contains(r"A\+|BUY", regex=True, na=False) & eq.str.contains(r"WAIT|AVOID|SKIP", regex=True, na=False)]
    if bad.empty:
        return [_result("No A+ / BUY rating while WAIT/AVOID/SKIP", True, "No contradictions found in current scan.")]
    sample = ", ".join(bad.get("Ticker", pd.Series(dtype=str)).astype(str).head(8).tolist())
    return [_result("No A+ / BUY rating while WAIT/AVOID/SKIP", False, f"Contradictory rows: {len(bad)}. Sample: {sample}", "Ensure final Tradeable Buy gate overrides Next-Day Rating and Entry Quality together.")]


def _tradeable_buy_gate(globals_dict: dict[str, Any]) -> list[dict[str, Any]]:
    df = _df(globals_dict, "df_long")
    if df.empty:
        return [_result("Tradeable Buy gate sanity", None, "No long scan dataframe available. Run a scan first.")]
    needed = ["Tradeable Buy", "Entry Quality", "Quality Score", "Next-Day Score"]
    missing = [c for c in needed if c not in df.columns]
    if missing:
        return [_result("Tradeable Buy gate sanity", False, f"Missing columns: {missing}")]
    tb = df["Tradeable Buy"].astype(str).str.upper().str.contains("YES|TRUE|✅", regex=True, na=False)
    eq = df["Entry Quality"].astype(str).str.upper().str.contains("BUY", regex=False, na=False)
    q = pd.to_numeric(df["Quality Score"], errors="coerce").fillna(-999)
    nd = pd.to_numeric(df["Next-Day Score"], errors="coerce").fillna(-999)
    bad = df[tb & (~eq | (q < 9) | (nd < 8))]
    if bad.empty:
        return [_result("Tradeable Buy requires BUY + minimum scores", True, "No gate violations found in current scan.")]
    sample = ", ".join(bad.get("Ticker", pd.Series(dtype=str)).astype(str).head(8).tolist())
    return [_result("Tradeable Buy requires BUY + minimum scores", False, f"Gate violations: {len(bad)}. Sample: {sample}", "Check v13 accuracy gate thresholds in analysis_scan_core.")]


def _strategy_static(strategy: str) -> list[dict[str, Any]]:
    path = Path(__file__).resolve().parents[1] / "core_runtime" / "analysis_scan_core.py"
    txt = path.read_text(encoding="utf-8", errors="ignore")
    upper = strategy.upper()
    results = []
    results.append(_result(f"{strategy}: strategy branch exists", upper in txt, f"Looked for {upper!r} in analysis_scan_core.py", "Add/restore branch if FAIL."))
    if strategy == "Strict":
        terms = ["next_day_buy_ok", "quality_score", "risk_reward_ok", "resistance_clearance_ok"]
    elif strategy == "High Volume":
        terms = ["HIGH VOLUME", "hv_score", "Vol Ratio"]
    elif strategy == "Premarket Momentum":
        terms = ["PREMARKET MOMENTUM", "pm_zone", "PM Chg"]
    elif strategy == "Support Entry":
        terms = ["SUPPORT ENTRY", "support_zone", "Support Tier"]
    elif strategy == "High Conviction":
        terms = ["HIGH CONVICTION", "HC[", "_hc_tag"]
    elif strategy == "PSM Strategy":
        terms = ["PSM", "PSS Score", "PI Proxy"]
    elif strategy == "Discovery":
        terms = ["DISCOVERY", "discovery"]
    else:
        terms = ["BALANCED", "balanced"]
    missing = [t for t in terms if t not in txt]
    results.append(_result(f"{strategy}: key logic tokens", not missing, "Missing: " + ", ".join(missing) if missing else "Expected tokens present."))
    return results


def _event_predictor(globals_dict: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [_import_test(globals_dict, "swing_trader_app.tabs.event_predictor_tab")]
    path = Path(__file__).with_name("event_predictor_tab.py")
    txt = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
    rows.append(_result("Event Predictor cloud fallback present", "Cloud fallback" in txt or "cloud-safe" in txt or "fast_info" in txt, "Checks that Streamlit Cloud does not blank the tab when Yahoo info/news fails."))
    rows.append(_result("Event Predictor SEDG-style columns defined", all(c in txt for c in ["Squeeze Score", "Post-Event Score", "SEDG-Type"]), "Checks SEDG-style event/squeeze scoring labels."))
    df = st.session_state.get("event_predictor_df")
    if isinstance(df, pd.DataFrame) and not df.empty:
        ok, detail, _ = _has_cols(df, REQUIRED_EVENT_COLUMNS)
        rows.append(_result("Event Predictor current dataframe columns", ok, detail))
    else:
        rows.append(_result("Event Predictor current dataframe columns", None, "No Event Predictor dataframe in session. Run the Event Predictor tab first."))
    return rows


def _premarket(globals_dict: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [_import_test(globals_dict, "swing_trader_app.tabs.premarket_tab")]
    path = Path(__file__).with_name("premarket_tab.py")
    txt = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
    rows.append(_result("Premarket manual ticker input present", "Add tickers" in txt or "manual" in txt.lower(), "Useful for checking SEDG without hardcoded priority lists."))
    rows.append(_result("Premarket no hardcoded priority_pm_watch", "priority_pm_watch" not in txt, "Scanner should not rely on a hardcoded priority watchlist."))
    return rows


def _accuracy_lab(globals_dict: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [_import_test(globals_dict, "swing_trader_app.tabs.accuracy_lab_tab")]
    path = Path(__file__).with_name("accuracy_lab_tab.py")
    txt = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
    rows.append(_result("Accuracy target-before-stop logic", "target_before_stop" in txt or "hit_target_before_stop" in txt, "Should validate +target before -stop, not just fwd_ret > 0."))
    rows.append(_result("Accuracy Precision@Top style metrics", "Precision" in txt or "precision" in txt, "Prefer precision of top-ranked picks for 5–7 day target tests."))
    return rows


def _breakout(globals_dict: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [_import_test(globals_dict, "swing_trader_app.tabs.breakout_scanner_tab")]
    path = Path(__file__).with_name("breakout_scanner_tab.py")
    txt = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
    for term in ["Vol Ratio", "52W", "Breakout", "ATR"]:
        rows.append(_result(f"Breakout token: {term}", term in txt, f"Checks {term} logic/display token."))
    return rows


def _earnings(globals_dict: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [_import_test(globals_dict, "swing_trader_app.tabs.earnings_tab")]
    path = Path(__file__).with_name("earnings_tab.py")
    txt = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
    rows.append(_result("Earnings offset support", "offset" in txt.lower() or "Upcoming" in txt, "Confirms earnings window/offset controls exist."))
    rows.append(_result("SGX fallback wording/source", "SGInvestors" in txt or "Yahoo fallback" in txt or "fallback" in txt.lower(), "Helps explain SGX/HK sparse earnings."))
    return rows


def _operator(globals_dict: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [_import_test(globals_dict, "swing_trader_app.tabs.operator_activity_tab")]
    df = _df(globals_dict, "df_operator")
    if isinstance(df, pd.DataFrame) and not df.empty:
        cols = ["Ticker", "Op Score"]
        ok, detail, _ = _has_cols(df, cols)
        rows.append(_result("Operator current dataframe columns", ok, detail))
    else:
        rows.append(_result("Operator current dataframe columns", None, "No operator dataframe available. Run a scan first."))
    return rows



def _market_single_source(_: dict[str, Any]) -> list[dict[str, Any]]:
    checks = []
    files = {
        "Pre-Market": Path(__file__).with_name("premarket_tab.py"),
        "Breakout": Path(__file__).with_name("breakout_scanner_tab.py"),
        "Earnings": Path(__file__).with_name("earnings_tab.py"),
        "Event Predictor": Path(__file__).with_name("event_predictor_tab.py"),
    }
    for name, path in files.items():
        txt = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
        checks.append(_result(
            f"{name}: uses top market_selector",
            "market_selector" in txt,
            "Tab reads st.session_state['market_selector']." if "market_selector" in txt else "Tab does not read the top market selector.",
            "Make the top market radio the single source of truth."
        ))
    pm_txt = files["Pre-Market"].read_text(encoding="utf-8", errors="ignore")
    checks.append(_result(
        "Pre-Market: no hardcoded US-only title",
        "Pre-Market Scanner — US Stocks" not in pm_txt and "US only" not in pm_txt[:250],
        "Title is dynamic by selected market." if "Pre-Market Scanner — US Stocks" not in pm_txt else "Still contains hardcoded US title.",
        "Use selected market in the subheader."
    ))
    checks.append(_result(
        "Catalyst tabs: no inner market widgets",
        'st.radio("Market"' not in files["Earnings"].read_text(encoding="utf-8", errors="ignore")
        and 'st.radio("Market"' not in files["Event Predictor"].read_text(encoding="utf-8", errors="ignore")
        and 'key="bk_market"' not in files["Breakout"].read_text(encoding="utf-8", errors="ignore"),
        "Breakout/Earnings/Event Predictor follow the top selector only.",
        "Remove inner market controls that can drift from the top selector."
    ))
    return checks

def _scenario_results(globals_dict: dict[str, Any], scenario: str) -> list[dict[str, Any]]:
    if scenario == "All tabs import smoke test":
        return _all_tab_imports(globals_dict)
    if scenario == "Main scanner: required v16.5 columns":
        return _long_columns(globals_dict)
    if scenario == "Main scanner: no A+ vs WAIT contradiction":
        return _no_contradictory_next_day(globals_dict)
    if scenario == "Main scanner: Tradeable Buy gate":
        return _tradeable_buy_gate(globals_dict)
    if scenario.startswith("Strategy: "):
        return _strategy_static(scenario.replace("Strategy: ", "", 1))
    if scenario == "Event Predictor: SEDG-style / cloud fallback":
        return _event_predictor(globals_dict)
    if scenario == "Pre-Market: manual ticker / no priority list":
        return _premarket(globals_dict)
    if scenario == "Accuracy Lab: target-before-stop validation":
        return _accuracy_lab(globals_dict)
    if scenario == "Breakout Scanner: high volume / 52W / movers":
        return _breakout(globals_dict)
    if scenario == "Earnings: offset / fallback checks":
        return _earnings(globals_dict)
    if scenario == "Operator Activity: dataframe checks":
        return _operator(globals_dict)
    if scenario == "Market selector: all tabs follow top radio":
        return _market_single_source(globals_dict)
    return [_result("Unknown scenario", False, scenario)]


def render_test_cases(globals_dict: dict[str, Any]) -> None:
    st.subheader("🧪 Test Cases / QA")
    st.caption(
        "Run quick smoke tests for each tab and strategy scenario. These tests are read-only: "
        "they do not call Yahoo, do not change scan results, and do not alter strategy logic."
    )

    scenario_options = [
        "All tabs import smoke test",
        "Main scanner: required v16.5 columns",
        "Main scanner: no A+ vs WAIT contradiction",
        "Main scanner: Tradeable Buy gate",
        "Event Predictor: SEDG-style / cloud fallback",
        "Pre-Market: manual ticker / no priority list",
        "Accuracy Lab: target-before-stop validation",
        "Breakout Scanner: high volume / 52W / movers",
        "Earnings: offset / fallback checks",
        "Operator Activity: dataframe checks",
        "Market selector: all tabs follow top radio",
    ] + [f"Strategy: {s}" for s in STRATEGIES]

    scenario = st.selectbox(
        "Select test case / strategy scenario",
        scenario_options,
        index=0,
        help="Choose one scenario from the dropdown. Strategy tests verify the code path exists; dataframe tests use the latest scan in session.",
    )

    col_a, col_b, col_c = st.columns([1, 1, 3])
    with col_a:
        run_selected = st.button("▶ Run selected", type="primary", key="qa_run_selected")
    with col_b:
        run_all = st.button("▶ Run core set", key="qa_run_core")

    scenarios_to_run = [scenario]
    if run_all:
        scenarios_to_run = [
            "All tabs import smoke test",
            "Main scanner: required v16.5 columns",
            "Main scanner: no A+ vs WAIT contradiction",
            "Main scanner: Tradeable Buy gate",
            "Event Predictor: SEDG-style / cloud fallback",
            "Pre-Market: manual ticker / no priority list",
            "Accuracy Lab: target-before-stop validation",
            "Breakout Scanner: high volume / 52W / movers",
        ] + [f"Strategy: {s}" for s in STRATEGIES]

    if not (run_selected or run_all):
        st.info("Select a scenario and click **Run selected**, or run the core regression set.")
        with st.expander("What these tests cover"):
            st.markdown(
                """
- **Import smoke tests**: catches syntax errors like `invalid decimal literal` before deployment.
- **Main scanner column tests**: verifies v16/v16.5 accuracy columns still exist.
- **Tradeable Buy gate tests**: catches contradictions like `A+ NEXT-DAY BUY` while `Entry Quality = WAIT`.
- **Strategy tests**: checks every strategy dropdown mode has a code path.
- **Event Predictor tests**: checks SEDG-style squeeze/event labels and Streamlit Cloud fallback code.
- **Pre-Market tests**: checks manual ticker flow, dynamic selected-market title, and avoids hardcoded priority lists.
- **Market selector tests**: checks Pre-Market, Breakout, Earnings, and Event Predictor follow the top radio.
- **Accuracy Lab tests**: checks target-before-stop validation for the 5–7 day objective.
                """
            )
        return

    all_rows: list[dict[str, Any]] = []
    for sc in scenarios_to_run:
        rows = _scenario_results(globals_dict, sc)
        for r in rows:
            r["Scenario"] = sc
        all_rows.extend(rows)

    out = pd.DataFrame(all_rows)
    if not out.empty:
        out = out[["Scenario", "Test", "Status", "Detail", "Fix / Notes"]]
        st.dataframe(out, width="stretch", hide_index=True)
        pass_count = int(out["Status"].astype(str).str.contains("PASS", na=False).sum())
        fail_count = int(out["Status"].astype(str).str.contains("FAIL", na=False).sum())
        na_count = int(out["Status"].astype(str).str.contains("N/A", na=False).sum())
        c1, c2, c3 = st.columns(3)
        c1.metric("Pass", pass_count)
        c2.metric("Fail", fail_count)
        c3.metric("N/A", na_count)
        if fail_count:
            st.warning("One or more tests failed. Review the Fix / Notes column before deployment.")
        elif na_count:
            st.info("Some tests are N/A because no scan dataframe exists yet. Run a fresh scan to validate data-dependent checks.")
        else:
            st.success("Selected test set passed.")
