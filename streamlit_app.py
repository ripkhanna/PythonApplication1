from pathlib import Path
import runpy

if __name__ == "__main__":
    app_path = Path(__file__).resolve().parent / "PythonApplication1" / "swing_scanner1" / "main.py"
    runpy.run_path(str(app_path), run_name="__main__")
