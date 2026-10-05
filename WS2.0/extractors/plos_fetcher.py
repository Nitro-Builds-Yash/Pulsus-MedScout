import os
import logging
import requests
from concurrent.futures import ThreadPoolExecutor

from .http_client import POLITE_USER_AGENT, polite_jitter

log = logging.getLogger("extraction.plos")

# PLOS article type labels → PLOS article_type values
_PLOS_TYPE_MAP = {
    "Article": "Research Article",
    "Research Article": "Research Article",
    "Case Reports": "Case Report",
    "Case Report": "Case Report",
    "Brief Reports": "Short Report",
    "Brief Report": "Short Report",
    "Systematic Reports": "Systematic Review",
    "Systematic Report": "Systematic Review",
    "Review": "Review",
    "Systematic Review": "Systematic Review",
}


def fetch_plos_papers(topic, limit, target_dir, filters=None, offset=0, **kwargs):
    """
    Searches PLOS and downloads real article PDFs for contact extraction.
    Supports offset pagination.
    """
    filters = filters or {}
    year_from = filters.get("year_from")
    year_to = filters.get("year_to")
    article_types = filters.get("article_types", [])

    os.makedirs(target_dir, exist_ok=True)

    # Build PLOS query — topic + optional article type filter
    query = f"title:{topic} OR abstract:{topic}"
    plos_types = list({_PLOS_TYPE_MAP[t] for t in article_types if t in _PLOS_TYPE_MAP})
    if plos_types:
        type_clause = " OR ".join(f'article_type:"{t}"' for t in plos_types)
        query = f"({query}) AND ({type_clause})"

    # Add year filter into the Solr query if specified
    if year_from and year_to:
        query += f" AND publication_date:[{year_from}-01-01T00:00:00Z TO {year_to}-12-31T23:59:59Z]"
    elif year_from:
        query += f" AND publication_date:[{year_from}-01-01T00:00:00Z TO *]"
    elif year_to:
        query += f" AND publication_date:[* TO {year_to}-12-31T23:59:59Z]"

    base_url = "https://api.plos.org/search"
    params = {
        "q": query,
        "fl": "id,title,author_display,publication_date",
        "wt": "json",
        "rows": limit,
        "start": max(0, int(offset)),
    }
    log.info(f"[PLOS] Query: {query!r} (start={offset})")

    try:
        resp = requests.get(base_url, params=params, timeout=25)
        if resp.status_code != 200:
            log.error(f"[PLOS] API HTTP {resp.status_code}")
            return []
        docs = resp.json().get("response", {}).get("docs", [])
    except Exception as e:
        log.error(f"[PLOS] API error: {e}")
        return []

    def _fetch_single_doc(idx_doc):
        i, doc = idx_doc
        doi = doc.get("id")
        title = doc.get("title", "Untitled")
        authors_meta = doc.get("author_display", [])
        pdf_name = f"plos_paper_{i}.pdf"
        file_path = os.path.join(target_dir, pdf_name)

        pdf_url = f"https://journals.plos.org/plosone/article/file?id={doi}&type=printable"
        try:
            polite_jitter()
            pdf_resp = requests.get(pdf_url, headers={"User-Agent": POLITE_USER_AGENT}, timeout=12)
            if pdf_resp.status_code == 200 and b"%PDF" in pdf_resp.content[:10]:
                with open(file_path, "wb") as f:
                    f.write(pdf_resp.content)
                return {
                    "file_path": file_path,
                    "pdf_name": pdf_name,
                    "title": title,
                    "authors": authors_meta,
                    "doi": doi,
                }
        except Exception as e:
            log.warning(f"[PLOS] PDF download failed for DOI {doi}: {e}")
        return None

    records = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        for result in executor.map(_fetch_single_doc, enumerate(docs, start=1)):
            if result:
                records.append(result)

    return records
