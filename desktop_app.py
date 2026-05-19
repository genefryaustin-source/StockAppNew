import os
import sys
import subprocess
import time
import socket
import webview


def wait_for_server(port, timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except:
            time.sleep(0.3)
    return False


def main():

    print("🔥 CORRECT DESKTOP APP LOADED")

    if getattr(sys, "frozen", False):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    app_path = os.path.join(base_dir, "equity_app.py")

    if not os.path.exists(app_path):
        raise RuntimeError(f"Missing app: {app_path}")

    runner_path = os.path.join(base_dir, "run_streamlit.py")

    port = 8501

    print(f"🚀 Launching Streamlit subprocess on port {port}")

    process = subprocess.Popen(
        [sys.executable, runner_path, app_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW
    )

    # Wait for server
    if not wait_for_server(port):
        process.terminate()
        raise RuntimeError("❌ Streamlit failed to start")

    print("✅ Server ready — launching desktop UI")

    webview.create_window(
        "Equity Research Terminal",
        f"http://127.0.0.1:{port}",
        width=1600,
        height=1000,
    )

    webview.start()

    print("Shutting down...")
    process.terminate()


if __name__ == "__main__":
    main()