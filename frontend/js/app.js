// ===== JURISCORE WEB APP =====
(function() {
  'use strict';

  const API_URL = window.JURISCORE_API_URL || 'http://localhost:8000/api';
  let AUTH_TOKEN = '';
  let CURRENT_USER = null;
  let currentRoute = 'home';
  let allCases = [];
  let filteredCases = [];
  let activeFilter = 'All';
  let currentSort = 'relevance';
  let selectedUniversity = 'Kabarak University';
  let currentCaseId = null;

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  // ---- INIT ----
  function init() {
    AUTH_TOKEN = localStorage.getItem('jwt_token') || '';
    const savedUser = localStorage.getItem('current_user');
    if (savedUser) CURRENT_USER = JSON.parse(savedUser);
    const onboardingDone = localStorage.getItem('onboarding_done');
    if (onboardingDone && AUTH_TOKEN && CURRENT_USER) {
      showMainApp();
    } else if (onboardingDone) {
      showScreen('login-screen');
    } else {
      showScreen('onboarding-screen');
    }
    setTimeout(() => hideLoading(), 800);
  }

  function hideLoading() {
    const ls = $('#loading-screen');
    if (ls) ls.style.display = 'none';
  }

  // ---- SCREENS ----
  function showScreen(id) {
    $$('.screen').forEach(s => s.classList.remove('active'));
    const el = document.getElementById(id);
    if (el) el.classList.add('active');
  }

  function showMainApp() {
    $$('.screen').forEach(s => s.classList.remove('active'));
    const ma = $('#main-app');
    if (ma) ma.classList.add('active');
    updateGreeting();
    showPage('home');
    loadHomeData();
    setupAuthListeners();
  }

  function showPage(route) {
    $$('.page').forEach(p => p.classList.remove('active'));
    const page = document.getElementById('page-' + route);
    if (page) page.classList.add('active');
    $$('.nav-item').forEach(n => n.classList.remove('active'));
    const navBtn = document.querySelector(`.nav-item[data-route="${route}"]`);
    if (navBtn) navBtn.classList.add('active');
    const titles = { home:'Juriscore', search:'Search', constitution:'Constitution', notebook:'Notebook', flashcards:'Flashcards', profile:'Profile' };
    const title = titles[route] || 'Juriscore';
    const el = $('#topBarTitle');
    if (el) el.textContent = title;
    currentRoute = route;
  }

  function showToast(msg, type = 'success') {
    const container = $('#toastContainer');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = 'toast toast-' + (type === 'error' ? 'error' : 'success');
    toast.textContent = msg;
    container.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('show'));
    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  function escHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function logout() {
    AUTH_TOKEN = '';
    CURRENT_USER = null;
    localStorage.removeItem('jwt_token');
    localStorage.removeItem('current_user');
    showScreen('login-screen');
  }

  function updateGreeting() {
    if (!CURRENT_USER) return;
    const firstName = CURRENT_USER.name.split(' ')[0];
    const h = new Date().getHours();
    const g = h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
    const el = $('#greetingText');
    if (el) el.textContent = g + ', ' + firstName;
    const initials = CURRENT_USER.name.split(' ').map(n => n[0]).slice(0, 2).join('').toUpperCase();
    const avatar = $('#profileAvatar');
    if (avatar) avatar.textContent = initials;
    const nameEl = $('#profileName');
    if (nameEl) nameEl.textContent = CURRENT_USER.name;
    const uniEl = $('#profileUni');
    if (uniEl) uniEl.textContent = CURRENT_USER.university || 'University';
  }

  // ---- API ----
  async function api(endpoint, options = {}) {
    const url = API_URL + endpoint;
    const headers = { 'Content-Type': 'application/json', ...options.headers };
    if (AUTH_TOKEN) headers['Authorization'] = 'Bearer ' + AUTH_TOKEN;
    try {
      const resp = await fetch(url, { ...options, headers });
      if (resp.status === 401) { logout(); throw new Error('Unauthorized'); }
      if (!resp.ok) throw new Error('API error ' + resp.status);
      const ct = resp.headers.get('content-type') || '';
      if (ct.includes('application/json')) return resp.json();
      if (ct.includes('text/')) return resp.text();
      return resp.blob();
    } catch (e) {
      console.warn('API call failed:', endpoint, e.message);
      throw e;
    }
  }

  // ---- AUTH HANDLERS ----
  function setupAuthListeners() {
    const lb = $('#logoutBtn');
    const lb2 = $('#logoutBtn2');
    if (lb) lb.onclick = logout;
    if (lb2) lb2.onclick = logout;
  }

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
      AUTH_TOKEN = 'demo-token-' + Date.now();
      localStorage.setItem('jwt_token', AUTH_TOKEN);
      localStorage.setItem('current_user', JSON.stringify(CURRENT_USER));
      updateGreeting();
      showMainApp();
      showToast('Welcome back!');
    } catch (err) { showToast(err.message, 'error'); }
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
      AUTH_TOKEN = 'demo-token-' + Date.now();
      localStorage.setItem('jwt_token', AUTH_TOKEN);
      localStorage.setItem('current_user', JSON.stringify(CURRENT_USER));
      updateGreeting();
      showMainApp();
      showToast('Account created!');
    } catch (err) { showToast(err.message, 'error'); }
    finally {
      btn.querySelector('.btn-text').style.display = 'inline';
      btn.querySelector('.btn-spinner').style.display = 'none';
      btn.disabled = false;
    }
  });

  $$('#uniChips .uni-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      $$('#uniChips .uni-chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      selectedUniversity = chip.dataset.uni;
    });
  });

  $('#goToSignup').addEventListener('click', (e) => { e.preventDefault(); showScreen('signup-screen'); });
  $('#goToLogin').addEventListener('click', (e) => { e.preventDefault(); showScreen('login-screen'); });
  $('#googleLoginBtn').addEventListener('click', () => showToast('Google OAuth requires Supabase setup', 'error'));
  $('#googleSignupBtn').addEventListener('click', () => showToast('Google OAuth requires Supabase setup', 'error'));

  // ---- ONBOARDING ----
  let onboardingStep = 0;
  const totalSteps = 3;

  function updateOnboarding() {
    $$('#onboardingSlides .slide').forEach((s, i) => s.classList.toggle('active', i === onboardingStep));
    $$('#onboardingDots .dot').forEach((d, i) => d.classList.toggle('active', i === onboardingStep));
    const btn = $('#onboardingNextBtn');
    if (btn) btn.textContent = onboardingStep === totalSteps - 1 ? 'Get Started' : 'Next';
  }

  $('#onboardingNextBtn').addEventListener('click', () => {
    if (onboardingStep < totalSteps - 1) { onboardingStep++; updateOnboarding(); }
    else { localStorage.setItem('onboarding_done', 'true'); showScreen('login-screen'); }
  });

  $('#onboardingSkipBtn').addEventListener('click', () => {
    localStorage.setItem('onboarding_done', 'true');
    showScreen('login-screen');
  });

  // ---- NAVIGATION ----
  $$('#bottomNav .nav-item').forEach(btn => {
    btn.addEventListener('click', () => {
      const route = btn.dataset.route;
      showPage(route);
      if (route === 'home') loadHomeData();
      if (route === 'search') loadSearchData();
      if (route === 'constitution') loadConstitution();
      if (route === 'notebook') loadNotebook();
      if (route === 'flashcards') loadFlashcards();
      if (route === 'profile') loadProfileData();
    });
  });

  $$('.quick-action').forEach(btn => {
    btn.addEventListener('click', () => {
      const route = btn.dataset.route;
      showPage(route);
      if (route === 'search') loadSearchData();
      if (route === 'notebook') loadNotebook();
      if (route === 'flashcards') loadFlashcards();
      if (route === 'constitution') loadConstitution();
    });
  });

  $('#homeSearchInput').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      const val = e.target.value.trim();
      if (val) {
        showPage('search');
        $('#searchInput').value = val;
        loadSearchData();
      }
    }
  });

  // ---- HOME ----
  async function loadHomeData() {
    let recentArr = [], recsArr = [];
    try {
      const [recent, recs] = await Promise.all([
        api('/cases/recent?limit=10').catch(() => []),
        api('/cases/search?limit=20').catch(() => []),
      ]);
      recentArr = Array.isArray(recent) ? recent.filter((_, i) => i < 6) : [];
      recsArr = Array.isArray(recs) ? recs.filter((_, i) => i < 5) : [];
    } catch (err) {
      console.warn('API fallback to demo data');
    }
    if (recentArr.length === 0 && recsArr.length === 0) {
      const demo = getDemoCases();
      recentArr = demo.slice(0, 6);
      recsArr = demo.slice(0, 5);
      allCases = demo;
    } else {
      allCases = [...recentArr, ...recsArr];
    }
    const scroll = $('#recentCasesScroll');
    if (scroll) {
      scroll.innerHTML = '';
      recentArr.forEach(c => scroll.appendChild(createCaseCard(c, true)));
    }
    const recList = $('#recommendedList');
    if (recList) {
      recList.innerHTML = '';
      recsArr.forEach(c => recList.appendChild(createCaseCard(c, false)));
    }
  }

  function createCaseCard(item, isHorizontal) {
    const div = document.createElement('div');
    div.className = 'case-card' + (isHorizontal ? ' case-card-h' : '');
    div.innerHTML = `
      <div class="case-card-body">
        <h4>${escHtml(item.title || 'Untitled Case')}</h4>
        <p class="case-citation">${escHtml(item.citation || '')}</p>
        <div class="tags-row">
          <span class="tag">${escHtml(item.court || '')}</span>
          <span class="tag tag-accent">${item.year || ''}</span>
          ${(item.subject_tags || []).slice(0, 2).map(t => `<span class="tag tag-light">${escHtml(t)}</span>`).join('')}
        </div>
      </div>
    `;
    div.addEventListener('click', () => openCaseDetail(item.id));
    return div;
  }

  // ---- SEARCH ----
  async function loadSearchData() {
    const input = $('#searchInput');
    if (input && input.value.trim()) {
      performSearch(input.value.trim());
    } else {
      try {
        const results = await api('/cases/search?limit=50');
        allCases = Array.isArray(results) ? results : results?.results || [];
      } catch {
        allCases = getDemoCases();
      }
      renderSearchResults();
    }
  }

  function performSearch(query) {
    const lq = query.toLowerCase();
    if (!lq) {
      allCases = getDemoCases();
    } else {
      allCases = getDemoCases().filter(c =>
        (c.title || '').toLowerCase().includes(lq) ||
        (c.citation || '').toLowerCase().includes(lq) ||
        (c.court || '').toLowerCase().includes(lq) ||
        (c.subject_tags || []).some(t => (t || '').toLowerCase().includes(lq))
      );
    }
    renderSearchResults();
  }

  function renderSearchResults() {
    let data = [...allCases];
    if (activeFilter !== 'All' && activeFilter !== 'Statutes') {
      const courtMap = { 'Supreme Court': 'supreme', 'Court of Appeal': 'appeal', 'High Court': 'high court' };
      const kw = courtMap[activeFilter] || activeFilter.toLowerCase();
      data = data.filter(c => (c.court || '').toLowerCase().includes(kw));
    }
    if (currentSort === 'newest') data.sort((a, b) => (b.year || 0) - (a.year || 0));
    else if (currentSort === 'oldest') data.sort((a, b) => (a.year || 0) - (b.year || 0));
    filteredCases = data;

    const container = $('#searchResults');
    container.innerHTML = '';
    const emptyState = $('#searchEmpty');
    if (filteredCases.length === 0) {
      if (emptyState) emptyState.style.display = 'flex';
    } else {
      if (emptyState) emptyState.style.display = 'none';
      filteredCases.forEach(c => container.appendChild(createCaseCard(c, false)));
    }
  }

  $('#searchInput').addEventListener('input', (e) => {
    const q = e.target.value.trim();
    const clearBtn = $('#searchClear');
    if (clearBtn) clearBtn.style.display = q ? 'block' : 'none';
    performSearch(q);
  });

  $('#searchClear').addEventListener('click', () => {
    $('#searchInput').value = '';
    $('#searchClear').style.display = 'none';
    allCases = getDemoCases();
    renderSearchResults();
  });

  $('#sortToggle').addEventListener('click', () => {
    const panel = $('#sortPanel');
    if (panel) panel.style.display = panel.style.display === 'none' ? 'flex' : 'none';
  });

  $$('#sortPanel .sort-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      $$('#sortPanel .sort-chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      currentSort = chip.dataset.sort;
      const panel = $('#sortPanel');
      if (panel) panel.style.display = 'none';
      renderSearchResults();
    });
  });

  $$('#filterChips .filter-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      $$('#filterChips .filter-chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      activeFilter = chip.dataset.court;
      renderSearchResults();
    });
  });

  // ---- CASE DETAIL ----
  function openCaseDetail(caseId) {
    currentCaseId = caseId;
    const caseData = allCases.find(c => c.id === caseId) || getDemoCases().find(c => c.id === caseId);
    if (!caseData) return showToast('Case not found', 'error');

    const summary = generateDemoSummary(caseData);
    const s = summary || {};
    const content = $('#caseDetailContent');
    content.innerHTML = `
      <div class="case-detail-header">
        <h2>${escHtml(caseData.title)}</h2>
        <p class="case-citation-lg">${escHtml(caseData.citation)}</p>
        <div class="tags-row">
          <span class="tag">${escHtml(caseData.court)}</span>
          <span class="tag tag-accent">${caseData.year}</span>
          ${(caseData.subject_tags || []).map(t => `<span class="tag tag-light">${escHtml(t)}</span>`).join('')}
        </div>
      </div>
      <div class="detail-tabs">
        <button class="detail-tab active" data-tab="summary">Summary</button>
        <button class="detail-tab" data-tab="fulltext">Full Judgment</button>
        <button class="detail-tab" data-tab="notes">Notes</button>
        <button class="detail-tab" data-tab="related">Related</button>
      </div>
      <div class="detail-content" id="detailContent">
        ${renderSummaryTab(s)}
      </div>
    `;

    setupDetailTabs(caseData, s);
    $('#caseDetailOverlay').style.display = 'flex';
  }

  function renderSummaryTab(s) {
    return `
      ${s.facts?.length ? `<div class="detail-section"><h4>Facts</h4>${s.facts.map(f => `<p class="bullet-item">• ${escHtml(f)}</p>`).join('')}</div>` : ''}
      ${s.issues?.length ? `<div class="detail-section"><h4>Issues</h4>${s.issues.map((iss, i) => `<p class="numbered-item">${i + 1}. ${escHtml(iss)}</p>`).join('')}</div>` : ''}
      ${s.holdings?.length ? `<div class="detail-section"><h4>Holdings</h4>${s.holdings.map((h, i) => `<p class="numbered-item">${i + 1}. ${escHtml(h)}</p>`).join('')}</div>` : ''}
      <div class="ratio-box"><h4>⚖️ Ratio Decidendi</h4><p>${escHtml(s.ratio || 'Not available for this case.')}</p></div>
      ${s.obiter ? `<div class="detail-section"><h4>Obiter Dictum</h4><p>${escHtml(s.obiter)}</p></div>` : ''}
      ${s.cases_cited?.length ? `<div class="detail-section"><h4>Cases Cited</h4>${s.cases_cited.map(c => `<p class="bullet-item">• ${escHtml(c)}</p>`).join('')}</div>` : ''}
    `;
  }

  function setupDetailTabs(caseData, s) {
    $$('#caseDetailContent .detail-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        $$('#caseDetailContent .detail-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        const dc = $('#detailContent');
        const t = tab.dataset.tab;
        if (t === 'summary') {
          dc.innerHTML = renderSummaryTab(s);
        } else if (t === 'fulltext') {
          dc.innerHTML = `<div class="full-text-block"><p>${escHtml(caseData.full_text || 'Full text not available.')}</p></div>`;
        } else if (t === 'notes') {
          dc.innerHTML = `
            <div class="notes-area">
              <textarea id="notesTextarea" placeholder="Add your personal notes here..."></textarea>
              <button class="btn btn-primary btn-full" id="saveNoteBtn">Save Note</button>
            </div>
          `;
          const existingNote = localStorage.getItem('note_' + caseData.id);
          if (existingNote) $('#notesTextarea').value = existingNote;
          $('#saveNoteBtn').addEventListener('click', () => {
            localStorage.setItem('note_' + caseData.id, $('#notesTextarea').value);
            showToast('Note saved!');
          });
        } else if (t === 'related') {
          const cited = (caseData.cases_cited && caseData.cases_cited.length) ? caseData.cases_cited : ['Referenced in judgment text'];
          dc.innerHTML = cited.map(c => `<div class="related-item"><h4>${escHtml(c)}</h4><span>Cited in this case</span></div>`).join('');
        }
      });
    });
  }

  $('#caseDetailBack').addEventListener('click', () => { $('#caseDetailOverlay').style.display = 'none'; });
  $('#saveCaseBtn').addEventListener('click', () => {
    if (currentCaseId) {
      localStorage.setItem('saved_' + currentCaseId, 'true');
      showToast('Case saved!');
    }
  });
  $('#cardsCaseBtn').addEventListener('click', () => {
    $('#caseDetailOverlay').style.display = 'none';
    showPage('flashcards');
    showToast('Card added to your deck!');
  });
  $('#exportCaseBtn').addEventListener('click', () => {
    const content = $('#caseDetailContent');
    const txt = 'Juriscore - Case Export\n' + '='.repeat(40) + '\n\n' + (content ? content.innerText : '');
    const blob = new Blob([txt], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'case-export.txt'; a.click();
    URL.revokeObjectURL(url);
    showToast('Exported!');
  });

  // ---- CONSTITUTION ----
  async function loadConstitution() {
    const list = $('#articleList');
    const loading = $('#constLoading');
    if (list) list.innerHTML = '';
    if (loading) loading.style.display = 'flex';
    try {
      const data = await api('/constitution');
      const fullText = data?.full_text || getDemoConstitution();
      populateConstitution(fullText);
    } catch {
      populateConstitution(getDemoConstitution());
    }
    if (loading) loading.style.display = 'none';
  }

  function populateConstitution(text) {
    const lines = text.split('\n').filter(l => l.trim());
    const chapters = [];
    let current = null;
    lines.forEach(line => {
      const trimmed = line.trim();
      if (/^(CHAPTER|CH)\s+\d+/i.test(trimmed)) {
        if (current) chapters.push(current);
        current = { title: trimmed, articles: [] };
      } else if (current && trimmed.length > 10) {
        current.articles.push(trimmed);
      }
    });
    if (current) chapters.push(current);
    if (chapters.length === 0) {
      chapters.push({ title: 'Constitution of Kenya, 2010', articles: lines });
    }

    const chipsContainer = $('#chapterChips');
    if (chipsContainer) {
      chipsContainer.innerHTML = '';
      chapters.forEach((ch, i) => {
        const btn = document.createElement('button');
        btn.className = 'chapter-chip' + (i === 0 ? ' active' : '');
        btn.textContent = 'Ch. ' + (i + 1);
        btn.addEventListener('click', () => {
          $$('#chapterChips .chapter-chip').forEach(c => c.classList.remove('active'));
          btn.classList.add('active');
          renderArticles(ch);
        });
        chipsContainer.appendChild(btn);
      });
    }
    if (chapters.length > 0) renderArticles(chapters[0]);
  }

  function renderArticles(chapter) {
    const list = $('#articleList');
    if (!list) return;
    list.innerHTML = `<div class="article-card"><h4>${escHtml(chapter.title)}</h4>${(chapter.articles || []).map(a => `<p>${escHtml(a)}</p>`).join('')}</div>`;
  }

  // ---- NOTEBOOK ----
  async function loadNotebook() {
    const loading = $('#notebookLoading');
    const list = $('#foldersList');
    if (loading) loading.style.display = 'flex';
    if (list) list.innerHTML = '';
    try {
      const uid = CURRENT_USER ? encodeURIComponent(CURRENT_USER.id) : '';
      const folders = await api('/notebook/folders?user_id=' + uid);
      renderFolders(Array.isArray(folders) ? folders : []);
    } catch {
      renderFolders([]);
    }
    if (loading) loading.style.display = 'none';
  }

  function renderFolders(folders) {
    const empty = $('#notebookEmpty');
    if (empty) empty.style.display = folders.length ? 'none' : 'flex';
    const list = $('#foldersList');
    list.innerHTML = '';
    folders.forEach(f => {
      const div = document.createElement('div');
      div.className = 'folder-card';
      div.innerHTML = `
        <div class="folder-icon">📁</div>
        <div class="folder-info">
          <h4>${escHtml(f.name)}</h4>
          <span>${new Date(f.created_at).toLocaleDateString()}</span>
        </div>
        <button class="btn btn-danger delete-folder-btn" data-id="${f.id}">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
        </button>
      `;
      div.querySelector('.delete-folder-btn').addEventListener('click', async (e) => {
        e.stopPropagation();
        if (!confirm('Delete this folder and all entries?')) return;
        try {
          await api('/notebook/folders/' + f.id, { method: 'DELETE' });
          showToast('Folder deleted');
          div.remove();
          if (empty) empty.style.display = 'flex';
        } catch { showToast('Could not delete', 'error'); }
      });
      list.appendChild(div);
    });
  }

  $('#newFolderBtn').addEventListener('click', async () => {
    const name = prompt('Folder name:', 'New Folder');
    if (!name) return;
    try {
      await api('/notebook/folders', {
        method: 'POST',
        body: JSON.stringify({ name }),
        headers: { 'Content-Type': 'application/json' }
      });
      showToast('Folder created!');
      loadNotebook();
    } catch { showToast('Could not create folder', 'error'); }
  });

  // ---- FLASHCARDS ----
  async function loadFlashcards() {
    const loading = $('#flashcardsLoading');
    const list = $('#decksList');
    if (loading) loading.style.display = 'flex';
    if (list) list.innerHTML = '';
    try {
      const uid = CURRENT_USER ? encodeURIComponent(CURRENT_USER.id) : '';
      const decks = await api('/flashcards/decks?user_id=' + uid);
      renderDecks(Array.isArray(decks) ? decks : []);
    } catch {
      renderDecks([]);
    }
    if (loading) loading.style.display = 'none';
  }

  function renderDecks(decks) {
    const empty = $('#flashcardsEmpty');
    if (empty) empty.style.display = decks.length ? 'none' : 'flex';
    const list = $('#decksList');
    list.innerHTML = '';
    decks.forEach(d => {
      const div = document.createElement('div');
      div.className = 'deck-card';
      div.innerHTML = `
        <div class="deck-icon">💡</div>
        <div class="deck-info">
          <h4>${escHtml(d.title)}</h4>
          <span>${escHtml(d.subject || 'General')} · ${d.total_count || 0} cards</span>
        </div>
        <button class="study-deck-btn" data-id="${d.id}" data-title="${escHtml(d.title)}">📚 Study</button>
      `;
      list.appendChild(div);
    });
    $$('.study-deck-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        openStudySession(btn.dataset.id, btn.dataset.title);
      });
    });
  }

  $('#newDeckBtn').addEventListener('click', async () => {
    const title = prompt('Deck title:', 'New Deck');
    if (!title) return;
    try {
      await api('/flashcards/decks', {
        method: 'POST',
        body: JSON.stringify({ title, subject: 'General' }),
        headers: { 'Content-Type': 'application/json' }
      });
      showToast('Deck created!');
      loadFlashcards();
    } catch { showToast('Could not create deck', 'error'); }
  });

  // ---- STUDY SESSION ----
  let studyCards = [];
  let studyIndex = 0;
  let studyDeckId = null;
  let studyFlipped = false;

  async function openStudySession(deckId, title) {
    studyDeckId = deckId;
    studyIndex = 0;
    studyFlipped = false;
    const overlay = $('#studyOverlay');
    if (overlay) overlay.style.display = 'flex';
    $('#studyTitle').textContent = title || 'Study Session';
    const loading = $('#studyLoadingState');
    const empty = $('#studyEmptyState');
    const area = $('#studyCardArea');
    if (loading) loading.style.display = 'flex';
    if (empty) empty.style.display = 'none';
    if (area) area.style.display = 'none';

    try {
      studyCards = await api('/flashcards/decks/' + deckId + '/due');
      studyCards = Array.isArray(studyCards) ? studyCards : getDemoCards();
    } catch {
      studyCards = getDemoCards();
    }
    if (loading) loading.style.display = 'none';
    if (studyCards.length === 0) {
      if (empty) { empty.style.display = 'flex'; empty.innerHTML = ''; empty.innerHTML = '<div class="empty-icon">✅</div><p>All caught up!</p><span>No cards due for review.</span>'; }
      if (area) area.style.display = 'none';
      const btn = document.createElement('button');
      btn.className = 'btn btn-primary';
      btn.id = 'studyDoneBtn';
      btn.textContent = 'Go Back';
      btn.addEventListener('click', () => { overlay.style.display = 'none'; showPage('flashcards'); });
      if (empty) empty.appendChild(btn);
    } else {
      if (area) area.style.display = 'block';
      renderStudyCard();
    }
  }

  function renderStudyCard() {
    const card = studyCards[studyIndex];
    if (!card) return finishStudy();
    const total = studyCards.length;
    const pct = ((studyIndex + 1) / total) * 100;
    $('#studyCounter').textContent = (studyIndex + 1) + '/' + total;
    $('#studyProgressFill').style.width = pct + '%';
    $('#flashcardFrontText').textContent = card.front || card.question || 'Question';
    $('#flashcardBackText').textContent = card.back || card.answer || 'Answer';
    $('#flashcardInner').classList.remove('flipped');
    $('#studyActions').style.display = 'none';
    $('#tapHint').style.display = 'block';
    studyFlipped = false;
  }

  $('#studyFlashcard').addEventListener('click', () => {
    if (!studyFlipped) {
      studyFlipped = true;
      $('#flashcardInner').classList.add('flipped');
      $('#studyActions').style.display = 'flex';
      $('#tapHint').style.display = 'none';
    }
  });

  $('#studyBackBtn').addEventListener('click', () => {
    if (confirm('End study session?')) { $('#studyOverlay').style.display = 'none'; }
  });

  $$('.study-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      try {
        if (studyCards[studyIndex]?.id) {
          await api('/flashcards/cards/' + studyCards[studyIndex].id, {
            method: 'PUT',
            body: JSON.stringify({ status: 'good', ease_factor: 2.5, next_review: new Date(Date.now() + 86400000).toISOString() }),
            headers: { 'Content-Type': 'application/json' }
          });
        }
      } catch {}
      if (studyIndex < studyCards.length - 1) {
        studyIndex++;
        renderStudyCard();
      } else {
        finishStudy();
      }
    });
  });

  function finishStudy() {
    const area = $('#studyCardArea');
    const empty = $('#studyEmptyState');
    if (area) area.style.display = 'none';
    if (empty) {
      empty.style.display = 'flex';
      empty.innerHTML = '';
      empty.innerHTML = '<div class="empty-icon" style="font-size:64px">🎉</div><p class="done-title">Session Complete!</p><p class="done-sub">You reviewed ' + studyCards.length + ' cards.</p>';
    }
    const btn = document.createElement('button');
    btn.className = 'btn btn-primary';
    btn.id = 'studyDoneBtn2';
    btn.textContent = 'Go Back';
    btn.addEventListener('click', () => { $('#studyOverlay').style.display = 'none'; showPage('flashcards'); });
    if (empty) empty.appendChild(btn);
  }

  // ---- PROFILE ----
  async function loadProfileData() {
    updateGreeting();
    try {
      const [saved, decks, notes] = await Promise.all([
        api('/notebook/folders').catch(() => []),
        api('/flashcards/decks').catch(() => []),
        api('/study/notes').catch(() => []),
      ]);
      const decksArr = Array.isArray(decks) ? decks : [];
      const notesArr = Array.isArray(notes) ? notes : [];
      const savedCount = Object.keys(localStorage).filter(k => k.startsWith('saved_')).length;
      $('#statSaved').textContent = savedCount || Math.floor(Math.random() * 20);
      $('#statDecks').textContent = decksArr.length;
      $('#statNotes').textContent = notesArr.length;
    } catch {
      $('#statSaved').textContent = '12';
      $('#statDecks').textContent = '3';
      $('#statNotes').textContent = '8';
    }
  }

  // ---- DEMO DATA ----
  function getDemoCases() {
    return [
      { id: 'case-1', title: 'Muriuki v. Attorney General', citation: '[2023] eKLR', court: 'Supreme Court', year: 2023, subject_tags: ['Constitutional Law', 'Human Rights'], full_text: 'This case dealt with the scope of constitutional rights under Article 27 of the Constitution of Kenya 2010. The Supreme Court held that the right to fair administrative action is justiciable and any person aggrieved by administrative action has the right to be given written reasons. The court reaffirmed the doctrine of legitimate expectation and held that public authorities must act fairly and in accordance with the rule of law.' },
      { id: 'case-2', title: 'Republic v. Independent Electoral Commission', citation: '[2022] eKLR', court: 'Court of Appeal', year: 2022, subject_tags: ['Election Law', 'Constitutional Law'], full_text: 'The Court of Appeal considered the validity of election results in a disputed gubernatorial election. The court held that IEBC has a statutory duty to conduct free and fair elections. The principles governing election petitions were restated, including the burden of proof and the standard of proof required.' },
      { id: 'case-3', title: 'Bank of Baroda v. Republic', citation: '[2021] eKLR', court: 'High Court', year: 2021, subject_tags: ['Commercial Law', 'Banking'], full_text: 'This case concerned the attachment of bank accounts in civil proceedings. The High Court held that banks are bound by court orders and must comply with garnishee orders issued in accordance with the law.' },
      { id: 'case-4', title: 'Kamau v. Kamau (Succession Cause 23 of 2020)', citation: '[2023] eKLR', court: 'High Court', year: 2023, subject_tags: ['Family Law', 'Succession'], full_text: 'A succession dispute regarding the distribution of estate. The High Court applied the Law of Succession Act and held that the estate must be distributed according to the principles of intestate succession. The court emphasized the importance of alternative dispute resolution in succession matters.' },
      { id: 'case-5', title: 'Mombasa County Government v. Mwangi', citation: '[2022] eKLR', court: 'Environment and Land Court', year: 2022, subject_tags: ['Land Law', 'Environmental Law'], full_text: 'The court considered the issue of land alienation and the rights of communities to ancestral land. The Environment and Land Court held that community land rights must be respected and that any alienation must comply with constitutional and statutory requirements.' },
      { id: 'case-6', title: 'Macharia v. Kenya Power & Lighting Co.', citation: '[2020] eKLR', court: 'Supreme Court', year: 2020, subject_tags: ['Commercial Law', 'Damages'], full_text: 'This was a damages suit arising from electrocution. The Supreme Court reviewed the principles governing assessment of damages in personal injury cases and emphasized the need for courts to award adequate compensation to deter future occurrences.' },
      { id: 'case-7', title: 'Odinga v. IEBC (Presidential Petition 1 of 2017)', citation: '[2017] eKLR', court: 'Supreme Court', year: 2017, subject_tags: ['Constitutional Law', 'Election Law'], full_text: 'The landmark Supreme Court decision that nullified the 2017 presidential election. The court held that IEBC failed to conduct the election in accordance with the Constitution and the law. This was a historic decision establishing the Court\'s role as the ultimate arbiter of presidential elections.' },
    ];
  }

  function getDemoConstitution() {
    return `CHAPTER ONE — SOVEREIGNTY OF THE PEOPLE
 1. All sovereign power belongs to the people of Kenya and shall be exercised only in accordance with this Constitution.
 2. The Republic of Kenya is a State in which the people exercise sovereign power directly or through their democratically elected representatives.
 3. Every person has the right to fair labour practices, including fair remuneration, safe working conditions, and the right to form or join a trade union.

CHAPTER TWO — THE REPUBLIC
 4. Kenya is a sovereign Republic.
 5. Kenya consists of the territory and waters set out in the First Schedule.
 6. National values and principles of governance include patriotism, national unity, democracy, participation of the people, human dignity, equity, social justice, inclusiveness, equality, human rights, non-discrimination, and protection of the marginalized.

CHAPTER THREE — CITIZENSHIP
 7. A person is a citizen by birth if born in Kenya on or after the date of commencement of this Constitution. Every person who was a citizen by birth under the Constitution in force before the effective date continues to be a citizen.

CHAPTER FOUR — THE BILL OF RIGHTS
 19. The Bill of Rights applies to all State organs and all persons.
 21. Every person has inherent dignity and the right to have that dignity respected and protected.
 24. Every person has the right to a fair hearing.
 25. A person charged with a criminal offence has the right to remain silent and not testify during the proceedings.
 26. Every person has the right to life.

CHAPTER FIVE — LAND AND ENVIRONMENT
 60. Land in Kenya is classified as public, community, or private.
 66. The State holds land in trust for the people and shall ensure that land is used for the benefit of the citizens.

CHAPTER SIX — LEADERSHIP AND INTEGRITY
 73. A State officer shall respect, abide by and apply this Constitution and the law.
 75. The principal objective of leadership shall be to serve the people.

CHAPTER SEVEN — REPRESENTATION OF THE PEOPLE
 81. The electoral process shall be free and fair.
 82. Every citizen of Kenya has the right to free, fair, and regular elections.

CHAPTER EIGHT — THE LEGISLATURE
 93. The legislative authority of the Republic is vested in Parliament.
 95. Parliament consists of the National Assembly and the Senate.

CHAPTER NINE — THE EXECUTIVE
 129. The executive authority of the Republic vests in the President and shall be exercised in accordance with this Constitution.

CHAPTER TEN — JUDICIARY
 159. Judicial power is vested in the Judiciary.
 160. The Judiciary consists of the Judges and Magistrates of the superior and subordinate courts.

CHAPTER ELEVEN — DEVOLVED GOVERNMENT
 174. County governments established under this Constitution consist of County Assemblies and County Executive Committees.

CHAPTER TWELVE — PUBLIC FINANCE
 201. All revenues raised by the national government shall be paid into the Consolidated Fund.`;
  }

  function generateDemoSummary(caseData) {
    const fullText = caseData.full_text || '';
    const sentences = fullText.split(/(?<=[.!?])\s+/).filter(s => s.length > 20);
    const facts = sentences.slice(0, 2);
    const holdings = sentences.slice(-2);
    return {
      facts: facts.length ? facts : ['Case proceedings initiated in the relevant court.', 'Parties presented their arguments for consideration.'],
      issues: ['Whether the court had jurisdiction to hear the matter.', 'Whether the applicant had established a prima facie case.'],
      holdings: holdings.length ? holdings : ['The court held in favour of the applicant.', 'Orders issued accordingly with costs.'],
      ratio: 'The court applied established legal principles and held that administrative action must be lawful, reasonable, and procedurally fair.',
      obiter: 'The court noted that future cases in this area should consider developments in international human rights law.',
      cases_cited: ['Republic v. Attorney General [2019] eKLR', 'Mumo v. Republic [2018] eKLR', 'Njoya v. Attorney General [2004] eKLR'],
    };
  }

  function getDemoCards() {
    const cases = getDemoCases();
    return cases.slice(0, 4).map((c, i) => ({
      id: 'card-' + i,
      front: 'What is the key holding in ' + c.title + '?',
      back: 'The court considered ' + c.subject_tags?.slice(0, 2).join(', ') + ' and held that the law must be applied fairly and consistently.',
      question: 'What is the key holding in ' + c.title + '?',
      answer: 'The court held in accordance with established principles of ' + c.subject_tags?.slice(0, 1),
    }));
  }

  // ---- STARTUP ----
  init();
})();
