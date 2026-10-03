import re

def normalise_doi(raw):
    """
    Convert any DOI representation to a stable, lowercase dedup key.

    Handles:
      - https://doi.org/10.xxxx/...  →  10.xxxx/...
      - http://arxiv.org/abs/1234v2  →  arxiv:1234  (version stripped)
      - 10.xxxx/...                  →  10.xxxx/...  (unchanged)
      - "N/A", "", None              →  ""  (excluded from seen_dois)
    """
    if not raw:
        return ""
    s = str(raw).strip().lower()
    if s in ("n/a", "na", "", "none", "null"):
        return ""

    # Strip https://doi.org/ and http://doi.org/ prefixes
    for prefix in ("https://doi.org/", "http://doi.org/",
                   "https://dx.doi.org/", "http://dx.doi.org/"):
        if s.startswith(prefix):
            return s[len(prefix):]

    # Normalise arXiv abstract URLs → stable arxiv:<id> key (version stripped)
    for prefix in ("https://arxiv.org/abs/", "http://arxiv.org/abs/"):
        if s.startswith(prefix):
            arxiv_id = s[len(prefix):]
            arxiv_id = re.sub(r'v\d+$', '', arxiv_id)  # strip v1/v2/...
            return f"arxiv:{arxiv_id}"

    return s
