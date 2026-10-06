import os
import io
import re
import math
import time
import uuid
import threading
import logging
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler
import pdfplumber
import pandas as pd
from flask import Flask, render_template, request, jsonify, send_file

# Active source connectors from the upstream registry.
from extractors.pubmed_fetcher import fetch_pubmed_papers
from extractors.europepmc_fetcher import fetch_europepmc_papers
from extractors.plos_fetcher import fetch_plos_papers
from extractors.elife_fetcher import fetch_elife_papers
from extractors.openalex_fetcher import fetch_openalex_papers
from extractors.arxiv_fetcher import fetch_arxiv_papers
from extractors.biorxiv_fetcher import fetch_biorxiv_papers
from extractors.crossref_fetcher import fetch_crossref_papers
from extractors.frontiers_fetcher import fetch_frontiers_papers
from extractors.aha_fetcher import fetch_aha_papers

from extractors.country_filter import COUNTRY_CODES, country_codes, eligible_authors, contact_allowed, resolve_email_author

app = Flask(__name__)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
PDFS_BASE_DIR = os.path.join(DOWNLOADS_DIR, "Pdf Files")

os.makedirs(PDFS_BASE_DIR, exist_ok=True)

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
_DATA_LOCK = threading.RLock()
DATA_LOCK_FILE = os.path.join(DOWNLOADS_DIR, "data.lock")

# -----------------------------------------------------------
# Extraction capacity
# -----------------------------------------------------------
MAX_CONCURRENT_EXTRACTIONS = 5
LOCK_FILE_PREFIX = os.path.join(DOWNLOADS_DIR, "extraction_")


@contextmanager
def _shared_data_lock():
    """Serialize shared data-file access in this process and across workers."""
    with _DATA_LOCK:
        with open(DATA_LOCK_FILE, "a+b") as lock:
            lock.seek(0, os.SEEK_END)
            if lock.tell() == 0:
                lock.write(b"\0")
                lock.flush()
            lock.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
                try:
                    yield
                finally:
                    lock.seek(0)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _acquire_extraction_lock():
    """Reserve one of the bounded, cross-process extraction slots."""
    for slot in range(MAX_CONCURRENT_EXTRACTIONS):
        lock_file = f"{LOCK_FILE_PREFIX}{slot}.lock"
        token = uuid.uuid4().hex
        try:
            descriptor = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                with open(lock_file, "r", encoding="utf-8") as existing:
                    owner_pid = int(existing.readline().strip())
                try:
                    os.kill(owner_pid, 0)
                except PermissionError:
                    continue
                except OSError:
                    os.remove(lock_file)
                    descriptor = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                else:
                    continue
            except (OSError, ValueError):
                # An unreadable or concurrently claimed slot is treated as busy.
                continue
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as lock:
                lock.write(f"{os.getpid()}\n{token}\n")
        except OSError:
            try:
                os.remove(lock_file)
            except OSError:
                pass
            log.exception("[Lock] Failed to write extraction slot.")
            return None
        return lock_file, token
    return None


def _release_extraction_lock(lease):
    """Release a slot only if it is still owned by this task."""
    if not lease:
        return
    lock_file, token = lease
    try:
        with open(lock_file, "r", encoding="utf-8") as lock:
            lock.readline()
            current_token = lock.readline().strip()
        if current_token == token:
            os.remove(lock_file)
    except FileNotFoundError:
        pass
    except OSError:
        log.exception("[Lock] Could not release extraction slot %s.", lock_file)


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
    """Read shared deduplication files without racing another task's writes."""
    with _shared_data_lock():
        return _load_seen_data()


def _load_seen_data():
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
        with _shared_data_lock():
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
    new_df = new_df[cols].drop_duplicates(subset=["Email ID"], keep="first")
    with _shared_data_lock():
        file_is_empty = (
            not os.path.exists(MASTER_EMAIL_FILE)
            or os.path.getsize(MASTER_EMAIL_FILE) == 0
        )
        if not file_is_empty:
            existing = pd.read_csv(MASTER_EMAIL_FILE, encoding="utf-8-sig")
            if "Email ID" in existing.columns:
                seen = set(existing["Email ID"].dropna().str.lower())
                new_df = new_df[
                    ~new_df["Email ID"].str.lower().isin(seen)
                ].drop_duplicates(subset=["Email ID"], keep="first")
        if new_df.empty:
            return
        new_df.to_csv(
            MASTER_EMAIL_FILE,
            mode="a",
            index=False,
            header=file_is_empty,
            encoding="utf-8-sig",
        )


def create_excel_workbook(rows):
    """Create an Excel workbook in memory from contact rows."""
    if not rows:
        return None

    df = pd.DataFrame(rows, columns=["Paper Title", "Author Name", "Email ID"])
    workbook = io.BytesIO()
    df.to_excel(workbook, index=False)
    workbook.seek(0)
    return workbook


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
# Dispatch Mapping: active source connectors aligned with the upstream registry.
# -----------------------------------------------------------
SOURCE_FETCHERS = {
    "plos":       ("PLOS", fetch_plos_papers),
    "europepmc":  ("Europe PMC", fetch_europepmc_papers),
    "elife":      ("eLife", fetch_elife_papers),
    "openalex":   ("OpenAlex", fetch_openalex_papers),
    "arxiv":      ("arXiv", fetch_arxiv_papers),
    "biorxiv":    ("bioRxiv / medRxiv", fetch_biorxiv_papers),
    "crossref":   ("Crossref", fetch_crossref_papers),
    "pubmed":     ("PubMed / NCBI", fetch_pubmed_papers),
    "frontiers":  ("Frontiers", fetch_frontiers_papers),
    "aha":        ("AHA Journals", fetch_aha_papers),
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
def _run_extraction_task(task_id, source_sites, topic, max_papers, filters=None, lock_lease=None):
    """
    Runs extraction across one or multiple repositories.
    Strictly yields rows with: 'Paper Title', 'Author Name', 'Email ID'.
    Completely excludes DOI, PDF File Name, and Source Journal from output.
    """
    filters = dict(filters or {})
    country_cache = {}
    selected_countries = filters.get("countries", [])
    if selected_countries and country_codes(selected_countries) == set(COUNTRY_CODES.values()):
        log.info(
            f"[Task {task_id[:8]}] All supported countries selected; "
            "searching worldwide without per-author country lookups."
        )
        selected_countries = []
        filters["countries"] = []
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

    # Keep selected connectors first, then use the remaining distinct
    # connectors only as failover candidates.
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
        per_source_max = min(25, max(1, math.ceil(max_papers * 0.5)))

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
                return min(max(requested_limit, 25), 1000)
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
        source_failed = set()
        source_empty_pages = {s: 0 for s in source_sites}
        source_no_contact_pages = {s: 0 for s in source_sites}
        source_duplicate_pages = {s: 0 for s in source_sites}
        source_contact_yields = {s: 0 for s in source_sites}
        seen_paper_keys = set()
        total_downloaded = 0
        doi_skipped_count = 0
        papers_searched = 0
        pdfs_downloaded = 0
        pdfs_parsed = 0
        pending_pdf_cleanup = []

        def _cleanup_processed_pdfs():
            while pending_pdf_cleanup:
                pdf_path = pending_pdf_cleanup.pop(0)
                try:
                    os.remove(pdf_path)
                except FileNotFoundError:
                    pass
                except OSError as cleanup_error:
                    log.warning(
                        f"[Task {short_id}] Could not remove processed PDF "
                        f"{pdf_path}: {cleanup_error}"
                    )

        def _queue_contact_pairs(pairs, paper_title, allowed_authors):
            added = 0
            for author, email in pairs:
                if len(rows) + len(pending_rows) >= max_papers:
                    break
                clean_email = clean_and_validate_email(email)
                if (
                    not clean_email or clean_email in seen_emails
                    or not contact_allowed(author, allowed_authors)
                    or not is_valid_author(author) or not is_valid_title(paper_title)
                ):
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
                added += 1
            return added

        def _process_item(item):
            nonlocal doi_skipped_count, papers_searched, pdfs_downloaded, pdfs_parsed
            if len(rows) + len(pending_rows) >= max_papers:
                return True
            papers_searched += 1
            file_path = item.get("file_path")

            allowed_authors = eligible_authors(item, selected_countries, country_cache)
            if allowed_authors == set():
                if file_path:
                    pending_pdf_cleanup.append(file_path)
                    _cleanup_processed_pdfs()
                return False
            paper_title = (item.get("title") or "Untitled Paper").strip()
            item_doi_raw = item.get("doi", "")
            item_doi = normalise_doi(item_doi_raw)

            # Deduplicate by DOI if available
            if item_doi and item_doi in seen_dois:
                doi_skipped_count += 1
                if file_path:
                    pending_pdf_cleanup.append(file_path)
                    _cleanup_processed_pdfs()
                return False

            paper_key = item_doi or paper_title.casefold()
            if paper_key in seen_paper_keys:
                if file_path:
                    pending_pdf_cleanup.append(file_path)
                    _cleanup_processed_pdfs()
                return False
            seen_paper_keys.add(paper_key)

            if item_doi:
                if not selected_countries:
                    _record_attempted_doi(item_doi)
                seen_dois.add(item_doi)

            metadata_emails = item.get("emails", [])
            if isinstance(metadata_emails, str):
                metadata_emails = [metadata_emails]
            elif not isinstance(metadata_emails, (list, tuple)):
                metadata_emails = []
            metadata_pairs = (
                (author, email)
                for email in metadata_emails
                if isinstance(email, str)
                for author in [resolve_email_author(item, email)]
                if author
            )
            metadata_contacts = _queue_contact_pairs(
                metadata_pairs, paper_title, allowed_authors
            )

            # Prefer emails that the source can link to an author; parse a PDF
            # only when metadata doesn't yield a valid contact.
            if metadata_contacts:
                item.pop("pdf_bytes", None)
                if file_path:
                    pending_pdf_cleanup.append(file_path)
                    _cleanup_processed_pdfs()
            else:
                pdf_bytes = item.pop("pdf_bytes", None)
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
                    except OSError as read_error:
                        log.warning(
                            f"[Task {short_id}] Could not read downloaded PDF "
                            f"{file_path}: {read_error}"
                        )
                if is_pdf:
                    pdfs_downloaded += 1
                    try:
                        pairs = extract_author_email_pairs(pdf_bytes, item.get("authors", []))
                        _queue_contact_pairs(pairs, paper_title, allowed_authors)
                    finally:
                        if file_path:
                            pending_pdf_cleanup.append(file_path)
                        pdfs_parsed += 1
                        if pdfs_parsed % 2 == 0:
                            _cleanup_processed_pdfs()
                elif file_path:
                    pending_pdf_cleanup.append(file_path)
                    _cleanup_processed_pdfs()

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
            fetch_started = time.monotonic()
            try:
                res = s_func(topic, per_source_max, t_dir, filters=filters)
            except Exception:
                log.info(
                    f"[Task {short_id}] {s_label} request failed after "
                    f"{time.monotonic() - fetch_started:.1f}s."
                )
                raise
            log.info(
                f"[Task {short_id}] {s_label} returned {len(res or [])} records "
                f"in {time.monotonic() - fetch_started:.1f}s."
            )
            return s_idx, s_key, s_label, res

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
                    source_failed.add(source_key)
                    source_exhausted.add(source_key)
                    log.error(
                        f"[Task {short_id}] Source {source_key} failed; "
                        f"switching to the next source: {ex}"
                    )
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

                new_contacts = len(rows) + len(pending_rows) - current_found
                source_contact_yields[source_key] += new_contacts
                if new_contacts <= 0:
                    source_no_contact_pages[source_key] += 1
                    if source_no_contact_pages[source_key] >= 3:
                        source_exhausted.add(source_key)
                else:
                    source_no_contact_pages[source_key] = 0
                    log.info(
                        f"[Task {short_id}] {source_label} yielded "
                        f"{new_contacts} verified contacts; prioritizing it for top-up."
                    )
                _flush_pending()
                task_update(
                    task_id, "running", contacts_found=len(rows) + len(pending_rows),
                    papers_searched=papers_searched, pdfs_downloaded=pdfs_downloaded,
                    pdfs_parsed=pdfs_parsed, sources_remaining=n_sources - completed_sources,
                )
                if len(rows) >= max_papers:
                    log.info(f"[Task {short_id}] Target limit of {max_papers} verified contacts achieved! Stopping early.")
                    break
                if new_contacts > 0:
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
            exhausted_sources = set(source_exhausted) | set(source_failed)
            round_idx = 0
            while True:
                if len(rows) >= max_papers:
                    break

                active_in_round = sorted(
                    (k for k in active_top_up_keys if k not in exhausted_sources),
                    key=lambda key: -source_contact_yields.get(key, 0),
                )
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

                    try:
                        extra_downloaded = top_fetcher(
                            topic, top_quota, topic_pdf_dir,
                            filters=filters, offset=current_offset
                        )
                    except TypeError:
                        try:
                            extra_downloaded = top_fetcher(
                                topic, top_quota, topic_pdf_dir, filters=filters
                            )
                        except Exception as ex:
                            log.warning(
                                f"[Task {short_id}] Top-up failed for {top_key}; "
                                f"switching sources: {ex}"
                            )
                            source_failed.add(top_key)
                            exhausted_sources.add(top_key)
                            continue
                    except Exception as ex:
                        log.warning(
                            f"[Task {short_id}] Top-up failed for {top_key}; "
                            f"switching sources: {ex}"
                        )
                        source_failed.add(top_key)
                        exhausted_sources.add(top_key)
                        continue

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
                    contacts_before_page = len(rows) + len(pending_rows)

                    for item in extra_downloaded:
                        if _process_item(item):
                            _flush_pending()
                            break

                    _flush_pending()
                    page_contact_yield = max(
                        0, len(rows) + len(pending_rows) - contacts_before_page
                    )
                    source_contact_yields[top_key] += page_contact_yield
                    if page_contact_yield <= 0:
                        source_no_contact_pages[top_key] = (
                            source_no_contact_pages.get(top_key, 0) + 1
                        )
                        if source_no_contact_pages[top_key] >= 3:
                            exhausted_sources.add(top_key)
                    else:
                        source_no_contact_pages[top_key] = 0
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

        log.info(f"[Task {short_id}] Extraction complete: {len(rows)}/{max_papers} verified contacts")

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
                message = f"Source exhaustion: found 0 of {max_papers} requested unique verified contacts for '{topic}'."
            task_update(task_id, "done", "", result={
                "success": False,
                "message": message,
                "data": [],
                "file": None,
                "download_file": None,
                "requested_count": max_papers,
                "total_records": 0,
                "shortfall": max_papers,
            }, percentage=100, contacts_found=0)
            return

        total_found = len(rows)
        task_update(
            task_id, "running",
            f"Finalizing {total_found}/{max_papers} verified contacts...",
            percentage=95, contacts_found=total_found
        )
        log.info(f"[Task {short_id}] Done. {len(rows)} verified records extracted.")
        task_update(task_id, "done", "", result={
            "success": len(rows) == max_papers,
            "total_records": len(rows),
            "requested_count": max_papers,
            "shortfall": max(0, max_papers - len(rows)),
            "message": (f"Reached the requested {max_papers} unique verified contacts." if len(rows) == max_papers else f"Source exhaustion: found {len(rows)} of {max_papers} requested unique verified contacts."),
            "download_file": None,
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
        _cleanup_processed_pdfs()
        for pdf_dir in task_pdf_dirs:
            try:
                for filename in os.listdir(pdf_dir):
                    if filename.lower().endswith(".pdf"):
                        pdf_path = os.path.join(pdf_dir, filename)
                        try:
                            os.remove(pdf_path)
                        except OSError as cleanup_error:
                            log.warning(
                                f"[Task {short_id}] Could not remove temporary PDF "
                                f"{pdf_path}: {cleanup_error}"
                            )
                os.rmdir(pdf_dir)
            except OSError as cleanup_error:
                if os.path.isdir(pdf_dir):
                    log.warning(
                        f"[Task {short_id}] Could not remove temporary PDF directory "
                        f"{pdf_dir}: {cleanup_error}"
                    )
        _release_extraction_lock(lock_lease)
        _cleanup_stale_tasks()


# -----------------------------------------------------------
# Flask Routes
# -----------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html", countries=COUNTRY_CODES)


@app.route("/download/current", methods=["POST"])
def download_current_results():
    """Return the current search results as an in-memory Excel workbook."""
    payload = request.get_json(silent=True)
    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or not rows:
        return jsonify({"error": "There are no search results to export."}), 400
    if any(
        not isinstance(row, dict)
        or any(not isinstance(row.get(column), str) or not row[column].strip()
               for column in ("Paper Title", "Author Name", "Email ID"))
        for row in rows
    ):
        return jsonify({"error": "Search results must contain a title, author, and email for every row."}), 400

    workbook = create_excel_workbook(rows)
    return send_file(
        workbook,
        as_attachment=True,
        download_name="medscout_search_results.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.route("/download/all")
def download_all_contacts():
    """Export the complete saved contact collection as an in-memory workbook."""
    with _shared_data_lock():
        if not os.path.isfile(MASTER_EMAIL_FILE) or os.path.getsize(MASTER_EMAIL_FILE) == 0:
            return jsonify({"error": "There are no saved contacts to export yet."}), 404
        contacts = pd.read_csv(MASTER_EMAIL_FILE, encoding="utf-8-sig")

    columns = ["Paper Title", "Author Name", "Email ID"]
    if not all(column in contacts.columns for column in columns):
        log.error("[Export] Master contact CSV is missing required columns.")
        return jsonify({"error": "The saved contact data has an invalid format."}), 500
    rows = contacts[columns].fillna("").to_dict(orient="records")
    if not rows:
        return jsonify({"error": "There are no saved contacts to export yet."}), 404

    workbook = create_excel_workbook(rows)
    return send_file(
        workbook,
        as_attachment=True,
        download_name="medscout_all_contacts.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


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

    lock_lease = _acquire_extraction_lock()
    if not lock_lease:
        return jsonify({
            "error": f"All {MAX_CONCURRENT_EXTRACTIONS} extraction slots are busy. Please try again shortly."
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
        args=(task_id, valid_sources, topic, max_papers, filters, lock_lease),
        daemon=True,
    )
    try:
        thread.start()
    except RuntimeError:
        _release_extraction_lock(lock_lease)
        task_update(task_id, "error", "Could not start extraction worker.")
        log.exception("[Task %s] Could not start extraction worker.", task_id[:8])
        return jsonify({"error": "Could not start extraction worker."}), 500
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


if __name__ == "__main__":
    app.run(debug=True, port=5000)
