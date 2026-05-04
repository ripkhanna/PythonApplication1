"""
Entry point for Streamlit Cloud deployment.
Runs the Swing Scanner application.
"""
import subprocess
import sys

# Run the main Swing Scanner application
if __name__ == "__main__":
    subprocess.run([
        sys.executable, 
        "-m", 
        "streamlit", 
        "run", 
        "PythonApplication1/swing_trader_sector_wise_yfin_simple.py"
    ])
