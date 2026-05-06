from __future__ import annotations

import runpy
import traceback
from pathlib import Path

import streamlit as st

try:
    runtime_path = Path(__file__).resolve().parent / "swing_trader_app" / "app_runtime.py"
    runpy.run_path(str(runtime_path), run_name="__main__")
except Exception as e:
    try:
        st.set_page_config(page_title="Swing Scanner Error", layout="wide")
    except Exception:
        pass
    st.error(f"App startup failed: {type(e).__name__}: {e}")
    st.code(traceback.format_exc())
