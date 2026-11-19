"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { ratingColor } from "@/lib/rating";

type Item = { id: number; platform: string; name: string; url: string; rating: number | null; source_difficulty: string | null; tags: string[]; solved: boolean; sheets: string[] };
type Res = { total: number; platform_counts: Record<string, number>; items: Item[] };
type Sheet = { id: number; title: string };
const PAGE = 30;

export default function Explorer() {
  const [f, setF] = useState({ platform: "", sheet_id: "", tag: "", min_rating: "", max_rating: "", difficulty: "", solved: "", q: "" }), [page, setPage] = useState(0);
  const [res, setRes] = useState<Res | null>(null), [sheets, setSheets] = useState<Sheet[]>([]), [err, setErr] = useState(""), [loading, setLoading] = useState(true);
  useEffect(() => { api<Sheet[]>("/sheets").then(setSheets).catch(() => {}); }, []);
  useEffect(() => { const t = setTimeout(() => { setLoading(true); setErr("");
    const qs = new URLSearchParams({ limit: String(PAGE), offset: String(page * PAGE) }); Object.entries(f).forEach(([k, v]) => v && qs.set(k, v));
    api<Res>(`/explorer?${qs}`).then(setRes).catch((e) => setErr(e.message)).finally(() => setLoading(false)); }, 250); return () => clearTimeout(t); }, [f, page]);
  const set = (k: string, v: string) => { setPage(0); setF({ ...f, [k]: v }); };
  return (
    <div className="grid" style={{ gap: 20 }}>
      <div><h1>Problem <span className="grad-text">Explorer</span></h1><p className="muted">One catalog across platforms. A problem on several sheets is one record with several memberships.</p></div>
      <div className="card grid g3" style={{ gap: 12 }}>
        <div><label htmlFor="q">Search</label><input id="q" value={f.q} onChange={(e) => set("q", e.target.value)} placeholder="name contains…" /></div>
        <div><label htmlFor="pl">Platform</label><select id="pl" value={f.platform} onChange={(e) => set("platform", e.target.value)}><option value="">All{res ? ` (${Object.values(res.platform_counts).reduce((a, b) => a + b, 0)})` : ""}</option>{res && Object.entries(res.platform_counts).map(([k, v]) => <option key={k} value={k}>{k} ({v})</option>)}</select></div>
        <div><label htmlFor="sh">Sheet</label><select id="sh" value={f.sheet_id} onChange={(e) => set("sheet_id", e.target.value)}><option value="">Any</option>{sheets.map((s) => <option key={s.id} value={s.id}>{s.title}</option>)}</select></div>
        <div><label htmlFor="tg">Tag (exact)</label><input id="tg" value={f.tag} onChange={(e) => set("tag", e.target.value)} placeholder="dp, graphs, greedy…" /></div>
        <div className="row"><div style={{ flex: 1 }}><label htmlFor="mn">Rating ≥</label><input id="mn" type="number" min={800} step={100} value={f.min_rating} onChange={(e) => set("min_rating", e.target.value)} /></div><div style={{ flex: 1 }}><label htmlFor="mx">Rating ≤</label><input id="mx" type="number" min={800} step={100} value={f.max_rating} onChange={(e) => set("max_rating", e.target.value)} /></div></div>
        <div className="row"><div style={{ flex: 1 }}><label htmlFor="df">Difficulty label</label><select id="df" value={f.difficulty} onChange={(e) => set("difficulty", e.target.value)}><option value="">Any</option><option>Easy</option><option>Medium</option><option>Hard</option></select></div>
          <div style={{ flex: 1 }}><label htmlFor="sv">Status</label><select id="sv" value={f.solved} onChange={(e) => set("solved", e.target.value)}><option value="">All</option><option value="false">Unsolved</option><option value="true">Solved</option></select></div></div>
      </div>
      {err && <p className="err" role="alert">{err}</p>}
      {loading && !res ? <div className="skeleton" style={{ height: 200 }} /> : res && (<>
        <p className="muted" style={{ fontSize: 13 }}>{res.total.toLocaleString()} problems{loading ? " …" : ""}</p>
        {res.items.length === 0 ? <div className="card"><p>Nothing matches. Loosen a filter, or sync a platform/import a sheet on the Platforms and Sheets pages.</p></div> :
          <div className="card" style={{ padding: 0, overflowX: "auto" }}><table className="t"><thead><tr><th>Problem</th><th>Platform</th><th>Difficulty</th><th>Tags</th><th>Sheets</th></tr></thead><tbody>
            {res.items.map((p) => <tr key={p.id}><td><Link href={`/problems/${p.id}`} style={{ fontWeight: 600 }}>{p.name}</Link> <a href={p.url} target="_blank" rel="noreferrer noopener" aria-label="Open on platform" className="muted">↗</a> {p.solved && <span className="st mastered">solved</span>}</td><td>{p.platform}</td>
              <td><span className="pill mono" style={{ color: ratingColor(p.rating), background: "rgba(255,255,255,.06)" }}>{p.rating ?? p.source_difficulty ?? "—"}</span></td>
              <td>{p.tags.slice(0, 3).map((t) => <span key={t} className="chip" style={{ marginRight: 4 }}>{t}</span>)}</td><td className="muted" style={{ fontSize: 12 }}>{p.sheets.length ? p.sheets.join(" · ") : "—"}</td></tr>)}</tbody></table></div>}
        <div className="row"><button className="btn" disabled={page === 0} onClick={() => setPage(page - 1)}>← Prev</button><span className="mono muted">page {page + 1} / {Math.max(1, Math.ceil(res.total / PAGE))}</span><button className="btn" disabled={(page + 1) * PAGE >= res.total} onClick={() => setPage(page + 1)}>Next →</button></div></>)}
    </div>
  );
}
