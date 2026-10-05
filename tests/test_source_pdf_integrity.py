import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "WS2.0"))

from extractors import europepmc_fetcher, openalex_fetcher, plos_fetcher


def test_plos_skips_manuscript_xml_and_requires_real_pdf(monkeypatch, tmp_path):
    search_response = Mock(status_code=200)
    search_response.json.return_value = {
        "response": {
            "docs": [{
                "id": "10.1371/journal.pone.0000001",
                "title": "Open ecology research",
                "author_display": ["Jane Smith"],
            }]
        }
    }
    pdf_content = b"%PDF-1.7 actual PLOS PDF"
    pdf_response = Mock(status_code=200, content=pdf_content)
    get = Mock(side_effect=[search_response, pdf_response])
    monkeypatch.setattr(plos_fetcher.requests, "get", get)
    monkeypatch.setattr(plos_fetcher, "polite_jitter", lambda: None)

    papers = plos_fetcher.fetch_plos_papers("ecology", 1, str(tmp_path))

    assert len(papers) == 1
    assert Path(papers[0]["file_path"]).read_bytes() == pdf_content
    assert get.call_count == 2
    assert "type=printable" in get.call_args_list[1].args[0]


def test_europepmc_requires_pdf_even_when_metadata_has_email(monkeypatch, tmp_path):
    search_response = Mock(status_code=200)
    search_response.json.return_value = {
        "resultList": {
            "result": [{
                "pmcid": "PMC12345",
                "doi": "10.1234/example",
                "title": "Ecology study",
                "authorString": "Jane Smith",
                "authorList": {
                    "author": [{
                        "authorAffiliationDetailsList": {
                            "authorAffiliation": [{
                                "affiliation": "Contact jane@example.org",
                            }]
                        }
                    }]
                },
            }]
        }
    }
    pdf_content = b"%PDF-1.7 actual Europe PMC PDF"
    pdf_response = Mock(status_code=200, content=pdf_content)

    class Session:
        def __init__(self):
            self.headers = {}
            self.get = Mock(side_effect=[search_response, pdf_response])

    session = Session()
    monkeypatch.setattr(europepmc_fetcher.requests, "Session", lambda: session)
    monkeypatch.setattr(europepmc_fetcher, "polite_jitter", lambda: None)

    papers = europepmc_fetcher.fetch_europepmc_papers(
        "ecology", 1, str(tmp_path)
    )

    assert len(papers) == 1
    assert Path(papers[0]["file_path"]).read_bytes() == pdf_content
    assert session.get.call_count == 2
    assert session.get.call_args_list[0].kwargs["params"]["pageSize"] == 25


def test_openalex_rate_limit_switches_sources_without_retry(monkeypatch, tmp_path):
    response = Mock(status_code=429, text="Insufficient budget")
    get = Mock(return_value=response)
    monkeypatch.setattr(openalex_fetcher.requests, "get", get)

    with pytest.raises(openalex_fetcher._OpenAlexRateLimitError):
        openalex_fetcher.fetch_openalex_papers("ecology", 1, str(tmp_path))

    get.assert_called_once()
