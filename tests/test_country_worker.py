import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'WS2.0'))
import app as application


@pytest.fixture
def worker(monkeypatch, tmp_path):
    monkeypatch.setattr(application, 'PDFS_BASE_DIR', str(tmp_path / 'pdf'))
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
    second = pdf_paper(tmp_path, 2, 'second@college.edu', 'John Smith')
    second['author_countries'] = {'John Smith': ['IN']}
    second['_test_pairs'] = [('John Smith', 'second@college.edu')]
    # The first page yields one contact; top-up should stay on that productive source.
    initial = ([selected] + [
        {'title': f'Metadata paper {i}', 'doi': f'10.9999/{i}', 'emails': ['fake@college.edu']}
        for i in range(49)
    ]) if topup else [selected]
    calls = []

    def fetcher(*args, **kwargs):
        calls.append(kwargs)
        return initial if len(calls) == 1 else [second]

    monkeypatch.setattr(worker, 'SOURCE_FETCHERS', {'pubmed': ('PubMed', fetcher)})
    papers_by_bytes = {
        selected['_test_pdf_bytes']: selected,
        second['_test_pdf_bytes']: second,
    }
    monkeypatch.setattr(
        worker, 'extract_author_email_pairs',
        lambda pdf_bytes, authors: papers_by_bytes[pdf_bytes]['_test_pairs'],
    )
    target = 2 if topup else 1
    worker._run_extraction_task('country-test', ['pubmed'], 'cancer', target, {'countries': ['India']})
    result = worker.TASKS['country-test']['result']
    assert result['success']
    expected = ['jsmith@college.edu', 'second@college.edu'] if topup else ['jsmith@college.edu']
    assert [row['Email ID'] for row in result['data']] == expected
    assert len(calls) == (2 if topup else 1)
    assert worker.save_new_emails_to_master.call_count == (2 if topup else 1)
    assert result['download_file'] is None
    assert not list(tmp_path.rglob('*.xlsx'))


def test_selecting_all_supported_countries_means_worldwide(worker, monkeypatch, tmp_path):
    paper = pdf_paper(tmp_path, 70)
    fetch_calls = []

    def fetcher(*args, **kwargs):
        fetch_calls.append(kwargs)
        return [paper]

    monkeypatch.setattr(worker, 'SOURCE_FETCHERS', {'arxiv': ('arXiv', fetcher)})
    monkeypatch.setattr(
        worker, 'extract_author_email_pairs',
        lambda pdf_bytes, authors: paper['_test_pairs'],
    )

    worker._run_extraction_task(
        'country-test', ['arxiv'], 'ecology', 1,
        {'countries': list(worker.COUNTRY_CODES)},
    )

    result = worker.TASKS['country-test']['result']
    assert result['success']
    assert [row['Email ID'] for row in result['data']] == ['author70@college.edu']
    assert fetch_calls[0]['filters']['countries'] == []


def test_zero_contact_first_page_does_not_exhaust_source(worker, monkeypatch, tmp_path):
    paper = pdf_paper(tmp_path, 71)
    calls = []
    metadata_only = {
        'title': 'Metadata only paper', 'doi': '10.1000/meta',
        'authors': ['Jane Smith'], 'emails': ['unrelated@college.edu'],
    }

    def fetcher(*args, **kwargs):
        calls.append(kwargs)
        return [metadata_only] if len(calls) == 1 else [paper]

    monkeypatch.setattr(worker, 'SOURCE_FETCHERS', {'pubmed': ('PubMed', fetcher)})
    monkeypatch.setattr(
        worker, 'extract_author_email_pairs',
        lambda pdf_bytes, authors: paper['_test_pairs'],
    )

    worker._run_extraction_task('country-test', ['pubmed'], 'ecology', 1, {})

    result = worker.TASKS['country-test']['result']
    assert result['success']
    assert [row['Email ID'] for row in result['data']] == ['author71@college.edu']
    assert len(calls) == 2


def test_worker_removes_pdf_and_does_not_create_excel(worker, monkeypatch, tmp_path):
    monkeypatch.setenv('KEEP_DOWNLOADED_PDFS', '1')
    extracted_paper = {}

    def source(topic, limit, target_dir, **kwargs):
        pdf_path = Path(target_dir) / 'temporary-paper.pdf'
        pdf_path.write_bytes(b'%PDF-1.4 temporary')
        paper = {
            'title': 'Cancer research cleanup',
            'doi': '10.1000/cleanup',
            'authors': ['Jane Cleanup'],
            'file_path': str(pdf_path),
        }
        extracted_paper['path'] = pdf_path
        return [paper]

    monkeypatch.setattr(worker, 'SOURCE_FETCHERS', {'pubmed': ('PubMed', source)})
    monkeypatch.setattr(
        worker, 'extract_author_email_pairs',
        lambda pdf_bytes, authors: [('Jane Cleanup', 'cleanup@college.edu')],
    )

    worker._run_extraction_task('country-test', ['pubmed'], 'cancer', 1, {})
    result = worker.TASKS['country-test']['result']

    assert result['success']
    assert not extracted_paper['path'].exists()
    assert not list(tmp_path.rglob('*.xlsx'))
    assert result['download_file'] is None


def test_worker_removes_processed_pdfs_in_pairs(worker, monkeypatch, tmp_path):
    pdf_paths = []

    def source(topic, limit, target_dir, **kwargs):
        papers = []
        for number in range(1, 4):
            pdf_path = Path(target_dir) / f'pair-{number}.pdf'
            pdf_path.write_bytes(f'%PDF-1.4 temporary {number}'.encode())
            pdf_paths.append(pdf_path)
            papers.append({
                'title': f'Cancer research pair {number}',
                'doi': f'10.1000/pair-{number}',
                'authors': [f'Jane Pair{number}'],
                'file_path': str(pdf_path),
            })
        return papers

    extraction_states = []

    def extract_pairs(_pdf_bytes, _authors):
        extraction_states.append([path.exists() for path in pdf_paths])
        number = len(extraction_states)
        return [(f'Jane Pair{number}', f'pair{number}@college.edu')]

    monkeypatch.setattr(worker, 'SOURCE_FETCHERS', {'pubmed': ('PubMed', source)})
    monkeypatch.setattr(worker, 'extract_author_email_pairs', extract_pairs)

    worker._run_extraction_task('country-test', ['pubmed'], 'cancer', 3, {})

    assert extraction_states == [
        [True, True, True],
        [True, True, True],
        [False, False, True],
    ]
    assert all(not path.exists() for path in pdf_paths)


def test_metadata_only_and_non_pdf_records_are_not_counted(worker, monkeypatch, tmp_path):
    record = {'title': 'Metadata only paper', 'doi': '10.1000/meta',
              'authors': ['Jane Smith'], 'emails': ['unrelated@college.edu']}
    fake = tmp_path / 'not-a-pdf.pdf'
    fake.write_text('HTML metadata unrelated@college.edu')
    record['file_path'] = str(fake)
    monkeypatch.setattr(worker, 'SOURCE_FETCHERS', {'pubmed': ('PubMed', lambda *a, **kw: [record])})
    worker._run_extraction_task('country-test', ['pubmed'], 'cancer', 1, {})
    result = worker.TASKS['country-test']['result']
    assert not result['success']
    assert result['data'] == []
    assert result['shortfall'] == 1
    worker.save_new_emails_to_master.assert_not_called()


def test_worker_uses_author_linked_metadata_without_parsing_pdf(worker, monkeypatch, tmp_path):
    pdf_path = tmp_path / 'metadata-first.pdf'
    pdf_path.write_bytes(b'%PDF-1.4 should not be parsed')
    record = {
        'title': 'Metadata contact study',
        'doi': '10.1000/metadata-first',
        'authors': ['Jane Smith'],
        'emails': ['jane.smith@college.edu'],
        'email_authors': {'jane.smith@college.edu': 'Jane Smith'},
        'file_path': str(pdf_path),
    }
    monkeypatch.setattr(
        worker, 'SOURCE_FETCHERS',
        {'metadata': ('Metadata source', lambda *args, **kwargs: [record])},
    )
    parse_pdf = Mock(side_effect=AssertionError('PDF parser should not be needed'))
    monkeypatch.setattr(worker, 'extract_author_email_pairs', parse_pdf)

    worker._run_extraction_task('country-test', ['metadata'], 'cancer', 1, {})

    result = worker.TASKS['country-test']['result']
    assert result['success']
    assert result['data'][0]['Email ID'] == 'jane.smith@college.edu'
    parse_pdf.assert_not_called()
    assert not pdf_path.exists()


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


def test_openrouter_pdf_match_is_used_only_for_text_emails(worker, monkeypatch):
    class Page:
        def extract_text(self, layout=True):
            return "Jane Smith\nCorresponding author: jsmith@university.edu"

    class Pdf:
        pages = [Page()]

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(worker.pdfplumber, 'open', lambda _source: Pdf())
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')
    monkeypatch.setattr(
        worker,
        'extract_with_openrouter',
        lambda _text, _key: [
            {'name': 'Jane Smith', 'email': 'jsmith@university.edu'},
            {'name': 'Fabricated Author', 'email': 'fabricated@university.edu'},
        ],
    )

    results = worker.extract_author_email_pairs(b'%PDF-test', ['Jane Smith'])

    assert ('Jane Smith', 'jsmith@university.edu') in results
    assert not any(email == 'fabricated@university.edu' for _, email in results)


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
    assert selected_fetch.call_args.args[1] == 1
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


def test_source_without_pdf_contacts_is_not_retried_before_fallback(worker, monkeypatch, tmp_path):
    paper = pdf_paper(tmp_path, 32)
    no_contact_source = Mock(return_value=[{
        'title': 'Metadata-only result',
        'doi': '10.9999/metadata-only',
        'emails': ['not-counted@college.edu'],
    }])
    working_source = Mock(return_value=[paper])
    monkeypatch.setattr(worker, 'SOURCE_FETCHERS', {
        'metadata': ('Metadata-only source', no_contact_source),
        'working': ('Working source', working_source),
    })
    monkeypatch.setattr(
        worker, 'extract_author_email_pairs',
        lambda pdf_bytes, authors: paper['_test_pairs'],
    )

    worker._run_extraction_task('country-test', ['metadata'], 'cancer', 1, {})
    result = worker.TASKS['country-test']['result']

    assert result['success']
    assert result['data'][0]['Email ID'] == 'author32@college.edu'
    no_contact_source.assert_called_once()
    working_source.assert_called_once()


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


def test_productive_source_is_topped_up_before_fallback(worker, monkeypatch, tmp_path):
    papers = [pdf_paper(tmp_path, index) for index in range(51, 54)]
    productive_calls = []

    def productive_source(*args, offset=None, **kwargs):
        productive_calls.append(offset)
        return [papers[0]] if offset is None else papers[1:]

    fallback_source = Mock(return_value=[])
    monkeypatch.setattr(worker, 'SOURCE_FETCHERS', {
        'productive': ('Productive source', productive_source),
        'fallback': ('Fallback source', fallback_source),
    })
    paper_by_bytes = {paper['_test_pdf_bytes']: paper for paper in papers}
    monkeypatch.setattr(
        worker, 'extract_author_email_pairs',
        lambda pdf_bytes, authors: paper_by_bytes[pdf_bytes]['_test_pairs'],
    )

    worker._run_extraction_task('country-test', ['productive'], 'cancer', 3, {})
    result = worker.TASKS['country-test']['result']

    assert result['success']
    assert productive_calls == [None, 2]
    fallback_source.assert_not_called()


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
    assert calls[1]['offset'] == 1


@pytest.mark.parametrize('data', [
    {'topic': 'cancer', 'countries[]': 'Atlantis'},
    {'topic': 'cancer', 'year_from': '2026', 'year_to': '2020'},
    {'topic': 'cancer', 'max_papers': '0'},
    {'topic': 'cancer', 'max_papers': '-1'},
    {'topic': 'cancer', 'max_papers': 'not-a-number'},
])
def test_invalid_filters_rejected_before_start(data):
    response = application.app.test_client().post('/start-extraction', data=data)
    assert response.status_code == 400


def test_start_extraction_allows_five_concurrent_tasks(monkeypatch, tmp_path):
    leases = []

    class DeferredThread:
        def __init__(self, target, args, daemon):
            self.args = args

        def start(self):
            leases.append(self.args[-1])

    monkeypatch.setattr(application, 'LOCK_FILE_PREFIX', str(tmp_path / 'extraction_'))
    monkeypatch.setattr(application, 'DATA_LOCK_FILE', str(tmp_path / 'data.lock'))
    thread_stub = type('ThreadingStub', (), {'Thread': DeferredThread})()
    monkeypatch.setattr(application, 'threading', thread_stub)
    client = application.app.test_client()

    responses = [
        client.post('/start-extraction', data={'topic': f'topic-{index}'})
        for index in range(application.MAX_CONCURRENT_EXTRACTIONS)
    ]

    assert all(response.status_code == 200 for response in responses)
    assert len(set(lease[0] for lease in leases)) == application.MAX_CONCURRENT_EXTRACTIONS
    assert client.post('/start-extraction', data={'topic': 'sixth'}).status_code == 429

    for lease in leases:
        application._release_extraction_lock(lease)


def test_start_extraction_has_no_contact_target_maximum(monkeypatch, tmp_path):
    started = []

    class DeferredThread:
        def __init__(self, target, args, daemon):
            self.args = args

        def start(self):
            started.append(self.args)

    monkeypatch.setattr(application, 'LOCK_FILE_PREFIX', str(tmp_path / 'extraction_'))
    monkeypatch.setattr(application, 'DATA_LOCK_FILE', str(tmp_path / 'data.lock'))
    monkeypatch.setattr(
        application,
        'threading',
        type('ThreadingStub', (), {'Thread': DeferredThread})(),
    )
    response = application.app.test_client().post(
        '/start-extraction',
        data={'topic': 'cancer', 'max_papers': '1500'},
    )

    assert response.status_code == 200
    assert started[0][3] == 1500
    application._release_extraction_lock(started[0][-1])
    application.TASKS.pop(response.get_json()['task_id'], None)


def test_concurrent_master_csv_appends_are_not_lost(monkeypatch, tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    master_file = tmp_path / 'master.csv'
    attempted_file = tmp_path / 'attempted.txt'
    monkeypatch.setattr(application, 'MASTER_EMAIL_FILE', str(master_file))
    monkeypatch.setattr(application, 'ATTEMPTED_DOIS_FILE', str(attempted_file))
    monkeypatch.setattr(application, 'DATA_LOCK_FILE', str(tmp_path / 'data.lock'))
    rows = [
        {'Paper Title': f'Paper {index}', 'Author Name': f'Author {index}',
         'Email ID': f'author{index}@university.edu'}
        for index in range(40)
    ]

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(application.save_new_emails_to_master, ([row] for row in rows)))

    saved = application.pd.read_csv(master_file, encoding='utf-8-sig')
    assert len(saved) == len(rows)
    assert set(saved['Email ID']) == {row['Email ID'] for row in rows}

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(application._record_attempted_doi, (f'10.1234/{i}' for i in range(40))))
    assert len(attempted_file.read_text(encoding='utf-8').splitlines()) == 40
