import os
import re
import time
import logging
import requests

log = logging.getLogger("extraction.openalex")

# Country name → ISO alpha-2 code (OpenAlex uses these codes)
from .country_filter import COUNTRY_CODES as _COUNTRY_CODES
from .http_client import POLITE_USER_AGENT, RESEARCH_EMAIL, polite_jitter

# Article type name → OpenAlex type string
_TYPE_MAP = {
    "Article": "article",
    "Research Article": "article",
    "Case Reports": "article",
    "Case Report": "article",
    "Brief Reports": "article",
    "Brief Report": "article",
    "Systematic Reports": "review",
    "Systematic Report": "review",
    "Review": "review",
    "Systematic Review": "review",
}


def fetch_openalex_papers(topic, limit, target_dir, filters=None, page=1, offset=0, **kwargs):
    """
    Searches and downloads Open Access PDFs from OpenAlex REST API.
    Supports page and offset pagination.

    filters (dict, optional):
        countries     (list[str]): UI country names, mapped to ISO codes
        year_from     (int|None):  publication year ≥ this
        year_to       (int|None):  publication year ≤ this
        article_types (list[str]): article type labels mapped to OpenAlex types
    """
    filters = filters or {}
    base_url = "https://api.openalex.org/works"

    # --- Build filter string ---
    api_filters = ["has_oa_accepted_or_published_version:true", "is_oa:true"]

    # Year range
    year_from = filters.get("year_from")
    year_to   = filters.get("year_to")
    if year_from and year_to:
        api_filters.append(f"publication_year:{year_from}-{year_to}")
    elif year_from:
        api_filters.append(f"publication_year:>{year_from - 1}")
    elif year_to:
        api_filters.append(f"publication_year:<{year_to + 1}")

    # Countries — map UI names to ISO codes, join with |  (OR logic)
    countries = filters.get("countries", [])
    iso_codes = [_COUNTRY_CODES[c] for c in countries if c in _COUNTRY_CODES]
    if iso_codes:
        api_filters.append("institutions.country_code:" + "|".join(iso_codes))

    # Article types — map UI names to OpenAlex types, join with |  (OR logic)
    article_types = filters.get("article_types", [])
    oa_types = list({_TYPE_MAP[t] for t in article_types if t in _TYPE_MAP})
    if oa_types:
        api_filters.append("type:" + "|".join(oa_types))

    filter_str = ",".join(api_filters)
    log.info(f"[OpenAlex] filter={filter_str!r}")

    headers = {
        "User-Agent": POLITE_USER_AGENT
    }

    per_page = min(max(limit, 25), 200)
    if offset and page == 1:
        page = max(1, (int(offset) // per_page) + 1)
    page = max(1, int(page))
    target_candidates = min(limit * 2, 1000)
    max_page = page + 5

    items = []
    try:
        while len(items) < target_candidates and page <= max_page:
            params = {
                "search":    topic,
                "filter":    filter_str,
                "per-page":  per_page,
                "page":      page,
                "sort":      "relevance_score:desc",
                "mailto":    RESEARCH_EMAIL,
            }
            resp = requests.get(base_url, params=params, headers=headers, timeout=25)
            if resp.status_code == 429:
                log.warning("[OpenAlex] Rate limited (HTTP 429). Backing off 2.5s...")
                time.sleep(2.5)
                resp = requests.get(base_url, params=params, headers=headers, timeout=25)
            if resp.status_code != 200:
                log.error(f"[OpenAlex] API error: HTTP {resp.status_code} — {resp.text[:120]}")
                break
            page_results = resp.json().get("results", [])
            if not page_results:
                break
            items.extend(page_results)
            page += 1
            if len(page_results) < per_page:
                break
            polite_jitter(0.3, 0.7)

        log.info(f"[OpenAlex] Got {len(items)} candidates across {page - 1} page(s).")
    except Exception as e:
        log.error(f"[OpenAlex] API error: {e}")
        if not items:
            return []

    records = []
    saved_count = 0

    for item in items:
        if saved_count >= limit:
            break

        title = item.get("display_name") or item.get("title") or "Untitled"
        doi   = item.get("doi") or "N/A"

        # Extract authors list and any affiliation emails
        authors_meta = []
        found_emails = []
        for a in item.get("authorships", []):
            name = (a.get("author") or {}).get("display_name")
            if name:
                authors_meta.append(name.strip())
            for aff in a.get("raw_affiliation_strings", []):
                for em in re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', aff):
                    clean = em.strip().rstrip(".").lower()
                    if clean not in found_emails:
                        found_emails.append(clean)

        # Collect all PDF URLs, prioritizing open repositories over commercial paywalls
        TRUSTED_HOSTS = ["arxiv.org", "europepmc.org", "ncbi.nlm.nih.gov", "pmc.ncbi.nlm.nih.gov", "biorxiv.org", "medrxiv.org", "mdpi.com", "frontiersin.org", "plos.org", "core.ac.uk", "zenodo.org", "researchsquare.com"]
        BLOCKED_HOSTS = ["wiley.com", "cell.com", "elsevier.com", "nature.com", "springer.com", "sciencedirect.com", "tandfonline.com", "oup.com"]

        raw_pdf_urls = []
        best_oa = item.get("best_oa_location") or {}
        if best_oa.get("pdf_url"):
            raw_pdf_urls.append(best_oa["pdf_url"])
        primary_loc = item.get("primary_location") or {}
        if primary_loc.get("pdf_url") and primary_loc["pdf_url"] not in raw_pdf_urls:
            raw_pdf_urls.append(primary_loc["pdf_url"])
        for loc in item.get("locations", []):
            u = loc.get("pdf_url")
            if u and u not in raw_pdf_urls:
                raw_pdf_urls.append(u)

        # Filter out known blocking hosts and prioritize trusted open repositories
        pdf_urls = []
        for u in raw_pdf_urls:
            u_low = u.lower()
            if any(bh in u_low for bh in BLOCKED_HOSTS):
                continue
            if any(th in u_low for th in TRUSTED_HOSTS):
                pdf_urls.insert(0, u)
            else:
                pdf_urls.append(u)

        if not pdf_urls and not found_emails:
            continue

        pdf_name = f"openalex_paper_{saved_count + 1}.pdf"
        file_path = os.path.join(target_dir, pdf_name)
        download_success = False

        for url in pdf_urls[:3]:  # Try at most top 3 open URLs
            try:
                pdf_resp = requests.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                }, timeout=8, allow_redirects=True)
                if pdf_resp.status_code == 200 and (
                    pdf_resp.content.startswith(b"%PDF") or b"%PDF-" in pdf_resp.content[:1024]
                ):
                    with open(file_path, "wb") as f:
                        f.write(pdf_resp.content)
                    download_success = True
                    break
            except Exception as e:
                log.warning(f"[OpenAlex] PDF download failed ({url}): {e}")

        if download_success or found_emails:
            saved_count += 1
            source_journal = "OpenAlex"
            src_obj = (item.get("primary_location") or {}).get("source") or {}
            if src_obj.get("display_name"):
                source_journal = src_obj["display_name"]
            rec = {
                "title":         title,
                "authors":       authors_meta,
                "doi":           doi,
                "source_journal": source_journal,
                "emails":        found_emails,
                "author_countries": {(a.get("author") or {}).get("display_name", ""): (a.get("countries") or []) + [i.get("country_code") for i in a.get("institutions", []) if i.get("country_code")] for a in item.get("authorships", [])},
            }
            if download_success:
                rec["file_path"] = file_path
                rec["pdf_name"]  = pdf_name
            records.append(rec)
            polite_jitter(0.3, 0.7)

    return records