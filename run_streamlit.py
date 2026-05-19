import os
import sys
import threading
import time
import webbrowser


def open_browser():
    time.sleep(2)  # wait for server to start
    webbrowser.open("http://localhost:8501")


def main():
    print("RUNNING STREAMLIT IN-PROCESS")

    # Force production mode
    os.environ["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"

    base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    app_path = os.path.join(base_dir, "app.py")

    if not os.path.exists(app_path):
        print("ERROR: app.py not found:", app_path)
        input("Press Enter to exit...")
        return

    # 🚀 START BROWSER THREAD BEFORE STREAMLIT
    threading.Thread(target=open_browser, daemon=True).start()

    import streamlit.web.cli as stcli

    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--server.port=8501",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
    ]

    # 🚀 THIS BLOCKS (EXPECTED)
    stcli.main()


if __name__ == "__main__":
    main()