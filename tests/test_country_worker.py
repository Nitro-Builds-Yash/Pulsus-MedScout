import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'WS2.0'))
import app as application


@pytest.fixture
def worker(monkeypatch, tmp_path):
    monkeypatch.setattr(application, 'PDFS_BASE_DIR', str(tmp_path / 'pdf'))
    monkeypatch.setattr(application, 'EXCEL_BASE_DIR', str(tmp_path))
    monkeypatch.setattr(application, 'load_seen_data', lambda: (set(), {'10.1234/test'}))
    monkeypatch.setattr(application, 'save_new_emails_to_master', Mock())
    monkeypatch.setattr(application, '_record_attempted_doi', Mock())
    monkeypatch.setattr(application, '_release_extraction_lock', Mock())
    application.TASKS['country-test'] = {'status': 'starting'}
    yield application
    application.TASKS.pop('country-test', None)


def pdf_paper(tmp_path, number, email=None, author=None):
    pdf_path = tmp_path / f'{number}.pdf'
    pdf_bytes = f'%PDF-1.4 fake test fixture {number}'.encode()
    pdf_path.write_bytes(pdf_bytes)
    author = author or f'Jane Author{number}'
    email = email or f'author{number}@college.edu'
    return {
        'title': f'Cancer research {number}', 'doi': f'10.1000/{number}',
        'authors': [author], 'file_path': str(pdf_path),
        '_test_pdf_bytes': pdf_bytes,
        '_test_pairs': [(author, email)],
    }


@pytest.mark.parametrize('topup', [False, True])
def test_pdf_contacts_obey_country_and_topup(worker, monkeypatch, tmp_path, topup):
    selected = pdf_paper(tmp_path, 1, 'jsmith@college.edu', 'Jane Smith')
    selected['author_countries'] = {'Jane Smith': ['IN']}
    selected['_test_pairs'] = [('Jane Smith', 'jsmith@college.edu')]
    # Make the first response full so the connector is eligible for pagination.
    initial = [{'title': f'Metadata paper {i}', 'doi': f'10.9999/{i}', 'emails': ['fake@college.edu']}
               for i in range(50)] if topup else [selected]
    calls = []

    def fetcher(*args, **kwargs):
        calls.append(kwargs)
        return initial if len(calls) == 1 else [selected]

    monkeypatch.setattr(worker, 'SOURCE_FETCHERS', {'pubmed': ('PubMed', fetcher)})
    monkeypatch.setattr(worker, 'extract_author_email_pairs', lambda path, authors: selected['_test_pairs'])
    worker._run_extraction_task('country-test', ['pubmed'], 'cancer', 1, {'countries': ['India']})
    result = worker.TASKS['country-test']['result']
    assert result['success']
    assert [row['Email ID'] for row in result['data']] == ['jsmith@college.edu']
    assert len(calls) == (2 if topup else 1)
    worker.save_new_emails_to_master.assert_called_once()
    assert (Path(worker.EXCEL_BASE_DIR) / result['download_file']).exists()


def test_metadata_only_and_non_pdf_records_are_not_counted(worker, monkeypatch, tmp_path):
    record = {'title': 'Metadata only paper', 'doi': '10.1000/meta',
              'authors': ['Jane Smith'], 'emails': ['jsmith@college.edu']}
    fake = tmp_path / 'not-a-pdf.pdf'
    fake.write_text('HTML metadata jsmith@college.edu')
    record['file_path'] = str(fake)
    monkeypatch.setattr(worker, 'SOURCE_FETCHERS', {'pubmed': ('PubMed', lambda *a, **kw: [record])})
    worker._run_extraction_task('country-test', ['pubmed'], 'cancer', 1, {})
    result = worker.TASKS['country-test']['result']
    assert not result['success']
    assert result['data'] == []
    assert result['shortfall'] == 1
    worker.save_new_emails_to_master.assert_not_called()


def test_email_on_later_pdf_page_is_extracted(worker, monkeypatch, tmp_path):
    class Page:
        def __init__(self, text):
            self.text = text
        def extract_text(self, layout=True):
            return self.text

    class Pdf:
        pages = [Page('Introduction'), Page('Methods'), Page('Correspondence: jsmith@university.edu')]
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    monkeypatch.setattr(worker.pdfplumber, 'open', lambda _path: Pdf())
    results = worker.extract_author_email_pairs(str(tmp_path / 'valid.pdf'), ['Jane Smith'])
    assert ('Jane Smith', 'jsmith@university.edu') in results


def test_selected_then_unselected_distinct_connectors_fill_exact_count(worker, monkeypatch, tmp_path):
    metadata = {'title': 'Index record', 'doi': '10.1000/meta', 'emails': ['fake@college.edu']}
    papers = [pdf_paper(tmp_path, i) for i in range(1, 4)]
    selected_fetch = Mock(return_value=[metadata])
    expanded_fetch = Mock(return_value=papers)
    # Different labels backed by one function are one connector and are called once.
    monkeypatch.setattr(worker, 'SOURCE_FETCHERS', {
        'pubmed': ('PubMed', selected_fetch),
        'pmc': ('PMC alias', selected_fetch),
        'openalex': ('OpenAlex', expanded_fetch),
    })
    monkeypatch.setattr(worker, 'extract_author_email_pairs', lambda path, authors: next(
        paper['_test_pairs'] for paper in papers if paper['_test_pdf_bytes'] == path
    ))
    worker._run_extraction_task('country-test', ['pubmed'], 'cancer', 2, {})
    result = worker.TASKS['country-test']['result']
    assert result['success']
    assert len(result['data']) == 2
    assert len({row['Email ID'] for row in result['data']}) == 2
    assert selected_fetch.call_count == expanded_fetch.call_count == 1


def test_small_target_uses_small_batch_and_stops_at_target(worker, monkeypatch, tmp_path):
    papers = [pdf_paper(tmp_path, i) for i in range(10, 13)]
    selected_fetch = Mock(return_value=papers)
    later_fetch = Mock(return_value=[])
    monkeypatch.setattr(worker, 'SOURCE_FETCHERS', {
        'pubmed': ('PubMed', selected_fetch), 'openalex': ('OpenAlex', later_fetch),
    })
    monkeypatch.setattr(worker, 'extract_author_email_pairs', lambda path, authors: next(
        paper['_test_pairs'] for paper in papers if paper['_test_pdf_bytes'] == path
    ))
    worker._run_extraction_task('country-test', ['pubmed'], 'cancer', 1, {})
    result = worker.TASKS['country-test']['result']
    assert result['success']
    assert len(result['data']) == 1
    assert selected_fetch.call_args.args[1] == 5
    later_fetch.assert_not_called()


def test_failed_source_switches_to_next_without_retries(worker, monkeypatch, tmp_path):
    paper = pdf_paper(tmp_path, 31)
    failed_fetch = Mock(side_effect=RuntimeError("HTTP 429"))
    working_fetch = Mock(return_value=[paper])
    monkeypatch.setattr(worker, 'SOURCE_FETCHERS', {
        'failed': ('Unavailable source', failed_fetch),
        'working': ('Working source', working_fetch),
    })
    monkeypatch.setattr(
        worker, 'extract_author_email_pairs',
        lambda path, authors: paper['_test_pairs'],
    )

    worker._run_extraction_task('country-test', ['failed'], 'cancer', 1, {})
    result = worker.TASKS['country-test']['result']

    assert result['success']
    assert result['data'][0]['Email ID'] == 'author31@college.edu'
    failed_fetch.assert_called_once()
    working_fetch.assert_called_once()


def test_top_up_prioritizes_the_source_with_higher_contact_yield(worker, monkeypatch, tmp_path):
    papers = [pdf_paper(tmp_path, index) for index in range(41, 44)]
    metadata_only = {'title': 'Metadata result', 'doi': '10.9999/meta'}
    source_calls = []

    def lower_yield_source(*args, offset=None, **kwargs):
        source_calls.append(('low', offset))
        if offset is None:
            return [metadata_only]
        pytest.fail('A higher-yield source should fill the target first')

    def higher_yield_source(*args, offset=None, **kwargs):
        source_calls.append(('high', offset))
        if offset is None:
            return [papers[0]]
        return papers[1:]

    monkeypatch.setattr(worker, 'SOURCE_FETCHERS', {
        'low': ('Low-yield source', lower_yield_source),
        'high': ('High-yield source', higher_yield_source),
    })
    paper_by_bytes = {paper['_test_pdf_bytes']: paper for paper in papers}
    monkeypatch.setattr(
        worker, 'extract_author_email_pairs',
        lambda pdf_bytes, authors: paper_by_bytes[pdf_bytes]['_test_pairs'],
    )

    worker._run_extraction_task('country-test', ['low'], 'cancer', 3, {})
    result = worker.TASKS['country-test']['result']

    assert result['success']
    assert [key for key, _ in source_calls] == ['low', 'high', 'high']


def test_shortfall_after_exhaustion_is_explicit(worker, monkeypatch, tmp_path):
    paper = pdf_paper(tmp_path, 1)
    papers = [paper]
    monkeypatch.setattr(worker, 'SOURCE_FETCHERS', {'pubmed': ('PubMed', lambda *a, **kw: papers)})
    monkeypatch.setattr(worker, 'extract_author_email_pairs', lambda path, authors: paper['_test_pairs'])
    worker._run_extraction_task('country-test', ['pubmed'], 'cancer', 3, {})
    result = worker.TASKS['country-test']['result']
    assert not result['success']
    assert result['total_records'] == 1
    assert result['shortfall'] == 2
    assert 'found 1 of 3' in result['message']


def test_short_page_advances_by_requested_window(worker, monkeypatch, tmp_path):
    first = pdf_paper(tmp_path, 21)
    second = pdf_paper(tmp_path, 22)
    calls = []

    def paged_fetcher(*args, **kwargs):
        calls.append(kwargs)
        return [first] if len(calls) == 1 else [second]

    monkeypatch.setattr(worker, 'SOURCE_FETCHERS', {'pubmed': ('PubMed', paged_fetcher)})
    monkeypatch.setattr(worker, 'extract_author_email_pairs', lambda path, authors: next(
        paper['_test_pairs'] for paper in (first, second) if paper['_test_pdf_bytes'] == path
    ))

    worker._run_extraction_task('country-test', ['pubmed'], 'cancer', 2, {})
    result = worker.TASKS['country-test']['result']

    assert result['success']
    assert len(result['data']) == 2
    assert calls[0].get('offset', 0) == 0
    assert calls[1]['offset'] == 5


@pytest.mark.parametrize('data', [
    {'topic': 'cancer', 'countries[]': 'Atlantis'},
    {'topic': 'cancer', 'year_from': '2026', 'year_to': '2020'},
])
def test_invalid_filters_rejected_before_start(data):
    response = application.app.test_client().post('/start-extraction', data=data)
    assert response.status_code == 400
