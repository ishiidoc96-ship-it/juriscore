const API_BASE = window.location.origin + '/api';

async function apiFetch(endpoint, options = {}) {
  const token = localStorage.getItem('juriscore_token');
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  try {
    const res = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });
    if (res.status === 401) {
      localStorage.removeItem('juriscore_token');
      localStorage.removeItem('juriscore_user');
      window.location.href = '/login.html';
      return null;
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return await res.json();
  } catch (e) {
    console.error(`API Error [${endpoint}]:`, e);
    throw e;
  }
}

const api = {
  get: (ep) => apiFetch(ep),
  post: (ep, data) => apiFetch(ep, { method: 'POST', body: JSON.stringify(data) }),
  put: (ep, data) => apiFetch(ep, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (ep) => apiFetch(ep, { method: 'DELETE' }),
};

function showToast(message, type = 'info', duration = 3000) {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.style.cssText = 'position:fixed;top:20px;right:20px;z-index:10000;display:flex;flex-direction:column;gap:8px;';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.style.cssText = 'padding:12px 20px;border-radius:8px;color:#fff;font-size:14px;font-family:inherit;box-shadow:0 4px 12px rgba(0,0,0,0.15);display:flex;align-items:center;gap:8px;opacity:0;transform:translateX(40px);transition:all 0.3s ease;min-width:280px;max-width:420px;';

  const colors = { success: '#10b981', error: '#ef4444', info: '#3b82f6' };
  toast.style.backgroundColor = colors[type] || colors.info;

  const icons = { success: '\u2713', error: '\u2717', info: '\u2139' };
  const icon = document.createElement('span');
  icon.style.cssText = 'font-size:16px;font-weight:bold;';
  icon.textContent = icons[type] || icons.info;

  const text = document.createElement('span');
  text.textContent = message;

  toast.appendChild(icon);
  toast.appendChild(text);
  container.appendChild(toast);

  requestAnimationFrame(() => {
    toast.style.opacity = '1';
    toast.style.transform = 'translateX(0)';
  });

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(40px)';
    setTimeout(() => {
      if (toast.parentNode) toast.parentNode.removeChild(toast);
      if (container.children.length === 0 && container.parentNode) {
        container.parentNode.removeChild(container);
      }
    }, 300);
  }, duration);
}

function setLoading(btnId, loading) {
  const btn = document.getElementById(btnId);
  if (!btn) return;

  if (loading) {
    btn.disabled = true;
    btn.dataset.originalText = btn.innerHTML;
    const spinner = document.createElement('span');
    spinner.className = 'btn-spinner';
    spinner.style.cssText = 'display:inline-block;width:16px;height:16px;border:2px solid rgba(255,255,255,0.3);border-top-color:#fff;border-radius:50%;animation:spin 0.6s linear infinite;margin-right:6px;vertical-align:middle;';
    btn.innerHTML = '';
    btn.appendChild(spinner);
    btn.appendChild(document.createTextNode(btn.dataset.originalText.replace(/<[^>]*>/g, '').trim()));
  } else {
    btn.disabled = false;
    if (btn.dataset.originalText) {
      btn.innerHTML = btn.dataset.originalText;
      delete btn.dataset.originalText;
    }
  }

  if (!document.getElementById('juriscore-spin-keyframes')) {
    const style = document.createElement('style');
    style.id = 'juriscore-spin-keyframes';
    style.textContent = '@keyframes spin{to{transform:rotate(360deg)}}';
    document.head.appendChild(style);
  }
}
