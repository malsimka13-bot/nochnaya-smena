// Обёртка над fetch: токен, единый формат ошибок {kind, detail}.
const KEY = "smena.token";

function loadToken() {
  try { return localStorage.getItem(KEY); } catch { return null; }
}

export const session = { token: loadToken(), user: null, next: null };

export function setToken(token) {
  session.token = token;
  try {
    if (token) localStorage.setItem(KEY, token);
    else localStorage.removeItem(KEY);
  } catch { /* хранилище недоступно: вход продержится до перезагрузки страницы */ }
}

export class ApiError extends Error {
  constructor(status, kind, detail) {
    super(detail);
    this.status = status;
    this.kind = kind;     // input | auth | server | network
    this.detail = detail;
  }
}

export async function api(path, { method = "GET", body } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (session.token) headers.Authorization = `Bearer ${session.token}`;
  let res;
  try {
    res = await fetch(`/api${path}`, { method, headers, body: body !== undefined ? JSON.stringify(body) : undefined });
  } catch {
    throw new ApiError(0, "network", "Нет связи с сервером. Проверьте, что он запущен, и повторите.");
  }
  let data = null;
  try { data = await res.json(); } catch { /* тело пустое или не JSON */ }
  if (!res.ok) {
    if (res.status === 401 && session.token) {
      setToken(null);
      session.user = null;
      window.dispatchEvent(new Event("session-expired"));
    }
    throw new ApiError(res.status, data?.kind ?? (res.status >= 500 ? "server" : "input"), data?.detail ?? "Неизвестная ошибка");
  }
  return data;
}

export async function loadUser() {
  if (!session.token) return;
  try {
    session.user = await api("/me");
  } catch (err) {
    if (err.kind === "network" || err.kind === "server") throw err;
    session.user = null;
  }
}
