"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { Final, streamChat } from "@/lib/stream";

type Msg = { id?: number; role: "user" | "assistant"; content: string; meta?: Partial<Final> & { patterns?: string[] }; draft?: boolean; feedback?: number | null };
type Status = { configured: string[]; offline: boolean; message: string | null; tokens_used_24h: number; providers: Record<string, { model: string; ready: boolean }> };
const MODES: [string, string][] = [["concept", "Explain"], ["hint", "Hint ladder"], ["debug", "Debug"], ["review", "Code review"], ["complexity", "Complexity"], ["interview", "Mock interview"], ["editorial", "Editorial"]];
const LEVELS = ["Concept only", "Key observation", "Direction", "Approach in words", "Full solution"];

export default function Mentor() {
  const [msgs, setMsgs] = useState<Msg[]>([]), [input, setInput] = useState(""), [mode, setMode] = useState("concept"), [level, setLevel] = useState(1), [busy, setBusy] = useState(false), [err, setErr] = useState("");
  const [st, setSt] = useState<Status | null>(null), [notes, setNotes] = useState<{ id: number; title: string }[]>([]), [nt, setNt] = useState({ title: "", text: "" }), [opt, setOpt] = useState(false);
  const end = useRef<HTMLDivElement>(null), abort = useRef<AbortController | null>(null);
  const load = useCallback(() => {
    api<Status>("/mentor/status").then(setSt).catch(() => {});
    api<Msg[]>("/mentor/history").then(setMsgs).catch(() => {});
    api<{ id: number; title: string }[]>("/notes").then(setNotes).catch(() => {});
    api<{ training_opt_in: boolean }>("/me/prefs").then((p) => setOpt(p.training_opt_in)).catch(() => {});
  }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { try { const a = new URLSearchParams(window.location.search).get("ask"); if (a) setInput(a.slice(0, 500)); } catch {} }, []); // deep link from the crash course: pre-fills, never auto-sends
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);
  async function send() {
    const text = input.trim(); if (!text || busy) return; setBusy(true); setErr(""); setInput("");
    setMsgs((m) => [...m, { role: "user", content: text }, { role: "assistant", content: "", draft: true }]);
    abort.current = new AbortController();
    try {
      const fin = await streamChat({ message: text, mode, hint_level: level }, (d) => setMsgs((m) => { const c = [...m]; const l = c[c.length - 1]; c[c.length - 1] = { ...l, content: l.content + d }; return c; }), abort.current.signal);
      setMsgs((m) => { const c = [...m]; c[c.length - 1] = { id: fin.id, role: "assistant", content: fin.answer, meta: fin }; return c; });
      window.dispatchEvent(new Event("nexora:refresh"));
    } catch (e) { setErr((e as Error).message); setMsgs((m) => m.filter((x) => !x.draft)); } finally { setBusy(false); }
  }
  async function rate(m: Msg, v: number) { if (!m.id) return; await api(`/mentor/${m.id}/feedback`, { method: "POST", body: JSON.stringify({ value: v }) }); setMsgs((x) => x.map((y) => y.id === m.id ? { ...y, feedback: v } : y)); }
  async function addNote(e: React.FormEvent) { e.preventDefault(); await api("/notes", { method: "POST", body: JSON.stringify(nt) }); setNt({ title: "", text: "" }); load(); }
  async function toggleOpt() { const r = await api<{ training_opt_in: boolean }>("/me/prefs", { method: "PUT", body: JSON.stringify({ training_opt_in: !opt }) }); setOpt(r.training_opt_in); }
  return (
    <div className="grid" style={{ gap: 16 }}>
      <div className="row" style={{ justifyContent: "space-between" }}><div><h1>AI <span className="grad-text">mentor</span></h1><p className="muted">Grounded in Nexora's notes and your own data. It teaches in steps; you control how much help you get.</p></div>
        {st && <span className={`st ${st.offline ? "learning" : "mastered"}`} title={Object.entries(st.providers).map(([k, v]) => `${k}: ${v.model} ${v.ready ? "ready" : "not configured"}`).join("\n")}>{st.offline ? "offline mode" : `live · ${st.configured[0]}`}</span>}</div>
      {st?.offline && <div className="card" style={{ borderColor: "rgba(251,191,36,.5)" }}><p><b>No LLM provider is available.</b> {st.message} Add a key (Gemini / Groq / OpenRouter) or run a local Ollama model, and the mentor goes live without code changes.</p></div>}
      <div className="grid" style={{ gridTemplateColumns: "minmax(0,1fr)", gap: 16 }}>
        <div className="card row" style={{ gap: 8 }}>
          <div className="seg" role="tablist" aria-label="Mentor mode">{MODES.map(([k, l]) => <button key={k} role="tab" aria-selected={mode === k} className={`btn ${mode === k ? "primary" : ""}`} onClick={() => setMode(k)}>{l}</button>)}</div>
          {mode === "hint" && <div style={{ flex: "1 1 260px" }}><label htmlFor="lv">Hint level {level}: {LEVELS[level - 1]}</label><input id="lv" type="range" min={1} max={5} value={level} onChange={(e) => setLevel(+e.target.value)} /></div>}
        </div>
        <div className="card" style={{ minHeight: 360, maxHeight: "58vh", overflowY: "auto", display: "grid", gap: 12, alignContent: "start" }} aria-live="polite">
          {msgs.length === 0 && <p className="muted">Ask about a concept, paste a problem you&apos;re stuck on, or switch to <b>Hint ladder</b> to get nudges instead of answers.</p>}
          {msgs.map((m, i) => <div key={i} className={`bubble ${m.role === "user" ? "me" : "ai"}`}>{m.content || <span className="muted">thinking…</span>}
            {m.draft && m.content && <p className="muted" style={{ fontSize: 11, marginTop: 6 }}>draft: still being checked</p>}
            {m.role === "assistant" && m.meta && !m.draft && <div style={{ marginTop: 10, borderTop: "1px solid var(--card-b)", paddingTop: 8 }}>
              <div className="row" style={{ gap: 6 }}>{m.meta.sources?.map((s) => <span key={s.id} className="chip" title={s.kind}>[{s.id}] {s.title}</span>)}</div>
              <div className="row" style={{ gap: 8, marginTop: 6, fontSize: 11 }}><span className="muted">{m.meta.offline ? "offline notes" : `${m.meta.provider}/${m.meta.model}`}</span>{(m.meta.validation ?? []).map((v) => <span key={v} className="st learning">{v.replace(/_/g, " ")}</span>)}
                <button className="btn" style={{ padding: "2px 8px" }} aria-label="Helpful" onClick={() => rate(m, 1)}>{m.feedback === 1 ? "👍✓" : "👍"}</button><button className="btn" style={{ padding: "2px 8px" }} aria-label="Not helpful" onClick={() => rate(m, -1)}>{m.feedback === -1 ? "👎✓" : "👎"}</button></div></div>}</div>)}
          <div ref={end} /></div>
        {err && <p className="err" role="alert">{err}</p>}
        <div className="row" style={{ alignItems: "flex-end" }}><div style={{ flex: 1 }}><label htmlFor="q">Your question</label><textarea id="q" rows={3} value={input} maxLength={4000} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) send(); }} placeholder="e.g. I need to minimise the maximum load across k machines — where do I start?  (Ctrl+Enter to send)" /></div>
          <button className="btn primary" disabled={busy || !input.trim()} onClick={send}>{busy ? "Thinking…" : "Ask"}</button>{busy && <button className="btn" onClick={() => abort.current?.abort()}>Stop</button>}</div>
      </div>
      <div className="grid g2">
        <div className="card"><h2>My notes (private)</h2><p className="muted" style={{ fontSize: 12 }}>Notes you add are searchable by the mentor for you only.</p>
          <form onSubmit={addNote} className="grid" style={{ gap: 8, margin: "10px 0" }}><input placeholder="Title" required maxLength={200} value={nt.title} onChange={(e) => setNt({ ...nt, title: e.target.value })} /><textarea rows={3} required maxLength={8000} placeholder="What did you learn?" value={nt.text} onChange={(e) => setNt({ ...nt, text: e.target.value })} /><button className="btn">Save note</button></form>
          {notes.map((n) => <div key={n.id} className="row" style={{ justifyContent: "space-between", fontSize: 13 }}><span>{n.title}</span><button className="muted" style={{ background: "none", border: 0, cursor: "pointer" }} onClick={async () => { await api(`/notes/${n.id}`, { method: "DELETE" }); load(); }}>delete</button></div>)}</div>
        <div className="card"><h2>Privacy</h2><p className="muted" style={{ fontSize: 13, margin: "8px 0" }}>Your chats are stored for your history. They are used to improve/fine-tune Nexora&apos;s models <b>only if you opt in</b>, and training examples never store your user id.</p>
          <label style={{ display: "flex", gap: 8, alignItems: "center", margin: 0 }}><input type="checkbox" style={{ width: "auto" }} checked={opt} onChange={toggleOpt} /> Allow my mentor chats to be used for model training</label>
          {st && <p className="mono muted" style={{ fontSize: 11, marginTop: 12 }}>Tokens used (24h): {st.tokens_used_24h.toLocaleString()}</p>}</div></div>
    </div>
  );
}
