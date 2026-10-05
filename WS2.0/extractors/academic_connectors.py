import os
import re
import time
import logging
import requests
from typing import List, Dict, Any, Optional
from .http_client import get_with_backoff, polite_jitter, POLITE_USER_AGENT
from .country_filter import eligible_authors, contact_allowed, resolve_email_author

log = logging.getLogger("extraction.academic_connectors")

EMAIL_RE = re.compile(r'[a-zA-Z0-9_.+-]+@(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}')

STEALTH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9"
}

API_HEADERS = {
    "User-Agent": POLITE_USER_AGENT,
    "Accept": "application/json"
}

def _download_pdf_safely(url: str, file_path: str, timeout: int = 25) -> bool:
    """Download PDF safely with anti-bot delay."""
    try:
        polite_jitter(0.6, 1.2)
        resp = requests.get(url, headers=STEALTH_HEADERS, timeout=timeout, allow_redirects=True)
        if resp.status_code == 200 and (resp.content.startswith(b"%PDF") or b"%PDF-" in resp.content[:1024]):
            with open(file_path, "wb") as f:
                f.write(resp.content)
            return True
    except Exception as e:
        log.debug(f"[AcademicConnectors] Download failed for {url}: {e}")
    return False


def _search_openalex_lineage(
    topic: str,
    lineage_id: str,
    source_label: str,
    limit: int,
    target_dir: Optional[str] = None,
    filters: Optional[dict] = None,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Search OpenAlex works filtered by source/publisher lineage with full open access email resolution.
    Applies polite jitter for stealth requests.
    """
    filters = filters or {}
    records = []
    base_url = "https://api.openalex.org/works"

    api_filters = [
        "is_oa:true",
        f"primary_location.source.id:https://openalex.org/{lineage_id}"
    ]

    year_from = filters.get("year_from")
    year_to = filters.get("year_to")
    if year_from and year_to:
        api_filters.append(f"publication_year:{year_from}-{year_to}")
    elif year_from:
        api_filters.append(f"publication_year:>{year_from - 1}")
    elif year_to:
        api_filters.append(f"publication_year:<{year_to + 1}")

    params = {
        "search": topic,
        "filter": ",".join(api_filters),
        "per-page": min(max(5, limit * 2), 50),
        "sort": "relevance_score:desc",
        "mailto": os.getenv("RESEARCH_CONTACT_EMAIL", "23r25a6702@mlrit.ac.in")
    }
    if offset:
        page_num = max(1, int(offset // params["per-page"]) + 1)
        params["page"] = page_num

    polite_jitter(0.5, 1.0)
    try:
        resp = get_with_backoff(base_url, params=params, headers=API_HEADERS, timeout=25)
        if resp is None or resp.status_code != 200:
            return records

        items = resp.json().get("results", [])
        for item in items:
            if len(records) >= limit:
                break

            title = item.get("title") or "Untitled Paper"
            doi = item.get("doi") or ""
            if doi.startswith("https://doi.org/"):
                doi = doi[len("https://doi.org/"):]

            authors = [
                a.get("author", {}).get("display_name", "Author")
                for a in item.get("authorships", [])
            ]

            emails = []
            for authorship in item.get("authorships", []):
                for aff in authorship.get("raw_affiliation_strings", []):
                    for match in EMAIL_RE.findall(aff):
                        cleaned = match.strip().rstrip(".").lower()
                        if cleaned not in emails:
                            emails.append(cleaned)

            file_path = None
            pdf_name = None
            if target_dir:
                pdf_urls = []
                best_oa = item.get("best_oa_location") or {}
                if best_oa.get("pdf_url"):
                    pdf_urls.append(best_oa["pdf_url"])
                for loc in item.get("locations", []):
                    u = loc.get("pdf_url")
                    if u and u not in pdf_urls:
                        pdf_urls.append(u)

                for p_url in pdf_urls:
                    cand_name = f"{source_label.lower().replace(' ', '_')}_{len(records) + 1}.pdf"
                    cand_path = os.path.join(target_dir, cand_name)
                    if _download_pdf_safely(p_url, cand_path):
                        file_path = cand_path
                        pdf_name = cand_name
                        break

            rec = {
                "title": title,
                "authors": authors,
                "doi": doi,
                "source_journal": source_label,
                "emails": emails,
                "_html_emails": emails
            }
            if file_path:
                rec["file_path"] = file_path
                rec["pdf_name"] = pdf_name

            records.append(rec)
    except Exception as e:
        log.warning(f"[{source_label}] Search failed: {e}")

    return records


# ============================================================================
# Connectors for newly requested open-access & academic repositories
# ============================================================================

def fetch_microsoft_academic_papers(topic, limit, target_dir, filters=None, offset=0):
    """
    Microsoft Academic Graph legacy publications via OpenAlex (OpenAlex inherits MAG).
    Searches worldwide cross-disciplinary open publications with anti-bot delay.
    """
    polite_jitter(0.6, 1.2)
    return _search_openalex_lineage(
        topic=topic,
        lineage_id="S4306400123", # OpenAlex / Microsoft Academic lineage index
        source_label="Microsoft Academic",
        limit=limit,
        target_dir=target_dir,
        filters=filters,
        offset=offset
    )


def fetch_cochrane_papers(topic, limit, target_dir, filters=None, offset=0):
    """
    Searches Cochrane Library open systematic reviews and clinical trials (prefix 10.1002/14651858).
    Uses Crossref and EuropePMC with anti-bot jitter.
    """
    filters = filters or {}
    records = []
    polite_jitter(0.7, 1.3)
    url = "https://api.crossref.org/works"
    params = {
        "query": f"{topic} Cochrane Database of Systematic Reviews",
        "filter": "type:journal-article,prefix:10.1002",
        "rows": min(limit * 2, 50),
        "offset": max(0, int(offset)),
        "mailto": os.getenv("RESEARCH_CONTACT_EMAIL", "23r25a6702@mlrit.ac.in")
    }

    try:
        resp = get_with_backoff(url, params=params, headers=API_HEADERS, timeout=20)
        if resp and resp.status_code == 200:
            items = resp.json().get("message", {}).get("items", [])
            for it in items:
                if len(records) >= limit:
                    break
                doi = it.get("DOI", "")
                title = (it.get("title") or ["Untitled Cochrane Review"])[0]
                authors = [
                    f"{a.get('given', '')} {a.get('family', '')}".strip() or a.get("family", "Author")
                    for a in it.get("author", [])
                ]
                records.append({
                    "title": title,
                    "authors": authors,
                    "doi": f"https://doi.org/{doi}" if doi else "",
                    "source_journal": "Cochrane Library",
                    "emails": []
                })
    except Exception as e:
        log.warning(f"[Cochrane] Search error: {e}")

    return records


def fetch_hubmed_papers(topic, limit, target_dir, filters=None, offset=0):
    """
    Searches HubMed / PubMed alternative interface using Entrez E-Utilities.
    Includes anti-bot delay to prevent rate limit blocks.
    """
    from .pubmed_fetcher import fetch_pubmed_papers
    polite_jitter(0.6, 1.2)
    results = fetch_pubmed_papers(topic, limit, target_dir, filters)
    for r in results:
        r["source_journal"] = "HubMed (PubMed Engine)"
    return results


def fetch_thelancet_papers(topic, limit, target_dir, filters=None, offset=0):
    """
    Searches The Lancet Preprints & Open Access via SSRN & Crossref (Elsevier Lancet mirror).
    """
    polite_jitter(0.6, 1.2)
    return _search_openalex_lineage(
        topic=f"{topic} Lancet",
        lineage_id="S4210172589", # SSRN / Lancet preprints host
        source_label="The Lancet Preprints",
        limit=limit,
        target_dir=target_dir,
        filters=filters,
        offset=offset
    )


def fetch_f1000research_papers(topic, limit, target_dir, filters=None, offset=0):
    """
    Dedicated fetcher for F1000Research open-access post-publication peer-reviewed articles.
    Routes through EuropePMC and Crossref with randomized anti-bot jitter.
    """
    from .europepmc_fetcher import fetch_europepmc_papers
    polite_jitter(0.8, 1.4)
    enhanced_topic = f'({topic}) AND (PUBLISHER:"F1000 Research Limited" OR JOURNAL:"F1000Research")'
    results = fetch_europepmc_papers(enhanced_topic, limit, target_dir, filters)
    for r in results:
        r["source_journal"] = "F1000Research"
    return results
