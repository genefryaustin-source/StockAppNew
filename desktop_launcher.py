import subprocess
import sys
from pathlib import Path

def main():
    base = Path(__file__).resolve().parent
    app_path = base / "app.py"
    # Launch Streamlit
    cmd = [sys.executable, "-m", "streamlit", "run", str(app_path), "--server.headless=true"]
    subprocess.run(cmd, check=False)

if __name__ == "__main__":
    main()