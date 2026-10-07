import sys
import os
import threading
import webbrowser
from pathlib import Path

# Add WS2.0 to path so extractors and app modules import cleanly
WS_DIR = Path(__file__).resolve().parent / "WS2.0"
if str(WS_DIR) not in sys.path:
    sys.path.insert(0, str(WS_DIR))

from app import app
import config

if __name__ == "__main__":
    display_host = "localhost" if config.HOST == "0.0.0.0" else config.HOST
    browser_url = f"http://{display_host}:{config.PORT}"
    print(f"[*] Starting Academic Author & Email Extractor on {browser_url}")
    print(f"    --> Opening in your default browser")
    if not config.DEBUG or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        threading.Timer(1.0, webbrowser.open_new_tab, args=(browser_url,)).start()
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
