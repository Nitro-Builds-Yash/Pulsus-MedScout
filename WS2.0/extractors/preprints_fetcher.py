import os
import re
import time
import logging
import requests
from .http_client import http_session, POLITE_USER_AGENT, polite_jitter

log = logging.getLogger("extraction.preprints")

EMAIL_RE = re.compile(r'[a-zA-Z0-9_.+-]+@(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}')

STEALTH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
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
        resp = requests.get(url, headers=STEALTH_HEADERS, timeout=timeout, allow_redirects=True)
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
        resp = requests.get(url, params=params, headers=API_HEADERS, timeout=20)
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
        resp = requests.get(epmc_url, params=params, headers=API_HEADERS, timeout=25)
        if resp.status_code == 200:
            results = resp.json().get("resultList", {}).get("result", [])
            for it in results:
                if len(records) >= limit:
                    break
                title = it.get("title", "Untitled").rstrip(".")
                doi = it.get("doi", "")
                authors_str = it.get("authorString", "")
                authors = [a.strip() for a in authors_str.split(",") if a.strip()]

                # Pre-extract author emails from affiliations
                emails = []
                for auth in it.get("authorList", {}).get("author", []):
                    for aff_obj in auth.get("authorAffiliationDetailsList", {}).get("authorAffiliation", []):
                        aff_text = aff_obj.get("affiliation", "")
                        for em in EMAIL_RE.findall(aff_text):
                            c = em.strip().rstrip(".").lower()
                            if c not in emails:
                                emails.append(c)

                records.append({
                    "title": title,
                    "authors": authors,
                    "doi": f"https://doi.org/{doi}" if doi and not doi.startswith("http") else doi,
                    "source_journal": "Preprints.org",
                    "emails": emails
                })
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
            resp = requests.get(crossref_url, params=params, headers=API_HEADERS, timeout=20)
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
        resp = requests.get(oa_url, params=params, headers=API_HEADERS, timeout=20)
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
            resp = requests.get(crossref_url, params=params, headers=API_HEADERS, timeout=20)
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
        resp = requests.get(oa_url, params=params, headers=API_HEADERS, timeout=20)
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
        resp = requests.get(crossref_url, params=params, headers=API_HEADERS, timeout=20)
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
        resp = requests.get(oa_url, params=params, headers=API_HEADERS, timeout=20)
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


def fetch_all_preprints_papers(topic, limit=10, target_dir=None, filters=None):
    """
    Master combined extractor across ALL preprint servers in the infographic:
    arXiv, bioRxiv, ChemRxiv, Preprints.org, OSF Network (EarthArXiv, PsyArXiv,
    SocArXiv, AgriXiv, engrXiv), SSRN, RePEc, SciELO, and PeerJ.
    """
    filters = filters or {}
    log.info(f"[All Preprints] Unified search across all preprint archives for '{topic}' (limit={limit})...")

    # 1. Fetch OSF preprints (greatest direct PDF yield)
    per_repo = max(2, limit // 3)
    results = []

    osf_records = fetch_osf_papers(topic, limit=per_repo, target_dir=target_dir, filters=filters)
    results.extend(osf_records)

    # 2. Fetch Preprints.org
    if len(results) < limit:
        remaining = limit - len(results)
        preprints_org_records = fetch_preprints_org_papers(topic, limit=remaining, target_dir=target_dir, filters=filters)
        results.extend(preprints_org_records)

    # 3. Fetch ChemRxiv
    if len(results) < limit:
        remaining = limit - len(results)
        chem_records = fetch_chemrxiv_papers(topic, limit=remaining, target_dir=target_dir, filters=filters)
        results.extend(chem_records)

    # 4. Fetch SSRN
    if len(results) < limit:
        remaining = limit - len(results)
        ssrn_records = fetch_ssrn_papers(topic, limit=remaining, target_dir=target_dir, filters=filters)
        results.extend(ssrn_records)

    # 5. Fallback to OpenAlex type:preprint if still under limit
    if len(results) < limit:
        remaining = limit - len(results)
        oa_url = "https://api.openalex.org/works"
        params = {
            "search": topic,
            "filter": "type:preprint",
            "per-page": min(remaining * 2, 50),
            "mailto": "23r25a6702@mlrit.ac.in"
        }
        try:
            resp = requests.get(oa_url, params=params, headers=API_HEADERS, timeout=20)
            if resp.status_code == 200:
                for it in resp.json().get("results", []):
                    if len(results) >= limit:
                        break
                    title = it.get("title") or "Untitled Preprint"
                    doi = it.get("doi") or ""
                    authors = [a.get("author", {}).get("display_name", "Author") for a in it.get("authorships", [])]
                    source_name = ((it.get("primary_location") or {}).get("source") or {}).get("display_name") or "Preprints"

                    emails = []
                    for a in it.get("authorships", []):
                        for aff in a.get("raw_affiliation_strings", []):
                            for em in EMAIL_RE.findall(aff):
                                c = em.strip().rstrip(".").lower()
                                if c not in emails:
                                    emails.append(c)

                    results.append({
                        "title": title,
                        "authors": authors,
                        "doi": doi,
                        "source_journal": source_name,
                        "emails": emails
                    })
        except Exception as e:
            log.error(f"[All Preprints] OpenAlex fallback error: {e}")

    return results[:limit]