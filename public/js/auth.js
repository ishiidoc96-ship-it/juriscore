function isLoggedIn() {
  return !!localStorage.getItem('juriscore_token');
}

function getCurrentUser() {
  const data = localStorage.getItem('juriscore_user');
  return data ? JSON.parse(data) : null;
}

function saveAuth(token, user) {
  localStorage.setItem('juriscore_token', token);
  localStorage.setItem('juriscore_user', JSON.stringify(user));
}

function logout() {
  localStorage.removeItem('juriscore_token');
  localStorage.removeItem('juriscore_user');
  window.location.href = '/login.html';
}

async function login(email, password) {
  const data = await api.post('/auth/login', { email, password });
  if (data && data.token) {
    saveAuth(data.token, data.user);
    return data;
  }
  throw new Error('Login failed');
}

async function signup(name, email, password, university) {
  const data = await api.post('/auth/signup', { name, email, password, university });
  if (data && data.token) {
    saveAuth(data.token, data.user);
    return data;
  }
  throw new Error('Signup failed');
}

function requireAuth() {
  if (!isLoggedIn()) {
    window.location.href = '/login.html';
    return false;
  }
  return true;
}
