import { API, api, tokens } from "@/lib/api";

export type Final = { id: number; answer: string; provider: string; model: string | null; offline: boolean; validation: string[]; sources: { id: number; key: string; title: string; kind: string }[]; hint_level: number | null };

/** POST + SSE over fetch (EventSource can't send auth headers or a body). `onDelta` receives an unvalidated DRAFT; the returned final replaces it. */
export async function streamChat(body: object, onDelta: (t: string) => void, signal?: AbortSignal): Promise<Final> {
  const go = () => fetch(`${API}/mentor/chat/stream`, { method: "POST", signal, headers: { "Content-Type": "application/json", Authorization: `Bearer ${tokens.get()?.access_token ?? ""}` }, body: JSON.stringify(body) });
  let res = await go();
  if (res.status === 401) { await api("/auth/me").catch(() => {}); res = await go(); }
  if (!res.ok) { let m = res.statusText; try { const j = await res.json(); m = typeof j.detail === "string" ? j.detail : m; } catch {} throw new Error(m); }
  const reader = res.body!.getReader(); const dec = new TextDecoder(); let buf = ""; let final: Final | null = null;
  for (;;) {
    const { value, done } = await reader.read(); if (done) break;
    buf += dec.decode(value, { stream: true });
    let i: number;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const block = buf.slice(0, i); buf = buf.slice(i + 2);
      const ev = /^event: (\w+)/.exec(block)?.[1]; const data = /\ndata: (.*)$/s.exec(block)?.[1];
      if (!ev || !data) continue;
      const j = JSON.parse(data);
      if (ev === "delta") onDelta(j.text); else if (ev === "final") final = j;
    }
  }
  if (!final) throw new Error("The mentor connection closed before finishing.");
  return final;
}
