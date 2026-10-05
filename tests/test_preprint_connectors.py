import sys
import re
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "WS2.0"))
from extractors import preprints_fetcher as preprints


def test_every_ui_source_has_a_backend_connector():
    import app

    workspace = (Path(__file__).resolve().parents[1] / "WS2.0" / "static" / "workspace.js").read_text(encoding="utf-8")
    ui_sources = set(re.findall(r"\bid:\s*'([a-zA-Z0-9_]+)'", workspace))
    assert ui_sources
    assert ui_sources <= set(app.SOURCE_FETCHERS)


def test_essoar_fetcher_returns_only_when_pdf_saved(monkeypatch, tmp_path):
    response = SimpleNamespace(
        status_code=200,
        json=lambda: {"message": {"items": [{
            "DOI": "10.22541/essoar.123",
            "title": ["Open archive study"],
            "author": [{"given": "Jane", "family": "Smith"}],
        }]}},
    )
    monkeypatch.setattr(preprints, "get_with_backoff", lambda *a, **k: response)

    def save_pdf(urls, path):
        Path(path).write_bytes(b"%PDF-1.4 test")
        return True

    monkeypatch.setattr(preprints, "_download_first_pdf", save_pdf)
    papers = preprints.fetch_essoar_papers("climate", 1, str(tmp_path))
    assert len(papers) == 1
    assert papers[0]["file_path"].endswith(".pdf")
    assert papers[0]["authors"] == ["Jane Smith"]


def test_eric_fetcher_skips_records_without_public_full_text(monkeypatch, tmp_path):
    response = SimpleNamespace(
        status_code=200,
        json=lambda: {"response": {"docs": [
            {"id": "ED1", "title": "Metadata only", "fulltextauth": "no"},
            {"id": "ED2", "title": "Open report", "author": ["Jane Smith"], "fulltextauth": "yes"},
        ]}},
    )
    monkeypatch.setattr(preprints, "get_with_backoff", lambda *a, **k: response)

    def save_pdf(urls, path):
        assert urls == ["https://files.eric.ed.gov/fulltext/ED2.pdf"]
        Path(path).write_bytes(b"%PDF-1.4 test")
        return True

    monkeypatch.setattr(preprints, "_download_first_pdf", save_pdf)
    papers = preprints.fetch_eric_papers("learning", 1, str(tmp_path))
    assert len(papers) == 1
    assert papers[0]["title"] == "Open report"
    assert papers[0]["authors"] == ["Jane Smith"]


def test_shared_preprint_connector_discards_metadata_only_records(monkeypatch, tmp_path):
    metadata = {"title": "No PDF", "emails": ["author@example.org"]}
    good = {"title": "PDF paper", "file_path": str(tmp_path / "good.pdf")}
    Path(good["file_path"]).write_bytes(b"%PDF-1.4 test")
    calls = []

    def source(topic, limit, target_dir, filters=None, **kwargs):
        calls.append(limit)
        return [metadata, good]

    monkeypatch.setattr(preprints, "fetch_osf_papers", source)
    monkeypatch.setattr(preprints, "fetch_essoar_papers", lambda *a, **k: [])
    results = preprints.fetch_all_preprints_papers("topic", 1, str(tmp_path))
    assert results == [good]
    assert calls == [1]
