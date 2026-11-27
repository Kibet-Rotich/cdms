// Thin client for the REST API (/api/v1). Every screen goes through here, the same contract
// future mobile/USSD/integration clients will use.

const BASE = "/api/v1";
const TOKENS_KEY = "cdms.tokens";
const PURPOSE_KEY = "cdms.purpose";

export class ApiError extends Error {
  constructor(status, body) {
    super(body?.detail || `Request failed (${status})`);
    this.status = status;
    this.body = body || {};
    this.code = body?.code;
  }
}

function readJSON(storage, key) {
  try {
    return JSON.parse(storage.getItem(key) || "null");
  } catch {
    return null;
  }
}

export const tokens = {
  get: () => readJSON(localStorage, TOKENS_KEY),
  set: (t) => {
    try {
      localStorage.setItem(TOKENS_KEY, JSON.stringify(t));
    } catch {
      /* storage unavailable: session still works until reload */
    }
  },
  clear: () => {
    try {
      localStorage.removeItem(TOKENS_KEY);
    } catch {
      /* ignore */
    }
  },
};

export const DEFAULT_PURPOSE = {
  PRESCRIBER: "PRESCRIBING",
  PHARMACIST: "DISPENSING",
  REGULATOR: "OVERSIGHT",
  SYSTEM_ADMIN: "ADMINISTRATION",
  FACILITY_ADMIN: "ADMINISTRATION",
};

export const purpose = {
  get: () => {
    try {
      return sessionStorage.getItem(PURPOSE_KEY);
    } catch {
      return null;
    }
  },
  set: (p) => {
    try {
      sessionStorage.setItem(PURPOSE_KEY, p);
    } catch {
      /* ignore */
    }
  },
};

let refreshing = null;

async function refreshAccess() {
  const t = tokens.get();
  if (!t?.refresh) return false;
  refreshing ||= fetch(`${BASE}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh: t.refresh }),
  })
    .then(async (r) => {
      if (!r.ok) return false;
      const body = await r.json();
      tokens.set({ ...t, access: body.access, refresh: body.refresh || t.refresh });
      return true;
    })
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

export async function api(path, { method = "GET", body, headers = {}, raw = false, retry = true } = {}) {
  const t = tokens.get();
  const h = { Accept: "application/json", ...headers };
  if (body !== undefined) h["Content-Type"] = "application/json";
  if (t?.access) h.Authorization = `Bearer ${t.access}`;
  const p = purpose.get();
  if (p && !h["X-Purpose-Of-Use"]) h["X-Purpose-Of-Use"] = p;

  const res = await fetch(`${BASE}${path}`, { method, headers: h, body: body !== undefined ? JSON.stringify(body) : undefined });
  if (res.status === 401 && retry && t?.refresh) {
    if (await refreshAccess()) return api(path, { method, body, headers, raw, retry: false });
    tokens.clear();
    window.location.assign("/login");
  }
  if (raw) return res;
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { detail: `Server error (${res.status}). Please try again.` };
  }
  if (!res.ok) throw new ApiError(res.status, data);
  return data;
}

export const get = (path) => api(path);
export const post = (path, body, headers) => api(path, { method: "POST", body, headers });
export const patch = (path, body) => api(path, { method: "PATCH", body });

export function newIdempotencyKey() {
  return crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
