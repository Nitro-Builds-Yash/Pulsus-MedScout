import os
import logging
import requests
import xml.etree.ElementTree as ET

log = logging.getLogger("extraction.arxiv")

from .http_client import POLITE_USER_AGENT, polite_jitter

# arXiv Atom feed namespace
ATOM_NS = "http://www.w3.org/2005/Atom"

# Polite headers for API search
API_HEADERS = {
    "User-Agent": POLITE_USER_AGENT
}

# Public repository identification for PDF downloads
PDF_HEADERS = {
    "User-Agent": POLITE_USER_AGENT,
    "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8"
}


def _download_pdf(url, file_path, timeout=12):
    """Download the source PDF used for author/contact extraction."""
    try:
        polite_jitter()
        resp = requests.get(url, headers=PDF_HEADERS, timeout=timeout, allow_redirects=True)
        if resp.status_code == 429:
            raise RuntimeError("arXiv rate limit reached while downloading a PDF.")
        if resp.status_code == 200 and (
            resp.content.startswith(b"%PDF") or b"%PDF-" in resp.content[:1024]
        ):
            with open(file_path, "wb") as f:
                f.write(resp.content)
            return True
    except RuntimeError:
        raise
    except Exception as e:
        log.warning(f"  [arXiv] PDF download failed: {e}")
    return False


def fetch_arxiv_papers(topic, limit, target_dir, filters=None, offset=0, **kwargs):
    """
    Search arXiv and download PDFs for extraction.

    filters (dict, optional):
        year_from (int|None): adds submittedDate filter to the arXiv query
        year_to   (int|None): adds submittedDate filter to the arXiv query
        countries / article_types: not supported by arXiv — silently ignored
    """
    filters   = filters or {}
    year_from = filters.get("year_from")
    year_to   = filters.get("year_to")

    # Build search query — add submittedDate constraint if year filters present
    search_query = f"all:{topic}"
    if year_from or year_to:
        from_str = f"{year_from}0101" if year_from else "19900101"
        to_str   = f"{year_to}1231"   if year_to   else "20991231"
        search_query += f" AND submittedDate:[{from_str}000000 TO {to_str}235959]"

    base_url = "https://export.arxiv.org/api/query"
    params = {
        "search_query": search_query,
        "start":        max(0, int(offset)),
        "max_results":  limit,
        "sortBy":       "relevance",
        "sortOrder":    "descending",
    }

    log.info(f"[arXiv] Searching: {search_query!r} (start={offset}, up to {limit} papers)...")

    try:
        polite_jitter()
        resp = requests.get(base_url, params=params, headers=API_HEADERS, timeout=15)
        if resp.status_code != 200:
            raise RuntimeError(f"arXiv search failed with HTTP {resp.status_code}.")
        root = ET.fromstring(resp.text)
    except Exception as e:
        raise RuntimeError(f"arXiv search failed: {e}") from e

    entries = root.findall(f"{{{ATOM_NS}}}entry")
    log.info(f"[arXiv] Found {len(entries)} results. Downloading PDFs for extraction...")

    records = []

    for i, entry in enumerate(entries[:limit]):
        # --- Extract metadata ---
        title_el = entry.find(f"{{{ATOM_NS}}}title")
        title = title_el.text.strip().replace("\n", " ") if title_el is not None else "Untitled"

        id_el = entry.find(f"{{{ATOM_NS}}}id")
        arxiv_id_url = id_el.text.strip() if id_el is not None else ""

        # DOI — use arXiv ID URL as fallback
        doi = arxiv_id_url
        for link in entry.findall(f"{{{ATOM_NS}}}link"):
            if link.get("rel") == "related" and "doi" in link.get("href", ""):
                doi = link.get("href")
                break

        # Authors from API metadata
        authors_meta = []
        for author_el in entry.findall(f"{{{ATOM_NS}}}author"):
            name_el = author_el.find(f"{{{ATOM_NS}}}name")
            if name_el is not None and name_el.text:
                authors_meta.append(name_el.text.strip())

        # PDF link
        pdf_url = None
        for link in entry.findall(f"{{{ATOM_NS}}}link"):
            if link.get("title") == "pdf":
                pdf_url = link.get("href")
                break

        log.info(f"  [arXiv] ({i + 1}/{min(limit, len(entries))}) Downloading PDF: {title[:55]}...")

        pdf_name = f"arxiv_paper_{i + 1}.pdf"
        file_path = os.path.join(target_dir, pdf_name)
        if not pdf_url or not _download_pdf(pdf_url, file_path):
            log.info(f"  [arXiv] PDF unavailable; skipping paper.")
            continue

        records.append({
            "file_path": file_path,
            "pdf_name": pdf_name,
            "title": title,
            "authors": authors_meta,
            "doi": doi,
        })

    log.info(f"[arXiv] Done. Collected metadata for {len(records)} papers.")
    return records
