import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "WS2.0"))

from extractors import arxiv_fetcher, crossref_fetcher, http_client


def test_polite_jitter_uses_a_variable_delay(monkeypatch):
    delays = []
    monkeypatch.setattr(http_client.random, "triangular", lambda low, high, mode: 1.37)
    monkeypatch.setattr(http_client.time, "sleep", delays.append)

    http_client.polite_jitter()

    assert delays == [1.37]


def test_arxiv_downloads_pdf_without_html_probe(monkeypatch, tmp_path):
    feed = """<?xml version="1.0"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <title>Ecology Research</title>
        <id>https://arxiv.org/abs/2401.00001</id>
        <author><name>Jane Smith</name></author>
        <link title="pdf" href="https://arxiv.org/pdf/2401.00001" />
      </entry>
    </feed>"""
    search_response = Mock(status_code=200, text=feed)
    pdf_response = Mock(status_code=200, content=b"%PDF-1.4 test document")
    get = Mock(side_effect=[search_response, pdf_response])
    monkeypatch.setattr(arxiv_fetcher.requests, "get", get)
    monkeypatch.setattr(arxiv_fetcher, "polite_jitter", lambda *args: None)

    records = arxiv_fetcher.fetch_arxiv_papers("ecology", 1, str(tmp_path))

    assert len(records) == 1
    assert records[0]["title"] == "Ecology Research"
    assert Path(records[0]["file_path"]).read_bytes().startswith(b"%PDF-")
    assert get.call_count == 2
    assert get.call_args_list[1].args[0] == "https://arxiv.org/pdf/2401.00001"


def test_crossref_stops_paging_when_openalex_is_rate_limited(monkeypatch, tmp_path):
    dois = [f"10.1234/paper-{index}" for index in range(100)]
    crossref_response = Mock(status_code=200)
    crossref_response.json.return_value = {
        "message": {
            "items": [{"DOI": doi, "title": [f"Paper {index}"], "author": []}
                      for index, doi in enumerate(dois)]
        }
    }
    rate_limited_response = Mock(status_code=429, text="Rate limit exceeded")
    get = Mock(side_effect=[crossref_response, rate_limited_response])
    monkeypatch.setattr(crossref_fetcher.requests, "get", get)
    monkeypatch.setattr(crossref_fetcher, "polite_jitter", lambda *args: None)

    with pytest.raises(crossref_fetcher._OpenAlexRateLimitError):
        crossref_fetcher.fetch_crossref_papers("ecology", 80, str(tmp_path))

    assert get.call_count == 2
