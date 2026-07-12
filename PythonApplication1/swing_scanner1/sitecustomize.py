"""Startup guardrails for Streamlit Community Cloud.

Python imports sitecustomize automatically when it is available on sys.path.
Keep this file dependency-free: it must run before pandas/numpy/streamlit import.
"""

from __future__ import annotations

import faulthandler
import os


for _name in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
):
    os.environ.setdefault(_name, "1")

# The Cloud traceback showed the server starts and then segfaults.  Disabling
# file watching removes one native/background component from the running app.
os.environ.setdefault("STREAMLIT_SERVER_FILE_WATCHER_TYPE", "none")

try:
    faulthandler.enable(all_threads=True)
except Exception:
    pass
