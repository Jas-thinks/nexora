"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Bars, Donut } from "@/components/charts";

type It = { problem: { id: number; name: string; platform: string; url: string; rating: number | null }; status: string; failed_attempts: number; verdicts: Record<string, number>; patterns: string[]; diagnosis: string | null; diagnosis_kind: string | null; note: string; cause: string | null };
type N = { items: It[]; total: number; recurring_patterns: { pattern: string; name: string; failed_attempts: number }[]; verdict_mix: Record<string, number>; note: string };
const CAUSES = ["logic", "edge-case", "complexity", "implementation", "concept", "careless"];

function Row({ it, onSaved }: { it: It; onSaved: () => void }) {
  const [note, setNote] = useState(it.note), [cause, setCause] = useState(it.cause ?? ""), [saved, setSaved] = useState(false), [err, setErr] = useState("");
  async function save() { setErr(""); try { await api(`/mistakes/${it.problem.id}/note`, { method: "PUT", body: JSON.stringify({ note, cause: cause || null }) }); setSaved(true); onSaved(); setTimeout(() => setSaved(false), 1500); } catch (e) { setErr((e as Error).message); } }
  return (
    <div className="card" style={{ padding: 16 }}>
      <div className="row" style={{ justifyContent: "space-between" }}><div><Link href={`/problems/${it.problem.id}`}><b>{it.problem.name}</b></Link> <a className="muted" href={it.problem.url} target="_blank" rel="noreferrer noopener">↗</a>
        <div className="row" style={{ gap: 6, marginTop: 6 }}><span className={`st ${it.status === "open" ? "weak" : "mastered"}`}>{it.status}</span><span className="chip">{it.failed_attempts} failed attempts</span>{Object.entries(it.verdicts).map(([k, v]) => <span key={k} className="chip">{k}×{v}</span>)}{it.patterns.map((p) => <span key={p} className="chip">{p}</span>)}</div></div>
        <Link className="btn" href={`/studio?problem=${it.problem.id}`}>Retry in Studio</Link></div>
      {it.diagnosis && <p className="muted" style={{ fontSize: 13, marginTop: 10 }}>💡 {it.diagnosis}</p>}
      <div className="grid" style={{ gap: 8, marginTop: 10 }}><textarea rows={2} maxLength={2000} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Why did this fail? What will you check next time?" />
        <div className="row"><select aria-label="Cause" value={cause} onChange={(e) => setCause(e.target.value)} style={{ width: 180 }}><option value="">my diagnosis…</option>{CAUSES.map((c) => <option key={c}>{c}</option>)}</select><button className="btn" onClick={save}>{saved ? "Saved ✓" : "Save note"}</button>{err && <span className="err">{err}</span>}</div></div>
    </div>
  );
}

export default function Mistakes() {
  const [d, setD] = useState<N | null>(null), [err, setErr] = useState(""), [f, setF] = useState("all");
  const load = useCallback(() => api<N>("/mistakes").then(setD).catch((e) => setErr(e.message)), []);
  useEffect(() => { load(); }, [load]);
  if (err) return <p className="err" role="alert">{err}</p>;
  if (!d) return <div className="skeleton" style={{ height: 200 }} />;
  const items = d.items.filter((i) => f === "all" || i.status === f);
  return (
    <div className="grid" style={{ gap: 18 }}>
      <div><h1>Mistake <span className="grad-text">notebook</span></h1><p className="muted">Your failed attempts, grouped and diagnosed from the verdicts. The mentor sees your recurring mistakes, and problems you eventually solved go to revision automatically.</p></div>
      {d.total === 0 ? <div className="card"><h2>No recurring mistakes yet</h2><p className="muted" style={{ marginTop: 8 }}>Problems you fail twice or more appear here. Sync a platform to see your history.</p></div> : <>
        <div className="grid g2"><div className="card"><h2 style={{ marginBottom: 10 }}>Failure types</h2><Donut data={d.verdict_mix} /></div>
          <div className="card"><h2 style={{ marginBottom: 10 }}>Patterns where you fail most</h2><Bars data={d.recurring_patterns.map((p) => [p.name, p.failed_attempts] as [string, number])} color="var(--rose)" /></div></div>
        <div className="seg">{["all", "open", "recovered"].map((k) => <button key={k} className={`btn ${f === k ? "primary" : ""}`} onClick={() => setF(k)}>{k} {k === "all" ? d.total : d.items.filter((i) => i.status === k).length}</button>)}</div>
        <div className="grid">{items.map((it) => <Row key={it.problem.id} it={it} onSaved={load} />)}</div><p className="muted" style={{ fontSize: 12 }}>{d.note}</p></>}
    </div>
  );
}
