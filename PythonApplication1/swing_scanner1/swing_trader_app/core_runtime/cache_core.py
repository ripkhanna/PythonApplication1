"""Extracted runtime section from app_runtime.py lines 252-418.
Loaded by app_runtime with exec(..., globals()) to preserve the original single-file behavior.
"""

# ─────────────────────────────────────────────────────────────────────────────
# CSV RESULT CACHE — load previous scan instantly; refresh on demand / interval
# ─────────────────────────────────────────────────────────────────────────────
# v13.31: Anchor the cache directory to the SCRIPT'S OWN location, not CWD.
# Path("scanner_cache") resolves relative to the working directory Streamlit
# was launched from — which is often different from where the .py file lives.
# That made cache files appear "missing" because users looked next to the
# script while Streamlit wrote them next to wherever they ran the command.
# Anchoring to __file__ guarantees files always land at <script_dir>/scanner_cache.
try:
    _SCRIPT_DIR = Path(__file__).resolve().parent
except NameError:
    _SCRIPT_DIR = Path.cwd()
SCAN_CACHE_DIR = _SCRIPT_DIR / "scanner_cache"
SCAN_CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# CENTRAL ERROR / DIAGNOSTICS LOGGING
# ─────────────────────────────────────────────────────────────────────────────
APP_ERROR_LOG_FILE = SCAN_CACHE_DIR / "app_error_log.jsonl"

def _trim_session_errors(max_items: int = 250) -> None:
    try:
        events = st.session_state.get("app_error_events", [])
        if len(events) > max_items:
            st.session_state["app_error_events"] = events[-max_items:]
    except Exception:
        pass

def _record_app_error(context: str, exc: Exception | None = None, message: str | None = None,
                      severity: str = "error", ticker: str | None = None, extra: dict | None = None) -> dict:
    """Record an app/scan error to session state and a JSONL file for Diagnostics.

    This must never raise. It is intentionally dependency-light so it can be
    called from scan code, tab renderers, cache functions, and Cloud fallback paths.
    """
    import traceback as _traceback
    record = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "severity": severity,
        "context": str(context),
        "ticker": ticker or "",
        "message": str(message if message is not None else (exc if exc is not None else "")),
        "type": type(exc).__name__ if exc is not None else "",
        "traceback": _traceback.format_exc() if exc is not None else "",
        "extra": extra or {},
    }
    try:
        events = st.session_state.setdefault("app_error_events", [])
        events.append(record)
        _trim_session_errors()
    except Exception:
        pass
    try:
        SCAN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with APP_ERROR_LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except Exception:
        pass
    return record

def _record_app_warning(context: str, message: str, ticker: str | None = None, extra: dict | None = None) -> dict:
    return _record_app_error(context=context, message=message, severity="warning", ticker=ticker, extra=extra)

def _record_scan_note(message: str, context: str = "scan", extra: dict | None = None) -> dict:
    return _record_app_error(context=context, message=message, severity="info", extra=extra)

def _read_app_error_log(limit: int = 200) -> list[dict]:
    try:
        if not APP_ERROR_LOG_FILE.exists():
            return []
        lines = APP_ERROR_LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()[-int(limit):]
        out = []
        for line in lines:
            try:
                out.append(json.loads(line))
            except Exception:
                out.append({"time":"", "severity":"error", "context":"log_parse", "message":line})
        return out
    except Exception:
        return []

def _clear_app_error_log() -> None:
    try:
        st.session_state["app_error_events"] = []
    except Exception:
        pass
    try:
        APP_ERROR_LOG_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def _market_cache_key(market: str) -> str:
    if "US" in market:
        return "us"
    if "SGX" in market:
        return "sgx"
    if "India" in market:
        return "india"
    return "market"


def _scan_cache_paths(market: str) -> dict:
    key = _market_cache_key(market)
    return {
        "long": SCAN_CACHE_DIR / f"{key}_long_setups.csv",
        "short": SCAN_CACHE_DIR / f"{key}_short_setups.csv",
        "operator": SCAN_CACHE_DIR / f"{key}_operator_activity.csv",
        "meta": SCAN_CACHE_DIR / f"{key}_scan_meta.json",
    }


def _read_csv_if_exists(path: Path) -> pd.DataFrame:
    try:
        if path.exists() and path.stat().st_size > 0:
            return pd.read_csv(path, keep_default_na=False)
    except Exception as e:
        try:
            _record_app_error("cache_read_csv", e, extra={"path": str(path)})
        except Exception:
            pass
    return pd.DataFrame()


def _save_scan_cache(market: str, df_long: pd.DataFrame, df_short: pd.DataFrame,
                     df_operator: pd.DataFrame, meta: dict):
    """Persist latest scan results so the next app start can load instantly.
    Returns the saved metadata so Diagnostics can show cache timing immediately.
    On failure stores both an error message AND the absolute path attempted
    so the user can see exactly where files should have been written.
    """
    paths = _scan_cache_paths(market)
    abs_dir = SCAN_CACHE_DIR.resolve()
    try:
        # Ensure the directory exists at write time (in case it was deleted
        # between import and now)
        SCAN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        df_long.to_csv(paths["long"], index=False)
        df_short.to_csv(paths["short"], index=False)
        df_operator.to_csv(paths["operator"], index=False)
        meta = dict(meta or {})
        meta.update({
            "market": market,
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "long_rows": int(len(df_long)),
            "short_rows": int(len(df_short)),
            "operator_rows": int(len(df_operator)),
            "abs_dir": str(abs_dir),
        })
        paths["meta"].write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
        # Record success info in session_state so the UI can show it
        st.session_state["scan_cache_last_save"] = {
            "ok":         True,
            "market":     market,
            "abs_dir":    str(abs_dir),
            "long_path":  str(paths["long"].resolve()),
            "short_path": str(paths["short"].resolve()),
            "operator_path": str(paths["operator"].resolve()),
            "meta_path":  str(paths["meta"].resolve()),
            "saved_at":   meta["saved_at"],
            "long_rows":  meta["long_rows"],
            "short_rows": meta["short_rows"],
        }
        # Clear any prior warning
        st.session_state.pop("scan_cache_warning", None)
        return meta
    except Exception as e:
        st.session_state["scan_cache_warning"] = (
            f"CSV cache save failed: {type(e).__name__}: {e}\n"
            f"Attempted directory: {abs_dir}"
        )
        try:
            _record_app_error("scan_cache_save", e, extra={"market": market, "abs_dir": str(abs_dir)})
        except Exception:
            pass
        st.session_state["scan_cache_last_save"] = {
            "ok":      False,
            "market":  market,
            "abs_dir": str(abs_dir),
            "error":   f"{type(e).__name__}: {e}",
        }
        return None


def _load_scan_cache(market: str):
    """Load the latest cached CSV scan for the selected market, if available."""
    paths = _scan_cache_paths(market)
    try:
        if not paths["meta"].exists():
            return None
        meta = json.loads(paths["meta"].read_text(encoding="utf-8"))
        return {
            "df_long": _read_csv_if_exists(paths["long"]),
            "df_short": _read_csv_if_exists(paths["short"]),
            "df_operator": _read_csv_if_exists(paths["operator"]),
            "meta": meta,
        }
    except Exception as e:
        st.session_state["scan_cache_warning"] = f"CSV cache load failed: {type(e).__name__}: {e}"
        try:
            _record_app_error("scan_cache_load", e, extra={"market": market, "paths": {k: str(v) for k, v in paths.items()}})
        except Exception:
            pass
        return None


def _cache_age_minutes(meta: dict):
    try:
        saved = datetime.fromisoformat(str(meta.get("saved_at", "")))
        return max(0.0, (datetime.now() - saved).total_seconds() / 60.0)
    except Exception:
        return None


def _cache_timing_info(meta: dict, refresh_minutes: int = 0) -> dict:
    """Return human-readable cache timing status for Diagnostics."""
    info = {
        "saved_at_raw": "",
        "saved_at": "No cache yet",
        "age_minutes": None,
        "age_text": "–",
        "refresh_interval": "Off",
        "next_refresh_at": "Auto refresh off",
        "next_refresh_in": "Auto refresh off",
        "is_due": False,
    }
    try:
        if not meta:
            return info
        saved_raw = str(meta.get("saved_at", ""))
        saved = datetime.fromisoformat(saved_raw)
        now = datetime.now()
        age = max(0.0, (now - saved).total_seconds() / 60.0)
        info["saved_at_raw"] = saved_raw
        info["saved_at"] = saved.strftime("%Y-%m-%d %H:%M:%S")
        info["age_minutes"] = age
        info["age_text"] = f"{age:.1f} min old" if age < 60 else f"{age/60:.1f} hr old"
        if refresh_minutes and int(refresh_minutes) > 0:
            refresh_minutes = int(refresh_minutes)
            next_at = saved + timedelta(minutes=refresh_minutes)
            remaining = (next_at - now).total_seconds() / 60.0
            info["refresh_interval"] = f"Every {refresh_minutes} min"
            info["next_refresh_at"] = next_at.strftime("%Y-%m-%d %H:%M:%S")
            if remaining <= 0:
                info["next_refresh_in"] = "Due now / on next reload"
                info["is_due"] = True
            else:
                info["next_refresh_in"] = f"in {remaining:.1f} min"
        return info
    except Exception as e:
        info["saved_at"] = f"Could not parse cache time: {e}"
        return info

