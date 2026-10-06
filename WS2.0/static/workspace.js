'use strict';
const $ = id => document.getElementById(id);
const form = $('extractForm');
const sources = [
  { num: 1, id: 'plos', name: 'PLOS', category: 'Biomedical', mode: 'Public Library of Science search + PDF', checked: true },
  { num: 2, id: 'europepmc', name: 'Europe PMC', category: 'Biomedical', mode: 'Full-text biomedical records + PDFs', checked: true },
  { num: 3, id: 'elife', name: 'eLife', category: 'Biomedical', mode: 'Life sciences and medicine search + PDF', checked: true },
  { num: 4, id: 'openalex', name: 'OpenAlex', category: 'Global', mode: 'Global open-access research index', checked: true },
  { num: 5, id: 'arxiv', name: 'arXiv.org', category: 'Preprints', mode: 'Cornell University research archive', checked: true },
  { num: 6, id: 'biorxiv', name: 'bioRxiv / medRxiv', category: 'Preprints', mode: 'CSHL biology and medicine research', checked: true },
  { num: 7, id: 'crossref', name: 'Crossref', category: 'Global', mode: 'Multi-publisher DOI network', checked: true },
  { num: 8, id: 'pubmed', name: 'PubMed / NCBI', category: 'Biomedical', mode: 'NCBI biomedical literature index', checked: true },
  { num: 9, id: 'frontiers', name: 'Frontiers', category: 'Biomedical', mode: 'Frontiers publications via Europe PMC', checked: true },
  { num: 10, id: 'aha', name: 'AHA Journals', category: 'Biomedical', mode: 'AHA publications via Europe PMC', checked: true }
];
let records = [], running = false, toastTimer;
for (const src of sources) {
  const label = document.createElement('label');
  label.className = 'source-card';
  label.dataset.category = src.category;
  const input = document.createElement('input');
  input.type = 'checkbox';
  input.name = 'source_sites[]';
  input.value = src.id;
  input.checked = !!src.checked;

  const body = document.createElement('div');
  body.className = 'source-card-body';

  const row = document.createElement('div');
  row.className = 'source-card-top';

  const num = document.createElement('span');
  num.className = 'source-num';
  num.textContent = `#${src.num}`;

  const title = document.createElement('span');
  title.className = 'source-name';
  title.textContent = src.name;

  const cat = document.createElement('span');
  cat.className = `source-tag cat-${src.category.toLowerCase()}`;
  cat.textContent = src.category;

  row.append(num, title, cat);

  const mode = document.createElement('span');
  mode.className = 'source-mode';
  mode.textContent = src.mode;

  body.append(row, mode);
  label.append(input, body);
  $('sourceList').append(label);
}
const checkedValues = name => Array.from(form.querySelectorAll(`input[name="${name}[]"]:checked`), el => el.value);
function updateSelection() {
  const countries = checkedValues('countries');
  $('countrySummary').textContent = countries.length ? countries.join(' · ') : 'Worldwide · no country restriction';
  const selectedSources = checkedValues('source_sites');
  $('sourceCount').textContent = `${selectedSources.length} selected`;
  if ($('selectAllCheckbox')) {
    $('selectAllCheckbox').checked = (selectedSources.length === sources.length);
    $('selectAllCheckbox').indeterminate = (selectedSources.length > 0 && selectedSources.length < sources.length);
  }
  const types = checkedValues('article_types').length;
  $('typeCount').textContent = types ? `${types} selected` : 'All types';
}
form.addEventListener('change', updateSelection);
if ($('selectAllCheckbox')) {
  $('selectAllCheckbox').addEventListener('change', e => {
    const checked = e.target.checked;
    for (const el of form.querySelectorAll('[name="source_sites[]"]')) el.checked = checked;
    updateSelection();
  });
}
$('countrySearch').addEventListener('input', e => {
  const query = e.target.value.toLocaleLowerCase();
  for (const label of document.querySelectorAll('.country-option')) label.hidden = !label.textContent.toLocaleLowerCase().includes(query);
});
$('clearCountries').addEventListener('click', () => {
  for (const el of form.querySelectorAll('[name="countries[]"]')) el.checked = false;
  updateSelection();
});
if ($('selectAllCountries')) {
  $('selectAllCountries').addEventListener('click', () => {
    for (const el of form.querySelectorAll('[name="countries[]"]')) el.checked = true;
    updateSelection();
  });
}
if ($('selectAllTypes')) {
  $('selectAllTypes').addEventListener('click', () => {
    for (const el of form.querySelectorAll('[name="article_types[]"]')) el.checked = true;
    updateSelection();
  });
}
if ($('clearTypes')) {
  $('clearTypes').addEventListener('click', () => {
    for (const el of form.querySelectorAll('[name="article_types[]"]')) el.checked = false;
    updateSelection();
  });
}
for (const [id, checked] of [['selectSources', true], ['clearSources', false]]) {
  $(id).addEventListener('click', () => {
    for (const el of form.querySelectorAll('[name="source_sites[]"]')) el.checked = checked;
    updateSelection();
  });
}
if ($('selectFastSources')) {
  $('selectFastSources').addEventListener('click', () => {
    const fastSources = new Set(['plos', 'europepmc', 'elife', 'openalex', 'crossref', 'pubmed']);
    for (const el of form.querySelectorAll('[name="source_sites[]"]')) {
      el.checked = fastSources.has(el.value);
    }
    updateSelection();
  });
}
for (const btn of document.querySelectorAll('.source-filter-btn')) {
  btn.addEventListener('click', () => {
    const cat = btn.dataset.cat;
    for (const card of document.querySelectorAll('.source-card')) {
      const input = card.querySelector('input');
      if (input) input.checked = (card.dataset.category === cat);
    }
    updateSelection();
  });
}
for (const button of document.querySelectorAll('[data-topic]')) button.addEventListener('click', () => { $('topic').value = button.dataset.topic; $('topic').focus(); });
for (const button of document.querySelectorAll('[data-years]')) button.addEventListener('click', () => {
  const year = new Date().getFullYear(); $('yearTo').value = year; $('yearFrom').value = year - Number(button.dataset.years) + 1;
});
$('clearYears').addEventListener('click', () => { $('yearFrom').value = ''; $('yearTo').value = ''; });
function message(text) { $('messageBox').textContent = text; $('messageBox').hidden = !text; }
function toast(text) { clearTimeout(toastTimer); $('toast').textContent = text; $('toast').hidden = false; toastTimer = setTimeout(() => $('toast').hidden = true, 3000); }
async function copy(text) {
  try { await navigator.clipboard.writeText(text); toast('Emails copied'); }
  catch { toast('Clipboard access unavailable. Select and copy the email text.'); }
}
$('copyAll').addEventListener('click', () => copy(filteredRecords().map(r => r['Email ID']).join('\n')));
function filteredRecords() {
  const query = $('resultSearch').value.trim().toLocaleLowerCase();
  return records.filter(r => Object.values(r).some(value => String(value).toLocaleLowerCase().includes(query)));
}
function renderRows() {
  const visible = filteredRecords(); $('tableBody').replaceChildren();
  visible.forEach((row, index) => {
    const tr = document.createElement('tr');
    for (const [text, className] of [[String(index + 1), ''], [row['Paper Title'], 'publication-cell'], [row['Author Name'], 'author-cell']]) {
      const td = document.createElement('td'); td.textContent = text; td.className = className; tr.append(td);
    }
    const td = document.createElement('td'); td.className = 'email-cell';
    const emailVal = (row['Email ID'] || '').trim();
    if (emailVal && emailVal.toLowerCase() !== 'n/a') {
      const a = document.createElement('a'); a.textContent = emailVal; a.href = `mailto:${emailVal}`;
      const button = document.createElement('button'); button.type = 'button'; button.className = 'copy-email'; button.textContent = 'Copy email'; button.setAttribute('aria-label', `Copy ${emailVal}`); button.addEventListener('click', () => copy(emailVal));
      td.append(a, button);
    } else {
      const span = document.createElement('span'); span.textContent = 'N/A'; span.style.color = 'var(--text-muted, #888)';
      td.append(span);
    }
    tr.append(td); $('tableBody').append(tr);
  });
  $('noMatches').hidden = visible.length !== 0;
  $('visibleCount').textContent = `${visible.length} of ${records.length} contacts`;
}
$('resultSearch').addEventListener('input', renderRows);
function setBusy(busy) {
  running = busy;
  for (const control of form.querySelectorAll('input, button')) control.disabled = busy;
  $('submitBtn').firstElementChild.textContent = busy ? 'Searching literature…' : 'Find author contacts';
  $('statusTag').textContent = busy ? 'Search in progress' : 'Ready to search';
  $('statusTag').className = busy ? 'status-tag busy' : 'status-tag';
}
async function getJSON(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let text = `Request failed (${response.status}). Try again.`;
    try { const body = await response.json(); text = body.error || body.message || text; } catch {}
    throw new Error(text);
  }
  return response.json();
}
function showResults(result) {
  const seenEmails = new Set();
  const seenPairs = new Set();
  records = (result.data || []).filter(row => {
    if (!['Paper Title', 'Author Name', 'Email ID'].every(key => typeof row[key] === 'string' && row[key].trim())) return false;
    const title = row['Paper Title'].trim().toLowerCase();
    const author = row['Author Name'].trim().toLowerCase();
    const pairKey = `${title}:::${author}`;
    if (seenPairs.has(pairKey)) return false;

    const email = row['Email ID'].trim().toLowerCase();
    const isEmail = /^[\w.%+\-]+@[\w.\-]+\.[a-z]{2,}$/i.test(email);
    if (isEmail) {
      if (seenEmails.has(email)) return false;
      seenEmails.add(email);
    }
    seenPairs.add(pairKey);
    return true;
  });
  $('resultCount').textContent = records.length; $('navCount').textContent = records.length;
  $('resultTools').hidden = !records.length; $('tableWrap').hidden = !records.length;
  $('emptyState').hidden = !!records.length;
  if (result.download_file) {
    $('downloadLink').href = `/download/${encodeURIComponent(result.download_file)}`;
    $('downloadLink').setAttribute('download', result.download_file);
    $('downloadLink').hidden = false;
  } else {
    $('downloadLink').hidden = true;
  }
  $('statusTag').textContent = records.length ? 'Search complete' : 'No contacts found'; $('statusTag').className = 'status-tag done';
  if (result.message) message(result.message);
  renderRows();
}
form.addEventListener('submit', async event => {
  event.preventDefault(); if (running) return;
  message('');
  if (!checkedValues('source_sites').length) { $('sourceDetails').open = true; message('Select at least one repository to search.'); return; }
  if (!$('topic').value.trim()) { $('topic').focus(); return; }
  if ($('yearFrom').value && $('yearTo').value && Number($('yearFrom').value) > Number($('yearTo').value)) { message('The start year must be before the end year.'); $('yearFrom').focus(); return; }
  const data = new FormData(form), countries = checkedValues('countries');
  if ($('searchContext')) {
    $('searchContext').textContent = `${$('topic').value.trim()} / ${countries.join(', ') || 'Worldwide'} / Target: ${$('maxPapers').value} unique email contacts`;
    $('searchContext').hidden = false;
  }
  records = []; $('resultSearch').value = ''; $('resultCount').textContent = '0'; $('navCount').textContent = '0'; $('visibleCount').textContent = '';
  $('resultTools').hidden = true; $('tableWrap').hidden = true; $('emptyState').hidden = true;
  $('progressBox').hidden = false; $('statusText').textContent = 'Preparing your search…'; $('percentage').textContent = '0%'; $('progressBar').style.width = '0%';
  if ($('etaTime')) $('etaTime').textContent = 'Est. ~15s';
  if ($('elapsedCounter')) $('elapsedCounter').textContent = 'Elapsed: 0s';
  const startTime = Date.now();
  setBusy(true);
  try {
    const {task_id} = await getJSON('/start-extraction', {method: 'POST', body: data});
    if (!task_id) throw new Error('The search could not be started. Try again.');
    // Sequential polling with live ETA countdown
    let failures = 0;
    while (true) {
      let status;
      try { status = await getJSON(`/status/${task_id}`); failures = 0; }
      catch (error) { if (++failures >= 3) throw error; await new Promise(resolve => setTimeout(resolve, 2000)); continue; }
      const percentage = Math.max(0, Math.min(100, Number(status.percentage) || 0));
      $('statusText').textContent = status.progress || 'Searching selected repositories…';
      $('percentage').textContent = `${percentage}%`; $('progressBar').style.width = `${percentage}%`;
      $('progressDetail').textContent = `${status.contacts_found || 0} / ${status.requested_count || 0} unique verified contacts · ${status.papers_searched || 0} papers · ${status.pdfs_parsed || 0} PDFs parsed · ${status.sources_remaining || 0} sources left`;

      // Live Elapsed & ETA update
      const elapsedSec = Math.floor((Date.now() - startTime) / 1000);
      if ($('elapsedCounter')) $('elapsedCounter').textContent = `Elapsed: ${elapsedSec}s`;

      if ($('etaTime')) {
        const eta = status.eta_seconds;
        if (typeof eta === 'number' && eta > 0) {
          $('etaTime').textContent = eta < 60 ? `Est. ~${eta}s` : `Est. ~${Math.ceil(eta / 60)}m`;
        } else if (percentage >= 90) {
          $('etaTime').textContent = 'Finishing up…';
        } else {
          $('etaTime').textContent = 'Calculating…';
        }
      }

      if (status.status === 'done' || status.status === 'error') {
        const result = await getJSON(`/result/${task_id}`);
        setBusy(false); $('progressBox').hidden = true; showResults(result);
        if (status.status === 'error') { message(result.message || 'Search failed. Try fewer repositories.'); $('statusTag').textContent = 'Search interrupted'; }
        return;
      }
      await new Promise(resolve => setTimeout(resolve, 500));
    }
  } catch (error) { message(error.message); setBusy(false); $('progressBox').hidden = true; $('emptyState').hidden = false; $('statusTag').textContent = 'Search interrupted'; }
});
updateSelection();
