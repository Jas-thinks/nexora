export const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:18080";
const K = "nexora.tokens";
type Tokens = { access_token: string; refresh_token: string };

export const tokens = {
  get(): Tokens | null { try { return JSON.parse(localStorage.getItem(K) || "null"); } catch { return null; } },
  set(t: Tokens | null) { try { t ? localStorage.setItem(K, JSON.stringify(t)) : localStorage.removeItem(K); } catch {} },
};

export class ApiError extends Error { constructor(public status: number, msg: string) { super(msg); } }

async function raw(path: string, init: RequestInit, access?: string) {
  return fetch(API + path, { ...init, headers: { "Content-Type": "application/json", ...(access ? { Authorization: `Bearer ${access}` } : {}), ...(init.headers || {}) } });
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  let t = tokens.get();
  let res = await raw(path, init, t?.access_token);
  if (res.status === 401 && t) {
    const r = await raw("/auth/refresh", { method: "POST", body: JSON.stringify({ refresh_token: t.refresh_token }) });
    if (r.ok) { t = await r.json(); tokens.set(t); res = await raw(path, init, t!.access_token); }
    else tokens.set(null);
  }
  if (!res.ok) {
    let msg = res.statusText;
    try { const j = await res.json(); msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch {}
    throw new ApiError(res.status, msg);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

export const authCall = async (kind: "login" | "register", body: object) => {
  const t = await api<Tokens>(`/auth/${kind}`, { method: "POST", body: JSON.stringify(body) });
  tokens.set(t);
};

export async function upload<T>(path: string, form: FormData): Promise<T> {
  const go = (access?: string) => fetch(API + path, { method: "POST", body: form, headers: access ? { Authorization: `Bearer ${access}` } : {} });
  let t = tokens.get(); let res = await go(t?.access_token);
  if (res.status === 401 && t) {
    const r = await raw("/auth/refresh", { method: "POST", body: JSON.stringify({ refresh_token: t.refresh_token }) });
    if (r.ok) { t = await r.json(); tokens.set(t); res = await go(t!.access_token); }
  }
  if (!res.ok) { let m = res.statusText; try { const j = await res.json(); m = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch {} throw new ApiError(res.status, m); }
  return res.json();
}
