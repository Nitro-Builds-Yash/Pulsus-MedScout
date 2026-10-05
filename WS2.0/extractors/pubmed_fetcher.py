import os
import re
import logging
import requests
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus
from .http_client import http_session
from .country_filter import COUNTRY_CODES

log = logging.getLogger("extraction.pubmed")

EMAIL_RE = re.compile(r'[a-zA-Z0-9_.+-]+@(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}')

def fetch_pubmed_papers(topic, limit=10, target_dir=None, filters=None):
    """
    Fetches scientific papers from PubMed (NCBI Entrez API).
    Extracts paper titles, authors, and email addresses directly from
    author affiliation fields in PubMed XML (eFetch).
    """
    filters = filters or {}
    year_from = filters.get("year_from")
    year_to = filters.get("year_to")

    # Build Entrez Search Query
    query = "(" + topic + ")"
    countries = filters.get("countries", [])
    if countries:
        names = {"USA": "United States", "UK": "United Kingdom"}
        query += " AND (" + " OR ".join(f'"{names.get(c, c)}"[Affiliation]' for c in countries if c in COUNTRY_CODES) + ")"
    if year_from and year_to:
        query += f" AND {year_from}:{year_to}[dp]"
    elif year_from:
        query += f" AND {year_from}:3000[dp]"
    elif year_to:
        query += f" AND 1800:{year_to}[dp]"

    search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    search_params = {
        "db": "pubmed",
        "term": query,
        "retmax": min(limit, 1000),
        "retmode": "json",
        "sort": "pub_date"
    }

    try:
        resp = http_session.get(search_url, params=search_params, timeout=15)
        if resp.status_code != 200:
            log.error(f"[PubMed] Search failed with HTTP {resp.status_code}")
            return []
        data = resp.json()
        id_list = data.get("esearchresult", {}).get("idlist", [])
        if not id_list:
            log.info(f"[PubMed] No results found for query: {query}")
            return []

        # Fetch paper details using eFetch XML in chunks of 100
        fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        papers = []
        batch_size = 100

        for i in range(0, len(id_list), batch_size):
            chunk = id_list[i:i + batch_size]
            fetch_params = {
                "db": "pubmed",
                "id": ",".join(chunk),
                "retmode": "xml"
            }
            try:
                fetch_resp = http_session.get(fetch_url, params=fetch_params, timeout=30)
                if fetch_resp.status_code != 200:
                    log.error(f"[PubMed] eFetch batch failed with HTTP {fetch_resp.status_code}")
                    continue
                root = ET.fromstring(fetch_resp.content)
                for article in root.findall(".//PubmedArticle"):
                    pmid_elem = article.find(".//MedlineCitation/PMID")
                    pmid = pmid_elem.text if pmid_elem is not None else "N/A"

                    title_elem = article.find(".//ArticleTitle")
                    title = title_elem.text if title_elem is not None else "Untitled Paper"

                    # DOI extraction
                    doi = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                    for article_id in article.findall(".//ArticleIdList/ArticleId"):
                        if article_id.attrib.get("IdType") == "doi":
                            doi = f"https://doi.org/{article_id.text}"
                            break

                    authors = []
                    emails = []
                    affiliations = []
                    author_affiliations = {}
                    email_candidates = {}

                    for author_node in article.findall(".//AuthorList/Author"):
                        last_name = author_node.find("LastName")
                        fore_name = author_node.find("ForeName")
                        if last_name is not None and fore_name is not None:
                            name = f"{fore_name.text} {last_name.text}"
                        elif last_name is not None:
                            name = last_name.text
                        else:
                            name = "Author"
                        authors.append(name)

                        # Search affiliations for emails
                        for aff in author_node.findall(".//AffiliationInfo/Affiliation"):
                            aff_text = aff.text or ""
                            affiliations.append(aff_text)
                            author_affiliations.setdefault(name, []).append(aff_text)
                            found_emails = EMAIL_RE.findall(aff_text)
                            for e in found_emails:
                                clean_e = e.strip().rstrip(".").lower()
                                email_candidates.setdefault(clean_e, set()).add(name)
                                if clean_e not in emails and not any(x in clean_e for x in [".png", ".jpg", ".gif"]):
                                    emails.append(clean_e)

                    # Look across all general affiliation nodes if none found on author
                    if not emails:
                        for aff in article.findall(".//Affiliation"):
                            aff_text = aff.text or ""
                            found_emails = EMAIL_RE.findall(aff_text)
                            for e in found_emails:
                                clean_e = e.strip().rstrip(".").lower()
                                if clean_e not in emails:
                                    emails.append(clean_e)

                    papers.append({
                        "source": "PubMed",
                        "title": title,
                        "authors": authors,
                        "emails": list(set(emails)),
                        "doi": doi,
                        "pmid": pmid,
                        "affiliations": affiliations,
                        "author_affiliations": author_affiliations,
                        "email_authors": {email: next(iter(names)) for email, names in email_candidates.items() if len(names) == 1},
                        "ambiguous_emails": [email for email, names in email_candidates.items() if len(names) > 1]
                    })
            except Exception as ex:
                log.error(f"[PubMed] Failed to fetch or parse XML batch: {ex}")
                continue

        return papers

    except Exception as e:
        log.error(f"[PubMed] Unexpected error: {e}", exc_info=True)
        return []
