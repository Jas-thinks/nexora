"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";

type Tier = { id: string; label: string; companies: number; problem_links: number };
type Overview = { tiers: Tier[]; distinct_problems: number; you_solved: number; design_questions: number; empty: boolean; attribution: { source: string; url: string; disclaimer: string } };
type Co = { slug: string; name: string; tier: string; domain: string | null; problems: number; solved: number };
type Prob = { id: number; name: string; url: string; difficulty: string | null; topics: string[]; frequency?: number; companies?: number; avg_frequency?: number; recent?: boolean; solved: boolean };
type Detail = { slug: string; name: string; tier_label: string; domain: string | null; problems: number; recent_problems: number; difficulty: Record<string, { total: number; solved: number }>; topics: { topic: string; count: number }[]; suggested_design: { slug: string; title: string; level: string }[]; suggested_design_note: string | null };
type DQ = { slug: string; title: string; prompt: string; level: string; category: string; kind: string; concepts: string[]; status: string | null };
const DC: Record<string, string> = { Easy: "mastered", Medium: "learning", Hard: "weak" };
const LC: Record<string, string> = { entry: "mastered", mid: "learning", senior: "weak" };

function ProblemList({ items, mode }: { items: Prob[]; mode: "company" | "tier" }) {
  return <div>{items.map((p) => <div key={p.id} className="row" style={{ justifyContent: "space-between", padding: "9px 0", borderTop: "1px solid var(--card-b)", gap: 12 }}>
    <div style={{ flex: 1, minWidth: 0 }}><span aria-label={p.solved ? "solved" : "not solved"} style={{ color: p.solved ? "var(--lime)" : "var(--muted)" }}>{p.solved ? "✓" : "○"}</span> <a href={p.url} target="_blank" rel="noreferrer noopener"><b>{p.name.trim()}</b> ↗</a> {p.difficulty && <span className={`st ${DC[p.difficulty]}`}>{p.difficulty}</span>} {p.recent && <span className="chip" style={{ color: "var(--cyan)" }}>recent</span>}
      <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>{p.topics.slice(0, 4).join(" · ")}</div></div>
    <div style={{ width: 120, textAlign: "right", fontSize: 12 }} className="muted">{mode === "tier" ? `${p.companies} companies` : <><div className="bar" style={{ height: 6 }}><i style={{ width: `${p.frequency}%` }} /></div>{p.frequency}%</>}</div></div>)}</div>;
}

function CompanyPanel({ slug, onClose }: { slug: string; onClose: () => void }) {
  const [d, setD] = useState<Detail | null>(null), [items, setItems] = useState<Prob[]>([]), [total, setTotal] = useState(0), [f, setF] = useState({ difficulty: "", topic: "", recent: false, unsolved: false, sort: "frequency" }), [err, setErr] = useState("");
  const qs = (off: number) => `limit=40&offset=${off}&sort=${f.sort}${f.difficulty ? `&difficulty=${f.difficulty}` : ""}${f.topic ? `&topic=${encodeURIComponent(f.topic)}` : ""}${f.recent ? "&recent=true" : ""}${f.unsolved ? "&unsolved=true" : ""}`;
  useEffect(() => { api<Detail>(`/resources/companies/${slug}`).then(setD).catch((e) => setErr(e.message)); }, [slug]);
  useEffect(() => { api<{ items: Prob[]; total: number }>(`/resources/companies/${slug}/problems?${qs(0)}`).then((r) => { setItems(r.items); setTotal(r.total); }).catch((e) => setErr(e.message)); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [slug, f]);
  if (err) return <p className="err" role="alert">{err}</p>;
  if (!d) return <div className="skeleton" style={{ height: 200 }} />;
  return <div className="card" style={{ borderColor: "var(--violet)" }}>
    <div className="row" style={{ justifyContent: "space-between" }}><div><h2>{d.name} <span className="chip">{d.tier_label}</span></h2><p className="muted" style={{ fontSize: 12 }}>{d.problems} reported problems · {d.recent_problems} in the last 6 months</p></div><button className="btn" onClick={onClose}>Close ✕</button></div>
    <div className="grid g3" style={{ marginTop: 12 }}>{["Easy", "Medium", "Hard"].map((k) => { const x = d.difficulty[k]; return <div key={k}><span className={`st ${DC[k]}`}>{k}</span> <span className="mono" style={{ fontSize: 13 }}>{x.solved}/{x.total}</span><div className="bar" style={{ marginTop: 6 }}><i style={{ width: `${x.total ? (x.solved / x.total) * 100 : 0}%` }} /></div></div>; })}</div>
    <div className="row" style={{ gap: 6, marginTop: 12 }}>{d.topics.map((t) => <button key={t.topic} className="chip" onClick={() => setF({ ...f, topic: f.topic === t.topic ? "" : t.topic })} style={{ cursor: "pointer", borderColor: f.topic === t.topic ? "var(--violet)" : undefined, color: f.topic === t.topic ? "var(--violet)" : undefined }}>{t.topic} {t.count}</button>)}</div>
    <div className="row" style={{ marginTop: 12 }}>{["", "Easy", "Medium", "Hard"].map((k) => <button key={k} className={`btn ${f.difficulty === k ? "primary" : ""}`} onClick={() => setF({ ...f, difficulty: k })}>{k || "all"}</button>)}
      <label className="chip" style={{ cursor: "pointer" }}><input type="checkbox" checked={f.recent} onChange={(e) => setF({ ...f, recent: e.target.checked })} /> recent (6 mo)</label><label className="chip" style={{ cursor: "pointer" }}><input type="checkbox" checked={f.unsolved} onChange={(e) => setF({ ...f, unsolved: e.target.checked })} /> unsolved only</label>
      <select aria-label="Sort" value={f.sort} onChange={(e) => setF({ ...f, sort: e.target.value })} style={{ width: 150 }}><option value="frequency">most asked first</option><option value="difficulty">easy → hard</option><option value="name">A → Z</option></select></div>
    <div style={{ marginTop: 8 }}>{items.length === 0 ? <p className="muted" style={{ padding: 12 }}>No problems match these filters.</p> : <ProblemList items={items} mode="company" />}</div>
    {items.length < total && <button className="btn" style={{ marginTop: 10 }} onClick={() => api<{ items: Prob[] }>(`/resources/companies/${slug}/problems?${qs(items.length)}`).then((r) => setItems([...items, ...r.items]))}>Load more ({total - items.length} left)</button>}
    {d.suggested_design.length > 0 && <div style={{ marginTop: 16 }}><h2>Suggested system design practice</h2><div className="row" style={{ gap: 6, marginTop: 8 }}>{d.suggested_design.map((q) => <Link key={q.slug} className="chip" href={`/design?question=${q.slug}`}>🧩 {q.title}</Link>)}</div><p className="muted" style={{ fontSize: 11, marginTop: 6 }}>{d.suggested_design_note}</p></div>}
  </div>;
}

function DsaTab({ ov }: { ov: Overview }) {
  const [tier, setTier] = useState(""), [q, setQ] = useState(""), [cos, setCos] = useState<Co[]>([]), [total, setTotal] = useState(0), [open, setOpen] = useState<string | null>(null), [must, setMust] = useState<Prob[]>([]), [md, setMd] = useState(""), [mu, setMu] = useState(false);
  const fetchCos = useCallback((off: number) => api<{ items: Co[]; total: number }>(`/resources/companies?limit=60&offset=${off}${tier ? `&tier=${tier}` : ""}${q ? `&q=${encodeURIComponent(q)}` : ""}`), [tier, q]);
  useEffect(() => { const t = setTimeout(() => fetchCos(0).then((r) => { setCos(r.items); setTotal(r.total); }).catch(() => {}), 200); return () => clearTimeout(t); }, [fetchCos]);
  useEffect(() => { if (!tier) { setMust([]); return; } api<{ items: Prob[] }>(`/resources/must-do?tier=${tier}&limit=25${md ? `&difficulty=${md}` : ""}${mu ? "&unsolved=true" : ""}`).then((r) => setMust(r.items)).catch(() => {}); }, [tier, md, mu]);
  const tl = ov.tiers.find((t) => t.id === tier);
  return <div className="grid" style={{ gap: 14 }}>
    <div className="row" style={{ gap: 8 }}><button className={`btn ${tier === "" ? "primary" : ""}`} onClick={() => setTier("")}>All</button>{ov.tiers.map((t) => <button key={t.id} className={`btn ${tier === t.id ? "primary" : ""}`} onClick={() => setTier(t.id)}>{t.label} <span className="muted mono" style={{ fontSize: 11 }}>{t.companies}</span></button>)}</div>
    {tier === "service" && <p className="muted" style={{ fontSize: 12 }}>Large IT-services and mass recruiters. Entry-level offers there are commonly below ~10 LPA, but pay varies by role, college and year: check each offer. This grouping is Nexora&apos;s own, not salary data.</p>}
    {tier && <div className="card"><div className="row" style={{ justifyContent: "space-between" }}><div><h2>⭐ Must-do for {tl?.label}</h2><p className="muted" style={{ fontSize: 12 }}>Problems reported by the <b>most companies</b> in this group: the best value for your time.</p></div><Link className="btn primary" href="/planner">Plan a 30/60-day sprint →</Link></div>
      <div className="row" style={{ margin: "10px 0" }}>{["", "Easy", "Medium", "Hard"].map((k) => <button key={k} className={`btn ${md === k ? "primary" : ""}`} onClick={() => setMd(k)}>{k || "all levels"}</button>)}<label className="chip" style={{ cursor: "pointer" }}><input type="checkbox" checked={mu} onChange={(e) => setMu(e.target.checked)} /> unsolved only</label></div><ProblemList items={must} mode="tier" /></div>}
    <div className="row"><input aria-label="Search companies" placeholder="Search a company (Amazon, TCS, Razorpay…)" value={q} onChange={(e) => setQ(e.target.value)} style={{ maxWidth: 380 }} /><span className="muted" style={{ fontSize: 12 }}>{total} {total === 1 ? "company" : "companies"}</span></div>
    {open && <CompanyPanel key={open} slug={open} onClose={() => setOpen(null)} />}
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(210px,1fr))", gap: 10 }}>{cos.map((c) => <button key={c.slug} onClick={() => { setOpen(c.slug); window.scrollTo({ top: 0, behavior: "smooth" }); }} className="card" style={{ cursor: "pointer", textAlign: "left", padding: 14, borderColor: open === c.slug ? "var(--violet)" : undefined }}>
      <b>{c.name}</b><div className="muted" style={{ fontSize: 11, margin: "2px 0 8px" }}>{ov.tiers.find((t) => t.id === c.tier)?.label}</div><div className="bar" style={{ height: 6 }}><i style={{ width: `${c.problems ? (c.solved / c.problems) * 100 : 0}%` }} /></div><div className="mono" style={{ fontSize: 12, marginTop: 6 }}>{c.solved}<span className="muted">/{c.problems} solved</span></div></button>)}</div>
    {cos.length < total && <button className="btn" onClick={() => fetchCos(cos.length).then((r) => setCos([...cos, ...r.items]))}>Show more companies</button>}
  </div>;
}

function DesignTab() {
  const [d, setD] = useState<{ items: DQ[]; categories: string[]; note: string } | null>(null), [level, setLevel] = useState(""), [cat, setCat] = useState(""), [kind, setKind] = useState("hld"), [q, setQ] = useState("");
  useEffect(() => { const t = setTimeout(() => api<NonNullable<typeof d>>(`/resources/system-design?kind=${kind}${level ? `&level=${level}` : ""}${cat ? `&category=${cat}` : ""}${q ? `&q=${encodeURIComponent(q)}` : ""}`).then(setD).catch(() => {}), 150); return () => clearTimeout(t); }, [level, cat, kind, q]);
  return <div className="grid" style={{ gap: 14 }}>
    <div className="row"><div className="seg"><button className={`btn ${kind === "hld" ? "primary" : ""}`} onClick={() => setKind("hld")}>High-level design</button><button className={`btn ${kind === "lld" ? "primary" : ""}`} onClick={() => setKind("lld")}>Low-level (class) design</button></div>
      {["", "entry", "mid", "senior"].map((l) => <button key={l} className={`btn ${level === l ? "primary" : ""}`} onClick={() => setLevel(l)}>{l || "all levels"}</button>)}</div>
    <div className="row"><input aria-label="Search" placeholder="Search (cache, feed, payments…)" value={q} onChange={(e) => setQ(e.target.value)} style={{ maxWidth: 320 }} />
      {kind === "hld" && <select aria-label="Category" value={cat} onChange={(e) => setCat(e.target.value)} style={{ width: 180 }}><option value="">all categories</option>{d?.categories.filter((c) => c !== "lld").map((c) => <option key={c}>{c}</option>)}</select>}</div>
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(290px,1fr))", gap: 12 }}>{d?.items.map((x) => <div key={x.slug} className="card" style={{ display: "grid", gap: 8, alignContent: "start" }}>
      <div className="row" style={{ justifyContent: "space-between" }}><b>{x.title}</b>{x.status && <span className={`st ${x.status === "reviewed" ? "mastered" : "learning"}`}>{x.status}</span>}</div>
      <div className="row" style={{ gap: 6 }}><span className={`st ${LC[x.level]}`}>{x.level}</span><span className="chip">{x.category}</span></div>
      <p className="muted" style={{ fontSize: 12 }}>{x.prompt}</p><div className="row" style={{ gap: 4 }}>{x.concepts.map((c) => <span key={c} className="chip" style={{ fontSize: 10 }}>{c}</span>)}</div>
      <Link className="btn primary" href={`/design?question=${x.slug}`} style={{ justifyContent: "center" }}>{x.status ? "Continue" : "Design it"} →</Link></div>)}</div>
    {d && d.items.length === 0 && <p className="muted">No questions match.</p>}
    {d && <p className="muted" style={{ fontSize: 11 }}>{d.note}</p>}
  </div>;
}

export default function Resources() {
  const [ov, setOv] = useState<Overview | null>(null), [tab, setTab] = useState<"dsa" | "sd">("dsa"), [err, setErr] = useState(""), [att, setAtt] = useState(false);
  useEffect(() => { api<Overview>("/resources/overview").then(setOv).catch((e) => setErr(e.message)); }, []);
  if (err) return <p className="err" role="alert">{err}</p>;
  if (!ov) return <div className="skeleton" style={{ height: 240 }} />;
  return <div className="grid" style={{ gap: 16 }}>
    <div><h1>Interview <span className="grad-text">resources</span></h1><p className="muted">What companies reportedly ask, grouped by company type and difficulty, with your progress on every list. Plus a system-design library from fresher to senior.</p></div>
    <div className="grid g3"><div className="card"><p className="muted">Company problems</p><h1 className="mono grad-text">{ov.distinct_problems.toLocaleString()}</h1></div><div className="card"><p className="muted">You solved</p><h1 className="mono">{ov.you_solved.toLocaleString()}</h1></div><div className="card"><p className="muted">Design questions</p><h1 className="mono">{ov.design_questions || "70+"}</h1></div></div>
    <div className="seg"><button className={`btn ${tab === "dsa" ? "primary" : ""}`} onClick={() => setTab("dsa")}>💻 DSA by company</button><button className={`btn ${tab === "sd" ? "primary" : ""}`} onClick={() => setTab("sd")}>🧩 System design</button><Link className="btn" href="/planner">🚀 30/60-day crash course</Link></div>
    {tab === "dsa" ? (ov.empty ? <div className="card"><h2>No company data loaded yet</h2><p className="muted" style={{ marginTop: 8 }}>An admin needs to run <code>scripts/ingest_company_lists.py</code> (see docs/interview-resources.md).</p></div> : <DsaTab ov={ov} />) : <DesignTab />}
    <button className="muted" style={{ background: "none", border: 0, cursor: "pointer", textAlign: "left", fontSize: 12 }} onClick={() => setAtt(!att)}>{att ? "▾" : "▸"} About this data</button>
    {att && <div className="card"><p style={{ fontSize: 13 }}>{ov.attribution.disclaimer}</p><p className="muted" style={{ fontSize: 12, marginTop: 6 }}>Source: <a href={ov.attribution.url} target="_blank" rel="noreferrer noopener">{ov.attribution.source}</a>. Nexora stores only company, problem link, difficulty, topics and the reported frequency; statements stay on LeetCode.</p></div>}
  </div>;
}
