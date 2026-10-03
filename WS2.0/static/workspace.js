'use strict';
const $ = id => document.getElementById(id);
const form = $('extractForm');
const sources = [
  ['pubmed', 'PubMed / NCBI', true], ['europepmc', 'Europe PMC', true], ['openalex', 'OpenAlex', true],
  ['plos', 'PLOS ONE'], ['crossref', 'Crossref'], ['semanticscholar', 'Semantic Scholar'],
  ['biorxiv', 'bioRxiv / medRxiv'], ['arxiv', 'arXiv'], ['elife', 'eLife'],
  ['preprints', 'Preprint indexes'], ['sciencedirect', 'ScienceDirect'], ['imedpub', 'iMedPub']
];
let records = [], running = false, toastTimer;
for (const [value, name, selected] of sources) {
  const label = document.createElement('label'), input = document.createElement('input');
  input.type = 'checkbox'; input.name = 'source_sites[]'; input.value = value; input.checked = !!selected;
  label.append(input, document.createTextNode(name)); $('sourceList').append(label);
}
const checkedValues = name => Array.from(form.querySelectorAll(`input[name="${name}[]"]:checked`), el => el.value);
function updateSelection() {
  const countries = checkedValues('countries');
  $('countrySummary').textContent = countries.length ? countries.join(' · ') : 'Worldwide · no country restriction';
  $('sourceCount').textContent = `${checkedValues('source_sites').length} selected`;
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
for (const [id, checked] of [['selectSources', true], ['clearSources', false]]) {
  $(id).addEventListener('click', () => {
    for (const el of form.querySelectorAll('[name="source_sites[]"]')) el.checked = checked;
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
    const a = document.createElement('a'); a.textContent = row['Email ID']; a.href = `mailto:${row['Email ID']}`;
    const button = document.createElement('button'); button.type = 'button'; button.className = 'copy-email'; button.textContent = 'Copy email'; button.setAttribute('aria-label', `Copy ${row['Email ID']}`); button.addEventListener('click', () => copy(row['Email ID']));
    td.append(a, button); tr.append(td); $('tableBody').append(tr);
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
  const seen = new Set();
  records = (result.data || []).filter(row => {
    if (!['Paper Title', 'Author Name', 'Email ID'].every(key => typeof row[key] === 'string' && row[key].trim())) return false;
    const email = row['Email ID'].trim().toLowerCase();
    if (!/^[\w.%+\-]+@[\w.\-]+\.[a-z]{2,}$/i.test(email) || seen.has(email)) return false;
    seen.add(email); return true;
  });
  $('resultCount').textContent = records.length; $('navCount').textContent = records.length;
  $('resultTools').hidden = !records.length; $('tableWrap').hidden = !records.length;
  $('emptyState').hidden = !!records.length;
  $('downloadLink').hidden = !result.download_file;
  if (result.download_file) $('downloadLink').href = `/download/${encodeURIComponent(result.download_file)}`;
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
  $('searchContext').textContent = `${$('topic').value.trim()} / ${countries.join(', ') || 'Worldwide'} / Up to ${$('maxPapers').value} contacts`;
  $('searchContext').hidden = false;
  records = []; $('resultSearch').value = ''; $('resultCount').textContent = '0'; $('navCount').textContent = '0'; $('visibleCount').textContent = '';
  $('resultTools').hidden = true; $('tableWrap').hidden = true; $('emptyState').hidden = true;
  $('progressBox').hidden = false; $('statusText').textContent = 'Preparing your search…'; $('percentage').textContent = '0%'; $('progressBar').style.width = '0%';
  setBusy(true);
  try {
    const {task_id} = await getJSON('/start-extraction', {method: 'POST', body: data});
    if (!task_id) throw new Error('The search could not be started. Try again.');
    // Sequential polling prevents overlapping requests and duplicate result delivery.
    let failures = 0;
    while (true) {
      let status;
      try { status = await getJSON(`/status/${task_id}`); failures = 0; }
      catch (error) { if (++failures >= 3) throw error; await new Promise(resolve => setTimeout(resolve, 3000)); continue; }
      const percentage = Math.max(0, Math.min(100, Number(status.percentage) || 0));
      $('statusText').textContent = status.progress || 'Searching selected repositories…';
      $('percentage').textContent = `${percentage}%`; $('progressBar').style.width = `${percentage}%`;
      $('progressDetail').textContent = `${status.contacts_found || 0} contacts found · Checking selected filters`;
      if (status.status === 'done' || status.status === 'error') {
        const result = await getJSON(`/result/${task_id}`);
        setBusy(false); $('progressBox').hidden = true; showResults(result);
        if (status.status === 'error') { message(result.message || 'Search failed. Try fewer repositories.'); $('statusTag').textContent = 'Search interrupted'; }
        return;
      }
      await new Promise(resolve => setTimeout(resolve, 2500));
    }
  } catch (error) { message(error.message); setBusy(false); $('progressBox').hidden = true; $('emptyState').hidden = false; $('statusTag').textContent = 'Search interrupted'; }
});
updateSelection();
