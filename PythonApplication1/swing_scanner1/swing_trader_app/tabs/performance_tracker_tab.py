"""Performance Tracker tab.

Records scanner selections and updates forward returns so the scanner can be
judged by actual outcomes instead of displayed probability alone.
"""

from __future__ import annotations

import hashlib
import sqlite3
from contextlib import closing
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st


TRACKER_COLUMNS = [
    "Pick ID", "Market", "Selection Date", "Captured At", "Scan Time",
    "Ticker", "Source", "Tier", "Score", "Why",
    "Entry Price", "Trigger", "Stop", "Action", "Entry Quality",
    "Tradeable Buy", "Today %", "Vol Ratio", "ATR%", "Rise Prob",
    "Quality Score", "Next-Day Score", "RR Est",
    "Days Checked", "Max Gain 1D %", "Max Gain 3D %", "Max Gain 5D %",
    "Max Gain 7D %", "Max Drawdown 7D %", "Close 7D %",
    "Hit +3%", "Hit +5%", "Hit +7%", "Hit +10%",
    "Stop Hit", "Stop First", "Status", "Last Outcome Update",
]


def _bind_runtime(ctx: dict) -> None:
    globals().update(ctx)


TRACKER_TABLE = "performance_tracker"


def _legacy_tracker_path() -> Path:
    cache_dir = globals().get("SCAN_CACHE_DIR")
    if cache_dir:
        out = Path(cache_dir)
    else:
        out = Path(__file__).resolve().parents[1] / "scanner_cache"
    out.mkdir(parents=True, exist_ok=True)
    return out / "performance_tracker.csv"


def _tracker_db_path() -> Path:
    configured_dir = globals().get("PERFORMANCE_DB_DIR")
    if configured_dir:
        out = Path(configured_dir)
    else:
        # Keep durable user records outside scanner_cache so cache deletion
        # cannot remove captured picks or their later outcome updates.
        out = Path(__file__).resolve().parents[2] / "user_data"
    out.mkdir(parents=True, exist_ok=True)
    return out / "performance_tracker.sqlite3"


def _quoted_identifier(value: str) -> str:
    return '"' + str(value).replace('"', '""') + '"'


def _normalise_tracker_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    for col in TRACKER_COLUMNS:
        if col not in out.columns:
            out[col] = ""
    out = out[TRACKER_COLUMNS].copy()
    return out.where(pd.notna(out), "")


def _connect_tracker_db() -> sqlite3.Connection:
    conn = sqlite3.connect(_tracker_db_path(), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def _ensure_tracker_db() -> None:
    column_defs = ", ".join(
        f"{_quoted_identifier(col)} TEXT" for col in TRACKER_COLUMNS
    )
    with closing(_connect_tracker_db()) as conn, conn:
        conn.execute(
            f"CREATE TABLE IF NOT EXISTS {_quoted_identifier(TRACKER_TABLE)} "
            f"({column_defs}, PRIMARY KEY ({_quoted_identifier('Pick ID')}))"
        )
        existing = {
            str(row[1])
            for row in conn.execute(
                f"PRAGMA table_info({_quoted_identifier(TRACKER_TABLE)})"
            ).fetchall()
        }
        for col in TRACKER_COLUMNS:
            if col not in existing:
                conn.execute(
                    f"ALTER TABLE {_quoted_identifier(TRACKER_TABLE)} "
                    f"ADD COLUMN {_quoted_identifier(col)} TEXT"
                )
        conn.execute(
            f"CREATE INDEX IF NOT EXISTS idx_perf_tracker_date "
            f"ON {_quoted_identifier(TRACKER_TABLE)} "
            f"({_quoted_identifier('Selection Date')}, {_quoted_identifier('Ticker')})"
        )


def _upsert_tracker_rows(df: pd.DataFrame) -> None:
    out = _normalise_tracker_frame(df)
    if out.empty:
        return
    columns_sql = ", ".join(_quoted_identifier(col) for col in TRACKER_COLUMNS)
    placeholders = ", ".join(["?"] * len(TRACKER_COLUMNS))
    sql = (
        f"INSERT OR REPLACE INTO {_quoted_identifier(TRACKER_TABLE)} "
        f"({columns_sql}) VALUES ({placeholders})"
    )
    rows = [
        tuple("" if pd.isna(value) else str(value) for value in row)
        for row in out.itertuples(index=False, name=None)
    ]
    with closing(_connect_tracker_db()) as conn, conn:
        conn.executemany(sql, rows)
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")


def _migrate_legacy_tracker_csv() -> int:
    """Import the old cache CSV once when the durable database is empty."""
    legacy = _legacy_tracker_path()
    if not legacy.exists() or legacy.stat().st_size <= 0:
        return 0
    with closing(_connect_tracker_db()) as conn:
        count = int(
            conn.execute(
                f"SELECT COUNT(*) FROM {_quoted_identifier(TRACKER_TABLE)}"
            ).fetchone()[0]
        )
    if count:
        return 0
    try:
        old = pd.read_csv(legacy, keep_default_na=False)
    except Exception:
        return 0
    old = _normalise_tracker_frame(old)
    _upsert_tracker_rows(old)
    return len(old)


def _market_key(market: str) -> str:
    m = str(market or "").upper()
    if "HK" in m or "HONG" in m:
        return "hk"
    if "INDIA" in m or "NS" in m:
        return "india"
    if "SGX" in m or "SG" in m:
        return "sgx"
    if "US" in m:
        return "us"
    return "market"


def _current_market() -> str:
    return str(
        st.session_state.get(
            "market_selector",
            globals().get("last_market", globals().get("market_sel", "US")),
        )
    )


def _num_value(value, default: float = 0.0) -> float:
    try:
        text = str(value)
        text = (
            text.replace("%", "")
            .replace("+", "")
            .replace("$", "")
            .replace("HK$", "")
            .replace("S$", "")
            .replace("x", "")
            .replace(",", "")
            .strip()
        )
        if text.lower() in {"", "nan", "none", "-", "–"}:
            return float(default)
        if text.startswith("1:"):
            text = text.split("1:", 1)[1]
        val = pd.to_numeric(text, errors="coerce")
        return float(default) if pd.isna(val) else float(val)
    except Exception:
        return float(default)


def _num_series(df: pd.DataFrame, col: str, default: float = 0.0) -> pd.Series:
    if col not in df.columns:
        return pd.Series([default] * len(df), index=df.index, dtype="float64")
    return pd.to_numeric(
        df[col].astype(str)
        .str.replace("%", "", regex=False)
        .str.replace("+", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.replace("HK$", "", regex=False)
        .str.replace("S$", "", regex=False)
        .str.replace("x", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.extract(r"(-?\d+(?:\.\d+)?)")[0],
        errors="coerce",
    ).fillna(default)


def _text_series(df: pd.DataFrame, col: str, default: str = "") -> pd.Series:
    if col not in df.columns:
        return pd.Series([default] * len(df), index=df.index)
    return df[col].astype(str).fillna(default)


def _parse_date(value) -> pd.Timestamp | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        raw = str(value).replace("Latest bar:", "").replace("SGT", "").replace("ET", "").strip()
        ts = pd.to_datetime(raw, errors="coerce")
        if pd.isna(ts):
            return None
        if getattr(ts, "tzinfo", None) is not None:
            ts = ts.tz_convert(None)
        return pd.Timestamp(ts).normalize()
    except Exception:
        return None


def _scan_date_from(df: pd.DataFrame) -> str:
    meta = st.session_state.get("scan_cache_meta", {}) or {}
    for value in (
        meta.get("latest_bar_time"),
        meta.get("saved_at"),
        globals().get("_latest_bar_for_cache", ""),
    ):
        ts = _parse_date(value)
        if ts is not None:
            return ts.date().isoformat()
    if "Last Bar" in df.columns:
        vals = pd.to_datetime(df["Last Bar"], errors="coerce").dropna()
        if not vals.empty:
            return vals.max().date().isoformat()
    return pd.Timestamp.now().date().isoformat()


def _scan_time() -> str:
    meta = st.session_state.get("scan_cache_meta", {}) or {}
    return str(meta.get("saved_at") or pd.Timestamp.now().isoformat(timespec="seconds"))


def _source_frame() -> pd.DataFrame:
    sources = [
        st.session_state.get("df_long_master", pd.DataFrame()),
        st.session_state.get("df_long", pd.DataFrame()),
        globals().get("df_long_master", pd.DataFrame()),
        globals().get("df_long", pd.DataFrame()),
    ]
    for df in sources:
        if isinstance(df, pd.DataFrame) and not df.empty:
            out = df.copy()
            if "Ticker" not in out.columns:
                out.insert(0, "Ticker", out.index.astype(str))
            out["Ticker"] = out["Ticker"].astype(str).str.upper().str.strip()
            return out.drop_duplicates("Ticker").reset_index(drop=True)

    cache_dir = Path(globals().get("SCAN_CACHE_DIR", Path(__file__).resolve().parents[1] / "scanner_cache"))
    path = cache_dir / f"{_market_key(_current_market())}_long_setups.csv"
    if path.exists() and path.stat().st_size > 0:
        try:
            out = pd.read_csv(path, keep_default_na=False)
            if "Ticker" not in out.columns:
                out.insert(0, "Ticker", out.index.astype(str))
            out["Ticker"] = out["Ticker"].astype(str).str.upper().str.strip()
            return out.drop_duplicates("Ticker").reset_index(drop=True)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def _load_tracker() -> pd.DataFrame:
    try:
        _ensure_tracker_db()
        _migrate_legacy_tracker_csv()
        columns_sql = ", ".join(_quoted_identifier(col) for col in TRACKER_COLUMNS)
        with closing(_connect_tracker_db()) as conn:
            df = pd.read_sql_query(
                f"SELECT {columns_sql} "
                f"FROM {_quoted_identifier(TRACKER_TABLE)} "
                f"ORDER BY {_quoted_identifier('Selection Date')} DESC, "
                f"{_quoted_identifier('Captured At')} DESC",
                conn,
            )
    except Exception:
        df = pd.DataFrame(columns=TRACKER_COLUMNS)
    return _normalise_tracker_frame(df)


def _save_tracker(df: pd.DataFrame) -> None:
    _ensure_tracker_db()
    _upsert_tracker_rows(df)


def _pick_id(market: str, selection_date: str, ticker: str, source: str) -> str:
    raw = f"{market}|{selection_date}|{ticker}|{source}".upper()
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _row_to_pick(row: pd.Series, market: str, selection_date: str, scan_time: str,
                 source: str, tier_col: str, score_col: str, why_col: str,
                 trigger_col: str = "", stop_col: str = "") -> dict:
    ticker = str(row.get("Ticker", "")).upper().strip()
    price = _num_value(row.get("Price", 0))
    trigger = _num_value(row.get(trigger_col, 0)) if trigger_col else 0.0
    stop = _num_value(row.get(stop_col, 0)) if stop_col else 0.0
    if trigger <= 0 and price > 0:
        trigger = round(price * 1.006, 2)
    if (stop <= 0 or (price > 0 and stop >= price)) and price > 0:
        stop = round(price * 0.94, 2)
    tier = str(row.get(tier_col, "") or "")
    return {
        "Pick ID": _pick_id(market, selection_date, ticker, source),
        "Market": market,
        "Selection Date": selection_date,
        "Captured At": pd.Timestamp.now().isoformat(timespec="seconds"),
        "Scan Time": scan_time,
        "Ticker": ticker,
        "Source": source,
        "Tier": tier,
        "Score": _num_value(row.get(score_col, 0)),
        "Why": str(row.get(why_col, "") or "")[:500],
        "Entry Price": price,
        "Trigger": trigger,
        "Stop": stop,
        "Action": str(row.get("Action", "") or ""),
        "Entry Quality": str(row.get("Entry Quality", "") or ""),
        "Tradeable Buy": str(row.get("Tradeable Buy", "") or ""),
        "Today %": str(row.get("Today %", "") or ""),
        "Vol Ratio": _num_value(row.get("Vol Ratio", 0)),
        "ATR%": str(row.get("ATR%", "") or ""),
        "Rise Prob": str(row.get("Rise Prob", "") or ""),
        "Quality Score": _num_value(row.get("Quality Score", 0)),
        "Next-Day Score": _num_value(row.get("Next-Day Score", 0)),
        "RR Est": str(row.get("RR Est", "") or ""),
        "Days Checked": 0,
        "Max Gain 1D %": "",
        "Max Gain 3D %": "",
        "Max Gain 5D %": "",
        "Max Gain 7D %": "",
        "Max Drawdown 7D %": "",
        "Close 7D %": "",
        "Hit +3%": "",
        "Hit +5%": "",
        "Hit +7%": "",
        "Hit +10%": "",
        "Stop Hit": "",
        "Stop First": "",
        "Status": "Open",
        "Last Outcome Update": "",
    }


def _candidate_rows(src: pd.DataFrame, top_n: int, sources: list[str], include_wait_reset: bool) -> pd.DataFrame:
    if src.empty:
        return pd.DataFrame(columns=TRACKER_COLUMNS)

    market = _current_market()
    selection_date = _scan_date_from(src)
    scan_time = _scan_time()
    rows = []

    if "Best 7-10%" in sources:
        try:
            from swing_trader_app.tabs.best_710_tab import _classify as _best_classify

            best = _best_classify(src, min_score=50, max_today=3.5, strict=True)
            best = best[~best["Best 710 Tier"].astype(str).str.startswith("Reject", na=False)].head(top_n)
            for _, row in best.iterrows():
                rows.append(_row_to_pick(
                    row, market, selection_date, scan_time, "Best 7-10%",
                    "Best 710 Tier", "Best 710 Score", "Best 710 Why",
                    "Trigger Above", "Invalid Below",
                ))
        except Exception:
            pass

    if "Next-Day 5-10%" in sources:
        try:
            from swing_trader_app.tabs.pre_movers_tab import _next_day_510, _rank

            nd = _next_day_510(_rank(src)).head(top_n)
            for _, row in nd.iterrows():
                rows.append(_row_to_pick(
                    row, market, selection_date, scan_time, "Next-Day 5-10%",
                    "Next-Day 5-10 Tier", "Next-Day 5-10 Score", "Next-Day 5-10 Why",
                    "Next-Day Trigger", "Next-Day Invalid",
                ))
        except Exception:
            pass

    if "Long Buy" in sources:
        action = _text_series(src, "Action").str.upper()
        entry = _text_series(src, "Entry Quality").str.upper()
        tradeable = _text_series(src, "Tradeable Buy").str.upper().eq("YES")
        score = np.maximum(_num_series(src, "Quality Score", 0), _num_series(src, "Next-Day Score", 0))
        long_buy = src[
            tradeable
            | entry.str.contains("BUY|DISCOVERY|NEAR-MISS", regex=True, na=False)
            | action.str.contains("STRONG BUY|TOP BUY|ELITE", regex=True, na=False)
        ].copy()
        if not long_buy.empty:
            long_buy["_tracker_score"] = score.loc[long_buy.index]
            long_buy = long_buy.sort_values("_tracker_score", ascending=False).head(top_n)
            for _, row in long_buy.iterrows():
                rows.append(_row_to_pick(
                    row, market, selection_date, scan_time, "Long Buy",
                    "Entry Quality", "_tracker_score", "Signals",
                    "", "Best Stop",
                ))

    if "Stage 2 Qualified" in sources:
        action = _text_series(src, "Action").str.upper()
        quality_gate = _text_series(src, "Swing Quality Gate").str.upper().eq("PASS")
        stage2 = src[
            quality_gate
            & action.str.contains("QUALIFIED.*STAGE 2", regex=True, na=False)
        ].copy()
        if not stage2.empty:
            stage2["_tracker_score"] = _num_series(stage2, "Stage 2 Rank Score", 0)
            stage2 = stage2.sort_values("_tracker_score", ascending=False).head(top_n)
            for _, row in stage2.iterrows():
                pick = _row_to_pick(
                    row, market, selection_date, scan_time, "Stage 2 Qualified",
                    "Stage 2 Phase", "_tracker_score", "Swing Quality Why",
                    "Stage 2 Entry", "Stage 2 Hard Stop",
                )
                # Stage 2 is not entered at the current watchlist price. Track
                # outcomes only from the future breakout trigger.
                pick["Entry Price"] = pick["Trigger"]
                rows.append(pick)

    if "Momentum Runner" in sources:
        try:
            from swing_trader_app.tabs.momentum_runner_tab import _classify as _runner_classify

            runner = _runner_classify(src, min_score=35, show_chase=True)
            if not include_wait_reset:
                runner = runner[~runner["Runner Tier"].eq("C - Hot Runner / Wait Reset")]
            runner = runner.head(top_n)
            for _, row in runner.iterrows():
                rows.append(_row_to_pick(
                    row, market, selection_date, scan_time, "Momentum Runner",
                    "Runner Tier", "Runner Score", "Runner Why",
                    "Runner Trigger", "Runner Invalid",
                ))
        except Exception:
            pass

    out = pd.DataFrame(rows)
    if out.empty:
        return pd.DataFrame(columns=TRACKER_COLUMNS)
    return out[TRACKER_COLUMNS].drop_duplicates("Pick ID").reset_index(drop=True)


def _append_candidates(existing: pd.DataFrame, picks: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    if picks.empty:
        return existing, 0
    old_ids = set(existing.get("Pick ID", pd.Series(dtype=str)).astype(str))
    add = picks[~picks["Pick ID"].astype(str).isin(old_ids)].copy()
    if add.empty:
        return existing, 0
    out = pd.concat([existing, add], ignore_index=True)
    out = out.drop_duplicates("Pick ID", keep="last")
    return out[TRACKER_COLUMNS], len(add)


def _history_for_ticker(ticker: str, start_date: pd.Timestamp) -> pd.DataFrame:
    yf_mod = globals().get("yf")
    if yf_mod is None:
        import yfinance as yf_mod  # type: ignore

    start = (start_date - pd.Timedelta(days=7)).date().isoformat()
    end = (pd.Timestamp.now() + pd.Timedelta(days=2)).date().isoformat()
    raw = yf_mod.download(ticker, start=start, end=end, interval="1d", auto_adjust=True, progress=False, threads=False)
    if raw is None or raw.empty:
        return pd.DataFrame()
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in raw.columns]
    out = raw[cols].copy()
    out.index = pd.to_datetime(out.index).tz_localize(None).normalize()
    return out.dropna(subset=["High", "Low", "Close"], how="any")


def _first_hit_day(bars: pd.DataFrame, entry: float, threshold_pct: float) -> int | None:
    target = entry * (1.0 + threshold_pct / 100.0)
    for i, (_, bar) in enumerate(bars.iterrows(), start=1):
        if float(bar["High"]) >= target:
            return i
    return None


def _first_stop_day(bars: pd.DataFrame, stop: float) -> int | None:
    if stop <= 0:
        return None
    for i, (_, bar) in enumerate(bars.iterrows(), start=1):
        if float(bar["Low"]) <= stop:
            return i
    return None


def _max_gain(bars: pd.DataFrame, entry: float, days: int) -> float:
    view = bars.head(days)
    if view.empty or entry <= 0:
        return np.nan
    return (float(view["High"].max()) / entry - 1.0) * 100.0


def _max_drawdown(bars: pd.DataFrame, entry: float, days: int) -> float:
    view = bars.head(days)
    if view.empty or entry <= 0:
        return np.nan
    return (float(view["Low"].min()) / entry - 1.0) * 100.0


def _close_return(bars: pd.DataFrame, entry: float, days: int) -> float:
    view = bars.head(days)
    if view.empty or entry <= 0:
        return np.nan
    return (float(view["Close"].iloc[-1]) / entry - 1.0) * 100.0


def _fmt_pct(value) -> str:
    try:
        if pd.isna(value):
            return ""
        return f"{float(value):+.2f}%"
    except Exception:
        return ""


def _yes_no(value: bool | None) -> str:
    if value is None:
        return ""
    return "YES" if value else "NO"


def _update_outcomes(log: pd.DataFrame, max_tickers: int = 80) -> tuple[pd.DataFrame, int, list[str]]:
    if log.empty:
        return log, 0, []

    out = log.copy()
    out["Ticker"] = out["Ticker"].astype(str).str.upper().str.strip()
    tickers = out["Ticker"].dropna().replace("", np.nan).dropna().unique().tolist()[:max_tickers]
    errors = []
    updated = 0

    history = {}
    for ticker in tickers:
        dates = pd.to_datetime(out.loc[out["Ticker"].eq(ticker), "Selection Date"], errors="coerce").dropna()
        if dates.empty:
            continue
        try:
            hist = _history_for_ticker(ticker, dates.min())
            if not hist.empty:
                history[ticker] = hist
        except Exception as exc:
            errors.append(f"{ticker}: {type(exc).__name__}: {exc}")

    for i, row in out.iterrows():
        ticker = str(row.get("Ticker", "")).upper().strip()
        hist = history.get(ticker)
        selected = _parse_date(row.get("Selection Date", ""))
        entry = _num_value(row.get("Entry Price", 0))
        stop = _num_value(row.get("Stop", 0))
        if hist is None or hist.empty or selected is None or entry <= 0:
            continue

        after = hist[hist.index > selected].copy()
        if after.empty:
            out.at[i, "Status"] = "Waiting"
            continue

        if str(row.get("Source", "")) == "Stage 2 Qualified":
            trigger = _num_value(row.get("Trigger", 0))
            trigger_hits = after.index[after["High"] >= trigger] if trigger > 0 else []
            if len(trigger_hits) == 0:
                out.at[i, "Status"] = "Waiting Trigger"
                out.at[i, "Days Checked"] = int(min(len(after), 7))
                out.at[i, "Last Outcome Update"] = pd.Timestamp.now().isoformat(timespec="seconds")
                updated += 1
                continue
            after = after[after.index >= trigger_hits[0]].copy()
            entry = trigger

        horizon = after.head(7)
        days_checked = int(len(horizon))
        out.at[i, "Days Checked"] = days_checked
        for days in (1, 3, 5, 7):
            out.at[i, f"Max Gain {days}D %"] = _fmt_pct(_max_gain(after, entry, days))
        out.at[i, "Max Drawdown 7D %"] = _fmt_pct(_max_drawdown(after, entry, 7))
        out.at[i, "Close 7D %"] = _fmt_pct(_close_return(after, entry, 7))

        target_days = {pct: _first_hit_day(horizon, entry, pct) for pct in (3, 5, 7, 10)}
        stop_day = _first_stop_day(horizon, stop)
        out.at[i, "Hit +3%"] = _yes_no(target_days[3] is not None)
        out.at[i, "Hit +5%"] = _yes_no(target_days[5] is not None)
        out.at[i, "Hit +7%"] = _yes_no(target_days[7] is not None)
        out.at[i, "Hit +10%"] = _yes_no(target_days[10] is not None)
        out.at[i, "Stop Hit"] = _yes_no(stop_day is not None)
        out.at[i, "Stop First"] = _yes_no(stop_day is not None and (target_days[5] is None or stop_day <= target_days[5]))

        if target_days[10] is not None:
            status = "Hit +10%"
        elif target_days[7] is not None:
            status = "Hit +7%"
        elif target_days[5] is not None:
            status = "Hit +5%"
        elif stop_day is not None and (target_days[5] is None or stop_day <= target_days[5]):
            status = "Stop First"
        elif days_checked >= 7:
            status = "No +5% in 7D"
        else:
            status = "Waiting"
        out.at[i, "Status"] = status
        out.at[i, "Last Outcome Update"] = pd.Timestamp.now().isoformat(timespec="seconds")
        updated += 1

    return out[TRACKER_COLUMNS], updated, errors


def _rate(series: pd.Series) -> float:
    vals = series.astype(str).str.upper()
    known = vals.isin(["YES", "NO"])
    if not known.any():
        return 0.0
    return float((vals[known] == "YES").mean() * 100.0)


def _pct_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str).str.replace("%", "", regex=False).str.replace("+", "", regex=False),
        errors="coerce",
    )


def _summary_by_source(log: pd.DataFrame) -> pd.DataFrame:
    if log.empty:
        return pd.DataFrame()
    matured = log[pd.to_numeric(log["Days Checked"], errors="coerce").fillna(0) >= 3].copy()
    if matured.empty:
        return pd.DataFrame()
    rows = []
    for (source, tier), grp in matured.groupby(["Source", "Tier"], dropna=False):
        rows.append({
            "Source": source,
            "Tier": tier,
            "Picks": len(grp),
            "+3% Hit": f"{_rate(grp['Hit +3%']):.1f}%",
            "+5% Hit": f"{_rate(grp['Hit +5%']):.1f}%",
            "+7% Hit": f"{_rate(grp['Hit +7%']):.1f}%",
            "+10% Hit": f"{_rate(grp['Hit +10%']):.1f}%",
            "Stop First": f"{_rate(grp['Stop First']):.1f}%",
            "Avg Max 7D": _fmt_pct(_pct_num(grp["Max Gain 7D %"]).mean()),
            "Avg Drawdown": _fmt_pct(_pct_num(grp["Max Drawdown 7D %"]).mean()),
        })
    return pd.DataFrame(rows).sort_values(["+5% Hit", "Picks"], ascending=[False, False])


def render_performance_tracker(ctx: dict) -> None:
    _bind_runtime(ctx)

    st.markdown("## Performance Tracker")
    st.caption("Records scanner picks, then measures actual 1D/3D/5D/7D forward performance.")

    src = _source_frame()
    log = _load_tracker()
    path = _tracker_db_path()

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        source_choices = st.multiselect(
            "Capture from",
            ["Best 7-10%", "Next-Day 5-10%", "Long Buy", "Stage 2 Qualified", "Momentum Runner"],
            default=["Best 7-10%", "Next-Day 5-10%", "Long Buy", "Stage 2 Qualified"],
            key="perf_sources",
        )
    with c2:
        top_n = st.slider("Top N/source", 3, 50, 15, key="perf_top_n")
    with c3:
        include_wait_reset = st.checkbox("Include hot wait-reset", value=False, key="perf_include_wait_reset")

    b1, b2 = st.columns(2)
    with b1:
        if st.button("Capture Current Candidates", type="primary", key="perf_capture"):
            picks = _candidate_rows(src, top_n, source_choices, include_wait_reset)
            log, added = _append_candidates(log, picks)
            _save_tracker(log)
            st.success(f"Captured {added} new picks." if added else "No new picks to capture.")
    with b2:
        if st.button("Update Outcomes", key="perf_update"):
            with st.spinner("Updating outcomes from Yahoo daily bars..."):
                log, updated, errors = _update_outcomes(log)
                _save_tracker(log)
            if updated:
                st.success(f"Updated {updated} tracked picks.")
            else:
                st.info("No rows updated yet. There may be no later daily bars.")
            if errors:
                with st.expander("Outcome update warnings", expanded=False):
                    st.code("\n".join(errors[:50]))

    st.caption(
        f"Permanent tracker database: `{path}` · Stored outside scanner_cache, "
        "so clearing scan cache does not remove picks or outcomes."
    )

    if log.empty:
        st.info("No tracked picks yet. Run a scan, then click Capture Current Candidates.")
        return

    days_checked = pd.to_numeric(log["Days Checked"], errors="coerce").fillna(0)
    matured = log[days_checked >= 3].copy()
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Tracked Picks", len(log))
    m2.metric("Checked >=3D", len(matured))
    m3.metric("+5% Hit", f"{_rate(matured['Hit +5%']) if not matured.empty else 0:.1f}%")
    m4.metric("+7% Hit", f"{_rate(matured['Hit +7%']) if not matured.empty else 0:.1f}%")
    m5.metric("Stop First", f"{_rate(matured['Stop First']) if not matured.empty else 0:.1f}%")

    summary = _summary_by_source(log)
    st.markdown("### What Is Working")
    if summary.empty:
        st.info("Capture picks and update outcomes after a few trading days to see hit rates by tab/tier.")
    else:
        st.dataframe(summary, width="stretch", hide_index=True, key="perf_summary")

    show_cols = [
        "Selection Date", "Ticker", "Market", "Source", "Tier", "Score",
        "Entry Price", "Trigger", "Stop", "Days Checked", "Max Gain 1D %",
        "Max Gain 3D %", "Max Gain 5D %", "Max Gain 7D %",
        "Max Drawdown 7D %", "Hit +5%", "Hit +7%", "Hit +10%",
        "Stop First", "Status", "Why",
    ]
    show_cols = [c for c in show_cols if c in log.columns]

    open_rows = log[~log["Status"].astype(str).isin(["Hit +10%", "Hit +7%", "Hit +5%", "Stop First", "No +5% in 7D"])].copy()
    with st.expander(f"Open / Waiting Picks ({len(open_rows)})", expanded=True):
        st.dataframe(open_rows[show_cols].sort_values(["Selection Date", "Source"], ascending=[False, True]), width="stretch", hide_index=True, key="perf_open")

    with st.expander(f"All Tracked Picks ({len(log)})", expanded=False):
        st.dataframe(log[show_cols].sort_values(["Selection Date", "Source"], ascending=[False, True]), width="stretch", hide_index=True, key="perf_all")

    csv_data = log.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download tracker CSV",
        data=csv_data,
        file_name="performance_tracker.csv",
        mime="text/csv",
        key="perf_download",
    )
