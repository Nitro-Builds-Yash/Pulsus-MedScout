import os
import re
import logging
import requests
from .http_client import http_session

log = logging.getLogger("extraction.semanticscholar")

EMAIL_RE = re.compile(r'[a-zA-Z0-9_.+-]+@(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}')

def fetch_semanticscholar_papers(topic, limit=10, target_dir=None, filters=None):
    """
    Fetches papers from the Semantic Scholar Academic Graph API (200M+ research papers).
    Retrieves paper metadata, abstracts, authors, and open access PDF download links.
    """
    filters = filters or {}
    year_from = filters.get("year_from")
    year_to = filters.get("year_to")

    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")
    headers = {
        "User-Agent": "AcademicEmailExtractor/2.0 (Research Suite)"
    }
    if api_key:
        headers["x-api-key"] = api_key

    # Year range filter
    year_param = None
    if year_from and year_to:
        year_param = f"{year_from}-{year_to}"
    elif year_from:
        year_param = f"{year_from}-"
    elif year_to:
        year_param = f"-{year_to}"

    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": topic,
        "limit": min(limit, 100),
        "fields": "paperId,title,authors,abstract,year,externalIds,openAccessPdf"
    }
    if year_param:
        params["year"] = year_param

    try:
        resp = http_session.get(url, params=params, headers=headers, timeout=8)
        if resp.status_code == 429:
            log.warning("[SemanticScholar] Rate limited (HTTP 429). Skipping silently without blocking search.")
            return []
        elif resp.status_code != 200:
            log.info(f"[SemanticScholar] API HTTP {resp.status_code}. Skipping source.")
            return []

        data = resp.json()
        raw_papers = data.get("data", [])
        results = []

        for p in raw_papers:
            title = p.get("title", "Untitled Paper")
            authors_data = p.get("authors", [])
            authors = [a.get("name", "Author") for a in authors_data if a.get("name")]
            abstract = p.get("abstract") or ""

            # Check for emails inside abstract text
            found_emails = EMAIL_RE.findall(abstract)
            clean_emails = list({e.lower() for e in found_emails if not any(x in e.lower() for x in [".png", ".jpg", "example.com"])})

            ext_ids = p.get("externalIds") or {}
            doi = ext_ids.get("DOI")
            doi_url = f"https://doi.org/{doi}" if doi else f"https://www.semanticscholar.org/paper/{p.get('paperId')}"

            oa_pdf = p.get("openAccessPdf") or {}
            pdf_url = oa_pdf.get("url")

            file_path = None
            pdf_name = None
            if pdf_url and target_dir:
                candidate_name = f"semanticscholar_paper_{len(results) + 1}.pdf"
                candidate_path = os.path.join(target_dir, candidate_name)
                try:
                    pdf_resp = http_session.get(pdf_url, headers=headers, timeout=20, allow_redirects=True)
                    if pdf_resp.status_code == 200 and (
                        pdf_resp.content.startswith(b"%PDF") or b"%PDF-" in pdf_resp.content[:1024]
                    ):
                        with open(candidate_path, "wb") as f:
                            f.write(pdf_resp.content)
                        file_path = candidate_path
                        pdf_name = candidate_name
                except Exception as ex:
                    log.warning(f"[SemanticScholar] PDF download failed: {ex}")

            rec = {
                "source": "Semantic Scholar",
                "source_journal": "Semantic Scholar",
                "title": title,
                "authors": authors,
                "emails": clean_emails,
                "doi": doi_url,
            }
            if file_path:
                rec["file_path"] = file_path
                rec["pdf_name"] = pdf_name
            results.append(rec)

        return results

    except Exception as e:
        log.error(f"[SemanticScholar] Unexpected error: {e}", exc_info=True)
        return []
