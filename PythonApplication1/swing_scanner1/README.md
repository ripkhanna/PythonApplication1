# Swing Scanner exact split v13.46

This build keeps the original working behavior but moves each Streamlit tab body into `swing_trader_app/tabs/*.py`.

Run:

```bash
pip install -r requirements.txt
streamlit run swing_trader_sector_wise_yfin_simple.py
```

The small launcher uses `runpy.run_path()` so Streamlit reruns execute like the original single-file app.


## v13.48 core split

Large helper/function blocks have been moved from `app_runtime.py` into `swing_trader_app/core_runtime/` and are loaded by `app_runtime.py` at startup. Tab files remain under `swing_trader_app/tabs/`.
