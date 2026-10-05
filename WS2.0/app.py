import os
import io
import re
import math
import time
import uuid
import threading
import logging
from functools import partial
from logging.handlers import RotatingFileHandler
import pdfplumber
import pandas as pd
from flask import Flask, render_template, request, send_file, jsonify

# Existing extractors
from extractors.plos_fetcher import fetch_plos_papers
from extractors.elife_fetcher import fetch_elife_papers
from extractors.europepmc_fetcher import fetch_europepmc_papers

# New extractors
from extractors.imedpub_fetcher import fetch_imedpub_papers
from extractors.openalex_fetcher import fetch_openalex_papers
from extractors.sciencedirect_fetcher import fetch_sciencedirect_papers

# API-based fetchers
from extractors.arxiv_fetcher import fetch_arxiv_papers
from extractors.biorxiv_fetcher import fetch_biorxiv_papers
from extractors.crossref_fetcher import fetch_crossref_papers
from extractors.pubmed_fetcher import fetch_pubmed_papers
from extractors.semanticscholar_fetcher import fetch_semanticscholar_papers
from extractors.preprints_fetcher import (
    fetch_all_preprints_papers,
    fetch_osf_papers,
    fetch_preprints_org_papers,
    fetch_chemrxiv_papers,
    fetch_ssrn_papers,
    fetch_scielo_preprints_papers,
    fetch_repec_papers,
    fetch_eric_papers,
    fetch_essoar_papers,
)
from extractors.ai_extractor_router import extract_authors_and_emails

from extractors.country_filter import COUNTRY_CODES, country_codes, eligible_authors, contact_allowed, resolve_email_author

app = Flask(__name__)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
PDFS_BASE_DIR = os.path.join(DOWNLOADS_DIR, "Pdf Files")
EXCEL_BASE_DIR = os.path.join(DOWNLOADS_DIR, "author details")

os.makedirs(PDFS_BASE_DIR, exist_ok=True)
os.makedirs(EXCEL_BASE_DIR, exist_ok=True)

# -----------------------------------------------------------
# Logging Setup — ISSUE-17
# Replaces all print() calls with a persistent, rotating log file.
# Console handler uses UTF-8 with 'replace' so Unicode paper titles
# never crash the Windows terminal (which defaults to cp1252).
# -----------------------------------------------------------
import sys

_log_file = os.path.join(BASE_DIR, "extraction.log")
try:
    _file_handler = RotatingFileHandler(
        _log_file, maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
except Exception:
    _file_handler = logging.NullHandler()

# Wrap stdout in a UTF-8 stream with 'replace' for unencodable chars
try:
    _utf8_stdout = open(sys.stdout.fileno(), mode="w", encoding="utf-8",
                        errors="replace", closefd=False, buffering=1)
except (OSError, ValueError):
    _utf8_stdout = sys.stdout
_console_handler = logging.StreamHandler(stream=_utf8_stdout)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[_file_handler, _console_handler],
)
log = logging.getLogger("extraction")

# -----------------------------------------------------------
# Background Task Store
# -----------------------------------------------------------
# Maps task_id -> {"status": ..., "progress": ..., "result": ...}
TASKS = {}
TASKS_LOCK = threading.Lock()

# Intra-process concurrency guard (one extraction per worker thread)
_INTRA_PROCESS_LOCK = threading.Lock()

# -----------------------------------------------------------
# Filesystem Lock — ISSUE-12
# Cross-process lock using a timestamp-stamped lock file.
# Works correctly under multi-worker WSGI (gunicorn --workers N).
# The threading lock handles same-process races; the file lock
# handles cross-process races on the master_email_list.csv.
# -----------------------------------------------------------
LOCK_FILE = os.path.join(DOWNLOADS_DIR, "extraction.lock")
_LOCK_TTL_SECONDS = 300  # 5 minutes — prevent interrupted tasks from wedging the server


def _acquire_extraction_lock():
    """
    Acquire the two-layer extraction lock:
      Layer 1: threading.Lock — prevents races within the same process.
      Layer 2: filesystem lock file — prevents races across processes.

    Returns True if the lock was acquired, False if it is already held.
    """
    # Layer 1: fast intra-process check
    if not _INTRA_PROCESS_LOCK.acquire(blocking=False):
        return False

    # Layer 2: cross-process file lock
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r") as f:
                timestamp = float(f.read().strip() or "0")
            age = time.time() - timestamp
            if age < _LOCK_TTL_SECONDS:
                # Live lock held by another process — reject
                _INTRA_PROCESS_LOCK.release()
                return False
            # Stale lock — clear it and proceed
            log.warning(
                f"[Lock] Stale extraction.lock found (age {age / 60:.0f} min). Clearing."
            )
            os.remove(LOCK_FILE)
        except Exception as e:
            log.warning(f"[Lock] Could not read lock file: {e}. Clearing and proceeding.")
            try:
                os.remove(LOCK_FILE)
            except Exception:
                pass

    try:
        with open(LOCK_FILE, "w") as f:
            f.write(str(time.time()))
    except Exception as e:
        log.error(f"[Lock] Failed to write lock file: {e}")
        _INTRA_PROCESS_LOCK.release()
        return False

    return True


def _release_extraction_lock():
    """Release the filesystem lock and the intra-process threading lock."""
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except Exception as e:
        log.warning(f"[Lock] Could not remove lock file: {e}")
    try:
        _INTRA_PROCESS_LOCK.release()
    except RuntimeError:
        pass  # Already released — safe to ignore


def _cleanup_stale_tasks():
    """Remove tasks that finished or were abandoned more than 30 minutes ago."""
    cutoff = time.time() - 1800
    with TASKS_LOCK:
        stale = [
            tid for tid, t in TASKS.items()
            if t.get("status") in ("done", "error") and t.get("ts", 0) < cutoff
        ]
        for tid in stale:
            TASKS.pop(tid, None)
    if stale:
        log.info(f"[Tasks] Cleaned up {len(stale)} stale task(s).")


def task_update(task_id, status, progress=None, result=None, percentage=None, contacts_found=None, **details):
    """Thread-safe update of task status."""
    with TASKS_LOCK:
        if task_id in TASKS:
            TASKS[task_id]["status"] = status
            if progress is not None:
                TASKS[task_id]["progress"] = progress
            if percentage is not None:
                TASKS[task_id]["percentage"] = percentage
            if contacts_found is not None:
                TASKS[task_id]["contacts_found"] = contacts_found
            TASKS[task_id].update(details)
            if result is not None:
                TASKS[task_id]["result"] = result
            if status in ("done", "error"):
                TASKS[task_id]["ts"] = time.time()


# -----------------------------------------------------------
# Master Email Tracker (Deduplication)
# -----------------------------------------------------------
MASTER_EMAIL_FILE = os.path.join(DOWNLOADS_DIR, "master_email_list.csv")

# ISSUE-09: Separate file to track papers that were attempted (even if no emails found).
# Prevents re-downloading PDFs that will never yield emails.
ATTEMPTED_DOIS_FILE = os.path.join(DOWNLOADS_DIR, "attempted_dois.txt")


def normalise_doi(raw):
    """
    ISSUE-10: Convert any DOI representation to a stable, lowercase dedup key.

    Handles:
      - https://doi.org/10.xxxx/...  →  10.xxxx/...
      - http://arxiv.org/abs/1234v2  →  arxiv:1234  (version stripped)
      - 10.xxxx/...                  →  10.xxxx/...  (unchanged)
      - "N/A", "", None              →  ""  (excluded from seen_dois)

    Returns "" for missing/invalid values so they are NEVER added to seen_dois,
    preventing false-positive deduplication collisions (e.g. two "N/A" papers
    being treated as the same paper).
    """
    if not raw:
        return ""
    s = str(raw).strip().lower()
    if s in ("n/a", "na", "", "none", "null"):
        return ""

    # Strip https://doi.org/ and http://doi.org/ prefixes
    for prefix in ("https://doi.org/", "http://doi.org/",
                   "https://dx.doi.org/", "http://dx.doi.org/"):
        if s.startswith(prefix):
            return s[len(prefix):]

    # Normalise arXiv abstract URLs → stable arxiv:<id> key (version stripped)
    for prefix in ("https://arxiv.org/abs/", "http://arxiv.org/abs/"):
        if s.startswith(prefix):
            arxiv_id = s[len(prefix):]
            arxiv_id = re.sub(r'v\d+$', '', arxiv_id)  # strip v1/v2/...
            return f"arxiv:{arxiv_id}"

    return s  # Raw DOI (e.g. 10.1038/...) — already a clean key


def load_seen_data():
    """
    Load the set of all previously scraped emails AND DOIs from:
      1. master_email_list.csv  (emails + DOIs of extracted papers)
      2. attempted_dois.txt     (DOIs of all attempted papers, incl. empty ones)

    Returns (seen_emails, seen_dois) — two separate sets.

    Why two sets?
    - seen_emails: skip individual duplicate emails
    - seen_dois:   skip the ENTIRE PAPER before any download/parse
    """
    seen_emails = set()
    seen_dois = set()

    # --- Load from master CSV ---
    if os.path.exists(MASTER_EMAIL_FILE):
        try:
            # utf-8-sig handles both plain UTF-8 and UTF-8-with-BOM files
            df = pd.read_csv(MASTER_EMAIL_FILE, encoding="utf-8-sig")
            if "Email ID" in df.columns:
                seen_emails = set(df["Email ID"].dropna().str.lower().tolist())
            if "DOI" in df.columns:
                for raw in df["DOI"].dropna().tolist():
                    key = normalise_doi(raw)
                    if key:
                        seen_dois.add(key)
        except Exception as e:
            log.warning(f"[Dedup] Could not read master CSV: {e}")

    # --- Load from attempted-dois file (ISSUE-09) ---
    if os.path.exists(ATTEMPTED_DOIS_FILE):
        try:
            with open(ATTEMPTED_DOIS_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    key = line.strip()
                    if key:
                        seen_dois.add(key)
        except Exception as e:
            log.warning(f"[Dedup] Could not read attempted_dois.txt: {e}")

    return seen_emails, seen_dois


def _record_attempted_doi(doi_key):
    """
    ISSUE-09: Append a normalised DOI key to the attempted-dois file.
    Called after every paper attempt, regardless of whether emails were found.
    This prevents re-downloading empty/image PDFs on future runs.
    """
    if not doi_key:
        return
    try:
        with open(ATTEMPTED_DOIS_FILE, "a", encoding="utf-8") as f:
            f.write(doi_key + "\n")
    except Exception as e:
        log.warning(f"[Dedup] Could not write attempted_dois.txt: {e}")


def save_new_emails_to_master(new_rows):
    """Append newly found verified email rows to the master CSV file."""
    if not new_rows:
        return
    # Filter rows with valid Email ID (allowing personal domains and gmail.com)
    new_rows = [
        r for r in new_rows
        if r.get("Email ID")
    ]
    if not new_rows:
        return
    # Strictly output Paper Title, Author Name, Email ID (no DOI, no PDF name, no source)
    cols = ["Paper Title", "Author Name", "Email ID"]
    new_df = pd.DataFrame(new_rows)
    for col in cols:
        if col not in new_df.columns:
            new_df[col] = ""
    new_df = new_df[cols]
    file_is_empty = (
        not os.path.exists(MASTER_EMAIL_FILE)
        or os.path.getsize(MASTER_EMAIL_FILE) == 0
    )
    new_df.to_csv(
        MASTER_EMAIL_FILE,
        mode="a",
        index=False,
        header=file_is_empty,
        encoding="utf-8-sig",
    )


# -----------------------------------------------------------
# Email Utilities
# -----------------------------------------------------------

# ISSUE-06: Generic / non-personal local-part names — these are platform
# or navigation addresses, not individual academic authors.
_GENERIC_LOCAL_PARTS = frozenset({
    "info", "admin", "support", "contact", "editor", "editorial", "webmaster",
    "noreply", "no-reply", "help", "line", "mail", "office", "submit",
    "submission", "postmaster", "reply", "donotreply", "do-not-reply",
    "mailer", "bounce", "newsletter", "list", "subscribe", "sales",
    "enquiries", "enquiry", "query", "feedback", "helpdesk",
})

# ISSUE-06: Expanded platform/publisher domain blocklist.
# These domains belong to publishers/platforms, not individual researchers.
_IGNORED_DOMAINS = frozenset({
    "plos.org", "elifesciences.org", "europepmc.org", "ebi.ac.uk",
    "ncbi.nlm.nih.gov", "crossref.org", "orcid.org", "adobe.com",
    "openalex.org", "imedpub.com",
    # New additions (ISSUE-06):
    "biorxiv.org", "medrxiv.org", "doi.org", "pubmed.ncbi.nlm.nih.gov",
    "frontiersin.org", "mdpi.com", "arxiv.org", "ssrn.com",
    "wiley.com", "springer.com", "elsevier.com", "tandfonline.com",
    "nature.com", "oup.com", "cambridge.org",
})


def clean_and_validate_email(raw_email):
    if not raw_email:
        return None
    cleaned = raw_email.strip(" \t\n\r*\u2020\u2021\u00a7#()[]{}<>,;:'\"")
    cleaned = re.split(r'[\s\(\[\{]', cleaned)[0].rstrip(".,;:")

    # Must match a standard email pattern
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', cleaned):
        return None

    local_part = cleaned.split("@")[0].lower()
    domain = cleaned.split("@")[-1].lower()
    tld = domain.split(".")[-1]

    # ISSUE-06: Reject generic / non-personal local parts
    if local_part in _GENERIC_LOCAL_PARTS:
        return None

    # Reject fused/malformed emails.
    # Original: TLD > 7 chars.
    # ISSUE-06 improvement: also detect 'monash.eduqi.fang' pattern where a
    # TLD-like segment (2-6 chars) is immediately followed by more alphabetic
    # chars without a dot separator (e.g., '.eduqi' contains 'edu' + 'qi').
    if len(tld) > 7:
        return None
    if re.search(r'\.[a-zA-Z]{2,6}[a-zA-Z]{2,}', domain):
        return None

    # Reject if domain has consecutive dots or is too long
    if ".." in domain or len(domain) > 50 or domain.count(".") > 4:
        return None
    if len(cleaned) > 80:
        return None

    # ISSUE-06: Reject platform/internal domains (expanded list)
    if any(d in domain for d in _IGNORED_DOMAINS):
        return None

    return cleaned.lower()


def unwrap_broken_emails(text):
    """
    Reassemble email addresses fragmented by PDF line-wrapping and
    multi-column layout interleaving. (ISSUE-02)
    """
    # --- Existing patterns ---
    # Stitch whitespace around @ and dots: 'john .doe @ uni . edu'
    text = re.sub(r'([\w.-]+)\s*@\s*([\w.-]+)\s*\.\s*([a-zA-Z]{2,})', r'\1@\2.\3', text)
    text = re.sub(r'(\b[\w]+)\s*\.\s*([\w]+)\s*\.\s*([\w]+@)', r'\1.\2.\3', text)
    text = re.sub(r'(\b[\w]+)\s*\.\s*([\w]+@)', r'\1.\2', text)
    text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1-\2', text)
    text = re.sub(r'([\w.+-]+)@\s*\n\s*([\w.-]+)', r'\1@\2', text)
    text = re.sub(r'([\w.-]+)\.\s*\n\s*([a-zA-Z]{2,})', r'\1.\2', text)
    text = re.sub(r'([\w.+-]+@[\w.-]+)\s*\n\s*([\w.-]+\.[a-zA-Z]{2,})', r'\1\2', text)
    # --- New patterns for multi-column PDF interleaving (ISSUE-02) ---
    # Domain split at TLD with whitespace: 'john@uni .edu' → 'john@uni.edu'
    text = re.sub(
        r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+)\s+([a-zA-Z]{2,6})\b',
        r'\1.\2', text
    )
    # Full email with whitespace around each segment: 'j.doe @ uni . edu'
    text = re.sub(
        r'([a-zA-Z0-9._%+-]+)\s*\.\s*([a-zA-Z0-9._%-]+)\s*@\s*'
        r'([a-zA-Z0-9.-]+)\s*\.\s*([a-zA-Z]{2,})',
        r'\1.\2@\3.\4', text
    )
    # Line break inside domain: 'john@university\n.edu'
    text = re.sub(
        r'(@[a-zA-Z0-9.-]+)\n([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
        r'\1\2', text
    )
    return text


def extract_full_names_from_pdf(text):
    candidate_names = []
    potential_blocks = re.findall(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', text)
    blacklist = {
        "Indian Journal", "Medical Research", "Medical College", "Research Centre",
        "Artificial Intelligence", "All Rights", "Creative Commons", "Open Access",
        "Author Response", "Authors Response", "Received January", "Accepted February",
        "Published June", "Conflicts Of", "Financial Support", "Public Health", "BMJ Open",
    }
    for name in potential_blocks:
        if name not in blacklist and len(name.split()) in [2, 3, 4]:
            if not any(
                b.lower() in name.lower()
                for b in ["department", "university", "hospital", "institute"]
            ):
                candidate_names.append(name.strip())
    return list(dict.fromkeys(candidate_names))


def extract_author_email_pairs(pdf_source, metadata_authors):
    mapped_pairs = []
    try:
        pdf_input = io.BytesIO(pdf_source) if isinstance(pdf_source, (bytes, bytearray)) else pdf_source
        with pdfplumber.open(pdf_input) as pdf:
            if len(pdf.pages) == 0:
                return mapped_pairs

            raw_text = ""
            for page in pdf.pages:
                # ISSUE-02: layout=True preserves column structure better than
                # layout=False, reducing column-interleave fragmentation.
                raw_text += (page.extract_text(layout=True) or "") + "\n"

            text = unwrap_broken_emails(raw_text)
            pdf_names = extract_full_names_from_pdf(text)
            all_candidate_authors = list(dict.fromkeys(metadata_authors + pdf_names))

            raw_matches = re.findall(
                r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)'
                r'(?:\s*\(([A-Z]+)\))?',
                text
            )

            for raw_email, initials in raw_matches:
                clean_email = clean_and_validate_email(raw_email)
                if not clean_email:
                    continue

                username = clean_email.split('@')[0].lower()
                clean_username = re.sub(r'[^a-z]', '', username)
                matched_author = None

                for author in all_candidate_authors:
                    # Strip non-alphabet characters from each part
                    raw_parts = [
                        re.sub(r'[^a-z]', '', p.lower())
                        for p in author.split()
                    ]
                    # Only keep parts that actually contain letters
                    name_parts = [p for p in raw_parts if len(p) > 0]
                    if any(len(part) >= 3 and part in clean_username for part in name_parts):
                        matched_author = author
                        break
                    if len(name_parts) >= 2:
                        first_init_last = name_parts[0][0] + name_parts[-1]
                        if first_init_last in clean_username:
                            matched_author = author
                            break

                if not matched_author and initials:
                    for author in all_candidate_authors:
                        author_initials = "".join(
                            [p[0].upper() for p in author.split() if p]
                        )
                        if initials.upper() == author_initials:
                            matched_author = author
                            break

                # ISSUE-03: Do NOT silently assign to first author.
                # metadata_authors[0] is the FIRST author (by listing order),
                # which is almost never the corresponding author. Using it produced
                # systematically incorrect Author↔Email pairings in the master CSV.
                # "Unknown" is honest and filterable downstream.
                if not matched_author:
                    matched_author = "Unknown"
                    log.debug(
                        f"    [Match fallback] {clean_email} → Unknown (no username/initials match)"
                    )

                if clean_email not in [p[1] for p in mapped_pairs]:
                    mapped_pairs.append((matched_author, clean_email))

    except Exception as e:
        log.error(f"Error parsing PDF source: {e}", exc_info=True)
    return mapped_pairs


# -----------------------------------------------------------
# Dispatch Mapping & Multi-Repository Registry
# -----------------------------------------------------------
from extractors.frontiers_fetcher import fetch_frontiers_papers
from extractors.aha_fetcher import fetch_aha_papers
from extractors.academic_connectors import (
    fetch_microsoft_academic_papers,
    fetch_cochrane_papers,
    fetch_hubmed_papers,
    fetch_thelancet_papers,
    fetch_f1000research_papers
)

SOURCE_FETCHERS = {
    # Direct Connectors
    "plos":            ("PLOS ONE",                  fetch_plos_papers),
    "pubmed":          ("PubMed / NCBI",            fetch_pubmed_papers),
    "biorxiv":         ("bioRxiv",                  fetch_biorxiv_papers),
    "medrxiv":         ("medRxiv",                  fetch_biorxiv_papers),
    "europepmc":       ("Europe PMC",                fetch_europepmc_papers),
    "arxiv":           ("arXiv.org",                 fetch_arxiv_papers),
    "openalex":        ("OpenAlex",                  fetch_openalex_papers),
    "semanticscholar": ("Semantic Scholar",         fetch_semanticscholar_papers),
    "crossref":        ("Crossref",                  fetch_crossref_papers),
    "elife":           ("eLife",                     fetch_elife_papers),
    "preprints":       ("Preprints.org",             fetch_preprints_org_papers),
    "sciencedirect":   ("ScienceDirect",             fetch_sciencedirect_papers),
    "imedpub":         ("iMedPub Group",             fetch_imedpub_papers),
    # Preprint Servers
    "osf":             ("OSF Preprints",             fetch_osf_papers),
    "chemrxiv":        ("ChemRxiv",                  fetch_chemrxiv_papers),
    "zenodo":          ("Zenodo",                    fetch_all_preprints_papers),
    "ssrn":            ("SSRN (open PDFs)",          fetch_ssrn_papers),
    "eartharxiv":      ("EarthArXiv",                partial(fetch_osf_papers, specific_prefix="10.31223")),
    "essoar":          ("ESS Open Archive / ESSOAr", fetch_essoar_papers),
    "essopenarchive":  ("ESS Open Archive",          fetch_essoar_papers),
    "eric":            ("ERIC (full-text PDFs)",      fetch_eric_papers),
    # These OSF/community servers and open indexes are queried through one
    # shared connector to avoid repeating the same underlying search.
    "agrirxiv":        ("AgriXiv (open preprint index)", fetch_openalex_papers),
    "crimrxiv":        ("CrimRxiv (open index)",      fetch_openalex_papers),
    "engrxiv":         ("engrXiv (OSF DOI collection)", partial(fetch_osf_papers, specific_prefix="10.31224")),
    "focusarchive":    ("FocUS Archive (OSF)",        fetch_osf_papers),
    "lawarxiv":        ("Law Archive (OSF DOI collection)", partial(fetch_osf_papers, specific_prefix="10.31228")),
    "nutrixiv":        ("NutriXiv (OSF DOI collection)", partial(fetch_osf_papers, specific_prefix="10.31220")),
    "psyarxiv":        ("PsyArXiv (OSF DOI collection)", partial(fetch_osf_papers, specific_prefix="10.31234")),
    "socarxiv":        ("SocArXiv (OSF DOI collection)", partial(fetch_osf_papers, specific_prefix="10.31235")),
    "sportrxiv":       ("SportRxiv (OSF DOI collection)", partial(fetch_osf_papers, specific_prefix="10.31236")),
    "scielopreprints": ("SciELO Preprints",           fetch_scielo_preprints_papers),
    "repec":           ("RePEc (open index + PDFs)",  fetch_repec_papers),
    "peerjpreprints":  ("PeerJ Preprints (archive index)", fetch_openalex_papers),
    "riojournal":      ("RIO Journal (Crossref)",     fetch_crossref_papers),
    "elis":            ("E-LIS / RCLIS (OA index)",   fetch_openalex_papers),
    # Biomedical & Clinical Journals
    "peerj":           ("PeerJ",                     fetch_openalex_papers),
    "f1000":           ("F1000Research",             fetch_f1000research_papers),
    "microsoftresearch": ("Microsoft Research publications (OpenAlex)", fetch_microsoft_academic_papers),
    "cochrane":        ("Cochrane (open PDF copies only)", fetch_cochrane_papers),
    "hubmed":          ("HubMed",                    fetch_hubmed_papers),
    "lancet":          ("The Lancet Preprints",      fetch_thelancet_papers),
    "frontiers":       ("Frontiers",                 fetch_frontiers_papers),
    "ahajournals":     ("AHA Journals",              fetch_aha_papers),
    "mdpi":            ("MDPI",                      fetch_europepmc_papers),
    "hindawi":         ("Hindawi",                   fetch_europepmc_papers),
    "biomedcentral":   ("BioMed Central (BMC)",      fetch_europepmc_papers),
    "pmc":             ("PubMed Central (PMC)",      fetch_pubmed_papers),
    # Global Scholarly Indexes & Publishers
    "doaj":            ("DOAJ",                      fetch_openalex_papers),
    "base":            ("BASE Search",               fetch_openalex_papers),
    "core":            ("CORE OA",                   fetch_openalex_papers),
    "researchgate":    ("ResearchGate",              fetch_semanticscholar_papers),
    "springer":        ("Springer Open",             fetch_crossref_papers),
    "tandf":           ("Taylor & Francis",          fetch_crossref_papers),
    "scielo":          ("SciELO",                    fetch_openalex_papers),
    "hal":             ("HAL Open Archive",          fetch_openalex_papers),
}


# -----------------------------------------------------------
# Strict Validation Helpers
# -----------------------------------------------------------
def is_valid_author(name):
    """
    Strict validation for author name.
    Only accept real person names with alphabetic characters.
    Rejects 'Unknown', 'None', 'N/A', empty strings, institutions, and roles.
    """
    if not name or not isinstance(name, str):
        return False
    clean = name.strip()
    if not clean:
        return False
    lower = clean.lower()
    invalid_keywords = {
        "unknown", "none", "n/a", "na", "null", "undefined",
        "author", "authors", "et al", "et al.", "et. al.", "corresponding author",
        "first author", "co-author", "department", "university", "institute",
        "hospital", "center", "centre", "laboratory", "division", "school",
        "faculty", "college", "corporation", "consortium", "group", "team"
    }
    if lower in invalid_keywords:
        return False
    # If the string contains @, URL, or HTML, it's not a real author name
    if "@" in clean or "http:" in lower or "https:" in lower or "www." in lower or "<" in clean:
        return False
    # Must contain alphabetic characters
    if not re.search(r'[a-zA-Z]', clean):
        return False
    # Check length
    if len(clean) < 2 or len(clean) > 80:
        return False
    return True


def is_valid_title(title):
    """
    Strict validation for paper title.
    Rejects empty or placeholder titles.
    """
    if not title or not isinstance(title, str):
        return False
    clean = title.strip()
    if not clean:
        return False
    lower = clean.lower()
    if lower in ("untitled", "untitled paper", "none", "n/a", "null", "na"):
        return False
    if len(clean) < 3:
        return False
    return True


# -----------------------------------------------------------
# Background Extraction Worker
# -----------------------------------------------------------
def _run_extraction_task(task_id, source_sites, topic, max_papers, filters=None):
    """
    Runs extraction across one or multiple repositories.
    Strictly yields rows with: 'Paper Title', 'Author Name', 'Email ID'.
    Completely excludes DOI, PDF File Name, and Source Journal from output.
    """
    filters = filters or {}
    country_cache = {}
    selected_countries = filters.get("countries", [])
    short_id = task_id[:8]
    rows = []           # All rows strictly with keys: "Paper Title", "Author Name", "Email ID"
    pending_rows = []   # Batch buffer — flushed every 5 papers
    dedup_emails = set()
    dedup_pairs = set()
    task_pdf_dirs = []

    if isinstance(source_sites, str):
        source_sites = [source_sites]
    source_sites = [s for s in source_sites if s in SOURCE_FETCHERS]
    if not source_sites:
        source_sites = ["plos"]

    # Each repository label is backed by a connector. Search every distinct
    # connector, with user-selected labels first, without repeating aliases.
    connector_order = []
    connector_ids = set()
    for key in source_sites + list(SOURCE_FETCHERS):
        if key not in SOURCE_FETCHERS:
            continue
        connector_id = id(SOURCE_FETCHERS[key][1])
        if connector_id not in connector_ids:
            connector_ids.add(connector_id)
            connector_order.append(key)
    source_sites = connector_order

    def _flush_pending():
        nonlocal pending_rows
        if pending_rows:
            # STRICT FILTER: Discard if even ONE field (title, author, email) is missing or invalid
            valid_batch = []
            for r in pending_rows:
                t = (r.get("Paper Title") or "").strip()
                a = (r.get("Author Name") or "").strip()
                e = (r.get("Email ID") or "").strip()
                clean_e = clean_and_validate_email(e)
                if is_valid_title(t) and is_valid_author(a) and clean_e:
                    pair_key = (t.lower(), a.lower())
                    if clean_e in dedup_emails or pair_key in dedup_pairs:
                        continue
                    dedup_emails.add(clean_e)
                    dedup_pairs.add(pair_key)
                    valid_batch.append({
                        "Paper Title": t,
                        "Author Name": a,
                        "Email ID": clean_e
                    })
            if valid_batch:
                save_new_emails_to_master(valid_batch)
                rows.extend(valid_batch)
                task_update(task_id, "running", contacts_found=len(rows))
                log.info(
                    f"[Task {short_id}] Batch flushed {len(valid_batch)} verified rows to master CSV. Progress: {len(rows)}/{max_papers}"
                )
            pending_rows = []

    try:
        topic_clean = re.sub(r'[^\w\-]', '_', topic).lower()[:80]
        task_update(task_id, "running", "Loading previously seen emails and papers...", percentage=5, contacts_found=0)
        seen_emails, seen_dois = load_seen_data()
        if selected_countries:
            # A paper attempted for one country can contain contacts in another.
            seen_dois = set()
        log.info(
            f"[Dedup] Loaded {len(seen_emails)} seen emails, {len(seen_dois)} seen DOIs."
        )

        n_sources = len(source_sites)
        start_time = time.time()

        # Start with a target-scaled batch to minimize first-result latency and
        # avoid unnecessary downloads when the requested count is small.
        per_source_max = min(100, max(5, math.ceil(max_papers * 2.5)))

        def _pagination_step(source_key, requested_limit):
            """Return the result-window size used by offset-based connectors."""
            if source_key == "microsoftresearch":
                # Its OpenAlex lineage fetcher requests two rows per desired
                # result, capped at 50; advance by that same window.
                return min(max(5, requested_limit * 2), 50)
            if source_key in {
                "osf", "preprints", "eartharxiv", "agrirxiv", "engrxiv",
                "focusarchive", "lawarxiv", "nutrixiv", "psyarxiv", "socarxiv",
                "sportrxiv", "scielopreprints", "ssrn", "chemrxiv", "repec",
                "hubmed",
            }:
                return min(max(1, requested_limit), 50 if source_key in {"chemrxiv", "ssrn", "repec"} else 100)
            if source_key == "cochrane":
                return min(max(1, requested_limit) * 2, 50)
            if source_key == "europepmc":
                return min(max(requested_limit * 2, 50), 1000)
            if source_key in {"openalex", "agrirxiv", "crimrxiv", "peerjpreprints", "elis", "doaj", "base", "core", "scielo", "hal", "peerj"}:
                return min(max(requested_limit, 25), 200)
            if source_key in {"crossref", "springer", "tandf", "riojournal"}:
                return 100
            if source_key in {"biorxiv", "medrxiv"}:
                return min(100, max(1, requested_limit) * 2)
            if source_key == "eric":
                return min(max(requested_limit, 1) * 3, 200)
            if source_key in {"essoar", "essopenarchive"}:
                return min(max(requested_limit, 1) * 2, 100)
            return requested_limit

        source_offsets = {s: 0 for s in source_sites}
        source_exhausted = set()
        source_empty_pages = {s: 0 for s in source_sites}
        source_duplicate_pages = {s: 0 for s in source_sites}
        seen_paper_keys = set()
        total_downloaded = 0
        doi_skipped_count = 0
        papers_searched = 0
        pdfs_downloaded = 0
        pdfs_parsed = 0

        def _process_item(item):
            nonlocal doi_skipped_count, papers_searched, pdfs_downloaded, pdfs_parsed
            if len(rows) + len(pending_rows) >= max_papers:
                return True
            papers_searched += 1

            allowed_authors = eligible_authors(item, selected_countries, country_cache)
            if allowed_authors == set():
                return False
            paper_title = (item.get("title") or "Untitled Paper").strip()
            item_doi_raw = item.get("doi", "")
            item_doi = normalise_doi(item_doi_raw)

            # Deduplicate by DOI if available
            if item_doi and item_doi in seen_dois:
                doi_skipped_count += 1
                return False

            paper_key = item_doi or paper_title.casefold()
            if paper_key in seen_paper_keys:
                return False
            seen_paper_keys.add(paper_key)

            if item_doi:
                if not selected_countries:
                    _record_attempted_doi(item_doi)
                seen_dois.add(item_doi)

            # Count contacts only when the fetcher saved a real PDF. Metadata
            # emails remain useful to fetchers for discovery, never as results.
            file_path = item.get("file_path")
            pdf_bytes = item.pop("pdf_bytes", None)
            keep_pdf_files = os.getenv("KEEP_DOWNLOADED_PDFS", "0").strip().lower() in {"1", "true", "yes"}
            is_pdf = False
            if isinstance(pdf_bytes, bytearray):
                pdf_bytes = bytes(pdf_bytes)
            if isinstance(pdf_bytes, bytes):
                is_pdf = pdf_bytes.startswith(b"%PDF-")
            elif file_path and os.path.isfile(file_path):
                try:
                    with open(file_path, "rb") as pdf_file:
                        pdf_bytes = pdf_file.read()
                    is_pdf = pdf_bytes.startswith(b"%PDF-")
                except OSError:
                    pass
                finally:
                    # Fetchers still use path-based download helpers. In the
                    # default mode, move the bytes into memory and remove the
                    # temporary artifact before parsing or processing results.
                    if not keep_pdf_files:
                        try:
                            os.remove(file_path)
                        except OSError:
                            pass
            if is_pdf:
                pdfs_downloaded += 1
                pairs = extract_author_email_pairs(pdf_bytes, item.get("authors", []))
                pdfs_parsed += 1
                for author, email in pairs:
                    clean_email = clean_and_validate_email(email)
                    if not clean_email or clean_email in seen_emails:
                        continue
                    if not contact_allowed(author, allowed_authors) or not is_valid_author(author) or not is_valid_title(paper_title):
                        continue
                    pair_key = (paper_title.lower(), author.strip().lower())
                    if clean_email in dedup_emails or pair_key in dedup_pairs:
                        continue
                    pending_rows.append({
                        "Paper Title": paper_title,
                        "Author Name": author.strip(),
                        "Email ID": clean_email,
                    })
                    seen_emails.add(clean_email)
                    if len(rows) + len(pending_rows) >= max_papers:
                        return True

            if len(pending_rows) >= 5 or (len(rows) + len(pending_rows) >= max_papers):
                _flush_pending()
            return len(rows) + len(pending_rows) >= max_papers

        # Preserve selected-source priority, then cover remaining distinct connectors.
        sorted_sources = list(source_sites)

        def _fetch_single_source(src_tuple):
            s_idx, s_key = src_tuple
            s_label, s_func = SOURCE_FETCHERS[s_key]
            t_dir = os.path.join(PDFS_BASE_DIR, f"{s_key}_{topic_clean}_{short_id}_pdfs")
            os.makedirs(t_dir, exist_ok=True)
            if t_dir not in task_pdf_dirs:
                task_pdf_dirs.append(t_dir)
            for attempt in range(3):
                try:
                    res = s_func(topic, per_source_max, t_dir, filters=filters)
                    return s_idx, s_key, s_label, res
                except Exception as e:
                    if attempt == 2:
                        log.error(f"[Task {short_id}] Error in fetcher {s_key}: {e}")
                        return s_idx, s_key, s_label, []
                    time.sleep(2 ** attempt)

        task_update(
            task_id, "running",
            f"Searching {n_sources} distinct PDF connectors in priority order...",
            percentage=15,
            contacts_found=0
        )

        completed_sources = 0
        for idx, key in enumerate(sorted_sources):
                if len(rows) + len(pending_rows) >= max_papers:
                    _flush_pending()
                    log.info(f"[Task {short_id}] Target limit of {max_papers} verified contacts achieved! Stopping early.")
                    break

                try:
                    src_idx, source_key, source_label, downloaded = _fetch_single_source((idx, key))
                except Exception as ex:
                    source_key = key
                    source_label = SOURCE_FETCHERS[key][0]
                    log.error(f"[Task {short_id}] Source failed: {ex}")
                    downloaded = []

                # Offsets count the requested result window, not only PDFs that
                # survived filtering/download. Keep the cursor stable so a later
                # page doesn't overlap the initial request when few PDFs qualify.
                source_offsets[source_key] = _pagination_step(source_key, per_source_max)
                if downloaded:
                    source_empty_pages[source_key] = 0
                else:
                    source_empty_pages[source_key] += 1
                    if source_empty_pages[source_key] >= 3:
                        source_exhausted.add(source_key)
                completed_sources += 1
                total_downloaded += len(downloaded)

                current_pct = min(88, 15 + int(65 * (completed_sources / n_sources)))
                current_found = len(rows) + len(pending_rows)
                task_update(
                    task_id, "running",
                    f"Processing {source_label}: {len(rows) + len(pending_rows)} / {max_papers} contacts; {completed_sources} / {n_sources} sources searched...",
                    percentage=current_pct,
                    contacts_found=current_found
                )

                for item in downloaded:
                    if _process_item(item):
                        _flush_pending()
                        break

                _flush_pending()
                task_update(
                    task_id, "running", contacts_found=len(rows) + len(pending_rows),
                    papers_searched=papers_searched, pdfs_downloaded=pdfs_downloaded,
                    pdfs_parsed=pdfs_parsed, sources_remaining=n_sources - completed_sources,
                )
                if len(rows) >= max_papers:
                    log.info(f"[Task {short_id}] Target limit of {max_papers} verified contacts achieved! Stopping early.")
                    break

        # Final flush from source iteration
        _flush_pending()

        # -----------------------------------------------------------------
        # TARGET-DRIVEN ADAPTIVE TOP-UP PASS:
        # If target contact count was not yet met, systematically paginate
        # and harvest subsequent paper batches from high-yield engines
        # until the target limit (max_papers) is accurately satisfied.
        # -----------------------------------------------------------------
        if len(rows) < max_papers:
            shortfall = max_papers - len(rows)
            log.info(
                f"[Task {short_id}] Pass 1 yielded {len(rows)}/{max_papers} contacts. "
                f"Starting adaptive target pagination for {shortfall} remaining contacts..."
            )
            active_top_up_keys = list(source_sites)
            exhausted_sources = set(source_exhausted)
            round_idx = 0
            while True:
                if len(rows) >= max_papers:
                    break

                active_in_round = [k for k in active_top_up_keys if k not in exhausted_sources]
                if not active_in_round:
                    break

                for top_key in active_in_round:
                    if len(rows) >= max_papers:
                        break

                    needed = max_papers - len(rows)
                    top_label, top_fetcher = SOURCE_FETCHERS[top_key]
                    current_pct = min(94, 70 + int(24 * (len(rows) / max(1, max_papers))))
                    task_update(
                        task_id, "running",
                        f"Harvesting {top_label} (page {round_idx + 2}) to reach target ({len(rows)}/{max_papers} found)...",
                        percentage=current_pct,
                        contacts_found=len(rows)
                    )

                    # Keep page size constant: connector offsets are based on
                    # requested records, and changing limit can repeat or skip pages.
                    top_quota = per_source_max
                    current_offset = source_offsets.get(top_key, 0)
                    topic_pdf_dir = os.path.join(PDFS_BASE_DIR, f"{top_key}_{topic_clean}_{short_id}_pdfs")
                    os.makedirs(topic_pdf_dir, exist_ok=True)
                    if topic_pdf_dir not in task_pdf_dirs:
                        task_pdf_dirs.append(topic_pdf_dir)

                    extra_downloaded = []
                    for attempt in range(3):
                        try:
                            extra_downloaded = top_fetcher(topic, top_quota, topic_pdf_dir, filters=filters, offset=current_offset)
                            break
                        except TypeError:
                            try:
                                extra_downloaded = top_fetcher(topic, top_quota, topic_pdf_dir, filters=filters)
                                break
                            except Exception as ex:
                                if attempt == 2:
                                    log.warning(f"[Task {short_id}] Top-up error on {top_key}: {ex}")
                                else:
                                    time.sleep(2 ** attempt)
                        except Exception as ex:
                            if attempt == 2:
                                log.warning(f"[Task {short_id}] Top-up error on {top_key}: {ex}")
                            else:
                                time.sleep(2 ** attempt)

                    source_offsets[top_key] = current_offset + _pagination_step(top_key, top_quota)
                    if extra_downloaded:
                        source_empty_pages[top_key] = 0
                    else:
                        source_empty_pages[top_key] = source_empty_pages.get(top_key, 0) + 1
                        if source_empty_pages[top_key] >= 3:
                            exhausted_sources.add(top_key)
                    if not extra_downloaded:
                        continue

                    prior_seen_papers = len(seen_paper_keys)

                    for item in extra_downloaded:
                        if _process_item(item):
                            _flush_pending()
                            break

                    _flush_pending()
                    task_update(
                        task_id, "running", contacts_found=len(rows) + len(pending_rows),
                        papers_searched=papers_searched, pdfs_downloaded=pdfs_downloaded,
                        pdfs_parsed=pdfs_parsed, sources_remaining=n_sources - len(exhausted_sources),
                    )
                    if len(seen_paper_keys) == prior_seen_papers:
                        source_duplicate_pages[top_key] = source_duplicate_pages.get(top_key, 0) + 1
                        if source_duplicate_pages[top_key] >= 3:
                            exhausted_sources.add(top_key)
                    else:
                        source_duplicate_pages[top_key] = 0
                    if len(rows) >= max_papers:
                        log.info(f"[Task {short_id}] Target of {max_papers} verified contacts achieved during top-up!")
                        break

                round_idx += 1

            _flush_pending()

        # STRICT FILTER & STRICT DEDUPLICATION:
        # Discard any record where even ONE field (title, author, email) is missing or invalid.
        # Deduplicate strictly across email and (paper title, author) combinations.
        final_strict_rows = []
        dedup_emails = set()
        dedup_pairs = set()

        for r in rows:
            t = (r.get("Paper Title") or "").strip()
            a = (r.get("Author Name") or "").strip()
            e = (r.get("Email ID") or "").strip()
            clean_e = clean_and_validate_email(e)
            if is_valid_title(t) and is_valid_author(a) and clean_e:
                pair_key = (t.lower(), a.lower())
                if clean_e in dedup_emails or pair_key in dedup_pairs:
                    continue
                dedup_emails.add(clean_e)
                dedup_pairs.add(pair_key)
                final_strict_rows.append({
                    "Paper Title": t,
                    "Author Name": a,
                    "Email ID": clean_e
                })
        # Exact target capping: Return up to max_papers
        rows = final_strict_rows[:max_papers]

        log.info(f"[Task {short_id}] Extraction complete: {len(rows)}/{max_papers} PDF-extracted contacts")

        if not rows:
            if doi_skipped_count > 0 and doi_skipped_count == total_downloaded:
                message = (
                    f"All {doi_skipped_count} papers for '{topic}' on selected sources "
                    f"are already in your collection. Try a different topic or select more sources."
                )
            elif doi_skipped_count > 0:
                message = (
                    f"{doi_skipped_count} papers already collected (skipped). "
                    f"Remaining papers had no valid author names with verified emails."
                )
            else:
                message = f"Source exhaustion: found 0 of {max_papers} requested unique PDF-extracted contacts for '{topic}'."
            task_update(task_id, "done", "", result={
                "success": False,
                "message": message,
                "data": [],
                "file": None,
                "requested_count": max_papers,
                "total_records": 0,
                "shortfall": max_papers,
            }, percentage=100, contacts_found=0)
            return

        # Write Excel output strictly with 3 columns: Paper Title, Author Name, Email ID
        total_found = len(rows)
        task_update(task_id, "running", f"Writing {total_found}/{max_papers} PDF-extracted contacts to Excel...", percentage=95, contacts_found=total_found)
        excel_filename = f"authors_{topic_clean}_{int(time.time())}.xlsx"
        excel_path = os.path.join(EXCEL_BASE_DIR, excel_filename)
        df = pd.DataFrame(rows)[["Paper Title", "Author Name", "Email ID"]]
        with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Authors")
            ws = writer.sheets["Authors"]
            for col in ws.columns:
                max_len = max(len(str(cell.value or "")) for cell in col)
                ws.column_dimensions[col[0].column_letter].width = max(max_len + 4, 18)

        log.info(f"[Task {short_id}] Done. {len(rows)} verified records written to {excel_filename}")
        task_update(task_id, "done", "", result={
            "success": len(rows) == max_papers,
            "total_records": len(rows),
            "requested_count": max_papers,
            "shortfall": max(0, max_papers - len(rows)),
            "message": (f"Reached the requested {max_papers} unique PDF-extracted contacts." if len(rows) == max_papers else f"Source exhaustion: found {len(rows)} of {max_papers} requested unique PDF-extracted contacts."),
            "download_file": excel_filename,
            "data": rows,
        }, percentage=100, contacts_found=len(rows))

    except Exception as e:
        log.error(f"[Task {short_id}] CRASHED: {e}", exc_info=True)
        _flush_pending()
        task_update(task_id, "error", str(e), result={
            "success": False,
            "message": f"Extraction failed: {str(e)}",
            "data": rows,
            "file": None,
        }, percentage=100, contacts_found=len(rows))
    finally:
        if os.getenv("KEEP_DOWNLOADED_PDFS", "0").strip().lower() not in {"1", "true", "yes"}:
            for pdf_dir in task_pdf_dirs:
                try:
                    for filename in os.listdir(pdf_dir):
                        if filename.lower().endswith(".pdf"):
                            try:
                                os.remove(os.path.join(pdf_dir, filename))
                            except OSError:
                                pass
                    os.rmdir(pdf_dir)
                except OSError:
                    pass
        _release_extraction_lock()
        _cleanup_stale_tasks()


# -----------------------------------------------------------
# Flask Routes
# -----------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html", countries=COUNTRY_CODES)


@app.route("/start-extraction", methods=["POST"])
def start_extraction():
    """
    Starts extraction across one or multiple selected repositories.
    """
    selected_sources = request.form.getlist("source_sites[]")
    if not selected_sources:
        single = request.form.get("source_site", "").strip().lower()
        if single:
            selected_sources = [single]
        else:
            selected_sources = ["plos"]

    valid_sources = [s for s in selected_sources if s in SOURCE_FETCHERS]
    if not valid_sources:
        valid_sources = ["plos"]

    topic = request.form.get("topic", "").strip()
    try:
        max_papers = int(request.form.get("max_papers", 10))
    except (ValueError, TypeError):
        max_papers = 10
    max_papers = max(1, min(max_papers, 1000))

    if not topic:
        return jsonify({"error": "Please enter a valid research topic or keyword."}), 400

    raw_year_from = request.form.get("year_from", "").strip()
    raw_year_to   = request.form.get("year_to",   "").strip()
    filters = {
        "countries":     request.form.getlist("countries[]"),
        "year_from":     int(raw_year_from) if raw_year_from.isdigit() else None,
        "year_to":       int(raw_year_to)   if raw_year_to.isdigit()   else None,
        "article_types": request.form.getlist("article_types[]"),
    }

    if any(not country_codes([c]) for c in filters["countries"]):
        return jsonify({"error": "Select supported countries from the list."}), 400
    if filters["year_from"] and filters["year_to"] and filters["year_from"] > filters["year_to"]:
        return jsonify({"error": "The start year must be before the end year."}), 400

    if not _acquire_extraction_lock():
        return jsonify({
            "error": "An extraction is already in progress. Please wait for it to finish."
        }), 429

    task_id = str(uuid.uuid4())
    now = time.time()
    with TASKS_LOCK:
        TASKS[task_id] = {
            "status": "starting",
            "progress": "Initialising multi-source extraction...",
            "percentage": 0,
            "contacts_found": 0,
            "requested_count": max_papers,
            "result": None,
            "ts": now,
            "started_at": now,
        }

    thread = threading.Thread(
        target=_run_extraction_task,
        args=(task_id, valid_sources, topic, max_papers, filters),
        daemon=True,
    )
    thread.start()
    log.info(
        f"[Task {task_id[:8]}] Queued: sources={valid_sources}, "
        f"topic='{topic}', max={max_papers}, filters={filters}"
    )

    return jsonify({"task_id": task_id})


@app.route("/status/<task_id>")
def task_status(task_id):
    """Polling endpoint — browser calls this every 2.5 seconds."""
    with TASKS_LOCK:
        task = TASKS.get(task_id)
    if not task:
        return jsonify({"error": "Task not found."}), 404

    pct = max(0, min(100, task.get("percentage", 0)))
    started_at = task.get("started_at", time.time())
    elapsed = max(1.0, time.time() - started_at)

    # Dynamic remaining seconds calculation
    if pct > 0:
        total_estimated = elapsed / (pct / 100.0)
        remaining_seconds = max(0, int(total_estimated - elapsed))
    else:
        remaining_seconds = 30  # Default warm-up estimate

    return jsonify({
        "status": task["status"],
        "progress": task["progress"],
        "percentage": pct,
        "contacts_found": task.get("contacts_found", 0),
        "requested_count": task.get("requested_count", 0),
        "papers_searched": task.get("papers_searched", 0),
        "pdfs_downloaded": task.get("pdfs_downloaded", 0),
        "pdfs_parsed": task.get("pdfs_parsed", 0),
        "sources_remaining": task.get("sources_remaining", 0),
        "elapsed_seconds": int(elapsed),
        "eta_seconds": remaining_seconds,
    })


@app.route("/result/<task_id>")
def task_result(task_id):
    """Called once when status is 'done'. Returns the final data."""
    with TASKS_LOCK:
        task = TASKS.get(task_id)
    if not task or task["status"] not in ("done", "error"):
        return jsonify({"error": "Result not ready."}), 404
    # Clean up task from memory after delivering result
    with TASKS_LOCK:
        TASKS.pop(task_id, None)
    return jsonify(task["result"])


@app.route("/download/<filename>")
def download_excel(filename):
    file_path = os.path.join(EXCEL_BASE_DIR, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return "File not found", 404


if __name__ == "__main__":
    app.run(debug=True, port=5000)
