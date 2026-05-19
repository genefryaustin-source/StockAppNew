import subprocess
import webbrowser
import time
import os
import sys

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.abspath(relative_path)

def main():
    port = 8501

    subprocess.Popen(
        [
            "streamlit",
            "run",
            resource_path("app.py"),
            "--server.port",
            str(port),
            "--server.headless",
            "true"
        ],
        shell=True
    )

    time.sleep(3)
    webbrowser.open(f"http://localhost:{port}")

    input("Press Enter to exit...")

if __name__ == "__main__":
    main()