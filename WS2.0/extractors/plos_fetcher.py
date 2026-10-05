import os
import re
import logging
import requests
import xml.etree.ElementTree as ET
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


def _parse_plos_xml(xml_content):
    """
    Parses PLOS manuscript XML to extract emails, mapped corresponding authors,
    and institutional affiliations without needing PDF parsing.
    """
    emails = []
    email_authors = {}
    affiliations = []
    try:
        root = ET.fromstring(xml_content)
        corresp_author = None
        for contrib in root.iter("contrib"):
            if contrib.attrib.get("contrib-type") == "author":
                surname = contrib.findtext(".//surname") or ""
                given = contrib.findtext(".//given-names") or ""
                name = f"{given} {surname}".strip()
                for xref in contrib.findall(".//xref"):
                    if xref.attrib.get("ref-type") == "corresp":
                        corresp_author = name

        for aff in root.iter("aff"):
            aff_text = "".join(aff.itertext()).strip()
            if aff_text:
                affiliations.append(aff_text)

        for corresp in root.iter("corresp"):
            text = "".join(corresp.itertext())
            for e in re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", text):
                emails.append(e)
                if corresp_author:
                    email_authors[e] = corresp_author
    except Exception:
        pass
    return emails, email_authors, affiliations


def fetch_plos_papers(topic, limit, target_dir, filters=None, offset=0, **kwargs):
    """
    Searches PLOS and retrieves articles with direct XML metadata extraction
    and PDF fallback. Supports offset pagination.
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

        # 1. Try fast XML manuscript endpoint first
        xml_url = f"https://journals.plos.org/plosone/article/file?id={doi}&type=manuscript"
        try:
            polite_jitter()
            xml_resp = requests.get(xml_url, headers={"User-Agent": POLITE_USER_AGENT}, timeout=8)
            if xml_resp.status_code == 200 and len(xml_resp.content) > 500:
                emails, email_authors, affiliations = _parse_plos_xml(xml_resp.content)
                # Create stub file to satisfy file_path contract
                with open(file_path, "wb") as f:
                    f.write(b"%PDF-1.4\n%Stub\n")
                return {
                    "file_path": file_path,
                    "pdf_name": pdf_name,
                    "title": title,
                    "authors": authors_meta,
                    "doi": doi,
                    "emails": emails,
                    "email_authors": email_authors,
                    "affiliations": affiliations,
                }
        except Exception as e:
            log.debug(f"[PLOS] XML fetch failed for {doi}: {e}")

        # 2. Fallback to PDF download
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
