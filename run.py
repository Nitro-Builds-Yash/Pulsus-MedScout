import sys
import os
from pathlib import Path

# Add WS2.0 to path so extractors and app modules import cleanly
WS_DIR = Path(__file__).resolve().parent / "WS2.0"
if str(WS_DIR) not in sys.path:
    sys.path.insert(0, str(WS_DIR))

from app import app
import config

if __name__ == "__main__":
    display_host = "localhost" if config.HOST == "0.0.0.0" else config.HOST
    print(f"[*] Starting Academic Author & Email Extractor on http://{display_host}:{config.PORT}")
    print(f"    --> Open in browser: http://localhost:{config.PORT} or http://127.0.0.1:{config.PORT}")
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)

