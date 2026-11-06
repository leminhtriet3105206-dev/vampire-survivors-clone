// REST client + session storage shared by every page.

// Set window.LS_CONFIG = { apiBase: 'https://api.example.com' } before loading
// the scripts if the frontend is hosted separately from the backend.
export const API_BASE = (window.LS_CONFIG && window.LS_CONFIG.apiBase) || '';

const TOKEN_KEY = 'ls_token';
const USER_KEY = 'ls_user';

export const session = {
  get token() {
    return localStorage.getItem(TOKEN_KEY);
  },
  get user() {
    try {
      return JSON.parse(localStorage.getItem(USER_KEY) || 'null');
    } catch {
      return null;
    }
  },
  save(token, user) {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
  },
  clear() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },
};

export class ApiError extends Error {
  constructor(message, status, details) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.details = details || null;
  }
}

/**
 * fetch() wrapper: JSON in/out, bearer token, consistent ApiError on failure.
 */
export async function request(path, { method = 'GET', body, auth = true } = {}) {
  const headers = { Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (auth && session.token) headers.Authorization = `Bearer ${session.token}`;

  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError('Cannot reach the server. Is it running?', 0);
  }

  let data = null;
  const text = await res.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
  }

  if (!res.ok || (data && data.success === false)) {
    const message = (data && data.message) || `Request failed (${res.status})`;
    if (res.status === 401 && auth) {
      session.clear();
      window.dispatchEvent(new CustomEvent('ls:unauthorized', { detail: message }));
    }
    throw new ApiError(message, res.status, data && data.details);
  }
  return data;
}

export const api = {
  register: (payload) => request('/api/auth/register', { method: 'POST', body: payload, auth: false }),
  login: (payload) => request('/api/auth/login', { method: 'POST', body: payload, auth: false }),
  me: () => request('/api/auth/me'),
  listSkins: () => request('/api/shop/skins', { auth: false }),
  purchaseSkin: (slug) => request(`/api/shop/skins/${encodeURIComponent(slug)}/purchase`, { method: 'POST' }),
  equipSkin: (slug) => request('/api/users/me/equipped-skin', { method: 'PATCH', body: { slug } }),
  equipFrame: (slug) => request('/api/users/me/equipped-frame', { method: 'PATCH', body: { slug } }),
  claimDaily: () => request('/api/users/me/daily-reward', { method: 'POST' }),
  addGold: (gold) => request('/api/users/me/add-gold', { method: 'POST', body: { gold } }),
  addDiamonds: (diamonds) => request('/api/users/me/add-diamonds', { method: 'POST', body: { diamonds } }),
  getMatchHistory: () => request('/api/users/me/history'),
  recordMatch: (payload) => request('/api/users/me/record-match', { method: 'POST', body: payload }),
  getLeaderboard: () => request('/api/users/leaderboard'),
  chatHistory: (limit = 50) => request(`/api/chat/messages?limit=${limit}`),
  // Admin Endpoints
  getAdminUsers: () => request('/api/admin/users'),
  adminGiveCurrency: (payload) => request('/api/admin/give-currency', { method: 'POST', body: payload }),
  adminSetStats: (payload) => request('/api/admin/set-stats', { method: 'POST', body: payload }),
};

