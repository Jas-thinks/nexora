"use client";
import "@xyflow/react/dist/style.css";
import { addEdge, Background, Controls, Handle, MiniMap, Position, ReactFlow, useEdgesState, useNodesState, type Connection, type Edge, type Node, type NodeProps, type NodeTypes } from "@xyflow/react";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { streamChat } from "@/lib/stream";
import Md from "@/components/Md";

type Data = { type: string; label: string; replicas: number; consistency?: string; kind?: string; flag?: string; [k: string]: unknown };
const ICON: Record<string, string> = { client: "🖥", cdn: "🌐", api_gateway: "🚪", load_balancer: "⚖️", app_server: "⚙️", auth_service: "🔐", rate_limiter: "⏱", cache: "⚡", database: "🗄", message_broker: "📨", worker: "🛠", object_storage: "🪣", search_engine: "🔎", monitoring: "📈", sandbox: "📦" };
const SEV: Record<string, string> = { high: "weak", medium: "learning", low: "unexplored" };
type Finding = { rule: string; severity: string; nodes: string[]; message: string; suggestion: string };
type DocItem = { key: string; label: string; hint: string; words: number; done: boolean; has_numbers: boolean | null };
type Review = { findings: Finding[]; coverage: { present: string[]; missing: string[]; ratio: number; note: string } | null; counts?: Record<string, number>; questions: string[]; doc: { items: DocItem[]; ratio: number; note: string }; inferred: { why: Record<string, string[]> } | null };
type Sec = { key: string; label: string; hint: string };
type Q = { slug: string; title: string; prompt: string; level: string; category: string; kind: string; concepts: string[]; status: string | null };
const PLACEHOLDER: Record<string, string> = { requirements: "Functional: ...\nNon-functional: scale, latency, availability, consistency\nOut of scope: ...", estimation: "DAU x actions / 86,400 = QPS (peak 3x)\nStorage = items x bytes x retention\nBandwidth = QPS x payload", api: "POST /v1/...  -> 201 {id}\nGET /v1/.../{id}", data_model: "Tables/collections, primary keys, indexes; SQL or NoSQL and why", deep_dives: "The 2-3 hardest parts: e.g. ID generation, fan-out, cache invalidation, ordering", tradeoffs: "What breaks first at 10x? Failure modes? What did you give up?" };

function Box({ data, selected }: NodeProps<Node<Data>>) {
  const bad = data.flag; const stateful = ["database", "cache", "message_broker"].includes(data.type);
  return <div style={{ padding: "8px 12px", borderRadius: 14, minWidth: 124, background: stateful ? "rgba(34,211,238,.12)" : "rgba(139,92,246,.16)", border: `1.5px solid ${bad === "high" ? "#fb7185" : bad === "medium" ? "#fbbf24" : selected ? "#22d3ee" : "rgba(255,255,255,.2)"}`, boxShadow: bad ? `0 0 18px -4px ${bad === "high" ? "#fb7185" : "#fbbf24"}` : selected ? "0 0 18px -6px #22d3ee" : "none", color: "#ece9f8", textAlign: "center", fontSize: 12 }}>
    <Handle type="target" position={Position.Left} /><div style={{ fontSize: 20 }}>{ICON[data.type] ?? "▫"}</div><b>{data.label}</b><div className="mono" style={{ opacity: 0.7, fontSize: 10 }}>{data.type.replace("_", " ")} ×{data.replicas}</div><Handle type="source" position={Position.Right} /></div>;
}
const nodeTypes = { box: Box } as unknown as NodeTypes;
const uid = () => Math.random().toString(36).slice(2, 8);

function Inner() {
  const sp = useSearchParams();
  const [nodes, setNodes, onNodes] = useNodesState<Node<Data>>([]), [edges, setEdges, onEdges] = useEdgesState<Edge>([]);
  const [types, setTypes] = useState<string[]>([]), [secs, setSecs] = useState<Sec[]>([]), [title, setTitle] = useState(""), [prompt, setPrompt] = useState(""), [doc, setDoc] = useState<Record<string, string>>({}), [question, setQuestion] = useState<string | null>(null);
  const [tab, setTab] = useState<"plan" | "diagram" | "review">("plan"), [rv, setRv] = useState<Review | null>(null), [sel, setSel] = useState<string | null>(null);
  const [saved, setSaved] = useState<{ id: number; title: string; reviewed: boolean }[]>([]), [did, setDid] = useState<number | null>(null), [msg, setMsg] = useState(""), [err, setErr] = useState("");
  const [chat, setChat] = useState<{ role: string; text: string }[]>([]), [q, setQ] = useState(""), [busy, setBusy] = useState(false), [ai, setAi] = useState<{ text: string; draft: boolean } | null>(null);
  const [lib, setLib] = useState<Q[] | null>(null), [libQ, setLibQ] = useState(""), [libLevel, setLibLevel] = useState(""), [showLib, setShowLib] = useState(false);
  const loadLib = useCallback(() => lib ? Promise.resolve(lib) : api<{ items: Q[] }>("/resources/system-design").then((d) => { setLib(d.items); return d.items; }), [lib]);
  useEffect(() => { api<{ node_types: string[]; doc_sections: Sec[] }>("/design/scenarios").then((d) => { setTypes(d.node_types); setSecs(d.doc_sections); }).catch((e) => setErr(e.message)); api<typeof saved>("/design").then(setSaved).catch(() => {}); }, []);
  const qslug = sp.get("question");
  useEffect(() => { if (!qslug) return; loadLib().then((items) => { const x = items.find((i) => i.slug === qslug); if (x) pick(x); }).catch(() => {}); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [qslug]);
  function pick(x: Q) { setQuestion(x.slug); setPrompt(x.prompt); setTitle(x.title); setShowLib(false); setDid(null); setRv(null); setAi(null); setChat([]); setNodes([]); setEdges([]); setDoc({}); setTab("plan"); }
  const graph = useMemo(() => ({ nodes: nodes.map((n) => ({ id: n.id, type: n.data.type, label: n.data.label, replicas: n.data.replicas, consistency: n.data.consistency ?? null, kind: n.data.kind ?? null, x: n.position.x, y: n.position.y })), edges: edges.map((e) => ({ from: e.source, to: e.target, label: "" })) }), [nodes, edges]);
  const add = (type: string) => setNodes((ns) => [...ns, { id: `${type}-${uid()}`, type: "box", position: { x: 40 + (ns.length % 4) * 210, y: 50 + Math.floor(ns.length / 4) * 150 }, data: { type, label: type.replace("_", " "), replicas: 1 } }]);
  const connect = useCallback((c: Connection) => setEdges((es) => addEdge({ ...c, animated: true, style: { stroke: "#8b5cf6" } }, es)), [setEdges]);
  const flag = (r: Review | null) => setNodes((ns) => ns.map((n) => { const f = r?.findings.filter((x) => x.nodes.includes(n.id)).sort((a, b) => (a.severity === "high" ? 0 : 1) - (b.severity === "high" ? 0 : 1))[0]; return { ...n, data: { ...n.data, flag: f?.severity } }; }));
  const body = () => JSON.stringify({ title: title || prompt.slice(0, 60) || "Untitled design", prompt, doc, question, graph });
  async function review() { setErr(""); try { const r = await api<Review>("/design/review", { method: "POST", body: body() }); setRv(r); flag(r); } catch (e) { setErr((e as Error).message); } }
  async function save(): Promise<number | null> { try { let id = did; if (id) await api(`/design/${id}`, { method: "PUT", body: body() }); else { const r = await api<{ id: number }>("/design", { method: "POST", body: body() }); id = r.id; setDid(id); } setMsg("Saved."); setTimeout(() => setMsg(""), 1500); api<typeof saved>("/design").then(setSaved); return id; } catch (e) { setErr((e as Error).message); return null; } }
  async function open(id: number) { const d = await api<{ title: string; prompt: string; doc: Record<string, string>; question: string | null; graph: { nodes: (Data & { id: string; x: number; y: number })[]; edges: { from: string; to: string }[] } }>(`/design/${id}`); setDid(id); setTitle(d.title); setPrompt(d.prompt); setDoc(d.doc); setQuestion(d.question); setRv(null); setAi(null); setTab("plan");
    setNodes(d.graph.nodes.map((n) => ({ id: n.id, type: "box", position: { x: n.x, y: n.y }, data: { type: n.type, label: n.label, replicas: n.replicas, consistency: n.consistency ?? undefined, kind: n.kind ?? undefined } }))); setEdges(d.graph.edges.map((e, i) => ({ id: `e${i}`, source: e.from, target: e.to, animated: true, style: { stroke: "#8b5cf6" } }))); }
  async function aiReview() { if (!prompt.trim()) { setErr("Write or pick a design question first."); return; } setErr(""); setBusy(true); setAi({ text: "", draft: true }); review();
    try { const f = await streamChat({ message: "Review my design and teach me what to improve.", mode: "design_review", design: { prompt, doc, graph } }, (d) => setAi((a) => ({ text: (a?.text ?? "") + d, draft: true })));
      setAi({ text: f.answer, draft: false }); const id = await save(); if (id) { await api(`/design/${id}/reviewed`, { method: "POST" }).catch(() => {}); api<typeof saved>("/design").then(setSaved); }
    } catch (e) { setAi(null); setErr((e as Error).message); } finally { setBusy(false); } }
  async function interview(text: string) { setBusy(true); setChat((c) => [...c, { role: "user", text }, { role: "ai", text: "" }]);
    try { const f = await streamChat({ message: text, mode: "design", design: { prompt, doc, graph } }, (d) => setChat((c) => { const x = [...c]; x[x.length - 1] = { role: "ai", text: x[x.length - 1].text + d }; return x; })); setChat((c) => { const x = [...c]; x[x.length - 1] = { role: "ai", text: f.answer }; return x; }); } catch (e) { setChat((c) => [...c.slice(0, -1), { role: "ai", text: `⚠ ${(e as Error).message}` }]); } finally { setBusy(false); } }
  const cur = nodes.find((n) => n.id === sel); const upd = (p: Partial<Data>) => setNodes((ns) => ns.map((n) => n.id === sel ? { ...n, data: { ...n.data, ...p } } : n));
  const filled = secs.filter((x) => (doc[x.key] ?? "").trim().split(/\s+/).filter(Boolean).length >= 12).length;
  const libItems = (lib ?? []).filter((x) => x.kind === "hld" && (!libLevel || x.level === libLevel) && (!libQ || (x.title + x.concepts.join(" ")).toLowerCase().includes(libQ.toLowerCase())));
  return (
    <div className="grid" style={{ gap: 14 }}>
      <div><h1>System design <span className="grad-text">lab</span></h1><p className="muted">Design <b>any</b> system. Write your own question or pick one, plan it, draw it, then get a review that teaches you what you missed.</p></div>
      {err && <p className="err" role="alert">{err}</p>}
      <div className="card" style={{ display: "grid", gap: 10 }}>
        <label htmlFor="q">What do you want to design?</label>
        <textarea id="q" rows={2} maxLength={2000} value={prompt} onChange={(e) => { setPrompt(e.target.value); setQuestion(null); }} placeholder="e.g. Design Instagram: upload photos, follow users, see a feed. 50M daily users." />
        <div className="row" style={{ justifyContent: "space-between" }}>
          <div className="row"><button className="btn" onClick={() => { setShowLib(!showLib); loadLib(); }}>📚 Pick from {lib ? lib.filter((x) => x.kind === "hld").length : "70"}+ questions</button>{question && <span className="chip">from library: {question}</span>}</div>
          <div className="row">{saved.slice(0, 4).map((x) => <button key={x.id} className="chip" onClick={() => open(x.id)} style={{ cursor: "pointer" }}>{x.reviewed ? "✓ " : ""}{x.title}</button>)}</div></div>
        {showLib && <div style={{ borderTop: "1px solid var(--card-b)", paddingTop: 10 }}><div className="row"><input aria-label="Search questions" placeholder="Search (cache, feed, payments…)" value={libQ} onChange={(e) => setLibQ(e.target.value)} style={{ maxWidth: 280 }} />
          {["", "entry", "mid", "senior"].map((l) => <button key={l} className={`btn ${libLevel === l ? "primary" : ""}`} onClick={() => setLibLevel(l)}>{l || "all levels"}</button>)}</div>
          <div style={{ display: "grid", gap: 6, maxHeight: 260, overflowY: "auto", marginTop: 10 }}>{libItems.map((x) => <button key={x.slug} onClick={() => pick(x)} className="card" style={{ textAlign: "left", padding: "8px 12px", cursor: "pointer" }}><b>{x.title}</b> <span className="chip">{x.level}</span> <span className="chip">{x.category}</span> {x.status && <span className="st mastered">{x.status}</span>}<p className="muted" style={{ fontSize: 12 }}>{x.concepts.join(" · ")}</p></button>)}</div></div>}
      </div>
      <div className="seg" role="tablist">{([["plan", `① Plan the HLD (${filled}/${secs.length})`], ["diagram", `② Draw it (${nodes.length})`], ["review", "③ Review & learn"]] as const).map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} className={`btn ${tab === k ? "primary" : ""}`} onClick={() => setTab(k)}>{l}</button>)}</div>
      {tab === "plan" && <div className="grid g2">{secs.map((x) => { const w = (doc[x.key] ?? "").trim().split(/\s+/).filter(Boolean).length; return <div key={x.key} className="card"><label htmlFor={`s-${x.key}`}><b>{x.label}</b> <span className="muted" style={{ fontWeight: 400 }}>· {x.hint}</span></label>
        <textarea id={`s-${x.key}`} rows={6} maxLength={6000} value={doc[x.key] ?? ""} onChange={(e) => setDoc({ ...doc, [x.key]: e.target.value })} placeholder={PLACEHOLDER[x.key]} style={{ marginTop: 6 }} /><span className="muted" style={{ fontSize: 11 }}>{w} words {w >= 12 ? "✓" : ""}</span></div>; })}</div>}
      {tab === "diagram" && <>
        <div className="row" style={{ gap: 6 }}>{types.map((t) => <button key={t} className="btn" onClick={() => add(t)} title={`Add ${t}`}>{ICON[t]} {t.replace("_", " ")}</button>)}</div>
        <div className="grid g2" style={{ alignItems: "start", gridTemplateColumns: "minmax(0,2fr) minmax(260px,1fr)" }}>
          <div style={{ height: 520, borderRadius: 16, overflow: "hidden", border: "1px solid var(--card-b)", background: "#0b0912" }}>
            <ReactFlow nodes={nodes} edges={edges} onNodesChange={onNodes} onEdgesChange={onEdges} onConnect={connect} nodeTypes={nodeTypes} onNodeClick={(_, n) => setSel(n.id)} onPaneClick={() => setSel(null)} defaultViewport={{ x: 20, y: 20, zoom: 0.7 }} minZoom={0.25} maxZoom={1.6} deleteKeyCode={["Backspace", "Delete"]}>
              <Background color="#2a2540" gap={22} /><Controls /><MiniMap pannable zoomable style={{ background: "#0d0b17", border: "1px solid rgba(255,255,255,.12)" }} maskColor="rgba(7,6,13,.75)" nodeColor="#8b5cf6" nodeStrokeWidth={0} /></ReactFlow></div>
          <div className="grid" style={{ gap: 12 }}>
            <div className="card"><p className="muted" style={{ fontSize: 13 }}>Add components, drag to arrange, connect the dots from right handle to left handle. Click a box to set replicas/consistency.</p>
              <div className="row" style={{ marginTop: 8 }}><button className="btn" onClick={() => { setNodes([]); setEdges([]); setRv(null); }}>Clear diagram</button></div></div>
            {cur && <div className="card"><h2>Selected: {cur.data.label}</h2><div className="grid" style={{ gap: 8, marginTop: 8 }}><div><label htmlFor="nl">Label</label><input id="nl" maxLength={60} value={cur.data.label} onChange={(e) => upd({ label: e.target.value })} /></div>
              <div><label htmlFor="nr">Replicas</label><input id="nr" type="number" min={1} max={1000} value={cur.data.replicas} onChange={(e) => upd({ replicas: Math.max(1, +e.target.value || 1) })} /></div>
              {cur.data.type === "database" && <div className="row"><select aria-label="Kind" value={cur.data.kind ?? ""} onChange={(e) => upd({ kind: e.target.value || undefined })}><option value="">kind: unspecified</option><option>relational</option><option>nosql</option></select><select aria-label="Consistency" value={cur.data.consistency ?? ""} onChange={(e) => upd({ consistency: e.target.value || undefined })}><option value="">consistency: unspecified</option><option>strong</option><option>eventual</option></select></div>}</div></div>}
          </div></div></>}
      {tab === "review" && <div className="grid" style={{ gap: 14 }}>
        <div className="card row" style={{ justifyContent: "space-between" }}><div><h2>Ready?</h2><p className="muted" style={{ fontSize: 13 }}>The AI reviewer reads your question, HLD notes and diagram, tells you what is good and missing, <b>teaches</b> the top gaps and asks interview follow-ups.</p></div>
          <div className="row"><button className="btn" onClick={review} disabled={!nodes.length && !prompt}>Quick rule check</button><button className="btn primary" onClick={aiReview} disabled={busy || !prompt.trim()}>{busy ? "Reviewing…" : "✨ AI review & teach me"}</button><button className="btn" onClick={save}>Save</button></div></div>
        {msg && <p role="status" style={{ color: "var(--lime)" }}>{msg}</p>}
        {ai && <div className="card" aria-live="polite"><h2>AI review {ai.draft && <span className="muted" style={{ fontSize: 12 }}>· draft, still being checked…</span>}</h2><div style={{ marginTop: 8 }}><Md text={ai.text || "Thinking…"} /></div>
          {!ai.draft && <p className="muted" style={{ fontSize: 11, marginTop: 10 }}>AI-generated and can be wrong. Treat the scores as an estimate. Use the discussion below to push back.</p>}</div>}
        {rv && <div className="grid g2">
          <div className="card"><h2>Rule findings {rv.counts && <span className="muted" style={{ fontSize: 13 }}>· {rv.counts.high} high · {rv.counts.medium} medium · {rv.counts.low} low</span>}</h2>
            {rv.findings.length === 0 ? <p className="muted" style={{ marginTop: 8 }}>No rule violations. That doesn&apos;t mean it&apos;s perfect: ask the AI reviewer.</p> : rv.findings.map((f, i) => <div key={i} style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid var(--card-b)" }}><span className={`st ${SEV[f.severity]}`}>{f.severity}</span> <b className="mono" style={{ fontSize: 12 }}>{f.rule}</b><p style={{ fontSize: 13, marginTop: 4 }}>{f.message}</p><p className="muted" style={{ fontSize: 12 }}>→ {f.suggestion}</p></div>)}</div>
          <div className="card"><h2>Checklists</h2><p className="muted" style={{ fontSize: 12, margin: "6px 0" }}>HLD sections written</p><div className="bar"><i style={{ width: `${rv.doc.ratio * 100}%` }} /></div><div className="row" style={{ gap: 6, marginTop: 6 }}>{rv.doc.items.map((i) => <span key={i.key} className={`st ${i.done ? "mastered" : "weak"}`}>{i.done ? "" : "missing: "}{i.label}</span>)}</div>
            {rv.coverage && <><p className="muted" style={{ fontSize: 12, margin: "12px 0 6px" }}>Components this kind of system usually needs</p><div className="bar"><i style={{ width: `${rv.coverage.ratio * 100}%` }} /></div><div className="row" style={{ gap: 6, marginTop: 6 }}>{rv.coverage.present.map((p) => <span key={p} className="st mastered">{p.replace("_", " ")}</span>)}{rv.coverage.missing.map((p) => <span key={p} className="st weak">missing: {p.replace("_", " ")}</span>)}</div><p className="muted" style={{ fontSize: 11, marginTop: 8 }}>{rv.coverage.note}</p></>}
            <h2 style={{ marginTop: 16 }}>Interviewer follow-ups</h2>{rv.questions.map((x) => <p key={x} className="row" style={{ gap: 8, fontSize: 13, marginTop: 8, justifyContent: "space-between" }}><span>{x}</span><button className="btn" style={{ padding: "2px 8px" }} disabled={busy} onClick={() => interview(`Interviewer asked: ${x}\nMy answer: `)}>Discuss</button></p>)}</div></div>}
        <div className="card"><h2>Discuss with the AI interviewer</h2><p className="muted" style={{ fontSize: 12 }}>Defend a decision, ask &quot;why not X?&quot;, or ask it to explain a concept. It sees your question, notes and diagram.</p>
          <div style={{ display: "grid", gap: 8, margin: "10px 0", maxHeight: 320, overflowY: "auto" }}>{chat.map((m, i) => <div key={i} className={`bubble ${m.role === "user" ? "me" : "ai"}`}>{m.role === "ai" ? <Md text={m.text || "…"} /> : m.text}</div>)}</div>
          <div className="row"><input style={{ flex: 1 }} value={q} maxLength={600} onChange={(e) => setQ(e.target.value)} placeholder="Explain a decision or ask a question" onKeyDown={(e) => { if (e.key === "Enter" && q.trim() && !busy) { interview(q); setQ(""); } }} /><button className="btn primary" disabled={busy || !q.trim()} onClick={() => { interview(q); setQ(""); }}>Send</button></div></div>
      </div>}
    </div>
  );
}
export default function Design() { return <Suspense><Inner /></Suspense>; }
