/**
 * api.js — Authenticated HTTP client for the LEO Eval Console.
 * Depends on: nothing (loaded first)
 */

const API = (() => {
  function getToken() {
    return localStorage.getItem('leo_eval_token') || '';
  }

  function authHeaders() {
    const token = getToken();
    return {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
  }

  function handleUnauthorized() {
    localStorage.removeItem('leo_eval_token');
    localStorage.removeItem('leo_eval_reviewer_id');
    window.location.href = '/';
  }

  async function get(path) {
    const res = await fetch(path, { headers: authHeaders() });
    if (res.status === 401) { handleUnauthorized(); return null; }
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  }

  async function post(path, body) {
    const res = await fetch(path, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(body),
    });
    if (res.status === 401) { handleUnauthorized(); return null; }
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  }

  async function login(reviewer_id, password) {
    const res = await fetch('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reviewer_id, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Invalid credentials');
    }
    return res.json();
  }

  async function adminGet(path, adminPassword) {
    const res = await fetch(path, {
      headers: { 'X-Admin-Password': adminPassword },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  }

  async function adminGetCsv(path, adminPassword) {
    const res = await fetch(path, {
      headers: { 'X-Admin-Password': adminPassword },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.blob();
  }

  return { get, post, login, adminGet, adminGetCsv };
})();
