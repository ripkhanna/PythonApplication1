from __future__ import annotations

import faulthandler
import os
import runpy
import traceback
from pathlib import Path

for _name in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
):
    os.environ.setdefault(_name, "1")
os.environ.setdefault("STREAMLIT_SERVER_FILE_WATCHER_TYPE", "none")

try:
    faulthandler.enable(all_threads=True)
except Exception:
    pass

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
