import os
import re
import time
import logging
import requests
from .http_client import http_session, POLITE_USER_AGENT, polite_jitter, get_with_backoff
from .openalex_fetcher import fetch_openalex_papers

log = logging.getLogger("extraction.preprints")

EMAIL_RE = re.compile(r'[a-zA-Z0-9_.+-]+@(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}')

REPOSITORY_HEADERS = {
    "User-Agent": POLITE_USER_AGENT,
    "Accept": "application/pdf,application/xhtml+xml,text/html,application/xml;q=0.9,*/*;q=0.8"
}

API_HEADERS = {
    "User-Agent": POLITE_USER_AGENT
}

# Prefix mappings for major preprint repositories from the image:
OSF_PREFIXES = [
    "10.31219",  # OSF Preprints (General)
    "10.31223",  # EarthArXiv
    "10.31234",  # PsyArXiv
    "10.31235",  # SocArXiv
    "10.31224",  # engrXiv
    "10.31220",  # AgriXiv / NutriXiv
    "10.31228",  # LawArXiv
    "10.31236",  # SportRxiv
    "10.31231",  # MindRxiv
    "10.31233",  # PaleorXiv
    "10.31227",  # INA-Rxiv
    "10.31222",  # BITSS / MetaArXiv
]

def _download_pdf(url, file_path, timeout=20):
    """Download PDF file safely."""
    try:
        polite_jitter()
        resp = get_with_backoff(url, headers=REPOSITORY_HEADERS, timeout=timeout)
        if resp.status_code == 200 and (resp.content.startswith(b"%PDF") or b"%PDF-" in resp.content[:1024]):
            with open(file_path, "wb") as f:
                f.write(resp.content)
            return True
    except Exception as e:
        log.debug(f"[Preprints] PDF download failed from {url}: {e}")
    return False

def _extract_osf_guid(doi):
    """Extract 5-character OSF GUID from DOI (e.g. 10.31234/osf.io/8cw3h_v2 -> 8cw3h)."""
    if not doi:
        return None
    m = re.search(r'osf\.io/([a-zA-Z0-9]{4,7})', doi)
    if m:
        return m.group(1)
    return None

def fetch_osf_papers(topic, limit=10, target_dir=None, filters=None, specific_prefix=None):
    """
    Fetches preprints from the Center for Open Science OSF Preprints network:
    Includes AgriXiv, EarthArXiv, engrXiv, PsyArXiv, SocArXiv, LawArXiv,
    NutriXiv, PaleorXiv, MindRxiv, SportRxiv, INA-Rxiv, and BITSS.
    Directly downloads full-text PDFs from osf.io.
    """
    filters = filters or {}
    year_from = filters.get("year_from")
    year_to = filters.get("year_to")

    records = []
    log.info(f"[OSF Preprints] Searching '{topic}' (limit={limit})...")

    # Build Crossref filter for OSF
    filter_parts = ["type:posted-content"]
    if year_from:
        filter_parts.append(f"from-pub-date:{year_from}-01-01")
    if year_to:
        filter_parts.append(f"until-pub-date:{year_to}-12-31")

    if specific_prefix:
        filter_parts.append(f"prefix:{specific_prefix}")
    else:
        filter_parts.append("member:15934")  # Center for Open Science member ID

    crossref_filter = ",".join(filter_parts)

    url = "https://api.crossref.org/works"
    params = {
        "query": topic,
        "filter": crossref_filter,
        "rows": min(limit * 2, 100),
        "select": "DOI,title,author,published,publisher",
        "mailto": "23r25a6702@mlrit.ac.in"
    }

    try:
        resp = get_with_backoff(url, params=params, headers=API_HEADERS, timeout=20)
        if resp.status_code == 200:
            items = resp.json().get("message", {}).get("items", [])
            for it in items:
                if len(records) >= limit:
                    break
                doi = it.get("DOI", "")
                title = (it.get("title") or ["Untitled Preprint"])[0]
                authors = [
                    f"{a.get('given', '')} {a.get('family', '')}".strip() or a.get("family", "Author")
                    for a in it.get("author", [])
                ]

                guid = _extract_osf_guid(doi)
                file_path = None
                pdf_name = None

                if guid and target_dir:
                    osf_pdf_url = f"https://osf.io/{guid}/download"
                    pdf_name = f"osf_preprint_{len(records) + 1}.pdf"
                    candidate_path = os.path.join(target_dir, pdf_name)
                    if _download_pdf(osf_pdf_url, candidate_path):
                        file_path = candidate_path

                record = {
                    "title": title,
                    "authors": authors,
                    "doi": f"https://doi.org/{doi}" if doi and not doi.startswith("http") else doi,
                    "source_journal": "OSF Preprints",
                    "emails": []
                }
                if file_path:
                    record["file_path"] = file_path
                    record["pdf_name"] = pdf_name

                records.append(record)
    except Exception as e:
        log.error(f"[OSF Preprints] Error fetching papers: {e}")

    return records


def fetch_preprints_org_papers(topic, limit=10, target_dir=None, filters=None):
    """
    Fetches preprints from MDPI's Preprints.org platform (DOI prefix 10.20944).
    Uses Europe PMC and Crossref to retrieve preprints and author affiliations.
    """
    filters = filters or {}
    year_from = filters.get("year_from")
    year_to = filters.get("year_to")

    records = []
    log.info(f"[Preprints.org] Searching '{topic}' (limit={limit})...")

    # Europe PMC has full metadata and affiliations for Preprints.org
    epmc_query = f'SRC:PPR AND DOI:10.20944* AND "{topic}"'
    if year_from and year_to:
        epmc_query += f" AND PUB_YEAR:[{year_from} TO {year_to}]"
    elif year_from:
        epmc_query += f" AND PUB_YEAR:[{year_from} TO 2099]"
    elif year_to:
        epmc_query += f" AND PUB_YEAR:[1990 TO {year_to}]"

    epmc_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    params = {
        "query": epmc_query,
        "format": "json",
        "pageSize": min(limit * 2, 100),
        "resultType": "core"
    }

    try:
        resp = get_with_backoff(epmc_url, params=params, headers=API_HEADERS, timeout=25)
        if resp.status_code == 200:
            results = resp.json().get("resultList", {}).get("result", [])
            for it in results:
                if len(records) >= limit:
                    break
                title = it.get("title", "Untitled").rstrip(".")
                doi = it.get("doi", "")
                authors_str = it.get("authorString", "")
                authors = [a.strip() for a in authors_str.split(",") if a.strip()]

                pdf_urls = [
                    full_text.get("url")
                    for full_text in it.get("fullTextUrlList", {}).get("fullTextUrl", [])
                    if full_text.get("documentStyle") == "pdf" and full_text.get("url")
                ]
                file_path = None
                if target_dir and pdf_urls:
                    candidate_path = os.path.join(target_dir, f"preprints_org_{len(records) + 1}.pdf")
                    if _download_first_pdf(pdf_urls, candidate_path):
                        file_path = candidate_path

                # Pre-extract author emails from affiliations
                emails = []
                for auth in it.get("authorList", {}).get("author", []):
                    for aff_obj in auth.get("authorAffiliationDetailsList", {}).get("authorAffiliation", []):
                        aff_text = aff_obj.get("affiliation", "")
                        for em in EMAIL_RE.findall(aff_text):
                            c = em.strip().rstrip(".").lower()
                            if c not in emails:
                                emails.append(c)

                record = {
                    "title": title,
                    "authors": authors,
                    "doi": f"https://doi.org/{doi}" if doi and not doi.startswith("http") else doi,
                    "source_journal": "Preprints.org",
                    "emails": emails
                }
                if file_path:
                    record["file_path"] = file_path
                    record["pdf_name"] = os.path.basename(file_path)
                records.append(record)
    except Exception as e:
        log.error(f"[Preprints.org] Error querying EuropePMC: {e}")

    # Fallback to Crossref if Europe PMC had 0 records
    if not records:
        log.info("[Preprints.org] Querying Crossref fallback...")
        crossref_url = "https://api.crossref.org/works"
        params = {
            "query": topic,
            "filter": "type:posted-content,prefix:10.20944",
            "rows": limit,
            "mailto": "23r25a6702@mlrit.ac.in"
        }
        try:
            resp = get_with_backoff(crossref_url, params=params, headers=API_HEADERS, timeout=20)
            if resp.status_code == 200:
                for it in resp.json().get("message", {}).get("items", []):
                    title = (it.get("title") or ["Untitled"])[0]
                    doi = it.get("DOI", "")
                    authors = [
                        f"{a.get('given', '')} {a.get('family', '')}".strip() or a.get("family", "Author")
                        for a in it.get("author", [])
                    ]
                    records.append({
                        "title": title,
                        "authors": authors,
                        "doi": f"https://doi.org/{doi}" if doi else "",
                        "source_journal": "Preprints.org",
                        "emails": []
                    })
        except Exception as e:
            log.error(f"[Preprints.org] Crossref error: {e}")

    return records


def fetch_chemrxiv_papers(topic, limit=10, target_dir=None, filters=None):
    """
    Fetches chemistry preprints from ChemRxiv (ACS, RSC, GDCh, CCS, CSJ).
    Uses Crossref prefix 10.26434 and OpenAlex source S4393918830.
    """
    filters = filters or {}
    records = []
    log.info(f"[ChemRxiv] Searching '{topic}' (limit={limit})...")

    # Use OpenAlex ChemRxiv source filter to locate OA mirrors and author emails
    oa_url = "https://api.openalex.org/works"
    params = {
        "search": topic,
        "filter": "primary_location.source.id:https://openalex.org/S4393918830",
        "per-page": min(limit * 2, 50),
        "mailto": "23r25a6702@mlrit.ac.in"
    }

    try:
        resp = get_with_backoff(oa_url, params=params, headers=API_HEADERS, timeout=20)
        if resp.status_code == 200:
            for it in resp.json().get("results", []):
                if len(records) >= limit:
                    break
                title = it.get("title") or "Untitled Paper"
                doi = it.get("doi") or ""
                authors = [a.get("author", {}).get("display_name", "Author") for a in it.get("authorships", [])]

                emails = []
                for a in it.get("authorships", []):
                    for aff in a.get("raw_affiliation_strings", []):
                        for em in EMAIL_RE.findall(aff):
                            c = em.strip().rstrip(".").lower()
                            if c not in emails:
                                emails.append(c)

                file_path = None
                pdf_name = None
                # Check for open repository mirrors (Zenodo, institutional, osti)
                if target_dir:
                    for loc in it.get("locations", []):
                        p_url = loc.get("pdf_url")
                        if p_url and "chemrxiv.org" not in p_url.lower():
                            cand_name = f"chemrxiv_{len(records) + 1}.pdf"
                            cand_path = os.path.join(target_dir, cand_name)
                            if _download_pdf(p_url, cand_path):
                                file_path = cand_path
                                pdf_name = cand_name
                                break

                rec = {
                    "title": title,
                    "authors": authors,
                    "doi": doi,
                    "source_journal": "ChemRxiv",
                    "emails": emails
                }
                if file_path:
                    rec["file_path"] = file_path
                    rec["pdf_name"] = pdf_name
                records.append(rec)
    except Exception as e:
        log.error(f"[ChemRxiv] Error: {e}")

    # Fallback to Crossref prefix if OpenAlex returns few
    if len(records) < limit:
        crossref_url = "https://api.crossref.org/works"
        params = {
            "query": topic,
            "filter": "type:posted-content,prefix:10.26434",
            "rows": limit - len(records),
            "mailto": "23r25a6702@mlrit.ac.in"
        }
        try:
            resp = get_with_backoff(crossref_url, params=params, headers=API_HEADERS, timeout=20)
            if resp.status_code == 200:
                for it in resp.json().get("message", {}).get("items", []):
                    title = (it.get("title") or ["Untitled"])[0]
                    doi = it.get("DOI", "")
                    authors = [
                        f"{a.get('given', '')} {a.get('family', '')}".strip() or a.get("family", "Author")
                        for a in it.get("author", [])
                    ]
                    records.append({
                        "title": title,
                        "authors": authors,
                        "doi": f"https://doi.org/{doi}" if doi else "",
                        "source_journal": "ChemRxiv",
                        "emails": []
                    })
        except Exception as e:
            log.error(f"[ChemRxiv] Crossref fallback error: {e}")

    return records


def fetch_ssrn_papers(topic, limit=10, target_dir=None, filters=None):
    """
    Fetches preprints and working papers from SSRN (Social Science Research Network).
    Uses Crossref prefix 10.2139 and OpenAlex SSRN source S4210172589.
    """
    filters = filters or {}
    records = []
    log.info(f"[SSRN] Searching '{topic}' (limit={limit})...")

    oa_url = "https://api.openalex.org/works"
    params = {
        "search": topic,
        "filter": "primary_location.source.id:https://openalex.org/S4210172589",
        "per-page": min(limit * 2, 50),
        "mailto": "23r25a6702@mlrit.ac.in"
    }

    try:
        resp = get_with_backoff(oa_url, params=params, headers=API_HEADERS, timeout=20)
        if resp.status_code == 200:
            for it in resp.json().get("results", []):
                if len(records) >= limit:
                    break
                title = it.get("title") or "Untitled Paper"
                doi = it.get("doi") or ""
                authors = [a.get("author", {}).get("display_name", "Author") for a in it.get("authorships", [])]

                emails = []
                for a in it.get("authorships", []):
                    for aff in a.get("raw_affiliation_strings", []):
                        for em in EMAIL_RE.findall(aff):
                            c = em.strip().rstrip(".").lower()
                            if c not in emails:
                                emails.append(c)

                records.append({
                    "title": title,
                    "authors": authors,
                    "doi": doi,
                    "source_journal": "SSRN",
                    "emails": emails
                })
    except Exception as e:
        log.error(f"[SSRN] OpenAlex error: {e}")

    return records


def fetch_scielo_preprints_papers(topic, limit=10, target_dir=None, filters=None):
    """
    Fetches preprints from SciELO Preprints (Latin America & Global Open Science).
    Uses Crossref prefix 10.1590 and SciELO preprints repository.
    """
    filters = filters or {}
    records = []
    log.info(f"[SciELO Preprints] Searching '{topic}' (limit={limit})...")

    crossref_url = "https://api.crossref.org/works"
    params = {
        "query": topic,
        "filter": "type:posted-content,prefix:10.1590",
        "rows": limit,
        "mailto": "23r25a6702@mlrit.ac.in"
    }
    try:
        resp = get_with_backoff(crossref_url, params=params, headers=API_HEADERS, timeout=20)
        if resp.status_code == 200:
            for it in resp.json().get("message", {}).get("items", []):
                title = (it.get("title") or ["Untitled"])[0]
                doi = it.get("DOI", "")
                authors = [
                    f"{a.get('given', '')} {a.get('family', '')}".strip() or a.get("family", "Author")
                    for a in it.get("author", [])
                ]
                records.append({
                    "title": title,
                    "authors": authors,
                    "doi": f"https://doi.org/{doi}" if doi else "",
                    "source_journal": "SciELO Preprints",
                    "emails": []
                })
    except Exception as e:
        log.error(f"[SciELO Preprints] error: {e}")

    return records


def fetch_repec_papers(topic, limit=10, target_dir=None, filters=None):
    """
    Fetches economics research preprints and working papers from RePEc (Research Papers in Economics).
    Uses OpenAlex RePEc source S4306401271.
    """
    filters = filters or {}
    records = []
    log.info(f"[RePEc] Searching '{topic}' (limit={limit})...")

    oa_url = "https://api.openalex.org/works"
    params = {
        "search": topic,
        "filter": "primary_location.source.id:https://openalex.org/S4306401271",
        "per-page": min(limit * 2, 50),
        "mailto": "23r25a6702@mlrit.ac.in"
    }

    try:
        resp = get_with_backoff(oa_url, params=params, headers=API_HEADERS, timeout=20)
        if resp.status_code == 200:
            for it in resp.json().get("results", []):
                if len(records) >= limit:
                    break
                title = it.get("title") or "Untitled Paper"
                doi = it.get("doi") or ""
                authors = [a.get("author", {}).get("display_name", "Author") for a in it.get("authorships", [])]

                emails = []
                for a in it.get("authorships", []):
                    for aff in a.get("raw_affiliation_strings", []):
                        for em in EMAIL_RE.findall(aff):
                            c = em.strip().rstrip(".").lower()
                            if c not in emails:
                                emails.append(c)

                records.append({
                    "title": title,
                    "authors": authors,
                    "doi": doi,
                    "source_journal": "RePEc",
                    "emails": emails
                })
    except Exception as e:
        log.error(f"[RePEc] error: {e}")

    return records


def fetch_essoar_papers(topic, limit=10, target_dir=None, filters=None, offset=0):
    """Search ESS Open Archive DOI records and download their public PDF links."""
    filters = filters or {}
    records = []
    url = "https://api.crossref.org/works"
    params = {
        "query": topic,
        "filter": "type:posted-content,prefix:10.22541",
        "rows": min(max(1, limit) * 2, 100),
        "offset": max(0, int(offset)),
        "mailto": os.getenv("RESEARCH_CONTACT_EMAIL", "outreach@example.org"),
    }
    if filters.get("year_from"):
        params["filter"] += f",from-pub-date:{filters['year_from']}-01-01"
    if filters.get("year_to"):
        params["filter"] += f",until-pub-date:{filters['year_to']}-12-31"

    try:
        items = []
        for prefix in ("10.22541", "10.1002"):
            query_params = dict(params)
            query_params["filter"] = query_params["filter"].replace(
                "prefix:10.22541", f"prefix:{prefix}", 1
            )
            response = get_with_backoff(url, params=query_params, headers=API_HEADERS, timeout=20)
            if response is not None and response.status_code == 200:
                items.extend(response.json().get("message", {}).get("items", []))
            if len(items) >= limit * 2:
                break
        for item in items:
            if len(records) >= limit:
                break
            doi = item.get("DOI", "")
            if not doi:
                continue
            title = (item.get("title") or ["Untitled ESS Open Archive preprint"])[0]
            authors = [
                f"{author.get('given', '')} {author.get('family', '')}".strip()
                for author in item.get("author", [])
            ]
            urls = [f"https://essopenarchive.org/doi/pdf/{doi}"]
            urls.extend(link.get("URL") for link in item.get("link", []) if link.get("URL"))
            record = {"title": title, "authors": authors, "doi": doi, "source_journal": "ESS Open Archive", "emails": []}
            if target_dir:
                path = os.path.join(target_dir, f"essoar_{len(records) + 1}.pdf")
                if _download_first_pdf(urls, path):
                    record["file_path"] = path
                    record["pdf_name"] = os.path.basename(path)
            records.append(record)
    except Exception as exc:
        log.warning("[ESS Open Archive] Search failed: %s", exc)
    return records


def fetch_eric_papers(topic, limit=10, target_dir=None, filters=None, offset=0):
    """Search ERIC's public API and download only records with ERIC full text."""
    filters = filters or {}
    records = []
    params = {
        "search": topic, "format": "json", "rows": min(max(1, limit) * 3, 200),
        "start": max(0, int(offset)),
        "fields": "id,title,author,fulltextauth,url,publicationdateyear",
    }
    if filters.get("year_from"):
        params["publicationdatestart"] = f"{filters['year_from']}-01-01"
    if filters.get("year_to"):
        params["publicationdateend"] = f"{filters['year_to']}-12-31"
    try:
        response = get_with_backoff("https://api.ies.ed.gov/eric/", params=params, headers=API_HEADERS, timeout=20)
        if response is None or response.status_code != 200:
            return records
        docs = response.json().get("response", {}).get("docs", [])
        for doc in docs:
            if len(records) >= limit:
                break
            eric_id = doc.get("id", "")
            full_text = doc.get("fulltextauth")
            if isinstance(full_text, list):
                full_text = any(str(value).lower() in {"yes", "true", "1", "y"} for value in full_text)
            if str(full_text).lower() not in {"yes", "true", "1", "y"} or not eric_id or not target_dir:
                continue
            pdf_url = f"https://files.eric.ed.gov/fulltext/{eric_id}.pdf"
            path = os.path.join(target_dir, f"eric_{len(records) + 1}.pdf")
            if not _download_first_pdf([pdf_url], path):
                continue
            authors = doc.get("author", [])
            if isinstance(authors, str):
                authors = [name.strip() for name in re.split(r"\s*[;,]\s*", authors) if name.strip()]
            records.append({
                "title": doc.get("title") or "Untitled ERIC record", "authors": authors,
                "doi": doc.get("id", ""), "source_journal": "ERIC",
                "file_path": path, "pdf_name": os.path.basename(path), "emails": [],
            })
    except Exception as exc:
        log.warning("[ERIC] Search failed: %s", exc)
    return records


def _download_first_pdf(urls, file_path):
    for url in urls:
        if url and _download_pdf(url, file_path):
            return True
    return False


def _has_pdf_file(record):
    path = record.get("file_path")
    try:
        with open(path, "rb") as pdf_file:
            return pdf_file.read(5) == b"%PDF-"
    except (OSError, TypeError):
        return False


def fetch_all_preprints_papers(topic, limit=10, target_dir=None, filters=None, offset=0):
    """
    Discover across listed preprint services, returning only validated PDF files.
    """
    filters = filters or {}
    log.info(f"[All Preprints] Unified search across all preprint archives for '{topic}' (limit={limit})...")

    results = []
    # OSF hosts FocUS, Law Archive, PsyArXiv, SocArXiv and related servers.
    # Every distinct connector is queried once; paper-level deduplication happens in the worker.
    sources = [
        (fetch_osf_papers, {"specific_prefix": None}),
        (fetch_preprints_org_papers, {}),
        (fetch_chemrxiv_papers, {}),
        (fetch_ssrn_papers, {}),
        (fetch_repec_papers, {}),
        (fetch_scielo_preprints_papers, {}),
        (fetch_openalex_papers, {"offset": offset}),
    ]
    seen_connectors = set()
    for fetcher, extra in sources:
        if fetcher in seen_connectors:
            continue
        seen_connectors.add(fetcher)
        remaining = limit - len(results)
        if remaining <= 0:
            break
        try:
            candidates = fetcher(topic, limit=remaining, target_dir=target_dir, filters=filters, **extra)
        except TypeError:
            try:
                candidates = fetcher(topic, limit=remaining, target_dir=target_dir, filters=filters)
            except Exception as exc:
                log.warning("[All Preprints] %s search failed: %s", fetcher.__name__, exc)
                continue
        except Exception as exc:
            log.warning("[All Preprints] %s search failed: %s", fetcher.__name__, exc)
            continue
        results.extend(record for record in candidates if _has_pdf_file(record))

    return results[:limit]
