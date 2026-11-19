"use client";
import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

type Row = { id: string; name: string; parent: string; status: string; score: number; solved: number; attempted: number; due_for_revision: boolean; missing_prereqs: string[] };
type Cov = { total_patterns: number; by_status: Record<string, number>; due_for_revision: number; note: string; patterns: Row[] };
type Tax = { version: string; review_status: string; patterns: { id: string; name: string; kind: string; prerequisites?: string[] }[] };
const Galaxy3D = dynamic(() => import("@/components/Galaxy3D"), { ssr: false, loading: () => <div className="skeleton" style={{ height: 520 }} /> });
const ORDER = ["mastered", "practised", "learning", "weak", "unexplored", "unmeasured"];

export default function Patterns() {
  const router = useRouter(); const [view, setView] = useState<"galaxy" | "grid">("galaxy");
  const [cov, setCov] = useState<Cov | null>(null), [tax, setTax] = useState<Tax | null>(null), [err, setErr] = useState(""), [f, setF] = useState("all");
  useEffect(() => { Promise.all([api<Cov>("/patterns/coverage"), api<Tax>("/patterns")]).then(([a, b]) => { setCov(a); setTax(b); }).catch((e) => setErr(e.message)); }, []);
  const groups = useMemo(() => {
    if (!cov || !tax) return [];
    const cats = tax.patterns.filter((p) => p.kind === "category");
    return cats.map((c) => ({ cat: c, items: cov.patterns.filter((p) => p.parent === c.id && (f === "all" || p.status === f || (f === "due" && p.due_for_revision))) })).filter((g) => g.items.length);
  }, [cov, tax, f]);
  if (err) return <p className="err" role="alert">{err}</p>;
  if (!cov || !tax) return <div className="skeleton" style={{ height: 200 }} />;
  return (
    <div className="grid" style={{ gap: 20 }}>
      <div><h1>Pattern <span className="grad-text">Universe</span></h1>
        <p className="muted">{cov.total_patterns} patterns in taxonomy v{tax.version} ({tax.review_status}). Mastery comes from coverage, accuracy, difficulty breadth and knowledge tracing, never just a solved count.</p></div>
      <div className="grid g3">{ORDER.map((s) => <button key={s} className="card hover" style={{ textAlign: "left", cursor: "pointer", color: "inherit" }} onClick={() => setF(f === s ? "all" : s)} aria-pressed={f === s}>
        <span className={`st ${s}`}>{s}</span><h1 className="mono" style={{ fontSize: 36, marginTop: 8 }}>{cov.by_status[s] ?? 0}</h1></button>)}
        <button className="card hover" style={{ textAlign: "left", cursor: "pointer", color: "inherit" }} onClick={() => setF(f === "due" ? "all" : "due")} aria-pressed={f === "due"}><span className="chip">due for revision</span><h1 className="mono" style={{ fontSize: 36, marginTop: 8 }}>{cov.due_for_revision}</h1></button></div>
      <div className="seg" role="tablist" aria-label="View"><button role="tab" aria-selected={view === "galaxy"} className={`btn ${view === "galaxy" ? "primary" : ""}`} onClick={() => setView("galaxy")}>3D map</button><button role="tab" aria-selected={view === "grid"} className={`btn ${view === "grid" ? "primary" : ""}`} onClick={() => setView("grid")}>Grid</button></div>
      {view === "galaxy" && <><Galaxy3D height={560} cats={tax.patterns.filter((p) => p.kind === "category").map((c) => ({ id: c.id, name: c.name }))} nodes={cov.patterns.map((p) => ({ id: p.id, name: p.name, parent: p.parent, status: p.status, score: p.score }))}
        edges={tax.patterns.flatMap((p) => (p.prerequisites ?? []).map((q) => [q, p.id] as [string, string]))} onPick={(id) => router.push(`/patterns/${id}`)} />
        <p className="muted" style={{ fontSize: 12 }}>Drag to orbit, scroll to zoom, click a star to open it. Colour = your mastery status, size = score, faint lines = prerequisites. Dim stars are unexplored/unmeasured.</p></>}
      {view === "grid" && groups.map(({ cat, items }) => <div key={cat.id}><h2 style={{ marginBottom: 10 }}>{cat.name}</h2>
        <div className="grid g3">{items.map((p) => <Link key={p.id} href={`/patterns/${p.id}`} className="card hover" style={{ padding: 14 }}>
          <div className="row" style={{ justifyContent: "space-between" }}><b>{p.name}</b><span className={`st ${p.status}`}>{p.status}</span></div>
          <div className="bar" style={{ margin: "10px 0 6px" }}><i style={{ width: `${p.score * 100}%` }} /></div>
          <span className="mono muted" style={{ fontSize: 11 }}>{p.solved}/{p.attempted} solved{p.due_for_revision ? " · due" : ""}{p.missing_prereqs.length ? ` · needs ${p.missing_prereqs.length} prereq` : ""}</span></Link>)}</div></div>)}
      <p className="muted" style={{ fontSize: 12 }}>{cov.note}</p>
    </div>
  );
}
