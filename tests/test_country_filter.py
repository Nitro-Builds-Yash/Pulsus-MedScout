import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'WS2.0'))
from extractors.country_filter import country_codes, eligible_authors, contact_allowed, resolve_email_author


def test_all_ui_countries_and_aliases():
    assert country_codes(['India', 'China', 'United Kingdom', 'USA']) == {'IN', 'CN', 'GB', 'US'}


def test_country_is_author_specific_not_paper_specific():
    item = {'author_countries': {'Jane Smith': ['IN'], 'John Brown': ['US']}}
    names = eligible_authors(item, ['India'])
    assert contact_allowed('Jane Smith', names)
    assert not contact_allowed('John Brown', names)


def test_unknown_country_fails_closed():
    assert eligible_authors({'authors': ['Jane Smith']}, ['India']) == set()
    assert not contact_allowed('Jane Smith', set())


def test_unfiltered_search_stays_unrestricted():
    assert eligible_authors({}, []) is None
    assert contact_allowed('Jane Smith', None)


def test_multiple_selected_countries_use_union():
    item = {'author_countries': {'Jane Smith': ['IN'], 'John Brown': ['US'], 'Li Wu': ['CN']}}
    names = eligible_authors(item, ['India', 'USA'])
    assert names == {'jane smith', 'john brown'}


def test_email_domain_does_not_prove_country():
    assert eligible_authors({'emails': ['jane@college.in']}, ['India']) == set()


def test_shared_surname_is_not_an_author_match():
    assert resolve_email_author({'authors': ['Jane Smith', 'John Smith']}, 'smith@college.edu') is None


def test_shared_affiliation_email_is_not_attributed_to_first_author():
    item = {'authors': ['Jane Smith'], 'email_authors': {'smith@college.edu': 'Jane Smith'},
            'ambiguous_emails': ['smith@college.edu']}
    assert resolve_email_author(item, 'smith@college.edu') is None


def test_inconsistent_source_association_is_rejected():
    item = {'authors': ['Navin Kumar Tailor'],
            'email_authors': {'elham@example.com': 'Navin Kumar Tailor'}}
    assert resolve_email_author(item, 'elham@example.com') is None
