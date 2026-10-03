"""Country evidence belongs to an author, not an email domain or coauthor."""
import re
import unicodedata
from urllib.parse import quote
import requests

COUNTRY_CODES = dict(zip(
    ['USA', 'UK', 'Germany', 'France', 'Canada', 'Australia', 'China', 'Japan',
     'India', 'Italy', 'Spain', 'Netherlands', 'Switzerland', 'Sweden', 'Belgium',
     'South Korea', 'Singapore', 'Brazil', 'Russia', 'South Africa', 'Saudi Arabia',
     'Egypt', 'Israel', 'Turkey', 'Poland', 'Norway', 'Denmark', 'Finland',
     'Austria', 'Portugal', 'New Zealand', 'Mexico', 'Argentina', 'Chile', 'Romania', 'Greece'],
    ['US', 'GB', 'DE', 'FR', 'CA', 'AU', 'CN', 'JP', 'IN', 'IT', 'ES', 'NL', 'CH',
     'SE', 'BE', 'KR', 'SG', 'BR', 'RU', 'ZA', 'SA', 'EG', 'IL', 'TR', 'PL', 'NO',
     'DK', 'FI', 'AT', 'PT', 'NZ', 'MX', 'AR', 'CL', 'RO', 'GR']))
ALIASES = {'United States': 'US', 'United States of America': 'US', 'United Kingdom': 'GB',
           'U.S.A.': 'US', 'U.K.': 'GB', 'Republic of Korea': 'KR'}


def country_codes(names):
    lookup = {k.casefold(): v for k, v in {**COUNTRY_CODES, **ALIASES}.items()}
    lookup.update({v.casefold(): v for v in COUNTRY_CODES.values()})
    return {lookup[str(n).strip().casefold()] for n in names if str(n).strip().casefold() in lookup}


def countries_in_affiliation(text):
    text = re.sub(r'[\w.+-]+@[\w.-]+', '', text or '')
    return {code for name, code in {**COUNTRY_CODES, **ALIASES}.items()
            if re.search(r'(?<!\w)' + re.escape(name) + r'(?!\w)', text, re.I)}


def author_key(name):
    return ' '.join(unicodedata.normalize('NFKC', name or '').casefold().split())


def eligible_authors(item, countries, cache=None):
    if not countries:
        return None
    selected = country_codes(countries)
    evidence = dict(item.get('author_countries') or {})
    for name, affiliations in (item.get('author_affiliations') or {}).items():
        if isinstance(affiliations, str):
            affiliations = [affiliations]
        evidence[name] = list(country_codes(evidence.get(name, [])) |
                              countries_in_affiliation(' '.join(affiliations)))
    if not evidence:
        doi = re.sub(r'^https?://(?:dx\.)?doi.org/', '', str(item.get('doi') or ''), flags=re.I)
        if doi.startswith('10.'):
            cache = cache if cache is not None else {}
            if doi not in cache:
                try:
                    response = requests.get('https://api.openalex.org/works/https://doi.org/' +
                                            quote(doi, safe=''), timeout=12)
                    response.raise_for_status()
                    cache[doi] = response.json().get('authorships', [])
                except (requests.RequestException, ValueError):
                    cache[doi] = []
            for authorship in cache[doi]:
                name = (authorship.get('author') or {}).get('display_name', '')
                codes = list(authorship.get('countries') or [])
                codes += [i.get('country_code') for i in authorship.get('institutions', [])
                          if i.get('country_code')]
                evidence[name] = codes
    return {author_key(name) for name, codes in evidence.items() if country_codes(codes) & selected}


def contact_allowed(author, eligible):
    return eligible is None or author_key(author) in eligible


def resolve_email_author(item, email):
    """Prefer an unambiguous source association; never guess the first author."""
    if email in item.get('ambiguous_emails', []):
        return None
    explicit = (item.get('email_authors') or {}).get(email)
    username = re.sub(r'[^a-z]', '', email.split('@')[0].lower())
    candidates = []
    for author in item.get('authors', []):
        parts = [re.sub(r'[^a-z]', '', part.lower()) for part in author.split()]
        if any(len(part) >= 3 and part in username for part in parts):
            candidates.append(author)
    # Some source records attach a completely different person's email to an
    # affiliation. Require name evidence even for an explicit association.
    if explicit:
        return explicit if explicit in candidates else None
    return candidates[0] if len(set(candidates)) == 1 else None
