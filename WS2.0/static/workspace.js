'use strict';
const $ = id => document.getElementById(id);
const form = $('extractForm');
const sources = [
  { num: 1, id: 'plos', name: 'PLOS', category: 'Biomedical', mode: 'Public Library of Science search + PDF', checked: true },
  { num: 2, id: 'europepmc', name: 'Europe PMC', category: 'Biomedical', mode: 'Full-text biomedical records + PDFs', checked: true },
  { num: 3, id: 'elife', name: 'eLife', category: 'Biomedical', mode: 'Life sciences and medicine search + PDF', checked: true },
  { num: 4, id: 'openalex', name: 'OpenAlex', category: 'Global', mode: 'Global open-access research index', checked: true },
  { num: 5, id: 'arxiv', name: 'arXiv.org', category: 'Preprints', mode: 'Cornell University research archive', checked: false },
  { num: 6, id: 'biorxiv', name: 'bioRxiv / medRxiv', category: 'Preprints', mode: 'CSHL biology and medicine research', checked: false },
  { num: 7, id: 'crossref', name: 'Crossref', category: 'Global', mode: 'Multi-publisher DOI network', checked: true },
  { num: 8, id: 'pubmed', name: 'PubMed / NCBI', category: 'Biomedical', mode: 'NCBI biomedical literature index', checked: true },
  { num: 9, id: 'frontiers', name: 'Frontiers', category: 'Biomedical', mode: 'Frontiers publications via Europe PMC', checked: false },
  { num: 10, id: 'aha', name: 'AHA Journals', category: 'Biomedical', mode: 'AHA publications via Europe PMC', checked: false }
];
const sourcePresets = {
  all: new Set(sources.map(source => source.id)),
  fast: new Set(['plos', 'europepmc', 'elife', 'openalex', 'crossref', 'pubmed']),
  Biomedical: new Set(sources.filter(source => source.category === 'Biomedical').map(source => source.id)),
  Preprints: new Set(sources.filter(source => source.category === 'Preprints').map(source => source.id)),
  Global: new Set(sources.filter(source => source.category === 'Global').map(source => source.id))
};
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
  if ($('sourcePreset')) {
    const selectedIds = new Set(selectedSources);
    const activePreset = Object.entries(sourcePresets).find(([, ids]) =>
      ids.size === selectedIds.size && [...ids].every(id => selectedIds.has(id))
    );
    $('sourcePreset').value = activePreset ? activePreset[0] : 'custom';
  }
  const types = checkedValues('article_types').length;
  $('typeCount').textContent = types ? `${types} selected` : 'All types';
}
form.addEventListener('change', updateSelection);
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
if ($('sourcePreset')) {
  $('sourcePreset').addEventListener('change', event => {
    const selectedIds = sourcePresets[event.target.value] || new Set();
    for (const input of form.querySelectorAll('[name="source_sites[]"]')) {
      input.checked = selectedIds.has(input.value);
    }
    updateSelection();
  });
}
if ($('clearSources')) {
  $('clearSources').addEventListener('click', () => {
    for (const input of form.querySelectorAll('[name="source_sites[]"]')) {
      input.checked = false;
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
async function downloadWorkbook(url, filename, options) {
  try {
    const response = await fetch(url, options);
    if (!response.ok) {
      let text = `Export failed (${response.status}). Try again.`;
      try { const body = await response.json(); text = body.error || body.message || text; } catch {}
      throw new Error(text);
    }
    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = objectUrl;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(objectUrl);
  } catch (error) {
    message(error.message);
  }
}
async function copy(text) {
  try { await navigator.clipboard.writeText(text); toast('Emails copied'); }
  catch { toast('Clipboard access unavailable. Select and copy the email text.'); }
}
$('copyAll').addEventListener('click', () => copy(filteredRecords().map(r => r['Email ID']).join('\n')));
$('downloadAllLink').addEventListener('click', event => {
  event.preventDefault();
  downloadWorkbook('/download/all', 'medscout_all_contacts.xlsx');
});
$('downloadLink').addEventListener('click', event => {
  event.preventDefault();
  downloadWorkbook('/download/current', 'medscout_search_results.xlsx', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({data: records})
  });
});
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
  $('downloadLink').hidden = !records.length;
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
  $('resultTools').hidden = true; $('tableWrap').hidden = true;
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
  } catch (error) { message(error.message); setBusy(false); $('progressBox').hidden = true; $('statusTag').textContent = 'Search interrupted'; }
});
updateSelection();
