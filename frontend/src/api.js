const BASE = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8001").replace(/\/$/, "");
const STORAGE_KEY = "airline.tokens";

// Keep in step with the backend's supported file types (app/services/extraction.py).
export const ACCEPTED_EXTENSIONS = [
  ".pdf", ".docx", ".txt", ".md",
  ".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".csv", ".html", ".css", ".sql", ".yaml", ".yml",
];
export const MAX_UPLOAD_BYTES = 5 * 1024 * 1024;

export class ApiError extends Error {
  constructor(status, message, retryAfter = null) {
    super(message);
    this.status = status;
    this.retryAfter = retryAfter;
  }
}

// ---- tokens -------------------------------------------------------------------------------
function loadTokens() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY));
  } catch {
    return null;
  }
}

function saveTokens(tokens) {
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({ access: tokens.access_token, refresh: tokens.refresh_token })
  );
}

export function clearTokens() {
  localStorage.removeItem(STORAGE_KEY);
}

export const hasSession = () => Boolean(loadTokens()?.refresh);

function uuid() {
  if (crypto.randomUUID) return crypto.randomUUID();
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = crypto.getRandomValues(new Uint8Array(1))[0] & 15;
    return (c === "x" ? r : (r & 3) | 8).toString(16);
  });
}

// ---- requests -----------------------------------------------------------------------------
async function toApiError(res) {
  let message = `Something went wrong (${res.status}).`;
  try {
    const body = await res.json();
    if (body?.error?.message) message = body.error.message;
    else if (Array.isArray(body?.detail) && body.detail[0]?.msg) message = body.detail[0].msg;
  } catch {
    // body was not JSON; keep the generic message
  }
  const retry = Number(res.headers.get("Retry-After"));
  return new ApiError(res.status, message, retry > 0 ? retry : null);
}

let refreshing = null;

function refreshTokens() {
  if (!refreshing) {
    refreshing = (async () => {
      const tokens = loadTokens();
      if (!tokens?.refresh) throw new ApiError(401, "Your session expired. Sign in again.");
      const res = await fetch(`${BASE}/api/v1/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: tokens.refresh }),
      });
      if (!res.ok) {
        clearTokens();
        window.dispatchEvent(new Event("airline:signout"));
        throw new ApiError(401, "Your session expired. Sign in again.");
      }
      saveTokens(await res.json());
    })().finally(() => {
      refreshing = null;
    });
  }
  return refreshing;
}

async function request(path, { method = "GET", data, body, headers = {}, signal, auth = true } = {}) {
  const send = () => {
    const h = { ...headers };
    if (data !== undefined) h["Content-Type"] = "application/json";
    const tokens = loadTokens();
    if (auth && tokens?.access) h.Authorization = `Bearer ${tokens.access}`;
    return fetch(`${BASE}${path}`, {
      method,
      headers: h,
      body: data !== undefined ? JSON.stringify(data) : body,
      signal,
    });
  };

  let res;
  try {
    res = await send();
    if (res.status === 401 && auth && loadTokens()?.refresh) {
      await refreshTokens();
      res = await send();
    }
  } catch (err) {
    if (err.name === "AbortError" || err instanceof ApiError) throw err;
    throw new ApiError(0, "Can't reach the server. Check your connection and try again.");
  }

  if (!res.ok) throw await toApiError(res);
  return res;
}

const getJson = async (path, options) => (await request(path, options)).json();

// ---- streaming chat -----------------------------------------------------------------------
// documentIds: omit (or pass an empty list) to answer from all documents.
async function streamChat({ message, chatId, documentIds, useV2, signal, onEvent }) {
  const res = await request(useV2 ? "/api/v2/chat" : "/api/v1/chat", {
    method: "POST",
    data: {
      message,
      chat_id: chatId || null,
      document_ids: documentIds && documentIds.length ? documentIds : null,
    },
    signal,
  });

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let end;
    while ((end = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      const line = block.split("\n").find((l) => l.startsWith("data:"));
      if (!line) continue;
      try {
        onEvent(JSON.parse(line.slice(5).trim()));
      } catch {
        // ignore a malformed event
      }
    }
  }
}

// ---- public API ---------------------------------------------------------------------------
export const api = {
  async register(email, password, tenantName) {
    saveTokens(
      await getJson("/api/v1/auth/register", {
        method: "POST",
        data: { email, password, tenant_name: tenantName },
        auth: false,
      })
    );
  },

  async login(email, password) {
    saveTokens(
      await getJson("/api/v1/auth/login", {
        method: "POST",
        data: { email, password },
        auth: false,
      })
    );
  },

  async logout() {
    const tokens = loadTokens();
    clearTokens();
    if (!tokens?.refresh) return;
    try {
      await fetch(`${BASE}/api/v1/auth/logout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: tokens.refresh }),
      });
    } catch {
      // the local session is already gone; nothing else to do
    }
  },

  me: () => getJson("/api/v1/auth/me"),
  flags: () => getJson("/api/v1/flags"),
  billingStatus: () => getJson("/api/v1/billing/status"),
  checkout: () =>
    getJson("/api/v1/billing/checkout", {
      method: "POST",
      headers: { "Idempotency-Key": uuid() },
    }),

  documents: () => getJson("/api/v1/documents"),
  uploadDocument(file) {
    const form = new FormData();
    form.append("file", file);
    return getJson("/api/v1/documents", {
      method: "POST",
      body: form,
      headers: { "Idempotency-Key": uuid() },
    });
  },
  async deleteDocument(id) {
    await request(`/api/v1/documents/${id}`, { method: "DELETE" });
  },

  listChats: () => getJson("/api/v1/chats"),
  chatMessages: (id) => getJson(`/api/v1/chats/${id}/messages`),
  async deleteChat(id) {
    await request(`/api/v1/chats/${id}`, { method: "DELETE" });
  },

  streamChat,
};