"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";

type L = { id: number; pattern: string; pattern_name: string; source: string; confidence: number; reason: string; problem: { id: number; name: string; platform: string; rating: number | null; tags: string[]; url: string } };
export default function Labels() {
  const [q, setQ] = useState<L[] | null>(null), [err, setErr] = useState(""), [stats, setStats] = useState<Record<string, unknown> | null>(null);
  const load = useCallback(() => { api<L[]>("/labels/queue?limit=25").then(setQ).catch((e) => setErr(e.message)); api<Record<string, unknown>>("/labels/stats").then(setStats).catch(() => {}); }, []);
  useEffect(() => { load(); }, [load]);
  async function review(id: number, decision: "accept" | "reject") { try { await api(`/labels/${id}/review`, { method: "POST", body: JSON.stringify({ decision }) }); setQ((x) => x && x.filter((l) => l.id !== id)); } catch (e) { setErr((e as Error).message); } }
  if (err) return <div><h1>Label review</h1><p className="err" role="alert">{err}</p><p className="muted">This page is for moderators and admins.</p></div>;
  if (!q) return <div className="skeleton" style={{ height: 200 }} />;
  return (
    <div className="grid" style={{ gap: 16 }}>
      <div><h1>Pattern label <span className="grad-text">review</span></h1><p className="muted">Proposed problem→pattern labels. Accepting is a human judgement and feeds pattern mastery; proposer precision is only reported after enough reviews.</p></div>
      {stats && <details className="card"><summary>Stats ▸</summary><pre className="mono" style={{ fontSize: 12, overflow: "auto" }}>{JSON.stringify(stats, null, 2)}</pre></details>}
      {q.length === 0 ? <div className="card"><p className="muted">Queue is empty.</p></div> : q.map((l) => <div key={l.id} className="card row" style={{ justifyContent: "space-between" }}>
        <div><a href={l.problem.url} target="_blank" rel="noreferrer noopener"><b>{l.problem.name} ↗</b></a> <span className="chip">{l.problem.platform}</span> {l.problem.rating && <span className="chip">{l.problem.rating}</span>}<p style={{ marginTop: 6 }}>→ <b>{l.pattern_name}</b> <span className="chip">{l.source} · {Math.round(l.confidence * 100)}%</span></p><p className="muted" style={{ fontSize: 12 }}>{l.reason} · tags: {l.problem.tags.join(", ")}</p></div>
        <div className="row"><button className="btn" onClick={() => review(l.id, "reject")}>Reject</button><button className="btn primary" onClick={() => review(l.id, "accept")}>Accept</button></div></div>)}
    </div>
  );
}
