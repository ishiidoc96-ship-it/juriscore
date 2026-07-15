const NAV_ITEMS = [
  { id: 'dashboard', icon: 'dashboard', label: 'Dashboard', href: '/app.html#home' },
  { id: 'search', icon: 'search', label: 'Search', href: '/app.html#search' },
  { id: 'constitution', icon: 'balance', label: 'Constitution', href: '/app.html#constitution' },
  { id: 'notebook', icon: 'book', label: 'Notebook', href: '/app.html#notebook' },
  { id: 'flashcards', icon: 'quiz', label: 'Flashcards', href: '/app.html#flashcards' },
  { id: 'bookmarks', icon: 'bookmark', label: 'Bookmarks', href: '/app.html#bookmarks' },
  { id: 'history', icon: 'history', label: 'History', href: '/app.html#history' },
  { id: 'profile', icon: 'person', label: 'Profile', href: '/app.html#profile' },
];

const BOTTOM_NAV_IDS = ['dashboard', 'search', 'notebook', 'flashcards', 'profile'];

function getActivePage() {
  const hash = window.location.hash.replace('#', '') || 'home';
  const map = {
    home: 'dashboard',
    search: 'search',
    constitution: 'constitution',
    notebook: 'notebook',
    flashcards: 'flashcards',
    bookmarks: 'bookmarks',
    history: 'history',
    profile: 'profile',
  };
  return map[hash] || 'dashboard';
}

function renderSidebar() {
  const activeId = getActivePage();

  const navLinks = NAV_ITEMS.map(item => {
    const isActive = item.id === activeId;
    return `
      <a
        href="${item.href}"
        data-page="${item.id}"
        class="flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200 ${
          isActive
            ? 'bg-primary-container text-on-primary-container'
            : 'text-on-surface-variant hover:bg-surface-container-high'
        }"
      >
        <span class="material-symbols-outlined text-[20px] ${isActive ? 'filled' : ''}">${item.icon}</span>
        <span>${item.label}</span>
      </a>
    `;
  }).join('');

  return `
    <aside class="fixed top-0 left-0 z-40 hidden md:flex flex-col w-64 h-full bg-surface-container-lowest border-r border-outline-variant/20">
      <div class="flex items-center gap-3 px-6 py-5">
        <div class="flex items-center justify-center w-10 h-10 rounded-lg bg-primary-container">
          <span class="material-symbols-outlined text-on-primary-container text-xl">gavel</span>
        </div>
        <span class="headline-sm text-on-surface">Juriscore</span>
      </div>

      <nav class="flex-1 flex flex-col gap-1 px-3 py-2 overflow-y-auto">
        ${navLinks}
      </nav>

      <div class="px-3 py-4 border-t border-outline-variant/20">
        <button
          onclick="handleLogout()"
          class="flex items-center gap-3 w-full px-4 py-3 rounded-xl text-sm font-medium text-on-surface-variant hover:bg-surface-container-high transition-all duration-200"
        >
          <span class="material-symbols-outlined text-[20px]">logout</span>
          <span>Log out</span>
        </button>
      </div>
    </aside>
  `;
}

function renderBottomNav() {
  const activeId = getActivePage();

  const items = NAV_ITEMS.filter(item => BOTTOM_NAV_IDS.includes(item.id));

  const tabs = items.map(item => {
    const isActive = item.id === activeId;
    return `
      <a
        href="${item.href}"
        data-page="${item.id}"
        class="relative flex flex-col items-center justify-center flex-1 h-full text-xs font-medium transition-colors duration-200 ${
          isActive ? 'text-primary' : 'text-on-surface-variant'
        }"
      >
        ${isActive ? '<span class="absolute top-0 left-1/2 -translate-x-1/2 w-8 h-[3px] rounded-full bg-primary"></span>' : ''}
        <span class="material-symbols-outlined text-[24px] ${isActive ? 'filled' : ''}">${item.icon}</span>
        <span class="mt-0.5 leading-none">${item.label}</span>
      </a>
    `;
  }).join('');

  return `
    <nav class="fixed bottom-0 left-0 right-0 z-40 md:hidden h-16 bg-surface-container-lowest/90 backdrop-blur-lg border-t border-outline-variant/20 pb-safe">
      <div class="flex items-center justify-around h-full">
        ${tabs}
      </div>
    </nav>
  `;
}

function renderTopBar(title, options = {}) {
  const { showBack = false } = options;
  const isHashPage = window.location.hash && window.location.hash !== '#home';
  const showHamburger = !showBack && isHashPage;

  const left = showBack
    ? `<button onclick="history.back()" class="flex items-center justify-center w-10 h-10 rounded-full hover:bg-surface-container-high transition-colors">
         <span class="material-symbols-outlined">arrow_back</span>
       </button>`
    : showHamburger
      ? `<button onclick="toggleMobileMenu()" class="flex items-center justify-center w-10 h-10 rounded-full hover:bg-surface-container-high transition-colors md:hidden">
           <span class="material-symbols-outlined">menu</span>
         </button>`
      : `
        <div class="hidden md:flex items-center gap-3">
          <div class="flex items-center justify-center w-10 h-10 rounded-lg bg-primary-container">
            <span class="material-symbols-outlined text-on-primary-container text-xl">gavel</span>
          </div>
          <span class="headline-sm text-on-surface">Juriscore</span>
        </div>
      `;

  return `
    <header class="fixed top-0 left-0 right-0 z-30 flex items-center justify-between h-16 px-4 md:pl-[256px] bg-surface-container-lowest/80 backdrop-blur-lg border-b border-outline-variant/20">
      <div class="flex items-center">
        ${left}
        <h1 class="title-lg text-on-surface ml-2 md:ml-4">${title}</h1>
      </div>
      <div class="flex items-center gap-2">
        <button class="relative flex items-center justify-center w-10 h-10 rounded-full hover:bg-surface-container-high transition-colors">
          <span class="material-symbols-outlined text-on-surface-variant">notifications</span>
          <span class="absolute top-2 right-2 w-2 h-2 rounded-full bg-primary"></span>
        </button>
        <button onclick="window.location.href='/app.html#profile'" class="flex items-center justify-center w-9 h-9 rounded-full bg-primary-container overflow-hidden">
          <span class="material-symbols-outlined text-on-primary-container text-lg">person</span>
        </button>
      </div>
    </header>
  `;
}

function initNav() {
  const sidebarContainer = document.getElementById('sidebar-container');
  const bottomNavContainer = document.getElementById('bottomnav-container');

  if (sidebarContainer) {
    sidebarContainer.innerHTML = renderSidebar();
  }

  if (bottomNavContainer) {
    bottomNavContainer.innerHTML = renderBottomNav();
  }
}

function setActivePage(pageName) {
  document.querySelectorAll('[data-page]').forEach(el => {
    const isActive = el.dataset.page === pageName;

    if (el.closest('#sidebar-container')) {
      el.className = `flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200 ${
        isActive
          ? 'bg-primary-container text-on-primary-container'
          : 'text-on-surface-variant hover:bg-surface-container-high'
      }`;
      const icon = el.querySelector('.material-symbols-outlined');
      if (icon) {
        icon.classList.toggle('filled', isActive);
      }
    }

    if (el.closest('#bottomnav-container')) {
      el.className = `relative flex flex-col items-center justify-center flex-1 h-full text-xs font-medium transition-colors duration-200 ${
        isActive ? 'text-primary' : 'text-on-surface-variant'
      }`;
      const icon = el.querySelector('.material-symbols-outlined');
      if (icon) {
        icon.classList.toggle('filled', isActive);
      }
      const existingIndicator = el.querySelector('.absolute');
      if (existingIndicator) existingIndicator.remove();
      if (isActive) {
        const indicator = document.createElement('span');
        indicator.className = 'absolute top-0 left-1/2 -translate-x-1/2 w-8 h-[3px] rounded-full bg-primary';
        el.prepend(indicator);
      }
    }
  });
}

function toggleMobileMenu() {
  const sidebarContainer = document.getElementById('sidebar-container');
  if (!sidebarContainer) return;

  const sidebar = sidebarContainer.querySelector('aside');
  if (!sidebar) return;

  const isOpen = sidebar.classList.contains('mobile-open');

  if (isOpen) {
    sidebar.classList.remove('mobile-open', 'fixed', 'inset-0', 'z-50', 'w-full');
    sidebar.classList.add('hidden', 'md:flex');
    sidebar.style.transform = '';
    document.body.style.overflow = '';
    const overlay = document.getElementById('mobile-menu-overlay');
    if (overlay) overlay.remove();
  } else {
    const overlay = document.createElement('div');
    overlay.id = 'mobile-menu-overlay';
    overlay.className = 'fixed inset-0 z-50 bg-black/40 md:hidden';
    overlay.onclick = toggleMobileMenu;
    document.body.appendChild(overlay);

    sidebar.classList.remove('hidden', 'md:flex');
    sidebar.classList.add('mobile-open', 'fixed', 'inset-0', 'z-50', 'w-full');
    sidebar.style.transform = 'translateX(0)';
    document.body.style.overflow = 'hidden';
  }
}

function handleLogout() {
  localStorage.removeItem('juriscore_user');
  window.location.href = '/app.html#home';
}
