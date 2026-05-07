# Swing Scanner v13.55

Modular Streamlit build for the Swing/Long Term Scanner.

## Latest changes in v13.55

- Updated Help tab to match the latest live-market swing trading behavior.
- Documents the new **Swing signal mode**: Strict / Balanced / Discovery.
- Documents improved Long, Short, Swing Picks, Trade Desk, and Stock Analysis criteria.
- Documents Cloud diagnostics and scan debug logging.
- Keeps the v13.52 practical swing criteria and v13.51 diagnostics hardening.

## Run

```bash
pip install -r requirements.txt
streamlit run main.py
```

The small launcher uses `runpy.run_path()` so Streamlit reruns execute close to the original single-file app.

## Structure

- `main.py` — small Streamlit launcher
- `swing_trader_app/app_runtime.py` — UI orchestration and sidebar
- `swing_trader_app/tabs/` — readable tab renderers
- `swing_trader_app/core_runtime/` — scanner, signal, cache, market-data, strategy, and trade-desk helpers
