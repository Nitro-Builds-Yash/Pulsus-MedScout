import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
WS_DIR = BASE_DIR / "WS2.0"
DOWNLOADS_DIR = WS_DIR / "downloads"
PDFS_DIR = DOWNLOADS_DIR / "Pdf Files"
EXCEL_DIR = DOWNLOADS_DIR / "author details"

# Ensure runtime directories exist
PDFS_DIR.mkdir(parents=True, exist_ok=True)
EXCEL_DIR.mkdir(parents=True, exist_ok=True)

# Server Config
HOST = os.getenv("APP_HOST", "0.0.0.0")
PORT = int(os.getenv("APP_PORT", 5000))
DEBUG = os.getenv("APP_DEBUG", "True").lower() in ("true", "1", "yes")

# API Politeness & Contact
POLITE_EMAIL = os.getenv("POLITE_EMAIL", "academic-researcher@example.org")
USER_AGENT = os.getenv("USER_AGENT", "AcademicEmailExtractor/2.0 (Research Outreach Suite)")

# Extraction Settings
MAX_PAPERS_DEFAULT = int(os.getenv("MAX_PAPERS_DEFAULT", 10))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 15))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))
