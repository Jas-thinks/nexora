"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { API, api, tokens } from "@/lib/api";

type M = { id: number; channel_id: number; parent_id: number | null; kind: string; language: string | null; author: string; author_id: number | null; content: string; deleted: boolean; created_at: string; reactions: Record<string, { count: number; mine: boolean }>; replies: number };
type Ch = { id: number; slug: string; name: string; topic: string };
const EMOJI = ["👍", "🔥", "💡", "🎯", "❤️", "😂", "🤔"];

export default function Community() {
  const [chs, setChs] = useState<Ch[]>([]), [cid, setCid] = useState<number | null>(null), [msgs, setMsgs] = useState<M[]>([]), [more, setMore] = useState<number | null>(null), [err, setErr] = useState(""), [text, setText] = useState(""), [kind, setKind] = useState("text"), [lang, setLang] = useState("cpp");
  const [thread, setThread] = useState<{ root: M; replies: M[] } | null>(null), [reply, setReply] = useState(""), [live, setLive] = useState(false), [q, setQ] = useState(""), [found, setFound] = useState<M[] | null>(null), [role, setRole] = useState("student"), [reports, setReports] = useState<{ id: number; reason: string; message: M | null }[]>([]);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { api<Ch[]>("/channels").then((c) => { setChs(c); setCid(c[0]?.id ?? null); }).catch((e) => setErr(e.message)); api<{ role: string }>("/auth/me").then((u) => setRole(u.role)); }, []);
  const load = useCallback((id: number) => api<{ items: M[]; next_before: number | null }>(`/channels/${id}/messages?limit=30`).then((r) => { setMsgs(r.items); setMore(r.next_before); }).catch((e) => setErr(e.message)), []);
  useEffect(() => { if (cid == null) return; setThread(null); setFound(null); load(cid);
    const ws = new WebSocket(`${API.replace(/^http/, "ws")}/ws/channels/${cid}?token=${tokens.get()?.access_token ?? ""}`);
    ws.onopen = () => setLive(true); ws.onclose = () => setLive(false);
    ws.onmessage = (e) => { const ev = JSON.parse(e.data);
      if (ev.type === "message") setMsgs((m) => ev.message.parent_id ? m.map((x) => x.id === ev.message.parent_id ? { ...x, replies: x.replies + 1 } : x) : m.some((x) => x.id === ev.message.id) ? m : [...m, ev.message]);
      else if (ev.type === "reaction") setMsgs((m) => m.map((x) => x.id === ev.message_id ? { ...x, reactions: Object.fromEntries(Object.entries(ev.reactions as M["reactions"]).map(([k, v]) => [k, { count: v.count, mine: x.reactions[k]?.mine ?? false }])) } : x));
      else if (ev.type === "deleted") setMsgs((m) => m.map((x) => x.id === ev.message_id ? { ...x, deleted: true, content: "[message removed by a moderator]" } : x)); };
    return () => ws.close(); }, [cid, load]);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs.length]);
  async function post(parent?: number) { const content = (parent ? reply : text).trim(); if (!content || cid == null) return; setErr("");
    try { const m = await api<M>(`/channels/${cid}/messages`, { method: "POST", body: JSON.stringify({ content, kind: parent ? "text" : kind, language: kind === "code" && !parent ? lang : null, parent_id: parent ?? null }) });
      if (parent) { setReply(""); setThread(await api(`/messages/${parent}/thread`)); } else { setText(""); setMsgs((x) => x.some((y) => y.id === m.id) ? x : [...x, m]); } } catch (e) { setErr((e as Error).message); } }
  async function react(m: M, emoji: string) { const r = await api<M["reactions"]>(`/messages/${m.id}/react`, { method: "POST", body: JSON.stringify({ emoji }) }); setMsgs((x) => x.map((y) => y.id === m.id ? { ...y, reactions: r } : y)); }
  async function report(m: M) { const reason = prompt("Why are you reporting this message?"); if (reason && reason.length >= 3) { try { await api(`/messages/${m.id}/report`, { method: "POST", body: JSON.stringify({ reason }) }); alert("Reported. A moderator will review it."); } catch (e) { alert((e as Error).message); } } }
  const modLoad = () => api<typeof reports>("/mod/reports").then(setReports).catch(() => {});
  const Msg = ({ m, inThread }: { m: M; inThread?: boolean }) => (
    <div className="card" style={{ padding: 12, opacity: m.deleted ? 0.5 : 1 }}><div className="row" style={{ justifyContent: "space-between" }}><span><b>{m.author}</b> <span className="muted mono" style={{ fontSize: 11 }}>{new Date(m.created_at).toLocaleString()}</span></span>
      {!m.deleted && <span className="row" style={{ gap: 4 }}><button className="muted" style={{ background: "none", border: 0, cursor: "pointer" }} title="Bookmark" onClick={() => api(`/messages/${m.id}/bookmark`, { method: "POST" })}>☆</button><button className="muted" style={{ background: "none", border: 0, cursor: "pointer" }} title="Report" onClick={() => report(m)}>⚑</button></span>}</div>
      {m.kind === "code" && !m.deleted ? <pre className="mono" style={{ background: "rgba(255,255,255,.05)", padding: 10, borderRadius: 10, overflowX: "auto", margin: "8px 0", fontSize: 13 }}>{m.content}</pre> : <p style={{ margin: "6px 0", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{m.content}</p>}
      {!m.deleted && !inThread && <div className="row" style={{ gap: 6 }}>{EMOJI.map((e) => <button key={e} className="chip" onClick={() => react(m, e)} style={{ cursor: "pointer", borderColor: m.reactions[e]?.mine ? "var(--violet)" : undefined, opacity: m.reactions[e] ? 1 : 0.5 }}>{e}{m.reactions[e] ? ` ${m.reactions[e].count}` : ""}</button>)}
        <button className="btn" style={{ padding: "2px 10px", marginLeft: "auto" }} onClick={async () => setThread(await api(`/messages/${m.id}/thread`))}>{m.replies ? `${m.replies} replies` : "Reply"}</button></div>}</div>);
  return (
    <div className="grid" style={{ gap: 14 }}>
      <div className="row" style={{ justifyContent: "space-between" }}><div><h1>Community</h1><p className="muted">Discuss problems, share code, learn together. Be kind; moderators review reports.</p></div><span className={`st ${live ? "mastered" : "unexplored"}`}>{live ? "● live" : "connecting…"}</span></div>
      {err && <p className="err" role="alert">{err}</p>}
      <div className="grid" style={{ gridTemplateColumns: "minmax(170px,230px) minmax(0,1fr)", gap: 14, alignItems: "start" }}>
        <div className="card" style={{ padding: 10 }}>{chs.map((c) => <button key={c.id} onClick={() => setCid(c.id)} className="nav" style={{ width: "100%", background: cid === c.id ? "rgba(139,92,246,.18)" : "none", border: 0, cursor: "pointer", textAlign: "left", color: "inherit" }} title={c.topic}># {c.slug}</button>)}
          {(role === "moderator" || role === "admin") && <button className="btn" style={{ width: "100%", marginTop: 8 }} onClick={modLoad}>Mod queue</button>}</div>
        <div className="grid" style={{ gap: 10 }}>
          <div className="row"><input style={{ flex: 1 }} placeholder="Search messages…" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={async (e) => { if (e.key === "Enter") { setFound(q.length >= 2 ? await api<M[]>(`/search/messages?q=${encodeURIComponent(q)}${cid ? `&channel_id=${cid}` : ""}`) : null); } }} />{found && <button className="btn" onClick={() => { setFound(null); setQ(""); }}>Clear</button>}</div>
          {reports.length > 0 && <div className="card" style={{ borderColor: "rgba(251,113,133,.5)" }}><h2>Reports</h2>{reports.map((r) => <div key={r.id} style={{ marginTop: 8 }}><p style={{ fontSize: 13 }}>“{r.message?.content}” — <span className="muted">{r.reason}</span></p><div className="row" style={{ gap: 6 }}>{["delete", "mute", "dismiss"].map((a) => <button key={a} className="btn" onClick={async () => { await api(`/mod/reports/${r.id}`, { method: "POST", body: JSON.stringify({ action: a }) }); modLoad(); }}>{a}</button>)}</div></div>)}</div>}
          {found ? <>{found.length ? found.map((m) => <Msg key={m.id} m={m} />) : <p className="muted">No matches.</p>}</> : <>
            {more && <button className="btn" onClick={async () => { const r = await api<{ items: M[]; next_before: number | null }>(`/channels/${cid}/messages?limit=30&before=${more}`); setMsgs((m) => [...r.items, ...m]); setMore(r.next_before); }}>Load older</button>}
            <div style={{ display: "grid", gap: 8, maxHeight: "52vh", overflowY: "auto" }}>{msgs.length === 0 && <p className="muted">No messages yet. Start the conversation.</p>}{msgs.map((m) => <Msg key={m.id} m={m} />)}<div ref={end} /></div></>}
          {thread && <div className="card" style={{ borderColor: "rgba(34,211,238,.4)" }}><div className="row" style={{ justifyContent: "space-between" }}><h2>Thread</h2><button className="btn" onClick={() => setThread(null)}>Close</button></div><Msg m={thread.root} inThread />{thread.replies.map((r) => <div key={r.id} style={{ marginLeft: 18, marginTop: 8 }}><Msg m={r} inThread /></div>)}
            <div className="row" style={{ marginTop: 10 }}><input style={{ flex: 1 }} value={reply} maxLength={4000} placeholder="Reply…" onChange={(e) => setReply(e.target.value)} onKeyDown={(e) => e.key === "Enter" && post(thread.root.id)} /><button className="btn primary" onClick={() => post(thread.root.id)}>Reply</button></div></div>}
          <div className="card"><div className="row" style={{ marginBottom: 8 }}><div className="seg"><button className={`btn ${kind === "text" ? "primary" : ""}`} onClick={() => setKind("text")}>Text</button><button className={`btn ${kind === "code" ? "primary" : ""}`} onClick={() => setKind("code")}>Code</button></div>{kind === "code" && <select aria-label="Language" value={lang} onChange={(e) => setLang(e.target.value)} style={{ width: 110 }}><option>cpp</option><option>python</option><option>java</option></select>}</div>
            <textarea className={kind === "code" ? "mono" : ""} rows={kind === "code" ? 5 : 2} maxLength={4000} value={text} onChange={(e) => setText(e.target.value)} placeholder={kind === "code" ? "Paste a snippet…" : "Message #" + (chs.find((c) => c.id === cid)?.slug ?? "")} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && kind === "text") { e.preventDefault(); post(); } }} />
            <div className="row" style={{ justifyContent: "space-between", marginTop: 8 }}><span className="muted" style={{ fontSize: 11 }}>{text.length}/4000 · rate-limited to prevent spam</span><button className="btn primary" disabled={!text.trim()} onClick={() => post()}>Send</button></div></div>
        </div></div>
    </div>
  );
}
