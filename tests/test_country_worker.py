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


def mixed_paper():
    return {'title': 'Cancer immunotherapy research', 'doi': '10.1234/test',
            'authors': ['Jane Smith', 'John Brown'],
            'emails': ['jsmith@college.edu', 'jbrown@college.edu'],
            'email_authors': {'jsmith@college.edu': 'Jane Smith', 'jbrown@college.edu': 'John Brown'},
            'author_countries': {'Jane Smith': ['IN'], 'John Brown': ['US']}}


@pytest.mark.parametrize('topup', [False, True])
def test_single_country_worker_including_topup(worker, monkeypatch, topup):
    fetcher = Mock(side_effect=[[], [mixed_paper()]] if topup else [[mixed_paper()]])
    monkeypatch.setattr(worker, 'SOURCE_FETCHERS', {'pubmed': ('PubMed', fetcher)})
    worker._run_extraction_task('country-test', ['pubmed'], 'cancer', 1, {'countries': ['India']})
    result = worker.TASKS['country-test']['result']
    assert result['success']
    assert [row['Email ID'] for row in result['data']] == ['jsmith@college.edu']
    assert fetcher.call_count == (2 if topup else 1)
    worker._record_attempted_doi.assert_not_called()
    worker.save_new_emails_to_master.assert_called_once()
    assert (Path(worker.EXCEL_BASE_DIR) / result['download_file']).exists()


def test_pdf_contacts_also_obey_country(worker, monkeypatch, tmp_path):
    paper = mixed_paper()
    paper.pop('emails')
    pdf = tmp_path / 'test.pdf'
    pdf.touch()
    paper['file_path'] = str(pdf)
    monkeypatch.setattr(worker, 'SOURCE_FETCHERS', {'pubmed': ('PubMed', lambda *a, **kw: [paper])})
    monkeypatch.setattr(worker, 'extract_author_email_pairs', lambda *a: [('John Brown', 'jbrown@college.edu'), ('Jane Smith', 'jsmith@college.edu')])
    worker._run_extraction_task('country-test', ['pubmed'], 'cancer', 1, {'countries': ['India']})
    assert [r['Author Name'] for r in worker.TASKS['country-test']['result']['data']] == ['Jane Smith']


def test_ambiguous_email_never_enters_worker_results(worker, monkeypatch):
    paper = mixed_paper()
    paper['ambiguous_emails'] = ['jsmith@college.edu']
    monkeypatch.setattr(worker, 'SOURCE_FETCHERS', {'pubmed': ('PubMed', lambda *a, **kw: [paper])})
    worker._run_extraction_task('country-test', ['pubmed'], 'cancer', 1, {'countries': ['India']})
    assert worker.TASKS['country-test']['result']['data'] == []
    worker.save_new_emails_to_master.assert_not_called()


@pytest.mark.parametrize('data', [
    {'topic': 'cancer', 'countries[]': 'Atlantis'},
    {'topic': 'cancer', 'year_from': '2026', 'year_to': '2020'},
])
def test_invalid_filters_rejected_before_start(data):
    response = application.app.test_client().post('/start-extraction', data=data)
    assert response.status_code == 400


def test_target_count_fulfillment(worker, monkeypatch):
    # Batch 1 returns 2 contacts (short of target 5)
    # Batch 2 returns 4 contacts (satisfying target of 5 with exact capping)
    batch1 = [
        {'title': f'Paper {i}', 'doi': f'10.1000/{i}',
         'authors': [f'Author {i}'],
         'emails': [f'author{i}@university.edu'],
         'email_authors': {f'author{i}@university.edu': f'Author {i}'}}
        for i in range(1, 3)
    ]
    batch2 = [
        {'title': f'Paper {i}', 'doi': f'10.1000/{i}',
         'authors': [f'Author {i}'],
         'emails': [f'author{i}@university.edu'],
         'email_authors': {f'author{i}@university.edu': f'Author {i}'}}
        for i in range(3, 7)
    ]
    fetcher = Mock(side_effect=[batch1, batch2])
    monkeypatch.setattr(worker, 'SOURCE_FETCHERS', {'pubmed': ('PubMed', fetcher)})
    worker._run_extraction_task('country-test', ['pubmed'], 'cancer', 5, {})
    result = worker.TASKS['country-test']['result']
    assert result['success']
    assert len(result['data']) == 5
    assert fetcher.call_count == 2
