import os
import re
import logging
import requests

from .http_client import POLITE_USER_AGENT, polite_jitter
from .country_filter import resolve_email_author

log = logging.getLogger("extraction.europepmc")

# Country display name → EuropePMC COUNTRY field values
# EuropePMC uses full English country names in its query syntax
_COUNTRY_NAMES = {
    "USA":          "United States",
    "UK":           "United Kingdom",
    "Italy":        "Italy",
    "Spain":        "Spain",
    "Romania":      "Romania",
    "France":       "France",
    "Brazil":       "Brazil",
    "Germany":      "Germany",
    "Australia":    "Australia",
    "Canada":       "Canada",
    "Mexico":       "Mexico",
    "Saudi Arabia": "Saudi Arabia",
    "Egypt":        "Egypt",
}


def fetch_europepmc_papers(topic, limit, target_dir, filters=None, page=1, offset=0, **kwargs):
    """
    Searches and downloads Open Access PDFs exclusively from Europe PMC.
    Supports page and offset pagination.

    filters (dict, optional):
        countries     (list[str]): UI country names → added as COUNTRY: clauses
        year_from     (int|None):  earliest publication year
        year_to       (int|None):  latest publication year
        article_types (list[str]): not supported by EuropePMC query — ignored
    """
    filters = filters or {}
    if offset and page == 1:
        page = max(1, (int(offset) // max(1, limit)) + 1)
    page = max(1, int(page))

    # --- Build EuropePMC query ---
    query_parts = [f'"{topic}"', "HAS_PDF:y", "OPEN_ACCESS:y"]

    # Year range — EuropePMC supports PUB_YEAR:[from TO to]
    year_from = filters.get("year_from")
    year_to   = filters.get("year_to")
    if year_from and year_to:
        query_parts.append(f"PUB_YEAR:[{year_from} TO {year_to}]")
    elif year_from:
        query_parts.append(f"PUB_YEAR:[{year_from} TO 2099]")
    elif year_to:
        query_parts.append(f"PUB_YEAR:[1900 TO {year_to}]")

    # Countries — build (COUNTRY:"X" OR COUNTRY:"Y") clause
    countries = filters.get("countries", [])
    mapped    = [_COUNTRY_NAMES[c] for c in countries if c in _COUNTRY_NAMES]
    if mapped:
        country_clause = " OR ".join(f'COUNTRY:"{c}"' for c in mapped)
        query_parts.append(f"({country_clause})")

    query = " AND ".join(query_parts)
    log.info(f"[EuropePMC] Query: {query!r} (page={page})")

    base_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    params = {
        "query":      query,
        "format":     "json",
        "pageSize":   min(max(limit, 25), 1000),
        "page":       page,
        "resultType": "core",
    }

    session = requests.Session()
    session.headers.update({
        "User-Agent": POLITE_USER_AGENT,
        "Accept": "application/json",
    })

    try:
        resp = session.get(base_url, params=params, timeout=30)
        if resp.status_code != 200:
            log.error(f"[EuropePMC] HTTP {resp.status_code}")
            return []
        results = resp.json().get("resultList", {}).get("result", [])
        log.info(f"[EuropePMC] Got {len(results)} candidates.")
    except Exception as e:
        log.error(f"[EuropePMC] API error: {e}")
        return []

    records = []
    saved = 0

    for item in results:
        if saved >= limit:
            break

        pmcid        = item.get("pmcid")
        doi          = item.get("doi", "N/A")
        title        = item.get("title", "Untitled").rstrip(".")
        author_string= item.get("authorString", "")
        author_list_obj = item.get("authorList", {})
        author_entries = (
            author_list_obj.get("author", [])
            if isinstance(author_list_obj, dict) else []
        )
        authors_meta = []
        author_affiliations = {}
        email_author_candidates = {}
        for author in author_entries:
            name = " ".join(
                part.strip()
                for part in (author.get("firstName", ""), author.get("lastName", ""))
                if part and part.strip()
            ) or author.get("fullName", "").strip()
            if name:
                authors_meta.append(name)
            details = author.get("authorAffiliationDetailsList", {})
            author_affs = (
                details.get("authorAffiliation", [])
                if isinstance(details, dict) else []
            )
            for aff_obj in author_affs:
                aff_str = aff_obj.get("affiliation", "")
                if name and aff_str:
                    author_affiliations.setdefault(name, []).append(aff_str)
                if name:
                    for email in re.findall(
                        r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+',
                        aff_str,
                    ):
                        clean_email = email.strip().rstrip(".").lower()
                        email_author_candidates.setdefault(clean_email, set()).add(name)
        email_authors = {
            email: next(iter(names))
            for email, names in email_author_candidates.items()
            if len(names) == 1
        }
        ambiguous_emails = [
            email for email, names in email_author_candidates.items()
            if len(names) > 1
        ]
        if not authors_meta:
            authors_meta = [a.strip() for a in author_string.split(",") if a.strip()]
        source_journal = item.get("journalTitle", "Europe PMC") or "Europe PMC"

        # 1. Pre-extract any emails present in author affiliations
        found_emails = []
        if isinstance(author_list_obj, dict):
            for auth in author_list_obj.get("author", []):
                aff_details = auth.get("authorAffiliationDetailsList", {})
                if isinstance(aff_details, dict):
                    for aff_obj in aff_details.get("authorAffiliation", []):
                        aff_str = aff_obj.get("affiliation", "")
                        for em in re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', aff_str):
                            clean = em.strip().rstrip(".").lower()
                            if clean not in found_emails:
                                found_emails.append(clean)
        gen_aff = item.get("affiliation", "")
        if gen_aff:
            for em in re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', gen_aff):
                clean = em.strip().rstrip(".").lower()
                if clean not in found_emails:
                    found_emails.append(clean)

        record = {
            "title": title,
            "authors": authors_meta,
            "doi": doi,
            "source_journal": source_journal,
            "emails": found_emails,
            "email_authors": email_authors,
            "ambiguous_emails": ambiguous_emails,
            "author_affiliations": author_affiliations,
        }

        # Use author-linked affiliation emails directly instead of downloading
        # and parsing a PDF when the source metadata is sufficient.
        if any(resolve_email_author(record, email) for email in found_emails):
            saved += 1
            records.append(record)
            polite_jitter()
            continue

        pdf_urls = []
        if pmcid:
            pdf_urls.append(f"https://europepmc.org/backend/ptpmcrender.fcgi?accid={pmcid}&blobtype=pdf")
            pdf_urls.append(f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/pdf/")

        if not pdf_urls:
            continue

        pdf_name  = f"europepmc_paper_{saved + 1}.pdf"
        file_path = os.path.join(target_dir, pdf_name)

        download_success = False
        for url in pdf_urls:
            try:
                pdf_resp = session.get(url, timeout=4, allow_redirects=True, headers={
                    "User-Agent": POLITE_USER_AGENT
                })
                if pdf_resp.status_code == 200 and (
                    pdf_resp.content.startswith(b"%PDF") or b"%PDF-" in pdf_resp.content[:1024]
                ):
                    with open(file_path, "wb") as f:
                        f.write(pdf_resp.content)
                    download_success = True
                    break
            except Exception as e:
                log.debug(f"[EuropePMC] Download failed ({url}): {e}")

        # Fall back to PDF parsing when metadata cannot identify an author.
        if download_success:
            saved += 1
            record["file_path"] = file_path
            record["pdf_name"] = pdf_name
            records.append(record)

        polite_jitter()

    return records
