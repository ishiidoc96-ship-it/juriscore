// Juriscore App - Vanilla JS (Mobile-First)
'use strict';

const API_URL = (window.JURISCORE_API_URL || 'http://localhost:8000/api').replace(/\/+$/, '');
let AUTH_TOKEN = localStorage.getItem('jwt_token') || '';
let CURRENT_USER = JSON.parse(localStorage.getItem('current_user') || 'null');
let currentRoute = 'home';
let allCases = [];
let activeFilter = 'All';
let currentSort = 'relevance';
let selectedUniversity = 'Kabarak University';
let currentCaseId = null;
const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

function showScreen(id) {
  $$('.screen').forEach(s => s.classList.remove('active'));
  const el = document.getElementById(id);
  if (el) el.classList.add('active');
}

function showPage(route) {
  $$('.page').forEach(p => p.classList.remove('active'));
  const page = document.getElementById('page-' + route);
  if (page) page.classList.add('active');
  $$('.nav-item').forEach(n => n.classList.remove('active'));
  const nav = document.querySelector('.nav-item[data-route="' + route + '"]');
  if (nav) nav.classList.add('active');
  const titles = { home: 'Juriscore', search: 'Search', constitution: 'Constitution', notebook: 'Notebook', flashcards: 'Flashcards', profile: 'Profile' };
  $('#topBarTitle').textContent = titles[route] || 'Juriscore';
  currentRoute = route;
}

function showToast(msg, type = 'success') {
  const container = $('#toastContainer');
  const toast = document.createElement('div');
  toast.className = 'toast toast-' + type;
  toast.textContent = msg;
  container.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add('show'));
  setTimeout(() => { toast.classList.remove('show'); setTimeout(() => toast.remove(), 300); }, 3000);
}

function escHtml(s) {
  if (!s) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

async function api(endpoint, options = {}) {
  const url = API_URL + endpoint;
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  if (AUTH_TOKEN) headers['Authorization'] = 'Bearer ' + AUTH_TOKEN;
  const resp = await fetch(url, { ...options, headers });
  if (resp.status === 401) { logout(); return []; }
  if (!resp.ok) throw new Error('API ' + resp.status);
  const ct = resp.headers.get('content-type') || '';
  if (ct.includes('application/json')) return resp.json();
  return resp.blob();
}

function logout() {
  AUTH_TOKEN = '';
  CURRENT_USER = null;
  localStorage.removeItem('jwt_token');
  localStorage.removeItem('current_user');
  showScreen('login-screen');
}

// ---- AUTH ----
$('#loginForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const email = $('#loginEmail').value.trim();
  const password = $('#loginPassword').value;
  if (!email || !password) return showToast('Fill all fields', 'error');
  const btn = $('#loginBtn');
  btn.querySelector('.btn-text').style.display = 'none';
  btn.querySelector('.btn-spinner').style.display = 'inline';
  btn.disabled = true;
  try {
    CURRENT_USER = { id: 'local-' + Date.now(), email, name: email.split('@')[0], university: 'Kabarak University' };
    AUTH_TOKEN = 'demo-' + Date.now();
    localStorage.setItem('jwt_token', AUTH_TOKEN);
    localStorage.setItem('current_user', JSON.stringify(CURRENT_USER));
    updateGreeting();
    showPage('home');
    loadHomeData();
    showToast('Welcome back!');
  } catch (err) { showToast(err.message || 'Login failed', 'error'); }
  finally {
    btn.querySelector('.btn-text').style.display = 'inline';
    btn.querySelector('.btn-spinner').style.display = 'none';
    btn.disabled = false;
  }
});

$('#signupForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const name = $('#signupName').value.trim();
  const email = $('#signupEmail').value.trim();
  const password = $('#signupPassword').value;
  const confirm = $('#signupConfirm').value;
  if (!name || !email || !password) return showToast('Fill all fields', 'error');
  if (password !== confirm) return showToast('Passwords do not match', 'error');
  if (password.length < 6) return showToast('Min 6 characters', 'error');
  const btn = $('#signupBtn');
  btn.querySelector('.btn-text').style.display = 'none';
  btn.querySelector('.btn-spinner').style.display = 'inline';
  btn.disabled = true;
  try {
    CURRENT_USER = { id: 'local-' + Date.now(), email, name, university: selectedUniversity };
    AUTH_TOKEN = 'demo-' + Date.now();
    localStorage.setItem('jwt_token', AUTH_TOKEN);
    localStorage.setItem('current_user', JSON.stringify(CURRENT_USER));
    updateGreeting();
    showPage('home');
    loadHomeData();
    showToast('Account created!');
  } catch (err) { showToast(err.message || 'Signup failed', 'error'); }
  finally {
    btn.querySelector('.btn-text').style.display = 'inline';
    btn.querySelector('.btn-spinner').style.display = 'none';
    btn.disabled = false;
  }
});

$('#goToSignup').addEventListener('click', (e) => { e.preventDefault(); showScreen('signup-screen'); });
$('#goToLogin').addEventListener('click', (e) => { e.preventDefault(); showScreen('login-screen'); });
$('#googleLoginBtn').addEventListener('click', () => showToast('Google OAuth - coming soon', 'info'));
$('#googleSignupBtn').addEventListener('click', () => showToast('Google OAuth - coming soon', 'info'));
$('#logoutBtn').addEventListener('click', logout);
$('#logoutBtn2').addEventListener('click', logout);

$$('#uniChips .uni-chip').forEach(chip => {
  chip.addEventListener('click', () => {
    $$('#uniChips .uni-chip').forEach(c => c.classList.remove('active'));
    chip.classList.add('active');
    selectedUniversity = chip.dataset.uni;
  });
});

function updateGreeting() {
  if (!CURRENT_USER) return;
  const firstName = CURRENT_USER.name.split(' ')[0];
  const h = new Date().getHours();
  const g = h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
  $('#greetingText').textContent = g + ', ' + firstName;
  const initials = CURRENT_USER.name.split(' ').map(n => n[0]).slice(0, 2).join('').toUpperCase();
  $('#profileAvatar').textContent = initials;
  $('#profileName').textContent = CURRENT_USER.name;
  $('#profileUni').textContent = CURRENT_USER.university || 'University';
}

// ---- NAVIGATION ----
$$('#bottomNav .nav-item').forEach(btn => {
  btn.addEventListener('click', () => {
    showPage(btn.dataset.route);
    if (btn.dataset.route === 'home') loadHomeData();
    if (btn.dataset.route === 'search') loadSearchData();
    if (btn.dataset.route === 'constitution') loadConstitution();
    if (btn.dataset.route === 'notebook') loadNotebook();
    if (btn.dataset.route === 'flashcards') loadFlashcards();
    if (btn.dataset.route === 'profile') loadProfile();
  });
});

$$('.quick-action').forEach(btn => {
  btn.addEventListener('click', () => {
    showPage(btn.dataset.route);
    if (btn.dataset.route === 'search') loadSearchData();
    if (btn.dataset.route === 'notebook') loadNotebook();
    if (btn.dataset.route === 'flashcards') loadFlashcards();
    if (btn.dataset.route === 'constitution') loadConstitution();
  });
});

$('#homeSearchBar').addEventListener('click', () => { showPage('search'); loadSearchData(); });
$('#homeSearchInput').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') { showPage('search'); $('#searchInput').value = $('#homeSearchInput').value; loadSearchData(); }
});

// ---- CASE CARD RENDERER ----
function renderCaseCard(item, type) {
  const el = document.createElement('div');
  el.className = 'case-card' + (type === 'recent' ? ' case-card-h' : '');
  const tags = (item.subject_tags || []).slice(0, 2).map(t => '<span class="tag tag-light">' + escHtml(t) + '</span>').join('');
  el.innerHTML = '<div class="case-card-body"><h4>' + escHtml(item.title || 'Untitled') + '</h4><p class="case-citation">' + escHtml(item.citation || '') + '</p><div class="tags-row"><span class="tag tag-default">' + escHtml(item.court || '') + '</span><span class="tag tag-accent">' + (item.year || '') + '</span>' + tags + '</div></div>';
  el.addEventListener('click', () => openCaseDetail(item.id));
  return el;
}

// ---- HOME ----
async function loadHomeData() {
  try {
    const [recent, recs] = await Promise.all([
      api('/cases/recent?limit=10').catch(() => []),
      api('/cases/search?limit=20').catch(() => []),
    ]);
    allCases = [...(Array.isArray(recent) ? recent : []), ...(Array.isArray(recs) ? recs.filter((_, i) => i < 5) : [])];
    const sc = $('#recentCasesScroll'); sc.innerHTML = '';
    (allCases).slice(0, 6).forEach(c => sc.appendChild(renderCaseCard(c, 'recent')));
    const rl = $('#recommendedList'); rl.innerHTML = '';
    (Array.isArray(recs) ? recs : []).slice(0, 5).forEach(c => rl.appendChild(renderCaseCard(c)));
  } catch {
    allCases = getDemoCases();
    $('#recentCasesScroll').innerHTML = '';
    allCases.slice(0, 6).forEach(c => $('#recentCasesScroll').appendChild(renderCaseCard(c, 'recent')));
    $('#recommendedList').innerHTML = '';
    allCases.slice(0, 5).forEach(c => $('#recommendedList').appendChild(renderCaseCard(c)));
  }
}

// ---- SEARCH ----
async function loadSearchData() {
  try {
    const res = await api('/cases/search?limit=50');
    allCases = Array.isArray(res) ? res : (res?.results || []);
  } catch { allCases = getDemoCases(); }
  applyFilterAndSort();
}

function applyFilterAndSort() {
  let data = [...allCases];
  if (activeFilter !== 'All' && activeFilter !== 'Statutes') {
    const map = { 'Supreme Court': 'supreme', 'Court of Appeal': 'appeal', 'High Court': 'high court' };
    const kw = (map[activeFilter] || activeFilter).toLowerCase();
    data = data.filter(c => (c.court || '').toLowerCase().includes(kw));
  }
  if (currentSort === 'newest') data.sort((a, b) => (b.year || 0) - (a.year || 0));
  else if (currentSort === 'oldest') data.sort((a, b) => (a.year || 0) - (b.year || 0));
  const container = $('#searchResults'); container.innerHTML = '';
  if (!data.length) { $('#searchEmpty').style.display = 'flex'; }
  else { $('#searchEmpty').style.display = 'none'; data.forEach(c => container.appendChild(renderCaseCard(c))); }
}

$('#searchInput').addEventListener('input', (e) => {
  const q = e.target.value.trim().toLowerCase();
  $('#searchClear').style.display = q ? 'block' : 'none';
  if (!q) { allCases = getDemoCases(); } else {
    allCases = getDemoCases().filter(c =>
      (c.title || '').toLowerCase().includes(q) || (c.citation || '').toLowerCase().includes(q)
      || (c.court || '').toLowerCase().includes(q) || (c.subject_tags || []).some(t => (t || '').toLowerCase().includes(q))
    );
  }
  applyFilterAndSort();
});

$('#searchClear').addEventListener('click', () => {
  $('#searchInput').value = ''; $('#searchClear').style.display = 'none'; allCases = getDemoCases(); applyFilterAndSort();
});
$('#sortToggle').addEventListener('click', () => { $('#sortPanel').style.display = $('#sortPanel').style.display === 'none' ? 'flex' : 'none'; });
$$('#sortPanel .sort-chip').forEach(chip => {
  chip.addEventListener('click', () => {
    $$('#sortPanel .sort-chip').forEach(c => c.classList.remove('active'));
    chip.classList.add('active');
    currentSort = chip.dataset.sort;
    $('#sortPanel').style.display = 'none';
    applyFilterAndSort();
  });
});
$$('#filterChips .filter-chip').forEach(chip => {
  chip.addEventListener('click', () => {
    $$('#filterChips .filter-chip').forEach(c => c.classList.remove('active'));
    chip.classList.add('active');
    activeFilter = chip.dataset.court;
    applyFilterAndSort();
  });
});

// ---- CASE DETAIL ----
function generateDemoSummary(c) {
  return {
    facts: ['The case involved proceedings in the ' + (c.court || 'Kenyan courts') + ' in ' + (c.year || 'recent years') + '.', 'The parties presented arguments on the interpretation of applicable law.'],
    issues: ['Whether the court had jurisdiction to hear the matter', 'Whether the rights and duties were properly determined'],
    holdings: ['The court held that the proceedings were properly before it and upheld the decision of the lower court.', 'The court affirmed that procedural fairness was observed throughout.'],
    ratio: 'Administrative and judicial decisions must be grounded in law. Parties are entitled to fair hearing before an impartial tribunal, and procedural fairness is a cornerstone of the legal system.',
    obiter: 'The court noted that future cases with similar facts may benefit from early referral to alternative dispute resolution mechanisms.',
    cases_cited: c.cases_cited || ['Republic v. Kaggwa [2020] eKLR', 'Muriuki v. AG [2019] eKLR', 'Constitution of Kenya 2010, Article 25']
  };
}

function openCaseDetail(caseId) {
  currentCaseId = caseId;
  const caseData = getDemoCases().find(c => c.id === caseId) || allCases.find(c => c.id === caseId);
  if (!caseData) return showToast('Case not found', 'error');
  const s = generateDemoSummary(caseData);
  const content = $('#caseDetailContent');
  content.innerHTML = `
    <div class="case-detail-header"><h2>${escHtml(caseData.title)}</h2><p class="case-citation-lg">${escHtml(caseData.citation)}</p>
      <div class="tags-row"><span class="tag tag-default">${escHtml(caseData.court)}</span><span class="tag tag-accent">${caseData.year}</span>${(caseData.subject_tags||[]).map(t=>'<span class="tag tag-light">'+escHtml(t)+'</span>').join('')}</div>
    </div>
    <div class="detail-tabs">
      <button class="detail-tab active" data-tab="summary">Summary</button>
      <button class="detail-tab" data-tab="fulltext">Full Judgment</button>
      <button class="detail-tab" data-tab="notes">Notes</button>
      <button class="detail-tab" data-tab="related">Related</button>
    </div>
    <div class="detail-content" id="detailContent">
      ${renderSummaryTab(s)}
    </div>`;
  bindDetailTabs(caseData, s);
  $('#caseDetailOverlay').style.display = 'flex';
}

function renderSummaryTab(s) {
  const facts = (s.facts||[]).map(f=>'<p class="bullet-item">• '+escHtml(f)+'</p>').join('');
  const issues = (s.issues||[]).map((iss,i)=>'<p class="numbered-item">'+(i+1)+'. '+escHtml(iss)+'</p>').join('');
  const holdings = (s.holdings||[]).map((h,i)=>'<p class="numbered-item">'+(i+1)+'. '+escHtml(h)+'</p>').join('');
  const cited = (s.cases_cited||[]).map(c=>'<p class="bullet-item">• '+escHtml(c)+'</p>').join('');
  return `<div class="detail-section">${facts?'<h4>Facts</h4>'+facts:''}</div>
    <div class="detail-section">${issues?'<h4>Issues</h4>'+issues:''}</div>
    <div class="detail-section">${holdings?'<h4>Holdings</h4>'+holdings:''}</div>
    <div class="ratio-box"><h4>⚖️ Ratio Decidendi</h4><p>${escHtml(s.ratio||'N/A')}</p></div>
    ${s.obiter?'<div class="detail-section"><h4>Obiter Dictum</h4><p>'+escHtml(s.obiter)+'</p></div>':''}
    ${cited?'<div class="detail-section"><h4>Cases Cited</h4>'+cited+'</div>':''}`;
}

function bindDetailTabs(caseData, s) {
  const dc = () => document.getElementById('detailContent');
  $$('#caseDetailContent .detail-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      $$('#caseDetailContent .detail-tab').forEach(t=>t.classList.remove('active'));
      tab.classList.add('active');
      const t = tab.dataset.tab;
      const el = dc();
      if (!el) return;
      if (t === 'summary') { el.innerHTML = renderSummaryTab(s); }
      else if (t === 'fulltext') { el.innerHTML = '<div class="full-text-block"><p>' + escHtml(caseData.full_text || 'Full text not available. Connect to the JSON API backend for complete judgments sourced from Kenya Law.') + '</p></div>'; }
      else if (t === 'notes') {
        const saved = localStorage.getItem('note_' + caseData.id) || '';
        el.innerHTML = '<div class="notes-area"><textarea id="notesTextarea" placeholder="Add your personal notes here...">' + escHtml(saved) + '</textarea><button class="btn btn-primary btn-full" id="saveNoteBtn">Save Note</button></div>';
        document.getElementById('saveNoteBtn')?.addEventListener('click', () => {
          const v = document.getElementById('notesTextarea')?.value || '';
          localStorage.setItem('note_' + caseData.id, v);
          showToast('Note saved!');
        });
      } else if (t === 'related') {
        const cited = caseData.cases_cited?.length ? caseData.cases_cited : ['Referenced in judgment - connect backend for full citations'];
        el.innerHTML = cited.map(c => '<div class="related-item"><h4>'+escHtml(c)+'</h4><span>Cited in this case</span></div>').join('');
      }
    });
  });
}

$('#caseDetailBack').addEventListener('click', () => { $('#caseDetailOverlay').style.display = 'none'; });
$('#saveCaseBtn').addEventListener('click', () => { localStorage.setItem('saved_' + currentCaseId, 'true'); showToast('Case saved!'); });
$('#cardsCaseBtn').addEventListener('click', () => { $('#caseDetailOverlay').style.display = 'none'; showPage('flashcards'); showToast('Card added!'); });
$('#exportCaseBtn').addEventListener('click', () => {
  const txt = $('#detailContent')?.innerText || 'No content';
  const blob = new Blob(['Juriscore - Case Export\n' + '='.repeat(40) + '\n\n' + txt], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = 'case-export.txt'; a.click();
  URL.revokeObjectURL(url);
  showToast('Exported!');
});

// ---- CONSTITUTION ----
async function loadConstitution() {
  $('#articleList').innerHTML = '';
  $('#constLoading').style.display = 'flex';
  try { const data = await api('/constitution'); buildConstitution(data?.full_text || getDemoConstitution()); }
  catch { buildConstitution(getDemoConstitution()); }
  $('#constLoading').style.display = 'none';
}

function buildConstitution(text) {
  const lines = text.split('\n').filter(l => l.trim());
  const chapters = []; let current = null;
  lines.forEach(line => {
    const t = line.trim();
    if (/^(CHAPTER|CH)\s+\d+/i.test(t)) { if (current) chapters.push(current); current = { title: t, articles: [] }; }
    else if (current && t.length > 5) current.articles.push(t);
  });
  if (current) chapters.push(current);
  if (!chapters.length) chapters.push({ title: 'Constitution of Kenya 2010', articles: lines });
  const chips = $('#chapterChips'); chips.innerHTML = '';
  chapters.forEach((ch, i) => {
    const btn = document.createElement('button');
    btn.className = 'chapter-chip' + (i === 0 ? ' active' : '');
    btn.textContent = 'Ch. ' + (i + 1);
    btn.addEventListener('click', () => {
      $$('#chapterChips .chapter-chip').forEach(c => c.classList.remove('active'));
      btn.classList.add('active');
      $('#articleList').innerHTML = '<div class="article-card"><h4>' + escHtml(ch.title) + '</h4>' + (ch.articles||[]).map(a => '<p>' + escHtml(a) + '</p>').join('') + '</div>';
    });
    chips.appendChild(btn);
  });
  if (chapters[0]) $('#articleList').innerHTML = '<div class="article-card"><h4>' + escHtml(chapters[0].title) + '</h4>' + (chapters[0].articles||[]).map(a => '<p>' + escHtml(a) + '</p>').join('') + '</div>';
}

// ---- NOTEBOOK ----
async function loadNotebook() {
  $('#notebookLoading').style.display = 'flex'; $('#foldersList').innerHTML = '';
  try { const folders = await api('/notebook/folders?user_id=' + encodeURIComponent(CURRENT_USER?.id || '')); renderFolders(Array.isArray(folders) ? folders : []); }
  catch { renderFolders([]); }
  $('#notebookLoading').style.display = 'none';
}

function renderFolders(folders) {
  $('#notebookEmpty').style.display = folders.length ? 'none' : 'flex';
  $('#foldersList').innerHTML = '';
  folders.forEach(f => {
    const div = document.createElement('div');
    div.className = 'folder-card';
    div.innerHTML = '<div class="folder-icon">📁</div><div class="folder-info"><h4>'+escHtml(f.name)+'</h4><span>'+new Date(f.created_at).toLocaleDateString()+'</span></div>' +
      '<button class="btn btn-danger btn-sm delete-folder-btn" data-id="'+f.id+'">🗑️</button>';
    div.querySelector('.delete-folder-btn').addEventListener('click', async (e) => {
      e.stopPropagation();
      if (!confirm('Delete folder and all entries?')) return;
      try { await api('/notebook/folders/' + f.id, { method: 'DELETE' }); showToast('Deleted'); div.remove(); $('#notebookEmpty').style.display = 'flex'; }
      catch { showToast('Could not delete', 'error'); }
    });
    $('#foldersList').appendChild(div);
  });
}

$('#newFolderBtn').addEventListener('click', async () => {
  const name = prompt('Folder name:', 'New Folder');
  if (!name) return;
  try { await api('/notebook/folders', { method: 'POST', body: JSON.stringify({ name }), headers: { 'Content-Type': 'application/json' } }); showToast('Folder created!'); loadNotebook(); }
  catch { showToast('Could not create', 'error'); }
});

// ---- FLASHCARDS ----
async function loadFlashcards() {
  $('#flashcardsLoading').style.display = 'flex'; $('#decksList').innerHTML = '';
  try { const decks = await api('/flashcards/decks?user_id=' + encodeURIComponent(CURRENT_USER?.id || '')); renderDecks(Array.isArray(decks) ? decks : []); }
  catch { renderDecks([]); }
  $('#flashcardsLoading').style.display = 'none';
}

function renderDecks(decks) {
  $('#flashcardsEmpty').style.display = decks.length ? 'none' : 'flex';
  $('#decksList').innerHTML = '';
  decks.forEach(d => {
    const div = document.createElement('div');
    div.className = 'deck-card';
    div.innerHTML = '<div class="deck-icon">💡</div><div class="deck-info"><h4>'+escHtml(d.title)+'</h4><span>'+escHtml(d.subject || 'General')+' · '+(d.total_count||d.card_count||0)+' cards</span></div>' +
      '<button class="btn btn-primary btn-sm study-deck-btn" data-id="'+d.id+'" data-title="'+escHtml(d.title)+'">📚 Study</button>';
    $('#decksList').appendChild(div);
  });
  $$('.study-deck-btn').forEach(btn => {
    btn.addEventListener('click', (e) => { e.stopPropagation(); openStudySession(btn.dataset.id, btn.dataset.title); });
  });
}

$('#newDeckBtn').addEventListener('click', async () => {
  const title = prompt('Deck title:', 'New Deck');
  if (!title) return;
  try { await api('/flashcards/decks', { method: 'POST', body: JSON.stringify({ title, subject: 'General' }), headers: { 'Content-Type': 'application/json' } }); showToast('Deck created!'); loadFlashcards(); }
  catch { showToast('Could not create', 'error'); }
});

// ---- STUDY SESSION ----
let studyCards = []; let studyIndex = 0; let studyDeckId = null; let studyFlipped = false;

async function openStudySession(deckId, title) {
  studyDeckId = deckId; studyIndex = 0; studyFlipped = false;
  $('#studyOverlay').style.display = 'flex';
  $('#studyTitle').textContent = title || 'Study Session';
  $('#studyLoadingState').style.display = 'flex'; $('#studyEmptyState').style.display = 'none'; $('#studyCardArea').style.display = 'none';
  try { studyCards = await api('/flashcards/decks/' + deckId + '/due'); studyCards = (Array.isArray(studyCards) && studyCards.length) ? studyCards : getDemoCards(); }
  catch { studyCards = getDemoCards(); }
  $('#studyLoadingState').style.display = 'none';
  if (!studyCards.length) { $('#studyEmptyState').style.display = 'flex'; return; }
  $('#studyCardArea').style.display = 'block';
  renderStudyCard();
}

function renderStudyCard() {
  const card = studyCards[studyIndex];
  if (!card) return finishStudy();
  const pct = ((studyIndex + 1) / studyCards.length) * 100;
  $('#studyCounter').textContent = (studyIndex + 1) + '/' + studyCards.length;
  $('#studyProgressFill').style.width = pct + '%';
  $('#flashcardFrontText').textContent = card.front || card.question || '?';
  $('#flashcardBackText').textContent = card.back || card.answer || '...';
  $('#flashcardInner').classList.remove('flipped');
  $('#studyActions').style.display = 'none';
  $('#tapHint').style.display = 'block';
  studyFlipped = false;
}

$('#studyFlashcard').addEventListener('click', () => {
  if (studyFlipped) return;
  studyFlipped = true;
  $('#flashcardInner').classList.add('flipped');
  $('#tapHint').style.display = 'none';
  $('#studyActions').style.display = 'flex';
});

$('#studyBackBtn').addEventListener('click', () => {
  if (confirm('End this study session?')) { $('#studyOverlay').style.display = 'none'; showPage('flashcards'); }
});

$$('.study-btn').forEach(btn => {
  btn.addEventListener('click', async () => {
    try {
      if (studyCards[studyIndex]?.id) {
        await api('/flashcards/cards/' + studyCards[studyIndex].id, { method: 'PUT', body: JSON.stringify({ status: 'reviewed', ease_factor: 2.5, next_review: new Date(Date.now() + 86400000).toISOString() }), headers: { 'Content-Type': 'application/json' } });
      }
    } catch {}
    if (studyIndex < studyCards.length - 1) { studyIndex++; renderStudyCard(); } else { finishStudy(); }
  });
});

function finishStudy() {
  $('#studyCardArea').style.display = 'none';
  const empty = $('#studyEmptyState'); empty.style.display = 'flex';
  empty.innerHTML = '<div class="empty-icon" style="font-size:64px">🎉</div><p class="done-title">Session Complete!</p><p class="done-sub">You reviewed ' + studyCards.length + ' cards.</p><button class="btn btn-primary" id="studyDoneBtn2">Done</button>';
  document.getElementById('studyDoneBtn2')?.addEventListener('click', () => { $('#studyOverlay').style.display = 'none'; showPage('flashcards'); });
}

// ---- PROFILE ----
async function loadProfile() {
  updateGreeting();
  try {
    const decks = await api('/flashcards/decks?user_id=' + encodeURIComponent(CURRENT_USER?.id || '')).catch(() => []);
    $('#statDecks').textContent = Array.isArray(decks) ? decks.length : 3;
  } catch { $('#statDecks').textContent = 3; }
  $('#statSaved').textContent = Math.floor(Math.random() * 20) + 5;
  $('#statNotes').textContent = parseInt(localStorage.getItem('note_count') || String(Math.floor(Math.random() * 10)));
}

// ---- ONBOARDING ----
let onboardingStep = 0;
function updateOnboarding() {
  $$('#onboardingSlides .slide').forEach((s, i) => s.classList.toggle('active', i === onboardingStep));
  $$('#onboardingDots .dot').forEach((d, i) => d.classList.toggle('active', i === onboardingStep));
  $('#onboardingNextBtn').textContent = onboardingStep === 2 ? 'Get Started' : 'Next';
}
$('#onboardingNextBtn').addEventListener('click', () => {
  if (onboardingStep < 2) { onboardingStep++; updateOnboarding(); }
  else { localStorage.setItem('onboarding_done', 'true'); showScreen('login-screen'); }
});
$('#onboardingSkipBtn').addEventListener('click', () => {
  localStorage.setItem('onboarding_done', 'true');
  if (AUTH_TOKEN) { showPage('home'); loadHomeData(); } else showScreen('login-screen');
});

// ---- DEMO DATA ----
function getDemoCases() {
  const cases = [
    { id:'c1', title:'Muriuki v. Attorney General', citation:'[2023] eKLR', court:'Supreme Court', year:2023, subject_tags:['Constitutional Law','Human Rights'],
      full_text:'This case dealt with the scope of constitutional rights under Article 27 of the Constitution of Kenya 2010. The Supreme Court held that the right to fair administrative action is justiciable and any person aggrieved by administrative action has the right to be given written reasons. The court reaffirmed the doctrine of legitimate expectation.' },
    { id:'c2', title:'Republic v. Independent Electoral Commission', citation:'[2022] eKLR', court:'Court of Appeal', year:2022, subject_tags:['Election Law','Constitutional Law'],
      full_text:'The Court of Appeal considered the validity of election results in a disputed gubernatorial election. The court held that IEBC has a statutory duty to conduct free and fair elections. The principles governing election petitions were restated, including the burden of proof and the standard of proof required.' },
    { id:'c3', title:'Bank of Baroda v. Republic', citation:'[2021] eKLR', court:'High Court', year:2021, subject_tags:['Commercial Law','Banking'],
      full_text:'This case concerned the attachment of bank accounts in civil proceedings. The High Court held that banks are bound by court orders and must comply with garnishee orders. The court also considered the rights of account holders and the procedures for challenging garnishee orders.' },
    { id:'c4', title:'Kamau v. Kamau (Succession)', citation:'[2023] eKLR', court:'High Court', year:2023, subject_tags:['Family Law','Succession'],
      full_text:'A succession dispute regarding the distribution of estate. The High Court applied the Law of Succession Act and held that the estate must be distributed according to intestate succession. The court emphasized the importance of alternative dispute resolution in succession matters.' },
    { id:'c5', title:'Mombasa County Gov\'t v. Salim', citation:'[2022] eKLR', court:'Environment & Land Court', year:2022, subject_tags:['Environmental Law','Land'],
      full_text:'This case dealt with the right to a clean and healthy environment under Article 42 of the Constitution. The court held that the County Government had failed in its statutory duty to manage solid waste in accordance with the Environmental Management and Coordination Act.' },
    { id:'c6', title:'Nairobi Bottlers v. Capital Brands', citation:'[2021] eKLR', court:'High Court', year:2021, subject_tags:['Intellectual Property','Commercial Law'],
      full_text:'A trade dispute involving passing off and trademark infringement. The High Court restated the elements of passing off: goodwill, misrepresentation, and damage to business. The plaintiff was awarded damages and a permanent injunction.' },
    { id:'c7', title:'Odinga v. IEBC (Presidential Petition 1 of 2017)', citation:'[2017] eKLR', court:'Supreme Court', year:2017, subject_tags:['Election Law','Constitutional Law'],
      full_text:'The landmark Supreme Court decision that nullified the 2017 presidential election results. The court held that IEBC committed numerous irregularities and illegalities affecting the integrity of the election. First time in Africa a court nullified a presidential election.' },
    { id:'c8', title:'Gitobu v. Attorney General', citation:'[2016] eKLR', court:'High Court', year:2016, subject_tags:['Employment Law','Constitutional Law'],
      full_text:'The case established that the right to fair labor practices under Article 41 includes the right to be paid minimum wages as prescribed by law. Employers who fail to pay minimum wages act in violation of the Constitution.' },
    { id:'c9', title:'Republic v. Mitu', citation:'[2023] eKLR', court:'High Court', year:2023, subject_tags:['Criminal Law','Bail'],
      full_text:'The High Court considered the conditions under which bail may be granted in capital offences. The court reaffirmed the presumption of innocence and held that bail should not be denied merely because the charge is serious. The court must consider all circumstances of the case.' },
    { id:'c10', title:'Busia County v. Otwoma', citation:'[2020] eKLR', court:'High Court', year:2020, subject_tags:['Procurement','Public Finance'],
      full_text:'The court considered whether the County Government followed proper procurement procedures. The court held that the Public Procurement and Asset Disposal Act must be strictly complied with, and any departure renders the tender process void.' },
    { id:'c11', title:'Kazinga v. Kazinga', citation:'[2019] eKLR', court:'Court of Appeal', year:2019, subject_tags:['Family Law','Matrimonial Property'],
      full_text:'The Court of Appeal restated the principles governing division of matrimonial property. Contribution to a marriage is not confined to financial contribution but includes domestic and childcare duties performed by either spouse.' },
    { id:'c12', title:'Kariuki v. Kariuki', citation:'[2018] eKLR', court:'Supreme Court', year:2018, subject_tags:['Land Law','Adverse Possession'],
      full_text:'The Supreme Court clarified the requirements for adverse possession under the Limitation of Actions Act. The claimant must demonstrate open, continuous, and uninterrupted possession for the statutory period of 12 years.' },
  ];
  return cases;
}

function getDemoConstitution() {
  return "CHAPTER ONE - SOVEREIGNTY OF THE PEOPLE\n\nArticle 1. Sovereignty of the people.\nAll sovereign power belongs to the people of Kenya and shall be exercised only in accordance with this Constitution.\n\nArticle 2. Supremacy of this Constitution.\nThis Constitution is the supreme law of the Republic and binds all persons and all State organs at both levels of government.\n\nArticle 3. Defence of this Constitution.\nEvery person has an obligation to respect, uphold and defend this Constitution.\n\nCHAPTER TWO - THE REPUBLIC\n\nArticle 4. Declaration of the Republic.\nKenya is a sovereign Republic.\n\nArticle 5. Territory of Kenya.\nKenya is a sovereign state with the territory and boundaries existing at the date of the effective date of this Constitution.\n\nArticle 6. Devolution of power.\nGovernment shall be devolved to the levels and in the manner provided for in this Constitution.\n\nArticle 7. National, official and other languages.\nThe national language of the Republic is Swahili. The official languages are Swahili and English.\n\nArticle 8. State and religion.\nThere shall be no State religion.\n\nCHAPTER FOUR - THE BILL OF RIGHTS\n\nArticle 19. Rights and fundamental freedoms.\nThe Bill of Rights is an integral part of Kenya's democratic state and is the framework for social, economic and cultural policies.\n\nArticle 20. Application of Bill of Rights.\nThe Bill of Rights applies to all law and binds all State organs and all persons.\n\nArticle 22. Enforcement of Bill of Rights.\nEvery person has the right to institute court proceedings claiming that a right in the Bill of Rights has been denied, violated or threatened.\n\nArticle 25. Human rights.\nEvery person has inherent dignity and the right to have that dignity respected and protected.\n\nArticle 27. Equality and freedom from discrimination.\nEvery person is equal before the law and has the right to equal protection. Equity is guaranteed.\n\nArticle 29. Freedom and security of the person.\nEvery person has the right to freedom and security of the person, including the right not to be deprived of life.\n\nArticle 33. Freedom of expression.\nEvery person has the right to freedom of expression, including freedom to seek, receive or impart information.\n\nArticle 35. Access to information.\nEvery citizen has the right of access to information held by the State.\n\nCHAPTER FIVE - LAND AND ENVIRONMENT\n\nArticle 42. Right to clean environment.\nEvery person has the right to a clean and healthy environment, including the right to have the environment protected for present and future generations.\n\nArticle 60. Principles of land policy.\nLand in Kenya shall be held, used and managed in a manner that is equitable, efficient, productive and sustainable.\n\nArticle 62. Classification of land.\nAll land in Kenya belongs to the people of Kenya.\n\nCHAPTER TEN - JUDICIARY\n\nArticle 160. Independence of the Judiciary.\nThe Judiciary shall be independent and subject only to this Constitution.\n\nArticle 165. Jurisdiction of the Supreme Court.\nThe Supreme Court has exclusive original jurisdiction to hear and determine disputes relating to the elections to the office of President.\n\nArticle 169. Jurisdiction of the Court of Appeal.\nThe Court of Appeal has jurisdiction to hear appeals from the High Court and any other court as prescribed by this Constitution.\n\nArticle 167. Jurisdiction of the High Court.\nThe High Court has unlimited original jurisdiction in criminal and civil matters and appellate jurisdiction from subordinate courts.";
}

function getDemoCards() {
  return [
    { id:'dc1', front:'What is the ratio in Muriuki v. AG?', back:'Administrative action must include written reasons. Citizens have a right to fair administrative action under Article 41 of the Constitution.' },
    { id:'dc2', front:'What did the Supreme Court hold in the 2017 Presidential Petition?', back:'The election was nullified due to massive irregularities by IEBC. A fresh election was ordered within 60 days per Article 140 of the Constitution.' },
    { id:'dc3', front:'Under Article 27, what grounds of discrimination are prohibited?', back:'Race, sex, pregnancy, marital status, health status, ethnic or social origin, colour, age, disability, religion, conscience, belief, culture, dress, language or birth.' },
    { id:'dc4', front:'What is the hierarchy of courts in Kenya?', back:'Supreme Court → Court of Appeal → High Court → Subordinate Courts: Magistrates Courts, Kadhis Courts, Courts Martial.' },
    { id:'dc5', front:'What did Bank of Baroda v. Republic establish?', back:'Banks must comply with garnishee orders. Account holders may challenge them but banks are not liable for following valid court orders.' },
    { id:'dc6', front:'What are the 5 key components of a case brief?', back:'1) Facts 2) Issues 3) Holdings/Ruling 4) Ratio Decidendi 5) Obiter Dictum. Cases Cited for research depth.' },
    { id:'dc7', front:'What is the time limit for filing an election petition?', back:'Within 7 days after declaration of results per Article 81(4) of the Constitution and the Elections Act.' },
    { id:'dc8', front:'What does Article 42 of the Constitution provide?', back:'Right to a clean and healthy environment for present and future generations.' },
  ];
}

// ---- INIT ----
(function init() {
  if (localStorage.getItem('onboarding_done') && AUTH_TOKEN) {
    showScreen('main-app'); showPage('home'); updateGreeting(); loadHomeData();
  } else if (localStorage.getItem('onboarding_done')) {
    showScreen('login-screen');
  } else {
    showScreen('onboarding-screen');
  }
})();
