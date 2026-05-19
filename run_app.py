def main():
    import sys
    import os
    import threading
    import time
    import webbrowser

    # -----------------------------------
    # Handle PyInstaller path
    # -----------------------------------
    if getattr(sys, 'frozen', False):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    app_path = os.path.join(base_dir, "app.py")

    if not os.path.exists(app_path):
        raise FileNotFoundError(f"app.py not found at: {app_path}")

    # -----------------------------------
    # Open browser AFTER server starts
    # -----------------------------------
    def open_browser():
        time.sleep(2)  # give Streamlit time to start
        webbrowser.open("http://localhost:8501")

    threading.Thread(target=open_browser, daemon=True).start()

    # -----------------------------------
    # Run Streamlit
    # -----------------------------------
    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
    ]

    import streamlit.web.cli as stcli
    sys.exit(stcli.main())