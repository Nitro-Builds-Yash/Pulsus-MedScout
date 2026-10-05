import os
import re
import logging
import requests

log = logging.getLogger("extraction.crossref")


class _OpenAlexRateLimitError(RuntimeError):
    """Raised when OpenAlex blocks PDF-location lookups for this run."""


# --- Replace this with your email address ---
from .http_client import POLITE_USER_AGENT, RESEARCH_EMAIL, polite_jitter
CONTACT_EMAIL = RESEARCH_EMAIL

# Standardized Polite headers for API calls (Crossref Polite Pool)
API_HEADERS = {
    "User-Agent": POLITE_USER_AGENT
}

# Public repository identification for PDF downloads
PDF_HEADERS = {
    "User-Agent": POLITE_USER_AGENT,
    "Accept": "application/pdf,application/xhtml+xml,text/html,application/xml;q=0.9,*/*;q=0.8"
}

# Publishers that ALWAYS block automated PDF downloads.
PUBLISHER_BLOCKLIST = [
    "link.springer.com",
    "www.nature.com",
    "www.elsevier.com",
    "sciencedirect.com",
    "onlinelibrary.wiley.com",
    "academic.oup.com",
    "journals.sagepub.com",
    "www.tandfonline.com",
    "www.cell.com",
    "jamanetwork.com",
    "nejm.org",
    "bmj.com",
    "thelancet.com",
]

# UI country name → OpenAlex ISO code (used in post-fetch affiliation check)
from .country_filter import COUNTRY_CODES as _COUNTRY_CODES

# UI article type → Crossref type string
_TYPE_MAP = {
    "Article":          "journal-article",
    "Review":           "journal-article",
    "Systematic Review":"journal-article",
    "Brief Report":     "journal-article",
}


def _all_urls_blocked(urls):
    """
    Return True when EVERY URL in the list is from a known-blocked publisher.
    In that case we skip the paper entirely — no download will ever succeed.
    If even ONE URL is from a trusted/open host it's worth trying.
    """
    return all(
        any(blocked in url.lower() for blocked in PUBLISHER_BLOCKLIST)
        for url in urls
    )


def _download_pdf(url, file_path, timeout=12):
    """Download a PDF. Returns True on success, False on any failure."""
    try:
        polite_jitter()
        resp = requests.get(url, headers=PDF_HEADERS, timeout=timeout, allow_redirects=True)
        if resp.status_code == 429:
            raise RuntimeError("PDF host rate limit reached during Crossref download.")
        if resp.status_code == 200 and (
            resp.content.startswith(b"%PDF") or b"%PDF-" in resp.content[:1024]
        ):
            with open(file_path, "wb") as f:
                f.write(resp.content)
            return True
    except RuntimeError:
        raise
    except Exception as e:
        log.warning(f"    [PDF] Download failed: {e}")
    return False


def _query_openalex_chunk(batch):
    """Send exactly one chunk (≤50 DOIs) to OpenAlex. Returns {doi: [ordered_urls]}."""
    TRUSTED_HOSTS = [
        "arxiv.org", "europepmc.org", "biorxiv.org", "medrxiv.org",
        "ncbi.nlm.nih.gov", "plos.org", "mdpi.com", "frontiersin.org",
    ]
    result = {}
    if not batch:
        return result

    filter_str = "doi:" + "|".join(batch)
    try:
        polite_jitter()
        resp = requests.get(
            "https://api.openalex.org/works",
            params={
                "filter": filter_str,
                "select": "doi,best_oa_location,locations",
                "per-page": 50,
                "mailto": CONTACT_EMAIL
            },
            headers=API_HEADERS,
            timeout=20
        )
        if resp.status_code == 429:
            raise _OpenAlexRateLimitError(
                f"OpenAlex rate limit reached: {resp.text[:150]}"
            )
        if resp.status_code != 200:
            raise RuntimeError(
                f"OpenAlex PDF lookup failed with HTTP {resp.status_code}: "
                f"{resp.text[:150]}"
            )

        for work in resp.json().get("results", []):
            raw_doi = (work.get("doi") or "").replace("https://doi.org/", "").lower()
            if not raw_doi:
                continue

            # Collect ALL available PDF URLs
            all_pdf_urls = []
            best_oa = work.get("best_oa_location") or {}
            if best_oa.get("pdf_url"):
                all_pdf_urls.append(best_oa["pdf_url"])
            for loc in work.get("locations", []):
                url = loc.get("pdf_url")
                if url and url not in all_pdf_urls:
                    all_pdf_urls.append(url)

            if not all_pdf_urls:
                continue

            # Sort: trusted hosts first, publisher URLs last
            ordered_urls = []
            for trusted_host in TRUSTED_HOSTS:
                for url in all_pdf_urls:
                    if trusted_host in url.lower() and url not in ordered_urls:
                        ordered_urls.append(url)
            for url in all_pdf_urls:
                if url not in ordered_urls:
                    ordered_urls.append(url)

            result[raw_doi] = ordered_urls

    except _OpenAlexRateLimitError:
        raise
    except Exception as e:
        log.error(f"  [OpenAlex batch] Error: {e}")
        raise

    return result


def _batch_resolve_pdf_urls(dois):
    """
    Resolve open-access PDF URLs for any number of DOIs via OpenAlex.
    automatically splits into chunks of 50 (API limit).

    Returns {doi_lowercase: [ordered_url_list]} for every DOI that has
    at least one open-access PDF location.
    """
    doi_to_pdf = {}
    if not dois:
        return doi_to_pdf

    chunks = [dois[i:i + 50] for i in range(0, len(dois), 50)]
    for idx, chunk in enumerate(chunks):
        try:
            chunk_result = _query_openalex_chunk(chunk)
        except _OpenAlexRateLimitError as e:
            log.warning(f"  [OpenAlex] Stopping PDF lookup for this search: {e}")
            return None
        doi_to_pdf.update(chunk_result)
        log.info(f"  [OpenAlex] Chunk {idx+1}/{len(chunks)}: resolved {len(chunk_result)} PDFs.")

    return doi_to_pdf


def fetch_crossref_papers(topic, limit, target_dir, filters=None, offset=0, **kwargs):
    """
    Two-phase approach for maximum PDF coverage.
    Supports offset pagination.

    filters (dict, optional):
        year_from     (int|None):  applied via Crossref 'from-pub-date' filter
        year_to       (int|None):  applied via Crossref 'until-pub-date' filter
        countries     (list[str]): post-fetch check on OpenAlex affiliation country codes
        article_types (list[str]): ignored (Crossref only returns journal-articles anyway)
    """
    filters      = filters or {}
    year_from    = filters.get("year_from")
    year_to      = filters.get("year_to")
    countries    = filters.get("countries", [])
    iso_codes    = {_COUNTRY_CODES[c] for c in countries if c in _COUNTRY_CODES}

    # Build Crossref filter string — year range applied natively
    crossref_filter_parts = ["type:journal-article"]
    if year_from:
        crossref_filter_parts.append(f"from-pub-date:{year_from}-01-01")
    if year_to:
        crossref_filter_parts.append(f"until-pub-date:{year_to}-12-31")
    crossref_filter = ",".join(crossref_filter_parts)
    log.info(f"[Crossref] Crossref filter: {crossref_filter!r}")
    if iso_codes:
        log.info(f"[Crossref] Post-fetch country filter: {iso_codes}")

    offset = max(0, int(offset))
    log.info(f"[Crossref] Searching for: '{topic}' (start offset={offset}, targeting {limit} papers)...")

    base_url   = "https://api.crossref.org/works"
    records    = []
    saved_count= 0
    max_offset = max(2000, offset + limit * 3)

    while saved_count < limit and offset < max_offset:
        params = {
            "query":   topic,
            "filter":  crossref_filter,
            "select":  "DOI,title,author,container-title,publisher",
            "rows":    100,
            "offset":  offset,
            "mailto":  CONTACT_EMAIL
        }

        try:
            polite_jitter()
            resp = requests.get(base_url, params=params, headers=API_HEADERS, timeout=15)
            if resp.status_code == 429:
                raise RuntimeError(
                    f"Crossref rate limit reached at offset {offset}; "
                    "skipping this source."
                )
            if resp.status_code != 200:
                raise RuntimeError(
                    f"Crossref search failed at offset {offset}: HTTP {resp.status_code}"
                )
            items = resp.json().get("message", {}).get("items", [])
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Crossref API error at offset {offset}: {e}") from e

        if not items:
            log.info(f"[Crossref] No more candidates found at offset {offset}.")
            break

        log.info(f"\n[Crossref] --- Page {offset//100 + 1}: Found {len(items)} candidates ---")

        # --- PHASE 2: Batch-resolve PDF URLs via ONE OpenAlex call ---
        all_dois = [item.get("DOI", "") for item in items if item.get("DOI")]
        log.info(f"[Crossref] Batch-resolving PDF URLs for {len(all_dois)} DOIs via OpenAlex...")
        doi_to_pdf = _batch_resolve_pdf_urls(all_dois)
        if doi_to_pdf is None:
            raise _OpenAlexRateLimitError(
                "OpenAlex PDF lookup was rate-limited; skipping Crossref so other sources can run."
            )
        log.info(f"[Crossref] Found open-access PDFs for {len(doi_to_pdf)} / {len(all_dois)} papers in this chunk.")

        for item in items:
            if saved_count >= limit:
                break

            doi = item.get("DOI", "N/A")
            if not doi or doi == "N/A":
                continue

            # Get the priority-ordered URL list for this DOI
            pdf_urls = doi_to_pdf.get(doi.lower())
            if not pdf_urls:
                continue   # No open-access PDF known for this paper

            titles = item.get("title", ["Untitled"])
            title = titles[0] if titles else "Untitled"

            # Author names
            authors_meta = []
            for auth in item.get("author", []):
                given = auth.get("given", "")
                family = auth.get("family", "")
                full_name = f"{given} {family}".strip()
                if full_name:
                    authors_meta.append(full_name)

            # Real journal name
            container_titles = item.get("container-title", [])
            publisher = item.get("publisher", "")
            if container_titles and container_titles[0].strip():
                source_journal = container_titles[0].strip()
            elif publisher.strip():
                source_journal = publisher.strip()
            else:
                source_journal = "Crossref"

            pdf_name = f"crossref_paper_{saved_count + 1}.pdf"
            file_path = os.path.join(target_dir, pdf_name)

            # Sanitise title for logging: collapse Unicode whitespace to plain space
            safe_title = re.sub(r'[\u2000-\u200f\u2028\u2029\u00a0]', ' ', title)
            log.info(
                f"  [Crossref] ({saved_count + 1}/{limit}) "
                f"[{source_journal[:25]}] {safe_title[:45]}..."
            )

            # Fast-skip: if every URL is from a known-blocked publisher,
            # don't waste 12+ seconds on connection timeouts — move to next candidate.
            if _all_urls_blocked(pdf_urls):
                log.info(f"    Skipped (all URLs from blocked publishers).")
                continue

            # Try each URL in priority order (trusted hosts first, publisher as fallback)
            success = False
            for attempt_url in pdf_urls:
                host_label = (
                    "trusted" if any(
                        h in attempt_url
                        for h in ["arxiv", "europepmc", "biorxiv", "medrxiv",
                                  "ncbi", "plos", "mdpi", "frontiersin"]
                    ) else "publisher"
                )
                log.info(f"    Trying [{host_label}]: {attempt_url[:70]}")
                success = _download_pdf(attempt_url, file_path)
                if success:
                    log.info(f"    Downloaded OK.")
                    break
                else:
                    log.info(f"    Failed, trying next URL...")

            if success:
                saved_count += 1
                records.append({
                    "file_path": file_path,
                    "pdf_name": pdf_name,
                    "title": title,
                    "authors": authors_meta,
                    "doi": doi,
                    "source_journal": source_journal
                })
            else:
                log.warning(f"    All URLs failed for this paper — skipping.")

        # Move to next page of candidates
        offset += 100

    log.info(f"\n[Crossref] Done. Successfully downloaded {saved_count} PDFs total.")
    return records
